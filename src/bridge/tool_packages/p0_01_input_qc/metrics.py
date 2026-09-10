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


def apply_robust_candidate_rules(
    metrics: pd.DataFrame, groups: pd.Series, policy: dict
) -> tuple[pd.DataFrame, list[dict]]:
    """Apply one versioned technical rule separately to each declared capture."""
    if not groups.index.equals(metrics.index) or groups.isna().any():
        raise ValueError("qc_robust_capture_partition_invalid")
    lower_mads = float(policy["lower_log_mads"])
    upper_mads = float(policy["upper_mito_mads"])
    if not (np.isfinite([lower_mads, upper_mads]).all() and min(lower_mads, upper_mads) > 0):
        raise ValueError("qc_robust_mad_policy_invalid")
    columns = ["total_counts", "detected_genes", "mitochondrial_fraction"]
    values = metrics[columns].to_numpy(dtype=float)
    nonempty = values[:, 0] > 0
    if (
        not np.isfinite(values[:, :2]).all() or (values[:, :2] < 0).any()
        or not np.isfinite(values[nonempty]).all()
        or (values[nonempty, 2] < 0).any() or (values[nonempty, 2] > 1).any()
    ):
        raise ValueError("qc_robust_metrics_unavailable")
    flags = pd.DataFrame(False, index=metrics.index, columns=[
        "flag_zero_total_counts", "flag_low_total_counts",
        "flag_low_detected_genes", "flag_high_mitochondrial_fraction",
    ])
    flags["flag_zero_total_counts"] = metrics.total_counts <= 0
    thresholds = []
    for capture in sorted(groups.astype(str).unique()):
        mask = groups.astype(str) == capture
        frame = metrics.loc[mask]
        record = {"capture_id": capture, "n_observations": int(mask.sum())}
        for metric, field, flag, logarithmic in (
            ("total_counts", "min_total_counts", "flag_low_total_counts", True),
            ("detected_genes", "min_detected_genes", "flag_low_detected_genes", True),
            ("mitochondrial_fraction", "max_mitochondrial_fraction", "flag_high_mitochondrial_fraction", False),
        ):
            raw = frame[metric].to_numpy(dtype=float)
            assessed = raw[frame.total_counts.to_numpy() > 0]
            if not len(assessed):
                raise ValueError("qc_robust_degenerate_distribution")
            transformed = np.log1p(assessed) if logarithmic else assessed
            median = float(np.median(transformed))
            mad = float(np.median(np.abs(transformed - median)))
            if mad == 0:
                raise ValueError("qc_robust_degenerate_distribution")
            cutoff = median - lower_mads * mad if logarithmic else median + upper_mads * mad
            if logarithmic:
                cutoff = max(0, int(np.ceil(round(float(np.expm1(cutoff)), 10))))
                flags.loc[mask, flag] = raw < cutoff
            else:
                cutoff = min(1.0, round(cutoff, 12))
                flags.loc[mask, flag] = raw > cutoff
            record[field] = cutoff
            record[f"{metric}_median_transformed"] = median
            record[f"{metric}_mad_unscaled"] = mad
        thresholds.append(record)
    flags["bridge_qc_candidate_eligible"] = ~flags.any(axis=1)
    return flags, thresholds


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
