# GeniOS — Brain Upgrade Plan (Phased)

> Phased roadmap from current system → production-grade agent system.
> Each phase = atomic, testable, deployable. Do not start next phase until current one is green.

---

## Ground Rules

1. **No phase exceeds 1 week of work.**
2. **Every phase ships with a test case that proves the new behavior.**
3. **Deploy to staging first, run test, promote to prod.**
4. **If a phase breaks prod, roll back before starting next.**
5. **Skip any phase that doesn't have a real user pain behind it.**

---

## What This Plan Delivers (Honest Scope)

After all phases, GeniOS will be:
- ✅ Reactive (webhook-driven, <5s latency)
- ✅ Coordinated (agents don't duplicate work)
- ✅ Policy-safe (hard gates, not advisory)
- ✅ Inspectable (every decision explainable)
- ✅ Accurate (hybrid retrieval + reranker)
- ✅ Auditable (action ledger + bitemporal memory)

NOT delivered (out of scope, honest):
- ❌ True AGI / "brain"
- ❌ Goal hierarchy / meta-cognition
- ❌ Multi-region / sharded scale (premature)
- ❌ Full test harness / CI (separate initiative)

---

## What's Being Skipped and Why

| Skipped | Why |
|---|---|
| Move off pgvector / Supabase | No accuracy gain at current scale. Abstract interface added, migrate when metrics force it. |
| Dedicated graph DB (Neo4j/Memgraph) | <1M edges. Postgres recursive CTE + incremental updates is enough. |
| OpenTelemetry / distributed tracing | Structured JSON logs + request_id is enough until >100 orgs. |
| Full CI/CD + golden eval set | Separate engineering initiative. Not blocker for upgrades. |
| Multi-agent consensus / telepathy | Blackboard covers 90% of coordination. Consensus is research-grade. |
| PII encryption at rest | SOC2 readiness workstream, not agent-brain workstream. |

---

# PHASE 1 — Coordination + Reactive Core (Week 1)

**Goal:** Agents stop duplicating work. System reacts to events in <5s.

## Changes

| # | Change | Where | Files |
|---|---|---|---|
| 1.1 | **Blackboard** (Redis KV for agent coordination) | genios-brain | `app/coordination/blackboard.py` (~150 lines) |
| 1.2 | **Gmail webhook receiver** (replaces 15-min poll) | genios-brain | `app/ingestion/webhooks/gmail.py` |
| 1.3 | **Calendar webhook receiver** | genios-brain | `app/ingestion/webhooks/calendar.py` |
| 1.4 | **Webhook renewal cron** (Calendar expires 7d) | genios-celery | `app/tasks/renew_watches.py` |

## Setup (external, one-time)

### Upstash Redis
- Already have it. No changes. Blackboard keys use existing instance.
- Verify memory free: if >80% full, upgrade to paid ($10/mo for 1GB).

### Google Cloud Platform (for Gmail + Calendar push)
- [ ] Create GCP project `genios-webhooks` (free)
- [ ] Enable Gmail API + Calendar API
- [ ] Create Pub/Sub topic `gmail-push`
- [ ] Grant `gmail-api-push@system.gserviceaccount.com` publish role on topic
- [ ] Create Pub/Sub subscription pointing to `https://brain.genios.app/webhooks/gmail`
- [ ] Verify webhook endpoint with Google's challenge response

**Time:** ~2 hours GCP console work.
**Cost:** $0 (free tier covers <10GB/mo Pub/Sub traffic).

### DigitalOcean App Platform
- No new services this phase.
- Add env vars to genios-brain: `GCP_PUBSUB_TOPIC`, `WEBHOOK_SECRET`

## Schema Changes (Supabase)

```sql
-- Migration 058_blackboard_audit.sql
CREATE TABLE IF NOT EXISTS agent_activity_log (
  id BIGSERIAL PRIMARY KEY,
  org_id UUID NOT NULL,
  agent_id TEXT NOT NULL,
  contact_id UUID,
  action TEXT NOT NULL,
  status TEXT NOT NULL,
  started_at TIMESTAMPTZ DEFAULT NOW(),
  ended_at TIMESTAMPTZ,
  metadata JSONB
);
CREATE INDEX idx_activity_org_time ON agent_activity_log(org_id, started_at DESC);
```

## Tests to Pass

1. **Blackboard lock test**
   - Two concurrent `POST /api/generate/draft` for same contact → second returns `409 locked_by:agent_xyz`.
2. **Gmail webhook latency test**
   - Reply to a tracked email. Assert interaction row in DB within 10s.
3. **Calendar webhook test**
   - Create event in Google Calendar. Assert `calendar_events` row within 10s.
4. **Renewal cron test**
   - Fast-forward 6 days. Assert watch renewed before expiry.

## Deploy

1. Deploy schema migration to Supabase (SQL editor or CLI).
2. Deploy genios-brain to staging → run 4 tests.
3. Deploy genios-celery (renewal cron).
4. Subscribe user's Gmail/Calendar to webhook via API call.
5. Promote to prod.

## Rollback plan
- Flip feature flag `USE_BLACKBOARD=false` → agents ignore locks.
- Flip `USE_WEBHOOKS=false` → polling resumes.
- Drop migration (schema is additive, safe to leave).

## Success metric
- Agent reaction time p95: **15 min → <10s**
- Duplicate drafts per day: **measure → aim for 0**

---

# PHASE 2 — Memory + Audit (Week 2)

**Goal:** Every fact is versioned. Every action is logged. "As-of" queries possible.

## Changes

| # | Change | Where | Files |
|---|---|---|---|
| 2.1 | **Event log** (immutable, append-only) | genios-brain | `app/memory/event_log.py` |
| 2.2 | **Bitemporal columns** on contacts + interactions | schema | migration |
| 2.3 | **Action ledger** (every agent action logged) | genios-brain | `app/actions/ledger.py` |
| 2.4 | **Time-travel API** `GET /v1/context?as_of=<ts>` | genios-brain | `app/api/context.py` |

## Setup (external)
- None. Pure Postgres + app code.

## Schema Changes

```sql
-- Migration 059_bitemporal.sql
ALTER TABLE contacts ADD COLUMN valid_from TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE contacts ADD COLUMN valid_to TIMESTAMPTZ;
ALTER TABLE interactions ADD COLUMN valid_from TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE interactions ADD COLUMN valid_to TIMESTAMPTZ;

-- Migration 060_event_log.sql
CREATE TABLE event_log (
  id BIGSERIAL PRIMARY KEY,
  org_id UUID NOT NULL,
  source TEXT NOT NULL,          -- gmail / calendar / slack / manual
  verb TEXT NOT NULL,            -- reply / send / update / create
  actor TEXT,
  object_type TEXT,
  object_id TEXT,
  payload JSONB NOT NULL,
  payload_hash TEXT NOT NULL,
  observed_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (payload_hash)
);
CREATE INDEX idx_event_org_time ON event_log(org_id, observed_at DESC);

-- Migration 061_action_ledger.sql
CREATE TABLE action_ledger (
  id BIGSERIAL PRIMARY KEY,
  org_id UUID NOT NULL,
  agent_id TEXT NOT NULL,
  action_type TEXT NOT NULL,     -- draft / send / schedule / log_interaction
  risk_tier TEXT NOT NULL,       -- internal_read/write, external_draft/send, irreversible
  target_ref TEXT,
  payload JSONB,
  policy_match TEXT,
  outcome TEXT,                  -- pending / success / failed / reverted
  reverted_by BIGINT REFERENCES action_ledger(id),
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

## Tests to Pass

1. **Event log dedup test** — post same payload twice, assert only one row.
2. **Time-travel test** — query `as_of=yesterday` returns yesterday's stage, not today's.
3. **Action ledger test** — every draft/send creates a row with risk_tier.
4. **Replay test** — stream event_log through ingestion pipeline → same DB state.

## Deploy
1. Run migrations 059, 060, 061.
2. Deploy genios-brain with dual-write (new writes hit event_log + old tables).
3. Backfill event_log from last 30 days of interactions (one-time script).
4. Enable `as_of` parameter on context API.

## Rollback
- Revert app code → schema additions harmless.
- Disable `as_of` endpoint if misbehaving.

## Success metric
- 100% of new interactions appear in event_log.
- `as_of` query returns correct historical state for 10 sampled contacts.

---

# PHASE 3 — Policy Engine + Hard Gates (Week 3)

**Goal:** Rules become data. Agents can't bypass guardrails.

## Changes

| # | Change | Where | Files |
|---|---|---|---|
| 3.1 | **Policy table + CRUD API** | genios-brain | `app/policy/store.py` |
| 3.2 | **Policy evaluator** (OPA embedded or simple rule interpreter) | genios-brain | `app/policy/engine.py` |
| 3.3 | **Hard enforcement** at action endpoints | genios-brain | `app/api/draft.py`, `writeback.py` |
| 3.4 | **Approval inbox** table + endpoints | genios-brain | `app/api/approvals.py` |

## Setup (external)
- None. Policy engine is embedded (Python library `opa-python` or simple in-house evaluator).

## Schema Changes

```sql
-- Migration 062_policies.sql
CREATE TABLE policy_rules (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL,
  name TEXT NOT NULL,
  action_tier TEXT NOT NULL,      -- external_send, irreversible, etc
  rule_json JSONB NOT NULL,       -- {if: {confidence: {lt: 0.6}}, then: "block"}
  enabled BOOLEAN DEFAULT TRUE,
  version INT DEFAULT 1,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE approvals_queue (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL,
  action_ledger_id BIGINT REFERENCES action_ledger(id),
  status TEXT DEFAULT 'pending',  -- pending / approved / rejected / expired
  reason TEXT,
  approved_by TEXT,
  expires_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

## Tests to Pass

1. **Hard block test** — create rule `block external_send if confidence<0.6` → low-confidence draft returns `403 policy_block`.
2. **Approval flow test** — rule says `require_approval` → action lands in queue → approve → executes.
3. **Policy dry-run test** — submit new policy in shadow mode → report on last 30d traffic.
4. **Rule version test** — edit rule → old version still queryable via `version` field.

## Deploy
1. Run migration 062.
2. Deploy genios-brain with policy enforcement (default: all rules in `warn` mode first week).
3. Flip to `enforce` mode after observing logs.

## Rollback
- Set all rules `enabled=false` → system falls back to existing advisory behavior.

## Success metric
- 0 policy bypasses in action_ledger (all blocks enforced at API).
- Approval queue median resolution time: <30 min.

---

# PHASE 4 — Hybrid Retrieval + Reranker (Week 4)

**Goal:** Accuracy jump. Retrieval actually finds the right answer.

## Changes

| # | Change | Where | Files |
|---|---|---|---|
| 4.1 | **BM25 keyword search** (Postgres full-text) | genios-brain | `app/retrieval/bm25.py` |
| 4.2 | **RRF fusion** of vector + BM25 | genios-brain | `app/retrieval/fuse.py` |
| 4.3 | **BGE reranker** as separate DO service | new repo | `genios-reranker` |
| 4.4 | **`VectorStore` interface abstraction** | genios-brain | `app/retrieval/store.py` |

## Setup (external)

### DigitalOcean App Platform — new service `genios-reranker`
- [ ] Create new App Platform app
- [ ] Basic XS plan: **$12/mo** (1GB RAM)
- [ ] Env vars: `MODEL_NAME=BAAI/bge-reranker-base`
- [ ] Expose internal URL → add to genios-brain env as `RERANKER_URL`
- [ ] Health check: `/health` endpoint

### No other external setup.

## Schema Changes

```sql
-- Migration 063_fulltext.sql
ALTER TABLE interactions ADD COLUMN search_tsv tsvector
  GENERATED ALWAYS AS (to_tsvector('english', coalesce(body,'') || ' ' || coalesce(subject,''))) STORED;
CREATE INDEX idx_interactions_tsv ON interactions USING GIN(search_tsv);
```

## Tests to Pass

1. **BM25 recall test** — exact-phrase query finds interaction that vector missed.
2. **RRF fusion test** — top-10 merged list contains results unique to each method.
3. **Rerank latency test** — end-to-end query <500ms p95 with reranker in path.
4. **Accuracy benchmark** — 50-query gold set: recall@10 jumps from ~65% → ~85%.

## Deploy
1. Run migration 063 (full-text column).
2. Deploy genios-reranker as new DO app.
3. Deploy genios-brain with hybrid retrieval behind feature flag `USE_HYBRID=true`.
4. A/B on 10% of traffic for 3 days.
5. Roll to 100%.

## Rollback
- Flip `USE_HYBRID=false` → falls back to pure vector.

## Success metric
- Retrieval recall@10 (measured on gold set): **>85%**
- Latency p95: **<500ms**
- Cost increase: **+$12/mo** (reranker service).

---

# PHASE 5 — Dashboard Controls + Explainer (Week 5)

**Goal:** Operators can see and tune the system without deploying code.

## Changes

| # | Change | Where | Files |
|---|---|---|---|
| 5.1 | **Live activity page** (reads blackboard + action_ledger) | genios-dashboard | `app/dashboard/live/page.tsx` |
| 5.2 | **Policy editor UI** (form + dry-run) | genios-dashboard | `app/dashboard/policies/page.tsx` |
| 5.3 | **Decision explainer** `GET /contact/{id}/why?field=stage` | genios-brain | `app/api/explain.py` |
| 5.4 | **Approval inbox UI** | genios-dashboard | `app/dashboard/approvals/page.tsx` |
| 5.5 | **Memory inspector** (browse/edit/forget facts per contact) | genios-dashboard | `app/dashboard/memory/page.tsx` |

## Setup (external)
- None. Pure code.

## Tests to Pass

1. **Live page test** — trigger agent → page updates within 2s (SSE or poll).
2. **Policy dry-run test** — edit rule in UI → see impact report before saving.
3. **Explainer test** — "why is Acme COLD?" → returns events, scores, rules fired.
4. **Approval UI test** — pending action appears in inbox, approve → executes.
5. **Forget test** — mark fact as forgotten → next context call excludes it.

## Deploy
1. Deploy genios-brain with explainer endpoint.
2. Deploy genios-dashboard with new pages.
3. Gate with feature flag per-org (roll to beta users first).

## Rollback
- Hide new pages via flag; no schema changes to roll back.

## Success metric
- Operators stop emailing support for "why did it do X" — explainer handles it.
- Time-to-edit-a-rule: **hours (redeploy) → minutes (UI)**.

---

# DEPLOYMENT MATRIX

| Phase | New Services | Schema Migrations | External Setup | Monthly Cost Added |
|---|---|---|---|---|
| 1 | none | 058 | GCP Pub/Sub, webhook subs | **$0** |
| 2 | none | 059, 060, 061 | none | **$0** |
| 3 | none | 062 | none | **$0** |
| 4 | genios-reranker (DO Basic XS) | 063 | none | **$12** |
| 5 | none | none | none | **$0** |
| **Total** | **+1 DO service** | **6 migrations** | **GCP project** | **+$12/mo** |

---

# ORDER OF EXECUTION (strict)

```
Phase 1 → test → deploy → observe 2 days
  ↓
Phase 2 → test → deploy → observe 2 days
  ↓
Phase 3 → test → deploy → warn-mode 3 days → enforce
  ↓
Phase 4 → test → deploy → A/B 3 days → 100%
  ↓
Phase 5 → test → deploy → roll by org
```

**Total time:** ~5 weeks, 1 engineer, sequential.
**Parallelizable:** Phase 4 (reranker service) can start in parallel with Phase 3 if second dev available.

---

# SKIPPED ITEMS (Honest List)

| Item | Reason skipped | Revisit when |
|---|---|---|
| Move to Qdrant / Pinecone | pgvector is fine <5M vectors | p95 query >200ms |
| Neo4j / Memgraph | <1M edges, Postgres handles | >10M edges |
| OpenTelemetry tracing | Structured logs suffice | >100 orgs, ops pain |
| Golden eval set / CI | Separate initiative | After Phase 4 done |
| PII encryption at rest | SOC2 workstream | Enterprise customer asks |
| Multi-region | Single DO region fine | International customers |
| Distributed agents across nodes | One brain process enough | >1000 concurrent agents |
| True meta-cognition / goal hierarchy | Research-grade, not product | Never, for startup scope |

---

# DEFINITION OF DONE (Per Phase)

A phase is DONE only when:
1. ✅ All tests pass in staging
2. ✅ Deployed to prod
3. ✅ Observed 48h with no rollback
4. ✅ Success metric hit (see each phase)
5. ✅ Rollback plan documented and tested once

---

# AWAITING APPROVAL

Before I touch any code:

1. Do you approve this phase order? (Or want to reorder?)
2. Do you want me to start with Phase 1 only, or go through all 5?
3. Is $12/mo for reranker acceptable, or skip Phase 4 reranker service?
4. Is there any skipped item you want moved into scope?

Reply with "go phase 1" (or similar) to start.
