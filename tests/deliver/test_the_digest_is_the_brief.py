"""STEP-15 · one morning surface: the daily digest a Slack tenant receives IS the brief the seat kept.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/deliver/test_the_digest_is_the_brief.py

`deliver/outbox` (tree `yc2_w27_s15` M45.C3.L-integration.V0.U03; `03` s15-F4, s15-F14: four morning surfaces existed
and none read a file). The digest was `executive/summary.build_summary`'s count of signals, claimed once per UTC day at
whatever hour the six-hour heavy tick ran — *"Nothing needs you right now."* while the expert held a wait rule and a
question was open. Now it is the brief the account owner's seat has KEPT: its one line and today's five, nothing
else; claimed only once the brief is kept (until then the slot stays free); for the LOCAL day the brief belongs to,
not the UTC one; and read at the drain by the day the row was queued for, so a retry after midnight still sends the day
it was queued for. A tenant with only the pull surface (`in_app`) is queued nothing and reads the same brief on the
dashboard (`GET /v1/executive/morning`).
"""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from genios_engine.contracts import morning_brief as B
from genios_engine.contracts.execution import ChannelClass
from genios_engine.deliver import outbox
from genios_engine.deliver.channels.base import ChannelResult
from genios_engine.deliver.channels.slack import SlackWebhookChannel
from genios_engine.executive import morning_store
from genios_engine.executive.morning_template import template_brief

pytestmark = pytest.mark.pg

ORG, PULL_ORG = "org_s15_digest", "org_s15_digest_pull"
SEAT = "seat_owner"
TZ = "Asia/Kolkata"
AT = datetime(2026, 10, 6, 2, 40, tzinfo=timezone.utc)             # 08:10 in Kolkata, the 6th
HOOK = '{"webhook_url": "https://hooks.slack.com/services/T/B/x"}'


def _item(kind, about, *, words, **over):
    return B.Item(item_id=B.item_id_for(kind, about), kind=kind, about=about, subject=over.pop("subject", about),
                  material=B.Material(words=words), sources=(B.Source(B.SOURCE_REVIEW, f"{about}@fp"),), **over)


def _day():
    """Six decisions (five fit today; the sixth is quiet past 14 days and stuck), a file being watched, a change."""
    names = ["Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot"]
    decisions = [_item(B.DECISION, f"node_{n.lower()}", subject=n, stakes="high", urgency="high",
                       book_score_bp=9_000 - 100 * k, our_move=True, quiet_days=20.0 if n == "Foxtrot" else 2.0,
                       words=(("name", n), ("headline", f"Write to {n} about the pilot")))
                 for k, n in enumerate(names)]
    watched = _item(B.WATCHED, "node_golf", subject="Golf", quiet_days=30.0,
                    words=(("name", "Golf"), ("headline", "A deferral, wait for the milestone")))
    change = _item(B.CHANGE, "node_hotel:review", subject="Hotel",
                   words=(("name", "Hotel"), ("what", "Hotel wrote")))
    return tuple(decisions) + (watched, change)


def _brief(now=AT, seat=SEAT, org=ORG):
    return template_brief(org_id=org, seat_id=seat, items=_day(), now=now, tz=TZ)


@pytest.fixture
def world(monkeypatch):
    if not os.environ.get("GENIOS_TEST_DATABASE_URL"):
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the digest is claimed and read on Postgres")
    from genios_engine.platform.db import get_engine
    from genios_engine.platform.seats import ensure_owner_seat
    engine = get_engine(os.environ["GENIOS_TEST_DATABASE_URL"])
    with engine.begin() as c:
        for org in (ORG, PULL_ORG):
            c.execute(text("delete from orgs where id = :o"), {"o": org})
            c.execute(text("insert into orgs (id, name, email, timezone) values (:o, 'Arjun Rao', :e, :tz)"),
                      {"o": org, "e": f"{org}@example.test", "tz": TZ})
            ensure_owner_seat(c, org)
        c.execute(text("insert into org_channels (org_id, channel, config, active) values "
                       "(:o, 'slack', cast(:cfg as jsonb), true)"), {"o": ORG, "cfg": HOOK})
        c.execute(text("insert into org_channels (org_id, channel, config, active) values "
                       "(:o, 'in_app', cast('{}' as jsonb), true)"), {"o": PULL_ORG})
    sent: list[dict] = []
    monkeypatch.setattr(SlackWebhookChannel, "send",
                        lambda self, payload, config: sent.append(payload) or ChannelResult(ok=True))
    yield engine, sent
    with engine.begin() as c:
        for org in (ORG, PULL_ORG):
            c.execute(text("delete from orgs where id = :o"), {"o": org})


