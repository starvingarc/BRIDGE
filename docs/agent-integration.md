# Agent Integration

> [!NOTE]
> The [PRD workflow](BRIDGE_PRD.md#6-agent-功能需求) is the single product
> contract. This page defines Agent/tool ownership and the existing integration
> seam. The private Web preview has accepted steps 1–6 within their stated
> scope; the downstream graph-driven loop, internal comparator selection and
> qualified export remain approved targets.

## Ownership

The LLM coordinates research questions, necessary clarification, plans, graph
queries, competing hypotheses and interpretation. Registered high-level tools
own values, denominators, thresholds, states, versions and Evidence IDs. The Web
owns authenticated display, exact confirmation and approval; it does not
recalculate scientific results.

Current bounded intake can draft source-backed product-definition and role
candidates for explicit review. Confirmation materializes candidate objects; it
does not make them reviewed/frozen science, create biological-unit attestation
or approve execution. The current missingness-only graph and blocked internal
report are partial paths, not the target autonomous feedback loop.

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

## Target coordinator loop

The graph-driven hypothesis/update loop and its approval boundaries are defined
once in [PRD sections 6.1–6.8](BRIDGE_PRD.md#61-agent-总体工作流). A valid
profile, tool menu or graph component alone does not establish that loop.

## Scientific boundary

Profiles and successful runs are engineering connectivity evidence. Methods and
outputs retain candidate/shadow or unavailable states, domain_score=null, until
their independent scientific contracts and release gates pass. See the
[question-led package index](tool-packages.md), [Web preview](web-preview.md) and
[validation records](validation/README.md).
