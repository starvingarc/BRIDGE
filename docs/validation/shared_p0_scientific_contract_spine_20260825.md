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
| Validated implementation commit | `2d670c25538571ac31da052f057cb7fa14abfe9d` |
| Python | `3.12.13` |
| Wheel | `bridge-0.2.0.dev0-py3-none-any.whl` |
| Wheel SHA-256 | `a741b5b4bf7e8edc7e55966be43b6369ebf510c068c272c0ad8c88cc1cb26c5d` |
| Source archive SHA-256 | `2c108913038acecc211488ce936e6f27b745e46ade94a7c4b0616c7aa3daee1d` |

The exact commit was archived, installed with all declared CI extras, built as
a wheel, installed into a fresh environment, and imported from that
environment's `site-packages` rather than the source tree.

## Observations

| Gate | Result |
|---|---|
| Focused shared-spine contract and Schema suite | `32 passed` |
| Complete archived-source suite | `994 passed, 3 warnings` |
| Complete clean installed-wheel suite | `994 passed, 3 warnings` |
| Tool discovery | 12 packages |
| Public/packaged Schema registry | 62 references; 124 paired files |
| Schema generation | Two passes produced identical SHA-256 manifests |
| Knowledge snapshot | valid; 354 methods, 396 bindings, no dangling references, 0 formal-eligible methods |
| Repository policy and diff check | passed |
| Installed environment dependency check | passed |

The tests reject capture or graft units as independent groups, reject hierarchy/group contradictions, parse and verify every assignment row and observation-set digest, prevent P0-01 from claiming reviewed/frozen lineage, keep ProductDefinitionCard draft-only, and require ProductCase source/manifest/group coherence. Public Schemas cover structural pair/null alternatives; the standard validators cover cross-object equality, digests, finite interval order and assignment membership. `ToolRunV2` continues to accept the unchanged v0.1 `MeasurementResult`; standalone `MeasurementResultV2` adds stricter numeric semantics without making any non-null domain score possible.

The three warnings are the existing AnnData duplicate-name and SciPy sparse
matrix deprecation warnings in unrelated QC fixtures.

## Evidence location and integrity

Private engineering evidence is retained on the authorized validation server,
keyed by the validated commit SHA. It contains the source archive, wheel,
source/wheel logs, installed import path, Schema and Tool Card manifests, gate
outputs and their checksum manifest. No private biological input is included.

## Boundary

The contract records what a producer declared and whether an external,
checksummed review receipt exists. It does not determine the correct donor,
sample, preparation, animal, pairing structure or estimand for real data.
Mutable state roles, thresholds, developmental windows and assay decisions
remain external versioned inputs. All tools retain their prior implementation
and scientific states; `domain_score` remains null and formal methods remain 0.
