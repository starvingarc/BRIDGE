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


@pytest.mark.parametrize("mode", ["case_query", "case_append_v2"])
def test_graph_continuation_keeps_existing_graph_and_report_sources(tmp_path, mode):
    controls, state, directory = chain(tmp_path)
    state["_input_objects"]["old-assertions"] = {"path": str(directory / "runs" / "measured.json")}
    before = {"tool_id": "P0-09", "mode_id": "case_initial_v2",
              "object_inputs": [{"input_id": "old-assertions", "role": "compilation_bundle"}]}
    after = {"tool_id": "P0-09", "mode_id": mode,
             "object_inputs": [{"input_id": "base-graph", "role": "evidence_graph_manifest"}]}
    impact = controls.selection_impact(state, before, after)
    assert impact["affected"] == []
    assert len(impact["reusable"]) == 6
    assert impact["new_approval_required"] is True


def test_adding_an_evidence_requirement_does_not_retract_existing_results(tmp_path):
    controls, state, _ = chain(tmp_path)
    before = {"tool_id": "P0-09", "mode_id": "case_initial_v2", "asset_ids": [],
              "measurement_spec_ref": None,
              "object_inputs": [{"input_id": "retained", "role": "claim_registry"}]}
    after = {**before, "object_inputs": [*before["object_inputs"],
             {"input_id": "additional", "role": "measurement_result"}]}
    impact = controls.selection_impact(state, before, after)
    assert impact["affected"] == []
    assert len(impact["reusable"]) == 6


def test_p008_new_source_selected_from_frozen_scope_preserves_compiled_history(tmp_path):
    from bridge.web.scientific_inputs import digest

    controls, state, directory = setup_state(tmp_path)
    old_path = directory / "runs" / "pluri-gate.json"
    new_path = directory / "runs" / "dissoc-gate.json"
    sufficiency = directory / "runs" / "pluri-sufficiency.json"
    receipt(state, directory, "P0-08", "pluri-gate", [old_path], [sufficiency])
    receipt(state, directory, "P0-09", "pluri-graph", [sufficiency], [directory / "runs" / "graph.json"])
    state["_input_objects"] = {
        "pluri": {"path": str(old_path), "sha256": "a" * 64},
        "dissoc": {"path": str(new_path), "sha256": "b" * 64},
    }
    before = {"tool_id": "P0-08", "mode_id": "default", "asset_ids": [],
              "measurement_spec_ref": None,
              "object_inputs": [{"role": "domain_gate_input", "input_id": "pluri"}]}
    after = {**before, "object_inputs": [{"role": "domain_gate_input", "input_id": "dissoc"}]}
    scope = {"input_revision": state["_input_revision"], "binding": {
        "resources": {"dissoc": state["_input_objects"]["dissoc"]},
        "append_p008": {"base_selection": before, "selection": after}}}
    state["_assessment"] = {"status": "proposed", "scope": scope, "scope_digest": digest(scope)}
    impact = controls.selection_impact(state, before, after)
    assert impact["affected"] == []
    assert [row["tool_id"] for row in impact["reusable"]] == ["P0-08", "P0-09"]
    assert impact["new_approval_required"] is True


def test_p008_correction_still_invalidates_old_measurement_and_graph(tmp_path):
    from bridge.web.scientific_inputs import digest

    controls, state, directory = setup_state(tmp_path)
    old_path = directory / "runs" / "pluri-gate.json"
    sufficiency = directory / "runs" / "pluri-sufficiency.json"
    receipt(state, directory, "P0-08", "pluri-gate", [old_path], [sufficiency])
    receipt(state, directory, "P0-09", "pluri-graph", [sufficiency], [directory / "runs" / "graph.json"])
    state["_input_objects"] = {
        "pluri": {"path": str(old_path), "sha256": "a" * 64},
        "dissoc": {"path": str(directory / "runs" / "dissoc-gate.json"), "sha256": "b" * 64},
        "correction": {"path": str(directory / "runs" / "corrected-gate.json"), "sha256": "c" * 64},
    }
    before = {"tool_id": "P0-08", "mode_id": "default", "asset_ids": [],
              "measurement_spec_ref": None,
              "object_inputs": [{"role": "domain_gate_input", "input_id": "pluri"}]}
    append = {**before, "object_inputs": [{"role": "domain_gate_input", "input_id": "dissoc"}]}
    correction = {**before, "object_inputs": [{"role": "domain_gate_input", "input_id": "correction"}]}
    scope = {"input_revision": state["_input_revision"], "binding": {
        "resources": {"dissoc": state["_input_objects"]["dissoc"]},
        "append_p008": {"base_selection": before, "selection": append}}}
    state["_assessment"] = {"status": "proposed", "scope": scope, "scope_digest": digest(scope)}
    impact = controls.selection_impact(state, before, correction)
    assert [row["tool_id"] for row in impact["affected"]] == ["P0-08", "P0-09"]
    assert impact["new_approval_required"] is True


