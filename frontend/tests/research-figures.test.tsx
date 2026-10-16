import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ResearchFigures, { compositionRows, scopedFigureSession } from "../src/components/ResearchFigures";
import ReferenceSimilarity, { parseSimilarity } from "../src/components/ReferenceSimilarity";
import type { AssessmentAxis, AssessmentEvidence, Session } from "../src/types";

const candidate = { alias:"source-1",tool_id:"P0-02",state:"available",summary:{
  analysis_scope:"candidate_method_observation",composition:[
    {label:"L1:Radial_Glia",state:"candidate",fraction:0.7,count:7,denominator:10},
    {label:"unknown",state:"unknown",fraction:0.3,count:3,denominator:10},
  ]},artifact_ids:[] } as unknown as AssessmentEvidence;
const base = {id:"test",artifacts:[],assessment:{evidence:[candidate],portrait:[],freshness:{state:"current"}}} as unknown as Session;
const row = (kind:string,raw:number|null) => ({measurement:{measurement_id:kind,unit:"similarity_coefficient",domain_score:null,raw_value:raw},definition:{
  native_field:kind,label:"Reference A",label_level:"L1",profile_id:"profile",source_id:"source",shared_genes:123},measurement_sha256:"a".repeat(64)});
const projection = {kind:"reference_similarity",reference_manifest_ref:"reference@1.0",n_observations:10,rows:[row("spearman",null),row("cosine",0.25)]};

it("shows only scope-bound available evidence, including context and family dependencies", async () => {
  const artifact = (id: string) => ({id,name:"native_measurement_spec."+id+".json",kind:"download" as const,tool_id:"P0-03",media_type:"application/json",url:"https://untrusted.invalid"});
  const axis: AssessmentAxis = {id:"target_identity",title:"目标身份",state:"missing",reason_codes:[],summary:{},
    evidence_aliases:[],context_evidence_aliases:["context#measurement:m@1"]};
  const family = {...axis,id:"process",context_evidence_aliases:[],families:[{...axis,id:"cycle",context_evidence_aliases:[],evidence_aliases:["family"]}]};
  const source: Session = {...base,artifacts:["context","dependency","unavailable","history","denied"].map(artifact).map(a => a.id === "denied" ? {...a,access_state:"denied" as const} : a),
    assessment:{...base.assessment!,portrait:[axis],evidence:[
      {...candidate,alias:"context",tool_id:"P0-03",artifact_ids:["context","denied"],summary:{runtime_mode:"reference_similarity"}},
      {...candidate,alias:"family",artifact_ids:[],dependencies:[{role:"source",schema_ref:"source",object_version:"1",sha256:"a".repeat(64),artifact_ids:["dependency"]}]},
      {...candidate,alias:"unavailable",state:"unavailable",artifact_ids:["unavailable"]},
    ]}};
  expect(scopedFigureSession(source,[family]).artifacts.map(a => a.id)).toEqual(["dependency"]);
  expect(scopedFigureSession(source).artifacts.map(a => a.id)).toEqual(["context","dependency"]);
  const fetcher = vi.spyOn(globalThis,"fetch").mockResolvedValue(Response.json(projection));
  render(<ResearchFigures session={source} axes={[axis]}/>);
  expect(await screen.findByRole("figure",{name:"参考相似度图"})).toBeVisible();
  expect(screen.getByRole("cell",{name:"不可用（未补零）"})).not.toBeVisible();
  await userEvent.click(screen.getByText("系数与说明"));
  expect(screen.getByRole("cell",{name:"不可用（未补零）"})).toBeVisible();
  expect(fetcher.mock.calls.filter(([url])=>String(url).includes("/artifacts/"))).toHaveLength(1);
  expect(fetcher.mock.calls[0][0]).toBe("/api/sessions/test/artifacts/context/preview");
  expect(screen.getByText(/目标身份：/).parentElement).toHaveTextContent("缺少证据");
  expect(screen.queryByRole("region",{name:"候选组成"})).not.toBeInTheDocument();
});

