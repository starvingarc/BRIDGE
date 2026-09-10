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



def test_bounded_repair_identifies_unsupported_options_without_changing_steps(client, tmp_path, monkeypatch):
    import bridge.web.protocol_formalization as formal
    sid, aid, pid = prepare_protocol(client, tmp_path, monkeypatch, text="Wait for the required period.")
    calls = []
    def generator(settings, context, previous=None, diagnostics=None):
        calls.append(diagnostics)
        draft = draft_fixture(context, missing=True)
        guidance = next((item for item in diagnostics or []
                         if item["code"] == "unsupported_question_option"), {})
        if guidance.get("unsupported_options") != [{"question_id": "duration", "value": "2 h"}]:
            draft.questions[0].options = [formal.QuestionOption(value="2 h", label="两小时")]
        return draft
    monkeypatch.setattr(formal, "generate", generator)
    assert protocol_action(client, sid, aid, pid, "formalize").status_code == 200
    settle(client, sid)
    item = representation(client, sid, aid, pid)
    assert item["state"] == "complete"
    version = item["latest"]
    assert version["generation"]["request_count"] == 2
    assert version["coverage_state"] == "needs_input"
    assert version["questions"][0]["id"] == "duration"
    assert version["questions"][0]["options"] == []
    assert len(version["steps"]) == 1
    assert version["bpl"] == "protocol Probe {\n wait()\n}"
    assert client.get(f"/api/sessions/{sid}").json()["plan"] is None
    attempts = sorted((client.app.state.service.directory(sid) / "protocol-attempts" / pid).glob("*/[12].json"))
    assert len(attempts) == 2
    first = json.loads(attempts[0].read_text())
    assert first["error"] == "unsupported_question_option"
    assert first["draft"]["questions"][0]["options"][0]["value"] == "2 h"



@pytest.mark.parametrize("protocol", ["json", "deepseek_tools"])
def test_provider_generates_one_fragment_source_with_distinct_repeated_spans(monkeypatch, protocol):
    from types import SimpleNamespace
    import httpx
    import bridge.web.protocol_formalization as formal
    wire = {"steps": [
        {"id": "first", "label": "First", "operations": "Wait for 2 h.",
         "bpl_fragment": "wait(duration: 2 h)", "source_ids": ["S1"]},
        {"id": "second", "label": "Second", "operations": "Wait for 2 h.",
         "bpl_fragment": "wait(duration: 2 h)", "source_ids": ["S2"]}],
        "questions": [], "excluded_sources": []}
    captured = []
    real_client = httpx.Client
    def response(request):
        captured.append(json.loads(request.content))
        message = ({"content": None, "tool_calls": [{"type": "function", "function": {
                    "name": "formalize_protocol", "arguments": json.dumps(wire)}}]}
                   if protocol == "deepseek_tools" else {"content": json.dumps(wire)})
        return httpx.Response(200, json={"model": "test-model", "choices": [{"message": message}]})
    monkeypatch.setattr(formal.httpx, "Client",
                        lambda **kwargs: real_client(transport=httpx.MockTransport(response), **kwargs))
    settings = SimpleNamespace(model="test-model", model_action_protocol=protocol,
                               model_base_url="https://provider.invalid/v1", model_api_key="test-key")
    supplied = {"sources": [{"id": sid, "text": "Wait for 2 h."} for sid in ("S1", "S2")], "supplements": []}
    result = formal.generate(settings, supplied)
    assert result.bpl == "protocol UploadedProtocol {\n  wait(duration: 2 h)\n  wait(duration: 2 h)\n}\n"
    assert [(s.line_start, s.line_end) for s in result.steps] == [(2, 2), (3, 3)]
    assert [s.source_ids for s in result.steps] == [["S1"], ["S2"]]
    schema = (captured[0]["tools"][0]["function"]["parameters"] if protocol == "deepseek_tools" else
              json.loads(captured[0]["messages"][0]["content"].split("\nRequired JSON schema: ", 1)[1]))
    assert set(schema["properties"]) == {"steps", "questions", "excluded_sources"}
    instruction = captured[0]["messages"][0]["content"]
    assert "The server normalizes formatting newlines inside call expressions" in instruction
    for field in ("bpl", "bpl_occurrence", "line_start", "line_end"):
        assert f'"{field}"' not in json.dumps(schema)


def test_fragment_repair_reassembles_multiline_spans_without_changing_source_content(bpl_python):
    import bridge.web.protocol_formalization as formal
    wire = {"steps": [
        {"id": "first", "label": "First", "operations": "Wait for the required period and rinse.",
         "bpl_fragment": "wait()\nrinse()", "source_ids": ["S1"]},
        {"id": "second", "label": "Second", "operations": "Wait for the required period.",
         "bpl_fragment": "wait()", "source_ids": ["S2"]}],
        "questions": [], "excluded_sources": []}
    original = formal._assemble_draft(formal.ProtocolProposal.model_validate(wire))
    before = original.model_dump()
    repair = formal.ProtocolRepair(step_fragments=[
        {"step_id": "first", "bpl_fragment": "// preserved operation\nwait()\nrinse()"}])
    result = formal._repair_draft(original, repair, allow_fragments=True)
    assert original.model_dump() == before
    assert result.bpl == "protocol UploadedProtocol {\n  // preserved operation\nwait()\nrinse()\n  wait()\n}\n"
    assert [(s.line_start, s.line_end) for s in result.steps] == [(2, 4), (5, 5)]
    assert [(s.operations, s.source_ids) for s in result.steps] == [
        ("Wait for the required period and rinse.", ["S1"]),
        ("Wait for the required period.", ["S2"])]
    supplied = {"sources": [{"id": "S1", "text": "Wait for the required period and rinse."},
                            {"id": "S2", "text": "Wait for the required period."}], "supplements": []}
    compiled = formal.compile_bpl(result.bpl, bpl_python)
    assert compiled["syntax_state"] == "passed" and compiled["compiler_state"] == "passed"
    assert formal.validate_draft(result, supplied, compiled, original)


