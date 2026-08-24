from __future__ import annotations

import hashlib
import importlib
from importlib.resources import files
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
import pytest

from bridge.tool_packages.p0_08_evidence_sufficiency.adapter import (
    RESULT_SCHEMA_REF,
    adapter,
    gate_rule_sha256,
    load_gate_rule,
    load_reason_catalog,
)
from bridge.tool_packages.p0_08_evidence_sufficiency.executor import REASON_CODES
from bridge.tool_packages.p0_08_evidence_sufficiency.models import (
    PUBLIC_SCHEMA_MODELS,
    DomainGateInput,
    EvidenceSufficiencyRunResult,
)
from bridge.toolkit.api import run_tool, validate_request
from bridge.toolkit.contracts import ExecutionState, ToolRequest, ToolRequestV2
from bridge.toolkit.registry import ToolRegistry


adapter_module = importlib.import_module(
    "bridge.tool_packages.p0_08_evidence_sufficiency.adapter"
)


def _write(path: Path, payload: object) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _measurement_spec(*, status: str = "frozen") -> dict[str, Any]:
    return {
        "measurement_spec_id": "MS-TARGET-v0.1",
        "version": "0.1.0",
        "scientific_question": "Are immutable upstream target-evidence records assessable?",
        "assay": "scRNA-seq",
        "status": status,
        "applicable_product_cards": ["product-definition:pd-mda-progenitor"],
        "input_contract": {"object_type": "versioned_upstream_evidence"},
        "analysis_unit": "product case x domain",
        "raw_metric_definition": {"owner": "upstream_tool"},
        "numerator": None,
        "denominator": None,
        "direction": None,
        "uncertainty_method": None,
        "minimum_data": {},
        "missing_behavior": "not_assessed",
        "tool_refs": ["P0-03"],
        "reference_refs": ["reference:test-v0.1"],
        "prior_refs": ["prior:test-v0.1"],
        "validation_ref": "validation-record:method-1",
        "exclusion_rules": {},
        "release_manifest_ref": None,
    }


def _qc(*, readiness_state: str = "ready") -> dict[str, Any]:
    return {
        "profile_id": "qc-profile:case-001",
        "input_level": "analysis_ready",
        "assay": "scRNA-seq",
        "assay_spec_id": "assay:scRNA-seq",
        "measurement_spec_status": "frozen",
        "readiness_state": readiness_state,
        "schema_integrity": {"state": "valid"},
        "metadata_completeness": {"state": "complete"},
        "matrix_provenance": {"state": "declared"},
        "upstream_library_qc": {"state": "available"},
        "cell_qc": {"state": "available"},
        "doublet_assessment": {"state": "available"},
        "cell_calling_assessment": {"state": "not_required"},
        "ambient_assessment": {"state": "not_required"},
        "data_views": {"state": "available"},
        "module_eligibility": {"P0-03": "eligible"},
        "missing_inputs": [],
        "blocking_issues": [],
        "warnings": [],
        "evidence_ids": ["evidence:qc-1"],
        "score_state": "unavailable",
        "domain_score": None,
    }


def _measurement(*, evidence_state: str = "measured") -> dict[str, Any]:
    return {
        "measurement_id": "measurement:target-1",
        "measurement_spec_id": "MS-TARGET-v0.1",
        "metric_name": "upstream_target_evidence",
        "raw_value": {"state": evidence_state},
        "numerator": None,
        "denominator": None,
        "interval": None,
        "domain_score": None,
        "score_state": "unavailable",
        "evidence_state": evidence_state,
        "provenance_refs": ["evidence:measurement-1", "run:upstream-1"],
    }


def _validation(**overrides: Any) -> dict[str, Any]:
    payload = {
        "validation_record_id": "validation-record:method-1",
        "object_version": "0.1.0",
        "created_at": "2026-08-13T00:00:00Z",
        "measurement_spec_ref": "MS-TARGET-v0.1",
        "method_id": "METHOD-BRIDGE-ALGORITHM-A0908D",
        "method_version": "0.1.0",
        "tool_ref": "P0-03",
        "environment_spec_ref": "ENV-EVIDENCE-v0.1",
        "evidence_family_id": "evidence-family:validation-1",
        "required_for_interpretation": True,
        "method_kind": "deterministic",
        "validation_state": "frozen",
        "environment_state": "frozen",
        "context_of_use_ref": "context:test-v0.1",
        "context_of_use_state": "applicable",
        "source_family_ref": "source-family:test",
        "source_holdout_state": "covered",
        "modality": "scRNA-seq",
        "modality_holdout_state": "covered",
        "calibration_state": "passed",
        "ood_state": "passed",
        "validation_refs": ["validation:test-v0.1"],
        "evidence_refs": ["evidence:validation-1"],
        "provenance_refs": ["run:validation-1"],
    }
    payload.update(overrides)
    return payload


def _prior(**overrides: Any) -> dict[str, Any]:
    payload = {
        "prior_record_id": "prior-record:prior-1",
        "object_version": "0.1.0",
        "created_at": "2026-08-13T00:00:00Z",
        "measurement_spec_ref": "MS-TARGET-v0.1",
        "product_definition_ref": "product-definition:pd-mda-progenitor",
        "prior_ref": "prior:test-v0.1",
        "snapshot_ref": "snapshot:test-v0.1",
        "prior_kind": "reference",
        "evidence_family_id": "evidence-family:prior-1",
        "required_for_interpretation": True,
        "species_match": "match",
        "assay_match": "match",
        "specimen_match": "match",
        "anatomy_match": "match",
        "developmental_stage_match": "match",
        "product_definition_match": "match",
        "gene_coverage_match": "match",
        "version_match": "match",
        "license_match": "match",
        "crosswalk_ref": "crosswalk:test-v0.1",
        "evidence_refs": ["evidence:prior-1"],
        "provenance_refs": ["run:prior-1"],
    }
    payload.update(overrides)
    return payload


def _sensitivity(**overrides: Any) -> dict[str, Any]:
    payload = {
        "sensitivity_record_id": "sensitivity-record:reference-1",
        "object_version": "0.1.0",
        "created_at": "2026-08-13T00:00:00Z",
        "measurement_spec_ref": "MS-TARGET-v0.1",
        "sensitivity_kind": "reference",
        "evidence_family_id": "evidence-family:sensitivity-1",
        "required_for_interpretation": True,
        "state": "stable",
        "baseline_ref": "result:baseline",
        "perturbation_ref": "result:reference-swap",
        "conclusion_ref": "conclusion:reference-stable",
        "evidence_refs": ["evidence:sensitivity-1"],
        "provenance_refs": ["run:sensitivity-1"],
    }
    payload.update(overrides)
    return payload


def _domain(**overrides: Any) -> dict[str, Any]:
    payload = {
        "domain_gate_input_id": "domain-gate-input:case-001:target-identity",
        "object_version": "0.1.0",
        "created_at": "2026-08-13T00:00:00Z",
        "product_case": {
            "object_id": "product-case:case-001",
            "object_version": "1.0.0",
            "provenance_refs": ["provenance:case-001"],
        },
        "product_definition": {
            "object_id": "product-definition:pd-mda-progenitor",
            "object_version": "1.0.0",
            "provenance_refs": ["provenance:product-definition"],
        },
        "domain_id": "target_identity",
        "measurement_spec_input_id": "target-spec",
        "qc_profile_input_id": "case-qc",
        "measurement_result_input_ids": ["target-result"],
        "validation_record_input_ids": ["target-validation"],
        "prior_record_input_ids": ["target-prior"],
        "sensitivity_record_input_ids": ["target-sensitivity"],
        "method_requirement": "required",
        "prior_requirement": "required",
        "required_sensitivity_kinds": ["reference"],
        "task_validation_state": "frozen",
        "score_contract_ref": None,
        "evidence_refs": ["evidence:target-raw"],
        "provenance_refs": ["run:target-domain-upstream"],
    }
    payload.update(overrides)
    return payload


def _fixture_request(
    tmp_path: Path,
    *,
    domain: dict[str, Any] | None = None,
    measurement_spec: dict[str, Any] | None = None,
    qc: dict[str, Any] | None = None,
    measurement: dict[str, Any] | None = None,
    validation: dict[str, Any] | None = None,
    prior: dict[str, Any] | None = None,
    sensitivity: dict[str, Any] | None = None,
    extras: list[tuple[str, str, str, dict[str, Any], str]] | None = None,
    request_id: str = "request-p0-08",
    output_name: str = "output",
) -> ToolRequestV2:
    input_root = tmp_path / f"inputs-{request_id}"
    input_root.mkdir(parents=True, exist_ok=True)
    gate_path = input_root / "gate_rule_spec_v0.1.json"
    gate_path.write_bytes(
        files("bridge.tool_packages.p0_08_evidence_sufficiency.resources")
        .joinpath("gate_rule_spec_v0.1.json")
        .read_bytes()
    )
    refs: list[dict[str, Any]] = [
        {
            "input_id": "gate-rules",
            "role": "gate_rule_spec",
            "schema_ref": "bridge://schemas/evidence-sufficiency-gate-rule-spec/v0.1",
            "object_version": "0.1.0",
            "path": gate_path,
            "sha256": gate_rule_sha256(),
            "media_type": "application/json",
        }
    ]
    entries: list[tuple[str, str, str, dict[str, Any], str]] = [
        (
            "target-domain",
            "domain_gate_input",
            "bridge://schemas/domain-gate-input/v0.1",
            domain if domain is not None else _domain(),
            "0.1.0",
        )
    ]
    candidates = [
        (
            "target-spec",
            "measurement_spec",
            "bridge://schemas/measurement-spec/v0.1",
            measurement_spec if measurement_spec is not None else _measurement_spec(),
            "0.1.0",
        ),
        (
            "case-qc",
            "qc_readiness_profile",
            "bridge://schemas/qc-readiness-profile/v0.1",
            qc if qc is not None else _qc(),
            "0.1.0",
        ),
        (
            "target-result",
            "measurement_result",
            "bridge://schemas/measurement-result/v0.1",
            measurement if measurement is not None else _measurement(),
            "0.1.0",
        ),
        (
            "target-validation",
            "validation_record",
            "bridge://schemas/evidence-validation-record/v0.1",
            validation if validation is not None else _validation(),
            "0.1.0",
        ),
        (
            "target-prior",
            "prior_applicability_record",
            "bridge://schemas/prior-applicability-record/v0.1",
            prior if prior is not None else _prior(),
            "0.1.0",
        ),
        (
            "target-sensitivity",
            "sensitivity_record",
            "bridge://schemas/evidence-sensitivity-record/v0.1",
            sensitivity if sensitivity is not None else _sensitivity(),
            "0.1.0",
        ),
    ]
    bound_ids = {
        value
        for key, value in (domain if domain is not None else _domain()).items()
        if key in {"measurement_spec_input_id", "qc_profile_input_id"} and value is not None
    }
    for key in (
        "measurement_result_input_ids",
        "validation_record_input_ids",
        "prior_record_input_ids",
        "sensitivity_record_input_ids",
    ):
        bound_ids.update((domain if domain is not None else _domain()).get(key, []))
    entries.extend(entry for entry in candidates if entry[0] in bound_ids)
    entries.extend(extras or [])
    for input_id, role, schema_ref, payload, version in entries:
        path = input_root / f"{input_id}.json"
        sha256 = _write(path, payload)
        refs.append(
            {
                "input_id": input_id,
                "role": role,
                "schema_ref": schema_ref,
                "object_version": version,
                "path": path.resolve(),
                "sha256": sha256,
                "media_type": "application/json",
            }
        )
    return ToolRequestV2(
        request_id=request_id,
        tool_id="P0-08",
        tool_version="0.2.0",
        output_dir=(tmp_path / output_name).resolve(),
        assets=[],
        measurement_spec_ref=None,
        parameters={},
        random_seed=0,
        object_inputs=refs,
    )


