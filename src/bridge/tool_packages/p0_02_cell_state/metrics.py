from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.stats import rankdata

from bridge.toolkit.contracts import MarkerProgramCard


def normalize_query(matrix, semantics: str):
    if semantics == "normalized_expression":
        return matrix.astype(float)
    totals = np.asarray(matrix.sum(axis=1)).ravel().astype(float)
    scale = np.divide(10000.0, totals, out=np.zeros_like(totals), where=totals > 0)
    if sparse.issparse(matrix):
        normalized = sparse.diags(scale) @ matrix
        normalized = normalized.tocsr().astype(float)
        normalized.data = np.log1p(normalized.data)
        return normalized
    return np.log1p(np.asarray(matrix, dtype=float) * scale[:, None])


def source_support(
    query,
    query_genes: np.ndarray,
    reference: np.ndarray,
    reference_metadata: dict[str, Any],
    observation_ids: np.ndarray,
    *,
    minimum_shared_genes: int,
    chunk_size: int = 256,
    workers: int = 1,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    reference_genes = np.asarray(reference_metadata["genes"])
    query_index = {gene: index for index, gene in enumerate(query_genes)}
    shared = [gene for gene in reference_genes if gene in query_index]
    coverage = {
        "shared_genes": len(shared),
        "query_gene_fraction": len(shared) / len(query_genes),
        "reference_gene_fraction": len(shared) / len(reference_genes),
        "state": "available" if len(shared) >= minimum_shared_genes else "insufficient",
    }
    if len(shared) < minimum_shared_genes:
        return pd.DataFrame(), pd.DataFrame(), coverage

    q_indices = np.asarray([query_index[gene] for gene in shared])
    r_index = {gene: index for index, gene in enumerate(reference_genes)}
    r_indices = np.asarray([r_index[gene] for gene in shared])
    ref = np.asarray(reference[:, r_indices], dtype=float)
    labels = np.asarray([row["label"] for row in reference_metadata["rows"]])
    unique_labels = np.asarray(sorted(set(labels)))
    label_centroids = np.vstack([np.median(ref[labels == label], axis=0) for label in unique_labels])
    ref_ranked = _row_standardize(rankdata(label_centroids, axis=1, method="average"))
    ref_cosine = _row_standardize(label_centroids, center=False)

    def calculate_chunk(start: int) -> tuple[np.ndarray, np.ndarray]:
        chunk = query[start : start + chunk_size, q_indices]
        dense = chunk.toarray() if sparse.issparse(chunk) else np.asarray(chunk)
        ranked = _row_standardize(rankdata(dense, axis=1, method="average"))
        cosine_query = _row_standardize(dense, center=False)
        return ranked @ ref_ranked.T, cosine_query @ ref_cosine.T

    starts = range(0, query.shape[0], chunk_size)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        parts = list(pool.map(calculate_chunk, starts))
    spearman_parts, cosine_parts = zip(*parts, strict=True)
    spearman = np.vstack(spearman_parts)
    cosine = np.vstack(cosine_parts)

    long = pd.DataFrame(
        {
            "observation_id": np.repeat(observation_ids, len(unique_labels)),
            "label": np.tile(unique_labels, len(observation_ids)),
            "spearman_support": spearman.ravel(),
            "cosine_support": cosine.ravel(),
        }
    )
    ordered = np.argsort(np.nan_to_num(spearman, nan=-np.inf), axis=1)
    top_index = ordered[:, -1]
    runner_index = ordered[:, -2] if len(unique_labels) > 1 else top_index
    top = spearman[np.arange(len(observation_ids)), top_index]
    runner = spearman[np.arange(len(observation_ids)), runner_index]
    finite = np.isfinite(top)
    summary = pd.DataFrame(
        {
            "observation_id": observation_ids,
            "top_label": np.where(finite, unique_labels[top_index], None),
            "top_spearman_support": np.where(finite, top, np.nan),
            "runner_up_label": np.where(finite, unique_labels[runner_index], None),
            "margin": np.where(finite, top - runner, np.nan),
            "top_cosine_support": np.where(
                finite,
                cosine[np.arange(len(observation_ids)), top_index],
                np.nan,
            ),
        }
    )
    return long, summary, coverage


def reconcile_source_tops(
    observation_ids: np.ndarray,
    source_summaries: list[pd.DataFrame],
) -> pd.DataFrame:
    by_source = [frame.set_index("observation_id")["top_label"] for frame in source_summaries]
    records: list[dict[str, Any]] = []
    for observation_id in observation_ids:
        labels = sorted(
            {
                str(series.get(observation_id))
                for series in by_source
                if pd.notna(series.get(observation_id))
            }
        )
        if not labels:
            status = "unavailable"
            consensus = None
        elif len(by_source) == 1:
            status = "single_source_supported"
            consensus = None
        elif len(labels) == 1:
            status = "consensus_supported"
            consensus = labels[0]
        else:
            status = "source_conflict"
            consensus = None
        records.append(
            {
                "observation_id": observation_id,
                "prediction_set": labels,
                "consensus_label": consensus,
                "support_state": status,
                "assignment_state": "shadow_candidate" if labels else "unavailable",
                "open_set_state": "not_assessed",
            }
        )
    return pd.DataFrame(records)


def marker_program_evidence(
    query,
    genes: np.ndarray,
    observation_ids: np.ndarray,
    cards: list[MarkerProgramCard],
    *,
    minimum_marker_genes: int,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    gene_index = {gene: index for index, gene in enumerate(genes)}
    frames: list[pd.DataFrame] = []
    summaries: list[dict[str, Any]] = []
    for card in cards:
        if card.level != "L1" or "shadow_evidence" not in card.allowed_use:
            continue
        positive = [gene.upper() for gene in card.positive_markers if gene.upper() in gene_index]
        negative = [gene.upper() for gene in card.negative_markers if gene.upper() in gene_index]
        state = "shadow" if len(positive) >= minimum_marker_genes else "unavailable"
        summaries.append(
            {
                "card_id": card.card_id,
                "state_id": card.state_id,
                "review_status": card.review_status,
                "positive_gene_coverage": len(positive) / len(card.positive_markers)
                if card.positive_markers
                else 0.0,
                "negative_gene_coverage": len(negative) / len(card.negative_markers)
                if card.negative_markers
                else None,
                "state": state,
                "source_ids": card.source_ids,
            }
        )
        if state == "unavailable":
            continue
        positive_values = _mean_columns(query, [gene_index[gene] for gene in positive])
        negative_values = (
            _mean_columns(query, [gene_index[gene] for gene in negative])
            if negative
            else np.full(len(observation_ids), np.nan)
        )
        frames.append(
            pd.DataFrame(
                {
                    "observation_id": observation_ids,
                    "card_id": card.card_id,
                    "state_id": card.state_id,
                    "positive_mean_expression": positive_values,
                    "negative_mean_expression": negative_values,
                    "review_status": card.review_status,
                    "evidence_state": "prior_only_shadow",
                }
            )
        )
    return (pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(), summaries)


def hierarchy_restricted_summary(
    support: pd.DataFrame,
    observation_ids: np.ndarray,
    allowed_labels: dict[str, set[str]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    result = support.copy()
    result["hierarchy_applicable"] = [
        label in allowed_labels.get(observation_id, set())
        for observation_id, label in zip(result["observation_id"], result["label"], strict=True)
    ]
    applicable = result[result["hierarchy_applicable"]].sort_values(
        ["observation_id", "spearman_support"],
        ascending=[True, False],
        kind="stable",
    )
    grouped = applicable.groupby("observation_id", sort=False, observed=True)
    top = grouped.nth(0).set_index("observation_id")
    runner = grouped.nth(1).set_index("observation_id")
    records: list[dict[str, Any]] = []
    for observation_id in observation_ids:
        if observation_id not in top.index:
            records.append({"observation_id": observation_id, "top_label": None})
            continue
        first = top.loc[observation_id]
        second = runner.loc[observation_id] if observation_id in runner.index else None
        records.append(
            {
                "observation_id": observation_id,
                "top_label": first["label"],
                "top_spearman_support": first["spearman_support"],
                "runner_up_label": second["label"] if second is not None else None,
                "margin": first["spearman_support"] - second["spearman_support"]
                if second is not None
                else None,
                "top_cosine_support": first["cosine_support"],
            }
        )
    return result, pd.DataFrame(records)


def composition_records(
    evidence: pd.DataFrame,
    source_summaries: list[pd.DataFrame],
    source_ids: list[str],
) -> list[dict[str, Any]]:
    denominator = len(evidence)
    records: list[dict[str, Any]] = []
    for source_id, frame in zip(source_ids, source_summaries, strict=True):
        for label, count in frame["top_label"].value_counts(dropna=True).items():
            records.append(
                {
                    "view": "source_specific",
                    "source_id": source_id,
                    "label": label,
                    "count": int(count),
                    "fraction": float(count / denominator),
                    "denominator": denominator,
                }
            )
    for status, count in evidence["support_state"].value_counts().items():
        records.append(
            {
                "view": "reconciliation_state",
                "source_id": None,
                "label": status,
                "count": int(count),
                "fraction": float(count / denominator),
                "denominator": denominator,
            }
        )
    for label, count in evidence["consensus_label"].value_counts(dropna=True).items():
        records.append(
            {
                "view": "consensus_supported_only",
                "source_id": None,
                "label": label,
                "count": int(count),
                "fraction": float(count / denominator),
                "denominator": denominator,
            }
        )
    return records


def composition_records_v3(
    records: list[dict[str, Any]],
    *,
    selected_view_denominator: int,
) -> list[dict[str, Any]]:
    reconciliation_states = {
        "consensus_supported": "candidate",
        "single_source_supported": "candidate",
        "source_conflict": "unresolved",
        "unavailable": "unavailable",
        "unknown": "unknown",
        "ood": "ood",
    }
    typed: list[dict[str, Any]] = []
    for record in records:
        if record.get("label_level") != "L1":
            continue
        view = str(record["view"])
        label = str(record["label"])
        if int(record["denominator"]) != selected_view_denominator:
            raise ValueError(
                "L1 composition denominator does not match selected DataView"
            )
        if view in {"source_specific", "consensus_supported_only"}:
            evidence_state = "candidate"
        elif view == "reconciliation_state":
            try:
                evidence_state = reconciliation_states[label]
            except KeyError as exc:
                raise ValueError(
                    f"unmapped reconciliation state: {label}"
                ) from exc
        else:
            raise ValueError(f"unmapped composition view: {view}")
        typed.append(
            {
                "view": view,
                "source_id": record.get("source_id"),
                "label": label,
                "label_level": "L1",
                "state_evidence_state": evidence_state,
                "denominator_scope": "selected_data_view",
                "count": int(record["count"]),
                "fraction": float(record["fraction"]),
                "denominator": selected_view_denominator,
            }
        )
    return typed


def serialize_prediction_sets(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for column in ("prediction_set", "l2_prediction_set"):
        if column in result:
            result[column] = result[column].map(
                lambda values: json.dumps(values, ensure_ascii=False, separators=(",", ":"))
                if isinstance(values, list)
                else None
            )
    return result


def _mean_columns(matrix, indices: list[int]) -> np.ndarray:
    values = matrix[:, indices].mean(axis=1)
    return np.asarray(values).ravel()


def _row_standardize(matrix: np.ndarray, *, center: bool = True) -> np.ndarray:
    values = np.asarray(matrix, dtype=float)
    if center:
        values = values - np.nanmean(values, axis=1, keepdims=True)
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    return np.divide(values, norms, out=np.zeros_like(values), where=norms > 0)
