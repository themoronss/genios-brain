from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from .parse import parse_json_lenient, strip_code_fence

#: Anthropic prices a cache WRITE at 1.25x and a cache READ at 0.1x the base input rate.
CACHE_WRITE_MULTIPLIER = 1.25
CACHE_READ_MULTIPLIER = 0.1


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

    def call(self, prompt: str, *, max_tokens: int = 4096,
             cache_prefix_chars: int = 0) -> LLMResult:
        """`cache_prefix_chars` > 0 marks `prompt[:n]` as a cacheable prefix (the fixed
        instructions). The model sees the identical text either way; only the price changes.
        A prefix under the model's minimum cacheable length is simply not cached."""
        if 0 < cache_prefix_chars < len(prompt):
            content: Any = [
                {"type": "text", "text": prompt[:cache_prefix_chars],
                 "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": prompt[cache_prefix_chars:]},
            ]
        else:
            content = prompt
        try:
            resp = self._c().messages.create(
                model=self._model, max_tokens=max_tokens, temperature=0,
                messages=[{"role": "user", "content": content}])
        except Exception as e:      # noqa: BLE001 — network/API errors surfaced, not raised
            return LLMResult(parsed={}, raw="", ok=False, error=str(e)[:400], model=self._model)
        raw = strip_code_fence("".join(b.text for b in resp.content
                                       if getattr(b, "type", None) == "text").strip())
        usage = resp.usage
        cw = int(getattr(usage, "cache_creation_input_tokens", 0) or 0)
        cr = int(getattr(usage, "cache_read_input_tokens", 0) or 0)
        it = (int(getattr(usage, "input_tokens", 0) or 0)
              + round(cw * CACHE_WRITE_MULTIPLIER) + round(cr * CACHE_READ_MULTIPLIER))
        ot = getattr(usage, "output_tokens", 0)
        parsed = parse_json_lenient(raw)
        if parsed is None:
            return LLMResult(parsed={}, raw=raw, input_tokens=it, output_tokens=ot,
                             model=self._model, ok=False, error="unparseable JSON",
                             cache_write_tokens=cw, cache_read_tokens=cr)
        return LLMResult(parsed=parsed, raw=raw, input_tokens=it, output_tokens=ot,
                         model=self._model, cache_write_tokens=cw, cache_read_tokens=cr)
