"""Mapping tests catch forced neural labels, moving PCA origins and lost source binding."""
import json
import numpy as np
import pytest

from quick_atlas_support import RECIPE, reference_data, tree_data


def test_reference_only_transfer_and_non_neural_cells_stay_off_tree():
    from bridge.tool_packages.p0_02_cell_state.quick_atlas import map_counts
    reference = reference_data()
    tree, ids = tree_data()
    query = reference[[3, 35, 67]].copy()
    query.obs_names = ["query-rg", "query-da", "query-vascular"]
    summary, cells = map_counts(query, reference, tree, ids, RECIPE)
    assert cells["label"].tolist() == ["RG_mFP", "Neuron_DA", "Endothelial_Cell"]
    assert cells["tree_node"].tolist() == [0, 1, -1]
    assert summary["n_cells"] == 3 and summary["n_tree_cells"] == 2
    assert summary["mapped_cells"] == [[-0.8, 0.1, 0.0, 0], [0.8, 0.3, 0.1, 1]]
    assert summary["tree_position"] == {"RG_mFP": 1 / 3, "Neuron_DA": 1 / 3}
    assert summary["target_fraction"] is None
    assert all(x["value"] is None for x in summary["chain"])
    assert summary["scientific_status"] == "candidate"
    assert summary["ood_status"] == "not_calibrated"
    assert cells.loc["query-rg", "reference_week"] == 7
    assert cells.loc["query-da", "reference_week"] == 20


def test_shared_genes_order_and_query_composition_do_not_move_projection():
    from bridge.tool_packages.p0_02_cell_state.quick_atlas import map_counts
    reference = reference_data()
    tree, ids = tree_data()
    # Missing genes are intersected, not imputed. The same measured features are kept in all calls.
    query = reference[[4, 36, 68], 5:].copy()
    one, one_cells = map_counts(query[[0]], reference, tree, ids, RECIPE)
    both, both_cells = map_counts(query, reference, tree, ids, RECIPE)
    reordered, reordered_cells = map_counts(query[:, ::-1], reference, tree, ids, RECIPE)
    assert one["feature_set_sha256"] == both["feature_set_sha256"] == reordered["feature_set_sha256"]
    assert both["shared_genes"] == 75
    assert both["reference_genes_not_measured"] == 5
    assert one_cells.iloc[0]["label"] == both_cells.iloc[0]["label"] == reordered_cells.iloc[0]["label"]
    np.testing.assert_allclose(one_cells.iloc[0]["pca"], both_cells.iloc[0]["pca"], atol=1e-5)
    np.testing.assert_allclose(both_cells.iloc[0]["pca"], reordered_cells.iloc[0]["pca"], atol=1e-5)
    assert both["projection_sha256"] == one["projection_sha256"]
    assert reference.X[0, 0] == reference_data().X[0, 0]


@pytest.mark.parametrize("problem,reason", [
    ("few_genes", "quick_mapping_insufficient_shared_genes"),
    ("normalized", "raw_counts_must_be_nonnegative_integers"),
    ("zero_cell", "quick_mapping_zero_count_cells"),
    ("duplicate_genes", "duplicate_gene_ids"),
])
def test_unsafe_query_does_not_produce_positions(problem, reason):
    from bridge.tool_packages.p0_02_cell_state.quick_atlas import map_counts
    reference = reference_data()
    query = reference[[0, 32]].copy()
    if problem == "few_genes": query = query[:, :10].copy()
    if problem == "normalized": query.X.data[:] *= 0.1
    if problem == "zero_cell": query.X[0, :] = 0
    if problem == "duplicate_genes": query.var_names = ["duplicate"] * query.n_vars
    tree, ids = tree_data()
    with pytest.raises(ValueError) as error:
        map_counts(query, reference, tree, ids, RECIPE)
    assert getattr(error.value, "reason_code", str(error.value)) == reason


def test_resource_binding_rejects_wrong_modality_and_tampering(tmp_path):
    from bridge.tool_packages.p0_02_cell_state.quick_atlas_reference import freeze_reference, load_reference
    reference = reference_data()
    tree, ids = tree_data()
    manifest = freeze_reference(reference, tree, ids, tmp_path / "frozen",
                                reference_id="REF-CHEN-VMB-SC-v1", modality="scRNA",
                                source_records=[{"id": "synthetic-source", "sha256": "a" * 64}], recipe=RECIPE)
    loaded = load_reference(manifest, expected_modality="scRNA")
    assert loaded.reference.n_obs == 96 and loaded.tree_cell_ids == ids
    with pytest.raises(ValueError, match="quick_mapping_reference_modality_mismatch"):
        load_reference(manifest, expected_modality="snRNA")
    payload = json.loads(manifest.read_text())
    (manifest.parent / payload["data"]["path"]).write_bytes(b"changed")
    with pytest.raises(ValueError, match="quick_mapping_reference_integrity"):
        load_reference(manifest, expected_modality="scRNA")

