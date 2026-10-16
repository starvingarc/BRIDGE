# Biological interpretation and research harness

Status: `scoped_engineering_acceptance_passed; literature_and_human_review_pending` for the evidence-bound extension. Earlier bounded-release evidence is retained below. Issue: the development follow-up.
Baseline: `054ff6e3`. The initial implementation was merged in PR #35; the evidence-bound extension was merged in PR #55. Release identity and deployment are recorded separately under the release process.

## Outcome

A researcher should receive a concise biological argument: what the observations
suggest about the intended cell product, why the proposed explanation fits, which
alternative remains plausible, and what observation would distinguish them.
Measurements remain available in the results tables. Interpretation adds reasoning
rather than repeating those tables or listing generic disclaimers.

The approved scope includes product context, question-driven public literature
retrieval, traceable report references, and a shorter model-facing prompt.
Implementation stays in the existing Python application and registered analysis
runtime. Deployment and scientific qualification are separate.

## Baseline causes and reference design

At the baseline, the assessment call in `src/bridge/web/assessment.py` passed the question,
options, aggregate evidence and blockers, but not a complete allowlisted projection
of the confirmed biological background. `research_context.py` adds that background
later when assembling the report. The baseline explanation therefore preceded information
that ought to guide it.

The local knowledge snapshot supports method discovery and provenance.
Its records are not a biological literature synthesis; baseline assessment generation
did not invoke its search API or an external literature provider.

A captured synthetic JSON request at the baseline contains 25,683 characters in
the system message: 9,940 in the assessment instructions before the schema and
10,744 in three automatically loaded workflow bodies. Error recovery instructions
are present even without an error. These are character counts, not token counts
or real-case cost measurements; the capture used a mocked HTTP transport.

The upstream reference is official DeepSeek Harness, commit
`5badb15009ae1756c3afe0ae0cef1faafc290ccc`. Reuse its division of responsibilities:

- [Prompt assembly](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/core/system-prompt/README.md):
  stable instructions, current context and available schemas have separate owners.
- [Skill loading](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/skill/tool-skill/src/index.ts):
  publish a small catalog and load the relevant body through a scoped capability.
- [Search provider](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/web/web-search-deepseek/README.md):
  accept structured source records, expose explicit failures, and record the request;
  search-provider prose is not source evidence.

These are architectural references, not a dependency migration. No Cordis runtime,
general plugin framework or extra coding-agent tools are introduced.

## One bounded assessment loop

1. Build current biological context from confirmed intake and source-bound
   definitions: species when supplied, intended lineage, expected stage, sample
   context, assay, biological replicate information and the question.
   Unknown facts remain unknown. Product names, private protocol text and sample
   identifiers do not enter the search request.
2. Let the model identify the consequential biological question using the current
   observations and select a literature search from the permitted capabilities.
   Execution and report preparation continue through existing registered options.
3. Search a named public literature provider; read selected abstracts or licensed
   passages, assess applicability, and freeze the exact material used.
4. Produce a small set of evidence-bound interpretations with separate sample and
   literature references. A result may justify a question rather than a mechanism.
5. Generate the report from the same graph, background, interpretation and
   literature snapshot. A later search or corrected fact creates a successor version.

The model chooses the next useful action within the approved budget. The server
owns admissibility, network destinations, numerical integrity, source identity,
cancellation and persistence. A search is not a biological measurement or a vote
for the product.

## Prompt and context contract

Extract assessment prompt assembly from `provider.py` into a focused module.
Keep transport, parsing and model settings in the existing provider. Do not add
an extensible plugin registry merely to assemble a few strings.

The stable instruction contains role, scientific task and the distinction between
sample observations, external knowledge and proposed interpretation. Tool schemas
describe arguments; current context supplies facts, available actions and sources.
Only the current failure contributes repair guidance. Transport errors do not
become research context.

Candidate core instruction, to be evaluated rather than treated as a guarantee:

