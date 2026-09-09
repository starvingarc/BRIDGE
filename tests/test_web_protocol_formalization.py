"""Source-linked protocol representations are not execution or biological proof."""
from __future__ import annotations

import os
from pathlib import Path
import sys

import pytest


@pytest.mark.parametrize("source,code", [
    ('import stdlib.reagents\nprotocol Probe { wait() }', "external_module_forbidden"),
    ('module custom { }', "external_module_forbidden"),
    ('protocol Probe { read(path: "/etc/passwd") }', "external_path_forbidden"),
    ('protocol Probe { read(path: "../outside") }', "external_path_forbidden"),
    (r'protocol Probe { read(path: "\u002fetc/passwd") }', "external_path_forbidden"),
    ('protocol Probe { read(path: "./outside") }', "external_path_forbidden"),
    ('x' * (128 * 1024 + 1), "bpl_size_limit"),
], ids=["import", "module", "absolute-path", "relative-path", "escaped-path", "dot-relative-path", "size-limit"])
def test_compiler_rejects_unsafe_or_oversized_input_before_child(source, code, monkeypatch):
    from bridge.web import protocol_compiler
    def never(*args, **kwargs):
        pytest.fail("unsafe input must not start a child")
    monkeypatch.setattr(protocol_compiler.subprocess, "Popen", never)
    value = protocol_compiler.compile_bpl(source, "/unused/runtime")
    assert value["compiler_state"] == "not_run"
    assert value["syntax_state"] == "not_run"
    assert code in {item["code"] for item in value["diagnostics"]}


def test_missing_compiler_is_unavailable_not_invalid_protocol():
    from bridge.web.protocol_compiler import compile_bpl
    value = compile_bpl("protocol Probe {\n wait(duration: 1 s)\n}", None)
    assert value["syntax_state"] == "not_run"
    assert value["compiler_state"] == "unavailable"


def test_compiler_environment_does_not_inherit_provider_or_home(monkeypatch):
    from bridge.web.protocol_compiler import child_environment
    monkeypatch.setenv("BRIDGE_WEB_MODEL_API_KEY", "PRIVATE_TEST_KEY")
    monkeypatch.setenv("HOME", "/private/test-home")
    monkeypatch.setenv("PYTHONPATH", "/private/override")
    environment = child_environment()
    assert not {"HOME", "BRIDGE_WEB_MODEL_API_KEY", "PYTHONPATH", "USER"} & environment.keys()
    assert "PRIVATE_TEST_KEY" not in repr(environment)


@pytest.fixture
def bpl_python():
    runtime = os.environ.get("BRIDGE_TEST_BPL_PYTHON")
    if not runtime:
        pytest.skip("pinned compiler runtime is an explicit server acceptance dependency")
    assert Path(runtime).is_file()
    return runtime


@pytest.mark.parametrize("body,expected", [
    ("transfer(from: source, to: dest, volume: 1 mL)", "volume_mapping_changed"),
    ("transfer(from: source, to: dest, volume: 10 mM)", "volume_dimension_unchecked"),
    ("wait()", "duration_unresolved"),
    ("wait(duration: -1 s)", "duration_unresolved"),
    ("wait(duration: 10 mL)", "duration_dimension_unchecked"),
    ("incubate(target: cells, temperature: 37 degC, time: 2 h)", "human_step_unchecked"),
    ("wait(duration: 1 s)\n if true { wait(duration: 2 s) }", "statement_not_lowered"),
    ("wait(duration: 1 s)\n for item in [1, 2] { wait(duration: 2 s) }", "statement_not_lowered"),
])
def test_actual_compiler_success_retains_unchecked_semantics(bpl_python, body, expected):
    from bridge.web.protocol_compiler import compile_bpl, COMPILER_COMMIT
    value = compile_bpl("protocol Probe {\n " + body + "\n}", bpl_python)
    assert value["syntax_state"] == "passed", value
    assert value["compiler_state"] == "passed", value
    assert expected in {item["code"] for item in value["unchecked"]}
    assert value["compiler"]["commit"] == COMPILER_COMMIT
    assert value["ast"]["node_type"] == "Program"
    assert value["plan"]["target"] == "human"
    assert "validated" not in value and "executed" not in value


