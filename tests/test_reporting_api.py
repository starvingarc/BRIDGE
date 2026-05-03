from __future__ import annotations

import importlib
import sys
from pathlib import Path

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



def test_save_figure_preserves_dotted_path_base(tmp_path):
    from bridge.reporting.core import import_pyplot, save_figure

    plt = import_pyplot()
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])

    out = save_figure(fig, tmp_path / "demo_dataset.prescreen_counts")

    assert Path(out).name == "demo_dataset.prescreen_counts.png"
    assert (tmp_path / "demo_dataset.prescreen_counts.png").exists()
    assert not (tmp_path / "demo_dataset.png").exists()


def test_notebook_display_helpers_render_files(monkeypatch, tmp_path):
    import importlib
    from types import SimpleNamespace

    calls = []

    class FakeMarkdown:
        def __init__(self, text):
            self.text = text

    class FakeImage:
        def __init__(self, filename):
            self.filename = filename

    def fake_display(obj):
        calls.append(obj)

    real_import = importlib.import_module

    def fake_import(name, *args, **kwargs):
        if name == "IPython.display":
            return SimpleNamespace(Markdown=FakeMarkdown, Image=FakeImage, display=fake_display)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", fake_import)

    from bridge.reporting.notebook import display_figure_file, display_interpretation, display_markdown_file, display_table_file
    from bridge.reporting import ReportResult

    md = tmp_path / "report.md"
    md.write_text("# Report\n", encoding="utf-8")
    table = tmp_path / "table.csv"
    table.write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
    fig = tmp_path / "figure.png"
    fig.write_bytes(b"fake")
    report = ReportResult(figures={}, tables={}, markdown_report=str(md), manifest_json="manifest.json", interpretation={"overview": "hello"})

    display_markdown_file(md)
    df = display_table_file(table, max_rows=1)
    display_figure_file(fig)
    display_interpretation(report)

    assert df.shape == (2, 2)
    assert len(calls) == 4
    assert isinstance(calls[0], FakeMarkdown)
    assert isinstance(calls[2], FakeImage)
    assert "overview" in calls[3].text



def test_display_matplotlib_figure_emits_png_image(monkeypatch):
    import importlib
    from types import SimpleNamespace

    calls = []

    class FakeImage:
        def __init__(self, data=None, format=None, filename=None):
            self.data = data
            self.format = format
            self.filename = filename

    def fake_display(obj):
        calls.append(obj)

    real_import = importlib.import_module

    def fake_import(name, *args, **kwargs):
        if name == "IPython.display":
            return SimpleNamespace(Image=FakeImage, display=fake_display)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", fake_import)

    from bridge.reporting.core import import_pyplot
    from bridge.reporting.notebook import display_matplotlib_figure

    plt = import_pyplot()
    fig, ax = plt.subplots()
    ax.plot([0, 1], [1, 0])

    image = display_matplotlib_figure(fig)

    assert calls == [image]
    assert image.format == "png"
    assert image.filename is None
    assert image.data.startswith(b"\x89PNG")



def test_plot_umap_skips_without_umap_without_scanpy_import():
    import sys
    import pandas as pd
    from bridge.reporting import plot_umap
    from tests.helpers import DummyAnnData

    sys.modules.pop("scanpy", None)
    adata = DummyAnnData(pd.DataFrame({"label": ["a", "b"]}, index=["c1", "c2"]))

    assert plot_umap(adata, color="label") is None
    assert "scanpy" not in sys.modules
