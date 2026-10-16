"""Research-owned M1 objects, atomic persistence and protocol edition isolation.

The existing single-process Web store lock serializes read/check/write. No
scientific execution occurs here; document generation runs outside that lock.
"""
from copy import deepcopy
from datetime import date, datetime
import json
from pathlib import Path

from fastapi import HTTPException
from pydantic import ValidationError

from .research_object_models import LeadCreate, ProtocolContent, MappingInput
from .sessions import ID, now, read_file, uid, write_file

OBJECT_STORE_BYTES = 4 * 1024 * 1024
OBJECT_COUNT_LIMIT = 4096
CATALOG_PATH = Path(__file__).resolve().parents[3] / "examples/protocol-visualization/molecules/data/catalog.json"
COLLECTIONS = ("protocols", "versions", "runs", "samples", "assessments", "leads", "actions")
PUBLIC = {
    "protocols": ("id", "research_id", "name", "origin", "citation"),
    "versions": ("id", "protocol_id", "version", "label", "status", "based_on_version_id",
                 "change_note", "total_days", "stages", "reagents", "operations",
                 "provenance", "confirmed_at", "unconfirmed", "source_review"),
    "runs": ("id", "research_id", "name", "protocol_version_id", "cell_line", "start_date", "state", "graft", "purpose"),
    "samples": ("id", "run_id", "day", "collected_on", "assay", "material_id", "session_id", "assessment_id", "mapping_input", "workflow"),
    "assessments": ("id", "sample_id", "status", "versions", "chain", "target_fraction",
                    "gestation", "tree_position", "mapped_cells", "alerts", "evidence_ids", "failure", "tool_run_id",
                    "method_label", "scientific_status", "ood_status", "n_cells", "n_tree_cells",
                    "shared_genes", "selected_genes", "reference_genes_not_measured",
                    "query_genes_not_in_reference", "limitations", "tree_unavailable_cells", "normalization", "marker_expression"),
    "leads": ("id", "run_id", "sample_id", "chain_level", "summary", "status", "created_by"),
    "actions": ("id", "research_id", "title", "context", "tier", "estimate", "kind", "status", "result_ref"),
}
SINGULAR = {"protocols": "protocol", "versions": "protocol_version", "runs": "run",
            "samples": "sample", "assessments": "assessment", "leads": "lead", "actions": "action"}
COMMON_PUBLIC = ("revision", "created_at", "updated_at")


def local_today():
    """Date in the deployment's local timezone, not an assumed client timezone."""
    return datetime.now().astimezone().date()


def pending_source_review():
    return {"status": "pending", "reviewed_at": None, "note": ""}


def execution_readiness(value):
    missing = []
    if not value.get("total_days"):
        missing.append("total_days_unknown")
    if any(not r["dose_text"] for r in value["reagents"]):
        missing.append("reagent_dose_unknown")
    if any(r["start_day"] is None or r["end_day"] is None for r in value["reagents"]):
        missing.append("reagent_window_unknown")
    if any(o["day"] is None for o in value["operations"]):
        missing.append("operation_day_unknown")
    unchecked = bool(value.get("unconfirmed") or any(r["unconfirmed"] for r in value["reagents"]))
    return {"status": "incomplete" if missing else "needs_review" if unchecked else "ready",
            "reasons": missing + (["unconfirmed_fields"] if unchecked else [])}


def public(kind, value):
    result = deepcopy({key: value[key] for key in (*PUBLIC[kind], *COMMON_PUBLIC) if key in value})
    if kind == "versions":
        result.setdefault("unconfirmed", [])
        result["total_days"] = result.get("total_days") or None
        result.setdefault("source_review", pending_source_review())
        result["execution_readiness"] = execution_readiness(value)
    if kind == "runs":
        result.setdefault("purpose", "execution")
    return result


def check_revision(value, expected):
    if value["revision"] != expected:
        raise HTTPException(409, "object_version_conflict")


def touch(value):
    value["revision"] += 1
    value["updated_at"] = now()


def record(**fields):
    return {"id": uid(), "revision": 1, "created_at": now(), "updated_at": now(), **fields}


