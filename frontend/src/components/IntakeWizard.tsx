import { useState, type ReactNode } from "react";
import type { IntakeFacts, IntakeResponse, IntakeQuestion } from "../types";
import { intakeLabels, intakeValue } from "./intakeLabels";

type Props = {
  data: IntakeResponse;
  busy: boolean;
  onAnswer: (field: keyof IntakeFacts, value: string | number, other: boolean) => Promise<void>;
  onProtocol: (file: File) => void;
  onParse: () => void;
  onStage: (facts: IntakeFacts) => void;
  protocolReview?: ReactNode;
};

const visibleFields: (keyof IntakeFacts)[] = ["product_name", "starting_cell_type", "cell_line", "culture_day",
  "target_cell_type", "target_stage", "assay", "sequencing_method", "protocol_name", "independent_cultures"];
const provenance: Record<string, string> = { metadata: "文件元数据", model: "模型提取 · 待核对", user: "您已填写" };

export function IntakeWizard({ data, busy, onAnswer, onProtocol, onParse, onStage, protocolReview }: Props) {
  const [edit, setEdit] = useState<keyof IntakeFacts | null>(null);
  const fill = data.autofill!;
  const parsing = fill.state === "not_started" || fill.state === "parsing";
  const conflict = fill.conflicts[0];
  const batch = fill.batch_binding;
  const question: IntakeQuestion | undefined = edit
    ? { field: edit, title: "修改" + (intakeLabels[edit] ?? edit), options: [],
        input_type: ["culture_day", "independent_cultures"].includes(edit) ? "number" : "text" }
    : conflict ? { field: conflict.field, title: "请核对冲突：" + intakeLabels[conflict.field],
        options: [], input_type: conflict.field === "culture_day" ? "number" : "text" }
    : fill.questions[0];
  return <div className="intake-wizard">
    <section aria-label="已提取的实验信息" className="intake-extracted">
      <h3>已提取的实验信息</h3>
      <p className="intake-hint">以下内容为可编辑草稿；出处不等于实验事实已确认。</p>
      {fill.sources_truncated ? <p className="intake-hint">本次解析只包含部分文字，未读到的内容会保留缺失。</p> : null}
      <dl>{visibleFields.filter(field => data.facts[field] != null && data.facts[field] !== "unknown" || fill.other_answers[field]).map(field => {
        const origin = fill.field_sources[field];
        const ids = origin?.source_ids ?? [];
        return <div key={field}>
          <dt>{intakeLabels[field]}</dt>
          <dd><span>{fill.other_answers[field] ?? (field === "culture_day" ? "D" + data.facts[field] : intakeValue(data.facts[field] ?? null))}</span>
            {field !== "independent_cultures" || !batch ? <button type="button" disabled={busy || parsing} onClick={() => setEdit(field)} aria-label={"修改" + intakeLabels[field]}>修改</button> : null}
            {origin ? <small>{provenance[origin.kind] ?? "待核对"}</small> : null}
            {ids.length ? <details><summary>查看出处</summary>
              {ids.map(id => { const source = fill.sources.find(item => item.id === id);
                return source ? <p key={id}>{source.label} · {source.location}</p> : null; })}
              <blockquote>{origin.quote}</blockquote>
            </details> : null}
          </dd>
        </div>;
      })}</dl>
      {batch ? <div className="intake-batch">
        <p>批次字段核对：{batch.column} · {intakeValue(batch.role)}</p>
        {batch.role === "independent_culture" && (!batch.complete || batch.missing > 0)
          ? <p>这列有缺失值或读取不完整，独立培养次数仍未确定。</p> : null}
        <button type="button" disabled={busy || parsing}
          onClick={() => { void onAnswer("culture_batch_column", batch.column, false).catch(() => {}); }}>重新核对批次字段</button>
      </div> : null}
      {fill.other_answers.culture_batch_role ? <p>字段说明（待核对）：{fill.other_answers.culture_batch_role}
        <button type="button" disabled={busy || parsing} onClick={() => setEdit("culture_batch_role")}>修改字段说明</button>
      </p> : null}
      {fill.other_answers.culture_batch_column ? <p>批次对应关系（待核对）：{fill.other_answers.culture_batch_column}
        <button type="button" disabled={busy || parsing} onClick={() => setEdit("culture_batch_column")}>修改对应关系</button>
      </p> : null}
      {fill.samples.length ? <details className="intake-samples"><summary>样本信息（{fill.samples.length} 个已列出）</summary>
        {fill.samples.map(sample => <p key={sample.sample_id}>{sample.sample_id}：{sample.culture_days.map(day => "D" + day).join(" / ") || "天数未标注"}
          {sample.missing_days ? "；有观测缺少天数" : ""} · {sample.n_observations} 个观测</p>)}
        <small>样本数量不代表独立培养次数。{fill.samples.some(s => !s.sample_summary_complete) ? "样本列表未完整展开。" : ""}</small>
      </details> : null}
    </section>
    <section className="intake-protocol" aria-label="分化方案">
      <h3>分化 protocol</h3>
      <p>上传方案，自动整理起始细胞、分化目标与阶段安排。</p>
      <label className="intake-protocol-upload">上传分化 protocol
        <input type="file" accept=".pdf,.docx,.txt,.md" disabled={busy || parsing}
          onChange={event => { const file = event.currentTarget.files?.[0]; if (file) onProtocol(file); event.currentTarget.value = ""; }} />
      </label>
      <small>支持 PDF、Word、文本，单个文件不超过 25 MB。扫描版 PDF 需先转为可选中文字。</small>
      {fill.protocols.map(protocol => <p key={protocol.id}>{protocol.name}</p>)}
      {protocolReview}
      {fill.protocol_stages.length && !fill.formalizations?.some(item => item.latest) ? <div className="intake-protocol-stages">
        <p>方案中的阶段安排（不证明这批样本实际完成了全部步骤）</p>
        <ol>{fill.protocol_stages.map((stage, i) => <li key={i}>
          <strong>{stage.label}</strong>
          {stage.start_day !== null || stage.end_day !== null ? <span> D{stage.start_day ?? "?"}–D{stage.end_day ?? "?"}</span> : null}
          {stage.timing_state === "needs_confirmation" ? <small>起止时间未获引用原文明确支持，已留空待核对。</small> : null}
          <p>{stage.operations}</p><details><summary>方案原文</summary><blockquote>{stage.quote}</blockquote>
            <small>{stage.source_ids.map(id => fill.sources.find(s => s.id === id)?.location).filter(Boolean).join("、")}</small></details>
        </li>)}</ol>
      </div> : null}
    </section>
    {parsing ? <p role="status">正在解析实验元数据与方案，完成后只补充缺失或冲突的信息…</p> : <>
      {fill.state === "unavailable" ? <p className="intake-hint">语义解析暂未完成；文件中直接读到的信息已保留。
        <button type="button" disabled={busy} onClick={onParse}>重试解析</button></p> : null}
      {conflict && !edit ? <p role="alert">当前记录：{conflict.observed === null ? "未提供" : String(conflict.observed)}；方案中的候选：{String(conflict.extracted)}。请按这批样本的实际情况填写。</p> : null}
      {question ? <IntakeQuestionForm key={question.field + ":" + fill.revision + ":" + (edit ?? "")}
        question={question} busy={busy} initial={edit ? fill.other_answers[edit] ?? data.facts[edit] : undefined}
        onSave={async (value, other) => { await onAnswer(question.field, value, other || edit === "culture_batch_column" || edit === "culture_batch_role"); setEdit(null); }}
        onCancel={edit ? () => setEdit(null) : undefined} /> : <p>当前没有待补充的问题，请核对以上草稿。</p>}
      <button className="intake-primary" type="button" disabled={busy || !!edit || fill.conflicts.length > 0}
        onClick={() => onStage(data.facts)}>核对当前资料</button>
      <small>可以先核对已知部分；这一步只展示确认卡片，不运行分析。</small>
    </>}
  </div>;
}

