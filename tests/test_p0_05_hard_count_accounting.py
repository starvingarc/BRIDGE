from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from bridge.tool_packages.p0_05_off_target_control.adapter import adapter
from bridge.tool_packages.p0_05_off_target_control.models import (
    OffTargetHardCountProfileV1,
)
from bridge.toolkit.contracts import (
    ExecutionState,
    StructuredInputRef,
    ToolRequestV2,
)
from bridge.toolkit.registry import ToolRegistry
from bridge.toolkit.schemas import load_schema
from test_p0_05_off_target_control import _with_measurement_spec, _write
from test_p0_05_real_methods import _method_request, _rewrite_method


def _hard_count_request(tmp_path: Path) -> ToolRequestV2:
    method_request = _rewrite_method(
        _method_request(tmp_path),
        "cell_state_evidence_profile",
        lambda payload: payload["composition"]["records"][-1].update(
            {"label": "unknown"}
        ),
    )
    excluded_roles = {
        "off_target_evidence_bundle",
        "off_target_method_spec",
        "off_target_method_input",
    }
    return method_request.model_copy(
        update={
            "request_id": "request-p0-05-hard-count",
            "tool_version": None,
            "random_seed": 0,
            "object_inputs": [
                ref
                for ref in method_request.object_inputs
                if ref.role not in excluded_roles
            ],
        }
    )


def test_hard_count_mode_closes_selected_view_without_soft_mass(
    tmp_path: Path,
) -> None:
    registry = ToolRegistry.load_default()
    request = _hard_count_request(tmp_path)
    run = adapter.run(request, registry.describe("P0-05"))

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result is not None
    accounting = run.result["accounting"]
    non_consensus_count = sum(
        record["count"]
        for record in accounting["producer_composition"]["records"]
        if record["view"] == "reconciliation_state"
        and record["label"] != "consensus_supported"
    )
    assert (
        sum(
            record["consensus_supported_count"]
            for record in accounting["role_counts"]
        )
        + non_consensus_count
        == accounting["n_observations"]
    )
    assert accounting["total_soft_mass"] is None
    assert accounting["mass_state"] == "unavailable"



def _run(request: ToolRequestV2):
    return ToolRegistry.load_default().run(request)


def _rewrite_profile(request: ToolRequestV2, change) -> ToolRequestV2:
    return _rewrite_method(request, "cell_state_evidence_profile", change)


def _role_counts(result: dict) -> dict[str, int]:
    return {
        record["product_role"]: record["consensus_supported_count"]
        for record in result["accounting"]["role_counts"]
    }


def test_hard_count_profile_binds_inputs_and_publishes_only_count_profile(
    tmp_path: Path,
) -> None:
    request = _hard_count_request(tmp_path)
    run = _run(request)

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result is not None
    refs = {ref.role: ref for ref in request.object_inputs}
    assert run.tool_version == "0.6.0"
    assert run.result_schema_ref == "bridge://schemas/off-target-control-result/v0.1"
    assert run.result["object_version"] == "0.1.0"
    assert run.result["profile_version"] == "0.1.0"
    assert run.result["tool_version"] == "0.6.0"
    assert run.result["product_case_sha256"] == refs["product_case"].sha256
    assert (
        run.result["product_definition_sha256"]
        == refs["product_definition_card"].sha256
    )
    assert run.result["state_role_map_sha256"] == refs["state_role_map"].sha256
    assert (
        run.result["assessment_spec_sha256"]
        == refs["off_target_assessment_spec"].sha256
    )
    assert (
        run.result["cell_state_profile_sha256"]
        == refs["cell_state_evidence_profile"].sha256
    )
    assert (
        run.result["biological_unit_manifest_sha256"]
        == refs["biological_unit_manifest"].sha256
    )
    assert (
        run.result["biological_unit_attestation_receipt_sha256"]
        == refs["biological_unit_attestation_receipt"].sha256
    )
    assert run.result["measurement_projection_state"] == "not_requested"
    assert run.measurements == []
    assert [item.kind for item in run.artifacts] == [
        "off_target_hard_count_profile"
    ]
    assert run.visualizations == []


def test_hard_count_model_rejects_fraction_or_mass_tamper(tmp_path: Path) -> None:
    run = _run(_hard_count_request(tmp_path))
    assert run.result is not None
    wrong_fraction = json.loads(json.dumps(run.result))
    wrong_fraction["accounting"]["role_counts"][0][
        "fraction_of_selected_view"
    ] = 0.1
    with pytest.raises(ValueError, match="role fraction"):
        OffTargetHardCountProfileV1.model_validate(wrong_fraction)

    soft_mass = json.loads(json.dumps(run.result))
    soft_mass["accounting"]["total_soft_mass"] = 10.0
    with pytest.raises(ValueError):
        OffTargetHardCountProfileV1.model_validate(soft_mass)


