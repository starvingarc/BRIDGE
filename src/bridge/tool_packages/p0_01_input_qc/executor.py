from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from bridge.tool_packages.p0_01_input_qc.io import (
    InputAuditError,
    LEGACY_TWO_COLUMN_FEATURE_WARNING,
    P001_STRUCTURED_OUTPUT_INDEX_SCHEMA_REF,
    P001_STRUCTURED_OUTPUT_INDEX_V2_SCHEMA_REF,
    P001StructuredOutputIndex,
    P001StructuredOutputIndexV2,
    P001StructuredOutputRecord,
    P001StructuredOutputRecordV2,
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
from bridge.tool_packages.p0_01_input_qc.visualization_runtime import (
    write_typed_qc_visualizations,
)
from bridge.toolkit.contracts import (
    ArtifactManifest,
    EvidenceState,
    ExecutionState,
    InputAsset,
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
    try:
        input_hash = sha256_path(asset.path)
    except InputAuditError as exc:
        return _failed_run(request, spec, None, exc.reason_code, str(exc))
    except Exception as exc:
        return _failed_run(request, spec, None, "input_asset_hash_failed", str(exc))
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

    run_id = _run_id(request, spec, input_hash)
    workspace: Path | None = None
    try:
        workspace = _private_workspace(request.output_dir)
        snapshot_path = _snapshot_asset(asset.path, workspace / "input")
        snapshot_hash = sha256_path(snapshot_path)
        original_after_snapshot_hash = sha256_path(asset.path)
        if snapshot_hash != input_hash or original_after_snapshot_hash != input_hash:
            return _failed_run(
                request,
                spec,
                input_hash,
                "input_asset_modified_during_snapshot",
            )

        snapshot_asset = asset.model_copy(update={"path": snapshot_path})
        try:
            adata = read_expression_asset(snapshot_asset)
            require_counts = asset.matrix_semantics == "raw_counts"
            validate_expression_object(adata, require_counts=require_counts)
        except InputAuditError as exc:
            return _failed_run(request, spec, input_hash, exc.reason_code, str(exc))
        except Exception as exc:
            return _failed_run(request, spec, input_hash, "expression_asset_read_failed", str(exc))

        staging_run_dir = workspace / "bundle"
        staging_run_dir.mkdir(mode=0o700)
        final_run_dir = request.output_dir / run_id
        staged_run = _build_staged_run(
            request=request,
            spec=spec,
            asset=asset,
            adata=adata,
            measurement_spec=measurement_spec,
            input_hash=input_hash,
            run_id=run_id,
            staging_run_dir=staging_run_dir,
            final_run_dir=final_run_dir,
        )
        if staged_run.execution_state is not ExecutionState.SUCCEEDED:
            return staged_run
        if sha256_path(asset.path) != input_hash:
            return _failed_run(
                request,
                spec,
                input_hash,
                "input_asset_modified_during_run",
            )
        publish_reason = _publish_bundle(staging_run_dir, final_run_dir)
        if publish_reason is not None:
            return _failed_run(request, spec, input_hash, publish_reason)
        return staged_run
    except InputAuditError as exc:
        return _failed_run(request, spec, input_hash, exc.reason_code, str(exc))
    except Exception as exc:
        return _failed_run(request, spec, input_hash, "artifact_staging_failed", str(exc))
    finally:
        if workspace is not None:
            shutil.rmtree(workspace, ignore_errors=True)


def _build_staged_run(
    *,
    request: ToolRequest,
    spec: ToolPackageSpec,
    asset: InputAsset,
    adata,
    measurement_spec: MeasurementSpec | None,
    input_hash: str,
    run_id: str,
    staging_run_dir: Path,
    final_run_dir: Path,
) -> ToolRun:
    input_level = asset.input_level.value
    observation_unit = _observation_unit(asset.assay, input_level)
    warnings: list[str] = []
    feature_selection: dict[str, Any] = {}
    if asset.format == "10x_mtx":
        raw_feature_selection = adata.uns.get("bridge_10x_feature_selection")
        if isinstance(raw_feature_selection, dict):
            feature_selection = {
                "input_feature_count": int(raw_feature_selection["input_feature_count"]),
                "selected_gene_expression_feature_count": int(
                    raw_feature_selection["selected_gene_expression_feature_count"]
                ),
                "feature_selection_policy": str(raw_feature_selection["feature_selection_policy"]),
            }
        if feature_selection.get("feature_selection_policy") == "all_features_assumed_gene_expression":
            warnings.append(LEGACY_TWO_COLUMN_FEATURE_WARNING)
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
    qc_capture_groups: pd.Series | None = None
    metrics: pd.DataFrame | None = None
    flags: pd.DataFrame | None = None

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
        qc_capture_groups, group_warning = _declared_group(
            adata.obs,
            asset.metadata,
            "capture_id",
        )
        group_series = qc_capture_groups
        if group_warning:
            warnings.append(group_warning)
        if group_series is None and group_warning == "capture_id_not_declared":
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

        metrics_path = staging_run_dir / "qc_metrics.parquet"
        metrics.to_parquet(metrics_path)
        artifacts.append(
            _artifact(
                f"artifact:{run_id}:qc-metrics",
                "qc_metrics",
                metrics_path,
                evidence_ids,
                logical_path=final_run_dir / metrics_path.name,
            )
        )
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
            derived_path = staging_run_dir / "candidate_qc_view.h5ad"
            adata.write_h5ad(derived_path, compression="gzip")
            evidence_ids.append(f"evidence:{run_id}:candidate-flags")
            artifacts.append(
                _artifact(
                    f"artifact:{run_id}:candidate-view",
                    "derived_h5ad",
                    derived_path,
                    [f"evidence:{run_id}:candidate-flags"],
                    logical_path=final_run_dir / derived_path.name,
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
            staging_run_dir,
            final_run_dir,
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
            **feature_selection,
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

    profile_path = staging_run_dir / "qc_readiness_profile.json"
    _write_json(profile_path, profile.model_dump(mode="json"))
    artifacts.append(
        _artifact(
            f"artifact:{run_id}:profile",
            "qc_profile",
            profile_path,
            evidence_ids,
            logical_path=final_run_dir / profile_path.name,
        )
    )

    lineage = build_declared_lineage(
        asset=asset,
        observations=adata.obs,
        qc_capture_groups=qc_capture_groups,
        input_hash=input_hash,
        run_id=run_id,
        tool_version=spec.version,
        input_level=input_level,
    )
    v2_data_views = deepcopy(profile.data_views)
    v2_missing_inputs = list(profile.missing_inputs)
    v2_warnings = list(profile.warnings)
    v2_evidence_ids = list(profile.evidence_ids)
    structured_outputs: list[P001StructuredOutputRecord] = []
    if lineage.lineage_is_available:
        lineage_evidence_id = f"evidence:{run_id}:declared-biological-unit-lineage"
        v2_evidence_ids.append(lineage_evidence_id)
        v2_warnings.append("biological_unit_lineage_is_declared_not_reviewed")
        v2_data_views["biological_unit_lineage"] = {
            "state": "declared",
            "assignment_artifact_id": f"artifact:{run_id}:biological-unit-assignment",
            "manifest_ref": lineage.manifest.ref.ref,
        }
        assignment_path = staging_run_dir / "biological_unit_assignment.json"
        _write_json(
            assignment_path,
            lineage.assignment_artifact.model_dump(mode="json"),
        )
        assignment_artifact = _artifact(
                f"artifact:{run_id}:biological-unit-assignment",
                "biological_unit_assignment",
                assignment_path,
                [lineage_evidence_id],
                logical_path=final_run_dir / assignment_path.name,
            )
        artifacts.append(assignment_artifact)
        structured_outputs.append(
            _structured_output_record(
                role="biological_unit_assignment",
                artifact=assignment_artifact,
                schema_ref="bridge://schemas/biological-unit-assignment/v0.1",
                object_version=lineage.assignment_artifact.object_version,
            )
        )
        biological_manifest_path = staging_run_dir / "biological_unit_manifest.json"
        _write_json(
            biological_manifest_path,
            lineage.manifest.model_dump(mode="json"),
        )
        biological_manifest_artifact = _artifact(
                f"artifact:{run_id}:biological-unit-manifest",
                "biological_unit_manifest",
                biological_manifest_path,
                [lineage_evidence_id],
                logical_path=final_run_dir / biological_manifest_path.name,
            )
        artifacts.append(biological_manifest_artifact)
        structured_outputs.append(
            _structured_output_record(
                role="biological_unit_manifest",
                artifact=biological_manifest_artifact,
                schema_ref="bridge://schemas/biological-unit-manifest/v0.1",
                object_version=lineage.manifest.object_version,
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
    profile_v2_path = staging_run_dir / "qc_readiness_profile_v2.json"
    _write_json(profile_v2_path, profile_v2.model_dump(mode="json"))
    profile_v2_artifact = _artifact(
            f"artifact:{run_id}:profile-v2",
            "qc_profile_v2",
            profile_v2_path,
            v2_evidence_ids,
            logical_path=final_run_dir / profile_v2_path.name,
        )
    artifacts.append(profile_v2_artifact)
    structured_outputs.insert(
        0,
        _structured_output_record(
            role="qc_readiness_profile_v2",
            artifact=profile_v2_artifact,
            schema_ref="bridge://schemas/qc-readiness-profile/v0.2",
            object_version="0.2.0",
        ),
    )

    metrics_artifact = next(
        (item for item in artifacts if item.kind == "qc_metrics"),
        None,
    )
    typed_visualizations = write_typed_qc_visualizations(
        metrics=metrics,
        flags=flags,
        capture_groups=qc_capture_groups,
        measurement_spec=measurement_spec,
        profile=profile_v2,
        metrics_artifact=metrics_artifact,
        staging_run_dir=staging_run_dir,
        final_run_dir=final_run_dir,
        run_id=run_id,
        tool_version=spec.version,
        observation_unit=observation_unit,
    )
    artifacts.extend(typed_visualizations.artifacts)

    structured_index = P001StructuredOutputIndex(
        object_version="0.1.0",
        schema_ref=P001_STRUCTURED_OUTPUT_INDEX_SCHEMA_REF,
        run_id=run_id,
        outputs=structured_outputs,
    )
    structured_index_path = staging_run_dir / "structured_output_index.json"
    _write_json(structured_index_path, structured_index.model_dump(mode="json"))
    artifacts.append(
        _artifact(
            f"artifact:{run_id}:structured-output-index",
            P001_STRUCTURED_OUTPUT_INDEX_SCHEMA_REF,
            structured_index_path,
            v2_evidence_ids,
            logical_path=final_run_dir / structured_index_path.name,
        )
    )

    structured_outputs_v2 = [
        P001StructuredOutputRecordV2.model_validate(item.model_dump(mode="json"))
        for item in structured_outputs
    ]
    structured_outputs_v2.extend(
        [
            _structured_output_record_v2(
                role="qc_visualization_data",
                artifact=typed_visualizations.data_artifact,
                schema_ref="bridge://schemas/qc-visualization-data/v0.1",
                object_version="0.1.0",
            ),
            _structured_output_record_v2(
                role="visualization_artifact_set",
                artifact=typed_visualizations.artifact_set_artifact,
                schema_ref="bridge://schemas/p0-01-visualization-artifact-set/v0.1",
                object_version="0.1.0",
            ),
        ]
    )
    structured_index_v2 = P001StructuredOutputIndexV2(
        run_id=run_id,
        outputs=structured_outputs_v2,
    )
    structured_index_v2_path = staging_run_dir / "structured_output_index_v2.json"
    _write_json(
        structured_index_v2_path,
        structured_index_v2.model_dump(mode="json"),
    )
    artifacts.append(
        _artifact(
            f"artifact:{run_id}:structured-output-index-v2",
            P001_STRUCTURED_OUTPUT_INDEX_V2_SCHEMA_REF,
            structured_index_v2_path,
            v2_evidence_ids,
            logical_path=final_run_dir / structured_index_v2_path.name,
        )
    )

    manifest_path = staging_run_dir / "artifact_manifest.json"
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
    artifacts.append(
        _artifact(
            f"artifact:{run_id}:manifest",
            "manifest",
            manifest_path,
            evidence_ids,
            logical_path=final_run_dir / manifest_path.name,
        )
    )

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
    payload = {
        "attempted_request": request.model_dump(mode="json"),
        "tool_version": spec.version,
        "reason_code": reason_code,
        "known_input_sha256": input_hash,
    }
    failed_run_digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    return ToolRun(
        run_id=f"run-{failed_run_digest[:16]}",
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
                denominator=int(len(values)) if available else None,
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
        groups, _ = _declared_group(obs, metadata, logical_name)
        checks[logical_name] = groups is not None
    return {"fields": checks, "complete": all(checks.values())}


def _declared_group(obs: pd.DataFrame, metadata: dict[str, Any], logical_name: str) -> tuple[pd.Series | None, str | None]:
    column = metadata.get(f"{logical_name}_column")
    if column is not None:
        if column not in obs.columns:
            return None, f"{logical_name}_incomplete"
        normalized = [_normalized_group_value(value) for value in obs[column].tolist()]
        if any(value is None for value in normalized):
            return None, f"{logical_name}_incomplete"
        return pd.Series(normalized, index=obs.index, dtype="string"), None
    if logical_name in metadata:
        normalized_value = _normalized_group_value(metadata.get(logical_name))
        if normalized_value is None:
            return None, f"{logical_name}_incomplete"
        return pd.Series([normalized_value] * len(obs), index=obs.index, dtype="string"), None
    return None, f"{logical_name}_not_declared"


_MISSING_GROUP_SENTINELS = frozenset(
    {
        "",
        "na",
        "n/a",
        "nan",
        "none",
        "null",
        "missing",
        "unknown",
        "unavailable",
        "not_assessed",
        "not assessed",
        "not available",
    }
)


def _normalized_group_value(value: object) -> str | None:
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        return None
    text = str(value).strip()
    if text.casefold() in _MISSING_GROUP_SENTINELS:
        return None
    return text


def _assess_doublets(
    adata,
    metrics: pd.DataFrame,
    metadata: dict[str, Any],
    measurement_spec: MeasurementSpec | None,
    request: ToolRequest,
) -> tuple[dict[str, Any], list[str]]:
    groups, warning = _declared_group(adata.obs, metadata, "capture_id")
    if groups is None:
        reason = warning or "capture_id_not_declared"
        return {"state": "not_assessed", "reason": reason}, [reason]
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
    staging_run_dir: Path,
    final_run_dir: Path,
    run_id: str,
    observation_unit: str,
) -> tuple[list[ArtifactManifest], list[VisualizationArtifact]]:
    data_path = staging_run_dir / "qc_visualization_data.parquet"
    metrics.to_parquet(data_path)
    overview_svg, overview_png = render_qc_overview(
        metrics,
        staging_run_dir / "qc_overview",
        observation_unit=observation_unit,
    )
    scatter_svg, scatter_png = render_counts_genes_scatter(
        metrics,
        staging_run_dir / "counts_genes_scatter",
    )
    evidence = [f"evidence:{run_id}:count-metrics"]
    artifacts = [
        _artifact(f"artifact:{run_id}:visual-data", "visualization_data", data_path, evidence, logical_path=final_run_dir / data_path.name),
        _artifact(f"artifact:{run_id}:overview-svg", "visualization_svg", overview_svg, evidence, logical_path=final_run_dir / overview_svg.name),
        _artifact(f"artifact:{run_id}:overview-png", "visualization_png", overview_png, evidence, logical_path=final_run_dir / overview_png.name),
        _artifact(f"artifact:{run_id}:scatter-svg", "visualization_svg", scatter_svg, evidence, logical_path=final_run_dir / scatter_svg.name),
        _artifact(f"artifact:{run_id}:scatter-png", "visualization_png", scatter_png, evidence, logical_path=final_run_dir / scatter_png.name),
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


def _artifact(
    artifact_id: str,
    kind: str,
    path: Path,
    evidence_ids: list[str],
    *,
    logical_path: Path,
) -> ArtifactManifest:
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
        path=logical_path.resolve(),
        media_type=media_types.get(path.suffix, "application/octet-stream"),
        sha256=sha256_path(path),
        evidence_ids=evidence_ids,
    )


def _structured_output_record(
    *,
    role: str,
    artifact: ArtifactManifest,
    schema_ref: str,
    object_version: str,
) -> P001StructuredOutputRecord:
    return P001StructuredOutputRecord(
        role=role,
        relative_filename=artifact.path.name,
        artifact_id=artifact.artifact_id,
        sha256=artifact.sha256,
        media_type="application/json",
        schema_ref=schema_ref,
        object_version=object_version,
    )


def _structured_output_record_v2(
    *,
    role: str,
    artifact: ArtifactManifest,
    schema_ref: str,
    object_version: str,
) -> P001StructuredOutputRecordV2:
    return P001StructuredOutputRecordV2(
        role=role,
        relative_filename=artifact.path.name,
        artifact_id=artifact.artifact_id,
        sha256=artifact.sha256,
        media_type="application/json",
        schema_ref=schema_ref,
        object_version=object_version,
    )


def _private_workspace(output_dir: Path) -> Path:
    parent = output_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix=".bridge-p0-01-", dir=parent))
    workspace.chmod(0o700)
    return workspace


def _snapshot_asset(source: Path, destination_root: Path) -> Path:
    destination_root.mkdir(mode=0o700)
    destination = destination_root / source.name
    if source.is_dir():
        shutil.copytree(source, destination, symlinks=True)
    else:
        shutil.copy2(source, destination, follow_symlinks=False)
    return destination


def _publish_bundle(staging_run_dir: Path, final_run_dir: Path) -> str | None:
    output_dir = final_run_dir.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    if final_run_dir.exists() or final_run_dir.is_symlink():
        return None if _bundles_match(staging_run_dir, final_run_dir) else "existing_run_bundle_mismatch"
    try:
        os.rename(staging_run_dir, final_run_dir)
    except FileExistsError:
        return None if _bundles_match(staging_run_dir, final_run_dir) else "existing_run_bundle_mismatch"
    except OSError:
        if final_run_dir.exists() or final_run_dir.is_symlink():
            return None if _bundles_match(staging_run_dir, final_run_dir) else "existing_run_bundle_mismatch"
        raise
    return None


def _bundles_match(first: Path, second: Path) -> bool:
    try:
        return _bundle_records(first) == _bundle_records(second)
    except (InputAuditError, OSError):
        return False


def _bundle_records(root: Path) -> tuple[tuple[str, int, str], ...]:
    if root.is_symlink() or not root.is_dir():
        raise InputAuditError("existing_run_bundle_mismatch", "Run bundle must be a regular directory")
    records: list[tuple[str, int, str]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        if path.is_symlink():
            raise InputAuditError("existing_run_bundle_mismatch", "Run bundle cannot contain symlinks")
        if path.is_dir():
            continue
        if not path.is_file():
            raise InputAuditError("existing_run_bundle_mismatch", "Run bundle cannot contain special files")
        records.append(
            (
                path.relative_to(root).as_posix(),
                path.stat().st_size,
                sha256_path(path),
            )
        )
    return tuple(records)


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
