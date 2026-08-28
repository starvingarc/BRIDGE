from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib
import pandas as pd

from bridge.tool_packages.p0_01_input_qc.io import (
    P001VisualizationArtifactSet,
    QC_COMPONENT_REFS,
    QC_VISUALIZATION_DATA_SCHEMA_REF,
    QCVisualizationDataProfile,
    QCVisualizationRecord,
    canonical_json_bytes,
    sha256_path,
)
from bridge.tool_packages.p0_01_input_qc.visualization import (
    FLAG_LABELS,
    METRICS,
    flag_intersection_table,
    render_analysis_eligibility,
    render_qc_distributions,
    render_qc_flag_intersections,
    render_qc_relationships,
    render_unavailable_figure,
)
from bridge.toolkit.contracts import (
    ArtifactManifest,
    EvidenceState,
    MeasurementSpec,
    QCReadinessProfileV2,
)
from bridge.toolkit.visualization import (
    FigureRegistry,
    VisualizationAccessibility,
    VisualizationArtifactV2,
    VisualizationDataBinding,
    VisualizationRenderBinding,
)


_EXPORT_PROFILE = {
    "export_profile_id": "bridge-static-scientific-figure-v0.1",
    "renderer_id": "bridge.matplotlib",
    "dpi": 300,
    "vector_format": "svg",
    "raster_format": "png",
    "palette": "bridge-qc-accessible-v0.1",
}

_COMPONENT_METADATA = {
    "bridge.qc.readiness-flow@0.1.0": {
        "slug": "observation-retention",
        "title": "Observation retention and analysis eligibility",
        "unit": "observations and availability states",
        "denominator": True,
    },
    "bridge.qc.overview@0.2.0": {
        "slug": "capture-distributions",
        "title": "Quality-metric distributions by capture",
        "unit": "metric-specific",
        "denominator": False,
    },
    "bridge.qc.counts_genes@0.2.0": {
        "slug": "metric-relationships",
        "title": "Library complexity and mitochondrial transcript fraction",
        "unit": "counts, detected genes and percent",
        "denominator": False,
    },
    "bridge.qc.flag-intersections@0.1.0": {
        "slug": "flag-intersections",
        "title": "QC-flag combinations and observation counts",
        "unit": "observations",
        "denominator": True,
    },
}


@dataclass(frozen=True)
class TypedQCVisualizationBundle:
    artifacts: tuple[ArtifactManifest, ...]
    data_artifact: ArtifactManifest
    artifact_set_artifact: ArtifactManifest


