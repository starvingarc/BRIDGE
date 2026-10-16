from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from threading import BoundedSemaphore

from fastapi import HTTPException

from bridge.domain import AnalysisPlan
from bridge.runners import ToolExecutionPipeline, ToolExecutionScope
from bridge.storage.private_paths import ensure_private_directory
from bridge.workflow import LocalWorkflowExecutor, SQLiteRunEventStore

from .inputs import verify_checked_file
from .sessions import ID, uid, write_file
from .model_settings import ModelSelectionError


class ProviderUnavailable(RuntimeError):
    pass


class WebExecution:
    """Own worker lifecycle and workflow execution, with explicit collaborators."""

    def __init__(
        self,
        *,
        sessions,
        load_state,
        assessment,
        controls,
        inputs,
        artifacts,
        check_plan,
        message,
        qc_catalog,
        max_upload_bytes,
        task_context=lambda owner, selection: nullcontext(),
        quotas=None,
        after_settle=lambda sid, *, stopped=False: None,
    ):
        self.sessions = sessions
        self.lock = sessions.lock
        self.load = load_state
        self.assessment = assessment
        self.controls = controls
        self.inputs = inputs
        self.artifacts = artifacts
        self.check_plan = check_plan
        self.message = message
        self.qc_catalog = qc_catalog
        self.max_upload_bytes = max_upload_bytes
        self.task_context = task_context
        self.quotas = quotas
        self.after_settle, self.closing = after_settle, False
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="bridge-web")
        self.capacity = BoundedSemaphore(2)
        self._pending = {}
        self.executor = LocalWorkflowExecutor(
            SQLiteRunEventStore(sessions.root / "events.sqlite3"), max_attempts=1
        )

    def pending_status(self, sid):
        # Under the session lock. Future.done() precedes our quota-release callback.
        return next((status for owner, status in self._pending.values() if owner == sid), None)

    def has_pending(self, sid):
        return self.pending_status(sid) is not None

    def shutdown(self):
        self.closing = True
        self.pool.shutdown(wait=True, cancel_futures=False)

    def recover(self):
        for item in self.sessions.root.iterdir():
            if ID.fullmatch(item.name):
                state = self.load(item.name)
                interrupted_handoffs = [row for row in state.get("_sample_handoffs", [])
                                        if row["state"] in {"pending", "preparing", "scheduled"}]
                if interrupted_handoffs or state.get("_sample_workflow_active"):
                    for row in interrupted_handoffs:
                        row["state"] = "unavailable"
                    state.pop("_sample_workflow_active", None)
                    self.sessions.save(state)
                self.sessions.cleanup_uploads(state)
                if state["status"] in {
                    "running",
                    "thinking",
                    "stopping",
                    "awaiting_approval",
                }:
                    state["status"], state["error"] = "failed", "interrupted"
                    self.assessment.stop(state, "restart_interrupted", status="interrupted")
                    if state["plan"] and state["plan"]["status"] in {
                        "proposed",
                        "approved",
                        "cancelled",
                    }:
                        state["plan"]["status"] = "cancelled"
                        for step in state["plan"]["steps"]:
                            if step["status"] in {"pending", "running"}:
                                step["status"], step["reason"] = (
                                    "cancelled",
                                    "interrupted",
                                )
                    if state.get("_run_id"):
                        self.executor.cancel(state["_run_id"])
                    self.sessions.save(state)

    def schedule(self, state, status, work):
        if not self.capacity.acquire(blocking=False):
            raise HTTPException(429, "worker_busy")
        reservation = self.quotas.reserve_task(state["owner_id"]) if self.quotas else nullcontext()
        try:
            reservation.__enter__()
        except BaseException:
            self.capacity.release()
            raise
        previous = (state["_control_epoch"], state["status"], state["error"])
        try:
            context = self.task_context(state.get("owner_id"), state.get("model_selection"))
        except BaseException as error:
            reservation.__exit__(None, None, None)
            self.capacity.release()
            if isinstance(error, ModelSelectionError):
                raise HTTPException(409, error.code) from None
            raise
        state["_control_epoch"] += 1
        epoch = state["_control_epoch"]
        state["status"], state["error"] = status, None
        sid = state["id"]

        def run():
            try:
                with context as configuration:
                    if configuration is not None:
                        with self.lock:
                            current = self.load(sid)
                            current["model_configuration"] = {
                                "base_url": configuration.model_base_url,
                                "model": configuration.model,
                                "version": configuration.model_configuration_id,
                                "provider_id": configuration.model_provider_id,
                                "effort": configuration.model_effort,
                            }
                            self.sessions.save(current)
                    work(sid, epoch)
            except Exception as exc:
                with self.lock:
                    failed = self.load(sid)
                    if failed["_control_epoch"] == epoch:
                        failed["status"] = "failed"
                        self.assessment.stop(failed, "execution_interrupted", status="interrupted")
                        failed["error"] = (
                            (
                                "provider_unavailable"
                                if isinstance(exc, ProviderUnavailable)
                                else "stage_input_construction_failed"
                            )
                            if status == "thinking"
                            else "execution_failed"
                        )
                        if failed["plan"] and status == "running":
                            failed["plan"]["status"] = (
                                "partial"
                                if any(
                                    step["status"] in {"succeeded", "partial"}
                                    for step in failed["plan"]["steps"]
                                )
                                else "failed"
                            )
                            for step in failed["plan"]["steps"]:
                                if step["status"] in {"pending", "running"}:
                                    step["status"], step["reason"] = (
                                        "failed",
                                        "execution_failed",
                                    )
                        self.sessions.save(failed)
            finally:
                # The sole worker owns executor cancellation, after any in-flight
                # tool has released its operation lock. HTTP only fences state.
                with self.lock:
                    current = self.load(sid)
                    stopped = current["_control_epoch"] != epoch
                    run_id = current.get("_run_id") if stopped and status == "running" else None
                if run_id:
                    self.executor.cancel(run_id)
        try:
            self.sessions.save(state)
            future = self.pool.submit(run)
        except BaseException:
            state["_control_epoch"], state["status"], state["error"] = previous
            try:
                self.sessions.save(state)
            finally:
                reservation.__exit__(None, None, None)
                self.capacity.release()
            raise
        self._pending[future] = (sid, status)

        def forget(completed):
            with self.lock:
                try:
                    current = self.load(sid)
                    if current["_control_epoch"] != epoch and current["status"] == "stopping":
                        self.controls.settle(current)
                        self.sessions.save(current)
                finally:
                    self._pending.pop(completed, None)
                    reservation.__exit__(None, None, None)
                    self.capacity.release()
                self.after_settle(sid, stopped=current["_control_epoch"] != epoch)

        future.add_done_callback(forget)

    def execute(self, sid, epoch):
        with self.qc_catalog():
            self._execute(sid, epoch)

    def _execute(self, sid, epoch):
        with self.lock:
            state = self.load(sid)
            if state["_control_epoch"] != epoch or state["input_review_required"]:
                return
            plan = AnalysisPlan.model_validate(state["_plan"])
            if (
                plan.approval_receipt
                and plan.approval_receipt.authorization_kind == "scope_derived"
            ):
                reason = self.assessment.check(state, epoch)
                authorization = state["_assessment"]["authorization"]
                if reason or (
                    plan.approval_receipt.scope_id != authorization["scope_id"]
                    or plan.approval_receipt.scope_sha256 != authorization["scope_sha256"]
                ):
                    self.assessment._finish(
                        state,
                        reason or "scope_authorization_mismatch",
                        status="blocked",
                    )
                    return
            self.check_plan(state, plan)
            self.inputs.verify_plan(state, plan)
            for upload_id, upload in state["_uploads"].items():
                directory, _, _ = ensure_private_directory(self.sessions.directory(sid) / "uploads")
                path = directory / (upload_id + ".h5ad")
                try:
                    verify_checked_file(
                        self.sessions,
                        state,
                        path,
                        upload["sha256"],
                        limit=self.max_upload_bytes,
                    )
                except ValueError as exc:
                    raise ValueError("upload_integrity_mismatch") from exc
            run_id = self.executor.submit(plan)
            state["_run_id"] = run_id
            self.sessions.save(state)
        pipeline = ToolExecutionPipeline(ToolExecutionScope.from_plan(plan))
        while True:
            with self.lock:
                state = self.load(sid)
                if state["_control_epoch"] != epoch or state["input_review_required"]:
                    return
                if plan.approval_receipt.authorization_kind == "scope_derived":
                    reason = self.assessment.check(state, epoch)
                    if reason:
                        self.assessment._finish(state, reason, status="blocked")
                        return
                claim = self.executor.claim_step(run_id)
                if claim is None:
                    break
                for item in state["plan"]["steps"]:
                    if item["id"] == claim.step_id:
                        item["status"] = "running"
                # Capture declaration binding before this exact in-flight step.
                qc_revision = {
                    key: value["declaration_start"] for key, value in state["_uploads"].items()
                }
                self.sessions.save(state)
            outcome = self.executor.execute_claim(claim, pipeline)
            with self.lock:
                state = self.load(sid)
                receipt_id = uid()
                receipt = outcome.model_dump_json().encode()
                write_file(
                    self.sessions.directory(sid) / "receipts" / (receipt_id + ".json"),
                    receipt,
                )
                state["_tool_runs"].append(
                    {
                        "file": receipt_id + ".json",
                        "sha256": hashlib.sha256(receipt).hexdigest(),
                        "tool_id": outcome.request.tool_id,
                        "state": outcome.execution_state.value,
                        "plan_id": plan.plan_id,
                        "declaration_start": (
                            qc_revision.get(outcome.request.assets[0].asset_id)
                            if outcome.request.assets
                            else None
                        ),
                    }
                )
                self.sessions.save(state)
                for item in state["plan"]["steps"]:
                    if item["id"] == claim.step_id:
                        item["status"] = (
                            outcome.execution_state.value
                            if outcome.execution_state.value
                            in {"succeeded", "partial", "cancelled", "blocked"}
                            else "failed"
                        )
                        item["reason"] = (
                            None if item["status"] == "succeeded" else "tool_not_successful"
                        )
                self.sessions.save(state)
                self.inputs.register_outputs(state, outcome, state["_tool_runs"][-1])
                self.artifacts.register(state, outcome)
        with self.lock:
            state = self.load(sid)
            if state["_control_epoch"] != epoch:
                return
            snapshot = self.executor.get_status(run_id)
            success = snapshot.status.value == "succeeded"
            continuing = state.get("_assessment", {}).get("status") == "running"
            state["status"] = ("running" if continuing else "idle") if success else "failed"
            state["error"] = None if success else "execution_incomplete"
            actual = {item["status"] for item in state["plan"]["steps"]}
            state["plan"]["status"] = (
                "completed"
                if success
                else (
                    "partial"
                    if "partial" in actual or "succeeded" in actual
                    else "cancelled"
                    if "cancelled" in actual
                    else "failed"
                )
            )
            self.message(
                state,
                "assistant",
                (
                    "工具运行已结束。请在结果面板查看工具生成的图表和证据。未声明的采样或捕获信息不会被补造；运行完成不代表科学验证通过，不能用于临床或放行结论。"
                    if success
                    else "工具运行未完整完成。未将缺失或失败证据解释为产品失败。"
                ),
                source="deterministic_evidence",
            )
            self.sessions.save(state)
