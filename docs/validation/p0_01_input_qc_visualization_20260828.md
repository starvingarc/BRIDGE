# P0-01 input quality visualization validation — 2026-08-28

## Scope

This record tests whether P0-01 can render its technical input evidence as four
typed, deterministic and publication-ready static figures:

1. **Observation retention and analysis eligibility**
2. **Quality-metric distributions by capture**
3. **Library complexity and mitochondrial transcript fraction**
4. **QC-flag combinations and observation counts**

The titles name the measured quantity and analysis scope. User questions guide
figure selection but are not used as figure titles. This validation does not
cover a Web interface or a biological product-quality conclusion.

## Exact build

| Item | Value |
|---|---|
| Branch | `p0-01-input-qc-visualization` |
| Base `main` | `ddfa748e422024a258cf73e7e63016a86f08df6e` |
| Validated implementation commit | `c688a312ab751aabba1262af177adcc4780e15e4` |
| Python | `3.12.13` |
| Wheel | `bridge-0.2.0.dev0-py3-none-any.whl` |
| Wheel SHA-256 | `197912c63e0dc2ff54867d13e46772f62634ea58e5d447049e4a613da3543929` |
| Reproducible-build epoch | `1787921993` |

The wheel was built from the implementation commit on the authorized server,
force-installed into a fresh Python environment and imported from that
environment's `site-packages`. All declared P0 extras were installed together;
the environment dependency check reported no conflicts.

## Public-data validation

The end-to-end source run used the reviewed processed matrix for
[GSE192405](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE192405):
77,804 observations by 25,032 genes, grouped by 13 GEO accessions. These groups
are treated only as caller-declared technical captures. The biological sample
unit remains unresolved, so the 13 accessions are not counted as independent
samples or biological replicates.

The run produced 23 artifacts. The typed visualization layer contained four
figure objects and 274 evidence records: 273 `measured` and one `unavailable`
record for downstream sensitivity results. Capture labels were published only
as `capture_001` through `capture_013` and displayed as `Capture 1` through
`Capture 13`.

| Public artifact | SHA-256 |
|---|---|
| Typed visualization data JSON | `c0a0092e688f9faf0f771b8be8d1ad08266bd1c6120df23b00aa2f58565637ee` |
| Table fallback TSV | `d1c31eb169aee5292a443ae7e73a8d520145d366c4d834db4bbb0724698d25f6` |
| Visualization artifact set | `ad02cd76617b17281ca217b07da53c372c9628bf586500b71ac9126f3975691b` |

The public JSON, TSV and artifact set contained neither source accession IDs
nor server paths. All four current SVGs contained zero embedded raster images;
PNG fallbacks were rendered at 300 dpi. Missing or unavailable evidence was
shown explicitly rather than as a zero value.

The end-to-end data profile was generated at `c0f3515d890de90453c576cbf724bdf06448fe98`.
The subsequent changes through the validated implementation commit updated only
registry expectations, numeric capture ordering, single-intersection scaling,
SVG colorbar representation and available font weights. They did not change QC
metrics, the candidate measurement rules or the typed data profile.

## Realistic user-upload validation panel

P0-01 begins at an expression matrix or analysis object, not at FASTQ or BAM
reprocessing. Formal figure validation therefore uses unnormalized,
non-negative integer counts from cell-called barcodes (`count_ready`) with
caller-declared sample, capture and timepoint metadata. The processed BRIDGE v1
objects are retained only as historical downstream controls.