def _run(tmp_path: Path, **kwargs: Any):
    request = _fixture_request(tmp_path, **kwargs)
    spec = ToolRegistry.load_default().describe("P0-08")
    return adapter.run(request, spec)


def _assert_failed_without_publication(
    request: ToolRequestV2, reason: str
) -> None:
    spec = ToolRegistry.load_default().describe("P0-08")
    eligibility = adapter.check_eligibility(request, spec)
    run = adapter.run(request, spec)

    assert not eligibility.eligible
    assert reason in eligibility.reason_codes
    assert run.execution_state is ExecutionState.FAILED
    assert reason in run.reason_codes
    assert run.result is None
    assert run.artifacts == []
    assert run.measurements == []
    assert not request.output_dir.exists()


def _replace_ref(
    request: ToolRequestV2, input_id: str, **changes: Any
) -> ToolRequestV2:
    refs = [
        ref.model_copy(update=changes) if ref.input_id == input_id else ref
        for ref in request.object_inputs
    ]
    return request.model_copy(update={"object_inputs": refs})


def test_packaged_rule_and_reason_catalog_are_exact_candidate_resources() -> None:
    gate = load_gate_rule()
    catalog = load_reason_catalog()

    assert gate.status.value == "candidate"
    assert gate.precedence == ("not_assessed", "insufficient", "limited", "sufficient")
    assert tuple(reason.code for reason in catalog.reasons) == REASON_CODES
    assert len(catalog.reasons) == 48


@pytest.mark.parametrize("schema_ref,model", PUBLIC_SCHEMA_MODELS.items())
def test_module_models_round_trip_through_draft_2020_12(
    schema_ref: str, model: type[Any]
) -> None:
    schema = model.model_json_schema()
    Draft202012Validator.check_schema(schema)
    assert schema["additionalProperties"] is False
    assert schema_ref.startswith("bridge://schemas/")


def test_sufficient_raw_evidence_never_enables_a_domain_score(tmp_path: Path) -> None:
    run = _run(tmp_path)

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.measurements == []
    assert run.visualizations == []
    assert run.result_schema_ref == RESULT_SCHEMA_REF
    result = EvidenceSufficiencyRunResult.model_validate(run.result)
    profile = result.profiles[0]
    assert profile.evidence_sufficiency_state.value == "sufficient"
    assert profile.domain_score is None
    assert profile.score_state.value == "unavailable"
    assert profile.score_reason_codes == ["p0_score_contract_unavailable"]
    assert [item.model_dump() for item in profile.measurement_result_refs] == [
        {"object_id": "measurement:target-1", "object_version": "0.1.0"}
    ]


def test_profile_state_counts_must_match_versioned_measurement_refs(
    tmp_path: Path,
) -> None:
    run = _run(tmp_path)
    payload = json.loads(json.dumps(run.result))
    payload["profiles"][0]["measurement_evidence_state_counts"]["measured"] = 2

    with pytest.raises(ValueError, match="counts must match result refs"):
        EvidenceSufficiencyRunResult.model_validate(payload)


def test_assessed_profile_requires_complete_versioned_context(
    tmp_path: Path,
) -> None:
    run = _run(tmp_path)
    payload = json.loads(json.dumps(run.result))
    payload["profiles"][0]["product_case_ref"] = None

    with pytest.raises(ValueError, match="complete versioned context"):
        EvidenceSufficiencyRunResult.model_validate(payload)


def test_default_registry_dispatches_p0_08_through_declared_adapter(tmp_path: Path) -> None:
    request = _fixture_request(tmp_path)
    registry = ToolRegistry.load_default()

    eligibility = registry.check_eligibility(request)
    run = registry.run(request)

    assert eligibility.eligible
    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result_schema_ref == RESULT_SCHEMA_REF
    assert registry.describe("P0-08").adapter_ref.endswith(":adapter")


def test_five_domains_are_gated_independently_and_counted_only(tmp_path: Path) -> None:
    domains = [
        _domain(),
        _domain(
            domain_gate_input_id="domain-gate-input:case-001:regional-fidelity",
            domain_id="regional_fidelity",
            qc_profile_input_id="qc-limited",
        ),
        _domain(
            domain_gate_input_id="domain-gate-input:case-001:developmental-compatibility",
            domain_id="developmental_compatibility",
            qc_profile_input_id="qc-blocked",
        ),
        _domain(
            domain_gate_input_id="domain-gate-input:case-001:off-target-control",
            domain_id="off_target_control",
            product_definition=None,
            measurement_spec_input_id=None,
            qc_profile_input_id=None,
            measurement_result_input_ids=[],
            validation_record_input_ids=[],
            prior_record_input_ids=[],
            sensitivity_record_input_ids=[],
            method_requirement="not_assessed",
            prior_requirement="not_assessed",
            required_sensitivity_kinds=[],
            task_validation_state="not_assessed",
        ),
        _domain(
            domain_gate_input_id="domain-gate-input:case-001:proliferation-stress-response",
            domain_id="proliferation_stress_response",
            validation_record_input_ids=["validation-candidate"],
        ),
    ]
    extras: list[tuple[str, str, str, dict[str, Any], str]] = [
        (
            f"domain-{index}",
            "domain_gate_input",
            "bridge://schemas/domain-gate-input/v0.1",
            domain,
            "0.1.0",
        )
        for index, domain in enumerate(domains[1:], start=2)
    ]
    extras.extend(
        [
            (
                "qc-limited",
                "qc_readiness_profile",
                "bridge://schemas/qc-readiness-profile/v0.1",
                _qc(readiness_state="limited") | {"profile_id": "qc-profile:limited"},
                "0.1.0",
            ),
            (
                "qc-blocked",
                "qc_readiness_profile",
                "bridge://schemas/qc-readiness-profile/v0.1",
                _qc(readiness_state="blocked") | {"profile_id": "qc-profile:blocked"},
                "0.1.0",
            ),
            (
                "validation-candidate",
                "validation_record",
                "bridge://schemas/evidence-validation-record/v0.1",
                _validation(
                    validation_record_id="validation-record:candidate",
                    validation_state="candidate",
                ),
                "0.1.0",
            ),
        ]
    )
    request = _fixture_request(tmp_path, domain=domains[0], extras=extras)
    spec = ToolRegistry.load_default().describe("P0-08")
    run = adapter.run(request, spec)
    result = EvidenceSufficiencyRunResult.model_validate(run.result)

    assert [profile.domain_id.value for profile in result.profiles] == [
        "target_identity",
        "regional_fidelity",
        "developmental_compatibility",
        "off_target_control",
        "proliferation_stress_response",
    ]
    assert [profile.evidence_sufficiency_state.value for profile in result.profiles] == [
        "sufficient",
        "limited",
        "insufficient",
        "not_assessed",
        "limited",
    ]
    assert result.case_summary.evidence_sufficiency_counts.model_dump() == {
        "sufficient": 1,
        "limited": 2,
        "insufficient": 1,
        "not_assessed": 1,
    }
    assert result.case_summary.score_state_counts.unavailable == 5
    assert all(profile.domain_score is None for profile in result.profiles)


@pytest.mark.parametrize(
    ("changes", "axis", "axis_state", "gate_state", "reason"),
    [
        (
            {"validation": _validation(validation_state="candidate")},
            "model_robustness",
            "candidate_applicable",
            "limited",
            "method_validation_candidate",
        ),
        (
            {"prior": _prior(anatomy_match="partial_match")},
            "prior_applicability",
            "partially_applicable",
            "limited",
            "prior_partially_applicable",
        ),
        (
            {"qc": _qc(readiness_state="blocked")},
            "data_readiness",
            "insufficient",
            "insufficient",
            "data_readiness_insufficient",
        ),
        (
            {"validation": _validation(context_of_use_state="not_applicable")},
            "model_robustness",
            "not_applicable",
            "insufficient",
            "method_context_not_applicable",
        ),
        (
            {"prior": _prior(species_match="mismatch")},
            "prior_applicability",
            "inapplicable",
            "insufficient",
            "required_prior_inapplicable",
        ),
        (
            {"sensitivity": _sensitivity(state="unstable")},
            "model_robustness",
            "unstable",
            "insufficient",
            "sensitivity_unstable",
        ),
        (
            {"validation": _validation(source_holdout_state="not_covered")},
            "model_robustness",
            "candidate_applicable",
            "limited",
            "source_holdout_not_covered",
        ),
    ],
)
def test_axis_folds_follow_fixed_precedence(
    tmp_path: Path,
    changes: dict[str, Any],
    axis: str,
    axis_state: str,
    gate_state: str,
    reason: str,
) -> None:
    run = _run(tmp_path, **changes)
    profile = EvidenceSufficiencyRunResult.model_validate(run.result).profiles[0]

    assert getattr(profile, axis).value == axis_state
    assert profile.evidence_sufficiency_state.value == gate_state
    assert reason in {
        *profile.data_reason_codes,
        *profile.robustness_reason_codes,
        *profile.prior_reason_codes,
    }
    assert profile.domain_score is None


def test_sparse_valid_binding_is_not_assessed_not_execution_failure(tmp_path: Path) -> None:
    sparse = _domain(
        product_case=None,
        product_definition=None,
        domain_id=None,
        measurement_spec_input_id=None,
        qc_profile_input_id=None,
        measurement_result_input_ids=[],
        validation_record_input_ids=[],
        prior_record_input_ids=[],
        sensitivity_record_input_ids=[],
        method_requirement="not_assessed",
        prior_requirement="not_assessed",
        required_sensitivity_kinds=[],
        task_validation_state="not_assessed",
    )
    run = _run(tmp_path, domain=sparse)
    profile = EvidenceSufficiencyRunResult.model_validate(run.result).profiles[0]

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert profile.evidence_sufficiency_state.value == "not_assessed"
    assert "product_case_not_declared" in profile.missing_requirements
    assert "raw_evidence_gate_not_assessed" in profile.missing_requirements
    assert profile.blocking_reasons == []
    assert EvidenceSufficiencyRunResult.model_validate(
        run.result
    ).case_summary.blocking_reasons == []
    assert profile.domain_score is None


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"domain": _domain(task_validation_state="not_assessed")}, "task_validation_not_assessed"),
        (
            {"domain": _domain(method_requirement="not_assessed")},
            "method_requirement_not_assessed",
        ),
        (
            {"domain": _domain(validation_record_input_ids=[])},
            "validation_record_not_provided",
        ),
        (
            {"validation": _validation(calibration_state="not_assessed")},
            "validation_check_not_assessed",
        ),
        (
            {"domain": _domain(sensitivity_record_input_ids=[])},
            "required_sensitivity_record_missing",
        ),
        (
            {"sensitivity": _sensitivity(state="not_assessed")},
            "sensitivity_not_assessed",
        ),
        (
            {"domain": _domain(prior_requirement="not_assessed")},
            "prior_requirement_not_assessed",
        ),
        (
            {"domain": _domain(prior_record_input_ids=[])},
            "required_prior_record_missing",
        ),
        (
            {"prior": _prior(species_match="not_assessed")},
            "prior_match_not_assessed",
        ),
    ],
)
def test_missing_scientific_records_are_successful_not_assessed_results(
    tmp_path: Path, changes: dict[str, Any], reason: str
) -> None:
    run = _run(tmp_path, **changes)
    profile = EvidenceSufficiencyRunResult.model_validate(run.result).profiles[0]

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert profile.evidence_sufficiency_state.value == "not_assessed"
    assert reason in profile.missing_requirements
    assert profile.domain_score is None


