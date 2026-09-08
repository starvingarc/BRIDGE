"""Bounded public-safe evidence projection for the private Web conversation."""
from __future__ import annotations

import json
import math

from bridge.tool_packages._configurable_contracts import parse_composition
from bridge.tool_packages.p0_02_cell_state.reference import load_packaged_vocabulary
from bridge.toolkit.contracts import (
    CellStateCompositionView,
    CellStateEvidenceProfileV2,
    CellStateEvidenceProfileV3,
    QCReadinessProfileV2,
    ToolRun,
)

from .inputs import checked_bytes, strict_json

PROFILE_SCHEMA = "bridge://schemas/cell-state-evidence-profile/v0.3"
LEGACY_PROFILE_SCHEMA = "bridge://schemas/cell-state-evidence-profile/v0.2"
QC_PROFILE_SCHEMA = "bridge://schemas/qc-readiness-profile/v0.2"
MAX_ROWS = 128
MAX_SUMMARY_BYTES = 32 * 1024
QC_METRICS = {
    "total_counts_median",
    "detected_genes_median",
    "mitochondrial_fraction_median",
    "ribosomal_fraction_median",
    "top_20_gene_fraction_median",
}
QC_ASSAYS = {"scRNA-seq", "snRNA-seq"}
QC_INPUT_LEVELS = {"analysis_ready", "count_ready", "droplet_ready"}
QC_OBSERVATION_KINDS = {"cells", "nuclei", "barcodes"}
QC_COUNT_METRICS_STATES = {"measured", "not_assessed"}
QC_ASSESSMENT_STATES = {
    "not_assessed",
    "candidate",
    "unavailable",
    "not_implemented",
}
QC_ASSESSMENTS = (
    "upstream_library_qc",
    "doublet_assessment",
    "cell_calling_assessment",
    "ambient_assessment",
)
# The producer currently has no exported reconciliation enum. Keep its fail-closed
# fixed mapping aligned with composition_records_v3.
RECONCILIATION_STATES = {
    "consensus_supported": "candidate",
    "single_source_supported": "candidate",
    "source_conflict": "unresolved",
    "unavailable": "unavailable",
    "unknown": "unknown",
    "ood": "ood",
}


class _SummaryLimit(ValueError):
    pass


def _value(value):
    return value.value if hasattr(value, "value") else value


def _row(record):
    return {
        "label_level": record.label_level,
        "label": record.label,
        "count": record.count,
        "fraction": record.fraction,
        "denominator": record.denominator,
        "state_evidence_state": _value(record.state_evidence_state),
    }


def _latest_receipt(state, tool_id="P0-02"):
    return next(
        (
            receipt
            for receipt in reversed(state.get("_tool_runs", []))
            if receipt.get("tool_id") == tool_id
            and receipt.get("state") in {"succeeded", "partial"}
        ),
        None,
    )


def _registered_profile(state, receipt, schema=PROFILE_SCHEMA):
    candidates = []
    for input_id, record in state.get("_input_objects", {}).items():
        if (
            record.get("source") == "tool_output"
            and record.get("schema_ref") == schema
            and record.get("receipt_file") == receipt.get("file")
            and record.get("receipt_sha256") == receipt.get("sha256")
        ):
            candidates.append((input_id, record))
    if not candidates:
        return None
    # Registration order is stable. Repeated registration of the same artifact
    # cannot manufacture another vote or change which canonical artifact is used.
    deduplicated = {}
    for input_id, record in candidates:
        deduplicated[record.get("sha256")] = (input_id, record)
    return next(reversed(deduplicated.values()))


def _verified_receipt(inputs, state, receipt):
    root = inputs.service.directory(state["id"])
    raw = checked_bytes(
        inputs.service,
        state,
        root / "receipts" / receipt["file"],
        receipt["sha256"],
    )
    return strict_json(raw, 128 * 1024 * 1024)


