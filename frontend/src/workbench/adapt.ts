/** Converts contract objects into the view model the workbench components render. */
import type { AssessmentDTO, FormalizationDTO, ProtocolDTO, ProtocolVersionDTO, ReagentDTO, RunDTO, WorkbenchDTO } from "./objects";
import { mappingNote, mappingView } from "./mapping";
import { CHAIN_NAMES, weakestLevel } from "./stages";
import type { ChainValues, CultureState, MappingStatus, Protocol, ProtocolSource, QueueItem, Reagent, ReviewItem, Sample, SampleRecord, SampleStatus, SourceQuote, SourceView, StageWindow } from "./types";

const STATE: Record<RunDTO["state"], CultureState> = {
  planned: "draft", expanding: "expanding", differentiating: "differentiating", frozen: "frozen", grafted: "grafted", ended: "differentiating",
};

const reagents = (version: ProtocolVersionDTO): Reagent[] => version.reagents.map((r, i) => ({
  id: r.id ?? `unsaved-${i}`, name: r.name, short: r.short, pathway: r.pathway, kind: r.kind, dose: r.dose_text,
  start: r.start_day, end: r.end_day, catalogId: r.catalog_id ?? undefined, unconfirmed: r.unconfirmed?.length ? r.unconfirmed : undefined,
  sourceLocator: r.source_locator ?? undefined,
  ...(r.timing_text ? { timingText: r.timing_text } : {}),
  ...(r.field_provenance?.some(f => f.kind === "recipe_reference") ? { recipeRefs: r.field_provenance.filter(f => f.kind === "recipe_reference").map(f => ({ field: f.field, locator: f.recipe_locator ?? f.source_locator })) } : {}),
  ...(r.field_provenance?.length ? { provenance: { entries: r.field_provenance, dose: r.dose_text, start: r.start_day, end: r.end_day } } : {}),
}));

const SERVER_ID = /^[a-f0-9]{32}$/;

const AVAILABILITY: Record<string, string> = {
  standard_mapping_not_configured: "标准图谱映射暂不可用",
  mapping_input_required: "还差数据说明",
  mapping_reference_unavailable: "没有对应的参考数据",
  mapping_tree_mismatch: "发育树版本已更新，暂不能映射",
  mapping_worker_busy: "映射任务已满，稍后重试",
};
/** Reason mapping cannot run yet; it is a missing capability, never a failed or running assessment. */
export const availabilityText = (code: string) => AVAILABILITY[code] ?? "图谱映射暂不可用";

/** Custom stage windows of a version; malformed entries are ignored so the defaults show instead. */
const stagesOf = (version: ProtocolVersionDTO): StageWindow[] | undefined => {
  const list = (version.stages ?? []).filter(s => [1, 2, 3, 4].includes(s.index) && Number.isFinite(s.start_day) && Number.isFinite(s.end_day) && s.start_day <= s.end_day)
    .map(s => ({ index: s.index as StageWindow["index"], start: s.start_day, end: s.end_day })).sort((a, b) => a.index - b.index);
  return list.length ? list : undefined;
};

/** View reagents back to contract shape; client-side placeholder IDs are dropped so the server assigns them. */
export const reagentsToDTO = (list: Reagent[]): ReagentDTO[] => list.map(r => ({
  ...(SERVER_ID.test(r.id) ? { id: r.id } : {}), name: r.name, short: r.short, pathway: r.pathway, kind: r.kind,
  dose_text: r.dose, start_day: r.start, end_day: r.end, catalog_id: r.catalogId ?? null, unconfirmed: r.unconfirmed ?? [],
  ...(r.sourceLocator ? { source_locator: r.sourceLocator } : {}),
  ...(r.timingText ? { timing_text: r.timingText } : {}),
  ...(r.provenance ? { field_provenance: keptProvenance(r) } : {}),
}));

/** A changed dose or day drops its old source; the contract forbids keeping a source for a value it did not give. */
function keptProvenance(r: Reagent) {
  const p = r.provenance!;
  const same = { dose_text: r.dose === p.dose, start_day: r.start === p.start, end_day: r.end === p.end };
  return p.entries.filter(entry => same[entry.field]);
}

const REVIEW: readonly string[] = ["source_review", "total_days", "stages", "operations"];

const sourceOf = (protocol: ProtocolDTO, version: ProtocolVersionDTO): ProtocolSource => ({
  protocolId: protocol.id, versionId: version.id, status: version.status, protocolRevision: protocol.revision,
  versionRevision: version.revision, totalDaysSet: (version.total_days ?? 0) > 0,
  review: (version.unconfirmed ?? []).filter((item): item is ReviewItem => REVIEW.includes(item)),
  hasSource: !!(version.provenance?.material_id || version.provenance?.formalization_version_id),
});

