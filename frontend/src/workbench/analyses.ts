import { useEffect, useState } from "react";
import type { AnalysisDTO } from "./objects";
import { branchBars } from "./mapping";
import type { Protocol, Sample, SampleRecord } from "./types";

export type LoadAnalyses = (sampleId: string, signal: AbortSignal) => Promise<AnalysisDTO[]>;
export type SampleAnalyses = { sampleId: string; analyses?: AnalysisDTO[]; error?: string };

/** How often a sample's analyses are read again while its standard analysis is still running. */
export const ANALYSES_POLL_MS = 4000;

/**
 * Reads every analysis registered for a sample. QC is registered before mapping finishes, so the list is read again
 * while the sample is still mapping; a failed refresh keeps what was already shown.
 */
export function useSampleAnalyses(load: LoadAnalyses | undefined, sample: SampleRecord | null): SampleAnalyses | null {
  const [state, setState] = useState<SampleAnalyses | null>(null);
  const id = sample?.id ?? null, busy = sample?.status === "mapping";
  const key = sample ? `${sample.id}:${sample.status}:${sample.mapping}:${sample.revision}` : "";
  useEffect(() => {
    if (!load || !id || sample?.status === "collected") return;
    const controller = new AbortController();
    let timer = 0;
    const read = async () => {
      try {
        const analyses = await load(id, controller.signal);
        if (!controller.signal.aborted) setState({ sampleId: id, analyses });
      } catch (failure) {
        if (controller.signal.aborted) return;
        const error = failure instanceof Error ? failure.message : "分析记录读取失败。";
        setState(current => current?.sampleId === id && current.analyses ? current : { sampleId: id, error });
      }
      if (busy && !controller.signal.aborted) timer = window.setTimeout(() => void read(), ANALYSES_POLL_MS);
    };
    void read();
    return () => { controller.abort(); window.clearTimeout(timer); };
  }, [load, key]);
  return state && state.sampleId === id ? state : null;
}

/** The analyses of several samples, e.g. the batches of one day, read once per change of those samples. */
export function useManyAnalyses(load: LoadAnalyses | undefined, samples: SampleRecord[]): Map<string, SampleAnalyses> {
  const [state, setState] = useState<Map<string, SampleAnalyses>>(new Map());
  const key = samples.map(s => `${s.id}:${s.status}:${s.revision}`).join(",");
  useEffect(() => {
    if (!load) return;
    const controller = new AbortController();
    for (const sample of samples) {
      if (sample.status === "collected") continue;
      load(sample.id, controller.signal).then(
        analyses => ({ sampleId: sample.id, analyses }),
        (failure: unknown) => ({ sampleId: sample.id, error: failure instanceof Error ? failure.message : "分析记录读取失败。" }),
      ).then(next => { if (!controller.signal.aborted) setState(map => new Map(map).set(sample.id, next)); });
    }
    return () => controller.abort();
  }, [load, key]); // eslint-disable-line react-hooks/exhaustive-deps
  return state;
}

/** The address of a day's batches taken together, used where a sample id would name one batch. */
export const dayKey = (day: number) => `day-${day}`;
export const dayOf = (key: string | null | undefined) => { const m = key?.match(/^day-(\d+)$/); return m ? Number(m[1]) : null; };

/** Registered analyses of one kind, most recent registration first. Registration order is not adoption. */
export const ofKind = (analyses: AnalysisDTO[], kind: AnalysisDTO["source_kind"]) =>
  analyses.filter(a => a.source_kind === kind).sort((a, b) => b.version - a.version);

/**
 * The sampling points drawn on a run's flow: its registered samples, or for an example run one finished point per
 * mapped day so the same interaction can be tried without a server.
 */
export function samplingPoints(protocol: Protocol): SampleRecord[] {
  if (protocol.sampleRecords) return protocol.sampleRecords;
  return protocol.samples.map(s => ({ id: `example-${protocol.id}-${s.day}`, revision: 0, day: s.day, assay: "scRNA-seq", materialId: "example",
    mapping: "done" as const, status: "done" as const }));
}

/** The mapped result of a sampling point, matched by sample, never by day: several samples can share a day. */
export function resultOf(protocol: Protocol, point: SampleRecord): Sample | undefined {
  if (point.id.startsWith("example-")) return protocol.samples.find(s => s.day === point.day && !s.sampleId);
  return protocol.samples.find(s => s.sampleId === point.id);
}

/** What a sampling point's mapping says in one line: cells mapped and where most of them landed. */
export function pointSummary(protocol: Protocol, point: SampleRecord) {
  const mapping = resultOf(protocol, point)?.mapping;
  const top = mapping ? branchBars(mapping).find(b => b.key !== "off" && b.key !== "rest") : undefined;
  return { cells: mapping?.cells ?? null, lead: top ? `${top.name} ${Math.round(top.share * 100)}%` : null };
}
