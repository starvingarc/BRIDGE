"""Bounded workbench records for conversation; scientific receipts keep authority."""
import hashlib
import json

from fastapi import HTTPException

from .sessions import private_text

CONTEXT_BYTES = 48 * 1024
_PROTOCOL_FIELDS = ("total_days", "stages", "reagents", "operations")


def _fields(names, **nested):
    return {**dict.fromkeys(names.split()), **nested}


# Model-purpose projection is narrower than the authenticated workbench API.
# Nested records never inherit future fields from public object serializers.
_RECORDS = {
    "protocols": _fields("id name origin", citation=_fields("title doi")),
    "protocol_versions": _fields("id protocol_id version status based_on_version_id change_note total_days confirmed_at revision",
        source_review=_fields("status"), execution_readiness=_fields("status", reasons=[None]),
        stages=[_fields("index start_day end_day")],
        reagents=[_fields("id name short pathway kind dose_text start_day end_day catalog_id timing_text", unconfirmed=[None])],
        operations=[_fields("day kind note timing_text")]),
    "runs": _fields("id research_id name protocol_version_id start_date state revision day stage_index purpose",
                    today=[_fields("kind label")]),
    "samples": _fields("id run_id day collected_on assay assessment_id revision status",
        assessment_request=_fields("action_id status"), assessment_availability=_fields("status code"),
        workflow=_fields("status attempt_id agent_state", issues=[_fields("step code", fields=[None])])),
    "assessments": _fields("id sample_id status revision", versions=_fields("atlas naming metrics"),
                           failure=_fields("code message")),
    "leads": _fields("id run_id sample_id chain_level summary status created_by revision"),
    "actions": _fields("id title tier estimate kind status revision",
                       context=_fields("run_id sample_id protocol_version_id")),
}


def _project(value, shape):
    if value is None:
        return None
    if isinstance(shape, dict) and isinstance(value, dict):
        return {key: _project(value[key], nested) for key, nested in shape.items() if key in value}
    if isinstance(shape, list) and isinstance(value, list):
        return [_project(item, shape[0]) for item in value]
    if shape is None and isinstance(value, (str, int, float, bool)):
        return _safe_text(value)
    raise HTTPException(409, "object_store_unavailable")


def context_bytes(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()


def context_digest(value):
    return hashlib.sha256(context_bytes(value)).hexdigest()


def _safe_text(value):
    if isinstance(value, str):
        return private_text(value)
    if isinstance(value, dict):
        return {key: _safe_text(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe_text(item) for item in value]
    return value


def build_workbench_context(researches, objects, session):
    """Read only records in the server-bound scope, never another chat or matrix."""
    kind = session.get("conversation_kind")
    if kind is None:
        return None
    rid, run_id = session.get("research_id"), session.get("run_id")
    if kind not in {"run", "research"} or (kind == "run") != (run_id is not None):
        raise HTTPException(409, "conversation_binding_invalid")
    owner = session["owner_id"]
    with researches.lock:
        research = researches.owned(owner, rid)
        board = objects.workbench(owner, rid)
    runs = board["runs"]
    if kind == "run":
        runs = [run for run in runs if run["id"] == run_id]
        if len(runs) != 1:
            raise HTTPException(404, "run_not_found")
    run_ids = {run["id"] for run in runs}
    samples = [sample for sample in board["samples"] if sample["run_id"] in run_ids]
    sample_ids = {sample["id"] for sample in samples}
    versions = {version["id"]: version for protocol in board["protocols"] for version in protocol["versions"]}
    if kind == "run":
        selected_ids = {run["protocol_version_id"] for run in runs}
        try:
            selected_ids |= {versions[vid]["based_on_version_id"] for vid in selected_ids
                             if versions[vid]["based_on_version_id"] is not None}
            selected_versions = [versions[vid] for vid in sorted(selected_ids)]
        except KeyError:
            raise HTTPException(409, "object_store_unavailable") from None
    else:
        selected_versions = list(versions.values())
    protocol_ids = {version["protocol_id"] for version in selected_versions}
    protocols = [{key: protocol[key] for key in ("id", "name", "origin", "citation")}
                 for protocol in board["protocols"] if protocol["id"] in protocol_ids]
    differences = []
    bound_version_ids = {run["protocol_version_id"] for run in runs}
    for version in selected_versions:
        if kind == "run" and version["id"] not in bound_version_ids:
            continue
        parent_id = version["based_on_version_id"]
        if parent_id is None:
            continue
        parent = versions.get(parent_id)
        if parent is None or parent["protocol_id"] != version["protocol_id"]:
            raise HTTPException(409, "object_store_unavailable")
        differences.append({"version_id": version["id"], "based_on_version_id": parent_id,
                            "changed_fields": [field for field in _PROTOCOL_FIELDS
                                               if version[field] != parent[field]]})
    # A stored workflow result ID is not an admitted scientific receipt.
    assessments = [{key: assessment.get(key) for key in
                    ("id", "sample_id", "status", "versions", "revision", "failure")}
                   for assessment in board["assessments"] if assessment["sample_id"] in sample_ids]
    snapshot = {
        "schema_version": 1,
        "state": "available",
        "scope": {"research_id": rid, "run_id": run_id, "kind": kind},
        "research": {key: research[key] for key in ("id", "name", "description")},
        "record_authority": "registered_records_and_workflow_status",
        "scientific_result_authority": "verified_session_result_summary_only",
        "protocols": protocols,
        "protocol_versions": selected_versions,
        "protocol_differences": differences,
        "runs": runs,
        "samples": samples,
        "assessments": assessments,
        "leads": [lead for lead in board["leads"] if lead["run_id"] in run_ids],
        "actions": [action for action in board["actions"]
                    if kind == "research" or action["context"].get("run_id") == run_id],
    }
    for collection, shape in _RECORDS.items():
        snapshot[collection] = [_project(record, shape) for record in snapshot[collection]]
    snapshot = _safe_text(snapshot)
    if len(context_bytes(snapshot)) > CONTEXT_BYTES:
        return {
            "schema_version": 1,
            "state": "unavailable",
            "reason_code": "workbench_context_too_large",
            "scope": snapshot["scope"],
            "object_counts": {key: len(snapshot[key]) for key in
                              ("protocols", "protocol_versions", "runs", "samples", "assessments", "leads", "actions")},
            "next_step": "Use a narrower run conversation or review the records in the workbench.",
        }
    return snapshot