@pytest.mark.parametrize("fragment", ["}\nprotocol Other { wait()", "if true {\nwait()", "protocol Other { wait() }"])
def test_generated_fragment_cannot_escape_or_split_the_server_protocol(fragment):
    import bridge.web.protocol_formalization as formal
    proposal = formal.ProtocolProposal(steps=[{
        "id": "first", "label": "First", "operations": "Wait.",
        "bpl_fragment": fragment, "source_ids": ["S1"]}])
    with pytest.raises(ValueError, match="^invalid_protocol_fragment$"):
        formal._assemble_draft(proposal)



@pytest.mark.parametrize("fragments", [
    ['wait(note: "', '")\n}\nprotocol Other { wait(note: "', '")'],
    ['wait() /*', 'ignored */\nwait()'],
    ['wait(', ')'],
    ['culture(values: [', '])'],
    ['culture(values: [)])'],
], ids=["cross-string-protocol", "cross-comment", "cross-call", "cross-list", "mismatched-delimiters"])
def test_fragment_lexical_and_delimiter_state_cannot_cross_source_boundaries(fragments):
    import bridge.web.protocol_formalization as formal
    proposal = formal.ProtocolProposal(steps=[{
        "id": f"step-{index}", "label": "Wait", "operations": "Wait.",
        "bpl_fragment": fragment, "source_ids": ["S1"]}
        for index, fragment in enumerate(fragments)])
    with pytest.raises(ValueError, match="^invalid_protocol_fragment$"):
        formal._assemble_draft(proposal)


def test_complete_multiline_string_and_comment_remain_byte_exact(bpl_python):
    import bridge.web.protocol_formalization as formal
    fragment = 'culture(note: "first\nsecond \\"quoted\\" {[(]}", timing: "8 days")\n/* keep } protocol Other { */\nrinse()'
    proposal = formal.ProtocolProposal(steps=[{
        "id": "first", "label": "Culture", "operations": "Culture for 8 days and rinse.",
        "bpl_fragment": fragment, "source_ids": ["S1"]}])
    draft = formal._assemble_draft(proposal)
    assert draft.steps[0].bpl_fragment == fragment
    assert draft.bpl == "protocol UploadedProtocol {\n  " + fragment + "\n}\n"
    compiled = formal.compile_bpl(draft.bpl, bpl_python)
    assert compiled["syntax_state"] == compiled["compiler_state"] == "passed"


@pytest.mark.parametrize("prefix", [b"{partial-response", b"x" * 65536 + b"end"], ids=["short", "nonaligned"])
def test_short_interrupted_provider_body_is_preserved_before_chunk_buffering(monkeypatch, prefix):
    import base64
    import httpx
    from types import SimpleNamespace
    import bridge.web.protocol_formalization as formal
    class Interrupted(httpx.SyncByteStream):
        def __iter__(self):
            yield prefix
            raise httpx.ReadError("controlled disconnect")
    real_client = httpx.Client
    monkeypatch.setattr(formal.httpx, "Client", lambda **kwargs: real_client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=Interrupted())), **kwargs))
    settings = SimpleNamespace(model="test-model", model_action_protocol="json",
                               model_base_url="https://provider.invalid/v1", model_api_key="test-key")
    with pytest.raises(formal.ProtocolResponseError) as caught:
        formal.generate(settings, {"sources": [], "supplements": []})
    assert str(caught.value) == "protocol_provider_unavailable"
    receipt = caught.value.receipt
    assert base64.b64decode(receipt["body_base64"]) == prefix
    assert receipt["captured_bytes"] == len(prefix)
    assert receipt["captured_sha256"] == hashlib.sha256(prefix).hexdigest()
    assert receipt["truncated"] is True and receipt["status_code"] == 200


@pytest.mark.parametrize("body", [
    'culture(\n target: "cells", time: "8 days")',
    'culture(factors: {\n "N2": 1%})',
    'culture(targets: [\n "cells"])',
])
def test_pinned_call_expression_newline_is_not_ignored(bpl_python, body):
    from bridge.web.protocol_formalization import compile_bpl
    broken = compile_bpl("protocol Probe {\n " + body + "\n}", bpl_python)
    assert broken["syntax_state"] == "failed" and broken["compiler_state"] == "not_run"
    fixed = compile_bpl("protocol Probe {\n " + body.replace("\n", " ") + "\n}", bpl_python)
    assert fixed["syntax_state"] == fixed["compiler_state"] == "passed"



