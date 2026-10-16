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

from .inputs import checked_bytes, integrity_limit, strict_json, verify_checked_file

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
    verify_checked_file(
        inputs.service,
        state,
        asset.path,
        asset.checksum,
        limit=inputs.service.settings.max_upload_bytes,
    )

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


def _check_summary_limit(summary, *, limit=None):
    if limit is None:
        limit = MAX_SUMMARY_BYTES
    encoded = json.dumps(
        summary,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode()
    if len(encoded) > limit:
        raise _SummaryLimit()


def _assessment_result_limit(tool_id, result):
    if result.get("runtime_mode") == "saved_cell_state_context":
        # Whole-view fine states retain both their count/denominator rows and
        # independently citable measurements. The combined projection can exceed
        # 64 KiB; its allowlisted rows remain bounded by MAX_ROWS.
        if (tool_id in {"P0-03", "P0-05"}
                and isinstance(result.get("whole_product_composition"), list)):
            return 128 * 1024
        return 64 * 1024
    if (tool_id == "P0-09" and result.get("query_name") == "get_case_evidence_subgraph"
            and type(result.get("returned_node_count")) is int
            and 0 <= result["returned_node_count"] <= 100):
        return 64 * 1024
    return MAX_SUMMARY_BYTES


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
    return project_qc_summary(run, payload, run_payload=run_payload), {
        "E0": {
            "input_id": input_id,
            "receipt_file": record["receipt_file"],
            "receipt_sha256": record["receipt_sha256"],
            "artifact_id": record["artifact_id"],
            "artifact_sha256": record["sha256"],
        }
    }


def project_qc_summary(run, payload, *, run_payload=None):
    """Shared validated QC summary for session and sample result readers."""
    profile = QCReadinessProfileV2.model_validate(payload)
    if run_payload is None:
        run_payload = run.model_dump(mode="json")
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
    return summary


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
    "signature_scope", "gene_coverage_fraction", "source_gene_set", "gene_symbols_sha256",
    "direction_definition", "unresolved_member_count",
    "missing_genes", "ambiguous_genes",
    "cell_cycle", "phase_counts", "S", "G2M", "G1", "s_g2m_fraction", "mean_s_score", "mean_g2m_score",
    "profiles", "domain_id", "evidence_sufficiency_state", "eligibility", "source_execution_state",
    "metric_name", "raw_value", "interval", "interval_confidence_level", "unknown_scope",
    "reason_codes", "composition", "reconciliation", "composition_state", "open_set_state",
    "calibration_state", "label", "count", "state_evidence_state",
    "accounting", "role_counts", "consensus_supported_count", "fraction_of_selected_view",
    "observation_unit", "producer_composition", "records", "state", "view", "source_id",
    "support_basis", "accounting_basis", "accounting_state", "mass_state", "primary_denominator_id",
}
_ASSESSMENT_FIELDS.update({"primary_composition", "auxiliary_composition", "marker_observations",
    "channel", "expected_window_match", "target_fraction", "non_target_fraction",
    "role_judgement_state", "state_id", "definition_decision", "identity_state",
    "positive_genes", "counter_genes", "source_ids", "gene_detection"})
_ASSESSMENT_FIELDS.update({"whole_product_composition", "data_view", "record_id", "record_kind", "display_name",
    "level", "parent_state_id", "resolution_state", "whole_product_denominator",
    "whole_product_fraction", "parent_denominator", "parent_fraction", "scientific_status",
    "source_definition_decisions"})
_ASSESSMENT_IDENTIFIERS = {"program_id", "method_id", "source_gene_set", "label", "source_id", "primary_denominator_id"}
_ASSESSMENT_IDENTIFIERS.update({"display_name", "record_id", "parent_state_id", "state_id", "positive_genes", "counter_genes", "source_ids"})
_PROGRAM_FAMILIES_BY_SET = {
    "HU-2020-TABLE-S1": "pluripotency_like",
    "OFLANAGAN-2019-CORE": "dissociation_heat_shock",
    "HALLMARK_REACTIVE_OXYGEN_SPECIES_PATHWAY": "oxidative_stress",
    "HALLMARK_UNFOLDED_PROTEIN_RESPONSE": "unfolded_protein_response",
    "HALLMARK_APOPTOSIS": "apoptosis_related",
    "HALLMARK_HYPOXIA": "hypoxia",
}


