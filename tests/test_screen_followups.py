"""P8 manager value, brain side (SCREEN_INTEL_MANAGER_VALUE_BUILD C1–C6, C8) + P9 K1, K4, K5
(SCREEN_INTEL_COST_RELEVANCE_BUILD: memory in the one call, not-useful mutes + examples, expiry).

Pure halves first (kind mapping, nudge clocks incl. working days, topic key, due parsing, the
structural "ask answered" test, the v2 model answer, popup actions), then real-Postgres flows
through the routes: popup → follow-up → repeat (204, refreshed) → answered → slice delta; the
hourly popup budget (queued_for_brief, follow-up still written); work:false (no popup, personal
verdict, memory parked); resolve / list / expiry; the weekly report.
"""
from __future__ import annotations

import os
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import text

from genios_engine.reason.moments import followups as F
from genios_engine.reason.moments import screen_insight as SI

IST = ZoneInfo("Asia/Kolkata")
URL = os.environ.get("GENIOS_TEST_DATABASE_URL")
pg = [pytest.mark.pg, pytest.mark.skipif(not URL, reason="GENIOS_TEST_DATABASE_URL not set")]


# ── pure ──────────────────────────────────────────────────────────────────────────────────────
def test_kind_mapping():
    assert F.map_kind("ask", None) == "ask"
    assert F.map_kind("commitment", "me") == "my_promise"
    assert F.map_kind("Commitment", "them") == "their_promise"
    assert F.map_kind("commitment", None) is None          # nobody owns it → no follow-up
    for k in ("deadline", "risk", "next_step"):
        assert F.map_kind(k, "me") == k
    assert F.map_kind("gossip", None) is None


def test_nudge_clocks_and_working_days():
    fri = datetime(2026, 9, 18, 10, 0, tzinfo=IST).astimezone(timezone.utc)   # Friday 10:00 IST
    due = fri + timedelta(days=1)
    assert F.nudge_at("ask", created_at=fri, due_at=None, tz_name="Asia/Kolkata") == \
        fri + timedelta(hours=3)
    assert F.nudge_at("my_promise", created_at=fri, due_at=due, tz_name="Asia/Kolkata") == \
        due - timedelta(minutes=60)
    # undated: +3 working days from Friday is Wednesday, same local time
    assert F.nudge_at("my_promise", created_at=fri, due_at=None, tz_name="Asia/Kolkata") == \
        datetime(2026, 9, 23, 10, 0, tzinfo=IST)
    assert F.nudge_at("their_promise", created_at=fri, due_at=due, tz_name="Asia/Kolkata") == \
        due + timedelta(hours=1)
    assert F.nudge_at("their_promise", created_at=fri, due_at=None, tz_name="Asia/Kolkata") == \
        datetime(2026, 9, 22, 10, 0, tzinfo=IST)
    assert F.nudge_at("deadline", created_at=fri, due_at=due, tz_name=None) == \
        due - timedelta(hours=24)
    assert F.nudge_at("deadline", created_at=fri, due_at=None, tz_name=None) is None
    for k in ("risk", "next_step"):
        assert F.nudge_at(k, created_at=fri, due_at=due, tz_name=None) is None
    # the weekend is the SEAT's: Saturday 02:00 IST is still Friday in UTC
    sat = datetime(2026, 9, 19, 2, 0, tzinfo=IST)
    assert F.add_working_days(sat, 1, "Asia/Kolkata") == datetime(2026, 9, 21, 2, 0, tzinfo=IST)


def test_topic_key_dedupes_one_topic_per_day():
    d = date(2026, 9, 14)
    base = dict(seat_id="s1", thread_key="wa:1", app="whatsapp", kind="ask", who="Priya Shah",
                local_date=d)
    k = F.topic_key(**base)
    assert F.topic_key(**{**base, "who": "  priya   SHAH "}) == k
    assert F.topic_key(**{**base, "app": "slack"}) == k              # the thread wins over app
    assert F.topic_key(**{**base, "local_date": d + timedelta(days=1)}) != k
    assert F.topic_key(**{**base, "kind": "my_promise"}) != k
    assert F.topic_key(**{**base, "thread_key": "wa:2"}) != k
    assert F.topic_key(**{**base, "thread_key": None}) != k           # falls back to the app
    assert F.followup_id("o", "s1", k).startswith("fu_")


