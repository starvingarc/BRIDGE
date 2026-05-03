from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


@dataclass(frozen=True)
class ReportResult:
    figures: dict[str, str]
    tables: dict[str, str]
    markdown_report: str
    manifest_json: str
    interpretation: dict[str, str]


COMPONENT_LABELS = {
    "A": "Identity",
    "B": "Pseudo-bulk",
    "C": "Transfer AUC",
    "D": "Neighborhood",
    "E": "Pseudotime",
    "F": "Regulon",
}

DEFAULT_PROTOCOL_COLORS = [
    "#a0d8ef",
    "#ffb6c1",
    "#b8e0d2",
    "#f7c59f",
    "#c6e5d9",
    "#d7bde2",
]

STEP_COLORS = {
    "on": "#dd8452",
    "off": "#4c72b0",
    "neutral": "#d9d9d9",
    "accent": "#f28c5e",
}


def ensure_dir(path: str | Path) -> Path:
    out = Path(path)
    out.mkdir(parents=True, exist_ok=True)
    return out


def _missing_dependency(name: str, extra: str = "notebook") -> ImportError:
    return ImportError(
        f"BRIDGE report plotting requires '{name}'. Install BRIDGE with the '{extra}' extra or add the package to the active environment."
    )


def _optional_import(name: str, *, extra: str = "notebook"):
    try:
        return importlib.import_module(name)
    except ImportError as exc:
        raise _missing_dependency(name, extra=extra) from exc


def import_pyplot():
    matplotlib = _optional_import("matplotlib", extra="notebook")
    try:
        matplotlib.use("Agg", force=False)
    except Exception:
        pass
    return _optional_import("matplotlib.pyplot", extra="notebook")


def import_scanpy():
    return _optional_import("scanpy", extra="runtime")


def import_seaborn():
    return _optional_import("seaborn", extra="notebook")


def require_obs_columns(adata, columns: Iterable[str], *, context: str) -> None:
    missing = [column for column in columns if column not in adata.obs.columns]
    if missing:
        raise KeyError(f"{context} requires adata.obs columns: {', '.join(missing)}")


def write_table(df: pd.DataFrame, path: str | Path) -> str:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    return str(out)


def write_json(payload: dict[str, Any], path: str | Path) -> str:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    return str(out)


def write_markdown(lines: list[str], path: str | Path) -> str:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return str(out)


def save_figure(fig, path_base: str | Path, *, formats=("png",), dpi: int = 300) -> str:
    base = Path(path_base)
    base.parent.mkdir(parents=True, exist_ok=True)
    primary: str | None = None
    for fmt in formats:
        out = base.parent / f"{base.name}.{fmt}"
        fig.savefig(out, dpi=dpi, bbox_inches="tight")
        if primary is None:
            primary = str(out)
    try:
        import_pyplot().close(fig)
    except Exception:
        pass
    if primary is None:
        raise ValueError("formats must include at least one figure format.")
    return primary


def has_umap(adata) -> bool:
    obsm = getattr(adata, "obsm", None)
    return obsm is not None and "X_umap" in obsm


def save_optional_umap(
    adata,
    *,
    color,
    path_base: str | Path,
    title: str | None = None,
    cmap: str | None = None,
    palette: dict[str, str] | None = None,
    formats=("png",),
    dpi: int = 300,
) -> str | None:
    if not has_umap(adata):
        return None
    sc = import_scanpy()
    plt = import_pyplot()
    fig = sc.pl.umap(
        adata,
        color=color,
        frameon=False,
        title=title,
        cmap=cmap,
        palette=palette,
        show=False,
        return_fig=True,
    )
    if fig is None:
        fig = plt.gcf()
    return save_figure(fig, path_base, formats=formats, dpi=dpi)


def value_counts_frame(series: pd.Series, *, label: str, count_name: str = "count") -> pd.DataFrame:
    counts = series.astype(str).value_counts(dropna=False)
    return counts.rename_axis(label).reset_index(name=count_name)


def fraction_text(value: Any) -> str:
    try:
        return f"{float(value) * 100:.1f}%"
    except Exception:
        return "n/a"
