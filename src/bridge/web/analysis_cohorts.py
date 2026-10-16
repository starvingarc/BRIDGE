"""Persist explicit analysis selections; scientific comparison remains separate."""
from collections import Counter
from copy import deepcopy
import json
from typing import Annotated

from fastapi import HTTPException, Request
from pydantic import Field, model_validator

from bridge.tool_packages.p0_07_product_comparison_stability.models import ComparisonGroupRole
from .research_object_models import Body, Mutation, ObjectID
from .sample_analyses import digest
from .sessions import ID, now, read_file, uid, write_file

HASH = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
STORE_BYTES = 1024 * 1024
COHORT_LIMIT = 128
ERRORS = {
    "cohort_not_found": "找不到该比较名单。",
    "cohort_analysis_changed": "分析版本摘要不匹配，请重新读取后选择。",
    "cohort_decision_changed": "确认的名单摘要不匹配，请重新读取。",
    "cohort_source_unavailable": "名单中存在来源不可核验的分析，不能确认。",
    "cohort_store_unavailable": "比较名单历史暂不可读取。",
    "cohort_limit": "该研究的比较名单已达到存储上限。",
}
COMPARISON_BLOCKERS = [
    "frozen_comparison_spec_required",
    "product_analysis_context_required",
    "measured_comparison_evidence_required",
    "independence_not_recorded",
]


class CohortMember(Body):
    analysis_id: ObjectID
    snapshot_sha256: HASH
    role: ComparisonGroupRole


class CohortCreate(Body):
    expected_version: Annotated[int, Field(strict=True, ge=0)]
    members: list[CohortMember] = Field(min_length=2, max_length=32)

    @model_validator(mode="after")
    def distinct_members_and_roles(self):
        if len({m.analysis_id for m in self.members}) != len(self.members):
            raise ValueError("duplicate_analysis")
        roles = {m.role for m in self.members}
        if ComparisonGroupRole.BASELINE not in roles or len(roles) < 2:
            raise ValueError("baseline_and_nonbaseline_required")
        return self


class CohortConfirmation(Mutation):
    digest: HASH


