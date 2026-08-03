"""g-i-1 Memory Integration Layer.

Read-only pipe from customer memory sources -> normalized MemoryItem stream.
Persists ONLY operational metadata (connection, cursor, mapping, scope grants).
NEVER persists customer content.

Public API:
    from core.memory import MemoryAdapter, MemoryItem, register_adapter
"""

from core.memory.interface import MemoryAdapter
from core.memory.types import (
    AuthConfig,
    ConnectionHandle,
    Cursor,
    HealthStatus,
    MemoryItem,
    RawRecord,
    ReadScope,
    SourceMapping,
)

__all__ = [
    "AuthConfig",
    "ConnectionHandle",
    "Cursor",
    "HealthStatus",
    "MemoryAdapter",
    "MemoryItem",
    "RawRecord",
    "ReadScope",
    "SourceMapping",
]
