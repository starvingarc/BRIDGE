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

The wheel was built from the implementation commit, force-installed into a fresh
Python environment and imported from that environment's `site-packages`. All
declared P0 extras were installed together without dependency conflicts.

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

The public JSON, TSV and artifact set exposed only anonymized capture labels,
typed scientific records and checksums. All four current SVGs contained zero
embedded raster images; PNG fallbacks were rendered at 300 dpi. Missing or
unavailable evidence was shown explicitly rather than as a zero value.

The end-to-end data profile was generated at `c0f3515d890de90453c576cbf724bdf06448fe98`.
The subsequent changes through the validated implementation commit updated only
registry expectations, numeric capture ordering, single-intersection scaling,
SVG colorbar representation and available font weights. They did not change QC
metrics, the candidate measurement rules or the typed data profile.

## Count-ready input validation panel

P0-01 begins at an expression matrix or analysis object, not at FASTQ or BAM
reprocessing. Formal figure validation therefore uses unnormalized,
non-negative integer counts from cell-called barcodes (`count_ready`) with
caller-declared sample, capture and timepoint metadata. The processed BRIDGE v1
objects are retained only as historical downstream controls.

| Dataset | Evaluation input | Formal size | Historical BRIDGE v1 control | Provenance boundary |
|---|---|---:|---:|---|
| MacroDiff | Lossless multi-capture counts H5AD | 78,542 cells × 38,907 gene IDs; six captures | 57,464 cells × 34,097 genes | Chen Yuejun lab internal, unpublished |
| Studer-protocol D16 | Original filtered 10x-style MTX | 11,087 cells × 36,601 genes; one capture | 9,046 cells × 29,010 genes | Protocol-linked sequencing asset; [Piao et al. 2021](https://doi.org/10.1016/j.stem.2021.01.004) supports MSK-DA01 product/protocol context, not dataset identity |
| SphereDiff | `count_ready` unavailable | — | 9,547 cells × 26,849 genes | [Zhang et al. 2025](https://doi.org/10.1016/j.stem.2025.10.001) deposited the relevant 3D-culture scRNA data under controlled `HRA008865`; exact sample mapping remains unresolved |

The MacroDiff input contains every barcode in six upstream cell-filtered
matrices: 14,365 at D14, 15,050 at D21, 15,879 in the first D28 capture, and
9,896, 11,621 and 11,731 in three further D28 captures. The 57,464 historical
v1 cells are exact subsets of those sources. No further cell filtering was
applied while constructing the input object; differing feature references
were joined by gene ID with sparse zeros for absent features.

All 9,046 Studer v1 barcodes are present in the 11,087-cell upstream filtered
matrix. The sequencing and count-generation provenance is distinct from the
published differentiation/product protocol context.

SphereDiff contributes only the historical `analysis_ready` control until its
sample map and count-ready access state are resolved.

A checksummed validation manifest binds input versions, per-file hashes and
barcode correspondence. This record contains aggregate scientific and
engineering results. SphereDiff remains an explicit unavailable-input
rendering case.

### Exact-wheel results

Both eligible inputs were validated with a wheel built from the same clean
implementation commit. The installed package was loaded from the isolated
validation environment rather than from the source worktree.

| Item | Value |
|---|---|
| Validated implementation commit | `88268b95cfe6857cb56b151bfcba7f20b35c5dc7` |
| Wheel SHA-256 | `c14de8d77657c7f26b16797ad5c750beb1212809c8ea9930ba6c03151c687c90` |
| Runtime | Python 3.12.13; NumPy 2.2.6; pandas 2.3.3; SciPy 1.16.3; AnnData 0.12.19; Matplotlib 3.10.9; PyArrow 21.0.0; h5py 3.14.0 |
| Hardware | x86_64; Intel Xeon Gold 6330; 112 visible CPUs |

| Result | MacroDiff | Studer-protocol D16 |
|---|---:|---:|
| Run ID | `run-155afe6da2d72b33` | `run-58fd6c6f8a81a8c6` |
| Declared cells | 78,542 | 11,087 |
| Candidate-eligible | 77,946 | 10,315 |
| Flagged for review, not removed | 596 | 772 |
| Mutually exclusive flag combinations | 310 high mitochondrial; 264 high detected genes; 22 low detected genes + high mitochondrial | 682 high detected genes; 86 high mitochondrial; 4 low detected genes + high mitochondrial |
| First/repeat wall time | 4:14.77 / 4:00.45 | 1:08.50 / 1:06.36 |
| First/repeat peak RSS | 8.30 / 8.29 GiB | 2.27 / 2.25 GiB |

Both inputs had unique observation and gene identifiers, non-negative integer
counts and complete caller-declared sample/capture metadata. The six MacroDiff
captures were displayed as D14, D21 and four D28 captures without exposing raw
capture identifiers. The Studer input was displayed as one D16 capture. Missing
upstream library reports remained `not_assessed`. Cell calling and ambient-RNA
assessment remained `not_assessed` because these were cell-called `count_ready`
inputs rather than unfiltered droplets; Scrublet remained `not_assessed` because
it was not requested. Count-based QC was eligible, downstream scientific modules
remained conditional, and `domain_score` remained `null`.

Each input was run twice in the same wheel environment. The 18 core outputs for
each run were byte-identical across repeats: five SVGs, five PNGs, typed JSON,
Parquet, TSV, the visualization artifact set, the metrics table, the compressed
candidate-view H5AD and both readiness profiles. Formal artifact hashes were:

| Public/derived artifact | MacroDiff SHA-256 | Studer-protocol D16 SHA-256 |
|---|---|---|
| Typed visualization JSON | `edb755c8f30f5e228347c45506a3e7dd21b2d3454b808f286ed972205aacc0a1` | `e89d873fb924e9048b752b583ff4f00bc2315bc6f41c26e4f97ff17ada902c81` |
| Table fallback TSV | `3dddfd1af2cb152b2d8911df331d7d4e1acdd5162679f92c4b8974c9c7450118` | `96d023dc7bc5548bb9c2ff69824b2d2f92c4383b4b3e21745ab0e4c836130122` |
| Visualization artifact set | `f8f9a12e5c832f64fb364fd2babef71837bd0c8cd3e603db1f0e0bbe7ee1785e` | `f1e65233455b6b95e2a6dea527150bba253b776ebbb955bbdee2873322ef2e04` |
| Candidate-view H5AD | `f7a84b52e1169f4b55379a51c1abe0787e769e6fe21edd90a4958a8522c7250a` | `90c6e9a9c6d8e42244b9754857a2df526425e00b9dda36237ea7b7583c8b306d` |

The final figures were inspected at publication scale. Capture ordering,
denominators, threshold labels and review-flag wording were legible. The
publication scan confirmed that the 16 JSON, TSV, artifact-set and SVG files
used anonymized capture labels and typed aggregate records.

## Supplemental public-data engineering stress test

The repository's
[foundation-materials matrix](../registries/BRIDGE_foundation_materials_matrix_20260713.tsv)
identifies [GSE204796](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE204796)
as a public hPSC midbrain dopaminergic differentiation time course. It is used
here only as a supplemental multi-capture engineering stress test. The
checksummed input object contains 37,397 cells by 33,538 genes, with raw counts
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
145.82 s wall time, 1,644.58 s CPU and 5.99 GiB peak RSS under the observed
workload,
compared with 42.09 s wall time for the initial uncompressed run. This is an
explicit storage/runtime trade-off, not a performance guarantee. The public
visualization JSON, TSV, artifact set and SVGs used anonymized capture
identifiers and typed aggregate records.

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
are loaded. BRIDGE's render cache was disabled; operating-system caches and
concurrent system load were not controlled. The range is an observed resource
record rather than a runtime guarantee.

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