class AnalysisCohorts:
    def __init__(self, *, researches, get_analysis, lock):
        self.researches, self.get_analysis, self.lock = researches, get_analysis, lock

    def _path(self, owner, rid):
        try:
            self.researches.owned(owner, rid)
        except HTTPException:
            raise HTTPException(404, "research_not_found") from None
        return self.researches.directory(rid) / "analysis-cohorts.json"

    @staticmethod
    def _digest(rid, members):
        return digest({"research_id": rid, "members": members})

    def _load(self, owner, rid):
        path = self._path(owner, rid)
        try:
            raw = read_file(path, STORE_BYTES)
        except FileNotFoundError:
            if not path.is_symlink():
                return {"schema_version": 1, "cohorts": {}}
            raise HTTPException(409, "cohort_store_unavailable") from None
        except (ValueError, OSError):
            raise HTTPException(409, "cohort_store_unavailable") from None
        try:
            state = json.loads(raw)
            if state["schema_version"] != 1 or not isinstance(state["cohorts"], dict):
                raise ValueError("invalid_store")
            for cid, row in state["cohorts"].items():
                if (not ID.fullmatch(cid) or row["id"] != cid or row["research_id"] != rid
                        or row["digest"] != self._digest(rid, row["members"])
                        or row["status"] not in {"pending", "confirmed"}
                        or row["revision"] != (2 if row["status"] == "confirmed" else 1)
                        or bool(row["confirmed_at"]) != (row["status"] == "confirmed")):
                    raise ValueError("invalid_record")
                CohortCreate(expected_version=0, members=row["members"])
                if not isinstance(row["created_at"], str):
                    raise ValueError("invalid_record")
            return state
        except (KeyError, TypeError, ValueError):
            raise HTTPException(409, "cohort_store_unavailable") from None

    def _save(self, owner, rid, state):
        raw = json.dumps(state, ensure_ascii=False, allow_nan=False).encode()
        if len(state["cohorts"]) > COHORT_LIMIT or len(raw) > STORE_BYTES:
            raise HTTPException(409, "cohort_limit")
        write_file(self._path(owner, rid), raw)

    @staticmethod
    def _row(state, cid):
        if cid not in state["cohorts"]:
            raise HTTPException(404, "cohort_not_found")
        return state["cohorts"][cid]

    def _evaluate(self, owner, rid, members):
        analyses, entries = [], []
        for member in members:
            analysis = self.get_analysis(owner, rid, member["analysis_id"])
            if analysis["snapshot_sha256"] != member["snapshot_sha256"]:
                raise HTTPException(409, "cohort_analysis_changed")
            analyses.append(analysis)
            available = analysis["availability"]["status"] == "available"
            reasons = list(COMPARISON_BLOCKERS) if available else ["analysis_source_unavailable"]
            if member["role"] == "reference_ood":
                reasons.append("reference_ood_group_not_rankable")
            entries.append({
                "analysis_id": analysis["id"], "sample_id": analysis["sample_id"],
                "run_id": analysis["run_id"], "protocol_version_id": analysis["protocol_version_id"],
                "session_id": analysis["session_id"], "analysis_version": analysis["version"],
                "role": member["role"], "category": "background_only" if available else "excluded",
                "availability": analysis["availability"], "reason_codes": reasons,
            })
        sample_counts = Counter(a["sample_id"] for a in analyses)
        material_counts = Counter(a["material_sha256"] for a in analyses)
        reasons = list(COMPARISON_BLOCKERS)
        if any(n > 1 for n in sample_counts.values()):
            reasons.append("multiple_analyses_same_sample")
        if any(n > 1 for n in material_counts.values()):
            reasons.append("shared_input_bytes")
        available = all(e["availability"]["status"] == "available" for e in entries)
        if not available:
            reasons.append("cohort_source_unavailable")
        return {
            "entries": entries,
            "summary": {"analysis_count": len(analyses), "sample_count": len(sample_counts),
                        "independent_unit_count": None},
            "availability": {"status": "available" if available else "unavailable",
                             "reason_code": None if available else "cohort_source_unavailable"},
            "reason_codes": reasons, "execution_available": False,
        }

    def _public(self, owner, rid, row):
        saved = {key: row[key] for key in ("id", "research_id", "members", "digest", "revision",
                  "status", "created_at", "confirmed_at")}
        return deepcopy({**saved, **self._evaluate(owner, rid, row["members"])})

    def create(self, owner, rid, body):
        with self.lock:
            state = self._load(owner, rid)
            if body.expected_version != 0:
                raise HTTPException(409, "object_version_conflict")
            members = [m.model_dump(mode="json") for m in body.members]
            evaluation = self._evaluate(owner, rid, members)
            row = {"id": uid(), "research_id": rid, "members": members,
                   "digest": self._digest(rid, members), "revision": 1, "status": "pending",
                   "created_at": now(), "confirmed_at": None}
            state["cohorts"][row["id"]] = row
            self._save(owner, rid, state)
            return deepcopy({**row, **evaluation})

    def confirm(self, owner, rid, cid, body):
        with self.lock:
            state = self._load(owner, rid)
            row = self._row(state, cid)
            if body.digest != row["digest"]:
                raise HTTPException(409, "cohort_decision_changed")
            # An exact lost-response replay cannot create a second decision.
            if row["status"] == "confirmed" and body.expected_version in {1, 2}:
                return self._public(owner, rid, row)
            if body.expected_version != row["revision"]:
                raise HTTPException(409, "object_version_conflict")
            evaluation = self._evaluate(owner, rid, row["members"])
            if evaluation["availability"]["status"] != "available":
                raise HTTPException(409, "cohort_source_unavailable")
            row.update(status="confirmed", revision=2, confirmed_at=now())
            self._save(owner, rid, state)
            return deepcopy({**row, **evaluation})

    def list(self, owner, rid):
        with self.lock:
            state = self._load(owner, rid)
            return {"cohorts": [self._public(owner, rid, row) for row in state["cohorts"].values()]}

    def get(self, owner, rid, cid):
        with self.lock:
            return self._public(owner, rid, self._row(self._load(owner, rid), cid))


def install_analysis_cohort_http(app, store):
    prefix = "/api/researches/{rid}/analysis-cohorts"

    @app.post(prefix)
    def create(rid: str, body: CohortCreate, request: Request):
        return store.create(request.state.principal.id, rid, body)

    @app.get(prefix)
    def listing(rid: str, request: Request):
        return store.list(request.state.principal.id, rid)

    @app.get(prefix + "/{cid}")
    def detail(rid: str, cid: str, request: Request):
        return store.get(request.state.principal.id, rid, cid)

    @app.post(prefix + "/{cid}/confirm")
    def confirm(rid: str, cid: str, body: CohortConfirmation, request: Request):
        return store.confirm(request.state.principal.id, rid, cid, body)
