<div align="center">

<h1>BRIDGE</h1>

<p><em>Brain-Referenced In vivo-to-in vitro Developmental Guidance and Evaluation</em></p>
<p><strong>Scientific agent for cell-therapy product evaluation</strong></p>

<p>
  <a href="https://github.com/starvingarc/BRIDGE/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/starvingarc/BRIDGE/actions/workflows/ci.yml/badge.svg"></a>
  <img alt="Python 3.12" src="https://img.shields.io/badge/Python-3.12-3776AB">
  <a href="LICENSE"><img alt="MIT License" src="https://img.shields.io/badge/License-MIT-2E7B70.svg"></a>
</p>

</div>

BRIDGE coordinates source-aware intake, deterministic analysis tools, evidence
reconciliation and reviewable reporting for single-cell evaluation of
cell-therapy products. PD hPSC-derived midbrain dopaminergic products are the
first use case.

## Current status

- Twelve P0 Tool Packages are implemented and callable as engineering
  candidates. Their methods and outputs remain candidate/shadow;
  domain_score=null and no P0 ScoreContract is frozen.
- The private Web preview has accepted the first six intake-to-QC steps within
  their stated scope: research question, materials, necessary questions,
  source-backed fact confirmation, scoped plan and QC. Protocol formalization is
  a reviewable representation, not an experiment record.
- The downstream graph-driven research loop, internal comparator selection and
  qualified report/export are approved target behavior, not current end-to-end
  capability. Existing missingness compilation and blocked internal reports do
  not satisfy those gates.

The canonical current/target workflow is [PRD section 6](docs/BRIDGE_PRD.md#6-agent-功能需求).
Exact tested scope is recorded in [validation](docs/validation/README.md);
remaining scientific work is in [active plans](plans/README.md).

## Architecture

<img src="docs/assets/bridge-agent-architecture.svg" alt="BRIDGE Agent architecture: product data, product definition and sample metadata enter the Agent; the Agent performs intake, planning, tool orchestration and interpretation; versioned P0 tools and governed knowledge produce an evidence graph and reviewable outputs.">

The Agent coordinates questions, plans and interpretation. Registered high-level
tools own values, denominators, thresholds, statuses, versions and Evidence IDs.

## Quickstart

~~~bash
git clone https://github.com/starvingarc/BRIDGE.git
cd BRIDGE
python -m pip install -e ".[qc,evidence]"

bridge-tool list
bridge-tool describe P0-02
bridge-tool input-contract P0-02
bridge-tool validate --request /absolute/path/to/request.json
bridge-tool run --request /absolute/path/to/request.json
~~~

Start with the [question-led Tool Package index](docs/tool-packages.md) and
[synthetic examples](examples/README.md).

## Documentation

| Need | Entry point |
|---|---|
| Product behavior and approved workflow | [BRIDGE PRD](docs/BRIDGE_PRD.md) |
| Current private interface | [Web preview](docs/web-preview.md) |
| Agent/tool ownership | [Agent integration](docs/agent-integration.md) |
| Tool runtime contract | [Tool Cards](src/bridge/tool_packages/cards/) |
| Scientific design | [P0 specifications](docs/bridge_spec_v0.1/README.md) |
| Exact evidence | [Validation records](docs/validation/README.md) |
| Contribution rules | [Contributing](CONTRIBUTING.md) |

## Scientific boundary

BRIDGE provides research-use transcriptomic evidence. It does not currently
establish clinical efficacy, safety, validated potency, GMP release or an
absolute product ranking. Missing, unknown, unavailable, negative and alert
states remain distinct, and graft evidence never backfills pre-transplant
judgments.

BRIDGE is available under the [MIT License](LICENSE).