@pytest.mark.parametrize(("fragment", "expected"), [
    ('culture(\n target: "cells", time: "8 days"\n)',
     'culture(  target: "cells", time: "8 days" )'),
    ('culture(factors: {\n "N2": 1%\n})',
     'culture(factors: {  "N2": 1% })'),
    ('culture(targets: [\n "cells"\n])',
     'culture(targets: [  "cells" ])'),
    ('culture(\n note: "first\nsecond", /* preserve\ncomment */ time: "8 days"\n)\nrinse()',
     'culture(  note: "first\nsecond", /* preserve\ncomment */ time: "8 days" )\nrinse()'),
])
def test_call_layout_is_normalized_without_rewriting_protected_text_or_operations(bpl_python, fragment, expected):
    import bridge.web.protocol_formalization as formal
    proposal = formal.ProtocolProposal(steps=[{
        "id": "first", "label": "Culture", "operations": "Culture as specified.",
        "bpl_fragment": fragment, "source_ids": ["S1"]}])
    before = proposal.model_dump()
    draft = formal._assemble_draft(proposal)
    assert proposal.model_dump() == before
    assert draft.steps[0].bpl_fragment == expected
    assert draft.bpl == "protocol UploadedProtocol {\n  " + expected + "\n}\n"
    assert (draft.steps[0].id, draft.steps[0].operations, draft.steps[0].source_ids) == (
        "first", "Culture as specified.", ["S1"])
    assert formal._assemble_draft(draft).model_dump() == draft.model_dump()
    compiled = formal.compile_bpl(draft.bpl, bpl_python)
    assert compiled["syntax_state"] == compiled["compiler_state"] == "passed"


def test_layout_normalization_does_not_swallow_a_line_comment_terminator():
    import bridge.web.protocol_formalization as formal
    fragment = 'culture(note: "cells", // preserve comment\n time: "8 days")'
    proposal = formal.ProtocolProposal(steps=[{
        "id": "first", "label": "Culture", "operations": "Culture for 8 days.",
        "bpl_fragment": fragment, "source_ids": ["S1"]}])
    draft = formal._assemble_draft(proposal)
    assert draft.steps[0].bpl_fragment == fragment


def test_assembled_fragment_size_is_bounded_for_the_complete_program():
    import bridge.web.protocol_formalization as formal
    fragment = 'culture(note: "' + "x" * 65536 + '")'
    proposal = formal.ProtocolProposal(steps=[{
        "id": sid, "label": "Culture", "operations": "Culture.",
        "bpl_fragment": fragment, "source_ids": ["S1"]} for sid in ("first", "second")])
    with pytest.raises(ValueError, match="^bpl_size_limit$"):
        formal._assemble_draft(proposal)


def test_compiled_protocol_cannot_be_rewritten_during_option_only_repair():
    import bridge.web.protocol_formalization as formal
    proposal = formal.ProtocolProposal(steps=[{
        "id": "first", "label": "Wait", "operations": "Wait.",
        "bpl_fragment": "wait()", "source_ids": ["S1"]}])
    original = formal._assemble_draft(proposal)
    before = original.model_dump()
    with pytest.raises(ValueError, match="^invalid_protocol_repair$"):
        formal._repair_draft(original, formal.ProtocolRepair(step_fragments=[
            {"step_id": "first", "bpl_fragment": "rinse()"}]), allow_fragments=False)
    assert original.model_dump() == before


@pytest.mark.parametrize("protocol", ["json", "deepseek_tools"])
def test_provider_repair_reassembles_source_fragments_without_regenerating_source_content(monkeypatch, protocol):
    from types import SimpleNamespace
    import httpx
    import bridge.web.protocol_formalization as formal
    supplied = {"sources": [{"id": "S1", "kind": "protocol", "text": "Wait for the required period."}],
                "supplements": []}
    original = draft_fixture(supplied, missing=True)
    original.steps[0].bpl_fragment = "not_present()"
    original.questions[0].options = [formal.QuestionOption(value="2 h", label="两小时")]
    before = original.model_dump()
    wire = {"step_fragments": [{"step_id": "step-1", "bpl_fragment": "wait()"}],
            "question_options": [{"question_id": "duration", "options": []}]}
    captured = []
    real_client = httpx.Client
    def response(request):
        captured.append(json.loads(request.content))
        message = ({"content": None, "tool_calls": [{"type": "function", "function": {
                    "name": "formalize_protocol", "arguments": json.dumps(wire)}}]}
                   if protocol == "deepseek_tools" else {"content": json.dumps(wire)})
        return httpx.Response(200, json={"model": "test-reported-model", "choices": [{"message": message}]})
    monkeypatch.setattr(formal.httpx, "Client",
                        lambda **kwargs: real_client(transport=httpx.MockTransport(response), **kwargs))
    settings = SimpleNamespace(model="test-model", model_action_protocol=protocol,
                               model_base_url="https://provider.invalid/v1", model_api_key="test-key")
    repaired = formal.generate(settings, supplied, previous=original,
                               diagnostics=[{"code": "bpl_compilation_failed", "syntax_state": "failed",
                                             "compiler_state": "not_run"}])
    assert original.model_dump() == before
    assert repaired.bpl == "protocol UploadedProtocol {\n  wait()\n}\n"
    assert repaired.steps[0].bpl_fragment == "wait()"
    assert repaired.steps[0].operations == before["steps"][0]["operations"]
    assert repaired.steps[0].source_ids == ["S1"]
    assert repaired.questions[0].title == before["questions"][0]["title"]
    assert repaired.questions[0].options == []
    assert repaired.excluded_sources == original.excluded_sources
    assert repaired._repair_response["step_fragments"][0]["step_id"] == "step-1"
    schema = (captured[0]["tools"][0]["function"]["parameters"] if protocol == "deepseek_tools" else
              json.loads(captured[0]["messages"][0]["content"].split("\nRequired JSON schema: ", 1)[1]))
    assert set(schema["properties"]) == {"step_fragments", "question_options", "source_additions",
                                         "question_additions", "source_resolutions"}
    assert schema["additionalProperties"] is False
    assert '"operations"' not in json.dumps(schema)
    assert schema["properties"]["question_additions"]["maxItems"] == 0
    assert schema["properties"]["source_resolutions"]["maxItems"] == 0
    assert formal.validate_draft(repaired, supplied, compiler_fixture(repaired.bpl, None), original)


