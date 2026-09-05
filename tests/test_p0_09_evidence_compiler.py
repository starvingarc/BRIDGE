from __future__ import annotations

import hashlib
import importlib
import inspect
import json
import re
import traceback
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
import pytest

from bridge.tool_packages.p0_09_evidence_compiler.adapter import (
    RESULT_SCHEMA_REF,
    _validate_source_record_set,
    adapter,
)
from bridge.tool_packages.p0_08_evidence_sufficiency.models import (
    EvidenceSufficiencyProfile,
    P0DomainId,
    EvidenceSufficiencyProfileV2,
    EvidenceSufficiencyRunResultV2,
)
from bridge.tool_packages.p0_09_evidence_compiler.models import (
    PUBLIC_SCHEMA_MODELS,
    publication_ref,
    BaseGraphRef,
    ClaimRequirementSpec,
    EvidenceCandidate,
    EvidenceCompilerRunResult,
    EvidenceInterval,
    EvidenceRecordSet,
    EvidenceRequirementSet,
    ReconciliationRecordSet,
    EvidenceCompilationBundle,
    EvidenceRecord,
    EvidenceRequirement,
    CaseEvidenceGraphManifest,
    ComparisonEvidenceGraphManifest,
    MissingEvidenceObservation,
    EvidenceFamilyRegistry,
    GraphArtifactRef,
    ReconciliationSpec,
    ReconciliationRecord,
    ClaimRegistry,
    ReconciliationSpecRegistry,
)
from bridge.tool_packages.p0_09_evidence_compiler.compiler import (
    canonical_json_bytes,
    evidence_identity,
    evidence_record_logical_key,
    evidence_record_content_hash,
)
from bridge.tool_packages.p0_09_evidence_compiler.graph import (
    build_graph_rows,
    node_id,
    object_counts,
    read_parquet_rows,
    write_parquet,
)
from bridge.tool_packages.p0_09_evidence_compiler.reconciler import (
    ReconciliationEvidence,
    _resolve_channel,
)
from bridge.tool_packages.p0_09_evidence_compiler.models import (
    EvidenceApplicability,
    EvidenceLifecycleState,
    EvidenceRelation,
    EvidenceTier,
    EvidenceRequirementState,
    GraphEdgeRow,
    GraphEdgeType,
    GraphNodeRow,
    GraphNodeType,
    GraphRecordMode,
)
from bridge.tool_packages.p0_09_evidence_compiler.visualization import (
    prepare_evidence_compiler_visualizations,
    _short_ref,
)
from bridge.tool_packages.p0_09_evidence_compiler.visualization_data import (
    PUBLIC_VISUALIZATION_SCHEMA_MODELS,
    ClaimInterpretationRecord,
    CompilationExclusionRecord,
    EvidenceFamilyRelationRecord,
    EvidenceRequirementRecord,
    EvidenceCompilerVisualizationDataV1,
    P009VisualizationArtifactSet,
)
from bridge.toolkit.contracts import EvidenceState
from bridge.tool_packages.p0_09_evidence_compiler.queries import EvidenceGraphQueries
from bridge.toolkit.contracts import (
    ExecutionState,
    ImplementationState,
    ToolPackageSpecV2,
    ToolRequest,
    ToolRequestV2,
)
from bridge.toolkit.registry import ToolRegistry


SHA = "a" * 64
CREATED_AT = "2026-08-13T00:00:00Z"


def _case_graph_id(product_case_id: str, version: str = "1.0.0") -> str:
    identity = f"case|{product_case_id}@{version}"
    return "case-evidence-graph:" + hashlib.sha256(identity.encode()).hexdigest()[:24]


def _write(path: Path, payload: object) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _spec() -> ToolPackageSpecV2:
    return ToolPackageSpecV2(
        tool_id="P0-09",
        name="Evidence Compiler & Reconciler",
        version="0.4.1",
        summary="Compile atomic evidence and reconcile conflicts by versioned rules.",
        implementation_state=ImplementationState.IMPLEMENTED,
        scientific_status="candidate",
        optional=False,
        environment_spec_id="ENV-EVIDENCE-v0.2",
        input_schema_ref="bridge://schemas/tool-request/v0.2",
        output_schema_ref="bridge://schemas/tool-run/v0.2",
        result_schema_ref=RESULT_SCHEMA_REF,
        adapter_ref="bridge.tool_packages.p0_09_evidence_compiler.adapter:adapter",
        method_ids=[
            "METHOD-INTERNAL-DETERMINISTIC-ENGINE-25908A",
            "METHOD-INTERNAL-READ-ONLY-API",
            "METHOD-COLUMNAR-STORAGE",
            "METHOD-GRAPH-LIBRARY",
        ],
        card_ref="bridge://tool-cards/P0-09",
    )


def _profile(
    *,
    profile_id: str = "evidence-sufficiency-profile:aaaaaaaaaaaaaaaa:target_identity",
    product_case_ref: str = "product-case:synthetic-001",
    domain_id: str = "target_identity",
    measurement_spec_ref: str = "measurement-spec:target",
    state: str = "sufficient",
) -> dict[str, Any]:
    state_reason = {
        "sufficient": "raw_evidence_gate_sufficient",
        "limited": "raw_evidence_gate_limited",
        "insufficient": "raw_evidence_gate_insufficient",
        "not_assessed": "raw_evidence_gate_not_assessed",
    }[state]
    return {
        "profile_id": profile_id,
        "profile_version": "0.1.0",
        "gate_rule_spec_ref": "GATE-EVIDENCE-SUFFICIENCY-v0.1",
        "gate_rule_version": "0.1.0",
        "product_case_ref": product_case_ref,
        "product_definition_ref": "product-definition:synthetic",
        "domain_id": domain_id,
        "measurement_spec_ref": measurement_spec_ref,
        "score_contract_ref": None,
        "data_readiness": "adequate",
        "data_reason_codes": ["data_readiness_adequate"],
        "qc_profile_ref": "qc-profile:synthetic",
        "model_robustness": "validated_applicable",
        "robustness_reason_codes": ["method_validated_applicable"],
        "validation_refs": ["validation:synthetic"],
        "prior_applicability": "applicable",
        "prior_reason_codes": ["prior_applicable"],
        "snapshot_refs": ["snapshot:synthetic"],
        "evidence_sufficiency_state": state,
        "blocking_reasons": [] if state == "sufficient" else [state_reason],
        "limiting_reasons": [],
        "missing_requirements": [],
        "domain_score": None,
        "score_state": "unavailable",
        "score_reason_codes": ["p0_score_contract_unavailable"],
        "measurement_result_refs": ["measurement-result:target"],
        "evidence_refs": ["upstream-evidence:target"],
        "sensitivity_refs": ["sensitivity:synthetic"],
        "deduplicated_evidence_family_ids": ["evidence-family:transcriptomic"],
        "created_at": CREATED_AT,
        "deterministic_run_ref": "run-aaaaaaaaaaaaaaaa",
    }


def _family_registry(*, second_family: bool = False) -> dict[str, Any]:
    families = [
        {
            "evidence_family_id": "evidence-family:transcriptomic",
            "version": "1.0.0",
            "family_type": "shared_data",
            "channel_role": "transcriptomic",
            "shared_source_refs": ["source:synthetic"],
            "shared_algorithm_refs": ["algorithm:synthetic"],
            "shared_reference_or_prior_refs": ["reference:synthetic"],
            "independence_scope": "synthetic-transcriptomic",
            "known_dependencies": [],
            "rationale": "Synthetic independent transcriptomic channel.",
            "reviewer_ref": "reviewer:synthetic",
            "status": "reviewed",
        }
    ]
    if second_family:
        families.append(
            {
                **families[0],
                "evidence_family_id": "evidence-family:orthogonal",
                "channel_role": "orthogonal",
                "independence_scope": "synthetic-orthogonal",
            }
        )
    return {
        "registry_id": "BRIDGE-EVIDENCE-FAMILY-REGISTRY-v0.1",
        "registry_version": "0.1.0",
        "status": "frozen",
        "created_at": CREATED_AT,
        "families": families,
    }


def _claim_registry(*, orthogonal_required: bool = False) -> dict[str, Any]:
    requirements = [
        {
            "requirement_key": "transcriptomic_channel",
            "channel_role": "transcriptomic",
            "required_modality": "scRNA-seq",
            "required_experiment": None,
            "blocking_scope": "claim",
            "required": True,
        }
    ]
    if orthogonal_required:
        requirements.append(
            {
                "requirement_key": "orthogonal_channel",
                "channel_role": "orthogonal",
                "required_modality": None,
                "required_experiment": "orthogonal assay",
                "blocking_scope": "claim",
                "required": True,
            }
        )
    return {
        "registry_id": "BRIDGE-CLAIM-REGISTRY-v0.1",
        "registry_version": "0.1.0",
        "status": "frozen",
        "created_at": CREATED_AT,
        "claims": [
            {
                "claim_id": "claim:target-identity",
                "version": "1.0.0",
                "claim_type": "identity_support",
                "domain_id": "target_identity",
                "claim_target_ref": "target:synthetic",
                "biological_context_ref": {
                    "object_id": "context:synthetic",
                    "object_version": "1.0.0",
                },
                "allowed_relations": ["supports", "contradicts"],
                "reconciliation_spec_ref": {
                    "object_id": "reconciliation-spec:identity",
                    "object_version": "1.0.0",
                },
                "requirement_specs": requirements,
                "status": "frozen",
                "reviewer_ref": "reviewer:synthetic",
            }
        ],
    }


def _reconciliation_registry(*, orthogonal_required: bool = False) -> dict[str, Any]:
    required = ["transcriptomic"]
    minimum = {"transcriptomic": 1}
    if orthogonal_required:
        required.append("orthogonal")
        minimum["orthogonal"] = 1
    return {
        "registry_id": "BRIDGE-RECONCILIATION-SPEC-REGISTRY-v0.1",
        "registry_version": "0.1.0",
        "status": "frozen",
        "created_at": CREATED_AT,
        "specs": [
            {
                "reconciliation_spec_id": "reconciliation-spec:identity",
                "version": "1.0.0",
                "claim_type": "identity_support",
                "required_channel_roles": required,
                "optional_channel_roles": [],
                "primary_channel_roles": ["transcriptomic"],
                "confirmation_channel_roles": [],
                "integration_sensitive_channel_roles": [],
                "minimum_independent_families_by_role": minimum,
                "allowed_evidence_states": ["measured", "negative", "alert"],
                "required_sufficiency_states": ["sufficient"],
                "conflict_rule": "family_dedup_then_channel_resolution",
                "consensus_rule": "unanimous_independent_confirmation",
                "integration_sensitivity_rule": "integration_role_disagrees_with_resolved_direction",
                "missing_behavior": "insufficient_evidence",
                "validation_ref": "validation:synthetic-reconciliation",
                "reviewer_ref": "reviewer:synthetic",
                "status": "frozen",
            }
        ],
    }


def _comparison_claim_registry() -> dict[str, Any]:
    claims = []
    for claim_id in ("claim:case-a", "claim:case-b", "claim:comparison"):
        claims.append(
            {
                "claim_id": claim_id,
                "version": "1.0.0",
                "claim_type": "identity_support",
                "domain_id": "target_identity",
                "claim_target_ref": "target:synthetic",
                "biological_context_ref": {
                    "object_id": "context:synthetic",
                    "object_version": "1.0.0",
                },
                "allowed_relations": ["supports", "contradicts"],
                "reconciliation_spec_ref": {
                    "object_id": "reconciliation-spec:identity",
                    "object_version": "1.0.0",
                },
                "requirement_specs": [],
                "status": "frozen",
                "reviewer_ref": "reviewer:synthetic",
            }
        )
    return {
        "registry_id": "BRIDGE-CLAIM-REGISTRY-v0.1",
        "registry_version": "0.1.0",
        "status": "frozen",
        "created_at": CREATED_AT,
        "claims": claims,
    }


def _comparison_bundle(*, dangling: bool = False) -> dict[str, Any]:
    case_graphs = [
        {
            "graph_id": _case_graph_id("product-case:case-a"),
            "graph_version": 1,
            "manifest_sha256": "a" * 64,
            "product_case_ref": {
                "object_id": "product-case:case-a",
                "object_version": "1.0.0",
            },
            "manifest_input_id": "source-manifest-0",
            "record_set_input_id": "source-records-0",
        },
        {
            "graph_id": _case_graph_id("product-case:case-b"),
            "graph_version": 1,
            "manifest_sha256": "b" * 64,
            "product_case_ref": {
                "object_id": "product-case:case-b",
                "object_version": "1.0.0",
            },
            "manifest_input_id": "source-manifest-1",
            "record_set_input_id": "source-records-1",
        },
    ]
    externals = []
    for index, (case_ref, relation) in enumerate(
        zip(case_graphs, ("supports", "contradicts"), strict=True)
    ):
        public_case_ref = {
            key: value
            for key, value in case_ref.items()
            if key not in {"manifest_input_id", "record_set_input_id"}
        }
        externals.append(
            {
                "source_case_graph_ref": public_case_ref,
                "evidence_ref": f"evidence:{('a' if index == 0 else 'b') * 24}@1",
                "evidence_content_hash": ("c" if index == 0 else "d") * 64,
                "product_case_ref": case_ref["product_case_ref"],
                "source_claim_ref": {
                    "object_id": f"claim:case-{'a' if index == 0 else 'b'}",
                    "object_version": "1.0.0",
                },
                "comparison_claim_ref": {
                    "object_id": "claim:comparison",
                    "object_version": "1.0.0",
                },
                "evidence_family_ref": {
                    "object_id": "evidence-family:transcriptomic",
                    "object_version": "1.0.0",
                },
                "sufficiency_profile_input_id": f"profile-{'a' if index == 0 else 'b'}",
                "relation": relation,
                "evidence_state": "measured",
                "evidence_tier": "shadow",
                "lifecycle_state": "active",
                "applicability": "applicable",
                "tool_run_execution_state": "succeeded",
            }
        )
    if dangling:
        externals[1] = {
            **externals[1],
            "source_claim_ref": {
                "object_id": "claim:not-registered",
                "object_version": "1.0.0",
            },
        }
    return {
        "bundle_id": "evidence-compilation-bundle:comparison",
        "bundle_version": "0.1.0",
        "graph_kind": "comparison",
        "product_case_ref": None,
        "comparison_ref": {
            "object_id": "comparison:case-a-vs-b",
            "object_version": "1.0.0",
        },
        "case_graph_refs": case_graphs,
        "external_case_evidence_refs": externals,
        "base_graph_ref": None,
        "object_catalog": [
            {
                "object_id": "comparison:case-a-vs-b",
                "object_version": "1.0.0",
                "node_type": "ComparisonRecord",
                "schema_ref": "bridge://schemas/comparison-record/v0.1",
                "content_hash": "e" * 64,
            }
        ],
        "candidate_records": [],
        "missing_observations": [],
        "prior_evidence_records": [],
        "prior_requirements": [],
        "created_at": CREATED_AT,
        "provenance_refs": ["provenance:comparison"],
    }


def _comparison_profiles() -> list[tuple[str, dict[str, Any]]]:
    return [
        (
            "profile-a",
            _profile(
                profile_id="evidence-sufficiency-profile:aaaaaaaaaaaaaaaa:target_identity",
                product_case_ref="product-case:case-a",
            ),
        ),
        (
            "profile-b",
            _profile(
                profile_id="evidence-sufficiency-profile:bbbbbbbbbbbbbbbb:target_identity",
                product_case_ref="product-case:case-b",
            )
            | {"deterministic_run_ref": "run-bbbbbbbbbbbbbbbb"},
        ),
    ]


def _source_record_for_external(
    external: dict[str, Any], profile: dict[str, Any]
) -> dict[str, Any]:
    suffix = external["product_case_ref"]["object_id"].split(":", 1)[1]
    record = EvidenceRecord(
        evidence_id="evidence:" + "0" * 24,
        evidence_version=1,
        logical_key="pending",
        content_hash="0" * 64,
        product_case_ref=external["product_case_ref"],
        sample_or_preparation_ref={
            "object_id": f"sample:{suffix}",
            "object_version": "1.0.0",
        },
        domain_id="target_identity",
        measurement_result_ref={
            "object_id": "measurement-result:target",
            "object_version": "1.0.0",
        },
        measurement_spec_ref={
            "object_id": "measurement-spec:target",
            "object_version": "1.0.0",
        },
        metric_id=f"target-fraction-{suffix}",
        value=0.5,
        unit="fraction",
        claim_ref={
            "object_id": f"claim:{suffix}",
            "object_version": "1.0.0",
        },
        biological_context={
            "context_id": "context:synthetic",
            "context_version": "1.0.0",
        },
        relation=external["relation"],
        evidence_state="measured",
        evidence_tier="shadow",
        lifecycle_state="active",
        applicability="applicable",
        evidence_family_ref={
            "object_id": "evidence-family:transcriptomic",
            "object_version": "1.0.0",
        },
        sufficiency_profile_ref={
            "object_id": profile["profile_id"],
            "object_version": profile["profile_version"],
        },
        tool_run_ref={"object_id": f"tool-run:{suffix}", "object_version": "1.0.0"},
        tool_run_execution_state="succeeded",
        reference_refs=[],
        prior_refs=[],
        artifact_refs=[],
        provenance_refs=[f"provenance:{suffix}"],
        revision_action="create",
        predecessor_ref=None,
        created_at=CREATED_AT,
        compiler_version="0.2.0",
    )
    logical_key = evidence_record_logical_key(record)
    record = record.model_copy(
        update={"logical_key": logical_key, "evidence_id": evidence_identity(logical_key)}
    )
    return record.model_copy(update={"content_hash": evidence_record_content_hash(record)}).model_dump(mode="json")


def _materialize_comparison_sources(
    tmp_path: Path,
    bundle: dict[str, Any],
    profiles: list[tuple[str, dict[str, Any]]],
) -> tuple[dict[str, Any], list[Path]]:
    bundle = json.loads(json.dumps(bundle))
    profile_by_input = dict(profiles)
    paths: list[Path] = []
    for index, case_ref in enumerate(bundle["case_graph_refs"]):
        source_input_hash = str(index + 1) * 64
        source_digest = source_input_hash[:16]
        external = next(
            item
            for item in bundle["external_case_evidence_refs"]
            if item["source_case_graph_ref"]["graph_id"] == case_ref["graph_id"]
        )
        profile = profile_by_input[external["sufficiency_profile_input_id"]]
        expected = _source_record_for_external(external, profile)
        placeholder_ref = f"evidence:{('a' if index == 0 else 'b') * 24}@1"
        if external["evidence_ref"] == placeholder_ref:
            external["evidence_ref"] = f"{expected['evidence_id']}@1"
        record_set = {
            "record_set_id": f"evidence-record-set:{source_digest}",
            "record_set_version": "0.1.0",
            "graph_id": case_ref["graph_id"],
            "graph_version": case_ref["graph_version"],
            "records": [expected],
            "dispositions": [],
        }
        root = tmp_path / f"source-case-{index}"
        records_path = root / "evidence_records.json"
        records_sha = _write(records_path, record_set)
        requirement_set = {
            "requirement_set_id": f"evidence-requirement-set:{source_digest}",
            "requirement_set_version": "0.1.0",
            "graph_id": case_ref["graph_id"],
            "graph_version": case_ref["graph_version"],
            "requirements": [],
        }
        requirements_sha = _write(root / "evidence_requirements.json", requirement_set)
        reconciliation_set = {
            "reconciliation_set_id": f"reconciliation-record-set:{source_digest}",
            "reconciliation_set_version": "0.1.0",
            "graph_id": case_ref["graph_id"],
            "graph_version": case_ref["graph_version"],
            "records": [],
        }
        reconciliation_sha = _write(
            root / "reconciliation_records.json", reconciliation_set
        )
        product = case_ref["product_case_ref"]
        suffix = product["object_id"].split(":", 1)[1]
        catalog = [
            {
                "object_id": object_id,
                "object_version": "1.0.0",
                "node_type": node_type,
                "schema_ref": f"bridge://schemas/{schema}/v0.1",
                "content_hash": hashlib.sha256(object_id.encode()).hexdigest(),
            }
            for object_id, node_type, schema in [
                (product["object_id"], "ProductCase", "product-case"),
                (f"sample:{suffix}", "Sample", "sample"),
                ("measurement-result:target", "MeasurementResult", "measurement-result"),
                ("measurement-spec:target", "MeasurementSpec", "measurement-spec"),
                (f"tool-run:{suffix}", "ToolRun", "tool-run"),
            ]
        ]
        source_bundle = EvidenceCompilationBundle.model_validate(
            {
                "bundle_id": f"evidence-compilation-bundle:source-{index}",
                "bundle_version": "0.1.0",
                "graph_kind": "case",
                "product_case_ref": product,
                "comparison_ref": None,
                "case_graph_refs": [],
                "external_case_evidence_refs": [],
                "base_graph_ref": None,
                "object_catalog": catalog,
                "candidate_records": [],
                "missing_observations": [],
                "prior_evidence_records": [],
                "prior_requirements": [],
                "created_at": CREATED_AT,
                "provenance_refs": [f"provenance:source-{index}"],
            }
        )
        nodes, edges = build_graph_rows(
            graph_id=case_ref["graph_id"],
            graph_version=case_ref["graph_version"],
            bundle=source_bundle,
            records=[EvidenceRecord.model_validate(expected)],
            requirements=[],
            reconciliation_records=[],
            profiles_by_input_id={
                external["sufficiency_profile_input_id"]: (
                    EvidenceSufficiencyProfileV2
                    if profile["profile_version"] == "0.2.0"
                    else EvidenceSufficiencyProfile
                ).model_validate(profile)
            },
            family_registry=EvidenceFamilyRegistry.model_validate(_family_registry()),
            claim_registry=ClaimRegistry.model_validate(_comparison_claim_registry()),
            reconciliation_registry=ReconciliationSpecRegistry.model_validate(
                _reconciliation_registry()
            ),
        )
        write_parquet(root / "graph_nodes.parquet", root / "graph_edges.parquet", nodes, edges)
        nodes_sha = hashlib.sha256((root / "graph_nodes.parquet").read_bytes()).hexdigest()
        edges_sha = hashlib.sha256((root / "graph_edges.parquet").read_bytes()).hexdigest()
        manifest = {
            "graph_id": case_ref["graph_id"],
            "graph_version": case_ref["graph_version"],
            "canonicalization_id": "bridge-canonical-json/v0.1",
            "node_count": len(nodes),
            "edge_count": len(edges),
            "object_counts": {
                key.value: value for key, value in object_counts(nodes).items()
            },
            "source_input_hash": source_input_hash,
            "base_graph_ref": None,
            "evidence_records": {
                "filename": "evidence_records.json",
                "media_type": "application/json",
                "sha256": records_sha,
                "row_count": None,
            },
            "evidence_requirements": {
                "filename": "evidence_requirements.json",
                "media_type": "application/json",
                "sha256": requirements_sha,
                "row_count": None,
            },
            "reconciliation_records": {
                "filename": "reconciliation_records.json",
                "media_type": "application/json",
                "sha256": reconciliation_sha,
                "row_count": None,
            },
            "graph_nodes": {
                "filename": "graph_nodes.parquet",
                "media_type": "application/vnd.apache.parquet",
                "sha256": nodes_sha,
                "row_count": len(nodes),
            },
            "graph_edges": {
                "filename": "graph_edges.parquet",
                "media_type": "application/vnd.apache.parquet",
                "sha256": edges_sha,
                "row_count": len(edges),
            },
            "created_at": CREATED_AT,
            "graph_kind": "case",
            "product_case_ref": case_ref["product_case_ref"],
        }
        manifest_path = root / "case_evidence_graph_manifest.json"
        manifest_sha = _write(manifest_path, manifest)
        original_sha = case_ref["manifest_sha256"]
        external_original_sha = external["source_case_graph_ref"]["manifest_sha256"]
        if original_sha in {"a" * 64, "b" * 64}:
            case_ref["manifest_sha256"] = manifest_sha
            if external_original_sha == original_sha:
                external["source_case_graph_ref"]["manifest_sha256"] = manifest_sha
        if external["evidence_content_hash"] in {"c" * 64, "d" * 64}:
            external["evidence_content_hash"] = expected["content_hash"]
        paths.append(manifest_path)
    return bundle, paths


