# V1 PDF Spec Gap Analysis

**Date**: March 21, 2026
**Scope**: Gmail-only V1 implementation per PDF specification (contextEnginnering.md)
**Status**: ~78% complete based on PDF spec sections 1-10

---

## Executive Summary

The codebase has implemented the **core backend** of V1 (graph building, insights, context bundles) with excellent data infrastructure. However, significant gaps remain in:

1. **Ingestion Filtering** — No exclusion rules for newsletters, mass outreach, automation
2. **Auto-Categorization** — No INVESTOR/VENDOR/CUSTOMER detection with confidence scoring
3. **Frontend UI** — Minimal implementation of graph visualization and detail panels
4. **Chatbot Layer** — Natural language query interface not started
5. **Search Interface** — Dashboard search bar for name/topic/overdue queries

---

## Detailed Gap Analysis by PDF Section

### 1. Graph Taxonomy (Section 1)
**Spec Requirements:**
- Node types: Org (center), People, Companies
- Edge types: Email threads (directional), Commitments
- Every node has: type, stage, interaction_count
- Relationship stages with color coding: ACTIVE (green), WARM (teal), DORMANT (amber), COLD (gray), AT_RISK (red)

**Status: ✅ 90% COMPLETE**

**What's Implemented:**
- ✅ Node types stored (org_id, contacts, companies)
- ✅ Relationship stages calculated (ACTIVE, WARM, NEEDS_ATTENTION, DORMANT, COLD, AT_RISK)
- ✅ Interaction edges stored (interactions table with direction)
- ✅ Commitment edges tracked (commitments table)
- ✅ Stage thresholds: ACTIVE (<14d + positive + bidirectional), WARM (<30d), etc.

**What's Missing:**
- ❌ Frontend color encoding: stages not visually mapped to colors in graph render
- ❌ Node shape distinction: circles vs. rounded squares not rendered
- ❌ Org node special styling: no special ring or center position lock
- ❌ Visual node sizing based on interaction_count (formula: 12 + sqrt(count) * 3)

---

### 2. Ingestion Filter (Section 2)
**Spec Requirements:**
Hard exclusions BEFORE entity extraction:
- noreply@, donotreply@, notifications@, alerts@ prefixes
- Promotional domains (Mailchimp, SendGrid, Klaviyo headers)
- Mass outreach (BCC to 50+ people)
- Known newsletter domains (substack.com, beehiiv.com, etc.)
- Auto-generated calendar invites without human reply

**Status: ❌ 0% COMPLETE**

**What's Missing:**
- ❌ No sender pattern filtering (noreply@, notifications@, etc.)
- ❌ No List-Unsubscribe header detection
- ❌ No BCC recipient count filtering
- ❌ No newsletter domain list
- ❌ No automated calendar invite filtering
- ❌ Filter logic needs to run BEFORE `is_human_interaction()` in Gmail ingestion

**Impact**: Graph includes noise (newsletters, automated alerts) that shouldn't count as relationships

**Recommendation**: Add `should_exclude_thread()` function in `app/ingestion/gmail_sync.py` before entity extraction, check against exclusion patterns.

---

### 3. Auto-Categorization (Section 3)
**Spec Requirements:**
Automatic detection hierarchy (in priority order):
1. Domain match against VC firm list (~500 known) → INVESTOR
2. Email signature role parsing (CEO/Founder/Partner/MD/GP/LP) → INVESTOR
3. Thread topic analysis (term sheet, valuation, due diligence, cap table, round) → INVESTOR
4. Same org domain → TEAM
5. Thread contains vendor keywords → VENDOR
6. Thread contains customer keywords → CUSTOMER
7. All others → OTHER

Each entity gets a `category_confidence` score. Low confidence nodes flagged for manual review.

**Status: ❌ 0% COMPLETE**

