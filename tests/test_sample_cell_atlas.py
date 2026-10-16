"""All-cell, sample-owned expression embeddings use actual registered tools."""
import hashlib
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from bridge.web.provider import Action
from test_research_atlas_mapping import DECLARATION, objects
from test_research_objects import base, request, sample
from test_sample_workflow import wait_workflow


def atlas_input(path):
    from anndata import AnnData
    from scipy import sparse
    rng = np.random.default_rng(140)
    counts = rng.poisson(2, (48, 60)).astype(np.float32)
    counts[:24, :8] += 12
    counts[24:, 8:16] += 12
    counts[:, -1] = 0  # Measured zero must remain distinct from an absent gene.
    data = AnnData(sparse.csr_matrix(counts),
        obs=pd.DataFrame(index=[f"original-cell-{i}" for i in range(48)]),
        var=pd.DataFrame(index=[f"GENE{i}" for i in range(60)]))
    data.write_h5ad(path)
    return data


def test_worker_without_reference_produces_bound_full_cell_atlas(tmp_path, monkeypatch):
    from bridge.web.atlas_worker import run_job
    path = tmp_path / "synthetic.h5ad"
    data = atlas_input(path)
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    job = {"id": "synthetic-atlas", "asset": {
        "asset_id": "synthetic", "path": str(path), "format": "h5ad", "input_level": "count_ready",
        "checksum": checksum, "matrix_location": "X", "matrix_semantics": "raw_counts",
        "assay": "scRNA-seq", "metadata": {"source_family_id": "SYNTHETIC-ATLAS"}}, "parameters": {}}
    job_path = tmp_path / "job.json"
    job_path.write_text(json.dumps(job))
    monkeypatch.setenv("BRIDGE_QC_PROFILE_CATALOG", "")
    run_job(job_path)
    receipt_path = tmp_path / "cell-atlas-run.json"
    assert receipt_path.exists(), "QC succeeded but sample atlas was not executed"
    receipt = json.loads(receipt_path.read_bytes())
    assert receipt["execution_state"] == "succeeded", receipt
    assert receipt["request"]["measurement_spec_ref"] == "EXPRESSION-exploration-v0.1"
    assert receipt["request"]["parameters"]["exploration"]["embedding_key"] is None
    assert receipt["request"]["parameters"]["exploration"]["group_key"] is None
    artifact = next(a for a in receipt["artifacts"] if a["kind"] == "expression_cell_coordinates")
    table = pd.read_parquet(artifact["path"])
    assert table.columns.tolist() == ["observation_id", "umap_1", "umap_2", "leiden"]
    assert table.observation_id.tolist() == data.obs_names.tolist()
    assert np.isfinite(table[["umap_1", "umap_2"]].to_numpy()).all()
    assert table.leiden.notna().all() and table.leiden.nunique() >= 2
    assert receipt["result"]["input_data_view"]["n_observations"] == 48
    assert receipt["result"]["domain_score"] is None
    marker_artifact = next((a for a in receipt["artifacts"] if a["kind"] == "expression_cluster_markers"), None)
    assert marker_artifact is not None, "ranked marker table must be served with its own clustering"
    marker_rows = pd.read_parquet(marker_artifact["path"])
    assert set(marker_rows.leiden) == set(table.leiden)
    assert marker_rows.groupby("leiden")["rank"].min().eq(1).all()
    assert any(a["kind"] == "expression_gene_store" for a in receipt["artifacts"])
    assert hashlib.sha256(path.read_bytes()).hexdigest() == checksum


