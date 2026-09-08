import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api";
import type { IntakeFacts, IntakeResponse, Session } from "../types";
import { InputChangeCard } from "./InputChangeCard";
import { intakeLabels, intakeValue, intakeValues } from "./intakeLabels";

type Props = {
  session: Session;
  busy: boolean;
  onSession: (session: Session) => void;
  onError: (error: unknown) => void;
  onConfirm: () => void;
  onDiscard: () => void;
};

const stateLabels: Record<string, string> = {
  not_run: "待运行", available: "已有 QC 证据", unavailable: "证据暂不可用",
  needs_confirmation: "待确认当前资料；已有证据保留",
  next_stage: "可准备下一阶段", needs_evidence: "待补充证据",
  needs_product_definition: "待确认正式产品定义与分析输入",
  needs_method_inputs: "待补充方法与取样设计",
};
const blockerLabels: Record<string, string> = {
  supported_product_family_required: "当前细胞状态参考仅支持 hPSC-mDA；其他产品可先完成通用 QC。",
  source_family_id_required: "继续细胞状态分析前，需要确认数据来源家族。",
  qc_evidence_unavailable: "已有 QC 文件暂不可用或完整性校验未通过，需要先处理证据问题。",
  cell_state_history_review_required: "已有细胞状态运行记录；请先查看其输入与结果，再决定是否需要新的分析。",
};
const errorMessage = (error: unknown) => {
  if (error instanceof ApiError && error.message === "invalid_intake_declaration")
    return "资料中有不符合文件结构的声明，请核对计数位置与元数据列。";
  if (error instanceof ApiError && error.status === 409)
    return "资料或运行状态已变化，请重新查看当前资料后再操作。";
  return "暂时无法读取或保存产品资料，请重试。";
};

export function ProductIntake(props: Props) {
  const [selected, setSelected] = useState<string | null>(null);
  const uploads = props.session.uploads;
  const reviewUpload = props.session.pending_input_change?.kind === "intake"
    ? props.session.pending_input_change.upload_id : null;
  const aid = reviewUpload ?? uploads.find((upload) => upload.id === selected)?.id ?? uploads.at(-1)?.id;
  if (!aid) return (
    <section className="product-intake intake-start" aria-label="产品资料">
      <p className="intake-eyebrow">移植前 · 研究性评估</p>
      <h2>先认识这批细胞</h2>
      <p>在对话框上传 H5AD 后，这里会展示文件结构、产品资料和下一阶段计划。</p>
      <p>先看数据是否可分析，再梳理细胞组成、目标特征、发育阶段及非目标群体等证据。</p>
      <small>比较数据与移植后数据不是开始评估的必要条件。</small>
    </section>
  );
  return (
    <section className="product-intake" aria-label="产品资料">
      <p className="intake-eyebrow">1 确认资料 → 2 查看计划 → 3 批准运行</p>
      <h2>产品资料</h2>
      {uploads.length > 1 ? (
        <label className="intake-field">本次评估文件
          <select value={aid} onChange={(event) => setSelected(event.target.value)} disabled={props.busy || reviewUpload !== null}>
            {uploads.map((upload) => <option key={upload.id} value={upload.id}>{upload.name}</option>)}
          </select>
        </label>
      ) : <p className="intake-filename">{uploads[0].name}</p>}
      <IntakeFile key={props.session.id + ":" + aid} {...props} aid={aid} />
    </section>
  );
}

