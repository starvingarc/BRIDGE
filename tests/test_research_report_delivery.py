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




def _revised_research_graphs(root, metric):
    first = _run(root / "first", bundle=_bundle(candidates=[
        {**_candidate(metric_id=metric), "numerator": 75}]))
    paths = [first.request.output_dir / first.run_id / "case_evidence_graph_manifest.json"]
    for action in ("supersede", "invalidate"):
        prior = paths[-1]
        manifest = json.loads(prior.read_bytes())
        records = json.loads((prior.parent / "evidence_records.json").read_bytes())["records"]
        requirements = json.loads((prior.parent / "evidence_requirements.json").read_bytes())["requirements"]
        original = {path: path.read_bytes() for path in prior.parent.iterdir() if path.is_file()}
        candidate = _candidate(metric_id=metric, value=0.8,
            revision_action=action,
            predecessor_ref=records[-1]["evidence_id"] + "@" + str(records[-1]["evidence_version"]))
        candidate["numerator"] = 80
        result = _run(root / action, bundle=_bundle(candidates=[candidate],
            prior_records=records, prior_requirements=requirements,
            base_graph_ref={"graph_id": manifest["graph_id"], "graph_version": manifest["graph_version"],
                "manifest_sha256": hashlib.sha256(prior.read_bytes()).hexdigest()}),
            base_manifest_path=prior)
        assert result.execution_state.value == "succeeded", result.reason_codes
        assert all(path.read_bytes() == raw for path, raw in original.items())
        paths.append(result.request.output_dir / result.run_id / "case_evidence_graph_manifest.json")
    return paths


@pytest.fixture(scope="module")
def revised_research_graphs(tmp_path_factory):
    return _revised_research_graphs(tmp_path_factory.mktemp("research-revisions"), "native_s_g2m_fraction")


@pytest.fixture(scope="module")
def revised_process_graphs(tmp_path_factory):
    return _revised_research_graphs(tmp_path_factory.mktemp("process-revisions"), "native_mean_proc_score_scanpy_s")



@pytest.mark.parametrize("revision,record_index,withdrawn", [
    (0, 0, False), (1, 0, True), (1, 1, False), (2, 1, True),
])
def test_legacy_verifier_respects_compiled_revision_history(
        revised_research_graphs, tmp_path, revision, record_index, withdrawn):
    from test_p0_10_claim_verifier import _request, _report_payload
    graph_path = revised_research_graphs[revision]
    graph = EvidenceGraphQueries.open(graph_path)
    record_set = graph.evidence_record_set
    record = record_set.records[record_index]
    assert record.lifecycle_state.value == "active"
    payload = _report_payload(audience="internal_research")
    payload["evidence_record_set_ref"] = f"{record_set.record_set_id}@{record_set.record_set_version}"
    claim = payload["claim_blocks"][0]
    rendered = str(record.value) + (f" {record.unit}" if record.unit else "")
    claim.update(claim_ref=record.claim_ref.ref,
                 product_case_ref=record.product_case_ref.ref,
                 text=f"{record.metric_id}: {rendered}.", evidence_refs=[record.ref])
    claim["value_bindings"][0].update(
        source_evidence_ref=record.ref, canonical_numeric_string=str(record.value),
        raw_unit=record.unit,
        text_span=(len(record.metric_id) + 2, len(record.metric_id) + 2 + len(rendered)))
    payload["content_hash"] = report_content_hash(payload)
    request = _request(tmp_path, report=payload)
    refs = [ref for ref in request.object_inputs if ref.role != "evidence_graph_manifest"]
    refs.append(StructuredInputRef(
        input_id="graph", role="evidence_graph_manifest",
        schema_ref="bridge://schemas/case-evidence-graph-manifest/v0.1",
        object_version=str(revision + 1), path=graph_path,
        sha256=hashlib.sha256(graph_path.read_bytes()).hexdigest(), media_type="application/json"))
    run = execute(request.model_copy(update={"object_inputs": refs}))
    assert run.execution_state.value == "succeeded", run.reason_codes
    reasons = [check["reason_code"] for check in run.result["check_records"]]
    assert ("evidence_not_active" in reasons) is withdrawn, reasons
    assert run.result["release_state"] == ("release_blocked" if withdrawn else "verified"), reasons


