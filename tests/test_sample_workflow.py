"""User-visible script/agent handoff, recovery and immutable result lineage."""
import json
import time
from dataclasses import replace
import pytest

from fastapi.testclient import TestClient

from account_support import create_test_app, login_test_account
from test_research_atlas_mapping import objects, upload, DECLARATION, resources
from test_research_objects import base, request, sample
from bridge.web.runtime import Settings
from bridge.web.provider import Action


def settings(tmp_path, **options):
    return Settings(storage_root=tmp_path / "store", origin="http://testserver",
                    model_base_url="https://provider.invalid/v1", model="unused", model_api_key="unused", **options)


def wait_workflow(client, rid, sid):
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        current = next(s for s in request(client, "GET", base(rid) + "/workbench")["samples"] if s["id"] == sid)
        workflow = current.get("workflow")
        if workflow and workflow["status"] != "running":
            service = client.app.state.service
            if not service.atlas_mapping.has_pending(sid) and (
                    not current["session_id"] or not service.execution.has_pending(current["session_id"])):
                return current
        time.sleep(.1)
    raise AssertionError("sample workflow did not settle")


def test_missing_declaration_reaches_agent_with_owned_sample_context_without_computing(tmp_path, monkeypatch):
    seen = []
    def converse(config, messages, context):
        seen.append(context)
        return Action(action="reply", text="请补充原始计数所在位置和采样背景，已有资料会保留。")
    monkeypatch.setattr("bridge.web.service.converse", converse)
    with TestClient(create_test_app(settings(tmp_path))) as client:
        login_test_account(client)
        rid, run = objects(client)
        mid = upload(client, rid, tmp_path)
        created = sample(client, rid, run, material_id=mid)
        assert created.get("workflow") is not None
        final = wait_workflow(client, rid, created["id"])
        assert final["workflow"]["status"] == "needs_input"
        assert final["workflow"]["issues"][0]["code"] == "mapping_input_required"
        assert final["assessment_id"] is None
        assert final["session_id"]
        assert len(seen) == 1
        context = seen[0]["sample_workflow_context"]
        assert context["sample_id"] == created["id"]
        assert context["issues"][0]["fields"] == ["matrix_location", "matrix_semantics", "sample_context", "source_family_id"]
        assert all(word not in json.dumps(seen) for word in (str(tmp_path), "private-rg", "private-da"))
        state = request(client, "GET", "/api/sessions/" + final["session_id"])
        assert any("原始计数" in m["content"] for m in state["messages"])
        assert request(client, "GET", base(rid) + f"/samples/{created['id']}/analyses")["analyses"] == []
        # Reads and duplicate delivery cannot consume a new model turn.
        for _ in range(2):
            request(client, "GET", base(rid) + "/workbench")
        assert len(seen) == 1


def test_qc_and_cycle_run_without_mapping_reference_and_agent_failure_keeps_results(tmp_path, monkeypatch):
    seen = []
    def unavailable(*args):
        seen.append(1)
        raise RuntimeError("synthetic provider outage")
    monkeypatch.setattr("bridge.web.service.converse", unavailable)
    with TestClient(create_test_app(settings(tmp_path))) as client:
        login_test_account(client)
        rid, run = objects(client)
        mid = upload(client, rid, tmp_path)
        created = sample(client, rid, run, material_id=mid, mapping_input=DECLARATION)
        assert created.get("workflow") is not None
        final = wait_workflow(client, rid, created["id"])
        rows = request(client, "GET", base(rid) + f"/samples/{created['id']}/analyses")["analyses"]
        assert {r["source_kind"] for r in rows} == {"sample_qc", "sample_cell_cycle"}
        assert all(r["availability"]["status"] == "available" for r in rows)
        assert next(r for r in rows if r["source_kind"] == "sample_qc")["qc_summary"]["schema_integrity"]["n_observations"] == 3
        codes = {i["code"] for i in final["workflow"]["issues"]}
        assert {"standard_mapping_not_configured", "capture_id_not_declared"} <= codes
        assert len(seen) == 1
        assert final["workflow"]["agent_state"] == "unavailable"
        assert request(client, "GET", base(rid) + f"/samples/{created['id']}/analyses")["analyses"] == rows


