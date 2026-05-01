# Phase Deviations from PHASED_BUILD_PLAN.md

Living record of: every delta from the plan, **why** it deltas, and **what still needs
to happen later** to close the gap.

When plan and this file disagree → **this file wins**. Update this file whenever a
new deviation is introduced, never silently diverge.

Last updated: 2026-04-18

---

## Global decisions (apply to every phase)

| Topic | Plan says | Reality | Why | Deferred? |
|---|---|---|---|---|
| Naming | `tenant_id` in schemas | `org_id` everywhere | Existing codebase uses `org_id` | No — permanent choice |
| Org table name | `organizations` | `orgs` | Existing table name | No |
| Git | one branch per phase | direct edits | `genios/` is not a git repo | Initialize later if needed |
| Razorpay | "already connected" | NOT configured | Not needed for Phase 1–3; billing route lazy-loads | Set up when billing goes live |
| Hosting | DO droplet + systemd | App Platform (managed containers) | User is on managed PaaS | Informs Phase 2+ design |

---

## Phase 1 — LLM Foundation + Pull Safety  ·  status: **IMPLEMENTED**

| # | Plan | What we did | Why | Deferred work |
|---|---|---|---|---|
| 1 | Anthropic for `reason_haiku / reason_sonnet / narrative` | Groq `llama-3.3-70b-versatile` for all | No Anthropic API key | **Phase 1.5 checklist** (below) |
| 2 | Add `anthropic==0.39.0` to requirements.txt | Not added; only `pip-audit==2.7.3` added | Don't install unused dep | Add on Phase 1.5 |
| 3 | Migration 069 index `(org_id, called_at::date)` | Index `(org_id, called_at DESC)` | `timestamptz::date` is not IMMUTABLE in Postgres | No — permanent fix |
| 4 | `delivery_attempts.recommendation_id` | `delivery_attempts.insight_id` | Matches existing `insights` table | Rename column in Phase 3 migration |
| 5 | Schema uses `tenant_id` | Uses `org_id` | See Global Decisions | No |
| 6 | Pull API 400ms hard deadline | Done as planned | — | — |
| 7 | Webhook retry via `delivery_attempts` | Done; beat 5min → 30s; `consecutive_failures` auto-disable removed | Plan-aligned | — |
| 8 | CI `pip-audit` + `npm audit` | Added to [.github/workflows/ci.yml](.github/workflows/ci.yml) | — | — |

---

## Phase 2 — Brain Core  ·  status: **IMPLEMENTED**

| # | Plan | What we did | Why | Deferred work |
|---|---|---|---|---|
| 1 | NATS JetStream as event bus (self-hosted, systemd) | **Redis Streams** on existing Upstash | App Platform can't run systemd; Upstash already paid for; Redis Streams has durability + consumer groups | Swap to NATS only if we hit >10M events/day — interface in `event_bus.py` allows drop-in replacement |
| 2 | `nats-py==2.9.0` package | Not added | Not using NATS | — |
| 3 | `NATS_URL` env var | Not added | Not using NATS | — |
| 4 | `genios-brain-router.service` (systemd) | Celery task `task_brain_router` on new queue `brain_router`, beat-triggered every 5s | Reuses existing Celery infra on App Platform | **Deploy-time:** add `,brain_router` to worker start command (see below) |
| 5 | Reasoner on Anthropic Haiku | Runs through `llm_client.call(purpose="reason_haiku")` → Groq | No Anthropic key | Flips automatically when Phase 1.5 happens |
| 6 | "6 existing + 3 new = 9 detectors" | `ALL_DETECTORS` = 48 functions (plan counted categories) | Clarification, not a deviation | — |
| 7 | No migrations | None added | Plan-aligned | — |
| 8 | `GENIOS_REASONER_ENABLED=false` default | Same | Plan-aligned | Flip per canary tenant after Phase 2 validation |

**Worker start command change (must happen at deploy):**
```
# Before
celery -A app.celery_app worker -Q high_priority,low_priority
# After
celery -A app.celery_app worker -Q high_priority,low_priority,brain_router
```

