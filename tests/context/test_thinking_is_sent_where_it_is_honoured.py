"""Claude 5 thinks by default, and its thinking counts toward `max_tokens`.

    pytest tests/context/test_thinking_is_sent_where_it_is_honoured.py -q

⛔ WHY THIS FILE EXISTS (`yc2_w27_s18` M50.C1.L-contract.V0.U01, the 13 Oct audit's T5-1, s5t-F1 and F8).
The golden live pass of 12 Oct ran the R-7 expert on `claude-sonnet-5`: 203 calls reached the API and
EVERY ONE stopped at `max_tokens` = 4,000 — 196 unparseable, 7 cut and closed by the lenient parser with
1,636–4,899 visible characters. Sonnet 5's adaptive thinking is on by default and is billed and counted
as output, so thinking took about 2,600–3,500 of the 4,000. `LLMClient.call` sent no thinking control at
all; the only fix lived in `reason/llm_decision_maker.DecisionClient`, which matched models by a bare
prefix and would have sent Opus 5's `disabled` to `claude-opus-5-5` — a model that cannot turn thinking
off, so a 400 on every call.

These tests hold the table: each family gets the control it honours, a family is matched as itself or
its dated snapshot and never as a prefix of a longer id, thinking is OFF unless a site asks (`06` D71),
and a model that cannot stop thinking is asked at the lowest effort with its own headroom.
"""

from __future__ import annotations

import logging

import pytest

from genios_engine.context.llm import client as C
from genios_engine.context.llm.client import (
    THINKING_ADAPTIVE,
    THINKING_FAMILIES,
    THINKING_OFF,
    LLMClient,
    output_ceiling,
    request_controls,
    thinking_family,
    thinking_kwargs,
)

pytestmark = pytest.mark.unit

_DISABLED = {"thinking": {"type": "disabled"}}
_ADAPTIVE = {"thinking": {"type": "adaptive"}}
_LOW = {"output_config": {"effort": "low"}}


# =================================================================================================
# 1 · what OFF sends, per family
# =================================================================================================
@pytest.mark.parametrize("model, sent", [
    ("claude-sonnet-5", _DISABLED),
    ("claude-sonnet-5-20260601", _DISABLED),
    ("claude-opus-5", _DISABLED),
    ("claude-opus-4-8", _DISABLED),
    ("claude-opus-4-7", _DISABLED),
    # ⛔ cannot be off: the lowest effort, never `disabled` (a 400 at every effort level)
    ("claude-opus-5-5", _LOW),
    ("claude-opus-5-5-20261101", _LOW),
    ("claude-fable-5", _LOW),
    ("claude-fable-5-1", _LOW),
    # Haiku does not think unless it is given a budget, and it is never given one
    ("claude-haiku-4-5", {}),
    ("claude-haiku-4-5-20251001", {}),
])
def test_off_sends_what_the_family_honours(model, sent):
    assert thinking_kwargs(model, THINKING_OFF) == sent


@pytest.mark.parametrize("model", ["claude-opus-5-5", "claude-opus-5-5-20261101", "claude-fable-5-1"])
def test_a_model_that_cannot_stop_thinking_never_gets_disabled(model):
    """⛔ THE PREFIX DEFECT (s5t-F8). `"claude-opus-5-5".startswith("claude-opus-5")` is true, and the
    decision client sent Opus 5's `disabled` to it."""
    assert "thinking" not in thinking_kwargs(model, THINKING_OFF)


@pytest.mark.parametrize("model", ["claude-sonnet-5-5", "claude-opus-5-7", "claude-sonnet-50",
                                   "gpt-whatever", "", "fake"])
def test_an_id_that_only_starts_like_a_family_is_not_that_family(model):
    """Never a bare prefix: an id is its family's, or the family's plus a dated snapshot. A model this
    table has not met gets nothing — its own default — rather than another family's control."""
    assert thinking_family(model) is None
    assert thinking_kwargs(model, THINKING_OFF) == {}


def test_families_are_tried_longest_id_first():
    """Belt and braces with the snapshot rule: a longer id is never shadowed by a shorter one."""
    lengths = [len(f.family) for f in C._by_length()]          # noqa: SLF001
    assert lengths == sorted(lengths, reverse=True)
    assert thinking_family("claude-opus-5-5").family == "claude-opus-5-5"
    assert thinking_family("claude-opus-5").family == "claude-opus-5"
    assert thinking_family("claude-fable-5-1").family == "claude-fable-5-1"


def test_every_family_appears_once():
    names = [f.family for f in THINKING_FAMILIES]
    assert len(names) == len(set(names))