class ResearchObjectStore:
    def __init__(self, researches):
        self.researches = researches
        self.lock = researches.lock

    def _load(self, owner, rid):
        try:
            self.researches.owned(owner, rid)
        except HTTPException as exc:
            if exc.status_code == 404:
                raise HTTPException(404, "research_not_found") from None
            raise
        path = self.researches.directory(rid) / "objects.json"
        try:
            raw = read_file(path, OBJECT_STORE_BYTES)
        except FileNotFoundError:
            # A broken symlink is an invalid store, never a new empty research.
            if path.is_symlink():
                raise HTTPException(409, "object_store_unavailable") from None
            return {"schema_version": 1, **{key: {} for key in COLLECTIONS}}
        except (OSError, ValueError):
            raise HTTPException(409, "object_store_unavailable") from None
        try:
            state = json.loads(raw)
            if state["schema_version"] != 1 or any(not isinstance(state[key], dict) for key in COLLECTIONS):
                raise ValueError("object_store_schema")
            for kind in COLLECTIONS:
                for oid, value in state[kind].items():
                    if (not ID.fullmatch(oid) or not isinstance(value, dict) or value.get("id") != oid
                            or type(value.get("revision")) is not int or value["revision"] < 1):
                        raise ValueError("object_store_identity")
            return state
        except (KeyError, TypeError, ValueError):
            raise HTTPException(409, "object_store_unavailable") from None

    def _save(self, rid, state):
        if sum(len(state[key]) for key in COLLECTIONS) > OBJECT_COUNT_LIMIT:
            raise HTTPException(409, "research_object_limit")
        raw = json.dumps(state, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
        if len(raw) > OBJECT_STORE_BYTES:
            raise HTTPException(413, "research_object_limit")
        write_file(self.researches.directory(rid) / "objects.json", raw)

    @staticmethod
    def _get(state, kind, oid):
        if not isinstance(oid, str) or not ID.fullmatch(oid) or oid not in state[kind]:
            raise HTTPException(404, SINGULAR[kind] + "_not_found")
        return state[kind][oid]

    @staticmethod
    def _protocol(state, p):
        value = public("protocols", p)
        versions = sorted((v for v in state["versions"].values() if v["protocol_id"] == p["id"]),
                          key=lambda v: v["version"])
        value["versions"] = [public("versions", v) for v in versions]
        value["latest"] = value["versions"][-1]
        value["latest_version_id"] = value["latest"]["id"]
        return value

    def _content(self, existing=None, changes=None):
        initial = {key: existing[key] for key in ProtocolContent.model_fields if key in existing} if existing else {}
        try:
            content = ProtocolContent.model_validate({**initial, **(changes or {})}).model_dump(mode="json")
        except ValidationError:
            raise HTTPException(422, "invalid_protocol_content") from None
        previous = {r["id"]: r for r in (existing or {}).get("reagents", [])}
        for reagent in content["reagents"]:
            old = previous.get(reagent["id"])
            candidates = [old] if old else [r for r in previous.values() if r["name"] == reagent["name"]]
            for entry in reagent["field_provenance"]:
                field = entry["field"]
                inherited = [r for r in candidates if entry in r.get("field_provenance", [])]
                if inherited and not any(r["name"] == reagent["name"] and r[field] == reagent[field]
                                         for r in inherited):
                    raise HTTPException(422, "protocol_provenance_stale")
        requested = {r["catalog_id"] for r in content["reagents"] if r["catalog_id"] is not None}
        if requested:
            try:
                known = {r["id"] for r in json.loads(CATALOG_PATH.read_text())["compounds"]}
            except (OSError, KeyError, TypeError, ValueError):
                raise HTTPException(409, "reagent_catalog_unavailable") from None
            if requested - known:
                raise HTTPException(422, "reagent_catalog_id_unknown")
        return content

    def protocol(self, owner, rid, pid):
        with self.lock:
            state = self._load(owner, rid)
            return self._protocol(state, self._get(state, "protocols", pid))

    def create_protocol(self, owner, rid, body, *, settings=None):
        imported = None
        if body.material_id:
            from .protocol_import import prepare
            imported = prepare(self.researches, owner, rid, body.material_id, settings, CATALOG_PATH)
        with self.lock:
            state = self._load(owner, rid)
            p = record(research_id=rid, name=imported.name if imported else body.name,
                       origin="lab" if imported else body.origin,
                       citation=body.citation.model_dump(mode="json") if body.citation else None)
            provenance = {"material_id": body.material_id,
                          "formalization_version_id": imported.formalization_id if imported else None}
            v = record(protocol_id=p["id"], version=1, status="draft", based_on_version_id=None,
                       confirmed_at=None, source_review=pending_source_review(), provenance=provenance,
                       **self._content(changes=imported.content if imported else None))
            if imported:
                v["_formalization_sha256"] = imported.sha256
                write_file(self.researches.directory(rid) / "protocol-formalizations" /
                           (imported.formalization_id + ".json"), imported.raw)
            state["protocols"][p["id"]] = p
            state["versions"][v["id"]] = v
            self._save(rid, state)
            return self._protocol(state, p)

    def formalization(self, owner, rid, pid, vid):
        from .protocol_formalization import _sha
        from .protocol_import import FORMALIZATION_LIMIT
        with self.lock:
            state = self._load(owner, rid)
            v = self._version(state, pid, vid)
            fid = v["provenance"]["formalization_version_id"]
            if not fid:
                raise HTTPException(404, "protocol_formalization_not_found")
            try:
                if not ID.fullmatch(fid):
                    raise ValueError("invalid_formalization_id")
                raw = read_file(self.researches.directory(rid) / "protocol-formalizations" /
                                (fid + ".json"), FORMALIZATION_LIMIT)
                if _sha(raw) != v["_formalization_sha256"]:
                    raise ValueError("formalization_integrity")
                value = json.loads(raw)
            except (OSError, ValueError, KeyError, TypeError):
                raise HTTPException(409, "protocol_formalization_unavailable") from None
            allowed = ("id", "created_at", "bpl", "steps", "questions", "excluded_sources", "supplements",
                       "source_binding", "generation", "coverage_state", "review_state", "syntax_state",
                       "compiler_state", "diagnostics", "unchecked", "compiler", "stages",
                       "projection", "projected_content")
            return {key: value[key] for key in allowed if key in value}

    def create_version(self, owner, rid, pid, body):
        with self.lock:
            state = self._load(owner, rid)
            p = self._get(state, "protocols", pid)
            check_revision(p, body.expected_version)
            parent = self._version(state, pid, body.based_on_version_id)
            content = self._content(parent, body.changes.model_dump(mode="json", exclude_unset=True))
            number = max(v["version"] for v in state["versions"].values() if v["protocol_id"] == pid) + 1
            v = record(protocol_id=pid, version=number, status="draft", based_on_version_id=parent["id"],
                       confirmed_at=None, source_review=pending_source_review(), provenance=deepcopy(parent["provenance"]), **content)
            if "_formalization_sha256" in parent:
                v["_formalization_sha256"] = parent["_formalization_sha256"]
            state["versions"][v["id"]] = v
            touch(p)
            self._save(rid, state)
            return public("versions", v)

    def _version(self, state, pid, vid):
        self._get(state, "protocols", pid)
        v = self._get(state, "versions", vid)
        if v["protocol_id"] != pid:
            raise HTTPException(404, "protocol_version_not_found")
        return v

    def edit_version(self, owner, rid, pid, vid, body, *, confirm=False):
        with self.lock:
            state = self._load(owner, rid)
            v = self._version(state, pid, vid)
            check_revision(v, body.expected_version)
            if v["status"] != "draft":
                raise HTTPException(409, "protocol_version_immutable")
            if confirm:
                if execution_readiness(v)["status"] == "incomplete":
                    raise HTTPException(409, "protocol_incomplete")
                if v.get("unconfirmed") or any(r["unconfirmed"] for r in v["reagents"]):
                    raise HTTPException(409, "protocol_unconfirmed_fields")
                v.update(status="confirmed", confirmed_at=now())
            else:
                if v.get("source_review", {}).get("status") == "reviewed":
                    raise HTTPException(409, "protocol_version_immutable")
                changes = body.model_dump(mode="json", exclude_unset=True, exclude={"expected_version"})
                v.update(self._content(v, changes))
            touch(v)
            touch(state["protocols"][pid])
            self._save(rid, state)
            return public("versions", v)

    def review_source(self, owner, rid, pid, vid, body):
        """Record an explicit, version-bound review, independently of execution."""
        with self.lock:
            state = self._load(owner, rid)
            v = self._version(state, pid, vid)
            check_revision(v, body.expected_version)
            if v.get("source_review", {}).get("status") == "reviewed":
                raise HTTPException(409, "protocol_version_immutable")
            p = state["protocols"][pid]
            mid = v["provenance"].get("material_id")
            if not mid and not p.get("citation"):
                raise HTTPException(409, "protocol_source_required")
            if mid:
                try:
                    with self.researches.checked_material(owner, rid, mid):
                        pass
                except (OSError, ValueError):
                    raise HTTPException(409, "research_material_unavailable") from None
                if v["provenance"].get("formalization_version_id"):
                    self.formalization(owner, rid, pid, vid)
            v["source_review"] = {"status": "reviewed", "reviewed_at": now(), "note": body.note}
            v["unconfirmed"] = [field for field in v.get("unconfirmed", []) if field != "source_review"]
            touch(v)
            touch(p)
            self._save(rid, state)
            return public("versions", v)

    @staticmethod
    def _run(state, r, today):
        result = public("runs", r)
        if result["purpose"] == "retrospective":
            result.update(day=None, stage_index=None, today=[])
            return result
        day = (today - date.fromisoformat(r["start_date"])).days if r["start_date"] else None
        result.update(day=day, stage_index=None, today=[])
        version = state["versions"][r["protocol_version_id"]]
        if (r["state"] != "differentiating" or day is None or not version.get("total_days")
                or not 0 <= day <= version["total_days"]):
            return result
        stages = version["stages"]
        if stages:
            result["stage_index"] = next((s["index"] for s in stages if s["start_day"] <= day <= s["end_day"]), None)
        else:
            result["stage_index"] = 1 if day <= 4 else 2 if day <= 10 else 3 if day <= 16 else 4
        for reagent in version["reagents"]:
            if day == reagent["start_day"]:
                result["today"].append({"kind": "add", "label": "加入 " + reagent["short"]})
            if day == reagent["end_day"] + 1:
                result["today"].append({"kind": "remove", "label": "撤除 " + reagent["short"]})
        labels = {"feed": "换液", "passage": "传代", "sample": "取样", "freeze": "冻存", "other": "操作"}
        for operation in version["operations"]:
            if day == operation["day"]:
                label = labels[operation["kind"]]
                if operation["note"]:
                    label += "：" + operation["note"]
                result["today"].append({"kind": operation["kind"], "label": label})
        return result

    def run(self, owner, rid, oid):
        with self.lock:
            state = self._load(owner, rid)
            return self._run(state, self._get(state, "runs", oid), local_today())

    def create_run(self, owner, rid, body):
        with self.lock:
            state = self._load(owner, rid)
            v = self._get(state, "versions", body.protocol_version_id)
            if body.purpose == "retrospective":
                if v.get("source_review", {}).get("status") != "reviewed":
                    raise HTTPException(409, "protocol_source_not_reviewed")
            elif v["status"] != "confirmed":
                raise HTTPException(409, "protocol_version_not_confirmed")
            r = record(research_id=rid, **body.model_dump(mode="json", exclude={"expected_version"}))
            state["runs"][r["id"]] = r
            self._save(rid, state)
            return self._run(state, r, local_today())

    def edit_run(self, owner, rid, oid, body):
        with self.lock:
            state = self._load(owner, rid)
            r = self._get(state, "runs", oid)
            check_revision(r, body.expected_version)
            r.update(body.model_dump(mode="json", exclude_unset=True, exclude={"expected_version"}))
            touch(r)
            self._save(rid, state)
            return self._run(state, r, local_today())

    def _sample_material(self, owner, rid, mid):
        try:
            material = self.researches.material(owner, rid, mid)
        except HTTPException as exc:
            if exc.status_code == 404:
                raise HTTPException(404, "material_not_found") from None
            raise
        if material["kind"] != "h5ad":
            raise HTTPException(422, "sample_material_requires_h5ad")
        try:
            with self.researches.checked_material(owner, rid, mid):
                pass
        except (OSError, ValueError):
            raise HTTPException(409, "research_material_unavailable") from None

    @staticmethod
    def _sample(state, sample):
        result = public("samples", sample)
        assessment = state["assessments"].get(sample["assessment_id"])
        status = "data_attached" if sample["material_id"] else "collected"
        if assessment:
            status = {"running": "mapping", "done": "done", "failed": "failed",
                      "unavailable": "failed"}.get(assessment["status"], status)
        result["status"] = status
        result.setdefault("workflow", None)
        result["assessment_availability"] = (
            {"status": "unavailable", "code": sample.get("_mapping_unavailable") or "standard_mapping_not_configured"}
            if sample["material_id"] and (not assessment or (
                assessment["status"] in ("failed", "unavailable") and sample.get("_mapping_unavailable")
            )) else None
        )
        result["assessment_request"] = None
        for action in state["actions"].values():
            if action["kind"] == "atlas_assessment" and action["context"].get("sample_id") == sample["id"]:
                result["assessment_request"] = {"action_id": action["id"], "status": action["status"]}
        return result

    def create_sample(self, owner, rid, oid, body):
        if body.material_id:
            self._sample_material(owner, rid, body.material_id)
        with self.lock:
            state = self._load(owner, rid)
            r = self._get(state, "runs", oid)
            check_revision(r, body.expected_version)
            s = record(run_id=oid, session_id=None, assessment_id=None,
                       **body.model_dump(mode="json", exclude={"expected_version"}))
            if body.mapping_input is not None:
                s["mapping_input"] = body.mapping_input.model_dump(mode="json", exclude_none=True)
            state["samples"][s["id"]] = s
            touch(r)
            self._save(rid, state)
            return self._sample(state, s)

    def attach_sample(self, owner, rid, oid, body):
        # Check ownership and revision before hashing; repeat after I/O so a
        # concurrent attachment cannot be overwritten. No global lock during I/O.
        def check(state):
            sample = self._get(state, "samples", oid)
            check_revision(sample, body.expected_version)
            if sample["material_id"] is not None:
                raise HTTPException(409, "sample_has_material")
            return sample

        with self.lock:
            check(self._load(owner, rid))
        self._sample_material(owner, rid, body.material_id)
        with self.lock:
            state = self._load(owner, rid)
            sample = check(state)
            if body.mapping_input is not None:
                declaration = body.mapping_input.model_dump(mode="json", exclude_none=True)
                if sample.get("mapping_input") is not None and sample["mapping_input"] != declaration:
                    raise HTTPException(409, "mapping_input_immutable")
                sample["mapping_input"] = declaration
            sample["material_id"] = body.material_id
            touch(sample)
            self._save(rid, state)
            return self._sample(state, sample)

    def propose_assessment(self, owner, rid, oid, body):
        with self.lock:
            state = self._load(owner, rid)
            s = self._get(state, "samples", oid)
            check_revision(s, body.expected_version)
            if any(a["kind"] == "atlas_assessment" and a["context"].get("sample_id") == oid
                   and a["status"] in {"pending", "approved", "running"} for a in state["actions"].values()):
                raise HTTPException(409, "assessment_request_active")
            action = record(research_id=rid, title="样本图谱映射", context={"run_id": s["run_id"], "sample_id": oid},
                            tier="formal", estimate="执行接入后估计", kind="atlas_assessment", status="pending",
                            result_ref=None)
            state["actions"][action["id"]] = action
            touch(s)
            self._save(rid, state)
            return public("actions", action)

    def decide(self, owner, rid, oid, body, *, approve):
        with self.lock:
            state = self._load(owner, rid)
            action = self._get(state, "actions", oid)
            if body.expected_version is not None:
                check_revision(action, body.expected_version)
            if action["status"] != "pending":
                raise HTTPException(409, "action_not_pending")
            action["status"] = "approved" if approve else "declined"
            touch(action)
            self._save(rid, state)
            return public("actions", action)

    def assessment(self, owner, rid, oid):
        with self.lock:
            state = self._load(owner, rid)
            return self._assessment(rid, self._get(state, "assessments", oid))

    def create_lead(self, owner, rid, **fields):
        """Trusted producer entry; browser clients cannot invent analysis findings."""
        body = LeadCreate.model_validate(fields)
        with self.lock:
            state = self._load(owner, rid)
            self._get(state, "runs", body.run_id)
            if body.sample_id:
                sample = self._get(state, "samples", body.sample_id)
                if sample["run_id"] != body.run_id:
                    raise HTTPException(404, "sample_not_found")
            lead = record(status="open", **body.model_dump(mode="json"))
            state["leads"][lead["id"]] = lead
            self._save(rid, state)
            return public("leads", lead)

    def edit_lead(self, owner, rid, oid, body):
        with self.lock:
            state = self._load(owner, rid)
            lead = self._get(state, "leads", oid)
            check_revision(lead, body.expected_version)
            if lead["status"] != "open":
                raise HTTPException(409, "lead_not_open")
            lead["status"] = body.status
            touch(lead)
            self._save(rid, state)
            return public("leads", lead)

    def workbench(self, owner, rid):
        with self.lock:
            state = self._load(owner, rid)
            today = local_today()
            samples = sorted(state["samples"].values(), key=lambda s: (s["day"], s["created_at"], s["id"]))
            assessment_ids = {s["assessment_id"] for s in samples if s["assessment_id"] is not None}
            return {
                "protocols": [self._protocol(state, p) for p in state["protocols"].values()],
                "runs": [self._run(state, r, today) for r in state["runs"].values()],
                "samples": [self._sample(state, s) for s in samples],
                "assessments": [self._assessment(rid, self._get(state, "assessments", oid)) for oid in sorted(assessment_ids)],
                "leads": [public("leads", l) for l in state["leads"].values() if l["status"] == "open"],
                "actions": [public("actions", a) for a in state["actions"].values() if a["status"] == "pending"],
            }

    def sample(self, owner, rid, oid):
        with self.lock:
            state = self._load(owner, rid)
            return self._sample(state, self._get(state, "samples", oid))

    def mapping_source(self, owner, rid, oid):
        with self.lock:
            state = self._load(owner, rid)
            sample = self._get(state, "samples", oid)
            return {"sample": deepcopy(sample),
                    "assessment": deepcopy(state["assessments"].get(sample["assessment_id"]))}

    def declare_mapping(self, owner, rid, oid, body):
        with self.lock:
            state = self._load(owner, rid)
            sample = self._get(state, "samples", oid)
            check_revision(sample, body.expected_version)
            if body.mapping_input is not None:
                declaration = body.mapping_input.model_dump(mode="json", exclude_none=True)
                if sample.get("mapping_input") is not None and sample["mapping_input"] != declaration:
                    raise HTTPException(409, "mapping_input_immutable")
                if sample.get("mapping_input") is None:
                    sample["mapping_input"] = declaration
                    touch(sample)
                    self._save(rid, state)

    def supplement_sample_input(self, owner, rid, oid, body):
        """Accept a user-submitted declaration revision; never rewrite past attempts."""
        with self.lock:
            state = self._load(owner, rid)
            sample = self._get(state, "samples", oid)
            check_revision(sample, body.expected_version)
            if sample["material_id"] is None:
                raise HTTPException(409, "mapping_material_required")
            old = sample.get("mapping_input") or {}
            incoming = body.mapping_input.model_dump(mode="json", exclude_unset=True) if body.mapping_input else {}
            merged = {key: value for key, value in {**old, **incoming}.items() if value is not None}
            if merged and merged["matrix_location"] not in self.researches.material(owner, rid, sample["material_id"])["locations"]:
                raise HTTPException(422, "sample_matrix_location_unavailable")
            changed = merged != old
            previous = state["assessments"].get(sample["assessment_id"])
            if changed and previous and previous["status"] == "running":
                raise HTTPException(409, "mapping_already_started")
            if changed:
                try:
                    MappingInput.model_validate(merged)
                except ValidationError:
                    raise HTTPException(422, "sample_declaration_conflict") from None
                # Freeze legacy attempts before accepting a user-submitted correction.
                for attempt in state["assessments"].values():
                    if attempt["sample_id"] == oid and "_mapping_config" in attempt:
                        attempt.setdefault("_mapping_input", deepcopy(old))
                sample["mapping_input"] = merged
                sample.pop("_workflow_answers", None)
                touch(sample)
                self._save(rid, state)
            return changed

    def sample_answers(self, owner, rid, oid):
        with self.lock:
            sample = self._get(self._load(owner, rid), "samples", oid)
            return deepcopy({**(sample.get("mapping_input") or {}), **sample.get("_workflow_answers", {})})

    def save_sample_answers(self, owner, rid, oid, revision, answers):
        with self.lock:
            state = self._load(owner, rid)
            sample = self._get(state, "samples", oid)
            check_revision(sample, revision)
            if sample.get("_workflow_answers") != answers:
                sample["_workflow_answers"] = deepcopy(answers)
                touch(sample)
                self._save(rid, state)
            return sample["revision"]

    def set_sample_workflow(self, owner, rid, oid, workflow, *, attempt_id=None):
        """Fence late workers so they cannot overwrite a resumed sample."""
        with self.lock:
            state = self._load(owner, rid)
            sample = self._get(state, "samples", oid)
            if sample["assessment_id"] != attempt_id:
                return False
            if sample.get("workflow") != workflow:
                sample["workflow"] = deepcopy(workflow)
                if workflow.get("session_id"):
                    sample["session_id"] = workflow["session_id"]
                # Agent progress is not a user-input revision and must not race an answer.
                sample["updated_at"] = now()
                self._save(rid, state)
            return True

    def mapping_blocked(self, owner, rid, oid, reason):
        with self.lock:
            state = self._load(owner, rid)
            sample = self._get(state, "samples", oid)
            previous = sample.get("_mapping_unavailable")
            if not sample["assessment_id"]:
                previous = previous or "standard_mapping_not_configured"
            if previous != reason:
                sample["_mapping_unavailable"] = reason
                if reason == "mapping_worker_busy":
                    from .sample_workflow import issue, state_for
                    workflow = state_for([issue(reason)], sample["assessment_id"])
                    workflow.update(session_id=sample.get("session_id"), agent_state=None)
                    sample["workflow"] = workflow
                touch(sample)
                self._save(rid, state)

    def begin_mapping(self, owner, rid, oid, expected_revision, config, *, allow_completed=False):
        with self.lock:
            state = self._load(owner, rid)
            sample = self._get(state, "samples", oid)
            check_revision(sample, expected_revision)
            previous = state["assessments"].get(sample["assessment_id"])
            if previous and (previous["status"] == "running" or previous["status"] == "done" and not allow_completed):
                raise HTTPException(409, "mapping_already_started")
            assessment = record(sample_id=oid, status="running", versions={}, chain=[],
                                target_fraction=None, gestation=[], tree_position={}, mapped_cells=[],
                                alerts=[], evidence_ids=[], failure=None,
                                _mapping_config=deepcopy(config), _material_id=sample["material_id"],
                                _mapping_input=deepcopy(sample["mapping_input"]))
            state["assessments"][assessment["id"]] = assessment
            sample["assessment_id"] = assessment["id"]
            sample["_mapping_unavailable"] = None
            sample["workflow"] = {"status": "running", "attempt_id": assessment["id"],
                                  "issues": [], "session_id": sample.get("session_id"), "agent_state": None}
            touch(sample)
            self._save(rid, state)
            return assessment["id"]

    def finish_mapping(self, owner, rid, aid, tool_run_id, result, receipt, *, prepare_analysis):
        with self.lock:
            state = self._load(owner, rid)
            assessment = self._get(state, "assessments", aid)
            sample = self._get(state, "samples", assessment["sample_id"])
            if assessment["status"] != "running" or sample["assessment_id"] != aid:
                return  # A recovered/interrupted worker cannot resurrect an old attempt.
            assessment.update(status="done", tool_run_id=tool_run_id, _result=result, _receipt=receipt)
            self._assessment(rid, assessment)  # Verify before committing success.
            experiment = self._get(state, "runs", sample["run_id"])
            assessment["_analysis"] = prepare_analysis(sample, experiment, assessment)
            touch(assessment)
            touch(sample)
            self._save(rid, state)

    def fail_mapping(self, owner, rid, aid, reason):
        with self.lock:
            state = self._load(owner, rid)
            assessment = self._get(state, "assessments", aid)
            if assessment["status"] != "running":
                return
            assessment.update(status="failed", failure={"code": reason, "message": "快速映射未完成，请核对输入与资源后重试。"})
            touch(assessment)
            sample = self._get(state, "samples", assessment["sample_id"])
            if sample["assessment_id"] == aid:
                touch(sample)
            self._save(rid, state)

    def marker_expression(self, owner, rid, aid):
        with self.lock:
            state = self._load(owner, rid)
            assessment = self._get(state, "assessments", aid)
            return self._assessment(rid, assessment, marker_expression=True)

    def _assessment(self, rid, assessment, *, marker_expression=False):
        result = public("assessments", assessment)
        if "_analysis" in assessment:
            result["analysis_id"] = assessment["_analysis"]["id"]
        if assessment["status"] != "done" or "_result" not in assessment:
            if marker_expression:
                raise HTTPException(404, "marker_expression_unavailable")
            return result
        import hashlib
        try:
            root = self.researches.directory(rid)
            def checked(binding, limit):
                relative = Path(binding["path"])
                if relative.is_absolute() or ".." in relative.parts or relative.parts[:2] != ("atlas-runs", assessment["id"]):
                    raise ValueError("mapping_result_path")
                path = root
                for part in relative.parts:
                    path = path / part
                    if path.is_symlink():
                        raise ValueError("mapping_result_symlink")
                raw = read_file(path, limit)
                if hashlib.sha256(raw).hexdigest() != binding["sha256"]:
                    raise ValueError("mapping_result_hash")
                return json.loads(raw)
            payload = checked(assessment["_result"], 2 * 1024 * 1024)
            receipt = checked(assessment["_receipt"], 2 * 1024 * 1024)
            if (receipt["execution_state"] != "succeeded" or receipt["run_id"] != assessment["tool_run_id"]
                    or receipt["result"] != payload
                    or payload["versions"]["tree"] != assessment["_mapping_config"]["tree_sha256"]
                    or payload["reference_manifest_sha256"] != assessment["_mapping_config"]["reference_manifest_sha256"]
                    or receipt["request"]["tool_id"] != "P0-02"):
                raise ValueError("mapping_result_binding")
            if marker_expression:
                metadata = payload.get("marker_expression")
                if not metadata:
                    raise HTTPException(404, "marker_expression_unavailable")
                artifacts = [a for a in receipt["artifacts"] if a["kind"] == "quick_atlas_marker_expression"]
                if len(artifacts) != 1 or artifacts[0]["sha256"] != metadata["sha256"]:
                    raise ValueError("marker_expression_binding")
                artifact = artifacts[0]
                binding = {"path": str(Path(artifact["path"]).relative_to(root)), "sha256": artifact["sha256"]}
                panel = checked(binding, 32 * 1024 * 1024)
                if (panel["tree_version"] != payload["versions"]["tree"]
                        or panel["feature_set_sha256"] != payload["feature_set_sha256"]
                        or panel["normalization"] != payload["normalization"]
                        or panel["genes"] != metadata["genes"]
                        or panel["object_version"] != metadata["version"]
                        or len(panel["sample"]["values"]) != len(payload["mapped_cells"])
                        or len(panel["reference"]["values"]) != metadata["n_reference_points"]):
                    raise ValueError("marker_expression_binding")
                return {**{key: panel[key] for key in ("object_version", "genes", "tree_version", "feature_set_sha256", "normalization")},
                        "gene_status": [{key: item[key] for key in ("gene", "status", "missing_from")} for item in panel["gene_status"]],
                        "sample": {"values": panel["sample"]["values"]},
                        "reference": {key: panel["reference"][key] for key in ("tree_cell_indices", "values", "excluded_reason")}}
            result.update(public("assessments", payload))
            return result
        except (OSError, ValueError, KeyError, TypeError):
            raise HTTPException(409, "mapping_result_unavailable") from None

    def mapping_attempt(self, owner, rid, aid):
        """Read one attempt's identities without requiring mapping success."""
        with self.lock:
            state = self._load(owner, rid)
            assessment = self._get(state, "assessments", aid)
            sample = self._get(state, "samples", assessment["sample_id"])
            experiment = self._get(state, "runs", sample["run_id"])
            return deepcopy(sample), deepcopy(experiment), deepcopy(assessment)

    def backfill_qc_analyses(self, register):
        """Index existing complete QC, including attempts whose mapping failed."""
        for directory in self.researches.root.iterdir():
            if not ID.fullmatch(directory.name) or not directory.is_dir() or directory.is_symlink():
                continue
            rid = directory.name
            owner = self.researches.load(rid)["owner_id"]
            with self.lock:
                state = self._load(owner, rid)
                attempts = [a["id"] for a in state["assessments"].values() if "_mapping_config" in a]
                for aid in attempts:
                    try:
                        register(owner, rid, aid)
                    except HTTPException as exc:
                        if exc.detail == "analysis_source_unavailable":
                            continue  # Missing/incomplete/damaged QC is never a successful record.
                        raise

    def mapping_analyses(self, owner, rid):
        """Private immutable indexes, including unreadable historical sources."""
        with self.lock:
            state = self._load(owner, rid)
            return [deepcopy(a["_analysis"]) for a in state["assessments"].values() if "_analysis" in a]

    def mapping_analysis_source(self, owner, rid, aid):
        """Return a verified source, never treating a failed attempt as an analysis."""
        from bridge.toolkit.contracts import ToolRun
        import hashlib
        with self.lock:
            state = self._load(owner, rid)
            assessment = self._get(state, "assessments", aid)
            if assessment["status"] != "done" or "_receipt" not in assessment:
                raise HTTPException(409, "mapping_result_unavailable")
            self._assessment(rid, assessment)
            sample = self._get(state, "samples", assessment["sample_id"])
            experiment = self._get(state, "runs", sample["run_id"])
            raw = read_file(self.researches.directory(rid) / assessment["_receipt"]["path"], 2 * 1024 * 1024)
            if hashlib.sha256(raw).hexdigest() != assessment["_receipt"]["sha256"]:
                raise HTTPException(409, "mapping_result_unavailable")
            return deepcopy(sample), deepcopy(experiment), deepcopy(assessment), ToolRun.model_validate_json(raw)

    def backfill_mapping_analyses(self, prepare):
        """Upgrade valid historical done attempts; no GET writes and no tool reruns."""
        for directory in self.researches.root.iterdir():
            if not ID.fullmatch(directory.name) or not directory.is_dir() or directory.is_symlink():
                continue
            rid = directory.name
            owner = self.researches.load(rid)["owner_id"]
            with self.lock:
                state = self._load(owner, rid)
                candidates = [a["id"] for a in state["assessments"].values()
                              if a["status"] == "done" and "_receipt" in a and "_analysis" not in a]
                for aid in candidates:
                    try:
                        sample, experiment, assessment, execution = self.mapping_analysis_source(owner, rid, aid)
                    except (HTTPException, OSError, ValueError, KeyError, TypeError):
                        continue  # Corrupt legacy results are not imported as successful history.
                    try:
                        row = prepare(owner, rid, sample, experiment, assessment, execution)
                    except HTTPException as exc:
                        if exc.detail == "mapping_result_unavailable":
                            continue
                        raise
                    state = self._load(owner, rid)
                    state["assessments"][aid]["_analysis"] = row
                    self._save(rid, state)

    def recover_mappings(self):
        for directory in self.researches.root.iterdir():
            if not ID.fullmatch(directory.name) or not directory.is_dir() or directory.is_symlink():
                continue
            rid = directory.name
            owner = self.researches.load(rid)["owner_id"]
            with self.lock:
                state = self._load(owner, rid)
                active = [a["id"] for a in state["assessments"].values()
                          if a["status"] == "running" and "_mapping_config" in a]
            for aid in active:
                self.fail_mapping(owner, rid, aid, "mapping_interrupted")
            with self.lock:
                from .sample_workflow import issue, state_for
                state = self._load(owner, rid)
                changed = False
                for sample in state["samples"].values():
                    workflow = sample.get("workflow")
                    if not workflow:
                        continue
                    if workflow["status"] == "running":
                        workflow = state_for([issue("mapping_interrupted")], sample["assessment_id"])
                        workflow["session_id"] = sample.get("session_id")
                        sample["workflow"] = workflow
                        changed = True
                    if workflow["agent_state"] in {"pending", "scheduled"}:
                        workflow["agent_state"] = "unavailable"
                        changed = True
                if changed:
                    self._save(rid, state)
