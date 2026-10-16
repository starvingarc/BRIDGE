"""Defer runtime exports while preserving same-named package/submodule aliases."""
from importlib import import_module
import sys
from types import ModuleType


class _LazyExports(ModuleType):
    def __getattribute__(self, name):
        namespace = ModuleType.__getattribute__(self, "__dict__")
        target = namespace.get("_lazy_export_targets", {}).get(name)
        if target is not None:
            # Python installs a submodule on its parent under the same name.
            # __getattr__ alone would return that module after adapter-first
            # imports, instead of the historical public adapter instance.
            module_name, attribute = target
            value = getattr(import_module(module_name), attribute)
            namespace[name] = value
            return value
        return ModuleType.__getattribute__(self, name)


def defer_exports(package_name: str, exports: dict[str, tuple[str, str]]) -> None:
    package = sys.modules[package_name]
    package.__dict__["_lazy_export_targets"] = exports
    package.__class__ = _LazyExports
