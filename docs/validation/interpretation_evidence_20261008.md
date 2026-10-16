# Evidence-bound interpretation: engineering scope

This record describes the interpretation and report safeguards integrated in the
source snapshot. Detailed controlled-session receipts, model responses, input
identities and internal revision history are not distributed here. The
[active plan](../../plans/biological-interpretation-harness.md#evidence-bound-interpretation-and-saved-continuation)
owns the broader literature and human-reader acceptance work.

## Versioned behavior

P0-06 exploratory attempts include request identity in run identity; candidate
program definitions retain their source and observed feature coverage. P0-10
interpretation and report contexts retain proposed relations, source features,
exact evidence graph bindings and explicit unresolved limitations.

A new interpretation is not admitted when a unique verified graph is unavailable.
The draft stays private, without creating a released explanation or report.
Saved native profiles must match both producer version and source artifact hash;
a same-ID profile from a different receipt cannot substitute for the selected
source. Historical compatible records remain readable without rewriting them.

## Reproducible engineering checks

- `tests/test_interpretation_graph.py`: graph binding and saved-source identity.
- `tests/test_web_interpretation_review.py` and
  `tests/test_web_interpretation_revision.py`: review failures, bounded revisions
  and preservation of unadmitted drafts.
- `tests/test_web_report_inputs.py`: source selection, invalidation and redaction.
- The registered synthetic producer flow checks evidence admission and report
  binding without using private experimental data.

Use the current public PR or CI run to identify which exact source revision
passed these checks. Historical controlled acceptance is not a substitute for
current test execution, and engineering checks do not establish biological
validity.

## Scientific boundaries

Feature coverage is identifier membership, not expression or cell identity.
Proposed semantic relations remain unverified. Missing evidence stays missing;
no clinical efficacy, safety, potency or manufacturing release claim follows.
Independent biological validation, literature applicability and human review
remain separate from software execution and consistency review.
