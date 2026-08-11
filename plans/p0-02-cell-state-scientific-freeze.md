# P0-02 Cell-State Scientific Freeze

| Field | Value |
|---|---|
| Branch | `codex/bridge-scientific-freeze` |
| Status | `awaiting_biological_review` |
| Owner | BRIDGE core |

## Biological question

Can a pre-transplant hPSC-mDA product be assigned to biologically defined fetal
ventral-midbrain states while unrelated neural and non-neural cells are left
unassigned?

This is the prerequisite for later Target Identity, Regional Fidelity,
Developmental Compatibility and Off-target Control analyses.

## Data and controls

- Chen vMB scRNA-seq: 61,455 cells for broad L1 states.
- Chen RG/Nb scRNA-seq: 11,366 cells for seven priority L2 states.
- Development OOD: cortical organoid, neural crest, motor-neuron and mesenchymal datasets.
- Behavior-only time course: GSE204796, used to check whether outputs behave consistently across real differentiation days.
- Locked external-source and OOD datasets remain unopened.
- snRNA-seq remains a cross-modality shadow analysis.

## Current biological findings

| Question | Finding | Consequence |
|---|---|---|
| Broad fetal VM identity | CellTypist and scANVI recover many L1 states in donor-held-out Chen data | Broad composition can be explored, but labels are not released |
| Fine RG/Nb identity | scANVI separates the seven L2 states better than the transparent baselines, but it is transductive and lacks external OOD validation | L2 states remain provisional and cannot support formal regional claims |
| Off-axis rejection | Tested inductive methods force the four OOD datasets into known fetal VM labels | A confident label cannot yet be interpreted as true product identity |
| Marker support | Negative markers are missing for `Neuron_ChAT` and `Neuron_OMTN`; `Neuron_Glut_GABA` and all seven L2 states lack complete reviewed cards | Marker evidence cannot yet provide an independent biological check |
| Uncertainty calibration | scConform reaches 90.2% coverage for L1 but 83.3% for L2 against a nominal 90% target | L2 abstention is not calibrated sufficiently |

No method or state is frozen. The pilot does not yet support formal target-cell,
regional-fidelity or off-target composition conclusions.

## Biological work before release

- Review 18 L1 and seven priority L2 state definitions, parent-child relations,
  developmental context, positive markers, negative markers and likely confounders.
- Keep 328 historical label conflicts excluded, including 25 RG-to-Pericyte records.
- Confirm the product definition and state-role mapping before translating a cell
  state into target, adjacent or off-target product roles.
- Set per-state acceptance and abstention rules before opening locked data.
- Run the fixed rules on the La Manno source-family holdout and locked OOD families.

P0-03 starts only after the biological definitions, marker cards and locked-test
rules are approved. Failure at that point leaves the affected state as `shadow` or
`unavailable`.

## Scientific boundaries

- The pilot evaluates analytical reliability and rejection behavior, not product
  efficacy, safety, potency, GMP release or absolute quality.
- Differentiation day is not converted into fetal age.
- Cells are not treated as biological replicates.
- No locked or sealed competitor data may influence state definitions, markers or thresholds.

## Engineering record

- Local Python 3.12: 171 tests passed.
- Server Python 3.12: 171 tests passed.
- Pilot run: `CELLSTATE-PILOT-e45ada3778e2`.
- Evidence run: `CELLSTATE-EVIDENCE-3268ddfd0caf`.
- Repeated summaries were content-stable.
- Runtime remains fail-closed without approved review, gate and release records.
