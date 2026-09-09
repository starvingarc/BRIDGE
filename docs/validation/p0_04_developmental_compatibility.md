# P0-04 Developmental Compatibility: Validation History

This subject-level record preserves the complete dated receipts below.
Each receipt's inputs, source versions, test counts and scientific limits
apply to that historical run, not to the current main branch or a newly
qualified method/product. Consolidation changes organization and links only;
it does not combine evidence families or create a new validation result.

- [P0-04 Developmental Compatibility v0.2 validation](#record-p0-04-developmental-compatibility-v0-2)
- [P0-04 Developmental Compatibility v0.3 validation](#record-p0-04-developmental-compatibility-v0-3)

<a id="record-p0-04-developmental-compatibility-v0-2"></a>

## P0-04 Developmental Compatibility v0.2 validation

- Branch: `p0-04-developmental-compatibility`
- Base: `c336a20f25c8536b3a4a42dd1f85ee91bd83d6a1`
- Runtime: Ubuntu server, Python 3.12, `ENV-P0-CORE-v0.1`
- Scientific status: `candidate`; methods remain `formal_eligible=false`
- Score boundary: `domain_score=null`, `score_state=unavailable`

### Implemented scope

The adapter consumes six required checksummed JSON objects and one optional real
timepoint series through `ToolRequestV2`. It validates case, product, window,
state-map, assay, MeasurementSpec and P0-02 profile bindings. The executor selects
one externally declared composition channel and reports five stage roles under
whole-product and target-related denominators. No biological label, marker,
threshold or stage conversion is embedded in code.

### Verification

Server verification on the branch source passed:

- 14 focused P0-04 tests;
- 1,058 complete repository tests;
- public schema export and runtime result validation;
- 12-tool discovery, example-version and active-method parity;
- repository policy and `git diff --check`.

The PR evidence must bind these commands to the final commit SHA; this record
does not claim clean-wheel or scientific-release validation.

### Boundaries retained

Reference-stage support and inferential time-course remain unavailable. One
timepoint is static; multiple declared timepoints are descriptive only.
Unconfirmed windows do not produce a compatibility conclusion. Missing, unknown
or unavailable composition is not zero. Execution does not imply scientific
validation, clinical meaning or release authority.


---

<a id="record-p0-04-developmental-compatibility-v0-3"></a>

## P0-04 Developmental Compatibility v0.3 validation

- Branch: `p0-04-real-method-runtime`
- Runtime contract: Ubuntu, Python 3.12, `ENV-DEVELOPMENT-PY-v0.1`
- Scientific status: `candidate/shadow`; `domain_score=null`
- Evidence source: fully synthetic fixtures only

### Implemented scope

The aggregation path consumes the current checksummed P0-01 → P0-02 v0.3
lineage plus product, window, state-map, vocabulary and reference contracts. It
reports whole-product and target-related stage composition.

The optional expression path binds one normalized H5AD to the selected P0-02
view and a versioned `DevelopmentMethodSpec`. The fixture executes:

- pseudobulk Spearman/cosine reference support;
- a scikit-learn cumulative ordinal logistic baseline, only after a reviewed
  and passed source-group-held-out receipt binds all selected profiles and
  sources;
- decoupler ULM stage-program activity;
- independence-group-preserving bootstrap;
- unadjusted descriptive program and reference-support trends using
  statsmodels/Patsy splines.

Reference labels, roles, ranks, program cards, true timepoints and thresholds are
fixture inputs rather than code constants.

### Verification

Server verification on the exact branch head established:

- the P0-04 focused suite and complete repository suite passed;
- all six selected method aliases produced typed, checksummed output;
- repeated execution reused identical content;
- method/H5AD pairing and replaced-asset checks failed closed;
- changing an external stage-role definition changed the reported role without a
  code change;
- absent ordinal held-out evidence produced typed `not_assessed`, while the
  synthetic reviewed receipt only exercised gate binding and did not constitute
  scientific calibration;
- inadequate coverage in any selected reference profile and cross-source/assay
  stage-role disagreement propagated `unavailable` and were excluded from
  derived reference-support summaries;
- time splines were labelled `unadjusted_descriptive`, contained no inferential
  interval, and the domain result retained
  `inferential_timecourse_unavailable`;
- public Pydantic models emitted valid Draft 2020-12 schemas;
- a clean wheel loaded from its installed location, exposed every registered
  `describe` and `input-contract` call, validated the request and completed
  all six methods;
- the pinned developmental environment reproduced the same installed-wheel run;
- knowledge validation had no dangling references and no formal eligible
  methods; repository policy, diff and tracked-content privacy checks passed.

### Boundary

These tests establish executable packaging and deterministic synthetic behavior.
They do not validate a developmental reference, the caller-supplied held-out
receipt, ordinal calibration, biological age, lineage, efficacy, safety,
potency, score or release decision. Conditional
R/Bioconductor, trajectory, velocity, OT and lineage methods remain outside the
v0.3 runtime contract.
