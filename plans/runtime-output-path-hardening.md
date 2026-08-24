# V1 Output Path Hardening

## Goal

Keep P0-01 and P0-02 behind the existing `ToolRegistry` interface when the
requested output path is unusable. A pre-existing file or final symlink must
produce one typed failed `ToolRun` without reading, replacing or deleting the
target.

## Scope

- add one shared registry preflight used by the two V1 packages;
- return the stable reason code `output_path_invalid`;
- cover eligibility, run behavior and target preservation for P0-01/P0-02;
- record exact source, wheel and GitHub verification evidence.

## Non-goals

- no V1-to-V2 migration;
- no output publication rewrite or new runtime interface;
- no P0-01/P0-02 scientific, Schema, Tool ID or score change;
- no P0-02 biological review or formal release promotion.

## Verification

No project code runs in the local macOS checkout. Focused, complete and
installed-wheel suites run on `/data1` and GitHub Actions. The final gate also
checks 12-tool discovery, knowledge validity, repository policy and the diff.

## PR boundary

Branch: `runtime-output-path-hardening`.

Implementation and green CI do not independently authorize merge.

## Current status

Implementation commit `967047adbdc7f9c983f0fa2cdeb818f0a6af5bce` passed
the three focused regression cases and both complete source and clean-wheel
suites (`962 passed`). Twelve tools remained discoverable, knowledge retained
zero formal-eligible methods, and repository policy passed. GitHub review and
the required check remain pending.