it("keeps unknown categories, denominators and missing proportions distinct", async () => {
  render(<ResearchFigures session={base}/>);
  const chart = within(screen.getByRole("figure",{name:"候选细胞组成图"}));
  expect(chart.getByRole("img",{name:"Radial Glia: 70%, 7 / 10"})).toBeVisible();
  expect(chart.getByRole("img",{name:"未确定分配: 30%, 3 / 10"})).toBeVisible();
  expect(screen.getByRole("table",{name:"候选组成比例与完整分母"})).not.toBeVisible();
  await userEvent.click(screen.getByText("数值与说明"));
  expect(screen.getByRole("cell",{name:"7 / 10"})).toBeVisible();
  expect(screen.getByRole("rowheader",{name:"未确定分配"})).toBeVisible();
  expect(screen.getByText(/尚未登记可核验的参考相似系数/)).toBeVisible();
  expect(compositionRows({...candidate,summary:{...candidate.summary,composition:[{label:"unknown",state:"unknown",fraction:null,count:3,denominator:10}]}})).toEqual([]);
});
it("keeps methods and units separate and exposes exact original means", () => {
  const process = {alias:"process",tool_id:"P0-06",state:"available",artifact_ids:[],summary:{runtime_mode:"exploratory_process",program_summaries:[
    {program_id:"S",method_id:"PROC-SCORE-SCANPY",score_unit:"scanpy_control_adjusted_expression",mean:-0.05475292280919151,n_observations:10,assessment_state:"available"},
    {program_id:"S",method_id:"PROC-SCORE-DECOUPLER",score_unit:"decoupler_ulm_t_value",mean:null,n_observations:10,assessment_state:"unavailable"},
  ]}};
  render(<ResearchFigures session={{...base,assessment:{...base.assessment!,evidence:[process as unknown as AssessmentEvidence]}}}/>);
  expect(within(screen.getByRole("table",{name:"相对背景表达数值"})).getByTitle("-0.05475292280919151")).toHaveTextContent("-0.054753");
  expect(within(screen.getByRole("table",{name:"基因集关联数值"})).getAllByText("不可用")).toHaveLength(2);
  expect(screen.getByText("t 值 · 探索性 RNA 观察")).toBeVisible();
  expect(screen.getByRole("heading",{name:"相对背景表达"})).toBeVisible();
  expect(screen.getByText(/Scanpy：相关基因/)).not.toBeVisible();
  expect(screen.queryByText("Scanpy 程序得分")).not.toBeInTheDocument();
});
it("explains candidate directions, signed-method refusal and distinct missing source members", async () => {
  // Synthetic values exercise the source contract without copying a research run.
  const programs = [
    {program_id:"PROC-PLURI",source_gene_set:"HU-2020-TABLE-S1",direction_definition:"candidate_membership_plus_one",
      declared_gene_count:6,unresolved_member_count:0},
    {program_id:"PROC-DISSOC",source_gene_set:"OFLANAGAN-2019-CORE",direction_definition:"sign_of_source_logFC",
      declared_gene_count:8,unresolved_member_count:2},
  ];
  const summaries = programs.flatMap(program => ["PROC-SCORE-SCANPY","PROC-SCORE-DECOUPLER"].map(method_id => {
    const refused = program.program_id === "PROC-DISSOC" && method_id === "PROC-SCORE-SCANPY";
    return {...program,method_id,score_unit:method_id === "PROC-SCORE-SCANPY" ? "scanpy_control_adjusted_expression" : "decoupler_ulm_t_value",
      mean:refused ? null : -0.25,median:refused ? null : -0.2,lower_quantile:refused ? null : -0.5,upper_quantile:refused ? null : 0.1,
      observed_gene_count:5,gene_coverage_fraction:5/program.declared_gene_count,missing_genes:["SYNTHETIC_MISSING"],ambiguous_genes:[],
      gene_symbols_sha256:"a".repeat(64),signature_scope:refused ? "not_estimable" : "observed_feature_subset",n_observations:12,
      assessment_state:refused ? "not_assessed" : "available",reason_codes:refused ? ["scanpy_signed_signature_not_supported"] : []};
  }));
  const unknown = {...summaries[1],source_gene_set:"UNREGISTERED-CANDIDATE",direction_definition:undefined,unresolved_member_count:undefined};
  const process = {alias:"process",tool_id:"P0-06",state:"available",artifact_ids:["profile"],summary:{runtime_mode:"exploratory_programs",program_summaries:[...summaries,unknown]}};
  render(<ResearchFigures session={{...base,artifacts:[{id:"profile",name:"exploratory_process_profile.json",kind:"download",media_type:"application/json",tool_id:"P0-06",url:"https://untrusted.invalid"}],
    assessment:{...base.assessment!,evidence:[process as unknown as AssessmentEvidence]}}}/>);
  expect(screen.getAllByRole("rowheader",{name:"多能性相关候选基因集（Hu 2020）"})).toHaveLength(2);
  expect(screen.getByText(/不同单位不可横向比较/)).not.toBeVisible();
  await userEvent.click(screen.getByText("方法与限制"));
  for (const summary of screen.getAllByText("方法、数值与覆盖")) await userEvent.click(summary);
  expect(screen.getByText(/不同单位不可横向比较/)).toBeVisible();
  expect(screen.getByText(/有向 ULM 按来源签名的正负方向/)).toBeVisible();
  const scanpy = within(screen.getByRole("table",{name:"相对背景表达数值"}));
  const refused = within(scanpy.getByRole("row",{name:/解离／热休克相关候选基因集/}));
  expect(refused.getByText("该方法不适用于带正负方向的签名。")).toBeVisible();
  expect(refused.getAllByTitle("不可用")).toHaveLength(2);
  const ulm = within(screen.getByRole("table",{name:"基因集关联数值"}));
  const directed = within(ulm.getByRole("row",{name:/解离／热休克相关候选基因集/}));
  expect(directed.getByTitle("-0.25")).toHaveTextContent("-0.25");
  expect(directed.getByText(/5 \/ 8 个来源成员/)).toBeVisible();
  await userEvent.click(directed.getByText("覆盖详情与基因集来源"));
  expect(directed.getByText(/未匹配基因（输入中未找到，未补零）：SYNTHETIC_MISSING/)).toBeVisible();
  expect(directed.getByText("源文件未解析成员：2（未补零；保留在来源分母中）")).toBeVisible();
  expect(directed.getByText(/使用来源 logFC 的正负号/)).toBeVisible();
  expect(directed.getByRole("link",{name:"下载数值与完整来源"})).toHaveAttribute("href","/api/sessions/test/artifacts/profile");
  const membership = within(ulm.getByRole("row",{name:/多能性相关候选基因集/}));
  await userEvent.click(membership.getByText("覆盖详情与基因集来源"));
  expect(membership.getByText(/候选成员统一为 \+1，不是原文拟合权重/)).toBeVisible();
  const fallback = within(ulm.getByRole("row",{name:/候选基因集（名称见来源）/}));
  await userEvent.click(fallback.getByText("覆盖详情与基因集来源"));
  expect(fallback.getByText("基因集：来源名称未提供")).toBeVisible();
  expect(screen.queryByText(/UNREGISTERED-CANDIDATE/)).not.toBeInTheDocument();
  expect(fallback.getByText("方向定义：未提供")).toBeVisible();
  expect(fallback.getByText("源文件未解析成员：未提供（未补零；保留在来源分母中）")).toBeVisible();
});
it("separates reference coefficients, preserves null and rejects ambiguous rows", async () => {
  expect(parseSimilarity({...projection,rows:[row("spearman",0.2),row("spearman",0.3)]})).toBeNull();
  expect(parseSimilarity({...projection,rows:[row("cosine",2)]})).toBeNull();
  vi.spyOn(globalThis,"fetch").mockResolvedValue(Response.json(projection));
  render(<ReferenceSimilarity session={{...base,artifacts:[{id:"spec",name:"native_measurement_spec.display-redacted.json",kind:"download",tool_id:"P0-03",media_type:"application/json",url:"https://untrusted.invalid"}]}}/>);
  expect(await screen.findByRole("figure",{name:"参考相似度图"})).toBeVisible();
  expect(screen.getByRole("cell",{name:"不可用（未补零）"})).not.toBeVisible();
  await userEvent.click(screen.getByText("系数与说明"));
  expect(screen.getByRole("cell",{name:"不可用（未补零）"})).toBeVisible();
  expect(screen.getByRole("figure",{name:"参考相似度图"}).querySelector(".similarity-track b")).toBeNull();
  await userEvent.selectOptions(screen.getByRole("combobox",{name:"选择参考与系数"}),"source|profile|L1|cosine");
  expect(screen.getByRole("cell",{name:"0.2500"})).toBeVisible();
  const chart = screen.getByRole("figure",{name:"参考相似度图"});
  expect(chart.querySelector(".similarity-track b")).toHaveStyle({left:"62.5%"});
  expect(screen.queryByRole("cell",{name:"不可用（未补零）"})).not.toBeInTheDocument();
});
it("uses receipt-bound image and table IDs and opens the table only on request", async () => {
  const a = (id:string,kind:"figure"|"table"|"download",media_type:string) => ({id,kind,name:id,media_type,tool_id:"P0-01",url:"https://untrusted.invalid"});
  const set={...a("set","download","application/json"),name:"qc_visualization_artifact_set.json"};
  const fetcher=vi.spyOn(globalThis,"fetch").mockImplementation(async(input)=>String(input).endsWith("/preview") ? Response.json({kind:"typed_figures",figures:[{
    contract:{visualization_id:"v",component_id:"bridge.qc.readiness-flow",scientific_status:"candidate",insight_title:"QC",takeaway:"Saved observation",accessibility:{alt_text:"Saved QC figure"}},
    renders:[a("bound-svg","figure","image/svg+xml")],table:a("bound-table","table","text/tab-separated-values"),data:a("bound-data","download","application/json"),
  }]}) : new Response("value\tdenominator\n7\t10"));
  render(<ResearchFigures session={{...base,artifacts:[set],assessment:{...base.assessment!,evidence:[{...candidate,artifact_ids:[set.id]}]}}}/>);
  expect(await screen.findByRole("img",{name:"Saved QC figure"})).toHaveAttribute("src","/api/sessions/test/artifacts/bound-svg");
  expect(fetcher.mock.calls.filter(([url])=>String(url).includes("/artifacts/"))).toHaveLength(1);
  await userEvent.click(screen.getByText("数据与下载"));
  await userEvent.click(screen.getByRole("button",{name:"查看同源数据表"}));
  expect(await screen.findByRole("cell",{name:"7"})).toBeVisible();
  expect(fetcher).toHaveBeenLastCalledWith("/api/sessions/test/artifacts/bound-table",expect.objectContaining({credentials:"same-origin"}));
});

