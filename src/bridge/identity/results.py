from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass
class IdentityProbabilities:
    probs_ref_raw: pd.DataFrame
    probs_ref_cal: pd.DataFrame
    probs_query_raw: pd.DataFrame
    probs_query_cal: pd.DataFrame
    class_names: list[str]
    target_class: str
    calibrators: dict[str, Any]


@dataclass
class IdentityUncertainty:
    mean_prob: pd.DataFrame
    std_prob: pd.DataFrame
    entropy_norm: pd.Series
    ensemble_size: int
    seed_base: int


@dataclass
class IdentityThresholds:
    threshold_t: float
    threshold_u: float
    threshold_v: float
    u_raw: float
    target_precision: float


@dataclass
class IdentitySelectionResult:
    candidate_mask: pd.Series
    thresholds: IdentityThresholds
    target_class: str
