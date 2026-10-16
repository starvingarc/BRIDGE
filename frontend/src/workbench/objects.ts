/** Wire types for plans/research-objects.md. Keep in step with that contract; the backend owns the shapes. */
import type { Artifact } from "../types";
import type { Pathway, ReagentKind } from "./types";

export type ReagentDTO = {
  id?: string; name: string; short: string; pathway: Pathway; kind: ReagentKind; dose_text: string;
  start_day: number | null; end_day: number | null; catalog_id: string | null; unconfirmed?: string[]; source_locator?: string | null;
  /** The source's own wording for the timing, kept when it is relative (e.g. "after the cells reach confluence"). */
  timing_text?: string | null;
  /** Where a dose or a day came from: the document itself, or a protocol the document cites (contract §7.8). */
  field_provenance?: { field: "dose_text" | "start_day" | "end_day"; kind: "direct" | "recipe_reference"; source_ref: string; source_locator: string; recipe_locator: string | null }[];
};

export type ProtocolVersionDTO = {
  id: string; protocol_id: string; version: number; status: "draft" | "confirmed"; based_on_version_id: string | null;
  /** A name the version is known by, such as a published variant (Boost+); shown instead of "name vN" when present. */
  label?: string | null;
  change_note?: string; total_days: number | null; stages?: { index: number; start_day: number; end_day: number }[];
  reagents: ReagentDTO[]; operations?: { day: number | null; kind: string; note: string }[]; confirmed_at: string | null; revision: number;
  /** Whole-version review items (contract §7.5): subset of source_review, total_days, stages, operations. */
  unconfirmed?: string[];
  provenance?: { material_id: string | null; formalization_version_id: string | null } | null;
  /** Whether a reader checked this version against its source (contract §7.8); independent of confirmation. */
  source_review?: { status: "pending" | "reviewed"; reviewed_at: string | null; note: string };
  execution_readiness?: { status: "ready" | "incomplete" | "needs_review"; reasons: string[] };
};

type FormalizationSourceDTO = { id: string; kind: string; label: string; location: string; text: string };
type QuotedDTO = { quote?: string | null; source_ids?: string[] };
/** GET …/versions/{vid}/formalization; only the fields the source pane reads are typed. */
export type FormalizationDTO = {
  id: string;
  steps?: { id: string; label: string; operations?: string; sources?: FormalizationSourceDTO[] }[];
  questions?: { id: string; title: string; answer_state: string; sources?: FormalizationSourceDTO[] }[];
  coverage_state?: string; review_state?: string; compiler_state?: string;
  projection?: {
    reagents?: (QuotedDTO & { name: string })[]; operations?: QuotedDTO[]; stages?: QuotedDTO[];
    total_days?: (QuotedDTO & { value: number | null }) | null;
  };
};

export type ProtocolDTO = {
  id: string; research_id: string; name: string; origin: "lab" | "literature";
  citation: { title: string; doi?: string } | null; latest_version_id: string; latest: ProtocolVersionDTO;
  versions: ProtocolVersionDTO[]; revision: number;
};

export type RunDTO = {
  id: string; research_id: string; name: string; protocol_version_id: string; cell_line: string | null;
  start_date: string | null; state: "planned" | "expanding" | "differentiating" | "frozen" | "grafted" | "ended";
  graft: { date: string; host: string; site: string } | null; day: number | null; stage_index: number | null;
  today: { kind: string; label: string }[]; revision: number;
  /** A retrospective run records an experiment already done, e.g. public data; it has no current day or reminders. */
  purpose?: "execution" | "retrospective";
};

export type SampleDTO = {
  id: string; run_id: string; day: number; collected_on: string | null; assay: string;
  material_id: string | null; session_id: string | null; assessment_id: string | null; revision: number;
  /** Latest mapping request for this sample (proposed in plans/research-objects.md §7). */
  assessment_request?: { action_id: string; status: ActionDTO["status"] } | null;
  /** Lifecycle from collection to mapping result (proposed in plans/workbench-flow.md §3); derived when absent. */
  status?: "collected" | "data_attached" | "mapping" | "done" | "failed";
  /** Why standard mapping cannot run for attached data yet; null when it can or when there is no data. */
  assessment_availability?: { status: "unavailable"; code: string } | null;
  /** The researcher's declaration of where the raw counts are and what the sample is (contract §7.6); null until declared. */
  mapping_input?: MappingInputDTO | null;
};

export type MappingInputDTO = {
  matrix_location: string; matrix_semantics: "raw_counts"; sample_context: "pre_graft" | "post_graft"; source_family_id: string;
  /** The single capture the whole file came from, or the obs column naming each cell's capture; never both. */
  capture_id?: string; capture_id_column?: string; gene_symbol_column?: string;
};

export type ChainLevelDTO = { level: number; name: string; numerator: number | null; denominator: number | null; value: number | null; reason?: string };

