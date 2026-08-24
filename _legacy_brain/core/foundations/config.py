"""GLOBAL TUNABLE CONSTANTS — single source of truth.

Two layers of config:
1. SETTINGS (this module's Settings class) — platform secrets + service URLs from .env
2. TUNABLES (constants below)               — system defaults; per-org overrides via DB

Per-org dynamic override pattern:
    Engine first reads `org_tunables` table for (org_id, key); falls back to default here.
    Customer onboards → defaults apply. Sales tier upgrade → DB override row added. Zero code change.

Rule:
- Add to Settings only what comes from .env (secrets, service URLs).
- Add to TUNABLES anything we may want to tune from data (thresholds, windows, model picks).
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# ─────────────────────────────────────────────────────────────────────────────
# 1. Platform secrets + service URLs (from .env)
# ─────────────────────────────────────────────────────────────────────────────


class Settings(BaseSettings):
    """Reads from .env at process start. Required values fail-fast at boot."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Core infra
    DATABASE_URL: str = Field(..., description="Supabase Postgres URL")
    REDIS_URL: str = Field(..., description="Upstash Redis URL (cache + Celery broker)")
    GENIOS_PUBLIC_URL: str = Field(default="", description="Public base for inbound webhooks")

    # Encryption (master key for customer-secret column encryption)
    GENIOS_CRYPTO_MASTER_KEY: str = Field(
        ...,
        description="32-byte url-safe base64 Fernet key — encrypts customer tokens at rest",
    )

    # JWT (human-user auth — signup/login → JWT in HttpOnly cookie + Bearer)
    JWT_SECRET: str = Field(
        default="",
        description="HMAC secret for signing JWT session tokens. Required for /auth/*.",
    )
    JWT_TTL_HOURS: int = Field(default=24 * 7, description="Session lifetime")

    # LLM keys (platform-level, our spend)
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_HAIKU_MODEL: str = "claude-haiku-4-5-20251001"
    ANTHROPIC_SONNET_MODEL: str = "claude-sonnet-4-6"
    GROQ_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    # Observability
    SENTRY_DSN: str = ""
    POSTHOG_API_KEY: str = ""
    # EU region. Reference config only — the actual event sender is
    # app/core/analytics.py (override its ingest host via POSTHOG_INGEST_HOST).
    POSTHOG_HOST: str = "https://eu.i.posthog.com"

    # Environment
    GENIOS_ENV: str = Field(default="development", description="development | staging | production")
    LOG_LEVEL: str = "INFO"


# Singleton — import this anywhere
settings = Settings()  # type: ignore[call-arg]


# ─────────────────────────────────────────────────────────────────────────────
# 2. TUNABLES — system defaults; override per-org via `org_tunables` table
# ─────────────────────────────────────────────────────────────────────────────

# ── g-i-2 Engine ────────────────────────────────────────────────────────────
CONFIDENCE_WEIGHTS: dict[str, float] = {
    "grounding": 0.4,
    "consistency": 0.2,
    "symbolic": 0.4,
}
# constraint_pass is a HARD GATE (multiplier), not a weighted term.

# Path-aware weights. When the engine takes the SYMBOLIC path, rules carry
# the load and grounding+symbolic dominate. When the engine takes the NEURAL
# path (LLM gap-fill), there's no rule match so symbolic_support is 0 by
# construction — using the default weights collapses confidence to ~0.14
# even when the LLM returned a valid, schema-constrained answer. We give
# weight to `llm_validation` (was the LLM output schema-valid + constraint-
# passing + non-empty?) so a good neural answer can clear the 0.45 NOTIFY
# threshold and the 0.75 AUTONOMOUS threshold once grounding catches up.
NEURAL_PATH_WEIGHTS: dict[str, float] = {
    "grounding": 0.20,
    "consistency": 0.20,
    "symbolic": 0.20,
    "llm_validation": 0.40,
}
# Symbolic-path weights kept backwards-compatible — `llm_validation` is
# always 0 on this path (no LLM ran), so an explicit 0 weight here means
# the math collapses to the original CONFIDENCE_WEIGHTS form.
SYMBOLIC_PATH_WEIGHTS: dict[str, float] = {
    "grounding": 0.40,
    "consistency": 0.20,
    "symbolic": 0.40,
    "llm_validation": 0.0,
}

LLM_TIMEOUT_SECONDS: int = 30
LLM_MAX_RETRIES: int = 2
CSP_TIMEOUT_SECONDS: int = 5  # Z3 fall back if exceeds

# ── g-i-3 Company Mind ──────────────────────────────────────────────────────
N_MIN_EVIDENCE: int = 20  # softened from 30 for early-startup UX
DECAY_HALF_LIFE_DAYS: int = 90
SNAPSHOT_INTERVAL_HOURS: int = 24

# ── g-i-4 Proactive Analysis ────────────────────────────────────────────────
CRON_INTERVAL_HOURS: dict[str, int] = {"sales": 2, "default": 6}
FORESIGHT_N_MIN: int = 20
PUSH_BUDGET_PER_USER_PER_DAY: int = 5
COLD_START_PRIORITY_THRESHOLD: float = 0.55
DIGEST_TIME_LOCAL: str = "09:00"
WORKFLOW_DRIFT_THRESHOLD: float = 0.3

# ── g-i-5 Module SDK ────────────────────────────────────────────────────────
GOLDEN_THRESHOLD: dict[str, float] = {
    "sales_initial": 0.70,
    "sales_target": 0.80,
}

# ── g-i-6 Artifacts ─────────────────────────────────────────────────────────
MAX_REGEN_ATTEMPTS: int = 3

# ── g-i-7 Delivery ──────────────────────────────────────────────────────────
EMAIL_RATE_PER_USER_PER_MIN: int = 1

# ── g-i-8 Foundations ───────────────────────────────────────────────────────
AUDIT_HOT_RETENTION_DAYS: int = 90
AUDIT_COLD_STORAGE: str = "s3"
CALIBRATION_WINDOW: str = "weekly"
LLM_DAILY_BUDGET_USD: dict[str, float] = {
    "default": 10.0,
    "design_partner": 50.0,
}
LLM_CIRCUIT_BREAKER_THRESHOLD: float = 1.5  # 1.5x daily budget -> halt

# ── g-i-9 User Model ────────────────────────────────────────────────────────
USER_MODEL_WINDOW_K: int = 20
USER_MODEL_VOLUME_GATE_N: int = 5


# Per-org override resolver: use `core.foundations.org_tunables.get_tunable()`
# when you need a per-org-overridable value (engine code that reads tunables
# from a request context). For pure constants (no per-org variance), import
# directly:
#     from core.foundations.config import N_MIN_EVIDENCE
