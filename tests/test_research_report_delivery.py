from __future__ import annotations

import csv
import hashlib
import importlib
from io import StringIO
import json
import shutil
from pathlib import Path

import pytest

from bridge.tool_packages._structured_runtime import canonical_json_bytes
from bridge.tool_packages.p0_09_evidence_compiler.queries import EvidenceGraphQueries
from bridge.tool_packages.p0_10_claim_verifier.models import ReportDraft, report_content_hash
from bridge.toolkit.contracts import StructuredInputRef, ToolRequestV2
from bridge.toolkit.registry import ToolRegistry
from test_p0_09_evidence_compiler import _run, _bundle, _candidate


def research():
    name = "bridge.tool_packages.p0_10_claim_verifier.research"
    assert importlib.util.find_spec(name) is not None, "research delivery module must exist"
    return importlib.import_module(name)


@pytest.fixture(scope="module")
def graph_path(tmp_path_factory):
    root = tmp_path_factory.mktemp("research-graph")
    run = _run(root)
    assert run.execution_state.value == "succeeded"
    return run.request.output_dir / run.run_id / "case_evidence_graph_manifest.json"


def request_for(root, graph_path, draft):
    r = research()
    contract = r.load_research_release_contract()
    root.mkdir(parents=True, exist_ok=True)
    objects = [
        ("report_draft", "bridge://schemas/report-draft/v0.1", draft, "0.1.0"),
        ("claim_policy_spec", "bridge://schemas/claim-policy-spec/v0.1", contract.claim_policy, "0.1.0"),
        ("statement_registry", r.RESEARCH_STATEMENT_SCHEMA_REF, contract.statement_registry, "0.2.0"),
    ]
    refs = []
    for role, schema_ref, value, version in objects:
        path = root / (role + ".json")
        path.write_bytes(canonical_json_bytes(value.model_dump(mode="json"), indent=2))
        refs.append(StructuredInputRef(input_id=role, role=role, schema_ref=schema_ref,
            path=path, object_version=version, sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            media_type="application/json"))
    refs.append(StructuredInputRef(input_id="graph", role="evidence_graph_manifest",
        schema_ref="bridge://schemas/case-evidence-graph-manifest/v0.1", path=graph_path,
        object_version=str(json.loads(graph_path.read_bytes())["graph_version"]),
        sha256=hashlib.sha256(graph_path.read_bytes()).hexdigest(), media_type="application/json"))
    return ToolRequestV2(request_id="research-report", tool_id="P0-10",
                         object_inputs=refs, output_dir=root / "outputs")


def execute(request):
    spec = ToolRegistry.load_default().describe("P0-10")
    module, name = spec.adapter_ref.split(":")
    return getattr(importlib.import_module(module), name).run(request, spec)


def make_draft(graph_path):
    return research().build_research_draft(graph_manifest_path=graph_path, input_revision="7",
                                         created_at="2026-09-11T00:00:00Z")


def alter_draft(draft, **changes):
    payload = draft.model_dump(mode="json")
    payload.update(changes)
    payload["content_hash"] = report_content_hash(payload)
    return ReportDraft.model_validate(payload)


def test_real_compiler_graph_to_registered_verifier_and_identical_attachments(graph_path, tmp_path):
    r = research()
    draft = make_draft(graph_path)
    run = execute(request_for(tmp_path, graph_path, draft))
    assert run.execution_state.value == "succeeded", run.reason_codes
    assert run.result["release_state"] == "verified"
    assert run.result["public_export_eligibility"] == "ineligible"
    assert run.result["benchmark_id"] is None
    assert run.result_schema_ref == r.RESEARCH_RESULT_SCHEMA_REF
    paths = {a.path.name: a.path for a in run.artifacts}
    snapshot = r.ResearchAnalysisSnapshot.model_validate_json(paths["research_snapshot.json"].read_bytes())
    assert snapshot.input_revision == "7"
    assert snapshot.graph_manifest_sha256 == hashlib.sha256(graph_path.read_bytes()).hexdigest()
    assert snapshot.domain_score is None
    records = json.loads(snapshot.source_evidence_records_json)
    assert records == [x.model_dump(mode="json") for x in EvidenceGraphQueries.open(graph_path).evidence_record_set.records]
    assert records[0]["value"] == 0.75
    assert records[0]["numerator"] == 75 and records[0]["denominator"] == 100
    for name in ["research_report.html", "research_report.json", "research_report.csv", "research_report.svg"]:
        content = paths[name].read_text()
        assert snapshot.snapshot_sha256 in content
        assert "<script" not in content and "https://" not in content
    rows = list(csv.DictReader(StringIO(paths["research_report.csv"].read_text())))
    assert rows[0]["value"] == "0.75"
    assert rows[0]["numerator"] == "75" and rows[0]["denominator"] == "100"
    assert json.loads(snapshot.missing_requirements_json)
    assert "分子=75" in draft.claim_blocks[0].text
    assert "分母=100" in draft.claim_blocks[0].text
    assert "目标纯度" in paths["research_report.html"].read_text()
    rerun = execute(request_for(tmp_path, graph_path, draft))
    assert rerun.run_id == run.run_id and rerun.execution_state.value == "succeeded"


