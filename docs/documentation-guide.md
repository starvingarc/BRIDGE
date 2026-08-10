# Documentation Guide

## Stable Documents

`docs/` contains approved scientific and engineering facts. Update the relevant stable document in the same change when code, Schema, privacy behavior, Tool IDs or claim boundaries change.

Every stable document must be linked from `docs/index.md` or another indexed document. Proposed capabilities are labelled `candidate`, `proposed`, `shadow` or `not_implemented`.

## Plans

`plans/` contains branch-scoped implementation state: motivation, scope, non-goals, tasks, decisions, risks and acceptance evidence. Plans do not override stable contracts and do not serve as user documentation.

## Knowledge Cards

Method and Source Cards use machine-readable YAML plus concise Markdown. Facts cite official sources. A missing paper, license or version is represented explicitly rather than inferred.

## Historical Material

Superseded implementation and documents live under `legacy/` or Git history. They are not linked as current contracts and cannot silently supply values to v2 tools.
