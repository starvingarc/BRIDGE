from __future__ import annotations

from copy import deepcopy
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .scientific_inputs import digest


Stage = Literal[
    "needs_input",
    "needs_confirmation",
    "needs_approval",
    "working",
    "results_ready",
    "partially_complete",
    "blocked",
    "idle",
]
ActionId = Literal[
    "provide_input",
    "review_inputs",
    "approve_plan",
    "approve_assessment",
    "stop",
    "resume_assessment",
    "view_results",
    "download_report",
]
PublicErrorId = Literal[
    "input_required",
    "confirmation_required",
    "approval_required",
    "execution_incomplete",
    "report_unavailable",
    "request_failed",
]
ResultsState = Literal["preserved", "not_available", "unknown"]
ArtifactContentClass = Literal[
    "research_report",
    "user_result",
    "developer_diagnostic",
]
ArtifactAccessState = Literal[
    "available",
    "current",
    "historical_unreviewed",
    "denied",
]


class PresentationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    error_version: Literal[1] = 1
    error_id: PublicErrorId
    user_message: str
    results_state: ResultsState
    details: list[str] = Field(default_factory=list, max_length=12)


class PresentationAction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: ActionId
    label: str


class SessionPresentation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    stage: Stage
    stage_label: str
    summary: str
    issue: PresentationIssue | None
    next_actions: list[PresentationAction]
    diagnostics_available: bool


class ErrorEnvelope(PresentationIssue):
    pass


_ACTIONS = {
    "provide_input": "补充输入",
    "review_inputs": "核对更正",
    "approve_plan": "确认本次计划",
    "approve_assessment": "确认评估范围",
    "stop": "停止当前工作",
    "resume_assessment": "继续已确认的评估",
    "view_results": "查看已有结果",
    "download_report": "下载当前报告",
}

MODEL_SELECTION_ERRORS = {
    "model_selection_unavailable": "所选模型或服务已不可用，请在对话中重新选择模型，或到设置中检查服务。",
    "model_effort_unavailable": "所选思考强度尚未获当前模型支持，请刷新模型能力，或重新选择思考强度。",
    "model_configuration_changed": "读取期间服务配置已改变，请刷新模型能力后重试。",
}


