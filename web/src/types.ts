export type SessionStatus =
  | "idle"
  | "thinking"
  | "awaiting_approval"
  | "running"
  | "stopping"
  | "failed";

export type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
};

export type Upload = {
  id: string;
  name: string;
  kind: string;
  size: number;
  source_family_id?: string;
};

export type PlanStep = {
  id: string;
  tool_id: string;
  label: string;
  status:
    | "pending"
    | "running"
    | "succeeded"
    | "failed"
    | "skipped"
    | "partial"
    | "cancelled"
    | "blocked";
  reason: string | null;
};

export type Plan = {
  id: string;
  digest: string;
  status: "proposed" | "approved" | "completed" | "failed" | "partial" | "cancelled";
  summary: string;
  steps: PlanStep[];
};

export type ArtifactKind = "figure" | "table" | "evidence" | "download";

export type Artifact = {
  id: string;
  name: string;
  kind: ArtifactKind;
  media_type: string;
  url: string;
  tool_id: string;
};

export type ToolCapability = {
  tool_id: string;
  label: string;
  state: "ready" | "needs_input" | "not_connected";
  reason_codes: string[];
};

export type AnalysisAssetInputContract = {
  min_count: number;
  max_count: number | null;
  formats: string[];
  assays: string[];
  input_levels: string[];
  matrix_semantics: string[];
  required_metadata_keys: string[];
};

export type AnalysisInputRoleContract = {
  role: string;
  schema_refs: string[];
  object_version_policy: "fixed" | "payload";
  object_versions: string[];
  min_count: number;
  max_count: number | null;
};

export type AnalysisInputModeContract = {
  mode_id: string;
  roles: AnalysisInputRoleContract[];
  asset_input: AnalysisAssetInputContract | null;
};

export type AnalysisInputContract = {
  tool_id: string;
  request_schema_ref: string;
  asset_input: AnalysisAssetInputContract | null;
  measurement_spec_ref_policy: "forbidden" | "optional" | "required";
  parameters_allowed: boolean;
  random_seed_policy: "any_integer" | "fixed_zero";
  object_input_modes: AnalysisInputModeContract[];
};

export type AnalysisSelection = {
  tool_id: string;
  mode_id: string | null;
  asset_ids: string[];
  object_inputs: Array<{ role: string; input_id: string }>;
  measurement_spec_ref: string | null;
};

export type AnalysisInputObject = {
  id: string;
  label: string;
  schema_ref: string;
  object_version: string;
  source: "user_upload" | "package_resource" | "system_resource" | "tool_output";
  producer_tool_id: string | null;
};

export type AnalysisAssetDeclaration = {
  upload_id?: string;
  assay?: string;
  matrix_location?: string;
  matrix_semantics?: string;
  input_level?: string;
  metadata?: Record<string, unknown>;
};

export type AnalysisInputAsset = {
  id: string;
  label: string;
  declaration: AnalysisAssetDeclaration | null;
};

export type AnalysisInputsResponse = {
  tools: Array<{ tool_id: string; label: string; input_contract: AnalysisInputContract }>;
  objects: AnalysisInputObject[];
  assets: AnalysisInputAsset[];
  selections: Record<string, AnalysisSelection>;
  measurement_specs: Array<{ id: string; label: string }>;
};

export type AnalysisAssetRegistration = {
  upload_id: string;
  assay: string;
  matrix_location: string;
  matrix_semantics: string;
  input_level: string;
  metadata: Record<string, unknown>;
};

export type JsonValue =
  | null
  | boolean
  | number
  | string
  | JsonValue[]
  | { [key: string]: JsonValue };

export type PendingInputChange = {
  id: string;
  digest: string;
  kind: "asset" | "source" | "intake";
  upload_id: string;
  changes: Array<{ field: string; before: JsonValue; after: JsonValue }>;
};

export type ClarificationAnswer = {
  field: string;
  selected: string[];
  text: string;
  unknown: boolean;
};

