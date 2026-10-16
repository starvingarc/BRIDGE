from __future__ import annotations

import hashlib
import re
from importlib.resources import files

from fastapi import HTTPException

from bridge.domain import CaseInputAsset, CaseInputBundle
from bridge.planner import PlanBuilder
from bridge.storage.private_paths import ensure_private_directory
from bridge.toolkit.contracts import ToolRequest, ToolRequestV2
from bridge.toolkit.registry import ToolRegistry

from . import intake_autofill
from .artifacts import ArtifactStore
from .assessment import AssessmentCoordinator
from .clarification import Clarifications
from .conditional_inputs import ConditionalInputs
from .control import Controls
from .execution import ProviderUnavailable, WebExecution
from .inputs import Inputs, Selection, verify_checked_file
from .intake import Intake, IntakeFacts, IntakeInput
from .model_settings import ModelConfiguration
from .presentation import build_session_presentation, project_user_assessment
from .provider import (
    MESSAGE_SOURCES,
    admit_provider_text,
    build_research_context,
    converse,
    project_public_messages,
    result_observation_choices,
    result_observation_refs,
)
from .qc_results import CATALOG_LOCK, QcResults
from .report_inputs import ReportInputs
from .runtime import Settings
from .scientific_inputs import ScientificInputs
from .sessions import SessionStore, now, private_text, uid

NO_GRAFT_DECLARATION = re.compile(
    r"(?:没有|无|未提供)(?:任何)?(?:移植|graft)(?:数据|证据)?"
    r"|\bno graft (?:data|evidence)(?:,\s*(?:please )?record (?:it as )?not provided)?\b"
    r"|\bgraft data (?:is |was )?not provided\b",
    re.I,
)


NO_GRAFT_UNCERTAIN = re.compile(
    r"[?？]|并非没有|不是没有|不要|取消|停止|撤回|假设|如果|假如"
    r"|\b(?:not without|not no|do not|don.t|cancel|stop|if|suppose)\b",
    re.I,
)


PUBLIC = (
    "id",
    "research_id",
    "run_id",
    "conversation_kind",
    "title",
    "updated_at",
    "archived",
    "model_configuration",
    "model_selection",
    "status",
    "messages",
    "uploads",
    "plan",
    "artifacts",
    "error",
    "plan_history",
    "capabilities",
    "input_review_required",
    "pending_input_change",
)


