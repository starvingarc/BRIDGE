from __future__ import annotations

import importlib
import json
import math
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from bridge.tool_packages._configurable_contracts import (
    BiologicalUnitAssignmentArtifact,
    observation_ids_sha256,
)
from bridge.tool_packages.p0_01_input_qc.io import InputAuditError, sha256_path
from bridge.tool_packages.p0_02_cell_state.metrics import source_support
from bridge.tool_packages.p0_02_cell_state.reference import load_reference_profile
from bridge.tool_packages.p0_04_developmental_compatibility.method_models import (
    DevelopmentBootstrapInterval,
    DevelopmentMethodBundle,
    DevelopmentMethodEvidence,
    DevelopmentMethodId,
    DevelopmentMethodSpec,
    DevelopmentProgramActivity,
    DevelopmentTimeTrend,
    MethodExecutionState,
    OrdinalGroupHeldoutEvidence,
    OrdinalStagePrediction,
    ReferenceStageSupportRecord,
    TimeTrendPoint,
)
from bridge.tool_packages.p0_04_developmental_compatibility.roles import (
    DevelopmentStageRole,
)
from bridge.toolkit.contracts import (
    InputAsset,
    MarkerProgramCard,
    ReferenceManifest,
    ReferenceProfile,
    ScoreState,
)


class DevelopmentMethodError(RuntimeError):
    def __init__(self, reason_code: str, detail: str | None = None) -> None:
        self.reason_code = reason_code
        super().__init__(f"{reason_code}: {detail}" if detail else reason_code)


@dataclass(frozen=True)
class _QuerySummary:
    matrix: np.ndarray
    genes: np.ndarray
    analysis_unit_refs: np.ndarray
    independence_by_analysis_unit: dict[str, str]
    n_observations: int
    observation_ids_sha256: str


@dataclass(frozen=True)
class _ReferenceRun:
    profile: ReferenceProfile
    matrix: np.ndarray
    metadata: dict[str, Any]
    shared_genes: int


@dataclass(frozen=True)
class _MethodOutputs:
    reference_support: list[ReferenceStageSupportRecord]
    within_window_support: dict[str, float]
    ordinal_predictions: list[OrdinalStagePrediction]
    program_activity: list[DevelopmentProgramActivity]
    bootstrap_intervals: list[DevelopmentBootstrapInterval]
    time_trends: list[DevelopmentTimeTrend]
    method_reasons: dict[DevelopmentMethodId, set[str]]