def test_answer_resumes_tools_and_capture_supplement_keeps_prior_results(tmp_path, monkeypatch):
    monkeypatch.setattr("bridge.web.service.converse", lambda *args: Action(action="reply", text="请核对缺失信息。"))
    with TestClient(create_test_app(settings(tmp_path, **resources(tmp_path)))) as client:
        login_test_account(client)
        rid, run = objects(client)
        mid = upload(client, rid, tmp_path)
        created = sample(client, rid, run, material_id=mid)
        first = wait_workflow(client, rid, created["id"])
        url = base(rid) + f"/samples/{created['id']}/workflow"
        response = client.post(url, json={"expected_version": first["revision"], "mapping_input": DECLARATION})
        assert response.status_code == 200, response.text
        done = wait_workflow(client, rid, created["id"])
        history_url = base(rid) + f"/samples/{created['id']}/analyses"
        old = request(client, "GET", history_url)["analyses"]
        assert len(old) == 3 and done["status"] == "done"
        root = client.app.state.service.researches.directory(rid)
        previous_receipt = root / "atlas-runs" / done["assessment_id"] / "qc-run.json"
        previous_bytes = previous_receipt.read_bytes()
        # Re-submission is idempotent; no extra model call or new analysis attempt.
        same = request(client, "POST", url, {"expected_version": done["revision"], "mapping_input": DECLARATION})
        assert same["assessment_id"] == done["assessment_id"]
        extra = {**DECLARATION, "capture_id": "declared-capture"}
        capacity = client.app.state.service.atlas_mapping.capacity
        assert capacity.acquire(blocking=False)
        try:
            blocked = request(client, "POST", url, {"expected_version": same["revision"], "mapping_input": extra})
            assert blocked["assessment_id"] == done["assessment_id"]
            assert blocked["workflow"]["status"] == "needs_review"
        finally:
            capacity.release()
        started = request(client, "POST", url, {"expected_version": blocked["revision"], "mapping_input": extra})
        assert started["assessment_id"] != done["assessment_id"]
        # The same old request cannot race the new revision.
        request(client, "POST", url, {"expected_version": same["revision"], "mapping_input": extra}, status=409)
        new = wait_workflow(client, rid, created["id"])
        all_rows = request(client, "GET", history_url)["analyses"]
        assert len(all_rows) == 6
        assert all(r["availability"]["status"] == "available" for r in all_rows)
        assert previous_receipt.read_bytes() == previous_bytes
        assert all_rows[:3] == old
        assert new["mapping_input"]["capture_id"] == "declared-capture"
        request(client, "POST", url, {"expected_version": new["revision"],
                "mapping_input": {**extra, "matrix_location": "layers/other"}}, status=422)
        assert request(client, "GET", history_url)["analyses"] == all_rows


def test_invalid_counts_handoff_has_specific_reason_and_corrected_layer_can_resume(tmp_path, monkeypatch):
    import hashlib
    from quick_atlas_support import reference_data
    seen = []
    def review(config, messages, context):
        seen.append(context)
        return Action(action="reply", text="声明的矩阵不满足原始计数要求，请核对原始计数所在层。")
    monkeypatch.setattr("bridge.web.service.converse", review)
    with TestClient(create_test_app(settings(tmp_path))) as client:
        login_test_account(client)
        rid, run = objects(client)
        data = reference_data()[[3, 35, 67]].copy()
        data.layers["counts"] = data.X.copy()
        data.X.data *= .123
        path = tmp_path / "correctable.h5ad"
        data.write_h5ad(path)
        with path.open("rb") as stream:
            mid = client.post(base(rid) + "/uploads", files={"file": (path.name, stream)}).json()["id"]
        original_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        created = sample(client, rid, run, material_id=mid, mapping_input=DECLARATION)
        failed = wait_workflow(client, rid, created["id"])
        codes = {row["code"] for row in failed["workflow"]["issues"]}
        assert "raw_counts_must_be_nonnegative_integers" in codes
        assert len(seen) == 1
        assert request(client, "GET", base(rid) + f"/samples/{created['id']}/analyses")["analyses"] == []
        corrected = {**DECLARATION, "matrix_location": "layers/counts"}
        response = client.post(base(rid) + f"/samples/{created['id']}/workflow",
                               json={"expected_version": failed["revision"], "mapping_input": corrected})
        assert response.status_code == 200, response.text
        final = wait_workflow(client, rid, created["id"])
        rows = request(client, "GET", base(rid) + f"/samples/{created['id']}/analyses")["analyses"]
        assert {r["source_kind"] for r in rows} == {"sample_qc", "sample_cell_cycle"}
        assert final["assessment_id"] != failed["assessment_id"]
        root = client.app.state.service.researches.directory(rid)
        old = json.loads((root / "atlas-runs" / failed["assessment_id"] / "qc-run.json").read_bytes())
        assert old["request"]["assets"][0]["matrix_location"] == "X"
        assert hashlib.sha256((root / "materials" / (mid + ".bin")).read_bytes()).hexdigest() == original_hash


