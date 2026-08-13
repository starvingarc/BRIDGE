# P0-09 Evidence Compiler & Reconciler validation record — 2026-08-13

## Biological question

Can already-computed, immutable product evidence be converted into atomic, versioned records and reconciled without conflating missing evidence with zero, correlated methods with independent support, or engineering success with a biological/product conclusion?

## Data, references and controls

This record uses synthetic ProductCase, MeasurementSpec, ToolRun, P0-08 EvidenceSufficiencyProfile, EvidenceFamily, Claim and ReconciliationSpec objects only. No patient, donor, laboratory, competitor, server-path, sealed or clinical data was used.

Controls include:

- identical rerun and set-like input-list reorder controls;
- create, unchanged, supersede and invalidate histories;
- required missing measurement and shadow-tier controls;
- failed sibling item, duplicate logical key, exact same-source external duplication, conflicting external content/source, boolean/numeric-string/nonfinite-value and bounded credential/path/public-ref canaries;
- same-family de-duplication, cross-family conflict, independent confirmation and integration-sensitive channel cases;
- Case and Comparison graphs, including dangling/mismatched source-manifest external provenance;
- content-addressed base/source manifests, exact source-input bijection, complete source history/effective lifecycle and request-binding non-leakage;
- exact ProductCase/MeasurementSpec/MeasurementResult/family/context/catalog-role binding and conservative P0-08 v0.1 formal refusal;
- normalized no-score conclusion keys and nearby scientific-field negative controls;
- JSON-to-Parquet-to-NetworkX reconstruction, basename/traversal/symlink/checksum/row-count/size boundaries, exact node-type counts, node/edge self-description hashes, unusable output paths and seven bounded read-only query surfaces.

Committed examples are documentation-only and contain placeholder paths/checksums. Executable tests generate temporary absolute paths and exact SHA-256 values at runtime.

## Actual observations

