from __future__ import annotations

import hashlib
import csv
from dataclasses import dataclass
from importlib.resources import files
from importlib.metadata import version as distribution_version
from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import Field, field_validator, model_validator

from bridge.tool_packages._structured_runtime import canonical_json_bytes
from bridge.tool_packages.p0_02_cell_state.hierarchical_composition import (
    HierarchicalCellStateCompositionDataV1,
)
from bridge.tool_packages.p0_02_cell_state.visualization import (
    render_hierarchical_composition,
    render_source_state_evidence_matrix,
    write_hierarchical_visualization_table,
    write_source_state_evidence_table,
)
from bridge.tool_packages.p0_02_cell_state.visualization_data import (
    CELL_STATE_EVIDENCE_MATRIX_V2_SCHEMA_REF,
    HIERARCHICAL_CELL_STATE_VISUALIZATION_SCHEMA_REF,
    HIERARCHICAL_COMPOSITION_COMPONENT_REF,
    P002VisualizationArtifactSet,
    SOURCE_STATE_EVIDENCE_COMPONENT_REF,
    CellStateEvidenceChannelRecord,
    CellStateEvidenceMatrixDataV2,
    CellStateEvidenceMatrixRecordV2,
    CellStateEvidenceRow,
    CellStateEvidenceSource,
    CellStateEvidenceStatistic,
    EvidenceChannel,
    EvidenceRole,
    VisualizationArtifactHash,
    HierarchicalCellStateVisualizationDataV1,
    HierarchicalCellStateVisualizationRecord,
    MatrixAssessmentState,
    SourceAvailability,
    SourceRelationship,
    _artifact_id,
    _visualization_id,
)
from bridge.toolkit.contracts import ArtifactManifest, EvidenceState, FrozenModel
from bridge.toolkit.visualization import (
    FigureRegistry,
    VisualizationAccessibility,
    VisualizationArtifactV2,
    VisualizationContextBinding,
    VisualizationDataBinding,
    VisualizationRenderBinding,
)


_RESOURCE_PACKAGE = "bridge.tool_packages.p0_02_cell_state.resources"
_RENDERER_ID = "bridge.matplotlib.cell-state-evidence"
_RENDERER_VERSION = "0.2.1"
_EXPORT_PROFILE_ID = "bridge-static-scientific-figure-v0.1"
_EVIDENCE_KEYS = Literal[
    "biological_review",
    "marker_programs",
    "external_source_lineage",
    "birtele_sample_manifest",
    "source_registry",
]
_SOURCE_POLICIES = Literal[
    "primary_review_counts",
    "unassessed_derived_context",
    "unassessed_spatial_concordance",
    "independent_source_mapping_unavailable",
    "external_holdout_unrun",
]


class _ResourceBinding(FrozenModel):
    resource_name: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*\.yaml$")
    object_ref: str = Field(min_length=1)
    object_version: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class _RegistryInputBindings(FrozenModel):
    biological_review: _ResourceBinding
    marker_programs: _ResourceBinding
    external_source_lineage: _ResourceBinding
    birtele_sample_manifest: _ResourceBinding