def _keep(engine, brief):
    with engine.begin() as c:
        return morning_store.keep(c, brief)[0]


def _digests(engine, org=ORG):
    with engine.connect() as c:
        return c.execute(text("select card_id, channel, status, attempts, last_error, next_attempt_at from "
                              "delivery_outbox where org_id = :o and card_id like 'digest:%' order by card_id"),
                         {"o": org}).all()


def _marker(engine):
    with engine.connect() as c:
        return c.execute(text("select last_digest_date from org_channels where org_id = :o and channel = 'slack'"),
                         {"o": ORG}).scalar()


def _bullets(message):
    return [l for l in message["blocks"][0]["text"]["text"].split("\n")[1:]]


def test_the_digest_waits_for_the_brief_and_the_slot_stays_free(world):
    engine, _sent = world
    assert outbox.enqueue_digest(engine, ORG, "slack", eval_time=AT) == 0       # nothing is kept: nothing to send
    assert _digests(engine) == [] and _marker(engine) is None                  # …and the day's slot is still free
    _keep(engine, _brief())
    assert outbox.enqueue_digest(engine, ORG, "slack", eval_time=AT) == 1      # kept: now it is claimed
    assert outbox.enqueue_digest(engine, ORG, "slack", eval_time=AT) == 0      # once a day
    ((card, channel, *_),) = _digests(engine)
    assert (card, channel) == ("digest:2026-10-06", "slack") and _marker(engine) == date(2026, 10, 6)


def test_an_org_with_no_owner_seat_has_no_brief_and_is_queued_nothing_without_breaking(world):
    engine, _sent = world
    bare = "org_s15_digest_bare"
    with engine.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": bare})
        c.execute(text("insert into orgs (id, name, email, timezone) values (:o, 'Arjun Rao', 'bare@example.test', :tz)"),
                  {"o": bare, "tz": TZ})
        c.execute(text("insert into org_channels (org_id, channel, config, active) values "
                       "(:o, 'slack', cast(:cfg as jsonb), true)"), {"o": bare, "cfg": HOOK})
    try:
        assert outbox.enqueue_digest(engine, bare, "slack", eval_time=AT) == 0      # nobody's brief: nothing to send
        assert _digests(engine, bare) == []
    finally:
        with engine.begin() as c:
            c.execute(text("delete from orgs where id = :o"), {"o": bare})


def test_the_digest_is_claimed_for_the_local_day_the_brief_belongs_to(world):
    engine, _sent = world
    late = datetime(2026, 10, 5, 20, 0, tzinfo=timezone.utc)                   # the 5th in UTC, 01:30 on the 6th here
    _keep(engine, _brief())
    assert outbox.enqueue_digest(engine, ORG, "slack", eval_time=late) == 1
    ((card, *_),) = _digests(engine)
    assert card == "digest:2026-10-06" and _marker(engine) == date(2026, 10, 6)  # never "digest:2026-10-05"


def test_the_digest_is_the_briefs_one_line_and_todays_five_and_nothing_else(world):
    engine, _sent = world
    brief = _keep(engine, _brief())
    today = brief.section(B.TODAY)
    assert len(today) == 5 and brief.section(B.STUCK) and brief.section(B.WATCHING) and brief.section(B.CHANGED)
    message = outbox._current_digest_payload(engine, ORG, AT, for_date=brief.local_date)
    assert message["text"].endswith(brief.one_line)
    assert _bullets(message) == [f"• {l.words}" for l in today]
    said = message["blocks"][0]["text"]["text"]
    for other in (*brief.section(B.STUCK), *brief.section(B.WATCHING), *brief.section(B.CHANGED)):
        assert other.words not in said                                           # one line and five, no more
    assert "open item" not in said and "right now" not in said                   # not the old signal count


