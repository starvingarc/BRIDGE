from __future__ import annotations

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


def test_artifact_store_rejects_untrusted_ids(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path / "artifacts")

    with pytest.raises(ValueError, match="invalid_artifact_id"):
        store.open("../../private-input")
