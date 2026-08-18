from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed settings from env (GENIOS_* prefix) / .env file.

    Empty DATABASE_URL  → in-memory repos (dev).
    Empty COMPOSIO keys → fake connector (dev).
    Fill .env to switch either to real, with no code change.
    """

    model_config = SettingsConfigDict(env_prefix="GENIOS_", env_file=".env", extra="ignore")

    env: str = "dev"

    # storage
    database_url: str = ""                       # Supabase Postgres

    # composio (auth + data delivery) — API key is GLOBAL (GeniOS's, one).
    # Per-org composio_user_id lives in the connections table, NOT here.
    composio_api_key: str = ""
    composio_gmail_account: str = ""             # optional shared connected-account id
    # JSON map tool→Composio auth_config_id, e.g. {"gmail":"ac_..","notion":"ac_..","gcal":"ca_.."}
    # Each auth_config is created ONCE in the Composio dashboard per toolkit. Needed for OAuth connect.
    composio_auth_configs: str = "{}"

    # crypto (raw payload encryption at rest)
    crypto_key: str = ""                         # Fernet key

    # auth + cache (ported from genios-brain, engine-native). Both optional:
    # empty REDIS_URL → NullCache no-op (Redis is a prod accelerator, not a hard dep).
    redis_url: str = ""                          # rediss://… (Upstash) or redis://localhost
    jwt_secret: str = "genios-dev-secret-change-in-prod"   # dashboard-session JWT signing
    internal_token: str = ""                     # cron/internal endpoints (sweep, ingest-all)
    # GeniOS staff logins allowed into the cross-org admin console, comma-separated emails.
    # Deliberately env-only: superadmin is a property of US, not of a tenant row, so granting it
    # never means writing to a customer's account. Empty (the default) = nobody, which is what a
    # customer deployment should always be.
    superadmin_emails: str = ""

    # PostHog (server-side product analytics). Empty key = emitter off, which is the correct
    # default for dev and for any self-hosted deployment. Host is the INGEST host
    # (eu.i.posthog.com), not the app/query host.
    posthog_api_key: str = ""
    posthog_host: str = "https://eu.i.posthog.com"
    composio_webhook_secret: str = ""            # HMAC-SHA256 secret for inbound Composio webhooks
    cors_origins: str = "*"                       # comma-separated dashboard origins ('*' = dev)

    # LLM (L2 extraction) — Anthropic. The single combined relevance+extraction call.
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5-20251001"

    # automatic data sync (in-process scheduler, NO Celery/Upstash). On startup the engine runs a
    # cross-org sync sweep every `sync_interval_hours` (L1 pull → L2/L3/L5), so connected tools stay
    # fresh without a button click. Set scheduler_enabled=false (or interval<=0) to disable — e.g. if
    # an external cron hits /ingest/all instead, or to avoid double-runs on a multi-instance deploy.
    scheduler_enabled: bool = True
    sync_interval_hours: float = 6.0             # cadence of the auto-sync sweep (0 = off)
    sync_initial_delay_seconds: int = 45         # wait after startup before the first sweep
    sync_batch_limit: int = 25                   # records pulled per connection per sweep

    # tenant / options
    org_id: str = "org_trial"
    mask_phone: bool = False
    # optional DETERMINISTIC S2 relevance classifier in L1 (dev/regex fallback). Default off.
    enable_l1_relevance: bool = False
    # The L1 S2 LLM junk-gate — the reliable filter that keeps noise OUT of the graph. On by
    # default, but only actually runs when an Anthropic key is present (so hermetic tests without
    # a key are unaffected). Set false to disable the gate even in production.
    l1_llm_gate: bool = True
    # OCR (Tesseract) fallback for scanned/image docs. Native text always works; OCR
    # needs the tesseract binary, so default off — turn on where the binary is present.
    enable_ocr: bool = False
    # Layer 3 Domain Expertise compiler, shadow pass. When on, each sweep also compiles the
    # active L2 situations into ExpertisePackages (route/coverage measured, nothing persisted,
    # NO decision impact) so route/package parity can be observed before any live cutover.
    # Default off — this is the design's mandated shadow-first activation step.
    use_domain_compiler: bool = False

    @property
    def use_real_db(self) -> bool:
        return bool(self.database_url)

    @property
    def use_real_composio(self) -> bool:
        return bool(self.composio_api_key)

    @property
    def use_real_llm(self) -> bool:
        return bool(self.anthropic_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
