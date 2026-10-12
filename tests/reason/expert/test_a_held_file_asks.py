"""STEP-13 · a held file asks you its one question — and a decision retires it.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/reason/expert/test_a_held_file_asks.py

Tree `yc2_w27_s13` M36.C2.L-integration.V2.U03 (`reason/domain_shadow`; STEP-13 §8.4 item 7, `06` D60, `03`
F184). A covered file decided INSUFFICIENT on its answer — its review's move held by the check, or a review
that must find out first — files its question (`context/founder_questions`, by the run that asked it) and
its question signal: the Investigation lane, bound to that run, no candidate, authorised as a question
(`reason/authority.QUESTION_SIGNAL_PREDICATE`) and never as a decision. The same question asked again is
the one already open — its signal re-bound to the run that asks it now, never rebuilt; a new question
replaces the old one, its card with it; any other decision retires the file's question and its signal.
The shadow lane asks nothing.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.context import founder_questions as Q
from genios_engine.contracts import claim_check as C
from genios_engine.contracts.expert_review import ExpertReview
from genios_engine.reason.authority import QUESTION_SIGNAL_JOINS, QUESTION_SIGNAL_PREDICATE
from genios_engine.reason.expert import asks
from genios_engine.reason.expert import store as R
from tests.reason.expert import check_world as W
from tests.reason.expert.checks import as_written
from tests.reason.expert.test_a_covered_file_decides_once import (  # noqa: F401 — fixtures
    NOW, _authoritative, _compile, _fund, _open_signals, _review, world)
from tests.reason.test_a_programme_is_not_decided_as_an_investor import admitted  # noqa: F401

pytestmark = pytest.mark.pg

FIND_OUT = "Did Arjun ask for last quarter's metrics or this quarter's?"
HELD_Q = "Is it so: “Arjun asked for the deck and the quarter's metrics”? It is not in what it cites."


def _write(store, org, file_id, fingerprint, events, *, checked=None, **over):
    review = ExpertReview.from_mapping(_review(sorted(events)[0], **over))
    with store.engine.begin() as c:
        assert R.write_review(c, org_id=org, file_id=file_id, fingerprint=fingerprint, model="claude-sonnet-5",
                              prompt_version="expert-review.v3", dossier_digest="d" * 64, status=R.VALID,
                              reason=None, review=review, input_tokens=10, output_tokens=10, cost_micro_usd=1,
                              at=NOW, inputs={"events": sorted(events), "booked": []},
                              triggers=[{"kind": "first_look", "says": "never judged"}],
                              checked=checked or as_written(review))
    return review


def _find_out(store, org, anchor, fp, events, question=FIND_OUT):
    return _write(store, org, anchor, fp, events, mode="find_out", draft=None,
                  next_move={"who": "you", "what": question, "for_whom": "Arjun", "by_when": None})


def _held(review) -> C.CheckedReview:
    shown = as_written(review)
    return C.CheckedReview(verdicts=(C.LineVerdict("fact:1", C.DROPPED, C.MISQUOTED, "the deck"),),
                           fate=C.HELD, cited=(), question=HELD_Q, because="misquoted (fact 1)",
                           words=C.CardWords(None, shown.words.situation, shown.words.done_when, None, None))


def _questions(store, org, file_id):
    with store.engine.connect() as c:
        return c.execute(text("select question_id, question, why, state, run_id, retired_why from "
                              "founder_questions where org_id = :o and file_id = :f order by asked_at, "
                              "question_id"), {"o": org, "f": file_id}).all()


def _asking(store, org, at=NOW) -> list[str]:
    with store.engine.connect() as c:
        return [r[0] for r in c.execute(text(
            "select s.signal_id from signals s " + QUESTION_SIGNAL_JOINS +
            " where s.org_id = :o and s.status = 'open' and " + QUESTION_SIGNAL_PREDICATE),
            {"o": org, "authority_time": at})]


def test_a_file_that_must_find_out_first_asks_you_its_question(world):
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    _find_out(store, org, anchor, "ffp-fund-findout-review-000", events)
    counts = _compile(store, org, registry, covered={anchor: "ffp-fund-findout-review-000"})
    assert counts.get("expert_question_asked") == 1, counts
    assert counts.get("needs_refused") == 1, "the needs queue is read once a pass — and, unwired, refuses"
    [q] = _questions(store, org, anchor)
    assert (q.question, q.state) == (FIND_OUT, Q.OPEN) and q.run_id
    [signal] = _open_signals(store, org, anchor)
    assert (signal.rule_id, signal.output_lane, signal.reasoning_run_id) == (
        "founder_question", "investigation", q.run_id)
    assert _asking(store, org) == [signal.signal_id]
    assert _authoritative(store, org, NOW) == set(), "never a decision: it selects no move"


def test_a_held_review_asks_the_question_its_check_asked(world):
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    review = ExpertReview.from_mapping(_review(sorted(events)[0]))
    _write(store, org, anchor, "ffp-fund-held-review-00000", events, checked=_held(review))
    _compile(store, org, registry, covered={anchor: "ffp-fund-held-review-00000"})
    [q] = _questions(store, org, anchor)
    # ⛔ RESTATED by M36.C2.L-logic.V2.U10 (`03` X10): the `why` was the check's internal reason string
    # ("misquoted (fact 1)"), which the card showed as its `because`. It is a closed, founder-facing phrase.
    assert (q.question, q.why, q.state) == (HELD_Q, asks.WHY_NOT_CONFIRMED, Q.OPEN)
    assert len(_asking(store, org)) == 1


def test_the_same_question_asked_again_is_rebound_never_rebuilt(world):
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    _find_out(store, org, anchor, "ffp-fund-findout-review-000", events)
    covered = {anchor: "ffp-fund-findout-review-000"}
    _compile(store, org, registry, covered=covered)
    [first] = _open_signals(store, org, anchor)
    with store.engine.begin() as c:            # the gate has no memory of it: decided again
        c.execute(text("delete from reasoning_fingerprints where org_id = :o"), {"o": org})
    again = _compile(store, org, registry, covered=covered, at=NOW + timedelta(hours=30))
    assert again.get("expert_question_standing") == 1, again
    [q] = _questions(store, org, anchor)
    [now] = _open_signals(store, org, anchor)
    assert now.signal_id == first.signal_id, "its card is not torn down and rebuilt"
    assert now.reasoning_run_id == q.run_id != first.reasoning_run_id, "re-bound to the run asking now"
    assert _asking(store, org, at=NOW + timedelta(hours=30)) == [first.signal_id]


def test_a_new_question_replaces_the_old_one_and_its_card(world):
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    _find_out(store, org, anchor, "ffp-fund-findout-review-000", events)
    _compile(store, org, registry, covered={anchor: "ffp-fund-findout-review-000"})
    [old_signal] = _open_signals(store, org, anchor)
    _find_out(store, org, anchor, "ffp-fund-findout-review-001", events, question="Who at the fund decides?")
    _compile(store, org, registry, covered={anchor: "ffp-fund-findout-review-001"},
             at=NOW + timedelta(hours=1))
    old, new = _questions(store, org, anchor)
    assert (old.state, old.retired_why) == (Q.RETIRED, Q.REPLACED) and new.state == Q.OPEN
    [signal] = _open_signals(store, org, anchor)
    assert signal.signal_id != old_signal.signal_id and _asking(store, org, at=NOW + timedelta(hours=1)) == [
        signal.signal_id]


def test_a_decision_retires_the_files_question(world):
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    _find_out(store, org, anchor, "ffp-fund-findout-review-000", events)
    _compile(store, org, registry, covered={anchor: "ffp-fund-findout-review-000"})
    _write(store, org, anchor, "ffp-fund-act-review-000000", events)
    counts = _compile(store, org, registry, covered={anchor: "ffp-fund-act-review-000000"},
                      at=NOW + timedelta(hours=1))
    assert counts.get("expert_question_retired") == 1, counts
    [q] = _questions(store, org, anchor)
    assert (q.state, q.retired_why) == (Q.RETIRED, Q.NO_LONGER_ASKED)
    assert [s.rule_id for s in _open_signals(store, org, anchor)] == ["file_review"], "the decision's own"
    assert _asking(store, org, at=NOW + timedelta(hours=1)) == []


def test_on_the_shadow_lane_nothing_is_asked(world):
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    _find_out(store, org, anchor, "ffp-fund-findout-review-000", events)
    _compile(store, org, registry, covered={anchor: "ffp-fund-findout-review-000"}, live=False)
    assert _questions(store, org, anchor) == [] and _open_signals(store, org, anchor) == []


def test_a_question_you_answered_is_not_asked_again_by_a_later_review(world):
    """⛔ `03` X25 (M36.C2.L-data.V2.U12): your answer moves the file's fingerprint, so the review that asks the
    same words next is a new review. It asks nothing: no signal is filed for words you answered, and the
    file's open question signal expires — `answered_already`, counted."""
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    _find_out(store, org, anchor, "ffp-fund-findout-review-000", events)
    _compile(store, org, registry, covered={anchor: "ffp-fund-findout-review-000"})
    [asked] = _questions(store, org, anchor)
    with store.engine.begin() as c:
        Q.answer(c, org_id=org, question_id=asked.question_id, words="This quarter's.", by="u",
                 at=NOW + timedelta(hours=1))
    _find_out(store, org, anchor, "ffp-fund-findout-review-001", events)
    later = NOW + timedelta(hours=2)
    counts = _compile(store, org, registry, covered={anchor: "ffp-fund-findout-review-001"}, at=later)
    assert counts.get("expert_question_answered_already") == 1, counts
    assert counts.get("expert_question_asked", 0) == 0 and counts.get("expert_question_standing", 0) == 0
    assert [(q.question_id, q.state) for q in _questions(store, org, anchor)] == [(asked.question_id, Q.ANSWERED)]
    assert _open_signals(store, org, anchor) == [], "no signal for words you answered"
    assert _asking(store, org, at=later) == []


