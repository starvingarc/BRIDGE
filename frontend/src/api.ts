import { parseUploadLimits, uploadErrorMessage } from "./upload";
import type { ActionDTO, AnalysisDTO, FormalizationDTO, MappingInputDTO, MarkerExpressionDTO, ProtocolDTO, RunDTO, SampleDTO, WorkbenchDTO } from "./workbench/objects";
import {
  normalizeSession,
  type AnalysisAssetRegistration,
  type AssessmentProposal,
  type AnalysisInputsResponse,
  type AnalysisSelection,
  type Session,
  type Artifact,
  type ClarificationAnswer,
  type ScienceCandidate,
  type IntakeFacts,
  type IntakeResponse,
  type ProtocolAction,
  type SessionsResponse,
  type SessionSummary,
  type ResearchSummary,
  type Research,
  type ResearchMaterial,
} from "./types";

export type Principal = {id: string; username: string; role: "user" | "admin"; must_change_password: boolean};
export type AuthConfig = {mode: "accounts"; notice?: string; notice_version?: string; username_pattern?: string; password_min?: number; password_max?: number};
export type PersonalModelView = {source: "default" | "personal"; default: ModelSettingsView; personal: ModelSettingsView | null};
export type AdminUser = Principal & {disabled: boolean};
export type AdminSession = SessionSummary & {owner_id: string; owner_username: string; status: string};
let accountEpoch = 0;
export const resetAccountRequests = () => { accountEpoch += 1; };
const GENERIC_ERROR = "The request could not be completed. Please try again.";

export type ModelSettingsView = { configured: boolean; base_url: string; model: string; has_api_key: boolean; action_protocol: string };
export type ModelSettingsInput = { base_url: string; model: string; api_key: string; action_protocol: string };
export type ProviderInput = {id: string; name: string; base_url: string; api_key: string; models: string[]; action_protocol: string};
export type ModelProvider = Omit<ProviderInput, "api_key"> & {shared: boolean; editable: boolean; has_api_key: boolean; configured: boolean;
  /** Effort capability per model ID, tied to the saved service configuration; absent or stale means unknown. */
  capabilities?: Record<string, ModelCapability>};
export type Effort = "none" | "minimal" | "low" | "medium" | "high" | "xhigh" | "max";
/** Only levels the service declared are supported; unknown is neither supported nor unsupported. */
export type ModelCapability = {status: "supported" | "unsupported" | "unknown"; supported_levels: Effort[]; default_level: Effort | null};
export type ModelChoice = {provider_id: string; model: string; effort: Effort | null};
/**
 * GET/PUT /api/sessions/{sid}/model-selection. `selection` is what the next task will use; `task_configuration` is
 * the configuration of the last task that started, which can differ while a task is running or queued.
 */
export type ModelSelectionView = {
  selection: ModelChoice;
  availability: {state: "ready" | "unavailable"; reason: string | null};
  capability: ModelCapability;
  task_configuration: (ModelChoice & {base_url?: string; version?: string}) | null;
};
const MODEL_CHOICE_ERRORS: Record<string, string> = {
  model_selection_unavailable: "这个模型现在不可用，可能服务已删除或密钥失效，请重新选择。",
  model_effort_unavailable: "这个模型没有确认支持该 effort 档位，请刷新能力或换一个档位。",
  model_configuration_changed: "模型服务的配置刚刚改变，请重新选择。",
};
/** Prefers the server's readable message, then the known codes, then a generic line. */
const modelChoiceError = (status: number, body: unknown) => {
  const raw = body as {detail?: unknown; user_message?: unknown} | null;
  if (typeof raw?.user_message === "string" && raw.user_message.trim()) return raw.user_message;
  if (typeof raw?.detail === "string" && MODEL_CHOICE_ERRORS[raw.detail]) return MODEL_CHOICE_ERRORS[raw.detail];
  return status === 401 ? "请先登录。" : "没能保存模型选择，请稍后重试。";
};
export type ModelDirectory = {providers: ModelProvider[]; selected: {provider_id: string; model: string}};
const modelSettingsError = (status: number) => status === 401 ? "请先登录。" : status === 422
  ? "请检查服务地址、模型名称和密钥；更换地址时必须重新填写密钥。" : "模型配置操作失败，请稍后重试。";

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init: RequestInit = {}, errorMessage?: (status: number, body: unknown) => string): Promise<T> {
  const epoch = accountEpoch;
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      headers,
      credentials: "same-origin",
    });
  } catch {
    throw new ApiError(0, "The server is unavailable. Check the connection and try again.");
  }

  if (epoch !== accountEpoch) throw new ApiError(0, "Request cancelled.");
  if (!response.ok) {
    if (response.status === 401 && !["/api/login", "/api/register", "/api/me"].includes(path)) {
      window.dispatchEvent(new Event("bridge-auth-expired"));
    }
    let detail = response.status === 401 ? "Authentication required." : GENERIC_ERROR;
    let body: unknown = null;
    try {
      body = await response.json();
      const raw = body as { detail?: unknown } | null;
      if (!errorMessage && typeof raw?.detail === "string" && raw.detail.trim()) detail = raw.detail;
    } catch {
      // Keep the stable public message for unknown or non-JSON failures.
    }
    throw new ApiError(response.status, errorMessage ? errorMessage(response.status, body) : detail);
  }

  const body = await response.json();
  if (epoch !== accountEpoch) throw new ApiError(0, "Request cancelled.");
  return body as T;
}

