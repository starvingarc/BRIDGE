"""Bounded public-safe evidence projection for the private Web conversation."""
from __future__ import annotations

import json
import math
import hashlib
import re

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
    if receipt["file"] in state.get("_invalidated_receipts", {}):
        raise ValueError("input_revision_invalidated_output")
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


# These are aggregate result fields, never raw observations or free-text provenance.
_ASSESSMENT_FIELDS = {
    "release_state", "public_export_eligibility", "scientific_validation", "input_revision",
    "result_state", "upstream_composition_state", "channels", "composition_view", "label_level",
    "denominator_scope", "assessment_state", "target_identity_fraction", "regional_fidelity_fraction",
    "whole_product_target_region_fraction", "numerator", "denominator", "fraction", "value", "unit",
    "window_compatibility_state", "analysis_mode", "whole_product_profile", "target_related_profile",
    "denominator_kind", "role_fractions", "role", "primary_denominator", "n_observations",
    "total_soft_mass", "role_composition", "product_role", "soft_mass", "observed_count",
    "exclusion_state", "unknown_profile", "coverage_state", "rare_state_profile",
    "soft_fraction", "detection_state", "validated_detection_limit_fraction", "false_positive_fraction",
    "zero_observation_upper_bound_fraction", "program_results", "gene_coverage", "minimum_gene_coverage",
    "lod_state", "evidence_state", "analysis_scope", "applicability", "availability", "process_attribution",
    "process_attribution_state", "measurement_projection_state", "score_state", "domain_score",
    "runtime_mode", "interpretation_scope", "state_review_status", "independence_state",
    "n_independent_replicates", "n_features", "program_summaries", "program_id", "method_id", "score_unit",
    "observed_gene_count", "declared_gene_count", "mean", "median", "lower_quantile", "upper_quantile",
    "cell_cycle", "phase_counts", "S", "G2M", "G1", "s_g2m_fraction", "mean_s_score", "mean_g2m_score",
    "profiles", "domain_id", "evidence_sufficiency_state", "eligibility", "source_execution_state",
    "metric_name", "raw_value", "interval", "interval_confidence_level", "unknown_scope",
    "reason_codes", "composition", "reconciliation", "composition_state", "open_set_state",
    "calibration_state", "label", "count", "state_evidence_state",
    "accounting", "role_counts", "consensus_supported_count", "fraction_of_selected_view",
    "observation_unit", "producer_composition", "records", "state", "view", "source_id",
    "support_basis", "accounting_basis", "accounting_state", "mass_state", "primary_denominator_id",
}
_ASSESSMENT_IDENTIFIERS = {"program_id", "method_id", "label", "source_id", "primary_denominator_id"}


def _assessment_aggregate(value, key=""):
    if isinstance(value, dict):
        return {name: _assessment_aggregate(item, name) for name, item in value.items()
                if name in _ASSESSMENT_FIELDS}
    if isinstance(value, list):
        if len(value) > MAX_ROWS:
            raise _SummaryLimit()
        return [_assessment_aggregate(item, key) for item in value]
    if isinstance(value, str):
        # Keep fixed result states and units, never unrestricted paths/prose/IDs.
        if key == "reason_codes":
            if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,200}", value):
                raise ValueError("unsafe_reason_code")
            return value
        if key in _ASSESSMENT_IDENTIFIERS:
            # Verified names are interpretation metadata for the authenticated browser.
            # The provider receives only ephemeral aliases, never these local IDs.
            if len(value) > 200:
                raise _SummaryLimit()
            return value
        if not re.fullmatch(r"[A-Za-z0-9_ .%/-]{1,80}", value) or "/" in value:
            raise ValueError("unsafe_result_text")
        return value
    if value is None or type(value) in {int, float, bool}:
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("nonfinite_result")
        return value
    raise ValueError("unsupported_result")