@pytest.mark.parametrize("patch", [
    {"step_fragments": [{"step_id": "unknown", "bpl_fragment": "wait()"}]},
    {"step_fragments": [{"step_id": "step-1", "bpl_fragment": "wait()"},
                        {"step_id": "step-1", "bpl_fragment": "wait()"}]},
    {"question_options": [{"question_id": "unknown", "options": []}]},
    {"steps": [{"id": "step-1", "operations": "Change the experimental procedure."}]},
])
def test_protocol_repair_cannot_address_unknown_or_semantic_fields(patch):
    import bridge.web.protocol_formalization as formal
    supplied = {"sources": [{"id": "S1", "kind": "protocol", "text": "Wait for the required period."}],
                "supplements": []}
    original = draft_fixture(supplied, missing=True)
    before = original.model_dump()
    with pytest.raises(ValueError):
        formal._repair_draft(original, formal.ProtocolRepair.model_validate(patch))
    assert original.model_dump() == before


def provider_wire(protocol, payload):
    arguments = json.dumps(payload, ensure_ascii=False) if isinstance(payload, dict) else payload
    message = ({"content": None, "tool_calls": [{"type": "function", "function": {
                "name": "formalize_protocol", "arguments": arguments}}]}
               if protocol == "deepseek_tools" else {"content": arguments})
    return json.dumps({"model": "test-reported-model", "choices": [{"message": message}]},
                      ensure_ascii=False).encode()


def install_protocol_responses(monkeypatch, protocol, replies):
    import httpx
    import bridge.web.protocol_formalization as formal
    captured = []
    real_client = httpx.Client
    def response(request):
        captured.append(json.loads(request.content))
        return httpx.Response(200, content=replies[min(len(captured) - 1, len(replies) - 1)])
    monkeypatch.setattr(formal.httpx, "Client",
                        lambda **kwargs: real_client(transport=httpx.MockTransport(response), **kwargs))
    return captured




@pytest.mark.parametrize("protocol", ["json", "deepseek_tools"])
@pytest.mark.parametrize("specified", [False, True], ids=["missing-duration", "specified-text-duration"])
def test_unparsed_duration_requires_source_review_even_when_model_omits_questions(
        client, tmp_path, monkeypatch, bpl_python, protocol, specified):
    import bridge.web.protocol_formalization as formal
    real_generate, real_compile = formal.generate, formal.compile_bpl
    source = "Wait for 8 days." if specified else "Wait for the required period."
    phrase = "8 days" if specified else "the required period"
    sid, aid, pid = prepare_protocol(client, tmp_path, monkeypatch, text=source)
    service = client.app.state.service
    service.settings = replace(service.settings, model_action_protocol=protocol, protocol_compiler_python=bpl_python)
    monkeypatch.setattr(formal, "generate", real_generate)
    monkeypatch.setattr(formal, "compile_bpl", real_compile)
    proposal = {"steps": [{"id": "wait-stage", "label": "Wait", "operations": source,
                           "bpl_fragment": 'wait(duration: "' + phrase + '")', "source_ids": ["S1"]}],
                "questions": [], "excluded_sources": []}
    question = {"id": "duration", "title": "这一步应等待多久，或达到什么结束条件？",
                "step_ids": ["wait-stage"], "source_ids": ["S1"], "options": []}
    patch = ({"source_resolutions": [{"step_id": "wait-stage", "line": 2, "column": 3, "quote": "8 days"}]} if specified else
             {"question_additions": [question]})
    captured = install_protocol_responses(monkeypatch, protocol,
                [provider_wire(protocol, proposal), provider_wire(protocol, patch)])
    assert protocol_action(client, sid, aid, pid, "formalize").status_code == 200
    settle(client, sid)
    item = representation(client, sid, aid, pid)
    assert item["state"] == "complete" and len(captured) == 2
    version = item["latest"]
    assert version["syntax_state"] == version["compiler_state"] == "passed"
    assert version["coverage_state"] == ("complete_for_extracted_scope" if specified else "needs_input")
    assert [q["id"] for q in version["questions"]] == ([] if specified else ["duration"])
    assert version["review_state"] == "unreviewed"
    assert "duration_unresolved" in {i["code"] for i in version["unchecked"]}
    attempts = [json.loads(p.read_text()) for p in sorted(
        (service.directory(sid) / "protocol-attempts" / pid).glob("*/*.json"))]
    assert attempts[0]["error"] == "protocol_source_review_required"
    assert attempts[0]["draft"]["questions"] == []
    assert attempts[0]["draft"]["steps"] == attempts[1]["draft"]["steps"]
    assert attempts[0]["draft"]["bpl"] == attempts[1]["draft"]["bpl"] == version["bpl"]
    diagnostic = json.loads(captured[1]["messages"][1]["content"])["diagnostics"][0]
    assert diagnostic["source_review_required"] == [{"step_id": "wait-stage", "line": 2, "column": 3, "code": "duration_unresolved"}]
    if specified:
        assert attempts[1]["source_resolutions"] == {"wait-stage:2:3": "8 days"}
    assert service.load(sid)["plan"] is None and not service.load(sid)["_tool_runs"]