export type AssessmentDTO = {
  id: string; sample_id: string; status: "awaiting_approval" | "running" | "done" | "failed" | "unavailable";
  /** The registered sample analysis of a finished mapping (docs/sample-analysis-api.md §10); absent on older results. */
  analysis_id?: string | null;
  /** Quick mapping adds reference, method, tree, features and projection; `tree` must equal the devtree version to draw cells. */
  versions: { atlas: string; naming: string; metrics: string; reference?: string; method?: string; tree?: string; features?: string };
  chain: ChainLevelDTO[]; target_fraction: number | null;
  /** Per transferred label; quick mapping reports the nearest reference cells' weeks, not a calibrated age. */
  gestation: { cell_type: string; weeks: Record<string, number>; outside_reference: number | null; status?: string }[];
  /** Share of all query cells per tree label; cells without a tree position are left out, so the sum may be below 1. */
  tree_position: Record<string, number>; mapped_cells?: [number, number, number, number][];
  alerts: { kind: string; value: number }[]; failure: { code: string; message: string } | null;
  method_label?: string; scientific_status?: string; ood_status?: string;
  n_cells?: number; n_tree_cells?: number; tree_unavailable_cells?: number;
  shared_genes?: number; selected_genes?: number; limitations?: string[];
  normalization?: string;
  /** Summary of the marker expression stored with this result; the matrix itself is read on demand. */
  marker_expression?: { status: string; version?: string; genes?: string[]; n_sample_points?: number; n_reference_points?: number } | null;
};

/**
 * GET …/assessments/{aid}/marker-expression. `sample.values` rows follow the assessment's `mapped_cells`;
 * `reference.values` rows follow `reference.tree_cell_indices` into the tree's `cells`. A null value means the gene is
 * outside the shared gene space; tree cells not listed are not in the mapping reference.
 */
export type MarkerExpressionDTO = {
  object_version: string; genes: string[]; tree_version: string; feature_set_sha256: string; normalization: string;
  gene_status: { gene: string; status: string; missing_from: ("query" | "reference")[] }[];
  sample: { values: (number | null)[][] };
  reference: { tree_cell_indices: number[]; values: (number | null)[][]; excluded_reason?: string };
};

/** One shared QC summary; values are the tool's own, a missing value stays null (docs/sample-analysis-api.md §11). */
export type QcSummaryDTO = {
  state: string; tool_id: string; execution_state: string; assay: string; input_level: string; readiness_state: string;
  schema_integrity: { n_observations: number; observation_kind: "cells" | "nuclei" | "barcodes"; n_genes: number; unique_cell_ids: boolean; unique_gene_ids: boolean };
  count_metrics_state: "measured" | "not_assessed";
  metrics: { metric_name: string; raw_value: number | null; denominator: number | null; evidence_state: string; score_state: string; domain_score: number | null }[];
  assessment_states: Record<string, string>;
  selected_data_view: { view_kind: string; n_observations: number } | null;
  score_state: string; domain_score: number | null;
};

/**
 * The automatic cell-cycle scoring of a sample (Seurat 2019 S and G2/M gene sets), over every cell. Phases are a
 * transcriptional assignment: G1 includes non-cycling cells, and the phase is never a QC criterion.
 */
export type CellCycleSummaryDTO = {
  cell_cycle: {
    assessment_state: string; n_observations: number | null; phase_counts: Partial<Record<"G1" | "S" | "G2M", number>> | null;
    s_g2m_fraction: number | null; mean_s_score: number | null; mean_g2m_score: number | null; reason_codes: string[];
    s_missing_genes?: string[]; g2m_missing_genes?: string[];
  } | null;
  n_observations: number | null; interpretation_scope: string; domain_score: null; score_state: string;
  resource_ref: string | null; resource_version: string | null; resource_sha256: string | null;
};

export type AnalysisResultDTO = {
  id: string; source_artifact_id: string; sha256: string; display_sha256: string | null;
  artifact: Artifact | null; assessment?: { id: string; url: string } | null;
};

/**
 * GET …/samples/{sid}/analyses, one registered analysis of a sample. `version` is the order of registration within the
 * sample, not which result the researcher adopted; an unavailable source keeps its record but no summary or files.
 */
export type AnalysisDTO = {
  /** sample_cell_atlas: the sample's own embedding and clusters (UMAP and Leiden), read from its per-cell table. */
  source_kind: "session_execution" | "atlas_mapping" | "sample_qc" | "sample_cell_cycle" | "sample_cell_atlas";
  qc_summary?: QcSummaryDTO | null; cell_cycle_summary?: CellCycleSummaryDTO | null; assessment_id?: string;
  mapping_versions?: Record<string, string>; reference_manifest_sha256?: string;
  id: string; research_id: string; sample_id: string; run_id: string; version: number; created_at: string;
  session_id: string | null; receipt_sha256: string; execution_state: "succeeded" | "partial";
  tool: { id: string; version: string; run_id: string; environment_spec_id: string };
  material_id: string;
  input_assets: { asset_id: string; format: string; input_level: string; matrix_location: string | null; matrix_semantics: string | null; assay: string | null }[];
  results: AnalysisResultDTO[];
  availability: { status: "available" | "unavailable"; reason_code: string | null };
};

export type LeadDTO = { id: string; run_id: string; sample_id: string | null; chain_level: number | null; summary: string; status: "open" | "resolved" | "dismissed"; revision: number };

export type ActionDTO = {
  id: string; research_id: string; title: string; context: { run_id?: string; sample_id?: string };
  tier: "formal" | "exploratory"; estimate: string; kind: string;
  status: "pending" | "approved" | "running" | "done" | "declined" | "failed"; revision: number;
};

export type WorkbenchDTO = {
  protocols: ProtocolDTO[]; runs: RunDTO[]; samples: SampleDTO[]; assessments: AssessmentDTO[];
  leads: LeadDTO[]; actions: ActionDTO[];
};
