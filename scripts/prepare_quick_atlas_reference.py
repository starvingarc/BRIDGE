#!/usr/bin/env python3
"""Freeze controlled Chen sc/sn references and existing tree row bindings.

This prepares private deployment resources, never downloadable fixtures or
scientific qualification. Query data are not read by this command.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

import anndata as ad
import h5py
import numpy as np
import pandas as pd

from bridge.tool_packages.p0_01_input_qc.io import sha256_path
from bridge.tool_packages.p0_02_cell_state.quick_atlas_reference import freeze_reference, canonical


def prepare(atlas_path, neural_path, tree_path, output_dir, modality_selection="scRNA"):
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=False, mode=0o700)
    print("Hashing controlled source inputs", flush=True)
    sources = [{"id": name, "sha256": sha256_path(Path(path))}
               for name, path in (("chen-vmb-whole-v1", atlas_path),
                                  ("chen-vmb-neurogenesis-top1-v1", neural_path), ("existing-display-tree", tree_path))]
    print("Reading reference counts and annotation joins", flush=True)
    with h5py.File(atlas_path, "r") as handle:
        obs = ad.io.read_elem(handle["obs"])
        var = ad.io.read_elem(handle["var"])
        counts = ad.io.read_elem(handle["layers/counts"]).tocsr()
    with h5py.File(neural_path, "r") as handle:
        neural = ad.io.read_elem(handle["obs"])
    tree = json.loads(Path(tree_path).read_bytes())
    # Replay only the existing deterministic display sampling, never graph edges
    # or geometry. Every row is checked against its immutable biological label.
    rng = np.random.default_rng(20261012)
    positions = []
    fine = neural["subsubtype"].astype(str).to_numpy()
    for label in np.unique(fine):
        candidates = np.flatnonzero(fine == label)
        positions.extend(rng.choice(candidates, min(len(candidates), 700), replace=False))
    positions = np.sort(positions)
    ids = neural.index[positions].astype(str).tolist()
    if len(ids) != len(tree["cells"]):
        raise ValueError("tree_sample_recipe_mismatch")
    for pos, cell in zip(positions, tree["cells"], strict=True):
        row = neural.iloc[pos]
        if (str(row["subsubtype"]) != tree["subtypes"][cell[3]]
                or int(str(row["Age"])[2:]) != cell[4]
                or (str(row["modality"]) == "scRNA") != bool(cell[6])
                or round(float(row["palantir_pseudotime_scvi_top1"]), 3) != cell[5]):
            raise ValueError("tree_source_row_binding_mismatch")
    annotation = pd.DataFrame(index=obs.index)
    annotation["cell_type"] = obs["cell_type"].astype(str)
    annotation["label"] = neural["subsubtype"].astype(str).reindex(obs.index)
    annotation["label"] = annotation["label"].fillna(annotation["cell_type"])
    annotation["gestation_week"] = obs["Age"].astype(str).str.removeprefix("GW").astype(int)
    annotation["pseudotime"] = neural["palantir_pseudotime_scvi_top1"].reindex(obs.index)
    annotation["modality"] = obs["modality"].astype(str)
    annotation["donor"] = obs["Sample"].astype(str)
    catalog = {}
    for modality, context, reference_id in (("scRNA", "pre_graft", "REF-CHEN-VMB-SC-v1"),
                                             ("snRNA", "post_graft", "REF-CHEN-VMB-SN-v1")):
        if modality_selection != "both" and modality != modality_selection:
            continue
        mask = annotation["modality"].eq(modality).to_numpy()
        data = ad.AnnData(counts[mask].copy(), obs=annotation.loc[mask].copy(), var=var[[]].copy())
        print(f"Freezing {modality}: {data.n_obs} cells, {data.n_vars} genes", flush=True)
        manifest = freeze_reference(data, tree, ids, root / modality,
                                    reference_id=reference_id, modality=modality,
                                    source_records=sources)
        catalog[context] = {"manifest": str(manifest.resolve()), "sha256": sha256_path(manifest)}
        del data
    path = root / "catalog.json"
    path.write_bytes(canonical(catalog))
    print(f"Prepared {path}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--atlas", type=Path, required=True)
    parser.add_argument("--neurogenesis", type=Path, required=True)
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--modality", choices=("scRNA", "snRNA", "both"), default="scRNA")
    args = parser.parse_args()
    prepare(args.atlas, args.neurogenesis, args.tree, args.output, args.modality)