def write_typed_qc_visualizations(
    *,
    metrics: pd.DataFrame | None,
    flags: pd.DataFrame | None,
    capture_groups: pd.Series | None,
    measurement_spec: MeasurementSpec | None,
    profile: QCReadinessProfileV2,
    metrics_artifact: ArtifactManifest | None,
    staging_run_dir: Path,
    final_run_dir: Path,
    run_id: str,
    tool_version: str,
    observation_unit: str,
) -> TypedQCVisualizationBundle:
    declared = int(profile.schema_integrity["n_observations"])
    records, display_groups = _build_records(
        metrics=metrics,
        flags=flags,
        capture_groups=capture_groups,
        measurement_spec=measurement_spec,
        profile=profile,
        run_id=run_id,
        declared=declared,
        observation_unit=observation_unit,
    )
    data_profile = QCVisualizationDataProfile(
        profile_id=f"qc-visualization-data:{run_id}",
        producer_run_ref=f"run:{run_id}",
        observation_unit=observation_unit,
        source_table_artifact_id=metrics_artifact.artifact_id if metrics_artifact else None,
        source_table_sha256=metrics_artifact.sha256 if metrics_artifact else None,
        source_columns=list(metrics.columns) if metrics is not None else [],
        records=records,
    )
    all_evidence = sorted({item for record in records for item in record.evidence_ids})
    generated: list[ArtifactManifest] = []

    data_path = staging_run_dir / "qc_visualization_data.json"
    data_path.write_bytes(canonical_json_bytes(data_profile))
    data_artifact = _manifest(
        artifact_id=f"artifact:{run_id}:qc-visualization-data",
        kind="qc_visualization_data",
        source_path=data_path,
        logical_path=final_run_dir / data_path.name,
        media_type="application/json",
        evidence_ids=all_evidence,
    )
    generated.append(data_artifact)

    table_path = staging_run_dir / "qc_visualization_table.tsv"
    _write_record_table(table_path, records)
    table_artifact = _manifest(
        artifact_id=f"artifact:{run_id}:qc-visualization-table",
        kind="qc_visualization_table",
        source_path=table_path,
        logical_path=final_run_dir / table_path.name,
        media_type="text/tab-separated-values",
        evidence_ids=all_evidence,
    )
    generated.append(table_artifact)

    render_artifacts = _render_figures(
        metrics=metrics,
        flags=flags,
        display_groups=display_groups,
        measurement_spec=measurement_spec,
        profile=profile,
        staging_run_dir=staging_run_dir,
        final_run_dir=final_run_dir,
        run_id=run_id,
        observation_unit=observation_unit,
        declared=declared,
    )
    generated.extend(render_artifacts.values())

    data_hash = data_artifact.sha256
    visualizations = [
        _visualization_contract(
            component_ref=component_ref,
            records=[record for record in records if record.component_ref == component_ref],
            data_artifact=data_artifact,
            table_artifact=table_artifact,
            svg_artifact=render_artifacts[f"{component_ref}:svg"],
            png_artifact=render_artifacts[f"{component_ref}:png"],
            run_id=run_id,
            tool_version=tool_version,
            observation_unit=observation_unit,
            declared=declared,
            data_hash=data_hash,
        )
        for component_ref in QC_COMPONENT_REFS
    ]
    registry = FigureRegistry.load_default()
    for artifact in visualizations:
        registry.validate_artifact(artifact)

    artifact_set = P001VisualizationArtifactSet(
        artifact_set_id=f"p0-01-visualizations:{run_id}",
        data_profile_artifact_id=data_artifact.artifact_id,
        data_profile_sha256=data_hash,
        visualizations=visualizations,
    )
    artifact_set_path = staging_run_dir / "qc_visualization_artifact_set.json"
    artifact_set_path.write_bytes(canonical_json_bytes(artifact_set))
    artifact_set_artifact = _manifest(
        artifact_id=f"artifact:{run_id}:qc-visualization-artifact-set",
        kind="visualization_artifact_set",
        source_path=artifact_set_path,
        logical_path=final_run_dir / artifact_set_path.name,
        media_type="application/json",
        evidence_ids=all_evidence,
    )
    generated.append(artifact_set_artifact)
    return TypedQCVisualizationBundle(
        artifacts=tuple(generated),
        data_artifact=data_artifact,
        artifact_set_artifact=artifact_set_artifact,
    )


