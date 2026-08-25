from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from bridge.tool_packages.p0_01_input_qc.io import (
    InputAuditError,
    read_expression_asset,
    sha256_path,
    validate_expression_object,
)
from bridge.tool_packages.p0_02_cell_state.measurement_specs import load_measurement_spec
from bridge.tool_packages.p0_02_cell_state.metrics import (
    composition_records,
    composition_records_v3,
    hierarchy_restricted_summary,
    marker_program_evidence,
    normalize_query,
    reconcile_source_tops,
    serialize_prediction_sets,
    source_support,
)
from bridge.tool_packages.p0_02_cell_state.reference import (
    ReferenceError,
    canonicalize_source_family_id,
    load_reference_profile,
    load_snapshot_resources,
    resolve_reference_snapshot,
    validate_runtime_reference,
)
from bridge.tool_packages.p0_02_cell_state.qc import (
    UpstreamQCError,
    validate_selected_data_view,
    validate_upstream_qc_bundle,
    validate_upstream_qc_unchanged,
)
from bridge.tool_packages.p0_02_cell_state.visualization import (
    render_composition,
    render_conflicts,
    render_marker_evidence,
    render_reference_support,
)
from bridge.toolkit.contracts import (
    ArtifactManifest,
    CellStateEvidenceProfile,
    CellStateEvidenceProfileV3,
    EvidenceState,
    ExecutionState,
    MeasurementResult,
    ScoreState,
    ToolPackageSpec,
    ToolRequest,
    ToolRun,
    VisualizationArtifact,
)


