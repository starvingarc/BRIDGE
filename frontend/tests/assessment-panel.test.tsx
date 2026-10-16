import { testPrincipal, onTestSignedOut } from "./account-fixture";
import { render, screen, within, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SessionWorkspace from "../src/SessionWorkspace";
import { api } from "../src/api";
import { AssessmentPanel } from "../src/components/AssessmentPanel";
import type { Session, Assessment, AssessmentAxis } from "../src/types";

const missing = (id: string, title: string): AssessmentAxis => ({ id, title, state: "missing",
  reason_codes: ["no_scope_evidence"], evidence_aliases: [], summary: {} });
const titles = ["多能性样程序", "细胞周期", "解离 / 热休克", "氧化应激", "缺氧", "未折叠蛋白反应", "凋亡相关程序"];
const assessment: Assessment = {
  scope_id: "scope-exact", scope_digest: "digest-exact", question: "这批细胞的状态和组成如何？",
  upload_id: "upload-exact", input_revision: 3, report_after_explanation:false,
  max_tool_runs: 5, max_model_turns: 8,
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
  hypotheses:[{qualification:"proposed_explanation",
    interpretation_ref:{scope_digest:"digest-exact",version:1,content_sha256:"a".repeat(64)},
    statement:"一个待检验解释",competing_explanation:"另一解释仍然开放",
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
// Legacy synthetic cases below now receive the same user-facing action envelope as the server.
function presented(value: Session): Session {
  if (value.presentation) return value;
  const a = value.assessment;
  const canResume = a && ["stopped", "blocked", "interrupted"].includes(a.status)
    && a.freshness.state === "current" && !value.input_review_required
    && !a.candidates.some(c => c.tool_id === "P0-10" && c.already_admitted)
    && (a.tool_runs_used ?? 0) < a.max_tool_runs
    && (a.stop_reason === "explanation_complete" || (a.model_turns_used ?? 0) < a.max_model_turns);
  return { ...value, presentation: {
    stage: a?.status === "running" ? "working" : a?.status === "proposed" ? "needs_approval" : "partially_complete",
    stage_label: a?.status === "running" ? "正在处理" : a?.status === "proposed" ? "等待确认评估范围" : "已有部分结果",
    summary: "已有结果可以查看，但当前问题尚未完全解决。",
    issue: a?.stop_reason === "user_stopped" ? { error_version: 1, error_id: "execution_incomplete",
      user_message: "已由研究者停止；已有结果仍保留。", results_state: "preserved" } : null,
    next_actions: a?.status === "proposed" ? [{ id: "approve_assessment", label: "确认评估范围" }]
      : a?.status === "running" ? [{ id: "stop", label: "停止当前工作" }]
      : canResume ? [{ id: "resume_assessment", label: a.report_after_explanation && a.stop_reason === "explanation_complete"
        ? "继续并生成私有研究报告" : "继续本范围" }] : [],
    diagnostics_available: false,
  } };
}
function load(value: Session = session) {
  localStorage.clear();
  return vi.spyOn(globalThis,"fetch").mockImplementation(async(input) => {
    const path=String(input);
    if(path==="/api/sessions") return Response.json({sessions:[value]});
    if(path==="/api/sessions/session-1") return Response.json(presented(value));
    if(path.endsWith("/artifacts/bound-table")) return new Response("numerator\tdenominator\n2\t4");
    throw new Error("Unexpected request: "+path);
  });
}

it("keeps five cards compact, preserves separate scientific states, and resets details for a new scope", async () => {
  const value = presented({...session,assessment:{...assessment,portrait:assessment.portrait.map(axis => axis.id === "target_identity"
    ? {...axis,state:"available",context_evidence_aliases:["E-exact"],reason_codes:[],summary:{channels:[{assessment_state:"not_estimable",target_identity_fraction:null}]}}
    : axis)}});
  const props = {busy:false,onSession:vi.fn(),onError:vi.fn()};
  const {rerender} = render(<AssessmentPanel session={value} {...props}/>);
  const findings = screen.getByRole("region",{name:"工具发现"});
  expect(within(findings).getAllByRole("button")).toHaveLength(5);
  expect(within(findings).queryByText("已有结果")).not.toBeInTheDocument();
  expect(within(findings).queryByText(/分项 1：不可估计/)).not.toBeInTheDocument();
  expect(within(findings).getAllByText("缺少证据").length).toBeGreaterThan(0);
  expect(within(findings).queryByRole("table")).not.toBeInTheDocument();
  for (const title of titles) expect(within(findings).getByText(title.replace("多能性样程序", "多能性相关").replace("凋亡相关程序", "凋亡相关"))).toBeVisible();
  expect(screen.getByText("分析内容").closest("details")).not.toHaveAttribute("open");
  expect(screen.getByText("前提条件与待补充信息").closest("details")).not.toHaveAttribute("open");
  await userEvent.click(within(findings).getByRole("button",{name:"目标与区域"}));
  const details = screen.getByRole("region",{name:"目标与区域详情"});
  expect(details).toHaveFocus();
  expect(within(details).getByText(/分项 1：不可估计/)).not.toBeVisible();
  await userEvent.click(within(details).getByText("方法、数值与限制"));
  expect(within(details).getByText(/分项 1：不可估计/)).toBeVisible();
  expect(within(details).getByRole("region",{name:"目标身份"})).toBeVisible();
  expect(within(details).getByRole("region",{name:"区域身份"})).toBeVisible();
  await userEvent.click(within(details).getByText("目标身份原值与分母"));
  expect(within(details).getByRole("cell",{name:"未提供"})).toBeVisible();
  await userEvent.click(within(details).getByRole("button",{name:"收起详情"}));
  expect(within(findings).getByRole("button",{name:"目标与区域"})).toHaveFocus();
  await userEvent.click(within(findings).getByRole("button",{name:"发育阶段"}));
  rerender(<AssessmentPanel {...props} session={{...value,assessment:{...value.assessment!,scope_digest:"new-scope"}}}/>);
  expect(screen.queryByRole("region",{name:"发育阶段详情"})).not.toBeInTheDocument();
});

it("shows an explicitly unresolved discriminator without inventing a tool", async()=>{
  load({...session,assessment:{...assessment,hypotheses:[{
    statement:"当前图支持有限的候选解释",competing_explanation:"技术状态效应尚未排除",
    discriminating_check:null,evidence_aliases:["E-exact"]}]}});
  render(<SessionWorkspace research={null} researches={[]} onHome={vi.fn()} onAssigned={vi.fn()} principal={testPrincipal} onSignedOut={onTestSignedOut} />);
  await userEvent.click(await screen.findByRole("button", {name: "实验背景"}));
  expect(await screen.findByText("本范围没有合适的科学鉴别检查；仍需后续研究。")).toBeInTheDocument();
  expect(screen.queryByText("已注册的专项检查")).not.toBeInTheDocument();
});

it("names missing scientific inputs for each exact tool without widening scope", async()=>{
  load({...session,assessment:{...assessment,candidates:[
    {tool_id:"P0-03",mode_id:"default",runnable:false,
      blockers:["canonical_source_required:cell_state_evidence_profile"],gaps:[]},
    {tool_id:"P0-04",mode_id:"default",runnable:false,
      blockers:["scientific_resource_required:development_window_spec"],gaps:[]},
    {tool_id:"P0-05",mode_id:"hard_count_accounting",runnable:false,
      blockers:["scientific_resource_required:biological_unit_attestation_receipt"],gaps:[]},
  ]}});
  render(<SessionWorkspace research={null} researches={[]} onHome={vi.fn()} onAssigned={vi.fn()} principal={testPrincipal} onSignedOut={onTestSignedOut} />);
  await userEvent.click(await screen.findByRole("button", {name: "实验背景"}));
  expect(await screen.findByText(/请先完成本批数据的细胞状态分析/)).toBeInTheDocument();
  expect(screen.getByText(/请补充并确认：预期发育窗口/)).toBeInTheDocument();
  expect(screen.getByText(/请补充并确认：生物学单位确认回执/)).toBeInTheDocument();
  expect(screen.queryByText("仍有前提待补齐；请核对输入资料与科学资源。")).not.toBeInTheDocument();
});

it("records an explicit report-after-explanation choice in the proposed scope", async()=>{
  const value: Session = {...session,assessment:null,
    uploads:[{id:"upload-exact",name:"case.h5ad",kind:"h5ad",size:12}]};
  const fetcher=load(value);
  let proposal: unknown = null;
  fetcher.mockImplementation(async(input,init)=>{
    const path=String(input);
    if(path==="/api/sessions") return Response.json({sessions:[value]});
    if(path==="/api/sessions/session-1") return Response.json(presented(value));
    if(path.endsWith("/assessment/propose")){
      proposal=JSON.parse(String(init?.body));
      return Response.json(presented({...value,assessment:{...assessment,report_after_explanation:true,
        status:"proposed",scope_authorized:false}}));
    }
    throw new Error("Unexpected request: "+path);
  });
  render(<SessionWorkspace research={null} researches={[]} onHome={vi.fn()} onAssigned={vi.fn()} principal={testPrincipal} onSignedOut={onTestSignedOut} />);
  await userEvent.click(await screen.findByRole("button", {name: "实验背景"}));
  const user=userEvent.setup();
  await user.click(await screen.findByRole("button",{name:"新建评估范围"}));
  const report=screen.getByRole("checkbox",{name:/解释完成后.*生成私有研究报告/});
  expect(report).not.toBeChecked();
  await user.click(report);
  await user.click(screen.getByRole("checkbox",{name:"目标与区域描述性观察（复用已有结果）"}));
  await user.click(screen.getByRole("button",{name:"准备范围供核对"}));
  await waitFor(()=>expect(proposal).toMatchObject({report_after_explanation:true,
    allowed_modes:expect.arrayContaining([{tool_id:"P0-10",mode_id:"default"}, {tool_id:"P0-03",mode_id:"saved_cell_state_context"}])}));
  expect(await screen.findByText(/完成结果解释后生成研究报告/)).toBeInTheDocument();
});

it("shows each bound program source before approving its separate exact scope", async()=>{
  const value = (scope: string, source?: string): Session => presented({...session,artifacts:[],assessment:{...assessment,
    status:"proposed",scope_authorized:false,scope_id:scope,scope_digest:scope+"-digest",evidence:[],portrait:[],hypotheses:[],resources:[],
    allowed_modes:[{tool_id:"P0-06",mode_id:"directed_programs"}],
    candidates:[{tool_id:"P0-06",mode_id:"directed_programs",runnable:true,blockers:[],gaps:[],
      ...(source ? {source_gene_set:source,source_resource_sha256:"a".repeat(64)} : {})}]}});
  const first=value("pluri-scope","HU-2020-TABLE-S1"), second=value("dissoc-scope","OFLANAGAN-2019-CORE");
  const propose=vi.spyOn(api,"proposeAssessment").mockResolvedValue({...first,plan_history:[],capabilities:[]});
  const approve=vi.spyOn(api,"approveAssessment").mockResolvedValue({...first,plan_history:[],capabilities:[]});
  const props={busy:false,onSession:vi.fn(),onError:vi.fn()};
  const initial=presented({...session,assessment:null,uploads:[{id:"upload-exact",name:"case.h5ad",kind:"h5ad",size:12}]});
  const {rerender}=render(<AssessmentPanel {...props} session={initial}/>);
  const user=userEvent.setup();
  await user.click(screen.getByRole("button",{name:"新建评估范围"}));
  const directed=screen.getByRole("checkbox",{name:"多能性与解离相关基因表达"});
  expect(directed).not.toBeChecked();
  for (const checkbox of screen.getAllByRole("checkbox")) {
    if ((checkbox as HTMLInputElement).checked) await user.click(checkbox);
  }
  await user.click(directed);
  await user.click(screen.getByRole("button",{name:"准备范围供核对"}));
  expect(propose).toHaveBeenCalledWith("session-1",expect.objectContaining({upload_id:"upload-exact",
    allowed_modes:[{tool_id:"P0-06",mode_id:"directed_programs"}]}));
  expect(props.onSession).toHaveBeenCalledWith(expect.objectContaining({assessment:first.assessment}));
  rerender(<AssessmentPanel {...props} session={props.onSession.mock.calls[0][0]}/>);
  const scope=within(screen.getByRole("region",{name:"确认分析内容"}));
  expect(scope.getByText("本范围选定来源：多能性相关候选基因集（Hu 2020）")).toBeVisible();
  expect(scope.queryByText("a".repeat(64))).not.toBeInTheDocument();
  expect(scope.queryByText("绑定资源、数据视图与范围身份")).not.toBeInTheDocument();
  await user.click(scope.getByRole("checkbox"));
  await user.click(scope.getByRole("button",{name:"批准本范围"}));
  expect(approve).toHaveBeenLastCalledWith("session-1","pluri-scope","pluri-scope-digest");
  rerender(<AssessmentPanel {...props} session={second}/>);
  expect(scope.getByText("本范围选定来源：解离／热休克相关候选基因集（O’Flanagan 2019）")).toBeVisible();
  expect(scope.queryByText(/本范围选定来源：多能性/)).not.toBeInTheDocument();
  expect(scope.getByRole("checkbox")).not.toBeChecked();
  expect(scope.getByRole("button",{name:"批准本范围"})).toBeDisabled();
  await user.click(scope.getByRole("checkbox"));
  await user.click(scope.getByRole("button",{name:"批准本范围"}));
  expect(approve).toHaveBeenLastCalledWith("session-1","dissoc-scope","dissoc-scope-digest");
  expect(approve).toHaveBeenCalledTimes(2);
  rerender(<AssessmentPanel {...props} session={value("unknown-scope","UNREGISTERED-CANDIDATE")}/>);
  expect(scope.getByText("本范围选定来源：已选基因集来源")).toBeVisible();
  rerender(<AssessmentPanel {...props} session={value("legacy-scope")}/>);
  expect(scope.queryByText(/本范围选定来源/)).not.toBeInTheDocument();
});

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
      return Response.json(presented({...value,status:"running",assessment:{...value.assessment!,status:"running",scope_authorized:true}}));
    }
    return Response.json(presented(value));
  });
  render(<SessionWorkspace research={null} researches={[]} onHome={vi.fn()} onAssigned={vi.fn()} principal={testPrincipal} onSignedOut={onTestSignedOut} />);
  await userEvent.click(await screen.findByRole("button", {name: "实验背景"}));
  const approval=await screen.findByRole("button",{name:"批准本范围"});
  expect(approval).toBeDisabled();
  expect(screen.queryByText(/工具运行：/)).not.toBeInTheDocument();
  expect(screen.queryByText(/模型轮次：/)).not.toBeInTheDocument();
  expect(screen.getByText(/解释缺口（不阻止本项检查）/)).toBeInTheDocument();
  const consent=screen.getByRole("checkbox",{name:/我已核对分析内容与数据来源/});
  consent.focus();
  const user=userEvent.setup();
  await user.keyboard("[Space]");
  expect(approval).toBeEnabled();
  approval.focus();
  await user.keyboard("[Enter]");
  await waitFor(()=>expect(requests).toEqual([{scope_id:"scope-exact",scope_digest:"digest-exact"}]));
});