@pytest.mark.parametrize("with_basics", [False, True])
def test_followup_agent_tool_result_returns_only_to_explicit_sample(tmp_path, monkeypatch, with_basics):
    from web_support import declare_counts, settle
    def converse(config, messages, context):
        if messages[-1]["role"] == "user" and "requested recheck" in messages[-1]["content"]:
            return Action(action="prepare_qc", upload_id=context["sample_workflow_context"]["upload_id"], matrix_location="X")
        return Action(action="reply", text="请补充所需输入信息。")
    monkeypatch.setattr("bridge.web.service.converse", converse)
    with TestClient(create_test_app(settings(tmp_path))) as client:
        login_test_account(client)
        rid, run = objects(client)
        mid = upload(client, rid, tmp_path)
        created = sample(client, rid, run, material_id=mid, **({"mapping_input": DECLARATION} if with_basics else {}))
        a = wait_workflow(client, rid, created["id"])
        current_run = next(r for r in request(client, "GET", base(rid) + "/workbench")["runs"] if r["id"] == run["id"])
        other = sample(client, rid, current_run, material_id=mid)
        b = wait_workflow(client, rid, other["id"])
        assert a["session_id"] == b["session_id"]
        sid = a["session_id"]
        session = request(client, "GET", "/api/sessions/" + sid)
        aid = next(u["id"] for u in session["uploads"] if u["material_id"] == mid)
        declare_counts(client, sid, aid)
        response = client.post(f"/api/sessions/{sid}/messages", json={"text": "requested recheck", "sample_id": a["id"]})
        assert response.status_code == 200, response.text
        planned = settle(client, sid)
        assert planned["plan"] is not None, planned
        plan = planned["plan"]
        request(client, "POST", f"/api/sessions/{sid}/approve", {"plan_id": plan["id"], "plan_digest": plan["digest"]})
        settle(client, sid)
        first = request(client, "GET", base(rid) + f"/samples/{a['id']}/analyses")["analyses"]
        second = request(client, "GET", base(rid) + f"/samples/{b['id']}/analyses")["analyses"]
        assert len(first) == (3 if with_basics else 1)
        assert first[-1]["source_kind"] == "session_execution"
        assert all(row["availability"]["status"] == "available" for row in first)
        assert second == []  # Identical data do not imply identical sample intent.


def test_queued_handoff_respects_stop_instead_of_restarting_conversation(tmp_path, monkeypatch):
    from threading import Event
    from web_support import settle
    entered, release = Event(), Event()
    calls = []
    def busy_reply(config, messages, context):
        calls.append(context)
        if len(calls) == 1:
            entered.set()
            assert release.wait(15)
        return Action(action="reply", text="已保留当前记录。")
    monkeypatch.setattr("bridge.web.service.converse", busy_reply)
    with TestClient(create_test_app(settings(tmp_path))) as client:
        login_test_account(client)
        rid, run = objects(client)
        sid = request(client, "POST", base(rid) + f"/runs/{run['id']}/conversation", {})["id"]
        request(client, "POST", f"/api/sessions/{sid}/messages", {"text": "查看记录"})
        assert entered.wait(5)
        try:
            mid = upload(client, rid, tmp_path)
            created = sample(client, rid, run, material_id=mid)
            assert created["workflow"]["agent_state"] == "pending"
            request(client, "POST", f"/api/sessions/{sid}/stop", {})
        finally:
            release.set()
        settle(client, sid)
        assert len(calls) == 1
        current = next(s for s in request(client, "GET", base(rid) + "/workbench")["samples"] if s["id"] == created["id"])
        assert current["workflow"]["agent_state"] == "paused"


