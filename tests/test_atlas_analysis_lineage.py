"""Unified history uses actual registered mapping runs and unchanged source files."""
import json
from copy import deepcopy
from dataclasses import replace

from fastapi.testclient import TestClient

from account_support import create_test_app, login_test_account
from multiuser_support import multi_clients
from test_research_atlas_mapping import resources, upload, objects, wait_mapping, DECLARATION
from test_research_objects import sample, base, request
from sample_analysis_support import qc, register
from web_support import client as provider_client
from bridge.web.runtime import Settings


def start_mapping(client, tmp_path):
    rid, run = objects(client)
    mid = upload(client, rid, tmp_path)
    s = sample(client, rid, run, material_id=mid, mapping_input=DECLARATION)
    final, board = wait_mapping(client, rid, s["id"])
    assert final["status"] == "done", board
    assessment = request(client, "GET", base(rid) + f"/assessments/{final['assessment_id']}")
    return rid, run, final, assessment


def test_mapping_and_session_share_history_with_exact_results_and_restart(tmp_path, provider_client):
    settings = Settings(storage_root=tmp_path / "store", origin="http://testserver",
                        model_base_url="https://provider.invalid/v1", model="unused", model_api_key="unused",
                        **resources(tmp_path))
    with TestClient(create_test_app(settings)) as client:
        login_test_account(client)
        rid, run, s, assessment = start_mapping(client, tmp_path)
        url = base(rid) + f"/samples/{s['id']}/analyses"
        history = request(client, "GET", url)["analyses"]
        assert len(history) == 3
        qc_analysis, cycle_analysis, a = history
        assert cycle_analysis["source_kind"] == "sample_cell_cycle"
        assert qc_analysis["tool"]["id"] == "P0-01"
        assert a["id"] == assessment["analysis_id"]
        assert a["assessment_id"] == assessment["id"]
        assert a["source_kind"] == "atlas_mapping"
        assert a["session_id"] is None and a["receipt_id"] is None
        assert a["version"] == 3 and a["run_id"] == run["id"]
        assert a["protocol_version_id"] == run["protocol_version_id"]
        assert a["tool"]["run_id"] == assessment["tool_run_id"]
        assert a["tool"]["id"] == "P0-02" and a["execution_state"] == "succeeded"
        assert a["mapping_versions"] == assessment["versions"]
        assert a["input_assets"][0]["matrix_semantics"] == "raw_counts"
        assert a["availability"]["status"] == "available"
        target = a["results"][0]["assessment"]
        assert target["id"] == assessment["id"]
        assert request(client, "GET", target["url"]) == assessment
        assert a["results"][0]["artifact"] is None
        assert a["results"][0]["display_sha256"] is None
        assert str(tmp_path) not in json.dumps(a) and "private-rg" not in json.dumps(a)
        assert "path" not in a["parameters"] and "reference_manifest" not in a["parameters"]
        sid, receipt = qc(client, rid, s["material_id"])
        session_analysis = register(client, rid, s, sid, receipt)
        assert session_analysis["version"] == 4
        assert session_analysis["source_kind"] == "session_execution"
        expected = [qc_analysis, cycle_analysis, a, session_analysis]
        assert request(client, "GET", url)["analyses"] == expected
        service = client.app.state.service
        root = service.researches.directory(rid)
        before = (root / "objects.json").read_bytes()
        assert request(client, "GET", base(rid) + f"/analyses/{a['id']}") == a
        assert (root / "objects.json").read_bytes() == before
    with TestClient(create_test_app(settings)) as restored:
        login_test_account(restored)
        assert request(restored, "GET", url)["analyses"] == expected
        # Existing mapping before this feature: backfill once, without rewriting sources.
        state = json.loads((root / "objects.json").read_bytes())
        saved = state["assessments"][assessment["id"]]
        saved.pop("_analysis")
        state["assessments"][assessment["id"]] = saved
        (root / "objects.json").write_text(json.dumps(state))
        source_bytes = {key: (root / saved[key]["path"]).read_bytes() for key in ("_result", "_receipt")}
    settings = replace(settings, quick_atlas_catalog_path=None, workbench_tree_path=None)
    with TestClient(create_test_app(settings)) as restored:
        login_test_account(restored)
        migrated = request(restored, "GET", url)["analyses"]
        assert len(migrated) == 4
        assert [x["version"] for x in migrated] == [1, 2, 4, 5]
        assert migrated[3]["assessment_id"] == assessment["id"]
        assert request(restored, "GET", base(rid) + "/workbench")["samples"][0]["revision"] == s["revision"]
        for key, raw in source_bytes.items():
            assert (root / saved[key]["path"]).read_bytes() == raw
    with TestClient(create_test_app(settings)) as restored:
        login_test_account(restored)
        assert request(restored, "GET", url)["analyses"] == migrated
    # A corrupt legacy input cannot be imported just because its old assessment says done.
    state = json.loads((root / "objects.json").read_bytes())
    state["assessments"][assessment["id"]].pop("_analysis")
    (root / "objects.json").write_text(json.dumps(state))
    material_path = root / "materials" / (s["material_id"] + ".bin")
    original_material = material_path.read_bytes()
    try:
        material_path.write_bytes(b"corrupted")
        with TestClient(create_test_app(settings)) as restored:
            login_test_account(restored)
            remaining = request(restored, "GET", url)["analyses"]
            assert [a["id"] for a in remaining] == [qc_analysis["id"], cycle_analysis["id"], session_analysis["id"]]
    finally:
        material_path.write_bytes(original_material)


