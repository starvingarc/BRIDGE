from __future__ import annotations

import math
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, field_validator, model_validator

from bridge.tool_packages.p0_12_graft_assessment.analysis_models import (
    AnalysisAvailability,
    GraftExpressionAnalysisResult,
)
from bridge.tool_packages.p0_12_graft_assessment.models import (
    GraftAssessmentResult,
    GraftResultState,
)
from bridge.toolkit.contracts import EvidenceState, FrozenModel
from bridge.toolkit.visualization import VisualizationArtifactV2


GRAFT_ASSESSMENT_VISUALIZATION_DATA_SCHEMA_REF = (
    "bridge://schemas/graft-assessment-visualization-data/v0.1"
)
P012_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF = (
    "bridge://schemas/p0-12-visualization-artifact-set/v0.1"
)
SPECIMEN_SCOPE_COMPONENT_REF = "bridge.graft-assessment.specimen-scope@0.1.0"
UPLOADED_PROFILE_COMPOSITION_COMPONENT_REF = (
    "bridge.graft-assessment.uploaded-profile-composition@0.1.0"
)
REFERENCE_AND_PROGRAM_COMPONENT_REF = (
    "bridge.graft-assessment.reference-and-program-expression@0.1.0"
)
P012_COMPONENT_REFS = (
    SPECIMEN_SCOPE_COMPONENT_REF,
    UPLOADED_PROFILE_COMPOSITION_COMPONENT_REF,
    REFERENCE_AND_PROGRAM_COMPONENT_REF,
)
P012_COMPONENT_BINDINGS = (
    (SPECIMEN_SCOPE_COMPONENT_REF, "specimen-scope", "scope_records"),
    (
        UPLOADED_PROFILE_COMPOSITION_COMPONENT_REF,
        "uploaded-profile-composition",
        "composition_records",
    ),
    (
        REFERENCE_AND_PROGRAM_COMPONENT_REF,
        "reference-and-program-expression",
        "molecular_records",
    ),
)

_SHA256 = r"^[0-9a-f]{64}$"
_RECORD_ID = r"^[a-z][a-z0-9.-]+$"
_SAFE_ID = r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"


def _artifact_id(digest: str, suffix: str) -> str:
    return f"artifact:run-{digest}:{suffix}"


def _visualization_id(digest: str, slug: str) -> str:
    return f"visualization:run-{digest}:{slug}"


def _sorted_unique(values: list[str], field_name: str) -> list[str]:
    if values != sorted(set(values)):
        raise ValueError(f"{field_name} must be sorted and unique")
    return values


class GraftVisualizationMode(StrEnum):
    NOT_PROVIDED = "not_provided"
    PRECOMPUTED = "precomputed"
    EXPRESSION_ANALYSIS = "expression_analysis"


class ScopeValueKind(StrEnum):
    IDENTIFIER = "identifier"
    COUNT = "count"
    DECLARED_METADATA = "declared_metadata"
    ANALYSIS_SEMANTICS = "analysis_semantics"
    AVAILABILITY = "availability"
    SCOPE_BOUNDARY = "scope_boundary"


class CompositionRowKind(StrEnum):
    STATE_PROBABILITY_MASS = "state_probability_mass"
    UNASSIGNED_PROBABILITY_MASS = "unassigned_probability_mass"
    COMPONENT_UNAVAILABLE = "component_unavailable"


class MolecularPanel(StrEnum):
    REFERENCE_SIMILARITY = "reference_similarity"
    REGISTERED_GENE_PROGRAM_EXPRESSION = "registered_gene_program_expression"


class MolecularRowKind(StrEnum):
    REFERENCE_SIMILARITY = "reference_similarity"
    REGISTERED_GENE_PROGRAM_EXPRESSION = "registered_gene_program_expression"
    COMPONENT_UNAVAILABLE = "component_unavailable"


class CandidateEvidenceAnchor(FrozenModel):
    anchor_id: str = Field(pattern=r"^candidate-evidence:p0-12:[a-f0-9]{64}$")
    anchor_kind: Literal["candidate_result_lineage"] = "candidate_result_lineage"
    formal_evidence: Literal[False] = False
    source_result_ref: str = Field(pattern=_SAFE_ID)
    source_result_sha256: str = Field(pattern=_SHA256)


class _VisualizationRecord(FrozenModel):
    record_id: str = Field(pattern=_RECORD_ID)
    evidence_ids: list[str] = Field(min_length=1)
    evidence_state: EvidenceState
    scientific_status: Literal["candidate"] = "candidate"
    missingness: Literal["available", "unavailable"]
    applicability: Literal["applicable", "not_assessed"]
    reason_codes: list[str]

    @field_validator("evidence_ids", "reason_codes")
    @classmethod
    def set_like_fields_are_sorted(cls, values: list[str], info):
        return _sorted_unique(values, info.field_name)

    def _validate_availability_axes(self) -> None:
        unavailable = self.missingness == "unavailable"
        if unavailable != (self.applicability == "not_assessed"):
            raise ValueError("missingness and applicability must agree")
        if unavailable != (self.evidence_state is EvidenceState.UNAVAILABLE):
            raise ValueError("unavailable records require unavailable evidence")
        if unavailable != bool(self.reason_codes):
            raise ValueError("unavailable records require a reason")


