"""Automatic sample computations use declared inputs and immutable, owner-bound results."""
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from bridge.web.research_object_models import MappingInput
from bridge.web.atlas_worker import cell_cycle_request
from bridge.toolkit.contracts import InputAsset
from bridge.toolkit.registry import ToolRegistry
from test_research_atlas_mapping import DECLARATION


def test_capture_declaration_preserves_fields_and_rejects_conflict():
    declaration = MappingInput(**DECLARATION, capture_id_column="capture",
                               gene_symbol_column="symbol")
    assert declaration.model_dump()["capture_id_column"] == "capture"
    with pytest.raises(ValidationError):
        MappingInput(**DECLARATION, capture_id="one", capture_id_column="capture")


def test_cycle_request_runs_registered_method_on_all_original_observations(tmp_path):
    import anndata as ad
    import numpy as np
    import pandas as pd
    import bridge.tool_packages.p0_06_proliferation_stress_response as cycle_package
    resource = Path(cycle_package.__file__).parent / "resources/seurat-cell-cycle-v5.5.1-candidate.json"
    bundle = json.loads(resource.read_bytes())
    genes = list(dict.fromkeys(bundle["lists"]["s.genes"]["genes"] + bundle["lists"]["g2m.genes"]["genes"]))
    genes += ["BACKGROUND_" + str(i) for i in range(300)]
    rng = np.random.default_rng(7)
    counts = rng.poisson(3, size=(120, len(genes))).astype("float32")
    data = ad.AnnData(counts, obs=pd.DataFrame(index=["cell-" + str(i) for i in range(120)]),
                      var=pd.DataFrame({"symbol": genes}, index=["gene-" + str(i) for i in range(len(genes))]))
    path = tmp_path / "synthetic.h5ad"
    data.write_h5ad(path)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    asset = InputAsset(asset_id="asset:synthetic", path=path, format="h5ad", input_level="count_ready",
                       checksum=sha, matrix_location="X", matrix_semantics="raw_counts", assay="scRNA-seq",
                       metadata={"source_family_id": "synthetic-only", "gene_symbol_column": "symbol"})
    request = cell_cycle_request(asset, "attempt", tmp_path)
    assert request.tool_id == "P0-06"
    payload = json.loads(request.object_inputs[0].path.read_bytes())
    assert payload["data_view"]["view_kind"] == "all_observations"
    assert payload["data_view"]["n_observations"] == 120
    assert payload["s_genes"] == bundle["lists"]["s.genes"]["genes"]
    registry = ToolRegistry.load_default()
    result = registry.run(request)
    registry.validate_result(result, request)
    assert result.execution_state in {"succeeded", "partial"}, result.reason_codes
    assert result.result["cell_cycle"]["assessment_state"] == "available"
    artifact = next(a for a in result.artifacts if a.kind == "exploratory_observation_scores")
    rows = pd.read_parquet(artifact.path)
    assert rows["observation_id"].tolist() == data.obs_names.tolist()
    assert rows[["cycle_S_score", "cycle_G2M_score"]].notna().all().all()
    assert set(rows["phase"]) <= {"G1", "S", "G2M"}
    assert result.result["domain_score"] is None
    assert hashlib.sha256(path.read_bytes()).hexdigest() == sha


