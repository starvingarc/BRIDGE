<div align="center">

<h1>BRIDGE</h1>

<p><strong>Development-aware transcriptomic evidence for cell-therapy products</strong></p>

<p>Twelve composable tools that turn uploaded single-cell data, reviewed biological<br>
authorities and precomputed measurements into traceable evidence.</p>

<p>
  <a href="https://github.com/starvingarc/BRIDGE/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/starvingarc/BRIDGE/actions/workflows/ci.yml/badge.svg"></a>
  <img alt="Python 3.12" src="https://img.shields.io/badge/Python-3.12-3776AB">
  <img alt="12 Tool Packages" src="https://img.shields.io/badge/Tool_Packages-12-6D5A9E">
  <img alt="Research preview" src="https://img.shields.io/badge/Status-research_preview-B65D3D">
  <a href="LICENSE"><img alt="MIT License" src="https://img.shields.io/badge/License-MIT-2E7B70.svg"></a>
</p>

<p>
  <a href="docs/README.md">Documentation</a> ·
  <a href="docs/tool-packages.md">Tool Packages</a> ·
  <a href="examples/README.md">Examples</a> ·
  <a href="CONTRIBUTING.md">Contributing</a>
</p>

</div>

> [!IMPORTANT]
> **Research preview.** All 12 P0 packages are implemented and callable, but
> their scientific use remains `candidate` or `shadow`. BRIDGE has no frozen
> state, method or `ScoreContract`; every domain score remains `null`. It does
> not make clinical efficacy, safety, potency or GMP-release claims.

![BRIDGE connects developmental references and a pre-transplant cell product to five evidence domains and traceable outputs.](docs/assets/bridge-biological-workflow.svg)

## Why BRIDGE

Evaluating a cell-therapy product is not one classification task. The uploaded
data, developmental reference, product definition, measurement choices,
uncertainty and final claims must remain connected. BRIDGE packages that chain
into explicit, checksummed interfaces that can be reviewed and rerun.