class SpecimenScopeRecord(_VisualizationRecord):
    record_kind: Literal["specimen_scope"] = "specimen_scope"
    field_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(min_length=1)
    display_value: str = Field(min_length=1)
    value_kind: ScopeValueKind

    @model_validator(mode="after")
    def axes_are_coherent(self) -> Self:
        self._validate_availability_axes()
        return self


class GraftCompositionRecord(_VisualizationRecord):
    record_kind: Literal["graft_composition"] = "graft_composition"
    row_kind: CompositionRowKind
    label: str = Field(min_length=1)
    state_id: str | None = Field(default=None, pattern=_SAFE_ID)
    mean_fraction: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)] | None = (
        None
    )
    probability_mass_equivalent: (
        Annotated[float, Field(ge=0, allow_inf_nan=False)] | None
    ) = None
    denominator_rows: int | None = Field(default=None, ge=1)
    denominator_scope: Literal["all_uploaded_rows"] | None = None
    unit: Literal["fraction"] | None = None

    @model_validator(mode="after")
    def values_are_coherent(self) -> Self:
        self._validate_availability_axes()
        unavailable = self.row_kind is CompositionRowKind.COMPONENT_UNAVAILABLE
        values = (
            self.mean_fraction,
            self.probability_mass_equivalent,
            self.denominator_rows,
            self.denominator_scope,
            self.unit,
        )
        if unavailable:
            if self.state_id is not None or any(value is not None for value in values):
                raise ValueError("unavailable composition cannot carry a value")
            return self
        if any(value is None for value in values):
            raise ValueError("available composition requires complete values")
        if self.row_kind is CompositionRowKind.STATE_PROBABILITY_MASS:
            if self.state_id is None:
                raise ValueError("state probability mass requires a state ID")
        elif self.state_id is not None:
            raise ValueError("unassigned probability mass cannot carry a state ID")
        expected = self.probability_mass_equivalent / self.denominator_rows
        if not math.isclose(self.mean_fraction, expected, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError("composition must preserve supplied probability mass")
        return self


class GraftMolecularEvidenceRecord(_VisualizationRecord):
    record_kind: Literal["graft_molecular_evidence"] = "graft_molecular_evidence"
    row_kind: MolecularRowKind
    panel: MolecularPanel
    sample_id: str | None = Field(default=None, pattern=_SAFE_ID)
    profile_id: str | None = Field(default=None, pattern=_SAFE_ID)
    program_id: str | None = Field(default=None, pattern=_SAFE_ID)
    display_value: Annotated[float, Field(allow_inf_nan=False)] | None = None
    spearman_rho: Annotated[float, Field(ge=-1, le=1, allow_inf_nan=False)] | None = (
        None
    )
    mean_log1p_cp10k: Annotated[float, Field(allow_inf_nan=False)] | None = None
    shared_gene_count: int | None = Field(default=None, ge=0)
    gene_count: int | None = Field(default=None, ge=0)
    gene_coverage: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)] | None = (
        None
    )
    unit: Literal["spearman_rho", "mean_log1p_cp10k"] | None = None

    @model_validator(mode="after")
    def values_are_coherent(self) -> Self:
        self._validate_availability_axes()
        if self.row_kind is MolecularRowKind.COMPONENT_UNAVAILABLE:
            if any(
                value is not None
                for value in (
                    self.sample_id,
                    self.profile_id,
                    self.program_id,
                    self.display_value,
                    self.spearman_rho,
                    self.mean_log1p_cp10k,
                    self.shared_gene_count,
                    self.gene_count,
                    self.gene_coverage,
                    self.unit,
                )
            ):
                raise ValueError("unavailable molecular panel cannot carry row values")
            return self

        if self.sample_id is None:
            raise ValueError("molecular evidence requires a sample ID")
        available = self.missingness == "available"
        if self.row_kind is MolecularRowKind.REFERENCE_SIMILARITY:
            if (
                self.panel is not MolecularPanel.REFERENCE_SIMILARITY
                or self.profile_id is None
                or self.program_id is not None
                or self.shared_gene_count is None
                or self.gene_count is not None
                or self.gene_coverage is not None
                or self.unit != "spearman_rho"
                or self.mean_log1p_cp10k is not None
                or available != (self.spearman_rho is not None)
                or self.display_value != self.spearman_rho
            ):
                raise ValueError("reference-similarity fields disagree")
        elif (
            self.panel is not MolecularPanel.REGISTERED_GENE_PROGRAM_EXPRESSION
            or self.program_id is None
            or self.profile_id is not None
            or self.gene_count is None
            or self.gene_coverage is None
            or self.unit != "mean_log1p_cp10k"
            or self.spearman_rho is not None
            or self.shared_gene_count is not None
            or available != (self.mean_log1p_cp10k is not None)
            or self.display_value != self.mean_log1p_cp10k
        ):
            raise ValueError("gene-program-expression fields disagree")
        return self


