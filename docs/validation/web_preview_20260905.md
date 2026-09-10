# Private conversational Web preview — validation history

## Protocol formalization closeout — 2026-09-10

The source implementation and isolated installed acceptance for source-backed
protocol formalization completed without changing scientific tools, facts,
original inputs or deployment state.

| Check | Exact result |
|---|---|
| Installed backend | 209 tests passed, including 119 protocol cases with the pinned BPL compiler |
| Browser client | 102 tests across 11 files passed; typecheck and production build passed |
| Configured-model browser path | A synthetic missing-wait case preserved unsure history, accepted an explicit two-hour user answer, created a new unreviewed version and required version-bound human review |
| Representation | The final BPL used wait(duration: 2 h); readable content identified the user-supplied duration and retained both source and user-answer references |
| Review boundary | Independent bounded reviews cleared source/fragment/audit and active-answer accounting; literal participation and compiler success remained separate from semantic or biological proof |

The tested path establishes one authoritative fragment representation, bounded
repair, source accounting and review-version invalidation. It does not prove that
all protocol omissions were detected, that the experiment was executed, that a
normal private deployment was upgraded or that downstream product assessment is
qualified. Failed earlier attempts remain failures in history rather than being
relabeled by this closeout.

## Current closeout — 2026-09-08

The sections below preserve dated validation records, not competing descriptions
of the current preview. Current functionality and acceptance boundaries are
summarized in the [Web interface contract](../web-preview.md); unresolved
scientific gates are tracked in [Product Evidence Validation](../../plans/product-evidence-validation.md). That validated increment includes explicit
stop/input confirmation, selectable JSON/native actions, opt-in canonical evidence
summaries, bounded Parquet previews and privately confirmed product intake.

A fresh genuine-data/current-model journey exercised upload, typed product draft,
explicit fact confirmation, a separate next-stage plan, and independently approved
QC execution. Its explanation reused canonical QC evidence without a second run.
Desktop/mobile presentation, refresh retention, bounded table preview and original
download integrity were checked. Missing product/design facts stayed unknown;
no formal scientific objects or complete downstream product assessment were made.
Measurements, input identities, source hashes and deployment details remain private.

The dated evidence below retains the tested scope and limitations. Recorded earlier
full-suite/review results apply only to their dated revisions. No new independent
review or unchanged-suite replay was performed for this closeout; required CI
binds the exact public PR head. This is an installed entry-flow increment, not a
validated score, P0-10-verified narrative, complete genuine twelve-tool chain or
release approval.

## Initial preview — 2026-09-05

### Question and scope

Can a researcher upload an expression file, declare its assay and count
semantics, approve a plan, and inspect the actual input-QC evidence within a
persistent conversation?

The Web route covers P0-01 input QC. Existing CLI/SDK packages remain callable;
this release does not construct the additional scientific objects needed for
a full-chain product evaluation.

## Evidence and observations

A private, authorized real-data browser scenario exercised login, conversation,
upload, clarification, exact-plan approval, actual P0-01 execution, figure and
table display, evidence downloads, model follow-up, page refresh and a narrow
viewport. The final fresh-session scenario passed without API mocks or browser
page errors. All registered download contents matched their private receipts;
workflow events recorded submission, claim and successful execution.

Scientific inputs, screenshots, transcripts, resource identities, checksums,
measurements and deployment details remain outside the repository. Missing
biological design was not filled in. A successful QC execution does not mean
that every QC metric is available or that a product has passed an assessment.

During validation, a provider returned an empty successful HTTP response when
a second system message followed the user turn. Keeping one leading system
message with the same status context restored real follow-up responses. A
request-order regression test now covers this compatibility requirement.
Provider failures remain explicit; no canned model reply is substituted.

## Engineering verification

