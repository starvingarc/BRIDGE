# Private conversational Web preview — 2026-09-05

## Question and scope

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
