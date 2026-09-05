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
