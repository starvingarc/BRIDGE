import { useEffect, useState } from "react";
import type { Artifact, AssessmentAxis, AssessmentEvidence, Session } from "../types";
import { ArtifactCard, readBoundedText } from "./ResultsPane";
import { object } from "./graphData";
import { candidateCompositionName, researcherText, stateName, reasonText, programSourceNames } from "../researcherLabels";
import "./ResearchFigures.css";
import LinkedCellExplorer from "./spatial/LinkedCellExplorer";
import ReferenceSimilarity from "./ReferenceSimilarity";
import CompositionChart from "./spatial/CompositionChart";
import AssessmentCellExplorer from "./spatial/AssessmentCellExplorer";
import {colorFor} from "./spatial/types";

type Row = Record<string, unknown>;
const numeric = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);
const artifactUrl = (sessionId: string, id: string) => "/api/sessions/" + encodeURIComponent(sessionId) + "/artifacts/" + encodeURIComponent(id);
const safeArtifact = (a: Artifact) => a.access_state !== "denied" && a.content_class !== "developer_diagnostic"
  && (!a.acknowledgement_required || a.acknowledged);
export const figureSet = (a: Artifact) => safeArtifact(a) && a.media_type === "application/json"
  && /visualization_artifact_set\./.test(a.name);
const number = (value: unknown) => numeric(value) ? String(value) : "不可用";
const concise = (value: unknown) => numeric(value) ? new Intl.NumberFormat("zh-CN", { maximumSignificantDigits: 5 }).format(value) : "不可用";
const percent = (value: number) => new Intl.NumberFormat("zh-CN", { style: "percent", maximumFractionDigits: 3 }).format(value);
function sourceLinks(evidence: AssessmentEvidence, session: Session) {
  return session.artifacts.filter(a => safeArtifact(a) && evidence.artifact_ids?.includes(a.id));
}
function Sources({ evidence, session }: { evidence: AssessmentEvidence; session: Session }) {
  const artifacts = sourceLinks(evidence, session).filter(a => ["figure", "table"].includes(a.kind)
    && !a.media_type.includes("json"));
  return <details><summary>方法与来源</summary>
    <p>方法版本 {evidence.tool_version ?? "未提供"}</p>
    {artifacts.map((a, i) => <a key={a.id} href={artifactUrl(session.id, a.id)} download={a.name}>
      {a.kind === "figure" ? "图表" : "数据表"} {i + 1}</a>)}
  </details>;
}

type FractionRow = {label: string; fraction: number | null; count: number | null; denominator: number | null; state?: string};
// One fixed 0–100% scale; missing values have no mark. Exact counts remain inspectable.
function FractionBars({rows, label}: {rows: FractionRow[]; label: string}) {
  const ordered = [...rows].sort((a, b) => (b.fraction ?? -1) - (a.fraction ?? -1));
  return <figure className="fraction-chart" aria-label={label}>
    <div className="fraction-chart-scale" aria-hidden="true"><span>0%</span><span>50%</span><span>100%</span></div>
    <ul>{ordered.map((row, i) => <li key={i} data-state={row.state}
      title={`${row.label}: ${number(row.count)} / ${number(row.denominator)}`}>
      <div className="fraction-chart-label"><span>{row.label.replace(/^L[12]:/, "").replaceAll("_", " ")}</span>
        <strong>{numeric(row.fraction) ? percent(row.fraction) : "不可用"}</strong></div>
      <div className="fraction-chart-track" aria-hidden="true">{numeric(row.fraction)
        && <span style={{width: `${row.fraction * 100}%`}} />}</div>
    </li>)}</ul>
  </figure>;
}

