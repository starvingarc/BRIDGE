"""Read immutable gene-major expression artifacts; no normalization or inference."""
from contextlib import contextmanager
import io

import numpy as np
from fastapi import HTTPException

from bridge.toolkit.contracts import ToolRun
from .inputs import checked_file
from .sample_qc import RECEIPT_LIMIT

GENE_STORE_LIMIT = 1024 * 1024 * 1024
MAX_RETURNED_VALUES = 2_000_000


@contextmanager
def gene_store(results, owner, rid, row):
    # Existing source verification binds this analysis to its sample, input,
    # QC, coordinates, marker table, receipt, and saved snapshot.
    outputs, summary = results.source(owner, rid, row)
    if summary.get("gene_expression", {}).get("state") != "available":
        raise HTTPException(404, "gene_expression_unavailable")
    root = results.researches.directory(rid)
    attempt = root / "atlas-runs" / row["snapshot"]["assessment_id"]
    try:
        import h5py
        import pandas as pd
        raw = results._read(root, attempt / "cell-atlas-run.json", RECEIPT_LIMIT,
                            row["snapshot"]["receipt_sha256"])
        run = ToolRun.model_validate_json(raw)
        files = [a for a in run.artifacts if a.kind == "expression_gene_store"]
        if len(files) != 1 or files[0].media_type != "application/x-hdf5":
            raise ValueError("gene_store_binding")
        cells_raw = next(raw for meta, raw in outputs.values() if meta["name"] == "expression_cells.parquet")
        cells = pd.read_parquet(io.BytesIO(cells_raw))
        artifact = files[0]
        with checked_file(None, None, artifact.path, artifact.sha256, root=attempt / "cell-atlas",
                          limit=GENE_STORE_LIMIT) as stream, h5py.File(stream, "r") as store:
            required = ("gene_ids", "observation_ids", "groups", "leiden", "group_counts",
                        "data", "indices", "indptr", "mean_log1p", "fraction_expressing")
            if any(not isinstance(store.get(key, getlink=True), h5py.HardLink) for key in required):
                raise ValueError("gene_store_link")
            if (store.attrs["object_version"] != "0.1.0"
                    or store.attrs["input_sha256"] != row["snapshot"]["material_sha256"]
                    or store.attrs["expression_scale"] != "natural_log1p"
                    or store.attrs["normalization"] != summary["gene_expression"]["normalization"]
                    or store["gene_ids"].shape != (summary["n_genes"],)
                    or store["observation_ids"].shape != (summary["n_observations"],)
                    or store["leiden"].shape != (summary["n_observations"],)):
                raise ValueError("gene_store_axis_binding")
            genes = store["gene_ids"].asstr()[:].tolist()
            observations = store["observation_ids"].asstr()[:].tolist()
            labels = store["leiden"].asstr()[:].tolist()
            groups = store["groups"].asstr()[:].tolist()
            if (len(set(genes)) != len(genes) or observations != cells.observation_id.tolist()
                    or labels != cells.leiden.tolist() or set(groups) != set(labels)
                    or len(set(groups)) != len(groups)
                    or store["group_counts"].shape != (len(groups),)
                    or store["mean_log1p"].shape != (len(groups), len(genes))
                    or store["fraction_expressing"].shape != (len(groups), len(genes))
                    or store["indptr"].shape != (len(genes) + 1,)
                    or len(store["data"].shape) != 1 or store["indices"].shape != store["data"].shape
                    or store["indptr"][0] != 0 or store["indptr"][-1] != len(store["data"])):
                raise ValueError("gene_store_shape_binding")
            yield store, genes, observations, labels, groups
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, StopIteration):
        raise HTTPException(409, "analysis_source_unavailable") from None


def catalog(results, owner, rid, row, *, query, offset, limit):
    with gene_store(results, owner, rid, row) as (_, genes, _, _, _):
        matching = [gene for gene in genes if query.casefold() in gene.casefold()]
        return {"analysis_id": row["id"], "material_sha256": row["snapshot"]["material_sha256"],
                "query": query, "offset": offset, "total": len(matching),
                "genes": matching[offset:offset + limit]}


def expression(results, owner, rid, row, *, genes):
    with gene_store(results, owner, rid, row) as (store, names, observations, labels, groups):
        if len(observations) * len(genes) > MAX_RETURNED_VALUES:
            raise HTTPException(413, "gene_expression_response_too_large")
        lookup = {name: i for i, name in enumerate(names)}
        records = []
        group_counts = store["group_counts"][:]
        for gene in dict.fromkeys(genes):
            if gene not in lookup:
                records.append({"gene": gene, "status": "not_found", "values": None, "groups": None})
                continue
            column = lookup[gene]
            start, stop = map(int, store["indptr"][column:column + 2])
            if not 0 <= start <= stop <= len(store["data"]):
                raise ValueError("gene_store_column_bounds")
            indices = store["indices"][start:stop]
            measured = store["data"][start:stop]
            if (np.any(indices < 0) or np.any(indices >= len(observations))
                    or (len(indices) > 1 and np.any(np.diff(indices) <= 0))
                    or not np.isfinite(measured).all() or np.any(measured < 0)):
                raise ValueError("gene_store_column_values")
            values = np.zeros(len(observations), dtype=np.float64)
            values[indices] = measured
            means = store["mean_log1p"][:, column]
            fractions = store["fraction_expressing"][:, column]
            if (not np.isfinite(means).all() or np.any(means < 0)
                    or not np.isfinite(fractions).all() or np.any((fractions < 0) | (fractions > 1))
                    or np.any(group_counts <= 0) or int(group_counts.sum()) != len(observations)):
                raise ValueError("gene_store_summary_values")
            records.append({"gene": gene, "status": "available", "values": values.tolist(),
                "groups": [{"leiden": group, "n_cells": int(group_counts[i]),
                            "mean_log1p": float(means[i]), "fraction_expressing": float(fractions[i])}
                           for i, group in enumerate(groups)]})
        return {"analysis_id": row["id"], "material_sha256": row["snapshot"]["material_sha256"],
                "scale": "natural_log1p", "normalization": str(store.attrs["normalization"]),
                "observation_ids": observations, "leiden": labels, "genes": records}