def test_omitted_duration_review_cannot_silently_publish_after_retry_budget(
        client, tmp_path, monkeypatch, bpl_python):
    import bridge.web.protocol_formalization as formal
    real_generate, real_compile = formal.generate, formal.compile_bpl
    sid, aid, pid = prepare_protocol(client, tmp_path, monkeypatch, text="Wait for the required period.")
    service = client.app.state.service
    service.settings = replace(service.settings, model_action_protocol="json", protocol_compiler_python=bpl_python)
    monkeypatch.setattr(formal, "generate", real_generate)
    monkeypatch.setattr(formal, "compile_bpl", real_compile)
    proposal = {"steps": [{"id": "wait-stage", "label": "Wait", "operations": "Wait for the required period.",
                           "bpl_fragment": 'wait(duration: "the required period")', "source_ids": ["S1"]}],
                "questions": [], "excluded_sources": []}
    captured = install_protocol_responses(monkeypatch, "json",
                [provider_wire("json", proposal), provider_wire("json", {})])
    protocol_action(client, sid, aid, pid, "formalize")
    settle(client, sid)
    item = representation(client, sid, aid, pid)
    assert item["state"] == "unavailable" and item["latest"] is None
    assert item["error"] == "protocol_source_review_required" and len(captured) == 3



@pytest.mark.parametrize("patch", [
    {"source_resolutions": [{"step_id": "unknown", "line": 2, "column": 3, "quote": "8 days"}]},
    {"source_resolutions": [{"step_id": "step-1", "line": 2, "column": 28, "quote": "8 days"}]},
    {"source_resolutions": [{"step_id": "step-1", "line": 2, "column": 3, "quote": "2 h"}]},
    {"source_resolutions": [{"step_id": "step-1", "line": 2, "column": 3, "quote": "8 days"},
                            {"step_id": "step-1", "line": 2, "column": 3, "quote": "8 days"}]},
    {"question_additions": [{"id": "duration", "title": "Replace old question", "step_ids": ["step-1"],
                              "source_ids": ["S1"], "options": []}]},
    {"question_additions": [{"id": "new", "title": "Unbound question", "step_ids": [],
                              "source_ids": ["S1"], "options": []}]},
    {"question_additions": [{"id": "new", "title": "Unknown step", "step_ids": ["unknown"],
                              "source_ids": ["S1"], "options": []}]},
])
def test_source_review_patch_rejects_unbound_outcomes_and_preserves_original(patch):
    import bridge.web.protocol_formalization as formal
    supplied = {"sources": [{"id": "S1", "kind": "protocol", "text": "Wait for 8 days."}], "supplements": []}
    original = draft_fixture(supplied, missing=True)
    before = original.model_dump()
    with pytest.raises(ValueError):
        formal._repair_draft(original, formal.ProtocolRepair.model_validate(patch),
            available_sources={"S1": supplied["sources"][0], "S2": {"text": "Wait for 2 h."}}, review_targets={("step-1", 2, 3)})
    assert original.model_dump() == before and original._source_resolutions == {}


@pytest.mark.parametrize("separator", ["\n", " "], ids=["separate-lines", "same-line"])
def test_one_known_wait_cannot_resolve_another_unparsed_wait_in_same_source_step(
        client, tmp_path, monkeypatch, bpl_python, separator):
    import bridge.web.protocol_formalization as formal
    real_generate, real_compile = formal.generate, formal.compile_bpl
    sid, aid, pid = prepare_protocol(client, tmp_path, monkeypatch, text="Wait for 8 days, then wait for the required period.")
    service = client.app.state.service
    service.settings = replace(service.settings, model_action_protocol="json", protocol_compiler_python=bpl_python)
    monkeypatch.setattr(formal, "generate", real_generate)
    monkeypatch.setattr(formal, "compile_bpl", real_compile)
    proposal = {"steps": [{"id": "wait-stage", "label": "Wait", "operations": "Wait for 8 days, then wait for the required period.",
                           "bpl_fragment": 'wait(duration: "8 days")' + separator + 'wait(duration: "the required period")',
                           "source_ids": ["S1"]}], "questions": [], "excluded_sources": []}
    patch = {"source_resolutions": [{"step_id": "wait-stage", "line": 2, "column": 3, "quote": "8 days"}]}
    captured = install_protocol_responses(monkeypatch, "json",
                [provider_wire("json", proposal), provider_wire("json", patch)])
    protocol_action(client, sid, aid, pid, "formalize")
    settle(client, sid)
    item = representation(client, sid, aid, pid)
    assert item["state"] == "unavailable" and item["latest"] is None
    assert len(captured) == 3
    remaining = json.loads(captured[2]["messages"][1]["content"])["diagnostics"][0]["source_review_required"]
    assert remaining == [{"step_id": "wait-stage", "line": 3 if separator == "\n" else 2, "column": 1 if separator == "\n" else 28, "code": "duration_unresolved"}]


