"""Private-path trust tests use synthetic directories and simulated foreign ownership."""

import os
import stat
from pathlib import Path

import pytest

from bridge.storage import private_paths as paths


@pytest.fixture(autouse=True)
def isolated_startup_policy(monkeypatch):
    # Production has no reset API: each test represents a fresh process.
    monkeypatch.setattr(paths, "_trusted_ancestors", {}, raising=False)
    monkeypatch.setattr(paths, "_trust_frozen", False, raising=False)


@pytest.fixture
def tree(tmp_path, monkeypatch):
    shared = tmp_path / "shared"
    shared.mkdir(mode=0o755)
    leaf = shared / "private"
    leaf.mkdir(mode=0o700)
    (leaf / "record").write_bytes(b"synthetic")
    original_fstat = os.fstat
    foreign = {}

    def pretend_foreign(path):
        info = path.stat()
        foreign[(info.st_dev, info.st_ino)] = os.geteuid() + 12345
        return (os.geteuid() + 12345, info.st_dev, info.st_ino)

    def observed_fstat(fd):
        info = original_fstat(fd)
        uid = foreign.get((info.st_dev, info.st_ino))
        if uid is None:
            return info
        fields = list(info)
        fields[4] = uid
        return os.stat_result(fields)

    monkeypatch.setattr(paths.os, "fstat", observed_fstat)
    return shared, leaf, pretend_foreign(shared), pretend_foreign


OPERATIONS = ("open", "ensure", "verify", "prepare", "tighten")


def invoke(operation, leaf):
    if operation == "open":
        canonical, fd = paths.open_private_directory(leaf, create=False)
        os.close(fd)
        assert canonical == leaf
    elif operation == "ensure":
        canonical, device, inode = paths.ensure_private_directory(leaf)
        assert canonical == leaf
        assert (device, inode) == (leaf.stat().st_dev, leaf.stat().st_ino)
    elif operation == "verify":
        info = leaf.stat()
        paths.verify_private_directory(leaf, device=info.st_dev, inode=info.st_ino)
    elif operation == "prepare":
        assert paths.prepare_private_file(leaf / "record") == leaf / "record"
    else:
        paths.tighten_private_file(leaf / "record")
    assert (leaf / "record").read_bytes() == b"synthetic"


@pytest.mark.parametrize("operation", OPERATIONS)
def test_unconfigured_foreign_ancestor_is_rejected(tree, operation):
    _, leaf, _, _ = tree
    with pytest.raises(paths.PrivatePathError, match="ancestor_owner_invalid"):
        invoke(operation, leaf)


@pytest.mark.parametrize("operation", OPERATIONS)
def test_exact_pinned_ancestor_allows_private_leaf(tree, operation):
    shared, leaf, pin, _ = tree
    paths.configure_trusted_ancestors({shared: pin})
    invoke(operation, leaf)


@pytest.mark.parametrize("operation", OPERATIONS)
def test_other_foreign_ancestor_is_not_implicitly_trusted(tree, operation):
    shared, leaf, pin, pretend_foreign = tree
    nested = leaf / "other"
    nested.mkdir(mode=0o755)
    private = nested / "private"
    private.mkdir(mode=0o700)
    (private / "record").write_bytes(b"synthetic")
    pretend_foreign(nested)
    paths.configure_trusted_ancestors({shared: pin})
    with pytest.raises(paths.PrivatePathError, match="ancestor_owner_invalid"):
        invoke(operation, private)


@pytest.mark.parametrize("field", (0, 1, 2), ids=("uid", "device", "inode"))
def test_startup_rejects_mismatched_pin(tree, field):
    shared, _, pin, _ = tree
    incorrect = list(pin)
    incorrect[field] += 1
    with pytest.raises(paths.PrivatePathError, match="trusted_ancestor_identity_mismatch"):
        paths.configure_trusted_ancestors({shared: tuple(incorrect)})


@pytest.mark.parametrize("operation", OPERATIONS)
@pytest.mark.parametrize("change", ("replacement", "symlink", "writable", "nonprivate_leaf", "foreign_leaf"))
def test_trust_preserves_security_checks_after_startup(tree, operation, change):
    shared, leaf, pin, pretend_foreign = tree
    paths.configure_trusted_ancestors({shared: pin})
    if change in {"replacement", "symlink"}:
        moved = shared.with_name("original")
        shared.rename(moved)
        if change == "symlink":
            shared.symlink_to(moved, target_is_directory=True)
        else:
            shared.mkdir(mode=0o755)
            leaf.mkdir(mode=0o700)
            (leaf / "record").write_bytes(b"synthetic")
    elif change == "writable":
        shared.chmod(0o777)
    elif change == "nonprivate_leaf":
        leaf.chmod(0o755)
    else:
        pretend_foreign(leaf)
    with pytest.raises(paths.PrivatePathError):
        invoke(operation, leaf)


@pytest.mark.parametrize("mode", (0o777, 0o1777))
def test_startup_rejects_writable_trusted_ancestor_even_if_sticky(tree, mode):
    shared, _, pin, _ = tree
    shared.chmod(mode)
    with pytest.raises(paths.PrivatePathError, match="ancestor_permissions_invalid"):
        paths.configure_trusted_ancestors({shared: pin})


