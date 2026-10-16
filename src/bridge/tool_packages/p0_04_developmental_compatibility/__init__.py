"""P0-04 Developmental Compatibility package."""

from bridge.tool_packages._lazy_exports import defer_exports


__all__ = ["adapter"]


defer_exports(__name__, {
    "adapter": ("bridge.tool_packages.p0_04_developmental_compatibility.adapter", "adapter"),
})