# ── M36.C2.L-logic.V2.U10 · the question is asked in checked words (`03` X06, X10, X34) ─────────────────────────
#
# Pure: `asks.question_words` over a review and its real check (`reason/expert/verify.check_review`, on the world
# STEP-13's check is tested on — Marco at Altavia, `tests/reason/expert/check_world`).

def _checked_row(**over):
    from types import SimpleNamespace

    from genios_engine.reason.expert.verify import check_review
    dossier, people = W.world()
    review = W.review(**over)
    return SimpleNamespace(review=review, fingerprint="ffp-x",
                           checked=check_review(review, dossier.text, people,
                                                evidence_ids=dossier.catalogue.evidence_ids))


def _find_out_row(*, unknowns=None, primary="An introduced investor has asked for a deck before a call",
                  what="Ask Marco whether Altavia leads seed rounds", **more):
    over = dict(mode="find_out", draft=None, move={"what": what, "to": None, "answers": None},
                frames={"primary": primary, "rivals": ["a polite brush-off"]}, **more)
    if unknowns is not None:
        over["unknowns"] = [{"question": u, "relevance": "decides the ask"} for u in unknowns]
    return _checked_row(**over)


def test_a_find_out_file_asks_you_a_real_question_its_first_unknown():
    """⛔ `03` X34: a find-out "question" was the move — an instruction ("Sign in to the portal…"). It is the
    review's first unknown, when that is a question its checked words can stand behind."""
    from genios_engine.reason.expert import asks
    row = _find_out_row(unknowns=["Does Altavia lead seed rounds?"])
    assert asks.question_words(row) == ("Does Altavia lead seed rounds?", asks.WHY_FIND_OUT)


