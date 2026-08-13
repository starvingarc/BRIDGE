# Interface Examples

The request files demonstrate the stable JSON shape used by the Python SDK and `bridge-tool` CLI. Paths are placeholders and must be replaced with real absolute paths before validation or execution.

- `requests/p0_01_count_ready.json`: executable count-level input audit and QC.
- `requests/p0_01_analysis_ready.json`: structure-only audit of normalized expression.
- `requests/p0_02_cell_state.json`: executable shadow Cell-State Evidence request. The deployment must resolve its `qc_profile_ref` and the frozen reference snapshot.
- `requests/p0_08_evidence_sufficiency.json`: structured P0-08 candidate request shape. Every path and checksum is a placeholder; create immutable local JSON objects and calculate their real SHA-256 values before `validate` or `run`. The packaged candidate gate-rule bytes must be used unchanged.
