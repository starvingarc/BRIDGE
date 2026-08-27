# P0-10 raw JSON Schema runtime validation (2026-08-27)

- Branch: `p0-10-jsonschema-validation`
- Integration base: `d749e8b3a05ffe9c4461312e8eb01b3fd32eb492`
- Package: `P0-10 0.1.1`
- Runtime: Ubuntu, Python 3.12, `ENV-EVIDENCE-v0.1`
- Scientific state: `candidate`; no biological truth or release authority

## Closed gap

P0-10 already registered `jsonschema` as an approved structured-contract method,
but runtime input loading previously relied on Pydantic alone. The adapter now
runs `jsonschema.Draft202012Validator` against the exact decoded payload of each
of its four checksummed input objects before Pydantic model validation. Invalid
raw input returns the existing `structured_input_schema_invalid` reason code.
The CLI, SDK, roles and result Schema are unchanged.

## Verification

- focused P0-10 and registry suite: **70 passed**;
- complete repository suite: **1,227 passed**, with eight pre-existing dependency warnings;
- wheel-only schema-call and successful-receipt smoke: **2 passed**;
- installed module resolved from the unpacked wheel outside the source tree;
- wheel SHA-256: `0ea309f58f2064594c07a23bf0fd1d1f930752b891924b707fe2cdea1531a4f9`;
- generated Tool Card, knowledge validation, repository policy and diff hygiene: passed.

## Boundary

JSON Schema validation establishes contract conformance only. Claim verification
still checks correspondence to supplied evidence and package authority; it does
not establish biological truth, efficacy, safety, potency, GMP release or public
release permission.
