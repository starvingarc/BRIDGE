from __future__ import annotations

from bridge.common.stats import normalize_weights, safe_weighted_mean


def test_normalize_weights_and_weighted_mean():
    w = normalize_weights([1, 3])
    assert w.tolist() == [0.25, 0.75]
    assert round(safe_weighted_mean([0.2, 0.8], [1, 3]), 6) == 0.65
