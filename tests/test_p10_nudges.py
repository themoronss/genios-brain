"""P10 nudges: the visible daily budget, the weekly manager profile, ask nudge timing, snooze,
reply drafts, the popup's Tomorrow / Draft reply actions, the weekly "nudged then closed" count, and
seat privacy on GET /graph + GET /graph/node/{id}.

Pure halves first; then real Postgres through the routes (fixtures from test_moments_pg).
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException
from sqlalchemy import text

from genios_engine.reason.moments import followups as F
from genios_engine.reason.moments import reply_draft as RD
from genios_engine.reason.moments import screen_insight as SI
from genios_engine.reason.moments import seat_profile as SP

IST = ZoneInfo("Asia/Kolkata")
URL = os.environ.get("GENIOS_TEST_DATABASE_URL")
pg = pytest.mark.skipif(not URL, reason="GENIOS_TEST_DATABASE_URL not set")


def _ist(y, m, d, h, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=IST).astimezone(timezone.utc)


# ── pure ──────────────────────────────────────────────────────────────────────────────────────
def test_ask_nudges_within_the_working_day():
    tz = "Asia/Kolkata"                                      # 2026-09-14 is a Monday
    assert F.nudge_at("ask", created_at=_ist(2026, 9, 14, 10), due_at=None,
                      tz_name=tz) == _ist(2026, 9, 14, 13)
    assert F.ask_nudge_at(_ist(2026, 9, 14, 16), tz) == _ist(2026, 9, 14, 18)     # capped 18:00
    assert F.ask_nudge_at(_ist(2026, 9, 14, 17, 30), tz) == _ist(2026, 9, 14, 18)
    assert F.ask_nudge_at(_ist(2026, 9, 14, 17, 31), tz) == _ist(2026, 9, 15, 9, 30)
    assert F.ask_nudge_at(_ist(2026, 9, 18, 18), tz) == _ist(2026, 9, 21, 9, 30)  # Fri → Mon
    assert F.ask_nudge_at(_ist(2026, 9, 14, 5), tz) == _ist(2026, 9, 14, 9, 30)   # never at dawn
    # other kinds unchanged
    fri = _ist(2026, 9, 18, 10)
    assert F.nudge_at("their_promise", created_at=fri, due_at=None, tz_name=tz) == \
        _ist(2026, 9, 22, 10)



def test_an_item_with_a_due_time_gets_a_heads_up_a_final_and_an_overdue_reminder():
    # P12 — "5:30 baje bhej dunga" typed at 11:00 → 4:30 heads-up, 5:20 final, 5:45 overdue.
    tz = "Asia/Kolkata"
    at11, due = _ist(2026, 9, 14, 11), _ist(2026, 9, 14, 17, 30)
    assert F.ladder("my_promise", created_at=at11, due_at=due) == [
        _ist(2026, 9, 14, 16, 30), _ist(2026, 9, 14, 17, 20), _ist(2026, 9, 14, 17, 45)]
    assert F.nudge_at("my_promise", created_at=at11, due_at=due, tz_name=tz) == _ist(2026, 9, 14, 16, 30)
    # An ask "within the hour": its due wins over the +3 h rule; too close for a heads-up.
    noon = _ist(2026, 9, 14, 12)
    assert F.ladder("ask", created_at=at11, due_at=noon) == [_ist(2026, 9, 14, 11, 50),
                                                             _ist(2026, 9, 14, 12, 15)]
    assert F.nudge_at("ask", created_at=at11, due_at=noon, tz_name=tz) == _ist(2026, 9, 14, 11, 50)
    # A same-day deadline used to get NO reminder (its day-before nudge had already passed).
    four = _ist(2026, 9, 14, 16)
    assert F.ladder("deadline", created_at=_ist(2026, 9, 14, 10), due_at=four) == [
        _ist(2026, 9, 14, 15), _ist(2026, 9, 14, 15, 50), _ist(2026, 9, 14, 16, 15)]
    # A deadline days away keeps the day-before heads-up.
    assert F.ladder("deadline", created_at=at11, due_at=_ist(2026, 9, 17, 17))[0] == _ist(2026, 9, 16, 17)
    # Seen 3 min before it is due → only the overdue step; seen long after → nothing at all.
    assert F.ladder("my_promise", created_at=due - timedelta(minutes=3), due_at=due) == [
        due + timedelta(minutes=15)]
    assert F.nudge_at("my_promise", created_at=due + timedelta(hours=2), due_at=due, tz_name=tz) is None
    # Their promises, undated items and risks keep their single nudge (or none).
    assert F.ladder("their_promise", created_at=at11, due_at=due) == []
    assert F.ladder("ask", created_at=at11, due_at=None) == []
    assert F.nudge_at("ask", created_at=_ist(2026, 9, 14, 10), due_at=None,
                      tz_name=tz) == _ist(2026, 9, 14, 13)


def test_remind_times_follow_the_ladder_unless_snoozed():
    at11, due = _ist(2026, 9, 14, 11), _ist(2026, 9, 14, 17, 30)
    row = SimpleNamespace(kind="my_promise", created_at=at11, due_at=due,
                          nudge_at=_ist(2026, 9, 14, 16, 30), snoozed_at=None)
    assert F.remind_times(row) == [_ist(2026, 9, 14, 16, 30), _ist(2026, 9, 14, 17, 20),
                                   _ist(2026, 9, 14, 17, 45)]
    # "Tomorrow" is the person's choice: only that time remains.
    row.snoozed_at, row.nudge_at = at11, _ist(2026, 9, 15, 9, 30)
    assert F.remind_times(row) == [_ist(2026, 9, 15, 9, 30)]
    ask = SimpleNamespace(kind="ask", created_at=at11, due_at=None, nudge_at=_ist(2026, 9, 14, 14),
                          snoozed_at=None)
    assert F.remind_times(ask) == [_ist(2026, 9, 14, 14)]
    assert F.remind_times(SimpleNamespace(kind="risk", created_at=at11, due_at=None,
                                          nudge_at=None, snoozed_at=None)) == []

def test_snooze_presets():
    tz = "Asia/Kolkata"
    mon3 = _ist(2026, 9, 14, 15)
    assert F.snooze_until("1h", now=mon3, tz_name=tz) == mon3 + timedelta(hours=1)
    assert F.snooze_until("tonight", now=mon3, tz_name=tz) == _ist(2026, 9, 14, 19)
    late = _ist(2026, 9, 14, 18, 30)
    assert F.snooze_until("tonight", now=late, tz_name=tz) == late + timedelta(hours=1)
    assert F.snooze_until("tomorrow", now=mon3, tz_name=tz) == _ist(2026, 9, 15, 9, 30)
    assert F.snooze_until("tomorrow", now=_ist(2026, 9, 18, 15), tz_name=tz) == \
        _ist(2026, 9, 21, 9, 30)
    with pytest.raises(ValueError):
        F.snooze_until("someday", now=mon3, tz_name=tz)


def test_popup_offers_tomorrow_and_draft_only_for_a_followup():
    res = SI.judge({"work": True, "items": [{"kind": "ask", "text": "Priya needs pricing",
                                             "quote": "revised pricing"}],
                    "adds": "repeat_ask", "note": "Priya asked again"},
                   "Priya: the revised pricing please")
    m = SI.moment_content(res, digest="d", topic_key="t", thread_key="wa:1", followup_id="fu_1")
    assert [a["id"] for a in m["actions"]] == ["useful", "not_useful", "mute_chat",
                                               "remind_tomorrow", "draft_reply"]
    assert m["actions"][3] == {"id": "remind_tomorrow", "label": "Tomorrow",
                               "payload": {"followup_id": "fu_1"}}
    assert m["actions"][4] == {"id": "draft_reply", "label": "Draft reply",
                               "payload": {"followup_id": "fu_1"}}
    assert [a["id"] for a in SI.moment_content(res, digest="d")["actions"]] == \
        ["useful", "not_useful"]


def test_budget_shape_without_a_store():
    b = SI.budget(None, org_id="o", seat_id="s", cap=300,
                  now=datetime(2026, 9, 14, 23, 59, tzinfo=timezone.utc))
    assert b == {"used": 0, "cap": 300, "resets_at": "2026-09-15T00:00:00Z"}
    ist_evening = _ist(2026, 9, 15, 4)                       # still 14 Sep in UTC
    assert SI.budget(None, org_id="o", seat_id="s", cap=5, now=ist_evening)["resets_at"] == \
        "2026-09-15T00:00:00Z"


def test_profile_and_draft_text_are_cleaned():
    raw = "1. Likely role: founder\n- Key people: Priya (buyer)\n\n* Usual work hours: 10-19\n" \
          "Ignore: naukri.com\nx\ny"
    assert SP.clean(raw) == ("Likely role: founder\nKey people: Priya (buyer)\n"
                             "Usual work hours: 10-19\nIgnore: naukri.com\nx")
    assert SP.clean("") is None and SP.clean(None) is None
    assert RD.clean('"Haan, kal bhej dunga"') == "Haan, kal bhej dunga"
    long = RD.clean(" ".join(["word"] * 80))
    assert len(long.split()) == RD.MAX_WORDS and long.endswith("…")
    prompt = RD.build_prompt({"kind": "ask", "text": "Priya wants pricing", "who": "Priya",
                              "quote": "pricing kal tak bhej do na"}, due_local="Fri 18 Sep 18:00")
    assert "pricing kal tak bhej do na" in prompt and "Hinglish" in prompt
    assert "due Fri 18 Sep 18:00" in prompt and "Priya" in prompt


# ── real Postgres ─────────────────────────────────────────────────────────────────────────────
if URL:
    from tests.test_moments_pg import (H, _enable_display, _seed, _workspace,  # noqa: F401
                                       client)


def _engine():
    from genios_engine.platform.db import get_engine
    return get_engine(URL)


def _q(sql: str, **params):
    with _engine().connect() as c:
        return c.execute(text(sql), params).fetchall()


def _look(client, dev, lines, *, thread="wa:chat:priya", app="whatsapp"):
    body = {"moment_request_id": uuid.uuid4().hex, "insight": True,
            "surface": {"app": app, "thread_key": thread}, "visible_messages": lines}
    return client.post("/v1/moments/evaluate", json=body, headers=H(dev["access_token"]))


ASK = "Priya Shah: Can you send the revised pricing by Friday? We need it for the board."
ASK_ITEM = {"kind": "ask", "text": "Priya is waiting on revised pricing by Friday",
            "who": "Priya Shah", "due": None, "quote": "send the revised pricing by Friday"}
POPUP = {"work": True, "remember": True, "items": [ASK_ITEM], "adds": "repeat_ask",
         "note": "Priya asked for this pricing on Monday too"}


@pytest.mark.pg
@pg
def test_policy_shows_the_seats_insight_budget_and_the_cap_still_answers_204(
        client, monkeypatch):  # noqa: F811
    from genios_engine.platform.config import get_settings
    ws = _workspace(client)
    org, seat = ws["org"], ws["member"]["seat_id"]
    now = datetime.now(timezone.utc)
    for _ in range(2):
        assert SI.reserve(_engine(), org_id=org, seat_id=seat, cap=300, now=now)
    doc = client.get("/v1/capture/policy", headers=H(ws["member"]["token"])).json()
    tomorrow = (now.date() + timedelta(days=1)).isoformat()
    assert doc["insight_budget"] == {"used": 2, "cap": 300,
                                     "resets_at": f"{tomorrow}T00:00:00Z"}
    owner = client.get("/v1/capture/policy", headers=H(ws["owner"]["token"])).json()
    assert owner["insight_budget"]["used"] == 0                     # per seat
    # a write answers the same document
    put = client.put("/v1/capture/settings", json={"enabled": True},
                     headers=H(ws["member"]["token"])).json()
    assert put["insight_budget"]["used"] == 2

    monkeypatch.setattr(get_settings(), "screen_insight_daily_cap", 2)
    monkeypatch.setattr(SI, "llm_insight",
                        lambda *a, **kw: pytest.fail("no model call over the daily cap"))
    assert _look(client, ws["member_dev"], [ASK]).status_code == 204
    capped = client.get("/v1/capture/policy", headers=H(ws["member"]["token"])).json()
    assert capped["insight_budget"]["used"] == 2 and capped["insight_budget"]["cap"] == 2


def _slice_version(org, seat) -> int:
    rows = _q("select version from seat_slice_versions where org_id=:o and seat_id=:s",
              o=org, s=seat)
    return int(rows[0].version) if rows else -1


@pytest.mark.pg
@pg
def test_popup_actions_snooze_and_draft(client, monkeypatch):  # noqa: F811
    ws = _workspace(client)
    _enable_display(client, ws)
    dev, org, seat = ws["member_dev"], ws["org"], ws["member"]["seat_id"]
    dev_h, seat_h = H(dev["access_token"]), H(ws["member"]["token"])
    with _engine().begin() as c:
        c.execute(text("update orgs set timezone='Asia/Kolkata' where id=:o"), {"o": org})
    client.get("/v1/seats/me/slice", headers=dev_h)            # the seat has a slice version
    monkeypatch.setattr(SP, "ensure_profile", lambda *a, **kw: None)
    monkeypatch.setattr(SI, "llm_insight", lambda *a, **kw: dict(POPUP))

    m = _look(client, dev, [ASK]).json()
    (fu,) = _q("select * from screen_followups where org_id=:o", o=org)
    assert [a["id"] for a in m["actions"]][-2:] == ["remind_tomorrow", "draft_reply"]
    assert m["actions"][-1]["payload"] == {"followup_id": fu.id}

    # snooze: Tomorrow → the next working day 09:30 in the seat's zone; slice bumped
    v0 = _slice_version(org, seat)
    r = client.post(f"/v1/followups/{fu.id}/snooze", json={"preset": "tomorrow"}, headers=dev_h)
    assert r.status_code == 200, r.text
    item = r.json()
    want = F.snooze_until("tomorrow", now=datetime.now(timezone.utc), tz_name="Asia/Kolkata")
    assert item["id"] == fu.id and item["resolution"] is None and "updated_at" in item
    assert datetime.fromisoformat(item["nudge_at"].replace("Z", "+00:00")) == want
    assert _slice_version(org, seat) > v0
    # a later sighting of the same topic keeps the snoozed nudge
    _look(client, dev, [ASK, "Priya Shah: please, it is urgent"])
    (again,) = _q("select nudge_at, snoozed_at from screen_followups where id=:i", i=fu.id)
    assert again.nudge_at == want and again.snoozed_at is not None

    until = (datetime.now(timezone.utc) + timedelta(hours=5)).replace(microsecond=0)
    r = client.post(f"/v1/followups/{fu.id}/snooze", json={"until": until.isoformat()},
                    headers=seat_h)
    assert r.status_code == 200 and r.json()["nudge_at"] == until.isoformat().replace(
        "+00:00", "Z")
    bad = [{"preset": "1h", "until": until.isoformat()}, {},
           {"until": (until - timedelta(days=1)).isoformat()},
           {"until": (until + timedelta(days=90)).isoformat()}, {"preset": "never"}]
    for body in bad:
        assert client.post(f"/v1/followups/{fu.id}/snooze", json=body,
                           headers=dev_h).status_code == 422, body
    assert client.post(f"/v1/followups/{fu.id}/snooze", json={"preset": "1h"},
                       headers=H(ws["owner_dev"]["access_token"])).status_code == 404
    assert client.post("/v1/followups/fu_nope/snooze", json={"preset": "1h"},
                       headers=dev_h).status_code == 404

    # draft: no model → 204; another seat → 404
    assert client.post(f"/v1/followups/{fu.id}/draft", headers=dev_h).status_code == 204
    assert client.post(f"/v1/followups/{fu.id}/draft",
                       headers=H(ws["owner"]["token"])).status_code == 404
    # a (fake) model: one T1 call, cost recorded as followup_draft, nothing stored
    from genios_engine.platform.config import get_settings
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "test-not-a-real-key")
    seen: dict = {}

    class _Resp:
        content = [SimpleNamespace(type="text", text='"Hi Priya, sending the revised pricing '
                                                     'by Friday evening."')]
        usage = SimpleNamespace(input_tokens=120, output_tokens=18)

    class _Client:
        def __init__(self, **kw):
            seen["client"] = kw
            self.messages = SimpleNamespace(create=self._create)

        def _create(self, **kw):
            seen["call"] = kw
            return _Resp()

    import anthropic
    monkeypatch.setattr(anthropic, "Anthropic", _Client)
    before = _q("select count(*) as n from screen_followups where org_id=:o", o=org)[0].n
    r = client.post(f"/v1/followups/{fu.id}/draft", headers=dev_h)
    assert r.status_code == 200, r.text
    assert r.json() == {"text": "Hi Priya, sending the revised pricing by Friday evening."}
    assert seen["client"]["timeout"] == RD.TIMEOUT_S and seen["client"]["max_retries"] == 0
    prompt = seen["call"]["messages"][0]["content"]
    assert ASK_ITEM["quote"] in prompt and "Priya Shah" in prompt
    (cost,) = _q("select purpose, input_tokens, output_tokens from llm_costs where org_id=:o "
                 "and purpose='followup_draft'", o=org)
    assert (cost.input_tokens, cost.output_tokens) == (120, 18)
    assert _q("select count(*) as n from screen_followups where org_id=:o", o=org)[0].n == before

    # resolved rows are never snoozed: the item answers its current state
    client.post(f"/v1/followups/{fu.id}/resolve", json={"resolution": "done"}, headers=dev_h)
    r = client.post(f"/v1/followups/{fu.id}/snooze", json={"preset": "1h"}, headers=dev_h).json()
    assert r["resolution"] == "done" and r["nudge_at"] == until.isoformat().replace("+00:00", "Z")


@pytest.mark.pg
@pg
def test_weekly_report_counts_what_closed_after_its_nudge(client):  # noqa: F811
    ws = _workspace(client, capture=False)
    org, seat = ws["org"], ws["member"]["seat_id"]
    now = datetime.now(timezone.utc)
    h = timedelta(hours=1)
    rows = {  # id: (kind, nudge_at, resolved_at, resolution)
        "ask_after": ("ask", now - 3 * h, now - h, "done"),
        "ask_answered_after": ("ask", now - 3 * h, now - 2 * h, "answered"),
        "promise_after": ("their_promise", now - 5 * h, now - 4 * h, "done"),
        "ask_before": ("ask", now + 3 * h, now - h, "done"),              # closed before the nudge
        "ask_dismissed": ("ask", now - 3 * h, now - h, "dismissed"),
        "risk_after": ("risk", now - 3 * h, now - h, "done"),              # risk is never nudged
        "ask_open": ("ask", now - 3 * h, None, None),
    }
    with _engine().begin() as c:
        for fid, (kind, nudge, resolved, res) in rows.items():
            c.execute(text(
                "insert into screen_followups (id, org_id, seat_id, kind, text, nudge_at, "
                "topic_key, created_at, resolved_at, resolution) values (:i, :o, :s, :k, 'n', "
                ":nu, :t, :cr, :r, :res)"),
                {"i": fid + org[-8:], "o": org, "s": seat, "k": kind, "nu": nudge, "t": fid,
                 "cr": now - 6 * h, "r": resolved, "res": res})
    rep = F.weekly_report(_engine(), org_id=org, seat_id=seat, capability_id=SI.CAPABILITY_ID,
                          now=now)
    # every row above resolved within the last 5 h — inside this week unless the week just began
    if F.week_bounds(None, tz_name="UTC", now=now)[1] <= now - 6 * h:
        assert rep["nudged_then_closed"] == 3
    last = F.weekly_report(_engine(), org_id=org, seat_id=seat, capability_id=SI.CAPABILITY_ID,
                           week_start=F.week_bounds(None, tz_name="UTC", now=now)[0]
                           - timedelta(days=14), now=now)
    assert last["nudged_then_closed"] == 0


@pytest.mark.pg
@pg
def test_the_weekly_profile_reads_only_the_seats_own_data(client, monkeypatch):  # noqa: F811
    ws = _workspace(client, capture=False)
    org, seat, other = ws["org"], ws["member"]["seat_id"], ws["owner"]["seat_id"]
    now = datetime.now(timezone.utc)
    with _engine().begin() as c:
        c.execute(text("update orgs set timezone='Asia/Kolkata' where id=:o"), {"o": org})
        for i, (s, who, kind) in enumerate([(seat, "Priya Shah", "ask"),
                                            (seat, "priya shah", "their_promise"),
                                            (seat, "Ravi Menon", "ask"),
                                            (other, "Secret Person", "ask")]):
            c.execute(text(
                "insert into screen_followups (id, org_id, seat_id, kind, text, who, topic_key, "
                "created_at) values (:i, :o, :s, :k, 'n', :w, :t, :cr)"),
                {"i": f"fu_p{i}{org[-6:]}", "o": org, "s": s, "k": kind, "w": who,
                 "t": f"tp{i}", "cr": _ist(2026, 9, 14, 11) if s == seat and i == 0
                 else now - timedelta(hours=2)})
        for s, t, w in [(seat, "site:naukri.com", False), (seat, "slack:ravi", True),
                        (other, "site:secret.example", False)]:
            c.execute(text("insert into screen_thread_verdicts (org_id, seat_id, thread_key, "
                           "work, judged_at) values (:o, :s, :t, :w, :now)"),
                      {"o": org, "s": s, "t": t, "w": w, "now": now})
    with _engine().connect() as c:
        facts = SP.gather(c, org_id=org, seat_id=seat, now=now)
    assert facts["people"][0] == {"who": "Priya Shah", "count": 2}
    assert [p["who"] for p in facts["people"]] == ["Priya Shah", "Ravi Menon"]
    assert facts["kinds"] == {"ask": 2, "their_promise": 1}
    assert facts["verdicts"] == {"work": 1, "personal": 1}
    assert facts["personal_threads"] == ["site:naukri.com"] and facts["tz"] == "Asia/Kolkata"
    assert sum(facts["hours"].values()) == 3
    prompt = SP.build_prompt(facts, email=ws["member"]["email"])
    assert "Secret Person" not in prompt and "secret.example" not in prompt
    assert "- Priya Shah · 2" in prompt and "Usual work hours" in prompt

    # no model → nothing built
    assert SP.build_if_stale(_engine(), org_id=org, seat_id=seat, email=None, now=now) is None
    calls: list = []
    monkeypatch.setattr(SP, "model_available", lambda: True)
    monkeypatch.setattr(SP, "t1_text", lambda engine, **kw: calls.append(kw) or (
        "- Likely role: founder selling to Acme\n- Key people: Priya Shah (buyer)\n"
        "- Usual work hours: 10:00-19:00\n- Ignore: naukri.com"))
    got = SP.build_if_stale(_engine(), org_id=org, seat_id=seat, email="m@x.test", now=now)
    assert got.splitlines()[0] == "Likely role: founder selling to Acme" and len(calls) == 1
    assert calls[0]["purpose"] == "screen_profile"
    with _engine().connect() as c:
        assert SP.profile_text(c, org_id=org, seat_id=seat) == got
        assert SP.profile_text(c, org_id=org, seat_id=other) is None
    # fresh → no second call; 9 days old → unread and rebuilt
    assert SP.build_if_stale(_engine(), org_id=org, seat_id=seat, email=None, now=now) is None
    assert len(calls) == 1
    with _engine().begin() as c:
        c.execute(text("update seat_profiles set built_at = :t where org_id=:o and seat_id=:s"),
                  {"t": now - timedelta(days=9), "o": org, "s": seat})
    with _engine().connect() as c:
        assert SP.profile_text(c, org_id=org, seat_id=seat) is None
    fut = SP.ensure_profile(_engine(), org_id=org, seat_id=seat, email=None, now=now)
    assert fut is not None
    fut.result(timeout=10)
    assert len(calls) == 2
    assert SP.ensure_profile(_engine(), org_id=org, seat_id=seat, email=None) is None  # memo
    with _engine().connect() as c:
        assert SP.profile_text(c, org_id=org, seat_id=seat) == got


@pytest.mark.pg
@pg
def test_screen_insight_schedules_the_profile_without_waiting(client, monkeypatch):  # noqa: F811
    ws = _workspace(client)
    seen: list = []
    monkeypatch.setattr(SP, "ensure_profile", lambda engine, **kw: seen.append(kw))
    monkeypatch.setattr(SI, "llm_insight", lambda *a, **kw: {
        "work": True, "remember": True, "items": [], "adds": "none", "note": None})
    assert _look(client, ws["member_dev"], [ASK], thread="wa:profile").status_code == 204
    assert [(k["org_id"], k["seat_id"]) for k in seen] == [(ws["org"], ws["member"]["seat_id"])]


# ── privacy: another seat's private screen data never reaches GET /graph ──────────────────────
@pytest.mark.pg
@pg
def test_graph_views_hide_another_seats_private_screen_data(client):  # noqa: F811
    from genios_engine.api import routes
    from genios_engine.context.graph_store import GraphStore
    from genios_engine.platform.auth import AuthCtx
    ws = _workspace(client, capture=False)
    n = _seed(ws)
    org = ws["org"]
    o_mail, m_mail = ws["owner"]["email"].lower(), ws["member"]["email"].lower()
    # an edge learned from the owner's private screen: Priya ↔ Ravi
    ev = f"evt_edge_{uuid.uuid4().hex[:8]}"
    with _engine().begin() as c:
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            "source_object_id, dedup_key, actor, occurred_at, visibility_scope, "
            "visibility_principals) values (:e, :o, 'conn', 'screen_session', 'message', :e, :e, "
            "'{}'::jsonb, now(), 'private', cast(:who as text[]))"),
            {"e": ev, "o": org, "who": [o_mail]})
        c.execute(text("insert into graph_edges (edge_version_id, edge_id, org_id, edge_type, "
                       "from_node_id, to_node_id, created_by_event_id) values "
                       "(:v, :e, :o, 'knows', :f, :t, :ev)"),
                  {"v": "ev_" + ev, "e": "e_" + ev, "o": org, "f": n["priya"], "t": n["acme"],
                   "ev": ev})

    owner = AuthCtx(org_id=org, seat_id=ws["owner"]["seat_id"], email=o_mail, source="jwt")
    member = AuthCtx(org_id=org, seat_id=ws["member"]["seat_id"], email=m_mail, source="jwt")
    api_key = AuthCtx(org_id=org, source="api_key")
    old = routes._graph
    routes._graph = GraphStore(URL)
    try:
        def graph(ctx):
            g = routes.graph_data(org_id=org, ctx=ctx)
            return ({x["id"] for x in g["nodes"]},
                    {(x["source"], x["target"], x["type"]) for x in g["links"]})

        o_nodes, o_links = graph(owner)
        m_nodes, m_links = graph(member)
        k_nodes, k_links = graph(api_key)
        assert n["ravi"] in o_nodes                        # the owner's own screen contact
        assert n["ravi"] not in m_nodes and n["ravi"] not in k_nodes
        assert o_nodes - m_nodes == {n["ravi"]}            # everything else is org business
        private_edge = (n["priya"], n["acme"], "knows")
        assert private_edge in o_links and private_edge not in m_links | k_links
        assert (n["priya"], n["acme"], "works_at") in m_links

        def detail(ctx, node):
            return routes.graph_node_detail(node, org_id=org, ctx=ctx)

        assert detail(owner, n["ravi"])["observations"][0]["kind"] == "mention:person"
        for ctx in (member, api_key):
            with pytest.raises(HTTPException) as e:
                detail(ctx, n["ravi"])
            assert e.value.status_code == 404
        mine, theirs = detail(owner, n["priya"]), detail(member, n["priya"])
        assert "Secret Buyer" in {f["value"] for f in mine["facts"]}
        assert "Secret Buyer" not in {f["value"] for f in theirs["facts"]}
        assert len(mine["observations"]) == 2 and len(theirs["observations"]) == 1
        knows = [r for r in theirs["relationships"] if r["edge_type"] == "knows"]
        assert knows == [] and [r for r in mine["relationships"] if r["edge_type"] == "knows"]
        # an org node linked to a hidden node: the link is not listed for the member
        with _engine().begin() as c:
            c.execute(text("insert into graph_edges (edge_version_id, edge_id, org_id, edge_type, "
                           "from_node_id, to_node_id) values (:v, :e, :o, 'mentioned', :f, :t)"),
                      {"v": "ev_m" + ev, "e": "e_m" + ev, "o": org, "f": n["acme"],
                       "t": n["ravi"]})
        # (an org-visible edge is readable evidence: Ravi is now known to the org)
        assert n["ravi"] in graph(member)[0]
    finally:
        routes._graph = old
