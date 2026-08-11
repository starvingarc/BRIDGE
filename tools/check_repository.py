#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".css", ".html", ".json", ".jsonl", ".md", ".py", ".toml", ".tsv", ".txt", ".yaml", ".yml"}
EXCLUDED_PARTS = {
    ".git",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "legacy",
    "private_assets",
    "run_artifacts",
    "tmp",
    "venv",
}
FORBIDDEN_PRIVATE = (
    re.compile(r"/data[12]/[^/\s\"']+/"),
    re.compile(r"/Users/[^/\s\"']+/"),
    re.compile(r"\\Users\\[^\\\s\"']+\\"),
)
LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")


def main() -> int:
    problems: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if path.resolve() == Path(__file__).resolve():
            continue
        if any(part in EXCLUDED_PARTS for part in path.relative_to(ROOT).parts):
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_PRIVATE:
            if pattern.search(text):
                problems.append(f"private path pattern {pattern.pattern!r}: {path.relative_to(ROOT)}")
        if path.suffix.lower() == ".md" and "knowledge" not in path.relative_to(ROOT).parts:
            problems.extend(_broken_links(path, text))

    active_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "src").rglob("*.py")
    ).casefold()
    for legacy_term in ("integrated_score", "potency_proxy", "product_pass", "negative_pass"):
        if legacy_term in active_source:
            problems.append(f"legacy scoring term in active source: {legacy_term}")

    if problems:
        print("\n".join(sorted(problems)))
        return 1
    print("Repository policy checks passed")
    return 0


def _broken_links(path: Path, text: str) -> list[str]:
    problems: list[str] = []
    for match in LINK.finditer(text):
        target = match.group(1).strip().strip("<>")
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        relative = target.split("#", 1)[0]
        if not relative:
            continue
        if not (path.parent / relative).resolve().exists():
            line = text[: match.start()].count("\n") + 1
            problems.append(f"broken Markdown link: {path.relative_to(ROOT)}:{line}: {target}")
    return problems


if __name__ == "__main__":
    raise SystemExit(main())