@pytest.mark.parametrize("revision,expected_versions", [(1, [2]), (2, [])])
def test_revised_research_report_uses_effective_evidence_not_historical_active_flags(
        revised_research_graphs, tmp_path, revision, expected_versions):
    graph = revised_research_graphs[revision]
    context = context_for(graph)
    request = context_request(tmp_path, graph, context)
    draft_ref = next(ref for ref in request.object_inputs if ref.role == "report_draft")
    draft = ReportDraft.model_validate_json(draft_ref.path.read_bytes())
    refs = [ref for claim in draft.claim_blocks for ref in claim.evidence_refs]
    assert [int(ref.rsplit("@", 1)[1]) for ref in refs] == expected_versions
    run = execute(request)
    assert run.execution_state.value == "succeeded", run.reason_codes
    assert run.result["release_state"] == "verified", run.result
    artifacts = {a.path.name: a.path for a in run.artifacts}
    report = artifacts["research_report.html"].read_text()
    current = report.split("<details>", 1)[0]
    assert "<td>75</td>" not in current
    assert ("<td>80</td>" in current) is bool(expected_versions)
    raw = json.loads(artifacts["research_report.json"].read_bytes())
    history = json.loads(raw["source_evidence_record_set_json"])["records"]
    assert history[0]["value"] == 0.75 and history[0]["lifecycle_state"] == "active"
    assert len(history) == revision + 1
    csv_rows = list(csv.DictReader(StringIO(artifacts["research_report.csv"].read_text())))
    assert [row["evidence_version"] for row in csv_rows if row["row_type"] == "evidence"] == [
        str(version) for version in range(1, revision + 2)]
    evidence_rows = [row for row in csv_rows if row["row_type"] == "evidence"]
    assert evidence_rows[0]["lifecycle_state"] == "active"
    assert [row["effective_lifecycle_state"] for row in evidence_rows] == (
        ["superseded", "active"] if revision == 1 else ["superseded", "invalidated", "invalidated"])
    assert all(row["applicability"] == "applicable" for row in evidence_rows)
    assert [row["value"] for row in evidence_rows if row["effective_lifecycle_state"] == "active"] == (
        ["0.8"] if revision == 1 else [])




@pytest.mark.parametrize("revision", [1, 2])
def test_report_context_checks_only_effective_measurement_versions(revised_process_graphs, revision):
    r = research()
    graph = revised_process_graphs[revision]
    manifest, sha, evidence, _ = r._read_graph(graph)
    record = evidence.records[-1]
    payload = context_for(graph).model_dump(mode="json", exclude={"context_sha256"})
    payload["process_means"] = [{"source_ref": "candidate-profile:test@1",
        "measurement_ref": record.measurement_result_ref.ref, "metric_id": record.metric_id,
        "method_id": "PROC-SCORE-SCANPY", "program_id": "S", "mean": 0.8,
        "score_unit": record.unit, "n_observations": 100,
        "assessment_state": "available", "reason_codes": []}]
    context = r.seal_research_context(payload)
    if revision == 1:
        r._check_context_graph(context, manifest, sha, "7", evidence)
    else:
        with pytest.raises(ValueError, match="report_context_measurement_missing"):
            r._check_context_graph(context, manifest, sha, "7", evidence)


def context_for(graph_path, *, name="修订后的产品名称", revision="7"):
    r = research()
    manifest = json.loads(graph_path.read_bytes())
    payload = {
        "context_id": "research-context:test", "input_revision": revision,
        "graph_id": manifest["graph_id"], "graph_version": manifest["graph_version"],
        "graph_manifest_sha256": hashlib.sha256(graph_path.read_bytes()).hexdigest(),
        "product_case_ref": manifest["product_case_ref"],
        "confirmed_product_facts": {"product_name": name},
        "intake_source_ref": "confirmed-intake:test@7",
        "data_view_source_ref": "qc-profile:test@1",
        "data_view": {"view_id": "data-view:test", "view_kind": "qc_selected_observations",
            "artifact_id": "artifact:qc:selected", "sha256": "a" * 64,
            "parent_asset_id": "upload-test", "parent_asset_sha256": "b" * 64,
            "matrix_location": "layers/counts", "matrix_semantics": "raw_counts",
            "n_observations": 100, "observation_ids_sha256": "c" * 64},
        "sources": [
            {"source_ref": "confirmed-intake:test@7", "sha256": "d" * 64, "schema_ref": "bridge://schemas/confirmed-intake/v0.1"},
            {"source_ref": "qc-profile:test@1", "sha256": "e" * 64, "schema_ref": "bridge://schemas/qc-readiness-profile/v0.2"},
            {"source_ref": "candidate-profile:test@1", "sha256": "f" * 64, "schema_ref": "bridge://schemas/cell-state-candidate-profile/v1.0"}],
        "candidate_development": [{"source_ref": "candidate-profile:test@1",
            "producer_run_ref": "tool-run:test@1", "development_gate_state": "failed",
            "development_reason_codes": ["heldout_gate_failed"],
            "development_summary_sha256": "1" * 64, "development_review_version": "1.1.0",
            "development_review_sha256": "2" * 64}],
    }
    return r.seal_research_context(payload)


