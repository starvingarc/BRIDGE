"""Conversation choices survive reloads and reach the queued provider request."""
from dataclasses import replace
import json
from threading import Event
import time

import httpx

from multiuser_support import multi_clients
from bridge.web.model_settings import ModelConfiguration

PROVIDER = {"id": "lab", "name": "Lab", "base_url": "https://personal.invalid/v1",
            "api_key": "synthetic-private-key", "models": ["first", "second"],
            "action_protocol": "deepseek_tools"}


def choose(client, sid, model="first", effort=None):
    return client.put(f"/api/sessions/{sid}/model-selection", json={
        "provider_id": "lab", "model": model, "effort": effort})


def catalog(monkeypatch, levels=("low", "high", "max"), default="high"):
    original = httpx.Client
    def client(settings, **kwargs):
        return original(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={
            "data": [{"id": model, "effort": {"supported_levels": list(levels), "default_level": default}}
                     for model in ("first", "second")]})))
    monkeypatch.setattr("bridge.web.model_settings.provider_client", client)


def test_selection_is_per_conversation_inherited_by_new_chats_and_reloaded(tmp_path, monkeypatch):
    catalog(monkeypatch)
    with multi_clients(tmp_path) as (service, alice, bob, admin):
        alice.put("/api/models/providers", json=PROVIDER).raise_for_status()
        a = alice.post("/api/sessions", json={}).json()["id"]
        b = alice.post("/api/sessions", json={}).json()["id"]
        assert alice.post("/api/models/providers/lab/capabilities", json={}).status_code == 200
        response = choose(alice, a, "second", "max")
        assert response.status_code == 200, response.text
        wanted = {"provider_id": "lab", "model": "second", "effort": "max"}
        assert response.json()["selection"] == wanted
        assert alice.get(f"/api/sessions/{a}").json()["model_selection"] == wanted
        assert alice.get(f"/api/sessions/{b}").json()["model_selection"]["model"] == "shared-model"
        assert alice.post("/api/sessions", json={}).json()["model_selection"] == wanted
        assert bob.post("/api/sessions", json={}).json()["model_selection"]["model"] == "shared-model"
        assert choose(bob, a).status_code == 404
        assert choose(admin, a).status_code == 404
        assert "synthetic-private-key" not in response.text and "shared-secret" not in response.text
        service.model_configuration = ModelConfiguration(service.root, service.model_configuration.default)
        assert alice.get(f"/api/sessions/{a}/model-selection").json()["selection"] == wanted
        assert alice.post("/api/sessions", json={}).json()["model_selection"] == wanted


def test_unknown_effort_or_removed_model_never_falls_back_or_starts_a_task(tmp_path, monkeypatch):
    catalog(monkeypatch)
    with multi_clients(tmp_path) as (service, alice, bob, admin):
        alice.put("/api/models/providers", json=PROVIDER).raise_for_status()
        sid = alice.post("/api/sessions", json={}).json()["id"]
        assert choose(alice, sid, effort="high").status_code == 409
        assert choose(alice, sid).status_code == 200
        assert alice.post("/api/models/providers/lab/capabilities", json={}).status_code == 200
        assert choose(alice, sid, effort="high").status_code == 200
        before = alice.get(f"/api/sessions/{sid}").json()
        bad = choose(alice, sid, effort="xhigh")
        assert bad.status_code == 409
        assert bad.json()["detail"] == "model_effort_unavailable"
        assert "思考" in bad.json()["user_message"]
        assert alice.get(f"/api/sessions/{sid}").json()["model_selection"] == before["model_selection"]
        alice.request("DELETE", "/api/models/providers/lab", json={}).raise_for_status()
        view = alice.get(f"/api/sessions/{sid}/model-selection").json()
        assert view["selection"] == before["model_selection"]
        assert view["availability"] == {"state": "unavailable", "reason": "model_selection_unavailable"}
        rejected = alice.post(f"/api/sessions/{sid}/messages", json={"text": "Discuss the records"})
        assert rejected.status_code == 409, rejected.text
        assert rejected.json()["detail"] == "model_selection_unavailable"
        assert "选择" in rejected.json()["user_message"]
        after = alice.get(f"/api/sessions/{sid}").json()
        assert after["status"] == "idle" and after["messages"] == before["messages"]
        assert not service.execution.has_pending(sid)


