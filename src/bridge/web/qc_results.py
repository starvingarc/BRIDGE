"""Resolve verified QC results without depending on the application coordinator."""

from __future__ import annotations

import hashlib
import json
import os
from contextlib import contextmanager
from pathlib import Path
from threading import RLock

from bridge.domain import CaseInputAsset
from bridge.storage.private_paths import ensure_private_directory

from .inputs import verify_checked_file
from .sessions import read_file, write_file

CATALOG_LOCK = RLock()


def qc_reading_note(receipt):
    """Explain verified QC output for display without changing its saved artifacts."""
    from bridge.tool_packages.p0_01_input_qc.measurement_specs import load_measurement_spec
    from bridge.toolkit.contracts import QCReadinessProfile

    profile = QCReadinessProfile.model_validate(receipt["result"])
    spec_ref = receipt["request"].get("measurement_spec_ref")
    if profile.assay_spec_id != spec_ref:
        raise ValueError("qc_measurement_spec_binding_mismatch")
    spec = load_measurement_spec(spec_ref)
    if spec_ref is not None and spec is None:
        # Do not echo arbitrary or no-longer-recognized identifiers.
        rule = "候选规则：本版本无法识别；请维护者核对原运行记录。"
    elif spec is None:
        rule = ("候选规则：未选择（measurement_spec_not_selected）。"
                "QC 规则定义候选标记的指标与阈值，网页首步默认仅审计，不自动选择规则。")
    else:
        rule = f"候选规则：{spec.measurement_spec_id}（候选，尚未完成科学验证）。"

    if profile.cell_qc.get("count_metrics_state") == "measured":
        metrics = "基础 QC 指标已计算。"
    else:
        metrics = "仅完成结构审计；基础计数 QC 指标不可用，需核对并提供原始计数及其输入声明。"

    flags_available = (
        spec_ref is not None
        and profile.data_views.get("eligible_cells_view", {}).get("state") == "candidate"
    )
    if flags_available:
        flags = "已生成候选标记；标记用于技术复核，不代表细胞身份或产品合格。"
        if profile.cell_qc.get("selection_state") == "applied":
            action = "本次已按明确请求生成筛选后数据视图；原始输入保留。"
        else:
            action = "本次仅添加标记，未删除细胞或细胞核；实际筛选需另行明确请求。"
    else:
        flags = "未生成候选标记；不可用不代表零个异常，也不代表所有细胞通过 QC。"
        if spec_ref is None:
            action = ("如需候选标记，请维护者核对原始计数与 scRNA/snRNA 类型后，"
                      "通过工具接口显式选择匹配规则重跑 QC。网页暂不支持选择 QC 规则，"
                      "无需自行填写或定义 MeasurementSpec。")
        else:
            action = "已选择规则仍未生成标记，请维护者核对输入级别及原始计数是否满足规则要求。"
    return metrics + rule + flags + action


