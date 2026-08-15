from __future__ import annotations

from copy import deepcopy
import hashlib
from importlib.resources import files
import json

from bridge.tool_packages._structured_runtime import canonical_json_bytes
from bridge.tool_packages.p0_10_claim_verifier.models import ClaimVerifierBenchmark


BENCHMARK_FILENAME = "benchmark_v0.1.json"
APPROVED_BENCHMARK_SHA256 = (
    "dd3c8dbcf8ecd7eb6881c503d8cc100788edbac4f2a5d7983cc6b0b67e56434a"
)


def benchmark_bytes() -> bytes:
    return files(
        "bridge.tool_packages.p0_10_claim_verifier.resources"
    ).joinpath(BENCHMARK_FILENAME).read_bytes()


def benchmark_sha256() -> str:
    return hashlib.sha256(benchmark_bytes()).hexdigest()


def decision_payload_sha256(payload: dict) -> str:
    normalized = deepcopy(payload)
    for method in normalized["methods"]:
        method["decision"]["benchmark_sha256"] = None
    return hashlib.sha256(canonical_json_bytes(normalized)).hexdigest()


def load_benchmark() -> ClaimVerifierBenchmark:
    if benchmark_sha256() != APPROVED_BENCHMARK_SHA256:
        raise ValueError("benchmark does not match the approved package record")
    benchmark = ClaimVerifierBenchmark.model_validate_json(benchmark_bytes())
    expected = decision_payload_sha256(benchmark.model_dump(mode="json"))
    actual = {method.decision.benchmark_sha256 for method in benchmark.methods}
    if actual != {expected}:
        raise ValueError("benchmark decisions do not bind the benchmark payload")
    return benchmark


def render_benchmark_markdown(
    benchmark: ClaimVerifierBenchmark | None = None,
    *,
    sha256: str | None = None,
) -> str:
    benchmark = benchmark or load_benchmark()
    sha256 = sha256 or benchmark_sha256()
    lines = [
        "# P0-10 Method Benchmark",
        "",
        f"- Benchmark ID: `{benchmark.benchmark_id}`",
        f"- Version: `{benchmark.benchmark_version}`",
        f"- JSON SHA-256: `{sha256}`",
        "- Decision payload SHA-256: "
        f"`{decision_payload_sha256(benchmark.model_dump(mode='json'))}`",
        f"- State: `{benchmark.benchmark_state}`",
        "- Selected default: `none`",
        "- Aggregate score/rank: `null` / `null`",
        "",
        "Methods are compared only within the same analysis task. Resource values",
        "are observations, not a cross-task score. A candidate recommendation is not",
        "a default selection unless the developer decision explicitly says so.",
        "",
        "## Data cases",
        "",
        "| Case | Class | Public accession or reference | Claims | Replicates | Scope |",
        "|---|---|---|---:|---:|---|",
    ]
    for case in benchmark.data_cases:
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(case.case_id),
                    _cell(case.data_class),
                    _cell(case.public_accession_or_ref or "not public"),
                    str(case.claim_count),
                    _cell(case.independent_replicate_count),
                    _cell(case.scope),
                ]
            )
            + " |"
        )
    lines.append("")

    tasks = sorted({method.analysis_task for method in benchmark.methods})
    for task in tasks:
        lines.extend(
            [
                f"## {task}",
                "",
                "| Method | Version / source / license | Role, data and metrics | Controls and missing inputs | Failure / abstention | Sensitivity | Runtime and resources | BRIDGE recommendation | Human decision |",
                "|---|---|---|---|---|---|---|---|---|",
            ]
        )
        for method in [item for item in benchmark.methods if item.analysis_task == task]:
            resources = method.resources
            runtime = (
                "not measured"
                if resources.wall_clock_seconds_median is None
                else (
                    f"wall {resources.wall_clock_seconds_median:.6g}s "
                    f"({resources.wall_clock_seconds_range[0]:.6g}–"
                    f"{resources.wall_clock_seconds_range[1]:.6g}); "
                    f"CPU {resources.cpu_seconds_median:.6g}s; "
                    f"RAM {resources.peak_ram_mb:.6g} MB; "
                    f"output {resources.output_bytes} B; n={resources.repetitions}"
                )
            )
            metrics = ", ".join(
                f"{key}={value}" for key, value in sorted(method.task_metrics.items())
            ) or "not measured"
            lines.append(
                "| "
                + " | ".join(
                    [
                        _cell(f"{method.method_name} (`{method.method_id}`)"),
                        _cell(f"{method.version}; {method.source}; {method.license}"),
                        _cell(
                            f"{method.role}; data={','.join(method.data_case_ids) or 'none'}; "
                            f"{method.evaluation}; {metrics}; interval={method.uncertainty_or_interval or 'none'}"
                        ),
                        _cell(
                            f"positive={','.join(method.positive_controls) or 'none'}; "
                            f"negative={','.join(method.negative_controls) or 'none'}; "
                            f"missing={method.missing_input_behavior}"
                        ),
                        _cell(
                            f"{method.failure_behavior}; {method.ood_or_abstention_behavior}"
                        ),
                        _cell(
                            f"seeds={method.random_seeds or 'not applicable'}; "
                            f"downsampling={method.downsampling}; reference={method.reference_sensitivity}; "
                            f"preprocessing={method.preprocessing_sensitivity}; denominator={method.denominator_sensitivity}"
                        ),
                        _cell(runtime),
                        _cell(method.recommendation.value),
                        _cell(
                            f"{method.decision.state.value}: {method.decision.reason}; "
                            f"reviewer={method.decision.reviewer or 'none'}; "
                            f"table hash={method.decision.benchmark_sha256}"
                        ),
                    ]
                )
                + " |"
            )
        lines.append("")

    lines.extend(
        [
            "## Stability and applicability",
            "",
            "P0-10 consumes structured report objects rather than expression matrices.",
            "Cell, gene and sequencing-depth downsampling are therefore recorded as",
            "not applicable instead of being imitated with claim deletion. Deterministic",
            "reruns, positive/negative controls, missing-input behavior, bilingual rules,",
            "policy/reference swaps and denominator changes remain package-specific gates.",
            "",
            "The benchmark does not establish clinical validity, safety, potency, GMP",
            "release, a best product or an overall method ranking.",
            "",
        ]
    )
    return "\n".join(lines)


def _cell(value: object) -> str:
    if value is None:
        return "not applicable"
    return str(value).replace("|", "\\|").replace("\n", " ")


def benchmark_json() -> dict:
    return json.loads(benchmark_bytes())