it("explains missing intake facts without exposing identifiers in ordinary details", async()=>{
  load({...session,assessment:{...assessment,status:"proposed",scope_authorized:false,
    candidates:[{tool_id:"P0-02",mode_id:null,runnable:false,
      blockers:["asset_declaration_required","supported_product_family_required"],gaps:[]}]}});
  render(<SessionWorkspace research={null} researches={[]} onHome={vi.fn()} onAssigned={vi.fn()} principal={testPrincipal} onSignedOut={onTestSignedOut} />);
  await userEvent.click(await screen.findByRole("button", {name: "实验背景"}));
  const conditions=await screen.findByRole("region",{name:"前提条件"});
  await userEvent.click(within(conditions).getByText("前提条件与待补充信息"));
  expect(within(conditions).getByText(/请在产品资料中确认实验类型、原始计数语义和计数位置/)).toBeVisible();
  expect(within(conditions).getByText(/请在完整资料中选择已知产品类别/)).toBeVisible();
  expect(within(conditions).queryByText("asset_declaration_required")).not.toBeInTheDocument();
  expect(within(conditions).queryByText(/P0-02/)).not.toBeInTheDocument();
  expect(within(conditions).queryByText("开发诊断")).not.toBeInTheDocument();
});

it("explains missing native sample identity in prerequisites without claiming independence", async()=>{
  load({...session,assessment:{...assessment,status:"proposed",scope_authorized:false,
    candidates:[{tool_id:"P0-09",mode_id:"case_initial_v2",runnable:false,
      blockers:["native_sample_identity_required"],gaps:[]}]}});
  render(<SessionWorkspace research={null} researches={[]} onHome={vi.fn()} onAssigned={vi.fn()} principal={testPrincipal} onSignedOut={onTestSignedOut} />);
  await userEvent.click(await screen.findByRole("button", {name: "实验背景"}));
  const conditions=await screen.findByRole("region",{name:"前提条件"});
  await userEvent.click(within(conditions).getByText("前提条件与待补充信息"));
  expect(within(conditions).getByText(/资料表的“样本标识列”/)).toBeVisible();
  expect(within(conditions).getByText(/无法确认时保留未知/)).toBeVisible();
  expect(within(conditions).getByText(/样本标识不代表生物学独立重复/)).toBeVisible();
  expect(within(conditions).queryByText("native_sample_identity_required")).not.toBeInTheDocument();
  expect(within(conditions).queryByText(/仍有前提待补齐/)).not.toBeInTheDocument();
});