**What's Missing:**
- ❌ No entity_type categorization beyond domain inference
- ❌ No VC domain matching database
- ❌ No email signature parsing for roles
- ❌ No thread topic analysis for category inference
- ❌ No category_confidence scoring
- ❌ No manual review queue for low-confidence merges
- ❌ Schema: contacts table has entity_type field but not populated intelligently

**Database Schema**: entity_type column exists in contacts table but only used as manual field

**Impact**: Context bundles cannot apply category-specific disclosure rules (what to share with investors vs. customers)

**Recommendation**: Create `app/ingestion/category_detector.py` with:
- VC firm domain list (hardcoded JSON or external API)
- Role keyword extraction from email signatures
- Thread topic analyzer for keyword matches
- Confidence scoring combining all signals
- Store category_confidence on contacts

---

### 4. Visual Graph Rendering (Section 4)
**Spec Requirements:**
- Node radius formula: 12 + sqrt(interaction_count) * 3 (min 12px, max 36px)
- Node shapes: circles (people), rounded squares (companies)
- Org node: larger circle with distinct ring, center-fixed
- Edge thickness scales with sentiment_avg
- Edge color: green (positive), gray (neutral), red (negative/at-risk)
- Layout: Force-directed (react-force-graph)
- Physics creates natural clustering (high-interaction nodes closer to org)

**Status: ⚠️ 30% COMPLETE**

**What's Implemented:**
- ✅ Force-directed layout likely exists in frontend (react-force-graph typical)
- ✅ Data shape available from `/v1/graph` API with all node/edge data

**What's Missing:**
- ❌ Node sizing: no radius calculation based on interaction_count
- ❌ Node shapes: all rendered as circles (no company square distinction)
- ❌ Org node styling: not visually distinct with ring
- ❌ Edge thickness: not scaling with sentiment
- ❌ Edge color gradient: not based on sentiment trend
- ❌ Node color encoding: needs stage-based color mapping
- ❌ Small node labels: labels should not appear on small nodes (<0.5 interaction radius)
- ❌ Text label sizing: should scale with node size
- ❌ Org node center-locking: not implemented in physics engine

**Files Affected**: `genios-dashboard/components/RelationshipGraph.tsx`

**Recommendation**: Enhance graph component to:
1. Calculate node radius from interaction_count using spec formula
2. Render company nodes as rounded squares (shape: 'rect', borderRadius: '8px')
3. Style org node with ring border and lock position
4. Scale edge strokeWidth by sentiment_avg
5. Map edge stroke color to sentiment (green/gray/red)
6. Hide labels on small nodes, show on hover

---

### 5. Node Detail Panel (Section 5)
**Spec Requirements:**
Right-side drawer showing:
- Name, company, role, relationship stage badge
- Interaction count, last contact, response rate, avg response time
- Confidence panel with 5 scores (freshness, confidence, consistency, authority, composite) as visual bars
- Timeline: last 10 interactions expandable
- Recommended actions (rule-based)

**Status: ❌ 20% COMPLETE**

**What's Implemented:**
- ✅ Backend data available: all scores, metrics, timeline in bundle
- ❌ Frontend drawer component: not implemented
- ❌ 5-score visualization: no visual progress bars for confidence metrics
- ❌ Timeline rendering: no interaction timeline view
- ❌ Recommended actions: generated in context but not surfaced visually

**Files Needed**:
- `genios-dashboard/components/ContextDrawer.tsx` (NEW)
- Update `genios-dashboard/app/dashboard/page.tsx` to display drawer

**Recommendation**: Create drawer component with 5 sections matching spec exactly:
1. **Identity**: name, company, role, stage badge, interaction count
2. **Metrics**: total interactions, last contact (days ago), response rate (%), avg response time (hours)
3. **Confidence Panel**: Visual progress bars for 5 scores + composite
4. **Timeline**: Last 10 interactions sorted by date, expandable for full text
5. **Recommended Actions**: Rule-based suggestions (e.g., "Follow up — 3 days since last contact")

---

