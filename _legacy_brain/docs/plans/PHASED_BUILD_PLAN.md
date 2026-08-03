# GeniOS — Phased Build Plan (Execution Reference)

**Purpose:** this is the execution document. Read [INTELLIGENCE_BUILD_DECISIONS.md](INTELLIGENCE_BUILD_DECISIONS.md) first for the *why*. This doc is the *what + when + how*.

**How to use in a new session:**
1. Say "start Phase N" → agent reads this doc + the decisions doc.
2. Agent executes tasks in order within the phase.
3. Each task has: files, migrations, env vars, dependencies, exit criteria.
4. Do not start Phase N+1 until Phase N exit gate is 100% green.
5. Flags: every new feature is gated off by default. Flip per tenant after validation.

**Zero-hallucination guarantees:** every file path is absolute, every migration numbered, every env var named, every dependency version-pinned. Agent should not invent — if something isn't here, ask the human.

---

## Phase 0 — Prerequisites (before Phase 1 starts)

### 0.1 Credentials to acquire (human action)

| Service | Why | Where | Cost |
|---|---|---|---|
| **Anthropic API key** | Haiku for reasoning, Sonnet for cascade (Phase 3) | [console.anthropic.com](https://console.anthropic.com) | Pay-as-you-go; budget ~$100-300/mo for 25-tenant beta |
| **(existing) Groq API key** | Keep for classification | already in `.env` | already paying |
| **(existing) Gemini API key** | Keep for embeddings | already in `.env` | free tier sufficient |
| **(existing) Supabase project** | Postgres + RLS | already connected | already paying |
| **(existing) Upstash Redis** | Celery broker + cache + blackboard | already connected | already paying |
| **(existing) DigitalOcean droplet** | API + workers + NATS (Phase 2) | already running | already paying |
| **(existing) Razorpay** | Billing | already connected | already live |
| **(existing) Sentry DSN** | Error tracking | already connected | already paying |

### 0.2 Infrastructure inventory (verify before Phase 1)

```bash
# Verify each returns a value:
echo $DATABASE_URL          # Supabase Postgres
echo $REDIS_URL             # Upstash Redis
echo $GEMINI_API_KEY        # Gemini
echo $GROQ_API_KEY          # Groq (check app/ingestion/entity_extractor.py)
echo $SENTRY_DSN            # Sentry
echo $GOOGLE_CLIENT_ID      # OAuth
# ... all integration keys per app/config.py
```

### 0.3 Branch strategy

- `main` — production
- `phase-1-foundation` → PR → `main` at Phase 1 exit gate
- `phase-2-brain` → PR after Phase 1 merged
- ...one branch per phase.

### 0.4 Pre-flight checklist

- [ ] All existing tests pass: `cd /home/harshtripathi/Desktop/genios/genios-brain && pytest tests/`
- [ ] Current prod is healthy (not launching into a known-broken state)
- [ ] Database backup taken (Supabase dashboard → project → backups)
- [ ] Anthropic API key added to `.env` (not yet committed anywhere)

---

## Phase 1 — LLM Foundation + Pull Safety

**Duration:** 2 weeks
**Goal:** Unify all LLM calls behind one client with cost logging + prompt caching. Enable Anthropic. Harden the Pull API and webhook delivery. Nothing customer-visible yet.

**New dependencies added in this phase:**
- Anthropic API (new provider)
- Python package `anthropic==0.39.0`
- `pip-audit==2.7.3` (dev)

**No new infrastructure** (no NATS yet, no Vault, no Prometheus).

### Tasks

#### P1.1 — Migration: `llm_usage` table

- **File:** `/home/harshtripathi/Desktop/genios/genios-brain/migrations/069_llm_usage.sql` (NEW)
- **Spec:** [INTELLIGENCE_BUILD_DECISIONS.md §1.11](INTELLIGENCE_BUILD_DECISIONS.md)
- **Schema to create:** exactly per [GENIOS_BUILD_SPEC V3.md §6.1](GENIOS_BUILD_SPEC%20V3.md) — fields `tenant_id, called_at, purpose, model, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, cost_usd NUMERIC(10,6), trace_id`.
- **Index:** `(tenant_id, called_at::date)` for daily rollup.
- **Exit:** migration applies cleanly, `SELECT * FROM llm_usage LIMIT 1` returns empty.

#### P1.2 — LLM client wrapper

- **File:** `/home/harshtripathi/Desktop/genios/genios-brain/app/llm/__init__.py` (NEW)
- **File:** `/home/harshtripathi/Desktop/genios/genios-brain/app/llm/client.py` (NEW)
- **File:** `/home/harshtripathi/Desktop/genios/genios-brain/app/llm/cost.py` (NEW) — pricing table per model
- **Reference code:** [GENIOS_SHIPPING_SPEC V3 (Complete).md §3.4](GENIOS_SHIPPING_SPEC%20V3%20%28Complete%29.md) — copy the `LLMClient` class.
- **Env vars to add to `app/config.py`:**
  ```python
  ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
  ANTHROPIC_HAIKU_MODEL = os.getenv("ANTHROPIC_HAIKU_MODEL", "claude-haiku-4-5-20251001")
  ANTHROPIC_SONNET_MODEL = os.getenv("ANTHROPIC_SONNET_MODEL", "claude-sonnet-4-6")
  GENIOS_LLM_DAILY_CAP_USD = float(os.getenv("GENIOS_LLM_DAILY_CAP_USD", "50.0"))
  ```
- **Routing table (hardcoded in client.py):**
  | `purpose` value | Provider | Model |
  |---|---|---|
  | `reason_haiku` | Anthropic | Haiku 4.5 |
  | `reason_sonnet` | Anthropic | Sonnet 4.6 |
  | `narrative` | Anthropic | Haiku 4.5 |
  | `classify_email` | Groq | Llama 3.3 70B |
  | `extract_entities` | Groq | Llama 3.3 70B |
  | `embed` | Gemini | embedding-001 |
- **Prompt caching:** system prompts wrapped with `cache_control: {"type":"ephemeral"}`.
- **Cost guardrail:** `_check_cost_guardrail(tenant_id)` raises `TenantCostGuardrailExceeded` if today's `SUM(cost_usd)` exceeds `GENIOS_LLM_DAILY_CAP_USD`.
- **Exit:** unit test in `tests/unit/test_llm_client.py` — mock Anthropic response, verify row inserted in `llm_usage` with correct tokens + cost.

#### P1.3 — Migrate existing LLM callers to new client

- **Files to modify:**
  - `/home/harshtripathi/Desktop/genios/genios-brain/app/ingestion/entity_extractor.py` — replace direct `groq_client` calls with `llm_client.call(purpose="extract_entities", ...)`
  - `/home/harshtripathi/Desktop/genios/genios-brain/app/tasks/classify_contacts.py:61-69`
  - `/home/harshtripathi/Desktop/genios/genios-brain/app/tasks/proactive_scanner.py:72-80`
  - `/home/harshtripathi/Desktop/genios/genios-brain/app/graph/embedder.py` — route embeddings through `purpose="embed"`
- **Exit:** run one real Gmail sync on fixture tenant, verify `SELECT SUM(cost_usd) FROM llm_usage WHERE tenant_id='test_org'` returns non-zero dollar figure.

#### P1.4 — Anthropic connectivity smoke test

- **File:** `/home/harshtripathi/Desktop/genios/genios-brain/scripts/test_anthropic_connection.py` (NEW)
- **Test:** single Haiku call with a fixed prompt, verify parse, verify `llm_usage` row inserted.
- **Exit:** script exits 0. No `GENIOS_ANTHROPIC_ENABLED` flag flipped yet — this is infrastructure validation only.

#### P1.5 — Pull API 400ms deadline + degraded fallback

- **File modified:** `/home/harshtripathi/Desktop/genios/genios-brain/app/api/routes/context.py` around line 496-515
- **Change:** wrap `build_context_bundle` call in `asyncio.wait_for(..., timeout=0.4)`. On `asyncio.TimeoutError`, return Redis-cached pack (if exists) with `meta.degraded=true` and `meta.timeout=true`. If no Redis entry, return minimal pack with `meta.degraded=true, meta.reason="no_cache"`.
- **Env var:** `GENIOS_PULL_DEADLINE_MS=400` (default, tunable per tenant).
- **Exit:** load test with `hey` or `wrk` at 50 req/s for 60s on fixture tenant — p95 < 400ms confirmed. `meta.degraded=true` response observable by artificially slowing DB query.

#### P1.6 — Migration: `delivery_attempts` table

- **File:** `/home/harshtripathi/Desktop/genios/genios-brain/migrations/065_delivery_attempts.sql` (NEW)
- **Schema:** per [GENIOS_BUILD_SPEC V3.md §6.1](GENIOS_BUILD_SPEC%20V3.md) — fields `id, tenant_id, webhook_id, recommendation_id, attempt_number, status, status_code, error, scheduled_at, attempted_at, next_attempt_at`.
- **Index:** `(scheduled_at) WHERE status = 'pending'`.
- **Exit:** migration applies.

#### P1.7 — Webhook retry schedule + DLQ

- **File modified:** `/home/harshtripathi/Desktop/genios/genios-brain/app/tasks/webhook_delivery.py`
- **Change:** replace `consecutive_failures >= 10 → auto_disable` logic with insert into `delivery_attempts`. Retry schedule from env: `GENIOS_WEBHOOK_RETRY_SCHEDULE=30,120,600,3600,21600,86400` seconds. Celery task runs every 30s, reads `delivery_attempts WHERE status='pending' AND next_attempt_at <= NOW()`, attempts delivery, reschedules or marks `dead`.
- **Exit:** chaos test — point webhook at `httpbin.org/status/503` for 5 minutes, then flip to `httpbin.org/status/200`. Verify in `delivery_attempts` table the event delivered with `attempt_number >= 3` and `status='succeeded'`. Zero events in `status='dead'`.

#### P1.8 — CVE scanning in CI

- **File modified:** `/home/harshtripathi/Desktop/genios/.github/workflows/ci.yml` (or create if missing)
- **Add step:** `pip-audit --strict --desc` — fail build on any high/critical CVE.
- **Add step:** `cd genios-node && npm audit --audit-level=high` — same.
- **Exit:** CI run passes on current main.

### Phase 1 Exit Gate

All must be green to move to Phase 2:

- [ ] P1.1 — `llm_usage` migration applied in Supabase
- [ ] P1.2 — `LLMClient` unit test passing
- [ ] P1.3 — All LLM callers migrated; entity extraction run on fixture tenant produces `llm_usage` rows
- [ ] P1.4 — Anthropic smoke test exits 0
- [ ] P1.5 — Pull API p95 < 400ms under 50 req/s load
- [ ] P1.6 — `delivery_attempts` migration applied
- [ ] P1.7 — Webhook chaos test passes (endpoint down 5 min, no events lost)
- [ ] P1.8 — `pip-audit` in CI green

---

## Phase 2 — Brain Core

**Duration:** 2 weeks
**Goal:** The actual reasoning pipeline. Event bus → detectors → LLM reasoner → scorer → gate → dispatcher. Feature-flagged off by default.

**New dependencies:**
- NATS server binary (self-hosted, ~30MB RAM, same DO droplet as brain worker)
- Python package `nats-py==2.9.0`

### Tasks

#### P2.1 — Install NATS JetStream on brain-worker droplet

- **Action:** SSH to droplet running `genios-brain-worker`. Install NATS per [INTELLIGENCE_BUILD_DECISIONS.md §1.1](INTELLIGENCE_BUILD_DECISIONS.md).
  ```bash
  wget https://github.com/nats-io/nats-server/releases/download/v2.10.21/nats-server-v2.10.21-linux-amd64.tar.gz
  tar xzf nats-server-*.tar.gz
  sudo mv nats-server-*/nats-server /usr/local/bin/
  sudo mkdir -p /var/lib/nats
  ```
- **File:** `/etc/systemd/system/nats.service` (NEW, on server)
  ```
  [Unit]
  Description=NATS JetStream
  After=network.target
  [Service]
  ExecStart=/usr/local/bin/nats-server -js -sd /var/lib/nats -p 4222 -m 8222
  Restart=always
  [Install]
  WantedBy=multi-user.target
  ```
- **Enable:** `systemctl enable --now nats`
- **Env var in app:** `NATS_URL=nats://localhost:4222`
- **Exit:** `curl http://localhost:8222/healthz` returns 200 on server.

#### P2.2 — Event bus abstraction

- **File:** `/home/harshtripathi/Desktop/genios/genios-brain/app/brain/__init__.py` (NEW)
- **File:** `/home/harshtripathi/Desktop/genios/genios-brain/app/brain/event_bus.py` (NEW)
- **Interface:**
  ```python
  async def publish(subject: str, payload: dict) -> None
  async def subscribe(subject: str, durable: str, cb: Callable) -> Subscription
  ```
- **Stream config (create once at startup):**
  ```python
  await js.add_stream(name="genios_events", subjects=["genios.events.>"])
  ```
- **Exit:** integration test — publish on `genios.events.test`, subscribe, kill+restart process, verify message still delivered.

#### P2.3 — Fire `fact.updated` events from existing writers

- **Files modified:**
  - `/home/harshtripathi/Desktop/genios/genios-brain/app/graph/relationship_calculator.py` — after score recompute
  - `/home/harshtripathi/Desktop/genios/genios-brain/app/ingestion/graph_builder.py` — after fact write
- **Event payload:**
  ```json
  {
    "tenant_id": "org_uuid",
    "subject_entity_id": "contact_uuid",
    "fact_id": "...",
    "event_type": "fact.updated",
    "score_before": 0.52,
    "score_after": 0.71,
    "crossed_threshold": "promoted"  // promoted | faded | score_dropped | null
  }
  ```
- **Publish to subject:** `genios.events.fact.updated`
- **Exit:** bulk ingest 10 emails on fixture tenant, observe events flowing via `nats sub genios.events.fact.>`.

#### P2.4 — Event router with debounce

- **File:** `/home/harshtripathi/Desktop/genios/genios-brain/app/brain/router.py` (NEW)
- **Spec:** [GENIOS_BUILD_SPEC V3.md §8.1](GENIOS_BUILD_SPEC%20V3.md)
- **Logic:** consume `genios.events.fact.>`, debounce 30s per `(tenant_id, subject_entity_id)`. On flush, call candidate_generator → reasoner → scorer → gate → dispatcher.
- **Env var:** `GENIOS_BATCH_WINDOW_SECONDS=30`
- **Run as:** new Celery long-running worker OR dedicated systemd process. Choose: dedicated systemd process `genios-brain-router.service`.
- **Exit:** bulk ingest 200 facts for one entity → exactly 1 flush called (debounced).

#### P2.5 — Add missing detectors

- **File:** `/home/harshtripathi/Desktop/genios/genios-brain/app/graph/detectors/role_drift.py` (NEW)
- **File:** `/home/harshtripathi/Desktop/genios/genios-brain/app/graph/detectors/authority_change.py` (NEW)
- **File:** `/home/harshtripathi/Desktop/genios/genios-brain/app/graph/detectors/contradiction.py` (NEW)
- **Spec:** [GENIOS_BUILD_SPEC V3.md §8.2](GENIOS_BUILD_SPEC%20V3.md)
- **Register in:** `/home/harshtripathi/Desktop/genios/genios-brain/app/graph/detectors/__init__.py` append to `ALL_DETECTORS` list.
- **Exit:** unit tests for each — synthetic fixture producing one positive case each.

#### P2.6 — Candidate generator wiring

- **File:** `/home/harshtripathi/Desktop/genios/genios-brain/app/brain/candidates.py` (NEW)
- **Logic:** wrap existing [graph/detectors/](genios-brain/app/graph/detectors/). On flush from router, pass the flushed events + tenant context, run all detectors, return union of candidates.
- **Exit:** for 1 flushed bulk-update event batch, candidates list non-empty on seeded fixture.

#### P2.7 — LLM reasoner

- **File:** `/home/harshtripathi/Desktop/genios/genios-brain/app/brain/reasoner.py` (NEW)
- **File:** `/home/harshtripathi/Desktop/genios/genios-brain/app/brain/prompts/__init__.py` (NEW)
- **File:** `/home/harshtripathi/Desktop/genios/genios-brain/app/brain/prompts/reason.py` (NEW)
- **Prompt:** [GENIOS_BUILD_SPEC V3.md §12.2](GENIOS_BUILD_SPEC%20V3.md) copy VERBATIM.
- **Inputs:** candidate + supporting facts + top-3 precedents from [app/context/precedent_search.py](genios-brain/app/context/precedent_search.py)
- **LLM call:** `llm_client.call(purpose="reason_haiku", ...)`
- **Parse:** strict JSON → Pydantic model `ReasonResult`. On parse fail → retry once at `temperature=0.0`. On second fail → log + return `keep=False`.
- **Env flag:** `GENIOS_REASONER_ENABLED=false` (default off).
- **Exit:** 20 synthetic candidates → 20 `ReasonResult` objects with valid schema. Manual review of 10 → ≥ 8 judged reasonable by human.

#### P2.8 — Priority scorer

- **File:** `/home/harshtripathi/Desktop/genios/genios-brain/app/brain/scorer.py` (NEW)
- **Spec:** [GENIOS_BUILD_SPEC V3.md §8.4](GENIOS_BUILD_SPEC%20V3.md) — `0.35·reason_conf + 0.25·subject_importance + 0.25·time_urgency + 0.15·novelty`.
- **Exit:** unit test with 5 fabricated scenarios — priorities rank as expected.

#### P2.9 — Push gate

- **File:** `/home/harshtripathi/Desktop/genios/genios-brain/app/brain/gate.py` (NEW)
- **Spec:** [GENIOS_BUILD_SPEC V3.md §8.5](GENIOS_BUILD_SPEC%20V3.md) — 5 blocking rules.
- **Dedup store:** Redis `SET` keyed `dedup:{tenant_id}:{type}:{subject_entity_id}` with TTL 24h.
- **Env vars:**
  ```
  GENIOS_MIN_PUSH_PRIORITY=0.60
  GENIOS_MIN_PUSH_CONFIDENCE=0.50
  GENIOS_WEBHOOK_DAILY_BUDGET=300
  ```
- **Exit:** unit test: 10 identical candidates in 1min → 1 push, 9 blocked.

#### P2.10 — Entity resolver (5-step algorithm)

- **File:** `/home/harshtripathi/Desktop/genios/genios-brain/app/ingestion/entity_resolver.py` (NEW)
- **Spec:** [GENIOS_BUILD_SPEC V3.md §7.3](GENIOS_BUILD_SPEC%20V3.md) + [INTELLIGENCE_BUILD_DECISIONS.md §3.1](INTELLIGENCE_BUILD_DECISIONS.md)
- **Replace:** current `rapidfuzz`-only matching in entity_extractor.
- **Thresholds:** cosine ≥ 0.90, trigram strong ≥ 0.92, trigram weak ≥ 0.75.
- **Exit:** test fixture with 50 variants of 10 people (aliases, emails, trigrams) — ≥ 95% merged correctly.

### Phase 2 Exit Gate

- [ ] NATS JetStream running on droplet, `systemctl status nats` green
- [ ] Event bus publish+subscribe roundtrip tested
- [ ] `fact.updated` events flowing from writers
- [ ] Event router debounces 200 events → 1 flush
- [ ] All 9 detectors (6 existing + 3 new) registered
- [ ] Reasoner returns valid schema on 20 synthetic candidates
- [ ] Scorer + gate unit tests green
- [ ] Entity resolver 95%+ on fixture
- [ ] `GENIOS_REASONER_ENABLED=true` enabled for 1 canary tenant; 100 candidates reasoned, manual review precision ≥ 0.80

---

## Phase 3 — Learning Loop

**Duration:** 2 weeks
**Goal:** Close the feedback loop. Enable cascade. Add narrative generation. Graph walk fused into retrieval.

**New dependencies:**
- None (Anthropic already in Phase 1)

### Tasks

#### P3.1 — Migration: `recommendations` table

- **File:** `/home/harshtripathi/Desktop/genios/genios-brain/migrations/066_recommendations.sql` (NEW)
- **Spec:** [GENIOS_BUILD_SPEC V3.md §6.2](GENIOS_BUILD_SPEC%20V3.md) — full schema.
- **Exit:** migration applies.

#### P3.2 — `POST /v1/feedback` endpoint

- **File:** `/home/harshtripathi/Desktop/genios/genios-brain/app/api/routes/feedback.py` (NEW)
- **File modified:** `/home/harshtripathi/Desktop/genios/genios-brain/app/main.py` — register router
- **Spec:** [GENIOS_BUILD_SPEC V3.md §8.6](GENIOS_BUILD_SPEC%20V3.md)
- **Keep alive:** `/v1/outcome` as deprecation alias with `Sunset: Wed, 31 Dec 2026 23:59:59 GMT` header.
- **Idempotency:** `idempotency_key` stored in Redis `SET NX` with 24h TTL.
- **On success:** publish `genios.events.feedback.recorded` on NATS (for future calibration consumer).
- **Exit:** integration test — push recommendation → agent acts → POST /v1/feedback → row in `recommendations` has `outcome='acted'`.

#### P3.3 — Wire webhook dispatcher to `recommendations` flow

- **File modified:** `/home/harshtripathi/Desktop/genios/genios-brain/app/tasks/webhook_delivery.py`
- **Change:** dispatcher now reads from `recommendations` table (output of reasoner+gate from Phase 2), not directly from insights.
- **Router hand-off:** in `app/brain/router.py`, after gate approves, `INSERT INTO recommendations` THEN trigger webhook delivery.
- **Exit:** end-to-end test — event → reasoner → gate → `recommendations` row → webhook delivered to test endpoint.

#### P3.4 — Cascade Haiku → Sonnet

- **File:** `/home/harshtripathi/Desktop/genios/genios-brain/app/brain/cascade.py` (NEW)
- **File:** `/home/harshtripathi/Desktop/genios/genios-brain/app/brain/prompts/reason_sonnet.py` (NEW)
- **Spec:** [GENIOS_SHIPPING_SPEC V3 (Complete).md §1.1](GENIOS_SHIPPING_SPEC%20V3%20%28Complete%29.md)
- **Prompts:** SONNET_SYSTEM + SONNET_USER_TEMPLATE verbatim from spec.
- **Env flag:** `GENIOS_CASCADE_ENABLED=false` — leave OFF for 2 weeks after reasoner ships stable, then enable per-tenant.
- **Integration:** `reasoner.reason()` now calls `cascade.should_escalate()` after Haiku; if true, runs Sonnet pass; Sonnet output overrides.
- **Exit:** on canary tenant after 2 weeks stable reasoner, flip cascade on. Measure escalation rate after 50 candidates: target 15-25%. Sonnet confirms ≥ 80% of escalations.

#### P3.5 — Narrative packer in Pull API

- **File:** `/home/harshtripathi/Desktop/genios/genios-brain/app/context/bundle_builder.py` around line 1259-1286 (pack sizing logic)
- **File:** `/home/harshtripathi/Desktop/genios/genios-brain/app/brain/prompts/narrative.py` (NEW)
- **Prompt:** [GENIOS_BUILD_SPEC V3.md §12.3](GENIOS_BUILD_SPEC%20V3.md) verbatim.
- **Logic:** when `format in ("medium","long")`, call `llm_client.call(purpose="narrative", ...)` with top-15 (medium) or top-40 (long) facts. Cache result in Redis with 5-min TTL keyed on `(tenant, query_hash)`.
- **Rename:** pack sizes `small → short`, `medium → medium`, `large → long`. Keep old names as aliases (if `format=small`, treat as `short`).
- **Deadline guard:** narrative call is inside the 400ms window — skip narrative if <150ms remaining.
- **Exit:** pull `format=medium` on fixture tenant returns non-empty `narrative` field under 500ms total.

#### P3.6 — Graph walk fused into retrieval

- **File modified:** `/home/harshtripathi/Desktop/genios/genios-brain/app/retrieval/fuse.py`
- **File modified:** `/home/harshtripathi/Desktop/genios/genios-brain/app/graph/indirect_edges.py` — ensure it exposes `get_neighbors(entity_ids, hops=2) -> ranked list`
- **New weights in `fuse.py`:** `0.35 bm25 + 0.30 vector + 0.20 context_score + 0.15 graph_affinity`.
- **Exit:** recall test on cluster-style query (e.g., "BrightPath deal status" returns facts about BrightPath employees too) — Recall@10 improves by ≥ 10pp vs current BM25+vector-only.

### Phase 3 Exit Gate

- [ ] `recommendations` migration applied
- [ ] `POST /v1/feedback` accepts outcomes; `/v1/outcome` alias works
- [ ] End-to-end: fact change → reasoner → gate → recommendation row → webhook delivered
- [ ] Cascade enabled on canary tenant; precision measured ≥ 80%
- [ ] Narrative packer returns briefing on medium/long packs
- [ ] Graph walk improves Recall@10 by ≥ 10pp on cluster queries

---

## Phase 4 — Correctness & Observability

**Duration:** 3 weeks
**Goal:** Single source of truth for scores and lifecycle. Full observability. Calibration loop. GDPR compliance.

**New dependencies:**
- Python packages: `opentelemetry-api==1.27.0`, `opentelemetry-sdk==1.27.0`, `opentelemetry-instrumentation-fastapi==0.48b0`, `opentelemetry-instrumentation-sqlalchemy==0.48b0`, `opentelemetry-exporter-otlp==1.27.0`, `prometheus-client==0.21.0`, `structlog==24.4.0`, `scikit-learn==1.5.2` (for Platt scaling)
- **New infrastructure (choose ONE):**
  - Option A (managed): Grafana Cloud free tier → receives OTLP + Prometheus remote_write
  - Option B (self-hosted): OTel Collector + Prometheus + Grafana on a new small droplet (~$6/mo)
- **Recommended:** Option A for weeks 7-9, Option B later if cost grows

### Tasks

#### P4.1 — Migration: unify composite score

- **File:** `/home/harshtripathi/Desktop/genios/genios-brain/migrations/067_unify_composite_score.sql` (NEW)
- **Add column:** `contact_facts.score_composite NUMERIC(4,3) GENERATED ALWAYS AS (freshness_score * confidence_score * consistency_score * signal_score * authority_score) STORED`
- **Add column:** `contact_facts.display_score NUMERIC(4,3)` — weighted-sum formula moved here, computed by trigger.
- **Backfill:** recompute all rows.
- **Index:** `(score_composite DESC) WHERE lifecycle IN ('live','fade')`
- **Exit:** migration applies; `SELECT score_composite FROM contact_facts LIMIT 10` returns expected products.

#### P4.2 — Implement missing `signal_score` pipeline

- **File:** `/home/harshtripathi/Desktop/genios/genios-brain/app/graph/signal_scorer.py` (NEW)
- **Spec:** [GENIOS_BUILD_SPEC V3.md §7.5 rule 4](GENIOS_BUILD_SPEC%20V3.md) — `+0.2 named-participant, +0.1 structured, +0.1 recent, -0.2 promo, -0.1 cc-only`.
- **Wire in:** [app/ingestion/graph_builder.py](genios-brain/app/ingestion/graph_builder.py) sets `signal_score` on every fact write.
- **Exit:** 100 synthetic facts → signal_scores match expected values per rule table.

#### P4.3 — Update retrieval to rank on `score_composite`

- **File modified:** `/home/harshtripathi/Desktop/genios/genios-brain/app/retrieval/fuse.py` — use `score_composite` column, not old `context_score`.
- **File modified:** `/home/harshtripathi/Desktop/genios/genios-brain/app/graph/queries.py` wherever `ORDER BY context_score` exists.
- **Exit:** retrieval still works end-to-end; harness T-04 recall unchanged or improved.

#### P4.4 — Migration: lifecycle unification

- **File:** `/home/harshtripathi/Desktop/genios/genios-brain/migrations/068_lifecycle_unification.sql` (NEW)
- **Add column:** `contact_facts.lifecycle TEXT CHECK (lifecycle IN ('ingest','validate','live','fade','dormant','archive'))`
- **Backfill map:**
  ```
  EXTRACTED   → ingest
  VALIDATED   → validate
  ACTIVE      → live
  STALE       → fade
  SUPERSEDED  → archive
  ARCHIVED    → archive
  DELETED     → archive
  ```
- **Rename:** `contacts.relationship_stage → contacts.engagement_stage` (keep old as alias column for 90d).
- **Drop planned:** `lifecycle_state` column dropped in Phase 6 (14-day delay per migration safety rule).
- **Exit:** no rows have `lifecycle IS NULL`.

#### P4.5 — Lifecycle state machine

- **File:** `/home/harshtripathi/Desktop/genios/genios-brain/app/lifecycle/__init__.py` (NEW)
- **File:** `/home/harshtripathi/Desktop/genios/genios-brain/app/lifecycle/machine.py` (NEW)
- **Reference:** [GENIOS_SHIPPING_SPEC V3 (Complete).md §3.3](GENIOS_SHIPPING_SPEC%20V3%20%28Complete%29.md) — copy state machine.
- **Scheduled jobs:**
  - `lifecycle_hourly` — freshness recompute + fade/live transitions (Celery beat)
  - `lifecycle_nightly` — dormant/archive transitions (Celery beat)
- **Exit:** unit test — fact aged 31d with low corroboration transitions `validate → archive` correctly.

#### P4.6 — Migration: fact-type taxonomy CHECK

- **File:** `/home/harshtripathi/Desktop/genios/genios-brain/migrations/070_fact_taxonomy.sql` (NEW)
- **Step 1:** create `fact_type_mapping` table with existing → 13-type map.
- **Step 2:** UPDATE `contact_facts.fact_type = mapping.new_type`.
- **Step 3:** `ALTER TABLE contact_facts ADD CONSTRAINT fact_type_check CHECK (fact_type IN (13 values))`.
- **13 values:** `identity, membership, relation, attendance, mention, thread_link, ownership, role, permission, deal_state, engagement_state, commitment, meeting_state`
- **Exit:** migration applies; no rows violate constraint.

#### P4.7 — OTel + Prometheus + structlog

- **File:** `/home/harshtripathi/Desktop/genios/genios-brain/app/otel_setup.py` (NEW)
- **File modified:** `/home/harshtripathi/Desktop/genios/genios-brain/app/logging_config.py` — replace stdlib JSON with structlog
- **File modified:** `/home/harshtripathi/Desktop/genios/genios-brain/app/main.py` — call `setup_otel()` + mount `/metrics`
- **Spans to instrument:** `api.request, db.query, redis.call, llm.call, ingest.extract, ingest.resolve, brain.reason, brain.score, brain.gate, webhook.deliver, lifecycle.transition`
- **Metrics (Prometheus):** exact names per [GENIOS_BUILD_SPEC V3.md §11.2](GENIOS_BUILD_SPEC%20V3.md).
- **Env vars:**
  ```
  OTEL_EXPORTER_OTLP_ENDPOINT=https://otlp.grafana.net  # or your collector
  OTEL_EXPORTER_OTLP_HEADERS=Authorization=Basic <token>
  OTEL_SERVICE_NAME=genios-api
  ```
- **Exit:** single pull request on fixture tenant → trace visible in Grafana; `GET /metrics` returns Prometheus format.

#### P4.8 — 20-test harness scaffold + Sprint-1 tests

- **File:** `/home/harshtripathi/Desktop/genios/genios-brain/tests/harness/__init__.py` (NEW)
- **Files:** `tests/harness/t01_entity_extraction.py, t03_resolution.py, t05_noise_stability.py, t06_pull_latency.py, t07_ingest_latency.py, t17_pii_leak.py` (6 NEW)
- **File:** `/home/harshtripathi/Desktop/genios/genios-brain/scripts/run_harness.py` (NEW)
- **File:** `/home/harshtripathi/Desktop/genios/genios-brain/tests/fixtures/synthetic_tenant.json` (NEW) — per [GENIOS_BUILD_SPEC V3.md §13.5](GENIOS_BUILD_SPEC%20V3.md).
- **Thresholds** (exit criteria per test):
  - T-01 entity F1 ≥ 0.94
  - T-03 resolution accuracy ≥ 98%
  - T-05 top-5 churn under noise ≤ 1
  - T-06 pull p95 < 400ms
  - T-07 ingest p95 < 90s
  - T-17 RLS cross-tenant query = 100% blocked
- **Add to CI:** `make test-harness` fails build if any Sprint-1 test regresses.
- **Exit:** all 6 tests pass on fixture tenant.

#### P4.9 — RLS bypass regression test

- **File:** `/home/harshtripathi/Desktop/genios/genios-brain/tests/integration/test_rls.py` (NEW or extended)
- **Scenarios:**
  - Missing `app.tenant_id` session var → query returns 0 rows
  - Different `tenant_id` set → query returns only that tenant's rows
  - Direct SQL with `SET ROLE` to non-BYPASSRLS role → cannot read other tenant
- **Exit:** test runs in CI.

#### P4.10 — Calibration worker

- **File:** `/home/harshtripathi/Desktop/genios/genios-brain/app/brain/calibration.py` (NEW)
- **Spec:** [GENIOS_SHIPPING_SPEC V3 (Complete).md §2.2](GENIOS_SHIPPING_SPEC%20V3%20%28Complete%29.md)
- **Celery beat:** nightly 03:00 UTC per tenant.
- **Input:** `recommendations` with outcome recorded in last 60d.
- **Output:** writes `tenants.settings.calibration.{curve, ece, thresholds_per_type}`.
- **Env flag:** `GENIOS_CALIBRATION_ENABLED=false` initially. Enable per-tenant after 50 labeled outcomes.
- **Gate integration:** `app/brain/gate.py` reads `thresholds_per_type` from tenant settings, uses in push decision.
- **Exit:** run on 100 synthetic labeled recommendations → ECE drops from ~12% to < 6%.

#### P4.11 — GDPR deletion cascade

- **File:** `/home/harshtripathi/Desktop/genios/genios-brain/scripts/gdpr_delete.py` (NEW)
- **File:** `/home/harshtripathi/Desktop/genios/genios-brain/app/api/routes/admin.py` — add `POST /v1/admin/delete` (admin auth required)
- **Spec:** [GENIOS_BUILD_SPEC V3.md §10.6](GENIOS_BUILD_SPEC%20V3.md)
- **Cascade:** facts, edges, recommendations, cached retrievals in Redis, embeddings (via fact delete). Anonymized audit entry retained.
- **SLA:** complete within 72h.
- **Exit:** delete fixture entity → 0 residual rows across all tables; audit entry present.

### Phase 4 Exit Gate

- [ ] Composite score unified; retrieval uses `score_composite`
- [ ] `signal_score` computed on all new facts
- [ ] Lifecycle unification migration applied; state machine running hourly+nightly
- [ ] Fact-type CHECK constraint in place; no violations
- [ ] OTel + Prometheus + structlog shipping to Grafana Cloud
- [ ] 6 Sprint-1 harness tests green in CI
- [ ] RLS regression test in CI
- [ ] Calibration worker reduces ECE on synthetic data
- [ ] GDPR delete script tested end-to-end

---

## Phase 5 — Production Polish

**Duration:** 3 weeks
**Goal:** On-call ready. SDK 1.0. SSE streaming. Migration discipline. Everything customer-visible polished.

**New dependencies:**
- PagerDuty account (human sets up) — can use Grafana Cloud OnCall free tier alternatively
- Status page provider (Better Stack or Instatus; free tier available)
- No new Python/Node packages beyond what's already installed

### Tasks

#### P5.1 — 8 incident runbooks

- **Directory:** `/home/harshtripathi/Desktop/genios/ops/runbooks/` (NEW)
- **Files (one per scenario, spec [§6.1-§6.8](GENIOS_SHIPPING_SPEC%20V3%20%28Complete%29.md)):**
  - `01_pull_api_latency_spike.md`
  - `02_llm_quota_exhausted.md`
  - `03_webhook_failing_per_tenant.md`
  - `04_oauth_refresh_failing.md`
  - `05_nats_consumer_lag.md`
  - `06_postgres_high_cpu.md`
  - `07_cross_tenant_leak_suspected.md`
  - `08_gdpr_deletion_request.md`
- **Format:** trigger, diagnosis, mitigation, follow-up.
- **Exit:** each runbook reviewed by one other engineer.

#### P5.2 — 20 alert definitions

- **File:** `/home/harshtripathi/Desktop/genios/ops/alerts.yaml` (NEW)
- **Spec:** [GENIOS_SHIPPING_SPEC V3 (Complete).md §8.2](GENIOS_SHIPPING_SPEC%20V3%20%28Complete%29.md) — exact thresholds.
- **Deploy:** via Grafana Alerting UI or Prometheus AlertManager config.
- **Routing:** SEV-1 → PagerDuty + CEO email; SEV-2 → PagerDuty; SEV-3 → Slack.
- **Exit:** synthetic alert fires → lands in correct destination.

#### P5.3 — Additive-only migration rules

- **File:** `/home/harshtripathi/Desktop/genios/CONTRIBUTING.md` (NEW or extend)
- **Rules:**
  1. Migration must be additive in same PR as code change
  2. `DROP COLUMN` / `DROP TABLE` happens ≥ 14 days later
  3. Every migration has `downgrade()`
  4. `CREATE INDEX CONCURRENTLY` for long-running
- **CI check:** `/home/harshtripathi/Desktop/genios/.github/workflows/migration_safety.yml` (NEW) — scans diff for `DROP COLUMN` and fails unless `[approved-drop]` in commit message.
- **Exit:** CI rejects a test PR that adds a drop without approval tag.

#### P5.4 — Backup restore drill

- **File:** `/home/harshtripathi/Desktop/genios/ops/backup_drill.md` (NEW)
- **Procedure:**
  1. Pick random 24-hour-old Supabase PITR
  2. Restore into a scratch Supabase project
  3. Run query: `SELECT COUNT(*) FROM contact_facts WHERE org_id = :known_id` — result matches pre-drill snapshot
  4. Write post-drill receipt in `ops/drill_log/`
- **Cadence:** quarterly. First drill this phase.
- **Exit:** first drill complete; receipt committed.

#### P5.5 — Python SDK 1.0

- **File modified:** `/home/harshtripathi/Desktop/genios/genios-python/genios/client.py`
- **New features:**
  - Retries with exp backoff on 5xx/429 (250ms, 1s, 4s)
  - `idempotency_key` parameter on `feedback()` and `record_outcome()`
  - `verify_webhook_signature(secret, body, timestamp, signature)` helper
  - Async streaming client for SSE: `client.stream.recommendations(...)` → async generator
- **Version bump:** `0.x → 1.0.0` in `pyproject.toml`.
- **File:** `/home/harshtripathi/Desktop/genios/genios-python/tests/test_retries.py` (NEW)
- **Exit:** publish to PyPI as pre-release tag `1.0.0rc1`.

#### P5.6 — TypeScript SDK 1.0

- **File modified:** `/home/harshtripathi/Desktop/genios/genios-node/src/index.ts`
- **Same features as P5.5, adapted for TS.**
- **Exit:** publish to npm as `@genios/sdk@1.0.0-rc.1`.

#### P5.7 — SSE stream endpoint

- **File:** `/home/harshtripathi/Desktop/genios/genios-brain/app/api/routes/stream.py` (NEW)
- **Spec:** [GENIOS_SHIPPING_SPEC V3 (Complete).md §1.2](GENIOS_SHIPPING_SPEC%20V3%20%28Complete%29.md)
- **Route:** `GET /v1/stream/recommendations?agent_id=&min_priority=`
- **Transport:** `text/event-stream`, NATS subscriber bound to `genios.delivery.{tenant_id}.>`
- **Heartbeat:** comment every 15s.
- **Exit:** SDK SSE client (P5.5) receives streamed recommendation.

#### P5.8 — Status page

- **Action:** create account on Better Stack (free tier).
- **Components:** Pull API, Ingestion, Brain, Webhook delivery, Admin console, Docs.
- **Uptime probes:** from 3 regions (US-east, EU-west, AP-south).
- **Exit:** status.genios.ai reachable and showing all components green.

### Phase 5 Exit Gate

- [ ] 8 runbooks in `ops/runbooks/`
- [ ] 20 alerts configured and test-fired successfully
- [ ] Migration safety CI check active
- [ ] First backup restore drill completed; receipt logged
- [ ] Python SDK 1.0.0rc1 on PyPI
- [ ] TS SDK 1.0.0-rc.1 on npm
- [ ] SSE stream endpoint working end-to-end
- [ ] Status page live at custom subdomain

---

## Phase 6 — Production Validation

**Duration:** 4-6 weeks (calendar time, not engineering effort — includes beta waiting periods)
**Goal:** Prove it works with real customers and real traffic before public launch.

**New dependencies:**
- Pen test vendor (~$3-8K one-time)
- Legal review (~$2-5K one-time)
- (Optional) HashiCorp Vault if SOC 2 Type I observation starts

### Tasks

#### P6.1 — Load test

- **Tool:** `k6` or `hey`
- **Scenarios:**
  - Pull API: 500 req/s sustained 15 min, p95 must stay < 400ms
  - Ingestion: 10K signals/min burst for 5 min
  - Webhook: 1000 concurrent deliveries
- **Exit:** all scenarios pass without errors; Grafana dashboards show steady metrics.

#### P6.2 — Penetration test

- **Vendor:** hire a reputable shop (e.g., HackerOne Professional, Cure53, or local equivalent).
- **Scope:** RLS bypass, OAuth flow attacks, webhook replay, API key forgery, prompt injection against extractor.
- **Exit:** all high/critical findings remediated; report filed in `ops/audits/`.

#### P6.3 — Legal review

- **Scope:** ToS, Privacy Policy, DPA template, Cross-tenant data-sharing clause (future), Razorpay terms alignment.
- **Exit:** legal sign-off letter on each document.

#### P6.4 — Beta tenants (3-5 real customers)

- **Recruit:** 3-5 design-partner customers who will use it for 30+ days.
- **Instrumentation:** per-tenant AAR (Autonomous Act-on Rate) dashboard.
- **Weekly check-in:** structured feedback session with each.
- **Exit criteria:** average AAR ≥ 50% across beta tenants (target ≥ 65% by GA). No SEV-1 incidents.

#### P6.5 — Secrets → Vault (if SOC 2 observation starts)

- **Optional in Phase 6** — trigger is SOC 2 observation start date.
- **Action:** deploy HashiCorp Vault, migrate master key + per-tenant DEKs. Re-encrypt OAuth refresh tokens.
- **Exit:** no plaintext secrets in env; Vault audit log shows key access events.

#### P6.6 — Pre-launch freeze + launch dry run

- **Week -2:** feature freeze. Only bugfixes.
- **Week -1:** deploy v1.0.0-rc to production-equivalent. Full harness run. All 6 Sprint-1 tests + all 20 alerts pre-tested.
- **Week 0 (launch day):** follow [GENIOS_SHIPPING_SPEC V3 (Complete).md §7.5](GENIOS_SHIPPING_SPEC%20V3%20%28Complete%29.md) hourly checklist.
- **Exit:** v1.0.0 tagged in main. Public announcement posted.

### Phase 6 Exit Gate (= GA)

- [ ] Load test passed at 500 req/s × 15 min
- [ ] Pen test findings remediated; sign-off report filed
- [ ] Legal review: ToS, Privacy, DPA signed off
- [ ] 3-5 beta tenants ran ≥ 30 days with AAR ≥ 50% average, no SEV-1
- [ ] Vault deployed if SOC 2 observation active
- [ ] Launch day checklist fully executed
- [ ] Status page green, all alerts armed, on-call staffed

---

## Phase Dependency Map

```
Phase 1 — LLM Foundation + Pull Safety
   │
   ├──> Phase 2 — Brain Core (needs LLM client + Anthropic working)
   │       │
   │       └──> Phase 3 — Learning Loop (needs reasoner from P2)
   │               │
   │               └──> Phase 4 — Correctness + Observability
   │                       │
   │                       └──> Phase 5 — Production Polish
   │                               │
   │                               └──> Phase 6 — Production Validation
```

Cannot skip ahead. Each phase's exit gate gates the next.

---

## Quick-reference: new dependencies by phase

| Phase | New service / account | New infra | New env vars | New packages |
|---|---|---|---|---|
| **0** | (verify existing) | — | — | — |
| **1** | Anthropic API key | — | `ANTHROPIC_API_KEY, ANTHROPIC_HAIKU_MODEL, ANTHROPIC_SONNET_MODEL, GENIOS_LLM_DAILY_CAP_USD, GENIOS_PULL_DEADLINE_MS, GENIOS_WEBHOOK_RETRY_SCHEDULE` | `anthropic==0.39.0`, `pip-audit` |
| **2** | — | NATS JetStream on existing droplet | `NATS_URL, GENIOS_BATCH_WINDOW_SECONDS, GENIOS_REASONER_ENABLED, GENIOS_MIN_PUSH_PRIORITY, GENIOS_MIN_PUSH_CONFIDENCE, GENIOS_WEBHOOK_DAILY_BUDGET` | `nats-py==2.9.0` |
| **3** | — | — | `GENIOS_CASCADE_ENABLED` | — |
| **4** | Grafana Cloud free tier | (optional) OTel collector | `OTEL_EXPORTER_OTLP_ENDPOINT, OTEL_EXPORTER_OTLP_HEADERS, OTEL_SERVICE_NAME, GENIOS_CALIBRATION_ENABLED` | `opentelemetry-*, prometheus-client, structlog, scikit-learn` |
| **5** | Better Stack status page, PagerDuty (or Grafana OnCall) | — | `PAGERDUTY_KEY` | — |
| **6** | Pen test vendor, legal counsel, (optional) Vault | (optional) Vault server | (optional) `VAULT_ADDR, VAULT_TOKEN` | — |

---

## What this doc does NOT do

- Does not tell you to skip decisions in [INTELLIGENCE_BUILD_DECISIONS.md](INTELLIGENCE_BUILD_DECISIONS.md). If there's conflict, decisions doc wins.
- Does not cover Sprint-3+ items (cross-tenant library, public benchmarks, US self-serve). Those are post-GA.
- Does not cover discarded MD items (per-tenant schema, Dramatiq, BGE, NATS-for-everything, Stripe-replacement). Do not build them.

---

## New-session start prompt template

When starting a new session on this plan, paste this:

```
Read /home/harshtripathi/Desktop/genios/PHASED_BUILD_PLAN.md first,
then /home/harshtripathi/Desktop/genios/INTELLIGENCE_BUILD_DECISIONS.md.
Start Phase N, Task PN.X. Follow the file paths, migrations, env vars
exactly as specified. Do not improvise. If any spec is ambiguous,
ask me — do not invent.
```

Replace N and PN.X with the phase/task you want to execute.

---

## Version

**v1.0 · 2026-04-18** — authoritative phased plan. Supersedes the "90-day build order" in [INTELLIGENCE_BUILD_DECISIONS.md Part 4](INTELLIGENCE_BUILD_DECISIONS.md). Amend via PR with rationale, do not silently edit.
