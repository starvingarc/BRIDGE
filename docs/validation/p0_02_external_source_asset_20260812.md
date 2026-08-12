# P0-02 External-Source Asset Validation — 2026-08-12

## Biological question

Can Birtele `GSE192405` serve as an external fetal ventral-midbrain source
without treating GEO files or cells as biological replicates, and without
leaking Birtele or La Manno source families into candidate development?

## Public inputs

- GEO provides 13 processed count-matrix CSV files. Raw reads are not public.
- The processed archive SHA-256 is
  `d86d167e39ea025ec3f8bce2b00c252e38a4bbc73dde2207d7d8321dd623836e`.
- The GEO MINiML SHA-256 is
  `a8a3a022a423f98a862b157bdb82758c91e53fe1c6e5fdb4131aad2bc2ef1e8d`.
- The publication supplement PDF SHA-256 is
  `f538ca0b034d33a587a11027e4986d6a7c30255cd730f0ddbb8527d2b103d09b`.
- Table S1 SHA-256 is
  `6a08c039a135c211e03da44d8dc592a934bbecafaae78a9dbb2b2d08755d9a75`.
- The packaged sample map records all 13 per-file checksums and the published
  GEO metadata without filling missing donor relationships by inference.

The formal conversion command verified all four provenance-file hashes and all
13 processed-matrix hashes before reading matrix contents.

## Observed data and sample-unit limitation

All 13 matrices contain the same 25,032 genes in the same order. Their 77,804
cell identifiers are unique across files. Per-GEO cell counts are:

| GEO sample | Cells | GEO sample | Cells |
|---|---:|---|---:|
| `GSM5746439` | 566 | `GSM5746446` | 2,776 |
| `GSM5746440` | 750 | `GSM5746447` | 5,960 |
| `GSM5746441` | 8,859 | `GSM5746448` | 8,113 |
| `GSM5746442` | 3,449 | `GSM5746449` | 17,689 |
| `GSM5746443` | 7,957 | `GSM5746450` | 11,448 |
| `GSM5746444` | 2,400 | `GSM5746451` | 6,634 |
| `GSM5746445` | 1,203 |  |  |

Four uncultured GEO matrices sum to the 23,483 cells that the paper reports
from three fetuses, but the public records do not identify which files share a
fetus. The nine cultured matrices likewise cannot be mapped unambiguously to
the three culture donors described in Table S1. `GSM5746445` also contains an
internal public-metadata conflict: its title, source text and characteristics
disagree on 2D/3D and day 14/day 30.

The frozen candidate therefore assigns no `biological_unit_id`. Every GEO
sample has `biological_unit_status=unresolved_public_mapping` and
`replicate_eligibility=not_estimable`. A GEO sample, culture condition or cell
must not be counted as a biological replicate.

## Deterministic conversion and QC

Two independent server conversions from the 13 read-only CSV files produced
byte-identical outputs:

| Output | SHA-256 |
|---|---|
| `GSE192405.h5ad` | `4fe964964535e5d7f39fb46619c6ef791365c4d73e638b25b7a0c8372432f9ce` |
| `conversion_manifest.json` | `151f75adbe11ab0c049abea07e7bd87094689c29781f49e6944741887b577ed6` |
| `qc_report.json` | `c7e4901ee54fe480d18ed6ada027f4b26660dd9ee672b849cc962da658075bec` |
| `sample_unit_map.tsv` | `f22466b136eac5dbe371f0be8725dcf6efc060fff76aca5547db3a0632697151` |
| `source_manifest.json` | `240c8144fc66932cad947ab9946cbd370a228580bcac2dabd0380a876db16d66` |

The H5AD is a `77,804 x 25,032` CSR `int32` matrix in `X` with
`matrix_semantics=raw_counts`. It contains 120,095,908 nonzero values; observed
nonzero counts range from 1 to 4,615. Counts are finite, nonnegative integers;
feature and observation identifiers are unique; and all per-GEO cell counts
match their source matrices. Public manifests contain no server path or user
identifier.

Conversion was executed at implementation
`aab7814c28bd796ff51282ec5286b581d5158107`. The corrected gene-order hash is
the SHA-256 of the newline-separated ordered gene names without an added
terminal newline:
`643be392404f6fc4c10ca6dce2abc3d10b07de0df9ed9e100826f26fe4939cd9`.

## Source-family and transitive-leakage audit

The packaged audit covers 21 current development, OOD, behavior, external,
related and sealed assets. It treats `GSE192405` and `GSE76381` as the external
holdout roots and found zero overlap with candidate fitting roles.

- The La Manno fetal reference and the same-study hESC/iPSC objects are excluded
  from candidate development and calibration.
- The Birtele converted H5AD is a derivative of the 13 processed matrices, not
  an independent source.
- Chen-derived objects remain one Chen source family.
- Sealed `E-MTAB-14729` remains excluded and unopened; only its isolation label
  is present in the public lineage map.

The audit output SHA-256 is
`31f3b82a20c6c7aceab7438ff5ff7f60fcedc2a3fce19b3809df2c0d53d0f6a6`;
the lineage map SHA-256 recorded inside it is
`8180e7e2d107612ec599c161adac806ffbe22bd38b495bcef2cd2e397d6112b9`.
Focused server tests passed: `17 passed in 2.17s`. At repository implementation
`28199d1534e280ea4a4161091f0a632b17fcc815`, the complete server suite passed
with `209 passed, 1 warning in 46.20s`; the warning is the existing AnnData
duplicate-feature negative fixture. Deterministic generators, tool discovery,
knowledge validation and repository policy checks also passed.

## Review status and scientific boundary

Engineering conversion, QC, checksum and declared-lineage checks are complete.
The external asset gate is **not approved**. A biological reviewer must choose
one of the following before the 25 state-card review begins:

1. accept the unresolved map for source-level holdout analysis, with no
   biological-replicate estimates;
2. obtain an authoritative matrix-to-donor map and issue a new sample-map
   version; or
3. exclude Birtele from the freeze candidate.

No method, state, threshold or product role is frozen. The locked runner has not
been implemented or run, locked OOD assets remain unopened, and this record
does not support efficacy, safety, potency, GMP release or product ranking.
