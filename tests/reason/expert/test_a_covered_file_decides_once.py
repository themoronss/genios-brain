"""STEP-12 M33 · a covered file decides once — its situations stand down, its review is its signal.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/expert/test_a_covered_file_decides_once.py -q

Tree `yc2_w27_s12` M33.C1.L-integration.V1.U02 (`reason/domain_shadow.py`), under `06` D1. The compiled
lane is handed the files a VALID review now answers (`covered`, the expert pass's receipt). Each is
decided ONCE, from its review (`reason/expert/decide`) — no decider, no R-1 — persisted as an audited
run and emitted as the file's own signal, its anchor the subject, the delivery authority's to show.
Every situation of the file whose events the review saw stands down (its end `decided`,
`covered_by_review`), and a signal one of them left open is replaced. A situation resting on an event
the review never saw keeps its own decision. The same review decides nothing again; a new one replaces
the file's signal; a review that needs nothing emits nothing; on the shadow lane nothing is written.

The world is STEP-11's (`tests/reason/test_a_programme_is_not_decided_as_an_investor`): a founder with
a fund's mail and a programme's, the Founder Office on, the investor capability admitted in a test
corpus — so a situation that does NOT stand down is decided on today's path, not refused.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.contracts.expert_review import ExpertReview
from genios_engine.reason.expert import store as R
from tests.reason.expert.checks import as_written
from tests.reason.test_a_programme_is_not_decided_as_an_investor import (  # noqa: F401 — a fixture
    FUND, NOW, PROGRAMME, _by_counterparty, _tenant, admitted)

pytestmark = pytest.mark.pg


def _review(event_id: str, **over) -> dict:
    raw = {
        "facts": [{"claim": "Arjun asked for the deck and the quarter's metrics", "evidence": [event_id]}],
        "frames": {"primary": "a fund preparing a partner meeting", "rivals": ["a polite check-in"]},
        "expected_vs_actual": {"stage": None, "expected": "the deck before the meeting",
                               "actual": "nothing sent yet"},
        "scenarios": {"do_nothing": "the partner meeting goes ahead without our numbers",
                      "act": "the partners read the deck first", "best": "a term sheet",
                      "worst": "a pass", "signals_to_watch": ["a reply from Arjun"]},
        "appraisal": {"stakes": "high", "urgency": "high", "reversibility": "reversible",
                      "reasons": ["the partner meeting is next"]},
        "mode": "act",
        "next_move": {"who": "the founder", "what": "Send Arjun the deck and the quarter's metrics",
                      "for_whom": "Arjun", "by_when": None},
        "alternative": "offer a short call to walk through them", "wait_or_stop": "if no reply, ask once",
        "done_when": "Arjun has the deck and the metrics",
        "draft": "Hi Arjun, attached are the deck and last quarter's metrics."}
    raw.update(over)
    return raw


def _fund(store, org: str) -> tuple[str, set[str], set[str]]:
    """The fund's file: its anchor, its situations, and every event behind them."""
    situations = _by_counterparty(store, org)[FUND]
    with store.engine.connect() as c:
        rows = c.execute(text(
            "select s.anchor_node_id, m.event_id from context_situations s "
            "  join context_correlation_members m on m.org_id = s.org_id "
            "       and m.correlation_id = s.correlation_id "
            " where s.org_id = :o and s.situation_id = any(:s)"), {"o": org, "s": list(situations)}).all()
    anchors = {r.anchor_node_id for r in rows}
    assert len(anchors) == 1, anchors
    return anchors.pop(), situations, {r.event_id for r in rows}


def _write(store, org: str, file_id: str, fingerprint: str, events, **over) -> None:
    # STEP-13: a review decides only through its check — here the check of one that stands whole
    # (`tests/reason/expert/checks.as_written`); this file's subject is the decision, not the check.
    review = ExpertReview.from_mapping(_review(sorted(events)[0], **over))
    with store.engine.begin() as c:
        assert R.write_review(c, org_id=org, file_id=file_id, fingerprint=fingerprint,
                              model="claude-sonnet-5", prompt_version="expert-review.v2",
                              dossier_digest="d" * 64, status=R.VALID, reason=None,
                              review=review, input_tokens=10, output_tokens=10,
                              cost_micro_usd=1, at=NOW, inputs={"events": sorted(events), "booked": []},
                              triggers=[{"kind": "first_look", "says": "never judged"}],
                              checked=as_written(review))


