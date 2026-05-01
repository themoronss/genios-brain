# GeniOS Production Readiness Review

## 1. Context Calls

### Current State
- Every `POST /v1/context` call is logged to `context_calls` table (PostgreSQL)
- 3-tier caching: Redis (60s) → precomputed_bundles (24h) → on-demand build
- Dashboard calls now tagged `source='dashboard'` via `X-GeniOS-Source` header (just implemented)
- External agent calls tagged `source='api'`, counted toward quota
- Rate limiting: 429 returned when daily limit exceeded (hustler=3000, startup=10000)
- **Zero LLM calls** on context requests — bundles are pre-aggregated from stored data

### Issues / Risks

| Issue | Risk | Priority |
|-------|------|----------|
| Fuzzy match loads ALL contacts into memory (`SELECT id, name, email FROM contacts WHERE org_id = :oid`) | Memory spike with 5000+ contacts per org | HIGH |
| No per-second rate limiting | A single agent can burst 1000 calls in 1 second, exhausting connection pool | HIGH |
| 6-8 DB queries per on-demand bundle build | Under 10 concurrent cache-misses, pool_size=10 connections exhausts | MEDIUM |
| No vector search index on embeddings column | Full table scan on every embedding-based search | CRITICAL |
| Cache invalidation is time-based only (60s Redis, 24h bundles) | If contact data changes mid-day (new email, commitment), stale data served for up to 24h | MEDIUM |

### Recommended Changes

1. **Add LIMIT to fuzzy match query** — cap at 500 candidates, order by interaction_count DESC
2. **Add per-second rate limiting** — use Redis sliding window: max 10 calls/second per org
3. **Add pgvector index** — `CREATE INDEX ON contacts USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)`
4. **Event-driven cache invalidation** — invalidate precomputed bundle when new interaction is created (not just time-based)

---

## 2. API Key + Organization Control

### Current State
- One API key per org: `gn_live_{secrets.token_urlsafe(32)}`
- Stored **plain text** in `orgs.api_key` column
- Verified via `SELECT id FROM orgs WHERE api_key = :api_key`
- Key regeneration overwrites old key immediately (no grace period)
- No per-key tracking — all agents share the org's single key
- No key rotation audit log

### Issues / Risks

| Issue | Risk | Priority |
|-------|------|----------|
| API keys stored unhashed in database | DB breach = all keys compromised instantly | CRITICAL |
| JWT secret hardcoded: `"genios-secret-key-replace-in-production"` | Anyone reading source can forge tokens | CRITICAL |
| JWT tokens valid for 7 days with no revocation | Leaked token can't be invalidated | HIGH |
| Single key per org — no multi-key support | Can't give different agents different permissions or track per-agent usage | MEDIUM |
| No key rotation grace period | Regenerating key instantly breaks all integrations | MEDIUM |

### Recommended Changes

1. **Hash API keys** — store `bcrypt(api_key)`, compare on auth. Keep only prefix (`gn_live_...abc`) for display.
2. **Move JWT secret to env var** — `JWT_SECRET = os.environ["JWT_SECRET"]` with strong random value
3. **Add API key table** — separate `api_keys` table with `org_id, key_hash, name, created_at, last_used_at, revoked_at`
4. **Add token revocation** — store revoked JWT IDs in Redis with TTL matching token expiry
5. **Key rotation grace period** — keep old key valid for 24h after regeneration

---

## 3. Pricing & LLM Cost Planning

### Groq Limitation (Blocker)

Groq free tier: **30 requests/minute, 14,400 requests/day**. A single Gmail sync processes 100+ emails with 2s delay between each = ~50 min per org. With 10 orgs syncing concurrently, Groq rate limits will block syncs. **Groq is not viable as primary for production.**

### Per-Call Token Profile (from actual prompt analysis)

Our extraction prompt = ~500 tokens (system + template) + ~750 tokens (email body, 3000 char cap) + ~200 tokens (thread context) = **~1,450 input tokens**. Max output = **700 tokens**. This is the baseline for all cost comparisons.

### LLM Options Comparison

