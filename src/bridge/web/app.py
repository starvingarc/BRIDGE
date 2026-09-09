from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from importlib.resources import files
import json
import math
import os
from pathlib import Path
import re
import secrets
import stat
from threading import BoundedSemaphore, RLock
import time
from typing import Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from bridge.domain import AnalysisPlan, CaseInputAsset, CaseInputBundle, approve_plan
from bridge.planner import PlanBuilder
from bridge.runners import ToolExecutionPipeline, ToolExecutionScope
from bridge.storage.private_paths import ensure_private_directory, verify_private_directory
from bridge.workflow import LocalWorkflowExecutor, SQLiteRunEventStore
from .provider import converse
from .control import Controls
from .clarification import Clarifications, AnswerBody, CardIdentity
from .scientific_inputs import ScientificInputs, DraftIdentity, DraftRevision
from .report_inputs import ReportInputs, ReportPreparation
from .intake import Intake, IntakeFacts, IntakeInput, IntakePrepare
from .inputs import Inputs, Selection, AssetDeclaration, PrepareAnalysis, OBJECT_LIMIT, checked_bytes
from bridge.toolkit.registry import ToolRegistry
from bridge.toolkit.contracts import ToolRequest, ToolRequestV2

CATALOG_LOCK = RLock()

ID = re.compile(r"^[a-f0-9]{32}$")
NO_GRAFT_DECLARATION = re.compile(
    r"(?:没有|无|未提供)(?:任何)?(?:移植|graft)(?:数据|证据)?"
    r"|\bno graft (?:data|evidence)(?:,\s*(?:please )?record (?:it as )?not provided)?\b"
    r"|\bgraft data (?:is |was )?not provided\b",
    re.I,
)
NO_GRAFT_UNCERTAIN = re.compile(
    r"[?？]|并非没有|不是没有|不要|取消|停止|撤回|假设|如果|假如"
    r"|\b(?:not without|not no|do not|don.t|cancel|stop|if|suppose)\b", re.I,
)
COOKIE = "bridge_session"
PUBLIC = ("id", "title", "updated_at", "status", "messages", "uploads", "plan", "artifacts", "error", "plan_history", "capabilities", "input_review_required", "pending_input_change")
PARQUET_MEDIA_TYPES = {"application/vnd.apache.parquet", "application/x-parquet"}
PARQUET_STORED_LIMIT = 8 * 1024 * 1024
PARQUET_ROW_GROUP_LIMIT = 32 * 1024 * 1024
PARQUET_ROW_LIMIT = 100
PARQUET_COLUMN_LIMIT = 24
PARQUET_RESPONSE_LIMIT = 200_000
PARQUET_TEXT_LIMIT = 1_000
PARQUET_TEXT_SUFFIX = "… [truncated]"
JSON_SAFE_INTEGER_LIMIT = (1 << 53) - 1


class ArtifactPreviewUnavailable(ValueError):
    pass


class ArtifactPreviewTooLarge(ArtifactPreviewUnavailable):
    pass


