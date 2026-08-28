from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import anndata as ad
import h5py
import numpy as np
import pandas as pd
import pytest
from jsonschema import Draft202012Validator
from scipy import sparse
from scipy.io import mmwrite

from bridge.tool_packages._configurable_contracts import (
    BiologicalUnitAssignmentArtifact,
    BiologicalUnitManifest,
    biological_unit_assignment_reasons,
    observation_ids_sha256,
)
from bridge.tool_packages.p0_01_input_qc import executor as input_qc_executor
from bridge.tool_packages.p0_01_input_qc.io import (
    P001_STRUCTURED_OUTPUT_INDEX_SCHEMA_REF,
    P001_STRUCTURED_OUTPUT_INDEX_V2_SCHEMA_REF,
    P001VisualizationArtifactSet,
    P001StructuredOutputIndex,
    P001StructuredOutputIndexV2,
    QC_COMPONENT_REFS,
    QCVisualizationDataProfile,
    sha256_path,
)
from bridge.tool_packages.p0_01_input_qc.visualization import (
    FLAG_LABELS,
    _capture_sort_key,
    render_qc_flag_intersections,
)
from bridge.tool_packages.p0_01_input_qc.measurement_specs import load_measurement_spec
from bridge.toolkit.contracts import (
    ExecutionState,
    InputAsset,
    QCReadinessProfileV2,
    ToolRequest,
)
from bridge.toolkit.registry import ToolRegistry
from bridge.toolkit.schemas import load_schema
from bridge.toolkit.visualization import FigureRegistry


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_tree(path: Path) -> str:
    digest = hashlib.sha256()
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(child.relative_to(path).as_posix().encode("utf-8"))
        digest.update(child.read_bytes())
    return digest.hexdigest()


def _write_h5ad(path: Path, *, counts: bool, assay: str = "scRNA-seq") -> Path:
    matrix = np.array(
        [
            [10, 0, 1, 0, 4, 3],
            [2, 8, 0, 1, 3, 2],
            [0, 1, 9, 2, 4, 1],
            [4, 0, 2, 8, 1, 2],
            [3, 2, 1, 0, 8, 4],
            [1, 4, 2, 3, 0, 9],
        ],
        dtype=np.int64 if counts else np.float64,
    )
    if not counts:
        matrix = np.log1p(matrix)
    obs = pd.DataFrame(
        {"sample_id": ["sample-a"] * 6, "capture_id": ["capture-a"] * 6},
        index=[f"cell-{index}" for index in range(6)],
    )
    var = pd.DataFrame(index=["MT-ND1", "RPS3", "SOX2", "LMX1A", "FOXA2", "TUBB3"])
    ad.AnnData(sparse.csr_matrix(matrix), obs=obs, var=var).write_h5ad(path)
    return path


def _request(tmp_path: Path, input_path: Path, *, semantics: str, assay: str = "scRNA-seq", spec: str | None = None) -> ToolRequest:
    return ToolRequest(
        request_id="qc-request",
        tool_id="P0-01",
        output_dir=(tmp_path / "results").resolve(),
        assets=[
            InputAsset(
                asset_id="asset-1",
                path=input_path.resolve(),
                format="h5ad",
                input_level="count_ready" if semantics == "raw_counts" else "analysis_ready",
                matrix_location="X",
                matrix_semantics=semantics,
                assay=assay,
                metadata={"sample_id_column": "sample_id", "capture_id_column": "capture_id"},
            )
        ],
        measurement_spec_ref=spec,
    )


def _tenx_request(tmp_path: Path, tenx: Path, *, label: str) -> ToolRequest:
    return ToolRequest(
        request_id=f"qc-{label}",
        tool_id="P0-01",
        output_dir=(tmp_path / "results").resolve(),
        assets=[
            InputAsset(
                asset_id=f"asset-{label}",
                path=tenx.resolve(),
                format="10x_mtx",
                input_level="count_ready",
                matrix_semantics="raw_counts",
                assay="scRNA-seq",
                metadata={"capture_id": "capture-1", "sample_id": "sample-1"},
            )
        ],
    )


def _with_lineage(request: ToolRequest, declaration: dict) -> ToolRequest:
    asset = request.assets[0]
    return request.model_copy(
        update={
            "assets": [
                asset.model_copy(
                    update={
                        "metadata": {
                            **asset.metadata,
                            "biological_unit_lineage": declaration,
                        }
                    }
                )
            ]
        }
    )


def _lineage_metadata(*, source_ref: str = "preparation:product-a@1.0.0") -> dict:
    return {
        "source_unit_kind": "preparation",
        "source_unit_ref": _versioned_ref(source_ref),
        "unit_identity_namespace_ref": _versioned_ref("unit-namespace:study-a@1.0.0"),
        "analysis_unit_kind": "preparation",
        "independence_group_kind": "donor",
        "independence_scope_ref": _versioned_ref("independence-scope:study-a@1.0.0"),
        "observation_ref_columns": {
            "capture": "capture_ref",
            "preparation": "preparation_ref",
            "donor": "donor_ref",
        },
    }


def _versioned_ref(value: str) -> dict[str, str]:
    object_id, object_version = value.rsplit("@", 1)
    return {"object_id": object_id, "object_version": object_version}


def _artifact_json(run, kind: str) -> tuple[Path, dict]:
    artifact = next(item for item in run.artifacts if item.kind == kind)
    return artifact.path, json.loads(artifact.path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("spec_id", "observation_unit"),
    [
        ("QC-scRNA-candidate-v0.1", "cell"),
        ("QC-snRNA-candidate-v0.1", "nucleus"),
    ],
)
def test_candidate_measurement_spec_capture_unit_is_caller_declared(
    spec_id: str,
    observation_unit: str,
) -> None:
    measurement_spec = load_measurement_spec(spec_id)
    assert measurement_spec is not None
    assert measurement_spec.analysis_unit == (
        f"{observation_unit} grouped by a row-complete caller-declared capture identifier"
    )
    assert "caller-declared" in measurement_spec.analysis_unit
    assert all(
        term not in measurement_spec.analysis_unit for term in ("confirmed", "verified")
    )


def test_analysis_ready_h5ad_emits_raw_structure_without_count_flags(tmp_path: Path) -> None:
    input_path = _write_h5ad(tmp_path / "analysis.h5ad", counts=False)

    run = ToolRegistry.load_default().run(
        _request(tmp_path, input_path, semantics="normalized_expression")
    )

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result["input_level"] == "analysis_ready"
    assert run.result["readiness_state"] == "limited"
    assert run.result["cell_qc"]["count_metrics_state"] == "not_assessed"
    assert run.result["domain_score"] is None
    assert "measurement_spec_not_selected" in run.result["missing_inputs"]
    assert all(measurement.domain_score is None for measurement in run.measurements)

    _, data_payload = _artifact_json(run, "qc_visualization_data")
    profile = QCVisualizationDataProfile.model_validate(data_payload)
    unavailable = [
        record
        for record in profile.records
        if record.evidence_state.value == "unavailable"
    ]
    assert profile.source_table_artifact_id is None
    assert unavailable
    assert all(record.value is None and record.numerator is None for record in unavailable)
    _, artifact_set_payload = _artifact_json(run, "visualization_artifact_set")
    artifact_set = P001VisualizationArtifactSet.model_validate(artifact_set_payload)
    assert {item.component_ref for item in artifact_set.visualizations} == set(
        QC_COMPONENT_REFS
    )
    assert all(
        item.scientific_status == "candidate"
        for item in artifact_set.visualizations
    )


