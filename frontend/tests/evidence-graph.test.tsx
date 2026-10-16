import { act, fireEvent, render, screen, within } from "@testing-library/react";
import EvidenceGraph from "../src/components/EvidenceGraph";
import { ResultsPane } from "../src/components/ResultsPane";
import { withInterpretation, label, nodeRecords, resolveGraphFocus, parseGraph, rowsFor, visibleElements, parseCompositionDisplay, compositionForRecord, recordMetricName } from "../src/components/graphData";
import type { Artifact, Session, AssessmentEvidence } from "../src/types";

// Canvas availability must not gate keyboard access to evidence.
vi.mock("cytoscape", () => ({ default: () => { throw new Error("no canvas"); } }));
const artifact = (id: string, name: string): Artifact => ({
  id, name, kind: "evidence", tool_id: "P0-09", media_type: "application/json", url: "/ignored",
});
const node = (id: string, node_type: string) => ({ data: {
  id, node_type, object_id: id, object_version: "1", label: id, lifecycle_state: "active",
} });
const edge = (id: string, source: string, target: string, edge_type: string) => ({ data: { id, source, target, edge_type } });
const graph = {
  graph_id: "case-graph", graph_version: 2, truncated: false, omitted_node_count: 0, omitted_edge_count: 0,
  returned_node_count: 4, returned_edge_count: 3,
  elements: { nodes: [node("claim", "Claim"), node("observation", "EvidenceRecord"), node("method", "MeasurementSpec"), node("gap", "EvidenceRequirement")],
    edges: [edge("support", "observation", "claim", "supports"), edge("source", "observation", "method", "derived_from"), edge("missing", "gap", "claim", "missing_for")] },
};
const record = { evidence_id: "observation", evidence_version: "1", metric_id: "observed_fraction", value: 0,
  denominator: null, unit: "fraction", evidence_tier: "candidate", claim_ref: { object_id: "claim", object_version: "1" } };