def test_actual_compiler_accounts_for_second_protocol(bpl_python):
    from bridge.web.protocol_compiler import compile_bpl
    value = compile_bpl("protocol First { wait(duration: 1 s) }\nprotocol Second { wait(duration: 2 s) }", bpl_python)
    codes = {item["code"] for item in value["unchecked"]}
    assert {"multiple_protocols", "statement_not_lowered"} <= codes
    assert value["plan"]["protocol_name"] == "First"


def test_actual_compiler_syntax_and_semantic_errors_are_separate(bpl_python):
    from bridge.web.protocol_compiler import compile_bpl
    syntax = compile_bpl("protocol Bad { ??? }", bpl_python)
    assert syntax["syntax_state"] == "failed" and syntax["compiler_state"] == "not_run"
    semantic = compile_bpl("protocol Bad { transfer(volume: 1 uL) }", bpl_python)
    assert semantic["syntax_state"] == "passed" and semantic["compiler_state"] == "failed"
    assert "SEMANTIC_MISSING_ENDPOINT" in {item["code"] for item in semantic["diagnostics"]}


def test_unpinned_runtime_fails_closed_without_exposing_paths():
    from bridge.web.protocol_compiler import compile_bpl
    value = compile_bpl("protocol Probe { wait(duration: 1 s) }", sys.executable)
    assert value["compiler_state"] == "unavailable"
    assert value["syntax_state"] == "not_run"
    assert sys.executable not in str(value)


from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import re

from test_web_service import client, settle
from test_web_intake_autofill import upload_metadata, intake


def compiler_fixture(text, python):
    """Controlled single-wait receipt for lifecycle tests, not a real compiler."""
    match = re.search(r"duration:\s*([0-9]+)\s*h", text)
    arguments = [] if not match else [{"name": "duration", "value": {
        "node_type": "QuantityExpr", "span": {"start_line": 2, "end_line": 2},
        "unit": {"text": "h"}, "value": {"node_type": "NumberLit", "value": float(match[1])}}}]
    return {"syntax_state": "passed", "compiler_state": "passed", "diagnostics": [], "stages": [],
            "unchecked": [] if match else [{"code": "duration_unresolved", "line": 2, "message": "Duration missing."}],
            "compiler": {"verified": True, "version": "2.4.0", "commit": "fixture"},
            "ast": {"node_type": "Program", "declarations": [{"node_type": "ProtocolDecl", "body": [
                {"node_type": "CallStmt", "name": "wait", "span": {"start_line": 2, "end_line": 2},
                 "arguments": arguments}]}]},
            "plan": {"target": "human", "steps": []}}


def draft_fixture(context, *, missing=False):
    from bridge.web.protocol_formalization import ProtocolDraft
    sources = context["sources"]
    supplements = context.get("supplements", [])
    known = not missing or any(not item["unsure"] for item in supplements)
    ids = [sources[0]["id"]] + [item["id"] for item in supplements if not item["unsure"]]
    return ProtocolDraft(bpl="protocol Probe {\n wait(" + ("duration: 2 h" if known else "") + ")\n}",
        steps=[{"id": "step-1", "label": "Wait", "operations": "Wait for the stated period.",
                "line_start": 2, "line_end": 2, "source_ids": ids}],
        questions=[] if known else [{"id": "duration", "title": "这一步需等待多久？",
            "step_ids": ["step-1"], "source_ids": [sources[0]["id"]], "options": []}],
        excluded_sources=[])