def test_due_is_read_in_the_seats_zone():
    now = datetime(2026, 9, 14, 6, 0, tzinfo=timezone.utc)
    assert F.parse_due("2026-09-18T17:00", tz_name="Asia/Kolkata", now=now) == \
        datetime(2026, 9, 18, 11, 30, tzinfo=timezone.utc)
    assert F.parse_due("2026-09-18", tz_name="Asia/Kolkata", now=now) == \
        datetime(2026, 9, 18, 18, 0, tzinfo=IST)
    assert F.parse_due("next friday", tz_name="UTC", now=now) is None
    assert F.parse_due("2031-01-01T10:00", tz_name="UTC", now=now) is None     # a misread year
    assert F.parse_due(None, tz_name="UTC", now=now) is None


def test_an_ask_is_answered_only_by_a_you_line_after_it():
    ask = "Priya Shah: Can you send the revised pricing by Friday?"
    q = "send the revised pricing by Friday"
    assert F.answered([ask, "You: sending it in an hour"], q)
    assert not F.answered(["You: hi Priya", ask], q)                  # before the ask
    assert not F.answered([ask, "Priya Shah: thanks"], q)
    assert not F.answered(["You: done", "Ravi: unrelated"], q)        # the ask scrolled away
    assert not F.answered([ask, ask.replace("Friday", "Monday"), "You: ok"], "zz")


def test_the_v2_answer_carries_who_owner_due_and_work():
    screen = "Priya Shah: I will share the signed PO by Thursday\nYou: great"
    res = SI.grounded({"insight": "Priya promised the signed PO by Thursday",
                       "kind": "commitment", "quote": "share the signed PO by Thursday",
                       "work": True, "who": "Priya Shah", "owner": "them",
                       "due": "2026-09-17T18:00"}, screen)
    assert (res["who"], res["owner"], res["due"]) == ("Priya Shah", "them", "2026-09-17T18:00")
    odd = SI.grounded({"insight": "x", "kind": "ask", "quote": "signed PO", "owner": "boss",
                       "who": "null", "due": ""}, screen)
    assert (odd["owner"], odd["who"], odd["due"]) == (None, None, None)
    assert SI.work_of({"work": False}) is False and SI.work_of({"work": "true"}) is True
    assert SI.work_of({"insight": None}) is None and SI.work_of(None) is None


def test_work_false_is_silence_whatever_else_the_model_wrote(monkeypatch):
    screen = "Mom: Did you eat? Call me when you are free beta"
    monkeypatch.setattr(SI, "llm_insight", lambda *a, **kw: {
        "insight": "Call your mother", "kind": "ask", "quote": "Call me when you are free",
        "work": False})
    out = SI._compute(None, org_id="o", email=None, app="whatsapp", participants=[],
                      entities=[], screen=screen, deadline=time.monotonic() + 3)
    assert out["work"] is False and out["insight"] is None and out["memory"] is False


def test_v3_memory_follows_work_and_the_prompt_names_personal_pages():
    assert SI.CAPABILITY_VERSION == "3"
    assert SI.memory_of({"work": True, "memory": True}) is True
    assert SI.memory_of({"work": True, "memory": "false"}) is False
    assert SI.memory_of({"work": False, "memory": True}) is False     # work:false ⇒ memory:false
    assert SI.memory_of({"work": True}) is None and SI.memory_of(None) is None
    flat = " ".join(SI._PROMPT.split())
    assert ("OWN job search, job boards, shopping, banking, personal admin and entertainment "
            "are PERSONAL") in flat
    assert '"memory": true' in SI._PROMPT and '"memory": true or false' in SI._PROMPT
    block = SI.not_useful_block(["Reply to the Naukri alert", "", "b", "c", "d", "e", "f"])
    assert "NOT useful" in block and block.count("\n- ") == 5 and "- f" not in block
    assert SI.not_useful_block([]) == "" and SI.not_useful_block(None) == ""
    prompt = SI._PROMPT.format(app="slack", now_local="Monday", facts="(none)",
                               not_useful=SI.not_useful_block(["Call Ravi about the MSA"]),
                               text="Ravi: hi")
    assert "- Call Ravi about the MSA" in prompt and prompt.index("Call Ravi") < \
        prompt.index("SCREEN TEXT")


