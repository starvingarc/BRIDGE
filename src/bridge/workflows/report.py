from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from bridge.common.stats import normalize_weights
from bridge.workflows.config import BridgeConfigBatch, BridgeRunConfig, WorkflowValidationError, load_config


def _component_json_path(config: BridgeRunConfig, component: str) -> Path:
    return config.paths.cls_output_dir / config.dataset.id / component / f"component_{component}_global.json"


def _identity_paths(config: BridgeRunConfig) -> dict[str, Path]:
    outdir = config.paths.identity_output_dir
    prefix = config.dataset.prefix
    return {
        "thresholds_json": outdir / f"{prefix}.thresholds.json",
        "bdata_step2_h5ad": outdir / f"{prefix}.bdata_step2.h5ad",
        "adata_ref_step2_h5ad": outdir / f"{prefix}.adata_ref_step2.h5ad",
        "probs_ref_cal_csv": outdir / f"{prefix}.probs_ref_cal.csv",
        "probs_query_cal_csv": outdir / f"{prefix}.probs_query_cal.csv",
        "mean_org_csv": outdir / f"{prefix}.mean_org.csv",
        "std_org_csv": outdir / f"{prefix}.std_org.csv",
        "hnorm_csv": outdir / f"{prefix}.Hnorm.csv",
    }


def _report_output_paths(config: BridgeRunConfig) -> dict[str, Path]:
    base = config.paths.report_output_dir / config.dataset.id
    return {
        "base_dir": base,
        "summary_csv": base / config.report.summary_filename,
        "manifest_json": base / config.report.manifest_filename,
    }


def _read_h5ad_obs_summary(bdata_path: Path, candidate_col: str, p_mean_col: str, p_std_col: str, p_cal_col: str) -> dict[str, Any]:
    try:
        from anndata import read_h5ad
    except ImportError:
        return {}

    try:
        adata = read_h5ad(bdata_path, backed="r")
    except Exception:
        return {}

    try:
        obs = adata.obs
        summary: dict[str, Any] = {
            "has_p_cal": p_cal_col in obs.columns,
            "has_p_mean": p_mean_col in obs.columns,
            "has_p_std": p_std_col in obs.columns,
            "has_hnorm": "Hnorm" in obs.columns,
        }
        if candidate_col in obs.columns:
            candidate_series = obs[candidate_col].astype(bool)
            candidate_count = int(candidate_series.sum())
            summary["candidate_count"] = candidate_count
            summary["candidate_fraction"] = float(candidate_count / max(1, adata.n_obs))
        return summary
    finally:
        file_manager = getattr(adata, "file", None)
        if file_manager is not None:
            try:
                file_manager.close()
            except Exception:
                pass


