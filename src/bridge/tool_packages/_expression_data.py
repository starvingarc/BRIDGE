"""Shared expression data rules used by exploration and sample comparison.

Owns matrix admissibility and complete observation labels. No tool package, execution policy or visualization is imported here.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from scipy import sparse

if TYPE_CHECKING:
    import pandas as pd
    from anndata import AnnData


def validate_matrix(data: AnnData, *, raw: bool = False) -> None:
    """Require bounded nonnegative expression, unique IDs and nonempty cells.

    Raw matrices additionally require integer counts. No mutation; failures raise
    ValueError with the same stable reason codes for both scientific consumers.
    """
    if data.n_obs < 4 or data.n_vars < 3:
        raise ValueError('expression_matrix_too_small')
    # Scanpy preserves sparse counts through normalization; PCA uses HVGs and
    # marker ranking uses bounded chunks. Do not price a sparse 10x input as dense.
    stored_values = data.X.nnz if sparse.issparse(data.X) else data.n_obs * data.n_vars
    if data.n_obs > 200000 or data.n_vars > 60000 or stored_values > 300_000_000:
        raise ValueError('expression_resource_limit')
    if not data.obs_names.is_unique or not data.var_names.is_unique:
        raise ValueError('unique_observation_and_gene_ids_required')
    values = data.X.data if sparse.issparse(data.X) else np.asarray(data.X)
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError('nonnegative_finite_expression_required')
    if raw and not np.equal(values, np.floor(values)).all():
        raise ValueError('raw_integer_counts_required')
    if np.any(np.asarray(data.X.sum(axis=1)).ravel() == 0):
        raise ValueError('zero_count_observations_require_qc')


def labels(data: AnnData, key: str) -> pd.Series:
    """Return complete string labels in observation order, capped at 200 categories.

    Missing columns, blank labels and excessive cardinality raise ValueError.
    """
    if key not in data.obs:
        raise ValueError('observation_column_not_found')
    values = data.obs[key].astype('string')
    if values.isna().any() or values.str.strip().eq('').any():
        raise ValueError('observation_labels_incomplete')
    if values.nunique() > 200:
        raise ValueError('too_many_observation_categories')
    return values.astype(str)
