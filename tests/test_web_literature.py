"""Public literature transport preserves provenance and never accepts product text."""
import json
import httpx
import pytest

from bridge.web import literature


def transport(monkeypatch, responses):
    calls = []
    original = httpx.Client
    def reply(request):
        calls.append(request)
        result = responses[len(calls)-1]
        return result if isinstance(result, httpx.Response) else httpx.Response(200, json=result)
    monkeypatch.setattr(literature.httpx, "Client",
        lambda **kw: original(transport=httpx.MockTransport(reply), **kw))
    return calls


def article(**changes):
    return {"id": "12345", "source": "MED", "title": "Synthetic public article",
            "doi": "10.1000/example", "pubYear": "2024", "authorString": "Example A",
            "journalTitle": "Example Journal", "abstractText": "<p>A public <b>abstract</b>.</p>",
            **changes}


def response(rows, total=None):
    return {"hitCount": len(rows) if total is None else total, "resultList": {"result": rows}}


def test_only_registered_public_concepts_reach_fixed_provider(monkeypatch):
    calls = transport(monkeypatch, [response([article()])])
    result = literature.search(["neural_progenitor"], "proliferation")
    assert result["state"] == "complete"
    assert len(result["sources"]) == 1
    request, = calls
    assert str(request.url).startswith("https://www.ebi.ac.uk/europepmc/webservices/rest/search?")
    assert request.url.params["query"] == 'SRC:MED AND TITLE_ABS:("neural progenitor") AND TITLE_ABS:("cell cycle" OR proliferation)'
    assert "abstract" not in result["sources"][0]
    with pytest.raises(ValueError, match="public_concept"):
        literature.search(["PRIVATE_PRODUCT"], "proliferation")
    assert len(calls) == 1


def test_duplicate_doi_is_one_source_and_discovery_is_bounded(monkeypatch):
    calls = transport(monkeypatch, [response([article(), article(id="67890", doi="10.1000/EXAMPLE")], 100)])
    result = literature.search(["neural_progenitor"], "development")
    assert result["state"] == "partial"
    assert result["hit_count"] == 100
    assert len(result["sources"]) == 1
    assert calls[0].url.params["pageSize"] == "5"


def test_empty_and_unavailable_are_distinct_and_redirects_are_not_followed(monkeypatch):
    calls = transport(monkeypatch, [response([]),
        httpx.Response(302, headers={"location":"https://untrusted.invalid/data"})])
    assert literature.search(["neuron"], "identity")["state"] == "no_results"
    assert literature.search(["neuron"], "identity")["state"] == "unavailable"
    assert len(calls) == 2


def test_read_freezes_provider_metadata_and_exact_abstract_hash(monkeypatch):
    from hashlib import sha256
    calls = transport(monkeypatch, [response([article()]), response([article()])])
    discovered = literature.search(["neuron"], "identity")["sources"][0]
    result = literature.read(discovered)
    # Europe PMC EXT_ID is an identifier field, not a quoted phrase.
    assert calls[1].url.params["query"] == "SRC:MED AND EXT_ID:12345"
    source = result["source"]
    assert result["state"] == "complete"
    assert source["abstract"] == "A public abstract."
    assert source["abstract_sha256"] == sha256(b"A public abstract.").hexdigest()
    assert source["content_level"] == "abstract"
    assert source["source_ref"] == discovered["source_ref"]
    assert source["url"] == "https://europepmc.org/article/MED/12345"
    assert source["retrieved_at"]
    assert source["metadata"]["title"] == "Synthetic public article"


def test_read_missing_abstract_is_metadata_only_and_mismatched_id_is_rejected(monkeypatch):
    transport(monkeypatch, [response([article()]), response([article(abstractText="")]),
                            response([article(id="99999")])])
    discovered = literature.search(["neuron"], "identity")["sources"][0]
    result = literature.read(discovered)
    assert result["state"] == "partial"
    assert result["source"]["content_level"] == "metadata_only"
    assert result["source"]["abstract"] is None
    assert literature.read(discovered)["state"] == "unavailable"


def test_oversized_response_is_unavailable(monkeypatch):
    transport(monkeypatch, [httpx.Response(200, content=b"x" * 600000)])
    assert literature.search(["neuron"], "identity")["state"] == "unavailable"