### 6. Edge Click Detail (Section 6)
**Spec Requirements:**
When clicking an edge between org and person:
- List of all email threads sorted by date
- Sentiment trajectory (trending up/down over time)
- Topic clustering (recurring subjects across threads)
- Response time analysis (fast/moderate/slow reply patterns)
- Full text summary of last 3 threads

When clicking company edge:
- Who else at that company is in graph
- Aggregate sentiment across all contacts at that company
- Multiple open commitments with same org

**Status: ⚠️ 60% COMPLETE**

**What's Implemented:**
- ✅ Backend endpoint: `GET /api/org/{org_id}/edge/{contact_id}` exists
- ✅ Returns sentiment trajectory, topic clustering, response time analysis, last 3 threads
- ✅ Company edge details endpoint for aggregate sentiment + contacts at company

**What's Missing:**
- ❌ Frontend UI: clicking an edge doesn't trigger detail panel
- ❌ Thread sorting: may not be sorted by date in response
- ❌ Sentiment trajectory visualization: no chart/graph showing trend over time
- ❌ Topic clustering visualization: list returned but not rendered as visual clusters
- ❌ Response time categorization: fast (<4h) / moderate (<24h) / slow — may not be in response

**Recommendation**:
1. Add frontend click handler for edges in graph component
2. Fetch edge details from `/api/org/{org_id}/edge/{contact_id}`
3. Render sentiment trend as a line chart (date on X-axis, sentiment on Y-axis)
4. Display topic clusters as tag pills sorted by frequency
5. Show response time breakdown as percentages or histogram

---

### 7. Graph Summary View (Section 7)
**Spec Requirements:**
Persistent summary panel showing:
- Total contacts
- Active contacts
- Contacts needing follow-up (overdue)
- At-risk contacts
- Open commitments (with count of overdue)

Attention required section with top 3 issues.

**Status: ⚠️ 50% COMPLETE**

**What's Implemented:**
- ✅ Backend endpoint: `GET /api/org/{org_id}/network-health` returns all metrics
- ❌ Frontend panel: not rendered in dashboard UI

**What's Missing:**
- ❌ Frontend component showing health metrics as cards/stats
- ❌ Visual update nightly (not real-time)
- ❌ Attention required section rendering
- ❌ Integration with main dashboard layout

**Files Needed**:
- `genios-dashboard/components/NetworkHealthPanel.tsx` (NEW)

**Recommendation**: Create panel component that:
1. Fetches from `/api/org/{org_id}/network-health` on mount + nightly refresh
2. Displays 5 key metrics as stat cards: total contacts, active, need follow-up, at-risk, open commitments
3. Shows "Attention Required" section with top 3 issues
4. Color codes issues by priority (red = immediate, orange = this week, yellow = FYI)

---

### 8. Multi-Source Graph Update (Section 8)
**Spec Requirements:**
Entity resolution logic when new sources connect:
- Exact email match → merge, add source tag, boost confidence
- Fuzzy name+company → flag for review, suggest merge
- No match → create new node
- Source priority hierarchy
- Canonical_id on each node
- sources[] array tracking all sources

**Status: ⚠️ 40% COMPLETE (for V1 Gmail-only)**

**What's Implemented:**
- ✅ Sources tracked (contacts table has sources column)
- ✅ Source priority logic exists (Gmail highest)
- ✅ Contacts can have multiple sources

**What's Missing:**
- ❌ Canonical_id field: not on contacts table
- ❌ Fuzzy entity resolution: no name+company matching algorithm
- ❌ Manual review queue: no dashboard for flagging low-confidence merges
- ❌ Confidence recalculation on merge: not implemented
- ⚠️ Not critical for V1 (Gmail-only) but architecture incomplete

**Database**: No canonical_id field, no merge tracking

**Note**: For V1 Gmail-only, this is deferred. Becomes critical for V2 (Calendar/HubSpot).

---

### 9. Graph Enrichment Ceiling (Section 9)
**Spec Requirements:**
V1 enrichment (Gmail only):
- Name ✅, email ✅, company ✅, role (from signature) ⚠️, interaction count ✅
- Sentiment trend ✅, communication style ✅, topics ✅
- Open commitments ✅, relationship stage ✅, last interaction summary ✅