class GraftAssessmentVisualizationDataV1(FrozenModel):
    object_version: Literal["0.1.0"] = "0.1.0"
    schema_ref: Literal[GRAFT_ASSESSMENT_VISUALIZATION_DATA_SCHEMA_REF] = (
        GRAFT_ASSESSMENT_VISUALIZATION_DATA_SCHEMA_REF
    )
    visualization_profile_id: str = Field(
        pattern=r"^graft-assessment-visualization:[a-f0-9]{16}$"
    )
    producer_tool_id: Literal["P0-12"] = "P0-12"
    producer_tool_version: str = Field(min_length=1)
    producer_run_ref: str = Field(pattern=r"^run:run-[a-f0-9]{16}$")
    source_result_ref: str = Field(pattern=_SAFE_ID)
    source_result_sha256: str = Field(pattern=_SHA256)
    source_created_at: datetime
    mode: GraftVisualizationMode
    candidate_evidence_anchor: CandidateEvidenceAnchor
    evidence_ids: list[str] = Field(min_length=1)
    formal_evidence_ids: list[str]
    formal_evidence_count: int = Field(ge=0)
    uploaded_profile_count: int | None = Field(default=None, ge=1)
    technical_sample_count: int | None = Field(default=None, ge=1)
    reference_source_family_id: str | None = Field(default=None, pattern=_SAFE_ID)
    marker_source_family_id: str | None = Field(default=None, pattern=_SAFE_ID)
    scope_records: list[SpecimenScopeRecord] = Field(min_length=1)
    composition_records: list[GraftCompositionRecord] = Field(min_length=1)
    molecular_records: list[GraftMolecularEvidenceRecord] = Field(min_length=2)
    technical_samples_are_not_biological_replicates: Literal[True] = True
    composition_is_pooled_probability_mass: Literal[True] = True
    unassigned_is_not_an_unknown_state: Literal[True] = True
    pretransplant_evidence_effect: Literal["none"] = "none"
    domain_score: None = None

    @field_validator("evidence_ids", "formal_evidence_ids")
    @classmethod
    def evidence_is_sorted(cls, values: list[str], info):
        return _sorted_unique(values, info.field_name)

    @model_validator(mode="after")
    def profile_is_coherent(self) -> Self:
        digest = self.visualization_profile_id.rsplit(":", 1)[1]
        if self.producer_run_ref != f"run:run-{digest}":
            raise ValueError("visualization profile and producer run disagree")
        anchor = self.candidate_evidence_anchor
        if (
            anchor.source_result_ref != self.source_result_ref
            or anchor.source_result_sha256 != self.source_result_sha256
        ):
            raise ValueError("candidate evidence anchor must bind the source result")
        if anchor.anchor_id in self.formal_evidence_ids:
            raise ValueError("candidate lineage anchor is not formal evidence")
        if self.formal_evidence_count != len(self.formal_evidence_ids):
            raise ValueError("formal evidence count must match formal evidence IDs")
        expected_evidence = sorted({anchor.anchor_id, *self.formal_evidence_ids})
        if self.evidence_ids != expected_evidence:
            raise ValueError(
                "profile evidence must separate lineage and formal evidence"
            )
        for records in (
            self.scope_records,
            self.composition_records,
            self.molecular_records,
        ):
            record_ids = [record.record_id for record in records]
            if len(record_ids) != len(set(record_ids)):
                raise ValueError("visualization record IDs must be unique")
        for record in (
            *self.scope_records,
            *self.composition_records,
            *self.molecular_records,
        ):
            if anchor.anchor_id not in record.evidence_ids or not set(
                record.evidence_ids
            ).issubset(self.evidence_ids):
                raise ValueError("every record must retain source-result lineage")
        expected_scope_fields = {
            GraftVisualizationMode.NOT_PROVIDED: [
                "input_state",
                "composition",
                "reference_similarity",
                "program_expression",
                "pretransplant_effect",
            ],
            GraftVisualizationMode.PRECOMPUTED: [
                "input_state",
                "evidence_roles",
                "evidence_records",
                "animal_metadata",
                "timepoint_metadata",
                "replicate_label",
                "preparation_linkage",
                "declared_confounders",
                "analysis_scope",
                "expression_matrix",
                "pretransplant_effect",
            ],
            GraftVisualizationMode.EXPRESSION_ANALYSIS: [
                "animal",
                "graft",
                "post_transplant_timepoint",
                "assay",
                "uploaded_profiles",
                "genes",
                "technical_samples",
                "matrix_semantics",
                "profile_aggregation",
                "reference_source_family",
                "marker_source_family",
                "expression_qc",
                "species_selection",
                "pretransplant_effect",
            ],
        }[self.mode]
        if [record.field_id for record in self.scope_records] != expected_scope_fields:
            raise ValueError("scope fields must be complete, unique and mode ordered")

        lineage_ids = [anchor.anchor_id]
        if self.mode is GraftVisualizationMode.PRECOMPUTED:
            for record in self.scope_records:
                expected_record_evidence = (
                    self.evidence_ids
                    if record.field_id in {"evidence_roles", "evidence_records"}
                    else lineage_ids
                )
                if record.evidence_ids != expected_record_evidence:
                    raise ValueError(
                        "precomputed records must bind only their exact evidence"
                    )
            records_requiring_lineage_only = (
                *self.composition_records,
                *self.molecular_records,
            )
        else:
            records_requiring_lineage_only = (
                *self.scope_records,
                *self.composition_records,
                *self.molecular_records,
            )
        if any(
            record.evidence_ids != lineage_ids
            for record in records_requiring_lineage_only
        ):
            raise ValueError("records must bind only source-result lineage")

        unavailable_composition = [
            record
            for record in self.composition_records
            if record.row_kind is CompositionRowKind.COMPONENT_UNAVAILABLE
        ]
        unavailable_molecular = [
            record
            for record in self.molecular_records
            if record.row_kind is MolecularRowKind.COMPONENT_UNAVAILABLE
        ]
        if self.mode is not GraftVisualizationMode.EXPRESSION_ANALYSIS:
            if (
                self.uploaded_profile_count is not None
                or self.technical_sample_count is not None
                or self.reference_source_family_id is not None
                or self.marker_source_family_id is not None
            ):
                raise ValueError(
                    "non-expression modes cannot declare expression context"
                )
            if (
                self.mode is GraftVisualizationMode.NOT_PROVIDED
                and self.formal_evidence_ids
            ):
                raise ValueError("not-provided mode cannot carry formal evidence")
            if len(self.composition_records) != 1 or len(unavailable_composition) != 1:
                raise ValueError(
                    "non-expression modes require a composition empty state"
                )
            if len(self.molecular_records) != 2 or len(unavailable_molecular) != 2:
                raise ValueError(
                    "non-expression modes require two molecular empty states"
                )
            if [record.panel for record in self.molecular_records] != [
                MolecularPanel.REFERENCE_SIMILARITY,
                MolecularPanel.REGISTERED_GENE_PROGRAM_EXPRESSION,
            ]:
                raise ValueError(
                    "non-expression modes require one empty row per molecular panel"
                )
            return self

        if unavailable_composition or unavailable_molecular:
            raise ValueError("expression mode uses row-level availability")
        if self.formal_evidence_ids:
            raise ValueError("expression mode cannot carry formal evidence")
        if self.uploaded_profile_count is None or self.technical_sample_count is None:
            raise ValueError(
                "expression mode requires uploaded-profile and sample counts"
            )
        if (
            self.reference_source_family_id is None
            or self.marker_source_family_id is None
        ):
            raise ValueError(
                "expression mode requires reference and marker source families"
            )
        if any(
            record.denominator_rows != self.uploaded_profile_count
            for record in self.composition_records
        ):
            raise ValueError(
                "composition denominators must equal uploaded-profile count"
            )
        assigned = [
            record
            for record in self.composition_records
            if record.row_kind is CompositionRowKind.STATE_PROBABILITY_MASS
        ]
        unassigned = [
            record
            for record in self.composition_records
            if record.row_kind is CompositionRowKind.UNASSIGNED_PROBABILITY_MASS
        ]
        if not assigned or len(unassigned) != 1:
            raise ValueError(
                "expression composition requires states and one unassigned row"
            )
        total = (
            sum(record.mean_fraction for record in assigned)
            + unassigned[0].mean_fraction
        )
        if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-6):
            raise ValueError(
                "assigned and unassigned probability mass must be conserved"
            )
        if {record.panel for record in self.molecular_records} != set(MolecularPanel):
            raise ValueError("expression mode requires both molecular panels")
        panel_samples: list[set[str]] = []
        for panel, id_field in (
            (MolecularPanel.REFERENCE_SIMILARITY, "profile_id"),
            (
                MolecularPanel.REGISTERED_GENE_PROGRAM_EXPRESSION,
                "program_id",
            ),
        ):
            panel_records = [
                record for record in self.molecular_records if record.panel is panel
            ]
            samples = {record.sample_id for record in panel_records}
            targets = {getattr(record, id_field) for record in panel_records}
            keys = [
                (record.sample_id, getattr(record, id_field))
                for record in panel_records
            ]
            expected_keys = {
                (sample_id, target_id) for sample_id in samples for target_id in targets
            }
            if (
                None in samples
                or None in targets
                or len(keys) != len(set(keys))
                or set(keys) != expected_keys
            ):
                raise ValueError("molecular panel requires a complete Cartesian grid")
            panel_samples.append(samples)
        if (
            panel_samples[0] != panel_samples[1]
            or len(panel_samples[0]) != self.technical_sample_count
        ):
            raise ValueError("molecular panels must cover every technical sample")
        return self


