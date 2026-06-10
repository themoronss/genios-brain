# GeniOS Quality Recovery Plan

**Status:** Awaiting approval
**Drafted:** 2026-04-28
**Owner:** Engineering
**Purpose:** Sequenced plan to take GeniOS from "demo-quality" to "actually useful" — addressing every issue in the audit doc (`genios-v3-improvements.html`) without scope creep.

---

## 1. Executive Summary

A 5-day Celery/Redis outage from Apr 22 to Apr 27 caused the Brain to **generate insights but not deliver, classify, dedup, score, or extract** them. The audit document was written during this outage — so most of its "broken" findings are actually symptoms of the same root cause, not separate bugs.

The infra has been fixed (Celery + Redis on Apr 27, pull-mode delivery on Apr 27–28). Three commits are deployed, one is local. Most audit-flagged issues will **self-heal within 24 hours** as scheduled jobs resume.

After self-heal, four genuine code gaps remain. This plan sequences them across **5 phases** over **3–4 weeks**, with a hard gate between phases. No work begins on the next phase until the prior phase's acceptance criteria are green.

---

## 2. Current State

### Already deployed (production today)

- `db1f916` — Upstash single-DB Redis compatibility fix
- `afdddf9` — UUID cast fix in pull-mode delivery
- `91096c0` — Pull-mode handles `no_webhook` status as well

### Local, not pushed (awaiting approval)

- `e95f05d` — Sync depth bumped 15→200 / 100→500; body excerpt retained (1000 chars); `context_depth: full` for trial + hustler tiers
- `2d2b252` — `PROCESSING_VERSION` bumped 3 → 4 (queues re-extraction signal)

### Audit findings expected to self-heal in 24h (no new code)

| Audit issue | Why it was failing | What fixes it |
|---|---|---|
| Email summaries blank | `task_extract_pending` couldn't run | Celery up → 5-min cron retries pending extractions |
| 4× duplicate Piyush insights | Push-gate dedup uses Redis SETNX; Redis was unreachable → "fail-open" let everything through | Celery + Redis up → dedup gate enforces |
| `classification: "unknown"` everywhere | `task_classify_contacts` daily 03:00 cron couldn't run | Celery up → cron runs |
| `cache_source: "minimal"` / `precomputed_miss` | Score writer + cache warmer crons couldn't run | Celery up → 15-min and 30-min crons run |
| 22 overdue commitments not surfaced | Proactive scanner 6h cron couldn't run | Celery up → scanner runs |

### Audit findings that are real code gaps

| # | Gap | Why it's real |
|---|---|---|
| A | Attachment processing (PDF / DOCX / ZIP) | No code exists in `gmail_sync.py` for attachment extraction |
| B | Fuzzy alias resolution ("3one4" returns 0) | No `entity_aliases` table; search uses canonical name only |
| C | Inbound acknowledgement detector | No detector for "email received + 48h no reply" |
| D | Cross-contact campaign linking (Op.02) | No `networkx` co-activation scan; `related_outbound` field exists but is never populated cross-contact |

---

## 3. Phases at a Glance

| Phase | Goal | Duration | Gate to next phase |
|---|---|---|---|
| **0 — Stabilize** | Deploy pending fixes, verify infra healthy | Apr 28 (1 day) | Celery logs clean; pull-mode delivery confirmed live |
| **1 — Recovery** | Re-process stale data with new logic | May 1–3 (2 days) | Top-10 contacts have non-empty summaries |
| **2 — Visibility** | Add attachments + fuzzy aliases | May 5–9 (4 days) | Sample PDF visible; "3one4" search resolves |
| **3 — Intelligence** | Inbound ack + cross-contact + PELT | May 12–22 (8 days) | Sohan email flagged; campaigns surface in `related_outbound` |
| **4 — Calibration** | Per-tenant tuning, precedent graph | Jun 12+ (deferred) | ≥30 days of feedback data accumulated |

---

## 4. Phase 0 — Stabilize (Apr 28)

**Goal:** Get every committed fix to production and confirm the infra is healthy.

### Tasks

| # | Task | Owner | Effort |
|---|---|---|---|
| 0.1 | Push commits `e95f05d` and `2d2b252` to `origin/harsh/mvp` | User | 1 min |
| 0.2 | Confirm DigitalOcean autodeploy succeeds | User | 5 min |
| 0.3 | Verify Celery logs show `succeeded` lines, no `Connection error` | Eng | 5 min |
| 0.4 | Verify pull-mode delivery: MCP `genios_list_insights` shows `delivered_at` populated | Eng | 2 min |
| 0.5 | Trigger one Gmail re-sync to test 200-msg cap kicks in | User | 1 min |

### Acceptance criteria

- [ ] Commits visible in remote, deploy succeeded
- [ ] Celery beat + worker show no errors for 10 minutes
- [ ] At least 5 insights show `delivery_status: "delivered"` with timestamp
- [ ] `genios_sync_status` shows `sync_total > 15` after re-sync

**Gate to Phase 1:** All four boxes ticked.

---

## 5. Phase 1 — Recover Stale Data (May 1–3)