def test_restart_recovers_interrupted_sample_without_running_tools_or_model(tmp_path, monkeypatch):
    monkeypatch.setattr("bridge.web.service.converse", lambda *args: Action(action="reply", text="请核对输入。"))
    config = settings(tmp_path)
    with TestClient(create_test_app(config)) as client:
        login_test_account(client)
        rid, run = objects(client)
        mid = upload(client, rid, tmp_path)
        created = sample(client, rid, run, material_id=mid)
        final = wait_workflow(client, rid, created["id"])
        service = client.app.state.service
        owner = service.researches.load(rid)["owner_id"]
        # Simulate a process exit after committing an attempt but before starting its worker.
        aid = service.research_objects.begin_mapping(owner, rid, created["id"], final["revision"], {})
    def unexpected(*args):
        raise AssertionError("restart must not make model calls")
    monkeypatch.setattr("bridge.web.service.converse", unexpected)
    with TestClient(create_test_app(config)) as client:
        login_test_account(client)
        current = next(s for s in request(client, "GET", base(rid) + "/workbench")["samples"] if s["id"] == created["id"])
        assert current["workflow"]["status"] == "needs_review"
        assert current["workflow"]["issues"][0]["code"] == "mapping_interrupted"
        assert current["assessment_id"] == aid
        assert request(client, "GET", base(rid) + f"/samples/{created['id']}/analyses")["analyses"] == []


@pytest.mark.parametrize("n_cells", [48, 240])
def test_complete_basic_pipeline_uses_real_tools_without_a_model_call(tmp_path, monkeypatch, n_cells):
    import anndata as ad
    import numpy as np
    import pandas as pd
    from pathlib import Path
    from quick_atlas_support import reference_data
    import bridge.tool_packages.p0_06_proliferation_stress_response as package
    called = []
    def unexpected(*args):
        called.append(True)
        raise AssertionError("fully declared basic steps do not need a model")
    monkeypatch.setattr("bridge.web.service.converse", unexpected)
    bundle = json.loads((Path(package.__file__).parent / "resources/seurat-cell-cycle-v5.5.1-candidate.json").read_bytes())
    genes = list(dict.fromkeys(bundle["lists"]["s.genes"]["genes"] + bundle["lists"]["g2m.genes"]["genes"] + reference_data().var_names.tolist()))
    genes += ["BACKGROUND_" + str(i) for i in range(1000 - len(genes))]
    rng = np.random.default_rng(42)
    counts = rng.poisson(rng.lognormal(0, 1.3, size=(n_cells, 1000))).astype("float32")
    data = ad.AnnData(counts, obs=pd.DataFrame(index=["synthetic-" + str(i) for i in range(n_cells)]),
                     var=pd.DataFrame(index=genes))
    path = tmp_path / "complete.h5ad"
    data.write_h5ad(path)
    with TestClient(create_test_app(settings(tmp_path, **resources(tmp_path)))) as client:
        login_test_account(client)
        rid, run = objects(client)
        with path.open("rb") as stream:
            result = client.post(base(rid) + "/uploads", files={"file": (path.name, stream)})
        assert result.status_code == 200, result.text
        created = sample(client, rid, run, material_id=result.json()["id"],
                         mapping_input={**DECLARATION, "capture_id": "synthetic-capture"})
        final = wait_workflow(client, rid, created["id"])
        assert final["workflow"]["status"] == "complete", final["workflow"]
        assert final["workflow"]["issues"] == []
        assert final["session_id"] is None
        assert called == []
        rows = request(client, "GET", base(rid) + f"/samples/{created['id']}/analyses")["analyses"]
        assert {r["tool"]["id"] for r in rows} == {"P0-01", "P0-02", "P0-06"}
        cycle = next(r for r in rows if r["tool"]["id"] == "P0-06")
        assert cycle["cell_cycle_summary"]["cell_cycle"]["assessment_state"] == "available"
        qc = next(r for r in rows if r["tool"]["id"] == "P0-01")
        profile = next(r["artifact"] for r in qc["results"] if r["artifact"]["kind"] == "evidence")
        assert client.get(profile["url"]).json()["doublet_assessment"]["state"] == ("candidate" if n_cells >= 100 else "not_assessed")


