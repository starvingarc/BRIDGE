"""Web-only review state and exact declaration confirmations.

All methods run under Service.lock; no provider or executor calls belong here.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import secrets

from fastapi import HTTPException

from .inputs import AssetDeclaration
from .intake import IntakeInput


class Controls:
    def __init__(self, service):
        self.service = service

    def initialize(self, state):
        state.setdefault("input_review_required", False)
        state.setdefault("pending_input_change", None)
        state.setdefault("_chat_input_review", False)
        state.setdefault("_input_revision", 0)
        state.setdefault("_control_epoch", 0)
        if "_qc_declarations" not in state:
            # Upgrade only exact saved input values, never subsequent chat.
            state["_qc_declarations"] = {}
            for asset in state.get("_bundle", {}).get("assets", []):
                aid = asset["asset_id"]
                if aid not in state["_uploads"]:
                    continue
                state["_qc_declarations"][aid] = {key: asset.get(key) for key in
                    ("assay", "matrix_location", "matrix_semantics", "input_level", "metadata")}
                try:
                    self.service.qc_asset(state, aid, register=False)
                except (ValueError, OSError, KeyError):
                    state["input_review_required"] = True
                    state["_chat_input_review"] = True

    def require_ready(self, state):
        if state["input_review_required"]:
            raise HTTPException(409, "input_review_required")

    def fence(self, state):
        self.service.assessment.stop(state, "user_stopped")
        state["_control_epoch"] += 1
        active = state["status"] in {"thinking", "running", "stopping"}
        if state.get("plan") and state["plan"]["status"] in {"proposed", "approved"}:
            state["plan"]["status"] = "cancelled"
            for step in state["plan"]["steps"]:
                if step["status"] == "pending":
                    step["status"], step["reason"] = "cancelled", "stopped"
        state["status"], state["error"] = ("stopping" if active else "idle"), None

    def settle(self, state):
        if state.get("plan") and state["plan"]["status"] == "cancelled":
            for step in state["plan"]["steps"]:
                if step["status"] == "running":
                    step["status"], step["reason"] = "failed", "execution_interrupted"
            if any(step["status"] in {"succeeded", "partial"} for step in state["plan"]["steps"]):
                state["plan"]["status"] = "partial"
        state["status"], state["error"] = "idle", None

    def review(self, state):
        self.fence(state)
        state["_chat_input_review"] = True
        state["input_review_required"] = True

    def stage(self, state, kind, body):
        payload = body.model_dump(mode="json")
        aid = body.upload_id
        if aid not in state["_uploads"]:
            raise HTTPException(404, "upload_not_found")
        if kind == "asset":
            trial = deepcopy(state)
            try:
                self.service.inputs.declare_asset(trial, body)
            except (ValueError, OSError):
                raise HTTPException(422, "invalid_asset_declaration") from None
            before = state["_asset_declarations"].get(aid) or state["_qc_declarations"].get(aid, {})
            values = {key: payload[key] for key in ("assay", "matrix_location", "matrix_semantics", "input_level", "metadata")}
        elif kind == "intake":
            trial = deepcopy(state)
            try:
                self.service.intake.commit(trial, body)
            except (ValueError, OSError, KeyError):
                raise HTTPException(422, "invalid_intake_declaration") from None
            before = self.service.intake.current_facts(state, aid, include_draft=False).model_dump(mode="json")
            values = dict(payload["facts"])
            sources = self.service.intake.confirmation_sources(state, aid)
            before.update(state.get("_intakes", {}).get(aid, {}).get("source_facts", {key: "" for key in sources}))
            values.update(sources)
        else:
            before = state["_uploads"][aid]
            values = {"source_family_id": body.source_family_id}
        changes = [{"field": key, "before": before.get(key), "after": value}
                   for key, value in values.items() if before.get(key) != value]
        if not changes and kind != "intake":
            return
        self.fence(state)
        pending = {"id": secrets.token_hex(16), "kind": kind, "upload_id": aid, "changes": changes}
        pending["digest"] = hashlib.sha256(json.dumps(
            [state["id"], state["_input_revision"], pending], sort_keys=True, separators=(",", ":"),
            allow_nan=False).encode()).hexdigest()
        state["pending_input_change"] = pending
        state["_pending_input_payload"] = payload
        state["_pending_input_revision"] = state["_input_revision"]
        state["input_review_required"] = True

    def resolve(self, state, change_id, digest, *, commit):
        pending = state["pending_input_change"]
        if (not pending or pending["id"] != change_id
                or not secrets.compare_digest(pending["digest"], digest)
                or state.get("_pending_input_revision") != state["_input_revision"]):
            raise HTTPException(409, "input_change_mismatch")
        if commit:
            payload = state["_pending_input_payload"]
            aid = pending["upload_id"]
            if pending["kind"] == "asset":
                try:
                    self.service.inputs.declare_asset(state, AssetDeclaration.model_validate(payload))
                except (ValueError, OSError):
                    raise HTTPException(409, "input_change_invalid") from None
                state["_qc_declarations"][aid] = {key: value for key, value in payload.items() if key != "upload_id"}
                # Only a confirmed asset edit invalidates prior QC bindings.
                state["_uploads"][aid]["declaration_start"] += 1
            elif pending["kind"] == "intake":
                try:
                    self.service.intake.commit(state, IntakeInput.model_validate(payload))
                except (ValueError, OSError, KeyError):
                    raise HTTPException(409, "input_change_invalid") from None
            else:
                state["_uploads"][aid]["source_family_id"] = payload["source_family_id"]
                for item in state["uploads"]:
                    if item["id"] == aid:
                        item["source_family_id"] = payload["source_family_id"]
            state["_input_revision"] += 1
            state["_chat_input_review"] = False
        state["pending_input_change"] = None
        state.pop("_pending_input_payload", None)
        state.pop("_pending_input_revision", None)
        state["input_review_required"] = state["_chat_input_review"]

    def keep(self, state):
        if state["pending_input_change"]:
            raise HTTPException(409, "pending_input_change")
        state["_chat_input_review"] = False
        state["input_review_required"] = False
