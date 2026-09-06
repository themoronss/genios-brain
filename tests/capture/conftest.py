"""Deterministic builders for every Layer 1 v2 capture test — one clock, one source text, one
fake model, and a refusal to reach anything real.

Layer 1's whole claim is that a fact can be checked instead of believed. A test suite for it
that quietly depends on today's date, on a live Anthropic key, or on whichever Postgres the
developer's `.env` happened to name proves the opposite: it passes for reasons the reader
cannot see, and it fails on a Tuesday. So the three sources of nondeterminism are each given
exactly one home here, and everything under `tests/capture/` takes them as parameters.

**The clock is a fixture, not a call.** `ResolvedDate.resolved_against` exists precisely so a
March event resolves "next week" against March rather than against whenever the suite ran, and
gate G1 greps `capture/validate/` for `datetime.now` and fails if it finds one. The `eval_time`
fixture is the value those units are handed; a test that needs "two days later" computes it
from `eval_time` with a `timedelta`, never from a literal it also has to keep in sync.

**The source text is a fixture, and offsets are found, not counted.** An `EvidenceSpan` is only
worth anything if `clean_text[start:end] == quote` holds byte-for-byte, and a hand-counted 412
in a test is a number nobody re-derives after the fixture text is reflowed. `span_of` locates
the quote in the source and builds the span from what it found, so a span in a test is
constructed the same way L1.5.1 verifies one.

**The model is a fake that records.** `FakeLLM` answers from a canned list and keeps every
prompt it was given, because half the extractor's gates are assertions about CALLS rather than
about output: the structured lane must make zero of them (G2), an unchanged re-run must make
zero of them (G4, 100% cache hit), and a malformed first answer must make exactly two (the one
repair retry). A fake that only returned text could not be asked any of those questions.

**Nothing here reaches the network.** `_hermetic_by_default` refuses `socket.connect` for the
duration of every test in this tree that does not carry `pg` or `llm`. That is not paranoia
about slowness — it is the same lesson as commit `ae63ef9`: the fastest way for a test to touch
production is for it to open a connection nobody in the test file ever mentions.
"""

from __future__ import annotations

import hashlib
import json
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import pytest

from genios_engine.contracts.evidence import EvidenceSpan

#: The one instant every Layer 1 test resolves relative language against.
#:
#: A **Wednesday**, deliberately: "by Friday" is then +2 days without crossing a weekend, "next
#: week" is a clean Mon-Sun range, and neither straddles a month or a year boundary — the three
#: places a date normalizer's off-by-one hides. 09:00 UTC rather than midnight so that a
#: same-day deadline is still in the future, which is the difference between "due today" and
#: "overdue" in every proximity term downstream.
EVAL_TIME = datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc)

#: The event id the worked-example spans point into. Spans are meaningless without a
#: `source_ref` — character 412 *of what* is not a receipt — and hardcoding the same literal in
#: twelve test files is how two of them end up disagreeing about the shape.
WORKED_EXAMPLE_EVENT_ID = "evt_l1_worked_example"
SOURCE_REF = f"prepared_content:{WORKED_EXAMPLE_EVENT_ID}"

#: The doc-04 L1.4.3-U2 acceptance fixture, verbatim — the message the extractor gate is scored
#: against. Stored as ONE line: the plan document wraps it across three lines for typography,
#: and if a test's offsets were computed against the wrapped form then reflowing a markdown file
#: would silently invalidate every span in the suite. One sentence per claim, no leading
#: whitespace, no trailing newline: the prepared `clean_text` this stands in for has none either.
WORKED_EXAMPLE_TEXT = (
    "Hey Rohit, we can probably move forward with the $84K annual contract, but I still need "
    "Finance to confirm whether we can absorb the increase. Also, our renewal is coming up "
    "pretty soon."
)


@pytest.fixture
def eval_time() -> datetime:
    """The frozen `resolved_against` value. Take it as a parameter; never call a clock."""
    return EVAL_TIME


