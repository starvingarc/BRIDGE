from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from urllib.parse import urlsplit
import json
import os
from pathlib import Path
import stat
from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict

from bridge.storage.private_paths import ensure_private_directory


RuntimeEnvironment = Literal["development", "acceptance", "production"]
RUNTIME_ENVIRONMENTS = frozenset({"development", "acceptance", "production"})
STORAGE_BINDING_FILE = ".bridge-runtime-environment.json"
STORAGE_LOCK_FILE = ".bridge-start.lock"


class StorageEnvironmentBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    object_version: Literal["1.0.0", "2.0.0"] = "1.0.0"
    runtime_environment: RuntimeEnvironment


class DiagnosticRuntime(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    environment: RuntimeEnvironment
    package_version: str


class DiagnosticSession(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str
    internal_error_code: str | None
    control_epoch: int


class DiagnosticPlanStep(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    step_id: str
    tool_id: str
    state: str


class DiagnosticPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    plan_id: str
    state: str
    steps: list[DiagnosticPlanStep]


class DiagnosticModelTurn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    number: int
    state: str
    provider_error_code: str | None = None


class DiagnosticAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scope_id: str
    state: str
    stop_reason: str | None
    max_tool_runs: int
    tool_runs_used: int
    max_model_turns: int
    model_turns_used: int
    model_turns: list[DiagnosticModelTurn]


class DiagnosticToolRun(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tool_id: str
    state: str
    plan_id: str | None


DegradationCode = Literal[
    "interpretation_graph_binding_unavailable",
    "report_context_producer_identity_mismatch",
    "graph_display_unavailable",
]
DEGRADATION_CODES = frozenset(get_args(DegradationCode))


class DiagnosticDegradation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: DegradationCode
    count: int


def record_degradation(state: dict, code: str) -> None:
    """Count a failed server attempt; caller owns the session lock and save."""
    if code not in DEGRADATION_CODES:
        return
    counts = state.setdefault("_degradation_counts", {})
    previous = counts.get(code, 0)
    counts[code] = (previous if type(previous) is int and previous > 0 else 0) + 1


class SessionDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    runtime: DiagnosticRuntime
    session: DiagnosticSession
    plan: DiagnosticPlan | None
    assessment: DiagnosticAssessment | None
    tool_runs: list[DiagnosticToolRun]
    degradations: list[DiagnosticDegradation]


def build_session_diagnostics(settings, state: dict) -> SessionDiagnostics:
    """Return a bounded operational projection with no research content or paths."""
    from bridge import __version__

    plan_value = state.get("plan")
    plan = None
    if isinstance(plan_value, dict):
        plan = DiagnosticPlan(
            plan_id=str(plan_value.get("id") or plan_value.get("plan_id") or "unknown"),
            state=str(plan_value.get("status") or plan_value.get("state") or "unknown"),
            steps=[
                DiagnosticPlanStep(
                    step_id=str(row.get("id") or row.get("step_id") or "unknown"),
                    tool_id=str(row.get("tool_id") or "unknown"),
                    state=str(row.get("status") or row.get("state") or "unknown"),
                )
                for row in plan_value.get("steps", [])
                if isinstance(row, dict)
            ],
        )

    assessment_value = state.get("_assessment")
    assessment = None
    if isinstance(assessment_value, dict):
        scope = assessment_value.get("scope")
        scope = scope if isinstance(scope, dict) else {}
        assessment = DiagnosticAssessment(
            scope_id=str(scope.get("scope_id") or "unknown"),
            state=str(assessment_value.get("status") or "unknown"),
            stop_reason=(
                str(assessment_value["stop_reason"])
                if assessment_value.get("stop_reason") is not None
                else None
            ),
            max_tool_runs=int(scope.get("max_tool_runs") or 0),
            tool_runs_used=int(assessment_value.get("tool_runs_used") or 0),
            max_model_turns=int(scope.get("max_model_turns") or 0),
            model_turns_used=int(assessment_value.get("model_turns_used") or 0),
            model_turns=[
                DiagnosticModelTurn(
                    number=int(row.get("number") or 0),
                    state=str(row.get("state") or "unknown"),
                    provider_error_code=(
                        str(row["provider_error_code"])
                        if row.get("provider_error_code") is not None
                        else None
                    ),
                )
                for row in assessment_value.get("model_turns", [])
                if isinstance(row, dict)
            ],
        )

    return SessionDiagnostics(
        runtime=DiagnosticRuntime(
            environment=settings.runtime_environment,
            package_version=__version__,
        ),
        session=DiagnosticSession(
            status=str(state.get("status") or "unknown"),
            internal_error_code=(
                str(state["error"]) if state.get("error") is not None else None
            ),
            control_epoch=int(state.get("_control_epoch") or 0),
        ),
        plan=plan,
        assessment=assessment,
        degradations=[
            DiagnosticDegradation(code=code, count=count)
            for code in sorted(DEGRADATION_CODES)
            if type(count := state.get("_degradation_counts", {}).get(code)) is int and count > 0
        ],
        tool_runs=[
            DiagnosticToolRun(
                tool_id=str(row.get("tool_id") or "unknown"),
                state=str(row.get("state") or "unknown"),
                plan_id=(str(row["plan_id"]) if row.get("plan_id") is not None else None),
            )
            for row in state.get("_tool_runs", [])
            if isinstance(row, dict)
        ],
    )


def validate_runtime_configuration(
    environment: RuntimeEnvironment,
    diagnostics_enabled: bool,
) -> None:
    if (
        environment not in RUNTIME_ENVIRONMENTS
        or type(diagnostics_enabled) is not bool
        or diagnostics_enabled and environment != "development"
    ):
        raise ValueError("invalid_server_configuration")


def _read_binding(path: Path) -> StorageEnvironmentBinding:
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as exc:
        raise ValueError("storage_environment_binding_invalid") from exc
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.geteuid()
            or info.st_mode & 0o077
            or info.st_size > 4096
        ):
            raise ValueError("storage_environment_binding_invalid")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            payload = json.load(stream)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        if isinstance(exc, ValueError) and str(exc) == "storage_environment_binding_invalid":
            raise
        raise ValueError("storage_environment_binding_invalid") from exc
    finally:
        os.close(fd)
    try:
        return StorageEnvironmentBinding.model_validate(payload)
    except ValueError as exc:
        raise ValueError("storage_environment_binding_invalid") from exc


def _write_binding(path: Path, binding: StorageEnvironmentBinding) -> None:
    encoded = (
        json.dumps(
            binding.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()
    try:
        fd = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
        )
    except FileExistsError:
        return
    try:
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(fd)


def bind_storage_environment(
    root: Path,
    environment: RuntimeEnvironment,
    *,
    allow_existing_unbound: bool = False,
    object_version: Literal["1.0.0", "2.0.0"] | None = None,
) -> StorageEnvironmentBinding:
    validate_runtime_configuration(environment, False)
    root, _, _ = ensure_private_directory(root)
    marker = root / STORAGE_BINDING_FILE
    if marker.exists() or marker.is_symlink():
        binding = _read_binding(marker)
        if binding.runtime_environment != environment:
            raise ValueError("storage_environment_mismatch")
        if object_version is not None and binding.object_version != object_version:
            raise ValueError("storage_environment_binding_invalid")
        return binding

    existing = {
        item.name
        for item in root.iterdir()
        if item.name not in {STORAGE_BINDING_FILE, STORAGE_LOCK_FILE}
    }
    if existing and not allow_existing_unbound:
        raise ValueError("storage_environment_binding_required")

    requested = StorageEnvironmentBinding(runtime_environment=environment, object_version=object_version or "1.0.0")
    _write_binding(marker, requested)
    binding = _read_binding(marker)
    if binding.runtime_environment != environment:
        raise ValueError("storage_environment_mismatch")
    return binding


def session_cookie_name(environment: RuntimeEnvironment) -> str:
    validate_runtime_configuration(environment, False)
    return f"bridge_{environment}_accounts_session"


GIB = 1024 * 1024 * 1024


MAX_CONFIGURED_FILE_BYTES = 16 * GIB


MAX_CONFIGURED_DATASET_ELEMENTS = 1_000_000_000


@dataclass(frozen=True)
class Settings:
    storage_root: Path
    model_base_url: str
    model: str
    model_api_key: str
    origin: str = "http://127.0.0.1:8765"
    static_dir: Path | None = None
    max_upload_bytes: int = 4 * GIB
    max_h5ad_logical_bytes: int = 4 * GIB
    max_h5ad_dataset_elements: int = 100_000_000
    model_endpoint_restricted: bool = False
    model_configuration_id: str = ""
    model_provider_id: str = "default"
    model_effort: str | None = None
    personal_model_allowlist: tuple[str, ...] = ()
    user_task_limit: int = 1
    user_storage_bytes: int = 20 * GIB
    total_storage_bytes: int = 100 * GIB
    public_origin: str | None = None
    trusted_proxy_ips: tuple[str, ...] = ("127.0.0.1",)
    cookie_ttl: int = 12 * 3600
    cell_state_measurement_spec_ref: str | None = None
    cell_state_candidate_runtime_ref: str | None = None
    share_result_summaries: bool = False
    model_action_protocol: Literal["json", "deepseek_tools"] = "json"
    protocol_compiler_python: str | None = None
    runtime_environment: RuntimeEnvironment = "production"
    diagnostics_enabled: bool = False
    spatial_reference_manifest_path: Path | None = None
    workbench_tree_path: Path | None = None
    quick_atlas_catalog_path: Path | None = None

    def __post_init__(self):
        validate_runtime_configuration(
            self.runtime_environment,
            self.diagnostics_enabled,
        )
        if (
            type(self.share_result_summaries) is not bool
            or self.model_action_protocol not in {"json", "deepseek_tools"}
            or type(self.max_upload_bytes) is not int
            or not 1 <= self.max_upload_bytes <= MAX_CONFIGURED_FILE_BYTES
            or type(self.max_h5ad_logical_bytes) is not int
            or not 1 <= self.max_h5ad_logical_bytes <= MAX_CONFIGURED_FILE_BYTES
            or type(self.max_h5ad_dataset_elements) is not int
            or not 1 <= self.max_h5ad_dataset_elements <= MAX_CONFIGURED_DATASET_ELEMENTS
        ):
            raise ValueError("invalid_server_configuration")
        if (type(self.user_task_limit) is not int or not 1 <= self.user_task_limit <= 2
                or any(type(value) is not int or not 1 <= value <= 1024 * GIB
                       for value in (self.user_storage_bytes, self.total_storage_bytes))
                or self.user_storage_bytes > self.total_storage_bytes):
            raise ValueError("invalid_server_configuration")
        if self.public_origin is not None:
            public = urlsplit(self.public_origin)
            if (public.scheme != "https" or not public.hostname or public.path
                    or public.username or public.password or public.query or public.fragment):
                raise ValueError("invalid_server_configuration")
            try:
                if public.port == 0 or not self.trusted_proxy_ips or any(
                    not ipaddress.ip_address(ip).is_loopback for ip in self.trusted_proxy_ips
                ):
                    raise ValueError
            except ValueError:
                raise ValueError("invalid_server_configuration") from None
            object.__setattr__(self, "origin", self.public_origin)
        for endpoint in self.personal_model_allowlist:
            from .model_transport import validate_endpoint
            validate_endpoint(endpoint, self.personal_model_allowlist)
        for url in (self.origin, *([self.model_base_url] if self.model_base_url else [])):
            parts = urlsplit(url)
            try:
                parts.port
            except ValueError:
                raise ValueError("invalid_server_configuration") from None
            if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
                raise ValueError("invalid_server_configuration")

    @property
    def upload_limit(self) -> int:
        """Compatibility for existing bounded artifact paths; new code uses the public contract name."""
        return self.max_upload_bytes


def configured_integer(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    if not raw.isdigit():
        raise ValueError("invalid_server_configuration")
    return int(raw)


def settings_from_environment() -> Settings:
    share_result_summaries = os.environ.get("BRIDGE_WEB_SHARE_RESULT_SUMMARIES")
    if share_result_summaries not in {None, "0", "1"}:
        raise ValueError("invalid_server_configuration")
    diagnostics = os.environ.get("BRIDGE_WEB_DIAGNOSTICS")
    if diagnostics not in {None, "0", "1"}:
        raise ValueError("invalid_server_configuration")
    if any(name in os.environ for name in ("BRIDGE_WEB_TOKEN", "BRIDGE_WEB_MULTI_USER")):
        raise ValueError("retired_auth_configuration")
    runtime_environment = os.environ.get("BRIDGE_RUNTIME_ENV", "production")
    return Settings(
        storage_root=Path(os.environ["BRIDGE_WEB_STORAGE"]),
        public_origin=os.environ.get("BRIDGE_WEB_PUBLIC_ORIGIN") or None,
        trusted_proxy_ips=tuple(value.strip() for value in os.environ.get("BRIDGE_WEB_TRUSTED_PROXY_IPS", "127.0.0.1").split(",")),
        personal_model_allowlist=tuple(value.strip().rstrip("/") for value in os.environ.get("BRIDGE_WEB_PERSONAL_MODEL_ALLOWLIST", "").split(",") if value.strip()),
        user_task_limit=configured_integer("BRIDGE_WEB_USER_TASK_LIMIT", 1),
        user_storage_bytes=configured_integer("BRIDGE_WEB_USER_STORAGE_BYTES", 20 * GIB),
        total_storage_bytes=configured_integer("BRIDGE_WEB_TOTAL_STORAGE_BYTES", 100 * GIB),
        model_base_url=os.environ.get("BRIDGE_WEB_MODEL_BASE_URL", ""),
        model=os.environ.get("BRIDGE_WEB_MODEL", ""),
        model_api_key=os.environ.get("BRIDGE_WEB_MODEL_API_KEY", ""),
        origin=os.environ.get("BRIDGE_WEB_ORIGIN", "http://127.0.0.1:8765"),
        max_upload_bytes=configured_integer("BRIDGE_WEB_MAX_UPLOAD_BYTES", 4 * 1024 * 1024 * 1024),
        max_h5ad_logical_bytes=configured_integer(
            "BRIDGE_WEB_MAX_H5AD_LOGICAL_BYTES",
            4 * 1024 * 1024 * 1024,
        ),
        max_h5ad_dataset_elements=configured_integer(
            "BRIDGE_WEB_MAX_H5AD_DATASET_ELEMENTS",
            100_000_000,
        ),
        cell_state_measurement_spec_ref=os.environ.get("BRIDGE_WEB_CELL_STATE_MEASUREMENT_SPEC_REF") or None,
        cell_state_candidate_runtime_ref=os.environ.get("BRIDGE_WEB_CELL_STATE_CANDIDATE_RUNTIME_REF") or None,
        static_dir=Path(os.environ["BRIDGE_WEB_STATIC_DIR"]) if os.environ.get("BRIDGE_WEB_STATIC_DIR") else None,
        share_result_summaries=share_result_summaries == "1",
        protocol_compiler_python=os.environ.get("BRIDGE_WEB_PROTOCOL_COMPILER_PYTHON") or None,
        model_action_protocol=os.environ.get(
            "BRIDGE_WEB_MODEL_ACTION_PROTOCOL",
            "json",
        ),
        runtime_environment=runtime_environment,
        diagnostics_enabled=diagnostics == "1",
        spatial_reference_manifest_path=(Path(os.environ["BRIDGE_WEB_SPATIAL_REFERENCE_MANIFEST"])
            if os.environ.get("BRIDGE_WEB_SPATIAL_REFERENCE_MANIFEST") else None),
        quick_atlas_catalog_path=(Path(os.environ["BRIDGE_WEB_QUICK_ATLAS_CATALOG"])
            if os.environ.get("BRIDGE_WEB_QUICK_ATLAS_CATALOG") else None),
        workbench_tree_path=(Path(os.environ["BRIDGE_WEB_WORKBENCH_TREE"])
            if os.environ.get("BRIDGE_WEB_WORKBENCH_TREE") else None),
    )
