from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path

from jsonschema import Draft202012Validator
from pydantic import ValidationError
import pytest

import bridge.tool_packages.p0_12_graft_assessment.adapter as adapter_module
from bridge.tool_packages.p0_12_graft_assessment.adapter import adapter
from bridge.tool_packages.p0_12_graft_assessment.models import (
    GraftObservation,
    PUBLIC_SCHEMA_MODELS,
)
from bridge.toolkit.contracts import (
    ExecutionState,
    ImplementationState,
    StructuredInputRef,
    ToolPackageSpecV2,
    ToolRequest,
    ToolRequestV2,
)
from bridge.toolkit.registry import ToolRegistry


ROLE_SCHEMAS = {
    "graft_assessment_spec": "bridge://schemas/graft-assessment-spec/v0.1",
    "graft_evidence_bundle": "bridge://schemas/graft-evidence-bundle/v0.1",
}


def _ref(object_id: str, version: str = "1.0.0") -> dict[str, str]:
    return {"object_id": object_id, "object_version": version}


def _observation(unit: int, channel: str, value: float) -> dict:
    return {
        "observation_id": f"graft-observation:unit-{unit}-{channel}",
        "channel_id": f"graft-channel:{channel}",
        "unit": "configured-unit",
        "value": value,
        "denominator": 100,
        "evidence_state": "measured",
        "evidence_refs": [f"evidence:unit-{unit}-{channel}"],
    }


def _payloads() -> dict[str, dict]:
    product_case = _ref("product-case:configured")
    measurement = _ref("measurement-spec:configured")
    assay = _ref("assay:configured")
    sampling = _ref("sampling-context:configured")
    reference = _ref("reference-snapshot:configured")
    algorithm = _ref("algorithm:configured")
    return {
        "graft_assessment_spec": {
            "object_version": "0.1.0",
            "assessment_spec_id": "graft-assessment-spec:configured",
            "assessment_spec_version": "1.0.0",
            "product_case_ref": product_case,
            "measurement_spec_ref": measurement,
            "assay_ref": assay,
            "sampling_context_ref": sampling,
            "reference_snapshot_ref": reference,
            "algorithm_ref": algorithm,
            "rules": [
                {
                    "channel_id": "graft-channel:configured-primary",
                    "unit": "configured-unit",
                    "required": True,
                    "eligible_evidence_states": ["measured", "inferred"],
                    "minimum_independent_units": 2,
                    "interpretation_policy": "configured_interval",
                    "configured_lower_bound": 1.0,
                    "configured_upper_bound": 4.0,
                },
                {
                    "channel_id": "graft-channel:configured-secondary",
                    "unit": "configured-unit",
                    "required": False,
                    "eligible_evidence_states": ["measured"],
                    "minimum_independent_units": 1,
                    "interpretation_policy": "descriptive_only",
                    "configured_lower_bound": None,
                    "configured_upper_bound": None,
                },
            ],
            "missing_observation_policy": "report_unavailable",
            "confounded_design_policy": "descriptive_only",
            "preparation_linkage_policy": "explicit_evidence_only",
            "score_policy": "unavailable",
        },
        "graft_evidence_bundle": {
            "object_version": "0.1.0",
            "evidence_bundle_id": "graft-evidence-bundle:configured",
            "evidence_bundle_version": "1.0.0",
            "graft_availability": "provided",
            "product_case_ref": product_case,
            "graft_case_ref": _ref("graft-case:configured"),
            "measurement_spec_ref": measurement,
            "assay_ref": assay,
            "sampling_context_ref": sampling,
            "reference_snapshot_ref": reference,
            "algorithm_ref": algorithm,
            "design_constraint_refs": [],
            "units": [
                {
                    "unit_ref": _ref("graft-unit:one"),
                    "animal_ref": _ref("animal:one"),
                    "graft_ref": _ref("graft:one"),
                    "timepoint_ref": _ref("timepoint:one"),
                    "originating_preparation_ref": _ref("preparation:one"),
                    "linkage_evidence_refs": ["evidence:link-one"],
                    "observations": [
                        _observation(1, "configured-primary", 2.0),
                        _observation(1, "configured-secondary", 10.0),
                    ],
                },
                {
                    "unit_ref": _ref("graft-unit:two"),
                    "animal_ref": _ref("animal:two"),
                    "graft_ref": _ref("graft:two"),
                    "timepoint_ref": _ref("timepoint:two"),
                    "originating_preparation_ref": _ref("preparation:two"),
                    "linkage_evidence_refs": ["evidence:link-two"],
                    "observations": [
                        _observation(2, "configured-primary", 4.0),
                        _observation(2, "configured-secondary", 12.0),
                    ],
                },
            ],
        },
    }


