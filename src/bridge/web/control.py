"""Web-only review state and exact declaration confirmations.

All methods run under Service.lock; no provider or executor calls belong here.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import secrets

from .inputs import checked_bytes, strict_json

from fastapi import HTTPException

from .inputs import AssetDeclaration, Selection
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
        state.setdefault("_input_change_history", [])
        state.setdefault("_invalidated_receipts", {})
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


    def impact(self, state, upload_id, kind, changes, *, root_input_ids=None, selected_tool=None):
        """Trace persisted request/artifact dependencies; never infer biological validity."""
        root = self.service.directory(state["id"])
        upload_path = str(root / "uploads" / (upload_id + ".h5ad"))
        invalidated = state.get("_invalidated_receipts", {})
        runs = []
        reusable_native = set()
        for receipt in state.get("_tool_runs", []):
            if receipt["file"] in invalidated or receipt["state"] not in {"succeeded", "partial"}:
                continue
            try:
                payload = strict_json(checked_bytes(
                    self.service, state, root / "receipts" / receipt["file"], receipt["sha256"]
                ), 128 * 1024 * 1024)
                if (payload["request"]["tool_id"] != receipt["tool_id"]
                        or payload["execution_state"] != receipt["state"]):
                    raise ValueError("canonical_receipt_invalid")
            except (ValueError, OSError, KeyError):
                raise HTTPException(409, "input_change_dependency_unavailable") from None
            if (receipt["tool_id"] in {"P0-01", "P0-02"}
                    or receipt["tool_id"] == "P0-06" and (payload.get("result") or {}).get("runtime_mode") == "exploratory_process"):
                reusable_native.add(receipt["file"])
            paths, identifiers = set(), set()

            def visit(value):
                if isinstance(value, dict):
                    for key, item in value.items():
                        if key == "path" and isinstance(item, str):
                            paths.add(item)
                        elif key == "asset_id" and isinstance(item, str):
                            identifiers.add(item)
                        visit(item)
                elif isinstance(value, list):
                    for item in value:
                        visit(item)

            visit(payload["request"])
            # Structured inputs can themselves bind uploaded matrices or earlier artifacts.
            pending_paths = list(paths)
            seen = set()
            records = {record["path"]: record for record in state.get("_input_objects", {}).values()}
            while pending_paths:
                path = pending_paths.pop()
                if path in seen:
                    continue
                seen.add(path)
                record = records.get(path)
                if record is None:
                    continue
                for dependency in record.get("dependencies", []):
                    paths.add(dependency["path"])
                    pending_paths.append(dependency["path"])
                for identifier in record.get("derivation_inputs", {}):
                    dependency = state["_input_objects"].get(identifier)
                    if dependency is None:
                        raise HTTPException(409, "input_change_dependency_unavailable")
                    paths.add(dependency["path"])
                    pending_paths.append(dependency["path"])
            runs.append((receipt, paths, identifiers, {a["path"] for a in payload["artifacts"]}))
        affected, affected_paths = set(), set()
        display_only = kind == "intake" and bool(changes) and all(row["field"] == "product_name" for row in changes)
        product_only = kind == "intake" and not any(
            change["field"] in {"assay", "matrix_location", "count_semantics", "source_family_id",
                               "sample_id_column", "capture_id_column", "gene_symbol_column"}
            for change in changes
        )
        linked_paths = ({state["_input_objects"][key]["path"] for key in root_input_ids}
                        if root_input_ids is not None else {upload_path})
        linked_runs = set()
        while True:
            previous = len(linked_runs)
            for receipt, paths, identifiers, outputs in runs:
                if (upload_id in identifiers or paths & linked_paths
                        or selected_tool is not None and receipt["tool_id"] == selected_tool):
                    linked_runs.add(receipt["file"])
                    linked_paths.update(outputs)
            if len(linked_runs) == previous:
                break
        # Intake edits alter product interpretation, not input QC or native annotation.
        for receipt, paths, identifiers, outputs in runs:
            touches = receipt["file"] in linked_runs
            affected_by_change = (receipt["tool_id"] == "P0-10" if display_only else
                                  not product_only or receipt["file"] not in reusable_native)
            if touches and affected_by_change and not (kind == "intake" and not changes):
                affected.add(receipt["file"])
                affected_paths.update(outputs)
        while True:
            previous = len(affected)
            for receipt, paths, _, outputs in runs:
                if receipt["file"] not in affected and paths & affected_paths:
                    affected.add(receipt["file"])
                    affected_paths.update(outputs)
            if len(affected) == previous:
                break
        def entry(receipt):
            return {"receipt_sha256": receipt["sha256"], "tool_id": receipt["tool_id"],
                    "label": self.service.registry.describe(receipt["tool_id"]).name
                    if hasattr(self.service, "registry") else "专项分析"}
        return {
            "version": "1.0", "input_revision": state["_input_revision"],
            "affected": [entry(r) for r, _, _, _ in runs if r["file"] in affected],
            "reusable": [entry(r) for r, _, _, _ in runs if r["file"] not in affected],
            "new_approval_required": True,
            "historical_artifacts_preserved": True,
        }


    def selection_impact(self, state, before, after):
        old_inputs = {row["input_id"] for row in before["object_inputs"]}
        new_inputs = {row["input_id"] for row in after["object_inputs"]}
        changed_inputs = sorted(old_inputs - new_inputs)
        # Object revisions follow exact consumers; mode/asset/spec replacements
        # without an old object also invalidate the selected tool's prior runs.
        return self.impact(state, "", "selection", [], root_input_ids=changed_inputs,
            selected_tool=before["tool_id"] if not changed_inputs else None)

    def stage_selection(self, state, body):
        after = body.model_dump(mode="json")
        before = state["_input_selections"].get(body.tool_id)
        if before is None or not any(row["tool_id"] == body.tool_id for row in state["_tool_runs"]):
            return False
        if before == after:
            return True
        self.require_ready(state)
        changes = [{"field": key, "before": before.get(key), "after": value}
                   for key, value in after.items() if before.get(key) != value]
        impact = self.selection_impact(state, before, after)
        self.fence(state)
        pending = {"id": secrets.token_hex(16), "kind": "selection", "upload_id": "",
                   "changes": changes, "impact": impact}
        pending["digest"] = hashlib.sha256(json.dumps(
            [state["id"], state["_input_revision"], pending], sort_keys=True,
            separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        state["pending_input_change"] = pending
        state["_pending_input_payload"] = {"before": before, "after": after}
        state["_pending_input_revision"] = state["_input_revision"]
        state["input_review_required"] = True
        return True

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
        pending["impact"] = self.impact(state, aid, kind, changes)
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
            impact = (self.selection_impact(state, payload["before"], payload["after"])
                      if pending["kind"] == "selection" else
                      self.impact(state, pending["upload_id"], pending["kind"], pending["changes"]))
            if pending.get("impact") != impact:
                raise HTTPException(409, "input_change_impact_changed")
            payload = state["_pending_input_payload"]
            aid = pending["upload_id"]
            if pending["kind"] == "selection":
                selection = Selection.model_validate(payload["after"])
                if state["_input_selections"].get(selection.tool_id) != payload["before"]:
                    raise HTTPException(409, "input_selection_changed")
                try:
                    self.service.inputs.selection_reasons(state, selection, verify=True)
                except (ValueError, OSError):
                    raise HTTPException(409, "input_change_invalid") from None
                state["_input_selections"][selection.tool_id] = selection.model_dump(mode="json")
            elif pending["kind"] == "asset":
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
            affected = {item["receipt_sha256"] for item in pending["impact"]["affected"]}
            for receipt in state.get("_tool_runs", []):
                if receipt["sha256"] in affected:
                    state["_invalidated_receipts"][receipt["file"]] = pending["id"]
            state["_input_change_history"].append(deepcopy(pending))
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
