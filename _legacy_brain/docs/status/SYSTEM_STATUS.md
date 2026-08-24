# GeniOS — System Status

**Last updated:** 2026-04-22  
**Source of truth for:** what exists, what works, what's wired but off, what's blocked.  
**Also read:** [PHASE_DEVIATIONS.md](PHASE_DEVIATIONS.md) — every plan-vs-reality delta with reasons.

---

## At a Glance

| Area | Status |
|---|---|
| Backend API (FastAPI) | ✅ All routes live |
| 9 data source integrations | ✅ Gmail, Calendar, Slack, Jira, Notion, Sheets, Drive, Docs, HubSpot |
| Context pull `/v1/context` | ✅ 3-layer fallback, <400ms SLA |
| Brain / anomaly detection | ✅ 48 detectors, but DISABLED (flag off) |
| LLM routing | ⚠️ Groq only — Anthropic wired but no key |
| Policy engine | ✅ Rules, approvals, enforcement |
| Audit trail | ✅ Event log + action ledger (immutable) |
| Dashboard (Next.js) | ✅ 5 pages including live feed, policies, approvals |
| MCP server | ✅ 10 tools for Claude |
| SDKs (Python + Node) | ✅ Feature-complete, NOT published |
| Celery / background jobs | ✅ Wired, needs deploy config change |
| Observability | ⚠️ Sentry + logs only — no alerting |
| Deployment | ❌ Local only, not yet on DigitalOcean |

---

## Codebase Map

```
genios/
├── genios-brain/        FastAPI backend + Celery workers (Python)
├── genios-dashboard/    Next.js frontend (React/TypeScript)
├── genios-mcp/          MCP server for Claude (Node.js, 10 tools)
├── genios-python/       Python SDK v1.1.0 (not published)
├── genios-node/         Node.js SDK v1.1.0 (not published)
├── genios-email-agent/  Standalone Gmail CLI assistant
├── genios-reranker/     Cross-encoder reranking microservice
├── ops/                 Runbooks, load tests, legal drafts, audit scope
├── scripts/             Utility scripts
└── .github/workflows/   CI: lint, audit, migration safety checks
```

---

## Backend — `genios-brain`

**Stack:** FastAPI + Uvicorn | Supabase Postgres + pgvector | Upstash Redis | Celery | Groq + Gemini

### API Routes (all live)

| Endpoint | Purpose |
|---|---|
| `POST /v1/agent` | Register agent |
| `GET /v1/contacts` | Search contacts with filters |
| `GET /v1/context` | Pull relationship context bundle for a contact |
| `POST /v1/feedback` | Log outcome of context use |
| `GET /v1/sync` | Sync status for all connected data sources |
| `GET /v1/org` | Org profile, plan, usage |
| `POST /v1/documents/upload` | Upload PDFs for extraction |
| `GET /v1/stream/recommendations` | SSE stream of proactive insights |
| `POST /v1/admin/delete` | GDPR data deletion (dry_run=true safe mode) |
| `GET /v1/admin/aar` | Annual Active Rate metric |
| `POST /api/org/{org}/policies` | Policy CRUD |
| `POST /api/org/{org}/policies/dry-run` | Test a rule without enforcing |
| `GET /api/org/{org}/approvals` | Pending/approved/rejected decisions |
| `GET /api/org/{org}/live` | Real-time activity (blackboard + ledger) |
| `GET /api/org/{org}/contacts/{id}/why` | Explainability: why is this score/stage set? |
| `POST /api/draft` | Draft email/message with policy enforcement |
| `POST /webhooks/gmail` | Gmail push notifications |
| `POST /webhooks/calendar` | Calendar push notifications |

### Context Pull — 3-Layer Fallback (Apr 20 architecture)

Every `/v1/context` call goes through these in order, 400ms hard deadline:

1. **Layer 1 — Precomputed bundles** (Postgres `precomputed_bundles`, 24h TTL)  
   Indexed on `(org_id, contact.name OR contact.email)`. Rebuilt event-driven via `task_refresh_bundle` (Celery, high_priority queue). Nightly full-refresh as floor.

2. **Layer 2 — Redis cache** (60s TTL, situation-keyed)  
   Catches repeated pulls with the same agent + prompt within 1 minute.

