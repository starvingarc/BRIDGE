from __future__ import annotations

import json

import pytest

from test_web_service import client, confirm_change, h5ad, new_session, settle


def uploaded(client, tmp_path):
    sid = new_session(client)["id"]
    response = client.post(f"/api/sessions/{sid}/uploads",
        files={"file": ("synthetic.h5ad", h5ad(tmp_path))})
    assert response.status_code == 200
    return sid, response.json()["uploads"][0]["id"]


def stated_facts(**updates):
    return {
        "product_name": "Research product",
        "product_family": "hpsc_mda",
        "target_cell_type": "midbrain dopaminergic progenitors",
        "target_stage": "declared progenitor stage",
        "sampling_context": "pretransplant_preparation",
        "independent_cultures": None,
        "assay": "scRNA-seq",
        "matrix_location": "X",
        "count_semantics": "raw_counts",
        "source_family_id": None,
        "sample_id_column": None,
        "capture_id_column": None,
        "gene_symbol_column": None,
        **updates,
    }


def stage(client, sid, aid, facts=None):
    response = client.post(f"/api/sessions/{sid}/intake",
        json={"upload_id": aid, "facts": facts or stated_facts()})
    assert response.status_code == 200, response.json()
    return response.json()





@pytest.mark.parametrize("family", ["unknown", "other"])
def test_confirmed_product_scope_gates_chat_and_advanced_cell_state_plans(client, tmp_path, monkeypatch, family):
    from bridge.web.provider import parse_action
    sid, aid = uploaded(client, tmp_path)
    confirm_change(client, sid, stage(client, sid, aid, stated_facts(product_family=family)))
    state = client.get(f"/api/sessions/{sid}").json()
    capability = next(item for item in state["capabilities"] if item["tool_id"] == "P0-02")
    assert "supported_product_family_required" in capability["reason_codes"]
    manual = client.post(f"/api/sessions/{sid}/prepare-analysis", json={"tool_id": "P0-02"})
    assert manual.status_code == 200
    assert manual.json()["error"] == "supported_product_family_required"
    monkeypatch.setattr("bridge.web.app.converse", lambda *args: parse_action({
        "content": '{"action":"prepare_analysis","tool_id":"P0-02"}'}))
    client.post(f"/api/sessions/{sid}/messages", json={"text": "Prepare the next cell-state plan"})
    final = settle(client, sid)
    assert final["error"] == "supported_product_family_required"
    assert client.app.state.service.load(sid)["_tool_runs"] == []


def test_confirmed_private_product_facts_never_enter_provider_context(client, tmp_path, monkeypatch):
    sid, aid = uploaded(client, tmp_path)
    confirm_change(client, sid, stage(client, sid, aid, stated_facts(
        product_name="PRIVATE_PRODUCT_SENTINEL", target_stage="PRIVATE_STAGE_SENTINEL",
        source_family_id="PRIVATE_SOURCE_SENTINEL")))
    captured = []
    from bridge.web.provider import parse_action
    def reply(settings, messages, context):
        captured.append({"messages": messages, "context": context})
        return parse_action({"content": '{"action":"reply","text":"Review the private panel."}'})
    monkeypatch.setattr("bridge.web.app.converse", reply)
    client.post(f"/api/sessions/{sid}/messages", json={"text": "What is the next stage?"})
    assert settle(client, sid)["error"] is None
    wire = json.dumps(captured)
    assert "PRIVATE_" not in wire and "private-cell-a" not in wire and "MT-ND1" not in wire
    assert captured[0]["context"]["intake_context"] == [{"upload_id": aid, "state": "confirmed",
                                                       "missing_fields": ["independent_cultures"]}]


def test_advanced_source_edit_makes_intake_stale_without_overwriting_new_facts(client, tmp_path):
    from test_web_service import declare_source
    sid, aid = uploaded(client, tmp_path)
    confirm_change(client, sid, stage(client, sid, aid))
    service = client.app.state.service
    before = service.load(sid)
    declare_source(client, sid, aid, "new-source")
    current = client.get(f"/api/sessions/{sid}/intake", params={"upload_id": aid}).json()
    assert current["state"] == "stale" and current["next_tool"] is None
    assert current["facts"]["source_family_id"] == "new-source"
    assert current["facts"]["target_cell_type"] == stated_facts()["target_cell_type"]
    confirm_change(client, sid, stage(client, sid, aid, current["facts"]))
    after = service.load(sid)
    assert after["_uploads"][aid]["declaration_start"] == before["_uploads"][aid]["declaration_start"]
    assert len(after["_intake_history"]) == 1


