from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import sys

import pytest
httpx = pytest.importorskip("httpx")

from bridge.toolkit.contracts import (
    ArtifactManifest,
    CellStateEvidenceProfileV3,
    MeasurementResult,
    QCReadinessProfileV2,
    ToolRequest,
    ToolRun,
)
from bridge.web.app import Settings, create_app, write_file
from bridge.web.evidence import build_result_context
from test_web_service import client, declare_counts, h5ad, new_session, settle



def test_assessment_portrait_keeps_axes_and_does_not_classify_arbitrary_programs():
    from bridge.web.evidence import assessment_portrait
    evidence = [
        {"alias": "E-target", "tool_id": "P0-03", "state": "available", "summary": {
            "channels": [{"target_identity_fraction": {"numerator": 2, "denominator": 4, "fraction": 0.5},
                          "regional_fidelity_fraction": None}],
            "reason_codes": ["state_role_mapping_unresolved"]}, "measurements": []},
        {"alias": "E-process", "tool_id": "P0-06", "state": "available", "summary": {
            "runtime_mode": "method_runtime_source_bound",
            "program_results": [{"program_id": "looks-like-hypoxia-but-unreviewed",
                "value": 3.0, "availability": "available", "reason_codes": []}]}, "measurements": []},
    ]
    axes = assessment_portrait(evidence, [])
    assert [row["id"] for row in axes] == ["cell_state", "target_identity", "regional_identity",
        "development", "composition", "process"]
    assert axes[1]["summary"]["channels"][0]["target_identity_fraction"]["fraction"] == 0.5
    assert axes[2]["summary"]["channels"][0]["regional_fidelity_fraction"] is None
    assert axes[0]["state"] == "missing"
    assert axes[-1]["summary"]["program_results"][0]["program_id"] == "looks-like-hypoxia-but-unreviewed"
    assert len(axes[-1]["families"]) == 7
    assert all(row["state"] == "unavailable" and row["reason_codes"] == ["reviewed_family_mapping_unavailable"]
        for row in axes[-1]["families"])
    evidence[-1]["summary"] = {"runtime_mode": "exploratory_process", "cell_cycle": {
        "assessment_state": "not_assessed", "s_g2m_fraction": None,
        "n_observations": 4, "reason_codes": ["cell_cycle_gene_coverage_insufficient"]}}
    families = assessment_portrait(evidence, [])[-1]["families"]
    assert families[1]["state"] == "unavailable"
    assert families[1]["reason_codes"] == ["cell_cycle_gene_coverage_insufficient"]
    assert families[1]["summary"]["s_g2m_fraction"] is None
    evidence[-1]["summary"]["cell_cycle"].update(assessment_state="available",
        s_g2m_fraction=0.5, reason_codes=[])
    families = assessment_portrait(evidence, [])[-1]["families"]
    assert families[1]["state"] == "measured" and families[1]["summary"]["n_observations"] == 4
    assert all(row["state"] == "unavailable" for index, row in enumerate(families) if index != 1)


def test_assessment_local_projection_retains_canonical_missingness_and_program_identity():
    from bridge.web.evidence import _assessment_aggregate, assessment_model_evidence
    local = _assessment_aggregate({
        "reason_codes": ["process_metadata_incomplete"],
        "program_summaries": [{"program_id": "program:reviewed-example@0.1.0",
            "availability": "unavailable", "reason_codes": ["program_gene_coverage_insufficient"]}],
        "private_path": "/private/not-allowed"})
    assert local == {"reason_codes": ["process_metadata_incomplete"], "program_summaries": [
        {"program_id": "program:reviewed-example@0.1.0", "availability": "unavailable",
         "reason_codes": ["program_gene_coverage_insufficient"]}]}
    rows = [{"alias": "E-privatehashprefix", "state": "available", "tool_id": "P0-06",
        "summary": local, "measurements": [], "provenance": {"plan_id": "private-plan"},
        "artifact_ids": ["private-artifact"]}]
    shared, binding = assessment_model_evidence(rows)
    assert shared[0]["summary"]["reason_codes"] == ["process_metadata_incomplete"]
    wire = json.dumps(shared)
    for private in ("program:reviewed-example@0.1.0", "E-privatehashprefix",
                    "private-plan", "private-artifact"):
        assert private not in wire
    assert binding["evidence"][shared[0]["alias"]] == "E-privatehashprefix"