def _build_records(
    *,
    metrics: pd.DataFrame | None,
    flags: pd.DataFrame | None,
    capture_groups: pd.Series | None,
    measurement_spec: MeasurementSpec | None,
    profile: QCReadinessProfileV2,
    run_id: str,
    declared: int,
    observation_unit: str,
) -> tuple[list[QCVisualizationRecord], pd.Series | None]:
    structure_evidence = [f"evidence:{run_id}:structure"]
    count_evidence = [f"evidence:{run_id}:count-metrics"]
    flag_evidence = [f"evidence:{run_id}:candidate-flags"]
    records: list[QCVisualizationRecord] = [
        _available_record(
            "eligibility.declared",
            "bridge.qc.readiness-flow@0.1.0",
            "eligibility_stage",
            "Declared observations",
            "available",
            observation_unit,
            structure_evidence,
            statistic="declared_count",
            numerator=declared,
            denominator=declared,
            denominator_scope="submitted expression object",
        ),
        _available_record(
            "eligibility.structure",
            "bridge.qc.readiness-flow@0.1.0",
            "eligibility_stage",
            "Structure and matrix semantics",
            "eligible",
            "eligibility state",
            structure_evidence,
            value=1,
        ),
    ]
    if metrics is None:
        records.append(
            _unavailable_record(
                "eligibility.count-metrics",
                "bridge.qc.readiness-flow@0.1.0",
                "eligibility_stage",
                "Per-observation QC metrics",
                "availability state",
                structure_evidence,
                "count_level_input_required",
            )
        )
    else:
        records.append(
            _available_record(
                "eligibility.count-metrics",
                "bridge.qc.readiness-flow@0.1.0",
                "eligibility_stage",
                "Per-observation QC metrics",
                "available",
                "availability state",
                count_evidence,
                value=1,
            )
        )

    if flags is None:
        records.append(
            _unavailable_record(
                "eligibility.candidate-status",
                "bridge.qc.readiness-flow@0.1.0",
                "eligibility_stage",
                "Candidate QC status",
                observation_unit,
                count_evidence if metrics is not None else structure_evidence,
                _candidate_unavailable_reason(profile),
            )
        )
    else:
        eligible = int(flags["bridge_qc_candidate_eligible"].fillna(False).astype(bool).sum())
        for record_id, label, state, numerator in (
            ("eligibility.candidate-eligible", "Candidate-eligible", "candidate", eligible),
            (
                "eligibility.flagged-review",
                "Flagged for review",
                "review_required",
                declared - eligible,
            ),
        ):
            records.append(
                _available_record(
                    record_id,
                    "bridge.qc.readiness-flow@0.1.0",
                    "eligibility_stage",
                    label,
                    state,
                    observation_unit,
                    flag_evidence,
                    statistic="available_count",
                    numerator=numerator,
                    denominator=declared,
                    denominator_scope="submitted expression object",
                )
            )

    all_view = profile.data_views.get("all_cells_view", {})
    records.append(
        _view_record(
            "view.all-observations",
            "All-observation view",
            str(all_view.get("state", "unavailable")),
            declared,
            observation_unit,
            structure_evidence,
            "all_observation_view_unavailable",
        )
    )
    records.append(
        _view_record(
            "view.candidate-flags",
            "Candidate-flag view",
            "candidate" if flags is not None else "unavailable",
            declared,
            observation_unit,
            flag_evidence if flags is not None else count_evidence,
            _candidate_unavailable_reason(profile),
        )
    )
    records.append(
        _unavailable_record(
            "view.downstream-sensitivity",
            "bridge.qc.readiness-flow@0.1.0",
            "view_availability",
            "Downstream sensitivity results",
            "availability state",
            structure_evidence,
            "downstream_sensitivity_results_unavailable",
        )
    )

    distribution_records, display_groups = _distribution_records(
        metrics,
        capture_groups,
        count_evidence,
        observation_unit,
    )
    records.extend(distribution_records)
    records.extend(
        _relationship_records(
            metrics,
            measurement_spec,
            count_evidence,
            observation_unit,
        )
    )
    records.extend(
        _intersection_records(
            flags,
            flag_evidence if flags is not None else count_evidence,
            declared,
            observation_unit,
            _candidate_unavailable_reason(profile),
        )
    )
    return records, display_groups


