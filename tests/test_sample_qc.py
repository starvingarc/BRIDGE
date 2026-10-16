"""Sample detail reads real automatic QC independently of mapping success."""
import hashlib
import json
from dataclasses import replace

from fastapi.testclient import TestClient

from account_support import create_test_app, login_test_account
from multiuser_support import multi_clients
from test_research_atlas_mapping import resources, objects, upload, wait_mapping, DECLARATION
from test_research_objects import sample, base, request
from bridge.web.runtime import Settings


def qc_analysis(client, rid, sid):
    rows = request(client, "GET", base(rid) + f"/samples/{sid}/analyses")["analyses"]
    qc = [a for a in rows if a["tool"]["id"] == "P0-01"]
    assert len(qc) == 1, rows
    return qc[0], rows


def test_sample_qc_has_verified_summary_figures_table_and_owner_routes(tmp_path):
    with multi_clients(tmp_path / "accounts", **resources(tmp_path)) as (_, alice, bob, admin):
        rid, run = objects(alice)
        mid = upload(alice, rid, tmp_path)
        s = sample(alice, rid, run, material_id=mid, mapping_input=DECLARATION)
        final, _ = wait_mapping(alice, rid, s["id"])
        assert final["status"] == "done"
        a, rows = qc_analysis(alice, rid, s["id"])
        assert [r["tool"]["id"] for r in rows] == ["P0-01", "P0-06", "P0-02"]
        assert [r["version"] for r in rows] == [1, 2, 3]
        assert a["source_kind"] == "sample_qc" and a["session_id"] is None
        assert a["assessment_id"] == final["assessment_id"]
        assert a["qc_summary"]["schema_integrity"]["n_observations"] == 3
        assert a["qc_summary"]["count_metrics_state"] == "measured"
        assert a["qc_summary"]["domain_score"] is None
        assert a["availability"]["status"] == "available"
        assert str(tmp_path) not in json.dumps(a)
        assert "private-rg" not in json.dumps(a)
        artifacts = [r["artifact"] for r in a["results"]]
        figure = next(x for x in artifacts if x["kind"] == "figure")
        table = next(x for x in artifacts if x["kind"] == "table")
        assert alice.get(figure["url"]).content.startswith(b"\x89PNG")
        preview = request(alice, "GET", table["url"] + "/preview")
        assert preview["total_rows"] == 3 and len(preview["rows"]) == 3
        assert "total_counts" in preview["columns"]
        assert "worker.log" not in json.dumps(artifacts)
        for result in a["results"]:
            reply = alice.get(result["artifact"]["url"])
            assert reply.status_code == 200, reply.text
            assert hashlib.sha256(reply.content).hexdigest() == result["display_sha256"]
        detail = base(rid) + f"/analyses/{a['id']}"
        for other in (bob, admin):
            assert other.get(detail).status_code == 404
            assert other.get(figure["url"]).status_code == 404
            assert other.get(table["url"] + "/preview").status_code == 404
        # The same saved input/receipt/output must be rechecked on detail AND direct reads.
        service = alice.app.state.service
        root = service.researches.directory(rid)
        qc_receipt = root / "atlas-runs" / final["assessment_id"] / "qc-run.json"
        saved_run = json.loads(qc_receipt.read_bytes())
        from pathlib import Path
        target = Path(next(x["path"] for x in saved_run["artifacts"] if x["kind"] == "visualization_png"))
        for path in (qc_receipt, target, root / "materials" / (mid + ".bin")):
            original = path.read_bytes()
            try:
                path.write_bytes(original + b"broken")
                unavailable = request(alice, "GET", detail)
                assert unavailable["availability"]["status"] == "unavailable"
                assert unavailable["qc_summary"] is None
                assert unavailable["snapshot_sha256"] == a["snapshot_sha256"]
                assert all(r["artifact"] is None for r in unavailable["results"])
                assert alice.get(figure["url"]).status_code == 409
                assert alice.get(table["url"] + "/preview").status_code == 409
            finally:
                path.write_bytes(original)
        # Even an identical file outside the controlled directory is not a valid source.
        saved = target.with_suffix(".original.png")
        target.rename(saved)
        try:
            target.symlink_to(saved)
            assert request(alice, "GET", detail)["availability"]["status"] == "unavailable"
            assert alice.get(figure["url"]).status_code == 409
        finally:
            target.unlink()
            saved.rename(target)
        assert alice.get(detail + "/results/" + "0" * 32).status_code == 404
        assert alice.get(figure["url"] + "/preview").status_code == 415
        assert request(alice, "GET", detail) == a
        before = (root / "analyses.json").read_bytes()
        request(alice, "GET", base(rid) + f"/samples/{s['id']}/analyses")
        assert (root / "analyses.json").read_bytes() == before