| Dataset | Formal simulated upload | Formal size | Historical BRIDGE v1 control | Provenance boundary |
|---|---|---:|---:|---|
| MacroDiff | Lossless multi-capture counts H5AD | 78,542 cells × 38,907 gene IDs; six captures | 57,464 cells × 34,097 genes | Chen Yuejun lab internal, unpublished |
| Studer-protocol D16 | Original filtered 10x-style MTX | 11,087 cells × 36,601 genes; one capture | 9,046 cells × 29,010 genes | Local sequencing asset; [Piao et al. 2021](https://doi.org/10.1016/j.stem.2021.01.004) supports MSK-DA01 product/protocol context, not a claim that the local files were deposited with the paper |
| SphereDiff | `count_ready` unavailable | — | 9,547 cells × 26,849 genes | [Zhang et al. 2025](https://doi.org/10.1016/j.stem.2025.10.001) deposited the relevant 3D-culture scRNA data under controlled `HRA008865`; exact local-sample mapping remains unresolved |

The MacroDiff upload contains every barcode in six upstream cell-filtered
matrices: 14,365 at D14, 15,050 at D21, 15,879 in the first D28 capture, and
9,896, 11,621 and 11,731 in three further D28 captures. The 57,464 historical
v1 cells are exact subsets of those sources. No further cell filtering was
applied while constructing the upload object; differing feature references
were joined by gene ID with sparse zeros for absent features.

All 9,046 Studer v1 barcodes are present in the 11,087-cell upstream filtered
matrix. The available files identify a local sequencing and count-generation
run, so publication status is attached to the differentiation/product protocol
rather than silently transferred to the local data provenance.

SphereDiff remains an explicit missing-input case. The downstream v1 object is
not relabeled as raw counts, and the controlled study is not opened or copied
without an exact sample map and access authorization.

The private source-input manifest has SHA-256
`5ee8d2b808e3d11d595a8388b9d34be5bbeae1b8986dc471a58817fffd358d94`.
It records server-only paths, per-file hashes and barcode correspondence; none
of these private fields may enter public figures. The MacroDiff and Studer runs
remain outstanding at this commit. SphereDiff is blocked only for formal
`count_ready` testing and does not block validation of honest unavailable-state
rendering.

## Supplemental public-data engineering stress test

The repository's
[foundation-materials matrix](../registries/BRIDGE_foundation_materials_matrix_20260713.tsv)
identifies [GSE204796](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE204796)
as a public hPSC midbrain dopaminergic differentiation time course. It is used
here only as a supplemental multi-capture engineering stress test. The
checksummed server object contains 37,397 cells by 33,538 genes, with raw counts
and normalized-expression layers.

| Caller-declared capture | Differentiation time | Cells |
|---|---:|---:|
| capture_001 | D8 | 4,013 |
| capture_002 | D14 | 10,036 |
| capture_003 | D21 | 10,233 |
| capture_004 | D28 | 6,247 |
| capture_005 | D35 | 6,868 |

These captures are successive time points in one reported differentiation
protocol. They are not treated as independent preparations, product lots or
biological replicates. The complete panel was used to exercise the per-capture
figure layout; D28 and D35 remain candidate product-stage query units for later
product-facing examples.

| Item | Value |
|---|---|
| Validated implementation commit | d9eb9602e1b12ee1ba7a352fe3966a73ecb13416 |
| Input SHA-256 | 679206f530f233dd85cf39e4c36cfc1c270603a4a785614513d1c22fa04474b7 |
| Wheel SHA-256 | 52c4be95fa6f55ecbf3c1c0129112c53e2c31d773f28d8bc40c7ea82783f5b1a |
| Run ID | run-08536b4cd15be1cf |

The run retained all 37,397 cells. Under the selected candidate MeasurementSpec,
37,190 were candidate-eligible and 207 carried at least one review flag: 201
had a high mitochondrial fraction, five had high detected-gene counts, and one
had both low detected-gene counts and a high mitochondrial fraction. These are
technical review flags, not removed cells or product-quality findings.

The real-data audit found that the first implementation stored raw medians and
quartiles while labeling them with display-transformed units. The implementation
now records counts as counts, detected features as genes, and expression
fractions as fraction; log10 and percentage transformations remain confined
to figure axes. All eight rendered SVG/PNG files remained byte-identical across
this correction.

| Public artifact | SHA-256 |
|---|---|
| Typed visualization data JSON | 70b37acb816b51f12c6ca8b080810e597ff72488b1bbcad65466096c78f51fd4 |
| Table fallback TSV | f57613536fbcc684b9a987903d422ecf1decf80f9804d2f9c22012adb5e006bb |
| Visualization artifact set | 6d6400c25ea2414fdf24d6041e20c3248fed2ab3e4f00328ab72caf53a404d1f |

Gzip compression reduced the derived all-observation candidate-flag H5AD from
3,080,543,078 to 690,995,440 bytes (77.6%). The exact compressed run took
145.82 s wall time, 1,644.58 s CPU and 5.99 GiB peak RSS on the shared server,
compared with 42.09 s wall time for the initial uncompressed run. This is an
explicit storage/runtime trade-off, not a performance guarantee. The public
visualization JSON, TSV, artifact set and SVGs contained no source accession,
raw capture identifier, user name or server path.

## Runtime observations

| Measurement | Result |
|---|---|
| End-to-end P0-01 run | 33.32 s wall; 550.97 s CPU; 4.05 GiB peak RSS |
| Exact current four-figure render, five runs | 9.586 s median wall, 8.995–10.416 s range |
| Exact current render CPU | 188.156 s median, 141.907–219.588 s range |
| Exact current render peak RSS | 430.79 MiB median, 429.70–441.91 MiB range |
| Eight rendered files | 3,872,637 bytes per run |
| Repeated output identity | all eight SHA-256 maps identical across five runs |
| Renderer stderr | 0 bytes across five runs |

The render timing starts after the metrics table and backed observation metadata
are loaded. BRIDGE's render cache was disabled; operating-system caches were not
controlled. The server was shared and had concurrent high-CPU work, so the
range is an observed resource record rather than a runtime guarantee.

## Engineering gates

| Gate | Result |
|---|---|
| Complete installed-wheel repository suite | `1375 passed, 20 warnings` |
| Tool discovery | 12 packages, `P0-01` through `P0-12` |
| Figure registry | valid; 11 components; 4 typed candidates; 7 legacy untyped |
| Knowledge snapshot | valid; 354 methods; 396 bindings; 0 formal-eligible methods |
| Repository policy and tracked-file budget | passed |
| Generated Schema and Tool Card parity | passed |
| P0-01 example/spec version | `0.1.3`, consistent |
| Installed-wheel import and dependency check | passed |
| Public identifier/path scan | passed |
| Deterministic render hashes and vector-SVG test | passed |

The 20 warnings are existing AnnData duplicate-name, SciPy sparse-matrix
migration and Scanpy score-genes warnings from unrelated or compatibility
fixtures.

## Scientific boundary

All 77,804 observations met the selected **candidate** technical rules in this
particular processed matrix, and no candidate QC flag was raised. This means
only that the observations satisfied those declared technical conditions. It
does not establish biological identity, product quality, safety, potency,
efficacy, batch release or a pass/fail decision. The candidate H5AD retains all
observations; it is not represented as a completed filtering result.

P0-01 remains a technical input and evidence-availability tool. It does not
promote an unresolved capture to a biological replicate, infer missing
downstream stability, or change the project-wide `domain_score=null` boundary.