**Goal:** The 200-msg sync cap fixes future depth, but historical interactions written before today still have blank summaries. This phase recovers them.

### Why this matters

Without this step, the audit's evidence ("22 Piyush interactions, all blank") will still appear in MCP queries. The brain has the right code now; it just needs to re-run on the old rows.

### Tasks

| # | Task | Effort | Risk |
|---|---|---|---|
| 1.1 | Verify `task_extract_pending` (5-min cron) drains all `extraction_status='pending'` rows organically | 0.5 day | Low |
| 1.2 | Trigger `POST /api/org/{org_id}/reextract` on production for the user's org | 0.5 day | Medium — LLM cost |
| 1.3 | Monitor `llm_usage` table during re-extract; abort if cost exceeds $10 | inline | High if not monitored |
| 1.4 | Verify summaries via MCP `genios_get_context entity:"Piyush Sharma"` | 0.5 day | Low |
| 1.5 | Spot-check Himanshu, Prashant, NSRCEL — confirm summaries populated | 0.5 day | Low |

### Acceptance criteria

- [ ] No interactions with `extraction_status='pending'` older than 1 hour
- [ ] `genios_get_context` for top-10 contacts returns non-empty summaries on majority of interactions
- [ ] Re-extract LLM cost ≤ $10 total for the run

**Gate to Phase 2:** All boxes ticked.

---

## 6. Phase 2 — Visibility Expansion (May 5–9)

**Goal:** Add new data sources the brain currently can't see. Two parallel workstreams.

### Task 2.1 — Attachment Processing (PDF / DOCX / ZIP)

**Why:** Investor term sheets, pitch decks, intern documents arrive as attachments. Today GeniOS sees the email body only — attachment content is invisible. This is the largest blind spot in Section A.