export type Clarification = {
  id: string;
  digest: string;
  upload_id: string;
  message_id: string;
  status: "pending" | "answered" | "cancelled" | "stale" | "superseded";
  input_revision: number;
  questions: Array<{
    field: string; title: string; reason: string; multiple: boolean;
    options: Array<{ id: string; label: string; description: string }>;
  }>;
  answers: ClarificationAnswer[];
};

export type ScienceCandidate = {
  label_level: "L1" | "L2";
  roles: Array<{ state_id: string; product_role: "target" | "acceptable_adjacent" | "known_off_target" | "role_unresolved"; source_ids: string[]; rationale: string }>;
  development: Array<{ state_id: string; stage_role: "earlier" | "within_window" | "later" | "branch_shift" | "unresolved"; source_ids: string[]; rationale: string }>;
  regional_denominator_state_ids: string[];
  regional_target_state_ids: string[];
};
export type InternalReport = {
  audience: "internal_research"; policy_state: "candidate_unreviewed"; boundaries: string[];
  sections: Array<{ domain_id: string; title: string; text: string; evidence_state: "not_assessed" }>;
  verification: { release_state: string; public_export_eligibility: string; reason_codes: string[] } | null;
  next_actions: string[];
};
export type ScientificDraft = {
  internal_report?: InternalReport | null;
  id: string; digest: string; upload_id: string; message_id: string;
  status: "pending" | "confirmed" | "stale" | "superseded";
  facts: IntakeFacts; candidate: ScienceCandidate; unknowns: string[];
  attestation_state: string; object_ids: Record<string, string>;
  sources: Array<{ source_id: string; version: string; state_id: string; label_level: string;
    definition: string; anatomy_scope: string; developmental_scope: string; derivation: string;
    review_status: string; limitations: string[]; source_refs: string[] }>;
  stages: Array<{ tool_id: string; state: string; reason_codes: string[] }>;
};

export type Session = {
  scientific_drafts?: ScientificDraft[];
  clarifications?: Clarification[];
  id: string;
  title: string;
  updated_at: string;
  status: SessionStatus;
  messages: Message[];
  uploads: Upload[];
  plan: Plan | null;
  plan_history?: Plan[];
  capabilities?: ToolCapability[];
  artifacts: Artifact[];
  error: string | null;
  input_review_required: boolean;
  pending_input_change: PendingInputChange | null;
};

export type SessionSummary = Pick<Session, "id" | "title" | "updated_at">;

export type SessionsResponse = {
  sessions: SessionSummary[];
};


export type IntakeFacts = {
  starting_cell_type?: string | null;
  cell_line?: string | null;
  culture_day?: number | null;
  sequencing_method?: string | null;
  protocol_name?: string | null;
  product_name: string | null;
  product_family: "hpsc_mda" | "other" | "unknown";
  target_cell_type: string | null;
  target_stage: string | null;
  sampling_context: "pretransplant_preparation" | "process_sample" | "unknown";
  independent_cultures: number | null;
  culture_batch_column?: string | null;
  culture_batch_role?: "unknown" | "independent_culture" | "not_culture" | "unsure";
  assay: "scRNA-seq" | "snRNA-seq" | "unknown";
  matrix_location: string | null;
  count_semantics: "raw_counts" | "not_raw_counts" | "unknown";
  source_family_id: string | null;
  sample_id_column: string | null;
  capture_id_column: string | null;
  gene_symbol_column: string | null;
};

export type IntakeQuestion = {
  field: keyof IntakeFacts; title: string; input_type: "number" | "text"; help?: string;
  options: Array<{ value: string; label: string }>;
};

