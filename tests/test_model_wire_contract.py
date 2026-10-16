"""Actual provider requests must obey the independent per-purpose privacy contract."""
from copy import deepcopy
from types import SimpleNamespace
import json

import httpx
import pytest

from bridge.web import provider
from bridge.web.assessment_prompt import biological_context
from bridge.web.evidence import assessment_model_evidence
from bridge.web.literature import model_context
from model_wire_contract import assert_model_context, assert_model_request
from test_web_interpretation_review import settings, proposal, finding
from test_web_interpretation_revision import PATCH


def context_and_hypotheses(monkeypatch):
    # Synthetic private identities exercise the real projection/aliasing layer.
    local = [{
        "alias": "PRIVATE_RECEIPT_HASH", "state": "available", "tool_id": "P0-06",
        "tool_version": "0.11.1", "execution_state": "succeeded",
        "score_state": "unavailable", "domain_score": None,
        "provenance": {"receipt_sha256": "PRIVATE_RECEIPT_HASH", "path": "/PRIVATE_DATA"},
        "summary": {
            "program_summaries": [{"program_id": "PRIVATE_PROGRAM", "method_id": "PROC-SCORE-SCANPY",
                "source_gene_set": "HALLMARK_APOPTOSIS", "mean": 0.2,
                "n_observations": 100, "assessment_state": "available"}],
            "marker_observations": [{"gene_detection": {"FOXA2": {
                "count": 20, "denominator": 100, "state": "measured"}},
                "source_definition_decisions": {"L1:private": "evaluate"}}],
        },
        "measurements": [{
            "alias": "PRIVATE_MEASUREMENT_" + str(i), "metric_name": "mean_s_score",
            "raw_value": 0.2, "numerator": None, "denominator": 100, "unit": "score",
            "evidence_state": "measured", "score_state": "unavailable",
            "domain_score": None, "interval": None, "interval_confidence_level": None,
            "measurement_class": "gate_input_measurement", "source_execution_state": "succeeded",
        } for i in range(4)],
    }]
    evidence, _ = assessment_model_evidence(local)
    hypotheses = proposal()
    citations = [row["citation_alias"] for row in evidence[0]["measurements"]]
    hypotheses[0].update(evidence_aliases=citations, feature_queries=["FOXA2"],
        evidence_relations=[{"evidence_alias": alias, "relation": "limits",
            "rationale": "Aggregate evidence does not establish biological identity.",
            "applicability": "Current selected view."} for alias in citations])
    scope = SimpleNamespace(input_revision=7, binding={"intake": {"facts": {
        "product_family": "neural", "culture_day": 28, "independent_cultures": None,
        "product_name": "PRIVATE_PRODUCT", "cell_line": "PRIVATE_CELL_LINE",
        "protocol_body": "PRIVATE_PROTOCOL"}}},
        literature_enabled=True, literature_concept_refs=["neural_progenitor"],
        max_literature_searches=3, max_literature_reads=6)
    # Exercise the real metadata/read projection; only the external fetch is
    # replaced. New model-default fields must cross the independent contract.
    from bridge.web import literature as literature_provider
    raw = dict(id="1", source="MED", title="Synthetic public source", pubYear="2020",
        authorString="Synthetic author", abstractText="A synthetic public abstract.",
        pubTypeList={"pubType": ["Journal Article"]},
        commentCorrectionList={"commentCorrection": [{"type": "Erratum", "id": "3",
            "source": "MED", "reference": "Synthetic correction", "note": None}]})
    metadata = literature_provider._metadata(raw)
    with monkeypatch.context() as external:
        external.setattr(literature_provider, "_fetch", lambda query: ([raw], 1))
        source = literature_provider.read(metadata)["source"]
    assert source is not None
    hypotheses = [provider.AssessmentHypothesis.model_validate(row).model_dump(mode="json")
                  for row in hypotheses]
    literature = model_context({"literature": {"sources": [source], "discovered": [metadata],
        "requests": [{"action": "read_literature", "source_ref": metadata["source_ref"],
                      "state": "complete", "private": "PRIVATE_LITERATURE_REQUEST"}],
        "searches_used": 1, "reads_used": 1}}, scope)
    context = dict(purpose="assessment", question="Interpret the aggregate evidence.",
        options=[dict(id="O-synthetic", tool_id="P0-02", mode_id=None, kind="check",
            name="Cell state", summary="Inspect candidate cell state.", scientific_status="unqualified",
            execution_state="not_executed_in_scope", prerequisites_state="satisfied_this_turn")],
        allowed_modes=[dict(tool_id="P0-02", mode_id=None)],
        evidence=evidence, results_sent_to_model=True, biological_context=biological_context(scope),
        blockers=[dict(tool_id="P0-06", mode_id="method_runtime_source_bound",
                       reason_codes=["scientific_resource_required"])],
        interpretation_gaps=[], literature=literature,
        report_after_explanation=True,
        report_preparation=dict(state="graph_required", explanation_after_graph_required=True),
        workflow_handoff=dict(state="report_ready_after_current_explanation",
                              explanation_version=1, prior_report_state="none"),
        previous_action_error="provider_action_invalid_or_unavailable",
        previous_action_error_detail=dict(category="action_schema",
            issues=[dict(path="decision.hypotheses[]", type="missing", code="invalid_feature_query")]),
        feature_coverage=dict(object_version="1.0.0", complete=False, feature_count=3,
            semantics="exact_identifier_membership_not_expression_or_biological_absence",
            results=[dict(identifier="FOXA2", state="present"), dict(identifier="TH", state="unknown")],
            upload_sha256="PRIVATE_UPLOAD_HASH", input_revision=7,
            matrix_location="PRIVATE_MATRIX", identifier_column="PRIVATE_COLUMN"))
    return context, hypotheses


