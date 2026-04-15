from __future__ import annotations


def write_identity_outputs_to_obs(bdata, target_class, mean_org, std_org, Hnorm, is_candidate, probs_query_cal=None):
    bdata.obs[f"is_candidate_{target_class}"] = is_candidate.reindex(bdata.obs_names).fillna(False).values
    bdata.obs[f"p_mean_{target_class}"] = mean_org[target_class].reindex(bdata.obs_names).astype(float).values
    bdata.obs[f"p_std_{target_class}"] = std_org[target_class].reindex(bdata.obs_names).astype(float).values
    bdata.obs["Hnorm"] = Hnorm.reindex(bdata.obs_names).astype(float).values
    if probs_query_cal is not None:
        bdata.obs[f"p_cal_{target_class}"] = probs_query_cal[target_class].reindex(bdata.obs_names).astype(float).values
    print(f"[identity_assessment] Wrote bdata.obs outputs for {target_class}")
