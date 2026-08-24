# GeniOS — Cost Analysis & LLM/DB Consumption Report

**Audience:** Product Manager
**Purpose:** Self-contained reference to understand where every dollar of cost comes from, how to model it, and how to price plans accordingly.
**Last verified against code:** 2026-04-29
**Repo audited:** `/home/harshtripathi/Desktop/genios/`

---

## TL;DR (30-second read)

GeniOS spends money in 3 places:

1. **LLM API calls** — Groq (cheap), Gemini (cheap), Anthropic (premium). 7 distinct call sites.
2. **Embeddings** — Gemini free tier today; trivial cost at scale.
3. **Database & infra** — Supabase Postgres + pgvector + Redis + worker VPS. Mostly fixed cost; ~$0.05–$0.10 marginal per user/month.

**All-in COGS per active user:**
- Hustler plan with default Groq routes: **~$0.50/month**
- Hustler with Anthropic Haiku route: **~$2.00/month**
- Startup plan (realtime + cascades + Slack/HubSpot): **~$7/month**

At $19 / $49 retail, gross margin is **86–97%** depending on route.

---

## 1. System Architecture — Where Cost Lives

```
┌─────────────────────────────────────────────────────────────┐
│  USER ACTIVITY (emails arrive, queries asked, syncs run)    │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        │                             │
        ▼                             ▼
┌──────────────────┐        ┌────────────────────┐
│  genios-brain    │        │ genios-email-agent │
│  (Celery workers)│        │  (CLI + dashboard) │
└────────┬─────────┘        └──────────┬─────────┘
         │                              │
         ▼                              ▼
   LLM CALLS (5 routes)            LLM CALLS (3 routes)
   + Embeddings                    + Embeddings
         │                              │
         ▼                              ▼
   Postgres + pgvector ◀──────▶ Supabase + pgvector
         │
         ▼
   Redis (Celery broker)
```

Two services, two databases, one shared cost model.

---

## 2. LLM Call Sites — The Complete Inventory

Every LLM API call in the codebase lives in one of these places. **If a feature isn't listed here, it doesn't cost anything.**

### 2.1 genios-brain (background reasoning service)

| # | Purpose | File path | Default model | Routable? | When it fires | Avg input tokens | Avg output tokens |
|---|---------|-----------|---------------|-----------|---------------|------------------|-------------------|
| B1 | `classify_email` — categorize incoming email | `genios-brain/app/event/classifier.py` | Groq llama-3.3-70b | Yes (env `LLM_ROUTE_CLASSIFY_EMAIL`) | Per email during Gmail sync | 250 | 50 |
| B2 | `reason_haiku` — produce recommendation/insight for an entity | `genios-brain/app/brain/reasoner.py` | Groq llama-3.3-70b (default) OR Anthropic Haiku 4.5 (when env-routed) | Yes | Per entity event, **debounced 5s** (coalesces bursts) | 625 | 200 |
| B3 | `reason_sonnet` — high-confidence cascade for greyband cases | `genios-brain/app/brain/cascade.py` | Anthropic Sonnet 4.6 | Partial | Only when B2 confidence < 0.7 AND `GENIOS_CASCADE_ENABLED=true` | 875 | 300 |
| B4 | `narrative` — story-form summary of recommendations | `genios-brain/app/brain/narrative.py` | **DISABLED** — programmatic fallback used | — | Off by default (`GENIOS_NARRATIVE_USE_LLM=false`) | 0 | 0 |
| B5 | `embed` — 768-dim vector for contact/interaction | `genios-brain/app/llm/client.py` | Gemini embedding-001 | No | Per email + per new contact | ~500 | — (embedding) |

**Routing config:** `genios-brain/app/llm/client.py` `_DEFAULT_ROUTES` dict. Override with env vars like `LLM_ROUTE_REASON_HAIKU=anthropic:claude-haiku-4-5-20251001`.

### 2.2 genios-email-agent (user-facing email assistant)

| # | Purpose | File path | Default model | When it fires | Avg input | Avg output |
|---|---------|-----------|---------------|---------------|-----------|------------|
| E1 | `call_llm` router — draft / compose / extract / summarize | `genios-email-agent/app/llm/router.py` | Gemini 2.5-flash → Ollama fallback | Per user command (CLI, dashboard) | 500 | 400 |
| E2 | `interpret_intent` — parse user CLI command | `genios-email-agent/app/llm/gemini.py` | Gemini 2.5-flash (hardcoded) | Per CLI command | 200 | 50 |
| E3 | `embed_text` — for memory/retrieval | `genios-email-agent/app/memory/embeddings.py` | Gemini embedding-001 | Per email + memory write | ~500 | — |

### 2.3 What is NOT costing money today

