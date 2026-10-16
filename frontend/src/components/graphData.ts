import { researcherText, metricName, domainNames, relationNames, fieldValue, candidateCompositionName } from "../researcherLabels";
import type { Artifact, Session } from "../types";

export type GraphNode = { id: string; label: string; node_type: string; object_id: string;
  object_version: string | number; evidence_tier?: string | null; lifecycle_state?: string | null; citation?: string };
export type GraphEdge = { id: string; source: string; target: string; edge_type: string; rationale?: string; applicability?: string; qualification?: string };
export type Graph = { graph_id: string; graph_version: number;
  elements: { nodes: Array<{ data: GraphNode }>; edges: Array<{ data: GraphEdge }> };
  truncated: boolean; omitted_node_count: number; omitted_edge_count: number };
export type ObjectRow = Record<string, unknown>;
export type LoadedObject = { artifact: Artifact; value: ObjectRow };
export const nodeNames: Record<string, string> = {
  ProposedExplanation: "候选解释（待验证）", CompetingExplanation: "竞争解释", ProposedObservation: "待检验观察", SourceCitation: "引用依据",
  Claim: "待核对判断", EvidenceRecord: "观察证据", EvidenceRequirement: "待补证据",
  MeasurementResult: "测量", MeasurementSpec: "测量方法", Artifact: "来源文件",
  ToolRun: "分析记录", EvidenceFamily: "证据来源组", ProductCase: "研究对象",
  ReconciliationRecord: "证据核对", ReconciliationSpec: "核对规则",
  EvidenceSufficiencyProfile: "证据缺口", Sample: "样本", Preparation: "制备",
  ProductDefinitionCard: "产品定义", ScoreContract: "评价规则",
  ReferenceSnapshot: "参考数据版本", PriorSnapshot: "先验证据版本", ComparisonRecord: "比较记录",
};
export const edgeNames: Record<string, string> = { ...relationNames, limits: "限制", alternative_to: "竞争解释", tests: "拟检验", cites: "引用" };
export function object(value: unknown): value is ObjectRow {
  return !!value && typeof value === "object" && !Array.isArray(value);
}
export function parseGraph(value: unknown): Graph | null {
  if (!object(value) || typeof value.graph_id !== "string" || !Number.isInteger(value.graph_version)
    || (value.graph_version as number) < 1 || !object(value.elements)
    || !Array.isArray(value.elements.nodes) || !Array.isArray(value.elements.edges)
    || typeof value.truncated !== "boolean") return null;
  const { nodes, edges } = value.elements;
  if (nodes.length > 5000 || edges.length > 20000) return null;
  const ids = new Set<string>();
  for (const row of nodes) {
    if (!object(row) || !object(row.data)) return null;
    const n = row.data;
    if (typeof n.id !== "string" || !n.id || ids.has(n.id) || typeof n.label !== "string"
      || typeof n.node_type !== "string" || typeof n.object_id !== "string"
      || !["string", "number"].includes(typeof n.object_version)
      || (n.evidence_tier != null && typeof n.evidence_tier !== "string")
      || (n.lifecycle_state != null && typeof n.lifecycle_state !== "string")) return null;
    ids.add(n.id);
  }
  const nodeIds = new Set(ids);
  for (const row of edges) {
    if (!object(row) || !object(row.data)) return null;
    const e = row.data;
    if (typeof e.id !== "string" || ids.has(e.id) || !e.id
      || typeof e.source !== "string" || typeof e.target !== "string"
      || !nodeIds.has(e.source) || !nodeIds.has(e.target)
      || typeof e.edge_type !== "string") return null;
    ids.add(e.id);
  }
  if (value.returned_node_count !== nodes.length || value.returned_edge_count !== edges.length
    || !Number.isInteger(value.omitted_node_count) || (value.omitted_node_count as number) < 0
    || !Number.isInteger(value.omitted_edge_count) || (value.omitted_edge_count as number) < 0
    || (!value.truncated && (value.omitted_node_count !== 0 || value.omitted_edge_count !== 0))) return null;
  return value as unknown as Graph;
}
export function graphArtifact(a: Artifact) {
  return a.tool_id === "P0-09" && a.access_state !== "denied" && a.content_class !== "developer_diagnostic";
}
// Names are discovery hints only; payload shape and graph identity are checked before use.
export function graphObjectCandidate(a: Artifact) {
  if (a.tool_id === "P0-10" && a.access_state !== "denied" && a.content_class !== "developer_diagnostic"
    && a.name === "research_report.json" && a.media_type === "application/json") return true;
  return graphArtifact(a) && a.media_type === "application/json"
    && /^(cytoscape_elements|evidence_records|evidence_requirements|evidence_compiler_visualization_data)\./.test(a.name);
}
export function sameVersion(value: ObjectRow, graph: Graph) {
  return value.graph_id === graph.graph_id && value.graph_version === graph.graph_version;
}
export function rowsFor(loaded: LoadedObject[], graph: Graph, key: string): ObjectRow[] {
  const candidates = loaded.filter(item => sameVersion(item.value, graph) && Array.isArray(item.value[key])
    && (key !== "records" || typeof item.value.record_set_id === "string"));
  // Ambiguous duplicates must not be silently pooled.
  return candidates.length === 1 ? (candidates[0].value[key] as unknown[]).filter(object) : [];
}
export function matchesRef(value: unknown, node: GraphNode) {
  return object(value) && value.object_id === node.object_id
    && String(value.object_version) === String(node.object_version);
}
export function nodeRecords(node: GraphNode, records: ObjectRow[]) {
  return records.filter(r => (node.node_type === "EvidenceRecord"
    && r.evidence_id === node.object_id && String(r.evidence_version) === String(node.object_version))
    || ["claim_ref", "measurement_result_ref", "measurement_spec_ref", "tool_run_ref",
      "evidence_family_ref", "product_case_ref", "sample_or_preparation_ref"].some(key => matchesRef(r[key], node))
    || (Array.isArray(r.artifact_refs) && r.artifact_refs.some(ref => matchesRef(ref, node))));
}
// Read-only metadata returned by the selected graph artifact's preview endpoint.
// The server verifies its canonical manifest/receipt and profile bytes; the UI
// checks graph identity, exact measurement versions, source registration and values.
export type GraphCompositionDisplay = {
  graph_id: string; graph_version: number; graph_manifest_sha256: string;
  composition_mapping: ObjectRow[]; sources: ObjectRow[];
};
const sha256 = (value: unknown): value is string => typeof value === "string" && /^[a-f0-9]{64}$/.test(value);
export function parseCompositionDisplay(value: unknown, graph: Graph): GraphCompositionDisplay | null {
  if (!object(value) || !sameVersion(value, graph) || !sha256(value.graph_manifest_sha256)
    || !Array.isArray(value.composition_mapping) || !value.composition_mapping.every(object)
    || !Array.isArray(value.sources) || !value.sources.every(object)) return null;
  return value as GraphCompositionDisplay;
}
export function compositionForRecord(record: ObjectRow, display: GraphCompositionDisplay | null) {
  const ref = record.measurement_result_ref;
  if (!display || !object(ref) || typeof ref.object_id !== "string"
    || typeof ref.object_version !== "string") return undefined;
  const matches = display.composition_mapping.filter(row => row.measurement_ref === ref.object_id + "@" + ref.object_version);
  if (matches.length !== 1) return undefined;
  const row = matches[0];
  const sources = display.sources.filter(source => source.source_ref === row.source_ref);
  if (sources.length !== 1 || typeof row.source_ref !== "string" || !row.source_ref
    || sources[0].schema_ref !== "bridge://schemas/cell-state-candidate-profile/v1.0"
    || !sha256(sources[0].sha256) || !sha256(sources[0].receipt_sha256)
    || typeof row.metric_id !== "string" || !/^candidate_composition_fraction_[a-f0-9]{16}$/.test(row.metric_id)
    || row.metric_id !== record.metric_id || record.unit !== "fraction"
    || row.interpretation !== "candidate_method_output_only"
    || typeof row.label !== "string" || !row.label.trim()
    || !["candidate", "unknown", "unavailable"].includes(String(row.assignment_state))
    || !Number.isSafeInteger(row.count) || (row.count as number) < 0
    || !Number.isSafeInteger(row.denominator) || (row.denominator as number) <= 0
    || (row.count as number) > (row.denominator as number)
    || typeof row.fraction !== "number" || !Number.isFinite(row.fraction)
    || Math.abs(row.fraction - (row.count as number) / (row.denominator as number)) > 1e-12
    || row.count !== record.numerator || row.denominator !== record.denominator || row.fraction !== record.value) return undefined;
  return row;
}
export function recordMetricName(record: ObjectRow, display: GraphCompositionDisplay | null = null) {
  const row = compositionForRecord(record, display);
  return row ? candidateCompositionName(row.label as string, row.assignment_state as string)
    : typeof record.metric_id === "string" ? metricName(record.metric_id) : undefined;
}
export function label(node: GraphNode, records: ObjectRow[], requirements: ObjectRow[] = [], claims: ObjectRow[] = [], composition: GraphCompositionDisplay | null = null) {
  const kind = nodeNames[node.node_type] ?? "证据记录";
  const related = nodeRecords(node, records);
  const matchingRequirements = requirements.filter(row =>
    row.requirement_id === node.object_id && String(row.requirement_version) === String(node.object_version));
  const requirement = matchingRequirements.length === 1 ? matchingRequirements[0] : undefined;
  const claimRef = node.node_type === "Claim" ? node.object_id + "@" + node.object_version
    : requirement && object(requirement.claim_ref)
      ? requirement.claim_ref.object_id + "@" + requirement.claim_ref.object_version : undefined;
  const matchingClaims = claimRef ? claims.filter(row => row.claim_ref === claimRef) : [];
  const requirementClaim = requirement && object(requirement.claim_ref) ? requirement.claim_ref : undefined;
  const measurements = requirementClaim ? records.filter(row =>
    object(row.claim_ref) && row.claim_ref.object_id === requirementClaim.object_id
      && String(row.claim_ref.object_version) === String(requirementClaim.object_version)) : related;
  const metric = measurements.length === 1 ? recordMetricName(measurements[0], composition) : undefined;
  const domains = [...new Set(measurements.map(row => row.domain_id).filter(value => typeof value === "string"))];
  // Exact graph/object versions supply domain meaning; identifiers are never parsed as biology.
  const domain = matchingClaims.length === 1 ? matchingClaims[0].domain_id
    : !matchingClaims.length && domains.length === 1 ? domains[0] : undefined;
  const domainTitle = typeof domain === "string" ? domainNames[domain] : undefined;
  if (requirement) {
    const subject = typeof requirement.requirement_key === "string" ? fieldValue(requirement.requirement_key, "requirement_key") : "要求待核对";
    return [kind, domainTitle, metric, subject].filter(Boolean).join(" · ");
  }
  if (node.node_type === "Claim" && (domainTitle || metric)) return [kind, domainTitle, metric].filter(Boolean).join(" · ");
  if (metric) return kind + " · " + metric;
  const readable = node.label !== node.object_id && node.label !== node.id
    && !/^[a-z][a-z0-9_-]*:/i.test(node.label) ? researcherText(node.label) : undefined;
  return kind + " · " + (readable || domainTitle || "名称待核对");
}
export function visibleElements(graph: Graph, selected: string | null, expanded: boolean) {
  const nodes = graph.elements.nodes.map(n => n.data);
  const edges = graph.elements.edges.map(e => e.data);
  let ids: Set<string>;
  if (selected) {
    ids = new Set([selected]);
    for (const edge of edges) if (edge.source === selected || edge.target === selected) {
      ids.add(edge.source); ids.add(edge.target);
    }
    if (expanded) { // Exact connected component; never synthesize transitive shortcut edges.
      let changed = true;
      while (changed) {
        changed = false;
        for (const edge of edges) if (ids.has(edge.source) || ids.has(edge.target)) {
          for (const id of [edge.source, edge.target]) if (!ids.has(id)) { ids.add(id); changed = true; }
        }
      }
    }
  } else {
    ids = new Set(nodes.filter(n => expanded || ["Claim", "EvidenceRecord", "EvidenceRequirement", "ProposedExplanation", "CompetingExplanation", "ProposedObservation", "SourceCitation"].includes(n.node_type)).map(n => n.id));
  }
  if (!selected) for (const edge of edges) if (edge.qualification === "unverified") {
    ids.add(edge.source); ids.add(edge.target);
  }
  return { nodes: nodes.filter(n => ids.has(n.id)), edges: edges.filter(e => ids.has(e.source) && ids.has(e.target)) };
}

