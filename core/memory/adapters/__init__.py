"""Adapter registry — providers register here; engine looks them up by source_type.

Adding source #2 = writing one class implementing MemoryAdapter + register_adapter()
call. Zero engine changes — per g-i-1 §1.1.1 acceptance criterion.

Two construction paths share the same registry:
- Known adapters (`adapters/known/`)   — mapping hardcoded
- Custom adapters (`adapters/custom/`) — mapping LLM-proposed + human-confirmed + frozen
"""

from __future__ import annotations

from collections.abc import Callable

from core.memory.interface import MemoryAdapter

# Factory takes connection_id + org_id (and optionally a frozen mapping for custom),
# returns a constructed adapter instance.
AdapterFactory = Callable[..., MemoryAdapter]

_REGISTRY: dict[str, AdapterFactory] = {}


def register_adapter(source_type: str, factory: AdapterFactory) -> None:
    """Register an adapter factory under a source_type key.

    Called at import time by each adapter module. Re-registering replaces.
    """
    _REGISTRY[source_type] = factory


def get_factory(source_type: str) -> AdapterFactory:
    """Look up a factory by source_type. Raises KeyError if unknown."""
    if source_type not in _REGISTRY:
        raise KeyError(
            f"No adapter registered for source_type={source_type!r}. "
            f"Known: {sorted(_REGISTRY.keys())}"
        )
    return _REGISTRY[source_type]


def known_source_types() -> list[str]:
    """Snapshot of currently-registered source_types."""
    return sorted(_REGISTRY.keys())


# Eager imports so registration runs at package import time.
# Each adapter module ends with `register_adapter("<name>", <factory>)`.
from core.memory.adapters.custom import runtime as _custom_runtime  # noqa: E402, F401
from core.memory.adapters.known import calendar as _calendar  # noqa: E402, F401
from core.memory.adapters.known import gmail as _gmail  # noqa: E402, F401
from core.memory.adapters.known import notion as _notion  # noqa: E402, F401
from core.memory.adapters.known import slack as _slack  # noqa: E402, F401