@pytest.fixture
def world(pg_store, admitted, monkeypatch, request):
    """The tenant, the investor capability admitted, and every reasoning call recorded by anchor."""
    from genios_engine.reason import domain_shadow
    org = f"m33u02_{request.node.name[5:30]}"
    registry = _tenant(pg_store, org)
    monkeypatch.setattr(domain_shadow, "expert_catalog", lambda: admitted)
    reasoned: list[str] = []
    original = domain_shadow.reason_native_capability

    def _recorded(**kw):
        reasoned.append(kw["context"].node_id)
        return original(**kw)
    monkeypatch.setattr(domain_shadow, "reason_native_capability", _recorded)
    return pg_store, org, registry, reasoned


def _compile(store, org, registry, *, covered, at=NOW, live=True):
    from genios_engine.reason import domain_shadow
    return domain_shadow.shadow_compile(
        store=store, org_id=org, eval_time=at, registry=registry, covered=covered,
        live_domains=frozenset({"founder_office"}) if live else frozenset())


def _open_signals(store, org, node):
    with store.engine.connect() as c:
        return c.execute(text(
            "select signal_id, rule_id, capability_id, play, output_lane, situation_id, level, "
            "       reasoning_run_id from signals where org_id = :o and subject_node_id = :n "
            "   and status = 'open' order by signal_id"), {"o": org, "n": node}).all()


def _authoritative(store, org, at) -> set[str]:
    """What the delivery authority would build a card from — `reason/authority.py`, verbatim."""
    from genios_engine.reason.authority import (AUTHORITATIVE_SIGNAL_JOINS,
                                                AUTHORITATIVE_SIGNAL_PREDICATE)
    with store.engine.connect() as c:
        return {r.signal_id for r in c.execute(text(
            "select s.signal_id from signals s " + AUTHORITATIVE_SIGNAL_JOINS +
            " where s.org_id = :o and " + AUTHORITATIVE_SIGNAL_PREDICATE),
            {"o": org, "authority_time": at})}


def test_a_covered_file_decides_once_and_its_situations_stand_down(world, monkeypatch):
    from genios_engine.reason import llm_decision_maker
    store, org, registry, reasoned = world
    anchor, situations, events = _fund(store, org)
    _write(store, org, anchor, "ffp-fund-first-review-00000", events)

    def _never(*a, **kw):
        raise AssertionError("the decider was asked about a covered file")
    monkeypatch.setattr(llm_decision_maker, "enabled_for", lambda org_id: True)
    monkeypatch.setattr(llm_decision_maker, "decide_with_llm", _never)
    counts = _compile(store, org, registry, covered={anchor: "ffp-fund-first-review-00000"})

    assert anchor not in reasoned, "a covered file's situation reached the decider's path"
    assert counts["covered_files"] == 1 and counts["covered_situations"] == len(situations)
    assert counts["expert_decided"] == 1 and counts.get("expert_emitted") == 1, counts
    [signal] = _open_signals(store, org, anchor)
    assert (signal.rule_id, signal.capability_id, signal.play, signal.output_lane, signal.level) == (
        "file_review", "expert.file_review", "expert.next_move", "decision", "prescriptive")
    assert signal.situation_id in situations
    assert signal.signal_id in _authoritative(store, org, NOW), "delivery would never show it"
    with store.engine.connect() as c:
        run = c.execute(text("select capability_id, mode, trigger_ref from reasoning_runs "
                             " where org_id = :o and run_id = :r"),
                        {"o": org, "r": signal.reasoning_run_id}).one()
        ends = {r.situation_id: (r.outcome, r.reason) for r in c.execute(text(
            "select situation_id, outcome, reason from situation_outcomes where org_id = :o"),
            {"o": org})}
    assert tuple(run) == ("expert.file_review", "live", "ffp-fund-first-review-00000")
    assert all(ends[s] == ("decided", "covered_by_review") for s in situations), ends


def test_the_same_review_decides_nothing_again(world):
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    _write(store, org, anchor, "ffp-fund-first-review-00000", events)
    covered = {anchor: "ffp-fund-first-review-00000"}
    _compile(store, org, registry, covered=covered)
    [first] = _open_signals(store, org, anchor)
    again = _compile(store, org, registry, covered=covered, at=NOW + timedelta(minutes=15))
    assert again.get("expert_unchanged") == 1 and again.get("expert_decided", 0) == 0, again
    assert [s.signal_id for s in _open_signals(store, org, anchor)] == [first.signal_id]


def test_the_same_review_decided_again_leaves_its_signal_standing(world):
    """When the gate has no memory of it — a lost write, a renewal — the same review is decided again,
    and the advice it already gave stands: no card is torn down and rebuilt for words that did not
    change."""
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    _write(store, org, anchor, "ffp-fund-first-review-00000", events)
    covered = {anchor: "ffp-fund-first-review-00000"}
    _compile(store, org, registry, covered=covered)
    [first] = _open_signals(store, org, anchor)
    with store.engine.begin() as c:
        c.execute(text("delete from reasoning_fingerprints where org_id = :o"), {"o": org})
    again = _compile(store, org, registry, covered=covered, at=NOW + timedelta(minutes=15))
    assert again.get("expert_standing") == 1 and again.get("expert_decided") == 1, again
    assert [s.signal_id for s in _open_signals(store, org, anchor)] == [first.signal_id]


