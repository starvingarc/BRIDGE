from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from bridge.identity.serialization import save_identity_results


class WritableAnnData:
    def __init__(self, n_obs: int):
        self.n_obs = n_obs
        self.write_calls = []

    def write_h5ad(self, path):
        self.write_calls.append(Path(path))
        Path(path).write_text("h5ad placeholder", encoding="utf-8")


def _frame(index):
    return pd.DataFrame({"RG_Mesencephalon_FP": [0.9 for _ in index]}, index=index)


def test_save_identity_results_links_reference_artifact_when_source_path_is_provided(tmp_path):
    source = tmp_path / "target_reference.h5ad"
    source.write_text("reference", encoding="utf-8")
    bdata = WritableAnnData(n_obs=2)
    adata_ref = WritableAnnData(n_obs=10)
    index = ["c1", "c2"]

    save_identity_results(
        outdir=tmp_path / "out",
        prefix="demo",
        bdata=bdata,
        adata_ref=adata_ref,
        probs_ref_cal=_frame(["r1", "r2"]),
        probs_query_cal=_frame(index),
        mean_org=_frame(index),
        std_org=_frame(index),
        Hnorm=pd.Series([0.1, 0.2], index=index, name="Hnorm"),
        t=0.8,
        u=0.01,
        u_raw=0.005,
        v=0.8,
        adata_ref_source_path=source,
    )

    reference_artifact = tmp_path / "out" / "demo.adata_ref_step2.h5ad"
    assert reference_artifact.is_symlink()
    assert reference_artifact.resolve() == source.resolve()
    assert not adata_ref.write_calls
    assert (tmp_path / "out" / "demo.bdata_step2.h5ad").exists()
    meta = json.loads((tmp_path / "out" / "demo.thresholds.json").read_text(encoding="utf-8"))
    assert meta["adata_ref_step2_mode"] == "symlink"


def test_save_identity_results_copies_reference_when_no_source_path_is_provided(tmp_path):
    bdata = WritableAnnData(n_obs=1)
    adata_ref = WritableAnnData(n_obs=3)
    index = ["c1"]

    save_identity_results(
        outdir=tmp_path / "out",
        prefix="demo",
        bdata=bdata,
        adata_ref=adata_ref,
        probs_ref_cal=_frame(["r1"]),
        probs_query_cal=_frame(index),
        mean_org=_frame(index),
        std_org=_frame(index),
        Hnorm=pd.Series([0.1], index=index, name="Hnorm"),
        t=0.8,
        u=0.01,
        u_raw=0.005,
        v=0.8,
    )

    reference_artifact = tmp_path / "out" / "demo.adata_ref_step2.h5ad"
    assert reference_artifact.exists()
    assert not reference_artifact.is_symlink()
    assert reference_artifact in adata_ref.write_calls
    meta = json.loads((tmp_path / "out" / "demo.thresholds.json").read_text(encoding="utf-8"))
    assert meta["adata_ref_step2_mode"] == "copy"