def test_hard_count_mode_preserves_producer_composition_without_source_double_counting(
    tmp_path: Path,
) -> None:
    request = _rewrite_profile(
        _hard_count_request(tmp_path),
        lambda payload: payload["composition"]["records"].extend(
            [
                {
                    "view": "source_specific",
                    "source_id": "source:one",
                    "label": "state:a",
                    "label_level": "L1",
                    "state_evidence_state": "candidate",
                    "denominator_scope": "selected_data_view",
                    "count": 6,
                    "fraction": 0.6,
                    "denominator": 10,
                },
                {
                    "view": "source_specific",
                    "source_id": "source:two",
                    "label": "state:a",
                    "label_level": "L1",
                    "state_evidence_state": "candidate",
                    "denominator_scope": "selected_data_view",
                    "count": 7,
                    "fraction": 0.7,
                    "denominator": 10,
                },
            ]
        ),
    )

    run = _run(request)

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result is not None
    assert _role_counts(run.result) == {
        "target": 7,
        "acceptable_adjacent": 0,
        "known_off_target": 2,
        "role_unresolved": 0,
    }
    source_specific_count = sum(
        record["count"]
        for record in run.result["accounting"]["producer_composition"]["records"]
        if record["view"] == "source_specific"
    )
    assert source_specific_count == 13
    assert sum(_role_counts(run.result).values()) == 9


@pytest.mark.parametrize(
    ("reconciliation_label", "reconciliation_state"),
    [
        ("single_source_supported", "candidate"),
        ("source_conflict", "unresolved"),
    ],
)
def test_non_consensus_only_profiles_remain_separate_and_do_not_infer_roles(
    tmp_path: Path,
    reconciliation_label: str,
    reconciliation_state: str,
) -> None:
    records = [
        {
            "view": "reconciliation_state",
            "source_id": None,
            "label": reconciliation_label,
            "label_level": "L1",
            "state_evidence_state": reconciliation_state,
            "denominator_scope": "selected_data_view",
            "count": 10,
            "fraction": 1.0,
            "denominator": 10,
        }
    ]
    if reconciliation_label == "single_source_supported":
        records.insert(
            0,
            {
                "view": "source_specific",
                "source_id": "source:one",
                "label": "state:a",
                "label_level": "L1",
                "state_evidence_state": "candidate",
                "denominator_scope": "selected_data_view",
                "count": 10,
                "fraction": 1.0,
                "denominator": 10,
            },
        )
    request = _rewrite_profile(
        _hard_count_request(tmp_path),
        lambda payload: payload["composition"].update({"records": records}),
    )

    run = _run(request)

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result is not None
    assert _role_counts(run.result) == {
        "target": 0,
        "acceptable_adjacent": 0,
        "known_off_target": 0,
        "role_unresolved": 0,
    }
    assert (
        "zero_consensus_support_does_not_establish_absence"
        in run.result["reason_codes"]
    )
    assert run.result["open_set_assessment_state"] == "not_assessed"
    assert run.result["rare_detection_state"] == "not_assessed"


@pytest.mark.parametrize(
    ("change", "expected_reason"),
    [
        (
            lambda payload: payload["composition"]["records"][-1].update(
                {"state_evidence_state": "unresolved"}
            ),
            "hard_count_reconciliation_label_state_mismatch",
        ),
        (
            lambda payload: payload["composition"]["records"][0].update(
                {"label": "state:unmapped"}
            ),
            "hard_count_contains_unmapped_consensus_state",
        ),
        (
            lambda payload: payload["composition"]["records"][0].update(
                {"denominator": 11, "fraction": 7 / 11}
            ),
            "structured_input_schema_invalid",
        ),
    ],
)
def test_hard_count_mode_rejects_noncanonical_producer_records(
    tmp_path: Path,
    change,
    expected_reason: str,
) -> None:
    request = _rewrite_profile(_hard_count_request(tmp_path), change)

    eligibility = adapter.check_eligibility(
        request,
        ToolRegistry.load_default().describe("P0-05"),
    )

    assert not eligibility.eligible
    assert expected_reason in eligibility.reason_codes


@pytest.mark.parametrize(
    ("role", "change", "expected_reason"),
    [
        (
            "biological_unit_manifest",
            lambda payload: payload.update({"selected_artifact_sha256": "8" * 64}),
            "cell_state_biological_unit_manifest_mismatch",
        ),
        (
            "biological_unit_attestation_receipt",
            lambda payload: payload.update({"decision": "not_confirmed"}),
            "biological_unit_attestation_not_confirmed",
        ),
    ],
)
def test_hard_count_mode_rejects_manifest_or_receipt_drift(
    tmp_path: Path,
    role: str,
    change,
    expected_reason: str,
) -> None:
    request = _rewrite_method(_hard_count_request(tmp_path), role, change)

    eligibility = adapter.check_eligibility(
        request,
        ToolRegistry.load_default().describe("P0-05"),
    )

    assert not eligibility.eligible
    assert expected_reason in eligibility.reason_codes