def _project(inputs, state, receipt, input_id, record):
    if record.get("producer_tool_id") != "P0-02":
        raise ValueError("canonical_source_producer_mismatch")
    payload = inputs.verify(state, record)
    run = _verified_receipt(inputs, state, receipt)
    if (
        run["request"]["tool_id"] != "P0-02"
        or run["execution_state"] != receipt["state"]
        or run["execution_state"] not in {"succeeded", "partial"}
    ):
        raise ValueError("canonical_receipt_invalid")

    profile = CellStateEvidenceProfileV3.model_validate(payload)
    if (
        profile.producer_run_ref != run["run_id"]
        or profile.producer_tool_version != run["tool_version"]
        or profile.producer_tool_id != "P0-02"
        or type(profile.n_observations) is not int
        or profile.n_observations <= 0
    ):
        raise ValueError("profile_producer_binding_invalid")

    records = profile.composition.records
    vocabulary = load_packaged_vocabulary()
    labels = {(item.level, item.state_id) for item in vocabulary.labels}
    composition = []
    reconciliation = []
    for item in records:
        if item.view is CellStateCompositionView.CONSENSUS_SUPPORTED_ONLY:
            if (item.label_level, item.label) not in labels:
                raise ValueError("unknown_annotation_label")
            composition.append(_row(item))
        elif item.view is CellStateCompositionView.RECONCILIATION_STATE:
            expected = RECONCILIATION_STATES.get(item.label)
            if expected is None or _value(item.state_evidence_state) != expected:
                raise ValueError("unknown_reconciliation_state")
            reconciliation.append(_row(item))

    if len(composition) + len(reconciliation) > MAX_ROWS:
        raise _SummaryLimit()

    summary = {
        "state": "available",
        "evidence_ref": "E1",
        "tool_id": "P0-02",
        "execution_state": run["execution_state"],
        "n_observations": profile.n_observations,
        "denominator_scope": profile.denominator,
        "composition_state": profile.composition.state,
        "open_set_state": profile.open_set_state,
        "calibration_state": profile.calibration_state,
        "score_state": _value(profile.score_state),
        "domain_score": None,
        "composition": composition,
        "reconciliation": reconciliation,
    }
    _check_summary_limit(summary)

    binding = {
        "E1": {
            "input_id": input_id,
            "receipt_file": record["receipt_file"],
            "receipt_sha256": record["receipt_sha256"],
            "artifact_id": record["artifact_id"],
            "artifact_sha256": record["sha256"],
        }
    }
    return summary, binding


