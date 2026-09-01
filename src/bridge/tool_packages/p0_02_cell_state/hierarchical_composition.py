from __future__ import annotations

import math
from typing import Any, Literal, Self

import pandas as pd
from pydantic import Field, field_validator, model_validator

from bridge.tool_packages.p0_02_cell_state.grouping import GroupingOutcome
from bridge.toolkit.contracts import (
    AnnotationVocabulary,
    EvidenceState,
    FrozenModel,
)


HIERARCHICAL_CELL_STATE_COMPOSITION_SCHEMA_REF = (
    "bridge://schemas/hierarchical-cell-state-composition-data/v0.1"
)


class PredictionSetSummary(FrozenModel):
    state_ids: list[str]
    count: int = Field(gt=0)
    denominator: int = Field(gt=0)
    fraction: float = Field(ge=0, le=1)

    @field_validator("state_ids")
    @classmethod
    def state_ids_are_unique(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("prediction-set state IDs must be unique")
        return values

    @model_validator(mode="after")
    def fraction_matches_count(self) -> Self:
        if self.count > self.denominator:
            raise ValueError("prediction-set count cannot exceed its denominator")
        if not math.isclose(
            self.fraction,
            self.count / self.denominator,
            abs_tol=1e-12,
        ):
            raise ValueError("prediction-set fraction does not match its count")
        return self


class HierarchicalCompositionRecord(FrozenModel):
    record_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    record_kind: Literal["state", "resolution"]
    partition_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    state_id: str | None = Field(
        default=None,
        pattern=r"^L[12]:[A-Za-z0-9_]+$",
    )
    display_name: str = Field(min_length=1)
    level: Literal["L1", "L2", "status"]
    parent_state_id: str | None = Field(
        default=None,
        pattern=r"^L1:[A-Za-z0-9_]+$",
    )
    order: int = Field(ge=0)
    resolution_state: Literal[
        "resolved",
        "source_conflict",
        "subtype_unresolved",
        "unavailable",
        "not_assessed",
    ]
    evidence_state: EvidenceState
    scientific_status: Literal["candidate"] = "candidate"
    applicability: Literal["applicable", "not_assessed"]
    missingness: Literal["available", "unavailable"]
    count: int | None = Field(default=None, ge=0)
    whole_product_denominator: int | None = Field(default=None, gt=0)
    whole_product_fraction: float | None = Field(default=None, ge=0, le=1)
    parent_denominator: int | None = Field(default=None, gt=0)
    parent_fraction: float | None = Field(default=None, ge=0, le=1)
    denominator_scope: str | None = None
    supporting_source_ids: list[str] = Field(default_factory=list)
    prediction_sets: list[PredictionSetSummary] = Field(default_factory=list)
    evidence_ids: list[str] = Field(min_length=1)
    reason_codes: list[str] = Field(default_factory=list)

    @field_validator(
        "supporting_source_ids",
        "evidence_ids",
        "reason_codes",
    )
    @classmethod
    def lists_are_unique(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("record references and reason codes must be unique")
        if any(not value.strip() for value in values):
            raise ValueError("record references and reason codes must be non-empty")
        return values

    @model_validator(mode="after")
    def quantitative_semantics_are_coherent(self) -> Self:
        quantities = (
            self.count,
            self.whole_product_denominator,
            self.whole_product_fraction,
            self.parent_denominator,
            self.parent_fraction,
            self.denominator_scope,
        )
        if self.missingness == "unavailable":
            if any(value is not None for value in quantities):
                raise ValueError("unavailable records cannot encode quantitative zero")
            if not self.reason_codes:
                raise ValueError("unavailable records require reason codes")
        elif any(value is None for value in quantities):
            raise ValueError("available records require complete denominator semantics")
        else:
            assert self.count is not None
            assert self.whole_product_denominator is not None
            assert self.whole_product_fraction is not None
            assert self.parent_denominator is not None
            assert self.parent_fraction is not None
            if self.count > min(
                self.whole_product_denominator,
                self.parent_denominator,
            ):
                raise ValueError("record count cannot exceed either denominator")
            if not math.isclose(
                self.whole_product_fraction,
                self.count / self.whole_product_denominator,
                abs_tol=1e-12,
            ):
                raise ValueError("whole-product fraction does not match its count")
            if not math.isclose(
                self.parent_fraction,
                self.count / self.parent_denominator,
                abs_tol=1e-12,
            ):
                raise ValueError("parent fraction does not match its count")
        if self.record_kind == "state" and self.state_id is None:
            raise ValueError("state records require state_id")
        if self.record_kind == "resolution" and self.state_id is not None:
            raise ValueError("resolution records cannot claim a state identity")
        if self.level == "L2" and self.parent_state_id is None:
            raise ValueError("L2 records require a parent state")
        if self.level != "L2" and self.parent_state_id is not None:
            raise ValueError("only L2 rows can declare a parent state")
        return self


class ProductGroupingProvenance(FrozenModel):
    state: Literal["user_provided", "generated", "not_generated"]
    source: Literal["user_label", "exploratory_leiden", "whole_product"]
    grouping_key: str | None = None
    grouping_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    n_groups: int | None = Field(default=None, gt=0)
    reason_codes: list[str] = Field(default_factory=list)
    method: dict[str, Any]

    @model_validator(mode="after")
    def grouping_state_is_coherent(self) -> Self:
        available = self.state != "not_generated"
        if available != (
            self.grouping_hash is not None and self.n_groups is not None
        ):
            raise ValueError("available grouping requires group count and hash")
        if available and self.reason_codes:
            raise ValueError("available grouping cannot carry failure reasons")
        if not available and not self.reason_codes:
            raise ValueError("unavailable grouping requires a reason")
        return self


class ProductGroup(FrozenModel):
    group_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    display_name: str = Field(min_length=1)
    source: Literal["user_label", "exploratory_leiden"]
    count: int = Field(gt=0)
    whole_product_denominator: int = Field(gt=0)
    whole_product_fraction: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def group_fraction_is_coherent(self) -> Self:
        if self.count > self.whole_product_denominator:
            raise ValueError("group count cannot exceed product denominator")
        if not math.isclose(
            self.whole_product_fraction,
            self.count / self.whole_product_denominator,
            abs_tol=1e-12,
        ):
            raise ValueError("group fraction does not match its count")
        return self


class GroupStateCorrespondenceRecord(FrozenModel):
    record_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    group_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    state_id: str | None = Field(
        default=None,
        pattern=r"^L[12]:[A-Za-z0-9_]+$",
    )
    level: Literal["L1", "L2"]
    parent_state_id: str | None = Field(
        default=None,
        pattern=r"^L1:[A-Za-z0-9_]+$",
    )
    resolution_state: Literal[
        "resolved",
        "source_conflict",
        "subtype_unresolved",
        "unavailable",
    ]
    value_semantics: Literal["reference_correspondence_fraction"] = (
        "reference_correspondence_fraction"
    )
    count: int = Field(ge=0)
    group_denominator: int = Field(gt=0)
    group_fraction: float = Field(ge=0, le=1)
    whole_product_denominator: int = Field(gt=0)
    whole_product_fraction: float = Field(ge=0, le=1)
    parent_denominator: int = Field(gt=0)
    parent_fraction: float = Field(ge=0, le=1)
    evidence_state: EvidenceState
    scientific_status: Literal["candidate"] = "candidate"
    applicability: Literal["applicable"] = "applicable"
    missingness: Literal["available"] = "available"
    prediction_sets: list[PredictionSetSummary] = Field(default_factory=list)
    evidence_ids: list[str] = Field(min_length=1)
    reason_codes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def fractions_are_coherent(self) -> Self:
        if self.count > min(
            self.group_denominator,
            self.whole_product_denominator,
            self.parent_denominator,
        ):
            raise ValueError("group-state count exceeds a denominator")
        if not math.isclose(
            self.group_fraction,
            self.count / self.group_denominator,
            abs_tol=1e-12,
        ):
            raise ValueError("group fraction does not match its count")
        if not math.isclose(
            self.whole_product_fraction,
            self.count / self.whole_product_denominator,
            abs_tol=1e-12,
        ):
            raise ValueError("whole-product fraction does not match its count")
        if not math.isclose(
            self.parent_fraction,
            self.count / self.parent_denominator,
            abs_tol=1e-12,
        ):
            raise ValueError("parent fraction does not match its count")
        if self.level == "L2" and self.parent_state_id is None:
            raise ValueError("L2 group records require a parent state")
        if self.level == "L1" and self.parent_state_id is not None:
            raise ValueError("L1 group records cannot declare a parent state")
        return self


class HierarchicalCellStateCompositionDataV1(FrozenModel):
    object_version: Literal["0.1.0"] = "0.1.0"
    schema_ref: Literal[
        "bridge://schemas/hierarchical-cell-state-composition-data/v0.1"
    ] = HIERARCHICAL_CELL_STATE_COMPOSITION_SCHEMA_REF
    profile_id: str = Field(
        pattern=r"^hierarchical-cell-state-composition:[A-Za-z0-9._-]+$"
    )
    producer_run_ref: str = Field(pattern=r"^run:[A-Za-z0-9._:-]+$")
    scientific_status: Literal["candidate"] = "candidate"
    observation_unit: Literal["cells", "nuclei", "observations"]
    whole_product_denominator: int = Field(gt=0)
    denominator_scope: str = Field(min_length=1)
    input_view_ref: str = Field(min_length=1)
    input_view_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    annotation_vocabulary_ref: str = Field(min_length=1)
    annotation_vocabulary_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_conflict_assessed: bool
    grouping: ProductGroupingProvenance
    groups: list[ProductGroup] = Field(default_factory=list)
    composition_records: list[HierarchicalCompositionRecord] = Field(min_length=2)
    group_records: list[GroupStateCorrespondenceRecord] = Field(default_factory=list)
    evidence_ids: list[str] = Field(min_length=1)
    limitations: list[str] = Field(min_length=1)
    alt_text: str = Field(min_length=40, max_length=240)
    long_description: str = Field(min_length=80)

    @model_validator(mode="after")
    def partitions_and_groups_are_conserved(self) -> Self:
        record_ids = [record.record_id for record in self.composition_records]
        if len(record_ids) != len(set(record_ids)):
            raise ValueError("composition record IDs must be unique")
        quantitative = [
            record
            for record in self.composition_records
            if record.count is not None
        ]
        partitions: dict[str, list[HierarchicalCompositionRecord]] = {}
        for record in quantitative:
            partitions.setdefault(record.partition_id, []).append(record)
        for partition_id, records in partitions.items():
            denominator = records[0].parent_denominator
            if any(record.parent_denominator != denominator for record in records):
                raise ValueError("partition parent denominators must agree")
            if sum(record.count or 0 for record in records) != denominator:
                raise ValueError(f"composition partition is not conserved: {partition_id}")
        root = partitions.get("root")
        if root is None or sum(record.count or 0 for record in root) != self.whole_product_denominator:
            raise ValueError("L1 root partition must conserve all observations")

        group_ids = [group.group_id for group in self.groups]
        if len(group_ids) != len(set(group_ids)):
            raise ValueError("product group IDs must be unique")
        group_record_ids = [record.record_id for record in self.group_records]
        if len(group_record_ids) != len(set(group_record_ids)):
            raise ValueError("group record IDs must be unique")
        if self.grouping.state == "not_generated":
            if self.groups or self.group_records:
                raise ValueError("unavailable grouping cannot carry group results")
        else:
            if sum(group.count for group in self.groups) != self.whole_product_denominator:
                raise ValueError("product groups must conserve all observations")
            if {record.group_id for record in self.group_records} != set(group_ids):
                raise ValueError("every declared group requires group records")
            groups_by_id = {group.group_id: group for group in self.groups}
            broad_state_ids = {
                record.state_id
                for record in self.composition_records
                if record.record_kind == "state" and record.level == "L1"
            }
            refined_by_parent: dict[str, set[str]] = {}
            for record in self.composition_records:
                if (
                    record.record_kind == "state"
                    and record.level == "L2"
                    and record.parent_state_id is not None
                ):
                    refined_by_parent.setdefault(record.parent_state_id, set()).add(
                        record.state_id
                    )
            for record in self.group_records:
                if record.level != "L2":
                    continue
                expected_states = refined_by_parent.get(record.parent_state_id)
                if expected_states is None:
                    raise ValueError("group record references an unknown refined parent")
                if record.state_id is not None and record.state_id not in expected_states:
                    raise ValueError("group record references an unknown refined state")
            records_by_group = {
                group_id: [
                    record
                    for record in self.group_records
                    if record.group_id == group_id
                ]
                for group_id in group_ids
            }
            expected_root_statuses = {"unavailable"}
            if self.source_conflict_assessed:
                expected_root_statuses.add("source_conflict")
            for group_id, records in records_by_group.items():
                group = groups_by_id[group_id]
                if any(record.group_denominator != group.count for record in records):
                    raise ValueError("group-record denominators must match group size")
                root = [record for record in records if record.level == "L1"]
                root_state_ids = {
                    record.state_id for record in root if record.state_id is not None
                }
                root_statuses = {
                    record.resolution_state
                    for record in root
                    if record.state_id is None
                }
                if root_state_ids != broad_state_ids:
                    raise ValueError("group broad-state rows are incomplete")
                if root_statuses != expected_root_statuses:
                    raise ValueError("group broad-state status rows are incomplete")
                if len(root) != len(broad_state_ids) + len(expected_root_statuses):
                    raise ValueError("group broad-state rows must be unique")
                if sum(record.count for record in root) != group.count:
                    raise ValueError("each group L1 partition must conserve observations")
                broad_counts = {
                    record.state_id: record.count
                    for record in root
                    if record.state_id is not None
                }
                for parent_state_id, child_state_ids in refined_by_parent.items():
                    parent_count = broad_counts.get(parent_state_id, 0)
                    refined = [
                        record
                        for record in records
                        if record.level == "L2"
                        and record.parent_state_id == parent_state_id
                    ]
                    if parent_count == 0:
                        if refined:
                            raise ValueError("empty parent cannot carry refined rows")
                        continue
                    refined_state_ids = {
                        record.state_id
                        for record in refined
                        if record.state_id is not None
                    }
                    refined_statuses = {
                        record.resolution_state
                        for record in refined
                        if record.state_id is None
                    }
                    if refined_state_ids != child_state_ids:
                        raise ValueError("group refined-state rows are incomplete")
                    if refined_statuses != {"subtype_unresolved", "unavailable"}:
                        raise ValueError("group refined-state status rows are incomplete")
                    if len(refined) != len(child_state_ids) + 2:
                        raise ValueError("group refined-state rows must be unique")
                    if any(
                        record.parent_denominator != parent_count
                        for record in refined
                    ):
                        raise ValueError("group refined denominators must match parent")
                    if sum(record.count for record in refined) != parent_count:
                        raise ValueError("each group refined partition must conserve parent")
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("profile evidence IDs must be unique")
        return self


def build_hierarchical_composition(
    *,
    evidence: pd.DataFrame,
    vocabulary: AnnotationVocabulary,
    grouping: GroupingOutcome,
    run_id: str,
    input_view_ref: str,
    input_view_sha256: str,
    annotation_vocabulary_sha256: str,
    observation_unit: str,
    evidence_ids: list[str],
    source_conflict_assessed: bool,
) -> HierarchicalCellStateCompositionDataV1:
    denominator = len(evidence)
    labels_by_id = {label.state_id: label for label in vocabulary.labels}
    l1_labels = [label for label in vocabulary.labels if label.level == "L1"]
    if not l1_labels:
        raise ValueError("annotation vocabulary requires at least one L1 state")
    l2_labels = [label for label in vocabulary.labels if label.level == "L2"]
    children: dict[str, list[str]] = {}
    for label in l2_labels:
        for parent in label.parent_state_ids:
            children.setdefault(parent, []).append(label.state_id)

    l1_sets = _sets(evidence["prediction_set"])
    l1_assignment = pd.Series(
        [values[0] if len(values) == 1 else None for values in l1_sets],
        index=evidence.index,
        dtype="object",
    )
    composition: list[HierarchicalCompositionRecord] = []
    order = 0
    for label in l1_labels:
        count = int(l1_assignment.eq(label.state_id).sum())
        composition.append(
            _state_record(
                record_id=f"state:{label.state_id}",
                partition_id="root",
                state_id=label.state_id,
                display_name=label.display_name,
                level="L1",
                parent_state_id=None,
                order=order,
                count=count,
                whole_denominator=denominator,
                parent_denominator=denominator,
                source_ids=_supporting_sources(evidence, label.state_id),
                prediction_sets=_prediction_summaries(
                    [values for values in l1_sets if label.state_id in values],
                    denominator,
                ),
                evidence_ids=evidence_ids,
            )
        )
        order += 1
        parent_mask = l1_assignment.eq(label.state_id)
        if label.state_id in children and parent_mask.any():
            child_records, order = _l2_partition_records(
                evidence=evidence,
                parent_mask=parent_mask,
                parent_state_id=label.state_id,
                child_state_ids=children[label.state_id],
                labels_by_id=labels_by_id,
                whole_denominator=denominator,
                order=order,
                evidence_ids=evidence_ids,
            )
            composition.extend(child_records)

    conflict_count = sum(len(values) > 1 for values in l1_sets)
    unavailable_count = sum(
        len(values) == 0 if source_conflict_assessed else len(values) != 1
        for values in l1_sets
    )
    if source_conflict_assessed:
        composition.append(
            _resolution_record(
                record_id="resolution:l1-source-conflict",
                partition_id="root",
                display_name="Multiple broad states remain possible",
                order=order,
                resolution_state="source_conflict",
                evidence_state=EvidenceState.ALERT,
                count=conflict_count,
                whole_denominator=denominator,
                parent_denominator=denominator,
                prediction_sets=_prediction_summaries(
                    [values for values in l1_sets if len(values) > 1],
                    denominator,
                ),
                evidence_ids=evidence_ids,
                reason_codes=["cross_source_state_disagreement"],
            )
        )
    else:
        composition.append(
            HierarchicalCompositionRecord(
                record_id="resolution:l1-source-conflict-not-assessed",
                record_kind="resolution",
                partition_id="nonquantitative",
                display_name="Multiple-source agreement not assessed",
                level="status",
                order=order,
                resolution_state="not_assessed",
                evidence_state=EvidenceState.UNAVAILABLE,
                scientific_status="candidate",
                applicability="not_assessed",
                missingness="unavailable",
                evidence_ids=evidence_ids,
                reason_codes=["source_conflict_requires_multiple_primary_sources"],
            )
        )
    composition.extend(
        [
            _resolution_record(
                record_id="resolution:l1-unavailable",
                partition_id="root",
                display_name="Reference correspondence unavailable",
                order=order + 1,
                resolution_state="unavailable",
                evidence_state=EvidenceState.UNAVAILABLE,
                count=unavailable_count,
                whole_denominator=denominator,
                parent_denominator=denominator,
                prediction_sets=[],
                evidence_ids=evidence_ids,
                reason_codes=["no_applicable_reference_label"],
            ),
            HierarchicalCompositionRecord(
                record_id="resolution:open-set-not-assessed",
                record_kind="resolution",
                partition_id="nonquantitative",
                display_name="Unknown / OOD status not assessed",
                level="status",
                order=order + 2,
                resolution_state="not_assessed",
                evidence_state=EvidenceState.UNAVAILABLE,
                scientific_status="candidate",
                applicability="not_assessed",
                missingness="unavailable",
                evidence_ids=evidence_ids,
                reason_codes=["open_set_calibration_not_available"],
            ),
        ]
    )

    groups, group_records = _group_records(
        evidence=evidence,
        grouping=grouping,
        l1_labels=l1_labels,
        children=children,
        whole_denominator=denominator,
        evidence_ids=evidence_ids,
        source_conflict_assessed=source_conflict_assessed,
    )
    unit = (
        "nuclei"
        if observation_unit == "nuclei"
        else "cells"
        if observation_unit == "cells"
        else "observations"
    )
    return HierarchicalCellStateCompositionDataV1(
        profile_id=f"hierarchical-cell-state-composition:{run_id}",
        producer_run_ref=f"run:{run_id}",
        observation_unit=unit,
        whole_product_denominator=denominator,
        denominator_scope="declared post-QC whole-product input view",
        input_view_ref=input_view_ref,
        input_view_sha256=input_view_sha256,
        annotation_vocabulary_ref=vocabulary.vocabulary_id,
        annotation_vocabulary_sha256=annotation_vocabulary_sha256,
        source_conflict_assessed=source_conflict_assessed,
        grouping=ProductGroupingProvenance(
            state=grouping.state,
            source=grouping.source,
            grouping_key=grouping.grouping_key,
            grouping_hash=grouping.grouping_hash,
            n_groups=int(grouping.labels.nunique()) if grouping.labels is not None else None,
            reason_codes=list(grouping.reason_codes),
            method=grouping.method,
        ),
        groups=groups,
        composition_records=composition,
        group_records=group_records,
        evidence_ids=evidence_ids,
        limitations=[
            "Reference correspondence is candidate evidence, not a calibrated identity probability.",
            "Identity detail beyond the reviewed vocabulary is not assessed.",
            "Unknown and out-of-distribution status is not assessed until calibration is available.",
            "Exploratory groups, when present, do not determine cell identity.",
        ],
        alt_text=(
            "Whole-product reference correspondence showing broad states, "
            "eligible refinements, and unresolved evidence."
        ),
        long_description=(
            "All quantitative rows use the same whole-product denominator. "
            "Refined-state rows additionally report their share within the "
            "resolved broad parent. Source conflict, unavailable "
            "correspondence and the unassessed open-set boundary are kept distinct."
        ),
    )


def _l2_partition_records(
    *,
    evidence: pd.DataFrame,
    parent_mask: pd.Series,
    parent_state_id: str,
    child_state_ids: list[str],
    labels_by_id: dict[str, Any],
    whole_denominator: int,
    order: int,
    evidence_ids: list[str],
) -> tuple[list[HierarchicalCompositionRecord], int]:
    parent_count = int(parent_mask.sum())
    l2_sets = (
        _sets(evidence["l2_prediction_set"])
        if "l2_prediction_set" in evidence
        else [[] for _ in range(len(evidence))]
    )
    records: list[HierarchicalCompositionRecord] = []
    for state_id in child_state_ids:
        count = sum(
            bool(in_parent and len(values) == 1 and values[0] == state_id)
            for in_parent, values in zip(parent_mask, l2_sets, strict=True)
        )
        records.append(
            _state_record(
                record_id=f"state:{state_id}",
                partition_id=parent_state_id,
                state_id=state_id,
                display_name=labels_by_id[state_id].display_name,
                level="L2",
                parent_state_id=parent_state_id,
                order=order,
                count=count,
                whole_denominator=whole_denominator,
                parent_denominator=parent_count,
                source_ids=_supporting_sources(evidence.loc[parent_mask], state_id),
                prediction_sets=_prediction_summaries(
                    [
                        values
                        for in_parent, values in zip(parent_mask, l2_sets, strict=True)
                        if in_parent and state_id in values
                    ],
                    parent_count,
                ),
                evidence_ids=evidence_ids,
            )
        )
        order += 1
    unresolved = sum(
        bool(in_parent and len(values) > 1)
        for in_parent, values in zip(parent_mask, l2_sets, strict=True)
    )
    unavailable = sum(
        bool(in_parent and len(values) == 0)
        for in_parent, values in zip(parent_mask, l2_sets, strict=True)
    )
    records.extend(
        [
            _resolution_record(
                record_id=f"resolution:{parent_state_id}:subtype-unresolved",
                partition_id=parent_state_id,
                display_name="Refined state remains unresolved",
                order=order,
                resolution_state="subtype_unresolved",
                evidence_state=EvidenceState.ALERT,
                count=unresolved,
                whole_denominator=whole_denominator,
                parent_denominator=parent_count,
                prediction_sets=_prediction_summaries(
                    [
                        values
                        for in_parent, values in zip(parent_mask, l2_sets, strict=True)
                        if in_parent and len(values) > 1
                    ],
                    parent_count,
                ),
                evidence_ids=evidence_ids,
                reason_codes=["multiple_l2_states_remain_possible"],
                level="L2",
                parent_state_id=parent_state_id,
            ),
            _resolution_record(
                record_id=f"resolution:{parent_state_id}:l2-unavailable",
                partition_id=parent_state_id,
                display_name="Refined reference correspondence unavailable",
                order=order + 1,
                resolution_state="unavailable",
                evidence_state=EvidenceState.UNAVAILABLE,
                count=unavailable,
                whole_denominator=whole_denominator,
                parent_denominator=parent_count,
                prediction_sets=[],
                evidence_ids=evidence_ids,
                reason_codes=["l2_reference_correspondence_unavailable"],
                level="L2",
                parent_state_id=parent_state_id,
            ),
        ]
    )
    return records, order + 2


def _state_record(
    *,
    record_id: str,
    partition_id: str,
    state_id: str,
    display_name: str,
    level: Literal["L1", "L2"],
    parent_state_id: str | None,
    order: int,
    count: int,
    whole_denominator: int,
    parent_denominator: int,
    source_ids: list[str],
    prediction_sets: list[PredictionSetSummary],
    evidence_ids: list[str],
) -> HierarchicalCompositionRecord:
    return HierarchicalCompositionRecord(
        record_id=record_id,
        record_kind="state",
        partition_id=partition_id,
        state_id=state_id,
        display_name=display_name,
        level=level,
        parent_state_id=parent_state_id,
        order=order,
        resolution_state="resolved",
        evidence_state=EvidenceState.INFERRED,
        scientific_status="candidate",
        applicability="applicable",
        missingness="available",
        count=count,
        whole_product_denominator=whole_denominator,
        whole_product_fraction=count / whole_denominator,
        parent_denominator=parent_denominator,
        parent_fraction=count / parent_denominator,
        denominator_scope=(
            "resolved L1 parent observations"
            if level == "L2"
            else "declared post-QC whole-product input view"
        ),
        supporting_source_ids=source_ids,
        prediction_sets=prediction_sets,
        evidence_ids=evidence_ids,
    )


def _resolution_record(
    *,
    record_id: str,
    partition_id: str,
    display_name: str,
    order: int,
    resolution_state: Literal[
        "source_conflict",
        "subtype_unresolved",
        "unavailable",
    ],
    evidence_state: EvidenceState,
    count: int,
    whole_denominator: int,
    parent_denominator: int,
    prediction_sets: list[PredictionSetSummary],
    evidence_ids: list[str],
    reason_codes: list[str],
    level: Literal["L1", "L2", "status"] = "status",
    parent_state_id: str | None = None,
) -> HierarchicalCompositionRecord:
    return HierarchicalCompositionRecord(
        record_id=record_id,
        record_kind="resolution",
        partition_id=partition_id,
        display_name=display_name,
        level=level,
        parent_state_id=parent_state_id,
        order=order,
        resolution_state=resolution_state,
        evidence_state=evidence_state,
        scientific_status="candidate",
        applicability="applicable",
        missingness="available",
        count=count,
        whole_product_denominator=whole_denominator,
        whole_product_fraction=count / whole_denominator,
        parent_denominator=parent_denominator,
        parent_fraction=count / parent_denominator,
        denominator_scope=(
            "resolved L1 parent observations"
            if level == "L2"
            else "declared post-QC whole-product input view"
        ),
        prediction_sets=prediction_sets,
        evidence_ids=evidence_ids,
        reason_codes=reason_codes,
    )


def _group_records(
    *,
    evidence: pd.DataFrame,
    grouping: GroupingOutcome,
    l1_labels: list[Any],
    children: dict[str, list[str]],
    whole_denominator: int,
    evidence_ids: list[str],
    source_conflict_assessed: bool,
) -> tuple[list[ProductGroup], list[GroupStateCorrespondenceRecord]]:
    if grouping.labels is None:
        return [], []
    aligned = grouping.labels.reindex(evidence["observation_id"].astype(str))
    if aligned.isna().any():
        return [], []
    aligned.index = evidence.index
    groups: list[ProductGroup] = []
    records: list[GroupStateCorrespondenceRecord] = []
    for index, display_name in enumerate(pd.unique(aligned), start=1):
        group_id = f"group:{index:02d}"
        mask = aligned.eq(display_name)
        count = int(mask.sum())
        groups.append(
            ProductGroup(
                group_id=group_id,
                display_name=str(display_name),
                source=grouping.source,
                count=count,
                whole_product_denominator=whole_denominator,
                whole_product_fraction=count / whole_denominator,
            )
        )
        subset = evidence.loc[mask]
        l1_sets = _sets(subset["prediction_set"])
        l1_assignment = [values[0] if len(values) == 1 else None for values in l1_sets]
        l2_sets = (
            _sets(subset["l2_prediction_set"])
            if "l2_prediction_set" in subset
            else [[] for _ in range(len(subset))]
        )
        for label in l1_labels:
            state_count = sum(value == label.state_id for value in l1_assignment)
            records.append(
                _group_record(
                    group_id=group_id,
                    state_id=label.state_id,
                    level="L1",
                    parent_state_id=None,
                    resolution_state="resolved",
                    count=state_count,
                    group_denominator=count,
                    parent_denominator=count,
                    whole_denominator=whole_denominator,
                    evidence_state=EvidenceState.INFERRED,
                    prediction_sets=_prediction_summaries(
                        [values for values in l1_sets if label.state_id in values],
                        count,
                    ),
                    evidence_ids=evidence_ids,
                )
            )
            if state_count and label.state_id in children:
                records.extend(
                    _group_refined_records(
                        group_id=group_id,
                        group_count=count,
                        whole_denominator=whole_denominator,
                        parent_state_id=label.state_id,
                        child_state_ids=children[label.state_id],
                        l1_assignment=l1_assignment,
                        l2_sets=l2_sets,
                        evidence_ids=evidence_ids,
                    )
                )
        if source_conflict_assessed:
            records.append(
                _group_record(
                    group_id=group_id,
                    state_id=None,
                    level="L1",
                    parent_state_id=None,
                    resolution_state="source_conflict",
                    count=sum(len(values) > 1 for values in l1_sets),
                    group_denominator=count,
                    parent_denominator=count,
                    whole_denominator=whole_denominator,
                    evidence_state=EvidenceState.ALERT,
                    prediction_sets=_prediction_summaries(
                        [values for values in l1_sets if len(values) > 1],
                        count,
                    ),
                    evidence_ids=evidence_ids,
                    reason_codes=["cross_source_state_disagreement"],
                )
            )
        records.append(
            _group_record(
                group_id=group_id,
                state_id=None,
                level="L1",
                parent_state_id=None,
                resolution_state="unavailable",
                count=sum(
                    len(values) == 0 if source_conflict_assessed else len(values) != 1
                    for values in l1_sets
                ),
                group_denominator=count,
                parent_denominator=count,
                whole_denominator=whole_denominator,
                evidence_state=EvidenceState.UNAVAILABLE,
                prediction_sets=[],
                evidence_ids=evidence_ids,
                reason_codes=["no_applicable_reference_label"],
            )
        )
    return groups, records


def _group_refined_records(
    *,
    group_id: str,
    group_count: int,
    whole_denominator: int,
    parent_state_id: str,
    child_state_ids: list[str],
    l1_assignment: list[str | None],
    l2_sets: list[list[str]],
    evidence_ids: list[str],
) -> list[GroupStateCorrespondenceRecord]:
    parent_mask = [value == parent_state_id for value in l1_assignment]
    parent_count = sum(parent_mask)
    records: list[GroupStateCorrespondenceRecord] = []
    for state_id in child_state_ids:
        state_count = sum(
            in_parent and len(values) == 1 and values[0] == state_id
            for in_parent, values in zip(parent_mask, l2_sets, strict=True)
        )
        records.append(
            _group_record(
                group_id=group_id,
                state_id=state_id,
                level="L2",
                parent_state_id=parent_state_id,
                resolution_state="resolved",
                count=state_count,
                group_denominator=group_count,
                parent_denominator=parent_count,
                whole_denominator=whole_denominator,
                evidence_state=EvidenceState.INFERRED,
                prediction_sets=_prediction_summaries(
                    [
                        values
                        for in_parent, values in zip(parent_mask, l2_sets, strict=True)
                        if in_parent and state_id in values
                    ],
                    parent_count,
                ),
                evidence_ids=evidence_ids,
            )
        )
    for resolution_state, predicate, evidence_state, reason_code in (
        (
            "subtype_unresolved",
            lambda values: len(values) > 1,
            EvidenceState.ALERT,
            "multiple_l2_states_remain_possible",
        ),
        (
            "unavailable",
            lambda values: len(values) == 0,
            EvidenceState.UNAVAILABLE,
            "l2_reference_correspondence_unavailable",
        ),
    ):
        selected = [
            values
            for in_parent, values in zip(parent_mask, l2_sets, strict=True)
            if in_parent and predicate(values)
        ]
        records.append(
            _group_record(
                group_id=group_id,
                state_id=None,
                level="L2",
                parent_state_id=parent_state_id,
                resolution_state=resolution_state,
                count=len(selected),
                group_denominator=group_count,
                parent_denominator=parent_count,
                whole_denominator=whole_denominator,
                evidence_state=evidence_state,
                prediction_sets=(
                    _prediction_summaries(selected, parent_count)
                    if resolution_state == "subtype_unresolved"
                    else []
                ),
                evidence_ids=evidence_ids,
                reason_codes=[reason_code],
            )
        )
    return records


def _group_record(
    *,
    group_id: str,
    state_id: str | None,
    level: Literal["L1", "L2"],
    parent_state_id: str | None,
    resolution_state: Literal[
        "resolved",
        "source_conflict",
        "subtype_unresolved",
        "unavailable",
    ],
    count: int,
    group_denominator: int,
    parent_denominator: int,
    whole_denominator: int,
    evidence_state: EvidenceState,
    prediction_sets: list[PredictionSetSummary],
    evidence_ids: list[str],
    reason_codes: list[str] | None = None,
) -> GroupStateCorrespondenceRecord:
    identity = state_id or resolution_state
    return GroupStateCorrespondenceRecord(
        record_id=f"{group_id}:{parent_state_id or 'root'}:{level}:{identity}",
        group_id=group_id,
        state_id=state_id,
        level=level,
        parent_state_id=parent_state_id,
        resolution_state=resolution_state,
        count=count,
        group_denominator=group_denominator,
        group_fraction=count / group_denominator,
        whole_product_denominator=whole_denominator,
        whole_product_fraction=count / whole_denominator,
        parent_denominator=parent_denominator,
        parent_fraction=count / parent_denominator,
        evidence_state=evidence_state,
        prediction_sets=prediction_sets,
        evidence_ids=evidence_ids,
        reason_codes=reason_codes or [],
    )


def _sets(values: pd.Series) -> list[list[str]]:
    result: list[list[str]] = []
    for value in values:
        if isinstance(value, (list, tuple, set)):
            result.append(sorted({str(item) for item in value if str(item)}))
        else:
            result.append([])
    return result


def _prediction_summaries(
    values: list[list[str]],
    denominator: int,
) -> list[PredictionSetSummary]:
    counts: dict[tuple[str, ...], int] = {}
    for value in values:
        key = tuple(value)
        if key:
            counts[key] = counts.get(key, 0) + 1
    return [
        PredictionSetSummary(
            state_ids=list(key),
            count=count,
            denominator=denominator,
            fraction=count / denominator,
        )
        for key, count in sorted(counts.items())
    ]


def _supporting_sources(evidence: pd.DataFrame, state_id: str) -> list[str]:
    suffix = "__top_label"
    return sorted(
        column[: -len(suffix)]
        for column in evidence.columns
        if column.endswith(suffix)
        and evidence[column].astype("string").eq(state_id).any()
    )


PUBLIC_SCHEMA_MODELS = {
    HIERARCHICAL_CELL_STATE_COMPOSITION_SCHEMA_REF: (
        HierarchicalCellStateCompositionDataV1
    ),
}
