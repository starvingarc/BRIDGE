import { useEffect, useRef, useState, type FormEvent } from "react";
import { api } from "../api";
import type { AssessmentAxis, AssessmentMode, AssessmentProposal, JsonValue, Session } from "../types";
import { ArtifactCard } from "./ResultsPane";
import { scientificGap } from "./ScientificInputs";

const modes: Array<AssessmentMode & { label: string }> = [
  { tool_id: "P0-01", mode_id: null, label: "输入与质量检查" },
  { tool_id: "P0-02", mode_id: null, label: "细胞状态" },
  { tool_id: "P0-03", mode_id: "default", label: "目标身份与区域" },
  { tool_id: "P0-04", mode_id: "default", label: "发育阶段" },
  { tool_id: "P0-05", mode_id: "hard_count_accounting", label: "全产品与非目标组成" },
  { tool_id: "P0-06", mode_id: "method_runtime_source_bound", label: "来源绑定的增殖与应激检查" },
  { tool_id: "P0-06", mode_id: "exploratory_process", label: "探索性细胞周期检查" },
  { tool_id: "P0-08", mode_id: "default", label: "证据充分性" },
  { tool_id: "P0-09", mode_id: "case_initial_v2", label: "建立产品证据图" },
  { tool_id: "P0-09", mode_id: "case_append_v2", label: "追加产品证据" },
  { tool_id: "P0-09", mode_id: "case_query", label: "查询产品证据图" },
];
const modeKey = (mode: AssessmentMode) => mode.tool_id + "/" + (mode.mode_id ?? "");
const modeName = (mode: AssessmentMode) => modes.find((item) => modeKey(item) === modeKey(mode))?.label
  ?? modes.find((item) => item.tool_id === mode.tool_id)?.label ?? "已注册的专项检查";
const stateNames: Record<string, string> = {
  available: "已有工具结果", measured: "已测量", missing: "缺少输入或本范围证据", unavailable: "不可用",
  proposed: "待批准", running: "进行中", stopped: "已停止", blocked: "受阻", interrupted: "已中断",
};
const reasons: Record<string, string> = {
  ...scientificGap,
  input_or_resource_change: "事实或资源变化时停止。",
  explicit_stop: "研究者可显式停止。",
  finite_budgets: "达到已批准的有限预算时停止。",
  necessary_fact: "缺少必要实验事实时停止并询问。",
  no_scope_evidence: "本范围尚无这一评估轴的已核验证据。",
  reviewed_family_mapping_unavailable: "缺少适用的已审阅程序分类映射；不按程序名称推断。",
  no_discriminating_check: "当前没有可区分解释的后续检查；这不是整体科学结论。",
  completion_contract_unavailable: "缺少适用于整个问题的完成判定合同；不能宣称评估完成。",
  user_stopped: "已由研究者停止；历史结果与原始授权保留。",
  input_revision_changed: "确认后的事实版本已变化。",
  input_review_required: "事实修改仍待核对和确认。",
  scope_resource_changed: "范围绑定的资源已经变化。",
  no_eligible_check: "当前没有满足前提的检查。",
  result_sharing_disabled: "此部署未允许向模型发送结果摘要；保留本地结果。",
  tool_run_budget_exhausted: "工具运行预算已耗尽，需要新范围。",
  model_turn_budget_exhausted: "模型轮次预算已耗尽，需要新范围。",
  explanation_complete: "本轮解释已结束；不是科学评估完成。",
  necessary_fact_required: "需要研究者提供必要实验事实。",
  canonical_graph_inputs_unchanged: "规范图输入未变化，不重复追加同一批证据。",
  measured_claim_binding_required: "测量与声明的精确绑定尚未补齐。",
  cell_cycle_gene_coverage_insufficient: "细胞周期基因覆盖不足，不能给出该测量。",
  program_gene_coverage_insufficient: "程序基因覆盖不足，不能给出该测量。",
};
function ReasonList({ codes }: { codes: string[] }) {
  return codes.length ? <ul className="assessment-reasons">{codes.map((code) =>
    <li key={code}>{reasons[code] ?? "服务端报告的未解决条件"} <code>{code}</code></li>)}</ul> : null;
}