def _project_legacy(inputs, state, receipt, input_id, record):
    """Interpret the historical V2 denominator; never create V3 lineage."""
    if record.get("producer_tool_id") != "P0-02":
        raise ValueError("canonical_source_producer_mismatch")
    payload = inputs.verify(state, record)
    run = ToolRun.model_validate(_verified_receipt(inputs, state, receipt))
    profile = CellStateEvidenceProfileV2.model_validate(payload)
    if (
        run.request.tool_id != "P0-02"
        or _value(run.execution_state) != receipt["state"]
        or run.request.tool_version != run.tool_version
        or profile.profile_id != f"cell-state-profile:{run.run_id}"
        or type(payload["n_observations"]) is not int
        or profile.n_observations <= 0
        or profile.assay not in QC_ASSAYS
        or profile.denominator != "all observations in the declared post-QC input view"
        or len(run.request.assets) != 1
    ):
        raise ValueError("legacy_profile_binding_invalid")
    asset = run.request.assets[0]
    upload = state["_uploads"].get(asset.asset_id)
    expected_path = inputs.service.directory(state["id"]) / "uploads" / (asset.asset_id + ".h5ad")
    if (
        upload is None or asset.path != expected_path
        or asset.checksum != upload["sha256"] or asset.assay != profile.assay
    ):
        raise ValueError("legacy_upload_binding_invalid")
    checked_bytes(inputs.service, state, asset.path, asset.checksum,
                  limit=inputs.service.settings.upload_limit)

    composition_state = profile.composition.get("state")
    if composition_state not in {"shadow", "not_assessed", "unavailable", "unknown", "missing"}:
        raise ValueError("legacy_composition_state_invalid")
    records = parse_composition(profile)
    if composition_state != "shadow" and records:
        raise ValueError("legacy_composition_state_invalid")
    vocabulary = load_packaged_vocabulary()
    labels = {(item.level, item.state_id) for item in vocabulary.labels}
    scopes = {"L1": ("all input observations", "all_input_observations"),
              "L2": ("L2-eligible observations", "l2_eligible_observations")}
    composition, reconciliation = [], []
    grouped = {}
    for item in records:
        if item.label_level not in scopes:
            raise ValueError("legacy_denominator_invalid")
        original_scope, scope = scopes[item.label_level]
        level_count = profile.label_levels[item.label_level]["n_observations"]
        if (
            type(level_count) is not int or level_count <= 0
            or level_count > profile.n_observations or item.denominator != level_count
            or item.denominator_view != original_scope
            or item.label_level == "L1" and level_count != profile.n_observations
        ):
            raise ValueError("legacy_denominator_invalid")
        view = _value(item.view)
        grouped.setdefault(item.label_level, {}).setdefault((view, item.source_id), []).append(item)
        if view == "reconciliation_state":
            evidence_state = RECONCILIATION_STATES.get(item.label)
            if evidence_state is None:
                raise ValueError("unknown_reconciliation_state")
        else:
            if (item.label_level, item.label) not in labels:
                raise ValueError("unknown_annotation_label")
            evidence_state = "candidate"
        if view == "source_specific":
            continue
        row = {"label_level": item.label_level, "label": item.label,
               "count": item.count, "fraction": item.fraction, "denominator": item.denominator,
               "denominator_scope": scope, "state_evidence_state": evidence_state}
        (reconciliation if view == "reconciliation_state" else composition).append(row)
    for groups in grouped.values():
        reconciled = groups.get(("reconciliation_state", None), [])
        denominator = next(iter(groups.values()))[0].denominator
        if not reconciled or sum(item.count for item in reconciled) != denominator:
            raise ValueError("legacy_reconciliation_partition_invalid")
        if any(sum(item.count for item in rows) > denominator for rows in groups.values()):
            raise ValueError("legacy_composition_partition_invalid")
        consensus = groups.get(("consensus_supported_only", None), [])
        if sum(item.count for item in consensus) != sum(
            item.count for item in reconciled if item.label == "consensus_supported"
        ):
            raise ValueError("legacy_consensus_partition_invalid")
    if len(composition) + len(reconciliation) > MAX_ROWS:
        raise _SummaryLimit()
    open_set = profile.prediction_sets.get("open_set_state")
    calibration = profile.calibration.get("state")
    if open_set not in {"not_assessed", "candidate", "calibrated"} or calibration not in {
        "not_assessed", "candidate", "calibrated"
    }:
        raise ValueError("legacy_assessment_state_invalid")
    summary = {
        "state": "available", "evidence_ref": "E1", "tool_id": "P0-02",
        "execution_state": _value(run.execution_state), "profile_schema_version": "0.2",
        "downstream_readiness": "not_established", "n_observations": profile.n_observations,
        "denominator_scope": "historical_tool_input", "composition_state": composition_state,
        "open_set_state": open_set, "calibration_state": calibration,
        "score_state": _value(profile.score_state), "domain_score": None,
        "composition": composition, "reconciliation": reconciliation,
    }
    _check_summary_limit(summary)
    return summary, {"E1": {
        "input_id": input_id, "receipt_file": record["receipt_file"],
        "receipt_sha256": record["receipt_sha256"], "artifact_id": record["artifact_id"],
        "artifact_sha256": record["sha256"],
    }}