it("shows fine-state whole-view counts without promoting parent-only labels", async () => {
  const record = (record_id: string, state_id: string|null, parent_state_id: string|null, count: number) => ({
    record_id,state_id,parent_state_id,count,whole_product_denominator:10,whole_product_fraction:count/10,
    parent_fraction:parent_state_id ? count/4 : count/10,resolution_state:state_id ? "resolved" : "unavailable",
  });
  const context = {...candidate,tool_id:"P0-05",summary:{runtime_mode:"saved_cell_state_context",target_fraction:null,non_target_fraction:null,
    role_judgement_state:"not_assessed",data_view:{n_observations:10},primary_composition:[],auxiliary_composition:[],
    source_definition_decisions:{"L2:RG_mFP":"parent_only"},whole_product_composition:[
      record("fine","L2:RG_mFP","L1:Radial_Glia",2),record("unresolved",null,"L1:Radial_Glia",2),record("broad","L1:Neuron_DA",null,6),
    ]}};
  render(<ResearchFigures session={{...base,assessment:{...base.assessment!,evidence:[context]}}}/>);
  expect(screen.getByRole("figure",{name:"整批候选组成图"})).toBeVisible();
  expect(within(screen.getByRole("figure",{name:"整批候选组成图"})).getByText(/仅父级支持，细分未定/)).toBeVisible();
  expect(screen.getByRole("table",{name:"整批候选组成"})).not.toBeVisible();
  await userEvent.click(screen.getByText("整批数值与说明"));
  const table = within(screen.getByRole("table",{name:"整批候选组成"}));
  expect(table.getAllByRole("cell",{name:"2 / 10"})).toHaveLength(2);
  expect(table.getAllByRole("cell",{name:"20%"})).toHaveLength(2);
  expect(table.getAllByRole("cell",{name:"50%"})).toHaveLength(2);
  expect(table.getByText("仅支持父级范围；细分身份未确定")).toBeVisible();
  expect(screen.getByText(/目标比例：尚未判定/)).toBeVisible();
  await userEvent.click(screen.getByText("方法与来源"));
  expect(screen.queryByText(/"parent_only"/)).not.toBeInTheDocument();
  expect(table.getByText("仅支持父级范围；细分身份未确定")).toBeVisible();
});

