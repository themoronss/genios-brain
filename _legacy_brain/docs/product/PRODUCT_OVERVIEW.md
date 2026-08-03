# GeniOS — Product & Engineering Overview

**Last updated:** 2026-04-26
**Audience:** Technical product reviewer (verifying scope, design, and current state)
**One-liner:** GeniOS is a tenant-scoped *relationship brain* — it ingests work data (email, calendar, Slack, Jira, Notion, Sheets, Drive, Docs, HubSpot), builds a contact graph with bi-temporal memory, and serves agents (Claude, in-app, SDKs, MCP) a `<400ms` context bundle plus proactive insights, all gated by a policy engine and an immutable audit trail.

> **Note:** GeniOS is positioned as a **brain** (judgment + learning + proactive), not a memory store. Reviewers should evaluate it on those criteria, not on CRUD.

---

## 1. System at a glance

```
┌──────────────────────────────────────────────────────────────────────┐
│                          USER / AGENT SURFACE                       │
│  Dashboard (Next.js 16) │ MCP Server (10 tools) │ Python+Node SDKs  │
│              Email Agent (CLI) │ Webhooks / SSE                     │
└───────────┬───────────────────────────────┬──────────────────────────┘
            │ REST + SSE                    │ stdio / OAuth
            ▼                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      genios-brain (FastAPI)                          │
│  /v1/* contracts │ Policy gate │ Action ledger │ Event log          │
│  3-layer context fallback (Precomputed → Redis → Minimal real)      │
└─┬────────────────────────────┬─────────────────────────┬────────────┘
  │                            │                         │
  ▼                            ▼                         ▼
┌──────────────┐   ┌────────────────────────┐   ┌──────────────────┐
│ Postgres +   │   │  Celery workers        │   │ LLM Router       │
│ pgvector     │   │  - Sync (9 sources)    │   │  Groq (live)     │
│ (Supabase)   │◀─▶│  - Brain router (off)  │◀─▶│  Gemini (embed)  │
│ 78 migrations│   │  - Bundle refresh      │   │  Anthropic (off) │
│ RLS enabled  │   │  - Proactive scanner   │   │  Reranker (DO)   │
└──────────────┘   └────────────────────────┘   └──────────────────┘
                              ▲
                              │
                       Upstash Redis
                  (streams + cache + dedup)
```

---

## 2. Repository map (verified against source)

```
genios/
├── genios-brain/          FastAPI + Celery (Python)         ← core
├── genios-dashboard/      Next.js 16 + React 19             ← UI
├── genios-mcp/            MCP server, 10 tools (Node)       ← Claude bridge
├── genios-python/         Python SDK v1.1.0 (unpublished)
├── genios-node/           Node SDK v1.1.0 (unpublished)
├── genios-email-agent/    Standalone Gmail RAG CLI
├── genios-reranker/       Cross-encoder rerank service (live on DO)
├── ops/                   Runbooks, load tests, audit scope
├── scripts/, deploy/      Tooling
└── *.md                   System docs (SYSTEM_DESIGN, PHASE_DEVIATIONS, …)
```

---

## 3. Backend — `genios-brain`

**Stack:** FastAPI · Uvicorn · SQLAlchemy 2.0 · Supabase Postgres + pgvector · Upstash Redis · Celery · Sentry · Groq + Gemini (+ Anthropic gated)

### 3.1 Module layout (`genios-brain/app/`)

