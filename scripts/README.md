# Maintenance Scripts

These scripts rebuild checked-in resources and enforce repository policy. They are developer entry points, not bioinformatics Tool Packages and not Agent-callable runtime tools.

| Script | Purpose |
|---|---|
| `prepare_quick_atlas_reference.py` | Freeze private sc/sn reference counts, annotations and existing tree row bindings; see [quick mapping](../docs/quick-atlas-mapping.md) |
| `build_knowledge_catalog.py` | Build the packaged knowledge snapshot and catalog-backed method shortlist |
| `verify_knowledge_sources.py` | Audit registered public sources |
| `export_schemas.py` | Generate packaged JSON Schemas; `--check` compares bytes, registrations and pinned historical snapshots without writing |
| `render_tool_cards.py` | Generate or validate the 12 Tool Cards |
| `check_research_skills_model.py` | Run opt-in live-model acceptance with synthetic questions and isolated tool execution; calls may incur provider usage |
| `check_repository.py` | Check layout, privacy, links and documentation contracts; check runtime package contracts when scientific dependencies are available |
| `check_documentation.py` | Read-only, standard-library checks of current versions, primary result schemas, input coverage, indexes, anchors and explicit numeric assertions |


Use the project's **Python 3.12** interpreter for repository and documentation checks,
including `--static` and `-S` invocations. They need no scientific dependencies;
that does not mean they support older system Python versions. Check `python --version`
before running them.

The application launch entry is `bridge-web` (`python -m bridge.web`); the root
[`start.sh`](../start.sh) delegates to it. See [Web startup and instance control](../docs/web-preview.md#start-a-private-instance)
for configuration, isolated acceptance and `status` / `stop`.

For schema maintenance, install `scripts/requirements-schemas.txt` and run
`PYTHONPATH=src python scripts/export_schemas.py --check`. Regenerate with
`PYTHONPATH=src python scripts/export_schemas.py` after an intentional Python
contract change; review the diff and rerun the check. The schema directory and
historical exceptions are described in [Development](../docs/DEVELOPMENT.md#schema-维护).

The [documentation assertion map](documentation_assertions.json) binds named
document captures to source declarations. See [Development](../docs/DEVELOPMENT.md#文档一致性)
for coverage, authoring conventions and adding assertions.