def test_capabilities_are_scoped_to_saved_configuration_and_bounded(tmp_path, monkeypatch):
    catalog(monkeypatch)
    with multi_clients(tmp_path) as (service, alice, bob, admin):
        alice.put("/api/models/providers", json=PROVIDER).raise_for_status()
        response = alice.post("/api/models/providers/lab/capabilities", json={})
        assert response.status_code == 200, response.text
        assert response.json()["capabilities"]["first"] == {
            "status": "supported", "supported_levels": ["low", "high", "max"], "default_level": "high"}
        assert bob.post("/api/models/providers/lab/capabilities", json={}).status_code == 409
        assert alice.get("/api/models").json()["providers"][1]["capabilities"]["first"]["status"] == "supported"
        alice.put("/api/models/providers", json={**PROVIDER, "api_key": "rotated-key"}).raise_for_status()
        assert alice.get("/api/models").json()["providers"][1]["capabilities"]["first"]["status"] == "unknown"
        sid = alice.post("/api/sessions", json={}).json()["id"]
        assert choose(alice, sid, effort="high").status_code == 409


def test_queued_and_running_tasks_keep_model_effort_and_credentials(tmp_path, monkeypatch):
    catalog(monkeypatch)
    started, release = Event(), Event()
    seen = []
    original = httpx.Client
    def client(settings, **kwargs):
        def reply(request):
            payload = json.loads(request.content)
            seen.append((payload, request.headers["authorization"]))
            if len(seen) == 1:
                started.set()
                assert release.wait(8)
            return httpx.Response(200, json={"choices": [{"message": {"content": None, "tool_calls": [
                {"id": "reply-1", "type": "function", "function": {"name": "reply", "arguments": json.dumps({"text": "Ready."})}}]}}]})
        return original(transport=httpx.MockTransport(reply))
    monkeypatch.setattr("bridge.web.provider.provider_client", client)
    with multi_clients(tmp_path, user_task_limit=2) as (service, alice, bob, admin):
        alice.put("/api/models/providers", json=PROVIDER).raise_for_status()
        assert alice.post("/api/models/providers/lab/capabilities", json={}).status_code == 200
        ids = [alice.post("/api/sessions", json={}).json()["id"] for _ in range(2)]
        assert choose(alice, ids[0], "first", "low").status_code == 200
        assert choose(alice, ids[1], "second", "max").status_code == 200
        try:
            alice.post(f"/api/sessions/{ids[0]}/messages", json={"text": "Hello first"}).raise_for_status()
            assert started.wait(3)
            alice.post(f"/api/sessions/{ids[1]}/messages", json={"text": "Hello second"}).raise_for_status()
            assert choose(alice, ids[0], "second", "high").status_code == 200
            assert choose(alice, ids[1], "first", "low").status_code == 200
            alice.request("DELETE", "/api/models/providers/lab", json={}).raise_for_status()
        finally:
            release.set()
        deadline = time.monotonic() + 5
        while any(service.execution.has_pending(sid) for sid in ids) and time.monotonic() < deadline:
            time.sleep(.02)
        assert len(seen) == 2
        assert [(body["model"], body["reasoning_effort"]) for body, _ in seen] == [("first", "low"), ("second", "max")]
        assert all(body["thinking"] == {"type": "enabled"} and "tool_choice" not in body for body, _ in seen)
        assert all(key == "Bearer synthetic-private-key" for _, key in seen)
        for sid, effort in zip(ids, ("low", "max")):
            state = alice.get(f"/api/sessions/{sid}").json()
            assert state["status"] == "idle", state.get("error")
            assert state["model_configuration"]["effort"] == effort
            assert state["model_configuration"]["provider_id"] == "lab"


