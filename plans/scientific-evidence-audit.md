# Scientific Evidence Audit and Product-Context Decision Packet

**Status:** preparation_complete_awaiting_research_intent_decision.
**Branch:** `scientific-evidence-audit`.
**Baseline:** `origin/main` at
`5720670b13bd7c70abb95ebbe8937e326ba893db`.
**Writable scope:** this branch-scoped plan and its new validation inventory only.
Existing scientific contracts, schemas, package code, thresholds, reference
resources and shared indexes remain unchanged.

## Goal and non-goals

Prepare the smallest reviewable input set needed before a genuine D28 product
assessment can be specified for P0-03, P0-04 and P0-05. This plan does not run
new science, change the P0-02 candidate, open locked or sealed data, qualify a
state or method, create a score, or approve a product claim.

The exact CellTypist/energy candidate evaluated in
`cell_state_development_20260911.md` failed its versioned development-entry
criteria. That result does not mean every future P0-02 method or the package
interface has permanently failed. No newer development or locked-evaluation
result was found on current `origin/main` or the extant repository branches
reviewed on 2026-09-15.

## Bound genuine D28 input

The preserved private run contains one GSE204796 D28 author-count matrix. The
selected view has 5,588 observations and 33,538 unchanged features after a
candidate technical QC selection from 6,247 observations. The H5AD declares one
`sample_id`, one `capture_id` and one `culture_day=28` value. The selected
`DataViewBinding` has no `sample_or_preparation_ref`, no
`biological_unit_manifest_ref` and no biological-unit manifest checksum.

Therefore the currently supportable design statement is:

- one observed sequencing capture/source sample at D28;
- preparation identity and relationship to the source sample: `unknown`;
- donor, cell line, manufacturing lot, pooling and cross-timepoint relationship:
  `unknown`;
- biological independence: `unknown`; independent `n=null`;
- the 5,588 cells are observations, not biological replicates.

These values may be bound read-only to a candidate ProductCase. They must not be
silently promoted to a reviewed BiologicalUnitManifest.

## ProductDefinitionCard decision

### Evidence available

- The maintained development review defines the product scope as
  `ventral_midbrain_dopaminergic`, with intended stages `progenitor` and
  `early_neuroblast`; identity and developmental stage are evaluated separately.
- GSE204796 supplies a D8/D14/D21/D28/D35 in-vitro differentiation series, but
  the current selected input is D28 only.
- Human fetal VM sources support broad radial-glial/neuroblast and neuronal
  context. They do not provide a direct conversion from culture day to fetal age
  or a product-release truth label.

### Counterevidence and limits

- The evaluated CellTypist/energy candidate did not meet selective-precision,
  rejection or preprocessing-sensitivity entry criteria.
- The seven priority L2 labels are maintained as `parent_only`; their fine
  anatomical names are historical source partitions rather than independently
  validated product identities.
- No independent product preparation, functional, potency, safety or release
  endpoint is bound to the D28 input.

### Recommendation

Keep the current contract object at `review_state=draft`. Describe the intended
research use as: "hPSC-derived ventral-midbrain/mDA candidate at an intended
pre-transplant research stage, evaluated with scRNA-seq." Record progenitor and
early-neuroblast inclusion separately as research intent. This wording does not
state that the observed D28 product is transplant-suitable or that its cells
have been measured as belonging to either stage. Do not encode target purity,
efficacy, safety, potency or release suitability in the definition.

## Seven priority L2 product-role decisions

All seven state decisions below are `parent_only` in development review v1.1.
The listed source programs support the broad parent, not the fine regional child.

| State | Maintained evidence | Important counterevidence | Recommended role now | Optional hypothesis-sensitivity tag |
|---|---|---|---|---|
| `RG_mFP` | Radial-glial parent markers; historical floor-plate-associated name | Shared FOXA2/LMX1A context is not unique mDA evidence; child discriminator is unvalidated | `role_unresolved` | floor-plate-target hypothesis |
| `RG_mBMP` | Radial-glial parent markers | Historical mBM/mBMP terminology and anatomical boundary unresolved | `role_unresolved` | adjacent-domain hypothesis |
| `RG_mBIP` | Radial-glial parent markers | Historical mBL/MHB merge does not define one anatomical compartment | `role_unresolved` | adjacent-domain hypothesis |
| `Nb_mFP` | Neuroblast parent markers | Manual cluster mapping and incomplete historical sublabels do not establish floor-plate lineage | `role_unresolved` | floor-plate-target hypothesis |
| `Nb_mBMP` | Neuroblast parent markers | Merged clusters, restricted ages and parent conflicts limit anatomical inference | `role_unresolved` | adjacent-domain hypothesis |
| `Nb_mBIP` | Neuroblast parent markers | No independent child-specific positive/counter program | `role_unresolved` | adjacent-domain hypothesis |
| `Nb_mAP` | Neuroblast parent markers | mAL-to-mAP naming and mostly absent historical sublabels do not establish alar identity | `role_unresolved` | off-target hypothesis |

