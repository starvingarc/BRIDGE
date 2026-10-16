"""Regeneration must detect drift without changing packaged files or loading science."""
import importlib.util
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys

import pytest
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]


def test_schema_export_import_does_not_load_scientific_dependencies():
    # A fresh interpreter catches eager package/adapter imports hidden by pytest.
    code = '''
import sys, runpy
class NoScientificRuntime:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {
            'numpy', 'pandas', 'scipy', 'sklearn', 'anndata', 'scanpy',
            'h5py', 'matplotlib', 'torch', 'decoupler', 'celltypist', 'networkx', 'pyarrow',
        }:
            raise ImportError('schema_export_requires_scientific_runtime: ' + fullname)
sys.meta_path.insert(0, NoScientificRuntime())
module = runpy.run_path('scripts/export_schemas.py')
assert len(module['render_schemas']()) > 0
'''
    result = subprocess.run([sys.executable, '-c', code], cwd=ROOT,
        env={**os.environ, 'PYTHONPATH': str(ROOT / 'src')}, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.fixture
def exporter():
    spec = importlib.util.spec_from_file_location('schema_export_under_test', ROOT / 'scripts/export_schemas.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_current_registered_exports_match_without_rewriting(exporter):
    root = ROOT / 'src/bridge/resources/schemas'
    before = {p.name: p.read_bytes() for p in root.glob('*.json')}
    assert callable(getattr(exporter, 'check_schemas', None)), 'read-only check is missing'
    assert exporter.check_schemas(root) == []
    assert {p.name: p.read_bytes() for p in root.glob('*.json')} == before


@pytest.mark.parametrize('damage', ['bytes', 'missing', 'extra', 'historical', 'invalid_id'])
def test_check_reports_exact_damaged_file_and_never_repairs_it(exporter, tmp_path, damage):
    root = tmp_path / 'schemas'
    shutil.copytree(ROOT / 'src/bridge/resources/schemas', root)
    name = 'tool_request.schema.json'
    if damage == 'bytes':
        path = root / name
        path.write_bytes(path.read_bytes().rstrip())  # Same JSON, different bytes.
    elif damage == 'missing':
        (root / name).unlink()
    elif damage == 'invalid_id':
        path = root / name
        value = json.loads(path.read_text())
        value['$id'] = []
        path.write_text(json.dumps(value))
    elif damage == 'extra':
        name = 'unregistered.schema.json'
        (root / name).write_text('{}\n')
    else:
        name = 'developmental_compatibility_result.schema.json'
        (root / name).write_bytes((root / name).read_bytes() + b' ')
    before = {p.name: p.read_bytes() for p in root.glob('*.json')}
    assert callable(getattr(exporter, 'check_schemas', None)), 'read-only check is missing'
    problems = exporter.check_schemas(root)
    assert any(name in problem for problem in problems), problems
    assert {p.name: p.read_bytes() for p in root.glob('*.json')} == before


def test_changed_model_without_regeneration_is_detected(exporter, tmp_path, monkeypatch):
    class Example(BaseModel):
        value: int
    schema_id = 'bridge://schemas/example/v0.1'
    monkeypatch.setattr(exporter, 'MODELS', {'example': (schema_id, Example)})
    monkeypatch.setattr(exporter, 'SCHEMA_LINKS', {})
    # A checked-in old model snapshot is independent of the new renderer.
    old = Example.model_json_schema()
    old['properties']['value']['type'] = 'string'
    old['$id'] = schema_id
    (tmp_path / 'example.schema.json').write_text(json.dumps(old, ensure_ascii=False, indent=2, sort_keys=True) + '\n')
    assert callable(getattr(exporter, 'check_schemas', None)), 'read-only check is missing'
    monkeypatch.setattr(exporter, 'SCHEMA_REFS', {schema_id: 'example.schema.json'})
    monkeypatch.setattr(exporter, 'HISTORICAL_SNAPSHOTS', {})
    assert any('example.schema.json' in problem for problem in exporter.check_schemas(tmp_path))


@pytest.mark.parametrize('damage', ['unregistered', 'wrong_id', 'no_producer', 'stale_pin', 'duplicate_file'])
def test_registry_and_producers_are_checked_in_both_directions(exporter, tmp_path, monkeypatch, damage):
    class Example(BaseModel):
        value: int
    schema_id = 'bridge://schemas/example/v0.1'
    filename = 'example.schema.json'
    monkeypatch.setattr(exporter, 'MODELS', {'example': (schema_id, Example)})
    monkeypatch.setattr(exporter, 'SCHEMA_LINKS', {})
    refs = {schema_id: filename}
    monkeypatch.setattr(exporter, 'SCHEMA_REFS', refs)
    monkeypatch.setattr(exporter, 'HISTORICAL_SNAPSHOTS', {})
    # Generate a valid baseline, then change only the registration contract.
    assert exporter.main(['--output-dir', str(tmp_path)]) == 0
    assert exporter.check_schemas(tmp_path) == []
    if damage == 'unregistered':
        refs.clear()
    elif damage == 'wrong_id':
        refs['bridge://schemas/wrong/v0.1'] = refs.pop(schema_id)
    elif damage == 'duplicate_file':
        refs['bridge://schemas/duplicate/v0.1'] = filename
    elif damage == 'no_producer':
        monkeypatch.setattr(exporter, 'MODELS', {})
    else:
        exporter.HISTORICAL_SNAPSHOTS['old.schema.json'] = '0' * 64
    problems = exporter.check_schemas(tmp_path)
    assert problems
    assert any(('old.schema.json' if damage == 'stale_pin' else filename) in p
               or 'same file' in p for p in problems), problems


def test_cli_exit_status_and_read_only_check(exporter, tmp_path, capsys):
    root = tmp_path / 'schemas'
    shutil.copytree(ROOT / 'src/bridge/resources/schemas', root)
    assert exporter.main(['--check', '--output-dir', str(root)]) == 0
    path = root / 'tool_request.schema.json'
    damaged = path.read_bytes() + b' '
    path.write_bytes(damaged)
    assert exporter.main(['--check', '--output-dir', str(root)]) == 1
    assert 'tool_request.schema.json' in capsys.readouterr().out
    assert path.read_bytes() == damaged


def test_check_does_not_create_missing_output_directory(exporter, tmp_path):
    missing = tmp_path / 'absent'
    assert exporter.main(['--check', '--output-dir', str(missing)]) == 1
    assert not missing.exists()
