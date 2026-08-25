# BRIDGE Documentation

Use this page to find the shortest path to the contract, scientific rationale or
evidence you need.

> [!NOTE]
> **Product and current stage:** BRIDGE's final product is a scientific
> evaluation Agent. The current `main` branch provides its deterministic P0 tool
> layer: all 12 packages are executable engineering candidates. The end-to-end
> Agent/Web experience is not yet integrated. No scientific method, state,
> threshold or score is frozen, and a target capability in the PRD or a task
> card is not current runtime behavior.

## Find what you need

| I want to… | Start | Continue with |
|---|---|---|
| Understand the Agent product | [Product requirements](BRIDGE_PRD.md) | [Agent architecture and team boundary](agent-integration.md) · [product principles](product-principles.md) |
| Run or integrate the current tool layer | [12 P0 Tool Packages](tool-packages.md) | [Request examples](../examples/README.md) · [high-level contract](tool-contract.md) |
| Review the biology | [Product and scientific principles](product-principles.md) | [P0 specifications](bridge_spec_v0.1/README.md) · [data/reference registry](bridge_spec_v0.1/data_reference_registry.md) |
| Verify an exact interface | [Tool Cards](../src/bridge/tool_packages/cards/) | [Public JSON Schemas](../src/bridge/resources/schemas/) · [high-level contract](tool-contract.md) |
| Check what was tested | [Validation records](validation/README.md) | [Quality baseline](quality-baseline.md) · [method/source knowledge](../knowledge/README.md) |
| Contribute safely | [Contributing guide](../CONTRIBUTING.md) | [Repository handbook](../AGENTS.md) · [documentation guide](documentation-guide.md) |

## What is authoritative?

| Question | Source of truth |
|---|---|
| What does an installed tool accept and return? | Public JSON Schema and package spec |
| How should a person call and interpret it? | Tool Card |
| Why does the biological assessment exist? | Scientific task card and data/reference registry |
| What passed for a specific version? | Exact validation record |
| What work is still proposed? | Active plan; never treated as implemented behavior |

If two layers disagree, stop at the most concrete versioned contract and resolve
the documentation drift. Do not infer current behavior from an overview page.

## Browse by topic

### Product architecture

- [Product requirements](BRIDGE_PRD.md)
- [Product and scientific principles](product-principles.md)
- [Agent team integration](agent-integration.md)
- [Privacy and provenance](privacy-and-provenance.md)

### Current P0 tool layer

- [12 P0 Tool Packages](tool-packages.md)
- [High-level tool contract](tool-contract.md)
- [Request examples](../examples/README.md)

### Science and methods

- [P0 scientific specification index](bridge_spec_v0.1/README.md)
- [Data and reference registry](bridge_spec_v0.1/data_reference_registry.md)
- [P0-02 external-source preparation](bridge_spec_v0.1/external_source_preparation.md)
- [Catalog-backed method shortlist](../knowledge/active-methods.md)
- [Method and source knowledge](../knowledge/README.md)

### Verification and governance

- [Validation records](validation/README.md)
- [Quality baseline](quality-baseline.md)
- [Decision log](decision-log.md)
- [Documentation guide](documentation-guide.md)
- [Active plans](../plans/README.md)
- [Security reporting](../SECURITY.md)

Tool Cards, Schemas, runtime output and exact validation records take precedence
over summary pages when determining current behavior.
