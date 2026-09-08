from __future__ import annotations

import hashlib
import json
import time
from types import SimpleNamespace

import pytest
httpx = pytest.importorskip("httpx")
pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from bridge.web.app import Settings, create_app
from bridge.web.provider import parse_action





def confirm_change(client, sid, state):
    change = state["pending_input_change"]
    response = client.post(f"/api/sessions/{sid}/input-change/confirm",
        json={"change_id": change["id"], "change_digest": change["digest"]})
    assert response.status_code == 200, response.json()
    return response.json()


def test_exact_source_change_is_pending_and_session_revision_bound(client, tmp_path):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    aid = client.post(url + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path))}).json()["uploads"][0]["id"]
    staged = client.post(url + "/inputs", json={"upload_id": aid, "source_family_id": "first"}).json()
    assert staged["input_review_required"] is True
    assert staged["uploads"][0].get("source_family_id") is None
    change = staged["pending_input_change"]
    assert change["changes"] == [{"field": "source_family_id", "before": None, "after": "first"}]
    other = new_session(client)["id"]
    payload = {"change_id": change["id"], "change_digest": change["digest"]}
    assert client.post(f"/api/sessions/{other}/input-change/confirm", json=payload).status_code == 409
    replaced = client.post(url + "/inputs", json={"upload_id": aid, "source_family_id": "second"}).json()
    assert client.post(url + "/input-change/confirm", json=payload).status_code == 409
    assert client.post(url + "/input-change/discard", json=payload).status_code == 409
    committed = confirm_change(client, sid, replaced)
    assert committed["uploads"][0]["source_family_id"] == "second"
    assert committed["input_review_required"] is False
    assert committed["plan"] is None
    assert client.post(url + "/input-change/confirm", json={"change_id": replaced["pending_input_change"]["id"],
        "change_digest": replaced["pending_input_change"]["digest"]}).status_code == 409


def test_review_inputs_blocks_plans_until_exact_confirmation_or_keep(client, tmp_path, monkeypatch):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    aid = client.post(url + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path))}).json()["uploads"][0]["id"]
    monkeypatch.setattr("bridge.web.app.converse", lambda *a: parse_action({"content": '{"action":"review_inputs","text":"Review the existing input panel."}'}))
    client.post(url + "/messages", json={"text": "Please correct the assay."})
    reviewed = settle(client, sid)
    assert reviewed["input_review_required"] is True
    assert client.post(url + "/prepare-analysis", json={"tool_id": "P0-02"}).json()["detail"] == "input_review_required"
    assert client.post(url + "/approve", json={"plan_id": "old", "plan_digest": "0"*64}).json()["detail"] == "input_review_required"
    staged = client.post(url + "/inputs", json={"upload_id": aid, "source_family_id": "private-source"}).json()
    assert client.post(url + "/input-review/keep", json={}).status_code == 409
    pending = staged["pending_input_change"]
    discarded = client.post(url + "/input-change/discard", json={"change_id": pending["id"], "change_digest": pending["digest"]}).json()
    assert discarded["input_review_required"] is True
    monkeypatch.setattr("bridge.web.app.converse", lambda *a: parse_action({"content": '{"action":"reply","text":"OK"}'}))
    client.post(url + "/messages", json={"text": "Thanks"})
    assert settle(client, sid)["input_review_required"] is True
    kept = client.post(url + "/input-review/keep", json={}).json()
    assert kept["input_review_required"] is False
    assert kept["pending_input_change"] is None and kept["plan"] is None


@pytest.mark.parametrize("late_error", [False, True])
def test_stop_returns_before_provider_settles_and_fences_late_result(client, monkeypatch, late_error):
    from threading import Event
    entered, release = Event(), Event()
    def blocked(*args):
        entered.set()
        assert release.wait(10)
        if late_error:
            raise RuntimeError("late provider error")
        return parse_action({"content": '{"action":"review_inputs","text":"late correction"}'})
    monkeypatch.setattr("bridge.web.app.converse", blocked)
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    client.post(url + "/messages", json={"text": "Discuss"})
    assert entered.wait(5)
    try:
        start = time.monotonic()
        stopped = client.post(url + "/stop", json={})
        assert time.monotonic() - start < 1
        assert stopped.status_code == 200
        assert stopped.json()["status"] == "stopping"
    finally:
        release.set()
    final = settle(client, sid)
    assert final["status"] == "idle" and final["error"] is None
    assert final["input_review_required"] is False
    assert not any(m["content"] == "late correction" for m in final["messages"])


def test_initial_qc_wait_is_provider_gated_and_needs_separate_approval(client, tmp_path, monkeypatch):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    aid = client.post(url + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path))}).json()["uploads"][0]["id"]
    monkeypatch.setattr("bridge.web.app.converse", lambda *a: parse_action({"content": '{"action":"reply","text":"Waiting."}'}))
    declare_counts(client, sid, aid, location="X")
    client.post(url + "/messages", json={"text": "scRNA-seq, X contains raw counts; please wait before preparing QC."})
    assert settle(client, sid)["plan"] is None
    monkeypatch.setattr("bridge.web.app.converse", lambda *a: parse_action({"content": json.dumps({
        "action": "prepare_qc", "upload_id": aid, "matrix_location": "X"})}))
    client.post(url + "/messages", json={"text": "scRNA-seq, use X raw counts for QC"})
    proposed = settle(client, sid)
    assert proposed["status"] == "awaiting_approval"
    assert client.app.state.service.load(sid)["_tool_runs"] == []
    stopped = client.post(url + "/stop", json={}).json()
    assert stopped["plan"]["status"] == "cancelled"
    assert client.post(url + "/approve", json={"plan_id": proposed["plan"]["id"], "plan_digest": proposed["plan"]["digest"]}).status_code == 409


@pytest.mark.parametrize("control", ["stop", "source", "asset"])
def test_stop_during_real_execution_retains_inflight_receipt(client, tmp_path, monkeypatch, control):
    from threading import Event
    from bridge.runners import ToolExecutionPipeline
    entered, release = Event(), Event()
    execute = ToolExecutionPipeline.execute_step
    def blocked(self, step):
        entered.set()
        assert release.wait(10)
        return execute(self, step)
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    aid = client.post(url + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path))}).json()["uploads"][0]["id"]
    monkeypatch.setattr("bridge.web.app.converse", lambda *a: parse_action({"content": json.dumps({
        "action": "prepare_qc", "upload_id": aid, "matrix_location": "X"})}))
    declare_counts(client, sid, aid, location="X")
    client.post(url + "/messages", json={"text": "scRNA-seq, use X raw counts for QC"})
    settle(client, sid)
    service = client.app.state.service
    state = service.load(sid)
    from bridge.domain import AnalysisPlan, CaseInputBundle
    from bridge.planner import PlanBuilder
    from bridge.toolkit.contracts import ToolRequest
    original = AnalysisPlan.model_validate(state["_plan"])
    request = ToolRequest.model_validate_json(original.steps[0].approved_request_json).model_copy(
        update={"request_id": "queued-qc-control-test"})
    batch = PlanBuilder().build(CaseInputBundle.model_validate(state["_bundle"]),
        output_root=service.directory(sid) / "runs",
        knowledge_snapshot_ref=original.knowledge_snapshot_ref, requests=[request])
    state["_plan"] = batch.model_dump(mode="json")
    state["plan"].update(id=batch.plan_id, digest=batch.approval_sha256(), steps=[
        {"id": step.step_id, "tool_id": step.tool_id, "label": "QC", "status": "pending", "reason": None}
        for step in batch.steps])
    service.save(state)
    plan = state["plan"]
    original_revision = state["_uploads"][aid]["declaration_start"]
    monkeypatch.setattr(ToolExecutionPipeline, "execute_step", blocked)
    client.post(url + "/approve", json={"plan_id": plan["id"], "plan_digest": plan["digest"]})
    assert entered.wait(5)
    try:
        start = time.monotonic()
        if control == "stop":
            stopped = client.post(url + "/stop", json={})
        elif control == "source":
            stopped = client.post(url + "/inputs", json={"upload_id": aid, "source_family_id": "private-source"})
        else:
            stopped = client.post(url + "/analysis-inputs/assets", json={
                "upload_id": aid, "assay": "snRNA-seq", "matrix_location": "X",
                "matrix_semantics": "raw_counts", "input_level": "count_ready", "metadata": {}})
        assert time.monotonic() - start < 1
        assert stopped.status_code == 200 and stopped.json()["status"] == "stopping"
        if control != "stop":
            confirm_change(client, sid, stopped.json())
        assert stopped.json()["plan"]["steps"][0]["status"] == "running"
    finally:
        release.set()
    final = settle(client, sid)
    assert final["status"] == "idle" and final["error"] is None
    state = client.app.state.service.load(sid)
    assert len(state["_tool_runs"]) == 1
    assert state["_tool_runs"][0]["state"] == "succeeded"
    assert final["plan"]["steps"][0]["status"] == "succeeded"
    assert final["plan"]["steps"][1]["status"] == "cancelled"
    assert state["_tool_runs"][0]["declaration_start"] == original_revision
    assert state["_uploads"][aid]["declaration_start"] == original_revision + (control == "asset")
    assert final["artifacts"]



def declare_counts(client, sid, aid, *, location="X", assay="scRNA-seq"):
    """Test setup uses the same explicit stage-and-confirm contract as the UI."""
    staged = client.post(f"/api/sessions/{sid}/analysis-inputs/assets", json={
        "upload_id": aid, "assay": assay, "matrix_location": location,
        "matrix_semantics": "raw_counts", "input_level": "count_ready", "metadata": {},
    })
    assert staged.status_code == 200, staged.json()
    return confirm_change(client, sid, staged.json())


def declare_source(client, sid, aid, source):
    staged = client.post(f"/api/sessions/{sid}/inputs",
        json={"upload_id": aid, "source_family_id": source})
    assert staged.status_code == 200, staged.json()
    return confirm_change(client, sid, staged.json())



def test_legacy_committed_bundle_does_not_reinterpret_new_chat(client, tmp_path):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    aid = client.post(url + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path))}).json()["uploads"][0]["id"]
    declare_counts(client, sid, aid, location="X")
    client.post(url + "/messages", json={"text": "scRNA-seq, use X raw counts for QC"})
    assert settle(client, sid)["status"] == "awaiting_approval"
    service = client.app.state.service
    state = service.load(sid)
    state["_asset_declarations"] = {}
    del state["_qc_declarations"]
    service.message(state, "user", "snRNA-seq")
    service.save(state)
    loaded = service.load(sid)
    assert service.assay(loaded, aid) == "scRNA-seq"
    assert loaded["input_review_required"]


@pytest.mark.parametrize("mismatch", [False, True])
def test_legacy_qc_receipt_proof_controls_review_without_rewriting_receipts(client, tmp_path, mismatch):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    aid = client.post(url + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path))}).json()["uploads"][0]["id"]
    declare_counts(client, sid, aid, location="X")
    client.post(url + "/messages", json={"text": "scRNA-seq, use X raw counts for QC"})
    plan = settle(client, sid)["plan"]
    client.post(url + "/approve", json={"plan_id": plan["id"], "plan_digest": plan["digest"]})
    settle(client, sid)
    service = client.app.state.service
    state = service.load(sid)
    receipts = list(state["_tool_runs"])
    state["_asset_declarations"] = {}
    del state["_qc_declarations"]
    state["_tool_runs"][0].pop("plan_id", None)
    if mismatch:
        state["_bundle"]["assets"][0]["assay"] = "snRNA-seq"
    service.save(state)
    loaded = service.load(sid)
    assert loaded["input_review_required"] is mismatch
    assert loaded["_tool_runs"] == receipts
    client.post(url + "/input-review/keep", json={})
    if mismatch:
        with pytest.raises(ValueError, match="qc_declaration_retracted"):
            service.qc_asset(service.load(sid), aid, register=False)
    else:
        assert service.qc_asset(service.load(sid), aid, register=False).assay == "scRNA-seq"