def invoke(monkeypatch, protocol, operation, *, shared=True, mutate=None):
    context, hypotheses = context_and_hypotheses(monkeypatch)
    if operation == "repair":
        context["revision"] = dict(hypotheses=hypotheses, issues=[finding()])
    if not shared:
        context.update(evidence=[], results_sent_to_model=False,
                       biological_context={"source": "not_shared", "facts": {}})
        context.pop("feature_coverage")
    before = deepcopy(context)
    calls = []
    client_cls = httpx.Client
    def respond(request):
        payload = json.loads(request.content)
        # Both positive tests and injected regressions traverse the same gate
        # on the actual serialized HTTP request.
        if mutate is not None:
            mutate(payload)
        sent = assert_model_request(operation, payload, shared=shared)
        calls.append((payload, sent))
        body = ({"issues": []} if operation == "review" else
                {"patches": [PATCH]} if operation == "repair" else
                {"decision": {"action": "stop", "reason": "no_discriminating_check"}})
        function = {"generation": "assessment", "review": "review_interpretation",
                    "repair": "revise_interpretation"}[operation]
        message = ({"content": json.dumps({**body, **({"action": "assessment"} if operation == "generation" else {})})}
                   if protocol == "json" else {"content": None, "tool_calls": [{
                       "id": "contract", "type": "function", "function": {
                           "name": function, "arguments": json.dumps(body)}}]})
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": message}]})
    monkeypatch.setattr(provider.httpx, "Client",
        lambda **kw: client_cls(transport=httpx.MockTransport(respond), **kw))
    if operation == "review":
        result = provider.review_interpretation(settings(protocol), hypotheses, context)
    else:
        result = provider.converse(settings(protocol), [{"role": "user", "content": context["question"]}], context)
    assert context == before
    return calls, result


@pytest.mark.parametrize("protocol", ["json", "deepseek_tools"])
@pytest.mark.parametrize("operation", ["generation", "review", "repair"])
def test_actual_model_requests_obey_purpose_allowlists(monkeypatch, protocol, operation):
    calls, _ = invoke(monkeypatch, protocol, operation)
    assert len(calls) == 1
    payload, sent = calls[0]
    assert "PRIVATE_" not in json.dumps(payload)
    assert sent["feature_coverage"]["results"] == [
        {"identifier": "FOXA2", "state": "present"}, {"identifier": "TH", "state": "unknown"}]
    assert sent["biological_context"]["facts"]["independent_cultures"] is None
    # Four repeated measurement rows take the real compact-table branch.
    assert set(sent["evidence"][0]["measurements"]) == {"columns", "rows", "missing"}
    if operation == "review":
        assert sent["hypotheses"][0]["feature_queries"] == ["FOXA2"]
    elif operation == "repair":
        assert sent["revision"]["hypotheses"][0]["feature_queries"] == ["FOXA2"]


@pytest.mark.parametrize("protocol", ["json", "deepseek_tools"])
def test_status_only_actual_request_has_no_result_facts(monkeypatch, protocol):
    calls, _ = invoke(monkeypatch, protocol, "generation", shared=False)
    assert len(calls) == 1
    assert "PRIVATE_" not in json.dumps(calls[0][0])