---

## Phase 3 — Learning Loop  ·  status: **IMPLEMENTED**

| # | Plan | What we did | Why | Deferred work |
|---|---|---|---|---|
| 1 | P3.4 Cascade Haiku→Sonnet enabled on canary | Built `cascade.py` infra; **`GENIOS_CASCADE_ENABLED=false`**; `should_escalate()` also blocks when `reason_sonnet` routes to groq | Groq has no Haiku/Sonnet split | Activates automatically on Phase 1.5 flip — no code change then |
| 2 | P3.5 Narrative via Anthropic Haiku | Uses `purpose="narrative"` → Groq; 150ms remaining-budget guard; 5-min Redis cache | Same as above | Flips on Phase 1.5 |
| 3 | P3.6 Fusion = weighted sum `0.35·bm25 + 0.30·vector + 0.20·context_score + 0.15·graph_affinity` | Kept **RRF** in [retrieval/fuse.py](genios-brain/app/retrieval/fuse.py); added graph walk as a 3rd input list via new `app/graph/neighbors.py` | RRF is score-scale independent; spec ambiguous on method; zero regression risk | Revisit only if T-04 recall regresses |
| 4 | Pack sizes `small → short`, `medium → medium`, `large → long` | Renamed; `small`/`large` kept as aliases | Plan-aligned | Drop aliases in Phase 6 cleanup (deferred item **F**) |
| 5 | SDK 1.0 with `feedback()` method | **No SDK change** | Plan puts SDK 1.0 in Phase 5 | SDKs updated in Phase 5 |
| 6 | `/v1/outcome` deprecation alias | Live with `Sunset: Wed, 31 Dec 2026 23:59:59 GMT`, `Deprecation: true`, `Link: </v1/feedback>; rel="successor-version"` headers | Plan-aligned | Remove after SDK 1.0 migration (deferred item **E**) |
| 7 | Migration 066 `recommendations` | Applied. Also added `delivery_attempts.recommendation_id` nullable column so both legacy `insights` and new `recommendations` flow through the same retry/DLQ machinery | Avoids breaking Phase 1 webhook path during migration | — |
| 8 | Router → recommendations | Router inserts row after gate approves; webhook dispatcher picks it up (parallel path to legacy `insights`) | — | — |
| 9 | Feedback idempotency | `Idempotency-Key` header → Redis `SET NX` 24h TTL | Plan-aligned | — |
| 10 | `feedback.recorded` event | Published on event bus after `/v1/feedback` accepts | Phase 4 calibration consumer reads it | — |

---

## Phase 4 — Correctness (observability carved out)  ·  status: **IMPLEMENTED**