function IntakeFile({ aid, ...props }: Props & { aid: string }) {
  const [data, setData] = useState<IntakeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  const [working, setWorking] = useState(false);
  const [editing, setEditing] = useState(false);
  const mounted = useRef(false);
  const { session } = props;
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    api.getIntake(session.id, aid, controller.signal).then((next) => {
      if (!active) return;
      setData(next);
      setError(null);
    }).catch((cause: unknown) => {
      if (active) {
        setError(errorMessage(cause));
        if (cause instanceof ApiError && cause.status === 401) props.onError(cause);
      }
    });
    return () => { active = false; controller.abort(); };
  }, [session.id, aid, session.pending_input_change?.id, session.input_review_required,
      session.status, session.plan?.id, retry, props.onError]);

  const perform = async (operation: () => Promise<Session>) => {
    setWorking(true);
    setError(null);
    try {
      const next = await operation();
      if (!mounted.current) return;
      props.onSession(next);
      setEditing(false);
      setRetry((value) => value + 1);
    } catch (cause) {
      if (mounted.current) {
        setError(errorMessage(cause));
        if (cause instanceof ApiError && cause.status === 401) props.onError(cause);
      }
    } finally {
      if (mounted.current) setWorking(false);
    }
  };
  const busy = props.busy || working;
  const pending = session.pending_input_change?.kind === "intake"
    && session.pending_input_change.upload_id === aid ? session.pending_input_change : null;
  if (!data) return <div role="status">
    <p>{error ?? "正在读取文件结构…"}</p>
    {error ? <button onClick={() => setRetry((value) => value + 1)}>重新读取</button> : null}
  </div>;
  return (
    <>
      <div className="intake-observed">
        <strong>文件中检测到</strong>
        <p>{data.observed.n_observations ?? "未知数量"} 个观测 · {data.observed.n_genes ?? "未知数量"} 个基因</p>
        <small>仅文件结构。实验类型、原始计数语义与产品目标需要您确认。</small>
      </div>
      {error ? <p className="intake-error" role="alert">{error}</p> : null}
      {data.state === "stale" ? <p className="intake-error">高级输入已修改；请核对最新声明并重新确认产品资料。</p> : null}
      {pending ? (
        <InputChangeCard pending={pending} uploads={session.uploads} busy={busy}
          onConfirm={props.onConfirm} onDiscard={props.onDiscard} onKeep={() => undefined} />
      ) : data.state !== "confirmed" || editing ? (
        <>
          {editing ? <button className="intake-cancel" onClick={() => setEditing(false)}
            disabled={busy}>取消编辑</button> : null}
          <IntakeForm key={JSON.stringify(data.facts)} data={data} busy={busy}
            onStage={(facts) => void perform(() => api.stageIntake(session.id, aid, facts))} />
        </>
      ) : (
        <div className="intake-confirmed">
          <header><strong>研究者已确认</strong><button onClick={() => setEditing(true)} disabled={busy}>修改资料</button></header>
          <dl>{Object.entries(data.facts).map(([key, value]) => (
            <div key={key}><dt>{intakeLabels[key]}</dt><dd>{intakeValue(value)}</dd></div>
          ))}</dl>
          <small>这份声明不是正式产品定义，也不证明细胞身份或生物学独立性。</small>
        </div>
      )}
      <div className="intake-roadmap">
        <h3>这次评估将回答什么？</h3>
        <p>以下是证据路线，不是已完成的结论，也不是一次批准所有分析。</p>
        <ol>{data.roadmap.map((row) => <li key={row.question}>
          <span>{row.question}</span><small>{stateLabels[row.state] ?? "待补充输入"}</small>
        </li>)}</ol>
        {data.state === "confirmed" ? (
          <>
            {data.facts.product_family === "hpsc_mda" && data.facts.target_cell_type && data.facts.target_stage && !session.input_review_required ? (
              <div className="intake-scientific-next">
                <button disabled={busy || editing || session.plan?.status === "proposed"}
                  onClick={() => void perform(() => api.draftScientificInputs(session.id, aid))}>整理科学输入草稿</button>
                <small>仅向模型提供已确认的产品家族、目标细胞与预期阶段。候选来源和确认卡片显示在对话中。</small>
              </div>
            ) : null}
            {data.blockers.map((reason) => <p className="intake-gap" key={reason}>
              {blockerLabels[reason] ?? "细胞状态分析所需的参考资源尚未就绪；已有证据会保留。"}
            </p>)}
            {data.next_tool && !session.input_review_required ? (
              <>
                <p><strong>下一阶段：</strong>{data.next_tool === "P0-01" ? "输入质量与可分析性检查" : "基于已配置参考的候选细胞状态分析"}</p>
                {data.measurement_spec_ref ? <p className="intake-reference">分析规格：{data.measurement_spec_ref}</p> : null}
                <button className="intake-primary" disabled={busy || editing || session.plan?.status === "proposed"}
                  onClick={() => void perform(() => api.prepareIntake(session.id, aid))}>生成下一阶段计划</button>
                <small>生成后请在对话中查看并单独批准；现在不会运行。</small>
              </>
            ) : data.qc_state === "not_run" && !session.input_review_required ? <p>开始 QC 还需确认实验类型、原始计数语义和计数位置。不确定时请保留未知。</p> : null}
          </>
        ) : <p>先核对并确认资料，再生成可执行的下一阶段计划。</p>}
        <small>缺少比较组或移植后数据不会阻止移植前评估；结果不作临床或放行判断。</small>
      </div>
    </>
  );
}