def test_protocol_named_argument_is_not_a_protocol_declaration(bpl_python):
    import bridge.web.protocol_formalization as formal
    fragment = 'culture(protocol: "terminal differentiation")'
    draft = formal._assemble_draft(formal.ProtocolProposal(steps=[{
        "id": "first", "label": "Culture", "operations": "Culture.",
        "bpl_fragment": fragment, "source_ids": ["S1"]}]))
    assert draft.bpl == 'protocol UploadedProtocol {\n  culture(protocol: "terminal differentiation")\n}\n'
    result = formal.compile_bpl(draft.bpl, bpl_python)
    assert result["syntax_state"] == result["compiler_state"] == "passed"


@pytest.mark.parametrize("protocol", ["json", "deepseek_tools"])
def test_compiled_step_can_add_missing_source_without_changing_its_content(
        client, tmp_path, monkeypatch, bpl_python, protocol):
    import bridge.web.protocol_formalization as formal
    real_generate, real_compile = formal.generate, formal.compile_bpl
    sid, aid, pid = prepare_protocol(client, tmp_path, monkeypatch,
                                    text="Culture on day 36.\n\nUse basal medium.")
    service = client.app.state.service
    service.settings = replace(service.settings, model_action_protocol=protocol, protocol_compiler_python=bpl_python)
    monkeypatch.setattr(formal, "generate", real_generate)
    monkeypatch.setattr(formal, "compile_bpl", real_compile)
    proposal = {"steps": [{"id": "stage", "label": "Culture", "operations": "Culture on day 36 using basal medium.",
                           "bpl_fragment": 'culture(timing: "day 36", medium: "basal medium")',
                           "source_ids": ["S2"]}], "questions": [], "excluded_sources": []}
    patch = {"source_additions": [{"step_id": "stage", "add_source_ids": ["S1"]}]}
    captured = install_protocol_responses(monkeypatch, protocol, [provider_wire(protocol, proposal), provider_wire(protocol, patch)])
    assert protocol_action(client, sid, aid, pid, "formalize").status_code == 200
    settle(client, sid)
    item = representation(client, sid, aid, pid)
    assert item["state"] == "complete" and len(captured) == 2
    version = item["latest"]
    assert version["syntax_state"] == version["compiler_state"] == "passed"
    assert version["review_state"] == "unreviewed"
    assert version["steps"][0]["source_ids"] == ["S2", "S1"]
    assert [s["text"] for s in version["steps"][0]["sources"]] == ["Use basal medium.", "Culture on day 36."]
    attempts = [json.loads(p.read_text()) for p in sorted(
        (service.directory(sid) / "protocol-attempts" / pid).glob("*/*.json"))]
    assert attempts[0]["error"] == "unsupported_literal"
    assert attempts[0]["compiler_result"]["syntax_state"] == attempts[0]["compiler_result"]["compiler_state"] == "passed"
    before = attempts[0]["draft"]
    after = attempts[1]["draft"]
    assert before["bpl"] == after["bpl"] == version["bpl"]
    assert before["steps"][0]["source_ids"] == ["S2"]
    assert {k: v for k, v in before["steps"][0].items() if k != "source_ids"} == {
        k: v for k, v in after["steps"][0].items() if k != "source_ids"}
    assert before["questions"] == after["questions"] and before["excluded_sources"] == after["excluded_sources"]
    assert attempts[1]["repair_response"]["source_additions"] == patch["source_additions"]
    data = json.loads(captured[1]["messages"][1]["content"])
    assert data["diagnostics"][0]["unsupported_literal"] == {"step_ids": ["stage"], "value": 36.0, "unit": None}
    schema = (captured[1]["tools"][0]["function"]["parameters"] if protocol == "deepseek_tools" else
              json.loads(captured[1]["messages"][0]["content"].split("\nRequired JSON schema: ", 1)[1]))
    assert schema["properties"]["step_fragments"]["maxItems"] == 0
    source_patch = schema["properties"]["source_additions"]["items"]
    assert source_patch["properties"]["step_id"]["enum"] == ["stage"]
    assert source_patch["properties"]["add_source_ids"]["items"]["enum"] == ["S1", "S2"]
    assert service.load(sid)["plan"] is None and not service.load(sid)["_tool_runs"]


@pytest.mark.parametrize("patch", [
    {"source_additions": [{"step_id": "unknown", "add_source_ids": ["S2"]}]},
    {"source_additions": [{"step_id": "step-1", "add_source_ids": ["unknown"]}]},
    {"source_additions": [{"step_id": "step-1", "add_source_ids": ["S2", "S2"]}]},
    {"source_additions": [{"step_id": "step-1", "add_source_ids": ["S2"]},
                          {"step_id": "step-1", "add_source_ids": ["S2"]}]},
    {"source_additions": [{"step_id": "step-1", "add_source_ids": ["S2"], "source_ids": ["S2"]}]},
    {"source_additions": [{"step_id": "step-1", "add_source_ids": ["S2"], "operations": "Change procedure."}]},
])
def test_source_additions_cannot_replace_citations_or_address_unknown_targets(patch):
    import bridge.web.protocol_formalization as formal
    supplied = {"sources": [{"id": "S1", "text": "Wait."}], "supplements": []}
    original = draft_fixture(supplied, missing=True)
    before = original.model_dump()
    with pytest.raises(ValueError):
        formal._repair_draft(original, formal.ProtocolRepair.model_validate(patch), available_sources={"S1", "S2"})
    assert original.model_dump() == before


