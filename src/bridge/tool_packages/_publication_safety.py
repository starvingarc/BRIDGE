from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qsl, urlsplit


PRIVATE_PATH_KEYS = {
    "path",
    "file_path",
    "source_path",
    "input_path",
    "output_path",
    "server_path",
}
WINDOWS_ABSOLUTE_PATH = re.compile(
    r"(?:^|[\s=:'\"(])(?:[A-Za-z]:[\\/]|\\\\[^\\\s]+\\[^\\\s]+)"
)
EMBEDDED_POSIX_PATH = re.compile(
    r"(?:^|[\s=:'\"(])/(?!/)(?:[A-Za-z0-9._~-]+/)+[^\s<>\"']*"
)
URI_URL = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://[^\s<>\"']+")
FILE_URI = re.compile(r"(?i)(?<![A-Za-z0-9+.-])file:")
HOME_RELATIVE_PATH = re.compile(
    r"(?:^|[\s=:'\"(])(?:~[A-Za-z0-9._-]*|\$HOME|\$\{HOME\}|"
    r"\$USERPROFILE|\$\{USERPROFILE\}|\$HOMEPATH|\$\{HOMEPATH\}|"
    r"%HOME%|%USERPROFILE%|%HOMEPATH%)[\\/]",
    re.IGNORECASE,
)
HOME_VARIABLE_NAMES = frozenset({"home", "userprofile", "homepath"})
CREDENTIAL_EXACT_NAMES = frozenset({"auth", "authorization"})
CREDENTIAL_SUFFIXES = (
    "password",
    "passphrase",
    "passwd",
    "pwd",
    "secret",
    "token",
    "credential",
    "credentials",
    "passcode",
    "pincode",
)
CREDENTIAL_KEY_QUALIFIERS = frozenset(
    {
        "api",
        "access",
        "account",
        "client",
        "consumer",
        "database",
        "db",
        "master",
        "private",
        "service",
        "signing",
        "ssh",
        "webhook",
        "encryption",
        "decryption",
        "secret",
    }
)
PIN_CONTEXT_QUALIFIERS = frozenset(
    {
        "access",
        "account",
        "auth",
        "authorization",
        "credential",
        "device",
        "login",
        "security",
        "user",
        "verification",
    }
)
BEARER_CREDENTIAL = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}")
COMMON_CREDENTIAL_TOKEN = re.compile(
    r"(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16})"
)
ASSIGNMENT = re.compile(
    r"(?:^|[\s?&,;])([A-Za-z][A-Za-z0-9_.-]{1,64})\s*[:=]\s*([^\s,;}\]]+)"
)


def normalized_name(value: object) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "", str(value)).casefold()


def _is_credential_name(value: object) -> bool:
    compact = normalized_name(value)
    if compact in CREDENTIAL_EXACT_NAMES or compact.endswith(CREDENTIAL_SUFFIXES):
        return True
    if compact.endswith("pin"):
        stem = compact[:-3]
        return any(
            stem.startswith(qualifier) or stem.endswith(qualifier)
            for qualifier in PIN_CONTEXT_QUALIFIERS
        )
    if not compact.endswith("key"):
        return False
    stem = compact[:-3]
    return any(
        stem.startswith(qualifier) or stem.endswith(qualifier)
        for qualifier in CREDENTIAL_KEY_QUALIFIERS
    )


def _nonempty(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (dict, list, tuple)):
        return bool(value)
    return True


def _unsafe_publication_string(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return False
    if (
        stripped.startswith(("/", "\\\\"))
        or WINDOWS_ABSOLUTE_PATH.search(stripped)
        or EMBEDDED_POSIX_PATH.search(stripped)
        or HOME_RELATIVE_PATH.search(stripped)
        or FILE_URI.search(stripped)
    ):
        return True
    if BEARER_CREDENTIAL.search(stripped) or COMMON_CREDENTIAL_TOKEN.search(stripped):
        return True
    for name, assigned in ASSIGNMENT.findall(stripped):
        if assigned and (
            _is_credential_name(name)
            or normalized_name(name) in HOME_VARIABLE_NAMES
        ):
            return True
    for url in URI_URL.findall(stripped):
        parsed = urlsplit(url.rstrip(".,);]"))
        if parsed.scheme.casefold() == "file" or parsed.username or parsed.password:
            return True
        if any(
            _is_credential_name(key) and bool(item)
            for key, item in parse_qsl(parsed.query, keep_blank_values=True)
        ):
            return True
    return False


def contains_unsafe_reference(value: Any) -> bool:
    """Detect machine paths or credential-like content before publication."""

    if isinstance(value, str):
        return _unsafe_publication_string(value)
    if isinstance(value, dict):
        return any(
            _unsafe_publication_string(str(key))
            or str(key).lower() in PRIVATE_PATH_KEYS
            or (normalized_name(key) in HOME_VARIABLE_NAMES and _nonempty(item))
            or (_is_credential_name(key) and _nonempty(item))
            or contains_unsafe_reference(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(contains_unsafe_reference(item) for item in value)
    return False


def validate_publication_text(value: str) -> str:
    """Keep configured text flexible while rejecting machine-local content."""

    if not value.strip():
        raise ValueError("publication text must not be blank")
    if contains_unsafe_reference(value):
        raise ValueError("unsafe path or credential-like string is forbidden")
    return value
