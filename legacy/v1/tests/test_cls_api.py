from __future__ import annotations

import importlib
import json
import math
import sys

import pandas as pd
import pytest

from bridge.common.results import CLSComponentResult
from tests.helpers import DummyAnnData


class MiniAnnData(DummyAnnData):
    def __init__(self, obs: pd.DataFrame, obsm: dict | None = None):
        super().__init__(obs)
        self.obsm = dict(obsm or {})

    def __getitem__(self, index):
        if isinstance(index, tuple):
            index = index[0]
        obs = self.obs.loc[index].copy() if not isinstance(index, slice) else self.obs.iloc[index].copy()
        return MiniAnnData(obs, self.obsm)

    def copy(self):
        return MiniAnnData(self.obs.copy(), self.obsm)


def test_cls_public_imports_do_not_force_runtime_dependencies():
    sys.modules.pop("scvi", None)
    sys.modules.pop("decoupler", None)

    cls_pkg = importlib.import_module("bridge.cls")

    assert callable(cls_pkg.score)
    assert cls_pkg.CLSResult.__name__ == "CLSResult"
    assert not hasattr(cls_pkg, "Step3Context")
    assert not hasattr(cls_pkg, "Step3Result")
    assert not hasattr(cls_pkg, "step3")
    assert "scvi" not in sys.modules
    assert "decoupler" not in sys.modules


def test_cls_context_normalizes_output_dir_and_defaults(tmp_path):
    from bridge.cls import CLSContext

    bdata = DummyAnnData(pd.DataFrame(index=["q1", "q2"]))
    adata_ref = DummyAnnData(pd.DataFrame(index=["r1", "r2"]))

    ctx = CLSContext(
        bdata=bdata,
        adata_ref=adata_ref,
        target_class="mDA",
        output_dir=tmp_path / "step3",
        dataset_id="demo",
    )

    assert ctx.output_dir == tmp_path / "step3"
    assert ctx.batch_key == "Sample"
    assert ctx.candidate_flag_prefix == "is_candidate_"
    assert ctx.ref_label_key == "cell_subtype"


def test_component_dependency_validation_messages(tmp_path):
    from bridge.cls import CLSContext, component_A, component_C, component_F

    ctx = CLSContext(
        bdata=DummyAnnData(pd.DataFrame(index=["q1"])),
        adata_ref=DummyAnnData(pd.DataFrame(index=["r1"])),
        target_class="mDA",
        output_dir=tmp_path,
        dataset_id="demo",
    )

    with pytest.raises(ValueError, match="probs_ref_cal"):
        component_A(ctx)
    with pytest.raises(ValueError, match="probs_ref_cal"):
        component_C(ctx)
    with pytest.raises(ValueError, match="ref_sceniclike"):
        component_F(ctx)


def test_component_d_auto_trains_query_when_embedding_must_be_generated(tmp_path, monkeypatch):
    from bridge.cls import CLSContext, component_D
    import bridge.cls.component_d as component_d

    captured = {}

    def fake_compute_D_and_save(**kwargs):
        captured.update(kwargs)
        score_df = pd.DataFrame({"batch": ["b1"], "n_candidate": [3], "sD": [0.8]})
        return score_df, 0.8, {"meta": {}}

    monkeypatch.setattr(component_d, "compute_D_and_save", fake_compute_D_and_save)
    ctx = CLSContext(
        bdata=MiniAnnData(pd.DataFrame({"Sample": ["b1"]}, index=["q1"]), obsm={}),
        adata_ref=MiniAnnData(pd.DataFrame(index=["r1"]), obsm={"X_scVI": [[0.0, 1.0]]}),
        target_class="mDA",
        output_dir=tmp_path,
        dataset_id="demo",
        ref_model_dir=tmp_path / "target_ref_model",
    )

    result = component_D(ctx)

    assert result.global_score == 0.8
    assert captured["train_query"] is True