def _catalog() -> list[dict[str, Any]]:
    return [
        {
            "object_id": object_id,
            "object_version": "1.0.0",
            "node_type": node_type,
            "schema_ref": f"bridge://schemas/{schema}/v0.1",
            "content_hash": hashlib.sha256(object_id.encode()).hexdigest(),
        }
        for object_id, node_type, schema in [
            ("product-case:synthetic-001", "ProductCase", "product-case"),
            ("sample:synthetic-001", "Sample", "sample"),
            ("measurement-result:target", "MeasurementResult", "measurement-result"),
            ("measurement-spec:target", "MeasurementSpec", "measurement-spec"),
            ("tool-run:target", "ToolRun", "tool-run"),
            ("reference:one", "ReferenceSnapshot", "reference-snapshot"),
            ("reference:two", "ReferenceSnapshot", "reference-snapshot"),
        ]
    ]


def _candidate(
    *,
    candidate_id: str = "evidence-candidate:target",
    metric_id: str = "target_fraction",
    value: Any = 0.75,
    relation: str = "supports",
    tier: str = "shadow",
    family_id: str = "evidence-family:transcriptomic",
    references: list[str] | None = None,
    revision_action: str = "create",
    predecessor_ref: str | None = None,
) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "product_case_ref": {
            "object_id": "product-case:synthetic-001",
            "object_version": "1.0.0",
        },
        "sample_or_preparation_ref": {
            "object_id": "sample:synthetic-001",
            "object_version": "1.0.0",
        },
        "domain_id": "target_identity",
        "measurement_result_ref": {
            "object_id": "measurement-result:target",
            "object_version": "1.0.0",
        },
        "measurement_spec_ref": {
            "object_id": "measurement-spec:target",
            "object_version": "1.0.0",
        },
        "score_contract_ref": None,
        "metric_id": metric_id,
        "value": value,
        "unit": "fraction",
        "numerator": 75,
        "denominator": 100,
        "interval": {"lower": 0.65, "upper": 0.82, "confidence_level": 0.95},
        "claim_ref": {"object_id": "claim:target-identity", "object_version": "1.0.0"},
        "biological_context": {
            "context_id": "context:synthetic",
            "context_version": "1.0.0",
            "species": "human",
            "assay": "scRNA-seq",
            "specimen": "synthetic cells",
        },
        "relation": relation,
        "evidence_state": "measured",
        "evidence_tier": tier,
        "applicability": "applicable",
        "evidence_family_ref": {"object_id": family_id, "object_version": "1.0.0"},
        "sufficiency_profile_input_id": "profile-target",
        "tool_run_ref": {"object_id": "tool-run:target", "object_version": "1.0.0"},
        "tool_run_execution_state": "succeeded",
        "reference_refs": [
            {"object_id": item, "object_version": "1.0.0"}
            for item in (references or ["reference:one", "reference:two"])
        ],
        "prior_refs": [],
        "artifact_refs": [],
        "provenance_refs": ["provenance:two", "provenance:one"],
        "revision_action": revision_action,
        "predecessor_ref": predecessor_ref,
        "created_at": CREATED_AT,
    }


def _bundle(
    *,
    candidates: list[dict[str, Any]] | None = None,
    missing: list[dict[str, Any]] | None = None,
    prior_records: list[dict[str, Any]] | None = None,
    prior_requirements: list[dict[str, Any]] | None = None,
    base_graph_ref: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if base_graph_ref is not None:
        base_graph_ref = {
            **base_graph_ref,
            "manifest_input_id": "base-manifest",
            "record_set_input_id": "base-records",
            "requirement_set_input_id": "base-requirements",
        }
    return {
        "bundle_id": "evidence-compilation-bundle:synthetic-001",
        "bundle_version": "0.1.0",
        "graph_kind": "case",
        "product_case_ref": {
            "object_id": "product-case:synthetic-001",
            "object_version": "1.0.0",
        },
        "comparison_ref": None,
        "case_graph_refs": [],
        "external_case_evidence_refs": [],
        "base_graph_ref": base_graph_ref,
        "object_catalog": _catalog(),
        "candidate_records": candidates if candidates is not None else [_candidate()],
        "missing_observations": missing or [],
        "prior_evidence_records": prior_records or [],
        "prior_requirements": prior_requirements or [],
        "created_at": CREATED_AT,
        "provenance_refs": ["provenance:bundle"],
    }


def _missing_observation() -> dict[str, Any]:
    return {
        "observation_id": "missing-evidence:orthogonal",
        "product_case_ref": {
            "object_id": "product-case:synthetic-001",
            "object_version": "1.0.0",
        },
        "claim_ref": {"object_id": "claim:target-identity", "object_version": "1.0.0"},
        "requirement_key": "orthogonal_channel",
        "reason_code": "required_experiment_not_performed",
        "source_contract_ref": {
            "object_id": "claim:target-identity",
            "object_version": "1.0.0",
        },
        "provenance_refs": ["provenance:missing"],
        "observed_at": CREATED_AT,
    }


def _request(
    tmp_path: Path,
    *,
    bundle: dict[str, Any] | None = None,
    profile: dict[str, Any] | None = None,
    profiles: list[tuple[str, dict[str, Any]]] | None = None,
    family_registry: dict[str, Any] | None = None,
    claim_registry: dict[str, Any] | None = None,
    reconciliation_registry: dict[str, Any] | None = None,
    request_id: str = "request-p0-09",
    output_name: str = "output",
    base_manifest_path: Path | None = None,
    source_case_manifest_paths: list[Path] | None = None,
    sufficiency_runs: list[tuple[str, dict[str, Any]]] | None = None,
) -> ToolRequestV2:
    inputs = tmp_path / f"inputs-{request_id}"
    manifest_paths_by_input_id: dict[str, Path] = {}
    profile_objects = (
        [(input_id, payload["profiles"][0]) for input_id, payload in sufficiency_runs]
        if sufficiency_runs is not None
        else profiles or [("profile-target", profile or _profile())]
    )
    effective_bundle = json.loads(json.dumps(bundle or _bundle()))
    if (
        effective_bundle["graph_kind"] == "comparison"
        and source_case_manifest_paths is None
    ):
        effective_bundle, source_case_manifest_paths = _materialize_comparison_sources(
            inputs, effective_bundle, profile_objects
        )
    objects = [
        (
            "bundle",
            "compilation_bundle",
            "bridge://schemas/evidence-compilation-bundle/v0.1",
            effective_bundle,
            "0.1.0",
        ),
        (
            "families",
            "evidence_family_registry",
            "bridge://schemas/evidence-family-registry/v0.1",
            family_registry or _family_registry(),
            "0.1.0",
        ),
        (
            "claims",
            "claim_registry",
            "bridge://schemas/claim-registry/v0.1",
            claim_registry or _claim_registry(),
            "0.1.0",
        ),
        (
            "reconciliation",
            "reconciliation_spec_registry",
            "bridge://schemas/reconciliation-spec-registry/v0.1",
            reconciliation_registry or _reconciliation_registry(),
            "0.1.0",
        ),
    ]
    objects[1:1] = (
        [
            (
                input_id,
                "evidence_sufficiency_run_result",
                "bridge://schemas/evidence-sufficiency-run-result/v0.2",
                payload,
                "0.2.0",
            )
            for input_id, payload in sufficiency_runs
        ]
        if sufficiency_runs is not None
        else [
            (
                input_id,
                "evidence_sufficiency_profile",
                (
                    "bridge://schemas/evidence-sufficiency-profile/v0.2"
                    if payload["profile_version"] == "0.2.0"
                    else "bridge://schemas/evidence-sufficiency-profile/v0.1"
                ),
                payload,
                payload["profile_version"],
            )
            for input_id, payload in profile_objects
        ]
    )
    if base_manifest_path is not None:
        manifest_paths_by_input_id["base-manifest"] = base_manifest_path
        base_manifest = json.loads(base_manifest_path.read_text())
        base_root = base_manifest_path.parent
        objects.extend(
            [
                (
                    "base-manifest",
                    "base_graph_manifest",
                    (
                        "bridge://schemas/case-evidence-graph-manifest/v0.1"
                        if base_manifest["graph_kind"] == "case"
                        else "bridge://schemas/comparison-evidence-graph-manifest/v0.1"
                    ),
                    base_manifest,
                    str(base_manifest["graph_version"]),
                ),
                (
                    "base-records",
                    "base_evidence_record_set",
                    "bridge://schemas/evidence-record-set/v0.1",
                    json.loads((base_root / base_manifest["evidence_records"]["filename"]).read_text()),
                    "0.1.0",
                ),
                (
                    "base-requirements",
                    "base_evidence_requirement_set",
                    "bridge://schemas/evidence-requirement-set/v0.1",
                    json.loads(
                        (base_root / base_manifest["evidence_requirements"]["filename"]).read_text()
                    ),
                    "0.1.0",
                ),
            ]
        )
    for index, source_manifest_path in enumerate(source_case_manifest_paths or []):
        manifest_paths_by_input_id[f"source-manifest-{index}"] = source_manifest_path
        source_manifest = json.loads(source_manifest_path.read_text())
        source_root = source_manifest_path.parent
        objects.extend(
            [
                (
                    f"source-manifest-{index}",
                    "source_case_graph_manifest",
                    "bridge://schemas/case-evidence-graph-manifest/v0.1",
                    source_manifest,
                    str(source_manifest["graph_version"]),
                ),
                (
                    f"source-records-{index}",
                    "source_case_evidence_record_set",
                    "bridge://schemas/evidence-record-set/v0.1",
                    json.loads(
                        (source_root / source_manifest["evidence_records"]["filename"]).read_text()
                    ),
                    "0.1.0",
                ),
            ]
        )
    refs = []
    for input_id, role, schema_ref, payload, version in objects:
        path = manifest_paths_by_input_id.get(input_id, inputs / f"{input_id}.json")
        digest = (
            hashlib.sha256(path.read_bytes()).hexdigest()
            if input_id in manifest_paths_by_input_id
            else _write(path, payload)
        )
        refs.append(
            {
                "input_id": input_id,
                "role": role,
                "schema_ref": schema_ref,
                "object_version": version,
                "path": path.resolve(),
                "sha256": digest,
                "media_type": "application/json",
            }
        )
    return ToolRequestV2(
        request_id=request_id,
        tool_id="P0-09",
        tool_version="0.4.1",
        output_dir=(tmp_path / output_name).resolve(),
        assets=[],
        measurement_spec_ref=None,
        parameters={},
        random_seed=0,
        object_inputs=refs,
    )


def _run(tmp_path: Path, **kwargs: Any):
    request = _request(tmp_path, **kwargs)
    return adapter.run(request, _spec())


@pytest.mark.parametrize("schema_ref,model", PUBLIC_SCHEMA_MODELS.items())
def test_public_models_export_valid_draft_2020_12_schema(schema_ref: str, model: type[Any]) -> None:
    schema = model.model_json_schema()
    Draft202012Validator.check_schema(schema)
    assert schema["additionalProperties"] is False
    assert schema_ref.startswith("bridge://schemas/")


def test_committed_synthetic_fixtures_validate_without_private_material() -> None:
    fixture_root = Path(__file__).parent / "fixtures" / "p0_09"
    case = EvidenceCompilationBundle.model_validate_json(
        (fixture_root / "case_bundle.json").read_text()
    )
    comparison = EvidenceCompilationBundle.model_validate_json(
        (fixture_root / "comparison_bundle.json").read_text()
    )
    missing = MissingEvidenceObservation.model_validate_json(
        (fixture_root / "missing_observation.json").read_text()
    )
    history = json.loads((fixture_root / "append_history.json").read_text())
    assert case.graph_kind.value == "case"
    assert comparison.graph_kind.value == "comparison"
    assert missing.reason_code == "measurement_not_provided"
    assert [item["revision_action"] for item in history["steps"]] == [
        "create",
        "supersede",
        "invalidate",
    ]
    serialized = json.dumps(
        [
            case.model_dump(mode="json"),
            comparison.model_dump(mode="json"),
            missing.model_dump(mode="json"),
        ]
    )
    private_path = re.compile(
        r"(?:/(?:data[0-9]+|mnt|srv|private|internal)/|/"
        r"Users/|/home/)"
    )
    assert private_path.search(serialized) is None


def test_case_compilation_publishes_complete_immutable_bundle_without_formal_promotion(
    tmp_path: Path,
) -> None:
    run = _run(tmp_path)

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result_schema_ref == RESULT_SCHEMA_REF
    assert run.measurements == [] and run.visualizations == []
    assert len(run.artifacts) == 24
    result = EvidenceCompilerRunResult.model_validate(run.result)
    final = run.request.output_dir / run.run_id
    assert final.is_dir()
    records = EvidenceRecordSet.model_validate_json((final / "evidence_records.json").read_text())
    requirements = EvidenceRequirementSet.model_validate_json(
        (final / "evidence_requirements.json").read_text()
    )
    reconciliations = ReconciliationRecordSet.model_validate_json(
        (final / "reconciliation_records.json").read_text()
    )
    assert len(records.records) == 1
    assert records.records[0].evidence_version == 1
    assert requirements.requirements[-1].state.value == "open"
    assert reconciliations.records[0].eligibility.value == "insufficient_evidence"
    assert reconciliations.records[0].state is None
    assert reconciliations.records[0].direction is None
    serialized = json.dumps(result.model_dump(mode="json"), sort_keys=True)
    assert "domain_score" not in serialized
    assert "overall_score" not in serialized


def test_missing_observation_creates_open_requirement_and_never_zero_record(
    tmp_path: Path,
) -> None:
    bundle = _bundle(missing=[_missing_observation()])
    run = _run(
        tmp_path,
        bundle=bundle,
        family_registry=_family_registry(second_family=True),
        claim_registry=_claim_registry(orthogonal_required=True),
        reconciliation_registry=_reconciliation_registry(orthogonal_required=True),
    )

    assert run.execution_state is ExecutionState.SUCCEEDED
    final = run.request.output_dir / run.run_id
    records = json.loads((final / "evidence_records.json").read_text())["records"]
    requirements = json.loads((final / "evidence_requirements.json").read_text())[
        "requirements"
    ]
    orthogonal = [item for item in requirements if item["requirement_key"] == "orthogonal_channel"]
    assert len(records) == 1
    assert orthogonal[-1]["state"] == "open"
    assert orthogonal[-1]["satisfying_evidence_refs"] == []
    assert all(item.get("value") != 0 for item in records)
    reconciliation = json.loads((final / "reconciliation_records.json").read_text())[
        "records"
    ][0]
    assert reconciliation["eligibility"] == "insufficient_evidence"
    assert reconciliation["state"] is None and reconciliation["direction"] is None


def test_shadow_record_is_visible_but_never_formal_reconciliation_input(tmp_path: Path) -> None:
    run = _run(tmp_path, bundle=_bundle(candidates=[_candidate(tier="shadow")]))
    assert run.execution_state is ExecutionState.SUCCEEDED
    final = run.request.output_dir / run.run_id
    reconciliation = json.loads((final / "reconciliation_records.json").read_text())[
        "records"
    ][0]
    assert reconciliation["included_evidence_refs"] == []
    assert reconciliation["eligibility"] == "insufficient_evidence"
    assert "lower_tier_excluded" in reconciliation["reason_codes"]


def test_shadow_integration_role_cannot_create_integration_sensitive_conclusion(
    tmp_path: Path,
) -> None:
    families = _family_registry(second_family=True)
    reconciliation = _reconciliation_registry()
    spec = reconciliation["specs"][0]
    spec["optional_channel_roles"] = ["orthogonal"]
    spec["integration_sensitive_channel_roles"] = ["orthogonal"]
    candidates = [
        _candidate(),
        _candidate(
            candidate_id="evidence-candidate:orthogonal",
            metric_id="orthogonal_identity",
            relation="contradicts",
            family_id="evidence-family:orthogonal",
        ),
    ]
    run = _run(
        tmp_path,
        bundle=_bundle(candidates=candidates),
        family_registry=families,
        reconciliation_registry=reconciliation,
        profile=_profile()
        | {
            "deduplicated_evidence_family_ids": [
                "evidence-family:transcriptomic",
                "evidence-family:orthogonal",
            ]
        },
    )
    assert run.execution_state is ExecutionState.SUCCEEDED
    record = json.loads(
        ((run.request.output_dir / run.run_id) / "reconciliation_records.json").read_text()
    )["records"][0]
    assert record["eligibility"] == "insufficient_evidence"
    assert record["state"] is None and record["direction"] is None
    assert "lower_tier_excluded" in record["reason_codes"]


def test_shadow_cross_family_conflict_cannot_be_promoted_by_confirmation(
    tmp_path: Path,
) -> None:
    base = _family_registry()["families"][0]
    families = {
        "registry_id": "BRIDGE-EVIDENCE-FAMILY-REGISTRY-v0.1",
        "registry_version": "0.1.0",
        "status": "frozen",
        "created_at": CREATED_AT,
        "families": [
            {
                **base,
                "evidence_family_id": "evidence-family:primary-a",
                "independence_scope": "primary-a",
            },
            {
                **base,
                "evidence_family_id": "evidence-family:primary-b",
                "independence_scope": "primary-b",
            },
            {
                **base,
                "evidence_family_id": "evidence-family:confirmation",
                "channel_role": "orthogonal",
                "independence_scope": "confirmation",
            },
        ],
    }
    claims = _claim_registry(orthogonal_required=True)
    reconciliation = _reconciliation_registry(orthogonal_required=True)
    spec = reconciliation["specs"][0]
    spec["primary_channel_roles"] = ["transcriptomic"]
    spec["confirmation_channel_roles"] = ["orthogonal"]
    spec["minimum_independent_families_by_role"]["transcriptomic"] = 2
    candidates = [
        _candidate(
            candidate_id="evidence-candidate:primary-a",
            metric_id="primary_a",
            relation="supports",
            family_id="evidence-family:primary-a",
        ),
        _candidate(
            candidate_id="evidence-candidate:primary-b",
            metric_id="primary_b",
            relation="contradicts",
            family_id="evidence-family:primary-b",
        ),
        _candidate(
            candidate_id="evidence-candidate:confirmation",
            metric_id="confirmation",
            relation="supports",
            family_id="evidence-family:confirmation",
        ),
    ]
    run = _run(
        tmp_path,
        bundle=_bundle(candidates=candidates),
        family_registry=families,
        claim_registry=claims,
        reconciliation_registry=reconciliation,
        profile=_profile()
        | {
            "deduplicated_evidence_family_ids": [
                "evidence-family:primary-a",
                "evidence-family:primary-b",
                "evidence-family:confirmation",
            ]
        },
    )
    assert run.execution_state is ExecutionState.SUCCEEDED
    record = json.loads(
        ((run.request.output_dir / run.run_id) / "reconciliation_records.json").read_text()
    )["records"][0]
    assert record["eligibility"] == "insufficient_evidence"
    assert record["state"] is None and record["direction"] is None
    assert "independent_confirmation_resolved_conflict" not in record["reason_codes"]


def test_one_invalid_candidate_yields_partial_without_graph_fact_or_secret_leak(
    tmp_path: Path,
) -> None:
    bad = _candidate(
        candidate_id="evidence-candidate:bad",
        metric_id="bad_metric",
        value={
            "note": "/" + "Users/private/raw.h5ad",
            "token": "gh" + "p_abcdefghijklmnopqrstuvwxyz",
        },
    )
    run = _run(tmp_path, bundle=_bundle(candidates=[_candidate(), bad]))

    assert run.execution_state is ExecutionState.PARTIAL
    final = run.request.output_dir / run.run_id
    rejected = (final / "rejected_records.json").read_text()
    nodes = (final / "graph_nodes.parquet").read_bytes()
    assert "individual_record_schema_invalid" in rejected
    assert "/" + "Users/private" not in rejected
    assert ("gh" + "p_").encode() not in nodes
    records = json.loads((final / "evidence_records.json").read_text())["records"]
    assert len(records) == 1


def test_duplicate_logical_key_is_rejected_instead_of_voted_or_overwritten(
    tmp_path: Path,
) -> None:
    duplicate = _candidate(
        candidate_id="evidence-candidate:duplicate",
        value=0.9,
    )
    run = _run(tmp_path, bundle=_bundle(candidates=[_candidate(), duplicate]))
    assert run.execution_state is ExecutionState.PARTIAL
    rejected = json.loads(
        ((run.request.output_dir / run.run_id) / "rejected_records.json").read_text()
    )["records"]
    assert any("duplicate_logical_key_conflict" in item["reason_codes"] for item in rejected)
    records = json.loads(
        ((run.request.output_dir / run.run_id) / "evidence_records.json").read_text()
    )["records"]
    assert len(records) == 1


def test_supersede_and_invalidate_append_versions_without_overwriting_history(
    tmp_path: Path,
) -> None:
    first = _run(tmp_path / "first")
    first_dir = first.request.output_dir / first.run_id
    prior_records = json.loads((first_dir / "evidence_records.json").read_text())["records"]
    prior_requirements = json.loads((first_dir / "evidence_requirements.json").read_text())[
        "requirements"
    ]
    predecessor = f"{prior_records[0]['evidence_id']}@1"
    manifest_path = first_dir / "case_evidence_graph_manifest.json"
    first_manifest = json.loads(manifest_path.read_text())
    base = {
        "graph_id": first_manifest["graph_id"],
        "graph_version": first_manifest["graph_version"],
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
    }
    second_bundle = _bundle(
        candidates=[
            _candidate(
                value=0.8,
                revision_action="supersede",
                predecessor_ref=predecessor,
            )
        ],
        prior_records=prior_records,
        prior_requirements=prior_requirements,
        base_graph_ref=base,
    )
    second = _run(
        tmp_path / "second",
        bundle=second_bundle,
        base_manifest_path=manifest_path,
    )
    assert second.execution_state is ExecutionState.SUCCEEDED
    second_dir = second.request.output_dir / second.run_id
    second_records = json.loads((second_dir / "evidence_records.json").read_text())[
        "records"
    ]
    assert [item["evidence_version"] for item in second_records] == [1, 2]
    assert second_records[0] == prior_records[0]
    assert second_records[1]["predecessor_ref"] == predecessor
    source_effective = _validate_source_record_set(
        EvidenceRecordSet.model_validate_json(
            (second_dir / "evidence_records.json").read_text()
        ),
        CaseEvidenceGraphManifest.model_validate_json(
            (second_dir / "case_evidence_graph_manifest.json").read_text()
        ),
    )
    assert source_effective[f"{second_records[0]['evidence_id']}@1"] is EvidenceLifecycleState.SUPERSEDED
    assert source_effective[f"{second_records[1]['evidence_id']}@2"] is EvidenceLifecycleState.ACTIVE
    edges = EvidenceGraphQueries.open(second_dir / "case_evidence_graph_manifest.json")
    provenance = edges.trace_evidence_provenance(
        evidence_ref=f"{second_records[1]['evidence_id']}@2"
    )
    assert provenance.returned_node_count > 1

    second_manifest_path = second_dir / "case_evidence_graph_manifest.json"
    second_manifest = json.loads(second_manifest_path.read_text())
    invalidate_bundle = _bundle(
        candidates=[
            _candidate(
                value=0.8,
                revision_action="invalidate",
                predecessor_ref=f"{second_records[1]['evidence_id']}@2",
            )
        ],
        prior_records=second_records,
        prior_requirements=json.loads(
            (second_dir / "evidence_requirements.json").read_text()
        )["requirements"],
        base_graph_ref={
            "graph_id": second_manifest["graph_id"],
            "graph_version": second_manifest["graph_version"],
            "manifest_sha256": hashlib.sha256(second_manifest_path.read_bytes()).hexdigest(),
        },
    )
    third = _run(
        tmp_path / "third",
        bundle=invalidate_bundle,
        base_manifest_path=second_manifest_path,
    )
    assert third.execution_state is ExecutionState.SUCCEEDED
    third_records = json.loads(
        ((third.request.output_dir / third.run_id) / "evidence_records.json").read_text()
    )["records"]
    assert [item["evidence_version"] for item in third_records] == [1, 2, 3]
    assert third_records[-1]["lifecycle_state"] == "invalidated"


def test_request_and_object_input_order_do_not_change_identity_or_artifact_bytes(
    tmp_path: Path,
) -> None:
    request_one = _request(tmp_path / "one", request_id="one", output_name="out-one")
    request_two = _request(tmp_path / "two", request_id="two", output_name="out-two")
    request_two = request_two.model_copy(
        update={"object_inputs": list(reversed(request_two.object_inputs))}
    )
    first = adapter.run(request_one, _spec())
    second = adapter.run(request_two, _spec())

    assert first.run_id == second.run_id
    assert first.input_hash == second.input_hash
    first_dir = first.request.output_dir / first.run_id
    second_dir = second.request.output_dir / second.run_id
    assert {item.name for item in first_dir.iterdir()} == {item.name for item in second_dir.iterdir()}
    for item in first_dir.iterdir():
        assert item.read_bytes() == (second_dir / item.name).read_bytes()


def test_identical_rerun_reuses_bundle_and_set_like_reference_order_is_canonical(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path)
    first = adapter.run(request, _spec())
    second = adapter.run(request, _spec())
    assert first.run_id == second.run_id
    assert second.execution_state is ExecutionState.SUCCEEDED
    records = json.loads(
        ((second.request.output_dir / second.run_id) / "evidence_records.json").read_text()
    )["records"]
    assert [item["object_id"] for item in records[0]["reference_refs"]] == [
        "reference:one",
        "reference:two",
    ]
    assert records[0]["provenance_refs"] == ["provenance:one", "provenance:two"]


def test_reordered_raw_set_bytes_reuse_same_output_bundle_by_semantic_hash(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path, output_name="shared-output")
    first = adapter.run(request, _spec())
    assert first.execution_state is ExecutionState.SUCCEEDED
    bundle_ref = next(item for item in request.object_inputs if item.role == "compilation_bundle")
    raw = json.loads(bundle_ref.path.read_text())
    raw["object_catalog"] = list(reversed(raw["object_catalog"]))
    raw["candidate_records"][0]["reference_refs"] = list(
        reversed(raw["candidate_records"][0]["reference_refs"])
    )
    raw["candidate_records"][0]["provenance_refs"] = list(
        reversed(raw["candidate_records"][0]["provenance_refs"])
    )
    new_checksum = _write(bundle_ref.path, raw)
    second_request = request.model_copy(
        update={
            "request_id": "request-p0-09-reordered-raw",
            "object_inputs": [
                item.model_copy(update={"sha256": new_checksum})
                if item.input_id == bundle_ref.input_id
                else item
                for item in request.object_inputs
            ],
        }
    )
    second = adapter.run(second_request, _spec())
    assert second.execution_state is ExecutionState.SUCCEEDED
    assert second.run_id == first.run_id
    manifest = json.loads(
        ((second.request.output_dir / second.run_id) / "artifact_manifest.json").read_text()
    )
    assert all("semantic_sha256" in item and "sha256" not in item for item in manifest["structured_inputs"])


@pytest.mark.parametrize(
    "unsafe",
    [
        "/data" + "1/private/server/catalog.json",
        "~/private/input.json",
        "file:///" + "Users/private/input.json",
        "$HOME/private.json",
        "%USERPROFILE%\\private.json",
        "token=gh" + "p_abcdefghijklmnopqrstuvwxyz",
        "?api_key=sk-abcdefghijklmnopqrstuvwxyz",
        "Bearer abcdefghijklmnopqrstuvwxyz",
    ],
)
def test_unsafe_top_level_registry_references_fail_without_echo_or_artifacts(
    tmp_path: Path, unsafe: str
) -> None:
    family_registry = _family_registry()
    family_registry["families"][0]["known_dependencies"] = [unsafe]
    request = _request(tmp_path, family_registry=family_registry)
    run = adapter.run(request, _spec())
    assert run.execution_state is ExecutionState.FAILED
    assert run.artifacts == [] and run.result is None
    assert run.reason_codes == ["unsafe_structured_input_reference"]
    assert unsafe not in json.dumps(run.model_dump(mode="json"))


def test_all_seven_queries_are_bounded_deterministic_and_read_only(tmp_path: Path) -> None:
    run = _run(tmp_path)
    final = run.request.output_dir / run.run_id
    manifest = final / "case_evidence_graph_manifest.json"
    before = {item.name: hashlib.sha256(item.read_bytes()).hexdigest() for item in final.iterdir()}
    queries = EvidenceGraphQueries.open(manifest)
    record_payload = json.loads((final / "evidence_records.json").read_text())
    assert queries.evidence_record_set.model_dump(mode="json") == record_payload
    record = record_payload["records"][0]
    calls = [
        queries.get_claim_evidence(claim_id="claim:target-identity"),
        queries.trace_evidence_provenance(
            evidence_ref=f"{record['evidence_id']}@{record['evidence_version']}"
        ),
        queries.get_conflicting_evidence(claim_id="claim:target-identity"),
        queries.get_missing_requirements(claim_id="claim:target-identity"),
        queries.get_evidence_family_members(
            evidence_family_id="evidence-family:transcriptomic"
        ),
        queries.get_case_evidence_subgraph(product_case_id="product-case:synthetic-001"),
        queries.compare_evidence_paths(
            comparison_id="comparison:forbidden", domain_id=P0DomainId.TARGET_IDENTITY
        ),
    ]
    assert [item.query_name for item in calls] == [
        "get_claim_evidence",
        "trace_evidence_provenance",
        "get_conflicting_evidence",
        "get_missing_requirements",
        "get_evidence_family_members",
        "get_case_evidence_subgraph",
        "compare_evidence_paths",
    ]
    assert calls[-1].reason_codes == ["graph_kind_mismatch"]
    invalid = queries.get_claim_evidence(claim_id="MATCH (n) DELETE n", limit=201)
    assert invalid.reason_codes == ["query_parameter_invalid"]
    public_methods = {
        name
        for name, value in inspect.getmembers(EvidenceGraphQueries, inspect.isfunction)
        if not name.startswith("_") and name != "open"
    }
    assert public_methods == {
        "get_claim_evidence",
        "trace_evidence_provenance",
        "get_conflicting_evidence",
        "get_missing_requirements",
        "get_evidence_family_members",
        "get_case_evidence_subgraph",
        "compare_evidence_paths",
    }
    after = {item.name: hashlib.sha256(item.read_bytes()).hexdigest() for item in final.iterdir()}
    assert before == after


def test_comparison_graph_uses_external_refs_and_separate_manifest(tmp_path: Path) -> None:
    profiles = [
        (
            "profile-a",
            _profile(
                profile_id="evidence-sufficiency-profile:aaaaaaaaaaaaaaaa:target_identity",
                product_case_ref="product-case:case-a",
            ),
        ),
        (
            "profile-b",
            _profile(
                profile_id="evidence-sufficiency-profile:bbbbbbbbbbbbbbbb:target_identity",
                product_case_ref="product-case:case-b",
            )
            | {"deterministic_run_ref": "run-bbbbbbbbbbbbbbbb"},
        ),
    ]
    run = _run(
        tmp_path,
        bundle=_comparison_bundle(),
        profiles=profiles,
        claim_registry=_comparison_claim_registry(),
    )
    assert run.execution_state is ExecutionState.SUCCEEDED
    final = run.request.output_dir / run.run_id
    assert (final / "comparison_evidence_graph_manifest.json").is_file()
    assert not (final / "case_evidence_graph_manifest.json").exists()
    queries = EvidenceGraphQueries.open(final / "comparison_evidence_graph_manifest.json")
    result = queries.compare_evidence_paths(
        comparison_id="comparison:case-a-vs-b",
        claim_id="claim:comparison",
    )
    external_evidence = [
        item
        for item in result.nodes
        if item["node_type"] == "EvidenceRecord" and item["record_mode"] == "external_ref"
    ]
    assert len(external_evidence) == 2
    assert all(item["properties"] == {} for item in external_evidence)
    assert "source_case_graph_required" in result.reason_codes


def test_dangling_comparison_provenance_is_partial_and_absent_from_graph(tmp_path: Path) -> None:
    profiles = [
        (
            "profile-a",
            _profile(
                profile_id="evidence-sufficiency-profile:aaaaaaaaaaaaaaaa:target_identity",
                product_case_ref="product-case:case-a",
            ),
        ),
        (
            "profile-b",
            _profile(
                profile_id="evidence-sufficiency-profile:bbbbbbbbbbbbbbbb:target_identity",
                product_case_ref="product-case:case-b",
            )
            | {"deterministic_run_ref": "run-bbbbbbbbbbbbbbbb"},
        ),
    ]
    run = _run(
        tmp_path,
        bundle=_comparison_bundle(dangling=True),
        profiles=profiles,
        claim_registry=_comparison_claim_registry(),
    )
    assert run.execution_state is ExecutionState.PARTIAL
    final = run.request.output_dir / run.run_id
    rejected = json.loads((final / "rejected_records.json").read_text())["records"]
    assert rejected[0]["source_kind"] == "external_case_evidence_ref"
    assert "declared_object_ref_not_found" in rejected[0]["reason_codes"]
    queries = EvidenceGraphQueries.open(final / "comparison_evidence_graph_manifest.json")
    result = queries.compare_evidence_paths(
        comparison_id="comparison:case-a-vs-b",
        claim_id="claim:comparison",
    )
    external = [
        item
        for item in result.nodes
        if item["node_type"] == "EvidenceRecord" and item["record_mode"] == "external_ref"
    ]
    assert len(external) == 1


def test_strict_json_duplicate_key_and_checksum_fail_without_publication(tmp_path: Path) -> None:
    request = _request(tmp_path)
    bundle_ref = next(item for item in request.object_inputs if item.role == "compilation_bundle")
    bundle_ref.path.write_text('{"bundle_id":"one","bundle_id":"two"}', encoding="utf-8")
    request = request.model_copy(
        update={
            "object_inputs": [
                item.model_copy(
                    update={"sha256": hashlib.sha256(item.path.read_bytes()).hexdigest()}
                )
                if item.input_id == bundle_ref.input_id
                else item
                for item in request.object_inputs
            ]
        }
    )
    run = adapter.run(request, _spec())
    assert run.execution_state is ExecutionState.FAILED
    assert run.result is None and run.artifacts == []
    assert "structured_input_json_invalid" in run.reason_codes
    assert not request.output_dir.exists()


def test_existing_file_at_output_dir_returns_typed_failure_without_overwrite(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path)
    request.output_dir.write_text("preserve-me", encoding="utf-8")

    run = adapter.run(request, _spec())

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["artifact_checksum_verification_failed"]
    assert run.result is None and run.artifacts == []
    assert request.output_dir.read_text(encoding="utf-8") == "preserve-me"


def test_output_parent_with_hive_partition_basename_is_valid(tmp_path: Path) -> None:
    run = _run(tmp_path / "batch=one")

    assert run.request.output_dir.parent.name == "batch=one"
    assert run.execution_state is ExecutionState.SUCCEEDED
    manifest_path = (
        run.request.output_dir / run.run_id / "case_evidence_graph_manifest.json"
    )
    EvidenceGraphQueries.open(manifest_path)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("numerator", "75"),
        ("denominator", "100"),
        ("numerator", True),
        ("denominator", True),
        ("interval.lower", "0.65"),
        ("interval.lower", True),
        ("interval.confidence_level", "0.95"),
        ("interval.confidence_level", True),
    ],
)
def test_candidate_scientific_numbers_do_not_coerce_strings_or_booleans(
    tmp_path: Path, field: str, value: Any
) -> None:
    candidate = _candidate()
    target = candidate
    parts = field.split(".")
    for part in parts[:-1]:
        target = target[part]
    target[parts[-1]] = value

    with pytest.raises(ValueError):
        EvidenceCandidate.model_validate(candidate)

    run = _run(tmp_path, bundle=_bundle(candidates=[candidate]))
    assert run.execution_state is ExecutionState.PARTIAL
    final = run.request.output_dir / run.run_id
    assert json.loads((final / "evidence_records.json").read_text())["records"] == []
    rejected = json.loads((final / "rejected_records.json").read_text())["records"]
    assert set(rejected[0]["reason_codes"]) <= {
        "individual_record_schema_invalid",
        "invalid_denominator",
    }
    assert rejected[0]["reason_codes"]


