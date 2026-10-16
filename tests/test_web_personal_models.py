from dataclasses import replace
import httpx
import pytest

from multiuser_support import multi_clients
from bridge.web.model_settings import ModelConfiguration, ModelSettingsInput

PERSONAL = {"base_url": "https://personal.invalid/v1", "model": "my-model",
            "api_key": "my-private-secret", "action_protocol": "json"}


def test_personal_settings_do_not_change_default_or_other_users(tmp_path):
    with multi_clients(tmp_path) as (service, alice, bob, admin):
        user_id = alice.get("/api/me").json()["user"]["id"]
        assert alice.get("/api/me/model-settings").json()["source"] == "default"
        result = alice.put("/api/me/model-settings", json=PERSONAL)
        assert result.status_code == 200
        assert result.json()["source"] == "personal"
        assert result.json()["personal"]["model"] == "my-model"
        assert "my-private-secret" not in result.text and "shared-secret" not in result.text
        assert bob.get("/api/me/model-settings").json()["source"] == "default"
        assert service.model_configuration.default.model == "shared-model"
        snapshot = service.model_configuration.snapshot_for(user_id)
        assert snapshot.model_api_key == "my-private-secret"
        assert snapshot.model_endpoint_restricted is True
        restarted = ModelConfiguration(service.root, service.model_configuration.default)
        assert restarted.snapshot_for(user_id).model == "my-model"
        assert alice.post("/api/me/model-settings/select", json={"source": "default"}).json()["source"] == "default"
        assert service.model_configuration.snapshot_for(user_id).model == "shared-model"
        assert alice.post("/api/me/model-settings/select", json={"source": "personal"}).status_code == 200
        assert alice.request("DELETE", "/api/me/model-settings", json={}).status_code == 200
        assert alice.get("/api/me/model-settings").json()["personal"] is None


def test_blank_personal_key_cannot_inherit_default(tmp_path):
    with multi_clients(tmp_path) as (service, alice, bob, admin):
        same_global = {**PERSONAL, "base_url": "https://provider.invalid/v1", "api_key": ""}
        assert alice.put("/api/me/model-settings", json=same_global).status_code == 422
        assert alice.put("/api/me/model-settings", json=PERSONAL).status_code == 200
        assert alice.put("/api/me/model-settings", json={**PERSONAL, "model": "next", "api_key": ""}).status_code == 200
        assert bob.put("/api/me/model-settings", json={**PERSONAL, "api_key": ""}).status_code == 422
        assert alice.put("/api/me/model-settings", json={**same_global, "model": "next"}).status_code == 422
        assert alice.put("/api/me/model-settings", json={**PERSONAL, "user_id": "a" * 32}).status_code == 422


def test_personal_failure_never_falls_back_or_saves_probe(tmp_path, monkeypatch):
    with multi_clients(tmp_path) as (service, alice, bob, admin):
        seen = []
        original_client = httpx.Client
        def failure(request):
            seen.append((str(request.url), request.headers.get("authorization")))
            return httpx.Response(401, text="my-private-secret upstream error")
        def client(settings, *, timeout, trust_env=True):
            return original_client(transport=httpx.MockTransport(failure), timeout=timeout)
        monkeypatch.setattr("bridge.web.model_settings.provider_client", client)
        response = alice.post("/api/me/model-settings/test", json=PERSONAL)
        assert response.status_code == 200 and response.json()["ok"] is False
        assert "my-private-secret" not in response.text
        assert seen == [("https://personal.invalid/v1/chat/completions", "Bearer my-private-secret")]
        assert alice.get("/api/me/model-settings").json()["personal"] is None
        assert service.model_configuration.default.model_api_key == "shared-secret"


def test_personal_literal_private_endpoint_requires_operator_allowlist(tmp_path):
    with multi_clients(tmp_path) as (service, alice, bob, admin):
        for url in ("http://example.org/v1", "https://127.0.0.1/v1", "https://169.254.169.254/v1",
                    "https://[::1]/v1", "https://10.0.0.5/v1"):
            assert alice.put("/api/me/model-settings", json={**PERSONAL, "base_url": url}).status_code == 422
