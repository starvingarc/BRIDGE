from __future__ import annotations

import json
import os
import re
import secrets
from datetime import datetime, timezone
from urllib.parse import urlsplit
from typing import Literal

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from bridge.domain import AnalysisPlan, approve_plan
from bridge.storage.private_paths import ensure_private_directory

from . import intake_autofill, protocol_formalization
from .artifacts import (
    PARQUET_MEDIA_TYPES,
    PARQUET_STORED_LIMIT,
    ArtifactPreviewTooLarge,
    parquet_preview,
)
from .assessment import ScopeIdentity, ScopeProposal
from .clarification import AnswerBody, CardIdentity
from .conditional_inputs import ConditionalDecision, ConditionalProposal
from .inputs import OBJECT_LIMIT, AssetDeclaration, PrepareAnalysis, Selection
from .intake import IntakeInput, IntakePrepare
from .intake_autofill import IntakeAnswer
from .model_settings import ModelSettingsInput, ConversationModelSelection, ModelSelectionError
from .presentation import derive_results_state, public_error, MODEL_SELECTION_ERRORS
from .protocol_formalization import (
    ProtocolAnswer,
    ProtocolEdit,
    ProtocolRequest,
    ProtocolReview,
)
from .provider import MESSAGE_SOURCES, project_public_messages
from .report_inputs import ReportPreparation
from .runtime import (
    Settings,
    build_session_diagnostics,
    session_cookie_name,
)
from .scientific_inputs import DraftIdentity, DraftRevision
from .sessions import (
    UploadLimitExceeded,
    inspect_h5ad,
    open_private_file,
    private_text,
    stream_upload,
    uid,
)


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SessionCreation(Body):
    research_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")


class SessionArchive(Body):
    archived: bool = Field(strict=True)


class ModelSource(Body):
    source: Literal["default", "personal"]


class Message(Body):
    text: str = Field(min_length=1, max_length=8000)
    sample_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")


class SourceInput(Body):
    upload_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    source_family_id: str = Field(
        min_length=1, max_length=160, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$"
    )


class InputChange(Body):
    change_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    change_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


class Approval(Body):
    plan_id: str = Field(max_length=100)
    plan_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


UPLOAD_REQUEST_OVERHEAD_BYTES = 65536


def upload_limit_response(settings: Settings) -> JSONResponse:
    return JSONResponse(
        {
            "detail": "request_too_large",
            "user_message": (
                f"文件超过当前上传上限（{settings.max_upload_bytes} 字节）。"
                "请选择较小文件或联系管理员调整服务器限制。"
            ),
            "max_upload_bytes": settings.max_upload_bytes,
        },
        status_code=413,
    )


def h5ad_resource_limit_response(settings: Settings, reason: str) -> JSONResponse:
    return JSONResponse(
        {
            "detail": "h5ad_resource_limit",
            "reason": reason,
            "user_message": "H5AD 的解压后数据规模超过当前服务器安全上限。请使用较小文件或联系管理员调整限制。",
            "max_h5ad_logical_bytes": settings.max_h5ad_logical_bytes,
            "max_h5ad_dataset_elements": settings.max_h5ad_dataset_elements,
        },
        status_code=413,
    )


