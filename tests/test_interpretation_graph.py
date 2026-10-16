"""Model-authored semantic relations remain source-bound through review and repair."""
import copy
import pytest
from pydantic import ValidationError
from bridge.web import provider
from bridge.web.interpretation_review import revision_context, parse_review, apply_text_revision

def hypothesis():
    return dict(statement="A precursor-like transcriptional pattern is a working hypothesis.",
        evidence_aliases=["E-observation"], opposing_evidence_aliases=[], missing_evidence_aliases=[],
        expected_observation="Matched protein measurements could distinguish the alternatives.",
        competing_explanation="Detection bias remains possible.", discriminating_check=None,
        literature_support=[], evidence_relations=[dict(evidence_alias="E-observation",
            relation="limits", rationale="This aggregate observation does not identify individual cells.",
            applicability="Only the current sample and measured transcriptional state.")],
        feature_queries=["FOXA2", "EN1"])

def test_model_selects_limitation_relation_and_retains_its_reason():
    value = provider.AssessmentHypothesis.model_validate(hypothesis()).model_dump(mode="json")
    assert value["evidence_relations"] == hypothesis()["evidence_relations"]
    assert value["feature_queries"] == ["FOXA2", "EN1"]

@pytest.mark.parametrize("change", ["unbound", "duplicate", "missing_support"])
def test_semantic_relation_cannot_escape_citations_or_recast_missing_measurement(change):
    value = hypothesis()
    if change == "unbound":
        value["evidence_relations"][0]["evidence_alias"] = "E-not-cited"
    elif change == "duplicate":
        value["evidence_relations"] *= 2
    else:
        value["missing_evidence_aliases"] = ["E-missing"]
        value["evidence_relations"].append(dict(value["evidence_relations"][0],
            evidence_alias="E-missing", relation="supports"))
    with pytest.raises(ValidationError):
        provider.AssessmentHypothesis.model_validate(value)

def test_resume_rebinds_relation_aliases_together_with_hypothesis():
    value = hypothesis()
    value["evidence_aliases"] = ["canonical-measurement"]
    value["evidence_relations"][0]["evidence_alias"] = "canonical-measurement"
    pending = {"hypotheses": [value], "issues": []}
    bound = revision_context(pending, {"evidence": {"E-new": "canonical-measurement"},
        "citation_roles": {"E-new": "observation"}})
    assert bound["hypotheses"][0]["evidence_relations"][0]["evidence_alias"] == "E-new"
    assert pending["hypotheses"][0]["evidence_relations"][0]["evidence_alias"] == "canonical-measurement"

def test_review_can_reject_semantic_relation_reason_and_repair_preserves_its_source():
    rows = [hypothesis()]
    issue = {"hypothesis_index": 0, "field": "evidence_relations",
        "code": "unsupported_observation", "quote": rows[0]["evidence_relations"][0]["rationale"],
        "reason": "The stated limitation must be tied to the supplied measurement scope."}
    assert parse_review({"issues": [issue]}, rows)["issues"] == [issue]
    revised = apply_text_revision({"patches": [{"hypothesis_index": 0, "relation_index": 0,
        "field": "evidence_relations.rationale", "text": "The measurement is a whole-sample aggregate."}]}, rows)
    assert revised[0]["evidence_relations"][0]["evidence_alias"] == "E-observation"
    assert revised[0]["evidence_relations"][0]["relation"] == "limits"
    assert revised[0]["evidence_relations"][0]["rationale"] == "The measurement is a whole-sample aggregate."
    assert rows == [hypothesis()]


def test_feature_membership_uses_selected_axis_and_exact_identifiers(tmp_path, monkeypatch):
    import h5py
    from contextlib import contextmanager
    from types import SimpleNamespace
    from bridge.web import intake
    root = tmp_path / "uploads"
    root.mkdir()
    path = root / "sample.h5ad"
    with h5py.File(path, "w") as f:
        for name, values in [("var", ["FOXA2", "EN1"]), ("raw/var", ["LMX1A", "EN1"])]:
            g = f.create_group(name)
            g.attrs["_index"] = "gene_id"
            g.create_dataset("gene_id", data=values)
    @contextmanager
    def checked(*args, **kwargs):
        assert args[3] == "a" * 64
        with path.open("rb") as stream:
            yield stream
    monkeypatch.setattr(intake, "checked_file", checked)
    service = SimpleNamespace(directory=lambda sid: tmp_path, settings=SimpleNamespace(max_upload_bytes=99999))
    state = {"id": "sid", "_uploads": {"sample": {"sha256": "a" * 64}}}
    scope = SimpleNamespace(upload_id="sample", input_revision=7,
        binding={"intake": {"facts": {"matrix_location": "raw.X", "gene_symbol_column": None}}})
    result = intake.Intake(service).feature_coverage(state, scope, [{"feature_queries": ["FOXA2", "LMX1A", "EN1"]}])
    assert result["identifier_column"] == "raw/var/gene_id"
    assert {r["identifier"]: r["state"] for r in result["results"]} == {"FOXA2": "not_found", "LMX1A": "present", "EN1": "present"}
    scope.binding["intake"]["facts"]["gene_symbol_column"] = "unavailable"
    result = intake.Intake(service).feature_coverage(state, scope, [{"feature_queries": ["EN1"]}])
    assert result["results"][0]["state"] == "unknown" and not result["complete"]


