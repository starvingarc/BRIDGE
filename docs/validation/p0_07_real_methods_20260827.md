# P0-07 real comparison methods validation (2026-08-27)

- Branch: `p0-07-real-method-runtime`
- Integration base: `d749e8b3a05ffe9c4461312e8eb01b3fd32eb492`
- Package: `P0-07 0.3.0`
- Runtime: Ubuntu, Python 3.12, `ENV-P0-CORE-v0.1`
- Scientific state: `candidate/shadow`; `domain_score=null`

## Implemented scope

The existing comparability/confounding gate and descriptive profile remain
backward compatible. A second checksummed input mode now dispatches five methods
selected from the P0-07 registry:

| Method ID | Executed implementation | Recorded estimate |
|---|---|---|
| `CMP-EFFECT` | BRIDGE independent-sample Hedges-g engine | raw delta, `hedges_g` |
| `CMP-JS` | `scipy.spatial.distance.jensenshannon` | `jensen_shannon_distance` |
| `CMP-CORR` | `scipy.stats.spearmanr` | `spearman_rho` |
| `CMP-WASS-1D` | `scipy.stats.wasserstein_distance` | `wasserstein_distance` |
| `STAB-CV` | NumPy CV and median absolute-deviation ratio | within-group dispersion |

The method input binds every series to the comparison manifest, metric contract,
group, source bundles, analysis-unit labels and SHA-256. Sample-level series
must cover the complete manifest group exactly once and equal the cited bundle
metrics. Method execution inherits the shared comparability and source-evidence
gates. Jensen-Shannon uses a base greater than one; only Wasserstein series accept
weights; STAB-CV requires an explicit ratio scale. Outputs include method and
package provenance plus typed `available` or `not_assessed` states.

## Verification

The focused P0-07 suite covers deterministic execution plus these closure
adversaries:

- reference/OOD comparability blocks every numeric method record;
- alert and missing source evidence propagate to typed `not_assessed`;
- omitted and duplicate source bundles are refused for sample-value series;
- Jensen-Shannon bases at or below one fail schema validation, and non-finite
  library output becomes typed `not_assessed`;
- non-Wasserstein weights are refused;
- ratio-scale zero observations remain executable when the CV and MAD-ratio
  denominators are defined, while non-ratio inputs are `not_assessed`.

Schema export is checked for idempotence. Repository policy, Tool Card
validation, privacy/path scans and `git diff --check` are run from the isolated
server worktree. Exact commit and tree identifiers belong in the PR evidence,
not this long-lived document.

## Retained boundaries

The runtime does not execute the registered R/Bioconductor, Bayesian,
mixed-model, differential-abundance or integration candidates. It produces no
p-values, confidence intervals, equivalence, winner, Pareto, ranking, safety,
efficacy or release conclusion. Distance and direction are descriptive and have
no intrinsic biological desirability.