it("keeps numeric values and readable reasons without raw codes",async()=>{
  load({...session,assessment:{...assessment,portrait:[{...assessment.portrait[0],state:"available",reason_codes:[],
    summary:{n_observations:4,reason_codes:["asset_declaration_required"]}}]}});
  render(<SessionWorkspace research={null} researches={[]} onHome={vi.fn()} onAssigned={vi.fn()} principal={testPrincipal} onSignedOut={onTestSignedOut} />);
  await userEvent.click(await screen.findByRole("button", {name: "实验背景"}));
  await userEvent.click(await screen.findByRole("button",{name:"细胞状态"}));
  await userEvent.click(screen.getByText("方法、数值与限制"));
  const axis=screen.getByRole("region",{name:"细胞状态"});
  await userEvent.click(within(axis).getByText("细胞状态原值与分母"));
  expect(within(axis).getByRole("cell",{name:"4"})).toBeVisible();
  expect(within(axis).queryByText("asset_declaration_required")).not.toBeInTheDocument();
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
      return Response.json(presented({...session,assessment:{...assessment,stop_reason:"user_stopped"}}));
    }
    return Response.json(presented(value));
  });
  render(<SessionWorkspace research={null} researches={[]} onHome={vi.fn()} onAssigned={vi.fn()} principal={testPrincipal} onSignedOut={onTestSignedOut} />);
  await userEvent.click(await screen.findByRole("button", {name: "实验背景"}));
  const button=await screen.findByRole("button",{name:"停止本范围"});
  expect(button).toBeEnabled();
  await userEvent.setup().click(button);
  await waitFor(()=>expect(stopped).toBe(true));
  expect(await screen.findByText(/已由研究者停止/)).toBeInTheDocument();
});

