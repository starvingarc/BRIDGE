from dataclasses import replace
import json
from threading import Event

import httpx
import pytest
from fastapi.testclient import TestClient

from bridge.web.app import Settings
from account_support import create_test_app as create_app, LOGIN


def settings(tmp_path, configured=True):
    return Settings(storage_root=tmp_path / "private",
                    origin="http://testserver", model="old-model" if configured else "",
                    model_base_url="https://provider.invalid/v1" if configured else "",
                    model_api_key="old-secret" if configured else "")


def login(client):
    client.headers["Origin"] = "http://testserver"
    assert client.post("/api/login", json=LOGIN).status_code == 200


UPDATE = {"base_url": "https://provider.invalid/v1", "model": "new-model", "api_key": "new-secret", "action_protocol": "json"}


def test_saved_default_survives_restart_without_disclosing_key(tmp_path):
    config = settings(tmp_path)
    with TestClient(create_app(config)) as client:
        assert client.get("/api/model-settings").status_code == 401
        login(client)
        assert client.get("/api/model-settings").status_code == 200
        saved = client.put("/api/model-settings", json=UPDATE)
        assert saved.status_code == 200
        assert saved.json()["model"] == "new-model"
        assert saved.json()["has_api_key"] is True
        assert "secret" not in saved.text
        assert "no-store" in saved.headers["cache-control"]
        assert client.put("/api/model-settings", json=UPDATE, headers={"Origin": "http://evil.invalid"}).status_code == 403
    path = config.storage_root / "model-settings.json"
    assert path.stat().st_mode & 0o777 == 0o600
    with TestClient(create_app(config)) as client:
        login(client)
        assert client.get("/api/model-settings").json()["model"] == "new-model"
        assert client.app.state.service.settings.model_api_key == "new-secret"


def test_unconfigured_start_and_key_retention_require_same_endpoint(tmp_path):
    with TestClient(create_app(settings(tmp_path, False))) as client:
        login(client)
        assert client.get("/api/model-settings").json()["configured"] is False
        assert client.put("/api/model-settings", json={**UPDATE, "api_key": ""}).status_code == 422
        assert client.put("/api/model-settings", json=UPDATE).status_code == 200
        assert client.put("/api/model-settings", json={**UPDATE, "api_key": "", "model": "other"}).status_code == 200
        assert client.app.state.service.settings.model_api_key == "new-secret"
        for url in ("https://other.invalid/v1", "https://user:secret@provider.invalid/v1", "https://provider.invalid/v1?key=secret"):
            assert client.put("/api/model-settings", json={**UPDATE, "base_url": url, "api_key": ""}).status_code == 422


def test_connection_probe_is_bounded_synthetic_and_does_not_save(tmp_path, monkeypatch):
    original = httpx.Client
    requests = []
    def reply(request):
        requests.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})
    app = create_app(settings(tmp_path))
    with TestClient(app) as client:
        login(client)
        monkeypatch.setattr("bridge.web.model_settings.httpx.Client", lambda **kw: original(transport=httpx.MockTransport(reply), **kw))
        result = client.post("/api/model-settings/test", json=UPDATE)
        assert result.status_code == 200 and result.json()["ok"] is True
        assert app.state.service.settings.model == "old-model"
        assert not (app.state.service.root / "model-settings.json").exists()
        assert str(requests[0].url) == "https://provider.invalid/v1/chat/completions"
        assert requests[0].headers["Authorization"] == "Bearer new-secret"
        assert json.loads(requests[0].content)["messages"] == [{"role": "user", "content": "Reply with OK."}]
        assert client.post("/api/model-settings/test", json={**UPDATE, "action_protocol": "deepseek_tools"}).json()["ok"] is True
        assert json.loads(requests[1].content)["thinking"] == {"type": "disabled"}
        def failed(request):
            return httpx.Response(401, text="private-provider-error new-secret")
        monkeypatch.setattr("bridge.web.model_settings.httpx.Client", lambda **kw: original(transport=httpx.MockTransport(failed), **kw))
        failure = client.post("/api/model-settings/test", json=UPDATE)
        assert failure.json()["ok"] is False
        assert "new-secret" not in failure.text and "private-provider-error" not in failure.text


