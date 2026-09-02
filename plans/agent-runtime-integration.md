# Agent Runtime Integration

## Goal

Integrate the recovered local Agent application core onto current `main` while
preserving deterministic scientific authority and the non-blocking treatment of
unavailable mitochondrial QC coverage.

## Scope

- Immutable ProductCase and approved AnalysisPlan contracts.
- Deterministic planning and case-scoped Tool Package execution.
- Append-only workflow events with in-memory and SQLite stores.
- Content-addressed local artifact storage.
- One synchronous, public-safe, text-only model boundary with no tool authority.
- P0-01 behavior that skips only the mitochondrial threshold when mitochondrial
  symbols are unavailable and continues independent candidate rules.
- Current-main compatibility tests and stable documentation.

## Non-goals

- No Web server, background worker, streaming, automatic retry, or persistent
  conversation service.
- No model-authored ToolRequest, plan approval, scientific measurement, score, or
  release decision.
- No raw scientific data, local run artifacts, credentials, provider responses,
  machine paths, or private validation records in the repository.

## Acceptance

- Recovered functionality is represented by one linear, sanitized commit on the
  latest `origin/main`.
- Focused Agent/runtime and P0-01 regressions pass.
- The full test suite, Tool Registry, knowledge validation, repository policy,
  compilation, and `git diff --check` pass.
- The proposed diff passes credential, absolute-path, generated-artifact, and
  oversized-file review.

## Status

Implementation recovered and engineering validation complete; scientific and
architecture review pending.

## Validation results

- Focused Agent, workflow, pipeline, artifact, ProductCase, planning, and
  mitochondrial regressions: 52 passed.
- Full current-main suite: 1,561 passed with 20 existing dependency warnings.
- Tool Registry, knowledge snapshot, repository policy, compilation, diff, and
  sensitive-information gates: passed.
