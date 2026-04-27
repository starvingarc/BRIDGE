from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass
class CLSComponentResult:
    component: str
    score_df: pd.DataFrame
    global_score: float
    meta: dict[str, Any]

    def to_payload(self, dataset_id: str) -> dict[str, Any]:
        return {
            "component": self.component,
            "dataset_id": dataset_id,
            "global_score": float(self.global_score),
            "meta": self.meta,
        }


@dataclass(frozen=True)
class Step2Summary:
    dataset_id: str
    target_class: str
    n_query: int | None
    n_ref: int | None
    threshold_t: float | None
    threshold_u: float | None
    threshold_u_raw: float | None
    threshold_v: float | None
    candidate_count: int | None = None
    candidate_fraction: float | None = None
    has_p_cal: bool = False
    has_p_mean: bool = False
    has_p_std: bool = False
    has_hnorm: bool = False
    p_mean_mean: float | None = None
    p_mean_median: float | None = None
    p_std_mean: float | None = None
    p_std_median: float | None = None
    hnorm_mean: float | None = None
    hnorm_median: float | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "target_class": self.target_class,
            "n_query": self.n_query,
            "n_ref": self.n_ref,
            "threshold_t": self.threshold_t,
            "threshold_u": self.threshold_u,
            "threshold_u_raw": self.threshold_u_raw,
            "threshold_v": self.threshold_v,
            "candidate_count": self.candidate_count,
            "candidate_fraction": self.candidate_fraction,
            "has_p_cal": self.has_p_cal,
            "has_p_mean": self.has_p_mean,
            "has_p_std": self.has_p_std,
            "has_hnorm": self.has_hnorm,
            "p_mean_mean": self.p_mean_mean,
            "p_mean_median": self.p_mean_median,
            "p_std_mean": self.p_std_mean,
            "p_std_median": self.p_std_median,
            "hnorm_mean": self.hnorm_mean,
            "hnorm_median": self.hnorm_median,
        }

    def to_row(self) -> dict[str, Any]:
        return self.to_payload()


@dataclass(frozen=True)
class Step3ComponentDetail:
    component: str
    global_score: float
    result_json: str
    has_batch_csv: bool
    has_branch_csv: bool
    has_genes_csv: bool
    has_query_aucell_csv: bool

    @property
    def has_detail_table(self) -> bool:
        return bool(self.has_batch_csv or self.has_branch_csv or self.has_genes_csv or self.has_query_aucell_csv)

    def to_payload(self) -> dict[str, Any]:
        return {
            "component": self.component,
            "global_score": self.global_score,
            "result_json": self.result_json,
            "has_batch_csv": self.has_batch_csv,
            "has_branch_csv": self.has_branch_csv,
            "has_genes_csv": self.has_genes_csv,
            "has_query_aucell_csv": self.has_query_aucell_csv,
        }


@dataclass(frozen=True)
class DatasetReportRecord:
    step2: Step2Summary
    step3_components: list[Step3ComponentDetail]
    weighted_total_cls: float | None = None

    def to_row(self) -> dict[str, Any]:
        row = self.step2.to_row()
        for component in self.step3_components:
            row[f"cls_{component.component}"] = component.global_score
            row[f"has_{component.component}_detail_table"] = component.has_detail_table
        row["weighted_total_cls"] = self.weighted_total_cls
        return row


@dataclass(frozen=True)
class DatasetReportManifest:
    dataset_id: str
    dataset_prefix: str
    target_class: str
    enabled_components: list[str]
    summary_csv: str
    weighted_total_cls: float | None
    step2: Step2Summary
    step2_artifacts: dict[str, str]
    component_payloads: dict[str, str]
    component_details: list[Step3ComponentDetail]

    def to_payload(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "dataset_prefix": self.dataset_prefix,
            "target_class": self.target_class,
            "enabled_components": self.enabled_components,
            "summary_csv": self.summary_csv,
            "weighted_total_cls": self.weighted_total_cls,
            "step2": self.step2.to_payload(),
            "step2_artifacts": self.step2_artifacts,
            "component_payloads": self.component_payloads,
            "component_details": [component.to_payload() for component in self.component_details],
        }


@dataclass(frozen=True)
class BatchReportManifest:
    config_list: str
    datasets: list[str]
    per_dataset_results: list[dict[str, Any]]
    combined_summary_csv: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "config_list": self.config_list,
            "datasets": self.datasets,
            "per_dataset_results": self.per_dataset_results,
            "combined_summary_csv": self.combined_summary_csv,
        }
