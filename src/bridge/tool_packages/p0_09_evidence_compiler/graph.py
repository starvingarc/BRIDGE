from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import networkx as nx
import pyarrow as pa
import pyarrow.parquet as pq

from bridge.tool_packages.p0_08_evidence_sufficiency.models import EvidenceSufficiencyProfile
from bridge.tool_packages.p0_09_evidence_compiler.compiler import (
    canonical_hash,
    canonical_json_bytes,
    evidence_record_content_hash,
    normalize_identity_payload,
    reconciliation_record_content_hash,
    requirement_content_hash,
)
from bridge.tool_packages.p0_09_evidence_compiler.models import (
    ClaimRegistry,
    ComparisonEvidenceGraphManifest,
    CompilationObjectRef,
    CytoscapeElements,
    CytoscapeEvidenceElements,
    EvidenceCompilationBundle,
    EvidenceFamilyRegistry,
    EvidenceGraphManifestBase,
    EvidenceLifecycleState,
    EvidenceRecord,
    EvidenceRequirement,
    EvidenceRequirementState,
    EvidenceTier,
    GraphEdgeRow,
    GraphEdgeType,
    GraphKind,
    GraphNodeRow,
    GraphNodeType,
    GraphRecordMode,
    ReconciliationRecord,
    ReconciliationSpecRegistry,
    validate_safe_json,
)


NODE_SCHEMA = pa.schema(
    [
        pa.field("graph_id", pa.string(), nullable=False),
        pa.field("graph_version", pa.int32(), nullable=False),
        pa.field("node_id", pa.string(), nullable=False),
        pa.field("node_type", pa.string(), nullable=False),
        pa.field("record_mode", pa.string(), nullable=False),
        pa.field("object_id", pa.string(), nullable=False),
        pa.field("object_version", pa.string(), nullable=False),
        pa.field("source_graph_id", pa.string(), nullable=True),
        pa.field("source_graph_version", pa.int32(), nullable=True),
        pa.field("lifecycle_state", pa.string(), nullable=True),
        pa.field("evidence_tier", pa.string(), nullable=True),
        pa.field("properties_json", pa.string(), nullable=True),
        pa.field("content_hash", pa.string(), nullable=False),
    ]
)

EDGE_SCHEMA = pa.schema(
    [
        pa.field("graph_id", pa.string(), nullable=False),
        pa.field("graph_version", pa.int32(), nullable=False),
        pa.field("edge_id", pa.string(), nullable=False),
        pa.field("edge_type", pa.string(), nullable=False),
        pa.field("source_node_id", pa.string(), nullable=False),
        pa.field("target_node_id", pa.string(), nullable=False),
        pa.field("properties_json", pa.string(), nullable=False),
        pa.field("content_hash", pa.string(), nullable=False),
    ]
)


