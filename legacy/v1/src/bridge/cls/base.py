from __future__ import annotations

from bridge.common.results import CLSComponentResult
from bridge.io.component_outputs import save_component_outputs


def build_component_result(component: str, score_df, global_score, meta):
    return CLSComponentResult(
        component=component,
        score_df=score_df,
        global_score=float(global_score),
        meta=meta,
    )


def save_component_result(component_result, outdir: str, dataset_id: str, owner_adata=None, table_key: str = "batch_table"):
    payload = save_component_outputs(
        result=component_result,
        outdir=outdir,
        dataset_id=dataset_id,
        owner_adata=owner_adata,
        table_key=table_key,
    )
    return component_result.score_df, component_result.global_score, payload
