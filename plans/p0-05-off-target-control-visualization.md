# P0-05 Off-target and Unknown Visualization

## Motivation

Researchers need to distinguish four questions that are easy to conflate:

- which observations fall outside the currently declared target roles;
- which identities or product roles remain unresolved;
- what a zero or low rare-state observation can exclude at the available detection capability;
- whether independent OOD evidence families agree, disagree or were not assessed.

P0-05 already returns these records but has no typed table or figure output.
The current change makes those boundaries visible without reannotating cells,
training an OOD model or turning a draft product definition into a safety claim.

## Scope

- Correct count-interval applicability when whole-product composition coverage
  is incomplete.
- Add package-owned typed visualization data and an artifact set.
- Render three deterministic figure families with exact table fallbacks:
  1. whole-product role composition and unresolved identity ledger;
  2. rare-state observations and distinct detection boundaries, with spike-in
     recovery when supplied;
  3. OOD source-family and channel evidence-state matrix.
- Register the figures and expose them through the existing P0-05 run seam.
- Update the Tool Card, package documentation and stable visualization index.

## Semantic invariants

- `known_off_target` means outside the current product definition; it does not
  mean harmful, unsafe or failed.
- `role_unresolved`, identity unknown, OOD and technical exclusion are distinct.
- Zero observed, below a supplied detection boundary, unavailable, conflict and
  not assessed remain distinct states.
- A cell-count interval describes the selected capture; cells are not
  biological replicates.
- `zero_observation_upper_bound_fraction`, supplied validated detection limit
  and spike-in candidate detection limit are never renamed as one generic LOD.
- OOD coordination summarizes supplied source-family states; it is not a
  probability, majority vote or biological truth.
- Missing values are never rendered at zero, and `domain_score` remains `null`.

## Frozen interfaces

- Tool ID `P0-05`.
- `ToolRequestV2` and `ToolRunV2` envelopes.
- Existing primary and method result Schemas.
- External ProductDefinitionCard, StateRoleMap and assessment rules remain the
  only sources of product-role and threshold decisions.

## Non-goals

- No expression-matrix access, clustering, annotation or rare-state discovery.
- No OOD model training, threshold learning or classifier benchmark.
- No cross-product comparison or biological-replicate inference.
- No safety, potency, efficacy, release or ranking conclusion.
- No shared chart framework beyond the existing visualization registry seam.

## Implementation outline

1. Reconcile partial-coverage behavior between the primary profile and method
   intervals.
2. Define the smallest package-owned record types and one top-level typed data
   object.
3. Generate exact TSV fallbacks from the same records used for rendering.
4. Render SVG, PDF and PNG from those records with direct labels, redundant
   shapes and explicit missing-state panels.
5. Attach one checksummed artifact-set object and register the three figures.
6. Regenerate public and packaged Schemas from the single model source.

## Completion criteria

- Counts and fractions close only when coverage is complete.
- Partial or missing coverage cannot yield available intervals or zero-valued
  marks.
- Every detection boundary retains its exact semantic name and provenance.
- Source families are deduplicated before any coordinated OOD summary.
- Tables and figures consume the same ordered record set.
- SVG, PDF and PNG are deterministic and retain legible direct labels.
- Package discovery, Schema parity, figure registry and repository policy remain
  consistent.

The plan is removed when the implementation is merged; stable facts remain in