// This is a lossless presentation table of the bounded server projection, not a calculator.
function FieldTable({ value, label }: { value: JsonValue; label: string }) {
  const rows: Array<[string, JsonValue]> = [];
  function visit(item: JsonValue, path: string) {
    if (Array.isArray(item)) {
      if (!item.length) rows.push([path, []]);
      else item.forEach((child, index) => visit(child, path + "[" + index + "]"));
    } else if (item !== null && typeof item === "object") {
      const entries = Object.entries(item);
      if (!entries.length) rows.push([path, {}]);
      else entries.forEach(([key, child]) => visit(child, path ? path + "." + key : key));
    } else rows.push([path, item]);
  }
  visit(value, "");
  return <div className="table-scroll"><table className="assessment-values" aria-label={label}>
    <thead><tr><th scope="col">字段 / 分母范围</th><th scope="col">服务端原值</th></tr></thead>
    <tbody>{rows.map(([path, item]) => <tr key={path}><th scope="row">{path || "记录"}</th>
      <td>{item === null ? "未提供（null）" : typeof item === "object" ? JSON.stringify(item) : String(item)}</td></tr>)}</tbody>
  </table></div>;
}
function EvidenceLinks({ aliases, onOpen }: { aliases: string[]; onOpen: (alias: string) => void }) {
  return aliases.length ? <p className="assessment-citations">{aliases.map((alias) =>
    <a key={alias} href={"#assessment-evidence-" + alias} onClick={() => onOpen(alias)}>查看来源 {alias}</a>)}</p> : null;
}
function Axis({ axis, onOpen }: { axis: AssessmentAxis; onOpen: (alias: string) => void }) {
  return <section className="assessment-axis" aria-label={axis.title}>
    <h3>{axis.title}</h3><p className="assessment-state">{stateNames[axis.state] ?? axis.state}</p>
    <ReasonList codes={axis.reason_codes} />
    <EvidenceLinks aliases={axis.evidence_aliases} onOpen={onOpen} />
    {Object.keys(axis.summary).length ? <FieldTable value={axis.summary} label={axis.title + "原值与分母"} /> : null}
    {axis.families ? <div className="assessment-families">{axis.families.map((family) =>
      <article key={family.id}><h4>{family.title}</h4><p>{stateNames[family.state] ?? family.state}</p>
        <ReasonList codes={family.reason_codes} />
        <EvidenceLinks aliases={family.evidence_aliases} onOpen={onOpen} />
        {Object.keys(family.summary).length ? <FieldTable value={family.summary} label={family.title + "原值与分母"} /> : null}
      </article>)}</div> : null}
  </section>;
}

