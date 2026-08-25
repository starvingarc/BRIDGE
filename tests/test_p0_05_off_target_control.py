from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Callable

import pytest

from bridge.tool_packages.p0_05_off_target_control.adapter import adapter
from bridge.toolkit.contracts import (
    ExecutionState,
    ImplementationState,
    StructuredInputRef,
    ToolRequest,
    ToolRequestV2,
)
from bridge.toolkit.registry import ToolRegistry


ROLE_SCHEMAS = {
    "product_case": ("bridge://schemas/product-case/v0.1", "0.1.0"),
    "product_definition_card": (
        "bridge://schemas/product-definition-card/v0.1",
        "0.1.0",
    ),
    "state_role_map": ("bridge://schemas/state-role-map/v0.1", "0.1.0"),
    "off_target_assessment_spec": (
        "bridge://schemas/off-target-assessment-spec/v0.1",
        "0.1.0",
    ),
    "cell_state_evidence_profile": (
        "bridge://schemas/cell-state-evidence-profile/v0.2",
        "0.2.0",
    ),
    "off_target_evidence_bundle": (
        "bridge://schemas/off-target-evidence-bundle/v0.1",
        "0.1.0",
    ),
}


def _encoded(payload: dict) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode()


def _write(path: Path, payload: dict) -> str:
    raw = _encoded(payload)
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def _request(tmp_path: Path) -> ToolRequestV2:
    root = tmp_path / "objects"
    root.mkdir()
    timestamp = datetime(2026, 8, 25, tzinfo=timezone.utc).isoformat()
    role_map = {
        "object_version": "0.1.0",
        "state_role_map_id": "state-role-map:demo",
        "map_version": "1",
        "product_definition_ref": {
            "object_id": "product-definition:demo",
            "object_version": "1",
        },
        "review_state": "draft",
        "assignments": [
            {
                "state_id": "state:a",
                "product_role": "target",
                "role_evidence_class": "externally_defined_target",
                "evidence_direction": "externally_defined",
                "source_refs": ["source:role-map"],
            },
            {
                "state_id": "state:b",
                "product_role": "known_off_target",
                "role_evidence_class": "externally_defined_non_target",
                "evidence_direction": "externally_defined",
                "source_refs": ["source:role-map"],
            },
        ],
        "provenance_refs": [
            {"object_id": "source:role-map", "object_version": "1"}
        ],
    }
    product_definition = {
        "object_version": "0.1.0",
        "product_definition_id": "product-definition:demo",
        "definition_version": "1",
        "state_role_map_ref": {
            "object_id": "state-role-map:demo",
            "object_version": "1",
        },
        "supported_assays": ["scRNA-seq"],
        "review_state": "draft",
        "provenance_refs": [
            {"object_id": "source:definition", "object_version": "1"}
        ],
    }
    product_case = {
        "object_version": "0.1.0",
        "product_case_id": "product-case:demo",
        "case_version": "1",
        "product_definition_ref": {
            "object_id": "product-definition:demo",
            "object_version": "1",
        },
        "source_unit_kind": "preparation",
        "sample_or_preparation_ref": {
            "object_id": "preparation:demo",
            "object_version": "1",
        },
        "measurement_spec_ref": {
            "object_id": "measurement-spec:cell-state",
            "object_version": "1",
        },
        "assay": "scRNA-seq",
        "provenance_refs": [
            {"object_id": "source:case", "object_version": "1"}
        ],
        "created_at": timestamp,
    }
    cell_state_profile = {
        "profile_id": "cell-state-profile:demo",
        "assay": "scRNA-seq",
        "measurement_spec_id": "measurement-spec:cell-state",
        "measurement_spec_version": "1",
        "measurement_spec_status": "candidate",
        "annotation_vocabulary_ref": "annotation-vocabulary:demo@1",
        "reference_snapshot_ref": "reference-snapshot:demo@1",
        "n_observations": 10,
        "n_genes": 100,
        "denominator": "eligible cells",
        "label_levels": {},
        "source_support": {},
        "marker_program_evidence": {},
        "prediction_sets": {},
        "composition": {},
        "gene_coverage": {},
        "modality_sensitivity": {},
        "score_state": "shadow",
        "domain_score": None,
        "evidence_ids": ["evidence:demo"],
    }

    paths = {
        role: root / f"{role}.json"
        for role in ROLE_SCHEMAS
    }
    role_map_sha = _write(paths["state_role_map"], role_map)
    definition_sha = _write(
        paths["product_definition_card"], product_definition
    )
    case_sha = _write(paths["product_case"], product_case)
    profile_sha = _write(
        paths["cell_state_evidence_profile"], cell_state_profile
    )
    assessment_spec = {
        "object_version": "0.1.0",
        "assessment_spec_id": "off-target-assessment-spec:demo",
        "spec_version": "1",
        "product_definition_ref": {
            "object_id": "product-definition:demo",
            "object_version": "1",
        },
        "state_role_map_ref": {
            "object_id": "state-role-map:demo",
            "object_version": "1",
        },
        "state_role_map_sha256": role_map_sha,
        "primary_denominator_id": "eligible-cells",
        "allowed_unknown_reason_ids": ["reference_gap"],
        "rare_state_rules": [
            {
                "state_id": "state:b",
                "max_validated_detection_limit_fraction": 0.05,
                "max_false_positive_fraction": 0.01,
                "missing_calibration_state": "cannot_exclude",
            }
        ],
        "active": True,
    }
    _write(paths["off_target_assessment_spec"], assessment_spec)
    evidence_bundle = {
        "object_version": "0.1.0",
        "bundle_id": "off-target-evidence-bundle:demo",
        "bundle_version": "1",
        "product_case_ref": "product-case:demo@1",
        "product_case_sha256": case_sha,
        "product_definition_ref": "product-definition:demo@1",
        "product_definition_sha256": definition_sha,
        "cell_state_profile_id": "cell-state-profile:demo",
        "cell_state_profile_sha256": profile_sha,
        "denominator": {
            "denominator_id": "eligible-cells",
            "n_observations": 10,
            "total_soft_mass": 10.0,
            "unit": "cells",
        },
        "composition_coverage_state": "complete",
        "state_observations": [
            {"state_id": "state:a", "soft_mass": 7.0, "observed_count": 7},
            {"state_id": "state:b", "soft_mass": 2.0, "observed_count": 2},
        ],
        "unknown_coverage_state": "complete",
        "unknown_observations": [
            {
                "reason_id": "reference_gap",
                "soft_mass": 1.0,
                "observed_count": 1,
            }
        ],
        "rare_state_calibrations": [
            {
                "state_id": "state:b",
                "calibration_ref": "calibration:demo",
                "calibration_sha256": "a" * 64,
                "validated_detection_limit_fraction": 0.02,
                "false_positive_fraction": 0.005,
                "zero_observation_upper_bound_fraction": 0.03,
            }
        ],
        "created_at": timestamp,
    }
    _write(paths["off_target_evidence_bundle"], evidence_bundle)

    refs = []
    for role, (schema_ref, object_version) in ROLE_SCHEMAS.items():
        raw = paths[role].read_bytes()
        refs.append(
            StructuredInputRef(
                input_id=f"input-{role}",
                role=role,
                schema_ref=schema_ref,
                object_version=object_version,
                path=paths[role],
                sha256=hashlib.sha256(raw).hexdigest(),
            )
        )
    return ToolRequestV2(
        request_id="request-p0-05",
        tool_id="P0-05",
        tool_version="0.2.0",
        output_dir=tmp_path / "output",
        object_inputs=refs,
    )