@pytest.mark.parametrize("change", ["value", "binding", "unit", "missing_reference", "revision", "case", "renderer", "interpretation", "public", "graph"])
def test_tampered_drafts_never_produce_verified_downloads(graph_path, tmp_path, change):
    draft = make_draft(graph_path)
    blocks = [x.model_dump(mode="json") for x in draft.claim_blocks]
    edits = {}
    if change == "value":
        blocks[0]["text"] = blocks[0]["text"].replace("0.75", "0.76")
    elif change == "binding":
        blocks[0]["value_bindings"] = []
    elif change == "unit":
        blocks[0]["value_bindings"][0]["raw_unit"] = "percent"
    elif change == "missing_reference":
        blocks[0]["evidence_refs"] = []
    elif change == "revision":
        edits["report_version"] = "8"
    elif change == "case":
        blocks[0]["product_case_ref"] = "product-case:other@1"
    elif change == "renderer":
        edits["renderer_id"] = "UNAPPROVED"
    elif change == "interpretation":
        blocks[0]["claim_type"] = "domain_interpretation"
        blocks[0]["text"] = "仅供研究：此结果说明产品成熟。"
        blocks[0]["value_bindings"] = []
    elif change == "public":
        edits["audience"] = "public_candidate"
    else:
        edits["report_id"] = "report:stale"
    edits["claim_blocks"] = blocks
    draft = alter_draft(draft, **edits)
    run = execute(request_for(tmp_path, graph_path, draft))
    assert run.result is not None, run.reason_codes
    assert run.result["release_state"] in {"release_blocked", "review_required"}
    names = {a.path.name for a in run.artifacts}
    assert "report_draft.json" in names and "claim_verification_result.json" in names
    assert not any(name.startswith("research_report.") for name in names)


def test_snapshot_mismatch_and_mutation_refused(graph_path, tmp_path):
    r = research()
    run = execute(request_for(tmp_path, graph_path, make_draft(graph_path)))
    snapshot_path = next(a.path for a in run.artifacts if a.path.name == "research_snapshot.json")
    snapshot = r.ResearchAnalysisSnapshot.model_validate_json(snapshot_path.read_bytes())
    result = r.ResearchClaimVerificationResult.model_validate(run.result)
    altered = snapshot.model_copy(update={"input_revision": "8"})
    with pytest.raises(ValueError):
        r.render_research_snapshot(snapshot=altered, result=result)
    with pytest.raises(ValueError):
        r.render_research_snapshot(snapshot=snapshot, result=result.model_copy(update={"report_content_hash": "f" * 64}))


@pytest.mark.parametrize("hostile", ["/home/private/person.csv", "https://example.com", "<svg onload=alert(1)>", "token=secret", "person@example.com"])
def test_hostile_snapshot_content_refused(graph_path, tmp_path, hostile):
    r = research()
    run = execute(request_for(tmp_path, graph_path, make_draft(graph_path)))
    path = next(a.path for a in run.artifacts if a.path.name == "research_snapshot.json")
    payload = json.loads(path.read_bytes())
    source = json.loads(payload["source_evidence_record_set_json"])
    source["records"][0]["provenance_refs"] = [hostile]
    payload["source_evidence_record_set_json"] = json.dumps(source)
    payload["snapshot_sha256"] = research()._digest({k: v for k, v in payload.items() if k != "snapshot_sha256"})
    with pytest.raises(ValueError):
        r.ResearchAnalysisSnapshot.model_validate(payload)


def test_formula_csv_cell_is_inert():
    assert research()._csv_cell("=1+1") == "'=1+1"
    assert research()._csv_cell("\t@SUM(1)") == "'\t@SUM(1)"
    assert research()._csv_cell("-3") == "'-3"


def test_altered_backing_graph_refused_without_report(graph_path, tmp_path):
    graph_copy = tmp_path / "graph"
    shutil.copytree(graph_path.parent, graph_copy)
    records_path = graph_copy / "evidence_records.json"
    raw = records_path.read_bytes()
    records_path.write_bytes(raw.replace(b"0.75", b"0.76"))
    with pytest.raises(ValueError):
        make_draft(graph_copy / graph_path.name)


def test_recomputed_snapshot_digest_cannot_hide_source_value_change(graph_path, tmp_path):
    r = research()
    run = execute(request_for(tmp_path, graph_path, make_draft(graph_path)))
    path = next(a.path for a in run.artifacts if a.path.name == "research_snapshot.json")
    payload = json.loads(path.read_bytes())
    payload["source_evidence_record_set_json"] = payload["source_evidence_record_set_json"].replace("0.75", "0.76")
    payload["snapshot_sha256"] = r._digest({k: v for k, v in payload.items() if k != "snapshot_sha256"})
    with pytest.raises(ValueError, match="snapshot_source_hash_mismatch"):
        r.ResearchAnalysisSnapshot.model_validate(payload)


