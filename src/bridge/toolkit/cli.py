from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from pydantic import ValidationError

from bridge.toolkit.registry import ToolRegistry


def _emit(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bridge-tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--json", action="store_true")

    describe_parser = subparsers.add_parser("describe")
    describe_parser.add_argument("tool_id")
    describe_parser.add_argument("--json", action="store_true")

    input_parser = subparsers.add_parser("input-contract")
    input_parser.add_argument("tool_id")
    input_parser.add_argument("--json", action="store_true")

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--request", required=True, type=Path)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--request", required=True, type=Path)

    figures_parser = subparsers.add_parser("figures")
    figure_subparsers = figures_parser.add_subparsers(
        dest="figures_command",
        required=True,
    )
    figure_list = figure_subparsers.add_parser("list")
    figure_list.add_argument("--tool")
    figure_show = figure_subparsers.add_parser("show")
    figure_show.add_argument("component_ref")
    figure_subparsers.add_parser("validate")

    knowledge_parser = subparsers.add_parser("knowledge")
    knowledge_subparsers = knowledge_parser.add_subparsers(dest="knowledge_command", required=True)
    knowledge_subparsers.add_parser("validate")
    show_parser = knowledge_subparsers.add_parser("show")
    show_parser.add_argument("knowledge_id")
    search_parser = knowledge_subparsers.add_parser("search")
    search_parser.add_argument("query")
    search_parser.add_argument("--module")
    search_parser.add_argument("--method")
    search_parser.add_argument("--source-type")
    search_parser.add_argument("--status")
    search_parser.add_argument("--allowed-use")
    search_parser.add_argument("--limit", type=int, default=10)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    registry = ToolRegistry.load_default()

    if args.command == "list":
        payload = [spec.model_dump(mode="json") for spec in registry.list()]
        _emit(payload)
        return 0

    if args.command == "describe":
        try:
            spec = registry.describe(args.tool_id)
        except KeyError:
            _emit({"error": "unknown_tool", "tool_id": args.tool_id})
            return 2
        _emit(spec.model_dump(mode="json"))
        return 0

    if args.command == "input-contract":
        try:
            contract = registry.describe_input(args.tool_id)
        except KeyError:
            _emit({"error": "unknown_tool", "tool_id": args.tool_id})
            return 2
        _emit(contract.model_dump(mode="json"))
        return 0

    if args.command in {"validate", "run"}:
        try:
            payload = json.loads(args.request.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("request must be a JSON object")
            request = registry.parse_request(payload)
        except (json.JSONDecodeError, OSError, KeyError, ValidationError, ValueError) as exc:
            _emit({"error": "invalid_request", "detail": str(exc)})
            return 2
        if args.command == "validate":
            try:
                eligibility = registry.check_eligibility(request)
            except Exception as exc:
                _emit(
                    {
                        "error": "tool_validation_error",
                        "detail": str(exc),
                        "tool_id": request.tool_id,
                    }
                )
                return 4
            _emit(eligibility.model_dump(mode="json"))
            return 0 if eligibility.eligible else 3
        try:
            result = registry.run(request)
        except Exception as exc:
            _emit({"error": "tool_execution_error", "detail": str(exc), "tool_id": request.tool_id})
            return 4
        _emit(result.model_dump(mode="json"))
        return 0 if result.execution_state.value in {"succeeded", "partial"} else 3

    if args.command == "figures":
        from bridge.toolkit.visualization import FigureRegistry

        figures = FigureRegistry.load_default()
        if args.figures_command == "validate":
            summary = figures.validation_summary()
            _emit(summary)
            return 0 if summary["valid"] else 3
        if args.figures_command == "show":
            try:
                component = figures.get(args.component_ref)
            except KeyError:
                _emit(
                    {
                        "error": "unknown_figure_component",
                        "component_ref": args.component_ref,
                    }
                )
                return 2
            _emit(component.model_dump(mode="json"))
            return 0
        _emit(
            [
                component.model_dump(mode="json")
                for component in figures.list(tool_id=args.tool)
            ]
        )
        return 0

    if args.command == "knowledge":
        from bridge.toolkit.knowledge import KnowledgeRegistry

        knowledge = KnowledgeRegistry.load_default()
        if args.knowledge_command == "validate":
            summary = knowledge.validation_summary()
            _emit(summary)
            return 0 if summary["valid"] else 3
        if args.knowledge_command == "show":
            try:
                _emit(knowledge.get_record(args.knowledge_id))
            except KeyError:
                _emit({"error": "unknown_knowledge_id", "knowledge_id": args.knowledge_id})
                return 2
            return 0
        hits = knowledge.search(
            args.query,
            module_id=args.module,
            method_id=args.method,
            source_type=args.source_type,
            scientific_status=args.status,
            allowed_use=args.allowed_use,
            limit=args.limit,
        )
        _emit([hit.model_dump(mode="json") for hit in hits])
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
