"""Read-only display payloads for the workbench views; no scientific computation runs here."""
import json
import math
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import JSONResponse

MAX_TREE_BYTES = 32 * 1024 * 1024
MAX_TREE_CELLS = 200_000


def validate_tree(value) -> dict:
    """Accepts only the documented tree shape so the browser never renders an ambiguous payload."""
    if not isinstance(value, dict):
        raise ValueError("tree_not_object")
    subtypes, nodes, edges, cells = (value.get(k) for k in ("subtypes", "nodes", "edges", "cells"))
    if not (isinstance(subtypes, list) and subtypes and all(isinstance(s, str) and s for s in subtypes)):
        raise ValueError("tree_subtypes_invalid")
    if not (isinstance(nodes, list) and len(nodes) == len(subtypes)):
        raise ValueError("tree_nodes_invalid")
    finite = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
    if not all(isinstance(n, list) and len(n) == 3 and all(finite(v) for v in n) for n in nodes):
        raise ValueError("tree_nodes_invalid")
    count = len(subtypes)
    if not (isinstance(edges, list) and all(isinstance(e, list) and len(e) == 2 and all(type(i) is int and 0 <= i < count for i in e) for e in edges)):
        raise ValueError("tree_edges_invalid")
    if not (isinstance(cells, list) and 0 < len(cells) <= MAX_TREE_CELLS):
        raise ValueError("tree_cells_invalid")
    for cell in cells:
        if not (isinstance(cell, list) and len(cell) == 7 and all(finite(v) for v in cell)
                and type(cell[3]) is int and 0 <= cell[3] < count and cell[6] in (0, 1)):
            raise ValueError("tree_cells_invalid")
    source = value.get("source")
    return {"subtypes": subtypes, "nodes": nodes, "edges": edges, "cells": cells,
            "source": source if isinstance(source, str) else ""}


def load_tree(path: Path) -> dict:
    if path.stat().st_size > MAX_TREE_BYTES:
        raise ValueError("tree_too_large")
    return validate_tree(json.loads(path.read_text(encoding="utf-8")))


def install_workbench_http(app, service):
    @app.get("/api/workbench/devtree")
    def developmental_tree():
        path = service.settings.workbench_tree_path
        if path is None:
            raise HTTPException(404, "workbench_tree_unavailable")
        try:
            tree = load_tree(path)
        except (OSError, ValueError):
            raise HTTPException(422, "workbench_tree_unavailable") from None
        from bridge.tool_packages.p0_02_cell_state.quick_atlas_reference import digest
        tree["version"] = digest(tree)
        return JSONResponse(tree, headers={"Cache-Control": "no-store"})