it("shows saved target roles with unresolved mass and explicit source reasons", async () => {
  const context = {...candidate,tool_id:"P0-03",summary:{runtime_mode:"saved_cell_state_context",target_fraction:null,non_target_fraction:null,
    role_judgement_state:"partial",data_view:{n_observations:10},primary_composition:[],auxiliary_composition:[],
    source_definition_decisions:{"state:child":"parent_only","state:target":"evaluate"},
    whole_product_composition:[
      {record_id:"fine",state_id:"state:child",count:4,whole_product_denominator:10,whole_product_fraction:.4},
      {record_id:"broad",state_id:"state:target",count:6,whole_product_denominator:10,whole_product_fraction:.6}],
    role_records:[
      {record_id:"fine",product_role:"role_unresolved",source_refs:[],reason_code:"source_definition_parent_only"},
      {record_id:"broad",product_role:"target",source_refs:["source:review"],reason_code:null}]}};
  render(<ResearchFigures session={{...base,assessment:{...base.assessment!,evidence:[context]}}}/>);
  expect(screen.getByText(/目标比例：尚未判定/)).toBeVisible();
  await userEvent.click(screen.getByText("整批数值与说明"));
  const table=within(screen.getByRole("table",{name:"整批候选组成"}));
  expect(table.getByText("来源仅支持父级范围")).toBeVisible();
  expect(table.getByText("来自已审核的角色映射；候选身份仍有不确定性")).toBeVisible();
  expect(table.getByText("4 / 10")).toBeVisible();
  expect(table.getByText("未判定部分仍在分母中")).toBeVisible();
});

