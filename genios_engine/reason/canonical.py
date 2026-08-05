"""Re-export shim — canonical serialization moved to platform/canonical.py.

It is a generic determinism utility (no reasoning in it), and contracts/ needs it too;
contracts may only depend on platform (see tests/test_layer_topology.py). Import from
genios_engine.platform.canonical in new code; this shim keeps existing reason.* imports
working."""
from genios_engine.platform.canonical import (CanonicalizationError, canonical_dumps,
                                              canonicalize, semantic_hash, stable_id)

__all__ = ["CanonicalizationError", "canonical_dumps", "canonicalize",
           "semantic_hash", "stable_id"]
