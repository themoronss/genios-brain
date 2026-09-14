"""P-20 screen insight: one short, grounded note about whatever is on screen.

A note survives only when its quote is really on screen (no invented facts), the same screen is
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


def test_visible_text_formats_senders_and_keeps_the_newest_part():
    out = SI.visible_text([{"sender": "Priya", "text": "hi  there"}, "plain line", {"text": ""}])
    assert out == "Priya: hi there\nplain line"
    long = SI.visible_text(["x" * 3000, "y" * 3000])
    assert len(long) == SI.MAX_TEXT_CHARS and long.endswith("y" * 10)


def test_a_note_survives_only_with_a_quote_that_is_on_screen():
    ok = SI.grounded({"insight": "Priya wants pricing by Friday — not sent yet", "kind": "ask",
                      "quote": "send the revised pricing by Friday"}, SCREEN)
    assert ok and ok["kind"] == "ask"
    assert SI.grounded({"insight": "x", "kind": "ask", "quote": "a discount of 20%"}, SCREEN) is None
    assert SI.grounded({"insight": "x", "kind": "gossip", "quote": "pricing"}, SCREEN) is None
    assert SI.grounded({"insight": None}, SCREEN) is None
    assert SI.grounded(None, SCREEN) is None


def test_the_moment_carries_the_note_and_a_hash_never_the_screen():
    res = {"insight": "Priya needs pricing before 25 Sep", "kind": "deadline",
           "quote": "before our board meeting on 25 Sep"}
    m = SI.moment_content(res, digest=SI.text_digest(SCREEN))
    assert m["capability_id"] == SI.CAPABILITY_ID and m["headline"] == res["insight"]
    assert m["evidence"] == [{"kind": "screen", "sha256": SI.text_digest(SCREEN),
                              "insight_kind": "deadline"}]
    assert "Can you send" not in str(m), "screen text beyond the quote must not travel"


def test_a_new_person_still_gets_an_insight(monkeypatch):
    monkeypatch.setattr(SI, "llm_insight", lambda *a, **kw: {
        "insight": "Priya wants pricing by Friday — not sent yet", "kind": "ask",
        "quote": "revised pricing by Friday"})
    out = SI._compute(None, org_id="o", email=None, app="whatsapp", participants=[],
                      entities=[], screen=SCREEN, deadline=time.monotonic() + 3)
    assert out and out["subject_ids"] == [] and out["insight"]["kind"] == "ask"


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
