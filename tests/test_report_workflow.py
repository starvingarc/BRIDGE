from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd

from bridge.workflows.config import load_config
from bridge.workflows.report import run_report_summary


def test_report_workflow_writes_summary_and_manifest(tmp_path):
    fixture_root = Path("tests/data")
    working_data = tmp_path / "data"
    shutil.copytree(fixture_root, working_data)

    config = load_config(working_data / "report_fixture.yaml")
    result = run_report_summary(config)

    summary_csv = Path(result["summary_csv"])
    manifest_json = Path(result["manifest_json"])
    assert summary_csv.exists()
    assert manifest_json.exists()

    df = pd.read_csv(summary_csv)
    assert set(df["component"]) == {"A", "B", "TOTAL_WEIGHTED"}

    manifest = json.loads(manifest_json.read_text(encoding="utf-8"))
    assert manifest["dataset_id"] == "demo_report"
    assert manifest["weighted_total_cls"] is not None
