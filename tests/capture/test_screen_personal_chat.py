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


# ── P9 K3 · the memory verdict, and ONE AI call per screen object ────────────────────────────
def test_memory_verdicts_route_without_a_gate_call():
    gate = _Gate()
    rel = ScreenDocRelevance(gate, _verdicts({
        "wa:1": {"work": True, "memory": False}, "wa:2": {"work": True, "memory": True},
        "wa:3": {"work": False, "memory": True}, "wa:4": {"work": True, "memory": None}}))
    got = {t: rel.classify(_ctx("whatsapp", 0, thread=t), None) for t in
           ("wa:1", "wa:2", "wa:3", "wa:4")}
    assert {t: (v.disposition, v.reason) for t, v in got.items()} == {
        "wa:1": ("park", "insight_no_memory"), "wa:2": ("keep", "insight_memory"),
        "wa:3": ("park", "insight_personal"), "wa:4": ("keep", "insight_work")}
    assert gate.calls == 0


class _Inner:
    """S4's real page stand-in: counts what reaches it."""

    stats = "inner-stats"

    def __init__(self) -> None:
        self.decides = 0
        self.primes = 0

    def prime(self, candidates, **kw):
        self.primes += 1

    def decide(self, candidate):
        self.decides += 1
        return "inner"


class _GateLLM:
    model = "stub"

    def __init__(self) -> None:
        self.calls = 0

    def call(self, prompt, max_tokens=None):
        self.calls += 1
        return SimpleNamespace(ok=True, model="stub", parsed={
            "disposition": "keep", "relevance": 0.8, "reason": "a person asking"})


def _obj(oid: str, *, thread: str, object_type: str = "screen_chat_thread", alias_hits: int = 0):
    return SimpleNamespace(
        raw={"app": "whatsapp", "thread_key": thread, "alias_hits": alias_hits,
             "subject": "Priya Shah", "body": "Can you send the deck?"},
        sender_known=False,
        event=SimpleNamespace(object_type=object_type, source="screen_session",
                              source_object_id=oid))


def test_one_ai_call_per_screen_object_the_gate_or_s4_never_both():
    from genios_engine.capture.esqe.relevance import (DECIDED_BY_LLM, DECIDED_BY_RULES,
                                                      RelevanceCandidate)
    from genios_engine.capture.gate.relevance import LLMRelevanceClassifier
    from genios_engine.capture.screen.relevance import ScreenRelevancePage
    llm, inner = _GateLLM(), _Inner()
    gate = ScreenDocRelevance(LLMRelevanceClassifier(llm),
                              _verdicts({"wa:mem": {"work": True, "memory": True}}))
    page = ScreenRelevancePage(inner, gate)

    # no verdict → the gate's one call; S4 trusts that model's keep (no second call)
    gate.classify(_obj("wa:9#5#in", thread="wa:9"), None)
    d = page.decide(RelevanceCandidate(event_id="e1", page_key="wa:9#5#in"))
    assert llm.calls == 1 and inner.decides == 0
    assert (d.relevant, d.decided_by) == (True, DECIDED_BY_LLM)
    # a memory verdict → no call at all
    gate.classify(_obj("wa:mem#5#in", thread="wa:mem"), None)
    assert page.decide(RelevanceCandidate(event_id="e2", page_key="wa:mem#5#in")).relevant
    assert llm.calls == 1 and inner.decides == 0
    # a doc the gate kept by RULE (alias hit) had no model yet → S4 makes its one call
    gate.classify(_obj("doc:1#1#doc", thread="doc:1", object_type="screen_doc", alias_hits=2),
                  None)
    assert page.decide(RelevanceCandidate(event_id="e3", page_key="doc:1#1#doc")) == "inner"
    assert llm.calls == 1 and inner.decides == 1
    # S4's deterministic rules still run first on a trusted object
    ruled = page.decide(RelevanceCandidate(event_id="e4", page_key="wa:9#5#in",
                                           sender="noreply@billing.acme.test"))
    assert (ruled.relevant, ruled.decided_by) == (False, DECIDED_BY_RULES)
    # pushed pages prime BEFORE the gate: for a screen lane that buys nothing
    assert page.prime([RelevanceCandidate(event_id="e5")]) == "inner-stats"
    assert inner.primes == 0 and page.stats == "inner-stats"


def test_only_screen_wirings_get_the_wrapped_page():
    from dataclasses import dataclass

    from genios_engine.capture.screen.relevance import ScreenRelevancePage, screen_semantic_lane

    @dataclass(frozen=True)
    class _Lane:
        relevance_page: object = None
        timezone: str = "UTC"

    inner, gate = _Inner(), ScreenDocRelevance(None)
    lane = _Lane(relevance_page=inner)
    wrapped = screen_semantic_lane(lane, gate)
    assert isinstance(wrapped.relevance_page, ScreenRelevancePage)
    assert lane.relevance_page is inner and wrapped.timezone == "UTC"   # the org's lane untouched
    assert screen_semantic_lane(None, gate) is None
    assert screen_semantic_lane(_Lane(), gate).relevance_page is None
