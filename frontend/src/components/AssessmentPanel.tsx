import { PresentationIssue } from "./PresentationIssue";
import { lazy, Suspense, useEffect, useRef, useState, type FormEvent } from "react";
import { Activity, ChartPie, ChevronDown, FileText, GitBranch, MapPin, Microscope, Network } from "lucide-react";
import { api } from "../api";
import type { AssessmentAxis, AssessmentProposal, JsonValue, Session } from "../types";
import { ResearchValue } from "./ResearchValue";
import { ArtifactCard } from "./ResultsPane";
import { object } from "./graphData";
import { assessmentModes as modes, modeKey, modeName, toolName, stateName, reasonText, researcherText, fieldLabel, programSourceNames, publicLiteratureConcepts } from "../researcherLabels";

const ResearchFigures = lazy(() => import("./ResearchFigures"));

function ReasonList({ codes }: { codes: string[] }) {
  return codes.length ? <ul className="assessment-reasons">{codes.map((code) =>
    <li key={code}>{reasonText(code)}</li>)}</ul> : null;
}

// Only research-facing values enter this table; audit prose stays in source artifacts.
const researchFields = new Set(['metric_id','metric_name','program_id','gene_id','label','source_label',
  'value','raw_value','numerator','denominator','unit','score_unit','lower','upper','mean','median','p10','p90',
  'fraction','count','n_observations','n_genes','n_cells','input_revision','graph_version','evidence_version',
  'state','status','assessment_state','assignment_state','evidence_state','scientific_status','relation',
  'reason_code','reason_codes','role','score_state','domain_score','missingness',
  'state_review_status','development_gate_state','development_reason_codes']);