def test_mapping_history_rechecks_corruption_and_owner_without_losing_metadata(tmp_path):
    with multi_clients(tmp_path / "accounts", **resources(tmp_path)) as (_, alice, bob, admin):
        rid, run, s, assessment = start_mapping(alice, tmp_path)
        url = base(rid) + f"/samples/{s['id']}/analyses"
        a = next(row for row in request(alice, "GET", url)["analyses"]
                 if row["source_kind"] == "atlas_mapping")
        detail = base(rid) + f"/analyses/{a['id']}"
        for other in (bob, admin):
            assert other.get(url).status_code == 404
            assert other.get(detail).status_code == 404
        root = alice.app.state.service.researches.directory(rid)
        path = root / "objects.json"
        raw_state = path.read_bytes()
        state = json.loads(raw_state)
        stored = state["assessments"][assessment["id"]]
        targets = [root / stored[k]["path"] for k in ("_result", "_receipt")]
        targets.append(root / "materials" / (s["material_id"] + ".bin"))
        for target in targets:
            original = target.read_bytes()
            try:
                target.write_bytes(original + b"broken")
                damaged = request(alice, "GET", detail)
                assert damaged["id"] == a["id"] and damaged["snapshot_sha256"] == a["snapshot_sha256"]
                assert damaged["availability"]["status"] == "unavailable"
                assert damaged["results"][0]["assessment"] is None
                assert [row for row in request(alice, "GET", url)["analyses"]
                        if row["source_kind"] == "atlas_mapping"] == [damaged]
            finally:
                target.write_bytes(original)
        # A matching hash alone never changes which sample this run belongs to.
        changed = deepcopy(state)
        changed["assessments"][assessment["id"]]["sample_id"] = "f" * 32
        try:
            path.write_text(json.dumps(changed))
            assert request(alice, "GET", detail)["availability"]["status"] == "unavailable"
        finally:
            path.write_bytes(raw_state)
        assert request(alice, "GET", detail) == a


def test_index_preparation_failure_cannot_commit_mapping_success(tmp_path, monkeypatch):
    from bridge.web.sample_analyses import SampleAnalyses
    def fail(*args, **kwargs):
        raise OSError("simulated_index_preparation_failure")
    monkeypatch.setattr(SampleAnalyses, "prepare_mapping", fail)
    with multi_clients(tmp_path / "accounts", **resources(tmp_path)) as (_, alice, _, _):
        rid, run = objects(alice)
        mid = upload(alice, rid, tmp_path)
        s = sample(alice, rid, run, material_id=mid, mapping_input=DECLARATION)
        final, _ = wait_mapping(alice, rid, s["id"])
        assert final["status"] == "failed"
        history = request(alice, "GET", base(rid) + f"/samples/{s['id']}/analyses")["analyses"]
        assert [a["source_kind"] for a in history] == ["sample_qc", "sample_cell_cycle"]
        assert history[0]["availability"]["status"] == "available"
        assessment = request(alice, "GET", base(rid) + f"/assessments/{final['assessment_id']}")
        assert not assessment.get("analysis_id")
