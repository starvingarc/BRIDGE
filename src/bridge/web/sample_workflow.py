"""Sample workflow findings: deterministic reasons, never model-invented measurements."""
from copy import deepcopy
import json
import re

from fastapi import HTTPException


# Only these input fields may be requested for resuming the existing basic tools.
INPUT_FIELDS = ["matrix_location", "matrix_semantics", "sample_context", "source_family_id"]
_DETAILS = {
    "mapping_input_required": ("input", "请补充原始计数位置、采样背景和数据来源，才能开始基础分析。", INPUT_FIELDS),
    "raw_counts_must_be_nonnegative_integers": ("input", "声明的矩阵不是非负整数原始计数，请核对原始计数所在层。", ["matrix_location", "matrix_semantics"]),
    "capture_id_incomplete": ("doublet", "捕获批次声明未匹配完整数据，请核对批次列或批次名称。", ["capture_id", "capture_id_column"]),
    "capture_id_not_declared": ("doublet", "双细胞检测需要真实捕获批次；已有基础结果保留。", ["capture_id", "capture_id_column"]),
    "standard_mapping_not_configured": ("mapping", "基础分析可独立完成；参考图谱尚未配置，需要核对后续映射条件。", []),
    "mapping_reference_unavailable": ("mapping", "当前参考不满足该样本的映射条件，请核对参考和采样背景。", []),
    "mapping_tree_mismatch": ("mapping", "参考与当前发育树版本不一致，需要维护者核对资源。", []),
    "mapping_worker_busy": ("execution", "分析资源暂忙，已有数据保留，稍后可继续。", []),
    "research_material_unavailable": ("input", "原始资料未通过完整性检查，请核对资料。", []),
    "mapping_interrupted": ("execution", "分析被中断；已完成结果保留，确认后可重试。", []),
}


def issue(code, step="execution"):
    code = code if isinstance(code, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,99}", code) else "analysis_execution_failed"
    category, message, fields = _DETAILS.get(code, (
        step, "该步骤尚未完成，需结合数据检查结果判断是否补充信息或调整后续分析。", []))
    return {"step": category, "code": code, "message": message, "fields": list(fields)}


def result_issues(owner, rid, aid, *, qc_results, cycle_results, atlas_results, mapping_reason=None):
    """Read verified scientific outputs; keep insufficiency distinct from failure."""
    findings = []
    try:
        _, _, _, outputs, _ = qc_results.capture(owner, rid, aid)
        profiles = [json.loads(content) for metadata, content in outputs.values() if metadata["kind"] == "evidence"]
        doublet = profiles[0]["doublet_assessment"]
        if (doublet["state"] == "not_assessed" and doublet.get("reason") not in {
                "insufficient_cells_for_scrublet", "insufficient_cells_per_capture_for_scrublet"}):
            findings.append(issue(doublet.get("reason", "doublet_not_assessed"), "doublet"))
    except (HTTPException, KeyError, ValueError, IndexError):
        reasons = qc_results.failure_reasons(owner, rid, aid)
        # Downstream steps did not run when input QC failed; report the actual cause.
        return [issue(code, "qc") for code in (reasons or ["qc_result_unavailable"])]
    try:
        _, _, _, _, summary = cycle_results.capture(owner, rid, aid)
        cycle = summary["cell_cycle"]
        if cycle["assessment_state"] != "available":
            findings.extend(issue(code, "cell_cycle") for code in cycle["reason_codes"])
    except (HTTPException, KeyError, ValueError):
        findings.append(issue("cell_cycle_result_unavailable", "cell_cycle"))
    try:
        atlas_results.capture(owner, rid, aid)
    except (HTTPException, KeyError, ValueError):
        reasons = atlas_results.failure_reasons(owner, rid, aid)
        findings.extend(issue(code, "cell_atlas") for code in (reasons or ["cell_atlas_result_unavailable"]))
    if mapping_reason:
        findings.append(issue(mapping_reason, "mapping"))
    return findings


def state_for(issues, attempt_id=None):
    return {"status": ("needs_input" if any(row["fields"] for row in issues) else
                       "needs_review" if issues else "complete"),
            "attempt_id": attempt_id, "issues": deepcopy(issues), "session_id": None,
            "agent_state": "pending" if issues else None}