3. **Layer 3 — Minimal real bundle** (`app/context/minimal_bundle.py`)  
   Single SQL: contact row + last 3 interactions. Returns real data (name, stage, sentiment, recent summaries). Same response shape as Layer 1 so agents need one parser. Target <150ms. Enqueues `task_refresh_bundle` so Layer 1 populates for next call.

4. **Unknown entity → 404 `ENTITY_NOT_FOUND`** (honest; was previously empty 200).

### LLM Routing

| Purpose | Current routing | What it should be |
|---|---|---|
| `reason_haiku` | Groq (Llama 3.3-70B) | Anthropic claude-haiku-4-5-20251001 |
| `reason_sonnet` | Groq (Llama 3.3-70B) | Anthropic claude-sonnet-4-6 |
| `narrative` | Groq (Llama 3.3-70B) | Anthropic claude-haiku-4-5-20251001 |
| `embed` | Gemini embedding-001 | (no change planned) |
| `chat` | Gemini / Groq fallback | (no change planned) |

**To activate Anthropic (Phase 1.5 — ~5 min work):**
1. Set `ANTHROPIC_API_KEY` + `GENIOS_ANTHROPIC_ENABLED=true` in `.env`
2. `pip install anthropic==0.39.0` and add to `requirements.txt`
3. Flip 3 entries in `app/llm/client.py` `ROUTES` dict (see `PHASE_DEVIATIONS.md` Phase 1.5 checklist)

### Feature Flags (all false by default)

| Flag | What it enables | When to flip |
|---|---|---|
| `GENIOS_ANTHROPIC_ENABLED` | Anthropic LLM routing | When Anthropic API key arrives |
| `GENIOS_REASONER_ENABLED` | Phase 2 brain router (48 detectors active) | After Phase 2 validation on canary |
| `GENIOS_CASCADE_ENABLED` | Haiku→Sonnet escalation in cascade.py | Phase 3 stable + Anthropic active |
| `GENIOS_CALIBRATION_ENABLED` | Per-tenant Platt scaling for confidence | When tenant has ≥50 labeled outcomes |

---

## Integrations (all 9 implemented)

| Source | Connector | Bridge | Sync Task | Auth |
|---|---|---|---|---|
| Gmail | `gmail_connector.py` | `email_parser.py` | `gmail_sync.py` | OAuth 2.0, history_id incremental |
| Google Calendar | `calendar_connector.py` | `calendar_bridge.py` | `calendar_sync.py` | OAuth 2.0, syncToken |
| Google Drive | `drive_connector.py` | `drive_bridge.py` | `drive_sync.py` | OAuth 2.0, with PDF extraction |
| Google Docs | `docs_connector.py` | `docs_bridge.py` | `docs_sync.py` | OAuth 2.0 |
| Google Sheets | `sheets_connector.py` | `sheets_bridge.py` | `sheets_sync.py` | OAuth 2.0 |
| Slack | `slack_connector.py` | `slack_bridge.py` | `slack_sync.py` | OAuth 2.0, messages + threads |
| Jira | `jira_connector.py` | `jira_bridge.py` | `jira_sync.py` | OAuth 2.0, issues + comments |
| Notion | `notion_connector.py` | embedded | `notion_sync.py` | OAuth 2.0, pages + databases |
| HubSpot | `hubspot_connector.py` | `hubspot_bridge.py` | `hubspot_sync.py` | OAuth 2.0, contacts + deals |

All sync state stored in `oauth_tokens` table. Ingestion flow: sync → classify (broadcast detection) → LLM entity extraction → graph merge → store.

---

## Database

**76 migrations applied.** Latest: `076_interaction_contact_role.sql` (Apr 22).

### Key tables

| Table | Purpose |
|---|---|
| `orgs` | Tenant isolation (RLS enabled) |
| `contacts` | Graph nodes — stage, sentiment, company, segments |
| `interactions` | Email/calendar/message events with embeddings |
| `commitments` | Bidirectional action items with confidence |
| `facts` | Extracted entities — 13 type taxonomy with CHECK constraint |
| `precomputed_bundles` | Cached `/v1/context` responses (24h TTL) |
| `recommendations` | Proactive insights from brain router |
| `insights` | Generated insights with webhook delivery |
| `delivery_attempts` | Webhook retry tracking with consecutive failure counts |
| `event_log` | Immutable audit trail (SHA-256 dedup) |
| `action_ledger` | Every agent action with risk tier + reversal tracking |
| `approvals_queue` | Policy gate: pending/approved/rejected |
| `policy_rules` | DSL rules (eq, gt, regex, all, any, not) |
| `contact_baselines` | 90-day rolling stats per contact |
| `contact_anomalies` | Z-score anomaly flags |
| `context_calls` | Audit log of every `/v1/context` call |
| `companies` | Auto-extracted from email domains |

