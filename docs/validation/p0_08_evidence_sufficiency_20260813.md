# P0-08 Evidence Sufficiency candidate validation — 2026-08-13

## Biological question

The implementation asks whether immutable upstream evidence records for a declared ProductCase and domain can be folded through Data Readiness, Model Robustness and Prior Applicability without turning missing evidence into a biological failure or score.

## Data, references and controls

Validation uses synthetic JSON-only fixtures representing ProductCase/ProductDefinition pointers, MeasurementSpec, QCReadinessProfile, MeasurementResult, validation, prior-applicability and sensitivity records. It uses the packaged candidate gate rule and reason-code catalog. No expression matrix, real product, patient, private, locked, sealed or competitor data are used; no scRNA analysis is rerun.

Controls cover an adequate/frozen/applicable path, one-field perturbations for limited/insufficient/not-assessed states, deterministic and prior-not-required paths, required/supporting Evidence Family combinations, every raw MeasurementResult state, malformed/unbound/legacy inputs, full ProductCase/ProductDefinition pointer reconciliation, cross-bound assay/status/tool mismatches, ambiguous logical IDs, strict versionless-schema ref versions, recursive unsafe-reference screening, content/path/request/set-order invariance, same-directory reuse, input mutation and existing-bundle drift.

## Observed finding and product-evaluation meaning

Synthetic contract tests show the executor applies the fixed order Data Readiness → Model Robustness → Prior Applicability → sufficiency and keeps domains independent. Contract-complete missing records produce a successful `not_assessed` profile, with missing reasons separated from blocking reasons, while malformed, cross-bound, pointer-conflicting, ambiguous-ID, version-invalid, checksum-invalid or unsafe-reference inputs fail eligibility without a scientific result or output bundle. Unsafe checks include absolute paths, POSIX and Windows home-variable paths, embedded file URIs, credential-bearing URLs, credential assignments and token forms while preserving ordinary bridge/http scientific references. Public and direct-adapter v0.1 rejection uses the shared `tool_request_v2_required` code. Exact Evidence Family duplicates collapse; all distinct conflicting required representatives remain in provenance and are not voted or averaged. Different supporting records cannot improve, worsen or conflict with the required gate record. Negative, alert, unknown, missing and unavailable upstream MeasurementResults remain upstream provenance and do not become zero, product failure or a safety statement.

Reversing request-object order and every tested contract-declared set-like binding/reference list preserves the canonical input hash, run ID, result object and every reusable bundle byte, including when the second invocation targets the first invocation's output directory. Raw source-byte checksums remain invocation provenance in `ToolRunV2.request.object_inputs`; the bundle manifest uses per-object semantic checksums, and every returned artifact checksum verifies its file. A semantic validation change still changes the input hash and run ID. Ordered gate-rule precedence is not normalized away.

Even the synthetic sufficient path emits `domain_score=null`, `score_state=unavailable` and `p0_score_contract_unavailable`. This establishes deterministic engineering behavior only; it does not establish that any real domain or product has sufficient evidence.

## Engineering evidence

- Module tests: `PYTHONPATH=src .../.venv/bin/python -m pytest -q tests/test_p0_08_evidence_sufficiency.py` — 126 passed after two independent-review hardening passes.
- The tests validate model schemas, 45 scientific reason codes, candidate resources, axis/gate states, severity-separated missing/blocking/limiting fields, score-null behavior, supporting/required family reconciliation, full-pointer/logical-ID/cross-binding eligibility, strict schema/ref versions, recursive unsafe-reference rejection, artifacts, same-directory semantic set-order reuse, deterministic identity and fail-closed mutation/drift behavior.
- The committed example request intentionally uses placeholder absolute paths and checksums. Executable CLI/SDK tests construct temporary immutable fixtures and calculate real checksums.
- Full source suite after rebasing onto the reviewed shared runtime: 391 passed with three pre-existing scientific-library warnings.
- Schema export registered 33 public contracts in total, including all nine P0-08 contracts; every public Schema has a byte-identical packaged copy and validates under JSON Schema Draft 2020-12.
- A clean Python 3.12 environment installed the built wheel, discovered exactly 12 tools, loaded both packaged P0-08 rule resources, loaded all 33 packaged Schemas, validated the knowledge snapshot, and passed the same 105 CLI/SDK adapter tests against the installed wheel.
- Knowledge validation reported 354 methods, 396 bindings, no dangling method/source references and zero formal-eligible methods. Repository policy, Tool Card byte parity and `git diff --check` passed.

## Remaining uncertainty and next scientific action

`ENV-EVIDENCE-v0.1` remains proposed, all selected method records remain `formal_eligible=false`, and no real upstream evidence bundle has been reviewed through this candidate. Next scientific work is to review/freeze the relevant MeasurementSpec-side requirements and upstream validation/prior/sensitivity records, then run a reproducible real ProductCase only after explicit scientific authorization. This validation does not freeze a gate, ScoreContract, threshold or release state.