class P012VisualizationArtifactSet(FrozenModel):
    object_version: Literal["0.1.0"] = "0.1.0"
    schema_ref: Literal[P012_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF] = (
        P012_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF
    )
    artifact_set_id: str = Field(pattern=r"^p0-12-visualizations:[a-f0-9]{16}$")
    data_profile_artifact_id: str = Field(min_length=1)
    data_profile_sha256: str = Field(pattern=_SHA256)
    visualizations: list[VisualizationArtifactV2] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def component_set_is_complete(self) -> Self:
        if [item.component_ref for item in self.visualizations] != list(
            P012_COMPONENT_REFS
        ):
            raise ValueError("P0-12 artifact set requires the three fixed components")
        if any(
            item.data_binding.artifact_id != self.data_profile_artifact_id
            or item.data_binding.sha256 != self.data_profile_sha256
            for item in self.visualizations
        ):
            raise ValueError("visualizations must bind the declared data profile")
        expected_media = ["image/svg+xml", "image/png", "application/pdf"]
        if any(
            [render.media_type for render in item.renders] != expected_media
            for item in self.visualizations
        ):
            raise ValueError("each visualization requires ordered SVG, PNG and PDF")
        digest = self.artifact_set_id.rsplit(":", 1)[1]
        if self.data_profile_artifact_id != _artifact_id(
            digest, "graft-assessment-visualization-data"
        ):
            raise ValueError("data profile artifact ID must bind the artifact-set run")
        if len({item.visualization_id for item in self.visualizations}) != 3:
            raise ValueError("visualization IDs must be unique")
        table_ids = [
            item.accessibility.table_artifact_id for item in self.visualizations
        ]
        if len(set(table_ids)) != 3:
            raise ValueError("visualization table artifact IDs must be unique")
        for item, (component_ref, slug, records_path) in zip(
            self.visualizations, P012_COMPONENT_BINDINGS, strict=True
        ):
            if (
                item.component_ref != component_ref
                or item.visualization_id != _visualization_id(digest, slug)
                or item.data_binding.records_path != records_path
                or item.accessibility.table_artifact_id
                != _artifact_id(digest, f"graft-assessment-{slug}-table")
            ):
                raise ValueError("visualization identity does not match its component")
            expected_render_ids = [
                _artifact_id(digest, f"graft-assessment-{slug}-{extension}")
                for extension in ("svg", "png", "pdf")
            ]
            if [render.artifact_id for render in item.renders] != expected_render_ids:
                raise ValueError("render artifact IDs must match format and component")
        producer_contracts = {
            (
                item.producer_tool_id,
                item.producer_tool_version,
                item.producer_run_ref,
            )
            for item in self.visualizations
        }
        if producer_contracts != {
            ("P0-12", self.visualizations[0].producer_tool_version, f"run:run-{digest}")
        }:
            raise ValueError("visualizations must share the artifact-set producer run")
        all_ids = {
            self.data_profile_artifact_id,
            *table_ids,
            *(
                render.artifact_id
                for item in self.visualizations
                for render in item.renders
            ),
        }
        if len(all_ids) != 13:
            raise ValueError("data, table and render artifact IDs must be disjoint")
        return self


