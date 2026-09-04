from __future__ import annotations

import hashlib
import importlib
from importlib.resources import files
import json
import shutil
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
    reason_catalog_sha256,
)
from bridge.tool_packages.p0_08_evidence_sufficiency.executor import REASON_CODES
from bridge.tool_packages.p0_08_evidence_sufficiency.models import (
    PUBLIC_SCHEMA_MODELS,
    DomainGateInput,
    EvidenceSufficiencyProfile,
    EvidenceSufficiencyProfileV2,
    EvidenceSufficiencyRunResultV2 as EvidenceSufficiencyRunResult,
    GateRuleSpec,
    GateRuleSpecV2,
    ReasonCodeCatalog,
    ReasonCodeCatalogV2,
)
from bridge.tool_packages.p0_08_evidence_sufficiency.visualization_data import (
    EVIDENCE_SUFFICIENCY_VISUALIZATION_DATA_SCHEMA_REF,
    P008_COMPONENT_REFS,
    P008_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF,
    EvidenceSufficiencyVisualizationDataV1,
    P008VisualizationArtifactSet,
)
from bridge.toolkit.api import run_tool, validate_request
from bridge.toolkit.contracts import EvidenceState, ExecutionState, ToolRequest, ToolRequestV2
from bridge.toolkit.registry import ToolRegistry
from bridge.toolkit.schemas import load_schema
from bridge.toolkit.visualization import FigureRegistry


adapter_module = importlib.import_module(
    "bridge.tool_packages.p0_08_evidence_sufficiency.adapter"
)
visualization_module = importlib.import_module(
    "bridge.tool_packages.p0_08_evidence_sufficiency.visualization"
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
        "analysis_unit_kind": "preparation",
        "independence_group_kind": "sample",
        "observation_unit_kind": "cell",
        "applicable_contexts": ["context:test-v0.1"],
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
        "measurement_spec_version": "0.1.0",
        "selected_data_view": {
            "view_id": "data-view:case-001:selected",
            "view_kind": "qc_selected_observations",
            "artifact_id": "artifact:case-001:selected",
            "sha256": "a" * 64,
            "parent_asset_id": "asset:case-001",
            "parent_asset_sha256": "b" * 64,
            "matrix_location": "layers/counts",
            "matrix_semantics": "raw_counts",
            "n_observations": 100,
            "observation_ids_sha256": "c" * 64,
            "sample_or_preparation_ref": "preparation:case-001@1.0.0",
            "selection_spec_ref": "QC-scRNA-candidate-v0.1@0.1.0",
            "biological_unit_manifest_ref": None,
            "biological_unit_manifest_sha256": None,
        },
    }