def test_agent_question_answers_resume_only_bound_sample_and_unknown_stops(tmp_path, monkeypatch):
    from bridge.web.clarification import QuestionSet
    seen = []
    def converse(config, messages, context):
        focus = context["sample_workflow_context"]
        seen.append(focus)
        return Action(action="ask_user_input", questions=QuestionSet(upload_id=focus["upload_id"], questions=[
            {"field": field, "title": field, "reason": "需要核对当前样本声明", "options": options}
            for field, options in [
                ("matrix_location", [{"id": "a", "label": "invented"}, {"id": "b", "label": "invented2"}]),
                ("count_semantics", [{"id": "raw_counts", "label": "原始计数"}, {"id": "not_raw_counts", "label": "非原始计数"}]),
                ("sample_context", [{"id": "pre_graft", "label": "移植前"}, {"id": "post_graft", "label": "移植后"}]),
            ]]))
    monkeypatch.setattr("bridge.web.service.converse", converse)
    with TestClient(create_test_app(settings(tmp_path))) as client:
        login_test_account(client)
        rid, run = objects(client)
        mid = upload(client, rid, tmp_path)
        created = sample(client, rid, run, material_id=mid)
        current = wait_workflow(client, rid, created["id"])
        sid = current["session_id"]
        card = request(client, "GET", "/api/sessions/" + sid)["clarifications"][-1]
        assert card["sample_id"] == created["id"]
        assert card["questions"][0]["options"][0]["label"] == "X"
        answered = request(client, "POST", f"/api/sessions/{sid}/clarification/answer", {
            "card_id": card["id"], "card_digest": card["digest"], "answers": [
                {"field": "matrix_location", "selected": ["choice_0"]},
                {"field": "count_semantics", "selected": ["raw_counts"]},
                {"field": "sample_context", "selected": ["pre_graft"]},
            ]})
        next_card = answered["clarifications"][-1]
        assert next_card["id"] != card["id"]
        assert [q["field"] for q in next_card["questions"]] == ["source_family_id"]
        assert next_card["questions"][0]["options"] == []
        unknown = {"card_id": next_card["id"], "card_digest": next_card["digest"],
                   "answers": [{"field": "source_family_id", "unknown": True}]}
        request(client, "POST", f"/api/sessions/{sid}/clarification/answer", unknown)
        request(client, "POST", f"/api/sessions/{sid}/clarification/answer", unknown)
        assert len(seen) == 1
        assert wait_workflow(client, rid, created["id"])["assessment_id"] is None
        revised = request(client, "POST", f"/api/sessions/{sid}/clarification/revise",
                          {"card_id": next_card["id"], "card_digest": next_card["digest"]})["clarifications"][-1]
        request(client, "POST", f"/api/sessions/{sid}/clarification/answer", {
            "card_id": revised["id"], "card_digest": revised["digest"],
            "answers": [{"field": "source_family_id", "text": "declared-synthetic"}]})
        final = wait_workflow(client, rid, created["id"])
        assert final["mapping_input"]["source_family_id"] == "declared-synthetic"
        rows = request(client, "GET", base(rid) + f"/samples/{created['id']}/analyses")["analyses"]
        assert {r["source_kind"] for r in rows} == {"sample_qc", "sample_cell_cycle"}