it("keeps marker direction and review-pending state on the visible graph", () => {
  const context = {...candidate,tool_id:"P0-04",summary:{runtime_mode:"saved_cell_state_context",expected_window_match:null,
    marker_observations:[{state_id:"L1:Example",positive_genes:["POS"],counter_genes:["NEG"],gene_detection:{
      POS:{count:3,denominator:10,state:"measured"},NEG:{count:7,denominator:10,state:"measured"},MISSING:{count:null,denominator:10,state:"missing"}}}]}};
  render(<ResearchFigures session={{...base,assessment:{...base.assessment!,freshness:{...base.assessment!.freshness,state:"review_pending"},evidence:[context]}}}/>);
  const graph = within(screen.getByRole("figure",{name:"标记基因检出率图"}));
  expect(graph.getByText("NEG · 反向")).toBeVisible();
  expect(graph.getByText("POS · 正向")).toBeVisible();
  expect(graph.getByText("不可用")).toBeVisible();
  expect(screen.getByText("资料待核对")).toBeVisible();
  expect(screen.queryByText("历史结果")).not.toBeInTheDocument();
});
it("renders legacy composition groups separately without changing denominators", () => {
  const context = {...candidate,tool_id:"P0-05",summary:{runtime_mode:"saved_cell_state_context",target_fraction:null,non_target_fraction:null,
    primary_composition:[{channel:"primary_celltypist_candidate",source_id:"internal-source",label_level:"L1",denominator_scope:"selected_data_view",label:"A",count:4,denominator:10,fraction:.4}],
    auxiliary_composition:[{channel:"reference",source_id:"internal-reference",label_level:"L2",denominator_scope:"other",label:"B",count:3,denominator:20,fraction:.15}]}};
  render(<ResearchFigures session={{...base,assessment:{...base.assessment!,evidence:[context]}}}/>);
  expect(within(screen.getByRole("figure",{name:"来源组成图 1"})).getByTitle("A: 4 / 10")).toBeVisible();
  expect(within(screen.getByRole("figure",{name:"来源组成图 2"})).getByTitle("B: 3 / 20")).toBeVisible();
  expect(screen.queryByText(/internal-source|internal-reference/)).not.toBeInTheDocument();
});