| # | Model | Provider | Input $/1M | Output $/1M | Cost/Call | Rate Limit | Speed | JSON Quality |
|---|-------|----------|-----------|-------------|-----------|------------|-------|-------------|
| 1 | **Gemini 2.5 Flash** | Google | $0.15 | $0.60 | **$0.00064** | 2,000 RPM (paid) | ~200 tok/s | Good |
| 2 | **GPT-4.1 mini** | OpenAI | $0.40 | $1.60 | **$0.00170** | 10,000 RPM | ~150 tok/s | Excellent |
| 3 | **Claude Haiku 4.5** | Anthropic | $0.80 | $4.00 | **$0.00396** | 4,000 RPM | ~180 tok/s | Excellent |
| 4 | **GPT-4.1 nano** | OpenAI | $0.10 | $0.40 | **$0.00043** | 10,000 RPM | ~250 tok/s | Good |

*Cost/call = (1,450 × input rate) + (700 × output rate)*

### Monthly Cost per Org (100 emails/day sync + 10 drafts + 5 chats)

| Model | Email Sync (100/day) | Drafts (10/day) | Chat (5/day) | Monthly Total |
|-------|---------------------|-----------------|--------------|---------------|
| Gemini 2.5 Flash | $1.92 | $0.19 | $0.10 | **$2.21** |
| GPT-4.1 mini | $5.10 | $0.51 | $0.26 | **$5.87** |
| Claude Haiku 4.5 | $11.88 | $1.19 | $0.59 | **$13.66** |
| GPT-4.1 nano | $1.29 | $0.13 | $0.06 | **$1.48** |

### Recommendation

| Role | Model | Why |
|------|-------|-----|
| **Primary (email extraction)** | **Gemini 2.5 Flash** | Cheapest with good JSON, 2000 RPM handles 20 orgs syncing concurrently, already integrated as fallback |
| **High-quality fallback** | **GPT-4.1 mini** | Best JSON extraction quality, 10K RPM headroom, reasonable cost |
| **User-facing (drafts/chat)** | **Claude Haiku 4.5** | Best quality for natural text, built-in safety guardrails, worth the premium for user-visible output |
| **Budget option** | **GPT-4.1 nano** | Cheapest at $1.48/org/month, good enough for extraction if cost is primary concern |

### At Scale (100 orgs)

| Model | 100 orgs/month | 1000 orgs/month |
|-------|---------------|-----------------|
| Gemini 2.5 Flash | $221 | $2,210 |
| GPT-4.1 mini | $587 | $5,870 |
| Claude Haiku 4.5 | $1,366 | $13,660 |
| GPT-4.1 nano | $148 | $1,480 |

### Cost Tracking (Not Implemented)

**Missing:** No token counting anywhere. Add:
- Log `prompt_tokens` and `completion_tokens` per LLM call to a `llm_usage` table
- Aggregate per org per day
- Expose in dashboard settings (Plan & Billing tab)
- Set cost alerts at 80% of budget threshold

---

## 4. Guardrails

### What Exists