function IntakeForm({ data, busy, onStage }: {
  data: IntakeResponse; busy: boolean; onStage: (facts: IntakeFacts) => void;
}) {
  const [facts, setFacts] = useState(data.facts);
  const set = <K extends keyof IntakeFacts>(key: K, value: IntakeFacts[K]) =>
    setFacts((current) => ({ ...current, [key]: value }));
  const text = (key: "product_name" | "target_cell_type" | "target_stage" | "source_family_id") => (
    <label className="intake-field">{intakeLabels[key]}
      <input value={facts[key] ?? ""} maxLength={key === "target_stage" || key === "target_cell_type" ? 240 : 160}
        onChange={(event) => set(key, event.target.value || null)} />
    </label>
  );
  const select = (key: "product_family" | "sampling_context" | "assay" | "matrix_location" |
    "count_semantics" | "sample_id_column" | "capture_id_column" | "gene_symbol_column", values: string[], nullable = false) => (
    <label className="intake-field">{intakeLabels[key]}
      <select value={facts[key] ?? ""} onChange={(event) => set(key, (event.target.value || null) as IntakeFacts[typeof key])}>
        {nullable ? <option value="">尚未选择</option> : null}
        {values.map((value) => <option key={value} value={value}>{intakeValues[value] ?? value}</option>)}
      </select>
    </label>
  );
  return (
    <form className="intake-form" onSubmit={(event) => { event.preventDefault(); onStage(facts); }}>
      <fieldset disabled={busy}>
        <legend>请补充您知道的事实</legend>
        {text("product_name")}
        {select("product_family", ["unknown", "hpsc_mda", "other"])}
        {text("target_cell_type")}
        {text("target_stage")}
        {select("sampling_context", ["unknown", "pretransplant_preparation", "process_sample"])}
        <label className="intake-field">{intakeLabels.independent_cultures}
          <input type="number" min={1} max={100000} step={1} value={facts.independent_cultures ?? ""}
            onChange={(event) => set("independent_cultures", event.target.value === "" ? null : Number(event.target.value))} />
        </label>
        <small>细胞数、样本数和独立培养次数不同；这里不会自动认定生物学重复。</small>
        {select("assay", ["unknown", "scRNA-seq", "snRNA-seq"])}
        {select("matrix_location", data.observed.matrix_locations, true)}
        {select("count_semantics", ["unknown", "raw_counts", "not_raw_counts"])}
        <details className="intake-extra"><summary>来源与元数据列（可后补）</summary>
          {text("source_family_id")}
          {select("sample_id_column", data.observed.obs_columns, true)}
          {select("capture_id_column", data.observed.obs_columns, true)}
          {select("gene_symbol_column", data.observed.var_columns, true)}
        </details>
        <button className="intake-primary" type="submit">核对产品资料</button>
        <small>先展示精确变更供您确认，不会立即运行分析。</small>
      </fieldset>
    </form>
  );
}