def prepare_protocol(client, tmp_path, monkeypatch, *, text="Wait for 2 h.", automatic=False):
    import bridge.web.intake_autofill as fill
    import bridge.web.protocol_formalization as formal
    monkeypatch.setattr(fill, "extract_intake", lambda *args: fill.Extraction())
    monkeypatch.setattr(formal, "compile_bpl", compiler_fixture)
    monkeypatch.setattr(formal, "generate", lambda settings, context, previous=None, diagnostics=None: draft_fixture(context))
    if automatic:
        service = client.app.state.service
        service.settings = replace(service.settings, protocol_compiler_python="/controlled/fixture")
    sid, aid = upload_metadata(client, tmp_path)
    response = client.post(f"/api/sessions/{sid}/intake/protocols?upload_id={aid}",
                          files={"file": ("method.txt", text.encode())})
    assert response.status_code == 200, response.json()
    settle(client, sid)
    pid = intake(client, sid, aid)["autofill"]["protocols"][0]["id"]
    return sid, aid, pid


def representation(client, sid, aid, pid):
    items = intake(client, sid, aid)["autofill"]["formalizations"]
    return next(item for item in items if item["protocol_id"] == pid)


def protocol_action(client, sid, aid, pid, action, **extra):
    item = representation(client, sid, aid, pid)
    return client.post(f"/api/sessions/{sid}/intake/protocols/{action}", json={
        "upload_id": aid, "protocol_id": pid, "revision": item["revision"], **extra})


def test_existing_attachment_is_not_formalized_by_opening_intake(client, tmp_path, monkeypatch):
    sid, aid, pid = prepare_protocol(client, tmp_path, monkeypatch)
    for _ in range(2):
        item = representation(client, sid, aid, pid)
        assert item["state"] == "not_started" and item["latest"] is None
    assert "_protocol_formalizations" not in client.app.state.service.load(sid)


def test_new_protocol_automatically_generates_when_runtime_is_configured(client, tmp_path, monkeypatch):
    sid, aid, pid = prepare_protocol(client, tmp_path, monkeypatch, automatic=True)
    item = representation(client, sid, aid, pid)
    assert item["state"] == "complete"
    assert item["latest"]["source_binding"]["protocol_sha256"] == hashlib.sha256(b"Wait for 2 h.").hexdigest()
    assert item["latest"]["review_state"] == "unreviewed"
    state = client.get(f"/api/sessions/{sid}").json()
    assert state["plan"] is None and not state["input_review_required"]


def test_generation_binds_checked_sources_and_keeps_intake_and_execution_unchanged(client, tmp_path, monkeypatch):
    sid, aid, pid = prepare_protocol(client, tmp_path, monkeypatch)
    before = deepcopy(client.app.state.service.load(sid))
    response = protocol_action(client, sid, aid, pid, "formalize")
    assert response.status_code == 200, response.json()
    settle(client, sid)
    item = representation(client, sid, aid, pid)
    version = item["latest"]
    assert item["state"] == "complete", item
    assert version["coverage_state"] == "complete_for_extracted_scope"
    assert version["steps"][0]["sources"][0]["text"] == "Wait for 2 h."
    assert version["review_state"] == "unreviewed"
    assert version["generation"]["request_count"] == 1
    after = client.app.state.service.load(sid)
    for key in ("_intakes", "_asset_declarations", "_uploads", "_tool_runs", "plan", "plan_history", "messages"):
        assert after.get(key) == before.get(key), key
    assert version["digest"] and item["versions"][0]["digest"] == version["digest"]


@pytest.mark.parametrize("defect,expected", [
    ("citation", "unknown_source"), ("quantity", "unsupported_literal"), ("omitted_source", "source_accounting_incomplete")
])
def test_invalid_generation_has_bounded_repairs_without_publishing_false_coverage(
        client, tmp_path, monkeypatch, defect, expected):
    import bridge.web.protocol_formalization as formal
    text = "Wait for 2 h.\n\nRinse the culture." if defect == "omitted_source" else "Wait for 2 h."
    sid, aid, pid = prepare_protocol(client, tmp_path, monkeypatch, text=text)
    calls = []
    def invalid(settings, context, previous=None, diagnostics=None):
        calls.append(context)
        draft = draft_fixture(context)
        if defect == "citation":
            draft.steps[0].source_ids = ["forged"]
        if defect == "quantity":
            draft.bpl = draft.bpl.replace("2 h", "12 h")
        return draft
    monkeypatch.setattr(formal, "generate", invalid)
    assert protocol_action(client, sid, aid, pid, "formalize").status_code == 200
    settle(client, sid)
    item = representation(client, sid, aid, pid)
    assert item["state"] == "unavailable" and item["latest"] is None
    assert len(calls) == 3
    assert item["error"] == expected
    assert client.get(f"/api/sessions/{sid}").json()["plan"] is None




