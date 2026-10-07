"""STEP-06 · one way to expire a card — and every expiry says why.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/platform/test_card_lifecycle.py -q

Tree `yc2_w27_s06 · M24.C1.L-contract.V0.U01`. Eleven places set a card `expired` and nine of them wrote
nothing (`speedrun008/YC-II W27/` STEP-06 §8.2): History showed the card gone and no reason. From
STEP-06 on, `platform/card_lifecycle` is the only writer of that state, and it writes one
`card_events` row per card it moved, in the caller's transaction, with a cause from a closed
vocabulary.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest

ORG = "card_lifecycle_org"
OTHER = "card_lifecycle_other"
AT = datetime(2026, 10, 7, 9, 0, tzinfo=timezone.utc)


def _reset(eng):
    from sqlalchemy import text
    with eng.begin() as c:
        for org in (ORG, OTHER):
            for table in ("card_events", "cards", "signals"):
                c.execute(text(f"delete from {table} where org_id = :o"), {"o": org})
            c.execute(text("delete from orgs where id = :o"), {"o": org})


@pytest.fixture
def engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    from sqlalchemy import create_engine, text
    eng = create_engine(url)
    _reset(eng)
    with eng.begin() as c:
        for org in (ORG, OTHER):
            c.execute(text("insert into orgs (id, name, email) values (:o, :o, :e)"),
                      {"o": org, "e": f"founder@{org}.test"})
        # One card per signal (`cards_one_per_signal`, migration 0008).
        for org, sig in [(ORG, "sig_q"), (ORG, "sig_c"), (ORG, "sig_acted"), (ORG, "sig_b"),
                         (ORG, "sig_l"), (ORG, "sig_lc"), (OTHER, "sig_x")]:
            c.execute(text("insert into signals (signal_id, org_id, rule_id, subject_node_id, score, "
                           "reason_code, eval_time) values (:s, :o, 'r1', 'n1', 50, 'rc', :t)"),
                      {"s": sig, "o": org, "t": AT})
        for org, card, sig, state, expires in [
                (ORG, "c_queued", "sig_q", "queued", AT + timedelta(days=3)),
                (ORG, "c_claimed", "sig_c", "claimed", AT + timedelta(days=3)),
                (ORG, "c_acted", "sig_acted", "acted", AT + timedelta(days=3)),
                (ORG, "c_other_sig", "sig_b", "surfaced", AT + timedelta(days=3)),
                (ORG, "c_lapsed", "sig_l", "snoozed", AT - timedelta(hours=1)),
                (ORG, "c_lapsed_claimed", "sig_lc", "claimed", AT - timedelta(hours=1)),
                (OTHER, "c_x", "sig_x", "queued", AT + timedelta(days=3))]:
            c.execute(text(
                "insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, "
                "situation, score, why, actions, artifact, state, expires_at) values "
                "(:c, :s, :o, 'review', 'low', 'h', 's', 10, cast('[]' as jsonb), "
                "cast('[]' as jsonb), cast('{}' as jsonb), :st, :exp)"),
                {"c": card, "s": sig, "o": org, "st": state, "exp": expires})
    yield eng
    _reset(eng)


def _state(eng, card):
    from sqlalchemy import text
    with eng.connect() as c:
        return c.execute(text("select state from cards where card_id = :c"), {"c": card}).scalar()


def _events(eng, card):
    from sqlalchemy import text
    with eng.connect() as c:
        return [dict(r) for r in c.execute(text(
            "select kind, cause, actor_id, detail from card_events where card_id = :c "
            "order by occurred_at, id"), {"c": card}).mappings()]


def test_the_open_cards_of_a_signal_expire_and_each_says_why(engine):
    from genios_engine.platform import card_lifecycle as cl
    with engine.begin() as c:
        moved = cl.expire_cards(c, org_id=ORG, signal_ids=["sig_q", "sig_c", "sig_acted"],
                                cause=cl.REPLACED)
    assert sorted(moved) == ["c_claimed", "c_queued"]
    for card, sig in [("c_claimed", "sig_c"), ("c_queued", "sig_q")]:
        assert _state(engine, card) == "expired"
        [event] = _events(engine, card)
        assert (event["kind"], event["cause"], event["actor_id"]) == ("card.expired", "replaced",
                                                                      "system")
        assert event["detail"]["signal_id"] == sig
    # a card somebody already decided is not touched, and says nothing new
    assert _state(engine, "c_acted") == "acted" and _events(engine, "c_acted") == []
    # nor is another signal's card, or another tenant's
    assert _state(engine, "c_other_sig") == "surfaced"
    assert _state(engine, "c_x") == "queued"


def test_cards_by_id_keep_the_callers_kind_actor_and_detail(engine):
    from genios_engine.platform import card_lifecycle as cl
    with engine.begin() as c:
        moved = cl.expire_cards(c, org_id=ORG, card_ids=["c_other_sig"], cause=cl.EXTENSION,
                                kind=cl.DISMISSED, actor="seat_1", detail={"via": "extension"})
    assert moved == ["c_other_sig"]
    [event] = _events(engine, "c_other_sig")
    assert (event["kind"], event["cause"], event["actor_id"]) == ("card.dismissed", "extension",
                                                                  "seat_1")
    assert event["detail"] == {"via": "extension", "signal_id": "sig_b"}


def test_a_card_id_of_another_tenant_is_never_moved(engine):
    from genios_engine.platform import card_lifecycle as cl
    with engine.begin() as c:
        assert cl.expire_cards(c, org_id=ORG, card_ids=["c_x"], cause=cl.REPLACED) == []
    assert _state(engine, "c_x") == "queued" and _events(engine, "c_x") == []


def test_the_callers_transaction_owns_both_the_move_and_the_reason(engine):
    from genios_engine.platform import card_lifecycle as cl
    with engine.connect() as c:
        tx = c.begin()
        cl.expire_cards(c, org_id=ORG, signal_ids=["sig_q"], cause=cl.REPLACED)
        tx.rollback()
    assert _state(engine, "c_queued") == "queued" and _events(engine, "c_queued") == []


def test_the_lapse_sweep_says_window_lapsed_and_leaves_a_claimed_card_alone(engine):
    from genios_engine.platform import card_lifecycle as cl
    with engine.begin() as c:
        lapsed = cl.expire_lapsed(c, now=AT)
    assert ("c_lapsed", ORG) in lapsed
    assert _state(engine, "c_lapsed") == "expired"
    [event] = _events(engine, "c_lapsed")
    assert (event["kind"], event["cause"]) == ("window.lapsed", "expired")
    assert _state(engine, "c_lapsed_claimed") == "claimed"      # the sweep's states, as before
    assert _state(engine, "c_queued") == "queued"               # not yet past its window


def test_an_unknown_cause_or_kind_is_refused_before_anything_moves(engine):
    from genios_engine.platform import card_lifecycle as cl
    with engine.begin() as c:
        with pytest.raises(ValueError):
            cl.expire_cards(c, org_id=ORG, signal_ids=["sig_q"], cause="because")
        with pytest.raises(ValueError):
            cl.expire_cards(c, org_id=ORG, signal_ids=["sig_q"], cause=cl.REPLACED,
                            kind="card.vanished")
    assert _state(engine, "c_queued") == "queued"


def test_nothing_named_is_nothing_done(engine):
    from genios_engine.platform import card_lifecycle as cl
    with engine.begin() as c:
        assert cl.expire_cards(c, org_id=ORG, cause=cl.REPLACED) == []
    assert _state(engine, "c_queued") == "queued"


def test_the_vocabulary_is_closed_and_every_cause_is_named_once():
    from genios_engine.platform import card_lifecycle as cl
    assert cl.CAUSES == {cl.REPLACED, cl.RULE_CLEARED, cl.BUDGET_HELD, cl.NOT_AUTHORIZED,
                         cl.PLAN_GONE, cl.RULE_MUTED, cl.LAPSED, cl.EXTENSION, cl.SUBJECT_IS_US}
    assert cl.KINDS == {cl.EXPIRED, cl.LAPSED_KIND, cl.DISMISSED, cl.RETIRED}
