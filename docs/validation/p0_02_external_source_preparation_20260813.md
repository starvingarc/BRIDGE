# P0-02 External-Source Preparation Validation — 2026-08-13

## Biological purpose and current meaning

This validation confirms that the public Birtele conversion and Birtele/La Manno
lineage-audit procedures remain deterministic and fail closed while P0-02 is in
`biological_review_in_progress`. It does not validate a biological replicate,
donor relationship, cell state, marker, classifier, threshold or product role.

Birtele's conditional approval remains limited to source-level external holdout,
stage-level description and provisional-group sensitivity. `scientific_status`
is `candidate`; all score states remain `shadow` or `unavailable`; and
`domain_score` is `null`. No scientific freeze is claimed.

## Environment and source boundary

Commands were executed from the isolated
`p0-02-external-source-preparation` worktree with its explicit
`.venv/bin/python` on 2026-08-13. The environment had no `pip` module, so no
wheel build or installation was attempted. Test and command invocations used
`PYTHONPATH=src` with that explicit interpreter to exercise this worktree rather
than the older installed package.

## Evidence

| Check | Exact command/result |
|---|---|
| Focused external-source contracts | `PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_birtele_asset.py tests/test_external_source_lineage.py tests/test_projection_parity.py tests/test_knowledge_catalog.py` — `39 passed in 2.56s` |
| Full suite | `PYTHONPATH=src .venv/bin/python -m pytest -q` — `214 passed, 3 warnings in 14.31s` |
| Tool discovery | `PYTHONPATH=src .venv/bin/python -m bridge.toolkit.cli list --json` — 12 packages, implemented only `P0-01`, `P0-02` |
| Knowledge snapshot | `PYTHONPATH=src .venv/bin/python -m bridge.toolkit.cli knowledge validate` — `valid=True`, 354 methods, 396 bindings |
| Repository policy | `PYTHONPATH=src .venv/bin/python tools/check_repository.py` — passed after the indexed validation record was added |
| Diff hygiene | `git diff --check` — passed |

The full-suite warnings are pre-existing negative-fixture and SciPy-deprecation
warnings: one AnnData duplicate-feature warning and two `spmatrix` default-value
deprecation warnings. They do not report a failed assertion.

The tests cover checksummed immutable Birtele inputs, exact 13-file sample-map
coverage, raw duplicate/blank cell-header rejection, raw blank-feature rejection,
matrix and gene-order validation, output manifest/QC/provenance projections,
stable failure reasons, declared-holdout-root coverage, transitive source-family
exclusion, tool-card projection parity, package version `0.4.8`, review status
and indexed human-facing documentation. Raw identifier checks occur before
Pandas can synthesize names such as `cell.1`, `Unnamed: 1` or string `nan`.

## Remaining boundary

The validated procedures do not authorize the locked runner, locked OOD/source
asset opening, tuning, score availability, or a non-null domain score. The next
scientific work remains biological review of the 25 state cards, then the
ProductDefinitionCard and StateRoleMap; a signed FreezeGate is required before a
single locked run.
