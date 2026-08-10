# pertpy scCODA

| Field | Value |
|---|---|
| Method ID | `METHOD-PERTPY-SCCODA` |
| Modules | P0-04, P0-05, P0-07 |
| Scientific status | benchmark, conditional |
| Source status | `registered` |
| License status | `review_required` |
| Version | `unresolved` (`not_frozen`) |
| Maintenance | `requires_live_review` |
| Primary paper | `unresolved` |
| Evidence family | replicated_composition |
| Retrieval policy | `registered_local_snapshot` |

## BRIDGE Use

composition comparison | off-target composition | time-course

## Inputs

Cell-type counts, unique statistical sample IDs and covariates | Independent sample-level category counts | Independent sample-level counts and reference category

## Outputs

Bayesian compositional effects | posterior effects, credible effects and reference sensitivity

## Boundaries

 | Effects are relative to the selected reference category | Legacy scCODA package is unmaintained; freeze current implementation

## Environment

R/Bioconductor 方法环境；工具专用隔离环境 | 工具专用隔离环境

## Curation Notes

The retired API path was replaced by the current pertpy API path.

## Official Sources

- [GitHub - scverse/pertpy: Single-cell perturbation analysis · GitHub](https://github.com/scverse/pertpy) (`SOURCE-68EC3C0E888D586C`)
- [scCODA - Compositional analysis of labeled single-cell data — pertpy](https://pertpy.readthedocs.io/en/latest/tutorials/notebooks/sccoda.html) (`SOURCE-7F8C39EE4270B805`)
- [pertpy.tools.Sccoda — pertpy](https://pertpy.readthedocs.io/en/latest/api/tools/pertpy.tools.Sccoda.html) (`SOURCE-BCFFA3217B7434A7`)

Source verification records confirm provenance and accessibility only; they do not promote scientific status.
