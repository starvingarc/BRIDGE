from __future__ import annotations

from hashlib import sha256
from importlib import resources
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from bridge.toolkit.contracts import (
    EvidenceState,
    ExecutionState,
    ImplementationState,
    MeasurementResult,
    InputAsset,
    ScoreState,
    ToolRequest,
    ToolRun,
    ToolPackageSpec,
)
from bridge.toolkit.schemas import load_schema
from bridge.toolkit.visualization import (
    FigureComponentSpec,
    FigureRegistry,
    FigureRegistrySnapshot,
    FigureRegistryState,
    FigureRole,
    FigureSurface,
    VisualizationAccessibility,
    VisualizationArtifactV2,
    VisualizationContextBinding,
    VisualizationDataBinding,
    VisualizationInteraction,
    VisualizationRenderBinding,
)


_VISUALIZATION_DATA_SHA = "a" * 64


def _visualization_artifact_v2() -> VisualizationArtifactV2:
    return VisualizationArtifactV2(
        visualization_id="visualization:run-1:qc-overview",
        component_id="bridge.qc.overview",
        component_version="0.1.0",
        data_binding=VisualizationDataBinding(
            artifact_id="artifact:run-1:qc-data",
            schema_ref="bridge://schemas/qc-visualization-data/v0.1",
            object_version="0.1.0",
            sha256=_VISUALIZATION_DATA_SHA,
            records_path="records",
            record_lookup_key="record_id",
            evidence_ids_field="evidence_ids",
            value_field="value",
            numerator_field="numerator",
            denominator_field="denominator",
            denominator_scope_field="denominator_scope",
            unit_field="unit",
            interval_lower_field="interval_lower",
            interval_upper_field="interval_upper",
            interval_semantics="95% bootstrap interval",
            evidence_state_field="evidence_state",
            scientific_status_field="scientific_status",
            missingness_field="missing_reason_codes",
            applicability_field="applicability",
        ),
        producer_tool_id="P0-01",
        producer_tool_version="0.1.0",
        producer_run_ref="run:run-1",
        evidence_ids=["evidence:run-1:qc"],
        evidence_states=[EvidenceState.MEASURED],
        scientific_status="candidate",
        applicability="applicable",
        denominator_label="declared observations",
        denominator_scope="selected QC data view",
        unit="metric-specific",
        context_bindings=[
            VisualizationContextBinding(
                role="environment",
                ref="ENV-P0-CORE-v0.1",
                version="0.1.0",
                sha256="b" * 64,
            )
        ],
        insight_title="QC distributions remain reviewable by observation.",
        takeaway="The figure presents measured QC values without a product score.",
        limitations=["This candidate contract does not validate biological quality."],
        accessibility=VisualizationAccessibility(
            alt_text="Three QC distributions for the declared observations.",
            long_description=(
                "The figure compares count depth, detected genes and mitochondrial "
                "fraction while retaining the declared denominator and limitations."
            ),
            table_artifact_id="artifact:run-1:qc-table",
            data_sha256=_VISUALIZATION_DATA_SHA,
        ),
        renders=[
            VisualizationRenderBinding(
                artifact_id="artifact:run-1:qc-svg",
                media_type="image/svg+xml",
                renderer_id="bridge.matplotlib",
                renderer_version="0.1.0",
                export_profile_id="bridge.static-vector.v0.1",
                data_sha256=_VISUALIZATION_DATA_SHA,
                config_sha256="c" * 64,
            )
        ],
    )


def test_measurement_result_requires_null_score_when_unavailable() -> None:
    with pytest.raises(ValidationError, match="domain_score"):
        MeasurementResult(
            measurement_id="m-1",
            measurement_spec_id="spec-1",
            metric_name="n_cells",
            raw_value=10,
            denominator=None,
            domain_score=70,
            score_state=ScoreState.UNAVAILABLE,
            evidence_state="measured",
        )


