import type { Session, SessionsResponse } from "./types";

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
  createSession: () => request<Session>("/api/sessions", { method: "POST" }),
  getSession: (id: string, signal?: AbortSignal) =>
    request<Session>(`/api/sessions/${encodeURIComponent(id)}`, { signal }),
  upload: (id: string, file: File) => {
    const body = new FormData();
    body.append("file", file);
    return request<Session>(`/api/sessions/${encodeURIComponent(id)}/uploads`, {
      method: "POST",
      body,
    });
  },
  sendMessage: (id: string, text: string) =>
    request<Session>(`/api/sessions/${encodeURIComponent(id)}/messages`, {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
  approvePlan: (id: string, planId: string, planDigest: string) =>
    request<Session>(`/api/sessions/${encodeURIComponent(id)}/approve`, {
      method: "POST",
      body: JSON.stringify({ plan_id: planId, plan_digest: planDigest }),
    }),
};