def test_count_ready_h5ad_writes_immutable_artifacts_and_visualizations(tmp_path: Path) -> None:
    input_path = _write_h5ad(tmp_path / "counts.h5ad", counts=True)
    before = _sha256(input_path)

    run = ToolRegistry.load_default().run(
        _request(
            tmp_path,
            input_path,
            semantics="raw_counts",
            spec="QC-scRNA-candidate-v0.1",
        )
    )

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert _sha256(input_path) == before
    assert run.input_hash == before
    assert run.result["input_level"] == "count_ready"
    assert run.result["measurement_spec_status"] == "candidate"
    assert run.result["cell_qc"]["feature_set_policy_id"] == "QC-feature-set-scRNA-human-symbol-v0.1"
    assert run.result["score_state"] == "unavailable"
    assert run.result["domain_score"] is None
    assert run.artifacts
    assert {artifact.kind for artifact in run.artifacts} >= {
        "manifest",
        "qc_metrics",
        "derived_h5ad",
        "visualization_data",
        "visualization_svg",
        "visualization_png",
        "qc_visualization_data",
        "qc_visualization_table",
        "qc_visualization_svg",
        "qc_visualization_png",
        "visualization_artifact_set",
        P001_STRUCTURED_OUTPUT_INDEX_V2_SCHEMA_REF,
    }
    assert len(run.visualizations) == 2
    assert all(item.evidence_ids for item in run.visualizations)
    assert all(artifact.path.is_file() for artifact in run.artifacts)

    data_path, data_payload = _artifact_json(run, "qc_visualization_data")
    profile = QCVisualizationDataProfile.model_validate(data_payload)
    assert set(record.component_ref for record in profile.records) == set(
        QC_COMPONENT_REFS
    )
    assert "capture-a" not in data_path.read_text(encoding="utf-8")
    assert "capture_001" in data_path.read_text(encoding="utf-8")
    table_path = next(
        artifact.path
        for artifact in run.artifacts
        if artifact.kind == "qc_visualization_table"
    )
    assert "capture-a" not in table_path.read_text(encoding="utf-8")

    _, artifact_set_payload = _artifact_json(run, "visualization_artifact_set")
    artifact_set = P001VisualizationArtifactSet.model_validate(artifact_set_payload)
    registry = FigureRegistry.load_default()
    for visualization in artifact_set.visualizations:
        registry.validate_artifact(visualization)
        assert visualization.data_binding.sha256 == artifact_set.data_profile_sha256
        assert {render.media_type for render in visualization.renders} == {
            "image/svg+xml",
            "image/png",
        }

    v1_path = next(
        artifact.path
        for artifact in run.artifacts
        if artifact.kind == P001_STRUCTURED_OUTPUT_INDEX_SCHEMA_REF
    )
    v1_index = P001StructuredOutputIndex.model_validate_json(v1_path.read_bytes())
    assert {
        record.role for record in v1_index.outputs
    }.isdisjoint({"qc_visualization_data", "visualization_artifact_set"})
    v2_path = next(
        artifact.path
        for artifact in run.artifacts
        if artifact.kind == P001_STRUCTURED_OUTPUT_INDEX_V2_SCHEMA_REF
    )
    v2_index = P001StructuredOutputIndexV2.model_validate_json(v2_path.read_bytes())
    assert {
        record.role for record in v2_index.outputs
    } >= {
        "qc_readiness_profile_v2",
        "qc_visualization_data",
        "visualization_artifact_set",
    }
    for schema_ref, payload in (
        ("bridge://schemas/qc-visualization-data/v0.1", data_payload),
        (
            "bridge://schemas/p0-01-visualization-artifact-set/v0.1",
            artifact_set_payload,
        ),
        (
            "bridge://schemas/p0-01-structured-output-index/v0.2",
            json.loads(v2_path.read_text(encoding="utf-8")),
        ),
    ):
        assert not list(Draft202012Validator(load_schema(schema_ref)).iter_errors(payload))


def test_typed_qc_visualization_outputs_are_deterministic(tmp_path: Path) -> None:
    input_path = _write_h5ad(tmp_path / "deterministic-figures.h5ad", counts=True)
    first_request = _request(
        tmp_path,
        input_path,
        semantics="raw_counts",
        spec="QC-scRNA-candidate-v0.1",
    )
    second_request = first_request.model_copy(
        update={"output_dir": (tmp_path / "second-results").resolve()}
    )

    first = ToolRegistry.load_default().run(first_request)
    second = ToolRegistry.load_default().run(second_request)

    assert first.execution_state is second.execution_state is ExecutionState.SUCCEEDED
    assert first.run_id == second.run_id
    deterministic_kinds = {
        "qc_visualization_data",
        "qc_visualization_table",
        "qc_visualization_svg",
        "qc_visualization_png",
        "visualization_artifact_set",
    }
    first_hashes = {
        artifact.artifact_id: artifact.sha256
        for artifact in first.artifacts
        if artifact.kind in deterministic_kinds
    }
    second_hashes = {
        artifact.artifact_id: artifact.sha256
        for artifact in second.artifacts
        if artifact.kind in deterministic_kinds
    }
    assert first_hashes == second_hashes
    assert len(first_hashes) == 11


def test_anonymous_capture_labels_sort_by_numeric_suffix() -> None:
    labels = ["Capture 1", "Capture 10", "Capture 2", "Unavailable"]

    assert sorted(labels, key=_capture_sort_key) == [
        "Capture 1",
        "Capture 2",
        "Capture 10",
        "Unavailable",
    ]


def test_single_flag_combination_uses_a_linear_count_axis(tmp_path: Path) -> None:
    flags = pd.DataFrame(
        {column: [False] * 8 for column in FLAG_LABELS}
    )

    svg_path, _ = render_qc_flag_intersections(
        flags,
        tmp_path / "single-combination",
        observation_unit="cells",
    )
    svg = svg_path.read_text(encoding="utf-8")
    assert "No candidate flag" in svg
    assert "log scale" not in svg