@pytest.mark.parametrize("metadata", [
    {"sample_id": "changed-sample"},
    {"capture_id": "changed-capture"},
    {"biological_unit_lineage": {"sample_id": "changed-unit"}},
    {"undeclared_fact": "changed"},
])
def test_legacy_metadata_mismatch_requires_review_and_fresh_qc(client, tmp_path, metadata):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    aid = client.post(url + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path))}).json()["uploads"][0]["id"]
    declare_counts(client, sid, aid, location="X")
    client.post(url + "/messages", json={"text": "scRNA-seq, use X raw counts for QC"})
    plan = settle(client, sid)["plan"]
    client.post(url + "/approve", json={"plan_id": plan["id"], "plan_digest": plan["digest"]})
    assert settle(client, sid)["plan"]["status"] == "completed"
    service = client.app.state.service
    state = service.load(sid)
    receipts = list(state["_tool_runs"])
    state["_asset_declarations"] = {}
    del state["_qc_declarations"]
    state["_bundle"]["assets"][0]["metadata"] = metadata
    service.save(state)
    migrated = service.load(sid)
    assert migrated["input_review_required"]
    assert migrated["_tool_runs"] == receipts
    client.post(url + "/input-review/keep", json={})
    with pytest.raises(ValueError, match="qc_declaration_retracted"):
        service.qc_asset(service.load(sid), aid, register=False)


@pytest.mark.parametrize("tampered", [False, True])
def test_legacy_verified_qc_enrichment_and_source_only_edit_preserve_qc(client, tmp_path, tampered):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    aid = client.post(url + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path))}).json()["uploads"][0]["id"]
    declare_counts(client, sid, aid, location="X")
    client.post(url + "/messages", json={"text": "scRNA-seq, use X raw counts for QC"})
    plan = settle(client, sid)["plan"]
    client.post(url + "/approve", json={"plan_id": plan["id"], "plan_digest": plan["digest"]})
    assert settle(client, sid)["plan"]["status"] == "completed"
    declare_source(client, sid, aid, "original-source")
    service = client.app.state.service
    state = service.load(sid)
    enriched = service.qc_asset(state, aid).model_dump(mode="json")
    if tampered:
        enriched["metadata"]["qc_profile_ref"] = "unproven-profile"
    state["_bundle"]["assets"] = [enriched]
    state["_asset_declarations"] = {}
    del state["_qc_declarations"]
    service.save(state)
    migrated = service.load(sid)
    assert migrated["input_review_required"] is tampered
    if not tampered:
        declare_source(client, sid, aid, "changed-source-only")
        current = service.load(sid)
        assert current["input_review_required"] is False
        assert service.qc_asset(current, aid).metadata["source_family_id"] == "changed-source-only"



def test_legacy_qc_enrichment_cannot_erase_original_caller_reserved_metadata(client, tmp_path):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    aid = client.post(url + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path))}).json()["uploads"][0]["id"]
    staged = client.post(url + "/analysis-inputs/assets", json={
        "upload_id": aid, "assay": "scRNA-seq", "matrix_location": "X",
        "matrix_semantics": "raw_counts", "input_level": "count_ready",
        "metadata": {"data_view_id": "caller-before-qc"},
    })
    assert staged.status_code == 200, staged.json()
    confirm_change(client, sid, staged.json())
    client.post(url + "/messages", json={"text": "scRNA-seq, use X raw counts for QC"})
    plan = settle(client, sid)["plan"]
    client.post(url + "/approve", json={"plan_id": plan["id"], "plan_digest": plan["digest"]})
    assert settle(client, sid)["plan"]["status"] == "completed"
    declare_source(client, sid, aid, "original-source")
    service = client.app.state.service
    state = service.load(sid)
    assert service.qc_asset(state, aid, register=False).metadata["data_view_id"] == "caller-before-qc"
    enriched = service.qc_asset(state, aid).model_dump(mode="json")
    assert enriched["metadata"]["data_view_id"] != "caller-before-qc"
    state["_bundle"]["assets"] = [enriched]
    state["_asset_declarations"] = {}
    del state["_qc_declarations"]
    service.save(state)
    assert service.load(sid)["input_review_required"]
    client.post(url + "/input-review/keep", json={})
    with pytest.raises(ValueError, match="qc_declaration_retracted"):
        service.qc_asset(service.load(sid), aid, register=False)


def test_exact_stop_command_cannot_bypass_conversation_bound(client):
    sid = new_session(client)["id"]
    service = client.app.state.service
    state = service.load(sid)
    state["messages"] *= 100
    service.save(state)
    assert client.post(f"/api/sessions/{sid}/messages", json={"text": "stop"}).status_code == 400
    assert client.post(f"/api/sessions/{sid}/stop", json={}).status_code == 200


def test_asset_edit_stays_private_pending_then_invalidates_qc_only_on_confirm(client, tmp_path, monkeypatch):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    aid = client.post(url + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path))}).json()["uploads"][0]["id"]
    declare_counts(client, sid, aid, location="X")
    client.post(url + "/messages", json={"text": "scRNA-seq, use X raw counts for QC"})
    plan = settle(client, sid)["plan"]
    client.post(url + "/approve", json={"plan_id": plan["id"], "plan_digest": plan["digest"]})
    assert settle(client, sid)["plan"]["status"] == "completed"
    service = client.app.state.service
    before = service.load(sid)
    staged = client.post(url + "/analysis-inputs/assets", json={
        "upload_id": aid, "assay": "snRNA-seq", "matrix_location": "X",
        "matrix_semantics": "raw_counts", "input_level": "count_ready",
        "metadata": {"sample_id": "private-sample-correction"},
    }).json()
    assert staged["input_review_required"]
    assert staged["pending_input_change"]["changes"] == [
        {"field": "assay", "before": "scRNA-seq", "after": "snRNA-seq"},
        {"field": "metadata", "before": {}, "after": {"sample_id": "private-sample-correction"}},
    ]
    pending = service.load(sid)
    assert pending["_qc_declarations"] == before["_qc_declarations"]
    service.qc_asset(pending, aid, register=False)
    captured = []
    def reply(settings, messages, context):
        captured.append(context)
        return parse_action({"content": '{"action":"reply","text":"Use the panel."}'})
    monkeypatch.setattr("bridge.web.app.converse", reply)
    client.post(url + "/messages", json={"text": "Tell me how to review"})
    assert settle(client, sid)["input_review_required"]
    assert "private-sample-correction" not in json.dumps(captured)
    assert staged["pending_input_change"]["digest"] not in json.dumps(captured)
    confirm_change(client, sid, staged)
    committed = service.load(sid)
    assert committed["_asset_declarations"][aid]["assay"] == "snRNA-seq"
    assert committed["_asset_declarations"][aid]["metadata"] == {"sample_id": "private-sample-correction"}
    assert committed["_tool_runs"] == before["_tool_runs"]
    assert committed["artifacts"] == before["artifacts"]
    with pytest.raises(ValueError, match="qc_declaration_retracted"):
        service.qc_asset(committed, aid, register=False)


def test_input_revision_and_digest_changes_fail_closed(client, tmp_path):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    aid = client.post(url + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path))}).json()["uploads"][0]["id"]
    staged = client.post(url + "/inputs", json={"upload_id": aid, "source_family_id": "first"}).json()
    change = staged["pending_input_change"]
    assert client.post(url + "/input-change/confirm", json={"change_id": change["id"], "change_digest": "0"*64}).status_code == 409
    assert client.post(url + "/analysis-inputs", json={
        "tool_id": "P0-12", "mode_id": "not_provided", "asset_ids": [], "object_inputs": [], "measurement_spec_ref": None}).status_code == 200
    assert client.post(url + "/input-change/confirm", json={"change_id": change["id"], "change_digest": change["digest"]}).status_code == 409
    assert client.get(url).json()["input_review_required"]
    assert client.get(url).json()["uploads"][0].get("source_family_id") is None



def test_other_session_planning_cannot_block_stop_on_catalog_lock(client, tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event, Thread
    from bridge.web.app import CATALOG_LOCK
    entered, release = Event(), Event()
    def tool_catalog_owner():
        with CATALOG_LOCK:
            entered.set()
            assert release.wait(10)
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    aid = client.post(url + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path))}).json()["uploads"][0]["id"]
    confirm_change(client, sid, client.post(url + "/analysis-inputs/assets", json={
        "upload_id": aid, "assay": "scRNA-seq", "matrix_location": "X",
        "matrix_semantics": "raw_counts", "input_level": "count_ready", "metadata": {}}).json())
    client.post(url + "/analysis-inputs", json={
        "tool_id": "P0-12", "mode_id": "not_provided", "asset_ids": [], "object_inputs": [], "measurement_spec_ref": None})
    holder = Thread(target=tool_catalog_owner)
    holder.start()
    assert entered.wait(5)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(client.post, url + "/prepare-analysis", json={"tool_id": "P0-12"})
        try:
            response = future.result(timeout=1)
            assert response.status_code == 409
            assert response.json()["detail"] == "worker_busy"
            assert client.post(url + "/stop", json={}).status_code == 200
        finally:
            release.set()
            holder.join()



def test_confirmed_asset_metadata_is_used_by_provider_qc_plan(client, tmp_path, monkeypatch):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    aid = client.post(url + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path))}).json()["uploads"][0]["id"]
    metadata = {"sample_id": "declared-sample", "capture_id": "declared-capture"}
    staged = client.post(url + "/analysis-inputs/assets", json={
        "upload_id": aid, "assay": "snRNA-seq", "matrix_location": "X",
        "matrix_semantics": "raw_counts", "input_level": "count_ready", "metadata": metadata}).json()
    confirm_change(client, sid, staged)
    def prepare(settings, messages, context):
        assert "declared-sample" not in json.dumps(context)
        return parse_action({"content": json.dumps({"action": "prepare_qc", "upload_id": aid, "matrix_location": "X"})})
    monkeypatch.setattr("bridge.web.app.converse", prepare)
    client.post(url + "/messages", json={"text": "Prepare QC for the confirmed input"})
    assert settle(client, sid)["status"] == "awaiting_approval"
    state = client.app.state.service.load(sid)
    assert "未声明 sample/capture" not in state["plan"]["summary"]
    request = json.loads(state["_plan"]["steps"][0]["approved_request_json"])
    assert request["assets"][0]["assay"] == "snRNA-seq"
    assert request["assets"][0]["metadata"] == metadata
    assert state["_tool_runs"] == []



def test_restart_settles_stopping_step_without_reviving_work(client):
    sid = new_session(client)["id"]
    service = client.app.state.service
    state = service.load(sid)
    state.update(status="stopping", input_review_required=True, _chat_input_review=True,
        plan={"id": "stopped", "status": "cancelled", "steps": [
            {"id": "done", "status": "succeeded", "reason": None},
            {"id": "in-flight", "status": "running", "reason": None},
            {"id": "queued", "status": "cancelled", "reason": "stopped"}]})
    service.save(state)
    restarted = create_app(service.settings).state.service
    try:
        loaded = restarted.load(sid)
        assert loaded["status"] == "failed" and loaded["error"] == "interrupted"
        assert loaded["input_review_required"]
        assert loaded["plan"]["steps"][0]["status"] == "succeeded"
        assert loaded["plan"]["steps"][1]["status"] == "cancelled"
        assert loaded["_tool_runs"] == []
    finally:
        restarted.pool.shutdown(wait=True)


def test_prepare_analysis_accepts_registered_tool_actions():
    for tool_id in (f"P0-{index:02}" for index in range(1, 13)):
        assert parse_action({"content": json.dumps({"action": "prepare_analysis", "tool_id": tool_id})}).tool_id == tool_id
    for tool_id in ("P0-00", "P0-13", "/private/tool"):
        with pytest.raises(ValueError):
            parse_action({"content": json.dumps({"action": "prepare_analysis", "tool_id": tool_id})})


def test_private_source_input_is_bound_to_registered_upload(client, tmp_path):
    sid = new_session(client)["id"]
    value = client.post(f"/api/sessions/{sid}/uploads",
        files={"file": ("synthetic.h5ad", h5ad(tmp_path, layer=True))}).json()
    aid = value["uploads"][0]["id"]
    url = f"/api/sessions/{sid}/inputs"
    saved = client.post(url, json={"upload_id": aid, "source_family_id": "source-family:unit-test"})
    assert saved.status_code == 200
    committed = confirm_change(client, sid, saved.json())
    assert committed["uploads"][0]["source_family_id"] == "source-family:unit-test"
    assert client.post(url, json={"upload_id": "0"*32, "source_family_id": "test"}).status_code == 404
    for bad in (" ", "/private/file", "a"*161):
        assert client.post(url, json={"upload_id": aid, "source_family_id": bad}).status_code == 422


