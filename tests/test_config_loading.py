from __future__ import annotations

from pathlib import Path

import pytest

from bridge.workflows.config import ConfigValidationError, load_config


def test_load_config_resolves_relative_paths():
    config = load_config(Path("configs/bridge.minimal.yaml"))
    assert config.dataset.id == "demo_dataset"
    assert config.paths.reference_h5ad.is_absolute()
    assert config.paths.reference_h5ad.exists()
    assert config.paths.ref_model_dir.exists()
    assert config.cls.enabled_components == ["A"]


def test_load_config_requires_top_level_sections(tmp_path):
    bad_config = tmp_path / "bad.yaml"
    bad_config.write_text("version: '1'\ndataset: {id: demo, prefix: demo}\n", encoding="utf-8")
    with pytest.raises(ConfigValidationError):
        load_config(bad_config)