def test_completed_qc_survives_failed_mapping_and_backfills_without_rerun(tmp_path):
    options = resources(tmp_path)
    settings = Settings(storage_root=tmp_path / "store", origin="http://testserver",
                        model_base_url="https://provider.invalid/v1", model="unused", model_api_key="unused",
                        **options)
    with TestClient(create_test_app(settings)) as client:
        login_test_account(client)
        rid, run = objects(client)
        # Real QC succeeds, then actual mapping fails because no genes overlap the reference.
        from quick_atlas_support import reference_data
        query = reference_data()[[3, 35, 67]].copy()
        query.var_names = ["NO_REFERENCE_" + str(i) for i in range(query.n_vars)]
        path = tmp_path / "no-overlap.h5ad"
        query.write_h5ad(path)
        with path.open("rb") as stream:
            mid = client.post(base(rid) + "/uploads", files={"file": (path.name, stream)}).json()["id"]
        s = sample(client, rid, run, material_id=mid, mapping_input=DECLARATION)
        final, _ = wait_mapping(client, rid, s["id"])
        assert final["status"] == "failed"
        a, rows = qc_analysis(client, rid, s["id"])
        assert len(rows) == 2 and a["availability"]["status"] == "available"
        root = client.app.state.service.researches.directory(rid)
        receipt = root / "atlas-runs" / final["assessment_id"] / "qc-run.json"
        receipt_bytes = receipt.read_bytes()
    with TestClient(create_test_app(settings)) as restarted:
        login_test_account(restarted)
        assert qc_analysis(restarted, rid, s["id"])[0] == a
        # Existing pre-feature QC has no index; a restart imports it exactly once.
        state = json.loads((root / "analyses.json").read_bytes())
        state["analyses"].pop(a["id"])
        (root / "analyses.json").write_text(json.dumps(state))
    settings = replace(settings, quick_atlas_catalog_path=None, workbench_tree_path=None)
    with TestClient(create_test_app(settings)) as restarted:
        login_test_account(restarted)
        restored, rows = qc_analysis(restarted, rid, s["id"])
        assert restored["availability"]["status"] == "available" and len(rows) == 2
        assert restored["tool"]["run_id"] == a["tool"]["run_id"]
        assert receipt.read_bytes() == receipt_bytes
    with TestClient(create_test_app(settings)) as restarted:
        login_test_account(restarted)
        assert qc_analysis(restarted, rid, s["id"])[0] == restored
    # Damaged legacy QC is not silently imported as a successful analysis.
    state = json.loads((root / "analyses.json").read_bytes())
    state["analyses"].pop(restored["id"])
    (root / "analyses.json").write_text(json.dumps(state))
    receipt.write_bytes(b"broken receipt")
    try:
        with TestClient(create_test_app(settings)) as restarted:
            login_test_account(restarted)
            rows = request(restarted, "GET", base(rid) + f"/samples/{s['id']}/analyses")["analyses"]
            assert [a["source_kind"] for a in rows] == ["sample_cell_cycle"]
    finally:
        receipt.write_bytes(receipt_bytes)