| Module | Responsibility |
|---|---|
| [api/routes/](genios-brain/app/api/routes/) | 40+ FastAPI routers (v1 contract + admin + webhooks) |
| [ingestion/](genios-brain/app/ingestion/) | 9 connectors + 8 bridges + classifier + entity resolver |
| [graph/](genios-brain/app/graph/) | Contact graph: scorer, embedder, communities, signals, intelligence |
| [retrieval/](genios-brain/app/retrieval/) | Hybrid retrieval — BM25 + pgvector + RRF fuse + rerank |
| [context/](genios-brain/app/context/) | Bundle compiler, situation embedder, precedent search, cache |
| [brain/](genios-brain/app/brain/) | Router, candidates, reasoner, scorer, gate, cascade, calibration, narrative |
| [policy/](genios-brain/app/policy/) | DSL engine + store + enforcement |
| [actions/](genios-brain/app/actions/) | Immutable action ledger |
| [memory/](genios-brain/app/memory/) | Bi-temporal `as_of` queries + event log |
| [coordination/](genios-brain/app/coordination/) | Multi-agent blackboard |
| [lifecycle/](genios-brain/app/lifecycle/) | Stage state machine |
| [llm/](genios-brain/app/llm/) | Provider router, cost tracker |
| [tasks/](genios-brain/app/tasks/) | 30+ Celery jobs (sync / brain / scanners / digests) |

Hard rule per project standards: **files <300 lines**, no abstraction beyond what's needed.

### 3.2 API surface (live)

All under FastAPI app declared in [genios-brain/app/main.py](genios-brain/app/main.py).

**Public v1 contract (used by SDKs + MCP):**

| Method · Path | Purpose |
|---|---|
| `POST /v1/agent` | Register / heartbeat an agent session |
| `GET  /v1/contacts` | Search by name / email / company / stage / segment |
| `GET  /v1/context` | **The hot path** — 400ms relationship bundle |
| `POST /v1/feedback` | Outcome of a context use (positive/negative/neutral) |
| `GET  /v1/sync` | Sync status across all 9 connectors |
| `GET  /v1/org` | Org profile, plan, usage, graph totals |
| `POST /v1/documents/upload` | PDF/DOCX upload → chunk → embed |
| `GET  /v1/stream/recommendations` | SSE stream of brain insights |
| `POST /v1/admin/delete` | GDPR deletion (`dry_run=true` default) |
| `GET  /v1/admin/aar` | Annual active rate metric |

**Org-scoped operator surface (used by dashboard):**
`/api/org/{org}/policies` (CRUD + `/dry-run`) · `/approvals` · `/live` · `/contacts/{id}/why` (explainability) · `/draft` (policy-gated drafting) · webhook receivers `/webhooks/gmail` and `/webhooks/calendar`.

### 3.3 Hot-path: `/v1/context` — 3-layer fallback

Every call has a **400ms hard deadline** (`GENIOS_PULL_DEADLINE_MS`). Implemented in [app/context/](genios-brain/app/context/):

1. **Layer 1 — Precomputed bundles** (Postgres `precomputed_bundles`, 24h TTL).
   Indexed on `(org_id, contact.name OR contact.email)` — both because email-only lookups previously missed Layer 1. Rebuilt **event-driven** via `task_refresh_bundle` on the `high_priority` Celery queue. Nightly full refresh as a floor.
2. **Layer 2 — Redis cache** (60s, situation-keyed) — catches repeated agent pulls.
3. **Layer 3 — Minimal real bundle** ([minimal_bundle.py](genios-brain/app/context/minimal_bundle.py)).
   One SQL: contact row + last 3 interactions. Real data (stage, sentiment, summaries), same response shape as Layer 1, target <150ms. Enqueues `task_refresh_bundle` so the next call is hot.
4. **Unknown entity → `404 ENTITY_NOT_FOUND`** (honest; previously returned empty 200).

Cold-pull storms are guarded by `SETNX bundle_refresh_guard:{org}:{contact}` (10s) so N concurrent misses don't fan out into N rebuilds.

### 3.4 LLM routing — current vs. target

Implemented in [app/llm/client.py](genios-brain/app/llm/client.py). Switching is a flag flip, not a rewrite.

| Purpose | Today | Target (when `ANTHROPIC_API_KEY` arrives) |
|---|---|---|
| `reason_haiku` | Groq Llama 3.3-70B | Anthropic `claude-haiku-4-5-20251001` |
| `reason_sonnet` | Groq Llama 3.3-70B | Anthropic `claude-sonnet-4-6` |
| `narrative` | Groq | Anthropic Haiku |
| `embed` | Gemini `embedding-001` (768-dim) | unchanged |
| `chat` | Gemini → Groq fallback | unchanged |

