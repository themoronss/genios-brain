from __future__ import annotations

import copy
import hashlib
import logging
import re
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


#: ⛔ CLAUDE 5 THINKS BY DEFAULT, AND ITS THINKING IS SPENT FROM `max_tokens` (the 13 Oct audit,
#: s5t-F1; `yc2_w27_s18` M50.C1.L-contract.V0.U01). Sonnet 5's adaptive thinking is on unless the
#: request turns it off, and the tokens it spends reasoning are billed as output and count toward
#: `max_tokens` alongside the answer. MEASURED: the golden live pass of 12 Oct sent R-7's 4,000-token
#: ceiling to `claude-sonnet-5` — 203 calls, every one stopped at 4,000, thinking ~2,600–3,500 of it
#: (`scratchpad/live/sonnet_facts.md`). This client sent no thinking control at all; the fix lived only
#: in `reason/llm_decision_maker`, behind a bare prefix match that sent Opus 5's `disabled` to Opus 5.5.
#:
#: What a site may ask: OFF (every ceiling in this engine was sized for a model that does not think —
#: `06` D71, the default) or ADAPTIVE (a site that sized its ceiling for thinking, `06` D72).
THINKING_OFF = "off"
THINKING_ADAPTIVE = "adaptive"
THINKING_MODES = (THINKING_OFF, THINKING_ADAPTIVE)

#: How many tokens a model that CANNOT turn thinking off needs beyond the visible answer when it is
#: asked at the lowest effort. ⛔ A SIZING, NOT A MEASUREMENT: the most thinking measured on any model
#: here is Sonnet 5's at its default effort on R-7, ~2,600–3,500 tokens; `low` thinks less, so 3,500 is
#: an upper sizing. Measure it on the model before a site depends on it (STEP-13b's Opus rung).
THINKING_HEADROOM_AT_LOW_EFFORT = 3500


@dataclass(frozen=True)
class ThinkingFamily:
    """One model family's thinking controls. `off` / `adaptive` are the request fields each mode
    sends; `can_be_off` is False for a family whose thinking is always on, which is then asked at the
    lowest effort and given `headroom` tokens beside the answer (`output_ceiling`)."""

    family: str
    off: Any
    adaptive: Any
    can_be_off: bool = True
    headroom: int = 0


_DISABLED = {"thinking": {"type": "disabled"}}
_ADAPTIVE = {"thinking": {"type": "adaptive"}}
_LOWEST_EFFORT = {"output_config": {"effort": "low"}}

#: ⛔ ONE ROW PER FAMILY, matched as the family's own id or its dated snapshot (`-YYYYMMDD`), never as a
#: prefix of a longer id, and tried longest id first. Per Anthropic's model notes (13 Oct):
#:   * Sonnet 5, Opus 5, Opus 4.8 / 4.7 accept `disabled` (Opus 5 only at effort ≤ high; its default is
#:     high). Sonnet 5 and Opus 5 think when nothing is sent.
#:   * Opus 5.5 and Fable 5 / 5.1 CANNOT turn thinking off — `disabled` is a 400 at every effort — so
#:     OFF asks the lowest effort and the ceiling gets the family's headroom.
#:   * Haiku 4.5 does not think unless it is given a budget, and it is never given one: nothing sent.
#:   * A model not in the table gets nothing (its own default) and is logged — never another family's
#:     control. Sonnet 5.5's no-tools behaviour is unverified (the audit's §4.1), so it is not a row.
THINKING_FAMILIES = (
    ThinkingFamily("claude-haiku-4-5", off={}, adaptive={}),
    ThinkingFamily("claude-sonnet-5", off=_DISABLED, adaptive=_ADAPTIVE),
    ThinkingFamily("claude-opus-5", off=_DISABLED, adaptive=_ADAPTIVE),
    ThinkingFamily("claude-opus-5-5", off=_LOWEST_EFFORT, adaptive=_ADAPTIVE, can_be_off=False,
                   headroom=THINKING_HEADROOM_AT_LOW_EFFORT),
    ThinkingFamily("claude-opus-4-8", off=_DISABLED, adaptive=_ADAPTIVE),
    ThinkingFamily("claude-opus-4-7", off=_DISABLED, adaptive=_ADAPTIVE),
    ThinkingFamily("claude-fable-5", off=_LOWEST_EFFORT, adaptive=_ADAPTIVE, can_be_off=False,
                   headroom=THINKING_HEADROOM_AT_LOW_EFFORT),
    ThinkingFamily("claude-fable-5-1", off=_LOWEST_EFFORT, adaptive=_ADAPTIVE, can_be_off=False,
                   headroom=THINKING_HEADROOM_AT_LOW_EFFORT),
)