def _rewrite(
    request: ToolRequestV2,
    role: str,
    mutate: Callable[[dict], None],
) -> ToolRequestV2:
    refs = list(request.object_inputs)
    index = next(index for index, ref in enumerate(refs) if ref.role == role)
    ref = refs[index]
    payload = json.loads(ref.path.read_text())
    mutate(payload)
    digest = _write(ref.path, payload)
    refs[index] = ref.model_copy(update={"sha256": digest})
    return request.model_copy(update={"object_inputs": refs})


def _role(result: dict, role: str) -> dict:
    return next(
        item for item in result["role_composition"]
        if item["product_role"] == role
    )


def test_registry_exposes_executable_p0_05() -> None:
    spec = ToolRegistry.load_default().describe("P0-05")

    assert spec.implementation_state is ImplementationState.IMPLEMENTED
    assert spec.version == "0.2.0"
    assert spec.result_schema_ref == (
        "bridge://schemas/off-target-control-profile/v0.1"
    )
    assert spec.method_ids == ["METHOD-BRIDGE-ROLE-AWARE-SOFT-COMPOSITION"]


def test_happy_run_aggregates_external_roles_and_publishes_checksum(
    tmp_path: Path,
) -> None:
    registry = ToolRegistry.load_default()
    request = _request(tmp_path)

    assert registry.check_eligibility(request).eligible
    run = registry.run(request)

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.measurements == []
    assert len(run.artifacts) == 1
    assert _role(run.result, "target")["fraction"] == pytest.approx(0.7)
    assert _role(run.result, "known_off_target")["fraction"] == pytest.approx(0.2)
    assert run.result["unknown_profile"]["fraction"] == pytest.approx(0.1)
    assert run.result["rare_state_profile"][0]["detection_state"] == "detected"
    assert run.result["evidence_state"] == "shadow"
    assert run.result["score_state"] == "unavailable"
    assert run.result["domain_score"] is None
    assert hashlib.sha256(run.artifacts[0].path.read_bytes()).hexdigest() == (
        run.artifacts[0].sha256
    )


