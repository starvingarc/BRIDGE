from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import stat
from typing import Any, Iterable, Sequence

import networkx as nx

from bridge.tool_packages.p0_08_evidence_sufficiency.models import P0DomainId
from bridge.tool_packages.p0_09_evidence_compiler.compiler import (
    canonical_hash,
    canonical_json_bytes,
    evidence_identity,
    evidence_record_logical_key,
    graph_identity_for_ref,
    reconciliation_identity,
    requirement_identity,
)
from bridge.tool_packages.p0_09_evidence_compiler.graph import (
    node_id,
    object_counts,
    read_parquet_bytes,
    validate_graph_rows,
)
from bridge.tool_packages.p0_09_evidence_compiler.models import (
    CaseEvidenceGraphManifest,
    ClaimSpec,
    ComparisonEvidenceGraphManifest,
    EvidenceGraphQueryResult,
    EvidenceApplicability,
    EvidenceFamilySpec,
    EvidenceFamilyStatus,
    EvidenceRecordSet,
    EvidenceRequirementSet,
    EvidenceLifecycleState,
    EvidenceRequirementState,
    EvidenceTier,
    GraphEdgeRow,
    GraphEdgeType,
    GraphKind,
    GraphNodeRow,
    GraphNodeType,
    GraphRecordMode,
    ReconciliationRecordSet,
    RevisionAction,
    VersionedObjectRef,
)


_DANGEROUS_PARAMETER = re.compile(
    r"(?:\.\.|[/\\;]|\b(?:match|create|merge|delete|detach|set|remove|drop|call|load\s+csv)\b)",
    re.IGNORECASE,
)


def _safe_artifact_filename(filename: str) -> bool:
    path = Path(filename)
    return (
        bool(filename)
        and not path.is_absolute()
        and path.name == filename
        and filename not in {".", ".."}
        and "/" not in filename
        and "\\" not in filename
    )


def _read_regular_file(path: Path) -> bytes:
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or path.is_symlink():
        raise OSError("not a regular file")
    raw = path.read_bytes()
    after = path.lstat()
    if (
        not stat.S_ISREG(after.st_mode)
        or before.st_dev != after.st_dev
        or before.st_ino != after.st_ino
        or before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or len(raw) != after.st_size
    ):
        raise OSError("artifact changed while reading")
    return raw


def _validate_comparison_projection(
    manifest: ComparisonEvidenceGraphManifest,
    nodes: Sequence[GraphNodeRow],
    edges: Sequence[GraphEdgeRow],
    reconciliation_set: ReconciliationRecordSet,
) -> None:
    refs = {
        (item.graph_id, item.graph_version): item for item in manifest.case_graph_refs
    }
    if len(refs) != len(manifest.case_graph_refs):
        raise ValueError("manifest_integrity_failed")
    node_map = {item.node_id: item for item in nodes}
    case_nodes: dict[tuple[str, int], GraphNodeRow] = {}
    for node in nodes:
        if node.node_type is GraphNodeType.PRODUCT_CASE:
            if (
                node.record_mode is not GraphRecordMode.EXTERNAL_REF
                or node.source_graph_id is None
                or node.source_graph_version is None
                or node.properties_json is not None
            ):
                raise ValueError("manifest_integrity_failed")
            key = (node.source_graph_id, node.source_graph_version)
            ref = refs.get(key)
            if (
                ref is None
                or key in case_nodes
                or node.object_id != ref.product_case_ref.object_id
                or node.object_version != ref.product_case_ref.object_version
                or node.content_hash != ref.manifest_sha256
            ):
                raise ValueError("manifest_integrity_failed")
            case_nodes[key] = node
    if set(case_nodes) != set(refs):
        raise ValueError("manifest_integrity_failed")

    root = _node_for_ref(nodes, manifest.comparison_ref, {GraphNodeType.COMPARISON_RECORD})
    bindings = {item.evidence_ref: item for item in manifest.external_evidence_bindings}
    if len(bindings) != len(manifest.external_evidence_bindings):
        raise ValueError("manifest_integrity_failed")
    expected: set[tuple[str, str, str, str]] = set()
    for case_node in case_nodes.values():
        expected.add(_semantic_edge_key(GraphEdgeType.DEPENDS_ON, root.node_id, case_node.node_id))
    seen_bindings: set[str] = set()
    for node in nodes:
        if node.node_type is not GraphNodeType.EVIDENCE_RECORD:
            continue
        evidence_ref = f"{node.object_id}@{node.object_version}"
        binding = bindings.get(evidence_ref)
        if (
            binding is None
            or
            node.record_mode is not GraphRecordMode.EXTERNAL_REF
            or node.source_graph_id is None
            or node.source_graph_version is None
            or node.properties_json is not None
            or node.content_hash != binding.evidence_content_hash
            or node.evidence_tier != binding.evidence_tier.value
            or node.lifecycle_state != binding.lifecycle_state.value
        ):
            raise ValueError("manifest_integrity_failed")
        key = (node.source_graph_id, node.source_graph_version)
        case_node = case_nodes.get(key)
        if (
            case_node is None
            or node_map.get(case_node.node_id) != case_node
            or binding.source_case_graph_ref
            != refs.get((node.source_graph_id, node.source_graph_version))
            or binding.product_case_ref
            != binding.source_case_graph_ref.product_case_ref
        ):
            raise ValueError("manifest_integrity_failed")
        seen_bindings.add(evidence_ref)
        expected.add(_semantic_edge_key(GraphEdgeType.APPLICABLE_TO, node.node_id, root.node_id))
        expected.add(
            _semantic_edge_key(
                GraphEdgeType.APPLICABLE_TO,
                node.node_id,
                case_node.node_id,
                {
                    "source_case_projection": True,
                    "external_binding_sha256": canonical_hash(
                        binding.model_dump(mode="json")
                    ),
                },
            )
        )
        profile = _node_for_ref(
            nodes,
            binding.sufficiency_profile_ref,
            {GraphNodeType.EVIDENCE_SUFFICIENCY_PROFILE},
        )
        family = _node_for_ref(
            nodes, binding.evidence_family_ref, {GraphNodeType.EVIDENCE_FAMILY}
        )
        claim = _node_for_ref(nodes, binding.comparison_claim_ref, {GraphNodeType.CLAIM})
        expected.add(_semantic_edge_key(GraphEdgeType.DEPENDS_ON, node.node_id, profile.node_id))
        expected.add(
            _semantic_edge_key(
                GraphEdgeType.BELONGS_TO_EVIDENCE_FAMILY, node.node_id, family.node_id
            )
        )
        if binding.lifecycle_state is EvidenceLifecycleState.ACTIVE:
            expected.add(
                _semantic_edge_key(
                    GraphEdgeType(binding.relation.value), node.node_id, claim.node_id
                )
            )
    if seen_bindings != set(bindings):
        raise ValueError("manifest_integrity_failed")

    for node in nodes:
        if node.node_type is not GraphNodeType.CLAIM or node.record_mode is not GraphRecordMode.OWNED:
            continue
        if node.properties_json is None:
            raise ValueError("manifest_integrity_failed")
        claim = ClaimSpec.model_validate_json(node.properties_json)
        spec = _node_for_ref(
            nodes, claim.reconciliation_spec_ref, {GraphNodeType.RECONCILIATION_SPEC}
        )
        expected.add(_semantic_edge_key(GraphEdgeType.DEPENDS_ON, node.node_id, spec.node_id))
        expected.add(_semantic_edge_key(GraphEdgeType.APPLICABLE_TO, node.node_id, root.node_id))
    evidence_nodes = {
        f"{item.object_id}@{item.object_version}": item.node_id
        for item in nodes
        if item.node_type is GraphNodeType.EVIDENCE_RECORD
    }
    for reconciliation in reconciliation_set.records:
        source = node_id(
            reconciliation.reconciliation_id,
            str(reconciliation.reconciliation_version),
            GraphNodeType.RECONCILIATION_RECORD,
        )
        for ref, allowed in [
            (reconciliation.claim_ref, {GraphNodeType.CLAIM}),
            (reconciliation.reconciliation_spec_ref, {GraphNodeType.RECONCILIATION_SPEC}),
            *((item, {GraphNodeType.EVIDENCE_SUFFICIENCY_PROFILE}) for item in reconciliation.sufficiency_profile_refs),
        ]:
            target = _node_for_ref(nodes, ref, allowed)
            expected.add(_semantic_edge_key(GraphEdgeType.DEPENDS_ON, source, target.node_id))
        for evidence_ref in reconciliation.included_evidence_refs:
            target = evidence_nodes.get(evidence_ref)
            if target is None:
                raise ValueError("manifest_integrity_failed")
            expected.add(_semantic_edge_key(GraphEdgeType.DEPENDS_ON, source, target))
    actual = {
        (item.edge_type.value, item.source_node_id, item.target_node_id, item.properties_json)
        for item in edges
    }
    if actual != expected:
        raise ValueError("manifest_integrity_failed")


