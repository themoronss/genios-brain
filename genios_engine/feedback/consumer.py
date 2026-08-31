"""Compatibility re-export — the consumption contract moved to `contracts/learned_state.py`.

Its docstring called this module "the ONLY safe way a lower layer reads" learned state, and no
lower layer ever imported it — because none legally could: the layer topology forbids an upward
import and feedback is layer 7. A consumption contract only the producing layer may import is a
decoy seam. The vocabulary now lives in `contracts/`, importable by every layer; this name stays
so existing tests and callers keep working.
"""
from genios_engine.contracts.learned_state import (
    CONSUMER_ALLOWLIST,
    LearnedState,
    may_consume,
    snapshot,
    snapshot_all,
)

__all__ = ["CONSUMER_ALLOWLIST", "LearnedState", "may_consume", "snapshot", "snapshot_all"]
