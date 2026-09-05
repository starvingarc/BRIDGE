"""Logical resource and request bindings for Agent orchestration."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Annotated, Literal, Self, TYPE_CHECKING

from pydantic import ConfigDict, Field, StrictInt, field_validator, model_validator

from bridge.toolkit.contracts import (
    FrozenModel,
    InputAsset,
    StructuredInputRef,
    ToolRequest,
    ToolRequestV2,
)

if TYPE_CHECKING:
    from bridge.tool_packages._input_contracts import (
        AssetInputContract,
        ObjectInputModeContract,
        ObjectInputRoleContract,
        ToolInputContract,
    )
    from bridge.toolkit.registry import ToolRegistry


AGENT_INTEGRATION_PROFILE_SCHEMA_REF = "bridge://schemas/agent-integration-profile/v0.1"
_SLOT_ID_PATTERN = r"^[a-z][a-z0-9_-]*$"
_SCHEMA_REF_PATTERN = r"^bridge://schemas/[A-Za-z0-9][A-Za-z0-9._/-]*$"
_OBJECT_VERSION_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]*$"
_MEASUREMENT_SPEC_SCHEMA_REF = "bridge://schemas/measurement-spec/v0.1"
_MEASUREMENT_SPEC_OBJECT_VERSION = "0.1.0"

SlotId = Annotated[str, Field(pattern=_SLOT_ID_PATTERN)]
SchemaRef = Annotated[str, Field(pattern=_SCHEMA_REF_PATTERN)]
ObjectVersion = Annotated[str, Field(pattern=_OBJECT_VERSION_PATTERN)]


_RESOURCE_SLOT_JSON_SCHEMA_EXTRA = {
    "allOf": [
        {
            "if": {
                "properties": {"resource_type": {"const": "asset"}},
                "required": ["resource_type"],
            },
            "then": {
                "properties": {
                    "asset_contract": {"type": "object"},
                    "schema_ref": {"type": "null"},
                    "object_version": {"type": "null"},
                },
                "required": ["asset_contract"],
            },
        },
        {
            "if": {
                "properties": {"resource_type": {"const": "structured_object"}},
                "required": ["resource_type"],
            },
            "then": {
                "properties": {
                    "asset_contract": {"type": "null"},
                    "schema_ref": {"type": "string"},
                    "object_version": {"type": "string"},
                },
                "required": ["schema_ref", "object_version"],
            },
        },
        {
            "if": {
                "properties": {"source": {"const": "derived_output"}},
                "required": ["source"],
            },
            "then": {
                "properties": {
                    "producer_binding_id": {"type": "string"},
                    "artifact_kind": {"type": "string"},
                    "depends_on_slots": {"maxItems": 0},
                },
                "required": ["producer_binding_id", "artifact_kind"],
            },
        },
        {
            "if": {
                "properties": {"source": {"const": "agent_constructed"}},
                "required": ["source"],
            },
            "then": {
                "properties": {
                    "producer_binding_id": {"type": "null"},
                    "artifact_kind": {"type": "null"},
                    "depends_on_slots": {"minItems": 1},
                },
                "required": ["depends_on_slots"],
            },
        },
        {
            "if": {
                "properties": {
                    "source": {
                        "enum": ["user_upload", "system_resource"],
                    }
                },
                "required": ["source"],
            },
            "then": {
                "properties": {
                    "producer_binding_id": {"type": "null"},
                    "artifact_kind": {"type": "null"},
                    "depends_on_slots": {"maxItems": 0},
                }
            },
        },
    ]
}


class IntegrationAssetContract(FrozenModel):
    format: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.+-]*$")
    assay: str = Field(min_length=1)
    input_level: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    matrix_semantics: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    required_metadata_keys: list[str] = Field(
        default_factory=list,
        json_schema_extra={"uniqueItems": True},
    )

    @field_validator("required_metadata_keys")
    @classmethod
    def metadata_keys_are_unique(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("asset metadata keys must be unique")
        return value


class IntegrationResourceSlot(FrozenModel):
    model_config = ConfigDict(json_schema_extra=_RESOURCE_SLOT_JSON_SCHEMA_EXTRA)

    slot_id: SlotId
    source: Literal[
        "user_upload",
        "system_resource",
        "derived_output",
        "agent_constructed",
    ]
    resource_type: Literal["asset", "structured_object"]
    schema_ref: SchemaRef | None = None
    object_version: ObjectVersion | None = None
    min_count: StrictInt = Field(default=1, ge=1)
    max_count: StrictInt | None = Field(default=1, ge=1)
    asset_contract: IntegrationAssetContract | None = None
    producer_binding_id: str | None = Field(
        default=None,
        pattern=r"^[a-z][a-z0-9_-]*$",
    )
    artifact_kind: str | None = Field(
        default=None,
        pattern=r"^[a-z][a-z0-9_]*$",
    )
    depends_on_slots: list[SlotId] = Field(
        default_factory=list,
        json_schema_extra={"uniqueItems": True},
    )

    @field_validator("depends_on_slots")
    @classmethod
    def dependencies_are_unique(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("resource dependencies must be unique")
        return value

    @model_validator(mode="after")
    def resource_shape_is_coherent(self) -> Self:
        if self.max_count is not None and self.max_count < self.min_count:
            raise ValueError("resource max_count cannot be smaller than min_count")
        if self.resource_type == "asset":
            if self.asset_contract is None:
                raise ValueError("asset resource requires asset_contract")
            if self.schema_ref is not None or self.object_version is not None:
                raise ValueError(
                    "asset resource cannot declare object Schema or version"
                )
        else:
            if self.asset_contract is not None:
                raise ValueError("structured object cannot declare asset_contract")
            if self.schema_ref is None or self.object_version is None:
                raise ValueError("structured object requires Schema and object version")

        if self.source == "derived_output":
            if self.producer_binding_id is None or self.artifact_kind is None:
                raise ValueError(
                    "derived output requires producer_binding_id and artifact_kind"
                )
            if self.depends_on_slots:
                raise ValueError("derived output dependencies come from its producer")
        elif self.source == "agent_constructed":
            if not self.depends_on_slots:
                raise ValueError("agent-constructed object requires depends_on_slots")
            if self.producer_binding_id is not None or self.artifact_kind is not None:
                raise ValueError(
                    "agent-constructed object cannot claim a tool producer"
                )
        elif (
            self.producer_binding_id is not None
            or self.artifact_kind is not None
            or self.depends_on_slots
        ):
            raise ValueError(
                "uploaded and system resources cannot claim producers or dependencies"
            )
        return self


class IntegrationObjectInput(FrozenModel):
    slot_id: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    role: str = Field(pattern=r"^[a-z][a-z0-9_]*$")


class IntegrationRequestBinding(FrozenModel):
    binding_id: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    tool_id: str = Field(pattern=r"^P0-(0[1-9]|1[0-2])$")
    tool_version: str = Field(min_length=1)
    request_schema_ref: Literal[
        "bridge://schemas/tool-request/v0.1",
        "bridge://schemas/tool-request/v0.2",
    ]
    mode_id: str | None = Field(
        default=None,
        pattern=r"^[a-z][a-z0-9_]*$",
    )
    asset_slot_ids: list[str] = Field(
        default_factory=list,
        json_schema_extra={"uniqueItems": True},
    )
    object_inputs: list[IntegrationObjectInput] = Field(
        default_factory=list,
        json_schema_extra={"uniqueItems": True},
    )
    measurement_spec_slot_id: str | None = Field(
        default=None,
        pattern=r"^[a-z][a-z0-9_-]*$",
    )

    @model_validator(mode="after")
    def slot_bindings_are_unique(self) -> Self:
        object_slots = [item.slot_id for item in self.object_inputs]
        if len(self.asset_slot_ids) != len(set(self.asset_slot_ids)):
            raise ValueError("asset slots must be unique within a request binding")
        if len(object_slots) != len(set(object_slots)):
            raise ValueError("object slots must be unique within a request binding")
        used = [*self.asset_slot_ids, *object_slots]
        if self.measurement_spec_slot_id is not None:
            used.append(self.measurement_spec_slot_id)
        if len(used) != len(set(used)):
            raise ValueError("one request cannot bind a slot through multiple channels")
        return self


class AgentIntegrationProfile(FrozenModel):
    profile_id: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    object_version: Literal["0.1.0"] = "0.1.0"
    schema_ref: Literal["bridge://schemas/agent-integration-profile/v0.1"] = (
        AGENT_INTEGRATION_PROFILE_SCHEMA_REF
    )
    resource_slots: list[IntegrationResourceSlot] = Field(
        default_factory=list,
        json_schema_extra={"uniqueItems": True},
    )
    request_bindings: list[IntegrationRequestBinding] = Field(
        min_length=1,
        json_schema_extra={"uniqueItems": True},
    )

    @model_validator(mode="after")
    def references_are_closed_and_acyclic(self) -> Self:
        slot_ids = [item.slot_id for item in self.resource_slots]
        binding_ids = [item.binding_id for item in self.request_bindings]
        if len(slot_ids) != len(set(slot_ids)):
            raise ValueError("resource slot IDs must be unique")
        if len(binding_ids) != len(set(binding_ids)):
            raise ValueError("request binding IDs must be unique")

        known_slots = set(slot_ids)
        known_bindings = set(binding_ids)
        edges: dict[str, set[str]] = defaultdict(set)
        for slot in self.resource_slots:
            node = f"slot:{slot.slot_id}"
            for dependency in slot.depends_on_slots:
                if dependency not in known_slots:
                    raise ValueError(f"unknown resource slot dependency: {dependency}")
                edges[f"slot:{dependency}"].add(node)
            if slot.producer_binding_id is not None:
                if slot.producer_binding_id not in known_bindings:
                    raise ValueError(
                        f"unknown producer binding: {slot.producer_binding_id}"
                    )
                edges[f"binding:{slot.producer_binding_id}"].add(node)

        for binding in self.request_bindings:
            references = [
                *binding.asset_slot_ids,
                *(item.slot_id for item in binding.object_inputs),
            ]
            if binding.measurement_spec_slot_id is not None:
                references.append(binding.measurement_spec_slot_id)
            for slot_id in references:
                if slot_id not in known_slots:
                    raise ValueError(f"unknown resource slot: {slot_id}")
                edges[f"slot:{slot_id}"].add(f"binding:{binding.binding_id}")

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visiting:
                raise ValueError("integration dependency graph must be acyclic")
            if node in visited:
                return
            visiting.add(node)
            for target in edges[node]:
                visit(target)
            visiting.remove(node)
            visited.add(node)

        for node in set(edges) | {
            target for targets in edges.values() for target in targets
        }:
            visit(node)
        return self


def _default_registry() -> ToolRegistry:
    from bridge.toolkit.registry import ToolRegistry

    return ToolRegistry.load_default()


def _combined_max(slots: list[IntegrationResourceSlot]) -> int | None:
    if any(slot.max_count is None for slot in slots):
        return None
    return sum(slot.max_count or 0 for slot in slots)


def _validate_cardinality(
    slots: list[IntegrationResourceSlot],
    minimum: int,
    maximum: int | None,
    label: str,
) -> None:
    declared_minimum = sum(slot.min_count for slot in slots)
    declared_maximum = _combined_max(slots)
    if declared_minimum < minimum:
        raise ValueError(f"profile contract mismatch: {label} minimum cardinality")
    if maximum is not None and (declared_maximum is None or declared_maximum > maximum):
        raise ValueError(f"profile contract mismatch: {label} maximum cardinality")


def _mode_for_binding(
    contract: ToolInputContract,
    binding: IntegrationRequestBinding,
) -> ObjectInputModeContract | None:
    if contract.request_schema_ref.endswith("/v0.1"):
        if binding.mode_id is not None:
            raise ValueError(
                "profile contract mismatch: v0.1 request has no input mode"
            )
        return None
    if binding.mode_id is None:
        raise ValueError("profile contract mismatch: v0.2 request requires input mode")
    modes = {mode.mode_id: mode for mode in contract.object_input_modes}
    try:
        return modes[binding.mode_id]
    except KeyError as exc:
        raise ValueError(
            f"profile contract mismatch: unknown input mode {binding.mode_id}"
        ) from exc


def _validate_asset_slot(
    slot: IntegrationResourceSlot,
    contract: AssetInputContract,
) -> None:
    if slot.resource_type != "asset" or slot.asset_contract is None:
        raise ValueError("profile contract mismatch: asset channel requires asset slot")
    declared = slot.asset_contract
    for value, allowed, label in (
        (declared.format, contract.formats, "format"),
        (declared.assay, contract.assays, "assay"),
        (declared.input_level, contract.input_levels, "input level"),
        (declared.matrix_semantics, contract.matrix_semantics, "matrix semantics"),
    ):
        if allowed and value not in allowed:
            raise ValueError(f"profile contract mismatch: unsupported asset {label}")
    if not set(contract.required_metadata_keys).issubset(
        declared.required_metadata_keys
    ):
        raise ValueError("profile contract mismatch: required asset metadata is absent")


def _validate_object_slot(
    slot: IntegrationResourceSlot,
    role: ObjectInputRoleContract,
) -> None:
    if slot.resource_type != "structured_object":
        raise ValueError(
            "profile contract mismatch: object role requires structured slot"
        )
    if slot.schema_ref not in role.schema_refs:
        raise ValueError("profile contract mismatch: object role Schema mismatch")
    if (
        role.object_version_policy == "fixed"
        and slot.object_version not in role.object_versions
    ):
        raise ValueError("profile contract mismatch: object role version mismatch")


def validate_agent_integration_profile(
    profile: AgentIntegrationProfile,
    registry: ToolRegistry | None = None,
) -> AgentIntegrationProfile:
    """Validate a logical integration profile against live package contracts."""

    active_registry = registry or _default_registry()
    slots = {item.slot_id: item for item in profile.resource_slots}
    for slot in profile.resource_slots:
        if slot.resource_type == "structured_object":
            assert slot.schema_ref is not None
            try:
                active_registry.resolve_schema(slot.schema_ref)
            except (KeyError, FileNotFoundError) as exc:
                raise ValueError(
                    f"profile contract mismatch: unregistered Schema {slot.schema_ref}"
                ) from exc
        if slot.source == "derived_output":
            assert slot.producer_binding_id is not None
            if slot.artifact_kind == "measurement_result_v2" and (
                slot.schema_ref != "bridge://schemas/measurement-result/v0.2"
            ):
                raise ValueError(
                    "profile contract mismatch: measurement artifact Schema mismatch"
                )

    for binding in profile.request_bindings:
        spec = active_registry.describe(binding.tool_id)
        contract = active_registry.describe_input(binding.tool_id)
        if binding.tool_version != spec.version:
            raise ValueError(
                "profile contract mismatch: tool version differs from registry"
            )
        if binding.request_schema_ref != contract.request_schema_ref:
            raise ValueError(
                "profile contract mismatch: request Schema differs from registry"
            )
        mode = _mode_for_binding(contract, binding)

        asset_contract = (
            mode.asset_input if mode and mode.asset_input else contract.asset_input
        )
        asset_slot_ids = [slots[slot_id] for slot_id in binding.asset_slot_ids]
        if asset_contract is None:
            if asset_slot_ids:
                raise ValueError(
                    "profile contract mismatch: tool mode does not accept assets"
                )
        else:
            _validate_cardinality(
                asset_slot_ids,
                asset_contract.min_count,
                asset_contract.max_count,
                "asset",
            )
            for slot in asset_slot_ids:
                _validate_asset_slot(slot, asset_contract)

        policy = contract.measurement_spec_ref_policy
        if policy == "required" and binding.measurement_spec_slot_id is None:
            raise ValueError(
                "profile contract mismatch: measurement_spec_ref is required"
            )
        if policy == "forbidden" and binding.measurement_spec_slot_id is not None:
            raise ValueError(
                "profile contract mismatch: measurement_spec_ref is forbidden"
            )
        if binding.measurement_spec_slot_id is not None:
            measurement_slot = slots[binding.measurement_spec_slot_id]
            if measurement_slot.resource_type != "structured_object":
                raise ValueError(
                    "profile contract mismatch: measurement_spec_ref requires structured slot"
                )
            if (
                measurement_slot.schema_ref != _MEASUREMENT_SPEC_SCHEMA_REF
                or measurement_slot.object_version
                != _MEASUREMENT_SPEC_OBJECT_VERSION
            ):
                raise ValueError(
                    "profile contract mismatch: unsupported measurement Spec Schema or version"
                )

        role_contracts = {role.role: role for role in (mode.roles if mode else [])}
        bound_by_role: dict[str, list[IntegrationResourceSlot]] = defaultdict(list)
        for object_binding in binding.object_inputs:
            try:
                role = role_contracts[object_binding.role]
            except KeyError as exc:
                raise ValueError(
                    f"profile contract mismatch: unknown object role {object_binding.role}"
                ) from exc
            slot = slots[object_binding.slot_id]
            _validate_object_slot(slot, role)
            bound_by_role[role.role].append(slot)
        for role in role_contracts.values():
            _validate_cardinality(
                bound_by_role[role.role],
                role.min_count,
                role.max_count,
                f"role {role.role}",
            )
    return profile


def _asset_matches(asset: InputAsset, slot: IntegrationResourceSlot) -> bool:
    declared = slot.asset_contract
    assert declared is not None
    return (
        asset.format == declared.format
        and asset.assay == declared.assay
        and asset.input_level.value == declared.input_level
        and asset.matrix_semantics == declared.matrix_semantics
        and set(declared.required_metadata_keys).issubset(asset.metadata)
    )


def _expected_object_counts(
    binding: IntegrationRequestBinding,
    slots: dict[str, IntegrationResourceSlot],
) -> tuple[Counter[tuple[str, str, str]], dict[tuple[str, str, str], int | None]]:
    minimum: Counter[tuple[str, str, str]] = Counter()
    maximum_parts: dict[tuple[str, str, str], list[int | None]] = defaultdict(list)
    for item in binding.object_inputs:
        slot = slots[item.slot_id]
        assert slot.schema_ref is not None and slot.object_version is not None
        key = (item.role, slot.schema_ref, slot.object_version)
        minimum[key] += slot.min_count
        maximum_parts[key].append(slot.max_count)
    maximum = {
        key: None if any(value is None for value in values) else sum(values)
        for key, values in maximum_parts.items()
    }
    return minimum, maximum


def validate_profile_request(
    profile: AgentIntegrationProfile,
    binding_id: str,
    request: ToolRequest | ToolRequestV2,
    registry: ToolRegistry | None = None,
) -> ToolRequest | ToolRequestV2:
    """Bind an already materialized request to one declared profile step."""

    active_registry = registry or _default_registry()
    validate_agent_integration_profile(profile, active_registry)
    binding = next(
        (item for item in profile.request_bindings if item.binding_id == binding_id),
        None,
    )
    if binding is None:
        raise ValueError(f"request_binding_mismatch: unknown binding {binding_id}")
    if (
        request.tool_id != binding.tool_id
        or request.tool_version != binding.tool_version
    ):
        raise ValueError("request_binding_mismatch: tool identity or version")
    expects_v2 = binding.request_schema_ref.endswith("/v0.2")
    if expects_v2 != isinstance(request, ToolRequestV2):
        raise ValueError("request_binding_mismatch: request envelope version")

    slots = {item.slot_id: item for item in profile.resource_slots}
    expected_assets = [slots[slot_id] for slot_id in binding.asset_slot_ids]
    minimum_assets = sum(slot.min_count for slot in expected_assets)
    maximum_assets = _combined_max(expected_assets)
    matching_assets = [
        asset
        for asset in request.assets
        if any(_asset_matches(asset, slot) for slot in expected_assets)
    ]
    if len(matching_assets) < minimum_assets:
        raise ValueError("unresolved_input_slot: required asset slot")
    if len(matching_assets) != len(request.assets) or (
        maximum_assets is not None and len(request.assets) > maximum_assets
    ):
        raise ValueError("request_binding_mismatch: asset slot")

    expects_measurement = binding.measurement_spec_slot_id is not None
    if expects_measurement and request.measurement_spec_ref is None:
        raise ValueError(f"unresolved_input_slot: {binding.measurement_spec_slot_id}")
    if not expects_measurement and request.measurement_spec_ref is not None:
        raise ValueError("request_binding_mismatch: unexpected measurement_spec_ref")

    actual_inputs: list[StructuredInputRef] = (
        request.object_inputs if isinstance(request, ToolRequestV2) else []
    )
    actual_counts = Counter(
        (item.role, item.schema_ref, item.object_version) for item in actual_inputs
    )
    minimum_counts, maximum_counts = _expected_object_counts(binding, slots)
    for key, minimum in minimum_counts.items():
        if actual_counts[key] < minimum:
            raise ValueError(f"unresolved_input_slot: object role {key[0]}")
    for key, count in actual_counts.items():
        if key not in minimum_counts:
            raise ValueError("request_binding_mismatch: unexpected object input")
        maximum = maximum_counts[key]
        if maximum is not None and count > maximum:
            raise ValueError("request_binding_mismatch: object input cardinality")
    return request
