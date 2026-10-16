"""Account-owned research metadata and immutable shared originals.

Scientific declarations, chat history and results remain in SessionStore.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
from typing import BinaryIO

from fastapi import HTTPException

from bridge.storage.private_paths import ensure_private_directory, verify_private_directory
from .intake_sources import PROTOCOL_LIMIT, protocol_text
from .sessions import (
    ID, UPLOAD_CHUNK_BYTES, UploadLimitExceeded, inspect_h5ad, now,
    open_private_file, read_file, stream_upload, uid, write_file,
)

RESEARCH_LIMIT = 256
MATERIAL_LIMIT = 128
MANIFEST_LIMIT = 1024 * 1024
MATERIAL_PUBLIC = ("id", "name", "kind", "size", "created_at", "locations")
RESEARCH_PUBLIC = ("id", "name", "description", "created_at", "updated_at")
PROTOCOL_SUFFIXES = {".txt", ".md", ".pdf", ".docx"}


class ResearchStore:
    def __init__(self, sessions):
        self.root, self.device, self.inode = ensure_private_directory(sessions.root / "researches")
        self.lock = sessions.lock

    def directory(self, rid: str) -> Path:
        verify_private_directory(self.root, device=self.device, inode=self.inode)
        if not isinstance(rid, str) or not ID.fullmatch(rid):
            raise HTTPException(404, "not_found")
        directory = self.root / rid
        if directory.is_symlink() or not directory.exists():
            raise HTTPException(404, "not_found")
        ensure_private_directory(directory)
        return directory

    def load(self, rid):
        return json.loads(read_file(self.directory(rid) / "research.json", MANIFEST_LIMIT))

    def owned(self, owner_id, rid):
        state = self.load(rid)
        if state.get("owner_id") != owner_id:
            raise HTTPException(404, "not_found")
        return state

    def authorize(self, principal, rid):
        try:
            self.owned(principal.id, rid)
        except HTTPException as exc:
            if exc.status_code == 404:
                raise HTTPException(404, "research_not_found") from None
            raise

    def save(self, state):
        state["updated_at"] = now()
        raw = json.dumps(state, ensure_ascii=False, separators=(",", ":")).encode()
        if len(raw) > MANIFEST_LIMIT:
            raise HTTPException(413, "research_limit")
        write_file(self.directory(state["id"]) / "research.json", raw)

    @staticmethod
    def public(state, sessions=(), *, detail=False):
        value = {key: state[key] for key in RESEARCH_PUBLIC}
        value["session_count"] = sum(item.get("research_id") == state["id"] for item in sessions)
        value["material_count"] = len(state["materials"])
        if detail:
            value["materials"] = [{key: item[key] for key in MATERIAL_PUBLIC if key in item} for item in state["materials"]]
        return value

    def list_owned(self, owner_id):
        verify_private_directory(self.root, device=self.device, inode=self.inode)
        values = []
        for directory in self.root.iterdir():
            if ID.fullmatch(directory.name):
                state = self.load(directory.name)
                if state.get("owner_id") == owner_id:
                    values.append(state)
        return sorted(values, key=lambda item: item["updated_at"], reverse=True)

    def create(self, owner_id, name, description=""):
        with self.lock:
            if len(self.list_owned(owner_id)) >= RESEARCH_LIMIT:
                raise HTTPException(409, "research_limit")
            rid = uid()
            state = {"id": rid, "owner_id": owner_id, "name": name, "description": description,
                     "created_at": now(), "updated_at": now(), "materials": []}
            ensure_private_directory(self.root / rid)
            self.save(state)
            return state

    def material(self, owner_id, rid, mid):
        state = self.owned(owner_id, rid)
        if not isinstance(mid, str) or not ID.fullmatch(mid):
            raise HTTPException(404, "not_found")
        item = next((item for item in state["materials"] if item["id"] == mid), None)
        if item is None:
            raise HTTPException(404, "not_found")
        return item

    @staticmethod
    def file_kind(name):
        if (not name or len(name) > 120 or "/" in name or "\\" in name
                or re.search(r"[\x00-\x1f\x7f]", name)):
            raise HTTPException(400, "invalid_upload_name")
        suffix = Path(name).suffix.lower()
        if suffix == ".h5ad":
            return "h5ad"
        if suffix in PROTOCOL_SUFFIXES:
            return "protocol"
        if suffix in {".csv", ".tsv"}:
            return "metadata"
        raise HTTPException(422, "research_material_type")

    def put(self, owner_id, rid, name, source: BinaryIO, *, max_upload_bytes,
            max_logical_bytes, max_dataset_elements):
        kind = self.file_kind(name)
        with self.lock:
            if len(self.owned(owner_id, rid)["materials"]) >= MATERIAL_LIMIT:
                raise HTTPException(409, "research_material_limit")
            directory, _, _ = ensure_private_directory(self.directory(rid) / "materials")
        mid = uid()
        temporary, destination = directory / ("." + mid + ".upload"), directory / (mid + ".bin")
        committed = False
        try:
            locations = []
            if kind == "h5ad":
                size, checksum = stream_upload(source, temporary, max_upload_bytes)
                with open_private_file(temporary, max_upload_bytes) as stream:
                    locations = inspect_h5ad(stream, max_logical_bytes=max_logical_bytes,
                                              max_dataset_elements=max_dataset_elements)
            else:
                limit = min(PROTOCOL_LIMIT, max_upload_bytes)
                raw = source.read(limit + 1)
                if len(raw) > limit:
                    raise UploadLimitExceeded("protocol_too_large")
                if not raw:
                    raise HTTPException(422, "research_material_empty")
                if kind == "protocol":
                    protocol_text(name, raw)
                else:
                    text = raw.decode("utf-8-sig")
                    if "\x00" in text:
                        raise ValueError("invalid_metadata_text")
                size, checksum = len(raw), hashlib.sha256(raw).hexdigest()
                write_file(temporary, raw)
            item = {"id": mid, "name": name, "kind": kind, "size": size, "created_at": now(),
                    "sha256": checksum, "locations": locations}
            with self.lock:
                state = self.owned(owner_id, rid)
                if len(state["materials"]) >= MATERIAL_LIMIT:
                    raise HTTPException(409, "research_material_limit")
                os.replace(temporary, destination)
                state["materials"].append(item)
                self.save(state)
                committed = True
            return item
        finally:
            temporary.unlink(missing_ok=True)
            if not committed:
                destination.unlink(missing_ok=True)

    @contextmanager
    def checked_material(self, owner_id, rid, mid):
        item = self.material(owner_id, rid, mid)
        directory, _, _ = ensure_private_directory(self.directory(rid) / "materials")
        with open_private_file(directory / (mid + ".bin"), item["size"]) as stream:
            checksum = hashlib.sha256()
            total = 0
            while chunk := stream.read(UPLOAD_CHUNK_BYTES):
                total += len(chunk)
                checksum.update(chunk)
            if total != item["size"] or checksum.hexdigest() != item["sha256"]:
                raise ValueError("research_material_integrity")
            stream.seek(0)
            yield stream

    def copy_to(self, owner_id, rid, mid, destination):
        """Independent private copy; no hardlink or mutable alias into the library."""
        ensure_private_directory(destination.parent)
        with self.checked_material(owner_id, rid, mid) as source:
            fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            try:
                with os.fdopen(fd, "wb") as target:
                    while chunk := source.read(UPLOAD_CHUNK_BYTES):
                        target.write(chunk)
                    target.flush()
                    os.fsync(target.fileno())
            except BaseException:
                destination.unlink(missing_ok=True)
                raise

    def usage(self):
        """Count actual originals and in-progress private files conservatively."""
        used = {}
        verify_private_directory(self.root, device=self.device, inode=self.inode)
        for directory in self.root.iterdir():
            if not ID.fullmatch(directory.name):
                continue
            state = self.load(directory.name)
            parent = directory / "materials"
            if parent.is_symlink():
                raise ValueError("private_file_invalid")
            size = 0
            if parent.exists():
                for entry in os.scandir(parent):
                    if entry.is_file(follow_symlinks=False):
                        size += entry.stat(follow_symlinks=False).st_size
            used[state["owner_id"]] = used.get(state["owner_id"], 0) + size
        return used
