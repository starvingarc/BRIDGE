# V1 output-path hardening validation — 2026-08-24

## Question tested

Do P0-01 and P0-02 return a typed, non-destructive failure when a valid V1
request names an existing file or final symbolic link as `output_dir`?

This is an engineering interface check. It does not exercise or validate a
cell-state method, biological assignment, product conclusion or score.

## Exact build

| Item | Value |
|---|---|
| Branch | `runtime-output-path-hardening` |
| Base `main` | `4578f93de34eb1dfd595703bf821070355b578e8` |
| Validated implementation commit | `967047adbdc7f9c983f0fa2cdeb818f0a6af5bce` |
| Python | `3.12.12` |
| Wheel | `bridge-0.2.0.dev0-py3-none-any.whl` |
| Wheel SHA-256 | `a841f356699bb617b0927db4320a6eb180bbeb81a1bf7ca6a8f2b84803317d8c` |

The wheel was built from the exact implementation commit, installed into a
fresh environment and imported from that environment's `site-packages`.

## Observations

| Gate | Result |
|---|---|
| New P0-01/P0-02 regression cases | `3 passed` |
| Complete source suite | `962 passed, 3 warnings` |
| Complete installed-wheel suite | `962 passed, 3 warnings` |
| Tool discovery | 12 packages; 5 implemented on the base branch |
| Knowledge snapshot | valid; no dangling method or source references; 0 formal-eligible methods |
| Repository policy | passed |
| Local diff check | passed; no project code was run locally |

Both packages returned `execution_state=failed` with the sole reason code
`output_path_invalid`. Existing file bytes and symbolic-link targets remained
unchanged. The registry now stops at its existing interface instead of letting
`NotADirectoryError` escape from an executor.

The three existing warnings are AnnData duplicate-name and SciPy sparse-matrix
deprecation warnings in unrelated QC fixtures.

## Boundary

The change adds no runtime version, Schema, Tool ID, biological rule or public
claim. P0-02 remains `candidate/shadow`, its biological review is still open,
and `domain_score` remains null.
