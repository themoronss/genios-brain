"""Every captured event that reached no signal must say where it stopped — receipt 44.

⛔ `capture/journey.py` opens on the sentence it exists for, quoted from `qualification.py`:

    a system that discards 92% of what a founder was sent has to be able to answer
    "why did I never see X?" in one query

⛔⛔ And the same module records what it cost to not have the join: *"Every layer kept its half of
that bargain and wrote its refusal down. **Nothing ever joined them.** Measured on the pilot org:
`event_trace` holds 10,840 rows and had NO read surface at all … Of 138 events one support question
was really about, 103 stopped at `s4_esqe short_circuit bulk_headers` and 33 at `llm5_not_business`;
**a founder reading `/qualification/drops` would have found nothing and concluded the events were
lost.**"*

⛔ `journey.event_journey` is the join. **Nothing checked that every event has an answer for it to
render** — which is what this receipt is, and the five derivations below are what keep it from
drifting away from the module it was taken from.
"""
from __future__ import annotations

import re

import pytest

from genios_engine.capture.journey import (_LEDGERS, _PER_SIGNAL_LEDGERS, TRACE_ADVANCING,
                                           TRACE_STOPPING)
from genios_engine.platform import receipt_coverage as RC
from genios_engine.platform.config import get_settings
from genios_engine.platform.receipts import _UNEXPLAINED_EVENT_SQL, receipts

_CLAIM = "every captured event that reached no signal says where it stopped"


def _receipt():
    found = [r for r in receipts("org_probe") if r.claim == _CLAIM]
    assert len(found) == 1, f"expected one receipt for {_CLAIM!r}, got {len(found)}"
    return found[0]


# ── the receipt asks the right question, and can fail ──────────────────────────────────────────

def test_the_receipt_is_correctness_shaped_and_org_filtered():
    r = _receipt()
    assert r.expect(0) is True and r.expect(1) is False
    assert "se.org_id = :org" in r.sql, (
        "one tenant's unanswerable events must not appear on another's readiness page")


def test_the_receipt_counts_events_not_traces():
    sql = " ".join(_receipt().sql.lower().split())
    assert sql.startswith("select count(*) from source_events se"), sql[:80]


def test_the_receipt_points_at_the_tool_that_answers_it():
    """⛔ A receipt that says an answer is missing must say where the answer is rendered, or an
    operator has a number and nowhere to go."""
    assert "journey.event_journey" in _receipt().detail


# ── the five derivations ───────────────────────────────────────────────────────────────────────

def test_the_stopping_actions_come_from_the_module():
    sql = _receipt().sql
    for action in TRACE_STOPPING:
        assert repr(action) in sql, f"{action!r} is in TRACE_STOPPING and not in the receipt"
    for action in TRACE_ADVANCING:
        assert f"'{action}'" not in sql, (
            f"{action!r} ADVANCES an event; counting it as a stop would call every passing event "
            "unexplained")


def test_the_action_vocabulary_matches_what_the_column_documents():
    """⛔ `event_trace.action`'s own comment is `pass | drop | park | emit | short_circuit`. If a
    sixth action ships and joins neither set, this receipt silently stops covering it."""
    import pathlib

    sql = "\n".join(p.read_text(encoding="utf-8")
                    for p in sorted((pathlib.Path(__file__).resolve().parents[2]
                                     / "migrations").glob("*.sql")))
    comment = re.search(r"action\s+text not null,\s*--\s*([a-z |_]+)", sql)
    assert comment, "the action column's documented vocabulary is gone"
    documented = {w.strip() for w in comment.group(1).split("|") if w.strip()}
    assert documented == set(TRACE_ADVANCING) | set(TRACE_STOPPING), (
        f"the column documents {sorted(documented)} and the module partitions "
        f"{sorted(set(TRACE_ADVANCING) | set(TRACE_STOPPING))}")


