"""Account login, registration and revocable session cookies."""
from dataclasses import asdict

from fastapi import Request, Response
from pydantic import BaseModel, ConfigDict, Field

from .runtime import session_cookie_name


class AccountLogin(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=128, repr=False)


class Registration(AccountLogin):
    notice_version: str = Field(max_length=64)


class PasswordChange(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    old_password: str = Field(min_length=1, max_length=128, repr=False)
    password: str = Field(min_length=12, max_length=128, repr=False)


def install_auth(app, service, settings):
    name = session_cookie_name(settings.runtime_environment)

    def set_cookie(response, cookie):
        response.set_cookie(name, cookie, httponly=True, samesite="strict",
                            secure=settings.origin.startswith("https:"), max_age=settings.cookie_ttl)

    @app.get("/api/auth/config")
    def auth_config():
        from .accounts import NOTICE, NOTICE_VERSION, USERNAME_PATTERN, PASSWORD_MIN, PASSWORD_MAX
        return {"mode": "accounts", "notice": NOTICE, "notice_version": NOTICE_VERSION,
                "username_pattern": USERNAME_PATTERN, "password_min": PASSWORD_MIN, "password_max": PASSWORD_MAX}

    @app.get("/api/me")
    def me(request: Request):
        return {"user": asdict(request.state.principal)}

    def rate_limit(request, *, registration=False):
        store = service.accounts
        client = request.client.host if request.client else "unknown"
        # Proxy addresses are deliberately not trusted from arbitrary headers.
        store.limit("auth:global", maximum=120, window=60)
        store.limit("auth:client:" + client, maximum=20, window=60)
        if registration:
            store.limit("register:global", maximum=30, window=3600)
            store.limit("register:client:" + client, maximum=5, window=3600)

    @app.post("/api/register")
    def register(body: Registration, request: Request, response: Response):
        rate_limit(request, registration=True)
        user = service.accounts.register(body.username, body.password, body.notice_version)
        set_cookie(response, service.accounts.issue_login(user.id))
        return {"authenticated": True, "user": asdict(user)}

    @app.post("/api/login")
    def account_login(body: AccountLogin, request: Request, response: Response):
        rate_limit(request)
        user = service.accounts.authenticate(body.username, body.password)
        set_cookie(response, service.accounts.issue_login(user.id))
        return {"authenticated": True, "user": asdict(user)}

    @app.post("/api/me/password")
    def password(body: PasswordChange, request: Request, response: Response):
        service.accounts.change_password(request.state.principal.id, body.old_password, body.password)
        response.delete_cookie(name)
        return {"authenticated": False}

    @app.post("/api/logout")
    def logout(request: Request, response: Response):
        cookie = request.cookies.get(name, "")
        service.accounts.revoke_login(cookie)
        response.delete_cookie(name)
        return {"authenticated": False}