def _semantic_edge_key(
    edge_type: GraphEdgeType,
    source: str,
    target: str,
    properties: dict[str, Any] | None = None,
) -> tuple[str, str, str, str]:
    return (
        edge_type.value,
        source,
        target,
        canonical_json_bytes(properties or {}).decode("utf-8"),
    )


def _node_for_ref(
    nodes: Sequence[GraphNodeRow],
    ref: VersionedObjectRef,
    allowed_types: set[GraphNodeType],
) -> GraphNodeRow:
    matches = [
        item
        for item in nodes
        if item.object_id == ref.object_id
        and item.object_version == ref.object_version
        and item.node_type in allowed_types
    ]
    if len(matches) != 1:
        raise ValueError("manifest_integrity_failed")
    return matches[0]


def _validate_case_semantic_edges(
    manifest: CaseEvidenceGraphManifest,
    nodes: Sequence[GraphNodeRow],
    edges: Sequence[GraphEdgeRow],
    record_set: EvidenceRecordSet,
    requirement_set: EvidenceRequirementSet,
    reconciliation_set: ReconciliationRecordSet,
) -> None:
    """Rebuild every Case edge from authoritative facts and registry projections."""

    root = _node_for_ref(nodes, manifest.product_case_ref, {GraphNodeType.PRODUCT_CASE})
    expected: set[tuple[str, str, str, str]] = set()
    records_by_ref = {item.ref: item for item in record_set.records}
    record_nodes = {
        item.ref: node_id(
            item.evidence_id,
            str(item.evidence_version),
            GraphNodeType.EVIDENCE_RECORD,
        )
        for item in record_set.records
    }
    by_id: dict[str, list[Any]] = {}
    for record in record_set.records:
        by_id.setdefault(record.evidence_id, []).append(record)
    effective: dict[str, EvidenceLifecycleState] = {}
    for versions in by_id.values():
        versions.sort(key=lambda item: item.evidence_version)
        for record in versions:
            effective[record.ref] = record.lifecycle_state
        for predecessor, successor in zip(versions, versions[1:], strict=False):
            effective[predecessor.ref] = (
                EvidenceLifecycleState.INVALIDATED
                if successor.lifecycle_state is EvidenceLifecycleState.INVALIDATED
                else EvidenceLifecycleState.SUPERSEDED
            )

    for record in record_set.records:
        source = record_nodes[record.ref]
        provenance_refs = (
            (record.measurement_result_ref, {GraphNodeType.MEASUREMENT_RESULT}),
            (
                record.sample_or_preparation_ref,
                {GraphNodeType.SAMPLE, GraphNodeType.PREPARATION},
            ),
            (record.tool_run_ref, {GraphNodeType.TOOL_RUN}),
            *(
                (item, {GraphNodeType.REFERENCE_SNAPSHOT})
                for item in record.reference_refs
            ),
            *((item, {GraphNodeType.PRIOR_SNAPSHOT}) for item in record.prior_refs),
            *((item, {GraphNodeType.ARTIFACT}) for item in record.artifact_refs),
        )
        for ref, allowed in provenance_refs:
            target = _node_for_ref(nodes, ref, allowed)
            expected.add(
                _semantic_edge_key(GraphEdgeType.DERIVED_FROM, source, target.node_id)
            )
        dependencies = [
            (
                record.measurement_spec_ref,
                {GraphNodeType.MEASUREMENT_SPEC},
            ),
            (
                record.sufficiency_profile_ref,
                {GraphNodeType.EVIDENCE_SUFFICIENCY_PROFILE},
            ),
        ]
        if record.score_contract_ref is not None:
            dependencies.append((record.score_contract_ref, {GraphNodeType.SCORE_CONTRACT}))
        for ref, allowed in dependencies:
            target = _node_for_ref(nodes, ref, allowed)
            expected.add(_semantic_edge_key(GraphEdgeType.DEPENDS_ON, source, target.node_id))
        expected.add(_semantic_edge_key(GraphEdgeType.APPLICABLE_TO, source, root.node_id))
        family = _node_for_ref(
            nodes, record.evidence_family_ref, {GraphNodeType.EVIDENCE_FAMILY}
        )
        expected.add(
            _semantic_edge_key(
                GraphEdgeType.BELONGS_TO_EVIDENCE_FAMILY, source, family.node_id
            )
        )
        claim = _node_for_ref(nodes, record.claim_ref, {GraphNodeType.CLAIM})
        if effective[record.ref] is EvidenceLifecycleState.ACTIVE:
            expected.add(
                _semantic_edge_key(GraphEdgeType(record.relation.value), source, claim.node_id)
            )
        if record.predecessor_ref is not None:
            predecessor = record_nodes.get(record.predecessor_ref)
            if predecessor is None or record.predecessor_ref not in records_by_ref:
                raise ValueError("manifest_integrity_failed")
            expected.add(
                _semantic_edge_key(
                    GraphEdgeType.INVALIDATES
                    if record.lifecycle_state is EvidenceLifecycleState.INVALIDATED
                    else GraphEdgeType.SUPERSEDES,
                    source,
                    predecessor,
                )
            )

    for node in nodes:
        if node.node_type is not GraphNodeType.CLAIM or node.record_mode is not GraphRecordMode.OWNED:
            continue
        if node.properties_json is None:
            raise ValueError("manifest_integrity_failed")
        claim = ClaimSpec.model_validate_json(node.properties_json)
        spec = _node_for_ref(
            nodes, claim.reconciliation_spec_ref, {GraphNodeType.RECONCILIATION_SPEC}
        )
        expected.add(_semantic_edge_key(GraphEdgeType.DEPENDS_ON, node.node_id, spec.node_id))
        expected.add(_semantic_edge_key(GraphEdgeType.APPLICABLE_TO, node.node_id, root.node_id))

    requirements_by_id: dict[str, list[Any]] = {}
    for requirement in requirement_set.requirements:
        requirements_by_id.setdefault(requirement.requirement_id, []).append(requirement)
        source = node_id(
            requirement.requirement_id,
            str(requirement.requirement_version),
            GraphNodeType.EVIDENCE_REQUIREMENT,
        )
        expected.add(_semantic_edge_key(GraphEdgeType.APPLICABLE_TO, source, root.node_id))
    for versions in requirements_by_id.values():
        latest = max(versions, key=lambda item: item.requirement_version)
        if latest.state is EvidenceRequirementState.OPEN:
            source = node_id(
                latest.requirement_id,
                str(latest.requirement_version),
                GraphNodeType.EVIDENCE_REQUIREMENT,
            )
            claim = _node_for_ref(nodes, latest.claim_ref, {GraphNodeType.CLAIM})
            expected.add(_semantic_edge_key(GraphEdgeType.MISSING_FOR, source, claim.node_id))

    for reconciliation in reconciliation_set.records:
        source = node_id(
            reconciliation.reconciliation_id,
            str(reconciliation.reconciliation_version),
            GraphNodeType.RECONCILIATION_RECORD,
        )
        refs = [
            (reconciliation.claim_ref, {GraphNodeType.CLAIM}),
            (
                reconciliation.reconciliation_spec_ref,
                {GraphNodeType.RECONCILIATION_SPEC},
            ),
            *(
                (item, {GraphNodeType.EVIDENCE_SUFFICIENCY_PROFILE})
                for item in reconciliation.sufficiency_profile_refs
            ),
        ]
        for ref, allowed in refs:
            target = _node_for_ref(nodes, ref, allowed)
            expected.add(_semantic_edge_key(GraphEdgeType.DEPENDS_ON, source, target.node_id))
        for evidence_ref in reconciliation.included_evidence_refs:
            target = record_nodes.get(evidence_ref)
            if target is None:
                raise ValueError("manifest_integrity_failed")
            expected.add(_semantic_edge_key(GraphEdgeType.DEPENDS_ON, source, target))

    actual = {
        (
            item.edge_type.value,
            item.source_node_id,
            item.target_node_id,
            item.properties_json,
        )
        for item in edges
    }
    if actual != expected:
        raise ValueError("manifest_integrity_failed")


