"""Bound workbench conversations use the existing authenticated Agent HTTP flow."""
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from account_support import create_test_app, login_test_account
from multiuser_support import multi_clients
from model_wire_contract import assert_model_context
from bridge.web.runtime import Settings


@pytest.fixture
def client(tmp_path):
    settings = Settings(storage_root=tmp_path / "conversations", origin="http://testserver",
                        model_base_url="https://provider.invalid/v1", model="test-model", model_api_key="test-key")
    with TestClient(create_test_app(settings)) as value:
        login_test_account(value)
        yield value


def call(client, method, path, body=None, status=200):
    response = client.request(method, path, **({"json": body} if body is not None else {}))
    assert response.status_code == status, response.text
    return response.json()


def make_research(client, name="Synthetic conversation research"):
    return call(client, "POST", "/api/researches", {"name": name})["id"]


def make_run(client, rid, name="Synthetic round"):
    base = f"/api/researches/{rid}"
    p = call(client, "POST", base + "/protocols",
             {"name": "Synthetic source protocol", "origin": "lab", "expected_version": 0})
    v = call(client, "PATCH", base + f"/protocols/{p['id']}/versions/{p['latest']['id']}",
             {"expected_version": 1, "total_days": 28})
    v = call(client, "POST", base + f"/protocols/{p['id']}/versions/{v['id']}/confirm",
             {"expected_version": v["revision"]})
    run = call(client, "POST", base + "/runs", {"name": name, "protocol_version_id": v["id"],
        "expected_version": 0, "state": "differentiating", "start_date": "2026-10-01"})
    return p, v, run


def url(rid, run_id=None):
    return f"/api/researches/{rid}" + (f"/runs/{run_id}" if run_id else "") + "/conversation"


def test_bound_conversations_are_idempotent_separate_from_legacy_and_survive_restart(client):
    rid = make_research(client)
    _, _, run = make_run(client, rid)
    legacy = call(client, "POST", "/api/sessions", {"research_id": rid})
    for address in (url(rid), url(rid, run["id"])):
        assert call(client, "GET", address, status=404)["detail"] == "conversation_not_found"
    general = call(client, "POST", url(rid), {})
    scoped = call(client, "POST", url(rid, run["id"]), {})
    assert len({legacy["id"], general["id"], scoped["id"]}) == 3
    assert (general["conversation_kind"], general["run_id"]) == ("research", None)
    assert (scoped["conversation_kind"], scoped["run_id"]) == ("run", run["id"])
    assert legacy["conversation_kind"] is None and legacy["run_id"] is None
    for address, expected in ((url(rid), general), (url(rid, run["id"]), scoped)):
        assert call(client, "GET", address)["id"] == expected["id"]
        assert call(client, "POST", address, {})["id"] == expected["id"]
    service = client.app.state.service
    with TestClient(create_test_app(service.settings)) as restarted:
        login_test_account(restarted)
        assert call(restarted, "GET", url(rid, run["id"]))["id"] == scoped["id"]
        assert call(restarted, "POST", url(rid), {})["id"] == general["id"]
    assert call(client, "GET", f"/api/researches/{rid}")["session_count"] == 3
    assert general["uploads"] == scoped["uploads"] == []
    assert general["plan"] is scoped["plan"] is None


def test_concurrent_creation_and_archiving_preserve_one_binding(client):
    rid = make_research(client)
    _, _, run = make_run(client, rid)
    address = url(rid, run["id"])
    with ThreadPoolExecutor(max_workers=4) as pool:
        answers = list(pool.map(lambda _: call(client, "POST", address, {}), range(4)))
    sid = answers[0]["id"]
    assert {a["id"] for a in answers} == {sid}
    call(client, "PATCH", f"/api/sessions/{sid}", {"archived": True})
    archived = call(client, "POST", address, {})
    assert archived["id"] == sid and archived["archived"] is True
    call(client, "DELETE", f"/api/sessions/{sid}", {})
    call(client, "GET", address, status=404)
    replacement = call(client, "POST", address, {})
    assert replacement["id"] != sid
    assert call(client, "GET", f"/api/researches/{rid}")["session_count"] == 1


