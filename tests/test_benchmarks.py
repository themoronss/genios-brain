"""Public benchmarks scorecard + methodology — shape + no-auth (hermetic, no DB needed)."""

from __future__ import annotations

from fastapi.testclient import TestClient

import genios_engine.main as m

client = TestClient(m.app)


def test_scorecard_is_public_and_well_shaped():
    r = client.get("/v1/benchmarks/scorecard")            # no Authorization header
    assert r.status_code == 200
    body = r.json()
    for key in ("version", "build_sha", "generated_at", "window_days",
                "min_n_gate", "k_anonymous", "scale", "tier1", "per_detector"):
        assert key in body
    # tier1 metrics gate honestly when there is no data
    assert body["tier1"] == {} or "faithfulness" in body["tier1"]


def test_methodology_is_public():
    r = client.get("/v1/benchmarks/methodology")
    assert r.status_code == 200
    assert r.json()["k_anonymous"] is True


# =================================================================================================
# STEP-16 · the acted rate counts what you did (`03` F76, `s16-F8`; `yc2_w27_s16` M47.C3.L-logic.V0.U04)
# =================================================================================================
import os  # noqa: E402
from datetime import datetime, timedelta, timezone  # noqa: E402

import pytest  # noqa: E402

from genios_engine.api import benchmarks_routes as B  # noqa: E402
from genios_engine.platform import card_lifecycle as L  # noqa: E402


def test_taken_is_a_card_acted_on_run_play_or_do_it_myself_or_resolved_never_delivered():
    counts = B.acted_counts([
        ("acted", "run_play", None, 3), ("acted", "do_it_myself", None, 2), ("resolved", "answer", None, 1),
        ("delivered", None, None, 7), ("claimed", None, None, 4)])
    assert (counts["taken"], counts["open"]) == (6, 11)


def test_a_card_called_wrong_is_its_own_count():
    counts = B.acted_counts([("acted", "wrong", None, 5)])
    assert (counts["called_wrong"], counts["taken"]) == (5, 0)


@pytest.mark.parametrize("cause", sorted(B.MOVED_ON))
def test_a_card_the_engine_moved_on_from_is_not_ignored(cause):
    counts = B.acted_counts([("expired", None, cause, 9)])
    assert counts["moved_on"] == 9 and counts["lapsed"] == counts["dismissed"] == 0
    assert B.acted_rate(counts)["n"] == 0, "in no denominator"


def test_what_lapsed_or_you_dismissed_is_ignored_and_an_ending_with_no_cause_is_in_no_rate():
    counts = B.acted_counts([("expired", None, L.LAPSED, 2), ("expired", None, L.EXTENSION, 1),
                             ("expired", None, None, 4), ("dismissed", None, None, 8),
                             ("acted", None, None, 3)])
    assert (counts["lapsed"], counts["dismissed"], counts["unattributed"]) == (2, 1, 15)


def test_the_rate_is_taken_of_what_you_ended_and_says_its_parts():
    counts = B.acted_counts([("acted", "run_play", None, 18), ("acted", "wrong", None, 6),
                             ("expired", None, L.LAPSED, 4), ("expired", None, L.EXTENSION, 2),
                             ("expired", None, L.REPLACED, 50), ("delivered", None, None, 40)])
    rate = B.acted_rate(counts)
    assert (rate["value"], rate["n"]) == (0.6, 30)
    assert (rate["taken"], rate["called_wrong"], rate["lapsed"], rate["dismissed"], rate["moved_on"]) == (
        18, 6, 4, 2, 50)
    assert B.acted_rate(B.acted_counts([("acted", "run_play", None, 29)])) == B._insufficient(29)


def test_the_moved_on_causes_are_every_cause_but_a_lapse_and_a_dismissal():
    assert B.MOVED_ON == L.CAUSES - {L.LAPSED, L.EXTENSION}
    assert {L.REPLACED, L.RULE_CLEARED} <= B.MOVED_ON


@pytest.mark.pg
def test_on_postgres_each_card_is_read_by_its_last_button_and_its_ending(live_db_url):
    """The statement, on the migrated schema: a card's last action event names its button, its ending event
    its cause. Counted as a difference inside one transaction, so other tenants' cards change nothing."""
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the statement is Postgres's")
    from sqlalchemy import text as sql

    from genios_engine.platform.db import get_engine
    org, at = "org_s16_acted_rate", datetime.now(timezone.utc) - timedelta(days=1)
    with get_engine(live_db_url).connect() as c:
        tx = c.begin()
        try:
            before = B.acted_counts(c.execute(sql(B._ACTED_ROWS)).all())
            c.execute(sql("insert into orgs (id, name) values (:o, :o) on conflict (id) do nothing"), {"o": org})
            cards = {"taken": ("acted", "human.card_action", "do_it_myself"),
                     "snoozed_then_taken": ("acted", "human.card_action", "run_play"),
                     "wrong": ("acted", "human.card_action", "wrong"),
                     "resolved": ("resolved", None, None),
                     "lapsed": ("expired", "window.lapsed", L.LAPSED),
                     "replaced": ("expired", "card.expired", L.REPLACED),
                     "delivered": ("delivered", None, None)}
            for name, (state, kind, cause) in cards.items():
                c.execute(sql(
                    "insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, situation, "
                    "score, expires_at, state, created_at) values (:c, :s, :o, 'prescriptive', 'standard', 'h', "
                    "'s', 10, :exp, :state, :at)"),
                    {"c": f"card_s16_{name}", "s": f"sig_s16_{name}", "o": org, "exp": at + timedelta(days=7),
                     "state": state, "at": at})
                if name == "snoozed_then_taken":       # the LAST button is what it came to
                    c.execute(sql("insert into card_events (id, card_id, org_id, kind, cause, actor_id, detail, "
                                  "occurred_at) values ('cev_s16_first', :c, :o, 'human.card_action', 'snooze', "
                                  "'founder', '{}'::jsonb, :at)"), {"c": f"card_s16_{name}", "o": org, "at": at})
                if kind:
                    c.execute(sql("insert into card_events (id, card_id, org_id, kind, cause, actor_id, detail, "
                                  "occurred_at) values (:i, :c, :o, :k, :cause, 'founder', '{}'::jsonb, :at)"),
                              {"i": f"cev_s16_{name}", "c": f"card_s16_{name}", "o": org, "k": kind,
                               "cause": cause, "at": at + timedelta(hours=1)})
            after = B.acted_counts(c.execute(sql(B._ACTED_ROWS)).all())
        finally:
            tx.rollback()
    delta = {k: after[k] - before[k] for k in after}
    assert delta == {"taken": 3, "called_wrong": 1, "lapsed": 1, "dismissed": 0, "moved_on": 1, "open": 1,
                     "unattributed": 0}


def test_a_body_cached_under_the_old_reading_never_answers_for_the_new_one():
    """The scorecard is cached an hour; the acted rate changed its meaning (F76), so its key did too."""
    assert B._CACHE_KEY == "benchmarks:scorecard:v3"