// Each method owns a separate scale. Intervals show cell spread, never confidence.
function ProgramPlot({rows, label}: {rows: Row[]; label: string}) {
  const values = rows.flatMap(row => [row.mean, row.lower_quantile, row.upper_quantile].filter(numeric));
  const lo = Math.min(0, ...values), hi = Math.max(0, ...values);
  const width = hi - lo || 1;
  const x = (value: number) => 100 * (value - lo) / width;
  const names: Record<string, string> = {"PROC-S":"S 期相关", "PROC-G2M":"G2/M 期相关", "S":"S 期相关", "G2M":"G2/M 期相关",
    "PROC-ROS":"氧化应激", "PROC-HYPOXIA":"缺氧", "PROC-UPR":"未折叠蛋白反应", "PROC-APOPTOSIS":"凋亡相关", "PROC-PLURI":"多能性相关", "PROC-DISSOC":"解离 / 热休克"};
  const hasRange = rows.some(row => numeric(row.lower_quantile) && numeric(row.upper_quantile));
  return <figure className="program-chart" aria-label={label}>
    <figcaption>{hasRange ? "● 均值 · 线段 P10–P90（细胞分布）" : "● 均值"}</figcaption>
    <div className="program-chart-scale" aria-hidden="true"><span>{concise(lo)}</span><span>{concise(hi === lo ? lo + 1 : hi)}</span></div>
    <ul>{rows.map((row, i) => {
      const name = names[String(row.program_id)] ?? programSourceNames[String(row.source_gene_set)] ?? "相关基因集";
      const range = numeric(row.lower_quantile) && numeric(row.upper_quantile) && row.lower_quantile <= row.upper_quantile;
      return <li key={i}><div className="fraction-chart-label"><span>{name}</span>
        <strong title={number(row.mean)}>{numeric(row.mean) ? concise(row.mean) : stateName(String(row.assessment_state))}</strong></div>
        <div className="program-chart-track" aria-hidden="true">
          <i className="program-chart-zero" style={{left:`${x(0)}%`}} />
          {numeric(row.mean) && <>
            {range && <span className="program-chart-range" style={{left:`${x(Number(row.lower_quantile))}%`,width:`${x(Number(row.upper_quantile)) - x(Number(row.lower_quantile))}%`}} />}
            <b style={{left:`${x(row.mean)}%`}} />
          </>}
        </div>
      </li>;
    })}</ul>
  </figure>;
}
export function compositionRows(evidence: AssessmentEvidence): Row[] {
  const rows = evidence.summary?.composition;
  if (evidence.state !== "available" || evidence.summary?.analysis_scope !== "candidate_method_observation"
      || !Array.isArray(rows)) return [];
  const valid = (rows as unknown[]).filter(object).filter(row => typeof row.label === "string" && typeof row.state === "string"
    && ["candidate", "unknown", "unavailable"].includes(row.state)
    && numeric(row.fraction) && row.fraction >= 0 && row.fraction <= 1
    && Number.isSafeInteger(row.count) && Number.isSafeInteger(row.denominator)
    && Number(row.count) >= 0 && Number(row.denominator) > 0 && Number(row.count) <= Number(row.denominator));
  return valid.length === rows.length ? valid : [];
}
function Composition({ evidence, session }: { evidence: AssessmentEvidence; session: Session }) {
  const rows = compositionRows(evidence);
  if (!rows.length) return <p>当前来源没有可显示的候选组成比例。缺失没有换算为零。</p>;
  return <>
    <CompositionChart showTable={false} palette={Object.fromEntries(rows.map(row=>[String(row.label),colorFor(String(row.label))]))} rows={rows.map(row => ({
      id:String(row.label), label: (candidateCompositionName(String(row.label), String(row.state))?.replace("候选组成比例 · ", "").replace("（候选分配）", "") ?? String(row.label)).replace(/^L[12]:/, "").replaceAll("_", " "),
      fraction: row.fraction as number, count: row.count as number, denominator: row.denominator as number, state: String(row.state),
    }))} />
    <details><summary>数值与说明</summary>
    <p>候选方法输出 · 分母为所选数据视图中的细胞。标签对应尚未确立生物学身份，也不是目标纯度。</p>
    <div className="figure-table-scroll"><table className="observation-bars" aria-label="候选组成比例与完整分母">
      <thead><tr><th scope="col">来源类别与分配状态</th><th scope="col">比例（0–100%）</th><th scope="col">细胞数 / 分母</th></tr></thead>
      <tbody>{rows.map((row, i) => <tr key={i}>
        <th scope="row">{candidateCompositionName(String(row.label), String(row.state))?.replace("候选组成比例 · ", "")}</th>
        <td><span>{percent(row.fraction as number)}</span><span className="proportion-track" aria-hidden="true"><span style={{ width: `${Number(row.fraction) * 100}%` }} /></span></td>
        <td>{number(row.count)} / {number(row.denominator)}</td>
      </tr>)}</tbody></table></div>
    </details>
    <Sources evidence={evidence} session={session} />
  </>;
}

