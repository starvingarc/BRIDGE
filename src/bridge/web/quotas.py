"""Finite input storage reservations and per-account task admission."""
from contextlib import contextmanager
import os
from fastapi import HTTPException
from .sessions import ID


class UserQuotas:
    def __init__(self, sessions, settings, researches=None):
        self.sessions, self.settings = sessions, settings
        self.researches = researches
        self.tasks = {}
        self.uploads = {}

    @contextmanager
    def reserve_task(self, user_id):
        with self.sessions.lock:
            if self.tasks.get(user_id, 0) >= self.settings.user_task_limit:
                raise HTTPException(429, "user_task_limit")
            self.tasks[user_id] = self.tasks.get(user_id, 0) + 1
        try:
            yield
        finally:
            with self.sessions.lock:
                self.tasks[user_id] -= 1
                if not self.tasks[user_id]:
                    del self.tasks[user_id]

    def usage(self):
        used = {}
        for directory in self.sessions.root.iterdir():
            if not ID.fullmatch(directory.name):
                continue
            owner = self.sessions.owner(directory.name)
            size = 0
            for name in ("uploads", "intake-protocols", "objects"):
                parent = directory / name
                if parent.is_symlink():
                    raise ValueError("private_file_invalid")
                if parent.exists():
                    for entry in os.scandir(parent):
                        if entry.is_file(follow_symlinks=False):
                            size += entry.stat(follow_symlinks=False).st_size
            used[owner] = used.get(owner, 0) + size
        if self.researches is not None:
            for owner, size in self.researches.usage().items():
                used[owner] = used.get(owner, 0) + size
        return used

    @contextmanager
    def reserve_upload(self, user_id, declared_bytes):
        with self.sessions.lock:
            used = self.usage()
            if (declared_bytes < 0 or
                used.get(user_id, 0) + self.uploads.get(user_id, 0) + declared_bytes > self.settings.user_storage_bytes or
                sum(used.values()) + sum(self.uploads.values()) + declared_bytes > self.settings.total_storage_bytes):
                raise HTTPException(429, "storage_quota_exceeded")
            self.uploads[user_id] = self.uploads.get(user_id, 0) + declared_bytes
        try:
            yield
        finally:
            with self.sessions.lock:
                self.uploads[user_id] -= declared_bytes
                if not self.uploads[user_id]:
                    del self.uploads[user_id]