const records = { graph_id: graph.graph_id, graph_version: 2, record_set_id: "set-2", records: [record] };
const graphArtifact = artifact("graph2", "cytoscape_elements.json");
const recordsArtifact = artifact("records2", "evidence_records.json");
const historical = artifact("graph1", "cytoscape_elements.json");
const session: Session = {
  id: "case", title: "Case", updated_at: "", status: "idle", messages: [], uploads: [], plan: null,
  error: null, input_review_required: false, pending_input_change: null, artifacts: [graphArtifact, recordsArtifact, historical],
};
function mockArtifacts() {
  const payloads: Record<string, unknown> = {
    graph2: graph, graph1: { ...graph, graph_version: 1 }, records2: records,
  };
  return vi.spyOn(globalThis, "fetch").mockImplementation(async input =>
    new Response(JSON.stringify(payloads[String(input).split("/").pop()!])));
}
describe("evidence graph semantics", () => {
  it("rejects incomplete exports and dangling links instead of filling relationships", () => {
    expect(parseGraph(graph)).not.toBeNull();
    expect(parseGraph({ ...graph, returned_edge_count: 4 })).toBeNull();
    expect(parseGraph({ ...graph, elements: { ...graph.elements, edges: [edge("bad", "claim", "unknown", "supports")] } })).toBeNull();
    expect(parseGraph({ ...graph, omitted_node_count: 1 })).toBeNull();
  });
  it("preserves original direction and hides technical nodes without shortcut edges", () => {
    const parsed = parseGraph(graph)!;
    const overview = visibleElements(parsed, null, false);
    expect(overview.nodes.map(n => n.id)).toEqual(["claim", "observation", "gap"]);
    expect(overview.edges.map(e => e.id)).toEqual(["support", "missing"]);
    const selected = visibleElements(parsed, "claim", false);
    expect(selected.edges[0]).toEqual(graph.elements.edges[0].data);
    expect(visibleElements(parsed, "claim", true).edges).toEqual(graph.elements.edges.map(e => e.data));
  });
  it("binds detail rows by graph and object versions, refusing ambiguous duplicates", () => {
    const parsed = parseGraph(graph)!;
    const loaded = [{ artifact: recordsArtifact, value: records }];
    expect(rowsFor(loaded, parsed, "records")).toEqual([record]);
    expect(rowsFor(loaded, { ...parsed, graph_version: 1 }, "records")).toEqual([]);
    expect(rowsFor([...loaded, ...loaded], parsed, "records")).toEqual([]);
    expect(nodeRecords(graph.elements.nodes[0].data, [record])).toEqual([record]);
    expect(nodeRecords({ ...graph.elements.nodes[0].data, object_version: "2" }, [record])).toEqual([]);
    const domainNode = { ...graph.elements.nodes[0].data, object_id:"claim:native-domain-hash:developmental_compatibility", label:"claim:native-domain-hash:developmental_compatibility" };
    expect(label(domainNode, [], [], [{claim_ref:domainNode.object_id+"@2",domain_id:"developmental_compatibility"}])).toBe("待核对判断 · 名称待核对");
    expect(label(domainNode, [], [], [{claim_ref:domainNode.object_id+"@1",domain_id:"developmental_compatibility"}])).toBe("待核对判断 · 发育阶段相容性");

  });
});
describe("evidence graph entry", () => {
  it("supports keyboard/list selection, missing versus zero, search, and version reset without canvas", async () => {
    const fetch = mockArtifacts();
    render(<EvidenceGraph session={session} />);
    expect(await screen.findByRole("heading", { name: "这些判断依据什么？" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "观察证据 · 名称待核对" }));
    expect(screen.getByText("0", { selector: "dd" })).toBeInTheDocument();
    expect(screen.getByText("纳入统计的总数量").nextElementSibling).toHaveTextContent("未提供");
    expect(screen.getByText("候选", { selector: "dd" })).toBeInTheDocument();
    expect(screen.getByText(/图形未能显示/)).toBeInTheDocument();
    fireEvent.change(screen.getByRole("textbox", { name: "查找判断或来源" }), { target: { value: "method" } });
    expect(screen.getByRole("button", { name: "测量方法 · 名称待核对" })).toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox", { name: "保存版本" }), { target: { value: "graph1" } });
    expect(screen.getByText(/历史版本 · 版本 1/)).toBeInTheDocument();
    expect(screen.queryByText("0", { selector: "dd" })).not.toBeInTheDocument();
    expect(screen.getByRole("textbox")).toHaveValue("");
    expect(fetch.mock.calls.every(([url]) => String(url).startsWith("/api/sessions/case/artifacts/"))).toBe(true);
  });
  it("distinguishes measurement gaps from missing independent validation and keeps source IDs out of ordinary details", async () => {
    const taggedClaim = { ...graph.elements.nodes[0].data, object_id: "claim:P0-04:test", label: "发育阶段", node_type: "UnrecognizedInternalType" };
    const taggedGraph = { ...graph, elements: { ...graph.elements, nodes: [{ data: taggedClaim }, ...graph.elements.nodes.slice(1)] } };
    const requirementFile = artifact("requirements", "evidence_requirements.json");
    const compilerFile = artifact("compiler", "evidence_compiler_visualization_data.json");
    const payloads: Record<string, unknown> = {
      graph2: taggedGraph,
      records2: { ...records, records: [{ ...record, applicability: "not_applicable", claim_ref: { object_id: taggedClaim.object_id, object_version: "1" } }] },
      requirements: { graph_id: graph.graph_id, graph_version: 2, requirements: [
        { requirement_id: "one", requirement_version: "1", claim_ref: { object_id: taggedClaim.object_id, object_version: "1" }, state: "open", requirement_key: "independent_validation", reason_codes: ["required_channel_not_provided"] },
        { requirement_id: "two", requirement_version: "1", claim_ref: { object_id: taggedClaim.object_id, object_version: "1" }, state: "open", requirement_key: "canonical_measurement", reason_codes: ["measurement_not_provided"] },
        { requirement_id: "three", requirement_version: "1", claim_ref: { object_id: taggedClaim.object_id, object_version: "1" }, state: "open", requirement_key: "canonical_measurement", reason_codes: ["measurement_unavailable"] },
      ] },
      compiler: { graph_id: graph.graph_id, graph_version: 2, claim_records: [{ claim_ref: taggedClaim.object_id + "@1", evidence_state: "measured", scientific_status: "shadow", applicability: "not_applicable", reason_codes: [] }] },
    };
    const original = JSON.stringify(payloads);
    vi.spyOn(globalThis, "fetch").mockImplementation(async input => new Response(JSON.stringify(payloads[String(input).split("/").pop()!])));
    render(<EvidenceGraph session={{ ...session, artifacts: [graphArtifact, recordsArtifact, requirementFile, compilerFile] }} />);
    await screen.findByRole("heading", { name: "这些判断依据什么？" });
    fireEvent.click(screen.getByRole("button", { name: "查看全部记录" }));
    fireEvent.click(screen.getByRole("button", { name: "证据记录 · 发育阶段" }));
    const detail = within(screen.getByRole("complementary", { name: "证据详情" }));
    expect(detail.getByRole("heading", { name: "证据记录" })).toBeInTheDocument();
    expect(detail.getByText(/已有观察，但尚缺独立验证/)).toBeInTheDocument();
    expect(detail.getByText(/尚未执行或提供此域测量/)).toBeInTheDocument();
    expect(detail.getByText(/测量当前不可用/)).toBeInTheDocument();
    expect(detail.getByText("待补证据 · 独立验证")).toBeInTheDocument();
    expect(detail.getByText("适用性").nextElementSibling).toHaveTextContent("不适用");
    expect(detail.getByText(/适用性：不适用/)).toBeInTheDocument();
    expect(detail.queryByText(/UnrecognizedInternalType|independent_validation|not_applicable|measurement_not_provided|required_channel_not_provided|measurement_unavailable|P0-04/)).not.toBeInTheDocument();
    expect(JSON.stringify(payloads)).toBe(original);
  });
  it("explains an unavailable graph without exposing raw internal attachments", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}"));
    render(<EvidenceGraph session={session} />);
    expect(await screen.findByText(/尚无可读取且结构完整/)).toBeInTheDocument();
    expect(screen.queryByText("全部证据图附件（按需查看）")).not.toBeInTheDocument();
    expect(screen.queryByText("cytoscape_elements.json")).not.toBeInTheDocument();
  });
  it("groups graph files under one lazy entry while retaining independent figures", async () => {
    const fetch = mockArtifacts();
    const independent: Artifact = { ...artifact("qc", "QC.svg"), kind: "figure", media_type: "image/svg+xml", tool_id: "P0-01" };
    render(<ResultsPane session={{ ...session, artifacts: [...session.artifacts, independent] }} />);
    expect(screen.getAllByRole("tab", { name: "结果依据" })).toHaveLength(1);
    expect(screen.queryByAltText("QC.svg")).not.toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText("全部原始图像附件（独立查看）"));
    expect(await screen.findByAltText("QC.svg")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: /下载/ }));
    expect(screen.queryByText("cytoscape_elements.json")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "结果依据" }));
    expect(await screen.findByRole("heading", { name: "这些判断依据什么？" })).toBeInTheDocument();
  });
  it("returns to the staged input review without losing the evidence graph entry", async () => {
    mockArtifacts();
    render(<ResultsPane session={{ ...session, input_review_required: true,
      pending_input_change: { id: "review", digest: "review-digest", kind: "intake", upload_id: "input", changes: [] } }}
      overview={<input aria-label="Research note" defaultValue="Keep this draft" />} />);
    fireEvent.click(screen.getByRole("tab", { name: "结果依据" }));
    expect(await screen.findByRole("heading", { name: "这些判断依据什么？" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "核对修改" }));
    expect(screen.getByRole("textbox", { name: "Research note" })).toHaveValue("Keep this draft");
    expect(screen.getByRole("tab", { name: "评估概览" })).toHaveAttribute("aria-selected", "true");
    fireEvent.click(screen.getByRole("tab", { name: "结果依据" }));
    expect(await screen.findByRole("heading", { name: "这些判断依据什么？" })).toBeVisible();
  });
});

