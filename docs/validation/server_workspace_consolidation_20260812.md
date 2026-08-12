# Server Workspace Consolidation Review

**Date:** 2026-08-12
**Status:** `cleanup_complete`

This public-safe record captures the review and exact cleanup of pre-existing
server work. It contains no host usernames, absolute server paths, process
identifiers or private asset paths. Cleanup is complete. After this cleanup, only
the existing execution worktree was synchronized in place and used for the later
[server reproducibility validation](server_reproducibility_20260812.md).

## Reviewed Git workspaces

| Logical workspace label | Original HEAD | Review outcome | Useful ideas retained as future curation notes | Why the workspace state is not the canonical implementation |
|---|---|---|---|---|
| P0-02 tool-package WIP | `d3ea8ae` | `clean; reviewed WIP discarded` | Source-aware cell-state evidence, fail-closed freeze records and competitor-isolation checks remain useful scientific curation inputs | At cleanup completion it remained at the original HEAD; the discarded rollback/scaffold WIP predated the compact canonical projections. This same execution worktree was later synchronized in place for engineering validation only |
| Product-evaluation design WIP | `bebdef7` | `clean; reviewed WIP discarded` | Product/sample manifest lineage, development-aware evidence cards and product-level aggregation remain useful future curation topics | At cleanup completion it remained at the original HEAD; its discarded product-scoring WIP used contracts incompatible with the canonical Tool Package tree |
| Repository-management checkout | `91a531e` | `clean; reviewed WIP discarded` | Early product-profile, benchmark-fixture and parameterized-report ideas remain future curation notes only | At cleanup completion it remained at the original HEAD as a Git-managed repository; its discarded WIP mixed repository administration with an older product architecture |

## Cleanup outcome

- The three reviewed legacy WIP sets were discarded according to the recorded
  path-by-path review; no WIP archive or parallel implementation was retained.
- Old pilot runs, a broken environment and caches were removed, reclaiming about
  19.60 GiB from the evidence workspace.
- The reviewed orphan workers exited and their shared-memory allocation was
  released before evidence-package cleanup began.
- The complete final `v048` evidence run was preserved. Before and after cleanup,
  its split-manifest hash matched, all `37/37` native artifacts matched, and all
  `12/12` implementation sources matched the run manifest.
- The historical wheel has four implementation hashes that differ from the final
  run manifest. The evidence-package source tree was therefore retained for
  provenance only and is not a canonical source checkout.
- Controlled assets, vendored dependencies, environment specifications, the
  historical wheel, catalog material and knowledge material were preserved.
- At cleanup completion, each reviewed Git workspace was clean and still at its
  original HEAD. Subsequently, only the existing P0-02 execution worktree was
  synchronized in place; its validated state is recorded separately.

## Consolidation boundary

- The canonical branch owns the active Tool IDs, ToolRequest/ToolRun contracts,
  compact knowledge projection, P0-02 freeze interfaces and scientific docs.
- Retaining an idea as a future curation note does not adopt its code, thresholds,
  labels, benchmark result or product claim.
- No reviewed workspace may supply reference, marker, prior, calibration or
  validation evidence without a new checksum-bound curation and scientific review.
- Pilot evidence remains a read-only historical/diagnostic record; it cannot
  replace the later engineering validation or the P0-02 biological FreezeGate.
- This cleanup record itself did not run or claim tests, builds, generators,
  wheel installation or validation. Those later engineering gates are reported in
  the server reproducibility validation record.