def test_role_mapping_is_external_not_inferred_from_state_name(
    tmp_path: Path,
) -> None:
    registry = ToolRegistry.load_default()
    request = _request(tmp_path)

    def move_role(payload: dict) -> None:
        payload["assignments"][1]["product_role"] = "acceptable_adjacent"

    request = _rewrite(request, "state_role_map", move_role)
    map_sha = next(
        ref.sha256 for ref in request.object_inputs
        if ref.role == "state_role_map"
    )
    request = _rewrite(
        request,
        "off_target_assessment_spec",
        lambda payload: payload.update({"state_role_map_sha256": map_sha}),
    )
    run = registry.run(request)

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert _role(run.result, "acceptable_adjacent")["fraction"] == pytest.approx(
        0.2
    )
    assert _role(run.result, "known_off_target")["fraction"] == 0.0


def test_partial_coverage_withholds_fractions(tmp_path: Path) -> None:
    registry = ToolRegistry.load_default()
    request = _request(tmp_path)
    request = _rewrite(
        request,
        "off_target_evidence_bundle",
        lambda payload: payload.update(
            {
                "composition_coverage_state": "partial",
                "unknown_coverage_state": "partial",
                "state_observations": [
                    {"state_id": "state:a", "soft_mass": 7.0, "observed_count": 7},
                    {"state_id": "state:b", "soft_mass": 0.0, "observed_count": 0},
                ],
            }
        ),
    )

    run = registry.run(request)

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert all(
        item["fraction"] is None
        and item["assessment_state"] == "not_assessed"
        for item in run.result["role_composition"]
    )
    assert run.result["unknown_profile"]["fraction"] is None
    assert "composition_coverage_not_complete" in run.result["reason_codes"]
    assert run.result["rare_state_profile"][0]["detection_state"] == (
        "cannot_exclude"
    )


def test_zero_observation_is_cannot_exclude_not_absent(
    tmp_path: Path,
) -> None:
    run = ToolRegistry.load_default().run(_request(tmp_path))

    unresolved = _role(run.result, "role_unresolved")
    assert unresolved["observed_count"] == 0
    assert unresolved["exclusion_state"] == "cannot_exclude"
    assert "zero_observation_does_not_establish_absence" in (
        run.result["reason_codes"]
    )


def test_unknown_reason_must_be_declared_by_external_spec(
    tmp_path: Path,
) -> None:
    registry = ToolRegistry.load_default()
    request = _request(tmp_path)
    request = _rewrite(
        request,
        "off_target_evidence_bundle",
        lambda payload: payload["unknown_observations"][0].update(
            {"reason_id": "caller_specific_reason"}
        ),
    )

    eligibility = registry.check_eligibility(request)

    assert not eligibility.eligible
    assert "unknown_reason_not_allowed" in eligibility.reason_codes


@pytest.mark.parametrize(
    ("bundle_mutation", "expected_state", "expected_reason"),
    [
        (
            lambda payload: payload.update({"rare_state_calibrations": []}),
            "cannot_exclude",
            "rare_state_calibration_missing",
        ),
        (
            lambda payload: payload["rare_state_calibrations"][0].update(
                {"validated_detection_limit_fraction": 0.2}
            ),
            "cannot_exclude",
            "rare_state_calibration_outside_spec",
        ),
    ],
)
def test_rare_state_calibration_fails_closed(
    tmp_path: Path,
    bundle_mutation: Callable[[dict], None],
    expected_state: str,
    expected_reason: str,
) -> None:
    request = _rewrite(
        _request(tmp_path),
        "off_target_evidence_bundle",
        bundle_mutation,
    )

    run = ToolRegistry.load_default().run(request)
    record = run.result["rare_state_profile"][0]

    assert record["detection_state"] == expected_state
    assert expected_reason in record["reason_codes"]


