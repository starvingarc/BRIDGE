"""Workflow entrypoints."""

from bridge.workflows.config import (
    BridgeConfigBatch,
    BridgeRunConfig,
    CLSWorkflowConfig,
    ConfigValidationError,
    DatasetConfig,
    IdentityWorkflowConfig,
    PathsConfig,
    ReportWorkflowConfig,
    RuntimeConfig,
    WorkflowValidationError,
    load_config,
    load_config_list,
)


def run_identity_workflow(*args, **kwargs):
    from bridge.workflows.identity import run_identity_workflow as _run_identity_workflow

    return _run_identity_workflow(*args, **kwargs)


def run_cls_workflow(*args, **kwargs):
    from bridge.workflows.cls import run_cls_workflow as _run_cls_workflow

    return _run_cls_workflow(*args, **kwargs)


def run_report_summary(*args, **kwargs):
    from bridge.workflows.report import run_report_summary as _run_report_summary

    return _run_report_summary(*args, **kwargs)


def run_report_summary_batch(*args, **kwargs):
    from bridge.workflows.report import run_report_summary_batch as _run_report_summary_batch

    return _run_report_summary_batch(*args, **kwargs)


__all__ = [
    "BridgeConfigBatch",
    "BridgeRunConfig",
    "CLSWorkflowConfig",
    "ConfigValidationError",
    "DatasetConfig",
    "IdentityWorkflowConfig",
    "PathsConfig",
    "ReportWorkflowConfig",
    "RuntimeConfig",
    "WorkflowValidationError",
    "load_config",
    "load_config_list",
    "run_cls_workflow",
    "run_identity_workflow",
    "run_report_summary",
    "run_report_summary_batch",
]
