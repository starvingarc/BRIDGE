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
| Validated implementation commit | `fa18928436202fd09bd105c4cc3f7111d9cce597` |
| Python | `3.12.13` |
| Wheel | `bridge-0.2.0.dev0-py3-none-any.whl` |
| Wheel SHA-256 | `19c54b0897d7b82aa6d7d87579d789056c44f72777bf7b99c799b855f94c4446` |
| Source archive SHA-256 | `81a03bec5830ea7cda730aeb8231df3c1f5c49e59555024b1b8fac63b0ca9b67` |

The exact commit was archived, installed with all declared CI extras, built as
a wheel, installed into a fresh environment, and imported from that
environment's `site-packages` rather than the source tree.

## Observations

| Gate | Result |
|---|---|
| Focused shared-spine contract and Schema suite | `42 passed` |
| Complete archived-source suite | `1004 passed, 3 warnings` |
| Complete clean installed-wheel suite | `1004 passed, 3 warnings` |
| Tool discovery | 12 packages |
| Public/packaged Schema registry | 62 references; 124 paired files |
| Schema generation | Two passes produced identical SHA-256 manifests |
| Knowledge snapshot | valid; 354 methods, 396 bindings, no dangling references, 0 formal-eligible methods |
| Repository policy and diff check | passed |
| Installed environment dependency check | passed |

The tests reject capture or graft units as independent groups, reject hierarchy/group contradictions, prevent one biological identity from becoming multiple version-only replicates, reject conflicting manufacturing lineage, parse and verify every assignment row and observation-set digest, prevent P0-01 from claiming reviewed/frozen lineage, keep ProductDefinitionCard draft-only, and require every binding in a single-source ProductCase to resolve to the same source. Public Schemas require nonempty manifest bindings and enforce structural pair/null/unknown alternatives; the standard validators add cross-object equality, digests, finite numeric and interval semantics, controlled analysis/independence-unit binding and assignment membership. `ToolRunV2` continues to accept the unchanged v0.1 `MeasurementResult`; standalone `MeasurementResultV2` requires an exact spec version without making any non-null domain score possible.

The three warnings are the existing AnnData duplicate-name and SciPy sparse
matrix deprecation warnings in unrelated QC fixtures.

## Evidence location and integrity

Private engineering evidence is retained on the authorized validation server,
keyed by the validated commit SHA. It contains the source archive, wheel,
source/wheel logs, installed import path, Schema and Tool Card manifests, gate
outputs and their checksum manifest. No private biological input is included.

## Boundary

The contract records a producer-declared review reference and checksum; it does
not establish that the referenced receipt exists, is authentic, or grants
authority. It does not determine the correct donor, sample, preparation, animal,
pairing structure or estimand for real data.
Mutable state roles, thresholds, developmental windows and assay decisions
remain external versioned inputs. All tools retain their prior implementation
and scientific states; `domain_score` remains null and formal methods remain 0.
