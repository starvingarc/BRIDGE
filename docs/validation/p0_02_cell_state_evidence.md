# P0-02 Cell-State Evidence: Validation History

This subject-level record preserves the complete dated receipts below.
Each receipt's inputs, source versions, test counts and scientific limits
apply to that historical run, not to the current main branch or a newly
qualified method/product. Consolidation changes organization and links only;
it does not combine evidence families or create a new validation result.

- [P0-02 Server Integration Record](#record-p0-02-server-integration-20260811)
- [P0-02 Cell-State Evidence Pilot](#record-p0-02-scientific-freeze-pilot-20260811)
- [P0-02 External-Source Asset Validation — 2026-08-12](#record-p0-02-external-source-asset-20260812)
- [P0-02 External-Source Preparation Validation — 2026-08-13](#record-p0-02-external-source-preparation-20260813)
- [P0-02 deterministic grouping artifacts](#record-p0-02-deterministic-grouping-20260905)

<a id="record-p0-02-server-integration-20260811"></a>

## P0-02 Server Integration Record

**Date:** 2026-08-11
**Tool:** `P0-02` version `0.3.0`
**Environment contract:** `ENV-P0-CORE-v0.1`

### Reference snapshot

Candidate snapshot `REF-PD-vMB-CELLSTATE-v0.2` was rebuilt from audited source assets. It contains separate scRNA and snRNA primary profiles, modality-specific L2 refinement profiles, one dependent combined-modality sensitivity profile, and planned regional context records.

| Profile | Included observations | Samples | Selected genes | Excluded |
|---|---:|---:|---:|---:|
| Chen vMB scRNA L1 | 61,455 | 6 | 2,018 | 0 |
| Chen vMB snRNA L1 | 85,465 | 6 | 2,032 | 2,002 unresolved |
| Chen RG/Nb scRNA L2 | 14,565 | 6 | 2,036 | 25 unresolved |
| Chen RG/Nb snRNA L2 | 505 | 5 | 2,042 | 0 |
| La Manno fetal VM scRNA L1 | 1,210 | 7 | 2,029 | 767 unmapped |
| Chen combined sensitivity | 146,920 | 12 | 2,028 | 2,002 unresolved |

Profile, vocabulary and marker artifacts reproduce the preceding candidate snapshot byte-for-byte. The new manifest adds the complete competitor denylist and remains free of source paths. Agent runtime rejects this candidate snapshot by default; it was enabled only for this science-team validation.

### Real-data runs

All inputs first had a checksum-bound `QCReadinessProfile`. Every P0-02 run preserved the input, emitted 16 checksummed artifacts and five registered visualizations, and kept `domain_score=null`, `score_state=shadow` and `open_set_state=not_assessed`.

| Logical asset | Role | Shape | Consensus supported | Source conflict | Wall time | Peak RSS |
|---|---|---:|---:|---:|---:|---:|
| GSE204796 pre-transplant time course | product development | 37,397 x 33,538 | 64.52% | 35.48% | 55 s | 6.1 GiB |
| GSE190729 cerebral organoid | developmental OOD | 17,636 x 33,538 | 10.63% | 89.37% | 25 s | 2.9 GiB |
| GSE221853 neural crest | lineage OOD | 29,857 x 24,297 | 47.97% | 52.03% | 49 s | 9.4 GiB |

For GSE204796, source-conflict fractions changed across the declared time course: D8 46.82%, D14 51.22%, D21 19.50%, D28 33.23% and D35 31.70%. This verifies time-dependent output, not an optimal harvest day.

The two OOD runs remain shadow candidate sets rather than final assignments. Their conflict fractions are diagnostic observations only; open-set calibration and an OOD decision threshold have not been frozen.

### Leakage and reproducibility checks

- A 337-cell GSE76381 iPS-mDA query declared as `LAMANNO-2016` excluded the La Manno fetal reference before computation. Only the Chen primary source remained, so consensus and source-conflict measurements returned `unavailable` rather than zero.
- L2 output obeyed the L1 Radial_Glia/Neuroblast parent set, and L1/L2 compositions retained separate denominators in all three main runs.
- Reference Evidence Families were de-duplicated; the Chen combined profile remained sensitivity-only.
- All output artifact hashes, reference checksums and input hashes validated after execution.
- Repeating the full GSE204796 request produced the same run ID and all 16 artifact hashes.
- The full repository suite collected and passed 68 tests in the server Python 3.12 scientific environment.

This historical record establishes an executable, traceable shadow baseline. It does not establish a frozen annotation method, calibrated OOD detector, formal domain score, product ranking, clinical efficacy, safety, potency or release decision. At the time of this run, independent rebuild validation of `ENV-P0-CORE-v0.1` was still pending. The later environment and engineering status is recorded in [Server reproducibility validation, 2026-08-12](server_reproducibility_20260812.md).


---

<a id="record-p0-02-scientific-freeze-pilot-20260811"></a>

## P0-02 Cell-State Evidence Pilot

**Date:** 2026-08-11

**Status:** `awaiting_biological_review`

**Scope:** development-only scRNA-seq pilot; no scientific release

### Biological question

Can fetal ventral-midbrain references identify intended states in a pre-transplant
hPSC-mDA product and refuse cells whose identity lies outside the reference?

Reliable answers are required before BRIDGE can report target-cell composition,
regional fidelity, developmental compatibility or off-target composition.

### Data and biological controls

| Logical asset | Biological role | Cells/profiles |
|---|---|---:|
| Chen vMB scRNA L1 | Broad fetal ventral-midbrain states | 61,455 |
| Chen RG/Nb scRNA L2 | Seven priority progenitor and neuroblast states | 11,366 |
| GSE190729 | Cortical/cerebral OOD | 17,636 |
| GSE221853 | Neural-crest OOD | 29,857 |
| GSE267791 | Motor-neuron OOD | 1,341 |
| GSE224152 | Mesenchymal OOD | 1,771 |
| GSE204796 | Product differentiation time course; behavior check only | 37,397 |

The La Manno source-family holdout, three locked OOD families and the sealed
competitor test were not opened. They had no influence on reference construction,
marker review, method selection or proposed gates.

### What the pilot found

#### Broad fetal ventral-midbrain states

CellTypist and scANVI recovered many L1 labels across donor-aware internal splits.
CellTypist had the lowest product-composition error among the inductive methods,
while scANVI also performed well. These are development observations, not evidence
that either method is ready for product use.

#### Fine RG/Nb-derived states

scANVI separated the seven L2 states more accurately than the transparent
correlation and marker baselines. Its pilot was transductive, however, and no
independent external label source has yet confirmed these fine states. scConform,
used only as a prediction-set/hierarchical coverage layer over a preregistered base
classifier, covered 83.3% of L2 true labels against a nominal 90% target. This does
not establish a standalone OOD detector or sufficient abstention behavior.

#### Unrelated cells are still forced into known labels

The tested inductive correlation, marker and CellTypist channels assigned all four
OOD datasets to known fetal ventral-midbrain labels instead of refusing them. Their
development-OOD false-reassurance rate was 1.0. This is the most important current
failure: a confident label may still represent cortex, motor neuron, neural crest
or mesenchymal identity.

#### Marker evidence is incomplete

Twenty-five state cards exist, covering 18 L1 states and seven priority L2 states,
but all remain pending. `Neuron_ChAT` and `Neuron_OMTN` lack reviewed negative
markers; `Neuron_Glut_GABA` has no complete marker card; and all seven L2 states
lack frozen positive and negative marker cards. The marker channel therefore cannot
yet serve as an independent biological check.

### Meaning for product evaluation

BRIDGE can currently produce an exploratory, source-aware view of how product cells
relate to fetal ventral-midbrain states. It cannot yet formally state:

- what fraction of a product is the intended mDA lineage;
- whether the product has the intended ventral-midbrain regional identity;
- what fraction is a known off-target lineage;
- whether an unassigned or unusual population is truly absent.

The output remains `shadow`, `domain_score=null`. It does not validate product
efficacy, safety, potency, GMP release or overall quality.

### Biological issues still unresolved

1. The definitions, developmental context and marker logic of all 25 states remain under review.
2. ProductDefinitionCard and StateRoleMap are not approved, so cell-state labels cannot yet be translated into target, adjacent or off-target product roles.
3. The 328 historical conflicts remain excluded, including 25 RG-to-Pericyte records.
4. Current methods either force OOD assignments or lack a completed OOD assessment.
5. Gene masking, sample-preserving downsampling and preprocessing sensitivity remain unassessed.
6. Locked external-source and OOD tests have not run.

No state has passed an approved per-state gate. P0-03 remains blocked until the
biological definitions and locked-test rules are fixed and the locked test is
completed without tuning.

### Method details

Accuracy measures overall label recovery, macro-F1 gives rare states equal weight,
and composition MAE measures error in the estimated product composition.

| Method | L1 accuracy / macro-F1 / composition MAE | L2 accuracy / macro-F1 / composition MAE | Limitation for product use |
|---|---|---|---|
| Source-specific correlation | 0.671 / 0.583 / 0.037 | 0.531 / 0.500 / 0.088 | Forced OOD assignment |
| Marker/program evidence | 0.427 / 0.399 / 0.080 | Not assessed | Incomplete marker cards; forced OOD assignment |
| CellTypist custom | 0.829 / 0.799 / 0.010 | 0.747 / 0.776 / 0.045 | Forced OOD assignment |
| scmap | 0.651 / 0.560 / 0.035 | 0.549 / 0.500 / 0.106 | OOD not assessed |
| scANVI | 0.803 / 0.745 / 0.014 | 0.810 / 0.811 / 0.039 | Transductive pilot; OOD not assessed |
| Symphony | 0.730 / 0.635 / 0.024 | 0.721 / 0.746 / 0.054 | OOD not assessed |
| scConform over scANVI | 0.803 / 0.745 / 0.014 | 0.810 / 0.811 / 0.039 | Coverage 0.902 / 0.833; not independent biological evidence |
| SingleR | No complete L1 result | Partial L2 output excluded | Exceeded the 3,600-second development budget |

SingleR and scmap belong to the same reference-similarity evidence family.
scConform wraps the preregistered scANVI base probabilities to assess prediction-set
coverage and is not counted as an independent OOD detector or biological evidence
source. No method was selected or frozen from this pilot.

### Engineering record

| Record | Value |
|---|---|
| Pilot run | `CELLSTATE-PILOT-e45ada3778e2` |
| Evidence run | `CELLSTATE-EVIDENCE-3268ddfd0caf` |
| Split manifest SHA-256 | `84685ea4ee2cea136ed973562c6a9a7ddd631fd9201f245befcc34e55de06504` |
| Evidence artifact SHA-256 | `ffe78a0ba64f632b4cb25191062e91fc053de22e11bf4aa5b5f9e91a864e1590` |
| Locked assets opened | `false` |
| Sealed assets opened | `false` |
| Historical local Python 3.12 suite | 171 passed, 3 warnings; diagnostic only, not current formal evidence |
| Server Python 3.12 suite | 171 passed, 2 warnings |

Repeated summaries were byte-identical and retained the same Evidence ID.


---

<a id="record-p0-02-external-source-asset-20260812"></a>

## P0-02 External-Source Asset Validation — 2026-08-12

### Biological question

Can Birtele `GSE192405` serve as an external fetal ventral-midbrain source
without treating GEO files or cells as biological replicates, and without
leaking Birtele or La Manno source families into candidate development?

### Public inputs

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

### Observed data and sample-unit limitation

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

### Deterministic conversion and QC

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

### Source-family and transitive-leakage audit

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

### Review status and scientific boundary

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


---

<a id="record-p0-02-external-source-preparation-20260813"></a>

## P0-02 External-Source Preparation Validation — 2026-08-13

### Biological purpose and current meaning

This validation confirms that the public Birtele conversion and Birtele/La Manno
lineage-audit procedures remain deterministic and fail closed while P0-02 is in
`biological_review_in_progress`. It does not validate a biological replicate,
donor relationship, cell state, marker, classifier, threshold or product role.

Birtele's conditional approval remains limited to source-level external holdout,
stage-level description and provisional-group sensitivity. `scientific_status`
is `candidate`; all score states remain `shadow` or `unavailable`; and
`domain_score` is `null`. No scientific freeze is claimed.

### Environment and source boundary

Commands were executed from the isolated
`p0-02-external-source-preparation` worktree with its explicit
`.venv/bin/python` on 2026-08-13. The environment had no `pip` module, so no
wheel build or installation was attempted. Test and command invocations used
`PYTHONPATH=src` with that explicit interpreter to exercise this worktree rather
than the older installed package.

### Evidence

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

### Remaining boundary

The validated procedures do not authorize the locked runner, locked OOD/source
asset opening, tuning, score availability, or a non-null domain score. The next
scientific work remains biological review of the 25 state cards, then the
ProductDefinitionCard and StateRoleMap; a signed FreezeGate is required before a
single locked run.


---

<a id="record-p0-02-deterministic-grouping-20260905"></a>

## P0-02 deterministic grouping artifacts

Package: `0.5.3`

### Correction

Repeated raw-count requests could produce the same exploratory grouping labels
and scientific statistics but fail immutable output reuse. Wall-clock duration
and process peak memory were serialized into the scientific grouping metadata,
so their changes altered its content hash.

The correction removes those two volatile measurements and their collection.
Stable method parameters, clustering diagnostics, grouping identity and thread
configuration remain. Clustering, normalization, state evidence and scientific
status are unchanged.

### Verification

- The synthetic repeated-grouping regression failed on the previous code with
  unchanged labels and grouping hash, and passed after the correction despite
  changing mocked runtime measurements.
- `python -m pytest tests/test_cell_state.py -q`: 46 passed before integration.
- On the combined installed wheel, the six relevant P0-02 input-preservation,
  count-conversion and deterministic-replay tests passed.
- The installed integration suite passed 39 tests. All three integration profiles
  validated; 157 model, source and installed Schema copies matched.
- An independently repeated exact request succeeded twice with the same run ID.
  Every artifact content hash matched, and the input remained unchanged.
- Repository policy and `git diff --check` passed.

The combined wheel tested the runtime tree at commit `0afc9df0`; this record
and its README link were added afterward without changing executable code.
The replay evidence remains in private validation storage. No resource
identifiers, locations, biological results or input hashes are published here.

This is an engineering reproducibility correction. P0-02 remains
`candidate/shadow`; it adds no scientific freeze, calibrated identity or
release authority.
