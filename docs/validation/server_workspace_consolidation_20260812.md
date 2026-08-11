# Server Workspace Consolidation Review

**Date:** 2026-08-12
**Status:** `reviewed_pending_cleanup`

This public-safe record captures the logical review of pre-existing server work.
It contains no host usernames, absolute server paths, process identifiers or
private asset paths. No cleanup is claimed by this record; Task 4 must update the
status only after the reviewed cleanup is actually performed and verified.

## Reviewed Git workspaces

| Logical workspace label | Original HEAD | Review outcome | Useful ideas retained as future curation notes | Why the workspace state is not the canonical implementation |
|---|---|---|---|---|
| P0-02 tool-package WIP | `d3ea8ae` | `reviewed_pending_cleanup` | Source-aware cell-state evidence, fail-closed freeze records and competitor-isolation checks remain useful scientific curation inputs | The checkout contains rollback/scaffold remnants and predates the compact canonical projections and current scientific corrections |
| Product-evaluation design WIP | `bebdef7` | `reviewed_pending_cleanup` | Product/sample manifest lineage, development-aware evidence cards and product-level aggregation remain useful future curation topics | It is a parallel design branch with obsolete product-level branding, duplicated legacy/generated material and contracts incompatible with the canonical Tool Package tree |
| Repository-management checkout | `91a531e` | `reviewed_pending_cleanup` | Early product-profile, benchmark-fixture and parameterized-report ideas remain future curation notes only | It mixes repository administration with an older product architecture and must not be treated as the source of current BRIDGE contracts |

## Consolidation boundary

- The canonical branch owns the active Tool IDs, ToolRequest/ToolRun contracts,
  compact knowledge projection, P0-02 freeze interfaces and scientific docs.
- Retaining an idea as a future curation note does not adopt its code, thresholds,
  labels, benchmark result or product claim.
- No reviewed workspace may supply reference, marker, prior, calibration or
  validation evidence without a new checksum-bound curation and scientific review.
- Pilot evidence remains a read-only historical/diagnostic record; it cannot replace
  Task 5 reproducibility checks or the later P0-02 biological FreezeGate.
- Cleanup execution, evidence-package reduction and post-cleanup verification belong
  to Task 4. Until then the only accurate status is `reviewed_pending_cleanup`.