def install_http(app: FastAPI, service, settings: Settings) -> None:
    from .auth_http import install_auth
    install_auth(app, service, settings)
    from .model_http import install_models
    install_models(app, service.model_configuration)
    from .research_http import install_research_http
    install_research_http(app, service, settings)
    from .research_object_http import OBJECT_ERROR_MESSAGES, install_research_object_http
    install_research_object_http(app, service.research_objects, service.model_configuration, service.atlas_mapping)
    from .sample_analyses import ERRORS, install_sample_analysis_http
    OBJECT_ERROR_MESSAGES.update(ERRORS)
    install_sample_analysis_http(app, service.sample_analyses)
    from .analysis_cohorts import ERRORS as COHORT_ERRORS, install_analysis_cohort_http
    OBJECT_ERROR_MESSAGES.update(COHORT_ERRORS)
    install_analysis_cohort_http(app, service.analysis_cohorts)
    from .cohort_comparison import ERRORS as COMPARISON_ERRORS, install_cohort_comparison_http
    OBJECT_ERROR_MESSAGES.update(COMPARISON_ERRORS)
    install_cohort_comparison_http(app, service.cohort_comparisons)
    from .workbench_http import install_workbench_http
    install_workbench_http(app, service)
    cookie_name = session_cookie_name(settings.runtime_environment)

    @app.get("/api/model-settings")
    def model_settings():
        return service.model_configuration.view()

    @app.put("/api/model-settings")
    def save_model_settings(body: ModelSettingsInput):
        try:
            return service.model_configuration.save(body)
        except ValueError:
            raise HTTPException(422, "invalid_request") from None

    @app.post("/api/model-settings/test")
    def test_model_settings(body: ModelSettingsInput):
        try:
            return service.model_configuration.test(body)
        except ValueError:
            raise HTTPException(422, "invalid_request") from None


    @app.get("/api/me/model-settings")
    def personal_model_settings(request: Request):
        try:
            return service.model_configuration.view_for(request.state.principal.id)
        except ValueError:
            raise HTTPException(422, "personal_model_configuration_invalid") from None

    @app.put("/api/me/model-settings")
    def save_personal_model_settings(request: Request, body: ModelSettingsInput):
        try:
            return service.model_configuration.save_for(request.state.principal.id, body)
        except ValueError:
            raise HTTPException(422, "invalid_model_configuration") from None

    @app.post("/api/me/model-settings/select")
    def select_personal_model(request: Request, body: ModelSource):
        try:
            return service.model_configuration.select_for(request.state.principal.id, body.source)
        except ValueError:
            raise HTTPException(422, "personal_model_required") from None

    @app.delete("/api/me/model-settings")
    def delete_personal_model(request: Request):
        return service.model_configuration.delete_for(request.state.principal.id)

    @app.post("/api/me/model-settings/test")
    def test_personal_model(request: Request, body: ModelSettingsInput):
        try:
            return service.model_configuration.test_for(request.state.principal.id, body)
        except ValueError:
            raise HTTPException(422, "invalid_model_configuration") from None

    def request_results_state(request: Request):
        match = re.match(r"^/api/sessions/([a-f0-9]{32})(?:/|$)", request.url.path)
        if match is None:
            return "unknown"
        try:
            with service.lock:
                principal = getattr(request.state, "principal", None)
                if principal is None:
                    return "unknown"
                service.access.authorize(principal, match.group(1))
                state = service.load(match.group(1))
                return derive_results_state({**state, "artifacts": service.artifacts.public(state)})
        except (HTTPException, OSError, ValueError, KeyError, json.JSONDecodeError):
            return "unknown"

    def safe_error_response(
        internal_code,
        status_code,
        *,
        request: Request | None = None,
        inspect_results: bool = False,
    ):
        code = internal_code if isinstance(internal_code, str) else "request_failed"
        results_state = (
            request_results_state(request) if inspect_results and request is not None else "unknown"
        )
        payload = public_error(code, results_state=results_state).model_dump(mode="json")
        if code in OBJECT_ERROR_MESSAGES:
            payload.update(detail=code, user_message=OBJECT_ERROR_MESSAGES[code])
        elif code in MODEL_SELECTION_ERRORS:
            payload["detail"] = code
        elif code == "invalid_request" and request is not None and re.match(
            r"^/api/researches/[^/]+/(workbench|protocols|runs|samples|assessments|actions|leads)(/|$)",
            request.url.path,
        ):
            payload["detail"] = code
        response = JSONResponse(payload, status_code=status_code)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(HTTPException)
    async def http_failure(request, exc):
        return safe_error_response(
            exc.detail,
            exc.status_code,
            request=request,
            inspect_results=True,
        )

    @app.exception_handler(RequestValidationError)
    async def invalid(request, exc):
        return safe_error_response(
            "invalid_request",
            422,
            request=request,
            inspect_results=True,
        )

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        if settings.public_origin:
            import ipaddress
            try:
                if (request.client is None or request.client.host not in settings.trusted_proxy_ips
                        or request.headers.get("host") != urlsplit(settings.origin).netloc
                        or request.headers.get("x-forwarded-proto") != "https"
                        or request.headers.get("forwarded")
                        or request.headers.get("x-forwarded-host", urlsplit(settings.origin).netloc) != urlsplit(settings.origin).netloc):
                    raise ValueError
                client_ip = str(ipaddress.ip_address(request.headers.get("x-forwarded-for", "")))
                request.scope["client"] = (client_ip, 0)
                request.scope["scheme"] = "https"
            except ValueError:
                return safe_error_response("invalid_proxy", 403)
        if request.url.path.startswith("/api/"):
            upload_request = request.url.path.endswith("/uploads")
            exceeded = False
            reservation = None
            try:
                received = 0
                if request.headers.get("host") != urlsplit(settings.origin).netloc:
                    return safe_error_response("invalid_host", 403)
                if request.method not in {"GET", "HEAD", "OPTIONS"}:
                    if request.headers.get("origin") != settings.origin:
                        return safe_error_response("origin_required", 403)
                    length = request.headers.get("content-length")
                    limit = (
                        settings.max_upload_bytes + UPLOAD_REQUEST_OVERHEAD_BYTES
                        if upload_request
                        else (
                            intake_autofill.PROTOCOL_LIMIT + 65536
                            if request.url.path.endswith("/intake/protocols")
                            else (
                                OBJECT_LIMIT + 65536
                                if request.url.path.endswith("/analysis-inputs/objects")
                                else (
                                    65536
                                    if request.url.path.endswith("/analysis-inputs/assets")
                                    else (
                                        6 * protocol_formalization.BPL_LIMIT + 32768
                                        if request.url.path.endswith("/intake/protocols/edit")
                                        else 32768
                                    )
                                )
                            )
                        )
                    )
                    if length is None or not length.isdigit() or int(length) > limit:
                        return (
                            upload_limit_response(settings)
                            if upload_request
                            else safe_error_response("request_too_large", 413)
                        )
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
                public_paths = {"/api/health", "/api/login", "/api/auth/config", "/api/register"}
                if request.url.path not in public_paths:
                    token = request.cookies.get(cookie_name, "")
                    principal = service.accounts.resolve_login(token)
                    if principal is None:
                        return safe_error_response("authentication_required", 401)
                    request.state.principal = principal
                    if principal.must_change_password and request.url.path not in {"/api/me", "/api/me/password", "/api/logout"}:
                        return safe_error_response("password_change_required", 403)

                    path = request.url.path
                    is_admin = path.startswith("/api/admin/")
                    if is_admin:
                        if principal.role != "admin":
                            raise HTTPException(403, "administrator_required")
                        match = re.match(r"^/api/admin/sessions/([^/]+)(?:/|$)", path)
                        sid = match.group(1) if match else None
                        request.state.admin_audit = (principal.id, None, sid, request.method + " " + path)
                        if sid:
                            if request.method != "GET":
                                raise HTTPException(403, "administrator_read_only")
                            with service.lock:
                                service.access.authorize(principal, sid, admin_read=True)
                                owner = service.sessions.owner(sid)
                                request.state.admin_read = True
                            request.state.admin_audit = (principal.id, owner, sid, request.method + " " + path)
                    else:
                        research_match = re.match(r"^/api/researches/([^/]+)(?:/|$)", path)
                        if research_match:
                            with service.lock:
                                service.researches.authorize(principal, research_match.group(1))
                        match = re.match(r"^/api/sessions/([^/]+)(?:/|$)", path)
                        if match:
                            with service.lock:
                                service.access.authorize(principal, match.group(1), deleted=request.method == "DELETE")
                        if path.startswith("/api/model-settings") and request.method != "GET" and principal.role != "admin":
                            raise HTTPException(403, "administrator_required")
                if request.method == "POST" and request.url.path.endswith(
                    ("/uploads", "/intake/protocols", "/analysis-inputs/objects", "/analysis-inputs/assets")
                ):
                    pending = service.quotas.reserve_upload(principal.id, int(length))
                    pending.__enter__()
                    reservation = pending
                response = await call_next(request)
                if exceeded:
                    response = (
                        upload_limit_response(settings)
                        if upload_request
                        else safe_error_response("request_too_large", 413)
                    )
            except HTTPException as exc:
                response = safe_error_response(exc.detail, exc.status_code)
            except Exception:
                if exceeded:
                    return (
                        upload_limit_response(settings)
                        if upload_request
                        else safe_error_response("request_too_large", 413)
                    )
                response = safe_error_response("request_failed", 500)
            finally:
                if reservation is not None:
                    reservation.__exit__(None, None, None)
            audit = getattr(request.state, "admin_audit", None)
            if audit is not None:
                try:
                    service.accounts.record_access(*audit, str(response.status_code))
                except Exception:
                    return safe_error_response("audit_unavailable", 503)
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
            return response
        return await call_next(request)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/config")
    def config():
        return {
            "max_upload_bytes": settings.max_upload_bytes,
            "max_h5ad_logical_bytes": settings.max_h5ad_logical_bytes,
            "max_h5ad_dataset_elements": settings.max_h5ad_dataset_elements,
        }

    @app.get("/api/sessions")
    def sessions(request: Request, archived: bool | None = None):
        with service.lock:
            states = service.access.visible_sessions(request.state.principal)
            return {"sessions": [{key: item[key] for key in ("id", "title", "updated_at", "status", "archived", "research_id", "run_id", "conversation_kind")}
                                 for item in states if archived is None or item["archived"] == archived]}

    @app.post("/api/sessions")
    def create(request: Request, body: SessionCreation | None = None):
        with service.lock:
            research_id = body.research_id if body else None
            if research_id is not None:
                service.researches.owned(request.state.principal.id, research_id)
            return service.public(service.create(owner_id=request.state.principal.id, research_id=research_id))

    @app.get("/api/sessions/{sid}")
    def get(sid: str):
        with service.lock:
            return service.public(service.load(sid))

    @app.get("/api/sessions/{sid}/model-selection")
    def conversation_model(sid: str):
        with service.lock:
            state = service.load(sid)
            return service.model_configuration.selection_view(state["owner_id"], state["model_selection"],
                                                               state.get("model_configuration"))

    @app.put("/api/sessions/{sid}/model-selection")
    def select_conversation_model(sid: str, body: ConversationModelSelection):
        with service.lock, service.model_configuration.lock:
            state = service.load(sid)
            if state.get("archived"):
                raise HTTPException(409, "session_archived")
            configuration = service.model_configuration
            value = configuration.selection_with_default(state["owner_id"], body.model_dump())
            try:
                configuration.resolve_selection(state["owner_id"], value)
                previous = state["model_selection"]
                state["model_selection"] = value
                service.sessions.save(state)
                try:
                    configuration.remember_selection(state["owner_id"], value)
                except Exception:
                    state["model_selection"] = previous
                    service.sessions.save(state)
                    raise
                return configuration.selection_view(state["owner_id"], value, state.get("model_configuration"))
            except ModelSelectionError as error:
                raise HTTPException(409, error.code) from None

    @app.patch("/api/sessions/{sid}")
    def archive_session(sid: str, body: SessionArchive):
        return service.manage_session(sid, archived=body.archived)

    @app.delete("/api/sessions/{sid}")
    def delete_session(sid: str):
        return service.manage_session(sid)

    @app.get("/api/sessions/{sid}/diagnostics")
    def diagnostics(sid: str):
        if not (settings.runtime_environment == "development" and settings.diagnostics_enabled):
            raise HTTPException(404, "not_found")
        with service.lock:
            return build_session_diagnostics(settings, service.load(sid))

    @app.post("/api/sessions/{sid}/assessment/propose")
    def propose_assessment(sid: str, body: ScopeProposal):
        with service.lock:
            state = service.load(sid)
            service.assessment.propose(state, body)
            return service.public(state)


    @app.get("/api/sessions/{sid}/assessment/cell-explorer")
    def assessment_cell_explorer(sid: str, scope_digest: str, evidence_alias: str):
        with service.lock:
            state = service.load(sid)
            current = state.get("_assessment")
            if current is None:
                raise HTTPException(404, "assessment_not_found")
            if current.get("scope_digest") != scope_digest:
                raise HTTPException(409, "cell_explorer_scope_changed")
            try:
                with service.inputs.verification(state):
                    display = service.spatial_contexts.assessment_explorer(
                        state, service.assessment.public(state),
                        scope_digest=scope_digest, evidence_alias=evidence_alias)
            except (ValueError, KeyError, TypeError, OSError):
                raise HTTPException(422, "cell_explorer_source_unavailable") from None
            return JSONResponse(display, headers={"Cache-Control": "no-store"})

    @app.post("/api/sessions/{sid}/assessment/approve")
    def approve_assessment(sid: str, body: ScopeIdentity):
        with service.lock:
            state = service.load(sid)
            service.assessment.approve(state, body)
            return service.public(state)

    @app.post("/api/sessions/{sid}/assessment/resume")
    def resume_assessment(sid: str, body: ScopeIdentity):
        with service.lock:
            state = service.load(sid)
            service.assessment.resume(state, body)
            return service.public(state)

    @app.post("/api/sessions/{sid}/uploads")
    def upload(sid: str, file: UploadFile = File(...)):
        name = file.filename or ""
        if "/" in name or "\\" in name or not name.lower().endswith(".h5ad") or len(name) > 120:
            raise HTTPException(400, "invalid_upload_name")
        temporary = None
        destination = None
        installed = False
        committed = False
        with service.lock:
            state = service.load(sid)
            service.busy(state)
            if len(state["uploads"]) >= 8:
                raise HTTPException(400, "upload_count_limit")
            started_at = state["updated_at"]
            service.uploads_in_progress.add(sid)
        try:
            try:
                directory, _, _ = ensure_private_directory(service.directory(sid) / "uploads")
                aid = uid()
                temporary = directory / ("." + aid + ".upload")
                destination = directory / (aid + ".h5ad")
                try:
                    size, checksum = stream_upload(file.file, temporary, settings.max_upload_bytes)
                except UploadLimitExceeded:
                    return upload_limit_response(settings)
                except ValueError:
                    raise HTTPException(400, "invalid_h5ad") from None
                try:
                    with open_private_file(temporary, settings.max_upload_bytes) as stream:
                        locations = inspect_h5ad(
                            stream,
                            max_logical_bytes=settings.max_h5ad_logical_bytes,
                            max_dataset_elements=settings.max_h5ad_dataset_elements,
                        )
                except (ValueError, OSError) as exc:
                    reason = str(exc)
                    if reason in {
                        "h5ad_logical_size_limit",
                        "h5ad_dataset_element_limit",
                    }:
                        return h5ad_resource_limit_response(settings, reason)
                    raise HTTPException(400, "invalid_h5ad") from None
                with service.lock:
                    state = service.load(sid)
                    if state["updated_at"] != started_at or state["status"] in {
                        "thinking",
                        "running",
                        "stopping",
                    }:
                        raise HTTPException(409, "session_busy")
                    if len(state["uploads"]) >= 8:
                        raise HTTPException(400, "upload_count_limit")
                    if destination.exists() or destination.is_symlink():
                        raise ValueError("private_file_invalid")
                    os.replace(temporary, destination)
                    installed = True
                    response = service.register_h5ad(state, aid, name, size, checksum, locations)
                    committed = True
                    return response
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
                if installed and not committed and destination is not None:
                    destination.unlink(missing_ok=True)
        finally:
            with service.lock:
                service.uploads_in_progress.discard(sid)

    @app.get("/api/sessions/{sid}/intake")
    def intake(sid: str, upload_id: str, request: Request):
        with service.lock:
            state = service.load(sid)
            try:
                result = service.intake.public(state, upload_id)
                if not getattr(request.state, "admin_read", False):
                    service.sessions.save(state)
                return result
            except (ValueError, OSError, KeyError):
                raise HTTPException(409, "intake_file_unavailable") from None

    @app.post("/api/sessions/{sid}/intake")
    def stage_intake(sid: str, body: IntakeInput):
        with service.lock:
            state = service.load(sid)
            service.busy(state)
            service.controls.stage(state, "intake", body)
            service.sessions.save(state)
            return service.public(state)

    @app.post("/api/sessions/{sid}/intake/answer")
    def answer_intake(sid: str, body: IntakeAnswer):
        with service.lock:
            state = service.load(sid)
            intake_autofill.answer(service, state, body)
            service.sessions.save(state)
            return service.intake.public(state, body.upload_id)

    @app.post("/api/sessions/{sid}/intake/parse")
    def parse_intake(sid: str, body: IntakePrepare):
        with service.lock:
            state = service.load(sid)
            try:
                intake_autofill.start(service, state, body.upload_id)
            except (ValueError, OSError, KeyError):
                raise HTTPException(409, "intake_source_unavailable") from None
            return service.public(state)

    @app.post("/api/sessions/{sid}/intake/protocols")
    def upload_protocol(sid: str, upload_id: str, file: UploadFile = File(...)):
        content = file.file.read(intake_autofill.PROTOCOL_LIMIT + 1)
        if len(content) > intake_autofill.PROTOCOL_LIMIT:
            raise HTTPException(413, "protocol_too_large")
        with service.lock:
            state = service.load(sid)
            intake_autofill.attach(service, state, upload_id, file.filename or "", content)
            return service.public(state)

    @app.post("/api/sessions/{sid}/intake/protocols/formalize")
    def formalize_protocol(sid: str, body: ProtocolRequest):
        with service.lock:
            state = service.load(sid)
            try:
                protocol_formalization.start(service, state, body)
            except (ValueError, OSError):
                raise HTTPException(409, "protocol_source_unavailable") from None
            return service.public(state)

    @app.post("/api/sessions/{sid}/intake/protocols/answer")
    def answer_protocol(sid: str, body: ProtocolAnswer):
        with service.lock:
            state = service.load(sid)
            try:
                protocol_formalization.answer(service, state, body)
            except (ValueError, OSError):
                raise HTTPException(409, "protocol_source_unavailable") from None
            return service.public(state)

    @app.post("/api/sessions/{sid}/intake/protocols/edit")
    def edit_protocol(sid: str, body: ProtocolEdit):
        with service.lock:
            state = service.load(sid)
            try:
                protocol_formalization.edit(service, state, body)
            except (ValueError, OSError):
                raise HTTPException(409, "protocol_source_unavailable") from None
            return service.public(state)

    @app.post("/api/sessions/{sid}/intake/protocols/review")
    def review_protocol(sid: str, body: ProtocolReview):
        with service.lock:
            state = service.load(sid)
            try:
                protocol_formalization.review(service, state, body)
            except (ValueError, OSError):
                raise HTTPException(409, "protocol_source_unavailable") from None
            return service.public(state)

    @app.get("/api/sessions/{sid}/intake/protocols/{pid}/versions/{vid}/{kind}")
    def download_protocol(sid: str, pid: str, vid: str, kind: str, upload_id: str):
        with service.lock:
            state = service.load(sid)
            try:
                content = protocol_formalization.download(service, state, upload_id, pid, vid, kind)
            except (ValueError, OSError, KeyError):
                raise HTTPException(409, "protocol_artifact_unavailable") from None
            return Response(
                content=content,
                media_type="text/plain" if kind == "bpl" else "application/json",
                headers={
                    "Content-Disposition": 'attachment; filename="'
                    + protocol_formalization.ARTIFACTS[kind]
                    + '"'
                },
            )

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
            service.execution.schedule(
                state,
                "thinking",
                lambda session_id, epoch: service.draft_scientific_inputs(
                    session_id, epoch, body.upload_id
                ),
            )
            return service.public(state)

    @app.post("/api/sessions/{sid}/scientific-inputs/confirm")
    def confirm_scientific_inputs(sid: str, body: DraftIdentity):
        with service.lock:
            state = service.load(sid)
            service.busy(state)
            service.scientific_inputs.confirm(state, body.draft_id, body.draft_digest)
            service.sessions.save(state)
            return service.public(state)

    @app.post("/api/sessions/{sid}/conditional-inputs/propose")
    def propose_conditional_inputs(sid: str, body: ConditionalProposal):
        with service.lock:
            state = service.load(sid)
            service.conditional_inputs.propose(state, body.selection, body.expected_revision)
            return service.public(state)

    @app.post("/api/sessions/{sid}/conditional-inputs/{action}")
    def decide_conditional_inputs(sid: str, action: str, body: ConditionalDecision):
        if action not in {"confirm", "cancel", "prepare"}:
            raise HTTPException(404, "not_found")
        with service.lock:
            state = service.load(sid)
            getattr(service.conditional_inputs, action)(
                state, body.draft_id, body.draft_digest, body.expected_revision
            )
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
            service.sessions.save(state)
            return service.public(state)

    @app.post("/api/sessions/{sid}/clarification/answer")
    def answer_clarification(sid: str, body: AnswerBody):
        with service.lock:
            state = service.load(sid)
            service.busy(state)
            resume = service.clarifications.answer(state, body)
            service.sessions.save(state)
        if resume:
            service.atlas_mapping.schedule(state["owner_id"], state["research_id"], resume["sample_id"],
                                           allow_completed=resume["changed"])
        with service.lock:
            return service.public(service.load(sid))

    @app.post("/api/sessions/{sid}/clarification/cancel")
    def cancel_clarification(sid: str, body: CardIdentity):
        with service.lock:
            state = service.load(sid)
            service.busy(state)
            service.clarifications.cancel(state, body)
            service.sessions.save(state)
            return service.public(state)

    @app.post("/api/sessions/{sid}/clarification/revise")
    def revise_clarification(sid: str, body: CardIdentity):
        with service.lock:
            state = service.load(sid)
            service.busy(state)
            service.clarifications.revise(state, body)
            service.sessions.save(state)
            return service.public(state)

    @app.post("/api/sessions/{sid}/stop")
    def stop(sid: str, body: Body):
        with service.lock:
            state = service.load(sid)
            service.controls.fence(state)
            service.pause_sample_handoffs(state)
            service.sessions.save(state)
            return service.public(state)

    @app.post("/api/sessions/{sid}/inputs")
    def inputs(sid: str, body: SourceInput):
        with service.lock:
            state = service.load(sid)
            service.controls.stage(state, "source", body)
            service.sessions.save(state)
            return service.public(state)

    @app.post("/api/sessions/{sid}/input-change/confirm")
    def confirm_input_change(sid: str, body: InputChange):
        with service.lock:
            state = service.load(sid)
            service.controls.resolve(state, body.change_id, body.change_digest, commit=True)
            service.sessions.save(state)
            return service.public(state)

    @app.post("/api/sessions/{sid}/input-change/discard")
    def discard_input_change(sid: str, body: InputChange):
        with service.lock:
            state = service.load(sid)
            service.controls.resolve(state, body.change_id, body.change_digest, commit=False)
            service.sessions.save(state)
            return service.public(state)

    @app.post("/api/sessions/{sid}/input-review/keep")
    def keep_inputs(sid: str, body: Body):
        with service.lock:
            state = service.load(sid)
            service.controls.keep(state)
            service.sessions.save(state)
            return service.public(state)

    @app.get("/api/sessions/{sid}/analysis-inputs")
    def analysis_inputs(sid: str, request: Request):
        with service.lock:
            state = service.load(sid)
            admin_read = getattr(request.state, "admin_read", False)
            value = service.inputs.public(state, refresh=not admin_read)
            if not admin_read and state["status"] not in {"thinking", "running", "stopping"}:
                service.sessions.save(state)
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
            if service.controls.stage_selection(state, body):
                service.sessions.save(state)
            else:
                state["_input_selections"][body.tool_id] = body.model_dump(mode="json")
                service.input_changed(state)
            return service.public(state)

    @app.post("/api/sessions/{sid}/analysis-inputs/objects")
    def input_object(
        sid: str,
        tool_id: str,
        mode_id: str,
        role: str,
        schema_ref: str,
        object_version: str,
        file: UploadFile = File(...),
    ):
        with service.lock:
            state = service.load(sid)
            service.busy(state)
            try:
                service.inputs.add_object(
                    state,
                    tool_id=tool_id,
                    mode_id=mode_id,
                    role=role,
                    schema_ref=schema_ref,
                    object_version=object_version,
                    data=file.file.read(OBJECT_LIMIT + 1),
                )
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
            service.sessions.save(state)
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
        focus = (service.focus_sample(sid, body.sample_id) if body.sample_id
                 and body.text.strip().casefold() not in {"stop", "cancel", "停止", "取消"} else None)
        with service.lock:
            state = service.load(sid)
            if len(state["messages"]) >= 100:
                raise HTTPException(400, "conversation_limit")
            if body.text.strip().casefold() in {"stop", "cancel", "停止", "取消"}:
                service.message(state, "user", body.text.strip(), source="user_input")
                service.controls.fence(state)
                service.pause_sample_handoffs(state)
                service.sessions.save(state)
                return service.public(state)
            service.busy(state)
            if not body.text.strip():
                raise HTTPException(422, "invalid_request")
            service.message(state, "user", body.text.strip(), source="user_input")
            if focus:
                state["_sample_turn"] = {**focus, "message_id": state["messages"][-1]["id"]}
            else:
                state.pop("_sample_turn", None)
            if state["title"] == "New analysis" and not state.get("_title_edited"):
                state["title"] = private_text(body.text.strip())[:60]
            # Any new user message invalidates an unapproved proposal.
            if state["plan"] and state["plan"]["status"] == "proposed":
                state["plan"], state["_plan"] = None, None
            service.execution.schedule(state, "thinking", service.think)
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
            if body.plan_id != plan.plan_id or not secrets.compare_digest(
                body.plan_digest, plan.approval_sha256()
            ):
                raise HTTPException(409, "approval_mismatch")
            if not any(item.disposition.value == "execute" for item in plan.steps):
                raise HTTPException(409, "plan_has_no_executable_steps")
            try:
                service.verify_scientific_plan(state, plan)
            except ValueError:
                raise HTTPException(409, "scientific_plan_invalid_or_stale") from None
            approved = approve_plan(
                plan,
                approver_id="private-operator",
                authority_ref="web-session:" + sid,
                approved_at=datetime.now(timezone.utc),
            )
            state["_plan"] = approved.model_dump(mode="json")
            state["plan"]["status"] = "approved"
            service.execution.schedule(state, "running", service.execution.execute)
            return service.public(state)

    @app.get("/api/sessions/{sid}/artifacts/{aid}")
    def artifact(sid: str, aid: str):
        with service.lock:
            state = service.load(sid)
            public, data = service.artifacts.read(state, aid)
            inline = public["media_type"] in {"image/png", "image/svg+xml"}
            return Response(
                data,
                media_type=public["media_type"],
                headers={
                    "Content-Disposition": ("inline" if inline else "attachment")
                    + '; filename="'
                    + public["name"]
                    + '"',
                    "Content-Security-Policy": "default-src 'none'; sandbox",
                    "X-Content-Type-Options": "nosniff",
                },
            )

    @app.post("/api/sessions/{sid}/artifacts/{aid}/acknowledge")
    def acknowledge_artifact(sid: str, aid: str):
        with service.lock:
            state = service.load(sid)
            return service.artifacts.acknowledge(state, aid)

    def spatial_context_value(sid, aid):
        state = service.load(sid)
        try:
            return service.spatial_contexts.read(state, aid)
        except (ValueError, KeyError, TypeError, OSError):
            raise HTTPException(422, "spatial_context_unavailable") from None

    @app.get("/api/sessions/{sid}/artifacts/{aid}/spatial-context")
    def spatial_context(sid: str, aid: str):
        with service.lock:
            display, _ = spatial_context_value(sid, aid)
            return JSONResponse(display, headers={"Cache-Control": "no-store"})

    @app.get("/api/sessions/{sid}/artifacts/{aid}/spatial-context/sections/{section_id}")
    def spatial_section(sid: str, aid: str, section_id: str, context_id: str):
        from .spatial_reference import read_spatial_section
        with service.lock:
            display, reference = spatial_context_value(sid, aid)
            if context_id != display["context_id"]:
                raise HTTPException(409, "spatial_context_changed")
            if reference is None:
                raise HTTPException(422, "spatial_context_unavailable")
            try:
                section = read_spatial_section(reference, section_id)
            except ValueError:
                raise HTTPException(404, "spatial_section_unknown") from None
            return JSONResponse({**section, "context_id": context_id}, headers={"Cache-Control": "no-store"})

    @app.get("/api/sessions/{sid}/artifacts/{aid}/spatial-context/model")
    def spatial_model(sid: str, aid: str, context_id: str):
        from .spatial_reference import configured_path, verify_file
        with service.lock:
            display, reference = spatial_context_value(sid, aid)
            if context_id != display["context_id"]:
                raise HTTPException(409, "spatial_context_changed")
            if reference is None or reference.manifest.model is None:
                raise HTTPException(404, "spatial_model_unavailable")
            asset = reference.manifest.model
            try:
                path = configured_path(reference.manifest.data_root, asset.file)
                verify_file(path, asset.sha256)
                data = path.read_bytes()
                import hashlib
                if hashlib.sha256(data).hexdigest() != asset.sha256:
                    raise ValueError("spatial_model_changed")
            except (ValueError, OSError):
                raise HTTPException(422, "spatial_model_unavailable") from None
            return Response(data, media_type="model/gltf-binary", headers={"Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff"})

    @app.get("/api/sessions/{sid}/artifacts/{aid}/preview")
    def artifact_preview(sid: str, aid: str):
        with service.lock:
            state = service.load(sid)
            try:
                public, data = service.artifacts.read(
                    state,
                    aid,
                    limit=PARQUET_STORED_LIMIT,
                )
            except ValueError as exc:
                if str(exc) == "private_file_too_large":
                    raise HTTPException(413, "artifact_preview_too_large") from None
                raise HTTPException(422, "artifact_preview_unavailable") from None
            if public["media_type"] == "application/json" and public["name"].startswith("expression_umap."):
                from .research_context import expression_plot_display
                try:
                    projection = expression_plot_display(service, state, aid)
                except (ValueError, KeyError, TypeError, OSError):
                    raise HTTPException(422, "expression_plot_display_unavailable") from None
                return JSONResponse(projection, headers={"X-Content-Type-Options": "nosniff"})
            if (
                public.get("tool_id") == "P0-03"
                and public["media_type"] == "application/json"
                and public["name"].startswith("native_measurement_spec.")
            ):
                from .research_context import reference_similarity_display

                try:
                    projection = reference_similarity_display(service, state, aid)
                except (ValueError, KeyError, TypeError, OSError):
                    raise HTTPException(422, "reference_similarity_display_unavailable") from None
                return JSONResponse(projection, headers={"X-Content-Type-Options": "nosniff"})
            if (
                public["media_type"] == "application/json"
                and "visualization_artifact_set." in public["name"]
            ):
                from .research_context import typed_figure_display

                try:
                    projection = typed_figure_display(service, state, aid)
                except (ValueError, KeyError, TypeError, OSError):
                    raise HTTPException(422, "figure_display_unavailable") from None
                return JSONResponse(projection, headers={"X-Content-Type-Options": "nosniff"})
            if (
                public.get("tool_id") == "P0-09"
                and public["media_type"] == "application/json"
                and public["name"].startswith("cytoscape_elements.")
            ):
                from .inputs import strict_json
                from .research_context import graph_composition_display

                try:
                    projection = graph_composition_display(service, state, aid, strict_json(data))
                except (ValueError, KeyError, TypeError, OSError):
                    from .runtime import record_degradation
                    with service.lock:
                        current = service.load(sid)
                        record_degradation(current, "graph_display_unavailable")
                        service.sessions.save(current)
                    raise HTTPException(422, "graph_display_unavailable") from None
                return JSONResponse(projection, headers={"X-Content-Type-Options": "nosniff"})
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
        with service.lock:
            state = service.load(sid)
            messages = [
                item
                for item in project_public_messages(state.get("messages", []))
                if item.get("source") in MESSAGE_SOURCES
            ]
        text = "# BRIDGE research conversation\n\n" + "\n\n".join(
            item["role"] + ":\n" + item["content"] for item in messages
        )
        return Response(
            text,
            media_type="text/markdown",
            headers={"Content-Disposition": 'attachment; filename="conversation.md"'},
        )

    from .admin_http import install_admin
    install_admin(app, service)

    if settings.static_dir is not None:
        app.mount("/", StaticFiles(directory=settings.static_dir, html=True), name="web")