@pytest.mark.parametrize("unknown, asked", [
    ("Whether Altavia leads seed rounds.", "Can you tell us whether Altavia leads seed rounds?"),
    ("How long Marco takes to decide", "Can you tell us how long Marco takes to decide?"),
    ("what the deck should hold", "Can you tell us what the deck should hold?")])
def test_an_unknown_that_can_be_a_question_is_asked_as_one(unknown, asked):
    """Its first word opens a sentence — "Whether" is no name (the checked words here never write it)."""
    from genios_engine.reason.expert import asks
    row = _find_out_row(unknowns=[unknown], what="Ask Marco if Altavia leads seed rounds")
    assert "whether" not in asks._checked_corpus(row.review, row.checked).lower()
    assert asks.question_words(row)[0] == asked


def test_a_question_that_names_us_is_never_asked_in_those_words():
    """⛔ STEP-04's rule on the question card (the golden lane, 12 Oct: F22's and F52's cards asked "Can you tell us
    whether Nimbus Labs is…?" and "…how many paying customers Nimbus Labs has today?"). A candidate that names us — our
    company, the founder — is passed over: the next one, else the closed question."""
    from genios_engine.reason.expert import asks
    row = _find_out_row(unknowns=["Does Altavia lead seed rounds?"], what="Ask Marco how the round is shaping up",
                        primary="An introduced investor at Altavia has asked for a deck before a call")
    names = lambda word: (lambda text: word in text.lower())               # noqa: E731 — as the sweep binds names_us
    assert asks.question_words(row, ours=names("nimbus"))[0] == "Does Altavia lead seed rounds?", \
        "nothing of ours in it: the first unknown, as before (the negative control)"
    assert asks.question_words(row, ours=names("altavia"))[0] == \
        "Can you tell us: Ask Marco how the round is shaping up?", "the unknown names us: the move"
    assert asks.question_words(row, ours=names("marco"))[0] == "Does Altavia lead seed rounds?"
    held_both = _find_out_row(unknowns=["Does Altavia lead seed rounds?"], what="Ask Altavia how the round looks")
    assert asks.question_words(held_both, ours=names("altavia"))[0] == asks.NOTHING_TO_ASK


