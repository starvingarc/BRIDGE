#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import yaml

from bridge.toolkit.contracts import ImplementationState, ToolPackageSpecV2
from bridge.toolkit.registry import ToolRegistry


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".css", ".html", ".json", ".jsonl", ".md", ".py", ".toml", ".tsv", ".txt", ".yaml", ".yml"}
EXCLUDED_PARTS = {
    ".git",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
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
PRODUCT_LEVEL_V2_BRANDING = re.compile(r"\bbridge(?:\s+|[-_])v2\b", re.IGNORECASE)
COMPLETED_PLAN_NAME = re.compile(r"(?:^|[-_])(?:complete(?:d)?|done)(?:[-_.]|$)", re.IGNORECASE)
BASELINE_TRACKED_FILES = 300
BASELINE_IMPLEMENTED_TOOL_COUNT = 4
TRACKED_FILES_PER_IMPLEMENTED_TOOL = 25
PACKAGED_ADAPTER_REF = re.compile(
    r"^bridge\.tool_packages(?:\.[A-Za-z_][A-Za-z0-9_]*)+:[A-Za-z_][A-Za-z0-9_]*$"
)


def main() -> int:
    problems: list[str] = []
    tracked_files = _tracked_files()
    if tracked_files is not None:
        max_tracked_files = _tracked_file_budget()
        if len(tracked_files) > max_tracked_files:
            problems.append(
                f"tracked file count exceeds {max_tracked_files}: {len(tracked_files)}"
            )
        _check_tracked_layout(tracked_files, problems)
        paths = [ROOT / relative for relative in tracked_files]
    else:
        paths = ROOT.rglob("*")

    for path in paths:
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        relative_path = path.relative_to(ROOT)
        if path.resolve() == Path(__file__).resolve():
            continue
        if any(part in EXCLUDED_PARTS for part in relative_path.parts):
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_PRIVATE:
            if pattern.search(text):
                problems.append(f"private path pattern {pattern.pattern!r}: {path.relative_to(ROOT)}")
        if path.suffix.lower() == ".md" and "knowledge" not in path.relative_to(ROOT).parts:
            problems.extend(_broken_links(path, text))
        if PRODUCT_LEVEL_V2_BRANDING.search(text):
            problems.append(f"product-level v2 branding in active text: {relative_path}")

    active_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "src").rglob("*.py")
    ).casefold()
    for legacy_term in ("integrated_score", "potency_proxy", "product_pass", "negative_pass"):
        if legacy_term in active_source:
            problems.append(f"legacy scoring term in active source: {legacy_term}")

    _check_projection_parity(problems)
    _check_tool_package_specs(problems)

    if problems:
        print("\n".join(sorted(problems)))
        return 1
    print("Repository policy checks passed")
    return 0


def _tracked_files() -> list[Path] | None:
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return [Path(line) for line in result.stdout.splitlines() if line]


def _tracked_file_budget() -> int:
    implemented = 0
    for path in (ROOT / "src/bridge/tool_packages/specs").glob("*.yaml"):
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        implemented += payload.get("implementation_state") == "implemented"
    added_tools = max(0, implemented - BASELINE_IMPLEMENTED_TOOL_COUNT)
    return BASELINE_TRACKED_FILES + added_tools * TRACKED_FILES_PER_IMPLEMENTED_TOOL


def _check_tracked_layout(tracked_files: list[Path], problems: list[str]) -> None:
    for relative_path in tracked_files:
        if "legacy" in {part.casefold() for part in relative_path.parts}:
            problems.append(f"active legacy directory: {relative_path}")
        if (
            relative_path.parts
            and relative_path.parts[0] == "plans"
            and relative_path.name != "README.md"
            and COMPLETED_PLAN_NAME.search(relative_path.name)
        ):
            problems.append(f"completed plan file remains active: {relative_path}")