@pytest.mark.parametrize("protocol", ["json", "deepseek_tools"])
@pytest.mark.parametrize("invalid", [
    {"step_fragments": [{"step_id": "unknown", "bpl_fragment": 'culture(time: "8 days")'}]},
    {"step_fragments": [{"step_id": "step-1", "bpl_fragment": 'culture(time: "8 days")'},
                        {"step_id": "step-1", "bpl_fragment": 'culture(time: "8 days")'}]},
    {"steps": [{"id": "step-1", "operations": "Replace the source procedure."}]},
    "{broken JSON",
], ids=["unknown-target", "duplicate-target", "semantic-field", "malformed-json"])
def test_rejected_provider_responses_are_retained_before_validation(
        client, tmp_path, monkeypatch, bpl_python, protocol, invalid):
    import base64
    import bridge.web.protocol_formalization as formal
    real_generate, real_compile = formal.generate, formal.compile_bpl
    sid, aid, pid = prepare_protocol(client, tmp_path, monkeypatch, text="Culture for 8 days.")
    service = client.app.state.service
    service.settings = replace(service.settings, model_action_protocol=protocol, protocol_compiler_python=bpl_python)
    monkeypatch.setattr(formal, "generate", real_generate)
    monkeypatch.setattr(formal, "compile_bpl", real_compile)
    proposal = {"steps": [{"id": "step-1", "label": "Culture", "operations": "Culture for 8 days.",
                           "bpl_fragment": "culture(time: 8 days)", "source_ids": ["S1"]}],
                "questions": [], "excluded_sources": []}
    first, rejected = provider_wire(protocol, proposal), provider_wire(protocol, invalid)
    captured = install_protocol_responses(monkeypatch, protocol, [first, rejected])
    assert protocol_action(client, sid, aid, pid, "formalize").status_code == 200
    settle(client, sid)
    item = representation(client, sid, aid, pid)
    assert item["state"] == "unavailable" and item["latest"] is None
    assert len(captured) == 3
    paths = sorted((service.directory(sid) / "protocol-attempts" / pid).glob("*/*.json"))
    assert len(paths) == 3
    for index, path in enumerate(paths):
        attempt = json.loads(path.read_text())
        expected = first if index == 0 else rejected
        receipt = attempt["provider_response"]
        assert base64.b64decode(receipt["body_base64"]) == expected
        assert receipt["captured_bytes"] == len(expected) and receipt["truncated"] is False
        assert receipt["captured_sha256"] == hashlib.sha256(expected).hexdigest()
        assert receipt["status_code"] == 200
        assert attempt["reported_model"] == "test-reported-model"
        if index:
            assert attempt["draft"] is None and attempt["error"] is not None
    assert service.load(sid)["plan"] is None and not service.load(sid)["_tool_runs"]


@pytest.mark.parametrize("protocol", ["json", "deepseek_tools"])
def test_invalid_repair_retains_prior_compiler_diagnostics_for_the_next_request(
        client, tmp_path, monkeypatch, bpl_python, protocol):
    import bridge.web.protocol_formalization as formal
    real_generate, real_compile = formal.generate, formal.compile_bpl
    sid, aid, pid = prepare_protocol(client, tmp_path, monkeypatch, text="Culture for 8 days.")
    service = client.app.state.service
    service.settings = replace(service.settings, model_action_protocol=protocol, protocol_compiler_python=bpl_python)
    monkeypatch.setattr(formal, "generate", real_generate)
    monkeypatch.setattr(formal, "compile_bpl", real_compile)
    proposal = {"steps": [{"id": "step-1", "label": "Culture", "operations": "Culture for 8 days.",
                           "bpl_fragment": "culture(time: 8 days)", "source_ids": ["S1"]}],
                "questions": [], "excluded_sources": []}
    replies = [provider_wire(protocol, proposal),
               provider_wire(protocol, {"step_fragments": [{"step_id": "unknown", "bpl_fragment": "wait()"}]}),
               provider_wire(protocol, {"step_fragments": [{"step_id": "step-1",
                                                              "bpl_fragment": 'culture(time: "8 days")'}]})]
    captured = install_protocol_responses(monkeypatch, protocol, replies)
    assert protocol_action(client, sid, aid, pid, "formalize").status_code == 200
    settle(client, sid)
    item = representation(client, sid, aid, pid)
    assert item["state"] == "complete" and item["latest"]["generation"]["request_count"] == 3
    assert item["latest"]["syntax_state"] == item["latest"]["compiler_state"] == "passed"
    assert item["latest"]["steps"][0]["operations"] == "Culture for 8 days."
    assert item["latest"]["steps"][0]["sources"][0]["text"] == "Culture for 8 days."
    data = json.loads(captured[2]["messages"][1]["content"])
    assert data["diagnostics"][0]["syntax_state"] == "failed"
    diagnostic = next(d for d in data["diagnostics"] if d["code"] == "SYNTAX_UNEXPECTED_CHARACTER")
    assert diagnostic["line"] == 2 and diagnostic["step_ids"] == ["step-1"]


