from __future__ import annotations

import importlib
import sys

import pytest


def test_report_modules_import_without_runtime_plotting_dependencies():
    for name in ["scanpy", "scvi", "decoupler"]:
        sys.modules.pop(name, None)

    prescreen_report = importlib.import_module("bridge.prescreen.report")
    identity_report = importlib.import_module("bridge.identity.report")
    cls_report = importlib.import_module("bridge.cls.report")

    assert callable(prescreen_report.write_report)
    assert callable(identity_report.write_report)
    assert callable(cls_report.write_report)
    assert callable(cls_report.compare_reports)
    assert "scanpy" not in sys.modules
    assert "scvi" not in sys.modules
    assert "decoupler" not in sys.modules


def test_missing_matplotlib_dependency_is_reported_lazily(monkeypatch):
    from bridge.reporting.core import import_pyplot

    real_import = importlib.import_module

    def fake_import(name, *args, **kwargs):
        if name.startswith("matplotlib"):
            raise ImportError("matplotlib intentionally missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", fake_import)

    with pytest.raises(ImportError, match="matplotlib"):
        import_pyplot()
