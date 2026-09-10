# Tool Package Guide

BRIDGE exposes twelve registered high-level P0 Tool Packages. This page routes
from a research question to the canonical Tool Card and the evidence that has
actually been recorded; it does not duplicate field tables, method contracts or
reason codes.

All packages are implemented engineering candidates. Scientific states remain
candidate/shadow or unavailable, domain_score=null, and no P0 ScoreContract is
frozen.

## How to use this index

1. Start from the research question below.
2. Read the Tool Card for exact inputs, outputs, modes and refusal behavior.
3. Check the linked validation record or executable contract test before making
   an implementation claim.
4. Treat scientific task cards as validation designs, not evidence that a method
   or product conclusion passed.

The shared CLI is:

~~~bash
bridge-tool describe P0-XX
bridge-tool input-contract P0-XX
bridge-tool validate --request <request.json>
bridge-tool run --request <request.json>
~~~

Public JSON Schemas and input-contract are machine-readable authorities. The
[high-level contract](tool-contract.md) explains shared states and lineage.

<a id="p0-01"></a>
## P0-01 — Can the declared input support downstream analysis?

Use [Input Audit & QC Tool Card](../src/bridge/tool_packages/cards/P0-01.md) and
the [request examples](../examples/requests/). Actual engineering evidence:
[server integration](validation/p0_01_server_integration_20260810.md). QC
readiness is not product quality, safety or release.

<a id="p0-02"></a>
## P0-02 — What cell states are supported, opposed or unresolved?

Use [Cell-State Evidence Tool Card](../src/bridge/tool_packages/cards/P0-02.md).
Actual evidence: [server integration and scientific-freeze pilot](validation/p0_02_cell_state_evidence.md).
Reference similarity and descriptive marker evidence do not force a released
assignment, purity estimate or product role.

<a id="p0-03"></a>
## P0-03 — Does target identity and regional evidence match the reviewed goal?

Use [Target Identity & Regional Fidelity Tool Card](../src/bridge/tool_packages/cards/P0-03.md).
Actual engineering evidence: [aggregation and expression-method validation](validation/p0_03_target_regional.md).
Target and regional axes stay separate and remain candidate/shadow.

<a id="p0-04"></a>
## P0-04 — Is the product compatible with the reviewed developmental window?

Use [Developmental Compatibility Tool Card](../src/bridge/tool_packages/cards/P0-04.md).
Actual evidence: [candidate validation](validation/p0_04_developmental_compatibility.md).
Similarity to supplied stages is not biological age or a continuous trajectory.

<a id="p0-05"></a>
## P0-05 — What is the whole-product and non-target composition?

Use [Off-target Control Tool Card](../src/bridge/tool_packages/cards/P0-05.md).
Actual evidence: [count, attestation and candidate records](validation/p0_05_off_target_control.md).
Unknown and unresolved observations remain in their declared denominator; a
count or absence of a flag is not safety evidence.

<a id="p0-06"></a>
## P0-06 — Which proliferation and stress programs are measured or unavailable?

Use [Proliferation & Stress Response Tool Card](../src/bridge/tool_packages/cards/P0-06.md).
Actual evidence: [source-bound, measurement and legacy records](validation/p0_06_proliferation_stress_response.md).
The required seven-family portrait and its acceptance boundary are defined once
in [PRD section 6.3](BRIDGE_PRD.md#63-分析计划与任务执行). S/G2M alone is
descriptive and cannot establish the whole assessment, proliferation rate,
safety or potency.

<a id="p0-07"></a>
## P0-07 — Are registered products eligible for a bounded comparison?

Use [Product Comparison & Stability Tool Card](../src/bridge/tool_packages/cards/P0-07.md).
Actual executable evidence is retained in the
[package tests](../tests/test_p0_07_product_comparison_stability.py).
Comparability and declared analysis units precede deltas; results are not an
absolute ranking.

<a id="p0-08"></a>
## P0-08 — Is each domain sufficiently evidenced for interpretation?

Use [Evidence Sufficiency Tool Card](../src/bridge/tool_packages/cards/P0-08.md).
Actual evidence: [case-binding validation](validation/p0_08_case_binding_v0.5.md).
A missing domain remains a requirement; the gate creates no measurement or
score.

<a id="p0-09"></a>
## P0-09 — How are evidence, conflicts and missing requirements connected?

Use [Evidence Compiler & Reconciler Tool Card](../src/bridge/tool_packages/cards/P0-09.md).
Actual evidence: [v0.2 sufficiency ingestion validation](validation/p0_09_sufficiency_v2_ingestion_v0.4.md).
Graph and evidence-family counts are audit structure, not independent votes.

<a id="p0-10"></a>
## P0-10 — Do report claims match their cited values and allowed wording?

Use [Claim Verifier Tool Card](../src/bridge/tool_packages/cards/P0-10.md).
Actual executable evidence is retained in the
[claim-verifier tests](../tests/test_p0_10_claim_verifier.py).
Verified correspondence is not biological truth or release approval.

<a id="p0-11"></a>
## P0-11 — Is a local candidate artifact eligible for public-safe handling?

Use [Public-safe Export Tool Card](../src/bridge/tool_packages/cards/P0-11.md).
Actual executable evidence is retained in the
[export tests](../tests/test_p0_11_public_safe_export.py).
Exported means a local candidate was built or audited; it does not publish,
share or authenticate approval.

<a id="p0-12"></a>
## P0-12 — Is linked post-transplant evidence available and eligible?

Use [Optional Graft Assessment Tool Card](../src/bridge/tool_packages/cards/P0-12.md).
Actual executable evidence is retained in the
[graft tests](../tests/test_p0_12_graft_assessment.py).
No-graft is an explicit absence path, and graft evidence never backfills
pre-transplant scoring, calibration or judgments.

## Shared boundaries

P0-03 through P0-06 form the current five-domain assessment because P0-03
contributes distinct target-identity and regional-fidelity domains. P0-07
comparison and P0-12 graft analysis are conditional branches. The five
knowledge-enhancement dimensions are not substitutes for the P0 acceptance gate.

Across packages, missing, unknown, unavailable, negative and alert remain
distinct. Reuse requires the same applicable measurement contract; changed
versions or definitions produce a new version rather than overwriting old
evidence. See the [validation index](validation/README.md) for dated records and
the [method shortlist](../knowledge/active-methods.md) for candidate sources.
