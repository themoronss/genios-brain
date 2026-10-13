"""The gate asks the model for what the site was sized for: its thinking mode, its timeout, its ceiling.

    pytest tests/reason/test_the_gate_sends_the_sites_thinking.py -q

⛔ `yc2_w27_s18` M50.C2.L-logic.V2.U03 (the 13 Oct audit's T5-4). `RSiteGate.consult` called
`client.call(prompt, max_tokens=ceiling)` and nothing else, so R-1, R-2 and R-7 reached Claude Sonnet 5
with its adaptive thinking on — spent from the same `max_tokens` as the answer. The site now says what it
may ask (`sites.SITE_THINKING`, OFF by `06` D71; `SITE_TIMEOUT_S`), and the gate sends it to a client that
says it takes it (`supports_thinking`, as `supports_prompt_cache`: the fakes without `**kw` keep
working). A model that cannot turn thinking off (Opus 5.5, Fable) is priced and called at its own
ceiling — the site's plus the family's headroom (`context/llm/client.output_ceiling`) — so the budget's
pre-flight prices the call it will actually make.
"""
from __future__ import annotations

import pytest

from genios_engine.context.llm.client import (
    THINKING_ADAPTIVE,
    THINKING_OFF,
    LLMResult,
    output_ceiling,
)
from genios_engine.reason.bundle import gate as G
from genios_engine.reason.bundle import sites as S
from genios_engine.reason.bundle.budget import NarrativeBudget

pytestmark = pytest.mark.unit

ORG = "org_t5_thinking"


def _good() -> LLMResult:
    return LLMResult(parsed={"mode": "wait"}, raw="{}", ok=True, model="claude-sonnet-5",
                     input_tokens=900, output_tokens=90)


class _Sends:
    """A client that takes the thinking mode, and remembers every call's keywords."""

    supports_thinking = True

    def __init__(self, model: str = "claude-sonnet-5") -> None:
        self.model = model
        self.sent: list[dict] = []

    def call(self, prompt, *, max_tokens=400, **kw):
        self.sent.append({"max_tokens": max_tokens, **kw})
        return _good()


class _Plain:
    """A fake as most tests write one: no `**kw`, no capability."""

    model = "claude-sonnet-5"

    def __init__(self) -> None:
        self.ceilings: list[int] = []

    def call(self, prompt, *, max_tokens=400):
        self.ceilings.append(max_tokens)
        return _good()


class _Priced(NarrativeBudget):
    """The expert's own budget, remembering every pre-flight estimate it was asked about."""

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self.estimates: list[int] = []

    def check(self, estimate):
        self.estimates.append(estimate)
        return super().check(estimate)


def _consult(client, site=S.SITE_EXPERT, budget=None):
    feature = "expert_review" if site == S.SITE_EXPERT else "bundle"
    gate = G.RSiteGate(org_id=ORG, engine=None, client=client, store=None,
                       activated=frozenset({feature}),
                       budget=budget or NarrativeBudget(org_id=ORG, daily_cap_micro_usd=10_000_000,
                                                        per_call_cap_micro_usd=10_000_000))
    return gate.consult(site=site, cache_key="k", build_prompt=lambda fb: "the dossier",
                        validate=lambda p: (dict(p), (), {"accepted": True}), feature=feature)


def test_the_expert_is_asked_with_thinking_off_its_ceiling_and_its_timeout():
    client = _Sends()
    assert _consult(client).outcome == S.OUTCOME_RAN
    assert client.sent == [{"max_tokens": 6000, "thinking": THINKING_OFF,
                            "timeout_s": S.timeout_s(S.SITE_EXPERT)}]


def test_the_narrative_is_asked_with_thinking_off_and_the_clients_own_timeout():
    client = _Sends()
    _consult(client, site=S.SITE_NARRATE)
    assert client.sent == [{"max_tokens": S.max_output_tokens(S.SITE_NARRATE),
                            "thinking": THINKING_OFF}]


def test_the_mode_is_the_sites_own_word(monkeypatch):
    """`06` D72's arm B: the site says adaptive, and the gate sends exactly that."""
    monkeypatch.setitem(S.SITE_THINKING, S.SITE_EXPERT, THINKING_ADAPTIVE)
    client = _Sends()
    _consult(client)
    assert client.sent[0]["thinking"] == THINKING_ADAPTIVE


def test_a_client_that_does_not_say_it_takes_thinking_is_called_as_before():
    client = _Plain()
    assert _consult(client).outcome == S.OUTCOME_RAN
    assert client.ceilings == [6000]


def test_a_model_that_cannot_stop_thinking_is_priced_and_called_at_its_own_ceiling():
    """Opus 5.5 thinks at every effort: asked OFF it gets `effort: low`, and the ceiling its thinking
    needs on top of the answer — priced BEFORE the call, so the budget refuses what it cannot afford."""
    client = _Sends(model="claude-opus-5-5")
    own = output_ceiling("claude-opus-5-5", 6000, THINKING_OFF)
    assert own > 6000
    budget = _Priced(org_id=ORG, daily_cap_micro_usd=10_000_000, per_call_cap_micro_usd=10_000_000)
    _consult(client, budget=budget)
    assert client.sent[0]["max_tokens"] == own
    from genios_engine.reason.bundle.budget import estimate_micro_usd
    assert budget.estimates == [estimate_micro_usd(site=S.SITE_EXPERT, prompt_chars=len("the dossier"),
                                                   max_output_tokens=own)]


def test_a_retry_is_asked_the_same_way():
    class _JunkThenGood(_Sends):
        def call(self, prompt, *, max_tokens=400, **kw):
            self.sent.append({"max_tokens": max_tokens, **kw})
            if len(self.sent) == 1:
                return LLMResult(parsed={}, raw="no", ok=False, error="unparseable JSON",
                                 model=self.model, input_tokens=9, output_tokens=9)
            return _good()
    client = _JunkThenGood()
    assert _consult(client).attempts == 2
    assert client.sent[0] == client.sent[1]
