import { ResearchValue } from "./ResearchValue";
import { toolName, researcherText, columnLabel, displayRecord } from "../researcherLabels";
import { Download, FileText, Image as ImageIcon, Table2 } from "lucide-react";
import { type KeyboardEvent, type ReactNode, lazy, Suspense, useEffect, useMemo, useRef, useId, useState } from "react";
import type { Artifact, ArtifactKind, Session } from "../types";
import { api } from "../api";
import { graphArtifact } from "./graphData";
import { WorkspaceFocus, type FocusTarget } from "./WorkspaceFocus";

const EvidenceGraph = lazy(() => import("./EvidenceGraph"));
const TypedFigures = lazy(() => import("./ResearchFigures").then(module => ({default: module.TypedFigures})));
const ResearchFigures = lazy(() => import("./ResearchFigures"));

const tabs: { kind: ArtifactKind; label: string }[] = [
  { kind: "figure", label: "图表" },
  { kind: "table", label: "数据表" },
  { kind: "download", label: "下载" },
];

function artifactUrl(sessionId: string, artifactId: string) {
  return `/api/sessions/${encodeURIComponent(sessionId)}/artifacts/${encodeURIComponent(artifactId)}`;
}

function isParquet(artifact: Artifact) {
  return artifact.media_type === "application/vnd.apache.parquet"
    || artifact.media_type === "application/x-parquet"
    || /\.parquet$/i.test(artifact.name);
}

function isTextPreview(artifact: Artifact) {
  return artifact.media_type.startsWith("text/")
    || artifact.media_type.includes("json")
    || /\.(?:csv|tsv|json)$/i.test(artifact.name);
}

const MAX_ARTIFACT_PREVIEW_BYTES = 200_000;
export const MAX_RESEARCH_REPORT_BYTES = 8_000_000;

export async function readBoundedText(response: Response, maxBytes = MAX_ARTIFACT_PREVIEW_BYTES) {
  const reader = response.body?.getReader();
  if (!reader) throw new Error("stream_unavailable");
  const decoder = new TextDecoder();
  let text = "";
  let bytesRead = 0;
  let truncated = false;

  try {
    while (bytesRead < maxBytes) {
      const { done, value } = await reader.read();
      if (done) {
        text += decoder.decode();
        return { text, truncated };
      }
      const remaining = maxBytes - bytesRead;
      const chunk = value.byteLength > remaining ? value.subarray(0, remaining) : value;
      text += decoder.decode(chunk, { stream: true });
      bytesRead += chunk.byteLength;
      if (value.byteLength > remaining || bytesRead === maxBytes) {
        truncated = true;
        await reader.cancel();
        break;
      }
    }
  } finally {
    reader.releaseLock();
  }

  text += decoder.decode();
  return { text, truncated };
}

function figureGroupKey(artifact: Artifact) {
  return `${artifact.tool_id}:${artifact.name.replace(/\.(?:svg|png)$/i, "")}`;
}

function isSvg(artifact: Artifact) {
  return artifact.media_type === "image/svg+xml" || /\.svg$/i.test(artifact.name);
}

function artifactsForTab(session: Session | null, kind: ArtifactKind) {
  if (!session) return [];
  const standalone = session.artifacts.filter(artifact => !graphArtifact(artifact)
    && artifact.content_class !== "developer_diagnostic" && artifact.access_state !== "denied"
    && (artifact.content_class === "research_report" ? artifact.media_type === "text/html" : ["figure", "table"].includes(artifact.kind))
    && !artifact.media_type.includes("json"));
  if (kind === "download") {
    return standalone;
  }
  if (kind !== "figure") return standalone.filter((artifact) => artifact.kind === kind);

  const figures = new Map<string, Artifact>();
  for (const artifact of standalone) {
    if (artifact.kind !== "figure") continue;
    const key = figureGroupKey(artifact);
    const current = figures.get(key);
    if (!current || (!isSvg(current) && isSvg(artifact))) figures.set(key, artifact);
  }
  return Array.from(figures.values());
}