def _assessment_hard_count(result):
    """Keep canonical hard accounting literal; private labels are aliased for the model."""
    from bridge.tool_packages.p0_05_off_target_control.models import OffTargetHardCountAccounting
    summary = _assessment_aggregate({key: value for key, value in result.items() if key != "accounting"})
    summary["accounting"] = _assessment_aggregate(OffTargetHardCountAccounting.model_validate(
        result["accounting"]).model_dump(mode="json"))
    return summary


def _assessment_query(result):
    """Retain typed scientific context locally; provider labels are vetted separately."""
    from bridge.tool_packages.p0_09_evidence_compiler.graph import node_id
    from bridge.tool_packages.p0_09_evidence_compiler.models import GraphNodeType
    def alias(value):
        return "N-" + hashlib.sha256(value.encode()).hexdigest()[:16]
    claims = {(row["object_id"], row["object_version"]): row.get("properties", {})
              for row in result["nodes"] if row["node_type"] == "Claim"}
    summary = {key: result[key] for key in ("query_name", "graph_version", "returned_node_count",
        "returned_edge_count", "truncated", "omitted_node_count", "omitted_edge_count")}
    summary["graph_alias"] = alias(result["graph_id"])
    for key in ("records", "requirements", "nodes", "claims", "reconciliations"):
        summary[key] = []
    for node in result["nodes"]:
        properties = node.get("properties", {})
        row = {"alias": alias(node["node_id"]), "node_type": node["node_type"],
               "evidence_tier": node["evidence_tier"], "lifecycle_state": node["lifecycle_state"]}
        summary["nodes"].append(row)
        if not properties:
            continue  # External references have no source-case semantics in this query.
        if node["node_type"] == "Claim":
            summary["claims"].append({**row, "domain_id": properties["domain_id"],
                                     "claim_type": properties["claim_type"]})
            continue
        ref = properties.get("claim_ref")
        if ref:
            claim = claims.get((ref["object_id"], ref["object_version"]), {})
            row = {**row, "claim_alias": alias(node_id(ref["object_id"], ref["object_version"], GraphNodeType.CLAIM)),
                   "domain_id": claim.get("domain_id"),
                   "claim_context_state": "available" if claim else "unavailable"}
        if node["node_type"] == "EvidenceRequirement":
            summary["requirements"].append({**row, **{key: properties[key] for key in
                ("state", "requirement_key", "channel_role", "reason_codes", "required_modality")},
                "experiment_required": properties.get("required_experiment") is not None})
        elif node["node_type"] == "EvidenceRecord":
            summary["records"].append({**row, **{key: properties.get(key) for key in
                ("domain_id", "evidence_state", "value", "unit", "metric_id",
                 "numerator", "denominator", "applicability", "relation")},
                "interval": ({key: properties["interval"].get(key) for key in
                    ("lower", "upper", "confidence_level")} if properties.get("interval") else None),
                "family_alias": alias(json.dumps(properties["evidence_family_ref"], sort_keys=True))})
        elif node["node_type"] == "ReconciliationRecord":
            summary["reconciliations"].append({**row, **{key: properties[key] for key in
                ("eligibility", "state", "direction", "reason_codes")},
                "channels": [{key: channel[key] for key in ("channel_role", "direction", "eligible", "reason_codes")}
                             for channel in properties["channel_resolutions"]]})
    summary["edges"] = [{"type": edge["edge_type"], "source": alias(edge["source_node_id"]),
                         "target": alias(edge["target_node_id"])} for edge in result["edges"]]
    return summary