def test_deterministic_and_prior_not_required_paths_are_explicit(tmp_path: Path) -> None:
    domain = _domain(
        method_requirement="not_required",
        prior_requirement="not_required",
        prior_record_input_ids=[],
    )
    run = _run(tmp_path, domain=domain)
    profile = EvidenceSufficiencyRunResult.model_validate(run.result).profiles[0]

    assert profile.model_robustness.value == "not_required"
    assert profile.prior_applicability.value == "not_required"
    assert "deterministic_method_path_validated" in profile.robustness_reason_codes
    assert "prior_not_required" in profile.prior_reason_codes
    assert profile.evidence_sufficiency_state.value == "sufficient"


def test_learned_record_cannot_establish_no_model_required_path(tmp_path: Path) -> None:
    domain = _domain(
        method_requirement="not_required",
        prior_requirement="not_required",
        prior_record_input_ids=[],
    )
    run = _run(tmp_path, domain=domain, validation=_validation(method_kind="learned"))
    profile = EvidenceSufficiencyRunResult.model_validate(run.result).profiles[0]

    assert profile.model_robustness.value == "not_assessed"
    assert profile.evidence_sufficiency_state.value == "not_assessed"
    assert "validation_check_not_assessed" in profile.missing_requirements


def test_score_reference_is_provenance_only_and_never_enables_score(tmp_path: Path) -> None:
    run = _run(tmp_path, domain=_domain(score_contract_ref="score-contract:candidate"))
    profile = EvidenceSufficiencyRunResult.model_validate(run.result).profiles[0]

    assert profile.evidence_sufficiency_state.value == "sufficient"
    assert profile.domain_score is None
    assert profile.score_state.value == "unavailable"
    assert profile.score_reason_codes == [
        "p0_score_contract_unavailable",
        "score_contract_ignored_current_release",
    ]


@pytest.mark.parametrize(
    ("evidence_state", "expected_gate_state", "expected_reason"),
    [
        ("negative", "sufficient", None),
        ("alert", "sufficient", None),
        ("unknown", "not_assessed", "measurement_evidence_unknown"),
        ("missing", "not_assessed", "measurement_evidence_missing"),
        ("unavailable", "not_assessed", "measurement_evidence_unavailable"),
    ],
)
def test_raw_measurement_state_is_preserved_without_promoting_absence(
    tmp_path: Path,
    evidence_state: str,
    expected_gate_state: str,
    expected_reason: str | None,
) -> None:
    run = _run(tmp_path, measurement=_measurement(evidence_state=evidence_state))
    profile = EvidenceSufficiencyRunResult.model_validate(run.result).profiles[0]

    assert profile.evidence_sufficiency_state.value == expected_gate_state
    assert profile.measurement_evidence_state_counts.model_dump()[evidence_state] == 1
    if expected_reason is not None:
        assert expected_reason in profile.data_reason_codes
        assert expected_reason in profile.missing_requirements
    assert profile.domain_score is None


def test_blocking_and_missing_reason_buckets_follow_catalog_severity(
    tmp_path: Path,
) -> None:
    blocked = _run(tmp_path / "blocked", qc=_qc(readiness_state="blocked"))
    blocked_result = EvidenceSufficiencyRunResult.model_validate(blocked.result)
    blocked_profile = blocked_result.profiles[0]

    assert blocked_profile.blocking_reasons == [
        "data_readiness_insufficient",
        "raw_evidence_gate_insufficient",
    ]
    assert blocked_profile.missing_requirements == []
    assert blocked_result.case_summary.blocking_reasons == blocked_profile.blocking_reasons

    missing = _run(
        tmp_path / "missing",
        domain=_domain(task_validation_state="not_assessed"),
    )
    missing_result = EvidenceSufficiencyRunResult.model_validate(missing.result)
    missing_profile = missing_result.profiles[0]

    assert "task_validation_not_assessed" in missing_profile.missing_requirements
    assert "raw_evidence_gate_not_assessed" in missing_profile.missing_requirements
    assert missing_profile.blocking_reasons == []
    assert missing_result.case_summary.blocking_reasons == []


def test_same_family_identical_records_collapse_without_a_vote(tmp_path: Path) -> None:
    duplicate = _validation()
    domain = _domain(validation_record_input_ids=["target-validation", "validation-copy"])
    extra = (
        "validation-copy",
        "validation_record",
        "bridge://schemas/evidence-validation-record/v0.1",
        duplicate,
        "0.1.0",
    )
    run = _run(tmp_path, domain=domain, extras=[extra])
    result = EvidenceSufficiencyRunResult.model_validate(run.result)

    assert result.profiles[0].model_robustness.value == "validated_applicable"
    assert "evidence_family_duplicate_collapsed" in result.profiles[0].robustness_reason_codes
    assert result.gate_trace[0].ignored_duplicate_input_refs == ["validation-copy"]
    assert (
        result.profiles[0].deduplicated_evidence_family_ids.count(
            "evidence-family:validation-1"
        )
        == 1
    )


def test_same_family_nonidentical_records_require_review(tmp_path: Path) -> None:
    conflicting = _validation(
        validation_record_id="validation-record:method-conflict",
        evidence_refs=["evidence:validation-conflict"],
    )
    domain = _domain(validation_record_input_ids=["target-validation", "validation-conflict"])
    extra = (
        "validation-conflict",
        "validation_record",
        "bridge://schemas/evidence-validation-record/v0.1",
        conflicting,
        "0.1.0",
    )
    run = _run(tmp_path, domain=domain, extras=[extra])
    profile = EvidenceSufficiencyRunResult.model_validate(run.result).profiles[0]

    assert profile.model_robustness.value == "not_assessed"
    assert profile.evidence_sufficiency_state.value == "not_assessed"
    assert "evidence_family_conflict_requires_review" in profile.missing_requirements
    assert profile.blocking_reasons == []
    assert profile.validation_refs == [
        "validation-record:method-1",
        "validation-record:method-conflict",
    ]
    assert "evidence:validation-1" in profile.evidence_refs
    assert "evidence:validation-conflict" in profile.evidence_refs


def test_nonidentical_optional_family_records_remain_provenance_only(tmp_path: Path) -> None:
    optional_a = _validation(
        validation_record_id="validation-record:optional-a",
        evidence_family_id="evidence-family:optional",
        required_for_interpretation=False,
    )
    optional_b = _validation(
        validation_record_id="validation-record:optional-b",
        evidence_family_id="evidence-family:optional",
        required_for_interpretation=False,
        evidence_refs=["evidence:optional-b"],
    )
    domain = _domain(
        validation_record_input_ids=[
            "target-validation",
            "optional-validation-a",
            "optional-validation-b",
        ]
    )
    extras = [
        (
            "optional-validation-a",
            "validation_record",
            "bridge://schemas/evidence-validation-record/v0.1",
            optional_a,
            "0.1.0",
        ),
        (
            "optional-validation-b",
            "validation_record",
            "bridge://schemas/evidence-validation-record/v0.1",
            optional_b,
            "0.1.0",
        ),
    ]
    run = _run(tmp_path, domain=domain, extras=extras)
    profile = EvidenceSufficiencyRunResult.model_validate(run.result).profiles[0]

    assert profile.evidence_sufficiency_state.value == "sufficient"
    assert "evidence_family_conflict_requires_review" not in profile.missing_requirements
    assert "evidence:optional-b" in profile.evidence_refs


def test_supporting_records_in_required_families_cannot_worsen_gates(
    tmp_path: Path,
) -> None:
    domain = _domain(
        validation_record_input_ids=["target-validation", "supporting-validation"],
        prior_record_input_ids=["target-prior", "supporting-prior"],
        sensitivity_record_input_ids=["target-sensitivity", "supporting-sensitivity"],
    )
    extras = [
        (
            "supporting-validation",
            "validation_record",
            "bridge://schemas/evidence-validation-record/v0.1",
            _validation(
                validation_record_id="validation-record:supporting-failed",
                required_for_interpretation=False,
                calibration_state="failed",
                ood_state="failed",
                evidence_refs=["evidence:supporting-validation"],
            ),
            "0.1.0",
        ),
        (
            "supporting-prior",
            "prior_applicability_record",
            "bridge://schemas/prior-applicability-record/v0.1",
            _prior(
                prior_record_id="prior-record:supporting-mismatch",
                required_for_interpretation=False,
                species_match="mismatch",
                evidence_refs=["evidence:supporting-prior"],
            ),
            "0.1.0",
        ),
        (
            "supporting-sensitivity",
            "sensitivity_record",
            "bridge://schemas/evidence-sensitivity-record/v0.1",
            _sensitivity(
                sensitivity_record_id="sensitivity-record:supporting-unstable",
                required_for_interpretation=False,
                state="unstable",
                evidence_refs=["evidence:supporting-sensitivity"],
            ),
            "0.1.0",
        ),
    ]
    run = _run(tmp_path, domain=domain, extras=extras)
    profile = EvidenceSufficiencyRunResult.model_validate(run.result).profiles[0]

    assert profile.evidence_sufficiency_state.value == "sufficient"
    assert profile.model_robustness.value == "validated_applicable"
    assert profile.prior_applicability.value == "applicable"
    assert "evidence_family_conflict_requires_review" not in profile.missing_requirements
    assert {
        "evidence:supporting-validation",
        "evidence:supporting-prior",
        "evidence:supporting-sensitivity",
    } <= set(profile.evidence_refs)


