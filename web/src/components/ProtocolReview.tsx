import { useState } from "react";
import type { ProtocolAction, ProtocolFormalization, ProtocolQuestion, ProtocolSource, ProtocolVersion } from "../types";

type Props = {
  value: ProtocolFormalization;
  busy: boolean;
  onAction: (action: ProtocolAction) => Promise<void>;
  downloadUrl: (versionId: string, kind: string) => string;
};
const errors: Record<string, string> = {
  unsupported_literal: "生成内容含未获原文支持的数值，已阻止发布。",
  unknown_source: "生成内容引用了不存在的来源，已阻止发布。",
  source_accounting_incomplete: "部分原文尚未交代用途，未发布完整表示。",
  repair_changed_source_steps: "修正过程改变了原步骤，已保留旧版本。",
  invalid_bpl_source_span: "BPL 片段与来源映射尚未对应，请重试。",
  protocol_source_changed: "附件或补充内容已变化，需要重新生成。",
  bpl_step_limit: "步骤超过本期 200 项上限；未截断后发布。",
  protocol_provider_unavailable: "模型暂不可用，已有记录已保留。",
  bpl_policy_rejected: "草稿包含本次检查不接受的模块或路径。",
};
const syntaxLabels = { not_run: "未运行", passed: "通过", failed: "有错误" };
const compilerLabels = { not_run: "未运行", passed: "返回成功", failed: "返回错误", unavailable: "暂不可用" };
const coverageLabels = { complete_for_extracted_scope: "已清点提供的片段", partial: "仅部分内容或映射待核对", needs_input: "仍有缺项" };

function Sources({ sources }: { sources: ProtocolSource[] }) {
  return <div className="protocol-sources">{sources.map(source => <blockquote key={source.id}>
    <p>{source.text || "暂未提供明确内容"}</p><footer>{source.label} · {source.location}</footer>
  </blockquote>)}</div>;
}

export function ProtocolReview({ value, busy, onAction, downloadUrl }: Props) {
  return <section className="protocol-review" aria-label={"方案核对：" + value.name}>
    <header><h4>{value.name}</h4><span>方案表示 · 非执行记录</span></header>
    <p className="intake-hint">用于核对方案规定的阶段、条件与缺项；不决定这批细胞的身份、独立重复或评分。</p>
    {value.state === "running" || value.state === "pending" ? <p role="status">正在生成并检查方案表示…</p> : null}
    {value.state === "not_started" ? <p>此附件尚未形式化，打开页面不会自动重跑。</p> : null}
    {value.state === "unavailable" || value.state === "cancelled" ? <p className="intake-hint" role="status">
      {value.state === "cancelled" ? "本次生成已停止。" : errors[value.error ?? ""] ?? "本次生成未完成。"}
      {value.latest ? "显示上次完整版本，未用失败结果替换。" : "原附件与已有资料保持不变。"}
    </p> : null}
    {value.latest ? <VersionView key={value.latest.id} version={value.latest} ready={value.state === "complete"}
      busy={busy} onAction={onAction} downloadUrl={downloadUrl} /> : null}
    <button type="button" disabled={busy || value.state === "running"} onClick={() => { void onAction({ action: "formalize" }).catch(() => {}); }}>
      {value.state === "not_started" ? "生成方案表示" : value.state === "unavailable" || value.state === "cancelled" ? "重试生成" : "重新生成"}
    </button>
    {value.versions.length ? <details className="protocol-history"><summary>版本记录（{value.versions.length}）</summary>
      <ol>{value.versions.map((entry, index) => <li key={entry.id}>
        版本 {index + 1} · {entry.review_state === "reviewed" ? "已人工核对" : "未核对"}
        <span className="protocol-version-time">{entry.created_at ? new Date(entry.created_at).toLocaleString() : ""}</span>
        <a href={downloadUrl(entry.id, "version")} download>下载该版本记录</a>
      </li>)}</ol>
    </details> : null}
  </section>;
}

