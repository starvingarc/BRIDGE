from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from bridge.tool_packages.p0_01_input_qc.io import (
    InputAuditError,
    build_declared_lineage,
    canonical_json_bytes,
    read_expression_asset,
    sha256_path,
    validate_expression_object,
)
from bridge.tool_packages.p0_01_input_qc.measurement_specs import load_measurement_spec
from bridge.tool_packages.p0_01_input_qc.metrics import (
    DEFAULT_FEATURE_SET_POLICY,
    apply_candidate_rules,
    calculate_count_metrics,
    summarize_by_group,
)
from bridge.tool_packages.p0_01_input_qc.visualization import (
    render_counts_genes_scatter,
    render_qc_overview,
)
from bridge.toolkit.contracts import (
    ArtifactManifest,
    EvidenceState,
    ExecutionState,
    MeasurementResult,
    MeasurementSpec,
    QCReadinessProfile,
    QCReadinessProfileV2,
    ReadinessState,
    ScoreState,
    ToolPackageSpec,
    ToolRequest,
    ToolRun,
    VisualizationArtifact,
)


def run_input_audit_qc(request: ToolRequest, spec: ToolPackageSpec) -> ToolRun:
    asset = request.assets[0]
    if _output_overlaps_input(asset.path, request.output_dir):
        return _failed_run(request, spec, None, "output_dir_overlaps_input_asset")
    input_hash = sha256_path(asset.path)
    if asset.checksum is not None and asset.checksum != input_hash:
        return _failed_run(request, spec, input_hash, "input_checksum_mismatch")

    measurement_spec = load_measurement_spec(request.measurement_spec_ref)
    if request.measurement_spec_ref is not None and measurement_spec is None:
        return _failed_run(request, spec, input_hash, "measurement_spec_not_found")
    if measurement_spec is not None and measurement_spec.assay != asset.assay:
        return _failed_run(request, spec, input_hash, "measurement_spec_assay_mismatch")
    if measurement_spec is not None:
        supported_levels = measurement_spec.input_contract.get("supported_levels", [])
        if asset.input_level.value not in supported_levels:
            return _failed_run(request, spec, input_hash, "measurement_spec_input_level_mismatch")

    try:
        adata = read_expression_asset(asset)
        require_counts = asset.matrix_semantics == "raw_counts"
        validate_expression_object(adata, require_counts=require_counts)
    except InputAuditError as exc:
        return _failed_run(request, spec, input_hash, exc.reason_code, str(exc))
    except Exception as exc:
        return _failed_run(request, spec, input_hash, "expression_asset_read_failed", str(exc))

    input_level = asset.input_level.value
    observation_unit = _observation_unit(asset.assay, input_level)
    run_id = _run_id(request, spec, input_hash)
    run_dir = request.output_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    missing_inputs: list[str] = []
    evidence_ids = [f"evidence:{run_id}:structure"]
    artifacts: list[ArtifactManifest] = []
    visualizations: list[VisualizationArtifact] = []
    measurements = _structural_measurements(
        run_id,
        adata.n_obs,
        adata.n_vars,
        input_level,
        asset.assay,
        measurement_spec,
    )

    cell_qc: dict[str, Any] = {"count_metrics_state": "not_assessed"}
    doublet_assessment: dict[str, Any] = {"state": "not_assessed", "reason": "count_input_required"}
    data_views: dict[str, Any] = {
        "all_cells_view": {
            "state": "available",
            "n_observations": int(adata.n_obs),
            "observation_unit": observation_unit,
        },
        "eligible_cells_view": {"state": "unavailable"},
        "sensitivity_views": [],
    }

    if input_level == "count_ready":
        try:
            gene_names, gene_identifier_source = _declared_gene_names(adata, asset.metadata)
        except InputAuditError as exc:
            return _failed_run(request, spec, input_hash, exc.reason_code, str(exc))
        feature_set_policy = (
            measurement_spec.input_contract.get("feature_set_policy", DEFAULT_FEATURE_SET_POLICY)
            if measurement_spec is not None
            else DEFAULT_FEATURE_SET_POLICY
        )
        metrics, gene_set_coverage = calculate_count_metrics(adata.X, gene_names, feature_set_policy)
        metrics.index = adata.obs_names.astype(str)
        metrics.index.name = "observation_id"
        evidence_ids.append(f"evidence:{run_id}:count-metrics")
        measurements.extend(_count_measurements(run_id, metrics, measurement_spec))
        group_series, group_warning = _declared_group(adata.obs, asset.metadata, "capture_id")
        if group_warning:
            warnings.append(group_warning)
        if group_series is None:
            group_series, sample_warning = _declared_group(adata.obs, asset.metadata, "sample_id")
            if sample_warning and sample_warning not in warnings:
                warnings.append(sample_warning)
        cell_qc = {
            "count_metrics_state": "measured",
            "metrics": list(metrics.columns),
            "gene_identifier_source": gene_identifier_source,
            "feature_set_policy_id": feature_set_policy["policy_id"],
            "mitochondrial_interpretation": feature_set_policy["mitochondrial_interpretation"],
            "gene_set_coverage": gene_set_coverage,
            "per_group": summarize_by_group(metrics, group_series, observation_unit)
            if group_series is not None
            else [],
        }
        doublet_assessment, doublet_warnings = _assess_doublets(
            adata,
            metrics,
            asset.metadata,
            measurement_spec,
            request,
        )
        warnings.extend(doublet_warnings)

        metrics_path = run_dir / "qc_metrics.parquet"
        metrics.to_parquet(metrics_path)
        artifacts.append(_artifact(f"artifact:{run_id}:qc-metrics", "qc_metrics", metrics_path, evidence_ids))
        data_views["all_cells_view"]["artifact_id"] = f"artifact:{run_id}:qc-metrics"

        missing_required_gene_sets: list[str] = []
        if measurement_spec is not None and "max_mitochondrial_fraction" in measurement_spec.exclusion_rules:
            if gene_set_coverage["mitochondrial_genes"] == 0:
                missing_required_gene_sets.append("mitochondrial_genes")
        if missing_required_gene_sets:
            missing_inputs.extend(f"required_gene_set_unavailable:{item}" for item in missing_required_gene_sets)
            warnings.append("candidate_eligibility_not_computed_due_to_gene_coverage")
            data_views["eligible_cells_view"] = {
                "state": "unavailable",
                "reason": "required_qc_gene_set_unavailable",
            }
        elif measurement_spec is not None:
            flags = apply_candidate_rules(metrics, measurement_spec.exclusion_rules)
            for column in flags.columns:
                adata.obs[column] = flags[column].to_numpy()
            for column in metrics.columns:
                adata.obs[f"bridge_qc_{column}"] = metrics[column].to_numpy()
            derived_path = run_dir / "candidate_qc_view.h5ad"
            adata.write_h5ad(derived_path)
            evidence_ids.append(f"evidence:{run_id}:candidate-flags")
            artifacts.append(
                _artifact(
                    f"artifact:{run_id}:candidate-view",
                    "derived_h5ad",
                    derived_path,
                    [f"evidence:{run_id}:candidate-flags"],
                )
            )
            data_views["eligible_cells_view"] = {
                "state": "candidate",
                "n_observations": int(flags["bridge_qc_candidate_eligible"].sum()),
                "observation_unit": observation_unit,
                "artifact_id": f"artifact:{run_id}:candidate-view",
            }
            data_views["sensitivity_views"].append("candidate_measurement_spec_flags")
        else:
            missing_inputs.append("measurement_spec_not_selected")

        visualization_artifacts, visualization_records = _write_visualizations(
            metrics,
            run_dir,
            run_id,
            observation_unit,
        )
        artifacts.extend(visualization_artifacts)
        visualizations.extend(visualization_records)
    elif input_level == "analysis_ready":
        missing_inputs.extend(
            ["raw_counts_not_available", "measurement_spec_not_selected"]
            if measurement_spec is None
            else ["raw_counts_not_available"]
        )
    else:
        data_views["all_cells_view"] = {
            "state": "unavailable",
            "reason": "cell_calling_not_executed",
        }
        data_views["all_droplets_view"] = {
            "state": "available",
            "n_barcodes": int(adata.n_obs),
        }
        missing_inputs.extend(["cell_calling_not_executed", "ambient_correction_not_executed"])

    readiness = ReadinessState.LIMITED
    profile = QCReadinessProfile(
        profile_id=f"qc-profile:{run_id}",
        input_level=input_level,
        assay=asset.assay or "unknown",
        assay_spec_id=measurement_spec.measurement_spec_id if measurement_spec else None,
        measurement_spec_status=measurement_spec.status if measurement_spec else "not_selected",
        readiness_state=readiness,
        schema_integrity={
            "state": "valid",
            "n_observations": int(adata.n_obs),
            "observation_kind": observation_unit,
            "n_cells": int(adata.n_obs) if observation_unit == "cells" else None,
            "n_nuclei": int(adata.n_obs) if observation_unit == "nuclei" else None,
            "n_barcodes": int(adata.n_obs) if input_level == "droplet_ready" else None,
            "n_genes": int(adata.n_vars),
            "unique_cell_ids": bool(adata.obs_names.is_unique),
            "unique_gene_ids": bool(adata.var_names.is_unique),
        },
        metadata_completeness=_metadata_completeness(adata.obs, asset.metadata),
        matrix_provenance={
            "asset_id": asset.asset_id,
            "format": asset.format,
            "matrix_location": asset.matrix_location or "X",
            "matrix_semantics": asset.matrix_semantics,
            "input_hash": input_hash,
            "gene_identifier_source": (
                gene_identifier_source if input_level == "count_ready" else "not_assessed"
            ),
        },
        upstream_library_qc={"state": "not_assessed", "reason": "upstream_report_not_provided"},
        cell_qc=cell_qc,
        doublet_assessment=doublet_assessment,
        cell_calling_assessment={"state": "not_assessed", "reason": "droplet_module_not_executed"},
        ambient_assessment={"state": "not_assessed", "reason": "droplet_module_not_executed"},
        data_views=data_views,
        module_eligibility={
            "count_based_qc": "eligible" if input_level == "count_ready" else "ineligible",
            "cell_calling": "not_implemented" if input_level == "droplet_ready" else "ineligible",
            "ambient_rna": "not_implemented" if input_level == "droplet_ready" else "ineligible",
            "downstream_scientific_modules": "ineligible" if input_level == "droplet_ready" else "conditional",
        },
        missing_inputs=sorted(set(missing_inputs)),
        warnings=sorted(set(warnings)),
        evidence_ids=evidence_ids,
        score_state=ScoreState.UNAVAILABLE,
        domain_score=None,
    )

    profile_path = run_dir / "qc_readiness_profile.json"
    _write_json(profile_path, profile.model_dump(mode="json"))
    artifacts.append(_artifact(f"artifact:{run_id}:profile", "qc_profile", profile_path, evidence_ids))

    lineage = build_declared_lineage(
        asset=asset,
        observations=adata.obs,
        input_hash=input_hash,
        run_id=run_id,
        tool_version=spec.version,
        input_level=input_level,
    )
    v2_data_views = deepcopy(profile.data_views)
    v2_missing_inputs = list(profile.missing_inputs)
    v2_warnings = list(profile.warnings)
    v2_evidence_ids = list(profile.evidence_ids)
    if lineage.lineage_is_available:
        lineage_evidence_id = f"evidence:{run_id}:declared-biological-unit-lineage"
        v2_evidence_ids.append(lineage_evidence_id)
        v2_warnings.append("biological_unit_lineage_is_declared_not_reviewed")
        v2_data_views["biological_unit_lineage"] = {
            "state": "declared",
            "assignment_artifact_id": f"artifact:{run_id}:biological-unit-assignment",
            "manifest_ref": lineage.manifest.ref.ref,
        }
        assignment_path = run_dir / "biological_unit_assignment.json"
        _write_json(
            assignment_path,
            lineage.assignment_artifact.model_dump(mode="json"),
        )
        artifacts.append(
            _artifact(
                f"artifact:{run_id}:biological-unit-assignment",
                "biological_unit_assignment",
                assignment_path,
                [lineage_evidence_id],
            )
        )
        biological_manifest_path = run_dir / "biological_unit_manifest.json"
        _write_json(
            biological_manifest_path,
            lineage.manifest.model_dump(mode="json"),
        )
        artifacts.append(
            _artifact(
                f"artifact:{run_id}:biological-unit-manifest",
                "biological_unit_manifest",
                biological_manifest_path,
                [lineage_evidence_id],
            )
        )
    else:
        v2_missing_inputs.extend(lineage.reason_codes)
        v2_data_views["biological_unit_lineage"] = {
            "state": "unavailable",
            "reason_codes": list(lineage.reason_codes),
        }

    profile_v2 = QCReadinessProfileV2.model_validate(
        {
            **profile.model_dump(mode="json"),
            "measurement_spec_version": measurement_spec.version if measurement_spec else None,
            "selected_data_view": lineage.selected_data_view,
            "data_views": v2_data_views,
            "missing_inputs": sorted(set(v2_missing_inputs)),
            "warnings": sorted(set(v2_warnings)),
            "evidence_ids": sorted(set(v2_evidence_ids)),
        }
    )
    profile_v2_path = run_dir / "qc_readiness_profile_v2.json"
    _write_json(profile_v2_path, profile_v2.model_dump(mode="json"))
    artifacts.append(
        _artifact(
            f"artifact:{run_id}:profile-v2",
            "qc_profile_v2",
            profile_v2_path,
            v2_evidence_ids,
        )
    )

    manifest_path = run_dir / "artifact_manifest.json"
    _write_json(
        manifest_path,
        {
            "run_id": run_id,
            "tool_id": spec.tool_id,
            "tool_version": spec.version,
            "environment_spec_id": spec.environment_spec_id,
            "input_hash": input_hash,
            "measurement_spec_ref": request.measurement_spec_ref,
            "artifacts": [item.model_dump(mode="json") for item in artifacts],
            "visualizations": [item.model_dump(mode="json") for item in visualizations],
        },
    )
    artifacts.append(_artifact(f"artifact:{run_id}:manifest", "manifest", manifest_path, evidence_ids))

    if sha256_path(asset.path) != input_hash:
        return _failed_run(request, spec, input_hash, "input_asset_modified_during_run")

    return ToolRun(
        run_id=run_id,
        request=request,
        implementation_state=spec.implementation_state,
        execution_state=ExecutionState.SUCCEEDED,
        tool_version=spec.version,
        environment_spec_id=spec.environment_spec_id,
        input_hash=input_hash,
        measurements=measurements,
        artifacts=artifacts,
        visualizations=visualizations,
        result=profile.model_dump(mode="json"),
        warnings=sorted(set(warnings)),
    )


