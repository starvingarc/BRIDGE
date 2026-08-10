# Legacy Boundary

This subtree is provenance-only.

- Do not import, install, test or register code from `legacy/` in active BRIDGE v2.
- Do not patch historical files to implement a v2 feature.
- Reuse requires an explicit migration decision, a new implementation outside `legacy/`, and current-contract tests.
- Preserve historical files unless the user explicitly authorizes deletion.