@pytest.mark.parametrize(
    "payload",
    [
        {"lower": float("nan"), "upper": 1.0},
        {"lower": 0.0, "upper": float("inf")},
        {"lower": 0.0, "upper": 1.0, "confidence_level": float("nan")},
    ],
)
def test_interval_rejects_nonfinite_numbers_directly(payload: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        EvidenceInterval.model_validate(payload)


@pytest.mark.parametrize("constant", ["NaN", "Infinity"])
def test_public_json_rejects_nonfinite_candidate_numbers_without_publication(
    tmp_path: Path, constant: str
) -> None:
    request = _request(tmp_path)
    bundle_ref = next(
        item for item in request.object_inputs if item.role == "compilation_bundle"
    )
    raw = bundle_ref.path.read_text()
    raw = raw.replace('"numerator": 75', f'"numerator": {constant}', 1)
    bundle_ref.path.write_text(raw, encoding="utf-8")
    checksum = hashlib.sha256(bundle_ref.path.read_bytes()).hexdigest()
    request = request.model_copy(
        update={
            "object_inputs": [
                item.model_copy(update={"sha256": checksum})
                if item.input_id == bundle_ref.input_id
                else item
                for item in request.object_inputs
            ]
        }
    )

    run = adapter.run(request, _spec())

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["structured_input_json_invalid"]
    assert run.result is None and run.artifacts == []
    assert not request.output_dir.exists()


def test_public_integer_and_boolean_fields_are_strict() -> None:
    with pytest.raises(ValueError):
        BaseGraphRef.model_validate(
            {"graph_id": "case-evidence-graph:test", "graph_version": "1", "manifest_sha256": SHA}
        )
    with pytest.raises(ValueError):
        ClaimRequirementSpec.model_validate(
            {
                "requirement_key": "orthogonal",
                "channel_role": "orthogonal",
                "blocking_scope": "claim",
                "required": "false",
            }
        )
    with pytest.raises(ValueError):
        GraphArtifactRef.model_validate(
            {
                "filename": "graph_nodes.parquet",
                "media_type": "application/vnd.apache.parquet",
                "sha256": SHA,
                "row_count": 1.0,
            }
        )
    spec = _reconciliation_registry()["specs"][0]
    spec["minimum_independent_families_by_role"]["transcriptomic"] = "1"
    with pytest.raises(ValueError):
        ReconciliationSpec.model_validate(spec)


def test_v1_adapter_invocation_has_one_stable_v2_reason(tmp_path: Path) -> None:
    request = ToolRequest(
        request_id="p0-09-v1",
        tool_id="P0-09",
        tool_version="0.4.1",
        output_dir=(tmp_path / "output").resolve(),
    )
    eligibility = adapter.check_eligibility(request, _spec())  # type: ignore[arg-type]

    assert eligibility.eligible is False
    assert eligibility.reason_codes == ["tool_request_v2_required"]


@pytest.mark.parametrize(
    "unsafe",
    [
        "file:opaque-reference",
        "~alice/private/input.json",
        "$USERPROFILE/private/input.json",
        "HOMEPATH=/private/input.json",
        "accessToken:credential-value",
        "clientSecret=credential-value",
        "apiKey:credential-value",
        "accountPin:credential-value",
    ],
)
def test_bounded_publication_guard_covers_path_and_camel_credential_forms(
    tmp_path: Path, unsafe: str
) -> None:
    family_registry = _family_registry()
    family_registry["families"][0]["known_dependencies"] = [unsafe]
    request = _request(tmp_path, family_registry=family_registry)

    run = adapter.run(request, _spec())

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["unsafe_structured_input_reference"]
    assert run.result is None and run.artifacts == []
    assert unsafe not in json.dumps(run.model_dump(mode="json"))
    assert not request.output_dir.exists()


@pytest.mark.parametrize(
    "safe_ref",
    [
        "tokenizationState:biological-state",
        "secretedFactor:biological-state",
        "publicKey:reference123",
        "signalingKey:biological-state",
        "cellPin:biological-state",
        "databasePasswordPolicy:policy-state",
    ],
)
def test_publication_guard_does_not_reject_scientific_substrings(
    tmp_path: Path, safe_ref: str
) -> None:
    family_registry = _family_registry()
    family_registry["families"][0]["known_dependencies"] = [safe_ref]

    run = _run(tmp_path, family_registry=family_registry)

    assert run.execution_state is ExecutionState.SUCCEEDED


@pytest.mark.parametrize("role", ["bundle", "profile", "registry"])
def test_top_level_publication_surfaces_fail_as_a_whole(
    tmp_path: Path, role: str
) -> None:
    unsafe = "file:opaque-private-reference"
    bundle = _bundle()
    profile = _profile()
    registry = _family_registry()
    if role == "bundle":
        bundle["provenance_refs"] = [unsafe]
    elif role == "profile":
        profile["validation_refs"] = [unsafe]
    else:
        registry["families"][0]["known_dependencies"] = [unsafe]
    request = _request(
        tmp_path,
        bundle=bundle,
        profile=profile,
        family_registry=registry,
    )

    run = adapter.run(request, _spec())

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["unsafe_structured_input_reference"]
    assert unsafe not in json.dumps(run.model_dump(mode="json"))
    assert not request.output_dir.exists()


def test_unsafe_missing_and_external_entries_are_isolated_without_echo(
    tmp_path: Path,
) -> None:
    unsafe = "clientSecret=credential-value"
    missing = _missing_observation()
    missing["provenance_refs"] = [unsafe]
    case_run = _run(
        tmp_path / "case",
        bundle=_bundle(missing=[missing]),
        family_registry=_family_registry(second_family=True),
        claim_registry=_claim_registry(orthogonal_required=True),
        reconciliation_registry=_reconciliation_registry(orthogonal_required=True),
    )
    assert case_run.execution_state is ExecutionState.PARTIAL
    case_final = case_run.request.output_dir / case_run.run_id
    case_rejected = (case_final / "rejected_records.json").read_text()
    assert "individual_record_schema_invalid" in case_rejected
    assert unsafe not in case_rejected

    comparison = _comparison_bundle()
    comparison["external_case_evidence_refs"][1]["clientSecret"] = "credential-value"
    comparison_run = _run(
        tmp_path / "comparison",
        bundle=comparison,
        profiles=_comparison_profiles(),
        claim_registry=_comparison_claim_registry(),
    )
    assert comparison_run.execution_state is ExecutionState.PARTIAL
    comparison_final = comparison_run.request.output_dir / comparison_run.run_id
    external_rejected = (comparison_final / "rejected_records.json").read_text()
    assert "individual_record_schema_invalid" in external_rejected
    assert "credential-value" not in external_rejected


def test_boolean_value_is_not_accepted_as_numeric_evidence(tmp_path: Path) -> None:
    run = _run(tmp_path, bundle=_bundle(candidates=[_candidate(value=True)]))

    assert run.execution_state is ExecutionState.PARTIAL
    final = run.request.output_dir / run.run_id
    assert json.loads((final / "evidence_records.json").read_text())["records"] == []
    rejected = json.loads((final / "rejected_records.json").read_text())["records"]
    assert rejected[0]["reason_codes"] == ["individual_record_schema_invalid"]


@pytest.mark.parametrize("tamper", ["requirement_id", "content_hash"])
def test_prior_requirement_identity_and_content_are_recomputed(
    tmp_path: Path, tamper: str
) -> None:
    first = _run(tmp_path / "first")
    first_dir = first.request.output_dir / first.run_id
    prior_records = json.loads((first_dir / "evidence_records.json").read_text())["records"]
    prior_requirements = json.loads(
        (first_dir / "evidence_requirements.json").read_text()
    )["requirements"]
    prior_requirements[0][tamper] = (
        "requirement:" + "f" * 24 if tamper == "requirement_id" else "f" * 64
    )
    manifest_path = first_dir / "case_evidence_graph_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    bundle = _bundle(
        candidates=[_candidate()],
        prior_records=prior_records,
        prior_requirements=prior_requirements,
        base_graph_ref={
            "graph_id": manifest["graph_id"],
            "graph_version": manifest["graph_version"],
            "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        },
    )
    request = _request(tmp_path / "tampered", bundle=bundle)

    run = adapter.run(request, _spec())

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["prior_history_invalid"]
    assert run.result is None and run.artifacts == []
    assert not request.output_dir.exists()


def test_requirement_content_change_appends_even_when_state_stays_open(
    tmp_path: Path,
) -> None:
    shadow = _candidate(tier="shadow")
    first = _run(tmp_path / "first", bundle=_bundle(candidates=[shadow]))
    first_dir = first.request.output_dir / first.run_id
    prior_records = json.loads((first_dir / "evidence_records.json").read_text())["records"]
    prior_requirements = json.loads(
        (first_dir / "evidence_requirements.json").read_text()
    )["requirements"]
    assert prior_requirements[-1]["state"] == "open"
    assert prior_requirements[-1]["reason_codes"] == ["required_evidence_missing"]
    observation = _missing_observation()
    observation.update(
        {
            "observation_id": "missing-evidence:transcriptomic",
            "requirement_key": "transcriptomic_channel",
            "reason_code": "measurement_unavailable",
        }
    )
    manifest_path = first_dir / "case_evidence_graph_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    bundle = _bundle(
        candidates=[shadow],
        missing=[observation],
        prior_records=prior_records,
        prior_requirements=prior_requirements,
        base_graph_ref={
            "graph_id": manifest["graph_id"],
            "graph_version": manifest["graph_version"],
            "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        },
    )

    second = _run(
        tmp_path / "second",
        bundle=bundle,
        base_manifest_path=manifest_path,
    )

    assert second.execution_state is ExecutionState.SUCCEEDED
    requirements = json.loads(
        (
            second.request.output_dir
            / second.run_id
            / "evidence_requirements.json"
        ).read_text()
    )["requirements"]
    assert [item["requirement_version"] for item in requirements] == [1, 2]
    assert requirements[1]["state"] == "open"
    assert requirements[1]["reason_codes"] == ["measurement_unavailable"]
    assert requirements[1]["supersedes_requirement_ref"].endswith("@1")


def test_public_output_bound_refs_are_preflighted_before_publication(tmp_path: Path) -> None:
    claims = _claim_registry()
    claims["claims"][0]["claim_target_ref"] = "free form target ref"
    request = _request(tmp_path, claim_registry=claims)

    run = adapter.run(request, _spec())

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["structured_input_schema_invalid"]
    assert run.result is None and run.artifacts == []
    assert not request.output_dir.exists()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("filename", "../graph_nodes.parquet"),
        ("filename", "/tmp/graph_nodes.parquet"),
        ("row_count", 999999),
    ],
)
def test_query_open_rejects_manifest_path_traversal_and_row_count_drift(
    tmp_path: Path, field: str, value: Any
) -> None:
    run = _run(tmp_path)
    manifest_path = (
        run.request.output_dir / run.run_id / "case_evidence_graph_manifest.json"
    )
    payload = json.loads(manifest_path.read_text())
    payload["graph_nodes"][field] = value
    _write(manifest_path, payload)

    with pytest.raises(ValueError, match="manifest_integrity_failed"):
        EvidenceGraphQueries.open(manifest_path)


