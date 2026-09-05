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
};

export type PlanStep = {
  id: string;
  tool_id: string;
  label: string;
  status: "pending" | "running" | "succeeded" | "failed" | "skipped";
  reason: string | null;
};

export type Plan = {
  id: string;
  digest: string;
  status: "proposed" | "approved" | "completed" | "failed";
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

export type Session = {
  id: string;
  title: string;
  updated_at: string;
  status: SessionStatus;
  messages: Message[];
  uploads: Upload[];
  plan: Plan | null;
  artifacts: Artifact[];
  error: string | null;
};

export type SessionSummary = Pick<Session, "id" | "title" | "updated_at">;

export type SessionsResponse = {
  sessions: SessionSummary[];
};