function IntakeQuestionForm({ question, busy, initial, onSave, onCancel }: {
  question: IntakeQuestion; busy: boolean; initial?: string | number | null;
  onSave: (value: string | number, other: boolean) => Promise<void>; onCancel?: () => void;
}) {
  const [choice, setChoice] = useState("");
  const [text, setText] = useState(initial == null || initial === "unknown" ? "" : String(initial));
  const [saving, setSaving] = useState(false);
  const other = choice === "__other__";
  const free = !question.options.length || other;
  const value = free ? text.trim() : choice;
  const submit = async () => {
    if (!value || saving || busy) return;
    setSaving(true);
    try { await onSave(question.input_type === "number" ? Number(value) : value, other); }
    catch { /* The parent displays the save error; retain this answer for retry. */ }
    finally { setSaving(false); }
  };
  return <form className="intake-question" onSubmit={event => { event.preventDefault(); void submit(); }}>
    <fieldset disabled={busy || saving}>
      <legend>{question.title}</legend>
      {question.help ? <p className="intake-hint">{question.help}</p> : null}
      {question.options.map(option => <label className="intake-choice" key={option.value}>
        <input type="radio" name={question.field} value={option.value} checked={choice === option.value}
          onChange={() => setChoice(option.value)} /><span>{option.label}</span>
      </label>)}
      {free ? <label className="intake-field">{other ? "请填写具体内容" : "填写答案"}
        <input aria-label={other ? "请填写具体内容" : question.title} type={question.input_type} min={question.field === "independent_cultures" ? 1 : 0}
          max={question.field === "independent_cultures" ? 100000 : 10000} step={1} maxLength={240}
          value={text} onChange={event => setText(event.target.value)} />
      </label> : null}
      {question.field === "independent_cultures" ? <small>按独立培养实验计数，不是细胞数、样本标签数或测序批次数。</small> : null}
      <button type="submit" disabled={!value}>{saving ? "正在保存…" : "保存并继续"}</button>
      {onCancel ? <button type="button" onClick={onCancel}>取消修改</button> : null}
    </fieldset>
  </form>;
}
