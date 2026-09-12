"""Conditional, confirmation-bound access to existing comparison/graft plans.

This helper does not run tools, curate products, grant source licenses, author
scientific settings, or rewrite pre-transplant evidence. Service owns locking,
routes and ordinary plan approval/execution.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

from fastapi import HTTPException
from pydantic import Field, StrictInt

from bridge.tool_packages.p0_07_product_comparison_stability.executor import (
    _confounding, _field_mismatches,
)
from bridge.tool_packages.p0_07_product_comparison_stability.models import (
    ComparisonCaseManifest, ComparisonStabilitySpec, ProductEvidenceBundle,
)
from .inputs import InputBody, Selection

TOOLS = {"P0-07", "P0-12"}
SOURCE_KINDS = {"user_upload", "tool_output", "system_resource"}
LABELS = {
    "comparable": "可作描述性比较", "background_only": "仅作背景资料", "excluded": "不可纳入",
    "comparison_stability_spec": "冻结的比较规范", "comparison_case_manifest": "明确的比较名单",
    "product_evidence_bundle": "已测量的产品证据", "graft_case": "移植后样本资料",
    "assessment_spec": "移植后评估规范", "evidence_bundle": "移植后实测证据",
    "graft_expression_asset": "移植后表达数据", "graft_expression_analysis_spec": "移植后表达分析规范",
    "graft_reference_panel": "移植后参考面板", "graft_marker_program_collection": "移植后标记程序",
    "comparison_method_spec": "比较方法规范", "comparison_method_input": "比较方法输入",
}
FIELDS = {"product_definition": "产品定义", "target_stage": "目标阶段", "assay": "测定类型",
    "data_view": "数据视图", "timepoint": "时间点", "reference": "参考数据",
    "preprocessing": "预处理", "algorithm": "分析算法", "protocol": "制备流程",
    "lab": "实验室", "batch": "批次", "cell_line": "细胞系"}
REASONS = {
    "frozen_comparison_spec_required": "缺少已冻结的比较规范；候选规范不能授权执行。",
    "measured_comparison_evidence_required": "缺少符合规范的已测量证据；影子、推断或缺失值不能替代。",
    "comparison_directory_empty": "尚未登记可核对的比较名单与产品证据。",
    "comparison_spec_ambiguous": "同一比较规范存在多个登记版本，需明确选择。",
    "comparison_bundle_ambiguous": "同一产品证据引用存在多个登记对象，需明确选择。",
    "graft_bundle_ambiguous": "该移植后样本存在多个证据包，需明确选择。",
    "graft_spec_ambiguous": "移植后评估规范存在多个匹配对象，需明确选择。",
    "graft_inputs_not_provided": "尚未登记匹配的移植后输入；不能运行移植后分析。",
    "matching_preparation_required": "缺少与移植后样本明确匹配的移植前制备资料。",
    "matching_preparation_ambiguous": "移植前制备存在多个版本或案例，尚不能唯一关联。",
    "graft_linkage_evidence_required": "缺少明确的移植前后关联证据。",
    "graft_animal_id_required": "缺少移植动物标识。",
    "graft_post_transplant_timepoint_required": "缺少移植后时间点。",
    "graft_biological_replicate_id_required": "缺少生物学重复标识；不能推断样本独立性。",
    "graft_required_roles_missing": "现有移植后证据缺少规范要求的证据类型。",
    "source_access_unverified": "来源未在当前会话获准访问，不能纳入。",
    "source_receipt_invalidated": "来源回执已被确认修订作废，需重新提供当前有效证据。",
    "source_dependency_cycle": "来源依赖形成循环，不能核对。",
    "source_integrity_failed": "已登记来源的内容、版本或依赖无法核对。",
    "input_review_required": "现有输入仍待用户核对。",
    "product_analysis_context_required": "缺少已登记的产品分析上下文。",
    "comparison_manifest_bundle_set_mismatch": "比较名单与已选择的产品证据不一致。",
    "reference_ood_group_not_rankable": "参考或域外产品只能作背景资料，不能纳入产品比较。",
    "unsupported_conditional_mode": "此入口只接受现有已注册的比较或移植后分析模式。",
}
BACKGROUND = {"frozen_comparison_spec_required", "measured_comparison_evidence_required",
              "comparison_directory_empty", "graft_inputs_not_provided",
              "product_analysis_context_required", "reference_ood_group_not_rankable"}


class ConditionalProposal(InputBody):
    selection: Selection
    expected_revision: StrictInt = Field(ge=0)


class ConditionalDecision(InputBody):
    draft_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    draft_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    expected_revision: StrictInt = Field(ge=0)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False, separators=(",", ":")).encode()).hexdigest()


def _reason_label(reason):
    if reason in REASONS:
        return REASONS[reason]
    if reason.startswith("object_required:"):
        return "缺少" + LABELS.get(reason.split(":", 1)[1], "所需的登记输入") + "。"
    for prefix, template in (
        ("required_field_mismatch_", "要求一致的{}不匹配。"),
        ("contextual_field_mismatch_", "{}存在差异，只能作背景解释。"),
        ("confounding_metadata_missing_", "缺少{}混杂因素元数据。"),
        ("complete_confounding_", "{}与比较组完全混杂，不能归因于产品差异。"),
    ):
        if reason.startswith(prefix):
            return template.format(FIELDS.get(reason[len(prefix):], "必要字段"))
    return "现有输入未满足已注册工具的对应合同；请查看诊断原因。"


class ConditionalInputs:
    def __init__(self, service):
        self.service = service

    def _record(self, state, identifier, visited=None):
        visited = set() if visited is None else visited
        if identifier in visited:
            raise ValueError("source_dependency_cycle")
        visited.add(identifier)
        record = state.get("_input_objects", {}).get(identifier)
        if record is None or record.get("source") not in SOURCE_KINDS:
            raise ValueError("source_access_unverified")
        invalidated = state.get("_invalidated_receipts", {})
        if record.get("receipt_file") in invalidated or any(
            row.get("receipt_file") in invalidated for row in record.get("dependencies", [])
        ):
            raise ValueError("source_receipt_invalidated")
        for dependency in record.get("derivation_inputs", {}):
            self._record(state, dependency, visited.copy())
        try:
            return self.service.inputs.verify(state, record)
        except (ValueError, OSError, KeyError, TypeError):
            raise ValueError("source_integrity_failed") from None

    def _matching_preparation(self, state, case):
        preparation = case.get("originating_preparation_id")
        if not preparation:
            return [], ["matching_preparation_required"]
        found = []
        for identifier, record in state.get("_input_objects", {}).items():
            if record["schema_ref"] not in {"bridge://schemas/product-case/v0.1",
                                            "bridge://schemas/product-evidence-bundle/v0.1"}:
                continue
            try:
                value = self._record(state, identifier)
            except ValueError:
                continue
            product = value.get("product_case", value)
            if product["source_unit_kind"] == "preparation" and product["sample_or_preparation_ref"]["object_id"] == preparation:
                found.append((identifier, (product["product_case_id"], product["case_version"])))
        if not found:
            return [], ["matching_preparation_required"]
        if len({identity for _, identity in found}) != 1:
            return [], ["matching_preparation_ambiguous"]
        return sorted(identifier for identifier, _ in found), []

    def _evaluate(self, state, selection, extra_reasons=()):
        reasons = list(extra_reasons)
        values, support_ids = {}, []
        if selection.tool_id not in TOOLS or (
            selection.tool_id == "P0-12" and selection.mode_id == "not_provided"
        ):
            reasons.append("unsupported_conditional_mode")
        if state.get("input_review_required"):
            reasons.append("input_review_required")
        for choice in selection.object_inputs:
            try:
                values.setdefault(choice.role, []).append(self._record(state, choice.input_id))
            except ValueError as exc:
                reasons.append(str(exc))
        request = None
        try:
            reasons.extend(self.service.inputs.selection_reasons(state, selection, verify=False))
            if not reasons:
                _, request = self.service.inputs.construct(state, selection)
                reasons.extend(self.service.registry.check_eligibility(request).reason_codes)
        except (ValueError, OSError, KeyError):
            reasons.append("source_integrity_failed")

        if selection.tool_id == "P0-07":
            specs = values.get("comparison_stability_spec", [])
            manifests = values.get("comparison_case_manifest", [])
            bundles = values.get("product_evidence_bundle", [])
            if len(specs) == 1 and specs[0]["status"] != "frozen":
                reasons.append("frozen_comparison_spec_required")
            if bundles and any(metric["evidence_state"] not in {"measured", "negative"}
                               or metric["raw_value"] is None or metric["denominator_value"] is None
                               for bundle in bundles for metric in bundle["metrics"]):
                reasons.append("measured_comparison_evidence_required")
            # These are the same metadata predicates used by the registered
            # executor; no metrics, method execution or report generation runs.
            if len(specs) == len(manifests) == 1 and request is not None and not reasons:
                spec = ComparisonStabilitySpec.model_validate(specs[0])
                manifest = ComparisonCaseManifest.model_validate(manifests[0])
                parsed = [ProductEvidenceBundle.model_validate(bundle) for bundle in bundles]
                by_ref = {bundle.ref.ref: bundle for bundle in parsed}
                grouped = {group.group_id: [by_ref[ref.ref] for ref in group.bundle_refs]
                           for group in manifest.groups}
                required, contextual = _field_mismatches(spec, grouped)
                missing, confounded = _confounding(spec, manifest.groups, grouped)
                reasons.extend("required_field_mismatch_" + item.value for item in required)
                reasons.extend("contextual_field_mismatch_" + item.value for item in contextual)
                reasons.extend("confounding_metadata_missing_" + item.value for item in missing)
                reasons.extend("complete_confounding_" + item.value for item in confounded)
                if any(group.role.value == "reference_ood" for group in manifest.groups):
                    reasons.append("reference_ood_group_not_rankable")
        elif selection.tool_id == "P0-12":
            cases = values.get("graft_case", [])
            if len(cases) == 1:
                case = cases[0]
                support_ids, matching = self._matching_preparation(state, case)
                reasons.extend(matching)
                if not case.get("linkage_evidence_refs"):
                    reasons.append("graft_linkage_evidence_required")
                for field in ("animal_id", "post_transplant_timepoint", "biological_replicate_id"):
                    if not case.get(field):
                        reasons.append("graft_" + field + "_required")
                if selection.mode_id == "graft_assessment":
                    specs, bundles = values.get("assessment_spec", []), values.get("evidence_bundle", [])
                    if len(specs) == len(bundles) == 1:
                        provided = {row["role_id"] for row in bundles[0]["records"]}
                        if any(row["required"] and row["role_id"] not in provided for row in specs[0]["role_rules"]):
                            reasons.append("graft_required_roles_missing")
        reasons = sorted(set(reasons))
        background = all(reason in BACKGROUND or reason.startswith(
            ("object_required:", "contextual_field_mismatch_")) for reason in reasons)
        category = "comparable" if not reasons else "background_only" if background else "excluded"
        return {
            "category": category,
            "category_label": "可进入移植后分析" if selection.tool_id == "P0-12" and not reasons else LABELS[category],
            "execution_available": not reasons,
            "reasons": [_reason_label(reason) for reason in reasons],
            "diagnostics": {"tool_id": selection.tool_id, "mode_id": selection.mode_id,
                            "reason_codes": reasons, "selection": selection.model_dump(mode="json"),
                            "support_input_ids": support_ids},
        }

    def _pool(self, state, schema):
        rows = []
        for identifier, record in sorted(state.get("_input_objects", {}).items()):
            if record["schema_ref"] != schema:
                continue
            try:
                rows.append((identifier, self._record(state, identifier), None))
            except ValueError as exc:
                rows.append((identifier, None, str(exc)))
        return rows

    @staticmethod
    def _ref(value, prefix):
        return {"object_id": value[prefix + "_id"], "object_version": value[prefix + "_version"]}

    def _comparison_directory(self, state):
        manifests = self._pool(state, "bridge://schemas/comparison-case-manifest/v0.1")
        specs = self._pool(state, "bridge://schemas/comparison-stability-spec/v0.1")
        bundles = self._pool(state, "bridge://schemas/product-evidence-bundle/v0.1")
        entries, included = [], set()
        for index, (identifier, manifest, error) in enumerate(manifests, 1):
            choices = [{"role": "comparison_case_manifest", "input_id": identifier}]
            reasons = [error] if error else []
            if manifest:
                matches = [(key, value) for key, value, _ in specs if value and
                           self._ref(value, "spec") == manifest["spec_ref"]]
                if len(matches) == 1:
                    choices.append({"role": "comparison_stability_spec", "input_id": matches[0][0]})
                elif len(matches) > 1:
                    reasons.append("comparison_spec_ambiguous")
                for group in manifest["groups"]:
                    for ref in group["bundle_refs"]:
                        matching = [(key, value) for key, value, _ in bundles if value and
                                    self._ref(value, "bundle") == ref]
                        if len(matching) == 1:
                            choices.append({"role": "product_evidence_bundle", "input_id": matching[0][0]})
                            included.add(matching[0][0])
                        elif len(matching) > 1:
                            reasons.append("comparison_bundle_ambiguous")
            selection = Selection(tool_id="P0-07", mode_id="legacy_comparison",
                                  asset_ids=[], object_inputs=choices, measurement_spec_ref=None)
            saved = state.get("_input_selections", {}).get("P0-07")
            if saved and any(row["role"] == "comparison_case_manifest" and row["input_id"] == identifier
                             for row in saved["object_inputs"]):
                selection = Selection.model_validate(saved)
            entries.append({"id": identifier, "label": f"已登记比较方案 {index}",
                            **self._evaluate(state, selection, reasons)})
        for index, (identifier, _, error) in enumerate(bundles, 1):
            if identifier in included:
                continue
            selection = Selection(tool_id="P0-07", mode_id="legacy_comparison", asset_ids=[],
                object_inputs=[{"role": "product_evidence_bundle", "input_id": identifier}],
                measurement_spec_ref=None)
            entries.append({"id": identifier, "label": f"未归入比较名单的产品资料 {index}",
                            **self._evaluate(state, selection, [error] if error else [])})
        return self._directory_view("产品比较", entries, "comparison_directory_empty")

    def _graft_directory(self, state):
        cases = self._pool(state, "bridge://schemas/graft-case/v0.1")
        specs = self._pool(state, "bridge://schemas/graft-assessment-spec/v0.1")
        bundles = self._pool(state, "bridge://schemas/graft-evidence-bundle/v0.1")
        entries = []
        for index, (identifier, case, error) in enumerate(cases, 1):
            choices = [{"role": "graft_case", "input_id": identifier}]
            reasons = [error] if error else []
            if case:
                matching = [(key, value) for key, value, _ in bundles
                            if value and value["graft_case_ref"] == case["graft_case_id"]]
                if len(matching) == 1:
                    key, bundle = matching[0]
                    choices.append({"role": "evidence_bundle", "input_id": key})
                    selected = [(key, value) for key, value, _ in specs
                                if value and value["assessment_spec_id"] == bundle["assessment_spec_ref"]]
                    if len(selected) == 1:
                        choices.append({"role": "assessment_spec", "input_id": selected[0][0]})
                    elif len(selected) > 1:
                        reasons.append("graft_spec_ambiguous")
                elif len(matching) > 1:
                    reasons.append("graft_bundle_ambiguous")
            selection = Selection(tool_id="P0-12", mode_id="graft_assessment", asset_ids=[],
                                  object_inputs=choices, measurement_spec_ref=None)
            saved = state.get("_input_selections", {}).get("P0-12")
            if saved and any(row["role"] == "graft_case" and row["input_id"] == identifier
                             for row in saved["object_inputs"]):
                selection = Selection.model_validate(saved)
            entries.append({"id": identifier, "label": f"已登记移植后样本 {index}",
                            **self._evaluate(state, selection, reasons)})
        return self._directory_view("移植后证据", entries, "graft_inputs_not_provided")

    @staticmethod
    def _directory_view(label, entries, missing_reason):
        available = any(row["execution_available"] for row in entries)
        return {"label": label, "execution_available": available, "entries": entries,
                "reasons": [] if entries else [_reason_label(missing_reason)],
                "diagnostics": {"reason_codes": [] if entries else [missing_reason]}}

    def _binding(self, state, selection, evaluation):
        identifiers = {row.input_id for row in selection.object_inputs}
        identifiers.update(evaluation["diagnostics"]["support_input_ids"])
        pending = list(identifiers)
        while pending:
            identifier = pending.pop()
            self._record(state, identifier)
            for dependency in state["_input_objects"][identifier].get("derivation_inputs", {}):
                if dependency not in identifiers:
                    identifiers.add(dependency)
                    pending.append(dependency)
        return {
            "objects": {key: deepcopy(state["_input_objects"][key]) for key in sorted(identifiers)},
            "context_assets": deepcopy(state.get("_bundle", {}).get("assets")
                                       or list(state.get("_asset_declarations", {}).values())),
            "invalidated_receipts": deepcopy(state.get("_invalidated_receipts", {})),
            "tool_spec": self.service.registry.describe(selection.tool_id).model_dump(mode="json"),
            "input_contract": self.service.registry.describe_input(selection.tool_id).model_dump(mode="json"),
        }

    def _ready(self, state, expected_revision):
        self.service.controls.require_ready(state)
        self.service.busy(state)
        if type(expected_revision) is not int or expected_revision != state.get("_input_revision", 0):
            raise HTTPException(409, "conditional_revision_mismatch")

    def propose(self, state, selection: Selection, expected_revision: int):
        from .app import uid
        self._ready(state, expected_revision)
        selection = Selection.model_validate(selection.model_dump(mode="json"))
        if selection.tool_id not in TOOLS:
            raise HTTPException(422, "unsupported_conditional_tool")
        if len(state.get("_conditional_history", [])) >= 128:
            raise HTTPException(409, "conditional_history_limit")
        evaluation = self._evaluate(state, selection)
        try:
            binding = self._binding(state, selection, evaluation)
        except (ValueError, OSError, KeyError):
            raise HTTPException(409, "conditional_source_invalid") from None
        event = {"event": "proposed", "id": uid(), "session_id": state["id"],
                 "input_revision": expected_revision, "selection": selection.model_dump(mode="json"),
                 "binding": binding, "evaluation": evaluation}
        self._append_event(state, event)
        self.service.save(state)
        return self._public_proposal(state, event)

    @staticmethod
    def _check_history(state):
        previous = None
        for event in state.get("_conditional_history", []):
            if (event.get("previous_digest") != previous
                    or event.get("digest") != _digest({key: value for key, value in event.items()
                                                       if key != "digest"})):
                raise HTTPException(409, "conditional_history_integrity_failed")
            previous = event["digest"]
        return previous

    def _append_event(self, state, event):
        event["previous_digest"] = self._check_history(state)
        event["digest"] = _digest(event)
        state.setdefault("_conditional_history", []).append(event)

    def _proposal(self, state, draft_id, draft_digest):
        self._check_history(state)
        event = next((row for row in state.get("_conditional_history", [])
                      if row["event"] == "proposed" and row["id"] == draft_id), None)
        if (event is None or event["session_id"] != state["id"] or event["digest"] != draft_digest or
                _digest({key: value for key, value in event.items() if key != "digest"}) != draft_digest):
            raise HTTPException(409, "conditional_selection_mismatch")
        actions = [row for row in state["_conditional_history"] if row.get("draft_id") == draft_id]
        return event, actions[-1] if actions else None

    def _recheck(self, state, event, revision):
        if state["_input_revision"] != revision:
            raise HTTPException(409, "conditional_selection_stale")
        selection = Selection.model_validate(event["selection"])
        evaluation = self._evaluate(state, selection)
        try:
            binding = self._binding(state, selection, evaluation)
        except (ValueError, OSError, KeyError):
            raise HTTPException(409, "conditional_source_invalid") from None
        if binding != event["binding"] or not evaluation["execution_available"]:
            raise HTTPException(409, "conditional_selection_unavailable_or_stale")
        return selection

    def confirm(self, state, draft_id, draft_digest, expected_revision):
        self._ready(state, expected_revision)
        event, action = self._proposal(state, draft_id, draft_digest)
        if action is not None:
            raise HTTPException(409, "conditional_selection_already_resolved")
        selection = self._recheck(state, event, event["input_revision"])
        self.service.controls.fence(state)
        state["_input_selections"][selection.tool_id] = selection.model_dump(mode="json")
        self._append_event(state, {
            "event": "confirmed", "draft_id": draft_id, "draft_digest": draft_digest,
            "input_revision": state["_input_revision"] + 1, "selection_digest": _digest(event["selection"]),
            "binding_digest": _digest(event["binding"]),
        })
        self.service.input_changed(state)
        return self._public_proposal(state, event)

    def cancel(self, state, draft_id, draft_digest, expected_revision):
        self._ready(state, expected_revision)
        event, action = self._proposal(state, draft_id, draft_digest)
        if action is not None and action["event"] == "cancelled":
            raise HTTPException(409, "conditional_selection_already_resolved")
        if action is None and state["_input_revision"] != event["input_revision"]:
            raise HTTPException(409, "conditional_selection_stale")
        changed = action is not None and action["event"] == "confirmed"
        if changed:
            if state["_input_selections"].get(event["selection"]["tool_id"]) != event["selection"]:
                raise HTTPException(409, "conditional_selection_stale")
            self.service.controls.fence(state)
            del state["_input_selections"][event["selection"]["tool_id"]]
        self._append_event(state, {
            "event": "cancelled", "draft_id": draft_id, "draft_digest": draft_digest,
            "input_revision": state["_input_revision"] + int(changed),
        })
        if changed:
            self.service.input_changed(state)
        else:
            self.service.save(state)
        return self._public_proposal(state, event)

    def selected_blocker(self, state, tool_id):
        if tool_id not in TOOLS:
            return None
        selection = state.get("_input_selections", {}).get(tool_id)
        if selection is None or selection.get("mode_id") == "not_provided":
            return "conditional_selection_not_confirmed"
        for event in reversed(state.get("_conditional_history", [])):
            if event["event"] != "proposed" or event["selection"] != selection:
                continue
            try:
                event, action = self._proposal(state, event["id"], event["digest"])
                if action is None or action["event"] != "confirmed":
                    return "conditional_selection_not_confirmed"
                self._recheck(state, event, action["input_revision"])
                return None
            except (HTTPException, ValueError, OSError, KeyError):
                return "conditional_selection_stale"
        return "conditional_selection_not_confirmed"

    def prepare(self, state, draft_id, draft_digest, expected_revision):
        self._ready(state, expected_revision)
        event, action = self._proposal(state, draft_id, draft_digest)
        if action is None or action["event"] != "confirmed":
            raise HTTPException(409, "conditional_selection_not_confirmed")
        selection = self._recheck(state, event, action["input_revision"])
        if state["_input_selections"].get(selection.tool_id) != event["selection"]:
            raise HTTPException(409, "conditional_selection_stale")
        # Service builds the existing Selection -> CaseInputBundle -> ToolRequest
        # one-step plan. Execution still requires ordinary exact plan approval.
        self.service.prepare_analysis(state, selection.tool_id)
        return self._public_proposal(state, event)

    def _public_proposal(self, state, event):
        _, action = self._proposal(state, event["id"], event["digest"])
        status = "pending" if action is None else action["event"]
        revision = event["input_revision"] if action is None else action["input_revision"]
        selection = Selection.model_validate(event["selection"])
        evaluation = self._evaluate(state, selection)
        if status != "cancelled":
            try:
                if state["_input_revision"] != revision or self._binding(state, selection, evaluation) != event["binding"]:
                    status = "stale"
            except (ValueError, OSError, KeyError):
                status = "stale"
        evaluation["execution_available"] = evaluation["execution_available"] and status in {"pending", "confirmed"}
        status_labels = {"pending": "待确认", "confirmed": "已确认，仍需单独批准计划",
                         "cancelled": "已取消", "stale": "输入已变化，需重新选择"}
        return {"id": event["id"], "digest": event["digest"], "status": status,
                "status_label": status_labels[status],
                "input_revision": state["_input_revision"], "label": "产品比较选择" if selection.tool_id == "P0-07" else "移植后证据选择",
                **evaluation}

    def public(self, state):
        return {
            "input_revision": state.get("_input_revision", 0),
            "access_boundary": "仅使用当前会话明确登记且可核对的私有输入；不代表取得新的许可或证明生物学可比性。",
            "scientific_boundary": "仅作研究性、描述性分析；移植后证据独立保存，不回填移植前评分、训练或校准。",
            "comparison": self._comparison_directory(state),
            "graft": self._graft_directory(state),
            "selections": [self._public_proposal(state, row) for row in state.get("_conditional_history", [])
                           if row["event"] == "proposed"],
        }
