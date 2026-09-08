# P0-06 Source-bound Observation Validation

Date: 2026-09-07 · Package: P0-06 0.7.0

## Question and observed behavior

Can proliferation/stress summaries retain cells whose source references disagree
without forcing a cell-state identity? The opt-in
`method_runtime_source_bound` route reads canonical P0-02 evidence rows and
their exact artifact manifest through ProcessMethodInputV2.

Producer-format synthetic Parquet fixtures cover consensus support,
single-source support, source conflict and unavailable assignments.
Whole-product analysis retains every observation in its declared unit.
State-specific analysis uses only unique candidate identities allowed by the
supplied program specification. A conflict remains unresolved; an unavailable
assignment stays unavailable. Neither becomes unknown or zero. All-conflict
input creates no artificial state-specific result.

Expression rows are joined by observation identity. Existing per-field
observation-set digests are preserved, while file checksums bind the actual
Parquet bytes. No biological identity, design unit, threshold or program
definition is created by the reader.

## Interfaces and invocation

Use `bridge-tool input-contract P0-06` to discover the explicit new mode.
Its expression input and 12 structured roles match method runtime except for the
versioned `process_method_input` object. The v0.2 source descriptor binds the
producer run/version, V3 profile, exact manifest and evidence artifact; it
replaces caller-supplied observation labels, not the need for valid design
records. The [Tool Card](../../src/bridge/tool_packages/cards/P0-06.md) and
[module guide](../../src/bridge/tool_packages/p0_06_proliferation_stress_response/README.md)
describe its fields, CLI/SDK use and refusals.

Old v0.1 inputs, result profile v0.3 and method bundle v0.2 remain unchanged.
Source correspondence checks do not authenticate an internally consistent but
fabricated bundle. Deployment still owns origin and user-confirmation records.

## Engineering verification

At implementation checkpoint `8f5eb9e1`, a fresh target installation from a
built wheel was checked to import BRIDGE from that installation, not source.

| Check | Observed result |
|---|---|
| Installed P0-06, registry, integration-profile and contract tests | 186 passed |
| Discovery and SDK input contracts | 12 implemented tools |
| CLI describe and input-contract | Passed for P0-06 0.7.0 |
| Knowledge and figure registries | Passed |
| Repository policy and committed whitespace | Passed |
| Source bindings | Run, version, artifact, profile, observation membership, checksum and changed-input refusals covered |
| Aggregation | All four support states, identity joins, allowlist boundaries and whole-product denominators covered |
| Malformed source rows | Stable typed refusal from both eligibility and run |

The test run emitted 49 existing Scanpy deprecation warnings, not failed
checks. No dependency was added. A missing Parquet engine is an execution-time
`source_evidence_runtime_unavailable` refusal, not a discovery import failure.

Independent review found malformed rows escaping as untyped exceptions.
The narrow fix checks singleton cardinality before indexing, rejects
array-shaped semantic cells safely, and converts invalid identifiers into the
existing typed refusal. Four direct-loader and four high-level regressions
failed before the fix; all eight passed after it and are included above.
Scoped re-review found no new breakage.

Reproduce the focused checks from a wheel-installed environment:

```bash
python -m pytest -q tests/test_p0_06*.py tests/test_registry.py tests/test_agent_integration.py tests/test_contracts.py
bridge-tool describe P0-06
bridge-tool input-contract P0-06
bridge-tool knowledge validate
bridge-tool figures validate
python scripts/check_repository.py
git diff --check
```

The test archive root may be importable for helpers; its `src` directory must
not override the wheel installation. GitHub checks bind the published PR head
separately; their outcome is not predeclared here.

## Limits and next evidence

These checks used synthetic source-format fixtures, not a genuine P0-02 run or
a real-model Web full-chain test. They establish parsing, binding and grouping
behavior, not biological accuracy, independent replication or truth of an
attestation. Supplied experimental design and genuine source lineage still
require review before product interpretation.

Existing methods, score semantics and candidate status are unchanged:
`domain_score=null`, `score_state=unavailable`. Next integration work must bind
actual producer artifacts and documented experimental units without coercing
unresolved cells or bypassing missing inputs.
