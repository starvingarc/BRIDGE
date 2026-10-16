# Agent Integration

> [!NOTE]
> The [PRD workflow](BRIDGE_PRD.md#6-agent-功能需求) is the single product
> contract. This page defines Agent/tool ownership and the existing integration
> seam. The private Web preview has accepted steps 1–6 within their stated
> scope. The source now connects bounded scope-driven graph/tool coordination;
> real-case acceptance, applicable scientific reviews, internal comparator
> selection and qualified export remain separate gates.

## Ownership

The LLM coordinates research questions, necessary clarification, plans, graph
queries, competing hypotheses and interpretation. Registered high-level tools
own values, denominators, thresholds, states, versions and Evidence IDs. The Web
owns authenticated display, exact confirmation and approval; it does not
recalculate scientific results.

Current bounded intake can draft source-backed product-definition and role
candidates for explicit review. Confirmation materializes candidate objects; it
does not make them reviewed/frozen science, create biological-unit attestation
or approve execution. Missingness-only graphs and blocked internal reports remain partial paths;
measured coordination requires source-bound inputs and explicit scientific
family/claim/requirement bindings.

## Research workflows

[Eight packaged Skills](research-skills.md) guide task selection, clarification,
evidence reasoning and stopping. Ordinary conversation reads one matching workflow;
approved assessment composes relevant guidance within one existing model request.
The provider validates the resulting Action, while the Registry and Web retain
eligibility, evidence admission and execution authority.

Product assessment still has five domains, including proliferation and stress
response. Expression exploration supplies shared evidence; comparison and graft
follow-up retain separate contracts. Skill routing does not redefine these domains
or qualify a scientific interpretation.

## Integration profile

AgentIntegrationProfile is a public, machine-readable dependency graph for one
tool path. It is checked against the installed ToolRegistry and
ToolInputContract so package version, request envelope, mode, role, Schema and
cardinality cannot silently drift.

- Python model: bridge.toolkit.AgentIntegrationProfile
- [Public Schema](../src/bridge/resources/schemas/agent_integration_profile.schema.json)
- Schema reference: bridge://schemas/agent-integration-profile/v0.1

A slot declares logical ownership and compatibility:

| Source | Meaning |
|---|---|
| user_upload | Data or structured facts supplied through the user workflow |
| system_resource | Versioned reference, method, rule or policy selected by the deployment |
| derived_output | Checksummed artifact from an earlier producer binding |
| agent_constructed | BRIDGE object built only from declared dependencies and confirmed facts |

For the canonical P0-08 evidence-sufficiency run-result artifact, profile
validation also checks the producer tool, its current result Schema and the
declared result version. Historical result versions remain readable by their
consumers but cannot describe a new output from the current producer. Other
derived slots may describe sub-artifacts rather than the complete ToolRun result;
they are not assumed to share the producer's top-level result Schema.

Profiles contain no runtime path, filename, checksum value, asset identifier,
host or credential. Runtime materialization uses the existing InputAsset and
StructuredInputRef contracts. A profile states what a caller must supply; it
does not prove that the Web can author every object or that the path has run on
qualified scientific inputs.

## Published profiles

| Profile | Registered path | Boundary |
|---|---|---|
| [Single product](../examples/agent-integration/profiles/single-product.json) | P0-01 → P0-02 → P0-03/P0-04/P0-05/P0-06 → P0-08 → P0-09 → P0-10 → P0-11 | Five assessment domains; local candidate export only |
| [Comparison](../examples/agent-integration/profiles/comparison.json) | Eligible product-evidence bundles → P0-07 | Descriptive; cohort and comparability must be confirmed |
| [Graft](../examples/agent-integration/profiles/graft.json) | P0-12 not_provided or expression_analysis | Independent post-transplant branch |

The single-product profile keeps target identity and regional fidelity as
separate P0-08 domain inputs. P0-01 emits selected-view and biological-unit
lineage artifacts; P0-02 emits aggregate and observation-level evidence.
P0-05 and P0-06 must consume the same checksummed attestation and reviewed role
definition where applicable. P0-09 record sets remain distinct from graph
manifests so reports bind the evidence actually read.

Comparison never modifies the query product's independent evidence. Graft
metadata are user-supplied and graft results never backfill pre-transplant
scoring, calibration or judgments.

## Validate and run one step

The reference runner validates already materialized requests; it does not
resolve catalogs, create scientific objects, call a model, fill missing fields
or alter evidence states.

~~~bash
python examples/agent-integration/reference_runner.py \
  validate-profile \
  --profile examples/agent-integration/profiles/single-product.json

python examples/agent-integration/reference_runner.py \
  run-step \
  --profile examples/agent-integration/profiles/single-product.json \
  --binding claim-verifier \
  --request <materialized-request.json>
~~~

For each step, the caller validates the profile binding, runs package
eligibility and then invokes the registered tool. Missing resources fail with a
named blocker. The ToolRun, result Schema, artifact manifest and checksum remain
the execution record.

## Scope-bound coordinator

The workflow remains defined in [PRD sections 6.1–6.8](BRIDGE_PRD.md#61-agent-总体工作流).
The Web coordinator now prepares a finite question/upload/mode/resource scope.
The same deterministic candidate entry reports actual blocking prerequisites
and separate interpretation gaps before approval, without scientific execution
or changing facts, selections, authorization or counters.

Within exact consent, a configured model may select only an opaque per-turn
option. The server reconstructs the normalized registered request, rechecks
eligibility and deduplication, and derives the exact-plan approval from the
original scope receipt. It records genuine tool outcomes, retrieves the graph,
and rebuilds the same-version portrait. The model cannot supply a ToolRequest,
upgrade a review, create a measurement or reset a limit. Each option describes an
unexecuted exact action whose current prerequisites have passed, using the packaged
registry name, summary and scientific status rather than implying an existing result.
Blocking reasons belong only to their exact tool/mode pair; interpretation gaps are
separate and do not suppress an otherwise eligible action. These descriptions grant
no additional authority, and an explanation may end the phase with options remaining
without establishing scientific completion.

Automatic scope modes use existing QC/cell-state and source-bound producer
seams, measured sufficiency, canonical initial/append and registered queries.
P0-06 resource modes and their private settings are documented together in the
[Web configuration guide](web-preview.md#start-a-private-instance).
For `P0-06/directed_programs`, deployment-configured `BRIDGE_P006_PLURI_RESOURCE_PATH`
and `BRIDGE_P006_DISSOC_RESOURCE_PATH` are verified against their reviewed source
hashes and the same QC view. A candidate binds one exact source; each new scope
shows its source gene set and resource hash before approval. That selected input
is part of the scope digest and cannot change during a multi-run scope. A terminal attempt,
including a partial or failed run, is not selected again automatically. Successful
source receipts remain separate by source gene set when subsequent sources are
added to the evidence graph; missing method values remain null.
When a saved sufficiency selection belongs to an earlier graph source, a new
scope freezes the pending native source separately from that saved selection.
Explicitly selecting this exact frozen addition preserves historical receipts
and still requires a new execution approval. Selecting a different replacement
remains an input correction with normal dependent-result invalidation.
For a subsequent source, approve sufficiency first, then propose a fresh graph
append scope against its completed receipt. Approving both steps together does
not authorize binding a future receipt or establish automatic dependency
continuation within that scope.
Legacy/manual modes remain manual selections; absent scientific requirements
never trigger conversion to an alternative policy. A measured claim binding
gap can coexist with an eligible check. Unchanged canonical graph inputs cannot
be appended as new evidence.

No whole-question completion contract is configured: a model proposal of
completion stops as `completion_contract_unavailable`, never scientific success.
Stopped and interrupted scopes retain evidence and used budgets; changed
facts/resources require a new scope. Repeated correction fencing does not replace
a terminal stop reason. Each resumed phase retains earlier stop events with the
then-used counters; resume never refunds budgets. The Web shows pending review
separately from historical bindings and never silently recomputes after a correction.
Explicit resume supplies only the immediately preceding allowlisted format,
explanation-length or evidence-citation rejection code to the model, never the
rejected response. Both provider protocols publish
the same per-action field constraints enforced on return: checks/queries require
an option, stops require a reason, questions require text, and explanations require
text or structured hypotheses. Fields belonging to another action must be absent
or null; hypotheses are reserved for explanations. JSON and native actions reuse
the same current-turn citation-role, option and discriminating-check choices in
their schemas. No parser repair changes an invalid action into an authorized one.

Hypothesis citations use current-turn aliases attached to
concrete canonical measurement or graph records. Top-level result aliases remain
containers, while other nested aliases remain joins rather than citations. A
measurement without a registered claim relation is an observation regardless of
whether its state is measured, inferred, negative or alert. Missing or unestimable
records are limitations. Support and opposition are assigned only by an eligible
record's registered relation to a concrete claim. A source-verified, effectively
active, applicable exploratory/shadow graph record that
has an available numeric value, it may be cited as an observation even without an
eligible reconciliation; this does not make it support or opposition. A truncated
query does not establish that unreturned reconciliations or conflicts are absent.
When a current-version observation
or explicit support record is available, an `explain` decision must carry at
least one structured hypothesis through that citation-checked contract. Free text
without structured hypotheses is rejected as an invalid provider action: it does
not append an empty successful interpretation or finish the phase. The model's
next explicit-resume context names `structured_hypotheses_required`, so it can
correct the structure or ask/stop without inventing evidence. Ordinary check,
query and stop turns do not create empty interpretation versions; each nonempty
version retains its exact scope, input revision and evidence-snapshot digest.

After a successful **in-scope** `P0-09/case_append_v2` updates the latest graph,
`P0-10` is withheld with `current_scope_explanation_required` until a current-scope,
current-snapshot structured explanation with role-valid record citations exists.
A prior-scope or pre-append explanation is history, not admission for the updated
graph. The report-context cache also includes current interpretation history, so
new explanations cannot silently reuse an older draft context. This gate does not
apply to an independent graph-snapshot report or the manual report-input path;
it never grants scientific qualification or public export eligibility. A later explicit
resume retains the original authorization, used budgets, receipts and stop history.
Without explicit report intent, a current cited explanation and eligible updated
P0-10 request still produce an advisory `workflow_handoff` for the next model
turn. It is derived from the successful append receipt, current evidence
snapshot and report candidate, and says whether an existing report predates the
explanation. The model still chooses the offered option; this legacy path does
not guarantee that the model will report.

A new scope can separately request `report_after_explanation=true`, with
P0-10/default among its allowed modes. This boolean is included in the approved
scope digest; absent fields in persisted older scopes remain false without
changing their original digest. The report candidate is not offered to the
model before this scope accepts a cited `explain` action. On explicit resume,
the coordinator checks that exact accepted action and current explanation
version, evidence snapshot, graph receipt, report context, authorization,
resources and remaining tool-run budget. It then admits the exact P0-10 request through
the existing scope-derived plan and executor, without another model selection.
The graph may be a valid pinned result from an earlier scope; no unchanged
measurement or graph append is rerun merely to trigger reporting. Completed
report execution ends the scope. A changed binding blocks the handoff; a report
already admitted but failed, interrupted or cancelled is not retried in that
scope. A new scope is required to reconsider execution. No separate pending
object or scientific approval is created.

A valid explanation can precede graph construction. If no available graph exists
and an unused, eligible P0-08/default or P0-09/case_initial_v2 option remains in
the original scope, explicit resume returns to the existing model-selection loop.
It does not execute a prerequisite automatically or expand authorization. The
private `report_preparation` context identifies the missing graph. After graph
execution changes the evidence snapshot, a fresh structured explanation is
required before the next explicit report handoff; the earlier version remains
unchanged history. Stale bindings, absent eligible prerequisites and exhausted
budgets still block rather than manufacturing a report.

Each assessment provider turn receives fresh opaque aliases for current concrete
records, with an explicit citation role. Native tool arguments separately
enumerate observation/explicit-support, opposition and missing aliases, with zero
items allowed when a role has no candidates. JSON mode sends the same exact
per-turn choices in its system context. Accepted versions replace those ephemeral
aliases with stable, versioned internal references of the form
`E-<receipt>#measurement:<record>@1` or `E-<receipt>#record:<record>@1`.
Each supported hypothesis binds its own observation/support, opposition and missing records
once. A missing-only item instead requires nonempty current missing citations, empty
support/opposition lists, and null expected observation and discriminating check.
It is rendered as an evidence-gap statement, with `competing_explanation` labelled
as its limitation, not a competing biological hypothesis. This is a Web action
contract change; the persisted report fields and public schema are unchanged.
Both report preparation and explicit report continuation require at least one
observation-backed item overall; gap statements may accompany but cannot replace it.
Missing-in-support citations remain invalid. Code renders numbered statements and their role-labelled stable references;
the model does not repeat citations in prose. For structured explanations,
`decision.text` is optional and discarded if supplied, so unrelated prose cannot
inherit the hypotheses' combined references. `statement`, `competing_explanation` and `expected_observation` remain
uncited proposed text; aliases embedded in those fields are rejected. Deterministic
checks validate action shape, current record roles, scope and citation binding, but
do not classify free prose as scientifically true. Accepted explanation messages carry
`qualification=proposed_explanation`, their stable `evidence_refs`, and an
`interpretation_ref` to the same version later consumed by report admission.
The user assessment projection labels each displayed hypothesis
`qualification=proposed_explanation` and supplies that version reference only
when the full hypothesis list, scope, input revision and content hash match the
latest stored interpretation version. Otherwise it supplies
`provenance_warning=legacy_unclassified`; it does not infer currentness from
input freshness or prose similarity. This is source classification, not
scientific validation.
Rejected prose is never retained. These deterministic checks enforce the current
contract; they are not a claim of general semantic verification.

The structured hypothesis field `discriminating_check` remains required but
accepts explicit `null`: the current scope has no suitable scientific
discriminating check. This records an unresolved test, not negative evidence,
tool authorization, or whole-question completion. Non-null P0 IDs remain
validated against the approved scope. The outbound JSON guidance and native
tool parameters now list exact current option IDs, eligible scientific-check
IDs and stop reasons as well as citation roles; sufficiency (P0-08), graph
operations (P0-09) and report verification (P0-10) are not offered as new
biological discriminators. Current cited explanations with `null` can still
reach the existing report gate after explicit continuation. The private
research-report v0.3 schema accepts both old non-null and new null values,
retains the original explanation content hashes, and does not rewrite earlier
reports. Web and new private HTML reports disclose when no suitable in-scope
check exists; neither makes the candidate interpretation scientifically
qualified.

If a hypothesis citation is rejected,
the private turn stores only a bounded error category and count, and explicit
resume may pass those safe diagnostics back; it stores neither rejected prose
nor the invalid alias. Neither handoff assesses the scientific quality of a
structurally valid explanation.
This rule does not require a hypothesis before any applicable evidence exists;
bounded missingness or limitation text in that state keeps its existing behavior.

## Researcher conversation handoff

The ordinary conversation path reuses its existing single provider call. Its
safe context now keeps the current question, confirmed input-state summary,
analyses already attempted, admitted result aliases, important limitations,
the concrete unresolved reason and user-correction state together. These are an
index over current server facts, not a second evidence store. A later correction
or result binding remains authoritative.

Method, workflow and clarification follow-ups remain natural provider text without
automatically prepending a model-provenance label. Provenance remains in the
`provider_admitted` source field; admission does not semantically verify the prose.
Conversation guidance applies both before and after workflow selection: answer the
current question directly, avoid repeating confirmed background or conclusions,
and expand when requested. Consequential uncertainty and failures remain explicit;
workflow checklists are not mandatory reply sections. Result facts take a different
path: the provider receives current `observation_choices`,
each containing one whole deterministic record, and selects only its opaque `O*`
alias. The server renders the record's method, metric, signed value, unit, state and
available version fields together and retains the exact `E0`/`E1` artifact binding
in the private turn audit. It never reconstructs a fact by matching words or a bag
of numbers in free prose. Free interpretation is shown separately as
`解释（未验证假设）`; selecting a correct observation does not qualify that text.
Legacy free-text `E0`/`E1` citations are rejected with `解释尚未通过核对`, and the raw
reply is not persisted. This is a structural provenance and expression-qualification
contract, not general semantic verification. No positive or negative keyword list
is used to decide whether prose is scientifically true. The assessment path uses
the same separation: deterministic observation/role binding plus explicitly
proposed hypothesis text, including valid `discriminating_check=null` behavior.

For stored assistant messages classified as `provider_admitted`, public display,
transcript export and subsequent model history remove only the old leading
`模型说明（未经结构化事实核验）：` label. Stored messages and their audit remain
unchanged; user text, embedded quotations and unclassified assistant text are preserved.

Every new public message has exactly one source: `user_input`,
`server_template`, `provider_admitted` or `deterministic_evidence`. Legacy user
turns can be identified from their stored role. Unclassified legacy assistant
text remains visible with a warning for historical continuity, but is not fed
back into the provider and is excluded from newly exported transcripts. This
prevents historical uncertainty from hiding the whole conversation or being
silently promoted into a new explanation.

The stable Web handoff is the session `presentation` object plus the existing
plan, assessment, artifact and message structures. `presentation` derives the
researcher stage, safe issue, actual result-preservation state and currently
authorized actions; it does not duplicate workflow state. Development operators
use the separately gated diagnostics projection for internal codes, counters and
step/run states. Visualization and report consumers should use deterministic
evidence/result objects and artifact bindings, not diagnostic fields or model
prose, as their numerical source.

The [Web guide](web-preview.md#cell-state-and-product-assessment) defines the
researcher controls. The [assessment privacy projection](privacy-and-provenance.md#assessment-purpose)
keeps provider aliases separate from exact browser-only receipt, artifact and
source dependencies. See [observed coordinator validation](validation/step7_evidence_coordinator_20260911.md)
the append/explanation gate record (controlled historical record; not distributed)
and the explicit report-intent handoff record (controlled historical record; not distributed)
for proof levels and remaining gates.

## Scientific boundary

The native candidate path uses the existing five-domain enumeration for P0-08
inputs. Genuine P0-02 target-identity and P0-06 exploratory process observations
retain their values, states and shared-source bindings; other domains receive
empty, same-case inputs rather than invented measurements. Candidate domain-level
requirements enter P0-09 alongside the measured records: `measurement_not_provided`
means no supplied native measurement; `measurement_unavailable` requires every
supplied measurement to explicitly have that state. Unknown/alert or unqualified
observations remain observations, with `required_channel_not_provided` recording
the unresolved independent-validation channel. No domain gains qualification.

Coverage-only changes can append requirements without duplicating measured
records. Unchanged coverage and measurements cannot trigger another append.
Prior requirements and receipts remain immutable; a later changed reason creates
a requirement revision. Reports cannot silently reuse an older graph that omits
the current coverage. These gaps do not expand the scope's allowed tool modes.
New scientific modes or resources still require a new proposal and approval.

This connects coverage, not all scientific measurements. The candidate profile
cannot become the structurally different V3 handoff by changing its version.
Reviewed role/window mappings and biological-unit inputs remain explicit gates.
The auxiliary P0-02 receipt already contains `consensus_supported_fraction`,
`source_conflict_fraction` and `marker_programs_assessed`, but those three native
V1 measurements do not yet have an approved domain/unit/context projection into
the graph's V2 measurement contract. The auxiliary artifact remains source-linked;
these values are not silently fabricated as V2 or counted as independent evidence.

Profiles and successful runs are engineering connectivity evidence. Methods and
outputs retain candidate/shadow or unavailable states, domain_score=null, until
their independent scientific contracts and release gates pass. See the
[question-led package index](tool-packages.md), [Web preview](web-preview.md) and
[validation records](validation/README.md).

The orchestration design considered per-claim verification in
[GeneAgent `88fd1adb`](https://github.com/ncbi-nlp/GeneAgent/blob/88fd1adb/main_cascade.py)
([NLM public-domain notice](https://github.com/ncbi-nlp/GeneAgent/blob/88fd1adb/LICENSE))
and execution/output/interpretation separation in
[CellVoyager `5a61f6b3`](https://github.com/zou-group/CellVoyager/blob/5a61f6b3/cellvoyager/execution/claude.py)
([MIT, Samuel Alber](https://github.com/zou-group/CellVoyager/blob/5a61f6b3/LICENSE)).
These are conceptual references only: no source, agent framework, arbitrary-code
execution or resume-by-rerunning mechanism is incorporated. BRIDGE retains its
registered-tool, authorization, versioning and unverified-science boundaries.