@pytest.mark.parametrize("score_state", [ScoreState.AVAILABLE, ScoreState.SHADOW])
def test_current_measurement_schema_rejects_all_non_null_domain_scores(score_state: ScoreState) -> None:
    with pytest.raises(ValidationError):
        MeasurementResult(
            measurement_id="m-1",
            measurement_spec_id="spec-1",
            metric_name="candidate_score",
            raw_value=0.7,
            domain_score=70,
            score_state=score_state,
            evidence_state="inferred",
        )


def test_current_measurement_schema_rejects_available_score_state_without_score() -> None:
    with pytest.raises(ValidationError, match="literal_error"):
        MeasurementResult(
            measurement_id="m-1",
            measurement_spec_id="spec-1",
            metric_name="candidate_score",
            raw_value=0.7,
            score_state=ScoreState.AVAILABLE,
            evidence_state="inferred",
        )


def test_scaffold_tool_run_cannot_contain_measurements(tmp_path: Path) -> None:
    request = ToolRequest(
        request_id="request-1",
        tool_id="P0-03",
        output_dir=tmp_path,
    )

    with pytest.raises(ValidationError, match="not_implemented"):
        ToolRun(
            run_id="run-1",
            request=request,
            implementation_state=ImplementationState.SCAFFOLD,
            execution_state=ExecutionState.NOT_IMPLEMENTED,
            tool_version="0.1.0",
            environment_spec_id="ENV-P0-CORE-v0.1",
            measurements=[
                MeasurementResult(
                    measurement_id="m-1",
                    measurement_spec_id="spec-1",
                    metric_name="placeholder",
                    raw_value=1,
                    domain_score=None,
                    score_state=ScoreState.UNAVAILABLE,
                    evidence_state="unavailable",
                )
            ],
        )


def test_scaffold_tool_run_cannot_claim_success_without_payload(tmp_path: Path) -> None:
    request = ToolRequest(
        request_id="request-1",
        tool_id="P0-03",
        output_dir=tmp_path,
    )

    with pytest.raises(ValidationError, match="scaffold ToolRun"):
        ToolRun(
            run_id="run-1",
            request=request,
            implementation_state=ImplementationState.SCAFFOLD,
            execution_state=ExecutionState.SUCCEEDED,
            tool_version="0.1.0",
            environment_spec_id="ENV-P0-CORE-v0.1",
        )


def test_scaffold_spec_allows_no_selected_methods() -> None:
    spec = ToolPackageSpec(
        tool_id="P0-03",
        name="Target Identity & Regional Fidelity",
        version="0.1.0",
        summary="Scaffold contract.",
        implementation_state=ImplementationState.SCAFFOLD,
        scientific_status="candidate",
        environment_spec_id="ENV-P0-CORE-v0.1",
        input_schema_ref="bridge://schemas/tool-request/v0.1",
        output_schema_ref="bridge://schemas/tool-run/v0.1",
        method_ids=[],
        card_ref="bridge://tool-cards/P0-03",
    )

    assert spec.method_ids == []


def test_implemented_spec_requires_a_selected_method() -> None:
    with pytest.raises(ValidationError, match="requires at least one method"):
        ToolPackageSpec(
            tool_id="P0-01",
            name="Input Audit & QC",
            version="0.1.0",
            summary="Executable contract.",
            implementation_state=ImplementationState.IMPLEMENTED,
            scientific_status="candidate",
            environment_spec_id="ENV-P0-CORE-v0.1",
            input_schema_ref="bridge://schemas/tool-request/v0.1",
            output_schema_ref="bridge://schemas/tool-run/v0.1",
            method_ids=[],
            card_ref="bridge://tool-cards/P0-01",
        )