@pytest.mark.parametrize("declaration", ["没有移植数据，请记录未提供 graft 数据", "No graft data, please record not provided"])
def test_real_qc_then_no_graft_has_new_approval_and_canonical_receipts(client, tmp_path, monkeypatch, declaration):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    client.post(url + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path, layer=True))})
    declare_counts(client, sid, client.get(url).json()["uploads"][0]["id"], location="layers/counts")
    client.post(url + "/messages", json={"text": "scRNA-seq，使用 counts 层进行 QC"})
    first = settle(client, sid)["plan"]
    client.post(url + "/approve", json={"plan_id": first["id"], "plan_digest": first["digest"]})
    done = settle(client, sid)
    service = client.app.state.service
    assert service.load(sid)["_tool_runs"]
    monkeypatch.setattr("bridge.web.app.converse", lambda *args: parse_action({"content": '{"action":"prepare_analysis","tool_id":"P0-12"}'}))
    client.post(url + "/messages", json={"text": declaration})
    proposed = settle(client, sid)
    assert proposed["status"] == "awaiting_approval", proposed
    assert proposed["plan_history"][0]["id"] == first["id"]
    assert proposed["artifacts"] == done["artifacts"]
    state = service.load(sid)
    request = json.loads(state["_plan"]["steps"][0]["approved_request_json"])
    assert request["assets"] == [] and request["object_inputs"] == []
    assert client.post(url + "/approve", json={"plan_id": first["id"], "plan_digest": first["digest"]}).status_code == 409
    second = proposed["plan"]
    client.post(url + "/approve", json={"plan_id": second["id"], "plan_digest": second["digest"]})
    result = settle(client, sid)
    assert result["plan"]["status"] == "completed", result
    assert len(service.load(sid)["_tool_runs"]) == 2


@pytest.mark.parametrize("retraction", [
    "No graft data. This is not scRNA-seq.",
    "没有移植数据。这个不是 scRNA-seq。",
    "No graft data. X is not raw counts.",
    "没有样本表。这个不是 scRNA-seq。",
    "没有批次表。counts 层不是原始计数。",
    "No product definition. Cancel analysis.",
    "Do not continue the analysis.",
    "不要继续分析。",
    "No sample tables, or raw counts.",
    "X is normalized, not raw.",
])
def test_provider_correction_pauses_before_neutral_cell_state_request(
        client, tmp_path, monkeypatch, retraction):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    uploaded = client.post(url + "/uploads", files={
        "file": ("synthetic.h5ad", h5ad(tmp_path, layer=True)),
    }).json()
    aid = uploaded["uploads"][0]["id"]
    declare_counts(client, sid, aid, location="layers/counts")
    client.post(url + "/messages", json={
        "text": "scRNA-seq，使用 counts 层进行 QC",
    })
    first = settle(client, sid)["plan"]
    client.post(url + "/approve", json={
        "plan_id": first["id"], "plan_digest": first["digest"],
    })
    assert settle(client, sid)["plan"]["status"] == "completed"
    declare_source(client, sid, aid, "source-family:unit-test")
    monkeypatch.setattr(client.app.state.service, "cell_state_config_reasons", lambda: [])
    before = client.app.state.service.load(sid)
    monkeypatch.setattr("bridge.web.app.converse", lambda *args: parse_action({
        "content": '{"action":"review_inputs","text":"Please review the input panel."}',
    }))
    client.post(url + "/messages", json={"text": retraction})
    assert settle(client, sid)["input_review_required"] is True
    monkeypatch.setattr("bridge.web.app.converse", lambda *args: parse_action({
        "content": '{"action":"prepare_analysis","tool_id":"P0-02"}',
    }))
    client.post(url + "/messages", json={"text": "Continue cell-state analysis."})
    value = settle(client, sid)
    assert value["plan"]["status"] == "completed"
    assert value["error"] == "input_review_required"
    after = client.app.state.service.load(sid)
    assert after["_uploads"] == before["_uploads"]
    assert after["_tool_runs"] == before["_tool_runs"]


def test_completed_qc_plan_complaint_preserves_declaration_for_p002(
        client, tmp_path, monkeypatch):
    from dataclasses import replace
    from test_cell_state import _build_snapshot, _write_query

    service = client.app.state.service
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    query = _write_query(tmp_path / "query.h5ad")
    uploaded = client.post(
        url + "/uploads",
        files={"file": ("synthetic.h5ad", query.read_bytes())},
    ).json()
    aid = uploaded["uploads"][0]["id"]
    declare_counts(client, sid, aid, location="X")
    client.post(
        url + "/messages",
        json={"text": "scRNA-seq，X 是原始计数，进行 QC"},
    )
    qc_plan = settle(client, sid)["plan"]
    client.post(
        url + "/approve",
        json={"plan_id": qc_plan["id"], "plan_digest": qc_plan["digest"]},
    )
    assert settle(client, sid)["plan"]["status"] == "completed"

    _build_snapshot(tmp_path, monkeypatch)
    service.settings = replace(
        service.settings,
        cell_state_measurement_spec_ref="CELLSTATE-scRNA-shadow-v0.1",
    )
    declare_source(client, sid, aid, "source-family:unit-test")
    baseline = service.load(sid)
    declaration_start = baseline["_uploads"][aid]["declaration_start"]
    receipts = list(baseline["_tool_runs"])
    service.qc_asset(baseline, aid, register=False)
    monkeypatch.setattr(
        "bridge.web.app.converse",
        lambda *args: parse_action(
            {
                "content": json.dumps(
                    {"action": "prepare_analysis", "tool_id": "P0-02"}
                )
            }
        ),
    )

    for statement in [
        "页面没有出现新的 P0-02 待确认计划，只有刚才已完成的 QC。"
        "请实际创建 P0-02 分析计划，让我在界面点击确认；"
        "不要只用文字说明已经创建。",
        "QC 已完成，但我没有独立的生物学重复。"
        "请保留为未知并创建 P0-02 待确认计划。",
        "当前文件已经恢复原始细胞条码和来源样本标签，但培养批次、混样和"
        "独立重复关系仍不能确认。请按可核验的技术分组描述结果，把独立重复"
        "保留为推测，不要生成已确认的生物学声明。现在还能继续做哪些分析？",
    ]:
        client.post(url + "/messages", json={"text": statement})
        proposed = settle(client, sid)
        assert proposed["status"] == "awaiting_approval", proposed
        assert proposed["error"] is None
        assert proposed["plan"]["steps"][0]["tool_id"] == "P0-02"
        assert proposed["plan"]["steps"][0]["status"] == "pending"
        current = service.load(sid)
        assert current["_uploads"][aid]["declaration_start"] == declaration_start
        assert current["_tool_runs"] == receipts
        service.qc_asset(current, aid, register=False)

    monkeypatch.setattr("bridge.web.app.converse", lambda *args: parse_action({
        "content": '{"action":"review_inputs","text":"请检查输入面板。"}',
    }))
    client.post(
        url + "/messages",
        json={
            "text": "页面没有出现新的 P0-02 待确认计划；"
            "不要继续使用 X 作为原始计数，请取消 QC。"
        },
    )
    fenced = settle(client, sid)
    assert fenced["input_review_required"] is True
    assert service.load(sid)["_uploads"][aid]["declaration_start"] == declaration_start


@pytest.mark.parametrize("statement", [
    "目前我没有额外的样本或批次表，也没有提供产品定义、状态角色和实验方案。请保持这些事实未知，告诉我哪些分析现在确实能运行，哪些需要我补什么材料。不要把空分数当成运行失败。",
    "没有样本表，也没有批次表。",
    "I have no additional sample or batch tables. No product definition, state roles or experimental protocol.",
    "No sample metadata. X still contains raw counts.",
    "QC is complete, not all biological replicates are confirmed.",
    "没有移植数据，请记录未提供 graft 数据",
    "No graft data, please record not provided",
])
def test_unrelated_missing_metadata_preserves_declared_assay_and_canonical_qc(
        client, tmp_path, monkeypatch, statement):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    uploaded = client.post(url + "/uploads", files={
        "file": ("synthetic.h5ad", h5ad(tmp_path, layer=True)),
    }).json()
    aid = uploaded["uploads"][0]["id"]
    declare_counts(client, sid, aid, location="layers/counts")
    client.post(url + "/messages", json={"text": "scRNA-seq，使用 counts 层进行 QC"})
    plan = settle(client, sid)["plan"]
    client.post(url + "/approve", json={"plan_id": plan["id"], "plan_digest": plan["digest"]})
    done = settle(client, sid)
    assert done["plan"]["status"] == "completed"
    declare_source(client, sid, aid, "test-source")
    service = client.app.state.service
    monkeypatch.setattr(service, "cell_state_config_reasons", lambda: [])
    before = service.load(sid)
    assert next(item for item in service.capabilities(before) if item["tool_id"] == "P0-02")["state"] == "ready"
    asset = service.qc_asset(before, aid, register=False)
    monkeypatch.setattr("bridge.web.app.converse", lambda *args: parse_action({
        "content": '{"action":"reply","text":"Please supply missing inputs privately."}',
    }))

    client.post(url + "/messages", json={"text": statement})
    after = settle(client, sid)
    state = service.load(sid)
    assert state["_uploads"][aid]["declaration_start"] == before["_uploads"][aid]["declaration_start"]
    assert service.assay(state, aid) == "scRNA-seq"
    assert service.qc_asset(state, aid, register=False) == asset
    assert after["plan"] == done["plan"]
    assert after["artifacts"] == done["artifacts"]
    assert state["_tool_runs"] == before["_tool_runs"]
    assert next(item for item in after["capabilities"] if item["tool_id"] == "P0-02")["state"] == "ready"


@pytest.mark.parametrize("statement", [
    "No sample table; scRNA-seq, X contains raw counts",
    "没有批次表，这是 scRNA-seq，使用 counts 层进行 QC",
    "没有产品定义，这是 scRNA-seq，使用 counts 层？",
])
def test_unrelated_negative_message_cannot_form_new_qc_declarations(client, statement):
    service = client.app.state.service
    state = {
        "messages": [{"role": "user", "content": statement}],
        "_uploads": {"test": {"locations": ["X", "layers/counts"], "declaration_start": 0}},
    }
    assert service.declaration(state, "test") is None
    assert service.assay(state, "test") is None


def test_no_graft_cannot_be_inferred_by_provider(client, tmp_path, monkeypatch):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    client.post(url + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path))})
    monkeypatch.setattr("bridge.web.app.converse", lambda *args: parse_action({"content": '{"action":"prepare_analysis","tool_id":"P0-12"}'}))
    client.post(url + "/messages", json={"text": "What is graft assessment?"})
    value = settle(client, sid)
    assert value["plan"] is None
    assert value["error"] == "no_graft_declaration_required"