def _write_json(path: Path, payload: dict) -> str:
    encoded = (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()
    path.write_bytes(encoded)
    return hashlib.sha256(encoded).hexdigest()


def _request(
    tmp_path: Path,
    *,
    payloads: dict[str, dict] | None = None,
    output_dir: Path | None = None,
    input_id_prefix: str = "input",
    random_seed: int = 0,
) -> ToolRequestV2:
    values = deepcopy(payloads or _payloads())
    input_root = tmp_path / f"objects-{input_id_prefix}"
    input_root.mkdir(parents=True)
    refs: list[StructuredInputRef] = []
    for index, role in enumerate(ROLE_SCHEMAS, start=1):
        path = input_root / f"{role}.json"
        digest = _write_json(path, values[role])
        refs.append(
            StructuredInputRef(
                input_id=f"{input_id_prefix}-{index}",
                role=role,
                schema_ref=ROLE_SCHEMAS[role],
                object_version="0.1.0",
                path=path,
                sha256=digest,
                media_type="application/json",
            )
        )
    return ToolRequestV2(
        request_id=f"request-{input_id_prefix}",
        tool_id="P0-12",
        tool_version="0.2.0",
        output_dir=output_dir or (tmp_path / "output"),
        random_seed=random_seed,
        object_inputs=refs,
    )


def test_p0_12_is_an_implemented_v2_package() -> None:
    spec = ToolRegistry.load_default().describe("P0-12")

    assert isinstance(spec, ToolPackageSpecV2)
    assert spec.implementation_state is ImplementationState.IMPLEMENTED
    assert spec.result_schema_ref == "bridge://schemas/graft-assessment/v0.1"
    assert spec.adapter_ref == (
        "bridge.tool_packages.p0_12_graft_assessment.adapter:adapter"
    )


@pytest.mark.parametrize("schema_ref,model", PUBLIC_SCHEMA_MODELS.items())
def test_public_models_emit_valid_draft_2020_12_schemas(
    schema_ref: str, model: type
) -> None:
    schema = model.model_json_schema()
    schema["$id"] = schema_ref
    Draft202012Validator.check_schema(schema)


def test_configured_graft_summary_runs_without_backfill_or_score(
    tmp_path: Path,
) -> None:
    run = ToolRegistry.load_default().run(_request(tmp_path))

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result["result_state"] == "complete"
    assert run.result["graft_availability"] == "provided"
    assert run.result["linkage_state"] == "provided_linked"
    assert run.result["analysis_mode"] == "descriptive_only"
    assert run.result["independent_unit_count"] == 2
    primary = run.result["channel_summaries"][0]
    assert primary["mean"] == 3.0
    assert primary["minimum"] == 2.0
    assert primary["maximum"] == 4.0
    assert primary["configured_interval_relation"] == "within_configured_interval"
    assert run.result["product_backfill"] == "not_performed"
    assert run.result["graft_score"] is None
    assert run.result["domain_score"] is None
    assert run.result["score_state"] == "shadow"
    assert run.measurements == []
    assert len(run.artifacts) == 1


def test_interval_interpretation_changes_only_with_versioned_spec(
    tmp_path: Path,
) -> None:
    baseline = ToolRegistry.load_default().run(_request(tmp_path / "baseline"))
    payloads = _payloads()
    rule = payloads["graft_assessment_spec"]["rules"][0]
    rule["configured_lower_bound"] = 0.0
    rule["configured_upper_bound"] = 2.0
    changed = ToolRegistry.load_default().run(
        _request(tmp_path / "changed", payloads=payloads)
    )

    assert baseline.result["channel_summaries"][0][
        "configured_interval_relation"
    ] == "within_configured_interval"
    assert changed.result["channel_summaries"][0][
        "configured_interval_relation"
    ] == "above_configured_interval"
    assert "outside_configured_interval" in changed.reason_codes
    assert baseline.run_id != changed.run_id


def test_explicit_not_provided_is_traceable_and_does_not_degrade_product(
    tmp_path: Path,
) -> None:
    payloads = _payloads()
    bundle = payloads["graft_evidence_bundle"]
    bundle.update(
        {
            "graft_availability": "not_provided",
            "graft_case_ref": None,
            "measurement_spec_ref": None,
            "assay_ref": None,
            "sampling_context_ref": None,
            "reference_snapshot_ref": None,
            "algorithm_ref": None,
            "design_constraint_refs": [],
            "units": [],
        }
    )

    run = ToolRegistry.load_default().run(_request(tmp_path, payloads=payloads))

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result["result_state"] == "not_provided"
    assert run.result["analysis_mode"] == "unavailable"
    assert run.result["linkage_state"] == "not_applicable"
    assert run.result["channel_summaries"] == []
    assert run.result["product_backfill"] == "not_performed"
    assert run.result["score_state"] == "unavailable"


def test_missing_observations_are_unavailable_not_zero(tmp_path: Path) -> None:
    payloads = _payloads()
    for unit in payloads["graft_evidence_bundle"]["units"]:
        observation = unit["observations"][0]
        observation.update(
            {"value": None, "denominator": None, "evidence_state": "missing"}
        )

    run = ToolRegistry.load_default().run(_request(tmp_path, payloads=payloads))
    primary = run.result["channel_summaries"][0]

    assert run.execution_state is ExecutionState.PARTIAL
    assert run.result["result_state"] == "partial"
    assert primary["result_state"] == "unavailable"
    assert primary["mean"] is None
    assert primary["eligible_unit_count"] == 0
    assert "graft_channel_unavailable" in primary["reason_codes"]


def test_provided_bundle_without_units_is_not_assessed(tmp_path: Path) -> None:
    payloads = _payloads()
    payloads["graft_evidence_bundle"]["units"] = []

    run = ToolRegistry.load_default().run(_request(tmp_path, payloads=payloads))

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result["result_state"] == "not_assessed"
    assert run.result["independent_unit_count"] == 0
    assert run.result["score_state"] == "unavailable"
    assert all(
        item["result_state"] == "unavailable"
        for item in run.result["channel_summaries"]
    )


def test_independent_unit_minimum_is_policy_input(tmp_path: Path) -> None:
    payloads = _payloads()
    observation = payloads["graft_evidence_bundle"]["units"][1]["observations"][0]
    observation.update(
        {"value": None, "denominator": None, "evidence_state": "unknown"}
    )

    run = ToolRegistry.load_default().run(_request(tmp_path, payloads=payloads))
    primary = run.result["channel_summaries"][0]

    assert run.execution_state is ExecutionState.PARTIAL
    assert primary["eligible_unit_count"] == 1
    assert "independent_units_below_configured_minimum" in primary["reason_codes"]


def test_unconfigured_channels_are_reported_not_silently_used(
    tmp_path: Path,
) -> None:
    payloads = _payloads()
    payloads["graft_evidence_bundle"]["units"][0]["observations"].append(
        _observation(1, "caller-added", 9.0)
    )

    run = ToolRegistry.load_default().run(_request(tmp_path, payloads=payloads))

    assert run.execution_state is ExecutionState.PARTIAL
    assert run.result["result_state"] == "partial"
    assert run.result["unmatched_observations"][0]["channel_id"] == (
        "graft-channel:caller-added"
    )
    assert "unmatched_graft_observations" in run.reason_codes


def test_linkage_is_never_inferred_from_graft_metadata(tmp_path: Path) -> None:
    payloads = _payloads()
    for unit in payloads["graft_evidence_bundle"]["units"]:
        unit["originating_preparation_ref"] = None
        unit["linkage_evidence_refs"] = []
    payloads["graft_evidence_bundle"]["design_constraint_refs"] = [
        _ref("design-constraint:configured")
    ]

    run = ToolRegistry.load_default().run(_request(tmp_path, payloads=payloads))

    assert run.result["linkage_state"] == "provided_unlinked"
    assert run.result["preparation_linkages"] == []
    assert "preparation_linkage_not_provided" in run.reason_codes
    assert "configured_design_constraints_present" in run.reason_codes


def test_partial_linkage_remains_unlinked(tmp_path: Path) -> None:
    payloads = _payloads()
    second = payloads["graft_evidence_bundle"]["units"][1]
    second["originating_preparation_ref"] = None
    second["linkage_evidence_refs"] = []

    run = ToolRegistry.load_default().run(_request(tmp_path, payloads=payloads))

    assert run.result["linkage_state"] == "provided_unlinked"
    assert len(run.result["preparation_linkages"]) == 1
    assert "partial_preparation_linkage" in run.reason_codes


@pytest.mark.parametrize(
    ("field", "reason"),
    [
        ("measurement_spec_ref", "graft_context_binding_mismatch"),
        ("assay_ref", "graft_context_binding_mismatch"),
        ("sampling_context_ref", "graft_context_binding_mismatch"),
        ("reference_snapshot_ref", "graft_context_binding_mismatch"),
        ("algorithm_ref", "graft_context_binding_mismatch"),
    ],
)
def test_context_refs_must_match_the_configured_spec(
    tmp_path: Path, field: str, reason: str
) -> None:
    payloads = _payloads()
    payloads["graft_evidence_bundle"][field] = _ref("context:other")

    eligibility = ToolRegistry.load_default().check_eligibility(
        _request(tmp_path, payloads=payloads)
    )

    assert eligibility.eligible is False
    assert eligibility.reason_codes == [reason]


def test_product_case_is_cross_bound(tmp_path: Path) -> None:
    payloads = _payloads()
    payloads["graft_evidence_bundle"]["product_case_ref"] = _ref(
        "product-case:other"
    )

    eligibility = ToolRegistry.load_default().check_eligibility(
        _request(tmp_path, payloads=payloads)
    )

    assert eligibility.eligible is False
    assert eligibility.reason_codes == ["graft_product_case_binding_mismatch"]


@pytest.mark.parametrize("value", [True, "3.0", math.nan, math.inf])
def test_scientific_numeric_values_are_strict_and_finite(value: object) -> None:
    payload = _observation(1, "configured-primary", 3.0)
    payload["value"] = value

    with pytest.raises(ValidationError):
        GraftObservation.model_validate(payload)


def test_missing_state_cannot_carry_a_numeric_value() -> None:
    payload = _observation(1, "configured-primary", 3.0)
    payload["evidence_state"] = "missing"

    with pytest.raises(ValidationError):
        GraftObservation.model_validate(payload)


@pytest.mark.parametrize(
    "mutation",
    ["duplicate_rule", "duplicate_unit", "implicit_linkage"],
)
def test_ambiguous_or_implicit_input_contracts_fail(
    tmp_path: Path, mutation: str
) -> None:
    payloads = _payloads()
    if mutation == "duplicate_rule":
        payloads["graft_assessment_spec"]["rules"].append(
            deepcopy(payloads["graft_assessment_spec"]["rules"][0])
        )
    elif mutation == "duplicate_unit":
        payloads["graft_evidence_bundle"]["units"].append(
            deepcopy(payloads["graft_evidence_bundle"]["units"][0])
        )
    else:
        payloads["graft_evidence_bundle"]["units"][0][
            "originating_preparation_ref"
        ] = None

    run = ToolRegistry.load_default().run(_request(tmp_path, payloads=payloads))

    assert run.execution_state is ExecutionState.FAILED
    assert not run.artifacts


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ("assets", "p0_12_expression_assets_not_supported"),
        ("parameters", "p0_12_parameters_forbidden"),
        ("measurement", "p0_12_measurement_spec_parameter_forbidden"),
        ("seed", "p0_12_random_seed_forbidden"),
    ],
)
def test_envelope_extension_points_are_refused(
    tmp_path: Path, change: str, reason: str
) -> None:
    request = _request(tmp_path)
    updates: dict[str, object] = {}
    if change == "assets":
        updates["assets"] = [
            {
                "asset_id": "asset:unexpected",
                "path": tmp_path / "unexpected.json",
                "format": "json",
                "assay": "scRNA-seq",
                "matrix_semantics": "normalized_expression",
            }
        ]
    elif change == "parameters":
        updates["parameters"] = {"unexpected": True}
    elif change == "measurement":
        updates["measurement_spec_ref"] = "measurement-spec:unexpected"
    else:
        updates["random_seed"] = 9
    request = request.model_copy(update=updates)

    eligibility = adapter.check_eligibility(
        request, ToolRegistry.load_default().describe("P0-12")
    )

    assert eligibility.eligible is False
    assert reason in eligibility.reason_codes


