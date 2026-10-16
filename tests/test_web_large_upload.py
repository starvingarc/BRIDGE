from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
from threading import Event
import time

import h5py
import pytest
from fastapi.testclient import TestClient

from bridge.web.app import Settings
from account_support import create_test_app as create_app, LOGIN


GIB = 1024 * 1024 * 1024


def minimal_h5ad(tmp_path: Path, *, extra_elements: int = 0) -> bytes:
    path = tmp_path / f"minimal-{extra_elements}.h5ad"
    with h5py.File(path, "w") as handle:
        handle.attrs["encoding-type"] = "anndata"
        obs = handle.create_group("obs")
        obs.attrs["_index"] = "_index"
        obs.create_dataset("_index", data=[b"cell-1"])
        var = handle.create_group("var")
        var.attrs["_index"] = "_index"
        var.create_dataset("_index", data=[b"GENE1"])
        handle.create_dataset("X", data=[[1]])
        if extra_elements:
            handle.create_dataset(
                "bounded-shape",
                shape=(extra_elements,),
                dtype="u1",
                chunks=True,
                fillvalue=0,
            )
    return path.read_bytes()


@contextmanager
def web_client(tmp_path: Path, **overrides):
    values = dict(
        storage_root=tmp_path / "private",
        model_base_url="https://provider.invalid/v1",
        model="test-model",
        model_api_key="private-key",
        origin="http://testserver",
    )
    values.update(overrides)
    app = create_app(Settings(**values))
    with TestClient(app) as client:
        client.headers["Origin"] = "http://testserver"
        yield client


def session(client: TestClient) -> str:
    assert client.post("/api/login", json=LOGIN).status_code == 200
    response = client.post("/api/sessions")
    assert response.status_code == 200
    return response.json()["id"]


def expected_upload_413(limit: int) -> dict:
    return {
        "detail": "request_too_large",
        "user_message": f"文件超过当前上传上限（{limit} 字节）。请选择较小文件或联系管理员调整服务器限制。",
        "max_upload_bytes": limit,
    }


def expected_safe_500() -> dict:
    return {
        "error_version": 1,
        "error_id": "request_failed",
        "user_message": "请求未能完成，请稍后重试。",
        "results_state": "unknown",
    }


def test_settings_have_finite_large_file_defaults_and_reject_unbounded_values(tmp_path):
    values = dict(
        storage_root=tmp_path / "private",
        model_base_url="https://provider.invalid/v1",
        model="test-model",
        model_api_key="private-key",
    )
    settings = Settings(**values)
    assert settings.max_upload_bytes == 4 * GIB
    assert settings.max_h5ad_logical_bytes == 4 * GIB
    assert settings.max_h5ad_dataset_elements == 100_000_000
    for field, value in (
        ("max_upload_bytes", None),
        ("max_upload_bytes", 0),
        ("max_upload_bytes", 16 * GIB + 1),
        ("max_h5ad_logical_bytes", 0),
        ("max_h5ad_dataset_elements", 0),
    ):
        with pytest.raises(ValueError, match="^invalid_server_configuration$"):
            Settings(**values, **{field: value})


def test_authenticated_config_reports_actual_upload_limit(tmp_path):
    with web_client(
        tmp_path,
        max_upload_bytes=12345,
        max_h5ad_logical_bytes=23456,
        max_h5ad_dataset_elements=34567,
    ) as client:
        assert client.get("/api/config").status_code == 401
        session(client)
        response = client.get("/api/config")
        assert response.status_code == 200
        assert response.json() == {
            "max_upload_bytes": 12345,
            "max_h5ad_logical_bytes": 23456,
            "max_h5ad_dataset_elements": 34567,
        }


def test_upload_accepts_exact_file_limit_and_records_stream_hash(tmp_path):
    data = minimal_h5ad(tmp_path)
    with web_client(tmp_path, max_upload_bytes=len(data)) as client:
        sid = session(client)
        response = client.post(
            f"/api/sessions/{sid}/uploads",
            files={"file": ("exact.h5ad", data)},
        )
        assert response.status_code == 200, response.text
        upload = response.json()["uploads"][0]
        state = client.app.state.service.load(sid)
        assert upload["size"] == len(data)
        assert state["_uploads"][upload["id"]]["sha256"] == hashlib.sha256(data).hexdigest()


def test_upload_rejects_one_byte_over_actual_file_limit_and_cleans_files(tmp_path):
    data = minimal_h5ad(tmp_path)
    limit = len(data) - 1
    with web_client(tmp_path, max_upload_bytes=limit) as client:
        sid = session(client)
        response = client.post(
            f"/api/sessions/{sid}/uploads",
            files={"file": ("over.h5ad", data)},
        )
        assert response.status_code == 413
        assert response.json() == expected_upload_413(limit)
        directory = client.app.state.service.root / sid / "uploads"
        assert not directory.exists() or list(directory.iterdir()) == []
        assert client.app.state.service.load(sid)["uploads"] == []


