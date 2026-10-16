"""Deterministic candidate Evidence Compiler & Reconciler (P0-09)."""

from bridge.tool_packages._lazy_exports import defer_exports

from bridge.tool_packages.p0_09_evidence_compiler.compiler import compile_evidence_graph

__all__ = ["EvidenceGraphQueries", "adapter", "compile_evidence_graph"]


defer_exports(__name__, {
    "adapter": ("bridge.tool_packages.p0_09_evidence_compiler.adapter", "adapter"),
    "EvidenceGraphQueries": ("bridge.tool_packages.p0_09_evidence_compiler.queries", "EvidenceGraphQueries"),
})