def test_automatic_cycle_has_owner_bound_results_and_survives_restart(tmp_path):
    from multiuser_support import multi_clients
    from test_research_atlas_mapping import resources, objects, upload, wait_mapping
    from test_research_objects import sample, base, request

    options = resources(tmp_path)
    with multi_clients(tmp_path / "accounts", **options) as (_, alice, bob, admin):
        rid, experiment = objects(alice)
        mid = upload(alice, rid, tmp_path)
        s = sample(alice, rid, experiment, material_id=mid,
                   mapping_input={**DECLARATION, "capture_id": "synthetic-capture"})
        final, _ = wait_mapping(alice, rid, s["id"])
        assert final["status"] == "done"
        rows = request(alice, "GET", base(rid) + f"/samples/{s['id']}/analyses")["analyses"]
        cycle = next(a for a in rows if a["source_kind"] == "sample_cell_cycle")
        qc = next(a for a in rows if a["source_kind"] == "sample_qc")
        assert cycle["availability"]["status"] == "available"
        assert cycle["cell_cycle_summary"]["cell_cycle"]["assessment_state"] == "not_assessed"
        assert cycle["cell_cycle_summary"]["cell_cycle"]["s_g2m_fraction"] is None
        assert cycle["cell_cycle_summary"]["domain_score"] is None
        assert str(tmp_path) not in json.dumps(cycle)
        profile = next(r["artifact"] for r in qc["results"] if r["artifact"]["kind"] == "evidence")
        # A three-cell capture is insufficient, not evidence of zero doublets.
        assert alice.get(profile["url"]).json()["doublet_assessment"]["state"] == "not_assessed"
        root = alice.app.state.service.researches.directory(rid)
        attempt = root / "atlas-runs" / final["assessment_id"]
        qc_run = json.loads((attempt / "qc-run.json").read_bytes())
        assert qc_run["request"]["parameters"]["run_scrublet"] is True
        assert qc_run["request"]["assets"][0]["metadata"]["capture_id"] == "synthetic-capture"
        table = next(r["artifact"] for r in cycle["results"] if r["artifact"]["kind"] == "table")
        preview = request(alice, "GET", table["url"] + "/preview")
        assert preview["total_rows"] == 3
        assert "observation_id" in preview["columns"]
        for result in cycle["results"]:
            artifact = result["artifact"]
            raw = alice.get(artifact["url"]).content
            assert hashlib.sha256(raw).hexdigest() == result["display_sha256"]
            for other in (bob, admin):
                assert other.get(artifact["url"]).status_code == 404
        detail = base(rid) + f"/analyses/{cycle['id']}"
        cycle_run = json.loads((attempt / "cell-cycle-run.json").read_bytes())
        table_path = Path(next(a["path"] for a in cycle_run["artifacts"] if a["kind"] == "exploratory_observation_scores"))
        for target in (attempt / "cell-cycle-run.json", attempt / "cell-cycle-input.json", table_path):
            original = target.read_bytes()
            try:
                target.write_bytes(original + b"tamper")
                broken = request(alice, "GET", detail)
                assert broken["availability"]["status"] == "unavailable"
                assert broken["cell_cycle_summary"] is None
                assert alice.get(table["url"]).status_code == 409
            finally:
                target.write_bytes(original)
        # Restart backfill is separately exercised through the same public registration path.
        store = alice.app.state.service.sample_analyses
        state_path = root / "analyses.json"
        state = json.loads(state_path.read_bytes())
        del state["analyses"][cycle["id"]]
        state_path.write_text(json.dumps(state))
        receipt_before = (attempt / "cell-cycle-run.json").read_bytes()
        alice.app.state.service.research_objects.backfill_qc_analyses(store.register_cell_cycle)
        restored = request(alice, "GET", base(rid) + f"/samples/{s['id']}/analyses")["analyses"]
        assert sum(a["source_kind"] == "sample_cell_cycle" for a in restored) == 1
        before_second_backfill = state_path.read_bytes()
        alice.app.state.service.research_objects.backfill_qc_analyses(store.register_cell_cycle)
        assert state_path.read_bytes() == before_second_backfill
        assert (attempt / "cell-cycle-run.json").read_bytes() == receipt_before


def test_registered_doublets_keep_all_cells_and_respect_two_captures(tmp_path):
    import anndata as ad
    import numpy as np
    import pandas as pd
    from bridge.toolkit.contracts import ToolRequest

    rng = np.random.default_rng(42)
    rates = rng.lognormal(mean=0, sigma=1.3, size=(240, 1000))
    counts = rng.poisson(rates).astype("float32")
    data = ad.AnnData(counts,
        obs=pd.DataFrame({"capture": ["capture-a"] * 120 + ["capture-b"] * 120},
                         index=["cell-" + str(i) for i in range(240)]),
        var=pd.DataFrame(index=["GENE" + str(i) for i in range(1000)]))
    path = tmp_path / "synthetic-captures.h5ad"
    data.write_h5ad(path)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    asset = InputAsset(asset_id="asset:synthetic", path=path, format="h5ad", input_level="count_ready",
                       checksum=sha, matrix_location="X", matrix_semantics="raw_counts", assay="scRNA-seq",
                       metadata={"source_family_id": "synthetic-only", "capture_id_column": "capture"})
    registry = ToolRegistry.load_default()
    request = ToolRequest(request_id="test-doublets", tool_id="P0-01", assets=[asset],
                          parameters={"run_scrublet": True}, output_dir=tmp_path / "qc")
    result = registry.run(request)
    registry.validate_result(result, request)
    profile = json.loads(next(a.path for a in result.artifacts if a.kind == "qc_profile_v2").read_bytes())
    doublets = profile["doublet_assessment"]
    assert doublets["state"] == "candidate", doublets
    assert [(c["capture_id"], c["n_observations"]) for c in doublets["per_capture"]] == [
        ("capture-a", 120), ("capture-b", 120)]
    metrics = pd.read_parquet(next(a.path for a in result.artifacts if a.kind == "qc_metrics"))
    assert metrics.index.tolist() == data.obs_names.tolist()
    assert metrics["scrublet_score"].notna().all()
    assert set(metrics["scrublet_class"]) <= {"doublet", "singlet"}
    assert doublets["n_predicted"] == int((metrics["scrublet_class"] == "doublet").sum())
    assert not any(a.kind == "qc_selected_expression" for a in result.artifacts)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == sha


