from __future__ import annotations

import importlib
import sys

import pandas as pd

from bridge.identity import IdentityResult, assess_identity_probabilities, identify
from bridge.identity.api import build_identity_summary
from bridge.identity.results import IdentityThresholds
from tests.helpers import DummyAnnData


def test_identity_public_imports_do_not_require_scvi_at_import_time():
    identity_pkg = importlib.import_module("bridge.identity")

    assert "scvi" not in sys.modules
    assert callable(identify)
    assert callable(assess_identity_probabilities)
    assert IdentityResult.__name__ == "IdentityResult"
    assert not hasattr(identity_pkg, "identity_assessment")
    assert not hasattr(identity_pkg, "IdentityAssessmentResult")
    assert not hasattr(identity_pkg, "run_identity_assessment")


def test_top_level_public_surface_uses_notebook_api_names():
    bridge_pkg = importlib.import_module("bridge")

    assert callable(bridge_pkg.identify)
    assert callable(bridge_pkg.score)
    assert not hasattr(bridge_pkg, "identity_assessment")
    assert not hasattr(bridge_pkg, "run_identity_assessment")
    assert not hasattr(bridge_pkg, "step3")


def test_build_identity_summary_counts_candidates_and_thresholds():
    bdata = DummyAnnData(pd.DataFrame(index=["c1", "c2", "c3", "c4"]))
    candidate_mask = pd.Series([True, False, True, False], index=bdata.obs_names)
    thresholds = IdentityThresholds(
        threshold_t=0.7,
        threshold_u=0.04,
        threshold_v=0.8,
        u_raw=0.03,
        target_precision=0.85,
    )

    summary = build_identity_summary(
        bdata,
        target_class="mDA_progenitor",
        candidate_mask=candidate_mask,
        thresholds=thresholds,
        max_epochs=10,
        ensemble_size=3,
        seed=42,
        output_paths={"thresholds_json": "/tmp/demo.thresholds.json"},
    )

    assert summary["query_count"] == 4
    assert summary["target_class"] == "mDA_progenitor"
    assert summary["candidate_count"] == 2
    assert summary["non_candidate_count"] == 2
    assert summary["candidate_fraction"] == 0.5
    assert summary["thresholds"] == {
        "t": 0.7,
        "u": 0.04,
        "u_raw": 0.03,
        "v": 0.8,
        "target_precision": 0.85,
    }
    assert summary["training"] == {"max_epochs": 10, "ensemble_size": 3, "seed": 42}
    assert summary["outputs"] == {"thresholds_json": "/tmp/demo.thresholds.json"}
