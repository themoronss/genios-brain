# GeniOS Spec v3 — Current System State

**Drafted:** 2026-04-28 (post Phase 2/3 rollout)
**Source of truth:** Live production code on `harsh/mvp` @ `33066c0` and live Postgres state for Rohit's org.
**Purpose:** A complete, unembellished snapshot of what exists, what works, what is intentionally not built, and how the pieces actually fit together right now.

---

## 1. System Topology

```
                       ┌─────────────────────────────────────────────┐
                       │           DigitalOcean App Platform          │
                       │                                             │
   browser ──HTTPS──▶  │  squid-app  (genios-brain web service)      │
                       │   FastAPI on uvicorn, 1 instance, 25% RAM   │
                       │                                             │
   MCP   ──HTTPS──▶    │  + genios-brain2  (worker)                  │
                       │   celery worker -B -Q high,low,brain_router │
                       │   single instance, beat embedded            │
                       └────────────┬───────────────┬────────────────┘
                                    │               │
                ┌───────────────────▼─┐         ┌───▼─────────────────┐
                │  Postgres 16        │         │  Upstash Redis      │
                │  Managed DB on DO   │         │  (TLS, single DB 0) │
                │  pgvector + pg_trgm │         │  cache + broker     │
                │  ~140 interactions  │         │  + result backend   │
                │  ~93 contacts       │         │  global_keyprefix:  │
                │  on Rohit's org     │         │   genios:celery:*   │
                └─────────────────────┘         └─────────────────────┘

LLM providers
  • Groq (llama-3.3-70b-versatile)  — primary, free tier 30 RPM / 100K TPD
  • Gemini (gemini-2.5-flash)       — fallback when Groq fails
  • Anthropic Haiku/Sonnet          — wired in client but not active by default
```

The whole brain runs in **one DigitalOcean app** with two components: a FastAPI web service (`genios-brain`) and a Celery worker (`genios-brain2`) that runs both worker and beat in the same process via `celery -A app.celery_app worker -B`.

---

## 2. Backend — `genios-brain`

### 2.1 API surface

176 endpoints across 30+ route files in `app/api/routes/`. The ones agents and the dashboard actually depend on:

| Surface | Auth | Purpose |
|---|---|---|
| `GET /health` | none | DB + Redis liveness; used by ops + smoke tests |
| `POST /v1/context` | API key | The brain's read API. Returns a structured bundle with `recent_interactions`, `open_commitments`, `relationship_stage`, `sentiment_trend`, `narrative`, `related_outbound`, `cache_source`. |
| `GET  /v1/contacts` | API key | Search / list contacts. As of Phase 2 also uses `pg_trgm` similarity (typos, partial forms). |
| `GET  /v1/insights` | API key | Lists proactive insights. As of Phase 2 it auto-marks `pending`/`no_webhook` rows as `delivered` on read (pull-mode delivery). |
| `POST /v1/insights/{id}/dismiss` | API key | Hide an insight. |
| `GET/POST/DELETE /v1/webhooks` | API key | Manage HMAC-SHA256 webhook subscribers. |
| `POST /v1/scan` | API key | Manually trigger a proactive scan (Hustler/Startup tier). |
| `POST /v1/feedback` | API key | Record AAR outcomes — the input the calibration loop is waiting on. |
| `POST /api/org/{id}/sync` | session/cookie | Dashboard manual Gmail sync trigger. |
| `GET  /api/org/{id}/sync/status` | session/cookie | Sync progress for the dashboard. |
| `POST /api/org/{id}/reextract` | session/cookie | Reprocess existing interactions through the latest extraction logic. |
| `/v1/messages/search`, `/v1/segments`, `/v1/segment/{id}/members`, `/v1/agent`, `/v1/interaction`, `/v1/outcome`, `/v1/sync` | API key | The full set the MCP server proxies. |

### 2.2 Storage

