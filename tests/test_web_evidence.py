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
from bridge.web.app import Settings
from account_support import create_test_app as create_app
from bridge.web.sessions import write_file
from bridge.web.evidence import build_result_context
from web_support import client, declare_counts, h5ad, new_session, settle



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


@pytest.mark.parametrize("mode", ["reference_similarity_exploratory", "saved_reference_similarity_projection"])
def test_portrait_links_reference_context_without_promoting_identity(mode):
    from bridge.web.evidence import assessment_portrait

    evidence = [{"alias": "E-reference", "tool_id": "P0-03", "state": "available",
                 "summary": {"runtime_mode": mode, "similarity": 0.75},
                 "provenance": {"receipt_sha256": "reference", "plan_id": "current"}}]
    modes = {"reference": mode}
    axes = assessment_portrait(evidence, [], modes_by_receipt=modes)
    for axis in axes[1:3]:
        assert axis["context_evidence_aliases"] == ["E-reference"]
        assert axis["evidence_aliases"] == []
        assert axis["state"] == "missing"
        assert axis["summary"] == {"channels": []}

    evidence.append({"alias": "E-invalid", "tool_id": "P0-03", "state": "unavailable",
                     "reason_code": "canonical_result_invalid",
                     "provenance": {"receipt_sha256": "invalid", "plan_id": "current"}})
    modes["invalid"] = mode
    axes = assessment_portrait(evidence, [], modes_by_receipt=modes,
                              order_by_receipt={"reference": 0, "invalid": 1})
    assert all(axis["context_evidence_aliases"] == [] for axis in axes[1:3])


def test_assessment_portrait_prefers_current_receipt_without_conflating_process_modes():
    from bridge.web.evidence import assessment_portrait
    evidence = [
        {"alias": "E-current-cell", "tool_id": "P0-02", "mode_id": None,
         "state": "available", "summary": {"n_observations": 9},
         "provenance": {"plan_id": "current"}},
        {"alias": "E-current-process", "tool_id": "P0-06", "mode_id": "method_runtime_source_bound",
         "state": "available", "summary": {"runtime_mode": "method_runtime_source_bound",
             "program_results": [{"program_id": "current-program"}]},
         "provenance": {"plan_id": "current"}},
        {"alias": "E-current-cycle", "tool_id": "P0-06", "mode_id": "exploratory_process",
         "state": "available", "summary": {"runtime_mode": "exploratory_process",
             "cell_cycle": {"assessment_state": "available", "n_observations": 9,
                            "reason_codes": [], "s_g2m_fraction": 0.5}},
         "provenance": {"plan_id": "current"}},
        {"alias": "E-reused-cell", "tool_id": "P0-02", "mode_id": None,
         "state": "available", "summary": {"n_observations": 4},
         "provenance": {"plan_id": "historical"}},
        {"alias": "E-reused-cycle", "tool_id": "P0-06", "mode_id": "exploratory_process",
         "state": "available", "summary": {"runtime_mode": "exploratory_process",
             "cell_cycle": {"assessment_state": "available", "n_observations": 4,
                            "reason_codes": [], "s_g2m_fraction": 0.25}},
         "provenance": {"plan_id": "historical"}},
    ]
    axes = {row["id"]: row for row in assessment_portrait(
        evidence, [], current_plan_ids={"current"})}
    assert axes["cell_state"]["evidence_aliases"] == ["E-current-cell"]
    assert axes["cell_state"]["summary"]["n_observations"] == 9
    assert axes["process"]["evidence_aliases"] == ["E-current-process"]
    assert axes["process"]["summary"]["program_results"][0]["program_id"] == "current-program"
    cycle = next(row for row in axes["process"]["families"] if row["id"] == "cell_cycle")
    assert cycle["evidence_aliases"] == ["E-current-cycle"]
    assert cycle["summary"]["n_observations"] == 9


def test_assessment_portrait_keeps_current_unavailable_and_uses_receipt_order():
    from bridge.web.evidence import assessment_portrait
    evidence = [
        {"alias": "E-new", "tool_id": "P0-06", "state": "unavailable",
         "reason_code": "output_not_readable", "provenance": {"plan_id": "current", "receipt_sha256": "new"}},
        {"alias": "E-old", "tool_id": "P0-06", "state": "available",
         "summary": {"runtime_mode": "exploratory_process", "cell_cycle": {
             "assessment_state": "available", "n_observations": 4,
             "reason_codes": [], "s_g2m_fraction": 0.25}},
         "provenance": {"plan_id": "historical", "receipt_sha256": "old"}},
        {"alias": "E-earlier-current", "tool_id": "P0-06", "state": "available",
         "summary": {"runtime_mode": "exploratory_process", "cell_cycle": {
             "assessment_state": "available", "n_observations": 9,
             "reason_codes": [], "s_g2m_fraction": 0.5}},
         "provenance": {"plan_id": "current", "receipt_sha256": "earlier"}},
    ]
    axes = assessment_portrait(evidence, [], current_plan_ids={"current"},
        modes_by_receipt={"new": "exploratory_process", "old": "exploratory_process",
                          "earlier": "exploratory_process"},
        order_by_receipt={"old": 0, "earlier": 1, "new": 2})
    process = axes[-1]
    cycle = next(row for row in process["families"] if row["id"] == "cell_cycle")
    assert process["state"] == "unavailable" and process["evidence_aliases"] == ["E-new"]
    assert cycle["state"] == "unavailable" and cycle["summary"] == {}
    assert cycle["reason_codes"] == ["output_not_readable"]
    assert cycle["evidence_aliases"] == ["E-new"]


