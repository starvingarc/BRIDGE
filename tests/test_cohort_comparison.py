"""Confirmed cross-session versions connected to real P0-07 plan execution."""
import json
import pytest
from web_support import client, settle
from sample_analysis_support import call, setup_sample, qc, register
from test_p0_07_product_comparison_stability import _payloads, SCHEMAS


def bound_comparison(c, tmp_path, mutation=None, second_day=10, same_sample=False):
    rid, _, version, run, first_sample = setup_sample(c, tmp_path)
    base = f"/api/researches/{rid}"
    # Two real registered samples, same experiment and day. No independence claim.
    from web_support import h5ad
    upload = c.post(base + "/uploads", files={"file": ("second.h5ad", h5ad(tmp_path))}).json()
    second_sample = call(c, "POST", base + f"/runs/{run['id']}/samples", {
        "expected_version": 2, "day": second_day, "assay": "scRNA-seq", "material_id": upload["id"]})
    if same_sample:
        second_sample = first_sample
    analyses = []
    for sample in (first_sample, second_sample):
        sid, receipt = qc(c, rid, sample["material_id"])
        analyses.append(register(c, rid, sample, sid, receipt))
    members = [{"analysis_id": a["id"], "snapshot_sha256": a["snapshot_sha256"], "role": role}
               for a, role in zip(analyses, ("baseline", "comparator"))]
    cohort = call(c, "POST", base + "/analysis-cohorts", {"expected_version": 0, "members": members})
    cohort = call(c, "POST", base + f"/analysis-cohorts/{cohort['id']}/confirm",
                  {"expected_version": 1, "digest": cohort["digest"]})
    payloads = _payloads()
    payloads["comparison_stability_spec"]["status"] = "frozen"
    for key, a in zip(("bundle-baseline-1", "bundle-comparator-1"), analyses):
        bundle = payloads[key]
        ref = lambda value: {"object_id": value, "object_version": "1.0.0"}
        bundle["product_case"].update(source_unit_kind="sample", sample_or_preparation_ref=ref("sample:" + a["sample_id"]))
        bundle["batch_refs"] = [ref("run:" + a["run_id"])]
        bundle["protocol_refs"] = [ref("protocol-version:" + a["protocol_version_id"])]
        bundle["provenance_refs"].append(ref("analysis:" + a["id"]))
        bundle["metrics"][0]["evidence_state"] = "measured"
        bundle["timepoint"] = {"basis": "in_vitro_day", "label": "D10", "order": 10}
    if mutation:
        mutation(payloads)
    sid = analyses[0]["session_id"]
    choices, bindings = [], []
    for key, payload in payloads.items():
        role = "product_evidence_bundle" if key.startswith("bundle-") else key
        state = call(c, "GET", f"/api/sessions/{sid}/analysis-inputs")
        before = {o["id"] for o in state["objects"]}
        reply = c.post(f"/api/sessions/{sid}/analysis-inputs/objects", params={
            "tool_id": "P0-07", "mode_id": "legacy_comparison", "role": role,
            "schema_ref": SCHEMAS[role], "object_version": "0.1.0"},
            files={"file": ("synthetic.json", json.dumps(payload).encode())})
        assert reply.status_code == 200, reply.text
        registered = call(c, "GET", f"/api/sessions/{sid}/analysis-inputs")
        added = [o["id"] for o in registered["objects"] if o["id"] not in before]
        assert len(added) == 1
        choices.append({"role": role, "input_id": added[0]})
        if key.startswith("bundle-"):
            a = analyses[0] if key == "bundle-baseline-1" else analyses[1]
            bindings.append({"analysis_id": a["id"], "bundle_input_id": added[0]})
    state = call(c, "GET", f"/api/sessions/{sid}")
    body = {
        "session_id": sid, "cohort_digest": cohort["digest"],
        "expected_revision": state["conditional_inputs"]["input_revision"],
        "selection": {"tool_id": "P0-07", "mode_id": "legacy_comparison", "asset_ids": [],
                      "object_inputs": choices, "measurement_spec_ref": None},
        "members": bindings,
    }
    endpoint = base + f"/analysis-cohorts/{cohort['id']}/comparison-proposals"
    return rid, analyses, cohort, endpoint, body