function parseDelimited(value: string, delimiter: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let quoted = false;
  for (let index = 0; index < value.length && rows.length < 101; index += 1) {
    const char = value[index];
    if (char === "\"") {
      if (quoted && value[index + 1] === "\"") {
        cell += "\"";
        index += 1;
      } else {
        quoted = !quoted;
      }
    } else if (char === delimiter && !quoted) {
      row.push(cell);
      cell = "";
    } else if ((char === "\n" || char === "\r") && !quoted) {
      if (char === "\r" && value[index + 1] === "\n") index += 1;
      row.push(cell);
      rows.push(row.slice(0, 24));
      row = [];
      cell = "";
    } else {
      cell += char;
    }
  }
  if ((cell || row.length) && rows.length < 101) {
    row.push(cell);
    rows.push(row.slice(0, 24));
  }
  return rows;
}

type PreviewCell = string | number | boolean | null;

type ParquetPreview = {
  columns: string[];
  rows: PreviewCell[][];
  total_rows: number;
  total_columns: number;
  truncated: boolean;
};

/** Data-table headers keep the file's real column name; a known name is added above it, never instead of it. */
function ColumnHeader({ name }: { name: string }) {
  const label = columnLabel(name);
  return label ? <th scope="col" title={name}>{label}<small className="column-name">{name}</small></th>
    : <th scope="col" title={name}>{name}</th>;
}

function RenderedTable({ columns, rows }: { columns: string[]; rows: PreviewCell[][] }) {
  if (!columns.length) return <p className="artifact-text">Empty table (0 rows, 0 columns).</p>;
  return (
    <><div className="table-scroll">
      <table>
        <thead>
          <tr>{columns.map((cell, index) => <ColumnHeader key={index} name={cell} />)}</tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {row.map((cell, cellIndex) => <td key={cellIndex}><ResearchValue value={cell} field={columns[cellIndex]} empty="" /></td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div></>
  );
}

function TablePreview({ text, mediaType }: { text: string; mediaType: string }) {
  const rows = useMemo(() => {
    if (mediaType.includes("json")) {
      try {
        const parsed = JSON.parse(text) as unknown;
        if (Array.isArray(parsed) && parsed.every((item) => item && typeof item === "object")) {
          const headers = Array.from(
            new Set(parsed.slice(0, 100).flatMap((item) => Object.keys(item as object))),
          ).slice(0, 24);
          return [
            headers,
            ...parsed
              .slice(0, 100)
              .map((item) => headers.map((header) => String((item as Record<string, unknown>)[header] ?? ""))),
          ];
        }
      } catch {
        return [];
      }
      return [];
    }
    return parseDelimited(text, mediaType.includes("csv") ? "," : "\t");
  }, [mediaType, text]);

  if (!rows.length) return <pre className="artifact-text">{researcherText(text)}</pre>;
  return <RenderedTable columns={rows[0]} rows={rows.slice(1)} />;
}

function DownloadFallback({ sessionId, artifact, message }: {
  sessionId: string;
  artifact: Artifact;
  message: string;
}) {
  return (
    <div className="artifact-error">
      <p>{message}</p>
      <a href={artifactUrl(sessionId, artifact.id)} download={artifact.name}>Download original file</a>
    </div>
  );
}

function TextArtifact({ sessionId, artifact }: { sessionId: string; artifact: Artifact }) {
  const [state, setState] = useState<{
    loading: boolean;
    text: string;
    truncated: boolean;
    error: boolean;
  }>({
    loading: true,
    text: "",
    truncated: false,
    error: false,
  });

  useEffect(() => {
    const controller = new AbortController();
    let current = true;
    setState({ loading: true, text: "", truncated: false, error: false });
    fetch(artifactUrl(sessionId, artifact.id), {
      credentials: "same-origin",
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) throw new Error();
        const { text, truncated } = await readBoundedText(response);
        if (current) setState({ loading: false, text, truncated, error: false });
      })
      .catch((error: unknown) => {
        if (current && (error as { name?: string }).name !== "AbortError") {
          setState({ loading: false, text: "", truncated: false, error: true });
        }
      });
    return () => {
      current = false;
      controller.abort();
    };
  }, [artifact.id, sessionId]);

  if (state.loading) return <p className="artifact-loading">Loading preview…</p>;
  if (state.error) {
    return <DownloadFallback sessionId={sessionId} artifact={artifact} message="This artifact could not be previewed." />;
  }
  return (
    <>
      {state.truncated ? (
        <p className="artifact-truncated">Preview truncated. Download the original artifact for complete content.</p>
      ) : null}
      {artifact.kind === "table" ? (
        <TablePreview text={state.text} mediaType={artifact.media_type} />
      ) : (
        <pre className="artifact-text">{researcherText(state.text)}</pre>
      )}
    </>
  );
}

function isParquetPreview(value: unknown): value is ParquetPreview {
  if (!value || typeof value !== "object") return false;
  const preview = value as Partial<ParquetPreview>;
  return Array.isArray(preview.columns)
    && preview.columns.every((column) => typeof column === "string")
    && Array.isArray(preview.rows)
    && preview.rows.every((row) => Array.isArray(row) && row.every(
      (cell) => cell === null
        || typeof cell === "string"
        || typeof cell === "boolean"
        || (typeof cell === "number" && Number.isFinite(cell) && (
          !Number.isInteger(cell) || Number.isSafeInteger(cell)
        )),
    ))
    && Number.isSafeInteger(preview.total_rows)
    && Number.isSafeInteger(preview.total_columns)
    && typeof preview.truncated === "boolean";
}

function ParquetArtifact({ sessionId, artifact }: { sessionId: string; artifact: Artifact }) {
  const [state, setState] = useState<{
    loading: boolean;
    preview: ParquetPreview | null;
    error: boolean;
  }>({ loading: true, preview: null, error: false });

  useEffect(() => {
    const controller = new AbortController();
    let current = true;
    setState({ loading: true, preview: null, error: false });
    fetch(`${artifactUrl(sessionId, artifact.id)}/preview`, {
      credentials: "same-origin",
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) throw new Error();
        const preview: unknown = await response.json();
        if (!isParquetPreview(preview)) throw new Error();
        if (current) setState({ loading: false, preview, error: false });
      })
      .catch((error: unknown) => {
        if (current && (error as { name?: string }).name !== "AbortError") {
          setState({ loading: false, preview: null, error: true });
        }
      });
    return () => {
      current = false;
      controller.abort();
    };
  }, [artifact.id, sessionId]);

  if (state.loading) return <p className="artifact-loading">Loading preview…</p>;
  if (state.error || !state.preview) {
    return <DownloadFallback sessionId={sessionId} artifact={artifact} message="This artifact could not be previewed." />;
  }
  return (
    <>
      {state.preview.truncated ? (
        <p className="artifact-truncated">
          Preview truncated. Showing {state.preview.rows.length} of {state.preview.total_rows} rows and {state.preview.columns.length} of {state.preview.total_columns} columns. Download the original artifact for complete content.
        </p>
      ) : null}
      <RenderedTable columns={state.preview.columns} rows={state.preview.rows} />
    </>
  );
}

