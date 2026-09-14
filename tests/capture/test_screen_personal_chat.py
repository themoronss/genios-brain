"""P8 C9 · a screen thread's memory is routed by the screen-insight model's verdict, not a rule.

The P3 rule "WhatsApp + nobody known → park" is gone: whether a chat is work is MEANING, so the
model judges it (screen_thread_verdicts, 24 h). A verdict routes with no AI gate call — work
keeps, personal PARKS (store-don't-delete: never dropped). No verdict → the ordinary gate.
"""

from __future__ import annotations

from types import SimpleNamespace

from genios_engine.capture.gate.relevance import RelevanceVerdict
from genios_engine.capture.screen.relevance import ScreenDocRelevance


class _Gate:
    def __init__(self) -> None:
        self.calls = 0

    def classify(self, ctx, prepared):
        self.calls += 1
        return RelevanceVerdict(True, 0.8, disposition="keep", reason="gate")


def _ctx(app: str, alias_hits: int, object_type: str = "chat_thread", thread: str = "wa:1"):
    return SimpleNamespace(raw={"app": app, "alias_hits": alias_hits, "thread_key": thread},
                           event=SimpleNamespace(object_type=object_type))


def _verdicts(table: dict):
    return lambda thread_key: table.get(thread_key)


def test_a_whatsapp_chat_with_nobody_known_now_goes_to_the_gate():
    gate = _Gate()
    v = ScreenDocRelevance(gate).classify(_ctx("whatsapp", 0), None)
    assert v.reason == "gate" and gate.calls == 1


def test_a_personal_verdict_parks_without_a_gate_call():
    gate = _Gate()
    v = ScreenDocRelevance(gate, _verdicts({"wa:1": False})).classify(_ctx("whatsapp", 3), None)
    assert (v.relevant, v.disposition, v.reason) == (False, "park", "insight_personal")
    assert gate.calls == 0


def test_a_work_verdict_keeps_without_a_gate_call():
    gate = _Gate()
    v = ScreenDocRelevance(gate, _verdicts({"wa:1": True})).classify(_ctx("whatsapp", 0), None)
    assert (v.relevant, v.disposition, v.reason) == (True, "keep", "insight_work")
    assert gate.calls == 0


def test_no_verdict_for_this_thread_is_the_ordinary_path():
    gate = _Gate()
    lookup = _verdicts({"other": False})
    assert ScreenDocRelevance(gate, lookup).classify(_ctx("whatsapp", 0), None).reason == "gate"
    assert ScreenDocRelevance(None, lookup).classify(_ctx("whatsapp", 0), None).reason == \
        "screen_thread"


def test_work_chat_apps_are_unaffected():
    for app in ("linkedin", "slack", "gmail", "outlook"):
        gate = _Gate()
        assert ScreenDocRelevance(gate).classify(_ctx(app, 0), None).reason == "gate"


def test_a_personal_verdict_parks_even_with_no_gate_configured():
    v = ScreenDocRelevance(None, _verdicts({"wa:1": False})).classify(_ctx("whatsapp", 0), None)
    assert v.disposition == "park"
