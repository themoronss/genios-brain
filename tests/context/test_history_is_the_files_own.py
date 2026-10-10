"""`03` F113 · a file's history is its own — how its PRIOR generation ended, in its own domain.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_history_is_the_files_own.py -q

`yc2_w27_align` M34.C2.L-logic.V0.U07. Since STEP-10 a file's past is published per (anchor, domain),
but `context/correlation_history.read_histories` keyed the two enrichments by ANCHOR and kept the LAST
row overall: an outcome and a card verdict from the fundraising file were the admin file's too, and a
verdict on the CURRENT generation's card was reported as how the prior one ended. STEP-12's dossier
reads these as "prior judgments and what came of them", so each is now placed where it belongs:

  * a signal compiled from a situation (`signals.situation_id`, 0182) names its file and generation
    through the situation's correlation — exactly;
  * a signal without one (four of the five writers leave it NULL, `reason/situation_binding`) names
    only its subject, so it is placed only where that cannot be wrong: in the prior generation of an
    anchor's ONE file, when it was emitted while that generation was open — and nowhere when the prior
    generation's row is gone or its opening unknown.

The prior is the generation just before the current one; what nothing places there is `unrecorded`.
Real Postgres: the joins run against the real schema.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.context.correlation_history import NO_PRIOR, UNKNOWN_OUTCOME, read_histories

from ..test_admin_support_packs import _seed_org

pytestmark = pytest.mark.pg

NOW = datetime(2026, 10, 10, 12, tzinfo=timezone.utc)
ANCHOR = "node_u07_kestrel"
_TABLES = ("card_feedback_verdicts", "cards", "execution_outcomes", "signals", "context_situations",
           "context_correlations")


@pytest.fixture
def org(pg_store, request):
    org = f"org_u07_{request.node.name[5:40]}"
    _seed_org(pg_store, org)
    with pg_store.engine.begin() as c:
        for table in _TABLES:
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": org})
    yield org
    with pg_store.engine.begin() as c:
        for table in _TABLES:
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": org})


def _days(n: float) -> datetime:
    return NOW - timedelta(days=n)


def _generation(store, org, domain, generation, *, first, last, anchor=ANCHOR) -> str:
    """One generation of a file, and the situation it formed. Returns the situation's id."""
    corr = f"corr_{org}_{anchor}_{domain}_{generation}"
    with store.engine.begin() as c:
        c.execute(text(
            "insert into context_correlations (correlation_id, org_id, anchor_node_id, anchor_type, "
            " domain, generation, first_event_at, last_event_at) "
            "values (:id, :o, :n, 'company', :d, :g, :f, :l)"),
            {"id": corr, "o": org, "n": anchor, "d": domain, "g": generation, "f": _days(first),
             "l": _days(last)})
        c.execute(text(
            "insert into context_situations (situation_id, org_id, correlation_id, anchor_node_id, "
            " situation_type, domain) values (:s, :o, :c, :n, 'relationship', :d)"),
            {"s": f"sit_{corr}", "o": org, "c": corr, "n": anchor, "d": domain})
    return f"sit_{corr}"


def _signal(store, org, name, *, emitted, situation=None, anchor=ANCHOR) -> str:
    with store.engine.begin() as c:
        c.execute(text(
            "insert into signals (signal_id, org_id, rule_id, subject_node_id, score, reason_code, "
            " eval_time, situation_id) values (:s, :o, 'r', :n, 50, 'r', :at, :sit)"),
            {"s": f"sig_{org}_{name}", "o": org, "n": anchor, "at": _days(emitted),
             "sit": situation})
    return f"sig_{org}_{name}"


def _outcome(store, org, signal, label, *, closed) -> None:
    with store.engine.begin() as c:
        c.execute(text(
            "insert into execution_outcomes (outcome_id, org_id, execution_id, decision_hash, "
            " capability_id, capability_version, play_id, play_version, terminal_state, reason_code, "
            " label, created_at, closed_at, seconds_to_close, actions_total, actions_completed, "
            " progress_bp, priority_bp, confidence_bp, band, routing_rule, subject_ref) values "
            " (:i, :o, :i, 'h', 'c', '1', 'p', '1', 'closed', 'r', :l, :t, :t, 0, 1, 1, 10000, 0, 0, "
            "  'b', 'x', :ref)"),
            {"i": f"out_{signal}_{label}", "o": org, "l": label, "t": _days(closed),
             "ref": f"signal:{signal}"})


