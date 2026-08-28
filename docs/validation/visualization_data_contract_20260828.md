# Visualization data contract validation — 2026-08-28

## Question tested

Can BRIDGE bind a figure to typed, immutable scientific data and expose existing
figure components without changing current P0-01/P0-02 outputs or promoting
missing, unknown or unavailable evidence?

This is a contract, packaging and discovery validation. It does not validate a
biological result or a visual design.

## Exact build

| Item | Value |
|---|---|
| Branch | `visualization-data-contract` |
| Base `main` | `0b57e1bcca0b66069e146d08108ca541c8f8dc9c` |
| Validated implementation commit | `7ec8be8f4a8e2d231ed88c2be2f7b8279e7e09cf` |
| Python | `3.12.13` |
| Wheel | `bridge-0.2.0.dev0-py3-none-any.whl` |
| Wheel SHA-256 | `e303ac79081c86c189bfc95038527f70d4964a41933df4a3e441b6b0a89c3cf3` |

The wheel was built from the implementation commit in the authorized server's
stable core environment, force-installed into a fresh virtual environment with
the source tree absent from the import path, and imported from that
environment's `site-packages`.

## Observations

| Gate | Result |
|---|---|
| Visualization contract, Schema, CLI and SDK suite | `65 passed` |
| Complete repository suite | `1371 passed, 20 warnings` |
| GitHub Actions at the implementation commit | passed |
| Independent code review | 0 Critical; 0 Important findings remaining |
| Tool discovery | 12 packages |
| Figure registry | 7 components; 0 typed candidates; 7 legacy untyped |
| Generated visualization Schemas | deterministic across two generations |
| Knowledge snapshot | valid; 354 methods; 396 bindings; 0 formal-eligible methods |
| Repository policy, Tool Card parity and diff check | passed |
| Installed-wheel import, Schema load and CLI smoke | passed |
| Installed environment dependency check | passed |

The focused tests establish that:

- the existing `VisualizationArtifact` v0.1 property set is unchanged;
- v0.2 requires explicit component/version separation, evidence state,
  denominator semantics, limitations and accessible table/text fallbacks;
- list elements that carry evidence, reason codes or limitations cannot be
  blank, and accessibility text keeps its field-specific minimum length;
- incomplete intervals or denominators, missing evidence without reason codes,
  local or encoded filesystem references and render/data hash drift fail closed;
- the public Draft 2020-12 Schemas enforce the same structural constraints;
- the registry returns defensive copies, validates declared interactions and
  required fallbacks, and refuses to promote the seven existing P0-01/P0-02
  components beyond `legacy_untyped`.

The 20 warnings are existing AnnData duplicate-name, Scanpy score-genes and
SciPy sparse-matrix migration warnings from unrelated fixtures.

## Evidence and boundary

Private engineering logs and the wheel remain on the authorized validation
server, keyed by the implementation commit. No private biological input was
used.

This validation does not implement a Web page, Visualization Composer, new
figure, renderer or package-owned visualization-data Schema. It does not change
Tool IDs, current `ToolRun` payloads, references, state names, thresholds,
scientific status or `domain_score=null`. P0-01/P0-02 figures remain
`legacy_untyped`; all other tools still have no registered figure component.
