# BRIDGE

**Development-aware transcriptomic evidence for cell-therapy products.**

Parkinson's disease hPSC-derived midbrain dopaminergic (hPSC-mDA) products are the first biological instance.

![BRIDGE connects human fetal references and a pre-transplant cell product to five evidence domains and traceable outputs.](docs/assets/bridge-biological-workflow.svg)

## Biological question

Given a pre-transplant cell product, which intended developmental and regional identities are supported by its transcriptome, where does the full composition diverge, and which uncertainties should be tested next?

## Five evidence domains

| Domain | Evidence question |
|---|---|
| Target identity | Are the intended lineage and cell states represented? |
| Regional fidelity | Does the product support the intended anatomical identity rather than an off-axis fate? |
| Developmental compatibility | How does the product align with a researcher-defined developmental window? |
| Off-target control | What target, adjacent, off-axis, and unresolved states make up the whole product? |
| Process integrity | Which proliferation, stress, and residual pluripotency-like transcriptomic signals require review? |

## Current implementation status

| Package | Status | Current output |
|---|---|---|
| P0-01 Input Audit & QC | Executable candidate | Input structure, matrix semantics, QC readiness, and traceable artifacts |
| P0-02 Cell-State Evidence | Executable shadow; unsealed pilot complete, biological review and locked test pending | Source-specific support, marker evidence, method benchmark outputs, abstention calibration, and source conflicts |
| P0-03 onward | Contracted | Scientific, input/output, environment, and validation contracts; executors pending |

Candidate and shadow outputs remain subject to benchmark, biological review, and version freeze.

## Minimal usage

```bash
python -m pip install -e ".[qc]"
bridge-tool list
bridge-tool describe P0-02
bridge-tool validate --request request.json
bridge-tool run --request request.json
```

Each run preserves the input and records the applicable measurement, reference, method, artifact, and checksum provenance.

## Scientific boundaries

- BRIDGE reports research-use transcriptomic evidence, uncertainty, and evidence gaps.
- Missing, unresolved, and out-of-reference evidence is not treated as a negative result.
- Candidate or shadow evidence does not establish clinical efficacy, safety, potency, GMP release, or an absolute product ranking.
- Post-transplant graft evidence is analyzed independently and is not back-propagated into the pre-transplant profile.
- No frozen P0 domain score is currently published.

## Documentation

- [Documentation index](docs/index.md)
- [Product requirements](docs/BRIDGE_PRD.md)
- [Scientific principles](docs/product-principles.md)
- [Tool Package cards](tool_packages/)
- [Method and source knowledge](knowledge/README.md)
- [Agent integration](docs/agent-integration.md)