def test_sample_question_accepts_negative_count_answer_without_starting_analysis(tmp_path, monkeypatch):
    from bridge.web.clarification import QuestionSet
    def converse(config, messages, context):
        return Action(action="ask_user_input", questions=QuestionSet(
            upload_id=context["sample_workflow_context"]["upload_id"], questions=[{
                "field": "count_semantics", "title": "这是原始计数吗？", "reason": "分析前需要确认",
                "options": [{"id": "raw_counts", "label": "是"}, {"id": "not_raw_counts", "label": "否"}]}]))
    monkeypatch.setattr("bridge.web.service.converse", converse)
    with TestClient(create_test_app(settings(tmp_path))) as client:
        login_test_account(client)
        rid, run = objects(client)
        created = sample(client, rid, run, material_id=upload(client, rid, tmp_path))
        current = wait_workflow(client, rid, created["id"])
        sid = current["session_id"]
        card = request(client, "GET", "/api/sessions/" + sid)["clarifications"][-1]
        answer = request(client, "POST", f"/api/sessions/{sid}/clarification/answer", {
            "card_id": card["id"], "card_digest": card["digest"],
            "answers": [{"field": "count_semantics", "selected": ["not_raw_counts"]}]})
        assert len(answer["clarifications"]) == 1
        assert answer["clarifications"][0]["status"] == "answered"
        assert wait_workflow(client, rid, created["id"])["assessment_id"] is None


def test_late_no_attempt_handoff_cannot_overwrite_new_running_attempt(tmp_path, monkeypatch):
    monkeypatch.setattr("bridge.web.service.converse", lambda *args: Action(action="reply", text="请核对输入。"))
    with TestClient(create_test_app(settings(tmp_path))) as client:
        login_test_account(client)
        rid, run = objects(client)
        created = sample(client, rid, run, material_id=upload(client, rid, tmp_path))
        current = wait_workflow(client, rid, created["id"])
        service = client.app.state.service
        owner = service.researches.load(rid)["owner_id"]
        service.research_objects.begin_mapping(owner, rid, created["id"], current["revision"], {})
        assert service.research_objects.set_sample_workflow(owner, rid, created["id"], current["workflow"], attempt_id=None) is False
        assert service.research_objects.sample(owner, rid, created["id"])["workflow"]["status"] == "running"


def test_stale_queue_entry_does_not_strand_next_sample(tmp_path, monkeypatch):
    from threading import Event
    from web_support import settle
    entered, release = Event(), Event()
    seen = []
    def converse(config, messages, context):
        seen.append(context)
        if len(seen) == 1:
            entered.set()
            assert release.wait(15)
        return Action(action="reply", text="请核对输入。")
    monkeypatch.setattr("bridge.web.service.converse", converse)
    with TestClient(create_test_app(settings(tmp_path))) as client:
        login_test_account(client)
        rid, run = objects(client)
        sid = request(client, "POST", base(rid) + f"/runs/{run['id']}/conversation", {})["id"]
        request(client, "POST", f"/api/sessions/{sid}/messages", {"text": "查看实验记录"})
        assert entered.wait(5)
        try:
            mid = upload(client, rid, tmp_path)
            a = sample(client, rid, run, material_id=mid)
            current_run = next(r for r in request(client, "GET", base(rid) + "/workbench")["runs"] if r["id"] == run["id"])
            b = sample(client, rid, current_run, material_id=mid)
            service = client.app.state.service
            owner = service.researches.load(rid)["owner_id"]
            service.research_objects.set_sample_workflow(owner, rid, a["id"],
                {**a["workflow"], "issues": [], "status": "complete", "agent_state": None})
        finally:
            release.set()
        settle(client, sid)
        final = wait_workflow(client, rid, b["id"])
        assert final["workflow"]["agent_state"] == "delivered"
        assert len(seen) == 2
        assert seen[-1]["sample_workflow_context"]["sample_id"] == b["id"]


