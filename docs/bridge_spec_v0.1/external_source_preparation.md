# P0-02 External-Source Preparation

## Biological purpose and boundary

This procedure makes the public Birtele `GSE192405` processed matrices and the
Birtele/La Manno lineage declaration reproducible before any P0-02 locked
evaluation. It establishes source-file identity, matrix semantics, sample-unit
limits and source-family exclusion; it does not establish donor identity,
biological replication, a frozen cell state, a frozen method, a threshold or a
product role.

The current review state is `biological_review_in_progress`. Birtele is
conditionally approved only for source-level external holdout, stage-level
description and provisional-group sensitivity. Every sample remains
`replicate_eligibility=not_estimable`; `scientific_status` remains `candidate`,
`score_state` remains `shadow` or `unavailable`, and `domain_score` remains
`null`.

## Entrypoint

Install the project with the `qc` extra, then use the installed science-team
entrypoint:

```bash
bridge-benchmark cell-state prepare-birtele \
  --source-dir /path/to/gse192405-source-root \
  --output-dir /path/to/prepared-gse192405

bridge-benchmark cell-state audit-external-sources \
  --output /path/to/external-source-audit.json
```

The optional `--sample-map /path/to/birtele_gse192405_samples.yaml` and
`--lineage-map /path/to/external_source_lineage.yaml` arguments replace the
packaged maps. A replacement map is a versioned scientific input, not an
opportunity to infer missing donor relationships.

## `prepare-birtele` inputs

`--source-dir` names the source *root*, not only the CSV directory. With the
packaged sample map it must contain this immutable layout:

```text
gse192405-source-root/
  GSE192405_RAW.tar
  GSE192405_family.xml.tgz
  TableS1.xlsx
  paper_supplement/develop-149-200504-s1.pdf
  processed_csv/
    GSM5746439_hVM2015aggrd14.csv.gz
    ... 11 other expected GSM CSV files ...
    GSM5746451_MP06-hVM-6wks.csv.gz
```

There must be exactly the 13 expected `processed_csv/*.csv.gz` files. Their
SHA-256 values, the archive, the MINiML file, the supplement and Table S1 are
verified before matrix conversion. Each CSV must have a first row of unique cell
IDs, a first column of unique nonempty feature IDs, the shared ordered gene list,
and finite nonnegative integer counts. The bundled map pins `dataset_id` to
`GSE192405`, `version` to `1.1`, a `source_archive`, `metadata_sources`,
`external_asset_review`, `sample_unit_limitations`,
`expected_gene_order_sha256`, and one record for each expected `samples` GEO
accession. Every sample record supplies its filename and checksum; public
metadata; biological-unit and provisional-group fields; a technical-subdivision
ID; replicate eligibility; and any metadata conflicts.

Minimal fixture command with an explicit map:

```bash
bridge-benchmark cell-state prepare-birtele \
  --source-dir ./fixture/gse192405-source-root \
  --sample-map ./fixture/birtele_gse192405_samples.yaml \
  --output-dir ./build/gse192405
```

## `prepare-birtele` outputs and verification

The output directory must be absent or empty. A successful conversion writes:

| File | Meaning |
|---|---|
| `GSE192405.h5ad` | CSR `int32` matrix in `X`, with `matrix_semantics=raw_counts` and observation provenance |
| `sample_unit_map.tsv` | Frozen sample, biological-unit, provisional-group and replicate-eligibility projection |
| `source_manifest.json` | Archive, metadata and every processed-file SHA-256 plus review boundary |
| `qc_report.json` | Matrix, feature, observation, sample-unit and provisional-group checks |
| `conversion_manifest.json` | Converter version, input-map SHA-256, dimensions, review status and SHA-256 checksums for the other four output files |

Use `conversion_manifest.json` as the output checksum manifest and
`source_manifest.json` as the input provenance manifest. The converter never
modifies the supplied source root. Its public output does not contain server
paths or user identifiers.

## `audit-external-sources` inputs and outputs

The lineage map requires an `audit_id`, `version`, nonempty
`external_holdout_roots`, and unique `assets`. Each asset requires `asset_id`,
`root_source_family_id`, `parent_asset_ids`, `candidate_decision` and a
`rationale`. Candidate decisions are limited to development reference/OOD,
behavior-only, external-holdout, excluded-from-candidate and sealed-excluded
roles. Parent IDs must exist and the parent graph must be acyclic.

The audit resolves each asset's transitive root families, rejects any external
holdout root in a development-reference, development-OOD or behavior-only role,
and writes one deterministic JSON report. The report contains the lineage-map
SHA-256, all resolved roots, candidate decisions, external holdout roots,
`prohibited_overlap_count=0`, and `status=passed`. It reads lineage metadata
only: sealed `E-MTAB-14729` stays unopened and excluded.

Minimal fixture command:

```bash
bridge-benchmark cell-state audit-external-sources \
  --lineage-map ./fixture/external_source_lineage.yaml \
  --output ./build/external-source-audit.json
```

## Stable failure behavior

Both operations fail closed. They return no success manifest or report when
validation fails, and their Python exceptions carry stable machine-readable
reason codes. `prepare-birtele` raises `BirteleAssetError` for, among others,
`output_dir_not_empty`, `invalid_sample_map:*`,
`sample_map_accessions_mismatch`, `source_file_set_mismatch`,
`source_checksum_mismatch:<GSM>`, `provenance_checksum_mismatch:<file>`,
`gene_order_mismatch:<GSM>`, `duplicate_feature_id:<GSM>`, and invalid count
reasons such as `negative_count:<GSM>`. `audit-external-sources` raises
`ExternalSourceAuditError` for `invalid_lineage_map:*`,
`lineage_asset_ids_not_unique`, `lineage_parent_missing:<asset>:<parents>`,
`lineage_cycle:<asset>`, or
`external_source_lineage_overlap:<asset>:<external-root>`.

These reason codes describe input or provenance eligibility, not biological
failure. Do not substitute a partial output, a rerun with altered files, or an
inferred donor map for the failed input.

## Remaining scientific work

The preparation gate does not authorize opening locked OOD/source assets or
running the locked runner. Review the 25 state cards, ProductDefinitionCard and
StateRoleMap; freeze per-state acceptance, fallback and unknown rules; then sign
the FreezeGate before a single locked run without tuning. The current work still
cannot make target-cell, regional-fidelity, off-target composition, efficacy,
safety, potency, GMP-release or product-ranking claims.
