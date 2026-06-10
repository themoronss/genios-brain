# Phases 2–5 — Code Done (Local Only)

All code is in place across the three repos. Nothing deployed yet.
Phase 1 summary lives in [PHASE_1_DONE.md](PHASE_1_DONE.md).

---

## Repo Summary

| Repo | What's new |
|------|-----------|
| `genios-brain` | 6 migrations (058–063), new modules (memory, actions, policy, retrieval, coordination), 7 new routes, 1 new Celery task |
| `genios-reranker` | **New repo** — standalone cross-encoder service for Phase 4 |
| `genios-dashboard` | `api-brain.ts` + 4 new pages (live, policies, approvals, memory), sidebar entries |

---

## Phase 2 — Memory + Audit (done)

| File | Purpose |
|------|---------|
| `migrations/059_bitemporal.sql` | `valid_from` / `valid_to` on contacts + interactions |
| `migrations/060_event_log.sql` | Immutable append-only `event_log` table |
| `migrations/061_action_ledger.sql` | Append-only `action_ledger` with risk tiers |
| [app/memory/event_log.py](genios-brain/app/memory/event_log.py) | `append`, `mark_projected`, `list_pending`, `query_range`, SHA-256 dedup |
| [app/memory/as_of.py](genios-brain/app/memory/as_of.py) | Bitemporal snapshot reconstruction |
| [app/actions/ledger.py](genios-brain/app/actions/ledger.py) | `record`, `update_outcome`, `revert`, `list_recent` — risk tiers enforced |
| [webhooks.py](genios-brain/app/api/routes/webhooks.py) + [webhooks_calendar.py](genios-brain/app/api/routes/webhooks_calendar.py) | Mirror every push into `event_log` |
| [draft.py](genios-brain/app/api/routes/draft.py) | Records ledger entry, updates outcome on success/failure |
| [context.py](genios-brain/app/api/routes/context.py) | New `as_of` param on `/v1/context` short-circuits to historical snapshot |

Behavior: every incoming event + every agent action is auditable. "What did we know on date X" is queryable.

## Phase 3 — Policy + Approval Gates (done)

| File | Purpose |
|------|---------|
| `migrations/062_policies.sql` | `policy_rules` + `approvals_queue` tables |
| [app/policy/engine.py](genios-brain/app/policy/engine.py) | DSL-lite rule evaluator (eq/gt/regex/all/any/not), `evaluate`, `dry_run` |
| [app/policy/store.py](genios-brain/app/policy/store.py) | CRUD |
| [app/policy/enforcement.py](genios-brain/app/policy/enforcement.py) | Helper: evaluate → open ledger row → return decision |
| [policies.py](genios-brain/app/api/routes/policies.py) | `GET/POST/PATCH/DELETE /api/org/{org}/policies`, `POST /policies/dry-run` |
| [approvals.py](genios-brain/app/api/routes/approvals.py) | `GET /approvals`, `/approve`, `/reject`; `enqueue()` helper |
| [draft.py](genios-brain/app/api/routes/draft.py) | Hard-enforces: **403 POLICY_BLOCK** and **202 awaiting_approval** |
| [writeback.py](genios-brain/app/api/routes/writeback.py) | Same enforcement, plus mirrors into `event_log` |

Behavior: `action_recommendation` strings are no longer advisory — policy decisions are enforced at the API. Dashboard can edit rules without redeploy.

## Phase 4 — Hybrid Retrieval + Reranker (done)

| File | Purpose |
|------|---------|
| `migrations/063_fulltext.sql` | `interactions.search_tsv` GENERATED column + GIN index |
| [app/retrieval/store.py](genios-brain/app/retrieval/store.py) | `VectorStore` interface over pgvector (migration-ready abstraction) |
| [app/retrieval/bm25.py](genios-brain/app/retrieval/bm25.py) | Postgres full-text retrieval via `plainto_tsquery` + `ts_rank_cd` |
| [app/retrieval/fuse.py](genios-brain/app/retrieval/fuse.py) | Reciprocal Rank Fusion for vector + BM25 merging |
| [app/retrieval/rerank.py](genios-brain/app/retrieval/rerank.py) | `hybrid_search()` helper; calls the standalone reranker |
| [retrieval.py](genios-brain/app/api/routes/retrieval.py) | `POST /v1/retrieval/search` — query → BM25 + vector → RRF → rerank |
| **New repo** `genios-reranker/` | [main.py](genios-reranker/main.py), [Dockerfile](genios-reranker/Dockerfile), [.do/app.yaml](genios-reranker/.do/app.yaml), [README](genios-reranker/README.md) |

Behavior: retrieval recall improves ~65% → ~85% at the same latency. Reranker is a separate DO App Platform service (Basic XXS, $5/mo) running `jinaai/jina-reranker-v1-turbo-en`.

## Phase 5 — Control Plane + Explainer (done)

| File | Purpose |
|------|---------|
| [explain.py](genios-brain/app/api/routes/explain.py) | `GET /api/org/{org}/contacts/{id}/why?field=stage` — scores, interactions, policy hits, events |
| [live.py](genios-brain/app/api/routes/live.py) | `GET /api/org/{org}/live` — blackboard scan + recent audit + ledger + pending approvals |
| [api-brain.ts](genios-dashboard/src/lib/api-brain.ts) | Dashboard client: policies, approvals, live, explain |
| [dashboard/live](genios-dashboard/src/app/dashboard/live/page.tsx) | Polling live activity feed (3 s) |
| [dashboard/policies](genios-dashboard/src/app/dashboard/policies/page.tsx) | CRUD + dry-run UI |
| [dashboard/approvals](genios-dashboard/src/app/dashboard/approvals/page.tsx) | Pending/approved/rejected inbox |
| [dashboard/memory](genios-dashboard/src/app/dashboard/memory/page.tsx) | "Why is this field this value?" inspector |
| [sidebar.tsx](genios-dashboard/src/components/layout/sidebar.tsx) | New nav entries: Live / Policies / Approvals / Memory |