def _extract_step2_summary(config: BridgeRunConfig) -> dict:
    identity_paths = _identity_paths(config)
    thresholds_path = identity_paths["thresholds_json"]
    if not thresholds_path.exists():
        raise WorkflowValidationError(f"Missing Step 2 thresholds JSON: {thresholds_path}")

    thresholds = json.loads(thresholds_path.read_text(encoding="utf-8"))
    summary = {
        "dataset_id": config.dataset.id,
        "target_class": config.identity.target_class,
        "n_query": thresholds.get("n_query"),
        "n_ref": thresholds.get("n_ref"),
        "threshold_t": thresholds.get("t"),
        "threshold_u": thresholds.get("u"),
        "threshold_u_raw": thresholds.get("u_raw"),
        "threshold_v": thresholds.get("v"),
    }

    candidate_col = f"{config.cls.candidate_flag_prefix}{config.identity.target_class}"
    p_mean_col = f"p_mean_{config.identity.target_class}"
    p_std_col = f"p_std_{config.identity.target_class}"
    p_cal_col = f"p_cal_{config.identity.target_class}"
    summary.update(
        {
            "candidate_count": None,
            "candidate_fraction": None,
            "has_p_cal": identity_paths["probs_query_cal_csv"].exists(),
            "has_p_mean": identity_paths["mean_org_csv"].exists(),
            "has_p_std": identity_paths["std_org_csv"].exists(),
            "has_hnorm": identity_paths["hnorm_csv"].exists(),
            "p_mean_mean": None,
            "p_mean_median": None,
            "p_std_mean": None,
            "p_std_median": None,
            "hnorm_mean": None,
            "hnorm_median": None,
        }
    )

    mean_org_path = identity_paths["mean_org_csv"]
    std_org_path = identity_paths["std_org_csv"]
    hnorm_path = identity_paths["hnorm_csv"]

    if mean_org_path.exists():
        mean_df = pd.read_csv(mean_org_path, index_col=0)
        if config.identity.target_class in mean_df.columns:
            series = mean_df[config.identity.target_class].astype(float)
            summary["p_mean_mean"] = float(series.mean())
            summary["p_mean_median"] = float(series.median())

    if std_org_path.exists():
        std_df = pd.read_csv(std_org_path, index_col=0)
        if config.identity.target_class in std_df.columns:
            series = std_df[config.identity.target_class].astype(float)
            summary["p_std_mean"] = float(series.mean())
            summary["p_std_median"] = float(series.median())

    if hnorm_path.exists():
        hnorm_df = pd.read_csv(hnorm_path, index_col=0)
        if hnorm_df.shape[1] >= 1:
            series = hnorm_df.iloc[:, 0].astype(float)
            summary["hnorm_mean"] = float(series.mean())
            summary["hnorm_median"] = float(series.median())

    bdata_path = identity_paths["bdata_step2_h5ad"]
    if bdata_path.exists():
        h5ad_summary = _read_h5ad_obs_summary(
            bdata_path=bdata_path,
            candidate_col=candidate_col,
            p_mean_col=p_mean_col,
            p_std_col=p_std_col,
            p_cal_col=p_cal_col,
        )
        for key, value in h5ad_summary.items():
            if key.startswith("has_"):
                summary[key] = bool(summary.get(key, False) or value)
            elif summary.get(key) is None:
                summary[key] = value

    return summary