_EXACT_ERRORS: dict[str, tuple[PublicErrorId, str]] = {
    **{code: ("request_failed", message) for code, message in MODEL_SELECTION_ERRORS.items()},
    "session_archived": ("request_failed", "请先恢复此对话，再修改模型选择。"),
    "research_material_type": ("input_required", "请选择 H5AD、PDF、DOCX、TXT、Markdown、CSV 或 TSV 文件。"),
    "research_material_empty": ("input_required", "文件为空，请选择包含内容的资料。"),
    "research_material_invalid": ("input_required", "资料无法读取或超出解析限制，请检查文件格式与内容。"),
    "research_material_unavailable": ("request_failed", "原始资料校验未通过，请重新添加该文件。"),
    "research_material_too_large": ("input_required", "文件超过上传上限；研究文档上限为 25 MiB，H5AD 使用当前服务器上限。"),
    "research_material_limit": ("request_failed", "本研究已达到 128 份资料的上限。"),
    "research_limit": ("request_failed", "研究数量已达到 256 项上限。"),
    "session_research_already_assigned": ("request_failed", "此会话已经属于另一项研究。"),
    "research_protocol_input_required": ("input_required", "请先选择当前会话中与这份实验方案对应的 H5AD。"),
    "research_metadata_selection_unavailable": ("input_required", "样本表可下载核对，尚未自动合并到分析输入。"),
    "interpretation_revision_budget_insufficient": (
        "execution_incomplete", "修订与重新核查需要两轮模型额度；请保留修改意见，申请继续额度并重新确认。"),
    "interpretation_graph_binding_unavailable": (
        "execution_incomplete", "解释与证据图的对应关系未能核实，本次解释尚未发布。"),
    "report_context_producer_identity_mismatch": (
        "report_unavailable", "测量来源与证据图不一致，本次报告尚未生成；请先核对来源。"),
    "graph_display_unavailable": (
        "request_failed", "解释图叠加层当前不可用，已保存的证据图仍可浏览。"),
    "not_found": ("request_failed", "没有找到请求的内容。"),
    "state_role_review_required": (
        "input_required",
        "还缺少经审阅的目标与非目标细胞判断依据；确认资料不会代替这项审阅。",
    ),
    "authentication_required": ("request_failed", "登录已失效，请重新登录。"),
    "username_unavailable": ("request_failed", "此用户名不可用，请换一个用户名。"),
    "invalid_account": ("request_failed", "用户名需为 3–32 位英文字母、数字、点、下划线或短横线。"),
    "invalid_password": ("request_failed", "密码需为 12–128 位。"),
    "testing_notice_required": ("request_failed", "请先确认内部测试告知。"),
    "too_many_attempts": ("request_failed", "尝试过于频繁，请稍后再试。"),
    "password_change_required": ("request_failed", "请先修改临时密码。"),
    "authentication_failed": ("request_failed", "登录信息不正确。"),
    "invalid_host": ("request_failed", "请求来源不受信任。"),
    "origin_required": ("request_failed", "请求来源不受信任。"),
    "invalid_request": ("request_failed", "请求内容无法处理，请检查后重试。"),
    "request_too_large": ("request_failed", "请求内容过大，未进行处理。"),
    "session_cleanup_failed": ("request_failed", "会话已移出列表，但文件清理尚未完成，请重试删除。"),
    "session_busy": ("execution_incomplete", "当前工作仍在进行，请等待或先停止。"),
    "user_task_limit": ("execution_incomplete", "你已有任务正在执行或排队，请完成后再试。"),
    "storage_quota_exceeded": ("request_failed", "上传累计占用已达到限额，请删除不需要的会话或联系管理员。"),
    "worker_busy": ("execution_incomplete", "当前没有可用执行资源，请稍后再试。"),
    "input_review_required": ("confirmation_required", "输入已有更正，核对确认后才能继续。"),
    "intake_confirmation_required": ("confirmation_required", "请先核对并确认当前资料。"),
    "native_sample_identity_required": (
        "input_required",
        "已有结果保留。请在资料表的“样本标识列”中选择并确认对应列；无法确认时保留未知。"
        "样本标识不代表生物学独立重复。确认后需重新生成对应的质量检查和细胞状态结果，再继续证据与报告。",
    ),
    "supported_product_family_required": (
        "input_required",
        "当前产品类型尚未进入这项分析的支持范围，请先核对产品类型或选择其他分析。",
    ),
    "conditional_selection_not_confirmed": (
        "confirmation_required",
        "这项分析还需要先确认条件输入；确认后才能生成计划。",
    ),
    "approval_not_pending": ("approval_required", "当前计划已变化，请重新查看后确认。"),
    "approval_mismatch": ("approval_required", "当前计划已变化，请重新查看后确认。"),
    "scientific_plan_invalid_or_stale": (
        "approval_required",
        "计划所依据的输入已变化，请重新生成并确认。",
    ),
    "execution_incomplete": (
        "execution_incomplete",
        "这次执行没有完整完成。",
    ),
}

_RESULT_MESSAGES = {
    "execution_incomplete": {
        "preserved": "这次执行没有完整完成；已有结果仍保留。",
        "not_available": "这次执行没有完整完成；当前没有可确认的已有结果。",
        "unknown": "这次执行没有完整完成；已有结果状态暂时无法确认。",
    },
    "report_unavailable": {
        "preserved": "报告未能生成；已有测量和证据仍保留。",
        "not_available": "报告未能生成；当前没有可确认的已有结果。",
        "unknown": "报告未能生成；已有结果状态暂时无法确认。",
    },
}


def _error_identity(internal_code: str | None) -> tuple[PublicErrorId, str]:
    code = internal_code or "request_failed"
    exact = _EXACT_ERRORS.get(code)
    if exact is not None:
        return exact
    if "report" in code:
        return "report_unavailable", ""
    if "approval" in code or code.startswith("plan_"):
        return "approval_required", "当前计划已变化，请重新查看后确认。"
    if "confirmation" in code or "review_required" in code:
        return "confirmation_required", "请先核对并确认当前资料。"
    if code.startswith("input_") or code.endswith("_input_required"):
        return "input_required", "继续前还需要补充必要输入。"
    if (
        "execution" in code
        or "budget_exhausted" in code
        or code.startswith("tool_")
        or code.startswith("model_turn_")
    ):
        return "execution_incomplete", ""
    return "request_failed", "请求未能完成，请稍后重试。"


