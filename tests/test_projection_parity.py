from __future__ import annotations

from pathlib import Path

from bridge.toolkit.registry import ToolRegistry


def test_public_and_packaged_tool_cards_are_byte_identical() -> None:
    repo = Path(__file__).resolve().parents[1]
    public_cards = {
        path.stem: path
        for path in (repo / "src" / "bridge" / "tool_packages" / "cards").glob("P0-*.md")
    }
    packaged_cards = {
        path.parent.name: path for path in (repo / "tool_packages").glob("P0-*/README.md")
    }

    assert public_cards.keys() == packaged_cards.keys() == {
        f"P0-{index:02d}" for index in range(1, 13)
    }
    for tool_id in sorted(public_cards):
        assert public_cards[tool_id].read_bytes() == packaged_cards[tool_id].read_bytes()


def test_public_and_packaged_schemas_are_byte_identical() -> None:
    repo = Path(__file__).resolve().parents[1]
    public_schemas = {path.name: path for path in (repo / "schemas").glob("*.schema.json")}
    packaged_schemas = {
        path.name: path
        for path in (repo / "src" / "bridge" / "resources" / "schemas").glob("*.schema.json")
    }

    assert public_schemas.keys() == packaged_schemas.keys()
    for filename in sorted(public_schemas):
        assert public_schemas[filename].read_bytes() == packaged_schemas[filename].read_bytes()


def test_cards_preserve_cell_state_boundary_and_scaffold_method_selection() -> None:
    repo = Path(__file__).resolve().parents[1]
    cards = repo / "src" / "bridge" / "tool_packages" / "cards"
    cell_state = (cards / "P0-02.md").read_text(encoding="utf-8")

    assert "| Package version | `0.4.8` |" in cell_state
    assert "| Freeze state | `biological_review_in_progress` |" in cell_state
    assert "No state or method is frozen." in cell_state
    assert "locked external-source and OOD testing" in cell_state

    registry = ToolRegistry.load_default()
    for spec in registry.list():
        card = (cards / f"{spec.tool_id}.md").read_text(encoding="utf-8")
        if spec.implementation_state.value == "scaffold":
            assert "No method is selected while this package remains a scaffold." in card
            assert "No method is registered or selected until benchmark-bound execution exists." in card


def test_external_source_documentation_is_indexed_and_preserves_boundaries() -> None:
    repo = Path(__file__).resolve().parents[1]
    index = (repo / "docs" / "index.md").read_text(encoding="utf-8")
    documentation = (
        repo / "docs" / "bridge_spec_v0.1" / "external_source_preparation.md"
    ).read_text(encoding="utf-8")

    assert "external_source_preparation.md" in index
    assert "bridge-benchmark cell-state prepare-birtele" in documentation
    assert "bridge-benchmark cell-state audit-external-sources" in documentation
    assert "conversion_manifest.json" in documentation
    assert "external_source_lineage_overlap:<asset>:<external-root>" in documentation
    assert "biological_review_in_progress" in documentation
    assert "`scientific_status` remains `candidate`" in documentation
    assert "`domain_score` remains\n`null`" in documentation
    assert "does not establish donor identity" in documentation
