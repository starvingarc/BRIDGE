"""Unified model directory routes; account identity and shared writes stay server-owned."""
from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from .model_settings import ProviderInput, ModelSelectionError


class EmptyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ModelSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    provider_id: str = Field(max_length=64)
    model: str = Field(max_length=200)


def install_models(app, configuration):
    def identity(request):
        principal = request.state.principal
        return principal.id, principal.role == "admin"

    def write_identity(request, provider_id):
        user_id, admin = identity(request)
        if provider_id == "default" and not admin:
            raise HTTPException(403, "administrator_required")
        return user_id, admin

    def perform(action, *args):
        try:
            return action(*args)
        except ModelSelectionError as error:
            raise HTTPException(409, error.code) from None
        except ValueError:
            raise HTTPException(422, "invalid_model_configuration") from None

    @app.get("/api/models")
    def models(request: Request):
        return perform(configuration.providers_for, *identity(request))

    @app.put("/api/models/providers")
    def save(request: Request, body: ProviderInput):
        user_id, admin = write_identity(request, body.id)
        return perform(configuration.save_provider, user_id, body, admin)

    @app.delete("/api/models/providers/{provider_id}")
    def delete(request: Request, provider_id: str):
        if provider_id == "default":
            raise HTTPException(403, "shared_provider_required")
        user_id, admin = identity(request)
        return perform(configuration.delete_provider, user_id, provider_id, admin)

    @app.post("/api/models/select")
    def select(request: Request, body: ModelSelection):
        user_id, admin = identity(request)
        return perform(configuration.select_provider, user_id, body.provider_id, body.model, admin)

    @app.post("/api/models/catalog")
    def catalog(request: Request, body: ProviderInput):
        user_id, _ = write_identity(request, body.id)
        return perform(configuration.catalog_for, user_id, body)

    @app.post("/api/models/test")
    def test(request: Request, body: ProviderInput):
        user_id, _ = write_identity(request, body.id)
        if not body.models:
            raise HTTPException(422, "model_required")
        return perform(configuration.test_provider, user_id, body)

    @app.post("/api/models/providers/{provider_id}/capabilities")
    def capabilities(request: Request, provider_id: str, body: EmptyBody):
        user_id, _ = identity(request)
        return perform(configuration.refresh_capabilities, user_id, provider_id)