def test_running_and_queued_tasks_keep_their_model_snapshot(tmp_path):
    entered, release, finished = Event(), Event(), Event()
    seen = []
    app = create_app(replace(settings(tmp_path), user_task_limit=2))
    with TestClient(app) as client:
        login(client)
        service = app.state.service
        def work(sid, epoch):
            entered.set()
            assert release.wait(5)
            seen.append(service.settings.model)
            if len(seen) == 2:
                finished.set()
        try:
            for _ in range(2):
                sid = client.post("/api/sessions").json()["id"]
                with service.lock:
                    service.execution.schedule(service.load(sid), "thinking", work)
            assert entered.wait(5)
            assert client.put("/api/model-settings", json=UPDATE).status_code == 200
            assert service.settings.model == "new-model"
        finally:
            release.set()
        assert finished.wait(5)
        assert seen == ["old-model", "old-model"]
        new_finished = Event()
        def new_work(sid, epoch):
            seen.append(service.settings.model)
            new_finished.set()
        sid = client.post("/api/sessions").json()["id"]
        with service.lock:
            service.execution.schedule(service.load(sid), "thinking", new_work)
        assert new_finished.wait(5)
        assert seen == ["old-model", "old-model", "new-model"]


def test_rejects_insecure_saved_configuration(tmp_path):
    config = settings(tmp_path)
    with TestClient(create_app(config)) as client:
        login(client)
        assert client.put("/api/model-settings", json=UPDATE).status_code == 200
    path = config.storage_root / "model-settings.json"
    path.chmod(0o644)
    with pytest.raises(ValueError, match="model_configuration_invalid"):
        create_app(config)


def test_model_snapshot_does_not_freeze_resource_or_sharing_controls(tmp_path):
    config = replace(settings(tmp_path), share_result_summaries=True,
                     cell_state_measurement_spec_ref="bridge://test/measurement-spec")
    with TestClient(create_app(config)) as client:
        service = client.app.state.service
        with service.model_configuration.task_context():
            service.settings = replace(service.model_configuration.default,
                                       model="new-model", share_result_summaries=False,
                                       cell_state_measurement_spec_ref=None)
            assert service.settings.model == "old-model"
            assert service.settings.share_result_summaries is False
            assert service.settings.cell_state_measurement_spec_ref is None
        assert service.settings.model == "new-model"


def test_maximum_key_round_trips_and_environment_urls_cannot_expose_secrets(tmp_path):
    config = settings(tmp_path)
    # JSON escaping expands this otherwise valid header value beyond the old 16 KiB limit.
    long_key = '"' * 8192
    with TestClient(create_app(config)) as client:
        login(client)
        response = client.put("/api/model-settings", json={**UPDATE, "api_key": long_key})
        assert response.status_code == 200
        assert "api_key" not in response.json()
        invalid = client.put("/api/model-settings", json={**UPDATE, "api_key": "秘密"})
        assert invalid.status_code == 422 and "秘密" not in invalid.text
    with TestClient(create_app(config)) as client:
        assert client.app.state.service.settings.model_api_key == long_key
    for url in ("https://user:secret@provider.invalid/v1", "https://provider.invalid/v1?key=secret",
                "https://provider.invalid/v1#secret"):
        with pytest.raises(ValueError, match="invalid_server_configuration"):
            replace(config, model_base_url=url)


def test_probe_rejects_redirects_and_oversized_response_without_leaking_details(tmp_path, monkeypatch):
    original = httpx.Client
    with TestClient(create_app(settings(tmp_path))) as client:
        login(client)
        for response in (httpx.Response(302, headers={"Location": "https://other.invalid"}),
                         httpx.Response(200, content=b"x" * 70000)):
            requests = []
            def reply(request):
                requests.append(request)
                return response
            monkeypatch.setattr("bridge.web.model_settings.httpx.Client",
                                lambda **kw: original(transport=httpx.MockTransport(reply), **kw))
            result = client.post("/api/model-settings/test", json=UPDATE)
            assert result.status_code == 200 and result.json()["ok"] is False
            assert len(requests) == 1
            assert client.app.state.service.settings.model == "old-model"