function Process({ evidence, session }: { evidence: AssessmentEvidence; session: Session }) {
  const programs = evidence.summary?.runtime_mode === "exploratory_programs";
  const profiles = sourceLinks(evidence, session).filter(a => a.tool_id === "P0-06"
    && a.media_type === "application/json" && a.name.startsWith("exploratory_process_profile."));
  const profile = profiles.length === 1 ? profiles[0] : null;
  const supplied = Array.isArray(evidence.summary?.program_summaries)
    ? (evidence.summary.program_summaries as unknown[]).filter(object) : [];
  const coverageReady = supplied.every(row => numeric(row.gene_coverage_fraction)
    && row.gene_coverage_fraction >= 0 && row.gene_coverage_fraction <= 1
    && typeof row.source_gene_set === "string" && typeof row.gene_symbols_sha256 === "string"
    && ["complete", "observed_feature_subset", "not_estimable"].includes(String(row.signature_scope))
    && [row.missing_genes, row.ambiguous_genes].every(list => Array.isArray(list) && list.every(g => typeof g === "string")));
  const rows = !programs || coverageReady ? supplied : [];
  const groups = [...new Set(rows.map(row => String(row.method_id) + "|" + String(row.score_unit)))];
  const cycle = object(evidence.summary?.cell_cycle) ? evidence.summary.cell_cycle : null;
  return <>
    <details><summary>方法与限制</summary>
    <p>探索性描述 · 同一份 RNA 来源的不同方法不构成独立验证。各方法使用自己的单位，不同单位不可横向比较，不合成总分。</p>
    {programs && <p>数值为所选 RNA 数据的基因集表达描述，不是活跃细胞或死亡比例，不能据此判定异常、产品合格性或临床安全。独立生物学重复未知；10%–90% 分位数描述细胞间分布，不是置信区间。</p>}
      <p>周期预测不等于真实分裂速率；G1 不证明静息。</p>
    </details>
    {cycle && <div className="cycle-result"><span>S / G2M · 预测比例</span>
      <strong>{numeric(cycle.s_g2m_fraction) ? percent(cycle.s_g2m_fraction) : "不可用"}</strong>
      <small>n = {number(cycle.n_observations)}</small></div>}
    {groups.map(group => { const groupRows = rows.filter(row => String(row.method_id) + "|" + String(row.score_unit) === group);
      const first = groupRows[0];
      const method = first.method_id === "PROC-SCORE-SCANPY" ? "相对背景表达" : first.method_id === "PROC-SCORE-DECOUPLER" ? "基因集关联" : "相关基因表达";
      const unit = first.score_unit === "scanpy_control_adjusted_expression" ? "表达差值" : first.score_unit === "decoupler_ulm_t_value" ? "t 值" : "单位待核对";
      return <div key={group}><h4>{method}</h4><p className="chart-meta">{unit} · 探索性 RNA 观察</p>
        <ProgramPlot rows={groupRows} label={method + "分布图"} />
        <details><summary>方法、数值与覆盖</summary>
        <p>{first.method_id === "PROC-SCORE-SCANPY" ? "Scanpy：相关基因的平均表达减去匹配背景基因的平均表达。不是实验组与对照组的差异。"
          : first.method_id === "PROC-SCORE-DECOUPLER" ? "decoupler ULM：逐细胞表达与基因集成员及其来源方向的关联，用回归 t 值表示。均值不代表群体显著性或实测通路活性。" : "方法名称见来源。"}</p>
        {first.method_id === "PROC-SCORE-DECOUPLER" && groupRows.some(row => row.direction_definition === "sign_of_source_logFC") &&
          <p>有向 ULM 按来源签名的正负方向计算可观测子集；t 值不是细胞比例，也不表示解离归因或产品质量。</p>}
        <div className="figure-table-scroll"><table aria-label={method + "数值"}><thead><tr><th scope="col">相关基因集</th><th scope="col">均值（5 位有效数字）</th>{programs && <><th scope="col">中位数 / 10%–90% 分位数</th><th scope="col">基因覆盖与来源</th></>}<th scope="col">观察细胞数</th><th scope="col">状态</th></tr></thead>
          <tbody>{groupRows.map((row, index) => <tr key={index}><th scope="row">{programSourceNames[String(row.source_gene_set)] ?? (programs ? "候选基因集（名称见来源）" : String(row.program_id))}</th><td title={number(row.mean)}>{concise(row.mean)}</td>
            {programs && <><td><span title={number(row.median)}>{concise(row.median)}</span><br />
              <span title={number(row.lower_quantile) + " / " + number(row.upper_quantile)}>{concise(row.lower_quantile)} – {concise(row.upper_quantile)}</span></td>
              <td>{number(row.observed_gene_count)} / {number(row.declared_gene_count)} 个来源成员（{percent(row.gene_coverage_fraction as number)}）
                <br />{row.signature_scope === "complete" ? "完整签名成员" : row.signature_scope === "observed_feature_subset" ? "可观测基因子集" : "无法估计"}
                <details><summary>覆盖详情与基因集来源</summary>
                  <p>基因集：{programSourceNames[String(row.source_gene_set)] ?? "来源名称未提供"}</p>
                  <p>方向定义：{row.direction_definition === "sign_of_source_logFC"
                    ? "使用来源 logFC 的正负号，不使用其效应大小作为本次测量权重。"
                    : row.direction_definition === "candidate_membership_plus_one"
                      ? "候选成员统一为 +1，不是原文拟合权重。" : "未提供"}</p>
                  <p>未匹配基因（输入中未找到，未补零）：{(row.missing_genes as string[]).join("、") || "无"}</p>
                  <p>歧义基因：{(row.ambiguous_genes as string[]).join("、") || "无"}</p>
                  <p>源文件未解析成员：{Number.isSafeInteger(row.unresolved_member_count) && Number(row.unresolved_member_count) >= 0
                    ? String(row.unresolved_member_count) : "未提供"}（未补零；保留在来源分母中）</p>
                  {profile && <a href={artifactUrl(session.id, profile.id)} download={profile.name}>下载数值与完整来源</a>}
                </details></td></>}
            <td>{number(row.n_observations)}</td><td>{stateName(String(row.assessment_state))}
              {Array.isArray(row.reason_codes) && <p>{row.reason_codes.filter((code): code is string => typeof code === "string").map(reasonText).join(" ")}</p>}
            </td></tr>)}</tbody></table></div>
        </details>
      </div>;
    })}
    {!groups.length && <p role="status">{programs
      ? "表达数值或基因覆盖详情暂不可用；请查看原始附件，缺失未补零。"
      : "当前来源未提供表达数值；缺失未画为零。"}</p>}
    <Sources evidence={evidence} session={session} />
  </>;
}