@pytest.mark.parametrize("reference_source", ["columns", "constants"])
def test_v2_profile_binds_exact_input_and_declared_lineage(
    tmp_path: Path,
    reference_source: str,
) -> None:
    input_path = _write_h5ad(tmp_path / f"counts-{reference_source}.h5ad", counts=True)
    declaration = _lineage_metadata()
    if reference_source == "columns":
        adata = ad.read_h5ad(input_path)
        adata.obs["capture_ref"] = "capture:capture-a@1.0.0"
        adata.obs["preparation_ref"] = "preparation:product-a@1.0.0"
        adata.obs["donor_ref"] = "donor:donor-a@1.0.0"
        adata.write_h5ad(input_path)
    else:
        declaration["observation_ref_columns"] = {}
        declaration["constant_unit_refs"] = {
            "capture": _versioned_ref("capture:capture-a@1.0.0"),
            "preparation": _versioned_ref("preparation:product-a@1.0.0"),
            "donor": _versioned_ref("donor:donor-a@1.0.0"),
        }
    before = _sha256(input_path)
    request = _request(
        tmp_path,
        input_path,
        semantics="raw_counts",
        spec="QC-scRNA-candidate-v0.1",
    )
    request = request.model_copy(
        update={
            "assets": [
                request.assets[0].model_copy(
                    update={
                        "metadata": {
                            **request.assets[0].metadata,
                            "biological_unit_lineage": declaration,
                        }
                    }
                )
            ]
        }
    )

    run = ToolRegistry.load_default().run(request)

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert _sha256(input_path) == before == run.input_hash
    assert "selected_data_view" not in run.result
    _, v1_payload = _artifact_json(run, "qc_profile")
    assert v1_payload == run.result

    v2_path, v2_payload = _artifact_json(run, "qc_profile_v2")
    profile_v2 = QCReadinessProfileV2.model_validate(v2_payload)
    assignment_path, assignment_payload = _artifact_json(run, "biological_unit_assignment")
    manifest_path, manifest_payload = _artifact_json(run, "biological_unit_manifest")
    index_path, index_payload = _artifact_json(
        run,
        P001_STRUCTURED_OUTPUT_INDEX_SCHEMA_REF,
    )
    assignment = BiologicalUnitAssignmentArtifact.model_validate(assignment_payload)
    manifest = BiologicalUnitManifest.model_validate(manifest_payload)
    for payload, schema_ref in (
        (v2_payload, "bridge://schemas/qc-readiness-profile/v0.2"),
        (assignment_payload, "bridge://schemas/biological-unit-assignment/v0.1"),
        (manifest_payload, "bridge://schemas/biological-unit-manifest/v0.1"),
        (index_payload, P001_STRUCTURED_OUTPUT_INDEX_SCHEMA_REF),
    ):
        assert not list(Draft202012Validator(load_schema(schema_ref)).iter_errors(payload))
    assignment_artifact = next(
        item for item in run.artifacts if item.kind == "biological_unit_assignment"
    )
    manifest_artifact = next(
        item for item in run.artifacts if item.kind == "biological_unit_manifest"
    )
    structured_index = P001StructuredOutputIndex.model_validate(index_payload)

    assert _sha256(v2_path) == next(
        item.sha256 for item in run.artifacts if item.kind == "qc_profile_v2"
    )
    assert _sha256(assignment_path) == assignment_artifact.sha256
    assert _sha256(manifest_path) == manifest_artifact.sha256
    assert _sha256(index_path) == next(
        item.sha256
        for item in run.artifacts
        if item.kind == P001_STRUCTURED_OUTPUT_INDEX_SCHEMA_REF
    )
    assert {item.role for item in structured_index.outputs} == {
        "qc_readiness_profile_v2",
        "biological_unit_assignment",
        "biological_unit_manifest",
    }
    indexed_artifacts = {item.artifact_id: item for item in structured_index.outputs}
    for artifact in (assignment_artifact, manifest_artifact):
        assert indexed_artifacts[artifact.artifact_id].sha256 == artifact.sha256
    assert manifest.assignment_artifact_sha256 == assignment_artifact.sha256
    assert manifest.lineage_state.value == "declared"
    assert manifest.review_gate_ref is None
    assert manifest.review_gate_sha256 is None
    assert manifest.assignment_row_count == manifest.n_observations == 6
    assert manifest.analysis_unit_kind.value == "preparation"
    assert manifest.independence_group_kind == "donor"
    assert manifest.selected_artifact_sha256 == before
    assert profile_v2.measurement_spec_version == "0.1.0"
    assert profile_v2.selected_data_view is not None
    expected_observation_digest = observation_ids_sha256(
        [f"cell-{index}" for index in range(6)]
    )
    assert profile_v2.selected_data_view.view_kind == "all_observations"
    assert profile_v2.selected_data_view.artifact_id == "input-asset:asset-1"
    assert profile_v2.selected_data_view.parent_asset_id == "asset-1"
    assert profile_v2.selected_data_view.sha256 == before
    assert profile_v2.selected_data_view.parent_asset_sha256 == before
    assert profile_v2.selected_data_view.matrix_location == "X"
    assert profile_v2.selected_data_view.matrix_semantics == "raw_counts"
    assert profile_v2.selected_data_view.n_observations == 6
    assert (
        profile_v2.selected_data_view.observation_ids_sha256
        == expected_observation_digest
    )
    assert assignment.observation_ids_sha256 == expected_observation_digest
    assert manifest.observation_ids_sha256 == expected_observation_digest
    assert profile_v2.selected_data_view.biological_unit_manifest_ref == manifest.ref.ref
    assert (
        profile_v2.selected_data_view.biological_unit_manifest_sha256
        == manifest_artifact.sha256
    )
    assert profile_v2.data_views["biological_unit_lineage"]["state"] == "declared"
    assert "biological_unit_lineage_is_declared_not_reviewed" in profile_v2.warnings
    assert {
        item.observation_id for item in assignment.assignments
    } == {f"cell-{index}" for index in range(6)}
    assert not biological_unit_assignment_reasons(
        manifest=manifest,
        artifact=assignment,
        artifact_sha256=assignment_artifact.sha256,
    )


@pytest.mark.parametrize(
    ("roles", "override"),
    [
        (("biological_unit_assignment", "biological_unit_manifest"), {}),
        (("qc_readiness_profile_v2", "biological_unit_assignment"), {}),
        (("qc_readiness_profile_v2", "biological_unit_manifest"), {}),
        (("qc_readiness_profile_v2", "qc_readiness_profile_v2"), {}),
        (("qc_readiness_profile_v2",), {"schema_ref": "bridge://schemas/wrong/v0.1"}),
        (("qc_readiness_profile_v2",), {"object_version": "9.9.9"}),
    ],
)
def test_structured_output_index_rejects_incoherent_roles_or_contracts(
    roles: tuple[str, ...],
    override: dict[str, str],
) -> None:
    role_contracts = {
        "qc_readiness_profile_v2": (
            "bridge://schemas/qc-readiness-profile/v0.2",
            "0.2.0",
        ),
        "biological_unit_assignment": (
            "bridge://schemas/biological-unit-assignment/v0.1",
            "0.1.0",
        ),
        "biological_unit_manifest": (
            "bridge://schemas/biological-unit-manifest/v0.1",
            "0.1.0",
        ),
    }
    payload = {
        "object_version": "0.1.0",
        "schema_ref": P001_STRUCTURED_OUTPUT_INDEX_SCHEMA_REF,
        "run_id": "run-test",
        "outputs": [
            {
                "role": role,
                "relative_filename": f"output-{index}.json",
                "artifact_id": f"artifact:test:{index}",
                "sha256": "0" * 64,
                "media_type": "application/json",
                "schema_ref": role_contracts[role][0],
                "object_version": role_contracts[role][1],
            }
            for index, role in enumerate(roles)
        ],
    }
    payload["outputs"][-1].update(override)

    with pytest.raises(ValueError):
        P001StructuredOutputIndex.model_validate(payload)
    schema = load_schema(P001_STRUCTURED_OUTPUT_INDEX_SCHEMA_REF)
    assert list(Draft202012Validator(schema).iter_errors(payload))


@pytest.mark.parametrize(
    ("case", "expected_reason"),
    [
        ("missing_metadata", "biological_unit_lineage_metadata_missing"),
        ("missing_column", "biological_unit_lineage_column_missing"),
        ("source_mismatch", "biological_unit_lineage_source_mismatch"),
        ("capture_as_independence", "biological_unit_lineage_metadata_invalid"),
        ("source_ref_unmapped", "biological_unit_lineage_metadata_invalid"),
        ("analysis_ref_unmapped", "biological_unit_lineage_metadata_invalid"),
        ("independence_ref_unmapped", "biological_unit_lineage_metadata_invalid"),
    ],
)
def test_lineage_metadata_failure_is_explicit_without_blocking_v1(
    tmp_path: Path,
    case: str,
    expected_reason: str,
) -> None:
    input_path = _write_h5ad(tmp_path / f"counts-{case}.h5ad", counts=True)
    request = _request(tmp_path, input_path, semantics="raw_counts")
    metadata = dict(request.assets[0].metadata)
    if case != "missing_metadata":
        declaration = _lineage_metadata()
        if case == "missing_column":
            declaration["observation_ref_columns"]["preparation"] = "missing_preparation_ref"
        elif case == "source_mismatch":
            declaration["observation_ref_columns"] = {}
            declaration["constant_unit_refs"] = {
                "capture": _versioned_ref("capture:capture-a@1.0.0"),
                "preparation": _versioned_ref("preparation:other@1.0.0"),
                "donor": _versioned_ref("donor:donor-a@1.0.0"),
            }
        elif case == "source_ref_unmapped":
            declaration["source_unit_kind"] = "sample"
            declaration["source_unit_ref"] = _versioned_ref("sample:sample-a@1.0.0")
            declaration["observation_ref_columns"] = {}
            declaration["constant_unit_refs"] = {
                "capture": _versioned_ref("capture:capture-a@1.0.0"),
                "preparation": _versioned_ref("preparation:product-a@1.0.0"),
                "donor": _versioned_ref("donor:donor-a@1.0.0"),
            }
        elif case == "analysis_ref_unmapped":
            declaration["source_unit_kind"] = "sample"
            declaration["source_unit_ref"] = _versioned_ref("sample:sample-a@1.0.0")
            declaration["observation_ref_columns"] = {}
            declaration["constant_unit_refs"] = {
                "capture": _versioned_ref("capture:capture-a@1.0.0"),
                "sample": _versioned_ref("sample:sample-a@1.0.0"),
                "donor": _versioned_ref("donor:donor-a@1.0.0"),
            }
        elif case == "independence_ref_unmapped":
            declaration["observation_ref_columns"] = {}
            declaration["constant_unit_refs"] = {
                "capture": _versioned_ref("capture:capture-a@1.0.0"),
                "preparation": _versioned_ref("preparation:product-a@1.0.0"),
            }
        elif case == "capture_as_independence":
            declaration["independence_group_kind"] = "capture"
            declaration["observation_ref_columns"] = {}
            declaration["constant_unit_refs"] = {
                "preparation": _versioned_ref("preparation:product-a@1.0.0"),
                "capture": _versioned_ref("capture:capture-a@1.0.0"),
            }
        metadata["biological_unit_lineage"] = declaration
    request = request.model_copy(
        update={"assets": [request.assets[0].model_copy(update={"metadata": metadata})]}
    )

    run = ToolRegistry.load_default().run(request)

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert "selected_data_view" not in run.result
    assert not {
        "biological_unit_assignment",
        "biological_unit_manifest",
    } & {item.kind for item in run.artifacts}
    _, payload = _artifact_json(run, "qc_profile_v2")
    profile_v2 = QCReadinessProfileV2.model_validate(payload)
    assert profile_v2.selected_data_view is not None
    assert profile_v2.selected_data_view.biological_unit_manifest_ref is None
    assert profile_v2.data_views["biological_unit_lineage"] == {
        "state": "unavailable",
        "reason_codes": [expected_reason],
    }
    assert expected_reason in profile_v2.missing_inputs
    assert all(not item.startswith("biological_unit_lineage") for item in run.warnings)


