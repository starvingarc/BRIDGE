"""Identity assessment package."""

from bridge.identity.adapters import write_identity_outputs_to_obs
from bridge.identity.api import assess_identity_probabilities, build_identity_summary, identify
from bridge.identity.calibration import (
    apply_calibrators,
    calibrate_probs,
    fit_isotonic_per_class,
)
from bridge.identity.results import (
    IdentityResult,
    IdentityProbabilities,
    IdentitySelectionResult,
    IdentityThresholds,
    IdentityUncertainty,
)
from bridge.identity.selection import (
    calibrate_threshold_from_ref,
    compute_candidate_mask,
    estimate_u_from_std,
)
from bridge.identity.serialization import save_identity_results
from bridge.identity.uncertainty import (
    approx_std_from_p,
    ensemble_mean_std,
    predictive_entropy_norm,
    run_query_ensemble,
)

__all__ = [
    "IdentityResult",
    "IdentityProbabilities",
    "IdentitySelectionResult",
    "IdentityThresholds",
    "IdentityUncertainty",
    "apply_calibrators",
    "build_identity_summary",
    "approx_std_from_p",
    "calibrate_probs",
    "calibrate_threshold_from_ref",
    "compute_candidate_mask",
    "ensemble_mean_std",
    "estimate_u_from_std",
    "fit_isotonic_per_class",
    "identify",
    "predictive_entropy_norm",
    "assess_identity_probabilities",
    "run_query_ensemble",
    "save_identity_results",
    "write_identity_outputs_to_obs",
]
