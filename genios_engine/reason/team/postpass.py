"""The post-pass hook (SCREEN_INTEL_P4 §3.1, frozen).

`run_post_passes(engine, card_store, org_id, *, now)` runs after `build_cards_for_org` in the
chain (`api/routes._run_l2_chain`). Every registered pass is a module exposing
`run(engine, card_store, org_id, *, now) -> int` (situations emitted), imported lazily:

    team     genios_engine.reason.team.passes     (group A)
    verify   genios_engine.reason.verify.passes   (group B — skipped until it exists)

A pass whose module does not exist is skipped silently (that is how B lands later without
touching this file). A pass that is present but fails — at import or at run — is LOGGED and the
next pass still runs; nothing here ever raises into the chain.
"""
from __future__ import annotations

import importlib
import importlib.util
from datetime import datetime

from genios_engine.platform.logging import get_logger

_log = get_logger("genios.team.postpass")

#: (name, module) in run order. Team first: a verify moment about a discrepancy is less urgent
#: than "the person your deadline depends on is away".
PASSES: tuple[tuple[str, str], ...] = (
    ("team", "genios_engine.reason.team.passes"),
    ("verify", "genios_engine.reason.verify.passes"),
    # P5 group B: prep precompute (device seats, next 3 h) + P-16 post-meeting follow-ups.
    ("meetings", "genios_engine.reason.meetings.passes"),
)


def _present(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):       # the parent package itself does not exist
        return False


def run_post_passes(engine, card_store, org_id: str, *, now: datetime) -> dict[str, int]:
    """Run every registered pass for one org. Returns {pass name: situations emitted} for the
    passes that ran; a failed pass is absent from the result (and logged)."""
    out: dict[str, int] = {}
    for name, module in PASSES:
        if not _present(module):
            continue
        try:
            run = getattr(importlib.import_module(module), "run")
            out[name] = int(run(engine, card_store, org_id, now=now) or 0)
        except Exception:      # noqa: BLE001 — a failing pass never fails the chain
            _log.exception("post-pass %s failed for org_id=%s", name, org_id)
    return out


__all__ = ["PASSES", "run_post_passes"]
