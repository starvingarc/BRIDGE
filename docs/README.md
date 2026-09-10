# BRIDGE Documentation

Use this page as an index. The [BRIDGE PRD](BRIDGE_PRD.md), especially
[section 6](BRIDGE_PRD.md#6-agent-功能需求), is the single product-workflow
contract; overview pages link to it rather than restating it.

> [!NOTE]
> The private Web preview has accepted the first six intake-to-QC steps only
> within their stated scope. Twelve deterministic packages are callable, but
> downstream graph-driven coordination, internal comparator selection and
> qualified report/export remain approved targets. All active domains keep
> domain_score=null and candidate/shadow or unavailable states. See
> [validation](validation/README.md) for exact evidence and
> [Product Evidence Validation](../plans/product-evidence-validation.md) for
> unresolved scientific gates.

## Start here

| Question | Source |
|---|---|
| What should the Agent do for a researcher? | [Product requirements](BRIDGE_PRD.md#6-agent-功能需求) |
| What is implemented in the private interface? | [Web preview](web-preview.md) |
| Who owns questions, values and execution? | [Agent integration](agent-integration.md) |
| Which high-level tool answers my question? | [Question-led Tool Package index](tool-packages.md) |
| What does a tool accept and return? | [Canonical Tool Cards](../src/bridge/tool_packages/cards/) and [public Schemas](../src/bridge/resources/schemas/) |
| What passed for a particular revision? | [Validation records](validation/README.md) |
| What science remains unresolved? | [Active plans](../plans/README.md) |

## Scientific and governance references

- [Product and scientific principles](product-principles.md)
- [P0 scientific specifications](bridge_spec_v0.1/README.md)
- [Data and reference registry](bridge_spec_v0.1/data_reference_registry.md)
- [High-level tool contract](tool-contract.md)
- [Privacy and provenance](privacy-and-provenance.md)
- [Quality baseline](quality-baseline.md)
- [Decision log](decision-log.md)
- [Documentation guide](documentation-guide.md)
- [Approved protocol BPL design](superpowers/specs/2026-09-09-protocol-bpl-design.md)

## Authority and status

| Question | Authority |
|---|---|
| Installed input/output shape | Public Schema and package spec |
| Human runtime use and refusal behavior | Tool Card |
| Biological rationale and validation design | Scientific task card and data/reference registry |
| Evidence for an exact run or revision | Validation record and immutable runtime receipt |
| Proposed or unfinished work | Active plan, never current capability |

Runtime output, frozen Schemas and exact validation records take precedence over
summaries. A task card, candidate design, graph component, tool menu, passing
test or installed package does not by itself prove scientific validation or a
connected autonomous workflow.
