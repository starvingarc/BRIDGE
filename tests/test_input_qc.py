from __future__ import annotations

import hashlib
import json
from pathlib import Path

import anndata as ad
import h5py
import numpy as np
import pandas as pd
import pytest
from scipy import sparse
from scipy.io import mmwrite

from bridge.toolkit.contracts import ExecutionState, InputAsset, ToolRequest
from bridge.toolkit.registry import ToolRegistry


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
    }
    assert run.visualizations
    assert all(item.evidence_ids for item in run.visualizations)
    assert all(artifact.path.is_file() for artifact in run.artifacts)


def test_identical_request_produces_stable_artifact_hashes(tmp_path: Path) -> None:
    input_path = _write_h5ad(tmp_path / "counts.h5ad", counts=True)
    request = _request(
        tmp_path,
        input_path,
        semantics="raw_counts",
        spec="QC-scRNA-candidate-v0.1",
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


def test_missing_capture_id_fails_the_declared_upload_contract(tmp_path: Path) -> None:
    input_path = _write_h5ad(tmp_path / "counts.h5ad", counts=True)
    request = _request(tmp_path, input_path, semantics="raw_counts")
    request = request.model_copy(
        update={
            "assets": [request.assets[0].model_copy(update={"metadata": {"sample_id_column": "sample_id"}})]
        }
    )

    run = ToolRegistry.load_default().run(request)

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["required_metadata_not_declared"]


def test_explicit_missing_metadata_column_is_not_silently_ignored(
    tmp_path: Path,
) -> None:
    input_path = _write_h5ad(tmp_path / "counts.h5ad", counts=True)
    request = _request(tmp_path, input_path, semantics="raw_counts")
    request = request.model_copy(
        update={
            "assets": [
                request.assets[0].model_copy(
                    update={
                        "metadata": {
                            "sample_id_column": "missing_sample_column",
                            "sample_id": "sample-a",
                            "capture_id_column": "capture_id",
                        }
                    }
                )
            ]
        }
    )

    run = ToolRegistry.load_default().run(request)

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["metadata_column_not_found"]


def test_one_sample_may_have_multiple_preparations(tmp_path: Path) -> None:
    input_path = _write_h5ad(tmp_path / "multiple-preparations.h5ad", counts=True)
    adata = ad.read_h5ad(input_path)
    adata.obs["capture_id"] = ["capture-a"] * 3 + ["capture-b"] * 3
    adata.obs["preparation_id"] = ["preparation-a"] * 3 + ["preparation-b"] * 3
    adata.write_h5ad(input_path)
    request = _request(tmp_path, input_path, semantics="raw_counts")
    request = request.model_copy(
        update={
            "assets": [
                request.assets[0].model_copy(
                    update={
                        "metadata": {
                            **request.assets[0].metadata,
                            "preparation_id_column": "preparation_id",
                        }
                    }
                )
            ]
        }
    )

    run = ToolRegistry.load_default().run(request)

    assert run.execution_state is ExecutionState.SUCCEEDED
    assert run.result["metadata_completeness"]["hierarchy_state"] == "validated"


def test_one_preparation_cannot_map_to_multiple_samples(tmp_path: Path) -> None:
    input_path = _write_h5ad(tmp_path / "conflicting-preparation.h5ad", counts=True)
    adata = ad.read_h5ad(input_path)
    adata.obs["sample_id"] = ["sample-a"] * 3 + ["sample-b"] * 3
    adata.obs["capture_id"] = ["capture-a"] * 3 + ["capture-b"] * 3
    adata.obs["preparation_id"] = ["preparation-shared"] * 6
    adata.write_h5ad(input_path)
    request = _request(tmp_path, input_path, semantics="raw_counts")
    request = request.model_copy(
        update={
            "assets": [
                request.assets[0].model_copy(
                    update={
                        "metadata": {
                            **request.assets[0].metadata,
                            "preparation_id_column": "preparation_id",
                        }
                    }
                )
            ]
        }
    )

    run = ToolRegistry.load_default().run(request)

    assert run.execution_state is ExecutionState.FAILED
    assert run.reason_codes == ["metadata_hierarchy_conflict"]


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