def _validate_fact_projection(
    manifest: CaseEvidenceGraphManifest | ComparisonEvidenceGraphManifest,
    nodes: Sequence[GraphNodeRow],
    record_set: EvidenceRecordSet,
    requirement_set: EvidenceRequirementSet,
    reconciliation_set: ReconciliationRecordSet,
    edges: Sequence[GraphEdgeRow],
) -> None:
    """Bind canonical JSON facts to the owned nodes in their Parquet graph."""

    for fact_set in (record_set, requirement_set, reconciliation_set):
        if (
            fact_set.graph_id != manifest.graph_id
            or fact_set.graph_version != manifest.graph_version
        ):
            raise ValueError("manifest_integrity_failed")
    digest = manifest.source_input_hash[:16]
    if (
        record_set.record_set_id != f"evidence-record-set:{digest}"
        or requirement_set.requirement_set_id != f"evidence-requirement-set:{digest}"
        or reconciliation_set.reconciliation_set_id
        != f"reconciliation-record-set:{digest}"
    ):
        raise ValueError("manifest_integrity_failed")
    node_map = {item.node_id: item for item in nodes}
    case_root = (
        manifest.product_case_ref
        if isinstance(manifest, CaseEvidenceGraphManifest)
        else None
    )
    if case_root is None and (record_set.records or requirement_set.requirements):
        raise ValueError("manifest_integrity_failed")

    expected_by_type: dict[GraphNodeType, set[str]] = {
        GraphNodeType.EVIDENCE_RECORD: set(),
        GraphNodeType.EVIDENCE_REQUIREMENT: set(),
        GraphNodeType.RECONCILIATION_RECORD: set(),
    }

    def require_owned_fact(
        *,
        object_id: str,
        object_version: str,
        node_type: GraphNodeType,
        content_hash: str,
        payload: dict[str, Any],
        require_properties: bool = True,
    ) -> None:
        identifier = node_id(object_id, object_version, node_type)
        node = node_map.get(identifier)
        if (
            node is None
            or node.record_mode is not GraphRecordMode.OWNED
            or node.object_id != object_id
            or node.object_version != object_version
            or node.content_hash != content_hash
            or (
                require_properties
                and (
                    node.properties_json is None
                    or json.loads(node.properties_json) != payload
                )
            )
        ):
            raise ValueError("manifest_integrity_failed")
        expected_by_type[node_type].add(identifier)

    for record in record_set.records:
        rebuilt_key = evidence_record_logical_key(record)
        expected_id = evidence_identity(rebuilt_key)
        if (
            case_root is None
            or record.product_case_ref != case_root
            or record.logical_key != rebuilt_key
            or record.evidence_id != expected_id
        ):
            raise ValueError("manifest_integrity_failed")
        claim_node = node_map.get(
            node_id(
                record.claim_ref.object_id,
                record.claim_ref.object_version,
                GraphNodeType.CLAIM,
            )
        )
        if (
            claim_node is None
            or claim_node.record_mode is not GraphRecordMode.OWNED
            or claim_node.properties_json is None
        ):
            raise ValueError("manifest_integrity_failed")
        claim = ClaimSpec.model_validate_json(claim_node.properties_json)
        if (
            claim.ref != record.claim_ref.ref
            or claim.domain_id is not record.domain_id
            or claim.biological_context_ref
            != VersionedObjectRef(
                object_id=record.biological_context.context_id,
                object_version=record.biological_context.context_version,
            )
            or record.relation not in claim.allowed_relations
        ):
            raise ValueError("manifest_integrity_failed")
        require_owned_fact(
            object_id=record.evidence_id,
            object_version=str(record.evidence_version),
            node_type=GraphNodeType.EVIDENCE_RECORD,
            content_hash=record.content_hash,
            payload=record.model_dump(mode="json"),
            require_properties=isinstance(manifest, CaseEvidenceGraphManifest),
        )
    for requirement in requirement_set.requirements:
        if (
            case_root is None
            or requirement.product_case_ref != case_root
            or requirement.requirement_id
            != requirement_identity(
                manifest.graph_id,
                requirement.claim_ref,
                requirement.requirement_key,
            )
        ):
            raise ValueError("manifest_integrity_failed")
        require_owned_fact(
            object_id=requirement.requirement_id,
            object_version=str(requirement.requirement_version),
            node_type=GraphNodeType.EVIDENCE_REQUIREMENT,
            content_hash=requirement.content_hash,
            payload=requirement.model_dump(mode="json"),
        )
    for reconciliation in reconciliation_set.records:
        if (
            reconciliation.graph_id != manifest.graph_id
            or reconciliation.graph_version != manifest.graph_version
            or reconciliation.reconciliation_version != manifest.graph_version
            or reconciliation.reconciliation_id
            != reconciliation_identity(
                manifest.graph_id,
                reconciliation.claim_ref,
                reconciliation.reconciliation_spec_ref,
            )
        ):
            raise ValueError("manifest_integrity_failed")
        require_owned_fact(
            object_id=reconciliation.reconciliation_id,
            object_version=str(reconciliation.reconciliation_version),
            node_type=GraphNodeType.RECONCILIATION_RECORD,
            content_hash=reconciliation.content_hash,
            payload=reconciliation.model_dump(mode="json"),
        )
    records_by_id: dict[str, list[Any]] = {}
    for record in record_set.records:
        records_by_id.setdefault(record.evidence_id, []).append(record)
    for versions in records_by_id.values():
        versions.sort(key=lambda item: item.evidence_version)
        if [item.evidence_version for item in versions] != list(
            range(1, len(versions) + 1)
        ) or len({item.logical_key for item in versions}) != 1:
            raise ValueError("manifest_integrity_failed")
        for index, record in enumerate(versions):
            expected_predecessor = None if index == 0 else versions[index - 1].ref
            expected_action = RevisionAction.CREATE if index == 0 else None
            if record.predecessor_ref != expected_predecessor or (
                expected_action is not None and record.revision_action is not expected_action
            ):
                raise ValueError("manifest_integrity_failed")
            expected_lifecycle = record.lifecycle_state
            if index + 1 < len(versions):
                successor = versions[index + 1]
                expected_lifecycle = (
                    EvidenceLifecycleState.INVALIDATED
                    if successor.lifecycle_state is EvidenceLifecycleState.INVALIDATED
                    else EvidenceLifecycleState.SUPERSEDED
                )
            node = node_map[node_id(
                record.evidence_id,
                str(record.evidence_version),
                GraphNodeType.EVIDENCE_RECORD,
            )]
            if node.evidence_tier != record.evidence_tier.value:
                raise ValueError("manifest_integrity_failed")
            if node.lifecycle_state != expected_lifecycle.value:
                raise ValueError("manifest_integrity_failed")

    requirements_by_id: dict[str, list[Any]] = {}
    for requirement in requirement_set.requirements:
        requirements_by_id.setdefault(requirement.requirement_id, []).append(requirement)
    for versions in requirements_by_id.values():
        versions.sort(key=lambda item: item.requirement_version)
        if [item.requirement_version for item in versions] != list(
            range(1, len(versions) + 1)
        ):
            raise ValueError("manifest_integrity_failed")
        for index, requirement in enumerate(versions):
            expected_predecessor = None if index == 0 else versions[index - 1].ref
            if requirement.supersedes_requirement_ref != expected_predecessor:
                raise ValueError("manifest_integrity_failed")
            node = node_map[node_id(
                requirement.requirement_id,
                str(requirement.requirement_version),
                GraphNodeType.EVIDENCE_REQUIREMENT,
            )]
            expected_lifecycle = (
                requirement.state.value
                if index + 1 == len(versions)
                else EvidenceLifecycleState.SUPERSEDED.value
            )
            if node.lifecycle_state != expected_lifecycle:
                raise ValueError("manifest_integrity_failed")
    latest_records = {
        versions[-1].evidence_id: versions[-1] for versions in records_by_id.values()
    }
    records_by_ref = {item.ref: item for item in record_set.records}
    for versions in requirements_by_id.values():
        latest_requirement = versions[-1]
        if latest_requirement.state is not EvidenceRequirementState.SATISFIED:
            continue
        for evidence_ref in latest_requirement.satisfying_evidence_refs:
            record = records_by_ref.get(evidence_ref)
            if (
                record is None
                or latest_records.get(record.evidence_id) != record
                or record.lifecycle_state is not EvidenceLifecycleState.ACTIVE
                or record.evidence_tier is not EvidenceTier.FORMAL
                or record.applicability is not EvidenceApplicability.APPLICABLE
                or record.claim_ref != latest_requirement.claim_ref
                or record.product_case_ref != latest_requirement.product_case_ref
            ):
                raise ValueError("manifest_integrity_failed")
            family_node = _node_for_ref(
                nodes, record.evidence_family_ref, {GraphNodeType.EVIDENCE_FAMILY}
            )
            if family_node.properties_json is None:
                raise ValueError("manifest_integrity_failed")
            family = EvidenceFamilySpec.model_validate_json(family_node.properties_json)
            if (
                family.status is not EvidenceFamilyStatus.REVIEWED
                or family.channel_role != latest_requirement.channel_role
            ):
                raise ValueError("manifest_integrity_failed")
    for node_type, expected_ids in expected_by_type.items():
        actual_ids = {
            item.node_id
            for item in nodes
            if item.node_type is node_type and item.record_mode is GraphRecordMode.OWNED
        }
        if actual_ids != expected_ids:
            raise ValueError("manifest_integrity_failed")
    if isinstance(manifest, CaseEvidenceGraphManifest):
        _validate_case_semantic_edges(
            manifest,
            nodes,
            edges,
            record_set,
            requirement_set,
            reconciliation_set,
        )


