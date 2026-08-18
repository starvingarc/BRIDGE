from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path

import pytest

from bridge.storage import LocalArtifactStore


def test_artifact_store_addresses_and_verifies_content(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path / "artifacts")
    artifact = store.put(BytesIO(b"measurement-result"), "application/json")

    assert artifact.artifact_id == f"sha256:{artifact.sha256}"
    assert not Path(artifact.relative_path).is_absolute()
    with store.open(artifact.artifact_id) as source:
        assert source.read() == b"measurement-result"
    assert store.verify(artifact.artifact_id).valid is True


def test_artifact_store_deduplicates_equal_content(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path / "artifacts")

    first = store.put(BytesIO(b"same"), "application/octet-stream")
    second = store.put(BytesIO(b"same"), "application/octet-stream")

    assert first.artifact_id == second.artifact_id
    assert list((tmp_path / "artifacts").glob("??/*")) == [
        tmp_path / "artifacts" / first.relative_path
    ]


def test_artifact_store_reports_tampering_without_rewriting(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path / "artifacts")
    artifact = store.put(BytesIO(b"original"), "application/octet-stream")
    stored_path = tmp_path / "artifacts" / artifact.relative_path
    stored_path.write_bytes(b"tampered")

    verification = store.verify(artifact.artifact_id)

    assert verification.valid is False
    assert verification.reason_code == "artifact_checksum_mismatch"
    assert stored_path.read_bytes() == b"tampered"


def test_artifact_store_rejects_corrupt_deduplication_target(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    store = LocalArtifactStore(root)
    artifact = store.put(BytesIO(b"original"), "application/octet-stream")
    stored_path = root / artifact.relative_path
    stored_path.write_bytes(b"tampered")

    with pytest.raises(ValueError, match="artifact_checksum_mismatch"):
        store.put(BytesIO(b"original"), "application/octet-stream")

    assert stored_path.read_bytes() == b"tampered"
    assert list((root / ".staging").iterdir()) == []


def test_artifact_store_refuses_to_open_corrupt_content(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    store = LocalArtifactStore(root)
    artifact = store.put(BytesIO(b"original"), "application/octet-stream")
    (root / artifact.relative_path).write_bytes(b"tampered")

    with pytest.raises(ValueError, match="artifact_checksum_mismatch"):
        store.open(artifact.artifact_id)


def test_artifact_store_rejects_symlinked_shard_without_external_write(
    tmp_path: Path,
) -> None:
    content = b"outside-root"
    digest = hashlib.sha256(content).hexdigest()
    root = tmp_path / "artifacts"
    outside = tmp_path / "outside"
    outside.mkdir()
    store = LocalArtifactStore(root)
    (root / digest[:2]).symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="artifact_directory_not_regular"):
        store.put(BytesIO(content), "application/octet-stream")

    assert list(outside.iterdir()) == []
    assert list((root / ".staging").iterdir()) == []


def test_artifact_store_rejects_symlinked_object_without_external_read(
    tmp_path: Path,
) -> None:
    content = b"external-private-bytes"
    digest = hashlib.sha256(content).hexdigest()
    artifact_id = f"sha256:{digest}"
    root = tmp_path / "artifacts"
    outside = tmp_path / "private"
    outside.write_bytes(content)
    store = LocalArtifactStore(root)
    shard = root / digest[:2]
    shard.mkdir()
    (shard / digest).symlink_to(outside)

    with pytest.raises(ValueError, match="artifact_not_regular"):
        store.open(artifact_id)

    verification = store.verify(artifact_id)
    assert verification.valid is False
    assert verification.reason_code == "artifact_not_regular"


def test_artifact_store_rejects_symlinked_deduplication_target(
    tmp_path: Path,
) -> None:
    content = b"external-private-bytes"
    digest = hashlib.sha256(content).hexdigest()
    root = tmp_path / "artifacts"
    outside = tmp_path / "private"
    outside.write_bytes(content)
    store = LocalArtifactStore(root)
    shard = root / digest[:2]
    shard.mkdir()
    (shard / digest).symlink_to(outside)

    with pytest.raises(ValueError, match="artifact_not_regular"):
        store.put(BytesIO(content), "application/octet-stream")

    assert outside.read_bytes() == content
    assert list((root / ".staging").iterdir()) == []


def test_artifact_store_rejects_non_regular_digest_object(tmp_path: Path) -> None:
    content = b"expected"
    digest = hashlib.sha256(content).hexdigest()
    artifact_id = f"sha256:{digest}"
    root = tmp_path / "artifacts"
    store = LocalArtifactStore(root)
    (root / digest[:2] / digest).mkdir(parents=True)

    with pytest.raises(ValueError, match="artifact_not_regular"):
        store.open(artifact_id)

    assert store.verify(artifact_id).reason_code == "artifact_not_regular"


def test_artifact_store_rejects_symlinked_staging_directory(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / ".staging").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="artifact_directory_not_regular"):
        LocalArtifactStore(root)

    assert list(outside.iterdir()) == []


def test_artifact_store_rejects_untrusted_ids(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path / "artifacts")

    with pytest.raises(ValueError, match="invalid_artifact_id"):
        store.open("../../private-input")