def test_matrix_change_invalidates_transitive_outputs_not_other_upload(tmp_path):
    controls, state, _ = chain(tmp_path)
    impact = controls.impact(state, "query", "asset", [{"field": "matrix_location"}])
    assert [row["tool_id"] for row in impact["affected"]] == ["P0-01", "P0-02", "P0-04", "P0-09", "P0-10"]
    assert len(impact["reusable"]) == 1
    assert impact["new_approval_required"] is True
    assert state["_invalidated_receipts"] == {}



@pytest.mark.parametrize(("kind", "changes"), [
    ("source", [{"field": "source_family_id"}]),
    ("intake", [{"field": "source_family_id"}]),
    ("intake", [{"field": "source_family_id"}, {"field": "product_family"}]),
    ("intake", [{"field": "product_name"}, {"field": "target_stage"}, {"field": "source_family_id"}]),
])
def test_source_correction_reuses_qc_but_invalidates_source_dependent_analysis(tmp_path, kind, changes):
    controls, state, _ = chain(tmp_path)
    impact = controls.impact(state, "query", kind, changes)
    assert [row["tool_id"] for row in impact["affected"]] == ["P0-02", "P0-04", "P0-09", "P0-10"]
    assert [row["tool_id"] for row in impact["reusable"]] == ["P0-01", "P0-01"]
    assert state["_invalidated_receipts"] == {}


def test_product_only_change_preserves_qc_and_native_but_updates_interpretation(tmp_path):
    controls, state, _ = chain(tmp_path)
    impact = controls.impact(state, "query", "intake", [{"field": "target_cell_type"}])
    assert [row["tool_id"] for row in impact["affected"]] == ["P0-04", "P0-09", "P0-10"]
    assert [row["tool_id"] for row in impact["reusable"]] == ["P0-01", "P0-02", "P0-01"]
    impact = controls.impact(state, "query", "intake", [{"field": "gene_symbol_column"}])
    assert len(impact["affected"]) == 5


@pytest.mark.parametrize("field", ["matrix_location", "count_semantics", "assay", "sample_id_column", "capture_id_column", "gene_symbol_column"])
def test_mixed_source_product_and_qc_declaration_change_still_invalidates_qc(tmp_path, field):
    controls, state, _ = chain(tmp_path)
    impact = controls.impact(state, "query", "intake", [
        {"field": "source_family_id"}, {"field": "product_family"}, {"field": field}])
    assert [row["tool_id"] for row in impact["affected"]] == ["P0-01", "P0-02", "P0-04", "P0-09", "P0-10"]


@pytest.mark.parametrize("register", [False, True])
def test_retired_qc_is_rejected_before_any_receipt_or_catalog_access(register, monkeypatch):
    from bridge.web.qc_results import QcResults
    qc = QcResults(None, lambda: 0)
    def unexpected_receipt_access(*args):
        pytest.fail("Invalidated QC must be rejected before receipt access")
    monkeypatch.setattr(qc, "receipt_asset_id", unexpected_receipt_access)
    state = {"_tool_runs": [{"tool_id": "P0-01", "state": "succeeded", "file": "retired.json"}],
             "_invalidated_receipts": {"retired.json": "confirmed-change"}}
    for enrich in (False, True):
        with pytest.raises(ValueError, match="^completed_qc_required$"):
            qc.asset(state, "upload", register=register, enrich=enrich)
    assert state["_invalidated_receipts"] == {"retired.json": "confirmed-change"}


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


@pytest.mark.parametrize(("role", "tool"), [
    ("program_spec", "P0-06"), ("state_role_map", "P0-03"),
    ("development_window_spec", "P0-04"), ("cohort_manifest", "P0-07"),
])
def test_object_revision_only_invalidates_its_consumers_and_descendants(tmp_path, role, tool):
    controls, state, directory = setup_state(tmp_path)
    changed = directory / "objects" / (role + ".json")
    unrelated = directory / "objects" / "other.json"
    state["_input_objects"]["old"] = {"path": str(changed)}
    derived = directory / "runs" / "changed.json"
    graph = directory / "runs" / "graph.json"
    receipt(state, directory, "P0-02", "native", [], [unrelated], assets=["query"])
    receipt(state, directory, tool, "changed", [changed, unrelated], [derived])
    receipt(state, directory, "P0-09", "graph", [derived], [graph])
    receipt(state, directory, "P0-10", "report", [graph], [])
    receipt(state, directory, tool, "unrelated", [unrelated], [])
    impact = controls.impact(state, "", "selection", [], root_input_ids=["old"])
    assert [row["tool_id"] for row in impact["affected"]] == [tool, "P0-09", "P0-10"]
    assert [row["tool_id"] for row in impact["reusable"]] == ["P0-02", tool]
    assert state["_invalidated_receipts"] == {}