def _assessment_aggregate(value, key=""):
    if isinstance(value, dict):
        if key == "source_definition_decisions":
            if len(value) > MAX_ROWS:
                raise _SummaryLimit()
            if any(not re.fullmatch(r"L[12]:[A-Za-z0-9_]+", state_id)
                   or decision not in {"evaluate", "parent_only", "unavailable"}
                   for state_id, decision in value.items()):
                raise ValueError("unsafe_state_definition_decision")
            return dict(value)
        if key == "gene_detection":
            if len(value) > MAX_ROWS:
                raise _SummaryLimit()
            if any(not isinstance(gene, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", gene)
                   for gene in value):
                raise ValueError("unsafe_gene_identifier")
            return {gene: _assessment_aggregate({name: row[name] for name in
                ("count", "denominator", "state") if name in row}) for gene, row in value.items()}
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


def _directed_program_summary(result):
    # Count unresolved source members without exposing the private membership list.
    return {**result, "program_summaries": [
        {**program, "unresolved_member_count": len(program["unresolved_members"])}
        for program in result["program_summaries"]]}


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
    eligible_directions = {}
    for node in result["nodes"]:
        if node["node_type"] != "ReconciliationRecord":
            continue
        properties = node.get("properties", {})
        direction = properties.get("direction")
        if properties.get("eligibility") != "eligible" or direction not in {"supports", "contradicts"}:
            continue
        for evidence_ref in properties.get("included_evidence_refs", []):
            eligible_directions.setdefault(evidence_ref, set()).add(direction)
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
            evidence_ref = f"{properties['evidence_id']}@{properties['evidence_version']}"
            directions = eligible_directions.get(evidence_ref, set())
            source_verified = (node.get("record_mode") == "owned"
                and node.get("graph_id") == result["graph_id"]
                and node.get("graph_version") == result["graph_version"]
                and all(properties.get(key) for key in ("tool_run_ref", "measurement_result_ref",
                                                     "measurement_spec_ref", "provenance_refs"))
                and properties.get("tool_run_execution_state") in {"succeeded", "partial"})
            summary["records"].append({**row, **{key: properties.get(key) for key in
                ("domain_id", "evidence_state", "value", "unit", "metric_id",
                 "numerator", "denominator", "applicability", "relation")},
                "source_verification_state": "verified" if source_verified else "unavailable",
                "source_execution_state": properties.get("tool_run_execution_state"),
                "eligibility": ("eligible" if properties.get("relation") in directions
                                else "not_eligible"),
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
            ("evidence_state", "numerator", "denominator", "applicability", "relation", "interval",
             "source_verification_state", "source_execution_state") if key in row},
            "eligibility": row.get("eligibility", "not_eligible"),
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


_CITATION_REF_VERSION = 1
_MISSING_CITATION_STATES = {"missing", "unknown", "unavailable", "not_assessed", "not_estimable"}
_OBSERVATION_CITATION_STATES = {"measured", "inferred", "prior_only", "negative", "alert"}


def _citation_role(record, *, graph_record=False):
    state = record.get("evidence_state")
    if state in _MISSING_CITATION_STATES:
        return "missing"
    if graph_record:
        if record.get("eligibility") == "eligible":
            return {"supports": "support", "contradicts": "opposition"}.get(record.get("relation"))
        if (record.get("source_verification_state") == "verified"
                and record.get("source_execution_state") in {"succeeded", "partial"}
                and record.get("evidence_tier") in {"exploratory", "shadow"}
                and record.get("lifecycle_state") == "active"
                and record.get("applicability") == "applicable"
                and record.get("evidence_state") in _OBSERVATION_CITATION_STATES
                and type(record.get("value")) in {int, float}
                and math.isfinite(record["value"])):
            return "observation"
        return None
    if (record.get("claim_ref") is not None
            and record.get("applicability") == "applicable"):
        bound = {"supports": "support", "contradicts": "opposition"}.get(record.get("relation"))
        if bound is not None:
            return bound
    if state in _OBSERVATION_CITATION_STATES:
        return "observation"
    return None


def _citation_ref(evidence_alias, kind, record_alias):
    return f"{evidence_alias}#{kind}:{record_alias}@{_CITATION_REF_VERSION}"


def assessment_citation_roles(evidence):
    """Return stable record references by scientific citation role."""
    roles = {"support": set(), "observation": set(), "opposition": set(), "missing": set()}
    for row in evidence:
        if row.get("state") != "available":
            continue
        for item in row.get("measurements", []):
            role = _citation_role(item)
            if role and isinstance(item.get("alias"), str):
                roles[role].add(_citation_ref(row["alias"], "measurement", item["alias"]))
        for item in row.get("summary", {}).get("records", []):
            role = _citation_role(item, graph_record=True)
            if role and isinstance(item.get("alias"), str):
                roles[role].add(_citation_ref(row["alias"], "record", item["alias"]))
    return roles





def assessment_portrait(evidence, candidates, *, current_plan_ids=(), modes_by_receipt=None,
                        order_by_receipt=None):
    """Arrange verified values by their producer contract; never rescore or classify programs."""
    current_plan_ids = set(current_plan_ids)
    modes_by_receipt = modes_by_receipt or {}
    order_by_receipt = order_by_receipt or {}
    def latest(tool, *, modes=None):
        matching = []
        for position, item in enumerate(evidence):
            if item["tool_id"] != tool:
                continue
            mode = (modes_by_receipt.get(item.get("provenance", {}).get("receipt_sha256"))
                    or item.get("mode_id") or item.get("summary", {}).get("runtime_mode"))
            if modes is None or mode in modes:
                matching.append((position, item))
        if not matching:
            return None
        current = [(position, item) for position, item in matching
                   if item.get("provenance", {}).get("plan_id") in current_plan_ids]
        return max(current or matching, key=lambda pair: (
            order_by_receipt.get(pair[1].get("provenance", {}).get("receipt_sha256"), pair[0]),
            pair[0]))[1]
    def latest_program(source_gene_set):
        matching = []
        for position, item in enumerate(evidence):
            if (item["tool_id"] == "P0-06" and
                    any(row.get("source_gene_set") == source_gene_set
                        for row in item.get("summary", {}).get("program_summaries", []))):
                matching.append((position, item))
        if not matching:
            return None
        current = [(position, item) for position, item in matching
                   if item.get("provenance", {}).get("plan_id") in current_plan_ids]
        return max(current or matching, key=lambda pair: (
            order_by_receipt.get(pair[1].get("provenance", {}).get("receipt_sha256"), pair[0]),
            pair[0]))[1]
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
        row = (latest(tool, modes={"method_runtime_source_bound"})
               or latest(tool, modes={"exploratory_programs"})
               or latest(tool, modes={"exploratory_process"})) if identifier == "process" else (
                   latest(tool, modes={None, "default"}) if tool == "P0-03" else latest(tool))
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
        if identifier in {"target_identity", "regional_identity"}:
            context = latest("P0-03", modes={"reference_similarity_exploratory",
                                             "saved_reference_similarity_projection"})
            # Similarity is inspectable context, never a substitute for identity measurements.
            axis["context_evidence_aliases"] = (
                [context["alias"]] if context and context["state"] == "available" else [])
            if identifier == "target_identity":
                roles = latest("P0-03", modes={"saved_cell_state_context"})
                if roles and roles["state"] == "available":
                    axis["context_evidence_aliases"].append(roles["alias"])
        if identifier == "process":
            cycle = latest("P0-06", modes={"exploratory_process"})
            families_by_set = _PROGRAM_FAMILIES_BY_SET
            axis["families"] = []
            for family_id, family_title in (
                ("pluripotency_like", "多能性样程序"), ("cell_cycle", "细胞周期"),
                ("dissociation_heat_shock", "解离 / 热休克"), ("oxidative_stress", "氧化应激"),
                ("hypoxia", "缺氧"), ("unfolded_protein_response", "未折叠蛋白反应"),
                ("apoptosis_related", "凋亡相关程序")):
                family = {"id": family_id, "title": family_title, "state": "unavailable",
                    "reason_codes": ["reviewed_family_mapping_unavailable"],
                    "summary": {}, "evidence_aliases": []}
                if family_id == "cell_cycle" and cycle and cycle["state"] != "available":
                    family.update(reason_codes=[cycle.get("reason_code", "source_unavailable")],
                                  evidence_aliases=[cycle["alias"]])
                elif family_id == "cell_cycle" and cycle and cycle.get("summary", {}).get("cell_cycle"):
                    measured = cycle["summary"]["cell_cycle"]
                    family.update(state="measured" if measured["assessment_state"] == "available" else "unavailable",
                        reason_codes=measured["reason_codes"], summary=measured, evidence_aliases=[cycle["alias"]])
                elif family_id in families_by_set.values():
                    source_set = next(key for key, value in families_by_set.items() if value == family_id)
                    source = latest_program(source_set)
                    if source and source["state"] == "available":
                        matching = [item for item in source.get("summary", {}).get("program_summaries", [])
                                    if item.get("source_gene_set") == source_set]
                        family.update(state="measured" if any(item.get("assessment_state") == "available"
                                                             for item in matching) else "unavailable",
                            reason_codes=sorted({reason for item in matching for reason in item.get("reason_codes", [])}),
                            summary={"program_summaries": matching}, evidence_aliases=[source["alias"]])
                    elif source:
                        family.update(reason_codes=[source.get("reason_code", "source_unavailable")],
                                      evidence_aliases=[source["alias"]])
                axis["families"].append(family)
        axes.append(axis)
    return axes


def assessment_model_evidence(evidence):
    """Rebuild this provider purpose from explicit fields and ephemeral join aliases."""
    import secrets
    bindings = {"evidence": {}, "references": {}, "citation_roles": {}}
    aliases = {}
    def opaque(value, kind="references", *, citable=False):
        key = (kind, value, citable)
        if key not in aliases:
            # Only record-level citations enter the E namespace. Context joins
            # and result containers must not look like admissible evidence.
            aliases[key] = ("E-" if citable else "R-") + secrets.token_hex(16)
            bindings[kind][aliases[key]] = value
        return aliases[key]
    join_fields = {"alias", "source_alias", "graph_alias", "family_alias", "source", "target"}
    summary_fields = (_ASSESSMENT_FIELDS - {"gene_symbols_sha256"}) | {
        "query_name", "graph_version", "returned_node_count", "returned_edge_count",
        "truncated", "omitted_node_count", "omitted_edge_count", "graph_alias",
        "records", "requirements", "nodes", "edges", "alias", "node_type",
        "evidence_tier", "lifecycle_state", "state", "relation", "family_alias",
        "type", "source", "target"}
    def aggregate(value, key=""):
        if isinstance(value, dict):
            if key in {"gene_detection", "source_definition_decisions"}:
                return {opaque(identifier): aggregate(row) for identifier, row in value.items()}
            projected = {name: aggregate(item, name) for name, item in value.items() if name in summary_fields}
            if key == "program_summaries":
                # Public, reviewed semantics supplement opaque source identities;
                # never forward arbitrary program/method labels from the input.
                family = _PROGRAM_FAMILIES_BY_SET.get(value.get("source_gene_set"))
                if family:
                    projected["program_family"] = family
                method = {"PROC-SCORE-SCANPY": "Scanpy score_genes",
                          "PROC-SCORE-DECOUPLER": "decoupler ULM"}.get(value.get("method_id"))
                if method:
                    projected["method_name"] = method
            return projected
        if isinstance(value, list):
            return [aggregate(item, key) for item in value]
        if isinstance(value, str) and (key in join_fields or key in _ASSESSMENT_IDENTIFIERS
                or key in {"missing_genes", "ambiguous_genes"}):
            return opaque(value)
        return value
    def cite(projected, source, evidence_alias, kind, *, graph_record=False):
        role = _citation_role(source, graph_record=graph_record)
        record_alias = source.get("alias")
        if role is None or not isinstance(record_alias, str):
            return
        alias = opaque(_citation_ref(evidence_alias, kind, record_alias), "evidence", citable=True)
        projected.update(citation_alias=alias, citation_role=role,
                         citation_ref_version=_CITATION_REF_VERSION)
        bindings["citation_roles"][alias] = role
    def native_detection_covered(row):
        observations = row["summary"].get("marker_observations")
        if not isinstance(observations, list) or not observations:
            return set()
        measurements = {}
        prefix = "native_gene_detection_"
        for item in row["measurements"]:
            name = item.get("metric_name", "")
            if not isinstance(name, str) or not name.startswith(prefix):
                continue
            gene = name[len(prefix):]
            if (not gene or gene in measurements or item.get("source_alias") != row["alias"]
                    or item.get("measurement_class") != "gate_input_measurement"):
                return set()
            measurements[gene] = item
        if not measurements:
            return set()
        covered = set(measurements)
        for marker in observations:
            detected = marker.get("gene_detection")
            if (not isinstance(detected, dict)
                    or set(detected) != set(marker.get("positive_genes", [])) | set(marker.get("counter_genes", []))):
                return set()
            for gene, observation in detected.items():
                item = measurements.get(gene)
                if (item is None or observation.get("state") != "measured"
                        or item.get("numerator") != observation.get("count")
                        or item.get("denominator") != observation.get("denominator")
                        or item.get("unit") != "fraction"
                        or not isinstance(item.get("raw_value"), (int, float))
                        or not isinstance(item.get("denominator"), int)
                        or item["denominator"] <= 0
                        or not math.isclose(item["raw_value"], item["numerator"] / item["denominator"],
                                            rel_tol=0, abs_tol=1e-12)):
                    covered.discard(gene)
        return covered
    native_p005 = [row for row in evidence if row.get("state") == "available"
                   and row.get("tool_id") == "P0-05"
                   and row.get("summary", {}).get("runtime_mode") == "saved_cell_state_context"]
    result = []
    for row in evidence:
        projected = {"alias": opaque(row["alias"], "evidence")}
        projected.update({key: row[key] for key in (
            "state", "tool_id", "tool_version", "execution_state", "score_state",
            "domain_score", "reason_code", "interpretation_scope") if key in row})
        if row["state"] == "available":
            projected["summary"] = (_assessment_model_query(row["summary"], opaque)
                if "query_name" in row["summary"] else aggregate(row["summary"]))
            for source, public in zip(
                    row["summary"].get("records", []),
                    projected["summary"].get("records", [])):
                cite(public, source, row["alias"], "record", graph_record=True)
            if projected["summary"]:
                defaults = {}
                for group in ("claims", "requirements", "reconciliations", "records",
                              "composition", "primary_composition", "auxiliary_composition",
                              "whole_product_composition", "marker_observations", "program_summaries"):
                    items = projected["summary"].get(group, [])
                    if len(items) < 2:
                        continue
                    shared = {key: value for key, value in items[0].items()
                              if key not in {"alias", "claim_alias", "family_alias",
                                             "citation_alias", "citation_role"}
                              and all(key in item and item[key] == value for item in items)}
                    compact = [{key: value for key, value in item.items() if key not in shared}
                               for item in items]
                    if shared and len(json.dumps({"defaults": shared, "rows": compact})) < len(json.dumps(items)):
                        projected["summary"][group] = compact
                        defaults[group] = shared
                if defaults:
                    projected["summary"]["record_defaults"] = defaults
                    projected["summary"]["record_defaults_semantics"] = (
                        "Absent row fields inherit group defaults; explicit null overrides defaults.")
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
                cite(measurement, item, row["alias"], "measurement")
                projected["measurements"].append(measurement)
            if (row.get("tool_id") in {"P0-03", "P0-04"}
                    and row["summary"].get("runtime_mode") == "saved_cell_state_context"):
                omitted = {}
                for field in ("primary_composition", "auxiliary_composition", "whole_product_composition"):
                    for source in native_p005:
                        if (row["summary"].get(field)
                                and row["summary"][field] == source["summary"].get(field)):
                            projected["summary"].pop(field, None)
                            omitted[field] = opaque(source["alias"], "evidence")
                            break
                covered = native_detection_covered(row)
                if covered:
                    # Keep missing/unknown or mismatched detection rows literal;
                    # only identical measured values can use canonical citations.
                    covered_aliases = {opaque(gene) for gene in covered}
                    for marker in projected["summary"]["marker_observations"]:
                        remaining = {gene: value for gene, value in marker.get("gene_detection", {}).items()
                                     if gene not in covered_aliases}
                        if remaining:
                            marker["gene_detection"] = remaining
                        else:
                            marker.pop("gene_detection", None)
                    omitted["marker_observations.gene_detection"] = (
                        "canonical_measurements_with_measured_detection_state")
                if omitted:
                    projected["projection_omissions"] = omitted
            if projected["measurements"]:
                # The provider needs each value and citation, not 100 copies of
                # the same source and null interval metadata.
                common = ("measurement_class", "source_alias", "source_execution_state",
                          "score_state", "domain_score", "interval", "interval_confidence_level",
                          "unknown_scope", "citation_ref_version")
                if len(projected["measurements"]) > 1:
                    common += ("unit", "denominator", "numerator", "evidence_state", "citation_role")
                defaults = {key: projected["measurements"][0][key] for key in common
                            if all(key in item and item[key] == projected["measurements"][0][key]
                                   for item in projected["measurements"])}
                if defaults:
                    projected["measurement_defaults"] = defaults
                    projected["measurement_defaults_semantics"] = (
                        "Absent measurement fields inherit these defaults; explicit null overrides defaults.")
                    for measurement in projected["measurements"]:
                        for key in defaults:
                            measurement.pop(key)
                for measurement in projected["measurements"]:
                    if "citation_alias" in measurement:
                        measurement.pop("alias", None)
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
    pinned = {}
    for record in assessment.get("scope", {}).get("binding", {}).get("resources", {}).values():
        if record.get("source") == "tool_output":
            key = (record.get("receipt_file"), record.get("receipt_sha256"), record.get("producer_tool_id"))
            pinned.setdefault(key, []).append(record)
    receipts = inputs.evidence_sources(state).assessment_receipts(
        assessment.get("scope", {}).get("binding", {}).get("resources", {}),
        assessment["admissions"],
    )
    projected, bindings = [], {}
    for receipt in receipts:
        alias = "E-" + receipt["sha256"][:16]
        try:
            for record in pinned.get((receipt["file"], receipt["sha256"], receipt["tool_id"]), []):
                inputs.verify(state, record)
            raw = _verified_receipt(inputs, state, receipt)
            run = ToolRunV2.model_validate(raw) if "object_inputs" in raw["request"] else ToolRun.model_validate(raw)
            inputs.service.registry.validate_historical_result(run, run.request)
            root = inputs.service.directory(state["id"]) / "runs"
            for artifact in run.artifacts:
                verify_checked_file(
                    inputs.service,
                    state,
                    artifact.path,
                    artifact.sha256,
                    root=root,
                    limit=integrity_limit(inputs.service, artifact.path),
                )
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
                if (receipt["tool_id"] == "P0-06" and result.get("object_version") == "0.2.0"
                        and result.get("runtime_mode") == "exploratory_programs"):
                    result = _directed_program_summary(result)
                summary = (_assessment_query(result) if "query_name" in result else
                    _assessment_hard_count(result) if "accounting" in result and receipt["tool_id"] == "P0-05"
                    else _assessment_aggregate(result))
            # Browser navigation is separate from scientific snapshots and model
            # context so existing interpretation/report hashes remain stable.
            navigation = {"tool_run_ref": {"object_id": "tool-run:" + run.run_id, "object_version": run.tool_version},
                          "measurements": {}, "measurement_artifacts": {}, "graph_nodes": {}}
            if "query_name" in result:
                navigation["graph_nodes"] = {projected["alias"]: original["node_id"]
                    for original, projected in zip(result["nodes"], summary["nodes"])}
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
                navigation["measurements"]["M-" + artifact.sha256[:16]] = {
                    "object_id": item.measurement_id, "object_version": "0.2.0"}
                navigation["measurement_artifacts"]["M-" + artifact.sha256[:16]] = {
                    "object_id": artifact.artifact_id, "object_version": run.tool_version}
            if not canonical:
                for index, item in enumerate(raw.get("measurements", [])):
                    measurement_projection = {key: item[key] for key in (
                        "metric_name", "raw_value", "numerator", "denominator", "unit", "interval",
                        "interval_confidence_level", "unknown_scope", "evidence_state", "score_state",
                        "domain_score", "source_execution_state")
                        if key in item and (key != "raw_value" or item[key] is None
                                            or type(item[key]) in {int, float})}
                    token = hashlib.sha256(json.dumps(
                        {"index": index, "measurement": measurement_projection},
                        sort_keys=True, separators=(",", ":"),
                    ).encode()).hexdigest()[:16]
                    measurements.append({"alias": "M-" + token,
                        "measurement_class": "legacy_tool_measurement", **measurement_projection})
            artifact_ids, source, dependencies = _assessment_display_artifacts(inputs, state, run, receipt)
            row = {"alias": alias, "state": "available", "tool_id": receipt["tool_id"],
                "tool_version": run.tool_version, "execution_state": receipt["state"],
                "domain_score": None, "score_state": result.get("score_state", "unavailable"),
                "summary": summary, "measurements": measurements,
                "interpretation_scope": "exploratory" if result.get("runtime_mode") in {"exploratory_process", "exploratory_programs", "saved_cell_state_context"} else "registered_tool_result",
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
            # Native context includes per-gene observations plus independently
            # citable measurements. Keep this new mode bounded without dropping
            # real observations or expanding historical result limits.
            _check_summary_limit(row, limit=_assessment_result_limit(receipt["tool_id"], result))
            projected.append(row)
            bindings[alias] = {"receipt_file": receipt["file"], "receipt_sha256": receipt["sha256"],
                               "plan_id": receipt["plan_id"], "navigation": navigation}
        except _SummaryLimit:
            projected.append({"alias": alias, "state": "unavailable", "tool_id": receipt["tool_id"],
                              "reason_code": "result_summary_limit"})
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
