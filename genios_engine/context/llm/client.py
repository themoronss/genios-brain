from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from .parse import parse_json_lenient, strip_code_fence

#: Anthropic prices a cache WRITE at 1.25x (the 5-minute default) or 2x (the 1-hour TTL), and a
#: cache READ at 0.1x, of the base input rate.
CACHE_WRITE_MULTIPLIER = 1.25
CACHE_WRITE_MULTIPLIER_1H = 2.0
CACHE_READ_MULTIPLIER = 0.1

#: ⛔ MODELS THAT REJECT SAMPLING PARAMETERS WITH A 400. Sending `temperature` to one of these is
#: not a degraded call — it is a request the API refuses outright, so the lane gets nothing.
#:
#: MEASURED, WHICH IS WHY THIS MOVED HERE. `llm_costs` records `l4_bundle` on `claude-sonnet-5` as
#: **600 calls, 0 successes**, every one of them
#: `"`temperature` is deprecated for this model"`, from 13 Sep to 25 Sep. The narrator has never
#: produced a bundle. Nothing surfaced it because the lane fails open and a missing narrative
#: looks exactly like a narrative nobody asked for.
#:
#: WHY THE CONSTANT LIVES IN THE CLIENT AND NOT IN THE CALLER. `reason/llm_decision_maker.py` knew
#: this list and worked around it by building *its own thin client*, leaving the shared client
#: still sending `temperature=0` to every model — so the knowledge existed and the module that
#: actually sends the parameter did not have it. A second copy of a closed set is a set that
#: drifts; the module that sends the field is the one that must own which models accept it.
#: `reason` may import `context` (same-or-lower), so the decision maker now reads this one.
NO_SAMPLING_PREFIXES = ("claude-sonnet-5", "claude-opus-5", "claude-opus-4-8",
                        "claude-opus-4-7", "claude-fable")


def accepts_sampling(model: str) -> bool:
    """Whether `model` will accept `temperature`. A model we do not recognise is assumed to, which
    is the same default every Haiku-class call has always run under."""
    return not str(model).startswith(NO_SAMPLING_PREFIXES)


@dataclass
class LLMResult:
    parsed: dict[str, Any]
    raw: str
    #: COST-EQUIVALENT input tokens: uncached + 1.25 x cache writes + 0.1 x cache reads, so
    #: `llm_costs` and the daily cap price a cached call correctly without knowing about caching.
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    cached: bool = False
    ok: bool = True
    error: str | None = None
    #: The raw prompt-cache counts, for measurement.
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0
    #: ⛔ THE MODEL RAN OUT OF BUDGET, which is not the same failure as bad output and does not
    #: have the same fix. See `TRUNCATED` below.
    truncated: bool = False


#: ⛔ WHAT A TRUNCATED CALL IS CALLED, so it stops being called something else.
#:
#: MEASURED on the design partner's org 2026-10-04, across three days of `llm_costs`:
#:
#:     l1_extract     failed  n=8    output_tokens min=8192  max=8192   (ceiling 8192)
#:     l1_relevance   failed  n=11   output_tokens min=1024  max=1024   (ceiling 1024)
#:
#: EVERY failure sat at exactly its ceiling. The successes ranged freely below it (l1_extract
#: 812-8192, l1_relevance 81-1024). The model had written well-formed JSON and the API cut it
#: mid-structure; `parse_json_lenient` then returned None and this client reported **"unparseable
#: JSON"** — which sends every reader to the prompt and the schema, and the answer was never
#: there. The budget was the answer, and `resp.stop_reason` had been saying so on every one of
#: those calls while this function discarded it.
#:
#: The fix is to say the true thing. Raising a ceiling is a cost decision and needs this counter
#: first: a lane that truncates once needs a bigger budget, a lane that truncates always needs a
#: smaller question.
TRUNCATED = "truncated: the model hit max_tokens and the JSON was cut mid-structure"