Per-org daily cap: `GENIOS_LLM_DAILY_CAP_USD` (default $50) tracked via `push_budget:{org}:{date}` Redis key.

### 3.5 Feature flags (all default `false`)

| Flag | Unlocks | Trigger to flip |
|---|---|---|
| `GENIOS_ANTHROPIC_ENABLED` | Anthropic LLM routing | Anthropic key arrives |
| `GENIOS_REASONER_ENABLED` | Phase-2 brain router (48 detectors) | ≥0.80 manual precision on 100 candidates (canary) |
| `GENIOS_CASCADE_ENABLED` | Haiku→Sonnet escalation | Phase 3 stable + Anthropic on |
| `GENIOS_CALIBRATION_ENABLED` | Per-tenant Platt scaling | Tenant has ≥50 labeled outcomes |

---

## 4. Integrations (all 9 wired end-to-end)

Each source has **connector → bridge → sync task → graph merge**. Files in [genios-brain/app/ingestion/](genios-brain/app/ingestion/) and [genios-brain/app/tasks/](genios-brain/app/tasks/).

| Source | Connector | Bridge | Sync task | Auth & incrementality |
|---|---|---|---|---|
| Gmail | `gmail_connector.py` | `email_parser.py` | `gmail_sync.py` | OAuth 2.0, `history_id` deltas |
| Google Calendar | `calendar_connector.py` | `calendar_bridge.py` | `calendar_sync.py` | OAuth 2.0, `syncToken` |
| Google Drive | `drive_connector.py` | `drive_bridge.py` | `drive_sync.py` | OAuth 2.0, PDF text extraction |
| Google Docs | `docs_connector.py` | `docs_bridge.py` | `docs_sync.py` | OAuth 2.0 |
| Google Sheets | `sheets_connector.py` | `sheets_bridge.py` | `sheets_sync.py` | OAuth 2.0 |
| Slack | `slack_connector.py` | `slack_bridge.py` | `slack_sync.py` | OAuth 2.0, channels + threads |
| Jira | `jira_connector.py` | `jira_bridge.py` | `jira_sync.py` | OAuth 2.0, issues + comments |
| Notion | `notion_connector.py` | embedded | `notion_sync.py` | OAuth 2.0, pages + DBs |
| HubSpot | `hubspot_connector.py` | `hubspot_bridge.py` | `hubspot_sync.py` | OAuth 2.0, contacts + deals |

**Common ingestion pipeline:** `sync → email_classifier (broadcast/transactional/personal) → entity_extractor (LLM) → entity_resolver (fuzzy match) → graph_builder → segment_assigner → store + Redis stream event`.

OAuth tokens live in `oauth_tokens` (one row per `account_email`, prefixed `gcal:`, `slack:`, …). Health checked nightly by [tasks/oauth_healthcheck.py](genios-brain/app/tasks/oauth_healthcheck.py).

---

## 5. Database

**78 migrations** applied (last: `078_marketing_awareness.sql`). Migrations are **additive-only**, enforced by [.github/workflows/migration_safety.yml](.github/workflows/migration_safety.yml) (no `DROP/DELETE/TRUNCATE`).

### Key tables

| Table | Why it exists |
|---|---|
| `orgs` | Tenant root; **RLS enabled** on all dependent tables (mig 053b) |
| `contacts` | Graph node — stage, sentiment, company, segments |
| `interactions` | Email/cal/msg events with embeddings (1536-dim Gemini, 768-dim chunks) |
| `commitments` | Bi-directional action items with confidence |
| `facts` | Extracted entities — **13-type taxonomy** with CHECK constraint |
| `companies` | Auto-extracted from email domains |
| `precomputed_bundles` | Layer-1 cache for `/v1/context` (24h TTL) |
| `recommendations` | Brain-router output (payload v2) |
| `insights` | Surfaceable insights with webhook delivery |
| `delivery_attempts` | Webhook retries — 30s → 24h backoff, consecutive-failure tracking |
| `event_log` | **Immutable audit** — SHA-256 dedup |
| `action_ledger` | Every agent action with risk tier + reversal pointer |
| `approvals_queue` | Policy gate state — pending/approved/rejected |
| `policy_rules` | DSL rules: `eq, gt, regex, all, any, not` |
| `contact_baselines` / `contact_anomalies` | 90-day rolling stats + Z-score flags |
| `context_calls` | Audit log of every `/v1/context` (for "why?" answers) |
| `llm_usage` | Per-call cost + tokens per org |
| `calibration_models` | Per-tenant Platt scaling weights |