| Check | Evidence |
|---|---|
| Service and exact ancestor trust | 104 focused server tests passed |
| Browser client | 16 tests and production build passed |
| Installed Python wheel | Service imported from the installed package, not the source checkout |
| Live browser flow | Final fresh conversation and actual QC flow passed; desktop and narrow layout inspected |
| Artifacts and events | Registered content integrity and persisted workflow transitions checked |
| Repository gates | Policy, knowledge, figure registry and whitespace checks passed on the integrated server tree |
| Full regression | The integration predecessor passed the full server suite; changed service/storage and client paths were retested after review fixes. Required CI runs the full suite on the PR revision before merge. |

Reproduce public engineering checks with the documented Python and Node setup:

~~~bash
python -m pytest -q
python -m pytest tests/test_web_service.py tests/test_private_path_trust.py -q
npm --prefix web ci
npm --prefix web test
npm --prefix web run build
python -m build --wheel
python -m bridge.toolkit.cli list --json
python -m bridge.toolkit.cli knowledge validate
python -m bridge.toolkit.cli figures validate
python scripts/check_repository.py
git diff --check
~~~

The private real-data browser scenario is separate from synthetic automated
tests. Its pass establishes this interaction path, not broad biological
performance or arbitrary-provider reliability.

Storage, service and client changes received independent scoped reviews.
The final integration review found no Critical or Important issue. Merge is
conditional on the required checks for the exact PR head.

## Limits and next work

- This is a single-operator private preview, not a public multi-user service.
- Only H5AD uploads and explicit raw-count/assay declarations are supported.
  No biological replicate or reference metadata is inferred.
- The provider receives conversation and minimal execution status. It does
  not receive the uploaded matrix or tool-owned biological measurements.
  Model replies are not passed through P0-10 claim verification in this preview.
- Actual numerical evidence lives in tool-owned artifacts. Path-redacted JSON
  display downloads are not canonical downstream inputs.
- All scientific methods remain candidate/shadow; scores and scientific
  release status are unchanged.
- Full-chain input construction and evidence-grounded model interpretation
  remain follow-up work, with separate data-sharing and scientific controls.

See [Web setup and interface](../web-preview.md) and
[Agent integration](../agent-integration.md).


## Staged Web extension — 2026-09-07

The extension connects the existing P0-02 raw-count-compatible candidate path
and P0-12 explicit no-graft path after input QC. It preserves per-stage approval,
canonical receipts, historical plans and the privately entered source reference.
It does not connect the remaining nine Web input constructors or assert a V3
cell-state profile, a complete product-evaluation chain or scientific validation.

A fresh private real-data browser conversation exercised upload, explicit count
and assay declarations, QC approval, private source entry, cell-state approval,
explicit no-graft approval, actual tool outputs, follow-up, refresh, desktop and
narrow layouts. P0-01, P0-02 and P0-12 each produced a successful canonical
ToolRun. P0-12 received zero assets and zero structured inputs; its output
records missing graft evidence, not graft expression analysis. Registered
download bytes matched their private receipts. Every displayed figure card
loaded; the narrow context panel remained bounded and scrollable. No browser
page errors occurred; the initial unauthenticated session request correctly
returned 401. Private resources, results, screenshots and their hashes are not
part of this repository.

