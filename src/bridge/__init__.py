"""BRIDGE public package surface."""

from bridge.workflows.config import load_config


def prescreen(*args, **kwargs):
    from bridge.prescreen.api import prescreen as _prescreen

    return _prescreen(*args, **kwargs)


def identity_assessment(*args, **kwargs):
    from bridge.identity.api import identity_assessment as _identity_assessment

    return _identity_assessment(*args, **kwargs)


def run_identity_assessment(*args, **kwargs):
    from bridge.identity.api import run_identity_assessment as _run_identity_assessment

    return _run_identity_assessment(*args, **kwargs)


def step3(*args, **kwargs):
    from bridge.cls.api import step3 as _step3

    return _step3(*args, **kwargs)


__all__ = ["identity_assessment", "load_config", "prescreen", "run_identity_assessment", "step3"]