def test_tampered_upload_cannot_supply_intake_structure_or_confirmed_facts(client, tmp_path):
    sid, aid = uploaded(client, tmp_path)
    service = client.app.state.service
    pending = stage(client, sid, aid)
    (service.directory(sid) / "uploads" / (aid + ".h5ad")).write_bytes(b"changed")
    assert client.get(f"/api/sessions/{sid}/intake", params={"upload_id": aid}).status_code == 409
    change = pending["pending_input_change"]
    assert client.post(f"/api/sessions/{sid}/input-change/confirm", json={
        "change_id": change["id"], "change_digest": change["digest"]}).status_code == 409
    assert aid not in service.load(sid)["_asset_declarations"]


def test_native_intake_action_has_closed_typed_facts():
    from bridge.web.provider import action_tools, parse_action
    function = next(item["function"] for item in action_tools()
                    if item["function"]["name"] == "propose_intake")
    schema = function["parameters"]["properties"]["facts"]
    assert schema["type"] == "object" and schema["additionalProperties"] is False
    def message(facts):
        return {"tool_calls": [{"type": "function", "function": {
            "name": "propose_intake", "arguments": json.dumps({
                "upload_id": "a" * 32, "facts": facts})}}]}
    action = parse_action(message({"assay": "scRNA-seq"}), "deepseek_tools")
    assert action.facts.assay == "scRNA-seq"
    assert action.facts.count_semantics == "unknown"
    with pytest.raises(ValueError):
        parse_action(message({"assay": "scRNA-seq", "invented_fact": 1}), "deepseek_tools")
    with pytest.raises(ValueError):
        parse_action({"content": json.dumps({"action": "reply", "text": "no",
                      "facts": {"assay": "scRNA-seq"}})})


def test_upload_intake_reports_structure_without_observation_identities(client, tmp_path):
    sid, aid = uploaded(client, tmp_path)
    response = client.get(f"/api/sessions/{sid}/intake", params={"upload_id": aid})
    assert response.status_code == 200
    value = response.json()
    assert value["observed"]["n_observations"] == 4
    assert value["observed"]["n_genes"] == 3
    assert value["observed"]["matrix_locations"] == ["X"]
    assert value["facts"]["assay"] == "unknown"
    assert value["facts"]["count_semantics"] == "unknown"
    assert value["facts"]["product_family"] == "unknown"
    assert value["state"] == "draft"
    assert value["qc_state"] == "needs_confirmation"
    assert value["next_tool"] is None
    assert "private-cell-a" not in json.dumps(value)
    assert "MT-ND1" not in json.dumps(value)


def test_intake_is_exactly_confirmed_before_materializing_counts(client, tmp_path):
    sid, aid = uploaded(client, tmp_path)
    service = client.app.state.service
    pending = stage(client, sid, aid)
    assert pending["pending_input_change"]["kind"] == "intake"
    assert pending["plan"] is None
    before = service.load(sid)
    assert aid not in before["_asset_declarations"]
    assert before["_tool_runs"] == []
    assert client.post(f"/api/sessions/{sid}/intake/prepare",
        json={"upload_id": aid}).status_code == 409

    other = new_session(client)["id"]
    change = pending["pending_input_change"]
    assert client.post(f"/api/sessions/{other}/input-change/confirm", json={
        "change_id": change["id"], "change_digest": change["digest"]}).status_code == 409

    committed = confirm_change(client, sid, pending)
    assert committed["input_review_required"] is False and committed["plan"] is None
    current = service.load(sid)
    assert current["_asset_declarations"][aid]["matrix_semantics"] == "raw_counts"
    assert current["_asset_declarations"][aid]["assay"] == "scRNA-seq"
    assert current["_asset_declarations"][aid]["metadata"] == {}
    value = client.get(f"/api/sessions/{sid}/intake", params={"upload_id": aid}).json()
    assert value["state"] == "confirmed"
    assert value["facts"]["independent_cultures"] is None
    assert value["next_tool"] == "P0-01"


def test_replaced_intake_proposal_and_discard_do_not_commit_facts(client, tmp_path):
    sid, aid = uploaded(client, tmp_path)
    first = stage(client, sid, aid)
    second = stage(client, sid, aid, stated_facts(target_stage="another declared stage"))
    change = first["pending_input_change"]
    assert client.post(f"/api/sessions/{sid}/input-change/confirm",
        json={"change_id": change["id"], "change_digest": change["digest"]}).status_code == 409
    change = second["pending_input_change"]
    discarded = client.post(f"/api/sessions/{sid}/input-change/discard",
        json={"change_id": change["id"], "change_digest": change["digest"]})
    assert discarded.status_code == 200
    assert client.get(f"/api/sessions/{sid}/intake", params={"upload_id": aid}).json()["state"] == "draft"
    assert aid not in client.app.state.service.load(sid)["_asset_declarations"]


@pytest.mark.parametrize("updates", [
    {"matrix_location": "layers/absent"},
    {"sample_id_column": "not_a_real_column"},
    {"independent_cultures": 0},
    {"assay": "guessed-assay"},
])
def test_intake_rejects_invalid_declarations(client, tmp_path, updates):
    sid, aid = uploaded(client, tmp_path)
    response = client.post(f"/api/sessions/{sid}/intake",
        json={"upload_id": aid, "facts": stated_facts(**updates)})
    assert response.status_code == 422
    assert client.app.state.service.load(sid)["pending_input_change"] is None