@pytest.mark.parametrize("via_message", [False, True])
def test_stop_while_awaiting_approval_pauses_sample_queue(tmp_path, monkeypatch, via_message):
    from web_support import settle, declare_counts
    seen = []
    def converse(config, messages, context):
        seen.append(context)
        if messages[-1]["content"] == "prepare a plan":
            return Action(action="prepare_qc", upload_id=context["upload_ids"][0], matrix_location="X")
        return Action(action="reply", text="已保留记录。")
    monkeypatch.setattr("bridge.web.service.converse", converse)
    with TestClient(create_test_app(settings(tmp_path))) as client:
        login_test_account(client)
        rid, run = objects(client)
        sid = request(client, "POST", base(rid) + f"/runs/{run['id']}/conversation", {})["id"]
        mid = upload(client, rid, tmp_path)
        selected = request(client, "POST", f"/api/sessions/{sid}/research-materials", {"material_id": mid})
        declare_counts(client, sid, selected["uploads"][0]["id"])
        request(client, "POST", f"/api/sessions/{sid}/messages", {"text": "prepare a plan"})
        assert settle(client, sid)["status"] == "awaiting_approval"
        seen.clear()
        created = sample(client, rid, run, material_id=mid)
        assert created["workflow"]["agent_state"] == "pending"
        request(client, "POST", f"/api/sessions/{sid}/" + ("messages" if via_message else "stop"),
                {"text": "停止"} if via_message else {})
        current = next(s for s in request(client, "GET", base(rid) + "/workbench")["samples"] if s["id"] == created["id"])
        assert current["workflow"]["agent_state"] == "paused"
        request(client, "POST", f"/api/sessions/{sid}/messages", {"text": "查看实验记录"})
        settle(client, sid)
        assert len(seen) == 1
        assert "sample_workflow_context" not in seen[0]


def test_question_card_keeps_sample_binding_after_other_sample_handoff(tmp_path, monkeypatch):
    from bridge.web.clarification import QuestionSet
    def converse(config, messages, context):
        return Action(action="ask_user_input", questions=QuestionSet(
            upload_id=context["sample_workflow_context"]["upload_id"], questions=[{
                "field": "matrix_location", "title": "原始计数在哪？", "reason": "需要声明矩阵",
                "options": [{"id": "a", "label": "fabricated-a"}, {"id": "b", "label": "fabricated-b"}]}]))
    monkeypatch.setattr("bridge.web.service.converse", converse)
    with TestClient(create_test_app(settings(tmp_path))) as client:
        login_test_account(client)
        rid, run = objects(client)
        mid = upload(client, rid, tmp_path)
        a = sample(client, rid, run, material_id=mid)
        a = wait_workflow(client, rid, a["id"])
        sid = a["session_id"]
        card = request(client, "GET", "/api/sessions/" + sid)["clarifications"][-1]
        current_run = next(r for r in request(client, "GET", base(rid) + "/workbench")["runs"] if r["id"] == run["id"])
        b = sample(client, rid, current_run, material_id=mid)
        b = wait_workflow(client, rid, b["id"])
        response = request(client, "POST", f"/api/sessions/{sid}/clarification/answer", {
            "card_id": card["id"], "card_digest": card["digest"],
            "answers": [{"field": "matrix_location", "selected": ["choice_0"]}]})
        next_card = response["clarifications"][-1]
        assert next_card["sample_id"] == a["id"]
        service = client.app.state.service
        owner = service.researches.load(rid)["owner_id"]
        assert service.research_objects.sample_answers(owner, rid, a["id"]) == {"matrix_location": "X"}
        assert service.research_objects.sample_answers(owner, rid, b["id"]) == {}
        # A later explicit answer from another surface invalidates the old card.
        updated = service.research_objects.sample(owner, rid, a["id"])
        service.research_objects.save_sample_answers(owner, rid, a["id"], updated["revision"],
                                                     {"matrix_location": "X", "source_family_id": "new-user-answer"})
        request(client, "POST", f"/api/sessions/{sid}/clarification/answer", {
            "card_id": next_card["id"], "card_digest": next_card["digest"],
            "answers": [{"field": q["field"], "unknown": True} for q in next_card["questions"]]}, status=409)
        assert service.research_objects.sample_answers(owner, rid, b["id"]) == {}