/** Source record for the source pane: unique original segments, every quoted value, and questions still open. */
export function sourceView(dto: FormalizationDTO): SourceView {
  const segments = new Map<string, SourceView["segments"][number]>();
  for (const holder of [...(dto.steps ?? []), ...(dto.questions ?? [])])
    for (const s of holder.sources ?? []) if (!segments.has(s.id)) segments.set(s.id, { id: s.id, label: s.label, location: s.location, text: s.text });
  const p = dto.projection ?? {};
  const quotes: SourceQuote[] = [
    ...(p.reagents ?? []).map(r => ({ kind: "reagent" as const, text: r.quote ?? "", name: r.name })),
    ...(p.total_days?.quote ? [{ kind: "total" as const, text: p.total_days.quote }] : []),
    ...(p.stages ?? []).map(s => ({ kind: "stage" as const, text: s.quote ?? "" })),
    ...(p.operations ?? []).map(o => ({ kind: "operation" as const, text: o.quote ?? "" })),
  ].filter(q => q.text);
  return {
    segments: [...segments.values()], quotes,
    questions: (dto.questions ?? []).filter(q => q.answer_state !== "answered").map(q => q.title),
    compiled: dto.compiler_state === "passed", needsInput: dto.coverage_state === "needs_input",
  };
}

/**
 * Weeks holding at least a fifth of the mass, e.g. "≈ GW7–8". Each label's weeks are weighted by that label's share of
 * cells when the tree position gives it; cells outside the reference are reported separately. An uncalibrated
 * neighbour distribution says so, because it is not a developmental age.
 */
export function gestationLabel(assessment: AssessmentDTO): string {
  const mass = new Map<number, number>();
  const weighted = assessment.gestation.some(g => (assessment.tree_position[g.cell_type] ?? 0) > 0);
  let outside = 0, total = 0;
  for (const g of assessment.gestation) {
    const weight = weighted ? assessment.tree_position[g.cell_type] ?? 0 : 1;
    for (const [week, share] of Object.entries(g.weeks)) { mass.set(Number(week), (mass.get(Number(week)) ?? 0) + share * weight); total += share * weight; }
    outside += (g.outside_reference ?? 0) * weight; total += (g.outside_reference ?? 0) * weight;
  }
  if (!total) return "孕周未估计";
  const weeks = [...mass].filter(([, m]) => m / total >= 0.2).map(([w]) => w).sort((a, b) => a - b);
  const early = outside / total >= 0.2 ? "早于参考" : "";
  const neighbours = assessment.gestation.some(g => g.status === "uncalibrated_neighbor_distribution") ? "近邻参考 " : "";
  if (!weeks.length) return early || "孕周分散";
  const span = weeks.length === 1 ? `GW${weeks[0]}` : `GW${weeks[0]}–${weeks.at(-1)}`;
  return early ? `${neighbours}≈ ${span} · ${early}` : `${neighbours}≈ ${span}`;
}

export function chainValues(assessment: AssessmentDTO): ChainValues {
  const values: ChainValues = [null, null, null, null, null];
  for (const level of assessment.chain) if (level.level >= 0 && level.level < 5) values[level.level] = level.value;
  return values;
}

/** A missing chain level never reads as "fine": without measured levels the note says where cells landed instead. */
function sampleView(assessment: AssessmentDTO, day: number, lead?: string): Sample {
  const chain = chainValues(assessment), weak = weakestLevel(chain), mapping = mappingView(assessment);
  const note = lead ?? (weak !== null ? `${CHAIN_NAMES[weak]}偏低` : mapping.chainMissing ? mappingNote(mapping)
    : chain.some(value => value === null) ? "部分分化链指标未能计算" : "各级未见偏低");
  return { day, position: assessment.tree_position, chain, gestation: gestationLabel(assessment), note, mappedCells: assessment.mapped_cells ?? [], mapping };
}

function weeksSince(date: string, now: Date) {
  return Math.max(0, Math.floor((now.getTime() - new Date(`${date}T00:00:00`).getTime()) / (7 * 864e5)));
}

export const libraryId = (protocolId: string) => `protocol-${protocolId}`;

/**
 * A run is named by its protocol, as in a lab notebook: the version when it is not the first, and the cell line and start date
 * only when the same version was run more than once. The run's own stored name is the last resort.
 */
/** A version shown by its own name when it has one, else as the protocol name with vN from version 2. */
export const versionTitle = (protocolName: string, version: number, label?: string | null) =>
  label?.trim() || (version > 1 ? `${protocolName} v${version}` : protocolName);

export function runTitle(protocolName: string, version: number, run: RunDTO, siblings: RunDTO[], label?: string | null): string {
  const base = versionTitle(protocolName, version, label);
  const same = siblings.filter(other => other.protocol_version_id === run.protocol_version_id);
  if (same.length < 2) return base;
  const parts = [run.cell_line, run.start_date?.slice(5)].filter(Boolean);
  return `${base} · ${parts.length ? parts.join(" · ") : `第 ${same.findIndex(other => other.id === run.id) + 1} 批`}`;
}

