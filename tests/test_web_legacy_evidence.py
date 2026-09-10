"""Canonical legacy summaries preserve their producer's actual denominator."""
from __future__ import annotations
import json

import pytest

from bridge.toolkit.contracts import InputAsset
from bridge.web.evidence import build_result_context
from test_web_service import client, declare_counts
from test_web_intake import uploaded
from test_web_evidence import register


def legacy_case(client, tmp_path):
    sid, aid = uploaded(client, tmp_path)
    declare_counts(client, sid, aid, location="X")
    service = client.app.state.service
    state = service.load(sid)
    asset = InputAsset(asset_id=aid, path=service.directory(sid) / "uploads" / (aid + ".h5ad"),
        checksum=state["_uploads"][aid]["sha256"], format="h5ad", assay="scRNA-seq",
        matrix_location="X", matrix_semantics="raw_counts", input_level="count_ready")
    common = {"label_level": "L1", "denominator_view": "all input observations", "denominator": 4}
    payload = {
        "profile_id": "cell-state-profile:run-legacy", "assay": "scRNA-seq",
        "measurement_spec_id": "PRIVATE_SPEC", "measurement_spec_status": "candidate",
        "annotation_vocabulary_ref": "PRIVATE_VOCAB", "reference_snapshot_ref": "PRIVATE_REF",
        "n_observations": 4, "n_genes": 3,
        "denominator": "all observations in the declared post-QC input view",
        "label_levels": {"L1": {"state": "shadow", "n_observations": 4},
                         "L2": {"state": "shadow", "n_observations": 3}},
        "source_support": {"private": "PRIVATE_SOURCE"}, "marker_program_evidence": {},
        "prediction_sets": {"open_set_state": "not_assessed"},
        "composition": {"state": "shadow", "records": [
            {**common, "view": "source_specific", "source_id": "PRIVATE_SOURCE",
             "label": "L1:Neuron_DA", "count": 4, "fraction": 1.0},
            {**common, "view": "consensus_supported_only", "source_id": None,
             "label": "L1:Neuron_DA", "count": 3, "fraction": 0.75},
            {**common, "view": "reconciliation_state", "source_id": None,
             "label": "consensus_supported", "count": 3, "fraction": 0.75},
            {**common, "view": "reconciliation_state", "source_id": None,
             "label": "source_conflict", "count": 1, "fraction": 0.25},
            {"label_level": "L2", "denominator_view": "L2-eligible observations", "denominator": 3,
             "view": "reconciliation_state", "source_id": None,
             "label": "single_source_supported", "count": 3, "fraction": 1.0},
        ]},
        "gene_coverage": {}, "modality_sensitivity": {}, "calibration": {"state": "not_assessed"},
        "warnings": ["PRIVATE_WARNING"], "score_state": "shadow", "domain_score": None,
    }
    record = register(service, sid, payload, run_id="run-legacy",
        schema_ref="bridge://schemas/cell-state-evidence-profile/v0.2", request_assets=[asset])
    return service, sid, record, payload


def test_real_registered_legacy_profile_is_available_without_v3_promotion(client, tmp_path):
    service, sid, record, _ = legacy_case(client, tmp_path)
    summary, binding = build_result_context(service.inputs, service.load(sid))
    assert summary["state"] == "available"
    assert summary["profile_schema_version"] == "0.2"
    assert summary["downstream_readiness"] == "not_established"
    assert summary["denominator_scope"] == "historical_tool_input"
    assert summary["n_observations"] == 4
    assert summary["composition"] == [{
        "label_level": "L1", "label": "L1:Neuron_DA", "count": 3, "fraction": 0.75,
        "denominator": 4, "denominator_scope": "all_input_observations", "state_evidence_state": "candidate",
    }]
    l2 = next(row for row in summary["reconciliation"] if row["label_level"] == "L2")
    assert l2["denominator"] == 3
    assert l2["denominator_scope"] == "l2_eligible_observations"
    assert summary["open_set_state"] == summary["calibration_state"] == "not_assessed"
    assert summary["domain_score"] is None and summary["score_state"] == "shadow"
    assert binding["E1"]["receipt_sha256"] == record["receipt"]["sha256"]
    assert "PRIVATE_" not in json.dumps(summary)
    assert "input_data_view" not in summary


@pytest.mark.parametrize("field,value", [
    ("profile_id", "cell-state-profile:another-run"),
    ("n_observations", 4.0),
    ("denominator", "PRIVATE_UNRECOGNIZED_SCOPE"),
])
def test_legacy_summary_rejects_unsupported_producer_or_shape(client, tmp_path, field, value):
    service, sid, _, payload = legacy_case(client, tmp_path)
    payload["profile_id"] = "cell-state-profile:run-malformed"
    payload[field] = value
    state = service.load(sid)
    asset = InputAsset.model_validate(json.loads(
        (service.directory(sid) / "receipts" / state["_tool_runs"][-1]["file"]).read_text())["request"]["assets"][0])
    register(service, sid, payload, run_id="run-malformed", request_assets=[asset],
             schema_ref="bridge://schemas/cell-state-evidence-profile/v0.2")
    summary, _ = build_result_context(service.inputs, service.load(sid))
    assert summary["state"] == "unavailable"
    assert summary["reason_code"] == "result_evidence_invalid"


def test_legacy_summary_rejects_changed_upload_without_rerunning_analysis(client, tmp_path):
    service, sid, record, _ = legacy_case(client, tmp_path)
    state = service.load(sid)
    aid = state["uploads"][0]["id"]
    (service.directory(sid) / "uploads" / (aid + ".h5ad")).write_bytes(b"modified")
    summary, binding = build_result_context(service.inputs, service.load(sid))
    assert summary["state"] == "unavailable"
    assert binding == {}
    assert service.load(sid)["_tool_runs"] == state["_tool_runs"]

@pytest.mark.parametrize("mutation", ["fraction", "partition", "label", "scope", "duplicate"])
def test_legacy_summary_rejects_invalid_composition(client, tmp_path, mutation):
    service, sid, _, payload = legacy_case(client, tmp_path)
    payload["profile_id"] = "cell-state-profile:run-invalid-composition"
    rows = payload["composition"]["records"]
    if mutation == "fraction":
        rows[1]["fraction"] = 0.5
    elif mutation == "partition":
        rows[3].update(count=0, fraction=0.0)
    elif mutation == "label":
        rows[1]["label"] = "L1:PRIVATE_UNKNOWN"
    elif mutation == "scope":
        rows[-1]["denominator_view"] = "all input observations"
    else:
        rows.append(dict(rows[1]))
    state = service.load(sid)
    asset = InputAsset.model_validate(json.loads(
        (service.directory(sid) / "receipts" / state["_tool_runs"][-1]["file"]).read_text())["request"]["assets"][0])
    register(service, sid, payload, run_id="run-invalid-composition", request_assets=[asset],
             schema_ref="bridge://schemas/cell-state-evidence-profile/v0.2")
    summary, binding = build_result_context(service.inputs, service.load(sid))
    assert summary["state"] == "unavailable" and binding == {}
    assert summary["reason_code"] == "result_evidence_invalid"


def test_invalid_registered_v3_does_not_fall_back_to_legacy(client, tmp_path):
    from test_web_evidence import register_profile
    service, sid, _, _ = legacy_case(client, tmp_path)
    current = register_profile(service, sid, run_id="run-invalid-v3")
    current["artifact_path"].write_bytes(b"changed")
    summary, binding = build_result_context(service.inputs, service.load(sid))
    assert summary["state"] == "unavailable" and binding == {}