function VersionView({ version, ready, busy, onAction, downloadUrl }: {
  version: ProtocolVersion; ready: boolean; busy: boolean;
  onAction: Props["onAction"]; downloadUrl: Props["downloadUrl"];
}) {
  const [acknowledged, setAcknowledged] = useState(false);
  const [editing, setEditing] = useState(false);
  const [bpl, setBpl] = useState(version.bpl);
  const [saving, setSaving] = useState(false);
  const [editSupplement, setEditSupplement] = useState<string | null>(null);
  const blocked = busy || saving;
  const currentQuestion = version.questions.find(question => question.answer_state === "unanswered");
  const supplement = version.supplements.find(item => item.id === editSupplement);
  const question = supplement ? {
    id: supplement.question_id, title: "修改补充：" + supplement.location, source_ids: [], step_ids: [],
    sources: [] as ProtocolSource[], options: [], answer_state: "unanswered" as const,
  } : currentQuestion;
  const save = async (action: ProtocolAction) => {
    setSaving(true);
    try {
      await onAction(action);
      setEditing(false);
      setEditSupplement(null);
    } finally { setSaving(false); }
  };
  return <>
    <ul className="protocol-statuses" aria-label="独立检查状态">
      <li>语法检查：{syntaxLabels[version.syntax_state]}</li>
      <li>编译器：{compilerLabels[version.compiler_state]}</li>
      <li>来源与覆盖：{coverageLabels[version.coverage_state]}</li>
      <li>人工核对：{version.review_state === "reviewed" ? "已核对本表示" : "未核对"}</li>
    </ul>
    <p className="intake-hint">编译返回成功不代表参数正确或生物学有效；来源清点也不是完整语义保真的证明。</p>
    {version.source_binding.sources_truncated ? <p className="intake-hint">只处理了部分文字，未覆盖整份附件。</p> : null}
    <details className="protocol-diagnostics"><summary>检查范围与未检查项</summary>
      <p>BPL {version.compiler.version} · {version.compiler.verified ? "固定版本已核实" : "编译环境未核实"}</p>
      <small>本次不检查本批样本是否实际执行方案，不运行实验或模拟。</small>
      {[...version.diagnostics, ...version.unchecked].length ? <ul>
        {[...version.diagnostics, ...version.unchecked].map((item, index) => <li key={item.code + index}>
          {item.line ? "BPL 第 " + item.line + " 行：" : ""}{item.message}
        </li>)}
      </ul> : <p>未报告额外诊断；这不扩大上述检查范围。</p>}
    </details>
    <ol className="protocol-steps">{version.steps.map(step => <li key={step.id}>
      <h5>{step.label}</h5><p>{step.operations}</p>
      <small>{step.origin === "user" ? "用户编辑 · 原出处对应已解除，待核对" :
        step.origin === "source_and_user" ? "模型整理 + 用户补充 · 待核对" : "模型按原文整理 · 待核对"}</small>
      {step.sources.length ? <details><summary>查看步骤出处</summary><Sources sources={step.sources} /></details> : null}
    </li>)}</ol>
    {version.excluded_sources.length ? <details><summary>未纳入步骤的原文片段（{version.excluded_sources.length}）</summary>
      {version.excluded_sources.map(item => <div key={item.source_id}><p>模型给出的理由（待核对）：{item.reason}</p><Sources sources={[item.source]} /></div>)}
    </details> : null}
    {version.supplements.length ? <div className="protocol-supplements"><h5>用户补充（非原文）</h5>
      {version.supplements.map(item => <p key={item.id}>
        {item.location}：{item.unsure ? "暂不确定" : item.text}{item.superseded ? "（已被后续回答更新）" : ""}
        {!item.superseded ? <button type="button" disabled={blocked || !ready} onClick={() => setEditSupplement(item.id)}>修改补充回答</button> : null}
      </p>)}
    </div> : null}
    {question && ready ? <ProtocolQuestionForm key={version.id + ":" + question.id + ":" + (editSupplement ?? "")}
      question={question} busy={blocked} initial={supplement?.text}
      onSave={async (value, other, unsure) => save({ action: "answer", question_id: question.id, value, other, unsure })}
      onCancel={editSupplement ? () => setEditSupplement(null) : undefined} /> : null}
    <details className="protocol-code"><summary>BPL 草稿与检查记录</summary>
      {editing ? <><label className="intake-field">BPL 草稿
        <textarea aria-label="BPL 草稿" rows={10} value={bpl} maxLength={128 * 1024}
          onChange={event => setBpl(event.target.value)} disabled={blocked} />
      </label><p className="intake-hint">编辑后形成新版本；旧出处映射与人工核对不自动沿用。</p>
        <button type="button" disabled={blocked || !bpl.trim()} onClick={() => { void save({ action: "edit", bpl }).catch(() => {}); }}>保存新草稿并重新检查</button>
        <button type="button" disabled={blocked} onClick={() => { setBpl(version.bpl); setEditing(false); }}>取消编辑</button>
      </> : <><pre><code>{version.bpl}</code></pre>
        <button type="button" disabled={blocked || !ready} onClick={() => setEditing(true)}>编辑 BPL 草稿</button></>}
      <div className="protocol-downloads">
        {([["bpl", "下载 BPL"], ["ast", "下载语法记录"], ["plan", "下载编译产物（非执行计划）"],
          ["diagnostics", "下载检查记录"]] as const).map(([kind, label]) =>
          <a key={kind} href={downloadUrl(version.id, kind)} download>{label}</a>)}
      </div>
    </details>
    {version.review_state === "unreviewed" ? <div className="protocol-confirm">
      <label><input type="checkbox" checked={acknowledged} disabled={blocked || !ready || editing || !!editSupplement}
        onChange={event => setAcknowledged(event.target.checked)} />
        我已核对本版本及其未检查项（不代表已执行实验）</label>
      <button type="button" disabled={!acknowledged || blocked || !ready || editing || !!editSupplement}
        onClick={() => { void save({ action: "review", digest: version.digest }).catch(() => {}); }}>保存核对版本</button>
    </div> : <p className="protocol-confirmed">已保存本版本的人工核对；未检查项仍然保留。</p>}
  </>;
}

