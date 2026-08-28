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