**Vector embeddings:** interactions at 1536-dim (Gemini), chunks at 768-dim.  
**Multi-tenant:** RLS policies enabled on all tables (migration 053b).  
**Migrations rule:** additive-only enforced via CI (`migration_safety.yml`).

---

## Background Jobs (Celery + Redis Streams)

### Celery tasks (scheduled via beat)

| Task | What it does |
|---|---|
| Gmail/Calendar/Slack/Jira/Notion/Sheets/Drive/Docs/HubSpot sync | Incremental data pulls per org |
| `task_refresh_bundle` | Per-contact precomputed bundle rebuild (high_priority) |
| `task_brain_router` | Phase 2 brain tick — reads Redis Streams, routes detectors (brain_router queue) |
| Nightly `_precompute_bundles` | Full bundle rebuild for all contacts |
| Webhook dispatcher | Retry delivery_attempts with 30s→24h backoff |
| Proactive scanner | Anomaly detection + insight generation |

### ⚠️ Deploy-time change required for brain router

```bash
# Current worker command (missing brain_router)
celery -A app.celery_app worker -Q high_priority,low_priority

# Must change to
celery -A app.celery_app worker -Q high_priority,low_priority,brain_router
```

Without this, Phase 2 brain router never runs even after `GENIOS_REASONER_ENABLED=true`.

### Redis key map (Upstash)

| Key | Purpose | TTL |
|---|---|---|
| `genios:events:fact` (stream) | Event bus for brain router | MAXLEN ~100k |
| `brain:debounce:{org}:{entity}` | Router batching window | 30s |
| `dedup:{org}:{type}:{subject}` | Gate 24h dedup | 24h |
| `push_budget:{org}:{date}` | Daily LLM cost cap per org | 24h |
| `bundle_refresh_guard:{org}:{contact}` | Storm guard: one rebuild per 10s | 10s |
| Celery broker (DB 1) | Task queue | — |
| App cache (DB 0) | Context + situation cache | varies |

---

## Brain / Intelligence

### Phase 2 Brain Router (currently DISABLED)

- 48 detector functions in `app/brain/` (anomaly, sentiment drift, engagement loss, cooling relationships, etc.)
- 5-second beat tick reads Redis Streams `genios:events:fact`
- Debounces 30s windows per `(org_id, entity_id)`, batches candidates → reasoner → scorer → gate → log
- Enqueues `task_refresh_bundle` per debounced entity (precomputed bundles stay fresh)
- **Enable:** `GENIOS_REASONER_ENABLED=true` + `brain_router` queue on worker

### Phase 3 Learning Loop (built, partially disabled)

- Cascade (`cascade.py`): Haiku → Sonnet escalation, `GENIOS_CASCADE_ENABLED=false`
- Narrative generation: routes through `purpose="narrative"` → currently Groq
- Policy engine: DSL rule evaluator, full CRUD, dry-run, approval gates — **all live**
- Action ledger enforcement: every agent action logged with risk tier — **all live**

### Phase 4 Correctness

- Hybrid retrieval: BM25 + pgvector + RRF + cross-encoder reranking — **live**
- Calibration (`GENIOS_CALIBRATION_ENABLED=false`): activates per tenant at ≥50 labeled outcomes
- Anomaly detection: Z-score vs 90-day baseline — **live** (feeds insights even when brain router off)
- Fact taxonomy: 13 standardized types with Postgres CHECK constraint — **live**

---

## MCP Server (`genios-mcp`)

10 tools, Node.js, stdio transport. Active in Claude Code sessions.

| Tool | What it does |
|---|---|
| `genios_search_contacts` | Find contacts by name/email/company/stage/filters |
| `genios_get_context` | Full relationship memory + intelligence for a contact |
| `genios_list_segments` | List contact groups |
| `genios_get_segment_members` | Contacts in a segment |
| `genios_org_info` | Org profile, plan, usage, graph totals |
| `genios_list_insights` | Anomalies, cooling relationships, overdue items |
| `genios_log_interaction` | Write-back: log outbound email/call/meeting |
| `genios_log_outcome` | Feedback: was context useful? (positive/negative/neutral) |
| `genios_trigger_scan` | Manual proactive scan |
| `genios_sync_status` | Sync state of all data sources |

