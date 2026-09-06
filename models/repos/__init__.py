"""Lazy repository facade.

Repository modules depend on services which in turn use repositories.  Eager
star imports made the result depend on import order and could leave
CollectionService partially initialized.  Keep the legacy facade while
loading only the requested symbol.
"""
from __future__ import annotations

from importlib import import_module


_MODULES = (
    "users_repo", "skill_repo", "tower_progress_repo", "raid_repo",
    "raid_progress_repo", "collection_repo", "static_cache",
)


def __getattr__(name: str):
    if name in {"collection_repo", "static_cache"}:
        module = import_module(f"{__name__}.{name}")
        globals()[name] = module
        return module
    for module_name in _MODULES:
        module = import_module(f"{__name__}.{module_name}")
        if hasattr(module, name):
            value = getattr(module, name)
            globals()[name] = value
            return value
    raise AttributeError(name)
