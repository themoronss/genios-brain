# 03.1 · The Goals page: Intelligence → Goals

**Written for:** Harsh.

**Status, 22 Oct 2026:** built, and live where the brain allows it.

- **Commit:** `f137d41` on `rohit/nav-grouping` (`genios-brain-dashbaord`).
- **Route:** `/dashboard/goals`. It is unlocked in the nav (Intelligence ▸ Cards · **Goals** · Screen), and the home page's "This month's goal" heading links to it.

**Rohit's ask:**
- *"domain-wise goals honge, goals-wise situations honge, situation-wise scenarios honge, aur uske regarding reasoning"*.
- That chain is the page.

**Screenshots** (in `screens/`):

| File | What it shows |
|---|---|
| `goals-sample-top.png` · `goals-sample-bottom.png` | The target, in sample mode. The first situation is opened. |
| `goals-signed-in.png` | A signed-in owner, against the stand-in brain (`../02-DASHBOARD-HOME/tools/mock_brain.py`). Northwind is opened. |

---

## 1 · What the page shows, top to bottom

1. **Header:** "Intelligence · October 2026", **Goals**, one line on what the page is. In live mode, a "See it with sample numbers" link.
2. **The chain as pills:** Domain → Goal → Situation → Scenario → Reasoning. It tells the reader how to read everything below.
3. **Overview:**
   - a **donut of goals by status**: done · on track · at risk · blocked · not measured;
   - three tiles: **open situations** (and how many are linked to a goal), **domains with work**, and **waiting for your approval**.
4. **Waiting for your approval:**
   - the goals GeniOS **proposed** from what it read, each with **Not a goal** / **Make it a goal**;
   - invariant: *an inferred goal never becomes approved without a human* (GeniOS-009 05 §5).
