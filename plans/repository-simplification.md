# Repository Simplification

Status: `awaiting_review`

## Question, scope and boundary

Keep the approved product-evaluation workflow understandable and its evidence
traceable, without changing any biological judgment. No new data, reference,
control set or scientific result is introduced. BRIDGE remains research-use
transcriptomic evidence; no P0 ScoreContract is frozen and domain_score stays null.

The user approved public-document simplification, consolidation of proven-equivalent
code, verified private archiving, retirement of absorbed branches/PRs and removal
of local code copies. Running services and irreplaceable evidence are preserved.
Development and validation run on the controlled server. GitHub contains public-safe
source, contracts, minimal fixtures and documentation. Merge and history rewriting
are not authorized.

## Global constraints

- One manually maintained source per fact; summaries link to that source.
- Preserve public schemas, Tool IDs, scientific states and numerical behavior.
- Accepted intake/QC/protocol work is not reopened. Downstream approved behavior
  is a requirement, not an implemented-capability claim.
- Archive exact targets and verify recovery before retiring operational copies.
  Preserve running processes, private artifacts and other contributors' work.
- No generic abstraction without at least two genuine existing callers.
- One root integrator; implementers use separate temporary worktrees and frozen
  write scopes. No private paths, credentials or operational receipts enter GitHub.

## Task 1: Consolidate documentation and approved workflow

Implementation and scoped review complete. The sixteen approved workflow
requirements now have one canonical home in
[PRD section 6](../docs/BRIDGE_PRD.md#6-agent-功能需求), preserving the ten-step flow
and existing section anchors. It distinguishes accepted intake from downstream
graph-driven assessment, reviewed reference/role definitions, internally registered
comparators, evidence-based stopping, versioned reports and approved partial updates.

README and the documentation, tool, Agent and Web guides are shorter entry points.
Five completed construction diaries were retired after retaining their unique
stable facts, exact evidence and unresolved scientific work. Historical Web evidence
is reachable through immutable links from
[its validation record](../docs/validation/web_preview_20260905.md).
The approved BPL design remains. Current correction behavior is explicitly
separate from the unimplemented downstream impact/update target.

Repository-policy and committed-whitespace checks passed for this documentation
increment. Independent review verified all sixteen requirements; its two important
documentation findings were corrected and scoped re-review found no new breakage.

## Task 2: Consolidate proven-equivalent figure code

Implementation and scoped review complete. P0-07 through P0-10 now use one
small shared exporter. Fifteen focused tests cover payloads, metadata, rendering
provenance, lazy import and figure closure on success/failure. The pre-change
red run had 11 expected failures; the completed implementation passed all 15.
All 12 captured SVG/PNG/PDF payloads remain byte-identical.

The shared source is included in renderer provenance. Existing run identity uses
Tool version and inputs, while checksummed bundles include renderer-source hashes.
Only patch versions were advanced to avoid collisions with older bundles:
P0-07 0.4.0 → 0.4.1, P0-08 0.5.0 → 0.5.1,
P0-09 0.4.1 → 0.4.2 and P0-10 0.4.0 → 0.4.1.
Current Specs, Tool Cards, task-card pointers, examples and relevant fixtures
are synchronized; historical validation versions are preserved. Materialized
namespace checks preserved 16/20/24/16 prior-namespace files and reused all new
bundle bytes. Those checks use current adapters under prior/current version
specs, not historical binaries; P0-10 uses its existing validated-graph fixture.

P0-11 and P0-12 sanitation policies differ, including stroke-dashoffset permission;
both remain unchanged. No other variants, flags, scientific models or public
schemas changed. Repository accounting adds only the two genuine shared files;
every safeguard remains.

## Task 3: Verify integration and retire operational clutter

Private recovery checks and the authorized retirement of obsolete branches,
worktrees and local code copies are complete. Superseded PRs were closed, not
merged. Exact source heads and retained history are recoverable; running services,
controlled data and existing installations were not changed. Recovery maps and
checksums remain private.

Integration verification and whole-branch review are complete. Task-owned temporary
worktrees and branches were retired after clean-state, integration and recovery
checks. Keep the main and current PR worktrees. Deliver this topic as a Draft PR
against main; GitHub CI/review and any eventual merge are separate gates.

## Verification and remaining gates

- Baseline: 100 focused planner, registry and visualization/security tests passed.
- Documentation: repository policy, whitespace, canonical workflow coverage and
  historical evidence-link checks passed.
- Exact code revision `3ec609f2`: `python -m pytest -q -ra` passed 2394 tests
  with 43 skips in 1824.68 seconds. Every skip was the explicit pinned BPL
  runtime dependency. With `BRIDGE_TEST_BPL_PYTHON` set to the existing verified
  compiler environment, `python -m pytest -q tests/test_web_protocol_formalization.py`
  passed all 119 tests in 110.65 seconds, including all 43 skipped cases.
  The focused count overlaps the full suite; it is not 119 additional cases.
- `python -m bridge.toolkit.cli list --json`: all 12 tools discovered with the
  exact four new patch versions. `python -m bridge.toolkit.cli knowledge validate`
  passed with zero formally eligible methods.
  `python -m bridge.toolkit.cli figures validate` passed for 43 components.
- `python scripts/check_repository.py`, `git diff --check` and committed-range
  whitespace, public-path/privacy and historical-link checks passed.
- A wheel built from the exact Git archive and installed into an isolated target
  passed helper-origin/lazy-import, tool/version, knowledge and figure-registry
  checks plus the same 12/12 byte comparison. Existing installations were untouched.
- Independent whole-branch review of `40d352b9..3ec609f2` found no remaining
  Critical, Important or Minor issues. Subsequent closeout changes only this plan
  and its index; repository and committed-diff checks are repeated before publication.
- This branch does not change Web source. Frontend tests and browser acceptance
  were not rerun here; earlier revision-bound acceptance is preserved, not upgraded.

This cleanup does not qualify reference candidates, state/role/window definitions,
P0-03–P0-06 product evidence, the full graph feedback loop or a qualified report.
The next scientific work remains in
[Product Evidence Validation](product-evidence-validation.md) and the
[P0-02 review plan](p0-02-cell-state-scientific-freeze.md).