def test_assessment_graph_model_aliases_keep_joins_without_hash_derived_ids():
    from bridge.web.evidence import assessment_model_evidence
    summary = {"graph_alias": "N-privategraphhash", "graph_version": 2,
        "query_name": "get_case_evidence_subgraph", "returned_node_count": 2,
        "returned_edge_count": 1, "truncated": False, "omitted_node_count": 0, "omitted_edge_count": 0,
        "nodes": [{"alias": "N-privatenodehash", "node_type": "EvidenceRecord",
                   "evidence_tier": "shadow", "lifecycle_state": "active"}],
        "records": [{"alias": "N-privatenodehash", "family_alias": "N-privatefamilyhash",
                     "node_type": "EvidenceRecord", "evidence_tier": "shadow", "lifecycle_state": "active",
                     "domain_id": "target_identity", "evidence_state": "inferred",
                     "metric_id": "target_identity_fraction", "unit": "fraction",
                     "applicability": "applicable", "relation": "supports", "interval": None,
                     "value": 0.5, "numerator": 2, "denominator": 4}],
        "claims": [], "reconciliations": [],
        "requirements": [], "edges": [{"source": "N-privatenodehash",
                     "target": "N-privategraphhash", "type": "supports"}]}
    local = [{"alias": "E-privatehash", "state": "available", "tool_id": "P0-09",
              "summary": summary, "measurements": []}]
    shared, bindings = assessment_model_evidence(local)
    again, _ = assessment_model_evidence(local)
    graph = shared[0]["summary"]
    assert graph["nodes"][0]["alias"] == graph["records"][0]["alias"] == graph["edges"][0]["source"]
    assert graph["edges"][0]["target"] == graph["graph_alias"]
    assert graph["records"][0]["value"] == 0.5 and graph["records"][0]["denominator"] == 4
    assert graph["records"][0]["metric_name"] == "target_identity_fraction"
    assert graph["records"][0]["metric_semantics_state"] == "available"
    assert graph["records"][0]["unit"] == "fraction" and graph["records"][0]["interval"] is None
    assert "private" not in json.dumps(shared)
    assert shared[0]["alias"] != again[0]["alias"]
    assert bindings["references"][graph["graph_alias"]] == "N-privategraphhash"


SCHEMA = "bridge://schemas/cell-state-evidence-profile/v0.3"
LABEL = "L1:Neuron_DA"
SECRETS = ("PRIVATE_SOURCE_SENTINEL", "PRIVATE_WARNING_SENTINEL",
           "PRIVATE_RESULT_SENTINEL", "PRIVATE_REFERENCE_SENTINEL",
           "PRIVATE_ARTIFACT_SENTINEL", "PRIVATE_PATH_SENTINEL")


def rows():
    common = {"label_level": "L1", "denominator_scope": "selected_data_view", "denominator": 10}
    return [
        {**common, "view": "source_specific", "source_id": "PRIVATE_SOURCE_SENTINEL",
         "label": LABEL, "state_evidence_state": "candidate", "count": 10, "fraction": 1.0},
        {**common, "view": "reconciliation_state", "source_id": None,
         "label": "consensus_supported", "state_evidence_state": "candidate", "count": 8, "fraction": 0.8},
        {**common, "view": "reconciliation_state", "source_id": None,
         "label": "source_conflict", "state_evidence_state": "unresolved", "count": 2, "fraction": 0.2},
        {**common, "view": "consensus_supported_only", "source_id": None,
         "label": LABEL, "state_evidence_state": "candidate", "count": 8, "fraction": 0.8},
    ]


def profile(run_id, *, n=10, composition=None, version="0.4.9"):
    payload = {
        "profile_id": f"cell-state-profile:{run_id}", "assay": "scRNA-seq",
        "measurement_spec_id": "PRIVATE_MEASUREMENT_SENTINEL",
        "measurement_spec_version": "1.0.0", "measurement_spec_sha256": "2" * 64,
        "measurement_spec_status": "candidate",
        "annotation_vocabulary_ref": "PRIVATE_REFERENCE_SENTINEL",
        "annotation_vocabulary_version": "0.1.0", "annotation_vocabulary_sha256": "f" * 64,
        "reference_snapshot_ref": "PRIVATE_REFERENCE_SENTINEL",
        "reference_manifest_version": "1.0.0", "reference_manifest_sha256": "1" * 64,
        "n_observations": n, "n_genes": 100, "denominator": "selected_data_view",
        "label_levels": {}, "source_support": {"secret": "PRIVATE_SOURCE_SENTINEL"},
        "marker_program_evidence": {}, "prediction_sets": {},
        "composition": composition or {"state": "shadow", "records": rows()},
        "gene_coverage": {}, "modality_sensitivity": {},
        "upstream_qc_profile_ref": "PRIVATE_QC_SENTINEL", "upstream_qc_profile_sha256": "e" * 64,
        "input_data_view": {
            "view_id": "PRIVATE_VIEW_SENTINEL", "view_kind": "qc_selected_observations",
            "artifact_id": "artifact:PRIVATE_MATRIX_SENTINEL", "sha256": "a" * 64,
            "parent_asset_id": "PRIVATE_PARENT_SENTINEL", "parent_asset_sha256": "b" * 64,
            "matrix_location": "PRIVATE_PATH_SENTINEL", "matrix_semantics": "normalized_expression",
            "n_observations": n, "observation_ids_sha256": "c" * 64},
        "open_set_state": "not_assessed", "calibration_state": "not_assessed",
        "producer_run_ref": run_id, "producer_tool_id": "P0-02",
        "producer_tool_version": version, "environment_spec_ref": "PRIVATE_ENVIRONMENT_SENTINEL",
        "warnings": ["PRIVATE_WARNING_SENTINEL"], "score_state": "shadow", "domain_score": None}
    return CellStateEvidenceProfileV3.model_validate(payload).model_dump(mode="json")