def test_atlas_results_are_sample_owned_recoverable_and_fail_closed(tmp_path, monkeypatch):
    from multiuser_support import multi_clients
    monkeypatch.setattr("bridge.web.service.converse", lambda *args: Action(action="reply", text="已有基础结果已保存。"))
    path = tmp_path / "synthetic.h5ad"
    data = atlas_input(path)
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    with multi_clients(tmp_path / "accounts") as (service, alice, bob, admin):
        rid, experiment = objects(alice)
        with path.open("rb") as stream:
            uploaded = alice.post(base(rid) + "/uploads", files={"file": (path.name, stream)})
            assert uploaded.status_code == 200, uploaded.text
            mid = uploaded.json()["id"]
        created = sample(alice, rid, experiment, material_id=mid, mapping_input=DECLARATION)
        final = wait_workflow(alice, rid, created["id"])
        history = base(rid) + f"/samples/{created['id']}/analyses"
        analyses = request(alice, "GET", history)["analyses"]
        atlas = next((r for r in analyses if r["source_kind"] == "sample_cell_atlas"), None)
        assert atlas is not None, "sample atlas is absent from the sample's analysis history"
        assert atlas["availability"]["status"] == "available"
        assert atlas["cell_atlas_summary"]["n_observations"] == 48
        assert str(tmp_path) not in json.dumps(atlas)
        tables = [r for r in atlas["results"] if r["artifact"]["kind"] == "table"]
        assert len(tables) == 2
        table = next(t for t in tables if t["artifact"]["name"] == "expression_cells.parquet")
        marker = next(t for t in tables if t["artifact"]["name"] == "expression_markers.parquet")
        marker_rows = pd.read_parquet(io.BytesIO(alice.get(marker["artifact"]["url"]).content))
        assert set(marker_rows.leiden) and marker_rows["rank"].min() == 1
        url = table["artifact"]["url"]
        original = alice.get(url)
        assert original.status_code == 200
        rows = pd.read_parquet(io.BytesIO(original.content))
        assert rows.observation_id.tolist() == data.obs_names.tolist()
        genes_url = base(rid) + f"/analyses/{atlas['id']}/genes"
        expression_url = base(rid) + f"/analyses/{atlas['id']}/gene-expression"
        catalog = alice.get(genes_url, params={"query": "GENE1", "limit": 3}).json()
        assert catalog["total"] == 11 and catalog["genes"] == ["GENE1", "GENE10", "GENE11"]
        payload = alice.get(expression_url, params=[("gene", "GENE0"), ("gene", "GENE59"), ("gene", "absent")])
        assert payload.status_code == 200, payload.text
        assert "no-store" in payload.headers["cache-control"]
        assert "no-store" in alice.get(genes_url).headers["cache-control"]
        payload = payload.json()
        assert payload["observation_ids"] == data.obs_names.tolist()
        assert payload["leiden"] == rows.leiden.tolist()
        assert payload["analysis_id"] == atlas["id"] and payload["material_sha256"] == checksum
        by_gene = {g["gene"]: g for g in payload["genes"]}
        measured = by_gene["GENE0"]
        counts = data.X.toarray()
        expected = np.log1p(counts[:, 0] / counts.sum(axis=1) * 10000)
        np.testing.assert_allclose(measured["values"], expected, rtol=1e-6)
        for group in measured["groups"]:
            selected = rows.leiden.to_numpy() == group["leiden"]
            assert group["n_cells"] == int(selected.sum())
            np.testing.assert_allclose(group["mean_log1p"], expected[selected].mean(), rtol=1e-6)
            np.testing.assert_allclose(group["fraction_expressing"], (counts[selected, 0] > 0).mean())
        assert by_gene["GENE59"]["status"] == "available" and set(by_gene["GENE59"]["values"]) == {0}
        assert by_gene["absent"]["status"] == "not_found" and by_gene["absent"]["values"] is None
        assert by_gene["absent"]["groups"] is None
        assert alice.get(expression_url).status_code == 422
        assert alice.get(expression_url, params=[("gene", "x")]*33).status_code == 422
        # Exercise the response budget without building a giant fixture.
        from bridge.web import sample_gene_expression
        with monkeypatch.context() as limit_patch:
            limit_patch.setattr(sample_gene_expression, "MAX_RETURNED_VALUES", 48)
            assert alice.get(expression_url, params={"gene": "GENE0"}).status_code == 200
            assert alice.get(expression_url, params=[("gene", "GENE0"), ("gene", "GENE1")]).status_code == 413
        for other in (bob, admin):
            assert other.get(genes_url).status_code == 404
            assert other.get(expression_url, params={"gene": "GENE0"}).status_code == 404
        cycle = next(a for a in analyses if a["source_kind"] == "sample_cell_cycle")
        cycle_url = next(r["artifact"]["url"] for r in cycle["results"] if r["artifact"]["kind"] == "table")
        assert pd.read_parquet(io.BytesIO(alice.get(cycle_url).content)).observation_id.tolist() == rows.observation_id.tolist()
        for other in (bob, admin):
            assert other.get(url).status_code == 404
            assert other.get(base(rid) + f"/analyses/{atlas['id']}").status_code == 404
        # A second sample sharing the same material must not inherit this analysis.
        current_run = request(alice, "GET", base(rid) + "/workbench")["runs"][0]
        other_sample = sample(alice, rid, current_run, material_id=mid)
        assert request(alice, "GET", base(rid) + f"/samples/{other_sample['id']}/analyses")["analyses"] == []
        root = service.researches.directory(rid)
        attempt = root / "atlas-runs" / final["assessment_id"]
        receipt = json.loads((attempt / "cell-atlas-run.json").read_bytes())
        table_path = Path(next(a["path"] for a in receipt["artifacts"] if a["kind"] == "expression_cell_coordinates"))
        for target in (table_path, attempt / "cell-atlas-run.json", attempt / "qc-run.json"):
            before = target.read_bytes()
            try:
                target.write_bytes(before + b"tamper")
                changed = request(alice, "GET", base(rid) + f"/analyses/{atlas['id']}")
                assert changed["availability"]["status"] == "unavailable"
                assert changed["cell_atlas_summary"] is None
                assert alice.get(url).status_code == 409
            finally:
                target.write_bytes(before)
        gene_path = Path(next(a["path"] for a in receipt["artifacts"] if a["kind"] == "expression_gene_store"))
        before_gene = gene_path.read_bytes()
        gene_path.write_bytes(before_gene + b"tamper")
        assert alice.get(expression_url, params={"gene": "GENE0"}).status_code == 409
        gene_path.write_bytes(before_gene)
        assert alice.get(expression_url, params={"gene": "GENE0"}).status_code == 200
        store_path = root / "analyses.json"
        stored = json.loads(store_path.read_bytes())
        del stored["analyses"][atlas["id"]]
        store_path.write_text(json.dumps(stored))
        service.research_objects.backfill_qc_analyses(service.sample_analyses.register_cell_atlas)
        restored = request(alice, "GET", history)["analyses"]
        assert sum(r["source_kind"] == "sample_cell_atlas" for r in restored) == 1
        saved = store_path.read_bytes()
        service.research_objects.backfill_qc_analyses(service.sample_analyses.register_cell_atlas)
        assert store_path.read_bytes() == saved
        assert hashlib.sha256(path.read_bytes()).hexdigest() == checksum