> You are BRIDGE's biological research analyst. Answer the research question in
> the context of the intended cell product and confirmed experiment. Use current
> measurements to develop the strongest defensible biological interpretation,
> explain the mechanism that connects evidence to the question, consider a
> plausible alternative, and identify a discriminating observation. Use the
> available literature capability when external knowledge would change the
> interpretation; assess each source's applicability. Keep sample observations,
> published findings and proposed explanations distinct. Cite the supplied
> records, use qualitative predictions for unmeasured outcomes, and state only
> uncertainty that affects the judgement. Write concise prose for researchers in
> the question's language. Select one available action within the supplied scope.

Hard clinical/release boundaries remain briefly stated once; deterministic checks
continue to enforce available actions, citation roles, budgets and release state.
The native tool path receives tool schemas once. The JSON path retains the
minimum machine-readable output contract without repeating the same action and
citation catalogs in prose, schema and context.

Use stage-specific workflow guidance instead of concatenating the complete
product-assessment, evidence-reasoning and research-reporting bodies each turn.
Record the actual guidance hashes. Interpretation receives the relevant biological
reasoning guidance; report handoff receives its short handoff instruction.

Acceptance targets for the same synthetic request: assessment instructions at most
3,000 characters and assembled system content at most half the baseline.
Measure request tokens on the configured model when available, and separately
report dynamic evidence/schema cost. Preserve both supported action protocols.

## Literature capability and privacy