def test_directed_source_projection_keeps_all_program_families_and_nulls():
    from bridge.web.evidence import _assessment_aggregate, _directed_program_summary, assessment_portrait

    directed = _assessment_aggregate(_directed_program_summary({
        "runtime_mode": "exploratory_programs", "object_version": "0.2.0",
        "program_summaries": [{"source_gene_set": "OFLANAGAN-2019-CORE",
            "method_id": "PROC-SCORE-SCANPY", "assessment_state": "not_assessed",
            "mean": None, "reason_codes": ["scanpy_signed_signature_not_supported"],
            "direction_definition": "sign_of_source_logFC",
            "unresolved_members": [{"source_member_id": "private-member"}]},
            {"source_gene_set": "OFLANAGAN-2019-CORE", "method_id": "PROC-SCORE-DECOUPLER",
             "assessment_state": "available", "mean": 0.25, "reason_codes": [],
             "direction_definition": "sign_of_source_logFC",
             "unresolved_members": [{"source_member_id": "private-member"}]}]}))
    assert all(row["unresolved_member_count"] == 1 for row in directed["program_summaries"])
    assert all("unresolved_members" not in row for row in directed["program_summaries"])
    assert directed["program_summaries"][0]["mean"] is None
    sources = [("E-cycle", "exploratory_process", {"cell_cycle": {
        "assessment_state": "available", "reason_codes": [], "n_observations": 12}}),
        ("E-hallmark", "exploratory_programs", {"program_summaries": [
            {"source_gene_set": source, "assessment_state": "available", "reason_codes": []}
            for source in ("HALLMARK_REACTIVE_OXYGEN_SPECIES_PATHWAY",
                           "HALLMARK_UNFOLDED_PROTEIN_RESPONSE", "HALLMARK_APOPTOSIS",
                           "HALLMARK_HYPOXIA")]}),
        ("E-pluri", "exploratory_programs", {"program_summaries": [
            {"source_gene_set": "HU-2020-TABLE-S1", "assessment_state": "available", "reason_codes": []}]}),
        ("E-dissoc", "exploratory_programs", directed)]
    evidence = [{"alias": alias, "tool_id": "P0-06", "state": "available",
                 "summary": {"runtime_mode": mode, **summary},
                 "provenance": {"receipt_sha256": alias, "plan_id": alias}}
                for alias, mode, summary in sources]
    families = assessment_portrait(evidence, [], order_by_receipt={alias: index
        for index, (alias, _, _) in enumerate(sources)})[-1]["families"]
    by_id = {row["id"]: row for row in families}
    assert by_id["cell_cycle"]["evidence_aliases"] == ["E-cycle"]
    assert by_id["pluripotency_like"]["evidence_aliases"] == ["E-pluri"]
    assert by_id["dissociation_heat_shock"]["evidence_aliases"] == ["E-dissoc"]
    for family in ("oxidative_stress", "unfolded_protein_response", "apoptosis_related", "hypoxia"):
        assert by_id[family]["evidence_aliases"] == ["E-hallmark"]


def test_cancelled_directed_admission_without_receipt_is_not_automatically_reselected():
    from bridge.web.scientific_inputs import _admitted_directed_inputs

    source = "a" * 32
    roots = {source: {"sha256": "b" * 64,
                      "schema_ref": "bridge://schemas/exploratory-process-input/v0.3"}}
    request = {"tool_id": "P0-06", "tool_version": "0.11.0", "object_inputs": [{
        "role": "directed_program_input", "input_id": source, "sha256": "b" * 64,
        "schema_ref": roots[source]["schema_ref"]}]}
    state = {"_assessment_history": [{"admissions": [{"plan_id": "plan-1", "tool_id": "P0-06",
        "mode_id": "directed_programs", "state": "cancelled"}]}],
        "_plan_history": [{"plan": {"plan_id": "plan-1", "status": "cancelled",
            "steps": [{"tool_id": "P0-06", "approved_request_json": json.dumps(request)}]}}],
        "_tool_runs": []}
    assert _admitted_directed_inputs(state, roots, "0.11.0") == {source}
    assert _admitted_directed_inputs(state, roots, "0.12.0") == set()


def test_directed_scope_keeps_approved_source_with_more_than_one_tool_run():
    from types import SimpleNamespace
    from bridge.web.inputs import Selection
    from bridge.web.scientific_inputs import ScientificInputs

    first, second = "a" * 32, "b" * 32
    schema = "bridge://schemas/exploratory-process-input/v0.3"
    records = {key: {"schema_ref": schema, "sha256": key * 2} for key in (first, second)}
    payloads = {first: {"data_view": {"view_id": "same-view"},
                        "programs": [{"source_gene_set": "HU-2020-TABLE-S1"}]},
                second: {"data_view": {"view_id": "same-view"},
                         "programs": [{"source_gene_set": "OFLANAGAN-2019-CORE"}]}}
    service = SimpleNamespace(inputs=SimpleNamespace(verify=lambda state, record:
        payloads[next(key for key, value in records.items() if value is record)]))
    frozen = Selection(tool_id="P0-06", mode_id="directed_programs", asset_ids=["upload"],
        object_inputs=[{"role": "directed_program_input", "input_id": first}],
        measurement_spec_ref=None)
    scope = SimpleNamespace(upload_id="upload", max_tool_runs=2,
        binding={"resources": records, "data_view": {"view_id": "same-view"},
                 "selections": {"P0-06": frozen.model_dump(mode="json")}})
    empty = Selection(tool_id="P0-06", mode_id="directed_programs", asset_ids=[],
        object_inputs=[], measurement_spec_ref=None)
    allowed = SimpleNamespace(tool_id="P0-06", mode_id="directed_programs")
    coordinator = ScientificInputs(service)
    assert coordinator.assessment_selection({}, scope, allowed, empty) == frozen
    # An already executed first source does not turn the old approved scope into
    # permission for the second source, even with a remaining tool-run slot.
    state = {"_tool_runs": [{"tool_id": "P0-06", "state": "succeeded"}]}
    assert coordinator.assessment_selection(state, scope, allowed, empty) == frozen


