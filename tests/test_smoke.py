from __future__ import annotations

from pathlib import Path

from bridge.workflows.config import load_config
from bridge.workflows.report import build_report_run_plan


def test_minimal_config_loads():
    config = load_config(Path("configs/bridge.minimal.yaml"))
    assert config.dataset.id == "demo_dataset"
    assert config.identity.target_class == "RG"


def test_report_fixture_builds_dry_run_plan():
    config = load_config(Path("tests/data/report_fixture.yaml"))
    plan = build_report_run_plan(config)
    assert plan["workflow"] == "report"
    assert plan["dataset_id"] == "demo_report"
