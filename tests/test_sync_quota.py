"""The ingestion meter, on real Postgres.

Sync is NOT charged in credits. One email costs ~1.3 credits to process (the L2 extraction prompt
is ~2,950 tokens), so a 3,000-message mailbox would burn ~4,000 credits before the product had
answered a single question — and it would bill the customer for how much mail other people send
them. Ingestion is included in the plan and bounded by a message count instead.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.skipif(
    not os.environ.get("GENIOS_TEST_DATABASE_URL"),
    reason="GENIOS_TEST_DATABASE_URL not set")


def _engine():
    from genios_engine.context.graph_store import GraphStore
    from genios_engine.platform.migrate import apply_migrations
    url = os.environ["GENIOS_TEST_DATABASE_URL"]
    apply_migrations(database_url=url)
    return GraphStore(url).engine


def _org(engine, org, tier, *, period_days_ago=1, first_period=False):
    """`first_period=False` by default: most tests are about the ORDINARY monthly quota, and the
    one-time history-import allowance would otherwise silently inflate every limit they assert."""
    now = datetime.now(timezone.utc)
    born = now if first_period else now - timedelta(days=period_days_ago + 60)
    with engine.begin() as c:
        c.execute(text(
            "insert into orgs (id,name,subscription_tier,plan_status,credit_period_start,created_at) "
            "values (:o,'S',:t,'active',:s,:b) on conflict (id) do update "
            "set subscription_tier=:t, credit_period_start=:s, created_at=:b"),
            {"o": org, "t": tier, "s": now - timedelta(days=period_days_ago), "b": born})
        c.execute(text("delete from source_events where org_id=:o"), {"o": org})


def _capture(engine, org, n, *, days_ago=0):
    now = datetime.now(timezone.utc) - timedelta(days=days_ago)
    with engine.begin() as c:
        for i in range(n):
            c.execute(text(
                "insert into source_events (event_id,org_id,connection_id,source,object_type,"
                "source_object_id,dedup_key,actor,occurred_at,captured_at) values "
                "(:e,:o,'c1','gmail','message',:s,:d,'{}'::jsonb,:t,:t)"),
                {"e": f"{org}_ev_{days_ago}_{i}", "o": org, "s": f"m{i}",
                 "d": f"{org}_{days_ago}_{i}", "t": now})


def test_a_fresh_account_has_its_whole_quota():
    from genios_engine.platform import billing as B
    from genios_engine.platform.quota import sync_status
    engine = _engine()
    _org(engine, "q_fresh", "trial")
    s = sync_status(engine, "q_fresh")
    assert s["used"] == 0
    assert s["limit"] == B.PLANS["trial"].sync_messages
    assert s["exhausted"] is False


def test_captured_messages_are_counted():
    from genios_engine.platform.quota import messages_used
    engine = _engine()
    _org(engine, "q_count", "trial")
    _capture(engine, "q_count", 25)
    assert messages_used(engine, "q_count") == 25


def test_the_meter_resets_with_the_billing_period_not_the_calendar():
    """A plan bought on the 28th must not get two days of quota for its first month."""
    from genios_engine.platform.quota import messages_used
    engine = _engine()
    _org(engine, "q_period", "startup", period_days_ago=2)
    _capture(engine, "q_period", 10, days_ago=30)          # last period
    _capture(engine, "q_period", 4)                        # this period
    assert messages_used(engine, "q_period") == 4


def test_a_full_meter_is_exhausted_and_has_no_headroom():
    from genios_engine.platform import billing as B
    from genios_engine.platform.quota import sync_headroom, sync_status
    engine = _engine()
    _org(engine, "q_full", "trial")
    _capture(engine, "q_full", B.PLANS["trial"].sync_messages)
    assert sync_status(engine, "q_full")["exhausted"] is True
    assert sync_headroom(engine, "q_full") == 0


def test_headroom_is_what_is_left_not_the_whole_limit():
    from genios_engine.platform import billing as B
    from genios_engine.platform.quota import sync_headroom
    engine = _engine()
    _org(engine, "q_part", "trial")
    _capture(engine, "q_part", 40)
    assert sync_headroom(engine, "q_part") == B.PLANS["trial"].sync_messages - 40


def test_a_bigger_plan_buys_a_bigger_mailbox():
    from genios_engine.platform.quota import sync_status
    engine = _engine()
    _org(engine, "q_small", "trial")
    _org(engine, "q_big", "startup")
    assert sync_status(engine, "q_big")["limit"] > sync_status(engine, "q_small")["limit"]


def test_an_old_tier_name_does_not_silently_shrink_the_mailbox():
    from genios_engine.platform import billing as B
    from genios_engine.platform.quota import sync_status
    engine = _engine()
    _org(engine, "q_early", "early")
    assert sync_status(engine, "q_early")["limit"] == B.PLANS["individual"].sync_messages


def test_ingesting_never_moves_the_credit_balance():
    """The whole point of the second meter."""
    from genios_engine.platform import billing as B
    from genios_engine.platform.quota import messages_used
    engine = _engine()
    _org(engine, "q_credits", "startup")
    with engine.begin() as c:
        c.execute(text("update orgs set credits=500 where id=:o"), {"o": "q_credits"})
        before = B.balance(c, "q_credits")["balance"]
    _capture(engine, "q_credits", 200)
    with engine.connect() as c:
        assert B.balance(c, "q_credits")["balance"] == before
    assert messages_used(engine, "q_credits") == 200


def test_an_unreadable_meter_fails_open():
    """A quota that cannot be read must never be the reason a customer's mail stops arriving."""
    from genios_engine.platform.quota import messages_used

    class _Broken:
        def connect(self):
            raise RuntimeError("db down")

    assert messages_used(_Broken(), "whoever") == 0