it("uses version-bound domain names and readable measurements without losing original source records", async () => {
  const cycleId = "evidence:111111111111111111111111";
  const claimId = "claim:native-domain-synthetic:developmental_compatibility";
  const gapId = "requirement:222222222222222222222222";
  const fixture = { ...graph, returned_node_count: 3, returned_edge_count: 1,
    elements: { nodes: [node(cycleId, "EvidenceRecord"), node(claimId, "Claim"), node(gapId, "EvidenceRequirement")],
      edges: [edge("missing", gapId, claimId, "missing_for")] } };
  const requirementFile = artifact("requirements", "evidence_requirements.json");
  const compilerFile = artifact("compiler", "evidence_compiler_visualization_data.json");
  const payloads: Record<string, unknown> = {
    graph2: fixture,
    records2: { ...records, records: [{ ...record, evidence_id: cycleId, metric_id: "native_s_g2m_fraction",
      domain_id: "proliferation_stress_response", value: 3147 / 9547, numerator: 3147, denominator: 9547, relation: "supports" }] },
    requirements: { graph_id: graph.graph_id, graph_version: 2, requirements: [{
      requirement_id: gapId, requirement_version: "1", claim_ref: { object_id: claimId, object_version: "1" },
      requirement_key: "independent_validation", state: "open", reason_codes: ["measurement_not_provided"] }] },
    compiler: { graph_id: graph.graph_id, graph_version: 2, claim_records: [{
      claim_ref: claimId + "@1", domain_id: "developmental_compatibility", evidence_state: "missing" }] },
  };
  const original = JSON.stringify(payloads);
  vi.spyOn(globalThis, "fetch").mockImplementation(async input => new Response(JSON.stringify(payloads[String(input).split("/").pop()!])));
  render(<EvidenceGraph session={{ ...session, artifacts: [graphArtifact, recordsArtifact, requirementFile, compilerFile] }} />);
  fireEvent.click(await screen.findByRole("button", { name: "观察证据 · S / G2M 期细胞比例" }));
  const detail = within(screen.getByRole("complementary", { name: "证据详情" }));
  expect(detail.getByText(String(3147 / 9547), { selector: "dd" })).toBeVisible();
  expect(detail.getByText("3147", { selector: "dd" })).toBeVisible();
  expect(detail.getByText("9547", { selector: "dd" })).toBeVisible();
  expect(detail.getByText("比例（0–1）", { selector: "dd" })).toBeVisible();
  expect(detail.getByText("支持", { selector: "dd" })).toBeVisible();
  expect(detail.queryByText(cycleId, {exact: false})).not.toBeInTheDocument();
  expect(detail.queryByText("来源记录详情")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "返回概览" }));
  fireEvent.click(screen.getByRole("button", { name: "待补证据 · 发育阶段相容性 · 独立验证" }));
  expect(screen.getByRole("button", { name: "待核对判断 · 发育阶段相容性" })).toBeVisible();
  expect(screen.getByText(/尚未执行或提供此域测量/)).toBeVisible();
  expect(JSON.stringify(payloads)).toBe(original);
});

