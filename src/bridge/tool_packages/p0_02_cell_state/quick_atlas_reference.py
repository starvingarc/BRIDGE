"""Checksummed, private reference inputs for the candidate ingest method.

Reference counts/labels are never learned from query expression. The feature
intersection is an execution identity because different assays measure different
gene universes. Full reference donors remain in the private bundle.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from bridge.tool_packages.p0_01_input_qc.io import sha256_path

QUICK_ATLAS_SPEC = "ATLAS-ingest-quick-v0.1"
METHOD_VERSION = "scanpy-ingest-v0.1.0"


class Recipe(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    n_hvg: int = Field(default=2000, ge=8, le=5000)
    n_pcs: int = Field(default=30, ge=2, le=50)
    n_neighbors: int = Field(default=30, ge=2, le=100)
    minimum_shared_genes: int = Field(default=1000, ge=8)
    normalization_target: int = Field(default=10000, ge=1000)
    random_seed: Literal[0] = 0
    threads: int = Field(default=2, ge=1, le=4)


class MappingParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    reference_manifest: Path
    reference_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sample_context: Literal["pre_graft", "post_graft"]


@dataclass(frozen=True)
class FrozenReference:
    manifest: dict
    reference: object
    tree: dict
    tree_cell_ids: list[str]


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def validate_tree_binding(tree, ids):
    import math
    if (not isinstance(tree, dict) or not isinstance(ids, list)
            or len(ids) != len(tree.get("cells", [])) or len(set(ids)) != len(ids)
            or not all(isinstance(x, str) and x for x in ids)):
        raise ValueError("quick_mapping_tree_binding_invalid")
    names = tree.get("subtypes", [])
    if not names or len(set(names)) != len(names):
        raise ValueError("quick_mapping_tree_binding_invalid")
    for cell in tree["cells"]:
        if (not isinstance(cell, list) or len(cell) != 7 or type(cell[3]) is not int
                or not 0 <= cell[3] < len(names) or cell[6] not in (0, 1)
                or not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)
                           for x in cell)):
            raise ValueError("quick_mapping_tree_binding_invalid")


def freeze_reference(reference, tree, tree_cell_ids, output_dir, *,
                     reference_id, modality, source_records, recipe=None):
    """Freeze caller-supplied reference-only counts and explicit display row IDs."""
    from bridge.tool_packages.p0_01_input_qc.io import validate_expression_object
    expected = {"scRNA": "REF-CHEN-VMB-SC-v1", "snRNA": "REF-CHEN-VMB-SN-v1"}
    if expected.get(modality) != reference_id:
        raise ValueError("quick_mapping_reference_modality_mismatch")
    validate_expression_object(reference, require_counts=True)
    tree = {key: tree[key] for key in ("subtypes", "nodes", "edges", "cells", "source")}
    validate_tree_binding(tree, tree_cell_ids)
    columns = ("label", "cell_type", "gestation_week", "pseudotime", "modality", "donor")
    if any(k not in reference.obs for k in columns):
        raise ValueError("quick_mapping_reference_annotations_required")
    if not reference.obs["modality"].eq(modality).all():
        raise ValueError("quick_mapping_reference_modality_mismatch")
    if reference.obs[["label", "cell_type", "gestation_week", "donor"]].isna().any().any():
        raise ValueError("quick_mapping_reference_annotations_required")
    for cid, cell in zip(tree_cell_ids, tree["cells"], strict=True):
        if cid in reference.obs_names:
            row = reference.obs.loc[cid]
            if (str(row["label"]) != tree["subtypes"][cell[3]]
                    or float(row["gestation_week"]) != cell[4]
                    or (modality == "scRNA") != bool(cell[6])):
                raise ValueError("quick_mapping_tree_binding_invalid")
    recipe = Recipe.model_validate(recipe or {}).model_dump()
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=False, mode=0o700)
    # Only the count matrix and necessary reference annotations are retained.
    import anndata as ad
    ref = ad.AnnData(reference.X.copy(), obs=reference.obs[list(columns)].copy(),
                     var=reference.var[[]].copy())
    ref.write_h5ad(root / "reference.h5ad", compression="gzip")
    (root / "tree.json").write_bytes(canonical(tree))
    (root / "tree-cell-ids.json").write_bytes(canonical(tree_cell_ids))
    data = {name: {"path": filename, "sha256": sha256_path(root / filename)}
            for name, filename in (("data", "reference.h5ad"), ("tree", "tree.json"),
                                   ("tree_cell_ids", "tree-cell-ids.json"))}
    manifest = {
        "object_version": "0.1.0", "method_version": METHOD_VERSION,
        "reference_id": reference_id, "modality": modality,
        "reference_version": data["data"]["sha256"],
        "annotation_version": digest(ref.obs.astype(str).to_dict(orient="split")),
        "recipe": recipe, "source_records": source_records, "n_cells": ref.n_obs,
        **data,
    }
    path = root / "manifest.json"
    path.write_bytes(canonical(manifest))
    return path


def read_manifest(path, expected_sha256=None):
    path = Path(path)
    if path.is_symlink() or path.stat().st_size > 1024 * 1024:
        raise ValueError("quick_mapping_reference_integrity")
    raw = path.read_bytes()
    if expected_sha256 and hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("quick_mapping_reference_integrity")
    value = json.loads(raw)
    if value.get("object_version") != "0.1.0" or value.get("method_version") != METHOD_VERSION:
        raise ValueError("quick_mapping_reference_version")
    Recipe.model_validate(value["recipe"])
    expected = {"scRNA": "REF-CHEN-VMB-SC-v1", "snRNA": "REF-CHEN-VMB-SN-v1"}
    if expected.get(value.get("modality")) != value.get("reference_id"):
        raise ValueError("quick_mapping_reference_modality_mismatch")
    return value


def checked_resource(root, item):
    relative = Path(item["path"])
    if relative.is_absolute() or len(relative.parts) != 1 or relative.name in (".", ".."):
        raise ValueError("quick_mapping_reference_integrity")
    path = root / relative
    if path.is_symlink() or sha256_path(path) != item["sha256"]:
        raise ValueError("quick_mapping_reference_integrity")
    return path


def load_reference(path, *, expected_modality, expected_sha256=None):
    import anndata as ad
    path = Path(path)
    manifest = read_manifest(path, expected_sha256)
    if manifest["modality"] != expected_modality:
        raise ValueError("quick_mapping_reference_modality_mismatch")
    paths = {name: checked_resource(path.parent, manifest[name])
             for name in ("data", "tree", "tree_cell_ids")}
    ref = ad.read_h5ad(paths["data"])
    tree = json.loads(paths["tree"].read_bytes())
    ids = json.loads(paths["tree_cell_ids"].read_bytes())
    validate_tree_binding(tree, ids)
    if (ref.n_obs != manifest["n_cells"] or not ref.obs["modality"].eq(expected_modality).all()):
        raise ValueError("quick_mapping_reference_modality_mismatch")
    return FrozenReference(manifest, ref, tree, ids)
