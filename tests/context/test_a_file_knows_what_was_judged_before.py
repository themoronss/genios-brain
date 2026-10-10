"""STEP-12 · a file knows what was judged before — its reviews, its people's cards, how its situations ended, its past.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_a_file_knows_what_was_judged_before.py -q

`context/file_judgments.judgments_for` (tree `yc2_w27_s12` M32.C2.L-data.V0.U02). STEP-12 §8.3 N6: prior
cards, verdicts and `derived.history.*` had no reader by file, so an expert reviewing a file could not be
told what was decided about it before, what the founder did with it, or how it went the last time. One
read per part, each by the FILE — the expert's own past reviews of it (`expert_reviews`, newest first),
the cards about its people with their events and the founder's verdicts, its situations with how each
ended (`situation_outcomes`), and the file's own past (`derived.history.*@<domain>`, each ending placed
on its own generation since `yc2_w27_align` M34.C2 U07, `03` F113). Bounded, and the cut COUNTED, never
silent; nothing a seat captured privately is read.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.context import file_judgments as J
from genios_engine.context.analytic.publish import publish_derived_fact
from genios_engine.context.correlation_history import VERSION_PREFIX, history_field

pytestmark = pytest.mark.pg

ORG = "org_s12_judged_before"
FILE, RAHUL, ELSE = "node_kestrel", "node_rahul", "node_someone_else"
T0 = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)


@pytest.fixture
def engine(pg_store):
    eng = pg_store.engine
    _clean(eng)
    with eng.begin() as c:
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'jb@example.test')"),
                  {"o": ORG})
        for node, kind, key in ((FILE, "company", "kestrelcap.test"),
                                (RAHUL, "person", "rahul@kestrelcap.test"),
                                (ELSE, "person", "priya@northwind.test")):
            c.execute(text("insert into graph_nodes (node_id, org_id, node_type, canonical_key) "
                           "values (:n, :o, :t, :k)"), {"n": node, "o": ORG, "t": kind, "k": key})
    yield eng
    _clean(eng)


def _clean(eng) -> None:
    with eng.begin() as c:
        for table in ("card_feedback_verdicts", "card_events", "cards", "signals",
                      "situation_outcomes", "situation_admission_decisions", "context_situations",
                      "context_correlations", "expert_reviews", "graph_facts", "graph_nodes"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _review(c, fp: str, at: datetime, *, status="valid", reason=None, mode="wait"):
    c.execute(text(
        "insert into expert_reviews (org_id, file_id, fingerprint, model, prompt_version, "
        "dossier_digest, status, reason, review, reviewed_at) values (:o, :f, :fp, "
        "'claude-sonnet-5', 'expert-review.v1', 'sha256:d', :s, :r, cast(:v as jsonb), :at)"),
        {"o": ORG, "f": FILE, "fp": fp, "s": status, "r": reason,
         "v": None if status != "valid" and mode is None else json.dumps({"mode": mode}),
         "at": at})


def _card(c, card: str, subject: str, at: datetime, *, events=(), verdict=None):
    c.execute(text(
        "insert into signals (signal_id, org_id, rule_id, subject_node_id, score, reason_code, "
        "eval_time, level) values (:s, :o, 'rule_a', :n, 5000, 'r', :at, 'prescriptive')"),
        {"s": f"sig_{card}", "o": ORG, "n": subject, "at": at})
    c.execute(text(
        "insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, situation, "
        "score, expires_at, created_at, state) values (:c, :s, :o, 'prescriptive', 'soon', :h, "
        "'a situation', 5000, :exp, :at, 'resolved')"),
        {"c": card, "s": f"sig_{card}", "o": ORG, "h": f"headline of {card}",
         "exp": at + timedelta(days=7), "at": at})
    for n, (kind, cause) in enumerate(events):
        c.execute(text("insert into card_events (id, card_id, org_id, kind, cause, occurred_at) "
                       "values (:i, :c, :o, :k, :cause, :at)"),
                  {"i": f"ev_{card}_{n}", "c": card, "o": ORG, "k": kind, "cause": cause,
                   "at": at + timedelta(hours=n + 1)})
    if verdict:
        c.execute(text(
            "insert into card_feedback_verdicts (feedback_id, org_id, card_id, pack_id, "
            "pack_version, authority_pack_revision, capability_id, capability_version, rule_id, "
            "cause, reason, actor_id, verdict_version, occurred_at) values (:f, :o, :c, 'p', '1', 1, "
            "'cap', '1', 'rule_a', :cause, :reason, 'seat_owner', 1, :at)"),
            {"f": f"fb_{card}", "o": ORG, "c": card, "cause": verdict[0], "reason": verdict[1],
             "at": at + timedelta(days=1)})


def _situation(c, sid: str, at: datetime, *, status="active", outcome=None, reason=None):
    c.execute(text("insert into context_correlations (correlation_id, org_id, anchor_node_id, "
                   "domain) values (:k, :o, :f, 'founder_office') on conflict do nothing"),
              {"k": f"cor_{sid}", "o": ORG, "f": FILE})
    c.execute(text(
        "insert into context_situations (situation_id, org_id, correlation_id, anchor_node_id, "
        "situation_type, domain, status, first_seen_at, last_seen_at) values (:s, :o, :k, :f, "
        "'investor_relationship', 'founder_office', :st, :at, :at)"),
        {"s": sid, "o": ORG, "k": f"cor_{sid}", "f": FILE, "st": status, "at": at})
    if outcome:
        c.execute(text(
            "insert into situation_admission_decisions (decision_id, org_id, situation_id, "
            "candidate_hash, outcome, candidate, schema_version, decided_at) values "
            "(:d, :o, :s, :h, 'admit', cast('{}' as jsonb), 'v1', :at)"),
            {"d": f"dec_{sid}", "o": ORG, "s": sid, "h": f"h_{sid}", "at": at})
        c.execute(text(
            "insert into situation_outcomes (org_id, decision_id, situation_id, outcome, reason, "
            "recorded_at, last_seen_at) values (:o, :d, :s, :out, :r, :at, :at)"),
            {"o": ORG, "d": f"dec_{sid}", "s": sid, "out": outcome, "r": reason, "at": at})


def _history(c, field: str, value, value_type: str, *, subject: str = FILE,
             visibility: str = "org"):
    publish_derived_fact(c, org_id=ORG, subject_node_id=subject,
                         field=history_field(field, "founder_office"), value=value, eval_time=T0,
                         value_type=value_type, visibility_scope=visibility,
                         version_prefix=VERSION_PREFIX)


def _people():
    return (FILE, RAHUL)


def test_each_part_is_read_by_the_file_newest_first(engine):
    with engine.begin() as c:
        _review(c, "fp_1", T0, mode="act")
        _review(c, "fp_2", T0 + timedelta(days=2), status="refused", reason="number_not_in_dossier: 32",
                mode="act")
        _card(c, "card_rahul", RAHUL, T0, events=(("surfaced", "built"), ("resolved", "acted")),
              verdict=("run_play", None))
        _card(c, "card_else", ELSE, T0)                                  # not this file's people
        _situation(c, "sit_old", T0 - timedelta(days=30), status="resolved", outcome="decided")
        _situation(c, "sit_now", T0, outcome="no_route", reason="predicate_rejected")
        _history(c, "derived.history.times_seen", 2, "count")
        _history(c, "derived.history.prior_outcome", "succeeded", "label")
    with engine.connect() as c:
        got = J.judgments_for(c, ORG, FILE, people=_people())
    assert [(r.fingerprint, r.status, r.mode) for r in got.reviews] == [
        ("fp_2", "refused", "act"), ("fp_1", "valid", "act")]
    assert got.reviews[0].reason == "number_not_in_dossier: 32"
    [card] = got.cards
    assert (card.card_id, card.subject_node_id, card.headline) == ("card_rahul", RAHUL,
                                                                    "headline of card_rahul")
    assert [(e.kind, e.cause) for e in card.events] == [("surfaced", "built"), ("resolved", "acted")]
    assert [(v.cause, v.reason) for v in card.verdicts] == [("run_play", None)]
    assert [(s.situation_id, s.status, s.outcome, s.reason) for s in got.situations] == [
        ("sit_now", "active", "no_route", "predicate_rejected"), ("sit_old", "resolved", "decided", None)]
    assert {(h.field, h.value) for h in got.history} == {
        ("derived.history.times_seen@founder_office", 2),
        ("derived.history.prior_outcome@founder_office", "succeeded")}
    assert got.cut == {"reviews": 0, "cards": 0, "events": 0, "situations": 0, "history": 0}


def test_every_part_is_bounded_and_the_cut_is_counted(engine):
    with engine.begin() as c:
        for n in range(J.LIMITS["reviews"] + 2):
            _review(c, f"fp_{n}", T0 + timedelta(hours=n))
        for n in range(J.LIMITS["cards"] + 1):
            _card(c, f"card_{n:02d}", RAHUL, T0 + timedelta(hours=n),
                  events=tuple(("shown", "sweep") for _ in range(J.LIMITS["events"] + 3)) if n == 0
                  else ())
        for n in range(J.LIMITS["situations"] + 4):
            _situation(c, f"sit_{n:02d}", T0 + timedelta(hours=n))
    with engine.connect() as c:
        got = J.judgments_for(c, ORG, FILE, people=_people())
    assert len(got.reviews) == J.LIMITS["reviews"] and got.cut["reviews"] == 2
    assert got.reviews[0].fingerprint == f"fp_{J.LIMITS['reviews'] + 1}"          # the newest kept
    assert len(got.cards) == J.LIMITS["cards"] and got.cut["cards"] == 1
    assert "card_00" not in {card.card_id for card in got.cards}                   # the oldest cut
    assert len(got.situations) == J.LIMITS["situations"] and got.cut["situations"] == 4
    assert got.cut["events"] == 0                                                   # card_00 was cut


def test_a_cards_events_are_bounded_newest_kept(engine):
    with engine.begin() as c:
        _card(c, "card_busy", RAHUL, T0,
              events=tuple(("shown", f"sweep_{n}") for n in range(J.LIMITS["events"] + 3)))
    with engine.connect() as c:
        got = J.judgments_for(c, ORG, FILE, people=_people())
    [card] = got.cards
    assert len(card.events) == J.LIMITS["events"] and got.cut["events"] == 3
    assert card.events[-1].cause == f"sweep_{J.LIMITS['events'] + 2}"


def test_another_files_and_a_private_past_are_not_read(engine):
    with engine.begin() as c:
        _history(c, "derived.history.times_seen", 3, "count", subject=ELSE)
        _history(c, "derived.history.prior_card_verdict", "wrong", "label", visibility="private")
    with engine.connect() as c:
        got = J.judgments_for(c, ORG, FILE, people=_people())
    assert got.history == () and got.cards == () and got.reviews == () and got.situations == ()


def test_a_file_with_no_past_is_empty_not_absent(engine):
    with engine.connect() as c:
        got = J.judgments_for(c, ORG, FILE, people=_people())
    assert (got.reviews, got.cards, got.situations, got.history) == ((), (), (), ())
    assert got.cut == {"reviews": 0, "cards": 0, "events": 0, "situations": 0, "history": 0}
    assert got.file_id == FILE


def test_the_record_is_plain_data(engine):
    with engine.begin() as c:
        _review(c, "fp_1", T0)
        _card(c, "card_rahul", RAHUL, T0, events=(("surfaced", "built"),),
              verdict=("wrong", "bad_timing"))
        _situation(c, "sit_now", T0, outcome="decided")
        _history(c, "derived.history.days_since_prior", 41, "days")
    with engine.connect() as c:
        shape = J.judgments_for(c, ORG, FILE, people=_people()).as_dict()
    assert json.loads(json.dumps(shape)) == shape
    assert shape["cards"][0]["verdicts"] == [{"cause": "wrong", "reason": "bad_timing",
                                              "at": (T0 + timedelta(days=1)).isoformat()}]