def test_signed_program_graph_validation_uses_available_ulm_method():
    from types import SimpleNamespace
    from bridge.web.native_evidence import _program_validation_method

    source = (SimpleNamespace(result={"program_summaries": [
        {"method_id": "PROC-SCORE-SCANPY", "assessment_state": "not_assessed",
         "direction_definition": "sign_of_source_logFC"},
        {"method_id": "PROC-SCORE-DECOUPLER", "assessment_state": "available",
         "direction_definition": "sign_of_source_logFC"}]}),)
    assert _program_validation_method(source) == "METHOD-DECOUPLER"
    source[0].result["program_summaries"][1]["assessment_state"] = "not_assessed"
    assert _program_validation_method(source) == "METHOD-DECOUPLER"


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
    coverage = {"missing_genes": ["PRIVATE_MISSING_GENE"], "ambiguous_genes": ["PRIVATE_AMBIGUOUS_GENE"],
        "gene_symbols_sha256": "a" * 64, "observed_gene_count": 3, "declared_gene_count": 5}
    local["program_summaries"][0].update(coverage)
    local["program_summaries"].extend([
        {"program_id": "private-pluri", "source_gene_set": "HU-2020-TABLE-S1",
         "method_id": "PROC-SCORE-SCANPY", "mean": 0.25, "reason_codes": []},
        {"program_id": "private-dissoc", "source_gene_set": "OFLANAGAN-2019-CORE",
         "method_id": "PROC-SCORE-DECOUPLER", "mean": None,
         "reason_codes": ["program_gene_identifier_ambiguous"]},
    ])
    local["marker_observations"] = [{"positive_genes": ["PRIVATE_MISSING_GENE"],
        "gene_detection": {"PRIVATE_MISSING_GENE": {"count": 0, "denominator": 5, "state": "unknown"}}}]
    rows = [{"alias": "E-privatehashprefix", "state": "available", "tool_id": "P0-06",
        "summary": local, "measurements": [{"alias": "M-local", "raw_value": None,
            "object_ref": {"object_id": "PRIVATE_MEASUREMENT_REF", "object_version": "0.2.0"}}],
        "provenance": {"plan_id": "private-plan", "tool_run_ref": {"object_id": "PRIVATE_RUN_REF", "object_version": "1"}},
        "artifact_ids": ["private-artifact"]}]
    shared, binding = assessment_model_evidence(rows)
    assert shared[0]["summary"]["reason_codes"] == ["process_metadata_incomplete"]
    wire = json.dumps(shared)
    for private in ("program:reviewed-example@0.1.0", "E-privatehashprefix",
                    "private-plan", "private-artifact", "PRIVATE_MISSING_GENE", "PRIVATE_AMBIGUOUS_GENE",
                    "PRIVATE_MEASUREMENT_REF", "PRIVATE_RUN_REF", "a" * 64):
        assert private not in wire
    projected = shared[0]["summary"]["program_summaries"][0]
    pluri, dissoc = shared[0]["summary"]["program_summaries"][1:]
    assert pluri["program_family"] == "pluripotency_like"
    assert pluri["method_name"] == "Scanpy score_genes"
    assert pluri["mean"] == 0.25
    assert dissoc["program_family"] == "dissociation_heat_shock"
    assert dissoc["method_name"] == "decoupler ULM"
    assert dissoc["mean"] is None
    assert dissoc["reason_codes"] == ["program_gene_identifier_ambiguous"]
    assert "program_family" not in projected and "method_name" not in projected
    assert "private-pluri" not in wire and "private-dissoc" not in wire
    assert "gene_symbols_sha256" not in projected
    assert local["program_summaries"][0]["gene_symbols_sha256"] == "a" * 64
    marker = shared[0]["summary"]["marker_observations"][0]
    gene_alias = projected["missing_genes"][0]
    assert marker["positive_genes"] == [gene_alias]
    assert marker["gene_detection"] == {gene_alias: {"count": 0, "denominator": 5, "state": "unknown"}}
    assert projected["availability"] == "unavailable"
    assert projected["reason_codes"] == ["program_gene_coverage_insufficient"]
    assert projected["observed_gene_count"] == 3 and projected["declared_gene_count"] == 5
    for field in ("missing_genes", "ambiguous_genes"):
        assert [binding["references"][alias] for alias in projected[field]] == coverage[field]
        assert local["program_summaries"][0][field] == coverage[field]
    assert binding["evidence"][shared[0]["alias"]] == "E-privatehashprefix"


