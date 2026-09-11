"""Dependency invalidation uses exact saved requests, not tool-name majority voting."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from bridge.web.control import Controls
from bridge.web.inputs import Inputs


def setup_state(tmp_path):
    directory = tmp_path / "session"
    (directory / "receipts").mkdir(parents=True)
    service = SimpleNamespace(directory=lambda sid: directory)
    controls = Controls(service)
    state = {"id": "session", "_input_revision": 3, "_tool_runs": [],
             "_input_objects": {}, "_invalidated_receipts": {}}
    return controls, state, directory


def receipt(state, directory, tool, name, inputs, outputs, assets=()):
    payload = {"request": {"tool_id": tool, "assets": [{"asset_id": x} for x in assets],
                           "object_inputs": [{"path": str(x)} for x in inputs]},
               "execution_state": "succeeded",
               "artifacts": [{"path": str(x)} for x in outputs]}
    raw = json.dumps(payload).encode()
    filename = name + ".json"
    (directory / "receipts" / filename).write_bytes(raw)
    row = {"file": filename, "sha256": hashlib.sha256(raw).hexdigest(),
           "tool_id": tool, "state": "succeeded"}
    state["_tool_runs"].append(row)
    return row


def chain(tmp_path):
    controls, state, directory = setup_state(tmp_path)
    upload = directory / "uploads" / "query.h5ad"
    qc = directory / "runs" / "qc.json"
    native = directory / "runs" / "native.json"
    measured = directory / "runs" / "measured.json"
    graph = directory / "runs" / "graph.json"
    receipt(state, directory, "P0-01", "qc", [upload], [qc])
    receipt(state, directory, "P0-02", "native", [qc], [native])
    receipt(state, directory, "P0-04", "measured", [native], [measured])
    receipt(state, directory, "P0-09", "graph", [measured], [graph])
    receipt(state, directory, "P0-10", "report", [graph], [])
    receipt(state, directory, "P0-01", "other", [directory / "uploads" / "other.h5ad"], [])
    return controls, state, directory


def test_matrix_change_invalidates_transitive_outputs_not_other_upload(tmp_path):
    controls, state, _ = chain(tmp_path)
    impact = controls.impact(state, "query", "asset", [{"field": "matrix_location"}])
    assert [row["tool_id"] for row in impact["affected"]] == ["P0-01", "P0-02", "P0-04", "P0-09", "P0-10"]
    assert len(impact["reusable"]) == 1
    assert impact["new_approval_required"] is True
    assert state["_invalidated_receipts"] == {}


def test_product_only_change_preserves_qc_and_native_but_updates_interpretation(tmp_path):
    controls, state, _ = chain(tmp_path)
    impact = controls.impact(state, "query", "intake", [{"field": "target_cell_type"}])
    assert [row["tool_id"] for row in impact["affected"]] == ["P0-04", "P0-09", "P0-10"]
    assert [row["tool_id"] for row in impact["reusable"]] == ["P0-01", "P0-02", "P0-01"]
    impact = controls.impact(state, "query", "intake", [{"field": "gene_symbol_column"}])
    assert len(impact["affected"]) == 5


def test_nested_structured_dependency_is_traced_and_receipt_corruption_blocks(tmp_path):
    controls, state, directory = setup_state(tmp_path)
    obj = directory / "objects" / "bound.json"
    state["_input_objects"]["bound"] = {
        "path": str(obj), "dependencies": [{"path": str(directory / "uploads" / "query.h5ad")}]
    }
    row = receipt(state, directory, "P0-04", "measured", [obj], [])
    assert len(controls.impact(state, "query", "asset", [])["affected"]) == 1
    (directory / "receipts" / row["file"]).write_bytes(b"{}")
    with pytest.raises(HTTPException) as caught:
        controls.impact(state, "query", "asset", [])
    assert caught.value.detail == "input_change_dependency_unavailable"


def test_invalidated_receipt_cannot_be_selected_as_current_but_file_remains(tmp_path):
    controls, state, directory = chain(tmp_path)
    row = state["_tool_runs"][0]
    state["_invalidated_receipts"][row["file"]] = "change"
    from bridge.web.evidence import _verified_receipt
    with pytest.raises(ValueError, match="input_revision_invalidated_output"):
        _verified_receipt(SimpleNamespace(service=controls.service), state, row)
    assert (directory / "receipts" / row["file"]).is_file()
    impact = controls.impact(state, "query", "source", [])
    assert row["sha256"] not in {item["receipt_sha256"] for item in impact["affected"]}
