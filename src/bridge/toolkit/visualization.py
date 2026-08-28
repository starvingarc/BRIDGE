from __future__ import annotations

from enum import StrEnum
import re
from typing import Literal, Self

from pydantic import (
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

from bridge.toolkit.contracts import EvidenceState, FrozenModel


_SHA256 = r"^[0-9a-f]{64}$"
_VERSION = r"^[0-9]+\.[0-9]+\.[0-9]+$"
_COMPONENT_ID = r"^bridge\.[a-z0-9]+(?:[._-][a-z0-9]+)+$"
_PUBLIC_STATE_ID = r"^[A-Za-z][A-Za-z0-9_.-]*$"
_PUBLISHED_REF = (
    r"^(?:bridge://[A-Za-z0-9._~:/@+%-]+|"
    r"(?:artifact|run|visualization):[A-Za-z0-9._~:/@+-]+|"
    r"[A-Za-z][A-Za-z0-9._-]*)$"
)
_SCHEMA_REF = r"^bridge://schemas/[a-z0-9-]+/v[0-9]+\.[0-9]+$"
_TOOL_ID = r"^P0-(0[1-9]|1[0-2])$"


def _all_or_none_json_schema(*fields: str) -> dict[str, object]:
    return {
        "oneOf": [
            {"properties": {field: {"type": "null"} for field in fields}},
            {
                "required": list(fields),
                "properties": {
                    field: {"not": {"type": "null"}} for field in fields
                },
            },
        ]
    }


def _unique_items_json_schema(*fields: str) -> dict[str, object]:
    return {
        "properties": {field: {"uniqueItems": True} for field in fields}
    }


def _unique(values: list[object], field_name: str) -> list[object]:
    keys = [str(value) for value in values]
    if len(keys) != len(set(keys)):
        raise ValueError(f"{field_name} must not contain duplicates")
    return values


class FigureRegistryState(StrEnum):
    LEGACY_UNTYPED = "legacy_untyped"
    TYPED_CANDIDATE = "typed_candidate"


class FigureSurface(StrEnum):
    DESKTOP = "desktop"
    MOBILE_PORTRAIT = "mobile_portrait"
    STATIC_EXPORT = "static_export"
    TABLE = "table"


class FigureRole(StrEnum):
    MAIN = "main"
    SUPPORTING = "supporting"


class VisualizationInteraction(StrEnum):
    FILTER = "filter"
    SELECT = "select"
    DRILL_DOWN = "drill_down"


class VisualizationDataBinding(FrozenModel):
    """Renderer-independent binding to one typed, immutable data object."""

    model_config = ConfigDict(
        json_schema_extra={
            "allOf": [
                _all_or_none_json_schema(
                    "numerator_field",
                    "denominator_field",
                    "denominator_scope_field",
                ),
                _all_or_none_json_schema(
                    "interval_lower_field",
                    "interval_upper_field",
                    "interval_semantics",
                ),
                {
                    "anyOf": [
                        {
                            "required": ["value_field"],
                            "properties": {"value_field": {"type": "string"}},
                        },
                        {
                            "required": ["numerator_field"],
                            "properties": {"numerator_field": {"type": "string"}},
                        },
                    ]
                },
            ]
        },
    )

    artifact_id: str = Field(min_length=1, pattern=_PUBLISHED_REF)
    schema_ref: str = Field(pattern=_SCHEMA_REF)
    object_version: str = Field(pattern=_VERSION)
    sha256: str = Field(pattern=_SHA256)
    media_type: Literal["application/json"] = "application/json"
    records_path: str = Field(min_length=1, pattern=_PUBLIC_STATE_ID)
    record_lookup_key: str = Field(min_length=1, pattern=_PUBLIC_STATE_ID)
    evidence_ids_field: str = Field(min_length=1, pattern=_PUBLIC_STATE_ID)
    value_field: str | None = Field(default=None, pattern=_PUBLIC_STATE_ID)
    numerator_field: str | None = Field(default=None, pattern=_PUBLIC_STATE_ID)
    denominator_field: str | None = Field(default=None, pattern=_PUBLIC_STATE_ID)
    denominator_scope_field: str | None = Field(
        default=None,
        pattern=_PUBLIC_STATE_ID,
    )
    unit_field: str | None = Field(default=None, pattern=_PUBLIC_STATE_ID)
    interval_lower_field: str | None = Field(default=None, pattern=_PUBLIC_STATE_ID)
    interval_upper_field: str | None = Field(default=None, pattern=_PUBLIC_STATE_ID)
    interval_semantics: str | None = Field(default=None, min_length=1)
    evidence_state_field: str = Field(min_length=1, pattern=_PUBLIC_STATE_ID)
    scientific_status_field: str = Field(min_length=1, pattern=_PUBLIC_STATE_ID)
    missingness_field: str = Field(min_length=1, pattern=_PUBLIC_STATE_ID)
    applicability_field: str = Field(min_length=1, pattern=_PUBLIC_STATE_ID)

    @model_validator(mode="after")
    def quantitative_fields_are_coherent(self) -> Self:
        quantity_fields = (
            self.numerator_field,
            self.denominator_field,
            self.denominator_scope_field,
        )
        if any(quantity_fields) and not all(quantity_fields):
            raise ValueError(
                "numerator, denominator and denominator-scope fields must be "
                "declared together"
            )
        if self.value_field is None and self.numerator_field is None:
            raise ValueError("visualization data must bind a value or numerator")
        interval_fields = (
            self.interval_lower_field,
            self.interval_upper_field,
            self.interval_semantics,
        )
        if any(interval_fields) and not all(interval_fields):
            raise ValueError(
                "interval lower, upper and semantics must be declared together"
            )
        return self


class VisualizationContextBinding(FrozenModel):
    role: Literal[
        "product_case",
        "product_definition",
        "measurement_spec",
        "data_view",
        "reference",
        "method",
        "environment",
        "source_family",
    ]
    ref: str = Field(min_length=1, pattern=_PUBLISHED_REF)
    version: str = Field(min_length=1)
    sha256: str = Field(pattern=_SHA256)


class VisualizationInteractionContract(FrozenModel):
    model_config = ConfigDict(
        json_schema_extra={
            "allOf": [
                _unique_items_json_schema(
                    "filter_ids",
                    "selection_ids",
                    "drill_down_ids",
                )
            ]
        },
    )

    filter_ids: list[str] = Field(default_factory=list)
    selection_ids: list[str] = Field(default_factory=list)
    drill_down_ids: list[str] = Field(default_factory=list)

    @field_validator("filter_ids", "selection_ids", "drill_down_ids")
    @classmethod
    def public_state_ids_are_unique(
        cls,
        values: list[str],
        info: ValidationInfo,
    ) -> list[str]:
        for value in values:
            if re.fullmatch(_PUBLIC_STATE_ID, value) is None:
                raise ValueError(f"{info.field_name} contains an invalid public ID")
        return _unique(values, info.field_name)


class VisualizationAccessibility(FrozenModel):
    alt_text: str = Field(min_length=12, max_length=240)
    long_description: str = Field(min_length=40)
    table_artifact_id: str = Field(min_length=1, pattern=_PUBLISHED_REF)


class VisualizationRenderBinding(FrozenModel):
    artifact_id: str = Field(min_length=1, pattern=_PUBLISHED_REF)
    media_type: Literal["image/svg+xml", "application/pdf", "image/png"]
    renderer_id: str = Field(min_length=1)
    renderer_version: str = Field(min_length=1)
    export_profile_id: str = Field(min_length=1)
    data_sha256: str = Field(pattern=_SHA256)
    config_sha256: str = Field(pattern=_SHA256)


class VisualizationArtifactV2(FrozenModel):
    """Portable figure contract; it is not embedded in ToolRun v0.1/v0.2."""

    model_config = ConfigDict(
        json_schema_extra={
            "allOf": [
                _unique_items_json_schema(
                    "evidence_ids",
                    "evidence_states",
                    "missing_reason_codes",
                    "limitations",
                ),
                _all_or_none_json_schema(
                    "denominator_label",
                    "denominator_scope",
                ),
                {
                    "properties": {
                        "component_id": {
                            "not": {"pattern": r"\.v[0-9]+\.[0-9]+$"}
                        }
                    }
                },
                {
                    "if": {
                        "required": ["evidence_states"],
                        "properties": {
                            "evidence_states": {
                                "contains": {
                                    "enum": [
                                        "missing",
                                        "unknown",
                                        "unavailable",
                                    ]
                                }
                            }
                        },
                    },
                    "then": {
                        "properties": {
                            "missing_reason_codes": {"minItems": 1}
                        }
                    },
                },
            ]
        },
    )

    object_version: Literal["0.2.0"] = "0.2.0"
    visualization_id: str = Field(min_length=1, pattern=_PUBLISHED_REF)
    component_id: str = Field(pattern=_COMPONENT_ID)
    component_version: str = Field(pattern=_VERSION)
    data_binding: VisualizationDataBinding
    producer_tool_id: str = Field(pattern=_TOOL_ID)
    producer_tool_version: str = Field(min_length=1)
    producer_run_ref: str = Field(min_length=1, pattern=_PUBLISHED_REF)
    evidence_ids: list[str] = Field(min_length=1)
    evidence_states: list[EvidenceState] = Field(min_length=1)
    scientific_status: str = Field(min_length=1)
    applicability: Literal[
        "applicable",
        "partially_applicable",
        "not_applicable",
        "not_assessed",
    ]
    missing_reason_codes: list[str] = Field(default_factory=list)
    denominator_label: str | None = Field(default=None, min_length=1)
    denominator_scope: str | None = Field(default=None, min_length=1)
    unit: str | None = Field(default=None, min_length=1)
    interval_semantics: str | None = Field(default=None, min_length=1)
    context_bindings: list[VisualizationContextBinding] = Field(default_factory=list)
    interactions: VisualizationInteractionContract = Field(
        default_factory=VisualizationInteractionContract
    )
    insight_title: str = Field(min_length=1)
    takeaway: str = Field(min_length=1)
    limitations: list[str] = Field(min_length=1)
    accessibility: VisualizationAccessibility
    renders: list[VisualizationRenderBinding] = Field(min_length=1)

    @field_validator(
        "evidence_ids",
        "evidence_states",
        "missing_reason_codes",
        "limitations",
    )
    @classmethod
    def lists_are_unique(
        cls,
        values: list[object],
        info: ValidationInfo,
    ) -> list[object]:
        return _unique(values, info.field_name)

    @model_validator(mode="after")
    def semantics_and_provenance_are_coherent(self) -> Self:
        if re.search(r"\.v[0-9]+\.[0-9]+$", self.component_id):
            raise ValueError("component version must not be embedded in component_id")
        if (self.denominator_label is None) != (self.denominator_scope is None):
            raise ValueError("denominator label and scope must be paired")
        reason_required = {
            EvidenceState.MISSING,
            EvidenceState.UNKNOWN,
            EvidenceState.UNAVAILABLE,
        }.intersection(self.evidence_states)
        if reason_required and not self.missing_reason_codes:
            raise ValueError(
                "missing, unknown or unavailable evidence requires reason codes"
            )
        context_keys = [
            (item.role, item.ref, item.version)
            for item in self.context_bindings
        ]
        _unique(context_keys, "context_bindings")
        if any(item.data_sha256 != self.data_binding.sha256 for item in self.renders):
            raise ValueError("every render must bind the exact visualization data hash")
        return self

    @property
    def component_ref(self) -> str:
        return f"{self.component_id}@{self.component_version}"


class FigureComponentSpec(FrozenModel):
    model_config = ConfigDict(
        json_schema_extra={
            "allOf": [
                _unique_items_json_schema(
                    "legacy_component_ids",
                    "producer_tool_ids",
                    "data_schema_refs",
                    "surfaces",
                    "interactions",
                    "required_fallbacks",
                ),
                {
                    "if": {
                        "required": ["registry_state"],
                        "properties": {
                            "registry_state": {"const": "legacy_untyped"}
                        },
                    },
                    "then": {
                        "properties": {
                            "legacy_component_ids": {"minItems": 1},
                            "data_schema_refs": {"maxItems": 0},
                        }
                    },
                    "else": {
                        "properties": {
                            "data_schema_refs": {"minItems": 1}
                        }
                    },
                },
            ]
        },
    )

    component_id: str = Field(pattern=_COMPONENT_ID)
    component_version: str = Field(pattern=_VERSION)
    legacy_component_ids: list[str] = Field(default_factory=list)
    title: str = Field(min_length=1)
    question: str = Field(min_length=1)
    figure_family: str = Field(min_length=1)
    producer_tool_ids: list[str] = Field(min_length=1)
    registry_state: FigureRegistryState
    default_role: FigureRole
    scientific_status_source: Literal["producer_run"] = "producer_run"
    data_schema_refs: list[str] = Field(default_factory=list)
    surfaces: list[FigureSurface] = Field(min_length=1)
    interactions: list[VisualizationInteraction] = Field(default_factory=list)
    required_fallbacks: list[
        Literal["table", "alt_text", "long_description", "static_vector"]
    ] = Field(default_factory=list)

    @field_validator(
        "legacy_component_ids",
        "producer_tool_ids",
        "data_schema_refs",
        "surfaces",
        "interactions",
        "required_fallbacks",
    )
    @classmethod
    def registry_lists_are_unique(
        cls,
        values: list[object],
        info: ValidationInfo,
    ) -> list[object]:
        return _unique(values, info.field_name)

    @field_validator("producer_tool_ids")
    @classmethod
    def tool_ids_are_valid(cls, values: list[str]) -> list[str]:
        if any(re.fullmatch(_TOOL_ID, value) is None for value in values):
            raise ValueError("producer_tool_ids contains an invalid Tool ID")
        return values

    @field_validator("data_schema_refs")
    @classmethod
    def data_schema_refs_are_valid(cls, values: list[str]) -> list[str]:
        if any(re.fullmatch(_SCHEMA_REF, value) is None for value in values):
            raise ValueError("data_schema_refs contains an invalid Schema URI")
        return values

    @model_validator(mode="after")
    def registry_state_is_truthful(self) -> Self:
        if self.registry_state is FigureRegistryState.LEGACY_UNTYPED:
            if not self.legacy_component_ids or self.data_schema_refs:
                raise ValueError(
                    "legacy_untyped components require legacy IDs and no typed data schema"
                )
        elif not self.data_schema_refs:
            raise ValueError("typed_candidate components require a data schema")
        return self

    @property
    def component_ref(self) -> str:
        return f"{self.component_id}@{self.component_version}"


class FigureRegistrySnapshot(FrozenModel):
    registry_id: Literal["bridge.figure-registry"] = "bridge.figure-registry"
    object_version: Literal["0.1.0"] = "0.1.0"
    components: list[FigureComponentSpec]

    @model_validator(mode="after")
    def component_identities_are_unique(self) -> Self:
        _unique(
            [component.component_ref for component in self.components],
            "component references",
        )
        _unique(
            [
                legacy_id
                for component in self.components
                for legacy_id in component.legacy_component_ids
            ],
            "legacy component IDs",
        )
        return self


def _legacy_component(
    component_id: str,
    legacy_component_id: str,
    *,
    title: str,
    question: str,
    figure_family: str,
    tool_id: str,
    default_role: FigureRole = FigureRole.SUPPORTING,
) -> FigureComponentSpec:
    return FigureComponentSpec(
        component_id=component_id,
        component_version="0.1.0",
        legacy_component_ids=[legacy_component_id],
        title=title,
        question=question,
        figure_family=figure_family,
        producer_tool_ids=[tool_id],
        registry_state=FigureRegistryState.LEGACY_UNTYPED,
        default_role=default_role,
        surfaces=[FigureSurface.STATIC_EXPORT],
    )


_DEFAULT_COMPONENTS = (
    _legacy_component(
        "bridge.qc.overview",
        "bridge.qc.overview.v0.1",
        title="QC metric distributions",
        question="Can the uploaded observations support the requested analyses?",
        figure_family="distribution_small_multiples",
        tool_id="P0-01",
    ),
    _legacy_component(
        "bridge.qc.counts_genes",
        "bridge.qc.counts_genes.v0.1",
        title="Counts and detected genes",
        question="Do count depth, detected genes and mitochondrial signal reveal QC structure?",
        figure_family="scatter",
        tool_id="P0-01",
    ),
    _legacy_component(
        "bridge.cell_state.composition-l1",
        "bridge.cell_state.composition-l1.v0.1",
        title="Broad cell-state composition",
        question="Which broad cell states are present in the product?",
        figure_family="composition",
        tool_id="P0-02",
        default_role=FigureRole.MAIN,
    ),
    _legacy_component(
        "bridge.cell_state.composition-l2",
        "bridge.cell_state.composition-l2.v0.1",
        title="Detailed cell-state composition",
        question="Which reviewed detailed states are present among eligible observations?",
        figure_family="composition",
        tool_id="P0-02",
    ),
    _legacy_component(
        "bridge.cell_state.reference-support",
        "bridge.cell_state.reference-support.v0.1",
        title="Reference support",
        question="How consistently do independent references support each state?",
        figure_family="evidence_matrix",
        tool_id="P0-02",
    ),
    _legacy_component(
        "bridge.cell_state.conflicts",
        "bridge.cell_state.conflicts.v0.1",
        title="Source agreement and conflict",
        question="Where do reference sources agree, conflict or remain unavailable?",
        figure_family="status_counts",
        tool_id="P0-02",
    ),
    _legacy_component(
        "bridge.cell_state.marker",
        "bridge.cell_state.marker.v0.1",
        title="Marker evidence",
        question="Do reviewed marker programs support the proposed cell-state labels?",
        figure_family="evidence_matrix",
        tool_id="P0-02",
    ),
)


class FigureRegistry:
    """Read-only discovery and validation for renderer-independent figures."""

    def __init__(self, snapshot: FigureRegistrySnapshot) -> None:
        self.snapshot = snapshot
        self._by_ref = {
            component.component_ref: component for component in snapshot.components
        }
        self._by_legacy = {
            legacy_id: component
            for component in snapshot.components
            for legacy_id in component.legacy_component_ids
        }

    @classmethod
    def load_default(cls) -> FigureRegistry:
        return cls(FigureRegistrySnapshot(components=list(_DEFAULT_COMPONENTS)))

    def list(self, *, tool_id: str | None = None) -> list[FigureComponentSpec]:
        components = self.snapshot.components
        if tool_id is not None:
            components = [
                component
                for component in components
                if tool_id in component.producer_tool_ids
            ]
        return sorted(components, key=lambda item: item.component_ref)

    def get(self, component_ref: str) -> FigureComponentSpec:
        try:
            return self._by_ref.get(component_ref) or self._by_legacy[component_ref]
        except KeyError as exc:
            raise KeyError(component_ref) from exc

    def validate_artifact(
        self,
        artifact: VisualizationArtifactV2,
    ) -> FigureComponentSpec:
        component = self.get(artifact.component_ref)
        if component.registry_state is not FigureRegistryState.TYPED_CANDIDATE:
            raise ValueError(
                "figure component has not migrated to typed visualization data"
            )
        if artifact.producer_tool_id not in component.producer_tool_ids:
            raise ValueError(
                "figure producer Tool ID is not registered for the component"
            )
        if artifact.data_binding.schema_ref not in component.data_schema_refs:
            raise ValueError(
                "visualization data schema is not registered for the component"
            )
        return component

    def validation_summary(self) -> dict[str, object]:
        components = self.snapshot.components
        typed_count = sum(
            item.registry_state is FigureRegistryState.TYPED_CANDIDATE
            for item in components
        )
        return {
            "valid": True,
            "registry_id": self.snapshot.registry_id,
            "object_version": self.snapshot.object_version,
            "component_count": len(components),
            "typed_candidate_count": typed_count,
            "legacy_untyped_count": len(components) - typed_count,
            "producer_tool_ids": sorted(
                {
                    tool_id
                    for component in components
                    for tool_id in component.producer_tool_ids
                }
            ),
        }
