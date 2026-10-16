# Tests

Tests are repository-only executable evidence and are not included in the BRIDGE wheel.

They cover the shared SDK and contracts, P0 package behavior, source and modality boundaries, OOD and refusal behavior, evidence-state integrity, provenance, and deterministic packaging. Synthetic fixtures test failure modes without committing private product data.

Use the [affected-scope checks](../docs/DEVELOPMENT.md#检查与内部验收) rather than
rerunning every test for documentation changes. Tests named `legacy`, `saved`,
`freeze` or `source` protect current historical-result readers and scientific
boundaries; their names do not mean the tests are obsolete. Remove a test only
when its supported behavior is intentionally retired or equivalent coverage is
retained elsewhere, not because the original implementation is old.

Generated test results, caches, private receipts and temporary acceptance scripts
are not source files and do not belong here. The shareable product/reference
bundle is maintained in [examples/demo](../examples/demo/README.md).

## Web test organization

- web_support.py owns shared application fixtures and synthetic uploads; it is not a collected test file.
- test_web_service.py covers session and user-flow coordination.
- test_web_provider.py covers model action parsing and protocol rejection.
- test_web_artifacts.py covers bounded table previews, integrity and downloads.

Import shared helpers from web_support rather than importing a collected service
test module. Fixture extraction must preserve parametrization and discovered
test cases; unreachable assertions after a terminal return are not coverage.