def test_a_day_that_flexes_past_five_still_sends_the_five(world):
    """Seven decisions due within 48 hours are all always-in: today's five FLEXES to seven (`morning_order`) — the brief
    keeps all seven, and the digest is its one line and the five a Slack message holds."""
    engine, _sent = world
    due = tuple(_item(B.DECISION, f"node_due{n}", subject=f"Due{n}", stakes="high", urgency="high", our_move=True,
                      at=AT + timedelta(hours=3 + n), words=(("name", f"Due{n}"), ("headline", f"Reply to Due{n}")))
                for n in range(7))
    brief = _keep(engine, template_brief(org_id=ORG, seat_id=SEAT, items=due, now=AT, tz=TZ))
    today = brief.section(B.TODAY)
    assert len(today) == 7 and brief.flexed == 2
    message = outbox._current_digest_payload(engine, ORG, AT, for_date=brief.local_date)
    assert _bullets(message) == [f"• {l.words}" for l in today[:5]]


def test_a_queued_digest_sends_the_day_it_was_queued_for_even_when_drained_after_midnight(world):
    engine, sent = world
    brief = _keep(engine, _brief())
    assert outbox.enqueue_digest(engine, ORG, "slack", eval_time=AT) == 1
    with engine.begin() as c:
        c.execute(text("update delivery_outbox set next_attempt_at = :t where org_id = :o and card_id like 'digest:%'"),
                  {"t": AT, "o": ORG})
    next_day = AT + timedelta(days=1)                                           # the 7th: no brief is kept for it
    out = outbox.drain(engine, eval_time=next_day, limit=10)
    assert out["delivered"] == 1 and len(sent) == 1
    assert sent[0]["text"].endswith(brief.one_line)
    assert _bullets(sent[0]) == [f"• {l.words}" for l in brief.section(B.TODAY)]
    ((_card, _ch, status, *_),) = _digests(engine)
    assert status == "delivered"


def test_a_digest_with_no_kept_brief_is_retried_never_sent_from_a_count(world):
    engine, sent = world
    with engine.begin() as c:                                                   # a row from before the brief: no day kept
        c.execute(text("insert into delivery_outbox (id, org_id, card_id, channel, payload, channel_class, delivery_id, "
                       "next_attempt_at) values ('ob_old_digest', :o, 'digest:2026-09-01', 'slack', "
                       "cast(:p as jsonb), :cc, 'ob_old_digest', :t)"),
                  {"o": ORG, "t": AT, "cc": ChannelClass.DIGEST.value,
                   "p": '{"kind": "daily_digest_intent", "for_date": "2026-09-01"}'})
    out = outbox.drain(engine, eval_time=AT + timedelta(minutes=1), limit=10)
    assert out["delivered"] == 0 and sent == []
    ((_card, _ch, status, attempts, error, _next),) = _digests(engine)
    assert status == "queued" and attempts == 1 and "no morning brief" in error


def test_a_tenant_with_only_the_pull_surface_is_queued_nothing_and_reads_the_brief_on_the_dashboard(world, monkeypatch):
    from genios_engine.api import executive_routes as R
    from genios_engine.platform import auth
    from genios_engine.platform.auth import AuthCtx, get_auth_ctx
    engine, _sent = world

    class _Graph:
        pass
    graph = _Graph()
    graph.engine = engine
    monkeypatch.setattr(R, "_graph", graph)
    monkeypatch.setattr(R, "_now", lambda: AT + timedelta(minutes=30))
    monkeypatch.setattr(auth, "check_org_kill", lambda org_id: None)
    app = FastAPI()
    app.include_router(R.router)
    app.dependency_overrides[get_auth_ctx] = lambda: AuthCtx(org_id=PULL_ORG, seat_id=SEAT, role="owner", source="jwt")

    totals = outbox.run_distribution(engine, eval_time=AT + timedelta(minutes=30), base_url="")
    assert _digests(engine, PULL_ORG) == [] and totals["digests"] == 0          # no push channel: no digest row
    served = TestClient(app).get("/v1/executive/morning").json()
    assert served["state"] == "today" and served["one_line"]                      # …it is on the dashboard instead
    with engine.connect() as c:
        kept = morning_store.read(c, PULL_ORG, SEAT, date(2026, 10, 6))
    assert kept is not None and served["one_line"] == kept.one_line                # the one brief, both surfaces
