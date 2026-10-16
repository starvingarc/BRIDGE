"""Candidate reference-only PCA/Scanpy ingest and source-bound display transfer."""
from __future__ import annotations

import hashlib
import numpy as np
import pandas as pd
from scipy import sparse

from .quick_atlas_reference import Recipe, digest, validate_tree_binding

MARKER_GENES = ("FOXA2", "LMX1A", "OTX2", "EN1", "CORIN", "SHH", "NR4A2", "TH", "DDC", "PITX3")

CHAIN_NAMES = ("脱离多能", "神经谱系", "中脑区域", "候选底板谱系", "DA 程序证据")


def map_counts(query, reference, tree, tree_cell_ids, recipe):
    """Return public bounded summaries and private full-cell assignments.

    Positions copy an existing display reference cell of the transferred label.
    They are a visualization, not query scVI coordinates or a new trajectory.
    """
    import anndata as ad
    import scanpy as sc
    from sklearn.neighbors import NearestNeighbors
    from threadpoolctl import threadpool_limits
    from bridge.tool_packages.p0_01_input_qc.io import validate_expression_object

    options = Recipe.model_validate(recipe)
    for data in (query, reference):
        validate_expression_object(data, require_counts=True)
    validate_tree_binding(tree, tree_cell_ids)
    genes = reference.var_names[reference.var_names.isin(query.var_names)]
    if len(genes) < options.minimum_shared_genes:
        raise ValueError("quick_mapping_insufficient_shared_genes")
    # No query expression contributes to feature selection, centering or PCA.
    ref = ad.AnnData(sparse.csr_matrix(reference[:, genes].X, dtype=np.float32, copy=True),
                     obs=reference.obs.copy(), var=reference.var.loc[genes, []].copy())
    new = ad.AnnData(sparse.csr_matrix(query[:, genes].X, dtype=np.float32, copy=True),
                     obs=pd.DataFrame(index=query.obs_names.copy()), var=ref.var.copy())
    # Sum duplicate cell/gene entries before nonlinear log1p, without touching inputs.
    for data in (ref, new):
        data.X.sum_duplicates()
    if np.any(np.asarray(ref.X.sum(axis=1)).ravel() == 0):
        raise ValueError("quick_mapping_zero_count_reference")
    if np.any(np.asarray(new.X.sum(axis=1)).ravel() == 0):
        raise ValueError("quick_mapping_zero_count_cells")
    with threadpool_limits(limits=options.threads):
        for data in (ref, new):
            sc.pp.normalize_total(data, target_sum=options.normalization_target)
            sc.pp.log1p(data)
        # Capture measured log-normalized expression before HVG selection/centering.
        # Query color comes from query counts, never the display neighbor.
        def marker_values(data):
            values = np.full((data.n_obs, len(MARKER_GENES)), np.nan)
            for column, gene in enumerate(MARKER_GENES):
                if gene in data.var_names:
                    values[:, column] = np.asarray(data[:, gene].X.toarray()).ravel()
            return values
        query_markers = marker_values(new)
        tree_indices = [i for i, cid in enumerate(tree_cell_ids) if cid in ref.obs_names]
        reference_markers = marker_values(ref[[tree_cell_ids[i] for i in tree_indices]])
        sc.pp.highly_variable_genes(ref, n_top_genes=min(options.n_hvg, ref.n_vars), flavor="seurat")
        selected = np.asarray(ref.var["highly_variable"], dtype=bool)
        if selected.sum() < options.n_pcs + 2 or ref.n_obs < options.n_neighbors + 1:
            raise ValueError("quick_mapping_reference_too_small")
        ref = ref[:, selected].copy()
        new = new[:, selected].copy()
        ref.var.drop(columns=["highly_variable"], inplace=True)
        new.var.drop(columns=["highly_variable"], inplace=True, errors="ignore")
        mean = np.asarray(ref.X.mean(axis=0)).ravel()
        ref.X = ref.X.toarray() - mean
        new.X = new.X.toarray() - mean
        # Scanpy 1.11 ingest otherwise centers each query batch by its own mean.
        # Explicit reference centering + zero_center=False preserves one frame,
        # including a one-cell query. PCA basis is fitted on reference only.
        sc.pp.pca(ref, n_comps=options.n_pcs, zero_center=False, random_state=0)
        sc.pp.neighbors(ref, n_neighbors=options.n_neighbors, n_pcs=options.n_pcs,
                        use_rep="X_pca", random_state=0)
        new.obsm["X_pca"] = np.asarray(new.X @ ref.varm["PCs"])
        for field in ("label", "cell_type"):
            ref.obs[field] = ref.obs[field].astype("category")
        sc.tl.ingest(new, ref, obs=["label", "cell_type"], embedding_method="pca",
                     random_state=0)
        coords = np.asarray(new.obsm["X_pca"])
        ref_coords = np.asarray(ref.obsm["X_pca"])
        # Exact neighbors give transparent numeric transfer. Ingest labels retain
        # Scanpy's kNN implementation; neither is a calibrated probability.
        neighbors = NearestNeighbors(n_neighbors=options.n_neighbors, algorithm="brute",
                                     n_jobs=options.threads).fit(ref_coords)
        distances, indices = neighbors.kneighbors(coords)
        frame = pd.DataFrame(index=query.obs_names.copy())
        frame["label"] = new.obs["label"].astype(str).to_numpy()
        frame["cell_type"] = new.obs["cell_type"].astype(str).to_numpy()
        frame["reference_cell"] = ref.obs_names[indices[:, 0]].to_numpy()
        frame["distance"] = distances[:, 0]
        frame["reference_week"] = np.median(ref.obs["gestation_week"].to_numpy()[indices], axis=1)
        pt = ref.obs["pseudotime"].to_numpy(dtype=float)[indices]
        frame["reference_pseudotime"] = [
            float(np.median(row[np.isfinite(row)])) if np.isfinite(row).any() else np.nan for row in pt
        ]
        frame["pca"] = list(coords.astype(float))
        frame["tree_node"] = -1
        for field in ("tree_x", "tree_y", "tree_z"):
            frame[field] = np.nan
        frame["tree_reference_cell"] = ""
        row_lookup = {str(cid): i for i, cid in enumerate(ref.obs_names)}
        # The frozen tree contains both modalities. Only matching reference rows
        # may supply a point. A non-tree label is never coerced onto a neural node.
        for label in sorted(frame["label"].unique()):
            candidates = [(row_lookup[cid], cid, cell) for cid, cell in zip(tree_cell_ids, tree["cells"], strict=True)
                          if cid in row_lookup and tree["subtypes"][cell[3]] == label
                          and str(ref.obs.iloc[row_lookup[cid]]["label"]) == label]
            if not candidates:
                continue
            selected_query = np.flatnonzero(frame["label"].to_numpy() == label)
            nn = NearestNeighbors(n_neighbors=1, algorithm="brute", n_jobs=options.threads).fit(
                ref_coords[[row[0] for row in candidates]])
            nearest = nn.kneighbors(coords[selected_query], return_distance=False).ravel()
            for qi, ni in zip(selected_query, nearest, strict=True):
                _, cid, cell = candidates[ni]
                frame.iloc[qi, frame.columns.get_indexer(["tree_x", "tree_y", "tree_z", "tree_node"])] = cell[:4]
                frame.iloc[qi, frame.columns.get_loc("tree_reference_cell")] = cid
    frame["tree_node"] = frame["tree_node"].astype(int)
    positioned = np.flatnonzero(frame["tree_node"].to_numpy() >= 0)
    display = positioned if len(positioned) <= 600 else np.sort(np.random.default_rng(0).choice(positioned, 600, replace=False))
    frame["display_index"] = -1
    frame.iloc[display, frame.columns.get_loc("display_index")] = np.arange(len(display))
    def public_values(values):
        return [[round(float(value), 6) if np.isfinite(value) else None for value in row] for row in values]
    panel = {
        "object_version": "0.1.0", "genes": list(MARKER_GENES),
        "tree_version": digest(tree), "feature_set_sha256": digest(genes.tolist()),
        "normalization": f"shared_gene_counts_log1p_target_{options.normalization_target}",
        "gene_status": [{"gene": gene, "status": "available" if gene in genes else "not_in_shared_gene_space",
                         "missing_from": [name for name, data in (("query", query), ("reference", reference))
                                          if gene not in data.var_names]} for gene in MARKER_GENES],
        "sample": {"values": public_values(query_markers[display])},
        "reference": {"tree_cell_indices": tree_indices, "values": public_values(reference_markers),
                      "excluded_reason": "not_in_mapping_reference"},
    }
    weeks = ref.obs["gestation_week"].to_numpy(dtype=int)[indices]
    gestation = []
    for label in sorted(frame["label"].unique()):
        values = weeks[frame["label"].to_numpy() == label].ravel()
        counts = pd.Series(values).value_counts().sort_index()
        gestation.append({"cell_type": label, "weeks": {str(k): int(v) / len(values) for k, v in counts.items()},
                          "outside_reference": None, "status": "uncalibrated_neighbor_distribution"})
    tree_fraction = {str(label): int(n) / len(frame)
                     for label, n in frame.iloc[positioned]["label"].value_counts().sort_index().items()}
    projection_hash = hashlib.sha256()
    for array in (mean, np.asarray(ref.varm["PCs"])):
        projection_hash.update(np.asarray(array, dtype="<f4").tobytes())
    summary = {
        "marker_expression_payload": panel,
        "object_version": "0.1.0", "method_label": "快速映射 v0",
        "scientific_status": "candidate", "ood_status": "not_calibrated",
        "n_cells": len(frame), "n_tree_cells": len(positioned),
        "shared_genes": len(genes), "selected_genes": ref.n_vars,
        "reference_genes_not_measured": reference.n_vars - len(genes),
        "query_genes_not_in_reference": query.n_vars - len(genes),
        "feature_set_sha256": digest(genes.tolist()), "projection_sha256": projection_hash.hexdigest(),
        "selected_feature_sha256": digest(ref.var_names.tolist()),
        "chain": [{"level": i, "name": name, "numerator": None, "denominator": None,
                   "value": None, "reason": "chain_not_computed"} for i, name in enumerate(CHAIN_NAMES)],
        "target_fraction": None, "gestation": gestation, "tree_position": tree_fraction,
        "mapped_cells": [[float(row.tree_x), float(row.tree_y), float(row.tree_z), int(row.tree_node)]
                         for row in frame.iloc[display].itertuples()],
        "alerts": [], "limitations": [
            "closed_set_label_transfer_not_ood_detection", "gestation_not_donor_holdout_validated",
            "tree_positions_are_reference_display_neighbors", "chain_not_computed",
        ],
        "tree_unavailable_cells": len(frame) - len(positioned),
        "normalization": f"shared_gene_counts_log1p_target_{options.normalization_target}",
    }
    return summary, frame
