from __future__ import annotations

import importlib
import json
import math
import sys

import pandas as pd
import pytest

from bridge.common.results import CLSComponentResult
from tests.helpers import DummyAnnData


def test_cls_public_imports_do_not_force_runtime_dependencies():
    sys.modules.pop("scvi", None)
    sys.modules.pop("decoupler", None)

    cls_pkg = importlib.import_module("bridge.cls")

    assert callable(cls_pkg.step3)
    assert cls_pkg.Step3Result.__name__ == "Step3Result"
    assert "scvi" not in sys.modules
    assert "decoupler" not in sys.modules


def test_step3_context_normalizes_output_dir_and_defaults(tmp_path):
    from bridge.cls import Step3Context

    bdata = DummyAnnData(pd.DataFrame(index=["q1", "q2"]))
    adata_ref = DummyAnnData(pd.DataFrame(index=["r1", "r2"]))

    ctx = Step3Context(
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
    from bridge.cls import Step3Context, component_A, component_C, component_F

    ctx = Step3Context(
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


def test_step3_rejects_unknown_component(tmp_path):
    from bridge.cls import Step3Context, step3

    ctx = Step3Context(
        bdata=DummyAnnData(pd.DataFrame(index=["q1"])),
        adata_ref=DummyAnnData(pd.DataFrame(index=["r1"])),
        target_class="mDA",
        output_dir=tmp_path,
        dataset_id="demo",
    )

    with pytest.raises(ValueError, match="Unknown Step3 components: Z"):
        step3(ctx, enabled_components=("A", "Z"))


def test_step3_with_fake_components_writes_summary_manifest_and_weighted_cls(tmp_path, monkeypatch):
    from bridge.cls import Step3Context, Step3Result, step3
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

    ctx = Step3Context(
        bdata=DummyAnnData(pd.DataFrame(index=["q1"])),
        adata_ref=DummyAnnData(pd.DataFrame(index=["r1"])),
        target_class="mDA",
        output_dir=tmp_path,
        dataset_id="demo",
    )

    result = step3(
        ctx,
        enabled_components=("A", "B"),
        component_params={"A": {"min_cells_per_batch": 5}},
        cls_weights={"A": 0.25, "B": 0.75},
    )

    assert isinstance(result, Step3Result)
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