| Layer | Tech | What lives here |
|---|---|---|
| Hot | Redis (Upstash, DB 0) | Layer-2 context cache (60s), narrative cache (1h date-stamped), push-gate dedup keys (24h), rate-limit counters, Celery broker + result backend, brain router event bus. |
| Warm | Postgres 16 + pgvector | All facts of record: `contacts`, `interactions`, `commitments`, `insights`, `webhook_config`, `delivery_attempts`, `precomputed_bundles`, `oauth_tokens`, `llm_usage`, `recommendations`, `feedback`. |
| Cold | not used yet | R2/S3 archive layer is in the spec but not built. |

Notable indexes that today's code relies on:
- `idx_contacts_name_trgm`, `idx_contacts_email_trgm` (pg_trgm GIN, migration 042) — used by the new fuzzy search.
- pgvector HNSW on `interactions.embedding` — used by `related_outbound` semantic match.

### 2.3 Ingestion pipeline (Gmail today; Calendar/Slack/HubSpot stubbed)

```
OAuth   →   gmail_sync.py    →    interactions row (raw_body)
                ↓                       ↓
       attachment_extractor       extract_interactions.py (Celery, 5 min cron)
                ↓                       ↓
        (PDF / DOCX / TXT)         extract_email_intelligence(body + attachment_text)
                ↓                       ↓
        body+attach_text            update interactions with summary, sentiment,
        passed to LLM               intent, topics, commitments, processed_version=4
```

- `SYNC_MAX_EMAILS = 200` per manual run (was 15 before today), `_CRON = 500`.
- Rate limit: `time.sleep(2)` between LLM calls = 30 RPM, matches Groq free tier.
- Daily token cap: **not enforced in code** — Groq's own 100K/day is the actual ceiling.
- `raw_body` is now retained as `LEFT(raw_body, 1000)` after extraction (was nulled before today). Lets pull-mode show an excerpt even if the LLM returned blank.
- `PROCESSING_VERSION = 4`. `task_reextract` re-fetches Gmail and re-runs extraction on any row with `processed_version < 4`.

### 2.4 Entity resolution

`app/ingestion/entity_resolver.py` runs the spec's 5-stage cascade: external_id → canonical name → trigram alias → email → embedding+fuzzy. New entities start `confidence=0.4`, lifecycle `ingest`. Promoted to `live` after 2 corroborations. `is_bidirectional` flag is updated lazily — today's detectors no longer rely on it (see 2.7).

### 2.5 Knowledge graph projections

Single `facts` table, projected by `facts.graph`:
- **Relationship** — who knows who. Working, ~50% complete vs spec.
- **Authority** — role/permission facts. Sparse — most rows still empty for Rohit's org.
- **State** — deal / engagement / commitment with temporal `valid_from`/`valid_until`. Working: 89 open commitments, 22 overdue.
- **Precedent** — Sprint 3 scope. Not built. Deferred to >30 days of feedback.

### 2.6 Context scoring + retrieval

5-axis composite score (`Decimal(3)`):
`context_score = Freshness × Confidence × Consistency × Signal × Authority`.
Scores live on each fact and roll up to contacts (`contacts.context_score`).

Pull API `/v1/context` cache layers:
1. `precomputed_bundles` (24h TTL) — written by `task_refresh_bundle` event-driven from the brain router.
2. Redis 60s — situation-keyed, for repeated identical pulls.
3. Live build (`build_context_bundle`) — cold path.

### 2.7 Brain (Section B)

Every 5 seconds the **brain router** runs (`celery beat`):
1. Pulls events from `event_log` (a Postgres-backed event bus, NOT NATS — see §5).
2. For each event subject, debounces and queues `task_refresh_bundle` to keep the precomputed cache warm.
3. Runs candidate generators against the batch.