def _measurement(*, evidence_state: str = "measured") -> dict[str, Any]:
    return {
        "measurement_id": "measurement:target-1",
        "measurement_spec_id": "MS-TARGET-v0.1",
        "measurement_spec_version": "0.1.0",
        "metric_name": "upstream_target_evidence",
        "raw_value": (
            None
            if evidence_state in {"missing", "unavailable"}
            else {"state": evidence_state}
        ),
        "numerator": None,
        "denominator": None,
        "interval": None,
        "domain_score": None,
        "score_state": "unavailable",
        "evidence_state": evidence_state,
        "source_run_ref": "tool-run:upstream-1@0.2.0",
        "source_execution_state": "succeeded",
        "unknown_scope": "identity" if evidence_state == "unknown" else None,
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
        "evidence_family_id": "family:validation-1",
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
        "evidence_family_id": "family:prior-1",
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
        "evidence_family_id": "family:sensitivity-1",
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


def _product_case(**overrides: Any) -> dict[str, Any]:
    payload = {
        "object_version": "0.1.0",
        "product_case_id": "product-case:case-001",
        "case_version": "1.0.0",
        "product_definition_ref": {
            "object_id": "product-definition:pd-mda-progenitor",
            "object_version": "1.0.0",
        },
        "source_unit_kind": "preparation",
        "sample_or_preparation_ref": {
            "object_id": "preparation:case-001",
            "object_version": "1.0.0",
        },
        "independence_group_refs": [],
        "biological_unit_manifest_ref": None,
        "biological_unit_manifest_sha256": None,
        "independence_scope_ref": None,
        "measurement_spec_ref": {
            "object_id": "measurement-spec:cell-state-source",
            "object_version": "1.0.0",
        },
        "assay": "scRNA-seq",
        "provenance_refs": [
            {
                "object_id": "provenance:case-001",
                "object_version": "1.0.0",
            }
        ],
        "created_at": "2026-08-13T00:00:00Z",
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


def _sparse_domain() -> dict[str, Any]:
    return _domain(
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


def _fixture_request(
    tmp_path: Path,
    *,
    domain: dict[str, Any] | None = None,
    product_case: dict[str, Any] | None = None,
    include_product_case: bool = True,
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
    gate_path = input_root / "gate_rule_spec_v0.2.json"
    gate_path.write_bytes(
        files("bridge.tool_packages.p0_08_evidence_sufficiency.resources")
        .joinpath("gate_rule_spec_v0.2.json")
        .read_bytes()
    )
    refs: list[dict[str, Any]] = [
        {
            "input_id": "gate-rules",
            "role": "gate_rule_spec",
            "schema_ref": "bridge://schemas/evidence-sufficiency-gate-rule-spec/v0.2",
            "object_version": "0.2.0",
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
    if include_product_case:
        entries.append(
            (
                "product-case",
                "product_case",
                "bridge://schemas/product-case/v0.1",
                product_case if product_case is not None else _product_case(),
                "0.1.0",
            )
        )
    candidates = [
        (
            "target-spec",
            "measurement_spec",
            "bridge://schemas/measurement-spec/v0.2",
            measurement_spec if measurement_spec is not None else _measurement_spec(),
            "0.1.0",
        ),
        (
            "case-qc",
            "qc_readiness_profile",
            "bridge://schemas/qc-readiness-profile/v0.2",
            qc if qc is not None else _qc(),
            "0.2.0",
        ),
        (
            "target-result",
            "measurement_result",
            "bridge://schemas/measurement-result/v0.2",
            measurement if measurement is not None else _measurement(),
            "0.2.0",
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
        tool_version="0.5.0",
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

    assert gate.gate_rule_spec_id == "GATE-EVIDENCE-SUFFICIENCY-v0.2"
    assert gate.object_version == "0.2.0"
    assert gate.reason_code_catalog_ref.endswith("/v0.2")
    assert catalog.catalog_id == "BRIDGE-REASON-CODE-CATALOG-v0.2"
    assert catalog.object_version == "0.2.0"
    assert gate.status.value == "candidate"
    assert gate.precedence == ("not_assessed", "insufficient", "limited", "sufficient")
    assert tuple(reason.code for reason in catalog.reasons) == REASON_CODES
    assert len(catalog.reasons) == 49


@pytest.mark.parametrize(
    ("package", "filename", "expected_sha256"),
    [
        (
            "bridge.tool_packages.p0_08_evidence_sufficiency.resources",
            "gate_rule_spec_v0.1.json",
            "733c47448edb80af564d0631c236466b930aa64e92c03e3f655e447a5aa7f445",
        ),
        (
            "bridge.tool_packages.p0_08_evidence_sufficiency.resources",
            "reason_code_catalog_v0.1.json",
            "53a53bfb95b7fc40aa8d3e1a8b3f7abf2c1dcbe7de7051a8a71c15bccdfbf9c6",
        ),
        (
            "bridge.resources.schemas",
            "evidence_sufficiency_gate_rule_spec.schema.json",
            "5d9459a4f5875ff85273518dc86fe667392ebeb8594554c83747f824b10439df",
        ),
        (
            "bridge.resources.schemas",
            "evidence_sufficiency_reason_code_catalog.schema.json",
            "77ef221d96425de6069f0c117d3a69805523fad1e7db81cca5cd922a6b4f3562",
        ),
    ],
)
def test_v01_gate_resources_and_schemas_remain_byte_identical(
    package: str, filename: str, expected_sha256: str
) -> None:
    raw = files(package).joinpath(filename).read_bytes()

    assert hashlib.sha256(raw).hexdigest() == expected_sha256


def test_v01_gate_contracts_do_not_validate_as_v02() -> None:
    resources = files("bridge.tool_packages.p0_08_evidence_sufficiency.resources")
    gate_v1 = json.loads(resources.joinpath("gate_rule_spec_v0.1.json").read_bytes())
    catalog_v1 = json.loads(
        resources.joinpath("reason_code_catalog_v0.1.json").read_bytes()
    )

    GateRuleSpec.model_validate(gate_v1)
    ReasonCodeCatalog.model_validate(catalog_v1)
    with pytest.raises(ValueError):
        GateRuleSpecV2.model_validate(gate_v1)
    with pytest.raises(ValueError):
        ReasonCodeCatalogV2.model_validate(catalog_v1)


def test_p0_08_v03_rejects_v01_gate_binding(tmp_path: Path) -> None:
    request = _fixture_request(tmp_path)
    legacy_path = tmp_path / "legacy_gate_rule_spec_v0.1.json"
    legacy_bytes = (
        files("bridge.tool_packages.p0_08_evidence_sufficiency.resources")
        .joinpath("gate_rule_spec_v0.1.json")
        .read_bytes()
    )
    legacy_path.write_bytes(legacy_bytes)
    legacy_request = _replace_ref(
        request,
        "gate-rules",
        schema_ref="bridge://schemas/evidence-sufficiency-gate-rule-spec/v0.1",
        object_version="0.1.0",
        path=legacy_path,
        sha256=hashlib.sha256(legacy_bytes).hexdigest(),
    )

    _assert_failed_without_publication(
        legacy_request, "object_input_schema_mismatch"
    )

def test_v01_profile_model_rejects_v02_reason_codes(tmp_path: Path) -> None:
    run = _run(tmp_path)
    profile_v2 = EvidenceSufficiencyRunResult.model_validate(run.result).profiles[0]
    payload = profile_v2.model_dump(mode="json")
    payload["profile_version"] = "0.1.0"
    payload["gate_rule_spec_ref"] = "GATE-EVIDENCE-SUFFICIENCY-v0.1"
    payload["gate_rule_version"] = "0.1.0"
    for field in (
        "product_case_ref",
        "product_definition_ref",
        "measurement_spec_ref",
        "qc_profile_ref",
    ):
        pointer = payload[field]
        payload[field] = (
            None
            if pointer is None
            else pointer["object_id"]
        )
    payload["measurement_result_refs"] = [
        item["object_id"]
        for item in payload["measurement_result_refs"]
    ]
    payload.pop("measurement_evidence_state_counts")

    EvidenceSufficiencyProfile.model_validate(payload)
    payload["data_reason_codes"] = ["measurement_state_missing"]
    with pytest.raises(ValueError, match="unknown P0-08 reason code"):
        EvidenceSufficiencyProfile.model_validate(payload)



@pytest.mark.parametrize("schema_ref,model", PUBLIC_SCHEMA_MODELS.items())
def test_module_models_round_trip_through_draft_2020_12(
    schema_ref: str, model: type[Any]
) -> None:
    schema = model.model_json_schema()
    Draft202012Validator.check_schema(schema)
    assert schema["additionalProperties"] is False
    assert schema_ref.startswith("bridge://schemas/")


def test_public_schemas_describe_the_checksummed_product_case_binding() -> None:
    expected = (
        "Versioned pointer declared inside DomainGateInput and, when present, "
        "validated against the checksummed ProductCase supplied to P0-08."
    )
    profile_schema = load_schema(
        "bridge://schemas/evidence-sufficiency-profile/v0.2"
    )
    result_schema = load_schema(RESULT_SCHEMA_REF)

    assert (
        profile_schema["properties"]["product_case_ref"]["description"]
        == expected
    )
    assert (
        result_schema["$defs"]["EvidenceSufficiencyProfileV2"]["properties"]
        ["product_case_ref"]["description"]
        == expected
    )


def test_sufficient_raw_evidence_never_enables_a_domain_score(tmp_path: Path) -> None:
    run = _run(tmp_path)

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.measurements == []
    assert run.visualizations == []
    assert run.result_schema_ref == RESULT_SCHEMA_REF
    result = EvidenceSufficiencyRunResult.model_validate(run.result)
    profile = result.profiles[0]
    source_by_input_id = {
        binding.input_id: binding for binding in result.source_object_bindings
    }
    assert profile.evidence_sufficiency_state.value == "sufficient"
    assert profile.domain_score is None
    assert profile.score_state.value == "unavailable"
    assert profile.score_reason_codes == ["p0_score_contract_unavailable"]
    assert profile.product_case_ref is not None
    assert profile.product_case_ref.ref == "product-case:case-001@1.0.0"
    assert profile.measurement_spec_ref is not None
    assert profile.measurement_spec_ref.ref == "MS-TARGET-v0.1@0.1.0"
    assert profile.measurement_result_refs[0].ref == "measurement:target-1@0.2.0"
    assert set(source_by_input_id) == {
        ref.input_id for ref in run.request.object_inputs
    }
    for ref in run.request.object_inputs:
        binding = source_by_input_id[ref.input_id]
        assert binding.role == ref.role
        expected_version = (
            result.case_summary.product_case_ref.object_version
            if ref.role == "product_case"
            and result.case_summary.product_case_ref is not None
            else ref.object_version
        )
        assert binding.object_version == expected_version
        assert binding.schema_ref == ref.schema_ref
        assert binding.source_sha256 == ref.sha256
        assert "path" not in binding.model_dump(mode="json")
    measurement_binding = source_by_input_id["target-result"]
    assert measurement_binding.logical_object_id == "measurement:target-1"
    assert profile.measurement_evidence_state_counts.model_dump() == {
        state: int(state == "measured")
        for state in (
            "measured",
            "inferred",
            "prior_only",
            "negative",
            "missing",
            "unknown",
            "unavailable",
            "alert",
        )
    }


def test_v2_result_binds_exact_product_case_source_to_summary(tmp_path: Path) -> None:
    run = _run(tmp_path)
    result = EvidenceSufficiencyRunResult.model_validate(run.result)

    case_bindings = [
        binding
        for binding in result.source_object_bindings
        if binding.role == "product_case"
    ]
    product_case_input = next(
        ref for ref in run.request.object_inputs if ref.role == "product_case"
    )
    assert result.case_summary.product_case_ref is not None
    assert len(case_bindings) == 1
    assert product_case_input.object_version == "0.1.0"
    assert case_bindings[0].object_version == "1.0.0"
    assert case_bindings[0].ref == result.case_summary.product_case_ref.ref
    assert case_bindings[0].schema_ref == product_case_input.schema_ref
    assert case_bindings[0].source_sha256 == product_case_input.sha256
    assert all(
        profile.product_case_ref == result.case_summary.product_case_ref
        for profile in result.profiles
    )


@pytest.mark.parametrize(
    "case_refs",
    [
        [],
        [
            ("product-case:case-001", "1.0.0"),
            ("product-case:case-001", "1.0.0"),
        ],
        [("product-case:case-002", "1.0.0")],
        [("product-case:case-001", "2.0.0")],
    ],
    ids=["missing", "duplicate", "id-mismatch", "version-mismatch"],
)
def test_v2_result_requires_one_exact_product_case_source_binding(
    tmp_path: Path,
    case_refs: list[tuple[str, str]],
) -> None:
    result = EvidenceSufficiencyRunResult.model_validate(_run(tmp_path).result)
    payload = result.model_dump(mode="json")
    template = next(
        binding
        for binding in payload["source_object_bindings"]
        if binding["role"] == "product_case"
    )
    payload["source_object_bindings"] = [
        binding
        for binding in payload["source_object_bindings"]
        if binding["role"] != "product_case"
    ]
    payload["source_object_bindings"].extend(
        {
            **template,
            "input_id": f"product-case-{index}",
            "logical_object_id": object_id,
            "object_version": object_version,
        }
        for index, (object_id, object_version) in enumerate(case_refs)
    )
    payload["source_object_bindings"].sort(
        key=lambda binding: (binding["role"], binding["input_id"])
    )

    with pytest.raises(
        ValueError,
        match="result must bind its exact ProductCase source object",
    ):
        EvidenceSufficiencyRunResult.model_validate(payload)


def test_v2_result_rejects_profile_product_case_summary_mismatch(
    tmp_path: Path,
) -> None:
    result = EvidenceSufficiencyRunResult.model_validate(_run(tmp_path).result)
    payload = result.model_dump(mode="json")
    payload["profiles"][0]["product_case_ref"] = {
        "object_id": "product-case:case-002",
        "object_version": "1.0.0",
    }

    with pytest.raises(
        ValueError, match="case summary product case must match profiles"
    ):
        EvidenceSufficiencyRunResult.model_validate(payload)


def test_v2_result_rejects_null_case_profile_in_case_bound_multi_domain_result(
    tmp_path: Path,
) -> None:
    case_bound_sparse_domain = _domain(
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
    )
    run = _run(
        tmp_path,
        extras=[
            (
                "off-target-domain",
                "domain_gate_input",
                "bridge://schemas/domain-gate-input/v0.1",
                case_bound_sparse_domain,
                "0.1.0",
            )
        ],
    )
    result = EvidenceSufficiencyRunResult.model_validate(run.result)
    payload = result.model_dump(mode="json")
    sparse_profile = next(
        profile
        for profile in payload["profiles"]
        if profile["domain_id"] == "off_target_control"
    )
    assert sparse_profile["evidence_sufficiency_state"] == "not_assessed"
    sparse_profile["product_case_ref"] = None

    with pytest.raises(
        ValueError,
        match="profile ProductCase refs must match the case summary",
    ):
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
                "bridge://schemas/qc-readiness-profile/v0.2",
                _qc(readiness_state="limited") | {"profile_id": "qc-profile:limited"},
                "0.2.0",
            ),
            (
                "qc-blocked",
                "qc_readiness_profile",
                "bridge://schemas/qc-readiness-profile/v0.2",
                _qc(readiness_state="blocked") | {"profile_id": "qc-profile:blocked"},
                "0.2.0",
            ),
            (
                "validation-candidate",
                "validation_record",
                "bridge://schemas/evidence-validation-record/v0.1",
                _validation(
                    validation_record_id="validation-record:method-1",
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
    assert len(run.artifacts) == 19 + len(result.profiles) == 24
    assert [
        artifact.path.name
        for artifact in run.artifacts
        if artifact.kind == "evidence_sufficiency_profile"
    ] == [f"evidence_sufficiency_profile_{index:02d}.json" for index in range(1, 6)]


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
    sparse = _sparse_domain()
    run = _run(tmp_path, domain=sparse, include_product_case=False)
    result = EvidenceSufficiencyRunResult.model_validate(run.result)
    profile = result.profiles[0]

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert profile.evidence_sufficiency_state.value == "not_assessed"
    assert "product_case_not_declared" in profile.missing_requirements
    assert "raw_evidence_gate_not_assessed" in profile.missing_requirements
    assert profile.blocking_reasons == []
    assert result.case_summary.blocking_reasons == []
    assert result.case_summary.product_case_ref is None
    assert not any(
        binding.role == "product_case"
        for binding in result.source_object_bindings
    )
    assert profile.domain_score is None


def test_sparse_v2_result_rejects_unexpected_product_case_source_binding(
    tmp_path: Path,
) -> None:
    sparse = _sparse_domain()
    result = EvidenceSufficiencyRunResult.model_validate(
        _run(tmp_path, domain=sparse, include_product_case=False).result
    )
    payload = result.model_dump(mode="json")
    payload["source_object_bindings"].append(
        {
            "input_id": "unexpected-product-case",
            "role": "product_case",
            "logical_object_id": "product-case:case-001",
            "object_version": "1.0.0",
            "schema_ref": "bridge://schemas/product-case/v0.1",
            "source_sha256": "a" * 64,
        }
    )
    payload["source_object_bindings"].sort(
        key=lambda binding: (binding["role"], binding["input_id"])
    )

    with pytest.raises(
        ValueError,
        match=(
            "result must not bind a ProductCase source object without a case summary"
        ),
    ):
        EvidenceSufficiencyRunResult.model_validate(payload)


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
    run = _run(
        tmp_path,
        domain=domain,
        validation=_validation(
            source_holdout_state="not_required",
            modality_holdout_state="not_required",
            calibration_state="not_required",
            ood_state="not_required",
        ),
    )
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


@pytest.mark.parametrize(
    "field",
    [
        "source_holdout_state",
        "modality_holdout_state",
        "calibration_state",
        "ood_state",
    ],
)
def test_learned_validation_cannot_omit_required_coverage(
    tmp_path: Path, field: str
) -> None:
    run = _run(
        tmp_path,
        validation=_validation(method_kind="learned", **{field: "not_required"}),
    )
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
    ("evidence_state", "expected_sufficiency", "expected_reason"),
    [
        ("measured", "sufficient", None),
        ("inferred", "sufficient", None),
        ("prior_only", "sufficient", None),
        ("negative", "sufficient", None),
        ("missing", "not_assessed", "measurement_state_missing"),
        ("unknown", "not_assessed", "measurement_state_unknown"),
        ("unavailable", "not_assessed", "measurement_state_unavailable"),
        ("alert", "sufficient", None),
    ],
)
def test_raw_measurement_state_is_not_reinterpreted(
    tmp_path: Path,
    evidence_state: str,
    expected_sufficiency: str,
    expected_reason: str | None,
) -> None:
    run = _run(tmp_path, measurement=_measurement(evidence_state=evidence_state))
    result = EvidenceSufficiencyRunResult.model_validate(run.result)
    profile = result.profiles[0]

    assert profile.evidence_sufficiency_state.value == expected_sufficiency
    assert getattr(profile.measurement_evidence_state_counts, evidence_state) == 1
    assert profile.measurement_evidence_state_counts.total == 1
    assert getattr(
        result.case_summary.measurement_evidence_state_counts, evidence_state
    ) == 1
    if expected_reason is None:
        assert not any(
            reason.startswith("measurement_state_")
            for reason in profile.data_reason_codes
        )
    else:
        assert expected_reason in profile.data_reason_codes
        assert expected_reason in profile.missing_requirements
        assert "raw_evidence_gate_not_assessed" in profile.missing_requirements
    assert profile.domain_score is None


def test_assessed_measurement_requires_upstream_tool_run_provenance(
    tmp_path: Path,
) -> None:
    measurement = _measurement()
    measurement["source_run_ref"] = None
    measurement["source_execution_state"] = None

    run = _run(tmp_path, measurement=measurement)
    profile = EvidenceSufficiencyRunResult.model_validate(run.result).profiles[0]

    assert profile.data_readiness.value == "not_assessed"
    assert profile.evidence_sufficiency_state.value == "not_assessed"
    assert "measurement_source_run_not_provided" in profile.data_reason_codes
    assert "measurement_source_run_not_provided" in profile.missing_requirements


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
    assert result.profiles[0].deduplicated_evidence_family_ids.count("family:validation-1") == 1


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
        evidence_family_id="family:optional",
        required_for_interpretation=False,
    )
    optional_b = _validation(
        validation_record_id="validation-record:optional-b",
        evidence_family_id="family:optional",
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
        "bridge://schemas/measurement-result/v0.2",
        extra_payload,
        "0.2.0",
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
                "bridge://schemas/measurement-spec/v0.2",
                _measurement_spec(),
                "0.1.0",
            ),
            (
                "case qc",
                "qc_readiness_profile",
                "bridge://schemas/qc-readiness-profile/v0.2",
                _qc(),
                "0.2.0",
            ),
            (
                "target result",
                "measurement_result",
                "bridge://schemas/measurement-result/v0.2",
                _measurement(),
                "0.2.0",
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
        tool_version="0.5.0",
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
        schema_ref = "bridge://schemas/measurement-spec/v0.2"
        payload = _measurement_spec()
    elif duplicate_role == "qc":
        input_id = "qc-copy"
        second_domain["qc_profile_input_id"] = input_id
        role = "qc_readiness_profile"
        schema_ref = "bridge://schemas/qc-readiness-profile/v0.2"
        payload = _qc()
    elif duplicate_role == "measurement":
        input_id = "measurement-copy"
        second_domain["measurement_result_input_ids"] = [input_id]
        role = "measurement_result"
        schema_ref = "bridge://schemas/measurement-result/v0.2"
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
            (
                input_id,
                role,
                schema_ref,
                payload,
                "0.1.0" if role == "measurement_spec" else "0.2.0",
            ),
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
            evidence_family_id="family:validation-other",
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
            evidence_family_id="family:prior-other",
            evidence_refs=["evidence:prior-other"],
        )
        domain = _domain(prior_record_input_ids=["target-prior", input_id])
    elif record_kind == "sensitivity":
        input_id = "sensitivity-copy"
        role = "sensitivity_record"
        schema_ref = "bridge://schemas/evidence-sensitivity-record/v0.1"
        payload = _sensitivity(
            evidence_family_id="family:sensitivity-other",
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
        schema_ref="bridge://schemas/measurement-result/v0.2",
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


@pytest.mark.parametrize(
    "input_id",
    ["product-case", "case-qc", "target-result", "target-spec"],
)
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
        ("measurement_result_version", "domain_input_measurement_spec_mismatch"),
        ("validation_modality", "domain_input_measurement_spec_mismatch"),
        ("validation_tool", "domain_input_measurement_spec_mismatch"),
        ("empty_measurement_tools", "domain_input_measurement_spec_mismatch"),
        ("qc_tool_ineligible", "domain_input_measurement_spec_mismatch"),
        ("qc_generic_blocked", "domain_input_measurement_spec_mismatch"),
        ("validation_context", "domain_input_measurement_spec_mismatch"),
        ("validation_ref", "domain_input_measurement_spec_mismatch"),
        ("prior_ref", "domain_input_measurement_spec_mismatch"),
    ],
)
def test_sufficient_path_cross_bindings_fail_eligibility(
    tmp_path: Path, case: str, reason: str
) -> None:
    measurement_spec = _measurement_spec()
    qc = _qc()
    measurement = _measurement()
    validation = _validation()
    prior = _prior()
    if case == "product_definition_not_applicable":
        measurement_spec["applicable_product_cards"] = ["product-definition:other"]
    elif case == "qc_assay":
        qc["assay"] = "bulk-RNA-seq"
    elif case == "measurement_result_version":
        measurement["measurement_spec_version"] = "9.9.9"
    elif case == "validation_modality":
        validation["modality"] = "bulk-RNA-seq"
    elif case == "validation_tool":
        validation["tool_ref"] = "P0-04"
    elif case == "empty_measurement_tools":
        measurement_spec["tool_refs"] = []
    elif case == "qc_tool_ineligible":
        qc["module_eligibility"]["P0-03"] = "ineligible"
    elif case == "qc_generic_blocked":
        qc["module_eligibility"]["downstream_scientific_modules"] = "blocked"
    elif case == "validation_context":
        validation["context_of_use_ref"] = "context:other-v0.1"
    elif case == "validation_ref":
        measurement_spec["validation_ref"] = "validation-record:other"
    elif case == "prior_ref":
        prior["prior_ref"] = "prior:other-v0.1"
    else:  # pragma: no cover - protects future parameter edits
        raise AssertionError(case)

    request = _fixture_request(
        tmp_path,
        measurement_spec=measurement_spec,
        qc=qc,
        measurement=measurement,
        validation=validation,
        prior=prior,
    )
    _assert_failed_without_publication(request, reason)


@pytest.mark.parametrize(
    "domain",
    [
        _domain(prior_requirement="not_required"),
        _domain(required_sensitivity_kinds=[]),
    ],
)
def test_requirement_contradictions_fail_eligibility(
    tmp_path: Path, domain: dict[str, Any]
) -> None:
    request = _fixture_request(tmp_path, domain=domain)

    _assert_failed_without_publication(
        request, "domain_input_measurement_spec_mismatch"
    )


def test_qc_profile_measurement_contract_is_independent_of_domain_spec(
    tmp_path: Path,
) -> None:
    qc = _qc()
    qc["measurement_spec_status"] = "candidate"
    qc["measurement_spec_version"] = "9.9.9"

    request = _fixture_request(tmp_path, qc=qc)
    spec = ToolRegistry.load_default().describe("P0-08")

    assert adapter.check_eligibility(request, spec).eligible


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("object_id", "product-case:other"),
        ("object_version", "9.9.9"),
        ("provenance_refs", ["provenance:other"]),
    ],
)
def test_product_case_pointer_must_match_checksummed_case(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    pointer = dict(_domain()["product_case"])
    pointer[field] = value
    request = _fixture_request(tmp_path, domain=_domain(product_case=pointer))

    _assert_failed_without_publication(request, "domain_gate_input_binding_invalid")


def test_product_definition_pointer_must_match_product_case(
    tmp_path: Path,
) -> None:
    domain = _domain(
        product_definition={
            "object_id": "product-definition:other",
            "object_version": "1.0.0",
            "provenance_refs": ["provenance:product-definition"],
        }
    )
    request = _fixture_request(tmp_path, domain=domain)
    _assert_failed_without_publication(
        request,
        "domain_input_product_definition_mismatch",
    )

def test_product_case_is_required_for_qc_bound_domain(tmp_path: Path) -> None:

    request = _fixture_request(tmp_path, include_product_case=False)

    _assert_failed_without_publication(request, "domain_gate_input_binding_invalid")


@pytest.mark.parametrize(
    ("case", "reason"),
    [
        ("missing_view", "qc_selected_data_view_required"),
        ("sample", "product_case_data_view_binding_mismatch"),
        ("manifest_ref", "product_case_data_view_binding_mismatch"),
        ("manifest_sha", "product_case_data_view_binding_mismatch"),
    ],
)
def test_qc_selected_view_must_match_product_case(
    tmp_path: Path,
    case: str,
    reason: str,
) -> None:
    manifest_ref = {
        "object_id": "biological-unit-manifest:case-001",
        "object_version": "1.0.0",
    }
    product_case = _product_case(
        biological_unit_manifest_ref=manifest_ref,
        biological_unit_manifest_sha256="d" * 64,
        independence_scope_ref={
            "object_id": "independence-scope:case-001",
            "object_version": "1.0.0",
        },
    )
    qc = _qc()
    qc["selected_data_view"].update(
        {
            "biological_unit_manifest_ref": (
                "biological-unit-manifest:case-001@1.0.0"
            ),
            "biological_unit_manifest_sha256": "d" * 64,
        }
    )
    if case == "missing_view":
        qc["selected_data_view"] = None
    elif case == "sample":
        qc["selected_data_view"]["sample_or_preparation_ref"] = (
            "preparation:other@1.0.0"
        )
    elif case == "manifest_ref":
        qc["selected_data_view"]["biological_unit_manifest_ref"] = (
            "biological-unit-manifest:other@1.0.0"
        )
    elif case == "manifest_sha":
        qc["selected_data_view"]["biological_unit_manifest_sha256"] = "e" * 64
    else:  # pragma: no cover - protects future parameter edits
        raise AssertionError(case)

    request = _fixture_request(tmp_path, product_case=product_case, qc=qc)

    _assert_failed_without_publication(request, reason)


@pytest.mark.parametrize(
    ("module_eligibility", "expected"),
    [
        ({}, False),
        ({"P0-03": "unknown"}, False),
        ({"P0-03": "eligible"}, True),
        ({"P0-03": "conditional"}, True),
        ({"downstream_scientific_modules": "eligible"}, True),
    ],
)
def test_qc_tool_authorization_is_positive_and_fail_closed(
    tmp_path: Path,
    module_eligibility: dict[str, str],
    expected: bool,
) -> None:
    qc = _qc()
    qc["module_eligibility"] = module_eligibility
    request = _fixture_request(tmp_path, qc=qc)
    spec = ToolRegistry.load_default().describe("P0-08")

    eligibility = adapter.check_eligibility(request, spec)

    assert eligibility.eligible is expected
    if not expected:
        assert "domain_input_measurement_spec_mismatch" in eligibility.reason_codes


def test_product_case_source_measurement_spec_is_independent_of_domain_spec(
    tmp_path: Path,
) -> None:
    product_case = _product_case()
    measurement_spec = _measurement_spec()
    assert (
        product_case["measurement_spec_ref"]["object_id"]
        != measurement_spec["measurement_spec_id"]
    )

    request = _fixture_request(
        tmp_path,
        product_case=product_case,
        measurement_spec=measurement_spec,
    )
    spec = ToolRegistry.load_default().describe("P0-08")

    assert adapter.check_eligibility(request, spec).eligible


def test_qc_measurement_spec_version_may_be_explicitly_absent(
    tmp_path: Path,
) -> None:
    qc = _qc()
    qc["measurement_spec_version"] = None

    request = _fixture_request(tmp_path, qc=qc)
    spec = ToolRegistry.load_default().describe("P0-08")

    assert adapter.check_eligibility(request, spec).eligible


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
        product_case=_product_case(
            provenance_refs=[
                {"object_id": "provenance:case-a", "object_version": "1"},
                {"object_id": "provenance:case-b", "object_version": "1"},
            ]
        ),
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
        "evidence_sufficiency_profile_01.json",
    }
    for name in scientific_names:
        assert (first_dir / name).read_bytes() == (second_dir / name).read_bytes()
        text = (first_dir / name).read_text(encoding="utf-8")
        assert str(tmp_path) not in text
        assert "NaN" not in text and "Infinity" not in text
    manifest = json.loads((first_dir / "artifact_manifest.json").read_text())
    assert len(manifest["artifacts"]) == 19
    assert {item["filename"] for item in manifest["artifacts"]} == {
        path.name for path in first_dir.iterdir() if path.name != "artifact_manifest.json"
    }
    assert all(item["filename"] != "artifact_manifest.json" for item in manifest["artifacts"])
    for item in manifest["artifacts"]:
        artifact_path = first_dir / item["filename"]
        assert hashlib.sha256(artifact_path.read_bytes()).hexdigest() == item["sha256"]
    profiles_projection = json.loads(
        (first_dir / "evidence_sufficiency_profiles.json").read_text()
    )
    assert profiles_projection["projection_kind"] == (
        "noncanonical_convenience_projection"
    )
    assert profiles_projection["canonical_result_ref"] == first.result["result_id"]
    assert "schema_ref" not in profiles_projection
    profile_payload = json.loads(
        (first_dir / "evidence_sufficiency_profile_01.json").read_text()
    )
    assert EvidenceSufficiencyProfileV2.model_validate(profile_payload).profile_id
    assert len(first.artifacts) == 20
    assert {path.name: path.read_bytes() for path in first_dir.iterdir()} == {
        path.name: path.read_bytes() for path in second_dir.iterdir()
    }

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


def test_object_input_order_does_not_change_run_identity_or_result_bytes(
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
                "module_eligibility": {
                    "P0-03": "eligible",
                    "P0-04": "conditional",
                },
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
            evidence_family_id="family:validation-2",
            validation_refs=["validation:method-2a", "validation:method-2b"],
            evidence_refs=["evidence:validation-3", "evidence:validation-4"],
            provenance_refs=["run:validation-3", "run:validation-4"],
        )
        second_prior = _prior(
            prior_record_id="prior-record:prior-2",
            prior_ref="prior:second-v0.1",
            snapshot_ref="snapshot:second-v0.1",
            evidence_family_id="family:prior-2",
            evidence_refs=["evidence:prior-3", "evidence:prior-4"],
            provenance_refs=["run:prior-3", "run:prior-4"],
        )
        second_sensitivity = _sensitivity(
            sensitivity_record_id="sensitivity-record:preprocessing-2",
            sensitivity_kind="preprocessing",
            evidence_family_id="family:sensitivity-2",
            evidence_refs=["evidence:sensitivity-3", "evidence:sensitivity-4"],
            provenance_refs=["run:sensitivity-3", "run:sensitivity-4"],
        )
        extras = [
            (
                "target-result-2",
                "measurement_result",
                "bridge://schemas/measurement-result/v0.2",
                second_measurement,
                "0.2.0",
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
            product_case=_product_case(
                provenance_refs=[
                    {
                        "object_id": "provenance:case-001",
                        "object_version": "1",
                    },
                    {
                        "object_id": "provenance:case-002",
                        "object_version": "1",
                    },
                ]
            ),
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
    assert raw_sha_first == raw_sha_second
    manifest = json.loads(
        (first_dir / "artifact_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["structured_input_provenance_policy"] == {
        "bundle_identity": "canonical_semantic_sha256_with_exact_source_sha256",
        "invocation_source_checksum": "ToolRunV2.request.object_inputs[].sha256",
        "result_source_checksum": "source_object_bindings[].source_sha256",
    }
    assert all(
        "semantic_sha256" in item
        for item in manifest["structured_inputs"]
    )
    assert all("source_sha256" in item for item in manifest["structured_inputs"])
    for artifact in second.artifacts:
        assert hashlib.sha256(artifact.path.read_bytes()).hexdigest() == artifact.sha256


def test_measurement_source_bytes_are_bound_into_run_identity(
    tmp_path: Path,
) -> None:
    first_measurement = _measurement()
    second_measurement = _measurement()
    second_measurement["provenance_refs"] = list(
        reversed(second_measurement["provenance_refs"])
    )
    first_request = _fixture_request(
        tmp_path / "first",
        measurement=first_measurement,
        request_id="measurement-bytes-first",
    )
    second_request = _fixture_request(
        tmp_path / "second",
        measurement=second_measurement,
        request_id="measurement-bytes-second",
    )
    spec = ToolRegistry.load_default().describe("P0-08")

    first = adapter.run(first_request, spec)
    second = adapter.run(second_request, spec)
    first_result = EvidenceSufficiencyRunResult.model_validate(first.result)
    second_result = EvidenceSufficiencyRunResult.model_validate(second.result)
    first_binding = next(
        item
        for item in first_result.source_object_bindings
        if item.role == "measurement_result"
    )
    second_binding = next(
        item
        for item in second_result.source_object_bindings
        if item.role == "measurement_result"
    )
    first_manifest = json.loads(
        (first.artifacts[0].path.parent / "artifact_manifest.json").read_text()
    )
    second_manifest = json.loads(
        (second.artifacts[0].path.parent / "artifact_manifest.json").read_text()
    )
    first_manifest_binding = next(
        item
        for item in first_manifest["structured_inputs"]
        if item["role"] == "measurement_result"
    )
    second_manifest_binding = next(
        item
        for item in second_manifest["structured_inputs"]
        if item["role"] == "measurement_result"
    )

    assert first.execution_state is ExecutionState.SUCCEEDED
    assert second.execution_state is ExecutionState.SUCCEEDED
    assert first.input_hash != second.input_hash
    assert first.run_id != second.run_id
    assert first_binding.source_sha256 != second_binding.source_sha256
    assert first_binding.source_sha256 == first_manifest_binding["source_sha256"]
    assert second_binding.source_sha256 == second_manifest_binding["source_sha256"]
    assert (
        first_manifest_binding["semantic_sha256"]
        == second_manifest_binding["semantic_sha256"]
    )


def test_nonmeasurement_source_bytes_are_bound_into_run_identity(
    tmp_path: Path,
) -> None:
    first_qc = _qc()
    first_qc["warnings"] = ["warning:a", "warning:b"]
    second_qc = _qc()
    second_qc["warnings"] = list(reversed(first_qc["warnings"]))
    first_request = _fixture_request(
        tmp_path / "first",
        qc=first_qc,
        request_id="qc-bytes-first",
    )
    second_request = _fixture_request(
        tmp_path / "second",
        qc=second_qc,
        request_id="qc-bytes-second",
    )
    spec = ToolRegistry.load_default().describe("P0-08")

    first = adapter.run(first_request, spec)
    second = adapter.run(second_request, spec)
    first_result = EvidenceSufficiencyRunResult.model_validate(first.result)
    second_result = EvidenceSufficiencyRunResult.model_validate(second.result)
    first_binding = next(
        item
        for item in first_result.source_object_bindings
        if item.role == "qc_readiness_profile"
    )
    second_binding = next(
        item
        for item in second_result.source_object_bindings
        if item.role == "qc_readiness_profile"
    )
    first_manifest = json.loads(
        (first.artifacts[0].path.parent / "artifact_manifest.json").read_text()
    )
    second_manifest = json.loads(
        (second.artifacts[0].path.parent / "artifact_manifest.json").read_text()
    )
    first_manifest_binding = next(
        item
        for item in first_manifest["structured_inputs"]
        if item["role"] == "qc_readiness_profile"
    )
    second_manifest_binding = next(
        item
        for item in second_manifest["structured_inputs"]
        if item["role"] == "qc_readiness_profile"
    )

    assert first.execution_state is ExecutionState.SUCCEEDED
    assert second.execution_state is ExecutionState.SUCCEEDED
    assert first.input_hash != second.input_hash
    assert first.run_id != second.run_id
    assert first_binding.source_sha256 != second_binding.source_sha256
    assert first_binding.source_sha256 == first_manifest_binding["source_sha256"]
    assert second_binding.source_sha256 == second_manifest_binding["source_sha256"]
    assert (
        first_manifest_binding["semantic_sha256"]
        == second_manifest_binding["semantic_sha256"]
    )


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


def test_v02_profile_and_visualization_schemas_are_public_and_exact(
    tmp_path: Path,
) -> None:
    run = _run(
        tmp_path,
        validation=_validation(validation_state="candidate"),
    )
    output_dir = run.artifacts[0].path.parent
    profile_payload = json.loads(
        (output_dir / "evidence_sufficiency_profile_01.json").read_text()
    )
    visualization_payload = json.loads(
        (output_dir / "evidence_sufficiency_visualization_data.json").read_text()
    )
    artifact_set_payload = json.loads(
        (output_dir / "evidence_sufficiency_visualization_artifact_set.json").read_text()
    )

    assert PUBLIC_SCHEMA_MODELS[
        "bridge://schemas/evidence-sufficiency-profile/v0.2"
    ] is EvidenceSufficiencyProfileV2
    Draft202012Validator(
        load_schema("bridge://schemas/evidence-sufficiency-profile/v0.2")
    ).validate(profile_payload)
    Draft202012Validator(
        load_schema(EVIDENCE_SUFFICIENCY_VISUALIZATION_DATA_SCHEMA_REF)
    ).validate(visualization_payload)
    Draft202012Validator(
        load_schema(P008_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF)
    ).validate(artifact_set_payload)
    EvidenceSufficiencyProfileV2.model_validate(profile_payload)
    profile = EvidenceSufficiencyVisualizationDataV1.model_validate(
        visualization_payload
    )
    artifact_set = P008VisualizationArtifactSet.model_validate(
        artifact_set_payload
    )

    assert profile.reason_catalog_sha256 == reason_catalog_sha256()
    raw_catalog = (
        files("bridge.tool_packages.p0_08_evidence_sufficiency.resources")
        .joinpath("reason_code_catalog_v0.2.json")
        .read_bytes()
    )
    assert profile.reason_catalog_sha256 == hashlib.sha256(raw_catalog).hexdigest()
    assert len(profile.axis_records) == 4
    assert [row.measurement_evidence_state for row in profile.measurement_state_records] == list(
        EvidenceState
    )
    assert sum(row.reference_count for row in profile.measurement_state_records) == 1
    assert all(row.independent_evidence_count is False for row in profile.measurement_state_records)
    assert {row.reason_code for row in profile.requirement_records} == {
        "method_validation_candidate"
    }
    assert profile.requirement_records[0].requirement_class.value == "limiting"
    assert profile.requirement_records[0].catalog_severity == "limiting"
    assert [item.component_ref for item in artifact_set.visualizations] == list(
        P008_COMPONENT_REFS
    )
    assert len(FigureRegistry.load_default().list(tool_id="P0-08")) == 3


def test_visualization_tables_are_complete_and_counts_are_not_evidence(
    tmp_path: Path,
) -> None:
    run = _run(tmp_path, validation=_validation(validation_state="candidate"))
    output_dir = run.artifacts[0].path.parent
    profile = EvidenceSufficiencyVisualizationDataV1.model_validate_json(
        (output_dir / "evidence_sufficiency_visualization_data.json").read_text()
    )
    serialized = profile.model_dump(mode="json")

    assert "source_to_reason_edges" not in json.dumps(serialized)
    assert profile.measurement_reference_counts_are_not_independent_evidence
    assert profile.evidence_family_ids_are_not_independent_evidence
    for name, expected_rows in (
        ("evidence_sufficiency_domain_axes.tsv", len(profile.axis_records)),
        (
            "evidence_sufficiency_interpretation_requirements.tsv",
            len(profile.requirement_records),
        ),
        (
            "evidence_sufficiency_measurement_states.tsv",
            len(profile.measurement_state_records),
        ),
    ):
        assert len((output_dir / name).read_text().splitlines()) == expected_rows + 1

    expanded = profile.model_copy(
        update={"requirement_records": profile.requirement_records * 25}
    )
    assert visualization_module._static_render_reason(
        expanded, P008_COMPONENT_REFS[1]
    ) == "static_render_requires_table_fallback"
    assert len(
        visualization_module._table(expanded, P008_COMPONENT_REFS[1])
        .decode()
        .splitlines()
    ) == 26


def test_visualization_builder_and_renderer_fail_with_stable_codes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = ToolRegistry.load_default().describe("P0-08")

    def invalid_builder(**_: object) -> None:
        raise ValueError("invalid visualization data")

    request = _fixture_request(tmp_path / "builder", output_name="output")
    with monkeypatch.context() as patch:
        patch.setattr(
            adapter_module,
            "build_evidence_sufficiency_visualization_data",
            invalid_builder,
        )
        run = adapter.run(request, spec)
    assert run.reason_codes == ["visualization_data_invalid"]
    assert not request.output_dir.exists()

    def invalid_renderer(**_: object) -> None:
        raise RuntimeError("invalid visualization render")

    request = _fixture_request(tmp_path / "renderer", output_name="output")
    with monkeypatch.context() as patch:
        patch.setattr(
            adapter_module,
            "prepare_evidence_sufficiency_visualizations",
            invalid_renderer,
        )
        run = adapter.run(request, spec)
    assert run.reason_codes == ["visualization_render_failed"]
    assert not request.output_dir.exists()


def test_tampered_visualization_bundle_is_never_overwritten(tmp_path: Path) -> None:
    request = _fixture_request(tmp_path, request_id="visual-tamper")
    spec = ToolRegistry.load_default().describe("P0-08")
    clean = adapter.run(request, spec)
    render = next(
        artifact for artifact in clean.artifacts if artifact.kind == "visualization_render"
    )
    render.path.write_bytes(b"tampered\n")

    repeated = adapter.run(request, spec)

    assert repeated.execution_state is ExecutionState.FAILED
    assert repeated.reason_codes == ["existing_run_bundle_hash_mismatch"]
    assert render.path.read_bytes() == b"tampered\n"


def test_visualization_profile_rejects_drifted_catalog_and_bindings(
    tmp_path: Path,
) -> None:
    run = _run(tmp_path, validation=_validation(validation_state="candidate"))
    output_dir = run.artifacts[0].path.parent
    original = json.loads(
        (output_dir / "evidence_sufficiency_visualization_data.json").read_text()
    )

    mutations = []
    changed = json.loads(json.dumps(original))
    changed["reason_catalog_sha256"] = "0" * 64
    mutations.append(changed)
    changed = json.loads(json.dumps(original))
    changed["reason_display_records"][0]["description"] = "drifted"
    mutations.append(changed)
    changed = json.loads(json.dumps(original))
    changed["requirement_records"][0]["catalog_axis"] = "score"
    mutations.append(changed)
    changed = json.loads(json.dumps(original))
    changed["source_evidence_refs"] = ["evidence:invented"]
    mutations.append(changed)
    changed = json.loads(json.dumps(original))
    changed["axis_records"][0]["evidence_ids"] = ["evidence:invented"]
    mutations.append(changed)

    changed = json.loads(json.dumps(original))
    changed["requirement_records"][0]["requirement_class"] = "blocking"
    mutations.append(changed)
    changed = json.loads(json.dumps(original))
    changed["requirement_records"][0]["reason_codes"] = [
        "prior_applicability_candidate"
    ]
    mutations.append(changed)
    changed = json.loads(json.dumps(original))
    changed["axis_records"][0]["source_state"] = "product_passes"
    mutations.append(changed)
    changed = json.loads(json.dumps(original))
    changed["axis_records"][0]["scoped_state_label"] = "Product passes"
    mutations.append(changed)
    changed = json.loads(json.dumps(original))
    changed["domain_bindings"][0]["domain_label"] = "Product passes"
    mutations.append(changed)

    for payload in mutations:
        with pytest.raises(ValueError):
            EvidenceSufficiencyVisualizationDataV1.model_validate(payload)


@pytest.mark.parametrize("target", ["missing-target", "output"])
def test_output_root_symlink_is_a_typed_failure(
    tmp_path: Path, target: str
) -> None:
    request = _fixture_request(tmp_path, output_name="output")
    request.output_dir.symlink_to(target, target_is_directory=True)

    run = adapter.run(request, ToolRegistry.load_default().describe("P0-08"))

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["output_path_invalid"]


def test_existing_run_directory_symlink_is_not_followed(tmp_path: Path) -> None:
    request = _fixture_request(tmp_path, request_id="visual-symlink")
    spec = ToolRegistry.load_default().describe("P0-08")
    first = adapter.run(request, spec)
    final = first.artifacts[0].path.parent
    shutil.rmtree(final)
    final.symlink_to(final.name, target_is_directory=True)

    repeated = adapter.run(request, spec)

    assert repeated.execution_state is ExecutionState.FAILED
    assert repeated.reason_codes == ["existing_run_bundle_hash_mismatch"]
    assert final.is_symlink()
