from __future__ import annotations

import json
import os

from bridge.common.results import CLSComponentResult


def save_component_outputs(
    result: CLSComponentResult,
    outdir: str,
    dataset_id: str,
    owner_adata=None,
    table_key: str = "batch_table",
):
    save_dir = os.path.join(outdir, dataset_id, result.component)
    os.makedirs(save_dir, exist_ok=True)

    table_path = os.path.join(save_dir, f"component_{result.component}_batch.csv")
    result.score_df.to_csv(table_path, index=False)

    payload = result.to_payload(dataset_id=dataset_id)
    json_path = os.path.join(save_dir, f"component_{result.component}_global.json")
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)

    if owner_adata is not None:
        owner_adata.uns.setdefault("CLS", {})
        owner_adata.uns["CLS"][result.component] = payload
        owner_adata.uns["CLS"][result.component][table_key] = result.score_df

    return payload