def _assessment_model_query(summary, opaque):
    """Only source-defined enums/Literals and audited built-in policy words cross this seam."""
    from typing import get_args
    from bridge.tool_packages.p0_03_target_regional.models import NormalizedMetricName
    from bridge.tool_packages.p0_04_developmental_compatibility.models import DevelopmentMeasurementMetricName
    from bridge.tool_packages.p0_05_off_target_control.models import (
        HardCountMetricName, OffTargetMeasurementArtifactBinding)
    from bridge.tool_packages.p0_06_proliferation_stress_response.models import MethodMeasurementArtifactBinding
    from bridge.tool_packages.p0_09_evidence_compiler.models import MissingEvidenceObservation
    from bridge.tool_packages.p0_09_evidence_compiler.reconciler import RECONCILIATION_REASON_CODES
    metrics = {item.value for enum in (NormalizedMetricName, DevelopmentMeasurementMetricName) for item in enum}
    metrics.update(get_args(HardCountMetricName))
    for model in (OffTargetMeasurementArtifactBinding, MethodMeasurementArtifactBinding):
        metrics.update(get_args(model.model_fields["metric_name"].annotation))
    missing_reasons = set(get_args(MissingEvidenceObservation.model_fields["reason_code"].annotation))
    # These two additional reasons are emitted by compiler.build_requirements.
    missing_reasons.update({"required_evidence_missing", "qualifying_evidence_available"})
    # The sole built-in Web candidate policy declares these exact public words.
    policy_words = {"claim_type": {"descriptive_domain_observation"},
                    "requirement_key": {"canonical_measurement"}, "channel_role": {"canonical_measurement"}}
    # Non-identifying units used by the registered numerical producers. Unknown custom
    # units remain private, even if syntactically valid in an imported graph.
    units = {"fraction", "cells", "observations", "count", "scanpy_control_adjusted_expression",
             "decoupler_ulm_t_value", "scanpy_relative_expression_score"}

    def base(row):
        result = {key: row[key] for key in ("node_type", "evidence_tier", "lifecycle_state",
                    "domain_id", "claim_context_state") if key in row}
        result.update({key: opaque(row[key]) for key in ("alias", "claim_alias", "family_alias") if key in row})
        return result

    def label(row, key):
        value = row[key]
        return ({key: value, key + "_semantics_state": "available"} if value in policy_words[key] else
                {key + "_alias": opaque(value), key + "_semantics_state": "unavailable"})

    def reasons(values, allowed):
        return {"reason_codes": [value for value in values if value in allowed],
                "reason_semantics_state": "available" if all(value in allowed for value in values) else "unavailable",
                "withheld_reason_count": sum(value not in allowed for value in values)}

    projected = {key: summary[key] for key in ("query_name", "graph_version", "returned_node_count",
        "returned_edge_count", "truncated", "omitted_node_count", "omitted_edge_count")}
    projected.update({key: summary[key] for key in ("display_omitted_edges", "display_omitted_nodes") if key in summary})
    projected["graph_alias"] = opaque(summary["graph_alias"])
    projected["nodes"] = [base(row) for row in summary["nodes"]]
    projected["claims"] = [{**base(row), **label(row, "claim_type")} for row in summary["claims"]]
    projected["requirements"] = [{**base(row), "state": row["state"],
        **label(row, "requirement_key"), **label(row, "channel_role"),
        **reasons(row["reason_codes"], missing_reasons),
        "required_modality": row["required_modality"] if row["required_modality"] in QC_ASSAYS else None,
        "modality_semantics_state": "available" if row["required_modality"] in QC_ASSAYS else "unavailable",
        "experiment_required": row["experiment_required"]} for row in summary["requirements"]]
    projected["records"] = []
    for row in summary["records"]:
        known = row["metric_id"] in metrics
        projection_state = ("literal_null" if row["value"] is None else
                            "numeric" if type(row["value"]) in {int, float} else "withheld")
        projected["records"].append({**base(row), **{key: row[key] for key in
            ("evidence_state", "numerator", "denominator", "applicability", "relation", "interval")},
            **({"metric_name": row["metric_id"]} if known else {"metric_alias": opaque(row["metric_id"])}),
            "metric_semantics_state": "available" if known else "unavailable",
            "value": row["value"] if projection_state != "withheld" else None,
            "value_projection_state": projection_state,
            "unit": row["unit"] if row["unit"] in units else None,
            "unit_semantics_state": "available" if row["unit"] in units else "unavailable"})
    projected["reconciliations"] = [{**base(row), **{key: row[key] for key in ("eligibility", "state", "direction")},
        **reasons(row["reason_codes"], RECONCILIATION_REASON_CODES),
        "channels": [{**label(channel, "channel_role"), "direction": channel["direction"], "eligible": channel["eligible"],
            **reasons(channel["reason_codes"], RECONCILIATION_REASON_CODES)} for channel in row["channels"]]}
        for row in summary["reconciliations"]]
    projected["edges"] = [{"type": row["type"], "source": opaque(row["source"]), "target": opaque(row["target"])}
                          for row in summary["edges"]]
    return projected