def confirm_and_prepare(c, sid, proposed):
    root = f"/api/sessions/{sid}"
    body = {"draft_id": proposed["id"], "draft_digest": proposed["digest"],
            "expected_revision": proposed["input_revision"]}
    confirmed = call(c, "POST", root + "/conditional-inputs/confirm", body)
    body["expected_revision"] = confirmed["conditional_inputs"]["input_revision"]
    return call(c, "POST", root + "/conditional-inputs/prepare", body)


def test_cross_session_cohort_reaches_real_comparison_only_after_plan_approval(client, tmp_path):
    rid, analyses, cohort, endpoint, body = bound_comparison(client, tmp_path)
    service = client.app.state.service
    sid = body["session_id"]
    before = service.load(sid)["_tool_runs"]
    proposal = call(client, "POST", endpoint, body)
    assert proposal["category"] == "comparable"
    assert proposal["cohort_binding"]["cohort_id"] == cohort["id"]
    assert proposal["cohort_binding"]["attribution"] == "user_declared"
    assert service.load(sid)["_tool_runs"] == before
    from fastapi.testclient import TestClient
    from account_support import create_test_app
    from web_support import login
    with TestClient(create_test_app(service.settings)) as restarted:
        login(restarted)
        restored = call(restarted, "GET", f"/api/sessions/{sid}")
        restored = next(x for x in restored["conditional_inputs"]["selections"] if x["id"] == proposal["id"])
        assert restored["digest"] == proposal["digest"]
        assert restored["cohort_binding"] == proposal["cohort_binding"]
        state = confirm_and_prepare(restarted, sid, restored)
    assert state["status"] == "awaiting_approval"
    assert service.load(sid)["_tool_runs"] == before
    plan = state["plan"]
    call(client, "POST", f"/api/sessions/{sid}/approve", {"plan_id": plan["id"], "plan_digest": plan["digest"]})
    done = settle(client, sid)
    assert done["plan"]["status"] in {"completed", "partial"}
    state = service.load(sid)
    receipt = state["_tool_runs"][-1]
    assert receipt["tool_id"] == "P0-07" and receipt["state"] in {"succeeded", "partial"}
    run, _ = service.inputs.producer_objects(state, receipt, "P0-07", set())
    artifact = next(a for a in run.artifacts if a.kind == "product_comparison_stability_profile")
    from bridge.web.inputs import checked_bytes
    profile = json.loads(checked_bytes(service, state, artifact.path, artifact.sha256))
    assert profile["metric_contrasts"][0]["delta_comparator_minus_baseline"] == pytest.approx(0.2)
    assert profile["overall_score"] is None and profile["overall_rank"] is None
    assert call(client, "GET", f"/api/researches/{rid}/analyses/{analyses[1]['id']}")["snapshot_sha256"] == analyses[1]["snapshot_sha256"]
    assert str(service.root) not in json.dumps(proposal)


@pytest.mark.parametrize("phase", ["confirm", "prepare", "execute"])
def test_deleted_source_stales_bound_proposal_at_every_execution_gate(client, tmp_path, phase):
    rid, analyses, _, endpoint, body = bound_comparison(client, tmp_path)
    sid = body["session_id"]
    proposal = call(client, "POST", endpoint, body)
    root = f"/api/sessions/{sid}"
    decision = {"draft_id": proposal["id"], "draft_digest": proposal["digest"],
                "expected_revision": proposal["input_revision"]}
    if phase != "confirm":
        state = call(client, "POST", root + "/conditional-inputs/confirm", decision)
        decision["expected_revision"] = state["conditional_inputs"]["input_revision"]
    if phase == "execute":
        state = call(client, "POST", root + "/conditional-inputs/prepare", decision)
    call(client, "DELETE", "/api/sessions/" + analyses[1]["session_id"], {})
    if phase in {"confirm", "prepare"}:
        call(client, "POST", root + "/conditional-inputs/" + phase, decision, status=409)
    else:
        plan = state["plan"]
        response = client.post(root + "/approve", json={"plan_id": plan["id"], "plan_digest": plan["digest"]})
        assert response.status_code in {200, 409}, response.text
        if response.status_code == 200:
            settle(client, sid)
    current = call(client, "GET", root)
    saved = next(x for x in current["conditional_inputs"]["selections"] if x["id"] == proposal["id"])
    assert saved["status"] == "stale" and saved["execution_available"] is False
    assert all(r["tool_id"] != "P0-07" for r in client.app.state.service.load(sid)["_tool_runs"])


