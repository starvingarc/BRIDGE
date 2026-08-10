"""BRIDGE public package surface."""

from bridge.workflows.config import load_config


def prescreen(*args, **kwargs):
    from bridge.prescreen.api import prescreen as _prescreen

    return _prescreen(*args, **kwargs)


def identify(*args, **kwargs):
    from bridge.identity.api import identify as _identify

    return _identify(*args, **kwargs)


def score(*args, **kwargs):
    from bridge.cls.api import score as _score

    return _score(*args, **kwargs)


__all__ = ["identify", "load_config", "prescreen", "score"]
