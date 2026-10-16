"""L6 outbox — retry policy is pure and bounded; delivery is state, not hope.
And the L6-01 lock: every state the engine writes is visible in the feed."""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

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


def test_digest_payload_is_regenerated_from_the_kept_brief_at_send_time(monkeypatch):
    """The digest is regenerated at send time from current authority — and since STEP-15 (M45.C3.L-integration.V0.U03) that
    authority is the morning brief the account owner's seat KEPT: its one line and today's five, read for the local day
    the row was queued for, never rebuilt from signals (`summary.build_summary`, the count it used to send)."""
    now = datetime(2026, 8, 6, 8, 30, tzinfo=timezone.utc)
    brief = SimpleNamespace(
        one_line="2 things need you.", local_date=date(2026, 8, 6),
        section=lambda name: ([SimpleNamespace(words="Bluepeak: Write to Meera."),
                               SimpleNamespace(words="Fjord: Wait for the milestone.")] if name == "today" else []))
    calls = []
    monkeypatch.setattr(
        "genios_engine.executive.morning.kept_brief",
        lambda engine, org_id, *, now, local_date=None: calls.append((engine, org_id, now, local_date)) or brief)
    monkeypatch.setattr(
        "genios_engine.deliver.outbox.format_digest_message", lambda value: value)
    monkeypatch.setattr("genios_engine.executive.summary.build_summary",
                        lambda *a, **k: pytest.fail("the digest is the kept brief, not the signal count"))
    engine = object()

    assert _current_digest_payload(engine, "org_1", now, for_date=date(2026, 8, 6)) == {
        "one_line": "2 things need you.",
        "top_items": [{"line": "Bluepeak: Write to Meera."}, {"line": "Fjord: Wait for the milestone."}]}
    assert calls == [(engine, "org_1", now, date(2026, 8, 6))]
    # No brief kept for the day: it RAISES — the drain retries on its backoff, and never sends a fallback.
    monkeypatch.setattr("genios_engine.executive.morning.kept_brief", lambda *a, **k: None)
    with pytest.raises(LookupError, match="no morning brief"):
        _current_digest_payload(engine, "org_1", now)


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
