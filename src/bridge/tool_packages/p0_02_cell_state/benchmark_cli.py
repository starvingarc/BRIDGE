from __future__ import annotations

import argparse
import json
from importlib.resources import as_file, files
from pathlib import Path
from typing import Sequence

import yaml

from bridge.toolkit.contracts import BenchmarkSplitManifest, CellStateBenchmarkSpec, FreezeGateSpec


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bridge-benchmark")
    domain = parser.add_subparsers(dest="domain", required=True)
    cell_state = domain.add_parser("cell-state")
    actions = cell_state.add_subparsers(dest="action", required=True)

    prepare = actions.add_parser("prepare")
    prepare.add_argument("--spec")
    prepare.add_argument("--asset-catalog", required=True)
    prepare.add_argument("--freeze-gate")
    prepare.add_argument("--output", required=True)

    prepare_birtele = actions.add_parser("prepare-birtele")
    prepare_birtele.add_argument("--source-dir", required=True)
    prepare_birtele.add_argument("--sample-map")
    prepare_birtele.add_argument("--output-dir", required=True)

    audit_sources = actions.add_parser("audit-external-sources")
    audit_sources.add_argument("--lineage-map")
    audit_sources.add_argument("--output", required=True)

    run = actions.add_parser("run")
    run.add_argument("--spec")
    run.add_argument("--asset-catalog", required=True)
    run.add_argument("--split-manifest", required=True)
    run.add_argument("--output-dir", required=True)

    summarize = actions.add_parser("summarize")
    summarize.add_argument("--run-dir", required=True)
    summarize.add_argument("--output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.action == "prepare-birtele":
        from bridge.tool_packages.p0_02_cell_state.birtele import prepare_birtele_asset

        if args.sample_map:
            result = prepare_birtele_asset(
                Path(args.source_dir), Path(args.sample_map), Path(args.output_dir)
            )
        else:
            resource = files("bridge.tool_packages.p0_02_cell_state.resources").joinpath(
                "birtele_gse192405_samples.yaml"
            )
            with as_file(resource) as sample_map:
                result = prepare_birtele_asset(
                    Path(args.source_dir), sample_map, Path(args.output_dir)
                )
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if args.action == "audit-external-sources":
        from bridge.tool_packages.p0_02_cell_state.external_source import (
            audit_external_source_lineage,
        )

        if args.lineage_map:
            result = audit_external_source_lineage(Path(args.lineage_map), Path(args.output))
        else:
            resource = files("bridge.tool_packages.p0_02_cell_state.resources").joinpath(
                "external_source_lineage.yaml"
            )
            with as_file(resource) as lineage_map:
                result = audit_external_source_lineage(lineage_map, Path(args.output))
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    from bridge.tool_packages.p0_02_cell_state.freeze import (
        prepare_benchmark_split,
        run_pilot_benchmark,
        summarize_benchmark,
    )

    if args.action == "prepare":
        spec = _load_spec(args.spec)
        gate = _load_gate(args.freeze_gate)
        result = prepare_benchmark_split(spec, Path(args.asset_catalog), freeze_gate=gate)
        _write_json(Path(args.output), result.model_dump(mode="json"))
        print(result.model_dump_json())
        return 0
    if args.action == "run":
        spec = _load_spec(args.spec)
        split = BenchmarkSplitManifest.model_validate_json(
            Path(args.split_manifest).read_text(encoding="utf-8")
        )
        result = run_pilot_benchmark(
            spec,
            Path(args.asset_catalog),
            split,
            Path(args.output_dir),
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    result = summarize_benchmark(Path(args.run_dir))
    if args.output:
        _write_json(Path(args.output), result)
    print(json.dumps(result, sort_keys=True))
    return 0


def _load_spec(path: str | None) -> CellStateBenchmarkSpec:
    if path is None:
        from bridge.tool_packages.p0_02_cell_state.freeze import load_pilot_benchmark_spec

        return load_pilot_benchmark_spec()
    return CellStateBenchmarkSpec.model_validate(_read_structured(Path(path)))


def _load_gate(path: str | None) -> FreezeGateSpec | None:
    return None if path is None else FreezeGateSpec.model_validate(_read_structured(Path(path)))


def _read_structured(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    return json.loads(text) if path.suffix == ".json" else yaml.safe_load(text)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
