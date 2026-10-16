from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bridge.web.app import Settings
from account_support import create_test_app as create_app, LOGIN




def _runtime():
    try:
        return importlib.import_module("bridge.web.runtime")
    except ModuleNotFoundError:
        pytest.fail("bridge.web.runtime is required")


def _settings(
    root: Path,
    environment: str = "production",
    *,
    diagnostics: bool = False,
) -> Settings:
    return Settings(
        storage_root=root,
        model_base_url="http://provider.invalid/v1",
        model="test-model",
        model_api_key="test-key",
        origin="http://testserver",
        runtime_environment=environment,
        diagnostics_enabled=diagnostics,
    )


@pytest.mark.parametrize("environment", ["acceptance", "production"])
def test_diagnostics_configuration_is_rejected_outside_development(
    tmp_path: Path, environment: str,
) -> None:
    with pytest.raises(ValueError, match="invalid_server_configuration"):
        _settings(tmp_path / environment, environment, diagnostics=True)


def test_empty_storage_is_bound_to_runtime_environment(tmp_path: Path) -> None:
    runtime = _runtime()
    root = tmp_path / "state"
    binding = runtime.bind_storage_environment(root, "development")
    marker = root / ".bridge-runtime-environment.json"

    assert binding.model_dump(mode="json") == {
        "object_version": "1.0.0",
        "runtime_environment": "development",
    }
    assert json.loads(marker.read_text()) == binding.model_dump(mode="json")
    assert marker.stat().st_mode & 0o777 == 0o600


def test_nonempty_legacy_storage_requires_explicit_binding_without_rewrite(
    tmp_path: Path,
) -> None:
    runtime = _runtime()
    root = tmp_path / "state"
    session = root / ("a" * 32)
    session.mkdir(parents=True)
    root.chmod(0o700)
    session.chmod(0o700)
    original = session / "session.json"
    original.write_bytes(b'{"legacy":true}')
    before = original.read_bytes()

    with pytest.raises(ValueError, match="storage_environment_binding_required"):
        runtime.bind_storage_environment(root, "production")

    binding = runtime.bind_storage_environment(
        root, "production", allow_existing_unbound=True,
    )
    assert binding.runtime_environment == "production"
    assert original.read_bytes() == before


def test_bound_storage_refuses_another_environment_even_with_override(
    tmp_path: Path,
) -> None:
    runtime = _runtime()
    root = tmp_path / "state"
    runtime.bind_storage_environment(root, "development")

    with pytest.raises(ValueError, match="storage_environment_mismatch"):
        runtime.bind_storage_environment(
            root, "acceptance", allow_existing_unbound=True,
        )


def test_environment_cookie_names_are_distinct() -> None:
    runtime = _runtime()
    assert runtime.session_cookie_name("development") == "bridge_development_accounts_session"
    assert runtime.session_cookie_name("production") == "bridge_production_accounts_session"


def test_same_host_environment_logins_coexist_and_logout_is_scoped(
    tmp_path: Path,
) -> None:
    runtime = _runtime()
    dev = TestClient(create_app(_settings(tmp_path / "dev", "development")))
    prod = TestClient(
        create_app(_settings(tmp_path / "prod", "production"))
    )
    origin = {"Origin": "http://testserver"}

    dev_login = dev.post("/api/login", json=LOGIN, headers=origin)
    prod_login = prod.post("/api/login", json=LOGIN, headers=origin)
    dev_name = runtime.session_cookie_name("development")
    prod_name = runtime.session_cookie_name("production")
    dev_cookie = dev_login.cookies.get(dev_name)
    prod_cookie = prod_login.cookies.get(prod_name)
    browser = {dev_name: dev_cookie, prod_name: prod_cookie}

    assert dev_login.status_code == 200
    assert prod_login.status_code == 200
    assert dev_cookie and prod_cookie
    assert dev.get("/api/sessions", cookies=browser).status_code == 200
    assert prod.get("/api/sessions", cookies=browser).status_code == 200

    logout = dev.post("/api/logout", headers=origin, cookies=browser)
    assert logout.status_code == 200
    assert dev_name in logout.headers["set-cookie"]
    assert prod_name not in logout.headers["set-cookie"]
    assert prod.get("/api/sessions", cookies=browser).status_code == 200

    prod.cookies.clear()
    assert prod.get(
        "/api/sessions", cookies={prod_name: dev_cookie},
    ).status_code == 401


def test_service_creation_enforces_storage_binding(tmp_path: Path) -> None:
    root = tmp_path / "state"
    root.mkdir()
    root.chmod(0o700)
    existing = root / "existing-private-record"
    existing.mkdir()
    existing.chmod(0o700)

    with pytest.raises(ValueError, match="multiuser_storage_not_ready"):
        from bridge.web.app import create_app as uninitialized_app
        uninitialized_app(_settings(root, "production"))