def parquet_preview(data: bytes) -> bytes:
    import pyarrow as pa
    import pyarrow.parquet as pq

    parquet = pq.ParquetFile(pa.BufferReader(data))
    metadata = parquet.metadata
    schema = parquet.schema_arrow
    total_rows = metadata.num_rows
    total_columns = len(schema)
    columns = schema.names[:PARQUET_COLUMN_LIMIT]
    if len(set(columns)) != len(columns):
        raise ArtifactPreviewUnavailable
    for field in list(schema)[:PARQUET_COLUMN_LIMIT]:
        data_type = field.type
        if not (
            pa.types.is_null(data_type)
            or pa.types.is_boolean(data_type)
            or pa.types.is_integer(data_type)
            or pa.types.is_floating(data_type)
            or pa.types.is_string(data_type)
            or pa.types.is_large_string(data_type)
        ):
            raise ArtifactPreviewUnavailable

    row_groups = []
    rows_accounted = 0
    declared_size = 0
    if total_rows:
        for index in range(metadata.num_row_groups):
            row_group = metadata.row_group(index)
            if row_group.num_rows < 0 or row_group.total_byte_size < 0:
                raise ArtifactPreviewUnavailable
            row_groups.append(index)
            rows_accounted += row_group.num_rows
            declared_size += row_group.total_byte_size
            if declared_size > PARQUET_ROW_GROUP_LIMIT:
                raise ArtifactPreviewTooLarge
            if rows_accounted >= PARQUET_ROW_LIMIT:
                break

    rows = []
    text_truncated = False
    for batch in parquet.iter_batches(
        batch_size=PARQUET_ROW_LIMIT,
        row_groups=row_groups,
        columns=columns,
        use_threads=False,
    ):
        for values in zip(*(column.to_pylist() for column in batch.columns)):
            rendered = []
            for value in values:
                if value is None or isinstance(value, bool):
                    rendered.append(value)
                elif isinstance(value, int):
                    rendered.append(
                        value if -JSON_SAFE_INTEGER_LIMIT <= value <= JSON_SAFE_INTEGER_LIMIT else str(value)
                    )
                elif isinstance(value, float):
                    if not math.isfinite(value):
                        rendered.append(
                            "NaN" if math.isnan(value) else "Infinity" if value > 0 else "-Infinity"
                        )
                    elif value.is_integer() and not (
                        -JSON_SAFE_INTEGER_LIMIT <= value <= JSON_SAFE_INTEGER_LIMIT
                    ):
                        rendered.append(str(value))
                    else:
                        rendered.append(value)
                elif isinstance(value, str):
                    if len(value) > PARQUET_TEXT_LIMIT:
                        value = value[:PARQUET_TEXT_LIMIT - len(PARQUET_TEXT_SUFFIX)] + PARQUET_TEXT_SUFFIX
                        text_truncated = True
                    rendered.append(value)
                else:
                    raise ArtifactPreviewUnavailable
            rows.append(rendered)
            if len(rows) >= PARQUET_ROW_LIMIT:
                break
        if len(rows) >= PARQUET_ROW_LIMIT:
            break

    payload = {
        "columns": columns,
        "rows": rows,
        "total_rows": total_rows,
        "total_columns": total_columns,
        "truncated": text_truncated or total_rows > len(rows) or total_columns > len(columns),
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode()
    if len(encoded) > PARQUET_RESPONSE_LIMIT:
        raise ArtifactPreviewTooLarge
    return encoded


@dataclass(frozen=True)
class Settings:
    storage_root: Path
    token: str
    model_base_url: str
    model: str
    model_api_key: str
    origin: str = "http://127.0.0.1:8765"
    static_dir: Path | None = None
    upload_limit: int = 128 * 1024 * 1024
    cookie_ttl: int = 12 * 3600
    cell_state_measurement_spec_ref: str | None = None
    share_result_summaries: bool = False
    model_action_protocol: Literal["json", "deepseek_tools"] = "json"

    def __post_init__(self):
        if (
            type(self.share_result_summaries) is not bool
            or self.model_action_protocol not in {"json", "deepseek_tools"}
        ):
            raise ValueError("invalid_server_configuration")
        if len(self.token) < 24 or not self.model_api_key or not self.model:
            raise ValueError("invalid_server_configuration")
        for url in (self.origin, self.model_base_url):
            parts = urlsplit(url)
            if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
                raise ValueError("invalid_server_configuration")


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Login(Body):
    token: str = Field(max_length=1024)


class Message(Body):
    text: str = Field(min_length=1, max_length=8000)


class SourceInput(Body):
    upload_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    source_family_id: str = Field(min_length=1, max_length=160, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")


class InputChange(Body):
    change_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    change_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


class Approval(Body):
    plan_id: str = Field(max_length=100)
    plan_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


def now():
    return datetime.now(timezone.utc).isoformat()


def uid():
    return secrets.token_hex(16)


def private_text(value: str) -> str:
    # Paths are never useful in a remote model prompt or public-facing envelope.
    return re.sub(r"(?<![\w:])(?:/[A-Za-z0-9_.-]+){2,}[^\s\"<>]*", "[private path omitted]", value)


def read_file(path: Path, limit: int | None = None) -> bytes:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o022:
            raise ValueError("private_file_invalid")
        if limit is not None and info.st_size > limit:
            raise ValueError("private_file_too_large")
        return stream.read()


def write_file(path: Path, content: bytes):
    ensure_private_directory(path.parent)
    temporary = path.parent / (uid() + ".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if path.is_symlink():
            raise ValueError("private_file_invalid")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def inspect_h5ad(path: Path) -> list[str]:
    import h5py
    with h5py.File(path, "r") as handle:
        if handle.attrs.get("encoding-type") != "anndata" or "obs" not in handle or "var" not in handle:
            raise ValueError("invalid_h5ad")
        visited = set()
        logical_bytes = 0
        def check(group, depth=0):
            nonlocal logical_bytes
            if depth > 16 or len(visited) > 10000:
                raise ValueError("h5ad_structure_limit")
            for name in group:
                link = group.get(name, getlink=True)
                if not isinstance(link, h5py.HardLink):
                    raise ValueError("h5ad_external_link")
                item = group[name]
                identity = hash(item.id)
                if identity in visited:
                    continue
                visited.add(identity)
                if isinstance(item, h5py.Group):
                    check(item, depth + 1)
                else:
                    if item.is_virtual or item.external:
                        raise ValueError("h5ad_external_dataset")
                    logical_bytes += item.size * item.dtype.itemsize
                    if item.size > 100_000_000 or logical_bytes > 512 * 1024 * 1024:
                        raise ValueError("h5ad_dataset_limit")
        check(handle)
        return (["X"] if "X" in handle else []) + [
            "layers/" + name for name in handle.get("layers", {})
            if re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", name)
        ]


class ProviderUnavailable(RuntimeError):
    pass


class Service:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.root, self.device, self.inode = ensure_private_directory(settings.storage_root)
        self.lock = RLock()
        self.registry = ToolRegistry.load_default()
        self.inputs = Inputs(self)
        self.controls = Controls(self)
        self.intake = Intake(self)
        self.clarifications = Clarifications(self)
        self.scientific_inputs = ScientificInputs(self)
        self.report_inputs = ReportInputs(self)
        self.cookies: dict[str, float] = {}
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="bridge-web")
        self.capacity = BoundedSemaphore(2)
        self.executor = LocalWorkflowExecutor(SQLiteRunEventStore(self.root / "events.sqlite3"), max_attempts=1)
        for item in self.root.iterdir():
            if ID.fullmatch(item.name):
                state = self.load(item.name)
                if state["status"] in {"running", "thinking", "stopping", "awaiting_approval"}:
                    state["status"], state["error"] = "failed", "interrupted"
                    if state["plan"] and state["plan"]["status"] in {"proposed", "approved", "cancelled"}:
                        state["plan"]["status"] = "cancelled"
                        for step in state["plan"]["steps"]:
                            if step["status"] in {"pending", "running"}:
                                step["status"], step["reason"] = "cancelled", "interrupted"
                    if state.get("_run_id"):
                        self.executor.cancel(state["_run_id"])
                    self.save(state)

    def directory(self, sid):
        verify_private_directory(self.root, device=self.device, inode=self.inode)
        if not ID.fullmatch(sid):
            raise HTTPException(404, "not_found")
        target = self.root / sid
        if not target.exists() or target.is_symlink():
            raise HTTPException(404, "not_found")
        ensure_private_directory(target)
        return target

    def load(self, sid):
        state = json.loads(read_file(self.directory(sid) / "session.json", 8 * 1024 * 1024))
        state.setdefault("plan_history", [])
        state.setdefault("_plan_history", [])
        state.setdefault("_tool_runs", [])
        self.inputs.initialize(state)
        self.controls.initialize(state)
        return state

    def save(self, state):
        state["updated_at"] = now()
        write_file(self.directory(state["id"]) / "session.json",
                   json.dumps(state, ensure_ascii=False).encode())

    def public(self, state):
        state["capabilities"] = self.capabilities(state)
        value = {key: state.get(key, [] if key == "plan_history" else None) for key in PUBLIC}
        value["clarifications"] = self.clarifications.public(state)
        value["scientific_drafts"] = self.scientific_inputs.public(state)
        return value

    def message(self, state, role, content):
        state["messages"].append({"id": uid(), "role": role, "content": private_text(content), "created_at": now()})

    def create(self):
        sid = uid()
        ensure_private_directory(self.root / sid)
        state = {"id": sid, "title": "New analysis", "updated_at": now(), "status": "idle",
                 "messages": [], "uploads": [], "plan": None, "artifacts": [], "error": None,
                 "_uploads": {}, "_artifacts": {}, "_plan": None,
                 "plan_history": [], "_plan_history": [], "_tool_runs": []}
        self.message(state, "assistant", "我是 BRIDGE。准备评估移植前的细胞产品？先上传这批细胞的 H5AD，再确认右侧产品资料。我会先检查数据可分析性，再按产品目标梳理细胞状态证据与缺口。资料确认后会生成下一阶段计划，单独批准才运行。这里提供研究性证据，不作临床或放行判断。")
        self.controls.initialize(state)
        self.save(state)
        return state


    @contextmanager
    def qc_catalog(self):
        # Toolkit currently resolves QC through a process environment variable.
        # Every Service shares this lock; restore even on planning/tool failure.
        with CATALOG_LOCK:
            previous = os.environ.get("BRIDGE_QC_PROFILE_CATALOG")
            os.environ["BRIDGE_QC_PROFILE_CATALOG"] = str(self.root / "qc-catalog.json")
            try:
                yield
            finally:
                if previous is None:
                    os.environ.pop("BRIDGE_QC_PROFILE_CATALOG", None)
                else:
                    os.environ["BRIDGE_QC_PROFILE_CATALOG"] = previous

    def archive_plan(self, state):
        if state.get("plan") and state["plan"]["status"] not in {"proposed", "approved"}:
            state["plan_history"].append(state["plan"])
            state["_plan_history"].append({"plan": state["_plan"], "bundle": state.get("_bundle"),
                                           "run_id": state.get("_run_id")})
        state["plan"], state["_plan"] = None, None
        state.pop("_run_id", None)

    def cell_state_config_reasons(self):
        if not self.settings.cell_state_measurement_spec_ref:
            return ["measurement_spec_not_configured"]
        from bridge.tool_packages.p0_02_cell_state.measurement_specs import load_measurement_spec
        from bridge.tool_packages.p0_02_cell_state.reference import (
            resolve_reference_snapshot, validate_reference_snapshot, validate_runtime_reference)
        try:
            spec = load_measurement_spec(self.settings.cell_state_measurement_spec_ref)
            if spec is None:
                return ["measurement_spec_not_found"]
            manifest = validate_reference_snapshot(resolve_reference_snapshot(spec.reference_refs[0]))
            validate_runtime_reference(manifest)
            if spec.measurement_spec_id not in manifest.measurement_spec_ids:
                return ["measurement_spec_not_supported_by_reference"]
        except Exception as exc:
            return [getattr(exc, "reason_code", "reference_configuration_invalid")]
        return []

    def no_graft_declared(self, state):
        text = next((item["content"] for item in reversed(state["messages"]) if item["role"] == "user"), "")
        if NO_GRAFT_UNCERTAIN.search(text):
            return False
        return bool(NO_GRAFT_DECLARATION.search(text))

    def capabilities(self, state):
        result = []
        selected = state["uploads"][-1]["id"] if state["uploads"] else None
        for spec in self.registry.list():
            reasons = []
            self.inputs.initialize(state)
            selection = state["_input_selections"].get(spec.tool_id)
            if selection is not None:
                try:
                    reasons = self.inputs.selection_reasons(state, Selection.model_validate(selection))
                except ValueError:
                    reasons = ["input_binding_invalid"]
            elif spec.tool_id == "P0-01":
                reasons = [] if selected else ["product_upload_required"]
                if selected and not self.assay(state, selected):
                    reasons.append("assay_declaration_required")
                if selected and not self.declaration(state, selected):
                    reasons.append("raw_count_declaration_required")
            elif spec.tool_id == "P0-02":
                reasons = self.cell_state_config_reasons()
                if not selected:
                    reasons.append("product_upload_required")
                elif not state["_uploads"][selected].get("source_family_id"):
                    reasons.append("source_family_id_required")
                if selected:
                    try:
                        self.qc_asset(state, selected, register=False)
                    except Exception as exc:
                        reasons.append(str(exc) if str(exc) in {"completed_qc_required", "qc_artifacts_missing", "qc_artifact_integrity_mismatch", "qc_declaration_retracted"} else "qc_artifacts_unavailable")
                else:
                    reasons.append("completed_qc_required")
            elif spec.tool_id == "P0-12":
                reasons = [] if self.no_graft_declared(state) else ["no_graft_declaration_required"]
                if selected and not any(item["asset_id"] == selected for item in state.get("_bundle", {}).get("assets", [])):
                    reasons.append("product_analysis_context_required")
                if not selected:
                    reasons.append("product_upload_required")
            else:
                contract = self.registry.describe_input(spec.tool_id)
                mode = contract.object_input_modes[0] if len(contract.object_input_modes) == 1 else None
                reasons = (["object_required:" + role.role for role in mode.roles if role.min_count]
                           if mode else ["input_mode_required"])
            if spec.tool_id == "P0-02":
                aids = selection["asset_ids"] if selection else ([selected] if selected else [])
                for aid in aids:
                    reasons.extend(self.intake.cell_state_reasons(state, aid))
            result.append({"tool_id": spec.tool_id, "label": spec.name,
                           "state": "needs_input" if reasons else "ready",
                           "reason_codes": reasons, "mode_id": selection["mode_id"] if selection else None})
        return result

    def stage_blocked(self, state, reason):
        state["status"], state["error"] = "idle", reason
        self.message(state, "assistant", "当前阶段输入尚未满足：" + reason + "。保留已有工具证据，不会推断缺失事实。")
        self.save(state)

    def prepare_analysis(self, state, tool_id):
        self.controls.require_ready(state)
        # Another session's in-flight tool may own the process QC catalog.
        # Never wait for that lock while holding the HTTP/session state lock.
        if not CATALOG_LOCK.acquire(blocking=False):
            raise HTTPException(409, "worker_busy")
        try:
            self._prepare_analysis(state, tool_id)
        finally:
            CATALOG_LOCK.release()

    def _prepare_analysis(self, state, tool_id):
        self.inputs.initialize(state)
        if tool_id == "P0-02":
            selection = state["_input_selections"].get(tool_id)
            aids = selection["asset_ids"] if selection else [item["id"] for item in state["uploads"][-1:]]
            if any(self.intake.cell_state_reasons(state, aid) for aid in aids):
                self.stage_blocked(state, "supported_product_family_required")
                return
        if tool_id in state["_input_selections"] or tool_id not in {"P0-02", "P0-12"}:
            self.prepare_selected(state, tool_id)
            return
        if tool_id == "P0-12":
            if not self.no_graft_declared(state):
                self.stage_blocked(state, "no_graft_declaration_required")
                return
        if not state["uploads"]:
            self.stage_blocked(state, "product_upload_required")
            return
        selected = state["uploads"][-1]["id"]
        upload = state["_uploads"][selected]
        try:
            directory, _, _ = ensure_private_directory(self.directory(state["id"]) / "uploads")
            path = directory / (selected + ".h5ad")
            if hashlib.sha256(read_file(path, self.settings.upload_limit)).hexdigest() != upload["sha256"]:
                raise ValueError("upload_integrity_mismatch")
            if tool_id == "P0-02":
                reasons = self.cell_state_config_reasons()
                if reasons:
                    self.stage_blocked(state, reasons[0])
                    return
                if not upload.get("source_family_id"):
                    self.stage_blocked(state, "source_family_id_required")
                    return
                asset = self.qc_asset(state, selected)
            else:
                # Context only: no biological semantics are inferred or sent to P0-12.
                context_assets = state.get("_bundle", {}).get("assets", [])
                context = next((item for item in context_assets if item["asset_id"] == selected), None)
                if context is None:
                    self.stage_blocked(state, "product_analysis_context_required")
                    return
                asset = CaseInputAsset.model_validate(context)
            bundle = CaseInputBundle(bundle_id=uid(), version="1", assets=[asset])
            spec = self.registry.describe(tool_id)
            arguments = dict(request_id=uid(), tool_id=tool_id, tool_version=spec.version,
                             output_dir=self.directory(state["id"]) / "runs")
            if tool_id == "P0-02":
                request = ToolRequest(**arguments, assets=[asset.to_toolkit_asset()],
                                      measurement_spec_ref=self.settings.cell_state_measurement_spec_ref)
            else:
                request = ToolRequestV2(**arguments, assets=[], object_inputs=[])
            self.propose_request(state, bundle, request, tool_id +
                (" 细胞状态候选分析；不保证 V3 或完整生物学证据。" if tool_id == "P0-02" else
                 " 明确未提供移植数据；不运行 graft 表达分析，不回填产品证据。"))
        except Exception as exc:
            reason = str(exc) if str(exc) in {"upload_integrity_mismatch", "completed_qc_required", "qc_artifacts_missing", "qc_artifact_integrity_mismatch", "qc_declaration_retracted"} else "stage_input_construction_failed"
            self.stage_blocked(state, reason)

    def qc_asset(self, state, selected, *, register=True):
        return self._qc_asset(state, selected, register=register, enrich=register)

    def effective_qc_asset(self, state, selected, *, register=False):
        return self._qc_asset(state, selected, register=register, enrich=True)

    def _qc_receipt_asset_id(self, state, receipt):
        plan_id = receipt.get("plan_id")
        if not plan_id:
            return None
        plans = [state.get("_plan"), *(
            item.get("plan")
            for item in state.get("_plan_history", [])
            if isinstance(item, dict)
        )]
        matches = [
            plan for plan in plans
            if isinstance(plan, dict) and plan.get("plan_id") == plan_id
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

    def _qc_asset(self, state, selected, *, register, enrich):
        for receipt in reversed(state.get("_tool_runs", [])):
            if receipt["tool_id"] != "P0-01" or receipt["state"] != "succeeded":
                continue
            receipt_asset_id = self._qc_receipt_asset_id(state, receipt)
            if receipt_asset_id is not None and receipt_asset_id != selected:
                continue
            directory, _, _ = ensure_private_directory(self.directory(state["id"]) / "receipts")
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
            declared = state.get("_asset_declarations", {}).get(selected) or state.get("_qc_declarations", {}).get(selected)
            if (payload.get("checksum") != state["_uploads"][selected]["sha256"]
                    or declared and any(payload.get(key) != declared.get(key) for key in
                        ("assay", "matrix_location", "matrix_semantics", "input_level"))):
                raise ValueError("qc_declaration_retracted")
            artifacts = {Path(item["path"]).name: item for item in run["artifacts"]}
            values = {}
            for name in ("qc_readiness_profile.json", "qc_readiness_profile_v2.json", "structured_output_index.json"):
                if name not in artifacts:
                    raise ValueError("qc_artifacts_missing")
                entry = artifacts[name]
                target = Path(entry["path"])
                relative = target.relative_to(self.directory(state["id"]) / "runs")
                current = self.directory(state["id"]) / "runs"
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
                        receipt_metadata, sort_keys=True, allow_nan=False):
                    raise ValueError("qc_declaration_retracted")
            selected_artifact = None
            if view.get("view_kind") == "qc_selected_observations":
                matches = [item for item in run["artifacts"]
                           if item["artifact_id"] == view["artifact_id"]]
                if (len(matches) != 1 or matches[0]["kind"] != "qc_selected_h5ad"
                        or matches[0]["sha256"] != view["sha256"]
                        or view["parent_asset_id"] != selected
                        or view["parent_asset_sha256"] != payload["checksum"]):
                    raise ValueError("qc_artifact_integrity_mismatch")
                selected_artifact = matches[0]
                try:
                    checked_bytes(self, state, selected_artifact["path"], view["sha256"],
                                  root=self.directory(state["id"]) / "runs",
                                  limit=self.settings.upload_limit)
                except (ValueError, OSError):
                    raise ValueError("qc_artifact_integrity_mismatch") from None
            if register:
                catalog_path = self.root / "qc-catalog.json"
                with CATALOG_LOCK:
                    catalog = json.loads(read_file(catalog_path)) if catalog_path.exists() else {"profiles": {}}
                    catalog["profiles"][profile["profile_id"]] = {
                        "path": artifacts["qc_readiness_profile.json"]["path"],
                        "sha256": artifacts["qc_readiness_profile.json"]["sha256"],
                        "structured_output_index_path": artifacts["structured_output_index.json"]["path"],
                        "structured_output_index_sha256": artifacts["structured_output_index.json"]["sha256"]}
                    write_file(catalog_path, json.dumps(catalog).encode())
            if not enrich:
                return CaseInputAsset.model_validate(payload)
            payload = dict(run["request"]["assets"][0])
            if selected_artifact is not None:
                payload.update(
                    asset_id=selected_artifact["artifact_id"],
                    path=selected_artifact["path"], checksum=view["sha256"],
                    format="h5ad", matrix_location=view["matrix_location"],
                    matrix_semantics=view["matrix_semantics"],
                )
            payload["metadata"] = {**payload.get("metadata", {}),
                "source_family_id": state["_uploads"][selected]["source_family_id"],
                "qc_profile_ref": profile["profile_id"], "data_view_id": view["view_id"],
                "parent_asset_sha256": view["parent_asset_sha256"]}
            return CaseInputAsset.model_validate(payload)
        raise ValueError("completed_qc_required")

    def prepare_selected(self, state, tool_id):
        self.inputs.initialize(state)
        blocker = self.scientific_inputs.selected_blocker(state, tool_id) or self.report_inputs.selected_blocker(state, tool_id)
        if blocker:
            self.stage_blocked(state, blocker)
            return
        contract = self.registry.describe_input(tool_id)
        saved = state["_input_selections"].get(tool_id)
        if saved is None:
            mode_id = contract.object_input_modes[0].mode_id if len(contract.object_input_modes) == 1 else None
            saved = dict(tool_id=tool_id, mode_id=mode_id, asset_ids=[], object_inputs=[], measurement_spec_ref=None)
        try:
            bundle, request = self.inputs.construct(state, Selection.model_validate(saved))
        except (ValueError, OSError) as exc:
            reason = str(exc)
            if not re.fullmatch(r"[a-z_]+(?::[a-z_]+)?", reason):
                reason = "input_binding_invalid"
            self.stage_blocked(state, reason)
            return
        self.propose_request(state, bundle, request, tool_id + " / " + (saved["mode_id"] or "asset_input") +
            "；使用明确选择的输入；仅研究性证据，不补造事实。请单独确认本次计划。")

    def propose_request(self, state, bundle, request, summary):
        snapshot = files("bridge.resources").joinpath("knowledge_snapshot.json.gz").read_bytes()
        with self.qc_catalog():
            plan = PlanBuilder(self.registry).build(bundle, output_root=request.output_dir,
                knowledge_snapshot_ref="sha256:" + hashlib.sha256(snapshot).hexdigest(),
                requests=[request], include_input_qc=False)
        self.archive_plan(state)
        state["_bundle"], state["_plan"] = bundle.model_dump(mode="json"), plan.model_dump(mode="json")
        state["plan"] = {"id": plan.plan_id, "digest": plan.approval_sha256(), "status": "proposed",
            "summary": summary,
            "steps": [{"id": item.step_id, "tool_id": item.tool_id,
                       "label": self.registry.describe(item.tool_id).name,
                       "status": "pending" if item.disposition.value == "execute" else "blocked",
                       "reason": None if not item.reason_codes else "input_not_eligible"} for item in plan.steps]}
        state["status"], state["error"] = "awaiting_approval", None
        self.message(state, "assistant", "新阶段计划已生成。请检查输入模式并单独确认；之前的审批不适用于本阶段。")
        self.save(state)

    def input_changed(self, state):
        state["_input_revision"] += 1
        if state.get("plan") and state["plan"]["status"] == "proposed":
            state["plan"], state["_plan"], state["status"] = None, None, "idle"
        state["error"] = None
        self.save(state)

    def busy(self, state):
        if state["status"] in {"thinking", "running", "stopping"}:
            raise HTTPException(409, "session_busy")

    def schedule(self, state, status, work):
        if not self.capacity.acquire(blocking=False):
            raise HTTPException(429, "worker_busy")
        state["_control_epoch"] += 1
        epoch = state["_control_epoch"]
        state["status"], state["error"] = status, None
        self.save(state)
        sid = state["id"]
        def run():
            try:
                work(sid, epoch)
            except Exception as exc:
                with self.lock:
                    failed = self.load(sid)
                    if failed["_control_epoch"] == epoch:
                        failed["status"] = "failed"
                        failed["error"] = ("provider_unavailable" if isinstance(exc, ProviderUnavailable) else "stage_input_construction_failed") if status == "thinking" else "execution_failed"
                        if failed["plan"] and status == "running":
                            failed["plan"]["status"] = "partial" if any(step["status"] in {"succeeded", "partial"} for step in failed["plan"]["steps"]) else "failed"
                            for step in failed["plan"]["steps"]:
                                if step["status"] in {"pending", "running"}:
                                    step["status"], step["reason"] = "failed", "execution_failed"
                        self.save(failed)
            finally:
                # The sole worker owns executor cancellation, after any in-flight
                # tool has released its operation lock. HTTP only fences state.
                with self.lock:
                    current = self.load(sid)
                    stopped = current["_control_epoch"] != epoch
                    run_id = current.get("_run_id") if stopped and status == "running" else None
                if run_id:
                    self.executor.cancel(run_id)
                with self.lock:
                    current = self.load(sid)
                    if current["_control_epoch"] != epoch and current["status"] == "stopping":
                        self.controls.settle(current)
                        self.save(current)
                self.capacity.release()
        self.pool.submit(run)

    def declaration(self, state, upload_id):
        declared = state.get("_asset_declarations", {}).get(upload_id) or state.get("_qc_declarations", {}).get(upload_id)
        if declared:
            return declared["matrix_location"] if declared.get("matrix_semantics") == "raw_counts" else None
        return None

    def think(self, sid, epoch):
        with self.lock:
            state = self.load(sid)
            if state["_control_epoch"] != epoch:
                return
        allowed_tools = {spec.tool_id for spec in self.registry.list()}
        allowed_states = {"succeeded", "failed", "partial", "cancelled", "blocked"}
        tool_history = [{"tool_id": item["tool_id"], "state": item["state"]}
                        for item in state.get("_tool_runs", [])[-24:]
                        if item.get("tool_id") in allowed_tools and item.get("state") in allowed_states]
        context = {"status": "idle", "upload_ids": [item["id"] for item in state["uploads"]],
                   "plan_status": state["plan"]["status"] if state["plan"] else None,
                   "capabilities": self.capabilities(state), "tool_execution_history": tool_history,
                   "input_contracts": {
                       spec.tool_id: [{"mode_id": mode.mode_id,
                                       "required_roles": [role.role for role in mode.roles if role.min_count]}
                                      for mode in self.registry.describe_input(spec.tool_id).object_input_modes]
                       for spec in self.registry.list()
                   },
                   "results_sent_to_model": False}
        context["input_review_required"] = state["input_review_required"]
        context["clarification_context"] = self.clarifications.context(state)
        # Provider receives readiness only, never private form values or column names.
        context["intake_context"] = [
            {"upload_id": item["id"],
             "state": "confirmed" if state.get("_intakes", {}).get(item["id"], {}).get("signature") ==
                 self.intake.signature(state, item["id"]) else "needs_confirmation",
             "missing_fields": self.intake.missing_fields(self.intake.current_facts(state, item["id"]))}
            for item in state["uploads"]
        ]
        result_turn_id = None
        if self.settings.share_result_summaries and not state["input_review_required"]:
            from .evidence import build_result_context
            summary, binding = build_result_context(self.inputs, state)
            context["result_summary"] = summary
            context["results_sent_to_model"] = summary["state"] == "available"
            result_turn_id = next(
                (item["id"] for item in reversed(state["messages"]) if item["role"] == "user"),
                None,
            )
            if result_turn_id is not None:
                with self.lock:
                    current = self.load(sid)
                    if current["_control_epoch"] != epoch:
                        return
                    records = current.setdefault("_result_contexts", {})
                    records[result_turn_id] = {
                        "control_epoch": epoch,
                        "result_summary": summary,
                        "private_binding": binding,
                    }
                    while len(records) > 24:
                        records.pop(next(iter(records)))
                    self.save(current)
        result_reply_ids = {
            record.get("assistant_message_id")
            for record in state.get("_result_contexts", {}).values()
            if isinstance(record, dict) and record.get("assistant_message_id")
        }
        private_message_ids = self.clarifications.private_message_ids(state) | self.scientific_inputs.private_message_ids(state)
        provider_messages = [
            {"role": item["role"], "content": private_text(item["content"])}
            for item in state["messages"]
            if item["id"] not in private_message_ids
            and (context["results_sent_to_model"] or item["id"] not in result_reply_ids)
        ]
        try:
            action = converse(self.settings, provider_messages, context)
        except Exception as exc:
            raise ProviderUnavailable() from exc
        if action.action == "draft_scientific_inputs":
            self.draft_scientific_inputs(sid, epoch, action.upload_id)
            return
        if action.action == "propose_scientific_inputs":
            raise ValueError("scientific_draft_purpose_required")
        with self.lock:
            state = self.load(sid)
            if state["_control_epoch"] != epoch:
                return
            assistant_message_id = None
            if action.action == "ask_user_input":
                card = self.clarifications.stage(state, action.questions)
                if card is None or card["status"] != "pending":
                    self.message(state, "assistant", "这些项目已有回答或已确认资料，我会保留现有信息；未知项仍按缺失处理。可在原问题卡片中修改。")
            elif action.action == "review_inputs":
                self.controls.review(state)
                self.message(state, "assistant", action.text)
                assistant_message_id = state["messages"][-1]["id"]
            elif action.action == "propose_intake":
                if action.upload_id not in state["_uploads"]:
                    raise ValueError("unknown_upload")
                if action.upload_id in state.get("_intakes", {}) or state["input_review_required"]:
                    self.message(state, "assistant", "请在右侧产品资料中查看或修改已确认事实，并确认精确变更。聊天不会改写现有声明。")
                else:
                    facts = self.intake.current_facts(state, action.upload_id).model_dump()
                    facts.update(action.facts.model_dump(exclude_unset=True))
                    self.controls.stage(state, "intake", IntakeInput(upload_id=action.upload_id,
                        facts=IntakeFacts.model_validate(facts)))
                    self.message(state, "assistant", "产品资料草稿已整理，请在右侧核对并确认。确认资料不会自动启动分析。")
            elif action.action in {"prepare_analysis", "prepare_qc"} and state["input_review_required"]:
                self.stage_blocked(state, "input_review_required")
                return
            elif action.action == "prepare_analysis":
                self.prepare_analysis(state, action.tool_id)
                return
            elif action.action == "prepare_qc":
                if action.upload_id not in state["_uploads"]:
                    raise ValueError("unknown_upload")
                declaration = self.declaration(state, action.upload_id)
                if declaration != action.matrix_location:
                    self.message(state, "assistant", "请先在右侧产品资料中确认实验类型与原始计数位置。聊天中的说法不会自动成为已确认输入。")
                else:
                    try:
                        self.qc_asset(state, action.upload_id, register=False)
                    except (ValueError, OSError, KeyError) as exc:
                        if str(exc) not in {"completed_qc_required", "qc_declaration_retracted"}:
                            self.stage_blocked(state, "qc_evidence_unavailable")
                            return
                        self.prepare(state, action.upload_id, declaration)
                        return
                    self.message(state, "assistant", "这份输入已有仍有效的 QC 证据，无需重复运行。可直接查看已有结果或继续下一阶段。")
            else:
                self.message(state, "assistant", action.text)
                assistant_message_id = state["messages"][-1]["id"]
            if (
                assistant_message_id is not None
                and result_turn_id is not None
                and context["results_sent_to_model"]
            ):
                record = state.get("_result_contexts", {}).get(result_turn_id)
                if record is not None:
                    record["assistant_message_id"] = assistant_message_id
            state["status"] = "idle"
            self.save(state)

    def draft_scientific_inputs(self, sid, epoch, aid):
        with self.lock:
            state = self.load(sid)
            if state["_control_epoch"] != epoch:
                return
            try:
                context, binding = self.scientific_inputs.request_context(state, aid)
            except (ValueError, OSError, KeyError, HTTPException):
                state["status"], state["error"] = "idle", "scientific_intent_or_source_required"
                self.save(state)
                return
        for attempt in range(2):
            feedback = None
            try:
                action = converse(self.settings, [{"role": "user", "content":
                    "请用中文提出有来源的科学输入候选，供用户逐项确认。严格遵守上下文中的候选约束；没有充分来源的选择保持未确定。不要运行分析或确认任何声明。"}], context)
            except ValueError:
                feedback = "scientific_candidate_shape_invalid"
            except Exception as exc:
                raise ProviderUnavailable() from exc
            else:
                if action.action != "propose_scientific_inputs" or action.upload_id != aid:
                    feedback = "scientific_candidate_required"
                else:
                    try:
                        self.scientific_inputs._validate(action.candidate, context)
                    except ValueError as exc:
                        feedback = str(exc)
            with self.lock:
                current = self.load(sid)
                if current["_control_epoch"] != epoch:
                    return
                if feedback:
                    try:
                        _, current_binding = self.scientific_inputs.request_context(current, aid)
                        if current_binding != binding:
                            raise ValueError("scientific_draft_stale")
                    except (ValueError, OSError, KeyError, HTTPException):
                        current["status"], current["error"] = "idle", "scientific_draft_stale"
                        self.save(current)
                        return
                    if attempt == 0:
                        # Retry only shape/source validation once. Never resend
                        # invalid values, private history or unconfirmed facts.
                        context = {**context, "validation_feedback": feedback}
                        continue
                    current["status"], current["error"] = "idle", "scientific_candidate_invalid"
                    self.message(current, "assistant", "候选仍未通过来源或结构校验，未生成科学草稿，也未运行分析。请重新整理候选；未知项继续保留。")
                    self.save(current)
                    return
                self.scientific_inputs.propose(current, aid, action.candidate, expected_binding=binding)
                current["status"], current["error"] = "idle", None
                self.save(current)
                return

    def assay(self, state, upload_id):
        declared = state.get("_asset_declarations", {}).get(upload_id) or state.get("_qc_declarations", {}).get(upload_id)
        if declared:
            return declared.get("assay")
        return None

    def prepare(self, state, upload_id, location):
        self.controls.require_ready(state)
        assay = self.assay(state, upload_id)
        if assay is None or self.declaration(state, upload_id) != location:
            raise HTTPException(409, "intake_confirmation_required")
        upload = state["_uploads"][upload_id]
        if location not in upload["locations"]:
            raise ValueError("matrix_not_registered")
        directory, _, _ = ensure_private_directory(self.directory(state["id"]) / "uploads")
        path = directory / (upload_id + ".h5ad")
        data = read_file(path, self.settings.upload_limit)
        if hashlib.sha256(data).hexdigest() != upload["sha256"]:
            raise ValueError("upload_integrity_mismatch")
        declared = state["_asset_declarations"].get(upload_id)
        asset = (CaseInputAsset.model_validate(declared) if declared else
                 CaseInputAsset(asset_id=upload_id, path=path, format="h5ad",
                                checksum=upload["sha256"], **state["_qc_declarations"][upload_id]))
        bundle = CaseInputBundle(bundle_id=uid(), version="1", assets=[asset])
        snapshot = files("bridge.resources").joinpath("knowledge_snapshot.json.gz").read_bytes()
        plan = PlanBuilder().build(bundle, output_root=self.directory(state["id"]) / "runs",
                                   knowledge_snapshot_ref="sha256:" + hashlib.sha256(snapshot).hexdigest())
        self.archive_plan(state)
        state["_bundle"] = bundle.model_dump(mode="json")
        state["_plan"] = plan.model_dump(mode="json")
        state["plan"] = {"id": plan.plan_id, "digest": plan.approval_sha256(), "status": "proposed",
                         "summary": "P0-01 输入 QC；实验类型：" + assay + "；原始计数位置：" + location + "。使用已确认的输入声明；仅研究性候选结果，不推断生物学重复。",
                         "steps": [{"id": item.step_id, "tool_id": item.tool_id, "label": "输入质量与可分析性",
                                    "status": "pending" if item.disposition.value == "execute" else "skipped",
                                    "reason": None if not item.reason_codes else "input_not_eligible"} for item in plan.steps]}
        state["status"] = "awaiting_approval"
        self.message(state, "assistant", "已根据您的计数声明生成输入 QC 计划。请检查并确认；确认前不会运行。结果不代表科学方法已验证。")
        self.save(state)

    def verify_scientific_plan(self, state, plan):
        for step in plan.steps:
            blocker = (self.scientific_inputs.selected_blocker(state, step.tool_id)
                       or self.report_inputs.selected_blocker(state, step.tool_id))
            if blocker:
                raise ValueError(blocker)

    def execute(self, sid, epoch):
        with self.qc_catalog():
            self._execute(sid, epoch)

    def _execute(self, sid, epoch):
        with self.lock:
            state = self.load(sid)
            if state["_control_epoch"] != epoch or state["input_review_required"]:
                return
            plan = AnalysisPlan.model_validate(state["_plan"])
            self.verify_scientific_plan(state, plan)
            self.inputs.verify_plan(state, plan)
            for upload_id, upload in state["_uploads"].items():
                directory, _, _ = ensure_private_directory(self.directory(sid) / "uploads")
                path = directory / (upload_id + ".h5ad")
                if hashlib.sha256(read_file(path, self.settings.upload_limit)).hexdigest() != upload["sha256"]:
                    raise ValueError("upload_integrity_mismatch")
            run_id = self.executor.submit(plan)
            state["_run_id"] = run_id
            self.save(state)
        pipeline = ToolExecutionPipeline(ToolExecutionScope.from_plan(plan))
        while True:
            with self.lock:
                state = self.load(sid)
                if state["_control_epoch"] != epoch or state["input_review_required"]:
                    return
                claim = self.executor.claim_step(run_id)
                if claim is None:
                    break
                for item in state["plan"]["steps"]:
                    if item["id"] == claim.step_id:
                        item["status"] = "running"
                # Capture declaration binding before this exact in-flight step.
                qc_revision = {key: value["declaration_start"] for key, value in state["_uploads"].items()}
                self.save(state)
            outcome = self.executor.execute_claim(claim, pipeline)
            with self.lock:
                state = self.load(sid)
                receipt_id = uid()
                receipt = outcome.model_dump_json().encode()
                write_file(self.directory(sid) / "receipts" / (receipt_id + ".json"), receipt)
                state["_tool_runs"].append({"file": receipt_id + ".json", "sha256": hashlib.sha256(receipt).hexdigest(),
                                           "tool_id": outcome.request.tool_id, "state": outcome.execution_state.value,
                                           "plan_id": plan.plan_id,
                                           "declaration_start": qc_revision.get(outcome.request.assets[0].asset_id) if outcome.request.assets else None})
                self.save(state)
                for item in state["plan"]["steps"]:
                    if item["id"] == claim.step_id:
                        item["status"] = outcome.execution_state.value if outcome.execution_state.value in {"succeeded", "partial", "cancelled", "blocked"} else "failed"
                        item["reason"] = None if item["status"] == "succeeded" else "tool_not_successful"
                self.save(state)
                self.inputs.register_outputs(state, outcome, state["_tool_runs"][-1])
                self.register_artifacts(state, outcome)
        with self.lock:
            state = self.load(sid)
            if state["_control_epoch"] != epoch:
                return
            snapshot = self.executor.get_status(run_id)
            success = snapshot.status.value == "succeeded"
            state["status"] = "idle" if success else "failed"
            state["error"] = None if success else "execution_incomplete"
            actual = {item["status"] for item in state["plan"]["steps"]}
            state["plan"]["status"] = "completed" if success else ("partial" if "partial" in actual or "succeeded" in actual else "cancelled" if "cancelled" in actual else "failed")
            self.message(state, "assistant", "工具运行已结束。请在结果面板查看工具生成的图表和证据。未声明的采样或捕获信息不会被补造；运行完成不代表科学验证通过，不能用于临床或放行结论。" if success else "工具运行未完整完成。未将缺失或失败证据解释为产品失败。")
            self.save(state)

    def read_registered_artifact(self, state, aid, limit=128 * 1024 * 1024):
        if not ID.fullmatch(aid) or aid not in state["_artifacts"]:
            raise HTTPException(404, "not_found")
        record = state["_artifacts"][aid]
        path = self.directory(state["id"]) / "artifacts" / record["file"]
        if path.parent.is_symlink():
            raise HTTPException(404, "not_found")
        data = read_file(path, limit)
        if hashlib.sha256(data).hexdigest() != record["sha256"]:
            raise HTTPException(409, "artifact_integrity_mismatch")
        public = next(item for item in state["artifacts"] if item["id"] == aid)
        return public, data

    def register_artifacts(self, state, outcome):
        root = self.directory(state["id"])
        for artifact in outcome.artifacts:
            path = artifact.path
            try:
                relative = path.relative_to(root / "runs")
            except ValueError:
                raise ValueError("artifact_outside_run")
            current = root / "runs"
            for part in relative.parts:
                current = current / part
                if current.is_symlink():
                    raise ValueError("artifact_symlink")
            suffix = path.suffix.lower()
            media = {".png": "image/png", ".svg": "image/svg+xml", ".json": "application/json",
                     ".csv": "text/csv", ".tsv": "text/tab-separated-values",
                     ".parquet": "application/octet-stream"}.get(suffix)
            if not media:
                continue
            data = read_file(path, 128 * 1024 * 1024)
            if hashlib.sha256(data).hexdigest() != artifact.sha256:
                raise ValueError("artifact_integrity_mismatch")
            if suffix == ".json":
                def redact(value):
                    if isinstance(value, dict):
                        return {key: redact(item) for key, item in value.items() if "path" not in key.lower() and key not in {"output_dir"}}
                    if isinstance(value, list):
                        return [redact(item) for item in value]
                    return private_text(value) if isinstance(value, str) else value
                data = json.dumps(redact(json.loads(data)), ensure_ascii=False).encode()
            aid = uid()
            write_file(root / "artifacts" / (aid + suffix), data)
            kind = "figure" if suffix in {".png", ".svg"} else "evidence" if suffix == ".json" else "table"
            name = re.sub(r"[^A-Za-z0-9_.-]", "_", path.name)[:100]
            if suffix == ".json":
                name = name.removesuffix(".json") + ".display-redacted.json"
            state["artifacts"].append({"id": aid, "name": name, "kind": kind, "media_type": media,
                                       "url": f"/api/sessions/{state['id']}/artifacts/{aid}", "tool_id": outcome.request.tool_id})
            self.inputs.initialize(state)
            state["_canonical_artifacts"][aid] = {"path": str(artifact.path), "sha256": artifact.sha256,
                "artifact_id": artifact.artifact_id, "receipt_file": state["_tool_runs"][-1]["file"],
                "receipt_sha256": state["_tool_runs"][-1]["sha256"]}
            state["_artifacts"][aid] = {"file": aid + suffix, "sha256": hashlib.sha256(data).hexdigest(),
                                       "source_artifact_id": artifact.artifact_id, "source_sha256": artifact.sha256,
                                       "projection": "path_redacted_display" if suffix == ".json" else "identity"}
            self.save(state)


def create_app(settings: Settings) -> FastAPI:
    service = Service(settings)

    @asynccontextmanager
    async def lifespan(app):
        yield
        service.pool.shutdown(wait=True, cancel_futures=False)

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.service = service

    @app.exception_handler(RequestValidationError)
    async def invalid(request, exc):
        return JSONResponse({"detail": "invalid_request"}, status_code=422)

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        if request.url.path.startswith("/api/"):
            try:
                received = 0
                exceeded = False
                if request.headers.get("host") != urlsplit(settings.origin).netloc:
                    return JSONResponse({"detail": "invalid_host"}, status_code=403)
                if request.method not in {"GET", "HEAD", "OPTIONS"}:
                    if request.headers.get("origin") != settings.origin:
                        return JSONResponse({"detail": "origin_required"}, status_code=403)
                    length = request.headers.get("content-length")
                    limit = (settings.upload_limit + 65536 if request.url.path.endswith("/uploads") else
                             OBJECT_LIMIT + 65536 if request.url.path.endswith("/analysis-inputs/objects") else
                             65536 if request.url.path.endswith("/analysis-inputs/assets") else 32768)
                    if length is None or not length.isdigit() or int(length) > limit:
                        return JSONResponse({"detail": "request_too_large"}, status_code=413)
                    original_receive = request._receive
                    async def bounded_receive():
                        nonlocal received, exceeded
                        message = await original_receive()
                        received += len(message.get("body", b""))
                        if received > limit:
                            exceeded = True
                            raise ValueError("request_too_large")
                        return message
                    request._receive = bounded_receive
                if request.url.path not in {"/api/health", "/api/login"}:
                    token = request.cookies.get(COOKIE, "")
                    if service.cookies.get(hashlib.sha256(token.encode()).hexdigest(), 0) <= time.time():
                        return JSONResponse({"detail": "authentication_required"}, status_code=401)
                response = await call_next(request)
                if exceeded:
                    response = JSONResponse({"detail": "request_too_large"}, status_code=413)
            except Exception:
                return JSONResponse({"detail": "request_failed"}, status_code=500)
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
            return response
        return await call_next(request)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.post("/api/login")
    def login(body: Login, response: Response):
        if not secrets.compare_digest(body.token.encode(), settings.token.encode()):
            raise HTTPException(401, "authentication_failed")
        cookie = secrets.token_urlsafe(32)
        with service.lock:
            service.cookies = {key: expiry for key, expiry in service.cookies.items() if expiry > time.time()}
            if len(service.cookies) >= 128:
                raise HTTPException(429, "too_many_logins")
            service.cookies[hashlib.sha256(cookie.encode()).hexdigest()] = time.time() + settings.cookie_ttl
        response.set_cookie(COOKIE, cookie, httponly=True, samesite="strict", secure=settings.origin.startswith("https:"), max_age=settings.cookie_ttl)
        return {"authenticated": True}

    @app.post("/api/logout")
    def logout(request: Request, response: Response):
        with service.lock:
            service.cookies.pop(hashlib.sha256(request.cookies.get(COOKIE, "").encode()).hexdigest(), None)
        response.delete_cookie(COOKIE)
        return {"authenticated": False}

    @app.get("/api/sessions")
    def sessions():
        with service.lock:
            states = [service.load(item.name) for item in service.root.iterdir() if ID.fullmatch(item.name)]
            return {"sessions": sorted([{key: item[key] for key in ("id", "title", "updated_at")} for item in states],
                                       key=lambda item: item["updated_at"], reverse=True)}

    @app.post("/api/sessions")
    def create():
        with service.lock:
            return service.public(service.create())

    @app.get("/api/sessions/{sid}")
    def get(sid: str):
        with service.lock:
            return service.public(service.load(sid))

    @app.post("/api/sessions/{sid}/uploads")
    def upload(sid: str, file: UploadFile = File(...)):
        with service.lock:
            state = service.load(sid)
            service.busy(state)
            if len(state["uploads"]) >= 8:
                raise HTTPException(400, "upload_count_limit")
            name = file.filename or ""
            if "/" in name or "\\" in name or not name.lower().endswith(".h5ad") or len(name) > 120:
                raise HTTPException(400, "invalid_upload_name")
            content = file.file.read(settings.upload_limit + 1)
            if len(content) > settings.upload_limit:
                raise HTTPException(413, "upload_too_large")
            if content[:8] != b"\x89HDF\r\n\x1a\n":
                raise HTTPException(400, "invalid_h5ad")
            aid = uid()
            path = service.directory(sid) / "uploads" / (aid + ".h5ad")
            write_file(path, content)
            try:
                locations = inspect_h5ad(path)
            except Exception:
                path.unlink(missing_ok=True)
                raise HTTPException(400, "invalid_h5ad") from None
            state["uploads"].append({"id": aid, "name": re.sub(r"[\x00-\x1f\x7f]", "", name), "kind": "h5ad", "size": len(content)})
            state["_uploads"][aid] = {"sha256": hashlib.sha256(content).hexdigest(), "locations": locations,
                                      "declaration_start": len(state["messages"])}
            service.archive_plan(state)
            state["plan"], state["_plan"], state["status"], state["error"] = None, None, "idle", None
            service.message(state, "assistant", "文件已接收。右侧已列出文件结构，请补充产品目标与取样背景，并确认实验类型和计数来源。不确定的项目可以保留未知；系统不会据此判断产品失败。")
            service.save(state)
            return service.public(state)

    @app.get("/api/sessions/{sid}/intake")
    def intake(sid: str, upload_id: str):
        with service.lock:
            state = service.load(sid)
            try:
                return service.intake.public(state, upload_id)
            except (ValueError, OSError, KeyError):
                raise HTTPException(409, "intake_file_unavailable") from None

    @app.post("/api/sessions/{sid}/intake")
    def stage_intake(sid: str, body: IntakeInput):
        with service.lock:
            state = service.load(sid)
            service.busy(state)
            service.controls.stage(state, "intake", body)
            service.save(state)
            return service.public(state)

    @app.post("/api/sessions/{sid}/intake/prepare")
    def prepare_intake(sid: str, body: IntakePrepare):
        with service.lock:
            state = service.load(sid)
            service.busy(state)
            service.intake.prepare(state, body.upload_id)
            return service.public(state)

    @app.post("/api/sessions/{sid}/scientific-inputs/draft")
    def draft_scientific_inputs(sid: str, body: IntakePrepare):
        with service.lock:
            state = service.load(sid)
            service.busy(state)
            try:
                service.scientific_inputs.context(state, body.upload_id)
            except (ValueError, OSError, KeyError):
                raise HTTPException(409, "scientific_intent_or_source_required") from None
            service.schedule(state, "thinking",
                lambda session_id, epoch: service.draft_scientific_inputs(session_id, epoch, body.upload_id))
            return service.public(state)

    @app.post("/api/sessions/{sid}/scientific-inputs/confirm")
    def confirm_scientific_inputs(sid: str, body: DraftIdentity):
        with service.lock:
            state = service.load(sid)
            service.busy(state)
            service.scientific_inputs.confirm(state, body.draft_id, body.draft_digest)
            service.save(state)
            return service.public(state)

    @app.post("/api/sessions/{sid}/report-inputs/prepare")
    def prepare_report_inputs(sid: str, body: ReportPreparation):
        with service.lock:
            state = service.load(sid)
            service.busy(state)
            service.report_inputs.prepare(state, body)
            return service.public(state)

    @app.post("/api/sessions/{sid}/scientific-inputs/revise")
    def revise_scientific_inputs(sid: str, body: DraftRevision):
        with service.lock:
            state = service.load(sid)
            service.busy(state)
            service.scientific_inputs.revise(state, body)
            service.save(state)
            return service.public(state)

    @app.post("/api/sessions/{sid}/clarification/answer")
    def answer_clarification(sid: str, body: AnswerBody):
        with service.lock:
            state = service.load(sid)
            service.busy(state)
            service.clarifications.answer(state, body)
            service.save(state)
            return service.public(state)

    @app.post("/api/sessions/{sid}/clarification/cancel")
    def cancel_clarification(sid: str, body: CardIdentity):
        with service.lock:
            state = service.load(sid)
            service.busy(state)
            service.clarifications.cancel(state, body)
            service.save(state)
            return service.public(state)

    @app.post("/api/sessions/{sid}/clarification/revise")
    def revise_clarification(sid: str, body: CardIdentity):
        with service.lock:
            state = service.load(sid)
            service.busy(state)
            service.clarifications.revise(state, body)
            service.save(state)
            return service.public(state)

    @app.post("/api/sessions/{sid}/stop")
    def stop(sid: str, body: Body):
        with service.lock:
            state = service.load(sid)
            service.controls.fence(state)
            service.save(state)
            return service.public(state)

    @app.post("/api/sessions/{sid}/inputs")
    def inputs(sid: str, body: SourceInput):
        with service.lock:
            state = service.load(sid)
            service.controls.stage(state, "source", body)
            service.save(state)
            return service.public(state)

    @app.post("/api/sessions/{sid}/input-change/confirm")
    def confirm_input_change(sid: str, body: InputChange):
        with service.lock:
            state = service.load(sid)
            service.controls.resolve(state, body.change_id, body.change_digest, commit=True)
            service.save(state)
            return service.public(state)

    @app.post("/api/sessions/{sid}/input-change/discard")
    def discard_input_change(sid: str, body: InputChange):
        with service.lock:
            state = service.load(sid)
            service.controls.resolve(state, body.change_id, body.change_digest, commit=False)
            service.save(state)
            return service.public(state)

    @app.post("/api/sessions/{sid}/input-review/keep")
    def keep_inputs(sid: str, body: Body):
        with service.lock:
            state = service.load(sid)
            service.controls.keep(state)
            service.save(state)
            return service.public(state)

    @app.get("/api/sessions/{sid}/analysis-inputs")
    def analysis_inputs(sid: str):
        with service.lock:
            state = service.load(sid)
            value = service.inputs.public(state)
            if state["status"] not in {"thinking", "running", "stopping"}:
                service.save(state)
            return value

    @app.post("/api/sessions/{sid}/analysis-inputs")
    def select_inputs(sid: str, body: Selection):
        with service.lock:
            state = service.load(sid)
            service.busy(state)
            try:
                service.inputs.selection_reasons(state, body, verify=True)
            except (ValueError, OSError):
                raise HTTPException(422, "invalid_input_selection") from None
            state["_input_selections"][body.tool_id] = body.model_dump(mode="json")
            service.input_changed(state)
            return service.public(state)

    @app.post("/api/sessions/{sid}/analysis-inputs/objects")
    def input_object(sid: str, tool_id: str, mode_id: str, role: str, schema_ref: str,
                     object_version: str, file: UploadFile = File(...)):
        with service.lock:
            state = service.load(sid)
            service.busy(state)
            try:
                service.inputs.add_object(state, tool_id=tool_id, mode_id=mode_id, role=role,
                    schema_ref=schema_ref, object_version=object_version, data=file.file.read(OBJECT_LIMIT + 1))
            except (ValueError, OSError, KeyError) as exc:
                reason = str(exc)
                if not re.fullmatch(r"[a-z_]+(?::[a-z_]+)?", reason):
                    reason = "invalid_scientific_object"
                raise HTTPException(422, reason) from None
            service.input_changed(state)
            return service.public(state)

    @app.post("/api/sessions/{sid}/analysis-inputs/assets")
    def declare_asset(sid: str, body: AssetDeclaration):
        with service.lock:
            state = service.load(sid)
            service.controls.stage(state, "asset", body)
            service.save(state)
            return service.public(state)

    @app.post("/api/sessions/{sid}/prepare-analysis")
    def prepare_analysis(sid: str, body: PrepareAnalysis):
        with service.lock:
            state = service.load(sid)
            service.controls.require_ready(state)
            service.busy(state)
            service.prepare_analysis(state, body.tool_id)
            return service.public(state)

    @app.post("/api/sessions/{sid}/messages")
    def message(sid: str, body: Message):
        with service.lock:
            state = service.load(sid)
            if len(state["messages"]) >= 100:
                raise HTTPException(400, "conversation_limit")
            if body.text.strip().casefold() in {"stop", "cancel", "停止", "取消"}:
                service.message(state, "user", body.text.strip())
                service.controls.fence(state)
                service.save(state)
                return service.public(state)
            service.busy(state)
            if not body.text.strip():
                raise HTTPException(422, "invalid_request")
            service.message(state, "user", body.text.strip())
            if state["title"] == "New analysis":
                state["title"] = private_text(body.text.strip())[:60]
            # Any new user message invalidates an unapproved proposal.
            if state["plan"] and state["plan"]["status"] == "proposed":
                state["plan"], state["_plan"] = None, None
            service.schedule(state, "thinking", service.think)
            return service.public(state)

    @app.post("/api/sessions/{sid}/approve")
    def approve(sid: str, body: Approval):
        with service.lock:
            state = service.load(sid)
            service.controls.require_ready(state)
            service.busy(state)
            if state["status"] != "awaiting_approval" or not state["_plan"]:
                raise HTTPException(409, "approval_not_pending")
            plan = AnalysisPlan.model_validate(state["_plan"])
            if body.plan_id != plan.plan_id or not secrets.compare_digest(body.plan_digest, plan.approval_sha256()):
                raise HTTPException(409, "approval_mismatch")
            if not any(item.disposition.value == "execute" for item in plan.steps):
                raise HTTPException(409, "plan_has_no_executable_steps")
            try:
                service.verify_scientific_plan(state, plan)
            except ValueError:
                raise HTTPException(409, "scientific_plan_invalid_or_stale") from None
            approved = approve_plan(plan, approver_id="private-operator", authority_ref="web-session:" + sid,
                                    approved_at=datetime.now(timezone.utc))
            state["_plan"] = approved.model_dump(mode="json")
            state["plan"]["status"] = "approved"
            service.schedule(state, "running", service.execute)
            return service.public(state)

    @app.get("/api/sessions/{sid}/artifacts/{aid}")
    def artifact(sid: str, aid: str):
        with service.lock:
            state = service.load(sid)
            public, data = service.read_registered_artifact(state, aid)
            inline = public["media_type"] in {"image/png", "image/svg+xml"}
            return Response(data, media_type=public["media_type"],
                            headers={"Content-Disposition": ("inline" if inline else "attachment") + '; filename="' + public["name"] + '"',
                                     "Content-Security-Policy": "default-src 'none'; sandbox", "X-Content-Type-Options": "nosniff"})

    @app.get("/api/sessions/{sid}/artifacts/{aid}/preview")
    def artifact_preview(sid: str, aid: str):
        with service.lock:
            state = service.load(sid)
            try:
                public, data = service.read_registered_artifact(
                    state,
                    aid,
                    limit=PARQUET_STORED_LIMIT,
                )
            except ValueError as exc:
                if str(exc) == "private_file_too_large":
                    raise HTTPException(413, "artifact_preview_too_large") from None
                raise HTTPException(422, "artifact_preview_unavailable") from None
            if not (
                public["kind"] == "table"
                and (
                    public["media_type"] in PARQUET_MEDIA_TYPES
                    or public["name"].lower().endswith(".parquet")
                )
            ):
                raise HTTPException(415, "artifact_preview_unsupported")
        try:
            encoded = parquet_preview(data)
        except ArtifactPreviewTooLarge:
            raise HTTPException(413, "artifact_preview_too_large") from None
        except Exception:
            raise HTTPException(422, "artifact_preview_unavailable") from None
        return Response(
            encoded,
            media_type="application/json",
            headers={"X-Content-Type-Options": "nosniff"},
        )

    @app.get("/api/sessions/{sid}/transcript")
    def transcript(sid: str):
        state = service.load(sid)
        text = "# BRIDGE research conversation\n\n" + "\n\n".join(
            item["role"] + ":\n" + item["content"] for item in state["messages"])
        return Response(text, media_type="text/markdown",
                        headers={"Content-Disposition": 'attachment; filename="conversation.md"'})

    if settings.static_dir is not None:
        app.mount("/", StaticFiles(directory=settings.static_dir, html=True), name="web")
    return app
