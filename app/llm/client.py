"""Unified LLM client — one call site, cost logged to llm_usage, daily guardrail.

Providers wired: Anthropic (primary for reasoning + classification + drafting),
Gemini (chat + embed), Groq (fallback only). Anthropic→Groq→Gemini fallback
chain handles transient failures.

Routing table maps `purpose` → (provider, model). Swap entries here to move a
purpose to a different provider without touching callers.
"""
from __future__ import annotations

import hashlib
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

# Embedding cache: same text+model → same vector (deterministic). 24h TTL.
# Cache key includes model + dim so changing either invalidates old entries
# and prevents semantic mismatch with vectors already stored in pgvector.
EMBED_CACHE_TTL_SEC = int(os.getenv("GENIOS_EMBED_CACHE_TTL_SEC", "86400"))
EMBED_CACHE_PREFIX = "embed:"


class TenantCostGuardrailExceeded(Exception):
    """Raised when an org has hit GENIOS_LLM_DAILY_CAP_USD for today."""


# Purposes that count as "proactive" — billed to the proactive bucket so they
# don't drain user-visible context credits. Background scanners, nightly
# refreshers, and entity extractors during ingest fall here.
_PROACTIVE_PURPOSES = {
    "classify_email",       # ingest pipeline (system-driven)
    "extract_entities",     # ingest pipeline
    "calendar_extract",     # sync pipeline
    "judge_insight",        # proactive scanner
    "compose_retention_offer",  # automated retention nudges
}


def _bucket_for_purpose(purpose: str) -> str:
    """Reactive (user-triggered) calls bill the CONTEXT bucket; background
    ingest/scan calls bill PROACTIVE."""
    from app.credits import CONTEXT, PROACTIVE
    return PROACTIVE if purpose in _PROACTIVE_PURPOSES else CONTEXT


# purpose → (provider, model). Anthropic-primary for reasoning + extraction.
# Override any purpose via env: LLM_ROUTE_<UPPER_PURPOSE>="provider:model"
#   e.g. LLM_ROUTE_REASON_HAIKU="anthropic:claude-haiku-4-5-20251001"
#        LLM_ROUTE_NARRATIVE="openai:gpt-4o-mini"
# Provider must be one of: groq | gemini | anthropic | openai.
_DEFAULT_ROUTES = {
    "classify_email":   ("anthropic", "claude-haiku-4-5-20251001"),
    "extract_entities": ("anthropic", "claude-haiku-4-5-20251001"),
    "calendar_extract": ("anthropic", "claude-haiku-4-5-20251001"),
    "draft":            ("anthropic", "claude-haiku-4-5-20251001"),
    "chat":             ("gemini",    "gemini-2.5-flash"),
    "reason_haiku":     ("anthropic", "claude-haiku-4-5-20251001"),
    "reason_sonnet":    ("anthropic", "claude-sonnet-4-6"),
    "narrative":        ("anthropic", "claude-haiku-4-5-20251001"),
    "embed":            ("gemini",    "gemini-embedding-001"),
    # ── Phase 2: intent + emotion classifier (cheap, cached 5min) ──
    "classify_intent":  ("anthropic", "claude-haiku-4-5-20251001"),
    # ── Phase 3: tone-adaptive output rewrite ──
    "shape_response":   ("anthropic", "claude-haiku-4-5-20251001"),
    # ── Phase 6: personalized retention offer composition ──
    "compose_retention_offer": ("anthropic", "claude-haiku-4-5-20251001"),
    # ── Phase 1 fix-set: proactive scanner judge (keep/dismiss decision) ──
    "judge_insight":    ("anthropic", "claude-haiku-4-5-20251001"),
}


def _load_routes() -> dict:
    """Build ROUTES from defaults + env overrides. Called once at import."""
    out = dict(_DEFAULT_ROUTES)
    for purpose in list(out.keys()):
        env_key = f"LLM_ROUTE_{purpose.upper()}"
        raw = os.getenv(env_key, "").strip()
        if not raw:
            continue
        if ":" not in raw:
            logger.warning(f"{env_key}={raw!r} ignored — expected 'provider:model'")
            continue
        provider, model = raw.split(":", 1)
        provider = provider.strip().lower()
        model = model.strip()
        if provider not in {"groq", "gemini", "anthropic", "openai"}:
            logger.warning(f"{env_key}={raw!r} ignored — unknown provider {provider!r}")
            continue
        out[purpose] = (provider, model)
        logger.info(f"LLM route override: {purpose} → {provider}:{model}")
    return out