@pytest.fixture
def worked_example_text() -> str:
    """The doc-04 worked example as prepared `clean_text` — the substrate for span checks."""
    return WORKED_EXAMPLE_TEXT


@pytest.fixture
def span_of(worked_example_text: str):
    """Build an `EvidenceSpan` by FINDING the quote, so no test ever hand-counts an offset.

    Two refusals are the point of this helper, and both catch a real class of bad test:

    * a quote that is not in the source raises here, loudly. A test that cites text the source
      does not contain is asserting against a fabrication — which is the exact defect the
      evidence system exists to catch, so the fixture must not paper over it by returning a
      span that "looks right";
    * a quote that appears TWICE raises too. `find` would return the first occurrence and the
      test would pass while pointing at the wrong sentence, which is indistinguishable from
      correct until the fixture text changes.
    """
    def _span(quote: str, *, text: str | None = None, source_ref: str = SOURCE_REF,
              verified: bool = False) -> EvidenceSpan:
        source = worked_example_text if text is None else text
        start = source.find(quote)
        if start < 0:
            raise AssertionError(
                f"quote is not present in the source text, so no span can point at it: {quote!r}")
        if source.find(quote, start + 1) >= 0:
            raise AssertionError(
                f"quote occurs more than once — the offsets would be a coin flip: {quote!r}")
        return EvidenceSpan(source_ref=source_ref, quote=quote, start_offset=start,
                            end_offset=start + len(quote), verified=verified)
    return _span


@dataclass(frozen=True)
class FakeCall:
    """One recorded request. Frozen because a test asserting on a prompt must be reading what
    was sent, not something a later assertion mutated."""

    prompt: str
    max_tokens: int


@dataclass
class FakeLLMResult:
    """The transport's answer, field-for-field the shape `context/llm/client.LLMResult` has.

    Duck-typed rather than imported: `capture/` must not learn its result type from `context/`
    (the import-direction ratchet in `tests/test_layer_topology.py` is the same rule one layer
    up), and W4 gives L1 its own client. Matching the field names means the extractor cannot
    tell the fake from the real thing, which is the only property that matters.
    """

    parsed: dict[str, Any]
    raw: str
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    cached: bool = False
    ok: bool = True
    error: str | None = None


class FakeLLM:
    """A model that answers from a list and remembers being asked.

    Canned responses are consumed in order, and running out is an **AssertionError**, not a
    default answer. That is deliberate: an extractor that calls the model more times than the
    test canned has either lost its cache or is retrying in a loop, and both are defects worth
    failing on. A silent fallback response would hide exactly the bug the call count exists to
    detect.

    A response may be given as:

    * a ``dict``  — the parsed object. ``raw`` is derived by ``json.dumps(sort_keys=True)`` so
      that a cache key computed over the raw text is stable across runs and across dict
      insertion order;
    * a ``str``   — raw text, parsed with plain ``json.loads``. Unparseable text yields
      ``ok=False`` with an error, which is how the one-repair-retry path is exercised. Plain
      ``json.loads``, not the repo's lenient parser: a fake that re-implemented the production
      parser would be testing itself, and one that imported it would make every extractor test
      depend on the leniency rather than on the extractor;
    * a ready ``FakeLLMResult`` — for canning a transport failure (``ok=False``, a timeout
      error string) without pretending it produced text.
    """

    def __init__(self, *responses: dict[str, Any] | str | FakeLLMResult,
                 model: str = "fake-model-1", input_tokens: int = 1000,
                 output_tokens: int = 200) -> None:
        self._responses: list[dict[str, Any] | str | FakeLLMResult] = list(responses)
        self._canned = len(responses)
        self._model = model
        self._input_tokens = input_tokens
        self._output_tokens = output_tokens
        #: Every request, in order. The assertion surface for the zero-call and
        #: exactly-two-calls gates, and for reading back the prompt the router assembled.
        self.calls: list[FakeCall] = []

    @property
    def model(self) -> str:
        return self._model

    @property
    def call_count(self) -> int:
        return len(self.calls)

    @property
    def prompts(self) -> list[str]:
        """The prompts as sent — for the injection-fence and envelope-block assertions."""
        return [c.prompt for c in self.calls]

    @staticmethod
    def content_hash(prompt: str) -> str:
        """Same digest the real client exposes, so a cache-key test can use either."""
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    def call(self, prompt: str, *, max_tokens: int = 4096) -> FakeLLMResult:
        self.calls.append(FakeCall(prompt=prompt, max_tokens=max_tokens))
        if not self._responses:
            raise AssertionError(
                f"FakeLLM was canned with {self._canned} response(s) and this is call "
                f"{len(self.calls)}. An extra model call is a defect (a cache miss, a retry "
                f"loop, a lane that should not have called at all) — can another response only "
                f"if the extra call is what the test means to assert.")
        return self._to_result(self._responses.pop(0))

    def _to_result(self, response: dict[str, Any] | str | FakeLLMResult) -> FakeLLMResult:
        if isinstance(response, FakeLLMResult):
            return response
        if isinstance(response, dict):
            return FakeLLMResult(parsed=response, raw=json.dumps(response, sort_keys=True),
                                 input_tokens=self._input_tokens,
                                 output_tokens=self._output_tokens, model=self._model)
        try:
            parsed = json.loads(response)
        except ValueError as exc:
            return FakeLLMResult(parsed={}, raw=response, input_tokens=self._input_tokens,
                                 output_tokens=self._output_tokens, model=self._model,
                                 ok=False, error=f"unparseable JSON: {exc}")
        return FakeLLMResult(parsed=parsed, raw=response, input_tokens=self._input_tokens,
                             output_tokens=self._output_tokens, model=self._model)