def test_supporting_records_cannot_improve_required_candidate_records(
    tmp_path: Path,
) -> None:
    domain = _domain(
        validation_record_input_ids=["target-validation", "supporting-validation"],
        prior_record_input_ids=["target-prior", "supporting-prior"],
        sensitivity_record_input_ids=["target-sensitivity", "supporting-sensitivity"],
    )
    extras = [
        (
            "supporting-validation",
            "validation_record",
            "bridge://schemas/evidence-validation-record/v0.1",
            _validation(
                validation_record_id="validation-record:supporting-frozen",
                required_for_interpretation=False,
            ),
            "0.1.0",
        ),
        (
            "supporting-prior",
            "prior_applicability_record",
            "bridge://schemas/prior-applicability-record/v0.1",
            _prior(
                prior_record_id="prior-record:supporting-match",
                required_for_interpretation=False,
            ),
            "0.1.0",
        ),
        (
            "supporting-sensitivity",
            "sensitivity_record",
            "bridge://schemas/evidence-sensitivity-record/v0.1",
            _sensitivity(
                sensitivity_record_id="sensitivity-record:supporting-stable",
                required_for_interpretation=False,
            ),
            "0.1.0",
        ),
    ]
    run = _run(
        tmp_path,
        domain=domain,
        validation=_validation(validation_state="candidate"),
        prior=_prior(anatomy_match="partial_match"),
        sensitivity=_sensitivity(state="limited"),
        extras=extras,
    )
    profile = EvidenceSufficiencyRunResult.model_validate(run.result).profiles[0]

    assert profile.evidence_sufficiency_state.value == "limited"
    assert profile.model_robustness.value == "candidate_applicable"
    assert profile.prior_applicability.value == "partially_applicable"
    assert "evidence_family_conflict_requires_review" not in profile.missing_requirements


@pytest.mark.parametrize(
    ("request_change", "reason"),
    [
        ({"tool_version": "0.1.0"}, "tool_version_mismatch"),
        ({"parameters": {"threshold": 0.5}}, "p0_08_parameters_forbidden"),
        ({"measurement_spec_ref": "MS-TARGET-v0.1"}, "p0_08_top_level_measurement_spec_forbidden"),
    ],
)
def test_envelope_failures_do_not_emit_results_or_artifacts(
    tmp_path: Path, request_change: dict[str, Any], reason: str
) -> None:
    request = _fixture_request(tmp_path)
    request = request.model_copy(update=request_change)
    spec = ToolRegistry.load_default().describe("P0-08")
    run = adapter.run(request, spec)

    assert run.execution_state is ExecutionState.FAILED
    assert reason in run.reason_codes
    assert run.result is None
    assert run.artifacts == []
    assert run.measurements == []


def test_unbound_structured_input_and_legacy_contract_fail_closed(tmp_path: Path) -> None:
    extra_payload = _measurement()
    extra_payload["measurement_id"] = "measurement:competitor-canary"
    unbound = (
        "sealed-competitor-extra",
        "measurement_result",
        "bridge://schemas/measurement-result/v0.1",
        extra_payload,
        "0.1.0",
    )
    request = _fixture_request(tmp_path, extras=[unbound])
    spec = ToolRegistry.load_default().describe("P0-08")
    eligibility = adapter.check_eligibility(request, spec)
    assert not eligibility.eligible
    assert "unbound_structured_input" in eligibility.reason_codes

    legacy = _measurement()
    legacy["raw_value"] = {"product_pass": True}
    request = _fixture_request(
        tmp_path / "legacy", measurement=legacy, request_id="legacy"
    )
    eligibility = adapter.check_eligibility(request, spec)
    assert not eligibility.eligible
    assert "legacy_evidence_contract_rejected" in eligibility.reason_codes


@pytest.mark.parametrize(
    "unsafe_value",
    [
        "/" + "Users/alice/private.json",
        "provenance from /" + "Users/alice/private.json",
        "path=/" + "home/alice/private.json",
        "mounted at /" + "data1/alice/private.json",
        "mounted at /" + "data2/alice/private.json",
        "located at /opt/project/private.json",
        "source=/" + "private/var/private.json",
        "temporary /" + "tmp/private.json",
        "volume /" + "Volumes/Research/private.json",
        "C:" + "\\Users\\" + "alice\\private.json",
        "path=C:" + "\\Users\\" + "alice\\private.json",
        "\\\\" + "server\\" + "share\\private.json",
        "source=\\\\" + "server\\" + "share\\private.json",
        "file:" + "///local/private.json",
        "file:/private.json",
        "file:private.json",
        "embedded source file:///local/private.json",
        "embedded source file:/private.json",
        "embedded source file:private.json",
        "citation [file:private.json]",
        "source=~/private.json",
        "source=~alice/private.json",
        "source=$HOME/private.json",
        "source=${HOME}/private.json",
        "source=%USERPROFILE%\\private.json",
        "embedded %HOMEPATH%\\private.json",
        "https://user:pass@example.org/data",
        "see https://user:pass@example.org/data for provenance",
        "ftp://user:pass@example.org/data",
        "pass" + "word=hunter2",
        "api_" + "key=placeholder-value",
        "APIToken=placeholder-value",
        "sec" + "ret=placeholder-value",
        "token=placeholder-value",
        "token: secret-123",
        "token: x",
        "password: hunter2",
        "authorization: credential-123",
        "access_token=placeholder-value",
        "auth=placeholder-value",
        "authorization=placeholder-value",
        "credential=placeholder-value",
        "credentials=placeholder-value",
        "Bear" + "er abcdefghijklmnop",
        "ghp_" + "A" * 24,
        "sk-" + "A" * 24,
        "AKIA" + "A" * 16,
        "https://example.org/data?" + "token=placeholder",
        "https://example.org/data?accessToken=placeholder",
        "https://example.org/data?sessionToken=placeholder",
        "https://example.org/data?consumerSecret=placeholder",
        "https://example.org/data?bearerToken=placeholder",
        "https://example.org/data?personalAccessToken=placeholder",
        "https://example.org/data?jwtToken=placeholder",
        "https://example.org/data?csrfToken=placeholder",
        "https://example.org/data?deviceToken=placeholder",
        "https://example.org/data?webhookSecret=placeholder",
        "https://example.org/data?databasePassword=placeholder",
        "https://example.org/data?signingKey=placeholder",
        "https://example.org/data?passphrase=placeholder",
        "https://example.org/data?passwd=placeholder",
        "https://example.org/data?pwd=placeholder",
        "https://example.org/data?databaseKey=placeholder",
        "https://example.org/data?webhookKey=placeholder",
        "clientSecret=placeholder-value",
        "refreshToken=placeholder-value",
        "authToken=placeholder-value",
        "sessionToken=placeholder-value",
        "id_token=placeholder-value",
        "oauthToken=placeholder-value",
        "privateKey=placeholder-value",
        "consumerSecret=placeholder-value",
        "bearerToken=placeholder-value",
        "personalAccessToken=placeholder-value",
        "jwtToken=placeholder-value",
        "csrfToken=placeholder-value",
        "deviceToken=placeholder-value",
        "webhookSecret=placeholder-value",
        "databasePassword=placeholder-value",
        "signingKey=placeholder-value",
        "encryptionKey=placeholder-value",
        "sshKey=placeholder-value",
        "apiResponseKey=placeholder-value",
        "myApiKey=placeholder-value",
        "passphrase=placeholder-value",
        "passwd=placeholder-value",
        "pwd=placeholder-value",
        "databaseKey=placeholder-value",
        "dbKey=placeholder-value",
        "webhookKey=placeholder-value",
    ],
)
def test_unsafe_scientific_references_fail_without_publication(
    tmp_path: Path, unsafe_value: str
) -> None:
    measurement = _measurement()
    measurement["raw_value"] = {"note": unsafe_value}
    request = _fixture_request(tmp_path, measurement=measurement)

    _assert_failed_without_publication(request, "unsafe_scientific_reference")


@pytest.mark.parametrize(
    "unsafe_value",
    [
        "token: secret-123",
        "token: x",
        "password: hunter2",
        "~alice/private.json",
        "embedded file:/private.json",
        "embedded file:private.json",
        "citation [file:private.json]",
        "sessionToken:credential123",
        "session_token=credential123",
        "idToken:credential123",
        "id_token=credential123",
        "oauthToken:credential123",
        "privateKey:credential123",
        "consumerSecret:credential123",
        "bearerToken:credential123",
        "personalAccessToken:credential123",
        "jwtToken:credential123",
        "csrfToken:credential123",
        "deviceToken:credential123",
        "webhookSecret:credential123",
        "databasePassword:credential123",
        "signingKey:credential123",
        "encryptionKey:credential123",
        "sshKey:credential123",
        "apiResponseKey:credential123",
        "myApiKey:credential123",
        "passphrase:credential123",
        "passwd:credential123",
        "pwd:credential123",
        "databaseKey:credential123",
        "webhookKey:credential123",
    ],
)
def test_direct_unsafe_string_contract_rejects_new_patterns(
    unsafe_value: str,
) -> None:
    assert adapter_module._unsafe_string(unsafe_value)


@pytest.mark.parametrize(
    "safe_value",
    [
        "token: a biological state label",
        "password-protected assay note",
        "secret: secreted factor expression",
        "secreted factor expression: elevated",
        "bridge://auth/context/v0.1",
        "monkey:biological-state",
        "cell-state-tokenization:stable",
        "secreted_factor:high",
        "publicKey:reference123",
        "bearerCellState:stable",
        "personalAccessPattern:descriptive",
        "jwtPathway:unavailable",
        "csrfLikeTranscript:measured",
        "deviceTokenization:stable",
        "webhookSecretedFactor:measured",
        "databasePasswordPolicy:documented",
        "signalingKey:reference",
        "cellStateKey:reference",
        "key:reference",
        "capillaryKey:vascular-state",
        "pin:cell-state",
        "cellPin:cell-state",
        "spinalPin:cell-state",
        "pinState:measured",
        "passcodePathway:measured",
        "pincodeState:measured",
        "passphraseUsage:documented",
        "passwdFormat:documented",
        "pwdState:unavailable",
        "databaseKeynote:annotation",
        "webhookKeyState:measured",
    ],
)
def test_direct_unsafe_string_contract_preserves_scientific_text(
    safe_value: str,
) -> None:
    assert not adapter_module._unsafe_string(safe_value)


@pytest.mark.parametrize(
    "safe_value",
    [
        "bridge://schemas/example/v0.1",
        "https://example.org/data?mode=scientific",
        "https://example.org/data?tokenization=cell-state",
        "bridge://auth/context/v0.1",
        "secreted factor with an API key annotation label",
        "token: a biological state label",
        "password-protected assay note",
        "secret: secreted factor expression",
        "secreted factor expression: elevated",
        "tokenization=biological-state",
        "profile:private-state",
        "CD4/CD8 ratio and neuron/glia comparison",
        "monkey:biological-state",
        "cell-state-tokenization:stable",
        "secreted_factor:high",
        "publicKey:reference123",
        "bearerCellState:stable",
        "personalAccessPattern:descriptive",
        "jwtPathway:unavailable",
        "csrfLikeTranscript:measured",
        "deviceTokenization:stable",
        "webhookSecretedFactor:measured",
        "databasePasswordPolicy:documented",
        "signalingKey:reference",
        "cellStateKey:reference",
        "key:reference",
        "capillaryKey:vascular-state",
        "pin:cell-state",
        "cellPin:cell-state",
        "spinalPin:cell-state",
        "pinState:measured",
        "passcodePathway:measured",
        "pincodeState:measured",
        "passphraseUsage:documented",
        "passwdFormat:documented",
        "pwdState:unavailable",
        "databaseKeynote:annotation",
        "webhookKeyState:measured",
    ],
)
def test_safe_scientific_references_remain_eligible(
    tmp_path: Path, safe_value: str
) -> None:
    measurement = _measurement()
    measurement["raw_value"] = {"note": safe_value}
    request = _fixture_request(tmp_path, measurement=measurement)
    spec = ToolRegistry.load_default().describe("P0-08")

    assert adapter.check_eligibility(request, spec).eligible
    assert adapter.run(request, spec).execution_state is ExecutionState.SUCCEEDED