def _verdict(store, org, signal, cause, reason=None, *, at) -> None:
    card = f"card_{signal}"
    with store.engine.begin() as c:
        c.execute(text(
            "insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, situation, "
            " score, expires_at) values (:c, :s, :o, 'prescriptive', 'normal', 'h', 's', 50, :x) "
            "on conflict do nothing"),
            {"c": card, "s": signal, "o": org, "x": NOW + timedelta(days=7)})
        c.execute(text(
            "insert into card_feedback_verdicts (feedback_id, org_id, card_id, pack_id, pack_version, "
            " authority_pack_revision, capability_id, capability_version, rule_id, cause, reason, "
            " actor_id, occurred_at) values (:f, :o, :c, 'p', '1', 1, 'c', '1', 'r', :cause, :why, "
            " 'founder', :at)"),
            {"f": f"fb_{card}_{cause}_{reason}", "o": org, "c": card, "cause": cause, "why": reason,
             "at": _days(at)})


def _past(store, org) -> dict[str, tuple]:
    with store.engine.connect() as c:
        return {h.domain: (h.times_seen, h.prior_outcome, h.prior_card_verdict)
                for h in read_histories(c, org) if h.anchor_node_id == ANCHOR}


def test_one_files_ending_is_not_the_other_files(pg_store, org):
    """Kestrel's fundraising file ended its second time `succeeded`, a card marked not relevant; its
    admin file has a second time too, and nothing recorded how its first ended."""
    for g, (first, last) in enumerate(((200, 190), (100, 90), (5, 0)), start=1):
        situation = _generation(pg_store, org, "fundraising", g, first=first, last=last)
        if g == 2:
            sig = _signal(pg_store, org, "fund2", emitted=95, situation=situation)
            _outcome(pg_store, org, sig, "succeeded", closed=92)
            _verdict(pg_store, org, sig, "wrong", "not_relevant", at=93)
    _generation(pg_store, org, "admin", 1, first=60, last=50)
    _generation(pg_store, org, "admin", 2, first=3, last=0)

    assert _past(pg_store, org) == {"fundraising": (3, "succeeded", "wrong:not_relevant"),
                                    "admin": (2, UNKNOWN_OUTCOME, UNKNOWN_OUTCOME)}


def test_the_prior_is_the_generation_before_this_one_not_the_latest_overall(pg_store, org):
    """A verdict on THIS generation's card is not how the last one ended."""
    first = _generation(pg_store, org, "sales", 1, first=200, last=190)
    current = _generation(pg_store, org, "sales", 2, first=5, last=0)
    old = _signal(pg_store, org, "old", emitted=195, situation=first)
    _outcome(pg_store, org, old, "succeeded", closed=189)
    _verdict(pg_store, org, old, "run_play", at=192)
    new = _signal(pg_store, org, "new", emitted=4, situation=current)
    _outcome(pg_store, org, new, "abandoned", closed=1)
    _verdict(pg_store, org, new, "wrong", "bad_timing", at=2)

    assert _past(pg_store, org) == {"sales": (2, "succeeded", "run_play")}


def test_within_the_prior_generation_the_latest_ending_wins(pg_store, org):
    """Two cards in the prior generation (a card holds one verdict): the later word is the last one."""
    first = _generation(pg_store, org, "sales", 1, first=200, last=150)
    _generation(pg_store, org, "sales", 2, first=5, last=0)
    for name, cause, reason, at in (("late", "run_play", None, 160),
                                    ("early", "wrong", "bad_timing", 180)):
        sig = _signal(pg_store, org, name, emitted=at + 5, situation=first)
        _verdict(pg_store, org, sig, cause, reason, at=at)
        _outcome(pg_store, org, sig, f"{name}_ending", closed=at - 1)

    assert _past(pg_store, org)["sales"][1:] == ("late_ending", "run_play")


def test_a_signal_with_no_situation_is_placed_on_an_anchors_only_file_by_when_it_was_emitted(
        pg_store, org):
    """The main path's signals carry no situation (`reason/situation_binding`, held). On an anchor
    with one file, the generation open when the signal was emitted is the only one it can be."""
    _generation(pg_store, org, "sales", 1, first=200, last=190)
    _generation(pg_store, org, "sales", 2, first=5, last=0)
    then = _signal(pg_store, org, "then", emitted=185)
    _outcome(pg_store, org, then, "succeeded", closed=180)
    _verdict(pg_store, org, then, "do_it_myself", at=182)
    now = _signal(pg_store, org, "now", emitted=2)
    _verdict(pg_store, org, now, "wrong", "not_relevant", at=1)

    assert _past(pg_store, org) == {"sales": (2, "succeeded", "do_it_myself")}