class QcResults:
    """Own QC receipt validation, selected-view assets and catalog registration."""

    def __init__(self, sessions, max_upload_bytes):
        self.sessions = sessions
        self.max_upload_bytes = max_upload_bytes

    @contextmanager
    def catalog(self):
        # Toolkit currently resolves QC through a process environment variable.
        # Every Service shares this lock; restore even on planning/tool failure.
        with CATALOG_LOCK:
            previous = os.environ.get("BRIDGE_QC_PROFILE_CATALOG")
            os.environ["BRIDGE_QC_PROFILE_CATALOG"] = str(self.sessions.root / "qc-catalog.json")
            try:
                yield
            finally:
                if previous is None:
                    os.environ.pop("BRIDGE_QC_PROFILE_CATALOG", None)
                else:
                    os.environ["BRIDGE_QC_PROFILE_CATALOG"] = previous

    @staticmethod
    def receipt_asset_id(state, receipt):
        plan_id = receipt.get("plan_id")
        if not plan_id:
            return None
        plans = [
            state.get("_plan"),
            *(
                item.get("plan")
                for item in state.get("_plan_history", [])
                if isinstance(item, dict)
            ),
        ]
        matches = [
            plan for plan in plans if isinstance(plan, dict) and plan.get("plan_id") == plan_id
        ]
        if len(matches) != 1:
            return None
        asset_ids = set()
        for step in matches[0].get("steps", []):
            approved = step.get("approved_request_json")
            if approved is None:
                continue
            try:
                request = json.loads(approved)
            except (TypeError, json.JSONDecodeError):
                return None
            if request.get("tool_id") != "P0-01":
                continue
            assets = request.get("assets")
            if (
                not isinstance(assets, list)
                or len(assets) != 1
                or not isinstance(assets[0], dict)
                or not isinstance(assets[0].get("asset_id"), str)
            ):
                return None
            asset_ids.add(assets[0]["asset_id"])
        return next(iter(asset_ids)) if len(asset_ids) == 1 else None

    def asset(self, state, selected, *, register=True, enrich=True):
        """Return a verified asset; enrich selects the QC view, register updates the catalog."""
        for receipt in reversed(state.get("_tool_runs", [])):
            if receipt["file"] in state.get("_invalidated_receipts", {}):
                continue
            if receipt["tool_id"] != "P0-01" or receipt["state"] != "succeeded":
                continue
            receipt_asset_id = self.receipt_asset_id(state, receipt)
            if receipt_asset_id is not None and receipt_asset_id != selected:
                continue
            directory, _, _ = ensure_private_directory(
                self.sessions.directory(state["id"]) / "receipts"
            )
            raw = read_file(directory / receipt["file"])
            if hashlib.sha256(raw).hexdigest() != receipt["sha256"]:
                raise ValueError("qc_artifact_integrity_mismatch")
            run = json.loads(raw)
            if run["request"]["assets"][0]["asset_id"] != selected:
                if receipt_asset_id == selected:
                    raise ValueError("qc_artifact_integrity_mismatch")
                continue
            if receipt.get("declaration_start") != state["_uploads"][selected]["declaration_start"]:
                raise ValueError("qc_declaration_retracted")
            payload = run["request"]["assets"][0]
            declared = state.get("_asset_declarations", {}).get(selected) or state.get(
                "_qc_declarations", {}
            ).get(selected)
            if (
                payload.get("checksum") != state["_uploads"][selected]["sha256"]
                or declared
                and any(
                    payload.get(key) != declared.get(key)
                    for key in (
                        "assay",
                        "matrix_location",
                        "matrix_semantics",
                        "input_level",
                    )
                )
            ):
                raise ValueError("qc_declaration_retracted")
            artifacts = {Path(item["path"]).name: item for item in run["artifacts"]}
            values = {}
            for name in (
                "qc_readiness_profile.json",
                "qc_readiness_profile_v2.json",
                "structured_output_index.json",
            ):
                if name not in artifacts:
                    raise ValueError("qc_artifacts_missing")
                entry = artifacts[name]
                target = Path(entry["path"])
                relative = target.relative_to(self.sessions.directory(state["id"]) / "runs")
                current = self.sessions.directory(state["id"]) / "runs"
                for part in relative.parts:
                    current = current / part
                    if current.is_symlink():
                        raise ValueError("qc_artifact_integrity_mismatch")
                if not target.exists():
                    raise ValueError("qc_artifacts_missing")
                content = read_file(target)
                if hashlib.sha256(content).hexdigest() != entry["sha256"]:
                    raise ValueError("qc_artifact_integrity_mismatch")
                values[name] = json.loads(content)
            profile = values["qc_readiness_profile.json"]
            view = values["qc_readiness_profile_v2.json"]["selected_data_view"]
            if not view:
                raise ValueError("qc_artifacts_missing")
            if declared:
                committed_metadata = dict(declared.get("metadata") or {})
                receipt_metadata = dict(payload.get("metadata") or {})
                # Source-only form edits intentionally preserve QC; downstream
                # source binding comes from the separately confirmed upload field.
                committed_metadata.pop("source_family_id", None)
                receipt_metadata.pop("source_family_id", None)
                # Permit only the exact enrichments this method derives from
                # the checksummed canonical QC artifacts above.
                for key, value in {
                    "qc_profile_ref": profile["profile_id"],
                    "data_view_id": view["view_id"],
                    "parent_asset_sha256": view["parent_asset_sha256"],
                }.items():
                    if key in committed_metadata and committed_metadata[key] == value:
                        if key in receipt_metadata and receipt_metadata[key] != value:
                            raise ValueError("qc_declaration_retracted")
                        committed_metadata.pop(key)
                        receipt_metadata.pop(key, None)
                if json.dumps(committed_metadata, sort_keys=True, allow_nan=False) != json.dumps(
                    receipt_metadata, sort_keys=True, allow_nan=False
                ):
                    raise ValueError("qc_declaration_retracted")
            selected_artifact = None
            if view.get("view_kind") == "qc_selected_observations":
                matches = [
                    item for item in run["artifacts"] if item["artifact_id"] == view["artifact_id"]
                ]
                if (
                    len(matches) != 1
                    or matches[0]["kind"] != "qc_selected_h5ad"
                    or matches[0]["sha256"] != view["sha256"]
                    or view["parent_asset_id"] != selected
                    or view["parent_asset_sha256"] != payload["checksum"]
                ):
                    raise ValueError("qc_artifact_integrity_mismatch")
                selected_artifact = matches[0]
                try:
                    verify_checked_file(
                        self.sessions,
                        state,
                        selected_artifact["path"],
                        view["sha256"],
                        root=self.sessions.directory(state["id"]) / "runs",
                        limit=self.max_upload_bytes(),
                    )
                except (ValueError, OSError):
                    raise ValueError("qc_artifact_integrity_mismatch") from None
            if register:
                catalog_path = self.sessions.root / "qc-catalog.json"
                with CATALOG_LOCK:
                    catalog = (
                        json.loads(read_file(catalog_path))
                        if catalog_path.exists()
                        else {"profiles": {}}
                    )
                    catalog["profiles"][profile["profile_id"]] = {
                        "path": artifacts["qc_readiness_profile.json"]["path"],
                        "sha256": artifacts["qc_readiness_profile.json"]["sha256"],
                        "structured_output_index_path": artifacts["structured_output_index.json"][
                            "path"
                        ],
                        "structured_output_index_sha256": artifacts["structured_output_index.json"][
                            "sha256"
                        ],
                    }
                    write_file(catalog_path, json.dumps(catalog).encode())
            if not enrich:
                return CaseInputAsset.model_validate(payload)
            payload = dict(run["request"]["assets"][0])
            if selected_artifact is not None:
                payload.update(
                    asset_id=selected_artifact["artifact_id"],
                    path=selected_artifact["path"],
                    checksum=view["sha256"],
                    format="h5ad",
                    matrix_location=view["matrix_location"],
                    matrix_semantics=view["matrix_semantics"],
                )
            payload["metadata"] = {
                **payload.get("metadata", {}),
                "source_family_id": state["_uploads"][selected]["source_family_id"],
                "qc_profile_ref": profile["profile_id"],
                "data_view_id": view["view_id"],
                "parent_asset_sha256": view["parent_asset_sha256"],
            }
            return CaseInputAsset.model_validate(payload)
        raise ValueError("completed_qc_required")
