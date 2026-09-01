from __future__ import annotations

from enum import StrEnum
import re
from typing import Annotated, Literal, Self

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
_EMBEDDED_COMPONENT_VERSION = r"\.v[0-9]+\.[0-9]+(?:\.[0-9]+)?$"
_PUBLIC_STATE_ID = r"^[A-Za-z][A-Za-z0-9_.-]*$"
_EVIDENCE_ID = (
    r"^[A-Za-z0-9][A-Za-z0-9_.-]*"
    r"(?::[A-Za-z0-9][A-Za-z0-9_.-]*)*$"
)
_NON_BLANK_TEXT = r"^[\s\S]*\S[\s\S]*$"
_BRIDGE_REF_SEGMENT = r"[A-Za-z0-9][A-Za-z0-9._~@+-]*"
_OPAQUE_REF_ID = r"[A-Za-z0-9][A-Za-z0-9._~:@+-]*"
_PUBLISHED_REF = (
    rf"^(?:bridge://{_BRIDGE_REF_SEGMENT}(?:/{_BRIDGE_REF_SEGMENT})*|"
    rf"(?:artifact|run|visualization):{_OPAQUE_REF_ID}|"
    r"[A-Za-z][A-Za-z0-9._-]*)$"
)
_SCHEMA_REF = r"^bridge://schemas/[a-z0-9-]+/v[0-9]+\.[0-9]+$"
_TOOL_ID = r"^P0-(0[1-9]|1[0-2])$"

_ComponentId = Annotated[str, Field(pattern=_COMPONENT_ID)]
_EvidenceId = Annotated[str, Field(min_length=1, pattern=_EVIDENCE_ID)]
_NonBlankText = Annotated[str, Field(pattern=_NON_BLANK_TEXT)]
_PublicStateId = Annotated[str, Field(min_length=1, pattern=_PUBLIC_STATE_ID)]
_PublishedRef = Annotated[str, Field(min_length=1, pattern=_PUBLISHED_REF)]
_SchemaRef = Annotated[str, Field(pattern=_SCHEMA_REF)]
_ToolId = Annotated[str, Field(pattern=_TOOL_ID)]


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

    artifact_id: _PublishedRef
    schema_ref: _SchemaRef
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
    interval_semantics: _NonBlankText | None = None
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
    ref: _PublishedRef
    version: _NonBlankText
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

    filter_ids: list[_PublicStateId] = Field(default_factory=list)
    selection_ids: list[_PublicStateId] = Field(default_factory=list)
    drill_down_ids: list[_PublicStateId] = Field(default_factory=list)

    @field_validator("filter_ids", "selection_ids", "drill_down_ids")
    @classmethod
    def public_state_ids_are_unique(
        cls,
        values: list[str],
        info: ValidationInfo,
    ) -> list[str]:
        return _unique(values, info.field_name)


class VisualizationAccessibility(FrozenModel):
    alt_text: _NonBlankText = Field(min_length=12, max_length=240)
    long_description: _NonBlankText = Field(min_length=40)
    table_artifact_id: _PublishedRef
    data_sha256: str = Field(pattern=_SHA256)