_SNAPSHOT = re.compile(r"-\d{8}")
_unknown_logged: set[str] = set()
_log = logging.getLogger("genios.context.llm.client")


def _by_length() -> list[ThinkingFamily]:
    return sorted(THINKING_FAMILIES, key=lambda f: len(f.family), reverse=True)


def thinking_family(model: str) -> ThinkingFamily | None:
    """The family `model` belongs to, or None. `claude-opus-5-5` is Opus 5.5's, never Opus 5's."""
    name = str(model or "").strip()
    for family in _by_length():
        if name == family.family or (name.startswith(family.family)
                                     and _SNAPSHOT.fullmatch(name[len(family.family):])):
            return family
    return None


def thinking_kwargs(model: str, mode: str = THINKING_OFF) -> dict[str, Any]:
    """The request fields that ask `model` for `mode` — a fresh copy, so a caller cannot edit the
    table. A model the table has not met gets nothing, logged once."""
    if mode not in THINKING_MODES:
        raise ValueError(f"unknown thinking mode {mode!r}; expected one of {THINKING_MODES}")
    family = thinking_family(model)
    if family is None:
        if model not in _unknown_logged:
            _unknown_logged.add(model)
            _log.warning("no thinking control known for model %r — sent nothing (its own default)",
                         model)
        return {}
    return copy.deepcopy(dict(family.off if mode == THINKING_OFF else family.adaptive))


def output_ceiling(model: str, ceiling: int, mode: str = THINKING_OFF) -> int:
    """The `max_tokens` a call needs: the site's own, plus the family's headroom when the site asked
    for thinking OFF and the model cannot turn it off. ADAPTIVE is sized by the site itself."""
    family = thinking_family(model)
    if mode == THINKING_OFF and family is not None and not family.can_be_off:
        return int(ceiling) + family.headroom
    return int(ceiling)


def request_controls(model: str, *, thinking: str = THINKING_OFF,
                     temperature: float = 0.0) -> dict[str, Any]:
    """Sampling and thinking together, for every caller that builds its own request: `temperature`
    only where the model takes it (`NO_SAMPLING_PREFIXES`), and the family's thinking control."""
    sampling = {"temperature": temperature} if accepts_sampling(model) else {}
    return {**sampling, **thinking_kwargs(model, thinking)}


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
    #: `call` accepts `thinking=` (and `timeout_s=`). Callers check this so test fakes need not.
    supports_thinking = True

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
             timeout_s: float | None = None, max_retries: int | None = None,
             thinking: str = THINKING_OFF) -> LLMResult:
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
        and has ~3 s, where a drain has a minute and wants the retries.

        `thinking` is OFF unless the site sized its ceiling for thinking (`THINKING_FAMILIES`)."""
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
            # The thinking control rides with it: `request_controls`.
            controls = request_controls(self._model, thinking=thinking)
            resp = client.messages.create(
                model=self._model, max_tokens=max_tokens, **controls,
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
        # nothing downstream can tell from a complete one. The flag travels either way — and so does
        # the error text (M50.C1.L-contract.V0.U01, s5t-F6): every ledger row is written from `ok`
        # and `error`, so without it a cut that parsed was a success with no error, invisible to every
        # health check. `ok` stays true: the answer is usable, and the caller decides.
        if cut_off:
            return LLMResult(parsed=parsed, raw=raw, input_tokens=it, output_tokens=ot,
                             model=self._model, truncated=True,
                             error=f"{TRUNCATED} (max_tokens={max_tokens})",
                             cache_write_tokens=cw, cache_read_tokens=cr)
        return LLMResult(parsed=parsed, raw=raw, input_tokens=it, output_tokens=ot,
                         model=self._model, cache_write_tokens=cw, cache_read_tokens=cr)