def test_a_new_review_replaces_the_files_signal(world):
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    _write(store, org, anchor, "ffp-fund-first-review-00000", events)
    _compile(store, org, registry, covered={anchor: "ffp-fund-first-review-00000"})
    [first] = _open_signals(store, org, anchor)
    _write(store, org, anchor, "ffp-fund-second-review-0000", events,
           next_move={"who": "the founder", "what": "Ask Arjun when the partner meeting is",
                      "for_whom": "Arjun", "by_when": None})
    counts = _compile(store, org, registry, covered={anchor: "ffp-fund-second-review-0000"},
                      at=NOW + timedelta(minutes=15))
    [second] = _open_signals(store, org, anchor)
    assert counts.get("expert_emitted") == 1 and second.signal_id != first.signal_id
    with store.engine.connect() as c:
        status = c.execute(text("select status from signals where org_id = :o and signal_id = :s"),
                           {"o": org, "s": first.signal_id}).scalar()
        trigger = c.execute(text("select trigger_ref from reasoning_runs where org_id = :o "
                                 "and run_id = :r"), {"o": org, "r": second.reasoning_run_id}).scalar()
    assert status == "expired" and trigger == "ffp-fund-second-review-0000"


def test_a_situation_the_review_never_saw_keeps_its_own_decision(world):
    store, org, registry, reasoned = world
    anchor, situations, events = _fund(store, org)
    _write(store, org, anchor, "ffp-fund-blind-review-00000", ["evt_some_other_mail"])
    counts = _compile(store, org, registry, covered={anchor: "ffp-fund-blind-review-00000"})
    assert counts.get("covered_situations", 0) == 0 and anchor in reasoned
    assert counts["expert_decided"] == 1, "the file is still decided from its review"


def test_the_signals_its_situations_left_open_are_replaced(world):
    store, org, registry, _ = world
    anchor, situations, events = _fund(store, org)
    before = _compile(store, org, registry, covered=None)                  # today's path first
    left = [s for s in _open_signals(store, org, anchor) if s.situation_id in situations]
    assert left and before.get("emitted"), before
    _write(store, org, anchor, "ffp-fund-first-review-00000", events)
    counts = _compile(store, org, registry, covered={anchor: "ffp-fund-first-review-00000"},
                      at=NOW + timedelta(minutes=15))
    assert counts["covered_signals_replaced"] == len(left)
    assert [s.rule_id for s in _open_signals(store, org, anchor)] == ["file_review"]


def test_a_review_that_needs_nothing_emits_nothing_and_still_decides_the_file(world):
    store, org, registry, reasoned = world
    anchor, situations, events = _fund(store, org)
    _write(store, org, anchor, "ffp-fund-nothing-review-000", events, mode="nothing", next_move=None)
    counts = _compile(store, org, registry, covered={anchor: "ffp-fund-nothing-review-000"})
    assert counts.get("expert_nothing_to_emit") == 1 and counts["covered_situations"] == len(situations)
    assert _open_signals(store, org, anchor) == [] and anchor not in reasoned


def test_a_review_that_must_find_out_first_is_audited_and_emits_no_decision(world):
    """A question must be answered before anyone moves: the decision is audited (INSUFFICIENT_CONTEXT,
    the Investigation lane) and no DECISION is emitted. ⛔ RESTATED by STEP-13 (`yc2_w27_s13`
    M36.C2.L-integration.V2.U03), whose question this always was: the file now asks it — its one open
    signal is the question's, authorised as a question and never as a decision
    (`tests/reason/expert/test_a_held_file_asks.py`)."""
    store, org, registry, reasoned = world
    anchor, situations, events = _fund(store, org)
    _write(store, org, anchor, "ffp-fund-findout-review-000", events, mode="find_out")
    counts = _compile(store, org, registry, covered={anchor: "ffp-fund-findout-review-000"})
    assert counts.get("expert_nothing_to_emit") == 1 and counts["covered_situations"] == len(situations)
    assert [s.rule_id for s in _open_signals(store, org, anchor)] == ["founder_question"]
    assert _authoritative(store, org, NOW) == set() and anchor not in reasoned
    with store.engine.connect() as c:
        outcome = c.execute(text(
            "select o.outcome_kind from reasoning_runs r join reasoning_run_outputs o "
            "  on o.org_id = r.org_id and o.run_id = r.run_id "
            " where r.org_id = :o and r.capability_id = 'expert.file_review'"), {"o": org}).scalar()
    assert outcome == "insufficient_context"


