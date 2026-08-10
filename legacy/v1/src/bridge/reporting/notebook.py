from __future__ import annotations

import importlib
import io
from pathlib import Path
from typing import Any

import pandas as pd


def _display_module():
    try:
        return importlib.import_module("IPython.display")
    except ImportError as exc:
        raise ImportError("Notebook display helpers require IPython. Install BRIDGE with the workflow extra or add IPython to the active environment.") from exc


def display_markdown_file(path: str | Path):
    module = _display_module()
    text = Path(path).read_text(encoding="utf-8")
    obj = module.Markdown(text)
    module.display(obj)
    return obj


def display_table_file(path: str | Path, max_rows: int = 20) -> pd.DataFrame:
    module = _display_module()
    df = pd.read_csv(path)
    module.display(df.head(max_rows))
    return df


def display_figure_file(path: str | Path):
    module = _display_module()
    obj = module.Image(filename=str(path))
    module.display(obj)
    return obj


def display_interpretation(report_or_interpretation: Any):
    module = _display_module()
    interpretation = getattr(report_or_interpretation, "interpretation", report_or_interpretation) or {}
    lines = ["## Interpretation"]
    for key, value in interpretation.items():
        lines.append(f"- **{key}:** {value}")
    obj = module.Markdown("\n".join(lines))
    module.display(obj)
    return obj



def display_matplotlib_figure(fig, *, dpi: int = 150, close: bool = True):
    module = _display_module()
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=dpi, bbox_inches="tight")
    data = buffer.getvalue()
    image = module.Image(data=data, format="png")
    module.display(image)
    if close:
        try:
            import matplotlib.pyplot as plt
            plt.close(fig)
        except Exception:
            pass
    return image
