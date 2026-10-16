from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import secrets
import shutil
import stat
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import BinaryIO

from fastapi import HTTPException

from bridge.skills import load_skill

from bridge.storage.private_paths import (
    ensure_private_directory,
    verify_private_directory,
)

from .runtime import RuntimeEnvironment, bind_storage_environment

ID = re.compile(r"^[a-f0-9]{32}$")


SESSION_BYTES_LIMIT = 8 * 1024 * 1024
BINDING_FILE_BYTES_LIMIT = 1024 * 1024
BINDING_TOTAL_BYTES_LIMIT = 32 * 1024 * 1024
BINDING_FIELDS = ("evidence_bindings", "provider_bindings")
UPLOAD_CHUNK_BYTES = 1024 * 1024


UPLOAD_TEMP = re.compile(r"^\.[a-f0-9]{32}\.upload$")


def now():
    return datetime.now(timezone.utc).isoformat()


def uid():
    return secrets.token_hex(16)


def private_text(value: str) -> str:
    # Paths are never useful in a remote model prompt or public-facing envelope.
    return re.sub(r"(?<![\w:])(?:/[A-Za-z0-9_.-]+){2,}[^\s\"<>]*", "[private path omitted]", value)


@contextmanager
def open_private_file(path: Path, limit: int | None = None):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o022:
            raise ValueError("private_file_invalid")
        if limit is not None and info.st_size > limit:
            raise ValueError("private_file_too_large")
        yield stream


def read_file(path: Path, limit: int | None = None) -> bytes:
    with open_private_file(path, limit) as stream:
        return stream.read()