---

## 6. Background jobs (Celery + Redis Streams)

Defined in [genios-brain/app/celery_app.py](genios-brain/app/celery_app.py) and [tasks/](genios-brain/app/tasks/).

| Job | Purpose |
|---|---|
| 9 sync tasks | Per-tool incremental pulls (cron + on-demand) |
| `task_refresh_bundle` | Per-contact precomputed bundle rebuild (high_priority) |
| `task_brain_router` | 5s tick, reads `genios:events:fact` stream → debounce → reasoner → scorer → gate → log (brain_router queue, **disabled**) |
| Nightly `_precompute_bundles` | Full bundle rebuild floor |
| Webhook dispatcher | Retries `delivery_attempts` with backoff |
| Proactive scanner | Anomaly detection + insight emit |
| Morning digest / weekly report | Batch insight delivery |
| Auto-merge | Duplicate contact resolution |
| Confidence updater · score writer | Periodic recompute |

### ⚠️ Deploy-time gotcha

```bash
# Won't run brain router:
celery -A app.celery_app worker -Q high_priority,low_priority

# Required:
celery -A app.celery_app worker -Q high_priority,low_priority,brain_router
```

### Redis (Upstash) key map

| Key | Purpose | TTL |
|---|---|---|
| `genios:events:fact` (stream) | Event bus → brain router | MAXLEN ~100k |
| `brain:debounce:{org}:{entity}` | Router batching | 30s |
| `dedup:{org}:{type}:{subject}` | Gate de-duplication | 24h |
| `push_budget:{org}:{date}` | Per-org LLM cost cap | 24h |
| `bundle_refresh_guard:{org}:{contact}` | Storm guard | 10s |
| Celery broker (DB 1) | Task queue | — |
| App cache (DB 0) | Context + situation | varies |

---

## 7. Brain / intelligence layer

### 7.1 Phase 2 — Brain Router (built, **off**)

- 48 detector functions in [app/brain/](genios-brain/app/brain/) (sentiment drift, engagement loss, cooling relationships, anomaly, etc.)
- 5s beat tick reads `genios:events:fact`
- Debounces 30s windows per `(org_id, entity_id)`, batches → reasoner → scorer → gate → ledger
- Re-enqueues `task_refresh_bundle` so precomputed bundles stay fresh
- **Enable:** `GENIOS_REASONER_ENABLED=true` + `brain_router` queue on worker

### 7.2 Phase 3 — Learning loop (built, partial)

- Cascade ([brain/cascade.py](genios-brain/app/brain/cascade.py)): Haiku→Sonnet escalation — flag-gated
- Narrative generation: routed via `purpose="narrative"`
- **Policy engine — fully live**: DSL evaluator + CRUD + dry-run + approval gates
- **Action ledger — fully live**: every agent action captured with risk tier

### 7.3 Phase 4 — Correctness (live)

- Hybrid retrieval: BM25 + pgvector + RRF fuse + cross-encoder rerank ([retrieval/](genios-brain/app/retrieval/))
- Anomaly detection: Z-score vs 90-day baseline (feeds insights even with router off)
- Fact taxonomy: 13 types with Postgres CHECK
- Calibration: Platt scaling per tenant (`GENIOS_CALIBRATION_ENABLED`)

### 7.4 Phase 5 — Memory & coordination (live)

