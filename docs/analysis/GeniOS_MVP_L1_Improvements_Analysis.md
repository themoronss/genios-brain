# GeniOS — MVP L1 Improvements: Final Implementation Plan

**Architecture Risk Analysis & Implementation Roadmap**
**Generated: April 5, 2026**
**Status: Decisions finalized after codebase analysis + infra review**

---

## Table of Contents

1. [Executive Summary — What We're Doing](#1-executive-summary)
2. [What the PDF Proposed vs What We Actually Need](#2-pdf-vs-reality)
3. [Batch 1: Quick Wins (FREE, No Dependencies)](#3-batch-1)
4. [Batch 2: Celery Task Queue ($8-10/mo extra)](#4-batch-2)
5. [Batch 3: Entity Resolution Hardening (FREE)](#5-batch-3)
6. [Batch 4: pgvector Activation (FREE)](#6-batch-4)
7. [What We're NOT Doing (and Why)](#7-skipping)
8. [Infrastructure & Cost Summary](#8-infra)
9. [Files to Modify — Complete Reference](#9-files)

---

## 1. Executive Summary

The PDF identified 6 architectural risks. After analyzing the live codebase:

| Risk | PDF Said | Reality | Decision |
|------|----------|---------|----------|
| 1. No Task Queue | Critical | **Valid** — BackgroundTasks share API process | **Implement Celery** |
| 2. NetworkX In-Memory | "Architecturally Fatal" | **Overstated** — graph rebuilds from PG on demand, not held in memory | **Skip** |
| 3. Gemini in Hot Path | Blows 500ms SLA | **Already solved** — context paragraph is template-based, no LLM | **Skip** |
| 4. Cache Key | ~5-15% hit rate | **Valid** — situation text in key causes constant misses | **Fix lookup order** |
| 5. Fuzzy Match 70% | Merges wrong people | **Valid** — threshold too low, no email anchoring | **Raise to 85% + add tiers** |
| 6. Nightly Refresh SPOF | No progress tracking | **Partially valid** — phase isolation exists, but no resume-on-restart | **Add progress table** |

**We implement 4 improvements across 4 batches. Skip Risks 2 and 3.**

---

## 2. PDF vs Reality — What Changed

### Risk 2: NetworkX — Why We Skip It
The PDF assumed the graph is held in memory across requests. In reality, `community_detection.py` rebuilds the graph from PostgreSQL every time. Results (community assignments, scores) are persisted to the DB. Multiple workers already read consistent data from Postgres. Redis serialization is unnecessary — PG IS the shared state. Celery (Batch 2) solves the remaining race condition concern by ensuring only one worker runs the nightly refresh.

### Risk 3: Gemini in Hot Path — Why We Skip It
The PDF assumed Gemini is called during context generation. In reality, `generate_context_paragraph()` in `bundle_builder.py` is 100% template-based string concatenation — zero LLM calls. Entity extraction (Groq/Gemini) runs only in background sync tasks. Context paragraphs are pre-computed in nightly refresh. Actual hot-path latency: ~94ms on cache miss. Well within 500ms SLA.

### Risk 4: pgvector — PDF Missed the Real Blocker
The PDF said "installed but doing nothing." Partially unfair — embeddings ARE stored and vector search IS implemented. The real blocker the PDF didn't identify: Gemini embedding-001 outputs 3072-dim vectors, but pgvector HNSW indexes cap at 2000 dims. Solution: use the same model's MRL parameter to output 768 dims (0.26% quality loss).

---

## 3. Batch 1: Quick Wins

**Cost: $0 | Dependencies: None | Effort: 2-3 days | Risk: Very low**

---

### 1A. Fix Cache Lookup Order

**Problem:** The context API checks the Redis situation-keyed cache first. Different situation text = cache miss = full bundle rebuild. Hit rate: ~5-15%.

**Fix:** Check `precomputed_bundles` (situation-independent, 24h TTL) BEFORE Redis situation-keyed cache. Only fall through to full generation if precomputed bundle is missing or expired.

**Impact:** Cache hit rate jumps from ~15% to ~70%+ for repeat contacts.

**Files to change:**
| File | Change |
|------|--------|
| `app/api/routes/context.py` | Reorder lookup: precomputed_bundles first, then Redis, then fresh build |
| `app/context/cache.py` | No structural change, just called later in the flow |

---

### 1B. Raise Fuzzy Match Threshold

**Problem:** 70% WRatio threshold matches wrong people. "John Smith" matches "John Smithson". "Sarah Chen" matches "Sarah Chan".

**Fix:** Raise `score_cutoff` from `70.0` to `85.0` in `get_contact_by_name()`. Add `resolution_method` field to bundle response.

**Impact:** Eliminates wrong-person merges. Some borderline matches return "no match" instead — safer than merging wrong contacts.

**Files to change:**
| File | Change |
|------|--------|
| `app/context/bundle_builder.py` | Change `score_cutoff=70.0` → `85.0`, add `resolution_method` to response |

---

### 1C. Add Nightly Refresh Progress Tracking

**Problem:** If nightly refresh crashes at phase 5, restart re-runs all 9 phases. No record of what completed.

**What exists (good):** Each phase has isolated try/except with `db.rollback()`. If Phase 3 fails, Phase 4 still runs.

**What's missing:** No persistent tracking. No resume-on-restart.

**Fix:** Create `refresh_jobs` table. Before each phase, check if completed for this org + date. After each phase, mark done. On restart, skip completed phases.

**Schema:**
```
refresh_jobs:
  org_id        UUID
  phase         VARCHAR     -- 'score_contacts', 'community_detect', etc.
  run_date      DATE
  status        VARCHAR     -- 'pending' / 'running' / 'completed' / 'failed'
  started_at    TIMESTAMP
  completed_at  TIMESTAMP
  error_message TEXT
  UNIQUE(org_id, phase, run_date)
```

**Files to change:**
| File | Change |
|------|--------|
| `migrations/047_refresh_jobs.sql` | **New** — create table |
| `app/tasks/nightly_refresh.py` | Check/update refresh_jobs before/after each phase |

---

## 4. Batch 2: Celery Task Queue

**Cost: ~$8-10/mo extra | Dependencies: celery[redis] | Effort: 2-3 days | Risk: Medium**

This is the single most impactful architectural change.

---

### What It Fixes

| Today (broken at 10 orgs) | After Celery |
|---------------------------|-------------|
| Sync runs in API process — blocks API requests | Sync runs in separate worker — API stays fast |
| Crash during sync = lost task, no retry | Crash → automatic retry (3 times, 60s delay) |
| No visibility into what's queued/failed | Full task queue visibility |
| 10 orgs sync simultaneously → API dies | 10 orgs queue → worker processes them, API untouched |
| Scheduler loop in API process memory | Celery Beat runs scheduling independently |

---

### Infrastructure Required

| Component | What | Cost | Action |
|-----------|------|------|--------|
| Python package | `celery[redis]` | $0 | Add to `requirements.txt` |
| Render Background Worker | Second service running `celery -A app.celery_app worker` | **+$7/mo** | Create new Render service, same repo |
| Upstash Redis | Upgrade to Pay-as-you-go (Celery heartbeats burn through free tier 10k/day limit) | **+$1-3/mo** | Switch plan in Upstash dashboard |

**Total extra: ~$8-10/mo on top of current Render costs.**

**Why we stay on Render (not Fly.io):**
- Already deployed there — no migration pain
- Adding a Background Worker is 5 minutes in the Render dashboard
- Fly.io would save $2-3/mo but requires learning new CLI, config format, deploy flow
- Fly.io free tier has cold starts and sleeping machines — unreliable

---

### Code Changes

**2A. New Celery config:**
| File | Change |
|------|--------|
| `app/celery_app.py` | **New** — Celery app with Redis broker, 2 queues (high_priority, low_priority) |
| `requirements.txt` | Add `celery[redis]` |

**2B. Convert sync tasks to Celery tasks:**
| File | Change |
|------|--------|
| `app/tasks/gmail_sync.py` | Add `@celery.task(bind=True, max_retries=3, default_retry_delay=60)` |
| `app/tasks/calendar_sync.py` | Same decorator |
| `app/tasks/slack_sync.py` | Same decorator |
| `app/tasks/jira_sync.py` | Same decorator |
| `app/tasks/notion_sync.py` | Same decorator |
| `app/tasks/sheets_sync.py` | Same decorator |
| `app/tasks/drive_sync.py` | Same decorator |
| `app/tasks/docs_sync.py` | Same decorator |
| `app/tasks/hubspot_sync.py` | Same decorator |
| `app/tasks/nightly_refresh.py` | Same decorator (low_priority queue) |
| `app/tasks/weekly_report.py` | Same decorator (low_priority queue) |
| `app/tasks/billing_jobs.py` | Same decorator (low_priority queue) |

Function logic stays identical. Only the decorator and error handling wrapper change.

**2C. Replace call sites:**
| File | Change |
|------|--------|
| `app/api/routes/sync.py` | Replace `background_tasks.add_task(sync_task, org_id)` → `sync_task.delay(org_id)` |
| `app/main.py` | Remove `sync_scheduler_loop()` — replaced by Celery Beat periodic tasks |

**2D. Render deployment:**
- Create new "Background Worker" service in Render dashboard
- Same repo, same branch, same env vars
- Start command: `celery -A app.celery_app worker --loglevel=info -Q high_priority,low_priority`
- Optional: Add Celery Beat to same worker or as third service

---

## 5. Batch 3: Entity Resolution Hardening

**Cost: $0 | Dependencies: None | Effort: 1-2 days | Risk: Low**

---

### Current (2-tier, unsafe)

```
1. Exact match (name/email) → confidence 1.0
2. Fuzzy match at 70% → confidence = score/100
```

### After (6-tier, production-safe)

| Tier | Method | Confidence | Auto-merge? |
|------|--------|------------|-------------|
| 1 | Email exact match | 1.0 | Yes |
| 2 | Email domain + name fuzzy (>70%) | 0.9 | Yes |
| 3 | Name exact + company fuzzy (>80%) | 0.85 | Yes |
| 4 | Name fuzzy >85% only | 0.7 | No — flag for review |
| 5 | Name fuzzy 70-85% | 0.5 | No — return confidence, let agent decide |
| 6 | No match | 0.0 | Create new contact + flag as unresolved |

**Key rule:** Never auto-merge below 0.85 without an email anchor.

### New `resolution_method` field in API response

```json
{
  "match_confidence": 0.9,
  "resolution_method": "email_domain_name_fuzzy",
  "agent_behavior_guidance": "execute_autonomously"
}
```

Values: `email_exact`, `email_domain_name_fuzzy`, `name_exact_company_fuzzy`, `name_fuzzy`, `no_match`

**Files to change:**
| File | Change |
|------|--------|
| `app/context/bundle_builder.py` | Rewrite `get_contact_by_name()` with 6-tier pipeline, add `resolution_method` to bundle |

---

## 6. Batch 4: pgvector Activation

**Cost: $0 | Dependencies: None | Effort: 1-2 days | Risk: Low**

---

### The Problem (that the PDF missed)

- Gemini embedding-001 outputs **3072 dimensions**
- pgvector HNSW/IVFFlat indexes cap at **2000 dimensions**
- Result: embeddings stored but **no index** → every vector search is a full table scan
- Migration 033 already documents this limitation

### The Solution (no model switch needed)

Gemini embedding-001 supports **Matryoshka Representation Learning (MRL)**. It has an `output_dimensionality` parameter that truncates the vector to any size. The first 768 dimensions already contain a fully coherent embedding.

**One parameter change:**
```python
# Before (3072 dims — can't index)
result = genai.embed_content(model="models/gemini-embedding-001", content=text)

# After (768 dims — indexable, 0.26% quality loss)
result = genai.embed_content(model="models/gemini-embedding-001", content=text, output_dimensionality=768)
```

- Same model, same API key, same free tier, same code
- 768 dims is well under the 2000 limit
- Quality loss: 0.26% (negligible)

### Compatibility Verified

| Component | Compatible? | Notes |
|-----------|------------|-------|
| Supabase PostgreSQL | Yes | `vector(768)` fully supported |
| pgvector HNSW index | Yes | Well under 2000 dim limit |
| Cosine distance (`<=>`) | Yes | Dimension-agnostic operator |
| gemini-embedding-001 API | Yes | Native MRL support via `output_dimensionality` |
| `genai.embed_content()` | Yes | Just add one parameter |
| Vector format in queries.py | Yes | `"[v1,v2,...,v768]"` — same format, fewer values |
| Hybrid scoring in chat.py | Yes | `(1 - (embedding <=> vector))` works at any dimension |
| embed_contacts / embed_interactions | Yes | Calls `embed_text()` which auto-returns 768 |
| situation_embedder.py | Yes | Wraps `embed_text()` — automatic |

### Migration Required

After switching to 768 dims, old 3072-dim embeddings are incompatible. The column type change NULLs out existing embeddings. Re-embedding is needed.

**Re-embedding cost:** $0 (Gemini free tier: 1500 requests/minute). Even 10k contacts take ~7 minutes.

### Files to change

| File | Change |
|------|--------|
| `app/graph/embedder.py` | Add `output_dimensionality=768` to `embed_content()` call |
| `app/context/situation_embedder.py` | Fix outdated comment ("dimension 1536" → "dimension 768") |
| `migrations/048_pgvector_768.sql` | **New** — ALTER columns to `vector(768)`, CREATE HNSW indexes |

**Migration SQL:**
```sql
-- Switch to 768-dim embeddings (Gemini MRL)
ALTER TABLE contacts ALTER COLUMN embedding TYPE vector(768);
ALTER TABLE interactions ALTER COLUMN embedding TYPE vector(768);

-- Now we can create HNSW indexes (under 2000 dim limit)
CREATE INDEX idx_contacts_embedding ON contacts
    USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_interactions_embedding ON interactions
    USING hnsw (embedding vector_cosine_ops);
```

**Post-migration:** Run `embed_contacts()` and `embed_interactions()` for all orgs to regenerate embeddings at 768 dims.

---

## 7. What We're NOT Doing (and Why)

| Suggestion from PDF | Why Skip | When to Revisit |
|---------------------|----------|-----------------|
| NetworkX → Redis serialization | Graph already rebuilds from PG. Not held in memory. Celery solves the race condition. | Never (unless you move to Neo4j) |
| Remove Gemini from hot path | Already done — context paragraph is template-based | Never (already solved) |
| Neo4j / Memgraph migration | Massive effort. PG + NetworkX is adequate at current scale | 500+ orgs |
| Tiered storage (hot/warm/cold) | Premature optimization. All contacts fit in PG | 10,000+ contacts per org |
| Context versioning / snapshots | Nice-to-have, not blocking anything | When agents need "what changed" diffs |
| Row-level security in PG | org_id filtering is consistent. No SQL injection vectors | Before enterprise / SOC2 audit |
| Read replica for dashboards | Single PG handles current load | When dashboard queries spike API latency |

---

## 8. Infrastructure & Cost Summary

### Current Setup

| Service | Provider | Cost |
|---------|----------|------|
| Backend API | Render (Web Service) | ~$7/mo |
| Database | Supabase (PostgreSQL, AWS Tokyo) | Free or $25/mo |
| Redis | Upstash (TLS) | Free tier |
| Frontend | Unknown (likely Render/Vercel) | Free tier |
| LLM - Embeddings | Gemini embedding-001 | Free tier |
| LLM - Extraction | Groq (primary) + Gemini (fallback) | Free tier |
| Analytics | PostHog | Free tier |
| Error tracking | Sentry (Germany) | Free tier |
| Payments | Razorpay | Per-transaction |

### After All 4 Batches

| Change | Extra Cost |
|--------|-----------|
| Batch 1 (cache, fuzzy, refresh tracking) | $0 |
| Batch 2 (Celery worker on Render) | **+$7/mo** |
| Batch 2 (Upstash Pay-as-you-go upgrade) | **+$1-3/mo** |
| Batch 3 (entity resolution) | $0 |
| Batch 4 (pgvector 768-dim) | $0 |
| **Total extra** | **~$8-10/mo** |

### Render Setup After Batch 2

| Render Service | Type | Start Command |
|----------------|------|---------------|
| genios-brain (existing) | Web Service | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| genios-worker (new) | Background Worker | `celery -A app.celery_app worker --loglevel=info -Q high_priority,low_priority` |

Both services use the same repo, branch, and env vars.

---

## 9. Files to Modify — Complete Reference

### Batch 1 (Quick Wins — $0)

| File | Change | Type |
|------|--------|------|
| `app/api/routes/context.py` | Reorder cache lookup: precomputed_bundles first | Edit |
| `app/context/bundle_builder.py` | Raise fuzzy threshold 70→85, add `resolution_method` | Edit |
| `migrations/047_refresh_jobs.sql` | Create refresh_jobs table | **New** |
| `app/tasks/nightly_refresh.py` | Check/update refresh_jobs per phase | Edit |

### Batch 2 (Celery — +$8-10/mo)

| File | Change | Type |
|------|--------|------|
| `app/celery_app.py` | Celery config, Redis broker, 2 queues | **New** |
| `requirements.txt` | Add `celery[redis]` | Edit |
| `app/tasks/gmail_sync.py` | Add `@celery.task` decorator | Edit |
| `app/tasks/calendar_sync.py` | Add `@celery.task` decorator | Edit |
| `app/tasks/slack_sync.py` | Add `@celery.task` decorator | Edit |
| `app/tasks/jira_sync.py` | Add `@celery.task` decorator | Edit |
| `app/tasks/notion_sync.py` | Add `@celery.task` decorator | Edit |
| `app/tasks/sheets_sync.py` | Add `@celery.task` decorator | Edit |
| `app/tasks/drive_sync.py` | Add `@celery.task` decorator | Edit |
| `app/tasks/docs_sync.py` | Add `@celery.task` decorator | Edit |
| `app/tasks/hubspot_sync.py` | Add `@celery.task` decorator | Edit |
| `app/tasks/nightly_refresh.py` | Add `@celery.task` decorator (low_priority) | Edit |
| `app/tasks/weekly_report.py` | Add `@celery.task` decorator (low_priority) | Edit |
| `app/tasks/billing_jobs.py` | Add `@celery.task` decorator (low_priority) | Edit |
| `app/api/routes/sync.py` | Replace `add_task()` → `.delay()` | Edit |
| `app/main.py` | Remove `sync_scheduler_loop()` | Edit |

### Batch 3 (Entity Resolution — $0)

| File | Change | Type |
|------|--------|------|
| `app/context/bundle_builder.py` | Rewrite `get_contact_by_name()` with 6-tier pipeline | Edit |

### Batch 4 (pgvector — $0)

| File | Change | Type |
|------|--------|------|
| `app/graph/embedder.py` | Add `output_dimensionality=768` parameter | Edit |
| `app/context/situation_embedder.py` | Fix comment (1536 → 768) | Edit |
| `migrations/048_pgvector_768.sql` | ALTER columns to vector(768), CREATE HNSW indexes | **New** |

### Summary Counts

| | Edited Files | New Files | Total |
|-|-------------|-----------|-------|
| Batch 1 | 3 | 1 | 4 |
| Batch 2 | 14 | 1 | 15 |
| Batch 3 | 1 | 0 | 1 |
| Batch 4 | 2 | 1 | 3 |
| **Total** | **20** | **3** | **23** |

---

### Implementation Order

```
Batch 1 (free, no deps)     →  Ship immediately
Batch 3 (free, no deps)     →  Ship with Batch 1
Batch 4 (free, no deps)     →  Ship with Batch 1
Batch 2 (needs Render + Upstash setup)  →  Ship after infra is ready
```

Batches 1, 3, 4 can all be done in parallel — zero dependencies between them. Batch 2 requires the Render Background Worker and Upstash upgrade to be set up first.

---

*Final version — all decisions confirmed after codebase analysis, infra review, and compatibility verification. April 5, 2026.*