def test_selected_p002_reuses_verified_qc_without_redeclaring_chat_asset(
        client, tmp_path, monkeypatch):
    from dataclasses import replace
    from test_cell_state import _build_snapshot, _write_query
    from bridge.tool_packages.p0_02_cell_state.qc import validate_upstream_qc_bundle
    from bridge.toolkit.contracts import InputAsset

    service = client.app.state.service
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    data = _write_query(tmp_path / "query.h5ad").read_bytes()
    uploaded = client.post(
        url + "/uploads",
        files={"file": ("synthetic.h5ad", data)},
    ).json()
    aid = uploaded["uploads"][0]["id"]
    declare_counts(client, sid, aid, location="X")
    client.post(
        url + "/messages",
        json={"text": "scRNA-seq，X 是原始计数，进行 QC"},
    )
    qc_proposal = settle(client, sid)["plan"]
    client.post(
        url + "/approve",
        json={
            "plan_id": qc_proposal["id"],
            "plan_digest": qc_proposal["digest"],
        },
    )
    assert settle(client, sid)["plan"]["status"] == "completed"

    _build_snapshot(tmp_path, monkeypatch)
    service.settings = replace(
        service.settings,
        cell_state_measurement_spec_ref="CELLSTATE-scRNA-shadow-v0.1",
    )
    declare_source(client, sid, aid, "source-family:selected-unit-test")
    # Simulate a saved pre-panel session: only its exact QC declaration remains.
    legacy = service.load(sid)
    legacy["_asset_declarations"] = {}
    service.save(legacy)
    before = service.load(sid)
    assert aid not in before["_asset_declarations"]
    before_declarations = json.loads(json.dumps({
        "asset": before["_asset_declarations"],
        "qc": before["_qc_declarations"],
        "uploads": before["_uploads"],
    }))
    before_runs = list(before["_tool_runs"])
    catalog_path = service.root / "qc-catalog.json"
    before_catalog = catalog_path.read_bytes() if catalog_path.exists() else None

    selection = {
        "tool_id": "P0-02",
        "mode_id": None,
        "asset_ids": [aid],
        "object_inputs": [],
        "measurement_spec_ref": "CELLSTATE-scRNA-shadow-v0.1",
    }
    saved = client.post(url + "/analysis-inputs", json=selection)
    assert saved.status_code == 200, saved.json()
    ready = next(
        item
        for item in saved.json()["capabilities"]
        if item["tool_id"] == "P0-02"
    )
    assert ready["state"] == "ready"
    after_readiness = service.load(sid)
    assert after_readiness["_asset_declarations"] == before_declarations["asset"]
    assert after_readiness["_qc_declarations"] == before_declarations["qc"]
    assert after_readiness["_uploads"] == before_declarations["uploads"]
    assert after_readiness["_tool_runs"] == before_runs
    assert (
        catalog_path.read_bytes() if catalog_path.exists() else None
    ) == before_catalog

    proposed = client.post(
        url + "/prepare-analysis",
        json={"tool_id": "P0-02"},
    )
    assert proposed.status_code == 200, proposed.json()
    proposed = proposed.json()
    assert proposed["status"] == "awaiting_approval"
    assert proposed["plan"]["steps"][0]["status"] == "pending"
    assert client.post(
        url + "/approve",
        json={
            "plan_id": qc_proposal["id"],
            "plan_digest": qc_proposal["digest"],
        },
    ).status_code == 409
    planned = service.load(sid)
    request = json.loads(planned["_plan"]["steps"][0]["approved_request_json"])
    asset = request["assets"][0]
    assert request["measurement_spec_ref"] == "CELLSTATE-scRNA-shadow-v0.1"
    assert asset["asset_id"] == aid
    assert asset["path"].endswith("/uploads/" + aid + ".h5ad")
    assert asset["checksum"] == hashlib.sha256(data).hexdigest()
    assert asset["assay"] == "scRNA-seq"
    assert asset["matrix_location"] == "X"
    assert asset["matrix_semantics"] == "raw_counts"
    assert asset["input_level"] == "count_ready"
    assert asset["metadata"]["source_family_id"] == "source-family:selected-unit-test"
    assert asset["metadata"]["parent_asset_sha256"] == asset["checksum"]
    with service.qc_catalog():
        upstream = validate_upstream_qc_bundle(InputAsset.model_validate(asset))
    assert upstream.profile.profile_id == asset["metadata"]["qc_profile_ref"]
    assert (
        upstream.profile_v2.selected_data_view.view_id
        == asset["metadata"]["data_view_id"]
    )

    old_analysis = proposed["plan"]
    source_edit = client.post(
        url + "/inputs",
        json={
            "upload_id": aid,
            "source_family_id": "source-family:selected-unit-test-2",
        },
    )
    assert source_edit.status_code == 200, source_edit.json()
    assert source_edit.json()["plan"]["status"] == "cancelled"
    confirm_change(client, sid, source_edit.json())
    assert client.post(
        url + "/approve",
        json={
            "plan_id": old_analysis["id"],
            "plan_digest": old_analysis["digest"],
        },
    ).status_code == 409
    after_source = service.load(sid)
    assert after_source["_tool_runs"] == before_runs
    assert after_source["_qc_declarations"] == before_declarations["qc"]
    reproposed = client.post(
        url + "/prepare-analysis",
        json={"tool_id": "P0-02"},
    )
    assert reproposed.status_code == 200, reproposed.json()
    assert reproposed.json()["plan"]["digest"] != old_analysis["digest"]
    rebound = service.load(sid)
    rebound_request = json.loads(
        rebound["_plan"]["steps"][0]["approved_request_json"]
    )
    assert (
        rebound_request["assets"][0]["metadata"]["source_family_id"]
        == "source-family:selected-unit-test-2"
    )
    assert rebound["_tool_runs"] == before_runs
    assert rebound["_qc_declarations"] == before_declarations["qc"]


def test_real_qc_cell_state_stage_binds_canonical_data_and_new_approval(client, tmp_path, monkeypatch):
    from dataclasses import replace
    from test_cell_state import _build_snapshot, _write_query
    from bridge.tool_packages.p0_02_cell_state.qc import validate_upstream_qc_bundle
    from bridge.toolkit.contracts import InputAsset
    import hashlib
    import os

    service = client.app.state.service
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    data = _write_query(tmp_path / "query.h5ad").read_bytes()
    uploaded = client.post(url + "/uploads", files={"file": ("synthetic.h5ad", data)}).json()
    aid = uploaded["uploads"][0]["id"]
    declare_counts(client, sid, aid, location="X")
    client.post(url + "/messages", json={"text": "scRNA-seq，X 是原始计数，进行 QC"})
    first = settle(client, sid)["plan"]
    client.post(url + "/approve", json={"plan_id": first["id"], "plan_digest": first["digest"]})
    assert settle(client, sid)["plan"]["status"] == "completed"
    captured = []
    def action(settings, messages, context):
        captured.append(context)
        return parse_action({"content": '{"action":"prepare_analysis","tool_id":"P0-02"}'})
    monkeypatch.setattr("bridge.web.app.converse", action)
    def propose():
        client.post(url + "/messages", json={"text": "继续细胞状态分析"})
        return settle(client, sid)
    assert propose()["error"] == "measurement_spec_not_configured"
    service.settings = replace(service.settings, cell_state_measurement_spec_ref="CELLSTATE-scRNA-shadow-v0.1")
    monkeypatch.delenv("BRIDGE_REFERENCE_ROOT", raising=False)
    assert propose()["error"] == "reference_root_not_configured"
    _build_snapshot(tmp_path, monkeypatch)
    assert propose()["error"] == "source_family_id_required"
    declare_source(client, sid, aid, "PRIVATE-UNIT-TEST-SOURCE")
    proposed = propose()
    assert proposed["status"] == "awaiting_approval", proposed
    assert proposed["plan"]["steps"][0]["status"] == "pending", proposed
    assert "PRIVATE-UNIT-TEST-SOURCE" not in json.dumps(captured)
    state = service.load(sid)
    request = json.loads(state["_plan"]["steps"][0]["approved_request_json"])
    asset = request["assets"][0]
    assert asset["checksum"] == hashlib.sha256(data).hexdigest()
    assert asset["input_level"] == "count_ready"
    assert asset["matrix_location"] == "X" and asset["matrix_semantics"] == "raw_counts"
    assert asset["metadata"]["parent_asset_sha256"] == asset["checksum"]
    assert ".display-redacted" not in json.dumps(request)
    monkeypatch.setenv("BRIDGE_QC_PROFILE_CATALOG", "original-catalog-sentinel")
    with service.qc_catalog():
        upstream = validate_upstream_qc_bundle(InputAsset.model_validate(asset))
        assert upstream.profile.profile_id == asset["metadata"]["qc_profile_ref"]
        assert upstream.profile_v2.selected_data_view.view_id == asset["metadata"]["data_view_id"]
    assert os.environ["BRIDGE_QC_PROFILE_CATALOG"] == "original-catalog-sentinel"
    with pytest.raises(RuntimeError), service.qc_catalog():
        raise RuntimeError("intentional")
    assert os.environ["BRIDGE_QC_PROFILE_CATALOG"] == "original-catalog-sentinel"
    # Fact edits invalidate only mutable proposals, and historical approvals survive.
    second = proposed["plan"]
    edited = client.post(url + "/inputs", json={"upload_id": aid, "source_family_id": "PRIVATE-UNIT-TEST-SOURCE-2"}).json()
    assert edited["plan"]["status"] == "cancelled" and edited["plan_history"][0]["id"] == first["id"]
    confirm_change(client, sid, edited)
    assert client.post(url + "/approve", json={"plan_id": second["id"], "plan_digest": second["digest"]}).status_code == 409
    third = propose()["plan"]
    assert third["digest"] != second["digest"]
    client.post(url + "/approve", json={"plan_id": third["id"], "plan_digest": third["digest"]})
    done = settle(client, sid)
    assert done["plan"]["status"] == "completed", done
    assert any(item["tool_id"] == "P0-02" for item in done["artifacts"])
    assert os.environ["BRIDGE_QC_PROFILE_CATALOG"] == "original-catalog-sentinel"
    # A provider review pauses future analysis without rewriting completed evidence.
    monkeypatch.setattr("bridge.web.app.converse", lambda *args: parse_action({
        "content": '{"action":"review_inputs","text":"Review the assay in the input panel."}',
    }))
    client.post(url + "/messages", json={"text": "This is not scRNA-seq"})
    reviewed = settle(client, sid)
    assert reviewed["input_review_required"]
    assert reviewed["plan"]["status"] == "completed"
    assert client.post(url + "/input-review/keep", json={}).status_code == 200
    monkeypatch.setattr("bridge.web.app.converse", lambda *args: parse_action({
        "content": '{"action":"prepare_analysis","tool_id":"P0-02"}',
    }))
    # Downstream construction must not fall back to display copies after deletion.
    upstream.profile_path.unlink()
    assert propose()["error"] == "qc_artifacts_missing"

    capability = next(item for item in client.get(url).json()["capabilities"] if item["tool_id"] == "P0-02")
    assert capability["state"] == "needs_input"
    assert "qc_artifacts_missing" in capability["reason_codes"]



def test_provider_context_reports_ready_stage_and_bounded_tool_history_without_private_values(
        client, tmp_path, monkeypatch):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    uploaded = client.post(url + "/uploads", files={
        "file": ("private-source-name.h5ad", h5ad(tmp_path, layer=True)),
    }).json()
    aid = uploaded["uploads"][0]["id"]
    declare_counts(client, sid, aid, location="layers/counts")
    client.post(url + "/messages", json={
        "text": "scRNA-seq，使用 counts 层进行 QC",
    })
    plan = settle(client, sid)["plan"]
    client.post(url + "/approve", json={
        "plan_id": plan["id"], "plan_digest": plan["digest"],
    })
    assert settle(client, sid)["plan"]["status"] == "completed"
    declare_source(client, sid, aid, "PRIVATE-ACTUAL-SOURCE-ID")
    service = client.app.state.service
    monkeypatch.setattr(service, "cell_state_config_reasons", lambda: [])
    captured = []
    def action(settings, messages, context):
        captured.append(context)
        return parse_action({"content": '{"action":"reply","text":"bounded"}'})
    monkeypatch.setattr("bridge.web.app.converse", action)

    client.post(url + "/messages", json={
        "text": "来源信息已在数据表单填写。请继续细胞状态分析。",
    })
    settle(client, sid)

    assert len(captured) == 1
    context = captured[0]
    assert set(context) == {
        "status", "upload_ids", "plan_status", "capabilities",
        "tool_execution_history", "results_sent_to_model", "input_contracts", "input_review_required",
        "intake_context",
    }
    assert context["intake_context"] == [{
        "upload_id": aid, "state": "needs_confirmation",
        "missing_fields": ["product_name", "product_family", "target_cell_type",
                           "target_stage", "sampling_context", "independent_cultures"],
    }]
    assert context["status"] == "idle"
    assert context["upload_ids"] == [aid]
    assert context["plan_status"] == "completed"
    assert context["tool_execution_history"] == [{
        "tool_id": "P0-01", "state": "succeeded",
    }]
    p002 = next(item for item in context["capabilities"] if item["tool_id"] == "P0-02")
    assert p002["state"] == "ready" and p002["reason_codes"] == []
    contracts = context["input_contracts"]
    assert set(contracts) == {f"P0-{index:02}" for index in range(1, 13)}
    assert contracts["P0-01"] == []
    assert contracts["P0-07"] == [
        {"mode_id": "legacy_comparison", "required_roles": [
            "comparison_stability_spec", "comparison_case_manifest", "product_evidence_bundle",
        ]},
        {"mode_id": "method_runtime", "required_roles": [
            "comparison_stability_spec", "comparison_case_manifest", "product_evidence_bundle",
            "comparison_method_spec", "comparison_method_input",
        ]},
    ]
    assert {mode["mode_id"] for mode in contracts["P0-05"]} == {
        "legacy_aggregation", "method_runtime", "hard_count_accounting",
    }
    assert contracts["P0-12"][0] == {"mode_id": "not_provided", "required_roles": []}
    for modes in contracts.values():
        for mode in modes:
            assert set(mode) == {"mode_id", "required_roles"}
            assert all(isinstance(role, str) for role in mode["required_roles"])
    assert len(json.dumps(contracts)) < 16000
    p007 = next(item for item in context["capabilities"] if item["tool_id"] == "P0-07")
    assert p007["state"] == "needs_input"
    assert p007["reason_codes"] == ["input_mode_required"]
    assert p007["mode_id"] is None
    serialized = json.dumps(context)
    for private_value in (
        "PRIVATE-ACTUAL-SOURCE-ID", "private-source-name.h5ad", str(tmp_path),
        service.load(sid)["_uploads"][aid]["sha256"], "private-cell-a",
    ):
        assert private_value not in serialized


