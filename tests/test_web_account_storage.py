import json
import hashlib
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from bridge.web.app import Settings, create_app
from bridge.web.service import Service
from bridge.web.account_admin import initialize, validate_storage, backup, restore
from bridge.web.launcher import storage_lock
from bridge.web.sessions import write_file
from multiuser_support import PASSWORD


def config(root, **options):
    return Settings(storage_root=root, model="synthetic", model_base_url="https://provider.invalid/v1", model_api_key="synthetic-secret", origin="http://testserver", **options)


def test_initialization_is_empty_idempotent_and_keeps_admin_identity(tmp_path):
    root = tmp_path / "accounts"
    admin = initialize(root, "operator", PASSWORD, "production")
    assert initialize(root, "operator", PASSWORD, "production") == admin
    assert not [item for item in root.iterdir() if item.is_dir()]
    assert json.loads((root / ".bridge-runtime-environment.json").read_text())["object_version"] == "2.0.0"
    with pytest.raises(Exception):
        initialize(root, "different-operator", PASSWORD, "production")
    validate_storage(root)
    with TestClient(create_app(config(root))) as client:
        assert client.get("/api/auth/config").json()["mode"] == "accounts"
    from bridge.web.sessions import SessionStore
    from bridge.storage.private_paths import ensure_private_directory
    legacy = SessionStore(tmp_path / "legacy", "production")
    sid = "a" * 32
    ensure_private_directory(legacy.root / sid)
    legacy.save({"id": sid, "status": "idle", "messages": []})
    original = (legacy.root / sid / "session.json").read_bytes()
    with pytest.raises(ValueError, match="multiuser_storage_not_ready"):
        create_app(config(legacy.root))
    with pytest.raises(ValueError, match="empty_directory"):
        initialize(legacy.root, "operator", PASSWORD, "production")
    assert (legacy.root / sid / "session.json").read_bytes() == original


def test_unowned_or_interrupted_restore_blocks_start(tmp_path):
    root = tmp_path / "accounts"
    admin = initialize(root, "operator", PASSWORD, "production")
    service = Service(config(root, ))
    state = service.create(owner_id=admin.id)
    service.execution.shutdown()
    guard = root / ".bridge-restore-in-progress"
    write_file(guard, b"interrupted")
    with pytest.raises(ValueError):
        create_app(config(root, ))
    guard.unlink()
    path = root / state["id"] / "session.json"
    state = json.loads(path.read_text())
    state.pop("owner_id")
    write_file(path, json.dumps(state).encode())
    with pytest.raises(ValueError):
        validate_storage(root)


def test_locked_storage_and_consistent_backup_restore(tmp_path):
    root = tmp_path / "accounts"
    admin = initialize(root, "operator", PASSWORD, "production")
    service = Service(config(root, ))
    state = service.create(owner_id=admin.id)
    artifact_path = root / state["id"] / "runs/synthetic/result.json"
    write_file(artifact_path, b'{"synthetic":true}')
    artifact = dict(artifact_id="synthetic-result", path=str(artifact_path),
                    sha256=hashlib.sha256(artifact_path.read_bytes()).hexdigest())
    receipt_path = root / state["id"] / "receipts/synthetic.json"
    receipt = json.dumps(dict(request={"tool_id":"P0-12"}, execution_state="succeeded",
                              artifacts=[artifact])).encode()
    write_file(receipt_path, receipt)
    receipt_hash = hashlib.sha256(receipt).hexdigest()
    state["_tool_runs"].append(dict(file=receipt_path.name, sha256=receipt_hash, tool_id="P0-12"))
    record = dict(artifact, receipt_file=receipt_path.name, receipt_sha256=receipt_hash)
    service.inputs.receipt_artifacts(state, record)
    state["_synthetic_path"] = str(root / state["id"] / "uploads/sample.h5ad")
    write_file(Path(state["_synthetic_path"]), b"synthetic original payload")
    service.sessions.save(state)
    service.execution.shutdown()
    snapshot = tmp_path / "snapshot"
    with storage_lock(root), pytest.raises(ValueError, match="storage_busy"):
        backup(root, snapshot)
    backup(root, snapshot)
    with pytest.raises(ValueError, match="original_directory"):
        restore(snapshot, tmp_path / "different-location")
    assert not (tmp_path / "different-location").exists()
    root.rename(tmp_path / "retained-original")
    restored = root
    restore(snapshot, restored)
    validate_storage(restored)
    result = json.loads((restored / state["id"] / "session.json").read_text())
    assert Path(result["_synthetic_path"]).read_bytes() == b"synthetic original payload"
    assert str(restored) in result["_synthetic_path"]
    assert receipt_path.read_bytes() == receipt
    restored_service = Service(config(restored, ))
    restored_service.inputs.receipt_artifacts(restored_service.load(state["id"]), record)
    restored_service.execution.shutdown()
    with TestClient(create_app(config(restored, ))) as client:
        client.headers["Origin"] = "http://testserver"
        assert client.post("/api/login", json={"username":"operator", "password":PASSWORD}).status_code == 200
        assert client.get("/api/sessions").json()["sessions"][0]["id"] == state["id"]
    write_file(snapshot / state["id"] / "uploads/sample.h5ad", b"tampered")
    restored.rename(tmp_path / "retained-restored")
    with pytest.raises(ValueError, match="integrity"):
        restore(snapshot, root)


def test_public_origin_requires_trusted_proxy_and_rejects_old_tokens(tmp_path):
    root = tmp_path / "accounts"
    initialize(root, "operator", PASSWORD, "production")
    for origin in ("http://internal.invalid", "https://internal.invalid/path", "https://user:pass@internal.invalid"):
        with pytest.raises(ValueError):
            config(root,  public_origin=origin)
    settings = config(root,  public_origin="https://internal.invalid")
    app = create_app(settings)
    with TestClient(app, base_url="https://internal.invalid", client=("127.0.0.1",40000)) as client:
        assert client.get("/api/auth/config").status_code == 403
        proxy = {"X-Forwarded-For":"192.168.50.10", "X-Forwarded-Proto":"https"}
        assert client.get("/api/auth/config", headers=proxy).status_code == 200
        assert client.post("/api/login", json={"token":"t"*32}, headers={**proxy,"Origin":settings.public_origin}).status_code == 422
        assert client.get("/api/auth/config", headers={**proxy,"X-Forwarded-For":"a, b"}).status_code == 403
        assert client.get("/", headers={**proxy,"Host":"evil.invalid"}).status_code == 403
    with TestClient(app, base_url="https://internal.invalid", client=("192.168.50.11",40000)) as client:
        assert client.get("/api/auth/config", headers=proxy).status_code == 403


def test_account_storage_requires_marker_even_after_marker_loss(tmp_path):
    root = tmp_path / "accounts"
    initialize(root, "operator", PASSWORD, "production")
    (root / ".bridge-accounts.json").unlink()
    with pytest.raises(ValueError):
        create_app(config(root))