def register(service, sid, payload, *, run_id, tool_id="P0-02",
             artifact_kind="cell_state_evidence_profile", measurements=None,
             schema_ref=SCHEMA, request_assets=None):
    state = service.load(sid)
    run_root = service.directory(sid) / "runs" / run_id
    artifact_path = run_root / "PRIVATE_PATH_SENTINEL-result.json"
    raw = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()
    write_file(artifact_path, raw)
    artifact = ArtifactManifest(artifact_id=f"artifact:PRIVATE_ARTIFACT_SENTINEL:{run_id}",
        kind=artifact_kind, path=artifact_path, media_type="application/json",
        sha256=hashlib.sha256(raw).hexdigest())
    outcome = ToolRun(run_id=run_id, request=ToolRequest(request_id=f"request-{run_id}",
        tool_id=tool_id, tool_version="0.4.9", output_dir=run_root, assets=request_assets or []),
        implementation_state="implemented", execution_state="succeeded", tool_version="0.4.9",
        environment_spec_id="PRIVATE_ENVIRONMENT_SENTINEL", artifacts=[artifact],
        measurements=measurements or [], result={"secret": "PRIVATE_RESULT_SENTINEL"},
        warnings=["PRIVATE_WARNING_SENTINEL"])
    receipt_raw = outcome.model_dump_json().encode()
    receipt_file = f"PRIVATE_RECEIPT_SENTINEL-{run_id}.json"
    receipt_path = service.directory(sid) / "receipts" / receipt_file
    write_file(receipt_path, receipt_raw)
    receipt = {"file": receipt_file, "sha256": hashlib.sha256(receipt_raw).hexdigest(),
        "tool_id": tool_id, "state": "succeeded", "plan_id": f"plan-{run_id}",
        "declaration_start": None}
    state["_tool_runs"].append(receipt)
    service.inputs.register_outputs(state, outcome, receipt)
    records = [(key, value) for key, value in state["_input_objects"].items()
               if value.get("receipt_file") == receipt_file
               and value.get("schema_ref") == schema_ref]
    service.save(state)
    return {"input_id": records[-1][0] if records else None, "receipt": receipt,
            "receipt_path": receipt_path, "artifact": artifact, "artifact_path": artifact_path}


def register_profile(service, sid, *, run_id="run-evidence", composition=None, n=10,
                     tool_id="P0-02", version="0.4.9"):
    return register(service, sid, profile(run_id, n=n, composition=composition, version=version),
                    run_id=run_id, tool_id=tool_id)

def qc_measurement(
    run_id, metric_name, raw_value, denominator=4, evidence_state="measured"
):
    return MeasurementResult(
        measurement_id=f"measurement:{run_id}:{metric_name}",
        measurement_spec_id="PRIVATE_QC_SPEC_SENTINEL",
        metric_name=metric_name,
        raw_value=raw_value,
        denominator=denominator,
        score_state="unavailable",
        evidence_state=evidence_state,
        provenance_refs=["PRIVATE_QC_EVIDENCE_SENTINEL"],
    )


def qc_profile(run_id, **updates):
    payload = {
        "profile_id": f"qc-profile:{run_id}",
        "input_level": "count_ready",
        "assay": "scRNA-seq",
        "measurement_spec_status": "not_selected",
        "readiness_state": "limited",
        "schema_integrity": {
            "state": "valid",
            "n_observations": 4,
            "observation_kind": "cells",
            "n_genes": 3,
            "unique_cell_ids": True,
            "unique_gene_ids": True,
            "private_ids": ["PRIVATE_OBSERVATION_SENTINEL"],
        },
        "metadata_completeness": {"secret": "PRIVATE_METADATA_SENTINEL"},
        "matrix_provenance": {"path": "PRIVATE_PATH_SENTINEL"},
        "upstream_library_qc": {
            "state": "not_assessed", "reason": "PRIVATE_REASON_SENTINEL",
        },
        "cell_qc": {
            "count_metrics_state": "measured",
            "per_group": [{"sample": "PRIVATE_SAMPLE_SENTINEL"}],
        },
        "doublet_assessment": {
            "state": "not_assessed", "reason": "PRIVATE_REASON_SENTINEL",
        },
        "cell_calling_assessment": {
            "state": "not_assessed", "reason": "PRIVATE_REASON_SENTINEL",
        },
        "ambient_assessment": {
            "state": "not_assessed", "reason": "PRIVATE_REASON_SENTINEL",
        },
        "data_views": {"secret": "PRIVATE_VIEW_SENTINEL"},
        "module_eligibility": {},
        "missing_inputs": ["PRIVATE_MISSING_SENTINEL"],
        "warnings": ["PRIVATE_WARNING_SENTINEL"],
        "evidence_ids": ["PRIVATE_QC_EVIDENCE_SENTINEL"],
        "score_state": "unavailable",
        "domain_score": None,
        "measurement_spec_version": None,
        "selected_data_view": {
            "view_id": f"data-view:{run_id}:all-observations@0.1.0",
            "view_kind": "all_observations",
            "artifact_id": "PRIVATE_MATRIX_ARTIFACT_SENTINEL",
            "sha256": "a" * 64,
            "parent_asset_id": "PRIVATE_PARENT_SENTINEL",
            "parent_asset_sha256": "b" * 64,
            "matrix_location": "PRIVATE_PATH_SENTINEL",
            "matrix_semantics": "raw_counts",
            "n_observations": 4,
            "observation_ids_sha256": "c" * 64,
        },
    }
    payload.update(updates)
    return QCReadinessProfileV2.model_validate(payload).model_dump(mode="json")