These exist in code but do not generate API spend:

- **`genios-reranker/`** service — dormant. `RERANKER_URL` env is empty by default; brain falls back to `head(top_k)`. Do not deploy.
- **`narrative.py`** — LLM mode off; uses deterministic template.
- **OpenAI / Voyage embeddings** — not in primary path.

---

## 3. Pricing Reference — Per 1M Tokens

| Model | Provider | Input $ | Output $ | Use case |
|-------|----------|---------|----------|----------|
| llama-3.3-70b | Groq | 0.59 | 0.79 | Cheap classification + reasoning |
| gemini-2.5-flash | Google | 0.30 | 2.50 | User-facing draft/compose |
| gemini-embedding-001 | Google | **0.00** (free tier ≤1500 RPM) / 0.025 paid | — | Vector embeddings |
| claude-haiku-4-5 | Anthropic | 1.00 | 5.00 | Premium reasoner upgrade |
| claude-sonnet-4-6 | Anthropic | 3.00 | 15.00 | Greyband cascade (rare) |

**Gemini free tier limits:** 1500 RPM, 15 RPD per project (check current quota). At >1000 active users with bursty backfills, plan to switch to paid embeddings — still trivial at $0.025/1M.

---

## 4. Per-Operation Cost Cheat Sheet

Use this to calculate any feature's cost directly. Formula:

```
cost_per_call = (input_tokens × input_price + output_tokens × output_price) / 1,000,000
```

| Operation | Default route | Cost per call |
|-----------|---------------|---------------|
| classify_email (Groq) | llama-3.3-70b | $0.000188 |
| reason_haiku (Groq) | llama-3.3-70b | $0.000527 |
| reason_haiku (Anthropic Haiku) | claude-haiku-4-5 | $0.001625 |
| reason_sonnet cascade | claude-sonnet-4-6 | $0.007125 |
| email-agent compose (Gemini) | gemini-2.5-flash | $0.001150 |
| Intent parse (Gemini) | gemini-2.5-flash | $0.000185 |
| Embedding (Gemini free) | embedding-001 | $0.000000 |
| Embedding (Gemini paid) | embedding-001 | $0.0000125 |

Multiply by call count → operation-level cost. That's it.

---

## 5. Per-User Daily Activity Profile

For a steady-state user processing **~33 emails/day** (1000/month):

| Operation | Calls/day | Reason |
|-----------|-----------|--------|
| classify_email | 33 | One per email |
| embed (email + new contact) | 40 | Email + occasional new contact |
| reason_haiku | 16 | 5-second debounce coalesces bursts → ~50% of email count |
| reason_sonnet cascade | ~1 | 5–10% of haiku calls hit greyband |
| proactive-scan (LLM) | 4 | Every 6h via Celery beat |
| morning-digest (LLM) | 1 | Once per day at user's local digest hour |
| email-agent compose | ~5 | User initiates draft/reply 5x/day |

Background tasks that **do not** cost money: score-writer (96/day, SQL only), auto-merge (48/day, SQL only), nightly precedent-writer + Hebbian (math only).

---

## 6. Plan Tier Definitions (from `app/plan_enforcer.py`)

| Field | Trial | Hustler | Startup |
|-------|-------|---------|---------|
| Period | 5 days | 30 days | 30 days |
| Daily call cap | 100 | 200 | 666 |
| Max contacts | 100 | 300 | 2,000 |
| Integrations | gmail | gmail, calendar, docs | gmail, calendar, slack, hubspot, docs |
| Sync method | manual | 6h cron | realtime webhook |
| LLM routing | Groq only (locked) | Anthropic routing allowed | Realtime + Sonnet cascade |
| Operations | read-only | manual_context, merge | + tagging, disclosure |
| Overage pricing | none | $0.40/1k calls | $0.50/1k calls |

---

## 7. Cost Per Plan — Steady State (after onboarding)

Assumes 1000 emails/month, all background tasks running.

### Trial — 5 days

| Component | Cost |
|-----------|------|
| All routes locked to Groq | $0.15 |
| DB | negligible |
| **Total trial period** | **$0.15–$0.20** |

### Hustler — Default Groq routes

| Component | Daily | Monthly |
|-----------|-------|---------|
| classify (Groq) | $0.0064 | $0.19 |
| reason_haiku (Groq) | $0.0084 | $0.25 |
| sonnet cascade | $0.007 | $0.21 |
| proactive + digest (Groq) | $0.005 | $0.15 |
| email-agent (Gemini) | $0.0058 | $0.17 |
| Embeddings | 0 | 0 |
| DB share | — | $0.10 |
| **Total** | **$0.033** | **~$0.97** |

### Hustler — Anthropic Haiku route