def run_development_methods(
    *,
    run_id: str,
    tool_version: str,
    asset: InputAsset,
    asset_sha256: str,
    method_spec: DevelopmentMethodSpec,
    reference_manifest: ReferenceManifest,
    biological_unit_assignment: BiologicalUnitAssignmentArtifact,
    reference_manifest_path: Path,
    random_seed: int,
    expected_n_observations: int,
    expected_observation_ids_sha256: str,
) -> DevelopmentMethodBundle:
    query = _load_query_pseudobulk(asset, method_spec, biological_unit_assignment)
    if query.n_observations != expected_n_observations:
        raise DevelopmentMethodError("expression_view_observation_count_mismatch")
    if query.observation_ids_sha256 != expected_observation_ids_sha256:
        raise DevelopmentMethodError("expression_view_observation_identity_mismatch")

    profiles = _resolve_profiles(reference_manifest, method_spec.reference_profile_ids)
    root = reference_manifest_path.parent
    references = [_load_checked_profile(root, profile, query) for profile in profiles]
    stage_by_profile_label = {
        (item.profile_id, item.label): item for item in method_spec.reference_stages
    }
    for reference in references:
        labels = {str(row["label"]).strip() for row in reference.metadata["rows"]}
        if any(
            (reference.profile.profile_id, label) not in stage_by_profile_label
            for label in labels
        ):
            raise DevelopmentMethodError("reference_stage_definition_missing")

    selected = set(method_spec.selected_method_ids)
    reasons = {method_id: set() for method_id in selected}
    support: list[ReferenceStageSupportRecord] = []
    within_support: dict[str, float] = {}
    reference_consumers = {
        DevelopmentMethodId.PSEUDOBULK_CORRELATION,
        DevelopmentMethodId.SAMPLE_BOOTSTRAP,
        DevelopmentMethodId.TIME_GAM_PY,
    }
    if selected & reference_consumers:
        support, within_support = _reference_support(
            query=query,
            references=references,
            stage_by_profile_label=stage_by_profile_label,
            minimum_shared_genes=method_spec.minimum_shared_genes,
        )
        available_support = [
            item for item in support if item.evidence_state == "shadow"
        ]
        if not available_support:
            for method_id in selected & reference_consumers:
                reasons[method_id].add("reference_stage_support_unavailable")
        elif len(available_support) < len(support):
            for method_id in selected & reference_consumers:
                reasons[method_id].add("reference_stage_support_incomplete")

    ordinal: list[OrdinalStagePrediction] = []
    if DevelopmentMethodId.ORDINAL_CLASSIFIER in selected:
        gate_reason = _ordinal_gate_reason(method_spec, profiles)
        if gate_reason is not None:
            reasons[DevelopmentMethodId.ORDINAL_CLASSIFIER].add(gate_reason)
        else:
            ordinal, reason = _ordinal_predictions(
                query=query,
                references=references,
                stage_by_profile_label=stage_by_profile_label,
                minimum_shared_genes=method_spec.minimum_shared_genes,
                heldout_evidence=method_spec.ordinal_group_heldout_evidence,
            )
            if reason:
                reasons[DevelopmentMethodId.ORDINAL_CLASSIFIER].add(reason)

    programs: list[DevelopmentProgramActivity] = []
    unavailable_cards: set[str] = set()
    if selected & {
        DevelopmentMethodId.PROGRAM_ACTIVITY,
        DevelopmentMethodId.TIME_PROGRAM,
    }:
        programs, unavailable_cards = _program_activity(
            root=root,
            manifest=reference_manifest,
            query=query,
            spec=method_spec,
        )
        if unavailable_cards:
            for method_id in selected & {
                DevelopmentMethodId.PROGRAM_ACTIVITY,
                DevelopmentMethodId.TIME_PROGRAM,
            }:
                reasons[method_id].add("stage_program_coverage_insufficient")

    intervals: list[DevelopmentBootstrapInterval] = []
    if DevelopmentMethodId.SAMPLE_BOOTSTRAP in selected:
        intervals, reason = _bootstrap_within_window_support(
            values_by_analysis_unit=within_support,
            independence_by_analysis_unit=query.independence_by_analysis_unit,
            replicates=method_spec.bootstrap_replicates,
            confidence_level=method_spec.bootstrap_confidence_level,
            random_seed=random_seed,
        )
        if reason:
            reasons[DevelopmentMethodId.SAMPLE_BOOTSTRAP].add(reason)

    trends: list[DevelopmentTimeTrend] = []
    if DevelopmentMethodId.TIME_GAM_PY in selected:
        trend, reason = _time_trend(
            metric_name="within_window_reference_support",
            card_id=None,
            values_by_analysis_unit=within_support,
            spec=method_spec,
            independence_by_analysis_unit=query.independence_by_analysis_unit,
        )
        if trend is not None:
            trends.append(trend)
        if reason:
            reasons[DevelopmentMethodId.TIME_GAM_PY].add(reason)
    if DevelopmentMethodId.TIME_PROGRAM in selected:
        by_card: dict[str, dict[str, float]] = {}
        for record in programs:
            by_card.setdefault(record.card_id, {})[record.analysis_unit_ref] = (
                record.activity
            )
        for card_id in sorted(method_spec.program_card_ids):
            trend, reason = _time_trend(
                metric_name="stage_program_activity",
                card_id=card_id,
                values_by_analysis_unit=by_card.get(card_id, {}),
                spec=method_spec,
                independence_by_analysis_unit=query.independence_by_analysis_unit,
            )
            if trend is not None:
                trends.append(trend)
            if reason:
                reasons[DevelopmentMethodId.TIME_PROGRAM].add(reason)

    outputs = _MethodOutputs(
        reference_support=support,
        within_window_support=within_support,
        ordinal_predictions=ordinal,
        program_activity=programs,
        bootstrap_intervals=intervals,
        time_trends=trends,
        method_reasons=reasons,
    )
    evidence = _method_evidence(method_spec, query, outputs)
    score_state = (
        ScoreState.SHADOW
        if any(
            item.execution_state
            in {MethodExecutionState.SUCCEEDED, MethodExecutionState.PARTIAL}
            for item in evidence
        )
        else ScoreState.UNAVAILABLE
    )
    return DevelopmentMethodBundle(
        object_version="0.1.0",
        bundle_id=f"development-method-bundle:{run_id.removeprefix('run-')}",
        tool_id="P0-04",
        tool_version=tool_version,
        method_spec_ref=method_spec.ref,
        expression_asset_id=asset.asset_id,
        expression_asset_sha256=asset_sha256,
        reference_manifest_ref={
            "object_id": reference_manifest.snapshot_id,
            "object_version": reference_manifest.version,
        },
        analysis_unit_refs=sorted(query.analysis_unit_refs.tolist()),
        independence_group_refs=sorted(
            set(query.independence_by_analysis_unit.values())
        ),
        n_observations=query.n_observations,
        n_genes=len(query.genes),
        method_evidence=evidence,
        reference_stage_support=support,
        ordinal_stage_predictions=ordinal,
        program_activity=programs,
        bootstrap_intervals=intervals,
        time_trends=trends,
        domain_score=None,
        score_state=score_state,
    )