def test_conversation_binding_cannot_cross_accounts_researches_or_be_supplied_by_client(tmp_path):
    with multi_clients(tmp_path) as (_, alice, bob, admin):
        rid = make_research(alice, "PRIVATE ALICE RESEARCH")
        _, _, run = make_run(alice, rid, "PRIVATE ALICE ROUND")
        other_rid = make_research(alice)
        for other in (bob, admin):
            for address in (url(rid), url(rid, run["id"])):
                for method, body in (("GET", None), ("POST", {})):
                    result = call(other, method, address, body, status=404)
                    assert "PRIVATE" not in str(result)
        call(alice, "POST", url(other_rid, run["id"]), {}, status=404)
        call(alice, "POST", url(rid, "f" * 32), {}, status=404)
        call(alice, "POST", url(rid), {"run_id": run["id"]}, status=422)
        call(alice, "POST", "/api/sessions", {"research_id": rid, "run_id": run["id"]}, status=422)
        scoped = call(alice, "POST", url(rid, run["id"]), {})
        call(bob, "GET", f"/api/sessions/{scoped['id']}", status=404)
        call(alice, "POST", f"/api/sessions/{scoped['id']}/messages",
             {"text": "Hello", "context": {"run_id": "f" * 32}}, status=422)


def provider_stub(monkeypatch, captures, *, entered=None, release=None):
    import json
    import httpx
    from web_support import skill_read_response
    original = httpx.Client

    def respond(request):
        payload = json.loads(request.content)
        context = json.loads(payload["messages"][0]["content"].split("Safe execution context: ", 1)[1])
        captures.append((payload, context))
        assert_model_context("workbench", context["workbench_context"])
        read = skill_read_response(payload)
        if read is not None:
            return read
        if entered is not None:
            entered.set()
            assert release.wait(10), "test did not release provider"
        if "tools" in payload:
            message = {"content": None, "tool_calls": [{"id": "synthetic_reply", "type": "function",
                "function": {"name": "reply", "arguments": json.dumps({"text": "Synthetic context answer."})}}]}
        else:
            message = {"content": json.dumps({"action": "reply", "text": "Synthetic context answer."})}
        return httpx.Response(200, json={"choices": [{"message": message, "finish_reason": "stop"}]})

    monkeypatch.setattr("bridge.web.provider.httpx.Client",
                        lambda **kwargs: original(**({"transport": httpx.MockTransport(respond)} | kwargs)))


@pytest.mark.parametrize("protocol", ["json", "deepseek_tools"])
def test_agent_receives_fresh_pinned_run_records_without_other_rounds_or_chat(client, monkeypatch, protocol):
    from dataclasses import replace
    from web_support import settle
    service = client.app.state.service
    service.settings = replace(service.settings, model_action_protocol=protocol)
    rid = make_research(client)
    p, v1, first = make_run(client, rid, "BOUND ROUND")
    _, _, other = make_run(client, rid, "UNRELATED ROUND")
    legacy = call(client, "POST", "/api/sessions", {"research_id": rid})
    state = service.load(legacy["id"])
    service.message(state, "user", "PRIVATE OTHER CHAT HISTORY", source="user_input")
    service.sessions.save(state)
    latest_p = call(client, "GET", f"/api/researches/{rid}/protocols/{p['id']}")
    draft = call(client, "POST", f"/api/researches/{rid}/protocols/{p['id']}/versions",
                 {"expected_version": latest_p["revision"], "based_on_version_id": v1["id"],
                  "changes": {"total_days": 35, "change_note": "UNBOUND FUTURE DRAFT"}})
    session = call(client, "POST", url(rid, first["id"]), {})
    sid = session["id"]
    captures = []
    provider_stub(monkeypatch, captures)
    call(client, "POST", f"/api/sessions/{sid}/messages", {"text": "Which protocol and samples belong to this round?"})
    first_reply = settle(client, sid, timeout=10)
    assert first_reply["status"] == "idle" and first_reply["error"] is None
    assert first_reply["messages"][-1]["content"] == "Synthetic context answer."
    for payload, context in captures:
        snapshot = context["workbench_context"]
        assert snapshot["scope"] == {"research_id": rid, "run_id": first["id"], "kind": "run"}
        assert [r["id"] for r in snapshot["runs"]] == [first["id"]]
        assert [v["id"] for v in snapshot["protocol_versions"]] == [v1["id"]]
        assert snapshot["protocol_versions"][0]["total_days"] == 28
        assert snapshot["samples"] == []
        assert draft["id"] not in str(snapshot) and other["id"] not in str(snapshot)
        assert "PRIVATE OTHER CHAT HISTORY" not in str(payload)
        assert context["upload_ids"] == [] and context["results_sent_to_model"] is False
    stored = service.load(sid)["_workbench_contexts"]
    assert len(stored) == 1
    original = next(iter(stored.values()))
    assert original["snapshot"] == captures[-1][1]["workbench_context"]
    assert original["disposition"] == "admitted" and len(original["sha256"]) == 64
    s = call(client, "POST", f"/api/researches/{rid}/runs/{first['id']}/samples",
             {"expected_version": first["revision"], "day": 5, "assay": "scRNA-seq"})
    captures.clear()
    call(client, "POST", f"/api/sessions/{sid}/messages", {"text": "Has a sample been registered?"})
    assert settle(client, sid, timeout=10)["status"] == "idle"
    assert [row["id"] for row in captures[-1][1]["workbench_context"]["samples"]] == [s["id"]]
    assert captures[-1][1]["workbench_context"]["samples"][0]["status"] == "collected"
    records = list(service.load(sid)["_workbench_contexts"].values())
    assert len(records) == 2 and records[0]["snapshot"]["samples"] == []
    assert records[0]["sha256"] != records[1]["sha256"]


