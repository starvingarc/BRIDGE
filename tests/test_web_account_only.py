"""Account authentication is the only supported Web login contract."""
import pytest
from fastapi.testclient import TestClient
from bridge.web.app import create_app
from bridge.web.runtime import settings_from_environment
from bridge.web.account_admin import initialize

PASSWORD = "synthetic-account-password"


def environment(monkeypatch, tmp_path):
    monkeypatch.delenv("BRIDGE_WEB_TOKEN", raising=False)
    monkeypatch.delenv("BRIDGE_WEB_MULTI_USER", raising=False)
    monkeypatch.setenv("BRIDGE_WEB_STORAGE", str(tmp_path / "accounts"))
    monkeypatch.setenv("BRIDGE_WEB_ORIGIN", "http://testserver")
    monkeypatch.setenv("BRIDGE_RUNTIME_ENV", "acceptance")


def test_default_start_uses_accounts_and_rejects_shared_token_and_old_cookie(monkeypatch, tmp_path):
    environment(monkeypatch, tmp_path)
    root = tmp_path / "accounts"
    initialize(root, "operator", PASSWORD, "acceptance")
    settings = settings_from_environment()
    with TestClient(create_app(settings)) as client:
        client.headers["Origin"] = settings.origin
        assert client.get("/api/auth/config").json()["mode"] == "accounts"
        rejected = client.post("/api/login", json={"token": "retired-shared-token"})
        assert rejected.status_code == 422 and not rejected.cookies
        client.cookies.set("bridge_acceptance_session", "retired-cookie")
        assert client.get("/api/sessions").status_code == 401
        assert client.post("/api/login", json={"username": "operator", "password": PASSWORD}).status_code == 200
        assert client.get("/api/me").json()["user"]["username"] == "operator"
        assert client.post("/api/logout", json={}).status_code == 200
        assert client.get("/api/sessions").status_code == 401


@pytest.mark.parametrize("name,value", [("BRIDGE_WEB_TOKEN", "retired-shared-token"), ("BRIDGE_WEB_MULTI_USER", "0"), ("BRIDGE_WEB_MULTI_USER", "1")])
def test_retired_auth_configuration_requires_explicit_removal(monkeypatch, tmp_path, name, value):
    environment(monkeypatch, tmp_path)
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError, match="retired_auth_configuration"):
        settings_from_environment()
