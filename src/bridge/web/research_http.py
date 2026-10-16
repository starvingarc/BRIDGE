"""Research HTTP composition; scientific input checks stay in their existing modules."""
from contextlib import ExitStack
import hashlib
import re
from urllib.parse import quote

from fastapi import File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.background import BackgroundTask

from . import intake_autofill
from .researches import MATERIAL_PUBLIC
from .sessions import UPLOAD_CHUNK_BYTES, UploadLimitExceeded, open_private_file, uid


class ResearchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=500)

    @field_validator("name", "description")
    @classmethod
    def clean(cls, value, info):
        value = value.strip()
        if (info.field_name == "name" and not value) or re.search(r"[\x00-\x1f\x7f]", value):
            raise ValueError("invalid_research_text")
        return value


class ConversationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResearchAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    research_id: str = Field(pattern=r"^[a-f0-9]{32}$")


class SessionTitle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=160)

    @field_validator("title")
    @classmethod
    def clean(cls, value):
        value = value.strip()
        if not value or re.search(r"[\x00-\x1f\x7f]", value):
            raise ValueError("invalid_session_title")
        return value


class MaterialSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    material_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    upload_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")


class ShareMaterial(BaseModel):
    model_config = ConfigDict(extra="forbid")
    upload_id: str = Field(pattern=r"^[a-f0-9]{32}$")


