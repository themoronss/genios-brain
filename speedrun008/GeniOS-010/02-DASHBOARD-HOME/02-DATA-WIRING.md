# 02.2 · Data wiring: every route, every field, where it lands

**Written for:** Harsh.

**Rules:**
- The home page reads **only routes the brain already serves**. No brain change was made for it.
- Everything turns brain JSON into what the screen draws in one file, `homepage/live.ts`. It is pure functions with no React, so it can be tested.
- `homepage/data.ts` declares the types, plus the sample values in the same shape.

---

## 1 · The fetch

`company-intelligence-home.tsx`, live mode only:

```ts
getHomeSummary()            → inputs.summary   // gates the page: success → "ready", failure → "error"
getFirstScanReport()        → inputs.scan      // each of these four fills in when it lands;
getActivityFeed(100)        → inputs.activity  // a failure leaves it null
getNetworkHealth()          → inputs.network
getIntegrationsStatus()     → inputs.sources
```

- Each one sets its own key with `setInputs(prev => ({ ...prev, [key]: value }))`. A slow route never holds the page.
- While `home-summary` is loading, the week cards show four grey skeleton cards. If it fails, they show "Couldn't load your dashboard right now — Refresh to retry."

`GeniosAtWork` also reads three routes itself in `useExtra()`, each tolerant on its own:

```ts
getWeeklyReport()   → the "Done instantly from your screen" tile
listAgents()        → AER step 1: agents with status active AND ≥1 connector ("can act")
listDelegations()   → AER steps 2–3: approved/dispatched/succeeded/failed count · succeeded count
```

## 2 · Route by route

### `GET /api/org/{org}/home-summary`

`genios_engine/api/home_routes.py · home_summary`

| Field | Used for | Notes |
|---|---|---|
| `cards[key=situations]` (`value`, `unit`, `delta`, `direction`, `bars`) | Week card "Situations formed"; flow stage 3; checks; HIR readiness step 2 | `value` = active `context_situations` with `computed_at` in 7 days |
| `cards[key=verified]` | Week card "Situations closed / outcome checked"; flow stage 5; HIR readiness step 3 | ⚠ = **all** `execution_outcomes` rows in 7 days, including `expired_untouched` and `completed_unproven`. It is not "with proof", so it is labelled "outcome checked" |
| `cards[key=decisions]` | **not shown** | ⚠ `decisions` is written only by `api/intelligence_routes._persist_decision_envelope`: an answer to an intelligence-API question, not a card. Showing it as "Decisions prepared" made the flow claim a stop that was not there |
| `cards[key=intervention]` | **not shown** | the old meaning (notify/flag share of decisions) clashes with HIR; see `03-AER-HIR.md` |
| `snapshot.health[]` | The health strip; check "No action bypassed a hard rule" | ⚠ `policy_safe` is 0% when `decisions_7d = 0`. On a fresh workspace it reads "0% Policy-safe actions", which sounds alarming. See `05-BRAIN-WORK.md` |
| `snapshot.notice` | **not shown anymore** | "Your company is becoming more proactive." is hard-coded in the brain |
| `graphKnowledge[]` (`label`, `value`, `change`, `live`) | Counts strip in "What the brain holds" | Matched **by label**: `Facts`, `Entities`, `Relationships`, `Documents indexed`, `Active sources`. `Context calls served` is skipped (it is `decisions_7d`) |

### `GET /api/org/{org}/first-scan`
`footprint.items_read` and `footprint.facts` → flow stages 1–2 ("all time") and the headline sentence.

### `GET /activity?limit=100`

`api/routes.py · activity_feed`

- **Returns:** live cards (`insight_generated`, with `event_data.title` and `event_data.badge_label` = urgency band) plus people/company nodes (`contact_created` / `contact_updated`). It is newest-first and cut to 100.

| Used for | How |
|---|---|
| "Latest changes" feed | First 20 rows: card → ✦, new → person+, updated → ↻ |
| Flow stage 4 "Cards raised" · tile "Cards raised this week" · change "Cards raised" | `insight_generated` in the last 7 days, by `badge_label` |
| Changes "New / Updated people and companies" | `contact_created` / `contact_updated` in 7 days |

⚠ **Two limits:**
- Only **live** cards are listed (not expired or resolved), so "cards raised this week" undercounts cards already closed.
- If 100 rows come back, counts get a "+" and a 0 becomes unknown (`live.ts · cardsThisWeek`).

A proper weekly count needs a brain field; see `05-BRAIN-WORK.md`.

### `GET /api/org/{org}/network-health`

| Field | Used for |
|---|---|
| `network_health.active_now / warm / needs_attention / cold` | Tile "People and companies active this week" (bar); Business health "going well" = active + warm |
| `open_commitments.total / overdue` | Change "Commitments tracked"; Business health "need you" = cooling + overdue; check "N commitments are past the due date" |

`at_risk` (90+ days quiet, or never) is **not** counted as "going wrong". On a mail-heavy graph it is most nodes, and it would swamp the bar.

### `GET /integrations/status?scope=workspace`

`api/routes.py`. Per tool: `connected`, `freshness` (`healthy` ≤ 6h · `aging` ≤ 24h · `stale` · `error`), `lastSyncAt`, and `metadata.recordsPulled / factsExtracted / entitiesExtracted`.

These feed:
- **"Where it comes from":** items, facts and people per source, ordered failing → healthy;
- the source checks;
- HIR readiness step 1 ("Sources being read · N connected").

Labels: `gmail → Gmail`, `googlecalendar → Google Calendar`, and so on (`live.ts · SOURCE_LABELS`).

### `GET /v1/seats/me/weekly-report`

`api/moment_routes.py · weekly_report`

- **This seat only.**
- `promises_caught + asks_flagged + deadlines_flagged + risks_flagged` → the tile "Done instantly from your screen", and the Screen page's "Done instantly" lane.

### `GET /v1/agents`, `GET /v1/delegations`
AER readiness only:
- an agent that can act = active with ≥1 connector;
- a step approved = a delegation in approved / dispatched / succeeded / failed;
- a step proven done = succeeded.

## 3 · The builders in `live.ts`

| Function | Returns | Tested by |
|---|---|---|
| `liveContextFlow(inputs, now)` | the brain card: headline, 5 stages, changes, feed (≤20), sources, health, `sourcesUnknown` | §4 below |
| `stoppedAt(stages)` | index of the first 0-after-non-0 stage, or −1 | §4 |
| `liveHeadlineCards(inputs)` | the 4 week cards (goals 0 + flat weeks; situations; closed; health split) | §4 |
| `liveChecks(inputs, flow)` | the working / needs-attention rows | §4 |
| `cardsByUrgency(activity, now)` | this week's cards by band, or null | — |

The tile, readiness and goal helpers live in `sections/genios-at-work.tsx`: `liveTiles`, `aerSteps`, `hirSteps`, `readiness`.

## 4 · How it was checked

The checks were done by hand. The dashboard repo has no unit-test runner set up.

- **Builders:**
  - `live.ts` was run under `node --experimental-strip-types` against inputs shaped exactly like the brain's JSON;
  - it was run again with every input except `home-summary` null;
  - the outputs were read: stage values, the stop index, check sentences, the null paths.
- **Rendering:** the signed-in page ran against `tools/mock_brain.py`, which serves those same shapes. Screenshots were taken at 1440 and 1024 wide.
- **Build:** `tsc --noEmit` and `next build` are green.

If you add tests, start with `stoppedAt` and `liveChecks`. They are where a wrong sentence would reach a customer.