def test_component_e_falls_back_to_available_reference_and_query_representations(tmp_path, monkeypatch):
    from bridge.cls import CLSContext, component_E
    import bridge.cls.component_e as component_e

    captured = {}

    def fake_compute_E_and_save(**kwargs):
        captured.update(kwargs)
        score_df = pd.DataFrame({"branch": ["main"], "branch_weight": [1.0], "E_dev": [0.6]})
        return score_df, 0.6, {"meta": {}}

    monkeypatch.setattr(component_e, "compute_E_and_save", fake_compute_E_and_save)
    ctx = CLSContext(
        bdata=MiniAnnData(
            pd.DataFrame({"is_candidate_mDA": [True], "Sample": ["b1"]}, index=["q1"]),
            obsm={"X_pca": [[0.1, 0.2]]},
        ),
        adata_ref=MiniAnnData(
            pd.DataFrame({"cell_subtype": ["mDA"]}, index=["r1"]),
            obsm={"X_scVI": [[0.0, 1.0]]},
        ),
        target_class="mDA",
        output_dir=tmp_path,
        dataset_id="demo",
    )

    result = component_E(ctx)

    assert result.global_score == 0.6
    assert captured["rep_key_ref"] == "X_scVI"
    assert captured["rep_key_org"] == "X_pca"


def test_score_rejects_unknown_component(tmp_path):
    from bridge.cls import CLSContext, score

    ctx = CLSContext(
        bdata=DummyAnnData(pd.DataFrame(index=["q1"])),
        adata_ref=DummyAnnData(pd.DataFrame(index=["r1"])),
        target_class="mDA",
        output_dir=tmp_path,
        dataset_id="demo",
    )

    with pytest.raises(ValueError, match="Unknown CLS components: Z"):
        score(ctx, enabled_components=("A", "Z"))


def test_score_with_fake_components_writes_summary_manifest_and_weighted_cls(tmp_path, monkeypatch):
    from bridge.cls import CLSContext, CLSResult, score
    import bridge.cls.api as api

    calls = []

    def fake_component(name: str, score: float):
        def _run(ctx, **params):
            calls.append((name, params))
            score_df = pd.DataFrame({"batch": ["b1"], "n_cells": [10], f"s{name}": [score]})
            return CLSComponentResult(component=name, score_df=score_df, global_score=score, meta={"params": params})

        return _run

    monkeypatch.setattr(api, "component_A", fake_component("A", 0.2))
    monkeypatch.setattr(api, "component_B", fake_component("B", 0.8))

    ctx = CLSContext(
        bdata=DummyAnnData(pd.DataFrame(index=["q1"])),
        adata_ref=DummyAnnData(pd.DataFrame(index=["r1"])),
        target_class="mDA",
        output_dir=tmp_path,
        dataset_id="demo",
    )

    result = score(
        ctx,
        enabled_components=("A", "B"),
        component_params={"A": {"min_cells_per_batch": 5}},
        cls_weights={"A": 0.25, "B": 0.75},
    )

    assert isinstance(result, CLSResult)
    assert calls == [("A", {"min_cells_per_batch": 5}), ("B", {})]
    assert math.isclose(result.weighted_total_cls, 0.65)
    assert result.summary.loc[0, "cls_A"] == 0.2
    assert result.summary.loc[0, "cls_B"] == 0.8
    assert result.output_paths["summary_csv"].endswith("demo/summary.csv")
    assert result.output_paths["manifest_json"].endswith("demo/manifest.json")

    summary_df = pd.read_csv(result.output_paths["summary_csv"])
    assert summary_df.loc[0, "weighted_total_cls"] == 0.65

    manifest = json.loads((tmp_path / "demo" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["dataset_id"] == "demo"
    assert manifest["target_class"] == "mDA"
    assert manifest["enabled_components"] == ["A", "B"]
    assert manifest["weighted_total_cls"] == 0.65