class VisualizationRenderBinding(FrozenModel):
    artifact_id: _PublishedRef
    media_type: Literal["image/svg+xml", "application/pdf", "image/png"]
    renderer_id: _NonBlankText
    renderer_version: _NonBlankText
    export_profile_id: _NonBlankText
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
                            "not": {"pattern": _EMBEDDED_COMPONENT_VERSION}
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
                {
                    "if": {
                        "required": ["data_binding"],
                        "properties": {
                            "data_binding": {
                                "required": ["numerator_field"],
                                "properties": {
                                    "numerator_field": {"type": "string"}
                                },
                            }
                        },
                    },
                    "then": {
                        "required": ["denominator_label", "denominator_scope"],
                        "properties": {
                            "denominator_label": {"type": "string"},
                            "denominator_scope": {"type": "string"},
                        },
                    },
                    "else": {
                        "properties": {
                            "denominator_label": {"type": "null"},
                            "denominator_scope": {"type": "null"},
                        }
                    },
                },
            ]
        },
    )

    object_version: Literal["0.2.0"] = "0.2.0"
    visualization_id: _PublishedRef
    component_id: _ComponentId
    component_version: str = Field(pattern=_VERSION)
    data_binding: VisualizationDataBinding
    producer_tool_id: _ToolId
    producer_tool_version: _NonBlankText
    producer_run_ref: _PublishedRef
    evidence_ids: list[_EvidenceId] = Field(min_length=1)
    evidence_states: list[EvidenceState] = Field(min_length=1)
    scientific_status: _NonBlankText
    applicability: Literal[
        "applicable",
        "partially_applicable",
        "not_applicable",
        "not_assessed",
    ]
    missing_reason_codes: list[_PublicStateId] = Field(default_factory=list)
    denominator_label: _NonBlankText | None = None
    denominator_scope: _NonBlankText | None = None
    unit: _NonBlankText | None = None
    context_bindings: list[VisualizationContextBinding] = Field(default_factory=list)
    interactions: VisualizationInteractionContract = Field(
        default_factory=VisualizationInteractionContract
    )
    insight_title: _NonBlankText
    takeaway: _NonBlankText
    limitations: list[_NonBlankText] = Field(min_length=1)
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
        if re.search(_EMBEDDED_COMPONENT_VERSION, self.component_id):
            raise ValueError("component version must not be embedded in component_id")
        if (self.denominator_label is None) != (self.denominator_scope is None):
            raise ValueError("denominator label and scope must be paired")
        has_denominator_fields = self.data_binding.numerator_field is not None
        if has_denominator_fields != (self.denominator_label is not None):
            raise ValueError(
                "denominator semantics must accompany numerator/denominator fields"
            )
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
        _unique(
            [item.artifact_id for item in self.renders],
            "render artifact IDs",
        )
        if self.accessibility.data_sha256 != self.data_binding.sha256:
            raise ValueError("table fallback must bind the exact visualization data hash")
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
                    "properties": {
                        "component_id": {
                            "not": {"pattern": _EMBEDDED_COMPONENT_VERSION}
                        }
                    }
                },
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

    component_id: _ComponentId
    component_version: str = Field(pattern=_VERSION)
    legacy_component_ids: list[_ComponentId] = Field(default_factory=list)
    title: _NonBlankText
    question: _NonBlankText
    figure_family: _NonBlankText
    producer_tool_ids: list[_ToolId] = Field(min_length=1)
    registry_state: FigureRegistryState
    default_role: FigureRole
    scientific_status_source: Literal["producer_run"] = "producer_run"
    data_schema_refs: list[_SchemaRef] = Field(default_factory=list)
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

    @model_validator(mode="after")
    def registry_state_is_truthful(self) -> Self:
        if re.search(_EMBEDDED_COMPONENT_VERSION, self.component_id):
            raise ValueError("component version must not be embedded in component_id")
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