def public_error(
    internal_code: str | None,
    *,
    results_state: ResultsState,
) -> PresentationIssue:
    if internal_code == "historical_report_acknowledgement_required":
        return PresentationIssue(
            error_id="report_unavailable",
            user_message=(
                "这是一份历史报告，尚未按当前输入和证据重新核对。"
                "请先确认历史版本提示，再下载原始文件。"
            ),
            results_state=results_state,
        )
    error_id, message = _error_identity(internal_code)
    if error_id in _RESULT_MESSAGES and internal_code not in {
        "interpretation_revision_budget_insufficient", "interpretation_graph_binding_unavailable", "report_context_producer_identity_mismatch",
        "session_busy", "worker_busy", "user_task_limit",
    }:
        message = _RESULT_MESSAGES[error_id][results_state]
    return PresentationIssue(
        error_id=error_id,
        user_message=message,
        results_state=results_state,
    )


_REVIEW_FIELDS = {
    "statement": "主要解释", "competing_explanation": "竞争解释",
    "expected_observation": "验证预期", "literature_support": "文献依据", "evidence_relations": "证据关系",
}
_REVIEW_REPAIRS = {
    "unknown_as_absent": "将未提供的信息写成了不存在；请改为未提供或未记录。",
    "aggregate_as_cell_identity": "汇总检测结果不足以证明细胞身份或共表达；请收窄为待验证的表达模式解释。",
    "phase_as_division": "推断的细胞周期阶段不能代表实际分裂或分裂速度；请修正这一推断。",
    "stage_conflation": "混用了谱系指定、分化与功能成熟；请分开说明各阶段及其证据。",
    "unsupported_observation": "包含引用记录未支持的观察或推断；请删除或收窄该说法，不能仅补充保留意见。",
    "literature_overreach": "文献结果或适用范围被扩大；请核对来源，并区分文献背景与本样本证据。",
    "non_discriminating_prediction": "预期结果不能区分竞争解释；请明确各解释支持的结果，以及仍无法区分的情况。",
    "numerical_restatement": "主要重复了测量数字；请说明生物学含义及证据如何支持解释，省略表格已有的数值清单。",
    "missing_validation_design": "缺少验证设计；请补充能区分竞争解释的比较与预期，或说明当前为何无法区分。",
}
_PROVIDER_FAILURE_MESSAGES = {
    "action_protocol": "模型返回格式不符合要求", "action_json": "模型返回内容无法解析",
    "response_json": "模型返回内容无法解析", "action_schema": "模型返回字段未通过校验",
    "transport_timeout": "模型服务响应超时", "transport_error": "模型服务连接失败",
    "http_status": "模型服务返回请求错误", "response_incomplete": "模型返回内容被截断",
    "response_too_large": "模型返回内容超过可处理范围", "response_envelope": "模型服务响应结构无法识别",
    "empty_response": "模型未返回可处理内容", "review_context_limit": "解释核查内容超过处理上限",
}


def _assessment_failure(assessment: dict, results_state: ResultsState):
    """Publish current allowlisted feedback, never rejected draft prose."""
    if (assessment.get("status") != "blocked"
            or assessment.get("stop_reason") != "provider_action_invalid_or_unavailable"):
        return None
    turns = assessment.get("model_turns", [])
    turn = turns[-1] if isinstance(turns, list) and turns else {}
    detail = turn.get("provider_error_detail", {})
    category = detail.get("category")
    is_review = turn.get("phase") == "interpretation_review"
    details = []
    if category == "interpretation_review":
        from .interpretation_review import safe_issues
        for finding in safe_issues(detail.get("issues", [])):
            text = (f"解释 {finding['hypothesis_index'] + 1} · {_REVIEW_FIELDS[finding['field']]}："
                    + _REVIEW_REPAIRS[finding["code"]])
            if text not in details:
                details.append(text)
        message = "解释核查发现需要修改的内容；本次解释尚未发布。"
        action_label = "按意见修订并重新核查"
        scope = assessment.get("scope", {})
        remaining = scope.get("max_model_turns", 2) - assessment.get("model_turns_used", 0)
        if remaining < 2:
            message += "修订和核查至少需要两轮模型额度，当前剩余额度不足；请申请继续额度并重新确认。"
    else:
        phase = "解释核查" if is_review else "解释与分析"
        failure = _PROVIDER_FAILURE_MESSAGES.get(category, "模型返回内容未能完成校验")
        message = f"{phase}未完成：{failure}；已有测量仍保留。"
        details = ["可重新核查已有解释，无需重跑已经完成的测量。" if is_review
                   else "可继续当前评估，系统会保留已完成的测量。"]
        action_label = "重新核查已有解释" if is_review else "继续当前评估"
    return PresentationIssue(error_id="execution_incomplete", user_message=message,
                             results_state=results_state, details=details), action_label


