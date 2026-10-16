# Research workflow adaptation sources

These are BRIDGE adaptations of public research guidance, not unchanged upstream
Skills or a bundled upstream execution environment. Workflow text, routing,
stopping rules, scientific boundaries and tool interfaces were modified for BRIDGE
on 2026-10-04. Current Actions, registered Tool Packages and evidence contracts
remain authoritative. No upstream commands, downloads or dependencies run implicitly.

## Attribution and pinned inputs

- ToolUniverse contributors, [ToolUniverse](https://github.com/mims-harvard/ToolUniverse/tree/ffe2d0b94fa43f31b9afcd2d99543d3bad4eb4a7/skills),
  Apache-2.0. Retained [license](licenses/tooluniverse-apache-2.0.txt).
- Copyright (c) 2025 K-Dense Inc.,
  [scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills/tree/154988403bb5a18e9d3c0ce4e6d5e2e4b184a298/skills),
  MIT for the selected guidance. Retained [license](licenses/kdense-mit.txt).

[sources.json](sources.json) is the maintained mapping of each BRIDGE workflow to
its exact upstream files, commit, original-byte SHA-256, license, reused BRIDGE
modules (paths relative to `src/bridge/`) and deliberately excluded upstream behavior.
It is packaged with the
workflows for review and reproducibility; it is not another routing registry.
The runtime catalog remains generated from each Skill's own frontmatter.

## Adaptation decisions

The public content supplies research-question framing, analysis branches,
experimental-unit distinctions, reference applicability, competing explanations,
evidence appraisal and report structure. BRIDGE supplies the product-specific
definitions, supported operations, private controls, current-version citations,
comparison/graft contracts and scientific status. A source pointer or copied
workflow never certifies a reference, marker, method or biological conclusion.

In particular, ToolUniverse's direct script execution, filename-first authority,
live-database retrieval, fixed marker thresholds, fidelity scoring and report
section quotas are not imported. K-Dense's standalone manuscript/study schemas,
trial appraisal frameworks, randomization/statistical engines and optional external
diagram services are not part of this integration.

The K-Dense `validate_prediction_matrix.py` and `audit_claims.py` helpers were
examined. They validate standalone CSV/JSON/manuscript objects, while BRIDGE
already validates typed hypotheses, current citation roles and registered claim
receipts. Their research-checking principles inform the guidance; the scripts
are not vendored, executed or advertised as BRIDGE capabilities. Existing BRIDGE
code is reused instead of introducing parallel validators.

The K-Dense Scanpy Skill was inspected as a candidate but not adapted or vendored;
expression guidance uses the ToolUniverse workflow and BRIDGE's existing contracts.
Upstream installation commands and package versions do not replace BRIDGE's
registered environment definitions. Future scientific code reuse belongs in a
Tool Package with its own contract, dependency review and validation.