def test_registered_quick_mode_requires_real_qc_and_reopens_bound_outputs(tmp_path, monkeypatch):
    from pathlib import Path
    from quick_atlas_support import split_counts
    from bridge.toolkit.registry import ToolRegistry
    from bridge.toolkit.contracts import InputAsset, ToolRequest
    from bridge.tool_packages.p0_01_input_qc.io import sha256_path
    from bridge.tool_packages.p0_02_cell_state.quick_atlas_reference import freeze_reference
    reference = reference_data()
    reference.var_names = ["FOXA2", *reference.var_names[1:]]
    tree, ids = tree_data()
    manifest = freeze_reference(reference, tree, ids, tmp_path / "reference",
                                reference_id="REF-CHEN-VMB-SC-v1", modality="scRNA",
                                source_records=[{"id": "synthetic", "sha256": "a" * 64}], recipe=RECIPE)
    query = reference[[3, 35, 67]].copy()
    path = tmp_path / "query.h5ad"
    split_counts(query).write_h5ad(path)
    asset = InputAsset(asset_id="synthetic-query", path=path, format="h5ad", input_level="count_ready",
                       matrix_semantics="raw_counts", matrix_location="X", assay="scRNA-seq",
                       checksum=sha256_path(path), metadata={"source_family_id": "SYNTHETIC-QUERY"})
    registry = ToolRegistry.load_default()
    parameters = {"reference_manifest": str(manifest), "reference_manifest_sha256": sha256_path(manifest),
                  "sample_context": "pre_graft"}
    missing = ToolRequest(request_id="no-qc", tool_id="P0-02", assets=[asset],
                          output_dir=tmp_path / "no-qc", measurement_spec_ref="ATLAS-ingest-quick-v0.1",
                          parameters=parameters)
    assert not registry.check_eligibility(missing).eligible
    qc = registry.run(ToolRequest(request_id="real-qc", tool_id="P0-01", assets=[asset], output_dir=tmp_path / "qc"))
    assert qc.execution_state == "succeeded", qc.reason_codes
    artifacts = {x.path.name: x for x in qc.artifacts}
    profile = json.loads(artifacts["qc_readiness_profile.json"].path.read_text())
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps({"profiles": {profile["profile_id"]: {
        "path": str(artifacts["qc_readiness_profile.json"].path),
        "sha256": artifacts["qc_readiness_profile.json"].sha256,
        "structured_output_index_path": str(artifacts["structured_output_index.json"].path),
        "structured_output_index_sha256": artifacts["structured_output_index.json"].sha256,
    }}}))
    monkeypatch.setenv("BRIDGE_QC_PROFILE_CATALOG", str(catalog))
    asset = asset.model_copy(update={"metadata": {**asset.metadata, "qc_profile_ref": profile["profile_id"]}})
    request = missing.model_copy(update={"request_id": "map", "assets": [asset], "output_dir": tmp_path / "mapping"})
    eligibility = registry.check_eligibility(request)
    assert eligibility.eligible, eligibility.reason_codes
    run = registry.run(request)
    assert run.execution_state == "succeeded", run.reason_codes
    registry.validate_result(run, request)
    artifact = next(x for x in run.artifacts if x.kind == "quick_atlas_mapping")
    assert sha256_path(artifact.path) == artifact.sha256
    result = json.loads(artifact.path.read_bytes())
    assert result["n_cells"] == 3 and result["n_tree_cells"] == 2
    assert result["versions"]["reference"] == "REF-CHEN-VMB-SC-v1"
    assert result["input_sha256"] == asset.checksum
    assert result["evidence_ids"] == artifact.evidence_ids
    marker_artifact = next(x for x in run.artifacts if x.kind == "quick_atlas_marker_expression")
    panel = json.loads(marker_artifact.path.read_bytes())
    # The first query cell has 36 FOXA2 counts out of 602, regardless of CSR representation.
    assert panel["sample"]["values"][0][panel["genes"].index("FOXA2")] == pytest.approx(
        np.log1p(36 * 10000 / 602), abs=1e-6)
    assert run.measurements == []  # No chain score or scientific qualification is invented.
    assert sha256_path(path) == asset.checksum
    manifest.write_text(manifest.read_text() + " ")
    rejected = registry.run(request.model_copy(update={"request_id": "tampered", "output_dir": tmp_path / "tampered"}))
    assert rejected.execution_state == "failed"
    assert "quick_mapping_reference_integrity" in rejected.reason_codes