export type ProtocolSource = { id: string; kind: string; label: string; location: string; text: string };
export type ProtocolQuestion = {
  id: string; title: string; step_ids: string[]; source_ids: string[]; sources: ProtocolSource[];
  options: Array<{ value: string; label: string }>; answer_state: "unanswered" | "answered" | "unsure";
};
export type ProtocolSupplement = ProtocolSource & {
  question_id: string; other: boolean; unsure: boolean; superseded?: boolean; created_at: string;
};
export type ProtocolVersion = {
  id: string; digest: string; created_at: string; bpl: string;
  steps: Array<{ id: string; label: string; operations: string; line_start: number; line_end: number;
    source_ids: string[]; sources: ProtocolSource[]; origin: string }>;
  questions: ProtocolQuestion[];
  excluded_sources: Array<{ source_id: string; reason: string; source: ProtocolSource }>;
  supplements: ProtocolSupplement[];
  coverage_state: "complete_for_extracted_scope" | "partial" | "needs_input";
  review_state: "unreviewed" | "reviewed"; review?: { created_at: string; scope: string } | null;
  syntax_state: "not_run" | "passed" | "failed";
  compiler_state: "not_run" | "passed" | "failed" | "unavailable";
  diagnostics: Array<{ code: string; message: string; line?: number | null }>;
  unchecked: Array<{ code: string; message: string; line?: number | null }>;
  compiler: { commit: string; version: string; verified: boolean };
  stages: Array<{ stage: string; exit_code: number }>;
  source_binding: { sources_truncated: boolean; included_passages: number; extracted_passages: number };
  generation: { number: number; request_count: number; model: string; reported_model: string | null; prompt_version: string; kind: string };
  artifacts: Record<string, string>;
};
export type ProtocolFormalization = {
  protocol_id: string; name: string; revision: number;
  state: "not_started" | "pending" | "running" | "complete" | "unavailable" | "cancelled";
  error: string | null; latest: ProtocolVersion | null;
  versions: Array<{ id: string; digest: string; created_at: string; review_state: "unreviewed" | "reviewed" }>;
};
export type ProtocolAction =
  | { action: "formalize" }
  | { action: "review"; digest: string }
  | { action: "edit"; bpl: string }
  | { action: "answer"; question_id: string; value: string; other: boolean; unsure: boolean };

export type IntakeAutofill = {
  state: "not_started" | "parsing" | "complete" | "unavailable"; revision: number; sources_truncated?: boolean;
  sources: Array<{ id: string; kind: string; label: string; location: string; text: string }>;
  field_sources: Record<string, { kind: string; source_ids: string[]; quote: string }>;
  samples: Array<{ sample_id: string; culture_days: number[]; missing_days: number;
    n_observations: number; sample_summary_complete: boolean }>;
  protocols: Array<{ id: string; name: string; size: number }>;
  formalizations?: ProtocolFormalization[];
  protocol_stages: Array<{ label: string; start_day: number | null; end_day: number | null;
    operations: string; source_ids: string[]; quote: string; timing_state?: "source_explicit" | "needs_confirmation" | "unspecified" }>;
  other_answers: Record<string, string>;
  conflicts: Array<{ field: keyof IntakeFacts; observed: string | number | null; extracted: string | number;
    source_ids: string[]; quote: string }>;
  questions: IntakeQuestion[];
  batch_binding?: { column: string; role: string; distinct: number; complete: boolean; missing: number } | null;
};

export type IntakeResponse = {
  autofill?: IntakeAutofill;
  upload_id: string;
  facts: IntakeFacts;
  observed: {
    n_observations: number | null;
    n_genes: number | null;
    matrix_locations: string[];
    obs_columns: string[];
    var_columns: string[];
  };
  state: "draft" | "confirmed" | "stale";
  missing_fields: string[];
  next_tool: string | null;
  blockers: string[];
  qc_state: string;
  measurement_spec_ref: string | null;
  roadmap: Array<{ question: string; state: string }>;
};

export type NormalizedSession = Session & {
  plan_history: Plan[];
  capabilities: ToolCapability[];
};

export function normalizeSession(session: Session): NormalizedSession {
  return {
    ...session,
    plan_history: session.plan_history ?? [],
    capabilities: session.capabilities ?? [],
    input_review_required: session.input_review_required ?? false,
    pending_input_change: session.pending_input_change ?? null,
  };
}