def assessment_portrait(evidence, candidates):
    """Arrange verified values by their producer contract; never rescore or classify programs."""
    axes = []
    definitions = (
        ("cell_state", "细胞状态", "P0-02"),
        ("target_identity", "目标身份", "P0-03"),
        ("regional_identity", "区域身份", "P0-03"),
        ("development", "发育阶段", "P0-04"),
        ("composition", "全产品与非目标组成", "P0-05"),
        ("process", "增殖与应激", "P0-06"),
    )
    for identifier, title, tool in definitions:
        row = next((item for item in reversed(evidence) if item["tool_id"] == tool), None)
        reasons = sorted({reason for item in candidates if item["tool_id"] == tool
                          for reason in item["blockers"]})
        summary = row.get("summary", {}) if row else {}
        if identifier in {"target_identity", "regional_identity"}:
            fields = {"target_identity_fraction"} if identifier == "target_identity" else {
                "regional_fidelity_fraction", "whole_product_target_region_fraction"}
            summary = {**{key: value for key, value in summary.items() if key != "channels"},
                "channels": [{key: value for key, value in channel.items()
                              if key in fields | {"assessment_state", "reason_codes", "label_level",
                                                  "composition_view", "denominator_scope"}}
                             for channel in summary.get("channels", [])]}
        axis = {"id": identifier, "title": title,
            "state": row["state"] if row else "unavailable" if reasons else "missing",
            "reason_codes": (row.get("summary", {}).get("reason_codes", [])
                            if row and row["state"] == "available" else
                            [row["reason_code"]] if row else reasons or ["no_scope_evidence"]),
            "evidence_aliases": [row["alias"]] if row else [], "summary": summary}
        if identifier == "process":
            cycle = next((item for item in reversed(evidence) if item["tool_id"] == "P0-06"
                          and item["state"] == "available"
                          and item["summary"].get("runtime_mode") == "exploratory_process"
                          and item["summary"].get("cell_cycle")), None)
            axis["families"] = []
            for family_id, family_title in (
                ("pluripotency_like", "多能性样程序"), ("cell_cycle", "细胞周期"),
                ("dissociation_heat_shock", "解离 / 热休克"), ("oxidative_stress", "氧化应激"),
                ("hypoxia", "缺氧"), ("unfolded_protein_response", "未折叠蛋白反应"),
                ("apoptosis_related", "凋亡相关程序")):
                family = {"id": family_id, "title": family_title, "state": "unavailable",
                    "reason_codes": ["reviewed_family_mapping_unavailable"],
                    "summary": {}, "evidence_aliases": []}
                if family_id == "cell_cycle" and cycle:
                    measured = cycle["summary"]["cell_cycle"]
                    family.update(state="measured" if measured["assessment_state"] == "available" else "unavailable",
                        reason_codes=measured["reason_codes"], summary=measured, evidence_aliases=[cycle["alias"]])
                axis["families"].append(family)
        axes.append(axis)
    return axes


