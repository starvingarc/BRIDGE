from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib
import json

import pytest
from fastapi import HTTPException

from bridge.web.inputs import Selection
from test_web_service import client
from test_web_inputs import context_upload, choice, approve
from test_p0_07_product_comparison_stability import _payloads, SCHEMAS
from test_p0_12_graft_assessment import _objects


def helper(service):
    name = "bridge.web.conditional_inputs"
    assert importlib.util.find_spec(name) is not None, "conditional input helper must exist"
    return importlib.import_module(name).ConditionalInputs(service)


def register(service, state, tool, mode, role, schema, payload):
    return service.inputs.add_object(state, tool_id=tool, mode_id=mode, role=role,
        schema_ref=schema, object_version="0.1.0", data=json.dumps(payload).encode())


def comparison(client, tmp_path, mutation=None):
    sid, aid = context_upload(client, tmp_path)
    service = client.app.state.service
    state = service.load(sid)
    payloads = _payloads()
    payloads["comparison_stability_spec"]["status"] = "frozen"
    for key, payload in payloads.items():
        if key.startswith("bundle-"):
            payload["metrics"][0]["evidence_state"] = "measured"
    if mutation:
        mutation(payloads)
    objects = []
    for key, payload in payloads.items():
        role = "product_evidence_bundle" if key.startswith("bundle-") else key
        identifier = register(service, state, "P0-07", "legacy_comparison", role, SCHEMAS[role], payload)
        objects.append({"role": role, "input_id": identifier})
    service.save(state)
    return service, state, Selection.model_validate(choice("P0-07", "legacy_comparison", objects)), aid


def graft(service, state):
    case, spec, bundle = _objects()
    case["originating_preparation_id"] = "preparation:baseline-1"
    objects = []
    for role, schema, payload in (
        ("graft_case", "bridge://schemas/graft-case/v0.1", case),
        ("assessment_spec", "bridge://schemas/graft-assessment-spec/v0.1", spec),
        ("evidence_bundle", "bridge://schemas/graft-evidence-bundle/v0.1", bundle),
    ):
        identifier = register(service, state, "P0-12", "graft_assessment", role, schema, payload)
        objects.append({"role": role, "input_id": identifier})
    return Selection.model_validate(choice("P0-12", "graft_assessment", objects))


def decision(h, state, proposed, method="confirm"):
    return getattr(h, method)(state, proposed["id"], proposed["digest"], state["_input_revision"])


def test_registered_measured_comparison_requires_confirmation_and_ordinary_approval(client, tmp_path):
    service, state, selection, aid = comparison(client, tmp_path)
    h = helper(service)
    directory = h.public(state)
    entry = directory["comparison"]["entries"][0]
    assert entry["category"] == "comparable"
    assert entry["execution_available"] is True
    before = deepcopy(state["_tool_runs"])
    proposed = h.propose(state, selection, state["_input_revision"])
    assert "P0-07" not in state["_input_selections"]
    with pytest.raises(HTTPException):
        decision(h, state, proposed, "prepare")
    decision(h, state, proposed)
    assert state["_tool_runs"] == before
    decision(h, state, proposed, "prepare")
    assert state["status"] == "awaiting_approval"
    assert [s["tool_id"] for s in state["plan"]["steps"]] == ["P0-07"]
    assert state["_tool_runs"] == before
    request = json.loads(state["_plan"]["steps"][0]["approved_request_json"])
    assert request["assets"] == [] and request["parameters"] == {}
    completed = approve(client, state["id"], state["plan"])
    assert completed["plan"]["status"] in {"completed", "partial"}
    assert [r["tool_id"] for r in service.load(state["id"])["_tool_runs"]] == ["P0-07"]