def test_upload_content_length_and_received_body_limits_share_413_contract(tmp_path):
    limit = 1024
    with web_client(tmp_path, max_upload_bytes=limit) as client:
        sid = session(client)
        url = f"/api/sessions/{sid}/uploads"
        declared = client.post(
            url,
            content=b"",
            headers={
                "Content-Length": str(limit + 65537),
                "Content-Type": "application/octet-stream",
            },
        )
        assert declared.status_code == 413
        assert declared.json() == expected_upload_413(limit)

        received = client.post(
            url,
            files={"file": ("underreported.h5ad", b"x" * (limit + 65537))},
            headers={"Content-Length": "1"},
        )
        assert received.status_code == 413
        assert received.json() == expected_upload_413(limit)


@pytest.mark.parametrize(
    ("logical_limit", "element_limit", "reason"),
    [
        (1, 100_000_000, "h5ad_logical_size_limit"),
        (4 * GIB, 1, "h5ad_dataset_element_limit"),
    ],
)
def test_h5ad_resource_limits_remain_bounded_and_configurable(
    tmp_path, logical_limit, element_limit, reason
):
    data = minimal_h5ad(tmp_path, extra_elements=2)
    with web_client(
        tmp_path,
        max_upload_bytes=len(data),
        max_h5ad_logical_bytes=logical_limit,
        max_h5ad_dataset_elements=element_limit,
    ) as client:
        sid = session(client)
        response = client.post(
            f"/api/sessions/{sid}/uploads",
            files={"file": ("bounded.h5ad", data)},
        )
        assert response.status_code == 413
        assert response.json() == {
            "detail": "h5ad_resource_limit",
            "reason": reason,
            "user_message": "H5AD 的解压后数据规模超过当前服务器安全上限。请使用较小文件或联系管理员调整限制。",
            "max_h5ad_logical_bytes": logical_limit,
            "max_h5ad_dataset_elements": element_limit,
        }
        directory = client.app.state.service.root / sid / "uploads"
        assert list(directory.iterdir()) == []


def test_invalid_h5ad_failure_cleans_private_temporary_file(tmp_path):
    data = b"\x89HDF\r\n\x1a\n" + b"not an HDF5 file"
    with web_client(tmp_path, max_upload_bytes=len(data)) as client:
        sid = session(client)
        response = client.post(
            f"/api/sessions/{sid}/uploads",
            files={"file": ("invalid.h5ad", data)},
        )
        assert response.status_code == 400
        directory = client.app.state.service.root / sid / "uploads"
        assert list(directory.iterdir()) == []


def test_restart_removes_interrupted_and_unregistered_upload_files(tmp_path):
    storage = tmp_path / "private"
    with web_client(tmp_path) as client:
        sid = session(client)
        directory = client.app.state.service.root / sid / "uploads"
        directory.mkdir(mode=0o700)
        (directory / ("." + "a" * 32 + ".upload")).write_bytes(b"partial")
        (directory / ("b" * 32 + ".h5ad")).write_bytes(b"orphan")
    values = dict(
        storage_root=storage,
        model_base_url="https://provider.invalid/v1",
        model="test-model",
        model_api_key="private-key",
        origin="http://testserver",
    )
    second = create_app(Settings(**values))
    try:
        directory = second.state.service.root / sid / "uploads"
        assert list(directory.iterdir()) == []
    finally:
        second.state.service.execution.pool.shutdown()