def test_query_open_rejects_symlinked_artifact_even_with_matching_bytes(
    tmp_path: Path,
) -> None:
    run = _run(tmp_path)
    final = run.request.output_dir / run.run_id
    nodes = final / "graph_nodes.parquet"
    target = tmp_path / "same-nodes.parquet"
    target.write_bytes(nodes.read_bytes())
    nodes.unlink()
    nodes.symlink_to(target)

    with pytest.raises(ValueError, match="manifest_integrity_failed"):
        EvidenceGraphQueries.open(final / "case_evidence_graph_manifest.json")


@pytest.mark.parametrize("explicit_zero", [False, True])
def test_query_open_rejects_object_count_type_substitution_with_same_total(
    tmp_path: Path, explicit_zero: bool
) -> None:
    run = _run(tmp_path)
    manifest_path = (
        run.request.output_dir / run.run_id / "case_evidence_graph_manifest.json"
    )
    payload = json.loads(manifest_path.read_text())
    if explicit_zero:
        payload["object_counts"]["Claim"] = 0
        payload["object_counts"]["Artifact"] = 1
    else:
        assert payload["object_counts"]["ReferenceSnapshot"] == 2
        payload["object_counts"]["ReferenceSnapshot"] = 1
        payload["object_counts"]["Artifact"] = 1
    _write(manifest_path, payload)

    with pytest.raises(ValueError, match="manifest_integrity_failed"):
        EvidenceGraphQueries.open(manifest_path)


def test_query_open_rejects_rehashed_parquet_with_forged_edge_self_hash(
    tmp_path: Path,
) -> None:
    run = _run(tmp_path)
    final = run.request.output_dir / run.run_id
    manifest_path = final / "case_evidence_graph_manifest.json"
    payload = json.loads(manifest_path.read_text())
    nodes_path = final / payload["graph_nodes"]["filename"]
    edges_path = final / payload["graph_edges"]["filename"]
    nodes, edges = read_parquet_rows(nodes_path, edges_path)
    edges[0] = edges[0].model_copy(update={"content_hash": "f" * 64})
    write_parquet(nodes_path, edges_path, nodes, edges)
    payload["graph_edges"]["sha256"] = hashlib.sha256(
        edges_path.read_bytes()
    ).hexdigest()
    _write(manifest_path, payload)

    with pytest.raises(ValueError, match="manifest_integrity_failed"):
        EvidenceGraphQueries.open(manifest_path)


@pytest.mark.parametrize("tamper", ["node_id", "owned_properties_hash"])
def test_query_open_rejects_forged_node_self_description(
    tmp_path: Path, tamper: str
) -> None:
    run = _run(tmp_path)
    final = run.request.output_dir / run.run_id
    manifest_path = final / "case_evidence_graph_manifest.json"
    payload = json.loads(manifest_path.read_text())
    nodes_path = final / payload["graph_nodes"]["filename"]
    edges_path = final / payload["graph_edges"]["filename"]
    nodes, edges = read_parquet_rows(nodes_path, edges_path)
    claim_index = next(
        index
        for index, node in enumerate(nodes)
        if node.node_type is GraphNodeType.CLAIM
    )
    claim = nodes[claim_index]
    if tamper == "owned_properties_hash":
        nodes[claim_index] = claim.model_copy(update={"content_hash": "f" * 64})
    else:
        forged_id = "node:Claim:" + "f" * 24
        nodes[claim_index] = claim.model_copy(update={"node_id": forged_id})
        edges = [
            edge.model_copy(
                update={
                    "source_node_id": (
                        forged_id if edge.source_node_id == claim.node_id else edge.source_node_id
                    ),
                    "target_node_id": (
                        forged_id if edge.target_node_id == claim.node_id else edge.target_node_id
                    ),
                }
            )
            for edge in edges
        ]
        # Keep every edge internally self-consistent so only the forged node identity
        # distinguishes this graph from a valid projection.
        repaired_edges = []
        for edge in edges:
            properties_hash = hashlib.sha256(
                edge.properties_json.encode("utf-8")
            ).hexdigest()
            identity = (
                f"{edge.graph_id}|{edge.edge_type.value}|{edge.source_node_id}|"
                f"{edge.target_node_id}|{properties_hash}"
            )
            digest = hashlib.sha256(identity.encode()).hexdigest()
            repaired_edges.append(
                edge.model_copy(
                    update={
                        "edge_id": f"edge:{digest[:24]}",
                        "content_hash": digest,
                    }
                )
            )
        edges = repaired_edges
    write_parquet(nodes_path, edges_path, nodes, edges)
    payload["graph_nodes"]["sha256"] = hashlib.sha256(
        nodes_path.read_bytes()
    ).hexdigest()
    payload["graph_edges"]["sha256"] = hashlib.sha256(
        edges_path.read_bytes()
    ).hexdigest()
    _write(manifest_path, payload)

    with pytest.raises(ValueError, match="manifest_integrity_failed"):
        EvidenceGraphQueries.open(manifest_path)


@pytest.mark.parametrize(
    "field",
    ["manifest_sha256", "graph_id", "graph_version", "product_case_ref"],
)
def test_comparison_manifest_external_nodes_are_bound_to_declared_case_manifests(
    tmp_path: Path, field: str
) -> None:
    run = _run(
        tmp_path,
        bundle=_comparison_bundle(),
        profiles=_comparison_profiles(),
        claim_registry=_comparison_claim_registry(),
    )
    manifest_path = (
        run.request.output_dir / run.run_id / "comparison_evidence_graph_manifest.json"
    )
    payload = json.loads(manifest_path.read_text())
    if field == "manifest_sha256":
        payload["case_graph_refs"][0][field] = "f" * 64
    elif field == "graph_id":
        payload["case_graph_refs"][0][field] = "case-evidence-graph:ffffffffffffffffffffffff"
    elif field == "graph_version":
        payload["case_graph_refs"][0][field] = 2
    else:
        payload["case_graph_refs"][0][field] = {
            "object_id": "product-case:different",
            "object_version": "1.0.0",
        }
    _write(manifest_path, payload)

    with pytest.raises(ValueError, match="manifest_integrity_failed"):
        EvidenceGraphQueries.open(manifest_path)


def test_external_source_manifest_mismatch_is_partial_and_not_projected(
    tmp_path: Path,
) -> None:
    bundle = json.loads(json.dumps(_comparison_bundle()))
    bundle["external_case_evidence_refs"][1]["source_case_graph_ref"][
        "manifest_sha256"
    ] = "f" * 64
    run = _run(
        tmp_path,
        bundle=bundle,
        profiles=_comparison_profiles(),
        claim_registry=_comparison_claim_registry(),
    )

    assert run.execution_state is ExecutionState.PARTIAL
    final = run.request.output_dir / run.run_id
    rejected = json.loads((final / "rejected_records.json").read_text())["records"]
    assert rejected[0]["reason_codes"] == ["declared_object_ref_not_found"]
    projected = EvidenceGraphQueries.open(
        final / "comparison_evidence_graph_manifest.json"
    ).compare_evidence_paths(
        comparison_id="comparison:case-a-vs-b", claim_id="claim:comparison"
    )
    assert sum(
        node["node_type"] == "EvidenceRecord"
        and node["record_mode"] == "external_ref"
        for node in projected.nodes
    ) == 1


def test_exact_query_node_cap_does_not_claim_truncation_without_omissions(
    tmp_path: Path,
) -> None:
    run = _run(tmp_path)
    query = EvidenceGraphQueries.open(
        run.request.output_dir / run.run_id / "case_evidence_graph_manifest.json"
    )
    complete = query.get_case_evidence_subgraph(
        product_case_id="product-case:synthetic-001", max_depth=6, max_nodes=500
    )
    assert complete.truncated is False
    exact = query.get_case_evidence_subgraph(
        product_case_id="product-case:synthetic-001",
        max_depth=6,
        max_nodes=complete.returned_node_count,
    )

    assert exact.returned_node_count == complete.returned_node_count
    assert exact.truncated is False
    assert exact.omitted_node_count == 0 and exact.omitted_edge_count == 0


def test_artifact_manifest_records_and_verifies_available_file_sizes(tmp_path: Path) -> None:
    run = _run(tmp_path)
    final = run.request.output_dir / run.run_id
    manifest = json.loads((final / "artifact_manifest.json").read_text())

    assert all(
        item["size_bytes"] == (final / item["filename"]).stat().st_size
        for item in manifest["artifacts"]
    )


def test_prior_history_from_another_product_case_fails_without_artifacts(
    tmp_path: Path,
) -> None:
    first = _run(tmp_path / "case-a")
    first_dir = first.request.output_dir / first.run_id
    prior_records = json.loads((first_dir / "evidence_records.json").read_text())["records"]
    prior_requirements = json.loads(
        (first_dir / "evidence_requirements.json").read_text()
    )["requirements"]
    product_b = {
        "object_id": "product-case:synthetic-002",
        "object_version": "1.0.0",
    }
    bundle = _bundle(
        candidates=[],
        prior_records=prior_records,
        prior_requirements=prior_requirements,
        base_graph_ref={
            "graph_id": "case-evidence-graph:"
            + hashlib.sha256(b"case|product-case:synthetic-002@1.0.0").hexdigest()[:24],
            "graph_version": 1,
            "manifest_sha256": "f" * 64,
        },
    )
    bundle["product_case_ref"] = product_b
    bundle["object_catalog"][0]["object_id"] = product_b["object_id"]
    profile = _profile(product_case_ref=product_b["object_id"])
    request = _request(tmp_path / "case-b", bundle=bundle, profile=profile)

    run = adapter.run(request, _spec())

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["prior_history_invalid"]
    assert run.result is None and run.artifacts == []
    assert not request.output_dir.exists()


@pytest.mark.parametrize("schema_version", ["v0.2", "v9.9"])
@pytest.mark.parametrize("schema_name", ["measurement-spec", "measurement-result", "tool-run"])
def test_catalog_checks_supported_upstream_schema_versions(
    tmp_path: Path, schema_name: str, schema_version: str
) -> None:
    bundle = _bundle()
    catalog_entry = next(
        item for item in bundle["object_catalog"]
        if item["schema_ref"] == f"bridge://schemas/{schema_name}/v0.1"
    )
    catalog_entry["schema_ref"] = f"bridge://schemas/{schema_name}/{schema_version}"

    run = _run(tmp_path, bundle=bundle)
    final = run.request.output_dir / run.run_id
    records = json.loads((final / "evidence_records.json").read_text())["records"]
    rejected = json.loads((final / "rejected_records.json").read_text())["records"]
    if schema_version == "v0.2":
        assert len(records) == 1
        assert rejected == []
    else:
        assert records == []
        assert rejected[0]["reason_codes"] == ["declared_object_ref_not_found"]


def test_versioned_data_view_provenance_is_preserved(tmp_path: Path) -> None:
    bundle = _bundle()
    reference = "data-view:run-example:all-observations@0.1.0"
    bundle["candidate_records"][0]["provenance_refs"] = [reference]

    run = _run(tmp_path, bundle=bundle)
    final = run.request.output_dir / run.run_id
    records = json.loads((final / "evidence_records.json").read_text())["records"]

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert records[0]["provenance_refs"] == [reference]


@pytest.mark.parametrize(
    "reference",
    [
        "data-view:example@",
        "data-view:example@0.1.0/extra",
        "data-view:example@0.1.0@other",
        "user@example.org",
        "data-view:example@/private/input",
        "data-view:example@sk-" + "a" * 24,
    ],
)
def test_versioned_provenance_keeps_strict_publication_guard(reference: str) -> None:
    with pytest.raises(ValueError):
        publication_ref(reference)


def test_catalog_node_role_confusion_rejects_only_the_candidate(tmp_path: Path) -> None:
    bundle = _bundle()
    measurement = next(
        item
        for item in bundle["object_catalog"]
        if item["object_id"] == "measurement-result:target"
    )
    measurement["node_type"] = "Artifact"
    measurement["schema_ref"] = "bridge://schemas/artifact/v0.1"

    run = _run(tmp_path, bundle=bundle)

    assert run.execution_state is ExecutionState.PARTIAL
    final = run.request.output_dir / run.run_id
    assert json.loads((final / "evidence_records.json").read_text())["records"] == []
    rejected = json.loads((final / "rejected_records.json").read_text())["records"]
    assert rejected[0]["reason_codes"] == ["declared_object_ref_not_found"]


def test_claim_context_requires_exact_versioned_candidate_context(tmp_path: Path) -> None:
    claims = _claim_registry()
    claims["claims"][0]["biological_context_ref"] = {
        "object_id": "context:synthetic",
        "object_version": "2.0.0",
    }

    run = _run(tmp_path, claim_registry=claims)

    assert run.execution_state is ExecutionState.PARTIAL
    final = run.request.output_dir / run.run_id
    rejected = json.loads((final / "rejected_records.json").read_text())["records"]
    assert rejected[0]["reason_codes"] == ["claim_context_mismatch"]


def test_formal_candidate_is_rejected_when_profile_cannot_bind_object_versions(
    tmp_path: Path,
) -> None:
    run = _run(tmp_path, bundle=_bundle(candidates=[_candidate(tier="formal")]))

    assert run.execution_state is ExecutionState.PARTIAL
    final = run.request.output_dir / run.run_id
    rejected = json.loads((final / "rejected_records.json").read_text())["records"]
    assert "sufficiency_profile_version_binding_unavailable" in rejected[0]["reason_codes"]
    assert json.loads((final / "evidence_records.json").read_text())["records"] == []


def test_base_graph_requires_content_addressed_manifest_and_facts(
    tmp_path: Path,
) -> None:
    first = _run(tmp_path / "first")
    first_dir = first.request.output_dir / first.run_id
    manifest_path = first_dir / "case_evidence_graph_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    prior_records = json.loads((first_dir / "evidence_records.json").read_text())["records"]
    prior_requirements = json.loads(
        (first_dir / "evidence_requirements.json").read_text()
    )["requirements"]
    bundle = _bundle(
        candidates=[_candidate()],
        prior_records=prior_records,
        prior_requirements=prior_requirements,
        base_graph_ref={
            "graph_id": manifest["graph_id"],
            "graph_version": manifest["graph_version"],
            "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        },
    )

    missing_source = _run(tmp_path / "missing-source", bundle=bundle)
    assert missing_source.execution_state is ExecutionState.FAILED
    assert missing_source.reason_codes == ["prior_history_invalid"]
    assert not missing_source.request.output_dir.exists()

    verified = _run(
        tmp_path / "verified",
        bundle=bundle,
        base_manifest_path=manifest_path,
    )
    assert verified.execution_state is ExecutionState.SUCCEEDED
    assert verified.result["graph_version"] == manifest["graph_version"] + 1


def test_base_graph_rejects_forged_manifest_checksum_and_version(tmp_path: Path) -> None:
    first = _run(tmp_path / "first")
    first_dir = first.request.output_dir / first.run_id
    manifest_path = first_dir / "case_evidence_graph_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    bundle = _bundle(
        candidates=[_candidate()],
        prior_records=json.loads((first_dir / "evidence_records.json").read_text())["records"],
        prior_requirements=json.loads(
            (first_dir / "evidence_requirements.json").read_text()
        )["requirements"],
        base_graph_ref={
            "graph_id": manifest["graph_id"],
            "graph_version": 99,
            "manifest_sha256": "f" * 64,
        },
    )

    run = _run(tmp_path / "forged", bundle=bundle, base_manifest_path=manifest_path)

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["prior_history_invalid"]
    assert not run.request.output_dir.exists()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("evidence_ref", "evidence:" + "f" * 24 + "@999"),
        ("evidence_content_hash", "f" * 64),
        (
            "source_claim_ref",
            {"object_id": "claim:case-b", "object_version": "1.0.0"},
        ),
    ],
)
def test_comparison_external_fact_must_exist_in_content_addressed_source_set(
    tmp_path: Path, field: str, value: Any
) -> None:
    bundle = _comparison_bundle()
    bundle["external_case_evidence_refs"][0][field] = value

    run = _run(
        tmp_path,
        bundle=bundle,
        profiles=_comparison_profiles(),
        claim_registry=_comparison_claim_registry(),
    )

    assert run.execution_state is ExecutionState.PARTIAL
    final = run.request.output_dir / run.run_id
    rejected = json.loads((final / "rejected_records.json").read_text())["records"]
    assert "external_evidence_claim_mapping_invalid" in rejected[0]["reason_codes"]
    graph = EvidenceGraphQueries.open(final / "comparison_evidence_graph_manifest.json")
    result = graph.compare_evidence_paths(
        comparison_id="comparison:case-a-vs-b", claim_id="claim:comparison"
    )
    assert sum(node["node_type"] == "EvidenceRecord" for node in result.nodes) == 1


def test_duplicate_evidence_identity_across_source_graphs_rejects_both_without_exception(
    tmp_path: Path,
) -> None:
    bundle = _comparison_bundle()
    duplicate_ref = "evidence:" + "f" * 24 + "@1"
    for item in bundle["external_case_evidence_refs"]:
        item["evidence_ref"] = duplicate_ref

    run = _run(
        tmp_path,
        bundle=bundle,
        profiles=_comparison_profiles(),
        claim_registry=_comparison_claim_registry(),
    )

    assert run.execution_state is ExecutionState.PARTIAL
    rejected = json.loads(
        (
            run.request.output_dir / run.run_id / "rejected_records.json"
        ).read_text()
    )["records"]
    assert len(rejected) == 2
    assert all("duplicate_logical_key_conflict" in item["reason_codes"] for item in rejected)
    assert all(set(item) <= {
        "source_kind", "source_id", "source_index", "reason_codes", "claim_ref", "logical_key_digest"
    } for item in rejected)


def test_identical_external_ref_duplicate_is_idempotent_and_byte_deterministic(
    tmp_path: Path,
) -> None:
    first_request = _request(
        tmp_path / "single",
        bundle=_comparison_bundle(),
        profiles=_comparison_profiles(),
        claim_registry=_comparison_claim_registry(),
    )
    first = adapter.run(first_request, _spec())
    assert first.execution_state is ExecutionState.SUCCEEDED
    first_dir = first.request.output_dir / first.run_id
    first_bytes = {item.name: item.read_bytes() for item in first_dir.iterdir()}

    duplicate_request = _request(
        tmp_path / "duplicate",
        bundle=_comparison_bundle(),
        profiles=_comparison_profiles(),
        claim_registry=_comparison_claim_registry(),
    )
    bundle_ref = next(
        item
        for item in duplicate_request.object_inputs
        if item.role == "compilation_bundle"
    )
    raw_bundle = json.loads(bundle_ref.path.read_text())
    raw_bundle["external_case_evidence_refs"].append(
        json.loads(json.dumps(raw_bundle["external_case_evidence_refs"][0]))
    )
    duplicate_sha = _write(bundle_ref.path, raw_bundle)
    duplicate_request = duplicate_request.model_copy(
        update={
            "object_inputs": [
                item.model_copy(update={"sha256": duplicate_sha})
                if item.input_id == bundle_ref.input_id
                else item
                for item in duplicate_request.object_inputs
            ]
        }
    )

    duplicate = adapter.run(duplicate_request, _spec())

    assert duplicate.execution_state is ExecutionState.SUCCEEDED
    assert duplicate.run_id == first.run_id
    assert duplicate.input_hash == first.input_hash
    duplicate_dir = duplicate.request.output_dir / duplicate.run_id
    assert {item.name: item.read_bytes() for item in duplicate_dir.iterdir()} == first_bytes


def test_same_external_logical_ref_with_different_content_is_not_deduplicated(
    tmp_path: Path,
) -> None:
    request = _request(
        tmp_path,
        bundle=_comparison_bundle(),
        profiles=_comparison_profiles(),
        claim_registry=_comparison_claim_registry(),
    )
    bundle_ref = next(
        item for item in request.object_inputs if item.role == "compilation_bundle"
    )
    raw_bundle = json.loads(bundle_ref.path.read_text())
    conflicting = json.loads(json.dumps(raw_bundle["external_case_evidence_refs"][0]))
    conflicting["evidence_content_hash"] = "f" * 64
    raw_bundle["external_case_evidence_refs"].append(conflicting)
    checksum = _write(bundle_ref.path, raw_bundle)
    request = request.model_copy(
        update={
            "object_inputs": [
                item.model_copy(update={"sha256": checksum})
                if item.input_id == bundle_ref.input_id
                else item
                for item in request.object_inputs
            ]
        }
    )

    run = adapter.run(request, _spec())

    assert run.execution_state is ExecutionState.PARTIAL
    final = run.request.output_dir / run.run_id
    rejected = json.loads((final / "rejected_records.json").read_text())["records"]
    conflict_rejections = [
        item
        for item in rejected
        if "duplicate_logical_key_conflict" in item["reason_codes"]
    ]
    assert len(conflict_rejections) == 2
    assert all("f" * 64 not in json.dumps(item) for item in rejected)