def assessment_model_evidence(evidence):
    """Rebuild this provider purpose from explicit fields and ephemeral join aliases."""
    import secrets
    bindings = {"evidence": {}, "references": {}}
    aliases = {}
    def opaque(value, kind="references"):
        key = (kind, value)
        if key not in aliases:
            aliases[key] = ("E-" if kind == "evidence" else "R-") + secrets.token_hex(16)
            bindings[kind][aliases[key]] = value
        return aliases[key]
    join_fields = {"alias", "source_alias", "graph_alias", "family_alias", "source", "target"}
    summary_fields = _ASSESSMENT_FIELDS | {
        "query_name", "graph_version", "returned_node_count", "returned_edge_count",
        "truncated", "omitted_node_count", "omitted_edge_count", "graph_alias",
        "records", "requirements", "nodes", "edges", "alias", "node_type",
        "evidence_tier", "lifecycle_state", "state", "relation", "family_alias",
        "type", "source", "target"}
    def aggregate(value, key=""):
        if isinstance(value, dict):
            return {name: aggregate(item, name) for name, item in value.items() if name in summary_fields}
        if isinstance(value, list):
            return [aggregate(item, key) for item in value]
        if isinstance(value, str) and (key in join_fields or key in _ASSESSMENT_IDENTIFIERS):
            return opaque(value)
        return value
    result = []
    for row in evidence:
        projected = {"alias": opaque(row["alias"], "evidence")}
        projected.update({key: row[key] for key in (
            "state", "tool_id", "tool_version", "execution_state", "score_state",
            "domain_score", "reason_code", "interpretation_scope") if key in row})
        if row["state"] == "available":
            projected["summary"] = (_assessment_model_query(row["summary"], opaque)
                if "query_name" in row["summary"] else aggregate(row["summary"]))
            projected["measurements"] = []
            for item in row["measurements"]:
                measurement = aggregate({key: value for key, value in item.items()
                    if key in _ASSESSMENT_FIELDS})
                if "alias" in item:
                    measurement["alias"] = opaque(item["alias"])
                if "source_alias" in item:
                    measurement["source_alias"] = opaque(item["source_alias"], "evidence")
                if "measurement_class" in item:
                    measurement["measurement_class"] = item["measurement_class"]
                projected["measurements"].append(measurement)
        result.append(projected)
    return result, bindings


def _assessment_display_artifacts(inputs, state, run, receipt):
    """Resolve only display IDs bound to this checked receipt or query source graph."""
    source_receipt, source_run = receipt, run
    graph = None
    if "query_name" in (run.result or {}):
        ref = next(ref for ref in run.request.object_inputs if ref.role == "evidence_graph_manifest")
        record = state["_input_objects"].get(ref.input_id)
        if not record or record["sha256"] != ref.sha256 or record["path"] != str(ref.path):
            raise ValueError("query_source_binding_invalid")
        graph = inputs.verify(state, record)
        if (graph["graph_id"] != run.result["graph_id"]
                or graph["graph_version"] != run.result["graph_version"]):
            raise ValueError("query_source_version_invalid")
        source_receipt = next(row for row in state["_tool_runs"]
            if row["file"] == record["receipt_file"] and row["sha256"] == record["receipt_sha256"])
        from bridge.toolkit.contracts import ToolRunV2
        source_run = ToolRunV2.model_validate(_verified_receipt(inputs, state, source_receipt))
        inputs.service.registry.validate_historical_result(source_run, source_run.request)
    canonical = {(item.artifact_id, item.sha256) for item in source_run.artifacts}
    ids = []
    for display in state.get("artifacts", []):
        binding = state.get("_canonical_artifacts", {}).get(display["id"], {})
        exposed = state.get("_artifacts", {}).get(display["id"], {})
        if (binding.get("receipt_file") == source_receipt["file"]
                and binding.get("receipt_sha256") == source_receipt["sha256"]
                and (binding.get("artifact_id"), binding.get("sha256")) in canonical
                and exposed.get("source_artifact_id") == binding["artifact_id"]
                and exposed.get("source_sha256") == binding["sha256"]):
            ids.append(display["id"])
    dependencies = []
    for ref in getattr(run.request, "object_inputs", []):
        record = state.get("_input_objects", {}).get(ref.input_id, {})
        links = []
        if record.get("sha256") == ref.sha256:
            for display in state.get("artifacts", []):
                binding = state.get("_canonical_artifacts", {}).get(display["id"], {})
                exposed = state.get("_artifacts", {}).get(display["id"], {})
                if (record.get("receipt_sha256") is not None
                        and all(binding.get(key) == record.get(key) for key in
                                ("receipt_sha256", "receipt_file", "sha256", "artifact_id"))
                        and exposed.get("source_artifact_id") == record.get("artifact_id")
                        and exposed.get("source_sha256") == ref.sha256):
                    links.append(display["id"])
        dependencies.append({"role": ref.role, "schema_ref": ref.schema_ref,
            "object_version": ref.object_version, "sha256": ref.sha256, "artifact_ids": links})
    return ids, {"source_receipt_sha256": source_receipt["sha256"],
                 **({"graph_id": graph["graph_id"], "graph_version": graph["graph_version"]} if graph else {})}, dependencies


