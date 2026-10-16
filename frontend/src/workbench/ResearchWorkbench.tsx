import { useCallback, useEffect, useMemo, useState } from "react";
import { api, ApiError, type Principal } from "../api";
import type { Research } from "../types";
import { adaptWorkbench, libraryId, reagentsToDTO, availabilityText, sourceView } from "./adapt";
import { demoProtocols, demoQueue, syntheticTree } from "./demo";
import { mappingInputDTO, markerPanel } from "./mapping";
import type { ProtocolDTO, SampleDTO } from "./objects";
import { isLow } from "./stages";
import type { DevTree, DraftPatch, MappingInput, MaterialOption, Protocol, ProtocolOps, QueueItem, RunOps } from "./types";
import { BoundConversation } from "./BoundConversation";
import { SettingsDialog } from "../components/SettingsDialog";
import { WorkbenchApp } from "./WorkbenchApp";
import type { WorkbenchLocation } from "../routes";

type Props = {
  principal: Principal; research: Research; onSessions: (sessionId?: string) => void; onHome: () => void;
  /** Sign-out from the settings dialog; absent in previews, where the rail shows only the name. */
  onLogout?: () => void; onSignedOut?: () => void;
  /** Where to open and how to report moves, so the address can follow the workbench. */
  location?: WorkbenchLocation; onLocate?: (at: WorkbenchLocation) => void;
  onReports?: () => void;
};
type Content = { mode: "live" | "example"; protocols: Protocol[]; queue: QueueItem[] };

/** Example answers for the example protocols only; free-text questions go to a real research session. */
function exampleAnswer(question: string, { protocol, sample }: { protocol: Protocol | null; sample: number | null }) {
  const point = protocol && sample !== null ? protocol.samples[sample] : protocol?.samples.at(-1);
  const low = isLow(point?.chain[3]);
  if (question.startsWith("为什么")) return low
    ? { text: "示例：SHH 下游信号偏弱，腹侧化不够。", tags: ["NKX6-1 ↓", "FOXA2 ↓", "GLI1 ↓"] }
    : { text: "示例：底板标记与 GW8 底板接近。", tags: ["FOXA2", "LMX1A"] };
  return low ? { text: "示例：先核查 SHH 通路处理的强度和撤除时间，可在方案图中生成下一版草案。" }
    : { text: "示例：可以在最后一个时间点之后再补一次取样。" };
}

/** The workbench route is optional until the backend ships; only the framework's missing-route answer means "not available". */
const routeMissing = (failure: unknown) =>
  failure instanceof ApiError && (failure.status === 405 || (failure.status === 404 && failure.message === "Not Found"));

const MESSAGES: Record<string, string> = {
  object_version_conflict: "方案刚被更新过，已刷新，请再试一次。",
  protocol_incomplete: "先填写总天数和每个试剂的剂量。",
  protocol_unconfirmed_fields: "还有未核对的项目。",
  protocol_version_immutable: "这个版本已确认，不能再修改。",
  protocol_version_not_confirmed: "方案确认后才能记录实验。",
  material_not_found: "找不到这份数据，可能已被删除。",
  sample_material_requires_h5ad: "样本数据需要是 H5AD 文件。",
  assessment_request_active: "这个样本已经提交过映射。",
  protocol_import_not_implemented: "文档识别即将接入。",
  protocol_material_required: "请上传方案文档。",
  protocol_source_invalid: "这份文档读不出文字，请换成 PDF、Word 或纯文本。",
  protocol_import_invalid: "没能从文档整理出方案，请检查文档，或手动录入。",
  protocol_provider_unavailable: "模型服务暂时不可用，请稍后再试。",
  protocol_compiler_unavailable: "方案转换服务暂时不可用，请稍后再试。",
  protocol_formalization_not_found: "这一版没有原文记录。",
  protocol_formalization_unavailable: "原文记录暂时读不出来，原文件可能已改变。",
  protocol_formalization_limit: "文档太长，超出一次能读取的范围，请拆分后上传。",
  sample_has_material: "这个样本已经关联了数据。",
  research_material_unavailable: "这份数据已损坏或丢失，请重新上传。",
  mapping_already_started: "这个样本已经在映射，或已经有结果。",
  mapping_result_unavailable: "映射结果读不出来，可能已损坏。",
  marker_expression_unavailable: "这次映射没有保存表达数据；较早的结果不会重新计算。",
  analysis_source_unavailable: "这次分析的来源文件已改变或丢失，只保留登记信息。",
  sample_not_found: "找不到这个样本，可能已被删除。",
};

