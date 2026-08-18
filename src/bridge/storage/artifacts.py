from __future__ import annotations

import errno
import hashlib
import os
import re
import secrets
import stat
import sys
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


class ArtifactStoreError(ValueError):
    """A deterministic failure raised at the artifact trust boundary."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


class LocalArtifactStore:
    """Append-only, content-addressed storage beneath one local root."""

    def __init__(self, root: Path) -> None:
        self.root = self._canonical_root(root)
        self._root_fd = self._establish_root(self.root)
        self._staging = self.root / ".staging"
        try:
            self._staging_fd = self._open_child_directory(
                self._root_fd, ".staging", create=True
            )
        except Exception:
            os.close(self._root_fd)
            self._root_fd = None
            raise

    def close(self) -> None:
        staging_fd = getattr(self, "_staging_fd", None)
        if staging_fd is not None:
            self._staging_fd = None
            os.close(staging_fd)
        root_fd = getattr(self, "_root_fd", None)
        if root_fd is not None:
            self._root_fd = None
            os.close(root_fd)

    def __enter__(self) -> LocalArtifactStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def __del__(self) -> None:
        self.close()

    def put(self, stream: BinaryIO, media_type: str) -> StoredArtifact:
        digest = hashlib.sha256()
        size_bytes = 0
        temporary_name, descriptor = self._create_staging_file()
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
            shard_fd = self._open_child_directory(
                self._root_descriptor(), sha256[:2], create=True
            )
            try:
                for _ in range(3):
                    try:
                        os.link(
                            temporary_name,
                            sha256,
                            src_dir_fd=self._staging_descriptor(),
                            dst_dir_fd=shard_fd,
                            follow_symlinks=False,
                        )
                        break
                    except FileExistsError:
                        try:
                            actual = self._digest_for_object(shard_fd, sha256)
                        except FileNotFoundError:
                            continue
                        if actual != sha256:
                            raise ArtifactStoreError("artifact_checksum_mismatch")
                        break
                else:
                    raise ArtifactStoreError("artifact_publication_race")
            finally:
                os.close(shard_fd)
            return StoredArtifact(
                artifact_id=artifact_id,
                relative_path=destination_path.relative_to(self.root).as_posix(),
                media_type=media_type,
                sha256=sha256,
                size_bytes=size_bytes,
            )
        finally:
            try:
                os.unlink(temporary_name, dir_fd=self._staging_descriptor())
            except FileNotFoundError:
                pass

    def open(self, artifact_id: str) -> BinaryIO:
        expected = self._digest_from_id(artifact_id)
        source = self._open_object(expected)
        try:
            snapshot = self._create_unlinked_snapshot()
        except Exception:
            os.close(source)
            raise
        digest = hashlib.sha256()
        try:
            with os.fdopen(source, "rb") as stored:
                while chunk := stored.read(1024 * 1024):
                    snapshot.write(chunk)
                    digest.update(chunk)
            if digest.hexdigest() != expected:
                raise ArtifactStoreError("artifact_checksum_mismatch")
            snapshot.seek(0)
            return snapshot
        except Exception:
            snapshot.close()
            raise

    def verify(self, artifact_id: str) -> ArtifactVerification:
        expected = self._digest_from_id(artifact_id)
        try:
            actual = self._digest_for_id(expected)
        except ArtifactStoreError as error:
            return ArtifactVerification(
                artifact_id=artifact_id,
                valid=False,
                expected_sha256=expected,
                reason_code=error.reason_code,
            )
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

    def _digest_for_id(self, digest: str) -> str:
        descriptor = self._open_object(digest)
        with os.fdopen(descriptor, "rb") as source:
            return self._sha256(source)

    def _open_object(self, digest: str) -> int:
        try:
            shard_fd = self._open_child_directory(
                self._root_descriptor(), digest[:2], create=False
            )
        except FileNotFoundError as error:
            raise ArtifactStoreError("artifact_not_found") from error
        try:
            try:
                descriptor = os.open(
                    digest,
                    os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW,
                    dir_fd=shard_fd,
                )
            except FileNotFoundError as error:
                raise ArtifactStoreError("artifact_not_found") from error
            except OSError as error:
                if error.errno in {errno.ELOOP, errno.ENOTDIR}:
                    raise ArtifactStoreError("artifact_not_regular") from error
                raise
        finally:
            os.close(shard_fd)
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            os.close(descriptor)
            raise ArtifactStoreError("artifact_not_regular")
        return descriptor

    def _digest_for_object(self, shard_fd: int, digest: str) -> str:
        try:
            descriptor = os.open(
                digest,
                os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW,
                dir_fd=shard_fd,
            )
        except OSError as error:
            if error.errno in {errno.ELOOP, errno.ENOTDIR}:
                raise ArtifactStoreError("artifact_not_regular") from error
            raise
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            os.close(descriptor)
            raise ArtifactStoreError("artifact_not_regular")
        with os.fdopen(descriptor, "rb") as source:
            return self._sha256(source)

    def _create_staging_file(self) -> tuple[str, int]:
        for _ in range(100):
            name = f"artifact-{secrets.token_hex(16)}.tmp"
            try:
                descriptor = os.open(
                    name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=self._staging_descriptor(),
                )
            except FileExistsError:
                continue
            return name, descriptor
        raise ArtifactStoreError("artifact_staging_collision")

    def _create_unlinked_snapshot(self) -> BinaryIO:
        for _ in range(100):
            name = f"snapshot-{secrets.token_hex(16)}.tmp"
            try:
                descriptor = os.open(
                    name,
                    os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=self._staging_descriptor(),
                )
            except FileExistsError:
                continue
            try:
                os.unlink(name, dir_fd=self._staging_descriptor())
            except Exception:
                os.close(descriptor)
                try:
                    os.unlink(name, dir_fd=self._staging_descriptor())
                except FileNotFoundError:
                    pass
                raise
            return os.fdopen(descriptor, "w+b")
        raise ArtifactStoreError("artifact_staging_collision")

    @classmethod
    def _canonical_root(cls, root: Path) -> Path:
        raw_parts = root.parts
        if any(part in {".", ".."} for part in raw_parts):
            raise ArtifactStoreError("artifact_root_invalid_component")
        absolute = root if root.is_absolute() else Path.cwd() / root

        # macOS exposes /tmp as a system-managed symlink to /private/tmp.  Treat
        # that one OS alias as part of the trusted anchor, while continuing to
        # reject symlinks in every caller-controlled component below it.
        if sys.platform == "darwin" and absolute.parts[:2] == ("/", "tmp"):
            trusted_tmp = Path("/tmp").resolve(strict=True)
            absolute = trusted_tmp.joinpath(*absolute.parts[2:])
        return absolute

    @classmethod
    def _establish_root(cls, path: Path) -> int:
        if not path.is_absolute():
            raise ArtifactStoreError("artifact_root_must_be_absolute")
        try:
            descriptor = os.open(
                path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            )
        except OSError as error:
            if error.errno in {errno.ELOOP, errno.ENOTDIR}:
                raise ArtifactStoreError("artifact_root_not_directory") from error
            raise
        try:
            for component in path.parts[1:]:
                if component in {"", ".", ".."}:
                    raise ArtifactStoreError("artifact_root_invalid_component")
                try:
                    next_descriptor = cls._open_child_directory(
                        descriptor, component, create=True
                    )
                except ArtifactStoreError as error:
                    raise ArtifactStoreError("artifact_root_not_directory") from error
                os.close(descriptor)
                descriptor = next_descriptor
            return descriptor
        except Exception:
            os.close(descriptor)
            raise

    @staticmethod
    def _open_child_directory(parent_fd: int, name: str, *, create: bool) -> int:
        if create:
            try:
                os.mkdir(name, 0o700, dir_fd=parent_fd)
            except FileExistsError:
                pass
        try:
            return os.open(
                name,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=parent_fd,
            )
        except OSError as error:
            if error.errno in {errno.ELOOP, errno.ENOTDIR}:
                raise ArtifactStoreError("artifact_directory_not_regular") from error
            raise

    def _root_descriptor(self) -> int:
        if self._root_fd is None:
            raise ArtifactStoreError("artifact_store_closed")
        return self._root_fd

    def _staging_descriptor(self) -> int:
        if self._staging_fd is None:
            raise ArtifactStoreError("artifact_store_closed")
        return self._staging_fd

    @staticmethod
    def _digest_from_id(artifact_id: str) -> str:
        match = _ARTIFACT_ID.fullmatch(artifact_id)
        if match is None:
            raise ValueError("invalid_artifact_id")
        return match.group(1)

    @staticmethod
    def _sha256(source: BinaryIO) -> str:
        digest = hashlib.sha256()
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
        return digest.hexdigest()