| Component | Daily | Monthly |
|-----------|-------|---------|
| classify (Groq) | $0.0064 | $0.19 |
| reason_haiku (Anthropic) | $0.026 | $0.78 |
| sonnet cascade | $0.007 | $0.21 |
| proactive + digest (Haiku) | $0.022 | $0.66 |
| email-agent (Gemini) | $0.0058 | $0.17 |
| DB | — | $0.10 |
| **Total** | **$0.067** | **~$2.11** |

### Startup — Realtime + Cascade + Slack/HubSpot

Higher event volume (~80/day from extra integrations).

| Component | Daily | Monthly |
|-----------|-------|---------|
| classify (Groq) | $0.016 | $0.48 |
| reason_haiku (Anthropic) | $0.10 | $3.00 |
| sonnet cascade (10%) | $0.042 | $1.26 |
| proactive + digest | $0.04 | $1.20 |
| email-agent (Gemini) | $0.017 | $0.51 |
| Embeddings (paid tier) | $0.005 | $0.15 |
| DB share | — | $0.15 |
| **Total** | **$0.22** | **~$6.75** |

---

## 8. New User Onboarding Burst

When a user signs up, the system back-fills 200–300 historical emails on Day 1, then settles into steady-state.

**Day 1 burst (250 emails):**

Debounce coalescing means reasoner fires per *contact* not per *email*. 250 emails → ~60 unique contacts → 60 reason calls.

| Phase | Hustler-Groq | Hustler-Anthropic | Startup |
|-------|--------------|-------------------|---------|
| Day 1 backfill | $0.11 | $0.19 | $0.34 |
| Day 2–30 (25 emails/day × 29) | $0.78 | $1.65 | $6.38 |
| email-agent + Gemini (monthly) | $0.17 | $0.17 | $0.51 |
| **Month 1 total LLM** | **$1.06** | **$2.01** | **$7.23** |
| DB (7–12 MB add) | $0.05 | $0.05 | $0.10 |
| **Month 1 all-in** | **$1.11** | **$2.06** | **$7.33** |

**Month 2+ steady:** ~$0.97 / $2.11 / $6.90.

**Onboarding adds $0.06–$0.60 one-time per user** — basically a rounding error.

---

## 9. Database & Infrastructure Cost

### 9.1 Storage per user per month

| Table | Row size | Volume / user / month | Storage |
|-------|----------|----------------------|---------|
| `interactions` (body + 768d embedding) | 6 KB | 1000 emails | 6 MB |
| `contacts` (profile + 768d embedding) | 5 KB | 100 new | 0.5 MB |
| `recommendations` | 1 KB | ~200 | 0.2 MB |
| `llm_usage` (audit log) | 0.3 KB | ~3000 | 1 MB |
| `precedent_situations` + Hebbian edges | 0.5 KB | ~500 | 0.25 MB |
| Indexes (pgvector ivfflat + btree) | — | ~40% overhead | 3 MB |
| **Total per user/month** | | | **~11 MB** |

### 9.2 Hosting cost ladder

| Users | Total DB | Hosting tier | Monthly cost |
|-------|----------|--------------|--------------|
| 1–40 | <500 MB | Supabase Free | $0 |
| 50–500 | <8 GB | Supabase Pro | $25 flat |
| 500–2000 | ~22 GB | Supabase Pro + storage | ~$50 |
| Redis (Upstash/Render) | — | pay-per-req | ~$10 flat |
| Worker VPS (Celery beat + workers) | — | 2 vCPU | ~$20 flat |

**Marginal DB cost per user/month: $0.05–$0.10.**

### 9.3 Per-org rate-limit guardrail

`llm_usage` table has indexes on `(org_id, called_at)`. The env var `GENIOS_LLM_DAILY_CAP_USD` enforces a daily $ cap per org — if exceeded, LLM calls are rejected. Set this conservatively per plan (e.g. $0.10 Trial, $0.50 Hustler, $1.50 Startup) to prevent runaway costs.

---

## 10. Sync Schedule — How Often Background Tasks Fire

From `genios-brain/app/celery_app.py`:

| Task | Schedule | LLM cost? |
|------|----------|-----------|
| brain-router | every 5s | yes (debounced reasoner) |
| score-writer | every 15m | no (SQL only) |
| auto-merge | every 30m | no |
| morning-digest | every 1h, fires at user's local digest hour | 1 LLM call/day/user |
| hourly-sync-check | every 1h | gates per-org `sync_interval_hours` (6/12/18/24 by plan) |
| proactive-scan | every 6h | 1 LLM call/scan/user |
| nightly-refresh | 2 AM | no |
| nightly-classify | 2 AM | yes (catch-up) |
| precedent-writer | nightly | no |
| hebbian-nightly | nightly | no |

