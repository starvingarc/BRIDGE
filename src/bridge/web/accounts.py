"""Private accounts and revocable logins; no browser-supplied role is trusted."""
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import os
import re
import secrets
import sqlite3
from threading import RLock
import time
from typing import Literal

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import HTTPException

from bridge.storage.private_paths import ensure_private_directory, verify_private_directory
from .sessions import open_private_file

NOTICE_VERSION = "internal-testing-v1"
NOTICE = "这是内部测试服务，管理员可以查看会话、上传材料及生成结果，用于排查问题和改进服务。"
USERNAME_PATTERN = r"[a-zA-Z0-9][a-zA-Z0-9_.-]{2,31}"
PASSWORD_MIN = 12
PASSWORD_MAX = 128


@dataclass(frozen=True)
class Principal:
    id: str
    username: str
    role: Literal["user", "admin"]
    must_change_password: bool = False


class AccountStore:
    def __init__(self, root, cookie_ttl=12 * 3600):
        self.root, self.device, self.inode = ensure_private_directory(root)
        self.path = self.root / "accounts.sqlite3"
        self.lock = RLock()
        self.cookie_ttl = cookie_ttl
        self.hasher = PasswordHasher()
        self.dummy_hash = self.hasher.hash(secrets.token_urlsafe(24))
        try:
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        except FileExistsError:
            pass
        else:
            os.close(fd)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL, role TEXT NOT NULL,
                    disabled INTEGER NOT NULL DEFAULT 0,
                    must_change_password INTEGER NOT NULL DEFAULT 0,
                    notice_version TEXT NOT NULL, created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS logins (
                    digest TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
                    expires REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS admin_audit (
                    id INTEGER PRIMARY KEY, actor_id TEXT NOT NULL,
                    target_user_id TEXT, sid TEXT, action TEXT NOT NULL,
                    outcome TEXT NOT NULL, created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS rate_limits (
                    key TEXT PRIMARY KEY, used INTEGER NOT NULL, expires REAL NOT NULL
                );
            """)

    @contextmanager
    def connect(self):
        with self.lock:
            verify_private_directory(self.root, device=self.device, inode=self.inode)
            with open_private_file(self.path) as stream:
                if os.fstat(stream.fileno()).st_mode & 0o077:
                    raise ValueError("unsafe_account_permissions")
            db = sqlite3.connect(self.path, timeout=10)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            try:
                with db:
                    yield db
            finally:
                db.close()

    @staticmethod
    def principal(row):
        return Principal(row["id"], row["username"], row["role"], bool(row["must_change_password"]))

    @staticmethod
    def username(value):
        value = value.strip().lower()
        if not re.fullmatch(USERNAME_PATTERN, value):
            raise HTTPException(422, "invalid_account")
        return value

    @staticmethod
    def validate_password(value):
        if not PASSWORD_MIN <= len(value) <= PASSWORD_MAX:
            raise HTTPException(422, "invalid_password")

    def _verify(self, row, password):
        try:
            self.hasher.verify(row["password_hash"] if row else self.dummy_hash, password)
        except VerificationError:
            raise HTTPException(401, "authentication_failed") from None
        if row is None or row["disabled"]:
            raise HTTPException(401, "authentication_failed")

    def _insert(self, db, username, password, role, notice_version):
        self.validate_password(password)
        identifier = secrets.token_hex(16)
        try:
            db.execute("INSERT INTO users(id,username,password_hash,role,notice_version,created_at) VALUES(?,?,?,?,?,?)",
                       (identifier, username, self.hasher.hash(password), role, notice_version, time.time()))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "username_unavailable") from None
        return Principal(identifier, username, role)

    def register(self, username, password, notice_version):
        username = self.username(username)
        if notice_version != NOTICE_VERSION:
            raise HTTPException(422, "testing_notice_required")
        with self.connect() as db:
            return self._insert(db, username, password, "user", notice_version)

    def bootstrap_admin(self, username, password):
        username = self.username(username)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            admin = db.execute("SELECT * FROM users WHERE role='admin'").fetchone()
            if admin:
                if admin["username"] != username:
                    raise HTTPException(409, "administrator_already_initialized")
                self._verify(admin, password)
                return self.principal(admin)
            return self._insert(db, username, password, "admin", NOTICE_VERSION)

    def authenticate(self, username, password):
        # Invalid names receive the same login failure as an unknown account.
        username = username.strip().lower()
        with self.connect() as db:
            row = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
            self._verify(row, password)
            if self.hasher.check_needs_rehash(row["password_hash"]):
                db.execute("UPDATE users SET password_hash=? WHERE id=?", (self.hasher.hash(password), row["id"]))
            return self.principal(row)

    def issue_login(self, user_id):
        cookie = secrets.token_urlsafe(32)
        with self.connect() as db:
            if not db.execute("SELECT 1 FROM users WHERE id=? AND disabled=0", (user_id,)).fetchone():
                raise HTTPException(401, "authentication_required")
            db.execute("DELETE FROM logins WHERE expires<=?", (time.time(),))
            # Bound retained sessions without invalidating other users' sessions.
            db.execute("DELETE FROM logins WHERE digest IN (SELECT digest FROM logins WHERE user_id=? ORDER BY expires DESC LIMIT -1 OFFSET 19)", (user_id,))
            db.execute("INSERT INTO logins VALUES(?,?,?)",
                       (self.digest(cookie), user_id, time.time() + self.cookie_ttl))
        return cookie

    @staticmethod
    def digest(value):
        return hashlib.sha256(value.encode()).hexdigest()

    def resolve_login(self, cookie):
        if not cookie or len(cookie) > 128:
            return None
        with self.connect() as db:
            row = db.execute("SELECT users.* FROM logins JOIN users ON users.id=logins.user_id WHERE digest=? AND expires>? AND disabled=0",
                             (self.digest(cookie), time.time())).fetchone()
            return self.principal(row) if row else None

    def revoke_login(self, cookie):
        with self.connect() as db:
            db.execute("DELETE FROM logins WHERE digest=?", (self.digest(cookie),))

    def change_password(self, user_id, old_password, password):
        self.validate_password(password)
        with self.connect() as db:
            row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
            self._verify(row, old_password)
            db.execute("UPDATE users SET password_hash=?,must_change_password=0 WHERE id=?",
                       (self.hasher.hash(password), user_id))
            db.execute("DELETE FROM logins WHERE user_id=?", (user_id,))

    def reset_password(self, user_id):
        password = secrets.token_urlsafe(18)
        with self.connect() as db:
            if not db.execute("SELECT 1 FROM users WHERE id=?", (user_id,)).fetchone():
                raise HTTPException(404, "not_found")
            db.execute("UPDATE users SET password_hash=?,must_change_password=1 WHERE id=?",
                       (self.hasher.hash(password), user_id))
            db.execute("DELETE FROM logins WHERE user_id=?", (user_id,))
        return password

    def disable(self, user_id):
        with self.connect() as db:
            row = db.execute("SELECT role FROM users WHERE id=?", (user_id,)).fetchone()
            if row is None:
                raise HTTPException(404, "not_found")
            if row["role"] == "admin":
                raise HTTPException(409, "administrator_required")
            db.execute("UPDATE users SET disabled=1 WHERE id=?", (user_id,))
            db.execute("DELETE FROM logins WHERE user_id=?", (user_id,))

    def limit(self, key, *, maximum, window):
        now = time.time()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM rate_limits WHERE expires<=?", (now,))
            key = self.digest(key)
            row = db.execute("SELECT used FROM rate_limits WHERE key=?", (key,)).fetchone()
            if row and row["used"] >= maximum:
                raise HTTPException(429, "too_many_attempts")
            db.execute("INSERT INTO rate_limits VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET used=used+1",
                       (key, now + window))


    def users(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT id,username,role,disabled,must_change_password,created_at FROM users ORDER BY username")]

    def record_access(self, actor_id, target_user_id, sid, action, outcome):
        with self.connect() as db:
            db.execute("INSERT INTO admin_audit(actor_id,target_user_id,sid,action,outcome,created_at) VALUES(?,?,?,?,?,?)",
                       (actor_id, target_user_id, sid, action[:512], outcome, time.time()))

    def audit_events(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM admin_audit ORDER BY id DESC LIMIT 100")]