class EvidenceGraphQueries:
    def __init__(
        self,
        *,
        manifest: CaseEvidenceGraphManifest | ComparisonEvidenceGraphManifest,
        record_set: EvidenceRecordSet,
        nodes: list[GraphNodeRow],
        edges: list[GraphEdgeRow],
        graph: nx.MultiDiGraph,
    ) -> None:
        self._manifest = manifest
        self._record_set = record_set
        self._nodes = {item.node_id: item for item in nodes}
        self._edges = {item.edge_id: item for item in edges}
        self._graph = graph

    @classmethod
    def open(cls, manifest_path: Path) -> "EvidenceGraphQueries":
        """Open an untrusted graph without exposing nested validation details."""

        try:
            return cls._open_untrusted(manifest_path)
        except Exception:
            raise ValueError("manifest_integrity_failed") from None

    @classmethod
    def _open_untrusted(cls, manifest_path: Path) -> "EvidenceGraphQueries":
        if manifest_path.is_symlink() or not manifest_path.is_file():
            raise ValueError("manifest_integrity_failed")
        try:
            manifest_path = manifest_path.resolve(strict=True)
            payload = json.loads(_read_regular_file(manifest_path).decode("utf-8"))
            if payload.get("graph_kind") == GraphKind.CASE.value:
                manifest = CaseEvidenceGraphManifest.model_validate(payload)
                root_ref = manifest.product_case_ref
                root_type = GraphNodeType.PRODUCT_CASE
            elif payload.get("graph_kind") == GraphKind.COMPARISON.value:
                manifest = ComparisonEvidenceGraphManifest.model_validate(payload)
                root_ref = manifest.comparison_ref
                root_type = GraphNodeType.COMPARISON_RECORD
            else:
                raise ValueError("unknown graph kind")
            if manifest.graph_id != graph_identity_for_ref(manifest.graph_kind, root_ref):
                raise ValueError("graph identity does not match root")
            if manifest.base_graph_ref is None:
                if manifest.graph_version != 1:
                    raise ValueError("initial graph version must be one")
            elif (
                manifest.base_graph_ref.graph_id != manifest.graph_id
                or manifest.graph_version != manifest.base_graph_ref.graph_version + 1
            ):
                raise ValueError("append graph version mismatch")
        except Exception as exc:
            raise ValueError("manifest_integrity_failed") from exc
        root = manifest_path.parent
        artifacts = (
            manifest.evidence_records,
            manifest.evidence_requirements,
            manifest.reconciliation_records,
            manifest.graph_nodes,
            manifest.graph_edges,
        )
        if len({item.filename for item in artifacts}) != len(artifacts):
            raise ValueError("manifest_integrity_failed")
        artifact_payloads: dict[str, bytes] = {}
        for artifact in artifacts:
            if not _safe_artifact_filename(artifact.filename):
                raise ValueError("manifest_integrity_failed")
            artifact_path = root / artifact.filename
            try:
                raw = _read_regular_file(artifact_path)
            except OSError as exc:
                raise ValueError("manifest_integrity_failed") from exc
            if hashlib.sha256(raw).hexdigest() != artifact.sha256:
                raise ValueError("manifest_integrity_failed")
            artifact_payloads[artifact.filename] = raw
        try:
            nodes, edges = read_parquet_bytes(
                artifact_payloads[manifest.graph_nodes.filename],
                artifact_payloads[manifest.graph_edges.filename],
            )
            root_node = next(
                item.node_id
                for item in nodes
                if item.node_type is root_type
                and item.object_id == root_ref.object_id
                and item.object_version == root_ref.object_version
            )
            graph = validate_graph_rows(
                nodes,
                edges,
                root_id=root_node,
                root_type=root_type,
                expected_graph_id=manifest.graph_id,
                expected_graph_version=manifest.graph_version,
            )
        except Exception as exc:
            raise ValueError("manifest_integrity_failed") from exc
        if (
            len(nodes) != manifest.node_count
            or len(edges) != manifest.edge_count
            or manifest.graph_nodes.row_count != len(nodes)
            or manifest.graph_edges.row_count != len(edges)
            or manifest.object_counts != object_counts(nodes)
        ):
            raise ValueError("manifest_integrity_failed")
        try:
            record_set = EvidenceRecordSet.model_validate_json(
                artifact_payloads[manifest.evidence_records.filename]
            )
            requirement_set = EvidenceRequirementSet.model_validate_json(
                artifact_payloads[manifest.evidence_requirements.filename]
            )
            reconciliation_set = ReconciliationRecordSet.model_validate_json(
                artifact_payloads[manifest.reconciliation_records.filename]
            )
            _validate_fact_projection(
                manifest,
                nodes,
                record_set,
                requirement_set,
                reconciliation_set,
                edges,
            )
        except Exception as exc:
            raise ValueError("manifest_integrity_failed") from exc
        if isinstance(manifest, ComparisonEvidenceGraphManifest):
            try:
                _validate_comparison_projection(
                    manifest, nodes, edges, reconciliation_set
                )
            except Exception:
                # This is a public, untrusted-artifact boundary. Nested model
                # validation details can contain attacker-controlled values.
                raise ValueError("manifest_integrity_failed") from None
        return cls(
            manifest=manifest,
            record_set=record_set,
            nodes=nodes,
            edges=edges,
            graph=graph,
        )

    @property
    def evidence_record_set(self) -> EvidenceRecordSet:
        """Return the record projection validated with the graph manifest."""

        return self._record_set

    def get_claim_evidence(
        self,
        *,
        claim_id: str,
        claim_version: str | None = None,
        evidence_tiers: tuple[EvidenceTier, ...] = (EvidenceTier.FORMAL,),
        include_inactive: bool = False,
        limit: int = 100,
    ) -> EvidenceGraphQueryResult:
        invalid = (
            self._validate_limit(limit)
            or self._validate_text(claim_id)
            or not self._enum_tuple(evidence_tiers, EvidenceTier)
            or not isinstance(include_inactive, bool)
        )
        if claim_version is not None:
            invalid = invalid or self._validate_text(claim_version)
        claim = None if invalid else self._resolve_claim(claim_id, claim_version)
        if invalid or claim is None:
            return self._empty("get_claim_evidence", "query_parameter_invalid" if invalid else "not_found")
        evidence_ids: set[str] = set()
        edge_ids: set[str] = set()
        for source, _, key, data in self._graph.in_edges(claim.node_id, keys=True, data=True):
            if data["edge_type"] not in {"supports", "contradicts"}:
                continue
            evidence = self._nodes[source]
            if EvidenceTier(evidence.evidence_tier) not in evidence_tiers:
                continue
            if not include_inactive and evidence.lifecycle_state != EvidenceLifecycleState.ACTIVE.value:
                continue
            evidence_ids.add(source)
            edge_ids.add(key)
        selected = sorted(evidence_ids)[:limit]
        selected_set = set(selected) | {claim.node_id}
        selected_edges = [key for key in edge_ids if self._edges[key].source_node_id in selected_set]
        return self._result(
            "get_claim_evidence",
            selected_set,
            selected_edges,
            truncated=len(evidence_ids) > limit,
            omitted_nodes=max(0, len(evidence_ids) - limit),
            omitted_edges=max(0, len(evidence_ids) - limit),
        )

    def trace_evidence_provenance(
        self,
        *,
        evidence_ref: str,
        max_depth: int = 4,
        max_nodes: int = 200,
    ) -> EvidenceGraphQueryResult:
        invalid = self._validate_depth_nodes(max_depth, max_nodes) or self._validate_text(
            evidence_ref
        )
        evidence = None if invalid else self._resolve_evidence(evidence_ref)
        if invalid or evidence is None:
            return self._empty(
                "trace_evidence_provenance", "query_parameter_invalid" if invalid else "not_found"
            )
        if evidence.record_mode is GraphRecordMode.EXTERNAL_REF:
            return self._result(
                "trace_evidence_provenance",
                {evidence.node_id},
                [],
                reason_codes=["source_case_graph_required"],
            )
        allowed = {
            GraphEdgeType.DERIVED_FROM.value,
            GraphEdgeType.DEPENDS_ON.value,
            GraphEdgeType.BELONGS_TO_EVIDENCE_FAMILY.value,
        }
        nodes, edges, omitted_nodes, omitted_edges = self._bounded_walk(
            starts={evidence.node_id},
            max_depth=max_depth,
            max_nodes=max_nodes,
            direction="out",
            allowed_edge_types=allowed,
        )
        truncated = bool(omitted_nodes or omitted_edges)
        return self._result(
            "trace_evidence_provenance",
            nodes,
            edges,
            truncated=truncated,
            omitted_nodes=omitted_nodes,
            omitted_edges=omitted_edges,
            reason_codes=["query_result_truncated"] if truncated else [],
        )

    def get_conflicting_evidence(
        self,
        *,
        claim_id: str,
        claim_version: str | None = None,
        reconciliation_version: int | None = None,
        limit: int = 100,
    ) -> EvidenceGraphQueryResult:
        invalid = self._validate_limit(limit) or self._validate_text(claim_id)
        if claim_version is not None:
            invalid = invalid or self._validate_text(claim_version)
        if reconciliation_version is not None and (
            isinstance(reconciliation_version, bool)
            or not isinstance(reconciliation_version, int)
            or reconciliation_version < 1
        ):
            invalid = True
        claim = None if invalid else self._resolve_claim(claim_id, claim_version)
        if invalid or claim is None:
            return self._empty(
                "get_conflicting_evidence", "query_parameter_invalid" if invalid else "not_found"
            )
        by_relation: dict[str, list[tuple[str, str]]] = {"supports": [], "contradicts": []}
        for source, _, key, data in self._graph.in_edges(claim.node_id, keys=True, data=True):
            if data["edge_type"] in by_relation:
                by_relation[data["edge_type"]].append((source, key))
        if not all(by_relation.values()):
            return self._result("get_conflicting_evidence", {claim.node_id}, [])
        pairs = sorted([*by_relation["supports"], *by_relation["contradicts"]])
        selected = pairs[:limit]
        node_ids = {claim.node_id, *(item[0] for item in selected)}
        edge_ids = [item[1] for item in selected]
        reasons = self._reconciliation_reasons(claim.node_id, reconciliation_version)
        return self._result(
            "get_conflicting_evidence",
            node_ids,
            edge_ids,
            truncated=len(pairs) > limit,
            omitted_nodes=max(0, len(pairs) - limit),
            omitted_edges=max(0, len(pairs) - limit),
            reason_codes=reasons + (["query_result_truncated"] if len(pairs) > limit else []),
        )

    def get_missing_requirements(
        self,
        *,
        claim_id: str | None = None,
        claim_version: str | None = None,
        product_case_id: str | None = None,
        state: EvidenceRequirementState = EvidenceRequirementState.OPEN,
        limit: int = 100,
    ) -> EvidenceGraphQueryResult:
        exactly_one = (claim_id is not None) ^ (product_case_id is not None)
        invalid = (
            not exactly_one
            or self._validate_limit(limit)
            or not isinstance(state, EvidenceRequirementState)
        )
        if claim_version is not None and claim_id is None:
            invalid = True
        for value in (claim_id, claim_version, product_case_id):
            if value is not None:
                invalid = invalid or self._validate_text(value)
        if invalid:
            return self._empty("get_missing_requirements", "query_parameter_invalid")
        latest: dict[str, GraphNodeRow] = {}
        for node in self._nodes.values():
            if node.node_type is not GraphNodeType.EVIDENCE_REQUIREMENT:
                continue
            previous = latest.get(node.object_id)
            try:
                version = int(node.object_version)
                previous_version = int(previous.object_version) if previous is not None else 0
            except (TypeError, ValueError):
                return self._empty("get_missing_requirements", "manifest_integrity_failed")
            if previous is None or version > previous_version:
                latest[node.object_id] = node
        matching: list[GraphNodeRow] = []
        for node in latest.values():
            properties = self._properties(node)
            if properties.get("state") != state.value:
                continue
            if claim_id is not None:
                claim_ref = properties.get("claim_ref", {})
                if claim_ref.get("object_id") != claim_id:
                    continue
                if claim_version is not None and claim_ref.get("object_version") != claim_version:
                    continue
            if product_case_id is not None:
                if properties.get("product_case_ref", {}).get("object_id") != product_case_id:
                    continue
            matching.append(node)
        selected = sorted(matching, key=lambda item: item.node_id)[:limit]
        node_ids = {item.node_id for item in selected}
        edge_ids = [
            edge.edge_id
            for edge in self._edges.values()
            if edge.source_node_id in node_ids
            and edge.edge_type in {GraphEdgeType.MISSING_FOR, GraphEdgeType.APPLICABLE_TO}
        ]
        node_ids.update(self._edges[item].target_node_id for item in edge_ids)
        return self._result(
            "get_missing_requirements",
            node_ids,
            edge_ids,
            truncated=len(matching) > limit,
            omitted_nodes=max(0, len(matching) - limit),
        )

    def get_evidence_family_members(
        self,
        *,
        evidence_family_id: str,
        include_inactive: bool = False,
        limit: int = 100,
    ) -> EvidenceGraphQueryResult:
        invalid = (
            self._validate_limit(limit)
            or self._validate_text(evidence_family_id)
            or not isinstance(include_inactive, bool)
        )
        families = [
            item
            for item in self._nodes.values()
            if item.node_type is GraphNodeType.EVIDENCE_FAMILY
            and item.object_id == evidence_family_id
        ]
        if invalid or len(families) != 1:
            return self._empty(
                "get_evidence_family_members",
                "query_parameter_invalid" if invalid else "not_found",
            )
        family = families[0]
        members: list[tuple[str, str]] = []
        for source, _, key, data in self._graph.in_edges(family.node_id, keys=True, data=True):
            if data["edge_type"] != GraphEdgeType.BELONGS_TO_EVIDENCE_FAMILY.value:
                continue
            node = self._nodes[source]
            if not include_inactive and node.lifecycle_state != EvidenceLifecycleState.ACTIVE.value:
                continue
            members.append((source, key))
        selected = sorted(members)[:limit]
        return self._result(
            "get_evidence_family_members",
            {family.node_id, *(item[0] for item in selected)},
            [item[1] for item in selected],
            truncated=len(members) > limit,
            omitted_nodes=max(0, len(members) - limit),
            omitted_edges=max(0, len(members) - limit),
        )

    def get_case_evidence_subgraph(
        self,
        *,
        product_case_id: str,
        domain_ids: tuple[P0DomainId, ...] = (),
        evidence_tiers: tuple[EvidenceTier, ...] = (
            EvidenceTier.FORMAL,
            EvidenceTier.SHADOW,
        ),
        max_depth: int = 4,
        max_nodes: int = 300,
    ) -> EvidenceGraphQueryResult:
        invalid = (
            self._validate_depth_nodes(max_depth, max_nodes)
            or self._validate_text(product_case_id)
            or not self._enum_tuple(domain_ids, P0DomainId)
            or not self._enum_tuple(evidence_tiers, EvidenceTier)
        )
        if invalid:
            return self._empty("get_case_evidence_subgraph", "query_parameter_invalid")
        if self._manifest.graph_kind is not GraphKind.CASE:
            return self._empty("get_case_evidence_subgraph", "graph_kind_mismatch")
        roots = [
            item
            for item in self._nodes.values()
            if item.node_type is GraphNodeType.PRODUCT_CASE and item.object_id == product_case_id
        ]
        if invalid or len(roots) != 1:
            return self._empty(
                "get_case_evidence_subgraph", "query_parameter_invalid" if invalid else "not_found"
            )
        nodes, edges, omitted_nodes, omitted_edges = self._bounded_walk(
            starts={roots[0].node_id},
            max_depth=max_depth,
            max_nodes=max_nodes,
            direction="both",
        )
        allowed_domains = {item.value for item in domain_ids}
        allowed_tiers = {item.value for item in evidence_tiers}
        excluded_evidence = {
            node_id
            for node_id in nodes
            if self._nodes[node_id].node_type is GraphNodeType.EVIDENCE_RECORD
            and (
                self._nodes[node_id].evidence_tier not in allowed_tiers
                or (
                    allowed_domains
                    and self._properties(self._nodes[node_id]).get("domain_id") not in allowed_domains
                )
            )
        }
        nodes -= excluded_evidence
        edges = {
            edge_id
            for edge_id in edges
            if self._edges[edge_id].source_node_id in nodes
            and self._edges[edge_id].target_node_id in nodes
        }
        truncated = bool(omitted_nodes or omitted_edges)
        return self._result(
            "get_case_evidence_subgraph",
            nodes,
            edges,
            truncated=truncated,
            omitted_nodes=omitted_nodes,
            omitted_edges=omitted_edges,
            reason_codes=["query_result_truncated"] if truncated else [],
        )

    def compare_evidence_paths(
        self,
        *,
        comparison_id: str,
        claim_id: str | None = None,
        claim_version: str | None = None,
        domain_id: P0DomainId | None = None,
        max_depth: int = 4,
        max_nodes: int = 300,
    ) -> EvidenceGraphQueryResult:
        exactly_one = (claim_id is not None) ^ (domain_id is not None)
        invalid = (
            not exactly_one
            or self._validate_depth_nodes(max_depth, max_nodes)
            or (domain_id is not None and not isinstance(domain_id, P0DomainId))
        )
        invalid = invalid or self._validate_text(comparison_id)
        if claim_version is not None and claim_id is None:
            invalid = True
        if claim_id is not None:
            invalid = invalid or self._validate_text(claim_id)
        if claim_version is not None:
            invalid = invalid or self._validate_text(claim_version)
        if invalid:
            return self._empty("compare_evidence_paths", "query_parameter_invalid")
        if self._manifest.graph_kind is not GraphKind.COMPARISON:
            return self._empty("compare_evidence_paths", "graph_kind_mismatch")
        roots = [
            item
            for item in self._nodes.values()
            if item.node_type is GraphNodeType.COMPARISON_RECORD
            and item.object_id == comparison_id
        ]
        if invalid or len(roots) != 1:
            return self._empty(
                "compare_evidence_paths", "query_parameter_invalid" if invalid else "not_found"
            )
        claim_nodes = [
            item
            for item in self._nodes.values()
            if item.node_type is GraphNodeType.CLAIM
            and (
                (claim_id is not None and item.object_id == claim_id)
                or (
                    domain_id is not None
                    and self._properties(item).get("domain_id") == domain_id.value
                )
            )
            and (claim_version is None or item.object_version == claim_version)
        ]
        if not claim_nodes:
            return self._empty("compare_evidence_paths", "not_found")
        nodes, edges, omitted_nodes, omitted_edges = self._bounded_walk(
            starts={roots[0].node_id, *(item.node_id for item in claim_nodes)},
            max_depth=max_depth,
            max_nodes=max_nodes,
            direction="both",
        )
        external_nodes = {
            node_id
            for node_id in nodes
            if self._nodes[node_id].record_mode is GraphRecordMode.EXTERNAL_REF
        }
        reasons = ["source_case_graph_required"] if external_nodes else []
        truncated = bool(omitted_nodes or omitted_edges)
        return self._result(
            "compare_evidence_paths",
            nodes,
            edges,
            truncated=truncated,
            omitted_nodes=omitted_nodes,
            omitted_edges=omitted_edges,
            reason_codes=reasons + (["query_result_truncated"] if truncated else []),
        )

    def _resolve_claim(self, claim_id: str, version: str | None) -> GraphNodeRow | None:
        matches = [
            item
            for item in self._nodes.values()
            if item.node_type is GraphNodeType.CLAIM
            and item.object_id == claim_id
            and (version is None or item.object_version == version)
        ]
        return matches[0] if len(matches) == 1 else None

    def _resolve_evidence(self, evidence_ref: str) -> GraphNodeRow | None:
        if "@" not in evidence_ref:
            return None
        object_id, version = evidence_ref.rsplit("@", 1)
        matches = [
            item
            for item in self._nodes.values()
            if item.node_type is GraphNodeType.EVIDENCE_RECORD
            and item.object_id == object_id
            and item.object_version == version
        ]
        return matches[0] if len(matches) == 1 else None

    def _bounded_walk(
        self,
        *,
        starts: set[str],
        max_depth: int,
        max_nodes: int,
        direction: str,
        allowed_edge_types: set[str] | None = None,
    ) -> tuple[set[str], set[str], int, int]:
        ordered_starts = sorted(starts)
        seen = set(ordered_starts[:max_nodes])
        omitted_node_ids = set(ordered_starts[max_nodes:])
        edge_ids: set[str] = set()
        omitted_edge_ids: set[str] = set()
        frontier = sorted(seen)
        for _ in range(max_depth):
            next_frontier: list[str] = []
            for node_id in frontier:
                candidates = []
                if direction in {"out", "both"}:
                    candidates.extend(self._graph.out_edges(node_id, keys=True, data=True))
                if direction in {"in", "both"}:
                    candidates.extend(self._graph.in_edges(node_id, keys=True, data=True))
                for source, target, key, data in sorted(candidates, key=lambda item: item[2]):
                    if allowed_edge_types is not None and data["edge_type"] not in allowed_edge_types:
                        continue
                    neighbor = target if source == node_id else source
                    if len(seen) >= max_nodes and neighbor not in seen:
                        omitted_node_ids.add(neighbor)
                        omitted_edge_ids.add(key)
                        continue
                    edge_ids.add(key)
                    if neighbor not in seen:
                        seen.add(neighbor)
                        next_frontier.append(neighbor)
            if not next_frontier:
                frontier = []
                break
            frontier = sorted(set(next_frontier))
        if frontier:
            for node_id in frontier:
                candidates = []
                if direction in {"out", "both"}:
                    candidates.extend(self._graph.out_edges(node_id, keys=True, data=True))
                if direction in {"in", "both"}:
                    candidates.extend(self._graph.in_edges(node_id, keys=True, data=True))
                for source, target, key, data in sorted(
                    candidates, key=lambda item: item[2]
                ):
                    if allowed_edge_types is not None and data["edge_type"] not in allowed_edge_types:
                        continue
                    if key in edge_ids:
                        continue
                    omitted_edge_ids.add(key)
                    neighbor = target if source == node_id else source
                    if neighbor not in seen:
                        omitted_node_ids.add(neighbor)
        return seen, edge_ids, len(omitted_node_ids), len(omitted_edge_ids)

    def _reconciliation_reasons(
        self, claim_node_id: str, reconciliation_version: int | None
    ) -> list[str]:
        reasons: list[str] = []
        for source, _, _, data in self._graph.in_edges(claim_node_id, keys=True, data=True):
            node = self._nodes[source]
            if node.node_type is not GraphNodeType.RECONCILIATION_RECORD:
                continue
            if reconciliation_version is not None and node.object_version != str(
                reconciliation_version
            ):
                continue
            reasons.extend(self._properties(node).get("reason_codes", []))
        return list(dict.fromkeys(reasons))

    def _result(
        self,
        query_name: str,
        node_ids: Iterable[str],
        edge_ids: Iterable[str],
        *,
        truncated: bool = False,
        omitted_nodes: int = 0,
        omitted_edges: int = 0,
        reason_codes: list[str] | None = None,
    ) -> EvidenceGraphQueryResult:
        nodes = [self._node_payload(self._nodes[item]) for item in sorted(set(node_ids))]
        edges = [
            self._edges[item].model_dump(mode="json") for item in sorted(set(edge_ids))
        ]
        return EvidenceGraphQueryResult(
            query_name=query_name,
            graph_id=self._manifest.graph_id,
            graph_version=self._manifest.graph_version,
            nodes=nodes,
            edges=edges,
            returned_node_count=len(nodes),
            returned_edge_count=len(edges),
            truncated=truncated,
            omitted_node_count=omitted_nodes,
            omitted_edge_count=omitted_edges,
            reason_codes=list(dict.fromkeys(reason_codes or [])),
        )

    def _empty(self, query_name: str, reason_code: str) -> EvidenceGraphQueryResult:
        return self._result(query_name, [], [], reason_codes=[reason_code])

    @staticmethod
    def _validate_text(value: str) -> bool:
        return not isinstance(value, str) or not value or bool(_DANGEROUS_PARAMETER.search(value))

    @staticmethod
    def _validate_limit(limit: int) -> bool:
        return isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200

    @staticmethod
    def _validate_depth_nodes(max_depth: int, max_nodes: int) -> bool:
        return (
            isinstance(max_depth, bool)
            or isinstance(max_nodes, bool)
            or not isinstance(max_depth, int)
            or not isinstance(max_nodes, int)
            or not 1 <= max_depth <= 6
            or not 1 <= max_nodes <= 500
        )

    @staticmethod
    def _enum_tuple(value: object, enum_type: type[Any]) -> bool:
        return (
            isinstance(value, tuple)
            and all(isinstance(item, enum_type) for item in value)
            and len(value) == len(set(value))
        )

    @staticmethod
    def _properties(node: GraphNodeRow) -> dict[str, Any]:
        if node.properties_json is None:
            return {}
        payload = json.loads(node.properties_json)
        return payload if isinstance(payload, dict) else {}

    def _node_payload(self, node: GraphNodeRow) -> dict[str, Any]:
        payload = node.model_dump(mode="json")
        payload["properties"] = self._properties(node)
        payload.pop("properties_json", None)
        return payload