_DATED = {"fact4": {"claim": "Introly introduced Marco on 4 Aug 2026"}}       # a kept fact holding "2026"
_DROPPED = {"facts": [*W.ANSWER["facts"], {"claim": "Tiger Global co-leads the round", "evidence": [W.ASK]}]}
_WITHHELD = {"primary": "Marco is deciding whether Tiger Global co-leads the round"}


@pytest.mark.parametrize("unknowns, more", [
    ([], {}),                                                   # no unknown at all
    (["Altavia's appetite for seed rounds."], {}),              # a statement, not a question
    (["Does Tiger Global co-lead the round?"], {}),             # a party no checked word holds
    (["Does Tiger Global co-lead the round?"], _DROPPED),       # …only a fact the check DROPPED names
    (["Does Tiger Global co-lead the round?"], _WITHHELD),      # …only the reading the check WITHHELD names
    (["Did Marco ask for 12 slides?"], {}),                     # a number no checked word holds
    (["Did Marco ask for 20 slides?"], _DATED)],                # …only inside another number ("2026")
    ids=["none", "a-statement", "an-unchecked-name", "a-dropped-facts-name", "a-withheld-readings-name",
         "an-unchecked-number",
         "a-number-inside-another"])
def test_with_no_question_its_checked_words_stand_behind_the_checked_move_is_asked(unknowns, more):
    from genios_engine.reason.expert import asks
    row = _find_out_row(unknowns=unknowns, **more)
    verdicts = {v.line: v.verdict for v in row.checked.verdicts if v.verdict != "noted"}
    assert more is not _DATED or verdicts["fact:4"] == "kept", "the number is in a KEPT fact"
    assert more is not _DROPPED or verdicts["fact:5"] == "dropped", "the name is in a DROPPED fact only"
    assert more is not _WITHHELD or verdicts["situation"] == "dropped", "the name is in a WITHHELD reading only"
    assert row.checked.words.headline == "Ask Marco whether Altavia leads seed rounds"
    assert asks.question_words(row) == ("Can you tell us: Ask Marco whether Altavia leads seed rounds?",
                                        asks.WHY_FIND_OUT)


def test_with_nothing_checked_the_file_asks_our_own_closed_question():
    """No check, no checked words: never the raw move or reading — our own question, closed."""
    from types import SimpleNamespace

    from genios_engine.reason.expert import asks
    row = _find_out_row(unknowns=["Does Altavia lead seed rounds?"])
    assert asks.question_words(SimpleNamespace(review=row.review, checked=None)) == (
        asks.NOTHING_TO_ASK, asks.WHY_FIND_OUT)


def test_a_checked_move_that_is_a_question_is_asked_as_written():
    from genios_engine.reason.expert import asks
    row = _find_out_row(what="Did Marco ask for the short deck before a call?", unknowns=["Altavia's fund."])
    assert asks.question_words(row)[0] == "Did Marco ask for the short deck before a call?"


def test_the_question_never_carries_the_reading_the_check_withheld():
    """⛔ `03` X06: the situation is dropped (`unsupported name:Tiger`), yet the question's `why` carried that very
    sentence ("the expert cannot read this file on without your answer: Marco is deciding whether Tiger Global
    co-leads the round"), and the card showed it."""
    from genios_engine.contracts import claim_check as C
    from genios_engine.reason.expert import asks
    row = _find_out_row(primary="Marco is deciding whether Tiger Global co-leads the round",
                        unknowns=["Does Altavia lead seed rounds?"])
    assert row.checked.fate == C.SHOWN and row.checked.words.situation is None
    question, why = asks.question_words(row)
    assert "Tiger" not in question and "Tiger" not in why and why == asks.WHY_FIND_OUT


