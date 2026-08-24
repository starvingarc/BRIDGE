# P0 stack literature-grounded peer review — 2026-08-24

## Scope and evidence hierarchy

This review re-examined Draft PR #29 at pre-revision head
`cade8a8c9484fb69e2e5895366f1a40a4b4c419d` from three independent lenses:
cell-product biology, single-cell experimental design/statistics, and
AI-for-science provenance/reproducibility. The initial verdict was **major
revision**. Final exact-head acceptance remains pending server validation and
same-SHA re-review.

Evidence was used in this order:

1. peer-reviewed primary studies and benchmark papers;
2. peer-reviewed methodological guidance and systematic reviews;
3. formal provenance, integrity and reproducibility standards.

No preprint, including any 2026 preprint, was used to create or raise the
severity of a finding. Recent clinical papers provide biological context; they
do not convert transcriptomic engineering checks into safety, efficacy,
potency or release evidence.

## Review findings and closure

| Severity | Modules | Literature-grounded concern | Closure in this revision |
|---|---|---|---|
| Critical | P0-06, P0-07, P0-12 | Cells, captures and repeated observations are nested measurements, not independent biological replicates. A caller-controlled `reviewed` label cannot establish independent N. | Caller review labels and checksums are trace-only until a trusted receipt verifier exists. Ordinary requests yield zero eligible group/animal N and cannot unlock flags or direction. Tests inject verifier outcomes only to exercise deterministic mechanics. |
| Important | P0-07 | Literal group-name disjointness is meaningless unless arms share one identity namespace and independence scope. | Both manifests must share exact namespace and scope; cross-arm overlap fails. No implicit crosswalk or pairing is inferred. |
| Important | P0-07 | Averaging repeated preparation values inside a group silently chooses an estimand and can discard denominator structure. | Repeated within-group observations return `within_group_aggregation_policy_not_supplied`; no arithmetic or denominator-weighted pooling occurs without an explicit contract. |
| Important | P0-12 | ProductCase independence groups are not necessarily physical preparations, so they cannot authorize graft-source linkage. | P0-12 now requires the exact ProductCase BiologicalUnitManifest and resolves source preparations only from `unit_bindings.preparation_ref`. |
| Important | P0-12 | String agreement among assay/context fields does not demonstrate applicability to the real graft specimen, sorting method or assay. | The current slice reports `graft_assay_applicability_not_assessed`; without trusted lineage verification it publishes no animal-level summary. A typed GraftCase remains future work. |
| Important | P0-09 | A catalog object could claim a MeasurementResult hash different from the exact input bytes. | Catalog `content_hash` must equal the SHA-256 of the exact StructuredInputRef bytes before compilation. |
| Important | P0-03 | `not_target` plus `target_region` is a semantic contradiction independent of mutable PD-mDA state assignments. | The public role model now enforces only cross-axis non-contradiction; all state-to-role biology remains versioned input. |
| Important | P0-05 | Unexplained denominator residual has unknown identity, not a known identity with unresolved product role. | Residual mass enters `unknown` with `composition_residual_identity_unknown`; the executor does not guess a cause. |
| Important | stack handoff | A contract-chain test was described too broadly as production end to end. | The test now passes an actual P0-08 result artifact and exact P0-10 ToolRun/result, while explicitly identifying synthetic ReportDraft authoring and external orchestration. |

## Scientific and statistical basis

### Biological replication and estimands

