from dataclasses import replace
from threading import Event
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi import HTTPException

from bridge.web.model_settings import ModelSettingsInput
from multiuser_support import multi_clients
from web_support import client


def test_two_users_keep_submitted_model_snapshots(tmp_path):
    entered, release = Event(), Event()
    seen = []
    with multi_clients(tmp_path) as (service, alice, bob, admin):
        aid = alice.get("/api/me").json()["user"]["id"]
        model = service.model_configuration
        model.save_for(aid, ModelSettingsInput(base_url="https://personal.invalid/v1", model="alice-old", api_key="alice-secret"))
        first = alice.post("/api/sessions", json={}).json()["id"]
        second = bob.post("/api/sessions", json={}).json()["id"]
        def work(sid, epoch):
            entered.set()
            assert release.wait(5)
            seen.append((service.settings.model, service.settings.model_api_key, service.settings.share_result_summaries))
        try:
            with service.lock:
                service.execution.schedule(service.load(first), "thinking", work)
                service.execution.schedule(service.load(second), "thinking", work)
            assert entered.wait(5)
            model.save_for(aid, ModelSettingsInput(base_url="https://personal.invalid/v1", model="alice-new", api_key="new-secret"))
            model.save(ModelSettingsInput(base_url="https://provider.invalid/v1", model="shared-new", api_key="shared-new-secret"))
            service.settings = replace(model.default, share_result_summaries=True)
        finally:
            release.set()
        for future in list(service.execution._pending):
            future.result(timeout=5)
        assert seen == [("alice-old", "alice-secret", True), ("shared-model", "shared-secret", True)]
        current = model.task_context(aid)
        with current:
            assert service.settings.model == "alice-new"
        view = alice.get(f"/api/sessions/{first}").json()
        assert view["model_configuration"]["model"] == "alice-old"
        assert "alice-secret" not in str(view)


def test_task_quota_and_submission_failure_release(tmp_path, monkeypatch):
    release = Event()
    with multi_clients(tmp_path) as (service, alice, bob, admin):
        ids = [alice.post("/api/sessions", json={}).json()["id"] for _ in range(2)]
        bid = bob.post("/api/sessions", json={}).json()["id"]
        try:
            with service.lock:
                service.execution.schedule(service.load(ids[0]), "thinking", lambda *_: release.wait(5))
                with pytest.raises(HTTPException) as error:
                    service.execution.schedule(service.load(ids[1]), "thinking", lambda *_: None)
                assert error.value.status_code == 429
                service.execution.schedule(service.load(bid), "thinking", lambda *_: None)
        finally:
            release.set()
        for future in list(service.execution._pending):
            future.result(timeout=5)
        def broken(*args):
            raise RuntimeError("submission failed")
        monkeypatch.setattr(service.execution.pool, "submit", broken)
        for _ in range(3):
            with service.lock, pytest.raises(RuntimeError, match="submission failed"):
                service.execution.schedule(service.load(ids[1]), "thinking", lambda *_: None)
        assert service.load(ids[1])["status"] == "idle"


def test_upload_reservations_are_atomic_and_release_after_error(tmp_path):
    with multi_clients(tmp_path, user_storage_bytes=100, total_storage_bytes=150) as (service, alice, bob, admin):
        # Empty sessions still have metadata; quotas specifically account input payload files.
        aid = alice.get("/api/me").json()["user"]["id"]
        bid = bob.get("/api/me").json()["user"]["id"]
        with service.quotas.reserve_upload(aid, 80):
            with pytest.raises(HTTPException):
                with service.quotas.reserve_upload(aid, 21):
                    pass
            with pytest.raises(HTTPException):
                with service.quotas.reserve_upload(bid, 71):
                    pass
            with service.quotas.reserve_upload(bid, 70):
                pass
        with pytest.raises(RuntimeError):
            with service.quotas.reserve_upload(aid, 100):
                raise RuntimeError()
        with service.quotas.reserve_upload(aid, 100):
            pass


