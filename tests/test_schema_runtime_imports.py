"""Lazy contract imports must preserve the registered runtime adapter objects."""
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('submodule_first', [False, True])
def test_public_adapter_exports_preserve_identity_for_both_import_orders(submodule_first):
    code = '''
from importlib import import_module
from bridge.toolkit.registry import ToolRegistry
packages = [
    'p0_04_developmental_compatibility', 'p0_05_off_target_control',
    'p0_06_proliferation_stress_response', 'p0_07_product_comparison_stability',
    'p0_08_evidence_sufficiency', 'p0_09_evidence_compiler',
    'p0_10_claim_verifier', 'p0_12_graft_assessment',
]
registry = ToolRegistry.load_default()
for name in packages:
    module_name = 'bridge.tool_packages.' + name
    if SUBMODULE_FIRST:
        module = import_module(module_name + '.adapter')
    package = import_module(module_name)
    public = package.adapter
    module = import_module(module_name + '.adapter')
    assert public is module.adapter, name
    tool_id = 'P0-' + name.split('_')[1]
    assert registry._resolve_adapter(registry.describe(tool_id)) is public, name
    assert package.adapter is public, name
queries = import_module('bridge.tool_packages.p0_09_evidence_compiler').EvidenceGraphQueries
assert queries is import_module('bridge.tool_packages.p0_09_evidence_compiler.queries').EvidenceGraphQueries
'''.replace('SUBMODULE_FIRST', repr(submodule_first))
    result = subprocess.run([sys.executable, '-c', code], cwd=ROOT,
        env={**os.environ, 'PYTHONPATH': str(ROOT / 'src')}, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