def test_native_model_projection_omits_only_canonically_repeated_observations():
    from bridge.web.evidence import assessment_model_evidence

    composition = [{"label": "state:example", "count": 1, "denominator": 10,
                    "fraction": 0.1, "denominator_scope": "selected_data_view"}]
    observation = {"count": 1, "denominator": 10, "state": "measured"}
    rows = [
        {"alias": "E-p005", "state": "available", "tool_id": "P0-05",
         "summary": {"runtime_mode": "saved_cell_state_context",
                     "primary_composition": composition, "auxiliary_composition": composition},
         "measurements": []},
        {"alias": "E-p004", "state": "available", "tool_id": "P0-04",
         "summary": {"runtime_mode": "saved_cell_state_context",
                     "primary_composition": composition, "auxiliary_composition": composition,
                     "marker_observations": [
                         {"state_id": "L1:first", "positive_genes": ["GENE1"],
                          "counter_genes": [], "gene_detection": {"GENE1": observation}},
                         {"state_id": "L1:second", "positive_genes": [],
                          "counter_genes": ["GENE1"], "gene_detection": {"GENE1": observation}},
                         {"state_id": "L1:empty", "positive_genes": [],
                          "counter_genes": [], "gene_detection": {}}]},
         "measurements": [{"alias": "M-gene1", "source_alias": "E-p004",
                           "measurement_class": "gate_input_measurement",
                           "metric_name": "native_gene_detection_GENE1", "raw_value": 0.1,
                           "numerator": 1, "denominator": 10, "unit": "fraction",
                           "evidence_state": "inferred"}]},
    ]

    projected, bindings = assessment_model_evidence(rows)
    from model_wire_contract import assert_model_context
    assert_model_context("generation", {"evidence": projected})
    source, native = projected
    assert source["summary"]["primary_composition"][0]["count"] == 1
    assert source["summary"]["auxiliary_composition"][0]["denominator"] == 10
    assert bindings["references"][source["summary"]["primary_composition"][0]["label"]] == "state:example"
    assert "primary_composition" not in native["summary"]
    assert "auxiliary_composition" not in native["summary"]
    assert all("gene_detection" not in row for row in native["summary"]["marker_observations"])
    assert len(native["measurements"]) == 1
    measurement = native["measurements"][0]
    assert {key: measurement[key] for key in ("raw_value", "numerator", "denominator", "unit")} == {
        "raw_value": 0.1, "numerator": 1, "denominator": 10, "unit": "fraction"}
    assert measurement["evidence_state"] == "inferred"
    assert measurement["citation_role"] == "observation"
    assert "alias" not in measurement
    assert native["measurement_defaults"] == {"measurement_class": "gate_input_measurement",
        "source_alias": native["alias"], "citation_ref_version": 1}
    assert bindings["evidence"][measurement["citation_alias"]] == "E-p004#measurement:M-gene1@1"
    assert native["projection_omissions"]["marker_observations.gene_detection"] == (
        "canonical_measurements_with_measured_detection_state")
    assert native["projection_omissions"]["primary_composition"] == source["alias"]
    assert native["projection_omissions"]["auxiliary_composition"] == source["alias"]

    rows[1]["measurements"][0]["numerator"] = 2
    mismatch, _ = assessment_model_evidence(rows)
    assert "gene_detection" in mismatch[1]["summary"]["marker_observations"][0]


def test_graph_model_projection_lifts_only_identical_record_fields():
    from bridge.web.evidence import assessment_model_evidence

    claims = [{"alias": f"N-private-{index}", "node_type": "Claim",
               "evidence_tier": "formal", "lifecycle_state": "active",
               "domain_id": "target_identity", "claim_type": "descriptive_domain_observation"}
              for index in range(15)]
    summary = {"query_name": "get_case_evidence_subgraph", "graph_alias": "N-private-graph",
               "graph_version": 1, "returned_node_count": 15, "returned_edge_count": 0,
               "truncated": False, "omitted_node_count": 0, "omitted_edge_count": 0,
               "nodes": [], "claims": claims, "requirements": [], "records": [],
               "reconciliations": [], "edges": []}
    projected, bindings = assessment_model_evidence([{
        "alias": "E-private", "state": "available", "tool_id": "P0-09",
        "summary": summary, "measurements": []}])
    from model_wire_contract import assert_model_context
    assert_model_context("generation", {"evidence": projected})
    graph = projected[0]["summary"]
    assert graph["record_defaults"]["claims"]["node_type"] == "Claim"
    assert graph["record_defaults"]["claims"]["domain_id"] == "target_identity"
    assert "explicit null overrides" in graph["record_defaults_semantics"]
    assert len(graph["claims"]) == 15
    assert {bindings["references"][row["alias"]] for row in graph["claims"]} == {
        f"N-private-{index}" for index in range(15)}
    assert all("node_type" not in row for row in graph["claims"])


def test_verified_case_query_has_bounded_summary_allowance_only_through_100_nodes():
    from bridge.web.evidence import (
        MAX_SUMMARY_BYTES, _SummaryLimit, _assessment_result_limit, _check_summary_limit)

    payload = {"summary": "x" * 40000}
    query = {"query_name": "get_case_evidence_subgraph", "returned_node_count": 100}
    assert MAX_SUMMARY_BYTES < 40000 < _assessment_result_limit("P0-09", query)
    _check_summary_limit(payload, limit=_assessment_result_limit("P0-09", query))
    for tool_id, result in (("P0-09", {**query, "returned_node_count": 101}),
                            ("P0-09", {**query, "returned_node_count": True}),
                            ("P0-04", query)):
        with pytest.raises(_SummaryLimit):
            _check_summary_limit(payload, limit=_assessment_result_limit(tool_id, result))


def test_exploratory_graph_observation_needs_verified_active_applicable_numeric_source():
    from bridge.web.evidence import _assessment_query, _citation_role, assessment_model_evidence

    result = {"query_name": "get_case_evidence_subgraph", "graph_id": "graph:example",
        "graph_version": 3, "returned_node_count": 1, "returned_edge_count": 0,
        "truncated": True, "omitted_node_count": 1, "omitted_edge_count": 0, "edges": [],
        "nodes": [{"node_id": "node:observation", "node_type": "EvidenceRecord",
            "graph_id": "graph:example", "graph_version": 3, "record_mode": "owned",
            "evidence_tier": "exploratory", "lifecycle_state": "active", "properties": {
                "evidence_id": "evidence:example", "evidence_version": 1,
                "evidence_family_ref": {"object_id": "family:example", "object_version": "1"},
                "tool_run_ref": {"object_id": "run:example", "object_version": "1"},
                "measurement_result_ref": {"object_id": "measurement:example", "object_version": "1"},
                "measurement_spec_ref": {"object_id": "spec:example", "object_version": "1"},
                "provenance_refs": ["run:example"], "tool_run_execution_state": "partial",
                "domain_id": "target_identity", "evidence_state": "inferred", "value": 0.25,
                "unit": "fraction", "metric_id": "target_identity_fraction",
                "numerator": 1, "denominator": 4, "applicability": "applicable",
                "relation": "supports", "interval": None}}]}
    summary = _assessment_query(result)
    record = summary["records"][0]
    assert record["source_verification_state"] == "verified"
    assert record["eligibility"] == "not_eligible"
    assert _citation_role(record, graph_record=True) == "observation"
    projected, bindings = assessment_model_evidence([{
        "alias": "E-source", "state": "available", "tool_id": "P0-09",
        "summary": summary, "measurements": []}])
    visible = projected[0]["summary"]["records"][0]
    assert "graph_node_id" not in visible
    assert "node:observation" not in json.dumps(projected)
    assert visible["citation_role"] == "observation"
    assert bindings["citation_roles"][visible["citation_alias"]] == "observation"
    for change in ({"source_verification_state": "unavailable"},
                   {"lifecycle_state": "superseded"}, {"applicability": "not_applicable"},
                   {"evidence_tier": "formal"}, {"value": None}):
        assert _citation_role({**record, **change}, graph_record=True) is None
    assert _citation_role({**record, "value": None, "evidence_state": "unknown"},
                          graph_record=True) == "missing"