class _SourceConfig(FrozenModel):
    source_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    source_alias_ids: list[str] = Field(default_factory=list)
    lineage_asset_id: str | None = None
    source_family_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    display_name: str = Field(min_length=1)
    short_name: str = Field(min_length=1, max_length=24)
    assay: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    relationship: SourceRelationship
    availability: SourceAvailability
    observation_unit: str = Field(min_length=1)
    n_observations: int | None = Field(default=None, ge=0)
    dependency_source_ids: list[str] = Field(default_factory=list)
    default_record_policy: _SOURCE_POLICIES
    evidence_keys: list[_EVIDENCE_KEYS] = Field(min_length=1)
    limitation: str = Field(min_length=1)

    @field_validator(
        "source_alias_ids",
        "dependency_source_ids",
        "evidence_keys",
    )
    @classmethod
    def source_lists_are_unique(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("source registry lists must be unique")
        return values


class _VisualizationSourceRegistry(FrozenModel):
    registry_id: str = Field(min_length=1)
    version: Literal["0.1.0"] = "0.1.0"
    status: Literal["draft"] = "draft"
    input_bindings: _RegistryInputBindings
    primary_source_id: str
    sources: list[_SourceConfig] = Field(min_length=2)
    state_order: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def registry_is_explicit(self) -> Self:
        source_ids = [source.source_id for source in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("source registry IDs must be unique")
        if self.primary_source_id not in source_ids:
            raise ValueError("source registry primary source is missing")
        primary = [
            source
            for source in self.sources
            if source.relationship is SourceRelationship.PRIMARY
        ]
        if len(primary) != 1 or primary[0].source_id != self.primary_source_id:
            raise ValueError("source registry requires one explicit primary source")
        if len(self.state_order) != len(set(self.state_order)):
            raise ValueError("source registry state order must be unique")
        all_aliases = [
            alias for source in self.sources for alias in source.source_alias_ids
        ]
        if len(all_aliases) != len(set(all_aliases)):
            raise ValueError("source aliases must be unique")
        return self


@dataclass(frozen=True)
class _LoadedResources:
    registry: _VisualizationSourceRegistry
    registry_sha256: str
    payloads: dict[str, dict[str, object]]
    anchors: dict[str, str]


@dataclass(frozen=True)
class PreparedCellStateVisualizations:
    artifacts: tuple[ArtifactManifest, ...]
    artifact_set: P002VisualizationArtifactSet


def build_source_state_evidence_matrix(
    run_id: str,
) -> tuple[CellStateEvidenceMatrixDataV2, _VisualizationSourceRegistry, str]:
    loaded = _load_resources()
    registry = loaded.registry
    review = loaded.payloads["biological_review"]
    markers = loaded.payloads["marker_programs"]
    lineage = loaded.payloads["external_source_lineage"]

    cards = {str(card["state_id"]): card for card in review["state_reviews"]}
    marker_cards = {str(card["state_id"]): card for card in markers["cards"]}
    if set(cards) != set(registry.state_order):
        raise ValueError("source registry must enumerate every biological-review state")
    if not set(marker_cards) <= set(cards):
        raise ValueError("marker programs reference states outside biological review")
    if review["card_defaults"]["count_source_id"] != registry.primary_source_id:
        raise ValueError("biological review and source registry primary IDs disagree")

    lineage_asset_ids = {str(asset["asset_id"]) for asset in lineage["assets"]}
    for source in registry.sources:
        if (
            source.lineage_asset_id is not None
            and source.lineage_asset_id not in lineage_asset_ids
        ):
            raise ValueError(
                f"source lineage asset is not registered: {source.lineage_asset_id}"
            )

    level_totals = {
        level: sum(
            int(card["n_observations"])
            for card in cards.values()
            if card["level"] == level
        )
        for level in ("L1", "L2")
    }
    primary_config = next(
        source
        for source in registry.sources
        if source.source_id == registry.primary_source_id
    )
    if primary_config.n_observations != level_totals["L1"]:
        raise ValueError("primary source count must equal the L1 review denominator")

    sources = [
        CellStateEvidenceSource(
            source_id=source.source_id,
            source_family_id=source.source_family_id,
            display_name=source.display_name,
            short_name=source.short_name,
            assay=source.assay,
            scope=source.scope,
            relationship=source.relationship,
            availability=source.availability,
            observation_unit=source.observation_unit,
            n_observations=source.n_observations,
            dependency_source_ids=source.dependency_source_ids,
            evidence_ids=sorted(loaded.anchors[key] for key in source.evidence_keys),
            limitation=source.limitation,
        )
        for source in registry.sources
    ]
    states = [
        _state_row(
            cards[state_id],
            order,
            loaded.anchors["biological_review"],
        )
        for order, state_id in enumerate(registry.state_order)
    ]
    records = [
        _source_record(
            card=cards[state_id],
            source=source,
            marker_card=marker_cards.get(state_id),
            anchors=loaded.anchors,
        )
        for state_id in registry.state_order
        for source in registry.sources
    ]
    evidence_ids = sorted(
        {evidence_id for record in records for evidence_id in record.evidence_ids}
    )
    digest = run_id.removeprefix("run-")
    profile = CellStateEvidenceMatrixDataV2(
        profile_id=f"cell-state-evidence-matrix:{digest}",
        producer_run_ref=f"run:{run_id}",
        primary_source_id=registry.primary_source_id,
        review_state=str(review["status"]),
        denominator=len(states),
        sources=sources,
        states=states,
        records=records,
        evidence_ids=evidence_ids,
        source_registry_ref=registry.registry_id,
        source_registry_sha256=loaded.registry_sha256,
        limitations=[
            (
                "This static registry review does not represent the references "
                "selected or the support generated for this product run."
            ),
            "Current state names and marker programs remain under biological review.",
            "Derived and label-transfer sources are not independent validation.",
            "Birtele held-out state assessment has not been run.",
            "Unknown and out-of-distribution performance is not assessed.",
        ],
        alt_text=(
            "Registry review of 18 broad and seven regional state cards across five "
            "definition-source entries; query-specific support is not represented."
        ),
        long_description=(
            "Sixteen of 18 broad labels and all seven registered regional labels "
            "occur in the current label-count source; occurrence is not validated "
            "identity. Combined and spatial state mappings remain unrecorded. "
            "La Manno state mapping is unavailable in this registry view and its "
            "runtime role is not represented. Birtele held-out assessment is unrun."
        ),
    )
    return profile, registry, loaded.registry_sha256


def build_hierarchical_visualization_data(
    profile: HierarchicalCellStateCompositionDataV1,
) -> HierarchicalCellStateVisualizationDataV1:
    source_payload = canonical_json_bytes(
        profile.model_dump(mode="json"),
        indent=2,
    )
    ordered_records = sorted(
        profile.composition_records,
        key=lambda item: item.order,
    )
    named_states = [
        record for record in ordered_records if record.record_kind == "state"
    ]
    state_records = [
        *[record for record in named_states if record.level == "L1"],
        *[record for record in named_states if record.level == "L2"],
    ]
    subtype_status_records = [
        record
        for record in ordered_records
        if record.record_kind == "resolution" and record.level == "L2"
    ]
    if profile.groups:
        rows = [
            {
                "row_id": group.group_id,
                "display_name": group.display_name,
                "count": group.count,
                "whole_fraction": group.whole_product_fraction,
            }
            for group in profile.groups
        ]
    else:
        rows = [
            {
                "row_id": "whole-product",
                "display_name": "Whole product",
                "count": profile.whole_product_denominator,
                "whole_fraction": 1.0,
            }
        ]

    group_records = {
        (record.group_id, record.state_id): record
        for record in profile.group_records
        if record.state_id is not None
    }
    group_root_statuses = {
        (record.group_id, record.resolution_state): record
        for record in profile.group_records
        if record.level == "L1" and record.state_id is None
    }
    group_subtype_statuses = {
        (record.group_id, record.parent_state_id, record.resolution_state): record
        for record in profile.group_records
        if record.level == "L2" and record.state_id is None
    }
    whole_states = {
        record.state_id: record
        for record in profile.composition_records
        if record.record_kind == "state"
    }
    whole_root_statuses = {
        record.resolution_state: record
        for record in profile.composition_records
        if record.record_kind == "resolution" and record.partition_id == "root"
    }
    whole_subtype_statuses = {
        (record.parent_state_id, record.resolution_state): record
        for record in subtype_status_records
    }
    open_set_status = next(
        record
        for record in profile.composition_records
        if record.record_kind == "resolution"
        and record.resolution_state == "not_assessed"
        and "open_set_calibration_not_available" in record.reason_codes
    )
    records = []
    for row_order, row in enumerate(rows):
        row_id = str(row["row_id"])
        row_count = int(row["count"])
        records.append(
            _hierarchy_record(
                row=row,
                row_order=row_order,
                column_id="measure:whole-product-share",
                column_display_name="Share of complete product",
                column_order=0,
                column_kind="group_share",
                state_id=None,
                reference_level="status",
                parent_state_id=None,
                count=row_count,
                denominator=profile.whole_product_denominator,
                denominator_scope=profile.denominator_scope,
                fraction=float(row["whole_fraction"]),
                evidence_state=EvidenceState.INFERRED,
                evidence_ids=sorted(profile.evidence_ids),
                reason_codes=[],
            )
        )
        for column_order, state in enumerate(state_records):
            parent_denominator = None
            parent_fraction = None
            if profile.groups:
                source = group_records.get((row_id, state.state_id))
                if source is None:
                    parent_count = next(
                        record.count
                        for record in profile.group_records
                        if record.group_id == row_id
                        and record.level == "L1"
                        and record.state_id == state.parent_state_id
                    )
                    if state.level != "L2" or parent_count != 0:
                        raise ValueError(
                            "group hierarchy has an unexplained missing state"
                        )
                    count = 0
                    fraction = 0.0
                    evidence_state = EvidenceState.INFERRED
                    evidence_ids = sorted(profile.evidence_ids)
                    reason_codes = ["parent_state_absent_in_product_group"]
                    parent_denominator = parent_count
                    parent_fraction = None
                else:
                    count = source.count
                    fraction = source.group_fraction
                    evidence_state = source.evidence_state
                    evidence_ids = sorted(source.evidence_ids)
                    reason_codes = sorted(source.reason_codes)
                    if state.level == "L2":
                        parent_denominator = source.parent_denominator
                        parent_fraction = source.parent_fraction
            else:
                source = whole_states[state.state_id]
                count = source.count
                fraction = source.whole_product_fraction
                evidence_state = source.evidence_state
                evidence_ids = sorted(source.evidence_ids)
                reason_codes = sorted(source.reason_codes)
                if state.level == "L2":
                    parent_denominator = source.parent_denominator
                    parent_fraction = source.parent_fraction
            records.append(
                _hierarchy_record(
                    row=row,
                    row_order=row_order,
                    column_id=state.state_id,
                    column_display_name=_state_display_name(
                        state.state_id, state.display_name
                    ),
                    column_order=column_order + 1,
                    column_kind="state",
                    state_id=state.state_id,
                    reference_level=state.level,
                    parent_state_id=state.parent_state_id,
                    count=count,
                    fraction=fraction,
                    evidence_state=evidence_state,
                    evidence_ids=evidence_ids,
                    reason_codes=reason_codes,
                    parent_denominator=parent_denominator,
                    parent_denominator_scope=(
                        (
                            "resolved broad-state observations in the whole product"
                            if row_id == "whole-product"
                            else (
                                "resolved broad-state observations in the product group"
                            )
                        )
                        if state.level == "L2"
                        else None
                    ),
                    parent_fraction=parent_fraction,
                )
            )

        subtype_offset = len(state_records) + 1
        for subtype_index, status_record in enumerate(subtype_status_records):
            parent_state_id = status_record.parent_state_id
            assert parent_state_id is not None
            if profile.groups:
                source = group_subtype_statuses.get(
                    (row_id, parent_state_id, status_record.resolution_state)
                )
                if source is None:
                    parent = group_records[(row_id, parent_state_id)]
                    if parent.count != 0:
                        raise ValueError("group refined status record is missing")
                    count = 0
                    fraction = 0.0
                    parent_denominator = 0
                    parent_fraction = None
                    evidence_state = EvidenceState.INFERRED
                    evidence_ids = sorted(profile.evidence_ids)
                    reason_codes = ["parent_state_absent_in_product_group"]
                else:
                    count = source.count
                    fraction = source.group_fraction
                    parent_denominator = source.parent_denominator
                    parent_fraction = source.parent_fraction
                    evidence_state = source.evidence_state
                    evidence_ids = sorted(source.evidence_ids)
                    reason_codes = sorted(source.reason_codes)
            else:
                source = whole_subtype_statuses[
                    (parent_state_id, status_record.resolution_state)
                ]
                count = source.count
                fraction = source.whole_product_fraction
                parent_denominator = source.parent_denominator
                parent_fraction = source.parent_fraction
                evidence_state = source.evidence_state
                evidence_ids = sorted(source.evidence_ids)
                reason_codes = sorted(source.reason_codes)
            parent_name = _state_display_name(
                parent_state_id, whole_states[parent_state_id].display_name
            )
            unresolved = status_record.resolution_state == "subtype_unresolved"
            records.append(
                _hierarchy_record(
                    row=row,
                    row_order=row_order,
                    column_id=(
                        f"status:{parent_state_id}:{status_record.resolution_state}"
                    ),
                    column_display_name=(
                        f"{parent_name}: subtype remains unresolved"
                        if unresolved
                        else f"{parent_name}: subtype correspondence unavailable"
                    ),
                    column_order=subtype_offset + subtype_index,
                    column_kind=(
                        "subtype_unresolved" if unresolved else "subtype_unavailable"
                    ),
                    state_id=None,
                    reference_level="L2",
                    parent_state_id=parent_state_id,
                    count=count,
                    fraction=fraction,
                    evidence_state=evidence_state,
                    evidence_ids=evidence_ids,
                    reason_codes=reason_codes,
                    parent_denominator=parent_denominator,
                    parent_denominator_scope=(
                        "resolved broad-state observations in the whole product"
                        if row_id == "whole-product"
                        else ("resolved broad-state observations in the product group")
                    ),
                    parent_fraction=parent_fraction,
                )
            )

        status_offset = 1 + len(state_records) + len(subtype_status_records)
        for status_index, (status, label) in enumerate(
            (
                ("source_conflict", "Multiple broad states"),
                ("unavailable", "Reference correspondence unavailable"),
            )
        ):
            if profile.groups:
                source = group_root_statuses.get((row_id, status))
            else:
                source = whole_root_statuses.get(status)
            if source is None:
                if status != "source_conflict" or profile.source_conflict_assessed:
                    raise ValueError("hierarchy status record is missing")
                records.append(
                    _hierarchy_record(
                        row=row,
                        row_order=row_order,
                        column_id="status:source-conflict",
                        column_display_name=label,
                        column_order=status_offset + status_index,
                        column_kind="source_conflict",
                        state_id=None,
                        reference_level="status",
                        parent_state_id=None,
                        count=None,
                        fraction=None,
                        evidence_state=EvidenceState.UNAVAILABLE,
                        evidence_ids=sorted(profile.evidence_ids),
                        reason_codes=[
                            "source_conflict_requires_multiple_primary_sources"
                        ],
                    )
                )
                continue
            records.append(
                _hierarchy_record(
                    row=row,
                    row_order=row_order,
                    column_id=f"status:{status.replace('_', '-')}",
                    column_display_name=label,
                    column_order=status_offset + status_index,
                    column_kind=status,
                    state_id=None,
                    reference_level="status",
                    parent_state_id=None,
                    count=source.count,
                    fraction=(
                        source.group_fraction
                        if profile.groups
                        else source.whole_product_fraction
                    ),
                    evidence_state=source.evidence_state,
                    evidence_ids=sorted(source.evidence_ids),
                    reason_codes=sorted(source.reason_codes),
                )
            )
        records.append(
            _hierarchy_record(
                row=row,
                row_order=row_order,
                column_id="status:open-set-not-assessed",
                column_display_name="Unknown / OOD status not assessed",
                column_order=status_offset + 2,
                column_kind="open_set_not_assessed",
                state_id=None,
                reference_level="status",
                parent_state_id=None,
                count=None,
                fraction=None,
                evidence_state=open_set_status.evidence_state,
                evidence_ids=sorted(open_set_status.evidence_ids),
                reason_codes=sorted(open_set_status.reason_codes),
            )
        )

    digest = profile.producer_run_ref.removeprefix("run:run-")
    return HierarchicalCellStateVisualizationDataV1(
        profile_id=f"hierarchical-cell-state-visualization:{digest}",
        producer_run_ref=profile.producer_run_ref,
        source_profile_ref=profile.profile_id,
        source_profile_sha256=hashlib.sha256(source_payload).hexdigest(),
        observation_unit=profile.observation_unit,
        whole_product_denominator=profile.whole_product_denominator,
        denominator_scope=profile.denominator_scope,
        grouping=profile.grouping,
        records=records,
        evidence_ids=sorted(profile.evidence_ids),
        limitations=profile.limitations,
        alt_text=profile.alt_text,
        long_description=profile.long_description,
    )


def prepare_cell_state_visualizations(
    hierarchy: HierarchicalCellStateCompositionDataV1,
    run_dir: Path,
    run_id: str,
    tool_version: str,
) -> PreparedCellStateVisualizations:
    if hierarchy.producer_run_ref != f"run:{run_id}":
        raise ValueError("hierarchical profile does not bind the producer run")
    hierarchy_view = build_hierarchical_visualization_data(hierarchy)
    source_matrix, source_registry, source_registry_sha = (
        build_source_state_evidence_matrix(run_id)
    )

    hierarchy_data = _write_data_artifact(
        hierarchy_view,
        run_dir / "hierarchical_cell_state_visualization_data.json",
        run_id,
        "hierarchical-visualization-data",
        "hierarchical_cell_state_visualization_data",
        hierarchy_view.evidence_ids,
    )
    hierarchy_table_path = write_hierarchical_visualization_table(
        hierarchy_view,
        run_dir / "hierarchical_cell_state_visualization.tsv",
    )
    _validate_table_records(hierarchy_table_path, hierarchy_view.records)
    hierarchy_table = _manifest(
        run_id,
        "hierarchical-visualization-table",
        "visualization_table",
        hierarchy_table_path,
        hierarchy_view.evidence_ids,
    )
    hierarchy_paths = render_hierarchical_composition(
        hierarchy_view,
        run_dir / "hierarchical_cell_state_visualization",
    )
    hierarchy_renders = _render_manifests(
        run_id,
        "hierarchical-visualization",
        hierarchy_paths,
        hierarchy_view.evidence_ids,
    )

    source_data = _write_data_artifact(
        source_matrix,
        run_dir / "cell_state_source_evidence_matrix_data.json",
        run_id,
        "source-state-evidence-data",
        "cell_state_source_evidence_matrix_data",
        source_matrix.evidence_ids,
    )
    source_table_path = write_source_state_evidence_table(
        source_matrix,
        run_dir / "cell_state_source_evidence_matrix.tsv",
    )
    _validate_table_records(source_table_path, source_matrix.records)
    source_table = _manifest(
        run_id,
        "source-state-evidence-table",
        "visualization_table",
        source_table_path,
        source_matrix.evidence_ids,
    )
    source_paths = render_source_state_evidence_matrix(
        source_matrix,
        run_dir / "cell_state_source_evidence_matrix",
    )
    source_renders = _render_manifests(
        run_id,
        "source-state-evidence",
        source_paths,
        source_matrix.evidence_ids,
    )

    visualizations = [
        _hierarchy_visualization(
            hierarchy_view,
            hierarchy_data,
            hierarchy_table,
            hierarchy_renders,
            run_id,
            tool_version,
        ),
        _source_visualization(
            source_matrix,
            source_data,
            source_table,
            source_renders,
            source_registry,
            source_registry_sha,
            run_id,
            tool_version,
        ),
    ]
    figure_registry = FigureRegistry.load_default()
    for visualization in visualizations:
        figure_registry.validate_artifact(visualization)

    component_artifacts = (
        hierarchy_data,
        hierarchy_table,
        *hierarchy_renders,
        source_data,
        source_table,
        *source_renders,
    )
    artifact_hashes = [
        VisualizationArtifactHash(
            artifact_id=artifact.artifact_id,
            content_sha256=_verify_manifest_content(artifact),
        )
        for artifact in component_artifacts
    ]

    artifact_set = P002VisualizationArtifactSet(
        artifact_set_id=f"p0-02-visualizations:{run_id.removeprefix('run-')}",
        hierarchical_data_artifact_id=hierarchy_data.artifact_id,
        hierarchical_data_sha256=hierarchy_data.sha256,
        source_matrix_data_artifact_id=source_data.artifact_id,
        source_matrix_data_sha256=source_data.sha256,
        visualizations=visualizations,
        artifact_hashes=artifact_hashes,
    )
    artifact_set_path = run_dir / "p0_02_visualization_artifact_set.json"
    artifact_set_path.write_bytes(
        canonical_json_bytes(
            artifact_set.model_dump(mode="json"),
            indent=2,
        )
    )
    artifact_set_artifact = _manifest(
        run_id,
        "p0-02-visualization-artifact-set",
        "visualization_artifact_set",
        artifact_set_path,
        sorted({*hierarchy_view.evidence_ids, *source_matrix.evidence_ids}),
    )
    artifacts = (
        *component_artifacts,
        artifact_set_artifact,
    )
    return PreparedCellStateVisualizations(tuple(artifacts), artifact_set)


def _load_resources() -> _LoadedResources:
    package = files(_RESOURCE_PACKAGE)
    registry_resource = package.joinpath("visualization_source_registry.yaml")
    registry_raw = registry_resource.read_bytes()
    registry = _VisualizationSourceRegistry.model_validate(yaml.safe_load(registry_raw))
    registry_sha = hashlib.sha256(registry_raw).hexdigest()
    payloads = {}
    anchors = {"source_registry": _candidate_anchor("source-registry", registry_sha)}
    reference_fields = {
        "biological_review": "review_record_id",
        "marker_programs": "snapshot_id",
        "external_source_lineage": "audit_id",
        "birtele_sample_manifest": "dataset_id",
    }
    for key, object_ref_field in reference_fields.items():
        binding = getattr(registry.input_bindings, key)
        raw = package.joinpath(binding.resource_name).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != binding.sha256:
            raise ValueError(f"source registry input checksum mismatch: {key}")
        payload = yaml.safe_load(raw)
        if (
            payload.get(object_ref_field) != binding.object_ref
            or str(payload.get("version")) != binding.object_version
        ):
            raise ValueError(f"source registry input identity mismatch: {key}")
        payloads[key] = payload
        anchors[key] = _candidate_anchor(key.replace("_", "-"), digest)
    return _LoadedResources(registry, registry_sha, payloads, anchors)


def _candidate_anchor(kind: str, digest: str) -> str:
    return f"candidate-evidence:p0-02:{kind}:{digest}"


def _state_display_name(state_id: str, display_name: str) -> str:
    if state_id == "L1:Glioblast":
        return (
            "Developmental gliogenic progenitor "
            "(internal label: Glioblast; naming review pending)"
        )
    return display_name


def _state_row(
    card: dict[str, object],
    order: int,
    review_anchor: str,
) -> CellStateEvidenceRow:
    state_id = str(card["state_id"])
    parent_ids = [str(item) for item in card.get("parent_state_ids", [])]
    if str(card["level"]) == "L2":
        if parent_ids == ["L1:Radial_Glia"]:
            row_group = "Regional radial-glial states"
        elif parent_ids == ["L1:Neuroblast"]:
            row_group = "Regional neuroblast states"
        else:
            raise ValueError(f"unrecognized refined-state parent: {state_id}")
    else:
        name = state_id.split(":", 1)[1]
        if name in {
            "Astrocyte",
            "Glioblast",
            "Radial_Glia",
            "Neuroblast",
            "OPC",
            "Oligo",
        }:
            row_group = "Progenitor and glial states"
        elif name.startswith("Neuron_"):
            row_group = "Neuronal states"
        else:
            row_group = "Vascular, mesenchymal and immune states"
    notes = [str(item) for item in card.get("review_blockers", [])]
    confusion = [str(item) for item in card.get("confusion_states", [])]
    if confusion:
        notes.append("Potentially confused with: " + ", ".join(confusion))
    return CellStateEvidenceRow(
        state_id=state_id,
        display_name=_state_display_name(state_id, str(card["display_name"])),
        level=str(card["level"]),
        row_group=row_group,
        order=order,
        primary_n_observations=int(card["n_observations"]),
        review_state=str(card.get("review_status", "pending")),
        evidence_ids=[review_anchor],
        review_notes=notes,
    )


def _source_record(
    *,
    card: dict[str, object],
    source: _SourceConfig,
    marker_card: dict[str, object] | None,
    anchors: dict[str, str],
) -> CellStateEvidenceMatrixRecordV2:
    policy = source.default_record_policy
    if policy == "primary_review_counts":
        return _primary_record(card, marker_card, source, anchors)
    if policy == "unassessed_derived_context":
        return _not_assessed_record(
            card,
            source,
            EvidenceRole.DERIVED_CONTEXT,
            EvidenceState.MISSING,
            "derived_source_state_assessment_not_recorded",
            EvidenceChannel.REFERENCE_PREDICTION,
            anchors,
        )
    if policy == "unassessed_spatial_concordance":
        return _not_assessed_record(
            card,
            source,
            EvidenceRole.DEPENDENT_SPATIAL_CONCORDANCE,
            EvidenceState.MISSING,
            "spatial_state_assessment_not_recorded",
            EvidenceChannel.SPATIAL_MARKER,
            anchors,
            extra_reasons=["spatial_annotation_review_pending"],
        )
    if policy == "independent_source_mapping_unavailable":
        return _not_assessed_record(
            card,
            source,
            EvidenceRole.EXTERNAL_HOLDOUT,
            EvidenceState.UNAVAILABLE,
            "source_state_mapping_not_recorded",
            EvidenceChannel.EXTERNAL_HOLDOUT,
            anchors,
            extra_reasons=["runtime_reference_role_not_represented"],
        )
    if policy == "external_holdout_unrun":
        return _not_assessed_record(
            card,
            source,
            EvidenceRole.EXTERNAL_HOLDOUT,
            EvidenceState.UNAVAILABLE,
            "heldout_runner_not_executed",
            EvidenceChannel.EXTERNAL_HOLDOUT,
            anchors,
            extra_reasons=["biological_review_in_progress"],
        )
    raise ValueError(f"unsupported source record policy: {policy}")


def _primary_record(
    card: dict[str, object],
    marker_card: dict[str, object] | None,
    source: _SourceConfig,
    anchors: dict[str, str],
) -> CellStateEvidenceMatrixRecordV2:
    count = int(card["n_observations"])
    review_anchor = anchors["biological_review"]
    marker_anchor = anchors["marker_programs"]
    lineage_anchor = anchors["external_source_lineage"]
    annotation_state = (
        MatrixAssessmentState.SOURCE_ANCHORED
        if count
        else MatrixAssessmentState.NOT_ASSESSED
    )
    annotation_evidence = EvidenceState.MEASURED if count else EvidenceState.UNAVAILABLE
    annotation_reason = [] if count else ["no_primary_observations"]
    marker_evidence = EvidenceState.UNKNOWN if marker_card else EvidenceState.MISSING
    marker_reason = (
        "marker_program_review_pending"
        if marker_card
        else "marker_program_not_registered"
    )
    channels = [
        _channel(
            EvidenceChannel.ANNOTATION_OBSERVATION,
            annotation_state,
            annotation_evidence,
            (
                f"{count:,} observations carry this label in the primary reference."
                if count
                else "No observations carry this label in the primary reference."
            ),
            [review_anchor],
            annotation_reason,
        ),
        _channel(
            EvidenceChannel.MARKER_PROGRAM,
            MatrixAssessmentState.NOT_ASSESSED,
            marker_evidence,
            (
                "A draft marker program is registered and remains under review."
                if marker_card
                else "No versioned marker program is registered for this state."
            ),
            [marker_anchor],
            [marker_reason],
        ),
        _channel(
            EvidenceChannel.OOD_ASSESSMENT,
            MatrixAssessmentState.NOT_ASSESSED,
            EvidenceState.UNAVAILABLE,
            "Unknown and out-of-distribution performance is not assessed.",
            [lineage_anchor],
            ["open_set_calibration_not_available"],
        ),
    ]
    if not count:
        return _record(
            card,
            source,
            MatrixAssessmentState.NOT_ASSESSED,
            EvidenceRole.PRIMARY_ANNOTATION,
            EvidenceState.UNAVAILABLE,
            "The current primary annotation contains no observations with this label.",
            channels,
            ["no_primary_observations"],
        )
    return _record(
        card,
        source,
        MatrixAssessmentState.SOURCE_ANCHORED,
        EvidenceRole.PRIMARY_ANNOTATION,
        EvidenceState.MEASURED,
        "This label occurs in the primary annotation; that occurrence is not independent validation.",
        channels,
        [],
    )


def _not_assessed_record(
    card: dict[str, object],
    source: _SourceConfig,
    role: EvidenceRole,
    evidence_state: EvidenceState,
    reason: str,
    channel_id: EvidenceChannel,
    anchors: dict[str, str],
    *,
    extra_reasons: list[str] | None = None,
) -> CellStateEvidenceMatrixRecordV2:
    reasons = sorted({reason, *(extra_reasons or [])})
    evidence_ids = sorted(anchors[key] for key in source.evidence_keys)
    channels = [
        _channel(
            channel_id,
            MatrixAssessmentState.NOT_ASSESSED,
            evidence_state,
            reason.replace("_", " "),
            evidence_ids,
            reasons,
        )
    ]
    return _record(
        card,
        source,
        MatrixAssessmentState.NOT_ASSESSED,
        role,
        evidence_state,
        reason.replace("_", " "),
        channels,
        reasons,
    )


def _record(
    card: dict[str, object],
    source: _SourceConfig,
    assessment_state: MatrixAssessmentState,
    evidence_role: EvidenceRole,
    evidence_state: EvidenceState,
    summary: str,
    channels: list[CellStateEvidenceChannelRecord],
    reason_codes: list[str],
) -> CellStateEvidenceMatrixRecordV2:
    state_id = str(card["state_id"])
    evidence_ids = sorted(
        {evidence_id for channel in channels for evidence_id in channel.evidence_ids}
    )
    missingness = {
        EvidenceState.MISSING: "missing",
        EvidenceState.UNAVAILABLE: "unavailable",
    }.get(evidence_state, "available")
    return CellStateEvidenceMatrixRecordV2(
        record_id=f"record:{state_id}:{source.source_id}",
        state_id=state_id,
        source_id=source.source_id,
        assessment_state=assessment_state,
        evidence_role=evidence_role,
        evidence_state=evidence_state,
        applicability=(
            "not_assessed"
            if assessment_state is MatrixAssessmentState.NOT_ASSESSED
            else "applicable"
        ),
        missingness=missingness,
        summary=summary,
        evidence_ids=evidence_ids,
        reason_codes=sorted(set(reason_codes)),
        channels=channels,
    )


def _channel(
    channel_id: EvidenceChannel,
    assessment_state: MatrixAssessmentState,
    evidence_state: EvidenceState,
    summary: str,
    evidence_ids: list[str],
    reason_codes: list[str],
    statistics: list[CellStateEvidenceStatistic] | None = None,
) -> CellStateEvidenceChannelRecord:
    return CellStateEvidenceChannelRecord(
        channel=channel_id,
        assessment_state=assessment_state,
        evidence_state=evidence_state,
        summary=summary,
        evidence_ids=sorted(set(evidence_ids)),
        reason_codes=sorted(set(reason_codes)),
        statistics=statistics or [],
    )


def _hierarchy_record(
    *,
    row: dict[str, object],
    row_order: int,
    column_id: str,
    column_display_name: str,
    column_order: int,
    column_kind: str,
    state_id: str | None,
    reference_level: str,
    parent_state_id: str | None,
    count: int | None,
    fraction: float | None,
    evidence_state: EvidenceState,
    evidence_ids: list[str],
    reason_codes: list[str],
    denominator: int | None = None,
    denominator_scope: str | None = None,
    parent_denominator: int | None = None,
    parent_denominator_scope: str | None = None,
    parent_fraction: float | None = None,
) -> HierarchicalCellStateVisualizationRecord:
    missing = count is None
    row_id = str(row["row_id"])
    return HierarchicalCellStateVisualizationRecord(
        record_id=f"presentation:{row_id}:{column_id}",
        row_id=row_id,
        row_display_name=str(row["display_name"]),
        row_order=row_order,
        row_count=int(row["count"]),
        row_whole_product_fraction=float(row["whole_fraction"]),
        column_id=column_id,
        column_display_name=column_display_name,
        column_order=column_order,
        column_kind=column_kind,
        state_id=state_id,
        reference_level=reference_level,
        parent_state_id=parent_state_id,
        count=count,
        denominator=denominator or int(row["count"]),
        denominator_scope=(
            denominator_scope
            or (
                "declared post-QC whole-product input view"
                if row_id == "whole-product"
                else "product group observations"
            )
        ),
        fraction=fraction,
        parent_denominator=parent_denominator,
        parent_denominator_scope=parent_denominator_scope,
        parent_fraction=parent_fraction,
        evidence_state=evidence_state,
        applicability="not_assessed" if missing else "applicable",
        missingness="unavailable" if missing else "available",
        evidence_ids=sorted(set(evidence_ids)),
        reason_codes=sorted(set(reason_codes)),
    )


def _write_data_artifact(
    profile: FrozenModel,
    path: Path,
    run_id: str,
    suffix: str,
    kind: str,
    evidence_ids: list[str],
) -> ArtifactManifest:
    path.write_bytes(
        canonical_json_bytes(
            profile.model_dump(mode="json"),
            indent=2,
        )
    )
    restored = type(profile).model_validate_json(path.read_bytes())
    if restored != profile:
        raise ValueError("written visualization data does not round-trip")
    return _manifest(run_id, suffix, kind, path, evidence_ids)


def _validate_table_records(path: Path, records: list[object]) -> None:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if reader.fieldnames is None or "record_id" not in reader.fieldnames:
            raise ValueError("visualization table must expose record_id")
        observed = [str(row["record_id"]) for row in reader]
    expected = [str(record.record_id) for record in records]
    if len(observed) != len(expected) or sorted(observed) != sorted(expected):
        raise ValueError("visualization table must cover the exact typed records")


def _verify_manifest_content(artifact: ArtifactManifest) -> str:
    digest = hashlib.sha256(artifact.path.read_bytes()).hexdigest()
    if digest != artifact.sha256:
        raise ValueError("artifact content changed after its manifest was created")
    return digest


def _render_manifests(
    run_id: str,
    artifact_slug: str,
    paths: tuple[Path, Path, Path],
    evidence_ids: list[str],
) -> tuple[ArtifactManifest, ...]:
    return tuple(
        _manifest(
            run_id,
            f"{artifact_slug}-{extension}",
            "visualization_render",
            path,
            evidence_ids,
        )
        for extension, path in zip(("svg", "png", "pdf"), paths, strict=True)
    )


def _hierarchy_visualization(
    profile: HierarchicalCellStateVisualizationDataV1,
    data_artifact: ArtifactManifest,
    table_artifact: ArtifactManifest,
    renders: tuple[ArtifactManifest, ...],
    run_id: str,
    tool_version: str,
) -> VisualizationArtifactV2:
    return _visualization(
        component_ref=HIERARCHICAL_COMPOSITION_COMPONENT_REF,
        visualization_slug="hierarchical-composition",
        data_schema_ref=HIERARCHICAL_CELL_STATE_VISUALIZATION_SCHEMA_REF,
        profile=profile,
        records=profile.records,
        data_artifact=data_artifact,
        table_artifact=table_artifact,
        renders=renders,
        run_id=run_id,
        tool_version=tool_version,
        insight_title="Reference correspondence to broad cell classes and regional subtypes",
        takeaway=(
            "Broad-class and regional-subtype correspondence retain their declared "
            "denominators and are not presented as identity probabilities."
        ),
        denominator_label="Each record carries its explicit denominator",
        denominator_scope="record_specific",
        unit="fraction",
        context_bindings=[],
    )


def _source_visualization(
    profile: CellStateEvidenceMatrixDataV2,
    data_artifact: ArtifactManifest,
    table_artifact: ArtifactManifest,
    renders: tuple[ArtifactManifest, ...],
    registry: _VisualizationSourceRegistry,
    registry_sha256: str,
    run_id: str,
    tool_version: str,
) -> VisualizationArtifactV2:
    return _visualization(
        component_ref=SOURCE_STATE_EVIDENCE_COMPONENT_REF,
        visualization_slug="source-state-evidence",
        data_schema_ref=CELL_STATE_EVIDENCE_MATRIX_V2_SCHEMA_REF,
        profile=profile,
        records=profile.records,
        data_artifact=data_artifact,
        table_artifact=table_artifact,
        renders=renders,
        run_id=run_id,
        tool_version=tool_version,
        insight_title="Draft cell-state definition evidence registry",
        takeaway=(
            "This static registry distinguishes label occurrence, unrecorded mappings, "
            "dependent sources and unrun external assessment; it is not product support."
        ),
        denominator_label=None,
        denominator_scope=None,
        unit=None,
        context_bindings=[
            VisualizationContextBinding(
                role="reference",
                ref=registry.registry_id,
                version=registry.version,
                sha256=registry_sha256,
            )
        ],
    )


def _visualization(
    *,
    component_ref: str,
    visualization_slug: str,
    data_schema_ref: str,
    profile: FrozenModel,
    records: list[object],
    data_artifact: ArtifactManifest,
    table_artifact: ArtifactManifest,
    renders: tuple[ArtifactManifest, ...],
    run_id: str,
    tool_version: str,
    insight_title: str,
    takeaway: str,
    denominator_label: str | None,
    denominator_scope: str | None,
    unit: str | None,
    context_bindings: list[VisualizationContextBinding],
) -> VisualizationArtifactV2:
    evidence_states = sorted(
        {record.evidence_state for record in records},
        key=lambda item: item.value,
    )
    missing_reasons = sorted(
        {reason for record in records for reason in record.reason_codes}
    )
    applicability_states = {record.applicability for record in records}
    applicability = (
        "applicable"
        if applicability_states == {"applicable"}
        else (
            "not_assessed"
            if applicability_states == {"not_assessed"}
            else "partially_applicable"
        )
    )
    component_id, component_version = component_ref.split("@", 1)
    binding_kwargs = {
        "artifact_id": data_artifact.artifact_id,
        "schema_ref": data_schema_ref,
        "object_version": profile.object_version,
        "sha256": data_artifact.sha256,
        "records_path": "records",
        "record_lookup_key": "record_id",
        "evidence_ids_field": "evidence_ids",
        "evidence_state_field": "evidence_state",
        "scientific_status_field": "scientific_status",
        "missingness_field": "missingness",
        "applicability_field": "applicability",
    }
    if denominator_label is None:
        binding_kwargs["value_field"] = "assessment_state"
    else:
        binding_kwargs.update(
            {
                "numerator_field": "count",
                "denominator_field": "denominator",
                "denominator_scope_field": "denominator_scope",
            }
        )
    return VisualizationArtifactV2(
        visualization_id=_visualization_id(
            run_id.removeprefix("run-"),
            visualization_slug,
        ),
        component_id=component_id,
        component_version=component_version,
        data_binding=VisualizationDataBinding(**binding_kwargs),
        producer_tool_id="P0-02",
        producer_tool_version=tool_version,
        producer_run_ref=f"run:{run_id}",
        evidence_ids=profile.evidence_ids,
        evidence_states=evidence_states,
        scientific_status=profile.scientific_status,
        applicability=applicability,
        missing_reason_codes=missing_reasons,
        denominator_label=denominator_label,
        denominator_scope=denominator_scope,
        unit=unit,
        context_bindings=context_bindings,
        insight_title=insight_title,
        takeaway=takeaway,
        limitations=profile.limitations,
        accessibility=VisualizationAccessibility(
            alt_text=profile.alt_text,
            long_description=profile.long_description,
            table_artifact_id=table_artifact.artifact_id,
            data_sha256=data_artifact.sha256,
        ),
        renders=[
            VisualizationRenderBinding(
                artifact_id=render.artifact_id,
                media_type=render.media_type,
                renderer_id=_RENDERER_ID,
                renderer_version=_RENDERER_VERSION,
                export_profile_id=_EXPORT_PROFILE_ID,
                data_sha256=data_artifact.sha256,
                config_sha256=_config_sha256(component_ref),
            )
            for render in renders
        ],
    )


def _config_sha256(component_ref: str) -> str:
    renderer_source_sha256 = hashlib.sha256(
        Path(__file__).with_name("visualization.py").read_bytes()
    ).hexdigest()
    payload = canonical_json_bytes(
        {
            "component_ref": component_ref,
            "renderer_id": _RENDERER_ID,
            "renderer_version": _RENDERER_VERSION,
            "export_profile_id": _EXPORT_PROFILE_ID,
            "renderer_source_sha256": renderer_source_sha256,
            "dependencies": {
                "matplotlib": distribution_version("matplotlib"),
                "numpy": distribution_version("numpy"),
                "pandas": distribution_version("pandas"),
            },
        }
    )
    return hashlib.sha256(payload).hexdigest()


def _manifest(
    run_id: str,
    suffix: str,
    kind: str,
    path: Path,
    evidence_ids: list[str],
) -> ArtifactManifest:
    media_type = {
        ".json": "application/json",
        ".tsv": "text/tab-separated-values",
        ".svg": "image/svg+xml",
        ".png": "image/png",
        ".pdf": "application/pdf",
    }[path.suffix]
    return ArtifactManifest(
        artifact_id=_artifact_id(run_id.removeprefix("run-"), suffix),
        kind=kind,
        path=path.resolve(),
        media_type=media_type,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        evidence_ids=sorted(set(evidence_ids)),
    )