function ResearchSnapshotView({ sessionId, artifact }: { sessionId: string; artifact: Artifact }) {
  type Section = [string, unknown];
  const [content, setContent] = useState<{ texts: string[]; sections: Section[]; missing: number; error: boolean } | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    let current = true;
    setContent(null);
    fetch(artifactUrl(sessionId, artifact.id), { credentials: "same-origin", signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error("report_unavailable");
        const { text, truncated } = await readBoundedText(response, MAX_RESEARCH_REPORT_BYTES);
        if (truncated) throw new Error("report_too_large");
        const snapshot = JSON.parse(text);
        const binding = artifact.research_report;
        if (!binding || snapshot.snapshot_sha256 !== binding.snapshot_sha256
            || snapshot.input_revision !== binding.input_revision || snapshot.graph_version !== binding.graph_version
            || snapshot.audience !== "internal_research" || snapshot.scientific_validation !== "not_qualified"
            || typeof snapshot.report_draft_json !== "string") throw new Error("report_binding_invalid");
        const draft = JSON.parse(snapshot.report_draft_json);
        const requirements = JSON.parse(snapshot.evidence_requirement_set_json);
        if (!Array.isArray(draft.claim_blocks) || draft.claim_blocks.length > 5000
            || !draft.claim_blocks.every((row: { text?: unknown }) => typeof row.text === "string")
            || !Array.isArray(requirements.requirements)) throw new Error("report_shape_invalid");
        const sections: unknown = snapshot.object_version === "0.3.0"
          ? JSON.parse(snapshot.context_sections_json) : [];
        if (!Array.isArray(sections) || sections.length > 20
            || !sections.every((row) => Array.isArray(row) && row.length === 2
              && typeof row[0] === "string")) throw new Error("report_context_invalid");
        if (current) setContent({
          sections: sections as Section[],
          texts: draft.claim_blocks.map((row: { text: string }) => row.text),
          missing: requirements.requirements.filter((row: { state?: string }) => row.state === "open").length,
          error: false,
        });
      }).catch((error: unknown) => {
        if (current && (error as { name?: string }).name !== "AbortError") {
          setContent({ texts: [], sections: [], missing: 0, error: true });
        }
      });
    return () => { current = false; controller.abort(); };
  }, [sessionId, artifact.id, artifact.research_report?.snapshot_sha256]);
  if (!content) return <p>正在读取已核验报告…</p>;
  if (content.error) return <p>无法核对这份报告的快照绑定；当前不展示报告正文。可下载原件供核查，不能据此视为当前已核验结论。</p>;
  return <section aria-label="同版本研究报告">
    <p>以下文字与离线报告读取同一份证据快照。尚有 {content.missing} 项开放证据要求。</p>
    {content.texts.map((text, index) => <p key={index}>{researcherText(text)}</p>)}
    {content.sections.map(([title, value], index) => <details key={index}>
      <summary>{title}</summary><pre>{JSON.stringify(displayRecord(value), null, 2)}</pre>
    </details>)}
  </section>;
}

