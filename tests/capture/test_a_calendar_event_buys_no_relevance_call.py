"""STEP-18 B25 · a calendar event buys no relevance call — it is decided by rule at capture.

    pytest tests/capture/test_a_calendar_event_buys_no_relevance_call.py -q

`yc2_w27_s18` M49.C1.L-logic.V0.U01 (L1 Signals, `capture/`), `03` F42, STEP-18 §8.3 s18-F6.

⛔ WHAT WAS WRONG. `capture/pipeline.page_relevance_candidate` built the page pass's candidate with no
`is_structured`, while `capture_event` routes the same object structured (a mapped kind — a calendar
event — or an enterprise system). So the relevance page pre-judged every calendar event of an unknown
organiser as ambiguous and paid a model call about it — its item *"(no readable text)"*, a calendar
event having a `summary` and no `subject` — and at capture the cascade settled it by
`RULE_STRUCTURED_SOURCE` before the page's verdict was ever read. A page of such events also tripped
the 10% "graph-coverage" alert about nothing. The two now ask one question, `_routes_structured`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from genios_engine.capture import pipeline as P
from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.esqe.relevance import RULE_STRUCTURED_SOURCE, RelevancePage
from genios_engine.context.llm.client import LLMResult

AT = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)


class _Counting:
    """A model that answers nothing useful and counts what it was asked."""

    model = "counting"

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def call(self, prompt: str, *, max_tokens: int = 1024):
        self.prompts.append(prompt)
        return LLMResult(parsed={"verdicts": []}, raw="{}", ok=True, model=self.model)


def _meeting(n: int) -> RawObject:
    return RawObject(source="gcal", object_type="calendar_event", source_object_id=f"ev_{n}",
                     occurred_at=AT, actor_email=f"organiser{n}@stranger.test",
                     raw={"summary": f"Intro call {n}", "attendees": []})


def _mail(n: int) -> RawObject:
    return RawObject(source="gmail", object_type="email_message", source_object_id=f"m_{n}",
                     occurred_at=AT, actor_email=f"someone{n}@stranger.test",
                     raw={"subject": "Quick question", "body": "Are you free to talk next week?"})


def _prime(objects) -> tuple[_Counting, RelevancePage]:
    llm = _Counting()
    page = RelevancePage(llm=llm)
    P.prime_relevance_page(list(objects), SimpleNamespace(relevance_page=page))
    return llm, page


def test_a_calendar_event_is_a_structured_candidate_as_capture_routes_it():
    assert P.page_relevance_candidate(_meeting(1), sender_known=False).is_structured
    assert not P.page_relevance_candidate(_mail(1), sender_known=False).is_structured


def test_a_page_of_calendar_events_from_strangers_asks_the_model_nothing():
    llm, page = _prime(_meeting(n) for n in range(12))
    assert llm.prompts == [], "a paid relevance call about calendar events no capture reads"
    assert page.stats.budget_alert is None, "no graph-coverage alert about a calendar page"


def test_mail_from_strangers_is_still_primed():
    """The negative half: the page still judges the ambiguous mail it exists for."""
    llm, _page = _prime([_mail(1), _meeting(1)])
    assert len(llm.prompts) == 1
    assert "Quick question" in llm.prompts[0] and "Intro call" not in llm.prompts[0]


def test_at_capture_a_calendar_event_is_decided_by_rule_without_the_page():
    llm, page = _prime([_meeting(1)])
    candidate = P.page_relevance_candidate(_meeting(1), sender_known=False)
    decision = page.decide(candidate)
    assert decision.rule == RULE_STRUCTURED_SOURCE and llm.prompts == []


def test_capture_and_the_page_ask_the_same_question():
    """One spelling: `capture_event` routes by `_routes_structured`, the page candidate too."""
    import inspect
    assert "_routes_structured(" in inspect.getsource(P.capture_event)
    assert "_routes_structured(" in inspect.getsource(P.page_relevance_candidate)
    assert P._routes_structured("gcal", "calendar_event")
    assert not P._routes_structured("gmail", "email_message")
