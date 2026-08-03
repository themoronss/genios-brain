# GeniOS Architecture Reconciliation — MDs vs. Code

**Scope:** Reconcile `GENIOS_BUILD_SPEC V3.md` (MD-A), `GENIOS_SHIPPING_SPEC V3.md` (MD-B), and the in-repo codebase at [genios-brain/](genios-brain/), [genios-python/](genios-python/), [genios-node/](genios-node/), [genios-mcp/](genios-mcp/), [genios-dashboard/](genios-dashboard/), [genios-reranker/](genios-reranker/).
**Author stance:** no blind loyalty — pick whichever side is correct for production.
**Bottom line up front:** the MDs describe a cleaner greenfield system; the code is a working, richer-than-spec system with the wrong LLM stack, wrong tenancy model, and missing cost/SLA infrastructure. **Do not rebuild. Port the MD discipline onto the existing codebase.**

---

## 1. Summary of the two MDs

### MD-A — `GENIOS_BUILD_SPEC V3` (v0.3 build)
Green-field construction plan. Locks:

- **Two halves:** Section A (Context Graph) + Section B (Context Intelligence) on NATS JetStream event bus.
- **Scope for v0.3:** Gmail + Calendar connectors only. HubSpot/Slack explicitly deferred.
- **Storage:** Postgres 16 + pgvector + pg_trgm. **Per-tenant schema** (`tenant_<ulid>`) + RLS as defense-in-depth. R2 for cold. Redis for hot cache + Dramatiq broker. NATS for events.
- **Reasoning cascade:** Claude Haiku 4.5 default; Sonnet 4.6 escalation behind `GENIOS_CASCADE_ENABLED=false` flag. Prompt caching mandatory (≥70% hit target).
- **Graph model:** single `facts` table projected into 4 graphs (relationship / authority / state / precedent). Locked 13-type fact taxonomy.
- **Scoring:** 5-axis product `F·C·K·S·A`. Decimal math. Half-life table by type.
- **Lifecycle:** explicit 6-stage state machine (ingest → validate → live → fade → dormant → archive).
- **Retrieval:** hybrid BM25+vector+graph-walk, weighted `0.35/0.30/0.20/0.15`. Pull API **400ms p95 deadline** non-negotiable.
- **Push:** event router debounces 30s per entity → candidate generator (8 algorithmic detectors) → Haiku reasoner → priority scorer → push gate → HMAC-signed webhooks with backoff `30s/2m/10m/1h/6h/24h`.
- **Tests:** 20-test harness, 7 of them Sprint-1 mandatory.
- **Python stack (locked):** FastAPI + Dramatiq + asyncpg + OTel + Prometheus + structlog.

### MD-B — `GENIOS_SHIPPING_SPEC V3` (v1 ship)
Production hardening + Sprint 2/3:

- **Cascade on:** rule-based escalation (high authority roles, high-stakes types, evidence conflicts) independent of Haiku self-report.
- **Precedent graph alive:** weekly extractor abstracts `(situation, action, outcome)` into pattern shapes; reasoner pre-queries top-k precedents.
- **Calibration worker:** nightly per-tenant Platt scaling on reported confidence vs. observed outcomes; per-type precision-targeted thresholds.
- **Cross-tenant pattern library:** k-anonymous (k≥5 tenants), structural hash, quarterly third-party privacy audit.
- **Deploy/DR:** additive-only migrations, two-phase drops at 14-day delay, quarterly restore drills, Vault for secrets, WORM audit log in S3 Object Lock.
- **Commercial:** 3 tiers (Hustler $35 / Startup $149 / Enterprise), self-serve signup 9-min AHA, Stripe billing with soft/hard quota, docs portal, status page, runbooks for 8 scenarios.

### Consistency between MDs
Aligned on every technical decision. MD-B is authoritative over MD-A only on production behavior, alerts, and Sprint 2/3 feature depth.

---

## 2. Current codebase capabilities (actual state)

Sourced from depth audit of [genios-brain/migrations/](genios-brain/migrations/), [genios-brain/app/](genios-brain/app/), and planning docs ([PRODUCTION_READINESS.md](PRODUCTION_READINESS.md), [PHASES_2_TO_5_DONE.md](PHASES_2_TO_5_DONE.md), [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md)).

### 2.1 What's built and working

