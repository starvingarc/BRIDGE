from __future__ import annotations

import errno
import os
import stat
import sys
from pathlib import Path


class PrivatePathError(ValueError):
    """A stable failure at a local private-path boundary."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


def canonical_absolute_path(path: Path) -> Path:
    raw = Path(path)
    if not raw.is_absolute():
        raise PrivatePathError("private_path_must_be_absolute")
    if any(part in {"", ".", ".."} for part in raw.parts[1:]):
        raise PrivatePathError("private_path_invalid_component")
    if sys.platform == "darwin" and raw.parts[:2] == ("/", "tmp"):
        return Path("/tmp").resolve(strict=True).joinpath(*raw.parts[2:])
    return raw


def open_private_directory(path: Path, *, create: bool) -> tuple[Path, int]:
    canonical = canonical_absolute_path(path)
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    try:
        descriptor = os.open(canonical.anchor, flags)
    except OSError as error:
        raise PrivatePathError("private_path_anchor_invalid") from error
    try:
        _require_safe_ancestor_directory(descriptor)
        for component in canonical.parts[1:]:
            if create:
                try:
                    os.mkdir(component, 0o700, dir_fd=descriptor)
                except FileExistsError:
                    pass
            try:
                next_descriptor = os.open(component, flags, dir_fd=descriptor)
            except OSError as error:
                if error.errno in {errno.ELOOP, errno.ENOTDIR}:
                    raise PrivatePathError("private_path_not_directory") from error
                raise
            try:
                _require_safe_ancestor_directory(next_descriptor)
            except Exception:
                os.close(next_descriptor)
                raise
            os.close(descriptor)
            descriptor = next_descriptor
        _require_private_owner_directory(descriptor)
        return canonical, descriptor
    except Exception:
        os.close(descriptor)
        raise


def ensure_private_directory(path: Path) -> tuple[Path, int, int]:
    canonical, descriptor = open_private_directory(path, create=True)
    try:
        info = os.fstat(descriptor)
        return canonical, int(info.st_dev), int(info.st_ino)
    finally:
        os.close(descriptor)


def verify_private_directory(path: Path, *, device: int, inode: int) -> None:
    _, descriptor = open_private_directory(path, create=False)
    try:
        info = os.fstat(descriptor)
        if int(info.st_dev) != device or int(info.st_ino) != inode:
            raise PrivatePathError("private_directory_identity_mismatch")
    finally:
        os.close(descriptor)


def prepare_private_file(path: Path) -> Path:
    canonical = canonical_absolute_path(path)
    parent, descriptor = open_private_directory(canonical.parent, create=True)
    try:
        flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW
        try:
            file_descriptor = os.open(canonical.name, flags, 0o600, dir_fd=descriptor)
        except OSError as error:
            if error.errno in {errno.ELOOP, errno.ENOTDIR}:
                raise PrivatePathError("private_file_not_regular") from error
            raise
        try:
            info = os.fstat(file_descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid():
                raise PrivatePathError("private_file_not_regular")
            os.fchmod(file_descriptor, 0o600)
        finally:
            os.close(file_descriptor)
    finally:
        os.close(descriptor)
    return parent / canonical.name


def tighten_private_file(path: Path) -> None:
    canonical = canonical_absolute_path(path)
    try:
        descriptor = os.open(canonical, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return
    except OSError as error:
        if error.errno in {errno.ELOOP, errno.ENOTDIR}:
            raise PrivatePathError("private_file_not_regular") from error
        raise
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid():
            raise PrivatePathError("private_file_not_regular")
        os.fchmod(descriptor, 0o600)
    finally:
        os.close(descriptor)


def _require_safe_ancestor_directory(descriptor: int) -> None:
    info = os.fstat(descriptor)
    if not stat.S_ISDIR(info.st_mode):
        raise PrivatePathError("private_path_not_directory")
    if info.st_uid not in {0, os.geteuid()}:
        raise PrivatePathError("private_path_ancestor_owner_invalid")
    mode = stat.S_IMODE(info.st_mode)
    if mode & 0o022 and not mode & stat.S_ISVTX:
        raise PrivatePathError("private_path_ancestor_permissions_invalid")


def _require_private_owner_directory(descriptor: int) -> None:
    _require_safe_ancestor_directory(descriptor)
    info = os.fstat(descriptor)
    if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise PrivatePathError("private_directory_permissions_invalid")
