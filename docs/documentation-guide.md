# Documentation Guide

## One fact, one maintained source

The [BRIDGE PRD](BRIDGE_PRD.md), especially
[section 6](BRIDGE_PRD.md#6-agent-功能需求), is the single product-workflow
contract. README, the documentation index, Web guide, Agent integration guide
and plans link to it instead of copying the full workflow.

Public Schemas and package specs own machine-readable interfaces. Tool Cards own
human runtime use and refusal behavior. Scientific task cards own biological
questions and validation design. Exact validation records own what passed for a
specific revision.

## Stable documents

docs/ contains approved scientific and engineering facts. Update the relevant
stable document when code, Schema, privacy behavior, Tool IDs, workflow contract
or claim boundary changes. Proposed capabilities are marked candidate,
proposed, shadow or not_implemented and are explicitly separated from current
source, installed behavior, genuine execution and scientific qualification.

Every stable document is reachable from docs/README.md or another indexed page.
If sources disagree, stop at the highest-priority versioned contract and resolve
the drift; an overview cannot override a Tool Card, Schema or runtime evidence.

## Plans and retirement

plans/ contains only active branch-scoped implementation state. Each plan path is
a unique task identity and appears once in plans/README.md. Plans never serve as
user documentation or override stable contracts.

When implementation work is genuinely complete:

1. move unique reusable facts to stable docs and exact evidence to validation;
2. carry unresolved scientific work into the relevant active plan;
3. remove the completed diary from the active tree and repair its links; and
4. rely on Git history for construction chronology.

Do not delete a validation record merely because it is old. A passing test,
fixture, model output, installed package or archived diary is not scientific
validation.

## Public/private boundary

GitHub files contain code, public contracts, public-safe fixtures and
source-qualified stable evidence. Private paths, credentials, raw provider
responses, runtime receipts, sessions, screenshots, private sample identifiers
and operational deployment details remain outside the repository. Public-safe
objects are rebuilt from explicit allowlists rather than redacting arbitrary
private records.

## Biology-first progress

README, plans, pull requests, issues and validation records lead with the
biological question, data/reference/control set, observations, meaning,
unresolved questions and next scientific action. Engineering evidence follows.
Do not assign review or data-supply work to an external collaborator unless that
responsibility was explicitly agreed.

## Knowledge catalog

Catalog curation inputs live under knowledge/catalog/. Runtime retrieval uses the
packaged snapshot; knowledge/active-methods.md is the compact human shortlist.
Missing paper, license or version fields stay explicit rather than inferred.
