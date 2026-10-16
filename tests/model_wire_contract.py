"""Independent key contracts for model contexts; never import production allowlists.

The test boundary consumes actual HTTP request JSON, including compact table
columns. These contracts detect field drift, not sensitive prose or biological
truth. Keep registration and clause mapping in docs/privacy-and-provenance.md.
"""
import json
import re

# None denotes a scalar or a list of scalars, not an arbitrary JSON object.
def fields(names, **nested):
    return {**dict.fromkeys(names.split()), **nested}


# Aggregate producers share this recursively closed vocabulary. It is declared
# independently from evidence.py so expanding a production projection requires
# an explicit privacy-contract review. No wildcard object keys are accepted.
AGGREGATE_FIELDS = frozenset("""
release_state public_export_eligibility scientific_validation input_revision
result_state upstream_composition_state channels composition_view label_level
denominator_scope assessment_state target_identity_fraction regional_fidelity_fraction
whole_product_target_region_fraction numerator denominator fraction value unit
window_compatibility_state analysis_mode whole_product_profile target_related_profile
denominator_kind role_fractions role primary_denominator n_observations
total_soft_mass role_composition product_role soft_mass observed_count
exclusion_state unknown_profile coverage_state rare_state_profile
soft_fraction detection_state validated_detection_limit_fraction false_positive_fraction
zero_observation_upper_bound_fraction program_results gene_coverage minimum_gene_coverage
lod_state evidence_state analysis_scope applicability availability process_attribution
process_attribution_state measurement_projection_state score_state domain_score
runtime_mode interpretation_scope state_review_status independence_state
n_independent_replicates n_features program_summaries program_id method_id score_unit
observed_gene_count declared_gene_count mean median lower_quantile upper_quantile
signature_scope gene_coverage_fraction source_gene_set direction_definition unresolved_member_count
missing_genes ambiguous_genes cell_cycle phase_counts S G2M G1 s_g2m_fraction mean_s_score mean_g2m_score
profiles domain_id evidence_sufficiency_state eligibility source_execution_state
metric_name raw_value interval interval_confidence_level unknown_scope
reason_codes composition reconciliation composition_state open_set_state
calibration_state label count state_evidence_state accounting role_counts
consensus_supported_count fraction_of_selected_view observation_unit producer_composition
records state view source_id support_basis accounting_basis accounting_state mass_state
primary_denominator_id primary_composition auxiliary_composition marker_observations
channel expected_window_match target_fraction non_target_fraction role_judgement_state
state_id definition_decision identity_state positive_genes counter_genes source_ids
gene_detection whole_product_composition data_view record_id record_kind display_name
level parent_state_id resolution_state whole_product_denominator whole_product_fraction
parent_denominator parent_fraction scientific_status source_definition_decisions
query_name graph_version returned_node_count returned_edge_count truncated omitted_node_count
omitted_edge_count display_omitted_edges display_omitted_nodes graph_alias
requirements nodes edges alias node_type evidence_tier lifecycle_state relation family_alias
type source target claims reconciliations claim_alias claim_context_state
claim_type claim_type_alias claim_type_semantics_state requirement_key requirement_key_alias
requirement_key_semantics_state channel_role channel_role_alias channel_role_semantics_state
required_modality modality_semantics_state experiment_required reason_semantics_state
withheld_reason_count metric_alias metric_semantics_state value_projection_state
unit_semantics_state source_verification_state direction eligible
program_family method_name citation_alias citation_role citation_ref_version
measurement_class source_alias record_defaults record_defaults_semantics
lower upper confidence_level method_ref
""".split())

BIOLOGICAL_CONTEXT = fields("source input_revision", facts=fields("""
product_family starting_cell_type culture_day target_cell_type target_stage
sampling_context independent_cultures assay sequencing_method
"""))
FEATURE_COVERAGE = fields("object_version complete feature_count semantics",
                          results=[fields("identifier state")])