export function ArtifactCard({ sessionId, artifact, view = artifact.kind }: {
  sessionId: string; artifact: Artifact; view?: ArtifactKind;
}) {
  const [confirmation, setConfirmation] = useState<{ source: Artifact; sessionId: string; value: Artifact } | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [confirmationError, setConfirmationError] = useState<string | null>(null);
  const effective = confirmation?.source === artifact && confirmation.sessionId === sessionId ? confirmation.value : artifact;
  const url = artifactUrl(sessionId, artifact.id);
  const historical = effective.access_state === "historical_unreviewed";
  const mustConfirm = effective.acknowledgement_required === true || (historical && effective.acknowledged !== true);
  async function acknowledge() {
    setConfirming(true);
    setConfirmationError(null);
    try {
      const updated = await api.acknowledgeArtifact(sessionId, artifact.id);
      if (updated.id !== artifact.id || updated.access_state !== "historical_unreviewed"
          || updated.acknowledged !== true || updated.acknowledgement_required !== false) {
        throw new Error("历史版本状态已变化，请刷新后重新核对。");
      }
      setConfirmation({ source: artifact, sessionId, value: updated });
    } catch (error) {
      setConfirmationError(error instanceof Error ? error.message : "历史版本确认未完成，请重试。");
    } finally {
      setConfirming(false);
    }
  }
  if (effective.access_state === "denied" || effective.content_class === "developer_diagnostic") return null;
  if (historical || mustConfirm) return <article className="artifact-card">
    <header><div><h2>{researcherText(artifact.name)}</h2><p>历史报告 · 尚未按当前输入和证据重新核对</p></div></header>
    <p role="note">{effective.warning ?? "这是历史报告，尚未按当前输入和证据重新核对。确认后仅开放历史原件，不代表当前结论。"}</p>
    {confirmationError ? <p role="alert">{confirmationError}</p> : null}
    {mustConfirm ? <button type="button" disabled={confirming} onClick={() => void acknowledge()}>
      {confirming ? "正在确认历史版本…" : "我已了解，开放历史原件下载"}
    </button> : <>
      <p>已确认历史版本提示。以下仅供追溯，不是当前已核验报告。</p>
      <a className="download-row" href={url} download={artifact.name}>下载历史原件：{researcherText(artifact.name)}</a>
    </>}
  </article>;
  return <article className="artifact-card">
    <header><div><h2>{researcherText(artifact.name)}</h2><p>{artifact.research_report
      ? `研究报告 · 资料版本 ${artifact.research_report.input_revision}`
      : toolName(artifact.tool_id)}</p></div>
      <a href={url} download={artifact.name} aria-label={`Download ${researcherText(artifact.name)}`}><Download aria-hidden="true" /></a>
    </header>
    {artifact.research_report && artifact.media_type === "application/json"
      ? <ResearchSnapshotView sessionId={sessionId} artifact={artifact} />
      : view === "figure" ? <img src={url} alt={researcherText(artifact.name)} />
      : view === "download" ? <a className="download-row" href={url} download={artifact.name}>
        <FileText aria-hidden="true" /><span>Download original file</span><Download aria-hidden="true" /></a>
      : isParquet(artifact) ? <ParquetArtifact sessionId={sessionId} artifact={artifact} />
      : isTextPreview(artifact) ? <TextArtifact sessionId={sessionId} artifact={artifact} />
      : <DownloadFallback sessionId={sessionId} artifact={artifact} message="A browser preview is not available for this artifact." />}
  </article>;
}