def register_qc_profile(
    service, sid, *, run_id="run-qc-evidence", payload=None, measurements=None
):
    metrics = measurements
    if metrics is None:
        values = {
            "total_counts_median": 3.5,
            "detected_genes_median": 2.0,
            "mitochondrial_fraction_median": 0.4,
            "ribosomal_fraction_median": 0.0,
            "top_20_gene_fraction_median": 1.0,
        }
        metrics = [
            qc_measurement(run_id, name, value)
            for name, value in values.items()
        ]
        metrics.append(qc_measurement(
            run_id, "PRIVATE_UNLISTED_METRIC_SENTINEL", 999.0
        ))
    return register(
        service,
        sid,
        payload or qc_profile(run_id),
        run_id=run_id,
        tool_id="P0-01",
        artifact_kind="qc_profile_v2",
        measurements=metrics,
        schema_ref="bridge://schemas/qc-readiness-profile/v0.2",
    )


def test_projects_hand_checked_partition_and_private_binding(client):
    sid = new_session(client)["id"]
    service = client.app.state.service
    registered = register_profile(service, sid)

    summary, binding = build_result_context(service.inputs, service.load(sid))

    assert set(summary) == {"state", "evidence_ref", "tool_id", "execution_state",
        "n_observations", "denominator_scope", "composition_state", "open_set_state",
        "calibration_state", "score_state", "domain_score", "composition", "reconciliation"}
    assert summary["state"] == "available"
    assert summary["evidence_ref"] == "E1"
    assert summary["tool_id"] == "P0-02"
    assert summary["execution_state"] == "succeeded"
    assert summary["n_observations"] == 10
    assert summary["denominator_scope"] == "selected_data_view"
    assert summary["composition_state"] == "shadow"
    assert summary["composition"] == [{"label_level": "L1", "label": LABEL, "count": 8,
        "fraction": 0.8, "denominator": 10, "state_evidence_state": "candidate"}]
    assert sum(row["count"] for row in summary["reconciliation"]) == 10
    assert summary["domain_score"] is None
    assert binding == {"E1": {"input_id": registered["input_id"],
        "receipt_file": registered["receipt"]["file"],
        "receipt_sha256": registered["receipt"]["sha256"],
        "artifact_id": registered["artifact"].artifact_id,
        "artifact_sha256": registered["artifact"].sha256}}
    encoded = json.dumps(summary)
    assert "source_specific" not in encoded
    assert all(secret not in encoded for secret in SECRETS)
    assert build_result_context(service.inputs, service.load(sid)) == (summary, binding)


def test_latest_p002_receipt_without_v3_does_not_fall_back(client):
    sid = new_session(client)["id"]
    service = client.app.state.service
    register_profile(service, sid, run_id="run-older")
    register(service, sid, {"unsupported": True}, run_id="run-latest")

    assert build_result_context(service.inputs, service.load(sid)) == (
        {"state": "not_available"}, {})


def test_record_producer_label_cannot_override_canonical_receipt_identity(client):
    sid = new_session(client)["id"]
    service = client.app.state.service
    expected = register_profile(service, sid, run_id="run-p002")
    false_record = register_profile(service, sid, run_id="run-p003", tool_id="P0-03")
    state = service.load(sid)
    state["_input_objects"][false_record["input_id"]]["producer_tool_id"] = "P0-02"
    service.save(state)

    summary, binding = build_result_context(service.inputs, service.load(sid))

    assert summary["state"] == "available"
    assert binding["E1"]["receipt_file"] == expected["receipt"]["file"]


@pytest.mark.parametrize("damage", [
    "artifact", "receipt", "producer_version", "unknown_label", "false_receipt_identity",
])
def test_invalid_latest_canonical_evidence_fails_closed(client, damage):
    sid = new_session(client)["id"]
    service = client.app.state.service
    composition = None
    version = "0.4.8" if damage == "producer_version" else "0.4.9"
    if damage == "unknown_label":
        composition = {"state": "shadow", "records": rows()}
        composition["records"][0]["label"] = "L1:PRIVATE_UNKNOWN_LABEL"
        composition["records"][3]["label"] = "L1:PRIVATE_UNKNOWN_LABEL"
    tool_id = "P0-03" if damage == "false_receipt_identity" else "P0-02"
    registered = register_profile(service, sid, composition=composition, version=version, tool_id=tool_id)
    state = service.load(sid)
    if damage == "artifact":
        write_file(registered["artifact_path"], b'{"tampered":true}')
    elif damage == "receipt":
        write_file(registered["receipt_path"], b'{"tampered":true}')
    elif damage == "false_receipt_identity":
        state["_tool_runs"][-1]["tool_id"] = "P0-02"
        state["_input_objects"][registered["input_id"]]["producer_tool_id"] = "P0-02"
        service.save(state)

    summary, binding = build_result_context(service.inputs, service.load(sid))

    assert summary == {"state": "unavailable", "reason_code": "result_evidence_invalid"}
    assert binding == {}
    assert all(secret not in json.dumps(summary) for secret in SECRETS)