- **Bi-temporal memory** — `valid_time` vs `transaction_time` ([memory/as_of.py](genios-brain/app/memory/as_of.py)) so we can answer *what did the system know on date X*
- **Event log** — append-only, SHA-256 deduped
- **Multi-agent blackboard** ([coordination/blackboard.py](genios-brain/app/coordination/blackboard.py)) — agents publish/subscribe to shared state

---

## 8. Frontend — `genios-dashboard`

**Stack:** Next.js 16 (app router) · React 19 · TypeScript · Tailwind v4 · D3 v7 · PostHog · `lucide-react`. No emoji, design rules from `Design.md` enforced. Files <300 lines per project standard.

### 8.1 Page tree

| Route | What the user sees |
|---|---|
| [/](genios-dashboard/src/app/page.tsx) | Marketing landing |
| [/auth/login](genios-dashboard/src/app/auth/login/page.tsx) · [/signup](genios-dashboard/src/app/auth/signup/page.tsx) | API-key auth |
| [/dashboard](genios-dashboard/src/app/dashboard/page.tsx) | **Graph home** — D3 relationship graph + stats + segments |
| [/dashboard/live](genios-dashboard/src/app/dashboard/live/page.tsx) | Real-time activity feed (3s polling, blackboard + ledger) |
| [/dashboard/brain](genios-dashboard/src/app/dashboard/brain/page.tsx) | Brain status: detectors, recommendations, calibration |
| [/dashboard/context](genios-dashboard/src/app/dashboard/context/page.tsx) | Context tester · health bar · call log · conflict resolver |
| [/dashboard/memory](genios-dashboard/src/app/dashboard/memory/page.tsx) | "Why is this field this value?" — bi-temporal inspector |
| [/dashboard/policies](genios-dashboard/src/app/dashboard/policies/page.tsx) | Policy CRUD + dry-run UI |
| [/dashboard/approvals](genios-dashboard/src/app/dashboard/approvals/page.tsx) | Pending / approved / rejected inbox |
| [/dashboard/integrations](genios-dashboard/src/app/dashboard/integrations/page.tsx) | OAuth flows for all 9 sources, sync state |
| [/dashboard/reports](genios-dashboard/src/app/dashboard/reports/page.tsx) | Weekly intel reports |
| [/dashboard/resources](genios-dashboard/src/app/dashboard/resources/page.tsx) · [/documentation](genios-dashboard/src/app/dashboard/documentation/page.tsx) | Help & docs |
| [/dashboard/settings](genios-dashboard/src/app/dashboard/settings/page.tsx) | Org, API keys, sync intervals |
| [/dashboard/upgrade](genios-dashboard/src/app/dashboard/upgrade/page.tsx) | Plan & seats |

### 8.2 Component groups

| Group | Files |
|---|---|
| [components/dashboard/](genios-dashboard/src/components/dashboard/) | `relationship-graph`, `activity-feed`, `north-star`, `segment-manager`, `stats-bar`, `graph-popups` |
| [components/graph/](genios-dashboard/src/components/graph/) | D3 graph engine — `GeniOSGraph`, `RelationshipGraph`, layers, controls, overlays, transformers |
| [components/context/](genios-dashboard/src/components/context/) | `context-bundle`, `context-tester`, `context-health-bar`, `context-call-log`, `conflict-resolver`, `contact-roster` |
| [components/integrations/](genios-dashboard/src/components/integrations/) | OAuth UI per provider, sync indicators |
| [components/chatbot/](genios-dashboard/src/components/chatbot/) | `ask-your-graph` — natural-language graph Q&A |
| `auth/`, `layout/`, `providers/`, `reports/`, `resources/`, `settings/`, `documentation/`, `ui/` | Standard primitives |

### 8.3 Data flow

- All API calls go to `genios-brain` via fetch in [src/lib/](genios-dashboard/src/lib/), passing the org's API key from `localStorage`
- Live feed polls `/api/org/{org}/live` every 3s
- Recommendations stream uses **SSE** to `/v1/stream/recommendations`
- Graph renders from `/v1/contacts` + per-contact `/v1/context` lazy-loads on click
- Telemetry: PostHog (page-views + custom events on policy/approval/context-test actions)

---

