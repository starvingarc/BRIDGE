"""Private scope-bound admission and one-worker evidence feedback."""
from __future__ import annotations

from datetime import datetime, timezone
from importlib.resources import files
import hashlib
import json
import secrets
from typing import Literal

from fastapi import HTTPException
from pydantic import Field, StrictInt, model_validator

from bridge.domain.models import AnalysisPlan, PlanApprovalReceipt
from bridge.toolkit.contracts import FrozenModel
from .inputs import InputBody, checked_bytes
from .scientific_inputs import digest


class AllowedMode(InputBody):
    tool_id: Literal["P0-01", "P0-02", "P0-03", "P0-04", "P0-05", "P0-06", "P0-08", "P0-09"]
    mode_id: str | None = Field(max_length=100)


class ScopeProposal(InputBody):
    question: str = Field(min_length=1, max_length=2000)
    upload_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    allowed_modes: list[AllowedMode] = Field(min_length=1, max_length=16)
    max_tool_runs: StrictInt = Field(ge=1, le=32)
    max_model_turns: StrictInt = Field(ge=1, le=64)

    @model_validator(mode="after")
    def unique_modes(self):
        keys = [(row.tool_id, row.mode_id) for row in self.allowed_modes]
        if len(keys) != len(set(keys)) or not self.question.strip():
            raise ValueError("invalid_assessment_scope")
        if any(row.mode_id and ("comparison" in row.mode_id or "graft" in row.mode_id) for row in self.allowed_modes):
            raise ValueError("separate_branch_approval_required")
        return self


class ScopeIdentity(InputBody):
    scope_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    scope_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class AssessmentScope(FrozenModel):
    scope_id: str
    session_id: str
    question: str
    upload_id: str
    input_revision: int
    allowed_modes: tuple[AllowedMode, ...]
    max_tool_runs: int
    max_model_turns: int
    binding: dict