def build_graft_assessment_visualization_data(
    result: GraftAssessmentResult | GraftExpressionAnalysisResult,
    result_sha: str,
    run_id: str,
    tool_version: str,
) -> GraftAssessmentVisualizationDataV1:
    anchor_id = f"candidate-evidence:p0-12:{result_sha}"
    lineage_evidence_ids = [anchor_id]
    formal_evidence_ids = (
        []
        if isinstance(result, GraftExpressionAnalysisResult)
        else sorted(
            {
                evidence_id
                for summary in result.role_summaries
                for evidence_id in summary.evidence_ids
            }
        )
    )
    evidence_ids = sorted({anchor_id, *formal_evidence_ids})
    if isinstance(result, GraftExpressionAnalysisResult):
        mode = GraftVisualizationMode.EXPRESSION_ANALYSIS
        scope_records = _expression_scope_records(result, lineage_evidence_ids)
        composition_records = _expression_composition_records(
            result, lineage_evidence_ids
        )
        molecular_records = _expression_molecular_records(result, lineage_evidence_ids)
    elif result.state is GraftResultState.NOT_PROVIDED:
        mode = GraftVisualizationMode.NOT_PROVIDED
        scope_records = _not_provided_scope_records(lineage_evidence_ids)
        composition_records = _empty_composition_records(
            lineage_evidence_ids, "graft_data_not_provided"
        )
        molecular_records = _empty_molecular_records(
            lineage_evidence_ids, "graft_data_not_provided"
        )
    else:
        mode = GraftVisualizationMode.PRECOMPUTED
        scope_records = _precomputed_scope_records(
            result, lineage_evidence_ids, evidence_ids
        )
        composition_records = _empty_composition_records(
            lineage_evidence_ids, "graft_expression_data_not_supplied"
        )
        molecular_records = _empty_molecular_records(
            lineage_evidence_ids, "graft_expression_data_not_supplied"
        )
    return GraftAssessmentVisualizationDataV1(
        visualization_profile_id=(
            "graft-assessment-visualization:" + run_id.removeprefix("run-")
        ),
        producer_tool_version=tool_version,
        producer_run_ref=f"run:{run_id}",
        source_result_ref=result.result_id,
        source_result_sha256=result_sha,
        source_created_at=result.created_at,
        mode=mode,
        candidate_evidence_anchor=CandidateEvidenceAnchor(
            anchor_id=anchor_id,
            source_result_ref=result.result_id,
            source_result_sha256=result_sha,
        ),
        evidence_ids=evidence_ids,
        formal_evidence_ids=formal_evidence_ids,
        formal_evidence_count=len(formal_evidence_ids),
        uploaded_profile_count=(
            result.cell_count
            if isinstance(result, GraftExpressionAnalysisResult)
            else None
        ),
        technical_sample_count=(
            result.sample_count
            if isinstance(result, GraftExpressionAnalysisResult)
            else None
        ),
        reference_source_family_id=(
            result.reference_source_family_id
            if isinstance(result, GraftExpressionAnalysisResult)
            else None
        ),
        marker_source_family_id=(
            result.marker_source_family_id
            if isinstance(result, GraftExpressionAnalysisResult)
            else None
        ),
        scope_records=scope_records,
        composition_records=composition_records,
        molecular_records=molecular_records,
    )