def _typed_component(
    component_id: str,
    component_version: str,
    *,
    title: str,
    question: str,
    figure_family: str,
    default_role: FigureRole = FigureRole.SUPPORTING,
    tool_id: str = "P0-01",
    data_schema_ref: str = "bridge://schemas/qc-visualization-data/v0.1",
) -> FigureComponentSpec:
    return FigureComponentSpec(
        component_id=component_id,
        component_version=component_version,
        title=title,
        question=question,
        figure_family=figure_family,
        producer_tool_ids=[tool_id],
        registry_state=FigureRegistryState.TYPED_CANDIDATE,
        default_role=default_role,
        data_schema_refs=[data_schema_ref],
        surfaces=[FigureSurface.STATIC_EXPORT, FigureSurface.TABLE],
        required_fallbacks=[
            "table",
            "alt_text",
            "long_description",
            "static_vector",
        ],
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
    _typed_component(
        "bridge.qc.readiness-flow",
        "0.1.0",
        title="Observation retention and analysis eligibility",
        question="Which submitted observations meet the defined technical input conditions?",
        figure_family="eligibility_flow",
        default_role=FigureRole.MAIN,
    ),
    _typed_component(
        "bridge.qc.overview",
        "0.2.0",
        title="Quality-metric distributions by capture",
        question="How are five technical QC measurements distributed across declared captures?",
        figure_family="distribution_raincloud_small_multiples",
    ),
    _typed_component(
        "bridge.qc.counts_genes",
        "0.2.0",
        title="Library complexity and mitochondrial transcript fraction",
        question="How do library complexity and mitochondrial transcript fraction vary across observations?",
        figure_family="density_hexbin_small_multiples",
    ),
    _typed_component(
        "bridge.qc.flag-intersections",
        "0.1.0",
        title="QC-flag combinations and observation counts",
        question="Which candidate QC flags occur alone or together?",
        figure_family="set_intersection",
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
    _typed_component(
        "bridge.target-regional.product-roles",
        "0.1.0",
        title="Product composition relative to the declared regional identity",
        question=(
            "How much of the product supports intended, adjacent, non-target "
            "or unresolved states, and which regional states contribute?"
        ),
        figure_family="denominator_aware_composition_fingerprint",
        tool_id="P0-03",
        data_schema_ref="bridge://schemas/target-regional-visualization-data/v0.1",
        default_role=FigureRole.MAIN,
    ),
    _typed_component(
        "bridge.target-regional.reference-fingerprint",
        "0.1.0",
        title="Reference support for cell states and midbrain regional identity",
        question=(
            "Which cell and regional states are supported across reference "
            "sources and assays?"
        ),
        figure_family="reference_state_evidence_matrix",
        tool_id="P0-03",
        data_schema_ref="bridge://schemas/target-regional-visualization-data/v0.1",
    ),
    _typed_component(
        "bridge.developmental-compatibility.window-composition",
        "0.1.0",
        title="Cell-state composition relative to the declared developmental window",
        question=(
            "How are product cell states distributed before, within and after "
            "the declared window, or outside that ordered axis?"
        ),
        figure_family="dual_denominator_developmental_composition",
        tool_id="P0-04",
        data_schema_ref="bridge://schemas/developmental-compatibility-visualization-data/v0.1",
        default_role=FigureRole.MAIN,
    ),
    _typed_component(
        "bridge.developmental-compatibility.reference-stage-summary",
        "0.1.0",
        title="Highest expression-similarity labels in each selected reference",
        question=(
            "Which supplied reference-stage labels have the highest expression "
            "similarity within each source and assay?"
        ),
        figure_family="source_separated_reference_stage_summary",
        tool_id="P0-04",
        data_schema_ref="bridge://schemas/developmental-compatibility-visualization-data/v0.1",
    ),
    _typed_component(
        "bridge.developmental-compatibility.observed-sampling-points",
        "0.1.0",
        title="Cell-state composition across declared product sampling points",
        question=(
            "How does categorical stage-role composition differ across "
            "the product sampling points that were actually supplied?"
        ),
        figure_family="categorical_sampling_point_matrix",
        tool_id="P0-04",
        data_schema_ref="bridge://schemas/developmental-compatibility-visualization-data/v0.1",
    ),
    _typed_component(
        "bridge.off-target-control.product-accounting",
        "0.1.0",
        title="Declared product-role accounting",
        question=(
            "How are observations accounted for under the declared product roles, "
            "and how much identity remains unresolved?"
        ),
        figure_family="denominator_aware_composition_ledger",
        tool_id="P0-05",
        data_schema_ref="bridge://schemas/off-target-control-visualization-data/v0.1",
        default_role=FigureRole.MAIN,
    ),
    _typed_component(
        "bridge.off-target-control.rare-state-detectability",
        "0.1.0",
        title="Rare-state observations and distinct detection boundaries",
        question=(
            "Which monitored rare states were observed, and what can the separately "
            "supplied or candidate detection boundaries support?"
        ),
        figure_family="rare_state_detection_boundary_fingerprint",
        tool_id="P0-05",
        data_schema_ref="bridge://schemas/off-target-control-visualization-data/v0.1",
    ),
    _typed_component(
        "bridge.off-target-control.ood-source-agreement",
        "0.1.0",
        title="Supplied OOD channel states by declared source family",
        question=(
            "How do the supplied OOD channel states differ across their declared "
            "source families, and what external coordination rule was applied?"
        ),
        figure_family="source_family_channel_state_matrix",
        tool_id="P0-05",
        data_schema_ref="bridge://schemas/off-target-control-visualization-data/v0.1",
    ),
    _typed_component(
        "bridge.proliferation-stress.program-evidence",
        "0.1.0",
        title="Stage- and cell-state-conditioned transcriptomic program evidence",
        question=(
            "Which declared transcriptomic programs have assessable evidence "
            "within their stage and cell-state context, and which require review?"
        ),
        figure_family="stage_state_program_evidence_matrix",
        tool_id="P0-06",
        data_schema_ref="bridge://schemas/proliferation-stress-visualization-data/v0.1",
        default_role=FigureRole.MAIN,
    ),
    _typed_component(
        "bridge.proliferation-stress.program-score-summary",
        "0.1.0",
        title="Program-score summaries across declared analysis units",
        question=(
            "How do method-specific program scores vary across the declared "
            "whole-product and cell-state analysis units?"
        ),
        figure_family="method_separated_program_score_interval",
        tool_id="P0-06",
        data_schema_ref="bridge://schemas/proliferation-stress-visualization-data/v0.1",
    ),
    _typed_component(
        "bridge.proliferation-stress.cell-cycle",
        "0.1.0",
        title="Cell-cycle phase composition across declared analysis units",
        question=(
            "How are G1, S and G2M assignments and S/G2M score evidence "
            "distributed across the declared product and cell-state views?"
        ),
        figure_family="cell_cycle_phase_and_score_profile",
        tool_id="P0-06",
        data_schema_ref="bridge://schemas/proliferation-stress-visualization-data/v0.1",
    ),
    _typed_component(
        "bridge.product-comparison.comparability",
        "0.1.0",
        title="Comparison eligibility and declared confounding structure",
        question=(
            "What declared design conditions support or prevent interpretation "
            "of between-product differences?"
        ),
        figure_family="comparison_eligibility_and_confounding_matrix",
        tool_id="P0-07",
        data_schema_ref="bridge://schemas/product-comparison-visualization-data/v0.1",
        default_role=FigureRole.MAIN,
    ),
    _typed_component(
        "bridge.product-comparison.metric-differences",
        "0.1.0",
        title="Declared analysis-unit values and descriptive group differences",
        question=(
            "What declared sample/preparation values and raw group differences were observed "
            "for each metric under its own unit and denominator?"
        ),
        figure_family="declared_analysis_unit_estimation_small_multiples",
        tool_id="P0-07",
        data_schema_ref="bridge://schemas/product-comparison-visualization-data/v0.1",
    ),
    _typed_component(
        "bridge.product-comparison.method-evidence",
        "0.1.0",
        title=(
            "Method-specific descriptive effect, distance, and dispersion evidence"
        ),
        question=(
            "Which method-specific effect, distance, similarity and dispersion "
            "estimates were assessable, and on which separate scales?"
        ),
        figure_family="method_separated_comparison_evidence",
        tool_id="P0-07",
        data_schema_ref="bridge://schemas/product-comparison-visualization-data/v0.1",
    ),
)


class FigureRegistry:
    """Read-only discovery and validation for renderer-independent figures."""

    def __init__(self, snapshot: FigureRegistrySnapshot) -> None:
        self._snapshot = snapshot.model_copy(deep=True)
        self._by_ref = {
            component.component_ref: component
            for component in self._snapshot.components
        }
        self._by_legacy = {
            legacy_id: component
            for component in self._snapshot.components
            for legacy_id in component.legacy_component_ids
        }

    @property
    def snapshot(self) -> FigureRegistrySnapshot:
        return self._snapshot.model_copy(deep=True)

    @classmethod
    def load_default(cls) -> FigureRegistry:
        return cls(
            FigureRegistrySnapshot(
                components=[
                    component.model_copy(deep=True)
                    for component in _DEFAULT_COMPONENTS
                ]
            )
        )

    def list(self, *, tool_id: str | None = None) -> list[FigureComponentSpec]:
        if tool_id is not None and re.fullmatch(_TOOL_ID, tool_id) is None:
            raise ValueError(f"invalid Tool ID: {tool_id}")
        components = self._snapshot.components
        if tool_id is not None:
            components = [
                component
                for component in components
                if tool_id in component.producer_tool_ids
            ]
        return [
            component.model_copy(deep=True)
            for component in sorted(components, key=lambda item: item.component_ref)
        ]

    def get(self, component_ref: str) -> FigureComponentSpec:
        component = self._by_ref.get(component_ref)
        if component is None:
            try:
                component = self._by_legacy[component_ref]
            except KeyError as exc:
                raise KeyError(component_ref) from exc
        return component.model_copy(deep=True)

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

        used_interactions = {
            interaction
            for interaction, values in (
                (VisualizationInteraction.FILTER, artifact.interactions.filter_ids),
                (VisualizationInteraction.SELECT, artifact.interactions.selection_ids),
                (
                    VisualizationInteraction.DRILL_DOWN,
                    artifact.interactions.drill_down_ids,
                ),
            )
            if values
        }
        undeclared_interactions = used_interactions.difference(
            component.interactions
        )
        if undeclared_interactions:
            names = ", ".join(
                sorted(item.value for item in undeclared_interactions)
            )
            raise ValueError(f"figure uses unregistered interactions: {names}")

        fallback_available = {
            "table": bool(artifact.accessibility.table_artifact_id),
            "alt_text": bool(artifact.accessibility.alt_text.strip()),
            "long_description": bool(
                artifact.accessibility.long_description.strip()
            ),
            "static_vector": any(
                render.media_type in {"image/svg+xml", "application/pdf"}
                for render in artifact.renders
            ),
        }
        missing_fallbacks = sorted(
            fallback
            for fallback in component.required_fallbacks
            if not fallback_available[fallback]
        )
        if missing_fallbacks:
            raise ValueError(
                "figure is missing required fallbacks: "
                + ", ".join(missing_fallbacks)
            )
        return component

    def validation_summary(self) -> dict[str, object]:
        components = self._snapshot.components
        typed_count = sum(
            item.registry_state is FigureRegistryState.TYPED_CANDIDATE
            for item in components
        )
        return {
            "valid": True,
            "registry_id": self._snapshot.registry_id,
            "object_version": self._snapshot.object_version,
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
