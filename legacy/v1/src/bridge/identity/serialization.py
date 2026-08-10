from __future__ import annotations

import json
import os
from pathlib import Path


def _write_reference_artifact(adata_ref, destination, source_path=None):
    destination = Path(destination)
    if source_path is None:
        adata_ref.write_h5ad(destination)
        return "copy"

    source = Path(source_path).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"reference_h5ad_path does not exist: {source}")

    if destination.exists() or destination.is_symlink():
        destination.unlink()
    relative_source = os.path.relpath(source, start=destination.parent)
    try:
        os.symlink(relative_source, destination)
        return "symlink"
    except (OSError, NotImplementedError):
        adata_ref.write_h5ad(destination)
        return "copy"


def save_identity_results(
    outdir,
    prefix,
    bdata,
    adata_ref,
    probs_ref_cal,
    probs_query_cal,
    mean_org,
    std_org,
    Hnorm,
    t,
    u,
    u_raw,
    v,
    adata_ref_source_path=None,
):
    os.makedirs(outdir, exist_ok=True)
    adata_ref_artifact = os.path.join(outdir, f"{prefix}.adata_ref_step2.h5ad")
    reference_artifact_mode = _write_reference_artifact(
        adata_ref,
        adata_ref_artifact,
        source_path=adata_ref_source_path,
    )

    meta = {
        "t": float(t),
        "u": float(u),
        "u_raw": float(u_raw),
        "v": float(v),
        "n_query": int(bdata.n_obs),
        "n_ref": int(adata_ref.n_obs),
        "adata_ref_step2_mode": reference_artifact_mode,
    }
    with open(os.path.join(outdir, f"{prefix}.thresholds.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)

    probs_ref_cal.to_csv(os.path.join(outdir, f"{prefix}.probs_ref_cal.csv"))
    probs_query_cal.to_csv(os.path.join(outdir, f"{prefix}.probs_query_cal.csv"))
    mean_org.to_csv(os.path.join(outdir, f"{prefix}.mean_org.csv"))
    std_org.to_csv(os.path.join(outdir, f"{prefix}.std_org.csv"))
    Hnorm.to_frame().to_csv(os.path.join(outdir, f"{prefix}.Hnorm.csv"))

    bdata.write_h5ad(os.path.join(outdir, f"{prefix}.bdata_step2.h5ad"))
    print(f"[identify] Saved outputs to: {outdir}")