def run_cell_state_evidence(request: ToolRequest, spec: ToolPackageSpec) -> ToolRun:
    asset = request.assets[0]
    input_hash = sha256_path(asset.path)
    if asset.checksum is not None and asset.checksum != input_hash:
        return _failed_run(request, spec, input_hash, "input_checksum_mismatch")
    try:
        upstream_qc = validate_upstream_qc_bundle(asset, input_hash)
    except UpstreamQCError as exc:
        return _failed_run(request, spec, input_hash, exc.reason_code, str(exc))
    measurement_spec = load_measurement_spec(request.measurement_spec_ref)
    if measurement_spec is None:
        return _failed_run(request, spec, input_hash, "measurement_spec_not_found")
    measurement_spec_sha256 = _semantic_sha256(
        measurement_spec.model_dump(mode="json")
    )
    release = None
    if measurement_spec.release_manifest_ref:
        try:
            from bridge.tool_packages.p0_02_cell_state.freeze import resolve_release_bundle

            release = resolve_release_bundle(measurement_spec.release_manifest_ref)
            if release.measurement_spec_ref != measurement_spec.measurement_spec_id:
                raise ReferenceError(
                    "cell_state_release_measurement_spec_mismatch",
                    release.release_manifest_id,
                )
            if release.reference_snapshot_ref != measurement_spec.reference_refs[0]:
                raise ReferenceError(
                    "cell_state_release_reference_mismatch",
                    release.release_manifest_id,
                )
            if (
                release.runtime_tool_version != spec.version
                or release.environment_spec_ref != spec.environment_spec_id
            ):
                raise ReferenceError(
                    "cell_state_release_runtime_mismatch", release.release_manifest_id
                )
        except ValueError as exc:
            return _failed_run(
                request,
                spec,
                input_hash,
                getattr(exc, "reason_code", "cell_state_release_invalid"),
                str(exc),
            )

    try:
        snapshot_id = measurement_spec.reference_refs[0]
        snapshot_root = resolve_reference_snapshot(snapshot_id)
        manifest, vocabulary, marker_cards = load_snapshot_resources(snapshot_root)
        validate_runtime_reference(manifest)
        reference_manifest_hash = sha256_path(snapshot_root / "reference_manifest.json")
        if release and release.reference_manifest_sha256 != reference_manifest_hash:
            raise ReferenceError(
                "cell_state_release_reference_checksum_mismatch",
                release.release_manifest_id,
            )
        if release and release.annotation_vocabulary_ref != vocabulary.vocabulary_id:
            raise ReferenceError(
                "cell_state_release_vocabulary_mismatch", release.release_manifest_id
            )
        if measurement_spec.measurement_spec_id not in manifest.measurement_spec_ids:
            raise ReferenceError("measurement_spec_not_supported_by_reference", measurement_spec.measurement_spec_id)
        adata = read_expression_asset(asset)
        validate_expression_object(adata, require_counts=asset.matrix_semantics == "raw_counts")
        genes = _declared_gene_names(adata, asset.metadata)
    except (InputAuditError, ReferenceError) as exc:
        return _failed_run(request, spec, input_hash, exc.reason_code, str(exc))
    except Exception as exc:
        return _failed_run(request, spec, input_hash, "cell_state_input_read_failed", str(exc))

    query = normalize_query(adata.X, asset.matrix_semantics or "")
    observation_ids = adata.obs_names.astype(str).to_numpy()
    selected_data_view = None
    if upstream_qc.profile_v2 is not None:
        try:
            selected_data_view = validate_selected_data_view(
                upstream_qc.profile_v2,
                observation_ids.tolist(),
            )
        except UpstreamQCError as exc:
            return _failed_run(request, spec, input_hash, exc.reason_code, str(exc))
    minimum_shared = int(measurement_spec.minimum_data["minimum_shared_genes"])
    chunk_size = int(request.parameters.get("chunk_size", 256))
    workers = max(1, min(int(request.parameters.get("workers", min(4, os.cpu_count() or 1))), 8))
    run_id = _run_id(
        request,
        spec,
        input_hash,
        sha256_path(snapshot_root / "reference_manifest.json"),
        measurement_spec_sha256,
    )
    run_dir = request.output_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    support_frames: list[pd.DataFrame] = []
    source_summaries: list[pd.DataFrame] = []
    primary_source_ids: list[str] = []
    coverage_records: list[dict[str, Any]] = []
    warnings = ["open_set_calibration_not_frozen", "marker_programs_are_shadow_candidates"]
    query_source_family = canonicalize_source_family_id(str(asset.metadata["source_family_id"]))
    held_out_sources = sorted(
        profile.source_id
        for profile in manifest.profiles
        if canonicalize_source_family_id(profile.source_family_id) == query_source_family
        and profile.matrix_file
    )
    if held_out_sources:
        warnings.append(f"reference_source_family_held_out:{query_source_family}")

    primary_profiles = [
        profile
        for profile in manifest.profiles
        if profile.assay == asset.assay
        and profile.label_level == "L1"
        and profile.role == "primary"
        and profile.matrix_file
        and canonicalize_source_family_id(profile.source_family_id) != query_source_family
    ]
    for profile in primary_profiles:
        reference, metadata = load_reference_profile(snapshot_root, profile)
        support, summary, coverage = source_support(
            query,
            genes,
            reference,
            metadata,
            observation_ids,
            minimum_shared_genes=minimum_shared,
            chunk_size=chunk_size,
            workers=workers,
        )
        coverage.update({"source_id": profile.source_id, "role": profile.role, "label_level": "L1"})
        coverage_records.append(coverage)
        if summary.empty:
            warnings.append(f"reference_gene_coverage_insufficient:{profile.source_id}")
            continue
        support.insert(1, "source_id", profile.source_id)
        support.insert(2, "label_level", "L1")
        support.insert(3, "reference_role", "primary")
        summary.insert(1, "source_id", profile.source_id)
        support_frames.append(support)
        source_summaries.append(summary)
        primary_source_ids.append(profile.source_id)

    if not source_summaries:
        return _failed_run(
            request,
            spec,
            input_hash,
            "no_applicable_reference_support",
            "; ".join(sorted(set(warnings))),
        )

    evidence = reconcile_source_tops(observation_ids, source_summaries)
    for source_id, summary in zip(primary_source_ids, source_summaries, strict=True):
        indexed = summary.set_index("observation_id")
        evidence[f"{source_id}__top_label"] = evidence["observation_id"].map(indexed["top_label"])
        evidence[f"{source_id}__margin"] = evidence["observation_id"].map(indexed["margin"])

    l2_evidence, l2_support, l2_coverage, l2_composition = _run_l2(
        query,
        genes,
        evidence,
        observation_ids,
        manifest.profiles,
        vocabulary,
        snapshot_root,
        asset.assay or "",
        minimum_shared,
        chunk_size,
        workers,
        query_source_family,
    )
    if not l2_evidence.empty:
        evidence = evidence.merge(l2_evidence, on="observation_id", how="left")
        support_frames.extend(l2_support)
        coverage_records.extend(l2_coverage)

    marker, marker_summary = marker_program_evidence(
        query,
        genes,
        observation_ids,
        marker_cards,
        minimum_marker_genes=int(measurement_spec.minimum_data["minimum_marker_genes"]),
    )
    l1_composition = composition_records(evidence, source_summaries, primary_source_ids)
    for record in l1_composition:
        record["label_level"] = "L1"
        record["denominator_view"] = "all input observations"
    composition = list(l1_composition)
    composition.extend(l2_composition)
    modality_sensitivity, sensitivity_support = _run_sensitivity(
        query,
        genes,
        observation_ids,
        evidence,
        manifest.profiles,
        snapshot_root,
        minimum_shared,
        chunk_size,
        workers,
        query_source_family,
    )
    support_frames.extend(sensitivity_support)
    composition_frame = pd.DataFrame(composition)
    support_frame = pd.concat(support_frames, ignore_index=True)
    unresolved = [label.state_id for label in vocabulary.labels if label.status == "unresolved"]
    state_counts = evidence["support_state"].value_counts().to_dict()
    evidence_ids = [
        f"evidence:{run_id}:reference-support",
        f"evidence:{run_id}:marker-program",
        f"evidence:{run_id}:source-reconciliation",
    ]
    profile = CellStateEvidenceProfile(
        profile_id=f"cell-state-profile:{run_id}",
        assay=asset.assay or "unknown",
        measurement_spec_id=measurement_spec.measurement_spec_id,
        measurement_spec_status=measurement_spec.status,
        annotation_vocabulary_ref=vocabulary.vocabulary_id,
        reference_snapshot_ref=manifest.snapshot_id,
        n_observations=int(adata.n_obs),
        n_genes=int(adata.n_vars),
        denominator="all observations in the declared post-QC input view",
        label_levels={
            "L1": {"state": "shadow", "n_observations": int(adata.n_obs)},
            "L2": {
                "state": "shadow" if not l2_evidence.empty else "unavailable",
                "n_observations": int(len(l2_evidence)),
                "eligibility": "L1 prediction set contains Radial_Glia or Neuroblast",
            },
            "L3": {"state": "shadow_not_executed"},
        },
        source_support={
            "state": "shadow",
            "primary_sources": primary_source_ids,
            "query_source_family_id": query_source_family,
            "held_out_sources": held_out_sources,
            "aggregation": "sample-by-label profiles; median within source; no cell-count weighting across sources",
            "coverage": coverage_records,
        },
        marker_program_evidence={"state": "shadow", "programs": marker_summary},
        prediction_sets={
            "state_counts": {str(key): int(value) for key, value in state_counts.items()},
            "open_set_state": "not_assessed",
            "interpretation": "candidate set only; not a calibrated assignment",
        },
        composition={"state": "shadow", "records": composition},
        gene_coverage={"records": coverage_records},
        modality_sensitivity=modality_sensitivity,
        method_outputs=_runtime_method_outputs(release),
        assignment_state={
            "state": "released_per_state" if release else "candidate_prediction_set",
            "interpretation": (
                "Only states listed as frozen or provisional_frozen in the signed release are released."
                if release
                else "source support has not passed release calibration"
            ),
        },
        unknown_reason={
            "state": "not_assessed",
            "reason": "open_set_calibration_not_frozen",
        },
        calibration={"state": "not_assessed"},
        method_disagreement={
            "state_counts": {str(key): int(value) for key, value in state_counts.items()}
        },
        per_state_release=(
            release.per_state_release
            if release
            else {
                label.state_id: "unavailable" if label.status == "unresolved" else "shadow"
                for label in vocabulary.labels
            }
        ),
        unresolved_labels=unresolved,
        warnings=sorted(set(warnings)),
        evidence_ids=evidence_ids,
        score_state=ScoreState.SHADOW,
        domain_score=None,
    )
    profile_v3 = None
    if selected_data_view is not None:
        try:
            profile_v3_payload = profile.model_dump(mode="python")
            profile_v3_payload.update(
                {
                    "denominator": "selected_data_view",
                    "composition": {
                        "state": "shadow",
                        "records": composition_records_v3(
                            l1_composition,
                            selected_view_denominator=selected_data_view.n_observations,
                        ),
                    },
                    "measurement_spec_version": measurement_spec.version,
                    "measurement_spec_sha256": measurement_spec_sha256,
                    "annotation_vocabulary_version": vocabulary.version,
                    "annotation_vocabulary_sha256": manifest.vocabulary_sha256,
                    "reference_manifest_version": manifest.version,
                    "reference_manifest_sha256": reference_manifest_hash,
                    "upstream_qc_profile_ref": upstream_qc.profile_v2.profile_id,
                    "upstream_qc_profile_sha256": upstream_qc.profile_v2_sha256,
                    "input_data_view": selected_data_view,
                    "open_set_state": "not_assessed",
                    "calibration_state": "not_assessed",
                    "producer_run_ref": run_id,
                    "producer_tool_id": "P0-02",
                    "producer_tool_version": spec.version,
                    "environment_spec_ref": spec.environment_spec_id,
                }
            )
            profile_v3 = CellStateEvidenceProfileV3.model_validate(
                profile_v3_payload
            )
        except ValueError as exc:
            return _failed_run(
                request,
                spec,
                input_hash,
                "cell_state_profile_v3_generation_failed",
                str(exc),
            )

    try:
        validate_upstream_qc_unchanged(upstream_qc)
    except UpstreamQCError as exc:
        return _failed_run(request, spec, input_hash, exc.reason_code, str(exc))

    artifacts, visualizations = _write_outputs(
        run_dir,
        run_id,
        profile,
        evidence,
        support_frame,
        marker,
        composition_frame,
        evidence_ids,
    )
    if profile_v3 is not None:
        profile_v3_path = run_dir / "cell_state_evidence_profile_v3.json"
        _write_json(profile_v3_path, profile_v3.model_dump(mode="json"))
        artifacts.append(
            _artifact(
                f"artifact:{run_id}:profile-v3",
                "cell_state_profile_v3",
                profile_v3_path,
                evidence_ids,
            )
        )
    manifest_path = run_dir / "artifact_manifest.json"
    manifest_artifacts = []
    for item in artifacts:
        record = item.model_dump(mode="json")
        record["size_bytes"] = item.path.stat().st_size
        manifest_artifacts.append(record)
    _write_json(
        manifest_path,
        {
            "run_id": run_id,
            "tool_id": spec.tool_id,
            "tool_version": spec.version,
            "environment_spec_id": spec.environment_spec_id,
            "input_hash": input_hash,
            "reference_snapshot_id": manifest.snapshot_id,
            "reference_manifest_hash": reference_manifest_hash,
            "measurement_spec_ref": request.measurement_spec_ref,
            "measurement_spec_sha256": measurement_spec_sha256,
            "artifacts": manifest_artifacts,
            "visualizations": [item.model_dump(mode="json") for item in visualizations],
        },
    )
    artifacts.append(
        _artifact(
            f"artifact:{run_id}:manifest",
            "manifest",
            manifest_path,
            evidence_ids,
        )
    )
    if sha256_path(asset.path) != input_hash:
        return _failed_run(request, spec, input_hash, "input_asset_modified_during_run")
    try:
        validate_upstream_qc_unchanged(upstream_qc)
    except UpstreamQCError as exc:
        return _failed_run(request, spec, input_hash, exc.reason_code, str(exc))
    run_warnings = list(profile.warnings)
    if profile_v3 is None:
        run_warnings.append(
            "cell_state_evidence_profile_v3_unavailable:"
            f"{upstream_qc.v2_unavailable_reason}"
        )
    return ToolRun(
        run_id=run_id,
        request=request,
        implementation_state=spec.implementation_state,
        execution_state=ExecutionState.SUCCEEDED,
        tool_version=spec.version,
        environment_spec_id=spec.environment_spec_id,
        input_hash=input_hash,
        measurements=_measurements(
            run_id,
            measurement_spec.measurement_spec_id,
            evidence,
            marker_summary,
            len(primary_source_ids),
        ),
        artifacts=artifacts,
        visualizations=visualizations,
        result=profile.model_dump(mode="json"),
        warnings=sorted(set(run_warnings)),
    )


