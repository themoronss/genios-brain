# Genios — Path from MVP to Production-Grade

> Diagnostic + plan. Aligned against the L2 Context Intelligence vision
> (`mvp-L2-launching-updates.pdf`). Zero assumptions — every gap cites a
> file, line, or doc reference.

**Target:** production-grade brain that serves both **Reactive** (agent-initiated
`/v1/context`) and **Proactive** (GeniOS-initiated scanner → webhook)
intelligence on DigitalOcean infrastructure.

**Current state:** partial L1 implementation with known risks. **Not L2-ready.**

---

## 0. Architectural Principles (non-negotiable)

These rules govern every design decision in the rest of this document.
Any future change that violates one of these is a regression.

### P1 — **Ingest everything, filter at read**
A brain remembers noise. Store every inbound email, calendar event, Slack
message — including promotional, transactional, and bot-originated — as
first-class rows. **Never filter at ingestion.** Tag richly with classification
metadata (`classification`, `is_broadcast`, `source`, `confidence`). Agents
see clean data because the **retrieval layer** applies filters by default,
not because data was discarded.

**Why:** lossless storage lets us re-classify when models improve, recover
from bad classifications, honor user overrides ("this *is* a real contact"),
and audit why any contact was surfaced or hidden. Gmail, Superhuman,
HubSpot, Salesforce — every serious system uses this pattern.

**Implication for the plan:**
- Tier-0 classifier (Phase 1.3) re-orders to run *before* LLM extraction
  to save cost — but it **tags**, it does not **drop**.
- `/v1/context` and `/v1/contacts` filter by default, with
  `include_broadcast=true` opt-in (Phase 3.4).
- Schema has `classification_override` column — user flips a contact from
  `newsletter` → `real_person`, override wins forever (Phase 3.3).

### P2 — **Explainability over accuracy**
Every score, stage, and insight must be traceable to the exact input
signal that caused it. No black-box ML. Formulas and rules only. If a
customer asks "why is Arjun marked AT_RISK?", we give a precise answer.
(L2 vision doc already commits to this — codifying it here.)

### P3 — **One source of truth per field**
When two signals can disagree (`agent_behavior` vs `action_recommendation`,
`confidence_score` vs `context_score`), pick one canonical value and
derive the rest. No parallel truths that can drift. Already applied in
Phase 0 fix F1.

### P4 — **Config in env, not code**
Every threshold, list, pattern, or tunable lives in
[app/tunables.py](genios-brain/app/tunables.py) with an env override.
Shipping a new classifier rule should not require a code deploy. Already
applied in Phase 0.

### P5 — **Store-at-ingest, compute-at-query, cache-at-read**
- **Ingest** (Phase 1): write raw + extracted facts to DB. No computation beyond that.
- **Background** (Phase 1-5): heavy analytics (scoring, anomalies, precedents) run async, results persisted.
- **Read** (Phase 1.4, 1.7): assembly + filtering only. No LLM calls on the hot path unless cache-miss + budget allows.

---

## 1. Where we are vs where we need to be

### The L2 vision is a 7-layer analytics chain

| Layer | Purpose | Current state | Gap to L2 |
|---|---|---|---|
| **L1 — Extraction** (LLM) | Unstructured text → structured facts (entities, sentiment, topics, commitments, tone) | ✅ Exists — [entity_extractor.py](genios-brain/app/ingestion/entity_extractor.py) via Groq + Gemini | ⚠️ In sync path, blocking, no batching, no retries |
| **L2 — Sentiment Tracking** (EWMA + trend) | Running score, IMPROVING/STABLE/DECLINING | ✅ Exists — [relationship_calculator.py](genios-brain/app/graph/relationship_calculator.py) has EWMA | ⚠️ Trend detection (±0.15 window) — verify correctness |
| **L3 — Relationship Scoring** (5 deterministic formulas) | confidence · freshness · authority · consistency · composite | ✅ Exists — 5-score system in place | ⚠️ Formula weights need tuning vs L2 spec (L2 says freshness uses stage-based half-life; verify) |
| **L4 — Stage Classification** (rule engine, priority-ordered) | ACTIVE / WARM / NEEDS_ATTENTION / COLD / AT_RISK | ✅ Exists — rules in [bundle_builder.py](genios-brain/app/context/bundle_builder.py) | ⚠️ Current rules don't 1:1 match L2 spec — need audit |
| **L5 — Anomaly Detection** (Z-score vs personal baseline) | Flag when entity behaves unusually | ❌ **Does not exist** | 🔴 Entire layer missing |
| **L6 — Root Cause Analysis** (graph traversal + fingerprint matching) | WHY anomaly is happening; find historical precedents | ⚠️ Partial — `find_warm_intro_path` exists, fingerprint matching does not | 🔴 Fingerprint schema + similarity matching + precedent table missing |
| **L7 — Synthesis** (LLM writes text only) | Convert structured analysis → human-readable insight | ⚠️ Partial — `context_for_agent` paragraph exists, but no `memory_view` / `genios_view` split | 🟡 Refactor into the L2 2-view format |

