from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
import hashlib
import json
import math
from typing import Literal, Self

from pydantic import ConfigDict, Field, StrictFloat, StrictInt, ValidationError, field_validator, model_validator

from bridge.tool_packages._publication_safety import validate_publication_text
from bridge.toolkit.contracts import (
    CellStateEvidenceProfileV2,
    FrozenModel,
    QCReadinessProfileV2,
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


class BiologicalUnitKind(StrEnum):
    CAPTURE = "capture"
    PREPARATION = "preparation"
    SAMPLE = "sample"
    DONOR = "donor"
    ANIMAL = "animal"
    GRAFT_UNIT = "graft_unit"


IndependenceGroupKind = Literal["preparation", "sample", "donor", "animal"]


class BiologicalUnitLineageState(StrEnum):
    DECLARED = "declared"
    REVIEWED = "reviewed"
    FROZEN = "frozen"


class BiologicalUnitBinding(FrozenModel):
    analysis_unit_ref: VersionedObjectRef
    analysis_unit_kind: BiologicalUnitKind
    independence_group_ref: VersionedObjectRef
    independence_group_kind: IndependenceGroupKind
    capture_ref: VersionedObjectRef | None = None
    preparation_ref: VersionedObjectRef | None = None
    sample_ref: VersionedObjectRef | None = None
    donor_ref: VersionedObjectRef | None = None
    animal_ref: VersionedObjectRef | None = None
    graft_unit_ref: VersionedObjectRef | None = None

    @model_validator(mode="after")
    def unit_roles_are_coherent(self) -> Self:
        hierarchy = {
            "capture": self.capture_ref,
            "preparation": self.preparation_ref,
            "sample": self.sample_ref,
            "donor": self.donor_ref,
            "animal": self.animal_ref,
            "graft_unit": self.graft_unit_ref,
        }
        if hierarchy[self.analysis_unit_kind.value] != self.analysis_unit_ref:
            raise ValueError(
                f"{self.analysis_unit_kind.value} analysis unit must bind its typed hierarchy ref"
            )
        if hierarchy[self.independence_group_kind] != self.independence_group_ref:
            raise ValueError(
                "independence group must equal its typed hierarchy ref"
            )
        return self


class BiologicalUnitAssignment(FrozenModel):
    """Logical row contract for the checksummed assignment artifact."""

    observation_id: str = Field(min_length=1)
    capture_ref: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z][A-Za-z0-9._:-]*@[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )
    preparation_ref: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z][A-Za-z0-9._:-]*@[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )
    sample_ref: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z][A-Za-z0-9._:-]*@[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )
    donor_ref: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z][A-Za-z0-9._:-]*@[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )
    animal_ref: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z][A-Za-z0-9._:-]*@[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )
    graft_unit_ref: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z][A-Za-z0-9._:-]*@[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )
    analysis_unit_ref: str = Field(
        pattern=r"^[A-Za-z][A-Za-z0-9._:-]*@[A-Za-z0-9][A-Za-z0-9._:-]*$"
    )
    independence_group_ref: str = Field(
        pattern=r"^[A-Za-z][A-Za-z0-9._:-]*@[A-Za-z0-9][A-Za-z0-9._:-]*$"
    )


class BiologicalUnitAssignmentArtifact(FrozenModel):
    """Checksummed observation-to-unit mapping consumed as one JSON object."""

    object_version: Literal["0.1.0"]
    schema_ref: Literal["bridge://schemas/biological-unit-assignment/v0.1"]
    data_view_ref: str = Field(min_length=1)
    observation_ids_sha256: str = Field(pattern=SHA256_PATTERN)
    assignments: list[BiologicalUnitAssignment]

    @field_validator("assignments")
    @classmethod
    def observations_are_unique(
        cls, value: list[BiologicalUnitAssignment]
    ) -> list[BiologicalUnitAssignment]:
        _unique([item.observation_id for item in value], "observation IDs")
        return value