def test_existing_uploads_count_and_http_failure_releases(tmp_path):
    from test_web_large_upload import minimal_h5ad
    data = minimal_h5ad(tmp_path)
    with multi_clients(tmp_path, user_storage_bytes=len(data) + 2000) as (service, alice, bob, admin):
        sid = alice.post("/api/sessions", json={}).json()["id"]
        url = f"/api/sessions/{sid}/uploads"
        assert alice.post(url, files={"file": ("a.h5ad", data)}).status_code == 200
        assert alice.post(url, files={"file": ("b.h5ad", data)}).status_code == 429
        aid = alice.get("/api/me").json()["user"]["id"]
        with service.quotas.reserve_upload(aid, 100):
            pass


@pytest.mark.parametrize("pause_at", ["worker_tail", "completion_callback"])
def test_approval_waits_until_planner_task_reservation_released(client, tmp_path, monkeypatch, pause_at):
    """A published plan must not invite approval while its planner still owns quota."""
    from web_support import new_session, h5ad, declare_counts, settle
    service = client.app.state.service
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    upload = client.post(url + "/uploads", files={"file": ("synthetic.h5ad", h5ad(tmp_path))}).json()
    declare_counts(client, sid, upload["uploads"][0]["id"])
    entered, release = Event(), Event()

    def pause():
        entered.set()
        assert release.wait(20)

    if pause_at == "worker_tail":
        original = service.think
        def think(*args):
            original(*args)  # Keep the actual provider/plan/input path; control only scheduling.
            pause()
        monkeypatch.setattr(service, "think", think)
    else:
        original = service.execution.pool.submit
        def submit(*args, **kwargs):
            future = original(*args, **kwargs)
            # Real Future is done before these callbacks release the task reservation.
            future.add_done_callback(lambda _: pause())
            return future
        monkeypatch.setattr(service.execution.pool, "submit", submit)

    try:
        assert client.post(url + "/messages", json={"text": "scRNA-seq raw counts QC"}).status_code == 200
        assert entered.wait(15)
        view = client.get(url).json()
        assert view["status"] == "thinking"
        assert view["presentation"]["stage"] == "working"
        assert [a["id"] for a in view["presentation"]["next_actions"]] == ["stop"]
        plan = view["plan"]
        early = client.post(url + "/approve", json={"plan_id": plan["id"], "plan_digest": plan["digest"]})
        assert early.status_code == 409
        assert "等待" in early.json()["user_message"]
        assert "没有完整完成" not in early.json()["user_message"]
        assert service.load(sid)["plan"]["status"] == "proposed"
        # A second session cannot consume the same owner's occupied task slot.
        sibling = client.post("/api/sessions", json={}).json()["id"]
        busy = client.post(f"/api/sessions/{sibling}/messages", json={"text": "Another question"})
        assert busy.status_code == 429
        assert "任务正在执行或排队" in busy.json()["user_message"]
    finally:
        release.set()

    view = settle(client, sid)
    assert view["status"] == "awaiting_approval"
    assert view["presentation"]["stage"] == "needs_approval"
    reply = client.post(url + "/approve", json={"plan_id": view["plan"]["id"], "plan_digest": view["plan"]["digest"]})
    assert reply.status_code == 200, reply.text
    finished = settle(client, sid)
    assert finished["plan"]["status"] == "completed"
    assert len(service.load(sid)["_tool_runs"]) == 1


@pytest.mark.parametrize("pause_at", ["worker_tail", "completion_callback"])
def test_stop_during_task_cleanup_remains_stopping_until_worker_releases(client, monkeypatch, pause_at):
    from web_support import new_session, settle
    service = client.app.state.service
    sid = new_session(client)["id"]
    entered, release = Event(), Event()
    def work(sid, epoch):
        with service.lock:
            state = service.load(sid)
            state["status"] = "idle"
            service.sessions.save(state)
        if pause_at == "worker_tail":
            entered.set()
            assert release.wait(15)
    if pause_at == "completion_callback":
        original = service.execution.pool.submit
        def submit(*args, **kwargs):
            future = original(*args, **kwargs)
            def pause(_):
                entered.set()
                assert release.wait(15)
            future.add_done_callback(pause)
            return future
        monkeypatch.setattr(service.execution.pool, "submit", submit)
    with service.lock:
        service.execution.schedule(service.load(sid), "thinking", work)
    try:
        assert entered.wait(10)
        stopped = client.post(f"/api/sessions/{sid}/stop", json={})
        assert stopped.status_code == 200
        assert stopped.json()["status"] == "stopping"
    finally:
        release.set()
    assert settle(client, sid)["status"] == "idle"
