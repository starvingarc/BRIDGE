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
group, source bundles, analysis-unit labels and SHA-256. Outputs include method
and package provenance plus typed `available` or `not_assessed` states.

## Verification

- focused P0-07 and registry suite: **26 passed**;
- complete repository suite: **1,229 passed**, with eight pre-existing dependency warnings;
- wheel-only P0-07 method smoke: **3 passed**;
- installed module resolved from the unpacked wheel, outside the source tree;
- installed P0-07 exposed version `0.3.0`, eight registered method references and two input modes;
- tool discovery: exactly **12** packages;
- public Schema registry: **99** entries, including three new P0-07 method contracts;
- wheel SHA-256: `58b79dcbbc4190fcff8499f06e218244790b201fe328cd1419e434979b1889bd`;
- knowledge snapshot: valid, no dangling method/source references, zero formal-eligible methods;
- generated Schema/Card checks and `git diff --check`: passed.

## Retained boundaries

The runtime does not execute the registered R/Bioconductor, Bayesian,
mixed-model, differential-abundance or integration candidates. It produces no
p-values, confidence intervals, equivalence, winner, Pareto, ranking, safety,
efficacy or release conclusion. Distance and direction are descriptive and have
no intrinsic biological desirability.