Validation exposed two provider-integration failures: an ambiguous readiness
summary prompted repeated requests for already-supplied inputs, and a gateway
returned tool-call markup as ordinary message content. The service now sends
bounded actual tool execution states and uses a strict JSON Action response
protocol. It rejects malformed or unrecognized responses rather than presenting
them as executed calls. Local eligibility and exact approval remain mandatory.
See the [JSON-mode requirement](../web-preview.md#privacy-and-interpretation).

| Check | Evidence |
|---|---|
| Installed Web service | 44 tests passed; two existing upstream deprecation warnings remain |
| Browser client | 24 tests and production build passed |
| Packaging and contracts | Installed wheel imports and source correspondence checked; 12-tool discovery and describe/input-contract calls verified |
| Fresh actual browser | Three connected stages, independent approvals, canonical receipts, all registered downloads, figure cards, refresh and narrow layout checked |
| Independent review | Backend, frontend and final integrated change reviewed; Critical/Important findings closed; blocked-only proposal confirmation corrected |
| Repository checks | Policy, knowledge, figure registry and whitespace gates passed; required CI binds the public PR revision |

The model receives execution status, not biological measurements. Chat replies
are not P0-10-verified reports. The first-stage integration remains separate
from full-chain acceptance, which requires real biological design/product facts,
faithful composition contracts and the remaining input constructors. Scientific
candidate/shadow states and null scores are unchanged.

## Contract-driven Web access — 2026-09-07

The input panel now exposes the current contracts of all twelve P0 tools. A
caller can select a mode, explicitly declare an uploaded H5AD, register named
scientific JSON objects, reuse compatible canonical outputs, save the selection,
and separately prepare and approve a stage. This extends Web access; it does
not automatically author all scientific inputs or establish a complete
real-data product evaluation.

### Verified coverage

| Evidence layer | Checked behavior | Boundary |
|---|---|---|
| Package-backed HTTP routes | Representative modes across all twelve tools use the actual planner, eligibility, exact approval, adapters and workflow receipts | Synthetic fixtures cover missing genuine prerequisites; not every optional method/mode is validated |
| Connected browser evidence chain | Fresh supplied objects → P0-08 canonical v2 result → P0-09 case graph → P0-10 verification → P0-11 artifact audit | Synthetic engineering scenario; P0-10's negative release decision remains intact; audit is not publication |
| Fresh real-data browser conversation | QC → candidate cell-state analysis → explicit no-graft record; input panel, inherited expression controls, history, figures, downloads, follow-up, refresh and narrow layout | No sample/capture facts or composition weights invented; no-graft is not expression-graft analysis |
| Packaging and client | Installed imports and source-byte correspondence, twelve-tool discovery and input contracts, frontend regression and production build | Engineering evidence, not biological calibration |

The browser test registers scientific files through the visible input controls;
it does not submit prebuilt ToolRequests or approve through a second execution
path. Canonical producer objects keep their original bytes, location and checked
bundle. Request-local binding IDs are supplied explicitly; graph manifests cannot
be uploaded as detached substitutes. Missing inputs produce named blockers.

Independent reviews found and closed four functional seams: successful
scientific reason codes incorrectly entering workflow failure events; canonical
object-version discovery and paired Schema/version checks; undeclared H5ADs
shown as compatible; and inherited mode asset contracts disappearing from the
client. The final fixes also corrected blocked-plan notices and a native HTML
matrix-location pattern rejected by Chromium's UnicodeSets grammar. Reviewer
and browser findings were followed by scoped checks, not scientific contract changes.

The private evidence retains complete conversations, canonical requests and
receipts, artifact integrity checks and actual figure screenshots. Resource
identities, data, private hashes, biological values and deployment details remain
outside Git. The required `repository-gates` checks bind the public PR revision.

### Regression environment

The installed-wheel server run completed with 1,883 passed and 64 failed tests.
All failures were in the synthetic private-path startup-policy suite: its
per-test policy reset omits the deployment's approved foreign-owned ancestor.
The failure log is retained. No path guards, permissions or assertions were
relaxed, and the server run is not reported as fully passing. The deployed Web
checks use the existing exact operator-approved ancestor configuration. The
required CI independently runs the unmodified full suite on a standard runner.

### Remaining limits

- Scientific JSON authoring is still explicit. The Web layer does not infer
  product definitions, biological units, state roles, soft mass or report claims.
- Genuine twelve-tool acceptance remains blocked by missing source facts and
  scientifically defined upstream/downstream inputs; engineering routing does
  not close those gaps.
- Model follow-up is status-grounded, not measurement-grounded interpretation
  or a P0-10-verified scientific report. Authoritative numerical results remain
  in the actual tool artifacts.
- This remains a single-operator private preview. Candidate/shadow, null scores
  and the existing scientific/publication boundaries remain unchanged.

## Genuine-conversation follow-up — 2026-09-07

A fresh actual-provider run reproduced two Web defects: statements about missing
unrelated metadata revoked a valid counts/assay declaration, and sparse mode
readiness context led the model to suggest unsupported input choices. The fix
uses a bounded unrelated-absence exception in declaration tracking and historical
assay lookup. Explicit retractions and cancellations remain conservative. Safe
provider context adds package-derived mode IDs and required object-role names;
mode selection is not evidence that the remaining inputs exist. No scientific
objects or selected resource values are added to model context.

The scoped Web/input/workflow suite passed 111 tests, with two pre-existing
dependency deprecation warnings. Independent review found no Critical or
Important issue. A fresh wheel's packaged source was checked against the reviewed
implementation, and package discovery, input contracts, knowledge/figure
registries, repository policy and diff checks passed.

The updated installed service then completed a new genuine-data conversation
using the configured real model API, without model or execution mocks. The
previously failing missing-metadata statement preserved the declaration epoch
and kept canonical QC reusable. QC, candidate cell-state analysis and the
explicit no-graft record executed with separate approvals; registered downloads,
figure loading, restored history and narrow layout passed. There were no browser
page errors or unexpected console errors. The sampled model replies no longer
invented unsupported comparison modes, but still listed internal object names;
this remains an expert-input preview, not a finished upload-only experience.

The genuine full-chain result remains incomplete. A read-only contract audit
confirmed that missing typed source lineage blocks a genuine V3 continuation.
Separately, P0-05 requires assignment mass not defined by the current producer
and P0-06 cannot losslessly represent source-conflict observations through its
current observation-state input. Neither gap is fixed by fabricating weights,
unknown labels or caller attestations. They require separately scoped module
decisions, not a silent Web-layer conversion. These blockers are distinct from
limited readiness, null scores and provider availability.

All actual input identities, transcripts, numerical outputs, screenshots and
content hashes remain private. This follow-up does not replace the earlier
full-server regression record or claim new full-suite success; required CI binds
the corresponding updated public head independently.

## Source-bound Web input closeout — 2026-09-07

The separately reviewed P0-05 count-only and P0-06 source-bound implementations
were integrated in the isolated Web branch for combined validation. The Web
change accepts only the two P0-06 v0.2 canonical artifact locators documented in
[Web preview](../web-preview.md). Same-session provenance, same P0-02 receipt,
artifact kinds, checksums and execution-time dependency integrity remain enforced.

A scoped independent review found an unhandled structured-checksum input.
The fix was reproduced through HTTP, then verified to return a bounded 422
without registering an object for arrays or objects in either checksum field.
The scoped re-review approved the fix.

Installed-package evidence is deliberately split:

- Combined revision `78c5ebcb`: 391 related module, Web, workflow and shared
  contract tests passed, with 58 recorded dependency warnings.
- Final fix revision `6e881861`: 129 Web-input and shared-contract tests passed,
  with 9 recorded dependency warnings. The scientific module sources are
  byte-identical to the combined revision; only the named-checksum validation
  and its tests changed.
- Both installations passed 12-tool discovery, 24 CLI describe/input-contract
  calls, knowledge/figure validation, repository policy and diff checks.
  Packaged source in the final installation was compared with tracked source.

This is focused installation evidence, not a new full-repository or
genuine-twelve-tool acceptance claim. The existing server-specific trust-fixture
limitation remains documented above. No startup trust guard or scientific
eligibility condition was weakened. Synthetic module/HTTP fixtures prove
engineering behavior only; actual-data/browser results remain separately bound
in private evidence.

## Conversation withdrawal follow-up: review blocked

A genuine follow-up about a missing plan reached prepare_analysis, but the
conversation layer treated unrelated negative wording as a withdrawal of the
earlier QC declaration. The immutable QC receipt then correctly failed the
changed-declaration check; this was not a biological readiness failure.

The bounded correction was developed and reviewed separately from scientific
input construction. Installed revision `078f19c1` passed 114 Web/input/workflow
tests. Review then found missed cancellation and coordinated-count negation.
Revision `9b3ab7e` addressed those examples and passed 119 installed tests, with
9 existing dependency warnings, plus discovery, 24 CLI interface checks,
knowledge/figure validation, repository policy and diff checks. All 349 packaged
source files matched the tracked source.

The final scoped review nevertheless found another Important regression:
`QC is complete, not all biological replicates are confirmed.` is incorrectly
classified as a withdrawal. A direct probe against the installed package
reproduced it. The candidate is therefore **not approved for deployment or merge**.
Passing tests do not supersede that open finding.

Further phrase-level fixes are paused pending an explicit interaction decision
for declaration changes and their confirmation. Existing services and historical
evidence were not changed. Full genuine-data acceptance remains incomplete.

## Explicit controls and genuine continuation — 2026-09-07

The owner approved replacing conversation-based declaration withdrawal with
explicit input review and exact confirmation. Ordinary chat no longer edits
committed metadata; stop fences later work immediately while an in-flight
non-interruptible outcome is retained. The preceding regex review stop is
superseded by this approved interaction, not retrospectively declared correct.

Source-backed column selectors and separately confirmed culture relationships
now support genuine QC and V3 cell-state outputs. They do not establish donor,
pooling or cross-timepoint facts, calibrated assignments or product validity.
The Web allowlist now accepts the three already-supported sample/capture/gene
column selectors through its existing staged confirmation path.

| Exact revision | Verification |
|---|---|
| `428ba2e6` | Integrated controls: 136 installed Web/input/workflow tests; client 50 tests, typecheck and production build |
| `a812b661` | Existing-column alignment: 137 installed Web/input/workflow tests, 9 dependency warnings |
| `c9f8df55` | Reply-envelope clarification: 86 installed Web-service tests, 2 dependency warnings; input/workflow sources unchanged from the preceding baseline |

The final installation matched all 350 packaged source files and passed discovery,
24 describe/input-contract calls, knowledge/figure validation, policy and diff
checks. Its complete client tree and built bytes match the validated control
revision. These are scoped checks, not a new full-repository pass; the earlier
server trust-fixture limitation and exact-head CI requirement remain open.

Real browser evidence is deliberately split:

- Resumed and fresh genuine inputs reached successful P0-01 and P0-02 runs after
  exact declarations and separate approvals. Missing-product-definition wording
  preserved canonical QC; requesting review and explicitly keeping inputs worked.
- The primary provider was unavailable, so the owner-authorized prior API was
  configured only in the isolated candidate. Post-tool explanation still failed
  intermittently. Prompt clarification and successful direct replays do not prove
  reliable browser follow-up; a history-envelope experiment was not deployed.
- A separate final-revision stop, refresh, desktop/narrow-layout and download
  inspection passed. All registered download bytes matched private registration
  hashes. Presentation-redacted downloads remain distinct from canonical inputs.
  An earlier real in-flight QC stop retained its completed receipt and fenced
  later work. These checks do not replace the failed conversational acceptance.

Independent reviews closed the explicit-control findings before integration;
the later column/prompt changes had focused regressions and root review, not a
new independent review claim. Existing components, executor, strict Action
validation and dependencies were reused. No parser fallback, retry framework or
scientific API change was added.

Genuine full-chain acceptance remains incomplete: provider reliability and
explicit product/process definitions, scientific input review, comparison design
and genuine graft evidence are separate unresolved requirements. Scores remain
null and methods candidate/shadow. Original preview services remain untouched;
only the idle isolated candidate was upgraded with its existing session storage.
No GitHub update, merge or publication was performed in this continuation.
