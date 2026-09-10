# Repository Simplification

Status: `in_progress`

## Goal and approved scope

Make the active repository explain one scientific product and one current workflow,
not accumulate implementation diaries and parallel descriptions. The biological
question and evidence boundaries do not change: BRIDGE provides research
transcriptomic evidence, not clinical efficacy, safety, validated potency, release
decisions or absolute product ranking.

The user approved sequential public-document simplification, consolidation of
proven-equivalent code, verified private archiving, retirement of absorbed branches
and PRs, and removal of local code copies. Running services and irreplaceable
evidence are preserved. Work and verification run on the controlled server; GitHub
contains only public-safe source, contracts, tests, minimal fixtures and stable
documentation. Merge and history rewriting are not authorized.

## Global Constraints

- One manually maintained source per fact; link summaries to it.
- Preserve public schemas, IDs, scientific states and numerical behavior.
- `domain_score` stays `null`; no scientific freeze or new reference approval.
- Completed intake/QC/protocol acceptance is not reopened; newly approved
  downstream workflow is a requirement, not an implemented-capability claim.
- Archive and verify exact targets before cleanup; preserve running processes,
  private artifacts, uncommitted changes and independent scientific evidence.
- No new generic abstraction without at least two genuine existing callers.
- Root controller is the sole integrator. Implementers use separate server
  worktrees and never push, merge, delete operational worktrees, or spawn agents.
- No private filesystem paths, credentials, source data or internal operations
  receipts enter public files.

## Task 1: Consolidate public documentation and approved user workflow

Work only in README.md, AGENTS.md, CONTRIBUTING.md, docs/, plans/ and, if necessary
to keep retirement checks accurate, scripts/check_repository.py. Do not edit
scientific task cards, validation evidence, source-state/role definitions or
runtime code except to repair links to retired plans. The controller owns this
plan and its final evidence; do not edit this plan.

Read AGENTS.md, plans/README.md, docs/README.md and docs/documentation-guide.md.
Use docs/BRIDGE_PRD.md as the single authoritative product-workflow source;
preserve existing section anchors, especially 6.1–6.9. Other overview pages should
link to it instead of restating the full workflow. Add these approved requirements,
with an explicit boundary between accepted existing intake work and downstream
target behavior:

1. Preserve the established ten-step flow: research question, materials, Agent
   understanding/necessary questions, sourced fact confirmation, scoped plan,
   QC, cell-state/product assessment, interpretation, report delivery, corrections.
   Do not re-design or reopen the first six completed steps.
2. Before QC, confirm the research question, overall analysis scope and resource
   ceiling. Refine eligibility after QC and show the update; proceed autonomously
   inside unchanged authorization and request approval for scope/resource expansion.
3. Review one concise sourced experimental-background summary. Distinguish absent
   source facts from explicit-but-unparseable facts; flag conflicts and uncertainty.
   The user can confirm together or edit individual facts. Ask later only for
   newly consequential information, retaining unknowns without repeated questions.
4. The LLM is an active evidence-driven research coordinator: retrieve graph
   evidence, identify gaps, maintain a small set of competing hypotheses, select
   discriminating registered high-level tools, validate their outputs into the
   evidence graph and update interpretation. Tools own numbers, denominators,
   thresholds, statuses, versions and Evidence IDs. A graph component or tool menu
   alone does not prove this autonomous feedback loop is connected.
5. Step seven proposes all existing P0 core dimensions: cell state, target and
   regional identity, developmental compatibility, whole-product/non-target
   composition, proliferation and stress. Mark each runnable, missing input or
   unavailable. Comparison and graft analysis are conditional. The five
   knowledge-enhancement dimensions are not this acceptance gate.
6. Describe all major cell classes and only refine states as evidence supports;
   keep regional, developmental, proliferation and stress axes distinct. Preserve
   upper-level and unresolved identities instead of forcing target/non-target.
7. Default reference selection uses one reviewed, internally aligned multi-source
   reference system with common definitions and decision rules, applicability
   checks, source/version traceability and unresolved genuine conflicts. This is
   an approved target, not a claim that current candidates are scientifically
   frozen. User-specified references are separated. Check method disagreements
   within approved scope, then show their substantive differences.
8. For missing role rules, combine P0-02 evidence, confirmed product goals and
   traceable materials to propose role candidates and their consequences; user
   review does not upgrade candidate science. P0-03 and P0-05 consume the same
   eligible reviewed role definition, not invent roles circularly.
9. Stop on predefined evidence requirements, unfillable evidence gaps or resource
   limits. Explain knowns, unknowns and the stop reason; never stop on LLM
   confidence or count correlated methods as independent votes.
10. Present a continuously updated multidimensional portrait; each dimension has
    state, observation, limitations and next action. Chat highlights consequential
    findings, conflicts and necessary questions. Drill down through a local
    evidence chain: support, opposition, missingness, uncertainty, actual values
    and denominators, figures, methods, sources and versions; mark same-family
    dependence and allow entry into the related graph.
