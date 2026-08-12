from __future__ import annotations

from bridge import describe_tool, list_tools, search_knowledge


def test_python_sdk_lists_and_describes_registered_tools() -> None:
    tools = list_tools()

    assert [tool.tool_id for tool in tools] == [f"P0-{index:02d}" for index in range(1, 13)]
    assert describe_tool("P0-01").name == "Input Audit & QC"


def test_python_sdk_searches_packaged_knowledge() -> None:
    hits = search_knowledge("ambient RNA correction", module_id="P0-01", limit=5)

    assert hits
    assert all("P0-01" in hit.tool_package_ids for hit in hits)
