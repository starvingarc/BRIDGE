# Documentation Guide

## Stable Documents

`docs/` contains approved scientific and engineering facts. Update the relevant stable document in the same change when code, Schema, privacy behavior, Tool IDs or claim boundaries change.

Every stable document must be linked from `docs/README.md` or another indexed document. Proposed capabilities are labelled `candidate`, `proposed`, `shadow` or `not_implemented`.

## Plans

`plans/` contains its active-plan index and branch-scoped implementation state: motivation, scope, non-goals, tasks, decisions, risks and acceptance evidence. Plan paths are idempotent task identities and appear once in `plans/README.md`. Draft PRs may retain an active plan; ready-to-merge work records final evidence and resolves or explicitly carries forward every remaining item. Plans do not override stable contracts and do not serve as user documentation.

## Biology-first Progress

README, plans, pull requests, issues and validation records lead with the biological
question, data/reference/control set, observed findings, meaning for pre-transplant
product evaluation, unresolved questions and next scientific action. Code, tests,
environment and commit status follow in a short engineering record. Terms such as
`implemented`, `frozen` or `benchmark complete` never substitute for a biological
finding or an explicit statement of what the product assessment still cannot claim.

Do not assign review or data-supply actions to an external collaborator unless that
responsibility has been explicitly agreed.

## Knowledge Catalog

Catalog curation and source-verification inputs live under `knowledge/catalog/`. Runtime retrieval uses the packaged gzip snapshot, while `knowledge/active-methods.md` is the compact human shortlist. Exploded Method Cards, Source Cards and retrieval indexes are not tracked. A missing paper, license or version is represented explicitly rather than inferred.

## Historical Material

Superseded implementation and documents remain in Git history. They are not linked as current contracts and cannot silently supply values to current BRIDGE tools.
