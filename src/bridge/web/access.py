"""One ownership boundary for browser session resources."""
from fastapi import HTTPException

from .sessions import ID

SUMMARY_KEYS = ("id", "title", "updated_at", "status", "archived", "research_id", "run_id", "conversation_kind")


class SessionAccess:
    def __init__(self, sessions):
        self.sessions = sessions

    def authorize(self, principal, sid, *, admin_read=False, deleted=False):
        owner = self.sessions.owner(sid, include_deleted=deleted)
        if not owner or not (owner == principal.id or (admin_read and principal.role == "admin")):
            raise HTTPException(404, "not_found")

    def visible_sessions(self, principal, *, owner_id=None, admin_read=False):
        result = []
        for item in self.sessions.root.iterdir():
            if not ID.fullmatch(item.name):
                continue
            owner = self.sessions.owner(item.name)
            if not owner or (owner_id and owner != owner_id):
                continue
            if owner != principal.id and not (admin_read and principal.role == "admin"):
                continue
            state = self.sessions.load(item.name)
            result.append({**{key: state[key] for key in SUMMARY_KEYS}, "owner_id": owner})
        return sorted(result, key=lambda item: item["updated_at"], reverse=True)
