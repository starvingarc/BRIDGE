from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Self

import anndata as ad
import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from scipy import sparse
from scipy.io import mmread

from bridge.tool_packages._configurable_contracts import (
    BiologicalUnitAssignment,
    BiologicalUnitAssignmentArtifact,
    BiologicalUnitBinding,
    BiologicalUnitManifest,
    VersionedObjectRef,
    biological_unit_assignment_reasons,
    observation_ids_sha256,
)
from bridge.toolkit.contracts import (
    BiologicalUnitKind,
    DataViewBinding,
    IndependenceGroupKind,
    InputAsset,
)

LINEAGE_METADATA_KEY = "biological_unit_lineage"
_LINEAGE_SCHEMA_VERSION = "0.1.0"
_HIERARCHY_KINDS = tuple(BiologicalUnitKind)


class InputAuditError(ValueError):
    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(detail)
        self.reason_code = reason_code


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    if path.is_file():
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(child.relative_to(path).as_posix().encode("utf-8"))
        with child.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def read_expression_asset(asset: InputAsset) -> ad.AnnData:
    if asset.format == "h5ad":
        adata = ad.read_h5ad(asset.path)
        if asset.matrix_location and asset.matrix_location != "X":
            prefix = "layers/"
            if not asset.matrix_location.startswith(prefix):
                raise InputAuditError("unsupported_matrix_location", asset.matrix_location)
            layer = asset.matrix_location[len(prefix) :]
            if layer not in adata.layers:
                raise InputAuditError("matrix_layer_not_found", layer)
            adata = adata.copy()
            adata.X = adata.layers[layer].copy()
        return adata
    if asset.format == "10x_mtx":
        return _read_10x_mtx(asset)
    if asset.format == "10x_h5":
        import scanpy as sc

        adata = sc.read_10x_h5(asset.path)
        _add_constant_metadata(adata, asset)
        return adata
    raise InputAuditError("unsupported_expression_format", asset.format)


def validate_expression_object(adata: ad.AnnData, *, require_counts: bool) -> None:
    if adata.n_obs == 0 or adata.n_vars == 0:
        raise InputAuditError("empty_expression_object", "Expression object has zero cells or genes")
    if not adata.obs_names.is_unique:
        raise InputAuditError("duplicate_cell_ids", "Cell IDs must be unique")
    if not adata.var_names.is_unique:
        raise InputAuditError("duplicate_gene_ids", "Gene IDs must be unique")
    values = adata.X.data if sparse.issparse(adata.X) else np.asarray(adata.X).ravel()
    if not np.isfinite(values).all():
        raise InputAuditError("non_finite_expression_values", "Expression matrix contains NaN or infinity")
    if (values < 0).any():
        raise InputAuditError("negative_expression_values", "Expression matrix contains negative values")
    if require_counts and not np.allclose(values, np.round(values), rtol=0, atol=1e-8):
        raise InputAuditError(
            "raw_counts_must_be_nonnegative_integers",
            "Declared raw counts contain non-integer values",
        )


def _read_10x_mtx(asset: InputAsset) -> ad.AnnData:
    matrix_path = _first_existing(asset.path, "matrix.mtx", "matrix.mtx.gz")
    feature_path = _first_existing(asset.path, "features.tsv", "features.tsv.gz", "genes.tsv", "genes.tsv.gz")
    barcode_path = _first_existing(asset.path, "barcodes.tsv", "barcodes.tsv.gz")
    matrix = mmread(matrix_path).tocsr().transpose().tocsr()
    features = pd.read_csv(feature_path, sep="\t", header=None, compression="infer")
    barcodes = pd.read_csv(barcode_path, sep="\t", header=None, compression="infer")
    if matrix.shape != (len(barcodes), len(features)):
        raise InputAuditError("10x_dimension_mismatch", "Matrix, feature and barcode dimensions disagree")
    gene_names = features.iloc[:, 1] if features.shape[1] > 1 else features.iloc[:, 0]
    adata = ad.AnnData(
        matrix,
        obs=pd.DataFrame(index=barcodes.iloc[:, 0].astype(str)),
        var=pd.DataFrame(index=gene_names.astype(str)),
    )
    _add_constant_metadata(adata, asset)
    return adata


def _first_existing(root: Path, *names: str) -> Path:
    for name in names:
        candidate = root / name
        if candidate.is_file():
            return candidate
    raise InputAuditError("incomplete_10x_mtx_directory", f"Missing one of: {', '.join(names)}")


def _add_constant_metadata(adata: ad.AnnData, asset: InputAsset) -> None:
    for key in ("sample_id", "capture_id"):
        value = asset.metadata.get(key)
        if value is not None:
            adata.obs[key] = str(value)