def test_tool_package_schema_allows_empty_scaffolds_but_not_empty_implementations() -> None:
    validator = Draft202012Validator(load_schema("bridge://schemas/tool-package-spec/v0.1"))
    payload = {
        "tool_id": "P0-03",
        "name": "Target Identity & Regional Fidelity",
        "version": "0.1.0",
        "summary": "Scaffold contract.",
        "implementation_state": "scaffold",
        "scientific_status": "candidate",
        "optional": False,
        "environment_spec_id": "ENV-P0-CORE-v0.1",
        "input_schema_ref": "bridge://schemas/tool-request/v0.1",
        "output_schema_ref": "bridge://schemas/tool-run/v0.1",
        "method_ids": [],
        "card_ref": "bridge://tool-cards/P0-03",
    }

    assert list(validator.iter_errors(payload)) == []
    payload["implementation_state"] = "implemented"
    assert list(validator.iter_errors(payload))


def test_exported_json_schemas_enforce_score_and_scaffold_guards(tmp_path: Path) -> None:
    measurement_schema = load_schema("bridge://schemas/measurement-result/v0.1")
    measurement_validator = Draft202012Validator(measurement_schema)
    invalid_measurement = {
        "measurement_id": "m-1",
        "measurement_spec_id": "spec-1",
        "metric_name": "candidate_score",
        "raw_value": 0.7,
        "domain_score": 70,
        "score_state": "available",
        "evidence_state": "inferred",
        "provenance_refs": [],
    }
    assert list(measurement_validator.iter_errors(invalid_measurement))

    profile_schema = load_schema("bridge://schemas/qc-readiness-profile/v0.1")
    serialized_profile_schema = json.dumps(profile_schema["properties"]["score_state"])
    assert '"available"' not in serialized_profile_schema
    assert profile_schema["properties"]["domain_score"]["type"] == "null"

    request = ToolRequest(
        request_id="request-1",
        tool_id="P0-03",
        output_dir=tmp_path,
    )
    tool_run_schema = load_schema("bridge://schemas/tool-run/v0.1")
    tool_run_validator = Draft202012Validator(tool_run_schema)
    invalid_run = {
        "run_id": "run-1",
        "request": request.model_dump(mode="json"),
        "implementation_state": "scaffold",
        "execution_state": "succeeded",
        "tool_version": "0.1.0",
        "environment_spec_id": "ENV-P0-CORE-v0.1",
        "measurements": [],
        "artifacts": [],
        "visualizations": [],
        "result": None,
        "reason_codes": [],
        "warnings": [],
    }
    assert list(tool_run_validator.iter_errors(invalid_run))


def test_tool_request_rejects_relative_output_directory() -> None:
    with pytest.raises(ValidationError, match="absolute"):
        ToolRequest(
            request_id="request-1",
            tool_id="P0-01",
            output_dir=Path("relative-output"),
        )


def test_input_level_and_matrix_semantics_must_agree(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="analysis_ready"):
        InputAsset(
            asset_id="asset-1",
            path=(tmp_path / "counts.h5ad").resolve(),
            format="h5ad",
            input_level="analysis_ready",
            matrix_semantics="raw_counts",
            assay="scRNA-seq",
        )

    with pytest.raises(ValidationError, match="droplet_ready"):
        InputAsset(
            asset_id="asset-2",
            path=(tmp_path / "droplets.h5ad").resolve(),
            format="h5ad",
            input_level="droplet_ready",
            matrix_semantics="raw_counts",
            assay="scRNA-seq",
        )


@pytest.mark.parametrize(
    "schema_ref",
    [
        "bridge://schemas/biological-review-record/v0.1",
        "bridge://schemas/cell-state-benchmark-spec/v0.2",
        "bridge://schemas/benchmark-split-manifest/v0.2",
        "bridge://schemas/freeze-gate-spec/v0.2",
        "bridge://schemas/cell-state-release-manifest/v0.1",
    ],
)
def test_cell_state_freeze_contracts_are_exported(schema_ref: str) -> None:
    schema = load_schema(schema_ref)

    assert schema["$id"] == schema_ref


def test_visualization_v1_schema_remains_byte_identical() -> None:
    schema_path = resources.files("bridge.resources.schemas").joinpath(
        "visualization_artifact.schema.json"
    )

    assert (
        sha256(schema_path.read_bytes()).hexdigest()
        == "d75f02ae929c9e87cf5ef6286e5c590ce1e3f7d36cb40b9f3162c2cebd440c84"
    )


