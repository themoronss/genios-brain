""""The model ran out of budget" and "the model wrote nonsense" are different failures.

    pytest tests/context/test_a_truncated_call_is_not_bad_json.py -q

⛔ WHY THIS FILE EXISTS. Measured on the design partner's org, 2026-10-04, over three days of
`llm_costs`:

    l1_extract     failed  n=8    output_tokens  min=8192  max=8192     ceiling 8192
    l1_relevance   failed  n=11   output_tokens  min=1024  max=1024     ceiling 1024

EVERY failure sat at exactly its ceiling; every success ranged freely below it (l1_extract
812–8192, l1_relevance 81–1024). The model had written well-formed JSON and the API cut it
mid-structure. `parse_json_lenient` returned None, and the client reported **"unparseable JSON"**.

That sentence is why nobody fixed it. It sends the reader to the prompt and the schema, and the
answer was never there — the answer was the budget, and `resp.stop_reason` had been saying
`"max_tokens"` on every one of those calls while the client discarded it. The owner's own reading
of the product was "LLM achhe se call nahi hua": correct, and unprovable from the error text.

⛔ THE SECOND HALF, AND THE WORSE ONE — `test_a_truncated_call_that_still_parses_is_flagged`.
`parse_json_lenient` is deliberately forgiving and will close an unterminated object. So a
truncated call can come back `ok=True` carrying a SHORTER answer than the model meant to give — a
half-written list of observations that nothing downstream can distinguish from a complete one.
That is silent data loss, and it does not appear in the failure counts at all.

⛔ THIS FILE DOES NOT RAISE ANY CEILING. Raising one is a cost decision and needs this counter
first: a lane that truncates once needs a bigger budget, a lane that truncates always needs a
smaller question. Naming the failure is what makes that decision possible.
"""

from __future__ import annotations

import pytest

from genios_engine.context.llm.client import TRUNCATED, LLMClient, LLMResult

pytestmark = pytest.mark.unit


class _Usage:
    input_tokens = 100
    output_tokens = 8192
    cache_creation_input_tokens = 0
    cache_read_input_tokens = 0


class _Block:
    type = "text"

    def __init__(self, text):
        self.text = text


class _Resp:
    def __init__(self, text, stop_reason):
        self.content = [_Block(text)]
        self.usage = _Usage()
        self.stop_reason = stop_reason


class _Messages:
    def __init__(self, resp):
        self._resp = resp

    def create(self, **_kw):
        return self._resp


class _Anthropic:
    def __init__(self, resp):
        self.messages = _Messages(resp)

    def with_options(self, **_kw):
        return self


def _client(text: str, stop_reason: str) -> LLMClient:
    client = LLMClient.__new__(LLMClient)
    client._model = "claude-haiku-4-5-20251001"          # noqa: SLF001
    client._c = lambda: _Anthropic(_Resp(text, stop_reason))   # noqa: SLF001
    return client


#: JSON cut mid-structure, exactly as an answer stopped at max_tokens arrives.
_CUT = '{"observations": [{"kind": "commitment_made", "quote": "I will send the'


def test_a_truncated_call_says_so_instead_of_blaming_the_json():
    """⛔ THE MUTATION THIS FILE REJECTS: dropping the `stop_reason` read. Nineteen measured
    failures go back to reading "unparseable JSON", and the next person to look spends their
    afternoon on the prompt."""
    result = _client(_CUT, "max_tokens").call("p", max_tokens=8192)
    assert result.ok is False
    assert result.truncated is True
    assert TRUNCATED.split(":")[0] in result.error
    assert "8192" in result.error, "the error must name the ceiling that was hit"
    assert "unparseable JSON" not in result.error


def test_genuinely_bad_output_is_still_called_bad_output():
    """The other direction. A model that returns prose when asked for JSON has NOT run out of
    budget, and calling that truncation would send the reader to the wrong fix."""
    result = _client("I'm afraid I can't help with that.", "end_turn").call("p")
    assert result.ok is False
    assert result.truncated is False
    assert result.error == "unparseable JSON"


def test_a_truncated_call_that_still_parses_is_flagged():
    """⛔ THE SILENT ONE. `parse_json_lenient` closes an unterminated object, so this call comes
    back ok=True with FEWER observations than the model was writing. Without the flag nothing
    downstream can tell it from a complete answer, and it never appears in a failure count."""
    result = _client('{"observations": [{"kind": "commitment_made"}]', "max_tokens").call("p")
    assert result.ok is True, "a parseable answer is still usable; this is a warning, not a failure"
    assert result.truncated is True, (
        "a short answer that parsed is indistinguishable from a complete one — that is silent "
        "data loss, and it is the half of this bug that never shows up in the error counts")


def test_a_clean_call_is_not_flagged():
    """The common path must stay untouched: this flag sits on every LLM call in the engine."""
    result = _client('{"observations": []}', "end_turn").call("p")
    assert result.ok is True
    assert result.truncated is False
    assert result.error is None


def test_the_flag_defaults_off():
    """Every fake client and every test double constructs `LLMResult` without this field."""
    assert LLMResult(parsed={}, raw="").truncated is False