**Detectors** (`app/graph/detectors/__init__.py`): **51 registered today.** Two new ones from Phase 3:
- `inbound_ack._detect_unacknowledged_inbound` — inbound > 48h with no reply, on `classification='real_person'` contacts. P1 if warm or has open commitments. **Confirmed firing on real data:** Ansh Goel, Keshav Tayal.
- `change_point._detect_engagement_change_point` — rolling z-score on inter-arrival gaps. Fires when current silence > mean + 2σ on contacts with ≥6 historical interactions. **Currently 0 fires** because the existing `_detect_dormant_reengagement` insight covers the same contacts in the last 7 days (intentional dedup).

**Reasoner cascade** (`app/brain/cascade.py`, `reasoner.py`): Haiku first → Sonnet escalation if confidence < 0.75. Wired but rarely escalating today.

**Push gate** (`app/brain/gate.py`): 4 rules — confidence threshold, priority threshold, quiet hours, dedup (Redis SETNX 24h), daily budget. **Was failing-open during the Apr 22–27 outage** when Redis was unreachable; now functioning.

**Delivery** (`app/tasks/webhook_delivery.py`):
- Webhook (HMAC-SHA256) with retry schedule + DLQ. Active.
- **Pull-mode delivery** added today: `/v1/insights` GET marks `pending` and `no_webhook` rows as `delivered` so insights drain even without a webhook configured.
- SSE — wired in `routes/stream.py` but lightly used.

### 2.8 Narrative (rewritten today)

Was: `narrative.py` made one Groq call per `/v1/context` medium/long pull → ~375 tokens × 154 calls in a single test session = 57K tokens burned.

Now (`narrative.py`, commit `0c00e53`):
- **Programmatic by default.** Synthesizes a 1-2 sentence headline from `stage`, `last_interaction_at`, `sentiment_ewma`, `open_commitments`, `last_subject`. Zero tokens. Output looks like:
  > Piyush Sharma — NEEDS_ATTENTION, last contact 38 days ago. Latest topic: "GeniOS update" · sentiment declining · 5 open commitments.
- LLM path retained behind `GENIOS_NARRATIVE_USE_LLM=true`.
- Cache key changed from facts-fingerprint to date-stamped entity (`narrative:v2:{org}:{entity}:{YYYYMMDD}`), 1h TTL. Old key had 0% hit rate; new key reuses across same-day requests.

### 2.9 Background schedules (Celery beat)

| Task | Cadence | Purpose |
|---|---|---|
| `brain-router-5s` | 5s | Consume event log, queue bundle refreshes |
| `deliver-webhooks` | 30s | Push pending insights to webhooks |
| `extract-pending-5m` | 5m | Pick up `extraction_status='pending'` interactions |
| `score-writer-15m` | 15m | Recompute `contacts.context_score` |
| `auto-merge-30m` | 30m | Apply high-confidence dedup |
| `proactive-scan-6h` | 6h | Run 51 detectors, generate insights |
| `lifecycle-hourly` / `lifecycle-nightly` | 1h / 02:30 | Move facts through lifecycle states |
| `daily-classify-contacts` | 03:00 | LLM classification for `classification='unknown'` rows |
| `precedent-writer-nightly` | 04:00 | Will harvest patterns once feedback data builds up |
| `oauth-healthcheck-daily` | 05:15 | Probe OAuth tokens before they silently rot |

All of these were dead from Apr 22–27 because of the Upstash Redis DB-1 incompatibility. Restored in commit `db1f916`.

---

## 3. Frontend — `genios-dashboard`

Next.js app at `genios-dashboard/`. Source under `src/app/dashboard`:

| Section | What it does |
|---|---|
| `dashboard/` (root) | Activity feed, sync status, quick contact lookup |
| `brain/` | Insight feed (consumes `/v1/insights`), proactive alerts |
| `context/` | Per-contact deep view — pulls `/v1/context` and renders the bundle including the new programmatic `narrative` field |
| `integrations/` | Gmail/Calendar OAuth connect, webhook config |
| `memory/` | Browse stored facts and interactions |
| `approvals/` | Action ledger items waiting for user approval |
| `policies/` | Per-org policy configuration |
| `reports/` | Usage + LLM cost + AAR (when feedback data lands) |
| `documentation/` | In-app docs |
| `resources/` | Helper links |
| `settings/` | API keys, webhooks, org profile |
| `upgrade/` | Plan tier upgrade flow |

