from __future__ import annotations

import json
from pathlib import Path

from bridge.toolkit.cli import main


def test_cli_list_emits_machine_readable_registry(capsys) -> None:
    exit_code = main(["list", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert [item["tool_id"] for item in payload] == [f"P0-{index:02d}" for index in range(1, 13)]


def test_cli_describe_rejects_unknown_tool(capsys) -> None:
    exit_code = main(["describe", "P0-99", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert payload == {"error": "unknown_tool", "tool_id": "P0-99"}


def test_cli_emits_machine_readable_input_contract(capsys) -> None:
    exit_code = main(["input-contract", "P0-12", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["schema_ref"] == "bridge://schemas/tool-input-contract/v0.1"
    assert [mode["mode_id"] for mode in payload["object_input_modes"]] == [
        "not_provided",
        "graft_assessment",
        "expression_analysis",
    ]


def test_cli_validate_reports_missing_input_as_ineligible(tmp_path: Path, capsys) -> None:
    request_path = tmp_path / "request.json"
    request_path.write_text(
        json.dumps(
            {
                "request_id": "request-empty",
                "tool_id": "P0-01",
                "output_dir": str(tmp_path / "output"),
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(["validate", "--request", str(request_path)])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 3
    assert payload["eligible"] is False
    assert payload["reason_codes"] == ["exactly_one_expression_asset_required"]


def test_cli_knowledge_validate_returns_nonzero_for_invalid_snapshot(monkeypatch, capsys) -> None:
    from bridge.toolkit.knowledge import KnowledgeRegistry

    class InvalidKnowledgeRegistry:
        @staticmethod
        def validation_summary() -> dict[str, object]:
            return {"valid": False, "dangling_method_refs": ["METHOD-MISSING"]}

    monkeypatch.setattr(
        KnowledgeRegistry,
        "load_default",
        classmethod(lambda cls: InvalidKnowledgeRegistry()),
    )

    exit_code = main(["knowledge", "validate"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 3
    assert payload["valid"] is False
    assert payload["dangling_method_refs"] == ["METHOD-MISSING"]


def test_cli_knowledge_show_returns_complete_method_record(capsys) -> None:
    from bridge.toolkit.knowledge import KnowledgeRegistry

    registry = KnowledgeRegistry.load_default()
    method = registry.methods[0]

    exit_code = main(["knowledge", "show", method["method_id"]])

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == method


def test_cli_knowledge_show_returns_complete_source_record(capsys) -> None:
    from bridge.toolkit.knowledge import KnowledgeRegistry

    registry = KnowledgeRegistry.load_default()
    source = registry.sources[0]

    exit_code = main(["knowledge", "show", source["source_id"]])

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == source


def test_cli_knowledge_show_rejects_unknown_id(capsys) -> None:
    exit_code = main(["knowledge", "show", "SOURCE-NOT-REGISTERED"])

    assert exit_code == 2
    assert json.loads(capsys.readouterr().out) == {
        "error": "unknown_knowledge_id",
        "knowledge_id": "SOURCE-NOT-REGISTERED",
    }


def test_cli_figures_list_filters_by_producer_tool(capsys) -> None:
    exit_code = main(["figures", "list", "--tool", "P0-01"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert [item["component_id"] for item in payload] == [
        "bridge.qc.counts_genes",
        "bridge.qc.overview",
    ]
    assert all(item["registry_state"] == "legacy_untyped" for item in payload)


def test_cli_figures_show_resolves_legacy_component_id(capsys) -> None:
    exit_code = main(["figures", "show", "bridge.qc.overview.v0.1"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["component_id"] == "bridge.qc.overview"
    assert payload["component_version"] == "0.1.0"


def test_cli_figures_show_rejects_unknown_component(capsys) -> None:
    exit_code = main(["figures", "show", "bridge.not.registered@0.1.0"])

    assert exit_code == 2
    assert json.loads(capsys.readouterr().out) == {
        "error": "unknown_figure_component",
        "component_ref": "bridge.not.registered@0.1.0",
    }


def test_cli_figures_validate_reports_migration_state(capsys) -> None:
    exit_code = main(["figures", "validate"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["valid"] is True
    assert payload["component_count"] == 7
    assert payload["typed_candidate_count"] == 0
    assert payload["legacy_untyped_count"] == 7
