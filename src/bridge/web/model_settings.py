"""Private instance defaults; immutable snapshots keep in-flight work consistent."""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import replace
import json
from hashlib import sha256
import os
from threading import RLock
from typing import Literal
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

from bridge.storage.private_paths import ensure_private_directory
from .sessions import ID, open_private_file, write_file, uid, now
from .model_transport import provider_client, validate_endpoint


MAX_SETTINGS_BYTES = 128 * 1024


class ModelSettingsInput(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    base_url: str = Field(min_length=1, max_length=2048)
    model: str = Field(min_length=1, max_length=200)
    api_key: str = Field(default="", max_length=8192, repr=False)
    action_protocol: Literal["json", "deepseek_tools"] = "json"

    @field_validator("base_url", "model", "api_key")
    @classmethod
    def clean(cls, value):
        if any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError("invalid_model_configuration")
        return value.strip()

    @field_validator("api_key")
    @classmethod
    def header_value(cls, value):
        if not value.isascii():
            raise ValueError("invalid_model_configuration")
        return value

    @field_validator("base_url")
    @classmethod
    def address(cls, value):
        parts = urlsplit(value)
        if (parts.scheme not in {"https", "http"} or not parts.hostname
                or parts.username or parts.password or parts.query or parts.fragment
                or any(c.isspace() for c in value)):
            raise ValueError("invalid_model_configuration")
        _ = parts.port
        return value.rstrip("/")


class PersonalModel(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    source: Literal["default", "personal"] = "default"
    settings: ModelSettingsInput | None = None
    version: str = Field(default="", max_length=64)


class ProviderInput(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    id: str = Field(pattern=r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$", max_length=64)
    name: str = Field(default="", max_length=100)
    base_url: str = Field(max_length=2048)
    api_key: str = Field(default="", max_length=8192, repr=False)
    models: list[str] = Field(default_factory=list, max_length=100)
    action_protocol: Literal["json", "deepseek_tools"] = "json"

    @field_validator("models")
    @classmethod
    def model_names(cls, values):
        values = [ModelSettingsInput.clean(v) for v in values]
        if any(not v or len(v) > 200 for v in values) or len(set(values)) != len(values):
            raise ValueError("invalid_model_catalog")
        return values

    @field_validator("name")
    @classmethod
    def display_name(cls, value):
        return ModelSettingsInput.clean(value)

    def connection(self):
        return ModelSettingsInput(base_url=self.base_url, api_key=self.api_key,
                                  model=self.models[0] if self.models else "catalog",
                                  action_protocol=self.action_protocol)


class StoredProvider(ProviderInput):
    version: str = Field(default="", max_length=64)


Effort = Literal["none", "minimal", "low", "medium", "high", "xhigh", "max"]


class ConversationModelSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    provider_id: str = Field(pattern=r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$", max_length=64)
    model: str = Field(max_length=200)
    effort: Effort | None = None


class EffortCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["supported", "unsupported", "unknown"] = "unknown"
    supported_levels: list[Effort] = Field(default_factory=list, max_length=7)
    default_level: Effort | None = None


class CatalogSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: str
    checked_at: str
    models: dict[str, EffortCapability]


class ModelSelectionError(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


class UserProviders(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    selected_provider: str = "default"
    selected_model: str = ""
    selected_effort: Effort | None = None
    capabilities: dict[str, CatalogSnapshot] = Field(default_factory=dict)
    providers: list[StoredProvider] = Field(default_factory=list, max_length=32)




class ModelConfiguration:
    def __init__(self, root, settings):
        self.path = root / "model-settings.json"
        self.lock = RLock()
        self.default_provider = {"name": "共享模型", "models": []}
        self.default = replace(settings, model_configuration_id=uid())
        self.bound = ContextVar("bridge_model_settings", default=None)
        try:
            with open_private_file(self.path, MAX_SETTINGS_BYTES) as stream:
                if os.fstat(stream.fileno()).st_mode & 0o077:
                    raise ValueError("unsafe_permissions")
                saved = json.loads(stream.read(MAX_SETTINGS_BYTES + 1))
                metadata = saved.pop("_provider", None)
                if metadata is not None:
                    self.default_provider = {"name": ProviderInput.display_name(metadata["name"]),
                                             "models": ProviderInput.model_names(metadata["models"])}
                version = saved.pop("_configuration_id", uid())
                if not isinstance(version, str) or not ID.fullmatch(version):
                    raise ValueError("invalid_model_configuration")
                value = ModelSettingsInput.model_validate(saved)
            if not value.api_key:
                raise ValueError("missing_key")
            self.default = replace(self.resolve(value), model_configuration_id=version)
        except FileNotFoundError:
            pass
        except (OSError, ValueError, KeyError, TypeError):
            raise ValueError("model_configuration_invalid") from None

    @property
    def current(self):
        snapshot = self.bound.get()
        if snapshot is None:
            return self.default
        # Only provider identity is pinned. Revoked sharing authorization and
        # changed scientific resources must remain visible to in-flight checks.
        return replace(self.default, model=snapshot.model,
                       model_base_url=snapshot.model_base_url,
                       model_api_key=snapshot.model_api_key,
                       model_action_protocol=snapshot.model_action_protocol,
                       model_endpoint_restricted=snapshot.model_endpoint_restricted,
                       model_configuration_id=snapshot.model_configuration_id,
                       model_provider_id=snapshot.model_provider_id,
                       model_effort=snapshot.model_effort)

    def task_context(self, owner_id=None, selection=None):
        snapshot = self.snapshot_for(owner_id, selection) if owner_id is not None else self.default

        @contextmanager
        def bind():
            token = self.bound.set(snapshot)
            try:
                yield snapshot
            finally:
                self.bound.reset(token)
        return bind()

    def view(self):
        return self.project(self.default)

    @staticmethod
    def project(value):
        return {"configured": bool(value.model and value.model_base_url and value.model_api_key),
                "base_url": value.model_base_url, "model": value.model,
                "has_api_key": bool(value.model_api_key), "action_protocol": value.model_action_protocol}

    def resolve(self, value, current=None):
        current = self.default if current is None else current
        key = value.api_key
        if not key and value.base_url == current.model_base_url.rstrip("/"):
            key = current.model_api_key
        if not key or not value.model:
            raise ValueError("invalid_model_configuration")
        return replace(current, model_base_url=value.base_url, model=value.model,
                       model_api_key=key, model_action_protocol=value.action_protocol)

    def save(self, value, provider=None):
        with self.lock:
            resolved = replace(self.resolve(value), model_configuration_id=uid())
            body = value.model_dump()
            body["_configuration_id"] = resolved.model_configuration_id
            body["api_key"] = resolved.model_api_key
            metadata = provider or {**self.default_provider, "models": list(dict.fromkeys([value.model, *self.default_provider["models"]]))}
            body["_provider"] = metadata
            encoded = json.dumps(body).encode()
            if len(encoded) > MAX_SETTINGS_BYTES:
                raise ValueError("invalid_model_configuration")
            write_file(self.path, encoded)
            self.default = resolved
            self.default_provider = metadata
            return self.view()

    def test(self, value):
        with self.lock:
            resolved = self.resolve(value)
        return self.probe(resolved)

    @staticmethod
    def probe(resolved):
        payload = {"model": resolved.model, "messages": [{"role": "user", "content": "Reply with OK."}],
                   "max_tokens": 32, "stream": False}
        if resolved.model_action_protocol == "deepseek_tools":
            payload["thinking"] = {"type": "disabled"}
        try:
            with provider_client(resolved, timeout=15, trust_env=False) as client:
                with client.stream("POST", resolved.model_base_url + "/chat/completions",
                                   headers={"Authorization": "Bearer " + resolved.model_api_key}, json=payload) as response:
                    response.raise_for_status()
                    body = bytearray()
                    for chunk in response.iter_bytes(chunk_size=4096):
                        body.extend(chunk)
                        if len(body) > 65536:
                            raise ValueError("response_too_large")
            data = json.loads(body)
            if not isinstance(data["choices"][0]["message"]["content"], str) or not data["choices"][0]["message"]["content"].strip():
                raise ValueError("invalid_response")
            return {"ok": True, "message": "连接成功。此测试不代表模型已通过完整分析验收。"}
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
            return {"ok": False, "message": "连接未通过，请检查服务地址、模型名称、密钥及网络。原默认配置未改变。"}

    def _personal_path(self, user_id):
        if not ID.fullmatch(user_id):
            raise ValueError("invalid_account")
        parent = self.path.parent / "models"
        if parent.exists() or parent.is_symlink():
            ensure_private_directory(parent)
        return parent / (user_id + ".json")


    def _personal(self, user_id):
        try:
            with open_private_file(self._personal_path(user_id), MAX_SETTINGS_BYTES) as stream:
                if os.fstat(stream.fileno()).st_mode & 0o077:
                    raise ValueError("unsafe_permissions")
                data = json.loads(stream.read(MAX_SETTINGS_BYTES + 1))
            if "source" in data:
                old = PersonalModel.model_validate(data)
                if old.source == "personal" and (not old.settings or not old.settings.api_key):
                    raise ValueError("missing_personal_model")
                providers = []
                if old.settings:
                    value = old.settings
                    providers.append(StoredProvider(id="personal", name="自定义模型", models=[value.model],
                        base_url=value.base_url, api_key=value.api_key, action_protocol=value.action_protocol,
                        version=old.version))
                return UserProviders(providers=providers, selected_provider="personal" if old.source == "personal" else "default",
                                     selected_model=old.settings.model if old.source == "personal" else "")
            profile = UserProviders.model_validate(data)
            for provider in profile.providers:
                if provider.id == "default" or not provider.models or not provider.connection().api_key:
                    raise ValueError("invalid_provider")
            if len({p.id for p in profile.providers}) != len(profile.providers):
                raise ValueError("duplicate_provider")
            if profile.selected_provider != "default":
                chosen = next((p for p in profile.providers if p.id == profile.selected_provider), None)
                if not chosen or profile.selected_model not in chosen.models:
                    raise ValueError("invalid_selection")
            return profile
        except FileNotFoundError:
            return UserProviders()
        except (OSError, ValueError, TypeError):
            raise ValueError("personal_model_configuration_invalid") from None

    def _write_personal(self, user_id, profile):
        encoded = profile.model_dump_json().encode()
        if len(encoded) > MAX_SETTINGS_BYTES or len(profile.providers) > 32:
            raise ValueError("model_configuration_too_large")
        write_file(self._personal_path(user_id), encoded)

    def _default_models(self):
        return list(dict.fromkeys(filter(None, [self.default.model, *self.default_provider["models"]])))

    def _provider_settings(self, provider, model=None):
        value = provider.connection() if provider else None
        return replace(self.default, model_base_url=value.base_url if value else "",
                       model=model or (value.model if value else ""),
                       model_api_key=value.api_key if value else "",
                       model_action_protocol=value.action_protocol if value else "json",
                       model_endpoint_restricted=True,
                       model_configuration_id=(sha256((provider.version + ":" + (model or value.model)).encode()).hexdigest()[:32] if provider else ""))

    def snapshot_for(self, user_id, selection=None):
        with self.lock:
            if selection is not None:
                return self.resolve_selection(user_id, selection)
            profile = self._personal(user_id)
            if profile.selected_provider == "default":
                model = profile.selected_model if profile.selected_model in self._default_models() else self.default.model
                return replace(self.default, model=model, model_configuration_id=(self.default.model_configuration_id if model == self.default.model
                    else sha256((self.default.model_configuration_id + ":" + model).encode()).hexdigest()[:32]))
            provider = next(p for p in profile.providers if p.id == profile.selected_provider)
            return self._provider_settings(provider, profile.selected_model)

    def providers_for(self, user_id, admin=False):
        with self.lock:
            profile = self._personal(user_id)
            shared = {"id": "default", "name": self.default_provider["name"], "shared": True,
                      "editable": admin, "models": self._default_models(), **self.view()}
            providers = [shared] + [{"id": p.id, "name": p.name or p.id, "shared": False, "editable": True,
                                    "models": p.models, **self.project(self._provider_settings(p))} for p in profile.providers]
            for provider in providers:
                provider["capabilities"] = self.capabilities_for(user_id, provider["id"])
            return {"providers": providers, "selected": {"provider_id": profile.selected_provider,
                    "model": self.snapshot_for(user_id).model}}

    def _resolve_provider(self, user_id, value):
        if value.id == "default":
            return self.resolve(value.connection())
        profile = self._personal(user_id)
        previous = next((p for p in profile.providers if p.id == value.id), None)
        resolved = self.resolve(value.connection(), self._provider_settings(previous))
        validate_endpoint(resolved.model_base_url, self.default.personal_model_allowlist)
        return resolved

    def save_provider(self, user_id, value, admin=False):
        with self.lock:
            if not value.models or (value.id == "default" and not admin):
                raise ValueError("invalid_provider")
            resolved = self._resolve_provider(user_id, value)
            if value.id == "default":
                self.save(value.connection(), {"name": value.name or "共享模型", "models": value.models})
            else:
                profile = self._personal(user_id)
                saved = StoredProvider(**{**value.model_dump(), "base_url": resolved.model_base_url,
                                          "api_key": resolved.model_api_key}, version=uid())
                found = next((i for i, p in enumerate(profile.providers) if p.id == value.id), None)
                if found is None:
                    profile.providers.append(saved)
                else:
                    profile.providers[found] = saved
                if profile.selected_provider == value.id and profile.selected_model not in value.models:
                    profile.selected_model = value.models[0]
                    profile.selected_effort = None
                self._write_personal(user_id, profile)
            return self.providers_for(user_id, admin)

    def select_provider(self, user_id, provider_id, model, admin=False):
        with self.lock:
            profile = self._personal(user_id)
            provider = next((p for p in profile.providers if p.id == provider_id), None)
            choices = self._default_models() if provider_id == "default" else provider.models if provider else []
            if model not in choices:
                raise ValueError("invalid_model_selection")
            profile.selected_provider, profile.selected_model = provider_id, model
            profile.selected_effort = None
            self._write_personal(user_id, profile)
            return self.providers_for(user_id, admin)

    def delete_provider(self, user_id, provider_id, admin=False):
        with self.lock:
            if provider_id == "default":
                raise ValueError("shared_provider_required")
            profile = self._personal(user_id)
            profile.providers = [p for p in profile.providers if p.id != provider_id]
            if profile.selected_provider == provider_id:
                profile.selected_provider, profile.selected_model = "default", ""
                profile.selected_effort = None
            profile.capabilities.pop(provider_id, None)
            self._write_personal(user_id, profile)
            return self.providers_for(user_id, admin)

    def recent_selection(self, user_id):
        with self.lock:
            profile = self._personal(user_id)
            return self.selection_with_default(user_id, {
                "provider_id": profile.selected_provider,
                "model": profile.selected_model or self.default.model,
                "effort": profile.selected_effort})

    def selection_with_default(self, user_id, selection):
        """Resolve an unspecified effort only from current declared metadata."""
        with self.lock:
            choice = ConversationModelSelection.model_validate(selection)
            if choice.effort is None:
                try:
                    capability = self.capabilities_for(user_id, choice.provider_id).get(choice.model, {})
                except ModelSelectionError:
                    capability = {}
                if capability.get("status") == "supported":
                    choice = choice.model_copy(update={"effort": capability.get("default_level")})
            return choice.model_dump()

    def remember_selection(self, user_id, selection):
        with self.lock:
            selection = self.selection_with_default(user_id, selection)
            self.resolve_selection(user_id, selection)
            choice = ConversationModelSelection.model_validate(selection)
            profile = self._personal(user_id)
            profile.selected_provider = choice.provider_id
            profile.selected_model = choice.model
            profile.selected_effort = choice.effort
            self._write_personal(user_id, profile)

    def _saved_provider(self, user_id, provider_id):
        if provider_id == "default":
            return self.default, self._default_models()
        profile = self._personal(user_id)
        provider = next((p for p in profile.providers if p.id == provider_id), None)
        if provider is None:
            raise ModelSelectionError("model_selection_unavailable")
        return self._provider_settings(provider), provider.models

    @staticmethod
    def _capability_version(settings, models):
        # Private cache identity binds metadata to the endpoint, credential,
        # protocol and catalogue, including environment-only shared providers.
        return sha256(json.dumps([settings.model_base_url, settings.model_api_key,
                                  settings.model_action_protocol, models]).encode()).hexdigest()

    def capabilities_for(self, user_id, provider_id):
        with self.lock:
            settings, models = self._saved_provider(user_id, provider_id)
            snapshot = self._personal(user_id).capabilities.get(provider_id)
            valid = snapshot and snapshot.version == self._capability_version(settings, models)
            return {model: (snapshot.models.get(model, EffortCapability()) if valid else EffortCapability()).model_dump()
                    for model in models}

    def resolve_selection(self, user_id, selection):
        with self.lock:
            choice = ConversationModelSelection.model_validate(selection)
            settings, models = self._saved_provider(user_id, choice.provider_id)
            if choice.model not in models or not all((settings.model_base_url, settings.model_api_key, choice.model)):
                raise ModelSelectionError("model_selection_unavailable")
            if choice.effort is not None:
                capability = self.capabilities_for(user_id, choice.provider_id)[choice.model]
                if capability["status"] != "supported" or choice.effort not in capability["supported_levels"]:
                    raise ModelSelectionError("model_effort_unavailable")
            version = sha256(json.dumps([settings.model_configuration_id, choice.model, choice.effort]).encode()).hexdigest()[:32]
            return replace(settings, model=choice.model, model_effort=choice.effort,
                           model_provider_id=choice.provider_id, model_configuration_id=version)

    def selection_view(self, user_id, selection, task_configuration=None):
        with self.lock:
            choice = ConversationModelSelection.model_validate(selection)
            try:
                self.resolve_selection(user_id, selection)
                availability = {"state": "ready", "reason": None}
            except ModelSelectionError as error:
                availability = {"state": "unavailable", "reason": error.code}
            try:
                capability = self.capabilities_for(user_id, choice.provider_id).get(choice.model, EffortCapability().model_dump())
            except ModelSelectionError:
                capability = EffortCapability().model_dump()
            return {"selection": choice.model_dump(), "availability": availability,
                    "capability": capability, "task_configuration": task_configuration}

    @staticmethod
    def _catalog(resolved):
        try:
            with provider_client(resolved, timeout=15, trust_env=False) as client:
                with client.stream("GET", resolved.model_base_url + "/models",
                                   headers={"Authorization": "Bearer " + resolved.model_api_key}) as response:
                    response.raise_for_status()
                    body = bytearray()
                    for chunk in response.iter_bytes(chunk_size=4096):
                        body.extend(chunk)
                        if len(body) > 1024 * 1024:
                            raise ValueError("catalog_too_large")
            items = json.loads(body)["data"]
            if not isinstance(items, list) or len(items) > 2000:
                raise ValueError("invalid_catalog")
            names, capabilities = [], {}
            for item in items:
                name = item.get("id") if isinstance(item, dict) else None
                if not (isinstance(name, str) and 0 < len(name) <= 200 and name.strip() == name
                        and all(ord(c) >= 32 and ord(c) != 127 for c in name)):
                    continue
                capability = EffortCapability()
                metadata = item.get("effort")
                if isinstance(metadata, dict) and isinstance(metadata.get("supported_levels"), list):
                    levels = metadata["supported_levels"]
                    try:
                        candidate = EffortCapability(status="supported" if levels else "unsupported",
                            supported_levels=levels, default_level=metadata.get("default_level"))
                        if (len(set(levels)) == len(levels)
                                and (candidate.default_level is None or candidate.default_level in levels)):
                            capability = candidate
                    except (ValueError, TypeError):
                        pass
                # Conflicting duplicate records cannot establish capabilities.
                if name in capabilities and capabilities[name] != capability.model_dump():
                    capabilities[name] = EffortCapability().model_dump()
                else:
                    capabilities[name] = capability.model_dump()
                names.append(name)
            return {"ok": True, "models": list(dict.fromkeys(names)), "capabilities": capabilities, "message": ""}
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return {"ok": False, "models": [], "capabilities": {},
                    "message": "无法获取模型目录，请检查地址和密钥，或手动添加模型。"}

    def catalog_for(self, user_id, value):
        with self.lock:
            resolved = self._resolve_provider(user_id, value)
        return self._catalog(resolved)

    def refresh_capabilities(self, user_id, provider_id):
        with self.lock:
            resolved, models = self._saved_provider(user_id, provider_id)
            version = self._capability_version(resolved, models)
        result = self._catalog(resolved)
        with self.lock:
            current, models = self._saved_provider(user_id, provider_id)
            if version != self._capability_version(current, models):
                raise ModelSelectionError("model_configuration_changed")
            profile = self._personal(user_id)
            if result["ok"]:
                profile.capabilities[provider_id] = CatalogSnapshot(version=version, checked_at=now(),
                    models={model: EffortCapability.model_validate(result["capabilities"].get(model, {})) for model in models})
                self._write_personal(user_id, profile)
            snapshot = profile.capabilities.get(provider_id)
            return {"ok": result["ok"], "capabilities": self.capabilities_for(user_id, provider_id),
                    "checked_at": snapshot.checked_at if snapshot and snapshot.version == version else None,
                    "message": result["message"]}

    def test_provider(self, user_id, value):
        with self.lock:
            resolved = self._resolve_provider(user_id, value)
        return self.probe(resolved)

    # Compatibility endpoints use the same provider store; no second credential copy.
    def view_for(self, user_id):
        with self.lock:
            profile = self._personal(user_id)
            personal = next((p for p in profile.providers if p.id == profile.selected_provider),
                            next(iter(profile.providers), None))
            return {"source": "default" if profile.selected_provider == "default" else "personal", "default": self.view(),
                    "personal": self.project(self._provider_settings(personal, profile.selected_model if personal.id == profile.selected_provider else None)) if personal else None}

    def save_for(self, user_id, value):
        with self.lock:
            profile = self._personal(user_id)
            provider_id = profile.selected_provider if profile.selected_provider != "default" else "personal"
            provider = ProviderInput(id=provider_id, name="自定义模型", models=[value.model],
                                     **value.model_dump(exclude={"model"}))
            self.save_provider(user_id, provider)
            self.select_provider(user_id, provider_id, value.model)
            return self.view_for(user_id)

    def select_for(self, user_id, source):
        with self.lock:
            profile = self._personal(user_id)
            profile.selected_effort = None
            if source == "default":
                profile.selected_provider, profile.selected_model = "default", ""
            elif source == "personal" and profile.providers:
                provider = profile.providers[0]
                profile.selected_provider, profile.selected_model = provider.id, provider.models[0]
            else:
                raise ValueError("personal_model_required")
            self._write_personal(user_id, profile)
            return self.view_for(user_id)

    def delete_for(self, user_id):
        with self.lock:
            self._personal_path(user_id).unlink(missing_ok=True)
            return self.view_for(user_id)

    def test_for(self, user_id, value):
        with self.lock:
            profile = self._personal(user_id)
            provider_id = profile.selected_provider if profile.selected_provider != "default" else "personal"
            provider = ProviderInput(id=provider_id, models=[value.model], **value.model_dump(exclude={"model"}))
        return self.test_provider(user_id, provider)