def test_popup_actions_teach_and_mute_the_thread():
    res = {"insight": "Priya is waiting on pricing", "kind": "ask", "quote": "revised pricing"}
    m = SI.moment_content(res, digest="d", topic_key="t1", thread_key="wa:1")
    assert m["actions"] == [{"id": "useful", "label": "Useful"},
                            {"id": "not_useful", "label": "Not useful"},
                            {"id": "mute_chat", "label": "Mute chat",
                             "payload": {"thread_key": "wa:1"}}]
    assert m["evidence"][0]["topic_key"] == "t1" and m["capability_version"] == "3"
    assert [a["id"] for a in SI.moment_content(res, digest="d")["actions"]] == \
        ["useful", "not_useful"]                       # nothing to mute without a thread
    label = SI.local_label(datetime(2026, 9, 14, 6, 0, tzinfo=timezone.utc), "Asia/Kolkata")
    assert label.startswith("Monday 2026-09-14 11:30 (Asia/Kolkata)")
    # The next 14 days are listed so the model copies "Friday" instead of counting to it.
    assert "Fri 2026-09-18" in label and "Sun 2026-09-27" in label and label.count(", ") == 13


# ── real Postgres through the routes ──────────────────────────────────────────────────────────
if URL:
    from tests.test_moments_pg import H, _enable_display, _workspace, client  # noqa: F401


def _engine():
    from genios_engine.platform.db import get_engine
    return get_engine(URL)


def _q(sql: str, **params):
    with _engine().connect() as c:
        return c.execute(text(sql), params).fetchall()


def _model(monkeypatch, answer: dict) -> None:
    monkeypatch.setattr(SI, "llm_insight", lambda *a, **kw: dict(answer))


def _look(client, dev, lines, *, thread="wa:chat:priya", app="whatsapp"):
    body = {"moment_request_id": uuid.uuid4().hex, "insight": True,
            "surface": {"app": app, "thread_key": thread}, "visible_messages": lines}
    return client.post("/v1/moments/evaluate", json=body, headers=H(dev["access_token"]))


ASK = "Priya Shah: Can you send the revised pricing by Friday? We need it for the board."
ASK_NOTE = {"insight": "Priya is waiting on revised pricing by Friday", "kind": "ask",
            "quote": "send the revised pricing by Friday", "work": True, "who": "Priya Shah",
            "owner": "me", "due": None}


@pytest.mark.pg
@pytest.mark.skipif(not URL, reason="GENIOS_TEST_DATABASE_URL not set")
def test_ask_popup_repeat_answered_and_the_slice(client, monkeypatch):  # noqa: F811
    ws = _workspace(client)
    _enable_display(client, ws)
    dev, org, seat = ws["member_dev"], ws["org"], ws["member"]["seat_id"]
    v0 = client.get("/v1/seats/me/slice", headers=H(dev["access_token"])).json()["version"]

    _model(monkeypatch, ASK_NOTE)
    r = _look(client, dev, [ASK])
    assert r.status_code == 200, r.text
    m = r.json()
    assert (m["display"], m["reason"]) == (True, None)
    assert [a["id"] for a in m["actions"]] == ["useful", "not_useful", "mute_chat"]
    assert m["actions"][2]["payload"] == {"thread_key": "wa:chat:priya"}
    (fu,) = _q("select * from screen_followups where org_id=:o", o=org)
    assert (fu.kind, fu.who, fu.text, fu.seat_id) == ("ask", "Priya Shah", ASK_NOTE["insight"],
                                                      seat)
    assert fu.nudge_at - fu.created_at == timedelta(hours=3)
    assert _q("select work from screen_thread_verdicts where org_id=:o", o=org)[0].work is True

    # C2: the same topic again (a new screen) → 204, the follow-up refreshed, still one popup
    _model(monkeypatch, {**ASK_NOTE, "insight": "Priya still needs the pricing for her board"})
    again = _look(client, dev, [ASK, "Priya Shah: any update?"])
    assert again.status_code == 204
    rows = _q("select text from screen_followups where org_id=:o", o=org)
    assert [x.text for x in rows] == ["Priya still needs the pricing for her board"]
    assert len(_q("select 1 from moments where org_id=:o and display", o=org)) == 1

    sl = client.get(f"/v1/seats/me/slice?since={v0}", headers=H(dev["access_token"])).json()
    assert sl["schema_version"] == 3 and [f["id"] for f in sl["followups"]] == [fu.id]
    assert set(sl["followups"][0]) == {"id", "kind", "text", "who", "thread_key", "app",
                                       "due_at", "nudge_at", "created_at"}

    # C4 answered: a `You:` line after the ask's line — no model needed to close it
    _model(monkeypatch, {"insight": None, "work": True})
    done = _look(client, dev, [ASK, "Priya Shah: any update?", "You: sending it in 10 minutes"])
    assert done.status_code == 204
    assert _q("select resolution from screen_followups where id=:i", i=fu.id)[0].resolution == \
        "answered"
    sl2 = client.get(f"/v1/seats/me/slice?since={sl['version']}",
                     headers=H(dev["access_token"])).json()
    assert sl2["followups"] == [] and sl2["removed_followups"] == [fu.id]


