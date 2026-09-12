"""Allowlisted private context from confirmed scope and canonical producer receipts.

No paths, raw protocol text, model prompts, observation IDs or undeclared metadata
enter reports. The source input IDs returned alongside the object are dependencies
for the existing structured-input registry, not a second report storage layer.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from bridge.tool_packages.p0_10_claim_verifier.research import (
    ResearchReportContext, _check_context_graph, _read_graph, active_research_records,
    seal_research_context,
)
from .scientific_inputs import digest


def build_research_context(reports, state, scope, pool, *, graph_manifest_input_id: str
                           ) -> tuple[ResearchReportContext, list[str]]:
    """Freeze source-backed context; caller registers it as research_report_context."""
    inputs = reports.service.inputs
    if graph_manifest_input_id not in pool:
        raise ValueError("report_context_graph_outside_scope")
    graph_record = pool[graph_manifest_input_id]
    if graph_record.get("receipt_file") in state.get("_invalidated_receipts", {}):
        raise ValueError("report_context_source_invalidated")
    inputs.verify(state, graph_record)
    manifest, graph_sha, evidence, _ = _read_graph(Path(graph_record["path"]))
    if graph_sha != graph_record["sha256"]:
        raise ValueError("report_context_graph_checksum_mismatch")
    intake = scope.binding["intake"]
    if (state.get("_intakes", {}).get(scope.upload_id) != intake
            or state["_input_revision"] != scope.input_revision):
        raise ValueError("report_context_confirmed_intake_changed")
    current = active_research_records(manifest, evidence)
    records = {}
    for row in current:
        records.setdefault(row.measurement_result_ref.object_id, []).append(row)
    graph_runs = {row.tool_run_ref.object_id for row in current}
    dependencies = {graph_manifest_input_id}
    sources = {}
    def register(identifier, *, logical_ref=None):
        record = pool[identifier]
        if record.get("receipt_file") in state.get("_invalidated_receipts", {}):
            raise ValueError("report_context_source_invalidated")
        inputs.verify(state, record)
        dependencies.add(identifier)
        ref = logical_ref or "input:" + identifier + "@" + record["object_version"]
        source = {"source_ref": ref, "sha256": record["sha256"], "schema_ref": record["schema_ref"],
                  "receipt_sha256": record.get("receipt_sha256")}
        if ref in sources and sources[ref] != source:
            raise ValueError("report_context_source_identity_conflict")
        sources[ref] = source
        return ref

    def profile_sources(tool_id, schema):
        found = []
        for identifier, value, run in reports._canonical_outputs(state, pool, tool_id, schema):
            if "tool-run:" + run.run_id not in graph_runs:
                continue
            if value != run.result:
                raise ValueError("report_context_profile_receipt_mismatch")
            register(identifier)
            found.append((identifier, value, run))
        return found

    candidates = profile_sources("P0-02", "bridge://schemas/cell-state-candidate-profile/v1.0")
    processes = profile_sources("P0-06", "bridge://schemas/exploratory-process-profile/v0.1")
    observed_views = [value["input_data_view"] for _, value, _ in candidates]
    observed_views.extend(value["input_contract"]["data_view"] for _, value, _ in processes)
    view = scope.binding.get("data_view") or (observed_views[0] if observed_views else None)
    if (view is None or any(value != view for value in observed_views)
            or view["parent_asset_id"] != scope.upload_id
            or view["parent_asset_sha256"] != scope.binding["upload"]["sha256"]):
        raise ValueError("report_context_data_view_mismatch")
    # Read the exact view-producing QC receipt, not a shape-compatible upload.
    qcs = [(identifier, value, run) for identifier, value, run in reports._canonical_outputs(
        state, pool, "P0-01", "bridge://schemas/qc-readiness-profile/v0.2")
        if value.get("selected_data_view") == view]
    if len(qcs) != 1:
        raise ValueError("report_context_qc_source_ambiguous")
    qc_id, _, _ = qcs[0]
    data_view_source_ref = register(qc_id)
    intake_ref = "confirmed-intake:" + scope.upload_id + "@" + str(scope.input_revision)
    sources[intake_ref] = {"source_ref": intake_ref, "sha256": digest(intake),
                          "schema_ref": "bridge://schemas/confirmed-intake/v0.1"}
    register(graph_manifest_input_id)

    def measurements(identifier, run):
        profile_record = pool[identifier]
        outputs = {}
        canonical = {row.measurement_id: row.model_dump(mode="json") for row in run.measurements}
        for key, record in pool.items():
            if (record.get("receipt_file") != profile_record["receipt_file"]
                    or record.get("receipt_sha256") != profile_record["receipt_sha256"]
                    or record["schema_ref"] != "bridge://schemas/measurement-result/v0.2"):
                continue
            value = inputs.verify(state, record)
            original = canonical.get(value["measurement_id"])
            if (original is None or any(value.get(k) != item for k, item in original.items())
                    or value["source_run_ref"] != "tool-run:" + run.run_id + "@" + run.tool_version):
                raise ValueError("report_context_measurement_receipt_mismatch")
            attached = records.get(value["measurement_id"], [])
            if not attached:
                continue
            if any(row.metric_id != value["metric_name"] or row.value != value["raw_value"]
                   or row.unit != value["unit"] or row.numerator != value.get("numerator")
                   or row.denominator != value.get("denominator")
                   or row.tool_run_ref.ref != value["source_run_ref"] for row in attached):
                raise ValueError("report_context_measurement_graph_mismatch")
            if value["metric_name"] in outputs:
                raise ValueError("report_context_metric_ambiguous")
            register(key)
            outputs[value["metric_name"]] = (value, attached[0].measurement_result_ref.ref)
        return outputs

    developments, composition, means = [], [], []
    for identifier, value, run in candidates:
        source_ref = register(identifier)
        developments.append({"source_ref": source_ref, "producer_run_ref": "tool-run:" + run.run_id + "@" + run.tool_version,
            **{key: value[key] for key in ("development_gate_state", "development_reason_codes",
                "development_summary_sha256", "development_review_version", "development_review_sha256",
                "scientific_qualification")}})
        measured = measurements(identifier, run)
        for row in value["candidate_composition"]:
            token = digest({key: row[key] for key in ("label", "assignment_state")})[:16]
            metric = "candidate_composition_fraction_" + token
            if metric not in measured:
                raise ValueError("report_context_composition_measurement_missing")
            canonical, measurement_ref = measured[metric]
            if (canonical["raw_value"] != row["fraction"] or canonical["numerator"] != row["count"]
                    or canonical["denominator"] != row["denominator"]):
                raise ValueError("report_context_composition_source_mismatch")
            composition.append({"source_ref": source_ref, "measurement_ref": measurement_ref, "metric_id": metric,
                **{key: row[key] for key in ("label", "assignment_state", "count", "denominator", "fraction")}})

    for identifier, value, run in processes:
        source_ref = register(identifier)
        measured = measurements(identifier, run)
        for row in value["program_summaries"]:
            metric = "native_mean_" + row["method_id"].lower().replace("-", "_") + "_" + row["program_id"].lower()
            if metric not in measured:
                raise ValueError("report_context_process_measurement_missing")
            canonical, measurement_ref = measured[metric]
            if canonical["raw_value"] != row["mean"] or canonical["unit"] != row["score_unit"]:
                raise ValueError("report_context_process_source_mismatch")
            means.append({"source_ref": source_ref, "measurement_ref": measurement_ref, "metric_id": metric,
                **{key: row[key] for key in ("method_id", "program_id", "mean", "score_unit",
                    "n_observations", "assessment_state", "reason_codes")}})

    native_runs = {row.tool_run_ref.object_id for row in current
                   if row.metric_id.startswith(("candidate_composition_fraction_", "native_mean_"))}
    if not native_runs <= {"tool-run:" + run.run_id for _, _, run in [*candidates, *processes]}:
        raise ValueError("report_context_native_profile_missing")
    versions = []
    seen = set()
    for assessment in [*state.get("_assessment_history", []), state.get("_assessment") or {}]:
        previous_scope = assessment.get("scope", {})
        if (previous_scope.get("upload_id") != scope.upload_id
                or previous_scope.get("input_revision", -1) > scope.input_revision):
            continue
        for row in assessment.get("interpretation_versions", []):
            identity = (row["scope_digest"], row["version"])
            if identity in seen:
                raise ValueError("report_context_explanation_history_duplicate")
            seen.add(identity)
            versions.append(deepcopy(row))
    payload = {
        "context_id": "research-context:" + digest([graph_sha, str(scope.input_revision), digest(intake), versions])[:24],
        "input_revision": str(scope.input_revision), "graph_id": manifest.graph_id,
        "graph_version": manifest.graph_version, "graph_manifest_sha256": graph_sha,
        "product_case_ref": manifest.product_case_ref.model_dump(mode="json"),
        "confirmed_product_facts": deepcopy(intake["facts"]), "intake_source_ref": intake_ref,
        "data_view": deepcopy(view), "data_view_source_ref": data_view_source_ref,
        "sources": [sources[key] for key in sorted(sources)], "explanation_versions": versions,
        "candidate_development": developments, "composition_mapping": composition, "process_means": means,
    }
    context = seal_research_context(payload)
    _check_context_graph(context, manifest, graph_sha, str(scope.input_revision), evidence)
    return context, sorted(dependencies)