def _runtime_method_outputs(release) -> dict[str, dict[str, Any]]:
    outputs = {
        "marker_program_evidence": {"release_state": "shadow"},
        "source_specific_correlation": {"release_state": "shadow"},
    }
    if release is None:
        return outputs
    for method in outputs:
        states = sorted(
            state_id
            for state_id, methods in release.selected_methods.items()
            if method in methods
        )
        if states:
            outputs[method] = {
                "release_state": "frozen",
                "released_for_states": states,
            }
    return outputs


def _run_l2(
    query,
    genes: np.ndarray,
    l1_evidence: pd.DataFrame,
    observation_ids: np.ndarray,
    profiles,
    vocabulary,
    snapshot_root: Path,
    assay: str,
    minimum_shared: int,
    chunk_size: int,
    workers: int,
    query_source_family: str,
):
    children: dict[str, set[str]] = {}
    for label in vocabulary.labels:
        if label.level == "L2" and label.status == "candidate":
            for parent in label.parent_state_ids:
                children.setdefault(parent, set()).add(label.state_id)
    allowed_labels = {
        row.observation_id: set().union(*(children.get(parent, set()) for parent in row.prediction_set))
        for row in l1_evidence[["observation_id", "prediction_set"]].itertuples()
    }
    eligible = np.asarray([bool(allowed_labels[observation_id]) for observation_id in observation_ids])
    if not eligible.any():
        return pd.DataFrame(), [], [], []
    summaries: list[pd.DataFrame] = []
    supports: list[pd.DataFrame] = []
    source_ids: list[str] = []
    coverage_records: list[dict[str, Any]] = []
    ids = observation_ids[eligible]
    for profile in profiles:
        if not (
            profile.assay == assay
            and profile.label_level == "L2"
            and profile.role == "refinement"
            and profile.matrix_file
            and canonicalize_source_family_id(profile.source_family_id) != query_source_family
        ):
            continue
        reference, metadata = load_reference_profile(snapshot_root, profile)
        support, _, coverage = source_support(
            query[eligible],
            genes,
            reference,
            metadata,
            ids,
            minimum_shared_genes=minimum_shared,
            chunk_size=chunk_size,
            workers=workers,
        )
        coverage.update({"source_id": profile.source_id, "role": profile.role, "label_level": "L2"})
        coverage_records.append(coverage)
        if support.empty:
            continue
        support, summary = hierarchy_restricted_summary(
            support,
            ids,
            {observation_id: allowed_labels[observation_id] for observation_id in ids},
        )
        support.insert(1, "source_id", profile.source_id)
        support.insert(2, "label_level", "L2")
        support.insert(3, "reference_role", "refinement")
        supports.append(support)
        summaries.append(summary)
        source_ids.append(profile.source_id)
    if not summaries:
        return pd.DataFrame(), supports, coverage_records, []
    reconciled = reconcile_source_tops(ids, summaries).rename(
        columns={
            "prediction_set": "l2_prediction_set",
            "consensus_label": "l2_consensus_label",
            "support_state": "l2_support_state",
            "assignment_state": "l2_assignment_state",
            "open_set_state": "l2_open_set_state",
        }
    )
    composition = composition_records(
        reconciled.rename(
            columns={
                "l2_support_state": "support_state",
                "l2_consensus_label": "consensus_label",
            }
        ),
        summaries,
        source_ids,
    )
    for record in composition:
        record["label_level"] = "L2"
        record["denominator_view"] = "L2-eligible observations"
    return reconciled, supports, coverage_records, composition


