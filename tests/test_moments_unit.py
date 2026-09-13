"""P3 hot lane — the pure halves (no database): guards, the realtime cursor, SSE framing and the
stream generator, the P-02 composer, slice helpers, and `moments_display` in the policy document.
`tests/test_moments_pg.py` runs the SQL and the routes."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from genios_engine.api.moment_routes import Principal
from genios_engine.api.stream_routes import event_stream
from genios_engine.platform import capture_policy as P
from genios_engine.platform import realtime
from genios_engine.reason.moments import guards as G
from genios_engine.reason.moments import slice as S
from genios_engine.reason.moments.common import parse_ts
from genios_engine.reason.moments.recall import Subject, SubjectRead, compose

NOW = datetime(2026, 9, 17, 5, 0, tzinfo=timezone.utc)          # 10:30 IST


# ── guards ────────────────────────────────────────────────────────────────────────────────────
def test_shadow_is_the_default_and_is_reported_first():
    assert G.decide(G.GuardState(), kind="advice", priority="normal", now=NOW) == (False, G.SHADOW)
    st = G.GuardState(moments_display=False, dnd=True, shown_hour=99)
    assert G.decide(st, kind="advice", priority="critical", now=NOW) == (False, G.SHADOW)


def test_dnd_rate_limits_and_the_reminder_exemption():
    on = G.GuardState(moments_display=True)
    assert G.decide(on, kind="advice", priority="normal", now=NOW) == (True, None)
    dnd = G.GuardState(moments_display=True, dnd=True)
    assert G.decide(dnd, kind="advice", priority="high", now=NOW) == (False, G.DND)
    assert G.decide(dnd, kind="advice", priority="critical", now=NOW) == (True, None)
    hour = G.GuardState(moments_display=True, shown_hour=6)
    assert G.decide(hour, kind="advice", priority="normal", now=NOW) == (False, G.RATE_HOUR)
    assert G.decide(hour, kind="reminder", priority="normal", now=NOW) == (True, None)
    day = G.GuardState(moments_display=True, shown_hour=1, shown_day=30)
    assert G.decide(day, kind="verify", priority="high", now=NOW) == (False, G.RATE_DAY)


def test_quiet_hours_apply_only_when_configured():
    assert G.quiet_profile(None, "Asia/Kolkata") is None
    assert G.quiet_profile({"quiet_enabled": None}, None) is None
    prof = G.quiet_profile({"quiet_enabled": True, "quiet_start_hour": 9,
                            "quiet_end_hour": 12}, "Asia/Kolkata")
    st = G.GuardState(moments_display=True, quiet=prof)
    assert G.decide(st, kind="advice", priority="normal", now=NOW) == (False, G.QUIET)
    assert G.decide(st, kind="reminder", priority="normal", now=NOW) == (True, None)
    assert G.decide(st, kind="advice", priority="critical", now=NOW) == (True, None)


# ── realtime ──────────────────────────────────────────────────────────────────────────────────
def _ev(seq, org="o1", seat="s1", kind="moment.new", payload=None):
    return {"seq": seq, "org_id": org, "seat_id": seat, "kind": kind, "payload": payload or {}}


def test_a_late_commit_below_the_cursor_is_still_delivered_once():
    hub = realtime.Hub(engine_factory=lambda: None)
    hub._last = 0
    assert [e["seq"] for e in hub.ingest([_ev(1), _ev(3)], now_s=0)] == [1, 3]
    assert hub.floor() == 1                               # seq 2 is a gap: re-read from 1
    assert [e["seq"] for e in hub.ingest([_ev(2), _ev(3)], now_s=1)] == [2]
    assert hub.floor() == 3
    hub.ingest([_ev(5)], now_s=2)
    assert hub.floor() == 3
    hub.ingest([], now_s=2 + realtime.GAP_WAIT_S + 1)     # a rolled-back writer's gap expires
    assert hub.floor() == 5


def test_subscribers_filter_by_seat_org_and_revoked_device():
    loop = asyncio.new_event_loop()
    try:
        dev = realtime.Subscriber(org_id="o1", seat_id="s1", device_id="d1", loop=loop)
        web = realtime.Subscriber(org_id="o1", seat_id="s1", device_id=None, loop=loop)
        assert dev.wants(_ev(1)) and not dev.wants(_ev(1, seat="s2"))
        assert dev.wants(_ev(1, seat=None, kind="policy.updated"))
        assert not dev.wants(_ev(1, org="o2", seat=None))
        revoked_other = _ev(2, kind="device.revoked", payload={"device_id": "d9"})
        assert not dev.wants(revoked_other) and web.wants(revoked_other)
    finally:
        loop.close()


def test_sse_frame_matches_plan_18_3():
    frame = realtime.sse_format(_ev(88213, payload={"moment_id": "mom_1", "kind": "team"}))
    assert frame == ('id: 88213\nevent: moment.new\n'
                     'data: {"moment_id":"mom_1","kind":"team"}\n\n')


def test_the_stream_generator_delivers_heartbeats_and_ends_on_revocation():
    async def run() -> list[str]:
        hub = realtime.Hub(engine_factory=lambda: None)
        p = Principal("o1", "s1", "d1", "a@x.test", None)
        gen = event_stream(p, engine=None, last_event_id=None, hub=hub, heartbeat_s=0.05, max_s=5)
        out = [await gen.__anext__()]                       # retry:
        out.append(await gen.__anext__())                   # heartbeat (nothing queued)
        hub._last = 0
        hub.dispatch(_ev(7, payload={"moment_id": "m"}))
        hub.dispatch(_ev(8, kind="device.revoked", payload={"device_id": "d1"}))
        async for frame in gen:
            if not frame.startswith(":"):
                out.append(frame)
        hub.stop()
        return out
    frames = asyncio.run(run())
    assert frames[0].startswith("retry:") and frames[1] == ": hb\n\n"
    assert frames[2].startswith("id: 7\nevent: moment.new")
    assert frames[3].startswith("id: 8\nevent: device.revoked")
    assert len(frames) == 4                                 # the stream ended after revocation


# ── P-02 composer ─────────────────────────────────────────────────────────────────────────────
def _read(**kw) -> SubjectRead:
    r = SubjectRead(subject=Subject("n1", "person", "Priya Shah"))
    r.nodes = {"n1": ("person", "Priya Shah"), "n7": ("company", "Acme Logistics"),
               "d1": ("deal", "Acme deal"), "c1": ("commitment", "send proposal")}
    r.company = "n7"
    r.facts = {"d1": {"deal.stage": ("negotiation", NOW)},
               "c1": {"commitment.text": ("send the revised proposal", NOW),
                      "commitment.owed_to": ("Priya Shah", NOW),
                      "commitment.due_at": ((NOW - timedelta(days=1)).isoformat(), NOW)}}
    r.seat_commitments = ["c1"]
    r.last_touch_at = NOW - timedelta(days=12)
    for k, v in kw.items():
        setattr(r, k, v)
    return r


def test_recall_says_who_when_and_what_is_owed():
    m = compose(_read(), now=NOW)
    assert m["capability_id"] == "moment.counterparty_recall" and m["kind"] == "advice"
    assert m["headline"] == "Priya Shah · Acme Logistics — last touch 12 d ago"
    assert m["body"].startswith("You owe: send the revised proposal (overdue since")
    assert "Deal: negotiation" in m["body"]
    assert m["priority"] == "high"
    assert {"node_id": "n1", "field": "last_touch_at"}.items() <= m["evidence"][0].items()


def test_recall_is_silent_for_a_teammate_or_an_empty_subject():
    assert compose(_read(internal=True), now=NOW) is None
    bare = SubjectRead(subject=Subject("n2", "person", "Nobody"))
    assert compose(bare, now=NOW) is None


# ── slice helpers + policy ────────────────────────────────────────────────────────────────────
def test_slice_helpers():
    blocks = [(NOW, NOW + timedelta(hours=1)), (NOW + timedelta(minutes=30), NOW + timedelta(hours=2)),
              (NOW + timedelta(hours=5), NOW + timedelta(hours=6))]
    assert len(S._merge_busy(blocks)) == 2
    assert S.version_instant(int(NOW.timestamp() * 1000)) == NOW
    assert parse_ts({"dateTime": "2026-09-18T15:00:00+05:30"}) == datetime(
        2026, 9, 18, 9, 30, tzinfo=timezone.utc)
    assert parse_ts('"2026-09-18"') == datetime(2026, 9, 18, tzinfo=timezone.utc)


def test_moments_display_is_in_the_policy_document_and_off_by_default():
    doc = P.policy_document(P.OrgPolicy(), P.SeatSettings(), now=NOW)
    assert doc["org"]["moments_display"] is False and doc["effective"]["moments_display"] is False
    on = P.policy_document(P.OrgPolicy(moments_display=True), P.SeatSettings(), now=NOW)
    assert on["org"]["moments_display"] is True and on["policy_version"] != doc["policy_version"]
    row = {"p_enabled": True, "moments_display": True, "moments_max_per_hour": 2}
    org = P._org_from_row(row)
    assert (org.moments_display, org.moments_max_per_hour, org.moments_max_per_day) == (True, 2, 30)