def _record_axes(
    evidence_ids: list[str],
    *,
    unavailable_reason: str | None = None,
    unavailable_reasons: list[str] | None = None,
) -> dict[str, object]:
    reasons = sorted(
        set(unavailable_reasons or [])
        | ({unavailable_reason} if unavailable_reason is not None else set())
    )
    return {
        "evidence_ids": evidence_ids,
        "evidence_state": (
            EvidenceState.UNAVAILABLE if reasons else EvidenceState.INFERRED
        ),
        "missingness": "unavailable" if reasons else "available",
        "applicability": "not_assessed" if reasons else "applicable",
        "reason_codes": reasons,
    }


def _scope_record(
    position: int,
    field_id: str,
    label: str,
    display_value: str,
    value_kind: ScopeValueKind,
    evidence_ids: list[str],
    unavailable_reason: str | None = None,
) -> SpecimenScopeRecord:
    return SpecimenScopeRecord(
        record_id=f"scope.{position:03d}",
        field_id=field_id,
        label=label,
        display_value=display_value,
        value_kind=value_kind,
        **_record_axes(evidence_ids, unavailable_reason=unavailable_reason),
    )


def _expression_scope_records(
    result: GraftExpressionAnalysisResult,
    evidence_ids: list[str],
) -> list[SpecimenScopeRecord]:
    values = [
        (
            "animal",
            "Animal",
            result.animal_id,
            ScopeValueKind.IDENTIFIER,
            None,
        ),
        (
            "graft",
            "Graft",
            result.graft_id,
            ScopeValueKind.IDENTIFIER,
            None,
        ),
        (
            "post_transplant_timepoint",
            "Post-transplant timepoint",
            result.post_transplant_timepoint,
            ScopeValueKind.DECLARED_METADATA,
            None,
        ),
        (
            "assay",
            "Assay",
            result.assay.value,
            ScopeValueKind.DECLARED_METADATA,
            None,
        ),
        (
            "uploaded_profiles",
            "Uploaded profiles",
            f"{result.cell_count:,}",
            ScopeValueKind.COUNT,
            None,
        ),
        (
            "genes",
            "Genes",
            f"{result.gene_count:,}",
            ScopeValueKind.COUNT,
            None,
        ),
        (
            "technical_samples",
            "Technical samples",
            f"{result.sample_count:,}",
            ScopeValueKind.COUNT,
            None,
        ),
        (
            "matrix_semantics",
            "Expression matrix",
            result.matrix_semantics.value,
            ScopeValueKind.ANALYSIS_SEMANTICS,
            None,
        ),
        (
            "profile_aggregation",
            "Reference comparison aggregation",
            result.profile_aggregation.value,
            ScopeValueKind.ANALYSIS_SEMANTICS,
            None,
        ),
        (
            "reference_source_family",
            "Reference source family",
            result.reference_source_family_id,
            ScopeValueKind.IDENTIFIER,
            None,
        ),
        (
            "marker_source_family",
            "Marker-program source family",
            result.marker_source_family_id,
            ScopeValueKind.IDENTIFIER,
            None,
        ),
        (
            "expression_qc",
            "Expression QC",
            "not reassessed",
            ScopeValueKind.SCOPE_BOUNDARY,
            "graft_expression_qc_not_reassessed",
        ),
        (
            "species_selection",
            "Species assignment and profile selection",
            "not recorded in this result",
            ScopeValueKind.SCOPE_BOUNDARY,
            "graft_species_selection_not_recorded",
        ),
        (
            "pretransplant_effect",
            "Effect on pre-transplant evidence",
            "none",
            ScopeValueKind.SCOPE_BOUNDARY,
            None,
        ),
    ]
    return [
        _scope_record(
            index,
            field_id,
            label,
            display_value,
            value_kind,
            evidence_ids,
            unavailable_reason,
        )
        for index, (
            field_id,
            label,
            display_value,
            value_kind,
            unavailable_reason,
        ) in enumerate(values, start=1)
    ]


