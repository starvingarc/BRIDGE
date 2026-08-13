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

The publication reports primary groups of 6,634 cells at 6 weeks, 8,113 cells
at 8 weeks and 8,736 cells at 11 weeks. These reconcile exactly to
`GSM5746451`, `GSM5746448`, and the sum of `GSM5746446` plus `GSM5746447`,
respectively. The last pair nevertheless has distinct 11.5-week and 10.5-week
GEO age labels and distinct BioSample records, so this is a reconstructed
publication analysis group rather than an authoritative donor identity.

Table S1 identifies cultured scRNA-seq condition sets for a 7-week embryo (four
2D/3D day-15/day-30 conditions), a 7.3-week embryo (3D day 15 only), and an
8-week embryo (four conditions). Four seven-week-titled GEO matrices reconcile
to the first set; the shared `hVM2096` stem reconciles three matrices to the
8-week set. The remaining `GSM5746439` and `GSM5746445` can each fill either
the 7.3-week singleton or the missing 8-week 3D condition. They therefore retain
both candidate group IDs. `GSM5746445` also has an internal conflict: its title,
source text and characteristics disagree on 2D/3D and day 14/day 30.

All relationships are recorded as `provisional_inferred`. The candidate mapping
still assigns no formal `biological_unit_id`; every GEO sample remains
`biological_unit_status=unresolved_public_mapping` and
`replicate_eligibility=not_estimable`. A provisional group, GEO sample, culture
condition or cell must not be counted as a biological replicate.

## Deterministic conversion and QC

Two independent server conversions from the 13 read-only CSV files produced
byte-identical outputs:

| Output | SHA-256 |
|---|---|
| `GSE192405.h5ad` | `fe260f817e99ac5038de2583d119b020d74d8c08e869caf55ea106396ba057a9` |
| `conversion_manifest.json` | `81d3332966591891db7bdcc4be4e4fe7bf8527401c0650f46542c820557eaf05` |
| `qc_report.json` | `b0d5b1b81012fa89ca7c222ab82d0d404d5cdbc28f95e2d5b8a5d15f7dbae776` |
| `sample_unit_map.tsv` | `de16bd1a5c67aac42677eabd273c3becb7a43b563aae23394f1c315b65b766e4` |
| `source_manifest.json` | `c1b468a9a08f3147c2101fa26acd4d2a4ff1b146b4f17ea30f8fe906ae55d9fa` |

The H5AD is a `77,804 x 25,032` CSR `int32` matrix in `X` with
`matrix_semantics=raw_counts`. It contains 120,095,908 nonzero values; observed
nonzero counts range from 1 to 4,615. Counts are finite, nonnegative integers;
feature and observation identifiers are unique; and all per-GEO cell counts
match their source matrices. Public manifests contain no server path or user
identifier.

Conversion was executed at implementation
`4516e209b5465becb5be7bb59c91caeae467f8ab`. The corrected gene-order hash is
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
At converter implementation
`4516e209b5465becb5be7bb59c91caeae467f8ab`, focused server tests passed with
`13 passed in 2.15s`. An exact Git archive
(`fa96b0675fcb31040cea84f77354ee7e642f7a4df67224fe6d9f58242520ab2c`)
produced the wheel
`98b522bbaa56e9e07fb9ccc1551fae5cfcd9b8cc9a19d70006be951024ceecd2`.
After installation from that wheel, the complete server suite passed with
`209 passed, 1 warning in 52.72s`; the warning is the existing AnnData
duplicate-feature negative fixture. Both deterministic-generator passes, all
12 Tool Package discovery with only P0-01/P0-02 implemented, knowledge
validation and repository policy checks also passed.

## Review status and scientific boundary

The project scientific lead **conditionally approved** the external asset for:

- source-level external holdout;
- stage-level descriptive analysis; and
- provisional-group sensitivity analysis.

The approval explicitly prohibits biological-replicate estimation, donor-level
inference, and promotion of a method, state, threshold or product role before
the remaining review and freeze gates. An authoritative matrix-to-donor map can
supersede this decision through a new sample-map version; it is not assumed here.

No method, state, threshold or product role is frozen. The locked runner has not
been implemented or run, locked OOD assets remain unopened, and this record
does not support efficacy, safety, potency, GMP release or product ranking.