**Scope trim:** Phase 4 split into quality + observability. Only quality items get built now; observability deferred (doesn't affect what the brain decides).

| # | Plan | What we'll do | Why | Deferred work |
|---|---|---|---|---|
| 1 | P4.7 OTel + Prometheus + structlog + Grafana Cloud | **DEFER entirely** | Pure monitoring — zero impact on brain quality. Existing Sentry + PostHog already catch exceptions + analytics. Revisit when scale demands. | Deferred item **R** |
| 2 | P4.1 unified `score_composite` via GENERATED column | Add new `score_composite` GENERATED column; leave `context_score` populated in parallel for 14 days | No-risk additive | Drop `context_score` in Phase 6 |
| 3 | P4.6 `fact_type` CHECK on 13 values | Step-by-step: map via `fact_type_mapping` table, UPDATE batch, verify 0 violations, then ADD CONSTRAINT | Existing `fact_type` values may not match 13-type list; safer flow | — |
| 4 | P4.10 Calibration enabled per-tenant | Build; flag `GENIOS_CALIBRATION_ENABLED=false`; activates only when tenant has ≥ 50 labeled outcomes | Plan-aligned | Flip per tenant as outcomes accumulate |
| 5 | P4.11 GDPR endpoint `POST /v1/admin/delete` | Build + require admin API key; support `dry_run=true` default | Avoid accidental mass delete | — |
| 6 | HashiCorp Vault | **Skip** | Only needed for SOC 2 — deferred item **Q** | — |
| 7 | P4.8 20-test harness | Build 6 Sprint-1 tests only (plan-aligned); skip remaining 14 | 14 remaining are Sprint-2+ scope | Future |

---

## Phase 5 — Production Polish  ·  status: **IMPLEMENTED (trimmed)**

Trimmed scope: SDK features, SSE stream, CI guards, runbooks, backup drill doc.
Alerts / status page / SDK publish deferred (see deferred items S, T, U).

| # | Plan | What we did | Why | Deferred work |
|---|---|---|---|---|
| 1 | P5.1 — 8 runbooks in `ops/runbooks/` | Wrote all 8 tool-agnostic | Plan referenced Grafana dashboards; observability deferred (item R) so we wrote generic procedures | Add tool-specific links once observability lands |
| 2 | P5.2 — 20 alerts via PagerDuty / Grafana OnCall | **Deferred** | Nothing to fire alerts into until item R unblocks | Deferred item **S** |
| 3 | P5.3 — Additive-only migration rules | Wrote `CONTRIBUTING.md` + `.github/workflows/migration_safety.yml` | Plan-aligned | — |
| 4 | P5.4 — Backup restore drill | Wrote `ops/backup_drill.md` procedure | Plan quarterly schedule — document first, schedule when in prod | Schedule first drill post-launch |
| 5 | P5.5 — Python SDK 1.0 | Built features (retries / idempotency / webhook verify / async SSE); **did NOT publish** | No PyPI token; release when first real consumer exists | Deferred item **T** |
| 6 | P5.6 — TS SDK 1.0 | Same features in TS; did NOT publish | No npm token | Same item **T** |
| 7 | P5.7 — SSE stream endpoint | Built `/v1/stream/recommendations` | Uses existing Redis Streams bus | — |
| 8 | P5.8 — Status page | **Deferred** | Needs subdomain + external account; pre-launch polish | Deferred item **U** |

---

## Phase 6 — Production Validation  ·  status: **IMPLEMENTED (tooling only)**

Phase 6 is mostly procurement + calendar + people, not code. We built all
tooling that *can* be built now; vendor engagements + beta recruitment are
tracked as deferred items V/W/X.

| # | Plan | What we did | Why | Deferred work |
|---|---|---|---|---|
| 1 | P6.1 — load test 500 req/s × 15 min | Wrote `ops/load_tests/` k6 scripts for Pull/Ingest/Webhook scenarios | Plan-aligned; runnable when we have a staging endpoint | Run once staging is up |
| 2 | P6.2 — pen test by reputable vendor | Wrote `ops/audits/pen_test_scope.md` (scope-of-work); **did NOT engage vendor** | $3–8K budget decision | Deferred item **V** |
| 3 | P6.3 — legal sign-off on ToS / Privacy / DPA | Drafted starter templates in `ops/legal/`; **did NOT engage counsel** | $2–5K budget; counsel redlines our draft | Deferred item **W** |
| 4 | P6.4 — 3–5 beta tenants, 30+ days, AAR ≥ 50% | Built AAR metric + `GET /v1/admin/aar` + CSV export; **recruitment is manual** | Code ready for first canary | Deferred item **X** |
| 5 | P6.5 — Vault migration (SOC 2) | Skip | Deferred item **Q** | — |
| 6 | P6.6 — pre-launch freeze + hourly launch checklist | Wrote `ops/launch_checklist.md` | Plan-aligned | Execute at actual launch |

---

## Deferred Work Tracker (single source of truth)

Every item we punted. Revisit at the noted trigger.

| # | Item | Trigger to act | Effort |
|---|---|---|---|
| A | Switch LLM routes to Anthropic (`reason_haiku`, `reason_sonnet`, `narrative`) | Anthropic API key in hand | 5 min — see Phase 1.5 checklist |
| B | Add `anthropic==0.39.0` to `requirements.txt` | Same trigger as A | part of A |
| C | Enable cascade Haiku→Sonnet (`GENIOS_CASCADE_ENABLED=true`) | Phase 3 complete + 2 weeks stable reasoner on canary | 1 env flip |
| D | Enable reasoner on canary tenant (`GENIOS_REASONER_ENABLED=true`) | Phase 2 validation — 100 candidates, ≥ 0.80 manual precision | 1 env flip per tenant |
| E | Flip `/v1/outcome` → remove alias | Phase 6+, after SDK 1.0 adoption ≥ 90% | 1 PR; remove route |
| F | Drop `small/medium/large` pack name aliases | 90d after Phase 3 ships | 1 PR |
| G | Rename `delivery_attempts.insight_id` → `recommendation_id` | Phase 3 migration 066 | Combine with 066 SQL |
| H | Add `brain_router` to worker `-Q` list | First Phase 2 deploy | 1 App Platform config edit |
| I | Consider NATS if event volume > 10M/day | Metrics show Redis Streams lag or MAXLEN trimming active events | Swap `event_bus.py` implementation |
| J | Pay Razorpay + wire billing | First paying customer / public launch | Billing code exists; add env vars |
| K | Initialize git repo + branch strategy | Any time | `git init` + baseline commit |
| L | Grafana Cloud account | Start of Phase 4 | Free tier sign-up |
| M | Grafana OnCall / PagerDuty account | Start of Phase 5 | Free tier sign-up |
| N | Better Stack status page | Start of Phase 5 | Free tier sign-up |
| O | Pen test vendor engagement | Start of Phase 6 | Budget + contract |
| P | Legal review engagement | Start of Phase 6 | Budget + counsel |
| Q | HashiCorp Vault migration | Only if SOC 2 Type I observation begins | Significant — re-encrypt all secrets |
| R | Observability stack (OTel + Prometheus + structlog + Grafana Cloud) | First prod incident un-debuggable from Sentry/logs alone, OR >25 tenants | Moderate — code wiring + account setup |
| S | 20 alert definitions (Grafana AlertManager rules) | Item R lands | Alert YAML exists in plan spec §8.2; plug in once R is live |
| T | Publish SDK 1.0rc to PyPI + npm | First external consumer wants install | Create PyPI + npm accounts, add tokens to GitHub Actions, `twine upload` + `npm publish` |
| U | Status page at status.genios.ai | Public launch / beta with external customers | Better Stack or Instatus free tier; point subdomain |
| V | Engage pen test vendor | Pre-GA security sign-off needed | SOW exists at `ops/audits/pen_test_scope.md`; vendor $3–8K |
| W | Engage legal counsel | First paid customer OR SOC 2 start | Draft templates exist at `ops/legal/`; counsel redlines, $2–5K |
| X | Recruit 3–5 beta design-partner tenants | Ready for canary traffic | Code ready; outreach + contracts are yours |

---

## Celery vs Redis Streams — division of labor

| Work | Tool |
|---|---|
| Scheduled jobs (Gmail sync, nightly refresh, webhook delivery, proactive scan) | **Celery beat + worker** (unchanged) |
| Reactive events (`fact.updated` from writers → brain router) | **Redis Streams** (Phase 2) |

Both coexist. Celery not removed, not useless.

---

## Upstash Redis — key map

| Key pattern | Purpose | TTL |
|---|---|---|
| `genios:events:fact` (stream) | event bus | MAXLEN ~ 100000 |
| `brain:debounce:{org}:{entity}` | router batching | 30s |
| `dedup:{org}:{type}:{subject}` | gate 24h dedup | 24h |
| `push_budget:{org}:{date}` | gate daily budget | 24h |
| `warm_lock:{cache_key}` | background cache-warm dedup (see Post-QA deviations) | 120s |
| Celery broker (DB 1) | task queue | — |
| App cache (DB 0) | context cache | varies |

One `REDIS_URL`. No Upstash dashboard changes required.

---

## Post-QA deviations (2026-04-19) — `/v1/context` hardening

Introduced during full-API QA pass against `tripathihk2014@gmail.com` org. All
changes land in [app/api/routes/context.py](genios-brain/app/api/routes/context.py)
unless noted.

| # | Plan | What we did | Why | Deferred work |
|---|---|---|---|---|
| 1 | Phase 1 row 6: "Pull API 400ms hard deadline" interpreted as *drop work on deadline* | Deadline still hard for the caller, but on timeout we spawn a **background cache-warm** (fresh `SessionLocal`, full `build_context_bundle`, `redis.setex` on success) | Old code orphaned the future → cache never warmed → every cold pull re-degraded forever | Remove when cold build <400ms |
| 2 | Background warm has no dedup | Per-key `SETNX warm_lock:{cache_key} ex=120` before spawn; losers log "skipping duplicate" | N concurrent cold pulls would otherwise spawn N identical builds and hammer DB/LLM | — |
| 3 | `/v1/context` degraded returned `confidence_score`; success returned `confidence` | Degraded now emits **both** (`confidence` + `confidence_score` as deprecated alias) | SDK consumers couldn't write one parser across cache states | Drop `confidence_score` alias after one release window — track as deferred item **Y** |
| 4 | Degraded `entity` was a string; success was a dict | Degraded now emits `entity: {email, name}` dict to match success | Same one-parser goal | — |
| 5 | Degraded bundle also lacked `confidence_level`, `situation_type`, `sources_used` | Now emits those as `unknown / null / []` so schema shape matches success | Unified contract | — |
| 6 | `:config::jsonb` inline cast in `segments.py` (2 spots) and `webhooks.py` (1 spot) | Rewrote as `CAST(:x AS jsonb)` | SQLAlchemy 2.0 + psycopg2 leaves `:name::type` unsubstituted → syntax error at runtime. `POST /v1/segment` was 100% broken; Gmail push webhook would've 500'd in prod | — |
| 7 | `/v1/context/entity/{entity_id}` 500 on non-UUID input | Validate UUID before DB query → 404 on invalid | Passing an email/garbage hit psycopg2 UUID cast error → leaky 500 | — |
| 8 | `/v1/agents/session/start` and `/end` took `org_id` in body with **no auth** | Both now require `verify_api_key`; `org_id` derived from key; body schema trimmed accordingly | Cross-tenant session manipulation via any valid API key | — |
| 9 | Stale pytest expectations (`confidence` field, `situation_type` always present, unknown-entity → 404) | Rewrote to match real contract: accepts unified-degraded shape; skips deep-shape checks when `meta.degraded=true` | Tests were written against an older bundle shape | — |

Deferred item **Y**: drop `confidence_score` alias from degraded bundle once
all external consumers are on `confidence`. Trigger: SDK 1.0 adoption ≥ 90%
(aligns with deferred item **E** timing).

**Invariant preserved:** the caller-facing 400ms deadline is still hard. The
warm thread runs strictly out-of-band on its own DB session and is
rate-limited to one in-flight build per cache key.

---

## Architecture shift (2026-04-20) — `/v1/context` moved from on-demand to pre-computed

**Context for the shift:** GeniOS is a context-intelligence API. External
agents call `/v1/context` on their hot path to decide "who is this, what do I
say, what should I suggest." Both of the prior failure modes — (a) a 2s wait
for an on-demand bundle build, (b) a fast-but-empty "degraded" pack — break
that product. Agents need real intelligence in <400ms every time.

### New contract

`/v1/context` pull path, in order:

1. **Layer 1 — `precomputed_bundles` (Postgres, 24h TTL, situation-independent)**
   Indexed lookup by `(org_id, contact.name|email)`. Hit rate is the target
   for steady-state traffic.
2. **Layer 2 — Redis cache (situation-keyed, 60s TTL)**
   Catches situation-specific repeats (same agent asking about the same
   person with the same prompt within a minute).
3. **Layer 3 — Minimal-real bundle** (new, replaces degraded-empty)
   One indexed query: contact row + last 3 interactions. Returns real data
   (name, stage, sentiment, last contact, recent summaries) in a single
   round-trip, matching the success-bundle shape so agents need one parser.
   Target <150ms for the query itself.
4. **Unknown entity → 404** (new; previously returned an empty 200).
   A 404 is honest — an agent asking about someone outside the org's graph
   should not get back confidence 0 masquerading as a real answer.

### Freshness model

- **Event-driven refresh** — the Phase 2 brain router (Redis Streams → Celery
  every 5s) already sees every (org_id, entity_id) whose debounce window has
  closed. It now also enqueues `task_refresh_bundle(org_id, contact_id)` for
  each one, which rebuilds the full bundle and writes `precomputed_bundles`.
- **Nightly full-refresh** already exists (`_precompute_bundles` in
  `nightly_refresh.py`) as the floor.
- **Per-refresh guard** — `bundle_refresh_guard:{org}:{contact}` SETNX 10s,
  so a contact that gets 50 rapid events produces at most one rebuild per 10s.
- **Staleness SLA**: p95 <30s, p99 <2min between event and fresh bundle.

### What the new code is

| File | Role |
|---|---|
| `app/tasks/refresh_bundle.py` | Per-contact pre-compute. Idempotent + storm-guarded. |
| `app/context/minimal_bundle.py` | Single-query real fallback for cold path. |
| `app/celery_app.py::task_refresh_bundle` | Celery wrapper, `high_priority` queue. |
| `app/brain/router.py` flush loop | Enqueues `task_refresh_bundle` per debounced entity. |
| `app/api/routes/context.py` Layer 3 | Replaced degraded-empty with minimal + enqueue. |

### What was removed

- Degraded-empty fallback (`confidence: 0`, empty `facts`, empty `context_for_agent`).
- Background cache-warm from the previous round — superseded by the refresh
  task pattern (same idea, but via Celery + Postgres precomputed table
  instead of an orphan thread + Redis-only cache).
- Deferred item **Y** (drop `confidence_score` alias) still open — the
  minimal bundle and former degraded path both dual-emit during transition.

### Layer 1 lookup bug caught during this work

`precomputed_bundles` JOIN matched only on `c.name`, so email-based pulls
(which is the dominant agent call pattern) fell through to Layer 3 every
time even when a precomputed row existed. Fixed to match on `name OR email`.
Without this fix, precomputation would have been essentially invisible to
callers.

### Deploy-time note

The existing Phase 2 worker start-command already includes `high_priority`
and `brain_router` queues, so `task_refresh_bundle` runs on existing workers
with zero config change. No new infra.

### Verified

- Known contact (precomputed row present) → `cache_source: precomputed`,
  `confidence: 0.528`, full rich paragraph, `cache_hit: True`.
- Cold contact (no precomputed row yet) → `cache_source: minimal`,
  real name + stage + last-contact summary, refresh enqueued.
- Unknown contact → 404 with `ENTITY_NOT_FOUND`.

---

## Phase 1.5 checklist (when Anthropic key arrives)

1. `.env`: replace `ANTHROPIC_API_KEY` dummy → real key
2. `.env`: set `GENIOS_ANTHROPIC_ENABLED=true`
3. `pip install anthropic==0.39.0` (and add to `requirements.txt`)
4. [app/llm/client.py](genios-brain/app/llm/client.py) `ROUTES`: flip these 3 entries
   ```
   "reason_haiku":  ("anthropic", "claude-haiku-4-5-20251001")
   "reason_sonnet": ("anthropic", "claude-sonnet-4-6")
   "narrative":     ("anthropic", "claude-haiku-4-5-20251001")
   ```
5. Create `scripts/test_anthropic_connection.py` (mirror of `test_groq_connection.py`) and run it.

Closes deferred items **A, B, C** at once.

---

## Ritual before starting any phase

1. Read this file.
2. Re-read [PHASED_BUILD_PLAN.md](PHASED_BUILD_PLAN.md) section for the next phase.
3. If plan and this file disagree: **this file wins**.
4. If a new deviation is introduced, update this file **before** writing code.
5. Ask the human before inventing a new path.
