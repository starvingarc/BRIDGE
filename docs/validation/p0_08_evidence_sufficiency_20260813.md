# P0-08 Evidence Sufficiency candidate validation — 2026-08-13

## Biological question

The implementation asks whether immutable upstream evidence records for a declared ProductCase and domain can be folded through Data Readiness, Model Robustness and Prior Applicability without turning missing evidence into a biological failure or score.

## Data, references and controls

Validation uses synthetic JSON-only fixtures representing ProductCase/ProductDefinition pointers, MeasurementSpec, QCReadinessProfile, MeasurementResult, validation, prior-applicability and sensitivity records. It uses the packaged candidate gate rule and reason-code catalog. No expression matrix, real product, patient, private, locked, sealed or competitor data are used; no scRNA analysis is rerun.

Controls cover an adequate/frozen/applicable path, one-field perturbations for limited/insufficient/not-assessed states, deterministic and prior-not-required paths, same-family duplicates/conflicts, every raw MeasurementResult state, malformed/unbound/legacy inputs, content/path/request-order invariance, input mutation and existing-bundle drift.

## Observed finding and product-evaluation meaning

Synthetic contract tests show the executor applies the fixed order Data Readiness → Model Robustness → Prior Applicability → sufficiency and keeps domains independent. Contract-complete missing records produce a successful `not_assessed` profile, while malformed or checksum-invalid inputs fail eligibility without a scientific result. Exact Evidence Family duplicates collapse; conflicting required records are not voted or averaged. Negative, alert, unknown, missing and unavailable upstream MeasurementResults remain upstream provenance and do not become zero, product failure or a safety statement.

Even the synthetic sufficient path emits `domain_score=null`, `score_state=unavailable` and `p0_score_contract_unavailable`. This establishes deterministic engineering behavior only; it does not establish that any real domain or product has sufficient evidence.

## Engineering evidence

- Module tests: `PYTHONPATH=src .../.venv/bin/python -m pytest -q tests/test_p0_08_evidence_sufficiency.py` — 56 passed before final documentation/integration sync.
- The tests validate model schemas, 45 reason codes, candidate resources, axis/gate states, score-null behavior, family reconciliation, artifacts, deterministic reuse and fail-closed mutation/drift behavior.
- The committed example request intentionally uses placeholder absolute paths and checksums. Executable CLI/SDK tests construct temporary immutable fixtures and calculate real checksums.
- Full repository, wheel, schema-projection, knowledge, CLI/SDK and policy results are recorded by the integrating PR after central schema/packaging registration.

## Remaining uncertainty and next scientific action

`ENV-EVIDENCE-v0.1` remains proposed, all selected method records remain `formal_eligible=false`, and no real upstream evidence bundle has been reviewed through this candidate. Next scientific work is to review/freeze the relevant MeasurementSpec-side requirements and upstream validation/prior/sensitivity records, then run a reproducible real ProductCase only after explicit scientific authorization. This validation does not freeze a gate, ScoreContract, threshold or release state.
