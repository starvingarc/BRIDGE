"""Mutation checks for documentation contracts; standard library only."""
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import check_documentation as checker


class DocumentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.paths = [Path(p) for p in subprocess.check_output(
            ["git", "ls-files"], cwd=ROOT, text=True).splitlines()]

    def problems(self, changes=None, extra=()):
        original = Path.read_text
        changes = {ROOT / key: value for key, value in (changes or {}).items()}
        def read(path, *args, **kwargs):
            return changes[path] if path in changes else original(path, *args, **kwargs)
        with patch.object(Path, "read_text", read):
            return checker.check_documentation(ROOT, [*self.paths, *map(Path, extra)])

    def mutate(self, path, old, new, expected):
        before = (ROOT / path).read_text()
        self.assertIn(old, before)
        problems = self.problems({path: before.replace(old, new, 1)})
        self.assertTrue(any(expected in item for item in problems), problems)

    def test_current_repository(self):
        self.assertEqual(self.problems(), [])

    def test_package_version(self):
        self.mutate("pyproject.toml", 'version = "0.3.0"', 'version = "9.9.9"', "package version")

    def test_tool_card_version(self):
        self.mutate("src/bridge/tool_packages/cards/P0-10.md",
                    "| Package version |", "| Removed version |", "Package version")

    def test_tool_card_result_missing(self):
        self.mutate("src/bridge/tool_packages/cards/P0-10.md",
                    "| Result schema |", "| Removed result |", "Result schema")

    def test_scientific_current_result(self):
        self.mutate("docs/bridge_spec_v0.1/developmental_compatibility_task_card.md",
                    "bridge://schemas/developmental-compatibility-result/v0.4",
                    "bridge://schemas/developmental-compatibility-result/v0.3", "primary result")

    def test_request_pin(self):
        path = "examples/requests/p0_10_claim_verifier.json"
        import json
        value = json.loads((ROOT / path).read_text())
        value["tool_version"] = "9.9.9"
        self.assertTrue(any("tool_version" in p for p in self.problems({path: json.dumps(value)})))

    def test_profile_pin(self):
        self.mutate("examples/agent-integration/profiles/single-product.json",
                    '"tool_version": "0.6.0"', '"tool_version": "9.9.9"', "tool_version")

    def test_input_schema_coverage(self):
        self.mutate("src/bridge/tool_packages/_input_contracts.py",
                    '"bridge://schemas/research-report-context/v0.5"',
                    '"bridge://schemas/research-report-context/v0.9"', "input schema")

    def test_input_version_coverage(self):
        self.mutate("src/bridge/tool_packages/_input_contracts.py",
                    '("0.3.0", "0.4.0", "0.5.0")', '("0.3.0", "0.4.0")', "input version")

    def test_adapter_additional_schema_is_checked(self):
        self.mutate("src/bridge/tool_packages/p0_10_claim_verifier/research.py",
                    'RESEARCH_CONTEXT_V05_SCHEMA_REF = "bridge://schemas/research-report-context/v0.5"',
                    'RESEARCH_CONTEXT_V05_SCHEMA_REF = "bridge://schemas/research-report-context/v0.9"',
                    "input schema")

    def test_script_index(self):
        self.assertTrue(any("script index" in p for p in self.problems(extra=["scripts/new_script.py"])))

    def test_document_index(self):
        self.assertTrue(any("documentation index" in p for p in self.problems(extra=["docs/new_document.md"])))

    def test_ownership_scope(self):
        self.mutate("AGENTS.md", "不穷尽", "列全", "ownership")

    def test_numeric_document_assertion(self):
        self.mutate("docs/web-preview.md", "600-second HTTP timeout", "601-second HTTP timeout", "assertion")

    def test_numeric_source_assertion(self):
        self.mutate("src/bridge/web/provider.py", "_INTERPRETATION_REQUEST_TIMEOUT_SECONDS = 600",
                    "_INTERPRETATION_REQUEST_TIMEOUT_SECONDS = 601", "assertion")

    def test_deleted_assertion(self):
        self.mutate("docs/web-preview.md", "600-second HTTP timeout", "timeout", "assertion")

    def test_relative_anchor(self):
        self.mutate("docs/RELEASE.md", "## 当前开发版本", "## Renamed current version", "anchor")

    def test_historical_versions_are_not_current_package_assertions(self):
        path = "docs/RELEASE.md"
        text = (ROOT / path).read_text() + "\nHistorical record: package 0.0.1 used a different format.\n"
        self.assertEqual(self.problems({path: text}), [])

    def test_missing_language_constraint(self):
        self.mutate("frontend/package.json", '"node":', '"removed_node":', "language version")

    def test_language_source_reference(self):
        self.mutate("README.md", "engines.node", "removed_field", "language version")

    def test_unknown_card_input_role(self):
        self.mutate("src/bridge/tool_packages/cards/P0-10.md",
                    "| `research_report_context` |", "| `new_context` |", "input schema")

    def test_output_cap_document(self):
        current = checker.PythonText(ROOT).named(
            "src/bridge/web/model_transport.py", "_REASONING_OUTPUT_TOKEN_LIMIT")
        self.mutate("docs/web-preview.md", f"allow at least {current:,} output tokens",
                    f"allow at least {current + 1:,} output tokens", "assessment-output-cap")

    def test_output_cap_source(self):
        self.mutate("src/bridge/web/provider.py", "_INTERPRETATION_OUTPUT_TOKEN_LIMIT = 20000",
                    "_INTERPRETATION_OUTPUT_TOKEN_LIMIT = 21000", "assertion")

    def test_invalid_assertion_count(self):
        self.mutate("scripts/documentation_assertions.json", '"count": 1', '"count": 0',
                    "invalid documentation assertion")

    def test_anchors_accept_supported_markdown(self):
        text = """# Hello, *World*!
# Hello, *World*!
# 中文标题
Setext title
============
<a id="record-one"></a>
<a name='old-record'></a>
```md
# Not a heading
[ignored](absent.md)
```
"""
        self.assertEqual(checker.anchors(text),
                         {"hello-world", "hello-world-1", "中文标题", "setext-title", "record-one", "old-record"})
        links = list(checker.local_links(Path("docs/source.md"),
                     text + "\n[中文](target.md#%E4%B8%AD%E6%96%87)\n"))
        self.assertEqual(links[0][:2], (Path("docs/target.md"), "中文"))
        self.assertEqual(len(links), 1)

    def test_explicit_anchor_removal_fails(self):
        path = "docs/validation/p0_03_target_regional.md"
        self.mutate(path, 'id="record-p0-03-target-regional-20260825"',
                    'id="removed-record"', "anchor")

    def test_unknown_adapter_constant_fails_closed(self):
        self.mutate("src/bridge/tool_packages/p0_10_claim_verifier/research.py",
                    'RESEARCH_CONTEXT_V05_SCHEMA_REF = "bridge://schemas/research-report-context/v0.5"',
                    'RESEARCH_CONTEXT_V05_SCHEMA_REF = unknown_schema_factory()', "documentation source")

    def test_scientific_index_cannot_omit_a_package(self):
        self.mutate("docs/bridge_spec_v0.1/README.md", "[P0-01", "[Unknown-01", "primary result")

    def test_adapter_schema_tuple_reads_all_versions(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = Path("adapter.py")
            (root / path).write_text('ROLE_SCHEMAS = {"context": ("bridge://schemas/context/v0.1", "bridge://schemas/context/v0.2")}\n')
            self.assertEqual(checker.adapter_schemas(checker.PythonText(root), path),
                             {"context": {"bridge://schemas/context/v0.1", "bridge://schemas/context/v0.2"}})

    def test_every_mapped_assertion_rejects_document_drift(self):
        import json
        import re
        rows = json.loads((ROOT / "scripts/documentation_assertions.json").read_text())
        for row in rows:
            for group in row["groups"]:
                with self.subTest(assertion=row["id"], group=group):
                    document = row["document"]
                    before = (ROOT / document).read_text()
                    match = re.search(row["pattern"], before, re.M)
                    self.assertIsNotNone(match)
                    start, end = match.span(group)
                    # Preserve the declared lexical format but alter the captured fact.
                    changed = str(int(match[group].replace(",", "")) + 1) if match[group].replace(",", "").isdigit() else "9.9.9"
                    errors = self.problems({document: before[:start] + changed + before[end:]})
                    self.assertTrue(any("assertion: " + row["id"] + ":" in error for error in errors), errors)

    def test_unused_helper_roles_do_not_count_as_accepted_inputs(self):
        self.mutate("src/bridge/tool_packages/_input_contracts.py",
                    "        *common,\n", "", "input schema")

    def test_unused_conditional_role_extension_does_not_count(self):
        self.mutate("src/bridge/tool_packages/_input_contracts.py",
                    "        roles.extend(", "        unused_roles = (", "input schema")


if __name__ == "__main__":
    unittest.main()