def _extract_step3_summary(config: BridgeRunConfig) -> tuple[pd.DataFrame, float | None]:
    rows = []
    for component in config.cls.enabled_components:
        path = _component_json_path(config, component)
        payload = json.loads(path.read_text(encoding="utf-8"))
        component_dir = path.parent
        rows.append(
            {
                "component": component,
                "global_score": float(payload["global_score"]),
                "result_json": str(path),
                "has_batch_csv": (component_dir / f"component_{component}_batch.csv").exists(),
                "has_branch_csv": (component_dir / f"component_{component}_branch.csv").exists(),
                "has_genes_csv": (component_dir / f"component_{component}_genes.csv").exists(),
                "has_query_aucell_csv": (component_dir / "query_aucell.csv").exists(),
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
    return summary_df, weighted_total


def _build_report_summary_row(config: BridgeRunConfig) -> tuple[pd.DataFrame, pd.DataFrame, float | None]:
    step2_summary = _extract_step2_summary(config)
    step3_summary_df, weighted_total = _extract_step3_summary(config)
    summary_row = dict(step2_summary)
    for _, row in step3_summary_df.iterrows():
        component = row["component"]
        summary_row[f"cls_{component}"] = float(row["global_score"])
        summary_row[f"has_{component}_detail_table"] = bool(
            row["has_batch_csv"] or row["has_branch_csv"] or row["has_genes_csv"] or row["has_query_aucell_csv"]
        )
    summary_row["weighted_total_cls"] = weighted_total
    return pd.DataFrame([summary_row]), step3_summary_df, weighted_total


def build_report_run_plan(config: BridgeRunConfig) -> dict:
    enabled = config.cls.enabled_components
    missing = [comp for comp in enabled if not _component_json_path(config, comp).exists()]
    if missing:
        raise WorkflowValidationError(f"Missing CLS component outputs required for report summary: {', '.join(missing)}")
    identity_paths = _identity_paths(config)
    if not identity_paths["thresholds_json"].exists():
        raise WorkflowValidationError(f"Missing Step 2 thresholds JSON required for report summary: {identity_paths['thresholds_json']}")
    outputs = _report_output_paths(config)
    return {
        "workflow": "report",
        "dataset_id": config.dataset.id,
        "enabled_components": enabled,
        "inputs": {
            "step2": {name: str(path) for name, path in identity_paths.items()},
            "step3": {comp: str(_component_json_path(config, comp)) for comp in enabled},
        },
        "outputs": {
            "summary_csv": str(outputs["summary_csv"]),
            "manifest_json": str(outputs["manifest_json"]),
        },
        "checks": [
            "step2 thresholds JSON found",
            "component global JSON files found",
            "report output paths resolved",
        ],
    }


def run_report_summary(config: BridgeRunConfig, dry_run: bool = False) -> dict:
    plan = build_report_run_plan(config)
    if dry_run:
        return plan

    summary_df, step3_summary_df, weighted_total = _build_report_summary_row(config)

    outputs = _report_output_paths(config)
    outputs["base_dir"].mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(outputs["summary_csv"], index=False)
    manifest = {
        "dataset_id": config.dataset.id,
        "target_class": config.identity.target_class,
        "enabled_components": config.cls.enabled_components,
        "summary_csv": str(outputs["summary_csv"]),
        "weighted_total_cls": weighted_total,
        "step2_artifacts": {name: str(path) for name, path in _identity_paths(config).items()},
        "component_payloads": {comp: str(_component_json_path(config, comp)) for comp in config.cls.enabled_components},
        "component_details": step3_summary_df.to_dict(orient="records"),
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


def _batch_output_paths(config_batch: BridgeConfigBatch) -> dict[str, Path]:
    first_config = load_config(config_batch.config_paths[0])
    base = first_config.paths.report_output_dir / "combined"
    return {
        "base_dir": base,
        "combined_summary_csv": base / "combined_summary.csv",
        "combined_manifest_json": base / "combined_manifest.json",
    }


def build_report_batch_plan(config_batch: BridgeConfigBatch) -> dict:
    plans = []
    for config_path in config_batch.config_paths:
        config = load_config(config_path)
        plans.append(build_report_run_plan(config))
    outputs = _batch_output_paths(config_batch)
    return {
        "workflow": "report-batch",
        "config_list": str(config_batch.config_list_path),
        "datasets": [plan["dataset_id"] for plan in plans],
        "per_dataset_plans": plans,
        "outputs": {
            "combined_summary_csv": str(outputs["combined_summary_csv"]),
            "combined_manifest_json": str(outputs["combined_manifest_json"]),
        },
    }


def run_report_summary_batch(config_batch: BridgeConfigBatch, dry_run: bool = False) -> dict:
    plan = build_report_batch_plan(config_batch)
    if dry_run:
        return plan

    per_dataset_results = []
    combined_rows = []
    for config_path in config_batch.config_paths:
        config = load_config(config_path)
        summary_df, step3_summary_df, weighted_total = _build_report_summary_row(config)
        outputs = _report_output_paths(config)
        outputs["base_dir"].mkdir(parents=True, exist_ok=True)
        summary_df.to_csv(outputs["summary_csv"], index=False)
        manifest = {
            "dataset_id": config.dataset.id,
            "target_class": config.identity.target_class,
            "enabled_components": config.cls.enabled_components,
            "summary_csv": str(outputs["summary_csv"]),
            "weighted_total_cls": weighted_total,
            "step2_artifacts": {name: str(path) for name, path in _identity_paths(config).items()},
            "component_payloads": {comp: str(_component_json_path(config, comp)) for comp in config.cls.enabled_components},
            "component_details": step3_summary_df.to_dict(orient="records"),
        }
        outputs["manifest_json"].write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        result = {
            "workflow": "report",
            "status": "completed",
            "dataset_id": config.dataset.id,
            "summary_csv": str(outputs["summary_csv"]),
            "manifest_json": str(outputs["manifest_json"]),
            "weighted_total_cls": weighted_total,
        }
        per_dataset_results.append(result)
        combined_rows.append(summary_df)

    combined_df = pd.concat(combined_rows, ignore_index=True)
    outputs = _batch_output_paths(config_batch)
    outputs["base_dir"].mkdir(parents=True, exist_ok=True)
    combined_df.to_csv(outputs["combined_summary_csv"], index=False)
    manifest = {
        "config_list": str(config_batch.config_list_path),
        "datasets": [result["dataset_id"] for result in per_dataset_results],
        "per_dataset_results": per_dataset_results,
        "combined_summary_csv": str(outputs["combined_summary_csv"]),
    }
    outputs["combined_manifest_json"].write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {
        "workflow": "report-batch",
        "datasets": [result["dataset_id"] for result in per_dataset_results],
        "combined_summary_csv": str(outputs["combined_summary_csv"]),
        "combined_manifest_json": str(outputs["combined_manifest_json"]),
    }
