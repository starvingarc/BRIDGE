# BRIDGE Documentation

BRIDGE documentation separates current executable contracts, scientific design,
validation evidence and temporary plans. A future capability in the PRD or a task
card is not current behavior merely because it is documented.

## Choose a path

| Reader | Start here | Then use |
|---|---|---|
| Researcher or scientific reviewer | [Product and scientific principles](product-principles.md) | [P0 scientific specifications](bridge_spec_v0.1/README.md), [data/reference registry](bridge_spec_v0.1/data_reference_registry.md), [tool guide](tool-packages.md) |
| Tool or Agent integrator | [Tool Package guide](tool-packages.md) | [Agent integration](agent-integration.md), [high-level tool contract](tool-contract.md), [public Schemas](../src/bridge/resources/schemas/), [request examples](../examples/README.md) |
| Contributor | [Contributing guide](../CONTRIBUTING.md) | [repository handbook](../AGENTS.md), [quality baseline](quality-baseline.md), [documentation guide](documentation-guide.md) |
| Evidence or privacy auditor | [Validation index](validation/README.md) | [Privacy and provenance](privacy-and-provenance.md), [method/source knowledge](../knowledge/README.md), [environment contracts](../environments/README.md) |

## Product and runtime contracts

- [Product requirements](BRIDGE_PRD.md)
- [Product and scientific principles](product-principles.md)
- [12 Tool Packages: purpose, inputs, outputs and boundaries](tool-packages.md)
- [High-level tool contract](tool-contract.md)
- [Agent team integration](agent-integration.md)
- [Privacy and provenance](privacy-and-provenance.md)
- [Quality baseline](quality-baseline.md)
- [Public JSON Schemas](../src/bridge/resources/schemas/)
- [Tool Cards](../src/bridge/tool_packages/cards/)

## Scientific specifications and knowledge

- [P0 specification index](bridge_spec_v0.1/README.md)
- [Data and reference registry](bridge_spec_v0.1/data_reference_registry.md)
- [P0-02 external-source preparation](bridge_spec_v0.1/external_source_preparation.md)
- [Catalog-backed method shortlist](../knowledge/active-methods.md)
- [Method and source knowledge](../knowledge/README.md)

## Governance and evidence

- [Validation records](validation/README.md)
- [Documentation guide](documentation-guide.md)
- [Decision log](decision-log.md)
- [Repository handbook](../AGENTS.md)
- [Active plans](../plans/README.md)
- [Security reporting](../SECURITY.md)

All 12 P0 packages are currently implemented engineering candidates. That does
not freeze a scientific method, cell state, threshold or score. Tool Cards,
Schemas, runtime output and exact validation records take precedence over summary
pages when determining current behavior.