def test_visualization_v2_schema_matches_model_and_accepts_valid_artifact() -> None:
    schema_ref = "bridge://schemas/visualization-artifact/v0.2"
    schema = load_schema(schema_ref)
    expected = VisualizationArtifactV2.model_json_schema()
    expected["$id"] = schema_ref
    artifact = _visualization_artifact_v2()

    assert schema == expected
    assert not list(
        Draft202012Validator(schema).iter_errors(
            artifact.model_dump(mode="json")
        )
    )


def test_figure_registry_schema_matches_model() -> None:
    schema_ref = "bridge://schemas/figure-registry/v0.1"
    schema = load_schema(schema_ref)
    expected = FigureRegistrySnapshot.model_json_schema()
    expected["$id"] = schema_ref

    assert schema == expected
    payload = FigureRegistry.load_default().snapshot.model_dump(mode="json")
    validator = Draft202012Validator(schema)
    assert not list(validator.iter_errors(payload))

    payload["components"][0]["legacy_component_ids"] = []
    assert list(validator.iter_errors(payload))


def test_visualization_v2_requires_reasons_for_missing_evidence() -> None:
    payload = _visualization_artifact_v2().model_dump(mode="json")
    payload["evidence_states"] = ["missing"]
    payload["missing_reason_codes"] = []

    with pytest.raises(ValidationError, match="requires reason codes"):
        VisualizationArtifactV2.model_validate(payload)
    validator = Draft202012Validator(
        load_schema("bridge://schemas/visualization-artifact/v0.2")
    )
    assert list(validator.iter_errors(payload))


def test_visualization_v2_rejects_render_bound_to_different_data() -> None:
    payload = _visualization_artifact_v2().model_dump(mode="json")
    payload["renders"][0]["data_sha256"] = "d" * 64

    with pytest.raises(ValidationError, match="exact visualization data hash"):
        VisualizationArtifactV2.model_validate(payload)


@pytest.mark.parametrize(
    "component_id",
    ["bridge.qc.overview.v0.1", "bridge.qc.overview.v0.1.0"],
)
def test_visualization_v2_separates_component_id_and_version(
    component_id: str,
) -> None:
    payload = _visualization_artifact_v2().model_dump(mode="json")
    payload["component_id"] = component_id

    with pytest.raises(ValidationError, match="must not be embedded"):
        VisualizationArtifactV2.model_validate(payload)
    validator = Draft202012Validator(
        load_schema("bridge://schemas/visualization-artifact/v0.2")
    )
    assert list(validator.iter_errors(payload))


def test_visualization_data_binding_requires_complete_interval_semantics() -> None:
    payload = _visualization_artifact_v2().data_binding.model_dump(mode="json")
    payload["interval_upper_field"] = None

    with pytest.raises(ValidationError, match="interval lower, upper and semantics"):
        VisualizationDataBinding.model_validate(payload)
    artifact_payload = _visualization_artifact_v2().model_dump(mode="json")
    artifact_payload["data_binding"]["interval_upper_field"] = None
    validator = Draft202012Validator(
        load_schema("bridge://schemas/visualization-artifact/v0.2")
    )
    assert list(validator.iter_errors(artifact_payload))


@pytest.mark.parametrize(
    "private_ref",
    [
        "/private/server/run.json",
        "artifact:/" + "data1/user/run.json",
        "bridge:///" + "Users/user/run.json",
        "artifact:C:/" + "Users/user/run.json",
        "artifact:%2F" + "data1%2Fuser%2Frun.json",
    ],
)
def test_visualization_v2_rejects_private_filesystem_references(
    private_ref: str,
) -> None:
    payload = _visualization_artifact_v2().model_dump(mode="json")
    payload["producer_run_ref"] = private_ref

    with pytest.raises(ValidationError, match="string_pattern_mismatch"):
        VisualizationArtifactV2.model_validate(payload)
    validator = Draft202012Validator(
        load_schema("bridge://schemas/visualization-artifact/v0.2")
    )
    assert list(validator.iter_errors(payload))