def test_a_signal_with_no_situation_on_an_anchor_with_two_files_is_placed_nowhere(pg_store, org):
    """Which file it was about is not written anywhere — so neither file says it."""
    for domain in ("sales", "admin"):
        _generation(pg_store, org, domain, 1, first=200, last=190)
        _generation(pg_store, org, domain, 2, first=5, last=0)
    sig = _signal(pg_store, org, "either", emitted=185)
    _outcome(pg_store, org, sig, "succeeded", closed=180)
    _verdict(pg_store, org, sig, "run_play", at=182)

    assert _past(pg_store, org) == {"sales": (2, UNKNOWN_OUTCOME, UNKNOWN_OUTCOME),
                                    "admin": (2, UNKNOWN_OUTCOME, UNKNOWN_OUTCOME)}


def test_a_prior_generation_that_is_gone_is_unrecorded(pg_store, org):
    """A merge removed generation 2: a signal emitted before generation 3 opened may be generation
    1's or the missing one's, and the prior is generation 2's whichever it was."""
    first = _generation(pg_store, org, "sales", 1, first=300, last=290)
    _generation(pg_store, org, "sales", 3, first=5, last=0)
    by_time = _signal(pg_store, org, "by_time", emitted=150)
    _verdict(pg_store, org, by_time, "run_play", at=140)
    exact = _signal(pg_store, org, "exact", emitted=295, situation=first)
    _outcome(pg_store, org, exact, "succeeded", closed=289)

    assert _past(pg_store, org) == {"sales": (3, UNKNOWN_OUTCOME, UNKNOWN_OUTCOME)}


def test_nothing_is_placed_in_a_generation_that_may_be_the_missing_ones():
    """`_placed`'s own word, not only the fact it feeds: with generation 2 gone, a signal emitted
    before generation 3 opened is placed nowhere — not in generation 1, which it may not be."""
    from genios_engine.context.correlation_history import _placed
    chains = {(ANCHOR, "sales"): [{"generation": 1, "first_event_at": _days(300)},
                                  {"generation": 3, "first_event_at": _days(5)}]}
    row = {"anchor": ANCHOR, "situation_id": None, "emitted_at": _days(150), "file_anchor": None,
           "file_domain": None, "file_generation": None}
    assert _placed(row, chains) is None
    chains[(ANCHOR, "sales")][1]["generation"] = 2
    assert _placed(row, chains) == (ANCHOR, "sales", 1)


def test_an_ending_from_two_generations_ago_is_not_the_priors(pg_store, org):
    _generation(pg_store, org, "sales", 1, first=300, last=290)
    _generation(pg_store, org, "sales", 2, first=100, last=90)
    _generation(pg_store, org, "sales", 3, first=5, last=0)
    sig = _signal(pg_store, org, "long_ago", emitted=295)
    _outcome(pg_store, org, sig, "succeeded", closed=289)

    assert _past(pg_store, org) == {"sales": (3, UNKNOWN_OUTCOME, UNKNOWN_OUTCOME)}


def test_an_opening_nobody_recorded_places_nothing_by_time(pg_store, org):
    """The prior generation's first event is unknown, so whether the signal came after it is too —
    while a signal that names its situation still says exactly where it belongs."""
    first = _generation(pg_store, org, "sales", 1, first=200, last=190)
    _generation(pg_store, org, "sales", 2, first=5, last=0)
    with pg_store.engine.begin() as c:
        c.execute(text("update context_correlations set first_event_at = null "
                       " where org_id = :o and generation = 1"), {"o": org})
    by_time = _signal(pg_store, org, "by_time", emitted=195)
    _outcome(pg_store, org, by_time, "succeeded", closed=189)
    assert _past(pg_store, org) == {"sales": (2, UNKNOWN_OUTCOME, UNKNOWN_OUTCOME)}

    exact = _signal(pg_store, org, "exact", emitted=195, situation=first)
    _verdict(pg_store, org, exact, "run_play", at=188)
    assert _past(pg_store, org) == {"sales": (2, UNKNOWN_OUTCOME, "run_play")}


def test_a_signal_whose_situation_is_gone_is_not_placed_by_its_time_instead(pg_store, org):
    """It named where it belonged; that place is gone, and its time is not a second opinion."""
    _generation(pg_store, org, "sales", 1, first=200, last=190)
    _generation(pg_store, org, "sales", 2, first=5, last=0)
    sig = _signal(pg_store, org, "orphan", emitted=195, situation="sit_merged_away")
    _outcome(pg_store, org, sig, "succeeded", closed=189)

    assert _past(pg_store, org) == {"sales": (2, UNKNOWN_OUTCOME, UNKNOWN_OUTCOME)}


def test_a_first_time_is_still_a_first_time(pg_store, org):
    current = _generation(pg_store, org, "sales", 1, first=5, last=0)
    sig = _signal(pg_store, org, "now", emitted=2, situation=current)
    _verdict(pg_store, org, sig, "run_play", at=1)

    assert _past(pg_store, org) == {"sales": (1, NO_PRIOR, NO_PRIOR)}