# ── the first sync is not a month ────────────────────────────────────────────────────────────
#
# Connecting a mailbox imports history: two months of mail is ~5,000 messages against an ongoing
# ~1,800/month. A monthly quota big enough to absorb that is twelve times too big for every month
# after it; one sized for the steady state refuses the import that makes the product work.

def test_a_new_account_gets_the_history_import_allowance():
    from genios_engine.platform import billing as B
    from genios_engine.platform.quota import sync_status
    engine = _engine()
    _org(engine, "q_first", "individual", first_period=True)
    s = sync_status(engine, "q_first")
    assert s["first_period"] is True
    assert s["limit"] == (B.PLANS["individual"].sync_messages
                          + B.PLANS["individual"].backfill_messages)
    assert s["backfill_included"] == B.PLANS["individual"].backfill_messages


def test_the_import_allowance_lapses_when_the_period_rolls():
    """It is one-time. An account in month two gets the ordinary monthly quota and nothing more."""
    from genios_engine.platform import billing as B
    from genios_engine.platform.quota import sync_status
    engine = _engine()
    _org(engine, "q_second", "individual", period_days_ago=2)   # born long before this period
    s = sync_status(engine, "q_second")
    assert s["first_period"] is False
    assert s["limit"] == B.PLANS["individual"].sync_messages
    assert s["backfill_included"] == 0


def test_two_months_of_a_real_mailbox_fits_the_first_sync():
    """The scenario this allowance exists for: ~5,000 messages of history on a paid plan."""
    from genios_engine.platform.quota import sync_headroom
    engine = _engine()
    _org(engine, "q_import", "individual", first_period=True)
    _capture(engine, "q_import", 5_000)
    assert sync_headroom(engine, "q_import") > 0, "a 2-month import must not exhaust month one"


def test_every_plan_can_import_more_than_it_ingests_in_a_month():
    from genios_engine.platform import billing as B
    for tier, plan in B.PLANS.items():
        assert plan.backfill_messages >= plan.sync_messages, tier