def test_hard_count_mode_rejects_checksum_drift(tmp_path: Path) -> None:
    request = _hard_count_request(tmp_path)
    profile_ref = next(
        ref
        for ref in request.object_inputs
        if ref.role == "cell_state_evidence_profile"
    )
    payload = json.loads(profile_ref.path.read_text(encoding="utf-8"))
    payload["warnings"] = ["tampered after request creation"]
    _write(profile_ref.path, payload)

    eligibility = adapter.check_eligibility(
        request,
        ToolRegistry.load_default().describe("P0-05"),
    )

    assert not eligibility.eligible
    assert "structured_input_checksum_mismatch" in eligibility.reason_codes


def test_hard_count_mode_rejects_mixed_evidence_bundle_input(
    tmp_path: Path,
) -> None:
    request = _hard_count_request(tmp_path)
    bundle_path = request.object_inputs[0].path.parent / "off_target_evidence_bundle.json"
    bundle_ref = StructuredInputRef(
        input_id="input-mixed-evidence-bundle",
        role="off_target_evidence_bundle",
        schema_ref="bridge://schemas/off-target-evidence-bundle/v0.1",
        object_version="0.1.0",
        path=bundle_path,
        sha256=hashlib.sha256(bundle_path.read_bytes()).hexdigest(),
    )
    request = request.model_copy(
        update={"object_inputs": [*request.object_inputs, bundle_ref]}
    )

    eligibility = adapter.check_eligibility(
        request,
        ToolRegistry.load_default().describe("P0-05"),
    )

    assert not eligibility.eligible
    assert "object_input_role_not_allowed_in_selected_mode" in eligibility.reason_codes


def test_hard_count_mode_preserves_all_non_consensus_reconciliation_buckets(
    tmp_path: Path,
) -> None:
    records = [
        {
            "view": "reconciliation_state",
            "source_id": None,
            "label": label,
            "label_level": "L1",
            "state_evidence_state": state,
            "denominator_scope": "selected_data_view",
            "count": count,
            "fraction": fraction,
            "denominator": 10,
        }
        for label, state, count, fraction in (
            ("single_source_supported", "candidate", 2, 0.2),
            ("source_conflict", "unresolved", 2, 0.2),
            ("unknown", "unknown", 2, 0.2),
            ("ood", "ood", 2, 0.2),
            ("unavailable", "unavailable", 2, 0.2),
        )
    ]
    request = _rewrite_profile(
        _hard_count_request(tmp_path),
        lambda payload: payload["composition"].update({"records": records}),
    )

    run = _run(request)

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result is not None
    observed = {
        record["label"]: record["count"]
        for record in run.result["accounting"]["producer_composition"]["records"]
    }
    assert observed == {
        "single_source_supported": 2,
        "source_conflict": 2,
        "unknown": 2,
        "ood": 2,
        "unavailable": 2,
    }
    assert all(value == 0 for value in _role_counts(run.result).values())


def _hard_count_request_with_measurement_spec(tmp_path: Path) -> ToolRequestV2:
    request = _with_measurement_spec(_hard_count_request(tmp_path))
    return _rewrite_method(
        request,
        "measurement_spec",
        lambda payload: payload.update(
            {
                "measurement_spec_id": "measurement-spec:off-target-hard-count",
                "scientific_question": (
                    "What producer reference-support counts are available, "
                    "and which off-target assessments remain unavailable?"
                ),
                "input_contract": {
                    "source_result": "off-target-hard-count-profile",
                    "projection": "complete_accounting_plus_unavailable_assessments",
                },
                "raw_metric_definition": {
                    "metric_names": [
                        "off_target_hard_count_accounting",
                        "off_target_soft_mass_composition",
                        "off_target_identity_unknown",
                        "off_target_rare_state_detection",
                    ]
                },
            }
        ),
    )


def test_hard_count_measurement_spec_requires_exact_metric_set(
    tmp_path: Path,
) -> None:
    request = _rewrite_method(
        _hard_count_request_with_measurement_spec(tmp_path),
        "measurement_spec",
        lambda payload: payload["raw_metric_definition"].update(
            {"metric_names": ["off_target_hard_count_accounting"]}
        ),
    )

    eligibility = adapter.check_eligibility(
        request,
        ToolRegistry.load_default().describe("P0-05"),
    )

    assert not eligibility.eligible
    assert "measurement_spec_metric_names_mismatch" in eligibility.reason_codes