@pytest.mark.parametrize(
    ("unsafe_key", "unsafe_value"),
    [
        ("token: secret-123", "masked"),
        ("password: hunter2", "masked"),
        ("token", "secret-123"),
        ("password", "hunter2"),
        ("api-key", "structural-secret-a"),
        ("access token", "structural-secret-b"),
        ("accessToken", "structural-secret-c"),
        ("clientSecret", "structural-secret-d"),
        ("refreshToken", "structural-secret-e"),
        ("authToken", "structural-secret-f"),
        ("APIToken", "structural-secret-g"),
        ("ACCESS_TOKEN", "structural-secret-h"),
        ("sessionToken", "structural-secret-i"),
        ("session_token", "structural-secret-j"),
        ("idToken", "structural-secret-k"),
        ("id_token", "structural-secret-l"),
        ("oauthToken", "structural-secret-m"),
        ("privateKey", "structural-secret-n"),
        ("consumerSecret", "structural-secret-o"),
        ("bearerToken", "structural-secret-p"),
        ("personalAccessToken", "structural-secret-q"),
        ("jwt_token", "structural-secret-r"),
        ("csrfToken", "structural-secret-s"),
        ("deviceToken", "structural-secret-t"),
        ("webhookSecret", "structural-secret-u"),
        ("databasePassword", "structural-secret-v"),
        ("signingKey", "structural-secret-w"),
        ("encryptionKey", "structural-secret-x"),
        ("sshKey", "structural-secret-y"),
        ("apiResponseKey", "structural-secret-z"),
        ("myApiKey", "structural-secret-aa"),
        ("passphrase", "structural-secret-ab"),
        ("databasePassphrase", "structural-secret-ac"),
        ("passwd", "structural-secret-ad"),
        ("servicePasswd", "structural-secret-ae"),
        ("pwd", "structural-secret-af"),
        ("accountPwd", "structural-secret-ag"),
        ("databaseKey", "structural-secret-ah"),
        ("dbKey", "structural-secret-ai"),
        ("webhookKey", "structural-secret-aj"),
        ("masterKey", "structural-secret-ak"),
        ("serviceKey", "structural-secret-al"),
        ("accountKey", "structural-secret-am"),
        ("decryptionKey", "structural-secret-an"),
        ("accessKey", "structural-secret-ao"),
        ("clientKey", "structural-secret-ap"),
        ("consumerKey", "structural-secret-aq"),
        ("secretKey", "structural-secret-ar"),
        ("passcode", "structural-secret-as"),
        ("pincode", "structural-secret-at"),
        ("accountPin", "structural-secret-au"),
        ("outer", "file:/private.json"),
        ("outer", "file:private.json"),
        ("~alice/private.json", "masked"),
    ],
)
def test_recursive_unsafe_keys_and_values_fail_without_echo_or_publication(
    tmp_path: Path, unsafe_key: str, unsafe_value: str
) -> None:
    measurement = _measurement()
    measurement["raw_value"] = {
        "level-1": [{"level-2": {unsafe_key: unsafe_value}}]
    }
    request = _fixture_request(tmp_path, measurement=measurement)
    spec = ToolRegistry.load_default().describe("P0-08")
    eligibility = adapter.check_eligibility(request, spec)
    run = adapter.run(request, spec)

    assert eligibility.reason_codes == ["unsafe_scientific_reference"]
    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["unsafe_scientific_reference"]
    assert unsafe_key not in json.dumps(run.model_dump(mode="json"))
    assert unsafe_value not in json.dumps(run.model_dump(mode="json"))
    assert run.result is None
    assert run.artifacts == []
    assert not request.output_dir.exists()


@pytest.mark.parametrize(
    "safe_key",
    [
        "tokenization",
        "tokenizationState",
        "secreted_factor",
        "secretedFactor",
        "authentication_state",
        "APITokenization",
        "sessionTokenization",
        "secretedConsumerFactor",
        "monkey",
        "publicKey",
        "bearerCellState",
        "personalAccessPattern",
        "jwtPathway",
        "csrfLikeTranscript",
        "deviceTokenization",
        "webhookSecretedFactor",
        "databasePasswordPolicy",
        "signalingKey",
        "cellStateKey",
        "key",
        "capillaryKey",
        "pin",
        "cellPin",
        "spinalPin",
        "pinState",
        "passcodePathway",
        "pincodeState",
        "passphraseUsage",
        "passwdFormat",
        "pwdState",
        "databaseKeynote",
        "webhookKeyState",
    ],
)
def test_scientific_keys_that_only_contain_credential_substrings_remain_legal(
    tmp_path: Path, safe_key: str
) -> None:
    measurement = _measurement()
    measurement["raw_value"] = {safe_key: "biological-state"}
    request = _fixture_request(tmp_path, measurement=measurement)
    spec = ToolRegistry.load_default().describe("P0-08")

    assert adapter.check_eligibility(request, spec).eligible
    assert adapter.run(request, spec).execution_state is ExecutionState.SUCCEEDED


@pytest.mark.parametrize(
    "unsafe_ref",
    [
        "sessionToken:credential123",
        "session_token:credential123",
        "idToken:credential123",
        "id_token:credential123",
        "oauthToken:credential123",
        "oauth_token:credential123",
        "privateKey:credential123",
        "private_key:credential123",
        "consumerSecret:credential123",
        "consumer_secret:credential123",
        "clientSecret:credential123",
        "accessToken:credential123",
        "refreshToken:credential123",
        "authToken:credential123",
        "apiToken:credential123",
        "bearerToken:credential123",
        "personalAccessToken:credential123",
        "jwtToken:credential123",
        "csrfToken:credential123",
        "deviceToken:credential123",
        "webhookSecret:credential123",
        "databasePassword:credential123",
        "signingKey:credential123",
        "encryptionKey:credential123",
        "sshKey:credential123",
        "apiResponseKey:credential123",
        "myApiKey:credential123",
        "passphrase:credential123",
        "databasePassphrase:credential123",
        "passwd:credential123",
        "servicePasswd:credential123",
        "pwd:credential123",
        "accountPwd:credential123",
        "databaseKey:credential123",
        "dbKey:credential123",
        "webhookKey:credential123",
        "masterKey:credential123",
        "serviceKey:credential123",
        "accountKey:credential123",
        "decryptionKey:credential123",
        "accessKey:credential123",
        "clientKey:credential123",
        "consumerKey:credential123",
        "secretKey:credential123",
        "passcode:credential123",
        "pincode:credential123",
        "accountPin:credential123",
    ],
)
def test_adjacent_credential_aliases_fail_direct_and_public_paths_without_echo(
    tmp_path: Path, unsafe_ref: str
) -> None:
    request = _fixture_request(
        tmp_path,
        domain=_domain(evidence_refs=[unsafe_ref]),
    )
    spec = ToolRegistry.load_default().describe("P0-08")

    direct_eligibility = adapter.check_eligibility(request, spec)
    direct_run = adapter.run(request, spec)
    public_eligibility = validate_request(request)
    public_run = run_tool(request)

    assert direct_eligibility.reason_codes == ["unsafe_scientific_reference"]
    assert public_eligibility.reason_codes == ["unsafe_scientific_reference"]
    for run in (direct_run, public_run):
        assert run.execution_state is ExecutionState.FAILED
        assert run.reason_codes == ["unsafe_scientific_reference"]
        assert run.result is None
        assert run.artifacts == []
        assert unsafe_ref not in json.dumps(run.model_dump(mode="json"))
    assert not request.output_dir.exists()


@pytest.mark.parametrize(
    ("fixture_overrides", "payload"),
    [
        ({"measurement_spec": _measurement_spec()}, ("measurement_spec_id", "bad spec")),
        ({"qc": _qc()}, ("profile_id", "bad qc profile")),
        ({"measurement": _measurement()}, ("measurement_id", "bad measurement")),
        ({"measurement": _measurement()}, ("provenance_refs", ["evidence:bad ref"])),
        ({"validation": _validation()}, ("validation_record_id", "validation bad")),
        ({"validation": _validation()}, ("evidence_family_id", "family bad")),
        ({"validation": _validation()}, ("evidence_refs", ["evidence:bad ref"])),
        ({"prior": _prior()}, ("prior_record_id", "prior bad")),
        ({"prior": _prior()}, ("snapshot_ref", "snapshot bad")),
        ({"prior": _prior()}, ("evidence_family_id", "family bad")),
        ({"prior": _prior()}, ("evidence_refs", ["evidence:bad ref"])),
        ({"sensitivity": _sensitivity()}, ("sensitivity_record_id", "sensitivity bad")),
        ({"sensitivity": _sensitivity()}, ("evidence_family_id", "family bad")),
        ({"sensitivity": _sensitivity()}, ("evidence_refs", ["evidence:bad ref"])),
    ],
)
def test_every_source_ref_copied_to_public_result_fails_during_preflight(
    tmp_path: Path,
    fixture_overrides: dict[str, dict[str, Any]],
    payload: tuple[str, Any],
) -> None:
    fixture_name, fixture = next(iter(fixture_overrides.items()))
    field, invalid_value = payload
    fixture[field] = invalid_value
    request = _fixture_request(tmp_path, **{fixture_name: fixture})

    _assert_failed_without_publication(request, "structured_input_schema_invalid")


def test_public_run_tool_returns_failed_v2_for_invalid_published_source_ref(
    tmp_path: Path,
) -> None:
    prior = _prior(snapshot_ref="snapshot with spaces")
    request = _fixture_request(tmp_path, prior=prior)

    run = run_tool(request)

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["structured_input_schema_invalid"]
    assert run.result is None
    assert run.artifacts == []
    assert not request.output_dir.exists()


def test_request_local_binding_ids_may_contain_spaces(tmp_path: Path) -> None:
    domain = _domain(
        measurement_spec_input_id="target spec",
        qc_profile_input_id="case qc",
        measurement_result_input_ids=["target result"],
        validation_record_input_ids=["target validation"],
        prior_record_input_ids=["target prior"],
        sensitivity_record_input_ids=["target sensitivity"],
    )
    request = _fixture_request(
        tmp_path,
        domain=domain,
        extras=[
            (
                "target spec",
                "measurement_spec",
                "bridge://schemas/measurement-spec/v0.1",
                _measurement_spec(),
                "0.1.0",
            ),
            (
                "case qc",
                "qc_readiness_profile",
                "bridge://schemas/qc-readiness-profile/v0.1",
                _qc(),
                "0.1.0",
            ),
            (
                "target result",
                "measurement_result",
                "bridge://schemas/measurement-result/v0.1",
                _measurement(),
                "0.1.0",
            ),
            (
                "target validation",
                "validation_record",
                "bridge://schemas/evidence-validation-record/v0.1",
                _validation(),
                "0.1.0",
            ),
            (
                "target prior",
                "prior_applicability_record",
                "bridge://schemas/prior-applicability-record/v0.1",
                _prior(),
                "0.1.0",
            ),
            (
                "target sensitivity",
                "sensitivity_record",
                "bridge://schemas/evidence-sensitivity-record/v0.1",
                _sensitivity(),
                "0.1.0",
            ),
        ],
    )
    spec = ToolRegistry.load_default().describe("P0-08")

    assert adapter.check_eligibility(request, spec).eligible
    assert adapter.run(request, spec).execution_state is ExecutionState.SUCCEEDED


