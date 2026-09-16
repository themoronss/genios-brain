"""P-20 screen insight — the ONE judge of screen text (SCREEN_INTEL_SYSTEM_DESIGN.html phase 1).

Items survive only when their quote is really on screen (no invented facts); the manager is never
"who"; a note survives only when it ADDS something the screen does not show; the same screen is
judged once, each seat has a daily cap, and a slow or missing model is silence, never an error.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone

import pytest

from genios_engine.reason.moments import screen_insight as SI

SCREEN = ("Priya Shah: Can you send the revised pricing by Friday?\n"
          "You: Sure, let me check with the team\n"
          "Priya Shah: We need it before our board meeting on 25 Sep")
ASK = {"kind": "ask", "text": "Priya wants the revised pricing by Friday", "who": "Priya Shah",
       "due": "2026-09-18T18:00", "quote": "send the revised pricing by Friday"}


def test_visible_text_formats_senders_and_keeps_the_newest_part():
    out = SI.visible_text([{"sender": "Priya", "text": "hi  there"}, "plain line", {"text": ""}])
    assert out == "Priya: hi there\nplain line"
    long = SI.visible_text(["x" * 3000, "y" * 3000])
    assert len(long) == SI.MAX_TEXT_CHARS and long.endswith("y" * 10)


def test_items_survive_only_with_a_quote_on_screen_and_a_known_kind():
    j = SI.judge({"work": True, "remember": True, "items": [
        ASK,
        {**ASK, "quote": "a discount of 20%"},              # not on screen → dropped
        {**ASK, "kind": "gossip"},                           # unknown kind → dropped
        {**ASK, "text": None},                               # no text → dropped
        "junk"], "adds": "none", "note": None}, SCREEN)
    assert [i["quote"] for i in j["items"]] == [ASK["quote"]]
    assert (j["work"], j["remember"], j["adds_candidate"], j["note_candidate"]) == (True, True, "none", None)
    assert SI.judge(None, SCREEN)["items"] == [] and SI.judge({"items": "x"}, SCREEN)["items"] == []
    # at most three items are read
    many = SI.judge({"work": True, "items": [ASK] * 5}, SCREEN)
    assert len(many["items"]) == SI.MAX_ITEMS


def test_a_note_only_when_it_adds_and_is_about_a_grounded_item():
    base = {"work": True, "remember": True, "items": [ASK]}
    ok = SI.judge({**base, "adds": "repeat_ask", "note": "Priya asked for this on Monday too"},
                  SCREEN)
    assert (ok["adds_candidate"], ok["note_candidate"]) == ("repeat_ask", "Priya asked for this on Monday too")
    # "none", an unknown reason, or no grounded item → no note, the items are still kept
    for raw in ({**base, "adds": "none", "note": "Priya is waiting on pricing"},
                {**base, "adds": "just_because", "note": "x"},
                {**base, "items": [{**ASK, "quote": "not there"}], "adds": "repeat_ask",
                 "note": "x"}):
        j = SI.judge(raw, SCREEN)
        assert (j["adds_candidate"], j["note_candidate"]) == ("none", None)
    assert len(SI.judge({**base, "adds": "none", "note": "x"}, SCREEN)["items"]) == 1


def test_personal_is_empty_whatever_else_the_model_wrote():
    j = SI.judge({"work": False, "remember": True, "items": [ASK], "adds": "urgent_risk",
                  "note": "Call your mother"}, SCREEN)
    assert j == {"work": False, "remember": False, "items": [], "adds_candidate": "none",
                 "note_candidate": None}



def test_only_what_a_person_actually_said_becomes_an_item():
    # Structural, not a word list: on a chat screen every real line carries a sender, so a quote
    # taken from a button or a status bar is not in `said` and cannot become an item.
    said = SI.said_lines([{"sender": "Priya", "text": "send the revised quote by Friday"},
                          {"sender": "You", "text": "sure, tomorrow 5 pm"},
                          "Join meeting", "Ln 1, Col 1  100%  UTF-8"])
    assert len(said) == 2, "only the two real messages"
    assert SI.reject({"kind": "ask", "who": "Priya", "text": "Priya needs the revised quote",
                      "quote": "send the revised quote by Friday"}, said=said) is None
    assert SI.reject({"kind": "next_step", "text": "Join the Zoom meeting",
                      "quote": "Join meeting now"}, said=said) == "not_said"
    assert SI.reject({"kind": "ask", "who": "Priya", "text": "x", "quote": "PO"}, said=said) == "no_quote"
    # A page has no senders, so the "was it said" rule cannot apply there and a real item stands.
    assert SI.reject({"kind": "risk", "text": "Database full, writes blocked",
                      "quote": "database at 1044 MB, writes blocked"}) is None


def test_the_calendar_owns_meetings():
    # "Join the 4 pm review" is not an item when the calendar already holds that meeting.
    meetings = [{"start_at": "2026-09-17T10:30:00Z", "title": "Acme review"}]   # 4 PM IST
    item = {"kind": "next_step", "text": "Attend the Acme review", "due": "2026-09-17T16:00",
            "quote": "review at 4 pm today"}
    assert SI.is_a_known_meeting(item, meetings, "Asia/Kolkata") is True
    assert SI.is_a_known_meeting(item, [], "Asia/Kolkata") is False
    raw = {"work": True, "remember": True, "adds": "none", "note": None, "items": [item]}
    out = SI.judge(raw, "review at 4 pm today", meetings=meetings, tz_name="Asia/Kolkata")
    assert out["items"] == [], "the calendar already reminds them"


def test_one_event_becomes_one_item():
    # The 11 Sep build failure became two items on 16 Sep: the risk and the next step.
    screen = ("Your build job failed because it returned a non-zero exit code. "
              "See the build logs for commit e18bf68 for details and fix the failure cause.")
    raw = {"work": True, "remember": True, "adds": "none", "note": None, "items": [
        {"kind": "risk", "text": "Build failed on Sep 11 for commit e18bf68", "who": None, "due": None,
         "quote": "Your build job failed because it returned"},
        {"kind": "next_step", "text": "Review build logs for commit e18bf68 to fix the failure", "who": None,
         "due": None, "quote": "See the build logs for commit e18bf68"},
    ]}
    out = SI.judge(raw, screen)
    assert len(out["items"]) == 1
    assert out["items"][0]["kind"] == "next_step", "the one you can act on survives"


def test_the_prompt_calls_salary_and_referrals_personal_and_shows_kept_notes():
    p = SI.build_prompt(app="whatsapp", screen="x", facts=[])
    assert "salary, pay, reimbursement or rent" in p and "job referral" in p
    assert "never an item" in p and "One real thing = one item" in p
    assert "kept these earlier notes as USEFUL" not in p, "nothing kept yet → no block"
    kept = SI.build_prompt(app="whatsapp", screen="x", facts=[],
                           useful=["Priya asked for this quote on 11 Sep too"])
    assert "kept these earlier notes as USEFUL" in kept and "11 Sep too" in kept

def test_the_manager_is_never_who():
    me = ["mrrohitswerashi@gmail.com", "Rohit Swerashi"]
    for who in ("Rohit Swerashi", "rohit swerashi", "mrrohitswerashi@gmail.com", "RohitSwerashi"):
        assert SI.is_me(who, me), who
    for who in ("Priya Shah", "Rohit", None, ""):
        assert not SI.is_me(who, me), who
    screen = "Harsh Tripathi's application requires your action. Your application is required"
    j = SI.judge({"work": True, "items": [{"kind": "ask", "text": "Application needs action",
                                           "who": "Harsh Tripathi",
                                           "quote": "Your application is required"}]},
                 screen, me=["tripathihk2014@gmail.com", "Harsh Tripathi"])
    assert j["items"][0]["who"] is None


def test_a_named_weekday_wins_over_a_wrongly_copied_date():
    from datetime import date
    today = date(2026, 9, 14)                                     # a Monday
    # measured: Haiku copied "Thursday 5 pm" as Friday the 18th
    assert SI.fix_weekday("2026-09-18T17:00", "send the signed MSA by Thursday 5 pm",
                          today) == "2026-09-17T17:00"
    assert SI.fix_weekday("2026-09-17T17:00", "by Thursday 5 pm", today) == "2026-09-17T17:00"
    assert SI.fix_weekday("2026-09-14T18:00", "by Monday EOD", today) == "2026-09-14T18:00"
    assert SI.fix_weekday("2026-09-18T18:00", "Friday or Monday works", today) == \
        "2026-09-18T18:00"                                        # two weekdays: left alone
    assert SI.fix_weekday("2026-09-18T18:00", "by the 18th", today) == "2026-09-18T18:00"
    assert SI.fix_weekday("2026-09-18", "by Thursday", today) == "2026-09-17"
    assert SI.fix_weekday(None, "Thursday", today) is None
    assert SI.fix_weekday("soon", "Thursday", today) == "soon"
    assert SI.fix_weekday("2026-09-18T17:00", "Thursday", None) == "2026-09-18T17:00"
    # only a date ONE day off is a copying slip; anything else is the model's reading
    assert SI.fix_weekday("2026-09-21T18:00", "by Monday", today) == "2026-09-21T18:00"   # next Monday
    assert SI.fix_weekday("2026-09-18T18:00", "after Monday's call, send it by 18 Sep",
                          today) == "2026-09-18T18:00"
    screen = "Ravi: can you share it?\nYou: I'll send the signed MSA by Thursday 5 pm"
    j = SI.judge({"work": True, "items": [{"kind": "my_promise", "text": "Send Ravi the MSA",
                                           "who": "Ravi", "due": "2026-09-18T17:00",
                                           "quote": "send the signed MSA by Thursday 5 pm"}]},
                 screen, today=today)
    assert j["items"][0]["due"] == "2026-09-17T17:00"


def test_the_moment_carries_the_note_the_quote_and_a_hash_never_the_screen():
    j = SI.judge({"work": True, "items": [ASK], "adds": "conflict",
                  "note": "Friday clashes with your Voltex review"}, SCREEN)
    m = SI.moment_content(j, digest=SI.text_digest(SCREEN), adds="conflict",
                          note=j["note_candidate"], topic_key="t1", thread_key="wa:1")
    assert m["capability_id"] == SI.CAPABILITY_ID and m["capability_version"] == "4"
    assert (m["headline"], m["body"]) == (j["note_candidate"], f"“{ASK['quote']}”")
    # `verified` is on the evidence because the popup exists only when code could check it.
    assert m["evidence"] == [{"kind": "screen", "sha256": SI.text_digest(SCREEN),
                              "insight_kind": "ask", "adds": "conflict", "verified": True,
                              "topic_key": "t1"}]
    assert "board meeting" not in str(m), "screen text beyond the quote must not travel"


def test_the_prompt_carries_who_the_manager_is_open_items_and_meetings():
    items = [{"kind": "ask", "who": "Priya Shah", "text": "Pricing for the board",
              "due_at": "2026-09-18T12:30:00+00:00", "thread_key": "mail:1", "app": "gmail",
              "created_at": "2026-09-10T09:00:00+00:00"},
             {"kind": "my_promise", "who": "Priya Shah", "text": "Send the deck",
              "due_at": None, "thread_key": "wa:1", "app": "whatsapp",
              "created_at": "2026-09-12T09:00:00+00:00"}]
    meetings = [{"title": "Voltex review", "start_at": "2026-09-18T10:30:00+00:00",
                 "end_at": "2026-09-18T11:30:00+00:00"}]
    p = SI.build_prompt(app="whatsapp", screen=SCREEN, facts=[], now_local="Monday",
                        me=["rohit@x.com", "Rohit"], open_items=items, meetings=meetings,
                        thread_key="wa:1", tz_name="Asia/Kolkata")
    assert "The manager whose screen this is: rohit@x.com, Rohit." in p
    assert "another chat (gmail)" in p and "this chat" in p and "since 2026-09-10" in p
    assert "- Fri 2026-09-18 16:00–17:00 Voltex review" in p           # in the seat's zone
    assert "has ALREADY READ this screen" in " ".join(p.split())
    assert p.index("Voltex review") < p.index("SCREEN TEXT")
    empty = SI.build_prompt(app=None, screen="x", facts=[])
    assert empty.count("(none)") == 5 and "(unknown)" in empty
    # the weekly profile (S8) and the chat's batch summary (S4) travel as context
    ctx = SI.build_prompt(app="whatsapp", screen="x", facts=[], profile="Founder of Acme; key: Priya (client)",
                          summary="Priya is negotiating the Q3 renewal")
    assert "About the manager (GeniOS's weekly notes; may be empty): Founder of Acme" in ctx
    assert "Priya is negotiating the Q3 renewal" in ctx and ctx.index("Q3 renewal") < ctx.index("SCREEN TEXT")


def test_a_new_person_still_gets_items(monkeypatch):
    monkeypatch.setattr(SI, "llm_insight", lambda *a, **kw: {
        "work": True, "remember": True, "items": [ASK], "adds": "none", "note": None})
    out = SI._compute(None, org_id="o", email=None, app="whatsapp", participants=[],
                      entities=[], screen=SCREEN, deadline=time.monotonic() + 3)
    assert out and out["subject_ids"] == [] and out["memory"] is True
    assert [i["kind"] for i in out["judged"]["items"]] == ["ask"]


def test_no_model_configured_is_silence():
    assert SI.llm_insight(None, org_id="o", app="x", screen=SCREEN, facts=[],
                          deadline=time.monotonic() + 3) is None


def test_a_slow_insight_times_out_to_silence(monkeypatch):
    monkeypatch.setattr(SI, "_compute", lambda *a, **kw: time.sleep(1) or {"x": 1})
    assert SI.insight(None, org_id="o", email=None, app="x", participants=[], entities=[],
                      screen=SCREEN, timeout_s=0.2) is None


@pytest.mark.pg
def test_the_daily_cap_is_enforced_per_seat(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — real-Postgres cap test skipped")
    from sqlalchemy import text

    from genios_engine.platform.db import get_engine

    engine = get_engine(live_db_url)
    org, seat = "org_cap_" + uuid.uuid4().hex[:6], "seat_cap"
    now = datetime.now(timezone.utc)
    try:
        got = [SI.reserve(engine, org_id=org, seat_id=seat, cap=2, now=now) for _ in range(3)]
        assert got == [True, True, False]
        assert SI.reserve(engine, org_id=org, seat_id="other_seat", cap=2, now=now) is True
    finally:
        with engine.begin() as c:
            c.execute(text("delete from rate_counters where scope_key like :k"),
                      {"k": f"{org}:%"})


# ── the interrupt is code's, not the model's (SCREEN_COST_LATENCY_FIX.md §2.4) ────────────────
NOW = datetime(2026, 9, 17, 10, 0, tzinfo=timezone.utc)
PRIYA_ASK = [{"kind": "ask", "text": "Priya needs pricing", "who": "Priya Shah",
              "due": None, "quote": "revised pricing"}]


def verify(candidate, **kw):
    base = {"items": PRIYA_ASK, "open_items": [], "meetings": [], "thread_key": "wa:1",
            "tz_name": "Asia/Kolkata", "now": NOW}
    return SI.verify_adds(candidate, **{**base, **kw})


def test_a_repeat_the_books_do_not_show_is_not_a_repeat():
    assert verify("repeat_ask") is None, "no prior ask on file ⇒ the model is guessing"
    prior = [{"kind": "ask", "who": "Priya Shah", "thread_key": "wa:1"}]
    assert verify("repeat_ask", open_items=prior) == "repeat_ask"
    # a prior ask from someone else is not this person asking again
    assert verify("repeat_ask", open_items=[{"kind": "ask", "who": "Rahul"}]) is None


def test_a_promise_owed_must_be_the_manager_s_own_and_to_this_person():
    assert verify("promise_to_them",
                  open_items=[{"kind": "their_promise", "who": "Priya Shah"}]) is None
    assert verify("promise_to_them",
                  open_items=[{"kind": "my_promise", "who": "Priya Shah"}]) == "promise_to_them"


def test_the_same_ask_elsewhere_has_to_be_elsewhere():
    same = [{"kind": "ask", "who": "Priya Shah", "thread_key": "wa:1"}]
    other = [{"kind": "ask", "who": "Priya Shah", "thread_key": "mail:9"}]
    assert verify("same_ask_elsewhere", open_items=same) is None
    assert verify("same_ask_elsewhere", open_items=other) == "same_ask_elsewhere"


def test_a_clash_is_calendar_arithmetic_not_an_opinion():
    meetings = [{"title": "Voltex review", "start_at": "2026-09-18T10:30:00+00:00",
                 "end_at": "2026-09-18T11:30:00+00:00"}]
    inside = [{**PRIYA_ASK[0], "due": "2026-09-18T16:30"}]      # 11:00 UTC — inside the meeting
    outside = [{**PRIYA_ASK[0], "due": "2026-09-18T20:00"}]
    assert verify("conflict", items=inside, meetings=meetings) == "conflict"
    assert verify("conflict", items=outside, meetings=meetings) is None
    assert verify("conflict", items=inside, meetings=[]) is None


def test_urgency_needs_a_clock_not_a_tone():
    assert verify("urgent_risk") is None, "cancellation language alone is not enough"
    soon = [{**PRIYA_ASK[0], "due": "2026-09-17T20:00"}]        # 14:30 UTC, same day
    assert verify("urgent_risk", items=soon) == "urgent_risk"
    assert verify("urgent_risk", open_items=[{"due_at": "2026-09-17T18:00:00+00:00"}]) == "urgent_risk"


def test_nothing_the_gate_does_not_know_can_reach_the_screen():
    assert verify("just_because", open_items=[{"kind": "ask", "who": "Priya Shah"}]) is None
    assert verify("none") is None
    assert verify("repeat_ask", items=[]) is None
    # an item whose "who" was stripped (it named the manager) cannot be matched to anyone
    anon = [{**PRIYA_ASK[0], "who": None}]
    assert verify("repeat_ask", items=anon,
                  open_items=[{"kind": "ask", "who": "Priya Shah"}]) is None


def test_confidence_is_recorded_and_never_invented():
    assert SI.confidence_of(0.91) == 0.91 and SI.confidence_of("0.5") == 0.5
    assert SI.confidence_of(85) == 0.85, "a model that answered in percent"
    assert SI.confidence_of(None) is None and SI.confidence_of("high") is None
    assert SI.confidence_of(-1) is None and SI.confidence_of(1000) is None
    j = SI.judge({"work": True, "items": [{**ASK, "confidence": 0.77}]}, SCREEN)
    assert j["items"][0]["confidence"] == 0.77
    assert SI.judge({"work": True, "items": [ASK]}, SCREEN)["items"][0]["confidence"] is None