def _project_candidate(inputs, state, receipt, input_id, record):
    from bridge.tool_packages.p0_02_cell_state.candidate_runtime import CellStateCandidateProfile
    profile = CellStateCandidateProfile.model_validate(inputs.verify(state, record))
    run = _verified_receipt(inputs, state, receipt)
    if (record.get("producer_tool_id") != "P0-02" or profile.producer_run_ref != run["run_id"]
            or profile.producer_tool_version != run["tool_version"]
            or profile.input_sha256 != run["input_hash"]
            or run["result"] != profile.model_dump(mode="json")):
        raise ValueError("candidate_profile_producer_mismatch")
    summary = {
        "analysis_scope": "candidate_method_observation", "method_id": profile.primary_method,
        "state_review_status": profile.scientific_qualification,
        "n_observations": profile.n_observations, "n_features": profile.n_genes,
        "gene_coverage": profile.feature_coverage,
        "independence_state": profile.biological_unit_state, "n_independent_replicates": None,
        "score_state": "unavailable", "domain_score": None,
        "reason_codes": profile.development_reason_codes,
        "composition": [{"label": row["label"], "state": row["assignment_state"],
            "count": row["count"], "denominator": row["denominator"], "fraction": row["fraction"],
            "denominator_scope": row["denominator_scope"], "evidence_state": "inferred"}
            for row in profile.candidate_composition],
    }
    return _assessment_aggregate(summary), {"profile_input_id": input_id, "profile_sha256": record["sha256"]}


