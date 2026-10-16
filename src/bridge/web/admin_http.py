"""Explicitly read-only cross-user views and administrator account actions."""
from contextlib import ExitStack
import hashlib
from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from bridge.storage.private_paths import ensure_private_directory
from .intake_autofill import PROTOCOL_LIMIT
from .sessions import ID, open_private_file

# Reuse the existing readers and integrity gates, not their mutation endpoints.
READ_PATHS = {
    "/api/sessions/{sid}/intake",
    "/api/sessions/{sid}/analysis-inputs",
    "/api/sessions/{sid}/artifacts/{aid}",
    "/api/sessions/{sid}/artifacts/{aid}/preview",
    "/api/sessions/{sid}/artifacts/{aid}/spatial-context",
    "/api/sessions/{sid}/artifacts/{aid}/spatial-context/sections/{section_id}",
    "/api/sessions/{sid}/artifacts/{aid}/spatial-context/model",
    "/api/sessions/{sid}/assessment/cell-explorer",
    "/api/sessions/{sid}/intake/protocols/{pid}/versions/{vid}/{kind}",
    "/api/sessions/{sid}/transcript",
}


def install_admin(app, service):
    @app.get("/api/admin/users")
    def users():
        return {"users": service.accounts.users()}

    @app.post("/api/admin/users/{user_id}/disable")
    def disable(user_id: str):
        service.accounts.disable(user_id)
        return {"disabled": True}

    @app.post("/api/admin/users/{user_id}/reset-password")
    def reset_password(user_id: str):
        return {"temporary_password": service.accounts.reset_password(user_id)}

    @app.get("/api/admin/audit")
    def audit():
        return {"events": service.accounts.audit_events()}

    @app.get("/api/admin/sessions")
    def sessions(request: Request, user_id: str | None = None):
        with service.lock:
            names = {user["id"]: user["username"] for user in service.accounts.users()}
            values = service.access.visible_sessions(request.state.principal, owner_id=user_id or None, admin_read=True)
            return {"sessions": [{**item, "owner_username": names.get(item["owner_id"], "unknown")} for item in values]}

    @app.get("/api/admin/sessions/{sid}")
    def session(sid: str):
        with service.lock:
            state = service.load(sid)
            owner = next((user for user in service.accounts.users() if user["id"] == state["owner_id"]), None)
            if owner is None:
                raise HTTPException(404, "not_found")
            return {"session": service.public(state), "owner": {"id": owner["id"], "username": owner["username"]},
                    "protocols": [{"id": item["id"], "name": item["name"]} for intake in state.get("_intake_autofill", {}).values()
                                  for item in intake.get("protocols", [])]}


    def material(sid, identifier, *, protocol=False):
        if not ID.fullmatch(identifier):
            raise HTTPException(404, "not_found")
        with service.lock:
            state = service.load(sid)
            if protocol:
                record = next((item for intake in state.get("_intake_autofill", {}).values()
                               for item in intake.get("protocols", []) if item["id"] == identifier), None)
                path = service.directory(sid) / "intake-protocols" / (identifier + ".bin")
                limit, suffix = PROTOCOL_LIMIT, ".bin"
                if record:
                    extension = Path(record["name"]).suffix.lower()
                    if extension in {".pdf", ".txt", ".md", ".docx"}:
                        suffix = extension
            else:
                record = state["_uploads"].get(identifier)
                path = service.directory(sid) / "uploads" / (identifier + ".h5ad")
                limit, suffix = service.settings.max_upload_bytes, ".h5ad"
            if record is None:
                raise HTTPException(404, "not_found")
            ensure_private_directory(path.parent)
            opened = ExitStack()
            try:
                stream = opened.enter_context(open_private_file(path, limit))
            except OSError:
                opened.close()
                raise HTTPException(404, "not_found") from None
        try:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
            if digest != record["sha256"]:
                raise HTTPException(409, "artifact_integrity_mismatch")
            stream.seek(0)
        except BaseException:
            opened.close()
            raise

        def chunks():
            try:
                yield from iter(lambda: stream.read(1024 * 1024), b"")
            finally:
                opened.close()
        return StreamingResponse(chunks(), media_type="application/octet-stream",
                                 background=BackgroundTask(opened.close),
                                 headers={"Content-Disposition": 'attachment; filename="' + identifier + suffix + '"',
                                          "Content-Security-Policy": "default-src 'none'; sandbox"})

    @app.get("/api/admin/sessions/{sid}/uploads/{upload_id}")
    def upload(sid: str, upload_id: str):
        return material(sid, upload_id)

    @app.get("/api/admin/sessions/{sid}/protocols/{protocol_id}")
    def protocol(sid: str, protocol_id: str):
        return material(sid, protocol_id, protocol=True)

    for route in list(app.routes):
        if getattr(route, "path", "") in READ_PATHS:
            app.add_api_route(route.path.replace("/api/", "/api/admin/", 1), route.endpoint, methods=["GET"])