def _distribution_records(
    metrics: pd.DataFrame | None,
    capture_groups: pd.Series | None,
    evidence_ids: list[str],
    observation_unit: str,
) -> tuple[list[QCVisualizationRecord], pd.Series | None]:
    component = "bridge.qc.overview@0.2.0"
    if metrics is None:
        return [
            _unavailable_record(
                "distribution.unavailable",
                component,
                "distribution_summary",
                "Capture-level QC distributions",
                "metric-specific",
                evidence_ids,
                "count_level_input_required",
            )
        ], None
    if capture_groups is None or len(capture_groups) != len(metrics):
        return [
            _unavailable_record(
                "distribution.unavailable",
                component,
                "distribution_summary",
                "Capture-level QC distributions",
                "metric-specific",
                evidence_ids,
                "capture_partition_unavailable",
            )
        ], None

    raw_groups = capture_groups.astype("string")
    unique_groups = sorted(raw_groups.dropna().unique().tolist())
    mapping = {group: (f"capture_{index:03d}", f"Capture {index}") for index, group in enumerate(unique_groups, 1)}
    display_groups = raw_groups.map({group: label for group, (_, label) in mapping.items()})
    records: list[QCVisualizationRecord] = []
    for raw_group in unique_groups:
        capture_id, capture_label = mapping[raw_group]
        group_metrics = metrics.loc[raw_groups.to_numpy() == raw_group]
        for metric_id, metric_label, record_unit, _, _ in METRICS:
            values = pd.to_numeric(group_metrics[metric_id], errors="coerce").dropna()
            base_id = f"distribution.{capture_id}.{metric_id}"
            if values.empty:
                records.append(
                    _unavailable_record(
                        f"{base_id}.unavailable",
                        component,
                        "distribution_summary",
                        f"{capture_label}: {metric_label}",
                        record_unit,
                        evidence_ids,
                        f"{metric_id}_unavailable",
                        metric_id=metric_id,
                        capture_id=capture_id,
                    )
                )
                continue
            summaries = {
                "available_count": int(len(values)),
                "q1": float(values.quantile(0.25)),
                "median": float(values.median()),
                "q3": float(values.quantile(0.75)),
            }
            for statistic, value in summaries.items():
                records.append(
                    _available_record(
                        f"{base_id}.{statistic}",
                        component,
                        "distribution_summary",
                        f"{capture_label}: {metric_label}",
                        "available",
                        record_unit,
                        evidence_ids,
                        metric_id=metric_id,
                        capture_id=capture_id,
                        statistic=statistic,
                        value=value,
                    )
                )
    return records, display_groups


def _relationship_records(
    metrics: pd.DataFrame | None,
    measurement_spec: MeasurementSpec | None,
    evidence_ids: list[str],
    observation_unit: str,
) -> list[QCVisualizationRecord]:
    component = "bridge.qc.counts_genes@0.2.0"
    if metrics is None:
        return [
            _unavailable_record(
                "relationships.unavailable",
                component,
                "relationship_summary",
                "Per-observation QC relationships",
                "metric-specific",
                evidence_ids,
                "count_level_input_required",
            )
        ]

    counts = pd.to_numeric(metrics["total_counts"], errors="coerce")
    genes = pd.to_numeric(metrics["detected_genes"], errors="coerce")
    records = [
        _available_record(
            "relationships.counts-genes.available",
            component,
            "relationship_summary",
            "Positive counts and detected genes",
            "available",
            observation_unit,
            evidence_ids,
            metric_id="counts_genes",
            statistic="available_count",
            value=int((counts.gt(0) & genes.gt(0)).sum()),
        )
    ]
    mitochondrial = pd.to_numeric(metrics["mitochondrial_fraction"], errors="coerce")
    available_mito = int((counts.gt(0) & mitochondrial.notna()).sum())
    if available_mito:
        records.append(
            _available_record(
                "relationships.counts-mito.available",
                component,
                "relationship_summary",
                "Positive counts and mitochondrial fraction",
                "available",
                observation_unit,
                evidence_ids,
                metric_id="counts_mitochondrial_fraction",
                statistic="available_count",
                value=available_mito,
            )
        )
    else:
        records.append(
            _unavailable_record(
                "relationships.counts-mito.unavailable",
                component,
                "relationship_summary",
                "Counts and mitochondrial fraction",
                "percent",
                evidence_ids,
                "mitochondrial_metric_unavailable",
                metric_id="counts_mitochondrial_fraction",
            )
        )

    if measurement_spec is not None:
        for metric_id, label, value, unit in (
            (
                "min_detected_genes",
                "Candidate minimum detected genes",
                measurement_spec.exclusion_rules["min_detected_genes"],
                "genes",
            ),
            (
                "max_detected_genes",
                "Candidate maximum detected genes",
                measurement_spec.exclusion_rules["max_detected_genes"],
                "genes",
            ),
            (
                "max_mitochondrial_fraction",
                "Candidate maximum mitochondrial fraction",
                measurement_spec.exclusion_rules["max_mitochondrial_fraction"],
                "fraction",
            ),
        ):
            records.append(
                _available_record(
                    f"relationships.threshold.{metric_id}",
                    component,
                    "relationship_summary",
                    label,
                    "candidate",
                    unit,
                    evidence_ids,
                    metric_id=metric_id,
                    statistic="threshold",
                    value=float(value),
                )
            )
    return records


