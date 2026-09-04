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
    re.compile(r"/(?:data[0-9]+|mnt|srv)/[^/\s\"']+/"),
    re.compile(r"/Users/[^/\s\"']+/"),
    re.compile(r"\\Users\\[^\\\s\"']+\\"),
)
LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
PRODUCT_LEVEL_V2_BRANDING = re.compile(r"\bbridge(?:\s+|[-_])v2\b", re.IGNORECASE)
COMPLETED_PLAN_NAME = re.compile(r"(?:^|[-_])(?:complete(?:d)?|done)(?:[-_.]|$)", re.IGNORECASE)
TRACKED_FILE_BASELINE = 269
IMPLEMENTED_TOOL_BASELINE = 5
MAX_FILES_PER_NEW_IMPLEMENTED_TOOL = 21
SHARED_CONTRACT_SPINE_FILES = (
    Path("docs/validation/shared_p0_scientific_contract_spine_20260825.md"),
    Path("src/bridge/resources/schemas/biological_unit_assignment.schema.json"),
    Path("src/bridge/resources/schemas/biological_unit_manifest.schema.json"),
    Path("src/bridge/resources/schemas/measurement_result_v2.schema.json"),
    Path("src/bridge/resources/schemas/measurement_spec_v2.schema.json"),
    Path("src/bridge/resources/schemas/qc_readiness_profile_v2.schema.json"),
    Path("src/bridge/resources/schemas/cell_state_evidence_profile_v2.schema.json"),
    Path("src/bridge/resources/schemas/product_case.schema.json"),
    Path("src/bridge/resources/schemas/product_definition_card.schema.json"),
    Path("src/bridge/tool_packages/_configurable_contracts.py"),
    Path("src/bridge/tool_packages/_publication_safety.py"),
    Path("tests/p0_biological_units.py"),
    Path("tests/test_shared_p0_contract_spine.py"),
)
SHARED_VISUALIZATION_CONTRACT_FILES = (
    Path("plans/visualization-data-contract.md"),
    Path("docs/validation/visualization_data_contract_20260828.md"),
    Path("src/bridge/toolkit/visualization.py"),
    Path("src/bridge/resources/schemas/figure_registry.schema.json"),
    Path("src/bridge/resources/schemas/visualization_artifact_v2.schema.json"),
)
AGENT_RUNTIME_FILES = (
    Path("docs/local-agent-runtime.md"),
    Path("src/bridge/domain/__init__.py"),
    Path("src/bridge/domain/models.py"),
    Path("src/bridge/planner/__init__.py"),
    Path("src/bridge/planner/service.py"),
    Path("src/bridge/runners/__init__.py"),
    Path("src/bridge/runners/pipeline.py"),
    Path("src/bridge/storage/__init__.py"),
    Path("src/bridge/storage/artifacts.py"),
    Path("src/bridge/storage/private_paths.py"),
    Path("src/bridge/workflow/__init__.py"),
    Path("src/bridge/workflow/event_store.py"),
    Path("src/bridge/workflow/events.py"),
    Path("src/bridge/workflow/executor.py"),
    Path("tests/test_agent_domain_planner.py"),
    Path("tests/test_local_artifact_store.py"),
    Path("tests/test_tool_execution_pipeline.py"),
    Path("tests/test_workflow_runtime.py"),
)
P001_VISUALIZATION_FILES = (
    Path("plans/p0-01-input-qc-visualization.md"),
    Path("docs/validation/p0_01_input_qc_visualization_20260828.md"),
    Path("src/bridge/tool_packages/p0_01_input_qc/visualization_runtime.py"),
    Path("src/bridge/resources/schemas/p0_01_structured_output_index_v2.schema.json"),
    Path("src/bridge/resources/schemas/p0_01_visualization_artifact_set.schema.json"),
    Path("src/bridge/resources/schemas/qc_visualization_data.schema.json"),
)
P002_VISUALIZATION_FILES = (
    Path("environments/bridge-p0-core-v0.2.yml"),
    Path("src/bridge/resources/schemas/cell_state_evidence_matrix_data.schema.json"),
    Path("src/bridge/resources/schemas/hierarchical_cell_state_composition_data.schema.json"),
    Path("src/bridge/tool_packages/p0_02_cell_state/grouping.py"),
    Path("src/bridge/tool_packages/p0_02_cell_state/hierarchical_composition.py"),
    Path("src/bridge/tool_packages/p0_02_cell_state/visualization_data.py"),
)
P003_VISUALIZATION_FILES = (
    Path("plans/p0-03-target-regional-visualization.md"),
    Path("src/bridge/resources/schemas/p0_03_visualization_artifact_set.schema.json"),
    Path("src/bridge/resources/schemas/target_regional_visualization_data.schema.json"),
    Path("src/bridge/tool_packages/p0_03_target_regional/visualization.py"),
    Path("src/bridge/tool_packages/p0_03_target_regional/visualization_data.py"),
)
P004_VISUALIZATION_FILES = (
    Path("plans/p0-04-developmental-compatibility-visualization.md"),
    Path("environments/bridge-development-py-v0.2.yml"),
    Path("src/bridge/resources/schemas/developmental_compatibility_visualization_data.schema.json"),
    Path("src/bridge/resources/schemas/p0_04_visualization_artifact_set.schema.json"),
    Path("src/bridge/tool_packages/p0_04_developmental_compatibility/visualization.py"),
    Path("src/bridge/tool_packages/p0_04_developmental_compatibility/visualization_data.py"),
)
P005_VISUALIZATION_FILES = (
    Path("src/bridge/resources/schemas/off_target_control_visualization_data.schema.json"),
    Path("src/bridge/resources/schemas/p0_05_visualization_artifact_set.schema.json"),
    Path("src/bridge/tool_packages/p0_05_off_target_control/visualization.py"),
    Path("src/bridge/tool_packages/p0_05_off_target_control/visualization_data.py"),
)
P005_MEASUREMENT_PROJECTION_FILES = (
    Path("src/bridge/resources/schemas/off_target_control_profile_v2.schema.json"),
    Path("src/bridge/tool_packages/p0_05_off_target_control/executor.py"),
)
P006_VISUALIZATION_FILES = (
    Path("src/bridge/resources/schemas/proliferation_stress_visualization_data.schema.json"),
    Path("src/bridge/resources/schemas/p0_06_visualization_artifact_set.schema.json"),
    Path("src/bridge/tool_packages/p0_06_proliferation_stress_response/visualization.py"),
    Path("src/bridge/tool_packages/p0_06_proliferation_stress_response/visualization_data.py"),
)
P006_MEASUREMENT_PROJECTION_FILES = (
    Path("src/bridge/resources/schemas/proliferation_stress_response_profile_v2.schema.json"),
)
P007_VISUALIZATION_FILES = (
    Path("src/bridge/resources/schemas/product_comparison_visualization_data.schema.json"),
    Path("src/bridge/resources/schemas/p0_07_visualization_artifact_set.schema.json"),
    Path("src/bridge/tool_packages/p0_07_product_comparison_stability/visualization.py"),
    Path("src/bridge/tool_packages/p0_07_product_comparison_stability/visualization_data.py"),
)
P008_VISUALIZATION_FILES = (
    Path("environments/bridge-p0-evidence-v0.2.yml"),
    Path("src/bridge/resources/schemas/evidence_sufficiency_visualization_data.schema.json"),
    Path("src/bridge/resources/schemas/p0_08_visualization_artifact_set.schema.json"),
    Path("src/bridge/tool_packages/p0_08_evidence_sufficiency/visualization.py"),
    Path("src/bridge/tool_packages/p0_08_evidence_sufficiency/visualization_data.py"),
)
P009_VISUALIZATION_FILES = (
    Path("src/bridge/resources/schemas/evidence_compiler_visualization_data.schema.json"),
    Path("src/bridge/resources/schemas/p0_09_visualization_artifact_set.schema.json"),
    Path("src/bridge/tool_packages/p0_09_evidence_compiler/visualization.py"),
    Path("src/bridge/tool_packages/p0_09_evidence_compiler/visualization_data.py"),
)
P010_VISUALIZATION_FILES = (
    Path("environments/bridge-p0-evidence-v0.3.yml"),
    Path("src/bridge/resources/schemas/claim_verifier_visualization_data.schema.json"),
    Path("src/bridge/resources/schemas/p0_10_visualization_artifact_set.schema.json"),
    Path("src/bridge/tool_packages/p0_10_claim_verifier/visualization.py"),
    Path("src/bridge/tool_packages/p0_10_claim_verifier/visualization_data.py"),
)
P011_VISUALIZATION_FILES = (
    Path("src/bridge/resources/schemas/public_safe_export_visualization_data.schema.json"),
    Path("src/bridge/resources/schemas/p0_11_visualization_artifact_set.schema.json"),
    Path("src/bridge/tool_packages/p0_11_public_safe_export/visualization.py"),
    Path("src/bridge/tool_packages/p0_11_public_safe_export/visualization_data.py"),
)
P012_VISUALIZATION_FILES = (
    Path("src/bridge/resources/schemas/graft_assessment_visualization_data.schema.json"),
    Path("src/bridge/resources/schemas/p0_12_visualization_artifact_set.schema.json"),
    Path("src/bridge/tool_packages/p0_12_graft_assessment/visualization.py"),
    Path("src/bridge/tool_packages/p0_12_graft_assessment/visualization_data.py"),
)
PACKAGED_ADAPTER_REF = re.compile(
    r"^bridge\.tool_packages(?:\.[A-Za-z_][A-Za-z0-9_]*)+:[A-Za-z_][A-Za-z0-9_]*$"
)


