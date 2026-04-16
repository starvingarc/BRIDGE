from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd

from bridge.workflows.config import load_config, load_config_list
from bridge.workflows.report import run_report_summary, run_report_summary_batch


def test_report_summary_includes_step2_fields(tmp_path):
    fixture_root = Path("tests/data")
    working_data = tmp_path / "data"
    shutil.copytree(fixture_root, working_data)

    config = load_config(working_data / "report_fixture_step2.yaml")
    result = run_report_summary(config)

    summary_df = pd.read_csv(result["summary_csv"])
    expected_columns = {
        "dataset_id",
        "target_class",
        "n_query",
        "n_ref",
        "threshold_t",
        "threshold_u",
        "threshold_u_raw",
        "threshold_v",
        "candidate_count",
        "candidate_fraction",
        "cls_A",
        "cls_B",
        "weighted_total_cls",
    }
    assert expected_columns.issubset(set(summary_df.columns))
    assert summary_df.loc[0, "dataset_id"] == "demo_report"

    manifest = json.loads(Path(result["manifest_json"]).read_text(encoding="utf-8"))
    assert "step2_artifacts" in manifest
    assert manifest["target_class"] == "RG"


def test_report_summary_batch_writes_combined_summary(tmp_path):
    fixture_root = Path("tests/data")
    working_data = tmp_path / "data"
    shutil.copytree(fixture_root, working_data)

    report_copy = working_data / "report_fixture_copy.yaml"
    report_copy.write_text((working_data / "report_fixture_step2.yaml").read_text(encoding="utf-8").replace("demo_report", "demo_report_copy"), encoding="utf-8")

    copy_dir = working_data / "report_fixture" / "cls_output" / "demo_report_copy"
    shutil.copytree(working_data / "report_fixture" / "cls_output" / "demo_report", copy_dir)
    copy_identity = working_data / "report_fixture_step2_copy" / "identity_outputs"
    copy_identity.mkdir(parents=True, exist_ok=True)
    shutil.copy2(working_data / "report_fixture_step2" / "identity_outputs" / "demo_prefix.thresholds.json", copy_identity / "demo_prefix_copy.thresholds.json")
    shutil.copy2(working_data / "report_fixture_step2" / "identity_outputs" / "demo_prefix.bdata_step2.h5ad", copy_identity / "demo_prefix_copy.bdata_step2.h5ad")

    report_copy.write_text(
        report_copy.read_text(encoding="utf-8")
        .replace("demo_prefix", "demo_prefix_copy")
        .replace("report_fixture_step2/identity_outputs", "report_fixture_step2_copy/identity_outputs")
        .replace("report_fixture_step2/generated", "report_fixture_step2_copy/generated"),
        encoding="utf-8",
    )

    config_list = working_data / "real_batch.yaml"
    config_list.write_text(
        "configs:\n  - report_fixture_step2.yaml\n  - report_fixture_copy.yaml\n",
        encoding="utf-8",
    )

    batch = load_config_list(config_list)
    result = run_report_summary_batch(batch)
    combined_df = pd.read_csv(result["combined_summary_csv"])
    assert set(combined_df["dataset_id"]) == {"demo_report", "demo_report_copy"}
