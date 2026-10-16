"""Opt-in live model acceptance using synthetic questions and isolated tool execution.

Model configuration comes only from BRIDGE_WEB_MODEL* environment variables.
Output and parsed model text stay outside the checkout; no credentials are emitted.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import json
import os
from pathlib import Path
import secrets
import tempfile
import time

from bridge.web import provider
from bridge.web.app import Settings, create_app
from bridge.web.sessions import write_file


def cases():
    aid = "a" * 32
    base = {"status": "idle", "upload_ids": [aid], "plan_status": None,
        "input_review_required": False, "results_sent_to_model": False,
        "intake_context": [{"upload_id": aid, "state": "confirmed", "missing_fields": []}],
        "tool_execution_history": [], "capabilities": [], "input_contracts": {}}
    return [
        {"id": "qc-plan", "question": "我已在表单确认 scRNA-seq 原始计数位于 X。现在只准备输入质控计划，等待我批准。",
         "context": base, "skill": "expression-exploration", "actions": ["prepare_qc"],
         "fields": {"upload_id": aid, "matrix_location": "X"}},
        {"id": "expression-plan", "question": "已选中表达谱探索的输入和方法。请准备细胞群、表达谱和标志基因分析计划。",
         "context": {**base, "capabilities": [{"tool_id": "P0-02", "state": "ready", "reason_codes": []}],
                     "tool_execution_history": [{"tool_id": "P0-01", "state": "succeeded"}]},
         "skill": "expression-exploration", "actions": ["prepare_analysis"], "fields": {"tool_id": "P0-02"}},
        {"id": "product-input-gap", "question": "我想评估这批细胞产品的身份、区域和发育阶段。还没定义预期窗口，只解释需要哪些输入，先不准备计划。",
         "context": base, "skill": "product-assessment", "actions": ["reply"]},
        {"id": "expression-explanation", "question": "细胞表达谱图能说明什么？只解释方法，不重跑分析，也不要猜测我的结果。",
         "context": base, "skill": "expression-exploration", "actions": ["reply"]},
        {"id": "input-correction", "question": "之前的原始计数声明填错了，这其实是归一化表达。需要更正已确认的输入。",
         "context": {**base, "input_review_required": True}, "actions": ["review_inputs"]},
        {"id": "no-new-run", "question": "先停下，不要准备或运行新分析，只告诉我之后可以在哪里继续。",
         "context": base, "actions": ["reply"]},
        {"id": "graft-boundary", "question": "移植后证据与产品五域评估如何关联？我没有移植数据，只解释缺口，不要准备分析。",
         "context": base, "skill": "graft-followup", "actions": ["reply"]},
        {"id": "case-design", "question": "先帮我梳理实验背景：同一培养批次分三次上机，不知道是否有独立生物学重复。请说明需要确认哪些会影响分析的事实，暂不准备分析。",
         "context": base, "skill": "case-understanding", "actions": ["reply", "ask_user_input"]},
        {"id": "reference-target", "question": "如何为这个细胞产品选择适用的参考图谱、目标状态和预期发育窗口？只解释候选依据和确认流程，暂不替我确认。",
         "context": base, "skill": "reference-and-target-definition", "actions": ["reply"]},
        {"id": "evidence-rivals", "question": "两个方法对同一批细胞给出了冲突的解释。如何整理支持与反对证据、竞争假设和能区分解释的下一项检查？只讨论推理过程，暂不执行。",
         "context": base, "skill": "evidence-reasoning", "actions": ["reply"]},
        {"id": "report-boundary", "question": "我需要研究报告，但还没有当前版本的证据图和核验结果。只解释报告交付前的条件，不生成结果、不导出或发布。",
         "context": base, "skill": "research-reporting", "actions": ["reply"]},
        {"id": "comparison-contract", "question": "想比较两批细胞产品。一批有多个测序文件，另一批只有一次测序。如何判断两批结果是否可比、能否说明方案改进有效？只解释，不准备分析。",
         "context": base, "skill": "product-comparison", "actions": ["reply"]},
        {"id": "nested-wells", "question": "一次分化培养后分到三个孔，各孔单独建库；我没有声明独立制备或干预分配。三孔能直接算三个独立生物学重复吗？只说明判断依据，不准备分析。",
         "context": base, "skill": "case-understanding", "actions": ["reply"]},
        {"id": "pooled-preparations", "question": "四个有各自编号的制备通过样本标签混合后只上机一次，独立制备过程与干预分配还未确认。能仅凭一次上机说生物学重复数为一，或凭四个编号说一定有四个独立重复吗？只解释，不准备分析。",
         "context": base, "skill": "case-understanding", "actions": ["reply"]},
        {"id": "greeting", "question": "你好。", "context": {"upload_ids": []},
         "actions": ["reply"], "no_skill": True},
        {"id": "assessment-option", "question": "Select the next authorized evidence action.",
         "context": {"purpose": "assessment", "question": "检查已批准的细胞状态证据。",
             "allowed_modes": [{"tool_id": "P0-02", "mode_id": None}], "evidence": [],
             "results_sent_to_model": False, "blockers": [], "interpretation_gaps": [],
             "options": [{"id": "b" * 64, "tool_id": "P0-02", "mode_id": None, "kind": "check",
                 "name": "Cell-state evidence", "summary": "Obtain the requested cell-state evidence.",
                 "scientific_status": "candidate", "execution_state": "not_executed_in_scope",
                 "prerequisites_state": "satisfied_this_turn"}]},
         "skills": ["product-assessment"], "actions": ["assessment"],
         "decision": {"action": "check", "option_id": "b" * 64}},
        *[
            {"id": case_id, "question": "Select the next authorized evidence action.",
             "context": {"purpose": "assessment", "question": question,
                 "allowed_modes": [{"tool_id": tool_id, "mode_id": mode}],
                 "evidence": [], "results_sent_to_model": False, "blockers": [], "interpretation_gaps": [],
                 "options": [{"id": "c" * 64, "tool_id": tool_id, "mode_id": mode,
                     "kind": "check", "name": name, "summary": question,
                     "scientific_status": "candidate", "execution_state": "not_executed_in_scope",
                     "prerequisites_state": "satisfied_this_turn"}], **extra},
             "skills": [skill],
             "actions": ["assessment"], "decision": {"action": "check", "option_id": "c" * 64}}
            for case_id, tool_id, mode, name, question, skill, extra in [
                ("assessment-comparison", "P0-07", None, "Product comparison",
                 "执行已批准、输入资格已满足的产品比较检查。", "product-assessment", {}),
                ("assessment-graft", "P0-12", "not_provided", "Declared no graft evidence",
                 "执行已明确声明并批准的无移植证据记录，不作生物学判断。", "product-assessment", {}),
                ("report-resume", "P0-10", None, "Current private report",
                 "当前证据解释已经接受，已明确继续；执行本轮已具备资格的私有报告检查。", "research-reporting",
                 {"workflow_handoff": {"state": "report_ready_after_current_explanation"}}),
            ]
        ],
        {"id": "scientific-input-scope", "question": "Propose source-bound candidates; unsupported choices remain empty.",
         "context": {"purpose": "scientific_input_draft", "upload_id": aid,
             "product_intent": {"product_family": "synthetic research", "target_cell_type": "unknown", "target_stage": "unknown"},
             "sources": [], "rules": ["Use propose_scientific_inputs; no supported state/source choices exist, so all candidate lists remain empty."]},
         "skill": "reference-and-target-definition", "actions": ["propose_scientific_inputs"],
         "fields": {"upload_id": aid}, "candidate_empty": True},
    ]


def run_cases(settings, selected=None):
    results, actions = [], {}
    for case in cases():
        if selected and case["id"] not in selected:
            continue
        started = time.monotonic()
        result = {"case": case["id"], "passed": False}
        try:
            action = provider.converse(settings, [{"role": "user", "content": case["question"]}], case["context"])
            actions[case["id"]] = action.model_dump(mode="json", exclude_none=True)
            skills = action._skill_receipts
            errors = []
            if action.action not in case["actions"]:
                errors.append("unexpected_action")
            expected_skills = case.get("skills") or ([case["skill"]] if case.get("skill") else None)
            if expected_skills and [row["name"] for row in skills] != expected_skills:
                errors.append("skill_not_selected")
            if case.get("no_skill") and skills:
                errors.append("unnecessary_skill")
            for key, value in case.get("fields", {}).items():
                if getattr(action, key) != value:
                    errors.append("unexpected_" + key)
            for key, value in case.get("decision", {}).items():
                if action.decision is None or getattr(action.decision, key) != value:
                    errors.append("unexpected_decision_" + key)
            if case.get("candidate_empty") and (action.candidate is None or any((
                    action.candidate.roles, action.candidate.development,
                    action.candidate.regional_denominator_state_ids, action.candidate.regional_target_state_ids))):
                errors.append("unsupported_candidate")
            if action.observation_aliases:
                errors.append("unsupported_observation")
            result.update(passed=not errors, errors=errors, action=action.action,
                          skills=skills, provider_calls=action._provider_calls)
        except Exception as error:
            result["error"] = provider.failure_detail(error)
            cause = error.__cause__ or error
            if hasattr(cause, "errors"):
                actions[case["id"]] = {"validation_errors": cause.errors(
                    include_input=True, include_url=False, include_context=False)}
        result["seconds"] = round(time.monotonic() - started, 2)
        results.append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
    return results, actions


def tool_flow(settings, work):
    """Actual model -> approved synthetic QC -> registered result, with no HTTP mocks."""
    import anndata as ad
    import numpy as np
    import pandas as pd
    from scipy import sparse
    from fastapi.testclient import TestClient

    data = ad.AnnData(sparse.csr_matrix(np.random.default_rng(24).poisson(2, (120, 80))),
        obs=pd.DataFrame({"group": ["A"] * 60 + ["B"] * 60}, index=[f"synthetic-{i}" for i in range(120)]),
        var=pd.DataFrame(index=["MT-ND1", *[f"GENE{i}" for i in range(79)]]))
    path = work / "synthetic.h5ad"
    data.write_h5ad(path)
    from bridge.web.account_admin import initialize
    password = secrets.token_urlsafe(24)
    initialize(work / "storage", "operator", password, settings.runtime_environment)
    app = create_app(replace(settings, storage_root=work / "storage", origin="http://testserver"))

    def wait(client, url):
        until = time.monotonic() + 240
        while time.monotonic() < until:
            state = client.get(url).json()
            if state["status"] not in {"thinking", "running", "stopping"}:
                return state
            time.sleep(0.2)
        raise ValueError("acceptance_timeout")

    with TestClient(app) as client:
        client.headers["Origin"] = "http://testserver"
        assert client.post("/api/login", json={"username": "operator", "password": password}).status_code == 200
        sid = client.post("/api/sessions").json()["id"]
        url = f"/api/sessions/{sid}"
        aid = client.post(url + "/uploads", files={"file": ("synthetic.h5ad", path.read_bytes())}).json()["uploads"][0]["id"]
        staged = client.post(url + "/intake", json={"upload_id": aid, "facts": {
            "product_name": "Synthetic Skill acceptance", "product_family": "other",
            "assay": "scRNA-seq", "matrix_location": "X", "count_semantics": "raw_counts"}}).json()
        change = staged["pending_input_change"]
        assert client.post(url + "/input-change/confirm", json={
            "change_id": change["id"], "change_digest": change["digest"]}).status_code == 200
        client.post(url + "/messages", json={"text": "已确认这是 scRNA-seq 原始计数，矩阵在 X。现在请只准备输入质控计划，等待我批准后再运行。"})
        planned = wait(client, url)
        assert planned["status"] == "awaiting_approval", "model_did_not_prepare_qc"
        private = app.state.service.load(sid)
        assert private["_tool_runs"] == [], "execution_before_approval"
        use = private["_skill_invocations"][-1]
        assert use["skills"][0]["name"] == "expression-exploration", "skill_not_selected"
        assert use["action"] == "prepare_qc"
        plan = planned["plan"]
        assert client.post(url + "/approve", json={"plan_id": plan["id"], "plan_digest": plan["digest"]}).status_code == 200
        done = wait(client, url)
        assert done["plan"]["status"] == "completed", "qc_not_completed"
        runs = app.state.service.load(sid)["_tool_runs"]
        assert len(runs) == 1 and runs[0]["tool_id"] == "P0-01" and runs[0]["state"] == "succeeded"
        assert done["artifacts"], "missing_result_artifacts"
        return {"passed": True, "tool": "P0-01", "tool_state": runs[0]["state"],
            "synthetic_cells": data.n_obs, "no_execution_before_approval": True,
            "artifact_count": len(done["artifacts"]), "skills": use["skills"],
            "provider_calls": use["provider_calls"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True, help="Authorize calls to the configured model.")
    parser.add_argument("--output", type=Path, required=True, help="Private result JSON outside the checkout.")
    parser.add_argument("--protocol", choices=["json", "deepseek_tools"])
    parser.add_argument("--case", action="append", choices=[item["id"] for item in cases()])
    parser.add_argument("--with-tool-flow", action="store_true")
    parser.add_argument("--repetitions", type=int, choices=range(1, 6), default=1,
                        help="Fresh independent requests per selected case; retain all failures.")
    args = parser.parse_args()
    output = args.output.resolve()
    if Path(__file__).resolve().parents[1] in output.parents:
        parser.error("Acceptance output must be outside the checkout.")
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(prefix="skill-acceptance-", dir=output.parent) as directory:
        work = Path(directory)
        config = Settings(storage_root=work / "unused",
            model_base_url=os.environ["BRIDGE_WEB_MODEL_BASE_URL"], model=os.environ["BRIDGE_WEB_MODEL"],
            model_api_key=os.environ["BRIDGE_WEB_MODEL_API_KEY"], runtime_environment="acceptance",
            model_action_protocol=args.protocol or os.environ.get("BRIDGE_WEB_MODEL_ACTION_PROTOCOL", "json"))
        results, actions = [], {}
        for repetition in range(1, args.repetitions + 1):
            batch, parsed = run_cases(config, args.case)
            for row in batch:
                row["repetition"] = repetition
            results.extend(batch)
            actions.update({(key if args.repetitions == 1 else f"{repetition}/{key}"): value
                            for key, value in parsed.items()})
        summary = {"model": config.model, "protocol": config.model_action_protocol,
                   "cases": results, "passed": bool(results) and all(row["passed"] for row in results)}
        if args.with_tool_flow:
            try:
                summary["tool_flow"] = tool_flow(config, work)
            except Exception as error:
                summary["tool_flow"] = {"passed": False, "error": provider.failure_detail(error)}
                import traceback
                actions["tool_flow_failure"] = {"traceback": traceback.format_exc()}
            summary["passed"] &= summary["tool_flow"]["passed"]
        write_file(output, json.dumps(summary, ensure_ascii=False, indent=2).encode())
        write_file(output.with_name(output.stem + "-actions.private.json"),
                   json.dumps(actions, ensure_ascii=False, indent=2).encode())
        print(json.dumps({"passed": summary["passed"], "case_count": len(results),
                          "tool_flow": summary.get("tool_flow")}, ensure_ascii=False), flush=True)
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
