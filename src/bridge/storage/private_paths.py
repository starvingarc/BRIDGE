from __future__ import annotations

import errno
import os
import stat
import sys
from collections.abc import Mapping
from pathlib import Path
from threading import Lock


_trusted_ancestors: dict[Path, tuple[int, int, int]] = {}
_trust_frozen = False
_trust_lock = Lock()


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


def configure_trusted_ancestors(
    ancestors: Mapping[Path, tuple[int, int, int]],
) -> None:
    """Pin operator-approved ancestors before private I/O; never use request input.

    Values are (uid, device, inode). Configuration is copied and validated
    without following links or changing permissions. Once configured or used,
    only an identical policy can be supplied again; changes require a restart.
    """
    global _trusted_ancestors, _trust_frozen
    policy: dict[Path, tuple[int, int, int]] = {}
    for path, identity in ancestors.items():
        canonical = canonical_absolute_path(path)
        if (
            canonical == Path(canonical.anchor)
            or canonical in policy
            or not isinstance(identity, tuple)
            or len(identity) != 3
            or any(type(value) is not int or value < 0 for value in identity)
        ):
            raise PrivatePathError("trusted_ancestor_configuration_invalid")
        policy[canonical] = identity
    with _trust_lock:
        if _trust_frozen and policy != _trusted_ancestors:
            raise PrivatePathError("private_path_trust_configuration_locked")
        for path in policy:
            descriptor = _open_directory(path, create=False, ancestors=policy)
            os.close(descriptor)
        _trusted_ancestors = policy
        _trust_frozen = True


def open_private_directory(path: Path, *, create: bool) -> tuple[Path, int]:
    global _trust_frozen
    with _trust_lock:
        _trust_frozen = True
        ancestors = _trusted_ancestors
    canonical = canonical_absolute_path(path)
    descriptor = _open_directory(canonical, create=create, ancestors=ancestors)
    try:
        _require_private_owner_directory(descriptor)
        return canonical, descriptor
    except Exception:
        os.close(descriptor)
        raise


def _open_directory(
    canonical: Path, *, create: bool, ancestors: Mapping[Path, tuple[int, int, int]],
) -> int:
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    try:
        descriptor = os.open(canonical.anchor, flags)
    except OSError as error:
        raise PrivatePathError("private_path_anchor_invalid") from error
    try:
        current = Path(canonical.anchor)
        _require_safe_ancestor_directory(descriptor, current, ancestors)
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
                current = current / component
                _require_safe_ancestor_directory(next_descriptor, current, ancestors)
            except Exception:
                os.close(next_descriptor)
                raise
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor
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
        _, parent_descriptor = open_private_directory(canonical.parent, create=False)
    except FileNotFoundError:
        return
    try:
        try:
            descriptor = os.open(
                canonical.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_descriptor,
            )
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
    finally:
        os.close(parent_descriptor)


def _require_safe_ancestor_directory(
    descriptor: int,
    path: Path | None = None,
    ancestors: Mapping[Path, tuple[int, int, int]] | None = None,
) -> None:
    info = os.fstat(descriptor)
    if not stat.S_ISDIR(info.st_mode):
        raise PrivatePathError("private_path_not_directory")
    pinned = ancestors.get(path) if ancestors is not None else None
    mode = stat.S_IMODE(info.st_mode)
    if pinned is not None:
        if (info.st_uid, info.st_dev, info.st_ino) != pinned:
            raise PrivatePathError("trusted_ancestor_identity_mismatch")
        # Sticky shared directories are not eligible for an ownership exception.
        if mode & 0o022:
            raise PrivatePathError("private_path_ancestor_permissions_invalid")
    elif info.st_uid not in {0, os.geteuid()}:
        raise PrivatePathError("private_path_ancestor_owner_invalid")
    if mode & 0o022 and not mode & stat.S_ISVTX:
        raise PrivatePathError("private_path_ancestor_permissions_invalid")


def _require_private_owner_directory(descriptor: int) -> None:
    _require_safe_ancestor_directory(descriptor)
    info = os.fstat(descriptor)
    if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise PrivatePathError("private_directory_permissions_invalid")