@pytest.mark.pg
@pytest.mark.skipif(not URL, reason="GENIOS_TEST_DATABASE_URL not set")
def test_budget_promises_personal_resolve_expiry_and_week(client, monkeypatch):  # noqa: F811
    from genios_engine.capture.screen.relevance import ScreenDocRelevance
    from genios_engine.platform.config import get_settings
    ws = _workspace(client)
    _enable_display(client, ws)
    dev, org, seat = ws["member_dev"], ws["org"], ws["member"]["seat_id"]
    with _engine().begin() as c:
        c.execute(text("update orgs set timezone='Asia/Kolkata' where id=:o"), {"o": org})
    monkeypatch.setattr(get_settings(), "screen_insight_max_per_hour", 1)
    now = datetime.now(timezone.utc)
    due_local = (now.astimezone(IST) + timedelta(days=3)).replace(hour=17, minute=0, second=0,
                                                                  microsecond=0)

    # my promise, dated → shown; nudge 60 min before the due (read in the seat's zone)
    _model(monkeypatch, {"insight": "You promised Ravi the deck", "kind": "commitment",
                         "quote": "I'll send the deck", "work": True, "who": "Ravi",
                         "owner": "me", "due": due_local.strftime("%Y-%m-%dT%H:%M")})
    first = _look(client, dev, ["Ravi: can we see the deck?", "You: I'll send the deck by then"],
                  thread="slack:ravi", app="slack").json()
    assert first["display"] is True
    (mine,) = _q("select * from screen_followups where org_id=:o and kind='my_promise'", o=org)
    assert mine.due_at == due_local
    assert mine.nudge_at == mine.due_at - timedelta(minutes=60)

    # C3: over the hourly budget → stored hidden (queued_for_brief); the follow-up still recorded
    _model(monkeypatch, {"insight": "Anita will share the signed PO", "kind": "commitment",
                         "quote": "I will share the signed PO", "work": True, "who": "Anita",
                         "owner": "them", "due": None})
    second = _look(client, dev, ["Anita: I will share the signed PO soon", "You: thanks"],
                   thread="wa:anita").json()
    assert (second["display"], second["reason"]) == (False, "queued_for_brief")
    (theirs,) = _q("select * from screen_followups where org_id=:o and kind='their_promise'",
                   o=org)
    assert theirs.nudge_at == F.add_working_days(theirs.created_at, 2, "Asia/Kolkata")

    # work:false → no popup, no follow-up, the thread's verdict is personal → memory parked
    _model(monkeypatch, {"insight": None, "work": False})
    fam = _look(client, dev, ["Mom: Did you eat? Come home early today beta", "You: yes ma"],
                thread="wa:family")
    assert fam.status_code == 204
    assert len(_q("select 1 from screen_followups where org_id=:o", o=org)) == 2
    lookup = F.verdict_lookup(_engine(), org, seat)
    gate = SimpleNamespace(classify=lambda *a: pytest.fail("the AI gate must not be called"))
    v = ScreenDocRelevance(gate, lookup).classify(SimpleNamespace(
        raw={"app": "whatsapp", "thread_key": "wa:family"},
        event=SimpleNamespace(object_type="chat_thread")), None)
    assert (v.disposition, v.reason) == ("park", "insight_personal")

    # resolve: seat token works, idempotent, another seat's → 404, only done / dismissed
    seat_h = H(ws["member"]["token"])
    ok = client.post(f"/v1/followups/{mine.id}/resolve", json={"resolution": "done"},
                     headers=seat_h)
    assert ok.status_code == 200 and ok.json()["resolution"] == "done"
    assert client.post(f"/v1/followups/{mine.id}/resolve", json={"resolution": "dismissed"},
                       headers=seat_h).json()["resolution"] == "done"
    assert client.post(f"/v1/followups/{mine.id}/resolve", json={"resolution": "done"},
                       headers=H(ws["owner_dev"]["access_token"])).status_code == 404
    assert client.post(f"/v1/followups/{mine.id}/resolve", json={"resolution": "answered"},
                       headers=seat_h).status_code == 422

    # expiry on read: a promise 3 days past due
    with _engine().begin() as c:
        c.execute(text(
            "insert into screen_followups (id, org_id, seat_id, kind, text, due_at, topic_key) "
            "values ('fu_old', :o, :s, 'their_promise', 'old promise', :due, 'topic_old')"),
            {"o": org, "s": seat, "due": now - timedelta(days=3)})
    dev_h = H(dev["access_token"])
    open_ids = [f["id"] for f in client.get("/v1/followups", headers=dev_h).json()["followups"]]
    assert open_ids == [theirs.id]
    every = client.get("/v1/followups?status=all&limit=10", headers=dev_h).json()["followups"]
    assert {f["id"]: f["resolution"] for f in every} == {
        theirs.id: None, mine.id: "done", "fu_old": "expired"}
    assert client.get("/v1/followups?status=bogus", headers=dev_h).status_code == 422

    # C8: the week in counts (+ teach feedback on the two insight moments)
    for mid, action in ((first["moment_id"], "useful"), (second["moment_id"], "wrong")):
        assert client.post(f"/v1/moments/{mid}/feedback", json={"action": action},
                           headers=dev_h).status_code == 200
    rep = client.get("/v1/seats/me/weekly-report", headers=seat_h).json()
    monday = now.astimezone(IST).date() - timedelta(days=now.astimezone(IST).weekday())
    assert rep == {"week_start": monday.isoformat(),
                   "week_end": (monday + timedelta(days=6)).isoformat(),
                   "promises_caught": 3, "promises_kept": 1, "asks_flagged": 0,
                   "asks_answered": 0, "deadlines_flagged": 0, "risks_flagged": 0,
                   "popups_shown": 1, "useful": 1, "not_useful": 1}
    last = client.get(f"/v1/seats/me/weekly-report?week_start={monday - timedelta(days=7)}",
                      headers=dev_h).json()
    assert last["promises_caught"] == 0 and last["popups_shown"] == 0