**Key insight:** Sync interval is **plan-gated**. Trial users sync manually only; Hustler at 6h cron; Startup gets realtime webhooks. This is the single biggest cost lever between plans.

---

## 11. Cost Levers — Things You Can Change

Ranked by impact, biggest first:

1. **`reason_haiku` route choice** — Groq vs Anthropic Haiku is a **4.5× cost difference**. Default ships Groq. Switch via env, never code change.
2. **`GENIOS_CASCADE_ENABLED`** — Sonnet cascade is the most expensive call. Off by default; turn on only for Startup tier.
3. **`GENIOS_NARRATIVE_USE_LLM`** — Off by default. Programmatic fallback works; do not flip without proof of value.
4. **Sync interval (`sync_interval_hours`)** — Realtime webhook (Startup) generates ~3× more events than 6h cron (Hustler). Plan-gated already.
5. **Debounce window** — `reason_haiku` debounces 5s. For bulk imports, raise to 30s to coalesce more events.
6. **Daily cap (`GENIOS_LLM_DAILY_CAP_USD`)** — Hard cost ceiling per org. Set per plan.
7. **Embedding paid vs free tier** — Free works to ~500 users; paid is $0.025/1M (still trivial).
8. **Reranker** — Currently dormant. Do **not** deploy unless quality lift is proven.

---

## 12. Margin Analysis — Suggested Pricing

| Plan | Avg COGS | Suggested price | Gross margin |
|------|----------|-----------------|--------------|
| Trial | $0.20 (one-time) | Free (5 days) | — |
| Hustler — Groq route | $0.52 | $19/mo | 97% |
| Hustler — Anthropic route | $2.00 | $19/mo | 89% |
| Startup | $6.90 | $49/mo | 86% |

At 100 users (60% Hustler-Groq / 30% Hustler-Anthropic / 10% Startup):

```
Variable LLM + DB:   ~$197 / month
Fixed (Supabase + Redis + VPS):  $55 / month
─────────────────────────────────────
Total infra:        ~$252 / month
Average COGS/user:  ~$2.50 / month
```

---

## 13. Self-Service Cost Calculator

A PM can estimate any custom scenario by plugging into this formula:

```
monthly_cost_per_user =
    (emails_per_month × $0.000188)                    # classify
  + (emails_per_month × 0.5 × COST_REASON_HAIKU)      # reasoner (debounced)
  + (emails_per_month × 0.05 × $0.007125)             # sonnet cascade
  + (4 × 30 × COST_REASON_HAIKU)                      # proactive scan
  + (1 × 30 × COST_REASON_HAIKU)                      # morning digest
  + (5 × 30 × $0.001150)                              # email-agent compose
  + DB_SHARE                                          # ~$0.10
```

Where `COST_REASON_HAIKU` is **$0.000527** (Groq route) or **$0.001625** (Anthropic route).

For Startup, multiply email-driven items by ~1.6× (Slack/HubSpot adds events) and add Sonnet cascade for 10% of haiku calls.

---

## 14. Open Questions for PM

1. **Trial backfill cap** — Trial = 100 calls/day; backfill of 250 emails will hit the cap on Day 1. Decision needed: spread backfill over 3 days, OR cap historical import at 100 emails on Trial.
2. **Anthropic vs Groq default for Hustler** — 4× cost increase for Anthropic route. Quality testing should decide whether the upgrade is worth the upsell.
3. **Daily LLM $ cap per plan** — Need explicit values for `GENIOS_LLM_DAILY_CAP_USD` per tier to bound runaway costs.
4. **Overage handling UX** — Plan enforcer charges $0.40–$0.50/1k overage calls. Is this surfaced to the user before they hit it?
5. **Embedding migration plan** — Free Gemini tier will saturate around 500–1000 users. Confirm Gemini paid tier billing account is ready before that scale.
6. **Reranker decision** — Code exists, deployment dormant. Confirm "do not deploy" remains policy.

---

## 15. Source-of-Truth Files

If any number in this doc looks stale, re-verify against:

- `genios-brain/app/llm/client.py` — `_DEFAULT_ROUTES` + cost table
- `genios-brain/app/llm/cost.py` — pricing per model
- `genios-brain/app/celery_app.py` — schedule of background tasks
- `genios-brain/app/plan_enforcer.py` — plan tier definitions
- `genios-brain/app/brain/reasoner.py` — reason_haiku call site
- `genios-brain/app/brain/cascade.py` — sonnet cascade gate
- `genios-email-agent/app/llm/router.py` — email-agent routing
- Migrations `002`, `048` — pgvector dimension changes (768d)

---

*End of report.*
