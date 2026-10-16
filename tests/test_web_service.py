from __future__ import annotations

import hashlib
import json
import time

import pytest
httpx = pytest.importorskip("httpx")
pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from bridge.web.app import Settings
from account_support import create_test_app as create_app, LOGIN
from bridge.web.provider import parse_action
from web_support import (
    confirm_change,
    declare_counts,
    declare_source,
    client as client,
    login,
    new_session,
    settle,
    h5ad,
)


def test_session_store_round_trip_without_application(tmp_path):
    from bridge.web.sessions import SessionStore
    from bridge.storage.private_paths import ensure_private_directory
    store = SessionStore(tmp_path / "sessions", "acceptance")
    sid = "a" * 32
    ensure_private_directory(store.root / sid)
    store.save({"id": sid, "status": "idle", "messages": []})
    loaded = store.load(sid)
    assert loaded["id"] == sid
    assert loaded["status"] == "idle"
    assert loaded["messages"] == []
    assert loaded["updated_at"]


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
    monkeypatch.setattr("bridge.web.service.converse", lambda *a: parse_action({"content": '{"action":"review_inputs","text":"Review the existing input panel."}'}))
    client.post(url + "/messages", json={"text": "Please correct the assay."})
    reviewed = settle(client, sid)
    assert reviewed["input_review_required"] is True
    for response in (
        client.post(url + "/prepare-analysis", json={"tool_id": "P0-02"}),
        client.post(url + "/approve", json={"plan_id": "old", "plan_digest": "0"*64}),
    ):
        assert response.json()["error_id"] == "confirmation_required"
        assert "detail" not in response.json()
    staged = client.post(url + "/inputs", json={"upload_id": aid, "source_family_id": "private-source"}).json()
    assert client.post(url + "/input-review/keep", json={}).status_code == 409
    pending = staged["pending_input_change"]
    discarded = client.post(url + "/input-change/discard", json={"change_id": pending["id"], "change_digest": pending["digest"]}).json()
    assert discarded["input_review_required"] is True
    monkeypatch.setattr("bridge.web.service.converse", lambda *a: parse_action({"content": '{"action":"reply","text":"OK"}'}))
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
    monkeypatch.setattr("bridge.web.service.converse", blocked)
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
    monkeypatch.setattr("bridge.web.service.converse", lambda *a: parse_action({"content": '{"action":"reply","text":"Waiting."}'}))
    declare_counts(client, sid, aid, location="X")
    client.post(url + "/messages", json={"text": "scRNA-seq, X contains raw counts; please wait before preparing QC."})
    assert settle(client, sid)["plan"] is None
    monkeypatch.setattr("bridge.web.service.converse", lambda *a: parse_action({"content": json.dumps({
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
    monkeypatch.setattr("bridge.web.service.converse", lambda *a: parse_action({"content": json.dumps({
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
    service.sessions.save(state)
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
    service.message(state, "user", "snRNA-seq", source="user_input")
    service.sessions.save(state)
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
    service.sessions.save(state)
    loaded = service.load(sid)
    assert loaded["input_review_required"] is mismatch
    assert loaded["_tool_runs"] == receipts
    client.post(url + "/input-review/keep", json={})
    if mismatch:
        with pytest.raises(ValueError, match="qc_declaration_retracted"):
            service.qc.asset(service.load(sid), aid, register=False, enrich=False)
    else:
        assert service.qc.asset(service.load(sid), aid, register=False, enrich=False).assay == "scRNA-seq"


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
    service.sessions.save(state)
    migrated = service.load(sid)
    assert migrated["input_review_required"]
    assert migrated["_tool_runs"] == receipts
    client.post(url + "/input-review/keep", json={})
    with pytest.raises(ValueError, match="qc_declaration_retracted"):
        service.qc.asset(service.load(sid), aid, register=False, enrich=False)


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
    enriched = service.qc.asset(state, aid).model_dump(mode="json")
    if tampered:
        enriched["metadata"]["qc_profile_ref"] = "unproven-profile"
    state["_bundle"]["assets"] = [enriched]
    state["_asset_declarations"] = {}
    del state["_qc_declarations"]
    service.sessions.save(state)
    migrated = service.load(sid)
    assert migrated["input_review_required"] is tampered
    if not tampered:
        declare_source(client, sid, aid, "changed-source-only")
        current = service.load(sid)
        assert current["input_review_required"] is False
        assert service.qc.asset(current, aid).metadata["source_family_id"] == "changed-source-only"


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
    assert service.qc.asset(state, aid, register=False, enrich=False).metadata["data_view_id"] == "caller-before-qc"
    enriched = service.qc.asset(state, aid).model_dump(mode="json")
    assert enriched["metadata"]["data_view_id"] != "caller-before-qc"
    state["_bundle"]["assets"] = [enriched]
    state["_asset_declarations"] = {}
    del state["_qc_declarations"]
    service.sessions.save(state)
    assert service.load(sid)["input_review_required"]
    client.post(url + "/input-review/keep", json={})
    with pytest.raises(ValueError, match="qc_declaration_retracted"):
        service.qc.asset(service.load(sid), aid, register=False, enrich=False)


def test_exact_stop_command_cannot_bypass_conversation_bound(client):
    sid = new_session(client)["id"]
    service = client.app.state.service
    state = service.load(sid)
    state["messages"] *= 100
    service.sessions.save(state)
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
    service.qc.asset(pending, aid, register=False, enrich=False)
    captured = []
    def reply(settings, messages, context):
        captured.append(context)
        return parse_action({"content": '{"action":"reply","text":"Use the panel."}'})
    monkeypatch.setattr("bridge.web.service.converse", reply)
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
    with pytest.raises(ValueError, match="completed_qc_required"):
        service.qc.asset(committed, aid, register=False, enrich=False)


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
    from bridge.web.service import CATALOG_LOCK
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
            assert response.json()["error_id"] == "execution_incomplete"
            assert "detail" not in response.json()
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
    monkeypatch.setattr("bridge.web.service.converse", prepare)
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
    service.sessions.save(state)
    restarted = create_app(service.settings).state.service
    try:
        loaded = restarted.load(sid)
        assert loaded["status"] == "failed" and loaded["error"] == "interrupted"
        assert loaded["input_review_required"]
        assert loaded["plan"]["steps"][0]["status"] == "succeeded"
        assert loaded["plan"]["steps"][1]["status"] == "cancelled"
        assert loaded["_tool_runs"] == []
    finally:
        restarted.execution.pool.shutdown(wait=True)


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
    monkeypatch.setattr("bridge.web.service.converse", lambda *args: parse_action({"content": '{"action":"prepare_analysis","tool_id":"P0-12"}'}))
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
    monkeypatch.setattr("bridge.web.service.converse", lambda *args: parse_action({
        "content": '{"action":"review_inputs","text":"Please review the input panel."}',
    }))
    client.post(url + "/messages", json={"text": retraction})
    assert settle(client, sid)["input_review_required"] is True
    monkeypatch.setattr("bridge.web.service.converse", lambda *args: parse_action({
        "content": '{"action":"prepare_analysis","tool_id":"P0-02"}',
    }))
    client.post(url + "/messages", json={"text": "Continue cell-state analysis."})
    value = settle(client, sid)
    assert value["plan"]["status"] == "completed"
    assert value["presentation"]["issue"]["error_id"] == "confirmation_required"
    after = client.app.state.service.load(sid)
    assert after["error"] == "input_review_required"
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
    service.qc.asset(baseline, aid, register=False, enrich=False)
    monkeypatch.setattr(
        "bridge.web.service.converse",
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
        service.qc.asset(current, aid, register=False, enrich=False)

    monkeypatch.setattr("bridge.web.service.converse", lambda *args: parse_action({
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
    asset = service.qc.asset(before, aid, register=False, enrich=False)
    monkeypatch.setattr("bridge.web.service.converse", lambda *args: parse_action({
        "content": '{"action":"reply","text":"Please supply missing inputs privately."}',
    }))

    client.post(url + "/messages", json={"text": statement})
    after = settle(client, sid)
    state = service.load(sid)
    assert state["_uploads"][aid]["declaration_start"] == before["_uploads"][aid]["declaration_start"]
    assert service.assay(state, aid) == "scRNA-seq"
    assert service.qc.asset(state, aid, register=False, enrich=False) == asset
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
    monkeypatch.setattr("bridge.web.service.converse", lambda *args: parse_action({"content": '{"action":"prepare_analysis","tool_id":"P0-12"}'}))
    client.post(url + "/messages", json={"text": "What is graft assessment?"})
    value = settle(client, sid)
    assert value["plan"] is None
    assert value["presentation"]["issue"]["error_id"] == "request_failed"
    assert client.app.state.service.load(sid)["error"] == "no_graft_declaration_required"


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
    service.sessions.save(legacy)
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
    with service.qc.catalog():
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
    monkeypatch.setattr("bridge.web.service.converse", action)
    def propose():
        client.post(url + "/messages", json={"text": "继续细胞状态分析"})
        return settle(client, sid)
    assert propose()["presentation"]["issue"]["error_id"] == "request_failed"
    assert service.load(sid)["error"] == "measurement_spec_not_configured"
    service.settings = replace(service.settings, cell_state_measurement_spec_ref="CELLSTATE-scRNA-shadow-v0.1")
    monkeypatch.delenv("BRIDGE_REFERENCE_ROOT", raising=False)
    assert propose()["presentation"]["issue"]["error_id"] == "request_failed"
    assert service.load(sid)["error"] == "reference_root_not_configured"
    _build_snapshot(tmp_path, monkeypatch)
    assert propose()["presentation"]["issue"]["error_id"] == "request_failed"
    assert service.load(sid)["error"] == "source_family_id_required"
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
    with service.qc.catalog():
        upstream = validate_upstream_qc_bundle(InputAsset.model_validate(asset))
        assert upstream.profile.profile_id == asset["metadata"]["qc_profile_ref"]
        assert upstream.profile_v2.selected_data_view.view_id == asset["metadata"]["data_view_id"]
    assert os.environ["BRIDGE_QC_PROFILE_CATALOG"] == "original-catalog-sentinel"
    with pytest.raises(RuntimeError), service.qc.catalog():
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
    monkeypatch.setattr("bridge.web.service.converse", lambda *args: parse_action({
        "content": '{"action":"review_inputs","text":"Review the assay in the input panel."}',
    }))
    client.post(url + "/messages", json={"text": "This is not scRNA-seq"})
    reviewed = settle(client, sid)
    assert reviewed["input_review_required"]
    assert reviewed["plan"]["status"] == "completed"
    assert client.post(url + "/input-review/keep", json={}).status_code == 200
    monkeypatch.setattr("bridge.web.service.converse", lambda *args: parse_action({
        "content": '{"action":"prepare_analysis","tool_id":"P0-02"}',
    }))
    # Downstream construction must not fall back to display copies after deletion.
    upstream.profile_path.unlink()
    assert propose()["presentation"]["issue"]["error_id"] == "request_failed"
    assert service.load(sid)["error"] == "qc_artifacts_missing"

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
    monkeypatch.setattr("bridge.web.service.converse", action)

    client.post(url + "/messages", json={
        "text": "来源信息已在数据表单填写。请继续细胞状态分析。",
    })
    settle(client, sid)

    assert len(captured) == 1
    context = captured[0]
    assert set(context) == {
        "status", "upload_ids", "plan_status", "capabilities",
        "tool_execution_history", "results_sent_to_model", "input_contracts", "input_review_required",
        "intake_context", "clarification_context", "research_context",
    }
    assert context["clarification_context"] == []
    assert context["intake_context"] == [{
        "upload_id": aid, "state": "needs_confirmation",
        # Report the current consequential questions, not the retired questionnaire.
        # This synthetic matrix has no confirmed independent-culture column.
        "missing_fields": ["target_cell_type", "target_stage", "culture_batch_column"],
    }]
    assert context["status"] == "idle"
    assert context["upload_ids"] == [aid]
    assert context["plan_status"] == "completed"
    assert context["tool_execution_history"] == [{
        "tool_id": "P0-01", "state": "succeeded",
    }]
    assert context["research_context"] == {
        "current_question": "来源信息已在数据表单填写。请继续细胞状态分析。",
        "confirmed_input_state": context["intake_context"],
        "analyses_attempted": context["tool_execution_history"],
        "admitted_results": {"state": "not_available", "evidence_refs": []},
        "limitations": [{"field": "state", "state": "not_available"}],
        "unresolved_reason": "results_not_available",
        "user_correction_state": "current",
    }
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
        "legacy_aggregation", "method_runtime", "hard_count_accounting", "saved_cell_state_context",
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
    service.sessions.save(state)
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
    monkeypatch.setattr("bridge.web.service.converse", lambda *args: parse_action({"content": '{"action":"prepare_analysis","tool_id":"P0-12"}'}))
    client.post(url + "/messages", json={"text": text})
    value = settle(client, sid)
    assert value["plan"] is None
    assert value["presentation"]["issue"]["error_id"] == "request_failed"
    assert client.app.state.service.load(sid)["error"] == "no_graft_declaration_required"


def test_restart_preserves_completed_plan_during_interrupted_conversation(client):
    sid = new_session(client)["id"]
    store = client.app.state.service
    state = store.load(sid)
    state["status"] = "thinking"
    state["plan"] = {"id": "completed", "status": "completed", "steps": []}
    store.sessions.save(state)
    other = create_app(store.settings)
    other.state.service.execution.pool.shutdown()
    assert other.state.service.load(sid)["plan"]["status"] == "completed"


def test_settings_default_and_native_action_protocol_validation(tmp_path):
    values = dict(
        storage_root=tmp_path / "private",
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
def test_settings_reads_only_explicit_action_protocol_startup_values(
    tmp_path, monkeypatch, configured, expected
):
    from bridge.web.runtime import settings_from_environment
    environment = {
        "BRIDGE_WEB_STORAGE": str(tmp_path / "startup-private"),

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
    assert settings_from_environment().model_action_protocol == expected


def test_settings_rejects_unknown_action_protocol_startup_value(tmp_path, monkeypatch):
    from bridge.web.runtime import settings_from_environment
    environment = {
        "BRIDGE_WEB_STORAGE": str(tmp_path / "startup-private"),

        "BRIDGE_WEB_MODEL_BASE_URL": "https://provider.invalid/v1",
        "BRIDGE_WEB_MODEL": "test-model",
        "BRIDGE_WEB_MODEL_API_KEY": "private-key",
        "BRIDGE_WEB_MODEL_ACTION_PROTOCOL": "automatic",
        "BRIDGE_WEB_SHARE_RESULT_SUMMARIES": "0",
    }
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("BRIDGE_WEB_TRUSTED_ANCESTORS", raising=False)

    with pytest.raises(ValueError, match="^invalid_server_configuration$"):
        settings_from_environment()


def test_auth_origin_logout_and_path_boundaries(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/api/sessions").status_code == 401
    assert client.post("/api/login", json={"username": "operator", "password": "wrong"}).status_code == 401
    assert client.post("/api/login", json=LOGIN, headers={"Origin": "https://evil.invalid"}).status_code == 403
    login(client)
    cookie = client.cookies.get("bridge_production_accounts_session")
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
    from web_support import skill_read_response
    sid = new_session(client)["id"]
    def response(request):
        payload = json.loads(request.content)
        read = skill_read_response(payload)
        if read is not None:
            return read
        assert "tools" not in payload and "tool_choice" not in payload
        assert "thinking" not in payload
        assert payload["response_format"] == {"type": "json_object"}
        assert payload["max_tokens"] == 3000
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
            "When results_sent_to_model is false, make no scientific result assertions. "
            "You may still answer method,"
        ) in system
        assert "ordinary method explanations or clarification" in system
        assert "research_context keeps the current question" in system
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
            "Do not prepare a plan when the user asks to stop or not prepare "
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
    assert value["messages"][-1]["source"] == "provider_admitted"
    monkeypatch.setattr("bridge.web.provider.httpx.Client", lambda **kwargs: original(transport=httpx.MockTransport(lambda request: httpx.Response(502, text="/private/provider/key")), **kwargs))
    client.post(f"/api/sessions/{sid}/messages", json={"text": "Continue"})
    failed = settle(client, sid)
    assert failed["status"] == "failed"
    assert failed["presentation"]["issue"]["error_id"] == "request_failed"
    assert client.app.state.service.load(sid)["error"] == "provider_unavailable"
    assert "/private/provider/key" not in json.dumps(failed)


def test_native_protocol_wire_and_service_proposal_never_executes(
    tmp_path, monkeypatch
):
    from web_support import skill_read_response
    captured = {}
    def response(request):
        payload = json.loads(request.content)
        read = skill_read_response(payload, "product-assessment")
        if read is not None:
            return read
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
    assert "tool_choice" not in payload
    assert "thinking" not in payload
    assert "reasoning_effort" not in payload
    # Unspecified effort preserves the provider default, which may reason.
    assert payload["max_tokens"] == 32768
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
        "properties": {"text": {"type": "string", "maxLength": 12000},
            "observation_aliases": {"type": "array", "items": {"type": "string"},
                "title": "Observation Aliases", "maxItems": 0}},
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
        "When results_sent_to_model is false, make no scientific result assertions. "
        "You may still answer method,"
    ) in system
    assert "ordinary method explanations or clarification" in system
    assert "research_context keeps the current question" in system
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
        "Do not prepare a plan when the user asks to stop or not prepare "
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


def test_restart_interrupts_never_reexecutes(client):
    sid = new_session(client)["id"]
    store = client.app.state.service
    state = store.load(sid)
    state["status"] = "running"
    store.sessions.save(state)
    other = create_app(store.settings)
    with TestClient(other) as restarted:
        restarted.headers["Origin"] = "http://testserver"
        login(restarted)
        value = restarted.get(f"/api/sessions/{sid}").json()
        assert value["status"] == "failed"
        assert value["presentation"]["issue"]["error_id"] == "request_failed"
        assert restarted.app.state.service.load(sid)["error"] == "interrupted"


def test_expired_cookie_and_oversized_body_are_rejected(client):
    new_session(client)
    with client.app.state.service.accounts.connect() as db:
        db.execute("UPDATE logins SET expires = 0")
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
    assert result["presentation"]["issue"]["error_id"] == "execution_incomplete"
    assert store.load(sid)["error"] == "execution_failed"
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
    from web_support import skill_read_response
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    response = client.post(url + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path, layer=True))})
    aid = response.json()["uploads"][0]["id"]
    original = httpx.Client
    def provider(request):
        payload = json.loads(request.content)
        read = skill_read_response(payload)
        if read is not None:
            return read
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
    monkeypatch.setattr("bridge.web.service.converse", lambda *a: parse_action({"content": '{"action":"reply","text":"Discussed."}'}))
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


def test_graph_composition_preview_preserves_download_and_rejects_bad_bindings(client):
    from copy import deepcopy
    from test_p0_09_evidence_compiler import _run
    from bridge.web.sessions import write_file
    service = client.app.state.service
    sid = new_session(client)["id"]
    root = service.directory(sid)
    run = _run(root / "runs" / "graph-preview")
    assert run.execution_state.value == "succeeded", run.reason_codes
    receipt_bytes = run.model_dump_json().encode()
    receipt = {"file": "graph-preview.json", "sha256": hashlib.sha256(receipt_bytes).hexdigest(),
        "tool_id": "P0-09", "state": "succeeded", "plan_id": "preview-test"}
    write_file(root / "receipts" / receipt["file"], receipt_bytes)
    state = service.load(sid)
    state["_tool_runs"].append(receipt)
    service.inputs.register_outputs(state, run, receipt)
    service.artifacts.register(state, run)
    artifact = next(a for a in state["artifacts"] if a["name"].startswith("cytoscape_elements."))
    url = artifact["url"]
    before = (root / "session.json").read_bytes()
    raw = client.get(url).content
    response = client.get(url + "/preview")
    assert response.status_code == 200, response.text
    assert response.json()["composition_mapping"] == []
    assert response.json()["graph_version"] == 1
    assert (root / "session.json").read_bytes() == before
    assert client.get(url).content == raw
    original = deepcopy(service.load(sid))
    for failure in ("source_sha", "duplicate_manifest", "denied", "unacknowledged", "receipt_tamper", "canonical_tamper"):
        state = deepcopy(original)
        if failure == "source_sha":
            state["_artifacts"][artifact["id"]]["source_sha256"] = "0" * 64
        elif failure == "duplicate_manifest":
            manifest = next(r for r in state["_input_objects"].values() if r["schema_ref"].endswith("case-evidence-graph-manifest/v0.1"))
            state["_input_objects"]["duplicate"] = deepcopy(manifest)
        elif failure == "denied":
            state["_artifacts"][artifact["id"]]["content_class"] = "developer_diagnostic"
            state["_artifacts"][artifact["id"]]["source_kind"] = "provider_log"
        elif failure == "unacknowledged":
            state["_artifacts"][artifact["id"]]["content_class"] = "research_report"
        elif failure == "receipt_tamper":
            write_file(root / "receipts" / receipt["file"], b"{}")
        elif failure == "canonical_tamper":
            source = next(a for a in run.artifacts if a.kind == "cytoscape_elements")
            saved = source.path.read_bytes()
            write_file(source.path, b"{}")
        service.sessions.save(state)
        response = client.get(url + "/preview")
        assert response.status_code == (404 if failure == "denied" else 409 if failure == "unacknowledged" else 422), (failure, response.text)
        assert str(root) not in response.text
        if failure not in {"denied", "unacknowledged"}:
            assert client.get(url).content == raw
        write_file(root / "receipts" / receipt["file"], receipt_bytes)
        if failure == "canonical_tamper":
            write_file(source.path, saved)
    service.sessions.save(original)


@pytest.mark.parametrize(("semantics", "assay", "spec", "expected"), [
    ("raw_counts", "scRNA-seq", None, ("基础 QC 指标已计算", "未生成候选标记", "measurement_spec_not_selected", "维护者", "不代表零个异常")),
    ("raw_counts", "scRNA-seq", "QC-scRNA-candidate-v0.1", ("基础 QC 指标已计算", "已生成候选标记", "QC-scRNA-candidate-v0.1", "未删除细胞")),
    ("raw_counts", "snRNA-seq", "QC-snRNA-candidate-v0.1", ("基础 QC 指标已计算", "已生成候选标记", "QC-snRNA-candidate-v0.1", "未删除细胞")),
    ("normalized_expression", "scRNA-seq", None, ("仅完成结构审计", "原始计数", "未生成候选标记", "不代表零个异常")),
])
def test_typed_figure_preview_binds_saved_renders_and_tables_without_writes(
    client, tmp_path, semantics, assay, spec, expected,
):
    from copy import deepcopy
    from test_input_qc import _write_h5ad, _request
    from bridge.toolkit.registry import ToolRegistry
    from bridge.web.sessions import write_file
    service = client.app.state.service
    sid = new_session(client)["id"]
    root = service.directory(sid)
    work = root / "runs" / "typed-preview"
    work.mkdir(parents=True)
    run = ToolRegistry.load_default().run(_request(
        work, _write_h5ad(work / "synthetic.h5ad", counts=semantics == "raw_counts"),
        semantics=semantics, assay=assay, spec=spec,
    ))
    assert run.execution_state.value in {"succeeded", "partial"}, run.reason_codes
    receipt_bytes = run.model_dump_json().encode()
    receipt = {"file": "typed-preview.json", "sha256": hashlib.sha256(receipt_bytes).hexdigest(),
        "tool_id": "P0-01", "state": run.execution_state.value, "plan_id": "preview-test"}
    write_file(root / "receipts" / receipt["file"], receipt_bytes)
    state = service.load(sid)
    state["_tool_runs"].append(receipt)
    service.inputs.register_outputs(state, run, receipt)
    service.artifacts.register(state, run)
    artifact = next(a for a in state["artifacts"] if a["name"].startswith("qc_visualization_artifact_set."))
    url = artifact["url"]
    before = (root / "session.json").read_bytes()
    original_download = client.get(url).content
    response = client.get(url + "/preview")
    assert response.status_code == 200, response.text
    projection = response.json()
    assert projection["kind"] == "typed_figures"
    assert len(projection["figures"]) == 4
    assert (root / "session.json").read_bytes() == before
    assert str(root) not in response.text
    for figure in projection["figures"]:
        contract = figure["contract"]
        description = contract["accessibility"]["long_description"]
        assert all(text in description for text in expected), description
        if spec is None:
            assert "候选规则：未选择" in description
            assert "已生成候选标记" not in description
        else:
            assert "候选规则：未选择" not in description
        table_binding = state["_canonical_artifacts"][figure["table"]["id"]]
        assert table_binding["artifact_id"] == contract["accessibility"]["table_artifact_id"]
        assert state["_canonical_artifacts"][figure["data"]["id"]]["sha256"] == contract["data_binding"]["sha256"]
        assert {a["media_type"] for a in figure["renders"]} == {"image/svg+xml", "image/png"}
    # Reading the explanatory projection must not rewrite historical artifacts.
    assert client.get(url).content == original_download
    assert run.request.measurement_spec_ref == spec
    original = deepcopy(service.load(sid))
    table_id = projection["figures"][0]["table"]["id"]
    for failure in ("source_sha", "table_sha", "duplicate_table", "denied_table", "unacknowledged_table", "duplicate_receipt", "receipt_tamper"):
        state = deepcopy(original)
        if failure == "source_sha":
            state["_artifacts"][artifact["id"]]["source_sha256"] = "0" * 64
        elif failure == "table_sha":
            state["_artifacts"][table_id]["source_sha256"] = "0" * 64
        elif failure == "duplicate_table":
            duplicate = deepcopy(next(a for a in state["artifacts"] if a["id"] == table_id))
            duplicate["id"] = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
            state["artifacts"].append(duplicate)
            state["_artifacts"]["bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"] = deepcopy(state["_artifacts"][table_id])
            state["_canonical_artifacts"]["bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"] = deepcopy(state["_canonical_artifacts"][table_id])
        elif failure == "denied_table":
            state["_artifacts"][table_id]["content_class"] = "developer_diagnostic"
            state["_artifacts"][table_id]["source_kind"] = "provider_log"
        elif failure == "unacknowledged_table":
            state["_artifacts"][table_id]["content_class"] = "research_report"
        elif failure == "duplicate_receipt":
            state["_tool_runs"].append(deepcopy(receipt))
        else:
            write_file(root / "receipts" / receipt["file"], b"{}")
        service.sessions.save(state)
        response = client.get(url + "/preview")
        assert response.status_code == 422, (failure, response.text)
        assert str(root) not in response.text
        assert client.get(url).content == original_download
        write_file(root / "receipts" / receipt["file"], receipt_bytes)
    service.sessions.save(original)


def test_oversized_session_write_preserves_previous_readable_file(tmp_path):
    from bridge.web.sessions import SessionStore
    from bridge.storage.private_paths import ensure_private_directory
    store = SessionStore(tmp_path / "sessions", "acceptance")
    sid = "b" * 32
    ensure_private_directory(store.root / sid)
    store.save({"id": sid, "status": "idle", "messages": []})
    path = store.root / sid / "session.json"
    before = path.read_bytes()
    state = store.load(sid)
    state["messages"].append({"content": "x" * (8 * 1024 * 1024)})
    with pytest.raises(ValueError, match="private_file_too_large"):
        store.save(state)
    assert path.read_bytes() == before
    assert store.load(sid)["status"] == "idle"
    assert store.load(sid)["messages"] == []


def test_large_assessment_bindings_roundtrip_outside_session_limit_without_losing_history(tmp_path, monkeypatch):
    from bridge.web import sessions
    from bridge.storage.private_paths import ensure_private_directory
    store = sessions.SessionStore(tmp_path / "sessions", "acceptance")
    sid = "c" * 32
    ensure_private_directory(store.root / sid)
    monkeypatch.setattr(sessions, "SESSION_BYTES_LIMIT", 64 * 1024)
    bindings = {"E-one": {"receipt_file": "private-record-" + "x" * 70000}}
    state = {"id": sid, "status": "idle", "messages": [],
        "_assessment": {"model_turns": [{"number": 2, "evidence_bindings": bindings,
            "provider_bindings": {"evidence": {"E-current": "canonical-record"}}}]},
        "_assessment_history": [{"model_turns": [{"number": 1, "evidence_bindings": bindings}]}]}
    store.save(state)
    assert (store.root / sid / "session.json").stat().st_size < 64 * 1024
    loaded = store.load(sid)
    assert loaded["_assessment"] == state["_assessment"]
    assert loaded["_assessment_history"] == state["_assessment_history"]
    loaded["_assessment"]["model_turns"][0]["state"] = "received"
    store.save(loaded)
    assert store.load(sid)["_assessment_history"] == state["_assessment_history"]


@pytest.mark.parametrize("damage", ["changed", "missing", "symlink"])
def test_archived_assessment_binding_integrity_is_required(tmp_path, damage):
    from bridge.web import sessions
    from bridge.storage.private_paths import ensure_private_directory
    store = sessions.SessionStore(tmp_path / "sessions", "acceptance")
    sid = "d" * 32
    ensure_private_directory(store.root / sid)
    state = {"id": sid, "_assessment": {"model_turns": [{
        "provider_bindings": {"evidence": {"E-old": "x" * 9000}}}]}}
    store.save(state)
    path, = (store.root / sid / "assessment-bindings").glob("*.json")
    if damage == "changed":
        path.write_text('{"altered":true}')
    elif damage == "missing":
        path.unlink()
    else:
        target = tmp_path / "outside.json"
        target.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(target)
    with pytest.raises((ValueError, OSError)):
        store.load(sid)


def test_archived_binding_reference_cannot_escape_session_directory(tmp_path):
    from bridge.web.sessions import SessionStore
    from bridge.storage.private_paths import ensure_private_directory
    store = SessionStore(tmp_path / "sessions", "acceptance")
    sid = "e" * 32
    ensure_private_directory(store.root / sid)
    path = store.root / sid / "session.json"
    path.write_text(json.dumps({"id": sid, "_assessment": {"model_turns": [{
        "_binding_files": {"provider_bindings": "../../outside"}}]}}))
    with pytest.raises(ValueError, match="private_binding_invalid"):
        store.load(sid)
