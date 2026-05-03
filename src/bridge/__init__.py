"""BRIDGE public package surface."""

from bridge.workflows.config import load_config


def run_identity_assessment(*args, **kwargs):
    from bridge.identity.api import run_identity_assessment as _run_identity_assessment

    return _run_identity_assessment(*args, **kwargs)


def identity_assessment(*args, **kwargs):
    from bridge.identity.api import identity_assessment as _identity_assessment

    return _identity_assessment(*args, **kwargs)


def run_cls_workflow(*args, **kwargs):
    from bridge.workflows.cls import run_cls_workflow as _run_cls_workflow

    return _run_cls_workflow(*args, **kwargs)


def run_report_summary(*args, **kwargs):
    from bridge.workflows.report import run_report_summary as _run_report_summary

    return _run_report_summary(*args, **kwargs)


__all__ = ["identity_assessment", "load_config", "run_cls_workflow", "run_identity_assessment", "run_report_summary"]