export function adaptWorkbench(dto: WorkbenchDTO, now = new Date()): { protocols: Protocol[]; queue: QueueItem[] } {
  // Runs stay bound to the version they started from, so every version is indexed, not only the latest.
  const versions = new Map(dto.protocols.flatMap(p => [...(p.versions ?? []), p.latest].map(v => [v.id, { protocol: p, version: v }] as const)));
  const assessments = new Map(dto.assessments.map(a => [a.id, a]));
  const used = new Set<string>();
  const runs: Protocol[] = dto.runs.flatMap(run => {
    const entry = versions.get(run.protocol_version_id);
    if (!entry) return [];
    used.add(entry.protocol.id);
    const leads = dto.leads.filter(l => l.run_id === run.id && l.status === "open");
    const samples = dto.samples.filter(s => s.run_id === run.id).sort((a, b) => a.day - b.day).flatMap(s => {
      const a = s.assessment_id ? assessments.get(s.assessment_id) : undefined;
      return a && a.status === "done" ? [{ ...sampleView(a, s.day, leads.find(l => l.sample_id === s.id)?.summary), sampleId: s.id, assessmentId: a.id, ...(a.analysis_id ? { analysisId: a.analysis_id } : {}) }] : [];
    });
    const records: SampleRecord[] = dto.samples.filter(s => s.run_id === run.id).sort((a, b) => a.day - b.day).map(s => {
      const a = s.assessment_id ? assessments.get(s.assessment_id) : undefined;
      const request = s.assessment_request ?? (() => { const p = dto.actions.find(x => x.kind === "atlas_assessment" && x.context.sample_id === s.id); return p ? { status: p.status } : null; })();
      const mapping: MappingStatus = a?.status === "done" ? "done" : a?.status === "failed" ? "failed"
        : request && ["pending", "approved", "running"].includes(request.status) ? request.status as MappingStatus
        : a?.status === "running" ? "running" : "none";
      const status: SampleStatus = s.status ?? (!s.material_id ? "collected" : mapping === "done" ? "done" : mapping === "failed" ? "failed"
        : mapping === "none" ? "data_attached" : "mapping");
      // Standard mapping starts on its own once data is attached; the server's status is authoritative then.
      const shown: MappingStatus = status === "mapping" && mapping === "none" ? "running" : mapping;
      const code = s.assessment_availability?.status === "unavailable" ? s.assessment_availability.code : undefined;
      return { id: s.id, revision: s.revision, day: s.day, assay: s.assay, materialId: s.material_id, mapping: shown, status,
        declared: !!s.mapping_input, ...(s.mapping_input ? { declaration: s.mapping_input } : {}), collectedOn: s.collected_on, ...(s.assessment_id ? { assessmentId: s.assessment_id } : {}), ...(code ? { unavailable: availabilityText(code), unavailableCode: code } : {}) };
    });
    const total = entry.version.total_days ?? 0;
    return [{
      id: run.id, name: runTitle(entry.protocol.name, entry.version.version, run, dto.runs, entry.version.label), version: entry.version.version, state: STATE[run.state],
      day: run.state === "ended" ? total : run.day ?? 0, totalDays: total,
      today: run.today.map(t => t.label).join("、") || (run.state === "planned" ? "等待开始" : ""),
      lead: leads[0]?.summary, graftWeeks: run.graft ? weeksSince(run.graft.date, now) : undefined,
      reagents: reagents(entry.version), samples, source: sourceOf(entry.protocol, entry.version), sampleRecords: records,
      stages: stagesOf(entry.version), stageIndex: run.stage_index, operations: entry.version.operations,
      run: { id: run.id, revision: run.revision, name: run.name, cellLine: run.cell_line, startDate: run.start_date, state: run.state,
        graft: run.graft, protocolVersionId: run.protocol_version_id, ...(run.purpose ? { purpose: run.purpose } : {}) },
    }];
  });
  const library: Protocol[] = dto.protocols.filter(p => !used.has(p.id) || p.latest.status === "draft").map(p => ({
    id: libraryId(p.id), name: versionTitle(p.name, p.latest.version, p.latest.label), version: p.latest.version, state: "draft", day: 0, totalDays: p.latest.total_days ?? 0,
    today: p.latest.status === "draft" ? "核对方案" : "记录实验", reagents: reagents(p.latest), samples: [], source: sourceOf(p, p.latest), stages: stagesOf(p.latest), operations: p.latest.operations,
  }));
  const runName = new Map(runs.map(r => [r.id, r.name]));
  const sampleDay = new Map(dto.samples.map(s => [s.id, s.day]));
  const queue: QueueItem[] = dto.actions.filter(a => a.status === "pending").map(a => ({
    id: a.id, title: a.title, tier: a.tier, eta: a.estimate,
    context: [a.context.run_id && runName.get(a.context.run_id), a.context.sample_id && sampleDay.has(a.context.sample_id) && `D${sampleDay.get(a.context.sample_id)}`]
      .filter(Boolean).join(" · "),
  }));
  return { protocols: [...runs, ...library], queue };
}