def derive_results_state(state: dict | None) -> ResultsState:
    if not isinstance(state, dict):
        return "unknown"
    if state.get("artifacts"):
        return "preserved"
    assessment = state.get("_assessment")
    if isinstance(assessment, dict):
        if assessment.get("hypotheses"):
            return "preserved"
        if any(
            row.get("state") in {"completed", "succeeded", "partial"}
            for row in assessment.get("admissions", [])
            if isinstance(row, dict)
        ):
            return "preserved"
    return "not_available"


def _action(action_id: ActionId) -> PresentationAction:
    return PresentationAction(id=action_id, label=_ACTIONS[action_id])


def _can_resume(service, state: dict) -> bool:
    try:
        allowed, _ = service.assessment.resume_eligibility(state)
    except (KeyError, OSError, ValueError):
        return False
    return allowed


def _current_report_download_available(state: dict) -> bool:
    return any(
        item.get("content_class") == "research_report"
        and item.get("access_state") == "current"
        for item in state.get("artifacts", [])
        if isinstance(item, dict)
    )


def build_session_presentation(service, state: dict) -> SessionPresentation:
    environment = service.settings.runtime_environment
    diagnostics_available = bool(
        environment == "development" and service.settings.diagnostics_enabled
    )
    status = state.get("status")
    results_state = derive_results_state(state)
    issue = (
        public_error(state.get("error"), results_state=results_state)
        if state.get("error")
        else None
    )

    if status in {"thinking", "running", "stopping"}:
        return SessionPresentation(
            stage="working",
            stage_label="正在处理",
            summary="当前工作仍在进行；可以等待完成，也可以停止。",
            issue=issue,
            next_actions=[_action("stop")],
            diagnostics_available=diagnostics_available,
        )

    if state.get("input_review_required") or state.get("pending_input_change"):
        return SessionPresentation(
            stage="needs_confirmation",
            stage_label="等待核对",
            summary="输入已有更正；确认后，后续计划会使用新版本。",
            issue=issue,
            next_actions=[_action("review_inputs")],
            diagnostics_available=diagnostics_available,
        )

    assessment = state.get("_assessment")
    if (
        isinstance(assessment, dict)
        and assessment.get("status") == "proposed"
        and assessment.get("authorization") is None
    ):
        return SessionPresentation(
            stage="needs_approval",
            stage_label="等待确认评估范围",
            summary="评估问题和范围已经准备好，确认前不会执行。",
            issue=issue,
            next_actions=[_action("approve_assessment")],
            diagnostics_available=diagnostics_available,
        )

    plan = state.get("plan")
    if (
        (isinstance(plan, dict) and plan.get("status") == "proposed")
        or status == "awaiting_approval"
    ):
        return SessionPresentation(
            stage="needs_approval",
            stage_label="等待确认计划",
            summary="本次计划已经准备好，确认前不会运行工具。",
            issue=issue,
            next_actions=[_action("approve_plan")],
            diagnostics_available=diagnostics_available,
        )

    resumable = _can_resume(service, state)
    completed_assessment = (
        isinstance(assessment, dict)
        and assessment.get("stop_reason") in {"explanation_complete", "report_complete"}
        and results_state == "preserved"
    )
    if status == "failed" or (
        isinstance(assessment, dict)
        and assessment.get("status") in {"stopped", "blocked", "interrupted"}
        and not completed_assessment
    ):
        actions: list[PresentationAction] = []
        if results_state == "preserved":
            actions.append(_action("view_results"))
        if resumable:
            actions.append(_action("resume_assessment"))
        producer_mismatch = any(
            "report_context_producer_identity_mismatch" in row.get("reason_codes", [])
            for row in (assessment or {}).get("blockers", []) if isinstance(row, dict)
        )
        if issue is None and producer_mismatch:
            issue = public_error("report_context_producer_identity_mismatch", results_state=results_state)
        if issue is None:
            issue = public_error(
                assessment.get("stop_reason") if isinstance(assessment, dict) else None,
                results_state=results_state,
            )
        feedback = _assessment_failure(assessment, results_state) if isinstance(assessment, dict) else None
        if feedback is not None:
            issue, label = feedback
            actions = [PresentationAction(id=item.id, label=label)
                       if item.id == "resume_assessment" else item for item in actions]
        return SessionPresentation(
            stage="partially_complete" if results_state == "preserved" else "blocked",
            stage_label="已有部分结果" if results_state == "preserved" else "当前未完成",
            summary=(
                "已有结果可以查看，但当前问题尚未完全解决。"
                if results_state == "preserved"
                else "当前问题尚未解决，需要先处理阻塞项。"
            ),
            issue=issue,
            next_actions=actions,
            diagnostics_available=diagnostics_available,
        )

    if results_state == "preserved":
        actions = [_action("view_results")]
        if _current_report_download_available(state):
            actions.append(_action("download_report"))
        if resumable:
            actions.append(_action("resume_assessment"))
        return SessionPresentation(
            stage="results_ready",
            stage_label="已有结果",
            summary="已有结果可查看；工具完成不等于研究问题已经完全解决。",
            issue=issue,
            next_actions=actions,
            diagnostics_available=diagnostics_available,
        )

    if not state.get("uploads"):
        return SessionPresentation(
            stage="needs_input",
            stage_label="等待输入",
            summary="请先提供本次研究要分析的数据。",
            issue=issue,
            next_actions=[_action("provide_input")],
            diagnostics_available=diagnostics_available,
        )

    if issue is not None:
        return SessionPresentation(
            stage="blocked",
            stage_label="当前未完成",
            summary="当前请求尚未完成；已有资料和结果状态会继续保留。",
            issue=issue,
            next_actions=[],
            diagnostics_available=diagnostics_available,
        )

    return SessionPresentation(
        stage="idle",
        stage_label="可以继续",
        summary="当前没有正在运行的工作；可以继续提问或准备下一步。",
        issue=issue,
        next_actions=[],
        diagnostics_available=diagnostics_available,
    )


