"""Bind an explicit cohort to registered, user-attributed comparison inputs."""
from copy import deepcopy
from typing import Literal

from fastapi import HTTPException, Request
from pydantic import Field, field_validator

from bridge.tool_packages.p0_07_product_comparison_stability.models import (
    ComparisonCaseManifest, ProductEvidenceBundle,
)
from .analysis_cohorts import HASH
from .conditional_inputs import ConditionalProposal
from .research_object_models import Body, ObjectID

ERRORS = {
    "conditional_cohort_binding_stale": "比较名单的来源或关联已变化，请重新核对。",
    "cohort_not_confirmed": "请先确认所选分析版本名单。",
    "cohort_bundle_binding_mismatch": "证据包与所选样本、分析版本或比较组的声明不一致。",
    "cohort_duplicate_sample": "同一样本的多次分析不能作为多个产品比较单位。",
    "cohort_comparison_mode_required": "请选择已有的产品比较输入模式。",
    "cohort_comparison_session_not_found": "找不到本研究中可用于比较的会话。",
}


class EvidenceBinding(Body):
    analysis_id: ObjectID
    bundle_input_id: ObjectID


def unique_members(members):
    if (len({m.analysis_id for m in members}) != len(members)
            or len({m.bundle_input_id for m in members}) != len(members)):
        raise ValueError("duplicate_evidence_binding")
    return members


class CohortAttachment(Body):
    research_id: ObjectID
    cohort_id: ObjectID
    cohort_digest: HASH
    session_id: ObjectID
    attribution: Literal["user_declared"] = "user_declared"
    members: list[EvidenceBinding] = Field(min_length=2, max_length=20)

    _unique_members = field_validator("members")(unique_members)


class CohortComparisonProposal(ConditionalProposal):
    session_id: ObjectID
    cohort_digest: HASH
    members: list[EvidenceBinding] = Field(min_length=2, max_length=20)

    _unique_members = field_validator("members")(unique_members)


def identity(kind, identifier):
    return {"object_id": kind + ":" + identifier, "object_version": "1.0.0"}


class CohortComparisons:
    def __init__(self, *, sessions, get_cohort, get_analysis, get_sample,
                 read_object, propose, lock):
        self.sessions, self.lock = sessions, lock
        self.get_cohort, self.get_analysis = get_cohort, get_analysis
        self.get_sample, self.read_object, self.propose_selection = get_sample, read_object, propose

    def _session(self, owner, rid, sid):
        if self.sessions.owner(sid) != owner:
            raise HTTPException(404, "cohort_comparison_session_not_found")
        state = self.sessions.load(sid)
        if state.get("research_id") != rid:
            raise HTTPException(404, "cohort_comparison_session_not_found")
        return state

    def validate_binding(self, state, selection, binding):
        """Called at proposal, confirmation, preparation and execution admission."""
        attachment = CohortAttachment.model_validate(binding)
        owner = self.sessions.owner(state["id"])
        rid = attachment.research_id
        if state["id"] != attachment.session_id or state.get("research_id") != rid:
            raise HTTPException(409, "cohort_bundle_binding_mismatch")
        cohort = self.get_cohort(owner, rid, attachment.cohort_id)
        if cohort["digest"] != attachment.cohort_digest:
            raise HTTPException(409, "cohort_decision_changed")
        if cohort["status"] != "confirmed":
            raise HTTPException(409, "cohort_not_confirmed")
        if cohort["availability"]["status"] != "available":
            raise HTTPException(409, "cohort_source_unavailable")
        if selection.tool_id != "P0-07" or selection.mode_id not in {"legacy_comparison", "method_runtime"}:
            raise HTTPException(422, "cohort_comparison_mode_required")
        members = {m["analysis_id"]: m for m in cohort["members"]}
        chosen = {x.input_id for x in selection.object_inputs if x.role == "product_evidence_bundle"}
        if (set(members) != {m.analysis_id for m in attachment.members}
                or chosen != {m.bundle_input_id for m in attachment.members}):
            raise HTTPException(409, "cohort_bundle_binding_mismatch")
        try:
            manifests = [x.input_id for x in selection.object_inputs if x.role == "comparison_case_manifest"]
            if len(manifests) != 1:
                raise ValueError("manifest_required")
            manifest = ComparisonCaseManifest.model_validate(self.read_object(state, manifests[0]))
            groups = {g.group_id: g for g in manifest.groups}
            seen_samples = set()
            for item in attachment.members:
                analysis = self.get_analysis(owner, rid, item.analysis_id)
                if analysis["sample_id"] in seen_samples:
                    raise HTTPException(409, "cohort_duplicate_sample")
                seen_samples.add(analysis["sample_id"])
                sample = self.get_sample(owner, rid, analysis["sample_id"])
                bundle = ProductEvidenceBundle.model_validate(self.read_object(state, item.bundle_input_id))
                value = bundle.model_dump(mode="json")
                group = groups[bundle.group_id]
                expected_sample = identity("sample", analysis["sample_id"])
                if (bundle.product_case.source_unit_kind != "sample"
                        or value["product_case"]["sample_or_preparation_ref"] != expected_sample
                        or bundle.product_case.assay != sample["assay"]
                        or identity("analysis", analysis["id"]) not in value["provenance_refs"]
                        or identity("run", analysis["run_id"]) not in value["batch_refs"]
                        or identity("protocol-version", analysis["protocol_version_id"]) not in value["protocol_refs"]
                        or bundle.timepoint.basis != "in_vitro_day"
                        or bundle.timepoint.order != sample["day"]
                        or group.role.value != members[item.analysis_id]["role"]
                        or bundle.ref not in group.bundle_refs):
                    raise ValueError("declared_binding_mismatch")
        except (KeyError, TypeError, ValueError, OSError):
            raise HTTPException(409, "cohort_bundle_binding_mismatch") from None

    def propose(self, owner, rid, cid, body):
        with self.lock:
            # Check research ownership before looking up the target session.
            self.get_cohort(owner, rid, cid)
            state = self._session(owner, rid, body.session_id)
            binding = CohortAttachment(research_id=rid, cohort_id=cid, cohort_digest=body.cohort_digest,
                session_id=body.session_id, members=body.members).model_dump(mode="json")
            return self.propose_selection(state, body.selection, body.expected_revision,
                                          cohort_binding=deepcopy(binding))


def install_cohort_comparison_http(app, store):
    @app.post("/api/researches/{rid}/analysis-cohorts/{cid}/comparison-proposals")
    def propose(rid: str, cid: str, body: CohortComparisonProposal, request: Request):
        return store.propose(request.state.principal.id, rid, cid, body)
