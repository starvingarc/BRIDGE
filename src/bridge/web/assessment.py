"""Private scope-bound admission and one-worker evidence feedback."""
from __future__ import annotations

from datetime import datetime, timezone
from importlib.resources import files
import hashlib
import json
import secrets
from typing import Literal

from fastapi import HTTPException
from pydantic import Field, StrictBool, StrictInt, ValidationError, model_validator

from bridge.domain.models import AnalysisPlan, PlanApprovalReceipt
from bridge.toolkit.contracts import FrozenModel
from .inputs import InputBody, Selection, verify_checked_file
from .scientific_inputs import digest


class AllowedMode(InputBody):
    tool_id: Literal["P0-01", "P0-02", "P0-03", "P0-04", "P0-05", "P0-06", "P0-08", "P0-09", "P0-10"]
    mode_id: str | None = Field(max_length=100)


class ContinuationSource(FrozenModel):
    scope_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    scope_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    pending_revision_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ScopeProposal(InputBody):
    continuation: ContinuationSource | None = None
    question: str = Field(min_length=1, max_length=2000)
    upload_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    allowed_modes: list[AllowedMode] = Field(min_length=1, max_length=16)
    max_tool_runs: StrictInt = Field(ge=1, le=32)
    max_model_turns: StrictInt = Field(ge=1, le=64)
    report_after_explanation: StrictBool = False
    literature_enabled: StrictBool = False
    literature_concept_refs: list[str] = Field(default_factory=list, max_length=6)
    max_literature_searches: StrictInt = Field(default=3, ge=1, le=3)
    max_literature_reads: StrictInt = Field(default=6, ge=1, le=6)

    @model_validator(mode="after")
    def unique_modes(self):
        from .literature import PUBLIC_CONCEPTS
        refs = self.literature_concept_refs
        if (len(refs) != len(set(refs)) or not set(refs) <= set(PUBLIC_CONCEPTS)
                or self.literature_enabled != bool(refs)):
            raise ValueError("literature_public_concepts_required")
        keys = [(row.tool_id, row.mode_id) for row in self.allowed_modes]
        if len(keys) != len(set(keys)) or not self.question.strip():
            raise ValueError("invalid_assessment_scope")
        if self.report_after_explanation and ("P0-10", "default") not in keys:
            raise ValueError("report_mode_required_for_report_intent")
        if any(row.mode_id and ("comparison" in row.mode_id or "graft" in row.mode_id) for row in self.allowed_modes):
            raise ValueError("separate_branch_approval_required")
        return self