@pytest.mark.parametrize("value,evidence_state,projected_value,projection_state", [
    (0.5, "inferred", 0.5, "numeric"),
    (None, "unavailable", None, "literal_null"),
    ("private_unstructured_value", "inferred", None, "withheld"),
])
def test_assessment_graph_model_aliases_keep_joins_without_hash_derived_ids(
        value, evidence_state, projected_value, projection_state):
    from bridge.web.evidence import assessment_model_evidence
    summary = {"graph_alias": "N-privategraphhash", "graph_version": 2,
        "query_name": "get_case_evidence_subgraph", "returned_node_count": 2,
        "returned_edge_count": 1, "truncated": False, "omitted_node_count": 0, "omitted_edge_count": 0,
        "nodes": [{"alias": "N-privatenodehash", "node_type": "EvidenceRecord",
                   "evidence_tier": "shadow", "lifecycle_state": "active"}],
        "records": [{"alias": "N-privatenodehash", "family_alias": "N-privatefamilyhash",
                     "node_type": "EvidenceRecord", "evidence_tier": "shadow", "lifecycle_state": "active",
                     "domain_id": "target_identity", "evidence_state": evidence_state,
                     "metric_id": "target_identity_fraction", "unit": "fraction",
                     "applicability": "applicable", "relation": "supports", "interval": None,
                     "value": value, "numerator": 2, "denominator": 4}],
        "claims": [], "reconciliations": [],
        "requirements": [], "edges": [{"source": "N-privatenodehash",
                     "target": "N-privategraphhash", "type": "supports"}]}
    local = [{"alias": "E-privatehash", "state": "available", "tool_id": "P0-09",
              "summary": summary, "measurements": []}]
    shared, bindings = assessment_model_evidence(local)
    from model_wire_contract import assert_model_context
    assert_model_context("generation", {"evidence": shared})
    again, _ = assessment_model_evidence(local)
    graph = shared[0]["summary"]
    assert graph["nodes"][0]["alias"] == graph["records"][0]["alias"] == graph["edges"][0]["source"]
    assert graph["edges"][0]["target"] == graph["graph_alias"]
    assert graph["records"][0]["value"] == projected_value and graph["records"][0]["denominator"] == 4
    assert graph["records"][0]["value_projection_state"] == projection_state
    assert "value_state" not in graph["records"][0]
    assert graph["records"][0]["evidence_state"] == evidence_state
    assert graph["records"][0]["metric_name"] == "target_identity_fraction"
    assert graph["records"][0]["metric_semantics_state"] == "available"
    assert graph["records"][0]["unit"] == "fraction" and graph["records"][0]["interval"] is None
    assert "private" not in json.dumps(shared)
    assert shared[0]["alias"] != again[0]["alias"]
    assert bindings["references"][graph["graph_alias"]] == "N-privategraphhash"


def test_measurement_states_are_observations_until_a_claim_relation_assigns_a_role():
    from bridge.web.evidence import assessment_model_evidence
    from bridge.web.provider import _citation_choices

    local = [{
        "alias": "E-privatehash",
        "state": "available",
        "tool_id": "P0-06",
        "summary": {},
        "measurements": [
            {"alias": "M-measured", "measurement_class": "gate_input_measurement",
             "metric_name": "mean_g2m_score", "raw_value": 0.2, "unit": "score",
             "evidence_state": "measured"},
            {"alias": "M-negative", "measurement_class": "gate_input_measurement",
             "metric_name": "g2m_detection", "raw_value": 0.0, "unit": "fraction",
             "evidence_state": "negative"},
            {"alias": "M-alert", "measurement_class": "gate_input_measurement",
             "metric_name": "stress_alert", "raw_value": 0.7, "unit": "score",
             "evidence_state": "alert"},
            {"alias": "M-missing", "measurement_class": "gate_input_measurement",
             "metric_name": "independent_repeat_effect", "raw_value": None, "unit": None,
             "evidence_state": "missing"},
        ],
    }]

    shared, bindings = assessment_model_evidence(local)
    choices = _citation_choices(shared)
    records = {row["metric_name"]: row for row in shared[0]["measurements"]}

    from bridge.web.provider import provider_citations
    assert shared[0]["alias"].startswith("R-")
    assert not provider_citations(shared[0]["alias"])
    assert all(provider_citations(record["citation_alias"]) == {record["citation_alias"]}
               for record in records.values())
    assert shared[0]["alias"] not in {
        alias for values in choices.values() for alias in values
    }
    assert set(choices["evidence_aliases"]) == {
        records[name]["citation_alias"]
        for name in ("mean_g2m_score", "g2m_detection", "stress_alert")
    }
    assert choices["opposing_evidence_aliases"] == []
    assert choices["missing_evidence_aliases"] == [
        records["independent_repeat_effect"]["citation_alias"]]
    assert {
        alias: bindings["citation_roles"][alias]
        for values in choices.values() for alias in values
    } == {
        records["mean_g2m_score"]["citation_alias"]: "observation",
        records["g2m_detection"]["citation_alias"]: "observation",
        records["stress_alert"]["citation_alias"]: "observation",
        records["independent_repeat_effect"]["citation_alias"]: "missing",
    }
    stable = {bindings["evidence"][alias]
              for values in choices.values() for alias in values}
    assert stable == {
        "E-privatehash#measurement:M-measured@1",
        "E-privatehash#measurement:M-negative@1",
        "E-privatehash#measurement:M-alert@1",
        "E-privatehash#measurement:M-missing@1",
    }