def _load_query_pseudobulk(
    asset: InputAsset,
    spec: DevelopmentMethodSpec,
    assignment_artifact: BiologicalUnitAssignmentArtifact,
) -> _QuerySummary:
    anndata = _require_module("anndata")
    try:
        adata = anndata.read_h5ad(asset.path, backed="r")
    except (OSError, ValueError) as exc:
        raise DevelopmentMethodError("expression_asset_unreadable", str(exc)) from exc
    try:
        if spec.observation_id_column is None:
            observation_values = pd.Index(adata.obs_names).astype(str)
        else:
            if spec.observation_id_column not in adata.obs:
                raise DevelopmentMethodError(
                    "observation_id_column_missing", spec.observation_id_column
                )
            values = adata.obs[spec.observation_id_column]
            if values.isna().any():
                raise DevelopmentMethodError("observation_id_values_missing")
            observation_values = pd.Index(values.astype(str))
        observation_ids = [value.strip() for value in observation_values]
        if any(not value for value in observation_ids):
            raise DevelopmentMethodError("observation_id_values_missing")
        if len(observation_ids) != len(set(observation_ids)):
            raise DevelopmentMethodError("observation_ids_not_unique")

        assignment_by_observation = {
            item.observation_id: item for item in assignment_artifact.assignments
        }
        if set(observation_ids) != set(assignment_by_observation):
            raise DevelopmentMethodError(
                "expression_view_biological_unit_assignment_mismatch"
            )
        analysis_values = np.asarray(
            [
                assignment_by_observation[observation_id].analysis_unit_ref
                for observation_id in observation_ids
            ]
        )
        independence_by_analysis_unit: dict[str, str] = {}
        for item in assignment_artifact.assignments:
            previous = independence_by_analysis_unit.setdefault(
                item.analysis_unit_ref, item.independence_group_ref
            )
            if previous != item.independence_group_ref:
                raise DevelopmentMethodError(
                    "analysis_unit_independence_group_mismatch"
                )

        if spec.gene_symbol_column is None:
            gene_values = pd.Index(adata.var_names).astype(str)
        else:
            if spec.gene_symbol_column not in adata.var:
                raise DevelopmentMethodError(
                    "gene_symbol_column_missing", spec.gene_symbol_column
                )
            values = adata.var[spec.gene_symbol_column]
            if values.isna().any():
                raise DevelopmentMethodError("gene_symbol_values_missing")
            gene_values = pd.Index(values.astype(str))
        genes = np.asarray([value.strip().upper() for value in gene_values])
        if np.any(genes == ""):
            raise DevelopmentMethodError("gene_symbol_values_missing")
        if len(genes) != len(set(genes)):
            raise DevelopmentMethodError("gene_symbols_not_unique")

        matrix = adata.X
        if asset.matrix_location and asset.matrix_location != "X":
            prefix = "layers/"
            if not asset.matrix_location.startswith(prefix):
                raise DevelopmentMethodError("unsupported_matrix_location")
            layer = asset.matrix_location.removeprefix(prefix)
            if layer not in adata.layers:
                raise DevelopmentMethodError("matrix_layer_not_found", layer)
            matrix = adata.layers[layer]

        analysis_unit_refs = np.asarray(sorted(set(analysis_values)))
        pseudobulk = np.zeros((len(analysis_unit_refs), adata.n_vars), dtype=np.float64)
        for row, analysis_unit_ref in enumerate(analysis_unit_refs):
            indices = np.flatnonzero(analysis_values == analysis_unit_ref)
            total = np.zeros(adata.n_vars, dtype=np.float64)
            for start in range(0, len(indices), 512):
                block = matrix[indices[start : start + 512], :]
                values = (
                    block.toarray() if sparse.issparse(block) else np.asarray(block)
                )
                if not np.isfinite(values).all():
                    raise DevelopmentMethodError("expression_matrix_nonfinite")
                total += values.sum(axis=0, dtype=np.float64)
            pseudobulk[row] = total / len(indices)
        return _QuerySummary(
            matrix=pseudobulk,
            genes=genes,
            analysis_unit_refs=analysis_unit_refs,
            independence_by_analysis_unit=independence_by_analysis_unit,
            n_observations=adata.n_obs,
            observation_ids_sha256=observation_ids_sha256(observation_ids),
        )
    finally:
        if getattr(adata, "file", None) is not None:
            adata.file.close()


def _resolve_profiles(
    manifest: ReferenceManifest, profile_ids: list[str]
) -> list[ReferenceProfile]:
    by_id = {profile.profile_id: profile for profile in manifest.profiles}
    missing = sorted(set(profile_ids) - set(by_id))
    if missing:
        raise DevelopmentMethodError("reference_profile_not_found", ",".join(missing))
    profiles = [by_id[profile_id] for profile_id in sorted(profile_ids)]
    if any(
        not profile.matrix_file or not profile.metadata_file for profile in profiles
    ):
        raise DevelopmentMethodError("reference_profile_artifact_unavailable")
    return profiles


