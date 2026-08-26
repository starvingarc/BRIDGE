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
from scipy.optimize import nnls

from bridge.tool_packages._configurable_contracts import (
    BiologicalUnitAssignmentArtifact,
    StateRoleMap,
    observation_ids_sha256,
)
from bridge.tool_packages.p0_01_input_qc.io import InputAuditError, sha256_path
from bridge.tool_packages.p0_02_cell_state.metrics import source_support
from bridge.tool_packages.p0_02_cell_state.reference import load_reference_profile
from bridge.tool_packages.p0_03_target_regional.method_models import (
    ContinuousIdentityWeight,
    MethodExecutionState,
    ProgramActivityRecord,
    ReferenceSupportRecord,
    RobustnessRecord,
    SampleBootstrapInterval,
    TargetRegionalMethodBundle,
    TargetRegionalMethodEvidence,
    TargetRegionalMethodId,
    TargetRegionalMethodSpec,
)
from bridge.tool_packages.p0_03_target_regional.models import (
    TargetRegionalAssessmentSpec,
)
from bridge.toolkit.contracts import (
    InputAsset,
    MarkerProgramCard,
    ReferenceManifest,
    ReferenceProfile,
    ScoreState,
)


class TargetRegionalMethodError(RuntimeError):
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


def run_target_regional_methods(
    *,
    run_id: str,
    tool_version: str,
    asset: InputAsset,
    asset_sha256: str,
    method_spec: TargetRegionalMethodSpec,
    assessment_spec: TargetRegionalAssessmentSpec,
    state_role_map: StateRoleMap,
    reference_manifest: ReferenceManifest,
    biological_unit_assignment: BiologicalUnitAssignmentArtifact,
    reference_manifest_path: Path,
    random_seed: int,
    expected_n_observations: int,
    expected_observation_ids_sha256: str,
) -> TargetRegionalMethodBundle:
    query = _load_query_pseudobulk(asset, method_spec, biological_unit_assignment)
    root = reference_manifest_path.parent
    if query.n_observations != expected_n_observations:
        raise TargetRegionalMethodError("expression_view_observation_count_mismatch")
    if query.observation_ids_sha256 != expected_observation_ids_sha256:
        raise TargetRegionalMethodError("expression_view_observation_identity_mismatch")
    target_profiles = _resolve_profiles(
        reference_manifest, method_spec.target_reference_profile_ids
    )
    regional_profiles = _resolve_profiles(
        reference_manifest, method_spec.regional_reference_profile_ids
    )
    profiles_by_id = {
        profile.profile_id: profile
        for profile in [*target_profiles, *regional_profiles]
    }
    reference_runs_by_id = {
        profile_id: _load_checked_profile(root, profile, query)
        for profile_id, profile in sorted(profiles_by_id.items())
    }
    target_reference_runs = [
        reference_runs_by_id[profile.profile_id] for profile in target_profiles
    ]
    regional_reference_runs = [
        reference_runs_by_id[profile.profile_id] for profile in regional_profiles
    ]
    selected = set(method_spec.selected_method_ids)
    target_support = (
        _reference_support(
            query,
            target_reference_runs,
            method_spec.minimum_shared_genes,
            evidence_scope="target_identity",
        )
        if TargetRegionalMethodId.TARGET_PSEUDOBULK_CORRELATION in selected
        else []
    )
    regional_support_methods = {
        TargetRegionalMethodId.REGIONAL_PSEUDOBULK_CORRELATION,
        TargetRegionalMethodId.REGIONAL_CROSS_REFERENCE,
        TargetRegionalMethodId.REGIONAL_MODALITY_SENSITIVITY,
    }
    regional_support = (
        _reference_support(
            query,
            regional_reference_runs,
            method_spec.minimum_shared_genes,
            evidence_scope="regional_fidelity",
        )
        if selected & regional_support_methods
        else []
    )
    support = [*target_support, *regional_support]
    weights = (
        _continuous_identity_weights(
            query, target_reference_runs, method_spec.minimum_shared_genes
        )
        if selected
        & {
            TargetRegionalMethodId.TARGET_NNLS,
            TargetRegionalMethodId.TARGET_BOOTSTRAP,
        }
        else []
    )
    program_activity, program_missing = (
        _program_activity(
            root=root,
            manifest=reference_manifest,
            query=query,
            spec=method_spec,
            selected=selected,
        )
        if selected
        & {
            TargetRegionalMethodId.TARGET_DECOUPLER,
            TargetRegionalMethodId.REGIONAL_DECOUPLER,
        }
        else ([], set())
    )
    target_states = _target_state_ids(state_role_map, assessment_spec)
    intervals, bootstrap_reason = (
        _bootstrap_target_weight(
            weights=weights,
            target_state_ids=target_states,
            replicates=method_spec.bootstrap_replicates,
            independence_by_analysis_unit=query.independence_by_analysis_unit,
            confidence_level=method_spec.bootstrap_confidence_level,
            random_seed=random_seed,
        )
        if TargetRegionalMethodId.TARGET_BOOTSTRAP in selected
        else ([], None)
    )
    robustness = _robustness_records(
        query.analysis_unit_refs,
        regional_support,
        include_cross_reference=(
            TargetRegionalMethodId.REGIONAL_CROSS_REFERENCE in selected
        ),
        include_modality=(
            TargetRegionalMethodId.REGIONAL_MODALITY_SENSITIVITY in selected
        ),
    )
    evidence = _method_evidence(
        spec=method_spec,
        query=query,
        target_reference_runs=target_reference_runs,
        regional_reference_runs=regional_reference_runs,
        support=support,
        weights=weights,
        program_activity=program_activity,
        program_missing=program_missing,
        intervals=intervals,
        bootstrap_reason=bootstrap_reason,
        robustness=robustness,
    )
    score_state = (
        ScoreState.SHADOW
        if any(
            item.execution_state
            in {MethodExecutionState.SUCCEEDED, MethodExecutionState.PARTIAL}
            for item in evidence
        )
        else ScoreState.UNAVAILABLE
    )
    return TargetRegionalMethodBundle(
        object_version="0.1.0",
        bundle_id=f"target-regional-method-bundle:{run_id.removeprefix('run-')}",
        tool_id="P0-03",
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
        reference_support=support,
        continuous_identity_weights=weights,
        program_activity=program_activity,
        bootstrap_intervals=intervals,
        robustness=robustness,
        domain_score=None,
        score_state=score_state,
    )


