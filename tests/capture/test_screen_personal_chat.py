"""P3 leftover · personal WhatsApp chats are parked before any model call.

A WhatsApp chat with nobody the org knows is most likely family or friends. It must never reach
the AI gate (cost + privacy), and it must be PARKED, not dropped (store-don't-delete). A chat
with a known contact still goes to the ordinary gate.
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


def _ctx(app: str, alias_hits: int, object_type: str = "chat_thread"):
    return SimpleNamespace(raw={"app": app, "alias_hits": alias_hits},
                           event=SimpleNamespace(object_type=object_type))


def test_a_whatsapp_chat_with_nobody_known_is_parked_without_a_model_call():
    gate = _Gate()
    v = ScreenDocRelevance(gate).classify(_ctx("whatsapp", 0), None)
    assert (v.relevant, v.disposition, v.reason) == (False, "park", "personal_chat")
    assert gate.calls == 0


def test_a_whatsapp_chat_with_a_known_contact_goes_to_the_gate():
    gate = _Gate()
    v = ScreenDocRelevance(gate).classify(_ctx("WhatsApp", 2), None)
    assert v.reason == "gate" and gate.calls == 1


def test_work_chat_apps_are_unaffected():
    for app in ("linkedin", "slack", "gmail", "outlook"):
        gate = _Gate()
        assert ScreenDocRelevance(gate).classify(_ctx(app, 0), None).reason == "gate"


def test_parked_even_when_no_gate_is_configured():
    v = ScreenDocRelevance(None).classify(_ctx("whatsapp", 0), None)
    assert v.disposition == "park"