def _load_checked_profile(
    root: Path,
    profile: ReferenceProfile,
    query: _QuerySummary,
) -> _ReferenceRun:
    _check_snapshot_artifact(root, profile.matrix_file, profile.matrix_sha256)
    _check_snapshot_artifact(root, profile.metadata_file, profile.metadata_sha256)
    try:
        matrix, metadata = load_reference_profile(root, profile)
        reference_genes = np.asarray(
            [str(gene).strip().upper() for gene in metadata["genes"]]
        )
        rows = metadata["rows"]
        labels = [str(row["label"]).strip() for row in rows]
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise DevelopmentMethodError(
            "reference_profile_invalid", profile.profile_id
        ) from exc
    if matrix.ndim != 2 or matrix.shape != (len(rows), len(reference_genes)):
        raise DevelopmentMethodError(
            "reference_profile_shape_mismatch", profile.profile_id
        )
    if not np.issubdtype(matrix.dtype, np.number) or not np.isfinite(matrix).all():
        raise DevelopmentMethodError(
            "reference_profile_matrix_invalid", profile.profile_id
        )
    if (
        np.any(reference_genes == "")
        or len(reference_genes) != len(set(reference_genes))
        or any(not label for label in labels)
    ):
        raise DevelopmentMethodError(
            "reference_profile_metadata_invalid", profile.profile_id
        )
    if profile.n_genes and profile.n_genes != len(reference_genes):
        raise DevelopmentMethodError(
            "reference_profile_metadata_mismatch", profile.profile_id
        )
    if profile.labels and set(profile.labels) != set(labels):
        raise DevelopmentMethodError(
            "reference_profile_metadata_mismatch", profile.profile_id
        )
    return _ReferenceRun(
        profile=profile,
        matrix=matrix,
        metadata={**metadata, "genes": reference_genes.tolist()},
        shared_genes=len(set(query.genes).intersection(reference_genes)),
    )


def _check_snapshot_artifact(
    root: Path, relative_name: str | None, expected_sha256: str | None
) -> Path:
    if not relative_name or not expected_sha256:
        raise DevelopmentMethodError("reference_profile_artifact_unavailable")
    path = root / relative_name
    try:
        actual = sha256_path(path)
    except (OSError, InputAuditError) as exc:
        raise DevelopmentMethodError(
            "reference_artifact_unreadable", relative_name
        ) from exc
    if actual != expected_sha256:
        raise DevelopmentMethodError(
            "reference_artifact_checksum_mismatch", relative_name
        )
    return path


def _reference_support(
    *,
    query: _QuerySummary,
    references: list[_ReferenceRun],
    stage_by_profile_label: dict[tuple[str, str], Any],
    minimum_shared_genes: int,
) -> tuple[list[ReferenceStageSupportRecord], dict[str, float]]:
    records: list[ReferenceStageSupportRecord] = []
    within_values: dict[str, list[float]] = {
        str(unit): [] for unit in query.analysis_unit_refs
    }
    for reference in references:
        long, summary, coverage = source_support(
            query.matrix,
            query.genes,
            reference.matrix,
            reference.metadata,
            query.analysis_unit_refs,
            minimum_shared_genes=minimum_shared_genes,
            workers=1,
        )
        if summary.empty:
            records.extend(
                ReferenceStageSupportRecord(
                    analysis_unit_ref=str(unit),
                    profile_id=reference.profile.profile_id,
                    profile_source_id=reference.profile.source_id,
                    profile_assay=reference.profile.assay,
                    shared_genes=int(coverage["shared_genes"]),
                    evidence_state="unavailable",
                    reason_codes=["shared_gene_coverage_insufficient"],
                )
                for unit in query.analysis_unit_refs
            )
            continue
        within_labels = {
            item.label
            for key, item in stage_by_profile_label.items()
            if key[0] == reference.profile.profile_id
            and item.stage_role is DevelopmentStageRole.WITHIN_WINDOW
        }
        within_frame = long[long["label"].isin(within_labels)]
        for unit, group in within_frame.groupby("observation_id", sort=True):
            finite = group["spearman_support"].dropna()
            if not finite.empty:
                within_values[str(unit)].append(float(finite.max()))
        for row in summary.to_dict(orient="records"):
            top_label = _optional_text(row["top_label"])
            definition = (
                None
                if top_label is None
                else stage_by_profile_label[
                    (reference.profile.profile_id, top_label)
                ]
            )
            records.append(
                ReferenceStageSupportRecord(
                    analysis_unit_ref=str(row["observation_id"]),
                    profile_id=reference.profile.profile_id,
                    profile_source_id=reference.profile.source_id,
                    profile_assay=reference.profile.assay,
                    top_label=top_label,
                    top_stage_role=(
                        None if definition is None else definition.stage_role
                    ),
                    top_ordinal_rank=(
                        None if definition is None else definition.ordinal_rank
                    ),
                    top_spearman_support=_bounded_float(
                        row["top_spearman_support"], -1.0, 1.0
                    ),
                    runner_up_label=_optional_text(row["runner_up_label"]),
                    margin=_bounded_float(row["margin"], 0.0, 2.0),
                    top_cosine_support=_bounded_float(
                        row["top_cosine_support"], -1.0, 1.0
                    ),
                    shared_genes=int(coverage["shared_genes"]),
                    evidence_state="shadow",
                )
            )
    for unit in query.analysis_unit_refs:
        unit_ref = str(unit)
        indices = [
            index
            for index, record in enumerate(records)
            if record.analysis_unit_ref == unit_ref
        ]
        unit_records = [records[index] for index in indices]
        unavailable_reason: str | None = None
        if len(unit_records) != len(references) or any(
            record.evidence_state == "unavailable" for record in unit_records
        ):
            unavailable_reason = "reference_stage_profile_coverage_incomplete"
        elif any(record.top_stage_role is None for record in unit_records):
            unavailable_reason = "reference_stage_role_unavailable"
        elif len({record.top_stage_role for record in unit_records}) > 1:
            unavailable_reason = "reference_stage_source_assay_disagreement"
        if unavailable_reason is None:
            continue
        for index in indices:
            record = records[index]
            records[index] = record.model_copy(
                update={
                    "evidence_state": "unavailable",
                    "reason_codes": sorted(
                        {*record.reason_codes, unavailable_reason}
                    ),
                }
            )
        within_values[unit_ref] = []
    return records, {
        unit: float(np.mean(values))
        for unit, values in sorted(within_values.items())
        if values
    }