function WholeProductComposition({ summary }: { summary: Row }) {
  const rows = Array.isArray(summary.whole_product_composition)
    ? summary.whole_product_composition.filter(object) : [];
  if (!rows.length) return null; // Historical results do not contain this projection.
  const denominator = object(summary.data_view) ? summary.data_view.n_observations : null;
  if (!numeric(denominator) || !rows.every(row => numeric(row.count)
    && row.whole_product_denominator === denominator && numeric(row.whole_product_fraction))
    || rows.reduce((sum, row) => sum + Number(row.count), 0) !== denominator) {
    return <p>整批组成的计数或分母不完整，请核对原始来源；缺失未补零。</p>;
  }
  const roles = Array.isArray(summary.role_records) ? summary.role_records.filter(object) : [];
  const roleNames: Record<string, string> = {target: "目标", acceptable_adjacent: "可接受的邻近状态",
    known_off_target: "已定义的非目标", role_unresolved: "尚未判定"};
  const roleReasons: Record<string, string> = {state_identity_unresolved: "身份未确定",
    state_role_review_required: "角色定义尚待审核", source_definition_parent_only: "来源仅支持父级范围",
    source_definition_unavailable: "来源定义尚不可评估", state_role_missing: "该状态尚无角色定义",
    state_role_unresolved: "角色尚未确定", state_role_sources_required: "角色缺少来源依据"};
  const decisions = object(summary.source_definition_decisions) ? summary.source_definition_decisions : {};
  const resolutionNames: Record<string, string> = {source_conflict:"不同参考有分歧", subtype_unresolved:"细分状态仍有多种可能",
    unavailable:"未找到可用对应", not_assessed:"尚未评估"};
  const readableState = (value: unknown) => researcherText(String(value).replace(/^L[12]:/, "").replaceAll("_", " "));
  const unresolved = (row: Row) => (row.parent_state_id
    ? readableState(row.parent_state_id) + " · " : "")
    + (resolutionNames[String(row.resolution_state)] ?? "未确定部分");
  return <section aria-label="整批候选组成核算">
    <h5>整批候选组成</h5>
    <p className="chart-meta">候选分类 · {number(denominator)} 个细胞</p>
    <FractionBars label="整批候选组成图" rows={rows.map(row => ({label:row.state_id ? readableState(row.display_name ?? row.state_id)
      + (decisions[String(row.state_id)] === "parent_only" ? " · 仅父级支持，细分未定" : "") : unresolved(row),
      fraction:Number(row.whole_product_fraction),count:Number(row.count),denominator, state:row.state_id ? "candidate" : "unknown"}))} />
    <details><summary>整批数值与说明</summary>
    <p>分母为纳入分析的全部 {number(denominator)} 个细胞。父类汇总不与子类重复相加，未确定部分保留在总数中。</p>
    <p>这是辅助参考的候选对应。角色核算依据显式定义，不能验证细胞身份或发育阶段；不能与主要方法的比例相加。</p>
    <div className="figure-table-scroll"><table aria-label="整批候选组成">
      <thead><tr><th scope="col">候选类别或未确定部分</th><th scope="col">占整批比例</th>
        <th scope="col">细胞数 / 整批分母</th><th scope="col">谱系内比例（辅助）</th><th scope="col">解释范围</th>{roles.length > 0 && <th scope="col">产品角色及依据</th>}</tr></thead>
      <tbody>{rows.map(row => <tr key={String(row.record_id)}>
        <th scope="row">{row.state_id ? readableState(row.display_name ?? row.state_id) : unresolved(row)}</th>
        <td title={number(row.whole_product_fraction)}>{percent(Number(row.whole_product_fraction))}</td>
        <td>{number(row.count)} / {number(denominator)}</td>
        <td>{row.parent_state_id && numeric(row.parent_fraction) ? percent(row.parent_fraction) : "不适用"}</td>
        <td>{!row.state_id ? "身份未确定"
          : decisions[String(row.state_id)] === "parent_only" ? "仅支持父级范围；细分身份未确定"
          : decisions[String(row.state_id)] === "evaluate" ? "候选参考对应；身份仍需验证"
          : "来源定义尚不可评估；身份未确定"}</td>
        {roles.length > 0 && <td>{(() => {
          const role = roles.find(item => item.record_id === row.record_id);
          if (!role) return "尚未判定";
          return <>{roleNames[String(role.product_role)] ?? "尚未判定"}<p>{role.reason_code
            ? roleReasons[String(role.reason_code)] ?? "请核对来源"
            : "来自已审核的角色映射；候选身份仍有不确定性"}</p>
            {Array.isArray(role.source_refs) && role.source_refs.length > 0 && <details><summary>角色来源</summary>
              <p>{role.source_refs.length} 项已保存来源</p></details>}</>;
        })()}</td>}
      </tr>)}</tbody>
      <tfoot><tr><th scope="row">合计（包含未确定部分）</th><td>100%</td><td>{number(denominator)} / {number(denominator)}</td><td>不相加</td><td>不代表目标纯度</td>{roles.length > 0 && <td>未判定部分仍在分母中</td>}</tr></tfoot>
    </table></div>
    </details>
  </section>;
}