def _precomputed_scope_records(
    result: GraftAssessmentResult,
    evidence_ids: list[str],
    role_evidence_ids: list[str],
) -> list[SpecimenScopeRecord]:
    evidence_count = sum(summary.record_count for summary in result.role_summaries)
    missing = set(result.missing_metadata)
    values = [
        (
            "input_state",
            "Post-transplant input",
            "structured evidence supplied",
            ScopeValueKind.AVAILABILITY,
            None,
        ),
        (
            "evidence_roles",
            "Evidence roles",
            f"{len(result.role_summaries):,}",
            ScopeValueKind.COUNT,
            None,
        ),
        (
            "evidence_records",
            "Evidence records",
            f"{evidence_count:,}",
            ScopeValueKind.COUNT,
            None,
        ),
        (
            "animal_metadata",
            "Animal metadata",
            "not recorded" if "animal_id" in missing else "recorded",
            ScopeValueKind.AVAILABILITY,
            ("graft_animal_id_not_recorded" if "animal_id" in missing else None),
        ),
        (
            "timepoint_metadata",
            "Post-transplant timepoint",
            ("not recorded" if "post_transplant_timepoint" in missing else "recorded"),
            ScopeValueKind.AVAILABILITY,
            (
                "graft_timepoint_not_recorded"
                if "post_transplant_timepoint" in missing
                else None
            ),
        ),
        (
            "replicate_label",
            "Biological-replicate label",
            (
                "not recorded"
                if "biological_replicate_id" in missing
                else "recorded; independence not inferred"
            ),
            ScopeValueKind.SCOPE_BOUNDARY,
            (
                "graft_replicate_label_not_recorded"
                if "biological_replicate_id" in missing
                else None
            ),
        ),
        (
            "preparation_linkage",
            "Pre-transplant preparation linkage",
            result.linkage_state.value,
            ScopeValueKind.AVAILABILITY,
            None,
        ),
        (
            "declared_confounders",
            "Declared confounder references",
            f"{len(result.confounder_refs):,}",
            ScopeValueKind.COUNT,
            None,
        ),
        (
            "analysis_scope",
            "Interpretation",
            "descriptive evidence summary",
            ScopeValueKind.SCOPE_BOUNDARY,
            None,
        ),
        (
            "expression_matrix",
            "Expression matrix",
            "not supplied to this analysis mode",
            ScopeValueKind.SCOPE_BOUNDARY,
            "graft_expression_data_not_supplied",
        ),
        (
            "pretransplant_effect",
            "Effect on pre-transplant evidence",
            "none",
            ScopeValueKind.SCOPE_BOUNDARY,
            None,
        ),
    ]
    return [
        _scope_record(
            index,
            field_id,
            label,
            display_value,
            value_kind,
            (
                role_evidence_ids
                if field_id in {"evidence_roles", "evidence_records"}
                else evidence_ids
            ),
            unavailable_reason,
        )
        for index, (
            field_id,
            label,
            display_value,
            value_kind,
            unavailable_reason,
        ) in enumerate(values, start=1)
    ]


def _not_provided_scope_records(
    evidence_ids: list[str],
) -> list[SpecimenScopeRecord]:
    unavailable_values = [
        ("input_state", "Post-transplant input", "not provided"),
        ("composition", "Cell-state composition", "not assessed"),
        ("reference_similarity", "Reference similarity", "not assessed"),
        (
            "program_expression",
            "Registered gene-program expression",
            "not assessed",
        ),
    ]
    records = [
        _scope_record(
            index,
            field_id,
            label,
            value,
            ScopeValueKind.AVAILABILITY,
            evidence_ids,
            "graft_data_not_provided",
        )
        for index, (field_id, label, value) in enumerate(unavailable_values, start=1)
    ]
    records.append(
        _scope_record(
            len(records) + 1,
            "pretransplant_effect",
            "Effect on pre-transplant evidence",
            "none",
            ScopeValueKind.SCOPE_BOUNDARY,
            evidence_ids,
        )
    )
    return records


