# Tool Package Rules

- Keep P0-01 through P0-12 as the only high-level Agent-callable packages in this release.
- Each package owns `describe`, deterministic eligibility and `run` behavior through the shared runtime.
- A scaffold returns `not_implemented` with no measurements, artifacts, visualizations or fabricated scientific state.
- Scientific computation lives in package executors; LLMs do not write measurements, thresholds, scores, evidence states or identifiers.
- Inputs are immutable. Outputs are versioned, checksummed and traceable to Tool, MeasurementSpec, environment and input hashes.
- Current contracts forbid non-null `domain_score` and `score_state=available`.
- Method-specific commands stay behind a high-level package and must be registered, benchmarked and versioned before formal use.