5. **A filter row:** All domains · each domain (scopes everything below), and **Add a goal** (the founder's own goal, in force at once).
6. **One section per domain:**
   - **Header:** icon, name, one line on what it covers, and pills (N goals · N situations · average progress when measurable).
   - **A card per goal:**
     - the statement, a status chip and "set by you" when the founder added it;
     - owner · due · number of situations;
     - **progress % with a bar and a dark "today" marker**. Unknown progress is a striped bar with "?", never 0;
     - a **"Situations moving this goal"** row with relation chips (N advances · N threatens · N depends on) and **Show / Hide**.
   - **Situations under a goal, ordered decision → conflict → question → waiting, then by urgency.** Each row shows an urgency dot, a lane chip, the headline, a relation chip and the due date. **Click it to open:**
     - **Scenario:** who · what is going on · why now · what remains · if you do nothing;
     - **Reasoning:**
       - what it does to the goal ("Advances *Raise the seed round* through a sixth fund entering diligence");
       - recommended, with numbered steps;
       - alternative · avoid · wait or stop;
       - **done when**;
       - **confidence, dimension by dimension**, with the word and its reason;
       - **what it stands on**: the quoted lines and their source;
     - **Open this card →** (`/dashboard/cards?card=<id>`) for a live card.
   - **Not linked to a goal (N), "counted, never hidden"**: the situations in this domain that no goal claims. GeniOS-009 06 §3 and §6: a card with no goal is shown and counted, never dropped.

## 2 · Live vs sample

| | Sample (`?demo=1`, or localhost signed out) | Live, signed in, today |
|---|---|---|
| Domains | Founder Office, Admin | **Company-wide** (the brief's goals; they have no department yet), plus every domain that has an open card (`card.domain`, named from `/v1/expertise/domains`) |
| Goals | 6, with status, %, pace, owner, due | the brief's **accepted** goal lines: status **Not measured**, progress unknown (no G5) |
| Situations under a goal | linked, with a relation | **none yet.** The goal says so ("Situations are linked to goals by the goal object…"), because there is no G4 |
| Not linked | 1 (F22) | **every open card**, under its domain |
| Scenario | sample lines | the card's real lines: `business_subject · relationship_role`, `situation`, `why_now`, `unresolved_item`, `do_nothing_consequence` |
| Reasoning | full target: impact, six confidence dimensions | the card's real reasoning: `decision.recommendation` (verdict, steps, avoid), `alternative`, `wait_or_stop`, `success_signal` (done when), `decision.confidence` (each 0–1 → strong ≥ 75% · medium ≥ 50% · weak), `why[]` (readings, doctrine, check lines) |
| Proposals · add a goal | buttons shown, disabled | **work**: `POST …/proposals/{id}/decide` and `POST /v1/company-brief/lines` |

## 3 · Files

All paths are under `src/`.

```
app/dashboard/goals/page.tsx                    the route
product/internal/dashboard/goals/
  types.ts                                      Domain · Goal · Situation · Scenario · Reasoning (+ GoalStatus, Relation, Lane)
  sample.ts                                     SAMPLE_GOALS_VIEW — built from GeniOS-009 06 §2–§4 (F02, F03, F13, F14, F15, F22, F24, F25)
  live.ts                                       liveGoalsView(brief, cards, details, domainNames) · situationFromCard · sortSituations
  goals-page.tsx                                GoalsPage, DomainSection, GoalCard, SituationRow, ScenarioPanel, ReasoningPanel, Proposals, AddGoal
lib/api-goals.ts                                getCompanyBrief · addGoal · decideGoalProposal
components/layout/sidebar.tsx                   Goals: { href: "/dashboard/goals" } (was locked)
product/internal/dashboard/homepage/sections/genios-at-work.tsx   "Open goals" in §1's heading
```

It reuses the home page's `ui.tsx` (CARD, Pill, IconBox) and `charts.tsx` (Donut, PaceBar), so the two pages look like one product.

## 4 · Calls it makes, live

```
GET  /v1/company-brief                        → lines (section "goals") → goals; proposals (section "goals") → waiting
GET  /cards                                   → open cards
GET  /cards/{id}            ×N (≤ 40, parallel) → domain, scenario lines, decision, why
GET  /v1/expertise/domains                    → domain names
POST /v1/company-brief/lines                  { section: "goals", text }       (Add goal)
POST /v1/company-brief/proposals/{id}/decide  { decision: "accept" | "reject" } (Make it a goal / Not a goal)
```

- The first three are read in parallel. The page is ready when either the brief or the cards answer.
- The card details fill in afterwards; until then an opened situation's reasoning reads "Reading the reasoning…".
- The two writes need an **account owner** (`require_account_owner`). A member gets 403, shown as the notice line.

⚠ **N+1:** reading every open card's detail is fine for tens of cards. If an org has hundreds, add `GET /cards?detail=1` (or a `domain` field on `/cards`) and drop the per-card reads. See `README.md` §6.

## 5 · What makes it fully live: the brain side (GeniOS-009)

| Piece | Today | Needs | Then the page |
|---|---|---|---|
| A goal's **department** | none, so goals are "Company-wide" | **G1** `Goal.department` | each goal sits under its domain |
| **Owner, due, measure** | none | **G1** `owner_seat`, `deadline`, `metric`/`target` | owner · due · % appear on the card |
| **Progress** | unknown | **G5** `GoalProgress` (measured / counted / unknown + why) | the bar, the %, "progress unknown — {why}" |
| **Status** (done / on track / at risk / blocked) | "Not measured" | **D-010-G1** rule in `GET /v1/goals` (`README.md` §4) | chips and the donut |
| **Goal ↔ situation** | none, so all "not linked" | **G4** `goal_situation_links` (advances / threatens / depends_on / unclear) | situations move under their goal with a relation |
| **Impact line** in reasoning | "Not linked to a goal yet" | **G3** goal impact in the judgment (`relation` + `through`) | "Advances X through Y" |
| **Six confidence dimensions** | the card's four (evidence, identity, situation, recommendation) | GeniOS-008 L2-9 six dimensions on the card | the six rows |
| **Done when** as a definition of done | `success_signal` | **G7** `definition_of_done` | stays the same field on screen |

**When `GET /v1/goals` ships:**
1. Write `mapGoal()` in `goals/live.ts` from the shape in `README.md` §3.
2. Group goals by `department`, and put each card under the goal its G4 link names (`goal_refs` from G6 on the card, or a `links` array on the goal).
3. Set `linked: true`.

The component code does not change: sample mode already draws exactly that.
