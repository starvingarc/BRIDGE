"""Shared reporting utilities for BRIDGE notebook workflows."""

from bridge.reporting.core import (
    COMPONENT_LABELS,
    DEFAULT_PROTOCOL_COLORS,
    ReportResult,
    ensure_dir,
    import_pyplot,
    import_scanpy,
    plot_umap,
    require_obs_columns,
    save_figure,
    save_optional_umap,
    write_json,
    write_markdown,
    write_table,
)

__all__ = [
    "COMPONENT_LABELS",
    "DEFAULT_PROTOCOL_COLORS",
    "ReportResult",
    "ensure_dir",
    "import_pyplot",
    "import_scanpy",
    "plot_umap",
    "require_obs_columns",
    "save_figure",
    "save_optional_umap",
    "write_json",
    "write_markdown",
    "write_table",
]