@pytest.mark.parametrize("mutation,expected,reason", [
    (lambda p: p["comparison_stability_spec"].update(status="candidate"),
     "background_only", "frozen_comparison_spec_required"),
    (lambda p: p["bundle-comparator-1"]["metrics"][0].update(evidence_state="shadow"),
     "background_only", "measured_comparison_evidence_required"),
    (lambda p: p["bundle-comparator-1"].update(protocol_refs=[]),
     "excluded", "confounding_metadata_missing_protocol"),
    (lambda p: p["bundle-comparator-1"].update(timepoint={"basis": "in_vitro_day", "label": "D40", "order": 40}),
     "excluded", "required_field_mismatch_timepoint"),
])
def test_background_and_excluded_are_not_selected_for_execution(client, tmp_path, mutation, expected, reason):
    service, state, selection, _ = comparison(client, tmp_path, mutation)
    h = helper(service)
    entry = h.public(state)["comparison"]["entries"][0]
    assert entry["category"] == expected
    assert reason in entry["diagnostics"]["reason_codes"]
    proposed = h.propose(state, selection, state["_input_revision"])
    with pytest.raises(HTTPException):
        decision(h, state, proposed)
    assert state["_tool_runs"] == [] and "P0-07" not in state["_input_selections"]


@pytest.mark.parametrize("change", ["revision", "checksum", "source", "invalidated"])
def test_stale_or_unauthorized_confirmation_fails_closed(client, tmp_path, change):
    service, state, selection, _ = comparison(client, tmp_path)
    h = helper(service)
    proposed = h.propose(state, selection, state["_input_revision"])
    identifier = selection.object_inputs[-1].input_id
    record = state["_input_objects"][identifier]
    if change == "revision":
        state["_input_revision"] += 1
    elif change == "checksum":
        from pathlib import Path
        Path(record["path"]).write_bytes(b"{}")
    elif change == "source":
        record["source"] = "unregistered_external"
    else:
        record["receipt_file"] = "invalidated-source.json"
        state["_invalidated_receipts"] = {"invalidated-source.json": "confirmed-change"}
    with pytest.raises(HTTPException):
        decision(h, state, proposed)
    assert state["_tool_runs"] == [] and "P0-07" not in state["_input_selections"]


def test_cancelled_selection_appends_history_and_never_runs_single_product(client, tmp_path):
    service, state, selection, _ = comparison(client, tmp_path)
    h = helper(service)
    before = deepcopy(state["_input_selections"])
    proposed = h.propose(state, selection, state["_input_revision"])
    decision(h, state, proposed, "cancel")
    assert state["_input_selections"] == before
    with pytest.raises(HTTPException):
        decision(h, state, proposed)
    assert [e["event"] for e in state["_conditional_history"]] == ["proposed", "cancelled"]
    assert state["_tool_runs"] == []
    another = h.propose(state, selection, state["_input_revision"])
    decision(h, state, another)
    decision(h, state, another, "cancel")
    assert "P0-07" not in state["_input_selections"]
    assert state["_tool_runs"] == []


def test_new_selection_after_confirmation_is_blocked_before_prepare(client, tmp_path):
    service, state, selection, _ = comparison(client, tmp_path)
    h = helper(service)
    proposed = h.propose(state, selection, state["_input_revision"])
    decision(h, state, proposed)
    state["_input_selections"]["P0-07"]["object_inputs"].pop()
    assert h.selected_blocker(state, "P0-07") is not None
    with pytest.raises(HTTPException):
        decision(h, state, proposed, "prepare")


