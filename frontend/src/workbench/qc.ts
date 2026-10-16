import { useEffect, useState } from "react";
import { parquetMetadata, parquetReadObjects, parquetSchema } from "hyparquet";
import type { AnalysisDTO, QcSummaryDTO } from "./objects";

/** Whether the data can be used downstream, as the QC tool judged it; no score is derived from it. */
export const READINESS: Record<string, { label: string; tone: "ok" | "warn" | "bad" | "muted" }> = {
  ready: { label: "可用", tone: "ok" }, limited: { label: "有限", tone: "warn" }, blocked: { label: "不可用", tone: "bad" },
  not_assessed: { label: "未评估", tone: "muted" }, not_applicable: { label: "不适用", tone: "muted" },
};

/** The five per-cell metrics: the median in the summary, and the column the charts are drawn from. */
export const METRICS = [
  { median: "total_counts_median", column: "total_counts", label: "总计数", unit: "count" },
  { median: "detected_genes_median", column: "detected_genes", label: "检测基因", unit: "count" },
  { median: "mitochondrial_fraction_median", column: "mitochondrial_fraction", label: "线粒体占比", unit: "fraction" },
  { median: "ribosomal_fraction_median", column: "ribosomal_fraction", label: "核糖体占比", unit: "fraction" },
  { median: "top_20_gene_fraction_median", column: "top_20_gene_fraction", label: "前 20 基因占比", unit: "fraction" },
] as const;
export type MetricColumn = typeof METRICS[number]["column"];

export const ASSESSMENTS: Record<string, string> = {
  upstream_library_qc: "上游文库 QC", doublet_assessment: "双细胞", cell_calling_assessment: "细胞判定", ambient_assessment: "环境 RNA",
};
const STATES: Record<string, string> = { not_assessed: "未评估", candidate: "有候选结果", unavailable: "不可用", not_implemented: "暂未实现" };
export const assessmentState = (state: string) => STATES[state] ?? state;

/** Plain reasons for what QC could not assess; an unknown code is shown as it is rather than guessed. */
const REASONS: Record<string, string> = {
  upstream_report_not_provided: "未提供测序公司的文库报告",
  capture_id_not_declared: "未声明 capture 标识",
  sample_id_not_declared: "未声明 sample 标识",
  droplet_module_not_executed: "输入是计数矩阵，没有液滴层面的数据",
  biological_unit_lineage_metadata_missing: "缺少生物学样本来源信息",
  measurement_spec_not_selected: "未选定 QC 测量规范，不做候选标记",
  insufficient_cells_for_scrublet: "细胞太少，不足以估计双细胞",
  insufficient_cells_per_capture_for_scrublet: "有的捕获批次细胞太少，不足以估计双细胞",
  scrublet_not_requested: "这次 QC 没有运行双细胞检测",
  scrublet_execution_failed: "双细胞检测运行失败",
};
export const reason = (code: string) => REASONS[code] ?? code;
/** What a missing input stops, for the rows of the "not assessed" list. */
export const MISSING: Record<string, string> = { biological_unit_lineage_metadata_missing: "样本来源", measurement_spec_not_selected: "候选标记" };

export const formatMetric = (value: number | null, unit: "count" | "fraction") =>
  value === null ? "—" : unit === "fraction" ? `${(value * 100).toFixed(1)}%` : Math.round(value).toLocaleString("en-US");

export const median = (summary: QcSummaryDTO, name: string) => summary.metrics.find(m => m.metric_name === name)?.raw_value ?? null;

/** Scrublet's doublet candidates for one capture; its threshold belongs to that capture only. */
export type DoubletCapture = {
  captureId: string; cells: number; predicted: number; threshold: number | null; expectedRate: number | null;
  /** Scores of the doublets Scrublet simulated from this capture, binned; null when absent or malformed. */
  simulated: { counts: number[]; edges: number[] } | null;
};
/** The doublet assessment of a QC, when it produced candidates: counted over cells with any counts. */
export type DoubletSummary = { assessed: number; predicted: number; fraction: number | null; emptyCells: number; method: string; captures: DoubletCapture[] };