it("retains historical values and original stop reason but disables resume after confirmed correction",async()=>{
  load({...session,assessment:{...assessment,stop_reason:"user_stopped",
    freshness:{...assessment.freshness,state:"historical",reason_code:"input_revision_changed",current_input_revision:4}}});
  render(<SessionWorkspace research={null} researches={[]} onHome={vi.fn()} onAssigned={vi.fn()} principal={testPrincipal} onSignedOut={onTestSignedOut} />);
  await userEvent.click(await screen.findByRole("button", {name: "实验背景"}));
  expect(await screen.findByText(/历史证据：绑定版本 3，当前事实版本 4/)).toBeInTheDocument();
  expect(screen.queryByRole("button",{name:"继续本范围"})).not.toBeInTheDocument();
  expect(screen.getByText(/已由研究者停止/)).toBeInTheDocument();
  expect(screen.getByText(/选择受影响检查并新建范围/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button",{name:"发育阶段"}));
  await userEvent.click(screen.getByText("发育阶段原值与分母"));
  expect(within(screen.getByRole("region",{name:"发育阶段"})).getAllByRole("cell",{name:"0.5"})).toHaveLength(1);
});

it("does not offer a same-scope retry after a report was admitted",async()=>{
  load({...session,assessment:{...assessment,report_after_explanation:true,status:"blocked",
    stop_reason:"tool_execution_failed",allowed_modes:[{tool_id:"P0-10",mode_id:"default"}],
    candidates:[{tool_id:"P0-10",mode_id:"default",runnable:false,already_admitted:true,
      blockers:[],gaps:[]}]}});
  render(<SessionWorkspace research={null} researches={[]} onHome={vi.fn()} onAssigned={vi.fn()} principal={testPrincipal} onSignedOut={onTestSignedOut} />);
  await userEvent.click(await screen.findByRole("button", {name: "实验背景"}));
  expect(await screen.findByText(/完成结果解释后生成研究报告/)).toBeInTheDocument();
  expect(screen.queryByRole("button",{name:/继续/})).not.toBeInTheDocument();
  expect(screen.queryByText(/回执并新建范围/)).not.toBeInTheDocument();
});

it("shows eligible checks without inventing a continuation action",async()=>{
  load({...session,assessment:{...assessment,report_after_explanation:true,status:"proposed",
    scope_authorized:false,stop_reason:null,allowed_modes:[{tool_id:"P0-10",mode_id:"default"}],
    candidates:[{tool_id:"P0-10",mode_id:"default",runnable:true,blockers:[],gaps:[]}]}});
  render(<SessionWorkspace research={null} researches={[]} onHome={vi.fn()} onAssigned={vi.fn()} principal={testPrincipal} onSignedOut={onTestSignedOut} />);
  await userEvent.click(await screen.findByRole("button", {name: "实验背景"}));
  const prerequisites=await screen.findByRole("region",{name:"前提条件"});
  expect(within(prerequisites).getByText(/前提满足，可在范围内选择/)).toBeInTheDocument();
  expect(screen.queryByRole("button",{name:/继续/})).not.toBeInTheDocument();
});

it("keeps direct report continuation available after the explanation uses the model-turn cap",async()=>{
  load({...session,assessment:{...assessment,report_after_explanation:true,
    stop_reason:"explanation_complete",max_model_turns:3,model_turns_used:3,
    allowed_modes:[{tool_id:"P0-10",mode_id:"default"}],
    candidates:[{tool_id:"P0-10",mode_id:"default",runnable:true,blockers:[],gaps:[]}]}});
  render(<SessionWorkspace research={null} researches={[]} onHome={vi.fn()} onAssigned={vi.fn()} principal={testPrincipal} onSignedOut={onTestSignedOut} />);
  await userEvent.click(await screen.findByRole("button", {name: "实验背景"}));
  const resume=await screen.findByRole("button",{name:"继续并生成私有研究报告"});
  expect(resume).toBeEnabled();
  expect(screen.queryByText(/预算已耗尽；保留原计数/)).not.toBeInTheDocument();
});

it("does not expose diagnostic stop phases or counters in the researcher view",async()=>{
  load({...session,assessment:{...assessment,status:"running",stop_reason:null,stop_events:[
    {reason:"no_discriminating_check",status:"stopped",stopped_at:"2026-09-11T00:00:00Z",
      tool_runs_used:1,model_turns_used:2},
    {reason:"necessary_fact_required",status:"blocked",stopped_at:"2026-09-11T00:01:00Z",
      tool_runs_used:2,model_turns_used:3}]}});
  render(<SessionWorkspace research={null} researches={[]} onHome={vi.fn()} onAssigned={vi.fn()} principal={testPrincipal} onSignedOut={onTestSignedOut} />);
  await userEvent.click(await screen.findByRole("button", {name: "实验背景"}));
  expect(await screen.findByRole("button",{name:"停止本范围"})).toBeEnabled();
  expect(screen.queryByText("本范围停止记录")).not.toBeInTheDocument();
  expect(screen.queryByText(/当时累计|工具运行：|模型轮次：/)).not.toBeInTheDocument();
});

it("requires a new scope at exhausted budgets and labels pending correction separately",async()=>{
  load({...session,input_review_required:true,assessment:{...assessment,model_turns_used:8,
    freshness:{...assessment.freshness,state:"review_pending",reason_code:"input_review_required",pending_review:true}}});
  render(<SessionWorkspace research={null} researches={[]} onHome={vi.fn()} onAssigned={vi.fn()} principal={testPrincipal} onSignedOut={onTestSignedOut} />);
  await userEvent.click(await screen.findByRole("button", {name: "实验背景"}));
  expect(await screen.findByText(/事实修改尚待确认；当前结果仍绑定版本 3/)).toBeInTheDocument();
  expect(screen.queryByRole("button",{name:"继续本范围"})).not.toBeInTheDocument();
  expect(screen.queryByText(/历史证据：/)).not.toBeInTheDocument();
  expect(screen.queryByText(/预算已耗尽/)).not.toBeInTheDocument();
});

it("renders every server-owned axis, denominators, missingness and exact local evidence in the real App seam",async()=>{
  load();
  render(<SessionWorkspace research={null} researches={[]} onHome={vi.fn()} onAssigned={vi.fn()} principal={testPrincipal} onSignedOut={onTestSignedOut} />);
  await userEvent.click(await screen.findByRole("button", {name: "实验背景"}));
  for(const title of ["细胞状态","目标与区域","发育阶段","整体组成","增殖与应激"])
    expect(await screen.findByRole("button",{name:title})).toBeVisible();
  expect(screen.getByText("目标身份")).toBeVisible();
  expect(screen.getByText("区域身份")).toBeVisible();
  await userEvent.click(screen.getByRole("button",{name:"增殖与应激"}));
  expect(screen.getByRole("region",{name:"前提条件"})).toBeInTheDocument();
  expect(screen.getByRole("region",{name:"下一步"})).toBeInTheDocument();
  const process=screen.getByRole("region",{name:"增殖与应激"});
  for(const title of titles) expect(within(process).getByText(title.replace("多能性样程序", "多能性相关").replace("凋亡相关程序", "凋亡相关"))).toBeInTheDocument();
  expect(within(process).getAllByText(/缺少适用的已审阅程序分类映射/)).toHaveLength(6);
  expect(screen.getByText("一个待检验解释")).toBeInTheDocument();
  expect(screen.getByText("另一解释仍然开放")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button",{name:"发育阶段"}));
  const development=screen.getByRole("region",{name:"发育阶段"});
  await userEvent.click(within(development).getByText("发育阶段原值与分母"));
  expect(within(development).getByText("全产品结果 › 分母")).toBeInTheDocument();
  expect(within(development).getByText("目标相关结果 › 分母")).toBeInTheDocument();
  expect(within(development).getAllByRole("cell",{name:"4"}).length).toBeGreaterThan(0);
  expect(within(development).getAllByRole("cell",{name:"2"}).length).toBeGreaterThan(0);
  expect(screen.queryByText(/总分|雷达评分|科学评估已完成/)).not.toBeInTheDocument();
  const user=userEvent.setup();
  await user.click(screen.getByText("发育阶段 · 记录 1"));
  expect(screen.queryByText("receipt-exact")).not.toBeInTheDocument();
  expect(screen.queryByText("artifact-exact")).not.toBeInTheDocument();
  expect(screen.queryByText("dependency-exact")).not.toBeInTheDocument();
  expect(screen.queryByText("graph_version")).not.toBeInTheDocument();
  await user.click(screen.getByRole("button",{name:"查看数据表"}));
  expect(await screen.findByRole("columnheader",{name:/^分子\s*numerator$/})).toBeInTheDocument();
  expect(screen.getByRole("link",{name:"Download exact-denominators.tsv"})).toHaveAttribute("href",
    "/api/sessions/session-1/artifacts/bound-table");
});

it("renders the researcher whitelist without diagnostics and follows server actions and neutral observation references", async () => {
  const projected = JSON.parse(JSON.stringify(assessment));
  for (const key of ["stop_conditions", "stop_reason", "stop_events", "tool_runs_used", "model_turns_used",
    "question_sent_to_model", "result_summaries_enabled", "interpretation_versions"]) delete projected[key];
  delete projected.freshness.reason_code;
  projected.history = [{ scope_id: "prior-scope", question: "先前问题", input_revision: 2, status: "stopped" }];
  projected.hypotheses[0].evidence_aliases = ["E-exact#measurement:M-exact@1"];
  projected.evidence[0].measurements[0].evidence_state = "measured";
  const value: Session = { ...session, assessment: projected, presentation: {
    stage: "results_ready", stage_label: "已有结果", summary: "已有结果可查看；工具完成不等于研究问题已经完全解决。",
    issue: null, next_actions: [{ id: "view_results", label: "查看已有结果" }], diagnostics_available: false,
  } };
  load(value);
  render(<SessionWorkspace research={null} researches={[]} onHome={vi.fn()} onAssigned={vi.fn()} principal={testPrincipal} onSignedOut={onTestSignedOut} />);
  await userEvent.click(await screen.findByRole("button", {name: "实验背景"}));
  expect(await screen.findByText("结果已就绪")).toBeVisible();
  expect(screen.queryByText(/模型轮次|停止阶段|尚无停止原因|此部署未启用结果摘要分享/)).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /继续本范围|批准本范围/ })).not.toBeInTheDocument();
  const user = userEvent.setup();
  await user.click(screen.getByRole("tab", { name: "评估概览" }));
  expect(screen.queryByRole("button", { name: "查看已有结果" })).not.toBeInTheDocument();
  await user.click(screen.getByText("解释与局限"));
  await user.click(screen.getByText("依据、竞争解释与缺口"));
  expect(screen.getByRole("region", { name: "工具发现" })).toBeVisible();
  await user.click(screen.getByRole("link", { name: "来源 1" }));
  expect(screen.queryByText("receipt-exact")).not.toBeInTheDocument();
  expect(screen.getByText("发育阶段 · 记录 1").closest("details")).toHaveAttribute("open");
  expect(screen.getByText("发育阶段 · 记录 1")).toBeVisible();
  expect(screen.queryByRole("heading", { name: "支持证据" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "查看数据表" }));
  expect(await screen.findByRole("columnheader", { name: /^分子\s*numerator$/ })).toBeVisible();
});