## 9. Agent surfaces beyond the dashboard

### 9.1 MCP server (`genios-mcp`, Node.js, stdio)

10 tools available in any Claude session:

`genios_search_contacts`, `genios_get_context`, `genios_list_segments`, `genios_get_segment_members`, `genios_org_info`, `genios_list_insights`, `genios_log_interaction`, `genios_log_outcome`, `genios_trigger_scan`, `genios_sync_status`.

Source: [genios-mcp/src/index.ts](genios-mcp/src/index.ts). Distributed as a binary; the user pastes their API key into MCP config.

### 9.2 SDKs (`genios-python`, `genios-node`)

- v1.1.0 each, feature-complete (retries, idempotency, webhook signature verify, async SSE, TS types)
- **Not yet published** — blocked only on PyPI / npm tokens
- Same shape as `/v1/*` so they're a thin wrapper, not a rewrite

### 9.3 Email Agent (`genios-email-agent`, Python CLI)

Standalone Gmail OAuth + RAG drafter with three guardrails (no auto-send, learns from user edits, draft-first). Useful as a reference implementation of how external agents should consume `/v1/context`.

### 9.4 Reranker (`genios-reranker`)

Jina reranker v1 turbo, single `POST /rerank`. Already deployed on DigitalOcean App Platform ($5/mo). Improves retrieval recall ~65% → ~85%. **No replacement planned** — pure code-level enhancements only.

---

## 10. Security & multi-tenancy

- **Row-Level Security** on every tenant table (mig `053b_enable_rls_fixed.sql`)
- **API keys hashed** (mig `032_hash_api_keys.sql`) — DB never holds plaintext
- **Action ledger** ensures every agent action is auditable + reversible-tracked
- **Event log** is append-only, SHA-256 deduped
- **GDPR delete** runs in `dry_run=true` by default; flips to live with explicit body flag
- **PII handling:** classifier flags broadcast/transactional vs personal mail before storage
- **OAuth scopes** are minimal per provider (read-only where possible)
- Sentry on, Sentry traces sample 0.1
- Pen test (item V) and legal counsel (item W) are deferred until paid customer / SOC 2 start

---

## 11. Observability & ops

| Layer | State |
|---|---|
| Structured logs (request_id propagated) | ✅ live |
| Sentry | ✅ live |
| 20 Grafana alert rules | ⚠️ written, no Grafana account yet |
| OTel + Prometheus | ⏳ deferred until first un-debuggable prod incident or >25 tenants |
| Status page | ⏳ deferred until public launch |
| Load tests (k6) | ✅ scripts in [ops/load_tests/](ops/load_tests/) |
| Launch checklist | [ops/launch_checklist.md](ops/launch_checklist.md) (50+ items) |

CI ([.github/workflows/](.github/workflows/)): ruff lint · syntax check · unit tests · pip-audit · npm audit · migration safety. Integration tests need a test DB and are commented out.

---

## 12. What's done vs. pending

### ✅ Done

- All 40+ FastAPI routes live; v1 contract stable
- All 9 integrations end-to-end; OAuth flows in dashboard
- 78 migrations applied, RLS on, additive-only enforced in CI
- 3-layer context pull with 400ms deadline
- Hybrid retrieval + reranker + 13-type fact taxonomy
- Policy engine + action ledger + event log + bi-temporal memory
- Dashboard 13 pages, graph, live feed, approvals, policies, memory inspector, context tester
- MCP server 10 tools, both SDKs feature-complete
- 78 migrations, 30+ Celery tasks, 18 test files

### ⚠️ Built but switched off

| Thing | Flag | Unblocks when |
|---|---|---|
| Brain router (48 detectors) | `GENIOS_REASONER_ENABLED` | After canary precision ≥0.80 on 100 candidates |
| Cascade (Haiku→Sonnet) | `GENIOS_CASCADE_ENABLED` | Anthropic key + 2 weeks Phase 3 stable |
| Tenant calibration | `GENIOS_CALIBRATION_ENABLED` | Tenant has ≥50 labeled outcomes |
| Anthropic routing | `GENIOS_ANTHROPIC_ENABLED` | API key arrives |