def test_old_conversation_freezes_selection_on_first_load(tmp_path):
    with multi_clients(tmp_path) as (service, alice, bob, admin):
        alice.put("/api/models/providers", json=PROVIDER).raise_for_status()
        sid = alice.post("/api/sessions", json={}).json()["id"]
        with service.lock:
            state = service.sessions.load(sid)
            state.pop("model_selection", None)
            service.sessions.save(state)
        initial = alice.get(f"/api/sessions/{sid}").json()["model_selection"]
        alice.post("/api/models/select", json={"provider_id": "lab", "model": "second"}).raise_for_status()
        assert alice.get(f"/api/sessions/{sid}").json()["model_selection"] == initial


def test_capability_failure_is_not_a_recent_success_and_changed_connection_discards_refresh(tmp_path, monkeypatch):
    from threading import Thread
    catalog(monkeypatch)
    with multi_clients(tmp_path) as (service, alice, bob, admin):
        alice.put("/api/models/providers", json=PROVIDER).raise_for_status()
        before = alice.post("/api/models/providers/lab/capabilities", json={}).json()
        original = httpx.Client
        monkeypatch.setattr("bridge.web.model_settings.provider_client", lambda *a, **k: original(
            transport=httpx.MockTransport(lambda request: httpx.Response(401, text="synthetic-private-key"))))
        failed = alice.post("/api/models/providers/lab/capabilities", json={})
        assert failed.status_code == 200 and not failed.json()["ok"]
        assert failed.json()["checked_at"] == before["checked_at"]
        assert "synthetic-private-key" not in failed.text
        entered, release = Event(), Event()
        responses = []
        def reply(request):
            entered.set()
            assert release.wait(5)
            return httpx.Response(200, json={"data": [{"id": "first", "effort": {"supported_levels": ["max"]}}]})
        monkeypatch.setattr("bridge.web.model_settings.provider_client", lambda *a, **k: original(transport=httpx.MockTransport(reply)))
        thread = Thread(target=lambda: responses.append(alice.post("/api/models/providers/lab/capabilities", json={})))
        thread.start()
        try:
            assert entered.wait(3)
            alice.put("/api/models/providers", json={**PROVIDER, "api_key": "new-key"}).raise_for_status()
        finally:
            release.set()
            thread.join(5)
        assert len(responses) == 1 and responses[0].status_code == 409
        assert responses[0].json()["detail"] == "model_configuration_changed"
        assert alice.get("/api/models").json()["providers"][1]["capabilities"]["first"]["status"] == "unknown"


def test_capability_absence_malformed_or_explicitly_empty_are_distinct(tmp_path, monkeypatch):
    original = httpx.Client
    with multi_clients(tmp_path) as (service, alice, bob, admin):
        alice.put("/api/models/providers", json=PROVIDER).raise_for_status()
        for metadata, expected in (({}, "unknown"), ({"effort": {"supported_levels": []}}, "unsupported"),
                ({"effort": {"supported_levels": ["invented"]}}, "unknown"),
                ({"effort": {"supported_levels": ["low"], "default_level": "high"}}, "unknown")):
            monkeypatch.setattr("bridge.web.model_settings.provider_client", lambda *a, **k: original(
                transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"data": [{"id": "first", **metadata}]}))))
            result = alice.post("/api/models/providers/lab/capabilities", json={})
            assert result.status_code == 200 and result.json()["ok"]
            assert result.json()["capabilities"]["first"]["status"] == expected
            assert result.json()["capabilities"]["first"]["supported_levels"] == []
        assert alice.post("/api/models/providers/default/capabilities", json={}).status_code == 200
        assert alice.post("/api/models/providers/lab/capabilities", json={"owner_id": "f" * 32}).status_code == 422