def test_the_event_keyed_ledgers_come_from_the_declared_tuple():
    sql = _receipt().sql
    # ⛔ THE NON-EMPTY ASSERTIONS COME FIRST, AND A MUTATION TAUGHT ME WHY. Emptying
    # `_PER_SIGNAL_LEDGERS` made the loop below run zero times and the test passed while the
    # per-signal tables flowed into an event-keyed query. *An empty collection makes an assertion
    # over it vacuous* — the same defect as a gate that can never be red.
    assert _LEDGERS, "`journey._LEDGERS` is empty; this receipt derives everything from it"
    assert _PER_SIGNAL_LEDGERS, (
        "⛔ `journey._PER_SIGNAL_LEDGERS` is empty. The module declares that distinction because a "
        "per-signal refusal cannot name an event that never produced a signal — without it this "
        "receipt would require a row in a table the event can never reach, and call every "
        "unqualified event unexplained")
    event_keyed = [name for name, _ in _LEDGERS if name not in _PER_SIGNAL_LEDGERS]
    assert event_keyed, "no event-keyed ledger left in `_LEDGERS`"
    for name in event_keyed:
        assert name in sql, f"{name} is event-keyed in `_LEDGERS` and missing from the receipt"
    for name in _PER_SIGNAL_LEDGERS:
        assert name not in sql, (
            f"⛔ {name} is per-SIGNAL. An event that never produced a signal cannot appear in it, "
            "so requiring a row there would call every unqualified event unexplained")
    # ⛔ And the known members by name, so emptying either set is caught by this test and not only
    # by the builder's own assertion.
    assert "qualification_drops" not in sql and "publication_rejections" not in sql


def test_the_horizon_is_four_declared_sweep_ticks():
    """⛔ The multiplier is the one judgement in the query, and the interval it multiplies is
    `platform/config.sync_interval_hours` — *"how often the sweep TICKS"*."""
    hours = 4 * float(get_settings().sync_interval_hours or 6.0)
    assert f"make_interval(hours => {hours:g})" in _receipt().sql
    assert hours >= 12, (
        "fewer than twelve hours of horizon starts counting events that are still mid-flight")


def test_the_receipt_is_declared_under_capture():
    package, why = RC.RECEIPT_PACKAGE[_CLAIM]
    assert package == "capture"
    assert "journey.py" in why and "narrower question" in why, (
        "the declaration must say how this differs from the sibling drop receipt, or the two read "
        "as duplicates")


# ── the builder refuses to guess when its source changes ───────────────────────────────────────

def test_the_builder_refuses_a_tuple_without_the_success_ledger(monkeypatch):
    import genios_engine.capture.journey as J

    monkeypatch.setattr(J, "_LEDGERS", (("parked_events", "created_at"),), raising=True)
    with pytest.raises(AssertionError, match="no longer carries the success ledger"):
        _UNEXPLAINED_EVENT_SQL("org_probe")


def test_the_builder_refuses_a_world_with_no_event_keyed_refusal(monkeypatch):
    """⛔ If every refusal becomes per-signal, an event that produced no signal has nowhere to be
    recorded — a bigger finding than this receipt, and the builder says so rather than emitting a
    query that would be green by construction."""
    import genios_engine.capture.journey as J

    monkeypatch.setattr(J, "_LEDGERS", (("qualified_signals", "created_at"),), raising=True)
    monkeypatch.setattr(J, "_PER_SIGNAL_LEDGERS", frozenset(), raising=True)
    with pytest.raises(AssertionError, match="no event-keyed refusal ledger"):
        _UNEXPLAINED_EVENT_SQL("org_probe")


# ── and the sentence the claim is taken from is still there ─────────────────────────────────────

def test_the_module_still_says_what_the_receipt_quotes():
    """⛔ A claim about PROSE needs attribution: the receipt is built on `journey.py`'s opening
    sentence, so the sentence is checked rather than remembered."""
    import pathlib

    src = (pathlib.Path(__file__).resolve().parents[2]
           / "genios_engine" / "capture" / "journey.py").read_text(encoding="utf-8")
    assert 'why did I never see X?' in src
    assert "Nothing ever joined them" in src


def test_the_sibling_drop_receipt_still_asks_its_narrower_question():
    """The two must stay distinguishable: that one is about reviewing a model's JUDGMENT, this one
    about an answer existing at all."""
    sibling = [r for r in receipts("org_probe")
               if r.claim == "every drop we might be wrong about can still be reviewed"]
    assert len(sibling) == 1
    assert "raw_payloads" in sibling[0].sql, (
        "the sibling stopped being about a deleted body; if it has widened into this receipt's "
        "question, one of the two is now redundant")