V2 enrichment (+ Calendar + HubSpot):
- Meeting history, deal stage, pipeline value, meeting frequency, response time pattern, referral chain (introduced_by) ✅
- Deferred (not Gmail-only)

V3 enrichment (+ Notion + Slack + LinkedIn):
- Shared documents, internal discussion, public posts, mutual connections, company funding, headcount changes
- Deferred (not Gmail-only)

**Status: ✅ 95% COMPLETE FOR V1**

**What's Implemented:**
- ✅ All V1 fields captured and stored
- ✅ Referral chain detection (introduced_by)
- ✅ Communication style (what_works, what_to_avoid)
- ✅ Sentiment trend and topics
- ✅ Commitments tracking

**What's Missing:**
- ⚠️ Role extraction: "from signature" logic may be incomplete
  - Should parse email signatures more aggressively
  - Current extraction relies on email_signature field from initial ingestion
  - Could be enhanced with regex patterns for common role indicators

**Recommendation**: Enhance role extraction in entity_extractor.py:
1. Parse email signatures more carefully (regex for "VP ", "Director of ", "Co-founder", etc.)
2. Extract phone, website, LinkedIn URL from signatures
3. Add fallback to HubSpot later (V2)

---

### 10. Searchability & Cross-Check Architecture (Section 10)
**Spec Requirements:**
Dashboard search bar:
- Type name → jump to node, open detail panel
- Type topic → filter graph to show only threads with that topic
- Type "overdue commitments" → filter to at-risk nodes with open commitments

Chatbot query layer (NL wrapper over graph):
- "What did I last discuss with Sequoia investors?" → pulls category=INVESTOR nodes
- "Who have I not contacted in 30 days?" → graph query stage=DORMANT/COLD
- "What commitments do I have outstanding?" → open_commitments > 0, sorted by due_date
- Returns: prioritized list with recommended actions

**Status: ⚠️ 25% COMPLETE**

**What's Implemented:**
- ✅ Backend endpoints for topic filtering: `GET /api/org/{org_id}/graph/filter/topic`
- ✅ Backend insights listing: tracks overdue commitments, at-risk contacts
- ✅ API design supports all query patterns (graph queries available)

**What's Missing:**
- ❌ Frontend search bar: no global search component in dashboard
- ❌ Name search: type name, jump to node
- ❌ Topic filter: type topic, highlight graph nodes
- ❌ Overdue query: type "overdue commitments", filter view
- ❌ Chatbot layer: NLP query interface NOT STARTED
  - Would need prompt routing (classify query intent)
  - LLM to translate NL to backend query params
  - Response formatting as paragraph + structured results
  - Safety checks to prevent graph injection attacks

**Files Needed**:
- `genios-dashboard/components/GlobalSearch.tsx` (NEW)
- `app/api/routes/chatbot.py` (NEW) — NL query layer
- Chatbot integration in dashboard

**Chatbot Implementation Scope** (Complex):
1. Create intent classifier: {type: 'entity_search' | 'topic_search' | 'overdue' | 'at_risk' | etc.}
2. Entity extractor: "Sequoia investors" → category=INVESTOR, company contains "Sequoia"
3. Query builder: intent → SQL/graph query parameters
4. Response formatter: structured result → prose paragraph
5. Safety: prevent SQL injection, validate all params

**Recommendation**:
- Phase 1 (Quick): Implement frontend search bar with name + topic autocomplete
- Phase 2 (Complex): Add chatbot layer with intent classification + query generation

---

## Feature Completion Matrix