class LLMClient:
    """Anthropic wrapper for L2's single combined call. temp-0 for determinism; JSON
    parsed leniently (Haiku truncation-safe). The caller does one repair retry."""

    #: `call` accepts `cache_prefix_chars`. Callers check this so test fakes need not.
    supports_prompt_cache = True

    def __init__(self, *, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model
        self._client: Any = None

    @property
    def model(self) -> str:
        return self._model

    def _c(self) -> Any:
        if self._client is None:
            from anthropic import Anthropic       # lazy: only on real calls
            # Hard per-request timeout (default SDK is ~10 min) so one hung request can't tie up an
            # L2 worker during a large onboarding drain. max_retries adds bounded backoff on
            # 429/5xx so a transient blip self-heals instead of parking the email.
            self._client = Anthropic(api_key=self._api_key, timeout=60.0, max_retries=2)
        return self._client

    @staticmethod
    def content_hash(prompt: str) -> str:
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    def call(self, prompt: str, *, max_tokens: int = 4096, cache_prefix_chars: int = 0,
             cache_ttl: str | None = None,
             timeout_s: float | None = None, max_retries: int | None = None) -> LLMResult:
        """`cache_prefix_chars` > 0 marks `prompt[:n]` as a cacheable prefix (the fixed
        instructions). The model sees the identical text either way; only the price changes.
        A prefix under the model's minimum cacheable length is simply not cached.

        `cache_ttl="1h"` keeps the entry alive for an hour instead of five minutes. The write
        costs 2x rather than 1.25x, so it is right only where the SAME prefix is re-read across
        gaps longer than five minutes — a person's screen, which is read in bursts with quiet
        between them. On continuous traffic the five-minute default is strictly cheaper.

        `timeout_s` / `max_retries` override the client's own for ONE call, without building a
        second client (a new client is a new connection pool, and an interactive lane cannot
        afford a TLS handshake): the screen lane answers a person who is looking at the screen
        and has ~3 s, where a drain has a minute and wants the retries."""
        if 0 < cache_prefix_chars < len(prompt):
            control: Any = {"type": "ephemeral"}
            if cache_ttl:
                control["ttl"] = cache_ttl
            content: Any = [
                {"type": "text", "text": prompt[:cache_prefix_chars],
                 "cache_control": control},
                {"type": "text", "text": prompt[cache_prefix_chars:]},
            ]
        else:
            content = prompt
        client = self._c()
        if timeout_s is not None or max_retries is not None:
            opts = {}
            if timeout_s is not None:
                opts["timeout"] = timeout_s
            if max_retries is not None:
                opts["max_retries"] = max_retries
            client = client.with_options(**opts)
        try:
            # `temperature=0` is the determinism this engine runs on and stays the default. It is
            # OMITTED, never changed, for the models that refuse it — see NO_SAMPLING_PREFIXES.
            # Those models are deterministic enough without it; sending it costs the whole call.
            sampling = {"temperature": 0} if accepts_sampling(self._model) else {}
            resp = client.messages.create(
                model=self._model, max_tokens=max_tokens, **sampling,
                messages=[{"role": "user", "content": content}])
        except Exception as e:      # noqa: BLE001 — network/API errors surfaced, not raised
            return LLMResult(parsed={}, raw="", ok=False, error=str(e)[:400], model=self._model)
        raw = strip_code_fence("".join(b.text for b in resp.content
                                       if getattr(b, "type", None) == "text").strip())
        usage = resp.usage
        cw = int(getattr(usage, "cache_creation_input_tokens", 0) or 0)
        cr = int(getattr(usage, "cache_read_input_tokens", 0) or 0)
        writes = CACHE_WRITE_MULTIPLIER_1H if cache_ttl == "1h" else CACHE_WRITE_MULTIPLIER
        it = (int(getattr(usage, "input_tokens", 0) or 0)
              + round(cw * writes) + round(cr * CACHE_READ_MULTIPLIER))
        ot = getattr(usage, "output_tokens", 0)
        # `stop_reason` is the API telling us WHY it stopped, and it was being thrown away.
        cut_off = str(getattr(resp, "stop_reason", "") or "") == "max_tokens"
        parsed = parse_json_lenient(raw)
        if parsed is None:
            return LLMResult(parsed={}, raw=raw, input_tokens=it, output_tokens=ot,
                             model=self._model, ok=False, truncated=cut_off,
                             error=(f"{TRUNCATED} (max_tokens={max_tokens})" if cut_off
                                    else "unparseable JSON"),
                             cache_write_tokens=cw, cache_read_tokens=cr)
        # PARSED, BUT STILL CUT SHORT. `parse_json_lenient` is deliberately forgiving and will
        # close an unterminated object, so a truncated call can come back `ok=True` carrying a
        # SHORTER answer than the model meant to give — a half-written list of observations that
        # nothing downstream can tell from a complete one. The flag travels either way.
        if cut_off:
            return LLMResult(parsed=parsed, raw=raw, input_tokens=it, output_tokens=ot,
                             model=self._model, truncated=True,
                             cache_write_tokens=cw, cache_read_tokens=cr)
        return LLMResult(parsed=parsed, raw=raw, input_tokens=it, output_tokens=ot,
                         model=self._model, cache_write_tokens=cw, cache_read_tokens=cr)