def test_nonpublished_source_text_is_not_subject_to_output_ref_shape(
    tmp_path: Path,
) -> None:
    qc = _qc()
    qc["evidence_ids"] = ["QC annotation with spaces"]
    measurement = _measurement()
    measurement["provenance_refs"] = [
        "upstream provenance narrative",
        "evidence:measurement-1",
    ]
    validation = _validation(
        validation_refs=["validation narrative with spaces"],
        provenance_refs=["validation provenance narrative"],
    )
    prior = _prior(provenance_refs=["prior provenance narrative"])
    sensitivity = _sensitivity(
        provenance_refs=["sensitivity provenance narrative"]
    )
    request = _fixture_request(
        tmp_path,
        qc=qc,
        measurement=measurement,
        validation=validation,
        prior=prior,
        sensitivity=sensitivity,
    )
    spec = ToolRegistry.load_default().describe("P0-08")

    assert adapter.check_eligibility(request, spec).eligible
    assert adapter.run(request, spec).execution_state is ExecutionState.SUCCEEDED


@pytest.mark.parametrize(
    "domain",
    [
        _domain(evidence_refs=["free form evidence reference"]),
        _domain(
            product_case={
                "object_id": "free form product case",
                "object_version": "1.0.0",
                "provenance_refs": ["provenance:case-001"],
            }
        ),
        _domain(score_contract_ref="free form score contract"),
    ],
)
def test_output_bound_refs_must_be_identifier_or_scheme_shaped(
    tmp_path: Path, domain: dict[str, Any]
) -> None:
    request = _fixture_request(tmp_path, domain=domain)

    _assert_failed_without_publication(request, "structured_input_schema_invalid")


def test_v1_invocation_and_forbidden_expression_channel_fail_eligibility(
    tmp_path: Path,
) -> None:
    spec = ToolRegistry.load_default().describe("P0-08")
    v1 = ToolRequest(
        request_id="v1",
        tool_id="P0-08",
        tool_version="0.2.0",
        output_dir=(tmp_path / "out-v1").resolve(),
    )
    v1_eligibility = adapter.check_eligibility(v1, spec)  # type: ignore[arg-type]
    assert v1_eligibility.reason_codes == ["tool_request_v2_required"]

    request = _fixture_request(tmp_path / "v2")
    request = request.model_copy(update={"assets": [object()]})
    eligibility = adapter.check_eligibility(request, spec)
    assert "p0_08_expression_assets_forbidden" in eligibility.reason_codes


def test_required_cardinality_and_object_identity_fail_closed(tmp_path: Path) -> None:
    spec = ToolRegistry.load_default().describe("P0-08")
    request = _fixture_request(tmp_path)
    without_gate = request.model_copy(
        update={
            "object_inputs": [
                ref for ref in request.object_inputs if ref.role != "gate_rule_spec"
            ]
        }
    )
    assert "exactly_one_gate_rule_spec_required" in adapter.check_eligibility(
        without_gate, spec
    ).reason_codes

    without_domain = request.model_copy(
        update={
            "object_inputs": [
                ref for ref in request.object_inputs if ref.role != "domain_gate_input"
            ]
        }
    )
    assert "one_to_five_domain_gate_inputs_required" in adapter.check_eligibility(
        without_domain, spec
    ).reason_codes

    duplicate_ref = request.object_inputs[-1].model_copy(
        update={"input_id": request.object_inputs[0].input_id}
    )
    duplicated = request.model_copy(
        update={"object_inputs": [*request.object_inputs[:-1], duplicate_ref]}
    )
    assert "duplicate_object_input_id" in adapter.check_eligibility(
        duplicated, spec
    ).reason_codes


def test_duplicate_null_domain_gate_logical_id_fails_before_profile_construction(
    tmp_path: Path,
) -> None:
    first = _domain(domain_id=None)
    duplicate = _domain(domain_id=None)
    request = _fixture_request(
        tmp_path,
        domain=first,
        extras=[
            (
                "domain-copy",
                "domain_gate_input",
                "bridge://schemas/domain-gate-input/v0.1",
                duplicate,
                "0.1.0",
            )
        ],
    )

    _assert_failed_without_publication(request, "duplicate_logical_object_id")


@pytest.mark.parametrize("duplicate_role", ["measurement_spec", "qc", "measurement"])
def test_duplicate_core_logical_object_ids_fail_even_when_fully_bound(
    tmp_path: Path, duplicate_role: str
) -> None:
    second_domain = _domain(
        domain_gate_input_id="domain-gate-input:case-001:regional-fidelity",
        domain_id="regional_fidelity",
    )
    if duplicate_role == "measurement_spec":
        input_id = "spec-copy"
        second_domain["measurement_spec_input_id"] = input_id
        role = "measurement_spec"
        schema_ref = "bridge://schemas/measurement-spec/v0.1"
        payload = _measurement_spec()
    elif duplicate_role == "qc":
        input_id = "qc-copy"
        second_domain["qc_profile_input_id"] = input_id
        role = "qc_readiness_profile"
        schema_ref = "bridge://schemas/qc-readiness-profile/v0.1"
        payload = _qc()
    elif duplicate_role == "measurement":
        input_id = "measurement-copy"
        second_domain["measurement_result_input_ids"] = [input_id]
        role = "measurement_result"
        schema_ref = "bridge://schemas/measurement-result/v0.1"
        payload = _measurement()
    else:  # pragma: no cover - protects future parameter edits
        raise AssertionError(duplicate_role)
    request = _fixture_request(
        tmp_path,
        extras=[
            (
                "domain-copy",
                "domain_gate_input",
                "bridge://schemas/domain-gate-input/v0.1",
                second_domain,
                "0.1.0",
            ),
            (input_id, role, schema_ref, payload, "0.1.0"),
        ],
    )

    _assert_failed_without_publication(request, "duplicate_logical_object_id")


@pytest.mark.parametrize("record_kind", ["validation", "prior", "sensitivity"])
def test_record_logical_id_cannot_cross_evidence_families(
    tmp_path: Path, record_kind: str
) -> None:
    if record_kind == "validation":
        input_id = "validation-copy"
        role = "validation_record"
        schema_ref = "bridge://schemas/evidence-validation-record/v0.1"
        payload = _validation(
            evidence_family_id="evidence-family:validation-other",
            evidence_refs=["evidence:validation-other"],
        )
        domain = _domain(
            validation_record_input_ids=["target-validation", input_id]
        )
    elif record_kind == "prior":
        input_id = "prior-copy"
        role = "prior_applicability_record"
        schema_ref = "bridge://schemas/prior-applicability-record/v0.1"
        payload = _prior(
            evidence_family_id="evidence-family:prior-other",
            evidence_refs=["evidence:prior-other"],
        )
        domain = _domain(prior_record_input_ids=["target-prior", input_id])
    elif record_kind == "sensitivity":
        input_id = "sensitivity-copy"
        role = "sensitivity_record"
        schema_ref = "bridge://schemas/evidence-sensitivity-record/v0.1"
        payload = _sensitivity(
            evidence_family_id="evidence-family:sensitivity-other",
            evidence_refs=["evidence:sensitivity-other"],
        )
        domain = _domain(
            sensitivity_record_input_ids=["target-sensitivity", input_id]
        )
    else:  # pragma: no cover - protects future parameter edits
        raise AssertionError(record_kind)
    request = _fixture_request(
        tmp_path,
        domain=domain,
        extras=[(input_id, role, schema_ref, payload, "0.1.0")],
    )

    _assert_failed_without_publication(request, "duplicate_logical_object_id")


@pytest.mark.parametrize("record_kind", ["validation", "prior", "sensitivity"])
def test_nonidentical_same_family_logical_records_become_scientific_conflicts(
    tmp_path: Path, record_kind: str
) -> None:
    if record_kind == "validation":
        input_id = "validation-copy"
        role = "validation_record"
        schema_ref = "bridge://schemas/evidence-validation-record/v0.1"
        payload = _validation(evidence_refs=["evidence:validation-copy"])
        domain = _domain(
            validation_record_input_ids=["target-validation", input_id]
        )
        expected_evidence = "evidence:validation-copy"
    elif record_kind == "prior":
        input_id = "prior-copy"
        role = "prior_applicability_record"
        schema_ref = "bridge://schemas/prior-applicability-record/v0.1"
        payload = _prior(evidence_refs=["evidence:prior-copy"])
        domain = _domain(prior_record_input_ids=["target-prior", input_id])
        expected_evidence = "evidence:prior-copy"
    elif record_kind == "sensitivity":
        input_id = "sensitivity-copy"
        role = "sensitivity_record"
        schema_ref = "bridge://schemas/evidence-sensitivity-record/v0.1"
        payload = _sensitivity(evidence_refs=["evidence:sensitivity-copy"])
        domain = _domain(
            sensitivity_record_input_ids=["target-sensitivity", input_id]
        )
        expected_evidence = "evidence:sensitivity-copy"
    else:  # pragma: no cover - protects future parameter edits
        raise AssertionError(record_kind)
    request = _fixture_request(
        tmp_path,
        domain=domain,
        extras=[(input_id, role, schema_ref, payload, "0.1.0")],
    )
    spec = ToolRegistry.load_default().describe("P0-08")

    assert adapter.check_eligibility(request, spec).eligible
    run = adapter.run(request, spec)
    result = EvidenceSufficiencyRunResult.model_validate(run.result)
    profile = result.profiles[0]
    assert run.execution_state is ExecutionState.SUCCEEDED
    assert profile.evidence_sufficiency_state.value == "not_assessed"
    assert "evidence_family_conflict_requires_review" in profile.missing_requirements
    assert expected_evidence in profile.evidence_refs


def test_role_schema_and_unrecognized_role_fail_closed(tmp_path: Path) -> None:
    spec = ToolRegistry.load_default().describe("P0-08")
    request = _fixture_request(tmp_path)
    mismatched = _replace_ref(
        request,
        "target-domain",
        schema_ref="bridge://schemas/measurement-result/v0.1",
    )
    assert "object_input_schema_mismatch" in adapter.check_eligibility(
        mismatched, spec
    ).reason_codes

    unsupported_ref = request.object_inputs[-1].model_copy(
        update={"input_id": "unsupported-extra", "role": "arbitrary_payload"}
    )
    unsupported = request.model_copy(
        update={"object_inputs": [*request.object_inputs, unsupported_ref]}
    )
    assert "unsupported_object_input_role" in adapter.check_eligibility(
        unsupported, spec
    ).reason_codes