def test_figure_registry_discovers_legacy_and_typed_qc_components() -> None:
    registry = FigureRegistry.load_default()

    assert registry.validation_summary() == {
        "valid": True,
        "registry_id": "bridge.figure-registry",
        "object_version": "0.1.0",
        "component_count": 43,
        "typed_candidate_count": 36,
        "legacy_untyped_count": 7,
        "producer_tool_ids": ["P0-01", "P0-02", "P0-03", "P0-04", "P0-05", "P0-06", "P0-07", "P0-08", "P0-09", "P0-10", "P0-11", "P0-12"],
    }
    assert len(registry.list(tool_id="P0-01")) == 6
    assert len(registry.list(tool_id="P0-07")) == 3
    assert len(registry.list(tool_id="P0-09")) == 3
    assert len(registry.list(tool_id="P0-12")) == 3
    assert (
        registry.get("bridge.qc.overview.v0.1").component_ref
        == "bridge.qc.overview@0.1.0"
    )
    typed = registry.get("bridge.qc.overview@0.2.0")
    assert typed.registry_state is FigureRegistryState.TYPED_CANDIDATE
    assert {surface.value for surface in typed.surfaces} == {
        "static_export",
        "table",
    }
    with pytest.raises(ValueError, match="has not migrated"):
        registry.validate_artifact(_visualization_artifact_v2())


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("evidence_ids", [""]),
        ("evidence_ids", ["   "]),
        ("missing_reason_codes", [""]),
        ("missing_reason_codes", ["   "]),
        ("limitations", [""]),
        ("limitations", ["   "]),
    ],
)
def test_visualization_v2_rejects_blank_semantic_items(
    field_name: str,
    value: list[str],
) -> None:
    payload = _visualization_artifact_v2().model_dump(mode="json")
    payload[field_name] = value
    if field_name == "missing_reason_codes":
        payload["evidence_states"] = ["missing"]

    with pytest.raises(ValidationError):
        VisualizationArtifactV2.model_validate(payload)
    validator = Draft202012Validator(
        load_schema("bridge://schemas/visualization-artifact/v0.2")
    )
    assert list(validator.iter_errors(payload))


def test_visualization_schema_enforces_public_interaction_ids() -> None:
    payload = _visualization_artifact_v2().model_dump(mode="json")
    payload["interactions"]["filter_ids"] = ["/private/sample-id"]

    with pytest.raises(ValidationError):
        VisualizationArtifactV2.model_validate(payload)
    validator = Draft202012Validator(
        load_schema("bridge://schemas/visualization-artifact/v0.2")
    )
    assert list(validator.iter_errors(payload))


def test_figure_registry_schema_enforces_tool_ids() -> None:
    payload = FigureRegistry.load_default().snapshot.model_dump(mode="json")
    payload["components"][0]["producer_tool_ids"] = ["P0-99"]

    with pytest.raises(ValidationError):
        FigureRegistrySnapshot.model_validate(payload)
    validator = Draft202012Validator(
        load_schema("bridge://schemas/figure-registry/v0.1")
    )
    assert list(validator.iter_errors(payload))


def test_visualization_v2_requires_denominator_semantics_with_fields() -> None:
    validator = Draft202012Validator(
        load_schema("bridge://schemas/visualization-artifact/v0.2")
    )

    without_labels = _visualization_artifact_v2().model_dump(mode="json")
    without_labels["denominator_label"] = None
    without_labels["denominator_scope"] = None
    with pytest.raises(ValidationError, match="denominator semantics"):
        VisualizationArtifactV2.model_validate(without_labels)
    assert list(validator.iter_errors(without_labels))

    without_fields = _visualization_artifact_v2().model_dump(mode="json")
    binding = without_fields["data_binding"]
    binding["numerator_field"] = None
    binding["denominator_field"] = None
    binding["denominator_scope_field"] = None
    with pytest.raises(ValidationError, match="denominator semantics"):
        VisualizationArtifactV2.model_validate(without_fields)
    assert list(validator.iter_errors(without_fields))


