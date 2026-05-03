"""CLS component package."""

from bridge.cls.api import (
    CLSContext,
    CLSResult,
    component_A,
    component_B,
    component_C,
    component_D,
    component_E,
    component_F,
    score,
)

_LAZY_EXPORTS = {
    "compute_A_and_save": ("bridge.cls.component_a", "compute_A_and_save"),
    "compute_B_and_save": ("bridge.cls.component_b", "compute_B_and_save"),
    "compute_C_and_save": ("bridge.cls.component_c", "compute_C_and_save"),
    "compute_D_and_save": ("bridge.cls.component_d", "compute_D_and_save"),
    "compute_E_and_save": ("bridge.cls.component_e", "compute_E_and_save"),
    "compute_F_and_save": ("bridge.cls.component_f", "compute_F_and_save"),
    "compute_component_A": ("bridge.cls.component_a", "compute_component_A"),
    "compute_component_B": ("bridge.cls.component_b", "compute_component_B"),
    "compute_component_C": ("bridge.cls.component_c", "compute_component_C"),
    "compute_component_D": ("bridge.cls.component_d", "compute_component_D"),
    "compute_component_E": ("bridge.cls.component_e", "compute_component_E"),
    "compute_component_F": ("bridge.cls.component_f", "compute_component_F"),
    "ensure_scanvi_embedding": ("bridge.cls.component_d", "ensure_scanvi_embedding"),
}


def __getattr__(name):
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module 'bridge.cls' has no attribute {name!r}")
    module_name, attr_name = _LAZY_EXPORTS[name]
    from importlib import import_module

    attr = getattr(import_module(module_name), attr_name)
    globals()[name] = attr
    return attr


__all__ = [
    "CLSContext",
    "CLSResult",
    "component_A",
    "component_B",
    "component_C",
    "component_D",
    "component_E",
    "component_F",
    "score",
    *_LAZY_EXPORTS.keys(),
]
