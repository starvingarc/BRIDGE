# Product and spatial display verification

This is an engineering validation surface for the internal `linked_cell_context`
version 1.0 display. It does not qualify annotations, crosswalk relations,
registration, or product conclusions. Human biological review, scientific qualification and deployment
remain separate gates in the [active plan](../../plans/product-spatial-link.md).

## Source and access boundary

The display uses an expression UMAP's canonical receipt to find its declared full
coordinate table. Candidate assignments must share the exact input hash and full
DataView object, and preserve identical, unique observation IDs in identical
order. Sampled point IDs index the full coordinate table. They are never assumed
to be cell barcodes. Neither equal row counts nor filenames establish a join.

`test_spatial_link_data.py` covers view/hash/order mismatches, duplicates, missing
observations, sampled indices, mixed groups, unknown and unavailable annotation counts and versioned
crosswalk review state. Only reviewed `same_type` or `broader_type` entries match;
unknown assignments retain their denominator and never gain a mapping from a
leftover source label.

`test_spatial_reference.py` covers metadata-only H5AD projection, exact coordinates,
full type counts including observed zeros, original capture layout, changed
checksums, field/vocabulary mismatches, nonfinite coordinates and path traversal.
The reference configuration and files remain deployment-owned and private.
A reviewed display relation is a versioned semantic correspondence, not biological
qualification. Its private review record identifies the reviewer, source hashes,
positive/counter-marker evidence, unresolved limitations and display-only scope;
agent review must never be represented as human approval.

`test_web_spatial_context.py` covers authentication, session ownership, canonical
receipt requirements, context versioning and read-only prerequisite reporting.
`test_web_linked_cell_flow.py` uses the actual registered QC, candidate and
expression tools after synthetic upload and confirmation. Its model/calibration
fixture is explicitly synthetic. It checks authenticated sections, denominator
preservation, invalidated sources, changed crosswalk versions and the absence of
new ToolRuns during display reads.

## Interactive behavior

`frontend/tests/linked-cell-explorer.test.tsx` covers preview versus locked
selection with pinned priority, keyboard/Escape and pending-preview cancellation,
120 ms stable-group hover at mixed boundaries, mixed-group unmatched counts, stale responses,
unknown versus missing mapping versus measured zero, model failure, independent
candidate-plane state and expansion from a narrow result pane.

Product and reference legends sit beside their own plots, with a stacked fallback
for narrow cards. A locked selection changes only through explicit selection or
clearing; hover and keyboard focus cannot replace it.

The reference uses complete coordinates with a cached background layer and type
indices for foreground drawing. A capture switch changes only the reference
panel. A context version change resets the selection; an old response cannot
replace new coordinates. A model failure does not disable either plot. The
candidate plane receives no product group or cell coordinates.

Browser acceptance must check desktop and narrow views, actual controls, relevant
console errors and screenshots. A build alone is not browser acceptance. Private
screenshots, real references, product runs and review drafts are not committed.
A synthetic interaction or large-point rendering check is not real-product or
scientific validation.

## Commands

```bash
python -m pytest -q tests/test_spatial_link_data.py tests/test_spatial_reference.py tests/test_web_spatial_context.py tests/test_web_linked_cell_flow.py tests/test_web_input_change_impact.py tests/test_web_expression.py tests/test_web_artifacts.py
npm --prefix frontend test -- tests/expression.test.tsx tests/linked-cell-explorer.test.tsx tests/research-figures.test.tsx
npm --prefix frontend run build
npm --prefix frontend run build:anatomy
python scripts/check_repository.py --static
git diff --check
```

## Controlled display acceptance boundary

Detailed runs, cell counts, capture layouts, sample identities and screenshots
remain in controlled records. They are not distributed with this source snapshot.
The public tests above cover software behavior using synthetic fixtures;
independent scientific qualification remains open.

## Integration checks

The integration candidate passed 66 focused backend tests covering display joins,
reference loading, artifact access, mode-switch invalidation and the registered
linked flow, plus 11 cumulative-domain-coverage regressions from its dependency.
The full frontend suite passed 221 tests; both the main and standalone anatomy
builds passed. Static repository checks, patch formatting and GitHub YAML parsing
are checked on the staged integration candidate. The PR records the exact commit.

The frontend suite emits an existing GraphView act warning; backend warnings concern
Starlette/httpx/anyio deprecations and a deliberately duplicated-observation fixture.
Vite reports chunks above its size advisory. These are warnings, not failing checks.
The historical development checks are not a claim about the current public
repository CI; use its exact-commit check status. Publicly shareable summaries exclude sample identities, asset
paths, private crosswalks, screenshots, model bytes and original run receipts.
