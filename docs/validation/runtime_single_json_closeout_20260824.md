# Configurable runtime closeout validation — 2026-08-24

## Question

Can the configurable P0 packages share one immutable single-JSON publication
path while preserving typed failures, deterministic reuse and their scientific
boundaries?

## Change under review

The runtime simplification replaces five module-local publication copies in
P0-03 through P0-07 with `publish_single_json`. The original refactor removes
315 lines and adds 24. The closure stack also centralizes generic configurable
contracts and publication-safety checks, closes the reviewed denominator/unit
and P0-11 payload leaks, and corrects the Agent integration range to P0-12.

No biological assignment, program, reference range, comparison direction,
graft rule, score contract or release authority moved into code.

## Exact evidence

No local project code was run. Exact head
`03e71eb184c350a5b194b78b3ec11709e55a047a` was transferred as a Git archive
to `/data1`. Source and installed-wheel execution used separate temporary
environments; the installed `bridge` resolved from `site-packages`. The wheel
SHA-256 was
`20815c66c21e6c167356ef8839493083c07562aaae5d3d0c54561b230394daa5`.

| Gate | Result |
|---|---|
| Affected configurable chain | 223 passed |
| Complete source suite | 1,182 passed; 3 existing dependency warnings |
| Complete installed-wheel suite | 1,182 passed; 2 dependency warnings |
| Tool discovery | exactly 12; all 12 implemented |
| Knowledge validation | valid; no dangling method/source refs; 0 formal-eligible methods |
| Repository policy and projection parity | passed |
| Schema/Card/benchmark regeneration | committed bytes unchanged after two rounds |

The focused chain includes ordinary and adversarial publication paths,
immutable reruns, output collisions, input mutation, strict numeric semantics,
machine-local denominator/unit rejection and recursive P0-11 payload scanning.

## Boundary

This is engineering and packaging evidence. Every P0 package remains a
`candidate`; P0-02 remains shadow unless a signed release manifest is supplied,
`domain_score` remains null where no ScoreContract exists, and public export
still stops at mandatory human confirmation. Real biological inputs were not
needed to reproduce the interface findings, so no unpublished data was opened
or copied.

## Independent integration with V1 output hardening

The final stacked head `79a6fb4e6a1cfd9f1c0192e917091b3cc0c8ef1c`
was merged in a temporary, unpushed integration branch with the independently
green V1 output-path head
`94269dc3fb0d0d16bb971be7ef97f232405a0a2d`. The reproducible combined tree was
`038fa7f779f50d10098f187f248c2348f56ba414`.

- 271 affected P0-01 through P0-07 plus P0-11/P0-12 tests passed;
- complete source and clean-wheel suites each passed 1,185 tests;
- the installed wheel SHA-256 was
  `e4843fe0389edefafbec6e1f58cf80261f5ab91b04c69c9b84e577a6a628dd38`;
- all 12 tools were implemented and discoverable, repository policy passed
  against 415 tracked files, and formal-eligible methods remained zero.

Only `PLANS.md` and `docs/index.md` required additive conflict resolution; the
runtime and tool code merged without conflict. The temporary branch was not
pushed and does not change the required integration order.