def _ordinal_gate_reason(
    spec: DevelopmentMethodSpec, profiles: list[ReferenceProfile]
) -> str | None:
    evidence = spec.ordinal_group_heldout_evidence
    if evidence is None:
        return "ordinal_group_heldout_evidence_not_supplied"
    if evidence.review_state != "reviewed":
        return "ordinal_group_heldout_evidence_not_reviewed"
    if evidence.validation_state != "passed":
        return "ordinal_group_heldout_evidence_not_passed"
    profile_ids = {profile.profile_id for profile in profiles}
    if set(evidence.reference_profile_ids) != profile_ids:
        return "ordinal_group_heldout_profile_binding_mismatch"
    source_ids = {profile.source_id for profile in profiles}
    if len(source_ids) < 2:
        return "ordinal_group_heldout_requires_two_sources"
    if set(evidence.held_out_source_ids) != source_ids:
        return "ordinal_group_heldout_source_binding_mismatch"
    return None


def _ordinal_predictions(
    *,
    query: _QuerySummary,
    references: list[_ReferenceRun],
    stage_by_profile_label: dict[tuple[str, str], Any],
    minimum_shared_genes: int,
    heldout_evidence: OrdinalGroupHeldoutEvidence,
) -> tuple[list[OrdinalStagePrediction], str | None]:
    if not references:
        return [], "reference_profiles_not_supplied"
    shared = set(query.genes)
    for reference in references:
        shared.intersection_update(reference.metadata["genes"])
    shared_genes = sorted(shared)
    if len(shared_genes) < minimum_shared_genes:
        return [], "ordinal_shared_gene_coverage_insufficient"

    query_index = {gene: index for index, gene in enumerate(query.genes)}
    q_indices = np.asarray([query_index[gene] for gene in shared_genes])
    reference_rows: list[np.ndarray] = []
    ranks: list[int] = []
    sources: set[str] = set()
    labels_by_rank: dict[int, set[tuple[str, DevelopmentStageRole]]] = {}
    for reference in references:
        ref_index = {
            gene: index
            for index, gene in enumerate(reference.metadata["genes"])
        }
        r_indices = np.asarray([ref_index[gene] for gene in shared_genes])
        for row_values, metadata in zip(
            reference.matrix[:, r_indices],
            reference.metadata["rows"],
            strict=True,
        ):
            label = str(metadata["label"]).strip()
            definition = stage_by_profile_label[
                (reference.profile.profile_id, label)
            ]
            reference_rows.append(np.asarray(row_values, dtype=float))
            ranks.append(definition.ordinal_rank)
            labels_by_rank.setdefault(definition.ordinal_rank, set()).add(
                (label, definition.stage_role)
            )
            sources.add(reference.profile.source_id)

    unique_ranks = sorted(set(ranks))
    if len(unique_ranks) < 2:
        return [], "ordinal_reference_requires_two_ranks"
    role_by_rank: dict[int, DevelopmentStageRole] = {}
    label_by_rank: dict[int, str] = {}
    for rank, labels_and_roles in labels_by_rank.items():
        roles = {item[1] for item in labels_and_roles}
        if len(roles) != 1:
            raise DevelopmentMethodError("ordinal_rank_role_conflict")
        role_by_rank[rank] = next(iter(roles))
        label_by_rank[rank] = sorted(item[0] for item in labels_and_roles)[0]

    x_reference = np.vstack(reference_rows)
    x_query = query.matrix[:, q_indices]
    y = np.asarray(ranks)
    cumulative: list[np.ndarray] = []
    try:
        for threshold in unique_ranks[:-1]:
            binary = (y > threshold).astype(int)
            if len(set(binary)) < 2:
                return [], "ordinal_reference_class_degenerate"
            model = make_pipeline(
                StandardScaler(),
                LogisticRegression(
                    class_weight="balanced",
                    max_iter=1000,
                    random_state=0,
                    solver="liblinear",
                ),
            )
            model.fit(x_reference, binary)
            cumulative.append(model.predict_proba(x_query)[:, 1])
    except (ValueError, FloatingPointError):
        return [], "ordinal_classifier_not_estimable"

    cumulative_matrix = np.minimum.accumulate(np.vstack(cumulative), axis=0)
    probabilities = np.vstack(
        [
            1.0 - cumulative_matrix[0],
            *(
                cumulative_matrix[index] - cumulative_matrix[index + 1]
                for index in range(len(cumulative_matrix) - 1)
            ),
            cumulative_matrix[-1],
        ]
    ).T
    probabilities = np.clip(probabilities, 0.0, 1.0)
    probabilities /= probabilities.sum(axis=1, keepdims=True)

    predictions: list[OrdinalStagePrediction] = []
    rank_array = np.asarray(unique_ranks, dtype=float)
    for unit, row in zip(query.analysis_unit_refs, probabilities, strict=True):
        expected = float(row @ rank_array)
        nearest_rank = min(unique_ranks, key=lambda value: (abs(value - expected), value))
        predictions.append(
            OrdinalStagePrediction(
                analysis_unit_ref=str(unit),
                expected_ordinal_rank=expected,
                nearest_label=label_by_rank[nearest_rank],
                nearest_stage_role=role_by_rank[nearest_rank],
                rank_probabilities={
                    str(rank): float(probability)
                    for rank, probability in zip(unique_ranks, row, strict=True)
                },
                calibration_state="uncalibrated_baseline",
                group_heldout_evidence_ref=heldout_evidence.ref,
                n_reference_rows=len(reference_rows),
                n_reference_sources=len(sources),
            )
        )
    return predictions, None


