# Interface Examples

The request files demonstrate the stable JSON shape used by the Python SDK and `bridge-tool` CLI. Paths are placeholders and must be replaced with real absolute paths before validation or execution.

- `requests/p0_01_count_ready.json`: executable count-level input audit and QC.
- `requests/p0_01_analysis_ready.json`: structure-only audit of normalized expression.
- `requests/p0_02_cell_state.json`: executable shadow Cell-State Evidence request. The deployment must resolve its `qc_profile_ref` and the frozen reference snapshot.
- `requests/p0_08_evidence_sufficiency.json`: structured P0-08 candidate request shape. Every path and checksum is a placeholder; create immutable local JSON objects and calculate their real SHA-256 values before `validate` or `run`. The packaged candidate gate-rule bytes must be used unchanged.
- `requests/p0_09_evidence_compiler.json`: structured P0-09 candidate request shape for a compilation bundle, P0-08 profiles and versioned Evidence Family, Claim and reconciliation registries. Placeholder paths and checksums must be replaced with immutable local JSON objects and their real SHA-256 values.
- `requests/p0_12_graft_assessment.json`: structured P0-12 request for one versioned graft rule object and one precomputed independent-unit evidence bundle. It does not invoke expression analysis; replace all paths and checksums before validation.

## Synthetic scRNA Upload Demo

`demo-data/scrna-upload-v0.1/` mimics files a user may upload for Agent
integration testing. The expression values, cells, samples, captures, batches,
preparations and timepoint are fully synthetic. Public human gene symbols are
used only as feature identifiers.

| File | Purpose | SHA-256 |
|---|---|---|
| `demo-data/scrna-upload-v0.1/demo_scrna.h5ad` | 2,048-cell by 10,000-gene scRNA object with log-normalized `X`, integer `layers/counts` and synthetic `obs` metadata | `984f74f7a4118da1c898e593a0d93b536aee092bcda5dbf76d10fc65addd5a91` |
| `demo-data/scrna-upload-v0.1/sample_metadata.csv` | Four-row capture-level companion metadata | `81c15f855da1c83ee58d0a5711d5afe1d0e52c78362f514604864d5aa194c93a` |

- Source class: `fully_synthetic`.
- Intended tests: upload handling, metadata hand-off and Agent integration.
- Not validated here: P0 execution, biological state recovery, scoring or any
  scientific, product-quality or clinical interpretation.
