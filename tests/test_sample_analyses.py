"""Sample analysis lineage through real QC executions and authenticated HTTP."""
import json
import pytest
from fastapi.testclient import TestClient
from account_support import create_test_app
from web_support import client, login, h5ad

from sample_analysis_support import call, setup_sample, qc, register

def test_two_actual_analyses_keep_results_and_exact_run_protocol_after_restart(client, tmp_path):
    rid, p, v, r, s = setup_sample(client, tmp_path)
    base = f"/api/researches/{rid}"
    from test_sample_workflow import wait_workflow
    wait_workflow(client, rid, s["id"])
    before = call(client, "GET", base + "/workbench")
    first_sid, first_receipt = qc(client, rid, s["material_id"])
    source = call(client, "GET", base + f"/samples/{s['id']}/analysis-sources?session_id={first_sid}")
    assert source["sources"][0]["receipt_id"] == first_receipt
    assert source["sources"][0]["eligible"] is True
    a1 = register(client, rid, s, first_sid, first_receipt)
    bound = call(client, "POST", base + f"/runs/{r['id']}/conversation", {})
    second_sid, second_receipt = qc(client, rid, s["material_id"], sid=bound["id"])
    a2 = register(client, rid, s, second_sid, second_receipt)
    assert a1["id"] != a2["id"]
    assert [a1["version"], a2["version"]] == [1, 2]
    assert a1["run_id"] == a2["run_id"] == r["id"]
    assert a1["protocol_version_id"] == a2["protocol_version_id"] == v["id"]
    assert a1["input_assets"][0]["sha256"] == a2["input_assets"][0]["sha256"]
    assert a1["tool"]["id"] == "P0-01"
    assert a1["results"] and a1["availability"]["status"] == "available"
    for result in a1["results"]:
        assert result["artifact"]["url"].startswith(f"/api/sessions/{first_sid}/artifacts/")
        assert client.get(result["artifact"]["url"]).status_code == 200
    # Replay uses exact receipt identity; execution names/checksums alone never deduplicate.
    assert register(client, rid, s, first_sid, first_receipt)["id"] == a1["id"]
    listing = call(client, "GET", base + f"/samples/{s['id']}/analyses")
    assert [a["id"] for a in listing["analyses"]] == [a1["id"], a2["id"]]
    assert call(client, "GET", base + "/workbench") == before
    service = client.app.state.service
    with TestClient(create_test_app(service.settings)) as restarted:
        login(restarted)
        assert call(restarted, "GET", base + f"/analyses/{a1['id']}") == a1
    serialized = json.dumps(a1)
    assert str(service.root) not in serialized
    assert "output_dir" not in serialized and '"path"' not in serialized
    # Later protocol drafts do not move this actual experiment or analysis.
    current = call(client, "GET", base + f"/protocols/{p['id']}")
    call(client, "POST", base + f"/protocols/{p['id']}/versions",
         {"expected_version": current["revision"], "based_on_version_id": v["id"], "changes": {"total_days": 35}})
    assert call(client, "GET", base + f"/analyses/{a1['id']}") == a1

@pytest.mark.parametrize("damage", ["receipt", "output", "invalidate", "delete", "input", "material"])
def test_unavailable_sources_preserve_history_but_never_claim_readable_results(client, tmp_path, damage):
    rid, _, _, _, s = setup_sample(client, tmp_path)
    sid, receipt = qc(client, rid, s["material_id"])
    a = register(client, rid, s, sid, receipt)
    service = client.app.state.service
    state = service.load(sid)
    if damage == "receipt":
        (service.directory(sid) / "receipts" / (receipt + ".json")).write_bytes(b"{}")
    elif damage == "output":
        from pathlib import Path
        source = state["_canonical_artifacts"][a["results"][0]["artifact"]["id"]]
        Path(source["path"]).write_bytes(b"broken")
    elif damage == "input":
        from pathlib import Path
        upload_id = next(iter(state["_uploads"]))
        (service.directory(sid) / "uploads" / (upload_id + ".h5ad")).write_bytes(b"broken")
    elif damage == "material":
        (service.researches.directory(rid) / "materials" / (s["material_id"] + ".bin")).write_bytes(b"broken")
    elif damage == "invalidate":
        state.setdefault("_invalidated_receipts", {})[receipt + ".json"] = "changed_input"
        service.sessions.save(state)
    else:
        call(client, "DELETE", f"/api/sessions/{sid}", {})
    historical = call(client, "GET", f"/api/researches/{rid}/analyses/{a['id']}")
    assert historical["id"] == a["id"] and historical["snapshot_sha256"] == a["snapshot_sha256"]
    assert historical["availability"]["status"] == "unavailable"
    assert all(result["artifact"] is None for result in historical["results"])