def test_oversized_provider_response_retains_only_an_explicit_bounded_prefix(client, tmp_path, monkeypatch):
    import base64
    import bridge.web.protocol_formalization as formal
    real_generate = formal.generate
    sid, aid, pid = prepare_protocol(client, tmp_path, monkeypatch)
    monkeypatch.setattr(formal, "generate", real_generate)
    prefix = b"x" * (1024 * 1024)
    install_protocol_responses(monkeypatch, "json", [prefix + b"overflow"])
    assert protocol_action(client, sid, aid, pid, "formalize").status_code == 200
    settle(client, sid)
    item = representation(client, sid, aid, pid)
    assert item["state"] == "unavailable" and item["latest"] is None
    service = client.app.state.service
    for path in (service.directory(sid) / "protocol-attempts" / pid).glob("*/*.json"):
        attempt = json.loads(path.read_text())
        receipt = attempt["provider_response"]
        assert receipt["truncated"] is True and receipt["captured_bytes"] == len(prefix)
        assert base64.b64decode(receipt["body_base64"]) == prefix
        assert receipt["captured_sha256"] == hashlib.sha256(prefix).hexdigest()
        assert attempt["error"] == "provider_response_too_large"


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



@pytest.mark.parametrize("protocol", ["json", "deepseek_tools"])
@pytest.mark.parametrize("incorporated", [False, True], ids=["ignored-answer", "incorporated-answer"])
def test_latest_user_answer_must_be_accounted_for_in_generated_steps(
        client, tmp_path, monkeypatch, bpl_python, protocol, incorporated):
    import bridge.web.protocol_formalization as formal
    real_generate, real_compile = formal.generate, formal.compile_bpl
    sid, aid, pid = prepare_protocol(client, tmp_path, monkeypatch, text="Wait for the required period.")
    monkeypatch.setattr(formal, "generate",
        lambda settings, context, previous=None, diagnostics=None: draft_fixture(context, missing=True))
    protocol_action(client, sid, aid, pid, "formalize")
    settle(client, sid)
    before = representation(client, sid, aid, pid)
    service = client.app.state.service
    service.settings = replace(service.settings, model_action_protocol=protocol, protocol_compiler_python=bpl_python)
    monkeypatch.setattr(formal, "generate", real_generate)
    monkeypatch.setattr(formal, "compile_bpl", real_compile)
    proposal = {"steps": [{"id": "wait-stage", "label": "Wait",
        "operations": "Wait for 2 h." if incorporated else "Wait for the required period.",
        "bpl_fragment": "wait(duration: 2 h)" if incorporated else 'wait(duration: "required period")',
        "source_ids": ["S1", "U1"] if incorporated else ["S1"]}],
        "questions": [{"id": "duration", "title": "这一步需等待多久？", "step_ids": ["wait-stage"],
                       "source_ids": ["S1"], "options": []}], "excluded_sources": []}
    # Replay the actual false resolution; literal source membership alone cannot
    # make an ignored user answer participate in the generated representation.
    patch = {"source_resolutions": [{"step_id": "wait-stage", "line": 2, "column": 3,
                                     "quote": "Wait for the required period."}]}
    captured = install_protocol_responses(monkeypatch, protocol,
        [provider_wire(protocol, proposal), provider_wire(protocol, patch), provider_wire(protocol, {})])
    assert protocol_action(client, sid, aid, pid, "answer", question_id="duration",
        value="Wait for 2 h.", other=True, unsure=False).status_code == 200
    settle(client, sid)
    after = representation(client, sid, aid, pid)
    if incorporated:
        assert after["state"] == "complete" and len(captured) == 1
        assert after["latest"]["bpl"] == 'protocol UploadedProtocol {\n  wait(duration: 2 h)\n}\n'
        assert after["latest"]["steps"][0]["source_ids"] == ["S1", "U1"]
        assert after["latest"]["steps"][0]["origin"] == "source_and_user"
        assert after["latest"]["coverage_state"] == "complete_for_extracted_scope"
        assert after["latest"]["review_state"] == "unreviewed"
    else:
        assert after["state"] == "unavailable" and len(captured) == 3
        assert after["error"] == "source_accounting_incomplete"
        assert after["latest"]["id"] == before["latest"]["id"]
        assert after["latest"]["coverage_state"] == "needs_input"
        assert len(after["versions"]) == 1
    assert service.load(sid)["plan"] is None and not service.load(sid)["_tool_runs"]


@pytest.mark.parametrize("protocol", ["json", "deepseek_tools"])
def test_proposal_exclusion_choices_are_only_protocol_sources(monkeypatch, protocol):
    from types import SimpleNamespace
    import bridge.web.protocol_formalization as formal
    proposal = {"steps": [{"id": "wait-stage", "label": "Wait", "operations": "Wait for 2 h.",
                           "bpl_fragment": "wait(duration: 2 h)", "source_ids": ["S1"]}],
                "questions": [], "excluded_sources": []}
    captured = install_protocol_responses(monkeypatch, protocol, [provider_wire(protocol, proposal)])
    supplied = {"sources": [{"id": "S1", "text": "Wait for 2 h."}], "supplements": [
        {"id": "U1", "text": "", "unsure": True, "superseded": False},
        {"id": "U2", "text": "Historical answer.", "unsure": False, "superseded": True}]}
    settings = SimpleNamespace(model="test-model", model_action_protocol=protocol,
                               model_base_url="https://provider.invalid/v1", model_api_key="test-key")
    draft = formal.generate(settings, supplied)
    assert draft.excluded_sources == []
    schema = (captured[0]["tools"][0]["function"]["parameters"] if protocol == "deepseek_tools" else
              json.loads(captured[0]["messages"][0]["content"].split("\nRequired JSON schema: ", 1)[1]))
    assert schema["properties"]["excluded_sources"]["items"]["properties"]["source_id"]["enum"] == ["S1"]

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