@pytest.mark.parametrize("protocol", ["json", "deepseek_tools"])
def test_literature_actions_are_typed_and_only_offered_with_scope_budget(protocol):
    from bridge.web.provider import Action, _assessment_choices, action_tools
    from jsonschema import Draft202012Validator
    ctx = {"purpose": "assessment", "options": [], "evidence": [],
        "literature": {"search_concept_refs": ["neuron"], "searches_remaining": 1,
                       "reads_remaining": 1, "readable_source_refs": ["literature:epmc-med-12345"],
                       "sources": []}}
    schema = action_tools("assessment", assessment_choices=_assessment_choices(ctx))[0]["function"]["parameters"]
    valid = {"decision": {"action": "search_literature", "concept_refs": ["neuron"], "focus": "identity"}}
    Draft202012Validator(schema).validate(valid)
    Action.model_validate({"action": "assessment", **valid})
    assert list(Draft202012Validator(schema).iter_errors(
        {"decision": {**valid["decision"], "concept_refs": ["PRIVATE_PRODUCT"]}}))
    disabled = {**ctx, "literature": {"search_concept_refs": [], "searches_remaining": 0,
                                    "reads_remaining": 0, "readable_source_refs": [], "sources": []}}
    schema = action_tools("assessment", assessment_choices=_assessment_choices(disabled))[0]["function"]["parameters"]
    assert list(Draft202012Validator(schema).iter_errors(valid))


def test_budget_reservation_is_durable_and_repeats_cannot_bypass_it(monkeypatch):
    from types import SimpleNamespace
    scope = SimpleNamespace(literature_enabled=True, literature_concept_refs=["neuron"],
                            max_literature_searches=1, max_literature_reads=1)
    assessment = {}
    request = {"action":"search_literature", "concept_refs":["neuron"], "focus":"identity"}
    reservation = literature.reserve(assessment, scope, request)
    assert assessment["literature"]["searches_used"] == 1
    with pytest.raises(ValueError, match="unavailable"):
        literature.reserve(assessment, scope, {**request, "focus":"development"})
    with pytest.raises(ValueError, match="unavailable"):
        literature.reserve(assessment, scope, {"action":"read_literature", "source_ref":"literature:epmc-med-999"})
    assert assessment["literature"]["reads_used"] == 0
    assert reservation["state"] == "reserved"


def test_frozen_source_rejects_changed_abstract_and_external_url(monkeypatch):
    from bridge.toolkit.literature import LiteratureSource
    transport(monkeypatch, [response([article()]), response([article()])])
    discovery = literature.search(["neuron"], "identity")["sources"][0]
    raw = literature.read(discovery)["source"]
    LiteratureSource.model_validate(raw)
    for change in ({"abstract":"Different claim."}, {"url":"https://untrusted.invalid/paper"}):
        with pytest.raises(ValueError):
            LiteratureSource.model_validate({**raw, **change})


def test_discovered_papers_require_one_read_attempt_before_explanation():
    from types import SimpleNamespace
    from bridge.web.provider import _assessment_choices, action_tools
    scope = SimpleNamespace(literature_enabled=True, literature_concept_refs=["neuron"],
                            max_literature_searches=1, max_literature_reads=1)
    assessment = {"literature": {"searches_used": 1, "reads_used": 0,
        "requests": [{"action": "search_literature", "state": "complete"}],
        "discovered": [{"source_ref": "literature:epmc-med-12345"}], "sources": []}}
    def actions():
        ctx = {"options": [], "evidence": [], "literature": literature.model_context(assessment, scope)}
        schema = action_tools("assessment", assessment_choices=_assessment_choices(ctx))[0]["function"]["parameters"]
        return schema["properties"]["decision"]["properties"]["action"]["enum"]
    assert "explain" not in actions()
    assert {"read_literature", "question", "stop"} <= set(actions())
    # A failed read is a recorded limitation, not a loop or a forced citation.
    assessment["literature"]["reads_used"] = 1
    assessment["literature"]["requests"].append({"action": "read_literature",
        "source_ref": "literature:epmc-med-12345", "state": "unavailable"})
    assert "explain" in actions()
    assessment["literature"].update(reads_used=0, discovered=[])
    assert "explain" in actions()