def test_repair_receives_compiler_diagnostic_and_can_preserve_source_steps(client, tmp_path, monkeypatch):
    import bridge.web.protocol_formalization as formal
    sid, aid, pid = prepare_protocol(client, tmp_path, monkeypatch)
    calls = []
    def generator(settings, context, previous=None, diagnostics=None):
        calls.append(diagnostics)
        draft = draft_fixture(context)
        if len(calls) == 1:
            draft.bpl = "broken BPL"
        elif not any(item["code"] == "SYNTAX_TEST_DETAIL" for item in diagnostics or []):
            raise ValueError("missing actual diagnostic")
        return draft
    def compiler(text, python):
        value = compiler_fixture(text, python)
        if text == "broken BPL":
            value.update(syntax_state="failed", compiler_state="not_run", ast=None, plan=None,
                         diagnostics=[{"code": "SYNTAX_TEST_DETAIL", "line": 1, "message": "Malformed call."}])
        return value
    monkeypatch.setattr(formal, "generate", generator)
    monkeypatch.setattr(formal, "compile_bpl", compiler)
    protocol_action(client, sid, aid, pid, "formalize")
    settle(client, sid)
    item = representation(client, sid, aid, pid)
    assert item["state"] == "complete"
    assert item["latest"]["syntax_state"] == "passed"
    assert item["latest"]["generation"]["request_count"] == 2


def test_repair_cannot_reset_preservation_by_returning_an_empty_intermediate_draft(client, tmp_path, monkeypatch):
    import bridge.web.protocol_formalization as formal
    sid, aid, pid = prepare_protocol(client, tmp_path, monkeypatch)
    calls = []
    def generator(settings, context, previous=None, diagnostics=None):
        calls.append(1)
        draft = draft_fixture(context)
        if len(calls) == 1:
            draft.bpl = "broken BPL"
        elif len(calls) == 2:
            draft.steps = []
            draft.excluded_sources = [formal.ExcludedSource(source_id=context["sources"][0]["id"], reason="Not a step.")]
        else:
            draft.steps[0].operations = "Different operation replacing the original."
        return draft
    def compiler(text, python):
        value = compiler_fixture(text, python)
        if text == "broken BPL":
            value.update(syntax_state="failed", compiler_state="not_run", ast=None, plan=None)
        return value
    monkeypatch.setattr(formal, "generate", generator)
    monkeypatch.setattr(formal, "compile_bpl", compiler)
    protocol_action(client, sid, aid, pid, "formalize")
    settle(client, sid)
    item = representation(client, sid, aid, pid)
    assert len(calls) == 3
    assert item["state"] == "unavailable" and item["latest"] is None
    assert item["error"] == "repair_changed_source_steps"


def test_other_and_unsure_are_versioned_user_supplements_not_source_facts(client, tmp_path, monkeypatch):
    import bridge.web.protocol_formalization as formal
    sid, aid, pid = prepare_protocol(client, tmp_path, monkeypatch, text="Wait for the required period.")
    monkeypatch.setattr(formal, "generate", lambda settings, context, previous=None, diagnostics=None:
                        draft_fixture(context, missing=True))
    protocol_action(client, sid, aid, pid, "formalize")
    settle(client, sid)
    old = representation(client, sid, aid, pid)
    assert old["latest"]["coverage_state"] == "needs_input"
    assert protocol_action(client, sid, aid, pid, "answer", question_id="duration",
        value="   ", other=True, unsure=False).status_code == 422
    response = protocol_action(client, sid, aid, pid, "answer", question_id="duration",
        value="Wait for 2 h.", other=True, unsure=False)
    assert response.status_code == 200, response.json()
    settle(client, sid)
    current = representation(client, sid, aid, pid)
    assert current["latest"]["digest"] != old["latest"]["digest"]
    assert current["latest"]["supplements"][0]["other"] is True
    assert any(source["kind"] == "user" for source in current["latest"]["steps"][0]["sources"])
    assert current["latest"]["review_state"] == "unreviewed"
    assert len(current["versions"]) == 2