def test_filesystem_checksum_media_and_json_failures_are_distinct(tmp_path: Path) -> None:
    spec = ToolRegistry.load_default().describe("P0-08")
    request = _fixture_request(tmp_path)
    missing = _replace_ref(
        request, "target-domain", path=(tmp_path / "does-not-exist.json").resolve()
    )
    assert "structured_input_not_found" in adapter.check_eligibility(
        missing, spec
    ).reason_codes

    dangling_path = tmp_path / "dangling-input.json"
    dangling_path.symlink_to(tmp_path / "absent-target.json")
    dangling = _replace_ref(request, "target-domain", path=dangling_path.absolute())
    assert "structured_input_not_found" in adapter.check_eligibility(
        dangling, spec
    ).reason_codes

    directory = tmp_path / "directory-input"
    directory.mkdir()
    not_file = _replace_ref(request, "target-domain", path=directory.resolve())
    assert "structured_input_not_regular_file" in adapter.check_eligibility(
        not_file, spec
    ).reason_codes

    bad_hash = _replace_ref(request, "target-domain", sha256="0" * 64)
    assert "structured_input_checksum_mismatch" in adapter.check_eligibility(
        bad_hash, spec
    ).reason_codes

    unsupported_media = _replace_ref(
        request, "target-domain", media_type="text/plain"
    )
    assert "structured_input_media_type_unsupported" in adapter.check_eligibility(
        unsupported_media, spec
    ).reason_codes

    target_ref = next(ref for ref in request.object_inputs if ref.input_id == "target-domain")
    target_ref.path.write_text('{"duplicate": 1, "duplicate": 2}\n', encoding="utf-8")
    invalid_json = _replace_ref(
        request,
        "target-domain",
        sha256=hashlib.sha256(target_ref.path.read_bytes()).hexdigest(),
    )
    assert "structured_input_json_invalid" in adapter.check_eligibility(
        invalid_json, spec
    ).reason_codes


def test_object_schema_and_packaged_gate_bytes_are_immutable(tmp_path: Path) -> None:
    spec = ToolRegistry.load_default().describe("P0-08")
    request = _fixture_request(tmp_path)
    domain_ref = next(ref for ref in request.object_inputs if ref.input_id == "target-domain")
    domain_ref.path.write_text("{}\n", encoding="utf-8")
    invalid_schema = _replace_ref(
        request,
        "target-domain",
        sha256=hashlib.sha256(domain_ref.path.read_bytes()).hexdigest(),
    )
    assert "structured_input_schema_invalid" in adapter.check_eligibility(
        invalid_schema, spec
    ).reason_codes

    gate_request = _fixture_request(tmp_path / "gate")
    gate_ref = next(ref for ref in gate_request.object_inputs if ref.input_id == "gate-rules")
    payload = json.loads(gate_ref.path.read_text(encoding="utf-8"))
    payload["status"] = "frozen"
    gate_sha = _write(gate_ref.path, payload)
    alternate_gate = _replace_ref(gate_request, "gate-rules", sha256=gate_sha)
    assert "unsupported_gate_rule_spec" in adapter.check_eligibility(
        alternate_gate, spec
    ).reason_codes


@pytest.mark.parametrize("input_id", ["case-qc", "target-result", "target-spec"])
def test_structured_input_ref_version_is_strict_for_all_input_models(
    tmp_path: Path, input_id: str
) -> None:
    request = _fixture_request(tmp_path)
    mismatched = _replace_ref(request, input_id, object_version="999.0.0")

    _assert_failed_without_publication(mismatched, "structured_input_schema_invalid")


def test_domain_bindings_measurement_and_product_definition_must_agree(
    tmp_path: Path,
) -> None:
    spec = ToolRegistry.load_default().describe("P0-08")
    dangling = _fixture_request(
        tmp_path / "dangling",
        domain=_domain(measurement_result_input_ids=["missing-result"]),
    )
    assert "domain_gate_input_binding_invalid" in adapter.check_eligibility(
        dangling, spec
    ).reason_codes

    measurement = _measurement()
    measurement["measurement_spec_id"] = "MS-OTHER-v0.1"
    mismatch = _fixture_request(tmp_path / "measurement", measurement=measurement)
    assert "domain_input_measurement_spec_mismatch" in adapter.check_eligibility(
        mismatch, spec
    ).reason_codes

    prior = _prior(product_definition_ref="product-definition:other")
    product_mismatch = _fixture_request(tmp_path / "product", prior=prior)
    assert "domain_input_product_definition_mismatch" in adapter.check_eligibility(
        product_mismatch, spec
    ).reason_codes


@pytest.mark.parametrize(
    ("case", "reason"),
    [
        ("product_definition_not_applicable", "domain_input_product_definition_mismatch"),
        ("qc_assay", "domain_input_measurement_spec_mismatch"),
        ("qc_measurement_status", "domain_input_measurement_spec_mismatch"),
        ("validation_modality", "domain_input_measurement_spec_mismatch"),
        ("validation_tool", "domain_input_measurement_spec_mismatch"),
        ("empty_measurement_tools", "domain_input_measurement_spec_mismatch"),
    ],
)
def test_sufficient_path_cross_bindings_fail_eligibility(
    tmp_path: Path, case: str, reason: str
) -> None:
    measurement_spec = _measurement_spec()
    qc = _qc()
    validation = _validation()
    if case == "product_definition_not_applicable":
        measurement_spec["applicable_product_cards"] = ["product-definition:other"]
    elif case == "qc_assay":
        qc["assay"] = "bulk-RNA-seq"
    elif case == "qc_measurement_status":
        qc["measurement_spec_status"] = "candidate"
    elif case == "validation_modality":
        validation["modality"] = "bulk-RNA-seq"
    elif case == "validation_tool":
        validation["tool_ref"] = "P0-04"
    elif case == "empty_measurement_tools":
        measurement_spec["tool_refs"] = []
    else:  # pragma: no cover - protects future parameter edits
        raise AssertionError(case)

    request = _fixture_request(
        tmp_path,
        measurement_spec=measurement_spec,
        qc=qc,
        validation=validation,
    )
    _assert_failed_without_publication(request, reason)


def test_cross_domain_pointer_provenance_order_is_set_like(tmp_path: Path) -> None:
    product_case = {
        "object_id": "product-case:case-001",
        "object_version": "1.0.0",
        "provenance_refs": ["provenance:case-a", "provenance:case-b"],
    }
    product_definition = {
        "object_id": "product-definition:pd-mda-progenitor",
        "object_version": "1.0.0",
        "provenance_refs": ["provenance:definition-a", "provenance:definition-b"],
    }
    first = _domain(
        product_case=product_case,
        product_definition=product_definition,
    )
    second = _domain(
        domain_gate_input_id="domain-gate-input:case-001:regional-fidelity",
        domain_id="regional_fidelity",
        product_case=product_case
        | {"provenance_refs": list(reversed(product_case["provenance_refs"]))},
        product_definition=product_definition
        | {
            "provenance_refs": list(
                reversed(product_definition["provenance_refs"])
            )
        },
    )
    request = _fixture_request(
        tmp_path,
        domain=first,
        extras=[
            (
                "regional-domain",
                "domain_gate_input",
                "bridge://schemas/domain-gate-input/v0.1",
                second,
                "0.1.0",
            )
        ],
    )
    spec = ToolRegistry.load_default().describe("P0-08")

    assert adapter.check_eligibility(request, spec).eligible
    assert adapter.run(request, spec).execution_state is ExecutionState.SUCCEEDED


@pytest.mark.parametrize(
    ("pointer_field", "reason"),
    [
        ("product_case", "multiple_product_cases_in_request"),
        ("product_definition", "domain_input_product_definition_mismatch"),
    ],
)
def test_cross_domain_full_pointer_provenance_conflicts_fail_eligibility(
    tmp_path: Path, pointer_field: str, reason: str
) -> None:
    first = _domain()
    second = _domain(
        domain_gate_input_id="domain-gate-input:case-001:regional-fidelity",
        domain_id="regional_fidelity",
    )
    second[pointer_field] = {
        **second[pointer_field],
        "provenance_refs": ["provenance:conflicting-lineage"],
    }
    request = _fixture_request(
        tmp_path,
        domain=first,
        extras=[
            (
                "regional-domain",
                "domain_gate_input",
                "bridge://schemas/domain-gate-input/v0.1",
                second,
                "0.1.0",
            )
        ],
    )

    _assert_failed_without_publication(request, reason)


def test_duplicate_domain_multiple_cases_and_output_overlap_fail_closed(
    tmp_path: Path,
) -> None:
    spec = ToolRegistry.load_default().describe("P0-08")
    duplicate_domain = _domain(
        domain_gate_input_id="domain-gate-input:case-001:target-copy"
    )
    duplicate_request = _fixture_request(
        tmp_path / "duplicate",
        extras=[
            (
                "domain-copy",
                "domain_gate_input",
                "bridge://schemas/domain-gate-input/v0.1",
                duplicate_domain,
                "0.1.0",
            )
        ],
    )
    assert "duplicate_domain_id" in adapter.check_eligibility(
        duplicate_request, spec
    ).reason_codes

    different_case = _domain(
        domain_gate_input_id="domain-gate-input:case-002:regional-fidelity",
        domain_id="regional_fidelity",
        product_case={
            "object_id": "product-case:case-002",
            "object_version": "1.0.0",
            "provenance_refs": ["provenance:case-002"],
        },
    )
    multiple_case_request = _fixture_request(
        tmp_path / "cases",
        extras=[
            (
                "domain-case-2",
                "domain_gate_input",
                "bridge://schemas/domain-gate-input/v0.1",
                different_case,
                "0.1.0",
            )
        ],
    )
    assert "multiple_product_cases_in_request" in adapter.check_eligibility(
        multiple_case_request, spec
    ).reason_codes

    request = _fixture_request(tmp_path / "overlap")
    input_parent = request.object_inputs[0].path.parent
    overlap = request.model_copy(update={"output_dir": input_parent})
    assert "output_dir_overlaps_structured_input" in adapter.check_eligibility(
        overlap, spec
    ).reason_codes


def test_artifact_bundle_is_deterministic_reusable_and_path_free(tmp_path: Path) -> None:
    first = _run(tmp_path, request_id="first", output_name="output-a")
    second = _run(tmp_path, request_id="second", output_name="output-b")

    assert first.input_hash == second.input_hash
    assert first.run_id == second.run_id
    first_dir = first.artifacts[0].path.parent
    second_dir = second.artifacts[0].path.parent
    scientific_names = {
        "evidence_sufficiency_profiles.json",
        "case_evidence_readiness_summary.json",
        "gate_trace.json",
        "evidence_sufficiency_run_result.json",
    }
    for name in scientific_names:
        assert (first_dir / name).read_bytes() == (second_dir / name).read_bytes()
        text = (first_dir / name).read_text(encoding="utf-8")
        assert str(tmp_path) not in text
        assert "NaN" not in text and "Infinity" not in text
    manifest = json.loads((first_dir / "artifact_manifest.json").read_text())
    assert all(item["filename"] != "artifact_manifest.json" for item in manifest["artifacts"])
    for item in manifest["artifacts"]:
        artifact_path = first_dir / item["filename"]
        assert hashlib.sha256(artifact_path.read_bytes()).hexdigest() == item["sha256"]
    assert len(first.artifacts) == 5

    repeated_request = _fixture_request(tmp_path, request_id="first", output_name="output-a")
    spec = ToolRegistry.load_default().describe("P0-08")
    repeated = adapter.run(repeated_request, spec)
    assert repeated.execution_state is ExecutionState.SUCCEEDED
    assert repeated.run_id == first.run_id

    reordered = repeated_request.model_copy(
        update={"object_inputs": list(reversed(repeated_request.object_inputs))}
    )
    reordered_run = adapter.run(reordered, spec)
    assert reordered_run.run_id == first.run_id
    assert reordered_run.input_hash == first.input_hash