| Inspect | Evaluate | Govern |
|---|---|---|
| Audit uploaded expression data and assemble source-aware cell-state evidence. | Summarize target, regional, developmental, composition, proliferation/stress, comparison and optional graft evidence. | Gate sufficiency, compile evidence graphs, verify claims and build a local public-safe export. |
| [P0-01–P0-02](docs/tool-packages.md#intake-and-state-evidence) | [P0-03–P0-06](docs/tool-packages.md#product-domain-evidence) · [P0-07/P0-12](docs/tool-packages.md#comparison-and-graft-context) | [P0-08–P0-11](docs/tool-packages.md#evidence-governance-and-export) |

Parkinson's disease hPSC-derived midbrain dopaminergic products are the first
biological use case. The evidence contract is intended to extend to other
cell-therapy products without embedding one lab's state map or thresholds in
the runtime.

## Quick start

BRIDGE requires Python 3.12.

```bash
git clone https://github.com/starvingarc/BRIDGE.git
cd BRIDGE
python -m pip install -e ".[qc,evidence]"

bridge-tool list
bridge-tool describe P0-02
bridge-tool validate --request /absolute/path/to/request.json
bridge-tool run --request /absolute/path/to/request.json
```

The CLI and Python SDK use the same versioned contracts. Start with the
[committed requests](examples/README.md), or use the
[fully synthetic scRNA upload fixture](examples/demo-data/scrna-upload-v0.1/)
to test file ingestion. Example paths and checksums are placeholders unless an
example explicitly states otherwise.

## The 12 Tool Packages

| Stage | Packages | Result |
|---|---|---|
| Intake and state evidence | **P0-01** Input Audit & QC · **P0-02** Cell-State Evidence | Audited expression views and source-aware state evidence |
| Product-domain evidence | **P0-03** Target/Regional · **P0-04** Development · **P0-05** Off-target · **P0-06** Proliferation/Stress | Descriptive, externally configured domain evidence |
| Product context | **P0-07** Comparison & Stability · **P0-12** Optional Graft Assessment | Comparable-case summaries and an independent graft branch |
| Evidence governance | **P0-08** Sufficiency · **P0-09** Compiler · **P0-10** Claim Verifier · **P0-11** Public-safe Export | Gate traces, evidence graphs, verification receipts and local export |

Every package has a concise module README, authoritative Tool Card, public JSON
Schema, request example, scientific task card and version-bound validation
record. Browse all of them in the [Tool Package guide](docs/tool-packages.md).

## Scientific scope

| Evidence domain | What BRIDGE asks | What it does not claim |
|---|---|---|
| Target identity | Are intended lineage and states represented? | Released identity or potency |
| Regional fidelity | Is there transcriptomic regional support? | Spatial localization |
| Developmental compatibility | Is evidence compatible with a supplied window? | Biological age |
| Off-target control | How is the whole product composition accounted for? | Physical removal, safety or release control |
| Proliferation & Stress Response | Which stage-conditioned signals require review? | Cell fitness, causality or safety |

BRIDGE keeps externally versioned biology outside the executors, distinguishes
`missing`, `unknown`, `unavailable`, `negative` and `alert`, and never fills
missing evidence with zero. Each result preserves applicable source, method,
artifact and checksum provenance.

<details>
<summary><strong>Current P0-02 scientific status</strong></summary>

The first pilot used donor-aware splits from a controlled, unpublished fetal
ventral-midbrain reference. Broad states were recoverable with uneven
label-level performance, while seven fine RG/Nb-derived states remained
incompletely supported. Tested inductive methods also forced several
out-of-reference / out-of-distribution controls into known labels rather than
reliably abstaining.

Marker/program evidence is complementary rather than independent because its
curation lineage overlaps the internal annotation. Pseudobulk correlation is a
reference-similarity summary, not replicate-aware differential-expression
inference. These observations support exploratory composition only.

See the [pilot record](docs/validation/p0_02_scientific_freeze_pilot_20260811.md),
[data/reference registry](docs/bridge_spec_v0.1/data_reference_registry.md) and
[active scientific plan](plans/p0-02-cell-state-scientific-freeze.md).

</details>

## Documentation

| I want to… | Start here |
|---|---|
| Understand the product and biological model | [Product and scientific principles](docs/product-principles.md) · [P0 scientific specifications](docs/bridge_spec_v0.1/README.md) |
| Call a tool or connect an Agent | [Tool Package guide](docs/tool-packages.md) · [Agent integration](docs/agent-integration.md) · [request examples](examples/README.md) |
| Inspect an interface or tested behavior | [Tool Cards](src/bridge/tool_packages/cards/) · [public JSON Schemas](src/bridge/resources/schemas/) · [validation index](docs/validation/README.md) |
| Contribute or review provenance | [Contributing](CONTRIBUTING.md) · [quality baseline](docs/quality-baseline.md) · [privacy and provenance](docs/privacy-and-provenance.md) |

The [documentation home](docs/README.md) explains which source is authoritative
for runtime behavior, scientific intent, validation evidence and active plans.

<details>
<summary><strong>Selected foundations and citation guidance</strong></summary>

- Human fetal midbrain and hPSC-mDA context: [La Manno et al., *Cell* 2016](https://doi.org/10.1016/j.cell.2016.09.027) and [Xu et al., *JCI* 2022](https://doi.org/10.1172/JCI156768).
- Single-cell representation and QC: [Wolf et al., *Genome Biology* 2018](https://doi.org/10.1186/s13059-017-1382-0) and [Wolock et al., *Cell Systems* 2019](https://doi.org/10.1016/j.cels.2018.11.005).
- Cross-dataset annotation benchmarking: [Abdelaal et al., *Genome Biology* 2019](https://doi.org/10.1186/s13059-019-1795-z).
- Experimental-unit and replicate safeguards: [Zimmerman et al., *Nature Communications* 2021](https://doi.org/10.1038/s41467-021-21038-1) and [Squair et al., *Nature Communications* 2021](https://doi.org/10.1038/s41467-021-25960-2).

These sources motivate the use case and safeguards; they do not validate
BRIDGE's internal reference, thresholds or product conclusions. Until a software
DOI is issued, cite the exact BRIDGE commit and Tool Package version together
with the underlying method and data papers.

</details>

BRIDGE is available under the [MIT License](LICENSE).