def test_unsure_remains_unresolved_without_repeating_same_question(client, tmp_path, monkeypatch):
    import bridge.web.protocol_formalization as formal
    sid, aid, pid = prepare_protocol(client, tmp_path, monkeypatch, text="Wait for the required period.")
    monkeypatch.setattr(formal, "generate", lambda settings, context, previous=None, diagnostics=None:
                        draft_fixture(context, missing=True))
    protocol_action(client, sid, aid, pid, "formalize")
    settle(client, sid)
    assert protocol_action(client, sid, aid, pid, "answer", question_id="duration",
                           value="", other=False, unsure=True).status_code == 200
    settle(client, sid)
    value = representation(client, sid, aid, pid)["latest"]
    assert value["coverage_state"] == "needs_input"
    assert value["questions"][0]["answer_state"] == "unsure"
    assert value["supplements"][0]["unsure"] is True


def test_review_is_exact_and_edit_keeps_old_review_without_inheriting_it(client, tmp_path, monkeypatch):
    sid, aid, pid = prepare_protocol(client, tmp_path, monkeypatch, automatic=True)
    original = representation(client, sid, aid, pid)
    digest = original["latest"]["digest"]
    assert protocol_action(client, sid, aid, pid, "review", digest="0"*64).status_code == 409
    assert protocol_action(client, sid, aid, pid, "review", digest=digest).status_code == 200
    reviewed = representation(client, sid, aid, pid)
    assert reviewed["latest"]["review_state"] == "reviewed"
    assert protocol_action(client, sid, aid, pid, "edit",
                           bpl="protocol Probe {\n wait(duration: 3 h)\n}").status_code == 200
    settle(client, sid)
    edited = representation(client, sid, aid, pid)
    assert edited["latest"]["review_state"] == "unreviewed"
    assert edited["latest"]["coverage_state"] == "partial"
    assert edited["versions"][0]["review_state"] == "reviewed"
    assert edited["latest"]["steps"][0]["origin"] == "user"
    assert edited["latest"]["steps"][0]["sources"] == []
    stale = client.post(f"/api/sessions/{sid}/intake/protocols/review", json={
        "upload_id": aid, "protocol_id": pid, "revision": original["revision"], "digest": digest})
    assert stale.status_code == 409


def test_protocol_context_removes_identities_paths_and_secrets(client, tmp_path, monkeypatch):
    import bridge.web.protocol_formalization as formal
    text = "Wait for 2 h. PRIVATE_SAMPLE_A. token=private-token. /home/private/recipe."
    sid, aid, pid = prepare_protocol(client, tmp_path, monkeypatch, text=text)
    service = client.app.state.service
    context, binding = formal.context(service, service.load(sid), aid, pid)
    wire = json.dumps(context)
    assert "PRIVATE_SAMPLE_A" not in wire and "private-token" not in wire
    assert "/home/private" not in wire and str(tmp_path) not in wire
    assert context["purpose"] == "protocol_formalization"
    assert len(binding["protocol_sha256"]) == 64
    assert "sha256" not in wire


def test_cancelled_generation_cannot_publish_a_late_version(client, tmp_path, monkeypatch):
    from threading import Event
    import bridge.web.protocol_formalization as formal
    sid, aid, pid = prepare_protocol(client, tmp_path, monkeypatch)
    entered, release = Event(), Event()
    def delayed(settings, context, previous=None, diagnostics=None):
        entered.set()
        assert release.wait(10)
        return draft_fixture(context)
    monkeypatch.setattr(formal, "generate", delayed)
    protocol_action(client, sid, aid, pid, "formalize")
    assert entered.wait(5)
    try:
        assert client.post(f"/api/sessions/{sid}/stop", json={}).status_code == 200
    finally:
        release.set()
    settle(client, sid)
    item = representation(client, sid, aid, pid)
    assert item["state"] == "cancelled" and item["latest"] is None