it("distinguishes same-domain measured claims and their requirements by exact metric bindings", () => {
  const first = node("claim:one", "Claim").data, second = node("claim:two", "Claim").data;
  const rows = [
    { ...record, domain_id:"target_identity", metric_id:"consensus_supported_fraction", claim_ref:{object_id:first.object_id,object_version:"1"} },
    { ...record, domain_id:"target_identity", metric_id:"source_conflict_fraction", claim_ref:{object_id:second.object_id,object_version:"1"} },
  ];
  const claims = [first, second].map(item => ({claim_ref:item.object_id+"@1", domain_id:"target_identity"}));
  expect(label(first, rows, [], claims)).toBe("待核对判断 · 目标身份 · 两参考给出相同候选标签的细胞比例");
  expect(label(second, rows, [], claims)).toBe("待核对判断 · 目标身份 · 两参考给出不同候选标签的细胞比例");
  const requirement = node("requirement:one", "EvidenceRequirement").data;
  const requirements = [{requirement_id:requirement.object_id,requirement_version:1,
    claim_ref:{object_id:first.object_id,object_version:1},requirement_key:"independent_validation"}];
  expect(label(requirement, rows, requirements, claims)).toBe("待补证据 · 目标身份 · 两参考给出相同候选标签的细胞比例 · 独立验证");
  expect(label(first, [], [], claims)).toBe("待核对判断 · 目标身份");
});