def test_non_shadow_composition_preserves_declared_unavailable_state(client):
    sid = new_session(client)["id"]
    service = client.app.state.service
    register_profile(service, sid, composition={"state": "unavailable", "records": []})

    summary, _ = build_result_context(service.inputs, service.load(sid))

    assert summary["state"] == "available"
    assert summary["composition_state"] == "unavailable"
    assert summary["composition"] == []
    assert summary["reconciliation"] == []


def test_large_source_specific_provenance_does_not_consume_shared_row_limit(client):
    sid = new_session(client)["id"]
    service = client.app.state.service
    composition = {"state": "shadow", "records": rows() + [
        {"view": "source_specific", "source_id": f"PRIVATE_SOURCE_{index}", "label": LABEL,
         "label_level": "L1", "state_evidence_state": "candidate",
         "denominator_scope": "selected_data_view", "count": 1, "fraction": 0.1, "denominator": 10}
        for index in range(125)]}
    registered = register_profile(service, sid, composition=composition)

    summary, binding = build_result_context(service.inputs, service.load(sid))

    assert summary["state"] == "available"
    assert len(summary["composition"]) + len(summary["reconciliation"]) == 3
    assert binding["E1"]["artifact_id"] == registered["artifact"].artifact_id


def test_projected_result_row_limit_fails_closed_without_truncation(
    client, monkeypatch
):
    sid = new_session(client)["id"]
    service = client.app.state.service
    register_profile(service, sid)
    monkeypatch.setattr("bridge.web.evidence.MAX_ROWS", 2)

    summary, binding = build_result_context(service.inputs, service.load(sid))

    assert summary == {"state": "unavailable", "reason_code": "result_summary_limit"}
    assert binding == {}


def test_result_encoded_byte_limit_fails_closed_without_truncation(client):
    sid = new_session(client)["id"]
    service = client.app.state.service
    old_limit = sys.get_int_max_str_digits()
    try:
        sys.set_int_max_str_digits(0)
        n = 10 ** 9000
        common = {"label_level": "L1", "denominator_scope": "selected_data_view",
                  "count": n, "fraction": 1.0, "denominator": n}
        composition = {"state": "shadow", "records": [
            {**common, "view": "source_specific", "source_id": "PRIVATE_SOURCE_SENTINEL",
             "label": LABEL, "state_evidence_state": "candidate"},
            {**common, "view": "reconciliation_state", "source_id": None,
             "label": "consensus_supported", "state_evidence_state": "candidate"},
            {**common, "view": "consensus_supported_only", "source_id": None,
             "label": LABEL, "state_evidence_state": "candidate"}]}
        register_profile(service, sid, composition=composition, n=n)
        summary, binding = build_result_context(service.inputs, service.load(sid))
    finally:
        sys.set_int_max_str_digits(old_limit)

    assert summary == {"state": "unavailable", "reason_code": "result_summary_limit"}
    assert binding == {}

def capture_transport(monkeypatch, captured):
    original = httpx.Client
    def respond(request):
        payload = json.loads(request.content)
        captured.append(payload)
        text = ("E1: 8 of 10 observations are consensus-supported."
                if len(captured) == 1 else "No result evidence supplied.")
        return httpx.Response(200, json={"choices": [{"message": {
            "content": json.dumps({"action": "reply", "text": text})}}]})
    monkeypatch.setattr("bridge.web.provider.httpx.Client",
        lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs))


