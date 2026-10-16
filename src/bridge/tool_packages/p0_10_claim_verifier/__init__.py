"""Deterministic P0-10 report claim verifier candidate."""

from bridge.tool_packages._lazy_exports import defer_exports

from bridge.tool_packages.p0_10_claim_verifier.verifier import verify_report

__all__ = ["adapter", "verify_report"]


defer_exports(__name__, {
    "adapter": ("bridge.tool_packages.p0_10_claim_verifier.adapter", "adapter"),
})