/** What the redacted QC profile says about missing inputs; anything malformed is simply left out. */
export type QcReasons = { assessments: Record<string, string>; warnings: string[]; missing: string[]; doublet: DoubletSummary | null };
const num = (value: unknown) => typeof value === "number" && Number.isFinite(value) ? value : null;
/** A binned histogram whose edges are one longer than its counts, all finite; otherwise null. */
function histogram(value: unknown): DoubletCapture["simulated"] {
  const h = value && typeof value === "object" ? value as { counts?: unknown; bin_edges?: unknown } : {};
  const counts = Array.isArray(h.counts) ? h.counts.map(num) : [], edges = Array.isArray(h.bin_edges) ? h.bin_edges.map(num) : [];
  if (!counts.length || edges.length !== counts.length + 1 || [...counts, ...edges].some(v => v === null)) return null;
  return { counts: counts as number[], edges: edges as number[] };
}
export function profileReasons(profile: unknown): QcReasons {
  const record = (value: unknown): Record<string, unknown> => value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
  const strings = (value: unknown) => Array.isArray(value) ? value.filter((v): v is string => typeof v === "string") : [];
  const p = record(profile);
  const assessments: Record<string, string> = {};
  for (const field of Object.keys(ASSESSMENTS)) {
    const why = record(p[field]).reason;
    if (typeof why === "string") assessments[field] = why;
  }
  const d = record(p.doublet_assessment);
  const doublet: DoubletSummary | null = d.state === "candidate" && num(d.n_assessed) !== null && num(d.n_predicted) !== null ? {
    assessed: num(d.n_assessed)!, predicted: num(d.n_predicted)!, fraction: num(d.fraction_predicted), emptyCells: num(d.n_not_assessed_empty_counts) ?? 0,
    method: [typeof d.method === "string" ? d.method : "Scrublet", typeof d.method_version === "string" ? d.method_version : ""].join(" ").trim(),
    captures: (Array.isArray(d.per_capture) ? d.per_capture : []).map(record).flatMap(c => num(c.n_observations) === null ? [] : [{
      captureId: typeof c.capture_id === "string" ? c.capture_id : "?", cells: num(c.n_observations)!, predicted: num(c.n_predicted) ?? 0,
      threshold: num(c.threshold), expectedRate: num(c.expected_doublet_rate), simulated: histogram(c.simulated_score_histogram),
    }]),
  } : null;
  return { assessments, warnings: strings(p.warnings), missing: strings(p.missing_inputs), doublet };
}

/** One sentence under the readiness label: what passed and what is missing. */
export function readinessNote(summary: QcSummaryDTO, reasons: QcReasons | null) {
  const s = summary.schema_integrity;
  const structure = s.unique_cell_ids && s.unique_gene_ids ? "结构检查通过" : "细胞或基因标识有重复";
  const counts = summary.count_metrics_state === "measured" ? "已计算逐细胞指标" : "未计算逐细胞指标";
  const open = Object.values(summary.assessment_states).filter(state => state !== "candidate").length;
  const declared = (reasons?.warnings ?? []).map(reason);
  return `${structure}，${counts}。${declared.length ? `${declared.join("、")}；` : ""}${open ? `${open} 项上游检查未评估。` : ""}`;
}

/** Per-cell metrics read from the QC table; columns the table does not have stay absent. */
export type QcCells = Partial<Record<MetricColumn | "scrublet_score", Float64Array>> & { rows: number; scrublet_class?: (string | null)[] };
/** Tables larger than this are not parsed in the browser; they can still be downloaded. */
export const MAX_TABLE_BYTES = 48 * 1024 * 1024;

/**
 * What the panel could read for one QC. `gone` means the server refused a result file because its source changed
 * (409): the whole analysis is then withdrawn, numbers included. A plain read failure only loses that file.
 */
export type QcDetail = { gone: boolean; reasons: QcReasons | null; cells: QcCells | null; cellsError?: string };
const cache = new Map<string, QcDetail>();

/** The server's authoritative answer that a result's source changed or is missing. */
export class SourceGone extends Error {}

async function readBytes(url: string, signal: AbortSignal) {
  const response = await fetch(url, { credentials: "same-origin", cache: "no-store", signal });
  if (response.status === 409) throw new SourceGone("这次 QC 的来源文件已改变或丢失。");
  if (!response.ok) throw new Error("结果文件读取失败。");
  const size = Number(response.headers.get("content-length") ?? 0);
  if (size > MAX_TABLE_BYTES) throw new Error("逐细胞表太大，没有在浏览器里画图，可以下载查看。");
  return response.arrayBuffer();
}