function FieldTable({ value, label }: { value: JsonValue; label: string }) {
  const rows: Array<[string, JsonValue]> = [];
  function visit(item: JsonValue, path: string) {
    if (Array.isArray(item)) {
      if (item.length) item.forEach((child, index) => visit(child, path + "[" + index + "]"));
    } else if (item !== null && typeof item === "object") {
      Object.entries(item).filter(([key]) => !/basis|review_notes|reviewer|provenance|receipt|sha256|hash|digest|schema|path/.test(key))
        .forEach(([key, child]) => visit(child, path ? path + "." + key : key));
    } else {
      const key = path.replace(/\[\d+\]/g, "").split(".").pop() ?? "";
      if (researchFields.has(key) || /_(fraction|count|mean|median|score)$/.test(key) && (item===null || typeof item==='number')) rows.push([path, item]);
    }
  }
  visit(value, "");
  if (!rows.length) return <p>详细数值见图表与下载。</p>;
  return <><div className="table-scroll"><table className="assessment-values" aria-label={label}>
    <thead><tr><th scope="col">字段 / 分母范围</th><th scope="col">数值 / 状态说明</th></tr></thead>
    <tbody>{rows.map(([path, item]) => <tr key={path}><th scope="row">{fieldLabel(path) || "记录"}</th>
      <td>{typeof item === "string" && /(^|\.)(?:development_)?reason_codes?(\[|$)/.test(path)
        ? <ReasonList codes={[item]} />
        : <ResearchValue value={item} field={path} empty="未提供" />}</td></tr>)}</tbody>
  </table></div></>;
}
function EvidenceLinks({ aliases, onOpen, onOpenGraph }: { aliases: string[]; onOpen: (alias: string) => void; onOpenGraph?: (citation: string) => void }) {
  return aliases.length ? <p className="assessment-citations">{aliases.map((alias, index) =>
    <span key={alias}><a href={"#assessment-evidence-" + alias.split("#")[0]} onClick={() => onOpen(alias.split("#")[0])}>来源 {index + 1}</a>
      {onOpenGraph && <button type="button" aria-label={"查看关联依据 " + (index + 1)} onClick={() => onOpenGraph(alias)}>查看关联依据</button>}</span>)}</p> : null;
}
function Axis({ axis, onOpen, onOpenGraph }: { axis: AssessmentAxis; onOpen: (alias: string) => void; onOpenGraph?: (citation: string) => void }) {
  return <section className="assessment-axis" aria-label={axis.title}>
    <h3>{axis.title}</h3>{axis.state !== "available" && <p className="assessment-state">{stateName(axis.state)}</p>}
    <AxisObservation axis={axis} />
    <ReasonList codes={axis.reason_codes} />
    <EvidenceLinks aliases={axis.evidence_aliases} onOpen={onOpen} onOpenGraph={onOpenGraph} />
    {axis.context_evidence_aliases?.length ? <><p>参考对应观察</p>
      <EvidenceLinks aliases={axis.context_evidence_aliases} onOpen={onOpen} onOpenGraph={onOpenGraph} /></> : null}
    {Object.keys(axis.summary).length ? <details><summary>{axis.title}原值与分母</summary>
      <FieldTable value={axis.summary} label={axis.title + "原值与分母"} /></details> : null}
    {axis.families ? <div className="assessment-families">{axis.families.map((family) =>
      <article key={family.id}><h4>{researcherText(family.title)}</h4><p>{stateName(family.state)}</p>
        <ReasonList codes={family.reason_codes} />
        <EvidenceLinks aliases={family.evidence_aliases} onOpen={onOpen} onOpenGraph={onOpenGraph} />
        {Object.keys(family.summary).length ? <details><summary>{researcherText(family.title)}原值与分母</summary>
          <FieldTable value={family.summary} label={family.title + "原值与分母"} /></details> : null}
      </article>)}</div> : null}
  </section>;
}

const domains = [
  {id: "cell_state", title: "细胞状态", icon: Microscope, axes: ["cell_state"]},
  {id: "identity", title: "目标与区域", icon: MapPin, axes: ["target_identity", "regional_identity"]},
  {id: "development", title: "发育阶段", icon: GitBranch, axes: ["development"]},
  {id: "composition", title: "整体组成", icon: ChartPie, axes: ["composition"]},
  {id: "process", title: "增殖与应激", icon: Activity, axes: ["process"]},
];
function AxisObservation({axis}: {axis: AssessmentAxis}) {
  const s = axis.summary;
  const channels = Array.isArray(s.channels) ? (s.channels as unknown[]).filter(object) : [];
  return <>
    {typeof s.n_observations === "number" && <p>观察范围：{s.n_observations} 个观测。</p>}
    {typeof s.assessment_state === "string" && <p>评估状态：{stateName(s.assessment_state)}。</p>}
    {channels.map((channel, index) => <p key={index}>分项 {index + 1}{typeof channel.label_level === "string" ? ` · ${channel.label_level}` : ""}：
      {typeof channel.assessment_state === "string" ? stateName(channel.assessment_state) : "尚未提供评估状态"}。
      {Array.isArray(channel.reason_codes) && channel.reason_codes.filter((code): code is string => typeof code === "string").map(reasonText).join(" ")}</p>)}
    {axis.id === "cell_state" && s.analysis_scope === "candidate_method_observation" && <p>候选细胞组成</p>}
    {axis.id === "development" && s.expected_window_match === null && <p>已有发育相关描述；预期发育窗口匹配尚未评估。</p>}
    {axis.id === "development" && object(s.whole_product_profile) && typeof s.whole_product_profile.denominator === "number" &&
      <p>整体观察分母：{s.whole_product_profile.denominator}；目标相关观察分母：
        {object(s.target_related_profile) && typeof s.target_related_profile.denominator === "number" ? s.target_related_profile.denominator : "未提供"}。数值按各自分母查看。</p>}
    {axis.id === "composition" && (s.target_fraction === null || s.non_target_fraction === null) && <p>
      {s.target_fraction === null ? "目标比例尚未判定。" : ""}{s.non_target_fraction === null ? "非目标比例尚未判定。" : ""}候选组成不等于目标纯度。</p>}
    {axis.id === "process" && object(s.cell_cycle) && typeof s.cell_cycle.assessment_state === "string" && <p>细胞周期评估：{stateName(s.cell_cycle.assessment_state)}。</p>}
    {axis.state === "available" && !Object.keys(s).length && <p>回执可读取，尚未提供观测摘要；请展开核对来源。</p>}
  </>;
}
function DomainSummary({session, onOpen, onOpenGraph}: {session: Session; onOpen: (alias: string) => void; onOpenGraph?: (citation: string) => void}) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const detail = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!expanded) return;
    detail.current?.scrollIntoView?.({block: "start"});
    detail.current?.focus({preventScroll: true});
  }, [expanded]);
  const portrait = session.assessment!.portrait;
  const selected = domains.find(domain => domain.id === expanded);
  const axesFor = (ids: string[]) => ids.flatMap(id => portrait.filter(axis => axis.id === id));
  return <section aria-label="工具发现" id="assessment-findings" tabIndex={-1}>
    <div className="assessment-domain-grid">
      {domains.map((domain) => {
        const axes = axesFor(domain.axes);
        return <article key={domain.id} className="assessment-domain-card" data-expanded={expanded === domain.id}>
          <span className="assessment-domain-icon" aria-hidden="true"><domain.icon /></span>
          <h4><button type="button" aria-expanded={expanded === domain.id}
            aria-controls={"domain-detail-" + domain.id}
            onClick={() => setExpanded(expanded === domain.id ? null : domain.id)}>{domain.title}<ChevronDown className="assessment-domain-chevron" aria-hidden="true" /></button></h4>
          {axes.map(axis => <div className="assessment-domain-status" key={axis.id}>
            {domain.axes.length > 1 && <strong>{axis.title}</strong>}
            {axis.state !== "available" && <span data-state={axis.state}>{stateName(axis.state)}</span>}
            {axis.context_evidence_aliases?.length ? <span className="assessment-context-indicator" title="有补充参考观察，判断状态不变"><Network aria-hidden="true" /><span className="sr-only">有补充参考观察</span></span> : null}
            {axis.families && <><ul className="assessment-family-summary">{axis.families.map(family =>
              <li key={family.id} title={researcherText(family.title) + " · " + stateName(family.state)}>
                <span className="program-state-mark" data-state={family.state} aria-hidden="true" />
                <span>{researcherText(family.title)}</span><span className="sr-only">{stateName(family.state)}</span></li>)}</ul>
              <p className="program-state-legend" aria-label="各项状态图例"><span><i data-state="measured" />有测量</span><span><i data-state="unavailable" />不可用</span><span><i data-state="missing" />缺少证据</span></p></>}
          </div>)}
          {axes.length < domain.axes.length && <p>尚未提供{domain.axes.length > 1 ? "完整的两项" : "本项"}状态，请核对来源。</p>}
        </article>;
      })}
    </div>
    {domains.map(domain => <div id={"domain-detail-" + domain.id} key={domain.id} hidden={expanded !== domain.id}>
      {selected?.id === domain.id && <div ref={detail} tabIndex={-1} className="assessment-domain-detail" role="region" aria-label={domain.title + "详情"}>
        <div className="assessment-domain-detail-heading"><h4>{domain.title} · 结果</h4>
          <button type="button" onClick={() => {setExpanded(null); document.querySelector<HTMLButtonElement>(`[aria-controls="domain-detail-${domain.id}"]`)?.focus();}}>收起详情</button></div>
        <Suspense fallback={<p role="status">正在加载结果…</p>}>
          <ResearchFigures session={session} axes={axesFor(domain.axes)} /></Suspense>
        <details className="assessment-measurement-details"><summary>方法、数值与限制</summary>
          {axesFor(domain.axes).map(axis => <Axis key={axis.id} axis={axis} onOpen={onOpen} onOpenGraph={onOpenGraph} />)}
        </details>
      </div>}
    </div>)}
  </section>;
}

