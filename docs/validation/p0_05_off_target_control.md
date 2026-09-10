# P0-05 Off-target Control: Validation History

This subject-level record preserves the complete dated receipts below.
Each receipt's inputs, source versions, test counts and scientific limits
apply to that historical run, not to the current main branch or a newly
qualified method/product. Consolidation changes organization and links only;
it does not combine evidence families or create a new validation result.

- [P0-05 Off-target Control candidate validation — 2026-08-25](#record-p0-05-off-target-control-20260825)
- [P0-05 real method runtime candidate validation — v0.3](#record-p0-05-real-method-runtime-v0-3)
- [P0-05 Biological-unit attestation receipt validation](#record-p0-05-biological-unit-attestation-receipt-20260905)
- [P0-05 Count-only Reference-support Accounting](#record-p0-05-hard-count-accounting-20260907)

<a id="record-p0-05-off-target-control-20260825"></a>

## P0-05 Off-target Control candidate validation — 2026-08-25

### Question tested

Can P0-05 accept six immutable structured objects, apply only caller-supplied
state roles and assessment limits, and publish a deterministic whole-product
off-target profile while failing closed on incomplete coverage, zero
observations, missing calibration and broken provenance?

This is an engineering contract validation. It does not validate the biological
correctness of a StateRoleMap, an unknown vocabulary, a calibration record or
an off-target interpretation.

### Validated source

| Item | Value |
|---|---|
| Branch | `p0-05-off-target-control` |
| Base commit | `c336a20f25c8536b3a4a42dd1f85ee91bd83d6a1` |
| Validated implementation | code, schemas and documentation co-committed with this record |
| Runtime | Python 3.12 server environment |
| Tool version | `0.2.0` |
| Result schema | `bridge://schemas/off-target-control-profile/v0.1` |
| Scientific status | `candidate / shadow` |
| Score | `score_state=unavailable`, `domain_score=null` |

### Inputs and controls

Tests used only synthetic JSON objects. No private expression matrix, internal
sample identifier or unpublished biological result was opened or committed.

The happy path bound:

- one ProductCase and its ProductDefinitionCard;
- one separately checksummed StateRoleMap;
- one OffTargetAssessmentSpec that bound the exact map checksum;
- one P0-02 CellStateEvidenceProfileV2;
- one precomputed OffTargetEvidenceBundle bound to the case, card and profile.

The controls changed role assignment without changing package code, withheld
composition coverage, introduced undeclared unknown reasons, exercised detected,
calibrated-zero, missing-calibration, insufficient-calibration and
missing-observation rare states, broke cross-object bindings and checksums,
reused identical output, and tampered with a published bundle.

### Results

| Gate | Result |
|---|---|
| P0-05 focused suite | `18 passed` |
| P0-05 plus registry | `25 passed` |
| Complete source suite | `1062 passed, 8 existing warnings` |
| Tool discovery | exactly 12 packages; P0-05 is implemented |
| Public Schema count | 67; four P0-05 schemas packaged and resolvable |
| Knowledge validation | valid; 354 methods, 387 sources, 396 bindings, no dangling references |
| Tool Card and Schema generators | two successive runs were idempotent |
| P0-05 method | `METHOD-BRIDGE-ROLE-AWARE-SOFT-COMPOSITION` |
| Formal-eligible methods | 0 |

The warnings are existing AnnData duplicate-variable and SciPy sparse-matrix
migration warnings from P0-01 tests; no warning originated in P0-05.

The same immutable inputs produced the same run ID and result checksum.
Replacing the existing result bytes caused a typed failure rather than silent
overwrite. A V1 ToolRequest produced `tool_request_v2_required`.

### Observed semantics

- Changing the external role map moved the same state mass between generic
  product roles without any code change.
- Complete coverage produced role and unknown fractions against the declared
  soft-mass denominator.
- Partial coverage preserved observed mass/count but withheld fractions and
  returned `not_assessed`.
- Zero role or unknown observations returned `cannot_exclude`, not absence.
- A calibrated zero rare-state count returned `not_detected_above_lod` with
  the supplied upper bound and an explicit zero-is-not-absence reason.
- Missing or out-of-spec calibration returned `cannot_exclude`; a missing
  rare-state observation returned `not_assessed`.
- Unknown reasons and state IDs outside the external contracts failed
  eligibility.

### Boundary and remaining work

P0-05 does not rerun scRNA-seq, calculate cell-state assignments, train or select
an OOD method, fit detection limits, compare products, produce visualizations or
emit MeasurementResults. It does not establish biological truth, safety,
efficacy, potency, GMP release or product ranking.

Formal evidence remains blocked until product-specific StateRoleMap review,
real whole-product denominator review, OOD/source-family holdouts, known-mixture
composition checks, rare-state spike-in/false-positive calibration and
reference/preprocessing/assay sensitivity are independently completed and
versioned. Those scientific gates can revise the external objects without
changing this aggregation implementation.


---

<a id="record-p0-05-real-method-runtime-v0-3"></a>

## P0-05 real method runtime candidate validation — v0.3

### Question tested

Can P0-05 retain its six-object aggregation contract while adding a callable,
checksummed method mode for composition uncertainty, rare-state planning and
supplied-source OOD coordination without embedding product-specific biology?

This record validates engineering execution and refusal semantics. It does not
validate a StateRoleMap, detection limit, OOD channel, product interpretation or
safety claim.

### Validated source

| Item | Value |
|---|---|
| Branch | `p0-05-real-method-runtime` |
| Base commit | `d749e8b3a05ffe9c4461312e8eb01b3fd32eb492` |
| Validated implementation | code, schemas, examples and documentation co-committed with this record |
| Runtime | Python 3.12 |
| Tool version | `0.3.0` |
| Primary result schema | `bridge://schemas/off-target-control-profile/v0.1` |
| Method artifact schema | `bridge://schemas/off-target-method-bundle/v0.1` |
| Scientific status | `candidate / shadow` |
| Score | `score_state=unavailable`, `domain_score=null` |

### Input modes

`legacy_aggregation` uses the existing six checksummed objects and P0-02 V2.
`method_runtime` uses the same product, role, assessment and evidence objects,
requires P0-02 V3, and adds:

- a reviewed `BiologicalUnitManifest`;
- an `OffTargetMethodSpec` containing method selection and numerical rules;
- an `OffTargetMethodInput` containing unit-level composition, spike-in trials
  and OOD channel states.

The fixture used four analysis units in four declared independence groups. Unit
soft and hard counts closed exactly to the whole-product evidence bundle and to
the P0-02 V3 reconciliation partition. No expression matrix, private sample ID
or unpublished result was used.

### Executed methods

| Selector | Runtime implementation | Output boundary |
|---|---|---|
| `COMP-EXACT` | SciPy beta quantiles for Clopper-Pearson intervals | descriptive cell-count interval; not replicate uncertainty |
| `COMP-HARD-SENS` | hard-versus-soft role aggregation | sensitivity record, not a preferred annotation rule |
| `COMP-HBOOT` | seeded NumPy resampling of independence groups | uncertainty over declared groups only |
| `RARE-EXACT` | Clopper-Pearson rare-state count interval | descriptive count evidence only |
| `RARE-SPIKEIN` | empirical recovery curve and external acceptance rule | candidate detection limit, not scientific validation |
| `RARE-BINOMIAL-AT-LEAST-ONE` | single-state at-least-one-cell binomial calculation | not SCOPIT; retains independent-sampling and perfect-detection assumptions |
| `OOD-DISAGREE` | source-family state comparison | disagreement audit, not OOD inference |
| `OOD-ENSEMBLE` | ordered external-rule coordinator | supplied channel states only; family conflict returns `not_assessed` |

Catalogued deep OOD, compositional inference and rare-cluster discovery methods
remain conditional candidates and were not executed by this release.

### Results

| Gate | Result |
|---|---|
| P0-05 legacy and method suites | `24 passed` |
| P0-05 plus registry and knowledge-catalog checks | `46 passed` |
| Input contracts | `legacy_aggregation` has 6 roles; `method_runtime` has 9 roles |
| Generated artifacts | P0-05 public schemas, Tool Card and knowledge snapshot regenerated from their repository sources |
| Repository checks | knowledge validation, repository policy and `git diff --check` passed |
| Formal-eligible methods | 0 |

These counts describe the focused closure run for this revision. The required
GitHub repository gate remains the authority for the complete source suite,
wheel build, 12-tool discovery and clean-install checks.

### Observed semantics

- All eight selectors ran through the same installed adapter used by the CLI
  and SDK, producing one primary profile and one method bundle.
- Identical checksummed inputs and seed reused the same run and artifact bytes.
  Changing the seed changed the run fingerprint.
- Bootstrap sampled declared independence groups rather than cells.
- Spike-in output reports each fraction's independent-group count and uses `candidate_detection_limit_fraction`; it did not promote
  the supplied engineering acceptance rule to biological validation.
- The checksummed MethodSpec fixes each OOD channel's family, upstream-result
  checksum, method and reference. Runtime input supplies only state/reason, and
  one upstream result cannot be relabelled as two families. Within-family
  conflict remains `not_assessed`; this boundary was reviewed in code
  but was not part of the executable fixture reported above.
- Missing one of the three method objects, changing an independence-group
  binding or replacing an input file prevented execution with typed reasons.
- Legacy six-object requests remained callable and continued to emit one
  `OffTargetControlProfile` artifact.

### Measurement projection contract closure — tool v0.5.1

A later compatibility closure kept both execution modes and the v0.2 result schema,
but separated the P0-05 domain MeasurementSpec from the P0-02 source spec carried
by ProductCase. Any run requesting normalized measurement projection now also
requires one checksummed reviewed BiologicalUnitManifest. Eligibility verifies the
analysis unit, independence group, assay-specific cell/nucleus observation unit,
ProductCase manifest binding and denominator count before projection. Missing or
mismatched unit evidence fails closed.

The focused server run covered legacy aggregation and method execution, including
unit-mismatch and missing-manifest adversaries: `55 passed`. This is engineering
contract evidence only and does not validate the supplied StateRoleMap, thresholds,
OOD evidence or biological interpretation.

### Remaining scientific work

Formal evidence still requires product-specific StateRoleMap review, real
whole-product denominator review, known-mixture composition error, source-family
and OOD holdouts, rare-state spike-in/false-positive calibration,
reference/preprocessing/assay sensitivity, and signed review of every external
rule object. Cell-count intervals must not be presented as biological-replicate
inference. The single-state binomial design is optimistic when detection is imperfect and must not be represented as SCOPIT.

Until those gates are independently completed, all method outputs remain
engineering candidates: `evidence_state=shadow`, `score_state=unavailable`,
`domain_score=null`.


---

<a id="record-p0-05-biological-unit-attestation-receipt-20260905"></a>

## P0-05 Biological-unit attestation receipt validation

Date: 2026-09-05

### Scope

P0-05 method execution consumes the immutable P0-01 `declared`
BiologicalUnitManifest together with a separate
`BiologicalUnitAttestationReceipt v0.1`. The receipt records an explicit
caller/data-owner assertion for `analysis_execution` and binds:

- the exact manifest and assignment checksums;
- the selected DataView, selected artifact and observation-set digest;
- the analysis unit, independence group and independence scope;
- four explicit design confirmations;
- the attestor, timezone-aware attested time and an external attestation
  reference/checksum.

Runtime validates only the receipt structure and these content bindings. It does
not authenticate the attestor or verify the truth or origin of the external
attestation record. Deployment is responsible for mapping an authenticated
conversation or workflow record to `attestation_ref` and
`attestation_sha256`.

A legacy `reviewed` or `frozen` manifest cannot replace the receipt. The
receipt does not establish biological truth, independent review, publication
permission, clinical validity, GMP release, safety, efficacy, potency or
product-release authority.

### Engineering checks

| Check | Result |
|---|---|
| P0-05 aggregation and method suites | 70 passed |
| Registry and shared contract-spine suites | 52 passed |
| Receipt refusal matrix | Absence, incomplete trace, not-confirmed decision, incomplete design confirmations, binding drift, file replacement and legacy-manifest bypass rejected |
| Schema generation | Draft 2020-12 public schema generated twice without drift |
| Repository policy and diff hygiene | Passed |
| Clean-wheel smoke | Installed package reported P0-05 v0.5.2, both input modes and the packaged receipt Schema |
| Scientific output boundary | Existing methods, measurements, `domain_score=null` and `score_state=unavailable` unchanged |

The tests use synthetic contract objects only. The fixed attestation hash is a
fixture value, not an authenticated record. No private data or deployment
resource is included.


---

<a id="record-p0-05-hard-count-accounting-20260907"></a>

## P0-05 Count-only Reference-support Accounting

Date: 2026-09-07 · Package: P0-05 0.6.0

### Question and observed behavior

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

### Interfaces and invocation

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

### Engineering verification

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

### Limits and next evidence

This is engineering evidence, not a real-data Web or model-driven full-chain
pass. No probability calibration, abundance accuracy, biological independence,
rare-state detectability, product safety or release validity was established.
The receipt validates declared bindings, not the truth of an experimental
design. Real runs still require genuine product, source and design records.

P0-05 remains `candidate/shadow`, with `domain_score=null` and
`score_state=unavailable`. Review real design records and perform source-bound
integration before interpreting this route in a product evaluation.