describe("candidate composition display", () => {
  const metric = "candidate_composition_fraction_0123456789abcdef";
  const measurementRef = { object_id: "measurement:source-run:composition", object_version: "0.2.0" };
  const observation = { ...record, metric_id: metric, value: 0.75, numerator: 75, denominator: 100,
    measurement_result_ref: measurementRef };
  const mapping = { source_ref: "input:profile@1.0.0", measurement_ref: measurementRef.object_id + "@0.2.0",
    metric_id: metric, label: "L1:Source_A", assignment_state: "candidate", count: 75, denominator: 100,
    fraction: 0.75, interpretation: "candidate_method_output_only" };
  const source = { source_ref: mapping.source_ref, schema_ref: "bridge://schemas/cell-state-candidate-profile/v1.0",
    sha256: "a".repeat(64), receipt_sha256: "b".repeat(64) };
  const display = { graph_id: graph.graph_id, graph_version: graph.graph_version, graph_manifest_sha256: "c".repeat(64),
    composition_mapping: [mapping], sources: [source] };
  it("uses source labels for the exact measurement, claim and requirement without promoting identity", () => {
    const parsed = parseCompositionDisplay(display, graph)!;
    expect(compositionForRecord(observation, parsed)).toEqual(mapping);
    for (const n of [graph.elements.nodes[0].data, graph.elements.nodes[1].data,
      { ...measurementRef, id: "measurement", label: "measurement", node_type: "MeasurementResult" }]) {
      expect(label(n, [observation], [], [], parsed)).toContain("候选组成比例 · L1:Source_A（候选分配）");
    }
    expect(label(graph.elements.nodes[3].data, [observation], [{ requirement_id: "gap", requirement_version: "1",
      claim_ref: observation.claim_ref, requirement_key: "independent_validation" }], [], parsed)).toContain("L1:Source_A（候选分配）");
    for (const state of ["unknown", "unavailable"]) {
      const value = { ...parsed, composition_mapping: [{ ...mapping, label: state, assignment_state: state }] };
      expect(recordMetricName(observation, value)).toBe(state === "unknown" ? "候选组成比例 · 未确定分配" : "候选组成比例 · 不可用分配");
    }
  });
  it.each([
    { graph_id: "other" }, { graph_version: 1 }, { graph_manifest_sha256: "invalid" }, { sources: null },
  ])("rejects mismatched graph metadata %j", change => {
    expect(parseCompositionDisplay({ ...display, ...change }, graph)).toBeNull();
  });
  it.each([
    { measurement_ref: "measurement:other-run:composition@0.2.0" },
    { measurement_ref: measurementRef.object_id + "@0.3.0" }, { metric_id: "other_metric" },
    { source_ref: "missing" }, { count: 74 }, { denominator: 101 }, { fraction: 0.74 },
    { interpretation: "established_identity" }, { assignment_state: "qualified" }, { label: " " },
  ])("does not guess a name when the measurement binding differs %j", change => {
    const altered = { ...display, composition_mapping: [{ ...mapping, ...change }] };
    expect(compositionForRecord(observation, altered)).toBeUndefined();
    expect(recordMetricName(observation, altered)).toBe("候选组成比例（类别见来源）");
  });
  it("rejects duplicate mappings, missing source hashes and ambiguous source registrations", () => {
    for (const changed of [
      { ...display, composition_mapping: [mapping, mapping] },
      { ...display, sources: [source, source] }, { ...display, sources: [{ ...source, sha256: "wrong" }] },
      { ...display, sources: [{ ...source, receipt_sha256: null }] },
    ]) expect(compositionForRecord(observation, changed)).toBeUndefined();
  });
  it("receives graph preview names in search, selection and source drilldown, resetting on version change", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async input => {
      const url = String(input);
      if (url.endsWith("graph2/preview")) return new Response(JSON.stringify(display));
      if (url.endsWith("graph1/preview")) return new Response(JSON.stringify(display)); // stale response is rejected
      return new Response(JSON.stringify(url.endsWith("records2") ? { ...records, records: [observation] }
        : url.endsWith("graph1") ? { ...graph, graph_version: 1 } : graph));
    });
    render(<EvidenceGraph session={session} />);
    const button = await screen.findByRole("button", { name: "观察证据 · 候选组成比例 · L1:Source_A（候选分配）" });
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Source_A" } });
    expect(button).toBeInTheDocument();
    fireEvent.click(button);
    const detail = screen.getByRole("complementary", { name: "证据详情" });
    expect(within(detail).getByText("0.75", { selector: "dd" })).toBeInTheDocument();
    expect(detail).not.toHaveTextContent(mapping.measurement_ref);
    expect(detail).not.toHaveTextContent(source.sha256);
    expect(within(detail).getByText("75", {selector:"dd"})).toBeVisible();
    expect(within(detail).getByText("100", {selector:"dd"})).toBeVisible();
    await act(async () => {
      fireEvent.change(screen.getByRole("combobox"), { target: { value: "graph1" } });
    });
    expect(screen.queryByRole("button", { name: /Source_A/ })).not.toBeInTheDocument();
  });
  it.each(["unavailable", "wrong-version"])("keeps the graph and raw metrics readable when preview is %s", async failure => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async input => {
      const url = String(input);
      if (url.endsWith("/preview")) return failure === "unavailable" ? new Response("", { status: 422 })
        : new Response(JSON.stringify({ ...display, graph_version: 1 }));
      return new Response(JSON.stringify(url.endsWith("records2") ? { ...records, records: [observation] }
        : url.endsWith("graph1") ? { ...graph, graph_version: 1 } : graph));
    });
    render(<EvidenceGraph session={session} />);
    expect(await screen.findByText(/部分候选组成的类别名称不可用/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "观察证据 · 候选组成比例（类别见来源）" }));
    expect(screen.getByText("0.75", { selector: "dd" })).toBeInTheDocument();
    expect(screen.getByRole("complementary", {name:"证据详情"})).not.toHaveTextContent(metric);
    expect(screen.getByText("75", {selector:"dd"})).toBeVisible();
  });
});