/** What happened to mapping after a sample write: started, or the reason it could not start yet. */
function mappingOutcome(sample: SampleDTO, day: number, prefix: string): string {
  if (sample.status === "mapping") return `${prefix}图谱映射已开始。`;
  const availability = sample.assessment_availability;
  if (availability?.status !== "unavailable") return prefix;
  if (availability.code === "mapping_input_required") return `${prefix}补充数据说明后开始映射。`;
  if (availability.code === "mapping_worker_busy") return `${prefix}映射任务已满，请稍后在 D${day} 旁点重试。`;
  return `${prefix}${availabilityText(availability.code)}，暂时不能映射。`;
}
const readable = (failure: unknown) =>
  failure instanceof ApiError ? MESSAGES[failure.message] ?? failure.message : "没有完成，请重试。";

const draftBody = (patch: DraftPatch) => ({
  ...(patch.reagents ? { reagents: reagentsToDTO(patch.reagents) } : {}),
  ...(patch.totalDays !== undefined ? { total_days: patch.totalDays } : {}),
  ...(patch.changeNote !== undefined ? { change_note: patch.changeNote } : {}),
  ...(patch.review !== undefined ? { unconfirmed: patch.review } : {}),
});

export function ResearchWorkbench({ principal, research, onSessions, onHome, onLogout, onSignedOut, location, onLocate, onReports }: Props) {
  const [tree, setTree] = useState<DevTree | null>(null);
  const [content, setContent] = useState<Content | null>(null);
  const [error, setError] = useState("");
  const [materials, setMaterials] = useState<MaterialOption[]>(() =>
    research.materials.filter(m => m.kind === "h5ad").map(m => ({ id: m.id, name: m.name, ...(m.locations ? { locations: m.locations } : {}) })));
  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      const dto = await api.workbench(research.id, signal);
      setContent({ mode: "live", ...adaptWorkbench(dto) }); setError("");
      return dto;
    } catch (failure) {
      if (signal?.aborted) return null;
      if (routeMissing(failure)) setContent({ mode: "example", protocols: demoProtocols, queue: demoQueue });
      else setError(failure instanceof Error ? failure.message : "工作台暂时无法打开，请重试。");
      return null;
    }
  }, [research.id]);
  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    fetch("/api/workbench/devtree", { cache: "no-store", credentials: "same-origin", signal: controller.signal })
      .then(r => (r.ok ? r.json() as Promise<DevTree> : null)).catch(() => null)
      .then(value => { if (!controller.signal.aborted) setTree(value ?? syntheticTree()); });
    return () => controller.abort();
  }, [load]);

  // Mapping runs on the server after data is attached; while any sample is mapping, refresh every few seconds.
  const mapping = content?.mode === "live" && content.protocols.some(p => p.sampleRecords?.some(s => s.status === "mapping"));
  useEffect(() => {
    if (!mapping) return;
    const timer = window.setInterval(() => { if (!document.hidden) void load(); }, 4000);
    return () => window.clearInterval(timer);
  }, [mapping, load]);

  /** Runs a server write and reloads; `unsupported` explains a route this server does not have yet. Conflicts refresh before failing. */
  const write = useCallback(async <T,>(work: () => Promise<T>, unsupported?: string): Promise<T> => {
    try { const result = await work(); await load(); return result; }
    catch (failure) {
      if (unsupported && routeMissing(failure)) throw new Error(unsupported);
      if (failure instanceof ApiError && failure.message === "object_version_conflict") await load();
      throw new Error(readable(failure));
    }
  }, [load]);

  const ops = useMemo<ProtocolOps>(() => {
    const created = async (protocol: ProtocolDTO) => libraryId(protocol.id);
    const latestDraftOf = (protocolId: string) => libraryId(protocolId);
    return {
      createManual: name => write(async () => created(await api.createProtocol(research.id, { name, origin: "lab", expected_version: 0 }))),
      importDocument: async file => {
        const material = await write(() => api.uploadResearchMaterial(research.id, file));
        try {
          return { viewId: await write(async () => created(await api.createProtocol(research.id, { material_id: material.id, expected_version: 0 }))) };
        } catch (failure) {
          if (!(failure instanceof Error) || failure.message !== MESSAGES.protocol_import_not_implemented) throw failure;
          const name = file.name.replace(/\.[^.]+$/, "") || "新的方案";
          const viewId = await write(async () => created(await api.createProtocol(research.id, { name, origin: "lab", expected_version: 0 })));
          return { viewId, notice: `文档识别即将接入。已保存「${file.name}」，并按文件名新建了空白方案，请先手动录入。` };
        }
      },
      formalization: async protocol => {
        const s = protocol.source!;
        try { return sourceView(await api.protocolFormalization(research.id, s.protocolId, s.versionId)); }
        catch (failure) {
          if (failure instanceof ApiError && failure.status === 404) return null;
          throw new Error(readable(failure));
        }
      },
      saveDraft: async (protocol, patch) => {
        const s = protocol.source!;
        await write(() => api.updateProtocolVersion(research.id, s.protocolId, s.versionId, { ...draftBody(patch), expected_version: s.versionRevision }));
      },
      confirm: async protocol => {
        const s = protocol.source!;
        await write(() => api.confirmProtocolVersion(research.id, s.protocolId, s.versionId, s.versionRevision));
      },
      newVersion: async (protocol, patch = {}) => {
        const s = protocol.source!;
        await write(() => api.createProtocolVersion(research.id, s.protocolId, {
          based_on_version_id: s.versionId, changes: draftBody(patch), expected_version: s.protocolRevision,
        }));
        return latestDraftOf(s.protocolId);
      },
    };
  }, [research.id, write]);

  const runOps = useMemo<RunOps>(() => ({
    materials,
    uploadMaterial: async file => {
      const material = await write(() => api.uploadResearchMaterial(research.id, file));
      if (material.kind !== "h5ad") throw new Error("这不是 H5AD 文件，已存入研究资料。");
      const option = { id: material.id, name: material.name, ...(material.locations ? { locations: material.locations } : {}) };
      setMaterials(list => [...list.filter(m => m.id !== option.id), option]);
      return option;
    },
    start: async (protocol, input) => {
      const run = await write(() => api.createRun(research.id, {
        protocol_version_id: protocol.source!.versionId, name: input.name, cell_line: input.cellLine || null,
        start_date: input.startDate || null, state: input.state, expected_version: 0,
      }));
      return run.id;
    },
    update: async (run, patch) => {
      await write(() => api.updateRun(research.id, run.id, {
        ...(patch.state ? { state: patch.state } : {}), ...(patch.startDate ? { start_date: patch.startDate } : {}),
        ...(patch.graft ? { graft: patch.graft } : {}), expected_version: run.revision,
      }));
    },
    addSample: async (run, input) => write(async () => {
      const sample = await api.createSample(research.id, run.id, {
        day: input.day, assay: input.assay, collected_on: input.collectedOn || null, material_id: input.materialId, expected_version: run.revision,
        ...(input.materialId && input.mappingInput ? { mapping_input: mappingInputDTO(input.mappingInput) } : {}),
      });
      if (!input.materialId) return { notice: `已登记 D${sample.day}，测序数据回来后在这里关联。` };
      return { notice: mappingOutcome(sample, sample.day, `已登记 D${sample.day}。`) };
    }),
    requestMapping: async (sample, input?: MappingInput) => {
      const updated = await write(() => api.startSampleMapping(research.id, sample.id, {
        expected_version: sample.revision, ...(input ? { mapping_input: mappingInputDTO(input) } : {}),
      }), "服务器还不支持从这里开始映射，后端更新后即可使用。");
      return { notice: mappingOutcome(updated, sample.day, `D${sample.day}：`) };
    },
    attachData: async (sample, materialId, input) => {
      const updated = await write(() => api.updateSample(research.id, sample.id, {
        material_id: materialId, expected_version: sample.revision, ...(input ? { mapping_input: mappingInputDTO(input) } : {}),
      }), "服务器还不支持之后关联数据，后端更新后即可使用。");
      return { notice: mappingOutcome(updated, sample.day, `D${sample.day} 已关联数据。`) };
    },
    addCapture: async (sample, capture) => {
      if (!sample.declaration) throw new Error("这个样本还没有数据说明。");
      const { capture_id: _id, capture_id_column: _column, ...rest } = sample.declaration;
      await write(() => api.continueSampleWorkflow(research.id, sample.id, { expected_version: sample.revision,
        mapping_input: { ...rest, ...("id" in capture ? { capture_id: capture.id } : { capture_id_column: capture.column }) } }),
        "服务器还不支持补充捕获批次，后端更新后即可使用。");
      return { notice: `D${sample.day} 已开始重新分析，几分钟后可以看到双细胞结果。` };
    },
  }), [materials, research.id, write]);

  const loadMarkers = useCallback(async (assessmentId: string, signal: AbortSignal) => {
    try { return markerPanel(await api.markerExpression(research.id, assessmentId, signal)); }
    catch (failure) { throw new Error(readable(failure)); }
  }, [research.id]);

  const loadAnalyses = useCallback(async (sampleId: string, signal: AbortSignal) => {
    try { return (await api.sampleAnalyses(research.id, sampleId, signal)).analyses; }
    catch (failure) { throw new Error(routeMissing(failure) ? "服务器还不支持样本分析记录，后端更新后即可查看。" : readable(failure)); }
  }, [research.id]);

  if (error) return <main className="loading-screen" role="alert"><div className="brand">BRIDGE</div><p>{error}</p>
    <button onClick={() => { setError(""); void load(); }}>重试</button></main>;
  if (!tree || !content) return <main className="loading-screen" aria-live="polite"><div className="brand">BRIDGE</div><p>正在打开工作台…</p></main>;
  const live = content.mode === "live";
  return <WorkbenchApp userName={principal.username} researchName={research.name} protocols={content.protocols} queue={content.queue} tree={tree}
    respond={exampleAnswer} location={location} onLocate={onLocate} onReports={onReports}
    previewLabel={live ? (tree.synthetic ? "发育树为合成示意" : undefined) : `方案与样本尚未接入，以下为示例${tree.synthetic ? " · 合成发育树" : ""}`}
    railExtras={[{ id: "sessions", label: "会话", onClick: () => onSessions() }, { id: "home", label: "所有研究", onClick: onHome }]}
    account={onLogout ? <SettingsDialog principal={principal} disabled={false} onLogout={onLogout} onSignedOut={onSignedOut} triggerClassName="wb-me"
      trigger={<><span className="wb-avatar">{principal.username.slice(0, 2).toUpperCase()}</span><span>{principal.username}</span></>} /> : undefined}
    onDecide={live ? async (id, decision) => { await write(() => api.decideAction(research.id, id, decision)); } : undefined}
    protocolOps={live ? ops : undefined}
    runOps={live ? runOps : undefined}
    loadMarkers={live ? loadMarkers : undefined}
    loadAnalyses={live ? loadAnalyses : undefined}
    renderConversation={(protocol, question) => <BoundConversation
      key={`${principal.id}:${research.id}:${protocol?.run?.id ?? "research"}`}
      researchId={research.id} runId={protocol?.run?.id ?? null}
      label={protocol?.run ? `${protocol.run.name} · 对话` : "研究总对话"}
      question={question} onOpenSession={id => onSessions(id)} />} />;
}