def _run_sensitivity(
    query,
    genes,
    observation_ids,
    primary_evidence,
    profiles,
    snapshot_root,
    minimum_shared,
    chunk_size,
    workers,
    query_source_family,
) -> tuple[dict[str, Any], list[pd.DataFrame]]:
    records: list[dict[str, Any]] = []
    support_frames: list[pd.DataFrame] = []
    for profile in profiles:
        if not (
            profile.role == "sensitivity"
            and profile.label_level == "L1"
            and profile.matrix_file
            and canonicalize_source_family_id(profile.source_family_id) != query_source_family
        ):
            continue
        reference, metadata = load_reference_profile(snapshot_root, profile)
        support, summary, coverage = source_support(
            query,
            genes,
            reference,
            metadata,
            observation_ids,
            minimum_shared_genes=minimum_shared,
            chunk_size=chunk_size,
            workers=workers,
        )
        if not support.empty:
            support.insert(1, "source_id", profile.source_id)
            support.insert(2, "label_level", "L1_sensitivity")
            support.insert(3, "reference_role", "sensitivity")
            support_frames.append(support)
        candidate_sets = primary_evidence.set_index("observation_id")["prediction_set"]
        agreement = (
            float(
                np.mean(
                    [
                        row.top_label in candidate_sets.get(row.observation_id, [])
                        for row in summary.itertuples()
                    ]
                )
            )
            if not summary.empty
            else None
        )
        records.append(
            {
                "source_id": profile.source_id,
                "state": "shadow" if not summary.empty else "unavailable",
                "gene_coverage": coverage,
                "independent_evidence": False,
                "candidate_set_agreement_fraction": agreement,
                "top_label_counts": {
                    str(label): int(count)
                    for label, count in summary["top_label"].value_counts().items()
                }
                if not summary.empty
                else {},
            }
        )
    return {"state": "shadow" if records else "not_assessed", "records": records}, support_frames


