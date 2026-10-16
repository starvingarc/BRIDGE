import { ResearchValue } from "./ResearchValue";
import { reasonLabel, displayRecord, researcherText, stateName } from "../researcherLabels";
import { useEffect, useMemo, useRef, useState } from "react";
import cytoscape, { type Core } from "cytoscape";
import type { Artifact, Session } from "../types";
import { MAX_RESEARCH_REPORT_BYTES, readBoundedText } from "./ResultsPane";
import { edgeNames, graphObjectCandidate, label, matchesRef, nodeNames, nodeRecords,
  object, resolveGraphFocus, withInterpretation, parseGraph, parseCompositionDisplay, compositionForRecord, recordMetricName, rowsFor, visibleElements, type Graph, type LoadedObject, type GraphCompositionDisplay } from "./graphData";
import "./EvidenceGraph.css";

type Version = { artifact: Artifact; graph: Graph };
const valueText = (value: unknown): string => value === null || value === undefined ? "未提供"
  : Array.isArray(value) ? value.map(valueText).join("；") || "未列出"
  : object(value) && typeof value.object_id === "string" ? value.object_id + " @ " + String(value.object_version)
  : typeof value === "object" ? JSON.stringify(displayRecord(value)) : researcherText(String(value));
const fields: Array<[string, string]> = [
  ["metric_id", "测量"], ["value", "数值"], ["numerator", "符合条件的数量"], ["denominator", "纳入统计的总数量"],
  ["unit", "单位"], ["interval", "区间"], ["evidence_state", "证据状态"],
  ["evidence_tier", "证据资格"], ["applicability", "适用性"], ["relation", "与判断的关系"],
];
export default function EvidenceGraph({ session, citation = null }: { session: Session; citation?: string | null }) {
  const [loaded, setLoaded] = useState<LoadedObject[]>([]);
  const [loading, setLoading] = useState(true);
  const [failures, setFailures] = useState(0);
  const ids = session.artifacts.filter(graphObjectCandidate).map(a => [a.id, a.access_state, a.acknowledged, a.acknowledgement_required].join(":")).join("|");
  useEffect(() => {
    const controller = new AbortController();
    let live = true;
    setLoading(true); setLoaded([]); setFailures(0);
    const artifacts = session.artifacts.filter(graphObjectCandidate);
    void (async () => {
      const result: LoadedObject[] = [];
      let errors = 0;
      for (let start = 0; start < artifacts.length; start += 4) {
        const batch = await Promise.all(artifacts.slice(start, start + 4).map(async artifact => {
          if (artifact.acknowledgement_required && !artifact.acknowledged) { errors++; return; }
          try {
            const response = await fetch(
              "/api/sessions/" + encodeURIComponent(session.id) + "/artifacts/" + encodeURIComponent(artifact.id),
              { credentials: "same-origin", signal: controller.signal });
            if (!response.ok) throw new Error("unavailable");
            // Report snapshots carry the full evidence context. Use the same
            // bounded capacity as the report reader, not the small graph limit.
            const limit = artifact.tool_id === "P0-10" ? MAX_RESEARCH_REPORT_BYTES : 2_000_000;
            const { text, truncated } = await readBoundedText(response, limit);
            if (truncated) throw new Error("truncated");
            const value: unknown = JSON.parse(text);
            if (!object(value)) throw new Error("invalid");
            if (artifact.name.startsWith("cytoscape_elements.") && !parseGraph(value)) throw new Error("invalid graph");
            return { artifact, value };
          } catch { if (!controller.signal.aborted) errors++; }
        }));
        for (const item of batch) if (item) result.push(item);
        if (controller.signal.aborted) return;
      }
      if (live) { setLoaded(result); setFailures(errors); setLoading(false); }
    })();
    return () => { live = false; controller.abort(); };
  // A new immutable artifact set triggers a new read, polling the same set does not.
  }, [session.id, ids]);
  const versions = useMemo(() => loaded.flatMap(item => {
    const graph = parseGraph(item.value);
    return graph ? [{ artifact: item.artifact, graph }] : [];
  }).sort((a, b) => a.graph.graph_id.localeCompare(b.graph.graph_id) || b.graph.graph_version - a.graph.graph_version), [loaded]);
  const [chosen, setChosen] = useState("");
  useEffect(() => { setChosen(""); }, [citation]);
  const focus = useMemo(() => citation ? resolveGraphFocus(loaded, session, citation) : null, [loaded, session, citation]);
  const version = versions.find(v => v.artifact.id === (chosen || focus?.artifactId)) ?? versions[0];
  if (loading) return <p role="status">正在读取已保存的证据关系…</p>;
  if (!version) return <section className="evidence-graph"><h2>结果依据</h2><p>尚无可读取且结构完整的结果依据。已有图表和报告仍可分别查看。</p>
    {failures > 0 && <p role="alert">部分图附件读取失败或超出显示范围；没有据此补建关系。</p>}</section>;
  const latest = !versions.some(v => v.graph.graph_id === version.graph.graph_id && v.graph.graph_version > version.graph.graph_version);
  return <section className="evidence-graph" aria-label="结果依据">
    <header><h2>这些判断依据什么？</h2>
      <p>沿着真实记录查看观察、待补证据和来源。连线表示所标注的关系，不表示因果。</p></header>
    <label>保存版本 <select value={version.artifact.id} onChange={e => setChosen(e.target.value)}>
      {versions.map(v => <option key={v.artifact.id} value={v.artifact.id}>
        结果依据 {Array.from(new Set(versions.map(item => item.graph.graph_id))).indexOf(v.graph.graph_id) + 1} · 版本 {v.graph.graph_version}
      </option>)}</select></label>
    <p className="evidence-graph-notice" role="note">
      {latest ? "最新保存版本" : "历史版本"} · 版本 {version.graph.graph_version}。保存时间顺序不代表当前证据有效；原记录状态保留，尚未核实是否被后续输入取代。
      {session.input_review_required || (session.assessment?.freshness && session.assessment.freshness.state !== "current")
        ? " 当前评估或输入另有待核对/历史状态，请勿把本图当作当前结论。" : ""}
    </p>
    {versions.some(v => v !== version && v.graph.graph_id === version.graph.graph_id && v.graph.graph_version === version.graph.graph_version)
      && <p role="alert">同一图版本有多个附件，未将它们混合；请分别核对。</p>}
    {failures > 0 && <p role="alert">{failures} 个相关附件未能读取，详情可能不完整。</p>}
    {citation && <p role="status">{focus ? (version.artifact.id === focus.artifactId ? "已定位引用的保存记录；科学状态仍以原记录为准。" : "当前查看其他保存版本，未将引用定位沿用到该版本。")
      : "未能在本评估的已登记图版本中定位该引用。可能尚未入图、版本不可用或存在歧义；请核对原始来源。"}</p>}

    <GraphView key={session.id + version.artifact.id + citation} version={version} loaded={loaded} session={session}
      initialNodeId={focus?.artifactId === version.artifact.id ? focus.nodeId : null} />
  </section>;
}

