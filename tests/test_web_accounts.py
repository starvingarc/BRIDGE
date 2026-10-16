from concurrent.futures import ThreadPoolExecutor
import sqlite3

from fastapi import HTTPException
import pytest

from bridge.web.accounts import AccountStore, NOTICE_VERSION

PASSWORD = "correct horse battery staple"


def test_registration_is_unique_under_concurrency(tmp_path):
    store = AccountStore(tmp_path / "private")
    def register(name):
        try:
            return store.register(name, PASSWORD, NOTICE_VERSION)
        except HTTPException as exc:
            return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(register, [" Alice ", "alice"]))
    assert sum(item == 409 for item in results) == 1
    user = next(item for item in results if item != 409)
    assert user.username == "alice" and user.role == "user"
    assert store.authenticate("ALICE", PASSWORD).id == user.id
    assert PASSWORD.encode() not in (tmp_path / "private/accounts.sqlite3").read_bytes()
    assert (tmp_path / "private/accounts.sqlite3").stat().st_mode & 0o777 == 0o600


def test_login_revoke_reset_disable_and_restart(tmp_path):
    root = tmp_path / "private"
    store = AccountStore(root)
    user = store.register("alice", PASSWORD, NOTICE_VERSION)
    token = store.issue_login(user.id)
    assert store.resolve_login(token).id == user.id
    assert AccountStore(root).resolve_login(token).id == user.id
    assert token.encode() not in (root / "accounts.sqlite3").read_bytes()
    store.revoke_login(token)
    assert store.resolve_login(token) is None
    token = store.issue_login(user.id)
    temporary = store.reset_password(user.id)
    assert store.resolve_login(token) is None
    assert store.authenticate("alice", temporary).must_change_password
    with pytest.raises(HTTPException) as error:
        store.authenticate("alice", PASSWORD)
    assert error.value.status_code == 401
    store.change_password(user.id, temporary, PASSWORD + " new")
    assert not store.authenticate("alice", PASSWORD + " new").must_change_password
    token = store.issue_login(user.id)
    store.disable(user.id)
    assert store.resolve_login(token) is None
    with pytest.raises(HTTPException):
        store.authenticate("alice", PASSWORD + " new")


def test_registration_notice_validation_and_admin_bootstrap(tmp_path):
    store = AccountStore(tmp_path / "private")
    for name, password, notice in [("../bad", PASSWORD, NOTICE_VERSION),
                                  ("alice", "short", NOTICE_VERSION),
                                  ("alice", PASSWORD, "")]:
        with pytest.raises(HTTPException) as error:
            store.register(name, password, notice)
        assert error.value.status_code == 422
    admin = store.bootstrap_admin("operator", PASSWORD)
    assert admin.role == "admin"
    assert store.bootstrap_admin("operator", PASSWORD).id == admin.id
    with pytest.raises(HTTPException):
        store.bootstrap_admin("someone-else", PASSWORD)
    with pytest.raises(HTTPException):
        store.disable(admin.id)
    user = store.register("bob", PASSWORD, NOTICE_VERSION)
    assert user.role == "user"


def test_expired_login_and_rate_limit(tmp_path, monkeypatch):
    store = AccountStore(tmp_path / "private", cookie_ttl=10)
    user = store.register("alice", PASSWORD, NOTICE_VERSION)
    token = store.issue_login(user.id)
    monkeypatch.setattr("bridge.web.accounts.time.time", lambda: 10**12)
    assert store.resolve_login(token) is None
    store.limit("client", maximum=2, window=60)
    store.limit("client", maximum=2, window=60)
    with pytest.raises(HTTPException) as error:
        store.limit("client", maximum=2, window=60)
    assert error.value.status_code == 429


def test_account_database_rejects_symlink(tmp_path):
    external = tmp_path / "outside"
    external.write_text("untouched")
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    (root / "accounts.sqlite3").symlink_to(external)
    with pytest.raises((ValueError, OSError)):
        AccountStore(root)
    assert external.read_text() == "untouched"

from dataclasses import replace
from fastapi.testclient import TestClient
from account_support import create_test_app as create_app
from bridge.web.runtime import Settings


def multi_app(tmp_path):
    return create_app(Settings(storage_root=tmp_path / "web",
                               origin="http://testserver", model="", model_base_url="", model_api_key=""))


def test_registration_cannot_assign_admin_and_requires_notice(tmp_path):
    with TestClient(multi_app(tmp_path)) as client:
        client.headers["Origin"] = "http://testserver"
        config = client.get("/api/auth/config").json()
        assert config["mode"] == "accounts" and "管理员" in config["notice"]
        body = {"username": "alice", "password": PASSWORD, "notice_version": NOTICE_VERSION}
        assert client.post("/api/register", json={**body, "role": "admin"}).status_code == 422
        assert client.post("/api/register", json={**body, "notice_version": ""}).status_code == 422
        result = client.post("/api/register", json=body)
        assert result.status_code == 200
        assert client.get("/api/me").json()["user"]["role"] == "user"
        assert PASSWORD not in result.text
        client.post("/api/logout", json={})
        assert client.get("/api/me").status_code == 401
        assert client.post("/api/login", json={"token": "retired-token"}).status_code == 422
        assert client.post("/api/login", json={"username": "alice", "password": PASSWORD}).status_code == 200
        cookie = list(client.cookies.keys())[0]
        assert "accounts" in cookie


def test_password_reset_session_is_restricted_until_changed(tmp_path):
    app = multi_app(tmp_path)
    with TestClient(app) as client:
        client.headers["Origin"] = "http://testserver"
        user = app.state.service.accounts.register("alice", PASSWORD, NOTICE_VERSION)
        temporary = app.state.service.accounts.reset_password(user.id)
        assert client.post("/api/login", json={"username": "alice", "password": temporary}).status_code == 200
        assert client.get("/api/me").json()["user"]["must_change_password"] is True
        assert client.get("/api/sessions").status_code == 403
        assert client.post("/api/me/password", json={"old_password": temporary, "password": PASSWORD}).status_code == 200
        assert client.get("/api/me").status_code == 401
        assert client.post("/api/login", json={"username": "alice", "password": PASSWORD}).status_code == 200
        assert client.get("/api/me").json()["user"]["must_change_password"] is False
