from __future__ import annotations

from pathlib import Path

import yaml

from bridge.workflows import PrescreenWorkflowConfig, load_config


def test_public_config_templates_load_with_prescreen_fields():
    root = Path(__file__).resolve().parents[1]

    minimal = load_config(root / "configs" / "bridge.minimal.yaml")
    example = load_config(root / "configs" / "bridge.example.yaml")

    assert isinstance(minimal.prescreen, PrescreenWorkflowConfig)
    assert minimal.prescreen.rg_label == "Radial Glia"
    assert minimal.prescreen.train_query is False
    assert minimal.paths.whole_brain_ref_model_dir == (root / "configs" / "models" / "whole_brain_ref_model").resolve()
    assert minimal.paths.prescreen_output_dir == (root / "configs" / "outputs" / "prescreen").resolve()
    assert example.prescreen.early_stopping_patience == 10


def test_config_without_prescreen_keeps_defaults(tmp_path):
    root = Path(__file__).resolve().parents[1]
    data = yaml.safe_load((root / "configs" / "bridge.minimal.yaml").read_text(encoding="utf-8"))
    data.pop("prescreen")
    data["paths"].pop("whole_brain_ref_model_dir")
    data["paths"].pop("prescreen_output_dir")

    config_path = tmp_path / "old_config.yaml"
    config_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    cfg = load_config(config_path)

    assert cfg.prescreen.rg_label == "Radial Glia"
    assert cfg.prescreen.counts_layer == "counts"
    assert cfg.prescreen.train_query is False
    assert cfg.prescreen.max_epochs == 0
    assert cfg.paths.whole_brain_ref_model_dir is None
    assert cfg.paths.prescreen_output_dir is None
