"""Private intake: researcher statements are not scientific product definitions."""
from __future__ import annotations
from copy import deepcopy
import io
import json
from typing import Literal
from fastapi import HTTPException
from pydantic import Field, field_validator
from .inputs import AssetDeclaration, InputBody, Selection, checked_bytes


class IntakeFacts(InputBody):
    product_name: str | None = Field(default=None, max_length=160)
    product_family: Literal["hpsc_mda", "other", "unknown"] = "unknown"
    target_cell_type: str | None = Field(default=None, max_length=240)
    target_stage: str | None = Field(default=None, max_length=240)
    sampling_context: Literal["pretransplant_preparation", "process_sample", "unknown"] = "unknown"
    independent_cultures: int | None = Field(default=None, ge=1, le=100000, strict=True)
    assay: Literal["scRNA-seq", "snRNA-seq", "unknown"] = "unknown"
    matrix_location: str | None = Field(default=None, max_length=100)
    count_semantics: Literal["raw_counts", "not_raw_counts", "unknown"] = "unknown"
    source_family_id: str | None = Field(default=None, max_length=160, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")
    sample_id_column: str | None = Field(default=None, max_length=160)
    capture_id_column: str | None = Field(default=None, max_length=160)
    gene_symbol_column: str | None = Field(default=None, max_length=160)

    @field_validator("product_name", "target_cell_type", "target_stage", "matrix_location",
                     "source_family_id", "sample_id_column", "capture_id_column", "gene_symbol_column", mode="before")
    @classmethod
    def strip_blank(cls, value):
        return (value.strip() or None) if isinstance(value, str) else value


class IntakeInput(InputBody):
    upload_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    facts: IntakeFacts


class IntakePrepare(InputBody):
    upload_id: str = Field(pattern=r"^[a-f0-9]{32}$")


class Intake:
    def __init__(self, service):
        self.service = service

    def observed(self, state, aid):
        import h5py
        upload = state["_uploads"].get(aid)
        if upload is None:
            raise HTTPException(404, "upload_not_found")
        path = self.service.directory(state["id"]) / "uploads" / (aid + ".h5ad")
        data = checked_bytes(self.service, state, path, upload["sha256"], limit=self.service.settings.upload_limit)
        with h5py.File(io.BytesIO(data), "r") as handle:
            def axis(name):
                group = handle[name]
                index = group.attrs.get("_index", "_index")
                if isinstance(index, bytes):
                    index = index.decode()
                dataset = group.get(index)
                size = dataset.shape[0] if isinstance(dataset, h5py.Dataset) and dataset.ndim == 1 else None
                # Names only, never row identifiers, gene values or expression.
                columns = [key for key in group if key != index and len(key) <= 160][:256]
                return size, columns
            n_obs, obs_columns = axis("obs")
            n_var, var_columns = axis("var")
        return {"n_observations": n_obs, "n_genes": n_var, "matrix_locations": upload["locations"],
                "obs_columns": obs_columns, "var_columns": var_columns}

    def signature(self, state, aid):
        declaration = state["_asset_declarations"].get(aid) or state["_qc_declarations"].get(aid)
        return json.dumps([declaration, state["_uploads"][aid].get("source_family_id")], sort_keys=True, allow_nan=False)

    def current_facts(self, state, aid):
        record = state.get("_intakes", {}).get(aid)
        values = dict(record["facts"]) if record else IntakeFacts().model_dump()
        if not record or record["signature"] != self.signature(state, aid):
            declaration = state["_asset_declarations"].get(aid) or state["_qc_declarations"].get(aid) or {}
            values.update(assay=declaration.get("assay") if declaration.get("assay") in
                          {"scRNA-seq", "snRNA-seq"} else "unknown",
                          matrix_location=declaration.get("matrix_location"),
                          count_semantics=("raw_counts" if declaration.get("matrix_semantics") == "raw_counts"
                                           else "not_raw_counts" if declaration else "unknown"),
                          source_family_id=state["_uploads"][aid].get("source_family_id"))
            for key in ("sample_id_column", "capture_id_column", "gene_symbol_column"):
                values[key] = (declaration.get("metadata") or {}).get(key)
        return IntakeFacts.model_validate(values)

    def missing_fields(self, facts):
        return [key for key in ("product_name", "product_family", "target_cell_type", "target_stage",
                "sampling_context", "independent_cultures", "assay", "matrix_location",
                "count_semantics", "source_family_id") if getattr(facts, key) in (None, "unknown")]

    def cell_state_reasons(self, state, aid):
        record = state.get("_intakes", {}).get(aid)
        if record and record["facts"]["product_family"] != "hpsc_mda":
            return ["supported_product_family_required"]
        return []

    def validate(self, state, body):
        observed = self.observed(state, body.upload_id)
        facts = body.facts
        if facts.matrix_location is not None and facts.matrix_location not in observed["matrix_locations"]:
            raise ValueError("matrix_not_registered")
        for key, axis in (("sample_id_column", "obs"), ("capture_id_column", "obs"), ("gene_symbol_column", "var")):
            column = getattr(facts, key)
            if column is not None and column not in observed[axis + "_columns"]:
                raise ValueError("metadata_column_not_registered")

    def commit(self, state, body):
        self.validate(state, body)
        aid, facts = body.upload_id, body.facts
        before = deepcopy(state["_asset_declarations"].get(aid) or state["_qc_declarations"].get(aid))
        if facts.assay != "unknown" and facts.count_semantics == "raw_counts" and facts.matrix_location:
            metadata = dict((before or {}).get("metadata") or {})
            for key in ("sample_id_column", "capture_id_column", "gene_symbol_column"):
                value = getattr(facts, key)
                if value is None:
                    metadata.pop(key, None)
                else:
                    metadata[key] = value
            declaration = AssetDeclaration(upload_id=aid, assay=facts.assay, matrix_location=facts.matrix_location,
                matrix_semantics="raw_counts", input_level="count_ready", metadata=metadata)
            self.service.inputs.declare_asset(state, declaration)
            state["_qc_declarations"][aid] = declaration.model_dump(exclude={"upload_id"})
        else:
            state["_asset_declarations"].pop(aid, None)
            state["_qc_declarations"].pop(aid, None)
        after = state["_asset_declarations"].get(aid) or state["_qc_declarations"].get(aid)
        keys = ("assay", "matrix_location", "matrix_semantics", "input_level", "metadata")
        if {k: (before or {}).get(k) for k in keys} != {k: (after or {}).get(k) for k in keys}:
            state["_uploads"][aid]["declaration_start"] += 1
        state["_uploads"][aid]["source_family_id"] = facts.source_family_id
        for upload in state["uploads"]:
            if upload["id"] == aid:
                if facts.source_family_id:
                    upload["source_family_id"] = facts.source_family_id
                else:
                    upload.pop("source_family_id", None)
        records = state.setdefault("_intakes", {})
        if aid in records:
            state.setdefault("_intake_history", []).append(deepcopy(records[aid]))
        records[aid] = {"upload_id": aid, "facts": facts.model_dump(mode="json"),
                       "signature": self.signature(state, aid), "input_revision": state["_input_revision"] + 1}

    def public(self, state, aid):
        observed = self.observed(state, aid)
        record = state.get("_intakes", {}).get(aid)
        status = ("confirmed" if record["signature"] == self.signature(state, aid) else "stale") if record else "draft"
        facts = self.current_facts(state, aid)
        missing = self.missing_fields(facts)
        next_tool, qc_state, blockers = None, ("not_run" if status == "confirmed" else "needs_confirmation"), []
        if status == "confirmed" and facts.assay != "unknown" and facts.count_semantics == "raw_counts" and facts.matrix_location:
            try:
                self.service.qc_asset(state, aid, register=False)
                qc_state = "available"
            except (ValueError, OSError, KeyError) as exc:
                if str(exc) in {"completed_qc_required", "qc_declaration_retracted"}:
                    next_tool = "P0-01"
                else:
                    qc_state = "unavailable"
                    blockers.append("qc_evidence_unavailable")
            if qc_state == "available":
                blockers.extend(self.cell_state_reasons(state, aid))
                if not facts.source_family_id:
                    blockers.append("source_family_id_required")
                blockers.extend(self.service.cell_state_config_reasons())
                if not blockers:
                    next_tool = "P0-02"
                    if any(item.get("tool_id") == "P0-02" and item.get("state") == "succeeded" for item in state["_tool_runs"]):
                        next_tool = None
                        blockers.append("cell_state_history_review_required")
        if state["input_review_required"]:
            next_tool = None
        questions = [
            ("数据是否可分析？", qc_state),
            ("细胞组成与目标身份是否有参考支持？", "next_stage" if next_tool == "P0-02" else "needs_evidence"),
            ("目标区域特征是否符合产品定义？", "needs_product_definition"),
            ("发育阶段是否符合预期？", "needs_product_definition"),
            ("是否存在非目标、未知或稀有群体？", "needs_product_definition"),
            ("增殖与应激反应证据如何？", "needs_method_inputs"),
        ]
        return {"upload_id": aid, "observed": observed, "facts": facts.model_dump(mode="json"),
                "state": status, "missing_fields": missing, "next_tool": next_tool, "blockers": blockers,
                "qc_state": qc_state, "measurement_spec_ref": self.service.settings.cell_state_measurement_spec_ref if next_tool == "P0-02" else None,
                "roadmap": [{"question": question, "state": stage} for question, stage in questions]}

    def prepare(self, state, aid):
        self.service.controls.require_ready(state)
        current = self.public(state, aid)
        if current["state"] != "confirmed":
            raise HTTPException(409, "intake_confirmation_required")
        if current["next_tool"] == "P0-01":
            self.service.prepare(state, aid, current["facts"]["matrix_location"])
        elif current["next_tool"] == "P0-02":
            state["_input_selections"]["P0-02"] = Selection(tool_id="P0-02", mode_id=None,
                asset_ids=[aid], object_inputs=[], measurement_spec_ref=self.service.settings.cell_state_measurement_spec_ref).model_dump(mode="json")
            self.service.prepare_analysis(state, "P0-02")
        else:
            raise HTTPException(409, "intake_next_stage_needs_input")
