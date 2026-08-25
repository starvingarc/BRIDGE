# Maintenance Scripts

These scripts rebuild checked-in resources and enforce repository policy. They are developer entry points, not bioinformatics Tool Packages and not Agent-callable runtime tools.

| Script | Purpose |
|---|---|
| `build_knowledge_catalog.py` | Build the packaged knowledge snapshot and active-method shortlist |
| `verify_knowledge_sources.py` | Audit registered public sources |
| `export_schemas.py` | Generate packaged JSON Schemas from Python contracts |
| `render_tool_cards.py` | Generate or validate the 12 Tool Cards |
| `render_p0_10_benchmark.py` | Render the P0-10 benchmark record |
| `check_repository.py` | Enforce repository layout, privacy, links, and package contracts in CI |