def test_checked_download_cannot_cross_session_and_detects_artifact_tampering(client, tmp_path, monkeypatch):
    sid, aid, pid = prepare_protocol(client, tmp_path, monkeypatch, automatic=True)
    item = representation(client, sid, aid, pid)
    vid = item["latest"]["id"]
    route = f"/api/sessions/{sid}/intake/protocols/{pid}/versions/{vid}/bpl?upload_id={aid}"
    downloaded = client.get(route)
    assert downloaded.status_code == 200 and downloaded.text == item["latest"]["bpl"]
    from test_web_service import new_session
    other_sid = new_session(client)["id"]
    assert client.get(route.replace(sid, other_sid)).status_code == 404
    service = client.app.state.service
    from bridge.web.app import write_file
    write_file(service.directory(sid) / "protocol-versions" / pid / vid / "protocol.bpl", b"tampered")
    assert client.get(route).status_code == 409


def test_negative_quantity_cannot_borrow_positive_source_evidence():
    from bridge.web.protocol_formalization import validate_draft
    supplied = {"sources": [{"id": "S1", "kind": "protocol", "text": "Wait for 2 h."}], "supplements": []}
    draft = draft_fixture(supplied)
    compiled = compiler_fixture(draft.bpl, None)
    argument = compiled["ast"]["declarations"][0]["body"][0]["arguments"][0]
    argument["value"] = {"node_type": "UnaryExpr", "op": "-", "operand": argument["value"]}
    draft.bpl = draft.bpl.replace("2 h", "-2 h")
    with pytest.raises(ValueError, match="unsupported_literal"):
        validate_draft(draft, supplied, compiled)


def test_editing_more_than_200_steps_is_not_silently_truncated():
    from types import SimpleNamespace
    from bridge.web.protocol_formalization import _make_version
    compiled = compiler_fixture("protocol P {\n wait()\n}", None)
    node = compiled["ast"]["declarations"][0]["body"][0]
    compiled["ast"]["declarations"][0]["body"] = [deepcopy(node) for _ in range(201)]
    work = {"edited_bpl": "protocol P {\n wait()\n}", "context": {"sources": [], "supplements": []},
            "binding": {}, "generation": 1}
    with pytest.raises(ValueError, match="bpl_step_limit"):
        _make_version(SimpleNamespace(settings=SimpleNamespace(model="test")), work, None, compiled, False, 0)


def test_superseded_unsure_answer_can_be_corrected_without_losing_history(client, tmp_path, monkeypatch):
    import bridge.web.protocol_formalization as formal
    sid, aid, pid = prepare_protocol(client, tmp_path, monkeypatch, text="Wait for the required period.")
    def generator(settings, context, previous=None, diagnostics=None):
        active = deepcopy(context)
        active["supplements"] = [item for item in context["supplements"] if not item.get("superseded")]
        return draft_fixture(active, missing=True)
    monkeypatch.setattr(formal, "generate", generator)
    protocol_action(client, sid, aid, pid, "formalize")
    settle(client, sid)
    protocol_action(client, sid, aid, pid, "answer", question_id="duration", value="", other=False, unsure=True)
    settle(client, sid)
    protocol_action(client, sid, aid, pid, "answer", question_id="duration", value="Wait for 2 h.", other=True, unsure=False)
    settle(client, sid)
    version = representation(client, sid, aid, pid)["latest"]
    assert version["coverage_state"] == "complete_for_extracted_scope"
    assert version["supplements"][0]["superseded"] is True
    assert len(version["supplements"]) == 2


