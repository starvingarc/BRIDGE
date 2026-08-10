from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class IdentityOutputContract:
    target_class: str

    @property
    def candidate_flag_col(self) -> str:
        return f"is_candidate_{self.target_class}"

    @property
    def p_mean_col(self) -> str:
        return f"p_mean_{self.target_class}"

    @property
    def p_std_col(self) -> str:
        return f"p_std_{self.target_class}"

    @property
    def p_cal_col(self) -> str:
        return f"p_cal_{self.target_class}"

    @property
    def entropy_col(self) -> str:
        return "Hnorm"


def read_identity_outputs(obs: pd.DataFrame, target_class: str) -> pd.DataFrame:
    contract = IdentityOutputContract(target_class=target_class)
    required = [
        contract.candidate_flag_col,
        contract.p_mean_col,
        contract.p_std_col,
        contract.entropy_col,
    ]
    missing = [col for col in required if col not in obs.columns]
    if missing:
        raise KeyError(f"Missing identity output columns: {missing}")
    available = required + ([contract.p_cal_col] if contract.p_cal_col in obs.columns else [])
    return obs.loc[:, available].copy()