---

## Dashboard (`genios-dashboard`)

**Stack:** Next.js + React 19 + TypeScript + Tailwind CSS + D3

| Page | What it shows |
|---|---|
| `/dashboard` | Contact graph visualization + search |
| `/dashboard/live` | Real-time activity feed (3s polling) |
| `/dashboard/policies` | Policy rule CRUD + dry-run UI |
| `/dashboard/approvals` | Pending/approved/rejected approval inbox |
| `/dashboard/memory` | "Why is this field this value?" inspector |
| `/dashboard/insights` | Proactive anomalies + outcomes |
| `/settings` | Org settings, API keys, sync status |

---

## SDKs

Both fully functional, not published.

| SDK | Package name | Features | Blocker |
|---|---|---|---|
| Python (`genios-python/`) | `genios` | Retries, idempotency, webhook verify, async SSE | No PyPI token |
| Node.js (`genios-node/`) | `@genios/sdk` | Same + TypeScript types | No npm token |

Publish trigger: first external consumer wants `pip install` / `npm install`.

---

## Supporting Services

### Reranker (`genios-reranker`)
- Jina reranker v1 turbo (cross-encoder)
- `POST /rerank` endpoint
- Deployed on DigitalOcean App Platform (Basic XXS, $5/mo)
- Improves retrieval recall ~65% → ~85%
- **Status: ✅ Running**

### Email Agent (`genios-email-agent`)
- Standalone CLI: Gmail OAuth, RAG-based drafting, 3 safety guardrails
- Draft-first (no auto-send), learns from user edits
- **Status: ✅ Functional, runs locally**

---

## CI/CD

| Workflow | Trigger | What runs |
|---|---|---|
| `ci.yml` | PR / push to main | ruff lint, syntax check, unit tests, pip-audit, npm audit |
| `migration_safety.yml` | PR changes `migrations/*.sql` | Validates additive-only (no DROP/DELETE/TRUNCATE) |

Integration tests (`test_api_core.py`) are commented out in CI — need a test database.

---

## Test Coverage

18 test files. Unit tests pass. Integration tests need Postgres + Redis.

| Test | Status |
|---|---|
| `test_tunables.py` — config, broadcast detection | ✅ Passing in CI |
| `test_brain.py` — scorer/gate/reasoner | ✅ Unit |
| `test_phase3.py` — policy engine, approvals | ✅ Unit |
| `test_phase4.py` — calibration, reranking | ✅ Unit |
| `test_llm_client.py` — routing, fallback | ✅ Unit |
| `test_api_core.py` — integration tests | ⚠️ Commented in CI (needs DB) |
| `test_rls.py` — row-level security | ⚠️ Needs DB |
| Harness `t01–t17` — entity extraction, latency, PII, noise | ✅ Runnable locally |

---

## What's Not Working / Blocked / Deferred

### Blocked on external keys/accounts

| Item | What's blocked | Fix |
|---|---|---|
| Anthropic key | `reason_haiku`, `reason_sonnet`, `narrative` routing; Phase 3 cascade | Phase 1.5 checklist (5 min once key arrives) |
| PyPI token | Python SDK publication | Create PyPI account + token → `twine upload` |
| npm token | Node SDK publication | Create npm account + token → `npm publish` |
| Grafana account | Observability alerts (20 rules written, nowhere to send) | Sign up free tier |
| DigitalOcean deployment | Everything only runs locally | Follow `ops/launch_checklist.md` |

### Built but switched off (feature flags)

| Thing | Flag | When on |
|---|---|---|
| Brain router (48 detectors) | `GENIOS_REASONER_ENABLED=false` | After Phase 2 canary validation |
| Haiku→Sonnet cascade | `GENIOS_CASCADE_ENABLED=false` | After Phase 3 stable + Anthropic key |
| Per-tenant confidence calibration | `GENIOS_CALIBRATION_ENABLED=false` | Per tenant at ≥50 labeled outcomes |

### Deferred (tracker from PHASE_DEVIATIONS.md)