@pytest.mark.parametrize("over, why", [
    (dict(move={"to": "Arjun Rao"}), "WHY_ADDRESSED_TO_YOU"),
    (dict(move={"to": "Introly"}, alternative=""), "WHY_TO_THE_CONNECTOR"),
    (dict(fact1={"quote": "a long deck and a term sheet"}), "WHY_NOT_CONFIRMED"),
    (dict(move={"what": "Send Marco the short deck and the Sequoia term sheet"}), "WHY_SAYS_MORE")],
    ids=["to-us", "to-the-connector", "misquoted", "the-move-says-more"])
def test_a_held_file_asks_the_checks_question_and_says_why_in_founder_words(over, why):
    """⛔ `03` X10: the check's internal reason (`misquoted: <the model's quote> (fact 1)`, `recipient_is_us:
    Arjun Rao`) became the question's `why`, and the card's `because`. It is one closed, founder-facing phrase."""
    from genios_engine.contracts import claim_check as C
    from genios_engine.reason.expert import asks
    row = _checked_row(**over)
    assert row.checked.fate == C.HELD, row.checked.verdicts
    question, said = asks.question_words(row)
    assert question == row.checked.question and said == getattr(asks, why)
    assert said in asks.WHYS and row.checked.because not in said and ":" not in said


# ── M36.C2.L-integration.V2.U11 · a question lives while it is asked (`03` X04, X26, X27) ───────────────────────

def _signal_of(store, org, anchor):
    with store.engine.connect() as c:
        return c.execute(text("select signal_id, authority_expires_at, reasoning_run_id from signals where org_id = :o "
                              "and subject_node_id = :n and rule_id = 'founder_question' and status = 'open'"),
                         {"o": org, "n": anchor}).one()


def test_an_asking_run_is_remembered_and_the_file_is_decided_again_before_its_question_lapses(world):
    """⛔ `03` X04: an insufficient run was gated SUPPRESSED — skipped forever (`reason/change_gate`), its question's
    authority lapsing at 168 h with nothing to renew it. An asking run is STANDING on its question's window: skipped
    while the window holds, decided again — re-bound, the window moved — in the day before it closes. The gate's
    memory is never deleted here."""
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    _find_out(store, org, anchor, "ffp-fund-findout-review-000", events)
    covered = {anchor: "ffp-fund-findout-review-000"}
    _compile(store, org, registry, covered=covered)
    first = _signal_of(store, org, anchor)
    quiet = _compile(store, org, registry, covered=covered, at=NOW + timedelta(hours=100))
    assert quiet.get("expert_unchanged") == 1 and quiet.get("expert_decided", 0) == 0, quiet
    renew = NOW + timedelta(hours=150)
    again = _compile(store, org, registry, covered=covered, at=renew)
    assert again.get("expert_decided") == 1 and again.get("expert_question_standing") == 1, again
    now = _signal_of(store, org, anchor)
    assert now.signal_id == first.signal_id and now.reasoning_run_id != first.reasoning_run_id
    assert now.authority_expires_at == renew + timedelta(hours=168)
    after = _compile(store, org, registry, covered=covered, at=renew + timedelta(hours=1))
    assert after.get("expert_unchanged") == 1, "renewed once, not on every sweep of its last day"
    assert _asking(store, org, at=NOW + timedelta(hours=169)) == [first.signal_id], "alive past seven days"
    # …and the re-bound question is remembered as standing too: its next window is renewed the same way.
    third = _compile(store, org, registry, covered=covered, at=renew + timedelta(hours=150))
    assert third.get("expert_question_standing") == 1, third
    assert _signal_of(store, org, anchor).authority_expires_at == renew + timedelta(hours=318)


def test_a_question_whose_window_lapsed_unseen_is_asked_again_on_the_next_sweep(world):
    """No sweep in its last day (the machine slept): the first sweep after the lapse decides the file again."""
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    _find_out(store, org, anchor, "ffp-fund-findout-review-000", events)
    covered = {anchor: "ffp-fund-findout-review-000"}
    _compile(store, org, registry, covered=covered)
    later = NOW + timedelta(hours=169)
    assert _asking(store, org, at=later) == []
    counts = _compile(store, org, registry, covered=covered, at=later)
    assert counts.get("expert_question_standing") == 1, counts
    assert len(_asking(store, org, at=later)) == 1


