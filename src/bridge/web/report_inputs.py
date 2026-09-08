"""Prepare the explicitly unmeasured, candidate-only internal report flow."""
from __future__ import annotations

from copy import deepcopy
from typing import Literal

from fastapi import HTTPException

from bridge.tool_packages.p0_08_evidence_sufficiency.models import DomainGateInput, P0DomainId
from .inputs import Selection
from .scientific_inputs import DraftIdentity, encoded


DOMAIN_LABELS = {"target_identity": "目标身份", "regional_fidelity": "区域一致性",
    "developmental_compatibility": "发育阶段兼容性", "off_target_control": "非目标细胞控制",
    "proliferation_stress_response": "增殖与应激"}


class ReportPreparation(DraftIdentity):
    tool_id: Literal["P0-08", "P0-09", "P0-10"] = "P0-08"


class ReportInputs:
    def __init__(self, service):
        self.service = service

    def _draft(self, state, body):
        draft = next((row for row in state.get("_scientific_drafts", []) if row["id"] == body.draft_id), None)
        if draft is None or draft["digest"] != body.draft_digest or draft["status"] != "confirmed":
            raise HTTPException(409, "confirmed_scientific_draft_required")
        # Confirmed retry validates dependencies and objects but never registers new objects.
        self.service.scientific_inputs.confirm(state, body.draft_id, body.draft_digest)
        if any(row["tool_id"] in {"P0-03", "P0-04", "P0-05", "P0-06"}
               and row["state"] in {"succeeded", "partial"} for row in state.get("_tool_runs", [])):
            raise HTTPException(409, "measured_report_binding_required")
        return draft

    def _saved(self, state, draft_id, tool_id):
        record = state.get("_report_inputs", {}).get(draft_id)
        return record if tool_id == "P0-08" or not record else record.get("stages", {}).get(tool_id)

    def _verify_saved(self, state, draft_id, saved):
        self._draft(state, DraftIdentity(draft_id=draft_id, draft_digest=saved["draft_digest"]))
        tool_id = saved["selection"]["tool_id"]
        chain = [self._saved(state, draft_id, prior) for prior in ("P0-08", "P0-09") if prior < tool_id]
        checked = set()
        for record in [*chain, saved]:
            if record is None:
                raise ValueError("report_upstream_stage_missing")
            for row in record["selection"]["object_inputs"]:
                if row["input_id"] not in checked:
                    self.service.inputs.verify(state, state["_input_objects"][row["input_id"]])
                    checked.add(row["input_id"])

    def selected_blocker(self, state, tool_id):
        if tool_id not in {"P0-08", "P0-09", "P0-10"}:
            return None
        selection = state.get("_input_selections", {}).get(tool_id, {})
        selected = {row["input_id"] for row in selection.get("object_inputs", [])}
        for identifier in state.get("_report_inputs", {}):
            record = self._saved(state, identifier, tool_id)
            if not record:
                continue
            owned = {row["input_id"] for row in record["selection"]["object_inputs"]
                if state["_input_objects"].get(row["input_id"], {}).get("source") != "package_resource"}
            if not selected.intersection(owned):
                continue
            if selection != record["selection"]:
                return "report_draft_selection_mismatch"
            try:
                self._verify_saved(state, identifier, record)
            except (HTTPException, ValueError, OSError, KeyError):
                return "report_draft_invalid_or_stale"
        return None

    def _result(self, state, draft, tool_id, schema):
        saved = self._saved(state, draft["id"], tool_id)
        if not saved:
            return None
        self._verify_saved(state, draft["id"], saved)
        receipts = {row["file"] for row in state.get("_tool_runs", [])
            if row.get("plan_id") in saved["plan_ids"] and row["tool_id"] == tool_id
            and row["state"] in {"succeeded", "partial"}}
        matches = [(identifier, record) for identifier, record in state["_input_objects"].items()
            if record["source"] == "tool_output" and record.get("producer_tool_id") == tool_id
            and record.get("receipt_file") in receipts and record["schema_ref"] == schema]
        if not matches:
            return None
        identifier, record = matches[-1]
        return identifier, self.service.inputs.verify(state, record)

    def _prepare_downstream(self, state, body):
        from .app import now
        from bridge.tool_packages._configurable_contracts import ProductCase, ProductDefinitionCard
        from bridge.tool_packages.p0_08_evidence_sufficiency.models import EvidenceSufficiencyRunResultV2
        from bridge.tool_packages.p0_09_evidence_compiler.candidate_policy import build_missingness_policy
        if body.tool_id == "P0-10":
            return self._prepare_verification(state, body)
        draft = self._draft(state, body)
        try:
            upstream = self._result(state, draft, "P0-08", "bridge://schemas/evidence-sufficiency-run-result/v0.2")
            if upstream is None:
                raise ValueError("canonical_missingness_result_required")
            trial = deepcopy(state)
            saved = self._saved(trial, draft["id"], body.tool_id)
            if saved is None:
                case = self.service.inputs.verify(trial, trial["_input_objects"][draft["object_ids"]["product_case"]])
                definition = self.service.inputs.verify(trial, trial["_input_objects"][draft["object_ids"]["product_definition_card"]])
                objects = build_missingness_policy(ProductCase.model_validate(case),
                    ProductDefinitionCard.model_validate(definition),
                    EvidenceSufficiencyRunResultV2.model_validate(upstream[1]), created_at=now())
                choices = [{"role": "evidence_sufficiency_run_result", "input_id": upstream[0]}]
                schemas = {"compilation_bundle": "evidence-compilation-bundle",
                    "evidence_family_registry": "evidence-family-registry", "claim_registry": "claim-registry",
                    "reconciliation_spec_registry": "reconciliation-spec-registry"}
                for role, model in objects.items():
                    identifier = self.service.inputs.add_object(trial, tool_id=body.tool_id, mode_id="case_initial_v2",
                        role=role, schema_ref="bridge://schemas/" + schemas[role] + "/v0.1",
                        object_version="0.1.0", data=encoded(model.model_dump(mode="json")))
                    choices.append({"role": role, "input_id": identifier})
                selection = Selection(tool_id=body.tool_id, mode_id="case_initial_v2", asset_ids=[],
                    object_inputs=choices, measurement_spec_ref=None).model_dump(mode="json")
                saved = {"draft_digest": draft["digest"], "selection": selection, "plan_ids": []}
                trial["_report_inputs"][draft["id"]].setdefault("stages", {})[body.tool_id] = saved
            self._verify_saved(trial, draft["id"], saved)
        except (ValueError, OSError, KeyError):
            raise HTTPException(409, "canonical_missingness_result_or_candidate_policy_invalid") from None
        self._propose_downstream(state, trial, saved, body.tool_id)

    def _propose_downstream(self, state, trial, saved, tool_id):
        trial["_input_selections"][tool_id] = saved["selection"]
        self.service.controls.fence(trial)
        trial["_input_revision"] += 1
        self.service.prepare_analysis(trial, tool_id)
        if trial.get("plan") and trial["plan"]["status"] == "proposed":
            trial["plan"]["summary"] = {
                "P0-09": "P0-09 整理当前证据：使用候选、未审阅规则，将本样本五个未评估域登记为缺失要求。不生成测量，不建立独立重复，不给产品打分或判定合格。请单独确认。",
                "P0-10": "P0-10 核验内部报告：报告仅说明当前缺失证据，使用现有发布规则逐条核对。规则尚未支持此类表述，预计会保留发布受阻结果；不会公开导出。请单独确认。",
            }[tool_id]
            saved["plan_ids"].append(trial["plan"]["id"])
        self.service.save(trial)
        state.update(trial)

    def _prepare_verification(self, state, body):
        from .app import now
        from bridge.tool_packages.p0_10_claim_verifier.models import ClaimBlock, ReportDraft, report_content_hash
        from bridge.tool_packages.p0_10_claim_verifier.verifier import load_release_contract
        draft = self._draft(state, body)
        try:
            graph = self._result(state, draft, "P0-09", "bridge://schemas/case-evidence-graph-manifest/v0.1")
            records = self._result(state, draft, "P0-09", "bridge://schemas/evidence-record-set/v0.1")
            requirements = self._result(state, draft, "P0-09", "bridge://schemas/evidence-requirement-set/v0.1")
            if graph is None or records is None or requirements is None:
                raise ValueError("canonical_candidate_graph_required")
            if (records[1]["records"] or len(requirements[1]["requirements"]) != 5
                    or any(row["state"] != "open" for row in requirements[1]["requirements"])
                    or any(row[1]["graph_id"] != graph[1]["graph_id"] or row[1]["graph_version"] != graph[1]["graph_version"]
                           for row in (records, requirements))):
                raise ValueError("unmeasured_candidate_graph_required")
            trial = deepcopy(state)
            saved = self._saved(trial, draft["id"], "P0-10")
            if saved is None:
                policy_saved = self._saved(trial, draft["id"], "P0-09")
                claim_id = next(row["input_id"] for row in policy_saved["selection"]["object_inputs"] if row["role"] == "claim_registry")
                claims = self.service.inputs.verify(trial, trial["_input_objects"][claim_id])["claims"]
                if {row["claim_ref"]["object_id"] + "@" + row["claim_ref"]["object_version"] for row in requirements[1]["requirements"]} != {
                        row["claim_id"] + "@" + row["version"] for row in claims}:
                    raise ValueError("candidate_claim_requirements_mismatch")
                case = self.service.inputs.verify(trial, trial["_input_objects"][draft["object_ids"]["product_case"]])
                release = load_release_contract()
                report = {
                    "object_version": "0.1.0", "report_id": "report:web-" + draft["id"],
                    "report_version": "0.1.0", "audience": "internal_research", "language": "zh",
                    "evidence_record_set_ref": records[1]["record_set_id"] + "@" + records[1]["record_set_version"],
                    "claim_policy_ref": release.claim_policy.ref, "statement_registry_ref": release.statement_registry.ref,
                    "claim_blocks": [{
                        "claim_id": "claim-block:web-" + draft["id"] + ":" + claim["domain_id"], "claim_version": "0.1.0",
                        "claim_ref": claim["claim_id"] + "@" + claim["version"],
                        "product_case_ref": case["product_case_id"] + "@" + case["case_version"],
                        "claim_type": "availability_claim", "language": "zh",
                        "text": DOMAIN_LABELS[claim["domain_id"]] + "：当前未提供正式测量，尚未评估。缺失不等于阴性。",
                        "authoring_channel": "deterministic_renderer",
                    } for claim in claims],
                    "renderer_id": "BRIDGE-WEB-MISSINGNESS-DRAFT", "renderer_version": "0.1.0",
                    "authoring_channel": "deterministic_renderer", "created_at": now().replace("+00:00", "Z"),
                }
                boundary = next(row for row in release.statement_registry.statements if row.ref == "statement:safety-boundary@0.1.0")
                report["claim_blocks"].append({
                    "claim_id": "claim-block:web-" + draft["id"] + ":boundary", "claim_version": "0.1.0",
                    "claim_ref": report["claim_blocks"][0]["claim_ref"],
                    "product_case_ref": report["claim_blocks"][0]["product_case_ref"],
                    "claim_type": "policy_or_boundary_statement", "language": "zh",
                    "text": boundary.texts["zh"], "statement_refs": [boundary.ref],
                    "authoring_channel": "deterministic_renderer",
                })
                report["claim_blocks"] = [ClaimBlock.model_validate(row).model_dump(mode="json") for row in report["claim_blocks"]]
                report["content_hash"] = report_content_hash(report)
                report = ReportDraft.model_validate(report)
                identifier = self.service.inputs.add_object(trial, tool_id="P0-10", mode_id="default",
                    role="report_draft", schema_ref="bridge://schemas/report-draft/v0.1",
                    object_version="0.1.0", data=encoded(report.model_dump(mode="json")))
                self.service.inputs.package_options(trial)
                choices = [{"role": "report_draft", "input_id": identifier},
                           {"role": "evidence_graph_manifest", "input_id": graph[0]}]
                for role in ("claim_policy_spec", "statement_registry"):
                    resource_id = next(key for key, row in trial["_input_objects"].items()
                        if row["source"] == "package_resource" and row["label"] == role)
                    choices.append({"role": role, "input_id": resource_id})
                saved = {"draft_digest": draft["digest"], "plan_ids": [],
                    "selection": Selection(tool_id="P0-10", mode_id="default", asset_ids=[],
                        object_inputs=choices, measurement_spec_ref=None).model_dump(mode="json")}
                trial["_report_inputs"][draft["id"]].setdefault("stages", {})["P0-10"] = saved
            self._verify_saved(trial, draft["id"], saved)
        except (ValueError, OSError, KeyError, StopIteration):
            raise HTTPException(409, "canonical_candidate_graph_or_report_invalid") from None
        self._propose_downstream(state, trial, saved, "P0-10")

    def public_report(self, state, draft):
        saved = self._saved(state, draft["id"], "P0-10")
        if not saved or draft["status"] != "confirmed":
            return None
        try:
            self._verify_saved(state, draft["id"], saved)
            identifier = next(row["input_id"] for row in saved["selection"]["object_inputs"] if row["role"] == "report_draft")
            report = self.service.inputs.verify(state, state["_input_objects"][identifier])
            verification = self._result(state, draft, "P0-10", "bridge://schemas/claim-verification-result/v0.1")
            if verification and (verification[1]["report_draft_ref"] != report["report_id"] + "@" + report["report_version"]
                    or verification[1]["report_content_hash"] != report["content_hash"]):
                raise ValueError("report_verification_binding_mismatch")
            return {
                "audience": report["audience"], "policy_state": "candidate_unreviewed",
                "sections": [{"domain_id": row["claim_id"].rsplit(":", 1)[-1],
                    "title": DOMAIN_LABELS[row["claim_id"].rsplit(":", 1)[-1]], "text": row["text"],
                    "evidence_state": "not_assessed"} for row in report["claim_blocks"] if row["claim_type"] == "availability_claim"],
                "boundaries": [row["text"] for row in report["claim_blocks"] if row["claim_type"] == "policy_or_boundary_statement"],
                "verification": None if verification is None else {
                    "release_state": verification[1]["release_state"],
                    "public_export_eligibility": verification[1]["public_export_eligibility"],
                    "reason_codes": sorted({row["reason_code"] for row in verification[1]["check_records"]})},
                "next_actions": ["完成候选来源与产品角色的生物学审阅，再准备正式域测量。",
                    "确认样本、制备与独立分组关系；不能用细胞数代替独立重复。",
                    "缺失性报告表述需通过声明规则评审；当前不可公开导出。"],
            }
        except (HTTPException, ValueError, OSError, KeyError, StopIteration):
            return None


    def prepare(self, state, body):
        if body.tool_id != "P0-08":
            return self._prepare_downstream(state, body)
        from .app import now
        draft = self._draft(state, body)
        trial = deepcopy(state)
        saved = trial.setdefault("_report_inputs", {}).get(draft["id"])
        if saved is None:
            case_id = draft["object_ids"]["product_case"]
            case = self.service.inputs.verify(trial, trial["_input_objects"][case_id])
            self.service.inputs.package_options(trial)
            gate_id = next(identifier for identifier, record in trial["_input_objects"].items()
                           if record["source"] == "package_resource" and record["label"] == "gate_rule_spec")
            self.service.inputs.verify(trial, trial["_input_objects"][gate_id])
            provenance = [item["object_id"] for item in case["provenance_refs"]]
            choices = [{"role": "product_case", "input_id": case_id}, {"role": "gate_rule_spec", "input_id": gate_id}]
            domains = [DomainGateInput(domain_gate_input_id="domain-gate-input:" + draft["id"] + ":" + domain.value,
                object_version="0.1.0", created_at=now(), domain_id=domain,
                product_case={"object_id": case["product_case_id"], "object_version": case["case_version"], "provenance_refs": provenance},
                product_definition={**case["product_definition_ref"], "provenance_refs": provenance},
                provenance_refs=provenance) for domain in P0DomainId]
            schema = "bridge://schemas/domain-gate-input/v0.1"
            for domain in domains:
                self.service.inputs.validate_object(domain.model_dump(mode="json"), schema, "0.1.0")
            for domain in domains:
                identifier = self.service.inputs.add_object(trial, tool_id="P0-08", mode_id="default",
                    role="domain_gate_input", schema_ref=schema, object_version="0.1.0",
                    data=encoded(domain.model_dump(mode="json")))
                choices.append({"role": "domain_gate_input", "input_id": identifier})
            selection = Selection(tool_id="P0-08", mode_id="default", asset_ids=[],
                object_inputs=choices, measurement_spec_ref=None).model_dump(mode="json")
            saved = {"draft_digest": draft["digest"], "selection": selection, "gate_id": gate_id, "plan_ids": []}
            trial["_report_inputs"][draft["id"]] = saved
        trial["_input_selections"]["P0-08"] = saved["selection"]
        self.service.controls.fence(trial)
        trial["_input_revision"] += 1
        self.service.prepare_analysis(trial, "P0-08")
        if trial.get("plan") and trial["plan"]["status"] == "proposed" and trial["plan"]["steps"][0]["tool_id"] == "P0-08":
            trial["plan"]["summary"] = ("P0-08 未评估与缺失证据检查：五个科学域均未提供正式测量、匹配的数据视图或验证记录。"
                "本次仅用包内规则登记缺项，不将已有 QC 或旧版细胞状态结果冒充这些证据，不判定产品合格。请单独确认。")
            saved["plan_ids"].append(trial["plan"]["id"])
        self.service.save(trial)
        state.update(trial)

    def stages(self, state, draft):
        result = deepcopy(draft["stages"])
        result.append({"tool_id": "P0-07", "state": "blocked", "reason_codes": ["comparison_inputs_not_bound"]})
        previous = draft["status"] == "confirmed"
        for tool_id, schema, ready_reason, blocked_reason in (
            ("P0-08", "evidence-sufficiency-run-result/v0.2", "missingness_only", "scientific_draft_confirmation_required"),
            ("P0-09", "case-evidence-graph-manifest/v0.1", "candidate_missingness_policy", "canonical_missingness_result_required"),
            ("P0-10", "claim-verification-result/v0.1", "internal_draft_only", "compiled_report_required"),
        ):
            status, reasons = ("ready", [ready_reason]) if previous else ("blocked", [blocked_reason])
            try:
                available = previous and self._result(state, draft, tool_id, "bridge://schemas/" + schema) is not None
            except (HTTPException, ValueError, OSError, KeyError):
                available, status, reasons = False, "blocked", ["result_evidence_invalid"]
            if available:
                status = "available"
            previous = bool(available)
            result.append({"tool_id": tool_id, "state": status, "reason_codes": reasons})
        result.extend([
            {"tool_id": "P0-11", "state": "blocked", "reason_codes": ["verified_report_and_export_approval_required"]},
        ])
        return result