def main() -> int:
    problems: list[str] = []
    tracked_files = _tracked_files()
    if tracked_files is not None:
        tracked_file_budget = _tracked_file_budget()
        if len(tracked_files) > tracked_file_budget:
            problems.append(
                f"tracked file count exceeds {tracked_file_budget}: {len(tracked_files)}"
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
    for path in (ROOT / "src/bridge/tool_packages/specs").glob("p0_*.yaml"):
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        implemented += payload.get("implementation_state") == "implemented"
    added_tools = max(0, implemented - IMPLEMENTED_TOOL_BASELINE)
    shared_files = sum(
        (ROOT / relative).is_file()
        for relative in SHARED_CONTRACT_SPINE_FILES
    )
    visualization_contract_files = sum(
        (ROOT / relative).is_file()
        for relative in SHARED_VISUALIZATION_CONTRACT_FILES
    )
    agent_runtime_files = sum(
        (ROOT / relative).is_file()
        for relative in AGENT_RUNTIME_FILES
    )
    p001_visualization_files = sum(
        (ROOT / relative).is_file()
        for relative in P001_VISUALIZATION_FILES
    )
    p002_visualization_files = sum(
        (ROOT / relative).is_file()
        for relative in P002_VISUALIZATION_FILES
    )
    p003_visualization_files = sum(
        (ROOT / relative).is_file()
        for relative in P003_VISUALIZATION_FILES
    )
    p004_visualization_files = sum(
        (ROOT / relative).is_file()
        for relative in P004_VISUALIZATION_FILES
    )
    p005_visualization_files = sum(
        (ROOT / relative).is_file()
        for relative in P005_VISUALIZATION_FILES
    )
    p005_measurement_projection_files = sum(
        (ROOT / relative).is_file()
        for relative in P005_MEASUREMENT_PROJECTION_FILES
    )
    p006_visualization_files = sum(
        (ROOT / relative).is_file()
        for relative in P006_VISUALIZATION_FILES
    )
    p006_measurement_projection_files = sum(
        (ROOT / relative).is_file()
        for relative in P006_MEASUREMENT_PROJECTION_FILES
    )
    p007_visualization_files = sum(
        (ROOT / relative).is_file()
        for relative in P007_VISUALIZATION_FILES
    )
    p008_visualization_files = sum(
        (ROOT / relative).is_file()
        for relative in P008_VISUALIZATION_FILES
    )
    p009_visualization_files = sum(
        (ROOT / relative).is_file()
        for relative in P009_VISUALIZATION_FILES
    )
    p010_visualization_files = sum(
        (ROOT / relative).is_file()
        for relative in P010_VISUALIZATION_FILES
    )
    p011_visualization_files = sum(
        (ROOT / relative).is_file()
        for relative in P011_VISUALIZATION_FILES
    )
    p012_visualization_files = sum(
        (ROOT / relative).is_file()
        for relative in P012_VISUALIZATION_FILES
    )
    return (
        TRACKED_FILE_BASELINE
        + p004_visualization_files
        + p005_visualization_files
        + p005_measurement_projection_files
        + p006_visualization_files
        + p006_measurement_projection_files
        + p007_visualization_files
        + p008_visualization_files
        + p009_visualization_files
        + p010_visualization_files
        + p011_visualization_files
        + p012_visualization_files
        + added_tools * MAX_FILES_PER_NEW_IMPLEMENTED_TOOL
        + shared_files
        + visualization_contract_files
        + agent_runtime_files
        + p001_visualization_files
        + p002_visualization_files
        + p003_visualization_files
    )

def _check_tracked_layout(tracked_files: list[Path], problems: list[str]) -> None:
    for relative_path in tracked_files:
        if relative_path.parts and relative_path.parts[0] in {"schemas", "tool_packages"}:
            problems.append(f"duplicate root projection: {relative_path}")
        if relative_path.parts and relative_path.parts[0] in {"catalog_seed", "tools"}:
            problems.append(f"obsolete root directory: {relative_path}")
        if relative_path == Path("PLANS.md"):
            problems.append("obsolete root plan index: PLANS.md")
        if "legacy" in {part.casefold() for part in relative_path.parts}:
            problems.append(f"active legacy directory: {relative_path}")
        if (
            relative_path.parts
            and relative_path.parts[0] == "plans"
            and relative_path.name != "README.md"
            and COMPLETED_PLAN_NAME.search(relative_path.name)
        ):
            problems.append(f"completed plan file remains active: {relative_path}")

def _check_tool_package_specs(problems: list[str]) -> None:
    for path in sorted((ROOT / "src/bridge/tool_packages/specs").glob("*.yaml")):
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        tool_id = str(payload.get("tool_id", ""))
        package_prefix = tool_id.casefold().replace("-", "_")
        package_dirs = sorted(
            item
            for item in (ROOT / "src/bridge/tool_packages").glob(f"{package_prefix}_*")
            if item.is_dir()
        )
        if len(package_dirs) != 1:
            problems.append(
                f"Tool Package must have exactly one implementation directory: "
                f"{tool_id}: {len(package_dirs)}"
            )
        else:
            package_readme = package_dirs[0] / "README.md"
            if not package_readme.is_file():
                problems.append(f"Tool Package has no package README: {tool_id}")
            else:
                readme = package_readme.read_text(encoding="utf-8")
                required_readme_fragments = (
                    f"../cards/{tool_id}.md",
                    "../../../../docs/bridge_spec_v0.1/",
                    "../../../../examples/requests/",
                )
                missing = [
                    item for item in required_readme_fragments if item not in readme
                ]
                if missing:
                    problems.append(
                        f"Tool Package README is incomplete: {tool_id}: {missing}"
                    )
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
