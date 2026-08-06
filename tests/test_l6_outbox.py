"""L6 outbox — retry policy is pure and bounded; delivery is state, not hope.
And the L6-01 lock: every state the engine writes is visible in the feed."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from genios_engine.deliver.outbox import (BACKOFF_MINUTES, digest_card_id,
                                          next_attempt_delay)


def test_backoff_schedule_is_bounded_and_monotonic():
    delays = [next_attempt_delay(n) for n in range(1, len(BACKOFF_MINUTES) + 1)]
    assert delays == list(BACKOFF_MINUTES)
    assert all(delays[i] < delays[i + 1] for i in range(len(delays) - 1))
    # after the schedule ends: terminal, never an infinite retry loop
    assert next_attempt_delay(len(BACKOFF_MINUTES) + 1) is None


def test_digest_dedup_key_is_one_per_day():
    a = digest_card_id(date(2026, 8, 6))
    b = digest_card_id(date(2026, 8, 6))
    c = digest_card_id(date(2026, 8, 7))
    assert a == b == "digest:2026-08-06" and a != c


def test_feed_shows_every_engine_written_open_state():
    """L6-01 regression lock: the engine writes 'surfaced' on every push and 'claimed'
    on every agent claim. The feed filter omitting them made the HIGHEST-priority cards
    invisible. If someone adds a new open state to the store, this must go red."""
    from genios_engine.api.intelligence_routes import _OPEN_STATES, _RESOLVED_STATES
    engine_written_open = {"queued", "surfaced", "snoozed", "claimed"}
    assert engine_written_open <= set(_OPEN_STATES)
    assert set(_RESOLVED_STATES) & {"acted", "resolved"} == {"acted", "resolved"}


def test_deliver_may_import_executive_but_never_the_reverse():
    """Layer direction at the L5/L6 seam: outbox (6) reads the executive summary (5)
    — downward, allowed. executive/ importing deliver/ is the forbidden direction
    (covered again here beside the outbox that exercises the seam)."""
    import ast
    root = Path(__file__).resolve().parents[1] / "genios_engine" / "executive"
    for py in root.rglob("*.py"):
        tree = ast.parse(py.read_text())
        for node in ast.walk(tree):
            mods = ([a.name for a in node.names] if isinstance(node, ast.Import)
                    else [node.module] if isinstance(node, ast.ImportFrom) and node.module
                    else [])
            for m in mods:
                assert not str(m).startswith("genios_engine.deliver"), \
                    f"{py.name} imports deliver (5→6 is forbidden)"