def _write_outputs(
    run_dir: Path,
    run_id: str,
    profile: CellStateEvidenceProfile,
    evidence: pd.DataFrame,
    support: pd.DataFrame,
    marker: pd.DataFrame,
    composition: pd.DataFrame,
    evidence_ids: list[str],
) -> tuple[list[ArtifactManifest], list[VisualizationArtifact]]:
    profile_path = run_dir / "cell_state_evidence_profile.json"
    evidence_path = run_dir / "cell_state_evidence.parquet"
    support_path = run_dir / "source_specific_support.parquet"
    marker_path = run_dir / "marker_program_evidence.parquet"
    composition_path = run_dir / "shadow_composition.parquet"
    _write_json(profile_path, profile.model_dump(mode="json"))
    serialize_prediction_sets(evidence).to_parquet(evidence_path, index=False)
    support.to_parquet(support_path, index=False)
    if marker.empty:
        marker = pd.DataFrame(
            columns=[
                "observation_id",
                "card_id",
                "state_id",
                "positive_mean_expression",
                "negative_mean_expression",
                "review_status",
                "evidence_state",
            ]
        )
    marker.to_parquet(marker_path, index=False)
    composition.to_parquet(composition_path, index=False)
    artifacts = [
        _artifact(f"artifact:{run_id}:profile", "cell_state_profile", profile_path, evidence_ids),
        _artifact(f"artifact:{run_id}:evidence", "cell_state_evidence", evidence_path, evidence_ids),
        _artifact(f"artifact:{run_id}:support", "reference_support", support_path, [evidence_ids[0]]),
        _artifact(f"artifact:{run_id}:marker", "marker_program_evidence", marker_path, [evidence_ids[1]]),
        _artifact(f"artifact:{run_id}:composition", "shadow_composition", composition_path, [evidence_ids[2]]),
    ]
    visualizations: list[VisualizationArtifact] = []
    renders = [
        (
            "composition-l1",
            render_composition(composition, run_dir / "shadow_composition_l1", label_level="L1"),
            f"artifact:{run_id}:composition",
            evidence_ids[2],
            "all observations in the declared post-QC input view",
        ),
        (
            "reference-support",
            render_reference_support(support[support["label_level"] == "L1"], run_dir / "reference_support"),
            f"artifact:{run_id}:support",
            evidence_ids[0],
            "all observations in the declared post-QC input view",
        ),
        (
            "conflicts",
            render_conflicts(evidence, run_dir / "source_conflicts"),
            f"artifact:{run_id}:evidence",
            evidence_ids[2],
            "all observations in the declared post-QC input view",
        ),
    ]
    if (composition["label_level"] == "L2").any():
        renders.append(
            (
                "composition-l2",
                render_composition(composition, run_dir / "shadow_composition_l2", label_level="L2"),
                f"artifact:{run_id}:composition",
                evidence_ids[2],
                "L2-eligible observations",
            )
        )
    if not marker.empty:
        renders.append(
            (
                "marker",
                render_marker_evidence(marker, evidence, run_dir / "marker_evidence"),
                f"artifact:{run_id}:marker",
                evidence_ids[1],
                "all observations in the declared post-QC input view",
            )
        )
    for name, (svg, png), data_artifact, evidence_id, denominator in renders:
        svg_id = f"artifact:{run_id}:{name}-svg"
        png_id = f"artifact:{run_id}:{name}-png"
        artifacts.extend(
            [
                _artifact(svg_id, "visualization_svg", svg, [evidence_id]),
                _artifact(png_id, "visualization_png", png, [evidence_id]),
            ]
        )
        visualizations.append(
            VisualizationArtifact(
                visualization_id=f"visualization:{run_id}:{name}",
                component_id=f"bridge.cell_state.{name}.v0.1",
                data_artifact_id=data_artifact,
                evidence_ids=[evidence_id],
                denominator=denominator,
                units="raw support or fraction",
                status="shadow",
                render_artifact_ids=[svg_id, png_id],
            )
        )
    return artifacts, visualizations