def test_input_ids_do_not_change_run_identity_or_result_bytes(
    tmp_path: Path,
) -> None:
    first = ToolRegistry.load_default().run(
        _request(tmp_path / "first", output_dir=tmp_path / "output", input_id_prefix="a")
    )
    second = ToolRegistry.load_default().run(
        _request(tmp_path / "second", output_dir=tmp_path / "output", input_id_prefix="b")
    )

    assert first.run_id == second.run_id
    assert first.input_hash == second.input_hash
    assert first.result == second.result
    assert first.artifacts[0].path.read_bytes() == second.artifacts[0].path.read_bytes()
    assert not any(
        ref.input_id in json.dumps(first.result, sort_keys=True)
        for ref in first.request.object_inputs
    )


def test_existing_nonmatching_run_bundle_is_typed_failure(tmp_path: Path) -> None:
    request = _request(tmp_path)
    first = adapter.run(request, ToolRegistry.load_default().describe("P0-12"))
    first.artifacts[0].path.write_text("changed", encoding="utf-8")

    second = adapter.run(request, ToolRegistry.load_default().describe("P0-12"))

    assert second.execution_state is ExecutionState.FAILED
    assert second.reason_codes == ["existing_run_bundle_hash_mismatch"]
    assert second.artifacts == []


def test_v1_request_returns_typed_refusal(tmp_path: Path) -> None:
    request = ToolRequest(
        request_id="request-v1",
        tool_id="P0-12",
        output_dir=tmp_path,
    )

    eligibility = adapter.check_eligibility(
        request, ToolRegistry.load_default().describe("P0-12")
    )
    run = adapter.run(request, ToolRegistry.load_default().describe("P0-12"))

    assert eligibility.eligible is False
    assert eligibility.reason_codes == ["tool_request_v2_required"]
    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["tool_request_v2_required"]


def test_registry_detects_input_mutation_during_adapter_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = _request(tmp_path)
    original = adapter_module.evaluate_graft_assessment

    def mutate_input(**kwargs):
        request.object_inputs[0].path.write_text("{}", encoding="utf-8")
        return original(**kwargs)

    monkeypatch.setattr(adapter_module, "evaluate_graft_assessment", mutate_input)

    run = ToolRegistry.load_default().run(request)

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["input_asset_modified_during_run"]
    assert run.artifacts == []


def test_module_source_contains_no_product_specific_biology() -> None:
    package = Path(adapter_module.__file__).parent
    source = "\n".join(
        path.read_text(encoding="utf-8").casefold()
        for path in package.glob("*.py")
    )

    for literal in (
        "dopamine",
        "astrocyte",
        "oligodendrocyte",
        "mesenchymal",
        "human fetal",
        "rodent",
        "month post",
    ):
        assert literal not in source