def write_file(path: Path, content: bytes):
    ensure_private_directory(path.parent)
    temporary = path.parent / (uid() + ".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if path.is_symlink():
            raise ValueError("private_file_invalid")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class UploadLimitExceeded(ValueError):
    pass


def stream_upload(source: BinaryIO, path: Path, limit: int) -> tuple[int, str]:
    """Copy one upload with bounded reads; the caller owns cleanup and registration."""
    ensure_private_directory(path.parent)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    total = 0
    digest = hashlib.sha256()
    prefix = bytearray()
    with os.fdopen(fd, "wb") as target:
        while True:
            chunk = source.read(min(UPLOAD_CHUNK_BYTES, limit - total + 1))
            if not chunk:
                break
            total += len(chunk)
            if total > limit:
                raise UploadLimitExceeded("request_too_large")
            if len(prefix) < 8:
                prefix.extend(chunk[: 8 - len(prefix)])
            digest.update(chunk)
            target.write(chunk)
        target.flush()
        os.fsync(target.fileno())
    if bytes(prefix) != b"\x89HDF\r\n\x1a\n":
        raise ValueError("invalid_h5ad")
    return total, digest.hexdigest()


def inspect_h5ad(
    source: BinaryIO,
    *,
    max_logical_bytes: int,
    max_dataset_elements: int,
) -> list[str]:
    import h5py

    with h5py.File(source, "r") as handle:
        if (
            handle.attrs.get("encoding-type") != "anndata"
            or "obs" not in handle
            or "var" not in handle
        ):
            raise ValueError("invalid_h5ad")
        visited = set()
        logical_bytes = 0

        def check(group, depth=0):
            nonlocal logical_bytes
            if depth > 16 or len(visited) > 10000:
                raise ValueError("h5ad_structure_limit")
            for name in group:
                link = group.get(name, getlink=True)
                if not isinstance(link, h5py.HardLink):
                    raise ValueError("h5ad_external_link")
                item = group[name]
                identity = hash(item.id)
                if identity in visited:
                    continue
                visited.add(identity)
                if isinstance(item, h5py.Group):
                    check(item, depth + 1)
                else:
                    if item.is_virtual or item.external:
                        raise ValueError("h5ad_external_dataset")
                    logical_bytes += item.size * item.dtype.itemsize
                    if item.size > max_dataset_elements:
                        raise ValueError("h5ad_dataset_element_limit")
                    if logical_bytes > max_logical_bytes:
                        raise ValueError("h5ad_logical_size_limit")

        check(handle)
        return (["X"] if "X" in handle else []) + [
            "layers/" + name
            for name in handle.get("layers", {})
            if re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", name)
        ]


class SessionStore:
    """Own private session files and their lock; never import the application."""

    def __init__(self, root: Path, environment: RuntimeEnvironment):
        self.root, self.device, self.inode = ensure_private_directory(root)
        self.binding = bind_storage_environment(self.root, environment)
        self.lock = RLock()

    def cleanup_uploads(self, state):
        directory = self.directory(state["id"]) / "uploads"
        if not directory.exists():
            return
        ensure_private_directory(directory)
        registered = {identifier + ".h5ad" for identifier in state.get("_uploads", {})}
        for path in directory.iterdir():
            orphan = (
                ID.fullmatch(path.stem) and path.suffix == ".h5ad" and path.name not in registered
            )
            if UPLOAD_TEMP.fullmatch(path.name) or orphan:
                info = path.lstat()
                if not (stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode)):
                    raise ValueError("private_file_invalid")
                path.unlink()

    def directory(self, sid):
        verify_private_directory(self.root, device=self.device, inode=self.inode)
        if not ID.fullmatch(sid):
            raise HTTPException(404, "not_found")
        target = self.root / sid
        if not target.exists() or target.is_symlink():
            raise HTTPException(404, "not_found")
        ensure_private_directory(target)
        return target

    def load(self, sid):
        directory = self.directory(sid)
        state = json.loads(read_file(directory / "session.json", SESSION_BYTES_LIMIT))
        binding_bytes = 0
        for turn in self._binding_turns(state):
            references = turn.pop("_binding_files", {})
            if not isinstance(references, dict) or set(references) - set(BINDING_FIELDS):
                raise ValueError("private_binding_invalid")
            for field, sha256 in references.items():
                if (field in turn or not isinstance(sha256, str)
                        or not re.fullmatch(r"[a-f0-9]{64}", sha256)):
                    raise ValueError("private_binding_invalid")
                ensure_private_directory(directory / "assessment-bindings")
                payload = read_file(directory / "assessment-bindings" / (sha256 + ".json"),
                                    BINDING_FILE_BYTES_LIMIT)
                binding_bytes += len(payload)
                if binding_bytes > BINDING_TOTAL_BYTES_LIMIT:
                    raise ValueError("private_file_too_large")
                if hashlib.sha256(payload).hexdigest() != sha256:
                    raise ValueError("private_binding_hash_mismatch")
                value = json.loads(payload)
                if not isinstance(value, dict):
                    raise ValueError("private_binding_invalid")
                turn[field] = value
        state.setdefault("archived", False)
        state.setdefault("research_id", None)
        state.setdefault("run_id", None)
        state.setdefault("conversation_kind", None)
        state.setdefault("plan_history", [])
        state.setdefault("_plan_history", [])
        state.setdefault("_tool_runs", [])
        state.setdefault("_artifact_acknowledgements", {})
        return state

    def find_conversation(self, owner_id, research_id, run_id):
        """Find the canonical binding in session records, including archived chats."""
        verify_private_directory(self.root, device=self.device, inode=self.inode)
        kind = "run" if run_id is not None else "research"
        found = None
        for entry in self.root.iterdir():
            if not ID.fullmatch(entry.name):
                continue
            state = json.loads(read_file(self.directory(entry.name) / "session.json", SESSION_BYTES_LIMIT))
            if (state.get("owner_id") == owner_id and state.get("research_id") == research_id
                    and state.get("run_id") == run_id and state.get("conversation_kind") == kind):
                if found is not None:
                    raise HTTPException(409, "conversation_binding_ambiguous")
                found = entry.name
        return found

    def owner(self, sid, *, include_deleted=False):
        if not ID.fullmatch(sid):
            raise HTTPException(404, "not_found")
        try:
            value = json.loads(read_file(self.directory(sid) / "session.json", SESSION_BYTES_LIMIT))
        except HTTPException as exc:
            if exc.status_code != 404 or not include_deleted:
                raise
            verify_private_directory(self.root, device=self.device, inode=self.inode)
            try:
                value = json.loads(read_file(self.root / (".deleted-" + sid + ".owner"), 1024))
            except FileNotFoundError:
                raise HTTPException(404, "not_found") from None
        owner = value.get("owner_id")
        return owner if isinstance(owner, str) and ID.fullmatch(owner) else None

    def delete(self, sid):
        """Remove only this session tree; a failed cleanup can be retried by ID."""
        verify_private_directory(self.root, device=self.device, inode=self.inode)
        if not ID.fullmatch(sid):
            raise HTTPException(404, "not_found")
        target = self.root / sid
        deleted = self.root / (".deleted-" + sid)
        owner_record = self.root / (".deleted-" + sid + ".owner")
        if target.exists() or target.is_symlink():
            directory = self.directory(sid)
            if deleted.exists() or deleted.is_symlink():
                raise HTTPException(503, "session_cleanup_failed")
            owner = self.owner(sid)
            if owner:
                write_file(owner_record, json.dumps({"owner_id": owner}).encode())
            # Hide the complete tree first so partial cleanup cannot break list/recovery.
            directory.rename(deleted)
        elif deleted.is_symlink() or (not deleted.exists() and not owner_record.exists()):
            raise HTTPException(404, "not_found")
        try:
            if deleted.exists():
                ensure_private_directory(deleted)
                shutil.rmtree(deleted)
            owner_record.unlink(missing_ok=True)
        except OSError:
            raise HTTPException(503, "session_cleanup_failed") from None

    def save(self, state):
        state["updated_at"] = now()
        stored = copy.deepcopy(state)
        files = {}
        binding_bytes = 0
        for turn in self._binding_turns(stored):
            for field in BINDING_FIELDS:
                if field not in turn:
                    continue
                value = turn[field]
                if not isinstance(value, dict):
                    raise ValueError("private_binding_invalid")
                raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
                binding_bytes += len(raw)
                if len(raw) > BINDING_FILE_BYTES_LIMIT or binding_bytes > BINDING_TOTAL_BYTES_LIMIT:
                    raise ValueError("private_file_too_large")
                if len(raw) > 8 * 1024:
                    sha256 = hashlib.sha256(raw).hexdigest()
                    files[sha256] = raw
                    turn.setdefault("_binding_files", {})[field] = sha256
                    del turn[field]
        payload = json.dumps(stored, ensure_ascii=False, separators=(",", ":")).encode()
        if len(payload) > SESSION_BYTES_LIMIT:
            # Never replace a readable session with a file load() must reject.
            raise ValueError("private_file_too_large")
        directory = self.directory(state["id"])
        if files:
            ensure_private_directory(directory / "assessment-bindings")
        for sha256, raw in files.items():
            path = directory / "assessment-bindings" / (sha256 + ".json")
            if path.exists() or path.is_symlink():
                if read_file(path, BINDING_FILE_BYTES_LIMIT) != raw:
                    raise ValueError("private_binding_hash_mismatch")
            else:
                write_file(path, raw)
        write_file(directory / "session.json", payload)

    @staticmethod
    def _binding_turns(state):
        for assessment in [state.get("_assessment"), *state.get("_assessment_history", [])]:
            if assessment:
                yield from assessment.get("model_turns", [])

    def record_skill_usage(self, state, receipts, *, action, purpose, provider_calls):
        """Persist only server-owned workflow identity, never prompt or model text."""
        if not receipts:
            return
        if not 1 <= len(receipts) <= 5 or provider_calls not in {1, 2}:
            raise ValueError("invalid_skill_receipt")
        names = set()
        for receipt in receipts:
            if (set(receipt) != {"name", "sha256", "selection"}
                    or receipt["selection"] not in {"model", "scope"}
                    or load_skill(receipt["name"]).sha256 != receipt["sha256"]
                    or receipt["name"] in names):
                raise ValueError("invalid_skill_receipt")
            names.add(receipt["name"])
        state.setdefault("_skill_invocations", []).append({
            "at": now(), "action": action, "purpose": purpose,
            "input_revision": state.get("_input_revision"),
            "message_id": next((item["id"] for item in reversed(state.get("messages", []))
                                if item.get("role") == "user"), None),
            "assessment_turn": (state.get("_assessment", {}).get("model_turns_used")
                                if purpose == "assessment" else None),
            "provider_calls": provider_calls,
            "skills": [{key: receipt[key] for key in ("name", "sha256", "selection")}
                       for receipt in receipts],
        })
        self.save(state)