def test_visualization_v2_rejects_table_bound_to_different_data() -> None:
    payload = _visualization_artifact_v2().model_dump(mode="json")
    payload["accessibility"]["data_sha256"] = "d" * 64

    with pytest.raises(ValidationError, match="table fallback"):
        VisualizationArtifactV2.model_validate(payload)


def test_figure_registry_returns_defensive_copies() -> None:
    registry = FigureRegistry.load_default()
    registry.list()[0].producer_tool_ids.clear()
    registry.snapshot.components.clear()

    assert registry.validation_summary()["component_count"] == 43
    assert len(registry.list(tool_id="P0-01")) == 6
    assert FigureRegistry.load_default().validation_summary()["component_count"] == 43


def test_typed_figure_validation_enforces_interactions_and_fallbacks() -> None:
    component = FigureComponentSpec(
        component_id="bridge.qc.overview",
        component_version="0.1.0",
        title="QC metric distributions",
        question="Can observations support the requested analyses?",
        figure_family="distribution_small_multiples",
        producer_tool_ids=["P0-01"],
        registry_state=FigureRegistryState.TYPED_CANDIDATE,
        default_role=FigureRole.SUPPORTING,
        data_schema_refs=["bridge://schemas/qc-visualization-data/v0.1"],
        surfaces=[FigureSurface.STATIC_EXPORT],
        required_fallbacks=[
            "table",
            "alt_text",
            "long_description",
            "static_vector",
        ],
    )
    registry = FigureRegistry(FigureRegistrySnapshot(components=[component]))
    payload = _visualization_artifact_v2().model_dump(mode="json")
    payload["interactions"]["filter_ids"] = ["sample_group"]
    payload["renders"][0]["media_type"] = "image/png"
    artifact = VisualizationArtifactV2.model_validate(payload)

    with pytest.raises(ValueError, match="unregistered interactions"):
        registry.validate_artifact(artifact)

    payload["interactions"]["filter_ids"] = []
    artifact = VisualizationArtifactV2.model_validate(payload)
    with pytest.raises(ValueError, match="static_vector"):
        registry.validate_artifact(artifact)


@pytest.mark.parametrize(
    "component_id",
    ["bridge.qc.overview.v0.1", "bridge.qc.overview.v0.1.0"],
)
def test_figure_registry_separates_component_id_and_version(
    component_id: str,
) -> None:
    payload = FigureRegistry.load_default().snapshot.model_dump(mode="json")
    payload["components"][0]["component_id"] = component_id

    with pytest.raises(ValidationError, match="must not be embedded"):
        FigureRegistrySnapshot.model_validate(payload)
    validator = Draft202012Validator(
        load_schema("bridge://schemas/figure-registry/v0.1")
    )
    assert list(validator.iter_errors(payload))


@pytest.mark.parametrize(
    ("field_name", "invalid_value", "valid_value"),
    [
        ("alt_text", "a" * 11, "a" * 12),
        ("long_description", "a" * 39, "a" * 40),
    ],
)
def test_visualization_accessibility_preserves_length_boundaries(
    field_name: str,
    invalid_value: str,
    valid_value: str,
) -> None:
    validator = Draft202012Validator(
        load_schema("bridge://schemas/visualization-artifact/v0.2")
    )
    payload = _visualization_artifact_v2().model_dump(mode="json")
    payload["accessibility"][field_name] = invalid_value

    with pytest.raises(ValidationError):
        VisualizationArtifactV2.model_validate(payload)
    assert list(validator.iter_errors(payload))

    payload["accessibility"][field_name] = valid_value
    VisualizationArtifactV2.model_validate(payload)
    assert not list(validator.iter_errors(payload))
