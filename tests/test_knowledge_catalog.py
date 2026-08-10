from __future__ import annotations

import json

from bridge.toolkit.knowledge import KnowledgeRegistry


def test_catalog_preserves_all_capability_bindings_and_resolves_methods() -> None:
    registry = KnowledgeRegistry.load_default()
    summary = registry.validation_summary()

    assert summary["valid"] is True
    assert summary["binding_count"] == 396
    assert 343 <= summary["method_count"] <= 385
    assert summary["raw_url_token_count"] == 640
    assert summary["public_url_assignment_count"] == 516
    assert summary["canonical_url_token_count"] == 644
    assert summary["canonical_public_url_assignment_count"] == 520
    assert summary["raw_distinct_public_url_count"] == 388
    assert summary["canonical_public_source_count"] == 385
    assert summary["verified_public_source_count"] == 385
    assert summary["unassigned_evidence_family_count"] == 160
    assert summary["formal_eligible_method_count"] == 0
    assert summary["dangling_method_refs"] == []
    assert summary["dangling_source_refs"] == []


def test_every_method_has_human_card_and_source_or_explicit_reason() -> None:
    registry = KnowledgeRegistry.load_default()

    for method in registry.methods:
        assert method["card_ref"].startswith("knowledge/methods/")
        assert method["source_ids"] or method["source_status"] in {
            "internal_no_public_source",
            "not_registered",
        }
        assert method["primary_paper_status"] in {"available", "not_applicable", "unresolved"}
        assert method["license_status"] in {"reported", "internal", "review_required", "unresolved"}
        assert method["input_requirements"]
        assert method["output_semantics"]
        assert method["critical_boundaries"]

    assert all(alias["resolution"] in {"unique", "context_required"} for alias in registry.snapshot["aliases"])
    assert all(alias["module_ids"] and alias["capabilities"] for alias in registry.snapshot["aliases"])


def test_search_returns_traceable_p0_01_sources() -> None:
    registry = KnowledgeRegistry.load_default()

    hits = registry.search("doublet raw counts confirmed capture", module_id="P0-01", limit=5)

    assert hits
    assert any("Scrublet" in hit.title or "scDblFinder" in hit.title for hit in hits)
    assert all(hit.source_ids for hit in hits)
    assert all(hit.snapshot_id == registry.snapshot_id for hit in hits)


def test_chinese_search_finds_ambient_rna_methods() -> None:
    registry = KnowledgeRegistry.load_default()

    hits = registry.search("环境 RNA 原始 counts 校正矩阵", module_id="P0-01", limit=8)

    assert any("SoupX" in hit.title or "CellBender" in hit.title for hit in hits)


def test_competitor_isolated_methods_are_not_retrievable() -> None:
    registry = KnowledgeRegistry.load_default()

    hits = registry.search("CapybaraBrain competitor", limit=20)

    assert all("CapybaraBrain" not in hit.title for hit in hits)


def test_clean_room_methods_are_retrievable_without_competitor_baseline() -> None:
    registry = KnowledgeRegistry.load_default()

    independent = registry.search("independent continuous identity", module_id="P0-02", limit=20)
    conformal = registry.search("scConform preregistered classifier", module_id="P0-02", limit=20)

    assert any("BRIDGE independent continuous identity" in hit.title for hit in independent)
    assert any("scConform" in hit.title for hit in conformal)
    assert all("CapybaraBrain" not in hit.title for hit in [*independent, *conformal])


def test_search_supports_status_source_and_use_filters() -> None:
    registry = KnowledgeRegistry.load_default()

    hits = registry.search(
        "doublet",
        module_id="P0-01",
        source_type="primary_paper",
        scientific_status="candidate",
        allowed_use="planning",
        limit=10,
    )

    assert hits
    assert all("P0-01" in hit.tool_package_ids for hit in hits)


def test_packaged_snapshot_contains_no_private_paths() -> None:
    registry = KnowledgeRegistry.load_default()
    payload = json.dumps(registry.snapshot, ensure_ascii=False)

    assert "/data1/" not in payload
    assert "/data2/" not in payload
    assert "/Users/" not in payload
    assert "yuxiao" not in payload.lower()


def test_curated_p0_01_source_corrections_are_present() -> None:
    registry = KnowledgeRegistry.load_default()
    methods = {method["display_name"]: method for method in registry.methods}
    sources = {source["source_id"]: source["url"] for source in registry.sources}

    sample_qc_urls = {sources[source_id] for source_id in methods["SampleQC"]["source_ids"]}
    assert "https://doi.org/10.1186/s13059-023-02859-3" in sample_qc_urls
    assert all("02859-x" not in url for url in sample_qc_urls)
    assert methods["SoupX"]["license_raw"] == ["GPL-3.0"]
    assert methods["scQCenrich"]["license_raw"] == ["MIT"]
    assert all(
        str(source["verification_status"]).startswith("verified")
        for source in registry.sources
    )