def test_legacy_sessions_default_history_and_unconnected_capabilities(client):
    sid = new_session(client)["id"]
    service = client.app.state.service
    state = service.load(sid)
    for key in ("plan_history", "_plan_history", "_tool_runs"):
        state.pop(key)
    service.save(state)
    value = client.get(f"/api/sessions/{sid}").json()
    assert value["plan_history"] == []
    caps = {item["tool_id"]: item for item in value["capabilities"]}
    assert len(caps) == 12
    assert caps["P0-05"]["state"] == "needs_input"
    assert "measurement_spec_not_configured" in caps["P0-02"]["reason_codes"]


def test_partial_run_keeps_real_state_and_artifacts(client, tmp_path, monkeypatch):
    from bridge.runners import ToolExecutionPipeline
    from bridge.toolkit.contracts import ExecutionState
    original = ToolExecutionPipeline.execute_step
    def partial(self, step):
        outcome = original(self, step)
        return outcome.model_copy(update={"execution_state": ExecutionState.PARTIAL})
    monkeypatch.setattr(ToolExecutionPipeline, "execute_step", partial)
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    client.post(url + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path))})
    declare_counts(client, sid, client.get(url).json()["uploads"][0]["id"], location="X")
    client.post(url + "/messages", json={"text": "scRNA-seq，X 是原始计数，进行 QC"})
    plan = settle(client, sid)["plan"]
    client.post(url + "/approve", json={"plan_id": plan["id"], "plan_digest": plan["digest"]})
    done = settle(client, sid)
    assert done["plan"]["status"] == "partial"
    assert done["plan"]["steps"][0]["status"] == "partial"
    assert done["artifacts"]




@pytest.mark.parametrize("text", ["No graft data, do not run analysis", "没有移植数据，不要分析", "假设没有移植数据", "If there is no graft data"])
def test_no_graft_negative_or_hypothetical_intent_never_plans(client, tmp_path, monkeypatch, text):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    client.post(url + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path))})
    declare_counts(client, sid, client.get(url).json()["uploads"][0]["id"], location="X")
    client.post(url + "/messages", json={"text": "scRNA-seq，X 是原始计数，进行 QC"})
    assert settle(client, sid)["status"] == "awaiting_approval"
    monkeypatch.setattr("bridge.web.app.converse", lambda *args: parse_action({"content": '{"action":"prepare_analysis","tool_id":"P0-12"}'}))
    client.post(url + "/messages", json={"text": text})
    value = settle(client, sid)
    assert value["plan"] is None
    assert value["error"] == "no_graft_declaration_required"



def test_restart_preserves_completed_plan_during_interrupted_conversation(client):
    sid = new_session(client)["id"]
    store = client.app.state.service
    state = store.load(sid)
    state["status"] = "thinking"
    state["plan"] = {"id": "completed", "status": "completed", "steps": []}
    store.save(state)
    other = create_app(store.settings)
    other.state.service.pool.shutdown()
    assert other.state.service.load(sid)["plan"]["status"] == "completed"


def test_provider_accepts_only_complete_typed_json_actions():
    qc = {"action": "prepare_qc", "upload_id": "a" * 32, "matrix_location": "X"}
    assert parse_action({"content": json.dumps(qc)}).action == "prepare_qc"
    assert parse_action({"content": '{"action":"reply","text":"Please upload a file."}'}).text == "Please upload a file."
    assert parse_action({"content": '{"action":"prepare_analysis","tool_id":"P0-02"}'}).tool_id == "P0-02"
    invalid = [
        {"content": "Please upload a file."},
        {"content": '<｜DSML｜function_calls><｜DSML｜invoke name="prepare_analysis">P0-02</｜DSML｜invoke>'},
        {"content": '{"action":"reply"}'},
        {"content": '{"action":"prepare_qc","upload_id":"a"}'},
        {"content": '{"action":"prepare_analysis"}'},
        {"content": '{"action":"shell","command":"ls"}'},
        {"content": '{"action":"prepare_qc","upload_id":"abc","matrix_location":"../../secret"}'},
        {"content": json.dumps(qc), "tool_calls": [{"function": {"name": "prepare_qc", "arguments": "{}"}}]},
    ]
    for message in invalid:
        with pytest.raises(ValueError):
            parse_action(message)


@pytest.mark.parametrize(("message", "expected"), [
    (
        {"content": "", "tool_calls": [{
            "type": "function",
            "function": {"name": "reply", "arguments": '{"text":"Ready."}'},
        }]},
        {"action": "reply", "text": "Ready."},
    ),
    (
        {"content": " \n\t", "tool_calls": [{
            "type": "function",
            "function": {"name": "review_inputs", "arguments": '{"text":"Review the panel."}'},
        }]},
        {"action": "review_inputs", "text": "Review the panel."},
    ),
    (
        {"content": None, "tool_calls": [{
            "type": "function",
            "function": {
                "name": "prepare_qc",
                "arguments": '{"upload_id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","matrix_location":"layers/counts"}',
            },
        }]},
        {
            "action": "prepare_qc",
            "upload_id": "a" * 32,
            "matrix_location": "layers/counts",
        },
    ),
    (
        {"content": "", "tool_calls": [{
            "type": "function",
            "function": {"name": "prepare_analysis", "arguments": '{"tool_id":"P0-02"}'},
        }]},
        {"action": "prepare_analysis", "tool_id": "P0-02"},
    ),
])
def test_provider_accepts_each_complete_native_action(message, expected):
    action = parse_action(message, protocol="deepseek_tools")
    assert action.model_dump(exclude_none=True) == expected


@pytest.mark.parametrize(("message", "error"), [
    ({"content": ""}, "invalid_model_tool_call_count"),
    ({"content": "plain prose"}, "unexpected_model_content"),
    (
        {"content": "", "tool_calls": [
            {
                "type": "function",
                "function": {"name": "reply", "arguments": '{"text":"one"}'},
            },
            {
                "type": "function",
                "function": {"name": "reply", "arguments": '{"text":"two"}'},
            },
        ]},
        "invalid_model_tool_call_count",
    ),
    (
        {"content": "outside", "tool_calls": [{
            "type": "function",
            "function": {"name": "reply", "arguments": '{"text":"inside"}'},
        }]},
        "unexpected_model_content",
    ),
    (
        {"content": "", "tool_calls": [{
            "type": "function",
            "function": {"name": "shell", "arguments": '{"command":"ls"}'},
        }]},
        "unknown_model_action",
    ),
    (
        {"content": "", "tool_calls": [{
            "type": "function",
            "function": {"name": "reply", "arguments": {"text": "not a string"}},
        }]},
        "invalid_model_action_arguments",
    ),
    (
        {"content": "", "tool_calls": [{
            "type": "function",
            "function": {"name": "reply", "arguments": '"not an object"'},
        }]},
        "invalid_model_action_arguments",
    ),
    (
        {"content": "", "tool_calls": [{
            "type": "function",
            "function": {
                "name": "prepare_analysis",
                "arguments": '{"action":"prepare_analysis","tool_id":"P0-02"}',
            },
        }]},
        "invalid_model_action_fields",
    ),
    (
        {"content": "", "tool_calls": [{
            "type": "function",
            "function": {"name": "prepare_analysis", "arguments": '{"tool_id":"P0-02","text":null}'},
        }]},
        "invalid_model_action_fields",
    ),
    (
        {"content": "", "tool_calls": [{
            "type": "function",
            "function": {"name": "prepare_analysis", "arguments": '{"tool_id":"P0-13"}'},
        }]},
        "invalid_model_action",
    ),
    (
        {"content": "", "tool_calls": [{
            "type": "function",
            "function": {"name": "reply", "arguments": '{}'},
        }]},
        "invalid_model_action_fields",
    ),
    (
        {"content": "", "tool_calls": [{
            "type": "function",
            "function": {"name": "reply", "arguments": "{"},
        }]},
        "invalid_model_action_arguments",
    ),
    (
        {"content": "", "tool_calls": [{
            "type": "custom",
            "function": {"name": "reply", "arguments": '{"text":"Ready."}'},
        }]},
        "invalid_model_tool_call",
    ),
])
def test_provider_rejects_invalid_native_action_shapes_with_stable_codes(message, error):
    with pytest.raises(ValueError, match=f"^{error}$"):
        parse_action(message, protocol="deepseek_tools")


def test_provider_rejects_unknown_action_protocol():
    with pytest.raises(ValueError, match="^invalid_model_action_protocol$"):
        parse_action({"content": '{"action":"reply","text":"Ready."}'}, protocol="automatic")


def test_settings_default_and_native_action_protocol_validation(tmp_path):
    values = dict(
        storage_root=tmp_path / "private",
        token="t" * 32,
        model_base_url="https://provider.invalid/v1",
        model="test-model",
        model_api_key="private-key",
        origin="http://testserver",
    )
    assert getattr(Settings(**values), "model_action_protocol", None) == "json"
    assert Settings(**values, model_action_protocol="deepseek_tools").model_action_protocol == "deepseek_tools"
    with pytest.raises(ValueError, match="^invalid_server_configuration$"):
        Settings(**values, model_action_protocol="automatic")


@pytest.mark.parametrize(("configured", "expected"), [
    (None, "json"),
    ("json", "json"),
    ("deepseek_tools", "deepseek_tools"),
])
def test_main_reads_only_explicit_action_protocol_startup_values(
    tmp_path, monkeypatch, configured, expected
):
    from bridge.web import __main__ as web_main
    environment = {
        "BRIDGE_WEB_STORAGE": str(tmp_path / "startup-private"),
        "BRIDGE_WEB_TOKEN": "t" * 32,
        "BRIDGE_WEB_MODEL_BASE_URL": "https://provider.invalid/v1",
        "BRIDGE_WEB_MODEL": "test-model",
        "BRIDGE_WEB_MODEL_API_KEY": "private-key",
        "BRIDGE_WEB_ORIGIN": "http://127.0.0.1:8765",
        "BRIDGE_WEB_SHARE_RESULT_SUMMARIES": "0",
    }
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("BRIDGE_WEB_TRUSTED_ANCESTORS", raising=False)
    if configured is None:
        monkeypatch.delenv("BRIDGE_WEB_MODEL_ACTION_PROTOCOL", raising=False)
    else:
        monkeypatch.setenv("BRIDGE_WEB_MODEL_ACTION_PROTOCOL", configured)
    captured = {}
    monkeypatch.setattr(
        web_main.uvicorn,
        "run",
        lambda app, **kwargs: captured.update(app=app),
    )

    web_main.main()

    service = captured["app"].state.service
    try:
        assert service.settings.model_action_protocol == expected
    finally:
        service.pool.shutdown()