Every section that fetches contact-level context now benefits from today's changes — programmatic narrative means **dashboard contact pages no longer need an LLM call to render**, just one Postgres read.

---

## 4. SDKs / MCP

- `genios-mcp/` — Python MCP server proxying 11 tools to the backend's `/v1/*` API. The tool set:
  `genios_search_contacts`, `genios_get_context`, `genios_list_segments`, `genios_get_segment_members`, `genios_org_info`, `genios_list_insights`, `genios_log_interaction`, `genios_log_outcome`, `genios_trigger_scan`, `genios_sync_status`, `genios_search_messages`.
- `genios-node/` — TypeScript SDK (v0.1).
- `genios-python/` — Python SDK (v0.1).

The MCP server is the consumer that benefits most from the narrative rewrite — Claude was ignoring the LLM-generated narrative anyway, so cutting its cost is a pure win.

---

## 5. What is intentionally NOT built — and why

These items are listed in the master design doc and the audit but are **not in production today**. Each is a deliberate trade-off, not an oversight.

| Item | Why skipped | Replaced by |
|---|---|---|
| **NATS JetStream event router** | Adds a separate server + new failure mode + ops burden. The brain router only needs at-least-once event delivery to a single consumer at single-tenant scale. | **Postgres `event_log` table + Celery beat polling every 5s.** Same semantics, no new infrastructure. Proven in production today. |
| **Anthropic prompt caching** | Wired in `llm/client.py` but not active because Groq is the primary provider and Groq does not honor Anthropic's cache control headers. | **Application-level Redis cache** (narrative cache, context cache layers 1+2). |
| **Cross-tenant pattern library** | Requires multi-tenant infra, anonymization, and a sharing UX. Pre-PMF is the wrong time. | Per-tenant precedent graph only — and that is itself deferred. |
| **Isolation Forest drift detection (Op.03)** | Needs months of per-entity baseline data. We have weeks. Would produce noise. | **Rolling z-score change-point** (`change_point.py`) on contacts with ≥6 historical interactions. Achieves the same intent at our data scale. |
| **Precedent graph + Op.04 pattern completion** | Sprint 3 in the build plan. Needs ≥30 days of acted/ignored feedback to extract meaningful patterns. | Schema present, writer scheduled (`precedent_writer_nightly`), but harvest produces nothing today. Stays dormant until feedback accumulates. |
| **Calibration loop / Platt scaling** | Same dependency on feedback data. | `calibration_nightly` task scheduled but a no-op until it has data. |
| **CDN / edge cache** | Latency is fine — pull API p95 is in the 200-400ms range against managed Postgres. | Direct origin, no Cloudflare in front of API. |
| **Hubspot / Slack / Jira connectors** | Auth flows present, sync stubs in place, no real ingestion runs yet. Not part of the audit's day-1 requirement. | Gmail + Calendar are the only live data sources. |
| **R2 cold archive** | Lifecycle stage `archive` exists in code but never moves payloads to R2. Local Postgres handles current volume. | Skipped until volume justifies it. |

---

## 6. What was done today (Phase 0–3 rollout)

Nine commits, in order:

