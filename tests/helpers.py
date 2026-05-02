from __future__ import annotations

import pandas as pd


class DummyAnnData:
    def __init__(self, obs: pd.DataFrame):
        self.obs = obs.copy()
        self.obs_names = self.obs.index
        self.uns = {}
        self.n_obs = len(self.obs)
