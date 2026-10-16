import type { AssessmentMode } from "./types";

export const programSourceNames: Record<string, string> = {
  "HALLMARK_REACTIVE_OXYGEN_SPECIES_PATHWAY": "活性氧相关基因集", "HALLMARK_UNFOLDED_PROTEIN_RESPONSE": "未折叠蛋白反应",
  "HALLMARK_APOPTOSIS": "凋亡相关基因集", "HALLMARK_HYPOXIA": "缺氧相关基因集",
  "HU-2020-TABLE-S1": "多能性相关候选基因集（Hu 2020）",
  "OFLANAGAN-2019-CORE": "解离／热休克相关候选基因集（O’Flanagan 2019）",
};

// Display-only vocabulary. Identifiers in requests, evidence bindings and downloads stay unchanged.
export const scientificGap: Record<string, string> = {
  native_sample_identity_required: "已有结果保留。请在资料表的“样本标识列”中选择并确认对应列；无法确认时保留未知。样本标识不代表生物学独立重复。确认后需重新生成对应的质量检查和细胞状态结果，再继续证据与报告。",
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
export const assessmentModes: Array<AssessmentMode & { label: string; defaultSelected?: boolean }> = [
  { tool_id: "P0-01", mode_id: null, label: "输入与质量检查" },
  { tool_id: "P0-02", mode_id: null, label: "细胞状态" },
  { tool_id: "P0-03", mode_id: "reference_similarity_exploratory", label: "探索性参考相似度分析", defaultSelected: false },
  { tool_id: "P0-03", mode_id: "saved_reference_similarity_projection", label: "整理已保存的参考相似度", defaultSelected: false },
  { tool_id: "P0-03", mode_id: "saved_cell_state_context", label: "目标与区域描述性观察（复用已有结果）", defaultSelected: false },
  { tool_id: "P0-03", mode_id: "default", label: "目标身份与区域" },
  { tool_id: "P0-04", mode_id: "saved_cell_state_context", label: "发育相关描述性观察（复用已有结果）", defaultSelected: false },
  { tool_id: "P0-04", mode_id: "default", label: "发育阶段" },
  { tool_id: "P0-05", mode_id: "saved_cell_state_context", label: "整体候选组成观察（复用已有结果）", defaultSelected: false },
  { tool_id: "P0-05", mode_id: "hard_count_accounting", label: "全产品与非目标组成" },
  { tool_id: "P0-06", mode_id: "exploratory_programs", label: "增殖与应激相关基因表达", defaultSelected: false },
  { tool_id: "P0-06", mode_id: "directed_programs", label: "多能性与解离相关基因表达", defaultSelected: false },
  { tool_id: "P0-06", mode_id: "method_runtime_source_bound", label: "来源绑定的增殖与应激检查" },
  { tool_id: "P0-06", mode_id: "exploratory_process", label: "探索性细胞周期检查" },
  { tool_id: "P0-08", mode_id: "default", label: "检查证据是否充分" },
  { tool_id: "P0-09", mode_id: "case_initial_v2", label: "整理结果依据" },
  { tool_id: "P0-09", mode_id: "case_append_v2", label: "补充结果依据" },
  { tool_id: "P0-09", mode_id: "case_query", label: "查看结果依据" },
  { tool_id: "P0-10", mode_id: "default", label: "核验并生成私有研究报告" },
];
export const modeKey = (mode: AssessmentMode) => mode.tool_id + "/" + (mode.mode_id ?? "");
const reasons: Record<string, string> = {
  ...scientificGap,
  energy_ood_auroc_fold_below_minimum: "参考外样本识别：部分验证划分低于预设要求。",
  energy_ood_auroc_mean_below_minimum: "参考外样本识别：平均表现低于预设要求。",
  energy_ood_fpr95_above_maximum: "参考外样本误接纳率高于预设上限。",
  ood_accepted_fraction_above_maximum: "参考外样本保留比例高于预设上限。",
  reference_count_thinning_unstable: "参考计数深度变化影响结果稳定性。",
  reference_selective_precision_below_minimum: "保留标签的识别准确度低于预设要求。",

  "scientific_resource_required:product_definition_card": "产品评价定义尚未就绪；请补充并确认产品定义后重新核对执行范围。",
  canonical_sufficiency_result_required: "请先检查当前范围的证据是否充分，再整理结果依据。",

  measurement_not_provided: "尚未执行或提供此域测量，不能据此判断该域结果。",
  measurement_unavailable: "测量当前不可用，不能据此推断阴性或产品失败。",
  required_channel_not_provided: "尚未提供所需证据渠道，已有观察不能代替这项证据。",
  required_experiment_not_performed: "尚未开展所需实验。",

  product_upload_required: "请先上传产品数据。",
  assay_declaration_required: "请确认实验类型。",
  raw_count_declaration_required: "请确认原始计数与存放位置。",
  source_family_id_required: "请补充数据来源。",
  completed_qc_required: "请先完成输入与质量检查。",
  input_mode_required: "请选择分析方式。",
  input_not_eligible: "当前输入不满足这项分析的要求。",
  no_graft_declaration_required: "请确认是否有移植后数据。",
  tool_not_successful: "分析未完整完成，已有结果保留。",
  claim_type_policy_missing: "当前声明规则尚未支持缺失性表述",
  unapproved_renderer_requires_review: "当前报告呈现方式尚未获得发布批准",
  asset_declaration_required: "请在产品资料中确认实验类型、原始计数语义和计数位置；不确定时保留未知。",
  supported_product_family_required: "请在完整资料中选择已知产品类别；当前细胞状态参考仅适用于 hPSC 来源的中脑多巴胺能细胞。",
  canonical_case_graph_required: "请先选择已生成的产品证据图，再准备查询。",
  canonical_graph_query_required: "请先选择本范围内的图查询对象。",
  input_or_resource_change: "事实或资源变化时停止。",
  explicit_stop: "研究者可显式停止。",
  finite_budgets: "达到已批准的有限预算时停止。",
  necessary_fact: "缺少必要实验事实时停止并询问。",
  no_scope_evidence: "本范围尚无这一评估轴的已核验证据。",
  reviewed_family_mapping_unavailable: "缺少适用的已审阅程序分类映射；不按程序名称推断。",
  no_discriminating_check: "当前没有可区分解释的后续检查；这不是整体科学结论。",
  interpretation_graph_binding_unavailable: "解释尚未绑定唯一、有效的当前证据图，草稿已保留；补齐证据图后再继续生成解释和报告。",
  completion_contract_unavailable: "缺少适用于整个问题的完成判定合同；不能宣称评估完成。",
  user_stopped: "已由研究者停止；历史结果与原始授权保留。",
  input_revision_changed: "确认后的事实版本已变化。",
  input_review_required: "事实修改仍待核对和确认。",
  scope_resource_changed: "范围绑定的资源已经变化。",
  no_eligible_check: "当前没有满足前提的检查。",
  result_sharing_disabled: "此部署未允许向模型发送结果摘要；保留本地结果。",
  provider_explanation_too_long: "模型解释超过长度限制，未被采纳。可继续本范围，要求更简洁的解释；本轮预算仍计入。",
  provider_action_invalid_or_unavailable: "模型未返回可用动作；已有结果与预算记录已保留。可稍后继续本范围。",
  invalid_evidence_alias: "模型引用了未提供的证据，未继续执行；已有结果仍保留。",
  tool_run_budget_exhausted: "工具运行预算已耗尽，需要新范围。",
  model_turn_budget_exhausted: "模型轮次预算已耗尽，需要新范围。",
  explanation_complete: "本轮解释已结束；不是科学评估完成。",
  report_complete: "私有研究报告已生成并绑定本轮解释；本范围结束，不代表科学资格或公开发布。",
  report_handoff_stale: "解释、证据图或输入绑定已变化；没有生成报告，请新建并确认范围。",
  report_candidate_unavailable: "当前报告候选不满足执行前提；没有调用模型或运行报告，请查看候选阻塞原因。",
  report_handoff_budget_exhausted: "原范围预算不足，未运行报告；需要新范围。",
  necessary_fact_required: "需要研究者提供必要实验事实。",
  native_invalidated_evidence_revision_requires_review: "已有证据已作废；请先复审，当前不能自动追加修订。",
  canonical_graph_inputs_unchanged: "规范图输入未变化，不重复追加同一批证据。",
  measured_claim_binding_required: "测量与声明的精确绑定尚未补齐。",
  cell_cycle_gene_coverage_insufficient: "细胞周期基因覆盖不足，不能给出该测量。",
  program_gene_coverage_insufficient: "程序基因覆盖不足，不能给出该测量。",
  scanpy_signed_signature_not_supported: "该方法不适用于带正负方向的签名。",
  canonical_five_domain_sufficiency_required: "当前充分性结果尚未包含全部五个评估域；需要在授权范围内整理已测结果和缺域，再更新证据图。",
  canonical_graph_domain_coverage_required: "请先更新五个评价方面的证据覆盖情况；当前证据图尚未完整记录，请在已确认的分析中检查证据是否充分并更新结果依据。历史报告仍保留。",
  state_role_review_required: "细胞状态到产品角色的映射仍未审阅；候选标签不能代替已确认角色。",
  regional_definition_review_required: "目标区域与分母定义尚未冻结，当前不能运行正式区域评估。",
  development_state_review_required: "细胞状态到发育阶段的映射仍未审阅。",
  development_window_review_required: "预期发育窗口尚未完成带审阅依据的确认。",
  canonical_source_binding_mismatch: "所选上游结果与真实生产回执不一致；不能替换或改名冒充。",
  scientific_resource_outside_scope: "所需科学资源不在本次已批准范围内；请重新准备范围并确认。",
  scientific_selected_view_mismatch: "科学输入与质量检查不属于同一数据视图。",
  native_sufficiency_binding_invalid: "充分性结果与当前真实测量的来源或域绑定不一致；需重新核对。",
};
export const inputRoles: Record<string, string> = {
  product_case: "产品资料", evidence_records: "证据记录", evidence_sufficiency_profile: "证据充分性结果", evidence_record_set: "证据记录", case_evidence_graph: "产品证据图",
  product_definition_card: "产品定义", state_role_map: "细胞状态与产品角色映射",
  target_regional_assessment_spec: "目标与区域评估规则", measurement_spec: "测量定义",
  development_state_map: "发育状态映射", development_window_spec: "预期发育窗口",
  off_target_assessment_spec: "非目标细胞评估规则", program_spec: "程序定义",
  process_method_spec: "过程测量方法", protocol_ir: "实验方案结构化记录",
  biological_unit_attestation_receipt: "生物学单位确认回执",
  biological_unit_manifest: "生物学单位清单", biological_unit_assignment: "观测与生物学单位对应表",
  qc_readiness_profile: "同一数据视图的质量检查结果", cell_state_evidence_profile: "可供后续产品分析的细胞状态结果",
  annotation_vocabulary: "注释词表", reference_manifest: "参考数据清单",
};
Object.assign(reasons, {
  spatial_link_candidate_analysis_required: "空间联动尚缺同一数据视图的候选注释；需在现有分析范围与预算内补齐。",
  spatial_link_expression_analysis_required: "空间联动尚缺同一数据视图的表达探索结果；需选择表达探索并沿用已有 QC 视图。",
  spatial_link_qc_view_required: "空间联动需先确定并检查产品数据视图。",
  spatial_link_source_verification_required: "空间联动的产物来源暂未核验通过；已有分析结果仍保留。",
});
export function reasonText(code: string) {
  if (reasons[code]) return reasons[code];
  const [kind, role] = code.split(":");
  if (kind === "canonical_source_required" && role === "cell_state_evidence_profile")
    return "请先完成本批数据的细胞状态分析。";
  if (inputRoles[role]) {
    if (kind === "object_required" || kind === "scientific_resource_required") return "请补充并确认：" + inputRoles[role] + "。";
    if (kind === "canonical_source_required") return "请先完成：" + inputRoles[role] + "。";
    if (kind === "canonical_source_ambiguous") return "请选择本次使用的" + inputRoles[role] + "版本。";
  }
  return "请补充本次分析所需的资料。";
}

const toolNames: Record<string, string> = Object.fromEntries(assessmentModes.map(item => [item.tool_id, item.label]));
Object.assign(toolNames, { "P0-06": "增殖与应激", "P0-07": "产品比较", "P0-09": "结果依据整理", "P0-11": "研究报告导出", "P0-12": "移植后证据" });
export const toolName = (id: string) => toolNames[id.toUpperCase()] ?? "专项分析";
export const modeName = (mode: AssessmentMode) => assessmentModes.find(item => modeKey(item) === modeKey(mode))?.label
  ?? (mode.mode_id ? modeNames[mode.mode_id] : undefined) ?? toolName(mode.tool_id);
const modeNames: Record<string, string> = { supplied_evidence: "使用已有证据", default: "标准分析", hard_count_accounting: "细胞组成计数",
  method_runtime_source_bound: "来源绑定的增殖与应激检查", exploratory_process: "探索性细胞周期检查",
  exploratory_programs: "增殖与应激相关基因表达", reference_similarity_exploratory: "探索性参考相似度分析",
  saved_reference_similarity_projection: "整理已保存的参考相似度", saved_cell_state_context: "整理已保存的细胞状态观察",
  case_initial_v2: "整理结果依据", case_append_v2: "补充结果依据", case_query: "查看结果依据" };
export const modeLabel = (id: string) => modeNames[id] ?? "已注册分析方式";
const stateNames: Record<string, string> = {
  not_established: "科学有效性待验证",
  open: "待补证据", satisfied: "已满足", applicable: "适用", partially_applicable: "部分适用", not_applicable: "不适用",
  available: "已有结果", measured: "已测量", missing: "缺少证据", unknown: "未知", unavailable: "不可用",
  negative: "阴性", alert: "警报", not_assessed: "尚未评估", not_estimable: "不可估计", not_available: "尚无结果",
  shadow: "候选测量（未验证）", candidate: "候选", exploratory: "探索性", descriptive_only: "仅作描述",
  proposed: "待批准", approved: "已批准", running: "进行中", thinking: "正在处理", stopping: "正在停止",
  stopped: "已停止", blocked: "受阻", interrupted: "已中断", pending: "待处理", succeeded: "已完成",
  completed: "已完成", failed: "未完成", partial: "部分完成", cancelled: "已取消", skipped: "已跳过",
  idle: "等待下一步", awaiting_approval: "等待批准", ready: "可准备计划", needs_input: "需补充资料",
  not_connected: "尚未接入", not_implemented: "尚未实现", needs_confirmation: "等待确认",
  current: "当前版本", historical: "历史版本", historical_unreviewed: "历史版本（尚未重新核对）",
  review_pending: "等待核对", not_confirmed: "尚未确认", confirmed: "已确认", stale: "相关输入已变化",
  superseded: "已被后续版本替代", invalidated: "已失效", active: "记录有效", retracted: "已撤回",
  release_blocked: "发布受阻", review_required: "仍需审阅", verified: "核验通过",
  verified_with_warnings: "带警告通过核验", not_qualified: "尚无科学资格", candidate_unreviewed: "候选（未审阅）",
  proposed_explanation: "待检验解释", observation: "观测", support: "支持", opposition: "反对",
  missingness: "证据缺失", conflict: "证据冲突", uncertainty: "不确定", prior_only: "仅先验证据",
  inferred: "推断", approved_with_limits: "有限条件下获准", unknown_source: "来源未确定",
};
export const stateName = (state?: string | null) => state ? stateNames[state] ?? "状态待核对" : "尚未提供状态";

// Labels only: values and object/version bindings are never rewritten.
export const domainNames: Record<string, string> = {
  target_identity: "目标身份", regional_fidelity: "区域一致性",
  developmental_compatibility: "发育阶段相容性", off_target_control: "非目标组成",
  proliferation_stress_response: "增殖与应激",
};
export const relationNames: Record<string, string> = {
  supports: "支持", contradicts: "反对", opposes: "反对", missing_for: "尚缺证据",
  derived_from: "来源于", depends_on: "依赖", applicable_to: "适用于",
  belongs_to_evidence_family: "属于同一证据组", supersedes: "取代", invalidates: "使其失效",
};
const metricNames: Record<string, string> = {
  native_s_g2m_fraction: "S / G2M 期细胞比例",
  s_g2m_fraction: "S / G2M 期细胞比例",
  candidate_assignment_fraction: "候选方法保留预测的比例",
  consensus_supported_fraction: "两参考给出相同候选标签的细胞比例",
  source_conflict_fraction: "两参考给出不同候选标签的细胞比例",
  marker_programs_assessed: "所使用的候选 marker 程序卡数量",
};
export function metricName(value: string): string | undefined {
  if (metricNames[value]) return metricNames[value];
  if (/^candidate_composition_fraction_[a-f0-9]{16}$/.test(value)) return "候选组成比例（类别见来源）";
  if (/^native_mean_[a-z0-9_]+$/.test(value)) return "基因集测量均值（方法见来源）";
}
const unitNames: Record<string, string> = {
  fraction: "比例（0–1）", count: "计数", cells: "细胞数",
  scanpy_control_adjusted_expression: "相对背景表达差值",
  decoupler_ulm_t_value: "单变量线性模型 t 值",
};
const fieldNames: Record<string, string> = {
  method_id: "分析方法", program_id: "相关基因集",
  metric_id: "测量名称", metric_name: "测量名称", raw_value: "测量值", value: "数值",
  numerator: "分子", denominator: "分母", unit: "单位", score_unit: "得分单位",
  interval: "区间", lower: "下界", upper: "上界", mean: "均值", median: "中位数",
  fraction: "比例", count: "数量", n_observations: "观测数", n_genes: "基因数",
  domain_id: "评价方面", domain_score: "评价得分", score_state: "得分资格",
  evidence_state: "证据状态", evidence_tier: "证据资格", applicability: "适用性",
  relation: "与判断的关系", scientific_status: "科学状态", state: "状态", status: "状态",
  state_review_status: "状态定义的科学有效性", development_gate_state: "方法开发验证状态",
  development_reason_codes: "方法验证限制", reason_codes: "限制与待补条件", reason_code: "限制与待补条件",
  candidate: "候选方法", candidate_development: "候选方法验证",
  source_family_id: "数据来源", whole_product_profile: "全产品结果", target_related_profile: "目标相关结果",
  role_fractions: "产品角色比例", role: "产品角色", candidate_composition: "候选组成",
  source_label: "来源标签", assignment_state: "预测状态", label: "名称",
  source_gene_set: "基因集来源", source_resource_sha256: "来源资源 SHA256",
  requirement_key: "证据要求", requirements: "待补证据", missingness: "证据缺失情况",
  tool_id: "分析功能", producer_tool_id: "生成分析", execution_state: "执行状态",
  input_revision: "资料版本", graph_version: "证据图版本", object_version: "记录版本",
  evidence_version: "证据版本", lifecycle_state: "原记录状态",
  measurements: "测量记录", observations: "观察记录", records: "记录",
  data_view: "数据范围", view_kind: "数据范围类型", matrix_location: "计数位置",
  matrix_semantics: "矩阵含义", assessment_state: "评估状态", qualification: "科学资格",
};
/** A known researcher-facing name for a data-table column, or null to show the column's own name. */
export function columnLabel(name: string): string | null {
  return Object.hasOwn(fieldNames, name) ? fieldNames[name] : null;
}
export function fieldLabel(path: string): string {
  return path.split(".").map(part => part.replace(/^[A-Za-z][A-Za-z0-9_]*/, key =>
    fieldNames[key] ?? (/^[a-z][a-z0-9]*_[a-z0-9_]+$/.test(key) ? "其他字段" : key))).join(" › ");
}

// Only machine-code contexts use a conservative fallback; arbitrary biology labels are retained.
export function researcherText(text: string): string {
  return text.replace(/多能性样程序/g, "多能性相关").replace(/凋亡相关程序/g, "凋亡相关").replace(/\bP0[-–—]?(\d{2,})(?:\/([a-z][a-z0-9_]*))?/gi,
    (_match, number: string, mode?: string) => mode && modeNames[mode]
      ? toolName("P0-" + number) + " · " + modeNames[mode] : toolName("P0-" + number))
    .replace(/\bP0\b/g, "核心分析")
    .replace(/\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+(?::[a-z][a-z0-9_]*)?\b/g, token => {
      if (modeNames[token]) return modeNames[token];
      if (stateNames[token]) return stateNames[token];
      if (reasons[token] || /_(?:required|unavailable|invalid|mismatch|failed|blocked|pending|exhausted|not_eligible)$/.test(token.split(":")[0])) return reasonText(token);
      return token;
    });
}
export function reasonLabel(value: string, requirementKey?: unknown): string {
  if (value === "required_channel_not_provided" && requirementKey === "independent_validation")
    return "已有观察，但尚缺独立验证；不代表科学资格通过。";
  return /^[a-z][a-z0-9_]*(?::[a-z0-9_]+)*$/.test(value) ? reasonText(value) : researcherText(value);
}
export function fieldValue(value: string, key = ""): string {
  const field = key.replace(/\[\d+\]/g, "").split(".").pop() ?? key;
  if (field === "tool_id" || field === "producer_tool_id") return toolName(value);
  if (field === "mode_id") return modeLabel(value);
  if (field === "method_id") return ({"PROC-SCORE-SCANPY":"Scanpy", "PROC-SCORE-DECOUPLER":"ULM"} as Record<string,string>)[value] ?? "方法名称待核对";
  if (field === "program_id") return ({"S":"S 期", "G2M":"G2/M 期", "PROC-ROS":"氧化应激", "PROC-UPR":"未折叠蛋白反应", "PROC-APOPTOSIS":"凋亡相关", "PROC-HYPOXIA":"缺氧相关", "PROC-PLURIPOTENCY":"多能性相关", "PROC-DISSOCIATION":"解离相关"} as Record<string,string>)[value] ?? "基因集名称待核对";
  if (field === "metric_id" || field === "metric_name") return metricName(value) ?? value;
  if (field === "unit" || field === "score_unit") return unitNames[value] ?? value;
  if (field === "relation" || field === "direction") return relationNames[value] ?? value;
  if (field === "domain_id") return domainNames[value] ?? value;
  if (field === "requirement_key") return value === "independent_validation" ? "独立验证"
    : value === "canonical_measurement" ? "规范测量" : "待核对的证据要求";
  if (field === "applicability") return stateName(value);
  if (field === "reason_code" || field === "reason_codes") return reasonLabel(value);
  if (field === "state" || field === "status" || field.endsWith("_state") || field.endsWith("_status") || field === "qualification" || field === "evidence_tier") {
    if (stateNames[value] || /^[a-z]+(?:_[a-z]+)+$/.test(value)) return stateName(value);
  }
  return researcherText(value);
}
export function displayRecord(value: unknown, key = ""): unknown {
  if (typeof value === "string") return fieldValue(value, key);
  if (Array.isArray(value)) return value.map(item => displayRecord(item, key));
  if (value && typeof value === "object") return Object.fromEntries(Object.entries(value).map(([name, item]) => [name, displayRecord(item, name)]));
  return value;
}

// Source labels describe candidate method outputs, never established cell identities.
export function candidateCompositionName(label: string, assignmentState: string) {
  const states: Record<string, string> = {
    candidate: "候选分配", unknown: "未确定分配", unavailable: "不可用分配",
  };
  const state = states[assignmentState];
  if (!state) return undefined;
  const subject = label === assignmentState && assignmentState !== "candidate"
    ? state : researcherText(label) + "（" + state + "）";
  return "候选组成比例 · " + subject;
}

export const publicLiteratureConcepts: Record<string, string> = {
  human_pluripotent_stem_cell: "人多能干细胞", neural_progenitor: "神经祖细胞",
  neuron: "神经元", midbrain_dopaminergic_neuron: "中脑多巴胺能神经元",
  astrocyte: "星形胶质细胞", oligodendrocyte: "少突胶质细胞",
};

export function conversationName(title?: string) {
  return !title || title === "New analysis" || title === "Untitled analysis" ? "新会话" : title;
}
