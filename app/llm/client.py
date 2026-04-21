"""Unified LLM client — one call site, cost logged to llm_usage, daily guardrail.

Phase 1 providers wired: Groq (chat), Gemini (chat + embed).
Anthropic stubbed — set GENIOS_ANTHROPIC_ENABLED=true + real key to activate.

Routing table maps `purpose` → (provider, model). Swap entries here to move a
purpose to a different provider without touching callers.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Optional, Union

from sqlalchemy import text

from app import config
from app.database import SessionLocal
from app.llm.cost import calc_cost_usd

logger = logging.getLogger(__name__)


class TenantCostGuardrailExceeded(Exception):
    """Raised when an org has hit GENIOS_LLM_DAILY_CAP_USD for today."""


# purpose → (provider, model). Phase 1: Groq-heavy. Flip when Anthropic live.
ROUTES = {
    "classify_email":   ("groq",      "llama-3.3-70b-versatile"),
    "extract_entities": ("groq",      "llama-3.3-70b-versatile"),
    "calendar_extract": ("groq",      "llama-3.3-70b-versatile"),
    "draft":            ("groq",      "llama-3.3-70b-versatile"),
    "chat":             ("gemini",    "gemini-2.5-flash"),
    "reason_haiku":     ("groq",      "llama-3.3-70b-versatile"),  # → anthropic
    "reason_sonnet":    ("groq",      "llama-3.3-70b-versatile"),  # → anthropic
    "narrative":        ("groq",      "llama-3.3-70b-versatile"),  # → anthropic
    "embed":            ("gemini",    "gemini-embedding-001"),
}


class LLMClient:
    def __init__(self) -> None:
        self._groq = None
        self._gemini_configured = False

    # ──────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────
    def call(
        self,
        *,
        org_id: Optional[str],
        purpose: str,
        prompt: Optional[str] = None,
        messages: Optional[list] = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        cache_control: Optional[dict] = None,  # noqa: ARG002 — Anthropic-only, no-op elsewhere
        trace_id: Optional[str] = None,
    ) -> str:
        """Chat completion. Returns assistant text. Logs cost + tokens."""
        if purpose not in ROUTES:
            raise ValueError(f"Unknown LLM purpose: {purpose}")
        provider, model = ROUTES[purpose]
        if prompt is None and not messages:
            raise ValueError("Pass either `prompt` or `messages`.")
        if messages is None:
            messages = [{"role": "user", "content": prompt}]

        if org_id:
            self._check_cost_guardrail(org_id)

        t0 = time.monotonic()
        try:
            if provider == "groq":
                text_out, in_tok, out_tok = self._call_groq(model, messages, temperature, max_tokens)
            elif provider == "gemini":
                text_out, in_tok, out_tok = self._call_gemini(model, messages, temperature, max_tokens)
            elif provider == "anthropic":
                text_out, in_tok, out_tok = self._call_anthropic(model, messages, temperature, max_tokens)
            else:
                raise ValueError(f"Unknown provider: {provider}")
        except Exception as primary_err:
            # Provider fallback: Groq → Gemini on quota / transient errors.
            if provider == "groq":
                logger.warning(f"Groq failed for {purpose}, falling back to Gemini: {primary_err}")
                text_out, in_tok, out_tok = self._call_gemini(
                    "gemini-2.5-flash", messages, temperature, max_tokens
                )
                provider, model = "gemini", "gemini-2.5-flash"
            else:
                raise

        latency_ms = int((time.monotonic() - t0) * 1000)
        cost_usd = calc_cost_usd(provider, model, in_tok, out_tok)
        self._log_usage(
            org_id=org_id, purpose=purpose, provider=provider, model=model,
            in_tok=in_tok, out_tok=out_tok, cost_usd=cost_usd,
            latency_ms=latency_ms, trace_id=trace_id,
        )
        return text_out

    def embed(
        self,
        *,
        org_id: Optional[str],
        text_in: str,
        trace_id: Optional[str] = None,
    ) -> list:
        """Return a 768-dim embedding. Currently Gemini-only."""
        provider, model = ROUTES["embed"]
        if org_id:
            self._check_cost_guardrail(org_id)

        t0 = time.monotonic()
        self._configure_gemini()
        import google.generativeai as genai
        result = genai.embed_content(
            model=f"models/{model}",
            content=text_in,
            output_dimensionality=768,
        )
        latency_ms = int((time.monotonic() - t0) * 1000)
        # embed_content tokens aren't surfaced on free tier; approximate from input.
        in_tok = max(1, len(text_in) // 4)
        self._log_usage(
            org_id=org_id, purpose="embed", provider=provider, model=model,
            in_tok=in_tok, out_tok=0, cost_usd=0.0,
            latency_ms=latency_ms, trace_id=trace_id,
        )
        return result["embedding"]

    # ──────────────────────────────────────────────────────────────
    # Providers
    # ──────────────────────────────────────────────────────────────
    def _call_groq(self, model, messages, temperature, max_tokens):
        from groq import Groq
        if self._groq is None:
            self._groq = Groq(api_key=config.GROQ_API_KEY)
        resp = self._groq.chat.completions.create(
            model=model, messages=messages,
            temperature=temperature, max_tokens=max_tokens,
        )
        content = resp.choices[0].message.content or ""
        u = getattr(resp, "usage", None)
        in_tok = getattr(u, "prompt_tokens", 0) if u else 0
        out_tok = getattr(u, "completion_tokens", 0) if u else 0
        return content, int(in_tok or 0), int(out_tok or 0)

    def _call_gemini(self, model, messages, temperature, max_tokens):
        self._configure_gemini()
        import google.generativeai as genai
        # Collapse messages to a single prompt (Gemini single-turn path).
        prompt = "\n\n".join(m.get("content", "") for m in messages if m.get("content"))
        gm = genai.GenerativeModel(model)
        resp = gm.generate_content(
            prompt,
            generation_config={
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            },
        )
        content = getattr(resp, "text", "") or ""
        u = getattr(resp, "usage_metadata", None)
        in_tok = getattr(u, "prompt_token_count", 0) if u else max(1, len(prompt) // 4)
        out_tok = getattr(u, "candidates_token_count", 0) if u else max(1, len(content) // 4)
        return content, int(in_tok or 0), int(out_tok or 0)

    def _call_anthropic(self, model, messages, temperature, max_tokens):
        if not config.GENIOS_ANTHROPIC_ENABLED or not config.ANTHROPIC_API_KEY or \
                config.ANTHROPIC_API_KEY.startswith("dummy"):
            raise NotImplementedError(
                "Anthropic not enabled — set ANTHROPIC_API_KEY and "
                "GENIOS_ANTHROPIC_ENABLED=true (Phase 1.5)."
            )
        import anthropic  # type: ignore
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        resp = client.messages.create(
            model=model, messages=messages,
            temperature=temperature, max_tokens=max_tokens,
        )
        parts = [b.text for b in resp.content if getattr(b, "type", "") == "text"]
        content = "".join(parts)
        in_tok = getattr(resp.usage, "input_tokens", 0)
        out_tok = getattr(resp.usage, "output_tokens", 0)
        return content, int(in_tok or 0), int(out_tok or 0)

    def _configure_gemini(self) -> None:
        if self._gemini_configured:
            return
        import google.generativeai as genai
        genai.configure(api_key=config.GEMINI_API_KEY)
        self._gemini_configured = True

    # ──────────────────────────────────────────────────────────────
    # Bookkeeping
    # ──────────────────────────────────────────────────────────────
    def _check_cost_guardrail(self, org_id: str) -> None:
        cap = config.GENIOS_LLM_DAILY_CAP_USD
        if cap <= 0:
            return
        db = SessionLocal()
        try:
            row = db.execute(
                text("""
                    SELECT COALESCE(SUM(cost_usd), 0) AS spent
                    FROM llm_usage
                    WHERE org_id = :oid
                      AND called_at >= date_trunc('day', NOW() AT TIME ZONE 'UTC')
                      AND called_at <  date_trunc('day', NOW() AT TIME ZONE 'UTC') + INTERVAL '1 day'
                """),
                {"oid": org_id},
            ).fetchone()
            spent = float(row.spent) if row and row.spent is not None else 0.0
            if spent >= cap:
                raise TenantCostGuardrailExceeded(
                    f"Org {org_id} hit daily LLM cap (${spent:.2f} / ${cap:.2f})."
                )
        finally:
            db.close()

    def _log_usage(self, *, org_id, purpose, provider, model,
                   in_tok, out_tok, cost_usd, latency_ms, trace_id):
        if not org_id:
            return  # system-level calls (smoke tests) — skip DB write
        db = SessionLocal()
        try:
            db.execute(
                text("""
                    INSERT INTO llm_usage (
                        org_id, purpose, provider, model,
                        input_tokens, output_tokens, cost_usd,
                        latency_ms, trace_id
                    ) VALUES (
                        :org_id, :purpose, :provider, :model,
                        :in_tok, :out_tok, :cost,
                        :lat, :trace
                    )
                """),
                {
                    "org_id": org_id, "purpose": purpose,
                    "provider": provider, "model": model,
                    "in_tok": in_tok, "out_tok": out_tok,
                    "cost": cost_usd, "lat": latency_ms, "trace": trace_id,
                },
            )
            db.commit()
        except Exception as e:
            logger.warning(f"llm_usage log failed: {e}")
            db.rollback()
        finally:
            db.close()


llm_client = LLMClient()