Retain all seven as `role_unresolved` until a fine-state discriminant is
supported. The final column is not a StateRoleMap and cannot assign observed
cells to target, adjacent or off-target roles. An engineering task may compare
those assumptions as explicitly hypothetical sensitivity scenarios without
requesting scientific endorsement. Such arithmetic must remain isolated from
the genuine ProductCase and cannot enter a biological identity, purity,
off-target or window conclusion.

Source-label target and window mappings therefore remain `unavailable` even if
the research intent is confirmed.

## DevelopmentWindowSpec decision

### Candidate options

1. `intended_pre_transplant_progenitor_research_stage` — records a
   progenitor-only research intention, not observed transplant suitability.
2. `progenitor_plus_early_neuroblast` — matches development review v1.1's stated
   product scope and avoids treating early neuroblasts as automatically late.
3. `descriptive_D28_only` — preserves culture day as context and asks no fetal-age
   compatibility question. This is the only option requiring no biological-age
   inference, but it cannot produce a window-compatibility conclusion.

### Recommendation

Use option 2 as the intended research-window candidate and keep
`review_state=candidate`. User confirmation defines the question to ask; it does
not establish that broad radial glia are `within_window_progenitor`, that broad
neuroblasts are `within_window_early_neuroblast`, or that any fine L2 state has a
product role. Those measurement mappings remain unavailable until supported by
a reviewed state-stage mapping. Preserve `D28` as an in-vitro sampling label;
do not map it to GW/PCW.

### User decision required

Should the intended pre-transplant research stage include early neuroblasts, or
should the intended research window be restricted to progenitor states?

## Report-admission matrix

| Domain | Current evidence | Admission now | Required before stronger use |
|---|---|---|---|
| P0-01 technical QC | Genuine installed 0.1.5 D28 run; 6,247 input, 5,588 selected; exact candidate thresholds and limitations preserved; current source is 0.1.6 | Research report as version-bound technical selection with `limited` QC; not product quality or current-version real acceptance | Raw droplets/ambient and doublet-threshold sensitivity; current-version rerun if 0.1.6 behavior is claimed |
| P0-02 source/state evidence | Genuine installed 0.5.5 D28 source-specific candidate run plus real reference/OOD development evidence; current source is 0.6.1 | Exploratory source-conditioned observations and explicit 0.6.x candidate method-limit finding; these are distinct evidence records | Current candidate real-product run, new versioned candidate meeting development entry, then untuned locked evaluation for qualification |
| P0-03 target/regional | Current runtime and expression methods validated on synthetic contracts; an older private visualization summarized real-derived MacroDiff/SphereDiff/Studer labels under a draft role map but lacked independent units and identity validation | The older figures may illustrate source-label-conditioned counting only; `unavailable` for genuine D28 product conclusion | Confirmed research intent plus evidence-supported StateRoleMap, genuine unit lineage, suitable references/programs and a current source-bound real run |
| P0-04 developmental compatibility | Current runtime validated on synthetic contracts; older private MacroDiff/SphereDiff/Studer figures used real-derived counts inside explicitly synthetic `demo` cases/manifests/windows; D28 is a real categorical timepoint | Older figures are visualization/contract demonstrations, not genuine developmental evidence; D28 context and `static_profile` limitation only | Confirmed research intent plus evidence-supported state-stage map, source-bound reference support and genuine units; numeric time contract for trends |
| P0-05 off-target control | Aggregation/method/count accounting validated on synthetic contracts only | `unavailable`; no absence or safety statement | Reviewed roles, genuine whole-product denominator, OOD holdouts and rare-state calibration/LOD |
| P0-06 proliferation/stress | Genuine 0.8.1 selected-view run (5,588; S+G2M 38.96%) and separate genuine 0.8.2 all-view run (6,247; S+G2M 42.58%); independence unknown | Version-and-view-bound exploratory expression-program and predicted-phase observations; the difference is not biological-change evidence | A 0.8.2 selected-view rerun before claiming current selected-view behavior; genuine unit lineage and stage conditioning for inference; selected and validated stress programs for stress claims |
| P0-08–P0-10 report chain | Can preserve measurements, missingness and claim limits in versioned research reports | May carry the rows above without upgrading them | Same-version genuine graph/report acceptance and qualified upstream evidence |

## Proposed execution scope and prerequisites

After the single research-intent decision above, a separate implementation task
may prepare inputs, but genuine P0-03 through P0-05 measurements remain blocked
until their additional prerequisites in the admission matrix are present. The
proposed scope for a separately assigned implementation task is:

1. materialize versioned candidate input objects without changing package code;
2. bind the existing selected D28 DataView and all unknown unit relationships;
3. emit typed `unavailable` for P0-03, P0-04 and P0-05 wherever a required
   measurement mapping, reference, unit lineage or calibration remains absent;
4. optionally run isolated hypothesis-sensitivity arithmetic that cannot be
   joined to the genuine ProductCase or reported as product evidence;
5. reuse a verified P0-06 descriptive result only when its exact DataView,
   version, hashes and dependencies match the report question; the 0.8.2
   all-view run cannot substitute for the 0.8.1 selected-view result;
6. compile a same-version research report whose admission state matches the
   matrix above.

Stop if an input requires inventing a biological unit, converting D28 to fetal
age, treating a source label as validated identity, substituting missing mass
with zero, or weakening the failed-development-entry status.