class DeclaredLineageMetadata(BaseModel):
    """Caller-declared lineage inputs; this model grants no review authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_unit_kind: Literal["sample", "preparation"]
    source_unit_ref: VersionedObjectRef
    unit_identity_namespace_ref: VersionedObjectRef
    analysis_unit_kind: BiologicalUnitKind
    independence_group_kind: IndependenceGroupKind
    independence_scope_ref: VersionedObjectRef
    observation_ref_columns: dict[BiologicalUnitKind, str] = Field(default_factory=dict)
    constant_unit_refs: dict[BiologicalUnitKind, VersionedObjectRef] = Field(default_factory=dict)

    @model_validator(mode="after")
    def required_unit_sources_are_explicit(self) -> Self:
        column_kinds = set(self.observation_ref_columns)
        constant_kinds = set(self.constant_unit_refs)
        overlap = column_kinds & constant_kinds
        if overlap:
            names = ", ".join(sorted(item.value for item in overlap))
            raise ValueError(f"unit kinds cannot be both column and constant: {names}")
        for kind, column in self.observation_ref_columns.items():
            if not isinstance(column, str) or not column.strip():
                raise ValueError(f"{kind.value} observation reference column must be non-empty")
        required = {
            BiologicalUnitKind(self.source_unit_kind),
            self.analysis_unit_kind,
            BiologicalUnitKind(self.independence_group_kind),
        }
        missing = required - column_kinds - constant_kinds
        if missing:
            names = ", ".join(sorted(item.value for item in missing))
            raise ValueError(f"missing explicit observation unit sources: {names}")
        return self


@dataclass(frozen=True)
class DeclaredLineageOutput:
    selected_data_view: DataViewBinding | None
    assignment_artifact: BiologicalUnitAssignmentArtifact | None
    manifest: BiologicalUnitManifest | None
    reason_codes: tuple[str, ...]

    @property
    def lineage_is_available(self) -> bool:
        return self.assignment_artifact is not None and self.manifest is not None


def build_declared_lineage(
    *,
    asset: InputAsset,
    observations: pd.DataFrame,
    input_hash: str,
    run_id: str,
    tool_version: str,
    input_level: str,
) -> DeclaredLineageOutput:
    """Build a declared-only lineage for the exact immutable input observation set."""

    if input_level == "droplet_ready":
        return DeclaredLineageOutput(
            selected_data_view=None,
            assignment_artifact=None,
            manifest=None,
            reason_codes=("biological_unit_lineage_unavailable:droplet_observations_are_not_cells",),
        )

    observation_ids = [str(item) for item in observations.index]
    observation_digest = observation_ids_sha256(observation_ids)
    view_ref = f"data-view:{run_id}:all-observations@{_LINEAGE_SCHEMA_VERSION}"
    base_view = DataViewBinding(
        view_id=view_ref,
        view_kind="all_observations",
        artifact_id=f"input-asset:{asset.asset_id}",
        sha256=input_hash,
        parent_asset_id=asset.asset_id,
        parent_asset_sha256=input_hash,
        matrix_location=asset.matrix_location or "X",
        matrix_semantics=asset.matrix_semantics,
        n_observations=len(observation_ids),
        observation_ids_sha256=observation_digest,
    )

    raw_metadata = asset.metadata.get(LINEAGE_METADATA_KEY)
    if raw_metadata is None:
        return _lineage_unavailable(base_view, "biological_unit_lineage_metadata_missing")
    try:
        declaration = DeclaredLineageMetadata.model_validate(raw_metadata)
    except ValidationError:
        return _lineage_unavailable(base_view, "biological_unit_lineage_metadata_invalid")

    missing_columns = sorted(
        {
            column
            for column in declaration.observation_ref_columns.values()
            if column not in observations.columns
        }
    )
    if missing_columns:
        return _lineage_unavailable(base_view, "biological_unit_lineage_column_missing")

    assignments: list[BiologicalUnitAssignment] = []
    bindings: dict[str, BiologicalUnitBinding] = {}
    for observation_id, (_, row) in zip(observation_ids, observations.iterrows(), strict=True):
        refs: dict[BiologicalUnitKind, VersionedObjectRef] = dict(declaration.constant_unit_refs)
        for kind, column in declaration.observation_ref_columns.items():
            value = row[column]
            if pd.isna(value) or not isinstance(value, str) or not value.strip():
                return _lineage_unavailable(base_view, "biological_unit_lineage_reference_missing")
            try:
                refs[kind] = _parse_versioned_ref(value.strip())
            except (ValidationError, ValueError):
                return _lineage_unavailable(base_view, "biological_unit_lineage_reference_invalid")

        source_kind = BiologicalUnitKind(declaration.source_unit_kind)
        if refs[source_kind] != declaration.source_unit_ref:
            return _lineage_unavailable(base_view, "biological_unit_lineage_source_mismatch")

        analysis_ref = refs[declaration.analysis_unit_kind]
        independence_ref = refs[BiologicalUnitKind(declaration.independence_group_kind)]
        hierarchy = {
            f"{kind.value}_ref": refs[kind].ref if kind in refs else None
            for kind in _HIERARCHY_KINDS
        }
        try:
            assignment = BiologicalUnitAssignment(
                observation_id=observation_id,
                analysis_unit_ref=analysis_ref.ref,
                independence_group_ref=independence_ref.ref,
                **hierarchy,
            )
            binding = BiologicalUnitBinding(
                analysis_unit_ref=analysis_ref,
                analysis_unit_kind=declaration.analysis_unit_kind,
                independence_group_ref=independence_ref,
                independence_group_kind=declaration.independence_group_kind,
                **{
                    key: None if value is None else _parse_versioned_ref(value)
                    for key, value in hierarchy.items()
                },
            )
        except (ValidationError, ValueError):
            return _lineage_unavailable(base_view, "biological_unit_lineage_contract_invalid")
        previous = bindings.setdefault(analysis_ref.ref, binding)
        if previous != binding:
            return _lineage_unavailable(base_view, "biological_unit_lineage_binding_conflict")
        assignments.append(assignment)

    try:
        assignment_artifact = BiologicalUnitAssignmentArtifact(
            object_version=_LINEAGE_SCHEMA_VERSION,
            schema_ref="bridge://schemas/biological-unit-assignment/v0.1",
            data_view_ref=view_ref,
            observation_ids_sha256=observation_digest,
            assignments=assignments,
        )
        assignment_sha256 = model_sha256(assignment_artifact)
        manifest = BiologicalUnitManifest(
            object_version=_LINEAGE_SCHEMA_VERSION,
            manifest_id=f"biological-unit-manifest:{run_id}",
            manifest_version=_LINEAGE_SCHEMA_VERSION,
            schema_ref="bridge://schemas/biological-unit-manifest/v0.1",
            generator_tool_id="P0-01",
            generator_tool_version=tool_version,
            data_view_ref=view_ref,
            selected_artifact_sha256=input_hash,
            observation_ids_sha256=observation_digest,
            n_observations=len(observation_ids),
            assignment_schema_ref=assignment_artifact.schema_ref,
            assignment_artifact_sha256=assignment_sha256,
            assignment_row_count=len(assignments),
            unit_identity_namespace_ref=declaration.unit_identity_namespace_ref,
            analysis_unit_kind=declaration.analysis_unit_kind,
            independence_group_kind=declaration.independence_group_kind,
            independence_scope_ref=declaration.independence_scope_ref,
            lineage_state="declared",
            review_gate_ref=None,
            review_gate_sha256=None,
            unit_bindings=[bindings[key] for key in sorted(bindings)],
        )
    except (ValidationError, ValueError):
        return _lineage_unavailable(base_view, "biological_unit_lineage_contract_invalid")

    if biological_unit_assignment_reasons(
        manifest=manifest,
        artifact=assignment_artifact,
        artifact_sha256=assignment_sha256,
    ):
        return _lineage_unavailable(base_view, "biological_unit_lineage_contract_invalid")

    manifest_sha256 = model_sha256(manifest)
    bound_view = base_view.model_copy(
        update={
            "sample_or_preparation_ref": declaration.source_unit_ref.ref,
            "biological_unit_manifest_ref": manifest.ref.ref,
            "biological_unit_manifest_sha256": manifest_sha256,
        }
    )
    return DeclaredLineageOutput(
        selected_data_view=bound_view,
        assignment_artifact=assignment_artifact,
        manifest=manifest,
        reason_codes=(),
    )


def canonical_json_bytes(payload: object) -> bytes:
    if isinstance(payload, BaseModel):
        payload = payload.model_dump(mode="json")
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            default=str,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def model_sha256(model: BaseModel) -> str:
    return hashlib.sha256(canonical_json_bytes(model)).hexdigest()


def _parse_versioned_ref(value: str) -> VersionedObjectRef:
    object_id, separator, object_version = value.rpartition("@")
    if separator != "@" or not object_id or not object_version:
        raise ValueError("versioned biological unit reference must use object_id@object_version")
    return VersionedObjectRef(object_id=object_id, object_version=object_version)


def _lineage_unavailable(view: DataViewBinding, reason: str) -> DeclaredLineageOutput:
    return DeclaredLineageOutput(
        selected_data_view=view,
        assignment_artifact=None,
        manifest=None,
        reason_codes=(reason,),
    )