def test_qc_only_service_turn_shares_canonical_aggregate_e0(
    client, tmp_path, monkeypatch
):
    sid = new_session(client)["id"]
    url = f"/api/sessions/{sid}"
    upload_id = client.post(
        url + "/uploads",
        files={"file": ("synthetic.h5ad", h5ad(tmp_path))},
    ).json()["uploads"][0]["id"]
    declare_counts(client, sid, upload_id)
    client.post(url + "/messages", json={
        "text": "scRNA-seq, use X raw counts for QC",
    })
    plan = settle(client, sid)["plan"]
    client.post(url + "/approve", json={
        "plan_id": plan["id"], "plan_digest": plan["digest"],
    })
    assert settle(client, sid)["plan"]["status"] == "completed"

    service = client.app.state.service
    service.settings = replace(service.settings, share_result_summaries=True)
    captured = []
    capture_transport(monkeypatch, captured)
    client.post(url + "/messages", json={
        "text": "Explain the completed QC evidence without preparing a new plan.",
    })
    settle(client, sid)

    context = json.loads(
        captured[0]["messages"][0]["content"].split(
            "Safe execution context: ", 1
        )[1]
    )
    summary = context["result_summary"]
    assert context["results_sent_to_model"] is True
    assert summary["state"] == "available"
    assert summary["evidence_ref"] == "E0"
    assert summary["tool_id"] == "P0-01"
    assert summary["execution_state"] == "succeeded"
    assert summary["schema_integrity"] == {
        "n_observations": 4,
        "observation_kind": "cells",
        "n_genes": 3,
        "unique_cell_ids": True,
        "unique_gene_ids": True,
    }
    assert [row["metric_name"] for row in summary["metrics"]] == [
        "total_counts_median",
        "detected_genes_median",
        "mitochondrial_fraction_median",
        "ribosomal_fraction_median",
        "top_20_gene_fraction_median",
    ]
    assert summary["metrics"][0] == {
        "metric_name": "total_counts_median",
        "raw_value": 3.5,
        "denominator": 4,
        "evidence_state": "measured",
        "score_state": "unavailable",
        "domain_score": None,
    }
    assert summary["selected_data_view"] == {
        "view_kind": "all_observations",
        "n_observations": 4,
    }
    state = service.load(sid)
    latest_user = next(
        item for item in reversed(state["messages"]) if item["role"] == "user"
    )
    binding = state["_result_contexts"][latest_user["id"]]["private_binding"]
    assert set(binding) == {"E0"}
    assert binding["E0"]["receipt_file"] == state["_tool_runs"][-1]["file"]
    outbound = json.dumps(captured[0])
    assert all(value not in outbound for value in binding["E0"].values())
    assert "private-cell-a" not in outbound
    assert all(secret not in outbound for secret in SECRETS)


def test_latest_qc_receipt_without_v2_does_not_fall_back(client):
    sid = new_session(client)["id"]
    service = client.app.state.service
    register_qc_profile(service, sid, run_id="run-qc-older")
    register(
        service,
        sid,
        {"unsupported": True},
        run_id="run-qc-latest",
        tool_id="P0-01",
    )

    assert build_result_context(service.inputs, service.load(sid)) == (
        {"state": "not_available"},
        {},
    )


@pytest.mark.parametrize("damage", [
    "artifact",
    "receipt",
    "producer",
    "profile_binding",
    "artifact_identity",
    "execution_identity",
])
def test_invalid_latest_qc_canonical_evidence_fails_closed(client, damage):
    sid = new_session(client)["id"]
    service = client.app.state.service
    payload = (
        qc_profile("different-run")
        if damage == "profile_binding"
        else qc_profile("run-qc-damaged")
    )
    registered = register_qc_profile(
        service, sid, run_id="run-qc-damaged", payload=payload
    )
    state = service.load(sid)
    record = state["_input_objects"][registered["input_id"]]
    if damage == "artifact":
        write_file(registered["artifact_path"], b'{"tampered":true}')
    elif damage == "receipt":
        write_file(registered["receipt_path"], b'{"tampered":true}')
    elif damage == "producer":
        record["producer_tool_id"] = "P0-02"
        service.save(state)
    elif damage == "artifact_identity":
        record["artifact_id"] = "artifact:PRIVATE_FALSE_ID"
        service.save(state)
    elif damage == "execution_identity":
        state["_tool_runs"][-1]["state"] = "partial"
        service.save(state)

    summary, binding = build_result_context(service.inputs, service.load(sid))

    assert summary == {
        "state": "unavailable",
        "reason_code": "result_evidence_invalid",
    }
    assert binding == {}


@pytest.mark.parametrize("damage", [
    "duplicate_metric",
    "nonnumeric_metric",
    "unavailable_with_value",
    "schema_scalar",
    "assay",
    "count_metrics_state",
    "assessment_state",
])
def test_invalid_qc_projection_values_fail_closed(client, damage):
    sid = new_session(client)["id"]
    service = client.app.state.service
    run_id = "run-qc-invalid-value"
    payload = qc_profile(run_id)
    measurements = [qc_measurement(
        run_id, "total_counts_median", 3.5
    )]
    if damage == "duplicate_metric":
        measurements.append(qc_measurement(
            run_id, "total_counts_median", 4.0
        ))
    elif damage == "nonnumeric_metric":
        measurements = [qc_measurement(
            run_id, "total_counts_median", "PRIVATE_NUMERIC_SENTINEL"
        )]
    elif damage == "unavailable_with_value":
        measurements = [qc_measurement(
            run_id,
            "total_counts_median",
            3.5,
            evidence_state="unavailable",
        )]
    elif damage == "schema_scalar":
        payload["schema_integrity"]["n_observations"] = "4"
    elif damage == "assay":
        payload["assay"] = "PRIVATE_ASSAY_SENTINEL"
    elif damage == "count_metrics_state":
        payload["cell_qc"]["count_metrics_state"] = "PRIVATE_STATE_SENTINEL"
    elif damage == "assessment_state":
        payload["ambient_assessment"]["state"] = "PRIVATE_STATE_SENTINEL"
    register_qc_profile(
        service,
        sid,
        run_id=run_id,
        payload=payload,
        measurements=measurements,
    )

    summary, binding = build_result_context(service.inputs, service.load(sid))

    assert summary == {
        "state": "unavailable",
        "reason_code": "result_evidence_invalid",
    }
    assert binding == {}


