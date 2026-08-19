# Local Agent DeepInfer Integration

| Field | Value |
|---|---|
| Branch | `local-dev-agent` |
| Baseline | `07aa6b2aa1e8368b5bc882c7dbc0dd656c89213b` |
| Status | `in_progress` |

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

1. [ ] Implement a concrete DeepInfer chat client using the standard library.
2. [ ] Add a constrained local Agent loop and immutable audit metadata.
3. [ ] Cover configuration, URL construction, headers, response validation,
   redaction, hashes, error handling and no-tool-authority behavior.
4. [ ] Verify the configured endpoint with a minimal live smoke request without
   persisting credentials or private scientific data.
5. [ ] Update stable Agent/runtime documentation with the implemented boundary and
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