it("presents verified missing-only records as gaps and opens their source without relabelling other explanations", async () => {
  const gap: Assessment["hypotheses"][number] = {...assessment.hypotheses[0],
    statement:"缺少适用方法的观测，当前无法回答。",competing_explanation:"方法适用性限制不代表产品异常。",
    evidence_aliases:[],missing_evidence_aliases:["E-exact#requirement:missing-method@1"],opposing_evidence_aliases:[],
    expected_observation:null,discriminating_check:null};
  const current=presented({...session,assessment:{...assessment,hypotheses:[gap]}});
  const props={busy:false,onSession:vi.fn(),onError:vi.fn()};
  const {rerender}=render(<AssessmentPanel {...props} session={current}/>);
  const notes=within(screen.getByRole("region",{name:"证据说明"}));
  expect(notes.getByText(gap.statement)).not.toBeVisible();
  await userEvent.click(notes.getByText("解释与局限"));
  expect(notes.getByRole("heading",{name:"证据缺口说明 · 第 1 版"})).toBeVisible();
  expect(notes.getByText(gap.statement)).toBeVisible();
  expect(notes.getByText(gap.competing_explanation)).not.toBeVisible();
  await userEvent.click(notes.getByText("限制与缺失来源"));
  expect(notes.getByRole("heading",{name:"限制说明"})).toBeVisible();
  expect(notes.getByText(gap.competing_explanation)).toBeVisible();
  expect(notes.queryByRole("heading",{name:/待检验解释|竞争解释|引用的观测与依据/})).not.toBeInTheDocument();
  expect(notes.queryByText(/预期观察：|鉴别检查|区分性检查/)).not.toBeInTheDocument();
  const source=notes.getByRole("link",{name:"来源 1"});
  expect(source).toHaveAttribute("href","#assessment-evidence-E-exact");
  await userEvent.click(source);
  expect(screen.getByText("发育阶段 · 记录 1").closest("details")).toHaveAttribute("open");
  expect(screen.getByText("发育阶段 · 记录 1")).toBeVisible();
  // A record carrying support, opposition, a prediction or a check must not hide those fields as a gap.
  for (const change of [
    {evidence_aliases:["E-exact"]}, {opposing_evidence_aliases:["E-exact"]},
    {expected_observation:"需要检验的预期观察"}, {discriminating_check:"P0-03"},
    {expected_observation:undefined},
  ]) {
    rerender(<AssessmentPanel {...props} session={{...current,assessment:{...current.assessment!,hypotheses:[{...gap,...change}]}}}/>);
    expect(notes.queryByRole("heading",{name:/证据缺口说明/})).not.toBeInTheDocument();
    expect(notes.getByRole("heading",{name:"待检验解释 · 第 1 版"})).toBeVisible();
  }
  rerender(<AssessmentPanel {...props} session={{...current,assessment:{...current.assessment!,hypotheses:[{...gap,provenance_warning:"legacy_unclassified"}]}}}/>);
  expect(notes.queryByRole("heading",{name:/证据缺口说明/})).not.toBeInTheDocument();
  expect(notes.getByText("历史解释（未核验）").closest("details")).not.toHaveAttribute("open");
});