def _run_id(request: ToolRequest, spec: ToolPackageSpec, input_hash: str) -> str:
    asset = request.assets[0]
    payload = json.dumps(
        {
            "request_id": request.request_id,
            "tool_id": request.tool_id,
            "tool_version": spec.version,
            "input_hash": input_hash,
            "asset_contract": {
                "asset_id": asset.asset_id,
                "format": asset.format,
                "input_level": asset.input_level.value,
                "matrix_location": asset.matrix_location,
                "matrix_semantics": asset.matrix_semantics,
                "assay": asset.assay,
                "metadata": asset.metadata,
            },
            "measurement_spec_ref": request.measurement_spec_ref,
            "parameters": request.parameters,
            "random_seed": request.random_seed,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"run-{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]}"


def _failed_run(
    request: ToolRequest,
    spec: ToolPackageSpec,
    input_hash: str | None,
    reason_code: str,
    detail: str | None = None,
) -> ToolRun:
    return ToolRun(
        run_id=f"run-{hashlib.sha256((request.request_id + reason_code).encode()).hexdigest()[:16]}",
        request=request,
        implementation_state=spec.implementation_state,
        execution_state=ExecutionState.FAILED,
        tool_version=spec.version,
        environment_spec_id=spec.environment_spec_id,
        input_hash=input_hash,
        reason_codes=[reason_code],
        warnings=[detail] if detail else [],
    )


def _structural_measurements(
    run_id: str,
    n_observations: int,
    n_genes: int,
    input_level: str,
    assay: str | None,
    spec: MeasurementSpec | None,
) -> list[MeasurementResult]:
    spec_id = spec.measurement_spec_id if spec else "QC-structure-v0.1"
    if input_level == "droplet_ready":
        observation_metric = "n_barcodes"
    elif assay == "snRNA-seq":
        observation_metric = "n_nuclei"
    else:
        observation_metric = "n_cells"
    return [
        MeasurementResult(
            measurement_id=f"measurement:{run_id}:{observation_metric.replace('_', '-')}",
            measurement_spec_id=spec_id,
            metric_name=observation_metric,
            raw_value=int(n_observations),
            score_state=ScoreState.UNAVAILABLE,
            evidence_state=EvidenceState.MEASURED,
        ),
        MeasurementResult(
            measurement_id=f"measurement:{run_id}:n-genes",
            measurement_spec_id=spec_id,
            metric_name="n_genes",
            raw_value=int(n_genes),
            score_state=ScoreState.UNAVAILABLE,
            evidence_state=EvidenceState.MEASURED,
        ),
    ]


def _count_measurements(run_id: str, metrics: pd.DataFrame, spec: MeasurementSpec | None) -> list[MeasurementResult]:
    spec_id = spec.measurement_spec_id if spec else "QC-count-metrics-v0.1"
    results: list[MeasurementResult] = []
    for column in metrics.columns:
        values = metrics[column].dropna()
        available = not values.empty
        median = values.median() if available else None
        results.append(
            MeasurementResult(
                measurement_id=f"measurement:{run_id}:{column}-median",
                measurement_spec_id=spec_id,
                metric_name=f"{column}_median",
                raw_value=float(median) if median is not None else None,
                denominator=int(len(metrics)),
                score_state=ScoreState.UNAVAILABLE,
                evidence_state=EvidenceState.MEASURED if available else EvidenceState.UNAVAILABLE,
                provenance_refs=[f"evidence:{run_id}:count-metrics"],
            )
        )
    return results


def _declared_gene_names(adata, metadata: dict[str, Any]) -> tuple[pd.Index, str]:
    column = metadata.get("gene_symbol_column")
    if column is None:
        return adata.var_names.astype(str), "var_names"
    if column not in adata.var.columns:
        raise InputAuditError("gene_symbol_column_not_found", str(column))
    values = adata.var[column]
    if values.isna().any() or (values.astype(str).str.strip() == "").any():
        raise InputAuditError("gene_symbol_column_incomplete", str(column))
    return pd.Index(values.astype(str)), f"var/{column}"


def _metadata_completeness(obs: pd.DataFrame, metadata: dict[str, Any]) -> dict[str, Any]:
    checks: dict[str, bool] = {}
    for logical_name in ("sample_id", "capture_id"):
        column = metadata.get(f"{logical_name}_column")
        checks[logical_name] = bool(
            logical_name in metadata or (column is not None and column in obs.columns)
        )
    return {"fields": checks, "complete": all(checks.values())}


def _declared_group(obs: pd.DataFrame, metadata: dict[str, Any], logical_name: str) -> tuple[pd.Series | None, str | None]:
    column = metadata.get(f"{logical_name}_column")
    if column is not None and column in obs.columns:
        return obs[column], None
    value = metadata.get(logical_name)
    if value is not None:
        return pd.Series([str(value)] * len(obs), index=obs.index), None
    return None, f"{logical_name}_not_declared"


def _assess_doublets(
    adata,
    metrics: pd.DataFrame,
    metadata: dict[str, Any],
    measurement_spec: MeasurementSpec | None,
    request: ToolRequest,
) -> tuple[dict[str, Any], list[str]]:
    groups, warning = _declared_group(adata.obs, metadata, "capture_id")
    if groups is None:
        return {"state": "not_assessed", "reason": "capture_id_not_declared"}, [warning or "capture_id_not_declared"]
    minimum = int(measurement_spec.minimum_data.get("min_cells_for_scrublet", 100)) if measurement_spec else 100
    if len(adata) < minimum:
        return {"state": "not_assessed", "reason": "insufficient_cells_for_scrublet", "minimum_cells": minimum}, []
    group_counts = groups.astype(str).value_counts()
    if (group_counts < minimum).any():
        return {
            "state": "not_assessed",
            "reason": "insufficient_cells_per_capture_for_scrublet",
            "minimum_cells": minimum,
            "insufficient_capture_count": int((group_counts < minimum).sum()),
        }, []
    if not request.parameters.get("run_scrublet", False):
        return {"state": "not_assessed", "reason": "scrublet_not_requested"}, []
    try:
        import scrublet as scr

        scores = np.full(adata.n_obs, np.nan)
        calls = np.zeros(adata.n_obs, dtype=bool)
        for group in sorted(groups.astype(str).unique()):
            mask = groups.astype(str).to_numpy() == group
            matrix = adata.X[mask]
            n_components = max(2, min(30, matrix.shape[0] - 1, matrix.shape[1] - 1))
            scrublet = scr.Scrublet(matrix, random_state=request.random_seed)
            group_scores, group_calls = scrublet.scrub_doublets(n_prin_comps=n_components, verbose=False)
            scores[mask] = group_scores
            calls[mask] = group_calls
        metrics["scrublet_score"] = scores
        return {
            "state": "candidate",
            "method": "Scrublet",
            "n_predicted": int(calls.sum()),
            "fraction_predicted": float(calls.mean()),
        }, []
    except Exception as exc:
        return {"state": "not_assessed", "reason": "scrublet_execution_failed"}, [f"scrublet_execution_failed: {exc}"]


def _write_visualizations(
    metrics: pd.DataFrame,
    run_dir: Path,
    run_id: str,
    observation_unit: str,
) -> tuple[list[ArtifactManifest], list[VisualizationArtifact]]:
    data_path = run_dir / "qc_visualization_data.parquet"
    metrics.to_parquet(data_path)
    overview_svg, overview_png = render_qc_overview(
        metrics,
        run_dir / "qc_overview",
        observation_unit=observation_unit,
    )
    scatter_svg, scatter_png = render_counts_genes_scatter(metrics, run_dir / "counts_genes_scatter")
    evidence = [f"evidence:{run_id}:count-metrics"]
    artifacts = [
        _artifact(f"artifact:{run_id}:visual-data", "visualization_data", data_path, evidence),
        _artifact(f"artifact:{run_id}:overview-svg", "visualization_svg", overview_svg, evidence),
        _artifact(f"artifact:{run_id}:overview-png", "visualization_png", overview_png, evidence),
        _artifact(f"artifact:{run_id}:scatter-svg", "visualization_svg", scatter_svg, evidence),
        _artifact(f"artifact:{run_id}:scatter-png", "visualization_png", scatter_png, evidence),
    ]
    visualizations = [
        VisualizationArtifact(
            visualization_id=f"visualization:{run_id}:overview",
            component_id="bridge.qc.overview.v0.1",
            data_artifact_id=f"artifact:{run_id}:visual-data",
            evidence_ids=evidence,
            denominator=f"declared {observation_unit}",
            units="metric-specific",
            status="candidate",
            render_artifact_ids=[f"artifact:{run_id}:overview-svg", f"artifact:{run_id}:overview-png"],
        ),
        VisualizationArtifact(
            visualization_id=f"visualization:{run_id}:counts-genes",
            component_id="bridge.qc.counts_genes.v0.1",
            data_artifact_id=f"artifact:{run_id}:visual-data",
            evidence_ids=evidence,
            denominator=f"declared {observation_unit}",
            units="counts and detected genes",
            status="candidate",
            render_artifact_ids=[f"artifact:{run_id}:scatter-svg", f"artifact:{run_id}:scatter-png"],
        ),
    ]
    return artifacts, visualizations


def _artifact(artifact_id: str, kind: str, path: Path, evidence_ids: list[str]) -> ArtifactManifest:
    media_types = {
        ".json": "application/json",
        ".parquet": "application/vnd.apache.parquet",
        ".h5ad": "application/x-hdf5",
        ".svg": "image/svg+xml",
        ".png": "image/png",
    }
    return ArtifactManifest(
        artifact_id=artifact_id,
        kind=kind,
        path=path.resolve(),
        media_type=media_types.get(path.suffix, "application/octet-stream"),
        sha256=sha256_path(path),
        evidence_ids=evidence_ids,
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_bytes(canonical_json_bytes(payload))


def _output_overlaps_input(input_path: Path, output_dir: Path) -> bool:
    resolved_input = input_path.resolve()
    resolved_output = output_dir.resolve()
    return resolved_input.is_dir() and resolved_output.is_relative_to(resolved_input)


def _observation_unit(assay: str | None, input_level: str) -> str:
    if input_level == "droplet_ready":
        return "barcodes"
    return "nuclei" if assay == "snRNA-seq" else "cells"
