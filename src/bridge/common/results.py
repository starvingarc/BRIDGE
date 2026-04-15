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