def test_wrong_sample_material_and_forged_results_are_rejected(client, tmp_path):
    rid, _, _, r, s = setup_sample(client, tmp_path)
    sid, receipt = qc(client, rid, s["material_id"])
    base = f"/api/researches/{rid}"
    # Another material ID, even identical bytes, is not this registered sample.
    response = client.post(base + "/uploads", files={"file": ("second.h5ad", h5ad(tmp_path))})
    other = call(client, "POST", base + f"/runs/{r['id']}/samples",
                 {"expected_version": 2, "day": 12, "assay": "scRNA-seq", "material_id": response.json()["id"]})
    response = client.post(base + f"/samples/{other['id']}/analyses",
                           json={"expected_version": 1, "session_id": sid, "receipt_id": receipt})
    assert response.status_code == 409
    assert response.json()["detail"] == "analysis_sample_input_mismatch"
    url = base + f"/samples/{s['id']}/analyses"
    payload = {"expected_version": 1, "session_id": sid, "receipt_id": receipt}
    call(client, "POST", url, {**payload, "results": [{"score": 1}]}, status=422)
    call(client, "POST", url, {**payload, "expected_version": 99}, status=409)
    assert call(client, "GET", url) == {"analyses": []}


def test_analysis_routes_enforce_research_and_session_ownership(client, tmp_path):
    from bridge.web.accounts import NOTICE_VERSION
    rid, _, _, _, s = setup_sample(client, tmp_path)
    sid = call(client, "POST", "/api/sessions", {"research_id": rid})["id"]
    second_rid = call(client, "POST", "/api/researches", {"name": "Other research"})["id"]
    second_sid = call(client, "POST", "/api/sessions", {"research_id": second_rid})["id"]
    base = f"/api/researches/{rid}"
    sources = base + f"/samples/{s['id']}/analysis-sources"
    call(client, "GET", sources + f"?session_id={second_sid}", status=404)
    cookies = dict(client.cookies)
    client.cookies.clear()
    call(client, "POST", "/api/register", {"username": "other-reader", "password": "strong synthetic password",
                                            "notice_version": NOTICE_VERSION})
    for method, path, body in (
        ("GET", sources + f"?session_id={sid}", None),
        ("GET", base + f"/samples/{s['id']}/analyses", None),
        ("GET", base + "/analyses/" + "a" * 32, None),
        ("POST", base + f"/samples/{s['id']}/analyses",
         {"expected_version": 1, "session_id": sid, "receipt_id": "a" * 32}),
    ):
        reply = call(client, method, path, body, status=404)
        assert "Synthetic" not in json.dumps(reply)
    client.cookies.clear()
    client.cookies.update(cookies)
    assert call(client, "GET", sources + f"?session_id={sid}") == {"sources": []}

def test_bad_analysis_store_fails_closed_without_overwriting_history(client, tmp_path):
    rid, _, _, _, s = setup_sample(client, tmp_path)
    service = client.app.state.service
    path = service.researches.directory(rid) / "analyses.json"
    path.write_text('{"schema_version":999,"analyses":{}}')
    call(client, "GET", f"/api/researches/{rid}/samples/{s['id']}/analyses", status=409)
    assert path.read_text() == '{"schema_version":999,"analyses":{}}'


