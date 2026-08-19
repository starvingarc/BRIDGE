# Local Agent DeepInfer Integration

| Field | Value |
|---|---|
| Branch | `local-dev-agent` |
| Baseline | `07aa6b2aa1e8368b5bc882c7dbc0dd656c89213b` |
| Status | `draft_review` |

## Motivation

The local runtime can execute an approved scientific plan but has no conversational
model boundary. Add one concrete DeepInfer-backed Agent loop so a deployment can
clarify requests and explain deterministic outcomes without giving model output
authority over ToolRequests, AnalysisPlans, numerical results or release state.

## Scope and non-goals

- Read the OpenAI-compatible endpoint from `DEEPINFER_BASE_URL` and use
  `deepseek-v4-flash-0731` by default.
- Accept an optional `DEEPINFER_API_KEY` without serializing or logging it.
- Define immutable request/response records with stable input/output SHA-256,
  provider request ID, token usage and latency.
- Provide one minimal synchronous local Agent loop for text clarification and
  explanation; only caller-supplied public-safe context can enter the model request.
- Keep AnalysisPlan construction, approval, workflow events and Tool execution
  outside the LLM boundary. The model cannot call a tool, mutate a case or approve
  a plan in this change.
- Do not add streaming, background workers, multi-turn persistence, HTTP routes,
  prompt retrieval, automatic retries, function calling or report publication.

## Work

1. [x] Implement a concrete DeepInfer chat client using the standard library.
2. [x] Add a constrained local Agent loop and immutable audit metadata.
3. [x] Cover configuration, URL construction, headers, response validation,
   redaction, hashes, error handling and no-tool-authority behavior.
4. [x] Verify the configured endpoint with a minimal live smoke request without
   persisting credentials or private scientific data.
5. [x] Update stable Agent/runtime documentation with the implemented boundary and
   the remaining non-goals.

## Acceptance

- Missing or malformed configuration fails before any network call with a stable
  reason code.
- Every successful call pins `deepseek-v4-flash-0731`, records request/response
  hashes and returns only validated text plus usage/audit metadata.
- Authorization values and raw environment values never appear in exceptions,
  response objects, repr output or workflow events.
- The model receives no raw asset bytes, filesystem traversal capability,
  ToolExecutionPipeline handle or plan-approval method.
- Focused tests, the complete test suite, Tool Registry, knowledge validation,
  repository policy, compilation and `git diff --check` pass.

## Risks

The configured service is external to the deterministic runtime even when its URL
is supplied locally. Callers remain responsible for selecting public-safe context.
The first implementation is synchronous and single-call; cancellation, timeout
coordination and conversation persistence require separate design.

## Validation on 2026-08-19

- Focused DeepInfer/Agent/CLI contract tests: 10 passed. They cover fixed model and
  endpoint construction, optional bearer header, secret-free errors, exact request
  envelope, request/response hashes, response-model mismatch, malformed output,
  explicit whole-turn `public_safe` classification and CLI success/refusal paths.
- The complete source suite passed: 983 tests with the same three dependency
  warnings as the baseline.
- A live `bridge-agent` smoke call used `deepseek-v4-flash-0731` and public test text
  only. It returned provider request ID
  `chatcmpl-932e6595-8e6e-4847-a543-2753914c82e9`, `finish_reason=stop`, 173 prompt
  tokens, 106 completion tokens, 279 total tokens and a validated `explain`
  decision. The request SHA-256 was
  `657d47afec2020ce2ac2354e6f458f8c0efb2e9a97f052982a211a32e646500a` and the
  canonical response SHA-256 was
  `0fc35990afc4dd7d0d0c99037bc3390501e4b91bf609fb0f7218e189813f5481`.
  No API key, endpoint URL, private case data or scientific asset was logged.
- Tool discovery still reports 12 packages. Knowledge validation remains valid at
  354 methods and 396 bindings. Repository policy passes at exactly 300 tracked
  files; compilation and `git diff --check` pass.

The implementation is ready for review, not automatic deployment. Before real case
use, the owner must define conversation retention and an approved public-safe
context compiler; the explicit classification remains an assertion rather than DLP.
