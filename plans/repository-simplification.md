# Repository Simplification

Status: `in_progress`

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

In progress. Replace the identical export bodies in P0-07 through P0-10 with one
small shared implementation. Preserve SVG/PNG/PDF bytes, metadata, rendering
configuration and figure closure on success/failure. Behavioral tests must first
fail, then pass; compare real outputs against the captured pre-change baseline.

Include the shared source in renderer provenance. Existing run identity uses Tool
version and inputs, while checksummed bundles include renderer-source hashes.
Advance only patch versions to prevent newly attributed bundles colliding with
older ones: P0-07 0.4.0 → 0.4.1, P0-08 0.5.0 → 0.5.1,
P0-09 0.4.1 → 0.4.2 and P0-10 0.4.0 → 0.4.1.
Update current Specs, Tool Cards, examples and relevant fixtures; preserve
historical validation versions. Verify old bundles remain intact and unchanged
new-version runs reuse deterministically.

P0-11 and P0-12 sanitation policies differ, including stroke-dashoffset permission;
leave both unchanged. Do not unify other differing renderer variants, introduce
flags, or modify scientific models or public schemas. Add only the two genuine
new shared files to existing repository accounting; keep every safeguard.

## Task 3: Verify integration and retire operational clutter

Private recovery checks and the authorized retirement of obsolete branches,
worktrees and local code copies are complete. Superseded PRs were closed, not
merged. Exact source heads and retained history are recoverable; running services,
controlled data and existing installations were not changed. Recovery maps and
checksums remain private.

After integrating Task 2, run the full pytest suite, CLI tool discovery, knowledge
and figure-registry validation, repository policy and committed whitespace checks.
Inspect public privacy/link safety, built-package contents and the resulting branch
map. Complete a whole-branch review, retire task-owned temporary worktrees, and
publish this topic as a PR against main without merging.

## Verification and remaining gates

- Baseline: 100 focused planner, registry and visualization/security tests passed.
- Documentation: repository policy, whitespace, canonical workflow coverage and
  historical evidence-link checks passed.
- Integrated suite, final review and PR publication: pending.

This cleanup does not qualify reference candidates, state/role/window definitions,
P0-03–P0-06 product evidence, the full graph feedback loop or a qualified report.
The next scientific work remains in
[Product Evidence Validation](product-evidence-validation.md) and the
[P0-02 review plan](p0-02-cell-state-scientific-freeze.md).
