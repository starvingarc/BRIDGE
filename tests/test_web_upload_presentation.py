from __future__ import annotations

from pathlib import Path

import h5py
from fastapi.testclient import TestClient

from bridge.web.app import Settings
from account_support import create_test_app as create_app, LOGIN


GIB = 1024 * 1024 * 1024


def settings(root: Path) -> Settings:
    return Settings(
        storage_root=root,
        model_base_url="https://provider.invalid/v1",
        model="test-model",
        model_api_key="private-key",
        origin="http://testserver",
        runtime_environment="production",
        diagnostics_enabled=False,
    )


def login(client: TestClient) -> None:
    response = client.post(
        "/api/login",
        json=LOGIN,
        headers={"Origin": "http://testserver"},
    )
    assert response.status_code == 200
    client.headers["Origin"] = "http://testserver"


def minimal_h5ad(tmp_path: Path) -> bytes:
    path = tmp_path / "minimal.h5ad"
    with h5py.File(path, "w") as handle:
        handle.attrs["encoding-type"] = "anndata"
        obs = handle.create_group("obs")
        obs.attrs["_index"] = "_index"
        obs.create_dataset("_index", data=[b"cell-1"])
        var = handle.create_group("var")
        var.attrs["_index"] = "_index"
        var.create_dataset("_index", data=[b"GENE1"])
        handle.create_dataset("X", data=[[1]])
    return path.read_bytes()


def test_authenticated_config_uses_large_file_contract_and_environment_cookie(tmp_path: Path) -> None:
    with TestClient(create_app(settings(tmp_path / "state"))) as client:
        unauthenticated = client.get("/api/config")
        assert unauthenticated.status_code == 401
        assert unauthenticated.json()["error_id"] == "request_failed"

        login(client)
        response = client.get("/api/config")
        assert response.status_code == 200
        assert response.json() == {
            "max_upload_bytes": 4 * GIB,
            "max_h5ad_logical_bytes": 4 * GIB,
            "max_h5ad_dataset_elements": 100_000_000,
        }


def test_upload_body_limit_keeps_machine_contract_beside_safe_errors(tmp_path: Path) -> None:
    with TestClient(create_app(settings(tmp_path / "state"))) as client:
        login(client)
        sid = client.post("/api/sessions").json()["id"]
        response = client.post(
            f"/api/sessions/{sid}/uploads",
            content=b"",
            headers={
                "Content-Length": str(4 * GIB + 65537),
                "Content-Type": "application/octet-stream",
            },
        )

        assert response.status_code == 413
        assert response.json() == {
            "detail": "request_too_large",
            "user_message": (
                f"文件超过当前上传上限（{4 * GIB} 字节）。"
                "请选择较小文件或联系管理员调整服务器限制。"
            ),
            "max_upload_bytes": 4 * GIB,
        }


def test_upload_preserves_researcher_projection_and_private_message_source(tmp_path: Path) -> None:
    data = minimal_h5ad(tmp_path)
    with TestClient(create_app(settings(tmp_path / "state"))) as client:
        login(client)
        sid = client.post("/api/sessions").json()["id"]
        response = client.post(
            f"/api/sessions/{sid}/uploads",
            files={"file": ("minimal.h5ad", data, "application/octet-stream")},
        )

        assert response.status_code == 200, response.text
        session = response.json()
        assert session["uploads"][0]["size"] == len(data)
        assert session["artifacts"] == []
        assert session["assessment"] is None
        assert session["presentation"]["diagnostics_available"] is False
        assert "diagnostics" not in session
        assert session["messages"][-1]["role"] == "assistant"
        assert session["messages"][-1]["source"] == "server_template"

        private = client.app.state.service.load(sid)
        assert private["messages"][-1]["source"] == "server_template"
