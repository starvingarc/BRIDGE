import { useEffect, useState } from "react";
import { SourceGone, readTable } from "./qc";
import type { AnalysisDTO } from "./objects";

export const PHASES = ["G1", "S", "G2M"] as const;
export type Phase = typeof PHASES[number];
export const PHASE_LABEL: Record<Phase, string> = { G1: "G1", S: "S", G2M: "G2/M" };

/** Plain reasons the cycle scores could not be computed; an unknown code is shown as it is. */
const REASONS: Record<string, string> = {
  cell_cycle_gene_coverage_insufficient: "数据里周期基因太少",
  program_gene_coverage_insufficient: "数据里周期基因太少",
  cell_cycle_gene_identifier_ambiguous: "有周期基因对应到多个基因名",
  gene_symbol_column_missing: "找不到声明的基因名列",
  gene_symbols_invalid: "基因名不是基因符号",
  gene_symbols_not_unique: "基因名有重复",
  scanpy_cell_cycle_failed: "周期评分运行失败",
  cell_cycle_unavailable: "没有算出周期评分",
};
export const cycleReason = (code: string) => REASONS[code] ?? code;

/** Per-cell scores from the cycle table; NaN and null stay missing. */
export type CycleCells = { rows: number; ids?: (string | null)[]; s?: Float64Array; g2m?: Float64Array; phase?: (string | null)[] };
export type CycleDetail = { gone: boolean; cells: CycleCells | null; error?: string };
const cache = new Map<string, CycleDetail>();

/** Reads the per-cell cycle table of one registered cell-cycle analysis once; a 409 withdraws the analysis. */
export function useCycleCells(analysis: AnalysisDTO): CycleDetail | null {
  const [detail, setDetail] = useState<CycleDetail | null>(cache.get(analysis.id) ?? null);
  useEffect(() => {
    if (analysis.availability.status !== "available") { setDetail(null); return; }
    const known = cache.get(analysis.id);
    if (known) { setDetail(known); return; }
    const table = analysis.results.find(r => r.artifact?.kind === "table")?.artifact;
    if (!table) { setDetail({ gone: false, cells: null, error: "这次分析没有逐细胞表。" }); return; }
    setDetail(null);
    const controller = new AbortController();
    readTable(table.url, controller.signal, ["cycle_S_score", "cycle_G2M_score"] as const, ["phase", "observation_id"] as const).then(
      t => ({ gone: false, cells: { rows: t.rows, ids: t.observation_id, s: t.cycle_S_score, g2m: t.cycle_G2M_score, phase: t.phase } }),
      (failure: unknown): CycleDetail => failure instanceof SourceGone ? { gone: true, cells: null }
        : { gone: false, cells: null, error: failure instanceof Error ? failure.message : "逐细胞表读取失败。" },
    ).then(next => { if (controller.signal.aborted) return; cache.set(analysis.id, next); setDetail(next); });
    return () => controller.abort();
  }, [analysis.id, analysis.availability.status]); // eslint-disable-line react-hooks/exhaustive-deps
  return detail;
}

/** The sample's own UMAP, with each cell's cluster; positions are joined to other tables by observation id, never by row. */
export type CellMapCells = { ids: (string | null)[]; x: Float64Array; y: Float64Array; cluster?: (string | null)[] };
const maps = new Map<string, CellMapCells | null>();

/** Reads the UMAP of one registered cell-atlas analysis once; anything unreadable or incomplete gives null, so no map is drawn. */
export function useCellMap(analysis: AnalysisDTO | undefined): CellMapCells | null {
  const [cells, setCells] = useState<CellMapCells | null>(analysis ? maps.get(analysis.id) ?? null : null);
  useEffect(() => {
    if (!analysis || analysis.availability.status !== "available") { setCells(null); return; }
    if (maps.has(analysis.id)) { setCells(maps.get(analysis.id)!); return; }
    // The atlas also carries its marker table; the coordinates are in the per-cell table only.
    const table = analysis.results.find(r => r.artifact?.kind === "table" && r.artifact.name === "expression_cells.parquet")?.artifact;
    if (!table) { setCells(null); return; }
    const controller = new AbortController();
    readTable(table.url, controller.signal, ["umap_1", "umap_2"] as const, ["observation_id", "leiden"] as const).then(
      t => t.umap_1 && t.umap_2 && t.observation_id ? { ids: t.observation_id, x: t.umap_1, y: t.umap_2, cluster: t.leiden } : null,
      () => null,
    ).then(next => { if (controller.signal.aborted) return; maps.set(analysis.id, next); setCells(next); });
    return () => controller.abort();
  }, [analysis?.id, analysis?.availability.status]); // eslint-disable-line react-hooks/exhaustive-deps
  return cells;
}

/** For each map cell, the row of the same cell in another table, or -1; matched by observation id only. */
export function joinRows(map: CellMapCells, ids: (string | null)[] | undefined) {
  const row = new Map<string, number>();
  ids?.forEach((id, i) => { if (id !== null) row.set(id, i); });
  return Int32Array.from(map.ids, id => id === null ? -1 : row.get(id) ?? -1);
}