def _measurements(
    run_id: str,
    spec_id: str,
    evidence: pd.DataFrame,
    marker_summary: list[dict[str, Any]],
    primary_source_count: int,
):
    denominator = len(evidence)
    consensus_available = primary_source_count >= 2
    return [
        MeasurementResult(
            measurement_id=f"measurement:{run_id}:consensus-supported-fraction",
            measurement_spec_id=spec_id,
            metric_name="consensus_supported_fraction",
            raw_value=float((evidence["support_state"] == "consensus_supported").mean())
            if consensus_available
            else None,
            denominator=denominator if consensus_available else None,
            score_state=ScoreState.SHADOW if consensus_available else ScoreState.UNAVAILABLE,
            evidence_state=EvidenceState.INFERRED if consensus_available else EvidenceState.UNAVAILABLE,
            provenance_refs=[f"evidence:{run_id}:source-reconciliation"],
        ),
        MeasurementResult(
            measurement_id=f"measurement:{run_id}:source-conflict-fraction",
            measurement_spec_id=spec_id,
            metric_name="source_conflict_fraction",
            raw_value=float((evidence["support_state"] == "source_conflict").mean())
            if consensus_available
            else None,
            denominator=denominator if consensus_available else None,
            score_state=ScoreState.SHADOW if consensus_available else ScoreState.UNAVAILABLE,
            evidence_state=EvidenceState.INFERRED if consensus_available else EvidenceState.UNAVAILABLE,
            provenance_refs=[f"evidence:{run_id}:source-reconciliation"],
        ),
        MeasurementResult(
            measurement_id=f"measurement:{run_id}:marker-programs-assessed",
            measurement_spec_id=spec_id,
            metric_name="marker_programs_assessed",
            raw_value=sum(item["state"] == "shadow" for item in marker_summary),
            score_state=ScoreState.SHADOW,
            evidence_state=EvidenceState.PRIOR_ONLY,
            provenance_refs=[f"evidence:{run_id}:marker-program"],
        ),
    ]