class Service:
    """Coordinate domain decisions; persistence, artifacts and workers own their behavior."""

    def __init__(self, settings: Settings):
        from .account_admin import validate_storage
        validate_storage(settings.storage_root)
        self.sessions = SessionStore(settings.storage_root, settings.runtime_environment)
        self.root = self.sessions.root
        from .accounts import AccountStore
        from .access import SessionAccess
        from .quotas import UserQuotas
        self.accounts = AccountStore(self.root, settings.cookie_ttl)
        self.access = SessionAccess(self.sessions)
        from .researches import ResearchStore
        self.researches = ResearchStore(self.sessions)
        from .research_objects import ResearchObjectStore
        self.research_objects = ResearchObjectStore(self.researches)
        self.quotas = UserQuotas(self.sessions, settings, self.researches)
        self.model_configuration = ModelConfiguration(self.root, settings)
        self.lock = self.sessions.lock
        self.uploads_in_progress: set[str] = set()
        self.registry = ToolRegistry.load_default()
        self.qc = QcResults(self.sessions, lambda: self.settings.max_upload_bytes)
        self.inputs = Inputs(self)
        self.controls = Controls(self)
        self.assessment = AssessmentCoordinator(self)
        self.intake = Intake(self)
        self.clarifications = Clarifications(self)
        self.scientific_inputs = ScientificInputs(self)
        self.report_inputs = ReportInputs(self)
        self.conditional_inputs = ConditionalInputs(self, check_cohort=lambda state, selection, binding:
            self.cohort_comparisons.validate_binding(state, selection, binding))
        self.artifacts = ArtifactStore(self.sessions, self.inputs)
        from .sample_qc import SampleQcResults
        self.sample_qc = SampleQcResults(researches=self.researches, objects=self.research_objects, registry=self.registry)
        from .sample_cell_cycle import SampleCellCycleResults
        self.sample_cell_cycle = SampleCellCycleResults(
            researches=self.researches, objects=self.research_objects, registry=self.registry)
        from .sample_cell_atlas import SampleCellAtlasResults
        self.sample_cell_atlas = SampleCellAtlasResults(
            researches=self.researches, objects=self.research_objects, registry=self.registry)
        from .sample_analyses import SampleAnalyses
        self.sample_analyses = SampleAnalyses(researches=self.researches, objects=self.research_objects,
            sessions=self.sessions, inputs=self.inputs, artifacts=self.artifacts,
            max_upload_bytes=settings.max_upload_bytes, qc_results=self.sample_qc,
            cell_cycle_results=self.sample_cell_cycle, cell_atlas_results=self.sample_cell_atlas)
        from .analysis_cohorts import AnalysisCohorts
        self.analysis_cohorts = AnalysisCohorts(researches=self.researches,
            get_analysis=self.sample_analyses.get, lock=self.lock)
        from .cohort_comparison import CohortComparisons
        self.cohort_comparisons = CohortComparisons(sessions=self.sessions,
            get_cohort=self.analysis_cohorts.get, get_analysis=self.sample_analyses.get,
            get_sample=self.research_objects.sample,
            read_object=self.conditional_inputs.verified_object,
            propose=self.conditional_inputs.propose, lock=self.lock)
        from .research_context import resolve_display_source, EXPRESSION_PLOT_LIMIT
        from .inputs import checked_bytes
        from .spatial_context import SpatialContexts
        self.spatial_contexts = SpatialContexts(
            resolve_source=lambda state, aid: resolve_display_source(
                self, state, aid, payload_limit=EXPRESSION_PLOT_LIMIT),
            read_artifact=lambda state, aid: self.artifacts.read(state, aid),
            checked_bytes=lambda state, path, sha: checked_bytes(self, state, path, sha),
            manifest_path=lambda: self.settings.spatial_reference_manifest_path,
        )
        self.execution = WebExecution(
            sessions=self.sessions,
            load_state=self.load,
            assessment=self.assessment,
            controls=self.controls,
            inputs=self.inputs,
            artifacts=self.artifacts,
            check_plan=self.verify_scientific_plan,
            message=self.message,
            qc_catalog=self.qc.catalog,
            max_upload_bytes=settings.max_upload_bytes,
            task_context=lambda owner, selection: self.model_configuration.task_context(owner, selection),
            quotas=self.quotas,
            after_settle=self.sample_workflow_settled,
        )
        self.execution.recover()
        from .atlas_mapping import AtlasMapping
        self.atlas_mapping = AtlasMapping(self.research_objects, self.researches, lambda: self.settings,
                                          self.quotas, self.registry, prepare_analysis=self.sample_analyses.prepare_mapping,
                                          register_qc=self.sample_analyses.register_qc,
                                          register_cell_cycle=self.sample_analyses.register_cell_cycle,
                                          register_cell_atlas=self.sample_analyses.register_cell_atlas,
                                          workflow_issues=self.sample_workflow_issues,
                                          handoff=self.handoff_sample)
        from .sample_questions import SampleQuestions
        self.sample_questions = SampleQuestions(self.research_objects, self.intake.observed, self.message)
        self.research_objects.recover_mappings()
        self.research_objects.backfill_qc_analyses(self.sample_analyses.register_qc)
        self.research_objects.backfill_qc_analyses(self.sample_analyses.register_cell_cycle)
        self.research_objects.backfill_qc_analyses(self.sample_analyses.register_cell_atlas)
        self.research_objects.backfill_mapping_analyses(self.sample_analyses.prepare_mapping)

    @property
    def settings(self):
        return self.model_configuration.current

    @settings.setter
    def settings(self, value):
        # Preserve the existing in-process configuration interface.
        self.model_configuration.default = value

    def directory(self, sid):
        # Stable input-verification interface shared with existing domain modules.
        return self.sessions.directory(sid)

    def load(self, sid):
        with self.lock:
            state = self.sessions.load(sid)
            self.inputs.initialize(state)
            self.controls.initialize(state)
            if "model_selection" not in state and state.get("owner_id"):
                # Freeze legacy account defaults once; subsequent account choices
                # must not keep changing an existing conversation.
                state["model_selection"] = self.model_configuration.recent_selection(state["owner_id"])
                self.sessions.save(state)
            elif state.get("owner_id") and state["model_selection"].get("effort") is None:
                selection = self.model_configuration.selection_with_default(
                    state["owner_id"], state["model_selection"])
                if selection != state["model_selection"]:
                    state["model_selection"] = selection
                    self.sessions.save(state)
            return state

    def public(self, state):
        pending = self.execution.pending_status(state["id"])
        if pending is not None and state["status"] not in {"thinking", "running", "stopping"}:
            # Publish actionable completion only after task admission resources release.
            state = {**state, "status": pending}
        with self.inputs.verification(state):
            state["capabilities"] = self.capabilities(state)
            value = {key: state.get(key, [] if key == "plan_history" else None) for key in PUBLIC}
            public_artifacts = self.artifacts.public(state)
            value["artifacts"] = public_artifacts
            value["clarifications"] = self.clarifications.public(state)
            value["scientific_drafts"] = self.scientific_inputs.public(state)
            value["conditional_inputs"] = self.conditional_inputs.public(state)
            value["assessment"] = project_user_assessment(self.assessment.public(state))
            presentation = build_session_presentation(
                self,
                {**state, "artifacts": public_artifacts},
            )
            value["presentation"] = presentation.model_dump(mode="json")
            value["error"] = presentation.issue.user_message if presentation.issue else None
            value["messages"] = project_public_messages(state.get("messages", []))
            return value

    def message(self, state, role, content, *, source):
        if source not in MESSAGE_SOURCES or (role == "user") != (source == "user_input"):
            raise ValueError("invalid_message_source")
        state["messages"].append(
            {
                "id": uid(),
                "role": role,
                "content": private_text(content),
                "created_at": now(),
                "source": source,
            }
        )

    def create(self, *, owner_id=None, research_id=None, run_id=None, conversation_kind=None):
        if not isinstance(owner_id, str) or not re.fullmatch(r"[a-f0-9]{32}", owner_id):
            raise ValueError("session_owner_required")
        sid = uid()
        ensure_private_directory(self.root / sid)
        state = {
            "id": sid,
            "research_id": research_id,
            "run_id": run_id,
            "conversation_kind": conversation_kind,
            "model_selection": self.model_configuration.recent_selection(owner_id),
            "title": "New analysis",
            "updated_at": now(),
            "status": "idle",
            "archived": False,
            "messages": [],
            "uploads": [],
            "plan": None,
            "artifacts": [],
            "error": None,
            "_uploads": {},
            "_artifacts": {},
            "_plan": None,
            "plan_history": [],
            "_plan_history": [],
            "_tool_runs": [],
            "_artifact_acknowledgements": {},
        }
        if owner_id is not None:
            state["owner_id"] = owner_id
        self.message(
            state,
            "assistant",
            "这次想研究什么？可以从一个问题开始，也可以先选择研究资料。",
            source="server_template",
        )
        self.controls.initialize(state)
        self.sessions.save(state)
        return state

    def conversation(self, owner_id, research_id, run_id=None, *, create=False):
        """Resolve one owned scope under the same lock as the initial session save."""
        with self.lock:
            self.researches.owned(owner_id, research_id)
            if run_id is not None:
                self.research_objects.run(owner_id, research_id, run_id)
            sid = self.sessions.find_conversation(owner_id, research_id, run_id)
            if sid is not None:
                return self.load(sid)
            if not create:
                raise HTTPException(404, "conversation_not_found")
            return self.create(owner_id=owner_id, research_id=research_id, run_id=run_id,
                               conversation_kind="run" if run_id is not None else "research")

    def manage_session(self, sid, *, archived=None):
        """Archive/restore, or delete after uploads and workers have fully settled."""
        with self.lock:
            try:
                state = self.load(sid)
            except HTTPException as exc:
                if exc.status_code != 404 or archived is not None:
                    raise
                # Retry a directory cleanup that already removed the session from view.
                self.sessions.delete(sid)
                return {"deleted": True}
            self.busy(state)
            if archived is None:
                self.sessions.delete(sid)
                return {"deleted": True}
            state["archived"] = archived
            self.sessions.save(state)
            return {key: state[key] for key in ("id", "title", "updated_at", "status", "archived", "research_id", "run_id", "conversation_kind")}

    def select_research_h5ad(self, owner, rid, sid, mid):
        """The user-selection and sample-handoff paths use the same verified copy."""
        with self.lock:
            state = self.load(sid)
            if state.get("owner_id") != owner or state.get("research_id") != rid:
                raise HTTPException(404, "not_found")
            self.busy(state)
            item = self.researches.material(owner, rid, mid)
            if item["kind"] != "h5ad":
                raise HTTPException(422, "research_metadata_selection_unavailable")
            if any(upload.get("material_id") == mid for upload in state["uploads"]):
                return self.public(state)
            self.controls.require_ready(state)
            if len(state["uploads"]) >= 8:
                raise HTTPException(400, "upload_count_limit")
            aid, started_at = uid(), state["updated_at"]
            destination = self.directory(sid) / "uploads" / (aid + ".h5ad")
            self.uploads_in_progress.add(sid)
        committed = False
        try:
            with self.quotas.reserve_upload(owner, item["size"]):
                self.researches.copy_to(owner, rid, mid, destination)
                with self.lock:
                    state = self.load(sid)
                    if state["updated_at"] != started_at or state["status"] in {"thinking", "running", "stopping"}:
                        raise HTTPException(409, "session_busy")
                    result = self.register_h5ad(state, aid, item["name"], item["size"], item["sha256"],
                                                item["locations"], material_id=mid)
                    committed = True
                    return result
        except (ValueError, OSError):
            raise HTTPException(409, "research_material_unavailable") from None
        finally:
            try:
                if not committed:
                    destination.unlink(missing_ok=True)
            finally:
                with self.lock:
                    self.uploads_in_progress.discard(sid)

    def focus_sample(self, sid, sample_id):
        """Bind an explicit user turn to a sample in the conversation's owned scope."""
        with self.lock:
            state = self.load(sid)
            self.busy(state)
            owner, rid = state["owner_id"], state.get("research_id")
            sample = self.research_objects.sample(owner, rid, sample_id)
            if state.get("run_id") not in {None, sample["run_id"]}:
                raise HTTPException(404, "sample_not_found")
            if not sample["material_id"]:
                raise HTTPException(409, "mapping_material_required")
        self.select_research_h5ad(owner, rid, sid, sample["material_id"])
        with self.lock:
            state = self.load(sid)
            upload = next(row for row in state["uploads"] if row.get("material_id") == sample["material_id"])
            return {"sample_id": sample_id, "material_id": sample["material_id"], "upload_id": upload["id"]}

    def bind_sample_plan(self, state):
        focus = state.get("_sample_workflow_active") or state.get("_sample_turn")
        if not focus or not state.get("plan") or state["plan"]["status"] != "proposed":
            return
        sample = self.research_objects.sample(state["owner_id"], state["research_id"], focus["sample_id"])
        state.setdefault("_sample_plan_bindings", {})[state["plan"]["id"]] = {
            "sample_id": sample["id"], "material_id": sample["material_id"]}
        self.sessions.save(state)

    def sample_workflow_issues(self, owner, rid, aid, mapping_reason):
        from .sample_workflow import result_issues
        return result_issues(owner, rid, aid, qc_results=self.sample_qc,
                             cycle_results=self.sample_cell_cycle, atlas_results=self.sample_cell_atlas,
                             mapping_reason=mapping_reason)

    def handoff_sample(self, owner, rid, sample_id):
        """Persist one bounded handoff; do not let model availability lose basic results."""
        from .sample_analyses import digest
        with self.lock:
            sample = self.research_objects.sample(owner, rid, sample_id)
            workflow = sample.get("workflow")
            if not workflow or not workflow["issues"]:
                return
            token = digest({key: workflow[key] for key in ("attempt_id", "issues")})
            try:
                state = self.conversation(owner, rid, sample["run_id"], create=True)
                queue = state.setdefault("_sample_handoffs", [])
                if any(row["sample_id"] == sample_id and row["token"] == token for row in queue):
                    return
                if len(queue) >= 32:
                    raise HTTPException(409, "conversation_limit")
                queue.append({"sample_id": sample_id, "token": token, "state": "pending"})
                workflow = {**workflow, "session_id": state["id"], "agent_state": "pending"}
                self.research_objects.set_sample_workflow(owner, rid, sample_id, workflow,
                                                         attempt_id=workflow["attempt_id"])
                self.sessions.save(state)
            except HTTPException:
                self.research_objects.set_sample_workflow(owner, rid, sample_id,
                    {**workflow, "agent_state": "unavailable"}, attempt_id=workflow["attempt_id"])
                return
        self.drain_sample_handoffs(state["id"])

    def drain_sample_handoffs(self, sid):
        """Resume a queued handoff when its existing conversation is idle."""
        from .sample_analyses import digest
        with self.lock:
            state = self.load(sid)
            if (state.get("archived") or state["status"] not in {"idle", "failed"}
                    or self.execution.has_pending(sid) or sid in self.uploads_in_progress
                    or state.get("plan", {}) and state["plan"]["status"] in {"proposed", "approved"}):
                return
            owner, rid = state["owner_id"], state["research_id"]
            pending = None
            for candidate in state.get("_sample_handoffs", []):
                if candidate["state"] != "pending":
                    continue
                sample = self.research_objects.sample(owner, rid, candidate["sample_id"])
                workflow = sample.get("workflow")
                if not workflow or digest({key: workflow[key] for key in ("attempt_id", "issues")}) != candidate["token"]:
                    candidate["state"] = "superseded"
                    continue
                pending = candidate
                break
            if pending is None:
                self.sessions.save(state)
                return
            if len(state["messages"]) >= 98:
                pending["state"] = "unavailable"
                self.sessions.save(state)
                self.research_objects.set_sample_workflow(owner, rid, sample["id"],
                    {**workflow, "agent_state": "unavailable"}, attempt_id=workflow["attempt_id"])
                return
            # Reserve this handoff before file I/O so another drain cannot duplicate it.
            pending["state"] = "preparing"
            token = pending["token"]
            self.sessions.save(state)
        try:
            self.select_research_h5ad(owner, rid, sid, sample["material_id"])
            with self.lock:
                state = self.load(sid)
                self.busy(state)
                pending = next(row for row in state["_sample_handoffs"] if row["sample_id"] == sample["id"] and row["token"] == token)
                if pending["state"] != "preparing":
                    return  # A stop during preparation revoked this queued handoff.
                current = self.research_objects.sample(owner, rid, sample["id"])
                workflow = current["workflow"]
                if digest({key: workflow[key] for key in ("attempt_id", "issues")}) != token:
                    pending["state"] = "superseded"
                    self.sessions.save(state)
                    return self.drain_sample_handoffs(sid)
                self.message(state, "assistant", "样本基础分析需要补充信息或判断：" +
                    "；".join(row["message"] for row in workflow["issues"][:4]), source="server_template")
                upload = next(row for row in state["uploads"] if row.get("material_id") == sample["material_id"])
                pending.update(state="scheduled", upload_id=upload["id"], message_id=state["messages"][-1]["id"])
                state["_sample_workflow_active"] = dict(pending)
                self.research_objects.set_sample_workflow(owner, rid, sample["id"],
                    {**workflow, "agent_state": "scheduled"}, attempt_id=workflow["attempt_id"])
                self.execution.schedule(state, "thinking", self.think)
        except (HTTPException, ValueError, OSError):
            with self.lock:
                state = self.load(sid)
                pending = next(row for row in state["_sample_handoffs"] if row["sample_id"] == sample["id"] and row["token"] == token)
                if pending["state"] == "paused":
                    return
                pending["state"] = "unavailable"
                state.pop("_sample_workflow_active", None)
                self.sessions.save(state)
                current = self.research_objects.sample(owner, rid, sample["id"])
                if current["workflow"] and digest({key: current["workflow"][key] for key in ("attempt_id", "issues")}) == token:
                    self.research_objects.set_sample_workflow(owner, rid, sample["id"],
                        {**current["workflow"], "agent_state": "unavailable"}, attempt_id=workflow["attempt_id"])
            self.drain_sample_handoffs(sid)

    def pause_sample_handoffs(self, state):
        """Revoke queued work synchronously, including when no worker is running."""
        from .sample_analyses import digest
        owner, rid = state.get("owner_id"), state.get("research_id")
        for row in state.get("_sample_handoffs", []):
            if row["state"] in {"pending", "preparing"}:
                row["state"] = "paused"
                sample = self.research_objects.sample(owner, rid, row["sample_id"])
                workflow = sample.get("workflow")
                if workflow and digest({key: workflow[key] for key in ("attempt_id", "issues")}) == row["token"]:
                    self.research_objects.set_sample_workflow(owner, rid, sample["id"],
                        {**workflow, "agent_state": "paused"}, attempt_id=workflow["attempt_id"])

    def sample_workflow_settled(self, sid, *, stopped=False):
        """Record the model outcome and bind eligible follow-up results to their sample."""
        from .sample_analyses import AnalysisRegistration, digest
        with self.lock:
            state = self.load(sid)
            owner, rid = state.get("owner_id"), state.get("research_id")
            active = state.pop("_sample_workflow_active", None)
            if active:
                sample = self.research_objects.sample(owner, rid, active["sample_id"])
                workflow = sample.get("workflow")
                outcome = "paused" if stopped else "unavailable" if state["status"] == "failed" else "delivered"
                for row in state["_sample_handoffs"]:
                    if row["sample_id"] == active["sample_id"] and row["token"] == active["token"]:
                        row["state"] = outcome
                if workflow and digest({key: workflow[key] for key in ("attempt_id", "issues")}) == active["token"]:
                    self.research_objects.set_sample_workflow(owner, rid, sample["id"],
                        {**workflow, "agent_state": outcome}, attempt_id=workflow["attempt_id"])
                self.sessions.save(state)
            if stopped:
                self.pause_sample_handoffs(state)
                self.sessions.save(state)
            for plan_id, binding in state.get("_sample_plan_bindings", {}).items():
                sample_id, material_id = binding["sample_id"], binding["material_id"]
                sample = self.research_objects.sample(owner, rid, sample_id)
                if sample["material_id"] != material_id:
                    continue
                receipts = {row["file"].removesuffix(".json") for row in state.get("_tool_runs", [])
                            if row.get("plan_id") == plan_id}
                if not receipts:
                    continue
                sources = self.sample_analyses.sources(owner, rid, sample_id, sid)
                for source in sources["sources"]:
                    if source["eligible"] and source["receipt_id"] in receipts:
                        self.sample_analyses.register(owner, rid, sample_id, AnalysisRegistration(
                            expected_version=sample["revision"], session_id=sid, receipt_id=source["receipt_id"]))
        if not stopped and not self.execution.closing:
            self.drain_sample_handoffs(sid)

    def register_h5ad(self, state, aid, name, size, checksum, locations, *, material_id=None):
        """Register an already validated private original through the shared input contract."""
        upload = {"id": aid, "name": re.sub(r"[\x00-\x1f\x7f]", "", name), "kind": "h5ad", "size": size}
        if material_id is not None:
            upload["material_id"] = material_id
        state["uploads"].append(upload)
        state["_uploads"][aid] = {"sha256": checksum, "locations": locations,
                                  "declaration_start": len(state["messages"])}
        self.archive_plan(state)
        state["plan"], state["_plan"], state["status"], state["error"] = None, None, "idle", None
        intake_autofill.ensure(self, state, aid)
        self.message(state, "assistant", "资料已加入当前会话。请核对实验背景，再确认需要开展的分析。", source="server_template")
        response = self.public(state)
        self.sessions.save(state)
        return response

    def archive_plan(self, state):
        if state.get("plan") and state["plan"]["status"] not in {
            "proposed",
            "approved",
        }:
            state["plan_history"].append(state["plan"])
            state["_plan_history"].append(
                {
                    "plan": state["_plan"],
                    "bundle": state.get("_bundle"),
                    "run_id": state.get("_run_id"),
                }
            )
        state["plan"], state["_plan"] = None, None
        state.pop("_run_id", None)

    def cell_state_runtime_parameters(self):
        from bridge.tool_packages.p0_02_cell_state.candidate_runtime import (
            CANDIDATE_SPEC,
            candidate_runtime_binding,
        )

        if self.settings.cell_state_measurement_spec_ref != CANDIDATE_SPEC:
            return {}
        binding, fingerprint = candidate_runtime_binding(
            self.settings.cell_state_candidate_runtime_ref
        )
        return {
            "candidate_runtime_ref": binding.runtime_id,
            "candidate_binding_sha256": fingerprint,
        }

    def cell_state_config_reasons(self):
        if not self.settings.cell_state_measurement_spec_ref:
            return ["measurement_spec_not_configured"]
        from bridge.tool_packages.p0_02_cell_state.measurement_specs import (
            load_measurement_spec,
        )
        from bridge.tool_packages.p0_02_cell_state.reference import (
            resolve_reference_snapshot,
            validate_reference_snapshot,
            validate_runtime_reference,
        )

        try:
            spec = load_measurement_spec(self.settings.cell_state_measurement_spec_ref)
            if spec is None:
                return ["measurement_spec_not_found"]
            manifest = validate_reference_snapshot(
                resolve_reference_snapshot(spec.reference_refs[0])
            )
            validate_runtime_reference(manifest)
            from bridge.tool_packages.p0_02_cell_state.candidate_runtime import (
                AUXILIARY_SPEC,
                CANDIDATE_SPEC,
            )

            self.cell_state_runtime_parameters()
            reference_spec = (
                AUXILIARY_SPEC
                if spec.measurement_spec_id == CANDIDATE_SPEC
                else spec.measurement_spec_id
            )
            if reference_spec not in manifest.measurement_spec_ids:
                return ["measurement_spec_not_supported_by_reference"]
        except Exception as exc:
            return [getattr(exc, "reason_code", "reference_configuration_invalid")]
        return []

    def no_graft_declared(self, state):
        text = next(
            (item["content"] for item in reversed(state["messages"]) if item["role"] == "user"),
            "",
        )
        if NO_GRAFT_UNCERTAIN.search(text):
            return False
        return bool(NO_GRAFT_DECLARATION.search(text))

    def capabilities(self, state):
        result = []
        selected = state["uploads"][-1]["id"] if state["uploads"] else None
        for spec in self.registry.list():
            reasons = []
            self.inputs.initialize(state)
            selection = state["_input_selections"].get(spec.tool_id)
            if selection is not None:
                try:
                    reasons = self.inputs.selection_reasons(
                        state, Selection.model_validate(selection)
                    )
                except ValueError:
                    reasons = ["input_binding_invalid"]
            elif spec.tool_id == "P0-01":
                reasons = [] if selected else ["product_upload_required"]
                if selected and not self.assay(state, selected):
                    reasons.append("assay_declaration_required")
                if selected and not self.declaration(state, selected):
                    reasons.append("raw_count_declaration_required")
            elif spec.tool_id == "P0-02":
                reasons = self.cell_state_config_reasons()
                if not selected:
                    reasons.append("product_upload_required")
                elif not state["_uploads"][selected].get("source_family_id"):
                    reasons.append("source_family_id_required")
                if selected:
                    try:
                        self.qc.asset(state, selected, register=False, enrich=False)
                    except Exception as exc:
                        reasons.append(
                            str(exc)
                            if str(exc)
                            in {
                                "completed_qc_required",
                                "qc_artifacts_missing",
                                "qc_artifact_integrity_mismatch",
                                "qc_declaration_retracted",
                            }
                            else "qc_artifacts_unavailable"
                        )
                else:
                    reasons.append("completed_qc_required")
            elif spec.tool_id == "P0-12":
                reasons = [] if self.no_graft_declared(state) else ["no_graft_declaration_required"]
                if selected and not any(
                    item["asset_id"] == selected
                    for item in state.get("_bundle", {}).get("assets", [])
                ):
                    reasons.append("product_analysis_context_required")
                if not selected:
                    reasons.append("product_upload_required")
            else:
                contract = self.registry.describe_input(spec.tool_id)
                mode = (
                    contract.object_input_modes[0]
                    if len(contract.object_input_modes) == 1
                    else None
                )
                reasons = (
                    ["object_required:" + role.role for role in mode.roles if role.min_count]
                    if mode
                    else ["input_mode_required"]
                )
            if spec.tool_id == "P0-02" and (selection or {}).get("measurement_spec_ref") != "EXPRESSION-exploration-v0.1":
                aids = selection["asset_ids"] if selection else ([selected] if selected else [])
                for aid in aids:
                    reasons.extend(self.intake.cell_state_reasons(state, aid))
            result.append(
                {
                    "tool_id": spec.tool_id,
                    "label": spec.name,
                    "state": "needs_input" if reasons else "ready",
                    "reason_codes": reasons,
                    "mode_id": selection["mode_id"] if selection else None,
                }
            )
        return result

    def stage_blocked(self, state, reason):
        state["status"], state["error"] = "idle", reason
        self.message(
            state,
            "assistant",
            "当前阶段还缺少继续所需的资料。已有工具证据会保留，未知项不会被补成事实。",
            source="server_template",
        )
        self.sessions.save(state)

    def prepare_analysis(self, state, tool_id):
        self.controls.require_ready(state)
        # Another session's in-flight tool may own the process QC catalog.
        # Never wait for that lock while holding the HTTP/session state lock.
        if not CATALOG_LOCK.acquire(blocking=False):
            raise HTTPException(409, "worker_busy")
        try:
            self._prepare_analysis(state, tool_id)
        finally:
            CATALOG_LOCK.release()

    def _prepare_analysis(self, state, tool_id):
        self.inputs.initialize(state)
        if tool_id == "P0-02" and state["_input_selections"].get(tool_id, {}).get("measurement_spec_ref") != "EXPRESSION-exploration-v0.1":
            selection = state["_input_selections"].get(tool_id)
            aids = (
                selection["asset_ids"]
                if selection
                else [item["id"] for item in state["uploads"][-1:]]
            )
            if any(self.intake.cell_state_reasons(state, aid) for aid in aids):
                self.stage_blocked(state, "supported_product_family_required")
                return
        if tool_id in state["_input_selections"] or tool_id not in {"P0-02", "P0-12"}:
            self.prepare_selected(state, tool_id)
            return
        if tool_id == "P0-12":
            if not self.no_graft_declared(state):
                self.stage_blocked(state, "no_graft_declaration_required")
                return
        if not state["uploads"]:
            self.stage_blocked(state, "product_upload_required")
            return
        selected = state["uploads"][-1]["id"]
        upload = state["_uploads"][selected]
        try:
            directory, _, _ = ensure_private_directory(self.directory(state["id"]) / "uploads")
            path = directory / (selected + ".h5ad")
            try:
                verify_checked_file(
                    self,
                    state,
                    path,
                    upload["sha256"],
                    limit=self.settings.max_upload_bytes,
                )
            except ValueError as exc:
                raise ValueError("upload_integrity_mismatch") from exc
            if tool_id == "P0-02":
                reasons = self.cell_state_config_reasons()
                if reasons:
                    self.stage_blocked(state, reasons[0])
                    return
                if not upload.get("source_family_id"):
                    self.stage_blocked(state, "source_family_id_required")
                    return
                asset = self.qc.asset(state, selected)
            else:
                # Context only: no biological semantics are inferred or sent to P0-12.
                context_assets = state.get("_bundle", {}).get("assets", [])
                context = next(
                    (item for item in context_assets if item["asset_id"] == selected),
                    None,
                )
                if context is None:
                    self.stage_blocked(state, "product_analysis_context_required")
                    return
                asset = CaseInputAsset.model_validate(context)
            bundle = CaseInputBundle(bundle_id=uid(), version="1", assets=[asset])
            spec = self.registry.describe(tool_id)
            arguments = dict(
                request_id=uid(),
                tool_id=tool_id,
                tool_version=spec.version,
                output_dir=self.directory(state["id"]) / "runs",
            )
            if tool_id == "P0-02":
                request = ToolRequest(
                    **arguments,
                    assets=[asset.to_toolkit_asset()],
                    measurement_spec_ref=self.settings.cell_state_measurement_spec_ref,
                    parameters=self.cell_state_runtime_parameters(),
                )
            else:
                request = ToolRequestV2(**arguments, assets=[], object_inputs=[])
            self.propose_request(
                state,
                bundle,
                request,
                tool_id
                + (
                    " 细胞状态候选分析；不保证 V3 或完整生物学证据。"
                    if tool_id == "P0-02"
                    else " 明确未提供移植数据；不运行 graft 表达分析，不回填产品证据。"
                ),
            )
        except Exception as exc:
            reason = (
                str(exc)
                if str(exc)
                in {
                    "upload_integrity_mismatch",
                    "completed_qc_required",
                    "qc_artifacts_missing",
                    "qc_artifact_integrity_mismatch",
                    "qc_declaration_retracted",
                }
                else "stage_input_construction_failed"
            )
            self.stage_blocked(state, reason)

    def conditional_blocker(self, state, tool_id):
        # Explicit absence remains a non-assessment outcome, not graft authorization.
        selected = state.get("_input_selections", {}).get(tool_id)
        if tool_id == "P0-12" and (
            selected
            and selected.get("mode_id") == "not_provided"
            or selected is None
            and self.no_graft_declared(state)
        ):
            return None
        return self.conditional_inputs.selected_blocker(state, tool_id)

    def prepare_selected(self, state, tool_id):
        self.inputs.initialize(state)
        blocker = (
            self.scientific_inputs.selected_blocker(state, tool_id)
            or self.report_inputs.selected_blocker(state, tool_id)
            or self.conditional_blocker(state, tool_id)
        )
        if blocker:
            self.stage_blocked(state, blocker)
            return
        contract = self.registry.describe_input(tool_id)
        saved = state["_input_selections"].get(tool_id)
        if saved is None:
            mode_id = (
                contract.object_input_modes[0].mode_id
                if len(contract.object_input_modes) == 1
                else None
            )
            saved = dict(
                tool_id=tool_id,
                mode_id=mode_id,
                asset_ids=[],
                object_inputs=[],
                measurement_spec_ref=None,
            )
        try:
            bundle, request = self.inputs.construct(state, Selection.model_validate(saved))
        except (ValueError, OSError) as exc:
            reason = str(exc)
            if not re.fullmatch(r"[a-z_]+(?::[a-z_]+)?", reason):
                reason = "input_binding_invalid"
            self.stage_blocked(state, reason)
            return
        self.propose_request(
            state,
            bundle,
            request,
            tool_id
            + " / "
            + (saved["mode_id"] or "asset_input")
            + "；使用明确选择的输入；仅研究性证据，不补造事实。请单独确认本次计划。",
        )

    def propose_request(self, state, bundle, request, summary, *, scope_admission=False):
        snapshot = files("bridge.resources").joinpath("knowledge_snapshot.json.gz").read_bytes()
        with self.qc.catalog():
            plan = PlanBuilder(self.registry).build(
                bundle,
                output_root=request.output_dir,
                knowledge_snapshot_ref="sha256:" + hashlib.sha256(snapshot).hexdigest(),
                requests=[request],
                include_input_qc=False,
            )
        self.archive_plan(state)
        state["_bundle"], state["_plan"] = (
            bundle.model_dump(mode="json"),
            plan.model_dump(mode="json"),
        )
        state["plan"] = {
            "id": plan.plan_id,
            "digest": plan.approval_sha256(),
            "status": "proposed",
            "summary": summary,
            "steps": [
                {
                    "id": item.step_id,
                    "tool_id": item.tool_id,
                    "label": self.registry.describe(item.tool_id).name,
                    "status": ("pending" if item.disposition.value == "execute" else "blocked"),
                    "reason": None if not item.reason_codes else "input_not_eligible",
                }
                for item in plan.steps
            ],
        }
        state["status"], state["error"] = "awaiting_approval", None
        if not scope_admission:
            self.message(
                state,
                "assistant",
                "新阶段计划已生成。请检查输入模式并单独确认；之前的审批不适用于本阶段。",
                source="server_template",
            )
        self.sessions.save(state)

    def input_changed(self, state):
        state["_input_revision"] += 1
        self.assessment.stop(state, "input_revision_changed", status="blocked")
        if state.get("plan") and state["plan"]["status"] == "proposed":
            state["plan"], state["_plan"], state["status"] = None, None, "idle"
        state["error"] = None
        self.sessions.save(state)

    def busy(self, state):
        if (
            state["status"] in {"thinking", "running", "stopping"}
            or self.execution.has_pending(state["id"])
            or state["id"] in self.uploads_in_progress
        ):
            raise HTTPException(409, "session_busy")

    def declaration(self, state, upload_id):
        declared = state.get("_asset_declarations", {}).get(upload_id) or state.get(
            "_qc_declarations", {}
        ).get(upload_id)
        if declared:
            return (
                declared["matrix_location"]
                if declared.get("matrix_semantics") == "raw_counts"
                else None
            )
        return None

    def _admit_workbench_turn(self, state, turn_id, action):
        """Fence object-dependent replies under the same lock as admission."""
        if turn_id is None:
            return True
        from .workbench_context import build_workbench_context, context_digest
        record = state["_workbench_contexts"][turn_id]
        current = build_workbench_context(self.researches, self.research_objects, state)
        record["provider_calls"] = action._provider_calls
        if context_digest(current) != record["sha256"]:
            record["disposition"] = "stale"
            self.message(state, "assistant",
                         "研究或轮次资料已更新，本次回复未采用。请重新提问，我会读取更新后的记录。",
                         source="server_template")
            state["status"], state["error"] = "idle", None
            self.sessions.save(state)
            return False
        record["disposition"] = "admitted"
        return True

    def think(self, sid, epoch):
        from .workbench_context import build_workbench_context, context_digest
        workbench_turn_id = None
        with self.lock:
            state = self.load(sid)
            if state["_control_epoch"] != epoch:
                return
            workbench_snapshot = build_workbench_context(self.researches, self.research_objects, state)
            if workbench_snapshot is not None:
                active_handoff = state.get("_sample_workflow_active")
                workbench_turn_id = (active_handoff["message_id"] if active_handoff else
                    next((item["id"] for item in reversed(state["messages"]) if item["role"] == "user"), None))
                if workbench_turn_id is not None:
                    state.setdefault("_workbench_contexts", {})[workbench_turn_id] = {
                        "control_epoch": epoch, "snapshot": workbench_snapshot,
                        "sha256": context_digest(workbench_snapshot), "disposition": "prepared",
                        "provider_calls": None,
                    }
                    self.sessions.save(state)
        allowed_tools = {spec.tool_id for spec in self.registry.list()}
        allowed_states = {"succeeded", "failed", "partial", "cancelled", "blocked"}
        tool_history = [
            {"tool_id": item["tool_id"], "state": item["state"]}
            for item in state.get("_tool_runs", [])[-24:]
            if item.get("tool_id") in allowed_tools and item.get("state") in allowed_states
        ]
        context = {
            "status": "idle",
            "upload_ids": [item["id"] for item in state["uploads"]],
            "plan_status": state["plan"]["status"] if state["plan"] else None,
            "capabilities": self.capabilities(state),
            "tool_execution_history": tool_history,
            "input_contracts": {
                spec.tool_id: [
                    {
                        "mode_id": mode.mode_id,
                        "required_roles": [role.role for role in mode.roles if role.min_count],
                    }
                    for mode in self.registry.describe_input(spec.tool_id).object_input_modes
                ]
                for spec in self.registry.list()
            },
            "results_sent_to_model": False,
        }
        if workbench_snapshot is not None:
            context["workbench_context"] = workbench_snapshot
        focus = state.get("_sample_workflow_active") or state.get("_sample_turn")
        if focus:
            current_sample = self.research_objects.sample(state["owner_id"], state["research_id"], focus["sample_id"])
            context["sample_workflow_context"] = {
                "sample_id": current_sample["id"], "upload_id": focus["upload_id"],
                "automatic_handoff": bool(state.get("_sample_workflow_active")),
                "issues": (current_sample.get("workflow") or {}).get("issues", []),
                "declared_fields": sorted((current_sample.get("mapping_input") or {}).keys()),
                "question_fields": {"matrix_semantics": "count_semantics", "sample_context": "sample_context",
                                    "capture_id": "capture_id"},
                "available_analyses": [{"id": row["id"], "tool_id": row["tool"]["id"],
                                        "source_kind": row["source_kind"]}
                    for row in self.sample_analyses.list(state["owner_id"], state["research_id"], current_sample["id"])["analyses"]
                    if row["availability"]["status"] == "available"],
                "authority": "workflow_findings_only_not_scientific_results",
                "next_action": "Clarify missing declarations or select an eligible registered tool within existing authorization. Never invent data or rerun completed basic analyses.",
            }
        context["input_review_required"] = state["input_review_required"]
        context["clarification_context"] = self.clarifications.context(state)
        # Provider receives readiness only, never private form values or column names.
        context["intake_context"] = [
            {
                "upload_id": item["id"],
                "state": (
                    "confirmed"
                    if state.get("_intakes", {}).get(item["id"], {}).get("signature")
                    == self.intake.signature(state, item["id"])
                    else "needs_confirmation"
                ),
                "missing_fields": [
                    q["field"]
                    for q in intake_autofill.questions(
                        intake_autofill.ensure(self, state, item["id"]),
                        self.intake.current_facts(state, item["id"]),
                    )
                ],
            }
            for item in state["uploads"]
        ]
        result_turn_id = None
        result_summary = {"state": "not_available"}
        if self.settings.share_result_summaries and not state["input_review_required"]:
            from .evidence import build_result_context

            summary, binding = build_result_context(self.inputs, state)
            result_summary = summary
            context["result_summary"] = summary
            context["report_context"] = self.artifacts.report_context(state)
            context["results_sent_to_model"] = summary["state"] == "available"
            context["observation_choices"] = result_observation_choices(context)
            result_turn_id = next(
                (item["id"] for item in reversed(state["messages"]) if item["role"] == "user"),
                None,
            )
            if result_turn_id is not None:
                with self.lock:
                    current = self.load(sid)
                    if current["_control_epoch"] != epoch:
                        return
                    records = current.setdefault("_result_contexts", {})
                    records[result_turn_id] = {
                        "control_epoch": epoch,
                        "result_summary": summary,
                        "report_context": context["report_context"],
                        "private_binding": binding,
                    }
                    while len(records) > 24:
                        records.pop(next(iter(records)))
                    self.sessions.save(current)
        context["research_context"] = build_research_context(
            {**state, "status": context["status"]},
            confirmed_input_state=context["intake_context"],
            analyses_attempted=tool_history,
            result_summary=result_summary,
        )
        result_reply_ids = {
            record.get("assistant_message_id")
            for record in state.get("_result_contexts", {}).values()
            if isinstance(record, dict) and record.get("assistant_message_id")
        }
        private_message_ids = self.clarifications.private_message_ids(
            state
        ) | self.scientific_inputs.private_message_ids(state)

        def include_history(item):
            if item["id"] in private_message_ids:
                return False
            if item.get("role") == "user":
                return True
            source = item.get("source")
            if source in {"server_template", "deterministic_evidence"}:
                return True
            if source == "provider_admitted":
                return context["results_sent_to_model"] or item["id"] not in result_reply_ids
            # Keep legacy text visible to the researcher, but do not compound
            # unclassified assistant prose into a new provider turn.
            return False

        provider_messages = [
            {"role": item["role"], "content": private_text(item["content"])}
            for item in project_public_messages(state["messages"])
            if include_history(item)
        ]
        try:
            action = converse(self.settings, provider_messages, context)
        except Exception as exc:
            raise ProviderUnavailable() from exc
        if action._skill_receipts:
            with self.lock:
                state = self.load(sid)
                if state["_control_epoch"] != epoch:
                    return
                self.sessions.record_skill_usage(state, action._skill_receipts,
                    action=action.action, purpose="conversation", provider_calls=action._provider_calls)
        if action.action == "draft_scientific_inputs":
            with self.lock:
                state = self.load(sid)
                if state["_control_epoch"] != epoch or not self._admit_workbench_turn(
                        state, workbench_turn_id, action):
                    return
                self.sessions.save(state)
            self.draft_scientific_inputs(sid, epoch, action.upload_id)
            return
        if action.action == "propose_scientific_inputs":
            raise ValueError("scientific_draft_purpose_required")
        with self.lock:
            state = self.load(sid)
            if state["_control_epoch"] != epoch:
                return
            if not self._admit_workbench_turn(state, workbench_turn_id, action):
                return
            assistant_message_id = None
            if action.action == "ask_user_input":
                card = self.clarifications.stage(state, action.questions)
                if card is None or card["status"] != "pending":
                    self.message(
                        state,
                        "assistant",
                        "这些项目已有回答或已确认资料，我会保留现有信息；未知项仍按缺失处理。可在原问题卡片中修改。",
                        source="server_template",
                    )
            elif action.action == "review_inputs":
                self.controls.review(state)
                text, source = admit_provider_text(
                    action.text,
                    context,
                    observation_aliases=action.observation_aliases,
                )
                self.message(state, "assistant", text, source=source)
                assistant_message_id = state["messages"][-1]["id"]
            elif action.action == "propose_intake":
                if action.upload_id not in state["_uploads"]:
                    raise ValueError("unknown_upload")
                if action.upload_id in state.get("_intakes", {}) or state["input_review_required"]:
                    self.message(
                        state,
                        "assistant",
                        "请在右侧产品资料中查看或修改已确认事实，并确认精确变更。聊天不会改写现有声明。",
                        source="server_template",
                    )
                else:
                    facts = self.intake.current_facts(state, action.upload_id).model_dump()
                    facts.update(action.facts.model_dump(exclude_unset=True))
                    self.controls.stage(
                        state,
                        "intake",
                        IntakeInput(
                            upload_id=action.upload_id,
                            facts=IntakeFacts.model_validate(facts),
                        ),
                    )
                    self.message(
                        state,
                        "assistant",
                        "产品资料草稿已整理，请在右侧核对并确认。确认资料不会自动启动分析。",
                        source="server_template",
                    )
            elif (
                action.action in {"prepare_analysis", "prepare_qc"}
                and state["input_review_required"]
            ):
                self.stage_blocked(state, "input_review_required")
                return
            elif action.action == "prepare_analysis":
                self.prepare_analysis(state, action.tool_id)
                self.bind_sample_plan(state)
                return
            elif action.action == "prepare_qc":
                if action.upload_id not in state["_uploads"]:
                    raise ValueError("unknown_upload")
                declaration = self.declaration(state, action.upload_id)
                if declaration != action.matrix_location:
                    self.message(
                        state,
                        "assistant",
                        "请先在右侧产品资料中确认实验类型与原始计数位置。聊天中的说法不会自动成为已确认输入。",
                        source="server_template",
                    )
                else:
                    try:
                        self.qc.asset(state, action.upload_id, register=False, enrich=False)
                    except (ValueError, OSError, KeyError) as exc:
                        if str(exc) not in {
                            "completed_qc_required",
                            "qc_declaration_retracted",
                        }:
                            self.stage_blocked(state, "qc_evidence_unavailable")
                            return
                        self.prepare(state, action.upload_id, declaration)
                        self.bind_sample_plan(state)
                        return
                    self.message(
                        state,
                        "assistant",
                        "这份输入已有仍有效的 QC 证据，无需重复运行。可直接查看已有结果或继续下一阶段。",
                        source="deterministic_evidence",
                    )
            else:
                text, source = admit_provider_text(
                    action.text,
                    context,
                    observation_aliases=action.observation_aliases,
                )
                self.message(state, "assistant", text, source=source)
                assistant_message_id = state["messages"][-1]["id"]
            if (
                assistant_message_id is not None
                and result_turn_id is not None
                and context["results_sent_to_model"]
            ):
                record = state.get("_result_contexts", {}).get(result_turn_id)
                if record is not None:
                    record["assistant_message_id"] = assistant_message_id
                    refs = result_observation_refs(context, action.observation_aliases)
                    if refs and source == "provider_admitted":
                        record["observation_refs"] = refs
            state["status"] = "idle"
            self.sessions.save(state)

    def draft_scientific_inputs(self, sid, epoch, aid):
        with self.lock:
            state = self.load(sid)
            if state["_control_epoch"] != epoch:
                return
            try:
                context, binding = self.scientific_inputs.request_context(state, aid)
            except (ValueError, OSError, KeyError, HTTPException):
                state["status"], state["error"] = (
                    "idle",
                    "scientific_intent_or_source_required",
                )
                self.sessions.save(state)
                return
        for attempt in range(2):
            feedback = None
            action = None
            try:
                action = converse(
                    self.settings,
                    [
                        {
                            "role": "user",
                            "content": "请用中文提出有来源的科学输入候选，供用户逐项确认。严格遵守上下文中的候选约束；没有充分来源的选择保持未确定。不要运行分析或确认任何声明。",
                        }
                    ],
                    context,
                )
            except ValueError:
                feedback = "scientific_candidate_shape_invalid"
            except Exception as exc:
                raise ProviderUnavailable() from exc
            else:
                if action.action != "propose_scientific_inputs" or action.upload_id != aid:
                    feedback = "scientific_candidate_required"
                else:
                    try:
                        self.scientific_inputs._validate(action.candidate, context)
                    except ValueError as exc:
                        feedback = str(exc)
            with self.lock:
                current = self.load(sid)
                if current["_control_epoch"] != epoch:
                    return
                if action is not None:
                    self.sessions.record_skill_usage(current, action._skill_receipts,
                        action=action.action, purpose="scientific_input_draft", provider_calls=action._provider_calls)
                if feedback:
                    try:
                        _, current_binding = self.scientific_inputs.request_context(current, aid)
                        if current_binding != binding:
                            raise ValueError("scientific_draft_stale")
                    except (ValueError, OSError, KeyError, HTTPException):
                        current["status"], current["error"] = (
                            "idle",
                            "scientific_draft_stale",
                        )
                        self.sessions.save(current)
                        return
                    if attempt == 0:
                        # Retry only shape/source validation once. Never resend
                        # invalid values, private history or unconfirmed facts.
                        context = {**context, "validation_feedback": feedback}
                        continue
                    current["status"], current["error"] = (
                        "idle",
                        "scientific_candidate_invalid",
                    )
                    self.message(
                        current,
                        "assistant",
                        "候选仍未通过来源或结构校验，未生成科学草稿，也未运行分析。请重新整理候选；未知项继续保留。",
                        source="server_template",
                    )
                    self.sessions.save(current)
                    return
                self.scientific_inputs.propose(
                    current, aid, action.candidate, expected_binding=binding
                )
                current["status"], current["error"] = "idle", None
                self.sessions.save(current)
                return

    def assay(self, state, upload_id):
        declared = state.get("_asset_declarations", {}).get(upload_id) or state.get(
            "_qc_declarations", {}
        ).get(upload_id)
        if declared:
            return declared.get("assay")
        return None

    def prepare(self, state, upload_id, location):
        self.controls.require_ready(state)
        assay = self.assay(state, upload_id)
        if assay is None or self.declaration(state, upload_id) != location:
            raise HTTPException(409, "intake_confirmation_required")
        upload = state["_uploads"][upload_id]
        if location not in upload["locations"]:
            raise ValueError("matrix_not_registered")
        directory, _, _ = ensure_private_directory(self.directory(state["id"]) / "uploads")
        path = directory / (upload_id + ".h5ad")
        try:
            verify_checked_file(
                self,
                state,
                path,
                upload["sha256"],
                limit=self.settings.max_upload_bytes,
            )
        except ValueError as exc:
            raise ValueError("upload_integrity_mismatch") from exc
        declared = state["_asset_declarations"].get(upload_id)
        asset = (
            CaseInputAsset.model_validate(declared)
            if declared
            else CaseInputAsset(
                asset_id=upload_id,
                path=path,
                format="h5ad",
                checksum=upload["sha256"],
                **state["_qc_declarations"][upload_id],
            )
        )
        bundle = CaseInputBundle(bundle_id=uid(), version="1", assets=[asset])
        snapshot = files("bridge.resources").joinpath("knowledge_snapshot.json.gz").read_bytes()
        plan = PlanBuilder().build(
            bundle,
            output_root=self.directory(state["id"]) / "runs",
            knowledge_snapshot_ref="sha256:" + hashlib.sha256(snapshot).hexdigest(),
        )
        self.archive_plan(state)
        state["_bundle"] = bundle.model_dump(mode="json")
        state["_plan"] = plan.model_dump(mode="json")
        state["plan"] = {
            "id": plan.plan_id,
            "digest": plan.approval_sha256(),
            "status": "proposed",
            "summary": "P0-01 输入 QC；实验类型："
            + assay
            + "；原始计数位置："
            + location
            + "。使用已确认的输入声明；仅研究性候选结果，不推断生物学重复。",
            "steps": [
                {
                    "id": item.step_id,
                    "tool_id": item.tool_id,
                    "label": "输入质量与可分析性",
                    "status": ("pending" if item.disposition.value == "execute" else "skipped"),
                    "reason": None if not item.reason_codes else "input_not_eligible",
                }
                for item in plan.steps
            ],
        }
        state["status"] = "awaiting_approval"
        self.message(
            state,
            "assistant",
            "已根据您的计数声明生成输入 QC 计划。请检查并确认；确认前不会运行。结果不代表科学方法已验证。",
            source="server_template",
        )
        self.sessions.save(state)

    def verify_scientific_plan(self, state, plan):
        for step in plan.steps:
            blocker = (
                self.scientific_inputs.selected_blocker(state, step.tool_id)
                or self.report_inputs.selected_blocker(state, step.tool_id)
                or self.conditional_blocker(state, step.tool_id)
            )
            if blocker:
                raise ValueError(blocker)