export function AssessmentPanel({ session, busy, onSession, onError, onOpenGraph, onOpenReports }: {
  session: Session; busy: boolean; onSession: (session: Session) => void; onError: (error: unknown) => void;
  onOpenGraph?: (citation: string) => void; onOpenReports?: () => void;
}) {
  const assessment = session.assessment;
  const sources = useRef<HTMLDetailsElement>(null);
  const [showProposal, setShowProposal] = useState(false);
  const [uploadId, setUploadId] = useState(assessment?.upload_id ?? session.uploads[0]?.id ?? "");
  const [question, setQuestion] = useState(assessment?.question ?? "请评估这批细胞的状态、目标与区域身份、发育、组成和增殖应激证据。");
  const [selected, setSelected] = useState(() => modes.slice(1).filter(mode => mode.defaultSelected !== false).map(modeKey));
  const [toolLimit, setToolLimit] = useState(12);
  const [modelLimit, setModelLimit] = useState(16);
  const [reportAfterExplanation, setReportAfterExplanation] = useState(false);
  const [literatureEnabled, setLiteratureEnabled] = useState(false);
  const [literatureConcepts, setLiteratureConcepts] = useState<string[]>([]);
  const [consent, setConsent] = useState(false);
  const [working, setWorking] = useState(false);
  const [openEvidence, setOpenEvidence] = useState<string | null>(null);
  // Citation navigation reveals the source before the browser follows its exact anchor.
  const openSource = (alias: string) => {
    if (sources.current) sources.current.open = true;
    setOpenEvidence(alias);
  };
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
      report_after_explanation: selected.includes("P0-10/default") && reportAfterExplanation,
      literature_enabled: literatureEnabled,
      literature_concept_refs: literatureEnabled ? literatureConcepts : [],
      max_tool_runs: toolLimit, max_model_turns: modelLimit };
    void perform(() => api.proposeAssessment(session.id, proposal));
  }
  const reportModeSelected = selected.includes("P0-10/default");
  const presentation = session.presentation;
  const action = (id: string) => presentation?.next_actions.find(item => item.id === id);
  const current = assessment?.freshness.state === "current";
  const preview = session.artifacts.find((item) => item.id === previewId);
  return <section className="assessment-panel" aria-label="细胞状态与产品评估">
    <header className="assessment-heading">
      <div className="assessment-title-row"><h2>产品概况</h2>
        {onOpenReports && <button type="button" onClick={onOpenReports}><FileText aria-hidden="true" />报告</button>}</div>
      {assessment && <dl className="assessment-binding">
        <div><dt>资料版本</dt><dd>{assessment.input_revision}</dd></div>
        <div><dt>纳入细胞</dt><dd>{typeof assessment.data_view.n_observations === "number"
          ? assessment.data_view.n_observations.toLocaleString() : "未提供"}</dd></div>
        <div><dt>结果版本</dt><dd>{assessment.freshness.state === "current" ? "当前" : assessment.freshness.state === "review_pending" ? "待核对" : "历史"}</dd></div>
      </dl>}
    </header>
    {assessment ? <>
      {(presentation?.stage !== "results_ready" || action("resume_assessment")) && <section className="assessment-scope" aria-label="评估范围">
        <details open={Boolean(action("approve_assessment"))}><summary>研究问题</summary><p>{researcherText(assessment.question)}</p></details>
        <p className="assessment-state">{presentation?.stage_label ?? "评估状态暂不可用，请刷新后重试。"}</p>
        {presentation?.issue ? <PresentationIssue issue={presentation.issue} /> : null}
        {assessment.freshness.state === "historical" ? <p className="assessment-warning" role="status">
          历史证据：绑定版本 {assessment.input_revision}，当前事实版本 {assessment.freshness.current_input_revision}。
          选择受影响检查并新建范围；不会自动重算或删除旧结果。</p>
          : assessment.freshness.state === "review_pending" ? <p className="assessment-warning" role="status">
            事实修改尚待确认；当前结果仍绑定版本 {assessment.input_revision}。请使用原事实核对卡确认或放弃修改。</p>
          : null}
        {action("stop") ? <button
          disabled={working || session.status === "stopping"}
          onClick={() => void perform(() => api.stopSession(session.id))}>停止本范围</button> : null}
        {action("resume_assessment") ? <button disabled={disabled || !current}
          onClick={() => void perform(() => api.resumeAssessment(session.id,assessment.scope_id,assessment.scope_digest))}>
            {action("resume_assessment")!.label}</button> : null}
        {assessment.continuation_proposal ? <button disabled={disabled || !current}
          onClick={() => void perform(() => api.proposeAssessment(session.id, assessment.continuation_proposal!))}>
          保留修改意见，申请继续额度</button> : null}
      </section>}
      <DomainSummary key={assessment.scope_digest} session={session} onOpen={openSource} onOpenGraph={onOpenGraph} />
      <section aria-label="确认分析内容">
        <details key={assessment.scope_digest + Boolean(action("approve_assessment"))} open={Boolean(action("approve_assessment"))}>
        <summary>{action("approve_assessment") ? "待确认 · 核对并批准本范围" : "分析内容"}</summary>
        <div role="region" aria-label="审批内容">
        <p>{researcherText(assessment.question)}</p>
        <ul>{assessment.allowed_modes.map((mode) => {
          const candidate = assessment.candidates.find(item => modeKey(item) === modeKey(mode));
          return <li key={modeKey(mode)}>{modeName(mode)}
            {candidate?.source_gene_set && <p>本范围选定来源：{programSourceNames[candidate.source_gene_set] ?? "已选基因集来源"}</p>}
          </li>;
        })}</ul>
        {assessment.report_after_explanation ? <p>完成结果解释后生成研究报告。</p> : null}
        {assessment.literature?.enabled && <p>允许用以下公共词检索 Europe PMC：
          {assessment.literature.concept_refs.map(ref => publicLiteratureConcepts[ref] ?? ref).join("、")}。
          最多检索 {assessment.literature.max_searches} 次、读取 {assessment.literature.max_reads} 篇摘要。</p>}
        {assessment.continuation ? <p>保留已有待修订解释与修改意见。此次继续最多允许 {assessment.max_model_turns} 轮模型处理、
          {assessment.max_tool_runs} 次工具运行；确认后才会继续，解释仍需重新核查。</p> : null}
        <p>本次仅进行上述分析，结果用于研究。</p>
        {action("approve_assessment") ? <>
          <label className="assessment-consent"><input type="checkbox" checked={consent} disabled={disabled || !current}
            onChange={(event) => setConsent(event.target.checked)} />我已核对分析内容与数据来源</label>
          <button disabled={disabled || !current || !consent}
            onClick={() => void perform(() => api.approveAssessment(session.id,assessment.scope_id,assessment.scope_digest))}>批准本范围</button>
        </> : null}
        </div></details>
      </section>
      <section aria-label="前提条件"><details><summary>前提条件与待补充信息</summary>
        {assessment.candidates.map((candidate) => <article key={modeKey(candidate)}>
          <h4>{modeName(candidate)} · {candidate.already_admitted ? "同一请求已执行，不重复选择"
            : candidate.runnable ? "前提满足，可在范围内选择" : "前提未满足"}</h4>
          {candidate.blockers.length ? <><p>阻塞前提</p><ReasonList codes={candidate.blockers} /></> : null}
          {candidate.gaps.length ? <><p>解释缺口（不阻止本项检查）</p><ReasonList codes={candidate.gaps} /></> : null}
        </article>)}
        {!assessment.candidates.length ? <p>尚未提供候选检查状态。</p> : null}
      </details></section>
      <section aria-label="下一步"><details><summary>后续操作</summary>
        {presentation ? <ul>{presentation.next_actions.map(item => <li key={item.id}>{item.label}</li>)}</ul>
          : <p>当前可用操作暂未取得，请刷新后重试。</p>}
      </details></section>
      <section id="assessment-explanations" tabIndex={-1} aria-label="证据说明">
        <details className="assessment-disclosure"><summary>解释与局限 <span>{assessment.hypotheses.length} · 待验证</span></summary>
        {!assessment.hypotheses.length && <p className="assessment-empty-note">尚未形成有来源的解释。可先查看工具观察与待补充条件。</p>}
        {assessment.hypotheses.map((item,index) => {
          const classified = item.provenance_warning !== "legacy_unclassified"
            && item.qualification === "proposed_explanation" && item.interpretation_ref;
          const gapOnly = classified && item.evidence_aliases.length === 0
            && (item.missing_evidence_aliases?.length ?? 0) > 0 && item.opposing_evidence_aliases?.length === 0
            && item.expected_observation === null && item.discriminating_check === null;
          const content = gapOnly ? <>
            <h4>证据缺口说明 · 第 {item.interpretation_ref!.version} 版</h4>
            <span className="interpretation-qualification">缺少证据</span>
            <p>{researcherText(item.statement)}</p>
            <details className="interpretation-detail"><summary>限制与缺失来源</summary>
              <p>仅说明当前证据缺口，不能据此作出结论。</p>
              <h5>限制说明</h5><p>{researcherText(item.competing_explanation)}</p>
              <h5>缺失证据来源</h5><EvidenceLinks aliases={item.missing_evidence_aliases!} onOpen={openSource} onOpenGraph={onOpenGraph} />
            </details>
          </> : <>
          <h4>{classified ? `待检验解释 · 第 ${item.interpretation_ref!.version} 版` : "原解释记录"}</h4>
          <span className="interpretation-qualification">{classified ? "未验证" : "历史未核验"}</span>
          <p>{researcherText(item.statement)}</p>
          <details className="interpretation-detail"><summary>依据、竞争解释与缺口</summary>
          <h5>竞争解释</h5><p>{researcherText(item.competing_explanation)}</p>
          <h5>{classified ? "解释中引用的反对依据" : "原记录标注的反对依据"}</h5>
          {item.opposing_evidence_aliases?.length ? <EvidenceLinks aliases={item.opposing_evidence_aliases} onOpen={openSource} onOpenGraph={onOpenGraph} /> : <p>尚未引用反对证据，不代表不存在。</p>}
          <h5>{classified ? "解释中列出的证据缺口" : "原记录标注的证据缺口"}</h5>
          {item.missing_evidence_aliases?.length ? <EvidenceLinks aliases={item.missing_evidence_aliases} onOpen={openSource} onOpenGraph={onOpenGraph} /> : <p>此解释未列出额外缺失证据。</p>}
          <p>预期观察：{item.expected_observation ?? "尚未提出"}</p>
          {item.discriminating_check === null
            ? <p>本范围没有合适的科学鉴别检查；仍需后续研究。</p>
            : <><p>区分性检查：{modeName({tool_id:item.discriminating_check,mode_id:null})}</p>
</>}
          <h5>引用的观测与依据</h5><EvidenceLinks aliases={item.evidence_aliases} onOpen={openSource} onOpenGraph={onOpenGraph} />
          {item.literature_support?.map(use => {
            const source = assessment.literature?.sources.find(row => row.source_ref === use.source_ref);
            return <div key={use.source_ref}><h5>文献背景与适用条件（待核对）</h5>
              {source && <a href={source.url} target="_blank" rel="noreferrer">{source.metadata.title}</a>}
              <p>{use.rationale}</p><p>{[use.species, use.lineage, use.stage, use.experimental_context].join("；")}</p>
            </div>;
          })}
          </details></>;
          return classified ? <article key={index}>{content}</article>
            : <details key={index}><summary>历史解释（未核验）</summary>{content}</details>;
        })}
        </details>
      </section>
      {assessment.literature?.enabled && <section aria-label="参考文献"><details>
        <summary>参考文献 · 已读 {assessment.literature.sources.length} 篇</summary>
        <p>已检索 {assessment.literature.searches_used} / {assessment.literature.max_searches} 次，
          已读取 {assessment.literature.reads_used} / {assessment.literature.max_reads} 次。</p>
        {assessment.literature.state === "no_results" && <p>本次查询未找到文献；这不表示不存在相关研究。</p>}
        {assessment.literature.state === "unavailable" && <p>文献服务暂不可用；现有测量仍然保留。</p>}
        {assessment.literature.sources.map(source => <article id={source.source_ref} key={source.source_ref}>
          <h4><a href={source.url} target="_blank" rel="noreferrer">{source.metadata.title}</a></h4>
          <p>{source.metadata.authors} · {source.metadata.year ?? "年份未提供"} · {source.metadata.journal ?? "期刊未提供"}</p>
          <p>{({
            unknown:"撤稿与更正状态未完整提供，尚未核实。",
            no_flag_reported:"来源未报告撤稿或更正标记，仍需核实。",
            correction_reported:"来源报告更正信息，请核对更正内容。",
            retraction_or_concern_reported:"来源报告撤稿或关注声明，不应据此确立机制解释。",
          })[source.metadata.publication_status]}</p>
          {source.metadata.corrections?.map((notice,index)=><p key={index}>
            {[notice.type,notice.source,notice.id,notice.reference,notice.note].filter(Boolean).join(" · ")}</p>)}
          <p>{source.content_level === "abstract" ? "已读取摘要" : "仅有书目信息，不能作为机制依据"} · 检索时间：{source.retrieved_at}</p>
          {source.abstract && <details><summary>查看保存的摘要</summary><p>{source.abstract}</p></details>}
        </article>)}
      </details></section>}
      <section id="assessment-sources" tabIndex={-1} aria-label="结果依据">
        <details ref={sources} className="assessment-disclosure"><summary>查看来源 <span>{assessment.evidence.length}</span></summary>
        {assessment.evidence.map((evidence, index) => <details key={evidence.alias} id={"assessment-evidence-"+evidence.alias}
          open={openEvidence===evidence.alias}>
          <summary onClick={(event) => {event.preventDefault();setOpenEvidence(openEvidence===evidence.alias?null:evidence.alias);}}>
            {toolName(evidence.tool_id)} · 记录 {index + 1}</summary>
          <p>{stateName(evidence.state)}</p>
          {evidence.interpretation_scope ? <p>解释范围：{researcherText(evidence.interpretation_scope)}</p> : null}
          {evidence.reason_code ? <ReasonList codes={[evidence.reason_code]} /> : null}
          {evidence.summary && Object.keys(evidence.summary).length ? <FieldTable value={evidence.summary} label="观察与限制" /> : null}
          {evidence.measurements?.length ? <FieldTable value={evidence.measurements} label={"测量值与细胞数量"} /> : null}
          {evidence.artifact_ids?.length ? evidence.artifact_ids.map((id) => {
            const artifact=session.artifacts.find((item)=>item.id===id);
            return artifact && ["figure", "table"].includes(artifact.kind) && !artifact.media_type.includes("json")
              ? <button key={id} onClick={()=>setPreviewId(id)}>查看{artifact.kind === "figure" ? "图表" : "数据表"}</button> : null;
          }) : null}
        </details>)}
        {preview ? <div className="assessment-preview"><button onClick={()=>setPreviewId(null)}>关闭预览</button>
          <ArtifactCard key={session.id+preview.id} sessionId={session.id} artifact={preview} /></div> : null}
        </details>
      </section>
      {assessment.history.length ? <details><summary>先前评估范围</summary>
        {assessment.history.map((item)=><article key={item.scope_id}><p>{item.question} · 事实版本 {item.input_revision}</p>
          <p>{stateName(item.status)}</p></article>)}
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
        <label className="assessment-mode"><input type="checkbox" checked={reportModeSelected && reportAfterExplanation}
          disabled={!reportModeSelected} onChange={(event)=>setReportAfterExplanation(event.target.checked)} />
          解释完成后，点击继续时生成私有研究报告</label>
        <label className="assessment-mode"><input type="checkbox" checked={literatureEnabled}
          onChange={event => setLiteratureEnabled(event.target.checked)} />检索公开文献辅助生物学解释</label>
        {literatureEnabled && <fieldset><legend>允许发送的公共检索词</legend>
          <p>选择与本问题相关的词。外部查询仅使用这些词和生物学主题，不发送产品名称、样本标识或私有数值。
            最多检索 3 次、读取 6 篇摘要；未找到匹配词时，需要先补充受审查的公共词。</p>
          {Object.entries(publicLiteratureConcepts).map(([ref, label]) => <label className="assessment-mode" key={ref}>
            <input type="checkbox" checked={literatureConcepts.includes(ref)}
              onChange={event => setLiteratureConcepts(values => event.target.checked
                ? [...values, ref] : values.filter(value => value !== ref))} />{label}</label>)}
        </fieldset>}
        <details><summary>执行次数上限</summary>
        <label>最多工具运行次数<input type="number" required min={1} max={32} value={toolLimit}
          onChange={(event)=>setToolLimit(Number(event.target.value))} /></label>
        <label>最多模型轮次<input type="number" required min={1} max={64} value={modelLimit}
          onChange={(event)=>setModelLimit(Number(event.target.value))} /></label></details>
        <p>服务端将列出每项检查的实际阻塞与解释缺口。准备不是批准，也不会更改确认事实。</p>
        <button type="submit" disabled={!uploadId || !question.trim() || !selected.length || literatureEnabled && !literatureConcepts.length}>准备范围供核对</button>
      </fieldset>
    </form> : null}
  </section>;
}
