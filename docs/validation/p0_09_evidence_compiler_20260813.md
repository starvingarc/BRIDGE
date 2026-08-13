# P0-09 Evidence Compiler & Reconciler validation record — 2026-08-13

## Biological question

Can already-computed, immutable product evidence be converted into atomic, versioned records and reconciled without conflating missing evidence with zero, correlated methods with independent support, or engineering success with a biological/product conclusion?

## Data, references and controls

This record uses synthetic ProductCase, MeasurementSpec, ToolRun, P0-08 EvidenceSufficiencyProfile, EvidenceFamily, Claim and ReconciliationSpec objects only. No patient, donor, laboratory, competitor, server-path, sealed or clinical data was used.

Controls include:

- identical rerun and set-like input-list reorder controls;
- create, unchanged, supersede and invalidate histories;
- required missing measurement and shadow-tier controls;
- failed sibling item, duplicate logical key, boolean-value and bounded credential/path/public-ref canaries;
- same-family de-duplication, cross-family conflict, independent confirmation and integration-sensitive channel cases;
- Case and Comparison graphs, including dangling/mismatched source-manifest external provenance;
- JSON-to-Parquet-to-NetworkX reconstruction, basename/traversal/symlink/checksum/row-count/size manifest boundaries and seven bounded read-only query surfaces.

Committed examples are documentation-only and contain placeholder paths/checksums. Executable tests generate temporary absolute paths and exact SHA-256 values at runtime.

## Actual observations

Focused command:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q tests/test_p0_09_evidence_compiler.py
```

Observed locally on Python 3.12.13 with the shared development environment's PyArrow 23.0.1 and NetworkX 3.6.1: `75 passed`.

Repository integration observations:

- the complete source-tree suite passed: `765 passed, 3 warnings`;
- a clean wheel environment on Python 3.12.13 with the declared PyArrow 21.0.0 and NetworkX 3.5 dependencies also passed: `765 passed, 3 warnings`;
- all 49 public Schemas were exported to source and packaged resources with byte parity, including the 16 P0-09 Schemas;
- knowledge validation reported no dangling references and zero formally publishable methods;
- repository policy passed with exactly 12 discoverable tools;
- the installed wheel exposed the P0-09 adapter and byte-identical Tool Card, all 49 Schemas and the packaged knowledge snapshot; and
- the clean wheel environment passed dependency consistency checks.

The synthetic executable cases observed:

- a valid Case request produced one immutable ten-file bundle, one atomic EvidenceRecord, a satisfied requirement and an eligible stable reconciliation;
- a missing orthogonal channel produced an open EvidenceRequirement with no zero-valued EvidenceRecord and an `insufficient_evidence` reconciliation with null state/direction;
- shadow evidence remained in records/graph but was excluded from formal reconciliation;
- one invalid sibling produced `partial`, kept the valid record, and exposed only ID/index/reason metadata for the rejected item;
- unsafe candidate, missing, or Comparison external items were isolated without echo; unsafe top-level bundle/profile/registry surfaces failed without publication;
- changed logical content appended versions through `supersedes` and `invalidates`; prior EvidenceRequirement identity/content tampering failed and a same-state content change appended N+1; previous JSON records remained byte-identical;
- set-like raw JSON reorder and request/output-path changes retained semantic run/object identity and reproducible bundle bytes;
- Comparison output used a distinct comparison manifest and property-free external EvidenceRecord nodes; source manifest SHA/graph/version/ProductCase mismatches and dangling external provenance were rejected or failed manifest reconstruction and did not enter graph facts;
- integration-channel disagreement emitted `integration_sensitive`; primary conflict was resolved only by an independent confirmation family;
- every public P0-09 model generated a valid Draft 2020-12 Schema;
- manifest opening rejected traversal/absolute filenames, symlinks and row-count drift; artifact byte sizes matched the manifest;
- all seven query methods enforced graph kind, parameter/cap rules and read-only behavior, and exact-cap results did not falsely report truncation; query calls did not change artifact checksums.

## Product-evidence meaning

These observations support the engineering claim that the candidate module can preserve evidence identity, provenance, missingness, tier, lifecycle and family independence across a deterministic graph bundle. They also show that scientific insufficiency is represented explicitly rather than converted into a product failure or numeric placeholder.

## What remains unanswered

This validation does not establish that any biological Claim is true, that any current ProductCase has sufficient evidence, that any domain score exists, that an EvidenceFamily assignment is scientifically correct, or that any output is suitable for public/scientific release. It does not validate LadybugDB, production-scale performance or the proposed evidence environment. The committed branch intentionally does not promote any method to `formal_eligible`.

The focused development run used PyArrow/NetworkX versions newer than the declared release environment; the separate clean-wheel run verified the declared PyArrow 21.0.0 and NetworkX 3.5 environment. Repository integration, generated Schema registration, packaging, adapter discovery, knowledge projection and full source/wheel gates are complete. Independent review and Draft PR publication remain outstanding, and neither step is authorized to promote the candidate scientifically or merge it.

## Engineering artifacts and reproducibility

Module implementation:

- `src/bridge/tool_packages/p0_09_evidence_compiler/`
- `src/bridge/tool_packages/specs/p0_09.yaml`
- byte-identical packaged/public P0-09 Tool Card projections
- `tests/test_p0_09_evidence_compiler.py` and synthetic fixtures under `tests/fixtures/p0_09/`
- documentation-only request `examples/requests/p0_09_evidence_compiler.json`

The test suite verifies fixed Parquet columns, canonical JSON, semantic object hashes, stable IDs, immutable staging/publication, authoritative artifact checksums and deterministic query ordering. The central integration run additionally verified source/package Schema parity, a clean wheel installation, installed adapter/Card/knowledge discovery, repository policy and dependency consistency.