def install_research_http(app, service, settings):
    store = service.researches

    def detail(principal, rid):
        return store.public(store.owned(principal.id, rid), service.access.visible_sessions(principal), detail=True)

    def put(owner, rid, name, source):
        return store.put(owner, rid, name, source, max_upload_bytes=settings.max_upload_bytes,
                         max_logical_bytes=settings.max_h5ad_logical_bytes,
                         max_dataset_elements=settings.max_h5ad_dataset_elements)

    @app.get("/api/researches")
    def researches(request: Request):
        with service.lock:
            sessions = service.access.visible_sessions(request.state.principal)
            return {"researches": [store.public(state, sessions) for state in store.list_owned(request.state.principal.id)]}

    @app.post("/api/researches")
    def create_research(request: Request, body: ResearchBody):
        with service.lock:
            state = store.create(request.state.principal.id, body.name, body.description)
            return store.public(state, detail=True)

    @app.get("/api/researches/{rid}")
    def get_research(rid: str, request: Request):
        with service.lock:
            return detail(request.state.principal, rid)

    @app.patch("/api/researches/{rid}")
    def rename_research(rid: str, request: Request, body: ResearchBody):
        with service.lock:
            state = store.owned(request.state.principal.id, rid)
            state.update(name=body.name, description=body.description)
            store.save(state)
            return detail(request.state.principal, rid)

    def conversation(owner_id, rid, run_id=None, *, create=False):
        with service.lock:
            return service.public(service.conversation(owner_id, rid, run_id, create=create))

    @app.get("/api/researches/{rid}/conversation")
    def research_conversation(rid: str, request: Request):
        return conversation(request.state.principal.id, rid)

    @app.post("/api/researches/{rid}/conversation")
    def create_research_conversation(rid: str, request: Request, body: ConversationRequest):
        return conversation(request.state.principal.id, rid, create=True)

    @app.get("/api/researches/{rid}/runs/{run_id}/conversation")
    def run_conversation(rid: str, run_id: str, request: Request):
        return conversation(request.state.principal.id, rid, run_id)

    @app.post("/api/researches/{rid}/runs/{run_id}/conversation")
    def create_run_conversation(rid: str, run_id: str, request: Request, body: ConversationRequest):
        return conversation(request.state.principal.id, rid, run_id, create=True)

    @app.post("/api/researches/{rid}/uploads")
    def upload_material(rid: str, request: Request, file: UploadFile = File(...)):
        try:
            item = put(request.state.principal.id, rid, file.filename or "", file.file)
        except UploadLimitExceeded:
            raise HTTPException(413, "research_material_too_large") from None
        except (ValueError, OSError):
            raise HTTPException(422, "research_material_invalid") from None
        return {key: item[key] for key in MATERIAL_PUBLIC if key in item}

    @app.get("/api/researches/{rid}/materials/{mid}")
    def download_material(rid: str, mid: str, request: Request):
        owner = request.state.principal.id
        item = store.material(owner, rid, mid)
        stack = ExitStack()
        try:
            stream = stack.enter_context(store.checked_material(owner, rid, mid))
        except (ValueError, OSError):
            stack.close()
            raise HTTPException(409, "research_material_unavailable") from None

        def chunks():
            try:
                while chunk := stream.read(UPLOAD_CHUNK_BYTES):
                    yield chunk
            finally:
                stack.close()

        return StreamingResponse(chunks(), media_type="application/octet-stream", headers={
            "Content-Disposition": "attachment; filename*=UTF-8''" + quote(item["name"], safe=""),
            "Content-Length": str(item["size"]),
        }, background=BackgroundTask(stack.close))

    @app.post("/api/sessions/{sid}/research")
    def assign_research(sid: str, request: Request, body: ResearchAssignment):
        with service.lock:
            store.owned(request.state.principal.id, body.research_id)
            state = service.load(sid)
            service.busy(state)
            if state.get("research_id") not in {None, body.research_id}:
                raise HTTPException(409, "session_research_already_assigned")
            state["research_id"] = body.research_id
            service.sessions.save(state)
            return service.public(state)

    @app.patch("/api/sessions/{sid}/title")
    def rename_session(sid: str, body: SessionTitle):
        with service.lock:
            state = service.load(sid)
            service.busy(state)
            state["title"] = body.title
            state["_title_edited"] = True
            service.sessions.save(state)
            return service.public(state)

    @app.post("/api/sessions/{sid}/research-materials")
    def select_material(sid: str, request: Request, body: MaterialSelection):
        with service.lock:
            owner = request.state.principal.id
            state = service.load(sid)
            service.busy(state)
            if service.execution.has_pending(sid):
                raise HTTPException(409, "session_busy")
            rid = state.get("research_id")
            item = store.material(owner, rid, body.material_id)
            if item["kind"] == "protocol":
                if not body.upload_id or body.upload_id not in state["_uploads"]:
                    raise HTTPException(422, "research_protocol_input_required")
                key = body.upload_id + ":" + item["id"]
                if key in state.get("_research_protocols", {}):
                    return service.public(state)
                try:
                    with store.checked_material(owner, rid, item["id"]) as stream:
                        content = stream.read(intake_autofill.PROTOCOL_LIMIT + 1)
                    with service.quotas.reserve_upload(owner, item["size"]):
                        intake_autofill.attach(service, state, body.upload_id, item["name"], content)
                        pid = state["_intake_autofill"][body.upload_id]["protocols"][-1]["id"]
                        state.setdefault("_research_protocols", {})[key] = pid
                        service.sessions.save(state)
                    return service.public(state)
                except (ValueError, OSError):
                    raise HTTPException(409, "research_material_unavailable") from None
        return service.select_research_h5ad(owner, rid, sid, item["id"])

    @app.post("/api/sessions/{sid}/share-material")
    def share_material(sid: str, request: Request, body: ShareMaterial):
        """Explicitly retain an existing conversation H5AD in its research library."""
        with service.lock:
            state = service.load(sid)
            service.busy(state)
            owner, rid = request.state.principal.id, state.get("research_id")
            store.owned(owner, rid)
            upload = next((item for item in state["uploads"] if item["id"] == body.upload_id), None)
            if upload is None:
                raise HTTPException(404, "not_found")
            if upload.get("material_id"):
                item = store.material(owner, rid, upload["material_id"])
                return {key: item[key] for key in MATERIAL_PUBLIC if key in item}
            path = service.directory(sid) / "uploads" / (body.upload_id + ".h5ad")
            expected = state["_uploads"][body.upload_id]["sha256"]
            service.uploads_in_progress.add(sid)
        try:
            with service.quotas.reserve_upload(owner, upload["size"]), open_private_file(path, upload["size"]) as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != expected:
                    raise ValueError("upload_integrity_mismatch")
                stream.seek(0)
                item = put(owner, rid, upload["name"], stream)
            with service.lock:
                state = service.load(sid)
                current = next(value for value in state["uploads"] if value["id"] == body.upload_id)
                current["material_id"] = item["id"]
                service.sessions.save(state)
            return {key: item[key] for key in MATERIAL_PUBLIC if key in item}
        except (ValueError, OSError):
            raise HTTPException(409, "research_material_unavailable") from None
        finally:
            with service.lock:
                service.uploads_in_progress.discard(sid)