def context_request(root, graph_path, context):
    r = research()
    draft = r.build_research_draft(graph_manifest_path=graph_path, input_revision=context.input_revision,
        created_at="2026-09-11T00:00:00Z", report_context=context)
    request = request_for(root, graph_path, draft)
    path = root / "research_context.json"
    path.write_bytes(canonical_json_bytes(context.model_dump(mode="json"), indent=2))
    ref = StructuredInputRef(input_id="context", role="research_report_context",
        schema_ref=r.RESEARCH_CONTEXT_SCHEMA_REF, object_version="0.3.0",
        path=path, sha256=hashlib.sha256(path.read_bytes()).hexdigest(), media_type="application/json")
    return request.model_copy(update={"object_inputs": [*request.object_inputs, ref]})


def test_private_context_corrected_name_failure_and_legacy_bytes(graph_path, tmp_path):
    r = research()
    legacy = execute(request_for(tmp_path / "legacy", graph_path, make_draft(graph_path)))
    original = {a.path: a.path.read_bytes() for a in legacy.artifacts}
    context = context_for(graph_path)
    run = ToolRegistry.load_default().run(context_request(tmp_path / "current", graph_path, context))
    assert run.execution_state.value == "succeeded", run.reason_codes
    assert run.result["release_state"] == "verified"
    paths = {a.path.name: a.path for a in run.artifacts}
    snapshot = r.ResearchAnalysisSnapshotV03.model_validate_json(paths["research_snapshot.json"].read_bytes())
    assert snapshot.object_version == "0.3.0"
    assert json.loads(snapshot.report_context_json)["context_sha256"] == context.context_sha256
    for extension in ("html", "json", "csv", "svg"):
        text = paths["research_report." + extension].read_text()
        assert "修订后的产品名称" in text
        assert "heldout_gate_failed" in text
    assert "开发门槛失败" in paths["research_report.html"].read_text()
    assert "解释未验证" in paths["research_report.html"].read_text()
    assert all(path.read_bytes() == value for path, value in original.items())
    assert run.result["benchmark_id"] is None and run.result["public_export_eligibility"] == "ineligible"
    assert json.loads(snapshot.source_evidence_records_json)[0]["numerator"] == 75



@pytest.mark.parametrize("version", ["0.4.4", "0.4.5", "0.4.6"])
def test_previous_report_patch_remains_readable_but_not_a_current_run(graph_path, tmp_path, version):
    from bridge.tool_packages.p0_10_claim_verifier.adapter import adapter
    registry = ToolRegistry.load_default()
    request = request_for(tmp_path, graph_path, make_draft(graph_path))
    recorded_spec = registry.describe("P0-10").model_copy(update={"version": version})
    receipt = adapter.run(request, recorded_spec)
    assert receipt.execution_state.value == "succeeded", receipt.reason_codes
    assert receipt.result_schema_ref == research().RESEARCH_RESULT_SCHEMA_REF
    assert registry.validate_historical_result(receipt, request) == receipt
    with pytest.raises(ValueError, match="mismatched tool version"):
        registry.validate_result(receipt, request)


def test_context_report_opens_with_product_before_technical_identifiers(graph_path, tmp_path):
    context = context_for(graph_path)
    result = ToolRegistry.load_default().run(context_request(tmp_path, graph_path, context))
    assert result.execution_state.value == "succeeded"
    report = next(a.path for a in result.artifacts if a.path.name == "research_report.html").read_text()
    assert report.index(context.confirmed_product_facts.product_name) < report.index("快照 SHA-256")