def test_identical_request_produces_stable_artifact_hashes(tmp_path: Path) -> None:
    input_path = _write_h5ad(tmp_path / "counts.h5ad", counts=True)
    request = _request(
        tmp_path,
        input_path,
        semantics="raw_counts",
        spec="QC-scRNA-candidate-v0.1",
    )
    declaration = _lineage_metadata()
    declaration["observation_ref_columns"] = {}
    declaration["constant_unit_refs"] = {
        "capture": _versioned_ref("capture:capture-a@1.0.0"),
        "preparation": _versioned_ref("preparation:product-a@1.0.0"),
        "donor": _versioned_ref("donor:donor-a@1.0.0"),
    }
    request = request.model_copy(
        update={
            "assets": [
                request.assets[0].model_copy(
                    update={"metadata": {**request.assets[0].metadata, "biological_unit_lineage": declaration}}
                )
            ]
        }
    )

    first = ToolRegistry.load_default().run(request)
    second = ToolRegistry.load_default().run(request)

    assert first.run_id == second.run_id
    first_hashes = {(item.kind, item.path.name): item.sha256 for item in first.artifacts}
    second_hashes = {(item.kind, item.path.name): item.sha256 for item in second.artifacts}
    assert first_hashes == second_hashes


def test_scientific_request_metadata_changes_run_identity(tmp_path: Path) -> None:
    input_path = _write_h5ad(tmp_path / "counts.h5ad", counts=True)
    first_request = _request(tmp_path, input_path, semantics="raw_counts")
    second_request = first_request.model_copy(
        update={
            "assets": [
                first_request.assets[0].model_copy(
                    update={"metadata": {**first_request.assets[0].metadata, "chemistry": "3-prime-v3"}}
                )
            ]
        }
    )

    first = ToolRegistry.load_default().run(first_request)
    second = ToolRegistry.load_default().run(second_request)

    assert first.run_id != second.run_id


def test_missing_capture_id_degrades_doublet_without_failing_basic_qc(tmp_path: Path) -> None:
    input_path = _write_h5ad(tmp_path / "counts.h5ad", counts=True)
    request = _request(tmp_path, input_path, semantics="raw_counts")
    request = request.model_copy(
        update={
            "assets": [request.assets[0].model_copy(update={"metadata": {"sample_id_column": "sample_id"}})]
        }
    )

    run = ToolRegistry.load_default().run(request)

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result["doublet_assessment"]["state"] == "not_assessed"
    assert "capture_id_not_declared" in run.result["warnings"]


def test_invalid_count_semantics_returns_structured_blocked_run(tmp_path: Path) -> None:
    input_path = _write_h5ad(tmp_path / "not-counts.h5ad", counts=False)

    run = ToolRegistry.load_default().run(
        _request(tmp_path, input_path, semantics="raw_counts")
    )

    assert run.execution_state is ExecutionState.FAILED
    assert run.measurements == []
    assert "raw_counts_must_be_nonnegative_integers" in run.reason_codes


def test_duplicate_gene_ids_return_structured_failure(tmp_path: Path) -> None:
    input_path = _write_h5ad(tmp_path / "duplicates.h5ad", counts=True)
    adata = ad.read_h5ad(input_path)
    adata.var_names = ["MT-ND1", "SOX2", "SOX2", "LMX1A", "FOXA2", "TUBB3"]
    adata.write_h5ad(input_path)

    run = ToolRegistry.load_default().run(_request(tmp_path, input_path, semantics="raw_counts"))

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["duplicate_gene_ids"]


def test_missing_mitochondrial_gene_coverage_is_unavailable_not_zero(tmp_path: Path) -> None:
    input_path = _write_h5ad(tmp_path / "no-mito.h5ad", counts=True)
    adata = ad.read_h5ad(input_path)
    adata.var_names = ["ACTB", "RPS3", "SOX2", "LMX1A", "FOXA2", "TUBB3"]
    adata.write_h5ad(input_path)

    run = ToolRegistry.load_default().run(
        _request(
            tmp_path,
            input_path,
            semantics="raw_counts",
            spec="QC-scRNA-candidate-v0.1",
        )
    )

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result["cell_qc"]["gene_set_coverage"]["mitochondrial_genes"] == 0
    assert run.result["data_views"]["eligible_cells_view"] == {
        "state": "unavailable",
        "reason": "required_qc_gene_set_unavailable",
    }
    mitochondrial = next(
        measurement for measurement in run.measurements if measurement.metric_name == "mitochondrial_fraction_median"
    )
    assert mitochondrial.raw_value is None
    assert mitochondrial.evidence_state.value == "unavailable"
    profile_path = next(item.path for item in run.artifacts if item.kind == "qc_profile")
    payload = profile_path.read_text(encoding="utf-8")
    assert "NaN" not in payload
    assert json.loads(payload)["cell_qc"]["per_group"][0]["mitochondrial_fraction_median"] is None


def test_declared_gene_symbol_column_drives_qc_gene_sets(tmp_path: Path) -> None:
    input_path = _write_h5ad(tmp_path / "gene-symbol-column.h5ad", counts=True)
    adata = ad.read_h5ad(input_path)
    adata.var["gene_symbol"] = ["MT-ND1", "RPS3", "SOX2", "LMX1A", "FOXA2", "TUBB3"]
    adata.var_names = [f"ENSG{index:05d}" for index in range(6)]
    adata.write_h5ad(input_path)
    request = _request(
        tmp_path,
        input_path,
        semantics="raw_counts",
        spec="QC-scRNA-candidate-v0.1",
    )
    request = request.model_copy(
        update={
            "assets": [
                request.assets[0].model_copy(
                    update={
                        "metadata": {
                            **request.assets[0].metadata,
                            "gene_symbol_column": "gene_symbol",
                        }
                    }
                )
            ]
        }
    )

    run = ToolRegistry.load_default().run(request)

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result["matrix_provenance"]["gene_identifier_source"] == "var/gene_symbol"
    assert run.result["cell_qc"]["gene_set_coverage"]["mitochondrial_genes"] == 1
    assert run.result["data_views"]["eligible_cells_view"]["state"] == "candidate"


def test_10x_mtx_is_supported_as_count_ready(tmp_path: Path) -> None:
    tenx = tmp_path / "tenx"
    tenx.mkdir()
    matrix = sparse.coo_matrix(np.array([[1, 0, 2], [0, 3, 1], [4, 0, 1]], dtype=np.int64))
    mmwrite(tenx / "matrix.mtx", matrix)
    (tenx / "features.tsv").write_text("g1\tMT-ND1\tGene Expression\ng2\tSOX2\tGene Expression\ng3\tLMX1A\tGene Expression\n", encoding="utf-8")
    (tenx / "barcodes.tsv").write_text("cell-1\ncell-2\ncell-3\n", encoding="utf-8")
    request = ToolRequest(
        request_id="qc-10x",
        tool_id="P0-01",
        output_dir=(tmp_path / "results").resolve(),
        assets=[
            InputAsset(
                asset_id="asset-10x",
                path=tenx.resolve(),
                format="10x_mtx",
                input_level="count_ready",
                matrix_semantics="raw_counts",
                assay="scRNA-seq",
                metadata={"capture_id": "capture-1", "sample_id": "sample-1"},
            )
        ],
    )

    run = ToolRegistry.load_default().run(request)

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result["input_level"] == "count_ready"
    assert run.result["schema_integrity"]["n_cells"] == 3
    assert run.result["schema_integrity"]["n_genes"] == 3