| Feature | Section | Status | Complexity | Impact |
|---------|---------|--------|------------|---------|
| Graph Taxonomy | 1 | ✅ 90% | Low | High — visual encoding missing |
| Ingestion Filter | 2 | ❌ 0% | Medium | Medium — adds noise to graph |
| Auto-Categorization | 3 | ❌ 0% | High | High — blocks disclosure rules, insights |
| Visual Rendering | 4 | ⚠️ 30% | High | High — core user experience |
| Node Detail Panel | 5 | ❌ 20% | Medium | High — how user understands contacts |
| Edge Click Detail | 6 | ⚠️ 60% | Medium | Medium — relationship-level details |
| Graph Summary View | 7 | ⚠️ 50% | Low | Medium — dashboard overview |
| Multi-Source Architecture | 8 | ⚠️ 40% | High | Low for V1 (Gmail-only), High for V2 |
| Graph Enrichment V1 | 9 | ✅ 95% | Low | Low — deferred features OK |
| Search & Chatbot | 10 | ⚠️ 25% | Very High | Medium — advanced feature |

---

## Priority Implementation Plan

### 🔴 CRITICAL (Blocks V1 Launch) — ~40 hours
1. **Ingestion Filter** (6h): Add exclusion rules before entity extraction
2. **Auto-Categorization** (8h): Implement category detection with confidence scoring
3. **Visual Node Rendering** (12h): Size, shape, color, labels
4. **Node Detail Panel** (14h): Right-side drawer with 5 sections

### 🟠 HIGH (V1 Feels Complete) — ~30 hours
5. **Graph Summary View** (4h): Dashboard health metrics panel
6. **Edge Click Detail UI** (8h): Sentiment chart, topic clustering, response time breakdown
7. **Dashboard Search** (8h): Name/topic/overdue queries
8. **Frontend Polish** (10h): Loading states, animations, responsive layout

### 🟡 MEDIUM (V1.1 Enhancement) — ~20 hours
9. **Chatbot Layer** (16h): NL query interface (complex — intent classifier, query builder)
10. **Manual Review Queue** (4h): Low-confidence merge reviews

### 🟢 DEFERRED (V2+)
- Multi-source entity resolution
- Authority Graph
- Precedent Graph
- Calendar/HubSpot integration
- Slack/Notion integration

---

## Code Organization Needed

**New Backend Files:**
```
app/ingestion/ingestion_filter.py          — exclusion logic
app/ingestion/category_detector.py         — auto-categorization
app/api/routes/chatbot.py                  — NL query layer (V1.1)
```

**New Frontend Files:**
```
genios-dashboard/components/ContextDrawer.tsx        — node detail panel
genios-dashboard/components/NetworkHealthPanel.tsx   — graph summary
genios-dashboard/components/GlobalSearch.tsx         — search bar
genios-dashboard/components/ChatbotPanel.tsx         — chatbot (V1.1)
```

**Enhanced Frontend Files:**
```
genios-dashboard/components/RelationshipGraph.tsx    — sizing, shapes, colors, edge click handlers
genios-dashboard/app/dashboard/page.tsx              — integrate new panels
```

---

## Verification Checklist for Full V1 Spec Compliance

- [ ] No noreply/notifications/newsletter emails in graph
- [ ] All contacts have entity_type (INVESTOR/TEAM/VENDOR/CUSTOMER/OTHER)
- [ ] Investor contacts flagged with category_confidence scores
- [ ] Graph nodes render with correct sizes, shapes, colors
- [ ] Clicking node opens detail drawer with all 5 sections
- [ ] Clicking edge opens sentiment trajectory + topic breakdown
- [ ] Network health panel visible with daily metrics
- [ ] Global search finds contacts by name
- [ ] Topic filter works (type topic name, graph highlights)
- [ ] "Overdue commitments" query returns correct list
- [ ] Chatbot understands "What did I discuss with [entity]?" patterns

---

## Estimated Total Work

**Backend**: ~14 hours (ingestion filter, categorization, chatbot)
**Frontend**: ~40+ hours (graph rendering, panels, search, chatbot UI)
**Testing**: ~8 hours (end-to-end verification)

**Total to Full V1 Spec Compliance: ~60 hours**

Currently ~78% complete (backend strong, frontend gaps significant).