def assessment_evidence(inputs, state, assessment):
    """Read canonical ToolRuns on demand; no duplicate result store and no raw cell rows."""
    from bridge.toolkit.contracts import ToolRunV2, MeasurementResultV2
    plans = {row["plan_id"] for row in assessment["admissions"]}
    pinned = {}
    for record in assessment.get("scope", {}).get("binding", {}).get("resources", {}).values():
        if record.get("source") == "tool_output":
            key = (record.get("receipt_file"), record.get("receipt_sha256"), record.get("producer_tool_id"))
            pinned.setdefault(key, []).append(record)
    receipts = state.get("_tool_runs", [])
    # Current admissions stay first. Reused evidence is explicitly scope-bound,
    # never every old result in the session, and never a new execution or vote.
    admitted = [row for row in receipts if row.get("plan_id") in plans]
    reused = [row for row in receipts if row.get("plan_id") not in plans
              and row["file"] not in state.get("_invalidated_receipts", {})
              and (row["file"], row["sha256"], row["tool_id"]) in pinned]
    projected, bindings = [], {}
    for receipt in [*admitted, *reused]:
        if receipt["state"] not in {"succeeded", "partial"}:
            continue
        alias = "E-" + receipt["sha256"][:16]
        try:
            for record in pinned.get((receipt["file"], receipt["sha256"], receipt["tool_id"]), []):
                inputs.verify(state, record)
            raw = _verified_receipt(inputs, state, receipt)
            run = ToolRunV2.model_validate(raw) if "object_inputs" in raw["request"] else ToolRun.model_validate(raw)
            inputs.service.registry.validate_historical_result(run, run.request)
            root = inputs.service.directory(state["id"]) / "runs"
            for artifact in run.artifacts:
                checked_bytes(inputs.service, state, artifact.path, artifact.sha256, root=root)
            result = raw.get("result") or {}
            if receipt["tool_id"] == "P0-02":
                registered = _registered_profile(state, receipt)
                projector = _project
                if registered is None:
                    registered = _registered_profile(state, receipt, LEGACY_PROFILE_SCHEMA)
                    projector = _project_legacy
                if registered is None:
                    registered = _registered_profile(state, receipt, "bridge://schemas/cell-state-candidate-profile/v1.0")
                    projector = _project_candidate
                if registered is None:
                    raise ValueError("canonical_cell_state_profile_required")
                summary, _ = projector(inputs, state, receipt, *registered)
            else:
                summary = (_assessment_query(result) if "query_name" in result else
                    _assessment_hard_count(result) if "accounting" in result and receipt["tool_id"] == "P0-05"
                    else _assessment_aggregate(result))
            measurements = []
            canonical = [artifact for artifact in run.artifacts if artifact.kind == "measurement_result_v2"]
            for artifact in canonical:
                item = MeasurementResultV2.model_validate_json(checked_bytes(
                    inputs.service, state, artifact.path, artifact.sha256, root=root))
                if (item.source_run_ref != f"tool-run:{run.run_id}@{run.tool_version}"
                        or item.source_execution_state != receipt["state"]):
                    raise ValueError("measurement_source_mismatch")
                payload = item.model_dump(mode="json")
                if payload["raw_value"] is not None and type(payload["raw_value"]) not in {int, float}:
                    raise ValueError("nonaggregate_measurement_value")
                measurements.append({
                    "alias": "M-" + artifact.sha256[:16], "measurement_class": "gate_input_measurement",
                    **_assessment_aggregate({key: payload[key] for key in ("metric_name", "raw_value", "numerator", "denominator",
                        "unit", "interval", "interval_confidence_level", "unknown_scope", "evidence_state",
                        "score_state", "domain_score", "source_execution_state")}),
                    "source_alias": alias, "artifact_sha256": artifact.sha256,
                })
            if not canonical:
                for item in raw.get("measurements", []):
                    measurements.append({"measurement_class": "legacy_tool_measurement",
                        **{key: item[key] for key in ("raw_value", "numerator", "denominator",
                                                     "evidence_state", "score_state", "domain_score")
                           if key in item and (key != "raw_value" or item[key] is None or type(item[key]) in {int, float})}})
            artifact_ids, source, dependencies = _assessment_display_artifacts(inputs, state, run, receipt)
            row = {"alias": alias, "state": "available", "tool_id": receipt["tool_id"],
                "tool_version": run.tool_version, "execution_state": receipt["state"],
                "domain_score": None, "score_state": result.get("score_state", "unavailable"),
                "summary": summary, "measurements": measurements,
                "interpretation_scope": "exploratory" if result.get("runtime_mode") == "exploratory_process" else "registered_tool_result",
                "artifact_ids": artifact_ids, "dependencies": dependencies,
                "provenance": {"receipt_sha256": receipt["sha256"], "plan_id": receipt["plan_id"], **source}}
            if "query_name" in summary:
                # Keep literal records/requirements; large topology remains in the
                # source graph artifact instead of invalidating valid evidence.
                for field in ("edges", "nodes"):
                    try:
                        _check_summary_limit(row)
                        break
                    except _SummaryLimit:
                        summary["display_omitted_" + field] = len(summary[field])
                        summary[field] = []
            _check_summary_limit(row)
            projected.append(row)
            bindings[alias] = {"receipt_file": receipt["file"], "receipt_sha256": receipt["sha256"],
                               "plan_id": receipt["plan_id"]}
        except (ValueError, OSError, KeyError, TypeError):
            projected.append({"alias": alias, "state": "unavailable", "tool_id": receipt["tool_id"],
                              "reason_code": "canonical_result_invalid"})
    return projected, bindings


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