def test_opposing_and_inferred_sources_remain_separate(tmp_path):
    measured = _candidate(candidate_id="evidence-candidate:measured")
    inferred = _candidate(candidate_id="evidence-candidate:inferred",
                          metric_id="native_method_observation", relation="contradicts", value=0.25)
    inferred["evidence_state"] = "inferred"
    inferred["numerator"] = 25
    inferred["interval"] = {"lower": 0.15, "upper": 0.35, "confidence_level": 0.95}
    run = _run(tmp_path / "compiler", bundle=_bundle(candidates=[measured, inferred]))
    assert run.execution_state.value == "succeeded", run.reason_codes
    path = run.request.output_dir / run.run_id / "case_evidence_graph_manifest.json"
    draft = make_draft(path)
    run = execute(request_for(tmp_path / "report", path, draft))
    assert run.result["release_state"] == "verified", run.result
    snapshot_path = next(a.path for a in run.artifacts if a.path.name == "research_snapshot.json")
    snapshot = research().ResearchAnalysisSnapshot.model_validate_json(snapshot_path.read_bytes())
    records = json.loads(snapshot.source_evidence_records_json)
    assert {r["relation"] for r in records} == {"supports", "contradicts"}
    assert {r["evidence_state"] for r in records} == {"measured", "inferred"}
    assert any("推断（inferred）" in c.text for c in draft.claim_blocks)
    assert snapshot.domain_score is None


def test_versioned_models_export_valid_schemas_without_legacy_benchmark():
    from jsonschema import Draft202012Validator
    r = research()
    for model in (r.ResearchStatementRegistry, r.ResearchClaimVerificationResult, r.ResearchAnalysisSnapshot):
        Draft202012Validator.check_schema(model.model_json_schema())
    from bridge.tool_packages.p0_10_claim_verifier.verifier import release_contract_sha256
    assert release_contract_sha256() == "c8a9237652cba4e6b3eb1c4f4215437980f0f480a0944d232abddeef5c4236c8"


@pytest.mark.parametrize("state,label", [("unknown", "未知"), ("unavailable", "不可用")])
def test_unavailable_and_unknown_do_not_become_zero(tmp_path, state, label):
    candidate = _candidate(value=None)
    candidate.update(evidence_state=state, numerator=None, denominator=None, interval=None)
    compiled = _run(tmp_path / "compiler", bundle=_bundle(candidates=[candidate]))
    assert compiled.execution_state.value == "succeeded", compiled.reason_codes
    path = compiled.request.output_dir / compiled.run_id / "case_evidence_graph_manifest.json"
    draft = make_draft(path)
    assert f"状态={label}（{state}）" in draft.claim_blocks[0].text
    assert "值=未提供" in draft.claim_blocks[0].text
    assert draft.claim_blocks[0].value_bindings == []
    run = execute(request_for(tmp_path / "report", path, draft))
    assert run.result["release_state"] == "verified", run.result
    csv_path = next(a.path for a in run.artifacts if a.path.name == "research_report.csv")
    row = next(csv.DictReader(StringIO(csv_path.read_text())))
    assert row["value"] == "" and row["numerator"] == "" and row["denominator"] == ""
    assert row["evidence_state"] == state


def test_html_and_svg_have_only_inert_self_contained_content(graph_path, tmp_path):
    from html.parser import HTMLParser
    from xml.etree import ElementTree
    class Tags(HTMLParser):
        def __init__(self):
            super().__init__()
            self.tags = []
        def handle_starttag(self, tag, attrs):
            self.tags.append(tag)
            assert not any(key.startswith("on") or key in {"href", "src"} for key, value in attrs)
    run = execute(request_for(tmp_path, graph_path, make_draft(graph_path)))
    paths = {a.path.name: a.path for a in run.artifacts}
    parser = Tags()
    parser.feed(paths["research_report.html"].read_text())
    assert set(parser.tags) <= {"html", "meta", "title", "style", "body", "h1", "h2", "p", "pre"}
    svg = ElementTree.fromstring(paths["research_report.svg"].read_bytes())
    assert {node.tag.rsplit("}", 1)[-1] for node in svg.iter()} == {"svg", "metadata", "text"}
    metadata = next(node.text for node in svg.iter() if node.tag.endswith("metadata"))
    assert json.loads(metadata) == json.loads(paths["research_snapshot.json"].read_bytes())
    manifest = json.loads(paths["artifact_manifest.json"].read_bytes())
    for artifact in manifest["artifacts"]:
        assert hashlib.sha256(paths[artifact["filename"]].read_bytes()).hexdigest() == artifact["sha256"]