def _load_query_pseudobulk(
    asset: InputAsset,
    spec: TargetRegionalMethodSpec,
    assignment_artifact: BiologicalUnitAssignmentArtifact,
) -> _QuerySummary:
    anndata = _require_module("anndata")
    try:
        adata = anndata.read_h5ad(asset.path, backed="r")
    except (OSError, ValueError) as exc:
        raise TargetRegionalMethodError(
            "expression_asset_unreadable", str(exc)
        ) from exc
    try:
        if spec.observation_id_column is None:
            observation_values = pd.Index(adata.obs_names).astype(str)
        else:
            if spec.observation_id_column not in adata.obs:
                raise TargetRegionalMethodError(
                    "observation_id_column_missing", spec.observation_id_column
                )
            observations = adata.obs[spec.observation_id_column]
            if observations.isna().any():
                raise TargetRegionalMethodError("observation_id_values_missing")
            observation_values = pd.Index(observations.astype(str))
        observation_ids = [value.strip() for value in observation_values]
        if any(not value for value in observation_ids):
            raise TargetRegionalMethodError("observation_id_values_missing")
        if len(observation_ids) != len(set(observation_ids)):
            raise TargetRegionalMethodError("observation_ids_not_unique")

        assignment_by_observation = {
            item.observation_id: item for item in assignment_artifact.assignments
        }
        if set(observation_ids) != set(assignment_by_observation):
            raise TargetRegionalMethodError(
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
                raise TargetRegionalMethodError(
                    "analysis_unit_independence_group_mismatch"
                )

        if spec.gene_symbol_column is None:
            gene_values = pd.Index(adata.var_names).astype(str)
        else:
            if spec.gene_symbol_column not in adata.var:
                raise TargetRegionalMethodError(
                    "gene_symbol_column_missing", spec.gene_symbol_column
                )
            symbols = adata.var[spec.gene_symbol_column]
            if symbols.isna().any():
                raise TargetRegionalMethodError("gene_symbol_values_missing")
            gene_values = pd.Index(symbols.astype(str))
        genes = np.asarray([value.strip().upper() for value in gene_values])
        if np.any(genes == ""):
            raise TargetRegionalMethodError("gene_symbol_values_missing")
        if len(genes) != len(set(genes)):
            raise TargetRegionalMethodError("gene_symbols_not_unique")

        matrix = adata.X
        if asset.matrix_location and asset.matrix_location != "X":
            prefix = "layers/"
            if not asset.matrix_location.startswith(prefix):
                raise TargetRegionalMethodError("unsupported_matrix_location")
            layer = asset.matrix_location.removeprefix(prefix)
            if layer not in adata.layers:
                raise TargetRegionalMethodError("matrix_layer_not_found", layer)
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
                    raise TargetRegionalMethodError("expression_matrix_nonfinite")
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
        raise TargetRegionalMethodError(
            "reference_profile_not_found", ",".join(missing)
        )
    profiles = [by_id[profile_id] for profile_id in sorted(profile_ids)]
    if any(
        not profile.matrix_file or not profile.metadata_file for profile in profiles
    ):
        raise TargetRegionalMethodError("reference_profile_artifact_unavailable")
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
        raise TargetRegionalMethodError(
            "reference_profile_invalid", profile.profile_id
        ) from exc
    if matrix.ndim != 2 or matrix.shape != (len(rows), len(reference_genes)):
        raise TargetRegionalMethodError(
            "reference_profile_shape_mismatch", profile.profile_id
        )
    if not np.issubdtype(matrix.dtype, np.number) or not np.isfinite(matrix).all():
        raise TargetRegionalMethodError(
            "reference_profile_matrix_invalid", profile.profile_id
        )
    if (
        np.any(reference_genes == "")
        or len(reference_genes) != len(set(reference_genes))
        or any(not label for label in labels)
    ):
        raise TargetRegionalMethodError(
            "reference_profile_metadata_invalid", profile.profile_id
        )
    if profile.n_genes and profile.n_genes != len(reference_genes):
        raise TargetRegionalMethodError(
            "reference_profile_metadata_mismatch", profile.profile_id
        )
    if profile.labels and set(profile.labels) != set(labels):
        raise TargetRegionalMethodError(
            "reference_profile_metadata_mismatch", profile.profile_id
        )
    shared = len(set(query.genes).intersection(reference_genes))
    return _ReferenceRun(
        profile=profile,
        matrix=matrix,
        metadata={**metadata, "genes": reference_genes.tolist()},
        shared_genes=shared,
    )


def _check_snapshot_artifact(
    root: Path, relative_name: str | None, expected_sha256: str | None
) -> Path:
    if not relative_name or not expected_sha256:
        raise TargetRegionalMethodError("reference_profile_artifact_unavailable")
    path = root / relative_name
    try:
        actual = sha256_path(path)
    except (OSError, InputAuditError) as exc:
        raise TargetRegionalMethodError(
            "reference_artifact_unreadable", relative_name
        ) from exc
    if actual != expected_sha256:
        raise TargetRegionalMethodError(
            "reference_artifact_checksum_mismatch", relative_name
        )
    return path


def _reference_support(
    query: _QuerySummary,
    references: list[_ReferenceRun],
    minimum_shared_genes: int,
    evidence_scope: str,
) -> list[ReferenceSupportRecord]:
    records: list[ReferenceSupportRecord] = []
    for reference in references:
        _, summary, coverage = source_support(
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
                ReferenceSupportRecord(
                    analysis_unit_ref=str(analysis_unit_ref),
                    evidence_scope=evidence_scope,
                    profile_id=reference.profile.profile_id,
                    profile_assay=reference.profile.assay,
                    shared_genes=int(coverage["shared_genes"]),
                    evidence_state="unavailable",
                )
                for analysis_unit_ref in query.analysis_unit_refs
            )
            continue
        for row in summary.to_dict(orient="records"):
            records.append(
                ReferenceSupportRecord(
                    analysis_unit_ref=str(row["observation_id"]),
                    evidence_scope=evidence_scope,
                    profile_id=reference.profile.profile_id,
                    profile_assay=reference.profile.assay,
                    top_label=_optional_text(row["top_label"]),
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
    return records


def _continuous_identity_weights(
    query: _QuerySummary,
    references: list[_ReferenceRun],
    minimum_shared_genes: int,
) -> list[ContinuousIdentityWeight]:
    query_index = {gene: index for index, gene in enumerate(query.genes)}
    records: list[ContinuousIdentityWeight] = []
    for reference in references:
        reference_genes = np.asarray(reference.metadata["genes"])
        shared = [gene for gene in reference_genes if gene in query_index]
        if len(shared) < minimum_shared_genes:
            continue
        q_indices = np.asarray([query_index[gene] for gene in shared])
        reference_index = {gene: index for index, gene in enumerate(reference_genes)}
        r_indices = np.asarray([reference_index[gene] for gene in shared])
        labels = np.asarray([row["label"] for row in reference.metadata["rows"]])
        unique_labels = np.asarray(sorted(set(labels)))
        centroids = np.vstack(
            [
                np.median(reference.matrix[labels == label][:, r_indices], axis=0)
                for label in unique_labels
            ]
        )
        for analysis_unit_ref, values in zip(
            query.analysis_unit_refs, query.matrix[:, q_indices], strict=True
        ):
            fitted, residual = nnls(centroids.T, np.asarray(values, dtype=float))
            total = fitted.sum()
            if total <= 0:
                continue
            fitted /= total
            records.extend(
                ContinuousIdentityWeight(
                    analysis_unit_ref=str(analysis_unit_ref),
                    profile_id=reference.profile.profile_id,
                    state_id=str(label),
                    weight=float(weight),
                    residual_norm=float(residual),
                )
                for label, weight in zip(unique_labels, fitted, strict=True)
            )
    return records


def _program_activity(
    *,
    root: Path,
    manifest: ReferenceManifest,
    query: _QuerySummary,
    spec: TargetRegionalMethodSpec,
    selected: set[TargetRegionalMethodId],
) -> tuple[list[ProgramActivityRecord], set[str]]:
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
        raise TargetRegionalMethodError("marker_program_registry_invalid") from exc
    requested = {
        "target_identity": (
            spec.target_program_card_ids
            if TargetRegionalMethodId.TARGET_DECOUPLER in selected
            else []
        ),
        "regional_fidelity": (
            spec.regional_program_card_ids
            if TargetRegionalMethodId.REGIONAL_DECOUPLER in selected
            else []
        ),
    }
    missing_ids = sorted(
        {
            card_id
            for card_ids in requested.values()
            for card_id in card_ids
            if card_id not in cards
        }
    )
    if missing_ids:
        raise TargetRegionalMethodError("program_card_not_found", ",".join(missing_ids))
    not_allowed = sorted(
        card_id
        for card_ids in requested.values()
        for card_id in card_ids
        if "shadow_evidence" not in cards[card_id].allowed_use
    )
    if not_allowed:
        raise TargetRegionalMethodError(
            "program_card_use_not_allowed", ",".join(not_allowed)
        )
    scopes_by_card: dict[str, set[str]] = {}
    for scope, card_ids in requested.items():
        for card_id in card_ids:
            scopes_by_card.setdefault(card_id, set()).add(scope)
    gene_set = set(query.genes)
    coverage: dict[str, tuple[int, int]] = {}
    network_rows: list[dict[str, str | float]] = []
    unavailable: set[str] = set()
    for card_id in sorted(scopes_by_card):
        card = cards[card_id]
        positive = sorted(
            {gene.upper() for gene in card.positive_markers}.intersection(gene_set)
        )
        negative = sorted(
            {gene.upper() for gene in card.negative_markers}.intersection(gene_set)
        )
        coverage[card_id] = (len(positive), len(negative))
        if len(positive) < spec.minimum_program_genes:
            unavailable.update(scopes_by_card[card_id])
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
        raise TargetRegionalMethodError("decoupler_execution_failed", str(exc)) from exc
    records: list[ProgramActivityRecord] = []
    for card_id in sorted(scopes_by_card):
        if card_id not in activities.columns:
            unavailable.update(scopes_by_card[card_id])
            continue
        card = cards[card_id]
        positive_count, negative_count = coverage[card_id]
        for analysis_unit_ref in query.analysis_unit_refs:
            activity = float(activities.loc[analysis_unit_ref, card_id])
            if not math.isfinite(activity):
                unavailable.update(scopes_by_card[card_id])
                continue
            p_value = float(p_values.loc[analysis_unit_ref, card_id])
            for scope in sorted(scopes_by_card[card_id]):
                records.append(
                    ProgramActivityRecord(
                        analysis_unit_ref=str(analysis_unit_ref),
                        card_id=card_id,
                        state_id=card.state_id,
                        evidence_scope=scope,
                        activity=activity,
                        p_value=p_value if math.isfinite(p_value) else None,
                        observed_positive_markers=positive_count,
                        observed_negative_markers=negative_count,
                    )
                )
    return records, unavailable


def _target_state_ids(
    state_role_map: StateRoleMap, assessment_spec: TargetRegionalAssessmentSpec
) -> set[str]:
    roles = set(assessment_spec.target_identity_numerator_product_roles)
    return {
        assignment.state_id
        for assignment in state_role_map.assignments
        if assignment.product_role in roles
    }


def _bootstrap_target_weight(
    *,
    weights: list[ContinuousIdentityWeight],
    target_state_ids: set[str],
    independence_by_analysis_unit: dict[str, str],
    replicates: int,
    confidence_level: float,
    random_seed: int,
) -> tuple[list[SampleBootstrapInterval], str | None]:
    observed_states = {record.state_id for record in weights}
    if not target_state_ids.intersection(observed_states):
        return [], "target_states_absent_from_reference"
    frame = pd.DataFrame(record.model_dump(mode="json") for record in weights)
    frame["target_weight"] = frame["weight"].where(
        frame["state_id"].isin(target_state_ids), 0.0
    )
    per_profile = frame.groupby(
        ["analysis_unit_ref", "profile_id"], sort=True, observed=True
    )["target_weight"].sum()
    per_analysis_unit = (
        per_profile.groupby("analysis_unit_ref", sort=True).mean().rename("weight")
    )
    independent = per_analysis_unit.reset_index()
    independent["independence_group_ref"] = independent["analysis_unit_ref"].map(
        independence_by_analysis_unit
    )
    if independent["independence_group_ref"].isna().any():
        raise TargetRegionalMethodError("independence_group_binding_missing")
    values = (
        independent.groupby("independence_group_ref", sort=True)["weight"]
        .mean()
        .to_numpy()
    )
    estimate = float(values.mean())
    if len(values) == 1:
        return [
            SampleBootstrapInterval(
                metric_name="target_identity_nnls_weight",
                estimate=estimate,
                n_independent_units=1,
                replicates=0,
                interval_state="descriptive_only",
            )
        ], "one_independent_unit_descriptive_only"
    rng = np.random.default_rng(random_seed)
    draws = rng.choice(values, size=(replicates, len(values)), replace=True).mean(
        axis=1
    )
    alpha = (1.0 - confidence_level) / 2.0
    lower, upper = np.quantile(draws, [alpha, 1.0 - alpha])
    return [
        SampleBootstrapInterval(
            metric_name="target_identity_nnls_weight",
            estimate=estimate,
            lower=float(lower),
            upper=float(upper),
            confidence_level=confidence_level,
            n_independent_units=len(values),
            replicates=replicates,
            interval_state="available",
        )
    ], None


def _robustness_records(
    analysis_unit_refs: np.ndarray,
    support: list[ReferenceSupportRecord],
    *,
    include_cross_reference: bool,
    include_modality: bool,
) -> list[RobustnessRecord]:
    records: list[RobustnessRecord] = []
    for analysis_unit_ref in analysis_unit_refs:
        available = [
            item
            for item in support
            if item.analysis_unit_ref == analysis_unit_ref
            and item.evidence_state == "shadow"
        ]
        if include_cross_reference:
            records.append(
                _robustness_record("cross_reference", str(analysis_unit_ref), available)
            )
        if include_modality:
            assay_count = len({item.profile_assay for item in available})
            records.append(
                _robustness_record(
                    "modality",
                    str(analysis_unit_ref),
                    available,
                    unavailable_reason=(
                        None
                        if assay_count >= 2
                        else "matched_modality_references_unavailable"
                    ),
                )
            )
    return records


def _robustness_record(
    kind: str,
    analysis_unit_ref: str,
    support: list[ReferenceSupportRecord],
    unavailable_reason: str | None = None,
) -> RobustnessRecord:
    profile_ids = sorted({item.profile_id for item in support})
    if len(profile_ids) < 2 and unavailable_reason is None:
        unavailable_reason = "multiple_reference_profiles_required"
    labels = sorted({item.top_label for item in support if item.top_label is not None})
    scores = [
        item.top_spearman_support
        for item in support
        if item.top_spearman_support is not None
    ]
    if (not labels or len(scores) < 2) and unavailable_reason is None:
        unavailable_reason = "reference_support_values_unavailable"
    if unavailable_reason is not None:
        return RobustnessRecord(
            robustness_kind=kind,
            analysis_unit_ref=analysis_unit_ref,
            compared_profile_ids=profile_ids,
            top_labels=labels,
            label_agreement="not_assessed",
            reason_codes=[unavailable_reason],
        )
    return RobustnessRecord(
        robustness_kind=kind,
        analysis_unit_ref=analysis_unit_ref,
        compared_profile_ids=profile_ids,
        top_labels=labels,
        label_agreement="agree" if len(labels) == 1 else "disagree",
        support_range=(float(max(scores) - min(scores)) if scores else None),
        reason_codes=[],
    )


def _method_evidence(
    *,
    spec: TargetRegionalMethodSpec,
    query: _QuerySummary,
    target_reference_runs: list[_ReferenceRun],
    regional_reference_runs: list[_ReferenceRun],
    support: list[ReferenceSupportRecord],
    weights: list[ContinuousIdentityWeight],
    program_activity: list[ProgramActivityRecord],
    program_missing: set[str],
    intervals: list[SampleBootstrapInterval],
    bootstrap_reason: str | None,
    robustness: list[RobustnessRecord],
) -> list[TargetRegionalMethodEvidence]:
    target_reference_methods = {
        TargetRegionalMethodId.TARGET_PSEUDOBULK_CORRELATION,
        TargetRegionalMethodId.TARGET_NNLS,
        TargetRegionalMethodId.TARGET_BOOTSTRAP,
    }
    regional_reference_methods = {
        TargetRegionalMethodId.REGIONAL_PSEUDOBULK_CORRELATION,
        TargetRegionalMethodId.REGIONAL_CROSS_REFERENCE,
        TargetRegionalMethodId.REGIONAL_MODALITY_SENSITIVITY,
    }
    records: list[TargetRegionalMethodEvidence] = []
    for method_id in sorted(spec.selected_method_ids, key=str):
        family, implementation, packages = _method_metadata(method_id)
        state = MethodExecutionState.SUCCEEDED
        reasons: list[str] = []
        n_units = len(query.analysis_unit_refs)
        reference_runs = (
            target_reference_runs
            if method_id in target_reference_methods
            else (
                regional_reference_runs
                if method_id in regional_reference_methods
                else []
            )
        )
        profile_ids = sorted(run.profile.profile_id for run in reference_runs)
        minimum_shared = (
            min(run.shared_genes for run in reference_runs) if reference_runs else None
        )

        if method_id in {
            TargetRegionalMethodId.TARGET_PSEUDOBULK_CORRELATION,
            TargetRegionalMethodId.REGIONAL_PSEUDOBULK_CORRELATION,
        }:
            scope = (
                "target_identity"
                if method_id is TargetRegionalMethodId.TARGET_PSEUDOBULK_CORRELATION
                else "regional_fidelity"
            )
            scoped_support = [item for item in support if item.evidence_scope == scope]
            available = [
                item for item in scoped_support if item.evidence_state == "shadow"
            ]
            if not available:
                state = MethodExecutionState.NOT_ASSESSED
                reasons = ["reference_gene_coverage_insufficient"]
                n_units = 0
            elif len(available) < len(scoped_support):
                state = MethodExecutionState.PARTIAL
                reasons = ["reference_profile_gene_coverage_incomplete"]
        elif method_id is TargetRegionalMethodId.TARGET_NNLS:
            if not weights:
                state = MethodExecutionState.NOT_ASSESSED
                reasons = ["reference_gene_coverage_insufficient"]
                n_units = 0
        elif method_id in {
            TargetRegionalMethodId.TARGET_DECOUPLER,
            TargetRegionalMethodId.REGIONAL_DECOUPLER,
        }:
            scope = (
                "target_identity"
                if method_id is TargetRegionalMethodId.TARGET_DECOUPLER
                else "regional_fidelity"
            )
            scoped = [item for item in program_activity if item.evidence_scope == scope]
            if not scoped:
                state = MethodExecutionState.NOT_ASSESSED
                reasons = ["program_gene_coverage_insufficient"]
                n_units = 0
            elif scope in program_missing:
                state = MethodExecutionState.PARTIAL
                reasons = ["program_gene_coverage_incomplete"]
        elif method_id is TargetRegionalMethodId.TARGET_BOOTSTRAP:
            if not intervals:
                state = MethodExecutionState.NOT_ASSESSED
                reasons = [bootstrap_reason or "target_weight_unavailable"]
                n_units = 0
            else:
                n_units = intervals[0].n_independent_units
                if bootstrap_reason is not None:
                    state = MethodExecutionState.PARTIAL
                    reasons = [bootstrap_reason]
        elif method_id in {
            TargetRegionalMethodId.REGIONAL_CROSS_REFERENCE,
            TargetRegionalMethodId.REGIONAL_MODALITY_SENSITIVITY,
        }:
            kind = (
                "cross_reference"
                if method_id is TargetRegionalMethodId.REGIONAL_CROSS_REFERENCE
                else "modality"
            )
            selected_records = [
                item for item in robustness if item.robustness_kind == kind
            ]
            assessed = [
                item
                for item in selected_records
                if item.label_agreement != "not_assessed"
            ]
            if not assessed:
                state = MethodExecutionState.NOT_ASSESSED
                reasons = sorted(
                    {
                        reason
                        for item in selected_records
                        for reason in item.reason_codes
                    }
                    or {"robustness_comparison_unavailable"}
                )
                n_units = 0
            elif len(assessed) < len(selected_records):
                state = MethodExecutionState.PARTIAL
                reasons = ["robustness_comparison_incomplete"]
        records.append(
            TargetRegionalMethodEvidence(
                method_id=method_id,
                execution_state=state,
                evidence_family=family,
                implementation=implementation,
                package_versions=packages,
                reference_profile_ids=profile_ids,
                n_analysis_units=n_units,
                n_shared_genes=minimum_shared,
                reason_codes=sorted(reasons),
            )
        )
    return records


def _method_metadata(
    method_id: TargetRegionalMethodId,
) -> tuple[str, str, dict[str, str]]:
    numpy_scipy = {
        "numpy": _package_version("numpy"),
        "scipy": _package_version("scipy"),
    }
    mapping = {
        TargetRegionalMethodId.TARGET_PSEUDOBULK_CORRELATION: (
            "reference_similarity",
            "BRIDGE sample-pseudobulk Spearman/cosine",
            numpy_scipy,
        ),
        TargetRegionalMethodId.REGIONAL_PSEUDOBULK_CORRELATION: (
            "regional_similarity",
            "BRIDGE regional sample-pseudobulk Spearman/cosine",
            numpy_scipy,
        ),
        TargetRegionalMethodId.TARGET_NNLS: (
            "continuous_identity",
            "SciPy non-negative least squares with simplex normalization",
            numpy_scipy,
        ),
        TargetRegionalMethodId.TARGET_DECOUPLER: (
            "marker_program",
            "decoupler univariate linear model",
            {"decoupler": _package_version("decoupler")},
        ),
        TargetRegionalMethodId.REGIONAL_DECOUPLER: (
            "regional_program",
            "decoupler univariate linear model",
            {"decoupler": _package_version("decoupler")},
        ),
        TargetRegionalMethodId.TARGET_BOOTSTRAP: (
            "uncertainty",
            "BRIDGE sample-preserving nonparametric bootstrap",
            {"numpy": _package_version("numpy")},
        ),
        TargetRegionalMethodId.REGIONAL_CROSS_REFERENCE: (
            "robustness",
            "BRIDGE cross-reference sensitivity",
            {"numpy": _package_version("numpy")},
        ),
        TargetRegionalMethodId.REGIONAL_MODALITY_SENSITIVITY: (
            "robustness",
            "BRIDGE scRNA/snRNA reference sensitivity",
            {"numpy": _package_version("numpy")},
        ),
    }
    return mapping[method_id]


def _require_module(name: str):
    try:
        return importlib.import_module(name)
    except ImportError as exc:
        raise TargetRegionalMethodError("method_dependency_missing", name) from exc


def _package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "unavailable"


def _optional_text(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    return str(value)


def _bounded_float(value: object, lower: float, upper: float) -> float | None:
    if value is None or not math.isfinite(float(value)):
        return None
    return min(upper, max(lower, float(value)))