describe("assessment citation navigation", () => {
  const querySource: AssessmentEvidence = { alias: "E-query", state: "available", tool_id: "P0-09",
    artifact_ids: ["graph1"], provenance: { graph_id: "case-graph", graph_version: 1 },
    navigation: {tool_run_ref:{object_id:"query",object_version:"1"}, measurements:{}, graph_nodes:{"N-record":"observation"}} };
  const citationSession = { ...session, assessment: { evidence: [querySource] } } as Session;
  const loaded = [{ artifact: graphArtifact, value: graph },
    { artifact: historical, value: { ...graph, graph_version: 1 } }];
  it("pins record citations to the cited version and rejects missing or ambiguous bindings", () => {
    const citation = "E-query#record:N-record@1";
    expect(resolveGraphFocus(loaded, citationSession, citation)).toEqual({ artifactId: "graph1", nodeId: "observation" });
    expect(resolveGraphFocus(loaded.slice(0, 1), citationSession, citation)).toBeNull();
    expect(resolveGraphFocus([...loaded, loaded[1]], citationSession, citation)).toBeNull();
    expect(resolveGraphFocus(loaded, citationSession, "E-query#record:missing@1")).toBeNull();
    expect(resolveGraphFocus(loaded, citationSession, "E-query#record:N-record@2")).toBeNull();
  });
  it("matches exact run versions only in admitted graphs and does not mix graph identities", () => {
    const runNode = node("tool-run:exact", "ToolRun");
    const runGraph = { ...graph, returned_node_count: 5, elements: { ...graph.elements, nodes: [...graph.elements.nodes, runNode] } };
    const state = { ...session, assessment: { evidence: [
      { alias: "E-run", state: "available", tool_id: "P0-03",
        navigation: {tool_run_ref: {object_id:"tool-run:exact",object_version:"1"}, measurements:{},graph_nodes:{}} },
      { alias: "E-graph", state: "available", tool_id: "P0-09", artifact_ids: ["graph2"] },
    ] } } as Session;
    const files = [{ artifact: graphArtifact, value: runGraph }];
    expect(resolveGraphFocus(files, state, "E-run")).toEqual({ artifactId: "graph2", nodeId: "tool-run:exact" });
    expect(resolveGraphFocus([{ artifact: historical, value: runGraph }], state, "E-run")).toBeNull();
    expect(resolveGraphFocus([{ artifact: graphArtifact, value: { ...runGraph,
      elements: { ...runGraph.elements, nodes: [...graph.elements.nodes, {data:{...runNode.data, object_version:"2"}}] } } }], state, "E-run")).toBeNull();
    const other = { artifact: graphArtifact, value: { ...runGraph, graph_id: "other-case" } };
    expect(resolveGraphFocus([...files, other], state, "E-run")).toBeNull();
  });
  it("locates a truncated measurement through its exact canonical artifact and record", () => {
    const measurement = {object_id:"measurement:exact", object_version:"0.2.0"};
    const canonical = {object_id:"artifact:exact", object_version:"0.2.1"};
    const fileNode = {data:{...node("file", "Artifact").data, ...canonical}};
    const small = {...graph, truncated:true, omitted_node_count:1, returned_node_count:1,
      returned_edge_count:0, elements:{nodes:[fileNode], edges:[]}};
    const full = {...records, records:[{...record, measurement_result_ref:measurement, artifact_refs:[canonical]}]};
    const source: AssessmentEvidence = {alias:"E-run", state:"available", tool_id:"P0-04",
      navigation:{tool_run_ref:{object_id:"run",object_version:"0.2.1"},
        measurements:{"M-exact":measurement}, measurement_artifacts:{"M-exact":canonical}, graph_nodes:{}}};
    const state = {...session, assessment:{evidence:[source,
      {alias:"E-graph",state:"available",tool_id:"P0-09",artifact_ids:["graph2"]}]}} as Session;
    const files = [{artifact:graphArtifact,value:small},{artifact:recordsArtifact,value:full}];
    const cite = "E-run#measurement:M-exact@1";
    expect(resolveGraphFocus(files, state, cite)).toEqual({artifactId:"graph2",nodeId:"file"});
    for (const changed of [
      {...full, graph_version:1},
      {...full, records:[{...full.records[0], measurement_result_ref:{...measurement,object_version:"0.1.0"}}]},
      {...full, records:[{...full.records[0], artifact_refs:[{...canonical,object_version:"0.2.0"}]}]},
      {...full, records:[full.records[0],full.records[0]]},
    ]) expect(resolveGraphFocus([files[0],{artifact:recordsArtifact,value:changed}],state,cite)).toBeNull();
    expect(resolveGraphFocus([files[0]],state,cite)).toBeNull();
    expect(resolveGraphFocus([...files,files[1]],state,cite)).toBeNull();
    expect(resolveGraphFocus([{artifact:historical,value:small},files[1]],state,cite)).toBeNull();
    expect(resolveGraphFocus(files, {...state, assessment:{evidence:[{
      ...source,navigation:{...source.navigation!,measurement_artifacts:{}}}, state.assessment!.evidence[1]]}} as Session, cite)).toBeNull();
  });
  it("opens the graph from a result citation with the exact record selected", async () => {
    mockArtifacts();
    render(<ResultsPane session={citationSession} overview={openGraph =>
      <button onClick={() => openGraph("E-query#record:N-record@1")}>查看判断依据</button>} />);
    fireEvent.click(screen.getByRole("button", {name:"查看判断依据"}));
    await screen.findByText("已定位引用的保存记录；科学状态仍以原记录为准。");
    expect(screen.getByRole("tab", {name:"结果依据"})).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("combobox", {name:"保存版本"})).toHaveValue("graph1");
    expect(screen.getByRole("button", {name:/观察证据/})).toHaveAttribute("aria-pressed", "true");
    fireEvent.change(screen.getByRole("combobox", {name:"保存版本"}), {target:{value:"graph2"}});
    expect(await screen.findByText("当前查看其他保存版本，未将引用定位沿用到该版本。")).toBeVisible();
  });
  it("shows a missing graph rather than leaving the result panel blank", async () => {
    render(<ResultsPane session={{...citationSession, artifacts:[]}} overview={openGraph =>
      <button onClick={() => openGraph("E-query#record:N-record@1")}>查看判断依据</button>} />);
    fireEvent.click(screen.getByRole("button", {name:"查看判断依据"}));
    expect(await screen.findByText(/尚无可读取且结构完整的结果依据/)).toBeVisible();
  });
});