def _expression_composition_records(
    result: GraftExpressionAnalysisResult,
    evidence_ids: list[str],
) -> list[GraftCompositionRecord]:
    records = [
        GraftCompositionRecord(
            record_id=f"composition.{index:03d}",
            row_kind=CompositionRowKind.STATE_PROBABILITY_MASS,
            label=item.state_id,
            state_id=item.state_id,
            mean_fraction=item.mean_fraction,
            probability_mass_equivalent=item.cell_equivalent,
            denominator_rows=item.denominator_cells,
            denominator_scope="all_uploaded_rows",
            unit="fraction",
            **_record_axes(evidence_ids),
        )
        for index, item in enumerate(
            sorted(
                result.composition_estimates,
                key=lambda value: (
                    -value.mean_fraction,
                    value.state_id,
                ),
            ),
            start=1,
        )
    ]
    records.append(
        GraftCompositionRecord(
            record_id=f"composition.{len(records) + 1:03d}",
            row_kind=(CompositionRowKind.UNASSIGNED_PROBABILITY_MASS),
            label="Unassigned probability mass",
            mean_fraction=result.unassigned_fraction,
            probability_mass_equivalent=(
                result.unassigned_fraction * result.cell_count
            ),
            denominator_rows=result.cell_count,
            denominator_scope="all_uploaded_rows",
            unit="fraction",
            **_record_axes(evidence_ids),
        )
    )
    return records


def _empty_composition_records(
    evidence_ids: list[str],
    reason: str,
) -> list[GraftCompositionRecord]:
    return [
        GraftCompositionRecord(
            record_id="composition.001",
            row_kind=CompositionRowKind.COMPONENT_UNAVAILABLE,
            label="Cell-state composition not assessed",
            **_record_axes(evidence_ids, unavailable_reason=reason),
        )
    ]


def _expression_molecular_records(
    result: GraftExpressionAnalysisResult,
    evidence_ids: list[str],
) -> list[GraftMolecularEvidenceRecord]:
    records: list[GraftMolecularEvidenceRecord] = []
    for item in result.reference_support:
        available = item.availability is AnalysisAvailability.AVAILABLE
        records.append(
            GraftMolecularEvidenceRecord(
                record_id=f"molecular.{len(records) + 1:04d}",
                row_kind=MolecularRowKind.REFERENCE_SIMILARITY,
                panel=MolecularPanel.REFERENCE_SIMILARITY,
                sample_id=item.sample_id,
                profile_id=item.profile_id,
                display_value=item.spearman_correlation,
                spearman_rho=item.spearman_correlation,
                shared_gene_count=item.shared_gene_count,
                unit="spearman_rho",
                **_record_axes(
                    evidence_ids,
                    unavailable_reasons=(
                        None
                        if available
                        else (
                            item.reason_codes
                            or ["graft_reference_similarity_unavailable"]
                        )
                    ),
                ),
            )
        )
    for item in result.program_evidence:
        available = item.availability is AnalysisAvailability.AVAILABLE
        records.append(
            GraftMolecularEvidenceRecord(
                record_id=f"molecular.{len(records) + 1:04d}",
                row_kind=(MolecularRowKind.REGISTERED_GENE_PROGRAM_EXPRESSION),
                panel=(MolecularPanel.REGISTERED_GENE_PROGRAM_EXPRESSION),
                sample_id=item.sample_id,
                program_id=item.program_id,
                display_value=item.mean_expression,
                mean_log1p_cp10k=item.mean_expression,
                gene_count=item.gene_count,
                gene_coverage=item.gene_coverage,
                unit="mean_log1p_cp10k",
                **_record_axes(
                    evidence_ids,
                    unavailable_reasons=(
                        None
                        if available
                        else (
                            item.reason_codes
                            or ["graft_program_expression_unavailable"]
                        )
                    ),
                ),
            )
        )
    return records


def _empty_molecular_records(
    evidence_ids: list[str],
    reason: str,
) -> list[GraftMolecularEvidenceRecord]:
    return [
        GraftMolecularEvidenceRecord(
            record_id="molecular.0001",
            row_kind=MolecularRowKind.COMPONENT_UNAVAILABLE,
            panel=MolecularPanel.REFERENCE_SIMILARITY,
            **_record_axes(evidence_ids, unavailable_reason=reason),
        ),
        GraftMolecularEvidenceRecord(
            record_id="molecular.0002",
            row_kind=MolecularRowKind.COMPONENT_UNAVAILABLE,
            panel=(MolecularPanel.REGISTERED_GENE_PROGRAM_EXPRESSION),
            **_record_axes(evidence_ids, unavailable_reason=reason),
        ),
    ]


PUBLIC_VISUALIZATION_SCHEMA_MODELS = {
    GRAFT_ASSESSMENT_VISUALIZATION_DATA_SCHEMA_REF: GraftAssessmentVisualizationDataV1,
    P012_VISUALIZATION_ARTIFACT_SET_SCHEMA_REF: P012VisualizationArtifactSet,
}