ALLOWED_EDGE_ENDPOINTS: dict[GraphEdgeType, set[tuple[GraphNodeType, GraphNodeType]]] = {
    GraphEdgeType.DERIVED_FROM: {
        (GraphNodeType.EVIDENCE_RECORD, GraphNodeType.MEASUREMENT_RESULT),
        (GraphNodeType.EVIDENCE_RECORD, GraphNodeType.TOOL_RUN),
        (GraphNodeType.EVIDENCE_RECORD, GraphNodeType.SAMPLE),
        (GraphNodeType.EVIDENCE_RECORD, GraphNodeType.PREPARATION),
        (GraphNodeType.EVIDENCE_RECORD, GraphNodeType.REFERENCE_SNAPSHOT),
        (GraphNodeType.EVIDENCE_RECORD, GraphNodeType.PRIOR_SNAPSHOT),
        (GraphNodeType.EVIDENCE_RECORD, GraphNodeType.ARTIFACT),
    },
    GraphEdgeType.SUPPORTS: {(GraphNodeType.EVIDENCE_RECORD, GraphNodeType.CLAIM)},
    GraphEdgeType.CONTRADICTS: {(GraphNodeType.EVIDENCE_RECORD, GraphNodeType.CLAIM)},
    GraphEdgeType.DEPENDS_ON: {
        (GraphNodeType.EVIDENCE_RECORD, GraphNodeType.MEASUREMENT_SPEC),
        (GraphNodeType.EVIDENCE_RECORD, GraphNodeType.SCORE_CONTRACT),
        (GraphNodeType.EVIDENCE_RECORD, GraphNodeType.EVIDENCE_SUFFICIENCY_PROFILE),
        (GraphNodeType.PRODUCT_CASE, GraphNodeType.PRODUCT_DEFINITION_CARD),
        (GraphNodeType.CLAIM, GraphNodeType.RECONCILIATION_SPEC),
        (GraphNodeType.COMPARISON_RECORD, GraphNodeType.PRODUCT_CASE),
        (GraphNodeType.RECONCILIATION_RECORD, GraphNodeType.CLAIM),
        (GraphNodeType.RECONCILIATION_RECORD, GraphNodeType.RECONCILIATION_SPEC),
        (
            GraphNodeType.RECONCILIATION_RECORD,
            GraphNodeType.EVIDENCE_SUFFICIENCY_PROFILE,
        ),
        (GraphNodeType.RECONCILIATION_RECORD, GraphNodeType.EVIDENCE_RECORD),
    },
    GraphEdgeType.APPLICABLE_TO: {
        (GraphNodeType.EVIDENCE_RECORD, GraphNodeType.PRODUCT_CASE),
        (GraphNodeType.EVIDENCE_RECORD, GraphNodeType.COMPARISON_RECORD),
        (GraphNodeType.CLAIM, GraphNodeType.PRODUCT_CASE),
        (GraphNodeType.CLAIM, GraphNodeType.COMPARISON_RECORD),
        (GraphNodeType.EVIDENCE_REQUIREMENT, GraphNodeType.PRODUCT_CASE),
        (GraphNodeType.EVIDENCE_REQUIREMENT, GraphNodeType.COMPARISON_RECORD),
    },
    GraphEdgeType.MISSING_FOR: {
        (GraphNodeType.EVIDENCE_REQUIREMENT, GraphNodeType.CLAIM)
    },
    GraphEdgeType.BELONGS_TO_EVIDENCE_FAMILY: {
        (GraphNodeType.EVIDENCE_RECORD, GraphNodeType.EVIDENCE_FAMILY)
    },
    GraphEdgeType.SUPERSEDES: {
        (GraphNodeType.EVIDENCE_RECORD, GraphNodeType.EVIDENCE_RECORD)
    },
    GraphEdgeType.INVALIDATES: {
        (GraphNodeType.EVIDENCE_RECORD, GraphNodeType.EVIDENCE_RECORD)
    },
}


def node_id(
    object_id: str, object_version: str, node_type: GraphNodeType
) -> str:
    digest = hashlib.sha256(f"{object_id}@{object_version}".encode("utf-8")).hexdigest()[:24]
    return f"node:{node_type.value}:{digest}"