def test_bundle_attribution_must_match_selected_sample_and_manifest_role(client, tmp_path):
    rid, _, cohort, endpoint, body = bound_comparison(client, tmp_path)
    pending = call(client, "POST", f"/api/researches/{rid}/analysis-cohorts", {"expected_version": 0, "members": cohort["members"]})
    call(client, "POST", f"/api/researches/{rid}/analysis-cohorts/{pending["id"]}/comparison-proposals",
         {**body, "cohort_digest": pending["digest"]}, status=409)
    call(client, "POST", endpoint, {**body, "members": [body["members"][0], body["members"][0]]}, status=422)
    swapped = [dict(m, bundle_input_id=body["members"][1-i]["bundle_input_id"])
               for i, m in enumerate(body["members"])]
    response = call(client, "POST", endpoint, {**body, "members": swapped}, status=409)
    assert response["detail"] == "cohort_bundle_binding_mismatch"
    call(client, "POST", endpoint, {**body, "cohort_digest": "0" * 64}, status=409)
    # A role-compatible but different owned research cannot host the selection.
    other = call(client, "POST", "/api/researches", {"name": "Other research"})["id"]
    sid = call(client, "POST", "/api/sessions", {"research_id": other})["id"]
    call(client, "POST", endpoint, {**body, "session_id": sid}, status=404)
    from bridge.web.accounts import NOTICE_VERSION
    client.cookies.clear()
    call(client, "POST", "/api/register", {"username": "other-comparison-reader",
         "password": "synthetic strong password", "notice_version": NOTICE_VERSION})
    call(client, "POST", endpoint, body, status=404)


def test_incompatible_timepoints_remain_blocked_by_existing_comparison_contract(client, tmp_path):
    def mutation(payloads):
        payloads["bundle-comparator-1"]["timepoint"] = {"basis": "in_vitro_day", "label": "D40", "order": 40}
    _, _, _, endpoint, body = bound_comparison(client, tmp_path, mutation, second_day=40)
    proposal = call(client, "POST", endpoint, body)
    assert proposal["category"] == "excluded"
    assert "required_field_mismatch_timepoint" in proposal["diagnostics"]["reason_codes"]
    call(client, "POST", f"/api/sessions/{body['session_id']}/conditional-inputs/confirm", {
        "draft_id": proposal["id"], "draft_digest": proposal["digest"],
        "expected_revision": proposal["input_revision"]}, status=409)


def test_reanalysis_of_one_sample_is_not_two_product_comparison_units(client, tmp_path):
    _, _, _, endpoint, body = bound_comparison(client, tmp_path, same_sample=True)
    response = call(client, "POST", endpoint, body, status=409)
    assert response["detail"] == "cohort_duplicate_sample"
    assert all(r["tool_id"] != "P0-07" for r in client.app.state.service.load(body["session_id"])["_tool_runs"])


def test_comparison_admission_does_not_read_unselected_mapping_results(client, tmp_path, monkeypatch):
    rid, _, _, endpoint, body = bound_comparison(client, tmp_path)
    service = client.app.state.service
    # The real workbench renderer verifies every assessment. A broken unrelated
    # assessment must have no bearing on these selected, intact analyses.
    from fastapi import HTTPException
    def unavailable_workbench(*args):
        raise HTTPException(409, "mapping_result_unavailable")
    monkeypatch.setattr(service.research_objects, "workbench", unavailable_workbench)
    if hasattr(service.cohort_comparisons, "get_workbench"):
        monkeypatch.setattr(service.cohort_comparisons, "get_workbench", unavailable_workbench)
    proposal = call(client, "POST", endpoint, body)
    assert proposal["category"] == "comparable"
    prepared = confirm_and_prepare(client, body["session_id"], proposal)
    assert prepared["status"] == "awaiting_approval"
