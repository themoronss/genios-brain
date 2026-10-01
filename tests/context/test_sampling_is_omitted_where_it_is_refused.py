"""The 400 that made `l4_bundle` produce nothing for twelve days.

    pytest tests/context/test_sampling_is_omitted_where_it_is_refused.py -q

`LLMClient.call` sent `temperature=0` to every model. Newer models refuse it outright:

    Error code: 400 — "`temperature` is deprecated for this model."

That is not a degraded answer, it is no answer. `llm_costs` records `l4_bundle` on
`claude-sonnet-5` as **600 calls, 0 successes**, 13–25 September — the narrator has never once
produced a bundle. Nothing surfaced it because the lane fails open, and a missing narrative looks
exactly like a narrative nobody asked for.

⛔ THE KNOWLEDGE EXISTED AND THE SENDER DID NOT HAVE IT. `reason/llm_decision_maker.py` already
listed these models and worked around the shared client by building a thin client of its own. That
fixed decisions and left every other lane on `LLMClient` still sending the field. A second copy of
a closed set is a set that drifts, so the list now lives with the code that sends it and the
decision maker reads that one.

These tests pin both halves: the field is omitted where it is refused, it is still sent everywhere
else, and there is exactly ONE list.
"""

from __future__ import annotations

import pytest

from genios_engine.context.llm.client import (NO_SAMPLING_PREFIXES, LLMClient,
                                              accepts_sampling)

pytestmark = pytest.mark.unit


# =================================================================================================
# 1 · the predicate
# =================================================================================================
@pytest.mark.parametrize("model", [
    "claude-sonnet-5",
    "claude-sonnet-5-20260101",
    "claude-opus-5",
    "claude-opus-4-8",
    "claude-opus-4-7",
    "claude-fable-5-1",
])
def test_models_that_refuse_sampling_are_recognised(model):
    assert accepts_sampling(model) is False


@pytest.mark.parametrize("model", [
    "claude-haiku-4-5-20251001",
    "claude-haiku-4-5",
    "some-model-we-have-never-seen",
])
def test_everything_else_still_gets_temperature(model):
    """A model we do not recognise is assumed to accept it — the same default Haiku-class calls
    have always run under. Guessing the other way would silently drop determinism."""
    assert accepts_sampling(model) is True


# =================================================================================================
# 2 · the call actually omits it
# =================================================================================================
class _Recorder:
    """Stands in for the Anthropic SDK and remembers the kwargs it was handed."""

    def __init__(self) -> None:
        self.kwargs: dict = {}
        self.messages = self

    def create(self, **kwargs):
        self.kwargs = kwargs
        raise RuntimeError("stop here — we only care about what was sent")


def _sent_kwargs(model: str) -> dict:
    client = LLMClient(api_key="k", model=model)
    recorder = _Recorder()
    client._client = recorder          # noqa: SLF001 — the seam this test exists to inspect
    client.call("hello", max_tokens=16)
    return recorder.kwargs


def test_temperature_is_not_sent_to_a_model_that_refuses_it():
    assert "temperature" not in _sent_kwargs("claude-sonnet-5")


def test_temperature_is_still_sent_to_haiku():
    """⛔ The fix must NOT become "stop sending temperature". `temperature=0` is the determinism
    this engine's replayability rests on, and it is omitted only where the API refuses it."""
    assert _sent_kwargs("claude-haiku-4-5-20251001")["temperature"] == 0


def test_the_model_and_max_tokens_still_cross():
    """The omission is surgical: nothing else about the request changed."""
    kwargs = _sent_kwargs("claude-opus-5")
    assert kwargs["model"] == "claude-opus-5"
    assert kwargs["max_tokens"] == 16
    assert kwargs["messages"][0]["role"] == "user"


# =================================================================================================
# 3 · ⛔ ONE list, not two
# =================================================================================================
def test_the_decision_maker_reads_the_same_list():
    """Both halves of the weld. If somebody re-adds a local copy to `llm_decision_maker`, the two
    stop being the same object and this fails — which is the whole reason the defect lasted twelve
    days the first time."""
    from genios_engine.reason import llm_decision_maker as dm

    assert dm._NO_SAMPLING_PREFIXES is NO_SAMPLING_PREFIXES


def test_the_decision_maker_still_refuses_sampling_for_those_models():
    """The behaviour the import must preserve: no sampling kwargs, thinking disabled."""
    from genios_engine.reason.llm_decision_maker import request_kwargs

    assert "temperature" not in request_kwargs("claude-sonnet-5")
    assert request_kwargs("claude-sonnet-5") == {"thinking": {"type": "disabled"}}
    assert request_kwargs("claude-haiku-4-5-20251001") == {"temperature": 0}