@pytest.mark.parametrize("operation", ["review", "repair"])
def test_unshared_review_or_repair_never_reaches_transport(monkeypatch, operation):
    with pytest.raises(ValueError, match="^result_sharing_disabled$"):
        invoke(monkeypatch, "json", operation, shared=False)


@pytest.mark.parametrize("operation", ["generation", "review", "repair"])
def test_wire_gate_catches_private_coverage_field_reintroduced_by_projection(monkeypatch, operation):
    original = provider._feature_coverage_wire
    def leaking(snapshot):
        return {**original(snapshot), "upload_sha256": "PRIVATE_REGRESSION"}
    monkeypatch.setattr(provider, "_feature_coverage_wire", leaking)
    with pytest.raises(AssertionError, match="feature_coverage: unregistered keys.*upload_sha256"):
        invoke(monkeypatch, "json", operation)


@pytest.mark.parametrize("location", ["top", "nested", "table_column", "table_value", "alias_map",
    "table_rows_mapping", "table_missing_mapping", "table_row_mapping"])
def test_wire_gate_rejects_unknown_fields_at_every_encoding_layer(monkeypatch, location):
    def inject(payload):
        text = payload["messages"][0]["content"].split("\nSafe execution context: ", 1)[1]
        context, end = json.JSONDecoder().raw_decode(text)
        if location == "top":
            context["future_private"] = "PRIVATE_REGRESSION"
        elif location == "nested":
            context["biological_context"]["facts"]["future_private"] = "PRIVATE_REGRESSION"
        elif location == "alias_map":
            row = context["evidence"][0]["summary"]["marker_observations"][0]
            row["gene_detection"]["PRIVATE_ID"] = {"count": 1}
        else:
            table = context["evidence"][0]["measurements"]
            assert isinstance(table, dict)
            if location == "table_column":
                table["columns"].append("future_private")
                for row, missing in zip(table["rows"], table["missing"]):
                    row.append(None)
                    missing.append(len(row)-1)
            elif location == "table_value":
                table["rows"][0][0] = {"future_private": "PRIVATE_REGRESSION"}
            else:
                table.update(columns=["alias"], rows=[["C1"]], missing=[[]])
                private = {"future_private": "PRIVATE_REGRESSION"}
                if location == "table_rows_mapping":
                    table["rows"] = {"x": private}
                elif location == "table_missing_mapping":
                    table["missing"] = {"": private}
                else:
                    table["rows"] = [{"x": private}]
        prefix = payload["messages"][0]["content"].split("\nSafe execution context: ", 1)[0]
        payload["messages"][0]["content"] = prefix + "\nSafe execution context: " + json.dumps(context) + text[end:]
    with pytest.raises(AssertionError):
        invoke(monkeypatch, "json", "generation", mutate=inject)


def test_status_only_contract_rejects_registered_but_unshared_facts(monkeypatch):
    context, _ = context_and_hypotheses(monkeypatch)
    context["results_sent_to_model"] = False
    # Keys alone cannot enforce consent: these facts are otherwise allowlisted.
    with pytest.raises(AssertionError):
        assert_model_context("generation", provider.assessment_wire_context(context), shared=False)


def test_native_assessment_repeats_sequential_action_contract_after_evidence(monkeypatch):
    calls, _ = invoke(monkeypatch, "deepseek_tools", "generation")
    payload = calls[0][0]
    trailing = payload["messages"][0]["content"].split("\nNext action only.", 1)[1]
    assert "exactly one assessment tool call" in trailing
    assert "Do not batch or parallelize" in trailing
    assert "Wait for the updated context" in trailing
    assert "parallel_tool_calls" not in payload


def test_native_assessment_rejects_batched_source_reads_without_retry(monkeypatch):
    original = httpx.Client
    calls = []
    def respond(request):
        calls.append(request)
        return httpx.Response(200, json={"choices": [{"finish_reason": "tool_calls", "message": {
            "content": None, "tool_calls": [
                {"type": "function", "function": {"name": "assessment", "arguments": json.dumps({
                    "decision": {"action": "read_literature", "source_ref": ref}})}}
                for ref in ["MED:1", "MED:2"]]}}]})
    monkeypatch.setattr(provider.httpx, "Client",
        lambda **kw: original(transport=httpx.MockTransport(respond), **kw))
    context, _ = context_and_hypotheses(monkeypatch)
    with pytest.raises(ValueError, match="^invalid_model_tool_call_count$"):
        provider.converse(settings("deepseek_tools"),
            [{"role": "user", "content": context["question"]}], context)
    assert len(calls) == 1