def test_on_the_shadow_lane_the_file_is_decided_and_nothing_is_written(world):
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    _write(store, org, anchor, "ffp-fund-first-review-00000", events)
    counts = _compile(store, org, registry, covered={anchor: "ffp-fund-first-review-00000"}, live=False)
    assert counts.get("expert_shadow") == 1 and _open_signals(store, org, anchor) == []
    with store.engine.connect() as c:
        assert c.execute(text("select count(*) from reasoning_runs where org_id = :o "
                              "and capability_id = 'expert.file_review'"), {"o": org}).scalar() == 0


def test_a_review_that_is_not_valid_covers_nothing(world):
    """Only a valid review may be read for a decision: a refused one handed over by mistake stands no
    situation down — the file is decided on today's path, situation by situation."""
    store, org, registry, reasoned = world
    anchor, _situations, events = _fund(store, org)
    with store.engine.begin() as c:
        assert R.write_review(c, org_id=org, file_id=anchor, fingerprint="ffp-fund-refused-review-000",
                              model="claude-sonnet-5", prompt_version="expert-review.v2",
                              dossier_digest="d" * 64, status=R.REFUSED, reason="uncited_fact",
                              review=None, input_tokens=1, output_tokens=1, cost_micro_usd=1, at=NOW,
                              inputs={"events": sorted(events)}, triggers=[{"kind": "first_look",
                                                                            "says": "never judged"}])
    counts = _compile(store, org, registry, covered={anchor: "ffp-fund-refused-review-000"})
    assert counts["covered_files"] == 0 and counts.get("covered_situations", 0) == 0
    assert anchor in reasoned and "expert_decided" not in counts


def test_without_coverage_the_pass_is_as_it_was(world):
    """⛔ THE NEGATIVE CONTROL: the same tenant, the same stored review, nothing handed over — the fund's
    situation is reasoned on today's path and nothing is the expert's."""
    store, org, registry, reasoned = world
    anchor, _situations, events = _fund(store, org)
    _write(store, org, anchor, "ffp-fund-first-review-00000", events)
    counts = _compile(store, org, registry, covered=None)
    assert anchor in reasoned and counts["covered_files"] == 0 and "expert_decided" not in counts
    assert all(s.rule_id != "file_review" for s in _open_signals(store, org, anchor))


# ── STEP-13 · M35.C3.L-integration.V2.U02 — the file is decided through its review's check ──────────
def test_the_same_review_checked_again_under_a_new_check_is_decided_again(world):
    """The change gate keys the check's version: a review checked again under a new check is a new
    judgment of the same review, and the file is decided again — never skipped on the old one."""
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    _write(store, org, anchor, "ffp-fund-first-review-00000", events)
    covered = {anchor: "ffp-fund-first-review-00000"}
    _compile(store, org, registry, covered=covered)
    with store.engine.begin() as c:
        c.execute(text("update expert_reviews set checked = jsonb_set(checked, '{version}', '\"check.v2\"') "
                       "where org_id = :o"), {"o": org})
    again = _compile(store, org, registry, covered=covered, at=NOW + timedelta(minutes=15))
    assert again.get("expert_unchanged", 0) == 0 and again.get("expert_decided") == 1, again


def test_the_advice_a_card_gave_is_what_the_check_let_stand():
    """Two reviews give the same advice when their CHECKED mode and move agree (`_same_advice`): a
    move the check corrected is the corrected move; a held move shows none; no check, no advice."""
    from types import SimpleNamespace

    import genios_engine.contracts.claim_check as C
    from genios_engine.reason.domain_shadow import _advice
    review = ExpertReview.from_mapping(_review("evt_1"))
    shown = as_written(review)
    move = review.next_move
    assert _advice(SimpleNamespace(review=review, checked=shown)) == (
        review.mode, (move.who, move.what, move.for_whom, move.by_when))
    corrected = C.CheckedReview(verdicts=shown.verdicts, fate=C.SHOWN, cited=shown.cited,
                                words=C.CardWords(headline="Send the deck by 4 Aug", situation="s",
                                                  done_when="d", draft=None, to=None))
    assert _advice(SimpleNamespace(review=review, checked=corrected))[1][1] == "Send the deck by 4 Aug"
    held = C.CheckedReview(verdicts=(), fate=C.HELD, cited=shown.cited, question="Is it so?",
                           because="fact:1 unquoted (fact 1)", words=C.CardWords(None, "s", "d", None, None))
    assert _advice(SimpleNamespace(review=review, checked=held)) == ("find_out", None)
    assert _advice(SimpleNamespace(review=review, checked=None)) == (None, None)
