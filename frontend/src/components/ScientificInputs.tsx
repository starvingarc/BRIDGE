import { toolName, stateName, reasonLabel, researcherText } from "../researcherLabels";
import { useEffect, useRef, useState } from "react";
import { ApiError } from "../api";
import type { ScienceCandidate, ScientificDraft } from "../types";

const roles = { target: "目标候选", acceptable_adjacent: "可接受邻近候选", known_off_target: "非目标候选", role_unresolved: "角色未确定" };
const stages = { earlier: "早于预期", within_window: "预期窗口候选", later: "晚于预期", branch_shift: "分支偏移候选", unresolved: "阶段未确定" };
const reportDomainOrder = ["target_identity", "regional_fidelity", "developmental_compatibility", "off_target_control", "proliferation_stress_response"];
const reportActions = { "P0-08": "准备缺失证据检查", "P0-09": "整理当前证据", "P0-10": "生成并核验内部报告" } as const;
export function ScientificInputs({ draft, busy, onConfirm, onRevise, onPrepareReport }: {
  draft: ScientificDraft; busy: boolean; onConfirm: () => Promise<void>;
  onRevise: (candidate: ScienceCandidate) => Promise<void>; onPrepareReport: (toolId: "P0-08" | "P0-09" | "P0-10") => Promise<void>;
}) {
  const [editedCandidate, setCandidate] = useState(draft.candidate);
  const candidate = draft.status === "pending" ? editedCandidate : draft.candidate;
  const [reviewed, setReviewed] = useState(false);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(false);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const changed = JSON.stringify(candidate) !== JSON.stringify(draft.candidate);
  const pending = draft.status === "pending";
  const disabled = busy || working;
  const perform = async (operation: () => Promise<void>) => {
    setWorking(true); setError(null);
    try { await operation(); }
    catch (cause) {
      if (mounted.current) setError(cause instanceof ApiError && cause.status === 409
        ? "草稿或来源已变化，请刷新后重新核对。" : "暂时无法保存科学草稿，请重试。");
    } finally { if (mounted.current) setWorking(false); }
  };
  const roleChange = (index: number, value: string) => {
    setReviewed(false);
    setCandidate((current) => {
      const rows = current.roles.map((row, i) => i === index ? { ...row, product_role: value as keyof typeof roles } : row);
      const targets = new Set(rows.filter((row) => ["target", "acceptable_adjacent"].includes(row.product_role)).map((row) => row.state_id));
      const numerator = current.regional_target_state_ids.filter((id) => targets.has(id));
      return { ...current, roles: rows, regional_target_state_ids: numerator,
        regional_denominator_state_ids: numerator.length ? current.regional_denominator_state_ids : [] };
    });
  };
  const sourceIds = new Set([...candidate.roles, ...candidate.development].flatMap((row) => row.source_ids));
  const sourceLimitation = (row: { state_id: string; source_ids: string[] }) => {
    const source = draft.sources.find((item) => item.state_id === row.state_id
      && row.source_ids.length === 1 && row.source_ids[0] === item.source_id);
    if (source?.decision === "evaluate") return null;
    if (source?.decision === "parent_only") return `现有依据仅支持较粗粒度的细胞类别${source.parent_state_id ? `（${source.parent_state_id}）` : ""}，不能确定该细分状态的产品角色或发育阶段。请补充该细分状态的身份依据及经审阅的产品角色／发育窗口定义；现有候选结果保留。`;
    if (source?.decision === "unavailable") return "当前来源不足以判断该状态的产品角色或发育阶段，保持未确定。请补充可追溯的状态身份依据及经审阅的产品角色／发育窗口定义；现有候选结果保留。";
    return "此草稿缺少可核对的来源限制信息，请重新整理草稿后再选择具体角色或阶段；原候选结果保留。";
  };
  const unsupportedChoice = candidate.roles.some((row) => row.product_role !== "role_unresolved" && sourceLimitation(row))
    || candidate.development.some((row) => row.stage_role !== "unresolved" && sourceLimitation(row));
  return <section className="scientific-draft" aria-label="科学输入草稿">
    <h3>科学输入草稿</h3>
    <p>{draft.status === "confirmed" ? "草稿已确认" : draft.status === "stale"
      ? "相关输入已变化，请重新整理草稿。" : draft.status === "superseded" ? "已由新草稿替代" : "待核对候选选择"}</p>
    <dl><dt>产品目标</dt><dd>{draft.facts.target_cell_type ?? "未知"}</dd>
      <dt>预期阶段</dt><dd>{draft.facts.target_stage ?? "未知"}</dd></dl>
    <fieldset disabled={disabled || !pending}><legend>候选科学选择</legend>
      {candidate.roles.length ? candidate.roles.map((row, index) => {
        const limitation = sourceLimitation(row);
        const hintId = `${draft.id}-role-${index}-hint`;
        return <div className="science-choice" key={row.state_id}>
          <label>{row.state_id} 的产品角色<select value={row.product_role} aria-describedby={limitation ? hintId : undefined}
            onChange={(event) => roleChange(index, event.target.value)}>
            {Object.entries(roles).map(([id, name]) => <option key={id} value={id} disabled={!!limitation && id !== "role_unresolved"}>{name}</option>)}
          </select></label>
          {limitation ? <p id={hintId}>{limitation}</p> : null}
          <p>{researcherText(row.rationale)}</p>
        </div>;
      }) : <p>没有足够来源支持角色建议；保持未确定。</p>}
      {candidate.development.map((row, index) => {
        const limitation = sourceLimitation(row);
        const hintId = `${draft.id}-stage-${index}-hint`;
        return <div className="science-choice" key={row.state_id}>
          <label>{row.state_id} 的发育阶段<select value={row.stage_role} aria-describedby={limitation ? hintId : undefined} onChange={(event) => {
            const value = event.target.value as keyof typeof stages; setReviewed(false);
            setCandidate((current) => ({ ...current, development: current.development.map((item, i) => i === index ? { ...item, stage_role: value } : item) }));
          }}>{Object.entries(stages).map(([id, name]) => <option key={id} value={id} disabled={!!limitation && id !== "unresolved"}>{name}</option>)}</select></label>
          {limitation ? <p id={hintId}>{limitation}</p> : null}
          <p>{researcherText(row.rationale)}</p>
        </div>;
      })}
    </fieldset>
    {candidate.regional_target_state_ids.length ? <p>区域候选分子：{candidate.regional_target_state_ids.join("、")}；分母：{candidate.regional_denominator_state_ids.join("、")}</p> : null}
    <details><summary>查看候选来源</summary>
      {draft.sources.filter((source) => sourceIds.has(source.source_id)).map((source) => <article key={source.source_id}>
        <strong>{source.state_id}</strong><p>{source.definition}</p>
        <small>{source.source_id} · {source.version} · {stateName(source.review_status)}</small>
        <p>{source.anatomy_scope}；{source.developmental_scope}</p>
        <ul>{source.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
      </article>)}
    </details>
    <h4>仍不能确认的事项</h4>
    <ul>{draft.unknowns.map((reason) => <li key={reason}>{reasonLabel(reason)}</li>)}</ul>
    <p>当前生物学声明：未确认。这里不认定独立重复，不把来源升级为已验证。</p>
    {error ? <p role="alert">{error}</p> : null}
    {pending ? <>
      {unsupportedChoice ? <p role="status">历史候选值仅保留供核对。请将受限的角色和阶段改为“未确定”，再保存新草稿；如来源信息缺失，请重新整理草稿。</p> : null}
      {changed ? <button disabled={disabled || unsupportedChoice} onClick={() => void perform(() => onRevise(candidate))}>保存选择为新草稿</button> : null}
      <label className="science-review"><input type="checkbox" checked={reviewed} disabled={disabled || changed || unsupportedChoice}
        onChange={(event) => setReviewed(event.target.checked)} />已核对候选选择和未知项；仅确认本版草稿</label>
      <button disabled={disabled || !reviewed || changed || unsupportedChoice} onClick={() => void perform(onConfirm)}>确认本版科学草稿</button>
    </> : null}
    {draft.status === "confirmed" ? <button disabled={disabled} onClick={() => void perform(() => onRevise(candidate))}>修改本版草稿</button> : null}
    <details open={draft.status === "confirmed"}><summary>后续阶段与所需条件</summary>
      {draft.stages.map((stage) => <article key={stage.tool_id}>
        <strong>{toolName(stage.tool_id)} · {stateName(stage.state)}</strong>
        <ul>{stage.reason_codes.map((reason) => <li key={reason}>{reasonLabel(reason)}</li>)}</ul>
      </article>)}
      {draft.status === "confirmed" ? (Object.keys(reportActions) as Array<keyof typeof reportActions>)
        .filter((toolId) => draft.stages.some((stage) => stage.tool_id === toolId && stage.state === "ready"))
        .map((toolId) => <button key={toolId} disabled={disabled} onClick={() => void perform(() => onPrepareReport(toolId))}>{reportActions[toolId]}</button>) : null}
    </details>
    {draft.internal_report ? <section className="internal-report" aria-label="内部研究报告">
      <h4>内部研究报告</h4>
      <p>候选规则 · 未完成生物学审阅 · 不用于产品放行</p>
      {[...draft.internal_report.sections].sort((left, right) => reportDomainOrder.indexOf(left.domain_id) - reportDomainOrder.indexOf(right.domain_id)).map((section) => <article key={section.domain_id}>
        <h5>{section.title} · 未评估</h5><p>{researcherText(section.text)}</p>
      </article>)}
      {draft.internal_report.boundaries.map((text) => <p key={researcherText(text)}>{researcherText(text)}</p>)}
      <h5>声明核验</h5>
      {draft.internal_report.verification ? <>
        <p>{stateName(draft.internal_report.verification.release_state)}</p>
        <ul>{draft.internal_report.verification.reason_codes.map((reason) => <li key={reason}>{reasonLabel(reason)}</li>)}</ul>
      </> : <p>尚未核验：请在当前核验计划中单独批准。</p>}
      <p>当前为内部研究草稿，不可公开导出。生成报告不代表科学结论成立。</p>
      <h5>接下来需要什么</h5>
      <ul>{draft.internal_report.next_actions.map((action) => <li key={researcherText(action)}>{researcherText(action)}</li>)}</ul>
    </section> : null}
    <small>确认只注册本版科学输入；运行分析和公开导出仍需分别批准。</small>
  </section>;
}
