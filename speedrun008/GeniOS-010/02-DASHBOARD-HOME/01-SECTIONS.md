# 02.1 · Each section: what it shows, live and sample

**Written for:** Harsh.

All home components live in `src/product/internal/dashboard/homepage/`. "Live" means a signed-in customer; "sample" means `?demo=1`. Exact route fields are in `02-DATA-WIRING.md`.

---

## 1 · This month's goal

**Heading:** "This month's goal", with a pill showing the month and year.

**Live today:**
- There is no goal object yet (GeniOS-009 G1 is not built). The panel (`MonthOnly`) shows only what is true:
  - a ring of how much of the month has gone, e.g. 71% of October, day 22 of 31, 9 days left;
  - next to it, a faded, greyscale preview of three goal rows, under the note "Goals are coming next…".
- Nothing in it is a number about the customer.

**Sample, and the target once G1/G5 exist** (`MonthPace` + `GoalRows`):
- **A donut by status:** done (green) · on track (ink) · at risk (orange) · blocked (red). The centre reads "3/5 done or on track".
- **A pace panel:**
  - "October · day 22 of 31";
  - the **average progress** of the goals that have a countable measure, e.g. 81%;
  - an "Ahead of / Behind pace by N pts" pill: average progress minus % of the month gone;
  - a bar with a **dark "today" marker**, i.e. where every goal should be by now.
- **One row per goal:**
  - name, a status chip, and "department · due · open situations";
  - a progress bar with the same today marker, the % at the right, and the progress text under it;
  - **unknown progress is a striped bar with "?"** and "Progress unknown — {why}", never 0.
- The shape the rows expect, and how it maps onto GeniOS-009, is in `03-GOALS/README.md`.

## 2 · Automation and intervention (AER · HIR)

Two `MetricPanel` cards. Definitions and the brain work they need are in `03-AER-HIR.md`.

**Every card, top to bottom:**
1. Title + short tag (`AER` / `HIR`), one-line meaning, and a "Last 8 weeks" pill.
2. A semicircle **gauge**, with a summary to its right.
3. An 8-week **trend chart**. It uses monotone curves, a 0–100% axis and Monday week labels. Hover shows a crosshair with that week's value and change.
4. **One folded row** with a Show / Hide toggle. It is folded by default: Rohit asked that the cards end at the chart to save space. Opened, it shows the breakdown and the factor list.

| | Sample (has a measurement) | Live today (no measurement) |
|---|---|---|
| Gauge | the value, e.g. 38%, with a green **target tick** | **% ready to measure** = steps in place ÷ steps (e.g. HIR **67% ready**) |
| Beside it | "+7 pts from last week" pill · basis ("24 of 64 steps this week") · "Target 50% · 12 pts to go" | "Not measured yet" pill + why |
| Chart | the series, with a target line | a **dotted ghost line** + note "The dotted line is the shape it will take, not a value" |
| Folded row label | AER: "Who did the work, and what moves this number" · HIR: "Why you stepped in, and what brings it down" | "What it needs before it can be measured · NN% ready" |
| Opened | AER: a stacked bar of who finished the week's steps · HIR: a stacked bar of resolved situations with and without you, bars of "why you stepped in", and the "not counted: decisions rightly yours" note. Then the factor list. | the readiness checklist (✓ / ○ / — unknown) with a live detail per step, then the factor list |

**AER is locked in live mode:**
- The card renders at **35% opacity with a 3px blur**, so it cannot be interacted with.
- On top: a lock badge, "Automation is locked", "It opens when an agent can act for you — 0% ready. Until then GeniOS prepares the work and you do it." and a **Connect an agent** button to `/dashboard/agents`.
- Today the lock comes off only in sample mode. Once the brain serves a real AER, show it unlocked; see `03-AER-HIR.md`.

**Note:** the readiness used to read "2/3". Rohit found that unclear, so it is a percentage everywhere: the gauge, the checklist header and the lock note.

## 3 · Activity this week

Three tiles. Each has a label, an icon box, a big number, a stacked bar and a legend.

| Tile | Number | Bar parts | Live source |
|---|---|---|---|
| People and companies active this week | `activeNow` | active this week · warm · cooling · cold | `network-health` |
| Cards raised this week | cards created in the last 7 days | critical · high · standard (`badge_label`) | `/activity` |
| Done instantly from your screen | promises + asks + deadlines + risks | promises · asks · deadlines · risks | `/v1/seats/me/weekly-report` (this seat) |