def _program_activity(
    *,
    root: Path,
    manifest: ReferenceManifest,
    query: _QuerySummary,
    spec: DevelopmentMethodSpec,
) -> tuple[list[DevelopmentProgramActivity], set[str]]:
    marker_path = _check_snapshot_artifact(
        root, manifest.marker_program_file, manifest.marker_program_sha256
    )
    try:
        payload = json.loads(marker_path.read_text(encoding="utf-8"))
        cards = {
            card.card_id: card
            for card in (
                MarkerProgramCard.model_validate(item) for item in payload["cards"]
            )
        }
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise DevelopmentMethodError("marker_program_registry_invalid") from exc
    missing = sorted(set(spec.program_card_ids) - set(cards))
    if missing:
        raise DevelopmentMethodError("program_card_not_found", ",".join(missing))
    not_allowed = sorted(
        card_id
        for card_id in spec.program_card_ids
        if "shadow_evidence" not in cards[card_id].allowed_use
    )
    if not_allowed:
        raise DevelopmentMethodError(
            "program_card_use_not_allowed", ",".join(not_allowed)
        )

    gene_set = set(query.genes)
    coverage: dict[str, tuple[int, int]] = {}
    network_rows: list[dict[str, str | float]] = []
    unavailable: set[str] = set()
    for card_id in sorted(spec.program_card_ids):
        card = cards[card_id]
        positive = sorted(
            {gene.upper() for gene in card.positive_markers}.intersection(gene_set)
        )
        negative = sorted(
            {gene.upper() for gene in card.negative_markers}.intersection(gene_set)
        )
        coverage[card_id] = (len(positive), len(negative))
        if len(positive) < spec.minimum_program_genes:
            unavailable.add(card_id)
            continue
        network_rows.extend(
            {"source": card_id, "target": gene, "weight": weight}
            for gene, weight in [
                *((gene, 1.0) for gene in positive),
                *((gene, -1.0) for gene in negative),
            ]
        )
    if not network_rows:
        return [], unavailable

    decoupler = _require_module("decoupler")
    expression = pd.DataFrame(
        query.matrix, index=query.analysis_unit_refs, columns=query.genes
    )
    network = pd.DataFrame(network_rows)
    try:
        activities, p_values = decoupler.mt.ulm(
            expression,
            network,
            tmin=spec.minimum_program_genes,
            raw=False,
            verbose=False,
        )
    except Exception as exc:
        raise DevelopmentMethodError("decoupler_execution_failed", str(exc)) from exc

    records: list[DevelopmentProgramActivity] = []
    for card_id in sorted(spec.program_card_ids):
        if card_id not in activities.columns:
            unavailable.add(card_id)
            continue
        card = cards[card_id]
        positive_count, negative_count = coverage[card_id]
        for unit in query.analysis_unit_refs:
            activity = float(activities.loc[unit, card_id])
            if not math.isfinite(activity):
                unavailable.add(card_id)
                continue
            p_value = float(p_values.loc[unit, card_id])
            records.append(
                DevelopmentProgramActivity(
                    analysis_unit_ref=str(unit),
                    card_id=card_id,
                    state_id=card.state_id,
                    activity=activity,
                    p_value=p_value if math.isfinite(p_value) else None,
                    observed_positive_markers=positive_count,
                    observed_negative_markers=negative_count,
                )
            )
    return records, unavailable


