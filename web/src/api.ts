import {
  normalizeSession,
  type AnalysisAssetRegistration,
  type AnalysisInputsResponse,
  type AnalysisSelection,
  type Session,
  type ClarificationAnswer,
  type ScienceCandidate,
  type IntakeFacts,
  type IntakeResponse,
  type SessionsResponse,
} from "./types";

const GENERIC_ERROR = "The request could not be completed. Please try again.";

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
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

  if (!response.ok) {
    let detail = response.status === 401 ? "Authentication required." : GENERIC_ERROR;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string" && body.detail.trim()) detail = body.detail;
    } catch {
      // Keep the stable public message for unknown or non-JSON failures.
    }
    throw new ApiError(response.status, detail);
  }

  return (await response.json()) as T;
}

const sessionRequest = async (path: string, init: RequestInit = {}) =>
  normalizeSession(await request<Session>(path, init));

export const api = {
  health: () => request<{ status: "ok" }>("/api/health"),
  login: (token: string) =>
    request<{ authenticated: true }>("/api/login", {
      method: "POST",
      body: JSON.stringify({ token }),
    }),
  logout: () =>
    request<{ authenticated: false }>("/api/logout", { method: "POST" }),
  listSessions: () => request<SessionsResponse>("/api/sessions"),
  createSession: () => sessionRequest("/api/sessions", { method: "POST" }),
  getSession: (id: string, signal?: AbortSignal) =>
    sessionRequest(`/api/sessions/${encodeURIComponent(id)}`, { signal }),
  upload: (id: string, file: File) => {
    const body = new FormData();
    body.append("file", file);
    return sessionRequest(`/api/sessions/${encodeURIComponent(id)}/uploads`, {
      method: "POST",
      body,
    });
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
