from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
import pytest

from bridge.tool_packages.p0_09_evidence_compiler.adapter import (
    RESULT_SCHEMA_REF,
    adapter,
)
from bridge.tool_packages.p0_09_evidence_compiler.models import (
    PUBLIC_SCHEMA_MODELS,
    EvidenceCompilerRunResult,
    EvidenceRecordSet,
    EvidenceRequirementSet,
    ReconciliationRecordSet,
    EvidenceCompilationBundle,
    MissingEvidenceObservation,
)
from bridge.tool_packages.p0_09_evidence_compiler.queries import EvidenceGraphQueries
from bridge.toolkit.contracts import (
    ExecutionState,
    ImplementationState,
    ToolPackageSpecV2,
    ToolRequest,
    ToolRequestV2,
)


SHA = "a" * 64
CREATED_AT = "2026-08-13T00:00:00Z"


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
        version="0.2.0",
        summary="Compile atomic evidence and reconcile conflicts by versioned rules.",
        implementation_state=ImplementationState.IMPLEMENTED,
        scientific_status="candidate",
        optional=False,
        environment_spec_id="ENV-EVIDENCE-v0.1",
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
                "biological_context_ref": "context:synthetic",
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
                "biological_context_ref": "context:synthetic",
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
            "graph_id": "case-evidence-graph:aaaaaaaaaaaaaaaaaaaaaaaa",
            "graph_version": 1,
            "manifest_sha256": "a" * 64,
            "product_case_ref": {
                "object_id": "product-case:case-a",
                "object_version": "1.0.0",
            },
        },
        {
            "graph_id": "case-evidence-graph:bbbbbbbbbbbbbbbbbbbbbbbb",
            "graph_version": 1,
            "manifest_sha256": "b" * 64,
            "product_case_ref": {
                "object_id": "product-case:case-b",
                "object_version": "1.0.0",
            },
        },
    ]
    externals = []
    for index, (case_ref, relation) in enumerate(
        zip(case_graphs, ("supports", "contradicts"), strict=True)
    ):
        externals.append(
            {
                "source_case_graph_ref": case_ref,
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
                "evidence_tier": "formal",
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
    tier: str = "formal",
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
) -> ToolRequestV2:
    inputs = tmp_path / f"inputs-{request_id}"
    profile_objects = profiles or [("profile-target", profile or _profile())]
    objects = [
        (
            "bundle",
            "compilation_bundle",
            "bridge://schemas/evidence-compilation-bundle/v0.1",
            bundle or _bundle(),
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
    objects[1:1] = [
        (
            input_id,
            "evidence_sufficiency_profile",
            "bridge://schemas/evidence-sufficiency-profile/v0.1",
            payload,
            "0.1.0",
        )
        for input_id, payload in profile_objects
    ]
    refs = []
    for input_id, role, schema_ref, payload, version in objects:
        path = inputs / f"{input_id}.json"
        digest = _write(path, payload)
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
        tool_version="0.2.0",
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
    assert "/Users/" not in serialized and "/data1/" not in serialized


def test_case_compilation_publishes_ten_immutable_artifacts_and_stable_reconciliation(
    tmp_path: Path,
) -> None:
    run = _run(tmp_path)

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result_schema_ref == RESULT_SCHEMA_REF
    assert run.measurements == [] and run.visualizations == []
    assert len(run.artifacts) == 10
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
    assert requirements.requirements[-1].state.value == "satisfied"
    assert reconciliations.records[0].eligibility.value == "eligible"
    assert reconciliations.records[0].state.value == "stable"
    assert reconciliations.records[0].direction.value == "supports"
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


def test_integration_role_opposite_resolved_primary_is_integration_sensitive(
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
    )
    assert run.execution_state is ExecutionState.SUCCEEDED
    record = json.loads(
        ((run.request.output_dir / run.run_id) / "reconciliation_records.json").read_text()
    )["records"][0]
    assert record["eligibility"] == "eligible"
    assert record["state"] == "integration_sensitive"
    assert record["direction"] == "supports"


def test_primary_cross_family_conflict_can_only_be_resolved_by_independent_confirmation(
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
    )
    assert run.execution_state is ExecutionState.SUCCEEDED
    record = json.loads(
        ((run.request.output_dir / run.run_id) / "reconciliation_records.json").read_text()
    )["records"][0]
    assert record["eligibility"] == "eligible"
    assert record["state"] == "consensus_supported"
    assert record["direction"] == "supports"
    assert "independent_confirmation_resolved_conflict" in record["reason_codes"]


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
    second = _run(tmp_path / "second", bundle=second_bundle)
    assert second.execution_state is ExecutionState.SUCCEEDED
    second_dir = second.request.output_dir / second.run_id
    second_records = json.loads((second_dir / "evidence_records.json").read_text())[
        "records"
    ]
    assert [item["evidence_version"] for item in second_records] == [1, 2]
    assert second_records[0] == prior_records[0]
    assert second_records[1]["predecessor_ref"] == predecessor
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
    third = _run(tmp_path / "third", bundle=invalidate_bundle)
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
    record = json.loads((final / "evidence_records.json").read_text())["records"][0]
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
            comparison_id="comparison:forbidden", domain_id="target_identity"
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


def test_v1_adapter_invocation_has_one_stable_v2_reason(tmp_path: Path) -> None:
    request = ToolRequest(
        request_id="p0-09-v1",
        tool_id="P0-09",
        tool_version="0.2.0",
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
    comparison_rejected = (comparison_final / "rejected_records.json").read_text()
    assert "individual_record_schema_invalid" in comparison_rejected
    assert unsafe not in comparison_rejected
    query = EvidenceGraphQueries.open(
        comparison_final / "comparison_evidence_graph_manifest.json"
    )
    projected = query.compare_evidence_paths(
        comparison_id="comparison:case-a-vs-b", claim_id="claim:comparison"
    )
    assert sum(
        node["node_type"] == "EvidenceRecord"
        and node["record_mode"] == "external_ref"
        for node in projected.nodes
    ) == 1


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

    second = _run(tmp_path / "second", bundle=bundle)

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