def test_qc_projection_does_not_broadly_verify_other_run_artifacts(
    client, monkeypatch
):
    sid = new_session(client)["id"]
    service = client.app.state.service
    registered = register_qc_profile(service, sid)
    monkeypatch.setattr(
        service.inputs,
        "verify",
        lambda *args: pytest.fail("broad input verification used"),
    )
    monkeypatch.setattr(
        service.inputs,
        "receipt_artifacts",
        lambda *args: pytest.fail("all receipt artifacts were read"),
    )

    summary, binding = build_result_context(service.inputs, service.load(sid))

    assert summary["evidence_ref"] == "E0"
    assert binding["E0"]["artifact_id"] == registered["artifact"].artifact_id


def test_e1_preserves_fields_and_adds_independent_qc_summary(client):
    sid = new_session(client)["id"]
    service = client.app.state.service
    qc = register_qc_profile(service, sid, run_id="run-independent-qc")
    cell = register_profile(service, sid, run_id="run-independent-cell-state")

    summary, binding = build_result_context(service.inputs, service.load(sid))

    assert summary["evidence_ref"] == "E1"
    assert summary["n_observations"] == 10
    assert summary["qc_summary"]["evidence_ref"] == "E0"
    assert summary["qc_summary"]["schema_integrity"]["n_observations"] == 4
    assert binding["E0"]["receipt_file"] == qc["receipt"]["file"]
    assert binding["E1"]["receipt_file"] == cell["receipt"]["file"]


def test_available_e0_reports_actual_missing_e1_state_without_relabeling(client):
    sid = new_session(client)["id"]
    service = client.app.state.service
    register_qc_profile(service, sid)
    register(
        service,
        sid,
        {"unsupported": True},
        run_id="run-p002-without-v3",
        tool_id="P0-02",
    )

    summary, binding = build_result_context(service.inputs, service.load(sid))

    assert summary["evidence_ref"] == "E0"
    assert summary["cell_state_summary"] == {"state": "not_available"}
    assert set(binding) == {"E0"}


def test_combined_e0_e1_summary_limit_fails_closed(client, monkeypatch):
    sid = new_session(client)["id"]
    service = client.app.state.service
    register_qc_profile(service, sid)
    register_profile(service, sid)
    monkeypatch.setattr("bridge.web.evidence.MAX_SUMMARY_BYTES", 1600)

    summary, binding = build_result_context(service.inputs, service.load(sid))

    assert summary == {
        "state": "unavailable",
        "reason_code": "result_summary_limit",
    }
    assert binding == {}


def test_unexpected_reconciliation_label_sends_no_evidence(
    client, monkeypatch
):
    sid = new_session(client)["id"]
    service = client.app.state.service
    composition = {"state": "shadow", "records": rows()}
    composition["records"][2]["label"] = "unexpected_state"
    register_profile(service, sid, composition=composition)
    service.settings = replace(service.settings, share_result_summaries=True)
    captured = []
    capture_transport(monkeypatch, captured)

    client.post(
        f"/api/sessions/{sid}/messages",
        json={"text": "Interpret only valid evidence."},
    )
    settle(client, sid)

    context = json.loads(
        captured[0]["messages"][0]["content"].split(
            "Safe execution context: ", 1
        )[1]
    )
    assert context["results_sent_to_model"] is False
    assert context["result_summary"] == {
        "state": "unavailable",
        "reason_code": "result_evidence_invalid",
    }
    assert "evidence_ref" not in context["result_summary"]
    assert "composition" not in context["result_summary"]
    assert all(secret not in json.dumps(captured[0]) for secret in SECRETS)


@pytest.mark.parametrize("suppression", ["disabled", "input_review"])
def test_service_sends_opt_in_summary_but_suppresses_prior_result_reply_history(
    client, monkeypatch, suppression
):
    sid = new_session(client)["id"]
    service = client.app.state.service
    registered = register_profile(service, sid)
    service.settings = replace(service.settings, share_result_summaries=True)
    captured = []
    capture_transport(monkeypatch, captured)

    client.post(f"/api/sessions/{sid}/messages",
                json={"text": "Interpret the selected-view evidence."})
    first_public = settle(client, sid)
    first_state = service.load(sid)
    first_user = [item for item in first_state["messages"] if item["role"] == "user"][-1]
    first_assistant = first_state["messages"][-1]
    first_context = json.loads(
        captured[0]["messages"][0]["content"].split("Safe execution context: ", 1)[1])
    assert first_context["results_sent_to_model"] is True
    assert first_context["result_summary"]["n_observations"] == 10
    assert first_context["result_summary"]["composition"][0]["count"] == 8
    outbound = json.dumps(captured[0])
    private_values = [registered["input_id"], registered["receipt"]["file"],
        registered["receipt"]["sha256"], registered["artifact"].artifact_id,
        registered["artifact"].sha256, *SECRETS]
    assert all(value not in outbound for value in private_values)
    audit = first_state["_result_contexts"][first_user["id"]]
    assert audit["result_summary"] == first_context["result_summary"]
    assert audit["private_binding"]["E1"]["artifact_id"] == registered["artifact"].artifact_id
    assert audit["assistant_message_id"] == first_assistant["id"]
    assert "_result_contexts" not in first_public

    reloaded = create_app(service.settings).state.service
    try:
        assert reloaded.load(sid)["_result_contexts"] == first_state["_result_contexts"]
    finally:
        reloaded.pool.shutdown()

    if suppression == "disabled":
        service.settings = replace(service.settings, share_result_summaries=False)
    else:
        state = service.load(sid)
        service.controls.review(state)
        service.save(state)
    client.post(f"/api/sessions/{sid}/messages",
                json={"text": "Continue without sharing results."})
    final_public = settle(client, sid)

    second_context = json.loads(
        captured[1]["messages"][0]["content"].split("Safe execution context: ", 1)[1])
    assert second_context["results_sent_to_model"] is False
    assert "result_summary" not in second_context
    second_history = captured[1]["messages"][1:]
    assert {"role": "user", "content": first_user["content"]} in second_history
    assert all(item.get("content") != first_assistant["content"] for item in second_history)
    assert any(item["content"] == first_assistant["content"]
               for item in service.load(sid)["messages"])
    assert first_assistant["content"] in json.dumps(final_public)