export type GraphFocus = { artifactId: string; nodeId: string | null };
// Resolve navigation from checked browser provenance, never from a biological
// label. Query citations pin their original graph version; tool observations
// use only graph artifacts admitted in this assessment. Ambiguity fails closed.
export function resolveGraphFocus(loaded: LoadedObject[], session: Session, citation: string): GraphFocus | null {
  const [alias, fragment, extra] = citation.split("#");
  if (extra !== undefined) return null;
  const evidence = session.assessment?.evidence ?? [];
  const source = evidence.find(row => row.alias === alias && row.state === "available");
  if (!source) return null;
  const versions = loaded.flatMap(item => {
    const graph = parseGraph(item.value);
    return graph ? [{ artifact: item.artifact, graph }] : [];
  });
  const provenance = source.provenance ?? {};
  if (typeof provenance.graph_id === "string" && typeof provenance.graph_version === "number") {
    const matches = versions.filter(v => v.graph.graph_id === provenance.graph_id
      && v.graph.graph_version === provenance.graph_version && source.artifact_ids?.includes(v.artifact.id));
    if (matches.length !== 1) return null;
    const version = matches[0];
    if (!fragment) return { artifactId: version.artifact.id, nodeId: null };
    const match = /^record:(.+)@1$/.exec(fragment);
    const nodeId = match ? source.navigation?.graph_nodes[match[1]] : null;
    return typeof nodeId === "string" && version.graph.elements.nodes.some(n => n.data.id === nodeId)
      ? { artifactId: version.artifact.id, nodeId } : null;
  }
  let ref: unknown = source.navigation?.tool_run_ref;
  let nodeType = "ToolRun";
  let artifactRef: unknown;
  if (fragment) {
    const match = /^measurement:(.+)@1$/.exec(fragment);
    if (!match) return null;
    ref = source.navigation?.measurements[match[1]];
    artifactRef = source.navigation?.measurement_artifacts?.[match[1]];
    nodeType = "MeasurementResult";
  }
  if (!object(ref)) return null;
  const admitted = new Set(evidence.filter(row => row.state === "available" && row.tool_id === "P0-09")
    .flatMap(row => row.artifact_ids ?? []));
  const matches = versions.filter(v => admitted.has(v.artifact.id)).flatMap(version => {
    const nodes = version.graph.elements.nodes.filter(n => n.data.node_type === nodeType && matchesRef(ref, n.data));
    if (nodes.length) return nodes.length === 1 ? [{ ...version, nodeId: nodes[0].data.id }] : [];
    // Bounded exports may omit measurements. Join the exact canonical file
    // and measurement in the same complete record set before selecting it.
    if (!version.graph.truncated || nodeType !== "MeasurementResult" || !object(artifactRef)) return [];
    const files = version.graph.elements.nodes.filter(n => n.data.node_type === "Artifact"
      && matchesRef(artifactRef, n.data));
    if (files.length !== 1) return [];
    const linked = rowsFor(loaded, version.graph, "records").filter(row =>
      object(row.measurement_result_ref) && object(ref)
      && row.measurement_result_ref.object_id === ref.object_id
      && String(row.measurement_result_ref.object_version) === String(ref.object_version)
      && Array.isArray(row.artifact_refs) && row.artifact_refs.some(r => matchesRef(r, files[0].data)));
    return linked.length === 1 ? [{ ...version, nodeId: files[0].data.id }] : [];
  });
  if (new Set(matches.map(v => v.graph.graph_id)).size !== 1) return null;
  const latest = Math.max(...matches.map(v => v.graph.graph_version));
  const exact = matches.filter(v => v.graph.graph_version === latest);
  return exact.length === 1 ? { artifactId: exact[0].artifact.id, nodeId: exact[0].nodeId } : null;
}