def test_general_conversation_sees_owned_objects_and_exact_parent_version_diff(client, monkeypatch):
    from web_support import settle
    rid = make_research(client)
    p, v1, first = make_run(client, rid)
    p2 = call(client, "GET", f"/api/researches/{rid}/protocols/{p['id']}")
    v2 = call(client, "POST", f"/api/researches/{rid}/protocols/{p['id']}/versions", {
        "expected_version": p2["revision"], "based_on_version_id": v1["id"],
        "changes": {"total_days": 35, "change_note": "Synthetic extended duration"}})
    v2 = call(client, "POST", f"/api/researches/{rid}/protocols/{p['id']}/versions/{v2['id']}/confirm",
              {"expected_version": v2["revision"]})
    second = call(client, "POST", f"/api/researches/{rid}/runs",
                  {"name": "Second round", "protocol_version_id": v2["id"], "expected_version": 0, "state": "planned"})
    other_rid = make_research(client, "OTHER RESEARCH SECRET")
    make_run(client, other_rid, "OTHER RESEARCH ROUND")
    captures = []
    provider_stub(monkeypatch, captures)
    for address, expected_runs in ((url(rid), {first["id"], second["id"]}),
                                   (url(rid, second["id"]), {second["id"]})):
        sid = call(client, "POST", address, {})["id"]
        call(client, "POST", f"/api/sessions/{sid}/messages", {"text": "What changed in the protocol?"})
        assert settle(client, sid, timeout=10)["status"] == "idle"
        context = captures[-1][1]["workbench_context"]
        assert {r["id"] for r in context["runs"]} == expected_runs
        assert {v["id"] for v in context["protocol_versions"]} == {v1["id"], v2["id"]}
        assert context["protocol_differences"] == [{
            "version_id": v2["id"], "based_on_version_id": v1["id"], "changed_fields": ["total_days"]}]
        assert "OTHER RESEARCH" not in str(captures[-1][0])


def test_context_limit_is_explicit_without_silent_record_truncation(client, monkeypatch):
    from web_support import settle
    rid = make_research(client)
    _, _, run = make_run(client, rid)
    service = client.app.state.service
    owner = service.load(call(client, "POST", url(rid, run["id"]), {})["id"])["owner_id"]
    for i in range(75):
        service.research_objects.create_lead(owner,
            rid, run_id=run["id"], sample_id=None, chain_level=None,
            summary=f"Long synthetic lead {i} " + "x" * 700, created_by="agent")
    sid = call(client, "POST", url(rid, run["id"]), {})["id"]
    captures = []
    provider_stub(monkeypatch, captures)
    call(client, "POST", f"/api/sessions/{sid}/messages", {"text": "Summarize available records."})
    assert settle(client, sid, timeout=10)["status"] == "idle"
    context = captures[-1][1]["workbench_context"]
    assert context["state"] == "unavailable"
    assert context["reason_code"] == "workbench_context_too_large"
    assert context["object_counts"]["leads"] == 75
    assert "leads" not in context
    assert len(str(context).encode()) < 48 * 1024