def test_source_graph_input_bindings_are_a_strict_bijection(tmp_path: Path) -> None:
    request = _request(
        tmp_path,
        bundle=_comparison_bundle(),
        profiles=_comparison_profiles(),
        claim_registry=_comparison_claim_registry(),
    )
    original = next(
        item
        for item in request.object_inputs
        if item.role == "source_case_evidence_record_set"
    )
    unused_path = (tmp_path / "unused-source-records.json").resolve()
    unused_path.write_bytes(original.path.read_bytes())
    unused = original.model_copy(
        update={"input_id": "source-records-unbound", "path": unused_path}
    )
    request = request.model_copy(
        update={"object_inputs": [*request.object_inputs, unused]}
    )

    run = adapter.run(request, _spec())

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["prior_history_invalid"]
    assert run.artifacts == [] and not request.output_dir.exists()


def test_source_graph_preflight_rejects_corrupt_authoritative_artifact(
    tmp_path: Path,
) -> None:
    profiles = _comparison_profiles()
    bundle, paths = _materialize_comparison_sources(
        tmp_path / "sources", _comparison_bundle(), profiles
    )
    (paths[0].parent / "reconciliation_records.json").write_text(
        '{"tampered":true}\n', encoding="utf-8"
    )

    run = _run(
        tmp_path / "run",
        bundle=bundle,
        profiles=profiles,
        claim_registry=_comparison_claim_registry(),
        source_case_manifest_paths=paths,
    )

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["prior_history_invalid"]
    assert run.artifacts == [] and not run.request.output_dir.exists()


@pytest.mark.parametrize("tamper", ["object_counts", "edge_self_hash"])
def test_source_graph_preflight_inherits_manifest_and_row_integrity_checks(
    tmp_path: Path, tamper: str
) -> None:
    profiles = _comparison_profiles()
    bundle, paths = _materialize_comparison_sources(
        tmp_path / "sources", _comparison_bundle(), profiles
    )
    manifest_path = paths[0]
    manifest = json.loads(manifest_path.read_text())
    if tamper == "object_counts":
        assert manifest["object_counts"].pop("ProductCase") == 1
        manifest["object_counts"]["Artifact"] = 1
    else:
        nodes_path = manifest_path.parent / manifest["graph_nodes"]["filename"]
        edges_path = manifest_path.parent / manifest["graph_edges"]["filename"]
        nodes, edges = read_parquet_rows(nodes_path, edges_path)
        edges[0] = edges[0].model_copy(update={"content_hash": "f" * 64})
        write_parquet(nodes_path, edges_path, nodes, edges)
        manifest["graph_edges"]["sha256"] = hashlib.sha256(
            edges_path.read_bytes()
        ).hexdigest()
    manifest_sha = _write(manifest_path, manifest)
    bundle["case_graph_refs"][0]["manifest_sha256"] = manifest_sha
    for external in bundle["external_case_evidence_refs"]:
        if (
            external["source_case_graph_ref"]["graph_id"]
            == bundle["case_graph_refs"][0]["graph_id"]
        ):
            external["source_case_graph_ref"]["manifest_sha256"] = manifest_sha

    run = _run(
        tmp_path / "run",
        bundle=bundle,
        profiles=profiles,
        claim_registry=_comparison_claim_registry(),
        source_case_manifest_paths=paths,
    )

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["prior_history_invalid"]
    assert run.artifacts == [] and not run.request.output_dir.exists()