def test_marker_expression_uses_query_counts_not_neighbor_and_keeps_missing_null():
    from bridge.tool_packages.p0_02_cell_state.quick_atlas import map_counts
    reference = reference_data()
    names = reference.var_names.tolist()
    names[:3] = ["FOXA2", "TH", "DDC"]
    reference.var_names = names
    query = reference[[3, 35, 67]].copy()
    query.X[0, 0] = 0  # Measured zero must survive; the reference neighbor is nonzero.
    query = query[:, query.var_names != "DDC"].copy()
    tree, ids = tree_data()
    # Extra tree point has no matching mapping reference; do not invent its expression.
    tree["cells"].append([0.8, 0.3, 0.1, 1, 20, 0.9, 0])
    ids.append("unavailable-sn")
    summary, cells = map_counts(query, reference, tree, ids, RECIPE)
    panel = summary["marker_expression_payload"]
    genes = panel["genes"]
    assert panel["sample"]["values"][0][genes.index("FOXA2")] == 0
    assert panel["sample"]["values"][0][genes.index("LMX1A")] is None
    assert panel["gene_status"][genes.index("DDC")] == {"gene": "DDC", "status": "not_in_shared_gene_space", "missing_from": ["query"]}
    assert panel["reference"]["tree_cell_indices"] == list(range(6))
    assert len(panel["sample"]["values"]) == len(summary["mapped_cells"])
    shared = reference.var_names[reference.var_names.isin(query.var_names)]
    total = float(query[0, shared].X.sum())
    expected = np.log1p(float(query[0, "TH"].X.sum()) * 10000 / total)
    assert panel["sample"]["values"][0][genes.index("TH")] == pytest.approx(expected, abs=1e-6)
    assert panel["reference"]["values"][0][genes.index("FOXA2")] > 0
    assert cells["display_index"].tolist() == [0, 1, -1]
    assert all(x["value"] is None for x in summary["chain"])


@pytest.mark.parametrize("side", ["query", "reference"])
def test_equivalent_sparse_storage_preserves_mapping_and_inputs(tmp_path, side):
    import pandas as pd
    from quick_atlas_support import split_counts
    from bridge.toolkit.contracts import InputAsset
    from bridge.tool_packages.p0_01_input_qc.io import read_expression_asset, sha256_path
    from bridge.tool_packages.p0_02_cell_state.quick_atlas import map_counts

    reference = reference_data()
    reference.var_names = ["FOXA2", *reference.var_names[1:]]
    query = reference[[3, 35, 67]].copy()
    tree, ids = tree_data()
    expected, expected_cells = map_counts(query, reference, tree, ids, RECIPE)
    original = query if side == "query" else reference
    path = tmp_path / "duplicate-entries.h5ad"
    split_counts(original).write_h5ad(path)
    file_hash = sha256_path(path)
    loaded = read_expression_asset(InputAsset(asset_id="synthetic", path=path, format="h5ad",
        input_level="count_ready", matrix_location="X", matrix_semantics="raw_counts", assay="scRNA-seq"))
    assert not loaded.X.has_canonical_format
    np.testing.assert_array_equal(loaded.X.toarray(), original.X.toarray())
    before = tuple(a.copy() for a in (loaded.X.data, loaded.X.indices, loaded.X.indptr))
    actual, actual_cells = map_counts(loaded if side == "query" else query,
        loaded if side == "reference" else reference, tree, ids, RECIPE)
    # Canonicalizing the private working copy must not rewrite the caller's matrix or file.
    for actual_array, expected_array in zip((loaded.X.data, loaded.X.indices, loaded.X.indptr), before, strict=True):
        np.testing.assert_array_equal(actual_array, expected_array)
    assert sha256_path(path) == file_hash
    np.testing.assert_allclose(np.stack(actual_cells.pca), np.stack(expected_cells.pca), atol=1e-6)
    pd.testing.assert_frame_equal(actual_cells.drop(columns="pca"), expected_cells.drop(columns="pca"))
    assert actual == expected