def test_10x_h5_is_supported_as_count_ready(tmp_path: Path) -> None:
    h5_path = tmp_path / "filtered_feature_bc_matrix.h5"
    genes_by_cells = sparse.csc_matrix(
        np.array([[1, 0, 2], [0, 3, 1], [4, 0, 1]], dtype=np.int64)
    )
    with h5py.File(h5_path, "w") as handle:
        matrix_group = handle.create_group("matrix")
        matrix_group.create_dataset("data", data=genes_by_cells.data)
        matrix_group.create_dataset("indices", data=genes_by_cells.indices)
        matrix_group.create_dataset("indptr", data=genes_by_cells.indptr)
        matrix_group.create_dataset("shape", data=genes_by_cells.shape)
        matrix_group.create_dataset("barcodes", data=np.array([b"cell-1", b"cell-2", b"cell-3"]))
        feature_group = matrix_group.create_group("features")
        feature_group.create_dataset("id", data=np.array([b"ENSG1", b"ENSG2", b"ENSG3"]))
        feature_group.create_dataset("name", data=np.array([b"MT-ND1", b"SOX2", b"LMX1A"]))
        feature_group.create_dataset("feature_type", data=np.array([b"Gene Expression"] * 3))
        feature_group.create_dataset("genome", data=np.array([b"GRCh38"] * 3))
        feature_group.create_dataset("_all_tag_keys", data=np.array([b"genome"]))
    request = ToolRequest(
        request_id="qc-10x-h5",
        tool_id="P0-01",
        output_dir=(tmp_path / "results").resolve(),
        assets=[
            InputAsset(
                asset_id="asset-10x-h5",
                path=h5_path.resolve(),
                format="10x_h5",
                input_level="count_ready",
                matrix_semantics="raw_counts",
                assay="scRNA-seq",
                metadata={"capture_id": "capture-1", "sample_id": "sample-1"},
            )
        ],
    )

    run = ToolRegistry.load_default().run(request)

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result["schema_integrity"]["n_cells"] == 3
    assert run.result["schema_integrity"]["n_genes"] == 3


def test_droplet_ready_audits_contract_without_treating_barcodes_as_cells(tmp_path: Path) -> None:
    tenx = tmp_path / "raw-droplets"
    tenx.mkdir()
    matrix = sparse.coo_matrix(np.array([[1, 0, 2], [0, 3, 1], [4, 0, 1]], dtype=np.int64))
    mmwrite(tenx / "matrix.mtx", matrix)
    (tenx / "features.tsv").write_text(
        "g1\tMT-ND1\tGene Expression\ng2\tSOX2\tGene Expression\ng3\tLMX1A\tGene Expression\n",
        encoding="utf-8",
    )
    (tenx / "barcodes.tsv").write_text("drop-1\ndrop-2\ndrop-3\n", encoding="utf-8")
    request = ToolRequest(
        request_id="qc-droplet",
        tool_id="P0-01",
        output_dir=(tmp_path / "results").resolve(),
        assets=[
            InputAsset(
                asset_id="asset-droplet",
                path=tenx.resolve(),
                format="10x_mtx",
                input_level="droplet_ready",
                matrix_semantics="raw_counts",
                assay="scRNA-seq",
                metadata={"capture_id": "capture-1", "sample_id": "sample-1"},
            )
        ],
    )

    run = ToolRegistry.load_default().run(request)

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result["input_level"] == "droplet_ready"
    assert run.result["schema_integrity"]["n_cells"] is None
    assert run.result["schema_integrity"]["n_barcodes"] == 3
    assert run.result["cell_qc"]["count_metrics_state"] == "not_assessed"
    assert run.result["cell_calling_assessment"]["state"] == "not_assessed"
    assert run.result["ambient_assessment"]["state"] == "not_assessed"
    assert run.result["data_views"]["all_cells_view"]["state"] == "unavailable"
    assert run.result["data_views"]["all_droplets_view"]["state"] == "available"
    assert run.result["module_eligibility"]["cell_calling"] == "not_implemented"
    assert run.result["module_eligibility"]["ambient_rna"] == "not_implemented"
    assert {measurement.metric_name for measurement in run.measurements} == {"n_barcodes", "n_genes"}
    _, v2_payload = _artifact_json(run, "qc_profile_v2")
    profile_v2 = QCReadinessProfileV2.model_validate(v2_payload)
    assert profile_v2.selected_data_view is None
    assert profile_v2.data_views["biological_unit_lineage"] == {
        "state": "unavailable",
        "reason_codes": ["biological_unit_lineage_unavailable:droplet_observations_are_not_cells"],
    }


def test_droplet_ready_rejects_cell_level_measurement_spec(tmp_path: Path) -> None:
    tenx = tmp_path / "raw-droplets"
    tenx.mkdir()
    mmwrite(tenx / "matrix.mtx", sparse.coo_matrix(np.eye(3, dtype=np.int64)))
    (tenx / "features.tsv").write_text(
        "g1\tMT-ND1\tGene Expression\ng2\tSOX2\tGene Expression\ng3\tLMX1A\tGene Expression\n",
        encoding="utf-8",
    )
    (tenx / "barcodes.tsv").write_text("drop-1\ndrop-2\ndrop-3\n", encoding="utf-8")
    request = ToolRequest(
        request_id="qc-droplet-spec",
        tool_id="P0-01",
        output_dir=(tmp_path / "results").resolve(),
        assets=[
            InputAsset(
                asset_id="asset-droplet",
                path=tenx.resolve(),
                format="10x_mtx",
                input_level="droplet_ready",
                matrix_semantics="raw_counts",
                assay="scRNA-seq",
                metadata={"capture_id": "capture-1", "sample_id": "sample-1"},
            )
        ],
        measurement_spec_ref="QC-scRNA-candidate-v0.1",
    )

    registry = ToolRegistry.load_default()
    eligibility = registry.check_eligibility(request)
    run = registry.run(request)

    assert eligibility.reason_codes == ["measurement_spec_input_level_mismatch"]
    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["measurement_spec_input_level_mismatch"]
    assert not request.output_dir.exists()


def test_output_directory_cannot_be_nested_inside_directory_input(tmp_path: Path) -> None:
    tenx = tmp_path / "tenx"
    tenx.mkdir()
    mmwrite(tenx / "matrix.mtx", sparse.coo_matrix(np.eye(3, dtype=np.int64)))
    (tenx / "features.tsv").write_text(
        "g1\tMT-ND1\tGene Expression\ng2\tSOX2\tGene Expression\ng3\tLMX1A\tGene Expression\n",
        encoding="utf-8",
    )
    (tenx / "barcodes.tsv").write_text("cell-1\ncell-2\ncell-3\n", encoding="utf-8")
    before = _sha256_tree(tenx)
    output_dir = tenx / "results"
    request = ToolRequest(
        request_id="qc-overlap",
        tool_id="P0-01",
        output_dir=output_dir.resolve(),
        assets=[
            InputAsset(
                asset_id="asset-10x",
                path=tenx.resolve(),
                format="10x_mtx",
                input_level="count_ready",
                matrix_semantics="raw_counts",
                assay="scRNA-seq",
                metadata={"capture_id": "capture-1", "sample_id": "sample-1"},
            )
        ],
    )

    registry = ToolRegistry.load_default()
    eligibility = registry.check_eligibility(request)
    run = registry.run(request)

    assert eligibility.reason_codes == ["output_dir_overlaps_input_asset"]
    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["output_dir_overlaps_input_asset"]
    assert not output_dir.exists()
    assert _sha256_tree(tenx) == before


