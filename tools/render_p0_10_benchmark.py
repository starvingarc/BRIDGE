#!/usr/bin/env python3
from pathlib import Path

from bridge.tool_packages.p0_10_claim_verifier.benchmark import (
    render_benchmark_markdown,
)


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    output = repo / "tool_packages" / "P0-10" / "BENCHMARK.md"
    output.write_text(render_benchmark_markdown(), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