def test_main_rejects_unknown_action_protocol_startup_value(tmp_path, monkeypatch):
    from bridge.web import __main__ as web_main
    environment = {
        "BRIDGE_WEB_STORAGE": str(tmp_path / "startup-private"),
        "BRIDGE_WEB_TOKEN": "t" * 32,
        "BRIDGE_WEB_MODEL_BASE_URL": "https://provider.invalid/v1",
        "BRIDGE_WEB_MODEL": "test-model",
        "BRIDGE_WEB_MODEL_API_KEY": "private-key",
        "BRIDGE_WEB_MODEL_ACTION_PROTOCOL": "automatic",
        "BRIDGE_WEB_SHARE_RESULT_SUMMARIES": "0",
    }
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("BRIDGE_WEB_TRUSTED_ANCESTORS", raising=False)
    monkeypatch.setattr(
        web_main.uvicorn,
        "run",
        lambda *args, **kwargs: pytest.fail("server started"),
    )

    with pytest.raises(ValueError, match="^invalid_server_configuration$"):
        web_main.main()


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Replace only the external provider HTTP boundary. Plans and tools stay real.
    original_client = httpx.Client
    def provider_response(request):
        payload = json.loads(request.content)
        context = json.loads(payload["messages"][0]["content"].split("Safe execution context: ", 1)[1])
        text = payload["messages"][-1]["content"]
        action = {"action": "reply", "text": "Please clarify the next input."}
        if context["upload_ids"] and any(word in text for word in ("counts", "计数", "scRNA-seq", "snRNA-seq")):
            history = " ".join(item["content"] for item in payload["messages"][1:])
            action = {"action": "prepare_qc", "upload_id": context["upload_ids"][-1],
                      "matrix_location": "layers/counts" if ("counts 层" in history or "layers/counts" in history) else "X"}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(action)}}]})
    monkeypatch.setattr("bridge.web.provider.httpx.Client",
        lambda **kwargs: original_client(**({"transport": httpx.MockTransport(provider_response)} | kwargs)))
    config = Settings(storage_root=tmp_path / "private", token="t" * 32,
                      model_base_url="https://provider.invalid/v1", model="test-model",
                      model_api_key="private-key", origin="http://testserver")
    app = create_app(config)
    with TestClient(app) as client:
        client.headers["Origin"] = "http://testserver"
        yield client


def login(client):
    assert client.post("/api/login", json={"token": "t" * 32}).status_code == 200


def new_session(client):
    login(client)
    return client.post("/api/sessions").json()


def settle(client, sid, timeout=90):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        value = client.get(f"/api/sessions/{sid}").json()
        if value["status"] not in {"thinking", "running", "stopping"}:
            return value
        time.sleep(.05)
    pytest.fail("worker did not finish")


def h5ad(tmp_path, *, layer=False):
    import anndata as ad
    import numpy as np
    import pandas as pd
    from scipy import sparse
    data = ad.AnnData(sparse.csr_matrix(np.array([[1, 2, 0], [2, 0, 1], [0, 3, 1], [2, 1, 1]], dtype=np.int64)),
                      obs=pd.DataFrame(index=["private-cell-a", "b", "c", "d"]),
                      var=pd.DataFrame(index=["MT-ND1", "SOX2", "FOXA2"]))
    if layer:
        data.layers["counts"] = data.X.copy()
    path = tmp_path / "synthetic.h5ad"
    data.write_h5ad(path)
    return path.read_bytes()


def registered_artifact(client, sid, name, data):
    from bridge.storage.private_paths import ensure_private_directory
    from bridge.toolkit.contracts import ArtifactManifest
    from bridge.web.app import write_file

    service = client.app.state.service
    source_root = service.directory(sid) / "runs" / "preview-test"
    ensure_private_directory(source_root)
    source = source_root / name
    write_file(source, data)
    sha256 = hashlib.sha256(data).hexdigest()
    state = service.load(sid)
    state["_tool_runs"].append({"file": "preview-test-receipt.json", "sha256": "0" * 64})
    service.register_artifacts(
        state,
        SimpleNamespace(
            artifacts=[ArtifactManifest(
                artifact_id="preview-test:" + name,
                kind="table",
                path=source,
                media_type="application/octet-stream",
                sha256=sha256,
            )],
            request=SimpleNamespace(tool_id="P0-test"),
        ),
    )
    return service.load(sid)["artifacts"][-1]


def parquet_bytes(tmp_path, name, columns, **write_options):
    import pyarrow as pa
    import pyarrow.parquet as pq

    path = tmp_path / name
    pq.write_table(pa.table(columns), path, **write_options)
    return path.read_bytes()


def test_auth_origin_logout_and_path_boundaries(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/api/sessions").status_code == 401
    assert client.post("/api/login", json={"token": "wrong"}).status_code == 401
    assert client.post("/api/login", json={"token": "t" * 32}, headers={"Origin": "https://evil.invalid"}).status_code == 403
    login(client)
    cookie = client.cookies.get("bridge_session")
    assert cookie and cookie != "t" * 32
    assert client.get("/api/sessions/" + "a" * 32).status_code == 404
    assert client.get("/api/sessions/%2e%2e%2fsecret").status_code == 404
    assert client.post("/api/logout").status_code == 200
    assert client.get("/api/sessions").status_code == 401


def test_upload_validation_and_private_state(client, tmp_path):
    session = new_session(client)
    url = f"/api/sessions/{session['id']}/uploads"
    assert client.post(url, files={"file": ("../bad.h5ad", b"not hdf5")}).status_code == 400
    response = client.post(url, files={"file": ("private.h5ad", h5ad(tmp_path, layer=True))})
    assert response.status_code == 200
    value = response.json()
    assert value["uploads"][0]["kind"] == "h5ad"
    assert str(tmp_path) not in response.text
    assert "private-cell-a" not in response.text
    assert value["plan"] is None
    intake = client.get(f"/api/sessions/{session['id']}/intake",
        params={"upload_id": value["uploads"][0]["id"]})
    assert intake.status_code == 200
    assert intake.json()["observed"]["matrix_locations"] == ["X", "layers/counts"]
    assert intake.json()["facts"]["count_semantics"] == "unknown"
    assert client.get(f"/api/sessions/{session['id']}/artifacts/" + "a" * 32).status_code == 404


def test_model_context_and_real_http_error(client, monkeypatch):
    sid = new_session(client)["id"]
    def response(request):
        payload = json.loads(request.content)
        assert "tools" not in payload and "tool_choice" not in payload
        assert "thinking" not in payload
        assert payload["response_format"] == {"type": "json_object"}
        assert payload["max_tokens"] == 1800
        assert [item["role"] for item in payload["messages"]].count("system") == 1
        assert payload["messages"][0]["role"] == "system"
        system = payload["messages"][0]["content"]
        assert system.startswith("Every conversational answer uses the JSON reply envelope.")
        assert "Safe execution context:" in system
        assert 'A capability with state "ready" means' in system
        assert "do not ask for its private source value in chat" in system
        assert "use prepare_analysis instead of asking the user to reconfirm QC" in system
        assert (
            "You cannot inspect raw uploaded biological data. Execution success alone "
            "is not biological evidence."
        ) in system
        assert (
            "Result evidence may contain E0 for aggregate P0-01 QC, E1 for P0-02 "
            "cell-state evidence, or both."
        ) in system
        assert "Interpret QC only from an available E0 summary or qc_summary." in system
        assert (
            "E0 and E1 may bind different historical runs; never claim they share "
            "an upload, selected view or denominator unless the evidence says so."
        ) in system
        assert "The context does not certify individual QC metrics" not in system
        assert (
            "When results_sent_to_model is false, describe only the reported tool "
            "ID/execution state and ask the user to inspect tool-owned results."
        ) in system
        assert (
            "When results_sent_to_model is true, use the supplied result_summary to "
            "answer the requested result question; do not replace its numerical "
            "evidence with execution-status language."
        ) in system
        assert (
            "Use the supplied counts and fractions when requested. Do not invent "
            "standard errors, confidence intervals or scores absent from result_summary."
        ) in system
        assert (
            "For explanation-only requests about results, missing inputs or next "
            "steps, use reply, not prepare_qc or prepare_analysis."
        ) in system
        assert (
            "Earlier positive input declarations establish prerequisites, not a "
            "request for a new plan."
        ) in system
        assert (
            "Do not prepare a plan when the user asks to wait, stop, or not prepare "
            "a new plan."
        ) in system
        assert "You receive conversation and minimal execution status only" not in system
        assert (
            "Never infer biological findings from execution success. Ask the user "
            "to inspect tool-owned results."
        ) not in system
        assert (
            "Describe completed execution history only at the reported tool ID and "
            "execution-state level."
        ) not in system
        assert payload["messages"][-1] == {"role": "user", "content": "What can you do?"}
        assert "private-key" not in json.dumps(payload)
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"action":"reply","text":"I can help prepare QC."}'}}]})
    original = httpx.Client
    monkeypatch.setattr("bridge.web.provider.httpx.Client", lambda **kwargs: original(transport=httpx.MockTransport(response), **kwargs))
    client.post(f"/api/sessions/{sid}/messages", json={"text": "What can you do?"})
    value = settle(client, sid)
    assert value["messages"][-1]["content"] == "I can help prepare QC."
    monkeypatch.setattr("bridge.web.provider.httpx.Client", lambda **kwargs: original(transport=httpx.MockTransport(lambda request: httpx.Response(502, text="/private/provider/key")), **kwargs))
    client.post(f"/api/sessions/{sid}/messages", json={"text": "Continue"})
    failed = settle(client, sid)
    assert failed["status"] == "failed"
    assert failed["error"] == "provider_unavailable"
    assert "/private/provider/key" not in json.dumps(failed)


def test_native_protocol_wire_and_service_proposal_never_executes(
    tmp_path, monkeypatch
):
    captured = {}
    def response(request):
        payload = json.loads(request.content)
        captured["payload"] = payload
        return httpx.Response(200, json={"choices": [{"message": {
            "content": "",
            "tool_calls": [{
                "id": "call-bounded",
                "type": "function",
                "function": {
                    "name": "prepare_analysis",
                    "arguments": '{"tool_id":"P0-12"}',
                },
            }],
        }}]})

    original = httpx.Client
    monkeypatch.setattr(
        "bridge.web.provider.httpx.Client",
        lambda **kwargs: original(
            transport=httpx.MockTransport(response),
            **kwargs,
        ),
    )
    config = Settings(
        storage_root=tmp_path / "native-private",
        token="t" * 32,
        model_base_url="https://provider.invalid/v1",
        model="test-model",
        model_api_key="private-key",
        origin="http://testserver",
        model_action_protocol="deepseek_tools",
    )
    app = create_app(config)
    with TestClient(app) as native_client:
        native_client.headers["Origin"] = "http://testserver"
        sid = new_session(native_client)["id"]
        url = f"/api/sessions/{sid}"
        uploaded = native_client.post(
            url + "/uploads",
            files={"file": ("synthetic.h5ad", h5ad(tmp_path, layer=True))},
        ).json()
        upload_id = uploaded["uploads"][0]["id"]
        staged = native_client.post(url + "/analysis-inputs/assets", json={
            "upload_id": upload_id,
            "assay": "scRNA-seq",
            "matrix_location": "layers/counts",
            "matrix_semantics": "raw_counts",
            "input_level": "count_ready",
            "metadata": {},
        }).json()
        confirm_change(native_client, sid, staged)
        selected = native_client.post(url + "/analysis-inputs", json={
            "tool_id": "P0-12",
            "mode_id": "not_provided",
            "asset_ids": [],
            "object_inputs": [],
            "measurement_spec_ref": None,
        })
        assert selected.status_code == 200, selected.json()

        native_client.post(
            url + "/messages",
            json={"text": "Prepare the selected no-graft analysis."},
        )
        proposed = settle(native_client, sid)
        assert proposed["status"] == "awaiting_approval", proposed
        assert proposed["plan"]["steps"][0]["tool_id"] == "P0-12"
        state = native_client.app.state.service.load(sid)
        assert state["_tool_runs"] == []

    payload = captured["payload"]
    assert "response_format" not in payload
    assert payload["tool_choice"] == "required"
    assert payload["thinking"] == {"type": "disabled"}
    assert payload["max_tokens"] == 1800
    tools = {
        item["function"]["name"]: item["function"]["parameters"]
        for item in payload["tools"]
    }
    assert list(tools) == [
        "reply",
        "review_inputs",
        "prepare_qc",
        "propose_intake",
        "prepare_analysis",
        "ask_user_input",
        "draft_scientific_inputs",
        "propose_scientific_inputs",
    ]
    assert tools["reply"] == {
        "type": "object",
        "properties": {"text": {"type": "string", "maxLength": 12000}},
        "required": ["text"],
        "additionalProperties": False,
    }
    assert tools["review_inputs"] == {
        "type": "object",
        "properties": {"text": {"type": "string", "maxLength": 12000}},
        "required": ["text"],
        "additionalProperties": False,
    }
    assert tools["prepare_qc"] == {
        "type": "object",
        "properties": {
            "upload_id": {"type": "string", "pattern": "^[a-f0-9]{32}$"},
            "matrix_location": {
                "type": "string",
                "pattern": "^(X|layers/[A-Za-z0-9_.-]{1,80})$",
            },
        },
        "required": ["upload_id", "matrix_location"],
        "additionalProperties": False,
    }
    assert tools["prepare_analysis"] == {
        "type": "object",
        "properties": {
            "tool_id": {
                "type": "string",
                "pattern": "^P0-(0[1-9]|1[0-2])$",
            },
        },
        "required": ["tool_id"],
        "additionalProperties": False,
    }
    system = payload["messages"][0]["content"]
    assert system.startswith(
        "You are BRIDGE, a research-only cell-therapy transcriptomic evidence assistant."
    )
    assert "Every conversational answer uses the JSON reply envelope." not in system
    assert "requires exactly one named function" in system
    assert "without an action key" in system
    assert "When results_sent_to_model is true" in system
    assert "ordinary chat cannot clear review" in system
    assert (
        "You cannot inspect raw uploaded biological data. Execution success alone "
        "is not biological evidence."
    ) in system
    assert (
        "Result evidence may contain E0 for aggregate P0-01 QC, E1 for P0-02 "
        "cell-state evidence, or both."
    ) in system
    assert "Interpret QC only from an available E0 summary or qc_summary." in system
    assert (
        "E0 and E1 may bind different historical runs; never claim they share "
        "an upload, selected view or denominator unless the evidence says so."
    ) in system
    assert "The context does not certify individual QC metrics" not in system
    assert (
        "When results_sent_to_model is false, describe only the reported tool "
        "ID/execution state and ask the user to inspect tool-owned results."
    ) in system
    assert (
        "When results_sent_to_model is true, use the supplied result_summary to "
        "answer the requested result question; do not replace its numerical "
        "evidence with execution-status language."
    ) in system
    assert (
        "Use the supplied counts and fractions when requested. Do not invent "
        "standard errors, confidence intervals or scores absent from result_summary."
    ) in system
    assert (
        "For explanation-only requests about results, missing inputs or next "
        "steps, use reply, not prepare_qc or prepare_analysis."
    ) in system
    assert (
        "Earlier positive input declarations establish prerequisites, not a "
        "request for a new plan."
    ) in system
    assert (
        "Do not prepare a plan when the user asks to wait, stop, or not prepare "
        "a new plan."
    ) in system
    assert "You receive conversation and minimal execution status only" not in system
    assert (
        "Never infer biological findings from execution success. Ask the user "
        "to inspect tool-owned results."
    ) not in system
    assert (
        "Describe completed execution history only at the reported tool ID and "
        "execution-state level."
    ) not in system
    assert payload["messages"][-1] == {
        "role": "user",
        "content": "Prepare the selected no-graft analysis.",
    }


