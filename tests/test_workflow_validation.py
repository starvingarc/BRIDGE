from __future__ import annotations

import pytest

from bridge.workflows.config import BridgeRunConfig, WorkflowValidationError, load_config
from bridge.workflows.cls import run_cls_workflow
from bridge.workflows.identity import run_identity_workflow


def test_identity_workflow_refuses_missing_required_input(tmp_path):
    config_path = tmp_path / "identity_missing.yaml"
    config_path.write_text(
        """
version: "1"
dataset:
  id: "demo"
  prefix: "demo_prefix"
paths:
  reference_h5ad: "missing_reference.h5ad"
  query_h5ad: "missing_query.h5ad"
  ref_model_dir: "missing_model"
  identity_output_dir: "identity"
  cls_output_dir: "cls"
  report_output_dir: "report"
runtime:
  seed: 0
  n_jobs: 1
identity:
  target_class: "RG"
  counts_layer: "counts"
  ref_label_key: "cell_subtype"
  max_epochs: 5
  plan_kwargs: {weight_decay: 0.0}
  early_stopping: false
  early_stopping_patience: 5
  ensemble_size: 2
  target_precision: 0.8
  std_quantile: 75.0
  u_min: 0.005
  entropy_threshold: 0.8
cls:
  enabled_components: ["A"]
  batch_key: "Sample"
  candidate_flag_prefix: "is_candidate_"
  ref_label_key: "cell_subtype"
  a: {}
  b: {}
  c: {}
  d: {}
  e: {}
  f: {}
report:
  summary_filename: "summary.csv"
  manifest_filename: "manifest.json"
""".strip(),
        encoding="utf-8",
    )
    config = load_config(config_path)
    with pytest.raises(WorkflowValidationError):
        run_identity_workflow(config, dry_run=True)


def test_cls_workflow_refuses_missing_component_prerequisites(tmp_path):
    config_path = tmp_path / "cls_missing.yaml"
    config_path.write_text(
        """
version: "1"
dataset:
  id: "demo"
  prefix: "demo_prefix"
paths:
  reference_h5ad: "../tests/data/minimal_inputs/reference.h5ad"
  query_h5ad: "../tests/data/minimal_inputs/query.h5ad"
  ref_model_dir: "../tests/data/minimal_inputs/ref_model"
  identity_output_dir: "missing_identity_outputs"
  cls_output_dir: "cls"
  report_output_dir: "report"
runtime:
  seed: 0
  n_jobs: 1
identity:
  target_class: "RG"
  counts_layer: "counts"
  ref_label_key: "cell_subtype"
  max_epochs: 5
  plan_kwargs: {weight_decay: 0.0}
  early_stopping: false
  early_stopping_patience: 5
  ensemble_size: 2
  target_precision: 0.8
  std_quantile: 75.0
  u_min: 0.005
  entropy_threshold: 0.8
cls:
  enabled_components: ["A"]
  batch_key: "Sample"
  candidate_flag_prefix: "is_candidate_"
  ref_label_key: "cell_subtype"
  a: {}
  b: {}
  c: {}
  d: {}
  e: {}
  f: {}
report:
  summary_filename: "summary.csv"
  manifest_filename: "manifest.json"
""".strip(),
        encoding="utf-8",
    )
    config = load_config(config_path)
    with pytest.raises(WorkflowValidationError):
        run_cls_workflow(config, dry_run=True)
