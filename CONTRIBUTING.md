# Contributing to BRIDGE

BRIDGE accepts focused changes that preserve traceable evidence and honest
scientific status. Read the [Agent handbook](AGENTS.md),
[documentation home](docs/README.md) and [active plans](plans/README.md) before
starting work.

## Development setup

Use Python 3.12 and install the repository with the extras required by the change:

```bash
python -m pip install -e ".[qc,test,freeze,evidence]"
```

Create a topic branch from the latest `main`. Branch names must describe the work
and must not use a `codex/` prefix. A module implementation belongs in one
module-specific Pull Request; shared contracts should be changed separately and
only when at least two real callers require them.

## Documentation and generated files

- Every P0 package must retain a package landing page, Tool Card, scientific task
  card, request example and validation record.
- The Tool Card is the detailed human runtime contract; avoid copying its full
  field and reason-code tables into another document.
- Update stable documentation when current behavior, a Schema, privacy behavior
  or a scientific boundary changes. Put temporary implementation state in a plan.
- Do not hand-edit generated Schemas, Tool Cards or knowledge projections without
  updating and rerunning their maintained source generator.

## Required checks

Run the full repository gates in an isolated Python 3.12 environment:

```bash
python -m pytest -q
python -m bridge.toolkit.cli list --json
python -m bridge.toolkit.cli knowledge validate
python scripts/check_repository.py
git diff --check
```

Add focused tests for changed behavior and verify the built wheel when an
installed interface changes. A passing test suite is engineering evidence, not
scientific validation.

## Data and claims

- Repository contributions consist of code, schemas, documentation and minimal
  fixtures that are synthetic, de-identified, public or explicitly authorized.
  Each fixture states its source class and checksum.
- Keep `missing`, `unknown`, `unavailable`, `negative` and `alert` distinct.
- Do not add clinical efficacy, safety, potency, GMP-release, absolute ranking or
  score claims without a separately versioned and validated authority.

Pull Requests follow the repository template and must report the biological
question, data/control boundary, actual findings, unsupported conclusions,
interface changes and reproducible engineering evidence.