def test_distinct_real_execution_parameters_are_pinned_and_duplicate_posts_are_atomic(client, tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    import hashlib
    from bridge.toolkit.contracts import ToolRun
    from bridge.web.sessions import uid, write_file
    rid, _, _, _, s = setup_sample(client, tmp_path)
    sid, receipt_id = qc(client, rid, s["material_id"])
    first = register(client, rid, s, sid, receipt_id)
    service = client.app.state.service
    state = service.load(sid)
    run = ToolRun.model_validate_json((service.directory(sid) / "receipts" / (receipt_id + ".json")).read_bytes())
    # Real deterministic tool, controlled new request; no model or result double.
    request = run.request.model_copy(update={
        "request_id": uid(), "random_seed": 17, "parameters": {"run_scrublet": False},
        "output_dir": service.directory(sid) / "runs" / "parameter-variant",
    })
    outcome = service.registry.run(request)
    assert outcome.execution_state.value == "succeeded"
    second_receipt = uid()
    raw = outcome.model_dump_json().encode()
    write_file(service.directory(sid) / "receipts" / (second_receipt + ".json"), raw)
    receipt = {"file": second_receipt + ".json", "sha256": hashlib.sha256(raw).hexdigest(),
               "tool_id": "P0-01", "state": "succeeded", "plan_id": uid(), "declaration_start": 1}
    state["_tool_runs"].append(receipt)
    service.inputs.register_outputs(state, outcome, receipt)
    service.artifacts.register(state, outcome)
    service.sessions.save(state)
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(pool.map(lambda _: register(client, rid, s, sid, second_receipt), range(2)))
    assert replies[0]["id"] == replies[1]["id"]
    assert replies[0]["version"] == 2
    assert replies[0]["random_seed"] == 17
    assert replies[0]["parameters"] == {"run_scrublet": False}
    assert replies[0]["parameters_sha256"] != first["parameters_sha256"]
    assert first["random_seed"] == 0 and first["parameters"] == {}
    assert call(client, "GET", f"/api/researches/{rid}/analyses/{first['id']}") == first
    assert len(call(client, "GET", f"/api/researches/{rid}/samples/{s['id']}/analyses")["analyses"]) == 2


def test_run_bound_conversation_cannot_register_under_another_experiment(client, tmp_path):
    rid, _, version, _, s = setup_sample(client, tmp_path)
    other_run = call(client, "POST", f"/api/researches/{rid}/runs", {
        "expected_version": 0, "protocol_version_id": version["id"], "name": "Other experiment", "state": "planned"})
    bound = call(client, "POST", f"/api/researches/{rid}/runs/{other_run['id']}/conversation", {})
    sid, receipt = qc(client, rid, s["material_id"], sid=bound["id"])
    response = client.post(f"/api/researches/{rid}/samples/{s['id']}/analyses",
                           json={"expected_version": s["revision"], "session_id": sid, "receipt_id": receipt})
    assert response.status_code == 409
    assert response.json()["detail"] == "analysis_sample_input_mismatch"


@pytest.mark.parametrize("unrelated_position", ["before", "after"])
@pytest.mark.parametrize("damage", ["missing", "hash_mismatch"])
def test_derived_analysis_depends_only_on_selected_qc(
        client, tmp_path, monkeypatch, unrelated_position, damage):
    import hashlib
    import sample_analysis_support
    from bridge.web.sessions import uid, write_file
    from test_qc_selection import _request

    synthetic_dir = tmp_path / "selected-input"
    synthetic_dir.mkdir()
    synthetic = _request(synthetic_dir, monkeypatch)
    monkeypatch.setattr(sample_analysis_support, "h5ad", lambda _: synthetic.assets[0].path.read_bytes())
    rid, _, _, experiment, sample = setup_sample(client, tmp_path)
    sid, unrelated_id = qc(client, rid, sample["material_id"])
    service = client.app.state.service
    state = service.load(sid)
    original, _ = service.inputs.producer_objects(state, state["_tool_runs"][0], "P0-01", set())

    def execute(request):
        outcome = service.registry.run(request)
        assert outcome.execution_state.value == "succeeded", outcome.reason_codes
        raw = outcome.model_dump_json().encode()
        receipt_id = uid()
        record = {**state["_tool_runs"][0], "file": receipt_id + ".json",
                  "sha256": hashlib.sha256(raw).hexdigest()}
        write_file(service.directory(sid) / "receipts" / record["file"], raw)
        state["_tool_runs"].append(record)
        service.inputs.register_outputs(state, outcome, record)
        service.artifacts.register(state, outcome)
        return outcome, receipt_id

    selection = original.request.model_copy(update={
        "request_id": uid(), "output_dir": service.directory(sid) / "runs" / "selected-qc",
        "parameters": synthetic.parameters, "measurement_spec_ref": synthetic.measurement_spec_ref,
        "assets": [original.request.assets[0].model_copy(update={"metadata": synthetic.assets[0].metadata})],
    })
    selected_qc, selected_id = execute(selection)
    profile = json.loads(next(a.path for a in selected_qc.artifacts if a.kind == "qc_profile_v2").read_bytes())
    view = profile["selected_data_view"]
    selected = next(a for a in selected_qc.artifacts if a.kind == "qc_selected_h5ad")
    if unrelated_position == "after":
        _, unrelated_id = execute(original.request.model_copy(update={
            "request_id": uid(), "output_dir": service.directory(sid) / "runs" / "later-unrelated-qc"}))
    # Run the registered QC tool on the real selected H5AD to exercise the public
    # Analysis reader with an authentic downstream receipt and display artifacts.
    _, target_id = execute(original.request.model_copy(update={
        "request_id": uid(), "output_dir": service.directory(sid) / "runs" / "derived-qc",
        "assets": [selection.assets[0].model_copy(update={
            "asset_id": selected.artifact_id, "path": selected.path, "checksum": selected.sha256,
            "metadata": {**selection.assets[0].metadata, "data_view_id": view["view_id"]}})],
    }))
    service.sessions.save(state)
    base = f"/api/researches/{rid}"
    sources_url = base + f"/samples/{sample['id']}/analysis-sources?session_id={sid}"
    def target_source():
        return next(r for r in call(client, "GET", sources_url)["sources"] if r["receipt_id"] == target_id)
    assert target_source()["eligible"] is True
    before = register(client, rid, sample, sid, target_id)
    detail_url = base + f"/analyses/{before['id']}"
    assert before["availability"]["status"] == "available"

    def damage_receipt(receipt_id):
        path = service.directory(sid) / "receipts" / (receipt_id + ".json")
        if damage == "missing":
            path.unlink()
        else:
            path.write_bytes(b"{}")

    damage_receipt(unrelated_id)
    assert target_source()["eligible"] is True
    assert call(client, "GET", detail_url) == before
    assert call(client, "GET", base + f"/samples/{sample['id']}/analyses") == {"analyses": [before]}
    for result in before["results"]:
        assert client.get(result["artifact"]["url"]).status_code == 200
    # A fresh registration must work too, not just replay the existing index.
    other = call(client, "POST", base + f"/runs/{experiment['id']}/samples", {
        "expected_version": 2, "day": 11, "assay": "scRNA-seq", "material_id": sample["material_id"]})
    assert register(client, rid, other, sid, target_id)["availability"]["status"] == "available"

    damage_receipt(selected_id)
    assert target_source()["eligible"] is False
    unavailable = call(client, "GET", detail_url)
    assert unavailable["snapshot_sha256"] == before["snapshot_sha256"]
    assert unavailable["availability"]["status"] == "unavailable"
    assert all(r["artifact"] is None for r in unavailable["results"])
    third = call(client, "POST", base + f"/runs/{experiment['id']}/samples", {
        "expected_version": 3, "day": 12, "assay": "scRNA-seq", "material_id": sample["material_id"]})
    call(client, "POST", base + f"/samples/{third['id']}/analyses", {
        "expected_version": 1, "session_id": sid, "receipt_id": target_id}, status=409)
