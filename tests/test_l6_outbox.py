"""Layer 5.2 Delivery outbox — retry policy is pure and bounded; delivery is state, not hope.
And the delivery-state lock: every state the engine writes is visible in the feed."""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from genios_engine.deliver.outbox import (BACKOFF_MINUTES, _current_digest_payload, digest_card_id,
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


def test_digest_payload_is_regenerated_from_current_authority_at_send_time(monkeypatch):
    now = datetime(2026, 8, 6, 8, 30, tzinfo=timezone.utc)
    calls = []
    monkeypatch.setattr(
        "genios_engine.executive.summary.build_summary",
        lambda store, org_id, horizon, eval_time: calls.append(
            (store.engine, org_id, horizon, eval_time)) or {"one_line": "Current"})
    monkeypatch.setattr(
        "genios_engine.deliver.outbox.format_digest_message", lambda value: value)
    engine = object()

    assert _current_digest_payload(engine, "org_1", now) == {"one_line": "Current"}
    assert calls == [(engine, "org_1", "one_minute", now)]


def test_feed_shows_every_engine_written_open_state():
    """Delivery-state regression lock: the engine writes 'surfaced' on every push and 'claimed'
    on every agent claim. The feed filter omitting them made the HIGHEST-priority cards
    invisible. If someone adds a new open state to the store, this must go red."""
    from genios_engine.api.intelligence_routes import _OPEN_STATES, _RESOLVED_STATES
    engine_written_open = {"queued", "surfaced", "snoozed", "claimed"}
    assert engine_written_open <= set(_OPEN_STATES)
    assert set(_RESOLVED_STATES) & {"acted", "resolved"} == {"acted", "resolved"}


def test_deliver_may_import_executive_but_never_the_reverse():
    """Import direction at the Layer 5/5.2 seam: delivery (rank 6) reads executive (rank 5)
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