def test_set_like_input_list_order_does_not_change_run_identity_or_result_bytes(
    tmp_path: Path,
) -> None:
    def ordered_request(root: Path, *, reverse: bool) -> ToolRequestV2:
        measurement_spec = _measurement_spec()
        measurement_spec.update(
            {
                "applicable_product_cards": [
                    "product-definition:pd-mda-progenitor",
                    "product-definition:context-only",
                ],
                "tool_refs": ["P0-03", "P0-04"],
                "reference_refs": ["reference:test-v0.1", "reference:second-v0.1"],
                "prior_refs": ["prior:test-v0.1", "prior:second-v0.1"],
            }
        )
        qc = _qc()
        qc.update(
            {
                "missing_inputs": ["missing:a", "missing:b"],
                "blocking_issues": ["issue:a", "issue:b"],
                "warnings": ["warning:a", "warning:b"],
                "evidence_ids": ["evidence:qc-1", "evidence:qc-2"],
            }
        )
        measurement = _measurement()
        measurement["provenance_refs"] = [
            "evidence:measurement-1",
            "run:upstream-1",
        ]
        validation = _validation(
            validation_refs=["validation:test-v0.1", "validation:second-v0.1"],
            evidence_refs=["evidence:validation-1", "evidence:validation-2"],
            provenance_refs=["run:validation-1", "run:validation-2"],
        )
        prior = _prior(
            evidence_refs=["evidence:prior-1", "evidence:prior-2"],
            provenance_refs=["run:prior-1", "run:prior-2"],
        )
        sensitivity = _sensitivity(
            evidence_refs=["evidence:sensitivity-1", "evidence:sensitivity-2"],
            provenance_refs=["run:sensitivity-1", "run:sensitivity-2"],
        )
        domain = _domain(
            product_case={
                "object_id": "product-case:case-001",
                "object_version": "1.0.0",
                "provenance_refs": ["provenance:case-001", "provenance:case-002"],
            },
            product_definition={
                "object_id": "product-definition:pd-mda-progenitor",
                "object_version": "1.0.0",
                "provenance_refs": [
                    "provenance:product-definition-1",
                    "provenance:product-definition-2",
                ],
            },
            measurement_result_input_ids=["target-result", "target-result-2"],
            validation_record_input_ids=["target-validation", "target-validation-2"],
            prior_record_input_ids=["target-prior", "target-prior-2"],
            sensitivity_record_input_ids=["target-sensitivity", "target-sensitivity-2"],
            required_sensitivity_kinds=["reference", "preprocessing"],
            evidence_refs=["evidence:target-raw-1", "evidence:target-raw-2"],
            provenance_refs=["run:target-domain-1", "run:target-domain-2"],
        )
        second_measurement = _measurement()
        second_measurement.update(
            {
                "measurement_id": "measurement:target-2",
                "provenance_refs": ["evidence:measurement-2", "run:upstream-2"],
            }
        )
        second_validation = _validation(
            validation_record_id="validation-record:method-2",
            tool_ref="P0-04",
            evidence_family_id="evidence-family:validation-2",
            validation_refs=["validation:method-2a", "validation:method-2b"],
            evidence_refs=["evidence:validation-3", "evidence:validation-4"],
            provenance_refs=["run:validation-3", "run:validation-4"],
        )
        second_prior = _prior(
            prior_record_id="prior-record:prior-2",
            prior_ref="prior:second-v0.1",
            snapshot_ref="snapshot:second-v0.1",
            evidence_family_id="evidence-family:prior-2",
            evidence_refs=["evidence:prior-3", "evidence:prior-4"],
            provenance_refs=["run:prior-3", "run:prior-4"],
        )
        second_sensitivity = _sensitivity(
            sensitivity_record_id="sensitivity-record:preprocessing-2",
            sensitivity_kind="preprocessing",
            evidence_family_id="evidence-family:sensitivity-2",
            evidence_refs=["evidence:sensitivity-3", "evidence:sensitivity-4"],
            provenance_refs=["run:sensitivity-3", "run:sensitivity-4"],
        )
        set_like_fields = [
            (
                measurement_spec,
                [
                    "applicable_product_cards",
                    "tool_refs",
                    "reference_refs",
                    "prior_refs",
                ],
            ),
            (qc, ["missing_inputs", "blocking_issues", "warnings", "evidence_ids"]),
            (measurement, ["provenance_refs"]),
            (validation, ["validation_refs", "evidence_refs", "provenance_refs"]),
            (prior, ["evidence_refs", "provenance_refs"]),
            (sensitivity, ["evidence_refs", "provenance_refs"]),
            (second_measurement, ["provenance_refs"]),
            (
                second_validation,
                ["validation_refs", "evidence_refs", "provenance_refs"],
            ),
            (second_prior, ["evidence_refs", "provenance_refs"]),
            (second_sensitivity, ["evidence_refs", "provenance_refs"]),
            (
                domain,
                [
                    "measurement_result_input_ids",
                    "validation_record_input_ids",
                    "prior_record_input_ids",
                    "sensitivity_record_input_ids",
                    "required_sensitivity_kinds",
                    "evidence_refs",
                    "provenance_refs",
                ],
            ),
        ]
        if reverse:
            for payload, fields_to_reverse in set_like_fields:
                for field in fields_to_reverse:
                    payload[field] = list(reversed(payload[field]))
            for pointer in (domain["product_case"], domain["product_definition"]):
                pointer["provenance_refs"] = list(
                    reversed(pointer["provenance_refs"])
                )
        extras = [
            (
                "target-result-2",
                "measurement_result",
                "bridge://schemas/measurement-result/v0.1",
                second_measurement,
                "0.1.0",
            ),
            (
                "target-validation-2",
                "validation_record",
                "bridge://schemas/evidence-validation-record/v0.1",
                second_validation,
                "0.1.0",
            ),
            (
                "target-prior-2",
                "prior_applicability_record",
                "bridge://schemas/prior-applicability-record/v0.1",
                second_prior,
                "0.1.0",
            ),
            (
                "target-sensitivity-2",
                "sensitivity_record",
                "bridge://schemas/evidence-sensitivity-record/v0.1",
                second_sensitivity,
                "0.1.0",
            ),
        ]
        request = _fixture_request(
            root,
            domain=domain,
            measurement_spec=measurement_spec,
            qc=qc,
            measurement=measurement,
            validation=validation,
            prior=prior,
            sensitivity=sensitivity,
            extras=extras,
            request_id="semantic-order",
        )
        if reverse:
            request = request.model_copy(
                update={"object_inputs": list(reversed(request.object_inputs))}
            )
        return request

    first_request = ordered_request(tmp_path / "first", reverse=False)
    second_request = ordered_request(tmp_path / "second", reverse=True)
    second_request = second_request.model_copy(
        update={"output_dir": first_request.output_dir}
    )
    spec = ToolRegistry.load_default().describe("P0-08")
    first = adapter.run(first_request, spec)
    first_dir = first.artifacts[0].path.parent
    first_bundle = {
        path.name: path.read_bytes() for path in sorted(first_dir.iterdir())
    }
    second = adapter.run(second_request, spec)

    assert first.execution_state is ExecutionState.SUCCEEDED
    assert second.execution_state is ExecutionState.SUCCEEDED
    assert first.input_hash == second.input_hash
    assert first.run_id == second.run_id
    assert first.result == second.result
    assert first.artifacts[0].path.parent == second.artifacts[0].path.parent
    assert {
        path.name: path.read_bytes() for path in sorted(first_dir.iterdir())
    } == first_bundle
    raw_sha_first = {
        ref.input_id: ref.sha256 for ref in first.request.object_inputs
    }
    raw_sha_second = {
        ref.input_id: ref.sha256 for ref in second.request.object_inputs
    }
    assert any(
        raw_sha_first[input_id] != raw_sha_second[input_id]
        for input_id in raw_sha_first
    )
    manifest = json.loads(
        (first_dir / "artifact_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["structured_input_provenance_policy"] == {
        "bundle_identity": "canonical_semantic_sha256",
        "invocation_source_checksum": "ToolRunV2.request.object_inputs[].sha256",
    }
    assert all(
        "semantic_sha256" in item and "sha256" not in item
        for item in manifest["structured_inputs"]
    )
    for artifact in second.artifacts:
        assert hashlib.sha256(artifact.path.read_bytes()).hexdigest() == artifact.sha256


def test_semantic_input_change_changes_run_identity(tmp_path: Path) -> None:
    first_request = _fixture_request(
        tmp_path / "first", request_id="semantic-first", output_name="output"
    )
    second_request = _fixture_request(
        tmp_path / "second",
        request_id="semantic-second",
        output_name="output",
        validation=_validation(validation_state="candidate"),
    )
    second_request = second_request.model_copy(
        update={"output_dir": first_request.output_dir}
    )
    spec = ToolRegistry.load_default().describe("P0-08")
    first = adapter.run(first_request, spec)
    second = adapter.run(second_request, spec)

    assert first.execution_state is ExecutionState.SUCCEEDED
    assert second.execution_state is ExecutionState.SUCCEEDED
    assert first.input_hash != second.input_hash
    assert first.run_id != second.run_id
    assert (first_request.output_dir / first.run_id).is_dir()
    assert (first_request.output_dir / second.run_id).is_dir()
    assert first.result != second.result


def test_mutated_input_and_drifted_existing_bundle_never_publish_overwrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = _fixture_request(tmp_path, request_id="mutated", output_name="mutation-output")
    spec = ToolRegistry.load_default().describe("P0-08")
    monkeypatch.setattr(adapter_module, "_inputs_unchanged", lambda refs: False)
    changed = adapter.run(request, spec)
    assert changed.execution_state is ExecutionState.FAILED
    assert changed.reason_codes == ["structured_input_modified_during_run"]
    assert not (request.output_dir / changed.run_id).exists()

    monkeypatch.undo()
    clean_request = _fixture_request(tmp_path, request_id="clean", output_name="drift-output")
    clean = adapter.run(clean_request, spec)
    result_path = clean.artifacts[3].path
    result_path.write_text("drift\n", encoding="utf-8")
    drifted = adapter.run(clean_request, spec)
    assert drifted.execution_state is ExecutionState.FAILED
    assert drifted.reason_codes == ["existing_run_bundle_hash_mismatch"]
    assert result_path.read_text(encoding="utf-8") == "drift\n"


def test_domain_gate_input_rejects_duplicate_binding_ids() -> None:
    payload = _domain(
        measurement_result_input_ids=["target-result", "target-result"]
    )
    with pytest.raises(ValueError, match="duplicates"):
        DomainGateInput.model_validate(payload)
