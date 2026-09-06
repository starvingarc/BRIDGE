from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from importlib.resources import files
import json
import os
from pathlib import Path
import re
import secrets
import stat
from threading import BoundedSemaphore, RLock
import time
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
from bridge.toolkit.registry import ToolRegistry
from bridge.toolkit.contracts import ToolRequest, ToolRequestV2

CATALOG_LOCK = RLock()

ID = re.compile(r"^[a-f0-9]{32}$")
RETRACTION = re.compile(
    r"不是|并非|不属于|不要|不能|不使用|没有|不做|停止|取消|撤回|撤销"
    r"|\b(?:not|no|don.t|isn.t|aren.t|wasn.t|cancel|stop|retract|revoke)\b",
    re.I,
)
NO_GRAFT_DECLARATION = re.compile(
    r"(?:没有|无|未提供)(?:任何)?(?:移植|graft)(?:数据|证据)?"
    r"|\bno graft (?:data|evidence)(?:,\s*(?:please )?record (?:it as )?not provided)?\b"
    r"|\bgraft data (?:is |was )?not provided\b",
    re.I,
)
COOKIE = "bridge_session"
PUBLIC = ("id", "title", "updated_at", "status", "messages", "uploads", "plan", "artifacts", "error", "plan_history", "capabilities")


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

    def __post_init__(self):
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
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid():
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
        self.cookies: dict[str, float] = {}
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="bridge-web")
        self.capacity = BoundedSemaphore(2)
        self.executor = LocalWorkflowExecutor(SQLiteRunEventStore(self.root / "events.sqlite3"), max_attempts=1)
        for item in self.root.iterdir():
            if ID.fullmatch(item.name):
                state = self.load(item.name)
                if state["status"] in {"running", "thinking", "awaiting_approval"}:
                    state["status"], state["error"] = "failed", "interrupted"
                    if state["plan"] and state["plan"]["status"] in {"proposed", "approved"}:
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
        return state

    def save(self, state):
        state["updated_at"] = now()
        write_file(self.directory(state["id"]) / "session.json",
                   json.dumps(state, ensure_ascii=False).encode())

    def public(self, state):
        state["capabilities"] = self.capabilities(state)
        return {key: state.get(key, [] if key == "plan_history" else None) for key in PUBLIC}

    def message(self, state, role, content):
        state["messages"].append({"id": uid(), "role": role, "content": private_text(content), "created_at": now()})

    def create(self):
        sid = uid()
        ensure_private_directory(self.root / sid)
        state = {"id": sid, "title": "New analysis", "updated_at": now(), "status": "idle",
                 "messages": [], "uploads": [], "plan": None, "artifacts": [], "error": None,
                 "_uploads": {}, "_artifacts": {}, "_plan": None,
                 "plan_history": [], "_plan_history": [], "_tool_runs": []}
        self.message(state, "assistant", "我是 BRIDGE。请描述研究问题并上传 H5AD。当前预览可执行输入 QC；服务端条件就绪后可准备 P0-02 候选细胞状态分析，明确无移植数据时可准备 P0-12。所有运行都需要您确认计划，不提供临床或放行结论。")
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
        if re.search(r"[?？]|并非没有|不是没有|不要|取消|停止|撤回|假设|如果|假如|\b(?:not without|not no|do not|don.t|cancel|stop|if|suppose)\b", text, re.I):
            return False
        return bool(NO_GRAFT_DECLARATION.search(text))

    def independent_retraction(self, state):
        text = state["messages"][-1]["content"]
        if self.no_graft_declared(state):
            text = NO_GRAFT_DECLARATION.sub("", text)
        return bool(RETRACTION.search(text))

    def capabilities(self, state):
        result = []
        selected = state["uploads"][-1]["id"] if state["uploads"] else None
        for spec in self.registry.list():
            reasons = []
            if spec.tool_id == "P0-01":
                reasons = [] if selected else ["product_upload_required"]
                if selected and not self.assay(state, selected):
                    reasons.append("assay_declaration_required")
                if selected and not state.get("_pending_qc") and not any(item["asset_id"] == selected for item in state.get("_bundle", {}).get("assets", [])):
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
                reasons = ["stage_materializer_not_connected"]
            result.append({"tool_id": spec.tool_id, "label": spec.name,
                           "state": "not_connected" if spec.tool_id not in {"P0-01", "P0-02", "P0-12"} else "needs_input" if reasons else "ready",
                           "reason_codes": reasons})
        return result

    def stage_blocked(self, state, reason):
        state["status"], state["error"] = "idle", reason
        self.message(state, "assistant", "当前阶段输入尚未满足：" + reason + "。保留已有工具证据，不会推断缺失事实。")
        self.save(state)

    def prepare_analysis(self, state, tool_id):
        if tool_id not in {"P0-02", "P0-12"}:
            self.stage_blocked(state, "stage_materializer_not_connected")
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
            snapshot = files("bridge.resources").joinpath("knowledge_snapshot.json.gz").read_bytes()
            with self.qc_catalog():
                plan = PlanBuilder(self.registry).build(bundle, output_root=arguments["output_dir"],
                    knowledge_snapshot_ref="sha256:" + hashlib.sha256(snapshot).hexdigest(),
                    requests=[request], include_input_qc=False)
            self.archive_plan(state)
            state["_bundle"] = bundle.model_dump(mode="json")
            state["_plan"] = plan.model_dump(mode="json")
            state["plan"] = {"id": plan.plan_id, "digest": plan.approval_sha256(), "status": "proposed",
                "summary": tool_id + (" 细胞状态候选分析；不保证 V3 或完整生物学证据。" if tool_id == "P0-02" else " 明确未提供移植数据；不运行 graft 表达分析，不回填产品证据。"),
                "steps": [{"id": item.step_id, "tool_id": item.tool_id, "label": spec.name,
                           "status": "pending" if item.disposition.value == "execute" else "blocked",
                           "reason": None if not item.reason_codes else "input_not_eligible"} for item in plan.steps]}
            state["status"], state["error"] = "awaiting_approval", None
            self.message(state, "assistant", "新阶段计划已生成。请检查并单独确认；之前的审批不适用于本阶段。")
            self.save(state)
        except Exception as exc:
            reason = str(exc) if str(exc) in {"upload_integrity_mismatch", "completed_qc_required", "qc_artifacts_missing", "qc_artifact_integrity_mismatch", "qc_declaration_retracted"} else "stage_input_construction_failed"
            self.stage_blocked(state, reason)

    def qc_asset(self, state, selected, *, register=True):
        for receipt in reversed(state.get("_tool_runs", [])):
            if receipt["tool_id"] != "P0-01" or receipt["state"] != "succeeded":
                continue
            directory, _, _ = ensure_private_directory(self.directory(state["id"]) / "receipts")
            raw = read_file(directory / receipt["file"])
            if hashlib.sha256(raw).hexdigest() != receipt["sha256"]:
                raise ValueError("qc_artifact_integrity_mismatch")
            run = json.loads(raw)
            if run["request"]["assets"][0]["asset_id"] != selected:
                continue
            if receipt.get("declaration_start") != state["_uploads"][selected]["declaration_start"]:
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
            if not register:
                return None
            catalog_path = self.root / "qc-catalog.json"
            with CATALOG_LOCK:
                catalog = json.loads(read_file(catalog_path)) if catalog_path.exists() else {"profiles": {}}
                catalog["profiles"][profile["profile_id"]] = {
                    "path": artifacts["qc_readiness_profile.json"]["path"],
                    "sha256": artifacts["qc_readiness_profile.json"]["sha256"],
                    "structured_output_index_path": artifacts["structured_output_index.json"]["path"],
                    "structured_output_index_sha256": artifacts["structured_output_index.json"]["sha256"]}
                write_file(catalog_path, json.dumps(catalog).encode())
            payload = run["request"]["assets"][0]
            payload["metadata"] = {**payload.get("metadata", {}),
                "source_family_id": state["_uploads"][selected]["source_family_id"],
                "qc_profile_ref": profile["profile_id"], "data_view_id": view["view_id"],
                "parent_asset_sha256": view["parent_asset_sha256"]}
            return CaseInputAsset.model_validate(payload)
        raise ValueError("completed_qc_required")

    def busy(self, state):
        if state["status"] in {"thinking", "running"}:
            raise HTTPException(409, "session_busy")

    def schedule(self, state, status, work):
        if not self.capacity.acquire(blocking=False):
            raise HTTPException(429, "worker_busy")
        state["status"], state["error"] = status, None
        self.save(state)
        sid = state["id"]
        def run():
            try:
                work(sid)
            except Exception as exc:
                with self.lock:
                    failed = self.load(sid)
                    failed["status"] = "failed"
                    failed["error"] = ("provider_unavailable" if isinstance(exc, ProviderUnavailable) else "stage_input_construction_failed") if status == "thinking" else "execution_failed"
                    if failed["plan"] and status == "running":
                        failed["plan"]["status"] = "partial" if any(step["status"] in {"succeeded", "partial"} for step in failed["plan"]["steps"]) else "failed"
                        for step in failed["plan"]["steps"]:
                            if step["status"] in {"pending", "running"}:
                                step["status"], step["reason"] = "failed", "execution_failed"
                    self.save(failed)
            finally:
                self.capacity.release()
        self.pool.submit(run)

    def declaration(self, state, upload_id):
        upload = state["_uploads"][upload_id]
        user = next((item["content"] for item in reversed(state["messages"]) if item["role"] == "user"), "")
        if re.search(r"[?？]", user) or RETRACTION.search(user):
            return None
        # Only explicit raw-count/QC intent may bind a matrix, never a model guess.
        if re.search(r"(使用|原始计数|raw counts|/counts|\buse\b)", user, re.I):
            if "layers/counts" in upload["locations"] and re.search(r"counts", user, re.I):
                return "layers/counts"
            if "X" in upload["locations"] and re.search(r"\bX\b", user):
                return "X"
        if (upload.get("suggested") == "layers/counts" and len(state["messages"]) >= 2
                and state["messages"][-2]["id"] == upload.get("question_id")) and re.fullmatch(r"(是|是的|好|好的|确认|yes|ok)[。！! ]*", user, re.I):
            return "layers/counts"
        return None

    def think(self, sid):
        state = self.load(sid)
        if self.independent_retraction(state):
            state.pop("_pending_qc", None)
            # A retraction fences off all earlier declarations conservatively.
            # Both matrix intent and assay must be positively declared again.
            for upload in state["_uploads"].values():
                upload["declaration_start"] = len(state["messages"])
                upload.pop("question_id", None)
            self.save(state)
        if self.no_graft_declared(state):
            state.pop("_pending_qc", None)
        if state.get("_pending_qc") and self.assay(state, state["_pending_qc"]["upload_id"]):
            self.prepare(state, **state["_pending_qc"])
            return
        if state["uploads"]:
            selected = state["uploads"][-1]["id"]
            location = self.declaration(state, selected)
            if location:
                self.prepare(state, selected, location)
                return
        allowed_tools = {spec.tool_id for spec in self.registry.list()}
        allowed_states = {"succeeded", "failed", "partial", "cancelled", "blocked"}
        tool_history = [{"tool_id": item["tool_id"], "state": item["state"]}
                        for item in state.get("_tool_runs", [])[-24:]
                        if item.get("tool_id") in allowed_tools and item.get("state") in allowed_states]
        context = {"status": "idle", "upload_ids": [item["id"] for item in state["uploads"]],
                   "plan_status": state["plan"]["status"] if state["plan"] else None,
                   "capabilities": self.capabilities(state), "tool_execution_history": tool_history,
                   "results_sent_to_model": False}
        try:
            action = converse(self.settings, [{"role": item["role"], "content": private_text(item["content"])}
                                             for item in state["messages"]], context)
        except Exception as exc:
            raise ProviderUnavailable() from exc
        if action.action == "prepare_analysis":
            self.prepare_analysis(state, action.tool_id)
            return
        if action.action == "prepare_qc":
            if action.upload_id not in state["_uploads"]:
                raise ValueError("unknown_upload")
            declaration = self.declaration(state, action.upload_id)
            if declaration != action.matrix_location:
                self.message(state, "assistant", "请明确声明原始计数所在位置：例如“使用 counts 层进行 QC”，或“X 是原始计数，进行 QC”。不会根据文件名推断计数语义。")
            else:
                self.prepare(state, action.upload_id, declaration)
                return
        else:
            self.message(state, "assistant", action.text)
        state["status"] = "idle"
        self.save(state)

    def assay(self, state, upload_id):
        start = state["_uploads"][upload_id]["declaration_start"]
        for item in reversed(state["messages"][start:]):
            if item["role"] == "user":
                if RETRACTION.search(item["content"]):
                    return None
                if re.search(r"[?？]", item["content"]):
                    continue
                matches = re.findall(r"(?<![A-Za-z])(scRNA-seq|snRNA-seq)(?![A-Za-z])", item["content"])
                if len(set(matches)) == 1:
                    return matches[0]
        return None

    def prepare(self, state, upload_id, location):
        assay = self.assay(state, upload_id)
        if assay is None:
            state["_pending_qc"] = {"upload_id": upload_id, "location": location}
            state["status"] = "idle"
            self.message(state, "assistant", "计数位置声明已记录。还需要您明确实验类型：scRNA-seq（单细胞）还是 snRNA-seq（单核）？不会根据表达数据自动推断。")
            self.save(state)
            return
        state.pop("_pending_qc", None)
        upload = state["_uploads"][upload_id]
        if location not in upload["locations"]:
            raise ValueError("matrix_not_registered")
        directory, _, _ = ensure_private_directory(self.directory(state["id"]) / "uploads")
        path = directory / (upload_id + ".h5ad")
        data = read_file(path, self.settings.upload_limit)
        if hashlib.sha256(data).hexdigest() != upload["sha256"]:
            raise ValueError("upload_integrity_mismatch")
        asset = CaseInputAsset(asset_id=upload_id, path=path, format="h5ad",
                               input_level="count_ready", checksum=upload["sha256"],
                               matrix_location=location, matrix_semantics="raw_counts", assay=assay)
        bundle = CaseInputBundle(bundle_id=uid(), version="1", assets=[asset])
        snapshot = files("bridge.resources").joinpath("knowledge_snapshot.json.gz").read_bytes()
        plan = PlanBuilder().build(bundle, output_root=self.directory(state["id"]) / "runs",
                                   knowledge_snapshot_ref="sha256:" + hashlib.sha256(snapshot).hexdigest())
        self.archive_plan(state)
        state["_bundle"] = bundle.model_dump(mode="json")
        state["_plan"] = plan.model_dump(mode="json")
        state["plan"] = {"id": plan.plan_id, "digest": plan.approval_sha256(), "status": "proposed",
                         "summary": "P0-01 输入 QC；实验类型：" + assay + "；原始计数位置：" + location + "。仅研究性候选结果；未声明 sample/capture 元数据，不推断生物学重复。",
                         "steps": [{"id": item.step_id, "tool_id": item.tool_id, "label": "输入质量与可分析性",
                                    "status": "pending" if item.disposition.value == "execute" else "skipped",
                                    "reason": None if not item.reason_codes else "input_not_eligible"} for item in plan.steps]}
        state["status"] = "awaiting_approval"
        self.message(state, "assistant", "已根据您的计数声明生成输入 QC 计划。请检查并确认；确认前不会运行。结果不代表科学方法已验证。")
        self.save(state)

    def execute(self, sid):
        with self.qc_catalog():
            self._execute(sid)

    def _execute(self, sid):
        state = self.load(sid)
        plan = AnalysisPlan.model_validate(state["_plan"])
        # Verify all registered input bytes immediately before any SDK execution.
        for upload_id, upload in state["_uploads"].items():
            directory, _, _ = ensure_private_directory(self.directory(sid) / "uploads")
            path = directory / (upload_id + ".h5ad")
            if hashlib.sha256(read_file(path, self.settings.upload_limit)).hexdigest() != upload["sha256"]:
                raise ValueError("upload_integrity_mismatch")
        run_id = self.executor.submit(plan)
        state["_run_id"] = run_id
        self.save(state)
        pipeline = ToolExecutionPipeline(ToolExecutionScope.from_plan(plan))
        while claim := self.executor.claim_step(run_id):
            for item in state["plan"]["steps"]:
                if item["id"] == claim.step_id:
                    item["status"] = "running"
            self.save(state)
            outcome = self.executor.execute_claim(claim, pipeline)
            receipt_id = uid()
            receipt = outcome.model_dump_json().encode()
            write_file(self.directory(sid) / "receipts" / (receipt_id + ".json"), receipt)
            state["_tool_runs"].append({"file": receipt_id + ".json", "sha256": hashlib.sha256(receipt).hexdigest(),
                                       "tool_id": outcome.request.tool_id, "state": outcome.execution_state.value,
                                       "plan_id": plan.plan_id,
                                       "declaration_start": state["_uploads"].get(outcome.request.assets[0].asset_id, {}).get("declaration_start") if outcome.request.assets else None})
            self.save(state)
            for item in state["plan"]["steps"]:
                if item["id"] == claim.step_id:
                    item["status"] = outcome.execution_state.value if outcome.execution_state.value in {"succeeded", "partial", "cancelled", "blocked"} else "failed"
                    item["reason"] = None if item["status"] == "succeeded" else "tool_not_successful"
            self.save(state)
            self.register_artifacts(state, outcome)
        snapshot = self.executor.get_status(run_id)
        success = snapshot.status.value == "succeeded"
        state["status"] = "idle" if success else "failed"
        state["error"] = None if success else "execution_incomplete"
        actual = {item["status"] for item in state["plan"]["steps"]}
        state["plan"]["status"] = "completed" if success else ("partial" if "partial" in actual or "succeeded" in actual else "cancelled" if "cancelled" in actual else "failed")
        self.message(state, "assistant", "工具运行已结束。请在结果面板查看工具生成的图表和证据。未声明的采样或捕获信息不会被补造；运行完成不代表科学验证通过，不能用于临床或放行结论。" if success else "工具运行未完整完成。未将缺失或失败证据解释为产品失败。")
        self.save(state)

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
                    limit = settings.upload_limit + 65536 if request.url.path.endswith("/uploads") else 32768
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
            state["_uploads"][aid] = {"sha256": hashlib.sha256(content).hexdigest(), "locations": locations, "declaration_start": len(state["messages"]),
                                      "suggested": "layers/counts" if "layers/counts" in locations else None}
            state.pop("_pending_qc", None)
            service.archive_plan(state)
            state["plan"], state["_plan"], state["status"], state["error"] = None, None, "idle", None
            service.message(state, "assistant", "文件已接收。检测到 counts 层：是否将它声明为原始计数并用于 QC？请回复“是，使用 counts 层进行 QC”。" if "layers/counts" in locations else "文件已接收。请声明原始计数位置，例如“X 是原始计数，进行 QC”。若 X 已标准化，请勿将它声明为原始计数。")
            state["_uploads"][aid]["question_id"] = state["messages"][-1]["id"]
            service.save(state)
            return service.public(state)

    @app.post("/api/sessions/{sid}/inputs")
    def inputs(sid: str, body: SourceInput):
        with service.lock:
            state = service.load(sid)
            service.busy(state)
            if body.upload_id not in state["_uploads"]:
                raise HTTPException(404, "upload_not_found")
            state["_uploads"][body.upload_id]["source_family_id"] = body.source_family_id
            for upload in state["uploads"]:
                if upload["id"] == body.upload_id:
                    upload["source_family_id"] = body.source_family_id
            if state["plan"] and state["plan"]["status"] == "proposed":
                state["plan"], state["_plan"], state["status"] = None, None, "idle"
            service.save(state)
            return service.public(state)

    @app.post("/api/sessions/{sid}/messages")
    def message(sid: str, body: Message):
        with service.lock:
            state = service.load(sid)
            service.busy(state)
            if len(state["messages"]) >= 100:
                raise HTTPException(400, "conversation_limit")
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
            service.busy(state)
            if state["status"] != "awaiting_approval" or not state["_plan"]:
                raise HTTPException(409, "approval_not_pending")
            plan = AnalysisPlan.model_validate(state["_plan"])
            if body.plan_id != plan.plan_id or not secrets.compare_digest(body.plan_digest, plan.approval_sha256()):
                raise HTTPException(409, "approval_mismatch")
            if not any(item.disposition.value == "execute" for item in plan.steps):
                raise HTTPException(409, "plan_has_no_executable_steps")
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
            if not ID.fullmatch(aid) or aid not in state["_artifacts"]:
                raise HTTPException(404, "not_found")
            record = state["_artifacts"][aid]
            path = service.directory(sid) / "artifacts" / record["file"]
            if path.parent.is_symlink():
                raise HTTPException(404, "not_found")
            data = read_file(path, 128 * 1024 * 1024)
            if hashlib.sha256(data).hexdigest() != record["sha256"]:
                raise HTTPException(409, "artifact_integrity_mismatch")
            public = next(item for item in state["artifacts"] if item["id"] == aid)
            inline = public["media_type"] in {"image/png", "image/svg+xml"}
            return Response(data, media_type=public["media_type"],
                            headers={"Content-Disposition": ("inline" if inline else "attachment") + '; filename="' + public["name"] + '"',
                                     "Content-Security-Policy": "default-src 'none'; sandbox", "X-Content-Type-Options": "nosniff"})

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