def test_public_graph_manifests_do_not_expose_request_local_input_ids(
    tmp_path: Path,
) -> None:
    comparison = _run(
        tmp_path / "comparison",
        bundle=_comparison_bundle(),
        profiles=_comparison_profiles(),
        claim_registry=_comparison_claim_registry(),
    )
    comparison_manifest = (
        comparison.request.output_dir
        / comparison.run_id
        / "comparison_evidence_graph_manifest.json"
    ).read_text()
    assert "manifest_input_id" not in comparison_manifest
    assert "record_set_input_id" not in comparison_manifest

    first = _run(tmp_path / "first")
    first_root = first.request.output_dir / first.run_id
    first_manifest_path = first_root / "case_evidence_graph_manifest.json"
    first_manifest = json.loads(first_manifest_path.read_text())
    append = _run(
        tmp_path / "append",
        bundle=_bundle(
            candidates=[_candidate()],
            prior_records=json.loads((first_root / "evidence_records.json").read_text())[
                "records"
            ],
            prior_requirements=json.loads(
                (first_root / "evidence_requirements.json").read_text()
            )["requirements"],
            base_graph_ref={
                "graph_id": first_manifest["graph_id"],
                "graph_version": first_manifest["graph_version"],
                "manifest_sha256": hashlib.sha256(
                    first_manifest_path.read_bytes()
                ).hexdigest(),
            },
        ),
        base_manifest_path=first_manifest_path,
    )
    append_manifest = (
        append.request.output_dir / append.run_id / "case_evidence_graph_manifest.json"
    ).read_text()
    assert "manifest_input_id" not in append_manifest
    assert "record_set_input_id" not in append_manifest
    assert "requirement_set_input_id" not in append_manifest


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("candidate_records", [42]),
        ("missing_observations", ["not-an-object"]),
        ("external_case_evidence_refs", [42]),
    ],
)
def test_non_object_public_record_arrays_fail_top_level_schema_without_echo(
    tmp_path: Path, field: str, value: list[Any], capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = _comparison_bundle() if field == "external_case_evidence_refs" else _bundle()
    bundle[field] = value
    assert list(
        Draft202012Validator(
            EvidenceCompilationBundle.model_json_schema()
        ).iter_errors(bundle)
    )

    request = _request(
        tmp_path,
        bundle=bundle,
        profiles=_comparison_profiles() if field == "external_case_evidence_refs" else None,
        claim_registry=(
            _comparison_claim_registry()
            if field == "external_case_evidence_refs"
            else None
        ),
        source_case_manifest_paths=(
            [] if field == "external_case_evidence_refs" else None
        ),
    )
    run = adapter.run(request, _spec())

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["structured_input_schema_invalid"]
    assert run.artifacts == [] and not request.output_dir.exists()
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_external_ref_public_schema_is_strict_while_direct_adapter_isolates_object(
    tmp_path: Path,
) -> None:
    bundle = _comparison_bundle()
    bundle["external_case_evidence_refs"][0]["unexpected_field"] = "synthetic-value"
    schema = EvidenceCompilationBundle.model_json_schema()

    assert schema["properties"]["external_case_evidence_refs"]["items"] == {
        "$ref": "#/$defs/ExternalCaseEvidenceRef"
    }
    assert schema["$defs"]["ExternalCaseEvidenceRef"]["additionalProperties"] is False
    assert list(Draft202012Validator(schema).iter_errors(bundle))

    request_kwargs = {
        "bundle": bundle,
        "profiles": _comparison_profiles(),
        "claim_registry": _comparison_claim_registry(),
    }
    direct_request = _request(tmp_path / "direct", **request_kwargs)
    direct_run = adapter.run(direct_request, _spec())
    assert direct_run.execution_state is ExecutionState.PARTIAL
    rejected = (
        direct_run.request.output_dir
        / direct_run.run_id
        / "rejected_records.json"
    ).read_text()
    assert "individual_record_schema_invalid" in rejected
    assert "synthetic-value" not in rejected

    public_request = _request(tmp_path / "public", **request_kwargs)
    registry = ToolRegistry.load_default()
    public_eligibility = registry.check_eligibility(public_request)
    public_run = registry.run(public_request)
    assert public_eligibility.reason_codes == [
        "structured_input_schema_validation_failed"
    ]
    assert public_run.execution_state is ExecutionState.FAILED
    assert public_run.reason_codes == ["structured_input_schema_validation_failed"]
    assert not public_request.output_dir.exists()


def _reconciliation_evidence(family_ref: str, evidence_ref: str) -> ReconciliationEvidence:
    return ReconciliationEvidence(
        evidence_ref=evidence_ref,
        claim_ref="claim:target-identity@1.0.0",
        family_ref=family_ref,
        profile_input_id="profile-target",
        profile_ref=None,
        relation=EvidenceRelation.SUPPORTS,
        evidence_state=EvidenceState.MEASURED,
        evidence_tier=EvidenceTier.FORMAL,
        lifecycle_state=EvidenceLifecycleState.ACTIVE,
        applicability=EvidenceApplicability.APPLICABLE,
        tool_run_execution_state="succeeded",
    )


@pytest.mark.parametrize("dependency_mode", ["same_scope", "one_way", "transitive"])
def test_minimum_independent_families_uses_scope_and_symmetric_dependency_closure(
    dependency_mode: str,
) -> None:
    base = _family_registry()["families"][0]
    payloads = [
        {
            **base,
            "evidence_family_id": f"evidence-family:f{index}",
            "independence_scope": f"scope-{index}",
            "known_dependencies": [],
        }
        for index in range(3)
    ]
    if dependency_mode == "same_scope":
        payloads[1]["independence_scope"] = payloads[0]["independence_scope"]
        selected = payloads[:2]
    elif dependency_mode == "one_way":
        payloads[0]["known_dependencies"] = [payloads[1]["evidence_family_id"]]
        selected = payloads[:2]
    else:
        payloads[0]["known_dependencies"] = [payloads[1]["evidence_family_id"]]
        payloads[1]["known_dependencies"] = [payloads[2]["evidence_family_id"]]
        selected = payloads
    registry = EvidenceFamilyRegistry.model_validate(
        _family_registry() | {"families": selected}
    )
    families = {(item.evidence_family_id, item.version): item for item in registry.families}
    evidence = [
        _reconciliation_evidence(item.ref, f"evidence:{index + 1:024x}@1")
        for index, item in enumerate(registry.families)
    ]

    resolution, reasons = _resolve_channel(
        role="transcriptomic",
        evidence=evidence,
        families=families,
        minimum=2,
    )

    assert resolution.eligible is False
    assert "non_independent_families_deduplicated" in reasons


def test_cross_scope_dependency_free_families_count_as_independent() -> None:
    base = _family_registry()["families"][0]
    registry = EvidenceFamilyRegistry.model_validate(
        _family_registry()
        | {
            "families": [
                {
                    **base,
                    "evidence_family_id": f"evidence-family:f{index}",
                    "independence_scope": f"scope-{index}",
                    "known_dependencies": [],
                }
                for index in range(2)
            ]
        }
    )
    families = {(item.evidence_family_id, item.version): item for item in registry.families}
    resolution, reasons = _resolve_channel(
        role="transcriptomic",
        evidence=[
            _reconciliation_evidence(item.ref, f"evidence:{index + 1:024x}@1")
            for index, item in enumerate(registry.families)
        ],
        families=families,
        minimum=2,
    )

    assert resolution.eligible is True
    assert "non_independent_families_deduplicated" not in reasons


def test_direct_v1_run_returns_typed_v2_failure_without_exception(tmp_path: Path) -> None:
    request = ToolRequest(
        request_id="legacy-p0-09",
        tool_id="P0-09",
        output_dir=(tmp_path / "out").resolve(),
    )

    run = adapter.run(request, _spec())

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["tool_request_v2_required"]
    assert run.request.object_inputs == []
    assert run.result is None and run.artifacts == []


def test_missing_requirement_query_rejects_shadow_evidence_as_satisfaction(
    tmp_path: Path,
) -> None:
    first = _run(tmp_path / "first")
    first_dir = first.request.output_dir / first.run_id
    manifest_path = first_dir / "case_evidence_graph_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    prior_records = json.loads((first_dir / "evidence_records.json").read_text())["records"]
    prior_requirements = json.loads(
        (first_dir / "evidence_requirements.json").read_text()
    )["requirements"]
    formal = _candidate(tier="formal")
    second_bundle = _bundle(
        candidates=[formal],
        prior_records=prior_records,
        prior_requirements=prior_requirements,
        base_graph_ref={
            "graph_id": manifest["graph_id"],
            "graph_version": manifest["graph_version"],
            "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        },
    )
    # The current profile cannot authorize new formal evidence, so create a
    # legitimate satisfied v2 requirement directly from the immutable v1 facts
    # to exercise query history semantics.
    old = prior_requirements[0]
    satisfied = {
        **old,
        "requirement_version": 2,
        "state": "satisfied",
        "reason_codes": ["required_evidence_present"],
        "satisfying_evidence_refs": [prior_records[0]["evidence_id"] + "@1"],
        "supersedes_requirement_ref": old["requirement_id"] + "@1",
    }
    from bridge.tool_packages.p0_09_evidence_compiler.models import EvidenceRequirement
    from bridge.tool_packages.p0_09_evidence_compiler.compiler import requirement_content_hash

    parsed = EvidenceRequirement.model_validate(satisfied | {"content_hash": "0" * 64})
    satisfied["content_hash"] = requirement_content_hash(parsed)
    second_bundle["prior_requirements"] = [old, satisfied]
    second_bundle["candidate_records"] = []
    second_bundle["missing_observations"] = [
        {
            **_missing_observation(),
            "observation_id": "missing-evidence:transcriptomic-current",
            "requirement_key": "transcriptomic_channel",
            "reason_code": "required_experiment_not_performed",
        }
    ]
    # Append-only input history must exactly match the immutable base graph.
    # Therefore exercise the query's latest-version logic against a copied,
    # internally coherent graph projection rather than forging a base manifest.
    from bridge.tool_packages.p0_09_evidence_compiler.graph import read_parquet_rows

    query_copy = tmp_path / "query-history"
    query_copy.mkdir()
    for name in (
        "evidence_records.json",
        "reconciliation_records.json",
        "graph_nodes.parquet",
        "graph_edges.parquet",
    ):
        (query_copy / name).write_bytes((first_dir / name).read_bytes())
    requirement_set = json.loads((first_dir / "evidence_requirements.json").read_text())
    requirement_set["requirements"] = [old, satisfied]
    req_sha = _write(query_copy / "evidence_requirements.json", requirement_set)
    nodes, edges = read_parquet_rows(
        first_dir / "graph_nodes.parquet", first_dir / "graph_edges.parquet"
    )
    latest_nodes = [
        item
        for item in nodes
        if not (
            item.node_type is GraphNodeType.EVIDENCE_REQUIREMENT
            and item.object_id == old["requirement_id"]
        )
    ]
    removed_requirement_node_ids = {
        item.node_id
        for item in nodes
        if item.node_type is GraphNodeType.EVIDENCE_REQUIREMENT
        and item.object_id == old["requirement_id"]
    }
    edges = [
        item
        for item in edges
        if item.source_node_id not in removed_requirement_node_ids
        and item.target_node_id not in removed_requirement_node_ids
    ]
    for payload, lifecycle in ((old, "superseded"), (satisfied, "satisfied")):
        requirement_node_id = node_id(
            payload["requirement_id"],
            str(payload["requirement_version"]),
            GraphNodeType.EVIDENCE_REQUIREMENT,
        )
        latest_nodes.append(
            GraphNodeRow(
                graph_id=manifest["graph_id"],
                graph_version=manifest["graph_version"],
                node_id=requirement_node_id,
                node_type=GraphNodeType.EVIDENCE_REQUIREMENT,
                record_mode=GraphRecordMode.OWNED,
                object_id=payload["requirement_id"],
                object_version=str(payload["requirement_version"]),
                lifecycle_state=lifecycle,
                properties_json=canonical_json_bytes(payload).decode(),
                content_hash=payload["content_hash"],
            )
        )
        root_node_id = node_id(
            "product-case:synthetic-001", "1.0.0", GraphNodeType.PRODUCT_CASE
        )
        edge_identity = (
            f"{manifest['graph_id']}|applicable_to|{requirement_node_id}|"
            f"{root_node_id}|{hashlib.sha256(b'{}').hexdigest()}"
        )
        edges.append(
            GraphEdgeRow(
                graph_id=manifest["graph_id"],
                graph_version=manifest["graph_version"],
                edge_id="edge:" + hashlib.sha256(edge_identity.encode()).hexdigest()[:24],
                edge_type=GraphEdgeType.APPLICABLE_TO,
                source_node_id=requirement_node_id,
                target_node_id=root_node_id,
                properties_json="{}",
                content_hash=hashlib.sha256(edge_identity.encode()).hexdigest(),
            )
        )
    write_parquet(
        query_copy / "graph_nodes.parquet",
        query_copy / "graph_edges.parquet",
        latest_nodes,
        edges,
    )
    query_manifest = json.loads(manifest_path.read_text())
    query_manifest["evidence_requirements"]["sha256"] = req_sha
    query_manifest["graph_nodes"]["sha256"] = hashlib.sha256(
        (query_copy / "graph_nodes.parquet").read_bytes()
    ).hexdigest()
    query_manifest["graph_nodes"]["row_count"] = len(latest_nodes)
    query_manifest["graph_edges"]["sha256"] = hashlib.sha256(
        (query_copy / "graph_edges.parquet").read_bytes()
    ).hexdigest()
    query_manifest["graph_edges"]["row_count"] = len(edges)
    query_manifest["node_count"] = len(latest_nodes)
    query_manifest["edge_count"] = len(edges)
    query_manifest["object_counts"]["EvidenceRequirement"] = 2
    query_manifest_path = query_copy / "case_evidence_graph_manifest.json"
    _write(query_manifest_path, query_manifest)

    with pytest.raises(ValueError, match="manifest_integrity_failed"):
        EvidenceGraphQueries.open(query_manifest_path)
    return

    second = _run(
        tmp_path / "second",
        bundle=second_bundle,
        base_manifest_path=copied_manifest_path,
    )
    assert second.execution_state is ExecutionState.SUCCEEDED
    query = EvidenceGraphQueries.open(
        second.request.output_dir / second.run_id / "case_evidence_graph_manifest.json"
    )

    current_open = query.get_missing_requirements(
        product_case_id="product-case:synthetic-001",
        state=EvidenceRequirementState.OPEN,
    )
    current_satisfied = query.get_missing_requirements(
        product_case_id="product-case:synthetic-001",
        state=EvidenceRequirementState.SATISFIED,
    )
    assert sum(
        node["node_type"] == "EvidenceRequirement" for node in current_open.nodes
    ) == 1
    assert not any(
        node["node_type"] == "EvidenceRequirement" for node in current_satisfied.nodes
    )
    latest_open = next(
        node for node in current_open.nodes if node["node_type"] == "EvidenceRequirement"
    )
    assert latest_open["object_version"] == "3"


@pytest.mark.parametrize(
    ("query_name", "kwargs"),
    [
        ("get_claim_evidence", {"claim_id": 7}),
        ("trace_evidence_provenance", {"evidence_ref": 7}),
        ("get_conflicting_evidence", {"claim_id": "claim:target-identity", "limit": 1.5}),
        ("get_missing_requirements", {"product_case_id": "product-case:synthetic-001", "state": "open"}),
        ("get_evidence_family_members", {"evidence_family_id": "evidence-family:transcriptomic", "include_inactive": "false"}),
        ("get_case_evidence_subgraph", {"product_case_id": "product-case:synthetic-001", "domain_ids": ("target_identity",)}),
        ("compare_evidence_paths", {"comparison_id": "comparison:x", "domain_id": "target_identity"}),
    ],
)
def test_all_public_queries_return_typed_invalid_for_wrong_parameter_types(
    tmp_path: Path, query_name: str, kwargs: dict[str, Any]
) -> None:
    run = _run(tmp_path)
    query = EvidenceGraphQueries.open(
        run.request.output_dir / run.run_id / "case_evidence_graph_manifest.json"
    )

    result = getattr(query, query_name)(**kwargs)

    assert result.query_name == query_name
    assert result.reason_codes in (["query_parameter_invalid"], ["graph_kind_mismatch"])
    assert result.nodes == [] and result.edges == []


@pytest.mark.parametrize(
    "key",
    [
        "domainScore",
        "domain-score",
        "domain score",
        "OverallScore",
        "total_score",
        "grade",
        "pass-fail",
        "potency",
        "safety",
        "efficacy",
        "GMP release",
        "clinicalConclusion",
        "ranking",
    ],
)
def test_no_score_conclusion_keys_are_normalized_and_rejected_per_candidate(
    tmp_path: Path, key: str
) -> None:
    bad = _candidate(
        candidate_id="evidence-candidate:no-score",
        metric_id="no_score_canary",
        value={key: "claimed"},
    )

    run = _run(tmp_path, bundle=_bundle(candidates=[_candidate(), bad]))

    assert run.execution_state is ExecutionState.PARTIAL
    final = run.request.output_dir / run.run_id
    rejected = (final / "rejected_records.json").read_text()
    assert "individual_record_schema_invalid" in rejected
    assert "claimed" not in rejected
    assert len(json.loads((final / "evidence_records.json").read_text())["records"]) == 1


@pytest.mark.parametrize(
    "safe_payload",
    [
        {"safety_marker_expression": 0.4},
        {"clinical_stage_label": "preclinical-model"},
        {"potency_assay_identifier": "assay:research-only"},
        {"ranking_method_ref": "method:descriptive-order"},
        {"gmp_like_transcriptional_program": "not-a-release-claim"},
    ],
)
def test_no_score_guard_allows_scientific_neighbor_keys(
    tmp_path: Path, safe_payload: dict[str, Any]
) -> None:
    candidate = _candidate(value=safe_payload)

    run = _run(tmp_path, bundle=_bundle(candidates=[candidate]))

    assert run.execution_state is ExecutionState.SUCCEEDED
    records = json.loads(
        (run.request.output_dir / run.run_id / "evidence_records.json").read_text()
    )["records"]
    assert records[0]["value"] == safe_payload


@pytest.mark.parametrize("invalid", [0, -1, True, "1"])
def test_positive_map_values_match_pydantic_and_public_schema(invalid: Any) -> None:
    spec_payload = _reconciliation_registry()["specs"][0]
    spec_payload["minimum_independent_families_by_role"]["transcriptomic"] = invalid
    spec_schema = ReconciliationSpec.model_json_schema()
    assert list(Draft202012Validator(spec_schema).iter_errors(spec_payload))
    with pytest.raises(ValueError):
        ReconciliationSpec.model_validate(spec_payload)

    manifest_schema = CaseEvidenceGraphManifest.model_json_schema()
    assert manifest_schema["properties"]["object_counts"]["additionalProperties"][
        "exclusiveMinimum"
    ] == 0


def test_public_schema_encodes_scientific_state_conditionals(tmp_path: Path) -> None:
    run = _run(tmp_path)
    final = run.request.output_dir / run.run_id
    record = json.loads((final / "evidence_records.json").read_text())["records"][0]
    requirement = json.loads((final / "evidence_requirements.json").read_text())[
        "requirements"
    ][0]
    reconciliation = json.loads((final / "reconciliation_records.json").read_text())[
        "records"
    ][0]
    cases = [
        (EvidenceRecord, record | {"evidence_state": "missing"}),
        (EvidenceRecord, record | {"denominator": 0}),
        (
            EvidenceRecord,
            record | {"revision_action": "create", "predecessor_ref": record["evidence_id"] + "@1"},
        ),
        (
            EvidenceRequirement,
            requirement | {"state": "satisfied", "satisfying_evidence_refs": []},
        ),
        (
            ReconciliationRecord,
            reconciliation | {"eligibility": "eligible", "state": None, "direction": None},
        ),
    ]
    for model, payload in cases:
        assert list(Draft202012Validator(model.model_json_schema()).iter_errors(payload))
        with pytest.raises(ValueError):
            model.model_validate(payload)


@pytest.mark.parametrize("graph_kind", ["case", "comparison"])
def test_caller_input_id_rename_preserves_run_bundle_and_public_manifest(
    tmp_path: Path, graph_kind: str,
) -> None:
    request_kwargs: dict[str, Any] = {"output_name": "shared-output"}
    if graph_kind == "comparison":
        request_kwargs.update(
            bundle=_comparison_bundle(),
            profiles=_comparison_profiles(),
            claim_registry=_comparison_claim_registry(),
        )
    request = _request(tmp_path, **request_kwargs)
    first = adapter.run(request, _spec())
    mapping = {item.input_id: f"caller-label-{index}" for index, item in enumerate(request.object_inputs)}
    bundle_ref = next(item for item in request.object_inputs if item.role == "compilation_bundle")
    bundle = json.loads(bundle_ref.path.read_text())

    def rename(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: mapping.get(item, item)
                if key in {
                    "manifest_input_id",
                    "record_set_input_id",
                    "requirement_set_input_id",
                    "sufficiency_profile_input_id",
                }
                and isinstance(item, str)
                else rename(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [rename(item) for item in value]
        return value

    renamed_bundle = rename(bundle)
    renamed_sha = _write(bundle_ref.path, renamed_bundle)
    renamed_request = request.model_copy(
        update={
            "request_id": "request-renamed-labels",
            "object_inputs": [
                item.model_copy(
                    update={
                        "input_id": mapping[item.input_id],
                        "sha256": renamed_sha if item is bundle_ref else item.sha256,
                    }
                )
                for item in request.object_inputs
            ],
        }
    )
    second = adapter.run(renamed_request, _spec())
    assert second.execution_state is ExecutionState.SUCCEEDED
    assert second.run_id == first.run_id and second.input_hash == first.input_hash
    final = second.request.output_dir / second.run_id
    manifest_text = (final / "artifact_manifest.json").read_text()
    assert not any(label in manifest_text for label in mapping.values())


def test_output_symlink_loop_returns_stable_typed_failure(tmp_path: Path) -> None:
    request = _request(tmp_path)
    loop = tmp_path / "loop"
    loop.symlink_to(loop)
    request = request.model_copy(update={"output_dir": loop})
    eligibility = adapter.check_eligibility(request, _spec())
    run = adapter.run(request, _spec())
    assert eligibility.reason_codes == ["output_dir_preflight_failed"]
    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["output_dir_preflight_failed"]
    public_registry = ToolRegistry.load_default()
    public_eligibility = public_registry.check_eligibility(request)
    public_run = public_registry.run(request)
    assert public_eligibility.reason_codes == ["output_dir_preflight_failed"]
    assert public_run.execution_state is ExecutionState.FAILED
    assert public_run.reason_codes == ["output_dir_preflight_failed"]
    assert loop.is_symlink()


@pytest.mark.parametrize("kind", ["candidate", "missing", "external"])
def test_rejected_parse_failure_never_echoes_unpublishable_refs(
    tmp_path: Path, kind: str
) -> None:
    leaked = "human readable unreleasable sentence"
    if kind == "candidate":
        bundle = _bundle(candidates=[_candidate() | {"claim_ref": {"object_id": leaked, "object_version": "1.0.0"}}])
        kwargs: dict[str, Any] = {"bundle": bundle}
    elif kind == "missing":
        bundle = _bundle(
            candidates=[_candidate()],
            missing=[_missing_observation() | {"claim_ref": {"object_id": leaked, "object_version": "1.0.0"}}],
        )
        kwargs = {"bundle": bundle}
    else:
        bundle = _comparison_bundle()
        bundle["external_case_evidence_refs"][0]["comparison_claim_ref"] = {
            "object_id": leaked,
            "object_version": "1.0.0",
        }
        kwargs = {
            "bundle": bundle,
            "profiles": _comparison_profiles(),
            "claim_registry": _comparison_claim_registry(),
        }
    run = _run(tmp_path, **kwargs)
    assert run.execution_state is ExecutionState.PARTIAL
    rejected = (
        run.request.output_dir / run.run_id / "rejected_records.json"
    ).read_text()
    assert leaked not in rejected


def test_query_parses_parquet_from_verified_bytes_without_path_reread(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = _run(tmp_path)

    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("unchecked path reread")

    monkeypatch.setattr(
        "bridge.tool_packages.p0_09_evidence_compiler.queries.read_parquet_rows",
        forbidden,
        raising=False,
    )
    EvidenceGraphQueries.open(
        run.request.output_dir / run.run_id / "case_evidence_graph_manifest.json"
    )


def test_comparison_manifest_binds_external_profile_without_input_label(
    tmp_path: Path,
) -> None:
    run = _run(
        tmp_path,
        bundle=_comparison_bundle(),
        profiles=_comparison_profiles(),
        claim_registry=_comparison_claim_registry(),
    )
    final = run.request.output_dir / run.run_id
    manifest_path = final / "comparison_evidence_graph_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    assert len(manifest["external_evidence_bindings"]) == 2
    assert "sufficiency_profile_input_id" not in json.dumps(manifest)
    manifest["external_evidence_bindings"][0]["sufficiency_profile_ref"] = {
        "object_id": "evidence-sufficiency-profile:bbbbbbbbbbbbbbbb:target_identity",
        "object_version": "0.1.0",
    }
    _write(manifest_path, manifest)
    with pytest.raises(ValueError, match="manifest_integrity_failed"):
        EvidenceGraphQueries.open(manifest_path)


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        (
            "source_claim_ref",
            {"object_id": "claim:case-b", "object_version": "1.0.0"},
        ),
        ("evidence_state", "negative"),
        ("applicability", "not_assessed"),
        ("tool_run_execution_state", "partial"),
    ],
)
def test_comparison_manifest_binding_semantics_are_bound_to_graph_edge(
    tmp_path: Path, field: str, replacement: Any
) -> None:
    run = _run(
        tmp_path,
        bundle=_comparison_bundle(),
        profiles=_comparison_profiles(),
        claim_registry=_comparison_claim_registry(),
    )
    manifest_path = (
        run.request.output_dir / run.run_id / "comparison_evidence_graph_manifest.json"
    )
    manifest = json.loads(manifest_path.read_text())
    manifest["external_evidence_bindings"][0][field] = replacement
    _write(manifest_path, manifest)

    with pytest.raises(ValueError, match="manifest_integrity_failed"):
        EvidenceGraphQueries.open(manifest_path)


def test_comparison_projection_masks_nested_claim_validation_details(
    tmp_path: Path,
) -> None:
    canary = "clientSecret=do-not-echo-this-value"
    run = _run(
        tmp_path,
        bundle=_comparison_bundle(),
        profiles=_comparison_profiles(),
        claim_registry=_comparison_claim_registry(),
    )
    final = run.request.output_dir / run.run_id
    manifest_path = final / "comparison_evidence_graph_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    nodes_path = final / manifest["graph_nodes"]["filename"]
    edges_path = final / manifest["graph_edges"]["filename"]
    nodes, edges = read_parquet_rows(nodes_path, edges_path)
    claim_index = next(
        index
        for index, node in enumerate(nodes)
        if node.node_type is GraphNodeType.CLAIM
        and node.record_mode is GraphRecordMode.OWNED
    )
    claim = nodes[claim_index]
    properties = json.loads(claim.properties_json or "{}")
    properties["clientSecret"] = canary
    properties_json = canonical_json_bytes(properties).decode("utf-8")
    nodes[claim_index] = claim.model_copy(
        update={
            "properties_json": properties_json,
            "content_hash": hashlib.sha256(properties_json.encode("utf-8")).hexdigest(),
        }
    )
    write_parquet(nodes_path, edges_path, nodes, edges)
    manifest["graph_nodes"]["sha256"] = hashlib.sha256(
        nodes_path.read_bytes()
    ).hexdigest()
    _write(manifest_path, manifest)

    with pytest.raises(Exception) as caught:
        EvidenceGraphQueries.open(manifest_path)
    rendered = "".join(
        traceback.format_exception(
            type(caught.value), caught.value, caught.value.__traceback__
        )
    )
    assert type(caught.value) is ValueError
    assert str(caught.value) == "manifest_integrity_failed"
    assert canary not in rendered


@pytest.mark.parametrize(
    "surface",
    ["case_manifest", "comparison_manifest", "case_fact_json", "comparison_parquet"],
)
def test_query_open_masks_every_untrusted_artifact_boundary(
    tmp_path: Path, surface: str
) -> None:
    canary = f"clientSecret=boundary-{surface}-do-not-echo"
    comparison = surface.startswith("comparison")
    run = _run(
        tmp_path,
        **(
            {
                "bundle": _comparison_bundle(),
                "profiles": _comparison_profiles(),
                "claim_registry": _comparison_claim_registry(),
            }
            if comparison
            else {}
        ),
    )
    final = run.request.output_dir / run.run_id
    manifest_name = (
        "comparison_evidence_graph_manifest.json"
        if comparison
        else "case_evidence_graph_manifest.json"
    )
    manifest_path = final / manifest_name
    manifest = json.loads(manifest_path.read_text())
    if surface == "case_manifest":
        manifest["product_case_ref"]["object_id"] = canary
    elif surface == "comparison_manifest":
        manifest["external_evidence_bindings"][0]["source_claim_ref"][
            "object_id"
        ] = canary
    elif surface == "case_fact_json":
        fact_path = final / manifest["evidence_records"]["filename"]
        fact = json.loads(fact_path.read_text())
        fact["records"][0]["claim_ref"]["object_id"] = canary
        manifest["evidence_records"]["sha256"] = _write(fact_path, fact)
    else:
        parquet_path = final / manifest["graph_nodes"]["filename"]
        parquet_path.write_bytes(canary.encode("utf-8"))
        manifest["graph_nodes"]["sha256"] = hashlib.sha256(
            parquet_path.read_bytes()
        ).hexdigest()
    _write(manifest_path, manifest)

    with pytest.raises(Exception) as caught:
        EvidenceGraphQueries.open(manifest_path)
    rendered = "".join(
        traceback.format_exception(
            type(caught.value), caught.value, caught.value.__traceback__
        )
    )
    assert type(caught.value) is ValueError
    assert str(caught.value) == "manifest_integrity_failed"
    assert caught.value.__cause__ is None
    assert canary not in rendered
    assert str(manifest_path) not in rendered


def _rehash_graph_edge(edge: GraphEdgeRow) -> GraphEdgeRow:
    properties_hash = hashlib.sha256(edge.properties_json.encode("utf-8")).hexdigest()
    identity = (
        f"{edge.graph_id}|{edge.edge_type.value}|{edge.source_node_id}|"
        f"{edge.target_node_id}|{properties_hash}"
    )
    digest = hashlib.sha256(identity.encode()).hexdigest()
    return edge.model_copy(
        update={"edge_id": f"edge:{digest[:24]}", "content_hash": digest}
    )


def test_query_rejects_rows_whose_scope_differs_from_manifest(tmp_path: Path) -> None:
    run = _run(tmp_path)
    final = run.request.output_dir / run.run_id
    manifest_path = final / "case_evidence_graph_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    nodes_path = final / "graph_nodes.parquet"
    edges_path = final / "graph_edges.parquet"
    nodes, edges = read_parquet_rows(nodes_path, edges_path)
    forged = "case-evidence-graph:" + "f" * 24
    nodes = [item.model_copy(update={"graph_id": forged}) for item in nodes]
    edges = [
        _rehash_graph_edge(item.model_copy(update={"graph_id": forged})) for item in edges
    ]
    write_parquet(nodes_path, edges_path, nodes, edges)
    manifest["graph_nodes"]["sha256"] = hashlib.sha256(nodes_path.read_bytes()).hexdigest()
    manifest["graph_edges"]["sha256"] = hashlib.sha256(edges_path.read_bytes()).hexdigest()
    _write(manifest_path, manifest)
    with pytest.raises(ValueError, match="manifest_integrity_failed"):
        EvidenceGraphQueries.open(manifest_path)


def test_query_rejects_self_consistent_noncanonical_relation_edge(tmp_path: Path) -> None:
    run = _run(tmp_path)
    final = run.request.output_dir / run.run_id
    manifest_path = final / "case_evidence_graph_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    nodes_path = final / "graph_nodes.parquet"
    edges_path = final / "graph_edges.parquet"
    nodes, edges = read_parquet_rows(nodes_path, edges_path)
    index = next(
        index for index, item in enumerate(edges) if item.edge_type is GraphEdgeType.SUPPORTS
    )
    edges[index] = _rehash_graph_edge(
        edges[index].model_copy(update={"edge_type": GraphEdgeType.CONTRADICTS})
    )
    write_parquet(nodes_path, edges_path, nodes, edges)
    manifest["graph_edges"]["sha256"] = hashlib.sha256(edges_path.read_bytes()).hexdigest()
    _write(manifest_path, manifest)
    with pytest.raises(ValueError, match="manifest_integrity_failed"):
        EvidenceGraphQueries.open(manifest_path)


@pytest.mark.parametrize(
    ("artifact", "id_field", "prefix"),
    [
        ("evidence_records", "record_set_id", "evidence-record-set:"),
        ("evidence_requirements", "requirement_set_id", "evidence-requirement-set:"),
        ("reconciliation_records", "reconciliation_set_id", "reconciliation-record-set:"),
    ],
)
def test_query_rejects_authoritative_set_id_not_bound_to_input_hash(
    tmp_path: Path, artifact: str, id_field: str, prefix: str
) -> None:
    run = _run(tmp_path)
    final = run.request.output_dir / run.run_id
    manifest_path = final / "case_evidence_graph_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    fact_path = final / manifest[artifact]["filename"]
    payload = json.loads(fact_path.read_text())
    payload[id_field] = prefix + "f" * 16
    manifest[artifact]["sha256"] = _write(fact_path, payload)
    _write(manifest_path, manifest)
    with pytest.raises(ValueError, match="manifest_integrity_failed"):
        EvidenceGraphQueries.open(manifest_path)


@pytest.mark.parametrize("fact_kind", ["evidence", "requirement", "reconciliation"])
def test_query_rejects_forged_fact_identity_after_full_rehash(
    tmp_path: Path, fact_kind: str
) -> None:
    run = _run(tmp_path)
    final = run.request.output_dir / run.run_id
    manifest_path = final / "case_evidence_graph_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    nodes_path = final / "graph_nodes.parquet"
    edges_path = final / "graph_edges.parquet"
    nodes, edges = read_parquet_rows(nodes_path, edges_path)
    artifact_key, node_type = {
        "evidence": ("evidence_records", GraphNodeType.EVIDENCE_RECORD),
        "requirement": ("evidence_requirements", GraphNodeType.EVIDENCE_REQUIREMENT),
        "reconciliation": ("reconciliation_records", GraphNodeType.RECONCILIATION_RECORD),
    }[fact_kind]
    fact_path = final / manifest[artifact_key]["filename"]
    facts = json.loads(fact_path.read_text())
    list_key = {
        "evidence": "records",
        "requirement": "requirements",
        "reconciliation": "records",
    }[fact_kind]
    fact = facts[list_key][0]
    id_field = {
        "evidence": "evidence_id",
        "requirement": "requirement_id",
        "reconciliation": "reconciliation_id",
    }[fact_kind]
    old_id = fact[id_field]
    fact[id_field] = old_id.rsplit(":", 1)[0] + ":" + "f" * 24
    if fact_kind == "evidence":
        modeled = EvidenceRecord.model_validate(fact)
        fact["content_hash"] = evidence_record_content_hash(modeled)
    elif fact_kind == "requirement":
        from bridge.tool_packages.p0_09_evidence_compiler.compiler import requirement_content_hash

        modeled = EvidenceRequirement.model_validate(fact)
        fact["content_hash"] = requirement_content_hash(modeled)
    else:
        from bridge.tool_packages.p0_09_evidence_compiler.compiler import reconciliation_record_content_hash

        modeled = ReconciliationRecord.model_validate(fact)
        fact["content_hash"] = reconciliation_record_content_hash(modeled)
    manifest[artifact_key]["sha256"] = _write(fact_path, facts)
    old_node = next(
        item
        for item in nodes
        if item.node_type is node_type and item.object_id == old_id
    )
    new_node = old_node.model_copy(
        update={
            "object_id": fact[id_field],
            "node_id": node_id(fact[id_field], old_node.object_version, node_type),
            "properties_json": canonical_json_bytes(fact).decode(),
            "content_hash": fact["content_hash"],
        }
    )
    nodes = [new_node if item == old_node else item for item in nodes]
    edges = [
        _rehash_graph_edge(
            item.model_copy(
                update={
                    "source_node_id": new_node.node_id
                    if item.source_node_id == old_node.node_id
                    else item.source_node_id,
                    "target_node_id": new_node.node_id
                    if item.target_node_id == old_node.node_id
                    else item.target_node_id,
                }
            )
        )
        for item in edges
    ]
    write_parquet(nodes_path, edges_path, nodes, edges)
    manifest["graph_nodes"]["sha256"] = hashlib.sha256(nodes_path.read_bytes()).hexdigest()
    manifest["graph_edges"]["sha256"] = hashlib.sha256(edges_path.read_bytes()).hexdigest()
    _write(manifest_path, manifest)
    with pytest.raises(ValueError, match="manifest_integrity_failed"):
        EvidenceGraphQueries.open(manifest_path)

def _v2_profile(
    payload: dict[str, Any],
    *,
    versions: dict[str, str] | None = None,
) -> dict[str, Any]:
    payload = json.loads(json.dumps(payload))
    ref_versions = {
        "product_case_ref": "1.0.0",
        "product_definition_ref": "1.0.0",
        "measurement_spec_ref": "1.0.0",
        "qc_profile_ref": "1.0.0",
        "measurement_result_refs": "1.0.0",
        **(versions or {}),
    }
    payload.update(
        {
            "profile_version": "0.2.0",
            "gate_rule_spec_ref": "GATE-EVIDENCE-SUFFICIENCY-v0.2",
            "gate_rule_version": "0.2.0",
            **{
                field: {
                    "object_id": payload[field],
                    "object_version": ref_versions[field],
                }
                for field in (
                    "product_case_ref",
                    "product_definition_ref",
                    "measurement_spec_ref",
                    "qc_profile_ref",
                )
            },
            "measurement_result_refs": [
                {
                    "object_id": item,
                    "object_version": ref_versions["measurement_result_refs"],
                }
                for item in payload["measurement_result_refs"]
            ],
            "measurement_evidence_state_counts": {
                "measured": len(payload["measurement_result_refs"]),
                "inferred": 0,
                "prior_only": 0,
                "negative": 0,
                "missing": 0,
                "unknown": 0,
                "unavailable": 0,
                "alert": 0,
            },
        }
    )
    return payload


def _v2_run(profile_payload: dict[str, Any]) -> dict[str, Any]:
    profile = EvidenceSufficiencyProfileV2.model_validate(
        _v2_profile(profile_payload)
        if profile_payload["profile_version"] == "0.1.0"
        else profile_payload
    )
    digest = profile.profile_id.split(":", 2)[1]
    assert profile.domain_id is not None
    assert profile.product_case_ref is not None
    assert profile.measurement_spec_ref is not None
    assert profile.qc_profile_ref is not None
    bindings = [
        {
            "input_id": f"domain-{profile.domain_id.value}",
            "role": "domain_gate_input",
            "logical_object_id": (
                f"domain-gate-input:{digest}:{profile.domain_id.value}"
            ),
            "object_version": "0.1.0",
            "schema_ref": "bridge://schemas/domain-gate-input/v0.1",
            "source_sha256": "1" * 64,
        },
        {
            "input_id": "product-case",
            "role": "product_case",
            "logical_object_id": profile.product_case_ref.object_id,
            "object_version": profile.product_case_ref.object_version,
            "schema_ref": "bridge://schemas/product-case/v0.1",
            "source_sha256": "f" * 64,
        },
        {
            "input_id": "gate-rules",
            "role": "gate_rule_spec",
            "logical_object_id": "GATE-EVIDENCE-SUFFICIENCY-v0.2",
            "object_version": "0.2.0",
            "schema_ref": (
                "bridge://schemas/evidence-sufficiency-gate-rule-spec/v0.2"
            ),
            "source_sha256": "2" * 64,
        },
        *[
            {
                "input_id": f"measurement-{index}",
                "role": "measurement_result",
                "logical_object_id": item.object_id,
                "object_version": item.object_version,
                "schema_ref": "bridge://schemas/measurement-result/v0.2",
                "source_sha256": f"{index + 3:x}" * 64,
            }
            for index, item in enumerate(profile.measurement_result_refs)
        ],
        {
            "input_id": "measurement-spec",
            "role": "measurement_spec",
            "logical_object_id": profile.measurement_spec_ref.object_id,
            "object_version": profile.measurement_spec_ref.object_version,
            "schema_ref": "bridge://schemas/measurement-spec/v0.2",
            "source_sha256": "d" * 64,
        },
        {
            "input_id": "qc-profile",
            "role": "qc_readiness_profile",
            "logical_object_id": profile.qc_profile_ref.object_id,
            "object_version": profile.qc_profile_ref.object_version,
            "schema_ref": "bridge://schemas/qc-readiness-profile/v0.2",
            "source_sha256": "e" * 64,
        },
    ]
    bindings.sort(key=lambda item: (item["role"], item["input_id"]))
    state_counts = {
        state: int(profile.evidence_sufficiency_state.value == state)
        for state in ("sufficient", "limited", "insufficient", "not_assessed")
    }
    payload = {
        "result_id": f"evidence-sufficiency-result:{digest}",
        "result_version": "0.2.0",
        "gate_rule_spec_ref": "GATE-EVIDENCE-SUFFICIENCY-v0.2",
        "source_object_bindings": bindings,
        "profiles": [profile.model_dump(mode="json")],
        "case_summary": {
            "summary_id": f"case-evidence-readiness-summary:{digest}",
            "summary_version": "0.2.0",
            "product_case_ref": profile.product_case_ref.model_dump(mode="json"),
            "profile_count": 1,
            "evidence_sufficiency_counts": state_counts,
            "score_state_counts": {"unavailable": 1},
            "blocking_reasons": profile.blocking_reasons,
            "measurement_evidence_state_counts": (
                profile.measurement_evidence_state_counts.model_dump(mode="json")
            ),
        },
        "gate_trace": [
            {
                "profile_ref": profile.profile_id,
                "domain_gate_input_ref": (
                    f"domain-gate-input:{digest}:{profile.domain_id.value}"
                ),
                "evaluated_precedence": (
                    "not_assessed",
                    "insufficient",
                    "limited",
                    "sufficient",
                ),
                "selected_state": profile.evidence_sufficiency_state.value,
                "selected_reason_codes": (
                    profile.blocking_reasons or ["raw_evidence_gate_sufficient"]
                ),
                "ignored_duplicate_input_refs": [],
            }
        ],
    }
    return EvidenceSufficiencyRunResultV2.model_validate(payload).model_dump(
        mode="json"
    )


def _request_with_v2_profile(
    tmp_path: Path,
    *,
    profile_versions: dict[str, str] | None = None,
    **request_kwargs: Any,
) -> ToolRequestV2:
    request = _request(tmp_path, **request_kwargs)
    profile_ref = next(
        item
        for item in request.object_inputs
        if item.role == "evidence_sufficiency_profile"
    )
    payload = json.loads(profile_ref.path.read_text())
    payload = _v2_profile(payload, versions=profile_versions)
    checksum = _write(profile_ref.path, payload)
    updated_ref = profile_ref.model_copy(
        update={
            "schema_ref": "bridge://schemas/evidence-sufficiency-profile/v0.2",
            "object_version": "0.2.0",
            "sha256": checksum,
        }
    )
    return request.model_copy(
        update={
            "object_inputs": [
                updated_ref if item.input_id == profile_ref.input_id else item
                for item in request.object_inputs
            ]
        }
    )


def _run_request(request: ToolRequestV2):
    return adapter.run(request, _spec())


def _case_v2_request(
    tmp_path: Path,
    *,
    bundle: dict[str, Any] | None = None,
    request_id: str = "case-v2",
    output_name: str = "case-v2-output",
    base_manifest_path: Path | None = None,
) -> ToolRequestV2:
    effective_bundle = json.loads(json.dumps(bundle or _bundle()))
    for candidate in effective_bundle["candidate_records"]:
        candidate["sufficiency_profile_input_id"] = "sufficiency-run"
    return _request(
        tmp_path,
        bundle=effective_bundle,
        request_id=request_id,
        output_name=output_name,
        base_manifest_path=base_manifest_path,
        sufficiency_runs=[("sufficiency-run", _v2_run(_profile()))],
    )


def _comparison_v2_inputs(
    bundle: dict[str, Any],
) -> tuple[dict[str, Any], list[tuple[str, dict[str, Any]]]]:
    bundle = json.loads(json.dumps(bundle))
    direct_profiles = _comparison_profiles()
    runs = []
    for index, (_profile_input_id, profile) in enumerate(direct_profiles):
        run_input_id = f"sufficiency-run-{index}"
        bundle["external_case_evidence_refs"][index][
            "sufficiency_profile_input_id"
        ] = run_input_id
        runs.append((run_input_id, _v2_run(profile)))
    return bundle, runs


def test_case_initial_v2_consumes_canonical_run_and_preserves_exact_profile_refs(
    tmp_path: Path,
) -> None:
    request = _case_v2_request(tmp_path)
    run_input = next(
        item
        for item in request.object_inputs
        if item.role == "evidence_sufficiency_run_result"
    )
    run_payload = json.loads(run_input.path.read_text())
    product_bindings = [
        item
        for item in run_payload["source_object_bindings"]
        if item["role"] == "product_case"
    ]
    assert product_bindings == [
        {
            "input_id": "product-case",
            "role": "product_case",
            "logical_object_id": "product-case:synthetic-001",
            "object_version": "1.0.0",
            "schema_ref": "bridge://schemas/product-case/v0.1",
            "source_sha256": "f" * 64,
        }
    ]

    run = _run_request(request)

    assert run.execution_state is ExecutionState.SUCCEEDED
    final = run.request.output_dir / run.run_id
    records = EvidenceRecordSet.model_validate_json(
        (final / "evidence_records.json").read_bytes()
    )
    assert records.records[0].sufficiency_profile_ref.object_version == "0.2.0"
    assert records.records[0].measurement_result_ref.object_version == "1.0.0"
    manifest = json.loads((final / "artifact_manifest.json").read_text())
    graph_manifest = json.loads(
        (final / "case_evidence_graph_manifest.json").read_text()
    )
    assert run.run_id == f"run-{run.input_hash[:16]}"
    assert manifest["run_id"] == run.run_id
    assert manifest["input_hash"] == run.input_hash
    assert graph_manifest["source_input_hash"] == run.input_hash
    run_inputs = [
        item
        for item in manifest["structured_inputs"]
        if item["role"] == "evidence_sufficiency_run_result"
    ]
    assert len(run_inputs) == 1
    assert run_inputs[0]["schema_ref"] == (
        "bridge://schemas/evidence-sufficiency-run-result/v0.2"
    )
    assert run_inputs[0]["object_version"] == "0.2.0"


def test_case_initial_v2_rejects_profile_binding_id_collision_without_publication(
    tmp_path: Path,
) -> None:
    request = _case_v2_request(
        tmp_path,
        request_id="binding-id-collision",
        output_name="binding-id-collision-output",
    )
    run_ref = next(
        item
        for item in request.object_inputs
        if item.role == "evidence_sufficiency_run_result"
    )
    run_payload = json.loads(run_ref.path.read_text())
    profile = run_payload["profiles"][0]
    profile_ref = f"{profile['profile_id']}@{profile['profile_version']}"
    collision_digest = hashlib.sha256(
        (
            f"{run_payload['result_id']}@{run_payload['result_version']}|"
            f"{profile_ref}"
        ).encode("utf-8")
    ).hexdigest()[:24]
    collision_id = f"sufficiency-profile-binding:{collision_digest}"

    bundle_ref = next(
        item for item in request.object_inputs if item.role == "compilation_bundle"
    )
    bundle_payload = json.loads(bundle_ref.path.read_text())
    for candidate in bundle_payload["candidate_records"]:
        candidate["sufficiency_profile_input_id"] = collision_id
    bundle_sha256 = _write(bundle_ref.path, bundle_payload)
    request = request.model_copy(
        update={
            "object_inputs": [
                item.model_copy(update={"input_id": collision_id})
                if item.role == "evidence_sufficiency_run_result"
                else item.model_copy(update={"sha256": bundle_sha256})
                if item.role == "compilation_bundle"
                else item
                for item in request.object_inputs
            ],
        }
    )
    spec = _spec()

    eligibility = adapter.check_eligibility(request, spec)
    run = adapter.run(request, spec)

    assert not eligibility.eligible
    assert eligibility.reason_codes == [
        "sufficiency_profile_binding_id_collision"
    ]
    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["sufficiency_profile_binding_id_collision"]
    assert run.result is None and run.artifacts == []
    assert not request.output_dir.exists()


def test_case_append_v2_reuses_canonical_run_with_exact_base_binding(
    tmp_path: Path,
) -> None:
    initial = _run_request(
        _case_v2_request(
            tmp_path, request_id="case-v2-initial", output_name="case-v2-initial-output"
        )
    )
    assert initial.execution_state is ExecutionState.SUCCEEDED
    initial_root = initial.request.output_dir / initial.run_id
    manifest_path = initial_root / "case_evidence_graph_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    prior_records = json.loads((initial_root / "evidence_records.json").read_text())[
        "records"
    ]
    prior_requirements = json.loads(
        (initial_root / "evidence_requirements.json").read_text()
    )["requirements"]
    append_bundle = _bundle(
        prior_records=prior_records,
        prior_requirements=prior_requirements,
        base_graph_ref={
            "graph_id": manifest["graph_id"],
            "graph_version": manifest["graph_version"],
            "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        },
    )
    append = _run_request(
        _case_v2_request(
            tmp_path,
            bundle=append_bundle,
            request_id="case-v2-append",
            output_name="case-v2-append-output",
            base_manifest_path=manifest_path,
        )
    )

    assert append.execution_state is ExecutionState.SUCCEEDED
    assert append.result["graph_version"] == 2


def test_comparison_initial_v2_consumes_two_canonical_runs(
    tmp_path: Path,
) -> None:
    bundle, runs = _comparison_v2_inputs(_comparison_bundle())
    request = _request(
        tmp_path,
        bundle=bundle,
        request_id="comparison-v2-initial",
        output_name="comparison-v2-initial-output",
        claim_registry=_comparison_claim_registry(),
        sufficiency_runs=runs,
    )
    run = _run_request(request)

    assert run.execution_state is ExecutionState.SUCCEEDED
    final = run.request.output_dir / run.run_id
    manifest = ComparisonEvidenceGraphManifest.model_validate_json(
        (final / "comparison_evidence_graph_manifest.json").read_bytes()
    )
    assert {
        item.sufficiency_profile_ref.object_version
        for item in manifest.external_evidence_bindings
    } == {"0.2.0"}


def test_comparison_append_legacy_and_v2_bind_exact_base_graph(
    tmp_path: Path,
) -> None:
    legacy_bundle = _comparison_bundle()
    legacy_initial = adapter.run(
        _request(
            tmp_path,
            bundle=legacy_bundle,
            request_id="comparison-legacy-initial",
            output_name="comparison-legacy-initial-output",
            profiles=_comparison_profiles(),
            claim_registry=_comparison_claim_registry(),
        ),
        _spec(),
    )
    assert legacy_initial.execution_state is ExecutionState.SUCCEEDED
    legacy_root = legacy_initial.request.output_dir / legacy_initial.run_id
    legacy_manifest_path = legacy_root / "comparison_evidence_graph_manifest.json"
    legacy_manifest = json.loads(legacy_manifest_path.read_text())
    legacy_append_bundle = _comparison_bundle()
    legacy_append_bundle["base_graph_ref"] = {
        "graph_id": legacy_manifest["graph_id"],
        "graph_version": legacy_manifest["graph_version"],
        "manifest_sha256": hashlib.sha256(
            legacy_manifest_path.read_bytes()
        ).hexdigest(),
        "manifest_input_id": "base-manifest",
        "record_set_input_id": "base-records",
        "requirement_set_input_id": "base-requirements",
    }
    legacy_append = adapter.run(
        _request(
            tmp_path,
            bundle=legacy_append_bundle,
            request_id="comparison-legacy-append",
            output_name="comparison-legacy-append-output",
            profiles=_comparison_profiles(),
            claim_registry=_comparison_claim_registry(),
            base_manifest_path=legacy_manifest_path,
        ),
        _spec(),
    )
    assert legacy_append.execution_state is ExecutionState.SUCCEEDED
    assert legacy_append.result["graph_version"] == 2

    v2_initial_bundle, v2_initial_runs = _comparison_v2_inputs(_comparison_bundle())
    v2_initial = _run_request(
        _request(
            tmp_path,
            bundle=v2_initial_bundle,
            request_id="comparison-v2-for-append",
            output_name="comparison-v2-for-append-output",
            claim_registry=_comparison_claim_registry(),
            sufficiency_runs=v2_initial_runs,
        )
    )
    assert v2_initial.execution_state is ExecutionState.SUCCEEDED
    v2_root = v2_initial.request.output_dir / v2_initial.run_id
    v2_manifest_path = v2_root / "comparison_evidence_graph_manifest.json"
    v2_manifest = json.loads(v2_manifest_path.read_text())
    v2_append_bundle, v2_append_runs = _comparison_v2_inputs(_comparison_bundle())
    v2_append_bundle["base_graph_ref"] = {
        "graph_id": v2_manifest["graph_id"],
        "graph_version": v2_manifest["graph_version"],
        "manifest_sha256": hashlib.sha256(v2_manifest_path.read_bytes()).hexdigest(),
        "manifest_input_id": "base-manifest",
        "record_set_input_id": "base-records",
        "requirement_set_input_id": "base-requirements",
    }
    v2_append = _run_request(
        _request(
            tmp_path,
            bundle=v2_append_bundle,
            request_id="comparison-v2-append",
            output_name="comparison-v2-append-output",
            claim_registry=_comparison_claim_registry(),
            base_manifest_path=v2_manifest_path,
            sufficiency_runs=v2_append_runs,
        )
    )
    assert v2_append.execution_state is ExecutionState.SUCCEEDED
    assert v2_append.result["graph_version"] == 2



def test_case_initial_v2_missing_only_creates_requirement_without_zero_record(
    tmp_path: Path,
) -> None:
    missing = _missing_observation()
    missing["source_contract_ref"] = {
        "object_id": "measurement-spec:target",
        "object_version": "1.0.0",
    }
    bundle = _bundle(candidates=[], missing=[missing])
    request = _request(
        tmp_path,
        bundle=bundle,
        request_id="case-v2-missing-only",
        output_name="case-v2-missing-only-output",
        family_registry=_family_registry(second_family=True),
        claim_registry=_claim_registry(orthogonal_required=True),
        reconciliation_registry=_reconciliation_registry(
            orthogonal_required=True
        ),
        sufficiency_runs=[("sufficiency-run", _v2_run(_profile()))],
    )

    run = _run_request(request)

    assert run.execution_state is ExecutionState.SUCCEEDED
    final = run.request.output_dir / run.run_id
    records = json.loads((final / "evidence_records.json").read_text())["records"]
    requirements = json.loads(
        (final / "evidence_requirements.json").read_text()
    )["requirements"]
    assert records == []
    assert {item["requirement_key"] for item in requirements} == {
        "orthogonal_channel",
        "transcriptomic_channel",
    }
    assert all(item["state"] == "open" for item in requirements)
    orthogonal = next(
        item
        for item in requirements
        if item["requirement_key"] == "orthogonal_channel"
    )
    assert orthogonal["source_contract_ref"] == missing["source_contract_ref"]
    assert orthogonal["satisfying_evidence_refs"] == []
    assert all("value" not in item for item in requirements)


def test_case_initial_v2_accepts_claim_contract_missing_observation(
    tmp_path: Path,
) -> None:
    missing = _missing_observation()
    bundle = _bundle(candidates=[], missing=[missing])
    request = _request(
        tmp_path,
        bundle=bundle,
        request_id="case-v2-claim-contract-missing",
        output_name="case-v2-claim-contract-missing-output",
        family_registry=_family_registry(second_family=True),
        claim_registry=_claim_registry(orthogonal_required=True),
        reconciliation_registry=_reconciliation_registry(
            orthogonal_required=True
        ),
        sufficiency_runs=[("sufficiency-run", _v2_run(_profile()))],
    )

    run = _run_request(request)

    assert run.execution_state is ExecutionState.SUCCEEDED
    final = run.request.output_dir / run.run_id
    requirements = json.loads(
        (final / "evidence_requirements.json").read_text()
    )["requirements"]
    orthogonal = next(
        item
        for item in requirements
        if item["requirement_key"] == "orthogonal_channel"
    )
    assert orthogonal["source_contract_ref"] == missing["source_contract_ref"]
    assert json.loads((final / "evidence_records.json").read_text())["records"] == []


def test_case_initial_v2_invalid_missing_contract_is_partial_and_keeps_candidate(
    tmp_path: Path,
) -> None:
    missing = _missing_observation()
    missing["source_contract_ref"] = {
        "object_id": "measurement-spec:not-registered",
        "object_version": "1.0.0",
    }
    bundle = _bundle(missing=[missing])
    bundle["candidate_records"][0]["sufficiency_profile_input_id"] = (
        "sufficiency-run"
    )
    request = _request(
        tmp_path,
        bundle=bundle,
        request_id="case-v2-invalid-missing-contract",
        output_name="case-v2-invalid-missing-contract-output",
        family_registry=_family_registry(second_family=True),
        claim_registry=_claim_registry(orthogonal_required=True),
        reconciliation_registry=_reconciliation_registry(
            orthogonal_required=True
        ),
        sufficiency_runs=[("sufficiency-run", _v2_run(_profile()))],
    )

    run = _run_request(request)

    assert run.execution_state is ExecutionState.PARTIAL
    assert run.reason_codes == ["individual_records_rejected"]
    final = run.request.output_dir / run.run_id
    records = json.loads((final / "evidence_records.json").read_text())["records"]
    rejected = json.loads((final / "rejected_records.json").read_text())["records"]
    assert len(records) == 1
    assert rejected == [
        {
            "source_kind": "missing_observation",
            "source_id": missing["observation_id"],
            "source_index": 0,
            "reason_codes": ["declared_object_ref_not_found"],
            "claim_ref": "claim:target-identity@1.0.0",
            "logical_key_digest": None,
        }
    ]


def test_comparison_v2_duplicate_run_identity_fails_closed(
    tmp_path: Path,
) -> None:
    bundle, runs = _comparison_v2_inputs(_comparison_bundle())
    first = runs[0][1]
    duplicate = runs[1][1]
    digest = first["result_id"].rsplit(":", 1)[1]
    duplicate["result_id"] = first["result_id"]
    duplicate["case_summary"]["summary_id"] = (
        f"case-evidence-readiness-summary:{digest}"
    )
    duplicate_profile = duplicate["profiles"][0]
    duplicate_profile["profile_id"] = (
        f"evidence-sufficiency-profile:{digest}:target_identity"
    )
    duplicate_profile["deterministic_run_ref"] = f"run-{digest}"
    duplicate["gate_trace"][0]["profile_ref"] = duplicate_profile["profile_id"]
    request = _request(
        tmp_path,
        bundle=bundle,
        request_id="comparison-v2-duplicate-run",
        output_name="comparison-v2-duplicate-run-output",
        claim_registry=_comparison_claim_registry(),
        sufficiency_runs=runs,
    )

    eligibility = adapter.check_eligibility(request, _spec())
    run = _run_request(request)

    assert eligibility.eligible is False
    assert eligibility.reason_codes == ["duplicate_sufficiency_run_id"]
    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["duplicate_sufficiency_run_id"]
    assert run.result is None and run.artifacts == []
    assert not request.output_dir.exists()


def test_dangling_comparison_provenance_is_partial_with_v2_run_inputs(
    tmp_path: Path,
) -> None:
    bundle, runs = _comparison_v2_inputs(_comparison_bundle(dangling=True))
    request = _request(
        tmp_path,
        bundle=bundle,
        request_id="comparison-v2-dangling",
        output_name="comparison-v2-dangling-output",
        claim_registry=_comparison_claim_registry(),
        sufficiency_runs=runs,
    )

    run = _run_request(request)

    assert run.execution_state is ExecutionState.PARTIAL
    assert run.reason_codes == ["individual_records_rejected"]
    final = run.request.output_dir / run.run_id
    rejected = json.loads((final / "rejected_records.json").read_text())["records"]
    assert len(rejected) == 1
    assert rejected[0]["source_kind"] == "external_case_evidence_ref"
    assert rejected[0]["reason_codes"] == [
        "declared_object_ref_not_found",
        "external_evidence_claim_mapping_invalid",
    ]
    queries = EvidenceGraphQueries.open(
        final / "comparison_evidence_graph_manifest.json"
    )
    result = queries.compare_evidence_paths(
        comparison_id="comparison:case-a-vs-b",
        claim_id="claim:comparison",
    )
    external = [
        item
        for item in result.nodes
        if item["node_type"] == "EvidenceRecord"
        and item["record_mode"] == "external_ref"
    ]
    assert len(external) == 1


def test_v2_sufficiency_modes_reject_mixing_and_binding_drift(
    tmp_path: Path,
) -> None:
    mixed = _case_v2_request(
        tmp_path, request_id="mixed-v2", output_name="mixed-v2-output"
    )
    legacy = _request(
        tmp_path,
        request_id="mixed-legacy-source",
        output_name="mixed-legacy-source-output",
    )
    legacy_profile = next(
        item
        for item in legacy.object_inputs
        if item.role == "evidence_sufficiency_profile"
    ).model_copy(update={"input_id": "legacy-profile"})
    mixed = mixed.model_copy(
        update={"object_inputs": [*mixed.object_inputs, legacy_profile]}
    )
    mixed_run = _run_request(mixed)
    assert mixed_run.execution_state is ExecutionState.FAILED
    assert "mixed_sufficiency_input_modes" in mixed_run.reason_codes

    drift_bundle = _bundle()
    drift_bundle["candidate_records"][0]["sufficiency_profile_input_id"] = (
        "sufficiency-run"
    )
    drift_bundle["candidate_records"][0]["measurement_result_ref"][
        "object_version"
    ] = "2.0.0"
    drift = _run_request(
        _case_v2_request(
            tmp_path,
            bundle=drift_bundle,
            request_id="binding-drift-v2",
            output_name="binding-drift-v2-output",
        )
    )
    assert drift.execution_state is ExecutionState.PARTIAL
    assert drift.reason_codes == ["individual_records_rejected"]
    rejected = json.loads(
        (
            drift.request.output_dir
            / drift.run_id
            / "rejected_records.json"
        ).read_text()
    )["records"]
    assert rejected[0]["reason_codes"] == [
        "declared_object_ref_not_found",
        "sufficiency_profile_measurement_result_mismatch",
    ]


def test_v2_run_schema_version_checksum_and_case_set_drift_fail_closed(
    tmp_path: Path,
) -> None:
    version_request = _case_v2_request(
        tmp_path, request_id="version-drift-v2", output_name="version-drift-v2-output"
    )
    run_ref = next(
        item
        for item in version_request.object_inputs
        if item.role == "evidence_sufficiency_run_result"
    )
    version_request = version_request.model_copy(
        update={
            "object_inputs": [
                item.model_copy(update={"object_version": "0.1.0"})
                if item.input_id == run_ref.input_id
                else item
                for item in version_request.object_inputs
            ]
        }
    )
    version_run = _run_request(version_request)
    assert version_run.execution_state is ExecutionState.FAILED
    assert "structured_input_schema_invalid" in version_run.reason_codes

    checksum_request = _case_v2_request(
        tmp_path,
        request_id="checksum-drift-v2",
        output_name="checksum-drift-v2-output",
    )
    checksum_ref = next(
        item
        for item in checksum_request.object_inputs
        if item.role == "evidence_sufficiency_run_result"
    )
    checksum_ref.path.write_text(checksum_ref.path.read_text() + " ")
    checksum_run = _run_request(checksum_request)
    assert checksum_run.execution_state is ExecutionState.FAILED
    assert "structured_input_checksum_mismatch" in checksum_run.reason_codes

    comparison_bundle, runs = _comparison_v2_inputs(_comparison_bundle())
    runs[1][1]["case_summary"]["product_case_ref"]["object_id"] = (
        "product-case:wrong"
    )
    case_drift_request = _request(
        tmp_path,
        bundle=comparison_bundle,
        request_id="case-set-drift-v2",
        output_name="case-set-drift-v2-output",
        sufficiency_runs=runs,
    )
    case_drift = _run_request(case_drift_request)
    assert case_drift.execution_state is ExecutionState.FAILED
    assert (
        "structured_input_schema_invalid" in case_drift.reason_codes
        or "sufficiency_run_case_binding_invalid" in case_drift.reason_codes
    )


@pytest.mark.parametrize(
    "schema_ref,model", PUBLIC_VISUALIZATION_SCHEMA_MODELS.items()
)
def test_visualization_models_export_valid_draft_2020_12_schema(
    schema_ref: str, model: type[Any]
) -> None:
    schema = model.model_json_schema()
    Draft202012Validator.check_schema(schema)
    assert schema["additionalProperties"] is False
    assert schema_ref.startswith("bridge://schemas/")


def test_v2_sufficiency_profile_compiles_shadow_evidence_without_losing_versioned_context(
    tmp_path: Path,
) -> None:
    request = _request_with_v2_profile(tmp_path)
    run = adapter.run(request, _spec())

    assert run.execution_state is ExecutionState.SUCCEEDED
    final = run.request.output_dir / run.run_id
    records = EvidenceRecordSet.model_validate_json(
        (final / "evidence_records.json").read_bytes()
    )
    assert len(records.records) == 1
    assert records.records[0].evidence_tier is EvidenceTier.SHADOW
    assert records.records[0].sufficiency_profile_ref.object_version == "0.2.0"


def test_v2_profile_keeps_formal_family_version_proof_conservatively_unavailable(
    tmp_path: Path,
) -> None:
    request = _request_with_v2_profile(
        tmp_path,
        bundle=_bundle(candidates=[_candidate(tier="formal")]),
    )
    run = adapter.run(request, _spec())

    assert run.execution_state is ExecutionState.PARTIAL
    final = run.request.output_dir / run.run_id
    rejected = json.loads((final / "rejected_records.json").read_text())["records"]
    assert len(rejected) == 1
    assert "sufficiency_profile_version_binding_unavailable" in rejected[0][
        "reason_codes"
    ]
    reconciliations = json.loads(
        (final / "reconciliation_records.json").read_text()
    )["records"]
    assert reconciliations == []


def test_visualization_bundle_has_exact_artifact_conservation_and_resolvable_bindings(
    tmp_path: Path,
) -> None:
    run = _run(tmp_path)
    final = run.request.output_dir / run.run_id
    manifest = json.loads((final / "artifact_manifest.json").read_text())
    artifact_set = P009VisualizationArtifactSet.model_validate_json(
        (final / "evidence_compiler_visualization_artifact_set.json").read_bytes()
    )
    data = EvidenceCompilerVisualizationDataV1.model_validate_json(
        (final / "evidence_compiler_visualization_data.json").read_bytes()
    )

    assert len(run.artifacts) == 24
    assert len(manifest["artifacts"]) == 23
    assert {item["filename"] for item in manifest["artifacts"]} == {
        path.name for path in final.iterdir() if path.name != "artifact_manifest.json"
    }
    artifact_ids = {item.artifact_id for item in run.artifacts}
    bound_ids = {
        artifact_set.data_profile_artifact_id,
        *(
            item.accessibility.table_artifact_id
            for item in artifact_set.visualizations
        ),
        *(
            render.artifact_id
            for item in artifact_set.visualizations
            for render in item.renders
        ),
    }
    assert bound_ids <= artifact_ids
    assert len(artifact_set.visualizations) == 3
    assert data.requirements_exclusions_records == sorted(
        [*data.requirement_records, *data.exclusion_records],
        key=lambda item: item.record_id,
    )
    assert data.record_and_family_counts_are_not_independent_evidence is True
    assert data.missing_requirements_are_not_zero_measurements is True
    assert data.claim_level_reasons_are_not_item_attribution is True


def test_visualization_payloads_are_byte_identical_on_exact_rerun(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path)
    first = adapter.run(request, _spec())
    final = first.request.output_dir / first.run_id
    names = {
        "evidence_compiler_visualization_data.json",
        "evidence_compiler_visualization_artifact_set.json",
        "evidence_compiler_claim_interpretation.tsv",
        "evidence_compiler_family_relations.tsv",
        "evidence_compiler_requirements_exclusions.tsv",
        "evidence_compiler_claim_interpretation.svg",
        "evidence_compiler_family_relations.png",
        "evidence_compiler_requirements_exclusions.pdf",
    }
    before = {name: (final / name).read_bytes() for name in names}

    second = adapter.run(request, _spec())

    assert second.execution_state is ExecutionState.SUCCEEDED
    assert second.run_id == first.run_id
    assert before == {name: (final / name).read_bytes() for name in names}


def test_visualization_tamper_prevents_existing_bundle_reuse(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path)
    first = adapter.run(request, _spec())
    final = first.request.output_dir / first.run_id
    target = final / "evidence_compiler_claim_interpretation.svg"
    target.write_bytes(target.read_bytes() + b"tampered")

    second = adapter.run(request, _spec())

    assert second.execution_state is ExecutionState.FAILED
    assert second.reason_codes == ["existing_run_bundle_hash_mismatch"]
    assert second.artifacts == []


def test_visualization_builder_and_renderer_fail_with_stable_reason_codes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def invalid_builder(**_: Any) -> None:
        raise ValueError("private implementation detail")

    adapter_module = importlib.import_module(
        "bridge.tool_packages.p0_09_evidence_compiler.adapter"
    )
    monkeypatch.setattr(
        adapter_module,
        "build_evidence_compiler_visualization_data",
        invalid_builder,
    )
    invalid = adapter.run(_request(tmp_path / "builder"), _spec())
    assert invalid.execution_state is ExecutionState.FAILED
    assert invalid.reason_codes == ["visualization_data_invalid"]
    assert invalid.artifacts == []

    monkeypatch.undo()

    def failed_renderer(**_: Any) -> None:
        raise RuntimeError("private implementation detail")

    monkeypatch.setattr(
        adapter_module,
        "prepare_evidence_compiler_visualizations",
        failed_renderer,
    )
    failed = adapter.run(_request(tmp_path / "renderer"), _spec())
    assert failed.execution_state is ExecutionState.FAILED
    assert failed.reason_codes == ["visualization_render_failed"]
    assert failed.artifacts == []


def test_static_capacity_uses_complete_table_without_top_n_selection(
    tmp_path: Path,
) -> None:
    run = _run(tmp_path / "source")
    final = run.request.output_dir / run.run_id
    profile = EvidenceCompilerVisualizationDataV1.model_validate_json(
        (final / "evidence_compiler_visualization_data.json").read_bytes()
    )
    source = profile.claim_records[0]
    claim_records = [
        source.model_copy(
            update={
                "record_id": f"claim-interpretation:{index:016d}",
                "claim_ref": f"claim:capacity-{index:02d}@1.0.0",
                "evidence_ids": [f"reconciliation:capacity-{index:02d}"],
            }
        )
        for index in range(21)
    ]
    expanded_payload = profile.model_dump(mode="json")
    expanded_payload["claim_records"] = [
        item.model_dump(mode="json") for item in claim_records
    ]
    with pytest.raises(ValueError, match="top-level evidence IDs"):
        EvidenceCompilerVisualizationDataV1.model_validate(expanded_payload)
    expanded_payload["evidence_ids"] = sorted(
        {
            evidence_id
            for key in (
                "claim_records",
                "family_relation_records",
                "requirement_records",
                "exclusion_records",
            )
            for record in expanded_payload[key]
            for evidence_id in record["evidence_ids"]
        }
    )
    expanded = EvidenceCompilerVisualizationDataV1.model_validate(expanded_payload)

    prepared = prepare_evidence_compiler_visualizations(
        profile=expanded,
        output_dir=tmp_path / "render",
        run_id="run-capacity",
        tool_version="0.4.1",
    )

    table = prepared.payloads["evidence_compiler_claim_interpretation.tsv"]
    assert len(table.decode().splitlines()) == 22
    svg = prepared.payloads["evidence_compiler_claim_interpretation.svg"]
    assert b"complete-table fallback" in svg


def test_static_capacity_falls_back_when_reason_text_cannot_fit(
    tmp_path: Path,
) -> None:
    run = _run(tmp_path / "source")
    final = run.request.output_dir / run.run_id
    profile = EvidenceCompilerVisualizationDataV1.model_validate_json(
        (final / "evidence_compiler_visualization_data.json").read_bytes()
    )
    payload = profile.model_dump(mode="json")
    record_id = payload["requirement_records"][0]["record_id"]
    reason_codes = [
        f"registered_reason_with_extended_context_{index:02d}"
        for index in range(10)
    ]
    payload["requirement_records"][0]["reason_codes"] = reason_codes
    for record in payload["requirements_exclusions_records"]:
        if record["record_id"] == record_id:
            record["reason_codes"] = reason_codes
    expanded = EvidenceCompilerVisualizationDataV1.model_validate(payload)

    prepared = prepare_evidence_compiler_visualizations(
        profile=expanded,
        output_dir=tmp_path / "render",
        run_id="run-reason-capacity",
        tool_version="0.4.1",
    )

    table = prepared.payloads["evidence_compiler_requirements_exclusions.tsv"]
    assert all(reason.encode() in table for reason in reason_codes)
    svg = prepared.payloads["evidence_compiler_requirements_exclusions.svg"]
    assert b"complete-table fallback" in svg


@pytest.mark.parametrize(
    ("profile_field", "reason_code"),
    [
        ("product_case_ref", "sufficiency_profile_case_mismatch"),
        (
            "measurement_spec_ref",
            "sufficiency_profile_measurement_spec_mismatch",
        ),
        (
            "measurement_result_refs",
            "sufficiency_profile_measurement_result_mismatch",
        ),
    ],
)
def test_v2_profile_requires_exact_case_spec_and_result_versions(
    tmp_path: Path, profile_field: str, reason_code: str
) -> None:
    request = _request_with_v2_profile(
        tmp_path,
        profile_versions={profile_field: "2.0.0"},
    )

    run = adapter.run(request, _spec())

    assert run.execution_state is ExecutionState.PARTIAL
    rejected = json.loads(
        (
            run.request.output_dir
            / run.run_id
            / "rejected_records.json"
        ).read_text()
    )["records"]
    assert rejected[0]["reason_codes"] == [reason_code]


def test_v2_profile_version_matching_applies_to_prior_history(
    tmp_path: Path,
) -> None:
    first_request = _request_with_v2_profile(tmp_path / "first")
    first = adapter.run(first_request, _spec())
    first_dir = first.request.output_dir / first.run_id
    manifest_path = first_dir / "case_evidence_graph_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    bundle = _bundle(
        candidates=[],
        prior_records=json.loads(
            (first_dir / "evidence_records.json").read_text()
        )["records"],
        prior_requirements=json.loads(
            (first_dir / "evidence_requirements.json").read_text()
        )["requirements"],
        base_graph_ref={
            "graph_id": manifest["graph_id"],
            "graph_version": manifest["graph_version"],
            "manifest_sha256": hashlib.sha256(
                manifest_path.read_bytes()
            ).hexdigest(),
        },
    )
    request = _request_with_v2_profile(
        tmp_path / "append",
        bundle=bundle,
        base_manifest_path=manifest_path,
        profile_versions={"measurement_result_refs": "2.0.0"},
    )

    run = adapter.run(request, _spec())

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["prior_history_invalid"]
    assert run.artifacts == []


def test_v2_profile_version_matching_applies_to_comparison_sources(
    tmp_path: Path,
) -> None:
    profiles = [
        (
            input_id,
            _v2_profile(
                payload,
                versions=(
                    {"measurement_spec_ref": "2.0.0"}
                    if input_id == "profile-a"
                    else None
                ),
            ),
        )
        for input_id, payload in _comparison_profiles()
    ]

    run = _run(
        tmp_path,
        bundle=_comparison_bundle(),
        profiles=profiles,
        claim_registry=_comparison_claim_registry(),
    )

    assert run.execution_state is ExecutionState.PARTIAL
    rejected = json.loads(
        (
            run.request.output_dir
            / run.run_id
            / "rejected_records.json"
        ).read_text()
    )["records"]
    external_rejections = [
        item
        for item in rejected
        if item["source_kind"] == "external_case_evidence_ref"
    ]
    assert len(external_rejections) == 1
    assert external_rejections[0]["reason_codes"] == [
        "external_evidence_claim_mapping_invalid"
    ]


def test_comparison_visualization_conserves_external_evidence_ids(
    tmp_path: Path,
) -> None:
    bundle = _comparison_bundle()
    run = _run(
        tmp_path,
        bundle=bundle,
        profiles=_comparison_profiles(),
        claim_registry=_comparison_claim_registry(),
    )
    data = EvidenceCompilerVisualizationDataV1.model_validate_json(
        (
            run.request.output_dir
            / run.run_id
            / "evidence_compiler_visualization_data.json"
        ).read_bytes()
    )
    output_records = [
        *data.claim_records,
        *data.family_relation_records,
        *data.requirement_records,
        *data.exclusion_records,
    ]
    expected = sorted(
        {
            evidence_id
            for record in output_records
            for evidence_id in record.evidence_ids
        }
    )
    manifest = json.loads(
        (
            run.request.output_dir
            / run.run_id
            / "comparison_evidence_graph_manifest.json"
        ).read_text()
    )
    external_ids = {
        item["evidence_ref"].rsplit("@", 1)[0]
        for item in manifest["external_evidence_bindings"]
    }

    assert data.evidence_ids == expected
    assert external_ids <= set(data.evidence_ids)
    artifacts_by_name = {Path(item.path).name: item for item in run.artifacts}
    for name in (
        "comparison_evidence_graph_manifest.json",
        "evidence_compiler_run_result.json",
        "artifact_manifest.json",
    ):
        assert artifacts_by_name[name].evidence_ids == data.evidence_ids


@pytest.mark.parametrize(
    ("applicabilities", "expected"),
    [
        (["not_applicable"], "not_applicable"),
        (["applicable", "not_applicable"], "partially_applicable"),
    ],
)
def test_family_component_applicability_preserves_single_and_mixed_states(
    tmp_path: Path, applicabilities: list[str], expected: str
) -> None:
    candidates = []
    for index, applicability in enumerate(applicabilities):
        candidate = _candidate(
            candidate_id=f"evidence-candidate:applicability-{index}",
            metric_id=f"applicability_metric_{index}",
        )
        candidate["applicability"] = applicability
        candidates.append(candidate)

    run = _run(tmp_path, bundle=_bundle(candidates=candidates))
    data = EvidenceCompilerVisualizationDataV1.model_validate_json(
        (
            run.request.output_dir
            / run.run_id
            / "evidence_compiler_visualization_data.json"
        ).read_bytes()
    )

    assert len(data.family_relation_records) == 1
    assert data.family_relation_records[0].applicability == expected


def test_multi_claim_visualization_is_stable_distinguishable_and_semantically_sorted(
    tmp_path: Path,
) -> None:
    claims = _claim_registry()
    second_claim = json.loads(json.dumps(claims["claims"][0]))
    second_claim["claim_id"] = "claim:secondary"
    claims["claims"].append(second_claim)
    candidates = [_candidate()]
    second_candidate = _candidate(
        candidate_id="evidence-candidate:secondary",
        metric_id="secondary_fraction",
    )
    second_candidate["claim_ref"] = {
        "object_id": "claim:secondary",
        "object_version": "1.0.0",
    }
    candidates.append(second_candidate)

    first = _run(
        tmp_path / "first",
        bundle=_bundle(candidates=candidates),
        claim_registry=claims,
    )
    permuted_claims = json.loads(json.dumps(claims))
    permuted_claims["claims"].reverse()
    second = _run(
        tmp_path / "second",
        bundle=_bundle(candidates=list(reversed(candidates))),
        claim_registry=permuted_claims,
    )
    first_dir = first.request.output_dir / first.run_id
    second_dir = second.request.output_dir / second.run_id
    first_data = EvidenceCompilerVisualizationDataV1.model_validate_json(
        (first_dir / "evidence_compiler_visualization_data.json").read_bytes()
    )
    second_data = EvidenceCompilerVisualizationDataV1.model_validate_json(
        (second_dir / "evidence_compiler_visualization_data.json").read_bytes()
    )
    first_svg = (
        first_dir / "evidence_compiler_claim_interpretation.svg"
    ).read_bytes()
    family_svg = (
        first_dir / "evidence_compiler_family_relations.svg"
    ).read_bytes()

    assert first.execution_state is ExecutionState.SUCCEEDED
    assert second.execution_state is ExecutionState.SUCCEEDED
    assert first_data.claim_records == second_data.claim_records
    assert [item.record_id for item in first_data.claim_records] == sorted(
        item.record_id for item in first_data.claim_records
    )
    for svg in (first_svg, family_svg):
        assert b"claim:secondary@1.0.0" in svg
        assert b"claim:target-identity@1.0.0" in svg
        assert svg.index(b"claim:secondary@1.0.0") < svg.index(
            b"claim:target-identity@1.0.0"
        )


def test_requirement_visualization_preserves_declared_fields_and_semantic_order(
    tmp_path: Path,
) -> None:
    run = _run(
        tmp_path,
        family_registry=_family_registry(second_family=True),
        claim_registry=_claim_registry(orthogonal_required=True),
        reconciliation_registry=_reconciliation_registry(
            orthogonal_required=True
        ),
    )
    final = run.request.output_dir / run.run_id
    data = EvidenceCompilerVisualizationDataV1.model_validate_json(
        (final / "evidence_compiler_visualization_data.json").read_bytes()
    )
    by_key = {item.requirement_key: item for item in data.requirement_records}

    assert set(by_key) == {"orthogonal_channel", "transcriptomic_channel"}
    assert by_key["transcriptomic_channel"].required_modality == "scRNA-seq"
    assert by_key["transcriptomic_channel"].required_experiment is None
    assert by_key["orthogonal_channel"].required_modality is None
    assert by_key["orthogonal_channel"].required_experiment == "orthogonal assay"

    table = (
        final / "evidence_compiler_requirements_exclusions.tsv"
    ).read_text().splitlines()
    header = table[0].split("\t")
    record_id_index = header.index("record_id")
    table_ids = [row.split("\t")[record_id_index] for row in table[1:]]
    assert table_ids == sorted(table_ids)

    svg = (
        final / "evidence_compiler_requirements_exclusions.svg"
    ).read_bytes()
    assert svg.index(b"orthogonal channel") < svg.index(
        b"transcriptomic channel"
    )
    for record in data.requirement_records:
        short_ref = _short_ref(record.requirement_ref)
        assert short_ref.encode() in svg


def test_visualization_record_contracts_reject_semantic_drift(tmp_path: Path) -> None:
    run = _run(tmp_path)
    final = run.request.output_dir / run.run_id
    data = EvidenceCompilerVisualizationDataV1.model_validate_json(
        (final / "evidence_compiler_visualization_data.json").read_bytes()
    )

    claim = data.claim_records[0].model_dump(mode="json")
    with pytest.raises(ValueError, match="claim interpretation axes"):
        ClaimInterpretationRecord.model_validate(
            claim
            | {
                "eligibility": "insufficient_evidence",
                "reconciliation_state": None,
                "direction": None,
                "evidence_state": "inferred",
                "missingness": "none",
                "applicability": "applicable",
            }
        )
    with pytest.raises(ValueError, match="resolved reconciliation requires direction"):
        ClaimInterpretationRecord.model_validate(
            claim
            | {
                "eligibility": "eligible",
                "reconciliation_state": "stable",
                "direction": None,
                "evidence_state": "inferred",
                "missingness": "none",
                "applicability": "applicable",
            }
        )

    family = data.family_relation_records[0].model_dump(mode="json")
    with pytest.raises(ValueError, match="raw record count"):
        EvidenceFamilyRelationRecord.model_validate(
            family | {"raw_record_count": family["raw_record_count"] + 1}
        )
    with pytest.raises(ValueError, match="conflicting family relations"):
        EvidenceFamilyRelationRecord.model_validate(
            family
            | {
                "relation": "conflict",
                "evidence_state": "inferred",
                "missingness": "none",
            }
        )
    with pytest.raises(ValueError, match="evidence state and missingness"):
        EvidenceFamilyRelationRecord.model_validate(
            family | {"evidence_state": "unknown", "missingness": "none"}
        )

    requirement = data.requirement_records[0].model_dump(mode="json")
    open_axes = requirement | {
        "requirement_state": "open",
        "satisfying_record_count": 0,
        "evidence_state": "inferred",
        "missingness": "none",
        "applicability": "applicable",
    }
    with pytest.raises(ValueError, match="requirement state axes"):
        EvidenceRequirementRecord.model_validate(open_axes)
    with pytest.raises(ValueError, match="open requirement"):
        EvidenceRequirementRecord.model_validate(
            open_axes
            | {
                "satisfying_record_count": 1,
                "evidence_state": "missing",
                "missingness": "missing",
                "applicability": "partially_applicable",
            }
        )
    with pytest.raises(ValueError, match="satisfied requirement"):
        EvidenceRequirementRecord.model_validate(
            requirement
            | {
                "requirement_state": "satisfied",
                "satisfying_record_count": 0,
                "evidence_state": "inferred",
                "missingness": "none",
                "applicability": "applicable",
            }
        )

    reconciliation_exclusion = {
        "record_id": "reconciliation-exclusion:test",
        "evidence_ids": ["reconciliation:test"],
        "evidence_state": "unknown",
        "missingness": "not_assessed",
        "applicability": "partially_applicable",
        "reason_codes": [],
        "exclusion_kind": "reconciliation_exclusion",
        "record_kind": "exclusion",
        "claim_ref": "claim:test@1.0.0",
        "excluded_record_count": 1,
        "excluded_evidence_refs": ["evidence:test@1"],
        "source_kind": None,
        "source_id": None,
        "reason_attribution_scope": "claim_level_not_per_evidence",
    }
    CompilationExclusionRecord.model_validate(reconciliation_exclusion)
    with pytest.raises(ValueError, match="claim-level reasons"):
        CompilationExclusionRecord.model_validate(
            reconciliation_exclusion | {"excluded_record_count": 2}
        )

    input_rejection = {
        "record_id": "input-rejection:test:000000",
        "evidence_ids": ["graph:test"],
        "evidence_state": "alert",
        "missingness": "conflict",
        "applicability": "not_assessed",
        "reason_codes": ["individual_record_schema_invalid"],
        "exclusion_kind": "input_rejection",
        "record_kind": "exclusion",
        "claim_ref": None,
        "excluded_record_count": 1,
        "excluded_evidence_refs": [],
        "source_kind": "candidate_record",
        "source_id": "evidence-candidate:test",
        "reason_attribution_scope": "exact_rejected_input",
    }
    CompilationExclusionRecord.model_validate(input_rejection)
    with pytest.raises(ValueError, match="exact sanitized source"):
        CompilationExclusionRecord.model_validate(
            input_rejection | {"excluded_record_count": 2}
        )
    with pytest.raises(ValueError, match="compilation exclusion axes"):
        CompilationExclusionRecord.model_validate(
            input_rejection
            | {
                "evidence_state": "unknown",
                "missingness": "not_assessed",
                "applicability": "partially_applicable",
            }
        )


def test_long_reference_labels_remain_distinguishable_in_render(tmp_path: Path) -> None:
    run = _run(tmp_path / "source")
    final = run.request.output_dir / run.run_id
    source = EvidenceCompilerVisualizationDataV1.model_validate_json(
        (final / "evidence_compiler_visualization_data.json").read_bytes()
    )
    base = source.claim_records[0].model_dump(mode="json")
    refs = [
        "claim:shared-middle-alpha-xxxxxxxxxxxxxxxxxxxxxxxx-suffix@1.0.0",
        "claim:shared-middle-bravo-yyyyyyyyyyyyyyyyyyyyyyyy-suffix@1.0.0",
    ]
    payload = source.model_dump(mode="json")
    payload["claim_records"] = [
        base
        | {
            "record_id": f"claim-interpretation:collision-{index}",
            "claim_ref": ref,
            "evidence_ids": [f"reconciliation:collision-{index}"],
        }
        for index, ref in enumerate(refs)
    ]
    payload["evidence_ids"] = sorted(
        {
            evidence_id
            for key in (
                "claim_records",
                "family_relation_records",
                "requirement_records",
                "exclusion_records",
            )
            for record in payload[key]
            for evidence_id in record["evidence_ids"]
        }
    )
    profile = EvidenceCompilerVisualizationDataV1.model_validate(payload)
    prepared = prepare_evidence_compiler_visualizations(
        profile=profile,
        output_dir=tmp_path / "render",
        run_id="run-ref-collision",
        tool_version="0.4.1",
    )
    labels = [_short_ref(ref) for ref in refs]
    svg = prepared.payloads["evidence_compiler_claim_interpretation.svg"]

    assert labels[0] != labels[1]
    assert all(label.encode() in svg for label in labels)