const sessionRequest = async (path: string, init: RequestInit = {}, errorMessage?: (status: number, body: unknown) => string) =>
  normalizeSession(await request<Session>(path, init, errorMessage));

const publicRequestError = (status: number, body: unknown) => {
  const message = (body as { user_message?: unknown } | null)?.user_message;
  return typeof message === "string" ? message : status === 401
    ? "登录已失效，请重新登录。" : "操作未完成，请重试。";
};

export const api = {
  authConfig: () => request<AuthConfig>("/api/auth/config"),
  me: () => request<{user: Principal | null}>("/api/me"),
  accountLogin: (username: string, password: string) => request<{user: Principal}>("/api/login", {method: "POST", body: JSON.stringify({username, password})}, publicRequestError),
  register: (username: string, password: string, notice_version: string) => request<{user: Principal}>("/api/register", {method: "POST", body: JSON.stringify({username, password, notice_version})}, publicRequestError),
  changePassword: (old_password: string, password: string) => request("/api/me/password", {method: "POST", body: JSON.stringify({old_password, password})}, publicRequestError),
  personalModelSettings: () => request<PersonalModelView>("/api/me/model-settings"),
  savePersonalModel: (value: ModelSettingsInput) => request<PersonalModelView>("/api/me/model-settings", {method: "PUT", body: JSON.stringify(value)}, modelSettingsError),
  testPersonalModel: (value: ModelSettingsInput) => request<{ok: boolean; message: string}>("/api/me/model-settings/test", {method: "POST", body: JSON.stringify(value)}, modelSettingsError),
  selectModel: (source: "default" | "personal") => request<PersonalModelView>("/api/me/model-settings/select", {method: "POST", body: JSON.stringify({source})}, modelSettingsError),
  deletePersonalModel: () => request<PersonalModelView>("/api/me/model-settings", {method: "DELETE", body: "{}"}, modelSettingsError),
  adminUsers: () => request<{users: AdminUser[]}>("/api/admin/users"),
  adminSessions: (userId = "") => request<{sessions: AdminSession[]}>("/api/admin/sessions?user_id=" + encodeURIComponent(userId)),
  adminSession: (id: string) => request<{session: Session; owner: Principal; protocols: {id: string; name: string}[]}>("/api/admin/sessions/" + encodeURIComponent(id)),
  disableUser: (id: string) => request("/api/admin/users/" + encodeURIComponent(id) + "/disable", {method: "POST", body: "{}"}, publicRequestError),
  resetPassword: (id: string) => request<{temporary_password: string}>("/api/admin/users/" + encodeURIComponent(id) + "/reset-password", {method: "POST", body: "{}"}, publicRequestError),
  models: () => request<ModelDirectory>("/api/models", {cache: "no-store", signal: AbortSignal.timeout(15_000)}),
  modelSelection: (sessionId: string, signal?: AbortSignal) =>
    request<ModelSelectionView>(`/api/sessions/${encodeURIComponent(sessionId)}/model-selection`, {cache: "no-store", signal}, modelChoiceError),
  saveModelSelection: (sessionId: string, choice: ModelChoice) =>
    request<ModelSelectionView>(`/api/sessions/${encodeURIComponent(sessionId)}/model-selection`, {method: "PUT", body: JSON.stringify(choice)}, modelChoiceError),
  /** Reads effort metadata from a saved service; a failed read answers ok=false and keeps the previous check time. */
  refreshCapabilities: (providerId: string) =>
    request<{ok: boolean; capabilities: Record<string, ModelCapability>; checked_at: string | null; message: string}>(
      `/api/models/providers/${encodeURIComponent(providerId)}/capabilities`, {method: "POST", body: "{}"}, modelSettingsError),
  saveProvider: (value: ProviderInput) => request<ModelDirectory>("/api/models/providers", {method: "PUT", body: JSON.stringify(value)}, modelSettingsError),
  deleteProvider: (id: string) => request<ModelDirectory>(`/api/models/providers/${encodeURIComponent(id)}`, {method: "DELETE", body: "{}"}, modelSettingsError),
  selectProviderModel: (provider_id: string, model: string) => request<ModelDirectory>("/api/models/select", {method: "POST", body: JSON.stringify({provider_id, model})}, modelSettingsError),
  providerCatalog: (value: ProviderInput) => request<{ok: boolean; models: string[]; message: string}>("/api/models/catalog", {method: "POST", body: JSON.stringify(value)}, modelSettingsError),
  testProvider: (value: ProviderInput) => request<{ok: boolean; message: string}>("/api/models/test", {method: "POST", body: JSON.stringify(value)}, modelSettingsError),
  modelSettings: () => request<ModelSettingsView>("/api/model-settings", { cache: "no-store", signal: AbortSignal.timeout(15_000) }),
  saveModelSettings: (value: ModelSettingsInput) => request<ModelSettingsView>("/api/model-settings", { method: "PUT", body: JSON.stringify(value) }, modelSettingsError),
  testModelSettings: (value: ModelSettingsInput) => request<{ ok: boolean; message: string }>("/api/model-settings/test", { method: "POST", body: JSON.stringify(value) }, modelSettingsError),
  acknowledgeArtifact: (sessionId: string, artifactId: string) =>
    request<Artifact>(`/api/sessions/${encodeURIComponent(sessionId)}/artifacts/${encodeURIComponent(artifactId)}/acknowledge`, {
      method: "POST", body: "{}",
    }, (_status, body) => {
      const message = (body as { user_message?: unknown } | null)?.user_message;
      return typeof message === "string" ? message : "历史版本确认未完成，请重试。";
    }),
  uploadConfig: async (signal?: AbortSignal) => parseUploadLimits(await request<unknown>(
    "/api/config", { signal, cache: "no-store" }, () => "Could not check the upload limit. Please retry.")),
  health: () => request<{ status: "ok" }>("/api/health"),
  logout: () =>
    request<{ authenticated: false }>("/api/logout", { method: "POST", body: "{}" }),
  listSessions: () => request<SessionsResponse>("/api/sessions"),
  archiveSession: (id: string, archived: boolean) =>
    request<SessionSummary>(`/api/sessions/${encodeURIComponent(id)}`, {
      method: "PATCH", body: JSON.stringify({ archived }),
    }, publicRequestError),
  deleteSession: (id: string) =>
    request<{ deleted: true }>(`/api/sessions/${encodeURIComponent(id)}`, {
      method: "DELETE", body: "{}",
    }, publicRequestError),
  workbench: (researchId: string, signal?: AbortSignal) =>
    request<WorkbenchDTO>(`/api/researches/${encodeURIComponent(researchId)}/workbench`, {signal, cache: "no-store"}),
  decideAction: (researchId: string, actionId: string, decision: "approve" | "decline") =>
    request<ActionDTO>(`/api/researches/${encodeURIComponent(researchId)}/actions/${encodeURIComponent(actionId)}/${decision}`,
      {method: "POST", body: "{}"}, publicRequestError),
  createProtocol: (researchId: string, body: {name: string; origin: "lab" | "literature"; expected_version: 0} | {material_id: string; expected_version: 0}) =>
    request<ProtocolDTO>(`/api/researches/${encodeURIComponent(researchId)}/protocols`, {method: "POST", body: JSON.stringify(body)}),
  createProtocolVersion: (researchId: string, protocolId: string, body: {based_on_version_id: string; changes: Record<string, unknown>; expected_version: number}) =>
    request<unknown>(`/api/researches/${encodeURIComponent(researchId)}/protocols/${encodeURIComponent(protocolId)}/versions`, {method: "POST", body: JSON.stringify(body)}),
  protocolFormalization: (researchId: string, protocolId: string, versionId: string) =>
    request<FormalizationDTO>(`/api/researches/${encodeURIComponent(researchId)}/protocols/${encodeURIComponent(protocolId)}/versions/${encodeURIComponent(versionId)}/formalization`),
  updateProtocolVersion: (researchId: string, protocolId: string, versionId: string, body: Record<string, unknown> & {expected_version: number}) =>
    request<unknown>(`/api/researches/${encodeURIComponent(researchId)}/protocols/${encodeURIComponent(protocolId)}/versions/${encodeURIComponent(versionId)}`, {method: "PATCH", body: JSON.stringify(body)}),
  confirmProtocolVersion: (researchId: string, protocolId: string, versionId: string, expectedVersion: number) =>
    request<unknown>(`/api/researches/${encodeURIComponent(researchId)}/protocols/${encodeURIComponent(protocolId)}/versions/${encodeURIComponent(versionId)}/confirm`, {method: "POST", body: JSON.stringify({expected_version: expectedVersion})}),
  createRun: (researchId: string, body: {protocol_version_id: string; name: string; cell_line: string | null; start_date: string | null; state: string; expected_version: 0}) =>
    request<RunDTO>(`/api/researches/${encodeURIComponent(researchId)}/runs`, {method: "POST", body: JSON.stringify(body)}),
  updateRun: (researchId: string, runId: string, body: Record<string, unknown> & {expected_version: number}) =>
    request<RunDTO>(`/api/researches/${encodeURIComponent(researchId)}/runs/${encodeURIComponent(runId)}`, {method: "PATCH", body: JSON.stringify(body)}),
  createSample: (researchId: string, runId: string, body: {day: number; assay: string; collected_on: string | null; material_id: string | null; expected_version: number; mapping_input?: MappingInputDTO}) =>
    request<SampleDTO>(`/api/researches/${encodeURIComponent(researchId)}/runs/${encodeURIComponent(runId)}/samples`, {method: "POST", body: JSON.stringify(body)}),
  /** Attaches sequencing data to a sample registered at collection (proposed in plans/workbench-flow.md §3). */
  updateSample: (researchId: string, sampleId: string, body: {material_id: string; expected_version: number; mapping_input?: MappingInputDTO}) =>
    request<SampleDTO>(`/api/researches/${encodeURIComponent(researchId)}/samples/${encodeURIComponent(sampleId)}`, {method: "PATCH", body: JSON.stringify(body)}),
  /** Stored marker expression of a mapping result, read only when the tree is coloured by gene. */
  /** Every analysis registered for one sample: automatic QC, atlas mapping and session results (docs/sample-analysis-api.md). */
  sampleAnalyses: (researchId: string, sampleId: string, signal?: AbortSignal) =>
    request<{analyses: AnalysisDTO[]}>(`/api/researches/${encodeURIComponent(researchId)}/samples/${encodeURIComponent(sampleId)}/analyses`, {signal}),
  markerExpression: (researchId: string, assessmentId: string, signal?: AbortSignal) =>
    request<MarkerExpressionDTO>(`/api/researches/${encodeURIComponent(researchId)}/assessments/${encodeURIComponent(assessmentId)}/marker-expression`, {signal}),
  /** Starts standard mapping for attached data: a first declaration, or a retry after a failed or blocked attempt (contract §7.6). */
  startSampleMapping: (researchId: string, sampleId: string, body: {expected_version: number; mapping_input?: MappingInputDTO}) =>
    request<SampleDTO>(`/api/researches/${encodeURIComponent(researchId)}/samples/${encodeURIComponent(sampleId)}/mapping`, {method: "POST", body: JSON.stringify(body)}),
  /** Supplements or corrects a sample's declaration; the server starts the sample's standard analysis again. */
  continueSampleWorkflow: (researchId: string, sampleId: string, body: {expected_version: number; mapping_input: MappingInputDTO}) =>
    request<unknown>(`/api/researches/${encodeURIComponent(researchId)}/samples/${encodeURIComponent(sampleId)}/workflow`, {method: "POST", body: JSON.stringify(body)}),
  requestAssessment: (researchId: string, sampleId: string, expectedVersion: number) =>
    request<ActionDTO>(`/api/researches/${encodeURIComponent(researchId)}/samples/${encodeURIComponent(sampleId)}/assessments`, {method: "POST", body: JSON.stringify({expected_version: expectedVersion})}),
  getConversation: (researchId: string, runId: string | null, signal?: AbortSignal) => sessionRequest(
    `/api/researches/${encodeURIComponent(researchId)}${runId ? `/runs/${encodeURIComponent(runId)}` : ""}/conversation`, { signal }),
  openConversation: (researchId: string, runId: string | null) => sessionRequest(
    `/api/researches/${encodeURIComponent(researchId)}${runId ? `/runs/${encodeURIComponent(runId)}` : ""}/conversation`,
    { method: "POST", body: "{}" }, publicRequestError),
  createSession: (researchId?: string | null) => sessionRequest("/api/sessions", {
    method: "POST", ...(researchId ? {body: JSON.stringify({research_id: researchId})} : {}),
  }),
  listResearches: (signal?: AbortSignal) => request<{researches: ResearchSummary[]}>("/api/researches", {signal}, publicRequestError),
  getResearch: (id: string, signal?: AbortSignal) => request<Research>(`/api/researches/${encodeURIComponent(id)}`, {signal}, publicRequestError),
  createResearch: (name: string, description: string) => request<Research>("/api/researches", {
    method: "POST", body: JSON.stringify({name, description}),
  }, publicRequestError),
  renameResearch: (id: string, name: string, description: string) => request<Research>(`/api/researches/${encodeURIComponent(id)}`, {
    method: "PATCH", body: JSON.stringify({name, description}),
  }, publicRequestError),
  assignResearch: (id: string, researchId: string) => sessionRequest(`/api/sessions/${encodeURIComponent(id)}/research`, {
    method: "POST", body: JSON.stringify({research_id: researchId}),
  }, publicRequestError),
  renameSession: (id: string, title: string) => sessionRequest(`/api/sessions/${encodeURIComponent(id)}/title`, {
    method: "PATCH", body: JSON.stringify({title}),
  }, publicRequestError),
  uploadResearchMaterial: (researchId: string, file: File) => {
    const body = new FormData(); body.append("file", file);
    return request<ResearchMaterial>(`/api/researches/${encodeURIComponent(researchId)}/uploads`, {method: "POST", body}, publicRequestError);
  },
  selectResearchMaterial: (id: string, materialId: string, uploadId?: string) => sessionRequest(
    `/api/sessions/${encodeURIComponent(id)}/research-materials`, {
      method: "POST", body: JSON.stringify({material_id: materialId, ...(uploadId ? {upload_id: uploadId} : {})}),
    }, publicRequestError),
  shareResearchMaterial: (id: string, uploadId: string) => request<ResearchMaterial>(
    `/api/sessions/${encodeURIComponent(id)}/share-material`, {
      method: "POST", body: JSON.stringify({upload_id: uploadId}),
    }, publicRequestError),
  researchMaterialUrl: (researchId: string, materialId: string) =>
    `/api/researches/${encodeURIComponent(researchId)}/materials/${encodeURIComponent(materialId)}`,

  getSession: (id: string, signal?: AbortSignal) =>
    sessionRequest(`/api/sessions/${encodeURIComponent(id)}`, { signal }),
  upload: (id: string, file: File) => {
    const body = new FormData();
    body.append("file", file);
    return sessionRequest(`/api/sessions/${encodeURIComponent(id)}/uploads`, {
      method: "POST",
      body,
    }, uploadErrorMessage);
  },
  setSourceInput: (id: string, uploadId: string, sourceFamilyId: string) =>
    sessionRequest(`/api/sessions/${encodeURIComponent(id)}/inputs`, {
      method: "POST",
      body: JSON.stringify({ upload_id: uploadId, source_family_id: sourceFamilyId }),
    }),
  sendMessage: (id: string, text: string) =>
    sessionRequest(`/api/sessions/${encodeURIComponent(id)}/messages`, {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
  proposeAssessment: (id: string, proposal: AssessmentProposal) =>
    sessionRequest(`/api/sessions/${encodeURIComponent(id)}/assessment/propose`, {
      method: "POST", body: JSON.stringify(proposal),
    }),
  approveAssessment: (id: string, scopeId: string, scopeDigest: string) =>
    sessionRequest(`/api/sessions/${encodeURIComponent(id)}/assessment/approve`, {
      method: "POST", body: JSON.stringify({ scope_id: scopeId, scope_digest: scopeDigest }),
    }),
  resumeAssessment: (id: string, scopeId: string, scopeDigest: string) =>
    sessionRequest(`/api/sessions/${encodeURIComponent(id)}/assessment/resume`, {
      method: "POST", body: JSON.stringify({ scope_id: scopeId, scope_digest: scopeDigest }),
    }),
  approvePlan: (id: string, planId: string, planDigest: string) =>
    sessionRequest(`/api/sessions/${encodeURIComponent(id)}/approve`, {
      method: "POST",
      body: JSON.stringify({ plan_id: planId, plan_digest: planDigest }),
    }),
  stopSession: (id: string) =>
    sessionRequest(`/api/sessions/${encodeURIComponent(id)}/stop`, {
      method: "POST",
      body: "{}",
    }),
  confirmInputChange: (id: string, changeId: string, changeDigest: string) =>
    sessionRequest(`/api/sessions/${encodeURIComponent(id)}/input-change/confirm`, {
      method: "POST",
      body: JSON.stringify({ change_id: changeId, change_digest: changeDigest }),
    }),
  discardInputChange: (id: string, changeId: string, changeDigest: string) =>
    sessionRequest(`/api/sessions/${encodeURIComponent(id)}/input-change/discard`, {
      method: "POST",
      body: JSON.stringify({ change_id: changeId, change_digest: changeDigest }),
    }),
  keepCurrentInputs: (id: string) =>
    sessionRequest(`/api/sessions/${encodeURIComponent(id)}/input-review/keep`, {
      method: "POST",
      body: "{}",
    }),
  proposeConditionalInputs: (id: string, selection: AnalysisSelection, revision: number) =>
    sessionRequest(`/api/sessions/${encodeURIComponent(id)}/conditional-inputs/propose`, {
      method: "POST", body: JSON.stringify({ selection, expected_revision: revision }),
    }),
  decideConditionalInputs: (id: string, action: "confirm" | "cancel" | "prepare", draftId: string, digest: string, revision: number) =>
    sessionRequest(`/api/sessions/${encodeURIComponent(id)}/conditional-inputs/${action}`, {
      method: "POST", body: JSON.stringify({ draft_id: draftId, draft_digest: digest, expected_revision: revision }),
    }),
  prepareReportInputs: (id: string, draftId: string, draftDigest: string, toolId: "P0-08" | "P0-09" | "P0-10" = "P0-08") =>
    sessionRequest(`/api/sessions/${encodeURIComponent(id)}/report-inputs/prepare`, {
      method: "POST", body: JSON.stringify({ draft_id: draftId, draft_digest: draftDigest, tool_id: toolId }),
    }),
  draftScientificInputs: (id: string, uploadId: string) =>
    sessionRequest(`/api/sessions/${encodeURIComponent(id)}/scientific-inputs/draft`, {
      method: "POST", body: JSON.stringify({ upload_id: uploadId }),
    }),
  confirmScientificInputs: (id: string, draftId: string, draftDigest: string) =>
    sessionRequest(`/api/sessions/${encodeURIComponent(id)}/scientific-inputs/confirm`, {
      method: "POST", body: JSON.stringify({ draft_id: draftId, draft_digest: draftDigest }),
    }),
  reviseScientificInputs: (id: string, draftId: string, draftDigest: string, candidate: ScienceCandidate) =>
    sessionRequest(`/api/sessions/${encodeURIComponent(id)}/scientific-inputs/revise`, {
      method: "POST", body: JSON.stringify({ draft_id: draftId, draft_digest: draftDigest, candidate }),
    }),
  answerClarification: (id: string, cardId: string, cardDigest: string, answers: ClarificationAnswer[]) =>
    sessionRequest(`/api/sessions/${encodeURIComponent(id)}/clarification/answer`, {
      method: "POST", body: JSON.stringify({ card_id: cardId, card_digest: cardDigest, answers }),
    }),
  cancelClarification: (id: string, cardId: string, cardDigest: string) =>
    sessionRequest(`/api/sessions/${encodeURIComponent(id)}/clarification/cancel`, {
      method: "POST", body: JSON.stringify({ card_id: cardId, card_digest: cardDigest }),
    }),
  reviseClarification: (id: string, cardId: string, cardDigest: string) =>
    sessionRequest(`/api/sessions/${encodeURIComponent(id)}/clarification/revise`, {
      method: "POST", body: JSON.stringify({ card_id: cardId, card_digest: cardDigest }),
    }),
  getIntake: (id: string, uploadId: string, signal?: AbortSignal) =>
    request<IntakeResponse>(`/api/sessions/${encodeURIComponent(id)}/intake?upload_id=${encodeURIComponent(uploadId)}`, { signal }),
  parseIntake: (id: string, uploadId: string) =>
    sessionRequest(`/api/sessions/${encodeURIComponent(id)}/intake/parse`, {
      method: "POST", body: JSON.stringify({ upload_id: uploadId }),
    }),
  answerIntake: (id: string, uploadId: string, revision: number, field: keyof IntakeFacts, value: string | number, other: boolean) =>
    request<IntakeResponse>(`/api/sessions/${encodeURIComponent(id)}/intake/answer`, {
      method: "POST", body: JSON.stringify({ upload_id: uploadId, revision, field, value, other }),
    }),
  uploadProtocol: (id: string, uploadId: string, file: File) => {
    const body = new FormData();
    body.set("file", file);
    return sessionRequest(`/api/sessions/${encodeURIComponent(id)}/intake/protocols?upload_id=${encodeURIComponent(uploadId)}`, { method: "POST", body });
  },
  protocolAction: (id: string, uploadId: string, protocolId: string, revision: number, command: ProtocolAction) => {
    const { action, ...payload } = command;
    return sessionRequest(`/api/sessions/${encodeURIComponent(id)}/intake/protocols/${action}`, {
      method: "POST", body: JSON.stringify({ upload_id: uploadId, protocol_id: protocolId, revision, ...payload }),
    });
  },
  protocolDownload: (id: string, uploadId: string, protocolId: string, versionId: string, kind: string) =>
    `/api/sessions/${encodeURIComponent(id)}/intake/protocols/${encodeURIComponent(protocolId)}/versions/${encodeURIComponent(versionId)}/${encodeURIComponent(kind)}?upload_id=${encodeURIComponent(uploadId)}`,
  stageIntake: (id: string, uploadId: string, facts: IntakeFacts) =>
    sessionRequest(`/api/sessions/${encodeURIComponent(id)}/intake`, {
      method: "POST", body: JSON.stringify({ upload_id: uploadId, facts }),
    }),
  prepareIntake: (id: string, uploadId: string) =>
    sessionRequest(`/api/sessions/${encodeURIComponent(id)}/intake/prepare`, {
      method: "POST", body: JSON.stringify({ upload_id: uploadId }),
    }),
  getAnalysisInputs: (id: string, signal?: AbortSignal) =>
    request<AnalysisInputsResponse>(
      `/api/sessions/${encodeURIComponent(id)}/analysis-inputs`,
      { signal },
    ),
  saveAnalysisInputs: (id: string, selection: AnalysisSelection) =>
    sessionRequest(`/api/sessions/${encodeURIComponent(id)}/analysis-inputs`, {
      method: "POST",
      body: JSON.stringify(selection),
    }),
  uploadAnalysisObject: (
    id: string,
    input: {
      toolId: string;
      modeId: string | null;
      role: string;
      schemaRef: string;
      objectVersion: string;
      file: File;
    },
  ) => {
    const query = new URLSearchParams({
      tool_id: input.toolId,
      role: input.role,
      schema_ref: input.schemaRef,
      object_version: input.objectVersion,
    });
    if (input.modeId !== null) query.set("mode_id", input.modeId);
    const body = new FormData();
    body.append("file", input.file);
    return sessionRequest(
      `/api/sessions/${encodeURIComponent(id)}/analysis-inputs/objects?${query.toString()}`,
      { method: "POST", body },
    );
  },
  registerAnalysisAsset: (id: string, registration: AnalysisAssetRegistration) =>
    sessionRequest(`/api/sessions/${encodeURIComponent(id)}/analysis-inputs/assets`, {
      method: "POST",
      body: JSON.stringify(registration),
    }),
  prepareAnalysis: (id: string, toolId: string) =>
    sessionRequest(`/api/sessions/${encodeURIComponent(id)}/prepare-analysis`, {
      method: "POST",
      body: JSON.stringify({ tool_id: toolId }),
    }),
};