def test_completed_question_answer_can_be_edited_after_question_disappears(client, tmp_path, monkeypatch):
    import bridge.web.protocol_formalization as formal
    sid, aid, pid = prepare_protocol(client, tmp_path, monkeypatch, text="Wait for the required period.")
    def generator(settings, context, previous=None, diagnostics=None):
        active = deepcopy(context)
        active["supplements"] = [item for item in context["supplements"] if not item.get("superseded")]
        return draft_fixture(active, missing=True)
    monkeypatch.setattr(formal, "generate", generator)
    protocol_action(client, sid, aid, pid, "formalize")
    settle(client, sid)
    protocol_action(client, sid, aid, pid, "answer", question_id="duration", value="Wait for 2 h.", other=True, unsure=False)
    settle(client, sid)
    assert representation(client, sid, aid, pid)["latest"]["questions"] == []
    assert protocol_action(client, sid, aid, pid, "answer", question_id="duration",
                           value="Wait for 2 h. Confirmed wording.", other=True, unsure=False).status_code == 200
    settle(client, sid)
    assert len(representation(client, sid, aid, pid)["latest"]["supplements"]) == 2


def test_review_receipt_integrity_is_checked(client, tmp_path, monkeypatch):
    sid, aid, pid = prepare_protocol(client, tmp_path, monkeypatch, automatic=True)
    version = representation(client, sid, aid, pid)["latest"]
    protocol_action(client, sid, aid, pid, "review", digest=version["digest"])
    service = client.app.state.service
    from bridge.web.app import write_file
    write_file(service.directory(sid) / "protocol-versions" / pid / version["id"] / "review.json", b"{}")
    assert client.get(f"/api/sessions/{sid}/intake?upload_id={aid}").status_code == 409


def test_bpl_fragment_resolves_actual_lines_instead_of_trusting_model_counts():
    from bridge.web.protocol_formalization import validate_draft
    supplied = {"sources": [{"id": "S1", "kind": "protocol", "text": "Wait for 2 h."}], "supplements": []}
    draft = draft_fixture(supplied)
    draft.bpl = "// Heading\n\nprotocol Probe {\n\n wait(duration: 2 h)\n}"
    draft.steps[0].line_start = draft.steps[0].line_end = 1
    object.__setattr__(draft.steps[0], "bpl_fragment", "wait(duration: 2 h)")
    compiled = compiler_fixture(draft.bpl, None)
    call = compiled["ast"]["declarations"][0]["body"][0]
    call["span"] = {"start_line": 5, "end_line": 5}
    call["arguments"][0]["value"]["span"] = {"start_line": 5, "end_line": 5}
    validate_draft(draft, supplied, compiled)
    assert (draft.steps[0].line_start, draft.steps[0].line_end) == (5, 5)


@pytest.mark.parametrize(("source", "readable"), [
    ("Wait for 2 h on day-51.", "第51天等待2 h。"),
    ("Wait for 2 h on days 9-12.", "第9至12天等待2 h。"),
    ("Wait for 2h.", "等待2h。"), ("等待2 h。", "等待2 h。"), ("Wait for 2.0 h.", "等待 2 h。"),
])
def test_source_numeric_matching_accepts_compact_units_and_chinese(source, readable):
    from bridge.web.protocol_formalization import validate_draft
    supplied = {"sources": [{"id": "S1", "kind": "protocol", "text": source}], "supplements": []}
    draft = draft_fixture(supplied)
    draft.steps[0].operations = readable
    compiled = compiler_fixture(draft.bpl, None)
    assert validate_draft(draft, supplied, compiled)


@pytest.mark.parametrize("readable", ["Culture for 4 days.", "培养4天。", "等待2 h。"])
def test_readable_steps_cannot_invent_duration_from_a_day_interval(readable):
    from bridge.web.protocol_formalization import validate_draft
    supplied = {"sources": [{"id": "S1", "kind": "protocol", "text": "Culture from days 9 to 12."}], "supplements": []}
    draft = draft_fixture(supplied, missing=True)
    draft.steps[0].operations = readable
    compiled = compiler_fixture(draft.bpl, None)
    with pytest.raises(ValueError, match="unsupported_literal"):
        validate_draft(draft, supplied, compiled)
