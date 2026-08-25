# BRIDGE

[![CI](https://github.com/starvingarc/BRIDGE/actions/workflows/ci.yml/badge.svg)](https://github.com/starvingarc/BRIDGE/actions/workflows/ci.yml)
![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB)
[![License: MIT](https://img.shields.io/badge/License-MIT-2E7B70.svg)](LICENSE)

**Development-aware transcriptomic evidence for cell-therapy products.**

Parkinson's disease hPSC-derived midbrain dopaminergic (hPSC-mDA) products are
the first biological use case.

> **Current maturity:** all 12 P0 packages are implemented and callable.
> Scientific use remains `candidate` or `shadow`: no state, method or
> `ScoreContract` is frozen, every domain score remains `null`, and BRIDGE does
> not make clinical efficacy, safety, potency or GMP-release claims.

![BRIDGE connects human fetal references and a pre-transplant cell product to five evidence domains and traceable outputs.](docs/assets/bridge-biological-workflow.svg)

## Biological question

Given a pre-transplant cell product, which intended developmental and regional
identities are supported by its transcriptome, where does the full composition
diverge, and which uncertainties should be tested next?

| Evidence domain | Question and boundary |
|---|---|
| Target identity | Are the intended lineage and cell states represented? |
| Regional fidelity | Is there transcriptomic regional support, without claiming spatial localization? |
| Developmental compatibility | Does the product align with a user-supplied developmental window, without inferring biological age? |
| Off-target control | How is the whole product partitioned into target, adjacent, off-axis and unresolved states? “Control” means accounting, not physical removal, safety or release control. |
| Proliferation & Stress Response | Which stage-conditioned proliferation, stress-response, death-associated or residual pluripotency-like signals require review, without reassigning identity or declaring cell fitness? |

## Current biological evidence

The first P0-02 pilot used donor-aware splits from a **controlled, unpublished
Chen fetal-vMB reference**. Broad states were recoverable with uneven label-level
performance, while seven fine RG/Nb-derived states remained incompletely
supported. Tested inductive methods also forced cortical, motor-neuron,
neural-crest and mesenchymal **out-of-reference / out-of-distribution (OOD)**
controls into known fetal-vMB labels rather than reliably abstaining.

Marker/program evidence is a complementary channel, not an independent source:
negative-marker coverage is incomplete and its cards share curation lineage with
the internal annotation. Pseudobulk reference correlation summarizes similarity
to reference labels; it is not replicate-aware differential-expression inference.

These observations support exploratory composition only. They do not release a
state or method, and formal target, regional-fidelity and off-target conclusions
remain unavailable. See the [pilot record](docs/validation/p0_02_scientific_freeze_pilot_20260811.md),
[data/reference registry](docs/bridge_spec_v0.1/data_reference_registry.md) and
[active scientific plan](plans/p0-02-cell-state-scientific-freeze.md).

## Tool chain

```text
P0-01 → P0-02 → P0-03 / P0-04 / P0-05 / P0-06
                         ↓
                      P0-08 → P0-09 → P0-10 → P0-11

P0-07 compares multiple precomputed product-evidence bundles.
P0-12 is an optional, independent post-transplant graft branch.
```

| Stage | Packages | Engineering state | Scientific use |
|---|---|---|---|
| Intake and state evidence | [P0-01, P0-02](docs/tool-packages.md#intake-and-state-evidence) | Implemented | Candidate; P0-02 output remains shadow without a signed release manifest |
| Product-domain evidence | [P0-03–P0-06](docs/tool-packages.md#product-domain-evidence) | Implemented | Deterministic candidate/shadow summaries over externally versioned biology |
| Comparison and graft context | [P0-07, P0-12](docs/tool-packages.md#comparison-and-graft-context) | Implemented | Descriptive candidates; no winner, score or pre-transplant backfill |
| Evidence governance and export | [P0-08–P0-11](docs/tool-packages.md#evidence-governance-and-export) | Implemented | Candidate gates, graph, verification receipt and local public-safe JSON packaging |

`implemented` means the interface executes. `candidate` means scientific use is
not released. `shadow` evidence cannot enter a formal conclusion. `frozen`
requires version-bound scientific review and approval; no P0 score is frozen.

The [12-package guide](docs/tool-packages.md) gives every tool's role, inputs,
outputs, refusal behavior, example, scientific task card and validation record.

## Interface tour

BRIDGE requires Python 3.12.

```bash
python -m pip install -e ".[qc,evidence]"
bridge-tool list
bridge-tool describe P0-02
bridge-tool validate --request /absolute/path/to/request.json
bridge-tool run --request /absolute/path/to/request.json
```

The CLI and Python SDK share the same contracts. Committed
[request examples](examples/README.md) document all 12 tools, but their absolute
paths and checksums are placeholders unless an example explicitly says otherwise.
The synthetic H5AD is for upload and integration testing, not biological
validation.

Each run preserves the applicable measurement, reference, method, artifact and
checksum provenance. Missing, unknown, unavailable, negative and alert states are
not interchangeable, and missing evidence is never filled with zero.

## Start here

| Reader | First document |
|---|---|
| Researcher or reviewer | [Product and scientific principles](docs/product-principles.md) and [P0 scientific specifications](docs/bridge_spec_v0.1/README.md) |
| Tool or Agent integrator | [Tool Package guide](docs/tool-packages.md), [Agent integration](docs/agent-integration.md) and [public JSON Schemas](src/bridge/resources/schemas/) |
| Contributor | [Contributing guide](CONTRIBUTING.md), [repository handbook](AGENTS.md) and [quality baseline](docs/quality-baseline.md) |
| Evidence auditor | [Validation index](docs/validation/README.md), [privacy and provenance](docs/privacy-and-provenance.md) and [method/source knowledge](knowledge/README.md) |

## Repository layout

| Path | Purpose |
|---|---|
| `src/bridge/toolkit/` | Shared SDK, CLI, contracts, registry, runtime and knowledge search |
| `src/bridge/tool_packages/` | The 12 package implementations, specs, Tool Cards and package-owned resources |
| `src/bridge/resources/schemas/` | Packaged public JSON Schemas for Python and non-Python clients |
| `examples/` | Request shapes and a fully synthetic upload fixture |
| `docs/` | Stable product, scientific, integration and validation documentation |
| `knowledge/` | Curated method/source inputs and the catalog-backed method shortlist |
| `scripts/` | Repository maintenance and deterministic generation; not Agent tools |
| `tests/` | Executable behavior and scientific-boundary checks |

## Selected scientific foundations

These sources motivate the use case and analytical safeguards; they do **not**
validate BRIDGE's internal reference, thresholds or product conclusions.

- Human fetal midbrain and hPSC-mDA context: [La Manno et al., *Cell* 2016](https://doi.org/10.1016/j.cell.2016.09.027) and [Xu et al., *JCI* 2022](https://doi.org/10.1172/JCI156768).
- Single-cell representation and QC methods: [Wolf et al., *Genome Biology* 2018](https://doi.org/10.1186/s13059-017-1382-0) and [Wolock et al., *Cell Systems* 2019](https://doi.org/10.1016/j.cels.2018.11.005).
- Cross-dataset annotation benchmarking: [Abdelaal et al., *Genome Biology* 2019](https://doi.org/10.1186/s13059-019-1795-z).
- Experimental-unit and replicate boundaries: [Zimmerman et al., *Nature Communications* 2021](https://doi.org/10.1038/s41467-021-21038-1) and [Squair et al., *Nature Communications* 2021](https://doi.org/10.1038/s41467-021-25960-2).
- Provenance concepts: [W3C PROV-DM](https://www.w3.org/TR/prov-dm/); BRIDGE does not claim PROV conformance.

Until a preferred software citation or archival DOI is issued, cite the exact
BRIDGE commit and Tool Package version together with the underlying method and
data papers. Detailed source records live in the
[knowledge catalog](knowledge/README.md) and [data/reference registry](docs/bridge_spec_v0.1/data_reference_registry.md).

BRIDGE is available under the [MIT License](LICENSE).