If a route fails, the tile shows "—" with an empty bar.

## 4 · This week at a glance

Four cards (`headline-cards.tsx`).

**Every card has:**
- a label and an icon box;
- a big number with its unit;
- "↗ +8% from last week", coloured by tone;
- a bar chart of 12 weeks with the last 3 highlighted, or a split bar for Business health;
- one note line.

**One card is dark:** the first whose value is not 0 or "—". Rohit's references lead with one dark card, and a dark zero leads with nothing.

| Card | Live value | Note |
|---|---|---|
| Goals formed | **0** with flat weeks (no goal object yet) | from G1: goals created this month |
| Situations formed | `home-summary.cards[key=situations]` | value, unit "from N signals", 12-week bars, delta: all the brain's |
| Situations closed | `home-summary.cards[key=verified]`, relabelled "outcome checked" | the brain counts **every** `execution_outcomes` row, not only proven ones, so the label must not say "with proof" |
| Business health | going well = active + warm; need you = cooling + overdue commitments | `network-health`; split bar green / red |

**Removed from this row:**
- **Intelligent Decisions.** The brain's `decisions` table holds intelligence-API answers, not cards (see `02-DATA-WIRING.md`).
- **Human intervention.** It now lives as HIR in section 2.

## 5 · What is working, what is not

- **A summary card:** "NN% of checks are fine" plus a stacked bar (working / to watch / broken).
- **Two columns below:** **Working** and **Needs attention**. Each item has a coloured left edge and a "Fix ↗" link where one exists. Both columns are fixed at 320px and **scroll inside**.
- **Live checks come from `live.ts · liveChecks()`:**

| Check | Tone | From |
|---|---|---|
| "{sources} are being read on time" | good | `/integrations/status` freshness `healthy` |
| "{source}: the last sync failed — reconnect it" / "has stopped syncing" | broken | freshness `error` / `stale` |
| "{source} has not synced recently" | watch | freshness `aging` |
| "No source is connected, so nothing new is read" | broken | no connected source |
| "Nothing reaches "{stage}" this week, though "{prev}" has N" | broken | the flow (section 7) stops at a stage |
| "N situations formed this week" | good | `home-summary` |
| "N commitments are past the due date" | watch | `network-health.open_commitments.overdue` |
| "N relationships are cooling off (30–60 days quiet)" | watch | `network-health.needs_attention` |
| "No action bypassed a hard rule" | good | `snapshot.health` "Policy-safe actions" = 100% |
| "No goals set yet…" · "No agent is connected yet…" | watch | always added today; remove them when G1 and agents land |

## 6 · Decisions over time · Recent decisions (sample only)

These two components already existed but were hidden. They now render **only in sample mode**, because nothing in the brain feeds them yet. Do not show them live until a route does.

## 7 · What the brain holds

One white card (`ContextMoving`). The heading reads "What the brain holds", with an **Open the graph** button. Rohit asked for it formal: white, with light-gray panels inside, and no gradients or glass.

**Inside, top to bottom:**
1. **Counts strip** (`KnowledgeStrip`): facts · people and companies · relationships · items read · sources, all on one line. It reads `home-summary.graphKnowledge` and leaves out "Context calls served" (see `02-DATA-WIRING.md`).
2. **A one-sentence headline**, e.g. "GeniOS has read 470 items and knows 1,830 facts; 6 situations formed this week."
3. **The flow:** five tiles, Items read → Facts known → Situations formed → Cards raised → Outcomes checked.
   - Each tile carries its window ("all time" / "this week").
   - Between two tiles **of the same window** a chip shows the share that went on (e.g. 50%), or "×3.9" facts per item.
   - Facts → situations gets an arrow only: a fact does not "become" a situation.
   - The first stage that is 0 while the stage before it is not turns red: **"Stops here"** (`live.ts · stoppedAt`). Stages after it fade.
4. **Where it comes from** and **Latest changes**, side by side, each 420px tall and **scrolling inside**:
   - **Sources:** per source, items read with a bar of its share, facts and people extracted, and freshness ("On time · Synced 1 h ago", "Behind", "Failing — reconnect").
   - **Feed:** up to 20 newest changes (new card / new person / updated person or company), with relative time.
5. **What changed this week:** six tiles, each with a number, an optional delta and a small bar.
6. **The health strip:** evidence coverage · freshness · policy-safe actions, from `snapshot.health`.