def test_incomplete_metadata_never_establishes_nonmembership():
    from bridge.toolkit.interpretation import FeatureCoverageSnapshot
    with pytest.raises(ValueError, match="incomplete_feature_absence"):
        FeatureCoverageSnapshot.model_validate(dict(upload_sha256="a"*64, input_revision=1,
            matrix_location="X", identifier_column="var/gene", complete=False,
            results=[dict(identifier="FOXA2", state="not_found")]))


def test_review_can_revise_semantic_direction_without_changing_measurement_reference():
    rows = [hypothesis()]
    revised = apply_text_revision({"patches": [{"hypothesis_index":0, "relation_index":0,
        "field":"evidence_relations.relation", "text":"contradicts"}]}, rows)
    accepted = provider.AssessmentHypothesis.model_validate(revised[0])
    assert accepted.evidence_relations[0].relation == "contradicts"
    assert accepted.evidence_relations[0].evidence_alias == rows[0]["evidence_aliases"][0]
    with pytest.raises(ValueError):
        apply_text_revision({"patches": [{"hypothesis_index":0, "relation_index":0,
            "field":"evidence_relations.relation", "text":"causes"}]}, rows)


def test_repair_can_complete_feature_queries_without_changing_citations():
    rows = [hypothesis()]
    rows[0].pop("feature_queries", None)
    revised = apply_text_revision({"patches": [{"hypothesis_index": 0,
        "field": "feature_queries", "identifiers": ["FOXA2", "EN1"]}]}, rows)
    assert revised[0]["feature_queries"] == ["FOXA2", "EN1"]
    assert revised[0]["evidence_relations"] == rows[0]["evidence_relations"]
    provider.AssessmentHypothesis.model_validate(revised[0])
    for identifiers in (["FOXA2", "FOXA2"], ["../../x"], ["X"] * 33):
        with pytest.raises(ValueError):
            apply_text_revision({"patches": [{"hypothesis_index": 0,
                "field": "feature_queries", "identifiers": identifiers}]}, rows)


def test_live_hypothesis_tool_explicitly_requires_feature_query_field():
    schema = provider.action_tools("assessment", assessment_evidence=[])[0]["function"]["parameters"]
    row = schema["properties"]["decision"]["properties"]["hypotheses"]["items"]
    assert "feature_queries" in row["required"]


def test_relation_validation_returns_safe_actionable_feedback():
    row = hypothesis()
    row['evidence_relations'][0]['evidence_alias'] = 'uncited'
    with pytest.raises(ValueError) as failure:
        provider.AssessmentHypothesis.model_validate(row)
    detail = provider.failure_detail(failure.value)
    assert detail['issues'][0]['code'] == 'interpretation_relation_not_cited'
    assert 'uncited' not in str(detail)
    assert 'code' not in provider.safe_schema_issues([{'path':'$', 'type':'value_error', 'code':'private arbitrary prose'}])[0]


def persisted_explanation(queries, coverage=True):
    from bridge.tool_packages.p0_10_claim_verifier.research import ResearchExplanationV12, _digest
    from bridge.toolkit.interpretation import FeatureCoverageSnapshot
    row = ResearchExplanationV12.model_validate(hypothesis()).model_dump(mode="json")
    row["feature_queries"] = queries
    facts = FeatureCoverageSnapshot(upload_sha256="a" * 64, input_revision=1,
        matrix_location="X", identifier_column="var/gene", complete=False,
        results=[{"identifier": "FOXA2", "state": "unknown"}]).model_dump(mode="json")
    payload = dict(object_version="1.2.0", scope_digest="b" * 64, input_revision=1,
        hypotheses=[row], evidence_snapshot_sha256="c" * 64,
        qualification="proposed_explanation", feature_coverage=facts if coverage else None,
        graph_ref=None, biological_context=None, literature=None)
    return dict(payload, content_sha256=_digest(payload), version=1,
        predecessor_sha256=None, created_at="2026-10-08T00:00:00Z")


@pytest.mark.parametrize("queries", [["FOXA2", "FOXA2"], ["../private"], [""], ["A" * 65], ["FOXA2 EN1"]])
def test_saved_explanation_rejects_the_same_invalid_feature_queries_as_wire(queries):
    from bridge.tool_packages.p0_10_claim_verifier.research import parse_research_explanation
    with pytest.raises(ValueError, match="invalid_feature_query"):
        provider.AssessmentHypothesis.model_validate({**hypothesis(), "feature_queries": queries})
    with pytest.raises(ValueError, match="invalid_feature_query"):
        parse_research_explanation(persisted_explanation(queries))


def test_saved_feature_queries_require_checked_coverage_even_when_unknown():
    from bridge.tool_packages.p0_10_claim_verifier.research import parse_research_explanation
    with pytest.raises(ValueError, match="feature_query_coverage_required"):
        parse_research_explanation(persisted_explanation(["FOXA2"], coverage=False))
    accepted = parse_research_explanation(persisted_explanation(["FOXA2"]))
    assert accepted.feature_coverage.results[0].state == "unknown"
    assert not accepted.feature_coverage.complete
    assert parse_research_explanation(persisted_explanation([], coverage=False)).feature_coverage is None