class ScopeIdentity(InputBody):
    scope_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    scope_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class AssessmentScope(FrozenModel):
    continuation: ContinuationSource | None = None
    scope_id: str
    session_id: str
    question: str
    upload_id: str
    input_revision: int
    allowed_modes: tuple[AllowedMode, ...]
    max_tool_runs: int
    max_model_turns: int
    report_after_explanation: StrictBool = False
    literature_enabled: StrictBool = False
    literature_concept_refs: list[str] = Field(default_factory=list, max_length=6)
    max_literature_searches: StrictInt = Field(default=3, ge=1, le=3)
    max_literature_reads: StrictInt = Field(default=6, ge=1, le=6)
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
        verify_checked_file(
            self.service,
            state,
            self.service.directory(state["id"]) / "uploads" / (upload_id + ".h5ad"),
            upload["sha256"],
            limit=self.service.settings.max_upload_bytes,
        )
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
        from bridge.tool_packages.p0_02_cell_state.candidate_runtime import CANDIDATE_SPEC
        if self.service.settings.cell_state_measurement_spec_ref == CANDIDATE_SPEC:
            parameters = self.service.cell_state_runtime_parameters()
            science["cell-state-candidate-binding"] = parameters["candidate_binding_sha256"]
            science["development-review-v1.1"] = hashlib.sha256(
                resources.joinpath("development_review_v1_1.json").read_bytes()).hexdigest()
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
            if (receipt["file"] in state.get("_invalidated_receipts", {})
                    or receipt["tool_id"] != "P0-01" or receipt["state"] != "succeeded"
                    or self.service.qc.receipt_asset_id(state, receipt) != upload_id):
                continue
            record = next((row for row in state["_input_objects"].values()
                if row.get("receipt_file") == receipt["file"]
                and row["schema_ref"] == "bridge://schemas/qc-readiness-profile/v0.2"
                and self.service.inputs.receipt_artifacts(state, row)[row["artifact_id"]]["kind"] == "qc_profile_v2"), None)
            if record:
                view = self.service.inputs.verify(state, record)["selected_data_view"]
                view_receipt = {"file": receipt["file"], "sha256": receipt["sha256"]}
            break
        selections = self.service.inputs.assessment_selections(state, allowed_modes)
        if approved_binding is not None and any(
                row.tool_id == "P0-06" and row.mode_id == "directed_programs" for row in allowed_modes):
            frozen = approved_binding.get("selections", {}).get("P0-06")
            if not frozen or frozen.get("mode_id") != "directed_programs":
                raise ValueError("directed_source_not_bound")
            selected = Selection.model_validate(frozen)
            refs = [row for row in selected.object_inputs if row.role == "directed_program_input"]
            if (len(refs) != 1 or refs[0].input_id not in records
                    or selected.asset_ids != [upload_id]):
                raise ValueError("directed_source_not_bound")
            self.service.inputs.verify(state, records[refs[0].input_id])
            if "P0-06" in selections and selections["P0-06"] != frozen:
                raise ValueError("directed_source_selection_changed")
            selections["P0-06"] = frozen
        appends = {}
        for tool_id, mode_id in (("P0-08", "default"), ("P0-09", "case_append_v2")):
            key = "append_" + tool_id.lower().replace("-", "")
            append = approved_binding.get(key) if approved_binding is not None else None
            if append is None:
                continue
            if (not any((row.tool_id, row.mode_id) == (tool_id, mode_id) for row in allowed_modes)
                    or selections.get(tool_id) != append.get("base_selection")):
                raise ValueError("native_append_selection_changed")
            if append.get("after_sufficiency") and (
                    tool_id != "P0-09"
                    or not approved_binding.get("append_p008", {}).get("selection")):
                raise ValueError("native_append_source_not_bound")
            if "selection" in append:
                selected = Selection.model_validate(append["selection"])
                if ((selected.tool_id, selected.mode_id) != (tool_id, mode_id)
                        or not selected.object_inputs
                        or any(row.input_id not in records for row in selected.object_inputs)):
                    raise ValueError("native_append_source_not_bound")
            appends[key] = append
        result = {"data_view": view, "data_view_receipt": view_receipt, "upload": upload, "intake": intake,
                "declaration": self.service.intake.signature(state, upload_id),
                "resources": records, "reference": reference, "science": science,
                "measurement_spec_ref": self.service.settings.cell_state_measurement_spec_ref,
                "knowledge": hashlib.sha256(files("bridge.resources").joinpath("knowledge_snapshot.json.gz").read_bytes()).hexdigest(),
                "selections": selections,
                "tool_contracts": [spec.model_dump(mode="json") for spec in self.service.registry.list()
                                  if spec.tool_id in {row.tool_id for row in allowed_modes}]}
        result.update(appends)
        return result

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
            if body.continuation is None:
                resource_ids = self.service.inputs.assessment_resource_ids(state, body.upload_id, body.allowed_modes)
                binding = self._binding(state, body.upload_id, resource_ids, body.allowed_modes)
            else:
                previous = state.get("_assessment") or {}
                if (previous.get("scope", {}).get("scope_id") != body.continuation.scope_id
                        or previous.get("scope_digest") != body.continuation.scope_digest
                        or self.check(state) is not None):
                    raise HTTPException(409, "assessment_continuation_not_available")
                previous_scope = AssessmentScope.model_validate(previous["scope"])
                # Pin only verified results admitted by the original scope, never newly discovered roots.
                roots = self.service.inputs.assessment_pool(state, previous_scope)
                binding = self._binding(state, body.upload_id, roots, body.allowed_modes,
                                        approved_binding=previous_scope.binding)
        except (ValueError, OSError, KeyError) as exc:
            raise HTTPException(409, "assessment_inputs_not_confirmed_or_valid") from exc
        scope = AssessmentScope(scope_id=secrets.token_hex(16), session_id=state["id"],
            question=body.question, upload_id=body.upload_id, input_revision=state["_input_revision"],
            allowed_modes=body.allowed_modes, max_tool_runs=body.max_tool_runs,
            max_model_turns=body.max_model_turns, report_after_explanation=body.report_after_explanation,
            literature_enabled=body.literature_enabled, literature_concept_refs=body.literature_concept_refs,
            max_literature_searches=body.max_literature_searches, max_literature_reads=body.max_literature_reads,
            binding=binding)
        directed = next((mode for mode in body.allowed_modes
            if (mode.tool_id, mode.mode_id) == ("P0-06", "directed_programs")), None)
        if directed is not None and body.continuation is None:
            existing = binding["selections"].get("P0-06")
            selection = Selection.model_validate(existing) if existing and existing["mode_id"] == "directed_programs" else (
                Selection(tool_id="P0-06", mode_id="directed_programs", asset_ids=[],
                          object_inputs=[], measurement_spec_ref=None))
            try:
                fixed = self.service.scientific_inputs.assessment_selection(state, scope, directed, selection)
            except (ValueError, OSError, KeyError) as exc:
                raise HTTPException(409, "assessment_inputs_not_confirmed_or_valid") from exc
            binding = {**binding, "selections": {**binding["selections"], "P0-06": fixed.model_dump(mode="json")}}
            scope = scope.model_copy(update={"binding": binding})
        if (body.continuation is None and self.service.settings.cell_state_candidate_runtime_ref
                and any(record.get("producer_tool_id") == "P0-09"
                        and record["schema_ref"] == "bridge://schemas/case-evidence-graph-manifest/v0.1"
                        for record in binding["resources"].values())):
            from .native_evidence import selection as native_selection
            for tool_id, mode_id in (("P0-08", "default"), ("P0-09", "case_append_v2")):
                allowed = next((mode for mode in body.allowed_modes
                    if (mode.tool_id, mode.mode_id) == (tool_id, mode_id)), None)
                old = binding["selections"].get(tool_id)
                if allowed is None or old is None or old["mode_id"] != mode_id:
                    continue
                if tool_id == "P0-09" and binding.get("append_p008", {}).get("selection"):
                    # The upstream selection is frozen, but its result does not
                    # exist yet. Resolve the append from verified scope outputs.
                    append = {"base_selection": old, "after_sufficiency": True}
                else:
                    try:
                        selected = native_selection(self.service.report_inputs, state, scope, allowed)
                    except ValueError as exc:
                        append = {"base_selection": old,
                                  "blocker": str(exc) if str(exc) in {
                                      "canonical_graph_inputs_unchanged",
                                      "native_invalidated_evidence_revision_requires_review",
                                  } else "native_append_source_unavailable"}
                    else:
                        append = {"base_selection": old, "selection": selected.model_dump(mode="json")}
                        resources = dict(binding["resources"])
                        for row in selected.object_inputs:
                            record = state["_input_objects"][row.input_id]
                            self.service.inputs.verify(state, record)
                            resources[row.input_id] = record
                        binding = {**binding, "resources": resources}
                key = "append_" + tool_id.lower().replace("-", "")
                binding = {**binding, key: append}
                scope = scope.model_copy(update={"binding": binding})
        pending = None
        if body.continuation is not None:
            import copy
            old = state.get("_assessment") or {}
            source = body.continuation
            pending = old.get("pending_revision")
            if (old.get("scope", {}).get("scope_id") != source.scope_id
                    or old.get("scope_digest") != source.scope_digest
                    or old.get("status") not in {"stopped", "blocked", "interrupted"}
                    or old.get("authorization") is None
                    or not pending or not pending.get("issues")
                    or digest(pending) != source.pending_revision_sha256
                    or old.get("interpretation_versions") or self.check(state) is not None):
                raise HTTPException(409, "assessment_continuation_not_available")
            previous = AssessmentScope.model_validate(old["scope"]).model_dump(mode="json")
            proposed = scope.model_dump(mode="json")
            # This extension is computed solely from the checked source scope's admitted receipts.
            previous["binding"] = binding
            for key in ("scope_id", "max_model_turns", "max_tool_runs", "continuation"):
                previous.pop(key, None)
                proposed.pop(key, None)
            # Read-literature sessions need a separately budgeted continuation contract.
            if previous != proposed or scope.literature_enabled:
                raise HTTPException(409, "assessment_continuation_scope_changed")
            pending = copy.deepcopy(pending)
            scope = scope.model_copy(update={"continuation": source})
        if state.get("_assessment"):
            if pending is None:
                state["_assessment"].pop("pending_revision", None)
            state.setdefault("_assessment_history", []).append(state["_assessment"])
        state["_assessment"] = {"scope": scope.model_dump(mode="json"),
            "scope_digest": digest(scope.model_dump(mode="json")), "status": "proposed",
            "authorization": None, "tool_runs_used": 0, "model_turns_used": 0,
            "admissions": [], "model_turns": [], "stop_reason": None, "stop_events": [], "blockers": []}
        if pending is not None:
            state["_assessment"]["pending_revision"] = pending
        self._candidate_state(state["_assessment"], self.service.inputs.assessment_candidates(state, scope))
        self.service.sessions.save(state)

    @staticmethod
    def _candidate_state(assessment, candidates):
        admitted = {row["fingerprint"] for row in assessment["admissions"]}
        assessment["candidates"] = [{
            "tool_id": row["tool_id"], "mode_id": row["mode_id"],
            **{key: row[key] for key in ("source_gene_set", "source_resource_sha256") if key in row},
            "runnable": row["request"] is not None and not row["blockers"] and row["fingerprint"] not in admitted,
            "already_admitted": row["fingerprint"] in admitted,
            "blockers": sorted(set(row["blockers"])), "gaps": sorted(set(row.get("gaps", [])))}
            for row in candidates]
        assessment["blockers"] = [{"tool_id": row["tool_id"], "mode_id": row["mode_id"],
            "reason_codes": sorted(set(row["blockers"] + row["gaps"]))}
            for row in assessment["candidates"] if row["blockers"] or row["gaps"]]

    @staticmethod
    def _report_handoff(state, assessment, scope, options, evidence):
        """Expose only the current append/explanation/report phase, never old aliases."""
        report = next((row for row in options.values()
            if (row["tool_id"], row["mode_id"]) == ("P0-10", "default")), None)
        if report is None:
            return None
        graph_ref = next((ref for ref in report["request"].object_inputs
            if ref.role == "evidence_graph_manifest"), None)
        record = state.get("_input_objects", {}).get(graph_ref.input_id) if graph_ref else None
        receipt = next((row for row in state.get("_tool_runs", [])
            if row["file"] == record.get("receipt_file")
            and row["sha256"] == record.get("receipt_sha256")), None) if record else None
        if receipt is None or not any(
                row["plan_id"] == receipt["plan_id"] and row["tool_id"] == "P0-09"
                and row["mode_id"] == "case_append_v2" and row["state"] in {"completed", "partial"}
                for row in assessment["admissions"]):
            return None
        snapshot = digest(evidence)
        version = next((row for row in reversed(assessment.get("interpretation_versions", []))
            if row["scope_digest"] == assessment["scope_digest"]
            and row["input_revision"] == scope.input_revision
            and row["evidence_snapshot_sha256"] == snapshot and row["hypotheses"]), None)
        if version is None:
            return None
        return {"state": "report_ready_after_current_explanation",
            "explanation_version": version["version"],
            "prior_report_state": ("not_bound_to_current_explanation"
                if any(row["tool_id"] == "P0-10" and row["state"] == "available" for row in evidence)
                else "none")}

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
        if digest(assessment["scope"]) != assessment["scope_digest"]:
            return "scope_binding_changed"
        if any((row.tool_id, row.mode_id) == ("P0-06", "directed_programs") for row in scope.allowed_modes):
            frozen = scope.binding.get("selections", {}).get("P0-06")
            if not frozen or frozen.get("mode_id") != "directed_programs":
                return "directed_source_not_bound"
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
        source = assessment["scope"].get("continuation")
        if source and digest(assessment.get("pending_revision")) != source["pending_revision_sha256"]:
            raise HTTPException(409, "assessment_continuation_draft_changed")
        assessment["authorization"] = {"scope_id": body.scope_id, "scope_sha256": body.scope_digest,
            "approver_id": "private-operator", "authority_ref": "web-session:" + state["id"],
            "approved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
        assessment["status"] = "running"
        self.service.sessions.save(state)  # original authorization is durable before dispatch
        self._schedule(state)

    def stop(self, state, reason, *, status="stopped"):
        assessment = state.get("_assessment")
        if assessment and assessment["status"] in {"proposed", "running"}:
            assessment["status"] = status
            assessment["stop_reason"] = reason
            assessment.setdefault("stop_events", []).append({
                "reason": reason, "status": status,
                "stopped_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "tool_runs_used": assessment["tool_runs_used"],
                "model_turns_used": assessment["model_turns_used"]})

    def _resume_blocker(self, state):
        if state.get("input_review_required"):
            return "input_review_required"
        if state.get("status") in {"thinking", "running", "stopping"}:
            return "session_busy"
        assessment = state.get("_assessment")
        if assessment is None:
            return "assessment_not_resumable"
        if assessment["status"] not in {"stopped", "blocked", "interrupted"} or assessment["authorization"] is None:
            return "assessment_not_resumable"
        if assessment["stop_reason"] == "report_complete":
            return "assessment_report_complete"
        if (assessment["scope"].get("report_after_explanation", False)
                and any(row["tool_id"] == "P0-10" for row in assessment["admissions"])):
            return "assessment_report_already_admitted"
        reason = self.check(state)
        if reason:
            return reason
        if assessment["tool_runs_used"] >= assessment["scope"]["max_tool_runs"]:
            return "tool_run_budget_exhausted"
        direct_report = (assessment["scope"].get("report_after_explanation", False)
            and assessment["stop_reason"] == "explanation_complete")
        if not direct_report and assessment["model_turns_used"] >= assessment["scope"]["max_model_turns"]:
            return "model_turn_budget_exhausted"
        if (not direct_report and assessment.get("pending_revision", {}).get("issues")
                and assessment["scope"]["max_model_turns"] - assessment["model_turns_used"] < 2):
            return "interpretation_revision_budget_insufficient"
        return None

    def continuation_proposal(self, state):
        """Offer a fresh finite authorization, carrying only the exact unresolved draft."""
        assessment = state.get("_assessment") or {}
        scope = assessment.get("scope", {})
        pending = assessment.get("pending_revision")
        if (assessment.get("status") not in {"stopped", "blocked", "interrupted"}
                or assessment.get("authorization") is None or not pending or not pending.get("issues")
                or assessment.get("interpretation_versions") or scope.get("literature_enabled")
                or scope["max_model_turns"] - assessment["model_turns_used"] >= 2
                or self.check(state) is not None):
            return None
        proposal = {key: value for key, value in scope.items() if key in ScopeProposal.model_fields}
        proposal.update(max_model_turns=8,
            max_tool_runs=max(1, scope["max_tool_runs"] - assessment["tool_runs_used"]),
            continuation={"scope_id": scope["scope_id"], "scope_digest": assessment["scope_digest"],
                          "pending_revision_sha256": digest(pending)})
        return ScopeProposal.model_validate(proposal).model_dump(mode="json")

    def resume_eligibility(self, state):
        """Return the actual resume decision without changing session state."""
        reason = self._resume_blocker(state)
        return reason is None, reason

    def resume(self, state, body):
        assessment = self._identity(state, body)
        reason = self._resume_blocker(state)
        if reason:
            raise HTTPException(409, reason)
        if not assessment.get("stop_events") and assessment.get("stop_reason"):
            # Preserve terminal records written before stop-event history existed.
            assessment["stop_events"] = [{"reason": assessment["stop_reason"],
                "status": assessment["status"], "stopped_at": None,
                "tool_runs_used": assessment["tool_runs_used"],
                "model_turns_used": assessment["model_turns_used"]}]
        assessment["status"], assessment["stop_reason"] = "running", None
        self._schedule(state)

    def _schedule(self, state):
        try:
            self.service.execution.schedule(state, "running", self.advance)
        except HTTPException as exc:
            from .presentation import MODEL_SELECTION_ERRORS
            reason = exc.detail if exc.detail in MODEL_SELECTION_ERRORS else "worker_busy"
            self._finish(state, reason, status="blocked")
            raise exc

    def _finish(self, state, reason, *, status="stopped"):
        from .runtime import record_degradation
        record_degradation(state, reason)
        self.stop(state, reason, status=status)
        state["status"], state["error"] = "idle", None
        self.service.sessions.save(state)

    def public(self, state):
        assessment = state.get("_assessment")
        if assessment is None:
            return None
        from .evidence import assessment_evidence, assessment_portrait
        scope = assessment["scope"]
        evidence, bindings = assessment_evidence(self.service.inputs, state, assessment)
        reason = ("input_revision_changed" if state["_input_revision"] != scope["input_revision"]
                  else self.check(state))
        freshness = {"state": "current" if reason is None else
                     "review_pending" if reason == "input_review_required" else "historical",
                     "reason_code": reason, "current_input_revision": state["_input_revision"],
                     "scope_input_revision": scope["input_revision"],
                     "pending_review": state["input_review_required"]}
        bound_view = scope["binding"].get("data_view")
        view = {"state": "not_available"} if not bound_view else {
            "state": "available", **{key: bound_view[key] for key in
                ("view_kind", "sha256", "parent_asset_sha256", "n_observations", "observation_ids_sha256")}}
        return {"scope_id": scope["scope_id"], "scope_digest": assessment["scope_digest"],
            "question": scope["question"], "upload_id": scope["upload_id"],
            "continuation": scope.get("continuation"),
            "continuation_proposal": self.continuation_proposal(state),
            "input_revision": scope["input_revision"], "allowed_modes": scope["allowed_modes"],
            "report_after_explanation": scope.get("report_after_explanation", False),
            "literature": self._public_literature(assessment),
            "max_tool_runs": scope["max_tool_runs"], "max_model_turns": scope["max_model_turns"],
            "status": assessment["status"], "tool_runs_used": assessment["tool_runs_used"],
            "model_turns_used": assessment["model_turns_used"], "stop_reason": assessment["stop_reason"],
            "stop_events": assessment.get("stop_events", []),
            "blockers": assessment["blockers"],
            "evidence": [{**row, "navigation": bindings[row["alias"]]["navigation"]}
                if row["alias"] in bindings else row for row in evidence],
            "candidates": assessment.get("candidates", []), "freshness": freshness,
            "portrait": assessment_portrait(evidence, assessment.get("candidates", []),
                current_plan_ids={row["plan_id"] for row in assessment["admissions"]},
                modes_by_receipt={row["sha256"]: row.get("mode_id") for row in state["_tool_runs"]},
                order_by_receipt={row["sha256"]: index for index, row in enumerate(state["_tool_runs"])}),
            "result_summaries_enabled": self.service.settings.share_result_summaries,
            "history": [{"scope_id": row["scope"]["scope_id"], "question": row["scope"]["question"],
                         "input_revision": row["scope"]["input_revision"], "status": row["status"],
                         "stop_reason": row["stop_reason"], "stop_events": row.get("stop_events", [])}
                        for row in state.get("_assessment_history", [])],
            "hypotheses": assessment.get("hypotheses", []),
            "interpretation_versions": assessment.get("interpretation_versions", []),
            "data_view": view,
            "resources": [{"alias": "R-" + identifier[:12], **{key: row[key] for key in
                ("schema_ref", "object_version", "sha256", "source")},
                **({"source_gene_set": self.service.inputs.verify(state, row)["programs"][0]["source_gene_set"],
                   "source_resource_sha256": self.service.inputs.verify(state, row)["resource"]["sha256"]}
                   if row["schema_ref"] == "bridge://schemas/exploratory-process-input/v0.3" else {})}
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

    def _report_resume_candidate(self, state, assessment, scope, options, evidence):
        """Resolve an explicit post-explanation report from existing bound records."""
        previous = (assessment.get("stop_events") or [{}])[-1]
        if not scope.report_after_explanation or previous.get("reason") != "explanation_complete":
            return None, None
        turn = (assessment.get("model_turns") or [{}])[-1]
        if (previous.get("model_turns_used") != assessment["model_turns_used"]
                or previous.get("tool_runs_used") != assessment["tool_runs_used"]
                or turn.get("number") != assessment["model_turns_used"]
                or turn.get("state") != "received"
                or turn.get("decision", {}).get("action") != "explain"):
            return None, "report_handoff_stale"
        from bridge.tool_packages.p0_10_claim_verifier.research import (
            parse_research_explanation, parse_research_context,
        )
        try:
            version = parse_research_explanation(
                assessment["interpretation_versions"][-1])
        except (ValueError, KeyError, IndexError):
            return None, "report_handoff_stale"
        from . import provider
        from .evidence import assessment_citation_roles
        citation_roles = assessment_citation_roles(evidence)
        evidence_roles = citation_roles["support"] | citation_roles["observation"]
        allowed = set(provider.scientific_check_ids(options.values()))
        if (version.scope_digest != assessment["scope_digest"]
                or version.input_revision != scope.input_revision
                or version.evidence_snapshot_sha256 != digest(evidence)
                or not any(row.evidence_aliases for row in version.hypotheses)
                or any(not (row.evidence_aliases or row.is_evidence_gap)
                    or not set(row.evidence_aliases) <= evidence_roles
                    or not set(row.opposing_evidence_aliases) <= citation_roles["opposition"]
                    or not set(row.missing_evidence_aliases) <= citation_roles["missing"]
                    or (row.discriminating_check is not None and row.discriminating_check not in allowed)
                    for row in version.hypotheses)):
            return None, "report_handoff_stale"
        report = next((row for row in options.values()
            if (row["tool_id"], row["mode_id"]) == ("P0-10", "default")), None)
        if report is None:
            return None, "report_candidate_unavailable"
        refs = {ref.role: ref for ref in report["request"].object_inputs}
        graph_ref, context_ref = refs.get("evidence_graph_manifest"), refs.get("research_report_context")
        graph = state.get("_input_objects", {}).get(graph_ref.input_id) if graph_ref else None
        if (graph is None or context_ref is None or graph["sha256"] != graph_ref.sha256):
            return None, "report_handoff_stale"
        receipt = next((row for row in state.get("_tool_runs", [])
            if row["file"] == graph.get("receipt_file")
            and row["sha256"] == graph.get("receipt_sha256")
            and row["tool_id"] == "P0-09" and row["state"] in {"succeeded", "partial"}
            and row["file"] not in state.get("_invalidated_receipts", {})), None)
        if receipt is None or not any(
                row["alias"] == "E-" + receipt["sha256"][:16] and row["state"] == "available"
                for row in evidence):
            return None, "report_handoff_stale"
        try:
            context = parse_research_context(self.service.inputs.verify(
                state, state["_input_objects"][context_ref.input_id]))
        except (ValueError, OSError, KeyError):
            return None, "report_handoff_stale"
        if (context.graph_manifest_sha256 != graph["sha256"]
                or not context.explanation_versions
                or context.explanation_versions[-1].content_sha256 != version.content_sha256):
            return None, "report_handoff_stale"
        return report, None

    def _admit_candidate(self, state, assessment, scope, offered):
        """Recheck one offered request and reuse the existing scope-derived plan path."""
        if offered["tool_id"] == "P0-10":
            refs = {ref.role: ref for ref in offered["request"].object_inputs}
            if "research_report_context" in refs:
                from .research_context import selected_report_context_key
                key = selected_report_context_key(state, scope, refs["evidence_graph_manifest"].sha256)
                state.setdefault("_selected_report_contexts", {})[key] = refs["research_report_context"].input_id
        current = self.service.inputs.assessment_candidates(state, scope)
        used = {row["fingerprint"] for row in assessment["admissions"]}
        candidate = next((row for row in current
            if row["fingerprint"] == offered["fingerprint"] and row["request"] is not None
            and not row["blockers"] and row["fingerprint"] not in used), None)
        if candidate is None:
            self._finish(state, "candidate_changed", status="blocked")
            return False
        self.service.propose_request(state, candidate["bundle"], candidate["request"],
            "范围内的精确检查；沿用原始范围授权，不产生新的科学审批。", scope_admission=True)
        plan = AnalysisPlan.model_validate(state["_plan"])
        if not any(step.disposition.value == "execute" for step in plan.steps):
            self._finish(state, "package_not_eligible", status="blocked")
            return False
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
        for row in assessment["candidates"]:
            if (row["tool_id"], row["mode_id"]) == (candidate["tool_id"], candidate["mode_id"]):
                row.update(runnable=False, already_admitted=True)
        state["status"] = "running"
        self.service.sessions.save(state)
        return True

    def _complete_admission(self, sid, epoch, *, report_handoff=False):
        self.service.execution.execute(sid, epoch)
        with self.service.lock:
            state = self.service.load(sid)
            if state["_control_epoch"] != epoch:
                return False
            assessment = state["_assessment"]
            if assessment["status"] != "running":
                return False
            assessment["admissions"][-1]["state"] = state["plan"]["status"]
            if (state["plan"]["status"] not in {"completed", "partial"}
                    or (report_handoff and state["plan"]["status"] != "completed")):
                self._finish(state, "tool_execution_failed", status="blocked")
                return False
            if report_handoff:
                self._finish(state, "report_complete")
                return False
            self.service.sessions.save(state)
            return True

    def _maybe_resume_report(self, sid, epoch):
        with self.service.qc.catalog(), self.service.lock:
            state = self.service.load(sid)
            assessment = state["_assessment"]
            scope = AssessmentScope.model_validate(assessment["scope"])
            previous = (assessment.get("stop_events") or [{}])[-1]
            if not scope.report_after_explanation or previous.get("reason") != "explanation_complete":
                return False
            reason = self.check(state, epoch)
            if reason:
                if state["_control_epoch"] == epoch:
                    self._finish(state, reason, status="blocked")
                return True
            if assessment["tool_runs_used"] >= scope.max_tool_runs:
                self._finish(state, "report_handoff_budget_exhausted", status="blocked")
                return True
            candidates = self.service.inputs.assessment_candidates(state, scope)
            used = {row["fingerprint"] for row in assessment["admissions"]}
            options = {secrets.token_hex(32): row for row in candidates
                if row["request"] is not None and not row["blockers"] and row["fingerprint"] not in used}
            self._candidate_state(assessment, candidates)
            from .evidence import assessment_evidence
            evidence, _ = assessment_evidence(self.service.inputs, state, assessment)
            report, error = self._report_resume_candidate(state, assessment, scope, options, evidence)
            if (error == "report_candidate_unavailable"
                    and not any(row["tool_id"] == "P0-09" and row["state"] == "available"
                                for row in evidence)
                    and any((row["tool_id"], row["mode_id"]) in {
                        ("P0-08", "default"), ("P0-09", "case_initial_v2")}
                        for row in options.values())):
                # A valid early explanation is not an execution dead end. Return
                # to the existing bounded planner; never dispatch a prerequisite
                # here or rebind this historical explanation to a future graph.
                return False
            if error:
                self._finish(state, error, status="blocked")
                return True
            if report is None:
                self._finish(state, "report_handoff_stale", status="blocked")
                return True
            if not self._admit_candidate(state, assessment, scope, report):
                return True
        self._complete_admission(sid, epoch, report_handoff=True)
        return True

    @staticmethod
    def _public_literature(assessment):
        from .literature import public_context
        return public_context(assessment, AssessmentScope.model_validate(assessment["scope"]))

    def _advance_literature(self, sid, epoch, scope_id, action, skill_receipts, provider_calls):
        from . import literature
        with self.service.qc.catalog(), self.service.lock:
            state = self.service.load(sid)
            reason = self.check(state, epoch)
            if reason or state["_assessment"]["scope"]["scope_id"] != scope_id:
                if state["_control_epoch"] == epoch and reason:
                    self._finish(state, reason, status="blocked")
                return False
            assessment = state["_assessment"]
            scope = AssessmentScope.model_validate(assessment["scope"])
            turn = assessment["model_turns"][-1]
            turn["state"] = "received"
            self.service.sessions.record_skill_usage(state, skill_receipts,
                action="assessment", purpose="assessment", provider_calls=provider_calls)
            try:
                reservation = literature.reserve(assessment, scope, action.decision.model_dump(mode="json"))
            except ValueError:
                self._finish(state, "unavailable_or_repeated_action", status="blocked")
                return False
            turn["decision"] = action.decision.model_dump(mode="json")
            self.service.sessions.save(state)
        # No catalog or session lock spans a public network request.
        result = literature.execute(reservation)
        with self.service.qc.catalog(), self.service.lock:
            state = self.service.load(sid)
            reason = self.check(state, epoch)
            if reason or state["_assessment"]["scope"]["scope_id"] != scope_id:
                if state["_control_epoch"] == epoch and reason:
                    self._finish(state, reason, status="blocked")
                return False
            literature.complete(state["_assessment"], reservation, result)
            self.service.sessions.save(state)
        return True

    def _interpretation_graph_ref(self, state, evidence):
        """Pin the unique current graph among the exact shared, verified receipts."""
        aliases = {row["alias"] for row in evidence
                   if row.get("tool_id") == "P0-09" and row.get("state") == "available"}
        refs = {}
        for record in state.get("_input_objects", {}).values():
            if (record.get("schema_ref") != "bridge://schemas/case-evidence-graph-manifest/v0.1"
                    or "E-" + (record.get("receipt_sha256") or "")[:16] not in aliases):
                continue
            graph = self.service.inputs.verify(state, record)
            ref = {"graph_id": graph["graph_id"], "graph_version": graph["graph_version"],
                   "graph_manifest_sha256": record["sha256"]}
            refs[(ref["graph_id"], ref["graph_version"], ref["graph_manifest_sha256"])] = ref
        if not refs or len({key[0] for key in refs}) != 1:
            return None
        latest = max(key[1] for key in refs)
        matches = [ref for key, ref in refs.items() if key[1] == latest]
        return matches[0] if len(matches) == 1 else None

    def _review_interpretation(self, sid, epoch, scope_id, decision, context, *, reserved=False):
        from . import provider
        from .interpretation_review import PROMPT, completeness_issues, parse_review, safe_issues
        from bridge.toolkit.interpretation import bind_hypotheses
        with self.service.qc.catalog(), self.service.lock:
            state = self.service.load(sid)
            reason = self.check(state, epoch)
            if reason or state["_assessment"]["scope"]["scope_id"] != scope_id:
                if reason and state["_control_epoch"] == epoch:
                    self._finish(state, reason, status="blocked")
                return False
            assessment = state["_assessment"]
            if not reserved and assessment["model_turns_used"] >= assessment["scope"]["max_model_turns"]:
                self._finish(state, "model_turn_budget_exhausted")
                return False
            proposal = assessment["model_turns"][-1]
            # Reserve the latest validated draft atomically with the review turn.
            # A process restart during I/O must not recover an older proposal.
            hypotheses = [row.model_dump(mode="json") for row in decision.hypotheses]
            bindings = proposal["provider_bindings"]["evidence"]
            assessment["pending_revision"] = {
                "hypotheses": bind_hypotheses(hypotheses, bindings), "issues": []}
            if self.service.settings.share_result_summaries:
                facts = self.service.intake.feature_coverage(state, AssessmentScope.model_validate(assessment["scope"]), hypotheses)
                assessment["feature_coverage"] = facts
                context["feature_coverage"] = facts
            incomplete = completeness_issues(hypotheses)
            if incomplete:
                assessment["pending_revision"]["issues"] = incomplete
                proposal.update(provider_error_code="provider_text_unverified",
                    provider_error_detail={"category": "interpretation_review", "issues": safe_issues(incomplete)})
                self._finish(state, "provider_action_invalid_or_unavailable", status="blocked")
                return False
            if not reserved:
                assessment["model_turns_used"] += 1
                assessment["model_turns"].append({
                    "number": assessment["model_turns_used"], "state": "dispatched",
                    "phase": "interpretation_review", "proposal_turn": proposal["number"]})
            # Ordinary reviews use their proposal's immutable maps. A retry has
            # fresh maps on its own already-reserved turn, without regenerating.
            assessment["model_turns"][-1].update(state="dispatched",
                review_policy_sha256=hashlib.sha256(PROMPT.encode()).hexdigest())
            self.service.sessions.save(state)
        # Review is a separately reserved model turn. No session/catalog lock
        # spans I/O. Rejected prose may enter only the private pending revision.
        try:
            result = parse_review(provider.review_interpretation(
                self.service.settings, hypotheses, context), hypotheses)
            error = None
        except Exception as failure:
            result, error = None, failure
        with self.service.qc.catalog(), self.service.lock:
            state = self.service.load(sid)
            reason = self.check(state, epoch)
            if reason or state["_assessment"]["scope"]["scope_id"] != scope_id:
                if reason and state["_control_epoch"] == epoch:
                    self._finish(state, reason, status="blocked")
                return False
            turn = state["_assessment"]["model_turns"][-1]
            turn["state"] = "received"
            # Invalid or unavailable reviews never contribute findings.
            state["_assessment"]["pending_revision"]["issues"] = (
                result["issues"] if result is not None else [])
            if error is not None:
                turn.update(review_outcome="unavailable",
                    provider_error_code="provider_action_invalid_or_unavailable",
                    provider_error_detail=provider.failure_detail(error))
                self._finish(state, "provider_action_invalid_or_unavailable", status="blocked")
                return False
            if result["issues"]:
                turn.update(review_outcome="issues_found", provider_error_code="provider_text_unverified",
                    provider_error_detail={"category": "interpretation_review",
                        "issues": safe_issues(result["issues"])})
                self._finish(state, "provider_action_invalid_or_unavailable", status="blocked")
                return False
            state["_assessment"].pop("pending_revision", None)
            turn["review_outcome"] = "no_issue_detected"
            self.service.sessions.save(state)
        return True

    def advance(self, sid, epoch):
        if self._maybe_resume_report(sid, epoch):
            return
        from . import provider
        from .evidence import assessment_evidence, assessment_model_evidence
        while True:
            with self.service.qc.catalog(), self.service.lock:
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
                options = {secrets.token_hex(32): row for row in candidates
                           if row["request"] is not None and not row["blockers"] and row["fingerprint"] not in used}
                self._candidate_state(assessment, candidates)
                if scope.report_after_explanation:
                    # Consent asks for a report after an accepted explanation and
                    # explicit continuation, not on this model-selected turn.
                    options = {key: row for key, row in options.items() if row["tool_id"] != "P0-10"}
                evidence, bindings = assessment_evidence(self.service.inputs, state, assessment)
                if not options and not any(row["state"] == "available" for row in evidence):
                    self._finish(state, "no_eligible_check", status="blocked")
                    return
                shared = self.service.settings.share_result_summaries
                model_evidence, provider_bindings = assessment_model_evidence(evidence if shared else [])
                provider_bindings["options"] = {key: row["fingerprint"] for key, row in options.items()}
                model_options = []
                for key, row in options.items():
                    spec = self.service.registry.describe(row["tool_id"])
                    model_options.append({"id": key, "tool_id": row["tool_id"], "mode_id": row["mode_id"],
                        "kind": "query" if row["mode_id"] == "case_query" else "check",
                        "name": spec.name, "summary": spec.summary, "scientific_status": spec.scientific_status,
                        "execution_state": "not_executed_in_scope", "prerequisites_state": "satisfied_this_turn"})
                from .assessment_prompt import biological_context
                context = {"purpose": "assessment", "question": scope.question, "options": model_options,
                    "biological_context": biological_context(scope) if shared else {"source": "not_shared", "facts": {}},
                    "allowed_modes": [mode.model_dump(mode="json") for mode in scope.allowed_modes],
                    "evidence": model_evidence, "results_sent_to_model": shared and bool(evidence),
                    "blockers": [{"tool_id": row["tool_id"], "mode_id": row["mode_id"], "reason_codes": row["blockers"]}
                        for row in assessment["candidates"] if row["blockers"]],
                    "interpretation_gaps": [{"tool_id": row["tool_id"], "mode_id": row["mode_id"], "reason_codes": row["gaps"]}
                        for row in assessment["candidates"] if row["gaps"]]}
                if scope.report_after_explanation:
                    context["report_after_explanation"] = True
                    if not any(row["tool_id"] == "P0-09" and row["state"] == "available"
                               for row in evidence):
                        context["report_preparation"] = {
                            "state": "graph_required",
                            "explanation_after_graph_required": True,
                        }
                from .literature import model_context as literature_context
                context["literature"] = literature_context(assessment, scope)
                if shared and assessment.get("feature_coverage") is not None:
                    context["feature_coverage"] = assessment["feature_coverage"]
                handoff = self._report_handoff(state, assessment, scope, options, evidence)
                if handoff is not None:
                    context["workflow_handoff"] = handoff
                previous_stop = (assessment.get("stop_events") or [{}])[-1]
                if (previous_stop.get("model_turns_used") == assessment["model_turns_used"]
                        and previous_stop.get("reason") in {
                            "provider_explanation_too_long", "provider_action_invalid_or_unavailable",
                            "invalid_evidence_alias"}):
                    last_turn = (assessment.get("model_turns") or [{}])[-1]
                    code = last_turn.get("provider_error_code")
                    context["previous_action_error"] = (code if code in {
                        "structured_hypotheses_required", "provider_text_unverified"}
                        else previous_stop["reason"])
                    detail = last_turn.get("provider_error_detail")
                    if (previous_stop["reason"] == "invalid_evidence_alias"
                            and isinstance(detail, dict)
                            and detail.get("category") in {
                                "support_not_available", "opposition_not_available",
                                "missing_not_unavailable", "support_opposition_overlap"}
                            and type(detail.get("count")) is int and 0 < detail["count"] <= 24):
                        context["previous_action_error_detail"] = {
                            "category": detail["category"], "count": detail["count"]}
                    elif (previous_stop["reason"] in {
                            "provider_action_invalid_or_unavailable", "provider_explanation_too_long"}
                            and isinstance(detail, dict)
                            and detail.get("category") in provider.PROVIDER_ERROR_CATEGORIES):
                        context["previous_action_error_detail"] = {"category": detail["category"]}
                        if (detail["category"] == "http_status"
                                and type(detail.get("status_code")) is int
                                and 400 <= detail["status_code"] <= 599):
                            context["previous_action_error_detail"]["status_code"] = detail["status_code"]
                        if detail["category"] == "action_schema" and "issues" in detail:
                            context["previous_action_error_detail"]["issues"] = provider.safe_schema_issues(detail["issues"])
                    elif code == "provider_text_unverified" and isinstance(detail, dict):
                        category = detail.get("category")
                        if category == "interpretation_review":
                            from .interpretation_review import safe_issues
                            issues = detail.get("issues", [])
                            context["previous_action_error_detail"] = {"category": category,
                                "issues": safe_issues(issues) if isinstance(issues, list) else []}
                        elif category == "hypothesis_text_citations":
                            fields = detail.get("fields", {})
                            context["previous_action_error_detail"] = {"category": category, "fields": {
                                field: fields[field] for field in ("statement", "competing_explanation", "expected_observation")
                                if isinstance(fields, dict) and type(fields.get(field)) is int and 0 < fields[field] <= 3}}
                        elif category == "explanation_citation_mismatch" and all(
                                type(detail.get(key)) is int and 0 <= detail[key] <= 2400
                                for key in ("missing_count", "extra_count")):
                            context["previous_action_error_detail"] = {key: detail[key] for key in (
                                "category", "missing_count", "extra_count")}
                        elif category == "question_text_unverified":
                            context["previous_action_error_detail"] = {"category": category}
                if shared and assessment.get("pending_revision"):
                    from .interpretation_review import revision_context
                    revision = revision_context(assessment["pending_revision"], provider_bindings)
                    if revision is not None:
                        context["revision"] = revision
                    else:
                        assessment.pop("pending_revision", None)
                last_turn = (assessment.get("model_turns") or [{}])[-1]
                retry_review = bool(context.get("revision")
                    and not context["revision"]["issues"]
                    and last_turn.get("phase") == "interpretation_review"
                    and last_turn.get("review_outcome") in {None, "unavailable"})
                proposal_turn = last_turn.get("proposal_turn") if retry_review else None
                dispatch_context = provider.assessment_wire_context(provider.interpretation_revision_context(context))
                if len(json.dumps(dispatch_context, ensure_ascii=False, separators=(",", ":")).encode()) > 128 * 1024:
                    self._finish(state, "evidence_context_limit", status="blocked")
                    return
                if evidence and not shared:
                    self._finish(state, "result_sharing_disabled", status="blocked")
                    return
                assessment["model_turns_used"] += 1
                assessment["model_turns"].append({"number": assessment["model_turns_used"],
                    "state": "dispatched", "evidence_bindings": bindings if shared else {},
                    "provider_bindings": provider_bindings})
                if retry_review:
                    assessment["model_turns"][-1].update(phase="interpretation_review",
                        review_retry=True, proposal_turn=proposal_turn)
                self.service.sessions.save(state)
            try:
                if retry_review:
                    action = provider.Action.model_validate({"action": "assessment", "decision": {
                        "action": "explain", "hypotheses": context["revision"]["hypotheses"]}})
                    skill_receipts, provider_calls = [], 0
                else:
                    action = provider.converse(self.service.settings,
                        [{"role": "user", "content": (
                            "Revise the existing interpretation to address each exact finding. "
                            "Remove numerical inventories already shown in tables. Lead with concise conditional "
                            "biological reasoning, not a restatement of measured values. Correct unsupported factual "
                            "premises, not just their caveats. Check dependent rivals and predictions: general lineage "
                            "patterns do not predict a specific regional identity; regional checks test an additional "
                            "possibility. Preserve valid citations and supported content; return complete hypotheses "
                            "in the assessment action envelope."
                            if context.get("revision") else "Select the next authorized evidence action.")}], context)
                    skill_receipts, provider_calls = action._skill_receipts, action._provider_calls
                action = provider.Action.model_validate(action.model_dump(mode="json"))
                if action.action != "assessment":
                    raise ValueError("model_action_purpose_mismatch")
            except Exception as error:
                reason = "provider_action_invalid_or_unavailable"
                cause = error.__cause__ or error
                if isinstance(cause, ValidationError):
                    errors = cause.errors(include_url=False, include_context=False, include_input=False)
                    if (len(errors) == 1 and errors[0]["loc"] == ("decision", "text")
                            and errors[0]["type"] == "string_too_long"):
                        reason = "provider_explanation_too_long"
                with self.service.lock:
                    state = self.service.load(sid)
                    if state["_control_epoch"] == epoch:
                        state["_assessment"]["model_turns"][-1].update(
                            provider_error_code=reason, provider_error_detail=provider.failure_detail(error))
                        self._finish(state, reason, status="blocked")
                return
            if action.decision.action in {"search_literature", "read_literature"}:
                if not self._advance_literature(sid, epoch, scope.scope_id, action, skill_receipts, provider_calls):
                    return
                continue
            with self.service.qc.catalog(), self.service.lock:
                state = self.service.load(sid)
                reason = self.check(state, epoch)
                if reason:
                    if state["_control_epoch"] == epoch:
                        self._finish(state, reason, status="blocked")
                    return
                assessment = state["_assessment"]
                assessment["model_turns"][-1]["state"] = "received"
                self.service.sessions.record_skill_usage(state, skill_receipts,
                    action=action.action, purpose="assessment", provider_calls=provider_calls)
                decision = action.decision
                if decision.action == "explain" and context["literature"].get("read_before_explanation"):
                    assessment["model_turns"][-1]["provider_error_code"] = "literature_read_required"
                    self._finish(state, "provider_action_invalid_or_unavailable", status="blocked")
                    return
                citation_choices = provider._citation_choices(context["evidence"])
                support_aliases = set(citation_choices["evidence_aliases"])
                opposition_aliases = set(citation_choices["opposing_evidence_aliases"])
                missing_aliases = set(citation_choices["missing_evidence_aliases"])
                def reject_alias(category, count):
                    # No rejected text, alias or stable source ID is retained.
                    assessment["model_turns"][-1].update(
                        provider_error_code="invalid_evidence_alias",
                        provider_error_detail={"category": category, "count": count})
                    self._finish(state, "invalid_evidence_alias", status="blocked")

                for hypothesis in decision.hypotheses:
                    checks = (
                        ("support_opposition_overlap",
                         set(hypothesis.evidence_aliases) & set(hypothesis.opposing_evidence_aliases)),
                        ("support_not_available", set(hypothesis.evidence_aliases) - support_aliases),
                        ("opposition_not_available", set(hypothesis.opposing_evidence_aliases) - opposition_aliases),
                        ("missing_not_unavailable", set(hypothesis.missing_evidence_aliases) - missing_aliases),
                    )
                    for category, invalid in checks:
                        if invalid:
                            reject_alias(category, len(invalid))
                            return
                read_sources = {row["source_ref"] for row in context["literature"]["sources"]
                                if row["content_level"] == "abstract"}
                if any(not scope.literature_enabled or use.source_ref not in read_sources
                       for hypothesis in decision.hypotheses for use in hypothesis.literature_support):
                    self._finish(state, "invalid_literature_reference", status="blocked")
                    return
                scientific_checks = set(provider.scientific_check_ids(context["options"]))
                if any(hypothesis.discriminating_check is not None
                       and hypothesis.discriminating_check not in scientific_checks
                       for hypothesis in decision.hypotheses):
                    self._finish(state, "hypothesis_check_outside_scope", status="blocked")
                    return
                if (decision.action == "explain" and (support_aliases or missing_aliases or scope.literature_enabled)
                        and not decision.hypotheses):
                    # Usable evidence and literature-enabled scopes require the
                    # structured, citation-checked hypothesis contract. Free text alone
                    # cannot become a traceable interpretation or later report input.
                    assessment["model_turns"][-1]["provider_error_code"] = "structured_hypotheses_required"
                    self._finish(state, "provider_action_invalid_or_unavailable", status="blocked")
                    return
                cited_fields = {field: sum(not provider.proposed_hypothesis_text_is_unbound(getattr(hypothesis, field))
                    for hypothesis in decision.hypotheses)
                    for field in ("statement", "competing_explanation", "expected_observation")}
                if any(cited_fields.values()):
                    assessment["model_turns"][-1].update(provider_error_code="provider_text_unverified",
                        provider_error_detail={"category": "hypothesis_text_citations",
                            "fields": {field: count for field, count in cited_fields.items() if count}})
                    self._finish(state, "provider_action_invalid_or_unavailable", status="blocked")
                    return
                self.service.sessions.save(state)
            needs_review = scope.literature_enabled or any(h.evidence_relations or h.feature_queries for h in decision.hypotheses)
            if (needs_review and decision.action == "explain" and decision.hypotheses
                    and not self._review_interpretation(sid, epoch, scope.scope_id, decision, context, reserved=retry_review)):
                return
            with self.service.qc.catalog(), self.service.lock:
                state = self.service.load(sid)
                reason = self.check(state, epoch)
                if reason or state["_assessment"]["scope"]["scope_id"] != scope.scope_id:
                    if reason and state["_control_epoch"] == epoch:
                        self._finish(state, reason, status="blocked")
                    return
                assessment = state["_assessment"]
                # Structured statements are the sole source of an interpretation.
                # Never attach their union of references to unrelated provider prose.
                admitted_text = None if decision.hypotheses else decision.text
                if admitted_text is not None:
                    explanation_valid = not provider.provider_citations(admitted_text)
                    if decision.action == "question":
                        admitted_text, source = provider.admit_provider_text(admitted_text, context)
                        explanation_valid = source == "provider_admitted"
                    if not explanation_valid:
                        actual_aliases = provider.provider_citations(admitted_text)
                        detail = ({"category": "question_text_unverified"} if decision.action == "question" else
                                  {"category": "explanation_citation_mismatch",
                                   "missing_count": 0,
                                   "extra_count": len(actual_aliases)})
                        assessment["model_turns"][-1].update(provider_error_code="provider_text_unverified",
                            provider_error_detail=detail)
                        self._finish(state, "provider_action_invalid_or_unavailable", status="blocked")
                        return
                    admitted_text = provider.bind_provider_citations(
                        admitted_text, provider_bindings["evidence"])
                if decision.reason == "evidence_requirements_reached":
                    # Scope consent authorizes checks, not a completion contract.
                    # Even satisfied graph-local requirements cannot establish the
                    # approved research question is complete; an absent contract
                    # is unavailable, never a vacuously satisfied empty set.
                    assessment["model_turns"][-1]["decision"] = decision.model_dump(mode="json")
                    self._finish(state, "completion_contract_unavailable", status="blocked")
                    return
                from bridge.toolkit.interpretation import bind_hypotheses
                hypotheses = bind_hypotheses([row.model_dump(mode="json",
                    exclude=set() if scope.literature_enabled else {"literature_support"})
                    for row in decision.hypotheses], provider_bindings["evidence"])
                if hypotheses:
                    admitted_text = provider.render_assessment_hypotheses(hypotheses)
                admitted_decision = decision.model_dump(mode="json")
                admitted_decision["text"] = admitted_text
                admitted_decision["hypotheses"] = hypotheses
                interpretation_version = None
                if hypotheses:
                    # Check/query turns without a new interpretation must not create
                    # empty versions. Current hypotheses clear on a new action;
                    # prior cited explanations remain in versioned history.
                    interpretation = {
                        "object_version": "1.0.0", "scope_digest": assessment["scope_digest"],
                        "input_revision": scope.input_revision, "hypotheses": hypotheses,
                        "evidence_snapshot_sha256": digest(evidence),
                        "qualification": "proposed_explanation",
                    }
                    try:
                        if scope.literature_enabled:
                            from .literature import freeze
                            interpretation.update(object_version="1.1.0",
                                biological_context=biological_context(scope),
                                literature=freeze(assessment, scope))
                        if any(row.get("evidence_relations") or row.get("feature_queries") for row in hypotheses):
                            graph_ref = self._interpretation_graph_ref(state, evidence)
                            if graph_ref is None:
                                # A reviewed draft is not publishable without the exact
                                # graph its report and visualization will consume.
                                assessment["pending_revision"] = {"hypotheses": hypotheses, "issues": []}
                                self._finish(state, "interpretation_graph_binding_unavailable", status="blocked")
                                return
                            interpretation.update(object_version="1.2.0",
                                feature_coverage=assessment.get("feature_coverage"),
                                graph_ref=graph_ref)
                            interpretation.setdefault("biological_context", biological_context(scope))
                            interpretation.setdefault("literature", None)
                            for row in hypotheses:
                                row.setdefault("literature_support", [])
                                row.setdefault("evidence_relations", [])
                                row.setdefault("feature_queries", [])
                        signature = digest(interpretation)
                        versions = assessment.get("interpretation_versions", [])
                        candidate = {**interpretation, "version": len(versions) + 1,
                            "content_sha256": signature,
                            "predecessor_sha256": versions[-1]["content_sha256"] if versions else None,
                            "created_at": datetime.now(timezone.utc).isoformat()}
                        if scope.literature_enabled or interpretation["object_version"] == "1.2.0":
                            from bridge.tool_packages.p0_10_claim_verifier.research import parse_research_explanation
                            parse_research_explanation(candidate)
                    except ValueError as error:
                        assessment["model_turns"][-1].update(
                            provider_error_code="provider_action_invalid_or_unavailable",
                            provider_error_detail=provider.failure_detail(error))
                        self._finish(state, "provider_action_invalid_or_unavailable", status="blocked")
                        return
                    if not versions or versions[-1]["content_sha256"] != signature:
                        versions.append(candidate)
                    assessment["interpretation_versions"] = versions
                    interpretation_version = versions[-1]
                assessment["model_turns"][-1]["decision"] = admitted_decision
                assessment["hypotheses"] = hypotheses
                if decision.action in {"stop", "question", "explain"}:
                    if admitted_text:
                        self.service.message(
                            state,
                            "assistant",
                            admitted_text,
                            source="provider_admitted",
                        )
                        if decision.action == "explain" and interpretation_version is not None:
                            message = state["messages"][-1]
                            message["qualification"] = "proposed_explanation"
                            message["evidence_refs"] = sorted({alias for row in hypotheses for alias in (
                                *row["evidence_aliases"],
                                *row["opposing_evidence_aliases"],
                                *row["missing_evidence_aliases"],
                            )})
                            message["interpretation_ref"] = {
                                "scope_digest": interpretation_version["scope_digest"],
                                "version": interpretation_version["version"],
                                "content_sha256": interpretation_version["content_sha256"],
                            }
                    elif (decision.action == "stop" and decision.reason == "no_discriminating_check"
                            and scope.report_after_explanation):
                        self.service.message(state, "assistant",
                            "已有测量仍可查看，但本轮未形成可引用的解释，因此不会据此生成新报告。"
                            "没有新的鉴别检查不代表已有观察无效；如只需整理观察与限制，可以继续提问。",
                            source="server_template")
                    self._finish(state, decision.reason or ("necessary_fact_required" if decision.action == "question" else "explanation_complete"))
                    return
                candidate = options.get(decision.option_id)
                if candidate is None or (decision.action == "query") != (candidate["mode_id"] == "case_query"):
                    self._finish(state, "unavailable_or_repeated_action", status="blocked")
                    return
                # Preserve the exact offered private report context. This decision
                # may append an interpretation, but cannot rewrite that snapshot or
                # make each report trigger another report from its own history.
                if not self._admit_candidate(state, assessment, scope, candidate):
                    return
            if not self._complete_admission(sid, epoch):
                return