| # | Item | Trigger |
|---|---|---|
| A/B | Flip to Anthropic LLM | Anthropic key arrives |
| C | Enable cascade | Phase 3 stable + 2 weeks |
| D | Enable reasoner on canary tenant | ≥0.80 manual precision on 100 candidates |
| E | Remove `/v1/outcome` alias | SDK 1.0 adoption ≥90% |
| H | Add `brain_router` to worker `-Q` | First deploy |
| R | Full observability stack (OTel + Prometheus + Grafana) | First un-debuggable prod incident or >25 tenants |
| S | Wire 20 alert rules | Item R lands |
| T | Publish SDKs to PyPI + npm | First external consumer |
| U | Status page at status.genios.ai | Public launch |
| V | Pen test vendor | Pre-GA security sign-off |
| W | Legal counsel (ToS, DPA) | First paid customer or SOC 2 start |
| X | Recruit 3–5 beta design partners | Code ready, outreach is manual |

---

## Known Bugs Fixed (Apr 18–22)

| Bug | What was wrong | Fixed |
|---|---|---|
| `POST /v1/segment` 500 | SQLAlchemy 2.0 + psycopg2 `:name::type` cast unsubstituted | `CAST(:x AS jsonb)` |
| Gmail webhook 500 | Same `:config::jsonb` cast in `webhooks.py` | Same fix |
| Email-based context pulls always hit Layer 3 | `precomputed_bundles` JOIN only matched `c.name`, not `c.email` | OR condition added |
| Degraded vs success shape mismatch | Different field names (`confidence` vs `confidence_score`), entity as string vs dict | Unified to one schema; `confidence_score` kept as deprecated alias (item Y) |
| Cold pull storm | N concurrent cold pulls spawned N identical builds | `SETNX bundle_refresh_guard` 10s per contact |
| `/v1/agents/session/{start,end}` no auth | Took `org_id` in body with no key verification | `verify_api_key` now required |
| `/v1/context/entity/{entity_id}` 500 on bad input | psycopg2 UUID cast error on non-UUID input | Validate before query → clean 404 |

---

## Environment Variables

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | ✅ | Supabase Postgres |
| `REDIS_URL` | ✅ | Upstash Redis |
| `GROQ_API_KEY` | ✅ | Llama 3.3 (current primary LLM) |
| `GEMINI_API_KEY` | ✅ | Embeddings + chat fallback |
| `GOOGLE_CLIENT_ID/SECRET` | ✅ | OAuth for Gmail, Calendar, Drive, Sheets, Docs |
| `SLACK_CLIENT_ID/SECRET` | ✅ | Slack OAuth |
| `JIRA_CLIENT_ID/SECRET` | ✅ | Jira OAuth |
| `NOTION_CLIENT_ID/SECRET` | ✅ | Notion OAuth |
| `HUBSPOT_CLIENT_ID/SECRET` | ✅ | HubSpot OAuth |
| `ANTHROPIC_API_KEY` | ⚠️ pending | Phase 1.5 (set dummy for now) |
| `GENIOS_ANTHROPIC_ENABLED` | — | `false` until key arrives |
| `GENIOS_REASONER_ENABLED` | — | `false` until canary validation |
| `GENIOS_CASCADE_ENABLED` | — | `false` until Anthropic + stable |
| `GENIOS_CALIBRATION_ENABLED` | — | `false` until ≥50 outcomes |
| `GENIOS_LLM_DAILY_CAP_USD` | — | Default 50.0 |
| `GENIOS_PULL_DEADLINE_MS` | — | Default 400 |
| `SENTRY_DSN` | — | Error tracking |

---

## Deployment Target (not yet live)

```
Cloudflare DNS
  └─→ Load Balancer
        ├─→ API ×2         (DO App Platform)
        ├─→ Dashboard      (DO App Platform / Vercel)
        ├─→ Reranker       (DO App Platform — already live)
        └─→ Celery workers (DO Droplet)
              ├─→ Supabase Postgres
              └─→ Upstash Redis
```

**Pre-deploy checklist:** `ops/launch_checklist.md` (50+ items).  
**Load test scripts:** `ops/load_tests/` (k6, runnable once staging is up).

---

## What to Do Next

1. **Get Anthropic API key** → run Phase 1.5 checklist (5 min, unlocks cascade + proper LLM routing)
2. **Deploy to DigitalOcean** → follow `ops/launch_checklist.md`, add `brain_router` to worker queues
3. **Enable brain router on one canary org** → `GENIOS_REASONER_ENABLED=true` per tenant
4. **Recruit 3–5 beta design partners** → code ready, outreach is manual (item X)
5. **Set up Grafana** → create free account, wire 20 alert rules (item R → S)
