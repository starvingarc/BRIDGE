from __future__ import annotations

from bridge.identity.results import IdentityThresholds, IdentityUncertainty
from bridge.identity.selection import calibrate_threshold_from_ref, estimate_u_from_std, select_target_candidates
from bridge.identity.uncertainty import ensemble_mean_std, predictive_entropy_norm


def run_identity_assessment(
    probs_ref_cal,
    probs_query_cal,
    probs_query_ensemble,
    y_ref_series,
    target_class: str,
    entropy_source=None,
    target_precision: float = 0.8,
    std_quantile: float = 75.0,
    u_min: float = 0.005,
    entropy_threshold: float = 0.8,
    obs_index=None,
):
    mean_org, std_org = ensemble_mean_std(probs_query_ensemble)
    entropy_source = probs_query_cal if entropy_source is None else entropy_source
    entropy_norm = predictive_entropy_norm(entropy_source)
    threshold_t = calibrate_threshold_from_ref(
        probs_ref_cal[target_class],
        y_ref_series,
        target_class=target_class,
        target_precision=target_precision,
    )
    threshold_u, u_raw = estimate_u_from_std(std_org[target_class], q=std_quantile, u_min=u_min)
    thresholds = IdentityThresholds(
        threshold_t=threshold_t,
        threshold_u=threshold_u,
        threshold_v=entropy_threshold,
        u_raw=u_raw,
        target_precision=target_precision,
    )
    uncertainty = IdentityUncertainty(
        mean_prob=mean_org,
        std_prob=std_org,
        entropy_norm=entropy_norm,
        ensemble_size=len(probs_query_ensemble),
        seed_base=0,
    )
    selection = select_target_candidates(
        mean_org=mean_org,
        std_org=std_org,
        entropy_norm=entropy_norm,
        target_class=target_class,
        thresholds=thresholds,
        obs_index=mean_org.index if obs_index is None else obs_index,
    )
    return uncertainty, selection