def test_graft_missing_vs_authorized_matching_inputs_preserve_pretransplant_receipts(client, tmp_path):
    service, state, _, aid = comparison(client, tmp_path)
    h = helper(service)
    assert h.public(state)["graft"]["execution_available"] is False
    # A real pre-transplant QC receipt is retained byte-for-byte.
    state["_input_selections"]["P0-01"] = choice("P0-01", None, assets=[aid])
    service.prepare_analysis(state, "P0-01")
    approve(client, state["id"], state["plan"])
    state = service.load(state["id"])
    receipts = deepcopy(state["_tool_runs"])
    paths = {r["file"]: service.directory(state["id"]) / "receipts" / r["file"] for r in receipts}
    checksums = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in paths.items()}
    before_selection = deepcopy(state["_input_selections"]["P0-01"])
    selected = graft(service, state)
    entry = h.public(state)["graft"]["entries"][0]
    assert entry["execution_available"] is True
    proposed = h.propose(state, selected, state["_input_revision"])
    decision(h, state, proposed)
    decision(h, state, proposed, "prepare")
    assert [s["tool_id"] for s in state["plan"]["steps"]] == ["P0-12"]
    assert state["_tool_runs"] == receipts
    assert state["_input_selections"]["P0-01"] == before_selection
    assert {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in paths.items()} == checksums


def test_graft_unmatched_preparation_is_unavailable(client, tmp_path):
    service, state, _, _ = comparison(client, tmp_path)
    selected = graft(service, state)
    case_id = next(c.input_id for c in selected.object_inputs if c.role == "graft_case")
    case = service.inputs.verify(state, state["_input_objects"][case_id])
    case["originating_preparation_id"] = "preparation:not-registered"
    replacement = register(service, state, "P0-12", "graft_assessment", "graft_case",
                           "bridge://schemas/graft-case/v0.1", case)
    selected.object_inputs[0].input_id = replacement
    h = helper(service)
    proposed = h.propose(state, selected, state["_input_revision"])
    assert "matching_preparation_required" in proposed["diagnostics"]["reason_codes"]
    with pytest.raises(HTTPException):
        decision(h, state, proposed)
    assert state["_tool_runs"] == []


def test_confirmation_history_revision_is_checksum_bound(client, tmp_path):
    service, state, selection, _ = comparison(client, tmp_path)
    h = helper(service)
    proposed = h.propose(state, selection, state["_input_revision"])
    decision(h, state, proposed)
    state["_input_revision"] += 1
    state["_conditional_history"][-1]["input_revision"] = state["_input_revision"]
    assert h.selected_blocker(state, "P0-07") is not None
    with pytest.raises(HTTPException):
        decision(h, state, proposed, "prepare")


def test_unregistered_source_is_excluded_without_exposing_private_paths(client, tmp_path):
    service, state, selection, _ = comparison(client, tmp_path)
    identifier = selection.object_inputs[-1].input_id
    state["_input_objects"][identifier]["source"] = "unregistered_external"
    public = helper(service).public(state)
    entry = next(row for row in public["comparison"]["entries"] if row["id"] == identifier)
    assert entry["category"] == "excluded"
    assert entry["diagnostics"]["reason_codes"] == sorted(set(entry["diagnostics"]["reason_codes"]))
    assert "source_access_unverified" in entry["diagnostics"]["reason_codes"]
    assert state["_input_objects"][identifier]["path"] not in json.dumps(public)


def test_graft_preparation_dependency_change_stales_confirmation(client, tmp_path):
    service, state, _, _ = comparison(client, tmp_path)
    selection = graft(service, state)
    h = helper(service)
    proposed = h.propose(state, selection, state["_input_revision"])
    decision(h, state, proposed)
    support = proposed["diagnostics"]["support_input_ids"][0]
    state["_input_objects"][support]["source"] = "unregistered_external"
    assert h.selected_blocker(state, "P0-12") is not None
    with pytest.raises(HTTPException):
        decision(h, state, proposed, "prepare")


def test_sample_identifier_is_not_inferred_to_be_a_preparation(client, tmp_path):
    def sample_only(payloads):
        payloads["bundle-baseline-1"]["product_case"]["source_unit_kind"] = "sample"
    service, state, _, _ = comparison(client, tmp_path, sample_only)
    selection = graft(service, state)
    h = helper(service)
    proposed = h.propose(state, selection, state["_input_revision"])
    assert "matching_preparation_required" in proposed["diagnostics"]["reason_codes"]
    with pytest.raises(HTTPException):
        decision(h, state, proposed)