it("labels versioned proposed explanations and preserves unverified history without presenting it as current", async () => {
  load({ ...session, messages: [
    { id: "old-message", role: "assistant", content: "旧对话原文保留", created_at: session.updated_at,
      provenance_warning: "legacy_unclassified" },
    { id: "proposed-message", role: "assistant", content: "带版本的候选解释原文", created_at: session.updated_at,
      qualification: "proposed_explanation", interpretation_ref: { scope_digest: "digest-exact", version: 2, content_sha256: "b".repeat(64) } },
  ], assessment: { ...assessment, hypotheses: [
    { ...assessment.hypotheses[0], statement: "有来源版本的解释原文", interpretation_ref: {
      scope_digest: "digest-exact", version: 2, content_sha256: "b".repeat(64) } },
    { statement: "历史解释原文保留", competing_explanation: "原竞争解释", discriminating_check: null,
      evidence_aliases: ["E-exact"], opposing_evidence_aliases: ["E-exact"], provenance_warning: "legacy_unclassified" },
  ] } });
  render(<SessionWorkspace research={null} researches={[]} onHome={vi.fn()} onAssigned={vi.fn()} principal={testPrincipal} onSignedOut={onTestSignedOut} />);
  await userEvent.click(await screen.findByRole("button", {name: "实验背景"}));
  expect(await screen.findByRole("heading", { name: "待检验解释 · 第 2 版" })).toBeInTheDocument();
  expect(screen.getByText("有来源版本的解释原文")).not.toBeVisible();
  await userEvent.click(screen.getByText("解释与局限"));
  expect(screen.getByText("有来源版本的解释原文")).toBeVisible();
  expect(within(screen.getByRole("region", {name: "证据说明"})).getByText("未验证")).toBeVisible();
  expect(screen.getByText("历史说明 · 来源与事实尚未核验，请勿作为当前结论。")).toBeVisible();
  const message = (await screen.findByText("带版本的候选解释原文")).closest("details")!;
  expect(message).not.toHaveAttribute("open");
  expect(within(message).getByText("未验证")).toBeVisible();
  expect(within(message).getByText("带版本的候选解释原文")).not.toBeVisible();
  await userEvent.click(within(message).getByText("待检验解释 · 第 2 版"));
  expect(within(message).getByText("带版本的候选解释原文")).toBeVisible();
  expect(screen.getByText("旧对话原文保留")).toBeInTheDocument();
  const history = screen.getByText("历史解释（未核验）").closest("details")!;
  expect(history).not.toHaveAttribute("open");
  expect(within(history).getByText("历史解释原文保留")).not.toBeVisible();
  await userEvent.click(within(history).getByText("历史解释（未核验）"));
  expect(within(history).getByText("历史解释原文保留")).toBeVisible();
  await userEvent.click(within(history).getByText("依据、竞争解释与缺口"));
  expect(within(history).getByRole("heading", { name: "原记录标注的反对依据" })).toBeVisible();
});


