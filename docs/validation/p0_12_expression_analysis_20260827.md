# P0-12 expression-analysis validation — 2026-08-27

## Scope

This record verifies that the public P0-12 adapter can read a declared H5AD and
execute the selected deterministic analysis chain. It does not validate a
biological vocabulary, reference panel, marker program or release threshold.

## Fixture and controls

The executable fixture is fully synthetic: eight cells, five genes, two samples
and two graft labels. It provides a raw-count layer, two externally declared
state-probability columns, a versioned reference profile and a versioned marker
program. All five JSON inputs and the H5AD carry SHA-256 bindings.

Controls cover:

- compatibility with the existing no-input and three-object modes;
- missing declared observation fields;
- H5AD checksum replacement;
- negative raw counts;
- probabilities outside the declared tolerance;
- exact object, case, assay, reference, program and method bindings;
- deterministic reruns and immutable publication.

## Observed behavior

The expression request passes the same registry, CLI and adapter seam used by
other P0 tools. Scanpy reads the H5AD. Raw counts are summed by sample, then
normalized and log-transformed before pseudobulk reference correlation and
marker-program evidence. Cell probabilities are averaged within sample before
case-level composition and sample bootstrap intervals are calculated.

The successful result reports two samples and two grafts, exact source
bindings, the eight selected method IDs, runtime versions and checksummed JSON
artifacts. Repeated identical input produces the same run and result. Invalid
counts or probabilities fail without publication; changed H5AD bytes and
missing metadata are rejected during eligibility.

## Engineering evidence

- P0-12, CLI and registry focused suite: 48 passed.
- Repository-wide suite: 1236 passed; one pre-existing duplicate-gene warning.
- Public Schema registry: 102 packaged Schemas, including the P0-12 union result
  and five expression-analysis object contracts.
- Public tool discovery remains 12 packages.
- The request example contains documentation placeholders only; no expression
  data or private metadata is committed.

## Scientific boundary

The run proves that the declared calculations execute through the published
interface. External state probabilities are not independently reclassified.
Reference correlation and marker-program means are descriptive evidence, not
cell identity, maturation truth, efficacy, safety, potency or release evidence.
Every provided result remains `candidate/shadow`,
`domain_score=null`, `score_state=unavailable` and
`pretransplant_evidence_effect=none`.