class AssessmentCoordinator:
    def __init__(self, service):
        self.service = service

    def _binding(self, state, upload_id, resource_ids, allowed_modes, *, approved_binding=None):
        """Read the exact facts/resources without promoting any review state."""
        upload = state["_uploads"].get(upload_id)
        intake = state.get("_intakes", {}).get(upload_id)
        if not upload or not intake or intake["signature"] != self.service.intake.signature(state, upload_id):
            raise ValueError("intake_confirmation_required")
        checked_bytes(self.service, state,
            self.service.directory(state["id"]) / "uploads" / (upload_id + ".h5ad"),
            upload["sha256"], limit=self.service.settings.upload_limit)
        records = {}
        for identifier in resource_ids:
            record = state["_input_objects"].get(identifier)
            if record is None:
                raise ValueError("scope_resource_missing")
            self.service.inputs.verify(state, record)
            records[identifier] = record
        resources = files("bridge.tool_packages.p0_02_cell_state.resources")
        science = {name: hashlib.sha256(resources.joinpath(name).read_bytes()).hexdigest()
                   for name in ("biological_review_draft.yaml", "product_context_review_draft.yaml")}
        if any(row.tool_id == "P0-06" and row.mode_id == "exploratory_process" for row in allowed_modes):
            _, candidate = self.service.scientific_inputs.exploratory_resource()
            science[candidate["resource_ref"]] = candidate["sha256"]
        try:
            _, references = self.service.inputs.reference_resources(state)
            reference = {"state": "available", "resources": references}
        except (ValueError, OSError, KeyError):
            reference = {"state": "unavailable"}
        view, view_receipt = None, None
        pinned = approved_binding.get("data_view_receipt") if approved_binding is not None else None
        receipts = state.get("_tool_runs", []) if approved_binding is None else [
            row for row in state.get("_tool_runs", []) if pinned and
            row["file"] == pinned["file"] and row["sha256"] == pinned["sha256"]]
        for receipt in reversed(receipts):
            if (receipt["tool_id"] != "P0-01" or receipt["state"] != "succeeded"
                    or self.service._qc_receipt_asset_id(state, receipt) != upload_id):
                continue
            record = next((row for row in state["_input_objects"].values()
                if row.get("receipt_file") == receipt["file"]
                and row["schema_ref"] == "bridge://schemas/qc-readiness-profile/v0.2"
                and self.service.inputs.receipt_artifacts(state, row)[row["artifact_id"]]["kind"] == "qc_profile_v2"), None)
            if record:
                view = self.service.inputs.verify(state, record)["selected_data_view"]
                view_receipt = {"file": receipt["file"], "sha256": receipt["sha256"]}
            break
        return {"data_view": view, "data_view_receipt": view_receipt, "upload": upload, "intake": intake,
                "declaration": self.service.intake.signature(state, upload_id),
                "resources": records, "reference": reference, "science": science,
                "measurement_spec_ref": self.service.settings.cell_state_measurement_spec_ref,
                "knowledge": hashlib.sha256(files("bridge.resources").joinpath("knowledge_snapshot.json.gz").read_bytes()).hexdigest(),
                "selections": self.service.inputs.assessment_selections(state, allowed_modes),
                "tool_contracts": [spec.model_dump(mode="json") for spec in self.service.registry.list()
                                  if spec.tool_id in {row.tool_id for row in allowed_modes}]}

    def propose(self, state, body):
        self.service.controls.require_ready(state)
        self.service.busy(state)
        self.service.inputs.initialize(state)
        try:
            for mode in body.allowed_modes:
                contract, _ = self.service.inputs.contract_mode(mode.tool_id, mode.mode_id)
                if contract.object_input_modes and mode.mode_id is None:
                    raise ValueError("input_mode_required")
        except ValueError:
            raise HTTPException(422, "invalid_assessment_mode") from None
        try:
            resource_ids = self.service.inputs.assessment_resource_ids(state, body.upload_id, body.allowed_modes)
            binding = self._binding(state, body.upload_id, resource_ids, body.allowed_modes)
        except (ValueError, OSError, KeyError) as exc:
            raise HTTPException(409, "assessment_inputs_not_confirmed_or_valid") from exc
        scope = AssessmentScope(scope_id=secrets.token_hex(16), session_id=state["id"],
            question=body.question, upload_id=body.upload_id, input_revision=state["_input_revision"],
            allowed_modes=body.allowed_modes, max_tool_runs=body.max_tool_runs,
            max_model_turns=body.max_model_turns, binding=binding)
        if state.get("_assessment"):
            state.setdefault("_assessment_history", []).append(state["_assessment"])
        state["_assessment"] = {"scope": scope.model_dump(mode="json"),
            "scope_digest": digest(scope.model_dump(mode="json")), "status": "proposed",
            "authorization": None, "tool_runs_used": 0, "model_turns_used": 0,
            "admissions": [], "model_turns": [], "stop_reason": None, "blockers": []}
        self.service.save(state)

    def _identity(self, state, body):
        assessment = state.get("_assessment")
        if (assessment is None or assessment["scope"]["scope_id"] != body.scope_id
                or not secrets.compare_digest(assessment["scope_digest"], body.scope_digest)):
            raise HTTPException(409, "assessment_scope_mismatch")
        return assessment

    def check(self, state, epoch=None):
        assessment = state["_assessment"]
        scope = AssessmentScope.model_validate(assessment["scope"])
        if epoch is not None and (state["_control_epoch"] != epoch or assessment["status"] != "running"):
            return "assessment_stopped"
        if state["input_review_required"]:
            return "input_review_required"
        if state["_input_revision"] != scope.input_revision:
            return "input_revision_changed"
        if digest(scope.model_dump(mode="json")) != assessment["scope_digest"]:
            return "scope_binding_changed"
        try:
            current = self._binding(state, scope.upload_id, scope.binding["resources"], scope.allowed_modes,
                                    approved_binding=scope.binding)
        except (ValueError, OSError, KeyError):
            return "scope_resource_changed"
        if current != scope.binding:
            return "scope_resource_changed"
        return None

    def approve(self, state, body):
        assessment = self._identity(state, body)
        self.service.controls.require_ready(state)
        self.service.busy(state)
        if assessment["status"] != "proposed" or assessment["authorization"] is not None:
            raise HTTPException(409, "assessment_approval_not_pending")
        reason = self.check(state)
        if reason:
            raise HTTPException(409, reason)
        assessment["authorization"] = {"scope_id": body.scope_id, "scope_sha256": body.scope_digest,
            "approver_id": "private-operator", "authority_ref": "web-session:" + state["id"],
            "approved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
        assessment["status"] = "running"
        self.service.save(state)  # original authorization is durable before dispatch
        self._schedule(state)

    def stop(self, state, reason, *, status="stopped"):
        if state.get("_assessment") and state["_assessment"]["status"] in {"proposed", "running", "stopped", "blocked", "interrupted"}:
            state["_assessment"]["status"] = status
            state["_assessment"]["stop_reason"] = reason

    def resume(self, state, body):
        assessment = self._identity(state, body)
        self.service.controls.require_ready(state)
        self.service.busy(state)
        if assessment["status"] not in {"stopped", "blocked", "interrupted"} or assessment["authorization"] is None:
            raise HTTPException(409, "assessment_not_resumable")
        reason = self.check(state)
        if reason:
            raise HTTPException(409, reason)
        if assessment["tool_runs_used"] >= assessment["scope"]["max_tool_runs"]:
            raise HTTPException(409, "tool_run_budget_exhausted")
        if assessment["model_turns_used"] >= assessment["scope"]["max_model_turns"]:
            raise HTTPException(409, "model_turn_budget_exhausted")
        assessment["status"], assessment["stop_reason"] = "running", None
        self._schedule(state)

    def _schedule(self, state):
        try:
            self.service.schedule(state, "running", self.advance)
        except HTTPException as exc:
            self._finish(state, "worker_busy", status="blocked")
            raise exc

    def _finish(self, state, reason, *, status="stopped"):
        self.stop(state, reason, status=status)
        state["status"], state["error"] = "idle", None
        self.service.save(state)

    def public(self, state):
        assessment = state.get("_assessment")
        if assessment is None:
            return None
        from .evidence import assessment_evidence
        scope = assessment["scope"]
        evidence, _ = assessment_evidence(self.service.inputs, state, assessment)
        bound_view = scope["binding"].get("data_view")
        view = {"state": "not_available"} if not bound_view else {
            "state": "available", **{key: bound_view[key] for key in
                ("view_kind", "sha256", "parent_asset_sha256", "n_observations", "observation_ids_sha256")}}
        return {"scope_id": scope["scope_id"], "scope_digest": assessment["scope_digest"],
            "question": scope["question"], "upload_id": scope["upload_id"],
            "input_revision": scope["input_revision"], "allowed_modes": scope["allowed_modes"],
            "max_tool_runs": scope["max_tool_runs"], "max_model_turns": scope["max_model_turns"],
            "status": assessment["status"], "tool_runs_used": assessment["tool_runs_used"],
            "model_turns_used": assessment["model_turns_used"], "stop_reason": assessment["stop_reason"],
            "blockers": assessment["blockers"], "evidence": evidence,
            "hypotheses": assessment.get("hypotheses", []),
            "data_view": view,
            "resources": [{"alias": "R-" + identifier[:12], **{key: row[key] for key in
                ("schema_ref", "object_version", "sha256", "source")}}
                for identifier, row in scope["binding"]["resources"].items()] + [
                    {"alias": "R-seurat-cell-cycle-v5.5.1", "schema_ref": None,
                     "resource_ref": key, "object_version": "0.1.0", "sha256": value, "source": "package_resource"}
                    for key, value in scope["binding"]["science"].items()
                    if key == "bridge://resources/seurat-cell-cycle-candidate/v5.5.1"],
            "stop_conditions": ["input_or_resource_change", "explicit_stop", "finite_budgets",
                                "no_eligible_check", "necessary_fact", "result_sharing_disabled"],
            "question_sent_to_model": True,
            "scope_authorized": assessment["authorization"] is not None,
            "scope_grants_scientific_approval": False}

    def advance(self, sid, epoch):
        from . import provider
        from .evidence import assessment_evidence
        while True:
            with self.service.qc_catalog(), self.service.lock:
                state = self.service.load(sid)
                reason = self.check(state, epoch)
                if reason:
                    if state["_control_epoch"] == epoch:
                        self._finish(state, reason, status="blocked")
                    return
                assessment = state["_assessment"]
                scope = AssessmentScope.model_validate(assessment["scope"])
                if assessment["tool_runs_used"] >= scope.max_tool_runs:
                    self._finish(state, "tool_run_budget_exhausted")
                    return
                if assessment["model_turns_used"] >= scope.max_model_turns:
                    self._finish(state, "model_turn_budget_exhausted")
                    return
                candidates = self.service.inputs.assessment_candidates(state, scope)
                used = {row["fingerprint"] for row in assessment["admissions"]}
                options = {row["fingerprint"]: row for row in candidates
                           if row["request"] is not None and not row["blockers"] and row["fingerprint"] not in used}
                assessment["blockers"] = [{"tool_id": row["tool_id"], "mode_id": row["mode_id"],
                    "reason_codes": row["blockers"]} for row in candidates if row["blockers"]]
                evidence, bindings = assessment_evidence(self.service.inputs, state, assessment)
                if not options and not any(row["state"] == "available" for row in evidence):
                    self._finish(state, "no_eligible_check", status="blocked")
                    return
                shared = self.service.settings.share_result_summaries
                context = {"purpose": "assessment", "question": scope.question,
                    "options": [{"id": key, "tool_id": row["tool_id"], "mode_id": row["mode_id"],
                                 "kind": "query" if row["mode_id"] == "case_query" else "check"} for key, row in options.items()],
                    "evidence": evidence if shared else [], "results_sent_to_model": shared and bool(evidence),
                    "blockers": assessment["blockers"]}
                if len(json.dumps(context, ensure_ascii=False).encode()) > 128 * 1024:
                    self._finish(state, "evidence_context_limit", status="blocked")
                    return
                if evidence and not shared:
                    self._finish(state, "result_sharing_disabled", status="blocked")
                    return
                assessment["model_turns_used"] += 1
                assessment["model_turns"].append({"number": assessment["model_turns_used"],
                    "state": "dispatched", "evidence_bindings": bindings if shared else {}})
                self.service.save(state)
            try:
                action = provider.converse(self.service.settings,
                    [{"role": "user", "content": "Select the next authorized evidence action."}], context)
                action = provider.Action.model_validate(action.model_dump(mode="json"))
                if action.action != "assessment":
                    raise ValueError("model_action_purpose_mismatch")
            except Exception:
                with self.service.lock:
                    state = self.service.load(sid)
                    if state["_control_epoch"] == epoch:
                        self._finish(state, "provider_action_invalid_or_unavailable", status="blocked")
                return
            with self.service.qc_catalog(), self.service.lock:
                state = self.service.load(sid)
                reason = self.check(state, epoch)
                if reason:
                    if state["_control_epoch"] == epoch:
                        self._finish(state, reason, status="blocked")
                    return
                assessment = state["_assessment"]
                assessment["model_turns"][-1]["state"] = "received"
                decision = action.decision
                valid_aliases = {row["alias"] for row in context["evidence"] if row["state"] == "available"}
                if any(not set(hypothesis.evidence_aliases) <= valid_aliases
                       for hypothesis in decision.hypotheses):
                    self._finish(state, "invalid_evidence_alias", status="blocked")
                    return
                if any(hypothesis.discriminating_check not in {mode.tool_id for mode in scope.allowed_modes}
                       for hypothesis in decision.hypotheses):
                    self._finish(state, "hypothesis_check_outside_scope", status="blocked")
                    return
                assessment["model_turns"][-1]["decision"] = decision.model_dump(mode="json")
                if decision.reason == "evidence_requirements_reached":
                    # Scope consent authorizes checks, not a completion contract.
                    # Even satisfied graph-local requirements cannot establish the
                    # approved research question is complete; an absent contract
                    # is unavailable, never a vacuously satisfied empty set.
                    self._finish(state, "completion_contract_unavailable", status="blocked")
                    return
                assessment["hypotheses"] = [row.model_dump(mode="json") for row in decision.hypotheses]
                if decision.action in {"stop", "question", "explain"}:
                    if decision.text:
                        self.service.message(state, "assistant", decision.text)
                    self._finish(state, decision.reason or ("necessary_fact_required" if decision.action == "question" else "explanation_complete"))
                    return
                candidate = options.get(decision.option_id)
                if candidate is None or (decision.action == "query") != (candidate["mode_id"] == "case_query"):
                    self._finish(state, "unavailable_or_repeated_action", status="blocked")
                    return
                # Reconstruct/recheck after the provider boundary. It cannot supply a request.
                current = self.service.inputs.assessment_candidates(state, scope)
                candidate = next((row for row in current if row["fingerprint"] == decision.option_id and not row["blockers"]), None)
                if candidate is None:
                    self._finish(state, "candidate_changed", status="blocked")
                    return
                self.service.propose_request(state, candidate["bundle"], candidate["request"],
                    "范围内的精确检查；沿用原始范围授权，不产生新的科学审批。", scope_admission=True)
                plan = AnalysisPlan.model_validate(state["_plan"])
                if not any(step.disposition.value == "execute" for step in plan.steps):
                    self._finish(state, "package_not_eligible", status="blocked")
                    return
                approval = PlanApprovalReceipt(plan_id=plan.plan_id, plan_sha256=plan.approval_sha256(),
                    authorization_kind="scope_derived", **assessment["authorization"])
                payload = plan.model_dump(mode="json")
                payload.update(status="approved", approval_receipt=approval.model_dump(mode="json"))
                approved = AnalysisPlan.model_validate(payload)
                state["_plan"], state["plan"]["status"] = approved.model_dump(mode="json"), "approved"
                assessment["tool_runs_used"] += 1
                assessment["admissions"].append({"fingerprint": candidate["fingerprint"], "plan_id": plan.plan_id,
                    "plan_sha256": plan.approval_sha256(), "tool_id": candidate["tool_id"],
                    "mode_id": candidate["mode_id"], "state": "dispatched"})
                state["status"] = "running"
                self.service.save(state)
            self.service.execute(sid, epoch)
            with self.service.lock:
                state = self.service.load(sid)
                if state["_control_epoch"] != epoch:
                    return
                assessment = state["_assessment"]
                if assessment["status"] != "running":
                    return
                assessment["admissions"][-1]["state"] = state["plan"]["status"]
                if state["plan"]["status"] not in {"completed", "partial"}:
                    self._finish(state, "tool_execution_failed", status="blocked")
                    return
                self.service.save(state)