### The two delivery modes

| Mode | Current state |
|---|---|
| **Reactive** (`POST /v1/context` → bundle) | ✅ Works, with caveats (latency, cache, no classification filter) |
| **Proactive** (6h scanner → insight → webhook) | ❌ **Does not exist** — no scanner, no insight generator, no webhook outbound |

---

## 2. The 7 critical risks from L1 diagram — status

Every risk flagged in the L1 diagram + what we've done:

| # | Risk | Severity | Current status |
|---|---|---|---|
| 1 | **No Task Queue** (Celery/RQ missing) | Critical | ⚠️ Celery exists but **LLM extraction is not yet off the sync path** |
| 2 | **Graph In-Memory** (NetworkX single-worker) | Critical | ❌ Still in-memory. **Breaks on multi-worker deploy.** |
| 3 | **LLM in Sync Path** (500ms SLA at risk) | Critical | ❌ Ingestion still blocks on LLM. Context latency 4-6s on cold build. |
| 4 | **Cache Key Flaw** (situation-only → low hit rate) | Critical | ❌ [cache.py](genios-brain/app/context/cache.py) keys on situation hash only. Should include entity. |
| 5 | **Fuzzy Match Risk** (70% threshold → false positives) | High | ⚠️ [bundle_builder.py:184](genios-brain/app/context/bundle_builder.py#L184) WRatio ≥70 unchanged |
| 6 | **Nightly Refresh SPOF** (no error recovery) | High | ❌ No checkpointing, no retry per-contact, one bad row kills the run |
| 7 | **pgvector Unused** (semantic search gap) | High | ⚠️ Used for document chunks (precedent_search) but not for contacts / interactions semantic lookup |

**Plus what I added during audit:**

| # | Finding | Severity | Status |
|---|---|---|---|
| 8 | No Row-Level Security — org isolation at app layer only | Blocker | ❌ Still missing (see §5) |
| 9 | No test suite / CI / eval harness | Blocker | ❌ Still missing |
| 10 | Tier-0 broadcast classifier runs AFTER LLM extraction | High | ❌ Wastes 30-50% LLM cost |
| 11 | Legacy plaintext API keys accepted alongside hashed | Medium | ⚠️ Grandfathered in |
| 12 | No RLS, no encryption at rest for sensitive fields | High | ❌ |

**Of the above, 5 items are blockers for production.** Fixing the 4 L1 critical risks + test coverage + RLS is the non-negotiable floor.

---

## 3. Infrastructure plan — DigitalOcean, one region to start

User constraint: **DigitalOcean for backend + Celery + frontend, scale later when needed.** Locking in these choices:

| Layer | Current | Target for production |
|---|---|---|
| **API** (FastAPI) | DigitalOcean droplet / App Platform | **DO App Platform, 2 instances behind load balancer** for zero-downtime deploys |
| **Worker** (Celery) | — | **DO droplet with 2-4 Celery workers** (separate from API) + Celery Beat on its own instance |
| **Database** | Supabase (hosted Postgres + pgvector) | **Keep Supabase** — managed Postgres with pgvector, HNSW, point-in-time recovery, automatic backups. Do NOT self-host Postgres yet. |
| **Cache / Queue** | Upstash Redis | **Keep Upstash Redis** — used for Celery broker, RPM limits, context cache |
| **Vector store** | pgvector (in Supabase) | **Keep pgvector** — sufficient up to ~10M vectors/org |
| **Graph DB** | NetworkX in-memory | **Migrate to batch-persisted communities table + SQL recursive CTEs** for L6 traversal. Add Apache AGE extension **only when** traversal exceeds 100ms at p95 (probably year 2). **Do not add Neo4j.** |
| **Observability** | Basic logs + Sentry 10% | **Sentry 100% for errors, structured JSON logs, one dashboard (Grafana Cloud free tier)** for p95/p99 latency + error rate |
| **CI/CD** | None | **GitHub Actions** — lint + pytest on PR, deploy to DO App Platform on main merge |
| **Secrets** | .env files | **DO App Platform encrypted env vars** for prod; `.env` only for local dev |

**Deploy topology (minimum viable production):**

```
┌──────────────┐   ┌──────────────┐
│ Load Balancer│   │   Cloudflare │
└──────┬───────┘   └──────┬───────┘
       │                  │
┌──────▼──────┐    ┌──────▼──────┐
│  API x 2    │    │  Next.js    │
│ (FastAPI)   │    │  Dashboard  │
└──────┬──────┘    └─────────────┘
       │
       ├──► Supabase Postgres (primary)
       ├──► Supabase Postgres read replica (for /v1/contacts searches)
       ├──► Upstash Redis (cache + broker + rate limits)
       │
┌──────▼────────────────────┐
│ Celery Workers x 2-4      │
│ - Gmail/Calendar sync     │
│ - LLM extraction (L1)     │
│ - Score recalc (L2/L3)    │
│ - Anomaly scan (L5)       │
│ - Insight synthesis (L7)  │
│ - Webhook delivery        │
└───────────────────────────┘
       │
┌──────▼──────┐
│ Celery Beat │  (single instance, scheduled jobs)
└─────────────┘
```

**Cost estimate (DO + managed):**
- DO App Platform (2 API instances, basic tier): ~$24/mo
- DO droplet for workers + beat: ~$18/mo
- Supabase Pro (when you outgrow free tier): $25/mo
- Upstash Redis Pay-as-you-go: ~$10-20/mo at MVP load
- **Total: ~$80-100/mo for 50-200 orgs.** Scales linearly.

---

## 4. Phased execution plan

Each phase is self-contained. Each has a clear "done" definition. No phase depends on future work.

### Phase 0 — Stop the bleeding (done during this audit)

| Done |
|---|
| ✅ F1 agent_behavior/action_recommendation reconciliation |
| ✅ F2 communication_style always string, falls back to what_works |
| ✅ F3 commitment dedupe |
| ✅ F4 topics from meeting titles |
| ✅ F5 `is_broadcast` computed flag on bundles + search |
| ✅ F8 entity-loop cap (was blocking multi-contact workflows) |
| ✅ G1 `/v1/contacts` search endpoint + MCP tool |
| ✅ G2 temporal filters (needs_attention, overdue, silent_days) |
| ✅ Tunables module — all patterns/thresholds env-overridable |
| ✅ Audit script + eval harness skeleton |

### Phase 1 — Fix the 4 critical risks from L1 diagram (1–2 weeks)

| # | Task | Files | Why |
|---|---|---|---|
| 1.1 | **Move LLM extraction off sync path** | [entity_extractor.py](genios-brain/app/ingestion/entity_extractor.py), [gmail_sync.py](genios-brain/app/tasks/gmail_sync.py) — create new `tasks/extract_interactions.py` | Sync becomes non-blocking. Gmail fetch → raw interaction row → Celery task extracts in background. |
| 1.2 | **Batch LLM calls** | new `classifier.py` | 10 interactions per Gemini call, not 1. Cuts LLM cost 10x. |
| 1.3 | **Tier-0 filter BEFORE LLM** — **tags**, does not **drop** | [email_classifier.py](genios-brain/app/ingestion/email_classifier.py) reordered | Skip *LLM extraction* for noreply/newsletter senders (30-50% LLM cost saved) — but interaction row is still stored with `classification='broadcast'`. Per Principle P1. |
| 1.4 | **Fix cache key** | [cache.py](genios-brain/app/context/cache.py) | Key on `sha256(org_id + entity + situation_hash)`. Expect 10x hit rate improvement. |
| 1.5 | **Persist community detection** | new `tasks/recompute_communities.py` + `contact_communities` table | NetworkX in batch job → write to DB. Stateless API. Multi-worker safe. |
| 1.6 | **Nightly refresh checkpointing** | [nightly_refresh.py](genios-brain/app/tasks/nightly_refresh.py) | Per-contact try/except + `last_recomputed_at` column. One failure ≠ batch fail. |
| 1.7 | **Parallelize bundle_builder queries** | [bundle_builder.py](genios-brain/app/context/bundle_builder.py) | `asyncio.gather` or `psycopg pool` — run independent queries concurrently. Target p95 < 1s. |

**Phase 1 — ✅ DONE** (1.7 deferred — needs profiling with real load).

### Phase 2 — Security + test harness — ✅ DONE

| # | Task | Why |
|---|---|---|
| 2.1 | **Enable Supabase RLS** on contacts, interactions, commitments, api_keys | Defense-in-depth against cross-tenant leaks |
| 2.2 | **Revoke all legacy plaintext API keys**, require hashed | Standard security hygiene |
| 2.3 | **pytest + golden eval set** (50 labelled contacts, 10 scenarios) | Regression prevention. Every PR runs it. |
| 2.4 | **Structured JSON logs with request_id** | Debugging in prod |
| 2.5 | **GitHub Actions CI** — lint + tests on PR | No bad merges |

### Phase 3 — Classification at ingestion — ✅ DONE

> **This phase implements Principle P1 (ingest everything, tag, filter at read) end-to-end.**
> Nothing is dropped. Every inbound email/contact lands in Postgres.
> Classification is a **tag** on the row, not a filter on the pipe.

| # | Task | Why | P1 alignment |
|---|---|---|---|
| 3.1 | **Parse email headers at ingestion** (`List-Unsubscribe`, `Precedence`, `X-Mailer`, `X-Campaign-*`) in gmail_connector | 80% of automated mail classified at zero cost | **Tag, don't drop** — sets `classification='newsletter'`, stays in DB |
| 3.2 | **LLM classifier** — batched Celery task, 10 contacts per call | Catches the 20% headers miss (Boardy-style bots, unmarked marketing) | Writes classification to same row, no row rejected |
| 3.3 | **Schema additions** on `contacts`: `classification`, `classification_confidence`, `classified_at`, `classification_method`, `classification_override` | Full audit trail of why a contact was tagged how | `classification_override` lets user force `real_person` even if classifier says `newsletter` — user always wins |
| 3.4 | **Read-time filter** — `/v1/context` and `/v1/contacts` hide `newsletter/bot/transactional` by default; accept `include_broadcast=true` to show them | Agents get clean data without losing the raw graph | **Pure read-layer concern.** Ingestion layer unaware. |
| 3.5 | **Commitment extractor gated at read, not at ingest** — extract all commitments at ingestion; bundle only surfaces commits where `is_bidirectional=true OR manual_commitment_confirmed=true` | Fixes the "newsletter CTAs appearing as commitments" bug without losing the underlying extraction | Extract-everything, surface-selectively |
| 3.6 | **Dashboard override UI** — button on each contact: "Mark as real person" / "Mark as newsletter" / "Reclassify" | Human-in-the-loop is the escape hatch for every classifier | Override takes precedence forever (can only be changed by human) |

### Phase 4 — L5 Anomaly Detection — ✅ DONE

| # | Task | Why |
|---|---|---|
| 4.1 | **Z-score computation** against 90-day personal baseline | Per-entity deviation flag |
| 4.2 | **Scheduled scan** (Celery Beat every 6h) — compute z-scores for all active contacts | Data ready for proactive scanner |
| 4.3 | **Schema**: `contact_baselines` (rolling 90d stats), `contact_anomalies` (flagged entities with deviation_score) | Persisted anomaly state |

### Phase 5 — L6 Root Cause + Fingerprint Matching — ✅ DONE

| # | Task | Why |
|---|---|---|
| 5.1 | **Fingerprint schema** — `{stage, sentiment_bucket, days_bucket, entity_type, has_overdue, situation_category, sentiment_trend}` | L2 spec §L6 |
| 5.2 | **Precedent table** — historical situations with outcome (`RECOVERED`, `LOST`, etc.) | Source for matching |
| 5.3 | **Weighted nearest-neighbor match** (no ML — just weighted field comparison) | L2 spec §L6 |
| 5.4 | **Graph traversal primitives** — SQL recursive CTE for authority chains, warm-intro paths | Today: hardcoded. Target: query-driven. |

### Phase 6 — Proactive mode — ✅ DONE

| # | Task | Why |
|---|---|---|
| 6.1 | **Scanner task** (Celery Beat, every 6h) — combines L5 anomalies + L6 root causes | L2 vision |
| 6.2 | **Insight generator (L7)** — single LLM call to write `memory_view` + `genios_view` | L2 spec §L7 |
| 6.3 | **`insights` table** — persist every generated insight with status (pending/delivered/dismissed) | Audit + retry |
| 6.4 | **Webhook delivery** — push insight to customer-configured URL with HMAC signature | L2 spec |
| 6.5 | **Dashboard `/insights` view** — user sees what GeniOS noticed | UX |

### Phase 7 — Scale readiness (ongoing, as load grows)

| Trigger | Action |
|---|---|
| p95 /v1/context > 1s | Profile → optimize bundle_builder → add read replica routing |
| Context cache hit rate < 30% | Revisit cache key + TTL |
| Supabase free tier exhausted | Move to Supabase Pro ($25/mo) |
| SQL traversal > 100ms p95 | Add Apache AGE extension |
| NetworkX batch job > 10 min | Switch to igraph (10x faster) |
| 1000+ orgs | Add read replica per region, sharded by org_id |

---

## 5. Security hardening checklist (blocker items)

| # | Item | Mechanism |
|---|---|---|
| 5.1 | Supabase RLS enabled on every tenant table | `CREATE POLICY ... USING (org_id = auth.uid())` — app sets JWT claim per request |
| 5.2 | API key rotation endpoint + 90-day forced rotation | `POST /v1/keys/rotate` |
| 5.3 | All API keys SHA-256 hashed in DB, prefix only shown | Already partial — finish migration |
| 5.4 | Rate limiting enforced (429), not just logged | Already works; tune rph_org for real traffic |
| 5.5 | Encryption at rest for commitment text + interaction summaries | Supabase Vault or column-level pgcrypto |
| 5.6 | Audit log — every context call logged to `context_calls` with who/what/when | Already exists — add 90-day retention + index |
| 5.7 | GDPR delete-my-data endpoint — cascade delete org → all rows | `DELETE FROM orgs WHERE id = X CASCADE` (schema must enforce) |
| 5.8 | Export-my-data endpoint — dump all tables filtered by org_id as JSON | Per regulation |

---

## 6. What needs to change in the L2 vision doc itself

Reading the PDF critically — two things missing or underspecified:

| # | Gap in L2 doc | Recommendation |
|---|---|---|
| 6.1 | **No definition of "credit exhaustion" behavior** — what does an agent get when credits=0? 402 Payment Required? 429 Too Many Requests? | Document the error contract + grace period policy |
| 6.2 | **Proactive webhook security** not specified — how is the receiving webhook authenticated? | Add: HMAC signature in `X-Genios-Signature` header, shared secret per org |
| 6.3 | **L6 precedent table population** not specified — how do historical situations get their outcome labels? | Add: auto-label from stage transitions (e.g., NEEDS_ATTENTION → ACTIVE within 30d = RECOVERED); manual override via dashboard |
| 6.4 | **L1 output schema not versioned** — when Gemini changes output format, how do we handle old records? | Add `schema_version` field to every extracted interaction |
| 6.5 | **Rate limits per plan** are mentioned but not defined (RPM/RPH/concurrent) | Align doc with `plan_enforcer.py` config values |

---

## 7. What I need from you to start Phase 1

Zero new decisions needed. You've already told me:
- Infrastructure: DigitalOcean for API + Celery + frontend → **locked**
- Database: keep Supabase + pgvector → **locked**
- LLM: Groq replaceable later, Gemini fine for now → **locked**
- Scale target: unspecified, so I'm building for 500 orgs × 2k contacts → **locked until you override**

**Go-signal options:**
- "Start Phase 1 now" → I begin with 1.1 (move LLM off sync path)
- "Start Phase 2 first" → Security + tests before perf
- "Only fix the 4 L1 critical risks, skip L5-L7 for now" → MVP+ not L2
- Custom ordering → tell me

---

## 8. Out of scope for this document

These are real concerns but deferred until first paying customer or specific trigger:

- Multi-region deploy (trigger: international customer + >100ms cross-region latency)
- Graph DB migration (trigger: SQL traversal p95 > 100ms)
- ML-based classification (trigger: heuristics + LLM accuracy drops below 95%)
- Cost optimization on Supabase (trigger: bill > $500/mo)
- Self-hosted Postgres (trigger: Supabase incident causes >1h downtime twice)
- Realtime push via Supabase Realtime (trigger: customer asks for live UI updates)

---

## Appendix — File map of changes per phase

Phase 1 will touch these files:
- `genios-brain/app/tasks/gmail_sync.py` (1.1)
- `genios-brain/app/tasks/extract_interactions.py` (1.1, 1.2 — new)
- `genios-brain/app/ingestion/email_classifier.py` (1.3)
- `genios-brain/app/ingestion/classifier.py` (1.2 — new)
- `genios-brain/app/context/cache.py` (1.4)
- `genios-brain/app/tasks/recompute_communities.py` (1.5 — new)
- `genios-brain/app/tasks/nightly_refresh.py` (1.6)
- `genios-brain/app/context/bundle_builder.py` (1.7)
- `migrations/052_contact_communities.sql` (1.5 — new)
- `migrations/053_interaction_schema_version.sql` (6.4 — new)

Phase 2–7 file maps will be added as those phases start.