def _bootstrap_within_window_support(
    *,
    values_by_analysis_unit: dict[str, float],
    independence_by_analysis_unit: dict[str, str],
    replicates: int,
    confidence_level: float,
    random_seed: int,
) -> tuple[list[DevelopmentBootstrapInterval], str | None]:
    if not values_by_analysis_unit:
        return [], "within_window_reference_support_unavailable"
    frame = pd.DataFrame(
        {
            "analysis_unit_ref": list(values_by_analysis_unit),
            "value": list(values_by_analysis_unit.values()),
        }
    )
    frame["independence_group_ref"] = frame["analysis_unit_ref"].map(
        independence_by_analysis_unit
    )
    if frame["independence_group_ref"].isna().any():
        raise DevelopmentMethodError("independence_group_binding_missing")
    values = (
        frame.groupby("independence_group_ref", sort=True)["value"]
        .mean()
        .to_numpy()
    )
    estimate = float(values.mean())
    if len(values) == 1:
        return [
            DevelopmentBootstrapInterval(
                metric_name="within_window_reference_support",
                estimate=estimate,
                n_independence_groups=1,
                replicates=0,
                interval_state="descriptive_only",
            )
        ], "one_independence_group_descriptive_only"
    rng = np.random.default_rng(random_seed)
    draws = rng.choice(values, size=(replicates, len(values)), replace=True).mean(
        axis=1
    )
    alpha = (1.0 - confidence_level) / 2.0
    lower, upper = np.quantile(draws, [alpha, 1.0 - alpha])
    return [
        DevelopmentBootstrapInterval(
            metric_name="within_window_reference_support",
            estimate=estimate,
            lower=float(lower),
            upper=float(upper),
            confidence_level=confidence_level,
            n_independence_groups=len(values),
            replicates=replicates,
            interval_state="available",
        )
    ], None


def _time_trend(
    *,
    metric_name: str,
    card_id: str | None,
    values_by_analysis_unit: dict[str, float],
    spec: DevelopmentMethodSpec,
    independence_by_analysis_unit: dict[str, str],
) -> tuple[DevelopmentTimeTrend | None, str | None]:
    time_by_unit = {
        item.analysis_unit_ref: item for item in spec.analysis_unit_timepoints
    }
    missing = sorted(set(values_by_analysis_unit) - set(time_by_unit))
    if missing:
        raise DevelopmentMethodError("analysis_unit_timepoint_binding_missing")
    rows = [
        {
            "analysis_unit_ref": unit,
            "independence_group_ref": independence_by_analysis_unit[unit],
            "timepoint_id": time_by_unit[unit].timepoint_id,
            "timepoint_order": time_by_unit[unit].timepoint_order,
            "timepoint_label": time_by_unit[unit].timepoint_label,
            "value": value,
        }
        for unit, value in sorted(values_by_analysis_unit.items())
    ]
    if not rows:
        return None, "time_metric_unavailable"
    frame = pd.DataFrame(rows)
    if frame["independence_group_ref"].duplicated().any():
        return None, "repeated_independence_group_requires_mixed_model"
    n_timepoints = frame["timepoint_order"].nunique()
    if n_timepoints < 4:
        return None, "four_timepoints_required_for_spline"
    if len(frame) <= spec.spline_degrees_of_freedom + 1:
        return None, "independent_units_insufficient_for_spline"

    patsy = _require_module("patsy")
    statsmodels = _require_module("statsmodels.api")
    try:
        design = patsy.dmatrix(
            (
                "bs(x, df="
                f"{spec.spline_degrees_of_freedom}, "
                "degree=3, include_intercept=False)"
            ),
            {"x": frame["timepoint_order"].to_numpy(dtype=float)},
            return_type="dataframe",
        )
        model = statsmodels.OLS(frame["value"].to_numpy(dtype=float), design).fit()
        unique = (
            frame[
                ["timepoint_id", "timepoint_order", "timepoint_label"]
            ]
            .drop_duplicates()
            .sort_values("timepoint_order")
        )
        prediction_design = patsy.build_design_matrices(
            [design.design_info],
            {"x": unique["timepoint_order"].to_numpy(dtype=float)},
            return_type="dataframe",
        )[0]
        prediction = np.asarray(model.predict(prediction_design), dtype=float)
    except (ValueError, np.linalg.LinAlgError, patsy.PatsyError):
        return None, "time_spline_not_estimable"

    points = [
        TimeTrendPoint(
            timepoint_id=str(row.timepoint_id),
            timepoint_order=int(row.timepoint_order),
            timepoint_label=str(row.timepoint_label),
            fitted_value=float(prediction[index]),
        )
        for index, row in enumerate(unique.itertuples(index=False))
    ]
    if any(
        not math.isfinite(value)
        for point in points
        for value in (point.fitted_value,)
    ):
        return None, "time_spline_nonfinite"
    return DevelopmentTimeTrend(
        metric_name=metric_name,
        card_id=card_id,
        n_analysis_units=len(frame),
        n_independence_groups=frame["independence_group_ref"].nunique(),
        n_timepoints=n_timepoints,
        spline_degrees_of_freedom=spec.spline_degrees_of_freedom,
        analysis_state="unadjusted_descriptive",
        fitted_points=points,
    ), None