def test_real_qc_exact_approval_and_artifacts(client, tmp_path):
    sid = new_session(client)["id"]
    client.post(f"/api/sessions/{sid}/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path, layer=True))})
    client.post(f"/api/sessions/{sid}/messages", json={"text": "是，使用 counts 层进行 QC"})
    value = settle(client, sid)
    assert value["status"] == "idle", value
    assert value["plan"] is None
    assert "实验类型" in value["messages"][-1]["content"]
    declare_counts(client, sid, value["uploads"][0]["id"], location="layers/counts")
    client.post(f"/api/sessions/{sid}/messages", json={"text": "这是 scRNA-seq 数据"})
    value = settle(client, sid)
    assert value["status"] == "awaiting_approval", value
    plan = value["plan"]
    assert client.post(f"/api/sessions/{sid}/approve", json={"plan_id": plan["id"], "plan_digest": "0" * 64}).status_code == 409
    assert client.post(f"/api/sessions/{sid}/approve", json={"plan_id": plan["id"], "plan_digest": plan["digest"]}).status_code == 200
    done = settle(client, sid)
    assert done["status"] == "idle", done
    assert done["plan"]["status"] == "completed"
    assert done["artifacts"]
    assert any(item["kind"] == "figure" for item in done["artifacts"])
    evidence = [item for item in done["artifacts"] if item["kind"] == "evidence"]
    assert evidence and all(item["name"].endswith(".display-redacted.json") for item in evidence)
    assert all("source_sha256" in client.app.state.service.load(sid)["_artifacts"][item["id"]] for item in evidence)
    assert str(tmp_path) not in json.dumps(done)
    for artifact in done["artifacts"]:
        response = client.get(artifact["url"])
        assert response.status_code == 200
        assert response.headers["x-content-type-options"] == "nosniff"
    assert client.post(f"/api/sessions/{sid}/approve", json={"plan_id": plan["id"], "plan_digest": plan["digest"]}).status_code == 409


def test_registered_parquet_preview_is_literal_bounded_and_preserves_download(client, tmp_path):
    sid = new_session(client)["id"]
    original = parquet_bytes(
        tmp_path,
        "literal.parquet",
        {"metric": ["observed", "missing"], "value": [7, None]},
    )
    artifact = registered_artifact(client, sid, "literal.parquet", original)

    response = client.get(artifact["url"] + "/preview")

    assert response.status_code == 200
    assert response.json()["columns"] == ["metric", "value"]
    assert response.json()["rows"] == [["observed", 7], ["missing", None]]
    assert response.json()["total_rows"] == 2
    assert response.json()["total_columns"] == 2
    assert response.json()["truncated"] is False
    downloaded = client.get(artifact["url"])
    assert downloaded.content == original
    assert hashlib.sha256(downloaded.content).hexdigest() == hashlib.sha256(original).hexdigest()
    assert downloaded.headers["content-disposition"].startswith("attachment")


def test_parquet_preview_represents_an_empty_valid_table(client, tmp_path):
    import pyarrow as pa

    sid = new_session(client)["id"]
    artifact = registered_artifact(
        client,
        sid,
        "empty.parquet",
        parquet_bytes(
            tmp_path,
            "empty-source.parquet",
            {"metric": pa.array([], type=pa.string())},
        ),
    )
    response = client.get(artifact["url"] + "/preview")
    assert response.status_code == 200
    assert response.json() == {
        "columns": ["metric"],
        "rows": [],
        "total_rows": 0,
        "total_columns": 1,
        "truncated": False,
    }


def test_parquet_preview_keeps_scope_integrity_and_fixed_safe_errors(client, tmp_path):
    from bridge.web.app import write_file

    first = new_session(client)["id"]
    artifact = registered_artifact(
        client,
        first,
        "scoped.parquet",
        parquet_bytes(tmp_path, "scoped-source.parquet", {"value": [1]}),
    )
    second = client.post("/api/sessions").json()["id"]
    assert client.get(f"/api/sessions/{second}/artifacts/{artifact['id']}/preview").status_code == 404
    assert client.get(f"/api/sessions/{first}/artifacts/" + "a" * 32 + "/preview").status_code == 404

    service = client.app.state.service
    record = service.load(first)["_artifacts"][artifact["id"]]
    write_file(service.directory(first) / "artifacts" / record["file"], b"changed")
    drift = client.get(artifact["url"] + "/preview")
    assert drift.status_code == 409
    assert drift.json() == {"detail": "artifact_integrity_mismatch"}

    unsupported = registered_artifact(client, first, "values.csv", b"metric,value\nobserved,7\n")
    unsupported_response = client.get(unsupported["url"] + "/preview")
    assert unsupported_response.status_code == 415
    assert unsupported_response.json() == {"detail": "artifact_preview_unsupported"}

    invalid = registered_artifact(client, first, "invalid.parquet", b"not a parquet or private path")
    invalid_response = client.get(invalid["url"] + "/preview")
    assert invalid_response.status_code == 422
    assert invalid_response.json() == {"detail": "artifact_preview_unavailable"}
    assert str(tmp_path) not in invalid_response.text


def test_parquet_preview_reports_row_column_and_cell_truncation(client, tmp_path):
    sid = new_session(client)["id"]
    wide = registered_artifact(
        client,
        sid,
        "wide.parquet",
        parquet_bytes(
            tmp_path,
            "wide-source.parquet",
            {f"column_{index}": list(range(101)) for index in range(25)},
        ),
    )
    response = client.get(wide["url"] + "/preview")
    assert response.status_code == 200
    assert response.json()["total_rows"] == 101
    assert response.json()["total_columns"] == 25
    assert len(response.json()["columns"]) == 24
    assert len(response.json()["rows"]) == 100
    assert response.json()["rows"][0] == [0] * 24
    assert response.json()["rows"][-1] == [99] * 24
    assert response.json()["truncated"] is True

    long_text = "x" * 1_050
    text_artifact = registered_artifact(
        client,
        sid,
        "long-text.parquet",
        parquet_bytes(tmp_path, "long-text-source.parquet", {"note": [long_text]}),
    )
    text_response = client.get(text_artifact["url"] + "/preview")
    displayed = text_response.json()["rows"][0][0]
    assert text_response.status_code == 200
    assert len(displayed) == 1_000
    assert displayed.endswith("… [truncated]")
    assert text_response.json()["truncated"] is True


def test_parquet_preview_preserves_scalars_and_rejects_binary_cells(client, tmp_path):
    import pyarrow as pa

    sid = new_session(client)["id"]
    scalar = registered_artifact(
        client,
        sid,
        "scalars.parquet",
        parquet_bytes(
            tmp_path,
            "scalars-source.parquet",
            {
                "number": [float("nan"), float("inf"), float("-inf")],
                "flag": [True, False, None],
            },
        ),
    )
    response = client.get(scalar["url"] + "/preview")
    assert response.status_code == 200
    assert response.json()["rows"] == [
        ["NaN", True],
        ["Infinity", False],
        ["-Infinity", None],
    ]

    binary = registered_artifact(
        client,
        sid,
        "binary.parquet",
        parquet_bytes(
            tmp_path,
            "binary-source.parquet",
            {"payload": pa.array([b"private bytes"], type=pa.binary())},
        ),
    )
    binary_response = client.get(binary["url"] + "/preview")
    assert binary_response.status_code == 422
    assert binary_response.json() == {"detail": "artifact_preview_unavailable"}


def test_parquet_preview_preserves_safe_boundaries_and_large_integers(client, tmp_path):
    import pyarrow as pa

    sid = new_session(client)["id"]
    artifact = registered_artifact(
        client,
        sid,
        "integers.parquet",
        parquet_bytes(
            tmp_path,
            "integers-source.parquet",
            {
                "signed": pa.array([
                    -9_007_199_254_740_991,
                    -9_007_199_254_740_992,
                    9_007_199_254_740_991,
                    9_007_199_254_740_993,
                ], type=pa.int64()),
                "unsigned": pa.array([
                    0,
                    9_007_199_254_740_991,
                    9_007_199_254_740_992,
                    18_446_744_073_709_551_615,
                ], type=pa.uint64()),
            },
        ),
    )

    response = client.get(artifact["url"] + "/preview")

    assert response.status_code == 200
    assert response.json()["rows"] == [
        [-9_007_199_254_740_991, 0],
        ["-9007199254740992", 9_007_199_254_740_991],
        [9_007_199_254_740_991, "9007199254740992"],
        ["9007199254740993", "18446744073709551615"],
    ]


def test_parquet_preview_preserves_large_integral_float64(client, tmp_path):
    import pyarrow as pa

    sid = new_session(client)["id"]
    artifact = registered_artifact(
        client,
        sid,
        "large-floats.parquet",
        parquet_bytes(
            tmp_path,
            "large-floats-source.parquet",
            {
                "float64": pa.array(
                    [1e20, -1e20, 1.25],
                    type=pa.float64(),
                ),
            },
        ),
    )

    response = client.get(artifact["url"] + "/preview")

    assert response.status_code == 200
    assert response.json()["rows"] == [
        ["1e+20"],
        ["-1e+20"],
        [1.25],
    ]


def test_parquet_decode_releases_service_lock_before_batch_parsing(client, tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
    from threading import Event
    from bridge.web import app as web_app

    preview_sid = new_session(client)["id"]
    control_sid = client.post("/api/sessions").json()["id"]
    artifact = registered_artifact(
        client,
        preview_sid,
        "paused.parquet",
        parquet_bytes(tmp_path, "paused-source.parquet", {"value": [1]}),
    )
    real_preview = web_app.parquet_preview
    entered, release = Event(), Event()

    def paused_preview(data):
        entered.set()
        assert release.wait(10)
        return real_preview(data)

    monkeypatch.setattr(web_app, "parquet_preview", paused_preview)
    control_finished_before_release = False
    control_future = None
    with ThreadPoolExecutor(max_workers=2) as pool:
        preview_future = pool.submit(client.get, artifact["url"] + "/preview")
        try:
            if not entered.wait(5):
                pytest.fail("preview decoder was not entered")
            control_future = pool.submit(client.post, f"/api/sessions/{control_sid}/stop", json={})
            try:
                control_response = control_future.result(timeout=1)
                control_finished_before_release = True
            except FutureTimeout:
                control_response = None
        finally:
            release.set()
        preview_response = preview_future.result(timeout=5)
        if control_future is not None and control_response is None:
            control_response = control_future.result(timeout=5)

    assert control_finished_before_release is True
    assert control_response.status_code == 200
    assert control_response.json()["id"] == control_sid
    assert preview_response.status_code == 200
    assert preview_response.json()["rows"] == [[1]]


def test_parquet_preview_rejects_stored_row_group_and_response_limits(client, tmp_path):
    sid = new_session(client)["id"]
    oversized = registered_artifact(
        client,
        sid,
        "oversized.parquet",
        b"PAR1" + b"0" * (8 * 1024 * 1024) + b"PAR1",
    )
    oversized_response = client.get(oversized["url"] + "/preview")
    assert oversized_response.status_code == 413
    assert oversized_response.json() == {"detail": "artifact_preview_too_large"}

    large_group = registered_artifact(
        client,
        sid,
        "large-group.parquet",
        parquet_bytes(
            tmp_path,
            "large-group-source.parquet",
            {"text": ["x" * (33 * 1024 * 1024)]},
            compression="gzip",
            use_dictionary=False,
        ),
    )
    assert len(client.get(large_group["url"]).content) < 8 * 1024 * 1024
    large_group_response = client.get(large_group["url"] + "/preview")
    assert large_group_response.status_code == 413
    assert large_group_response.json() == {"detail": "artifact_preview_too_large"}

    response_heavy = registered_artifact(
        client,
        sid,
        "response-heavy.parquet",
        parquet_bytes(
            tmp_path,
            "response-heavy-source.parquet",
            {
                "first": [("a" * 998) + f"{index:02d}" for index in range(100)],
                "second": [("b" * 998) + f"{index:02d}" for index in range(100)],
                "third": [("c" * 998) + f"{index:02d}" for index in range(100)],
            },
            compression="gzip",
            use_dictionary=False,
        ),
    )
    response_heavy_response = client.get(response_heavy["url"] + "/preview")
    assert response_heavy_response.status_code == 413
    assert response_heavy_response.json() == {"detail": "artifact_preview_too_large"}


def test_restart_interrupts_never_reexecutes(client):
    sid = new_session(client)["id"]
    store = client.app.state.service
    state = store.load(sid)
    state["status"] = "running"
    store.save(state)
    other = create_app(store.settings)
    with TestClient(other) as restarted:
        restarted.headers["Origin"] = "http://testserver"
        login(restarted)
        value = restarted.get(f"/api/sessions/{sid}").json()
        assert value["status"] == "failed"
        assert value["error"] == "interrupted"

def test_unknown_artifacts_are_session_scoped(client, tmp_path):
    first = new_session(client)["id"]
    second = client.post("/api/sessions").json()["id"]
    assert client.get(f"/api/sessions/{second}/artifacts/{first}").status_code == 404
    assert client.get(f"/api/sessions/{first}/artifacts/%2e%2e%2fprivate").status_code == 404


def test_expired_cookie_and_oversized_body_are_rejected(client):
    new_session(client)
    for key in client.app.state.service.cookies:
        client.app.state.service.cookies[key] = 0
    assert client.get("/api/sessions").status_code == 401
    login(client)
    assert client.post("/api/sessions", content=b"x" * 40000).status_code == 413


def test_assay_must_be_declared_for_each_upload(client, tmp_path):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    data = h5ad(tmp_path, layer=True)
    client.post(url + "/uploads", files={"file": ("first.h5ad", data)})
    declare_counts(client, sid, client.get(url).json()["uploads"][0]["id"], location="layers/counts")
    client.post(url + "/messages", json={"text": "scRNA-seq，使用 counts 层进行 QC"})
    assert settle(client, sid)["status"] == "awaiting_approval"
    client.post(url + "/uploads", files={"file": ("second.h5ad", data)})
    client.post(url + "/messages", json={"text": "使用 counts 层进行 QC"})
    result = settle(client, sid)
    assert result["status"] == "idle"
    assert result["plan"] is None


def test_changed_upload_never_executes_and_error_is_safe(client, tmp_path):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    client.post(url + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path, layer=True))})
    declare_counts(client, sid, client.get(url).json()["uploads"][0]["id"], location="layers/counts")
    client.post(url + "/messages", json={"text": "scRNA-seq，使用 counts 层进行 QC"})
    proposal = settle(client, sid)["plan"]
    store = client.app.state.service
    aid = store.load(sid)["uploads"][0]["id"]
    path = store.root / sid / "uploads" / (aid + ".h5ad")
    path.write_bytes(b"changed")
    client.post(url + "/approve", json={"plan_id": proposal["id"], "plan_digest": proposal["digest"]})
    result = settle(client, sid)
    assert result["status"] == "failed"
    assert result["error"] == "execution_failed"
    assert result["artifacts"] == []
    assert str(tmp_path) not in json.dumps(result)


