#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path

from bridge.tool_packages.p0_10_claim_verifier.benchmark import (
    decision_payload_sha256,
    render_benchmark_markdown,
)
from bridge.tool_packages.p0_10_claim_verifier.models import ClaimVerifierBenchmark


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    resource = (
        repo
        / "src/bridge/tool_packages/p0_10_claim_verifier/resources/benchmark_v0.1.json"
    )
    payload = json.loads(resource.read_text(encoding="utf-8"))
    for method in payload["methods"]:
        method.setdefault("negative_controls", [])
        method["decision"]["benchmark_sha256"] = None
    normalized = ClaimVerifierBenchmark.model_validate(payload).model_dump(mode="json")
    decision_hash = decision_payload_sha256(normalized)
    for method in normalized["methods"]:
        method["decision"]["benchmark_sha256"] = decision_hash
    benchmark = ClaimVerifierBenchmark.model_validate(normalized)
    resource_bytes = (
        json.dumps(
            benchmark.model_dump(mode="json"),
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    resource.write_bytes(resource_bytes)
    output = repo / "tool_packages" / "P0-10" / "BENCHMARK.md"
    output.write_text(
        render_benchmark_markdown(
            benchmark,
            sha256=hashlib.sha256(resource_bytes).hexdigest(),
        ),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
