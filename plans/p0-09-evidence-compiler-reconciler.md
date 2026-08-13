# P0-09 Evidence Compiler & Reconciler

## Biological question

Can BRIDGE preserve accepted domain evidence, explicit missing requirements, conflicts and source lineage as a deterministic ProductCase or Comparison graph without changing upstream measurements or turning engineering compilation into a scientific claim?

## Data and controls

- Tool ID: `P0-09`; package version: `0.2.0`.
- Request/run envelopes: `bridge://schemas/tool-request/v0.2` and `bridge://schemas/tool-run/v0.2`.
- Result: `bridge://schemas/evidence-compiler-run-result/v0.1`.
- Adapter: `bridge.tool_packages.p0_09_evidence_compiler.adapter:adapter`.
- Required inputs are one compilation bundle, one Evidence Family registry, one Claim registry, one reconciliation registry and the referenced P0-08 sufficiency profiles. Case append additionally requires the content-addressed base manifest/record/requirement sets; Comparison requires one content-addressed Case manifest/record set pair per bound source graph.
- Every input is a local immutable JSON object bound by role, public Schema, object version and SHA-256.
- Fixtures are synthetic. No private, locked, sealed, competitor or real ProductCase data are opened.

## Current observation

The candidate deterministically emits normalized evidence, requirement and reconciliation JSON; fixed-column Parquet nodes and edges; a Case or Comparison manifest; a Cytoscape projection; a rejected-record list; a typed result and an artifact manifest. NetworkX reconstructs every current/base/source graph and verifies graph/query/fact-set invariants. Missing observations become `EvidenceRequirement` objects, never zero-valued records. Schema-valid semantic sibling failures are excluded from a partial graph; malformed top-level inputs publish nothing. P0-08 v0.1 cannot prove ProductCase/MeasurementSpec versions, so formal evidence is conservatively refused rather than promoted.

## Meaning for product evaluation

The output can make evidence lineage, gaps and conflicts inspectable without allowing tool count, missing values or shadow evidence to decide a product conclusion. It does not establish that a Claim is true, that an Evidence Family assignment is biologically correct, or that any domain is formally assessable.

## Scope and non-goals

- Keep JSON and Parquet as authoritative facts; NetworkX is reconstruction and bounded-query support only.
- Support append-only create, supersede and invalidate transitions with stable logical keys and content hashes.
- Expose exactly seven named read-only query helpers; do not accept arbitrary Cypher, predicates or writes.
- Keep LadybugDB as deferred reconstructable shadow work.
- Emit no `MeasurementResult`, domain score, total score, grade, pass/fail, potency, safety, efficacy, GMP-release, clinical or absolute-ranking claim.
- Do not implement P0-10 Claim Verifier or P0-11 public-safe export.

## Delivery checklist

- [x] Implement module-local models, compiler, reconciler, graph projection, adapter and bounded queries.
- [x] Add detailed Tool Card, example request, scientific task card and reproducible validation record.
- [x] Re-export the post-review public P0-09 Schemas and verify packaged byte parity.
- [x] Recheck adapter/result-schema registration, explicit evidence dependencies, knowledge projection and repository-wide documentation against the frozen post-review contract.
- [x] Rerun the 2026-08-14 focused/full-source, discovery, knowledge, repository-policy, Schema/Card parity and diff gates after the final hardening review; the focused suite passes 168 tests and the full source suite passes 858 tests with three known warnings.
- [ ] Rebuild and install the wheel from the exact final tree, then repeat the installed-runtime gates with declared evidence dependencies.
- [ ] Complete independent review with no unresolved Critical or Important findings.
- [ ] Push one topic branch and open a Draft stacked PR; do not merge.

## Remaining scientific work

Before real-case use, reviewers must freeze the applicable ProductDefinition, Claims, Evidence Family membership and reconciliation rules; verify P0-08 profile applicability; and authorize the exact Case or Comparison bundle. A compiled graph cannot repair invalid upstream evidence or substitute for Claim verification.