it("keeps scientific values and sources while removing ordinary internal labels including closed details", async () => {
  load({...session, assessment:{...assessment,
    candidates:[{tool_id:"P0-09", mode_id:"case_initial_v2", runnable:false, gaps:[], blockers:[
      "scientific_resource_required:product_definition_card", "canonical_sufficiency_result_required", "canonical_graph_domain_coverage_required"]}],
    evidence:[{...assessment.evidence[0],
    execution_state:"succeeded", summary:{value:0.5,denominator:4,evidence_state:"negative",tool_id:"P0-04",
      candidate:{state_review_status:"not_established",development_reason_codes:[
        "energy_ood_auroc_fold_below_minimum","energy_ood_auroc_mean_below_minimum","energy_ood_fpr95_above_maximum",
        "ood_accepted_fraction_above_maximum","reference_count_thinning_unstable","reference_selective_precision_below_minimum"]}}}]}});
  const { container } = render(<SessionWorkspace research={null} researches={[]} onHome={vi.fn()} onAssigned={vi.fn()} principal={testPrincipal} onSignedOut={onTestSignedOut} />);
  await userEvent.click(await screen.findByRole("button", {name: "实验背景"}));
  await screen.findByRole("region", {name:"细胞状态与产品评估"});
  expect(container.textContent).not.toMatch(/P0-\d+|scientific_source_review_pending|succeeded|no_scope_evidence|M-exact|artifact-exact|receipt-exact/);
  expect(container.textContent).toContain("0.5");
  expect(container.textContent).toContain("阴性");
  for (const limitation of [
    "科学有效性待验证",
    "参考外样本识别：部分验证划分低于预设要求",
    "参考外样本识别：平均表现低于预设要求",
    "参考外样本误接纳率高于预设上限",
    "参考外样本保留比例高于预设上限",
    "参考计数深度变化影响结果稳定性",
    "保留标签的识别准确度低于预设要求",
  ]) expect(container.textContent).toContain(limitation);
  expect(container.textContent).not.toMatch(/not_established|energy_ood_|ood_accepted_fraction_|reference_count_thinning_unstable|reference_selective_precision_below_minimum/);
  expect(container.textContent).toContain("产品评价定义尚未就绪");
  expect(container.textContent).toContain("请先检查当前范围的证据是否充分");
  expect(container.textContent).toContain("请先更新五个评价方面的证据覆盖情况");
  expect(container.textContent).not.toMatch(/scientific_resource_required|canonical_sufficiency_result_required|canonical_graph_domain_coverage_required/);
});

it("preserves the full record citation when opening a hypothesis in the graph", async () => {
  const citation = "E-exact#record:N-observation@1";
  const openGraph = vi.fn();
  const user = userEvent.setup();
  render(<AssessmentPanel session={presented({...session, assessment:{...assessment,
    hypotheses:[{...assessment.hypotheses[0], evidence_aliases:[citation]}]}})}
    busy={false} onSession={vi.fn()} onError={vi.fn()} onOpenGraph={openGraph} />);
  await user.click(screen.getByText("解释与局限"));
  await user.click(screen.getByText("依据、竞争解释与缺口"));
  await user.click(screen.getByRole("button", {name:"查看关联依据 1"}));
  expect(openGraph).toHaveBeenCalledWith(citation);
});

it("opens details and report directly while keeping the first view compact", async () => {
  const openReports = vi.fn();
  render(<AssessmentPanel session={presented(session)} busy={false} onSession={vi.fn()} onError={vi.fn()} onOpenReports={openReports} />);
  expect(screen.getByText("一个待检验解释")).not.toBeVisible();
  expect(screen.getByText("发育阶段 · 记录 1")).not.toBeVisible();
  await userEvent.click(screen.getByText("解释与局限"));
  expect(screen.getByText("一个待检验解释")).toBeVisible();
  await userEvent.click(screen.getByText("查看来源"));
  expect(screen.getByText("发育阶段 · 记录 1")).toBeVisible();
  await userEvent.click(screen.getByRole("button", {name:"报告"}));
  expect(openReports).toHaveBeenCalledOnce();
});

it("requires explicit public concepts before proposing external literature retrieval", async()=>{
  const initial=presented({...session,assessment:null,uploads:[{id:"upload-exact",name:"case.h5ad",kind:"h5ad",size:12}]});
  const propose=vi.spyOn(api,"proposeAssessment").mockResolvedValue({...initial,plan_history:[],capabilities:[]});
  render(<AssessmentPanel session={initial} busy={false} onSession={vi.fn()} onError={vi.fn()}/>);
  const user=userEvent.setup();
  await user.click(screen.getByRole("button",{name:"新建评估范围"}));
  const retrieval=screen.getByRole("checkbox",{name:"检索公开文献辅助生物学解释"});
  expect(retrieval).not.toBeChecked();
  await user.click(retrieval);
  expect(screen.getByRole("button",{name:"准备范围供核对"})).toBeDisabled();
  await user.click(screen.getByRole("checkbox",{name:"神经祖细胞"}));
  await user.click(screen.getByRole("button",{name:"准备范围供核对"}));
  expect(propose).toHaveBeenCalledWith("session-1",expect.objectContaining({
    literature_enabled:true,literature_concept_refs:["neural_progenitor"]}));
});