def test_upload_stream_does_not_hold_global_lock_and_same_session_does_not_duplicate(
    tmp_path, monkeypatch
):
    from bridge.web import http as app_module

    data = minimal_h5ad(tmp_path)
    entered = Event()
    release = Event()
    original = app_module.stream_upload

    def paused(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return original(*args, **kwargs)

    monkeypatch.setattr(app_module, "stream_upload", paused)
    with web_client(tmp_path, max_upload_bytes=len(data)) as client:
        sid = session(client)
        session(client)
        url = f"/api/sessions/{sid}/uploads"
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(
                client.post,
                url,
                files={"file": ("first.h5ad", data)},
            )
            assert entered.wait(5)
            started = time.monotonic()
            assert client.get("/api/sessions").status_code == 200
            assert time.monotonic() - started < 1.0
            duplicate = client.post(
                url,
                files={"file": ("duplicate.h5ad", data)},
            )
            assert duplicate.status_code == 409
            assert duplicate.json() == {
                "error_version": 1,
                "error_id": "execution_incomplete",
                "user_message": "这次执行没有完整完成；当前没有可确认的已有结果。",
                "results_state": "not_available",
            }
            release.set()
            assert first.result(timeout=10).status_code == 200
        assert len(client.app.state.service.load(sid)["uploads"]) == 1


def test_upload_releases_reservation_when_directory_preparation_fails(tmp_path, monkeypatch):
    from bridge.web import http as app_module

    data = minimal_h5ad(tmp_path)
    original = app_module.ensure_private_directory
    failed = False

    def fail_upload_directory_once(path, *args, **kwargs):
        nonlocal failed
        if Path(path).name == "uploads" and not failed:
            failed = True
            raise OSError("simulated_upload_directory_failure")
        return original(path, *args, **kwargs)

    with web_client(tmp_path, max_upload_bytes=len(data)) as client:
        sid = session(client)
        service = client.app.state.service
        monkeypatch.setattr(app_module, "ensure_private_directory", fail_upload_directory_once)

        failed_response = client.post(
            f"/api/sessions/{sid}/uploads",
            files={"file": ("first.h5ad", data)},
        )
        assert failed_response.status_code == 500
        assert failed_response.json() == expected_safe_500()

        assert sid not in service.uploads_in_progress
        retry = client.post(
            f"/api/sessions/{sid}/uploads",
            files={"file": ("retry.h5ad", data)},
        )
        assert retry.status_code == 200, retry.text


def test_upload_releases_reservation_when_temporary_cleanup_fails(tmp_path, monkeypatch):
    data = minimal_h5ad(tmp_path)
    invalid = b"\x89HDF\r\n\x1a\nnot-an-hdf5-file"
    original = Path.unlink

    def fail_temporary_cleanup(path, *args, **kwargs):
        if path.suffix == ".upload":
            raise OSError("simulated_temporary_cleanup_failure")
        return original(path, *args, **kwargs)

    with web_client(tmp_path, max_upload_bytes=len(data)) as client:
        sid = session(client)
        service = client.app.state.service
        monkeypatch.setattr(Path, "unlink", fail_temporary_cleanup)

        failed_response = client.post(
            f"/api/sessions/{sid}/uploads",
            files={"file": ("invalid.h5ad", invalid)},
        )
        assert failed_response.status_code == 500
        assert failed_response.json() == expected_safe_500()

        assert sid not in service.uploads_in_progress
        directory = service.root / sid / "uploads"
        assert [path.suffix for path in directory.iterdir()] == [".upload"]

        monkeypatch.setattr(Path, "unlink", original)
        retry = client.post(
            f"/api/sessions/{sid}/uploads",
            files={"file": ("retry.h5ad", data)},
        )
        assert retry.status_code == 200, retry.text


def test_upload_releases_reservation_when_destination_cleanup_fails(tmp_path, monkeypatch):
    from bridge.web import intake_autofill

    data = minimal_h5ad(tmp_path)
    original_unlink = Path.unlink
    original_ensure = intake_autofill.ensure

    def fail_registration_once(*args, **kwargs):
        monkeypatch.setattr(intake_autofill, "ensure", original_ensure)
        raise OSError("simulated_registration_failure")

    def fail_destination_cleanup(path, *args, **kwargs):
        if path.suffix == ".h5ad":
            raise OSError("simulated_destination_cleanup_failure")
        return original_unlink(path, *args, **kwargs)

    with web_client(tmp_path, max_upload_bytes=len(data)) as client:
        sid = session(client)
        service = client.app.state.service
        monkeypatch.setattr(intake_autofill, "ensure", fail_registration_once)
        monkeypatch.setattr(Path, "unlink", fail_destination_cleanup)

        failed_response = client.post(
            f"/api/sessions/{sid}/uploads",
            files={"file": ("first.h5ad", data)},
        )
        assert failed_response.status_code == 500
        assert failed_response.json() == expected_safe_500()

        assert sid not in service.uploads_in_progress
        directory = service.root / sid / "uploads"
        assert [path.suffix for path in directory.iterdir()] == [".h5ad"]
        assert service.load(sid)["uploads"] == []

        monkeypatch.setattr(Path, "unlink", original_unlink)
        retry = client.post(
            f"/api/sessions/{sid}/uploads",
            files={"file": ("retry.h5ad", data)},
        )
        assert retry.status_code == 200, retry.text
        registered = retry.json()["uploads"][0]["id"]
        assert (directory / f"{registered}.h5ad").is_file()


def test_h5ad_intake_paths_use_checked_streams_and_detect_hash_changes(tmp_path, monkeypatch):
    from bridge.web import sessions as app_module
    from bridge.web import intake_autofill, intake_batches, intake_sources

    data = minimal_h5ad(tmp_path)
    original = app_module.read_file

    def no_h5ad_bytes(path, limit=None):
        if Path(path).suffix == ".h5ad":
            pytest.fail("H5AD was loaded through the whole-file byte helper")
        return original(path, limit)

    monkeypatch.setattr(app_module, "read_file", no_h5ad_bytes)
    with web_client(tmp_path, max_upload_bytes=len(data)) as client:
        sid = session(client)
        response = client.post(
            f"/api/sessions/{sid}/uploads",
            files={"file": ("streamed.h5ad", data)},
        )
        assert response.status_code == 200, response.text
        aid = response.json()["uploads"][0]["id"]
        service = client.app.state.service
        state = service.load(sid)
        observed = service.intake.observed(state, aid)
        assert observed["n_observations"] == 1
        assert intake_sources.metadata(service, state, aid)["sources"]
        assert isinstance(intake_batches.profiles(service, state, aid), list)
        assert intake_autofill.model_context(service, state, aid)["purpose"] == "intake_extraction"

        path = service.root / sid / "uploads" / f"{aid}.h5ad"
        with path.open("r+b") as stream:
            stream.seek(-1, os.SEEK_END)
            stream.write(b"x")
        with pytest.raises(ValueError, match="^input_integrity_mismatch$"):
            service.intake.observed(service.load(sid), aid)


def test_settings_reads_explicit_large_file_limits(tmp_path, monkeypatch):
    from bridge.web.runtime import settings_from_environment

    environment = {
        "BRIDGE_WEB_STORAGE": str(tmp_path / "startup-private"),

        "BRIDGE_WEB_MODEL_BASE_URL": "https://provider.invalid/v1",
        "BRIDGE_WEB_MODEL": "test-model",
        "BRIDGE_WEB_MODEL_API_KEY": "private-key",
        "BRIDGE_WEB_MAX_UPLOAD_BYTES": "12345",
        "BRIDGE_WEB_MAX_H5AD_LOGICAL_BYTES": "23456",
        "BRIDGE_WEB_MAX_H5AD_DATASET_ELEMENTS": "34567",
    }
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("BRIDGE_WEB_TRUSTED_ANCESTORS", raising=False)
    settings = settings_from_environment()
    assert settings.max_upload_bytes == 12345
    assert settings.max_h5ad_logical_bytes == 23456
    assert settings.max_h5ad_dataset_elements == 34567


@pytest.mark.parametrize("value", ["0", "unlimited", str(16 * GIB + 1)])
def test_settings_rejects_invalid_upload_limit_configuration(tmp_path, monkeypatch, value):
    from bridge.web.runtime import settings_from_environment

    environment = {
        "BRIDGE_WEB_STORAGE": str(tmp_path / "startup-private"),

        "BRIDGE_WEB_MODEL_BASE_URL": "https://provider.invalid/v1",
        "BRIDGE_WEB_MODEL": "test-model",
        "BRIDGE_WEB_MODEL_API_KEY": "private-key",
        "BRIDGE_WEB_MAX_UPLOAD_BYTES": value,
    }
    for key, configured in environment.items():
        monkeypatch.setenv(key, configured)
    monkeypatch.delenv("BRIDGE_WEB_TRUSTED_ANCESTORS", raising=False)
    with pytest.raises(ValueError, match="^invalid_server_configuration$"):
        settings_from_environment()


@pytest.mark.skipif(
    not os.environ.get("BRIDGE_TEST_LARGE_H5AD"),
    reason="requires an explicitly authorized private H5AD path",
)
def test_authorized_large_h5ad_reaches_intake_without_scientific_execution(tmp_path):
    source = Path(os.environ["BRIDGE_TEST_LARGE_H5AD"])
    assert source.stat().st_size > 512 * 1024 * 1024
    digest = hashlib.sha256()
    with source.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)

    with web_client(tmp_path) as client:
        sid = session(client)
        with source.open("rb") as stream:
            response = client.post(
                f"/api/sessions/{sid}/uploads",
                files={"file": ("authorized-large.h5ad", stream, "application/octet-stream")},
            )
        assert response.status_code == 200, response.text
        upload = response.json()["uploads"][0]
        service = client.app.state.service
        state = service.load(sid)
        assert upload["size"] == source.stat().st_size
        assert state["_uploads"][upload["id"]]["sha256"] == digest.hexdigest()
        intake = client.get(f"/api/sessions/{sid}/intake", params={"upload_id": upload["id"]})
        assert intake.status_code == 200, intake.text
        assert service.load(sid)["plan"] is None
