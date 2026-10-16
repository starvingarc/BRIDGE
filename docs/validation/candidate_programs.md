# Source-bound candidate program validation

## Scientific question and data

Can source-defined expression programs be described in an existing RNA view
without invented activation fractions, biological replicates or product scores?
P006 0.10.0 introduced the exact input DataView and MSigDB human Hallmark
2026.1.Hs resource path. P006 0.11.0 adds separate source-bound pluripotency and
dissociation/heat-shock candidate inputs. Source, license, membership counts and hash are recorded in the
[resource ledger](../../src/bridge/tool_packages/p0_06_proliferation_stress_response/resources/CANDIDATE_PROGRAM_LEDGER.md).
No new QC or cell-state annotation is performed. Matrix, private run identifiers
and exact sample measurements remain in the controlled acceptance record.

## Observed behavior and supported conclusion

The registered P006 run produced four program summaries with separate native
Scanpy and ULM measurements. Available gene subsets are explicitly labeled;
missing genes are listed, never filled with zeros or guessed aliases. Saved
per-observation tables support exact mean/median/quantile verification.
The normal P008 and P009 tools accept the source-bound technical-view spec and
measurements as exploratory evidence. Their admission is not scientific
qualification. Independent replicate count remains null and RNA evidence is
one dependent family. Original cell-cycle artifacts are read, not recomputed.

### Directed candidates

The registered `directed_programs` mode consumes an explicitly bound original
source CSV, not an invented marker list. The Hu pluripotency candidate uses
26 source members with membership weights, not fitted model weights. The
O'Flanagan dissociation candidate retains 512 source members, including five
negative-direction members and three unresolved source symbols. Its ULM result
uses signed observed members; Scanpy returns unavailable because its unsigned
score cannot represent this signature. These are separate outputs, not a
combined score. The restricted or license-unresolved source CSVs are not bundled.

Controlled registered-tool execution has produced both candidates. Exact
coverage and execution boundaries are maintained in the resource ledger. This
establishes descriptive execution, not residual-cell detection, a dissociation
cause, or applicability to a particular cell product. Web admission and real
model continuation must be assessed separately from those tool runs.

A separate controlled Web continuation on a public-data view produced numeric
pluripotency observations, but no estimable dissociation score: Scanpy was
inapplicable to the signed signature, and ULM was blocked by ambiguous gene
identifiers in that view. Those nulls cannot be replaced by successful results
from another input. The real model selected and executed the directed tool,
then failed action-structure validation on its next turn; a complete model
feedback loop is not established. Current integration acceptance is tracked in
the development follow-up.

The existing explicit approval path has admitted the two pluripotency
measurements through P008 and appended them to the saved graph, retaining its
previous records. Dissociation admission is still blocked: changing the saved
P008 selection is treated as an input correction and would invalidate the prior
selection's dependent receipts and graph. No such change was applied. Adding a
new source must be distinguished from correcting existing evidence before this
continuation can be accepted.

## Remaining questions

Matched positive/negative controls, independent preparations, perturbation and
preprocessing sensitivity, and intended-product validation are absent from this
acceptance. Resource coverage is not a sensitivity or specificity estimate.
Apoptosis-related expression is not cell-death fraction; quantiles are not
confidence intervals; native score scales cannot be averaged across methods or
interpreted as program strength rankings. A culture day does not establish a
developmental window. Pluripotency and dissociation candidates now have execution
evidence but still lack product-context validation. The Web result table exposes
method-specific values, signed member counts, coverage and unavailable reasons;
new exploratory-program distribution plots are not yet implemented.
Product-bound figures cannot substitute invented biological units.

## Verification evidence

- `tests/test_p0_06_candidate_programs.py`: registered input, complete/subset
  coverage, null refusal, resource tampering, explicit policy and exact artifacts.
- `tests/test_p0_06_exploratory.py`: unchanged cycle contracts and native behavior.
- `tests/test_registry.py`: current registration and historical compatibility.
- Controlled SDK acceptance: P006 receipt to checksummed MeasurementResultV2 /
  MeasurementSpecV3 artifacts to P008 receipt to P009 graph and native table
  reconciliation. No matrix rescoring is needed for graph verification.

The earlier 35-test combined run and final targeted checks are non-additive.
Installation, test success, real execution and biological validation are
separate proof layers. Full-repository tests and product qualification are not
claimed. Runtime contract: [P006 Tool Card](../../src/bridge/tool_packages/cards/P0-06.md).