def _intersection_records(
    flags: pd.DataFrame | None,
    evidence_ids: list[str],
    declared: int,
    observation_unit: str,
    unavailable_reason: str,
) -> list[QCVisualizationRecord]:
    component = "bridge.qc.flag-intersections@0.1.0"
    if flags is None:
        return [
            _unavailable_record(
                "intersections.unavailable",
                component,
                "flag_intersection",
                "Candidate QC-flag intersections",
                observation_unit,
                evidence_ids,
                unavailable_reason,
            )
        ]

    table = flag_intersection_table(flags)
    flag_columns = [column for column in FLAG_LABELS if column in table.columns]
    records = []
    for index, row in table.iterrows():
        labels = [FLAG_LABELS[column] for column in flag_columns if bool(row[column])]
        records.append(
            _available_record(
                f"intersections.combination_{index + 1:03d}",
                component,
                "flag_intersection",
                "; ".join(labels) if labels else "No candidate flag",
                "candidate" if labels else "available",
                observation_unit,
                evidence_ids,
                statistic="combination_count",
                numerator=int(row["count"]),
                denominator=declared,
                denominator_scope="submitted expression object",
            )
        )
    return records


def _view_record(
    record_id: str,
    label: str,
    state: str,
    declared: int,
    observation_unit: str,
    evidence_ids: list[str],
    unavailable_reason: str,
) -> QCVisualizationRecord:
    if state not in {"available", "candidate"}:
        return _unavailable_record(
            record_id,
            "bridge.qc.readiness-flow@0.1.0",
            "view_availability",
            label,
            "availability state",
            evidence_ids,
            unavailable_reason,
        )
    return _available_record(
        record_id,
        "bridge.qc.readiness-flow@0.1.0",
        "view_availability",
        label,
        state,
        observation_unit,
        evidence_ids,
        statistic="available_count",
        numerator=declared,
        denominator=declared,
        denominator_scope="submitted expression object",
    )


def _available_record(
    record_id: str,
    component_ref: str,
    record_type: str,
    label: str,
    state: str,
    unit: str,
    evidence_ids: list[str],
    **values: Any,
) -> QCVisualizationRecord:
    return QCVisualizationRecord(
        record_id=record_id,
        component_ref=component_ref,
        record_type=record_type,
        label=label,
        state=state,
        unit=unit,
        evidence_state=EvidenceState.MEASURED,
        missingness="none",
        applicability="applicable",
        evidence_ids=evidence_ids,
        **values,
    )


def _unavailable_record(
    record_id: str,
    component_ref: str,
    record_type: str,
    label: str,
    unit: str,
    evidence_ids: list[str],
    reason: str,
    **values: Any,
) -> QCVisualizationRecord:
    return QCVisualizationRecord(
        record_id=record_id,
        component_ref=component_ref,
        record_type=record_type,
        label=label,
        state="unavailable",
        unit=unit,
        evidence_state=EvidenceState.UNAVAILABLE,
        missingness="unavailable",
        applicability="not_assessed",
        evidence_ids=evidence_ids,
        missing_reason_codes=[reason],
        **values,
    )