it("adds proposed semantic edges only for the exact report graph manifest and preserves reasons", () => {
  const extra = { ...graph, graph_manifest_sha256: "a".repeat(64), explanation_sha256: "c".repeat(64),
    qualification: "unverified", returned_node_count: 2, returned_edge_count: 1,
    elements: { nodes: [node("proposed", "ProposedExplanation"), node("citation", "SourceCitation")],
      edges: [{ data: { id: "limitation", source: "citation", target: "proposed", edge_type: "limits",
        rationale: "Aggregate expression does not establish cell identity.", applicability: "This sample only." } }] } };
  const loaded = [{ artifact: { ...artifact("report", "research_report.json"), tool_id: "P0-10" },
    value: { object_version: "0.5.0", graph_id: graph.graph_id, graph_version: 2,
      graph_manifest_sha256: "a".repeat(64), snapshot_sha256: "b".repeat(64), interpretation_graph_json: JSON.stringify(extra) } }];
  const parsed = parseGraph(graph)!;
  const merged = withInterpretation(parsed, loaded, "a".repeat(64));
  expect(merged.elements.edges.at(-1)?.data.rationale).toContain("Aggregate expression");
  expect(visibleElements(merged, null, false).nodes.some(n => n.id === "proposed")).toBe(true);
  expect(withInterpretation(parsed, loaded, "d".repeat(64))).toBe(parsed);
  expect(withInterpretation(parsed, [...loaded, { ...loaded[0], value: { ...loaded[0].value, snapshot_sha256: "e".repeat(64) } }], "a".repeat(64))).toBe(parsed);
});