def test_account_and_conversation_choices_survive_full_service_restart(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from account_support import create_test_app
    from multiuser_support import PASSWORD
    catalog(monkeypatch)
    with multi_clients(tmp_path) as (service, alice, bob, admin):
        alice.put("/api/models/providers", json=PROVIDER).raise_for_status()
        alice.post("/api/models/providers/lab/capabilities", json={}).raise_for_status()
        sid = alice.post("/api/sessions", json={}).json()["id"]
        chosen = choose(alice, sid, "second", "max").json()["selection"]
        settings = service.model_configuration.default
    with TestClient(create_test_app(settings)) as client:
        client.headers["Origin"] = settings.origin
        client.post("/api/login", json={"username": "alice", "password": PASSWORD}).raise_for_status()
        loaded = client.get(f"/api/sessions/{sid}/model-selection").json()
        assert loaded["selection"] == chosen and loaded["availability"]["state"] == "ready"
        assert client.post("/api/sessions", json={}).json()["model_selection"] == chosen


def test_declared_default_is_saved_and_explicit_recent_choice_wins(tmp_path, monkeypatch):
    catalog(monkeypatch)
    with multi_clients(tmp_path) as (service, alice, bob, admin):
        alice.put("/api/models/providers", json=PROVIDER).raise_for_status()
        alice.post("/api/models/select", json={"provider_id": "lab", "model": "first"}).raise_for_status()
        unresolved = alice.post("/api/sessions", json={}).json()["id"]
        assert alice.get(f"/api/sessions/{unresolved}").json()["model_selection"]["effort"] is None
        alice.post("/api/models/providers/lab/capabilities", json={}).raise_for_status()
        # A conversation created before discovery resolves once metadata arrives.
        assert alice.get(f"/api/sessions/{unresolved}").json()["model_selection"]["effort"] == "high"
        created = alice.post("/api/sessions", json={}).json()
        assert created["model_selection"] == {"provider_id": "lab", "model": "first", "effort": "high"}
        assert choose(alice, created["id"], effort="low").json()["selection"]["effort"] == "low"
        assert alice.post("/api/sessions", json={}).json()["model_selection"]["effort"] == "low"
        reset = choose(alice, created["id"])
        assert reset.status_code == 200 and reset.json()["selection"]["effort"] == "high"
        assert alice.post("/api/sessions", json={}).json()["model_selection"]["effort"] == "high"
        # Refreshing a provider's default does not overwrite a persisted choice.
        catalog(monkeypatch, default="max")
        alice.post("/api/models/providers/lab/capabilities", json={}).raise_for_status()
        assert alice.get(f"/api/sessions/{unresolved}").json()["model_selection"]["effort"] == "high"
        assert alice.post("/api/sessions", json={}).json()["model_selection"]["effort"] == "high"


def test_missing_or_stale_default_does_not_invent_effort(tmp_path, monkeypatch):
    catalog(monkeypatch, default=None)
    with multi_clients(tmp_path) as (service, alice, bob, admin):
        alice.put("/api/models/providers", json=PROVIDER).raise_for_status()
        alice.post("/api/models/select", json={"provider_id": "lab", "model": "first"}).raise_for_status()
        alice.post("/api/models/providers/lab/capabilities", json={}).raise_for_status()
        sid = alice.post("/api/sessions", json={}).json()["id"]
        assert choose(alice, sid).json()["selection"]["effort"] is None
        catalog(monkeypatch)
        alice.post("/api/models/providers/lab/capabilities", json={}).raise_for_status()
        alice.put("/api/models/providers", json={**PROVIDER, "api_key": "rotated"}).raise_for_status()
        assert alice.get(f"/api/sessions/{sid}").json()["model_selection"]["effort"] is None
        assert alice.post("/api/sessions", json={}).json()["model_selection"]["effort"] is None
