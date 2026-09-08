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

    # Platform-wide daily LLM spend ceiling in USD. The per-org caps bound each tenant; this bounds
    # their sum, which is the only guard against many accounts abusing us at once. 0 = disabled.
    daily_llm_usd_cap: float = 25.0
    # Sub-ceiling on the FRONTIER tier of L1 extraction, in USD/day. T3 is five times T1 and is
    # where a runaway becomes expensive fastest, so it can be capped separately: the day's
    # frontier budget runs out while ordinary extraction continues at T2. 0 = no separate
    # sub-ceiling (the T3 budget equals the daily one), which is the honest default because
    # `llm_costs` records no tier and a sub-ledger opened at a guessed balance would demote
    # frontier work for a reason nobody could check.
    daily_t3_llm_usd_cap: float = 0.0
    # Layer 4.5's NARRATIVE spend, per org per day, in USD. Doc 11 §2 sizes a pilot org at about
    # $0.58/day of bundle generation; this ceiling is a little over three times that, so an
    # ordinary day never touches it and a runaway is stopped inside one day instead of at the end
    # of a month. On breach the narrative degrades to the labelled deterministic template and
    # DECISIONS ARE UNAFFECTED — narration runs after publication, so there is nothing for a
    # spend ceiling here to block. 0 = no L4 narrative ceiling, the same meaning
    # `daily_llm_usd_cap` gives zero.
    l4_bundle_daily_usd_cap: float = 2.0
    # The per-DECISION ceiling, in USD. Doc 11 §5's acceptance row is "<= $0.02 per published
    # decision"; this is that row as a control rather than a report, with headroom for a long
    # situation. A single consult estimated above it is refused before it runs.
    l4_bundle_max_usd_per_decision: float = 0.05
    # OUR OWN domains — the product's transactional mail, not anybody's counterparty.
    #
    # A customer's inbox contains our onboarding, invite and billing mail. Without this the
    # engine models the vendor as a business relationship inside the customer's own graph: the
    # design partner's feed carried "Book invite@thegenios.com's demo now" from a message whose
    # entire body was "Dear Rohit, The life is going to be changed for forever now.", plus two
    # "reply to them" cards on the same address. The tenant's self-filter cannot catch this —
    # we are genuinely not the tenant — so it needs its own boundary.
    #
    # Config rather than a constant, because a self-hosted or white-labelled deployment sends
    # from a different domain, and a hardcoded string would silently stop protecting it.
    platform_domains: str = "thegenios.com"
    # Founder-facing ops alerts (sync totally broken, platform LLM cap hit) — a Slack incoming
    # webhook URL pointed at the founder's OWN workspace. Empty = alerts just log, no push.
    ops_alert_webhook: str = ""
    composio_webhook_secret: str = ""            # HMAC-SHA256 secret for inbound Composio webhooks
    cors_origins: str = "*"                       # comma-separated dashboard origins ('*' = dev)
    # Public base URL of the client dashboard, e.g. https://brain.thegenios.com. Used ONLY to
    # build the "Open the card →" deep link on outbound proactive messages. Empty = no link,
    # which is why every message the distribution sweep has ever built had none: the sweep's
    # `base_url` defaulted to "" and its one caller never passed anything, so `channels/slack.py`
    # dropped the link line on all three production payloads. Kept empty by default because a
    # guessed hostname produces a broken link, which is worse than no link.
    dashboard_url: str = ""

    # LLM (L2 extraction) — Anthropic. The single combined relevance+extraction call.
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5-20251001"

    # automatic data sync (in-process scheduler, NO Celery/Upstash). On startup the engine runs a
    # cross-org sync sweep every `sync_interval_hours` (L1 pull → L2/L3/L5), so connected tools stay
    # fresh without a button click. Set scheduler_enabled=false (or interval<=0) to disable — e.g. if
    # an external cron hits /ingest/all instead, or to avoid double-runs on a multi-instance deploy.
    scheduler_enabled: bool = True
    sync_interval_hours: float = 6.0             # how often the sweep TICKS (0 = off), and the
                                                 # fallback cadence for a source nobody has tuned
    # Per-source poll cadences, overlaid on the shipped table (L1.2.6-U1). One global interval
    # polled a mailbox and a quarterly-edited Notion page at the same rate — wrong in both
    # directions at once — so cadence is a property of the SOURCE and is configuration rather
    # than a constant. e.g. "gmail=5m,notion=1d,default=2h". Empty = the shipped table.
    sync_cadences: str = ""
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
    # Per-tenant OCR rollout (L1.3.4-U2 — "enable per-tenant, not globally"). Comma-separated
    # org ids. The allowlist turns OCR ON for an org while the fleet default stays off; the
    # denylist turns it OFF for an org while the fleet default is on, and wins over both.
    # Env-only rather than a settings column because OCR is a cost/latency property of a
    # deployment, and turning it on for one design partner must not need a schema change.
    ocr_enabled_orgs: str = ""
    ocr_disabled_orgs: str = ""
    # Layer 3 Domain Expertise compiler — the AUTHORITY half of its cutover: when on, the L2 -> L3
    # pass publishes `expertise_packages`, requires admission, reasons in LIVE mode and emits
    # signals delivery can build cards from. That is Layer 3's own decision and Layer 3's own
    # wave: the L3 plan replaces this flag with `l3_activation(org_id, domain)` and says of it
    # "use_domain_compiler is being retired, not extended". It is left exactly as it was.
    #
    # WHAT IT IS NOT, since it was read as both for months: it does NOT decide which TENANTS' Layer
    # 3 reads what Layer 1 published. That question is `l1_seam_enabled` below — a row in
    # `l1_semantic_activation`, per tenant — because the L1 -> L2 seam is Layer 1's activation
    # decision and a global boolean answering it has exactly two states, both wrong (off: no tenant
    # ever reads `qualified_signals`; on: every tenant's Layer 3 changes on one deploy).
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


def l1_seam_enabled(engine, org_id: str) -> bool:
    """Does THIS tenant's Layer 3 read what Layer 1 published — the L1 -> L2 seam, per tenant.

    The seam's only production reader is `context/situation_bso.gather_l1_signals`, called from
    the L2 -> L3 pass. That pass used to be entered only behind `use_domain_compiler`, a global
    boolean set in no environment — so Layer 1 scored, qualified and stored every signal and
    nothing on any live path ever read one. The build order's rule is the fix and it is not a
    style preference: *"NO GLOBAL BOOLEAN FLAGS. Activation is a table."*

    The table already exists and already means this: `l1_semantic_activation` is the row that says
    a tenant's Layer 1 v2 lane is live. A tenant whose Layer 1 publishes qualified signals that its
    own Layer 2 then ignores is precisely the dark state being fixed, so the seam follows the same
    row rather than growing a second switch beside it (`test_there_is_no_second_activation_table`).

    This function does not consult `use_domain_compiler` and must not learn to: the moment a
    global boolean can answer "does this tenant read Layer 1", one deploy moves every tenant, which
    is the failure being removed. The flag keeps its own separate job at the pass's entry — whether
    the compiled brain's decisions carry AUTHORITY (published packages, admission, LIVE execution,
    emitted signals) — and a deployment that has set it behaves exactly as it did before. Retiring
    it belongs to Layer 3's wave and Layer 3's own `l3_activation(org_id, domain)` table.

    Fail closed, on `platform/activation`'s own contract: no engine, an unreadable table, a query
    that errors — all of them are OFF, and OFF is the path the tenant is already on.
    """
    from genios_engine.platform.activation import is_semantic_activated
    return is_semantic_activated(engine, org_id)