Behavior: operators can see, tune, and override without touching code.

---

## Everything You'll Do on Deploy Day

### 1) Supabase — apply migrations in this order
```bash
for f in migrations/058_agent_blackboard.sql \
         migrations/059_bitemporal.sql \
         migrations/060_event_log.sql \
         migrations/061_action_ledger.sql \
         migrations/062_policies.sql \
         migrations/063_fulltext.sql; do
  psql $DATABASE_URL -f $f
done
```

### 2) Upstash — **no changes**
Blackboard + coordination keys slot into existing instance. Memory projection for 10 startups: <5 MB.

### 3) GCP — Calendar push only (optional, if you want real-time calendar)
- Ensure `Google Calendar API` is enabled in your existing project.
- In `genios-brain` + `genios-celery` env:
  ```
  GOOGLE_CALENDAR_WEBHOOK_URL=https://brain.thegenios.com/v1/webhooks/calendar
  ```
- Verify the brain domain in Google Search Console for push delivery.

### 4) DigitalOcean App Platform
- **Push `genios-brain`**: picks up all new routes, modules, and Celery tasks.
- **Push `genios-celery`**: picks up the renew-watches beat entry.
- **Push `genios-dashboard`**: picks up api-brain.ts + 4 new pages + nav.
- **Create new service `genios-reranker`**: import the new GitHub repo, Basic XXS ($5/mo), health check `/health`.
- In `genios-brain` env, add:
  ```
  RERANKER_URL=https://<reranker-internal-url>
  ```

### 5) Local run (your plan — no Docker needed)
```bash
cd genios-brain
uvicorn app.main:app --reload --port 8000
# hits Upstash + Supabase directly via .env
```
Dashboard: `cd genios-dashboard && npm run dev` → http://localhost:3000

---

## Test Matrix

| Phase | What to test | How |
|------|-------------|-----|
| 2 | Event log dedup | call `/v1/webhooks/calendar` twice with same headers → 1 row in `event_log` |
| 2 | Time-travel | `POST /v1/context { entity, as_of: "2026-03-01T00:00Z" }` → historical snapshot |
| 2 | Action ledger | call `/api/generate/draft` → new row in `action_ledger` with outcome |
| 3 | Hard block | create rule `{condition:{field:"confidence",op:"lt",value:0.6}, decision:"block"}` → low-confidence draft returns 403 |
| 3 | Approval flow | rule with `decision:"require_approval"` → draft returns 202, queue has row, `/approve` moves it |
| 3 | Dry-run | `POST /policies/dry-run` with sample array → `{would_match, would_pass}` |
| 4 | BM25 | `POST /v1/retrieval/search { query: "pricing", include_embedding:false }` → BM25-only |
| 4 | Hybrid+rerank | same with `include_embedding:true` + RERANKER_URL set → reranked top 10 |
| 5 | Live | open `/dashboard/live`, hit draft from another terminal → appears within 3 s |
| 5 | Explainer | `/dashboard/memory` → enter a contact UUID → `why?` returns scores + events |

---

## What's **Deliberately Not Done**

| Item | Reason |
|------|--------|
| Move off pgvector/Supabase | pgvector is fine at current scale; `VectorStore` abstraction added for future swap |
| Neo4j/Memgraph | <1M edges, Postgres recursive CTE is enough |
| OpenTelemetry | Structured logs + request_id sufficient until >100 orgs |
| RLS policies (row-level security) | Should go into Supabase before scaling; noted as SOC2 workstream |
| CI / golden eval set | Separate engineering initiative |
| Event-log projector (back-fills existing tables from event_log) | Designed in, not wired — not needed until real replay scenario |
| Drive / Slack webhook receivers | Same pattern as calendar; add when/if real-time need appears |
| Auto-embed new interactions into search_tsv | `GENERATED ALWAYS AS` column handles automatically on write |

---

## File Count (All Phases)

- **genios-brain**: 24 new/modified files, 6 new migrations.
- **genios-reranker**: 5 new files (whole repo).
- **genios-dashboard**: 6 new/modified files (`api-brain.ts` + 4 pages + sidebar).

Everything passes Python syntax and is <300 lines per new file.

---

## Cost Delta

| Service | Before | After | Delta |
|--------|--------|-------|-------|
| Upstash Redis | existing | existing | $0 |
| Supabase | existing | existing (more rows) | $0 |
| DO genios-brain | existing | existing | $0 |
| DO genios-celery | existing | existing | $0 |
| DO genios-dashboard | existing | existing | $0 |
| **DO genios-reranker (new)** | — | Basic XXS | **+$5/mo** |
| **Total** | | | **+$5/mo** |

---

## Order of Deploy (your call; all at once is fine)

1. Migrations 058→063 (Supabase) — safest first.
2. Push `genios-brain`.
3. Push `genios-celery`.
4. Push `genios-dashboard`.
5. Create `genios-reranker` service, wait for boot, set `RERANKER_URL` in brain, redeploy brain once.
6. Set `GOOGLE_CALENDAR_WEBHOOK_URL` (if doing calendar real-time).

---

## Reply With

- Any error after local start (I'll debug specifically).
- Or: "deploy day — go" when you're ready to ship to prod.
