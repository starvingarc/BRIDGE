"""Deterministic display joins. These DTOs do not grant scientific qualification."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DisplayModel(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, allow_inf_nan=False)


class SourceBinding(DisplayModel):
    input_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    data_view_ref: str
    ordered_observation_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    producer_ref: str
    receipt_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')


class ProductRow(DisplayModel):
    observation_id: str
    x: float
    y: float
    cluster: str


class PlotRecord(DisplayModel):
    record_id: str
    x: float
    y: float
    group: str


class Assignment(DisplayModel):
    observation_id: str
    assigned_state: str | None
    assignment_state: str
    qualified_assignment: bool


class ReferenceSubtypeBinding(SourceBinding):
    source_id: str
    evidence_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')


class ReferenceSubtypeRow(DisplayModel):
    observation_id: str
    source_state_id: str | None = Field(default=None, pattern=r'^L2:[A-Za-z0-9_]+$')
    parent_state_id: str | None = Field(default=None, pattern=r'^L1:[A-Za-z0-9_]+$')


class ReferenceSubtypeInput(DisplayModel):
    rows: list[ReferenceSubtypeRow]
    source_binding: ReferenceSubtypeBinding


class CrosswalkEntry(DisplayModel):
    product_state_id: str
    spatial_type_id: str
    relation: Literal['same_type', 'broader_type']
    review_state: Literal['reviewed', 'pending', 'rejected']
    basis: str = Field(min_length=1)


class TypeCrosswalk(DisplayModel):
    version: str
    product_vocabulary_version: str
    spatial_vocabulary_version: str
    entries: list[CrosswalkEntry]


class ProductLinkInput(DisplayModel):
    rows: list[ProductRow]
    plot_records: list[PlotRecord]
    assignments: list[Assignment]
    coordinate_binding: SourceBinding
    assignment_binding: SourceBinding
    product_vocabulary_version: str
    spatial_vocabulary_version: str
    reference_subtypes: ReferenceSubtypeInput | None = None


def ordered_observation_sha256(ids: list[str]) -> str:
    """Length-delimited JSON preserves order and avoids delimiter collisions."""
    return hashlib.sha256(json.dumps(ids, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def build_product_link(source: ProductLinkInput, crosswalk: TypeCrosswalk) -> dict:
    left, right = source.coordinate_binding, source.assignment_binding
    for key in ('input_sha256', 'data_view_ref', 'ordered_observation_sha256'):
        if getattr(left, key) != getattr(right, key):
            raise ValueError('product_binding_mismatch')
    ids = [row.observation_id for row in source.rows]
    assigned_ids = [row.observation_id for row in source.assignments]
    if (not ids or len(set(ids)) != len(ids) or ids != assigned_ids
            or ordered_observation_sha256(ids) != left.ordered_observation_sha256):
        raise ValueError('product_observation_order_mismatch')
    if any(getattr(source, key) != getattr(crosswalk, key) for key in
           ('product_vocabulary_version', 'spatial_vocabulary_version')):
        raise ValueError('crosswalk_vocabulary_mismatch')
    reviewed: dict[str, list[dict]] = {}
    for entry in crosswalk.entries:
        if entry.review_state == 'reviewed':
            value = entry.model_dump()
            relations = reviewed.setdefault(entry.product_state_id, [])
            if value not in relations:
                relations.append(value)

    # Rejection/unknown remains unknown even if an upstream row retains a label.
    types = [row.assigned_state if row.assignment_state in {'candidate', 'parent_candidate'} else None
             for row in source.assignments]
    refinement = source.reference_subtypes
    # Optional display evidence fails closed without disabling the primary view.
    if refinement is not None and (
            any(getattr(refinement.source_binding, key) != getattr(left, key)
                for key in ('input_sha256', 'data_view_ref', 'ordered_observation_sha256'))
            or [row.observation_id for row in refinement.rows] != ids):
        refinement = None
    reference_types = None if refinement is None else [
        row.source_state_id if label is not None and row.parent_state_id == label
            and row.source_state_id is not None else label
        for label, row in zip(types, refinement.rows, strict=True)
    ]
    records, seen = [], set()
    for point in source.plot_records:
        try:
            index = int(point.record_id)
        except ValueError as exc:
            raise ValueError('product_plot_index_invalid') from exc
        if str(index) != point.record_id or not 0 <= index < len(ids) or index in seen:
            raise ValueError('product_plot_index_invalid')
        seen.add(index)
        full = source.rows[index]
        if (point.x, point.y, point.group) != (full.x, full.y, full.cluster):
            raise ValueError('product_plot_table_mismatch')
        assignment = source.assignments[index]
        records.append(dict(record_id=point.record_id, x=point.x, y=point.y, cluster=full.cluster,
                            type_id=types[index], assignment_state=assignment.assignment_state,
                            qualified_assignment=assignment.qualified_assignment))
        if reference_types is not None:
            records[-1]['reference_subtype_id'] = reference_types[index]

    def summary(key: str, indices: list[int], *, composition: bool = False):
        counts = Counter(types[i] for i in indices)
        relations = [row for label in counts if label is not None for row in reviewed.get(label, [])]
        result = dict(id=key, total=len(indices), fraction=len(indices) / len(ids),
                      matched_types=sorted({row['spatial_type_id'] for row in relations}),
                      unmatched_count=sum(n for label, n in counts.items() if label not in reviewed),
                      relations=relations)
        if composition:
            result['composition'] = [dict(type_id=label, count=n, fraction=n / len(indices))
                                     for label, n in sorted(counts.items(), key=lambda v: (v[0] is None, v[0] or ''))]
        return result

    type_indices: dict[str, list[int]] = {}
    cluster_indices: dict[str, list[int]] = {}
    for i, row in enumerate(source.rows):
        if types[i] is not None:
            type_indices.setdefault(types[i], []).append(i)
        cluster_indices.setdefault(row.cluster, []).append(i)
    result = dict(n_observations=len(ids), n_displayed=len(records), records=records,
                types=[summary(key, rows) for key, rows in sorted(type_indices.items())],
                clusters=[summary(key, rows, composition=True) for key, rows in sorted(cluster_indices.items())],
                unknown_count=sum(label is None for label in types),
                unassigned_counts=dict(Counter(row.assignment_state for row, label in zip(source.assignments, types) if label is None)),
                qualified_assignment=all(row.qualified_assignment for row in source.assignments),
                sources=[left.model_dump(), right.model_dump()])
    if reference_types is not None:
        result['reference_subtypes'] = dict(
            source_label='参考表达相似性', single_source=True,
            source_binding=refinement.source_binding.model_dump(),
            resolved_count=sum(label != broad for label, broad in zip(reference_types, types, strict=True)),
            groups=[dict(id=label, total=count, fraction=count / len(ids), matched_types=[],
                         unmatched_count=count, relations=[])
                    for label, count in sorted(Counter(reference_types).items(), key=lambda row: row[0] or '')
                    if label is not None])
    return result