it("keeps a proposed relation's exact measurement endpoint visible in the overview", () => {
  const linked = { ...parseGraph(graph)!, elements: { nodes: [...graph.elements.nodes, node("measurement", "MeasurementResult"), node("hypothesis", "ProposedExplanation")],
    edges: [...graph.elements.edges, { data: { id: "interpretation-edge", source: "measurement", target: "hypothesis", edge_type: "limits", qualification: "unverified" } }] } };
  const overview = visibleElements(linked, null, false);
  expect(overview.nodes.some(n => n.id === "measurement")).toBe(true);
  expect(overview.edges.some(e => e.id === "interpretation-edge")).toBe(true);
});


it.each([
  { reportBytes: 2_100_000, largeRecords: false, reportVisible: true, failedAttachment: false },
  { reportBytes: 8_100_000, largeRecords: false, reportVisible: false, failedAttachment: true },
  { reportBytes: 2_100_000, largeRecords: true, reportVisible: true, failedAttachment: true },
])("keeps report and ordinary graph byte limits distinct: %j", async ({ reportBytes, largeRecords, reportVisible, failedAttachment }) => {
  const manifest = "a".repeat(64);
  const extra = { ...graph, graph_manifest_sha256: manifest, explanation_sha256: "c".repeat(64),
    qualification: "unverified", returned_node_count: 1, returned_edge_count: 0,
    elements: { nodes: [node("proposed", "ProposedExplanation")], edges: [] } };
  const reportArtifact = { ...artifact("report", "research_report.json"), tool_id: "P0-10" };
  const payloads: Record<string, unknown> = {
    graph2: graph,
    records2: { ...records, padding: largeRecords ? "x".repeat(2_100_000) : "" },
    report: { object_version: "0.5.0", graph_id: graph.graph_id, graph_version: 2,
      graph_manifest_sha256: manifest, snapshot_sha256: "b".repeat(64),
      interpretation_graph_json: JSON.stringify(extra), report_context_json: "x".repeat(reportBytes) },
  };
  vi.spyOn(globalThis, "fetch").mockImplementation(async input => new Response(JSON.stringify(
    String(input).endsWith("/preview") ? { graph_id: graph.graph_id, graph_version: 2,
      graph_manifest_sha256: manifest, composition_mapping: [], sources: [] }
      : payloads[String(input).split("/").pop()!])));
  render(<EvidenceGraph session={{ ...session, artifacts: [graphArtifact, recordsArtifact, reportArtifact] }} />);
  if (reportVisible) expect(await screen.findByText(/虚线边框为模型提出的解释/)).toBeVisible();
  else {
    await screen.findByText(/相关附件未能读取/);
    expect(screen.queryByText(/虚线边框为模型提出的解释/)).not.toBeInTheDocument();
  }
  expect(Boolean(screen.queryByText(/相关附件未能读取/))).toBe(failedAttachment);
});

it.each(["http", "network", "invalid-json", "wrong-binding", "oversized"])(
  "shows unavailable overlay without candidate composition when preview fails: %s", async failure => {
    const fetch = vi.spyOn(globalThis, "fetch").mockImplementation(async input => {
      if (String(input).endsWith("/preview")) {
        if (failure === "network") throw new Error("PRIVATE transport details");
        if (failure === "http") return new Response("PRIVATE", { status: 422 });
        if (failure === "invalid-json") return new Response("PRIVATE invalid JSON");
        if (failure === "oversized") return new Response(" ".repeat(2_000_001));
        return new Response(JSON.stringify({ graph_id: "other", graph_version: 2,
          graph_manifest_sha256: "a".repeat(64), composition_mapping: [], sources: [] }));
      }
      return new Response(JSON.stringify(String(input).endsWith("records2") ? records : graph));
    });
    render(<EvidenceGraph session={{ ...session, artifacts: [graphArtifact, recordsArtifact] }} />);
    expect(await screen.findByText(/解释图叠加层当前不可用/)).toBeVisible();
    expect(screen.queryByText(/PRIVATE/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "观察证据 · 名称待核对" }));
    expect(screen.getByText("0", { selector: "dd" })).toBeVisible();
    fetch.mockImplementation(async input => new Response(JSON.stringify(String(input).endsWith("/preview")
      ? { graph_id: graph.graph_id, graph_version: 2, graph_manifest_sha256: "a".repeat(64), composition_mapping: [], sources: [] }
      : String(input).endsWith("records2") ? records : graph)));
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "重新加载解释图" })); });
    expect(screen.queryByText(/解释图叠加层当前不可用/)).not.toBeInTheDocument();
    expect(screen.getByText("0", { selector: "dd" })).toBeVisible();
  });
