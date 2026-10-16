# Quick atlas mapping v0

The research sample API can produce a persisted candidate mapping from declared
raw-count H5AD data, using the registered P0-01 input checks and P0-02
`ATLAS-ingest-quick-v0.1` mode. The [research-object contract](../plans/research-objects.md#76-样本取样后关联数据)
owns HTTP fields, statuses, retry and frontend rendering requirements.

## Method and boundaries

The method intersects exact, unique gene names in reference order. Missing genes
are recorded rather than filled with zeros. It normalizes and log-transforms the
shared gene counts, selects variable genes using reference expression only, centers
both matrices by the reference mean and fits PCA on the reference. Scanpy ingest
transfers reference labels. Both the effective feature set and PCA projection are
hashed; queries with different measured gene universes need not share a projection.
No query expression fits feature selection, centering or the PCA basis.
Duplicate sparse cell/gene entries are summed in private working copies before
normalization and log1p; equivalent count matrices retain the same result and
the original input buffers and files remain unchanged.

The implementation explicitly provides the query PCA representation and preserves
reference centering rather than allowing a query batch mean to shift individual
cell projections. See the [Scanpy ingest API](https://scanpy.scverse.org/en/stable/generated/scanpy.tl.ingest.html).
The frozen manifest owns numerical parameters; runtime receipts capture dependency
versions and exact input, reference, annotation, tree, feature and projection identities.

Numeric age/pseudotime summaries use exact nearest neighbors in this shared space.
Display points copy the nearest visible reference point with the same transferred
label and modality. They do not construct query scVI embeddings or a new trajectory.
Reference labels outside the neural tree retain missing positions. Label transfer
is closed-set: it does not establish out-of-reference detection. The result remains
`candidate`, with uncalibrated age/OOD, no chain measurements and no domain score.
Donor holdout, marker cross-checks, external controls and biological qualification
are separate work; successful engineering execution does not satisfy those gates.

## Private reference preparation

Run `scripts/prepare_quick_atlas_reference.py` in the controlled environment with
explicit `--atlas`, `--neurogenesis`, `--tree` and a new `--output` directory. The
optional `--modality` selects `scRNA` (default), `snRNA` or `both`. Preparation reads
reference count layers and required annotations, joins fine neural annotations by
cell ID, replays the existing deterministic display sampling and checks every tree
row's label, age, modality and pseudotime against its source. It never regenerates
tree geometry. Source files remain unchanged; their hashes are retained privately.

Each modality bundle contains `manifest.json`, `reference.h5ad`, `tree.json` and
`tree-cell-ids.json`. `catalog.json` maps `pre_graft` and/or `post_graft` to the
absolute manifest path and its SHA-256. Counts must pass explicit raw-count validation;
nonintegral or otherwise invalid matrices are rejected, never rounded or substituted.
A preparation failure does not make a partially written output catalog usable.

Set `BRIDGE_WEB_QUICK_ATLAS_CATALOG` to this private catalog and
`BRIDGE_WEB_WORKBENCH_TREE` to its matching tree when starting an authorized instance.
Pre-graft scRNA and post-graft snRNA have distinct fixed reference IDs. Configure only
resources that have passed preparation; an unavailable modality has no fallback.
The catalog, source identities, matrices, tree-cell IDs and real run receipts must
not be committed. The web process inherits the operator's pinned private ancestor
policy for its isolated worker.

## Lifecycle and acceptance

The worker runs one mapping at a time, shares account task quotas, validates input
and resource hashes before publishing and stores immutable JSON plus a full private
Parquet cell table. Public assessment reads verify the bound ToolRun and result.
Inputs without prerequisites remain attached with an explicit reason; a saturated
worker requires retry. A process interruption becomes a failed historical attempt,
and a later retry receives a new identity. Completed assessments are not recomputed
when a reference catalog changes.

Synthetic tests cover reference centering, gene intersection/order, source-bound
positions, tree-outside labels, modality refusal, registered QC/mapping execution,
ownership, artifact tampering and interruption/retry. Real-input acceptance belongs
in private, version-bound receipts and must independently check upload, persistence,
full-cell membership, exact tree coordinates and restart reads. It does not establish
frontend usability or scientific qualification.


## Marker expression for tree coloring

P0-02 0.8.1 adds an immutable `quick_atlas_marker_expression.json` artifact.
The default panel is FOXA2, LMX1A, OTX2, EN1, CORIN, SHH, NR4A2, TH, DDC and
PITX3. Expression is captured after shared-gene total-count normalization and
log1p, before HVG selection or reference centering. Sample rows use their own
counts; copying a reference neighbor's coordinates never copies its expression.
This display addition does not change mapping, chain metrics or scientific qualification.
The fixed panel is supported now; arbitrary gene selection remains future work.

A completed assessment carries a small `marker_expression` availability/version,
gene-list, content-hash and point-count summary. The authenticated research-owner
route `GET /api/researches/{rid}/assessments/{aid}/marker-expression` reads the
separate artifact on demand, checks its ToolRun/hash/path/tree/feature bindings,
and returns no source cell IDs or private paths. The full matrix is excluded from
workbench polling and Agent context. Missing old artifacts return 404
`marker_expression_unavailable`; a corrupted artifact returns 409
`mapping_result_unavailable` without invalidating an otherwise intact mapping summary.
Existing results are never silently recomputed.

`sample.values` rows align exactly with `mapped_cells` (at most 600 points).
`reference.tree_cell_indices` gives zero-based indices into the matching tree's
`cells` array, aligned with `reference.values`. Only cells in the selected mapping
reference appear; other modalities/unavailable reference cells remain missing.
The currently prepared sc reference therefore colors only the sc portion of the
fixed tree. It does not establish sn count semantics or permit modality fallback.

Columns follow `genes`. Missing shared-space genes are `null`; `gene_status`
identifies missing query/reference measurements. Measured zeros remain zero.
All values are rounded to six decimal places after log normalization. Consumers
must compare `tree_version` to the displayed tree version before applying colors.
`feature_set_sha256` and `normalization` describe the expression denominator;
different feature spaces are not directly comparable scales. These values are
neither batch-corrected absolute expression nor marker gates for a cell identity.


### Input gene identifiers

The current mapper intersects feature identifiers exactly, including case. It
expects query and reference to use the same gene namespace; a H5AD `gene_symbol`
column is not automatically substituted for Ensembl `var_names` by the HTTP path.
For source-backed acceptance inputs, a separate recorded preparation may use only
the source's own one-to-one gene-symbol annotation, retain the original feature
IDs, and verify that every count and axis position survives serialization.
Ambiguous or missing symbols retain their original IDs and are not merged or
imputed; they contribute only if that exact ID also exists in the reference.
This preparation is not normalization, an alias-database lookup, or a claim that
arbitrary Ensembl-indexed uploads are transparently supported. Input derivation
and this remaining direct-upload limitation must accompany acceptance results.
