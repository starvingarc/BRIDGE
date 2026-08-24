from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
import math
from typing import Literal, Self

from pydantic import Field, StrictFloat, StrictInt, ValidationError, field_validator, model_validator

from bridge.tool_packages._publication_safety import validate_publication_text
from bridge.toolkit.contracts import (
    CellStateEvidenceProfile,
    FrozenModel,
    QCReadinessProfile,
)


OBJECT_ID_PATTERN = r"^[A-Za-z][A-Za-z0-9._:-]*$"
VERSION_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"
SHA256_PATTERN = r"^[0-9a-f]{64}$"


def _unique(values: list[object], field: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{field} must contain unique values")


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("created_at must include a timezone")
    return value.astimezone(timezone.utc)


class VersionedObjectRef(FrozenModel):
    object_id: str = Field(pattern=OBJECT_ID_PATTERN)
    object_version: str = Field(pattern=VERSION_PATTERN)

    @property
    def ref(self) -> str:
        return f"{self.object_id}@{self.object_version}"


class ProductCase(FrozenModel):
    object_version: Literal["0.1.0"]
    product_case_id: str = Field(pattern=r"^product-case:[A-Za-z0-9._:-]+$")
    case_version: str = Field(pattern=VERSION_PATTERN)
    product_definition_ref: VersionedObjectRef
    sample_or_preparation_ref: VersionedObjectRef
    biological_unit_refs: list[VersionedObjectRef] = Field(default_factory=list)
    measurement_spec_ref: VersionedObjectRef
    assay: Literal["scRNA-seq", "snRNA-seq"]
    provenance_refs: list[VersionedObjectRef] = Field(min_length=1)
    created_at: datetime

    _created_at_utc = field_validator("created_at")(_aware_utc)

    @field_validator("biological_unit_refs", "provenance_refs")
    @classmethod
    def provenance_is_unique(
        cls, value: list[VersionedObjectRef]
    ) -> list[VersionedObjectRef]:
        _unique([item.ref for item in value], "versioned references")
        return value

    @property
    def ref(self) -> VersionedObjectRef:
        return VersionedObjectRef(
            object_id=self.product_case_id,
            object_version=self.case_version,
        )


class ProductDefinitionCard(FrozenModel):
    object_version: Literal["0.1.0"]
    product_definition_id: str = Field(
        pattern=r"^product-definition:[A-Za-z0-9._:-]+$"
    )
    definition_version: str = Field(pattern=VERSION_PATTERN)
    state_role_map_ref: VersionedObjectRef
    supported_assays: list[Literal["scRNA-seq", "snRNA-seq"]] = Field(
        min_length=1
    )
    review_state: Literal["draft", "reviewed", "frozen"]
    provenance_refs: list[VersionedObjectRef] = Field(min_length=1)

    @field_validator("supported_assays")
    @classmethod
    def assays_are_unique(cls, value: list[str]) -> list[str]:
        _unique(value, "supported_assays")
        return value

    @field_validator("provenance_refs")
    @classmethod
    def provenance_is_unique(
        cls, value: list[VersionedObjectRef]
    ) -> list[VersionedObjectRef]:
        _unique([item.ref for item in value], "provenance_refs")
        return value

    @property
    def ref(self) -> VersionedObjectRef:
        return VersionedObjectRef(
            object_id=self.product_definition_id,
            object_version=self.definition_version,
        )


class CompositionView(StrEnum):
    CONSENSUS_SUPPORTED_ONLY = "consensus_supported_only"
    SOURCE_SPECIFIC = "source_specific"


class UpstreamCompositionView(StrEnum):
    CONSENSUS_SUPPORTED_ONLY = "consensus_supported_only"
    SOURCE_SPECIFIC = "source_specific"
    RECONCILIATION_STATE = "reconciliation_state"


class UpstreamCompositionRecord(FrozenModel):
    view: UpstreamCompositionView
    source_id: str | None = Field(default=None, pattern=OBJECT_ID_PATTERN)
    label: str = Field(pattern=OBJECT_ID_PATTERN)
    label_level: Literal["L1", "L2", "L3"]
    denominator_view: str = Field(min_length=1)
    count: StrictInt = Field(ge=0)
    fraction: StrictFloat = Field(ge=0.0, le=1.0)
    denominator: StrictInt = Field(gt=0)

    _denominator_is_publication_safe = field_validator("denominator_view")(
        validate_publication_text
    )

    @model_validator(mode="after")
    def record_is_coherent(self) -> Self:
        if self.count > self.denominator:
            raise ValueError("composition count exceeds denominator")
        if not math.isclose(
            self.fraction,
            self.count / self.denominator,
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            raise ValueError("composition fraction does not match count/denominator")
        if self.view is UpstreamCompositionView.SOURCE_SPECIFIC and self.source_id is None:
            raise ValueError("source_specific composition requires source_id")
        if self.view is not UpstreamCompositionView.SOURCE_SPECIFIC and self.source_id is not None:
            raise ValueError("non-source-specific composition cannot declare source_id")
        return self


class RoleFraction(FrozenModel):
    role: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    numerator: StrictInt = Field(ge=0)
    denominator: StrictInt = Field(ge=0)
    fraction: StrictFloat | None = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def fraction_matches_counts(self) -> Self:
        if self.denominator == 0:
            if self.numerator != 0 or self.fraction is not None:
                raise ValueError("zero denominator requires zero numerator and null fraction")
        elif self.fraction is None or not math.isclose(
            self.fraction,
            self.numerator / self.denominator,
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            raise ValueError("role fraction does not match numerator/denominator")
        return self


def parse_composition(
    profile: CellStateEvidenceProfile,
) -> list[UpstreamCompositionRecord]:
    raw_records = profile.composition.get("records")
    if raw_records is None:
        return []
    if not isinstance(raw_records, list):
        raise ValueError("cell_state_composition_invalid")
    try:
        records = [
            UpstreamCompositionRecord.model_validate(item) for item in raw_records
        ]
    except (ValidationError, TypeError, ValueError):
        raise ValueError("cell_state_composition_invalid") from None
    identities = [
        (item.view, item.source_id, item.label_level, item.label)
        for item in records
    ]
    if len(identities) != len(set(identities)):
        raise ValueError("cell_state_composition_duplicate_record")
    return records


def profile_lineage_reasons(
    *,
    product_case: ProductCase,
    cell_state_profile: CellStateEvidenceProfile,
    qc_profile: QCReadinessProfile,
    input_sha256_by_role: dict[str, str],
) -> list[str]:
    """Validate the immutable P0-01 -> P0-02 -> ProductCase handoff."""

    reasons: list[str] = []
    qc_view = qc_profile.selected_data_view
    cell_state_view = cell_state_profile.input_data_view
    if qc_view is None:
        reasons.append("qc_selected_data_view_required")
    if cell_state_view is None:
        reasons.append("cell_state_input_data_view_required")
    if qc_view is not None and cell_state_view is not None:
        if qc_view != cell_state_view:
            reasons.append("cell_state_qc_data_view_mismatch")
        if (
            qc_view.sample_or_preparation_ref
            != product_case.sample_or_preparation_ref.ref
        ):
            reasons.append("product_case_data_view_binding_mismatch")
        if cell_state_profile.n_observations != cell_state_view.n_observations:
            reasons.append("cell_state_observation_count_mismatch")

    if cell_state_profile.upstream_qc_profile_ref != qc_profile.profile_id:
        reasons.append("cell_state_qc_profile_ref_mismatch")
    if (
        cell_state_profile.upstream_qc_profile_sha256
        != input_sha256_by_role.get("qc_readiness_profile")
    ):
        reasons.append("cell_state_qc_profile_checksum_mismatch")
    if (
        cell_state_profile.measurement_spec_id
        != product_case.measurement_spec_ref.object_id
        or cell_state_profile.measurement_spec_version
        != product_case.measurement_spec_ref.object_version
    ):
        reasons.append("measurement_spec_binding_mismatch")

    if cell_state_view is not None:
        try:
            records = parse_composition(cell_state_profile)
        except ValueError:
            records = []
        if any(
            record.label_level == "L1"
            and record.denominator != cell_state_view.n_observations
            for record in records
        ):
            reasons.append("cell_state_denominator_view_mismatch")
    return reasons
