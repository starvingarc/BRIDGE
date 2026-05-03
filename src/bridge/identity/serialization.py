from __future__ import annotations

import json
import os


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
):
    os.makedirs(outdir, exist_ok=True)
    meta = {
        "t": float(t),
        "u": float(u),
        "u_raw": float(u_raw),
        "v": float(v),
        "n_query": int(bdata.n_obs),
        "n_ref": int(adata_ref.n_obs),
    }
    with open(os.path.join(outdir, f"{prefix}.thresholds.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)

    probs_ref_cal.to_csv(os.path.join(outdir, f"{prefix}.probs_ref_cal.csv"))
    probs_query_cal.to_csv(os.path.join(outdir, f"{prefix}.probs_query_cal.csv"))
    mean_org.to_csv(os.path.join(outdir, f"{prefix}.mean_org.csv"))
    std_org.to_csv(os.path.join(outdir, f"{prefix}.std_org.csv"))
    Hnorm.to_frame().to_csv(os.path.join(outdir, f"{prefix}.Hnorm.csv"))

    bdata.write_h5ad(os.path.join(outdir, f"{prefix}.bdata_step2.h5ad"))
    adata_ref.write_h5ad(os.path.join(outdir, f"{prefix}.adata_ref_step2.h5ad"))
    print(f"[identify] Saved outputs to: {outdir}")