def test_context_revision_graph_and_content_are_bound(graph_path, tmp_path):
    r = research()
    context = context_for(graph_path)
    renamed = context_for(graph_path, name="另一个名称")
    a = r.build_research_draft(graph_manifest_path=graph_path, input_revision="7",
        created_at="2026-09-11T00:00:00Z", report_context=context)
    b = r.build_research_draft(graph_manifest_path=graph_path, input_revision="7",
        created_at="2026-09-11T00:00:00Z", report_context=renamed)
    assert a.content_hash != b.content_hash
    with pytest.raises(ValueError):
        r.build_research_snapshot(graph_manifest_path=graph_path, report=a, report_context=renamed)
    with pytest.raises(ValueError):
        r.build_research_draft(graph_manifest_path=graph_path, input_revision="8",
            created_at="2026-09-11T00:00:00Z", report_context=context)
    with pytest.raises(ValueError):
        r.ResearchReportContext.model_validate(context.model_copy(update={"context_sha256": "0" * 64}).model_dump(mode="json"))


@pytest.mark.parametrize("text", ["<script>alert(1)</script>", "/home/private/data.csv", "token=secret", "person@example.com"])
def test_context_private_allowlist_refuses_active_or_private_data(graph_path, text):
    with pytest.raises(ValueError):
        context_for(graph_path, name=text)


@pytest.mark.parametrize("kind", ["composition", "process"])
def test_context_builder_binds_native_labels_and_actual_mean_counts(tmp_path, kind):
    from types import SimpleNamespace
    from bridge.web.research_context import build_research_context
    r = research()
    label = {"label": "L1:source-family", "assignment_state": "candidate"}
    metric = ("candidate_composition_fraction_" + r._digest(label)[:16] if kind == "composition"
              else "native_mean_proc_score_scanpy_s")
    candidate = _candidate(metric_id=metric)
    if kind == "process":
        candidate.update(value=0.125, numerator=None, denominator=None, unit="scanpy_control_adjusted_expression", interval=None)
    compilation = _run(tmp_path / "graph", bundle=_bundle(candidates=[candidate]))
    assert compilation.execution_state.value == "succeeded", compilation.reason_codes
    graph = compilation.request.output_dir / compilation.run_id / "case_evidence_graph_manifest.json"
    view = context_for(graph).data_view.model_dump(mode="json")
    facts = {"product_name": "当前确认产品"}
    intake = {"facts": facts, "signature": "confirmed"}
    scope = SimpleNamespace(upload_id="upload-test", input_revision=7,
        binding={"intake": intake, "data_view": view, "upload": {"sha256": "b" * 64}})
    state = {"_intakes": {"upload-test": intake}, "_input_revision": 7}
    values = {"qc": {"selected_data_view": view}, "graph": json.loads(graph.read_bytes())}
    measurement = {
        "measurement_id": "measurement-result:target", "metric_name": metric, "raw_value": candidate["value"],
        "unit": candidate["unit"], "numerator": candidate["numerator"], "denominator": candidate["denominator"],
        "source_run_ref": "tool-run:target@1.0.0"}
    values["measurement"] = measurement
    run = SimpleNamespace(run_id="target", tool_version="1.0.0",
        measurements=[SimpleNamespace(measurement_id=measurement["measurement_id"], model_dump=lambda **kwargs: measurement)])
    if kind == "composition":
        profile = {"input_data_view": view, "candidate_composition": [
            {**label, "fraction": 0.75, "count": 75, "denominator": 100}],
            "development_gate_state": "failed", "development_reason_codes": ["heldout_gate_failed"],
            "development_summary_sha256": "1" * 64, "development_review_version": "1.1.0",
            "development_review_sha256": "2" * 64, "scientific_qualification": "not_established"}
        profile_schema = "bridge://schemas/cell-state-candidate-profile/v1.0"
    else:
        profile = {"input_contract": {"data_view": view}, "program_summaries": [
            {"method_id": "PROC-SCORE-SCANPY", "program_id": "S", "mean": 0.125,
             "score_unit": candidate["unit"], "n_observations": 100, "assessment_state": "available", "reason_codes": []}]}
        profile_schema = "bridge://schemas/exploratory-process-profile/v0.1"
    run.result = values["profile"] = profile
    schemas = {"graph": "bridge://schemas/case-evidence-graph-manifest/v0.1",
        "measurement": "bridge://schemas/measurement-result/v0.2", "profile": profile_schema,
        "qc": "bridge://schemas/qc-readiness-profile/v0.2"}
    pool = {key: {"schema_ref": schema, "object_version": "1.0.0", "sha256": r._digest(values[key]),
        "receipt_file": "native" if key in {"profile", "measurement"} else key,
        "receipt_sha256": "f" * 64, "value_key": key} for key, schema in schemas.items()}
    pool["graph"].update(path=str(graph), sha256=hashlib.sha256(graph.read_bytes()).hexdigest())
    reports = SimpleNamespace(service=SimpleNamespace(inputs=SimpleNamespace(
        verify=lambda state, record: values[record["value_key"]])),
        _canonical_outputs=lambda state, pool, tool, schema: (
            [("qc", values["qc"], None)] if tool == "P0-01" else
            [("profile", profile, run)] if schema == profile_schema else []))
    context, dependencies = build_research_context(reports, state, scope, pool, graph_manifest_input_id="graph")
    assert {"graph", "qc", "profile", "measurement"} <= set(dependencies)
    if kind == "composition":
        assert context.composition_mapping[0].label == label["label"]
        assert context.composition_mapping[0].count == 75
        profile["candidate_composition"][0]["label"] = "wrong-label"
        reason = "composition_measurement_missing"
    else:
        assert context.process_means[0].n_observations == 100
        assert measurement["numerator"] is None and measurement["denominator"] is None
        profile["program_summaries"][0]["n_observations"] = 99
        reason = "process_count_mismatch"
    with pytest.raises(ValueError, match=reason):
        build_research_context(reports, state, scope, pool, graph_manifest_input_id="graph")

    if kind == "composition":
        profile["candidate_composition"][0]["label"] = label["label"]
    else:
        profile["program_summaries"][0]["n_observations"] = 100
    prior = json.loads((graph.parent / "evidence_records.json").read_bytes())["records"]
    manifest = json.loads(graph.read_bytes())
    invalidated = _run(tmp_path / "invalidated", bundle=_bundle(
        candidates=[{**candidate, "revision_action": "invalidate",
            "predecessor_ref": prior[0]["evidence_id"] + "@1"}],
        prior_records=prior,
        prior_requirements=json.loads((graph.parent / "evidence_requirements.json").read_bytes())["requirements"],
        base_graph_ref={"graph_id": manifest["graph_id"], "graph_version": manifest["graph_version"],
            "manifest_sha256": hashlib.sha256(graph.read_bytes()).hexdigest()}),
        base_manifest_path=graph)
    assert invalidated.execution_state.value == "succeeded", invalidated.reason_codes
    revised = invalidated.request.output_dir / invalidated.run_id / "case_evidence_graph_manifest.json"
    values["graph"] = json.loads(revised.read_bytes())
    pool["graph"].update(path=str(revised), sha256=hashlib.sha256(revised.read_bytes()).hexdigest())
    current, dependencies = build_research_context(reports, state, scope, pool, graph_manifest_input_id="graph")
    assert current.composition_mapping == [] and current.process_means == []
    assert current.candidate_development == []
    assert not {"profile", "measurement"} & set(dependencies)


