from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from bridge.common.stats import normalize_weights
from bridge.workflows.config import BridgeRunConfig, WorkflowValidationError


def _component_json_path(config: BridgeRunConfig, component: str) -> Path:
    return config.paths.cls_output_dir / config.dataset.id / component / f"component_{component}_global.json"


def _report_output_paths(config: BridgeRunConfig) -> dict[str, Path]:
    base = config.paths.report_output_dir / config.dataset.id
    return {
        "base_dir": base,
        "summary_csv": base / config.report.summary_filename,
        "manifest_json": base / config.report.manifest_filename,
    }


def build_report_run_plan(config: BridgeRunConfig) -> dict:
    enabled = config.cls.enabled_components
    missing = [comp for comp in enabled if not _component_json_path(config, comp).exists()]
    if missing:
        raise WorkflowValidationError(f"Missing CLS component outputs required for report summary: {', '.join(missing)}")
    outputs = _report_output_paths(config)
    return {
        "workflow": "report",
        "dataset_id": config.dataset.id,
        "enabled_components": enabled,
        "inputs": {comp: str(_component_json_path(config, comp)) for comp in enabled},
        "outputs": {
            "summary_csv": str(outputs["summary_csv"]),
            "manifest_json": str(outputs["manifest_json"]),
        },
        "checks": [
            "component global JSON files found",
            "report output paths resolved",
        ],
    }


def run_report_summary(config: BridgeRunConfig, dry_run: bool = False) -> dict:
    plan = build_report_run_plan(config)
    if dry_run:
        return plan

    rows = []
    payloads: dict[str, dict] = {}
    for component in config.cls.enabled_components:
        path = _component_json_path(config, component)
        payload = json.loads(path.read_text(encoding="utf-8"))
        payloads[component] = payload
        rows.append(
            {
                "component": component,
                "global_score": float(payload["global_score"]),
                "result_json": str(path),
            }
        )

    summary_df = pd.DataFrame(rows).sort_values("component").reset_index(drop=True)
    weighted_total = None
    if config.report.cls_weights is not None:
        missing_weights = [comp for comp in config.cls.enabled_components if comp not in config.report.cls_weights]
        if missing_weights:
            raise WorkflowValidationError(
                f"Report config is missing cls_weights for enabled components: {', '.join(missing_weights)}"
            )
        weights = normalize_weights([config.report.cls_weights[comp] for comp in summary_df["component"]])
        weighted_total = float((summary_df["global_score"].to_numpy(dtype=float) * weights).sum())
        summary_df = pd.concat(
            [
                summary_df,
                pd.DataFrame(
                    [
                        {
                            "component": "TOTAL_WEIGHTED",
                            "global_score": weighted_total,
                            "result_json": "",
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )

    outputs = _report_output_paths(config)
    outputs["base_dir"].mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(outputs["summary_csv"], index=False)
    manifest = {
        "dataset_id": config.dataset.id,
        "enabled_components": config.cls.enabled_components,
        "summary_csv": str(outputs["summary_csv"]),
        "weighted_total_cls": weighted_total,
        "component_payloads": {comp: str(_component_json_path(config, comp)) for comp in config.cls.enabled_components},
    }
    outputs["manifest_json"].write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {
        "workflow": "report",
        "status": "completed",
        "dataset_id": config.dataset.id,
        "summary_csv": str(outputs["summary_csv"]),
        "manifest_json": str(outputs["manifest_json"]),
        "weighted_total_cls": weighted_total,
    }