- Zimmerman et al. showed that within-sample correlation in single-cell studies
  creates pseudoreplication when cells are treated as independent units
  ([Nature Communications, 2021](https://doi.org/10.1038/s41467-021-21038-1)).
- Squair et al. found that methods retaining biological-replicate structure,
  particularly pseudobulk approaches, better control false discoveries than
  cell-level testing
  ([Nature Communications, 2021](https://doi.org/10.1038/s41467-021-25960-2)).
- Lazic et al. explain why the experimental unit, rather than the number of
  measurements, defines N
  ([PLOS Biology, 2018](https://pubmed.ncbi.nlm.nih.gov/29617358/)).
- A recent cross-omics design review reiterates that biological replicates must
  be independently sampled and that nested subsamples do not increase N
  ([Nature Communications, 2025](https://doi.org/10.1038/s41467-025-62616-x)).

These sources support fail-closed biological-unit authorization and explicit
within-group estimands. They do not select a universal aggregation rule; that
choice remains a versioned MeasurementSpec/analysis contract.

### Composition, missingness and reference sensitivity

- scCODA models cell-type counts jointly as compositional data and emphasizes
  replicate-aware uncertainty rather than independent univariate fractions
  ([Nature Communications, 2021](https://doi.org/10.1038/s41467-021-27150-6)).
- Milo performs differential-abundance testing over neighborhoods while
  retaining sample-level replication
  ([Nature Biotechnology, 2022](https://pubmed.ncbi.nlm.nih.gov/34594043/)).
- Large-scale single-cell integration benchmarking shows that biological
  conservation and batch removal must be evaluated together
  ([Nature Methods, 2022](https://pubmed.ncbi.nlm.nih.gov/34949812/)).
- A recent atlas-scale annotation study reports marked out-of-distribution
  degradation on unseen studies
  ([Nature Computational Science, 2026](https://doi.org/10.1038/s43588-025-00945-z)).

These papers justify preserving `unknown`, denominators, reference scope and
OOD/applicability states. They do not justify hard-coded cell-state roles or a
fixed biological threshold.

### Dopaminergic product and graft biology

- Transplant-stage markers can predict graft outcome, while commonly used
  markers alone may not
  ([Cell Stem Cell, 2017](https://pubmed.ncbi.nlm.nih.gov/28094017/)).
- Single-cell differentiation maps show heterogeneous adjacent regional
  identities and demonstrate that enriched progenitor markers can change graft
  composition and function
  ([Journal of Clinical Investigation, 2022](https://pubmed.ncbi.nlm.nih.gov/35700056/)).
- Donor developmental age changes graft survival, composition, maturation and
  innervation, with cell-line-dependent effects
  ([Cell Stem Cell, 2022](https://pubmed.ncbi.nlm.nih.gov/36055392/)).
- Barcode lineage tracing shows that dopamine neurons, astrocytes and vascular
  leptomeningeal cells can share a transplant-stage progenitor origin, so graft
  identity and source linkage require measured lineage evidence rather than
  name matching
  ([Science Advances, 2024](https://doi.org/10.1126/sciadv.adn3057)).
- A systematic review found very wide between-study variation in progenitor
  survival and dopaminergic differentiation, reinforcing the need to preserve
  assay, specimen and experimental-design context
  ([2024 systematic review](https://pubmed.ncbi.nlm.nih.gov/39589166/)).
- Recent clinical reports establish current feasibility and early safety
  observations for hPSC-derived dopaminergic transplantation, but remain
  early-phase, product-specific studies
  ([Nature, 2025](https://doi.org/10.1038/s41586-025-08845-y);
  [Nature Medicine, 2026](https://doi.org/10.1038/s41591-026-04525-0)).

Accordingly, P0-03 to P0-07 and P0-12 may assemble configured evidence but must
not turn transcriptomic compatibility into clinical efficacy, safety, potency
or release claims.

## AI4S provenance and reproducibility basis

- [W3C PROV-DM](https://www.w3.org/TR/prov-dm/) distinguishes entities,
  activities and agents; content identity alone does not authenticate the agent
  that approved an entity.
- [W3C Data Integrity](https://www.w3.org/TR/vc-data-integrity/) separates
  cryptographic integrity/proof mechanisms from ordinary application fields.
- [FAIR4RS](https://doi.org/10.1038/s41597-022-01710-x) requires detailed
  software provenance and versioned, reusable research software metadata.
- [RO-Crate 1.3](https://w3id.org/ro/crate/1.3) provides a machine-readable
  packaging model for data, software, workflows and provenance.
- The [Reproducible Builds formal definition](https://reproducible-builds.org/docs/formal-definition/)
  requires identical outputs from identical source, environment and build
  instructions; a passing source-tree test alone is weaker evidence.
- Recent CURE guidance similarly emphasizes credibility, understandability,
  reproducibility and extensibility for computational biology models
  ([npj Systems Biology and Applications, 2026](https://doi.org/10.1038/s41540-026-00651-0)).

These sources motivate exact-byte bindings, immutable artifacts, installed-wheel
tests and an external review-authority boundary. They do not imply that the
current package possesses identity, signature or public-release authority.

## Remaining limitations after the code revision

- No trusted review-receipt verifier exists. This is intentionally visible as
  unavailable evidence, not hidden behind a development default.
- P0-07 still accepts a structurally valid P0-08 result without a separately
  authenticated producer ToolRun. Because review authority is unavailable, this
  cannot unlock eligible N or directional claims; producer authentication is
  required before those gates can be reopened.
- Semantic ReportDraft authoring and P0-09-to-P0-10 orchestration are outside the
  implemented P0 package chain.
- P0-12 lacks a typed GraftCase binding actual specimen, assay, sorting and host
  metadata. Assay applicability therefore remains `not_assessed`.
- StateRoleMap, DevelopmentWindowSpec, program definitions, reference choices,
  thresholds and ScoreContract remain biologically unreviewed configuration.
- All packages remain `candidate`; P0-02 remains
  `biological_review_in_progress`; `domain_score` remains null and no method is
  formal-eligible.

## Acceptance rule

The revision can leave major-revision status only after one immutable final SHA
passes source and clean-wheel gates on `/data1` and the biology, single-cell
statistics and AI4S reviewers independently report no unresolved Critical or
Important finding on that same SHA. That acceptance is engineering review only;
it does not make the Draft PR Ready or authorize merge or scientific release.
