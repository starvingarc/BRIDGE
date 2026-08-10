# Exact binomial / Clopper-Pearson

| Field | Value |
|---|---|
| Method ID | `METHOD-EXACT-BINOMIAL-CLOPPER-PEARSON` |
| Modules | P0-05 |
| Scientific status | candidate |
| Source status | `registered` |
| License status | `reported` |
| Version | `unresolved` (`not_frozen`) |
| Maintenance | `requires_live_review` |
| Primary paper | `unresolved` |
| Evidence family | count_interval |
| Retrieval policy | `registered_local_snapshot` |

## BRIDGE Use

off-target composition | rare-state detection

## Inputs

Observed count and eligible denominator | Observed count and fixed denominator

## Outputs

Exact interval and upper confidence bound | Exact interval and zero-count upper bound

## Boundaries

Does not model annotation or biological uncertainty | No biological or annotation uncertainty

## Environment

Python 单细胞核心环境

## Curation Notes

No method-specific correction is recorded in this snapshot.

## Official Sources

- [GitHub - scipy/scipy: SciPy library main repository · GitHub](https://github.com/scipy/scipy) (`SOURCE-23469E505384AA46`)
- [binomtest — SciPy v1.18.0 Manual](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.binomtest.html) (`SOURCE-3B346F128CE00FBC`)

Source verification records confirm provenance and accessibility only; they do not promote scientific status.
