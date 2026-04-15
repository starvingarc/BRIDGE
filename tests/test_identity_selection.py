from __future__ import annotations

import pandas as pd

from bridge.identity.selection import calibrate_threshold_from_ref, compute_candidate_mask, estimate_u_from_std


def test_compute_candidate_mask_requires_all_three_gates():
    mean_org = pd.DataFrame({"RG": [0.9, 0.9, 0.7]}, index=["a", "b", "c"])
    std_org = pd.DataFrame({"RG": [0.01, 0.2, 0.01]}, index=["a", "b", "c"])
    hnorm = pd.Series([0.2, 0.2, 0.2], index=["a", "b", "c"])
    mask = compute_candidate_mask(mean_org, std_org, hnorm, "RG", t=0.8, u=0.05, v=0.5, obs_index=mean_org.index)
    assert mask.to_dict() == {"a": True, "b": False, "c": False}


def test_estimate_u_from_std_respects_floor():
    u, u_raw = estimate_u_from_std(pd.Series([0.0, 0.0, 0.0]), q=75, u_min=0.005)
    assert u == 0.005
    assert u_raw == 0.0


def test_calibrate_threshold_from_ref_falls_back_when_precision_unreachable():
    p = pd.Series([0.1, 0.2, 0.3, 0.4], index=list("abcd"))
    y = pd.Series(["X", "Y", "Y", "Y"], index=p.index)
    threshold = calibrate_threshold_from_ref(p, y, target_class="X", target_precision=0.99)
    assert threshold >= p.quantile(0.8)
