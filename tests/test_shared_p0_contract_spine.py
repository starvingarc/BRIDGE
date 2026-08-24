from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from bridge.tool_packages._configurable_contracts import (
    BiologicalUnitBinding,
    BiologicalUnitManifest,
    ProductCase,
    VersionedObjectRef,
)
from bridge.toolkit.contracts import (
    DataViewBinding,
    EvidenceState,
    ExecutionState,
    ImplementationState,
    MeasurementResultV2,
    ScoreState,
    ToolRequestV2,
    ToolRunV2,
)
from bridge.toolkit.schemas import load_schema


def _ref(object_id: str) -> VersionedObjectRef:
    return VersionedObjectRef(object_id=object_id, object_version="1.0.0")


def _binding() -> BiologicalUnitBinding:
    preparation = _ref("preparation:demo")
    sample = _ref("sample:demo")
    return BiologicalUnitBinding(
        analysis_unit_ref=preparation,
        analysis_unit_kind="preparation",
        independence_group_ref=sample,
        independence_group_kind="sample",
        preparation_ref=preparation,
        sample_ref=sample,
    )


def _manifest(**overrides: object) -> BiologicalUnitManifest:
    payload: dict[str, object] = {
        "object_version": "0.1.0",
        "manifest_id": "biological-unit-manifest:demo",
        "manifest_version": "1.0.0",
        "schema_ref": "bridge://schemas/biological-unit-manifest/v0.1",
        "generator_tool_id": "P0-01",
        "generator_tool_version": "1.0.0",
        "data_view_ref": "data-view:demo@1.0.0",
        "selected_artifact_sha256": "a" * 64,
        "observation_ids_sha256": "b" * 64,
        "n_observations": 8,
        "assignment_schema_ref": "bridge://schemas/biological-unit-assignment/v0.1",
        "assignment_artifact_sha256": "c" * 64,
        "assignment_row_count": 8,
        "unit_identity_namespace_ref": _ref("biological-unit-namespace:demo"),
        "analysis_unit_kind": "preparation",
        "independence_group_kind": "sample",
        "independence_scope_ref": _ref("independence-scope:demo"),
        "lineage_state": "declared",
        "unit_bindings": [_binding()],
    }
    payload.update(overrides)
    return BiologicalUnitManifest.model_validate(payload)


def test_v2_run_accepts_v1_shaped_measurement_without_enabling_score(
    tmp_path: Path,
) -> None:
    measurement = MeasurementResultV2(
        measurement_id="measurement:demo",
        measurement_spec_id="measurement-spec:demo",
        metric_name="demo_fraction",
        raw_value=0.5,
        domain_score=None,
        score_state=ScoreState.UNAVAILABLE,
        evidence_state=EvidenceState.MEASURED,
    )
    run = ToolRunV2(
        run_id="tool-run:demo@1.0.0",
        request=ToolRequestV2(
            request_id="request:demo",
            tool_id="P0-08",
            output_dir=tmp_path.resolve(),
        ),
        implementation_state=ImplementationState.IMPLEMENTED,
        execution_state=ExecutionState.SUCCEEDED,
        tool_version="1.0.0",
        environment_spec_id="ENV-P0-CORE-v0.1",
        measurements=[measurement],
        result_schema_ref="bridge://schemas/evidence-sufficiency-run-result/v0.1",
        result={},
    )

    assert run.measurements == [measurement]
    assert run.measurements[0].domain_score is None


def test_measurement_v2_requires_paired_source_and_interval_metadata() -> None:
    common = {
        "measurement_id": "measurement:demo",
        "measurement_spec_id": "measurement-spec:demo",
        "metric_name": "demo_fraction",
        "raw_value": 0.5,
        "domain_score": None,
        "score_state": "unavailable",
        "evidence_state": "measured",
    }
    with pytest.raises(ValidationError, match="source_run_ref"):
        MeasurementResultV2(**common, source_execution_state="succeeded")
    with pytest.raises(ValidationError, match="interval metadata"):
        MeasurementResultV2(**common, interval_confidence_level=0.95)


def test_p0_01_cannot_claim_reviewed_biological_lineage() -> None:
    with pytest.raises(ValidationError, match="P0-01 can only generate declared"):
        _manifest(
            lineage_state="reviewed",
            review_gate_ref=_ref("biological-unit-review:demo"),
            review_gate_sha256="d" * 64,
        )


@pytest.mark.parametrize("independence_kind", ["capture", "graft_unit"])
def test_technical_units_cannot_be_independence_groups(
    independence_kind: str,
) -> None:
    with pytest.raises(ValidationError, match="independence assertions"):
        _manifest(independence_group_kind=independence_kind)


def test_product_case_requires_complete_manifest_binding() -> None:
    common = {
        "object_version": "0.1.0",
        "product_case_id": "product-case:demo",
        "case_version": "1.0.0",
        "product_definition_ref": _ref("product-definition:demo"),
        "sample_or_preparation_ref": _ref("preparation:demo"),
        "measurement_spec_ref": _ref("measurement-spec:demo"),
        "assay": "scRNA-seq",
        "provenance_refs": [_ref("provenance:demo")],
        "created_at": datetime(2026, 8, 25, tzinfo=timezone.utc),
    }
    with pytest.raises(ValidationError, match="must be supplied together"):
        ProductCase(
            **common,
            biological_unit_manifest_ref=_ref("biological-unit-manifest:demo"),
        )


def test_data_view_requires_paired_manifest_reference_and_checksum() -> None:
    with pytest.raises(ValidationError, match="must be paired"):
        DataViewBinding(
            view_id="data-view:demo@1.0.0",
            view_kind="qc_selected_observations",
            artifact_id="artifact:demo",
            sha256="a" * 64,
            parent_asset_id="asset:demo",
            parent_asset_sha256="b" * 64,
            matrix_location="X",
            matrix_semantics="raw_counts",
            n_observations=8,
            observation_ids_sha256="c" * 64,
            biological_unit_manifest_ref="biological-unit-manifest:demo@1.0.0",
        )


@pytest.mark.parametrize(
    "schema_ref",
    [
        "bridge://schemas/biological-unit-assignment/v0.1",
        "bridge://schemas/biological-unit-manifest/v0.1",
        "bridge://schemas/measurement-result/v0.2",
        "bridge://schemas/product-case/v0.1",
        "bridge://schemas/product-definition-card/v0.1",
    ],
)
def test_shared_contract_schemas_are_packaged(schema_ref: str) -> None:
    assert load_schema(schema_ref)["$id"] == schema_ref
