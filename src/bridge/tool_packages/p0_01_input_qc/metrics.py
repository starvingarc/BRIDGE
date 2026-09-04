from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import sparse


DEFAULT_FEATURE_SET_POLICY = {
    "policy_id": "QC-feature-set-human-symbol-default-v0.1",
    "mitochondrial_symbol_prefixes": ["MT-"],
    "ribosomal_symbol_prefixes": ["RPS", "RPL"],
    "mitochondrial_interpretation": "unvalidated_generic_fraction",
}


def calculate_count_metrics(
    matrix,
    gene_names: pd.Index,
    feature_set_policy: dict | None = None,
) -> tuple[pd.DataFrame, dict[str, int]]:
    csr = sparse.csr_matrix(matrix)
    total_counts = np.asarray(csr.sum(axis=1)).ravel().astype(float)
    detected_genes = np.asarray((csr > 0).sum(axis=1)).ravel().astype(int)
    upper_names = gene_names.astype(str).str.upper()
    policy = feature_set_policy or DEFAULT_FEATURE_SET_POLICY
    mt_prefixes = tuple(str(value).upper() for value in policy["mitochondrial_symbol_prefixes"])
    ribo_prefixes = tuple(str(value).upper() for value in policy["ribosomal_symbol_prefixes"])
    mt_mask = np.asarray(upper_names.str.startswith(mt_prefixes), dtype=bool)
    ribo_mask = np.asarray(upper_names.str.startswith(ribo_prefixes), dtype=bool)
    mt_counts = np.asarray(csr[:, mt_mask].sum(axis=1)).ravel() if mt_mask.any() else None
    ribo_counts = np.asarray(csr[:, ribo_mask].sum(axis=1)).ravel() if ribo_mask.any() else None
    positive_totals = total_counts > 0
    frame = pd.DataFrame(
        {
            "total_counts": total_counts,
            "detected_genes": detected_genes,
            "mitochondrial_fraction": _defined_fraction(mt_counts, total_counts, positive_totals),
            "ribosomal_fraction": _defined_fraction(ribo_counts, total_counts, positive_totals),
            "top_20_gene_fraction": _top_n_fraction(csr, total_counts, n=20),
        }
    )
    coverage = {
        "total_genes": int(len(gene_names)),
        "mitochondrial_genes": int(mt_mask.sum()),
        "ribosomal_genes": int(ribo_mask.sum()),
    }
    return frame, coverage


def apply_candidate_rules(metrics: pd.DataFrame, rules: dict) -> pd.DataFrame:
    flags = pd.DataFrame(index=metrics.index)
    flags["flag_zero_total_counts"] = metrics["total_counts"] <= 0
    flags["flag_low_detected_genes"] = metrics["detected_genes"] < int(rules["min_detected_genes"])
    flags["flag_high_detected_genes"] = metrics["detected_genes"] > int(rules["max_detected_genes"])
    if "max_mitochondrial_fraction" in rules:
        flags["flag_high_mitochondrial_fraction"] = (
            metrics["mitochondrial_fraction"] > float(rules["max_mitochondrial_fraction"])
        )
    flags["bridge_qc_candidate_eligible"] = ~flags.any(axis=1)
    return flags


def summarize_by_group(metrics: pd.DataFrame, groups: pd.Series, observation_unit: str) -> list[dict]:
    table = metrics.copy()
    table["group"] = groups.astype(str).to_numpy()
    records: list[dict] = []
    for group, frame in table.groupby("group", sort=True):
        record: dict[str, float | int | str | None] = {
            "group": str(group),
            "n_observations": int(len(frame)),
            "observation_unit": observation_unit,
        }
        for column in metrics.columns:
            values = frame[column].dropna()
            record[f"{column}_median"] = _optional_float(values.median()) if not values.empty else None
            record[f"{column}_q1"] = _optional_float(values.quantile(0.25)) if not values.empty else None
            record[f"{column}_q3"] = _optional_float(values.quantile(0.75)) if not values.empty else None
        records.append(record)
    return records


def _optional_float(value) -> float | None:
    return float(value) if pd.notna(value) else None


def _top_n_fraction(matrix: sparse.csr_matrix, totals: np.ndarray, n: int) -> np.ndarray:
    fractions = np.full(matrix.shape[0], np.nan, dtype=float)
    for row in range(matrix.shape[0]):
        start, end = matrix.indptr[row], matrix.indptr[row + 1]
        values = matrix.data[start:end]
        if values.size and totals[row] > 0:
            count = min(n, values.size)
            top = np.partition(values, values.size - count)[-count:]
            fractions[row] = float(top.sum() / totals[row])
    return fractions


def _defined_fraction(
    numerators: np.ndarray | None,
    totals: np.ndarray,
    positive_totals: np.ndarray,
) -> np.ndarray:
    fractions = np.full(len(totals), np.nan, dtype=float)
    if numerators is not None:
        fractions[positive_totals] = numerators[positive_totals] / totals[positive_totals]
    return fractions