| Commit | Type | Effect |
|---|---|---|
| `db1f916` | infra | Single-DB Redis support — Upstash compatibility. Celery, beat, dedup gate all back online after a 5-day outage. |
| `afdddf9` | fix | UUID cast in pull-mode delivery query. |
| `91096c0` | fix | Pull-mode also drains `no_webhook` insights, not just `pending`. |
| `e95f05d` | feature | Sync depth 15→200 (cron 100→500), retain 1000-char body excerpt after extraction, `context_depth='full'` on every plan tier. |
| `2d2b252` | feature | `PROCESSING_VERSION` 3→4 — marks all 142 existing rows as eligible for reextraction under the new logic. |
| `b91cb93` | feature | `pg_trgm` fuzzy search wired into `/v1/contacts` (was using LIKE only). |
| `4e9f761` | feature | Phase 2/3 batch: attachment text extraction (PDF via PyMuPDF, DOCX via python-docx), inbound_ack detector, change_point detector, campaigns + related_outbound enabled by default. |
| `97e1977` | fix | Reextract path also calls `attachment_extractor` (gmail_sync had it, reextract didn't). |
| `37e5a7a` | fix | Detector filter relaxed: `is_bidirectional=TRUE` was eliminating 90% of contacts; now uses `classification='real_person'`. |
| `0c00e53` | feature | Programmatic narrative + 1h date-stamped cache key. Zero tokens by default; LLM mode opt-in. |
| `33066c0` | chore | Diagnostic + verification scripts under `scripts/_*.py`. |

---

## 7. Verified live state (as of 2026-04-28 ~15:30 UTC)

| Check | Result |
|---|---|
| Backend `/health` | `db ok 436ms / redis ok 15ms / kill_switch off` |
| Celery worker + beat | `succeeded` log lines every 5s and 30s, no errors after the Upstash fix |
| Pull-mode delivery | MCP `list_insights` returns `delivered_at` populated for previously-`pending` rows |
| 5-row LLM dry test | 5/5 passed, ~2,114 tokens/row average |
| Reextract batch 1 (40 rows) | 33 ok, 7 skipped (TIER_0 noise), 0 failed, 68,528 tokens |
| Reextract batch 2 (20 rows) | 12 ok, 8 skipped, 0 failed, 18,604 tokens |
| Cumulative reextract today | **65/140 rows at v4 (46%)** |
| New detectors firing | inbound_ack: Ansh Goel + Keshav Tayal (P1, real). change_point: 0 (suppressed by existing reengagement). |
| Real summary recoveries | Piyush, Himanshu, Prashant, NSRCEL, Boardy, Ansh, Keshav — all now have non-blank, factual summaries from the new extraction |
| Groq token budget today | 97,704 / 100,000 — quota effectively exhausted, reset tomorrow |

---

## 8. Open work after the Groq quota resets

In strict order:

1. **Continue reextract** for the remaining 75 stale rows. Expected ~45/day, so 2 more days to hit 100%.
2. **PDF/DOCX in real data** — Rohit's org has 1 attachment-bearing interaction touched today (Piyush rescheduled meeting, ICS calendar attachment). Need to find a real PDF/DOCX-bearing row and confirm `extract_attachment_text` produces non-empty text in production.
3. **Full sync once extraction stabilizes** — bring fresh emails through the new pipeline so attachment extraction runs on first ingest, not just on reextract.
4. **Verify no regression** in `task_classify_contacts` overnight — it has not had a chance to run since the Upstash fix.
5. **Webhook registration** — currently zero webhooks configured. Pull-mode is fine for MCP/dashboard but a real customer would want push.

Items beyond that (entity_aliases table, Sonnet escalation tuning, Precedent graph harvest, calibration loop, attachment-text DB column split, prompt trimming for token-cost reduction) are tracked in `QUALITY_RECOVERY_PLAN.md` and remain Phase 4+ scope.

---

## 9. Hard constraints to keep in mind

- **Groq free tier: 30 RPM, 100,000 TPD** (separate limits — RPM is enforced by `time.sleep(2)` in the workers; TPD is **not** enforced in code, only by Groq's own 429).
- **Per reextract row: ~2,100 tokens** (extract_entities). 100K daily ÷ 2,100 = **~47 rows/day** ceiling on free tier.
- **Per /v1/context call (programmatic narrative): ~0 LLM tokens.** With LLM narrative on, ~375 tokens.
- **Single instance** for both web and worker. No horizontal scaling yet.
- **Single tenant in production today.** Schema supports multi-tenant (RLS via `tenant_id`), but only one is active.