def _other_file(store, org):
    """The programme's file — another covered file, so this pass's coverage is the expert's, not empty."""
    from tests.reason.test_a_programme_is_not_decided_as_an_investor import PROGRAMME, _by_counterparty
    situations = _by_counterparty(store, org)[PROGRAMME]
    with store.engine.connect() as c:
        rows = c.execute(text(
            "select s.anchor_node_id, m.event_id from context_situations s "
            "  join context_correlation_members m on m.org_id = s.org_id and m.correlation_id = s.correlation_id "
            " where s.org_id = :o and s.situation_id = any(:s)"), {"o": org, "s": list(situations)}).all()
    return {r.anchor_node_id for r in rows}.pop(), {r.event_id for r in rows}


def test_a_file_that_leaves_coverage_retires_its_question_and_its_signal(world):
    """⛔ `03` X26 (`06` D60, the file's one card): the file is no longer the expert's to decide — its situations are
    decided on their own again — so its question retires (`LEFT_COVERAGE`) and its signal expires, its card REPLACED."""
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    _find_out(store, org, anchor, "ffp-fund-findout-review-000", events)
    _compile(store, org, registry, covered={anchor: "ffp-fund-findout-review-000"})
    other, other_events = _other_file(store, org)
    _write(store, org, other, "ffp-programme-review-0000", other_events)
    later = NOW + timedelta(hours=1)
    counts = _compile(store, org, registry, covered={other: "ffp-programme-review-0000"}, at=later)
    assert counts.get("expert_question_uncovered") == 1, counts
    [q] = _questions(store, org, anchor)
    assert (q.state, q.retired_why) == (Q.RETIRED, Q.LEFT_COVERAGE)
    assert _asking(store, org, at=later) == []


def test_a_pass_that_covered_nothing_takes_no_question_down(world):
    """⛔ THE NEGATIVE CONTROL. A pass whose expert covered nothing — it failed, or it did not run — is our failure,
    not the file's: its question stays open (its window ends it, as declared)."""
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    _find_out(store, org, anchor, "ffp-fund-findout-review-000", events)
    _compile(store, org, registry, covered={anchor: "ffp-fund-findout-review-000"})
    counts = _compile(store, org, registry, covered={}, at=NOW + timedelta(hours=1))
    assert counts.get("expert_question_uncovered", 0) == 0
    [q] = _questions(store, org, anchor)
    assert q.state == Q.OPEN and len(_asking(store, org, at=NOW + timedelta(hours=1))) == 1


@pytest.fixture
def spent(monkeypatch):
    """A day whose cap is spent: no allowance left, across every lane."""
    from genios_engine.reason import domain_shadow
    monkeypatch.setattr(domain_shadow, "_daily_allowance", lambda *_a, **_k: 0)


def test_on_a_day_the_cap_is_spent_the_file_still_asks(world, spent):
    """⛔ `03` X27: the cap stopped the pass before the outcome — a held or finding-out file neither asked nor
    cleared. The cap is the emitted decision's; a question emits none."""
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    _find_out(store, org, anchor, "ffp-fund-findout-review-000", events)
    counts = _compile(store, org, registry, covered={anchor: "ffp-fund-findout-review-000"})
    assert counts.get("expert_question_asked") == 1 and counts.get("budget_exhausted", 0) == 0, counts
    assert len(_asking(store, org)) == 1


def test_on_a_day_the_cap_is_spent_a_review_that_names_no_move_still_clears(world, monkeypatch):
    from genios_engine.reason import domain_shadow
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    _write(store, org, anchor, "ffp-fund-act-review-000000", events)
    _compile(store, org, registry, covered={anchor: "ffp-fund-act-review-000000"})
    assert [s.rule_id for s in _open_signals(store, org, anchor)] == ["file_review"]
    monkeypatch.setattr(domain_shadow, "_daily_allowance", lambda *_a, **_k: 0)
    _write(store, org, anchor, "ffp-fund-nothing-review-00", events, mode="nothing", next_move=None, draft=None)
    counts = _compile(store, org, registry, covered={anchor: "ffp-fund-nothing-review-00"},
                      at=NOW + timedelta(hours=1))
    assert counts.get("expert_cleared") == 1 and counts.get("budget_exhausted", 0) == 0, counts
    assert _open_signals(store, org, anchor) == []


def test_on_a_day_the_cap_is_spent_a_decision_still_waits(world, spent):
    """The cap still holds what it is for: a decision that would be shown."""
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    _write(store, org, anchor, "ffp-fund-act-review-000000", events)
    counts = _compile(store, org, registry, covered={anchor: "ffp-fund-act-review-000000"})
    assert counts.get("budget_exhausted") == 1 and counts.get("expert_emitted", 0) == 0, counts