LITERATURE_METADATA = fields("""
source_ref provider provider_id pmid doi title year authors journal url publication_types publication_status
""", corrections=[fields("type id source reference note")])
LITERATURE_SOURCE = fields("""
object_version source_ref url retrieved_at content_level abstract abstract_sha256 content_sha256
""", metadata=LITERATURE_METADATA)
LITERATURE = fields("""
state search_concept_refs searches_remaining reads_remaining readable_source_refs read_before_explanation
""", request_history=[fields("action concept_refs focus source_ref state")],
    discovered=[LITERATURE_METADATA], sources=[LITERATURE_SOURCE])
HYPOTHESIS = fields("""
statement competing_explanation expected_observation discriminating_check evidence_aliases
missing_evidence_aliases opposing_evidence_aliases feature_queries
""", literature_support=[fields("source_ref rationale species lineage stage experimental_context qualification")],
    evidence_relations=[fields("evidence_alias relation rationale applicability")])
ISSUE = fields("hypothesis_index field code quote reason")
REVISION = fields("", hypotheses=[HYPOTHESIS], issues=[ISSUE])
EVIDENCE = fields("""
alias state tool_id tool_version execution_state score_state domain_score reason_code interpretation_scope
measurement_defaults_semantics
""", summary=AGGREGATE_FIELDS, measurements=[AGGREGATE_FIELDS],
    measurement_defaults=AGGREGATE_FIELDS,
    projection_omissions=fields("""
primary_composition auxiliary_composition whole_product_composition marker_observations.gene_detection
"""), review_projection=fields("uncited_measurements_omitted summary_tables_omitted"))
OPTION = fields("""
id tool_id mode_id kind name summary scientific_status execution_state prerequisites_state
""")
PREVIOUS_ERROR = fields("category count status_code missing_count extra_count",
    issues=[fields("path type code hypothesis_index field")],
    fields=fields("statement competing_explanation expected_observation"))

ASSESSMENT_GENERATION_ALLOWLIST = fields("""
purpose question results_sent_to_model evidence_table_encoding report_after_explanation
previous_action_error revision_evidence_scope
""", options=[OPTION], allowed_modes=[fields("tool_id mode_id")],
    biological_context=BIOLOGICAL_CONTEXT, evidence=[EVIDENCE],
    blockers=[fields("tool_id mode_id reason_codes")],
    interpretation_gaps=[fields("tool_id mode_id reason_codes")],
    report_preparation=fields("state explanation_after_graph_required"),
    workflow_handoff=fields("state explanation_version prior_report_state"),
    literature=LITERATURE, feature_coverage=FEATURE_COVERAGE,
    previous_action_error_detail=PREVIOUS_ERROR, revision=REVISION)
INTERPRETATION_REVIEW_ALLOWLIST = fields("""
question available_scientific_checks evidence_table_encoding review_scope
""", biological_context=BIOLOGICAL_CONTEXT, evidence=[EVIDENCE],
    feature_coverage=FEATURE_COVERAGE, literature=[LITERATURE_SOURCE],
    hypotheses=[HYPOTHESIS])
DIRECTED_REPAIR_ALLOWLIST = fields("question revision_evidence_scope evidence_table_encoding",
    biological_context=BIOLOGICAL_CONTEXT, evidence=[EVIDENCE],
    feature_coverage=FEATURE_COVERAGE, literature=fields("", sources=[LITERATURE_SOURCE]),
    revision=REVISION)
WORKBENCH_CONTEXT_ALLOWLIST = fields("schema_version state reason_code next_step record_authority scientific_result_authority",
    scope=fields("research_id run_id kind"), research=fields("id name description"),
    protocols=[fields("id name origin", citation=fields("title doi"))],
    protocol_versions=[fields("id protocol_id version status based_on_version_id change_note total_days confirmed_at revision",
        source_review=fields("status"), execution_readiness=fields("status reasons"),
        stages=[fields("index start_day end_day")],
        reagents=[fields("id name short pathway kind dose_text start_day end_day catalog_id unconfirmed timing_text")],
        operations=[fields("day kind note timing_text")])],
    protocol_differences=[fields("version_id based_on_version_id changed_fields")],
    runs=[fields("id research_id name protocol_version_id start_date state revision day stage_index purpose",
                 today=[fields("kind label")])],
    samples=[fields("id run_id day collected_on assay assessment_id revision status",
        assessment_request=fields("action_id status"), assessment_availability=fields("status code"),
        workflow=fields("status attempt_id agent_state", issues=[fields("step code", fields=[None])]))],
    assessments=[fields("id sample_id status revision", versions=fields("atlas naming metrics"), failure=fields("code message"))],
    leads=[fields("id run_id sample_id chain_level summary status created_by revision")],
    actions=[fields("id title tier estimate kind status revision", context=fields("run_id sample_id protocol_version_id"))],
    object_counts=fields("protocols protocol_versions runs samples assessments leads actions"))
