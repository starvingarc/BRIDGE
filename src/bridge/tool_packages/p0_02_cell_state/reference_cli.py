from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from bridge.tool_packages.p0_02_cell_state.reference import (
    ReferenceError,
    build_reference_snapshot,
    validate_reference_snapshot,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bridge-reference")
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--catalog", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--snapshot", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        manifest = (
            build_reference_snapshot(args.catalog, args.output)
            if args.command == "build"
            else validate_reference_snapshot(args.snapshot)
        )
    except (OSError, ValueError, ReferenceError) as exc:
        reason = getattr(exc, "reason_code", "reference_command_failed")
        print(json.dumps({"error": reason, "detail": str(exc)}, indent=2, sort_keys=True))
        return 3
    print(json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