def _check_summary_limit(summary):
    encoded = json.dumps(
        summary,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode()
    if len(encoded) > MAX_SUMMARY_BYTES:
        raise _SummaryLimit()


def _exact_nonnegative_int(value):
    if type(value) is not int or value < 0:
        raise ValueError("qc_scalar_invalid")
    return value


def _exact_bool(value):
    if type(value) is not bool:
        raise ValueError("qc_scalar_invalid")
    return value


def _finite_number_or_none(value):
    if value is None:
        return None
    if type(value) not in {int, float} or isinstance(value, float) and not math.isfinite(value):
        raise ValueError("qc_metric_invalid")
    return value


def _verified_qc_profile(inputs, state, receipt, record):
    if (
        record.get("producer_tool_id") != "P0-01"
        or record.get("object_version") != "0.2.0"
    ):
        raise ValueError("canonical_source_producer_mismatch")
    run_payload = _verified_receipt(inputs, state, receipt)
    run = ToolRun.model_validate(run_payload)
    if (
        run.request.tool_id != "P0-01"
        or _value(run.execution_state) != receipt["state"]
        or _value(run.execution_state) not in {"succeeded", "partial"}
        or run.request.tool_version != run.tool_version
    ):
        raise ValueError("canonical_receipt_invalid")

    artifacts = [
        artifact
        for artifact in run_payload["artifacts"]
        if artifact.get("artifact_id") == record.get("artifact_id")
    ]
    if len(artifacts) != 1:
        raise ValueError("canonical_artifact_mismatch")
    artifact = artifacts[0]
    if (
        artifact.get("kind") != "qc_profile_v2"
        or artifact.get("media_type") != "application/json"
        or artifact.get("path") != record.get("path")
        or artifact.get("sha256") != record.get("sha256")
    ):
        raise ValueError("canonical_artifact_mismatch")

    root = inputs.service.directory(state["id"])
    raw = checked_bytes(
        inputs.service,
        state,
        artifact["path"],
        artifact["sha256"],
        root=root / "runs",
    )
    profile_payload = strict_json(raw)
    profile = QCReadinessProfileV2.model_validate(profile_payload)
    if profile.profile_id != f"qc-profile:{run.run_id}":
        raise ValueError("profile_producer_binding_invalid")
    return run_payload, run, profile_payload, profile


def _project_qc(inputs, state, receipt, input_id, record):
    run_payload, run, payload, profile = _verified_qc_profile(
        inputs, state, receipt, record
    )
    assay = payload.get("assay")
    input_level = payload.get("input_level")
    if assay not in QC_ASSAYS or input_level not in QC_INPUT_LEVELS:
        raise ValueError("qc_profile_value_invalid")

    integrity = payload.get("schema_integrity")
    if not isinstance(integrity, dict):
        raise ValueError("qc_schema_integrity_invalid")
    observation_kind = integrity.get("observation_kind")
    if observation_kind not in QC_OBSERVATION_KINDS:
        raise ValueError("qc_schema_integrity_invalid")
    schema_integrity = {
        "n_observations": _exact_nonnegative_int(integrity.get("n_observations")),
        "observation_kind": observation_kind,
        "n_genes": _exact_nonnegative_int(integrity.get("n_genes")),
        "unique_cell_ids": _exact_bool(integrity.get("unique_cell_ids")),
        "unique_gene_ids": _exact_bool(integrity.get("unique_gene_ids")),
    }

    cell_qc = payload.get("cell_qc")
    if not isinstance(cell_qc, dict):
        raise ValueError("qc_count_metrics_state_invalid")
    count_metrics_state = cell_qc.get("count_metrics_state")
    if count_metrics_state not in QC_COUNT_METRICS_STATES:
        raise ValueError("qc_count_metrics_state_invalid")

    raw_measurements = run_payload.get("measurements")
    if not isinstance(raw_measurements, list) or len(raw_measurements) != len(run.measurements):
        raise ValueError("qc_measurements_invalid")
    metrics = []
    seen = set()
    for raw_metric, metric in zip(raw_measurements, run.measurements, strict=True):
        if not isinstance(raw_metric, dict):
            raise ValueError("qc_measurements_invalid")
        name = raw_metric.get("metric_name")
        if name not in QC_METRICS:
            continue
        if name in seen:
            raise ValueError("duplicate_qc_metric")
        seen.add(name)
        raw_value = _finite_number_or_none(raw_metric.get("raw_value"))
        denominator = _finite_number_or_none(raw_metric.get("denominator"))
        evidence_state = _value(metric.evidence_state)
        if evidence_state in {"missing", "unavailable"} and (
            raw_value is not None or denominator is not None
        ):
            raise ValueError("qc_metric_state_invalid")
        metrics.append({
            "metric_name": name,
            "raw_value": raw_value,
            "denominator": denominator,
            "evidence_state": evidence_state,
            "score_state": _value(metric.score_state),
            "domain_score": metric.domain_score,
        })

    assessment_states = {}
    for field in QC_ASSESSMENTS:
        assessment = payload.get(field)
        if not isinstance(assessment, dict):
            raise ValueError("qc_assessment_invalid")
        state_value = assessment.get("state")
        if state_value not in QC_ASSESSMENT_STATES:
            raise ValueError("qc_assessment_invalid")
        assessment_states[field] = state_value

    raw_view = payload.get("selected_data_view")
    selected_data_view = None
    if raw_view is not None:
        if not isinstance(raw_view, dict):
            raise ValueError("qc_data_view_invalid")
        view_kind = raw_view.get("view_kind")
        if view_kind not in {"all_observations", "qc_selected_observations"}:
            raise ValueError("qc_data_view_invalid")
        selected_data_view = {
            "view_kind": view_kind,
            "n_observations": _exact_nonnegative_int(
                raw_view.get("n_observations")
            ),
        }

    summary = {
        "state": "available",
        "evidence_ref": "E0",
        "tool_id": "P0-01",
        "execution_state": _value(run.execution_state),
        "assay": assay,
        "input_level": input_level,
        "readiness_state": _value(profile.readiness_state),
        "schema_integrity": schema_integrity,
        "count_metrics_state": count_metrics_state,
        "metrics": metrics,
        "assessment_states": assessment_states,
        "selected_data_view": selected_data_view,
        "score_state": _value(profile.score_state),
        "domain_score": profile.domain_score,
    }
    _check_summary_limit(summary)
    return summary, {
        "E0": {
            "input_id": input_id,
            "receipt_file": record["receipt_file"],
            "receipt_sha256": record["receipt_sha256"],
            "artifact_id": record["artifact_id"],
            "artifact_sha256": record["sha256"],
        }
    }


def _cell_state_context(inputs, state):
    receipt = _latest_receipt(state)
    if receipt is None:
        return {"state": "not_available"}, {}
    registered = _registered_profile(state, receipt)
    projector = _project
    if registered is None:
        registered = _registered_profile(state, receipt, LEGACY_PROFILE_SCHEMA)
        projector = _project_legacy
    if registered is None:
        return {"state": "not_available"}, {}
    try:
        return projector(inputs, state, receipt, *registered)
    except _SummaryLimit:
        return {"state": "unavailable", "reason_code": "result_summary_limit"}, {}
    except (KeyError, OSError, TypeError, UnicodeError, ValueError):
        return {"state": "unavailable", "reason_code": "result_evidence_invalid"}, {}


def _qc_context(inputs, state):
    receipt = _latest_receipt(state, "P0-01")
    if receipt is None:
        return None, {}
    registered = _registered_profile(state, receipt, QC_PROFILE_SCHEMA)
    if registered is None:
        return {"state": "not_available"}, {}
    try:
        return _project_qc(inputs, state, receipt, *registered)
    except _SummaryLimit:
        return {"state": "unavailable", "reason_code": "result_summary_limit"}, {}
    except (KeyError, OSError, TypeError, UnicodeError, ValueError):
        return {"state": "unavailable", "reason_code": "result_evidence_invalid"}, {}


def _bounded(summary, binding):
    try:
        _check_summary_limit(summary)
    except _SummaryLimit:
        return {"state": "unavailable", "reason_code": "result_summary_limit"}, {}
    return summary, binding


def build_result_context(inputs, state) -> tuple[dict, dict]:
    """Project canonical aggregate result evidence without raw-data access."""
    cell_state, cell_binding = _cell_state_context(inputs, state)
    qc, qc_binding = _qc_context(inputs, state)

    if cell_state["state"] == "available":
        combined = dict(cell_state)
        if qc is not None:
            combined["qc_summary"] = qc
        return _bounded(combined, {**cell_binding, **qc_binding})

    if qc is not None and qc["state"] == "available":
        combined = dict(qc)
        if _latest_receipt(state) is not None:
            combined["cell_state_summary"] = {
                key: cell_state[key]
                for key in ("state", "reason_code")
                if key in cell_state
            }
        return _bounded(combined, qc_binding)

    if _latest_receipt(state) is not None:
        return _bounded(cell_state, {})
    if qc is not None:
        return _bounded(qc, {})
    return {"state": "not_available"}, {}
