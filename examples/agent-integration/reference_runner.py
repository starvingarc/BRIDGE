"""Minimal reference bridge between an Agent profile and packaged tools."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from pydantic import ValidationError

from bridge.toolkit import (
    AgentIntegrationProfile,
    run_tool,
    validate_request,
)
from bridge.toolkit.integration import (
    validate_agent_integration_profile,
    validate_profile_request,
)
from bridge.toolkit.registry import ToolRegistry


def _emit(payload: object) -> None:
    print(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str)
    )


def _read_object(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("document must be a JSON object")
    return payload


def _load_profile(path: Path) -> AgentIntegrationProfile:
    profile = AgentIntegrationProfile.model_validate(_read_object(path))
    return validate_agent_integration_profile(profile)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-integration-reference")
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate-profile")
    validate.add_argument("--profile", required=True, type=Path)

    run = commands.add_parser("run-step")
    run.add_argument("--profile", required=True, type=Path)
    run.add_argument("--binding", required=True)
    run.add_argument("--request", required=True, type=Path)
    return parser


def _validate_profile_command(path: Path) -> int:
    try:
        profile = _load_profile(path)
    except (json.JSONDecodeError, OSError, ValidationError, ValueError) as exc:
        _emit({"error": "invalid_profile", "detail": str(exc)})
        return 2
    _emit({"profile_id": profile.profile_id, "valid": True})
    return 0


def _run_step_command(profile_path: Path, binding_id: str, request_path: Path) -> int:
    try:
        profile = _load_profile(profile_path)
    except (json.JSONDecodeError, OSError, ValidationError, ValueError) as exc:
        _emit({"error": "invalid_profile", "detail": str(exc)})
        return 2

    registry = ToolRegistry.load_default()
    try:
        request = registry.parse_request(_read_object(request_path))
    except (
        json.JSONDecodeError,
        OSError,
        KeyError,
        ValidationError,
        ValueError,
    ) as exc:
        _emit({"error": "invalid_request", "detail": str(exc)})
        return 2

    try:
        validate_profile_request(profile, binding_id, request, registry)
    except ValueError as exc:
        detail = str(exc)
        error = (
            "unresolved_input_slot"
            if detail.startswith("unresolved_input_slot")
            else "request_binding_mismatch"
        )
        _emit({"error": error, "detail": detail})
        return 3

    try:
        eligibility = validate_request(request)
    except Exception as exc:
        _emit({"error": "tool_validation_error", "detail": str(exc)})
        return 4
    if not eligibility.eligible:
        _emit(
            {
                "error": "ineligible_request",
                "eligibility": eligibility.model_dump(mode="json"),
            }
        )
        return 3

    try:
        result = run_tool(request)
    except Exception as exc:
        _emit({"error": "tool_execution_error", "detail": str(exc)})
        return 4
    _emit(result.model_dump(mode="json"))
    return 0 if result.execution_state.value in {"succeeded", "partial"} else 3


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate-profile":
        return _validate_profile_command(args.profile)
    return _run_step_command(args.profile, args.binding, args.request)


if __name__ == "__main__":
    raise SystemExit(main())