Add a focused literature service with a typed request/result boundary, injected
through the existing application assembly. The initial provider is the
[Europe PMC articles REST API](https://europepmc.org/RestfulWebService), including
PubMed-indexed records. Use its structured bibliographic results and read the
available abstract before citing a biological finding. An article title or search
snippet is a discovery lead, not support for a mechanism.

The approved assessment scope includes whether public literature search is enabled
and its budget. Existing saved scopes default to disabled. New consent displays
the public-search scope alongside the existing result-sharing setting; a resume
cannot silently expand either. Initial limits: three queries, five discovery hits
per query and six read sources per assessment. Resuming does not reset counters.

The model selects public concept references supplied by the server: reviewed
cell-type/species terms, public genes or named biological processes, plus a
bounded research focus. The backend composes the external query from those
registered public terms. No arbitrary free-form query, URL, private fact value,
sample count or upload name can be copied into the external request. A missing
public concept requires a reviewed public-term addition; a regex redactor does
not grant permission to send a private string.

Use a fixed HTTPS provider origin, explicit time/response-size limits and no
redirect following. Fetch only provider identifiers returned by search. Do not
download arbitrary PDFs or silently fall back to a different provider. Retrieve
outside the session lock, reserve budget before dispatch, and bind completion to
the original scope revision/control epoch so cancelled or stale results cannot
enter a newer assessment.

Search results distinguish complete, partial, no-results, unavailable and disabled.
Persist bounded request/response receipts and source content hashes in private
storage. A network failure preserves existing measurements and permits an honest
limited interpretation. It never creates a literature finding.

## Source and interpretation contracts

Separate three objects with explicit versions:

| Object | Owner and minimum content |
|---|---|
| Biological context | Confirmed input revision and allowlisted facts; no inferred maturity or unstated replicate count |
| Literature snapshot | Provider/query identity, retrieval time, PMID/PMCID/DOI when present, title/date, canonical source URL, content level, permitted read material, hash and retrieval status |
| Interpretation | Current graph and context binding, statement, sample evidence references, literature references, applicability rationale, competing explanation and discriminating expected observation |

Bibliographic identity comes from the provider, never the language model. DOI/PMID
deduplication identifies the same work; distinct methods or papers are not assumed
independent. Missing abstracts/full text remain explicit. Preserve supplied
publication and retraction/correction metadata; do not assert their absence when
the provider did not return it.

Literature gets its own current-turn reference namespace and frozen binding.
A paper cannot fill an `evidence_aliases` slot for a sample measurement. The model
must cite a read source and explain which aspect of its species, lineage,
developmental window or experimental setting applies. Source applicability is
proposed interpretation, not automatic scientific validation.

Extend the report context and research snapshot with new versions. Preserve
legacy 0.3 parsing and hashes; do not add default fields to old objects before
checking their digests. Historical interpretations and reports remain immutable.
The new interpretation and report bind the exact literature material used;
refreshing the live source cannot alter a saved explanation.

Deterministic validation checks source existence, read-content identity, binding
and version consistency. It does not claim to verify biological entailment.
The report labels proposed interpretation appropriately and supplies source links
near the relevant claims; detailed provenance remains in its existing disclosures
and audit artifacts. The ordinary results tables retain their measured values.

External findings support a new research interpretation version. They do not
change existing MeasurementSpecs, reference roles, score thresholds, source
measurements, formal qualification or deterministic release decisions. Update
the relevant contracts to distinguish this research-literature path from formal
frozen-knowledge evaluation; do not silently relax the existing rules.

## Ownership and delivery surface

- `web/provider.py` and a focused prompt-assembly module: short instructions,
  action schemas and contextual repair messages.
- `web/assessment.py`: scope, budget reservation, current-state checks and the
  existing continuation loop.
- A small literature module: provider request, normalization, source reads and
  explicit failure results; no access to raw matrices or session internals.
- `web/evidence.py` / `web/research_context.py`: allowlisted model projection
  and report context binding, each through explicit values.
- Existing research report contracts/renderer: versioned literature references,
  source-backed snapshots and reader presentation.
- Existing scope approval UI: disclose public retrieval and its limits without
  exposing tool IDs or source-schema terminology to researchers.

Only the necessary contracts, stable documentation and tests change.
`docs/privacy-and-provenance.md`, the PRD interpretation/network sections and
the affected report cards must agree before integration.

## Verification and completion

Engineering checks cover both model protocols, zero versus missing values,
current citation roles, invalid/unread literature citations, hostile source text,
provider errors, DOI/PMID deduplication, budget/cancellation races, private-field
exclusion, history compatibility and identical sample measurements after rendering.
Use synthetic or authorized public fixtures, not private case files in the repository.

Then compare old and new interpretation on the same approved saved input and
evidence graph. Keep model/settings, request sizes, source snapshots and outcomes
available in private records. Bound the comparison in advance; do not repeatedly
retry until one answer looks good. Network reachability and a successful response
are separate from reader acceptance.

Reader acceptance requires:
1. An interpretation addresses the intended biological question and distinguishes
   what follows from the actual observations from what would require another result.
2. A biological mechanism connects the observations to the hypothesis; a list of
   measured programs alone does not pass.
3. Literature supports the specific reasoning and its applicability is explicit;
   a citation count or a source list alone does not pass.
4. A concrete qualitative observation distinguishes the leading explanation from
   a plausible alternative. The suggestion does not imply an unapproved experiment
   has run or prescribe an unsupported intervention.
5. Results remain concise, with concrete uncertainty rather than repeated general
   disclaimers.

Engineering tests, source retrieval and human biological review are recorded
separately. Human interpretation acceptance and the pre-existing visual review in
Issue #32 remain distinct from scientific method or product qualification.

## Implementation sequence

Execute inline with superpowers:executing-plans; the approved design above is authoritative.
All implementation and checks run in the controlled development checkout.

1. **Concise assessment instructions and background.** Add a small assessment prompt
   module and a confirmed-intake projection. Select one workflow for the current phase,
   include only the current error recovery, and let schemas own action shapes.
   First capture provider requests in both protocols with length and private-field
   regressions; then implement. Verify research-skills, provider and assessment tests.
2. **Bounded literature service.** Implement reviewed public concept references,
   fixed-origin Europe PMC discovery/abstract reads, source deduplication, content
   hashes and explicit disabled/no-results/unavailable/partial states. Start with
   transport boundary tests for query projection, redirects, limits and malformed
   responses. No raw product text enters a search.
3. **Assessment integration and consent.** Add separate approved search/read budgets,
   typed actions and capability context. Reserve before network I/O; reconcile epoch
   afterwards. Test exhaustion, cancellation, invalid refs, legacy disabled behavior
   and real request dispatch. Expose the consent and search status in the assessment UI.
4. **Versioned interpretation and report sources.** Add new explanation/context/snapshot
   versions with literature references and applicability, preserving historical hashes.
   Render biological reasoning and read-source bibliography; verify historical fixtures,
   tamper rejection and report/UI linkage.
5. **Acceptance and delivery.** Compare one bounded old/new model run on identical saved
   inputs. Record engineering and biological quality separately, update maintained
   contracts and privacy docs, run affected integration tests and frontend build.
   Review the full branch before updating the draft PR; do not merge or deploy.

Shared interfaces: tasks 2–3 use provider-owned source refs and immutable read bundles;
tasks 3–4 use the new explanation version and approved-scope binding. Task 1 never
changes scientific measurement semantics. Exact new version numbers follow the
current schema registry; old model defaults must not change old content hashes.


## Interpretation consistency admission

A prompt-only attempt did not resolve the saved reader failures. The admission
path for literature-enabled explanations now includes one bounded model review
after deterministic action/citation validation and before saving the explanation.
Provider owns the request/response boundary; the review module owns its issue
vocabulary and proposal-field binding; the coordinator owns budget reservation,
cancellation and admission. Report schemas and scientific measurements are
unchanged. Legacy scopes without literature keep their previous behavior.

The reviewer checks the supplied facts and proposed prose, including rivals and
predictions. It cannot establish scientific truth. A detected issue, malformed
reply, network failure or unavailable budget blocks the proposal. Explicit
continuation receives the bounded private rejected draft and exact field-bound
criticism, with citations rebound to current request aliases, and consumes the
existing scope budget. Transport failure does not erase pending criticism;
missing current evidence discards the draft. Review calls are not hidden retries.
No late proposal is saved or rebound after cancellation. Final reader acceptance still requires direct review
of the actual output, including unknown replication, aggregate marker semantics,
stage distinctions and decisive follow-up observations.

## Review boundary

The implementation adds the bounded retrieval/report contracts above and retains
legacy report compatibility. Matched synthetic provider requests reduced the
JSON system message from 25,678 to 11,171 characters; the instruction portion
fell from 9,940 to 2,561 characters. These are mock-transport character counts,
not a biological-quality or production-token benchmark.

The bounded saved-input comparison and two targeted diagnostic repeats did not
meet reader acceptance: invalid action/citation choices, skipped source reads and
unsupported biological interpretations were observed. The original case was not
changed and no rejected explanation was admitted as a report. Prompt/context
changes and public retrieval do not by themselves establish interpretive quality.
Further reader acceptance remains open in Issue #34; existing visual acceptance
remains in Issue #32. Keep the PR in draft until the unmet criteria are resolved.

The first browser-driven saved-input run exhausted its eight-turn model budget
with an unsupported action and no new report. Its failure record is retained.
Targeted repairs cover abstract retrieval, attempted-query context and citation
records versus result containers.

The current engineering flow has completed with explicit recovery. Assessment
requests for the supported DeepSeek V4 family retain bounded thinking with a
12,000-token response cap and a 180-second timeout; ordinary chat and report
drafting keep their existing behavior. The approved model-turn budget and
fail-closed validation remain unchanged. The results-ready view also preserves
the backend-authorized continuation button needed to generate the report.

A fresh isolated saved-input run used five of eight model turns, including one
HTTP 502 followed by explicit continuation in the same scope. It read two
abstracts, admitted three structured hypotheses, and generated one report after
explicit continuation. The report exactly retained the latest interpretation
and literature bundle; all eight report artifact hashes passed. Existing
measurements, the original case and 598 existing immutable files were unchanged.
This was a recovered end-to-end flow, not an uninterrupted run or a biological
quality pass. The frontend continuation repair was loaded after interpretation.

Focused validation passed 141 backend tests, 53 frontend tests, the frontend
production build and repository checks. Reader review still found excessive
numerical restatement, an unknown replication state expressed as absent, and
insufficient separation of lineage commitment from maturity. Issue #34 remains
open and the PR remains draft; scientific qualification is not established.


## Bounded consistency review acceptance follow-up

Reader acceptance remains unmet. A prompt-only saved-input replay retained the
known errors. Literature-enabled explanations now require a bounded, separately
charged consistency review; review failure or findings block admission. The
initial full-context review exhausted its response cap. The reviewer projection
now keeps cited records, confirmed background and program semantics while marking
uncited measurements and repeated tables as omitted. Generation keeps its full
evidence projection. Model review does not establish scientific qualification.

The subsequent browser scope retained a twelve-turn budget and actual failures.
Native generation at turn seven produced a proposal; its real turn-eight review
rejected unsupported observations, aggregate-to-identity claims and phase-to-
division claims. Duplicate request bindings then exposed a pre-existing mismatch:
session writes could exceed the size accepted by reads. Writes now enforce the
same limit atomically; review rows reference their proposal maps. The isolated
receipt was recovered from the actual validated response with a private audit,
preserving budget/history and admitting no proposal. This was fault recovery,
not uninterrupted acceptance. Two explicit continuations returned no native tool
action and were rejected. Work stopped at ten of twelve turns, with no new
interpretation, report or scientific measurement. All 1,163 source-case files
matched their pre-run hashes. Failed scopes and private receipts are retained.

Final provider/review coverage passed 70 tests. Service/review coverage passed
119 of 121 on the broader run; the two old provider fixture expectations were
updated to the existing token/prompt contract and both passed targeted reruns.
The earlier affected-suite run passed 256 of 258, with the two stale explanation
fixtures corrected and passed in a three-test targeted rerun. No whole-repository
test pass or final-model quality pass is claimed. Static repository and diff
checks passed. Existing frontend evidence is reused because it did not change.
The PR remains draft and Issue #34 stays open. The decisive remaining blocker is
reliably obtaining a revised, structurally valid interpretation from the current
provider path and then passing direct biological reader review.


## Private research release 0.3 completion scope

The release target is the existing private single-operator research workflow.
This work repairs targeted revision after a blocked consistency review, verifies
an isolated real-case explanation and report, and prepares an immutable package
with exact source and rollback identity. It does not claim public multi-user
readiness, scientific qualification or coverage of every PRD capability.

Acceptance requires synthetic failure/recovery and privacy checks, real provider
revision followed by the same review gate, report and browser checks, full
release tests, and installed-artifact verification. Repository integration and
release approval remain separate from engineering completion. The original case,
measurements and previous acceptance receipts remain immutable.


Large historical per-turn maps were still close to the bounded session JSON
limit after deduplicating review rows. The 0.3 storage change externalizes only
these private maps with content hashes and bounded verified reconstruction;
legacy inline files remain readable. It preserves the original history and
requires the paired pre-upgrade session backup for a downgrade. Acceptance
covers roundtrip, history preservation, tampering, missing files and symlinks.


### Focused revision follow-up

The full action context remained in every repair request, even for a small number
of quoted findings. Revision now narrows the model view and citation choices to
the existing argument's records and read abstracts, preserving tool defaults,
units, denominators and missingness. The full context still controls admission.
The repair instruction targets unsupported premises and dependent predictions,
rather than adding caveats after the same claim. Initial analysis is unchanged.
Synthetic wire tests cover both JSON and native protocols, input immutability,
retained cited gaps and records, and exclusion from both context and choice enums.
Real provider acceptance and report handoff remain required.


Text-only findings additionally use bounded field replacements rather than a
complete regeneration. Citation arrays and literature uses stay fixed, edits are
reassembled into the existing action contract, and final review remains mandatory.
Literature findings also use bounded per-use prose edits, preserving source identity and qualification. Transport/schema failure retains
the original pending draft and consumed budget. DeepSeek v4.1 names use the bounded
reasoning profile, with effort explicit rather than dependent on gateway defaults.


An explicit continuation after an unavailable interpretation review retries the
validated private draft without another generation. The retry consumes one model
turn, reserves fresh private citation maps, and preserves its original proposal
link and all failed-turn history. Admission revalidates the full current context;
review failure retains the draft and consumes the turn without admitting it.


Review distinguishes measured facts, tentative explanations and prospective
experiments. Unknown future results do not invalidate a proposed check; its
outcomes must instead discriminate the named rivals. Co-occurrence alone and
reproducibility without a matched contrast are insufficient discriminators.
Exact field/quote binding remains mandatory; malformed reviews fail closed.

An unavailable executable tool does not suppress a prospective validation design.
When requested, the explanation supplies rival-specific outcomes independently
of the nullable tool choice, while keeping proposed observations unmeasured.

### Context and completeness repair

The initial request repeats large measurement and summary tables; focused review
still includes uncited sources. Supported hypotheses can also omit prospective
validation, allowing a structurally incomplete draft to consume review turns.
This repair preserves the existing public interpretation version and historical
readability. Provider-only table encoding must roundtrip exactly, including
missing fields versus explicit null, values, states and citation aliases.
Review retains cited records, defaults and source context; omitted tables and
sources do not imply absence. Deterministic completeness findings precede paid
review and are stored with the private pending draft. They route through the
existing field repair without changing citations or refunding failed calls.
The coordinator remains the sole owner of reservation and admission. No new
review cache, provider fallback or public scientific qualification is introduced.

- [x] Reproduce lossless wire, review projection and missing-design failures.
- [x] Implement bounded projection and completeness-to-repair admission.
- [x] Verify targeted regression, budget, cancellation and privacy behavior.
- [x] Validate known-bad and known-good provider behavior on the reduced context.
- [x] Continue the existing authorized case through interpretation and report;
      preserve consumed budget, prior history and original input hashes.
- [x] Run applicable release checks, inspect the installed build, and document
      the actual reader-facing result and any remaining limitation.


Literature repair uses the same bounded field patch path as hypothesis prose.
Only existing rationale and applicability fields may change; source references,
qualification, citation arrays and all unchanged hypothesis fields stay fixed.
This prevents a source-summary correction from regenerating the argument and
losing its validation design. Review also checks unsupported relative likelihood
and whether rival-specific predictions follow from the stated hypotheses.


### Private candidate acceptance outcome

The private candidate completed explanation, review, bounded field repair and
report generation for one focused core hypothesis. Prior scopes, spent model
turns and report history remain preserved. Other domains remain measurements
and evidence gaps rather than additional generated hypotheses. A fresh process
restored the same interpretation and report receipt; all report downloads and
served frontend assets matched the recorded hashes. The reader opens the latest
report by default and retains earlier reports in history.

Backend coverage was assembled across bounded test segments: 3,188 passed and
45 skipped after fixture corrections, with a further 114 affected-module checks.
The final frontend passed 240 tests and its production build. This is not a claim
of one uninterrupted full-suite run at one commit. The installed package was
checked against its wheel, and repository static checks passed.

Longer multi-hypothesis requests can still exhaust the finite model output or
request-time limits. This acceptance establishes the focused workflow, not
unconditional success for arbitrary questions. Reader inspection by the coding
agent does not replace maintainer/user acceptance, independent biological
validation or scientific qualification. Formal publication remains ineligible.


## Evidence-bound interpretation and saved continuation

Status (2026-10-08): `scoped_engineering_acceptance_passed; literature_and_human_review_pending`. A bounded saved case passed model, report, download, browser and cold-restart checks. This is not a release or scientific qualification claim.

### Implemented behavior

- Repeated exploratory executions retain distinct execution identities. Evidence
  revisions preserve prior receipts, and reports resolve the exact producers
  bound to their graph content. Revision context admission uses the same bounded
  projection and lossless encoding sent to the provider.
- Models author supports, limits, contradicts and missing_for relations with
  reasons and applicability. Citation identity, record state, input revision and
  graph version remain deterministic constraints.
- Exact feature-axis queries distinguish input membership from expression
  detection and biological identity. Coverage facts enter review and repair and
  freeze with accepted explanation v1.2.
- P0-10 0.6.0 and context/snapshot v0.5 carry version-bound interpretation graphs.
  The existing evidence view includes proposed hypotheses, relations, rivals and
  prospective observations. Reports lead with biological reasoning and expose
  measurement details, relation reasons and coverage in disclosures.
- Native reviews require the review function even for an empty issue list.
  Review/repair have bounded reasoning and response capacity; invalid, truncated
  or unavailable reviews still block admission. Review reasons allow 1,200
  characters, with precise length diagnostics.
- An unresolved draft can be carried into a newly authorized scope only when its
  source identity, draft digest and non-budget bindings match. Prior history and
  usage remain intact. This narrow continuation path excludes literature-enabled
  sessions and does not copy acceptance status.

### Verification evidence

The [version-bound engineering record](../docs/validation/interpretation_evidence_20261008.md)
records P0-06 0.11.1 and P0-10 0.6.0, including the review fixes, scoped acceptance and broader outstanding gates.

Engineering checks are distinct from the real-model and scientific gates. Counts
below overlap; they must not be added as independent coverage.

- Interpretation/report binding: 16 checks; registry contracts: 12 checks.
- Frontend interactions: 36 checks and production build.
- Provider/relation feedback: 60 checks; review-length adjustment: 12 checks.
- Additional assessment regression run: 127 passed and seven failed initially.
  After correcting continuation projection/assertions and updating legacy live
  schema examples, all 14 selected regressions covering those failures passed.
  Unchanged heavy computations were not repeated.
- Static repository and patch-format checks passed. Publication preparation
  preserves the verified code, schema, fixtures and frontend; only documentation
  and commit organization change.
- Controlled saved-case checks confirmed original evidence preservation and
  exact recovery of the pending assessment after a cold restart. No scientific
  calculation was rerun during the latest explanation-only continuation.

### Scoped merge acceptance and remaining work

The earlier bounded continuation used six calls and ended with three findings:
an unsupported direction for an unreferenced ratio, an incomplete discriminating
prediction and inconsistent interpretation of a candidate-label fraction. That
draft was not admitted.

The newly authorized continuation at `e9212820` used two official model calls
within a six-call cap. Repair and consistency review resolved those findings;
the accepted v1.2 explanation has three hypotheses, 17 relations and 15 feature
queries. One P0-10 execution produced a v0.5 report bound to that explanation,
scope and graph version. All six public downloads passed checksum verification;
the prior 23 receipts and 1,374 evidence files were unchanged.

The run used a separate acceptance process over the original saved case, after
stopping its idle earlier acceptance process. A copied case was rejected because
absolute source paths belonged to the original session; no path guard or binding
was rewritten. Literature was disabled. Model review, missingness and scientific
boundaries were not relaxed.

Browser acceptance at `553480ae` verified report explanations, relation reasons,
coverage, membership semantics and graph-version selection. It includes a fix for
the evidence view rejecting valid reports above 2 MB, with 67 frontend tests.
A controlled cold restart preserved exact session bytes and all 1,396 artifact
hashes without new model calls. The version-bound record gives the test and
baseline limits, including the earlier unmatched whole-session baseline.

This completes the scoped extension merge gate. Broader literature-enabled
acceptance and independent human-reader assessment remain open in #34.
No deployment, biological validity or scientific qualification is asserted.
Raw inputs, sample identifiers, model responses, private receipts, screenshots,
credentials and deployment configuration remain outside the repository.


### Latest bounded literature continuation

On 2026-10-09 the current saved case successfully read two public abstracts, but
the 12-call generation/review/repair budget ended with an unadmitted draft and
no new report. The last review retained four findings about discriminating
predictions and evidence-relation direction. The
[version-bound record](../docs/validation/interpretation_evidence_20261008.md)
records the provider corrections, spent budget and unchanged prior evidence.

The next acceptance must resolve those content issues and produce a bound
report for an independent reader. More prompt retries, a larger output cap or a
successful source read alone do not meet that gate. This plan and #34 remain open.