function NativeContext({ evidence, session }: { evidence: AssessmentEvidence; session: Session }) {
  const s = evidence.summary ?? {};
  const development = evidence.tool_id === "P0-04";
  const compositions = [s.primary_composition, s.auxiliary_composition]
    .flatMap(value => Array.isArray(value) ? (value as unknown[]).filter(object) : []);
  const groupKey = (row: Row) => JSON.stringify([row.channel, row.source_id, row.label_level, row.denominator_scope]);
  const groups = [...new Set(compositions.map(groupKey))];
  const markers = Array.isArray(s.marker_observations) ? (s.marker_observations as unknown[]).filter(object) : [];
  const [selectedMarker, setSelectedMarker] = useState(0);
  const marker = markers[selectedMarker] ?? markers[0];
  const genes = (value: unknown) => Array.isArray(value) ? value.map(String).join("、") || "无" : "未提供";
  return <article aria-label={development ? "发育相关描述性观察" : "整体候选组成观察"}>
    {development ? <>
      {markers.length > 0 && <>
        <label>标记组<select value={selectedMarker} onChange={event => setSelectedMarker(Number(event.target.value))}>
          {markers.map((item, i) => <option key={i} value={i}>{String(item.state_id).replace(/^L[12]:/, "").replaceAll("_", " ")}</option>)}
        </select></label>
        <p className="chart-meta">逐基因检出率 · 不代表细胞类型比例</p>
        <FractionBars label="标记基因检出率图" rows={object(marker?.gene_detection) ? Object.entries(marker.gene_detection).filter(([, value]) => object(value)).map(([gene, value]) => {
          const d = value as Row;
          const valid = numeric(d.count) && numeric(d.denominator) && d.denominator > 0 && d.count >= 0 && d.count <= d.denominator;
          const direction = Array.isArray(marker.counter_genes) && marker.counter_genes.includes(gene) ? "反向"
            : Array.isArray(marker.positive_genes) && marker.positive_genes.includes(gene) ? "正向" : "方向未提供";
          return {label:gene + " · " + direction, fraction:valid ? Number(d.count) / Number(d.denominator) : null,
            count:numeric(d.count) ? d.count : null,denominator:numeric(d.denominator) ? d.denominator : null};
        }) : []} />
      </>}
      <details><summary>发育描述与限制</summary>
      <p><strong>预期发育窗口匹配：{s.expected_window_match === null ? "尚未评估" : "请核对来源中的评估状态"}</strong>。参考对应与标记检测提供描述性背景，不能据此认定发育阶段匹配。</p>
      <p>参考系数见参考相似度与本次来源附件；逐基因检测不等于联合共表达或身份确认。父级限定保留为父级限定。</p>
      {markers.length ? markers.map((marker, i) => <details key={i}>
        <summary>{String(marker.state_id).replace(/^L[12]:/, "").replaceAll("_", " ")} · {marker.definition_decision === "parent_only" ? "仅父级范围" : marker.definition_decision === "evaluate" ? "逐基因检测" : "范围见来源"}</summary>
        <p>身份判断：{stateName(String(marker.identity_state))} · 观察细胞数 {number(marker.n_observations)}</p>
        <p>正向标记：{genes(marker.positive_genes)}；反向标记：{genes(marker.counter_genes)}</p>
        <div className="figure-table-scroll"><table aria-label={String(marker.state_id) + "逐基因检测"}>
          <thead><tr><th scope="col">基因</th><th scope="col">检测数 / 分母</th><th scope="col">状态</th></tr></thead>
          <tbody>{object(marker.gene_detection) && Object.entries(marker.gene_detection).filter(([, value]) => object(value)).map(([gene, value]) => {
            const detection = value as Row;
            return <tr key={gene}><th scope="row">{gene}</th><td>{number(detection.count)} / {number(detection.denominator)}</td><td>{stateName(String(detection.state))}</td></tr>;
          })}</tbody>
        </table></div>
        <p>标记来源：{Array.isArray(marker.source_ids) ? marker.source_ids.length + " 项已保存来源" : "未提供"}</p>
      </details>) : <p>当前摘要未提供逐基因检测详情，请查看本次来源附件。</p>}
      </details>
    </> : <>
      <p><strong>目标比例：{numeric(s.target_fraction) ? percent(s.target_fraction) + "（按审核角色映射核算）" : "尚未判定"}；非目标比例：{s.non_target_fraction === null ? "尚未判定" : "请核对来源"}</strong>。</p>
      <WholeProductComposition summary={s} />
      {(!Array.isArray(s.whole_product_composition) || !s.whole_product_composition.length) && groups.map((key, index) => {
        const rows = compositions.filter(row => groupKey(row) === key), first = rows[0];
        return <div key={key}><h5>{first.channel === "primary_celltypist_candidate" ? "主要候选方法" : "辅助参考候选"} · {String(first.label_level)} · 来源 {index + 1}</h5>
          <FractionBars label={"来源组成图 " + (index + 1)} rows={rows.map(row => ({label:String(row.label),
            fraction:numeric(row.fraction) && row.fraction >= 0 && row.fraction <= 1 ? row.fraction : null,
            count:numeric(row.count) ? row.count : null,denominator:numeric(row.denominator) ? row.denominator : null}))} /></div>;
      })}
      <details><summary>各来源组成与说明</summary>
      <p>下表是来源定义的候选标签组成。主要方法与辅助参考、不同来源和标签层级分别呈现，各组分母独立保留；不能跨组相加，也不代表目标纯度。</p>
      {groups.length ? groups.map((key, index) => {
        const rows = compositions.filter(row => groupKey(row) === key), first = rows[0];
        return <details key={key} open={index === 0}>
          <summary>{first.channel === "primary_celltypist_candidate" ? "主要候选方法" : "辅助参考候选"} · {String(first.label_level)} · 来源 {index + 1}</summary>
          <p>分母范围：{first.denominator_scope === "selected_data_view" ? "所选数据视图中的细胞" : first.denominator_scope === "all input observations" ? "全部输入细胞" : "来源定义的观察范围（详见附件）"}。产品角色判断：{stateName(String(s.role_judgement_state))}。</p>
          <div className="figure-table-scroll"><table aria-label={"候选来源组成 " + (index + 1)}>
            <thead><tr><th scope="col">来源标签</th><th scope="col">比例</th><th scope="col">细胞数 / 分母</th></tr></thead>
            <tbody>{rows.map((row, i) => <tr key={i}><th scope="row">{String(row.label)}</th>
              <td title={number(row.fraction)}>{numeric(row.fraction) ? percent(row.fraction) : "不可用"}</td>
              <td>{number(row.count)} / {number(row.denominator)}</td></tr>)}</tbody>
          </table></div>
        </details>;
      }) : <p>当前摘要未提供来源组成详情，请查看本次来源附件。</p>}
      </details>
    </>}
    <details><summary>适用范围</summary><p>同一份 RNA 来源，不构成独立验证；已有描述性结果不表示产品域评估完成。</p></details>
    <Sources evidence={evidence} session={session} />
  </article>;
}

