export type SessionStatus =
  | "idle"
  | "thinking"
  | "awaiting_approval"
  | "running"
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

export type Session = {
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
};

export type SessionSummary = Pick<Session, "id" | "title" | "updated_at">;

export type SessionsResponse = {
  sessions: SessionSummary[];
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
  };
}
