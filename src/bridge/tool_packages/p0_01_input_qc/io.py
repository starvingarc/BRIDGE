from __future__ import annotations

import hashlib
from pathlib import Path

import anndata as ad
import numpy as np
import pandas as pd
from scipy import sparse
from scipy.io import mmread

from bridge.toolkit.contracts import InputAsset


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