@pytest.mark.parametrize("target_kind", ["file", "symlink"])
def test_unusable_output_path_returns_typed_failure_without_mutation(
    tmp_path: Path, target_kind: str
) -> None:
    input_path = _write_h5ad(tmp_path / "counts.h5ad", counts=True)
    output_path = tmp_path / "occupied-output"
    if target_kind == "file":
        output_path.write_text("preserve-me", encoding="utf-8")
        expected = output_path.read_bytes()
    else:
        target = tmp_path / "symlink-target"
        target.mkdir()
        output_path.symlink_to(target, target_is_directory=True)
        expected = output_path.readlink()
    request = _request(
        tmp_path,
        input_path,
        semantics="raw_counts",
    ).model_copy(update={"output_dir": output_path})

    registry = ToolRegistry.load_default()
    eligibility = registry.check_eligibility(request)
    run = registry.run(request)

    assert eligibility.reason_codes == ["output_path_invalid"]
    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["output_path_invalid"]
    if target_kind == "file":
        assert output_path.read_bytes() == expected
    else:
        assert output_path.is_symlink()
        assert output_path.readlink() == expected
        assert list((tmp_path / "symlink-target").iterdir()) == []


def test_scrna_measurement_spec_cannot_be_used_for_snrna(tmp_path: Path) -> None:
    input_path = _write_h5ad(tmp_path / "nuclei.h5ad", counts=True, assay="snRNA-seq")

    run = ToolRegistry.load_default().run(
        _request(
            tmp_path,
            input_path,
            semantics="raw_counts",
            assay="snRNA-seq",
            spec="QC-scRNA-candidate-v0.1",
        )
    )

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["measurement_spec_assay_mismatch"]


def test_snrna_uses_nucleus_units_and_assay_specific_feature_policy(tmp_path: Path) -> None:
    input_path = _write_h5ad(tmp_path / "nuclei.h5ad", counts=True, assay="snRNA-seq")

    run = ToolRegistry.load_default().run(
        _request(
            tmp_path,
            input_path,
            semantics="raw_counts",
            assay="snRNA-seq",
            spec="QC-snRNA-candidate-v0.1",
        )
    )

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert {item.metric_name for item in run.measurements} >= {"n_nuclei", "n_genes"}
    assert run.result["schema_integrity"]["observation_kind"] == "nuclei"
    assert run.result["schema_integrity"]["n_cells"] is None
    assert run.result["schema_integrity"]["n_nuclei"] == 6
    assert run.result["data_views"]["all_cells_view"]["observation_unit"] == "nuclei"
    assert run.result["cell_qc"]["feature_set_policy_id"] == "QC-feature-set-snRNA-human-symbol-v0.1"
    assert "not directly comparable" in run.result["cell_qc"]["mitochondrial_interpretation"]
    assert all(item.denominator == "declared nuclei" for item in run.visualizations)


@pytest.mark.parametrize("missing_value", [None, "", "NA", "unknown"])
def test_incomplete_capture_values_never_form_a_pooled_qc_group(
    tmp_path: Path,
    missing_value: object,
) -> None:
    input_path = _write_h5ad(tmp_path / "incomplete-capture.h5ad", counts=True)
    adata = ad.read_h5ad(input_path)
    adata.obs["capture_id"] = adata.obs["capture_id"].astype(object)
    adata.obs.iloc[0, adata.obs.columns.get_loc("capture_id")] = missing_value
    adata.obs["capture_ref"] = "capture:capture-a@1.0.0"
    adata.obs["preparation_ref"] = "preparation:product-a@1.0.0"
    adata.obs["donor_ref"] = "donor:donor-a@1.0.0"
    adata.write_h5ad(input_path)

    run = ToolRegistry.load_default().run(
        _with_lineage(
            _request(
                tmp_path,
                input_path,
                semantics="raw_counts",
                spec="QC-scRNA-candidate-v0.1",
            ),
            _lineage_metadata(),
        )
    )

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result["metadata_completeness"]["fields"]["capture_id"] is False
    assert run.result["metadata_completeness"]["complete"] is False
    assert run.result["cell_qc"]["per_group"] == []
    assert run.result["doublet_assessment"] == {
        "state": "not_assessed",
        "reason": "capture_id_incomplete",
    }
    assert "capture_id_incomplete" in run.result["warnings"]
    _, profile_payload = _artifact_json(run, "qc_profile_v2")
    assert profile_payload["data_views"]["biological_unit_lineage"] == {
        "state": "unavailable",
        "reason_codes": ["biological_unit_lineage_capture_partition_unavailable"],
    }
    _, visualization_payload = _artifact_json(run, "qc_visualization_data")
    visualization_profile = QCVisualizationDataProfile.model_validate(
        visualization_payload
    )
    distribution_records = [
        record
        for record in visualization_profile.records
        if record.component_ref == "bridge.qc.overview@0.2.0"
    ]
    assert len(distribution_records) == 1
    assert distribution_records[0].capture_id is None
    assert distribution_records[0].missing_reason_codes == ["capture_partition_unavailable"]


def test_multiple_complete_captures_are_summarized_separately(tmp_path: Path) -> None:
    input_path = _write_h5ad(tmp_path / "mixed-captures.h5ad", counts=True)
    adata = ad.read_h5ad(input_path)
    adata.obs["capture_id"] = ["capture-a"] * 3 + ["capture-b"] * 3
    adata.write_h5ad(input_path)

    run = ToolRegistry.load_default().run(
        _request(tmp_path, input_path, semantics="raw_counts")
    )

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result["metadata_completeness"]["complete"] is True
    assert {item["group"] for item in run.result["cell_qc"]["per_group"]} == {
        "capture-a",
        "capture-b",
    }


def test_zero_total_count_fractions_are_undefined_and_ineligible(tmp_path: Path) -> None:
    input_path = _write_h5ad(tmp_path / "zero-count.h5ad", counts=True)
    adata = ad.read_h5ad(input_path)
    matrix = adata.X.tolil()
    matrix[0, :] = 0
    adata.X = matrix.tocsr()
    adata.write_h5ad(input_path)

    run = ToolRegistry.load_default().run(
        _request(
            tmp_path,
            input_path,
            semantics="raw_counts",
            spec="QC-scRNA-candidate-v0.1",
        )
    )

    assert run.execution_state is ExecutionState.SUCCEEDED
    metrics_path = next(item.path for item in run.artifacts if item.kind == "qc_metrics")
    metrics = pd.read_parquet(metrics_path)
    for column in (
        "mitochondrial_fraction",
        "ribosomal_fraction",
        "top_20_gene_fraction",
    ):
        assert pd.isna(metrics.loc["cell-0", column])
        measurement = next(
            item for item in run.measurements if item.metric_name == f"{column}_median"
        )
        assert measurement.denominator == 5
        assert measurement.evidence_state.value == "measured"
    candidate_path = next(item.path for item in run.artifacts if item.kind == "derived_h5ad")
    candidate = ad.read_h5ad(candidate_path)
    assert bool(candidate.obs.loc["cell-0", "flag_zero_total_counts"])
    assert not bool(candidate.obs.loc["cell-0", "bridge_qc_candidate_eligible"])


def test_10x_mtx_excludes_antibody_and_guide_features_from_gene_qc(
    tmp_path: Path,
) -> None:
    tenx = tmp_path / "mixed-feature-tenx"
    tenx.mkdir()
    genes_by_cells = sparse.coo_matrix(
        np.array(
            [
                [1, 2, 3],
                [1000, 1000, 1000],
                [2000, 2000, 2000],
            ],
            dtype=np.int64,
        )
    )
    mmwrite(tenx / "matrix.mtx", genes_by_cells)
    (tenx / "features.tsv").write_text(
        "g1\tMT-ND1\tGene Expression\n"
        "adt1\tCD56\tAntibody Capture\n"
        "guide1\tGUIDE-A\tCRISPR Guide Capture\n",
        encoding="utf-8",
    )
    (tenx / "barcodes.tsv").write_text("cell-1\ncell-2\ncell-3\n", encoding="utf-8")
    request = _tenx_request(tmp_path, tenx, label="mixed-features")

    run = ToolRegistry.load_default().run(request)

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result["schema_integrity"]["n_genes"] == 1
    assert run.result["matrix_provenance"] | {
        "input_feature_count": 3,
        "selected_gene_expression_feature_count": 1,
        "feature_selection_policy": "gene_expression_only",
    } == run.result["matrix_provenance"]
    metrics = pd.read_parquet(
        next(item.path for item in run.artifacts if item.kind == "qc_metrics")
    )
    assert metrics["total_counts"].tolist() == [1.0, 2.0, 3.0]


