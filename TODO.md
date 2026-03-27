# GeniOS Brain - What's Left (per MVP V1 PDF Spec)

**Overall completion: ~95%**

---

## ALREADY DONE (verified in code)

These were previously listed as gaps but are actually implemented:

- **Node shape encoding** — Star=Self, RoundedSquare=Org, Diamond=Unknown, Circle=Person (`RelationshipGraph.tsx:163-184`)
- **Confidence ring** — Solid (>0.75), Dashed (0.45-0.75), Dotted (<0.45) (`RelationshipGraph.tsx:186-201`)
- **Per-type freshness half-lives** — relationship_stage=12h, role=30d, communication_style=90d, historical/commitment=no decay (`bundle_builder.py:145-151`)
- **Edge encoding** — Thickness by interaction count, color by sentiment, dashed for one-sided (`RelationshipGraph.tsx:244-278`)

---

## HIGH Priority

### 1. Mr. Elite Chatbot - Wire into UI
- **PDF says:** Slide-up panel, persistent across all pages, fast response (<400ms)
- **Status:** `MrEliteChatbot.tsx` fully functional but NOT rendered in `DashboardLayout.tsx`
- **Fix:** Import and render in dashboard layout (~3 lines)
- **Files:** `genios-dashboard/components/DashboardLayout.tsx`

### 2. Configurable Cron Sync Intervals
- **PDF says:** 6/12/18/24 hour cron options for Gmail sync
- **Status:** Only 24h nightly refresh + manual sync. Settings UI has selector but backend ignores it
- **Fix:** Add `sync_interval_hours` to orgs table, rewrite scheduler to check per-org intervals
- **Files:** `app/main.py`, `app/api/routes/sync.py`, migration SQL

---

## MEDIUM Priority

### 3. Cooldown System
- **PDF says:** Email sent=72h, Meeting=24h, Inbound=0h cooldowns
- **Status:** Not implemented
- **Fix:** Check last outbound timestamp in bundle builder, add `cooldown_active` to bundle
- **Files:** `app/context/bundle_builder.py`

---

## LOW Priority

### 4. Notification Bell Dropdown
- **Status:** Bell icon exists but no dropdown panel
- **Fix:** Add dropdown with overdue commitments + recent activity
- **Files:** `genios-dashboard/components/DashboardLayout.tsx`

### 5. Theme Toggle Button
- **Status:** Dark mode works but no visible toggle
- **Fix:** Add Sun/Moon button in top bar
- **Files:** `genios-dashboard/components/DashboardLayout.tsx`

### 6. Graph Legend Toggle
- **Status:** Not implemented
- **Fix:** Collapsible legend overlay on graph
- **Files:** `genios-dashboard/app/dashboard/page.tsx`

### 7. Keyboard Shortcuts
- **Status:** Not implemented
- **Fix:** Cmd+K=search, Cmd+C=copy context
- **Files:** `genios-dashboard/app/dashboard/page.tsx`

### 8. Token Budget Management
- **Status:** No explicit token counting in bundle builder
- **Fix:** Add token estimation and truncation
- **Files:** `app/context/bundle_builder.py`

### 9. Dynamic llms.txt Endpoint
- **Status:** Static file only
- **Fix:** Add `GET /v1/llms.txt` per-org endpoint
- **Files:** `app/api/routes/context.py`

---

## NOT in V1 Scope (V2/V3+)

- POST /decide endpoint (V3+)
- Cross-agent collision detection (V2)
- Calendar/Slack/HubSpot/WhatsApp integrations (V2)
- Multi-user orgs (V2)
- SDK wrapper (V3+)
- Advanced search (topic-based) (V2)
- Custom entity types (V2)
- Agent personas (V3+)
- Context page static knowledge sections (V2)