def _method_evidence(
    spec: DevelopmentMethodSpec,
    query: _QuerySummary,
    outputs: _MethodOutputs,
) -> list[DevelopmentMethodEvidence]:
    implementations = {
        DevelopmentMethodId.PSEUDOBULK_CORRELATION: (
            "BRIDGE sample-pseudobulk Spearman/cosine reference support",
            "reference_stage_support",
            {"numpy": _package_version("numpy"), "scipy": _package_version("scipy")},
        ),
        DevelopmentMethodId.ORDINAL_CLASSIFIER: (
            "scikit-learn uncalibrated cumulative logistic ordinal baseline with external source-group-held-out evidence",
            "ordinal_stage_support",
            {"scikit-learn": _package_version("scikit-learn")},
        ),
        DevelopmentMethodId.PROGRAM_ACTIVITY: (
            "decoupler ULM on sample pseudobulk",
            "stage_program",
            {"decoupler": _package_version("decoupler")},
        ),
        DevelopmentMethodId.SAMPLE_BOOTSTRAP: (
            "BRIDGE independence-group-preserving bootstrap",
            "uncertainty",
            {"numpy": _package_version("numpy")},
        ),
        DevelopmentMethodId.TIME_PROGRAM: (
            "decoupler ULM plus unadjusted descriptive statsmodels spline on declared true time",
            "time_trend",
            {
                "decoupler": _package_version("decoupler"),
                "statsmodels": _package_version("statsmodels"),
                "patsy": _package_version("patsy"),
            },
        ),
        DevelopmentMethodId.TIME_GAM_PY: (
            "unadjusted descriptive statsmodels OLS with a prespecified cubic B-spline basis",
            "time_trend",
            {
                "statsmodels": _package_version("statsmodels"),
                "patsy": _package_version("patsy"),
            },
        ),
    }
    output_counts = {
        DevelopmentMethodId.PSEUDOBULK_CORRELATION: sum(
            item.evidence_state == "shadow" for item in outputs.reference_support
        ),
        DevelopmentMethodId.ORDINAL_CLASSIFIER: len(outputs.ordinal_predictions),
        DevelopmentMethodId.PROGRAM_ACTIVITY: len(outputs.program_activity),
        DevelopmentMethodId.SAMPLE_BOOTSTRAP: len(outputs.bootstrap_intervals),
        DevelopmentMethodId.TIME_PROGRAM: sum(
            item.metric_name == "stage_program_activity" for item in outputs.time_trends
        ),
        DevelopmentMethodId.TIME_GAM_PY: sum(
            item.metric_name == "within_window_reference_support"
            for item in outputs.time_trends
        ),
    }
    evidence: list[DevelopmentMethodEvidence] = []
    n_groups = len(set(query.independence_by_analysis_unit.values()))
    for method_id in sorted(spec.selected_method_ids, key=str):
        reasons = sorted(outputs.method_reasons[method_id])
        count = output_counts[method_id]
        if count == 0:
            state = MethodExecutionState.NOT_ASSESSED
            if not reasons:
                reasons = ["method_output_unavailable"]
        elif reasons:
            state = MethodExecutionState.PARTIAL
        else:
            state = MethodExecutionState.SUCCEEDED
        implementation, family, packages = implementations[method_id]
        evidence.append(
            DevelopmentMethodEvidence(
                method_id=method_id,
                execution_state=state,
                evidence_family=family,
                implementation=implementation,
                package_versions=packages,
                n_analysis_units=len(query.analysis_unit_refs),
                n_independence_groups=n_groups,
                reason_codes=reasons,
            )
        )
    return evidence


def _require_module(name: str):
    try:
        return importlib.import_module(name)
    except ImportError as exc:
        raise DevelopmentMethodError(
            "required_method_dependency_unavailable", name
        ) from exc


def _package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "unavailable"


def _optional_text(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _bounded_float(value: object, lower: float, upper: float) -> float | None:
    if value is None or pd.isna(value):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return min(max(number, lower), upper)