def test_hard_count_measurements_preserve_one_inferred_and_three_unavailable_states(
    tmp_path: Path,
) -> None:
    run = _run(_hard_count_request_with_measurement_spec(tmp_path))

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result is not None
    by_metric = {item.metric_name: item for item in run.measurements}
    assert set(by_metric) == {
        "off_target_hard_count_accounting",
        "off_target_soft_mass_composition",
        "off_target_identity_unknown",
        "off_target_rare_state_detection",
    }
    accounting = by_metric["off_target_hard_count_accounting"]
    assert accounting.evidence_state.value == "inferred"
    assert accounting.raw_value == run.result["accounting"]
    for metric_name in (
        "off_target_soft_mass_composition",
        "off_target_identity_unknown",
        "off_target_rare_state_detection",
    ):
        measurement = by_metric[metric_name]
        assert measurement.evidence_state.value == "unavailable"
        assert measurement.raw_value is None
        assert measurement.numerator is None
        assert measurement.denominator is None
        assert measurement.interval is None
        assert measurement.interval_confidence_level is None
        assert measurement.interval_method_ref is None
    assert all(item.source_execution_state == "succeeded" for item in run.measurements)
    assert all(item.domain_score is None for item in run.measurements)
    assert all(item.score_state.value == "unavailable" for item in run.measurements)
    assert all(item.unknown_scope is None for item in run.measurements)
    assert run.result["measurement_projection_state"] == "available"
    assert len(run.result["measurement_artifacts"]) == 4
    assert run.visualizations == []


def test_hard_count_mode_is_content_hash_deterministic(tmp_path: Path) -> None:
    request = _hard_count_request_with_measurement_spec(tmp_path)

    first = _run(request)
    second = _run(request)

    assert first.execution_state is ExecutionState.SUCCEEDED
    assert second.execution_state is ExecutionState.SUCCEEDED
    assert first.run_id == second.run_id
    assert first.input_hash == second.input_hash
    assert {
        item.path.name: item.sha256 for item in first.artifacts
    } == {
        item.path.name: item.sha256 for item in second.artifacts
    }
    assert first.result == second.result


@pytest.mark.parametrize(
    "schema_ref",
    [
        "bridge://schemas/off-target-hard-count-profile/v0.1",
        "bridge://schemas/off-target-control-result/v0.1",
    ],
)
def test_exported_hard_count_schema_rejects_projection_state_contradictions(
    tmp_path: Path,
    schema_ref: str,
) -> None:
    without_spec_root = tmp_path / "without-spec"
    without_spec_root.mkdir()
    with_spec_root = tmp_path / "with-spec"
    with_spec_root.mkdir()
    not_requested = _run(_hard_count_request(without_spec_root)).result
    available = _run(
        _hard_count_request_with_measurement_spec(with_spec_root)
    ).result
    assert not_requested is not None
    assert available is not None
    validator = Draft202012Validator(load_schema(schema_ref))

    assert not list(validator.iter_errors(not_requested))
    assert not list(validator.iter_errors(available))

    available_without_projection = deepcopy(not_requested)
    available_without_projection["measurement_projection_state"] = "available"
    assert list(validator.iter_errors(available_without_projection))

    not_requested_with_spec = deepcopy(not_requested)
    not_requested_with_spec["measurement_spec_ref"] = {
        "object_id": "measurement-spec:off-target-hard-count",
        "object_version": "1",
    }
    not_requested_with_spec["measurement_spec_sha256"] = "a" * 64
    assert list(validator.iter_errors(not_requested_with_spec))


@pytest.mark.parametrize(
    "schema_ref",
    [
        "bridge://schemas/off-target-hard-count-profile/v0.1",
        "bridge://schemas/off-target-control-result/v0.1",
    ],
)
def test_exported_hard_count_schema_requires_all_four_fixed_metric_states(
    tmp_path: Path,
    schema_ref: str,
) -> None:
    available = _run(_hard_count_request_with_measurement_spec(tmp_path)).result
    assert available is not None
    validator = Draft202012Validator(load_schema(schema_ref))
    assert not list(validator.iter_errors(available))

    missing_metric = deepcopy(available)
    missing_metric["measurement_artifacts"].pop()
    assert list(validator.iter_errors(missing_metric))

    wrong_state = deepcopy(available)
    accounting = next(
        item
        for item in wrong_state["measurement_artifacts"]
        if item["metric_name"] == "off_target_hard_count_accounting"
    )
    accounting["evidence_state"] = "unavailable"
    assert list(validator.iter_errors(wrong_state))
