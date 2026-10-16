"""Complete measured gene values from the same expression-exploration matrix.

The file is gene-major CSC: readers select columns without loading a dense
cell-by-gene array. Cluster summaries include zero-expression observations.
"""
from __future__ import annotations

import io
import numpy as np


def gene_store_bytes(result, *, input_sha256: str) -> bytes:
    import h5py
    from scipy import sparse
    matrix = sparse.csc_matrix(result.expression, copy=True)
    matrix.sum_duplicates()
    matrix.eliminate_zeros()
    matrix.sort_indices()
    labels = result.umap["group"].astype(str).to_numpy()
    groups = [str(row["group"]) for row in result.composition]
    if result.grouping_source == "exploratory_leiden":
        groups = [group.removeprefix("Cluster ") for group in groups]
        labels = np.array([group.removeprefix("Cluster ") for group in labels])
    buffer = io.BytesIO()
    with h5py.File(buffer, "w") as store:
        store.attrs.update(object_version="0.1.0", input_sha256=input_sha256,
                           expression_scale="natural_log1p", normalization=result.preparation["normalization"])
        strings = h5py.string_dtype("utf-8")
        for name, values in (("gene_ids", result.gene_ids),
                             ("observation_ids", result.umap.observation_id.tolist()),
                             ("groups", groups), ("leiden", labels)):
            store.create_dataset(name, data=np.asarray(values, dtype=object), dtype=strings)
        for name, values in (("data", matrix.data), ("indices", matrix.indices), ("indptr", matrix.indptr)):
            store.create_dataset(name, data=values, compression="gzip", compression_opts=1)
        store.create_dataset("group_counts", data=[int(np.count_nonzero(labels == group)) for group in groups])
        shape = (len(groups), matrix.shape[1])
        means = store.create_dataset("mean_log1p", shape=shape, dtype="float64", compression="gzip")
        fractions = store.create_dataset("fraction_expressing", shape=shape, dtype="float64", compression="gzip")
        for index, group in enumerate(groups):
            cells = labels == group
            selected = matrix[cells, :]
            means[index] = np.asarray(selected.sum(axis=0, dtype=np.float64)).ravel() / int(cells.sum())
            fractions[index] = np.asarray((selected > 0).sum(axis=0)).ravel() / int(cells.sum())
    return buffer.getvalue()


def marker_table(result):
    """Preserve Scanpy's signed ranking; add explicit one-based rank and cluster ID."""
    table = result.markers.copy()
    table["rank"] = table.groupby("group", observed=True, sort=False).cumcount() + 1
    table = table.rename(columns={"group": "leiden"})
    table["leiden"] = table["leiden"].astype("string").str.removeprefix("Cluster ")
    for column in ("score", "log2_fold_change", "pvalue", "padj", "fraction_in", "fraction_rest"):
        table[column] = table[column].astype(float).replace([np.inf, -np.inf], np.nan)
    return table
