# Shared P0 scientific contract spine validation — 2026-08-25

## Question tested

Can independently packaged P0 modules exchange one exact selected data view,
ProductCase, measurement contract and experimental-unit lineage without
hard-coding mutable biology or trusting a caller-supplied review label?

This is a shared-contract and packaging validation. It does not identify a
cell state, choose a biological replicate, validate a product, or grant release
authority.

## Exact build

| Item | Value |
|---|---|
| Branch | `shared-p0-scientific-contract-spine` |
| Base `main` | `7efbca22cf13f60bc57a7ff624e80649cd9143cd` |
| Validated implementation commit | `5ca05ede013694e57c037dfb15b94c10274b79ac` |
| Python | `3.12.13` |
| Wheel | `bridge-0.2.0.dev0-py3-none-any.whl` |
| Wheel SHA-256 | `745a795b4deb89a14dec530b0b5a2117162e1a4e9d0d7eb6617fb4f9d3f7fac1` |
| Source archive SHA-256 | `748cac2488a528e6843cc1abdfbe5674f3ac5194b67735c32c97f811ff1fc8a5` |

The exact commit was archived, installed with all declared CI extras, built as
a wheel, installed into a fresh environment, and imported from that
environment's `site-packages` rather than the source tree.

## Observations

| Gate | Result |
|---|---|
| Focused shared contract/runtime/schema suite | `106 passed` |
| Complete clean-source suite | `974 passed, 3 warnings` |
| Complete installed-wheel suite | `974 passed, 3 warnings` |
| Tool discovery | 12 packages |
| Public/packaged Schema registry | 59 references; paired files packaged |
| Schema generation | Two passes produced identical SHA-256 manifests |
| Knowledge snapshot | valid; 354 methods, 396 bindings, no dangling references, 0 formal-eligible methods |
| Repository policy and diff check | passed |
| Installed environment dependency check | passed |

The tests reject capture or graft units as independent groups, prevent P0-01
from claiming reviewed/frozen lineage, require a complete ProductCase manifest
binding, and require paired source-run and interval metadata. Existing
v0.1-shaped measurements remain valid inside `ToolRunV2`, but no non-null
domain score becomes possible.

The three warnings are the existing AnnData duplicate-name and SciPy sparse
matrix deprecation warnings in unrelated QC fixtures.

## Evidence location and integrity

Private engineering evidence is retained under
`/data1/yuxiao/BRIDGE/private/module-integration/shared-contract-spine/5ca05ede013694e57c037dfb15b94c10274b79ac/`.
It contains the source archive, wheel, source/wheel logs, installed import path,
Schema and Tool Card manifests, gate outputs and their checksum manifest. No
private biological input is included.

## Boundary

The contract records what a producer declared and whether an external,
checksummed review receipt exists. It does not determine the correct donor,
sample, preparation, animal, pairing structure or estimand for real data.
Mutable state roles, thresholds, developmental windows and assay decisions
remain external versioned inputs. All tools retain their prior implementation
and scientific states; `domain_score` remains null and formal methods remain 0.