export function AssessmentPanel({ session, busy, onSession, onError }: {
  session: Session; busy: boolean; onSession: (session: Session) => void; onError: (error: unknown) => void;
}) {
  const assessment = session.assessment;
  const [showProposal, setShowProposal] = useState(false);
  const [uploadId, setUploadId] = useState(assessment?.upload_id ?? session.uploads[0]?.id ?? "");
  const [question, setQuestion] = useState(assessment?.question ?? "请评估这批细胞的状态、目标与区域身份、发育、组成和增殖应激证据。");
  const [selected, setSelected] = useState(() => modes.slice(1).map(modeKey));
  const [toolLimit, setToolLimit] = useState(12);
  const [modelLimit, setModelLimit] = useState(16);
  const [consent, setConsent] = useState(false);
  const [working, setWorking] = useState(false);
  const [openEvidence, setOpenEvidence] = useState<string | null>(null);
  const [previewId, setPreviewId] = useState<string | null>(null);
  const mounted = useRef(false);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  useEffect(() => { setConsent(false); }, [assessment?.scope_id, assessment?.scope_digest]);
  const disabled = busy || working || session.input_review_required;
  async function perform(operation: () => Promise<Session>) {
    setWorking(true);
    try {
      const next = await operation();
      if (mounted.current) {
        onSession(next);
        if (next.assessment) setShowProposal(false);
      }
    } catch (error) { if (mounted.current) onError(error); }
    finally { if (mounted.current) setWorking(false); }
  }
  function propose(event: FormEvent) {
    event.preventDefault();
    const proposal: AssessmentProposal = { question, upload_id: uploadId,
      allowed_modes: modes.filter((item) => selected.includes(modeKey(item))).map(({tool_id,mode_id}) => ({tool_id,mode_id})),
      max_tool_runs: toolLimit, max_model_turns: modelLimit };
    void perform(() => api.proposeAssessment(session.id, proposal));
  }
  const exhausted = Boolean(assessment && (assessment.tool_runs_used >= assessment.max_tool_runs
    || assessment.model_turns_used >= assessment.max_model_turns));
  const current = assessment?.freshness.state === "current";
  const resumable = Boolean(assessment && ["stopped","blocked","interrupted"].includes(assessment.status) && assessment.scope_authorized);
  const preview = session.artifacts.find((item) => item.id === previewId);
  return <section className="assessment-panel" aria-label="细胞状态与产品评估">
    <header><h2>细胞状态与产品评估</h2>
      <p>按证据轴逐项查看。工具提供数值和分母；解释仍待证据检验。研究性结果不用于临床或产品放行。</p></header>
    {assessment ? <>
      <section className="assessment-scope" aria-label="评估范围">
        <h3>当前问题与执行范围</h3><p>{assessment.question}</p>
        <p className="assessment-state">{stateNames[assessment.status]} · 工具运行：{assessment.tool_runs_used} / {assessment.max_tool_runs}
          {" · "}模型轮次：{assessment.model_turns_used} / {assessment.max_model_turns}</p>
        {assessment.freshness.state === "historical" ? <p className="assessment-warning" role="status">
          历史证据：绑定版本 {assessment.input_revision}，当前事实版本 {assessment.freshness.current_input_revision}。
          选择受影响检查并新建范围；不会自动重算或删除旧结果。</p>
          : assessment.freshness.state === "review_pending" ? <p className="assessment-warning" role="status">
            事实修改尚待确认；当前结果仍绑定版本 {assessment.input_revision}。请使用原事实核对卡确认或放弃修改。</p>
          : <p>当前绑定：事实版本 {assessment.input_revision}。图版本与回执在各证据链中单独显示。</p>}
        {assessment.freshness.reason_code ? <ReasonList codes={[assessment.freshness.reason_code]} /> : null}
        <ul>{assessment.allowed_modes.map((mode) => <li key={modeKey(mode)}>{modeName(mode)}
          <small> {mode.tool_id} / {mode.mode_id ?? "asset"}</small></li>)}</ul>
        <details><summary>绑定资源、数据视图与范围身份</summary>
          <FieldTable value={{scope_id:assessment.scope_id,scope_digest:assessment.scope_digest,input_revision:assessment.input_revision}}
            label="范围身份" />
          <FieldTable value={assessment.data_view} label="绑定数据视图" />
          {assessment.resources.map((resource) => <article key={resource.alias}>
            <p>{resource.schema_ref === null ? "候选原始资源（不是 Schema 对象）" : "已注册对象"} · {resource.alias}</p>
            <FieldTable value={resource} label={resource.alias + "版本与哈希"} />
          </article>)}
          <ReasonList codes={assessment.stop_conditions} />
        </details>
        <p>问题会发送给已配置模型。{assessment.result_summaries_enabled
          ? "此部署允许发送有界聚合结果；原始数据、私有哈希、路径和本地链接不会进入此结果上下文。"
          : "此部署未启用结果摘要分享；结果保留在本地。"}
          范围批准只允许列明检查，不代替来源、产品角色、发育窗口、程序或生物学单位审阅，也不允许公开导出。</p>
        {assessment.status === "proposed" ? <>
          <label className="assessment-consent"><input type="checkbox" checked={consent} disabled={disabled || !current}
            onChange={(event) => setConsent(event.target.checked)} />已核对问题、范围、资源和未解决条件；仅批准上述有限执行</label>
          <button disabled={disabled || !current || !consent || exhausted}
            onClick={() => void perform(() => api.approveAssessment(session.id,assessment.scope_id,assessment.scope_digest))}>批准本范围</button>
        </> : null}
        {["running","proposed"].includes(assessment.status) ? <button
          disabled={working || session.status === "stopping"}
          onClick={() => void perform(() => api.stopSession(session.id))}>停止本范围</button> : null}
        {resumable ? <button disabled={disabled || !current || exhausted}
          onClick={() => void perform(() => api.resumeAssessment(session.id,assessment.scope_id,assessment.scope_digest))}>继续本范围</button> : null}
        {exhausted ? <p>预算已耗尽；保留原计数，需要新范围。</p> : null}
      </section>
      <section aria-label="停止与继续"><h3>停止与继续</h3>
        {assessment.stop_reason ? <ReasonList codes={[assessment.stop_reason]} /> : <p>尚无停止原因。</p>}
        <p>停止、解释结束或没有可用检查不代表整个科学问题已解决。</p>
      </section>
      <section aria-label="前提条件"><h3>前提条件</h3>
        {assessment.candidates.map((candidate) => <article key={modeKey(candidate)}>
          <h4>{modeName(candidate)} · {candidate.already_admitted ? "同一请求已执行，不重复选择" : candidate.runnable ? "前提满足，可在范围内选择" : "前提未满足"}</h4>
          <small>{candidate.tool_id} / {candidate.mode_id ?? "asset"}</small>
          {candidate.blockers.length ? <><p>阻塞前提</p><ReasonList codes={candidate.blockers} /></> : null}
          {candidate.gaps.length ? <><p>解释缺口（不阻止本项检查）</p><ReasonList codes={candidate.gaps} /></> : null}
        </article>)}
        {!assessment.candidates.length ? <p>尚未提供候选检查状态。</p> : null}
      </section>
      <section aria-label="下一步"><h3>下一步</h3>
        {assessment.candidates.some((candidate)=>candidate.runnable) ? <>
          <p>以下是当前范围内尚未执行的候选检查；停止后需要显式继续，不会自动运行。</p>
          <ul>{assessment.candidates.filter((candidate)=>candidate.runnable).map((candidate)=>
            <li key={modeKey(candidate)}>{modeName(candidate)}</li>)}</ul>
        </> : <p>当前没有新的可运行候选。保留结果并补齐前提，或结束本范围。</p>}
        <p>需补充事实时使用原事实核对卡；需补充科学资源时使用科学输入面板。更改后重新选择受影响检查并批准新范围。</p>
      </section>
      <section aria-label="工具发现"><h3>工具发现</h3><p>下表原样保留已核验的有界投影；未提供不等于零。完整表格和图在证据链中查看。</p>
        {assessment.portrait.map((axis) => <Axis key={axis.id} axis={axis} onOpen={setOpenEvidence} />)}
      </section>
      <section aria-label="冲突与待检验解释"><h3>冲突与待检验解释</h3>
        <p>图中的冲突、开放要求和来源关系保留在版本化证据链中。没有列出假设不等于没有冲突。</p>
        {assessment.hypotheses.map((item,index) => <article key={index}>
          <h4>待检验解释</h4><p>{item.statement}</p><h5>竞争解释</h5><p>{item.competing_explanation}</p>
          <p>区分性检查：{modeName({tool_id:item.discriminating_check,mode_id:null})} <code>{item.discriminating_check}</code></p>
          <EvidenceLinks aliases={item.evidence_aliases} onOpen={setOpenEvidence} />
        </article>)}
      </section>
      <section aria-label="本地证据链"><h3>本地证据链</h3>
        <p>以下回执、身份和下载仅供已认证的本地研究核对；显示副本不是公开安全导出。</p>
        {assessment.evidence.map((evidence) => <details key={evidence.alias} id={"assessment-evidence-"+evidence.alias}
          open={openEvidence===evidence.alias}>
          <summary onClick={(event) => {event.preventDefault();setOpenEvidence(openEvidence===evidence.alias?null:evidence.alias);}}>
            证据链 {evidence.alias}</summary>
          <p>{evidence.tool_id} · {evidence.tool_version} · {stateNames[evidence.state]} · {evidence.execution_state}</p>
          {evidence.interpretation_scope ? <p>解释范围：{evidence.interpretation_scope}</p> : null}
          {evidence.reason_code ? <ReasonList codes={[evidence.reason_code]} /> : null}
          {evidence.provenance ? <FieldTable value={evidence.provenance} label={evidence.alias+"来源"} /> : null}
          {evidence.dependencies?.length ? <><h4>来源依赖与原始版本</h4>
            <FieldTable value={evidence.dependencies} label={evidence.alias+"来源依赖"} />
            {evidence.dependencies.flatMap((dependency)=>dependency.artifact_ids).filter((id,index,ids)=>ids.indexOf(id)===index).map((id)=>{
              const artifact=session.artifacts.find((item)=>item.id===id);
              return artifact ? <button key={id} onClick={()=>setPreviewId(id)}>预览来源 {artifact.name}</button> : null;
            })}</> : null}
          {evidence.summary ? <FieldTable value={evidence.summary} label={evidence.alias+"完整投影"} /> : null}
          {evidence.measurements?.length ? <FieldTable value={evidence.measurements} label={evidence.alias+"测量原值与分母"} /> : null}
          {evidence.artifact_ids?.length ? evidence.artifact_ids.map((id) => {
            const artifact=session.artifacts.find((item)=>item.id===id);
            return artifact ? <button key={id} onClick={()=>setPreviewId(id)}>预览 {artifact.name}</button> : null;
          }) : <p>此回执没有可展开的已注册显示产物；保留上方原值和原因。</p>}
        </details>)}
        {preview ? <div className="assessment-preview"><button onClick={()=>setPreviewId(null)}>关闭产物预览</button>
          <ArtifactCard key={session.id+preview.id} sessionId={session.id} artifact={preview} /></div> : null}
      </section>
      {assessment.history.length ? <details><summary>先前范围与原始停止原因</summary>
        {assessment.history.map((item)=><article key={item.scope_id}><p>{item.question} · 事实版本 {item.input_revision}</p>
          <p>{stateNames[item.status] ?? item.status}</p>{item.stop_reason ? <ReasonList codes={[item.stop_reason]} /> : null}</article>)}
      </details> : null}
    </> : <p>完成上传、事实确认与适用的质量检查后，先准备有限评估范围。准备范围不会运行工具或模型。</p>}
    <button disabled={disabled} onClick={()=>setShowProposal(!showProposal)}>
      {showProposal ? "收起新范围" : "新建评估范围"}</button>
    {showProposal ? <form className="assessment-proposal" onSubmit={propose}>
      <h3>准备有限评估范围</h3>
      <fieldset disabled={disabled}><legend>问题、样本与允许检查</legend>
        <label>研究问题<textarea required maxLength={2000} value={question} onChange={(event)=>setQuestion(event.target.value)} /></label>
        <label>已上传样本<select required value={uploadId} onChange={(event)=>setUploadId(event.target.value)}>
          <option value="">选择样本</option>{session.uploads.filter((item)=>item.kind==="h5ad").map((item)=>
            <option key={item.id} value={item.id}>{item.name} · {item.id.slice(0,8)}</option>)}</select></label>
        {modes.map((mode)=><label className="assessment-mode" key={modeKey(mode)}>
          <input type="checkbox" checked={selected.includes(modeKey(mode))}
            onChange={(event)=>setSelected((items)=>event.target.checked?[...items,modeKey(mode)]:items.filter((key)=>key!==modeKey(mode)))} />
          {mode.label}</label>)}
        <label>最多工具运行次数<input type="number" required min={1} max={32} value={toolLimit}
          onChange={(event)=>setToolLimit(Number(event.target.value))} /></label>
        <label>最多模型轮次<input type="number" required min={1} max={64} value={modelLimit}
          onChange={(event)=>setModelLimit(Number(event.target.value))} /></label>
        <p>服务端将列出每项检查的实际阻塞与解释缺口。准备不是批准，也不会更改确认事实。</p>
        <button type="submit" disabled={!uploadId || !question.trim() || !selected.length}>准备范围供核对</button>
      </fieldset>
    </form> : null}
  </section>;
}