def test_startup_rejects_symlink_alias(tree):
    shared, _, pin, _ = tree
    alias = shared.with_name("alias")
    alias.symlink_to(shared, target_is_directory=True)
    with pytest.raises(paths.PrivatePathError, match="not_directory"):
        paths.configure_trusted_ancestors({alias: pin})


def test_trusted_path_cannot_be_used_as_foreign_owned_private_leaf(tree):
    shared, _, pin, _ = tree
    paths.configure_trusted_ancestors({shared: pin})
    with pytest.raises(paths.PrivatePathError):
        paths.ensure_private_directory(shared)


def test_startup_configuration_is_copied_and_cannot_be_expanded(tree):
    shared, leaf, pin, _ = tree
    policy = {shared: pin}
    paths.configure_trusted_ancestors(policy)
    policy.clear()
    invoke("open", leaf)
    paths.configure_trusted_ancestors({shared: pin})
    with pytest.raises(paths.PrivatePathError, match="trust_configuration_locked"):
        paths.configure_trusted_ancestors({})


def test_first_use_locks_strict_default_even_after_rejected_access(tree):
    shared, leaf, pin, _ = tree
    with pytest.raises(paths.PrivatePathError):
        paths.ensure_private_directory(leaf)
    with pytest.raises(paths.PrivatePathError, match="trust_configuration_locked"):
        paths.configure_trusted_ancestors({shared: pin})


@pytest.mark.parametrize("operation", ("prepare", "tighten"))
def test_file_symlinks_are_rejected_without_changing_target(tree, operation):
    shared, leaf, pin, _ = tree
    target = leaf / "target"
    target.write_bytes(b"private")
    target.chmod(0o644)
    (leaf / "record").unlink()
    (leaf / "record").symlink_to(target)
    paths.configure_trusted_ancestors({shared: pin})
    with pytest.raises(paths.PrivatePathError, match="private_file_not_regular"):
        invoke(operation, leaf)
    assert stat.S_IMODE(target.stat().st_mode) == 0o644


def test_missing_file_tighten_remains_noop(tmp_path):
    paths.tighten_private_file(tmp_path / "absent")
    paths.tighten_private_file(tmp_path / "absent-parent" / "absent")


def test_created_directories_and_files_remain_private(tree):
    shared, _, pin, _ = tree
    paths.configure_trusted_ancestors({shared: pin})
    leaf, _, _ = paths.ensure_private_directory(shared / "new" / "private")
    file = paths.prepare_private_file(leaf / "record")
    assert stat.S_IMODE(leaf.stat().st_mode) == 0o700
    assert stat.S_IMODE(file.stat().st_mode) == 0o600

@pytest.mark.parametrize("operation", OPERATIONS)
@pytest.mark.parametrize("field", (0, 1, 2), ids=("uid", "device", "inode"))
def test_pins_are_rechecked_on_every_access(tree, monkeypatch, operation, field):
    shared, leaf, pin, _ = tree
    paths.configure_trusted_ancestors({shared: pin})
    original_fstat = os.fstat

    def changed_identity(fd):
        info = original_fstat(fd)
        if (info.st_dev, info.st_ino) != pin[1:]:
            return info
        fields = list(info)
        fields[(4, 2, 1)[field]] += 1
        return os.stat_result(fields)

    monkeypatch.setattr(paths.os, "fstat", changed_identity)
    with pytest.raises(paths.PrivatePathError, match="trusted_ancestor_identity_mismatch"):
        invoke(operation, leaf)


@pytest.mark.parametrize("identity", ((-1, 1, 1), (True, 1, 1), (1, 1), [1, 1, 1]))
def test_malformed_identity_does_not_install_partial_policy(tree, identity):
    shared, leaf, pin, _ = tree
    with pytest.raises(paths.PrivatePathError, match="configuration_invalid"):
        paths.configure_trusted_ancestors({shared: identity})
    with pytest.raises(paths.PrivatePathError, match="ancestor_owner_invalid"):
        invoke("open", leaf)


def test_failed_validation_does_not_install_earlier_valid_entries(tree):
    shared, leaf, pin, _ = tree
    with pytest.raises(FileNotFoundError):
        paths.configure_trusted_ancestors({shared: pin, shared / "absent": (1, 1, 1)})
    with pytest.raises(paths.PrivatePathError, match="ancestor_owner_invalid"):
        invoke("open", leaf)


@pytest.mark.parametrize("path", (Path("relative"), Path("/"), Path("/safe/../other")))
def test_nonexact_trust_paths_are_rejected(path):
    with pytest.raises(paths.PrivatePathError):
        paths.configure_trusted_ancestors({path: (1, 1, 1)})


def test_final_directory_identity_is_still_verified(tree):
    shared, leaf, pin, _ = tree
    paths.configure_trusted_ancestors({shared: pin})
    info = leaf.stat()
    with pytest.raises(paths.PrivatePathError, match="private_directory_identity_mismatch"):
        paths.verify_private_directory(leaf, device=info.st_dev, inode=info.st_ino + 1)