# ── P9 K4 · not useful mutes the thread; the notes teach the prompt ───────────────────────────
@pytest.mark.pg
@pytest.mark.skipif(not URL, reason="GENIOS_TEST_DATABASE_URL not set")
def test_not_useful_mutes_the_thread_and_teaches_the_prompt(client, monkeypatch):  # noqa: F811
    ws = _workspace(client)
    _enable_display(client, ws)
    dev, org, seat = ws["member_dev"], ws["org"], ws["member"]["seat_id"]
    dev_h = H(dev["access_token"])
    calls: list = []

    def model(answer):
        def fake(*a, **kw):
            calls.append(kw.get("not_useful"))
            return dict(answer)
        monkeypatch.setattr(SI, "llm_insight", fake)

    model({**ASK_NOTE, "memory": True})
    m = _look(client, dev, [ASK]).json()
    assert calls == [[]]                                 # nothing marked not useful yet
    (v,) = _q("select work, memory, muted_until from screen_thread_verdicts where org_id=:o",
              o=org)
    assert (v.work, v.memory, v.muted_until) == (True, True, None)       # K2

    before = datetime.now(timezone.utc)
    assert client.post(f"/v1/moments/{m['moment_id']}/feedback", json={"action": "wrong"},
                       headers=dev_h).status_code == 200
    (v,) = _q("select muted_until from screen_thread_verdicts where org_id=:o", o=org)
    assert timedelta(days=6, hours=23) < v.muted_until - before <= timedelta(days=7, minutes=1)

    # the muted thread: a new screen → 204 and NO model call
    assert _look(client, dev, [ASK, "Priya Shah: hello?"]).status_code == 204
    assert len(calls) == 1

    # another thread: the model is told what the manager found not useful
    model({"insight": "Ravi wants the MSA today", "kind": "ask", "quote": "send the MSA today",
           "work": True, "memory": True, "who": "Ravi", "owner": "me", "due": None})
    r = _look(client, dev, ["Ravi: please send the MSA today"], thread="slack:ravi", app="slack")
    assert r.status_code == 200 and calls[-1] == [ASK_NOTE["insight"]]

    # "Mute chat" (device) → recorded server-side, for good; a later "not useful" never shortens it
    mid = r.json()["moment_id"]
    assert client.post(f"/v1/moments/{mid}/feedback",
                       json={"action": "dismissed", "reason": "mute_chat"},
                       headers=dev_h).status_code == 200
    assert client.post(f"/v1/moments/{mid}/feedback", json={"action": "wrong"},
                       headers=dev_h).status_code == 200
    (ravi,) = _q("select muted_until from screen_thread_verdicts where org_id=:o "
                 "and thread_key='slack:ravi'", o=org)
    assert ravi.muted_until == F.MUTE_FOREVER
    assert _look(client, dev, ["Ravi: and the NDA too"], thread="slack:ravi",
                 app="slack").status_code == 204
    with _engine().connect() as c:
        assert F.not_useful_notes(c, org_id=org, seat_id=seat,
                                  capability_id=SI.CAPABILITY_ID) == [
            "Ravi wants the MSA today", ASK_NOTE["insight"]]

    # a mute on a thread with no verdict yet is NOT a memory verdict
    now = datetime.now(timezone.utc)
    F.mute(_engine(), org_id=org, seat_id=seat, thread_key="wa:new", until=now + timedelta(days=7),
           now=now)
    with _engine().connect() as c:
        assert F.is_muted(c, org_id=org, seat_id=seat, thread_key="wa:new", now=now)
        assert F.thread_verdict(c, org_id=org, seat_id=seat, thread_key="wa:new", now=now) is None

    # retention: a running mute outlives the verdict's week; an ended one does not
    with _engine().begin() as c:
        F.purge(c, now=now + timedelta(days=8))
    left = {r.thread_key for r in _q("select thread_key from screen_thread_verdicts "
                                     "where org_id=:o", o=org)}
    assert left == {"slack:ravi"}


