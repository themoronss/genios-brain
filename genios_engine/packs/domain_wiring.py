"""Composition root for the Atlas Layer 3 compiler.

The caller owns the SQL transaction.  Keeping the dynamic-brain read and immutable package insert
on the same connection gives one tenant-scoped publication unit without letting Layer 3 create a
second database lifecycle behind the platform's back.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from genios_engine.packs.compiler import (
    DomainCompiler,
    ExpertBrainCatalog,
    PostgresExpertisePublisher,
    PostgresRuntimeBrains,
)
from genios_engine.packs.compiler.authoring import default_authoring_root


@lru_cache(maxsize=4)
def expert_catalog(authoring_root: str = "") -> ExpertBrainCatalog:
    root = Path(authoring_root).resolve() if authoring_root else default_authoring_root()
    return ExpertBrainCatalog(root)


def make_domain_compiler(connection, *, authoring_root: str = "") -> DomainCompiler:
    return DomainCompiler(
        catalog=expert_catalog(authoring_root),
        runtime_brains=PostgresRuntimeBrains(connection),
        publisher=PostgresExpertisePublisher(connection),
    )


__all__ = ["expert_catalog", "make_domain_compiler"]