@pytest.mark.parametrize("correction", ["Retraction in", "ExpressionOfConcernIn", "ErratumIn"])
def test_publication_notices_survive_discovery_and_frozen_read(monkeypatch, correction):
    notice = {"type": correction, "id": "67890", "source": "MED",
              "reference": "Example correction", "note": "Synthetic notice"}
    row = article(pubTypeList={"pubType": ["Journal Article"]},
        commentCorrectionList={"commentCorrection": [notice]})
    transport(monkeypatch, [response([row]), response([row])])
    metadata = literature.search(["neuron"], "identity")["sources"][0]
    source = literature.read(metadata)["source"]
    assert source["metadata"]["publication_types"] == ["Journal Article"]
    assert source["metadata"]["corrections"] == [notice]
    expected = "correction_reported" if correction == "ErratumIn" else "retraction_or_concern_reported"
    assert metadata["publication_status"] == source["metadata"]["publication_status"] == expected


def test_absent_publication_notices_remain_unknown(monkeypatch):
    transport(monkeypatch, [response([article()])])
    metadata = literature.search(["neuron"], "identity")["sources"][0]
    assert metadata["publication_status"] == "unknown"
    assert metadata["publication_types"] is None and metadata["corrections"] is None


def test_model_action_rejects_duplicate_literature_support_before_persistence():
    from bridge.web.provider import Action
    use = {"source_ref": "literature:epmc-med-12345", "rationale": "Public context",
        "species": "unknown", "lineage": "unknown", "stage": "unknown", "experimental_context": "unknown"}
    with pytest.raises(ValueError, match="duplicate_literature_support"):
        Action.model_validate({"action": "assessment", "decision": {"action": "explain",
            "hypotheses": [{"statement": "An observation.", "evidence_aliases": ["E-record"],
                "competing_explanation": "A rival.", "discriminating_check": None,
                "literature_support": [use, use]}]}})


def test_model_knows_attempted_queries_and_schema_excludes_repeating_them():
    from types import SimpleNamespace
    from jsonschema import Draft202012Validator
    from bridge.web.provider import _assessment_choices, action_tools
    scope = SimpleNamespace(literature_enabled=True,
        literature_concept_refs=["neural_progenitor", "neuron"], max_literature_searches=3, max_literature_reads=6)
    search = {"action": "search_literature", "concept_refs": ["neural_progenitor", "neuron"],
              "focus": "identity", "state": "partial"}
    read = {"action": "read_literature", "source_ref": "literature:epmc-med-12345", "state": "unavailable"}
    assessment = {"literature": {"searches_used": 1, "reads_used": 1,
        "requests": [{**search, "query": "unused", "private_extra": "not for model"},
                     {**read, "discovered": {"private_extra": "not for model"}}],
        "discovered": [], "sources": []}}
    context = literature.model_context(assessment, scope)
    assert context["request_history"] == [search, read]
    schema = action_tools("assessment", assessment_choices=_assessment_choices(
        {"options": [], "evidence": [], "literature": context}))[0]["function"]["parameters"]
    validator = Draft202012Validator(schema)
    def candidate(refs, focus):
        return {"decision": {"action": "search_literature", "concept_refs": refs, "focus": focus}}
    for refs in (["neural_progenitor", "neuron"], ["neuron", "neural_progenitor"]):
        assert list(validator.iter_errors(candidate(refs, "identity")))
    validator.validate(candidate(["neural_progenitor"], "identity"))
    validator.validate(candidate(["neural_progenitor", "neuron"], "stress"))


def test_advertised_explanation_requires_records_and_omits_unused_prose():
    from jsonschema import Draft202012Validator
    from bridge.web.provider import _assessment_choices, action_tools
    context = {"options": [], "evidence": [{"measurements": [
        {"citation_alias": "E-record", "citation_role": "observation"}]}]}
    schema = action_tools("assessment", assessment_choices=_assessment_choices(context))[0]["function"]["parameters"]
    validator = Draft202012Validator(schema)
    assert not validator.is_valid({"decision": {"action": "explain", "text": "Unbound prose."}})
    valid = {"decision": {"action": "explain", "hypotheses": [{
        "statement": "An observation.", "evidence_aliases": ["E-record"],
        "competing_explanation": "A rival.", "discriminating_check": None, "feature_queries": []}]}}
    validator.validate(valid)
    assert not validator.is_valid({"decision": {**valid["decision"], "text": "Extra prose."}})
    assert not validator.is_valid({"decision": {**valid["decision"], "reason": "no_discriminating_check"}})
    actions = schema["properties"]["decision"]["properties"]["action"]["enum"]
    assert "check" not in actions and "query" not in actions
