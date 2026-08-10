# BRIDGE v2

BRIDGE v2 is a modular, evidence-aware toolkit for transcriptomic evaluation of cell-therapy products. PD hPSC-mDA is the first application scope being instantiated, while the public contracts are designed to support additional products later.

The active repository is being rebuilt around 12 high-level Tool Packages. P0-01 Input Audit & QC is the first executable package. The remaining packages expose versioned descriptions and eligibility contracts until their methods pass benchmark and freeze gates.

## Current Boundary

- Research-use transcriptomic evidence only.
- No clinical efficacy, safety, validated potency, GMP release, or absolute product ranking.
- No P0 domain score is currently frozen; raw metrics and evidence states remain primary.
- Agent systems call BRIDGE's high-level Python/JSON interface, not individual bioinformatics commands.

## Entry Points

- Governance: [AGENTS.md](AGENTS.md)
- Documentation: [docs/index.md](docs/index.md)
- Active plan: [PLANS.md](PLANS.md)
- Product requirements: [docs/BRIDGE_v2_PRD.md](docs/BRIDGE_v2_PRD.md)
- Tool Packages: [tool_packages/](tool_packages/)
- Method and source knowledge: [knowledge/README.md](knowledge/README.md)
- JSON Schemas: [schemas/](schemas/)
- Conda contracts: [environments/README.md](environments/README.md)
- Request examples: [examples/README.md](examples/README.md)

```bash
python -m pip install -e ".[test,qc]"
bridge-tool list
bridge-tool describe P0-01
bridge-tool knowledge search "ambient RNA" --module P0-01
```

`bridge-tool validate --request <request.json>` checks schema and eligibility without executing analysis. `bridge-tool run --request <request.json>` executes only implemented packages; P0-02 through P0-12 currently return `not_implemented` and never synthesize measurements.

Historical Step1-Step3 code is retained under `legacy/` for provenance and is not part of the installed package.