def _render_figures(
    *,
    metrics: pd.DataFrame | None,
    flags: pd.DataFrame | None,
    display_groups: pd.Series | None,
    measurement_spec: MeasurementSpec | None,
    profile: QCReadinessProfileV2,
    staging_run_dir: Path,
    final_run_dir: Path,
    run_id: str,
    observation_unit: str,
    declared: int,
) -> dict[str, ArtifactManifest]:
    all_view_state = str(profile.data_views.get("all_cells_view", {}).get("state", "unavailable"))
    view_states = {
        "All-observation view": all_view_state,
        "Candidate-flag view": "candidate" if flags is not None else "unavailable",
        "Downstream sensitivity results": "unavailable",
    }
    rendered: dict[str, tuple[Path, Path]] = {
        "bridge.qc.readiness-flow@0.1.0": render_analysis_eligibility(
            declared_observations=declared,
            flags=flags,
            view_states=view_states,
            output_stem=staging_run_dir / "qc_observation_retention",
            observation_unit=observation_unit,
            structure_state="eligible",
            count_metrics_state="available" if metrics is not None else "unavailable",
        )
    }
    denominator = f"{declared:,} declared {observation_unit}"
    if metrics is not None and display_groups is not None:
        rendered["bridge.qc.overview@0.2.0"] = render_qc_distributions(
            metrics,
            display_groups,
            staging_run_dir / "qc_capture_distributions",
            observation_unit=observation_unit,
        )
    else:
        rendered["bridge.qc.overview@0.2.0"] = render_unavailable_figure(
            staging_run_dir / "qc_capture_distributions",
            title=_COMPONENT_METADATA["bridge.qc.overview@0.2.0"]["title"],
            reason="A complete caller-declared capture partition and count-level metrics are required.",
            denominator=denominator,
        )

    if metrics is not None:
        rendered["bridge.qc.counts_genes@0.2.0"] = render_qc_relationships(
            metrics,
            staging_run_dir / "qc_metric_relationships",
            flags=flags,
            candidate_rules=measurement_spec.exclusion_rules if measurement_spec else None,
            observation_unit=observation_unit,
        )
    else:
        rendered["bridge.qc.counts_genes@0.2.0"] = render_unavailable_figure(
            staging_run_dir / "qc_metric_relationships",
            title=_COMPONENT_METADATA["bridge.qc.counts_genes@0.2.0"]["title"],
            reason="Count-level per-observation metrics are required.",
            denominator=denominator,
        )

    if flags is not None:
        rendered["bridge.qc.flag-intersections@0.1.0"] = render_qc_flag_intersections(
            flags,
            staging_run_dir / "qc_flag_intersections",
            observation_unit=observation_unit,
        )
    else:
        rendered["bridge.qc.flag-intersections@0.1.0"] = render_unavailable_figure(
            staging_run_dir / "qc_flag_intersections",
            title=_COMPONENT_METADATA["bridge.qc.flag-intersections@0.1.0"]["title"],
            reason="Candidate QC flags require count-level metrics and an applicable MeasurementSpec.",
            denominator=denominator,
        )

    artifacts: dict[str, ArtifactManifest] = {}
    for component_ref, (svg_path, png_path) in rendered.items():
        slug = _COMPONENT_METADATA[component_ref]["slug"]
        evidence_ids = _component_evidence(profile.evidence_ids, component_ref, run_id)
        for suffix, path, media_type in (
            ("svg", svg_path, "image/svg+xml"),
            ("png", png_path, "image/png"),
        ):
            artifacts[f"{component_ref}:{suffix}"] = _manifest(
                artifact_id=f"artifact:{run_id}:qc-{slug}-{suffix}",
                kind=f"qc_visualization_{suffix}",
                source_path=path,
                logical_path=final_run_dir / path.name,
                media_type=media_type,
                evidence_ids=evidence_ids,
            )
    return artifacts


