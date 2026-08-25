# P0-12 graft assessment candidate validation — 2026-08-25

## Question and scope

This validation asks whether an optional graft handoff can be represented
without changing pretransplant evidence, and whether a provided three-object
bundle can be bound and aggregated deterministically without hard-coding
biological roles or rerunning single-cell analysis.

## Inputs and controls

Only synthetic JSON fixtures are used. They cover a module-local `GraftCase`,
an external `GraftAssessmentSpec`, and a `GraftEvidenceBundle` of precomputed
composition, reference-support, maturation and unknown records. A separate
fixture replaces all four example labels with future role, metric and state
names to confirm the vocabulary is owned by the external spec.

Controls cover no graft, explicit and absent preparation linkage, missing
animal/timepoint/replicate metadata, declared confounding, missing required
roles, checksum drift, partial input sets, case/spec/method binding drift,
undeclared record roles/metrics/states, input mutation and existing-output
drift.

## Observed behavior

The no-input request succeeds deterministically with `state=not_provided`,
`analysis_mode=unavailable` and
`pretransplant_evidence_effect=none`. A valid three-object request succeeds as
`state=candidate`, `analysis_mode=descriptive_only` and
`evidence_state=shadow`, with exact input checksum bindings and per-role
summaries.

Missing metadata, confounding, missing required roles and missing linkage remain
explicit result states or reason codes. Invalid envelopes, input bytes,
cross-object bindings or external-spec membership fail before publication.
Repeated identical requests reuse byte-identical artifacts, while input or
existing-bundle drift fails closed.

## Engineering evidence

- Focused P0-12 and registry suite: 29 passed.
- Public surface remains 12 discovered tools.
- Four P0-12 public JSON Schemas are generated from the module models and
  packaged through the shared schema registry.
- The committed request example covers the directly executable optional
  no-graft path.
- No expression matrix, real graft, private record or server path is included.
- No measurement, visualization or domain score is produced.

The final repository-wide knowledge, policy, generator idempotence and diff
checks are recorded in the branch handoff.

## Boundary

This is engineering evidence for a deterministic candidate interface only. It
does not validate composition, reference mapping, maturation or unknown-state
biology; it does not infer efficacy, safety, potency, clinical outcome or
release suitability. The two registered knowledge methods remain candidates,
and P0-12 never backfills pretransplant evidence.
