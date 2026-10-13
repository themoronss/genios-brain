"""Deep analyze, analyze and query ask the model with thinking off.

    pytest tests/reason/test_run_query_asks_without_thinking.py -q

⛔ `yc2_w27_s18` M50.C3.L-logic.V1.U05 (the 13 Oct audit's T5-6, s5t-F7). `reason/intelligence.run_query`
asks for one explanation sentence (30–130 tokens) under a 700-token ceiling — on `claude-sonnet-5`
when `deep=true` (`api/intelligence_routes`, hard-coded). Sonnet 5 thinks by default and its thinking is
spent from the same 700, so the sentence can be cut — and a cut answer is cached as `llm_unavailable`
until the graph moves. `06` D71: the call asks with thinking off, through a client that says it takes
the mode (`supports_thinking`); a client that does not is called exactly as before.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from genios_engine.context.llm.client import THINKING_OFF
from genios_engine.reason import intelligence

pytestmark = pytest.mark.unit

NOW = datetime(2026, 10, 13, 9, 0, tzinfo=timezone.utc)


def _signal():
    return SimpleNamespace(rule_id="cooling_deal", reason_code="cooling_deal", score=82,
                           play="restore_momentum", evidence={"field": "deal.status", "value": "open"},
                           display_name="Acme", subject_node_id="deal_1",
                           score_inputs={"marker": "cooling_deal", "C": 90},
                           reasoning_run_id="run_cooling_deal")


class _Sends:
    supports_thinking = True
    model = "claude-sonnet-5"

    def __init__(self):
        self.sent: list[dict] = []

    def call(self, prompt, *, max_tokens=700, **kw):
        self.sent.append({"max_tokens": max_tokens, **kw})
        return SimpleNamespace(ok=True, parsed={"explanation": "Acme has a cooling deal signal."},
                               input_tokens=10, output_tokens=10)


class _Plain:
    model = "claude-haiku-4-5-20251001"

    def __init__(self):
        self.ceilings: list[int] = []

    def call(self, prompt, *, max_tokens=700):
        self.ceilings.append(max_tokens)
        return SimpleNamespace(ok=True, parsed={"explanation": "Acme has a cooling deal signal."},
                               input_tokens=10, output_tokens=10)


def _query(monkeypatch, llm):
    monkeypatch.setattr(intelligence, "_retrieve", lambda *_a, **_k: ([_signal()], [], None))
    return intelligence.run_query(org_id="org_t5", module_id="sales", question="What now?",
                                  extra_facts={}, store=object(), llm=llm, registry=None,
                                  graph_version=1, eval_time=NOW)


def test_the_explanation_is_asked_with_thinking_off(monkeypatch):
    llm = _Sends()
    _env, result = _query(monkeypatch, llm)
    assert result is not None
    assert llm.sent == [{"max_tokens": 700, "thinking": THINKING_OFF}]


def test_a_client_that_does_not_take_the_mode_is_called_as_before(monkeypatch):
    llm = _Plain()
    _query(monkeypatch, llm)
    assert llm.ceilings == [700]
