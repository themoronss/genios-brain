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


# `make_domain_compiler` STOOD HERE AND WAS CALLED BY NOTHING. Retired 2026-09-10.
#
# Its docstring described it as the composition root for "a publishing compiler for one tenant",
# activation-aware. The only pass that compiles for a tenant is `reason/domain_shadow`, and it
# cannot use this: it builds TWO compilers — measurement and live — from one catalog and one
# runtime-brain reader, and its live publisher is `_TxnExpertisePublisher(store.engine)`, which
# opens its own transaction PER SITUATION so that one unroutable row cannot abort the rest of the
# pass. This built a `PostgresExpertisePublisher(connection)` on a single shared connection —
# deliberately different transaction semantics, for a caller that never arrived.
#
# So it was a composition root with no composition to root: not stale, never wired. Deleted
# rather than left as a second, drifting answer to "how is a compiler built for a tenant", which
# is what two composition paths become. `expert_catalog` below survives and has real callers.

__all__ = ["expert_catalog"]