def test_available_container_with_only_missing_record_offers_no_support_or_opposition():
    from bridge.web.evidence import assessment_model_evidence
    from bridge.web.provider import _citation_choices

    shared, _ = assessment_model_evidence([{
        "alias": "E1", "state": "available", "tool_id": "P0-06", "summary": {},
        "measurements": [{"alias": "M-null", "measurement_class": "gate_input_measurement",
            "metric_name": "mean_g2m_score", "raw_value": None, "unit": "score",
            "evidence_state": "missing"}],
    }])

    choices = _citation_choices(shared)
    assert choices["evidence_aliases"] == []
    assert choices["opposing_evidence_aliases"] == []
    assert choices["missing_evidence_aliases"] == [
        shared[0]["measurements"][0]["citation_alias"]
    ]


def test_graph_opposition_requires_the_record_to_enter_an_eligible_reconciliation():
    from bridge.web.evidence import _assessment_query, assessment_model_evidence
    from bridge.web.provider import _citation_choices

    claim_ref = {"object_id": "claim:synthetic", "object_version": "1.0.0"}
    family_ref = {"object_id": "evidence-family:synthetic", "object_version": "1.0.0"}

    def evidence_node(identifier, metric, relation, state, value):
        return {
            "node_id": "node:" + identifier,
            "object_id": identifier,
            "object_version": "1",
            "node_type": "EvidenceRecord",
            "evidence_tier": "formal",
            "lifecycle_state": "active",
            "properties": {
                "evidence_id": identifier,
                "evidence_version": 1,
                "claim_ref": claim_ref,
                "evidence_family_ref": family_ref,
                "domain_id": "target_identity",
                "evidence_state": state,
                "value": value,
                "unit": "fraction",
                "metric_id": metric,
                "numerator": None,
                "denominator": None,
                "applicability": "applicable",
                "relation": relation,
                "interval": None,
            },
        }

    result = {
        "query_name": "get_case_evidence_subgraph",
        "graph_id": "graph:synthetic",
        "graph_version": 1,
        "returned_node_count": 5,
        "returned_edge_count": 0,
        "truncated": False,
        "omitted_node_count": 0,
        "omitted_edge_count": 0,
        "edges": [],
        "nodes": [
            {"node_id": "node:claim", "object_id": "claim:synthetic",
             "object_version": "1.0.0", "node_type": "Claim", "evidence_tier": "formal",
             "lifecycle_state": "active", "properties": {
                 "domain_id": "target_identity", "claim_type": "descriptive_domain_observation"}},
            evidence_node("evidence:aaaaaaaaaaaaaaaaaaaaaaaa", "target_identity_fraction",
                          "contradicts", "negative", 0.0),
            evidence_node("evidence:bbbbbbbbbbbbbbbbbbbbbbbb", "regional_fidelity_fraction",
                          "contradicts", "negative", 0.0),
            evidence_node("evidence:cccccccccccccccccccccccc", "whole_product_target_region_fraction",
                          "supports", "unknown", None),
            {"node_id": "node:reconciliation", "object_id": "reconciliation:synthetic",
             "object_version": "1", "node_type": "ReconciliationRecord", "evidence_tier": "formal",
             "lifecycle_state": "active", "properties": {
                 "eligibility": "eligible", "state": "stable", "direction": "contradicts",
                 "reason_codes": [], "channel_resolutions": [],
                 "included_evidence_refs": ["evidence:aaaaaaaaaaaaaaaaaaaaaaaa@1"]}},
        ],
    }

    summary = _assessment_query(result)
    local = [{"alias": "E-graph", "state": "available", "tool_id": "P0-09",
              "summary": summary, "measurements": []}]
    shared, bindings = assessment_model_evidence(local)
    choices = _citation_choices(shared)
    records = {row["metric_name"]: row for row in shared[0]["summary"]["records"]}

    assert choices["opposing_evidence_aliases"] == [
        records["target_identity_fraction"]["citation_alias"]
    ]
    assert "citation_alias" not in records["regional_fidelity_fraction"]
    assert choices["missing_evidence_aliases"] == [
        records["whole_product_target_region_fraction"]["citation_alias"]
    ]
    assert bindings["evidence"][records["target_identity_fraction"]["citation_alias"]] == (
        "E-graph#record:N-64bc815af51fa805@1"
    )