def _visualization_contract(
    *,
    component_ref: str,
    records: list[QCVisualizationRecord],
    data_artifact: ArtifactManifest,
    table_artifact: ArtifactManifest,
    svg_artifact: ArtifactManifest,
    png_artifact: ArtifactManifest,
    run_id: str,
    tool_version: str,
    observation_unit: str,
    declared: int,
    data_hash: str,
) -> VisualizationArtifactV2:
    component_id, component_version = component_ref.rsplit("@", 1)
    metadata = _COMPONENT_METADATA[component_ref]
    uses_denominator = bool(metadata["denominator"])
    evidence_ids = sorted({item for record in records for item in record.evidence_ids})
    evidence_states = sorted({record.evidence_state for record in records}, key=str)
    reason_codes = sorted({item for record in records for item in record.missing_reason_codes})
    applicability_states = {record.applicability for record in records}
    if applicability_states == {"applicable"}:
        applicability = "applicable"
    elif "applicable" in applicability_states:
        applicability = "partially_applicable"
    else:
        applicability = "not_assessed"
    config_hash = hashlib.sha256(
        canonical_json_bytes({"component_ref": component_ref, **_EXPORT_PROFILE})
    ).hexdigest()
    takeaway, description = _component_text(component_ref, records, declared, observation_unit)
    binding_kwargs: dict[str, Any] = {"value_field": "value"}
    denominator_kwargs: dict[str, Any] = {
        "denominator_label": None,
        "denominator_scope": None,
    }
    if uses_denominator:
        binding_kwargs = {
            "numerator_field": "numerator",
            "denominator_field": "denominator",
            "denominator_scope_field": "denominator_scope",
        }
        denominator_kwargs = {
            "denominator_label": f"{declared:,} declared {observation_unit}",
            "denominator_scope": "submitted expression object",
        }
    return VisualizationArtifactV2(
        visualization_id=f"visualization:{run_id}:{metadata['slug']}",
        component_id=component_id,
        component_version=component_version,
        data_binding=VisualizationDataBinding(
            artifact_id=data_artifact.artifact_id,
            schema_ref=QC_VISUALIZATION_DATA_SCHEMA_REF,
            object_version="0.1.0",
            sha256=data_hash,
            records_path="records",
            record_lookup_key="record_id",
            evidence_ids_field="evidence_ids",
            unit_field="unit",
            evidence_state_field="evidence_state",
            scientific_status_field="scientific_status",
            missingness_field="missingness",
            applicability_field="applicability",
            **binding_kwargs,
        ),
        producer_tool_id="P0-01",
        producer_tool_version=tool_version,
        producer_run_ref=f"run:{run_id}",
        evidence_ids=evidence_ids,
        evidence_states=evidence_states,
        scientific_status="candidate",
        applicability=applicability,
        missing_reason_codes=reason_codes,
        unit=str(metadata["unit"]),
        insight_title=str(metadata["title"]),
        takeaway=takeaway,
        limitations=[
            "Candidate QC flags have not been manually reviewed and do not remove observations.",
            "Technical QC measurements do not establish biological identity, product quality, safety or potency.",
        ],
        accessibility=VisualizationAccessibility(
            alt_text=str(metadata["title"]),
            long_description=description,
            table_artifact_id=table_artifact.artifact_id,
            data_sha256=data_hash,
        ),
        renders=[
            VisualizationRenderBinding(
                artifact_id=artifact.artifact_id,
                media_type=media_type,
                renderer_id=str(_EXPORT_PROFILE["renderer_id"]),
                renderer_version=matplotlib.__version__,
                export_profile_id=str(_EXPORT_PROFILE["export_profile_id"]),
                data_sha256=data_hash,
                config_sha256=config_hash,
            )
            for artifact, media_type in (
                (svg_artifact, "image/svg+xml"),
                (png_artifact, "image/png"),
            )
        ],
        **denominator_kwargs,
    )


