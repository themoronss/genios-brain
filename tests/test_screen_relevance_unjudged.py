"""Instant screen memory: a page no model judged is kept for the hourly batch update (S4) when it
holds real text, and stays parked (stored, recoverable) when it was only flicked past."""
from __future__ import annotations

from types import SimpleNamespace

from genios_engine.capture.screen.relevance import (DOC_OBJECT_TYPE, UNJUDGED_KEEP_MIN_CHARS,
                                                    ScreenDocRelevance)


def _doc(body: str, thread: str = "doc:com.google.Chrome:shop.example.com/cart"):
    return SimpleNamespace(raw={"thread_key": thread, "host": "shop.example.com", "body": body},
                           event=SimpleNamespace(object_type=DOC_OBJECT_TYPE,
                                                 source_object_id="o1"))


def test_an_unjudged_page_with_real_text_waits_for_the_memory_update():
    long, short = "x" * UNJUDGED_KEEP_MIN_CHARS, "x" * (UNJUDGED_KEEP_MIN_CHARS - 1)
    gate = ScreenDocRelevance(None, lambda _t: None, keep_unjudged=True)
    v = gate.classify(_doc(long), None)
    assert (v.disposition, v.reason) == ("keep", "await_memory_update")
    assert gate.classify(_doc(short), None).disposition == "park"          # flicked past
    # off (the default, and "full" mode): parked exactly as before
    assert ScreenDocRelevance(None, lambda _t: None).classify(_doc(long), None).reason == \
        "no_work_signal"
    # a verdict still decides first: personal stays parked, whatever the length
    personal = ScreenDocRelevance(None, lambda _t: {"work": False, "memory": False},
                                  keep_unjudged=True)
    assert personal.classify(_doc(long), None).reason == "insight_personal"
