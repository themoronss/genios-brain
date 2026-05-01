# GeniOS — System Design Document

> **Context memory for AI agents.** GeniOS ingests relationship signals from Gmail, Google Calendar, Slack, and 6 other tools, scores them into a living relationship graph, and serves real-time context bundles to AI agents so they can act with human-level awareness.

---

## Table of Contents

1. [Design](#1-design)
2. [Features](#2-features)
3. [Requirements](#3-requirements)
4. [Working — End-to-End Flow](#4-working--end-to-end-flow)
5. [Algorithms & Core Logic](#5-algorithms--core-logic)
6. [System Design (HLD)](#6-system-design-hld)

---

## 1. Design

### 1.1 UI/UX Design

**Philosophy:** Warm, professional dashboard — no AI-slop (no purple gradients, no generic card layouts). Uses a golden-amber brand accent (`#c8962e`) on warm off-white backgrounds (`#faf8f5`).

**Layout Architecture:**
- Fixed left sidebar (220px) — navigation, user profile, upgrade CTA
- Top bar — page title, sync status, notifications
- Main content area — page-specific content
- Floating chatbot widget (bottom-right, `z-50`) — "Ask Your Graph"
- Global body zoom: `0.9x`

**Typography:**
| Font | Usage |
|------|-------|
| Poppins | All body text, labels, paragraphs |
| Blinker | Large metric numbers (34px) |
| Orbitron | Logo only |

**Color System:**
| Purpose | Token | Hex |
|---------|-------|-----|
| Brand accent | `brand-orange` | `#c8962e` |
| Page background | `gray-50` | `#faf8f5` |
| Card surface | `white` | `#ffffff` |
| Primary text | `gray-900` | `#171717` |
| Secondary text | `gray-500` | `#737373` |

**Score-based semantic colors** (applied universally):
- `>= 0.75` → emerald (healthy)
- `>= 0.45` → amber (needs attention)
- `< 0.45` → red (at-risk)

**Card Pattern:** `bg-white rounded-xl border border-gray-100 shadow-sm` — consistent across all pages.

### 1.2 Technical Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16.2, React 19.2, TypeScript 6.0 |
| Styling | Tailwind CSS v4 (`@theme` blocks, no config file) |
| Visualization | D3.js 7.9 (force-directed relationship graph) |
| Icons | Lucide React |
| Analytics | PostHog |
| Backend | FastAPI (Python) |
| Database | PostgreSQL + pgvector |
| Cache | Redis (context caching, rate limiting, OAuth state) |
| Graph Algorithms | NetworkX (in-memory) |
| NLP/Extraction | Google Gemini API |
| Fuzzy Matching | rapidfuzz |
| Auth | JWT (7-day) + bcrypt + OAuth 2.0 |
| Payments | Razorpay |

---

## 2. Features

### 2.1 Implemented Features

#### Dashboard (Main Hub)
- **Stats Bar** — 4 expandable metric cards (Brain Health, AER, Time Saved, Context Calls) with sparkline trends
- **Relationship Graph** — D3 force-directed visualization with 3 view modes (Community, Stage, Ego), search, zoom, drag, click-to-detail popups
- **Activity Feed** — Chronological event log with verdict badges (new contact, sentiment shift, commitment detected)
- **Graph Popups** — Drawer-style detail panels for person/org nodes and relationship edges

#### Context Intelligence
- **Global Dashboard** — 4 health metrics, 5 tabs (Overview, Active Facts, Lifecycle, Commitments, Tester), urgent alerts
- **Contact Roster** — Searchable contact list sidebar with stage/sentiment indicators
- **Context Bundle View** — Full contact profile with 5 score bars (Composite, Freshness, Confidence, Consistency, Authority), 5 tabs
- **Conflict Resolver** — Side panel for resolving contradictory facts across sources
- **Context Tester** — Live API test interface + call history

#### Integrations
- **Status Dashboard** — 14 integration cards across 6 categories with connection status
- **Gmail** — Full OAuth connect, sync status, domain exclusions, agent behavior config
- **Google Calendar** — OAuth connect, event sync, attendee resolution (Startup plan)
- **Slack, Jira, Notion, HubSpot** — OAuth connect flows (plan-gated)
- **Google Sheets, Drive, Docs** — Data ingestion connectors
- **Configuration Modal** — Per-tool sync settings, connected accounts management

#### Ask Your Graph (Chatbot)
- 3 query modes: Entity (all plans), Temporal (Hustler+), Semantic (Startup)
- Plan-gated mode selection, quick suggestions, message history

#### Settings (6 tabs)
- Profile, Security (2FA toggle), Billing, Team (invites), API & Keys (regenerate), Danger Zone (graph wipe, account delete)

#### Auth
- Login/Signup forms with JWT token storage
- OAuth redirect flows for all 9 integrations
- Protected routes via layout-level auth guard

#### Billing & Plans
- 3 tiers: Trial → Hustler → Startup
- Razorpay payment integration with order creation + verification

#### Resources
- File upload (drag-drop) + manual contact/interaction entry

#### Documentation
- 4-tab docs: Quick Start, API Reference, Integration Guides, Quick Reference
- Code examples in 5 languages (Python, n8n, OpenClaw, LangGraph, CrewAI)

### 2.2 Planned / Partial

| Feature | Status |
|---------|--------|
| L2 Detailing (Authority/State/Precedent deep scoring) | Tables exist, scoring incomplete |
| Full insights engine (all signal detectors) | Partial — some detectors wired |
| Gmail webhooks (push notifications) | Structure in place, not fully integrated |
| Dark mode | Not planned |
| Mobile responsive | Not implemented |

---

## 3. Requirements

### 3.1 Functional Requirements

| ID | Requirement | Status |
|----|-------------|--------|
| FR-1 | Ingest emails from Gmail via OAuth and extract contacts, sentiment, topics, commitments | ✅ |
| FR-2 | Ingest calendar events, resolve attendees to contacts, classify meeting types | ✅ |
| FR-3 | Ingest data from Slack, Jira, Notion, Sheets, Drive, Docs, HubSpot | ✅ |
| FR-4 | Score relationships across 5 dimensions (confidence, freshness, authority, consistency, composite) | ✅ |
| FR-5 | Classify relationship stage (ACTIVE → WARM → NEEDS_ATTENTION → COLD, AT_RISK override) | ✅ |
| FR-6 | Track sentiment via EWMA with trend detection (IMPROVING / STABLE / DECLINING) | ✅ |
| FR-7 | Serve context bundles via `/v1/context` API with entity resolution (fuzzy match) | ✅ |
| FR-8 | Provide action recommendations (proceed / warn / escalate / block) | ✅ |
| FR-9 | Detect and track commitments (OPEN / OVERDUE / FULFILLED) | ✅ |
| FR-10 | Enforce disclosure rules per entity type (safe/avoid topics) | ✅ |
| FR-11 | Compute warm introduction paths for cold/dormant contacts | ✅ |
| FR-12 | Enforce 72-hour outbound email cooldown | ✅ |
| FR-13 | Enforce plan-based quotas (context calls, contacts, integrations, sync frequency) | ✅ |
| FR-14 | Visualize relationship graph with community detection (Louvain) | ✅ |
| FR-15 | Provide chatbot interface for natural-language graph queries | ✅ |
| FR-16 | Background sync scheduler (manual / 6h cron / real-time per plan) | ✅ |
| FR-17 | Nightly refresh: recalculate scores, run insights, pre-compute bundles | ✅ |
| FR-18 | Filter automated/spam emails (noreply, marketing lists, mass outreach >10 recipients) | ✅ |
| FR-19 | Detect indirect relationships via CC chains and calendar co-attendance | ✅ |
| FR-20 | PII redaction in context paragraphs | ✅ |

### 3.2 Non-Functional Requirements

| ID | Requirement | Implementation |
|----|-------------|---------------|
| NFR-1 | **Latency** — Context API response < 500ms | Redis cache (60s TTL), pre-computed bundles |
| NFR-2 | **Rate Limiting** — Per-agent RPM limits | Redis-backed RPM counter per agent_id |
| NFR-3 | **Security** — API key hashing, JWT expiry | SHA-256 hashed keys, 7-day JWT, bcrypt passwords |
| NFR-4 | **Data Freshness** — Scores reflect current state | Nightly refresh + on-sync recalculation |
| NFR-5 | **Plan Isolation** — Tenants scoped by org_id | All queries filter by org_id, plan enforcement on every API call |
| NFR-6 | **Incremental Sync** — Don't re-process old data | Gmail history_id, Calendar syncToken, per-tool cursor tracking |
| NFR-7 | **Scalability** — Handle growing contact volume | Batch processing (15 emails/manual, 100/cron), contact limits per plan |
| NFR-8 | **Observability** — Track all context API usage | `context_calls` table logs every call with latency, source, cache hit |
| NFR-9 | **Resilience** — Non-blocking activity logging | `log_activity()` wraps in try/except, never blocks main flow |
| NFR-10 | **Data Quality** — Filter noise from signal | Email classifier, automated sender detection, mass outreach filtering |

---

## 4. Working — End-to-End Flow

### 4.1 User Onboarding Flow

```
Signup → Create Org (Trial plan) → Generate API Key → Connect Gmail (OAuth) → Initial Sync
```

1. User registers → `POST /auth/register` → org created with `trial` plan, API key generated (`gn_live_*`)
2. User connects Gmail → `GET /auth/gmail/connect` → Google OAuth consent → callback stores `oauth_tokens`
3. Initial sync triggered → `POST /api/org/{id}/sync` → fetches last 15 emails → processes pipeline

### 4.2 Data Ingestion Pipeline (Gmail Example)

```
Gmail API → Parse → Classify → Extract → Score → Store → Bridge to Graph
```

1. **Fetch** — Gmail API `messages.list()` with `historyId` for incremental sync
2. **Parse** — Extract headers (from/to/CC/subject/date), body (plain > HTML), attachments
3. **Filter** — Skip automated senders (noreply, marketing lists), mass outreach (>10 recipients)
4. **Classify** — Determine type: reply, one-way, commitment, introduction, follow-up
5. **Extract** — LLM-powered entity extraction: people, companies, topics, commitments, sentiment
6. **Score** — Compute `signal_score` weighted by interaction type and content richness
7. **Store** — Upsert `contacts` + insert `interactions`, update running stats (sentiment_ewma, response_rate)
8. **Bridge** — Update relationship metrics, detect stage changes, log to activity feed

### 4.3 Calendar Processing Pipeline

```
Calendar API → List Events → Classify → Resolve Attendees → Bridge
```

1. **Fetch** — Google Calendar API with `syncToken` for incremental updates
2. **Quality Gate** — Filter private events, OOO blocks, focus time, declined events
3. **Classify** — Internal vs external, meeting type (1:1, group, all-hands), location type (video/in-person/phone)
4. **Resolve** — Map attendees to existing contacts (by email), create new contacts if needed
5. **Extract** — Agenda summary, commitments, attendance (declined RSVP = no-show)
6. **Bridge** — Create interaction per attendee, generate upcoming meeting prep context

### 4.4 Context Bundle Assembly (The Core API)

```
POST /v1/context { entity, situation, agent_id } → Bundle
```

1. **Auth** — Validate API key → resolve org → check plan quota + RPM limit
2. **Cache Check** — Redis lookup: `context:{md5(org:entity:situation)}` (60s TTL)
3. **Entity Resolution** — Exact match (case-insensitive) → fuzzy match (70% threshold via rapidfuzz) → return `match_confidence`
4. **Data Gather** — Recent interactions (20/50/200 by plan), open commitments, tags, disclosure level
5. **Score** — Freshness, confidence, consistency, authority, composite → all 5 dimensions
6. **Action Engine** — Apply rules:
   - `AT_RISK` or sentiment < -0.5 → `block` (escalation recommended)
   - Investor + sensitive topic → `escalate`
   - Overdue commitments → `warn`
   - Default → `proceed`
7. **Disclosure** — Compute safe/avoid topics per entity type
8. **Warm Intros** — If COLD/DORMANT, find shared CC threads or calendar co-attendees as introducer candidates
9. **Cooldown** — Check 72-hour outbound email cooldown
10. **Generate** — Human-readable context paragraph with PII redaction
11. **Cache & Log** — Store in Redis, log to `context_calls`
12. **Return** — Full bundle: entity profile, scores, action recommendation, context paragraph, warm intro paths

### 4.5 Gmail ↔ Calendar Overlap

Both integrations feed the same `contacts` and `interactions` tables:
- **Cross-matching**: Calendar event subject + date matched against email thread subjects → same meeting
- **Co-attendance**: Calendar attendees who also appear in email CC → inferred indirect relationship
- **Signal stacking**: A contact with both email AND calendar signals scores higher confidence (source diversity bonus)
- **Meeting prep**: Upcoming calendar events trigger pre-computation of context bundles for all attendees

---

## 5. Algorithms & Core Logic

### 5.1 Relationship Stage Classification

```
Rules (evaluated top-to-bottom, first match wins):

AT_RISK:          sentiment_ewma < -0.3              (overrides all)
ACTIVE:           days < 14 AND sentiment > 0 AND bidirectional
WARM:             days < 14 AND sentiment > 0 (one-sided)
                  OR days < 30
NEEDS_ATTENTION:  31 ≤ days ≤ 60
COLD:             days > 60
```

### 5.2 Sentiment Tracking (EWMA)

```
Formula: ewma_new = α × sentiment_current + (1 − α) × ewma_previous
α = 0.3 (recent = 30% weight, history = 70%)

Trend Detection (window = 5 interactions):
  Δ = avg(last 5) − avg(previous 5)
  Δ > +0.15  → IMPROVING
  Δ < −0.15  → DECLINING
  else       → STABLE
```

### 5.3 Confidence Score

```
base_score = Σ source_weights[source]   (gmail=0.35, calendar=0.25, slack=0.20, ...)
recency_decay = 0.5 ^ (days_since / 90)
volume_mult = {≥20: 1.15, ≥10: 1.05, ≥5: 1.00, ≥2: 0.80, 1: 0.55}
recency_mult = {>90d: 0.75, >30d: 0.90, else: 1.00}

confidence = min(1.0, base × decay × volume × recency)
```

### 5.4 Freshness Decay

```
Formula: max(0.1, 0.5 ^ (days_since / half_life))

Stage-specific half-lives:
  ACTIVE:          7 days
  AT_RISK:        15 days
  WARM:           30 days
  NEEDS_ATTENTION: 45 days
  DORMANT:        60 days
  COLD:           90 days
```

### 5.5 Node Size Score

```
size = (normalized_interactions_90d × 0.6) + (recency_score × 0.4)
Tiers: Large (>0.70), Medium (0.40–0.70), Small (<0.40)
```

### 5.6 Community Detection

- **Algorithm**: Louvain method (via NetworkX)
- **Input**: Contact nodes + interaction edges weighted by signal_score
- **Output**: Cluster assignments stored in `graph_segments`
- **Cluster types**: Investor, Customer, Team, Vendor, Admin, Other
- **Plan limits**: Trial = 1 cluster, Hustler = 3, Startup = 10

### 5.7 Indirect Edge Computation

```
Finds A → B → C via:
  - Shared email CC chains
  - Calendar co-attendance

Confidence = min(0.7, 0.3 + shared_threads × 0.1)
```

### 5.8 Action Recommendation Engine

```
Priority-ordered rules:
1. AT_RISK OR sentiment < -0.5       → block  (escalate_recommended = true)
2. Investor/Board + sensitive topic  → escalate (human review)
3. Overdue commitments               → warn
4. DORMANT + declining sentiment     → warn
5. Default                           → proceed
```

### 5.9 Email Classification

Automated sender detection filters: `noreply@`, marketing lists, mass outreach (>10 unique recipients). Emails classified as: reply, one-way, commitment, introduction, follow-up — weighted differently in signal scoring.

---

## 6. System Design (HLD)

### 6.1 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (Next.js)                         │
│  Dashboard │ Context │ Integrations │ Chatbot │ Settings │ Auth    │
└────────────────────────────┬────────────────────────────────────────┘
                             │ REST API (JWT + API Key auth)
┌────────────────────────────▼────────────────────────────────────────┐
│                       FASTAPI BACKEND                              │
│                                                                    │
│  ┌──────────┐  ┌──────────────┐  ┌────────────┐  ┌─────────────┐  │
│  │ Auth     │  │ Context API  │  │ Integrations│  │ Graph API   │  │
│  │ Routes   │  │ /v1/context  │  │ OAuth +Sync │  │ Topology    │  │
│  └──────────┘  └──────┬───────┘  └──────┬──────┘  └─────────────┘  │
│                       │                 │                           │
│  ┌────────────────────▼─────────────────▼──────────────────────┐   │
│  │                    CORE ENGINE                              │   │
│  │                                                             │   │
│  │  ┌─────────────┐  ┌──────────────┐  ┌───────────────────┐  │   │
│  │  │ Bundle      │  │ Relationship │  │ Ingestion         │  │   │
│  │  │ Builder     │  │ Calculator   │  │ Pipeline          │  │   │
│  │  │             │  │              │  │                   │  │   │
│  │  │ - Resolve   │  │ - Stage      │  │ - Gmail Connector │  │   │
│  │  │ - Score     │  │ - Sentiment  │  │ - Cal Connector   │  │   │
│  │  │ - Recommend │  │ - Confidence │  │ - Slack/Jira/etc  │  │   │
│  │  │ - Disclose  │  │ - Freshness  │  │ - Email Parser    │  │   │
│  │  │ - Generate  │  │ - Authority  │  │ - Entity Extractor│  │   │
│  │  └─────────────┘  └──────────────┘  │ - Graph Builder   │  │   │
│  │                                     └───────────────────┘  │   │
│  │  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐  │   │
│  │  │ Plan        │  │ Community    │  │ Insights         │  │   │
│  │  │ Enforcer    │  │ Detection    │  │ Engine           │  │   │
│  │  │ (quotas,    │  │ (Louvain)    │  │ (signal          │  │   │
│  │  │  gates)     │  │              │  │  detectors)      │  │   │
│  │  └─────────────┘  └──────────────┘  └──────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │                  BACKGROUND TASKS                          │    │
│  │  Gmail Sync │ Calendar Sync │ Slack Sync │ Nightly Refresh │    │
│  │  Jira Sync  │ Notion Sync   │ Confidence Updater           │    │
│  │  Drive Sync │ Docs Sync     │ Weekly Report │ Billing Jobs  │    │
│  └────────────────────────────────────────────────────────────┘    │
└──────────┬──────────────────┬──────────────────┬───────────────────┘
           │                  │                  │
    ┌──────▼──────┐   ┌──────▼──────┐   ┌───────▼───────┐
    │ PostgreSQL  │   │   Redis     │   │ External APIs │
    │ + pgvector  │   │             │   │               │
    │             │   │ - Cache     │   │ - Gmail API   │
    │ - contacts  │   │ - RPM       │   │ - Calendar API│
    │ - interacts │   │ - OAuth     │   │ - Slack API   │
    │ - commits   │   │   state     │   │ - Jira API    │
    │ - oauth     │   │             │   │ - Notion API  │
    │ - segments  │   │             │   │ - HubSpot API │
    │ - activity  │   │             │   │ - Gemini API  │
    │ - 40+ tables│   │             │   │ - Razorpay    │
    └─────────────┘   └─────────────┘   └───────────────┘
```

### 6.2 Data Model (Core Tables)

```
orgs ──────────────────────────────────────────────────
  id, name, api_key (hashed), plan (trial/hustler/startup),
  plan_started_at, period_context_calls, daily_context_calls

contacts ──────────────────────────────────────────────
  id, org_id → orgs, name, email, company,
  relationship_stage, sentiment_avg, sentiment_ewma, sentiment_trend,
  freshness_score, confidence_score, consistency_score, authority_score,
  composite_score, response_rate, avg_response_time_hours,
  is_bidirectional, entity_type, disclosure_level,
  tags[], topics_aggregate[], communication_style,
  what_works, what_to_avoid, introduced_by,
  last_interaction_at, first_interaction_at, interaction_count

interactions ──────────────────────────────────────────
  id, org_id → orgs, contact_id → contacts,
  source (gmail/calendar/slack/...), interaction_type,
  subject, body_snippet, sentiment, signal_score,
  topics[], entities_extracted, commitment_detected,
  interaction_at, direction (inbound/outbound)

commitments ───────────────────────────────────────────
  id, org_id, contact_id → contacts, interaction_id → interactions,
  description, status (OPEN/OVERDUE/FULFILLED/SOFT),
  owner (user/contact), due_date, created_at

oauth_tokens ──────────────────────────────────────────
  id, org_id → orgs, tool (gmail/calendar/slack/...),
  account_email, access_token, refresh_token,
  history_id (gmail), sync_token (calendar),
  last_synced_at, sync_status

calendar_events ───────────────────────────────────────
  id, org_id, event_id, summary, start_time, end_time,
  location, location_type (video/in-person/phone),
  meeting_type, organizer_email, is_recurring

calendar_event_attendees ──────────────────────────────
  event_id, email, display_name, response_status,
  contact_id → contacts

graph_segments ────────────────────────────────────────
  id, org_id, name, segment_type, contact_ids[], rules

context_calls ─────────────────────────────────────────
  id, org_id, entity_queried, agent_id, source,
  response_time_ms, cache_hit, created_at

activity_log ──────────────────────────────────────────
  id, org_id, event_type, event_data (JSON), created_at
```

### 6.3 Authentication & Authorization

```
                          ┌──────────────────┐
  Dashboard UI ──JWT───►  │                  │
                          │  FastAPI Auth    │
  AI Agents ──API Key──►  │  Middleware      │
                          │                  │
                          └────────┬─────────┘
                                   │
                          ┌────────▼─────────┐
                          │ Plan Enforcer    │
                          │                  │
                          │ - check_quota()  │
                          │ - check_rpm()    │
                          │ - check_contacts │
                          │ - gate_features  │
                          └──────────────────┘

  JWT: Dashboard routes (/api/org/*, /auth/*, /dashboard/*)
  API Key: Agent routes (/v1/context, /v1/graph/stats, /chat)
```

**Plan-gated features:**

| Capability | Trial | Hustler | Startup |
|-----------|-------|---------|---------|
| Context calls / period | 500 | 3,000 | 10,000 |
| Contacts | 100 | 300 | 2,000 |
| Integrations | Gmail | Gmail, Slack | All 9 |
| Sync frequency | Manual | 6h cron | Real-time + 6h |
| Query modes | Entity | + Temporal | + Semantic |
| Segments | 1 | 3 | 10 |
| API keys | 1 | 1 | 3 |
| Context depth | Shallow | Shallow | Full |

### 6.4 Sync Architecture

```
┌──────────────────────────────────────────────────┐
│              Sync Scheduler (hourly loop)         │
│  For each org: if elapsed > plan.sync_interval   │
│  → dispatch sync tasks per connected tool         │
└──────────────────────┬───────────────────────────┘
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
   ┌───────────┐ ┌───────────┐ ┌───────────┐
   │ Gmail     │ │ Calendar  │ │ Slack     │   ... (9 tools)
   │ Sync      │ │ Sync      │ │ Sync      │
   │           │ │           │ │           │
   │ history_id│ │ syncToken │ │ cursor    │  ← Incremental markers
   └─────┬─────┘ └─────┬─────┘ └─────┬─────┘
         │             │             │
         ▼             ▼             ▼
   ┌─────────────────────────────────────┐
   │       Ingestion Pipeline            │
   │  Parse → Classify → Extract →       │
   │  Score → Graph Builder → Store      │
   └─────────────────────────────────────┘
         │
         ▼
   ┌─────────────────────────────────────┐
   │    Nightly Refresh (2 AM)           │
   │  - Recalculate all scores           │
   │  - Run community detection          │
   │  - Compute indirect edges           │
   │  - Pre-compute frequent bundles     │
   │  - Generate weekly report (Mon)     │
   └─────────────────────────────────────┘
```

### 6.5 Context API Request Flow

```
Agent Request                              Response
    │                                         ▲
    ▼                                         │
┌─ Auth ──────────────────────────────────────┤
│  Validate API key → Resolve org             │
│  Check quota + RPM limit                    │
└─────────────────────┬───────────────────────┘
                      ▼
┌─ Cache ─────────────────────────────────────┐
│  Redis: context:{md5(org:entity:situation)} │
│  Hit? → return cached (60s TTL)             │
└─────────────────────┬───────────────────────┘
                      ▼ (miss)
┌─ Resolve ───────────────────────────────────┐
│  Exact match → Fuzzy match (70% threshold)  │
│  Returns match_confidence                   │
└─────────────────────┬───────────────────────┘
                      ▼
┌─ Assemble ──────────────────────────────────┐
│  Interactions (20/50/200 by plan)           │
│  Commitments (OPEN + OVERDUE)               │
│  Scores (5 dimensions)                      │
│  Disclosure rules + safe/avoid topics       │
│  Warm intro paths (if COLD/DORMANT)         │
│  72h cooldown check                         │
└─────────────────────┬───────────────────────┘
                      ▼
┌─ Recommend ─────────────────────────────────┐
│  block / escalate / warn / proceed          │
└─────────────────────┬───────────────────────┘
                      ▼
┌─ Generate ──────────────────────────────────┐
│  Context paragraph (PII-redacted)           │
│  Cache in Redis + Log to context_calls      │
└─────────────────────────────────────────────┘
```

### 6.6 Key API Endpoints

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/auth/register` | POST | — | Create account + org |
| `/auth/login` | POST | — | Get JWT token |
| `/auth/{tool}/connect` | GET | — | OAuth redirect |
| `/v1/context` | POST | API Key | Get context bundle |
| `/v1/context/refresh` | POST | API Key | Force cache refresh |
| `/v1/graph/stats` | GET | API Key | Graph health metrics |
| `/api/org/{id}/graph` | GET | JWT | Graph topology |
| `/api/org/{id}/contacts` | GET | JWT | Contact list |
| `/api/org/{id}/sync` | POST | JWT | Trigger manual sync |
| `/dashboard/metrics` | GET | JWT | Dashboard stats |
| `/activity` | GET | JWT | Activity feed |
| `/chat` | POST | API Key | Natural language query |
| `/billing/order` | POST | JWT | Create payment |
| `/billing/verify` | POST | JWT | Verify payment |

### 6.7 Database Stats

- **46 migrations** (001–046)
- **40+ tables** (core + per-tool)
- **23 route files** with 80+ endpoints
- **9 ingestion connectors** with bridge modules
- **14 background task files**

---

*Generated from codebase analysis — reflects current implementation as of 2026-04-02.*
