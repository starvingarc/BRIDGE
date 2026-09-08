# P0-05 Count-only Reference-support Accounting

Date: 2026-09-07 · Package: P0-05 0.6.0

## Question and observed behavior

When P0-02 supplies reference-support counts without assignment mass, what can
Off-target Control retain? The opt-in `hard_count_accounting` route preserves
those counts and their full-view denominator. It does not estimate biological
abundance or reconstruct probabilities.

Synthetic contract fixtures cover mixed support, single-source support,
source conflict, unavailable evidence and zero role support. Consensus-supported
counts map through the supplied StateRoleMap; non-consensus reconciliation
buckets remain separate. Their sum equals the selected observation count.
Source-specific rows are retained, never summed across references.

All role fractions are descriptive count/N values. Soft mass stays
`null / unavailable`; zero supported cells cannot exclude an off-target state.
Rare-state detection and open-set assessment remain `not_assessed`.
There is no new calibration, threshold, biological role or figure.

## Interfaces and invocation

Use `bridge-tool input-contract P0-05` to discover the new mode and exact roles.
The seven required objects include the P0-02 V3 profile, declared biological-unit
manifest and separate attestation receipt. Missing design confirmation is not
filled by this route. The [Tool Card](../../src/bridge/tool_packages/cards/P0-05.md)
and [module guide](../../src/bridge/tool_packages/p0_05_off_target_control/README.md)
describe CLI/SDK use.

An optional MeasurementSpec authorizes four checksummed MeasurementResultV2
artifacts: one inferred count-accounting object and three explicitly unavailable
mass, unknown-identity and rare-detection measurements. Without a spec, no
measurement artifact is emitted. The new result union also accepts the unchanged
legacy v0.2 profile; old input modes and old Schema files are preserved.

## Engineering verification

The pre-publication implementation checkpoint was `f197a502`. A wheel was built
and installed into a fresh target directory; import resolution was asserted to
use that installation, not the source tree. Tests use synthetic objects only.

| Check | Observed result |
|---|---|
| Installed P0-05, registry, integration-profile and contract tests | 186 passed |
| Discovery and SDK input contracts | 12 implemented tools |
| CLI describe and input-contract | Passed for P0-05 0.6.0 |
| Knowledge and figure registries | Passed |
| Repository policy and committed whitespace | Passed |
| Refusal and publication behavior | Exact ownership/checksum, mixed-mode, changed-input and deterministic-content regressions passed |
| Exported result contracts | Standalone and union schemas reject contradictory projection states |

Independent review found an exported-schema/Python projection discrepancy and a
wrong documentation command. Both were corrected at the model/documentation
source. The schema regressions first failed, then all four passed after the fix;
they are included in the installed total above.

To reproduce the focused suite from a wheel-installed environment:

```bash
python -m pytest -q tests/test_p0_05*.py tests/test_registry.py tests/test_agent_integration.py tests/test_contracts.py
bridge-tool describe P0-05
bridge-tool input-contract P0-05
bridge-tool knowledge validate
bridge-tool figures validate
python scripts/check_repository.py
git diff --check
```

Run outside a source-import configuration when verifying the wheel. The test
archive root may be importable for test helpers; its `src` directory must not
override the installed package. GitHub checks bind the eventual published PR
head separately; this record does not predeclare their outcome.

## Limits and next evidence

This is engineering evidence, not a real-data Web or model-driven full-chain
pass. No probability calibration, abundance accuracy, biological independence,
rare-state detectability, product safety or release validity was established.
The receipt validates declared bindings, not the truth of an experimental
design. Real runs still require genuine product, source and design records.

P0-05 remains `candidate/shadow`, with `domain_score=null` and
`score_state=unavailable`. Review real design records and perform source-bound
integration before interpreting this route in a product evaluation.
