"""Small synthetic reference; labels and tree positions are independently prescribed."""
from pathlib import Path
import json

import anndata as ad
import numpy as np
import pandas as pd
from scipy import sparse


def reference_data():
    rng = np.random.default_rng(129)
    labels = np.repeat(["RG_mFP", "Neuron_DA", "Endothelial_Cell"], 32)
    counts = rng.poisson(2, (96, 80)).astype(np.float32)
    for group in range(3):
        counts[group * 32:(group + 1) * 32, group * 12:(group + 1) * 12] += 35
    obs = pd.DataFrame({
        "label": labels, "cell_type": labels, "gestation_week": np.repeat([7, 20, 8], 32),
        "pseudotime": np.repeat([0.1, 0.9, np.nan], 32),
        "modality": ["scRNA"] * 96, "donor": np.repeat(["a", "b", "c"], 32),
    }, index=[f"ref-{i}" for i in range(96)])
    var = pd.DataFrame(index=[f"G{i}" for i in range(80)])
    return ad.AnnData(sparse.csr_matrix(counts), obs=obs, var=var)


def tree_data():
    # Six real reference observations have a display coordinate, never Endothelial.
    ids = ["ref-0", "ref-1", "ref-2", "ref-32", "ref-33", "ref-34"]
    cells = [[-0.8, 0.1, 0.0, 0, 7, 0.1, 1]] * 3 + [[0.8, 0.3, 0.1, 1, 20, 0.9, 1]] * 3
    return {"subtypes": ["RG_mFP", "Neuron_DA"], "nodes": [[-0.8, 0.1, 0], [0.8, 0.3, 0.1]],
            "edges": [[1, 0]], "cells": cells, "source": "Synthetic fixture"}, ids


RECIPE = {"n_hvg": 40, "n_pcs": 8, "n_neighbors": 5, "minimum_shared_genes": 32,
          "normalization_target": 10000, "random_seed": 0, "threads": 2}


def split_counts(data):
    """Equivalent CSR storage with two entries per cell/gene, not two genes."""
    result = data.copy()
    x = result.X.tocsr()
    assert np.all(x.data >= 1)
    result.X = sparse.csr_matrix((np.column_stack((np.ones_like(x.data), x.data - 1)).ravel(),
                                 np.repeat(x.indices, 2), x.indptr * 2), shape=x.shape)
    return result