from web_support import client, confirm_change
from test_web_inputs import context_upload, choice, approve


def test_replacing_completed_selection_requires_confirmation_and_preserves_history(client, tmp_path):
    sid, _ = context_upload(client, tmp_path)
    url = f"/api/sessions/{sid}"
    old = choice("P0-12", "not_provided")
    assert client.post(url + "/analysis-inputs", json=old).status_code == 200
    plan = client.post(url + "/prepare-analysis", json={"tool_id": "P0-12"}).json()["plan"]
    assert approve(client, sid, plan)["plan"]["status"] == "completed"
    service = client.app.state.service
    before = service.load(sid)
    receipts = list(before["_tool_runs"])
    old_bytes = {row["file"]: (service.directory(sid) / "receipts" / row["file"]).read_bytes()
                 for row in receipts}
    changed = choice("P0-12", "graft_assessment")
    response = client.post(url + "/analysis-inputs", json=changed)
    assert response.status_code == 200, response.json()
    pending = response.json()["pending_input_change"]
    assert pending["kind"] == "selection"
    assert [item["tool_id"] for item in pending["impact"]["affected"]] == ["P0-12"]
    assert service.load(sid)["_input_selections"]["P0-12"] == old
    assert client.post(url + "/input-change/discard", json={
        "change_id": pending["id"], "change_digest": pending["digest"]}).status_code == 200
    assert service.load(sid)["_input_selections"]["P0-12"] == old
    response = client.post(url + "/analysis-inputs", json=changed)
    confirm_change(client, sid, response.json())
    after = service.load(sid)
    assert after["_input_selections"]["P0-12"] == changed
    assert after["_tool_runs"] == receipts
    assert set(after["_invalidated_receipts"]) == set(old_bytes)
    assert all((service.directory(sid) / "receipts" / name).read_bytes() == data
               for name, data in old_bytes.items())
    assert client.post(url + "/input-change/confirm", json={
        "change_id": pending["id"], "change_digest": pending["digest"]}).status_code == 409

def test_product_rename_only_updates_report_and_preserves_measurement_graph_bytes(tmp_path):
    controls, state, directory = chain(tmp_path)
    before = {p.name: p.read_bytes() for p in (directory / "receipts").iterdir()}
    impact = controls.impact(state, "query", "intake", [{"field": "product_name"}])
    assert [row["tool_id"] for row in impact["affected"]] == ["P0-10"]
    assert [row["tool_id"] for row in impact["reusable"]] == ["P0-01", "P0-02", "P0-04", "P0-09", "P0-01"]
    assert {p.name: p.read_bytes() for p in (directory / "receipts").iterdir()} == before
    assert state["_invalidated_receipts"] == {}

@pytest.mark.parametrize('reverse', [False, True])
def test_complementary_expression_and_candidate_selection_preserves_results(tmp_path, reverse):
    controls, state, _ = chain(tmp_path)
    candidate = {'tool_id': 'P0-02', 'mode_id': None, 'asset_ids': ['query'],
                 'object_inputs': [], 'measurement_spec_ref': 'CELLSTATE-scRNA-celltypist-candidate-v0.1'}
    expression = {**candidate, 'measurement_spec_ref': 'EXPRESSION-exploration-v0.1',
                  'expression_analysis': {'exploration': {'embedding_key': 'X_umap'}}}
    before, after = (expression, candidate) if reverse else (candidate, expression)
    impact = controls.selection_impact(state, before, after)
    assert impact['affected'] == []
    assert len(impact['reusable']) == 6
    assert impact['new_approval_required'] is True
    changed_asset = controls.selection_impact(state, before, {**after, 'asset_ids': ['other']})
    assert [row['tool_id'] for row in changed_asset['affected']] == ['P0-02', 'P0-04', 'P0-09', 'P0-10']
    changed_method = controls.selection_impact(state, before, {**after, 'measurement_spec_ref': 'another-method'})
    assert len(changed_method['affected']) == 4