| Guardrail | Status | Location |
|-----------|--------|----------|
| Entity name validation (2-200 chars) | ✅ | context.py:26-32 |
| Prompt injection sanitization (12 regex patterns) | ✅ | entity_extractor.py:31-72 |
| Email body truncation (3000 chars for LLM) | ✅ | entity_extractor.py:187 |
| Rate limiting (daily quota, source-aware) | ✅ | context.py:70-95 |
| Parameterized SQL queries | ✅ | All routes (SQLAlchemy text()) |
| Non-blocking logging (failures don't crash API) | ✅ | context.py:98-130 |
| Password hashing (bcrypt) | ✅ | auth.py:87 |

### What's Missing

| Guardrail | Risk | Priority |
|-----------|------|----------|
| **No output moderation** — LLM responses returned unfiltered | Harmful/biased content in drafts and chat | HIGH |
| **No PII redaction** — context bundles may contain emails, phone numbers | Data leakage to external agents | HIGH |
| **No per-second rate limiting** — only daily quota checked | Burst attacks can DDoS the DB | HIGH |
| **No request body size limit** — FastAPI default 16MB | Large payload attacks | MEDIUM |
| **No looping agent detection** — same agent calling same entity repeatedly | Wasted compute, inflated costs | MEDIUM |
| **No SQL injection in f-string patterns** — auth.py:252, facts.py:116 use f-strings with SQL | Fragile, could become injection vector | MEDIUM |
| **Draft endpoint has no prompt injection check** — user_request passed directly to LLM | Prompt injection via draft requests | MEDIUM |
| **No timeout on LLM calls** — Groq/Gemini calls have no explicit timeout | Hanging requests block workers | MEDIUM |

### Recommended Additions

1. **Add request size limit** — `app.add_middleware(RequestSizeLimitMiddleware, max_size=1_000_000)` (1MB)
2. **Add per-second rate limit** — Redis sliding window: 10 req/s per org for API, 30 req/s for dashboard
3. **Add LLM timeout** — `timeout=30` on all Groq/Gemini calls
4. **Add looping detection** — if same org+entity called >20 times in 5 minutes, return cached bundle without logging
5. **Add draft prompt injection check** — run `sanitize_email_body()` on `user_request` field before passing to LLM

---

## 5. API Call Strategy

### Current Architecture

```
                    ┌─────────────────────────────────────┐
                    │         POST /v1/context             │
                    │  (single endpoint, single response)  │
                    └───────────┬─────────────────────────┘
                                │
                    ┌───────────▼───────────┐
                    │     Redis Cache (60s)  │─── HIT → return
                    └───────────┬───────────┘
                                │ MISS
                    ┌───────────▼───────────┐
                    │  Precomputed Bundle DB │─── HIT → return
                    │     (24h expiry)       │
                    └───────────┬───────────┘
                                │ MISS
                    ┌───────────▼───────────┐
                    │  On-demand Build       │
                    │  (6-8 DB queries)      │
                    │  NO LLM call           │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │  Cache in Redis (60s)  │
                    │  Return to agent       │
                    └───────────────────────┘
```

**LLM calls happen ONLY during:**
1. Gmail sync (per email — entity extraction)
2. Draft generation (on-demand, user-triggered)
3. Chat (on-demand, user-triggered)
4. Embeddings (nightly refresh)

**Context calls are LLM-free** — this is the right architecture.

### What's Optimal

- **Retrieval:** Fuzzy name match + pre-aggregated data (no RAG needed for MVP — data is already structured)
- **No chaining:** Single call returns complete bundle — agents don't need multiple round-trips
- **Caching:** 2-tier (Redis 60s + DB 24h) prevents redundant computation

### Issues

| Issue | Impact | Priority |
|-------|--------|----------|
| N+1 query pattern in `recalculate_all_relationships()` — 10+ queries per contact, processed sequentially | 1M+ queries for 100 orgs × 1000 contacts during nightly refresh | CRITICAL |
| No parallel processing — nightly refresh runs orgs sequentially | 50+ minutes for 100 orgs | HIGH |
| No job queue (Celery/RQ) — background tasks run in-process | No retry on failure, no monitoring, crash = lost work | HIGH |
| Fuzzy match fetches ALL contacts to Python memory | Doesn't scale past ~5000 contacts/org | MEDIUM |

### Recommended Improvements

1. **Batch relationship recalculation** — replace per-contact loop with:
   ```sql
   WITH scored AS (
     SELECT contact_id, COUNT(*), AVG(sentiment), MAX(interaction_at), ...
     FROM interactions GROUP BY contact_id
   )
   UPDATE contacts SET ... FROM scored WHERE contacts.id = scored.contact_id
   ```
   Reduces 1M queries → ~10 queries for entire org.

2. **Add Celery or similar** — background task queue with:
   - Parallel org processing (4 workers)
   - Automatic retry on failure
   - Dead letter queue for debugging
   - Task monitoring dashboard

3. **Limit fuzzy match** — add `ORDER BY interaction_count DESC LIMIT 500` to candidate query

4. **Add pgvector HNSW index** — for embedding searches:
   ```sql
   CREATE INDEX ON contacts USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
   ```

---

## Priority Summary

### CRITICAL (Fix Before Production)
1. Hash API keys in database
2. Move JWT secret to environment variable
3. Add pgvector search index
4. Batch relationship recalculation (N+1 elimination)

### HIGH (Fix Before Multi-Tenant Scale)
5. Add per-second rate limiting
6. Add output moderation on LLM responses
7. Add PII redaction in context bundles
8. Implement job queue (Celery) for background tasks
9. Add LLM token tracking per org
10. Add JWT token revocation

### MEDIUM (Fix Before Enterprise)
11. Multi-key support per org
12. Request body size limiting
13. Looping agent detection
14. Event-driven cache invalidation
15. PostgreSQL Row-Level Security (RLS)
16. LLM call timeouts