def build_graph_rows(
    *,
    graph_id: str,
    graph_version: int,
    bundle: EvidenceCompilationBundle,
    records: list[EvidenceRecord],
    requirements: list[EvidenceRequirement],
    reconciliation_records: list[ReconciliationRecord],
    profiles_by_input_id: Mapping[str, EvidenceSufficiencyProfile],
    family_registry: EvidenceFamilyRegistry,
    claim_registry: ClaimRegistry,
    reconciliation_registry: ReconciliationSpecRegistry,
) -> tuple[list[GraphNodeRow], list[GraphEdgeRow]]:
    nodes: dict[str, GraphNodeRow] = {}
    edges: dict[str, GraphEdgeRow] = {}
    catalog = {(item.object_id, item.object_version): item for item in bundle.object_catalog}

    def add_node(row: GraphNodeRow) -> None:
        existing = nodes.get(row.node_id)
        if existing is not None and existing != row:
            raise ValueError("graph_invariant_failed: node identity collision")
        nodes[row.node_id] = row

    def add_owned(
        *,
        object_id: str,
        object_version: str,
        node_type: GraphNodeType,
        properties: object,
        content_hash: str | None = None,
        lifecycle_state: str | None = None,
        evidence_tier: str | None = None,
        allow_upstream_no_score_fields: bool = False,
    ) -> str:
        normalized_properties = normalize_identity_payload(properties)
        if not allow_upstream_no_score_fields:
            validate_safe_json(normalized_properties, location="graph properties")
        properties_json = canonical_json_bytes(normalized_properties).decode("utf-8")
        row = GraphNodeRow(
            graph_id=graph_id,
            graph_version=graph_version,
            node_id=node_id(object_id, object_version, node_type),
            node_type=node_type,
            record_mode=GraphRecordMode.OWNED,
            object_id=object_id,
            object_version=object_version,
            source_graph_id=None,
            source_graph_version=None,
            lifecycle_state=lifecycle_state,
            evidence_tier=evidence_tier,
            properties_json=properties_json,
            content_hash=content_hash or canonical_hash(normalized_properties),
        )
        add_node(row)
        return row.node_id

    def add_catalog(ref: Any) -> str:
        key = (ref.object_id, ref.object_version)
        item = catalog.get(key)
        if item is None:
            raise ValueError(f"graph_invariant_failed: missing object catalog node {ref.ref}")
        return add_owned(
            object_id=item.object_id,
            object_version=item.object_version,
            node_type=item.node_type,
            properties={"schema_ref": item.schema_ref},
            content_hash=item.content_hash,
        )

    def add_edge(
        edge_type: GraphEdgeType,
        source: str,
        target: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        properties_json = canonical_json_bytes(properties or {}).decode("utf-8")
        properties_hash = canonical_hash(properties or {})
        identity = f"{graph_id}|{edge_type.value}|{source}|{target}|{properties_hash}"
        edge_digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
        row = GraphEdgeRow(
            graph_id=graph_id,
            graph_version=graph_version,
            edge_id=f"edge:{edge_digest}",
            edge_type=edge_type,
            source_node_id=source,
            target_node_id=target,
            properties_json=properties_json,
            content_hash=hashlib.sha256(identity.encode("utf-8")).hexdigest(),
        )
        if row.edge_id in edges:
            raise ValueError("graph_invariant_failed: duplicate exact edge")
        edges[row.edge_id] = row

    if bundle.graph_kind is GraphKind.CASE:
        assert bundle.product_case_ref is not None
        root_id = add_catalog(bundle.product_case_ref)
        root_type = GraphNodeType.PRODUCT_CASE
    else:
        assert bundle.comparison_ref is not None
        root_id = add_catalog(bundle.comparison_ref)
        root_type = GraphNodeType.COMPARISON_RECORD
        external_case_nodes: dict[str, str] = {}
        for case_ref in sorted(bundle.case_graph_refs, key=lambda item: item.graph_id):
            case = case_ref.product_case_ref
            case_id = node_id(case.object_id, case.object_version, GraphNodeType.PRODUCT_CASE)
            add_node(
                GraphNodeRow(
                    graph_id=graph_id,
                    graph_version=graph_version,
                    node_id=case_id,
                    node_type=GraphNodeType.PRODUCT_CASE,
                    record_mode=GraphRecordMode.EXTERNAL_REF,
                    object_id=case.object_id,
                    object_version=case.object_version,
                    source_graph_id=case_ref.graph_id,
                    source_graph_version=case_ref.graph_version,
                    lifecycle_state=None,
                    evidence_tier=None,
                    properties_json=None,
                    content_hash=case_ref.manifest_sha256,
                )
            )
            external_case_nodes[case_ref.graph_id] = case_id
            add_edge(GraphEdgeType.DEPENDS_ON, root_id, case_id)

    claims_by_ref = {item.ref: item for item in claim_registry.claims}
    families_by_ref = {item.ref: item for item in family_registry.families}
    specs_by_ref = {item.ref: item for item in reconciliation_registry.specs}
    profiles_by_ref = {
        f"{item.profile_id}@{item.profile_version}": item
        for item in profiles_by_input_id.values()
    }
    effective_lifecycle = _effective_lifecycle(records)

    evidence_nodes: dict[str, str] = {}
    if bundle.graph_kind is GraphKind.CASE:
        for record in sorted(records, key=lambda item: (item.evidence_id, item.evidence_version)):
            evidence_ref = record.ref
            evidence_node = add_owned(
                object_id=record.evidence_id,
                object_version=str(record.evidence_version),
                node_type=GraphNodeType.EVIDENCE_RECORD,
                properties=record.model_dump(mode="json"),
                content_hash=record.content_hash,
                lifecycle_state=effective_lifecycle[evidence_ref].value,
                evidence_tier=record.evidence_tier.value,
            )
            evidence_nodes[evidence_ref] = evidence_node
            claim = claims_by_ref.get(record.claim_ref.ref)
            family = families_by_ref.get(record.evidence_family_ref.ref)
            profile = profiles_by_ref.get(record.sufficiency_profile_ref.ref)
            if claim is None or family is None or profile is None:
                raise ValueError("graph_invariant_failed: unresolved evidence registry binding")
            claim_node = add_owned(
                object_id=claim.claim_id,
                object_version=claim.version,
                node_type=GraphNodeType.CLAIM,
                properties=claim.model_dump(mode="json"),
            )
            family_node = add_owned(
                object_id=family.evidence_family_id,
                object_version=family.version,
                node_type=GraphNodeType.EVIDENCE_FAMILY,
                properties=family.model_dump(mode="json"),
            )
            profile_node = add_owned(
                object_id=profile.profile_id,
                object_version=profile.profile_version,
                node_type=GraphNodeType.EVIDENCE_SUFFICIENCY_PROFILE,
                properties=profile.model_dump(mode="json"),
                allow_upstream_no_score_fields=True,
            )
            measurement_result = add_catalog(record.measurement_result_ref)
            measurement_spec = add_catalog(record.measurement_spec_ref)
            sample = add_catalog(record.sample_or_preparation_ref)
            tool_run = add_catalog(record.tool_run_ref)
            for target in (measurement_result, sample, tool_run):
                add_edge(GraphEdgeType.DERIVED_FROM, evidence_node, target)
            for ref in [*record.reference_refs, *record.prior_refs, *record.artifact_refs]:
                add_edge(GraphEdgeType.DERIVED_FROM, evidence_node, add_catalog(ref))
            add_edge(GraphEdgeType.DEPENDS_ON, evidence_node, measurement_spec)
            add_edge(GraphEdgeType.DEPENDS_ON, evidence_node, profile_node)
            if record.score_contract_ref is not None:
                add_edge(GraphEdgeType.DEPENDS_ON, evidence_node, add_catalog(record.score_contract_ref))
            add_edge(GraphEdgeType.APPLICABLE_TO, evidence_node, root_id)
            add_edge(GraphEdgeType.BELONGS_TO_EVIDENCE_FAMILY, evidence_node, family_node)
            if effective_lifecycle[evidence_ref] is EvidenceLifecycleState.ACTIVE:
                add_edge(
                    GraphEdgeType(record.relation.value),
                    evidence_node,
                    claim_node,
                )
            if record.predecessor_ref is not None:
                predecessor_node = evidence_nodes.get(record.predecessor_ref)
                if predecessor_node is None:
                    raise ValueError("graph_invariant_failed: revision predecessor missing")
                add_edge(
                    GraphEdgeType.INVALIDATES
                    if record.lifecycle_state is EvidenceLifecycleState.INVALIDATED
                    else GraphEdgeType.SUPERSEDES,
                    evidence_node,
                    predecessor_node,
                )
    else:
        case_graphs = {item.graph_id: item for item in bundle.case_graph_refs}
        for external in sorted(bundle.external_case_evidence_refs, key=lambda item: item.evidence_ref):
            evidence_id, evidence_version = external.evidence_ref.rsplit("@", 1)
            source = case_graphs[external.source_case_graph_ref.graph_id]
            external_node_id = node_id(
                evidence_id, evidence_version, GraphNodeType.EVIDENCE_RECORD
            )
            add_node(
                GraphNodeRow(
                    graph_id=graph_id,
                    graph_version=graph_version,
                    node_id=external_node_id,
                    node_type=GraphNodeType.EVIDENCE_RECORD,
                    record_mode=GraphRecordMode.EXTERNAL_REF,
                    object_id=evidence_id,
                    object_version=evidence_version,
                    source_graph_id=source.graph_id,
                    source_graph_version=source.graph_version,
                    lifecycle_state=external.lifecycle_state.value,
                    evidence_tier=external.evidence_tier.value,
                    properties_json=None,
                    content_hash=external.evidence_content_hash,
                )
            )
            evidence_nodes[external.evidence_ref] = external_node_id
            claim = claims_by_ref[external.comparison_claim_ref.ref]
            family = families_by_ref[external.evidence_family_ref.ref]
            profile = profiles_by_input_id[external.sufficiency_profile_input_id]
            claim_node = add_owned(
                object_id=claim.claim_id,
                object_version=claim.version,
                node_type=GraphNodeType.CLAIM,
                properties=claim.model_dump(mode="json"),
            )
            family_node = add_owned(
                object_id=family.evidence_family_id,
                object_version=family.version,
                node_type=GraphNodeType.EVIDENCE_FAMILY,
                properties=family.model_dump(mode="json"),
            )
            profile_node = add_owned(
                object_id=profile.profile_id,
                object_version=profile.profile_version,
                node_type=GraphNodeType.EVIDENCE_SUFFICIENCY_PROFILE,
                properties=profile.model_dump(mode="json"),
                allow_upstream_no_score_fields=True,
            )
            add_edge(GraphEdgeType.DEPENDS_ON, external_node_id, profile_node)
            add_edge(GraphEdgeType.APPLICABLE_TO, external_node_id, root_id)
            add_edge(GraphEdgeType.BELONGS_TO_EVIDENCE_FAMILY, external_node_id, family_node)
            add_edge(
                GraphEdgeType.APPLICABLE_TO,
                external_node_id,
                external_case_nodes[external.source_case_graph_ref.graph_id],
                {"source_case_projection": True},
            )
            if external.lifecycle_state is EvidenceLifecycleState.ACTIVE:
                add_edge(GraphEdgeType(external.relation.value), external_node_id, claim_node)

    relevant_claim_refs = {
        record.claim_ref.ref for record in records
    } | {item.comparison_claim_ref.ref for item in bundle.external_case_evidence_refs} | {
        item.claim_ref.ref for item in requirements
    }
    for claim_ref in sorted(relevant_claim_refs):
        claim = claims_by_ref[claim_ref]
        claim_node = add_owned(
            object_id=claim.claim_id,
            object_version=claim.version,
            node_type=GraphNodeType.CLAIM,
            properties=claim.model_dump(mode="json"),
        )
        spec = specs_by_ref.get(claim.reconciliation_spec_ref.ref)
        if spec is not None:
            spec_node = add_owned(
                object_id=spec.reconciliation_spec_id,
                object_version=spec.version,
                node_type=GraphNodeType.RECONCILIATION_SPEC,
                properties=spec.model_dump(mode="json"),
            )
            add_edge(GraphEdgeType.DEPENDS_ON, claim_node, spec_node)
        add_edge(GraphEdgeType.APPLICABLE_TO, claim_node, root_id)

    latest_requirements = _latest_requirements(requirements)
    for requirement in sorted(
        requirements, key=lambda item: (item.requirement_id, item.requirement_version)
    ):
        requirement_node = add_owned(
            object_id=requirement.requirement_id,
            object_version=str(requirement.requirement_version),
            node_type=GraphNodeType.EVIDENCE_REQUIREMENT,
            properties=requirement.model_dump(mode="json"),
            content_hash=requirement.content_hash,
            lifecycle_state=(
                requirement.state.value
                if latest_requirements[requirement.requirement_id] == requirement
                else EvidenceLifecycleState.SUPERSEDED.value
            ),
        )
        claim_node = node_id(
            requirement.claim_ref.object_id,
            requirement.claim_ref.object_version,
            GraphNodeType.CLAIM,
        )
        add_edge(GraphEdgeType.APPLICABLE_TO, requirement_node, root_id)
        if (
            latest_requirements[requirement.requirement_id] == requirement
            and requirement.state is EvidenceRequirementState.OPEN
        ):
            add_edge(GraphEdgeType.MISSING_FOR, requirement_node, claim_node)

    for reconciliation in reconciliation_records:
        reconciliation_node = add_owned(
            object_id=reconciliation.reconciliation_id,
            object_version=str(reconciliation.reconciliation_version),
            node_type=GraphNodeType.RECONCILIATION_RECORD,
            properties=reconciliation.model_dump(mode="json"),
            content_hash=reconciliation.content_hash,
        )
        claim_node = node_id(
            reconciliation.claim_ref.object_id,
            reconciliation.claim_ref.object_version,
            GraphNodeType.CLAIM,
        )
        spec_node = node_id(
            reconciliation.reconciliation_spec_ref.object_id,
            reconciliation.reconciliation_spec_ref.object_version,
            GraphNodeType.RECONCILIATION_SPEC,
        )
        for target in [claim_node, spec_node]:
            if target in nodes:
                add_edge(GraphEdgeType.DEPENDS_ON, reconciliation_node, target)
        for profile_ref in reconciliation.sufficiency_profile_refs:
            target = node_id(
                profile_ref.object_id,
                profile_ref.object_version,
                GraphNodeType.EVIDENCE_SUFFICIENCY_PROFILE,
            )
            if target in nodes:
                add_edge(GraphEdgeType.DEPENDS_ON, reconciliation_node, target)
        for evidence_ref in reconciliation.included_evidence_refs:
            target = evidence_nodes.get(evidence_ref)
            if target is not None:
                add_edge(GraphEdgeType.DEPENDS_ON, reconciliation_node, target)

    node_rows = sorted(nodes.values(), key=lambda item: item.node_id)
    edge_rows = sorted(edges.values(), key=lambda item: item.edge_id)
    validate_graph_rows(node_rows, edge_rows, root_id=root_id, root_type=root_type)
    return node_rows, edge_rows


def validate_graph_rows(
    nodes: Sequence[GraphNodeRow],
    edges: Sequence[GraphEdgeRow],
    *,
    root_id: str | None = None,
    root_type: GraphNodeType | None = None,
    expected_graph_id: str | None = None,
    expected_graph_version: int | None = None,
) -> nx.MultiDiGraph:
    if not nodes:
        raise ValueError("graph_invariant_failed: graph has no nodes")
    graph_ids = {item.graph_id for item in nodes} | {item.graph_id for item in edges}
    versions = {item.graph_version for item in nodes} | {item.graph_version for item in edges}
    if len(graph_ids) != 1 or len(versions) != 1:
        raise ValueError("graph_invariant_failed: mixed graph identity")
    if expected_graph_id is not None and graph_ids != {expected_graph_id}:
        raise ValueError("graph_invariant_failed: graph ID does not match manifest")
    if expected_graph_version is not None and versions != {expected_graph_version}:
        raise ValueError("graph_invariant_failed: graph version does not match manifest")
    if len({item.node_id for item in nodes}) != len(nodes):
        raise ValueError("graph_invariant_failed: duplicate node")
    if len({item.edge_id for item in edges}) != len(edges):
        raise ValueError("graph_invariant_failed: duplicate edge")
    node_map = {item.node_id: item for item in nodes}
    graph = nx.MultiDiGraph()
    for item in nodes:
        if item.node_id != node_id(item.object_id, item.object_version, item.node_type):
            raise ValueError("graph_invariant_failed: node ID mismatch")
        if item.node_type is GraphNodeType.EVIDENCE_RECORD:
            if item.evidence_tier is None or item.lifecycle_state is None:
                raise ValueError("graph_invariant_failed: evidence metadata missing")
            EvidenceTier(item.evidence_tier)
            EvidenceLifecycleState(item.lifecycle_state)
        elif item.node_type is GraphNodeType.EVIDENCE_REQUIREMENT:
            if item.evidence_tier is not None or item.lifecycle_state not in {
                EvidenceRequirementState.OPEN.value,
                EvidenceRequirementState.SATISFIED.value,
                EvidenceRequirementState.NOT_APPLICABLE.value,
                EvidenceLifecycleState.SUPERSEDED.value,
            }:
                raise ValueError("graph_invariant_failed: requirement metadata mismatch")
        elif item.evidence_tier is not None or item.lifecycle_state is not None:
            raise ValueError("graph_invariant_failed: non-evidence metadata mismatch")
        if item.record_mode is GraphRecordMode.OWNED:
            if (
                item.source_graph_id is not None
                or item.source_graph_version is not None
                or item.properties_json is None
            ):
                raise ValueError("graph_invariant_failed: owned node metadata mismatch")
            try:
                properties = json.loads(item.properties_json)
            except (json.JSONDecodeError, TypeError) as exc:
                raise ValueError(
                    "graph_invariant_failed: invalid owned node properties"
                ) from exc
            if canonical_json_bytes(properties).decode("utf-8") != item.properties_json:
                raise ValueError("graph_invariant_failed: non-canonical node properties")
            if item.node_type is GraphNodeType.EVIDENCE_RECORD:
                expected_content_hash = evidence_record_content_hash(
                    EvidenceRecord.model_validate(properties)
                )
            elif item.node_type is GraphNodeType.EVIDENCE_REQUIREMENT:
                expected_content_hash = requirement_content_hash(
                    EvidenceRequirement.model_validate(properties)
                )
            elif item.node_type is GraphNodeType.RECONCILIATION_RECORD:
                expected_content_hash = reconciliation_record_content_hash(
                    ReconciliationRecord.model_validate(properties)
                )
            elif item.node_type in {
                GraphNodeType.CLAIM,
                GraphNodeType.EVIDENCE_FAMILY,
                GraphNodeType.EVIDENCE_SUFFICIENCY_PROFILE,
                GraphNodeType.RECONCILIATION_SPEC,
            }:
                expected_content_hash = canonical_hash(
                    normalize_identity_payload(properties)
                )
            else:
                # Catalog-backed owned nodes carry the content hash of the
                # referenced object while exposing only its Schema binding.
                expected_content_hash = item.content_hash
            if expected_content_hash != item.content_hash:
                raise ValueError("graph_invariant_failed: node content hash mismatch")
        elif (
            item.properties_json is not None
            or item.source_graph_id is None
            or item.source_graph_version is None
        ):
            raise ValueError("graph_invariant_failed: external node metadata mismatch")
        graph.add_node(item.node_id, **item.model_dump(mode="json"))
    seen_exact: set[tuple[str, str, str, str]] = set()
    for edge in edges:
        try:
            properties = json.loads(edge.properties_json)
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError("graph_invariant_failed: invalid edge properties") from exc
        if canonical_json_bytes(properties).decode("utf-8") != edge.properties_json:
            raise ValueError("graph_invariant_failed: non-canonical edge properties")
        properties_hash = canonical_hash(properties)
        identity = (
            f"{edge.graph_id}|{edge.edge_type.value}|{edge.source_node_id}|"
            f"{edge.target_node_id}|{properties_hash}"
        )
        expected_hash = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        if (
            edge.content_hash != expected_hash
            or edge.edge_id != f"edge:{expected_hash[:24]}"
        ):
            raise ValueError("graph_invariant_failed: edge identity mismatch")
        if edge.source_node_id == edge.target_node_id:
            raise ValueError("graph_invariant_failed: self loop")
        if edge.source_node_id not in node_map or edge.target_node_id not in node_map:
            raise ValueError("graph_invariant_failed: dangling edge")
        source_type = node_map[edge.source_node_id].node_type
        target_type = node_map[edge.target_node_id].node_type
        if (source_type, target_type) not in ALLOWED_EDGE_ENDPOINTS[edge.edge_type]:
            raise ValueError("graph_invariant_failed: forbidden edge endpoint")
        exact = (
            edge.edge_type.value,
            edge.source_node_id,
            edge.target_node_id,
            edge.properties_json,
        )
        if exact in seen_exact:
            raise ValueError("graph_invariant_failed: duplicate exact edge")
        seen_exact.add(exact)
        graph.add_edge(
            edge.source_node_id,
            edge.target_node_id,
            key=edge.edge_id,
            **edge.model_dump(mode="json"),
        )
    revision_graph = nx.DiGraph(
        (
            edge.source_node_id,
            edge.target_node_id,
        )
        for edge in edges
        if edge.edge_type in {GraphEdgeType.SUPERSEDES, GraphEdgeType.INVALIDATES}
    )
    if not nx.is_directed_acyclic_graph(revision_graph):
        raise ValueError("graph_invariant_failed: revision cycle")
    if root_id is not None:
        if root_id not in node_map or node_map[root_id].node_type is not root_type:
            raise ValueError("graph_invariant_failed: root mismatch")
        if set(nx.node_connected_component(graph.to_undirected(), root_id)) != set(graph.nodes):
            raise ValueError("graph_invariant_failed: node not reachable from root")
    return graph


def write_parquet(
    nodes_path: Path,
    edges_path: Path,
    nodes: Sequence[GraphNodeRow],
    edges: Sequence[GraphEdgeRow],
) -> None:
    node_table = pa.Table.from_pylist(
        [item.model_dump(mode="json") for item in sorted(nodes, key=lambda row: row.node_id)],
        schema=NODE_SCHEMA,
    )
    edge_table = pa.Table.from_pylist(
        [item.model_dump(mode="json") for item in sorted(edges, key=lambda row: row.edge_id)],
        schema=EDGE_SCHEMA,
    )
    options = {
        "version": "2.6",
        "compression": "zstd",
        "compression_level": 9,
        "use_dictionary": False,
        "write_statistics": True,
        "data_page_version": "1.0",
    }
    pq.write_table(node_table, nodes_path, **options)
    pq.write_table(edge_table, edges_path, **options)


def read_parquet_rows(
    nodes_path: Path, edges_path: Path
) -> tuple[list[GraphNodeRow], list[GraphEdgeRow]]:
    node_table = pq.read_table(nodes_path)
    edge_table = pq.read_table(edges_path)
    return _tables_to_rows(node_table, edge_table)


def read_parquet_bytes(
    nodes_payload: bytes, edges_payload: bytes
) -> tuple[list[GraphNodeRow], list[GraphEdgeRow]]:
    """Parse the exact immutable bytes whose checksums were already verified."""

    node_table = pq.read_table(pa.BufferReader(nodes_payload))
    edge_table = pq.read_table(pa.BufferReader(edges_payload))
    return _tables_to_rows(node_table, edge_table)


def _tables_to_rows(
    node_table: pa.Table, edge_table: pa.Table
) -> tuple[list[GraphNodeRow], list[GraphEdgeRow]]:
    if node_table.schema != NODE_SCHEMA or edge_table.schema != EDGE_SCHEMA:
        raise ValueError("manifest_integrity_failed: parquet schema mismatch")
    nodes = [GraphNodeRow.model_validate(item) for item in node_table.to_pylist()]
    edges = [GraphEdgeRow.model_validate(item) for item in edge_table.to_pylist()]
    return nodes, edges


def cytoscape_projection(
    *,
    graph_id: str,
    graph_version: int,
    nodes: Sequence[GraphNodeRow],
    edges: Sequence[GraphEdgeRow],
    node_limit: int = 500,
    edge_limit: int = 1000,
) -> CytoscapeEvidenceElements:
    selected_nodes = sorted(nodes, key=lambda item: item.node_id)[:node_limit]
    selected_ids = {item.node_id for item in selected_nodes}
    eligible_edges = [
        item
        for item in sorted(edges, key=lambda edge: edge.edge_id)
        if item.source_node_id in selected_ids and item.target_node_id in selected_ids
    ]
    selected_edges = eligible_edges[:edge_limit]
    node_payloads = [
        {
            "data": {
                "id": item.node_id,
                "node_type": item.node_type.value,
                "object_id": item.object_id,
                "object_version": item.object_version,
                "lifecycle_state": item.lifecycle_state,
                "evidence_tier": item.evidence_tier,
                "label": item.object_id,
            }
        }
        for item in selected_nodes
    ]
    edge_payloads = [
        {
            "data": {
                "id": item.edge_id,
                "source": item.source_node_id,
                "target": item.target_node_id,
                "edge_type": item.edge_type.value,
            }
        }
        for item in selected_edges
    ]
    return CytoscapeEvidenceElements(
        graph_id=graph_id,
        graph_version=graph_version,
        elements=CytoscapeElements(nodes=node_payloads, edges=edge_payloads),
        filters={"node_order": "node_id", "edge_order": "edge_id"},
        truncated=len(selected_nodes) < len(nodes) or len(selected_edges) < len(edges),
        returned_node_count=len(selected_nodes),
        returned_edge_count=len(selected_edges),
        omitted_node_count=len(nodes) - len(selected_nodes),
        omitted_edge_count=len(edges) - len(selected_edges),
    )


def object_counts(nodes: Iterable[GraphNodeRow]) -> dict[GraphNodeType, int]:
    counts = Counter(item.node_type for item in nodes)
    return {node_type: counts[node_type] for node_type in GraphNodeType if counts[node_type]}


def _effective_lifecycle(records: Sequence[EvidenceRecord]) -> dict[str, EvidenceLifecycleState]:
    by_id: dict[str, list[EvidenceRecord]] = defaultdict(list)
    for record in records:
        by_id[record.evidence_id].append(record)
    result: dict[str, EvidenceLifecycleState] = {}
    for versions in by_id.values():
        versions = sorted(versions, key=lambda item: item.evidence_version)
        for item in versions:
            result[item.ref] = item.lifecycle_state
        for predecessor, successor in zip(versions, versions[1:], strict=False):
            result[predecessor.ref] = (
                EvidenceLifecycleState.INVALIDATED
                if successor.lifecycle_state is EvidenceLifecycleState.INVALIDATED
                else EvidenceLifecycleState.SUPERSEDED
            )
    return result


def _latest_requirements(
    requirements: Sequence[EvidenceRequirement],
) -> dict[str, EvidenceRequirement]:
    latest: dict[str, EvidenceRequirement] = {}
    for item in requirements:
        if (
            item.requirement_id not in latest
            or item.requirement_version > latest[item.requirement_id].requirement_version
        ):
            latest[item.requirement_id] = item
    return latest