function GraphView({ version, loaded, session, initialNodeId }: { version: Version; loaded: LoadedObject[]; session: Session; initialNodeId: string | null }) {
  const baseGraph = version.graph;
  const [composition, setComposition] = useState<GraphCompositionDisplay | null>(null);
  const [compositionLoading, setCompositionLoading] = useState(true);
  const [compositionUnavailable, setCompositionUnavailable] = useState(false);
  const [compositionAttempt, setCompositionAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setComposition(null); setCompositionLoading(true); setCompositionUnavailable(false);
    void (async () => {
      try {
        const response = await fetch("/api/sessions/" + encodeURIComponent(session.id)
          + "/artifacts/" + encodeURIComponent(version.artifact.id) + "/preview",
          { credentials: "same-origin", signal: controller.signal });
        if (!response.ok) throw new Error("graph_display_unavailable");
        const { text, truncated } = await readBoundedText(response, 2_000_000);
        const parsed = truncated ? null : parseCompositionDisplay(JSON.parse(text), baseGraph);
        if (!parsed) throw new Error("graph_display_unavailable");
        if (!controller.signal.aborted) setComposition(parsed);
      } catch {
        if (!controller.signal.aborted) setCompositionUnavailable(true);
      }
      finally { if (!controller.signal.aborted) setCompositionLoading(false); }
    })();
    return () => controller.abort();
  }, [session.id, version.artifact.id, baseGraph, compositionAttempt]);
  const reports = useMemo(() => [...new Map(loaded.filter(item => item.artifact.tool_id === "P0-10"
    && item.value.object_version === "0.5.0" && item.value.graph_id === baseGraph.graph_id
    && item.value.graph_version === baseGraph.graph_version
    && item.value.graph_manifest_sha256 === composition?.graph_manifest_sha256)
    .map(item => [item.value.snapshot_sha256, item])).values()], [loaded, baseGraph, composition]);
  const [chosenReport, setChosenReport] = useState("");
  const selectedReport = reports.find(item => item.artifact.id === chosenReport) ?? (reports.length === 1 ? reports[0] : undefined);
  const graph = useMemo(() => withInterpretation(baseGraph,
    loaded.filter(item => item.artifact.tool_id !== "P0-10" || item.artifact.id === selectedReport?.artifact.id),
    composition?.graph_manifest_sha256, session), [baseGraph, loaded, composition, session, selectedReport]);
  const [selected, setSelected] = useState<string | null>(initialNodeId);
  const [expanded, setExpanded] = useState(false);
  const [query, setQuery] = useState("");
  const [canvasError, setCanvasError] = useState(false);
  const container = useRef<HTMLDivElement>(null);
  const core = useRef<Core | null>(null);
  const records = useMemo(() => rowsFor(loaded, graph, "records"), [loaded, graph]);
  const visible = useMemo(() => visibleElements(graph, selected, expanded), [graph, selected, expanded]);
  const allRequirements = useMemo(() => rowsFor(loaded, graph, "requirements"), [loaded, graph]);
  const allClaims = useMemo(() => rowsFor(loaded, graph, "claim_records"), [loaded, graph]);
  const titles = useMemo(() => {
    const names = graph.elements.nodes.map(({ data }) => label(data, records, allRequirements, allClaims, composition));
    const counts = new Map<string, number>();
    names.forEach(name => counts.set(name, (counts.get(name) ?? 0) + 1));
    return new Map(graph.elements.nodes.map(({ data }, index) => [data.id,
      counts.get(names[index])! > 1 ? names[index] + " · 记录 " + (index + 1) : names[index]]));
  }, [graph, records, allRequirements, allClaims, composition]);
  const title = (id: string) => titles.get(id) ?? "证据记录";

  const node = graph.elements.nodes.find(n => n.data.id === selected)?.data;
  const related = node ? nodeRecords(node, records) : [];
  const requirements = node ? allRequirements.filter(r =>
    (r.requirement_id === node.object_id && String(r.requirement_version) === String(node.object_version)) || matchesRef(r.claim_ref, node)) : [];
  const interpretations = node ? allClaims.filter(r =>
    r.claim_ref === node.object_id + "@" + node.object_version) : [];
  const searchResults = graph.elements.nodes.filter(n => !query.trim()
    ? visible.nodes.some(v => v.id === n.data.id)
    : (title(n.data.id) + " " + n.data.object_id).toLowerCase().includes(query.trim().toLowerCase()));
  useEffect(() => {
    if (!container.current) return;
    try {
      const cy = cytoscape({
        container: container.current, elements: [], minZoom: .15, maxZoom: 3,
        wheelSensitivity: .2, boxSelectionEnabled: false,
        style: [
          { selector: "node", style: { label: "data(displayLabel)", "font-size": 12,
            "text-wrap": "ellipsis", "text-max-width": "155px", "text-valign": "center",
            shape: "roundrectangle", width: 170, height: 46, "background-color": "#e6edf1",
            color: "#203841", "border-width": 1, "border-color": "#879fa9" } },
          { selector: 'node[node_type = "Claim"]', style: { "background-color": "#d8e9f3", "border-color": "#326b88" } },
          { selector: 'node[node_type = "EvidenceRecord"]', style: { "background-color": "#dfede8", "border-color": "#477363" } },
          { selector: 'node[node_type = "EvidenceRequirement"]', style: { "background-color": "#fff0d4", "border-color": "#a87820", shape: "diamond", height: 60 } },
          { selector: "edge", style: { width: 1.2, "line-color": "#99a6ad", "target-arrow-color": "#71848c",
            "target-arrow-shape": "triangle", "curve-style": "bezier", label: "data(displayRelation)",
            "font-size": 10, "text-background-color": "#fff", "text-background-opacity": .85,
            "text-background-padding": "2px", color: "#465861" } },
          { selector: 'edge[edge_type = "missing_for"]', style: { "line-style": "dashed", "line-color": "#a87820", "target-arrow-color": "#a87820" } },
          { selector: 'node[evidence_tier = "unverified"]', style: { "background-color": "#f1e9f7", "border-style": "dashed" } },
          { selector: ".focused", style: { "border-width": 3, "border-color": "#153f61" } },
        ],
      });
      core.current = cy;
      cy.on("tap", "node", event => { setSelected(event.target.id()); setExpanded(false); });
      const observer = new ResizeObserver(() => cy.resize());
      observer.observe(container.current);
      return () => { observer.disconnect(); cy.destroy(); core.current = null; };
    } catch { setCanvasError(true); }
  }, []);
  useEffect(() => {
    const cy = core.current;
    if (!cy) return;
    cy.batch(() => {
      cy.elements().remove();
      cy.add([
        ...visible.nodes.map(n => ({ data: { ...n, displayLabel: title(n.id) } })),
        ...visible.edges.map(e => ({ data: { ...e, displayRelation: edgeNames[e.edge_type] ?? "关联（类型待核对）" } })),
      ]);
      if (selected) cy.getElementById(selected).addClass("focused");
    });
    // Built-in layout only. Direction comes from source/target arrows, never screen position.
    cy.layout({ name: "breadthfirst", directed: true, circle: false, spacingFactor: 1.2,
      avoidOverlap: true, animate: false, padding: 28 }).run();
  }, [visible, selected, titles]);
  return <>
    {reports.length > 1 && <label>已保存的解释 <select value={selectedReport?.artifact.id ?? ""} onChange={e => setChosenReport(e.target.value)}>
      <option value="" disabled>选择解释版本</option>
      {reports.map((item, index) => <option key={item.artifact.id} value={item.artifact.id}>解释报告 {index + 1}</option>)}
    </select></label>}
    <div className="evidence-graph-controls">
      <label>查找判断或来源 <input value={query} onChange={e => setQuery(e.target.value)} placeholder="输入关键词" /></label>
      <button type="button" onClick={() => setExpanded(!expanded)}>{expanded ? "收起展开内容" : selected ? "展开相连来源" : "查看全部记录"}</button>
      <button type="button" onClick={() => { setSelected(null); setExpanded(false); setQuery(""); }}>返回概览</button>
      <button type="button" onClick={() => core.current?.zoom(Math.min(3, (core.current?.zoom() ?? 1) * 1.25))}>放大</button>
      <button type="button" onClick={() => core.current?.zoom(Math.max(.15, (core.current?.zoom() ?? 1) / 1.25))}>缩小</button>
      <button type="button" onClick={() => core.current?.fit(undefined, 28)}>缩放复位</button>
    </div>
    <p>显示 {visible.nodes.length} 条记录。
      {graph.elements.nodes.some(n => n.data.node_type === "ProposedExplanation") && " 虚线边框为模型提出的解释；支持、限制和相反关系均待验证。"}
      {graph.truncated ? " 当前仅显示部分内容，请结合报告查看完整结果。" : ""}
      {!expanded && selected ? " 已聚焦相关依据。" : ""}
    </p>
    {compositionUnavailable && <p role="status">
      解释图叠加层当前不可用，已保存的证据图仍可浏览。
      <button type="button" onClick={() => setCompositionAttempt(value => value + 1)}>重新加载解释图</button>
    </p>}
    {records.some(r => typeof r.metric_id === "string" && r.metric_id.startsWith("candidate_composition_fraction_")
      && !compositionForRecord(r, composition)) && <p role="status">{compositionLoading
        ? "正在核对候选类别来源…"
        : "部分候选组成的类别名称不可用，已保留测量记录与数值；可在来源记录详情核对原始指标。"}</p>}
    <div className="evidence-graph-workspace">
      <div>
        {canvasError ? <p role="alert">图形未能显示，请使用下方等价关系列表。</p>
          : <div ref={container} className="evidence-graph-canvas" role="img" aria-label="结果之间的关联。也可展开记录列表查看。" />}
        <details className="evidence-graph-list" open={canvasError}>
          <summary>查看记录列表</summary>
          <ul>{searchResults.map(({ data: n }) => <li key={n.id}>
            <button type="button" aria-pressed={selected === n.id} onClick={() => { setSelected(n.id); setExpanded(false); }}>
              {title(n.id)}
            </button></li>)}</ul>
          {!searchResults.length && <p>没有匹配的记录。</p>}
          {selected && <ol>{visible.edges.filter(e => e.source === selected || e.target === selected).map(e =>
            <li key={e.id}>
              {title(e.source)}
              {" → "}{edgeNames[e.edge_type] ?? "关联（类型待核对）"}{" → "}
              {title(e.target)}
              <button type="button" onClick={() => { setSelected(e.source === selected ? e.target : e.source); setExpanded(false); }}>
                查看相邻记录
              </button></li>)}</ol>}
        </details>
      </div>
      <aside aria-label="证据详情" className="evidence-graph-detail">
        {!node ? <p>选择一个判断或观察，查看它的数值、依据和来源。未列出证据不代表反证。</p> : <>
          <h3>{nodeNames[node.node_type] ?? "证据记录"}</h3><p>{title(node.id)}</p>
          <dl><dt>记录版本</dt><dd>{node.object_version}</dd>
            <dt>原记录状态</dt><dd>{node.lifecycle_state ? stateName(node.lifecycle_state) : "未提供"}；当前有效性未核实</dd>
            <dt>证据资格</dt><dd>{node.evidence_tier ? stateName(node.evidence_tier) : "未提供；不由节点连接推断"}</dd></dl>
          {node.citation && <p>精确来源引用：{node.citation}</p>}
          {graph.elements.edges.filter(e => e.data.source === node.id || e.data.target === node.id).map(({ data: e }) =>
            e.rationale ? <section key={e.id}><h4>{edgeNames[e.edge_type] ?? e.edge_type}（待验证）</h4>
              <p>{e.rationale}</p><p>适用范围：{e.applicability}</p></section> : null)}
          {related.length === 0 && <p>本项暂无可核对的测量详情。</p>}
          {related.map((r, i) => <details key={i} open={related.length === 1}><summary>观察 {i + 1} · {recordMetricName(r, composition) ?? "测量名称待核对"}</summary>
            <dl>{fields.map(([key, title]) => <div key={key}><dt>{title}</dt><dd>{key === "metric_id" && compositionForRecord(r, composition) ? recordMetricName(r, composition) : <ResearchValue value={r[key]} field={key} />}</dd></div>)}</dl>
          </details>)}
          {requirements.map((r, i) => <section key={i}><h4>待补证据</h4><p>{valueText(displayRecord(r.state, "state"))} · {valueText(displayRecord(r.requirement_key, "requirement_key"))}</p>
            <p>原因：{Array.isArray(r.reason_codes) ? r.reason_codes.map(code => reasonLabel(String(code), r.requirement_key)).join("；") : "尚未提供原因说明"}。缺失不等于反证。</p></section>)}
          {interpretations.map((r, i) => <section key={i}><h4>判断的适用范围</h4>
            <p>证据状态：{valueText(displayRecord(r.evidence_state, "evidence_state"))}；科学状态：{valueText(displayRecord(r.scientific_status, "scientific_status"))}；适用性：{valueText(displayRecord(r.applicability, "applicability"))}</p>
            <p>限制：{Array.isArray(r.reason_codes) ? r.reason_codes.map(code => reasonLabel(String(code), r.requirement_key)).join("；") : "尚未提供原因说明"}</p></section>)}
          {related.some(row => row.metric_id === "native_s_g2m_fraction") && <p>S / G2M 期标签比例不等于增殖速率。</p>}
          {related.some(row => ["consensus_supported_fraction", "source_conflict_fraction"].includes(String(row.metric_id))) &&
            <p>两个参考使用同一份查询 RNA；这些候选标签的一致或不同不构成独立验证，也不代表目标细胞纯度、生物学冲突或参考外样本判定。</p>}
          <p>同一来源的多个结果不能作为多个独立证据。候选观察不构成身份、疗效或安全性确认。</p>
        </>}
      </aside>
    </div>
  </>;
}