@pytest.mark.parametrize(
    ("feature_rows", "expected_reason"),
    [
        ("g1\n", "10x_feature_columns_incomplete"),
        ("g1\tMT-ND1\t\n", "10x_feature_type_ambiguous"),
        ("adt1\tCD56\tAntibody Capture\n", "10x_gene_expression_features_unavailable"),
    ],
)
def test_10x_mtx_feature_type_failures_are_explicit(
    tmp_path: Path,
    feature_rows: str,
    expected_reason: str,
) -> None:
    tenx = tmp_path / "invalid-feature-tenx"
    tenx.mkdir()
    mmwrite(tenx / "matrix.mtx", sparse.coo_matrix(np.array([[1, 2, 3]])))
    (tenx / "features.tsv").write_text(feature_rows, encoding="utf-8")
    (tenx / "barcodes.tsv").write_text("cell-1\ncell-2\ncell-3\n", encoding="utf-8")
    request = _tenx_request(tmp_path, tenx, label="invalid-features")

    run = ToolRegistry.load_default().run(request)

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == [expected_reason]
    assert not request.output_dir.exists()


def test_legacy_two_column_10x_features_are_explicitly_assumed_gene_expression(
    tmp_path: Path,
) -> None:
    tenx = tmp_path / "legacy-two-column-tenx"
    tenx.mkdir()
    mmwrite(tenx / "matrix.mtx", sparse.coo_matrix(np.array([[1, 2, 3]])))
    (tenx / "features.tsv").write_text("g1\tMT-ND1\n", encoding="utf-8")
    (tenx / "barcodes.tsv").write_text("cell-1\ncell-2\ncell-3\n", encoding="utf-8")

    run = ToolRegistry.load_default().run(
        _tenx_request(tmp_path, tenx, label="legacy-two-column-features")
    )

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result["matrix_provenance"] | {
        "input_feature_count": 1,
        "selected_gene_expression_feature_count": 1,
        "feature_selection_policy": "all_features_assumed_gene_expression",
    } == run.result["matrix_provenance"]
    warning = "legacy_two_column_features_assumed_gene_expression"
    assert warning in run.warnings
    assert warning in run.result["warnings"]


def test_all_zero_count_fraction_measurements_are_unavailable(tmp_path: Path) -> None:
    input_path = _write_h5ad(tmp_path / "all-zero-counts.h5ad", counts=True)
    adata = ad.read_h5ad(input_path)
    adata.X = sparse.csr_matrix(adata.shape, dtype=np.int64)
    adata.write_h5ad(input_path)

    run = ToolRegistry.load_default().run(
        _request(
            tmp_path,
            input_path,
            semantics="raw_counts",
            spec="QC-scRNA-candidate-v0.1",
        )
    )

    assert run.execution_state is ExecutionState.SUCCEEDED
    for column in (
        "mitochondrial_fraction",
        "ribosomal_fraction",
        "top_20_gene_fraction",
    ):
        measurement = next(
            item for item in run.measurements if item.metric_name == f"{column}_median"
        )
        assert measurement.raw_value is None
        assert measurement.denominator is None
        assert measurement.evidence_state.value == "unavailable"
    candidate = ad.read_h5ad(
        next(item.path for item in run.artifacts if item.kind == "derived_h5ad")
    )
    assert candidate.obs["flag_zero_total_counts"].all()
    assert not candidate.obs["bridge_qc_candidate_eligible"].any()


def test_one_preparation_can_bind_multiple_captures_under_one_independence_contract(
    tmp_path: Path,
) -> None:
    input_path = _write_h5ad(tmp_path / "multi-capture-lineage.h5ad", counts=True)
    adata = ad.read_h5ad(input_path)
    adata.obs["capture_ref"] = ["capture:capture-a@1.0.0"] * 3 + [
        "capture:capture-b@1.0.0"
    ] * 3
    adata.obs["capture_id"] = ["legacy-a"] * 3 + ["legacy-b"] * 3
    adata.obs["preparation_ref"] = "preparation:product-a@1.0.0"
    adata.obs["donor_ref"] = "donor:donor-a@1.0.0"
    adata.write_h5ad(input_path)
    request = _with_lineage(
        _request(tmp_path, input_path, semantics="raw_counts"),
        _lineage_metadata(),
    )

    run = ToolRegistry.load_default().run(request)

    assert run.execution_state is ExecutionState.SUCCEEDED
    _, assignment_payload = _artifact_json(run, "biological_unit_assignment")
    _, manifest_payload = _artifact_json(run, "biological_unit_manifest")
    assignment = BiologicalUnitAssignmentArtifact.model_validate(assignment_payload)
    manifest = BiologicalUnitManifest.model_validate(manifest_payload)
    assignment_artifact = next(
        item for item in run.artifacts if item.kind == "biological_unit_assignment"
    )
    assert len(manifest.unit_bindings) == 2
    assert {item.analysis_unit_ref.ref for item in manifest.unit_bindings} == {
        "preparation:product-a@1.0.0"
    }
    assert {item.capture_ref.ref for item in manifest.unit_bindings} == {
        "capture:capture-a@1.0.0",
        "capture:capture-b@1.0.0",
    }
    assert not biological_unit_assignment_reasons(
        manifest=manifest,
        artifact=assignment,
        artifact_sha256=assignment_artifact.sha256,
    )


@pytest.mark.parametrize("mismatch_kind", ["split", "merge"])
def test_typed_and_qc_capture_partitions_must_be_equivalent(
    tmp_path: Path,
    mismatch_kind: str,
) -> None:
    input_path = _write_h5ad(tmp_path / f"capture-{mismatch_kind}.h5ad", counts=True)
    adata = ad.read_h5ad(input_path)
    two_qc_groups = ["legacy-a"] * 3 + ["legacy-b"] * 3
    two_typed_groups = ["capture:a@1.0.0"] * 3 + ["capture:b@1.0.0"] * 3
    adata.obs["capture_id"] = ["legacy-a"] * 6 if mismatch_kind == "split" else two_qc_groups
    adata.obs["capture_ref"] = two_typed_groups if mismatch_kind == "split" else "capture:a@1.0.0"
    adata.obs["preparation_ref"] = "preparation:product-a@1.0.0"
    adata.obs["donor_ref"] = "donor:donor-a@1.0.0"
    adata.write_h5ad(input_path)
    request = _with_lineage(
        _request(tmp_path, input_path, semantics="raw_counts"),
        _lineage_metadata(),
    )

    run = ToolRegistry.load_default().run(request)

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result["cell_qc"]["count_metrics_state"] == "measured"
    assert not {"biological_unit_assignment", "biological_unit_manifest"} & {
        item.kind for item in run.artifacts
    }
    _, profile_payload = _artifact_json(run, "qc_profile_v2")
    assert profile_payload["data_views"]["biological_unit_lineage"] == {
        "state": "unavailable",
        "reason_codes": ["biological_unit_lineage_capture_partition_mismatch"],
    }


def test_count_ready_lineage_without_versioned_capture_mapping_is_unavailable(
    tmp_path: Path,
) -> None:
    input_path = _write_h5ad(tmp_path / "missing-lineage-capture.h5ad", counts=True)
    declaration = _lineage_metadata()
    declaration["observation_ref_columns"].pop("capture")
    adata = ad.read_h5ad(input_path)
    adata.obs["preparation_ref"] = "preparation:product-a@1.0.0"
    adata.obs["donor_ref"] = "donor:donor-a@1.0.0"
    adata.write_h5ad(input_path)
    request = _with_lineage(
        _request(tmp_path, input_path, semantics="raw_counts"),
        declaration,
    )

    run = ToolRegistry.load_default().run(request)

    assert run.execution_state is ExecutionState.SUCCEEDED
    _, profile_payload = _artifact_json(run, "qc_profile_v2")
    assert profile_payload["data_views"]["biological_unit_lineage"] == {
        "state": "unavailable",
        "reason_codes": ["biological_unit_lineage_capture_reference_required"],
    }


