from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from .parse import parse_json_lenient, strip_code_fence


@dataclass
class LLMResult:
    parsed: dict[str, Any]
    raw: str
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    cached: bool = False
    ok: bool = True
    error: str | None = None


class LLMClient:
    """Anthropic wrapper for L2's single combined call. temp-0 for determinism; JSON
    parsed leniently (Haiku truncation-safe). The caller does one repair retry."""

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
            self._client = Anthropic(api_key=self._api_key)
        return self._client

    @staticmethod
    def content_hash(prompt: str) -> str:
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    def call(self, prompt: str, *, max_tokens: int = 4096) -> LLMResult:
        try:
            resp = self._c().messages.create(
                model=self._model, max_tokens=max_tokens, temperature=0,
                messages=[{"role": "user", "content": prompt}])
        except Exception as e:      # noqa: BLE001 — network/API errors surfaced, not raised
            return LLMResult(parsed={}, raw="", ok=False, error=str(e)[:400], model=self._model)
        raw = strip_code_fence("".join(b.text for b in resp.content
                                       if getattr(b, "type", None) == "text").strip())
        it = getattr(resp.usage, "input_tokens", 0)
        ot = getattr(resp.usage, "output_tokens", 0)
        parsed = parse_json_lenient(raw)
        if parsed is None:
            return LLMResult(parsed={}, raw=raw, input_tokens=it, output_tokens=ot,
                             model=self._model, ok=False, error="unparseable JSON")
        return LLMResult(parsed=parsed, raw=raw, input_tokens=it, output_tokens=ot,
                         model=self._model)