def _declared_gene_names(adata, metadata: dict[str, Any]) -> np.ndarray:
    column = metadata.get("gene_symbol_column")
    if column is not None and column not in adata.var:
        raise InputAuditError("gene_symbol_column_not_found", str(column))
    values = adata.var_names if column is None else adata.var[column]
    genes = np.asarray([str(value).strip().upper() for value in values])
    if len(set(genes)) != len(genes):
        raise InputAuditError("gene_ids_not_unique_after_normalization", column or "var_names")
    return genes


def _run_id(
    request: ToolRequest,
    spec: ToolPackageSpec,
    input_hash: str,
    reference_hash: str,
    measurement_spec_sha256: str,
) -> str:
    payload = json.dumps(
        {
            "request": request.model_dump(mode="json"),
            "tool_version": spec.version,
            "input_hash": input_hash,
            "reference_hash": reference_hash,
            "measurement_spec_sha256": measurement_spec_sha256,
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return f"run-{hashlib.sha256(payload.encode()).hexdigest()[:16]}"


def _semantic_sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _failed_run(request, spec, input_hash, reason_code, detail=None) -> ToolRun:
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


def _artifact(artifact_id: str, kind: str, path: Path, evidence_ids: list[str]) -> ArtifactManifest:
    media_types = {
        ".json": "application/json",
        ".parquet": "application/vnd.apache.parquet",
        ".svg": "image/svg+xml",
        ".png": "image/png",
    }
    return ArtifactManifest(
        artifact_id=artifact_id,
        kind=kind,
        path=path.resolve(),
        media_type=media_types[path.suffix],
        sha256=sha256_path(path),
        evidence_ids=evidence_ids,
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False, default=str) + "\n",
        encoding="utf-8",
    )