def test_private_result_context_retention_is_bounded(client, monkeypatch):
    sid = new_session(client)["id"]
    service = client.app.state.service
    register_profile(service, sid)
    state = service.load(sid)
    state["_result_contexts"] = {
        f"old-{index}": {"result_summary": {"state": "not_available"},
                         "private_binding": {}}
        for index in range(24)
    }
    service.save(state)
    service.settings = replace(service.settings, share_result_summaries=True)
    captured = []
    capture_transport(monkeypatch, captured)

    client.post(f"/api/sessions/{sid}/messages", json={"text": "New bounded turn."})
    settle(client, sid)

    current = service.load(sid)
    latest_user_id = [item["id"] for item in current["messages"]
                      if item["role"] == "user"][-1]
    assert len(current["_result_contexts"]) == 24
    assert "old-0" not in current["_result_contexts"]
    assert latest_user_id in current["_result_contexts"]


def settings(tmp_path, **updates):
    values = dict(storage_root=tmp_path / "private", token="t" * 32,
        model_base_url="https://provider.invalid/v1", model="test-model",
        model_api_key="private-key", origin="http://testserver")
    values.update(updates)
    return Settings(**values)


def test_settings_default_off_and_reject_non_boolean(tmp_path):
    assert settings(tmp_path).share_result_summaries is False
    with pytest.raises(ValueError, match="invalid_server_configuration"):
        settings(tmp_path, share_result_summaries="1")


@pytest.mark.parametrize(("configured", "expected"),
                         [(None, False), ("0", False), ("1", True)])
def test_main_accepts_only_exact_share_result_summary_startup_values(
    tmp_path, monkeypatch, configured, expected
):
    from bridge.web import __main__ as web_main
    environment = {
        "BRIDGE_WEB_STORAGE": str(tmp_path / "startup-private"),
        "BRIDGE_WEB_TOKEN": "t" * 32,
        "BRIDGE_WEB_MODEL_BASE_URL": "https://provider.invalid/v1",
        "BRIDGE_WEB_MODEL": "test-model",
        "BRIDGE_WEB_MODEL_API_KEY": "private-key",
        "BRIDGE_WEB_ORIGIN": "http://127.0.0.1:8765"}
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("BRIDGE_WEB_TRUSTED_ANCESTORS", raising=False)
    if configured is None:
        monkeypatch.delenv("BRIDGE_WEB_SHARE_RESULT_SUMMARIES", raising=False)
    else:
        monkeypatch.setenv("BRIDGE_WEB_SHARE_RESULT_SUMMARIES", configured)
    captured = {}
    monkeypatch.setattr(web_main.uvicorn, "run",
                        lambda app, **kwargs: captured.update(app=app))

    web_main.main()

    service = captured["app"].state.service
    try:
        assert service.settings.share_result_summaries is expected
    finally:
        service.pool.shutdown()


def test_main_rejects_ambiguous_share_result_summary_startup_value(
    tmp_path, monkeypatch
):
    from bridge.web import __main__ as web_main
    environment = {
        "BRIDGE_WEB_STORAGE": str(tmp_path / "startup-private"),
        "BRIDGE_WEB_TOKEN": "t" * 32,
        "BRIDGE_WEB_MODEL_BASE_URL": "https://provider.invalid/v1",
        "BRIDGE_WEB_MODEL": "test-model",
        "BRIDGE_WEB_MODEL_API_KEY": "private-key",
        "BRIDGE_WEB_SHARE_RESULT_SUMMARIES": "true"}
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("BRIDGE_WEB_TRUSTED_ANCESTORS", raising=False)
    monkeypatch.setattr(web_main.uvicorn, "run",
        lambda *args, **kwargs: pytest.fail("server started"))

    with pytest.raises(ValueError, match="invalid_server_configuration"):
        web_main.main()