def test_symlink_upload_directory_never_plans(client, tmp_path):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    client.post(url + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path, layer=True))})
    declare_counts(client, sid, client.get(url).json()["uploads"][0]["id"], location="layers/counts")
    directory = client.app.state.service.root / sid / "uploads"
    destination = tmp_path / "moved-upload"
    directory.rename(destination)
    directory.symlink_to(destination, target_is_directory=True)
    client.post(url + "/messages", json={"text": "scRNA-seq，使用 counts 层进行 QC"})
    result = settle(client, sid)
    assert result["status"] == "failed"
    assert result["plan"] is None


def test_hdf5_external_links_rejected(client, tmp_path):
    import h5py
    sid = new_session(client)["id"]
    path = tmp_path / "external.h5ad"
    path.write_bytes(h5ad(tmp_path))
    with h5py.File(path, "a") as handle:
        handle["external"] = h5py.ExternalLink("/private/data.h5ad", "/")
    response = client.post(f"/api/sessions/{sid}/uploads", files={"file": ("external.h5ad", path.read_bytes())})
    assert response.status_code == 400
    assert "/private/" not in response.text


def test_provider_cannot_prepare_without_explicit_declaration(client, monkeypatch, tmp_path):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    response = client.post(url + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path, layer=True))})
    aid = response.json()["uploads"][0]["id"]
    original = httpx.Client
    def provider(request):
        payload = json.loads(request.content)
        encoded = json.dumps(payload)
        assert "private-cell-a" not in encoded
        assert str(tmp_path) not in encoded
        assert "synthetic.h5ad" not in encoded
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({"action": "prepare_qc", "upload_id": aid, "matrix_location": "layers/counts"})}}]})
    monkeypatch.setattr("bridge.web.provider.httpx.Client", lambda **kwargs: original(transport=httpx.MockTransport(provider), **kwargs))
    client.post(url + "/messages", json={"text": "Can you explain this workflow?"})
    value = settle(client, sid)
    assert value["status"] == "idle"
    assert value["plan"] is None

def test_hdf5_external_dataset_rejected(client, tmp_path):
    import h5py
    sid = new_session(client)["id"]
    path = tmp_path / "external-array.h5ad"
    path.write_bytes(h5ad(tmp_path))
    with h5py.File(path, "a") as handle:
        handle.create_dataset("external_array", (10,), dtype="i4", external=[("not-loaded.bin", 0, 40)])
    response = client.post(f"/api/sessions/{sid}/uploads", files={"file": ("external-array.h5ad", path.read_bytes())})
    assert response.status_code == 400

@pytest.mark.parametrize("text", ["counts 层不是原始计数", "scRNA-seq，使用 counts 层？", "不要使用 counts 层进行 QC"])
def test_ambiguous_or_negative_counts_never_prepare(client, tmp_path, monkeypatch, text):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    client.post(url + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path, layer=True))})
    original = httpx.Client
    monkeypatch.setattr("bridge.web.provider.httpx.Client", lambda **kwargs: original(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"choices": [{"message": {"content": "请明确计数语义。"}}]})), **kwargs))
    client.post(url + "/messages", json={"text": text})
    value = settle(client, sid)
    assert value["plan"] is None
    assert "_pending_qc" not in client.app.state.service.load(sid)

def test_underreported_content_length_still_bounds_received_json(client):
    sid = new_session(client)["id"]
    response = client.post(f"/api/sessions/{sid}/messages",
                           content=json.dumps({"text": "x" * 40000}),
                           headers={"Content-Length": "1", "Content-Type": "application/json"})
    assert response.status_code == 413

def test_cancelled_pending_counts_does_not_prepare_on_assay_mention(client, tmp_path, monkeypatch):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    client.post(url + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path, layer=True))})
    client.post(url + "/messages", json={"text": "使用 counts 层进行 QC"})
    assert settle(client, sid)["plan"] is None
    original = httpx.Client
    monkeypatch.setattr("bridge.web.provider.httpx.Client", lambda **kwargs: original(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"choices": [{"message": {"content": "已取消准备计划。"}}]})), **kwargs))
    client.post(url + "/messages", json={"text": "不要 QC，这是 scRNA-seq"})
    assert settle(client, sid)["plan"] is None

@pytest.mark.parametrize("text", [
    "This is not scRNA-seq; X contains raw counts",
    "Do not use X as raw counts; this is scRNA-seq",
    "This isn't scRNA-seq; X contains raw counts",
])
def test_english_negative_matrix_and_assay_never_prepare(client, tmp_path, monkeypatch, text):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    client.post(url + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path))})
    original = httpx.Client
    monkeypatch.setattr("bridge.web.provider.httpx.Client", lambda **kwargs: original(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"choices": [{"message": {"content": "Please clarify your declaration."}}]})), **kwargs))
    client.post(url + "/messages", json={"text": text})
    value = settle(client, sid)
    assert value["plan"] is None
    assert "_pending_qc" not in client.app.state.service.load(sid)


@pytest.mark.parametrize("statement", [
    "counts 层不是原始计数", "This is not scRNA-seq",
    "not all biological replicates are independent", "snRNA-seq rather than scRNA-seq",
])
def test_ordinary_followup_cannot_change_committed_qc(client, tmp_path, monkeypatch, statement):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    aid = client.post(url + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path, layer=True))}).json()["uploads"][0]["id"]
    declare_counts(client, sid, aid, location="layers/counts")
    client.post(url + "/messages", json={"text": "scRNA-seq，使用 counts 层进行 QC"})
    assert settle(client, sid)["status"] == "awaiting_approval"
    before = client.app.state.service.load(sid)
    monkeypatch.setattr("bridge.web.app.converse", lambda *a: parse_action({"content": '{"action":"reply","text":"Discussed."}'}))
    client.post(url + "/messages", json={"text": statement})
    assert settle(client, sid)["status"] == "idle"
    after = client.app.state.service.load(sid)
    assert after["_qc_declarations"] == before["_qc_declarations"]
    assert after["_uploads"] == before["_uploads"]
    assert client.app.state.service.assay(after, aid) == "scRNA-seq"
    assert client.app.state.service.declaration(after, aid) == "layers/counts"


def test_provider_failure_preserves_pending_fact_confirmation(client, tmp_path, monkeypatch):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    aid = client.post(url + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path, layer=True))}).json()["uploads"][0]["id"]
    staged = client.post(url + "/analysis-inputs/assets", json={
        "upload_id": aid, "assay": "scRNA-seq", "matrix_location": "layers/counts",
        "matrix_semantics": "raw_counts", "input_level": "count_ready", "metadata": {},
    }).json()
    original = httpx.Client
    monkeypatch.setattr("bridge.web.provider.httpx.Client", lambda **kwargs: original(transport=httpx.MockTransport(
        lambda request: httpx.Response(502)), **kwargs))
    client.post(url + "/messages", json={"text": "Discuss this pending declaration."})
    failed = settle(client, sid)
    assert failed["status"] == "failed"
    assert failed["pending_input_change"] == staged["pending_input_change"]
    assert aid not in client.app.state.service.load(sid)["_qc_declarations"]
