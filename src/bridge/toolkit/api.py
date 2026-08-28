from __future__ import annotations

from bridge.tool_packages._input_contracts import ToolInputContract
from bridge.toolkit.contracts import (
    EligibilityResult,
    KnowledgeHit,
    ToolPackageSpec,
    ToolPackageSpecV2,
    ToolRequest,
    ToolRequestV2,
    ToolRun,
    ToolRunV2,
)
from bridge.toolkit.knowledge import KnowledgeRegistry
from bridge.toolkit.registry import ToolRegistry
from bridge.toolkit.visualization import FigureComponentSpec, FigureRegistry


def list_tools() -> list[ToolPackageSpec | ToolPackageSpecV2]:
    return ToolRegistry.load_default().list()


def describe_tool(tool_id: str) -> ToolPackageSpec | ToolPackageSpecV2:
    return ToolRegistry.load_default().describe(tool_id)


def describe_tool_input(tool_id: str) -> ToolInputContract:
    return ToolRegistry.load_default().describe_input(tool_id)


def validate_request(request: ToolRequest | ToolRequestV2) -> EligibilityResult:
    return ToolRegistry.load_default().check_eligibility(request)


def run_tool(request: ToolRequest | ToolRequestV2) -> ToolRun | ToolRunV2:
    return ToolRegistry.load_default().run(request)


def search_knowledge(
    query: str,
    *,
    module_id: str | None = None,
    method_id: str | None = None,
    source_type: str | None = None,
    scientific_status: str | None = None,
    allowed_use: str | None = None,
    limit: int = 10,
) -> list[KnowledgeHit]:
    return KnowledgeRegistry.load_default().search(
        query,
        module_id=module_id,
        method_id=method_id,
        source_type=source_type,
        scientific_status=scientific_status,
        allowed_use=allowed_use,
        limit=limit,
    )


def list_figure_components(
    *,
    tool_id: str | None = None,
) -> list[FigureComponentSpec]:
    return FigureRegistry.load_default().list(tool_id=tool_id)


def describe_figure_component(component_ref: str) -> FigureComponentSpec:
    return FigureRegistry.load_default().get(component_ref)


def validate_figure_registry() -> dict[str, object]:
    return FigureRegistry.load_default().validation_summary()