Focused command:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q tests/test_p0_09_evidence_compiler.py
```

Observed after this five-finding review fix set on Python 3.12.13 with the shared development environment's PyArrow 23.0.1 and NetworkX 3.6.1: `146 passed`.

Current source-tree observations:

- the complete source-tree suite passed: `836 passed, 3 warnings`;
- all 49 public Schemas were exported to source and packaged resources with byte parity, including the 16 P0-09 Schemas;
- the current P0-09 strict runtime annotations produce no generated-Schema byte drift; and
- repository policy passed, the full suite retained exactly 12 discoverable tools, and the packaged/public P0-09 Tool Card projections remain byte-identical; and
- knowledge validation remained valid with no dangling method/source refs and zero formally eligible methods.

A fresh Python 3.12.13 environment installed the wheel with the declared PyArrow 21.0.0 and NetworkX 3.5 dependencies. Its complete installed-wheel suite passed `836 passed, 3 warnings`; dependency consistency, 12-tool discovery, all 49 packaged Schemas, the installed P0-09 adapter/Card, knowledge validation and repository policy also passed. This review did not add or change a public field or generated Schema.

The synthetic executable cases observed:

- a valid synthetic Case request produced one immutable ten-file bundle and one atomic shadow EvidenceRecord; because P0-08 v0.1 cannot prove ProductCase/MeasurementSpec versions, no tested request was promoted to eligible formal reconciliation;
- a missing orthogonal channel produced an open EvidenceRequirement with no zero-valued EvidenceRecord and an `insufficient_evidence` reconciliation with null state/direction;
- shadow evidence remained in records/graph but was excluded from formal reconciliation;
- one invalid sibling produced `partial`, kept the valid record, and exposed only ID/index/reason metadata for the rejected item;
- Schema-valid candidate/missing items with record-level unsafe or prohibited conclusion content were isolated without echo; non-object/Schema-invalid public record arrays and unsafe top-level bundle/registry surfaces failed without publication;
- changed logical content appended versions through `supersedes` and `invalidates`; prior EvidenceRequirement identity/content tampering failed and a same-state content change appended N+1; previous JSON records remained byte-identical;
- set-like raw JSON reorder and request/output-path changes retained semantic run/object identity and reproducible bundle bytes;
- an exactly repeated, Schema-valid same-source external Evidence ref collapsed idempotently before input identity and graph construction, producing the same run ID, input hash and artifact bytes as the singleton request; the same logical ref with different content or source retained the existing sanitized `duplicate_logical_key_conflict` behavior;
- Comparison output used a distinct comparison manifest and property-free external EvidenceRecord nodes; request-side input IDs were absent from public manifests. Source roles had to form an exact input-ID bijection, and each source manifest's real directory, five authoritative artifacts, raw manifest/record-set checksums, deterministic graph ID, graph/version/ProductCase and complete EvidenceRecord history were verified before use;
- forged evidence refs/content hashes/wrong source Claims and conflicting evidence identity/content across source graphs were sanitized as partial failures and did not enter graph facts; external lifecycle was derived from the full source revision chain rather than trusted from an old record;
- direct reconciliation-unit controls showed that same-scope and one-way/transitively dependency-connected families count as one independent component, while dependency-free cross-scope families remain independent. End-to-end formal resolution remained unavailable by the conservative P0-08 v0.1 version-binding rule;
- every public P0-09 model generated a valid Draft 2020-12 Schema;
- manifest opening rejected traversal/absolute filenames, symlinks, checksum/row-count drift, exact node-type-count substitution, forged node IDs, forged edge IDs/self-hashes, owned-property content-hash drift, disconnected graphs and JSON-fact/Parquet disagreement; base/source preflight inherited the same checks while property-free external nodes remained source-bound rather than being required to expose copied properties;
- candidate numerator/denominator/interval fields rejected numeric strings and booleans without coercion, and direct/public JSON paths rejected NaN/Infinity; valid integer and floating-point JSON numbers remained accepted;
- an output path already occupied by a regular file returned a typed failed run with null result and no artifacts while preserving the existing file;
- all seven query methods enforced explicit type/enum/bool and cap rules through typed `query_parameter_invalid`, remained read-only, selected only the latest EvidenceRequirement version, and did not falsely report truncation at an exact cap; query calls did not change artifact checksums.

## Product-evidence meaning

These observations support the engineering claim that the candidate module can preserve evidence identity, provenance, missingness, tier, lifecycle and family independence across a deterministic graph bundle. They also show that scientific insufficiency is represented explicitly rather than converted into a product failure or numeric placeholder.

## What remains unanswered

This validation does not establish that any biological Claim is true, that any current ProductCase has sufficient evidence, that any domain score exists, that an EvidenceFamily assignment is scientifically correct, or that any output is suitable for public/scientific release. It does not validate LadybugDB, production-scale performance or the proposed evidence environment. The committed branch intentionally does not promote any method to `formal_eligible`.

The focused and full development runs used PyArrow/NetworkX versions newer than the declared release environment; the separate clean-wheel run verified this exact review diff with the declared PyArrow 21.0.0 and NetworkX 3.5 environment. Independent review resolution and Draft PR publication remain outstanding, and neither step authorizes scientific promotion or merge.

## Engineering artifacts and reproducibility

Module implementation:

- `src/bridge/tool_packages/p0_09_evidence_compiler/`
- `src/bridge/tool_packages/specs/p0_09.yaml`
- byte-identical packaged/public P0-09 Tool Card projections
- `tests/test_p0_09_evidence_compiler.py` and synthetic fixtures under `tests/fixtures/p0_09/`
- documentation-only request `examples/requests/p0_09_evidence_compiler.json`

The focused suite verifies fixed Parquet columns, canonical JSON, strict scientific numeric parsing, semantic object hashes, stable IDs, immutable staging/publication, content-addressed source/base graph reconstruction, authoritative artifact checksums, self-describing graph rows and deterministic query ordering. Current source/package Schema bytes remain unchanged. The clean-wheel installation independently verified installed adapter/Card/knowledge discovery, repository policy and dependency consistency against this exact working tree.
