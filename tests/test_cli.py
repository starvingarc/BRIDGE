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
