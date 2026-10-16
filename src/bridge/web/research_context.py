"""Allowlisted private context from confirmed scope and canonical producer receipts.

No paths, raw protocol text, model prompts, observation IDs or undeclared metadata
enter reports. The source input IDs returned alongside the object are dependencies
for the existing structured-input registry, not a second report storage layer.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from bridge.tool_packages.p0_09_evidence_compiler.graph import read_parquet_bytes
from bridge.tool_packages.p0_10_claim_verifier.research import (
    ResearchReportContext, _check_context_graph, _read_graph, active_research_records,
    seal_research_context,
)
from .scientific_inputs import digest
from .evidence_sources import producer_identity

EXPRESSION_PLOT_LIMIT = 24_000_000


def selected_report_context_key(state, scope, graph_sha256: str) -> str:
    """Bind a selected draft to current-scope interpretation history as well as graph."""
    assessment = state.get("_assessment") or {}
    versions = (assessment.get("interpretation_versions", [])
        if assessment.get("scope", {}).get("scope_id") == scope.scope_id else [])
    return digest([scope.scope_id, scope.input_revision, graph_sha256, versions])


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
    manifest, graph_sha, evidence, backing = _read_graph(Path(graph_record["path"]))
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
    nodes, _ = read_parquet_bytes(backing["graph_nodes"], backing["graph_edges"])
    producer_identities = {(row.object_id, row.object_version, row.content_hash)
                           for row in nodes if row.node_type.value == "ToolRun"}
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

    mismatched_runs = set()
    def profile_sources(tool_id, schema):
        found = []
        for identifier, value, run in reports._canonical_outputs(state, pool, tool_id, schema):
            run_ref = ("tool-run:" + run.run_id, run.tool_version)
            if run_ref[0] not in graph_runs:
                continue
            # Older versions reused a run ID across execution attempts. Resolve
            # the exact immutable producer compiled into this graph, never the
            # newest receipt that happens to share its name.
            if producer_identity(run) not in producer_identities:
                mismatched_runs.add(run_ref[0])
                continue
            if value != run.result:
                raise ValueError("report_context_profile_receipt_mismatch")
            register(identifier)
            found.append((identifier, value, run))
        return found

    candidates = profile_sources("P0-02", "bridge://schemas/cell-state-candidate-profile/v1.0")
    # Cycle and source-bound program profiles share the native mean contract.
    # Each remains tied to its own producer, data view and graph measurements.
    processes = profile_sources("P0-06", (
        "bridge://schemas/exploratory-process-profile/v0.1",
        "bridge://schemas/exploratory-program-profile/v0.1",
        "bridge://schemas/exploratory-program-profile/v0.2",
    ))
    native_runs = {row.tool_run_ref.object_id for row in current
                   if row.metric_id.startswith(("candidate_composition_fraction_", "native_mean_"))}
    matched_runs = {"tool-run:" + run.run_id for _, _, run in [*candidates, *processes]}
    if (native_runs - matched_runs) & mismatched_runs:
        # Only report a loss when no exact producer remains. A historical
        # collision alongside the exact receipt is expected and not degradation.
        raise ValueError("report_context_producer_identity_mismatch")
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


    developments, composition, means = [], [], []
    for identifier, value, run in candidates:
        source_ref = register(identifier)
        developments.append({"source_ref": source_ref, "producer_run_ref": "tool-run:" + run.run_id + "@" + run.tool_version,
            **{key: value[key] for key in ("development_gate_state", "development_reason_codes",
                "development_summary_sha256", "development_review_version", "development_review_sha256",
                "scientific_qualification")}})
        measured = _graph_measurements(inputs, state, pool, records, identifier, run, register)
        composition.extend(_composition_mapping(value, measured, source_ref))

    for identifier, value, run in processes:
        source_ref = register(identifier)
        measured = _graph_measurements(inputs, state, pool, records, identifier, run, register)
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

    if not native_runs <= matched_runs:
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
    if any(row["object_version"] == "1.1.0" for row in versions):
        payload["object_version"] = "0.4.0"
    if any(row["object_version"] == "1.2.0" for row in versions):
        payload["object_version"] = "0.5.0"
    context = seal_research_context(payload)
    _check_context_graph(context, manifest, graph_sha, str(scope.input_revision), evidence)
    return context, sorted(dependencies)


def _graph_measurements(inputs, state, pool, records, identifier, run, register):
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
        if any(row.measurement_result_ref.object_version != record["object_version"]
               or row.metric_id != value["metric_name"] or row.value != value["raw_value"]
               or row.unit != value["unit"] or row.numerator != value.get("numerator")
               or row.denominator != value.get("denominator")
               or row.tool_run_ref.ref != value["source_run_ref"] for row in attached):
            raise ValueError("report_context_measurement_graph_mismatch")
        if value["metric_name"] in outputs:
            raise ValueError("report_context_metric_ambiguous")
        register(key)
        outputs[value["metric_name"]] = (value, attached[0].measurement_result_ref.ref)
    return outputs


def _composition_mapping(profile, measured, source_ref):
    """Validate the existing producer mapping; never derive a category from a hash."""
    from bridge.tool_packages.p0_10_claim_verifier.research import ResearchCompositionMapping
    composition = []
    for row in profile["candidate_composition"]:
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

    return [ResearchCompositionMapping.model_validate(row).model_dump(mode="json") for row in composition]


def graph_composition_display(service, state, aid, display):
    """Read names for one saved graph; no current report scope or state writes."""
    from .inputs import checked_bytes, strict_json
    from bridge.tool_packages.p0_10_claim_verifier.research import _safe_content

    inputs, pool = service.inputs, state.get("_input_objects", {})
    binding = state.get("_canonical_artifacts", {}).get(aid)
    exposed = state["_artifacts"][aid]
    if (not binding or exposed.get("source_artifact_id") != binding["artifact_id"]
            or exposed.get("source_sha256") != binding["sha256"]):
        raise ValueError("graph_display_source_mismatch")
    artifacts = inputs.receipt_artifacts(state, binding)
    source = artifacts[binding["artifact_id"]]
    if source["kind"] != "cytoscape_elements":
        raise ValueError("graph_display_source_kind_mismatch")
    receipts = [row for row in state.get("_tool_runs", [])
                if row["file"] == binding["receipt_file"] and row["sha256"] == binding["receipt_sha256"]]
    if len(receipts) != 1 or receipts[0]["tool_id"] != "P0-09":
        raise ValueError("graph_display_receipt_ambiguous")
    canonical = strict_json(checked_bytes(service, state, binding["path"], binding["sha256"]))
    manifest_records = [row for row in pool.values()
        if row.get("source") == "tool_output" and row.get("producer_tool_id") == "P0-09"
        and row.get("receipt_file") == binding["receipt_file"]
        and row.get("receipt_sha256") == binding["receipt_sha256"]
        and row.get("schema_ref") == "bridge://schemas/case-evidence-graph-manifest/v0.1"]
    if len(manifest_records) != 1:
        raise ValueError("graph_display_manifest_ambiguous")
    graph_record = manifest_records[0]
    inputs.verify(state, graph_record)
    manifest, graph_sha, evidence, _ = _read_graph(Path(graph_record["path"]))
    if (graph_sha != graph_record["sha256"] or any(
            value.get("graph_id") != manifest.graph_id or value.get("graph_version") != manifest.graph_version
            for value in (display, canonical))):
        raise ValueError("graph_display_manifest_mismatch")
    records = {}
    for row in evidence.records:
        if row.metric_id.startswith("candidate_composition_fraction_"):
            records.setdefault(row.measurement_result_ref.object_id, []).append(row)
    selected = {key: row for key, row in pool.items()
        if row.get("schema_ref") == "bridge://schemas/cell-state-candidate-profile/v1.0"
        and any(ref.object_id == row.get("artifact_id") for rows in records.values()
                for record in rows for ref in record.artifact_refs)}
    sources, composition = {}, []
    def register(identifier):
        record = pool[identifier]
        inputs.verify(state, record)
        ref = "input:" + identifier + "@" + record["object_version"]
        sources[ref] = {"source_ref": ref, "schema_ref": record["schema_ref"],
                        "sha256": record["sha256"], "receipt_sha256": record["receipt_sha256"]}
        return ref
    for identifier, profile, run in service.report_inputs._canonical_outputs(
            state, selected, "P0-02", "bridge://schemas/cell-state-candidate-profile/v1.0"):
        if (profile != run.result or profile["producer_run_ref"] != run.run_id
                or profile["producer_tool_version"] != run.tool_version
                or profile["input_sha256"] != run.input_hash):
            raise ValueError("graph_display_profile_mismatch")
        artifact_ref = pool[identifier]["artifact_id"] + "@" + run.tool_version
        attached = {key: rows for key, rows in records.items()
                    if any(row.tool_run_ref.ref == "tool-run:" + run.run_id + "@" + run.tool_version for row in rows)}
        if any(artifact_ref not in {ref.ref for ref in row.artifact_refs}
               for rows in attached.values() for row in rows):
            raise ValueError("graph_display_profile_binding_mismatch")
        source_ref = register(identifier)
        measured = _graph_measurements(inputs, state, pool, attached, identifier, run, register)
        composition.extend(_composition_mapping(profile, measured, source_ref))
    refs = [row["measurement_ref"] for row in composition]
    expected = {row.measurement_result_ref.ref for rows in records.values() for row in rows}
    if len(refs) != len(set(refs)) or set(refs) != expected:
        raise ValueError("graph_display_composition_ambiguous_or_missing")
    payload = {"graph_id": manifest.graph_id, "graph_version": manifest.graph_version,
        "graph_manifest_sha256": graph_sha, "composition_mapping": composition,
        "sources": [sources[key] for key in sorted(sources)]}
    _safe_content(payload)
    return payload


def resolve_display_source(service, state, aid, *, payload_limit=None):
    """Resolve a display ID only through its immutable producer registration."""
    from .inputs import OBJECT_LIMIT, checked_bytes, strict_json
    binding = state.get("_canonical_artifacts", {}).get(aid)
    exposed = state["_artifacts"][aid]
    if (not binding or exposed.get("source_artifact_id") != binding["artifact_id"]
            or exposed.get("source_sha256") != binding["sha256"]):
        raise ValueError("figure_source_mismatch")
    artifacts = service.inputs.receipt_artifacts(state, binding)
    receipts = [row for row in state.get("_tool_runs", [])
                if row["file"] == binding["receipt_file"] and row["sha256"] == binding["receipt_sha256"]]
    if len(receipts) != 1:
        raise ValueError("figure_receipt_ambiguous")
    receipt = strict_json(checked_bytes(service, state,
        service.directory(state["id"]) / "receipts" / binding["receipt_file"], binding["receipt_sha256"]))
    limit = OBJECT_LIMIT if payload_limit is None else payload_limit
    payload = strict_json(checked_bytes(service, state, binding["path"], binding["sha256"], limit=limit), limit)
    return binding, artifacts, receipt, payload


def typed_figure_display(service, state, aid):
    """Bind existing package renders and tables; never run a renderer on read."""
    import re
    from .inputs import checked_bytes, strict_json
    from bridge.toolkit.visualization import FigureRegistry, VisualizationArtifactV2
    from bridge.tool_packages.p0_10_claim_verifier.research import _safe_content
    binding, artifacts, receipt, payload = resolve_display_source(service, state, aid)
    if (payload.get("schema_ref") != "bridge://schemas/p0-02-visualization-artifact-set/v0.2" and not re.fullmatch(r"bridge://schemas/p0-(?:0[1-9]|1[0-2])-visualization-artifact-set/v0\.1", payload.get("schema_ref", ""))
            or artifacts[binding["artifact_id"]]["kind"] != "visualization_artifact_set"):
        raise ValueError("typed_figure_set_required")
    service.inputs.validate_object(payload, payload["schema_ref"], payload["object_version"])
    render_media = {"image/svg+xml", "image/png"}
    if payload["schema_ref"] == "bridge://schemas/p0-02-visualization-artifact-set/v0.2":
        render_media.add("application/pdf")
    registry = FigureRegistry.load_default()
    public = service.artifacts.public(state)
    def registered(source_id, media_type=None):
        source = artifacts.get(source_id)
        if source is None:
            raise ValueError("figure_artifact_missing")
        matches = []
        for item in public:
            canonical = state.get("_canonical_artifacts", {}).get(item["id"], {})
            exposed = state["_artifacts"][item["id"]]
            if (canonical.get("artifact_id") == source_id
                    and all(canonical.get(key) == binding[key] for key in ("receipt_file", "receipt_sha256"))
                    and canonical.get("sha256") == source["sha256"]
                    and exposed.get("source_artifact_id") == source_id
                    and exposed.get("source_sha256") == source["sha256"]
                    and not (item.get("acknowledgement_required") and not item.get("acknowledged"))
                    and (media_type is None or item["media_type"] == media_type)):
                matches.append(item)
        if len(matches) != 1:
            raise ValueError("figure_display_binding_ambiguous_or_missing")
        return matches[0]
    figures = []
    for value in payload["visualizations"]:
        view = VisualizationArtifactV2.model_validate(value)
        registry.validate_artifact(view)
        if (view.producer_run_ref != "run:" + receipt["run_id"]
                or view.producer_tool_id != receipt["request"]["tool_id"]
                or view.producer_tool_version != receipt["tool_version"]):
            raise ValueError("figure_producer_mismatch")
        data = artifacts.get(view.data_binding.artifact_id)
        if data is None or data["sha256"] != view.data_binding.sha256:
            raise ValueError("figure_data_hash_mismatch")
        typed = strict_json(checked_bytes(service, state, data["path"], data["sha256"]), EXPRESSION_PLOT_LIMIT)
        service.inputs.validate_object(typed, view.data_binding.schema_ref, view.data_binding.object_version)
        renders = [registered(item.artifact_id, item.media_type) for item in view.renders
                   if item.media_type in render_media]
        display_contract = view.model_dump(mode="json")
        if view.producer_tool_id == "P0-01":
            from .qc_results import qc_reading_note
            # A read-only explanation of this exact receipt, including historical runs.
            # The original contract, download and all data/render hashes stay intact.
            display_contract["accessibility"]["long_description"] = (
                qc_reading_note(receipt) + "\n" + view.accessibility.long_description
            )
        figures.append({"contract": display_contract, "renders": renders,
            "table": registered(view.accessibility.table_artifact_id),
            "data": registered(view.data_binding.artifact_id, "application/json")})
    result = {"kind": "typed_figures", "producer_run_ref": "run:" + receipt["run_id"],
        "source_receipt_sha256": binding["receipt_sha256"], "set_sha256": binding["sha256"], "figures": figures}
    _safe_content([figure["contract"] for figure in figures])
    return result



def expression_plot_display(service, state, aid):
    """Project only display fields from a checksum-verified expression artifact."""
    from bridge.tool_packages.p0_02_cell_state.expression_figures import ExpressionPlotData
    from .sessions import private_text
    binding, artifacts, receipt, payload = resolve_display_source(service, state, aid, payload_limit=EXPRESSION_PLOT_LIMIT)
    if (artifacts[binding["artifact_id"]]["kind"] != "expression_plot_data"
            or receipt["request"]["tool_id"] != "P0-02"
            or receipt["request"]["measurement_spec_ref"] != "EXPRESSION-exploration-v0.1"):
        raise ValueError("expression_plot_source_required")
    data = ExpressionPlotData.model_validate(payload)
    if data.kind != "umap":
        raise ValueError("umap_plot_required")
    return {"schema_ref": data.schema_ref, "kind": data.kind, "n_observations": data.n_observations,
        "records": [{"record_id": p.record_id, "x": p.x, "y": p.y, "group": private_text(p.group or "")}
                    for p in data.records],
        "colors": {private_text(key): [private_text(v) if isinstance(v, str) else v for v in values]
                   for key, values in data.colors.items()},
        "composition": [{**row, "group": private_text(str(row["group"]))} for row in data.composition],
        "missing_genes": [private_text(gene) for gene in data.missing_genes]}


def reference_similarity_display(service, state, aid):
    """Project saved native coefficients with exact spec keys and source labels."""
    from .inputs import checked_bytes, strict_json
    from bridge.toolkit.contracts import MeasurementResultV2
    from bridge.tool_packages.p0_10_claim_verifier.research import _safe_content
    binding, artifacts, receipt, spec = resolve_display_source(service, state, aid)
    if receipt["request"]["tool_id"] != "P0-03":
        raise ValueError("reference_similarity_producer_required")
    service.inputs.validate_object(spec, "bridge://schemas/measurement-spec/v0.3", spec["version"])
    definitions = spec["raw_metric_definition"]
    if (not definitions or spec["status"] != "descriptive_only"
            or any(not isinstance(row, dict) or row.get("native_field") not in {"spearman", "cosine"}
                   for row in definitions.values())):
        raise ValueError("reference_similarity_definition_required")
    result_artifacts = [a for a in artifacts.values() if a["kind"] == "reference_similarity_exploratory_result"]
    if len(result_artifacts) != 1:
        raise ValueError("reference_similarity_result_ambiguous")
    original = result_artifacts[0]
    result = strict_json(checked_bytes(service, state, original["path"], original["sha256"]))
    if (result != receipt["result"] or result["data_view"] != spec["data_view"]
            or result["reference_manifest_ref"] != spec["input_contract"]["reference_manifest_ref"]
            or result["reference_manifest_sha256"] != spec["input_contract"]["reference_manifest_sha256"]):
        raise ValueError("reference_similarity_result_mismatch")
    rows, seen = [], set()
    for artifact in artifacts.values():
        if not (Path(artifact["path"]).name.startswith("native_measurement_")
                and Path(artifact["path"]).name != "native_measurement_spec.json"
                and Path(artifact["path"]).suffix == ".json"):
            continue
        value = MeasurementResultV2.model_validate(strict_json(checked_bytes(
            service, state, artifact["path"], artifact["sha256"])))
        definition = definitions.get(value.metric_name)
        if (definition is None or value.metric_name in seen
                or value.measurement_spec_id != spec["measurement_spec_id"]
                or value.measurement_spec_version != spec["version"]
                or value.source_run_ref != "tool-run:" + receipt["run_id"] + "@" + receipt["tool_version"]
                or value.source_execution_state != receipt["execution_state"]
                or value.unit != "similarity_coefficient" or value.domain_score is not None):
            raise ValueError("reference_similarity_measurement_mismatch")
        native = [row for row in result["measurements"] if row["measurement_id"] == definition["native_measurement_id"]]
        if (len(native) != 1 or native[0].get(definition["native_field"]) != value.raw_value
                or any(native[0].get(key) != definition[key] for key in
                       ("profile_id", "source_id", "source_family_id", "label", "label_level",
                        "shared_genes", "query_gene_fraction", "reference_gene_fraction"))):
            raise ValueError("reference_similarity_label_binding_mismatch")
        seen.add(value.metric_name)
        rows.append({"measurement": value.model_dump(mode="json"), "definition": definition,
                     "measurement_sha256": artifact["sha256"]})
    if seen != set(definitions):
        raise ValueError("reference_similarity_measurement_missing")
    projection = {"kind": "reference_similarity", "spec_id": spec["measurement_spec_id"],
        "spec_version": spec["version"], "spec_sha256": binding["sha256"],
        "source_receipt_sha256": binding["receipt_sha256"], "source": spec["input_contract"],
        "reference_manifest_ref": result["reference_manifest_ref"],
        "n_observations": result["n_observations"], "rows": rows}
    _safe_content(projection)
    return projection
