"""Versioned, package-owned research workflows; no execution or user-file access."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
from importlib.resources import files
import re

import yaml


@dataclass(frozen=True)
class ResearchSkill:
    name: str
    description: str
    content: str
    sha256: str


@lru_cache(maxsize=1)
def _packaged_skills() -> tuple[ResearchSkill, ...]:
    skills = []
    for directory in sorted(files(__package__).iterdir(), key=lambda item: item.name):
        if not directory.is_dir() or not re.fullmatch(r"[a-z]+(?:-[a-z]+)*", directory.name):
            continue
        source = directory.joinpath("SKILL.md")
        if not source.is_file():
            continue
        raw = source.read_bytes()
        if len(raw) > 32_768:
            raise ValueError("invalid_packaged_skill")
        content = raw.decode("utf-8")
        parts = content.split("---\n", 2)
        if len(parts) != 3 or parts[0] or not parts[2].strip():
            raise ValueError("invalid_packaged_skill")
        metadata = yaml.safe_load(parts[1])
        if (not isinstance(metadata, dict) or set(metadata) != {"name", "description"}
                or metadata["name"] != directory.name
                or not isinstance(metadata["description"], str)
                or not 1 <= len(metadata["description"].strip()) <= 1024):
            raise ValueError("invalid_packaged_skill")
        skills.append(ResearchSkill(directory.name, metadata["description"].strip(),
                                    content, hashlib.sha256(raw).hexdigest()))
    if not skills:
        raise ValueError("packaged_skills_missing")
    return tuple(skills)


def catalog() -> list[dict[str, str]]:
    """Generate the discovery list from the same files that supply workflow text."""
    return [{"name": skill.name, "description": skill.description} for skill in _packaged_skills()]


def load_skill(name: str) -> ResearchSkill:
    # Compare registered names before any resource access; model input is never a path.
    for skill in _packaged_skills():
        if isinstance(name, str) and skill.name == name:
            return skill
    raise ValueError("invalid_model_skill_request")
