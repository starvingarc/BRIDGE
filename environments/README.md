# Conda Environment Contracts

| EnvironmentSpec | Conda name | State | Used by |
|---|---|---|---|
| `ENV-P0-CORE-v0.1` | `bridge-p0-core` | health_check_passed | Tool Runtime and P0-01–P0-07, P0-12 core execution |
| `ENV-EVIDENCE-v0.1` | `bridge-p0-evidence` | health_check_passed | P0-08 to P0-11 deterministic evidence and release services |
| `ENV-CELLSTATE-PY-v0.1` | `bridge-cellstate-py` | health_check_passed | P0-02 Python benchmarks and optional P0-03 expression methods |
| `ENV-CELLSTATE-BIOC-R46-v0.1` | `bridge-cellstate-bioc-r46` | health_check_passed | P0-02 R/Bioconductor benchmark methods |

Create these environments with strict channel priority. After creating the R environment, install Harmony and Symphony from the recorded commits without dependency upgrades:

```bash
CONDA_CHANNEL_PRIORITY=strict conda env create --file environments/bridge-cellstate-py.yml
CONDA_CHANNEL_PRIORITY=strict conda env create --file environments/bridge-cellstate-bioc-r46.yml
conda run --name bridge-cellstate-bioc-r46 Rscript environments/install-cellstate-bioc-r46.R
```

Keep Symphony in `bridge-cellstate-bioc-r46` unless a reproducible health check establishes a dependency conflict. Other scientific method-specific JAX, mixed-species and competitor environments remain conditional and require separate versioned specifications.

The core and cell-state environment validation is recorded in [Server
reproducibility validation, 2026-08-12](../docs/validation/server_reproducibility_20260812.md).
The evidence environment validation is recorded with the [P0-10 candidate](../docs/validation/p0_10_claim_verifier_20260814.md).

No environment installation implies scientific validation or method promotion.
