from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Any
from uuid import uuid4

import numpy as np
import pandas as pd
from bridge.tool_packages.p0_01_input_qc.io import (
    InputAuditError,
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
from bridge.tool_packages._structured_runtime import (
    directory_content_hashes,
    directory_state,
    snapshot_path,
)
from bridge.tool_packages._configurable_contracts import (
    BiologicalUnitBinding,
    BiologicalUnitKind,
    BiologicalUnitManifest,
    VersionedObjectRef,
)
from bridge.toolkit.contracts import (
    ArtifactManifest,
    DataViewBinding,
    EvidenceState,
    ExecutionState,
    MeasurementResult,
    MeasurementSpec,
    QCReadinessProfile,
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
    output_root = request.output_dir.resolve()
    if directory_state(output_root) == "other":
        return _failed_run(request, spec, None, "output_path_invalid")
    try:
        output_root.mkdir(parents=True, exist_ok=True)
    except OSError:
        return _failed_run(request, spec, None, "output_path_invalid")
    if directory_state(output_root) != "directory":
        return _failed_run(request, spec, None, "output_path_invalid")

    workspace = output_root / f".p0-01-work-{uuid4().hex}"
    try:
        workspace.mkdir(mode=0o700)
        asset_snapshot = workspace / "input" / asset.path.name
        snapshot_path(asset.path, asset_snapshot)
        snapshot_hash = sha256_path(asset_snapshot)
        if asset.checksum is not None and asset.checksum != snapshot_hash:
            return _failed_run(
                request,
                spec,
                snapshot_hash,
                "input_checksum_mismatch",
            )
        snapshot_asset = asset.model_copy(update={"path": asset_snapshot})
        snapshot_request = request.model_copy(
            update={
                "assets": [snapshot_asset],
                "output_dir": workspace / "output",
            }
        )
        run = _run_snapshotted_input_audit_qc(snapshot_request, spec)
        run = run.model_copy(update={"request": request})
        if run.execution_state is not ExecutionState.SUCCEEDED:
            return run
        return _publish_snapshotted_run(
            run=run,
            request=request,
            spec=spec,
            staging_root=snapshot_request.output_dir / run.run_id,
            output_root=output_root,
        )
    except InputAuditError as exc:
        return _failed_run(request, spec, None, exc.reason_code, str(exc))
    except (OSError, RuntimeError) as exc:
        return _failed_run(
            request,
            spec,
            None,
            "input_snapshot_failed",
            str(exc),
        )
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def _run_snapshotted_input_audit_qc(
    request: ToolRequest,
    spec: ToolPackageSpec,
) -> ToolRun:
    asset = request.assets[0]
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
        metadata_hierarchy = _validate_metadata_hierarchy(
            adata.obs,
            asset.metadata,
            require_sample_and_capture=asset.input_level.value
            in {"count_ready", "analysis_ready"},
        )
        sample_or_preparation_ref = _optional_metadata_ref(
            asset.metadata, "sample_or_preparation_ref"
        )
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
    selected_data_view: DataViewBinding | None = None
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
        measurements.extend(
            _count_measurements(run_id, metrics, measurement_spec)
        )
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
            eligible = flags["bridge_qc_candidate_eligible"].to_numpy(dtype=bool)
            selected = adata[eligible].copy()
            derived_path = run_dir / "candidate_qc_view.h5ad"
            selected.write_h5ad(derived_path)
            evidence_ids.append(f"evidence:{run_id}:candidate-flags")
            candidate_artifact = _artifact(
                f"artifact:{run_id}:candidate-view",
                "derived_h5ad",
                derived_path,
                [f"evidence:{run_id}:candidate-flags"],
            )
            artifacts.append(candidate_artifact)
            try:
                (
                    assignment_artifact,
                    manifest_artifact,
                    biological_unit_manifest,
                ) = _write_biological_unit_manifest(
                    selected=selected,
                    metadata=asset.metadata,
                    run_dir=run_dir,
                    run_id=run_id,
                    tool_version=spec.version,
                    view_id=f"data-view:{run_id}:qc-selected",
                    selected_artifact_sha256=candidate_artifact.sha256,
                )
            except InputAuditError as exc:
                return _failed_run(
                    request,
                    spec,
                    input_hash,
                    exc.reason_code,
                    str(exc),
                )
            artifacts.extend([assignment_artifact, manifest_artifact])
            selected_data_view = DataViewBinding(
                view_id=f"data-view:{run_id}:qc-selected",
                view_kind="qc_selected_observations",
                artifact_id=candidate_artifact.artifact_id,
                sha256=candidate_artifact.sha256,
                parent_asset_id=asset.asset_id,
                parent_asset_sha256=input_hash,
                matrix_location="X",
                matrix_semantics=asset.matrix_semantics,
                n_observations=int(selected.n_obs),
                observation_ids_sha256=_observation_ids_sha256(selected.obs_names),
                sample_or_preparation_ref=sample_or_preparation_ref,
                selection_spec_ref=(
                    f"{measurement_spec.measurement_spec_id}@{measurement_spec.version}"
                ),
                biological_unit_manifest_ref=biological_unit_manifest.ref.ref,
                biological_unit_manifest_sha256=manifest_artifact.sha256,
            )
            data_views["eligible_cells_view"] = {
                "state": "candidate",
                "n_observations": int(selected.n_obs),
                "observation_unit": observation_unit,
                "artifact_id": candidate_artifact.artifact_id,
                "sha256": candidate_artifact.sha256,
                "view_id": selected_data_view.view_id,
                "observation_ids_sha256": selected_data_view.observation_ids_sha256,
                "matrix_location": selected_data_view.matrix_location,
                "matrix_semantics": selected_data_view.matrix_semantics,
                "biological_unit_manifest_ref": (
                    selected_data_view.biological_unit_manifest_ref
                ),
                "biological_unit_manifest_sha256": (
                    selected_data_view.biological_unit_manifest_sha256
                ),
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
        measurement_spec_version=measurement_spec.version if measurement_spec else None,
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
        metadata_completeness=metadata_hierarchy,
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
        selected_data_view=selected_data_view,
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


def _count_measurements(
    run_id: str,
    metrics: pd.DataFrame,
    spec: MeasurementSpec | None,
) -> list[MeasurementResult]:
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
        names = pd.Index(adata.var_names.astype(str))
        source = "var_names"
    else:
        if column not in adata.var.columns:
            raise InputAuditError("gene_symbol_column_not_found", str(column))
        values = adata.var[column]
        if values.isna().any() or (values.astype(str).str.strip() == "").any():
            raise InputAuditError("gene_symbol_column_incomplete", str(column))
        names = pd.Index(values.astype(str))
        source = f"var/{column}"
    normalized = names.str.strip().str.upper()
    if normalized.has_duplicates:
        raise InputAuditError(
            "gene_symbol_normalization_collision",
            source,
        )
    return names, source


def _validate_metadata_hierarchy(
    obs: pd.DataFrame,
    metadata: dict[str, Any],
    *,
    require_sample_and_capture: bool,
) -> dict[str, Any]:
    fields = ("sample_id", "capture_id", "batch_id", "preparation_id", "timepoint")
    resolved: dict[str, pd.Series] = {}
    checks: dict[str, bool] = {}
    for logical_name in fields:
        values, _ = _declared_group(obs, metadata, logical_name)
        checks[logical_name] = values is not None
        if values is None:
            continue
        if values.isna().any() or (values.astype(str).str.strip() == "").any():
            raise InputAuditError("metadata_field_incomplete", logical_name)
        resolved[logical_name] = values.astype(str)

    if require_sample_and_capture:
        missing = [name for name in ("sample_id", "capture_id") if name not in resolved]
        if missing:
            raise InputAuditError("required_metadata_not_declared", ",".join(missing))

    capture = resolved.get("capture_id")
    if capture is not None:
        for parent_name in ("sample_id", "preparation_id", "batch_id", "timepoint"):
            parent = resolved.get(parent_name)
            if parent is None:
                continue
            mapping = pd.DataFrame({"capture": capture, "parent": parent})
            if (mapping.groupby("capture", dropna=False)["parent"].nunique() > 1).any():
                raise InputAuditError(
                    "metadata_hierarchy_conflict",
                    f"capture_id->{parent_name}",
                )

    sample = resolved.get("sample_id")
    preparation = resolved.get("preparation_id")
    if sample is not None and preparation is not None:
        mapping = pd.DataFrame({"preparation": preparation, "sample": sample})
        if (mapping.groupby("preparation", dropna=False)["sample"].nunique() > 1).any():
            raise InputAuditError(
                "metadata_hierarchy_conflict",
                "preparation_id->sample_id",
            )

    return {
        "fields": checks,
        "complete": all(checks[name] for name in ("sample_id", "capture_id")),
        "hierarchy_state": "validated",
    }


def _optional_metadata_ref(metadata: dict[str, Any], key: str) -> str | None:
    value = metadata.get(key)
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        raise InputAuditError("metadata_reference_invalid", key)
    return text


def _observation_ids_sha256(values: pd.Index) -> str:
    payload = json.dumps(
        [str(value) for value in values],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _write_biological_unit_manifest(
    *,
    selected,
    metadata: dict[str, Any],
    run_dir: Path,
    run_id: str,
    tool_version: str,
    view_id: str,
    selected_artifact_sha256: str,
) -> tuple[ArtifactManifest, ArtifactManifest, BiologicalUnitManifest]:
    analysis_kind = _declared_unit_kind(metadata, "analysis_unit_kind")
    independence_kind = _declared_unit_kind(
        metadata, "independence_group_kind"
    )
    if independence_kind in {
        BiologicalUnitKind.CAPTURE,
        BiologicalUnitKind.GRAFT_UNIT,
    }:
        raise InputAuditError(
            "independence_group_kind_invalid",
            independence_kind.value,
        )
    namespace = _metadata_versioned_ref(metadata, "unit_identity_namespace_ref")
    independence_scope = _metadata_versioned_ref(
        metadata, "independence_scope_ref"
    )
    raw_by_kind: dict[BiologicalUnitKind, pd.Series] = {}
    for kind in (
        BiologicalUnitKind.CAPTURE,
        BiologicalUnitKind.PREPARATION,
        BiologicalUnitKind.SAMPLE,
    ):
        values, _ = _declared_group(selected.obs, metadata, f"{kind.value}_id")
        if values is not None:
            raw_by_kind[kind] = values.astype(str)
    for kind in (analysis_kind, independence_kind):
        if kind not in {
            BiologicalUnitKind.CAPTURE,
            BiologicalUnitKind.PREPARATION,
            BiologicalUnitKind.SAMPLE,
        }:
            raise InputAuditError("p0_01_unit_kind_not_supported", kind.value)
        if kind not in raw_by_kind:
            raise InputAuditError(
                "biological_unit_metadata_not_declared",
                f"{kind.value}_id",
            )

    refs_by_kind = {
        kind: values.map(
            lambda value: _opaque_unit_ref(namespace, kind, str(value))
        )
        for kind, values in raw_by_kind.items()
    }
    def serialized_refs(kind: BiologicalUnitKind) -> pd.Series:
        values = refs_by_kind.get(kind)
        if values is None:
            return pd.Series([None] * len(selected), index=selected.obs.index)
        return values.map(lambda item: item.ref)

    assignment = pd.DataFrame(
        {
            "observation_id": selected.obs_names.astype(str),
            "capture_ref": serialized_refs(BiologicalUnitKind.CAPTURE),
            "preparation_ref": serialized_refs(BiologicalUnitKind.PREPARATION),
            "sample_ref": serialized_refs(BiologicalUnitKind.SAMPLE),
            "analysis_unit_ref": refs_by_kind[analysis_kind].map(
                lambda item: item.ref
            ),
            "independence_group_ref": refs_by_kind[independence_kind].map(
                lambda item: item.ref
            ),
        }
    )
    if assignment["observation_id"].duplicated().any():
        raise InputAuditError(
            "biological_unit_assignment_invalid",
            "duplicate observation assignment",
        )
    for child, parent in (
        ("capture_ref", "preparation_ref"),
        ("capture_ref", "sample_ref"),
        ("preparation_ref", "sample_ref"),
        ("analysis_unit_ref", "independence_group_ref"),
    ):
        pairs = assignment[[child, parent]].dropna()
        if pairs.groupby(child, dropna=False)[parent].nunique().gt(1).any():
            raise InputAuditError(
                "biological_unit_assignment_conflict",
                f"{child}->{parent}",
            )

    assignment_path = run_dir / "biological_unit_assignments.parquet"
    assignment.to_parquet(assignment_path, index=False)
    assignment_artifact = _artifact(
        f"artifact:{run_id}:biological-unit-assignments",
        "biological_unit_assignments",
        assignment_path,
        [f"evidence:{run_id}:candidate-flags"],
    )

    bindings: list[BiologicalUnitBinding] = []
    for analysis_ref, rows in assignment.groupby(
        "analysis_unit_ref", sort=True, dropna=False
    ):
        first = rows.iloc[0]
        bindings.append(
            BiologicalUnitBinding(
                analysis_unit_ref=_parse_versioned_ref(str(analysis_ref)),
                analysis_unit_kind=analysis_kind,
                independence_group_ref=_parse_versioned_ref(
                    str(first["independence_group_ref"])
                ),
                independence_group_kind=independence_kind,
                capture_ref=(
                    _parse_versioned_ref(str(first["capture_ref"]))
                    if analysis_kind is BiologicalUnitKind.CAPTURE
                    else None
                ),
                preparation_ref=_optional_versioned_ref(
                    first["preparation_ref"]
                    if analysis_kind
                    in {
                        BiologicalUnitKind.CAPTURE,
                        BiologicalUnitKind.PREPARATION,
                    }
                    else None
                ),
                sample_ref=_optional_versioned_ref(first["sample_ref"]),
            )
        )
    manifest = BiologicalUnitManifest(
        object_version="0.1.0",
        manifest_id=f"biological-unit-manifest:{run_id}",
        manifest_version="0.1.0",
        schema_ref="bridge://schemas/biological-unit-manifest/v0.1",
        generator_tool_id="P0-01",
        generator_tool_version=tool_version,
        data_view_ref=view_id,
        selected_artifact_sha256=selected_artifact_sha256,
        observation_ids_sha256=_observation_ids_sha256(selected.obs_names),
        n_observations=int(selected.n_obs),
        assignment_schema_ref=(
            "bridge://schemas/biological-unit-assignment/v0.1"
        ),
        assignment_artifact_sha256=assignment_artifact.sha256,
        assignment_row_count=len(assignment),
        unit_identity_namespace_ref=namespace,
        analysis_unit_kind=analysis_kind,
        independence_group_kind=independence_kind,
        independence_scope_ref=independence_scope,
        lineage_state="declared",
        review_gate_ref=None,
        review_gate_sha256=None,
        unit_bindings=bindings,
    )
    manifest_path = run_dir / "biological_unit_manifest.json"
    _write_json(manifest_path, manifest.model_dump(mode="json"))
    manifest_artifact = _artifact(
        f"artifact:{run_id}:biological-unit-manifest",
        "biological_unit_manifest",
        manifest_path,
        [f"evidence:{run_id}:candidate-flags"],
    )
    return assignment_artifact, manifest_artifact, manifest


def _declared_unit_kind(
    metadata: dict[str, Any], key: str
) -> BiologicalUnitKind:
    try:
        return BiologicalUnitKind(str(metadata[key]))
    except (KeyError, ValueError):
        raise InputAuditError("biological_unit_contract_required", key) from None


def _metadata_versioned_ref(
    metadata: dict[str, Any], key: str
) -> VersionedObjectRef:
    value = metadata.get(key)
    if not isinstance(value, str):
        raise InputAuditError("biological_unit_contract_required", key)
    try:
        return _parse_versioned_ref(value)
    except ValueError:
        raise InputAuditError("metadata_reference_invalid", key) from None


def _parse_versioned_ref(value: str) -> VersionedObjectRef:
    object_id, separator, object_version = value.rpartition("@")
    if not separator:
        raise ValueError("versioned reference required")
    return VersionedObjectRef(
        object_id=object_id,
        object_version=object_version,
    )


def _optional_versioned_ref(value: Any) -> VersionedObjectRef | None:
    if value is None or pd.isna(value):
        return None
    return _parse_versioned_ref(str(value))


def _opaque_unit_ref(
    namespace: VersionedObjectRef,
    kind: BiologicalUnitKind,
    raw_value: str,
) -> VersionedObjectRef:
    digest = hashlib.sha256(
        f"{namespace.ref}|{kind.value}|{raw_value}".encode("utf-8")
    ).hexdigest()[:24]
    return VersionedObjectRef(
        object_id=f"biological-unit:{kind.value}:{digest}",
        object_version="0.1.0",
    )


def _declared_group(obs: pd.DataFrame, metadata: dict[str, Any], logical_name: str) -> tuple[pd.Series | None, str | None]:
    column = metadata.get(f"{logical_name}_column")
    if column is not None:
        if column not in obs.columns:
            raise InputAuditError(
                "metadata_column_not_found", f"{logical_name}:{column}"
            )
        values = obs[column]
        declared = metadata.get(logical_name)
        if declared is not None and (
            values.astype(str).str.strip() != str(declared).strip()
        ).any():
            raise InputAuditError(
                "metadata_declaration_conflict", logical_name
            )
        return values, None
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
    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            default=str,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _publish_snapshotted_run(
    *,
    run: ToolRun,
    request: ToolRequest,
    spec: ToolPackageSpec,
    staging_root: Path,
    output_root: Path,
) -> ToolRun:
    final_root = output_root / run.run_id
    try:
        published_artifacts = [
            artifact.model_copy(
                update={
                    "path": final_root / artifact.path.relative_to(staging_root)
                }
            )
            for artifact in run.artifacts
            if artifact.kind != "manifest"
        ]
        manifest_path = staging_root / "artifact_manifest.json"
        _write_json(
            manifest_path,
            {
                "run_id": run.run_id,
                "tool_id": spec.tool_id,
                "tool_version": spec.version,
                "environment_spec_id": spec.environment_spec_id,
                "input_hash": run.input_hash,
                "measurement_spec_ref": request.measurement_spec_ref,
                "artifacts": [
                    item.model_dump(mode="json") for item in published_artifacts
                ],
                "visualizations": [
                    item.model_dump(mode="json") for item in run.visualizations
                ],
            },
        )
        manifest_artifact = _artifact(
            f"artifact:{run.run_id}:manifest",
            "manifest",
            manifest_path,
            [item for item in run.result.get("evidence_ids", [])]
            if run.result is not None
            else [],
        ).model_copy(update={"path": final_root / "artifact_manifest.json"})
        published_artifacts.append(manifest_artifact)

        final_state = directory_state(final_root)
        if final_state == "directory":
            if directory_content_hashes(final_root) != directory_content_hashes(
                staging_root
            ):
                return _failed_run(
                    request,
                    spec,
                    run.input_hash,
                    "existing_run_bundle_hash_mismatch",
                )
        elif final_state == "missing":
            os.replace(staging_root, final_root)
        else:
            return _failed_run(
                request,
                spec,
                run.input_hash,
                "existing_run_bundle_hash_mismatch",
            )
        if directory_content_hashes(final_root) != {
            artifact.path.relative_to(final_root).as_posix(): artifact.sha256
            for artifact in published_artifacts
        }:
            return _failed_run(
                request,
                spec,
                run.input_hash,
                "published_result_hash_mismatch",
            )
        return run.model_copy(
            update={
                "request": request,
                "artifacts": published_artifacts,
            }
        )
    except (OSError, RuntimeError, ValueError):
        return _failed_run(request, spec, run.input_hash, "output_path_invalid")


def _output_overlaps_input(input_path: Path, output_dir: Path) -> bool:
    resolved_input = input_path.resolve()
    resolved_output = output_dir.resolve()
    return resolved_input.is_dir() and resolved_output.is_relative_to(resolved_input)


def _observation_unit(assay: str | None, input_level: str) -> str:
    if input_level == "droplet_ready":
        return "barcodes"
    return "nuclei" if assay == "snRNA-seq" else "cells"