@pytest.mark.parametrize("failure", ["timeout", "native_exit"])
def test_cycle_process_failure_does_not_prevent_mapping(tmp_path, monkeypatch, failure):
    from bridge.web import atlas_worker
    from test_research_atlas_mapping import resources
    from quick_atlas_support import reference_data
    reference_data()[[3, 35, 67]].copy().write_h5ad(tmp_path / "query.h5ad")
    path = tmp_path / "query.h5ad"
    config = json.loads(resources(tmp_path)["quick_atlas_catalog_path"].read_bytes())["pre_graft"]
    job = {"id": "cycle-failure", "asset": {
        "asset_id": "synthetic", "path": str(path), "format": "h5ad", "input_level": "count_ready",
        "checksum": hashlib.sha256(path.read_bytes()).hexdigest(), "matrix_location": "X",
        "matrix_semantics": "raw_counts", "assay": "scRNA-seq",
        "metadata": {"source_family_id": "synthetic-only"}},
        "parameters": {"reference_manifest": config["manifest"],
                       "reference_manifest_sha256": config["sha256"], "sample_context": "pre_graft"}}
    job_path = tmp_path / "job.json"
    job_path.write_text(json.dumps(job))
    import subprocess
    original_run = subprocess.run
    def fail(command, **kwargs):
        if "--cell-cycle" in command:
            if failure == "timeout":
                raise subprocess.TimeoutExpired(command, kwargs["timeout"])
            raise subprocess.CalledProcessError(-11, command)
        return original_run(command, **kwargs)
    monkeypatch.setattr(subprocess, "run", fail)
    # Worker normally runs in its own process; restore its one process-local catalog variable here.
    monkeypatch.setenv("BRIDGE_QC_PROFILE_CATALOG", "")
    atlas_worker.run_job(job_path)
    assert json.loads((tmp_path / "qc-run.json").read_bytes())["execution_state"] == "succeeded"
    assert json.loads((tmp_path / "mapping-run.json").read_bytes())["execution_state"] == "succeeded"
    assert json.loads((tmp_path / "cell-cycle-error.json").read_bytes()) == {
        "reason_code": "cell_cycle_execution_timeout" if failure == "timeout" else "cell_cycle_execution_failed"}


@pytest.mark.parametrize("source_family", ["H9 batch 1", "来源家族"])
def test_new_declaration_rejects_incompatible_family_before_freezing(source_family):
    with pytest.raises(ValidationError):
        MappingInput(**{**DECLARATION, "source_family_id": source_family})


def test_optional_cycle_has_bounded_subprocess_and_records_timeout(tmp_path, monkeypatch):
    import subprocess
    from bridge.web.atlas_worker import run_optional_cell_cycle
    calls = []
    def timeout(command, **kwargs):
        calls.append((command, kwargs))
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])
    monkeypatch.setattr(subprocess, "run", timeout)
    run_optional_cell_cycle(tmp_path / "job.json")
    assert calls[0][1]["timeout"] == 600
    assert "--cell-cycle" in calls[0][0]
    assert json.loads((tmp_path / "cell-cycle-error.json").read_bytes())["reason_code"] == "cell_cycle_execution_timeout"
