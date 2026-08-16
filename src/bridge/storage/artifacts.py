from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path
from typing import BinaryIO

from pydantic import Field

from bridge.toolkit.contracts import FrozenModel


_ARTIFACT_ID = re.compile(r"^sha256:([0-9a-f]{64})$")


class StoredArtifact(FrozenModel):
    artifact_id: str = Field(pattern=_ARTIFACT_ID.pattern)
    relative_path: str
    media_type: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)


class ArtifactVerification(FrozenModel):
    artifact_id: str
    valid: bool
    expected_sha256: str
    actual_sha256: str | None = None
    reason_code: str | None = None


class LocalArtifactStore:
    """Append-only, content-addressed storage beneath one local root."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._staging = self.root / ".staging"
        self._staging.mkdir(exist_ok=True)

    def put(self, stream: BinaryIO, media_type: str) -> StoredArtifact:
        digest = hashlib.sha256()
        size_bytes = 0
        descriptor, temporary_name = tempfile.mkstemp(dir=self._staging)
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as destination:
                while chunk := stream.read(1024 * 1024):
                    if not isinstance(chunk, bytes):
                        raise TypeError("artifact stream must return bytes")
                    destination.write(chunk)
                    digest.update(chunk)
                    size_bytes += len(chunk)
            sha256 = digest.hexdigest()
            artifact_id = f"sha256:{sha256}"
            destination_path = self._path_for_digest(sha256)
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            if destination_path.exists():
                temporary_path.unlink()
            else:
                os.replace(temporary_path, destination_path)
            return StoredArtifact(
                artifact_id=artifact_id,
                relative_path=destination_path.relative_to(self.root).as_posix(),
                media_type=media_type,
                sha256=sha256,
                size_bytes=size_bytes,
            )
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

    def open(self, artifact_id: str) -> BinaryIO:
        return self._path_for_id(artifact_id).open("rb")

    def verify(self, artifact_id: str) -> ArtifactVerification:
        expected = self._digest_from_id(artifact_id)
        path = self._path_for_digest(expected)
        if not path.is_file():
            return ArtifactVerification(
                artifact_id=artifact_id,
                valid=False,
                expected_sha256=expected,
                reason_code="artifact_not_found",
            )
        actual = self._sha256(path)
        return ArtifactVerification(
            artifact_id=artifact_id,
            valid=actual == expected,
            expected_sha256=expected,
            actual_sha256=actual,
            reason_code=None if actual == expected else "artifact_checksum_mismatch",
        )

    def _path_for_id(self, artifact_id: str) -> Path:
        return self._path_for_digest(self._digest_from_id(artifact_id))

    def _path_for_digest(self, digest: str) -> Path:
        return self.root / digest[:2] / digest

    @staticmethod
    def _digest_from_id(artifact_id: str) -> str:
        match = _ARTIFACT_ID.fullmatch(artifact_id)
        if match is None:
            raise ValueError("invalid_artifact_id")
        return match.group(1)

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
        return digest.hexdigest()