def test_one_capture_mapping_to_conflicting_preparations_fails_lineage_closed(
    tmp_path: Path,
) -> None:
    input_path = _write_h5ad(tmp_path / "pooled-capture.h5ad", counts=True)
    adata = ad.read_h5ad(input_path)
    adata.obs["capture_ref"] = "capture:pooled@1.0.0"
    adata.obs["preparation_ref"] = ["preparation:a@1.0.0"] * 3 + [
        "preparation:b@1.0.0"
    ] * 3
    adata.write_h5ad(input_path)
    declaration = {
        "source_unit_kind": "sample",
        "source_unit_ref": _versioned_ref("sample:source-a@1.0.0"),
        "unit_identity_namespace_ref": _versioned_ref("unit-namespace:study-a@1.0.0"),
        "analysis_unit_kind": "preparation",
        "independence_group_kind": "donor",
        "independence_scope_ref": _versioned_ref("independence-scope:study-a@1.0.0"),
        "observation_ref_columns": {
            "capture": "capture_ref",
            "preparation": "preparation_ref",
        },
        "constant_unit_refs": {
            "sample": _versioned_ref("sample:source-a@1.0.0"),
            "donor": _versioned_ref("donor:donor-a@1.0.0"),
        },
    }
    request = _with_lineage(
        _request(tmp_path, input_path, semantics="raw_counts"),
        declaration,
    )

    run = ToolRegistry.load_default().run(request)

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert not {
        "biological_unit_assignment",
        "biological_unit_manifest",
    } & {item.kind for item in run.artifacts}
    _, profile_payload = _artifact_json(run, "qc_profile_v2")
    assert profile_payload["data_views"]["biological_unit_lineage"] == {
        "state": "unavailable",
        "reason_codes": ["biological_unit_lineage_contract_invalid"],
    }


def test_mutation_during_snapshot_fails_without_partial_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = _write_h5ad(tmp_path / "snapshot-race.h5ad", counts=True)
    request = _request(tmp_path, input_path, semantics="raw_counts")
    original_snapshot = input_qc_executor._snapshot_asset

    def mutate_after_copy(source: Path, destination_root: Path) -> Path:
        snapshot = original_snapshot(source, destination_root)
        adata = ad.read_h5ad(source)
        adata.uns["replacement"] = "during-snapshot"
        adata.write_h5ad(source)
        return snapshot

    monkeypatch.setattr(input_qc_executor, "_snapshot_asset", mutate_after_copy)

    run = ToolRegistry.load_default().run(request)

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["input_asset_modified_during_snapshot"]
    assert not request.output_dir.exists()
    assert not list(tmp_path.glob(".bridge-p0-01-*"))


def test_executor_reads_snapshot_even_if_original_undergoes_aba_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = _write_h5ad(tmp_path / "read-aba.h5ad", counts=True)
    request = _request(tmp_path, input_path, semantics="raw_counts")
    original_reader = input_qc_executor.read_expression_asset

    def read_with_aba(asset: InputAsset):
        assert asset.path != input_path
        original_bytes = input_path.read_bytes()
        input_path.write_bytes(b"temporary replacement")
        input_path.write_bytes(original_bytes)
        return original_reader(asset)

    monkeypatch.setattr(input_qc_executor, "read_expression_asset", read_with_aba)

    run = ToolRegistry.load_default().run(request)

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result["schema_integrity"]["n_observations"] == 6


def test_final_input_recheck_blocks_publication_and_cleans_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = _write_h5ad(tmp_path / "final-race.h5ad", counts=True)
    request = _request(tmp_path, input_path, semantics="raw_counts")
    original_builder = input_qc_executor._build_staged_run

    def build_then_replace(**kwargs):
        run = original_builder(**kwargs)
        adata = ad.read_h5ad(input_path)
        adata.uns["replacement"] = "before-publish"
        adata.write_h5ad(input_path)
        return run

    monkeypatch.setattr(input_qc_executor, "_build_staged_run", build_then_replace)

    run = ToolRegistry.load_default().run(request)

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["input_asset_modified_during_run"]
    assert not request.output_dir.exists()
    assert not list(tmp_path.glob(".bridge-p0-01-*"))


def test_staging_exception_leaves_no_partial_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = _write_h5ad(tmp_path / "staging-failure.h5ad", counts=True)
    request = _request(tmp_path, input_path, semantics="raw_counts")

    def fail_write(*args, **kwargs) -> None:
        raise OSError("injected staging write failure")

    monkeypatch.setattr(input_qc_executor, "_write_json", fail_write)

    run = ToolRegistry.load_default().run(request)

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["artifact_staging_failed"]
    assert not request.output_dir.exists()
    assert not list(tmp_path.glob(".bridge-p0-01-*"))


def test_tampered_existing_bundle_is_preserved_and_never_overwritten(
    tmp_path: Path,
) -> None:
    input_path = _write_h5ad(tmp_path / "tampered-bundle.h5ad", counts=True)
    request = _request(tmp_path, input_path, semantics="raw_counts")
    first = ToolRegistry.load_default().run(request)
    profile_path = next(item.path for item in first.artifacts if item.kind == "qc_profile")
    profile_path.write_bytes(profile_path.read_bytes() + b"\nTAMPERED\n")
    tampered = profile_path.read_bytes()

    second = ToolRegistry.load_default().run(request)

    assert second.execution_state is ExecutionState.FAILED
    assert second.reason_codes == ["existing_run_bundle_mismatch"]
    assert profile_path.read_bytes() == tampered
    assert not list(tmp_path.glob(".bridge-p0-01-*"))


def test_failed_run_identity_binds_the_full_attempted_request(tmp_path: Path) -> None:
    input_path = _write_h5ad(tmp_path / "failed-identity.h5ad", counts=True)
    first_request = _request(tmp_path, input_path, semantics="raw_counts")
    bad_checksum_asset = first_request.assets[0].model_copy(update={"checksum": "0" * 64})
    first_request = first_request.model_copy(update={"assets": [bad_checksum_asset]})
    second_request = first_request.model_copy(update={"parameters": {"run_scrublet": True}})

    first = ToolRegistry.load_default().run(first_request)
    repeated = ToolRegistry.load_default().run(first_request)
    second = ToolRegistry.load_default().run(second_request)

    assert first.reason_codes == repeated.reason_codes == second.reason_codes == [
        "input_checksum_mismatch"
    ]
    assert first.run_id == repeated.run_id
    assert first.run_id != second.run_id


def test_directory_digest_has_unambiguous_path_and_size_framing(tmp_path: Path) -> None:
    first = tmp_path / "first-tree"
    second = tmp_path / "second-tree"
    first.mkdir()
    second.mkdir()
    (first / "a").write_bytes(b"bc")
    (second / "ab").write_bytes(b"c")

    assert sha256_path(first) != sha256_path(second)


@pytest.mark.parametrize("unsafe_kind", ["symlink", "fifo"])
def test_directory_inputs_reject_symlinks_and_special_files(
    tmp_path: Path,
    unsafe_kind: str,
) -> None:
    tenx = tmp_path / "unsafe-tenx"
    tenx.mkdir()
    mmwrite(tenx / "matrix.mtx", sparse.coo_matrix(np.eye(3, dtype=np.int64)))
    (tenx / "features.tsv").write_text(
        "g1\tMT-ND1\tGene Expression\n"
        "g2\tSOX2\tGene Expression\n"
        "g3\tLMX1A\tGene Expression\n",
        encoding="utf-8",
    )
    (tenx / "barcodes.tsv").write_text("cell-1\ncell-2\ncell-3\n", encoding="utf-8")
    unsafe = tenx / "unsafe-entry"
    if unsafe_kind == "symlink":
        unsafe.symlink_to(tenx / "features.tsv")
    else:
        os.mkfifo(unsafe)
    request = _tenx_request(tmp_path, tenx, label="unsafe-tree")

    run = ToolRegistry.load_default().run(request)

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["input_asset_unsafe_file_type"]
    assert not request.output_dir.exists()