def observation_ids_sha256(observation_ids: list[str]) -> str:
    canonical = json.dumps(
        sorted(observation_ids),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


class BiologicalUnitManifest(FrozenModel):
    model_config = ConfigDict(
        json_schema_extra={
            "allOf": [
                {
                    "if": {
                        "properties": {"generator_tool_id": {"const": "P0-01"}},
                        "required": ["generator_tool_id"],
                    },
                    "then": {
                        "properties": {
                            "lineage_state": {"const": "declared"},
                            "review_gate_ref": {"type": "null"},
                            "review_gate_sha256": {"type": "null"},
                        }
                    },
                },
                {
                    "if": {
                        "properties": {
                            "generator_tool_id": {
                                "const": "BRIDGE-BIOLOGICAL-UNIT-REVIEW"
                            }
                        },
                        "required": ["generator_tool_id"],
                    },
                    "then": {
                        "required": ["review_gate_ref", "review_gate_sha256"],
                        "properties": {
                            "lineage_state": {"enum": ["reviewed", "frozen"]},
                            "review_gate_ref": {"not": {"type": "null"}},
                            "review_gate_sha256": {"not": {"type": "null"}},
                        },
                    },
                },
                {
                    "if": {
                        "properties": {"n_observations": {"const": 0}},
                        "required": ["n_observations"],
                    },
                    "then": {"properties": {"unit_bindings": {"maxItems": 0}}},
                    "else": {"properties": {"unit_bindings": {"minItems": 1}}},
                },
            ]
        }
    )

    object_version: Literal["0.1.0"]
    manifest_id: str = Field(
        pattern=r"^biological-unit-manifest:[A-Za-z0-9._:-]+$"
    )
    manifest_version: str = Field(pattern=VERSION_PATTERN)
    schema_ref: Literal["bridge://schemas/biological-unit-manifest/v0.1"]
    generator_tool_id: Literal["P0-01", "BRIDGE-BIOLOGICAL-UNIT-REVIEW"]
    generator_tool_version: str = Field(pattern=VERSION_PATTERN)
    data_view_ref: str = Field(min_length=1)
    selected_artifact_sha256: str = Field(pattern=SHA256_PATTERN)
    observation_ids_sha256: str = Field(pattern=SHA256_PATTERN)
    n_observations: StrictInt = Field(ge=0)
    assignment_schema_ref: Literal[
        "bridge://schemas/biological-unit-assignment/v0.1"
    ]
    assignment_artifact_sha256: str = Field(pattern=SHA256_PATTERN)
    assignment_row_count: StrictInt = Field(ge=0)
    unit_identity_namespace_ref: VersionedObjectRef
    analysis_unit_kind: BiologicalUnitKind
    independence_group_kind: IndependenceGroupKind
    independence_scope_ref: VersionedObjectRef
    lineage_state: BiologicalUnitLineageState
    review_gate_ref: VersionedObjectRef | None = None
    review_gate_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    unit_bindings: list[BiologicalUnitBinding] = Field(default_factory=list)

    @field_validator("unit_bindings")
    @classmethod
    def bindings_are_unique(
        cls, value: list[BiologicalUnitBinding]
    ) -> list[BiologicalUnitBinding]:
        _unique([item.analysis_unit_ref.ref for item in value], "analysis units")
        return value

    @model_validator(mode="after")
    def manifest_is_coherent(self) -> Self:
        if self.assignment_row_count != self.n_observations:
            raise ValueError("assignment row count must equal selected observations")
        if (self.n_observations == 0) != (not self.unit_bindings):
            raise ValueError(
                "unit bindings must be empty exactly when the selected view is empty"
            )
        if any(
            item.analysis_unit_kind != self.analysis_unit_kind
            or item.independence_group_kind != self.independence_group_kind
            for item in self.unit_bindings
        ):
            raise ValueError("unit bindings must use the manifest unit kinds")
        reviewed = self.lineage_state in {
            BiologicalUnitLineageState.REVIEWED,
            BiologicalUnitLineageState.FROZEN,
        }
        if reviewed != (
            self.review_gate_ref is not None and self.review_gate_sha256 is not None
        ):
            raise ValueError("reviewed lineage requires a checksummed review gate")
        if (
            self.generator_tool_id == "P0-01"
            and self.lineage_state is not BiologicalUnitLineageState.DECLARED
        ):
            raise ValueError("P0-01 can only generate declared lineage")
        if self.generator_tool_id == "BRIDGE-BIOLOGICAL-UNIT-REVIEW" and not reviewed:
            raise ValueError("review generator must produce reviewed or frozen lineage")
        return self

    @property
    def ref(self) -> VersionedObjectRef:
        return VersionedObjectRef(
            object_id=self.manifest_id,
            object_version=self.manifest_version,
        )

    @property
    def independence_group_refs(self) -> list[VersionedObjectRef]:
        by_ref = {
            item.independence_group_ref.ref: item.independence_group_ref
            for item in self.unit_bindings
        }
        return [by_ref[key] for key in sorted(by_ref)]

    @property
    def review_claim_is_present(self) -> bool:
        return self.lineage_state in {
            BiologicalUnitLineageState.REVIEWED,
            BiologicalUnitLineageState.FROZEN,
        }


def biological_unit_assignment_reasons(
    *,
    manifest: BiologicalUnitManifest,
    artifact: BiologicalUnitAssignmentArtifact,
    artifact_sha256: str,
) -> list[str]:
    """Validate every observation assignment against the manifest bindings."""

    reasons: set[str] = set()
    if manifest.assignment_schema_ref != artifact.schema_ref:
        reasons.add("biological_unit_assignment_schema_mismatch")
    if manifest.assignment_artifact_sha256 != artifact_sha256:
        reasons.add("biological_unit_assignment_checksum_mismatch")
    if manifest.data_view_ref != artifact.data_view_ref:
        reasons.add("biological_unit_assignment_data_view_mismatch")
    if len(artifact.assignments) != manifest.assignment_row_count:
        reasons.add("biological_unit_assignment_row_count_mismatch")

    calculated_observation_sha = observation_ids_sha256(
        [item.observation_id for item in artifact.assignments]
    )
    if (
        artifact.observation_ids_sha256 != calculated_observation_sha
        or manifest.observation_ids_sha256 != calculated_observation_sha
    ):
        reasons.add("biological_unit_assignment_observation_set_mismatch")

    bindings = {
        item.analysis_unit_ref.ref: item for item in manifest.unit_bindings
    }
    used_analysis_units: set[str] = set()
    used_independence_groups: set[str] = set()
    hierarchy_fields = (
        "capture_ref",
        "preparation_ref",
        "sample_ref",
        "donor_ref",
        "animal_ref",
        "graft_unit_ref",
    )
    for assignment in artifact.assignments:
        binding = bindings.get(assignment.analysis_unit_ref)
        if binding is None:
            reasons.add("biological_unit_assignment_unknown_analysis_unit")
            continue
        used_analysis_units.add(assignment.analysis_unit_ref)
        used_independence_groups.add(assignment.independence_group_ref)
        if assignment.independence_group_ref != binding.independence_group_ref.ref:
            reasons.add("biological_unit_assignment_group_mismatch")
        for field in hierarchy_fields:
            expected_ref = getattr(binding, field)
            expected = None if expected_ref is None else expected_ref.ref
            if getattr(assignment, field) != expected:
                reasons.add("biological_unit_assignment_hierarchy_mismatch")

    if used_analysis_units != set(bindings):
        reasons.add("biological_unit_assignment_unused_analysis_unit")
    if used_independence_groups != {
        item.ref for item in manifest.independence_group_refs
    }:
        reasons.add("biological_unit_assignment_unused_independence_group")
    return sorted(reasons)


class ProductCase(FrozenModel):
    model_config = ConfigDict(
        json_schema_extra={
            "oneOf": [
                {
                    "properties": {
                        "biological_unit_manifest_ref": {"type": "null"},
                        "biological_unit_manifest_sha256": {"type": "null"},
                        "independence_scope_ref": {"type": "null"},
                        "independence_group_refs": {"maxItems": 0},
                    }
                },
                {
                    "required": [
                        "biological_unit_manifest_ref",
                        "biological_unit_manifest_sha256",
                        "independence_scope_ref",
                    ],
                    "properties": {
                        "biological_unit_manifest_ref": {
                            "not": {"type": "null"}
                        },
                        "biological_unit_manifest_sha256": {
                            "not": {"type": "null"}
                        },
                        "independence_scope_ref": {"not": {"type": "null"}},
                    },
                },
            ]
        }
    )

    object_version: Literal["0.1.0"]
    product_case_id: str = Field(pattern=r"^product-case:[A-Za-z0-9._:-]+$")
    case_version: str = Field(pattern=VERSION_PATTERN)
    product_definition_ref: VersionedObjectRef
    source_unit_kind: Literal["sample", "preparation"]
    sample_or_preparation_ref: VersionedObjectRef
    independence_group_refs: list[VersionedObjectRef] = Field(default_factory=list)
    biological_unit_manifest_ref: VersionedObjectRef | None = None
    biological_unit_manifest_sha256: str | None = Field(
        default=None,
        pattern=SHA256_PATTERN,
    )
    independence_scope_ref: VersionedObjectRef | None = None
    measurement_spec_ref: VersionedObjectRef
    assay: Literal["scRNA-seq", "snRNA-seq"]
    provenance_refs: list[VersionedObjectRef] = Field(min_length=1)
    created_at: datetime

    _created_at_utc = field_validator("created_at")(_aware_utc)

    @field_validator("independence_group_refs", "provenance_refs")
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

    @model_validator(mode="after")
    def biological_unit_binding_is_coherent(self) -> Self:
        values = (
            self.biological_unit_manifest_ref,
            self.biological_unit_manifest_sha256,
            self.independence_scope_ref,
        )
        if any(value is not None for value in values) and any(
            value is None for value in values
        ):
            raise ValueError(
                "biological unit manifest, checksum, and independence scope must be supplied together"
            )
        if self.independence_group_refs and any(value is None for value in values):
            raise ValueError(
                "independence group references require the complete biological unit binding"
            )
        return self


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
    review_state: Literal["draft"]
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
    profile: CellStateEvidenceProfileV2,
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
    cell_state_profile: CellStateEvidenceProfileV2,
    qc_profile: QCReadinessProfileV2,
    biological_unit_manifest: BiologicalUnitManifest,
    biological_unit_assignment_artifact: BiologicalUnitAssignmentArtifact,
    input_sha256_by_role: dict[str, str],
) -> list[str]:
    """Validate the content-addressed P0-01 -> P0-02 -> ProductCase handoff."""

    reasons: list[str] = []
    reasons.extend(
        biological_unit_assignment_reasons(
            manifest=biological_unit_manifest,
            artifact=biological_unit_assignment_artifact,
            artifact_sha256=input_sha256_by_role.get(
                "biological_unit_assignment", ""
            ),
        )
    )
    source_ref_field = f"{product_case.source_unit_kind}_ref"
    manifest_source_refs = {
        source_ref.ref
        for binding in biological_unit_manifest.unit_bindings
        if (source_ref := getattr(binding, source_ref_field)) is not None
    }
    if product_case.sample_or_preparation_ref.ref not in manifest_source_refs:
        reasons.append("product_case_source_unit_binding_mismatch")

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

        manifest_ref = biological_unit_manifest.ref.ref
        if (
            qc_view.biological_unit_manifest_ref != manifest_ref
            or cell_state_view.biological_unit_manifest_ref != manifest_ref
            or product_case.biological_unit_manifest_ref
            != biological_unit_manifest.ref
        ):
            reasons.append("biological_unit_manifest_binding_mismatch")
        manifest_sha = input_sha256_by_role.get("biological_unit_manifest")
        if (
            manifest_sha is None
            or
            qc_view.biological_unit_manifest_sha256 != manifest_sha
            or cell_state_view.biological_unit_manifest_sha256 != manifest_sha
            or product_case.biological_unit_manifest_sha256 != manifest_sha
        ):
            reasons.append("biological_unit_manifest_checksum_mismatch")
        if (
            biological_unit_manifest.data_view_ref != qc_view.view_id
            or biological_unit_manifest.selected_artifact_sha256 != qc_view.sha256
            or biological_unit_manifest.observation_ids_sha256
            != qc_view.observation_ids_sha256
            or biological_unit_manifest.n_observations != qc_view.n_observations
        ):
            reasons.append("biological_unit_manifest_data_view_mismatch")
        if (
            product_case.independence_scope_ref
            != biological_unit_manifest.independence_scope_ref
            or {item.ref for item in product_case.independence_group_refs}
            != {
                item.ref
                for item in biological_unit_manifest.independence_group_refs
            }
        ):
            reasons.append("product_case_independence_binding_mismatch")

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
