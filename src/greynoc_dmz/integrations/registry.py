from __future__ import annotations

from .models import Adapter

_REGISTRY: dict[str, type[Adapter]] = {}


def register(adapter_cls: type[Adapter]) -> type[Adapter]:
    """Class decorator that registers an adapter under its ``name``."""
    _REGISTRY[adapter_cls.name] = adapter_cls
    return adapter_cls


def get_adapter(name: str) -> type[Adapter] | None:
    return _REGISTRY.get(name)


def adapter_names() -> list[str]:
    return sorted(_REGISTRY)