# =================================================================================================
# 2 · what ADAPTIVE sends
# =================================================================================================
@pytest.mark.parametrize("model, sent", [
    ("claude-sonnet-5", _ADAPTIVE),
    ("claude-opus-5", _ADAPTIVE),
    ("claude-opus-5-5", _ADAPTIVE),
    ("claude-haiku-4-5-20251001", {}),
])
def test_adaptive_sends_what_the_family_honours(model, sent):
    assert thinking_kwargs(model, THINKING_ADAPTIVE) == sent


def test_an_unnamed_mode_is_refused():
    with pytest.raises(ValueError):
        thinking_kwargs("claude-sonnet-5", "maybe")


def test_the_table_hands_out_copies():
    """A caller that edits what it was handed must not edit the table."""
    sent = thinking_kwargs("claude-sonnet-5", THINKING_OFF)
    sent["thinking"]["type"] = "adaptive"
    assert thinking_kwargs("claude-sonnet-5", THINKING_OFF) == _DISABLED


def test_an_unknown_model_is_logged(caplog):
    caplog.set_level(logging.WARNING, logger="genios.context.llm.client")
    C._unknown_logged.discard("claude-sonnet-9")             # noqa: SLF001
    thinking_kwargs("claude-sonnet-9", THINKING_OFF)
    assert any("claude-sonnet-9" in r.getMessage() for r in caplog.records)


# =================================================================================================
# 3 · the ceiling a model that cannot stop thinking needs
# =================================================================================================
def test_a_model_that_can_stop_thinking_keeps_the_sites_ceiling():
    assert output_ceiling("claude-sonnet-5", 2400, THINKING_OFF) == 2400
    assert output_ceiling("claude-haiku-4-5-20251001", 600, THINKING_OFF) == 600
    assert output_ceiling("unknown-model", 600, THINKING_OFF) == 600


def test_a_model_that_cannot_stop_thinking_gets_its_own_headroom():
    """Its thinking is spent from the same `max_tokens` as the answer the site was sized for."""
    family = thinking_family("claude-opus-5-5")
    assert family.can_be_off is False and family.headroom > 0
    assert output_ceiling("claude-opus-5-5", 2400, THINKING_OFF) == 2400 + family.headroom
    assert output_ceiling("claude-fable-5-1", 2400, THINKING_OFF) > 2400


def test_adaptive_is_sized_by_the_site_itself():
    """A site that asks for thinking has sized its ceiling for it (`06` D72's 12,000)."""
    assert output_ceiling("claude-opus-5-5", 12000, THINKING_ADAPTIVE) == 12000


# =================================================================================================
# 4 · the call actually sends it
# =================================================================================================
class _Recorder:
    def __init__(self) -> None:
        self.kwargs: dict = {}
        self.messages = self

    def create(self, **kwargs):
        self.kwargs = kwargs
        raise RuntimeError("stop here — only what was sent matters")


def _sent(model: str, **call_kw) -> dict:
    client = LLMClient(api_key="k", model=model)
    recorder = _Recorder()
    client._client = recorder                                  # noqa: SLF001
    client.call("hello", max_tokens=16, **call_kw)
    return recorder.kwargs


def test_the_client_says_it_takes_a_thinking_mode():
    assert LLMClient.supports_thinking is True


def test_thinking_is_off_unless_a_site_asks():
    """`06` D71: every ceiling in the engine was sized for a model that does not think."""
    sent = _sent("claude-sonnet-5")
    assert sent["thinking"] == {"type": "disabled"}
    assert "temperature" not in sent


def test_a_site_may_ask_for_adaptive():
    assert _sent("claude-sonnet-5", thinking=THINKING_ADAPTIVE)["thinking"] == {"type": "adaptive"}


def test_opus_5_5_is_asked_at_low_effort_and_never_disabled():
    sent = _sent("claude-opus-5-5")
    assert sent["output_config"] == {"effort": "low"}
    assert "thinking" not in sent and "temperature" not in sent


def test_haiku_is_asked_exactly_as_before():
    """No new field reaches the model every lane runs on today."""
    sent = _sent("claude-haiku-4-5-20251001")
    assert sent["temperature"] == 0
    assert set(sent) == {"model", "max_tokens", "temperature", "messages"}


# =================================================================================================
# 5 · the raw-SDK callers read the same answer
# =================================================================================================
def test_request_controls_carry_sampling_and_thinking_together():
    assert request_controls("claude-haiku-4-5", temperature=0.3) == {"temperature": 0.3}
    assert request_controls("claude-sonnet-5", temperature=0.3) == _DISABLED
    assert request_controls("claude-opus-5-5") == _LOW
    assert request_controls("claude-sonnet-5", thinking=THINKING_ADAPTIVE) == _ADAPTIVE
