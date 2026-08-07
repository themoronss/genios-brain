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
    # Delivery has minute-scale retry/deferral clocks and therefore cannot inherit the heavy
    # ingestion cadence. The same scheduler master switch controls both daemon loops; this shorter
    # interval is safe across replicas because Layer 5.2 claims rows with SKIP LOCKED + fencing.
    delivery_interval_seconds: float = 60.0      # due delivery sweep cadence (0 = off)
    delivery_initial_delay_seconds: int = 10     # let migrations/startup settle first
    public_app_url: str = ""                     # HTTPS UI origin for actionable delivery links

    # tenant / options
    org_id: str = "org_trial"
    mask_phone: bool = False
    # optional S2 relevance classifier in L1 (defense-in-depth). Deterministic until an
    # LLM classifier is wired. Default off — decide on real-data evidence.
    enable_l1_relevance: bool = False
    # OCR (Tesseract) fallback for scanned/image docs. Native text always works; OCR
    # needs the tesseract binary, so default off — turn on where the binary is present.
    enable_ocr: bool = False

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