function ReportPreview({sessionId, artifact}: {sessionId: string; artifact: Artifact}) {
  const [content, setContent] = useState<{html?: string; failed?: boolean} | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    let current = true;
    setContent(null);
    fetch(artifactUrl(sessionId, artifact.id), {credentials: "same-origin", signal: controller.signal})
      .then(async response => {
        if (!response.ok) throw new Error("report_unavailable");
        const {text, truncated} = await readBoundedText(response, MAX_RESEARCH_REPORT_BYTES);
        if (truncated) throw new Error("report_too_large");
        if (current) setContent({html: text});
      }).catch(() => { if (current && !controller.signal.aborted) setContent({failed: true}); });
    return () => {current = false; controller.abort();};
  }, [sessionId, artifact.id, artifact.research_report?.snapshot_sha256]);
  if (!content) return <p role="status">正在打开同版本报告…</p>;
  if (content.failed) return <p role="status">报告暂时无法预览。已有结果保留，可刷新或下载原件核对。</p>;
  // Render the verified artifact itself. The opaque sandbox prohibits scripts,
  // same-origin access, forms, top-level navigation and downloads from the report.
  return <iframe className="research-report-frame" sandbox="" referrerPolicy="no-referrer"
    title={`研究报告 · 资料版本 ${artifact.research_report!.input_revision}`} srcDoc={content.html} />;
}

function ResearchReports({session}: {session: Session}) {
  const reports = session.artifacts.filter(artifact => artifact.content_class === "research_report"
    && artifact.access_state !== "denied");
  const pending = session.input_review_required || session.assessment?.freshness.state === "review_pending";
  const current = reports.filter(artifact => artifact.access_state === "current" && artifact.research_report
    && !pending && (!session.assessment || (session.assessment.freshness.state === "current"
      && artifact.research_report.input_revision === String(session.assessment.input_revision))));
  const groups = new Map<string, Artifact[]>();
  for (const artifact of current) {
    const binding = artifact.research_report!;
    const key = `${binding.input_revision}:${binding.graph_version}:${binding.snapshot_sha256}`;
    groups.set(key, [...(groups.get(key) ?? []), artifact]);
  }
  // Artifacts are appended in tool-run order. One input revision can have
  // several interpretation/report snapshots; only the newest is the reader default.
  const editions = [...groups.entries()];
  const earlier = editions.slice(0, -1).reverse().flatMap(([, artifacts]) => artifacts)
    .filter(artifact => artifact.media_type === "text/html");
  const historical = [...earlier, ...reports.filter(artifact =>
    artifact.access_state === "historical_unreviewed" && artifact.media_type === "text/html")];
  return <section className="research-reports" aria-label="研究报告与版本">

    {pending ? <p role="status" className="report-empty">输入更正待确认，报告暂不作为当前结果展示。请先核对更正。</p>
      : !groups.size ? <div className="report-empty"><FileText aria-hidden="true" /><h3>尚无当前版本报告</h3>
        <p>在评估范围中选择研究报告；完成有来源的解释后，按可用操作继续生成。</p></div> : null}
    {editions.slice(-1).map(([key, artifacts]) => {
      const binding = artifacts[0].research_report!;
      const html = artifacts.find(artifact => artifact.media_type === "text/html");

      return <article className="report-edition" key={key}>
        <div className="report-edition-heading"><div><span className="report-current">最新报告</span>
          <h3>资料版本 {binding.input_revision}</h3></div>
          <div className="report-formats" aria-label="下载同版本报告">{artifacts.filter(artifact => artifact.media_type === "text/html").map(artifact =>
            <a key={artifact.id} href={artifactUrl(session.id, artifact.id)} download={artifact.name}>
              <Download aria-hidden="true" />{artifact.media_type === "text/html" ? "离线阅读"
                : artifact.name.split(".").pop()?.toUpperCase() ?? "原件"}</a>)}</div></div>
        {html ? <ReportPreview key={session.id + html.id} sessionId={session.id} artifact={html} />
          : <p>本版本暂未提供可阅读报告。</p>}
      </article>;
    })}
    {historical.length > 0 && <details className="report-history"><summary>历史报告 · {historical.length} 个文件</summary>
      <p>较早报告按原始版本保留；资料已更改的报告需先确认历史提示。</p>
      {historical.map(artifact => <ArtifactCard key={artifact.id} sessionId={session.id} artifact={artifact} />)}
    </details>}
  </section>;
}