// The registered report snapshot binds this projection to one exact graph manifest.
// Ambiguous reports are not silently combined. History stays in its report artifact.
export function withInterpretation(graph: Graph, loaded: LoadedObject[], manifestSha: string | undefined, session?: Session): Graph {
  if (!manifestSha) return graph;
  const candidates = loaded.filter(item => item.artifact.tool_id === "P0-10"
    && item.artifact.name === "research_report.json" && sameVersion(item.value, graph)
    && item.value.graph_manifest_sha256 === manifestSha && item.value.object_version === "0.5.0"
    && typeof item.value.interpretation_graph_json === "string");
  const unique = new Map(candidates.map(item => [item.value.snapshot_sha256, item]));
  if (unique.size !== 1) return graph;
  const report = [...unique.values()][0].value;
  let raw: unknown;
  try { raw = JSON.parse(report.interpretation_graph_json as string); } catch { return graph; }
  const extra = parseGraph(raw);
  if (!extra || !object(raw) || !sameVersion(raw, graph) || raw.graph_manifest_sha256 !== manifestSha
    || raw.qualification !== "unverified" || !sha256(raw.explanation_sha256)) return graph;
  const ids = new Set([...graph.elements.nodes, ...graph.elements.edges].map(row => row.data.id));
  if ([...extra.elements.nodes, ...extra.elements.edges].some(row => ids.has(row.data.id))) return graph;
  const resolved = new Map<string, string>();
  if (session) for (const { data } of extra.elements.nodes) {
    if (!data.citation) continue;
    const focus = resolveGraphFocus(loaded, session, data.citation);
    if (focus?.nodeId && graph.elements.nodes.some(n => n.data.id === focus.nodeId)
      && loaded.some(item => item.artifact.id === focus.artifactId && sameVersion(item.value, graph)))
      resolved.set(data.id, focus.nodeId);
  }
  return { ...graph, elements: { nodes: [...graph.elements.nodes, ...extra.elements.nodes.filter(n => !resolved.has(n.data.id))],
    edges: [...graph.elements.edges, ...extra.elements.edges.map(({ data }) => ({ data: { ...data,
      source: resolved.get(data.source) ?? data.source, target: resolved.get(data.target) ?? data.target } }))] } };
}