ROUTES = _load_routes()


def _embed_cache_key(model: str, dim: int, text_in: str) -> str:
    h = hashlib.md5(text_in.encode("utf-8")).hexdigest()
    return f"{EMBED_CACHE_PREFIX}{model}:{dim}:{h}"


def _embed_cache_get(key: str) -> Optional[list]:
    try:
        from app.redis_client import redis_client
        raw = redis_client.get(key)
        if not raw:
            return None
        vec = json.loads(raw)
        if isinstance(vec, list):
            return vec
    except Exception as e:
        logger.debug(f"embed cache read failed: {e}")
    return None


def _embed_cache_set(key: str, embedding: list) -> None:
    try:
        from app.redis_client import redis_client
        redis_client.setex(key, EMBED_CACHE_TTL_SEC, json.dumps(embedding))
    except Exception as e:
        logger.debug(f"embed cache write failed: {e}")


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

        # ── Sonnet daily cap (anti-abuse, only for Sonnet) ────────────────
        # Sonnet is ~3x more expensive than Haiku per call. Power users
        # spamming reason_sonnet would blow up unit economics. The cap is
        # plan-tier driven (see PLAN_CONFIG.sonnet_daily_limit) and resets
        # daily at UTC midnight. Atomic UPDATE in
        # check_and_increment_sonnet_quota — no race possible.
        if org_id and purpose == "reason_sonnet":
            self._check_sonnet_cap(org_id)

        # ── Atomic credit pre-deduct ──────────────────────────────────────
        # Charge before the call so a credit-exhausted org fails fast (402)
        # without hitting the provider. Refund on call failure. Dashboard-
        # passive renders set the request-scoped billing flag False (see
        # app.credits.billing_context) — those skip the deduct entirely so
        # opening a UI page doesn't drain user credits.
        from app.credits import is_billing_enabled
        ledger_id = self._prededuct_credits(
            org_id=org_id, purpose=purpose, trace_id=trace_id,
        ) if (org_id and is_billing_enabled()) else None

        t0 = time.monotonic()
        try:
            try:
                if provider == "groq":
                    text_out, in_tok, out_tok = self._call_groq(model, messages, temperature, max_tokens)
                elif provider == "gemini":
                    text_out, in_tok, out_tok = self._call_gemini(model, messages, temperature, max_tokens)
                elif provider == "anthropic":
                    text_out, in_tok, out_tok = self._call_anthropic(model, messages, temperature, max_tokens)
                elif provider == "openai":
                    text_out, in_tok, out_tok = self._call_openai(model, messages, temperature, max_tokens)
                else:
                    raise ValueError(f"Unknown provider: {provider}")
            except Exception as primary_err:
                # Provider fallback chain: Anthropic → Groq → Gemini.
                # Keeps the pipeline alive when a provider has quota/auth/transient errors.
                if provider == "anthropic":
                    logger.warning(f"Anthropic failed for {purpose}, falling back to Groq: {primary_err}")
                    try:
                        text_out, in_tok, out_tok = self._call_groq(
                            "llama-3.3-70b-versatile", messages, temperature, max_tokens
                        )
                        provider, model = "groq", "llama-3.3-70b-versatile"
                    except Exception as groq_err:
                        logger.warning(f"Groq fallback also failed for {purpose}, falling back to Gemini: {groq_err}")
                        text_out, in_tok, out_tok = self._call_gemini(
                            "gemini-2.5-flash", messages, temperature, max_tokens
                        )
                        provider, model = "gemini", "gemini-2.5-flash"
                elif provider == "groq":
                    logger.warning(f"Groq failed for {purpose}, falling back to Gemini: {primary_err}")
                    text_out, in_tok, out_tok = self._call_gemini(
                        "gemini-2.5-flash", messages, temperature, max_tokens
                    )
                    provider, model = "gemini", "gemini-2.5-flash"
                else:
                    raise
        except Exception:
            # All fallbacks failed — refund the pre-deduct so the user isn't
            # billed for work that produced no output.
            if ledger_id:
                self._refund_credits(org_id=org_id, ledger_id=ledger_id,
                                     reason=f"llm_call_failed:{purpose}")
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
        """Return a 768-dim embedding. Currently Gemini-only.

        Caches deterministic results in Redis keyed by model+dim+md5(text) so
        repeated situations ("follow up", "deal stuck") don't re-hit Gemini.
        Model+dim in the key prevents semantic mismatch if either changes.
        """
        provider, model = ROUTES["embed"]
        dim = 768

        cache_key = _embed_cache_key(model, dim, text_in)
        cached = _embed_cache_get(cache_key)
        if cached is not None:
            # Cache hit: skip Gemini + skip llm_usage write + skip credit
            # deduction. Cached embeddings cost nothing.
            return cached

        if org_id:
            self._check_cost_guardrail(org_id)

        # Embed misses bill the proactive bucket (called from ingest /
        # retrieval). Dashboard-passive paths skip billing — see
        # app.credits.billing_context.
        from app.credits import is_billing_enabled
        ledger_id = self._prededuct_credits(
            org_id=org_id, purpose="embed", trace_id=trace_id,
        ) if (org_id and is_billing_enabled()) else None

        t0 = time.monotonic()
        try:
            self._configure_gemini()
            import google.generativeai as genai
            result = genai.embed_content(
                model=f"models/{model}",
                content=text_in,
                output_dimensionality=dim,
            )
        except Exception:
            if ledger_id:
                self._refund_credits(org_id=org_id, ledger_id=ledger_id,
                                     reason="embed_failed")
            raise
        latency_ms = int((time.monotonic() - t0) * 1000)
        embedding = result["embedding"]
        _embed_cache_set(cache_key, embedding)
        # embed_content tokens aren't surfaced on free tier; approximate from input.
        in_tok = max(1, len(text_in) // 4)
        self._log_usage(
            org_id=org_id, purpose="embed", provider=provider, model=model,
            in_tok=in_tok, out_tok=0, cost_usd=0.0,
            latency_ms=latency_ms, trace_id=trace_id,
        )
        return embedding

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
        # Anthropic requires system messages as a top-level `system=` param,
        # not as role="system" in messages. Strip & concatenate.
        system_parts = []
        user_messages = []
        for m in messages:
            if m.get("role") == "system":
                if m.get("content"):
                    system_parts.append(m["content"])
            else:
                user_messages.append(m)
        kwargs = {
            "model": model,
            "messages": user_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system_parts:
            kwargs["system"] = "\n\n".join(system_parts)
        resp = client.messages.create(**kwargs)
        parts = [b.text for b in resp.content if getattr(b, "type", "") == "text"]
        content = "".join(parts)
        in_tok = getattr(resp.usage, "input_tokens", 0)
        out_tok = getattr(resp.usage, "output_tokens", 0)
        return content, int(in_tok or 0), int(out_tok or 0)

    def _call_openai(self, model, messages, temperature, max_tokens):
        if not config.OPENAI_API_KEY or config.OPENAI_API_KEY.startswith("dummy"):
            raise NotImplementedError(
                "OpenAI not enabled — set OPENAI_API_KEY."
            )
        from openai import OpenAI  # type: ignore
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model=model, messages=messages,
            temperature=temperature, max_tokens=max_tokens,
        )
        content = resp.choices[0].message.content or ""
        u = getattr(resp, "usage", None)
        in_tok = getattr(u, "prompt_tokens", 0) if u else 0
        out_tok = getattr(u, "completion_tokens", 0) if u else 0
        return content, int(in_tok or 0), int(out_tok or 0)

    def _configure_gemini(self) -> None:
        if self._gemini_configured:
            return
        import google.generativeai as genai
        genai.configure(api_key=config.GEMINI_API_KEY)
        self._gemini_configured = True

    # ──────────────────────────────────────────────────────────────
    # Credit bookkeeping
    # ──────────────────────────────────────────────────────────────
    def _prededuct_credits(
        self, *, org_id: str, purpose: str, trace_id: Optional[str],
    ) -> Optional[int]:
        """Atomic credit deduct before calling the provider.

        Returns ledger_id on success so a failed call can be refunded.
        Returns None on infra error (e.g. DB unavailable) — we fail-open
        in that case rather than block legitimate traffic on a DB blip.

        Raises HTTP 402 (via InsufficientCredits) if the org is out of
        credits in the relevant bucket.
        """
        from app.credits import deduct, InsufficientCredits
        from fastapi import HTTPException

        bucket = _bucket_for_purpose(purpose)
        reason = (
            f"proactive:llm_call:{purpose}"
            if bucket == "proactive"
            else f"llm_call:{purpose}"
        )

        db = SessionLocal()
        try:
            try:
                res = deduct(
                    db,
                    org_id=org_id,
                    bucket=bucket,
                    reason=reason,
                    idempotency_key=trace_id,  # trace_id makes Celery retries safe
                    related_kind="llm_usage",
                )
                db.commit()
                return res.ledger_id
            except InsufficientCredits as e:
                db.rollback()
                # 402 Payment Required — surfaced through HTTPException so
                # FastAPI routes that don't catch it produce a clean error.
                raise HTTPException(
                    status_code=402,
                    detail={
                        "error": "INSUFFICIENT_CREDITS",
                        "bucket": e.bucket,
                        "requested": e.requested,
                        "available": e.available,
                        "message": f"Out of {e.bucket} credits. Top up or upgrade to continue.",
                    },
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"credit pre-deduct failed (fail-open): {e}")
            db.rollback()
            return None
        finally:
            db.close()

    def _check_sonnet_cap(self, org_id: str) -> None:
        """Enforce per-tier daily Sonnet call limit.

        Reads `sonnet_daily_limit` from the org's plan config and asks
        `check_and_increment_sonnet_quota` to atomically test+increment
        the daily counter. Raises 429 when exhausted so the caller's
        retry/fallback chain can downgrade to Haiku transparently.
        """
        from app.credits import check_and_increment_sonnet_quota
        from app.plan_enforcer import get_org_plan
        from fastapi import HTTPException

        db = SessionLocal()
        try:
            plan = get_org_plan(db, org_id)
            limit = plan["config"].get("sonnet_daily_limit", 0)
            if limit <= 0:
                return  # unlimited (Enterprise)
            allowed = check_and_increment_sonnet_quota(db, org_id, limit)
            if not allowed:
                db.commit()  # commit any partial state cleanly
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "SONNET_DAILY_LIMIT",
                        "message": f"Daily Sonnet call limit ({limit}) reached. "
                                   f"Resets at UTC midnight. Use Haiku reasoning or wait.",
                        "limit": limit,
                    },
                )
            db.commit()
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"sonnet cap check failed (fail-open): {e}")
            db.rollback()
        finally:
            db.close()

    def _refund_credits(self, *, org_id: str, ledger_id: int, reason: str) -> None:
        """Reverse a previous deduct. Best-effort — never raises."""
        from app.credits import refund
        db = SessionLocal()
        try:
            refund(db, org_id=org_id, ledger_id=ledger_id, reason=reason)
            db.commit()
        except Exception as e:
            logger.warning(f"credit refund failed for ledger={ledger_id}: {e}")
            db.rollback()
        finally:
            db.close()

    # ──────────────────────────────────────────────────────────────
    # Cost guardrail + usage logging
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

        # ── Analytics — feed cost into the request accumulator + PostHog ──────
        try:
            from app.core.analytics import record_llm_cost, capture
            record_llm_cost(cost_usd, (in_tok or 0) + (out_tok or 0))
            if purpose != "embed":  # embeds are high-volume + zero-cost — skip event
                capture(org_id, "llm_call", {
                    "purpose": purpose,
                    "provider": provider,
                    "model": model,
                    "tokens_in": in_tok,
                    "tokens_out": out_tok,
                    "cost_usd": cost_usd,
                    "latency_ms": latency_ms,
                })
        except Exception:
            pass


llm_client = LLMClient()