11. Cover all seven P0-06 core program families: pluripotency-like, cell cycle,
    dissociation/heat-shock, oxidative stress, hypoxia, unfolded-protein response,
    and apoptosis-related. Report measured versus unavailable for each. S/G2M
    alone cannot stand for the whole assessment or prove proliferation/safety.
12. The default comparison is a new product versus eligible internally registered
    published products, not multiple uploads. Agent recommends usable comparators,
    background-only objects and excluded objects with reasons; user confirms the
    cohort. Publication alone is not registration, comparability or permission.
    Sealed/competitor-isolated data remain excluded.
13. Reuse valid evidence under the same applicable measurement contract. If
    versions or measurement definitions differ, propose alignment/recomputation,
    explain resource needs and obtain approval; preserve old results and produce
    a new version. Comparison does not replace the query product's independent
    assessment and is not an absolute ranking.
14. Actively check available linked post-transplant data for relevance and
    eligibility; propose the questions/resources and execute only when included
    by user approval. Graft evidence is independent and never backfills
    pre-transplant scoring, calibration or judgments.
15. Default delivery includes a result page, concise conclusion and downloadable
    full report bound to the same analysis version, with figures, methods,
    sources, limitations, next actions and explicit incomplete/unassessable parts.
    Do not automatically publish or share.
16. Fact corrections first record the change, expose affected dimensions,
    comparisons and report versions, then propose a partial update plan. Recompute
    only after user confirmation; retain previous versions and reuse unaffected
    evidence. This differs from autonomous checks under unchanged facts/scope.

Condense docs/README.md to a navigable index, README.md to current purpose/status/
entry points, and docs/tool-packages.md to a question-led tool index that links
canonical Tool Cards and actual evidence rather than duplicating their contracts.
Align docs/agent-integration.md, docs/web-preview.md and the documentation guide;
add a concise decision-log entry for approved autonomy/reference and server/public
boundaries without copying the full workflow.

Retire completed construction diaries from the active tree:
plans/web-full-chain-integration.md, plans/web-scientific-input-design.md,
plans/tool-runtime-contract-cleanup.md, plans/p0-05-hard-count-accounting.md and
plans/p0-06-unresolved-observations.md. Extract any unique stable/current fact
first; retain unresolved scientific work in the existing
plans/product-evidence-validation.md. Original histories remain in Git and have
been privately archived. Inspect linked protocol design/plan documents: retire
only completed implementation diaries, preserving unique approved BPL design
where it remains authoritative. Fix all affected links and stale plan statuses.
Do not delete validation records merely because they are old. Shorten package
READMEs only when genuinely redundant; retain the repository-required links.

Validation: run the repository check and diff whitespace check in this worktree;
inspect the current-flow/target distinction and all sixteen requirements.
Report before/after tracked file count and documentation/plan lines and bytes.
If the checker needs adjustment, preserve its privacy, orphan/link, package and
file-budget safeguards rather than weakening them. Full pytest is the controller's
integration gate, not required for pure documentation edits.

## Task 2: Consolidate proven-equivalent figure code

Preserve the public artifact contract and all existing differences in renderer
configuration, plot semantics and SVG security policy. Find the identical
_render_payloads bodies in P0-07 through P0-10 and replace only those copies with
one small shared implementation. The P0-11 and P0-12 SVG sanitation bodies are structurally identical, but P0-12
additionally permits stroke-dashoffset. Their security policies are not equivalent;
leave those implementations unchanged in this pass. Do not unify differing
rendering variants via flags or create a general framework.
No changes to Pydantic contracts or scientific models.

Add failing behavioral tests before code changes, then verify real figure export
formats and metadata, byte-equivalence with the pre-refactor rendering behavior,
and figure closure on success/failure. Preserve existing SVG security regression
coverage without changing either policy. Include the shared implementation in existing renderer provenance/
configuration identity so changed shared logic cannot silently retain old hashes.
Use existing test organization where possible. Run focused renderer/security
regressions and report RED/GREEN commands/output. Keep differences explicit.

## Task 3: Verify integration and retire archived operational clutter

Controller-owned. Verify old PR changes are absorbed rather than merge them.
Preserve exact public/private heads in verified server archives and record a
private recovery map. Close superseded PRs with precise evidence and delete only
their verified obsolete remote topic branches. Keep main protected and publish
this cleanup through a separate PR without merging.

Verify local snapshot contents and refs before removing local code copies; retain
the local workspace directory only as a non-code pointer if needed. Clean or
archive inactive server branches/worktrees only after checking clean state,
reachability/absorption, archive coverage and running-process bindings. Do not
stop or relocate live deployments or erase private scientific records.

Run the complete engineering gates after integrating Tasks 1–2:
pytest, CLI list, knowledge validate, repository check, diff whitespace check;
perform public privacy/link checks and inspect the resulting tree/branch map.
Record what cleanup proves, what science/Agent workflow remains unverified,
the remaining PR/merge boundary and recovery locations in the proper private
operations record. Public evidence contains no server paths.