type BoundFigure = { contract: Row; renders: Artifact[]; table: Artifact; data: Artifact };
function parseFigures(value: unknown): BoundFigure[] | null {
  if (!object(value) || value.kind !== "typed_figures" || !Array.isArray(value.figures)) return null;
  if (!value.figures.every(row => object(row) && object(row.contract) && Array.isArray(row.renders)
    && row.renders.every(a => object(a) && typeof a.id === "string") && object(row.table) && typeof row.table.id === "string"
    && object(row.data) && typeof row.data.id === "string")) return null;
  return value.figures as BoundFigure[];
}
const titles: Record<string, string> = {
  "bridge.expression.umap": "细胞表达谱分布",
  "bridge.expression.markers": "细胞群标志基因",
  "bridge.expression.differential-expression": "细胞类型内差异表达",
  "bridge.qc.readiness-flow": "细胞筛选概况", "bridge.qc.overview": "采集单元质控分布",
  "bridge.qc.counts_genes": "计数与基因数", "bridge.qc.flag-intersections": "质控标记重叠",
};
function BoundFigureView({ figure, session }: { figure: BoundFigure; session: Session }) {
  const c = figure.contract;
  const a = object(c.accessibility) ? c.accessibility : {};
  // The server resolves exact receipt/hash bindings; never pair same-named files.
  const render = figure.renders.find(r => r.media_type === "image/svg+xml") ?? figure.renders.find(r => r.media_type === "image/png");
  const [failed, setFailed] = useState(false);
  const [table, setTable] = useState(false);
  const title = titles[String(c.component_id)] ?? researcherText(String(c.insight_title));
  const picture = render && !failed ? <a href={artifactUrl(session.id, render.id)} target="_blank" rel="noreferrer" aria-label={"打开原尺寸图：“" + title + "”"}>
      <img loading="lazy" src={artifactUrl(session.id, render.id)} alt={String(a.alt_text ?? title)} onError={() => setFailed(true)} /></a>
      : <p role="status">图像暂不可用，请查看同一来源的数据表。</p>;
  return <article className="bound-figure">
    <h4>{title}</h4>
    {c.component_id === "bridge.expression.umap" && <LinkedCellExplorer sessionId={session.id} umapArtifactId={figure.data.id} />}
    {c.component_id === "bridge.expression.umap" ? <details><summary>静态图预览</summary>{picture}</details> : picture}
    <details><summary>图表说明与限制</summary>
      <p>{stateName(String(c.scientific_status))} · {String(c.denominator_label ?? "分母见数据表")} · {String(c.unit ?? "单位见数据表")}</p>
      <p>{researcherText(String(c.takeaway))}</p><p>{String(a.long_description ?? "详见原始数据")}</p>
      {Array.isArray(c.limitations) && <ul>{c.limitations.map((text, i) => <li key={i}>{researcherText(String(text))}</li>)}</ul>}
      {Array.isArray(c.missing_reason_codes) && c.missing_reason_codes.length > 0 && <p>{c.missing_reason_codes.map(code => reasonText(String(code))).join("；")}</p>}
    </details>
    <details><summary>数据与下载</summary>
    <button type="button" aria-expanded={table} onClick={() => setTable(!table)}>{table ? "收起同源数据表" : "查看同源数据表"}</button>
    <a href={artifactUrl(session.id, figure.table.id)} download={figure.table.name}>下载完整表格</a>
    {figure.renders.map(r => <a key={r.id} href={artifactUrl(session.id, r.id)} download={r.name}>
      下载 {r.media_type === "application/pdf" ? "PDF" : r.media_type === "image/png" ? "PNG" : "SVG"}</a>)}
    {table && <ArtifactCard sessionId={session.id} artifact={figure.table} />}
    </details>
  </article>;
}
export function TypedFigures({ session }: { session: Session }) {
  const sets = session.artifacts.filter(figureSet);
  const [chosen, setChosen] = useState("");
  const selected = sets.find(a => a.id === chosen) ?? sets.at(-1);
  const [state, setState] = useState<{ id: string; figures: BoundFigure[] | null; loading: boolean }>({ id: "", figures: null, loading: false });
  useEffect(() => {
    const controller = new AbortController();
    if (!selected) return;
    setState({ id: selected.id, figures: null, loading: true });
    void (async () => {
      let figures = null;
      try {
        const response = await fetch(artifactUrl(session.id, selected.id) + "/preview", { credentials: "same-origin", signal: controller.signal });
        if (response.ok) { const result = await readBoundedText(response, 2_000_000); if (!result.truncated) figures = parseFigures(JSON.parse(result.text)); }
      } catch { /* Original files remain reachable. */ }
      if (!controller.signal.aborted) setState({ id: selected.id, figures, loading: false });
    })();
    return () => controller.abort();
  }, [session.id, selected?.id]);
  if (!selected) return <p>完成分析后，图表会显示在这里。</p>;
  return <>
    {sets.length > 1 && <label>图表集合 <select value={selected.id} onChange={event => setChosen(event.target.value)}>
      {sets.map((a, index) => <option value={a.id} key={a.id}>{a.name.startsWith("expression_") ? "表达探索 " + (index + 1) : "图表集合 " + (index + 1) + " · " + researcherText(a.name)}</option>)}
    </select></label>}
    {state.id !== selected.id || state.loading ? <p role="status">正在加载图表…</p>
      : state.figures ? state.figures.map(figure => <BoundFigureView key={selected.id + ":" + String(figure.contract.visualization_id)} figure={figure} session={session} />)
      : <p role="status">图表加载待恢复，可先查看原始附件。</p>}
  </>;
}