def test_calibrated_zero_is_not_detected_above_lod_with_upper_bound(
    tmp_path: Path,
) -> None:
    def zero_rare_state(payload: dict) -> None:
        payload["state_observations"] = [
            {"state_id": "state:a", "soft_mass": 9.0, "observed_count": 9},
            {"state_id": "state:b", "soft_mass": 0.0, "observed_count": 0},
        ]

    request = _rewrite(
        _request(tmp_path), "off_target_evidence_bundle", zero_rare_state
    )
    run = ToolRegistry.load_default().run(request)
    record = run.result["rare_state_profile"][0]

    assert record["detection_state"] == "not_detected_above_lod"
    assert record["zero_observation_upper_bound_fraction"] == pytest.approx(0.03)
    assert "zero_observation_does_not_establish_absence" in (
        record["reason_codes"]
    )


def test_missing_rare_observation_is_not_assessed(tmp_path: Path) -> None:
    def remove_rare_row(payload: dict) -> None:
        payload["composition_coverage_state"] = "partial"
        payload["state_observations"] = payload["state_observations"][:1]

    request = _rewrite(
        _request(tmp_path), "off_target_evidence_bundle", remove_rare_row
    )
    run = ToolRegistry.load_default().run(request)
    record = run.result["rare_state_profile"][0]

    assert record["detection_state"] == "not_assessed"
    assert record["observed_count"] is None
    assert record["reason_codes"] == ["rare_state_observation_missing"]


@pytest.mark.parametrize(
    ("role", "mutate", "reason"),
    [
        (
            "product_case",
            lambda payload: payload["product_definition_ref"].update(
                {"object_id": "product-definition:other"}
            ),
            "product_definition_binding_mismatch",
        ),
        (
            "cell_state_evidence_profile",
            lambda payload: payload.update({"assay": "snRNA-seq"}),
            "cell_state_assay_binding_mismatch",
        ),
        (
            "off_target_assessment_spec",
            lambda payload: payload.update({"active": False}),
            "off_target_assessment_spec_inactive",
        ),
        (
            "off_target_evidence_bundle",
            lambda payload: payload["denominator"].update(
                {"denominator_id": "other-denominator"}
            ),
            "primary_denominator_binding_mismatch",
        ),
    ],
)
def test_cross_object_binding_failures_are_typed(
    tmp_path: Path,
    role: str,
    mutate: Callable[[dict], None],
    reason: str,
) -> None:
    request = _rewrite(_request(tmp_path), role, mutate)

    eligibility = ToolRegistry.load_default().check_eligibility(request)

    assert not eligibility.eligible
    assert reason in eligibility.reason_codes


def test_unmapped_state_fails_closed(tmp_path: Path) -> None:
    def add_unmapped(payload: dict) -> None:
        payload["state_observations"].append(
            {"state_id": "state:unmapped", "soft_mass": 0.0, "observed_count": 0}
        )

    request = _rewrite(
        _request(tmp_path), "off_target_evidence_bundle", add_unmapped
    )
    eligibility = ToolRegistry.load_default().check_eligibility(request)

    assert not eligibility.eligible
    assert "evidence_bundle_contains_unmapped_state" in eligibility.reason_codes


def test_checksum_mismatch_fails_before_execution(tmp_path: Path) -> None:
    registry = ToolRegistry.load_default()
    request = _request(tmp_path)
    ref = next(
        item for item in request.object_inputs if item.role == "state_role_map"
    )
    ref.path.write_text(ref.path.read_text() + " ")

    eligibility = registry.check_eligibility(request)

    assert not eligibility.eligible
    assert eligibility.reason_codes == ["structured_input_checksum_mismatch"]


def test_v1_request_receives_typed_refusal(tmp_path: Path) -> None:
    registry = ToolRegistry.load_default()
    spec = registry.describe("P0-05")
    request = ToolRequest(
        request_id="legacy-request",
        tool_id="P0-05",
        output_dir=tmp_path / "output",
    )

    run = adapter.run(request, spec)

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["tool_request_v2_required"]
    assert run.result is None


def test_identical_input_reuses_output_and_tamper_fails_closed(
    tmp_path: Path,
) -> None:
    registry = ToolRegistry.load_default()
    request = _request(tmp_path)

    first = registry.run(request)
    second = registry.run(request)
    assert first.run_id == second.run_id
    assert first.artifacts[0].sha256 == second.artifacts[0].sha256

    first.artifacts[0].path.write_text("{}\n")
    third = registry.run(request)

    assert third.execution_state is ExecutionState.FAILED
    assert third.reason_codes == ["existing_run_bundle_hash_mismatch"]
