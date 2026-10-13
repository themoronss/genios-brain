"""The recorder returns what production's client returns, and keeps every call it was asked to make.

    pytest tests/replays/test_the_recorder_keeps_every_call.py -q

⛔ `yc2_w27_s18` M50.C4.L-integration.V0.U08 (the 13 Oct audit's T5-9, s5t-F12). The Sonnet live pass of
12 Oct ran 203 R-7 calls and its scorecard said $0.3533. `CassetteRecorder.call` raised on any answer
with `ok=False`, so a cut answer reached the R-7 gate as an EXCEPTION: recorded `model_call_raised`, not
charged, no tokens, and RETRIED — where production returns a truncated outcome and never retries it
(`03` F140). And the scorecard summed the cassette, which holds only the answers it kept: 7 of 203.

Now a cut or an unparseable answer comes back to the chain exactly as `LLMClient` returns it — the gate
does what production does — and only a transport failure (no answer, no tokens) raises. A cassette
still holds only whole answers; the recorder's `ledger` holds every call, in order, with its tokens.
"""
from __future__ import annotations

import pytest

from genios_engine.context.llm.client import THINKING_OFF, LLMResult
from genios_engine.reason.bundle import gate as G
from genios_engine.reason.bundle import sites as S
from genios_engine.reason.bundle.budget import NarrativeBudget
from tests.replays.harness import SITE_MARKERS, CassetteRecorder, cassette_key

pytestmark = pytest.mark.unit

MARK = {site: marker for site, _module, marker in SITE_MARKERS}
PROMPT = "…" + MARK["expert"] + "… the dossier"


class _Model:
    model = "claude-sonnet-5"

    def __init__(self, *answers: LLMResult) -> None:
        self.answers = list(answers)
        self.seen: list[dict] = []

    def call(self, prompt, *, max_tokens=4096, **kw):
        self.seen.append({"max_tokens": max_tokens, **kw})
        return self.answers.pop(0)


def _cut(parsed=None) -> LLMResult:
    return LLMResult(parsed=parsed or {}, raw='{"mode": "act", "facts": [', ok=parsed is not None,
                     model="claude-sonnet-5", input_tokens=5600, output_tokens=6000, truncated=True,
                     error="truncated: the model hit max_tokens and the JSON was cut mid-structure "
                           "(max_tokens=6000)")


def _good() -> LLMResult:
    return LLMResult(parsed={"mode": "wait"}, raw='{"mode": "wait"}', ok=True, model="claude-sonnet-5",
                     input_tokens=5600, output_tokens=2000)


def _junk() -> LLMResult:
    return LLMResult(parsed={}, raw="not json", ok=False, error="unparseable JSON",
                     model="claude-sonnet-5", input_tokens=5600, output_tokens=40)


def _transport() -> LLMResult:
    return LLMResult(parsed={}, raw="", ok=False, error="Connection error.", model="claude-sonnet-5")


@pytest.mark.parametrize("answer", [_cut, lambda: _cut({"mode": "act"}), _junk])
def test_a_cut_or_unparseable_answer_comes_back_as_production_returns_it(answer):
    given = answer()
    recorder = CassetteRecorder(_Model(given))
    assert recorder.call(PROMPT, max_tokens=6000) is given
    assert recorder.cassette == {}, "a cassette holds whole answers only"


def test_a_transport_failure_still_raises_and_is_still_kept():
    recorder = CassetteRecorder(_Model(_transport()))
    with pytest.raises(RuntimeError, match="Connection error"):
        recorder.call(PROMPT)
    assert recorder.ledger == [{"site": "expert", "key": cassette_key(PROMPT), "model": "claude-sonnet-5",
                                "input_tokens": 0, "output_tokens": 0, "ok": False, "truncated": False,
                                "transport_failed": True, "visible_chars": 0}]


def test_the_ledger_keeps_every_call_in_order_with_its_tokens():
    recorder = CassetteRecorder(_Model(_cut(), _junk(), _good()))
    for _ in range(3):
        recorder.call(PROMPT, max_tokens=6000)
    assert [(r["ok"], r["truncated"], r["output_tokens"]) for r in recorder.ledger] == [
        (False, True, 6000), (False, False, 40), (True, False, 2000)]
    assert sum(r["input_tokens"] for r in recorder.ledger) == 3 * 5600
    assert recorder.ledger[0]["visible_chars"] == len(_cut().raw)
    assert list(recorder.cassette) == [cassette_key(PROMPT)]


def test_the_recorder_passes_the_thinking_mode_through_when_its_model_takes_it():
    class _Takes(_Model):
        supports_thinking = True
    inner = _Takes(_good())
    recorder = CassetteRecorder(inner)
    assert recorder.supports_thinking is True
    recorder.call(PROMPT, max_tokens=6000, thinking=THINKING_OFF, timeout_s=120.0)
    assert inner.seen == [{"max_tokens": 6000, "thinking": THINKING_OFF, "timeout_s": 120.0}]
    assert CassetteRecorder(_Model(_good())).supports_thinking is False


def test_through_the_gate_a_cut_is_truncated_charged_and_never_retried():
    """⛔ What the 12 Oct pass got wrong, end to end: the gate sees the cut answer, not an exception."""
    model = _Model(_cut(), _good())
    recorder = CassetteRecorder(model)
    gate = G.RSiteGate(org_id="org_t5_rec", engine=None, client=recorder, store=None,
                       activated=frozenset({"expert_review"}),
                       budget=NarrativeBudget.for_site(S.SITE_EXPERT, org_id="org_t5_rec"))
    result = gate.consult(site=S.SITE_EXPERT, cache_key="k", build_prompt=lambda fb: PROMPT,
                          validate=lambda p: (dict(p), (), {}), feature="expert_review")
    assert result.outcome == S.OUTCOME_TRUNCATED and result.cost_micro_usd > 0
    assert len(model.seen) == 1 and len(recorder.ledger) == 1
