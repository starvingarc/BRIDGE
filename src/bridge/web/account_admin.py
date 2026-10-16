"""Offline account initialization and consistent private snapshots."""
import argparse
import getpass
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys

from bridge.storage.private_paths import ensure_private_directory
from .accounts import AccountStore
from .launcher import storage_lock, PID_FILE
from .runtime import bind_storage_environment, STORAGE_LOCK_FILE, STORAGE_BINDING_FILE
from .sessions import ID, SESSION_BYTES_LIMIT, open_private_file, write_file

MARKER = ".bridge-accounts.json"
BACKUP_MARKER = ".bridge-backup.json"


def read_json(path, limit=SESSION_BYTES_LIMIT):
    with open_private_file(path, limit) as stream:
        return json.load(stream)


def copy_tree(source, target):
    """Copy only owner-controlled regular files; never follow links."""
    info = source.lstat()
    if stat.S_ISDIR(info.st_mode):
        ensure_private_directory(source)
        ensure_private_directory(target)
        for item in sorted(source.iterdir()):
            copy_tree(item, target / item.name)
    elif stat.S_ISREG(info.st_mode):
        ensure_private_directory(target.parent)
        with open_private_file(source) as original:
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "wb") as output:
                shutil.copyfileobj(original, output, 1024 * 1024)
                output.flush()
                os.fsync(output.fileno())
    else:
        raise ValueError("migration_unsafe_file")


def inventory(root):
    result = {}
    for base, directories, files in os.walk(root, followlinks=False):
        for name in directories:
            if (Path(base) / name).is_symlink():
                raise ValueError("migration_unsafe_file")
        for name in files:
            path = Path(base) / name
            if path.parent == root and name in {STORAGE_LOCK_FILE, PID_FILE, BACKUP_MARKER}:
                continue
            with open_private_file(path) as stream:
                result[str(path.relative_to(root))] = hashlib.file_digest(stream, "sha256").hexdigest()
    return result


def validate_storage(root):
    try:
        if (root / ".bridge-restore-in-progress").exists():
            raise ValueError
        if read_json(root / STORAGE_BINDING_FILE).get("object_version") != "2.0.0":
            raise ValueError
        marker = read_json(root / MARKER)
        if marker.get("object_version") != 1 or marker.get("phase") != "ready":
            raise ValueError
        users = AccountStore(root).users()
        admins = {user["id"] for user in users if user["role"] == "admin" and not user["disabled"]}
        identities = {user["id"] for user in users}
        if marker["admin_id"] not in admins:
            raise ValueError
        for directory in root.iterdir():
            if ID.fullmatch(directory.name):
                ensure_private_directory(directory)
                state = read_json(directory / "session.json")
                if state.get("owner_id") not in identities or state.get("id") != directory.name:
                    raise ValueError
    except (KeyError, OSError, TypeError, ValueError):
        raise ValueError("multiuser_storage_not_ready") from None


def initialize(root, username, password, environment):
    root = Path(root).absolute()
    root, _, _ = ensure_private_directory(root)
    with storage_lock(root):
        path = root / MARKER
        if not path.exists() and any(ID.fullmatch(item.name) for item in root.iterdir()):
            raise ValueError("account_storage_requires_empty_directory")
        bind_storage_environment(root, environment, object_version="2.0.0")
        admin = AccountStore(root).bootstrap_admin(username, password)
        if path.exists():
            marker = read_json(path)
            if marker.get("admin_id") != admin.id:
                raise ValueError("account_identity_mismatch")
        else:
            write_file(path, json.dumps(dict(object_version=1, phase="ready", admin_id=admin.id)).encode())
        validate_storage(root)
        return admin


def backup(root, target):
    root, target = Path(root).absolute(), Path(target).absolute()
    if root == target or target.is_relative_to(root) or root.is_relative_to(target) or target.exists():
        raise ValueError("backup_requires_new_directory")
    ensure_private_directory(root)
    with storage_lock(root):
        validate_storage(root)
        ensure_private_directory(target)
        for item in root.iterdir():
            if item.name not in {STORAGE_LOCK_FILE, PID_FILE, BACKUP_MARKER}:
                copy_tree(item, target / item.name)
        write_file(target / BACKUP_MARKER, json.dumps({"source_root":str(root), "files":inventory(target)}).encode())


def restore(snapshot, target):
    snapshot, target = Path(snapshot).absolute(), Path(target).absolute()
    if target.exists() or target.is_relative_to(snapshot):
        raise ValueError("restore_requires_new_directory")
    with storage_lock(snapshot):
        record = read_json(snapshot / BACKUP_MARKER, 16 * 1024 * 1024)
        if str(target) != record["source_root"]:
            raise ValueError("restore_requires_original_directory")
        if inventory(snapshot) != record["files"]:
            raise ValueError("backup_integrity_mismatch")
        ensure_private_directory(target)
        with storage_lock(target):
            guard = target / ".bridge-restore-in-progress"
            write_file(guard, b"restore in progress")
            for item in snapshot.iterdir():
                if item.name not in {STORAGE_LOCK_FILE, PID_FILE, BACKUP_MARKER}:
                    copy_tree(item, target / item.name)
            guard.unlink()
            validate_storage(target)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline account storage administration; stop the service first.")
    parser.add_argument("--config", type=Path, help="owner-only Web config for trusted storage ancestors")
    commands = parser.add_subparsers(dest="command", required=True)
    initial = commands.add_parser("initialize")
    initial.add_argument("--root", type=Path, required=True)
    initial.add_argument("--username", required=True)
    initial.add_argument("--environment", choices=("development","acceptance","production"), required=True)
    initial.add_argument("--password-stdin", action="store_true", help="read password from a private pipe, never argv")
    for command in ("backup", "restore"):
        child = commands.add_parser(command)
        child.add_argument("--source", type=Path, required=True)
        child.add_argument("--target", type=Path, required=True)
    args = parser.parse_args(argv)
    os.umask(0o077)
    try:
        from .__main__ import load_config
        from bridge.storage.private_paths import configure_trusted_ancestors
        environment = load_config(args.config) if args.config else os.environ
        pins = json.loads(environment.get("BRIDGE_WEB_TRUSTED_ANCESTORS", "{}"))
        configure_trusted_ancestors({Path(path): tuple(identity) for path, identity in pins.items()})
        if args.command == "initialize":
            password = sys.stdin.readline().rstrip("\n") if args.password_stdin else getpass.getpass("Administrator password: ")
            initialize(args.root, args.username, password, args.environment)
        elif args.command == "backup":
            backup(args.source, args.target)
        else:
            restore(args.source, args.target)
    except Exception:
        print("Account storage operation failed. Check identity, storage readiness, permissions and service locks.", file=sys.stderr)
        return 1
    print("Account storage operation completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