def test_changed_workbench_records_reject_late_provider_answer(client, monkeypatch):
    from threading import Event
    from web_support import settle
    rid = make_research(client)
    _, _, run = make_run(client, rid)
    sid = call(client, "POST", url(rid, run["id"]), {})["id"]
    entered, release = Event(), Event()
    captures = []
    provider_stub(monkeypatch, captures, entered=entered, release=release)
    call(client, "POST", f"/api/sessions/{sid}/messages", {"text": "What is the current run state?"})
    try:
        assert entered.wait(10)
        call(client, "PATCH", f"/api/researches/{rid}/runs/{run['id']}",
             {"expected_version": run["revision"], "state": "ended"})
    finally:
        release.set()
    result = settle(client, sid, timeout=10)
    assert result["status"] == "idle"
    assert all(m["content"] != "Synthetic context answer." for m in result["messages"])
    assert "已更新" in result["messages"][-1]["content"]
    saved = list(client.app.state.service.load(sid)["_workbench_contexts"].values())
    assert saved[0]["disposition"] == "stale"
    assert saved[0]["snapshot"]["runs"][0]["state"] == "differentiating"
    assert result["plan"] is None


def test_bound_conversation_preserves_existing_cancel_fence(client, monkeypatch):
    from threading import Event
    from web_support import settle
    rid = make_research(client)
    _, _, run = make_run(client, rid)
    sid = call(client, "POST", url(rid, run["id"]), {})["id"]
    entered, release = Event(), Event()
    captures = []
    provider_stub(monkeypatch, captures, entered=entered, release=release)
    call(client, "POST", f"/api/sessions/{sid}/messages", {"text": "Read the round context."})
    try:
        assert entered.wait(10)
        call(client, "POST", f"/api/sessions/{sid}/messages", {"text": "stop"})
    finally:
        release.set()
    result = settle(client, sid, timeout=10)
    assert all(m["content"] != "Synthetic context answer." for m in result["messages"])
    assert result["plan"] is None and result["run_id"] == run["id"]


def test_context_includes_only_direct_parent_of_bound_protocol(client, monkeypatch):
    from web_support import settle
    rid = make_research(client)
    p, first, _ = make_run(client, rid)
    parent = first
    for days in (35, 42):
        current = call(client, "GET", f"/api/researches/{rid}/protocols/{p['id']}")
        next_v = call(client, "POST", f"/api/researches/{rid}/protocols/{p['id']}/versions", {
            "expected_version": current["revision"], "based_on_version_id": parent["id"],
            "changes": {"total_days": days}})
        next_v = call(client, "POST", f"/api/researches/{rid}/protocols/{p['id']}/versions/{next_v['id']}/confirm",
                      {"expected_version": next_v["revision"]})
        if days == 35:
            middle = next_v
        parent = next_v
    r = call(client, "POST", f"/api/researches/{rid}/runs", {
        "name": "Third version round", "protocol_version_id": parent["id"], "expected_version": 0, "state": "planned"})
    sid = call(client, "POST", url(rid, r["id"]), {})["id"]
    captures = []
    provider_stub(monkeypatch, captures)
    call(client, "POST", f"/api/sessions/{sid}/messages", {"text": "What changed for this round?"})
    assert settle(client, sid, timeout=10)["status"] == "idle"
    snapshot = captures[-1][1]["workbench_context"]
    assert {v["id"] for v in snapshot["protocol_versions"]} == {middle["id"], parent["id"]}
    assert snapshot["protocol_differences"] == [{
        "version_id": parent["id"], "based_on_version_id": middle["id"], "changed_fields": ["total_days"]}]


def test_bound_scope_is_visible_in_session_listing(client):
    rid = make_research(client)
    _, _, run = make_run(client, rid)
    sid = call(client, "POST", url(rid, run["id"]), {})["id"]
    listed = {item["id"]: item for item in call(client, "GET", "/api/sessions")["sessions"]}
    assert listed[sid]["run_id"] == run["id"]
    assert listed[sid]["conversation_kind"] == "run"