# ── P9 K5 · follow-ups expire by kind ─────────────────────────────────────────────────────────
@pytest.mark.pg
@pytest.mark.skipif(not URL, reason="GENIOS_TEST_DATABASE_URL not set")
def test_followups_expire_by_kind(client):  # noqa: F811
    ws = _workspace(client)
    org, seat = ws["org"], ws["member"]["seat_id"]
    now = datetime.now(timezone.utc)
    d = timedelta(days=1)
    rows = {  # id: (kind, created_at, due_at, expired?)
        "fu_ask_8d": ("ask", now - 8 * d, None, True),
        "fu_ask_6d": ("ask", now - 6 * d, now - 5 * d, False),
        "fu_dl_due_2d": ("deadline", now - 3 * d, now - 2 * d, True),
        "fu_dl_due_12h": ("deadline", now - 3 * d, now - d / 2, False),
        "fu_dl_undated_8d": ("deadline", now - 8 * d, None, True),
        "fu_dl_undated_6d": ("deadline", now - 6 * d, None, False),
        "fu_risk_4d": ("risk", now - 4 * d, None, True),
        "fu_step_2d": ("next_step", now - 2 * d, None, False),
        "fu_mine_undated_30d": ("my_promise", now - 30 * d, None, False),   # promises unchanged
        "fu_theirs_due_3d": ("their_promise", now - 5 * d, now - 3 * d, True),
    }
    with _engine().begin() as c:
        for fid, (kind, created, due, _) in rows.items():
            c.execute(text(
                "insert into screen_followups (id, org_id, seat_id, kind, text, due_at, "
                "topic_key, created_at) values (:i, :o, :s, :k, 'note', :due, :t, :cr)"),
                {"i": fid + org[-6:], "o": org, "s": seat, "k": kind, "due": due,
                 "t": fid, "cr": created})
        assert F.expire(c, org_id=org, seat_id=seat, now=now) == 5
    got = {r.topic_key: r.resolution for r in _q(
        "select topic_key, resolution from screen_followups where org_id=:o", o=org)}
    assert got == {fid: ("expired" if exp else None) for fid, (*_, exp) in rows.items()}