### ❌ Pending external action

| Item | Owner unblocks |
|---|---|
| Anthropic API key | Vendor/legal |
| PyPI + npm publishing tokens | Owner accounts |
| Grafana account | Owner |
| DigitalOcean deployment | Follow `ops/launch_checklist.md` (must add `brain_router` to worker `-Q`) |
| 3–5 beta design partners | Manual outreach |
| Pen test + legal (ToS, DPA) | Pre-GA / first paid customer |

See [PHASE_DEVIATIONS.md](PHASE_DEVIATIONS.md) for every plan-vs-reality delta with reasons.

---

## 13. How to verify (for the reviewer)

A technical reviewer can confirm the system is real (not slideware) by checking:

1. **Routes mount cleanly** — open [genios-brain/app/main.py](genios-brain/app/main.py); ~40 routers imported, each backed by a file in [api/routes/](genios-brain/app/api/routes/).
2. **Migrations are additive** — `ls genios-brain/migrations/` shows 78 numbered files, none of which contain `DROP`/`DELETE`/`TRUNCATE` (CI enforces).
3. **The hot path is honest** — read [context/minimal_bundle.py](genios-brain/app/context/minimal_bundle.py): single SQL, real data, same shape as Layer 1, enqueues a refresh.
4. **Brain isn't fake** — [brain/](genios-brain/app/brain/) has reasoner/scorer/gate/cascade/calibration as separate files, each <300 lines.
5. **Audit is real** — `event_log` is append-only with SHA-256 dedup; `action_ledger` records risk tier per action.
6. **Tenant isolation** — RLS migrations 053 + 053b; API keys are hashed (mig 032).
7. **Frontend is wired** — [src/app/dashboard/](genios-dashboard/src/app/dashboard/) lists 13 pages, each component group present in [src/components/](genios-dashboard/src/components/).
8. **MCP works in Claude** — install `genios-mcp` binary, set API key, the 10 tools appear in any Claude session.

---

## 14. Decision points where product input would help

These are the open trade-offs — not bugs, choices:

1. **Brain router enablement strategy.** Currently flag-gated globally. Should we go *per-tenant* (canary one paying customer first) or *global* (all tenants once precision ≥0.80)?
2. **SDK publish timing.** Both SDKs are ready; we're not publishing until a real external consumer asks. OK to keep that posture, or ship now to reduce friction?
3. **Anthropic vs. Groq cost ceiling.** Per-org daily cap is currently $50 (`GENIOS_LLM_DAILY_CAP_USD`). Once on Anthropic, do we want a stricter default (e.g. $10) for free tier?
4. **Beta partner profile.** Code is ready for 3–5 design partners. Do we target sales-ops teams (HubSpot-heavy), founder-led startups (Gmail+Calendar), or PM teams (Jira+Notion+Slack)? Each emphasises different connectors.
5. **Dashboard or MCP first.** Both are live; positioning depends on whether the lead user is a human (dashboard) or an agent (MCP). The system serves both equally — what's the headline?

---

## 15. Glossary (so reviewer and we agree on terms)

- **Bundle** — a `/v1/context` response: contact + interactions + commitments + facts + recent narrative.
- **Detector** — a small Python function in `app/brain/` that fires on graph state and emits a candidate insight.
- **Gate** — final step before logging an insight: dedup + budget + policy.
- **Reasoner** — the LLM call that turns candidates into a typed recommendation.
- **Bi-temporal** — every fact has *valid time* (when it was true in the world) and *transaction time* (when we learned it). Lets us answer "what did GeniOS know on date X?"
- **Action ledger** — the immutable record of every action an agent took on the user's behalf.
- **Brain vs. memory** — GeniOS judges and learns; it isn't a passive store.

---

**Contact for follow-ups:** see [SYSTEM_STATUS.md](SYSTEM_STATUS.md) for the live snapshot and [PHASE_DEVIATIONS.md](PHASE_DEVIATIONS.md) for plan-vs-reality.