def test_workbench_notes_redact_private_paths_and_do_not_supply_scientific_evidence(client, monkeypatch):
    from web_support import settle
    rid = make_research(client)
    _, _, run = make_run(client, rid)
    session = call(client, "POST", url(rid, run["id"]), {})
    service = client.app.state.service
    owner = service.load(session["id"])["owner_id"]
    lead = service.research_objects.create_lead(owner, rid, run_id=run["id"],
        summary="Hypothesis only; file /private/lab/secret.h5ad", created_by="agent")
    captures = []
    provider_stub(monkeypatch, captures)
    call(client, "POST", f"/api/sessions/{session['id']}/messages", {"text": "What is the open lead?"})
    assert settle(client, session["id"], timeout=10)["status"] == "idle"
    payload, context = captures[-1]
    assert "/private/lab/secret.h5ad" not in str(payload)
    assert context["workbench_context"]["leads"][0]["id"] == lead["id"]
    assert "[private path omitted]" in context["workbench_context"]["leads"][0]["summary"]
    assert context["results_sent_to_model"] is False
    assert context.get("result_summary", {}).get("state") != "available"


def test_workbench_wire_excludes_private_provenance_and_unknown_nested_fields(client, monkeypatch):
    import json
    from bridge.web.sessions import read_file, write_file
    from web_support import settle
    rid = make_research(client)
    _, version, run = make_run(client, rid)
    sid = call(client, "POST", url(rid, run["id"]), {})["id"]
    path = client.app.state.service.researches.directory(rid) / "objects.json"
    stored = json.loads(read_file(path, 4 * 1024 * 1024))
    stored["versions"][version["id"]]["provenance"] = {"source_hash": "PRIVATE_SOURCE_SENTINEL"}
    stored["versions"][version["id"]]["operations"] = [
        {"day": 5, "kind": "sample", "note": "Registered sample day", "future_private": "PRIVATE_NESTED_SENTINEL"}]
    stored["versions"][version["id"]]["reagents"] = [
        {"id": "a" * 32, "name": "Synthetic reagent", "short": "SR", "pathway": "other",
         "kind": "supplement", "dose_text": "1 unit", "start_day": 0, "end_day": 5,
         "catalog_id": None, "unconfirmed": [], "source_locator": "PRIVATE_SOURCE_LOCATOR"}]
    stored["runs"][run["id"]]["cell_line"] = "PRIVATE_CELL_LINE"
    write_file(path, json.dumps(stored).encode())
    captures = []
    provider_stub(monkeypatch, captures)
    call(client, "POST", f"/api/sessions/{sid}/messages", {"text": "What are the registered operations?"})
    assert settle(client, sid, timeout=10)["error"] is None
    assert captures and "PRIVATE_" not in str(captures)
    snapshot = captures[-1][1]["workbench_context"]
    assert snapshot["protocol_versions"][0]["operations"] == [
        {"day": 5, "kind": "sample", "note": "Registered sample day"}]
    with pytest.raises(AssertionError, match="unregistered keys"):
        assert_model_context("workbench", dict(snapshot, future_private="PRIVATE_UNKNOWN"))


@pytest.mark.parametrize("protocol", ["json", "deepseek_tools"])
def test_retrospective_review_and_execution_state_reach_provider_without_source_details(client, monkeypatch, protocol):
    from dataclasses import replace
    from test_protocol_source_review import literature, review
    from web_support import settle
    service = client.app.state.service
    service.settings = replace(service.settings, model_action_protocol=protocol)
    rid = make_research(client)
    _, version, edition = literature(client, rid)
    version = review(client, edition, version)
    run = call(client, "POST", f"/api/researches/{rid}/runs", {
        "expected_version": 0, "name": "Historical round", "protocol_version_id": version["id"],
        "state": "ended", "purpose": "retrospective"})
    sid = call(client, "POST", url(rid, run["id"]), {})["id"]
    captures = []
    provider_stub(monkeypatch, captures)
    call(client, "POST", f"/api/sessions/{sid}/messages", {"text": "What can this source-reviewed protocol support?"})
    assert settle(client, sid, timeout=10)["error"] is None
    assert captures
    for _, context in captures:
        snapshot = context["workbench_context"]
        assert snapshot["runs"][0]["purpose"] == "retrospective"
        pv = snapshot["protocol_versions"][0]
        assert pv["source_review"] == {"status": "reviewed"}
        assert pv["execution_readiness"]["status"] == "incomplete" and pv["total_days"] is None
        assert pv["reagents"][0]["timing_text"] == "After replating until the assay"
        assert "recipe_locator" not in str(snapshot) and "source_locator" not in str(snapshot)
        assert "Source checked; endpoint" not in str(snapshot)
