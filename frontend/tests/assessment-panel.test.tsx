import { render, screen, within, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../src/App";
import type { Session, Assessment, AssessmentAxis } from "../src/types";

const missing = (id: string, title: string): AssessmentAxis => ({ id, title, state: "missing",
  reason_codes: ["no_scope_evidence"], evidence_aliases: [], summary: {} });
const titles = ["多能性样程序", "细胞周期", "解离 / 热休克", "氧化应激", "缺氧", "未折叠蛋白反应", "凋亡相关程序"];
const assessment: Assessment = {
  scope_id: "scope-exact", scope_digest: "digest-exact", question: "这批细胞的状态和组成如何？",
  upload_id: "upload-exact", input_revision: 3, max_tool_runs: 5, max_model_turns: 8,
  tool_runs_used: 2, model_turns_used: 3, status: "stopped", stop_reason: "no_discriminating_check",
  scope_authorized: true, scope_grants_scientific_approval: false,
  question_sent_to_model: true, result_summaries_enabled: true,
  allowed_modes: [{tool_id:"P0-03",mode_id:"default"},{tool_id:"P0-06",mode_id:"exploratory_process"}],
  candidates: [{tool_id:"P0-03",mode_id:"default",runnable:false,blockers:["scientific_source_review_pending"],gaps:[]}],
  blockers: [{tool_id:"P0-03",mode_id:"default",reason_codes:["scientific_source_review_pending"]}],
  freshness: {state:"current",reason_code:null,current_input_revision:3,scope_input_revision:3,pending_review:false},
  data_view: {state:"available",n_observations:4,view_kind:"qc_selected_observations",sha256:"view-exact"},
  resources:[{alias:"R-local",schema_ref:null,resource_ref:"bridge://resources/seurat-cell-cycle-candidate/v5.5.1",
    object_version:"0.1.0",sha256:"resource-exact",source:"package_resource"}],
  stop_conditions:["explicit_stop","finite_budgets"], history: [],
  evidence:[{alias:"E-exact",state:"available",tool_id:"P0-04",tool_version:"0.1.0",
    summary:{whole_product_profile:{denominator:4},target_related_profile:{denominator:2}},
    measurements:[{alias:"M-exact",metric_name:"developmental_fraction",raw_value:0.5,numerator:2,denominator:4,
      unit:"fraction",evidence_state:"shadow",domain_score:null,source_alias:"E-exact",artifact_sha256:"artifact-exact"}],
    provenance:{receipt_sha256:"receipt-exact",plan_id:"plan-exact",graph_version:2},
    dependencies:[{role:"product_case",schema_ref:"bridge://schemas/product-case/v0.1",object_version:"0.1.0",
      sha256:"dependency-exact",artifact_ids:["bound-table"]}],artifact_ids:["bound-table"]}],
  hypotheses:[{statement:"一个待检验解释",competing_explanation:"另一解释仍然开放",
    discriminating_check:"P0-03",evidence_aliases:["E-exact"]}],
  portrait:[
    missing("cell_state","细胞状态"),
    {...missing("target_identity","目标身份"),state:"unavailable",reason_codes:["scientific_source_review_pending"]},
    missing("regional_identity","区域身份"),
    {id:"development",title:"发育阶段",state:"available",reason_codes:[],evidence_aliases:["E-exact"],
      summary:{whole_product_profile:{denominator:4,role_fractions:[{role:"within_window",numerator:2,denominator:4,fraction:0.5}]},
        target_related_profile:{denominator:2,role_fractions:[{role:"within_window",numerator:2,denominator:2,fraction:1}]}}},
    missing("composition","全产品与非目标组成"),
    {...missing("process","增殖与应激"),families:titles.map((title,index): AssessmentAxis =>({
      id:String(index),title,state:index===1?"measured":"unavailable",evidence_aliases:index===1?["E-exact"]:[],
      reason_codes:index===1?[]:["reviewed_family_mapping_unavailable"],
      summary:index===1?{s_g2m_fraction:0.5,n_observations:4}:{},
    }))},
  ],
};
const session: Session = {
  id:"session-1", title:"Synthetic projection", updated_at:"2026-09-11T00:00:00Z", status:"idle",
  messages:[], uploads:[], plan:null, artifacts:[{
    id:"bound-table",name:"exact-denominators.tsv",kind:"table",media_type:"text/tab-separated-values",
    url:"https://must-not-use.invalid",tool_id:"P0-04"}],
  error:null,input_review_required:false,pending_input_change:null,assessment,
};
function load(value: Session = session) {
  localStorage.clear();
  return vi.spyOn(globalThis,"fetch").mockImplementation(async(input) => {
    const path=String(input);
    if(path==="/api/sessions") return Response.json({sessions:[value]});
    if(path==="/api/sessions/session-1") return Response.json(value);
    if(path.endsWith("/artifacts/bound-table")) return new Response("numerator\tdenominator\n2\t4");
    throw new Error("Unexpected request: "+path);
  });
}

it("keeps eligible interpretation gaps separate and approves the exact finite scope by keyboard", async()=>{
  const value: Session = {...session,assessment:{...assessment,status:"proposed",scope_authorized:false,stop_reason:null,
    candidates:[{tool_id:"P0-09",mode_id:"case_append_v2",runnable:true,blockers:[],gaps:["measured_claim_binding_required"]}]}};
  const fetcher=load(value as typeof session);
  const requests: unknown[]=[];
  fetcher.mockImplementation(async(input,init)=>{
    const path=String(input);
    if(path==="/api/sessions") return Response.json({sessions:[value]});
    if(path.endsWith("/assessment/approve")){
      requests.push(JSON.parse(String(init?.body)));
      return Response.json({...value,status:"running",assessment:{...value.assessment,status:"running",scope_authorized:true}});
    }
    return Response.json(value);
  });
  render(<App />);
  const approval=await screen.findByRole("button",{name:"批准本范围"});
  expect(approval).toBeDisabled();
  expect(screen.getByText(/工具运行：2 \/ 5/)).toBeInTheDocument();
  expect(screen.getByText(/模型轮次：3 \/ 8/)).toBeInTheDocument();
  expect(screen.getByText(/解释缺口（不阻止本项检查）/)).toBeInTheDocument();
  const consent=screen.getByRole("checkbox",{name:/已核对问题、范围、资源和未解决条件/});
  consent.focus();
  const user=userEvent.setup();
  await user.keyboard("[Space]");
  expect(approval).toBeEnabled();
  approval.focus();
  await user.keyboard("[Enter]");
  await waitFor(()=>expect(requests).toEqual([{scope_id:"scope-exact",scope_digest:"digest-exact"}]));
});

it("explains missing intake facts before approval and keeps identifiers in collapsed details", async()=>{
  load({...session,assessment:{...assessment,status:"proposed",scope_authorized:false,
    candidates:[{tool_id:"P0-02",mode_id:null,runnable:false,
      blockers:["asset_declaration_required","supported_product_family_required"],gaps:[]}]}});
  render(<App />);
  const conditions=await screen.findByRole("region",{name:"前提条件"});
  expect(within(conditions).getByText(/请在产品资料中确认实验类型、原始计数语义和计数位置/)).toBeVisible();
  expect(within(conditions).getByText(/请在完整资料中选择已知产品类别/)).toBeVisible();
  expect(within(conditions).getByText("asset_declaration_required")).not.toBeVisible();
  expect(within(conditions).getByText(/P0-02/)).not.toBeVisible();
  const details=within(conditions).getByText("技术详情");
  await userEvent.setup().click(details);
  expect(within(conditions).getByText(/P0-02/)).toBeVisible();
});

it("keeps raw reasons collapsed inside numeric fallback tables",async()=>{
  load({...session,assessment:{...assessment,portrait:[{...assessment.portrait[0],state:"available",reason_codes:[],
    summary:{n_observations:4,reason_codes:["asset_declaration_required"]}}]}});
  render(<App />);
  const axis=await screen.findByRole("region",{name:"细胞状态"});
  expect(within(axis).getByRole("cell",{name:"4"})).toBeVisible();
  expect(within(axis).getByText("asset_declaration_required")).not.toBeVisible();
  expect(within(axis).getByText(/请在产品资料中确认实验类型、原始计数语义和计数位置/)).toBeVisible();
});

it("keeps stop accessible while running without silently approving another scope",async()=>{
  const value: Session = {...session,status:"running",assessment:{...assessment,status:"running",stop_reason:null}};
  const fetcher=load(value as typeof session);
  let stopped=false;
  fetcher.mockImplementation(async(input,init)=>{
    const path=String(input);
    if(path==="/api/sessions") return Response.json({sessions:[value]});
    if(path.endsWith("/stop")){
      expect(init?.method).toBe("POST");
      expect(init?.body).toBe("{}");
      stopped=true;
      return Response.json({...session,assessment:{...assessment,stop_reason:"user_stopped"}});
    }
    return Response.json(value);
  });
  render(<App />);
  const button=await screen.findByRole("button",{name:"停止本范围"});
  expect(button).toBeEnabled();
  await userEvent.setup().click(button);
  await waitFor(()=>expect(stopped).toBe(true));
  expect(await screen.findByText(/已由研究者停止/)).toBeInTheDocument();
});

it("retains historical values and original stop reason but disables resume after confirmed correction",async()=>{
  load({...session,assessment:{...assessment,stop_reason:"user_stopped",
    freshness:{...assessment.freshness,state:"historical",reason_code:"input_revision_changed",current_input_revision:4}}});
  render(<App />);
  expect(await screen.findByText(/历史证据：绑定版本 3，当前事实版本 4/)).toBeInTheDocument();
  expect(screen.getByRole("button",{name:"继续本范围"})).toBeDisabled();
  expect(screen.getByText(/已由研究者停止/)).toBeInTheDocument();
  expect(screen.getByText(/选择受影响检查并新建范围/)).toBeInTheDocument();
  expect(within(screen.getByRole("region",{name:"发育阶段"})).getAllByRole("cell",{name:"0.5"})).toHaveLength(1);
});

it("keeps each prior stop phase inspectable after resume without resetting counters",async()=>{
  load({...session,assessment:{...assessment,status:"running",stop_reason:null,stop_events:[
    {reason:"no_discriminating_check",status:"stopped",stopped_at:"2026-09-11T00:00:00Z",
      tool_runs_used:1,model_turns_used:2},
    {reason:"necessary_fact_required",status:"blocked",stopped_at:"2026-09-11T00:01:00Z",
      tool_runs_used:2,model_turns_used:3}]}});
  render(<App />);
  await userEvent.setup().click(await screen.findByText("本范围停止记录"));
  expect(screen.getByText("停止阶段 1")).toBeVisible();
  expect(screen.getByText("停止阶段 2")).toBeVisible();
  expect(screen.getByText(/当时累计：工具 1 次，模型 2 轮/)).toBeVisible();
  expect(screen.getByText(/当时累计：工具 2 次，模型 3 轮/)).toBeVisible();
  expect(screen.getByText(/工具运行：2 \/ 5/)).toBeVisible();
  expect(screen.getByText(/需要研究者提供必要实验事实/)).toBeVisible();
});

it("requires a new scope at exhausted budgets and labels pending correction separately",async()=>{
  load({...session,input_review_required:true,assessment:{...assessment,model_turns_used:8,
    freshness:{...assessment.freshness,state:"review_pending",reason_code:"input_review_required",pending_review:true}}});
  render(<App />);
  expect(await screen.findByText(/事实修改尚待确认；当前结果仍绑定版本 3/)).toBeInTheDocument();
  expect(screen.getByRole("button",{name:"继续本范围"})).toBeDisabled();
  expect(screen.queryByText(/历史证据：/)).not.toBeInTheDocument();
  expect(screen.getByText(/预算已耗尽/)).toBeInTheDocument();
});

it("renders every server-owned axis, denominators, missingness and exact local evidence in the real App seam",async()=>{
  load();
  render(<App />);
  for(const title of ["细胞状态","目标身份","区域身份","发育阶段","全产品与非目标组成","增殖与应激"])
    expect(await screen.findByRole("heading",{name:title})).toBeInTheDocument();
  expect(screen.getByRole("region",{name:"前提条件"})).toBeInTheDocument();
  expect(screen.getByRole("region",{name:"下一步"})).toBeInTheDocument();
  const process=screen.getByRole("region",{name:"增殖与应激"});
  for(const title of titles) expect(within(process).getByText(title)).toBeInTheDocument();
  expect(within(process).getAllByText(/缺少适用的已审阅程序分类映射/)).toHaveLength(6);
  expect(screen.getByText("一个待检验解释")).toBeInTheDocument();
  expect(screen.getByText("另一解释仍然开放")).toBeInTheDocument();
  const development=screen.getByRole("region",{name:"发育阶段"});
  expect(within(development).getByText("whole_product_profile.denominator")).toBeInTheDocument();
  expect(within(development).getByText("target_related_profile.denominator")).toBeInTheDocument();
  expect(within(development).getAllByRole("cell",{name:"4"}).length).toBeGreaterThan(0);
  expect(within(development).getAllByRole("cell",{name:"2"}).length).toBeGreaterThan(0);
  expect(screen.queryByText(/总分|雷达评分|科学评估已完成/)).not.toBeInTheDocument();
  const user=userEvent.setup();
  await user.click(screen.getByText("证据链 E-exact"));
  expect(screen.getByText("receipt-exact")).toBeInTheDocument();
  expect(screen.getByText("artifact-exact")).toBeInTheDocument();
  expect(screen.getByText("dependency-exact")).toBeInTheDocument();
  expect(screen.getByText("graph_version")).toBeInTheDocument();
  await user.click(screen.getByRole("button",{name:"预览 exact-denominators.tsv"}));
  expect(await screen.findByRole("columnheader",{name:"numerator"})).toBeInTheDocument();
  expect(screen.getByRole("link",{name:"Download exact-denominators.tsv"})).toHaveAttribute("href",
    "/api/sessions/session-1/artifacts/bound-table");
});
