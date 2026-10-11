"""STEP-12 M33 · a file keeps ONE decision — the same advice stands, other advice replaces it, a review
that names no move clears it, and in whichever pack the file's home binds to.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/expert/test_a_file_keeps_one_decision.py -q

Tree `yc2_w27_s12` M33.C1.L-integration.V2.U12 (`reason/domain_shadow.py`), `03` F174 and F175. Measured on
the golden set's first decided re-record (12 Oct): a file's review is redone each time the file moves, and
every new review tore its card down and built it again — F03's *"Write to Rahul Menon directly"* three
times, word for word; F02's file held two open decisions at once, one per pack its home had bound to; and
F57's review of the signed NDA said *nothing*, and the card asking for it stayed open. Now: the file's open
decision is read in every pack; a new review giving the same advice (its mode and its move, word for word)
leaves it standing, its card with it; other advice replaces it in every pack; a review that names no move
now — wait, blocked, find out, nothing — clears it, its card `rule_cleared`; and our own failure clears
nothing. The pass reports the files it decided on the live lane (`decided`), for the pack rules.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import text

from tests.reason.expert.test_a_covered_file_decides_once import (  # noqa: F401 — fixtures
    NOW, _compile, _fund, _open_signals, _write, admitted, world)

pytestmark = pytest.mark.pg

FIRST, SECOND = "ffp-fund-first-review-00000", "ffp-fund-second-review-0000"
OTHER_MOVE = {"who": "the founder", "what": "Ask Arjun when the partner meeting is", "for_whom": "Arjun",
              "by_when": None}


def _status(store, org, signal_id) -> str:
    with store.engine.connect() as c:
        return c.execute(text("select status from signals where org_id = :o and signal_id = :s"),
                         {"o": org, "s": signal_id}).scalar()


def _runs(store, org) -> list[str]:
    with store.engine.connect() as c:
        return [r.trigger_ref for r in c.execute(text(
            "select trigger_ref from reasoning_runs where org_id = :o "
            "   and capability_id = 'expert.file_review' order by evaluation_time, run_id"), {"o": org})]


@pytest.fixture
def expiries(monkeypatch):
    """Every card expiry the pass asks for, with its cause."""
    from genios_engine.platform import card_lifecycle
    seen: list[tuple[str, tuple[str, ...]]] = []
    original = card_lifecycle.expire_cards

    def _spy(conn, *, org_id, cause, signal_ids=(), **kw):
        seen.append((cause, tuple(signal_ids)))
        return original(conn, org_id=org_id, cause=cause, signal_ids=signal_ids, **kw)
    monkeypatch.setattr(card_lifecycle, "expire_cards", _spy)
    return seen


def _first(store, org, registry):
    anchor, _situations, events = _fund(store, org)
    _write(store, org, anchor, FIRST, events)
    counts = _compile(store, org, registry, covered={anchor: FIRST})
    [signal] = _open_signals(store, org, anchor)
    assert counts.get("expert_emitted") == 1 and counts["decided"] == {anchor: FIRST}, counts
    return anchor, events, signal


def test_a_new_review_giving_the_same_advice_leaves_the_files_decision_standing(world, expiries):
    """The file moved and was reviewed again; the review advises the same move in the same words — the
    card stands. The new review is still decided and audited: its run is kept."""
    store, org, registry, _ = world
    anchor, events, first = _first(store, org, registry)
    _write(store, org, anchor, SECOND, events,
           frames={"primary": "a fund two days from its partner meeting", "rivals": ["a check-in"]})
    counts = _compile(store, org, registry, covered={anchor: SECOND}, at=NOW + timedelta(hours=6))
    assert counts.get("expert_standing") == 1 and counts.get("expert_decided") == 1, counts
    assert [s.signal_id for s in _open_signals(store, org, anchor)] == [first.signal_id]
    assert _runs(store, org) == [FIRST, SECOND], "the new review's decision was not audited"
    assert expiries == [] and counts["decided"] == {anchor: SECOND}


@pytest.mark.parametrize("change", [
    {"next_move": OTHER_MOVE},
    {"next_move": {**OTHER_MOVE, "what": "Send Arjun the deck and the quarter's metrics",
                   "by_when": "2026-08-14"}},
    {"next_move": {**OTHER_MOVE, "what": "Send Arjun the deck and the quarter's metrics",
                   "for_whom": "Arjun's partners"}},
], ids=["what", "by_when", "for_whom"])
def test_other_advice_replaces_the_files_decision(world, expiries, change):
    store, org, registry, _ = world
    anchor, events, first = _first(store, org, registry)
    _write(store, org, anchor, SECOND, events, **change)
    counts = _compile(store, org, registry, covered={anchor: SECOND}, at=NOW + timedelta(hours=6))
    [second] = _open_signals(store, org, anchor)
    assert counts.get("expert_emitted") == 1 and second.signal_id != first.signal_id, counts
    assert _status(store, org, first.signal_id) == "expired"
    assert ("replaced", (first.signal_id,)) in expiries


def test_the_same_advice_past_its_window_is_renewed(world):
    """⛔ The negative control for standing: the authority window still rules — a week on, the same
    advice is emitted afresh, as any compiled decision past its window is."""
    from genios_engine.reason.expert import decide as expert
    store, org, registry, _ = world
    anchor, events, first = _first(store, org, registry)
    _write(store, org, anchor, SECOND, events,
           frames={"primary": "a fund two days from its partner meeting", "rivals": ["a check-in"]})
    later = NOW + timedelta(hours=expert.EXPIRY_HOURS + 1)
    counts = _compile(store, org, registry, covered={anchor: SECOND}, at=later)
    [renewed] = _open_signals(store, org, anchor)
    assert counts.get("expert_emitted") == 1 and renewed.signal_id != first.signal_id, counts


@pytest.mark.parametrize("mode, over", [
    ("nothing", {"mode": "nothing", "next_move": None}),
    ("wait", {"mode": "wait", "next_move": None}),
    ("blocked", {"mode": "blocked", "next_move": None}),
    ("find_out", {"mode": "find_out"}),
])
def test_a_review_that_names_no_move_now_clears_the_files_decision(world, expiries, mode, over):
    """F57: the signed NDA came back and the review says there is nothing left to do — the card asking
    for it goes, said: the rule that fired no longer holds."""
    store, org, registry, _ = world
    anchor, events, first = _first(store, org, registry)
    _write(store, org, anchor, SECOND, events, **over)
    counts = _compile(store, org, registry, covered={anchor: SECOND}, at=NOW + timedelta(hours=6))
    assert counts.get("expert_cleared") == 1 and counts.get("expert_nothing_to_emit") == 1, counts
    assert _open_signals(store, org, anchor) == [] and _status(store, org, first.signal_id) == "expired"
    assert expiries == [("rule_cleared", (first.signal_id,))]
    assert counts["decided"] == {anchor: SECOND}, "a review that decides no move still decided its file"


def test_our_own_failure_never_clears_the_founders_card(world, expiries, monkeypatch):
    """A reader that crashed is ours, not a judgment that nothing is needed: the run FAILS and the card
    an earlier review raised stays open."""
    from genios_engine.reason.expert import decide as expert
    store, org, registry, _ = world
    anchor, events, first = _first(store, org, registry)
    _write(store, org, anchor, SECOND, events, mode="nothing", next_move=None)

    def _crash(self, request, prior_results):
        raise RuntimeError("the reader broke")
    monkeypatch.setattr(expert.ReviewReader, "evaluate", _crash)
    counts = _compile(store, org, registry, covered={anchor: SECOND}, at=NOW + timedelta(hours=6))
    assert counts.get("expert_cleared", 0) == 0 and expiries == [], counts
    assert [s.signal_id for s in _open_signals(store, org, anchor)] == [first.signal_id]


def test_a_file_whose_home_moved_to_another_pack_keeps_one_decision(world, expiries, monkeypatch):
    """F02: the file's home situation bound to one domain on Monday and another on Wednesday. Its
    decision is ONE across both packs — the same advice stands where it is; other advice replaces it."""
    from genios_engine.reason import domain_shadow
    store, org, registry, _ = world
    assert domain_shadow._tenant_pack(registry, store, org, "admin") is not None, "the premise"
    anchor, events, first = _first(store, org, registry)
    monkeypatch.setattr(domain_shadow, "_FILES_HOME", domain_shadow._FILES_HOME.replace(
        "s.situation_id, s.domain,", "s.situation_id, 'admin' as domain,"))
    both = frozenset({"founder_office", "admin"})
    _write(store, org, anchor, SECOND, events,
           frames={"primary": "a fund two days from its partner meeting", "rivals": ["a check-in"]})
    same = domain_shadow.shadow_compile(store=store, org_id=org, eval_time=NOW + timedelta(hours=6),
                                        registry=registry, covered={anchor: SECOND}, live_domains=both)
    assert same.get("expert_standing") == 1, same
    assert [s.signal_id for s in _open_signals(store, org, anchor)] == [first.signal_id]
    _write(store, org, anchor, "ffp-fund-third-review-00000", events, next_move=OTHER_MOVE)
    other = domain_shadow.shadow_compile(store=store, org_id=org, eval_time=NOW + timedelta(hours=12),
                                         registry=registry, covered={anchor: "ffp-fund-third-review-00000"},
                                         live_domains=both)
    [moved] = _open_signals(store, org, anchor)
    assert other.get("expert_emitted") == 1 and moved.signal_id != first.signal_id, other
    with store.engine.connect() as c:
        packs = dict(c.execute(text("select signal_id, pack_id from signals where org_id = :o "
                                    "and rule_id = 'file_review'"), {"o": org}).all())
    assert packs[first.signal_id] != packs[moved.signal_id] == "admin", packs
    assert _status(store, org, first.signal_id) == "expired"


def test_only_the_live_lane_reports_what_it_decided(world):
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    _write(store, org, anchor, FIRST, events)
    shadow = _compile(store, org, registry, covered={anchor: FIRST}, live=False)
    assert shadow.get("expert_shadow") == 1 and shadow["decided"] == {}
    live = _compile(store, org, registry, covered={anchor: FIRST}, at=NOW + timedelta(minutes=5))
    assert live["decided"] == {anchor: FIRST}
    unchanged = _compile(store, org, registry, covered={anchor: FIRST}, at=NOW + timedelta(minutes=20))
    assert unchanged.get("expert_unchanged") == 1 and unchanged["decided"] == {anchor: FIRST}, \
        "a decision standing from an earlier pass still decides its file"
    assert _compile(store, org, registry, covered=None, at=NOW + timedelta(minutes=30))["decided"] == {}


def test_a_standing_decision_whose_review_cannot_be_named_is_never_the_same_advice(world):
    """A decision whose run names no review (no trigger) cannot be shown to advise the same: the new
    review's advice replaces it, whatever it says."""
    store, org, registry, _ = world
    anchor, events, first = _first(store, org, registry)
    with store.engine.begin() as c:
        c.execute(text("update reasoning_runs set trigger_ref = null where org_id = :o and run_id = :r"),
                  {"o": org, "r": first.reasoning_run_id})
    _write(store, org, anchor, SECOND, events,
           frames={"primary": "a fund two days from its partner meeting", "rivals": ["a check-in"]})
    counts = _compile(store, org, registry, covered={anchor: SECOND}, at=NOW + timedelta(hours=6))
    [second] = _open_signals(store, org, anchor)
    assert counts.get("expert_emitted") == 1 and second.signal_id != first.signal_id, counts
