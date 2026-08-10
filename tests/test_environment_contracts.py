from __future__ import annotations

from pathlib import Path

import yaml

from bridge.toolkit.registry import ToolRegistry


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_every_tool_environment_reference_resolves_to_conda_yaml() -> None:
    index = yaml.safe_load((REPO_ROOT / "environments" / "index.yaml").read_text(encoding="utf-8"))
    specs = index["environment_specs"]

    for tool in ToolRegistry.load_default().list():
        assert tool.environment_spec_id in specs
        conda_spec = yaml.safe_load(
            (REPO_ROOT / specs[tool.environment_spec_id]["yaml_ref"]).read_text(encoding="utf-8")
        )
        assert conda_spec["name"].startswith("bridge-")
        assert "python=3.12" in conda_spec["dependencies"]
        assert "prefix" not in conda_spec


def test_active_environment_contracts_do_not_name_machine_local_environments() -> None:
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((REPO_ROOT / "environments").glob("*"))
        if path.is_file()
    )

    assert "name: pytorch" not in text
    assert "/data1/" not in text
    assert "/data2/" not in text
    assert "/Users/" not in text


def test_active_tool_docs_use_environment_specs_not_server_environment_names() -> None:
    docs = REPO_ROOT / "docs" / "bridge_v2_spec_v0.1"
    text = "\n".join(path.read_text(encoding="utf-8") for path in sorted(docs.glob("*.md")))

    assert "`pytorch`" not in text
    assert "`r4.3`" not in text
    assert "bridge-amax" not in text
