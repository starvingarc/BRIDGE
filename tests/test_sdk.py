from __future__ import annotations

from bridge import (
    describe_figure_component,
    describe_tool,
    describe_tool_input,
    list_figure_components,
    list_tools,
    search_knowledge,
    validate_figure_registry,
)


def test_python_sdk_lists_and_describes_registered_tools() -> None:
    tools = list_tools()

    assert [tool.tool_id for tool in tools] == [f"P0-{index:02d}" for index in range(1, 13)]
    assert describe_tool("P0-01").name == "Input Audit & QC"


def test_python_sdk_describes_tool_input_contract() -> None:
    contract = describe_tool_input("P0-07")

    assert contract.object_input_modes[0].roles[-1].min_count == 2


def test_p0_02_input_contract_declares_runtime_qc_metadata() -> None:
    contract = describe_tool_input("P0-02")

    assert contract.asset_input is not None
    assert contract.asset_input.required_metadata_keys == [
        "source_family_id",
        "qc_profile_ref",
    ]


def test_python_sdk_searches_packaged_knowledge() -> None:
    hits = search_knowledge("ambient RNA correction", module_id="P0-01", limit=5)

    assert hits
    assert all("P0-01" in hit.tool_package_ids for hit in hits)


def test_python_sdk_discovers_figure_components() -> None:
    figures = list_figure_components(tool_id="P0-02")

    assert len(figures) == 5
    assert all(figure.producer_tool_ids == ["P0-02"] for figure in figures)
    assert (
        describe_figure_component("bridge.cell_state.composition-l1.v0.1").title
        == "Broad cell-state composition"
    )


def test_python_sdk_validates_figure_registry() -> None:
    result = validate_figure_registry()

    assert result["component_count"] == 38
    assert result["typed_candidate_count"] == 31
    assert result["legacy_untyped_count"] == 7