// The assessment projection is already scope-verified by the server. Never infer
// a binding from a tool/name match in the session-wide artifact history.
export function scopedFigureSession(session: Session, axes?: AssessmentAxis[]): Session {
  const aliases = axes && new Set(axes.flatMap(axis => [axis, ...(axis.families ?? [])])
    .flatMap(axis => [...axis.evidence_aliases, ...(axis.context_evidence_aliases ?? [])])
    .map(alias => alias.split("#")[0]));
  const evidence = (session.assessment?.evidence ?? []).filter(e => e.state === "available" && (!aliases || aliases.has(e.alias)));
  const ids = new Set(evidence.flatMap(e => [...(e.artifact_ids ?? []),
    ...(e.dependencies ?? []).flatMap(dependency => dependency.artifact_ids)]));
  return {...session, artifacts: session.artifacts.filter(a => ids.has(a.id) && safeArtifact(a)),
    assessment: session.assessment ? {...session.assessment, evidence, portrait: axes ?? session.assessment.portrait} : null};
}

export default function ResearchFigures({ session: source, axes }: { session: Session; axes?: AssessmentAxis[] }) {
  const session = scopedFigureSession(source, axes);
  const evidence = session.assessment?.evidence ?? [];
  const includes = (...ids: string[]) => !axes || axes.some(axis => ids.includes(axis.id));
  const compositions = evidence.filter(e => e.tool_id === "P0-02" && compositionRows(e).length);
  const contexts = evidence.filter(e => ["P0-03", "P0-04", "P0-05"].includes(e.tool_id) && e.state === "available"
    && e.summary?.runtime_mode === "saved_cell_state_context");
  const processes = evidence.filter(e => e.tool_id === "P0-06" && e.state === "available" && ["exploratory_process", "exploratory_programs"].includes(String(e.summary?.runtime_mode)));
  return <div className="research-figures">
    {!axes && session.assessment?.question && <p><strong>本次研究问题：</strong>{researcherText(session.assessment.question)}</p>}
    {session.assessment?.freshness.state !== "current" && <p role="status">{session.assessment?.freshness.state === "review_pending" ? "资料待核对" : "历史结果"}</p>}
    {includes("cell_state") && <section aria-label="候选组成">
      {compositions.length ? compositions.map(e => <AssessmentCellExplorer key={session.id+session.assessment!.scope_digest+e.alias} sessionId={session.id} scopeDigest={session.assessment!.scope_digest} evidenceAlias={e.alias} fallback={<Composition evidence={e} session={session} />} />) : <p>当前评估未提供可核验的候选组成。缺失不表示比例为零。</p>}
    </section>}
    {includes("target_identity", "regional_identity", "development", "composition") && <section aria-label="参考与产品域"><h3>参考对应</h3>
      {includes("target_identity", "regional_identity") && <>
      <p className="chart-meta">RNA 相似度 · 描述性</p>
      <ReferenceSimilarity session={session} />
      </>}
      {contexts.map(e => <NativeContext key={e.alias} evidence={e} session={session} />)}
      <details><summary>评估范围与限制</summary>
      {session.assessment?.portrait.filter(axis => ["target_identity", "regional_identity", "development", "composition"].includes(axis.id)).map(axis =>
        <p key={axis.id}><strong>{axis.title}：</strong>{stateName(axis.state)} · {axis.reason_codes.map(reasonText).join("；") || "详见评估概览中的来源"}</p>)}
      </details>
    </section>}
    {includes("process") && <section aria-label="增殖与应激观察"><h3>增殖与应激</h3>
      {processes.length ? processes.map(e => <Process key={e.alias} evidence={e} session={session} />) : <p>当前评估没有可读取的探索性程序数值。请核对分析资格与所需资源。</p>}
      {!axes && <details><summary>各项状态</summary>{session.assessment?.portrait.find(axis => axis.id === "process")?.families?.map(family => <p key={family.id}>
        <strong>{family.title}：</strong>{stateName(family.state)} · {family.reason_codes.map(reasonText).join("；") || "详见来源"}</p>)}</details>}
    </section>}
    {(!axes || session.artifacts.some(figureSet)) && <section aria-label="已有工具图表"><h3>分析图表</h3><TypedFigures session={session} /></section>}
  </div>;
}
