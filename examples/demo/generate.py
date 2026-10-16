"""Generate small, entirely synthetic collaboration assets; never read user data."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import anndata as ad
import numpy as np
import pandas as pd
import yaml
from scipy import sparse

from bridge.tool_packages.p0_02_cell_state.reference import (
    build_reference_snapshot,
    load_packaged_marker_programs,
)

SNAPSHOT = "REF-SYNTHETIC-COLLAB-v1"
SPEC = "CELLSTATE-scRNA-synthetic-v0.1"
STATES = {
    "RG_mFP": ("Radial_Glia", ["SOX2", "HES1", "FOXA2", "LMX1A", "OTX2"]),
    "RG_mBMP": ("Radial_Glia", ["SOX2", "HES5", "WNT1", "MSX1"]),
    "Nb_mFP": ("Neuroblast", ["DCX", "STMN2", "FOXA2", "LMX1A", "NR4A2"]),
    "Nb_mBMP": ("Neuroblast", ["DCX", "TUBB3", "MSX1", "WNT1"]),
    "Neuron_DA": ("Neuron_DA", ["TH", "DDC", "SLC6A3", "NR4A2", "PITX3"]),
    "Astrocyte": ("Astrocyte", ["AQP4", "ALDH1L1", "SLC1A3", "GFAP"]),
}


def generate(output: Path) -> None:
    if output.exists() and any(output.iterdir()):
        raise SystemExit("Choose an empty output directory; existing files are not overwritten.")
    output.mkdir(parents=True, exist_ok=True)
    _, cards = load_packaged_marker_programs()
    markers = {g for card in cards for g in card.positive_markers + card.negative_markers}
    markers.update(g for _, genes in STATES.values() for g in genes)
    markers.update(["MT-CO1", "MT-ND1", "RPLP0", "RPS18", "MKI67", "TOP2A", "PCNA"])
    genes = sorted(markers)
    genes += [f"SYNTHETIC_GENE_{i:04d}" for i in range(1024 - len(genes))]
    rng = np.random.default_rng(20260924)
    index = {g: i for i, g in enumerate(genes)}
    for name, sizes in (("reference", [64] * 6), ("product", [128, 32, 96, 32, 64, 32])):
        labels = np.repeat(list(STATES), sizes)
        counts = rng.poisson(0.8, (len(labels), len(genes))).astype(np.int32)
        for number, (label, (_, signature)) in enumerate(STATES.items()):
            rows = np.flatnonzero(labels == label)
            columns = [index[g] for g in signature]
            columns += list(range(400 + number * 60, 460 + number * 60))
            counts[np.ix_(rows, columns)] += rng.poisson(5, (len(rows), len(columns)))
        obs = pd.DataFrame(index=[f"synthetic-{name}-{i:04d}" for i in range(len(labels))])
        obs["Sample"] = ([f"synthetic-ref-{i % 2}" for i in range(len(labels))]
                         if name == "reference" else "synthetic-product-01")
        if name == "reference":
            obs["label"] = [STATES[label][0] for label in labels]
            obs["subtype"] = labels
            obs["developmental_stage"] = ["progenitor" if x.startswith("RG_") else
                                          "precursor" if x.startswith("Nb_") else "other"
                                          for x in labels]
        else:
            pd.DataFrame({"cell_id": obs.index, "synthetic_state": labels}).to_csv(
                output / "product-design.csv", index=False)
        data = ad.AnnData(sparse.csr_matrix(counts), obs=obs,
                         var=pd.DataFrame({"gene_symbol": genes}, index=genes))
        norm = counts.astype(np.float32) * (10000 / counts.sum(axis=1))[:, None]
        data.layers["logcounts"] = sparse.csr_matrix(np.log1p(norm).astype(np.float32))
        data.uns["provenance"] = {"origin": "entirely_synthetic", "seed": 20260924,
                                  "version": "1.0.0", "matrix_X": "raw_counts",
                                  "purpose": "software_development_only",
                                  "biological_validation": "none"}
        data.write_h5ad(output / f"{name}.h5ad", compression="gzip")

    source = {"source_family_id": "SYNTHETIC-COLLAB", "evidence_family_id": "EF-SYNTHETIC-COLLAB",
              "asset_path": str((output / "reference.h5ad").resolve()), "assay": "scRNA-seq",
              "anatomy": "synthetic midbrain-like expression patterns; not tissue",
              "developmental_time": "synthetic stage labels; not measured time",
              "status": "candidate", "sample_column": "Sample", "matrix_location": "X",
              "matrix_semantics": "raw_counts"}
    catalog = {"snapshot_id": SNAPSHOT, "version": "1.0.0", "status": "candidate",
               "measurement_spec_ids": [SPEC], "sources": [
                   {**source, "source_id": "SYNTHETIC-L1", "label_level": "L1",
                    "role": "primary", "label_column": "label"},
                   {**source, "source_id": "SYNTHETIC-L2", "label_level": "L2",
                    "role": "refinement", "label_column": "subtype",
                    "filters": {"subtype": list(STATES)[:4]}}]}
    # Local paths are only transient builder inputs, never distributed configuration.
    catalog_path = output / ".build-catalog.yaml"
    catalog_path.write_text(yaml.safe_dump(catalog), encoding="utf-8")
    try:
        build_reference_snapshot(catalog_path, output / "references" / SNAPSHOT)
    finally:
        catalog_path.unlink()
    files = {str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(output.rglob("*")) if p.is_file()}
    (output / "checksums.json").write_text(json.dumps(files, indent=2) + "\n", encoding="utf-8")
    print(f"Created {len(files)} synthetic assets in {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    generate(parser.parse_args().output)