def test_unknown_count_semantics_never_becomes_executable_counts(client, tmp_path):
    sid, aid = uploaded(client, tmp_path)
    confirm_change(client, sid, stage(client, sid, aid, stated_facts(
        count_semantics="unknown", product_family="unknown", target_cell_type=None,
        target_stage=None, sampling_context="unknown")))
    value = client.get(f"/api/sessions/{sid}/intake", params={"upload_id": aid}).json()
    assert value["next_tool"] is None
    assert "count_semantics" in value["missing_fields"]
    assert aid not in client.app.state.service.load(sid)["_asset_declarations"]


def test_typed_chat_intake_stages_without_inventing_confirmation(client, tmp_path, monkeypatch):
    from bridge.web.provider import parse_action

    sid, aid = uploaded(client, tmp_path)
    monkeypatch.setattr("bridge.web.app.converse", lambda *args: parse_action({"content": json.dumps({
        "action": "propose_intake", "upload_id": aid,
        "facts": {"assay": "scRNA-seq", "matrix_location": "X",
                  "count_semantics": "raw_counts", "target_cell_type": "stated target"},
    })}))
    client.post(f"/api/sessions/{sid}/messages", json={
        "text": "This is scRNA-seq; X is raw counts and has not been normalized. The target is stated target."
    })
    pending = settle(client, sid)
    assert pending["input_review_required"] is True
    assert pending["pending_input_change"]["kind"] == "intake"
    assert pending["plan"] is None
    assert aid not in client.app.state.service.load(sid)["_qc_declarations"]


def test_chat_prepare_cannot_bypass_initial_fact_confirmation(client, tmp_path, monkeypatch):
    from bridge.web.provider import parse_action

    sid, aid = uploaded(client, tmp_path)
    monkeypatch.setattr("bridge.web.app.converse", lambda *args: parse_action({"content": json.dumps({
        "action": "prepare_qc", "upload_id": aid, "matrix_location": "X"
    })}))
    client.post(f"/api/sessions/{sid}/messages",
        json={"text": "scRNA-seq, use X raw counts for QC"})
    final = settle(client, sid)
    assert final["plan"] is None
    assert aid not in client.app.state.service.load(sid)["_qc_declarations"]


def test_intake_plan_runs_real_qc_once_then_chat_reuses_its_evidence(client, tmp_path, monkeypatch):
    from bridge.web.provider import parse_action

    sid, aid = uploaded(client, tmp_path)
    confirm_change(client, sid, stage(client, sid, aid))
    proposal = client.post(f"/api/sessions/{sid}/intake/prepare",
        json={"upload_id": aid})
    assert proposal.status_code == 200, proposal.json()
    value = proposal.json()
    assert value["status"] == "awaiting_approval"
    assert value["plan"]["steps"][0]["tool_id"] == "P0-01"
    assert client.app.state.service.load(sid)["_tool_runs"] == []
    plan = value["plan"]
    approved = client.post(f"/api/sessions/{sid}/approve",
        json={"plan_id": plan["id"], "plan_digest": plan["digest"]})
    assert approved.status_code == 200, approved.json()
    final = settle(client, sid)
    assert final["plan"]["steps"][0]["status"] == "succeeded"
    service = client.app.state.service
    before = service.load(sid)
    assert len(before["_tool_runs"]) == 1
    monkeypatch.setattr("bridge.web.app.converse", lambda *args: parse_action({"content": json.dumps({
        "action": "prepare_qc", "upload_id": aid, "matrix_location": "X"
    })}))
    client.post(f"/api/sessions/{sid}/messages",
        json={"text": "Explain the existing QC; do not start another analysis."})
    after = settle(client, sid)
    assert after["plan"]["id"] == plan["id"]
    assert after["plan_history"] == before["plan_history"]
    assert service.load(sid)["_tool_runs"] == before["_tool_runs"]
    # Product-only corrections preserve canonical QC; count retraction does not.
    confirm_change(client, sid, stage(client, sid, aid, stated_facts(target_stage="revised target")))
    revised = service.load(sid)
    assert revised["_uploads"][aid]["declaration_start"] == before["_uploads"][aid]["declaration_start"]
    service.qc_asset(revised, aid, register=False)
    confirm_change(client, sid, stage(client, sid, aid, stated_facts(count_semantics="unknown")))
    retracted = service.load(sid)
    assert aid not in retracted["_asset_declarations"]
    assert retracted["_uploads"][aid]["declaration_start"] == before["_uploads"][aid]["declaration_start"] + 1
    with pytest.raises(ValueError, match="qc_declaration_retracted"):
        service.qc_asset(retracted, aid, register=False)