@pytest.fixture
def fake_llm():
    """Factory: ``llm = fake_llm({...}, {...})``. A factory rather than an instance because the
    canned answers ARE the test setup — a shared pre-built fake would force every test to
    mutate it, and the call log would then belong to whoever ran first."""
    def _build(*responses: dict[str, Any] | str | FakeLLMResult, **kwargs: Any) -> FakeLLM:
        return FakeLLM(*responses, **kwargs)
    return _build


@pytest.fixture
def fake_llm_result():
    """The result class itself, for canning a transport failure the fake must not invent."""
    return FakeLLMResult


#: Markers that legitimately need a real connection: `pg` opens the scratch Postgres,
#: `llm` calls a real model. Everything else in this tree is hermetic by construction.
_MAY_CONNECT = ("pg", "llm")


@pytest.fixture(autouse=True)
def _hermetic_by_default(request: pytest.FixtureRequest):
    """Refuse outbound sockets for every capture test that is not marked `pg` or `llm`.

    The guard is the mechanism behind the word "hermetic". A capture test reaches the network
    by accident, not on purpose: a connector fixture that forgot its transport stub, a store
    constructed with a URL from settings, a client library that phones home on import of a
    submodule. Each of those fails today as a timeout or, worse, passes slowly against
    something real — and `tests/conftest.py` can only pin the DATABASE URL, not stop a request.

    `socket.socket.connect` is patched rather than the class replaced, so anything that merely
    constructs a socket still works and only an attempt to reach a peer fails, with a message
    that names the test's own way out. Restoration removes the override rather than writing the
    inherited C method back onto the Python subclass, which would leave a shadowing attribute
    behind for the rest of the session.
    """
    if any(request.node.get_closest_marker(m) for m in _MAY_CONNECT):
        yield
        return

    def _refuse(self: socket.socket, *args: Any, **kwargs: Any):
        raise RuntimeError(
            "network access refused: capture tests are hermetic. Stub the transport, or mark "
            "the test `@pytest.mark.pg` / `@pytest.mark.llm` if it genuinely needs a real one.")

    missing = object()
    saved = {name: socket.socket.__dict__.get(name, missing) for name in ("connect", "connect_ex")}
    for name in saved:
        setattr(socket.socket, name, _refuse)
    try:
        yield
    finally:
        for name, original in saved.items():
            if original is missing:
                delattr(socket.socket, name)
            else:
                setattr(socket.socket, name, original)
