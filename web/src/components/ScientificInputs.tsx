import { useEffect, useRef, useState } from "react";
import { ApiError } from "../api";
import type { ScienceCandidate, ScientificDraft } from "../types";

const roles = { target: "目标候选", acceptable_adjacent: "可接受邻近候选", known_off_target: "非目标候选", role_unresolved: "角色未确定" };
const stages = { earlier: "早于预期", within_window: "预期窗口候选", later: "晚于预期", branch_shift: "分支偏移候选", unresolved: "阶段未确定" };
export const scientificGap: Record<string, string> = {
  independence_unknown: "尚未确认生物学独立性",
  biological_unit_relationships_unconfirmed: "样本、制备和独立分组关系尚未完成确认",
  scientific_source_review_pending: "来源仍待生物学审阅；草稿确认不会解除此限制",
  reference_configuration_unavailable: "所需参考配置暂不可用",
  regional_definition_unresolved: "目标区域的分子与分母定义仍待确认",
  developmental_window_unresolved: "预期发育窗口仍待确认",
  comparison_inputs_not_bound: "尚未绑定采用一致产品定义、测量规则和比较条件的另一产品或批次",
  canonical_missingness_result_required: "请先完成本版样本的缺失证据检查",
  candidate_missingness_policy: "使用候选、未审阅规则整理缺失要求，不生成测量或产品判定",
  internal_draft_only: "仅供内部研究核对，核验结果不会自动允许公开导出",
  scientific_draft_confirmation_required: "请先确认当前科学草稿",
  report_policy_not_configured: "报告的证据归组与声明判定规则尚未配置",
  compiled_report_required: "尚未生成带证据绑定的报告草稿",
  verified_report_and_export_approval_required: "需要已核验的报告及单独的导出批准",
  missingness_only: "仅检查缺失证据，不是产品合格判定",
  result_evidence_invalid: "结果证据校验失败，暂不可使用",
};
const stageNames: Record<string, string> = { "P0-03": "目标身份与区域", "P0-04": "发育阶段", "P0-05": "非目标细胞", "P0-06": "增殖与应激", "P0-07": "产品比较", "P0-08": "证据充分性", "P0-09": "报告证据归组", "P0-10": "报告声明核验", "P0-11": "报告导出" };
const reportDomainOrder = ["target_identity", "regional_fidelity", "developmental_compatibility", "off_target_control", "proliferation_stress_response"];
const reportActions = { "P0-08": "准备缺失证据检查", "P0-09": "整理当前证据", "P0-10": "生成并核验内部报告" } as const;
const verificationStates: Record<string, string> = { release_blocked: "发布受阻", review_required: "仍需审阅", verified: "核验通过", verified_with_warnings: "带警告通过核验", not_assessed: "尚未核验" };
const verificationReasons: Record<string, string> = {
  claim_type_policy_missing: "当前声明规则尚未支持缺失性表述",
  unapproved_renderer_requires_review: "当前报告呈现方式尚未获得发布批准",
};
const stageStates: Record<string, string> = { blocked: "尚不可运行", ready: "可准备计划", available: "已有工具结果" };
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
  return <section className="scientific-draft" aria-label="科学输入草稿">
    <h3>科学输入草稿</h3>
    <p>{draft.status === "confirmed" ? "草稿已确认" : draft.status === "stale"
      ? "相关输入已变化，请重新整理草稿。" : draft.status === "superseded" ? "已由新草稿替代" : "待核对候选选择"}</p>
    <dl><dt>产品目标</dt><dd>{draft.facts.target_cell_type ?? "未知"}</dd>
      <dt>预期阶段</dt><dd>{draft.facts.target_stage ?? "未知"}</dd></dl>
    <fieldset disabled={disabled || !pending}><legend>候选科学选择</legend>
      {candidate.roles.length ? candidate.roles.map((row, index) => <div className="science-choice" key={row.state_id}>
        <label>{row.state_id} 的产品角色<select value={row.product_role}
          onChange={(event) => roleChange(index, event.target.value)}>
          {Object.entries(roles).map(([id, name]) => <option key={id} value={id}>{name}</option>)}
        </select></label><p>{row.rationale}</p>
      </div>) : <p>没有足够来源支持角色建议；保持未确定。</p>}
      {candidate.development.map((row, index) => <div className="science-choice" key={row.state_id}>
        <label>{row.state_id} 的发育阶段<select value={row.stage_role} onChange={(event) => {
          const value = event.target.value as keyof typeof stages; setReviewed(false);
          setCandidate((current) => ({ ...current, development: current.development.map((item, i) => i === index ? { ...item, stage_role: value } : item) }));
        }}>{Object.entries(stages).map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></label>
        <p>{row.rationale}</p>
      </div>)}
    </fieldset>
    {candidate.regional_target_state_ids.length ? <p>区域候选分子：{candidate.regional_target_state_ids.join("、")}；分母：{candidate.regional_denominator_state_ids.join("、")}</p> : null}
    <details><summary>查看候选来源</summary>
      {draft.sources.filter((source) => sourceIds.has(source.source_id)).map((source) => <article key={source.source_id}>
        <strong>{source.state_id}</strong><p>{source.definition}</p>
        <small>{source.source_id} · {source.version} · {source.review_status}</small>
        <p>{source.anatomy_scope}；{source.developmental_scope}</p>
        <ul>{source.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
      </article>)}
    </details>
    <h4>仍不能确认的事项</h4>
    <ul>{draft.unknowns.map((reason) => <li key={reason}>{scientificGap[reason] ?? reason}</li>)}</ul>
    <p>当前生物学声明：未确认。这里不认定独立重复，不把来源升级为已验证。</p>
    {error ? <p role="alert">{error}</p> : null}
    {pending ? <>
      {changed ? <button disabled={disabled} onClick={() => void perform(() => onRevise(candidate))}>保存选择为新草稿</button> : null}
      <label className="science-review"><input type="checkbox" checked={reviewed} disabled={disabled || changed}
        onChange={(event) => setReviewed(event.target.checked)} />已核对候选选择和未知项；仅确认本版草稿</label>
      <button disabled={disabled || !reviewed || changed} onClick={() => void perform(onConfirm)}>确认本版科学草稿</button>
    </> : null}
    {draft.status === "confirmed" ? <button disabled={disabled} onClick={() => void perform(() => onRevise(candidate))}>修改本版草稿</button> : null}
    <details open={draft.status === "confirmed"}><summary>后续阶段与所需条件</summary>
      {draft.stages.map((stage) => <article key={stage.tool_id}>
        <strong>{stageNames[stage.tool_id] ?? stage.tool_id} · {stageStates[stage.state] ?? stage.state}</strong>
        <ul>{stage.reason_codes.map((reason) => <li key={reason}>{scientificGap[reason] ?? reason}</li>)}</ul>
      </article>)}
      {draft.status === "confirmed" ? (Object.keys(reportActions) as Array<keyof typeof reportActions>)
        .filter((toolId) => draft.stages.some((stage) => stage.tool_id === toolId && stage.state === "ready"))
        .map((toolId) => <button key={toolId} disabled={disabled} onClick={() => void perform(() => onPrepareReport(toolId))}>{reportActions[toolId]}</button>) : null}
    </details>
    {draft.internal_report ? <section className="internal-report" aria-label="内部研究报告">
      <h4>内部研究报告</h4>
      <p>候选规则 · 未完成生物学审阅 · 不用于产品放行</p>
      {[...draft.internal_report.sections].sort((left, right) => reportDomainOrder.indexOf(left.domain_id) - reportDomainOrder.indexOf(right.domain_id)).map((section) => <article key={section.domain_id}>
        <h5>{section.title} · 未评估</h5><p>{section.text}</p>
      </article>)}
      {draft.internal_report.boundaries.map((text) => <p key={text}>{text}</p>)}
      <h5>声明核验</h5>
      {draft.internal_report.verification ? <>
        <p>{verificationStates[draft.internal_report.verification.release_state] ?? draft.internal_report.verification.release_state}</p>
        <ul>{draft.internal_report.verification.reason_codes.map((reason) => <li key={reason}>{verificationReasons[reason] ?? reason}</li>)}</ul>
      </> : <p>尚未核验：请在当前核验计划中单独批准。</p>}
      <p>当前为内部研究草稿，不可公开导出。生成报告不代表科学结论成立。</p>
      <h5>接下来需要什么</h5>
      <ul>{draft.internal_report.next_actions.map((action) => <li key={action}>{action}</li>)}</ul>
    </section> : null}
    <small>确认只注册本版科学输入；运行分析和公开导出仍需分别批准。</small>
  </section>;
}