it("shows provider correction notices next to the saved abstract", async()=>{
  const withLiterature: Assessment={...assessment,literature:{
    enabled:true,concept_refs:["neuron"],max_searches:1,max_reads:1,searches_used:1,reads_used:1,state:"complete",
    sources:[{source_ref:"literature:epmc-med-12345",url:"https://europepmc.org/article/MED/12345",
      retrieved_at:"2026-10-05T00:00:00Z",content_level:"abstract",abstract:"Synthetic abstract.",
      abstract_sha256:"a".repeat(64),content_sha256:"b".repeat(64),metadata:{
        title:"Synthetic public article",pmid:"12345",doi:null,year:"2024",authors:null,journal:null,
        publication_status:"retraction_or_concern_reported",publication_types:["Retracted Publication"],
        corrections:[{type:"RetractionIn",id:"67890",source:"MED",reference:"Synthetic notice",note:null}]}}]}};
  render(<AssessmentPanel session={presented({...session,assessment:withLiterature})}
    busy={false} onSession={vi.fn()} onError={vi.fn()}/>);
  await userEvent.click(screen.getByText("参考文献 · 已读 1 篇"));
  expect(screen.getByText("来源报告撤稿或关注声明，不应据此确立机制解释。")).toBeVisible();
  expect(screen.getByText(/RetractionIn · MED · 67890 · Synthetic notice/)).toBeVisible();
  expect(screen.getByRole("link",{name:"Synthetic public article"})).toHaveAttribute("href",
    "https://europepmc.org/article/MED/12345");
});


it("keeps the server-authorized report continuation visible after explanations are ready", async () => {
  const value: Session = {...session, assessment: {...assessment,
    report_after_explanation: true, stop_reason: "explanation_complete"}, presentation: {
      stage: "results_ready", stage_label: "已有结果", summary: "解释已保存，等待继续生成报告。",
      issue: null, next_actions: [{id: "view_results", label: "查看已有结果"},
        {id: "resume_assessment", label: "继续已确认的评估"}], diagnostics_available: false,
    }};
  const onSession = vi.fn();
  const resumed = {...value, status: "running" as const, plan_history: [], capabilities: []};
  const resume = vi.spyOn(api, "resumeAssessment").mockResolvedValue(resumed);
  render(<AssessmentPanel session={value} busy={false} onSession={onSession} onError={vi.fn()} />);
  const button = screen.getByRole("button", {name: "继续已确认的评估"});
  expect(button).toBeVisible();
  await userEvent.click(button);
  expect(resume).toHaveBeenCalledWith("session-1", "scope-exact", "digest-exact");
  await waitFor(() => expect(onSession).toHaveBeenCalledWith(resumed));
});


it("shows field-specific repair advice and resumes the same approved scope", async () => {
  const value = presented({...session});
  value.presentation!.issue = {error_version: 1, error_id: "execution_incomplete",
    user_message: "解释核查发现需要修改的内容；本次解释尚未发布。", results_state: "preserved",
    details: ["解释 2 · 主要解释：主要重复了测量数字；请说明生物学含义。",
      "解释 2 · 证据关系：请删除引用记录未支持的推断。"]};
  value.presentation!.next_actions = [{id: "resume_assessment", label: "按意见修订并重新核查"}];
  const resume = vi.spyOn(api, "resumeAssessment").mockResolvedValue({...value, plan_history: [], capabilities: []});
  render(<AssessmentPanel session={value} onSession={vi.fn()} onError={vi.fn()} busy={false} />);
  expect(screen.getByRole("list", {name: "错误与修改意见"})).toHaveTextContent("解释 2 · 主要解释");
  expect(screen.getByText(/请删除引用记录未支持的推断/)).toBeVisible();
  await userEvent.click(screen.getByRole("button", {name: "按意见修订并重新核查"}));
  expect(resume).toHaveBeenCalledWith("session-1", "scope-exact", "digest-exact");
});


it("proposes an exact draft continuation and waits for a separate approval", async () => {
  const source = {scope_id: "scope-exact", scope_digest: "digest-exact", pending_revision_sha256: "a".repeat(64)};
  const proposal = {question: assessment.question, upload_id: assessment.upload_id,
    allowed_modes: assessment.allowed_modes, max_model_turns: 8, max_tool_runs: 3, continuation: source};
  const before = presented({...session, assessment: {...assessment, continuation_proposal: proposal}});
  before.presentation!.next_actions = [];
  const after = presented({...session, assessment: {...assessment, scope_id: "continued-scope",
    scope_digest: "continued-digest", status: "proposed", continuation: source, max_model_turns: 8, max_tool_runs: 3}});
  const propose = vi.spyOn(api, "proposeAssessment").mockResolvedValue({...after, plan_history: [], capabilities: []});
  const approve = vi.spyOn(api, "approveAssessment").mockResolvedValue({...after, plan_history: [], capabilities: []});
  const onError = vi.fn();
  const view = render(<AssessmentPanel session={before} onSession={vi.fn()} onError={onError} busy={false} />);
  await userEvent.click(screen.getByRole("button", {name: "保留修改意见，申请继续额度"}));
  expect(propose).toHaveBeenCalledWith("session-1", proposal);
  expect(approve).not.toHaveBeenCalled();
  view.rerender(<AssessmentPanel session={after} onSession={vi.fn()} onError={onError} busy={false} />);
  expect(screen.getByText(/此次继续最多允许 8 轮模型处理/)).toBeVisible();
  expect(screen.getByRole("button", {name: "批准本范围"})).toBeDisabled();
  await userEvent.click(screen.getByRole("checkbox", {name: "我已核对分析内容与数据来源"}));
  await userEvent.click(screen.getByRole("button", {name: "批准本范围"}));
  expect(approve).toHaveBeenCalledWith("session-1", "continued-scope", "continued-digest");
  expect(onError).not.toHaveBeenCalled();
});