_ASSESSMENT_FIELDS = (
    "continuation",
    "continuation_proposal",
    "scope_id",
    "scope_digest",
    "question",
    "upload_id",
    "input_revision",
    "allowed_modes",
    "report_after_explanation",
    "literature",
    "max_tool_runs",
    "max_model_turns",
    "status",
    "blockers",
    "evidence",
    "candidates",
    "freshness",
    "portrait",
    "history",
    "hypotheses",
    "data_view",
    "resources",
    "scope_authorized",
    "scope_grants_scientific_approval",
)


def project_user_assessment(value: dict | None) -> dict | None:
    if value is None:
        return None
    projected = {
        key: deepcopy(value[key])
        for key in _ASSESSMENT_FIELDS
        if key in value
    }
    freshness = projected.get("freshness")
    if isinstance(freshness, dict):
        freshness.pop("reason_code", None)
    projected["history"] = [
        {
            key: deepcopy(row[key])
            for key in ("scope_id", "question", "input_revision", "status")
            if key in row
        }
        for row in value.get("history", [])
        if isinstance(row, dict)
    ]
    hypotheses = projected.get("hypotheses")
    if isinstance(hypotheses, list) and hypotheses:
        versions = value.get("interpretation_versions")
        latest = versions[-1] if isinstance(versions, list) and versions else None
        fields = (
            "object_version", "scope_digest", "input_revision", "hypotheses",
            "evidence_snapshot_sha256", "qualification",
        )
        if isinstance(latest, dict) and latest.get("object_version") == "1.1.0":
            fields += ("biological_context", "literature")
        bound = False
        if (
            isinstance(latest, dict)
            and all(field in latest for field in fields)
            and latest["hypotheses"] == hypotheses
            and latest["scope_digest"] == value.get("scope_digest")
            and latest["input_revision"] == value.get("input_revision")
            and latest["qualification"] == "proposed_explanation"
            and type(latest.get("version")) is int
            and latest["version"] > 0
            and isinstance(latest.get("content_sha256"), str)
        ):
            try:
                bound = digest({field: latest[field] for field in fields}) == latest["content_sha256"]
            except (TypeError, ValueError):
                pass
        for hypothesis in hypotheses:
            if not isinstance(hypothesis, dict):
                continue
            for field in ("qualification", "interpretation_ref", "provenance_warning"):
                hypothesis.pop(field, None)
            if bound:
                hypothesis["qualification"] = "proposed_explanation"
                hypothesis["interpretation_ref"] = {
                    "scope_digest": latest["scope_digest"],
                    "version": latest["version"],
                    "content_sha256": latest["content_sha256"],
                }
            else:
                hypothesis["provenance_warning"] = "legacy_unclassified"
    return projected