@pytest.mark.parametrize("oversized", ["composition", "reasons"])
def test_assessment_hard_count_keeps_existing_summary_row_bounds(tmp_path, oversized):
    from test_p0_05_hard_count_accounting import _hard_count_request, _run
    from bridge.tool_packages.p0_05_off_target_control.models import OffTargetHardCountAccounting
    from bridge.web.evidence import _assessment_hard_count, _SummaryLimit, MAX_ROWS
    run = _run(_hard_count_request(tmp_path))
    assert run.execution_state.value == "succeeded"
    assert _assessment_hard_count(run.result)["accounting"] == run.result["accounting"]
    result = json.loads(json.dumps(run.result))
    accounting = result["accounting"]
    if oversized == "composition":
        accounting["producer_composition"]["records"].extend([
            {"view": "source_specific", "source_id": f"source:extra-{index}", "label": "state:extra",
             "label_level": "L1", "state_evidence_state": "candidate", "denominator_scope": "selected_data_view",
             "count": 0, "fraction": 0.0, "denominator": accounting["n_observations"]}
            for index in range(MAX_ROWS + 1)])
    else:
        accounting["reason_codes"] = [f"source_reason_{index}" for index in range(MAX_ROWS + 1)]
    # The canonical contract accepts these unbounded lists; Web projection must refuse, not truncate.
    OffTargetHardCountAccounting.model_validate(accounting)
    with pytest.raises(_SummaryLimit):
        _assessment_hard_count(result)


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
    service.sessions.save(state)
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
    service.sessions.save(state)

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
        service.sessions.save(state)

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
        context = json.loads(payload["messages"][0]["content"].split(
            "Safe execution context: ", 1)[1])
        text = ("This observation is descriptive and does not establish product qualification."
                if len(captured) == 1 else "No result evidence supplied.")
        aliases = ([context["observation_choices"][0]["observation_alias"]]
                   if len(captured) == 1 else [])
        return httpx.Response(200, json={"choices": [{"message": {
            "content": json.dumps({"action": "reply", "text": text,
                                   "observation_aliases": aliases})}}]})
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
        service.sessions.save(state)
    elif damage == "artifact_identity":
        record["artifact_id"] = "artifact:PRIVATE_FALSE_ID"
        service.sessions.save(state)
    elif damage == "execution_identity":
        state["_tool_runs"][-1]["state"] = "partial"
        service.sessions.save(state)

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
    assert audit["observation_refs"] == [
        first_context["observation_choices"][0]["record_ref"]]
    assert "_result_contexts" not in first_public

    reloaded = create_app(service.settings).state.service
    try:
        assert reloaded.load(sid)["_result_contexts"] == first_state["_result_contexts"]
    finally:
        reloaded.execution.shutdown()

    if suppression == "disabled":
        service.settings = replace(service.settings, share_result_summaries=False)
    else:
        state = service.load(sid)
        service.controls.review(state)
        service.sessions.save(state)
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
    assert any(item["content"] == first_assistant["content"]
               for item in final_public["messages"])


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
    service.sessions.save(state)
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
    values = dict(storage_root=tmp_path / "private",
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
def test_settings_accepts_only_exact_share_result_summary_startup_values(
    tmp_path, monkeypatch, configured, expected
):
    from bridge.web.runtime import settings_from_environment
    environment = {
        "BRIDGE_WEB_STORAGE": str(tmp_path / "startup-private"),

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
    assert settings_from_environment().share_result_summaries is expected


def test_settings_rejects_ambiguous_share_result_summary_startup_value(
    tmp_path, monkeypatch
):
    from bridge.web.runtime import settings_from_environment
    environment = {
        "BRIDGE_WEB_STORAGE": str(tmp_path / "startup-private"),

        "BRIDGE_WEB_MODEL_BASE_URL": "https://provider.invalid/v1",
        "BRIDGE_WEB_MODEL": "test-model",
        "BRIDGE_WEB_MODEL_API_KEY": "private-key",
        "BRIDGE_WEB_SHARE_RESULT_SUMMARIES": "true"}
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("BRIDGE_WEB_TRUSTED_ANCESTORS", raising=False)

    with pytest.raises(ValueError, match="invalid_server_configuration"):
        settings_from_environment()

def test_saved_target_roles_remain_visible_when_receipt_has_no_mode():
    from bridge.web.evidence import assessment_portrait
    row=dict(tool_id="P0-03",alias="saved-roles",state="available",
        provenance={"receipt_sha256":"a"*64},
        summary={"runtime_mode":"saved_cell_state_context","target_fraction":None})
    axes=assessment_portrait([row],[],modes_by_receipt={"a"*64:None})
    target=next(axis for axis in axes if axis["id"]=="target_identity")
    assert target["context_evidence_aliases"]==["saved-roles"]
    assert target["evidence_aliases"]==[]
    assert target["state"]=="missing"


@pytest.mark.parametrize("tool_id", ["P0-03", "P0-05"])
def test_saved_whole_product_projection_fits_counts_and_citable_measurements(tool_id):
    """A fine-state portrait must not disappear when its measurements are included."""
    from bridge.web.evidence import _assessment_aggregate, _assessment_result_limit, _check_summary_limit, _SummaryLimit

    composition = [{"record_id": f"whole-product:synthetic-{i}", "record_kind": "state",
        "state_id": f"L2:synthetic_{i}", "display_name": f"Synthetic reference state {i}",
        "level": "L2", "parent_state_id": "L1:Radial_Glia", "count": 100,
        "whole_product_denominator": 9600, "whole_product_fraction": 100 / 9600,
        "parent_denominator": 9600, "parent_fraction": 100 / 9600,
        "resolution_state": "candidate", "scientific_status": "not_established"} for i in range(96)]
    result = {"runtime_mode": "saved_cell_state_context", "data_view": {"n_observations": 9600},
        "whole_product_composition": composition, "target_fraction": None,
        "non_target_fraction": None, "domain_score": None, "score_state": "unavailable"}
    row = {"state": "available", "tool_id": tool_id, "summary": _assessment_aggregate(result),
        "measurements": [{"alias": f"M-{i:016x}", "measurement_class": "gate_input_measurement",
            "metric_name": f"whole_product_fraction_synthetic_reference_state_{i}",
            "raw_value": 100 / 9600, "numerator": 100, "denominator": 9600, "unit": "fraction",
            "interval": None, "interval_confidence_level": None, "unknown_scope": "not_assessed",
            "evidence_state": "inferred", "score_state": "unavailable", "domain_score": None,
            "source_execution_state": "succeeded", "source_alias": "E-synthetic-source",
            "artifact_sha256": f"{i:064x}"} for i in range(96)]}
    assert len(json.dumps(row, separators=(",", ":")).encode()) > 64 * 1024
    _check_summary_limit(row, limit=_assessment_result_limit(tool_id, result))
    # This allowance belongs to saved whole-view accounting, not every tool result.
    for other in ({"runtime_mode": "saved_cell_state_context"}, {**result, "runtime_mode": "other"}):
        with pytest.raises(_SummaryLimit):
            _check_summary_limit(row, limit=_assessment_result_limit(tool_id, other))
    with pytest.raises(_SummaryLimit):
        _check_summary_limit({**row, "measurements": row["measurements"] * 4},
                             limit=_assessment_result_limit(tool_id, result))
    with pytest.raises(_SummaryLimit):
        _assessment_aggregate({**result, "whole_product_composition": composition * 2})


def test_native_model_projection_keeps_missing_genes_and_reuses_exact_whole_counts():
    from copy import deepcopy
    from bridge.web.evidence import assessment_model_evidence

    composition = [{"state_id": "L2:synthetic", "count": 3,
                    "whole_product_denominator": 10, "whole_product_fraction": 0.3}]
    source = {"alias": "E-composition", "state": "available", "tool_id": "P0-05",
              "summary": {"runtime_mode": "saved_cell_state_context",
                          "whole_product_composition": composition}, "measurements": []}
    target = {"alias": "E-target", "state": "available", "tool_id": "P0-03",
              "summary": {"runtime_mode": "saved_cell_state_context",
                          "whole_product_composition": deepcopy(composition),
                          "target_fraction": None, "role_judgement_state": "not_assessed"},
              "measurements": []}
    development = {"alias": "E-development", "state": "available", "tool_id": "P0-04",
        "summary": {"runtime_mode": "saved_cell_state_context", "marker_observations": [{
            "positive_genes": ["DETECTED", "ABSENT"], "counter_genes": [],
            "gene_detection": {"DETECTED": {"count": 3, "denominator": 10, "state": "measured"},
                               "ABSENT": {"count": None, "denominator": None, "state": "missing"}}}]},
        "measurements": [
            {"alias": "M-detected", "source_alias": "E-development",
             "measurement_class": "gate_input_measurement",
             "metric_name": "native_gene_detection_DETECTED",
             "numerator": 3, "denominator": 10, "raw_value": 0.3,
             "unit": "fraction", "evidence_state": "inferred"},
            {"alias": "M-absent", "source_alias": "E-development",
             "measurement_class": "gate_input_measurement",
             "metric_name": "native_gene_detection_ABSENT",
             "numerator": None, "denominator": None, "raw_value": None,
             "unit": "fraction", "evidence_state": "unavailable"}]}
    original = deepcopy([source, target, development])
    rows, bindings = assessment_model_evidence([source, target, development,
        {"alias": "E-following", "tool_id": "P0-06", "state": "available",
         "summary": {}, "measurements": []}])
    assert bindings["evidence"][rows[-1]["alias"]] == "E-following"
    assert "whole_product_composition" not in rows[1]["summary"]
    assert rows[1]["projection_omissions"]["whole_product_composition"] == rows[0]["alias"]
    assert rows[1]["summary"]["target_fraction"] is None
    remaining = rows[2]["summary"]["marker_observations"][0]["gene_detection"]
    assert {bindings["references"][key]: value for key, value in remaining.items()} == {
        "ABSENT": {"count": None, "denominator": None, "state": "missing"}}
    assert rows[2]["measurements"][0]["raw_value"] == 0.3
    assert rows[2]["measurements"][1]["raw_value"] is None
    assert rows[2]["measurements"][1]["citation_role"] == "missing"
    assert [source, target, development] == original

    target["summary"]["whole_product_composition"][0]["whole_product_denominator"] = 12
    development["measurements"][0]["numerator"] = 4
    mismatched, _ = assessment_model_evidence([source, target, development])
    assert mismatched[1]["summary"]["whole_product_composition"][0]["whole_product_denominator"] == 12
    assert len(mismatched[2]["summary"]["marker_observations"][0]["gene_detection"]) == 2


def test_model_query_defaults_reconstruct_numeric_and_missing_records_without_mutation():
    from copy import deepcopy
    from bridge.web.evidence import assessment_model_evidence, _assessment_model_query

    records = [{"alias": f"N-synthetic-{index}", "node_type": "EvidenceObservation",
        "evidence_tier": "formal", "lifecycle_state": "active",
        "domain_id": "target_identity", "evidence_state": "inferred",
        "metric_id": "target_fraction", "value": index / 100,
        "numerator": index, "denominator": 100, "unit": "fraction",
        "interval": None, "applicability": "applicable", "relation": "supports",
        "source_verification_state": "verified", "source_execution_state": "succeeded"}
        for index in range(20)]
    records[-1].update(value=None, numerator=None, denominator=None, evidence_state="unavailable")
    summary = {"query_name": "get_case_evidence_subgraph", "graph_alias": "N-graph",
        "graph_version": 2, "returned_node_count": 20, "returned_edge_count": 0,
        "truncated": False, "omitted_node_count": 0, "omitted_edge_count": 0,
        "nodes": [], "claims": [], "requirements": [], "records": records,
        "reconciliations": [], "edges": []}
    original = deepcopy(summary)
    rows, bindings = assessment_model_evidence([{"alias": "E-query", "tool_id": "P0-09",
        "state": "available", "summary": summary, "measurements": []}])
    graph = rows[0]["summary"]
    reverse = {value: key for key, value in bindings["references"].items()}
    expected = _assessment_model_query(summary, reverse.__getitem__)["records"]
    defaults = graph["record_defaults"]["records"]
    assert defaults["interval"] is None
    assert "denominator" not in defaults
    restored = [{**defaults, **row} for row in graph["records"]]
    for actual, wanted in zip(restored, expected):
        assert {key: actual[key] for key in wanted} == wanted
    assert restored[-1]["value"] is None and restored[-1]["denominator"] is None
    assert summary == original