function ProtocolQuestionForm({ question, busy, initial, onSave, onCancel }: {
  question: ProtocolQuestion; busy: boolean; initial?: string;
  onSave: (value: string, other: boolean, unsure: boolean) => Promise<void>; onCancel?: () => void;
}) {
  const [choice, setChoice] = useState(initial === undefined ? "" : "__other__");
  const [text, setText] = useState(initial ?? "");
  const [saving, setSaving] = useState(false);
  const other = choice === "__other__", unsure = choice === "__unsure__";
  const value = unsure ? "" : other ? text.trim() : choice;
  return <form className="intake-question protocol-question" onSubmit={event => {
    event.preventDefault();
    if ((!value && !unsure) || saving || busy) return;
    setSaving(true);
    void onSave(value, other, unsure).catch(() => {}).finally(() => setSaving(false));
  }}>
    <fieldset disabled={busy || saving}><legend>方案待补充：{question.title}</legend>
      {question.sources.length ? <details><summary>此问题对应的原文</summary><Sources sources={question.sources} /></details> : null}
      {[...question.options, { value: "__other__", label: "其他（自定义输入）" }, { value: "__unsure__", label: "暂不确定" }].map(option =>
        <label className="intake-choice" key={option.value}><input type="radio" name={"protocol-" + question.id}
          value={option.value} checked={choice === option.value} onChange={() => setChoice(option.value)} />{option.label}</label>)}
      {other ? <label className="intake-field">方案补充内容
        <input aria-label="方案补充内容" maxLength={1000} value={text} onChange={event => setText(event.target.value)} /></label> : null}
      <button type="submit" disabled={!value && !unsure}>{saving ? "正在保存…" : "保存方案补充"}</button>
      {onCancel ? <button type="button" onClick={onCancel}>取消修改</button> : null}
    </fieldset>
  </form>;
}