def test_sparse_sample_resource_check_uses_stored_entries_without_densifying():
    """A 10k-cell 10x matrix must not be charged as a hypothetical dense array."""
    from anndata import AnnData
    from scipy import sparse
    from bridge.tool_packages._expression_data import validate_matrix
    count = 10036
    data = AnnData(sparse.csr_matrix((np.ones(count, dtype=np.float32),
        (np.arange(count), np.arange(count) % 33538)), shape=(count, 33538)))
    validate_matrix(data, raw=True)


@pytest.mark.parametrize("failure", ["timeout", "native_exit"])
def test_atlas_child_failure_keeps_qc_cycle_and_mapping(tmp_path, monkeypatch, failure):
    import subprocess
    from bridge.web import atlas_worker
    from test_research_atlas_mapping import resources
    from quick_atlas_support import reference_data
    path = tmp_path / "synthetic.h5ad"
    reference_data()[[3, 35, 67]].copy().write_h5ad(path)
    config = json.loads(resources(tmp_path)["quick_atlas_catalog_path"].read_bytes())["pre_graft"]
    job = {"id": "atlas-failure", "asset": {
        "asset_id": "synthetic", "path": str(path), "format": "h5ad", "input_level": "count_ready",
        "checksum": hashlib.sha256(path.read_bytes()).hexdigest(), "matrix_location": "X",
        "matrix_semantics": "raw_counts", "assay": "scRNA-seq",
        "metadata": {"source_family_id": "SYNTHETIC-ATLAS"}},
        "parameters": {"reference_manifest": config["manifest"],
                       "reference_manifest_sha256": config["sha256"], "sample_context": "pre_graft"}}
    job_path = tmp_path / "job.json"
    job_path.write_text(json.dumps(job))
    original_run = subprocess.run
    def fail(command, **kwargs):
        if "--cell-atlas" in command:
            if failure == "timeout":
                raise subprocess.TimeoutExpired(command, kwargs["timeout"])
            raise subprocess.CalledProcessError(-11, command)
        return original_run(command, **kwargs)
    monkeypatch.setattr(subprocess, "run", fail)
    monkeypatch.setenv("BRIDGE_QC_PROFILE_CATALOG", "")
    atlas_worker.run_job(job_path)
    for name in ("qc", "cell-cycle", "mapping"):
        assert json.loads((tmp_path / (name + "-run.json")).read_bytes())["execution_state"] in {"succeeded", "partial"}
    assert not (tmp_path / "cell-atlas-run.json").exists()
    assert json.loads((tmp_path / "cell-atlas-error.json").read_bytes())["reason_code"] == (
        "cell_atlas_execution_timeout" if failure == "timeout" else "cell_atlas_execution_failed")