PURPOSE_ALLOWLISTS = {
    "workbench": WORKBENCH_CONTEXT_ALLOWLIST,
    "generation": ASSESSMENT_GENERATION_ALLOWLIST,
    "review": INTERPRETATION_REVIEW_ALLOWLIST,
    "repair": DIRECTED_REPAIR_ALLOWLIST,
}


def _check(value, allowed, path):
    if value is None:
        return
    if isinstance(allowed, list):
        if isinstance(value, dict):
            # Validate every declared column, even one marked absent in every
            # row. Checking only rows would miss compressed unknown-field leaks.
            assert set(value) == {"columns", "rows", "missing"}, path
            columns = value["columns"]
            assert isinstance(columns, list) and all(isinstance(k, str) for k in columns), path
            assert len(columns) == len(set(columns)), path
            _check(dict.fromkeys(columns), allowed[0], path + ".columns")
            assert isinstance(value["rows"], list), path
            assert isinstance(value["missing"], list), path
            assert len(value["rows"]) == len(value["missing"]), path
            for row, missing in zip(value["rows"], value["missing"]):
                assert isinstance(row, list), path
                assert isinstance(missing, list), path
                assert len(row) == len(columns), path
                assert all(type(i) is int and 0 <= i < len(columns) for i in missing), path
                # Absent cells must be placeholders; never hide payload objects.
                assert all(row[i] is None for i in missing), path
                _check(dict(zip(columns, row)), allowed[0], path + "[]")
            return
        assert isinstance(value, list), path
        for item in value:
            _check(item, allowed[0], path + "[]")
    elif isinstance(allowed, frozenset):
        if isinstance(value, list):
            for item in value:
                _check(item, allowed, path + "[]")
        elif isinstance(value, dict):
            if set(value) == {"columns", "rows", "missing"}:
                _check(value, [allowed], path)
                return
            assert set(value) <= allowed, path + ": unregistered keys " + str(sorted(set(value) - allowed))
            for key, item in value.items():
                if key in {"gene_detection", "source_definition_decisions"} and isinstance(item, dict):
                    assert all(re.fullmatch(r"R-[0-9a-f]{32}", alias) for alias in item), path + "." + key
                    for entry in item.values():
                        _check(entry, fields("count denominator state") if key == "gene_detection" else None,
                               path + "." + key + ".*")
                else:
                    _check(item, allowed, path + "." + key)
    elif isinstance(allowed, dict):
        assert isinstance(value, dict), path
        assert set(value) <= set(allowed), path + ": unregistered keys " + str(sorted(set(value) - set(allowed)))
        for key, item in value.items():
            _check(item, allowed[key], path + "." + key)
    else:
        assert not isinstance(value, dict), path
        if isinstance(value, list):
            assert all(not isinstance(item, (dict, list)) for item in value), path


def assert_model_context(operation, context, *, shared=True):
    _check(context, PURPOSE_ALLOWLISTS[operation], operation)
    if not shared:
        assert operation == "generation", "review and repair require explicit result sharing"
        assert context["results_sent_to_model"] is False
        assert context["evidence"] == []
        assert context["biological_context"] == {"source": "not_shared", "facts": {}}
        assert context.get("feature_coverage") is None and context.get("revision") is None


def assert_model_request(operation, payload, *, shared=True):
    """Inspect the serialized request, not an upstream builder's return value."""
    if operation == "generation":
        text = payload["messages"][0]["content"].split("\nSafe execution context: ", 1)[1]
        context, _ = json.JSONDecoder().raw_decode(text)
    else:
        context = json.loads(payload["messages"][1]["content"])
    assert_model_context(operation, context, shared=shared)
    return context