**Approach:**
- In `gmail_sync.py` `fetch_emails()`: after parsing message parts, detect parts with mimeType `application/pdf`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`, `application/zip`.
- Extract text using `PyPDF2` (PDF), `python-docx` (DOCX), `zipfile` + recursive extract (ZIP).
- Cap at 10 MB per attachment; truncate extracted text to 5000 chars per LLM call.
- Append extracted text to the email body before passing to `extract_email_intelligence()`.
- New migration: add `interactions.attachment_text TEXT`, `interactions.attachment_mime VARCHAR(100)`.

**Files touched:** `app/tasks/gmail_sync.py`, `app/ingestion/email_parser.py`, new migration, `requirements.txt`.

**Effort:** 2 days

**Acceptance:**
- [ ] Sohan's Feb 11 attachment content appears in `genios_get_context`
- [ ] Sample investor PDF (provided by user) is summarized in the brain
- [ ] No regression in regular email sync (run existing tests)

### Task 2.2 — Fuzzy Alias Resolution

**Why:** `genios_search_contacts(q:"3one4")` returns 0 results today. Any numeric- or stylized-named entity fails. UX-critical for any agent doing entity lookup.

**Approach:**
- New table: `entity_aliases (entity_id UUID, alias TEXT, source VARCHAR(50), created_at TIMESTAMPTZ)`.
- Backfill from email signatures (regex), CC lines, company name variants in extracted entities.
- Add a normalization function: numeric variants ("3one4" ↔ "ThreeOneFour"), case-folding, whitespace and punctuation stripping.
- Update `genios_search_contacts` SQL to UNION `contacts` and `entity_aliases` via `pg_trgm` GIN index.

**Files touched:** new migration, `app/api/routes/contacts.py`, `app/ingestion/entity_resolver.py`.

**Effort:** 1 day

**Acceptance:**
- [ ] `genios_search_contacts q:"3one4"` returns 3one4 Capital
- [ ] `genios_search_contacts q:"ThreeOneFour"` returns same entity
- [ ] No regression on existing exact-match queries

### Gate to Phase 3

Both 2.1 and 2.2 deployed; acceptance criteria for both green.

---

## 7. Phase 3 — Intelligence Layer (May 12–22)

**Goal:** Add three real intelligence features that move the brain from "tracker" to "advisor."

### Task 3.1 — Inbound Acknowledgement Detector

**Why:** Core "external brain" UX promise. Sohan emailed Apr 10, no reply sent — GeniOS should have flagged this. Today nothing surfaces. Buildable as a rule-based detector.

**Approach:**
- New file: `app/graph/detectors/inbound_ack.py`.
- For each `interaction` where `direction='inbound'` and `interaction_at > NOW() - 14d`, check if any outbound interaction to same contact within 48 hours after.
- If none and contact is not `classification IN ('newsletter','bot','transactional')`, generate insight `unacknowledged_inbound`.
- Wire into `ALL_DETECTORS` in `app/graph/detectors/__init__.py`.

**Effort:** 1 day

**Acceptance:**
- [ ] Sohan Apr 10 generates an `unacknowledged_inbound` insight
- [ ] Broadcast/marketing senders are not flagged
- [ ] Insight includes a suggested-reply hint pulling from contact context

### Task 3.2 — Cross-Contact Campaign Linking (Op.02)

**Why:** Today, sending the same update to NSRCEL + Founders Inc + Prashant generates three independent contexts. Brain can't recognize "this is one campaign." When drafting a fourth message, GeniOS asks the user for context that already exists in `related_outbound`. Op.02 closes this.

**Approach:**
- Use `networkx` to build a multi-graph: nodes = contacts, edges = "received same topic in 7-day window."
- Topic similarity via existing `interactions.embedding` column (cosine ≥ 0.85).
- New table: `campaign_clusters (id, org_id, topic_summary, contact_ids[], created_at, last_message_at)`.
- New scheduled task: `task_campaign_scan` every 30 minutes via Celery beat.
- Surface in `/v1/context` response under `related_outbound.campaign_id` (field already structured).

**Effort:** 3 days

**Acceptance:**
- [ ] When user mentions Prashant, related campaign messages from NSRCEL + Founders Inc surface in the bundle's `related_outbound`
- [ ] Campaign clusters are visible via a new admin endpoint `GET /v1/campaigns`

### Task 3.3 — PELT Change-Point Detection (Op.01)

**Why:** Current anomaly detection is rule-based threshold (e.g. "no contact in 30 days"). PELT detects statistical breaks in time series — catches "Jordan replied in 1.2d avg, then suddenly 11 days silence" before any threshold trips. Higher precision, fewer false positives.

**Approach:**
- New file: `app/graph/detectors/change_point.py`.
- Use `ruptures` library (PELT algorithm) on per-contact engagement_score time series.
- Trigger only when ≥ 14 data points exist (skip new contacts).
- Generate `engagement_change_point` insight on detection.

**Effort:** 2 days

**Acceptance:**
- [ ] Backfill test on Siddhant's interaction history shows PELT flags the sentiment drop earlier than the current rule-based detector
- [ ] No false positives on contacts with stable engagement patterns

### Gate to Phase 4

All three tasks deployed; AAR feedback is being recorded via `/v1/feedback`.

---

## 8. Phase 4 — Calibration (Deferred to Jun 12+)

**Do not start until ≥30 days of feedback data exist.**

Tasks deferred:

- Platt scaling on priority score per tenant
- Precedent graph extraction from successful interaction patterns
- Per-tenant priority weight tuning
- Communication-style learning (per-contact response time, formality, preferred window)

These items are **valuable but premature.** Without 30+ days of acted/ignored/dismissed feedback, calibration is averaging noise.

---

## 9. Out of Scope (Permanently Skipped)

| Item | Reason |
|---|---|
| **NATS JetStream event bus** | Celery + Redis is doing the same job, proven in production today. NATS = new server + new failure mode + zero functional gain at single-tenant scale. |
| **Cross-tenant pattern library** | Single-tenant focus until product-market fit. Requires multi-tenant infra, anonymization story, and a sharing UX — none of which we need now. |
| **Isolation Forest drift detection (Op.03)** | Needs months of per-entity baseline time series. Premature — we have weeks of data, not months. |
| **CDN / edge cache layer** | Latency is fine for current scale. MCP/dashboard latency is in the 200ms range, well under target. |

---

## 10. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| LLM cost spike during Phase 1 re-extract | Medium | Medium | Cap at top-50 contacts; monitor `llm_usage` table; abort if cost > $10 |
| Attachment extraction fails on encrypted/corrupt PDFs | High | Low | Fail-soft: log error, mark `attachment_status='failed'`, do not block the email |
| Fuzzy alias collisions ("ABC Capital" matches multiple) | Medium | Medium | Manual review queue for low-confidence merges; never auto-merge below 0.92 trigram similarity |
| Cross-contact linking creates false campaigns | Medium | Medium | Require ≥ 2 contacts + topic embedding ≥ 0.85 + 7-day window |
| PELT flags too sensitively on sparse data | Low | Low | Minimum 14 data points; tune penalty parameter conservatively |

---

## 11. Final Acceptance Criteria — "Quality Recovery Done"

By **May 25, 2026**, the following must be true via live MCP queries:

1. `genios_list_insights status:delivered` returns ≥ 10 insights with timestamps
2. `genios_get_context entity:"Piyush"` returns non-empty summaries for ≥ 80% of interactions
3. `genios_search_contacts q:"3one4"` returns the correct entity
4. Sohan's Feb 11 attachment content visible in `genios_get_context`
5. At least one `unacknowledged_inbound` insight surfaces in normal usage
6. `related_outbound.campaign_id` populated for multi-contact topics
7. No `classification: "unknown"` on contacts with > 2 interactions

When all 7 are green, GeniOS has crossed from "demo" to "actually useful."

---

## 12. Approvals Needed Before Execution

- [ ] **Phase 0 push approval** — Push `e95f05d` + `2d2b252` to remote
- [ ] **Phase 1 reextract approval** — Trigger `/api/org/{org_id}/reextract` (LLM cost up to $10)
- [ ] **Phase 2 dependency approval** — Add `PyPDF2`, `python-docx` to `requirements.txt`
- [ ] **Phase 3 schedule approval** — Add `task_campaign_scan` to Celery beat (every 30 min)

Each approval is a separate decision. No phase auto-rolls into the next without explicit go-ahead.