def _check_projection_parity(problems: list[str]) -> None:
    card_dir = ROOT / "src" / "bridge" / "tool_packages" / "cards"
    packaged_card_dir = ROOT / "tool_packages"
    public_cards = {path.stem: path for path in card_dir.glob("P0-*.md")}
    packaged_cards = {
        path.parent.name: path for path in packaged_card_dir.glob("P0-*/README.md")
    }
    _check_byte_projection_pair("Tool Card", public_cards, packaged_cards, problems)

    public_schemas = {path.name: path for path in (ROOT / "schemas").glob("*.schema.json")}
    packaged_schemas = {
        path.name: path
        for path in (ROOT / "src" / "bridge" / "resources" / "schemas").glob("*.schema.json")
    }
    _check_byte_projection_pair("schema", public_schemas, packaged_schemas, problems)


def _check_tool_package_specs(problems: list[str]) -> None:
    for path in sorted((ROOT / "src/bridge/tool_packages/specs").glob("*.yaml")):
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if payload.get("input_schema_ref") != "bridge://schemas/tool-request/v0.2":
            continue
        relative = path.relative_to(ROOT)
        state = payload.get("implementation_state")
        adapter_ref = payload.get("adapter_ref")
        result_schema_ref = payload.get("result_schema_ref")
        if state == "implemented":
            if not payload.get("method_ids"):
                problems.append(f"implemented v0.2 Tool Package has no methods: {relative}")
            if not adapter_ref:
                problems.append(f"implemented v0.2 Tool Package has no adapter_ref: {relative}")
            elif not PACKAGED_ADAPTER_REF.fullmatch(adapter_ref):
                problems.append(f"v0.2 Tool Package adapter is not packaged: {relative}")
            if not result_schema_ref:
                problems.append(
                    f"implemented v0.2 Tool Package has no result_schema_ref: {relative}"
                )
            prefix = str(payload.get("tool_id", "")).casefold().replace("-", "_")
            if not list((ROOT / "examples" / "requests").glob(f"{prefix}_*.json")):
                problems.append(
                    f"implemented v0.2 Tool Package has no example request: {relative}"
                )
            if not list((ROOT / "docs" / "validation").glob(f"{prefix}_*.md")):
                problems.append(
                    f"implemented v0.2 Tool Package has no validation record: {relative}"
                )
            card_path = ROOT / "src" / "bridge" / "tool_packages" / "cards" / f"{payload.get('tool_id')}.md"
            if not card_path.is_file():
                problems.append(f"implemented v0.2 Tool Package has no Tool Card: {relative}")
            else:
                card = card_path.read_text(encoding="utf-8")
                required_card_fragments = (
                    "bridge-tool validate --request",
                    "bridge-tool run --request",
                    "ToolRequestV2",
                    "checksum",
                    "reason",
                    "example",
                )
                missing = [item for item in required_card_fragments if item not in card]
                if missing:
                    problems.append(
                        f"implemented v0.2 Tool Card is incomplete: {relative}: {missing}"
                    )
        if state == "scaffold":
            if payload.get("method_ids"):
                problems.append(f"scaffold v0.2 Tool Package claims methods: {relative}")
            if adapter_ref is not None or result_schema_ref is not None:
                problems.append(
                    f"scaffold v0.2 Tool Package claims runtime bindings: {relative}"
                )

    try:
        registry = ToolRegistry.load_default()
    except Exception as exc:
        problems.append(f"Tool Package specs do not load: {exc}")
        return
    for spec in registry.list():
        if not isinstance(spec, ToolPackageSpecV2):
            continue
        if spec.implementation_state is not ImplementationState.IMPLEMENTED:
            continue
        try:
            registry._resolve_result_schema(spec)
        except Exception as exc:
            problems.append(
                f"implemented v0.2 result schema does not resolve: "
                f"{spec.tool_id}: {exc}"
            )
        try:
            registry._resolve_adapter(spec)
        except Exception as exc:
            problems.append(f"implemented v0.2 adapter does not resolve: {spec.tool_id}: {exc}")


def _check_byte_projection_pair(
    label: str,
    public: dict[str, Path],
    packaged: dict[str, Path],
    problems: list[str],
) -> None:
    if public.keys() != packaged.keys():
        problems.append(f"{label} projection inventory mismatch")
        return
    for key in sorted(public):
        if public[key].read_bytes() != packaged[key].read_bytes():
            problems.append(f"{label} projection bytes differ: {key}")


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