/** A table value as a number; null, undefined and non-numbers stay missing (NaN), never zero. */
export const measured = (value: unknown) => {
  if (value === null || value === undefined || value === "") return NaN;
  const v = typeof value === "bigint" ? Number(value) : typeof value === "number" ? value : Number.NaN;
  return Number.isFinite(v) ? v : NaN;
};

/** A table value as text; anything else is missing. */
const text = (value: unknown) => typeof value === "string" && value ? value : null;

/**
 * The named columns of a Parquet table: numbers as Float64Array with missing values as NaN, text as strings or null.
 * Only columns the table has are read and returned; `rows` is the table's row count.
 */
export async function readTable<N extends string, T extends string>(url: string, signal: AbortSignal, numbers: readonly N[], texts: readonly T[] = []) {
  const buffer = await readBytes(url, signal);
  const metadata = parquetMetadata(buffer);
  const present = new Set(parquetSchema(metadata).children.map(child => child.element.name));
  const wanted = [...numbers, ...texts].filter(column => present.has(column));
  const rows = wanted.length ? await parquetReadObjects({ file: buffer, metadata, columns: wanted }) : [];
  const table = { rows: Number(metadata.num_rows) } as { rows: number } & Partial<Record<N, Float64Array>> & Partial<Record<T, (string | null)[]>>;
  // Missing stays missing; a column with no measured value is kept as such and simply not drawn.
  for (const column of numbers) if (present.has(column)) (table as Record<string, unknown>)[column] = Float64Array.from(rows, row => measured(row[column]));
  for (const column of texts) if (present.has(column)) (table as Record<string, unknown>)[column] = rows.map(row => text(row[column]));
  return table;
}

export const readCells = (url: string, signal: AbortSignal): Promise<QcCells> =>
  readTable(url, signal, [...METRICS.map(m => m.column), "scrublet_score"] as const, ["scrublet_class"] as const);

/** Reads the QC profile reasons and per-cell table of one registered QC; either may fail on its own. */
async function loadQcDetail(analysis: AnalysisDTO, signal: AbortSignal): Promise<QcDetail> {
  const profile = analysis.results.find(r => r.artifact?.kind === "evidence" && r.artifact.media_type === "application/json")?.artifact;
  const table = analysis.results.find(r => r.artifact?.kind === "table")?.artifact;
  let gone = false;
  const [reasons, cells] = await Promise.all([
    profile ? readBytes(profile.url, signal).then(b => profileReasons(JSON.parse(new TextDecoder().decode(b))))
      .catch((failure: unknown) => { if (failure instanceof SourceGone) gone = true; return null; }) : null,
    table ? readCells(table.url, signal).then(cells => ({ cells }), (failure: unknown) => {
      if (failure instanceof SourceGone) gone = true;
      return { cells: null, cellsError: failure instanceof Error ? failure.message : "逐细胞表读取失败。" };
    }) : { cells: null, cellsError: "这次 QC 没有逐细胞表。" },
  ]);
  return gone ? { gone: true, reasons: null, cells: null } : { gone: false, reasons, ...cells };
}

/** The QC details of several registered QCs, each read once and shared with the single-QC view; null until read. */
export function useQcDetails(analyses: AnalysisDTO[]): (QcDetail | null)[] {
  const ids = analyses.map(a => `${a.id}:${a.availability.status}`).join(",");
  const [, setRead] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    for (const analysis of analyses) {
      if (analysis.availability.status !== "available" || cache.has(analysis.id)) continue;
      void loadQcDetail(analysis, controller.signal).then(next => {
        if (controller.signal.aborted) return;
        cache.set(analysis.id, next); setRead(n => n + 1);
      });
    }
    return () => controller.abort();
  }, [ids]); // eslint-disable-line react-hooks/exhaustive-deps
  return analyses.map(a => a.availability.status === "available" ? cache.get(a.id) ?? null : null);
}

/** Reads the QC profile reasons and per-cell table of one registered QC once. */
export function useQcDetail(analysis: AnalysisDTO | undefined): QcDetail | null {
  return useQcDetails(analysis ? [analysis] : [])[0] ?? null;
}

/** Forgets what was read for a QC, so a later listing re-checks its files. */
export const forgetQc = (id: string) => { cache.delete(id); };
