# P0-04 Developmental Compatibility v0.2 validation

- Branch: `p0-04-developmental-compatibility`
- Base: `c336a20f25c8536b3a4a42dd1f85ee91bd83d6a1`
- Runtime: Ubuntu server, Python 3.12, `ENV-P0-CORE-v0.1`
- Scientific status: `candidate`; methods remain `formal_eligible=false`
- Score boundary: `domain_score=null`, `score_state=unavailable`

## Implemented scope

The adapter consumes six required checksummed JSON objects and one optional real
timepoint series through `ToolRequestV2`. It validates case, product, window,
state-map, assay, MeasurementSpec and P0-02 profile bindings. The executor selects
one externally declared composition channel and reports five stage roles under
whole-product and target-related denominators. No biological label, marker,
threshold or stage conversion is embedded in code.

## Verification

Server verification on the branch source passed:

- 14 focused P0-04 tests;
- 1,058 complete repository tests;
- public schema export and runtime result validation;
- 12-tool discovery, example-version and active-method parity;
- repository policy and `git diff --check`.

The PR evidence must bind these commands to the final commit SHA; this record
does not claim clean-wheel or scientific-release validation.

## Boundaries retained

Reference-stage support and inferential time-course remain unavailable. One
timepoint is static; multiple declared timepoints are descriptive only.
Unconfirmed windows do not produce a compatibility conclusion. Missing, unknown
or unavailable composition is not zero. Execution does not imply scientific
validation, clinical meaning or release authority.