| Capability | Where | State |
|---|---|---|
| **9 connectors** | [app/ingestion/](genios-brain/app/ingestion/) — Gmail, Calendar, Slack, Jira, Notion, Sheets, Drive, Docs, HubSpot | Shipping — webhooks + backfill + Phase-2 bridges writing into contacts/interactions |
| **Entity extractor** | [app/ingestion/entity_extractor.py:12](genios-brain/app/ingestion/entity_extractor.py#L12) | Groq primary, Gemini fallback. No prompt caching. No cost logging |
| **5-axis scoring** | [app/graph/relationship_calculator.py:214-445](genios-brain/app/graph/relationship_calculator.py#L214) + [app/graph/consistency_engine.py](genios-brain/app/graph/consistency_engine.py) | F/C/K/A computed; **S has no dedicated compute — read as input only** |
| **Fact store** | migration [011_v1_detailing_upgrade.sql:12-41](genios-brain/migrations/011_v1_detailing_upgrade.sql#L12) `contact_facts(fact_type TEXT, lifecycle_state CHECK IN (7 states))` | Free-text fact_type, no controlled vocabulary |
| **Four graphs** | `contacts`+`interactions`+`authority_*`+`state_entities`+`precedent_graph`+`document_chunks`+`precedent_situations` | Tables exist; no `facts` umbrella; `edges` table missing |
| **Bitemporal + event log + action ledger** | migrations 059/060/061 + [app/memory/](genios-brain/app/memory/) | `valid_from/valid_to` on contacts+interactions; immutable `event_log` with SHA-256 dedup; `action_ledger` |
| **Retrieval** | [app/retrieval/bm25.py](genios-brain/app/retrieval/bm25.py), [fuse.py](genios-brain/app/retrieval/fuse.py) (RRF k=60), [rerank.py](genios-brain/app/retrieval/rerank.py) calls [genios-reranker](genios-reranker/) (jina-reranker-v1-turbo-en) | BM25+vector+rerank active; **graph-walk exists in [app/graph/indirect_edges.py](genios-brain/app/graph/indirect_edges.py) but NOT fused in** |
| **Pull API** | [app/api/routes/context.py:141-608](genios-brain/app/api/routes/context.py#L141) `POST /v1/context` | 3-layer cache; returns entity+context+confidence+stage. Pack sizes `small/medium/large` (spec says `short/medium/long`). **No 400ms p95 enforcement** |
| **Detectors** | [app/graph/detectors/](genios-brain/app/graph/detectors/) — commitment, cross_tool, data_quality, disengagement, network, relationship | 6 deterministic detectors (spec requires 8). No LLM-reasoned `keep/dismiss` step |
| **Proactive scanner** | [app/tasks/proactive_scanner.py](genios-brain/app/tasks/proactive_scanner.py), runs via Celery Beat | Formats insights; root-cause via [fingerprint.py::match_precedents](genios-brain/app/graph/fingerprint.py) (structural, not LLM) |
| **Webhook delivery** | [app/tasks/webhook_delivery.py:24-179](genios-brain/app/tasks/webhook_delivery.py#L24) | HMAC-SHA256 signing. **No exponential backoff; no DLQ.** Auto-disables at 10 consecutive failures |
| **Policy + approvals** | migrations 062+064, [app/policy/engine.py](genios-brain/app/policy/engine.py) | DSL evaluator + CRUD + approvals queue. **Not in either MD** — codebase ahead here |
| **Agent blackboard** | [app/coordination/blackboard.py](genios-brain/app/coordination/blackboard.py), migration 058 | Redis SETNX contact locks + audit. **Not in MDs** |
| **Tenancy** | [app/api/deps.py:65-128](genios-brain/app/api/deps.py#L65) `verify_api_key()` + shared-table `org_id` + RLS via Supabase `auth.uid()` (migrations 053/053b) | Works. Not per-tenant schema |
| **Auth** | Bearer API keys `gn_live_*` (hashed in `orgs.api_key_hash` or `api_keys.key_hash`) + JWT for dashboard | Rate limits per-agent RPM and per-org RPH; abuse detection at 1000/h |
| **Queue** | Celery + Redis, two queues `high_priority`/`low_priority`, Beat schedule [celery_app.py:321-384](genios-brain/app/celery_app.py#L321) | ~22 tasks wired |
| **Observability** | Sentry + PostHog + stdlib JSON logs + request_id ContextVar | **No OTel, no Prometheus, no structlog, no llm_usage table** |
| **MCP server** | [genios-mcp/server.py](genios-mcp/server.py) — 10 tools | Real implementation, not stub |
| **SDKs** | Python [client.py](genios-python/genios/client.py) (97 lines), TS [index.ts](genios-node/src/index.ts) (119 lines) | 5 methods each. No streaming, no retries, no webhook verify helper. **No Go SDK** |
| **Dashboard** | [genios-dashboard/](genios-dashboard/) Next.js 16.2 + React 19.2 + Tailwind v4 + D3 | Live/policies/approvals/memory pages exist; Razorpay billing wired |
| **Billing** | Razorpay + subscription lifecycle migrations 031/037/039 | Live. **MDs spec Stripe — India vs US GTM conflict** |
| **Embeddings** | [app/graph/embedder.py](genios-brain/app/graph/embedder.py) `gemini-embedding-001` 768-dim (MRL truncation, migration 048) | Spec says BGE-large 1024. Mismatch on dim + provider |

### 2.2 Consistent undeployed debt (from planning MDs)
- Migrations 058-063 written, **not deployed to prod**.
- `RERANKER_URL` env unset in prod → rerank fails open to raw candidates.
- [GENIOS_MVP_ANALYSIS.md](GENIOS_MVP_ANALYSIS.md) 2026-04-15 audit: localhost:8000 unreachable — live reality gap.

---

## 3. Detailed comparison: MD-A vs MD-B vs Code

### 3.1 Axes of divergence (only the load-bearing ones)

| Axis | MD-A (Build) | MD-B (Ship) | Code | Winner |
|---|---|---|---|---|
| **LLM stack** | Anthropic Haiku/Sonnet | Anthropic + cascade logic | **Groq + Gemini fallback** | **Code (cost)**, but spec-compliance means API-commitment to neither provider. Fix: abstract client |
| **Tenancy** | Per-tenant schema + RLS | Per-tenant schema + RLS | Shared tables + `org_id` + Supabase RLS | **Code** — simpler, supabase-native, validated with 50 migrations. Per-tenant schema was wrong choice for managed-Postgres tier |
| **Event bus** | NATS JetStream | NATS JetStream | Celery Beat + Redis polling | **MD** for true event-driven; **code** for ops simplicity. Event-log pattern in migration 060 is partial substitute |
| **Scoring** | 5-axis, locked weights + half-life | Same | 5-axis; **2 composite formulas** (node vs. fact retrieval); signal_score unimplemented | **MD** has single source of truth; code bifurcated. Consolidate |
| **Lifecycle** | 6-stage state machine | Same | **Two parallel state systems** (`lifecycle_state` 7-value + `clm_state` 6-value + `relationship_stage` 6-value) | **MD** — code is genuinely confused. Must merge |
| **Fact taxonomy** | 13-type controlled vocabulary, CHECK-constrained | Same | `fact_type TEXT` free-text, values suggested in comments only | **MD** unambiguously — missing constraint is a data-quality bomb |
| **Pull API latency** | 400ms p95 hard deadline, degraded-pack fallback | Same + alerting thresholds | **30s LLM timeout** only, no p95 enforcement | **MD** non-negotiable — agent frameworks depend on this |
| **Reasoning** | Haiku reasoner with `keep/dismiss/type/action/confidence/rationale/escalate` | + Sonnet cascade + rule-based escalation + precedents in prompt | Detectors algorithmic; [proactive_scanner:_generate_insight_text](genios-brain/app/tasks/proactive_scanner.py) *formats* not reasons | **MD** — code lacks the LLM-judged keep-dismiss step. This is the core "intelligence" gap |
| **Feedback API** | `POST /v1/feedback` writes `recommendations.outcome*` | + calibration consumer | `POST /v1/outcome` + [migration 040_context_outcomes.sql](genios-brain/migrations/040_context_outcomes.sql) | Draw — rename code endpoint, keep table; add recommendations table |
| **Webhooks** | HMAC + retry schedule `30s/2m/10m/1h/6h/24h` + DLQ | Same + SLA runbook | HMAC ✅ + disable@10-fails ❌ (no backoff, no DLQ) | **MD** — code loses events |
| **Precedent graph** | Schema only, Sprint 3 | Weekly extractor + cross-tenant k-anonymous library | `precedent_graph` + `document_chunks` + `precedent_situations` + [context/precedent_search.py](genios-brain/app/context/precedent_search.py) + fingerprint matching | **Code** is well ahead of MD-A but missing MD-B's cross-tenant anonymization layer |
| **Calibration** | Not in v0.3 | Nightly Platt scaling + per-type precision thresholds | Missing | **MD** — required once Section B reasoning lands |
| **Connectors** | Gmail + Calendar only | + Slack Sprint 2, HubSpot Sprint 3 | Gmail + Calendar + Slack + Jira + Notion + Sheets + Drive + Docs + HubSpot | **Code** is 18 months ahead of MD schedule. MD scoping was too conservative |
| **Observability** | OTel + Prometheus + structlog | + 20 alerts + Grafana dashboards | Sentry + PostHog + JSON stdlib + Sentry tracing@10% | **MD** — can't debug prod latency or cost without OTel spans on LLM calls |
| **Cost accounting** | `llm_usage` table + OTel `cost_usd` span attribute | + $50/tenant/day hard guardrail | **Missing entirely.** Context response uses `chars/4` token estimate | **MD** — unit-economics invisible today |
| **MCP** | Stub | Full in Sprint 2 | 10-tool server, REST-backed | **Code** — MD understates |
| **SDKs** | Python + TS scaffold | + Go + retries + OTel | Python + TS thin (5 methods each) | **MD** — production SDK needs retries/idempotency |
| **Policy engine + approvals** | Absent | Absent | Full DSL evaluator, policies+approvals tables | **Code** ahead of MDs. Keep |
| **Blackboard (multi-agent locks)** | Absent | Absent | Redis SETNX locks on contact claims | **Code** ahead. Keep — valuable for multi-agent |
| **Billing** | Stripe self-serve | Stripe 3-tier + hard cap | Razorpay, subscription_lifecycle migration 031 | **Conflict** — GTM decision. India-first → keep Razorpay; global → add Stripe |
| **Embeddings** | BGE-large 1024-dim | Same | gemini-embedding-001 MRL 768-dim + HNSW | **Code** — BGE is CPU+RAM heavy; Gemini MRL at 768 fits pgvector HNSW 2000-dim limit. MD wrong here |

### 3.2 Features in code that are not in either MD (keep)

- **Agent blackboard** — [app/coordination/blackboard.py](genios-brain/app/coordination/blackboard.py). Real multi-agent coordination. MDs assume single-agent per tenant; production has many.
- **Policy engine + approvals queue** — migrations 062/064, [app/policy/](genios-brain/app/policy/). Enterprise-selling feature.
- **Action ledger** — migration 061. Write-side audit for agent actions, complements read-side event_log.
- **Bitemporal as-of queries** — [app/memory/as_of.py](genios-brain/app/memory/as_of.py). Time-travel debugging. Not in MDs.
- **Tool bridges** — [app/ingestion/*_bridge.py](genios-brain/app/ingestion/). Unified contact/interaction graph across 9 tools. MD taxonomy would require extending.
- **Community detection** — [app/graph/community_detection.py](genios-brain/app/graph/community_detection.py) (Louvain). Not in MDs; valuable for relationship intelligence.

### 3.3 Features in MDs that code does not have (must add)

1. **Anthropic client + cascade** (MD §3.3, MD-B §1.1) — current Groq+Gemini is cost-competitive but unstable for structured JSON. See §5.
2. **400ms p95 on Pull API** (MD-A §7.7) — locked contract with agent frameworks.
3. **LLM-reasoned `keep/dismiss` step** (MD-A §8.3) — algorithmic detectors alone produce noise; no learned judgment layer.
4. **`llm_usage` cost table + OTel spans** (MD §11) — can't manage what we can't measure.
5. **Exponential backoff + DLQ on webhooks** (MD-A §8.5) — losing high-priority pushes silently today.
6. **Single 6-stage lifecycle** (MD-A §7.6) — unify `lifecycle_state` + `clm_state` + `relationship_stage`.
7. **Controlled fact-type CHECK constraint** (MD-A §6.5) — prevents extractor drift.
8. **Graph walk in fused retrieval** (MD-A §7.7) — code has the primitive, not the wire-up.
9. **Calibration worker** (MD-B §2.2) — required once push gate is confidence-driven.
10. **Runbooks + 20 Prometheus alerts** (MD-B §4-§8) — current ops is reactive.
11. **Cross-tenant anonymized pattern library** (MD-B §2.3) — real moat; legal/privacy serious.
12. **Self-serve signup + Stripe tiers** (MD-B §5) — unblocks $0 → paid funnel.

### 3.4 Features in MDs to discard or rescope

- **Per-tenant Postgres schema** (MD-A §6) — discard. Supabase RLS + `org_id` is correct for managed Postgres at 100-tenant scale. MD-A's schema-per-tenant is a 5-year-future problem; today it explodes Supabase connection limits.
- **BGE-large 1024-dim embeddings** (MD-A §3.2) — discard. Keep Gemini MRL-768. Update MD to reflect reality + HNSW index-dim constraint.
- **Dramatiq** (MD-A §3.2) — discard. Celery is live, 22 tasks, beat schedule tuned. Switching cost > benefit.
- **NATS JetStream as primary event bus** (MD-A §2) — discard as *replacement*. **Keep as augmentation** for the reasoning flush pipeline only (below). Celery stays for connector sync + scheduled.
- **Anthropic-only** (MD-A §3.3) — rescope. Use Anthropic for reasoning/narrative (where JSON reliability + prompt-cache matter); keep Gemini for embeddings; keep Groq for high-throughput low-stakes classification (email category). Abstract behind a provider interface.
- **v0.3 scope = Gmail+Calendar only** (MD-A §1.2) — already obsolete; code ships 9 connectors.

---

## 4. Final decisions — keep / change / remove

### 4.1 Keep (as-is)

- Shared-table multitenancy with `org_id` + RLS (053/053b). Validate RLS with pen-test in each release.
- Gemini MRL-768 embeddings + HNSW pgvector indexes.
- Celery + Redis + Beat for connector sync + scheduled jobs.
- Razorpay subscription as long as India is primary GTM.
- All 9 connectors, including their Phase-2 bridges.
- MCP server as a supported surface area (update MDs to mark it "shipped, not stub").
- Policy engine, approvals queue, agent blackboard, action ledger, bitemporal, event_log.
- Dashboard stack (Next.js 16.2 / React 19.2 / Tailwind v4 / D3).
- BM25 + vector + jina-reranker retrieval pipeline.

### 4.2 Change

- **LLM abstraction layer** — introduce `app/llm/client.py` with provider-agnostic interface. Route: reasoning + narrative → Anthropic Haiku (with cascade to Sonnet on rule-based escalation); classification (email category, sentiment) → Groq; embeddings → Gemini. Include prompt caching (for Anthropic), token/cost logging via new `llm_usage` table, and `$X/tenant/day` guardrail.
- **Pull API contract**:
  - Rename pack sizes `small|medium|large` → `short|medium|long` (spec-compliant) with backwards-compat alias.
  - Add `deadline_ms` header, enforce 400ms p95 via `asyncio.wait_for`. On timeout serve Redis-only degraded pack, emit `degraded=true` in response + metric.
- **Fact store consolidation**:
  - Add CHECK constraint to `contact_facts.fact_type` with locked 13-type taxonomy (MD-A §6.5) + migration to normalize existing rows.
  - Introduce `edges` table as denormalized projection of relation-type facts (MD-A §6.2) populated by trigger or writer hook.
- **Lifecycle unification**: new migration collapsing `lifecycle_state` + `clm_state` + `relationship_stage` into MD's 6-stage (`ingest/validate/live/fade/dormant/archive`). Keep `relationship_stage` as an orthogonal *engagement classification* (ACTIVE/WARM/COLD/…) since it's not a lifecycle but a stage label — document the distinction.
- **Reasoning layer**: add `app/brain/reasoner.py` that wraps Anthropic call over each detector-generated candidate. Inputs: candidate + supporting facts + top-3 precedents from [precedent_search.py](genios-brain/app/context/precedent_search.py). Output: `keep/dismiss/confidence/rationale/action/escalate`. Wire between existing `proactive_scanner` and `webhook_delivery`.
- **Webhook dispatcher**: replace disable-at-10 logic with retry schedule `30s/2m/10m/1h/6h/24h` persisted in `delivery_attempts` table (migration ~065). Dead-letter after last attempt. Keep existing HMAC.
- **Feedback endpoint**: rename internal name `outcome` → `feedback` at API layer (`POST /v1/feedback`) with `/v1/outcome` kept as alias for 90 days. Add `recommendations` table (MD-A §6.2) separate from `context_outcomes` (pull-time) — they're different lifecycles.
- **Observability**: add OTel SDK + OTLP exporter + Prometheus client. Minimum spans: `llm.call`, `ingest.extract`, `brain.reason`, `api.request`. Minimum counters: the 7 in MD §11.2. structlog replaces stdlib JSON formatter.
- **Python + TS SDK**: add retries (exp backoff on 5xx/429), idempotency key support, webhook HMAC verify helper, SSE stream client. Bump to 1.0.0 after.
- **Graph walk fusion**: wire [indirect_edges.py](genios-brain/app/graph/indirect_edges.py) as third RRF input in [retrieval/fuse.py](genios-brain/app/retrieval/fuse.py) with MD-A's `0.15` weight.

### 4.3 Remove / don't build

- Do **not** build Dramatiq migration.
- Do **not** build per-tenant Postgres schema.
- Do **not** replace Gemini embeddings with BGE.
- Do **not** build Go SDK until enterprise ask lands.
- Do **not** build marketplace/whitelabel (MD-B §10).
- Do **not** add NATS for primary ingest path — scoped only to reasoning flush loop.

### 4.4 Add (from MD-B) on a staged schedule

| Phase | Item | Why before GA |
|---|---|---|
| Now | LLM client + `llm_usage` + cost guardrail | Can't close a sales call without unit economics |
| Now | Pull API 400ms p95 + degraded fallback | Contract with agent clients |
| Now | Webhook retry schedule + DLQ | Losing pushes today |
| Now | OTel + Prometheus | On-call is blind |
| +2wk | LLM reasoner wrapping detectors | The "brain" in Context Brain |
| +4wk | Lifecycle unification + fact-type CHECK | Data quality degrading |
| +4wk | Feedback endpoint + recommendations table | Unblocks calibration |
| +6wk | Calibration worker (Platt + thresholds) | Tightens push gate precision |
| +8wk | Runbooks + 20 alerts + status page | SOC 2 Type I prerequisite |
| +12wk | Cross-tenant k-anonymous library | Actual moat |
| +16wk | Self-serve signup + Stripe tier (if US GTM) | PLG funnel |

---

## 5. Action plan

### 5.1 Code changes (ordered, each ≤ 3-day task)

1. **Create `app/llm/client.py`** with provider-agnostic `LLMClient.call()`. Port signature from MD-B §3.4. Add `llm_usage` migration (066). Migrate [entity_extractor.py](genios-brain/app/ingestion/entity_extractor.py) and [tasks/proactive_scanner.py](genios-brain/app/tasks/proactive_scanner.py) to use it. **Exit criteria:** every LLM call logs tokens + cost_usd. Daily `$/tenant` queryable.
2. **Add Anthropic path** alongside Groq/Gemini. Prompt caching on system prompts (extractor + reasoner). Route: reasoning + narrative generation → Anthropic; email classification → Groq. Feature flag `GENIOS_ANTHROPIC_ENABLED`.
3. **Enforce Pull API 400ms p95** — wrap [context.py:build_context_bundle](genios-brain/app/api/routes/context.py) in `asyncio.wait_for(timeout=0.4)`. On timeout, serve from Redis + mark `degraded=true`. Add Prometheus histogram.
4. **Webhook retry migration (065)** — `delivery_attempts` table per MD-A §6.1. Rewrite [webhook_delivery.py](genios-brain/app/tasks/webhook_delivery.py) to enqueue next attempt rather than disable. Dead-letter table entry after final attempt.
5. **Rename packs** — `small→short`, `large→long` in [bundle_builder.py:1259-1286](genios-brain/app/context/bundle_builder.py#L1259). Keep old names as alias.
6. **OTel + Prometheus + structlog** — add exporters, migrate [logging_config.py](genios-brain/app/logging_config.py). Instrument: `api.request`, `db.query`, `llm.call`, `ingest.extract`, `brain.reason`, `webhook.deliver`.
7. **Fact-type CHECK migration (067)** — backfill existing `contact_facts.fact_type` values into 13-type taxonomy; add CHECK constraint. Write compatibility map for legacy values.
8. **Lifecycle unification migration (068)** — introduce `contact_facts.lifecycle` (6-stage) derived from current `lifecycle_state`. Keep `clm_state` on `contacts` separately as a derived view. Update [machine.py](#) (new) per MD-A §7.6.
9. **LLM reasoner** — new [app/brain/reasoner.py](#). Consumes detector output from [proactive_scanner](genios-brain/app/tasks/proactive_scanner.py), calls Anthropic Haiku with MD-A §12.2 prompt + precedent context from [precedent_search.py](genios-brain/app/context/precedent_search.py). Output fed to existing webhook pipeline. Flag `GENIOS_REASONER_ENABLED`.
10. **Feedback endpoint + recommendations table** — new [app/api/routes/feedback.py](#) (`POST /v1/feedback`). `recommendations` table per MD-A §6.2. Keep `/v1/outcome` as alias with deprecation header.
11. **Graph-walk RRF fusion** — extend [retrieval/fuse.py](genios-brain/app/retrieval/fuse.py) to accept a third ranked list from [indirect_edges.py](genios-brain/app/graph/indirect_edges.py). Weight per MD-A §7.7.
12. **Calibration worker** — scheduled Celery task (nightly). Platt scaling on `recommendations` (post-op #10). Writes `tenants.settings.calibration`.
13. **SDK retries + HMAC verify helper** — update [genios-python/](genios-python/) + [genios-node/](genios-node/) to spec. Bump both to 1.0.0.
14. **Runbook file tree** — `ops/runbooks/` with the 8 scenarios from MD-B §6. Wire 20 Prometheus alerts to PagerDuty.

### 5.2 MD updates required (correctness, not wish-fixing)

- **MD-A §3.2**: remove Anthropic-only mandate. Replace with provider-agnostic client; Anthropic is the *default* for reasoning but Groq and Gemini remain supported per cost/latency tier.
- **MD-A §3.3**: change embedding model from `BAAI/bge-large-en-v1.5` to `gemini-embedding-001` with `output_dimensionality=768`; justify with pgvector HNSW 2000-dim limit.
- **MD-A §6**: change tenancy model from per-tenant schema to shared tables + `org_id` + Supabase RLS. Document why (managed Postgres connection-pool constraints at 100+ tenants; Supabase-native path).
- **MD-A §2.1**: process topology should list Celery (not Dramatiq). Add NATS as *optional* scoped only to reasoning flush queue if introduced later.
- **MD-A §1.2**: move Slack/HubSpot/Jira/Notion/Drive/Docs/Sheets connectors from "out of scope" into "shipped." Update the "in scope" list.
- **MD-A §6.2**: add `agent_activity_log`, `policies`, `approvals`, `action_ledger`, `event_log`, `precedent_situations` to documented schema. They exist in code; spec should reflect reality.
- **MD-A §9**: MCP is shipped with 10 tools, not a stub.
- **MD-B §5.5**: Razorpay (India) is primary billing. Stripe added when US GTM lands. Do not remove Razorpay.
- **MD-B §2.1**: precedent extraction is already local-tenant shipping (`precedent_situations` migration 056 + [precedent_search.py](genios-brain/app/context/precedent_search.py)). Cross-tenant library is the net-new Sprint-3 item.
- **Both MDs**: add a "Existing features not covered" section for: policy engine, approvals queue, agent blackboard, action ledger, bitemporal as-of, community detection.
- **MD-B §3.3**: fix `valid_values` for `lifecycle` in state-machine code to the 6-stage values; code comment currently allows 7.

### 5.3 Final unified architecture (production-ready, scale-honest)

```
┌────── edge ─────────────────────────────────────────────────────────┐
│  Cloudflare (WAF, DDoS, rate)                                       │
└────────────────┬────────────────────────────────────────────────────┘
                 │
┌── API (FastAPI, 2 workers) ─────────────────────────────────────────┐
│  /v1/context       (400ms p95 · 3-layer cache · short|medium|long)  │
│  /v1/feedback      (was /v1/outcome · 90d alias)                    │
│  /v1/recommendations                                                │
│  /v1/webhooks*     (HMAC-signed outbound · inbound connector)       │
│  /v1/admin, /v1/policies, /v1/approvals, /v1/agents, /v1/billing    │
│  /v1/stream        (SSE · min_priority · agent_id)   [add Sprint 2] │
└────┬───────────────────────────────┬───────────────────────────────┘
     │ auth: gn_live_* → org_id      │
┌──── ingestion (Celery high_priority) ─────┐  ┌── brain (Celery high) ─┐
│ 9 connectors (Gmail, Cal, Slack, Jira,    │  │ proactive_scanner      │
│ Notion, Sheets, Drive, Docs, HubSpot)     │  │  → 6 detectors         │
│   → entity_extractor (Groq · Gemini bkp)  │  │  → reasoner (Haiku +   │
│   → bridges → contacts/interactions       │  │    Sonnet escalation)  │
│   → scoring (F·C·K·S·A → composite)       │  │  → priority_scorer     │
│   → lifecycle machine (6-stage)           │  │  → push_gate           │
│   → event_log append (SHA-256 dedup)      │  │  → webhook_dispatcher  │
└───────────────────────────────────────────┘  │    (HMAC · 30s-24h     │
                                               │    retry · DLQ)        │
┌── storage ─────────────────────────────┐     │  [calibration nightly] │
│ Postgres 16 + pgvector (768 Gemini)    │     └────────────────────────┘
│   · contacts/interactions (bitemporal) │
│   · contact_facts (6-stage lifecycle,  │  ┌── coordination ───┐
│     13-type CHECK, 5 scores)           │  │ blackboard (Redis │
│   · edges (trigger-populated)          │  │  SETNX locks)     │
│   · state_entities, authority_*        │  │ policy + approvals│
│   · precedent_graph + situations       │  │ action_ledger     │
│   · event_log, action_ledger, audit    │  └───────────────────┘
│   · llm_usage, delivery_attempts [new] │
│ Redis (cache · locks · Celery broker)  │
│ R2 (cold signals ≥30d · audit WORM)    │
│ Reranker service (jina-reranker-v1)    │
└────────────────────────────────────────┘
       ▲
       │ OTel spans + Prometheus metrics + structlog + Sentry + PostHog
       │
┌── observability ────────────────────────┐
│ 20 alert thresholds → PagerDuty         │
│ 8 runbooks in ops/runbooks/             │
│ $/tenant/day dashboard (from llm_usage) │
│ status.genios.ai · 3-region uptime      │
└─────────────────────────────────────────┘

Surface area:
  • MCP server (10 tools, shipped)
  • Python SDK 1.0 (retry + HMAC verify + SSE)
  • TypeScript SDK 1.0 (retry + HMAC verify + SSE)
  • Dashboard (Next.js 16.2 · live · policies · approvals · memory)
```

**Design principles reaffirmed:**
1. Boring tech wins — Postgres + Redis + Celery. NATS stays out of the ingest critical path.
2. Cost visible per tenant, per call, per day — or it's not managed.
3. 400ms p95 is a contract, not a goal. Degrade, don't exceed.
4. The graph stores facts; the reasoner stores judgments — never mix.
5. One lifecycle state per fact, one confidence per recommendation.
6. Every outbound push is signed, retried on a schedule, and dead-lettered — no silent drops.
7. Code-to-spec drift gets fixed in the direction of whichever is correct for production, not whichever was written first.

---

## 6. Open questions for human decision

1. **Anthropic billing commit** — introducing Haiku/Sonnet moves us off pure Gemini+Groq. Acceptable monthly floor?
2. **Stripe vs Razorpay** — is US self-serve on the 12-week roadmap? If yes, Stripe alongside Razorpay; if no, skip until then.
3. **SOC 2 Type I timing** — MD-B §0.3 assumes observation period starts pre-GA. Current deploy footprint (Supabase + Upstash + DO + Razorpay) needs vendor DPAs before clock starts. Who owns?
4. **Reasoner default state** — ship with `GENIOS_REASONER_ENABLED=false` and roll forward per tenant, or default on with kill switch?
5. **Cross-tenant pattern library** — legal review of ToS clause before any code. Who signs off?

---

*Authoritative for implementation decisions as of 2026-04-18. Supersedes MD-A §1.2, §3.2-§3.3, §6 tenancy, §2.1 process topology; supersedes MD-B §5.5 billing; does not supersede MD-A §7.5 scoring math, §7.6 lifecycle states, §6.5 fact taxonomy, §8 pipeline shape, §9.2 webhook payload, §12 prompts — those remain canonical.*
