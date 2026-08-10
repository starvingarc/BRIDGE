# Decision Log

## 2026-08-10: Rebuild The Active Package

The historical Step1-Step3 implementation moves to `legacy/v1`. BRIDGE v2 uses new high-level Tool Package contracts and has no compatibility requirement with historical score or report APIs.

## 2026-08-10: Separate Scientific Tools From Agent Infrastructure

BRIDGE owns deterministic scientific modules, contracts, environments, artifacts, visualizations and knowledge semantics. The collaborating Agent team owns orchestration, Web, job management and model-provider integration. The first boundary is Python plus JSON CLI; HTTP and MCP adapters are future integration work.

## 2026-08-10: No Current P0 Domain Scores

The PRD's 0-100 language is a future design target. No current `ScoreContract` is frozen, so active tools must emit `domain_score=null`. Raw evidence can still be sufficient for interpretation.

## 2026-08-10: Versioned Local Knowledge

Markdown and YAML are canonical. All catalogued methods receive source-verified cards, while a deterministic generated index supports metadata and full-text retrieval. Formal runs cannot depend on live Web results.

## 2026-08-10: First Executable Package

P0-01 supports declared h5ad and 10x inputs at `analysis_ready`, `count_ready` and contract-only `droplet_ready`. Droplet-specific cell calling and ambient correction remain conditional and are not executed in the first vertical slice.
