# Interface Examples

The request files demonstrate the stable JSON shape used by the Python SDK and `bridge-tool` CLI. Paths are placeholders and must be replaced with real absolute paths before validation or execution.

- `requests/p0_01_count_ready.json`: executable count-level input audit and QC.
- `requests/p0_01_analysis_ready.json`: structure-only audit of normalized expression.
- `requests/p0_02_cell_state.json`: executable shadow Cell-State Evidence request. The deployment must resolve its `qc_profile_ref` and the frozen reference snapshot.
- `requests/p0_03_target_regional_evidence.json`: seven-input configurable target/regional request, including the exact ProductCase-bound `BiologicalUnitManifest`.
- `requests/p0_04_developmental_compatibility.json`: seven-input static developmental request with StateRoleMap, DevelopmentWindowSpec and exact biological-unit lineage.
- `requests/p0_05_off_target_control.json`: seven-input configurable product-role request with exact StateRoleMap and biological-unit lineage.
- `requests/p0_06_proliferation_stress_response.json`: seven-input program-evidence request; reviewed/frozen independence groups, not cells or captures, are the repeat unit.
- `requests/p0_07_product_comparison.json`: pairwise request with two ProductCases, two full P0-08 run results and two exact BiologicalUnitManifests.
- `requests/p0_08_evidence_sufficiency.json`: structured P0-08 candidate request with an exact checksummed v0.2 MeasurementResult. The packaged candidate gate-rule bytes must be used unchanged.
- `requests/p0_09_evidence_compiler.json`: compilation request with a full P0-08 result, exact v0.2 MeasurementResult and versioned Evidence Family, Claim and reconciliation registries; the candidate bundle does not restate numeric evidence.
- `requests/p0_10_claim_verifier.json`: four-input claim-verification request bound to a P0-09 graph manifest, policy and statement registry.
- `requests/p0_11_internal_review_projection.json`: four-input internal-review request bound to the exact P0-10 result and producing ToolRun; it never authorizes public distribution.
- `requests/p0_12_graft_assessment.json`: provided-graft request with separate graft MeasurementSpec, exact lineage manifest, assessment spec and precomputed evidence bundle; it does not invoke expression analysis.

Except for the runnable P0-01/P0-02 examples described above, structured
object paths and checksums are documentation placeholders. Replace them with
immutable local objects and exact SHA-256 values before validation or execution.

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