def _component_text(
    component_ref: str,
    records: list[QCVisualizationRecord],
    declared: int,
    observation_unit: str,
) -> tuple[str, str]:
    unavailable = all(record.evidence_state is EvidenceState.UNAVAILABLE for record in records)
    title = str(_COMPONENT_METADATA[component_ref]["title"])
    if unavailable:
        takeaway = f"{title} is unavailable because its required technical input was not supplied."
    elif component_ref == "bridge.qc.readiness-flow@0.1.0":
        candidate = next(
            (record.numerator for record in records if record.record_id == "eligibility.candidate-eligible"),
            None,
        )
        review = next(
            (record.numerator for record in records if record.record_id == "eligibility.flagged-review"),
            None,
        )
        if candidate is None:
            takeaway = f"{declared:,} {observation_unit} were retained; candidate QC status is unavailable."
        else:
            takeaway = (
                f"All {declared:,} {observation_unit} were retained; {candidate:,} are candidate-eligible "
                f"and {review:,} carry one or more review flags."
            )
    elif component_ref == "bridge.qc.overview@0.2.0":
        captures = {record.capture_id for record in records if record.capture_id}
        takeaway = f"Five QC measurements are shown separately across {len(captures)} caller-declared capture(s)."
    elif component_ref == "bridge.qc.counts_genes@0.2.0":
        takeaway = "Observation density and candidate thresholds are shown without applying a hard filter."
    else:
        combinations = sum(record.record_type == "flag_intersection" for record in records)
        takeaway = f"{combinations} mutually exclusive non-zero candidate-flag combination(s) are reported."
    description = (
        f"{title}. The denominator is {declared:,} declared {observation_unit}. "
        f"{takeaway} Missing technical evidence is displayed as unavailable rather than zero."
    )
    return takeaway, description


def _write_record_table(path: Path, records: list[QCVisualizationRecord]) -> None:
    payloads = [record.model_dump(mode="json") for record in records]
    table = pd.DataFrame(payloads)
    for column in ("evidence_ids", "missing_reason_codes"):
        table[column] = table[column].map(
            lambda value: json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        )
    table.to_csv(
        path,
        sep="\t",
        index=False,
        lineterminator="\n",
        float_format="%.12g",
    )


def _manifest(
    *,
    artifact_id: str,
    kind: str,
    source_path: Path,
    logical_path: Path,
    media_type: str,
    evidence_ids: list[str],
) -> ArtifactManifest:
    return ArtifactManifest(
        artifact_id=artifact_id,
        kind=kind,
        path=logical_path.resolve(),
        media_type=media_type,
        sha256=sha256_path(source_path),
        evidence_ids=evidence_ids,
    )


def _candidate_unavailable_reason(profile: QCReadinessProfileV2) -> str:
    missing = set(profile.missing_inputs)
    if "measurement_spec_not_selected" in missing:
        return "measurement_spec_not_selected"
    if any(item.startswith("required_gene_set_unavailable") for item in missing):
        return "required_qc_gene_set_unavailable"
    return "candidate_qc_flags_unavailable"


def _component_evidence(
    profile_evidence_ids: list[str],
    component_ref: str,
    run_id: str,
) -> list[str]:
    evidence = [f"evidence:{run_id}:structure"]
    if component_ref != "bridge.qc.readiness-flow@0.1.0":
        evidence.append(f"evidence:{run_id}:count-metrics")
    if component_ref == "bridge.qc.flag-intersections@0.1.0":
        evidence.append(f"evidence:{run_id}:candidate-flags")
    return sorted(set(evidence).intersection(profile_evidence_ids) or {profile_evidence_ids[0]})