def test_context_preserves_unverified_explanation_hash_history(graph_path):
    r = research()
    content = {
        "object_version": "1.0.0", "scope_digest": "a" * 64, "input_revision": 7,
        "hypotheses": [{"statement": "可能存在另一解释", "evidence_aliases": ["evidence:first"],
            "opposing_evidence_aliases": ["evidence:opposing"], "missing_evidence_aliases": [],
            "expected_observation": None, "competing_explanation": "替代解释", "discriminating_check": "P0-06"}],
        "evidence_snapshot_sha256": "b" * 64, "qualification": "proposed_explanation"}
    first = {**content, "version": 1, "content_sha256": r._digest(content),
        "predecessor_sha256": None, "created_at": "2026-09-11T00:00:00Z"}
    content2 = {**content, "evidence_snapshot_sha256": "c" * 64}
    second = {**content2, "version": 2, "content_sha256": r._digest(content2),
        "predecessor_sha256": first["content_sha256"], "created_at": "2026-09-11T01:00:00Z"}
    payload = context_for(graph_path).model_dump(mode="json", exclude={"context_sha256"})
    payload["explanation_versions"] = [first, second]
    context = r.seal_research_context(payload)
    assert context.explanation_versions[0].hypotheses[0].opposing_evidence_aliases == ["evidence:opposing"]
    assert context.explanation_versions[1].predecessor_sha256 == first["content_sha256"]
    second["hypotheses"] = []
    with pytest.raises(ValueError, match="explanation_hash_mismatch"):
        r.seal_research_context(payload)
