"""P0-07 Product Comparison & Stability package."""

from bridge.tool_packages._lazy_exports import defer_exports


__all__ = ["adapter"]


defer_exports(__name__, {
    "adapter": ("bridge.tool_packages.p0_07_product_comparison_stability.adapter", "adapter"),
})