function EmptyResults({ kind }: { kind: ArtifactKind }) {
  const Icon =
    kind === "figure" ? ImageIcon : kind === "table" ? Table2 : kind === "download" ? Download : FileText;
  const label = tabs.find((tab) => tab.kind === kind)?.label.toLowerCase();
  return (
    <div className="results-empty">
      <div className="results-empty-icon">
        <Icon aria-hidden="true" />
      </div>
      <h2>{kind === "figure" ? "Results will appear here" : `No ${label} yet`}</h2>
      <p>
        {kind === "figure"
          ? "Figures are generated by the analysis tools."
          : "Results produced by approved analysis tools will appear here."}
      </p>
    </div>
  );
}

export function ResultsPane({ session, overview, overviewRequest = 0, workspaceView, initialTab, onNavigate }: {
  session: Session | null; overview?: ReactNode | ((openGraph: (citation: string) => void, openReports: () => void) => ReactNode); overviewRequest?: number;
  workspaceView?: "context" | "results";
  initialTab?: "report";
  onNavigate?: (target: FocusTarget) => void;
}) {
  const [activeTab, setActiveTab] = useState<ArtifactKind | "overview" | "graph" | "report">(initialTab ?? (overview ? "overview" : "figure"));
  const [graphCitation, setGraphCitation] = useState<string | null>(null);
  const openGraph = (citation: string) => {
    setGraphCitation(citation); setActiveTab("graph");
    panel.current?.scrollIntoView?.({ block: "nearest" });
    panel.current?.focus({ preventScroll: true });
  };
  const openReports = () => {
    setActiveTab("report");
    panel.current?.scrollIntoView?.({block: "nearest"});
    panel.current?.focus({preventScroll: true});
  };
  const hasReports = Boolean(overview || session?.artifacts.some(artifact => artifact.content_class === "research_report"));
  const [showOriginalFigures, setShowOriginalFigures] = useState(false);
  const panel = useRef<HTMLDivElement>(null);
  const tablist = useRef<HTMLDivElement>(null);
  const prefix = useId();
  const tabItems: Array<{ kind: ArtifactKind | "overview" | "graph" | "report"; label: string }> = [
    ...(overview ? [{ kind: "overview" as const, label: "评估概览" }] : []),
    ...((session && (session.artifacts.some(graphArtifact) || graphCitation !== null)) ? [{ kind: "graph" as const, label: "结果依据" }] : []),
    ...(hasReports ? [{kind: "report" as const, label: "研究报告"}] : []), ...tabs,
  ];
  const artifacts = useMemo(() => activeTab === "overview" || activeTab === "graph" || activeTab === "report" ? [] : artifactsForTab(session, activeTab), [activeTab, session]);

  useEffect(() => {
    if (!overviewRequest || !overview) return;
    setActiveTab("overview");
    panel.current?.scrollIntoView?.({ block: "nearest" });
    panel.current?.focus({ preventScroll: true });
  }, [overviewRequest]);

  useEffect(() => {
    if (workspaceView) setActiveTab(workspaceView === "context" ? "overview" : initialTab ?? "figure");
  }, [workspaceView, initialTab]);

  const navigate = (target: FocusTarget) => {
    if (target === "overview") {
      setActiveTab("overview");
      panel.current?.focus({ preventScroll: true });
    } else onNavigate?.(target);
  };
  const onTabKey = (event: KeyboardEvent<HTMLDivElement>) => {
    const current = tabItems.findIndex(tab => tab.kind === activeTab);
    const next = event.key === "ArrowRight" ? (current + 1) % tabItems.length
      : event.key === "ArrowLeft" ? (current - 1 + tabItems.length) % tabItems.length
      : event.key === "Home" ? 0 : event.key === "End" ? tabItems.length - 1 : -1;
    if (next < 0) return;
    event.preventDefault();
    setActiveTab(tabItems[next].kind);
    tablist.current?.querySelectorAll<HTMLButtonElement>('[role="tab"]')[next]?.focus();
  };

  return (
    <section className="results-pane" aria-label="Analysis results">
      <header className="results-header">
        <h1>{workspaceView === "context" ? "实验背景" : overview ? "研究结果" : "Your findings"}</h1>
        {session?.presentation?.stage === "results_ready"
          ? <span className="results-ready" role="status">结果已就绪</span>
          : <span className="results-index" aria-hidden="true">↗</span>}
      </header>
      {session && session.presentation?.stage !== "results_ready" ? <WorkspaceFocus session={session} onNavigate={navigate} /> : null}
      <div className="result-tabs" ref={tablist} role="tablist" aria-label="Result type" onKeyDown={onTabKey}>
        {tabItems.map(tab => {
          const count = tab.kind === "overview" || tab.kind === "graph" || tab.kind === "report" ? 0 : artifactsForTab(session, tab.kind).length;
          return <button key={tab.kind} id={prefix + "-" + tab.kind} type="button" role="tab"
            aria-selected={activeTab === tab.kind} aria-controls={prefix + "-panel-" + tab.kind}
            tabIndex={activeTab === tab.kind ? 0 : -1}
            className={activeTab === tab.kind ? "result-tab--active" : ""}
            onClick={() => setActiveTab(tab.kind)}>
            {tab.label}{count ? <span>{count}</span> : null}
          </button>;
        })}
      </div>
      <div className="results-content" ref={panel} tabIndex={-1}>
        {overview ? <div role="tabpanel" id={prefix + "-panel-overview"}
          aria-labelledby={prefix + "-overview"} hidden={activeTab !== "overview"}>
          {typeof overview === "function" ? overview(openGraph, openReports) : overview}
        </div> : null}
        {(session && (session.artifacts.some(graphArtifact) || graphCitation !== null)) ? <div role="tabpanel" id={prefix + "-panel-graph"}
          aria-labelledby={prefix + "-graph"} hidden={activeTab !== "graph"}>
          {activeTab === "graph" ? <Suspense fallback={<p role="status">正在加载结果依据…</p>}>
            <EvidenceGraph key={session.id} session={session} citation={graphCitation} />
          </Suspense> : null}
        </div> : null}
        {hasReports && <div role="tabpanel" id={prefix + "-panel-report"}
          aria-labelledby={prefix + "-report"} hidden={activeTab !== "report"}>
          {activeTab === "report" && session ? <ResearchReports key={session.id} session={session} /> : null}
        </div>}
        {tabs.map(tab => <div key={tab.kind} role="tabpanel" id={prefix + "-panel-" + tab.kind}
          aria-labelledby={prefix + "-" + tab.kind} hidden={activeTab !== tab.kind}>
          {activeTab === tab.kind ? tab.kind === "figure" && session ? (
            <><Suspense fallback={<p role="status">正在加载已保存图表…</p>}>
              {session.artifacts.some(a => a.name.startsWith("qc_visualization_artifact_set.")) &&
                <section className="research-figures" aria-label="输入质控结果"><h3>输入质控</h3><TypedFigures session={{...session, artifacts: session.artifacts.filter(
                  a => a.name.startsWith("qc_visualization_artifact_set."))}} /></section>}
              {(session.assessment || !session.artifacts.some(a => /^(expression|qc)_visualization_artifact_set\./.test(a.name))) &&
                <ResearchFigures key={session.id} session={{...session, artifacts: session.artifacts.filter(
                  a => !a.name.startsWith("qc_visualization_artifact_set."))}} />}
              {session.artifacts.some(a => a.name.startsWith("expression_visualization_artifact_set.")) &&
                <section className="research-figures" aria-label="表达探索结果"><h3>表达探索结果</h3><TypedFigures session={{...session, artifacts: session.artifacts.filter(
                  a => a.name.startsWith("expression_visualization_artifact_set."))}} /></section>}</Suspense>
            <details onToggle={event => setShowOriginalFigures(event.currentTarget.open)}><summary>全部原始图像附件（独立查看）</summary>
              {showOriginalFigures && <div className="artifact-grid artifact-grid--figure">{session.artifacts.filter(a => a.kind === "figure" && !graphArtifact(a)).map(a =>
                <ArtifactCard key={a.id} sessionId={session.id} artifact={a} view="figure" />)}</div>}
            </details></>
          ) : !session || !artifacts.length ? <EmptyResults kind={tab.kind} /> : (
            <div className={`artifact-grid artifact-grid--${tab.kind}`}>
              {artifacts.map(artifact => <ArtifactCard key={artifact.id} sessionId={session.id} artifact={artifact} view={tab.kind} />)}
            </div>
          ) : null}
        </div>)}
      </div>
    </section>
  );
}
