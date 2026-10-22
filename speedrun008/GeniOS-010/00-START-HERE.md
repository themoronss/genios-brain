# GeniOS-010 · The dashboard: navigation, home page, goals, screen, cards

**Written for:** Harsh, to wire the new dashboard design in without asking, and Rohit, to review what was built (`04-BUILD-REVIEW.md`).

**Status, 22 Oct 2026:**
- Built and tested, but **not live**.
- Everything is on the dashboard branch `rohit/nav-grouping` in `github.com/themoronss/genios-brain-dashbaord`: 26 commits on top of `origin/main` `6ddc4db` (33 files, +7,272 / −906), HEAD `847eeac`. `f137d41` … `cc1b58f` are the Goals page; `5c0504f` locks Agents; `f151019`, `9130f84`, `972d122`, `9a13d87` and `847eeac` rebuild the Screen page.
- **For the analysis, start with [`04-BUILD-REVIEW.md`](04-BUILD-REVIEW.md):** for every part, what was there, what we built, why, how, each round of review and what was dropped, how it integrates, the risks, and Harsh's integration order.
- **The Cards page** is on its own branch, `rohit/cards-ux`, three commits on top of `847eeac` (`b5527dc` · `9d565e6` · `25553ab`; 3 files, +1,675 / −687). Merge it after, or with, `rohit/nav-grouping`. See [`06-CARDS/`](06-CARDS/README.md).
- brain.thegenios.com serves `main`, so nothing here is visible until those branches are merged.
- No brain code changed for any of this. Every brain change the design needs is listed in `02-DASHBOARD-HOME/05-BRAIN-WORK.md` and `03-GOALS/README.md`.

**Who decided what:**
- Rohit set the grouping, the priority order of the home page and the look, over one afternoon of reviews.
- The design follows his words: *"existing dashboard ko change nahi karna hai, bas update karna hai"*. Pages were regrouped and updated, not replaced.

---

## The folders, and the review

| Folder | What it covers | Read when |
|---|---|---|
| [`01-NAVIGATION/`](01-NAVIGATION/README.md) | The sidebar regrouping (Intelligence · Context · Workspace · Desktop), locked items, Screen under Intelligence, the Expertise page showing locked domains. | First. It is small and explains where every page now lives. |
| [`02-DASHBOARD-HOME/`](02-DASHBOARD-HOME/README.md) | The home page, section by section: what each shows, which brain route feeds it, what is sample-only, AER/HIR, the Screen page, how to run and test it, and the brain work it needs. | When you wire the home page to real data or merge the branch. |
| [`03-GOALS/`](03-GOALS/README.md) | **The Goals page** (Intelligence ▸ Goals): one goal, one card, with its reasoning and numbered cards inside, Admin only. It shows what is live today and the fields `GET /v1/goals` must return (GeniOS-009 G1/G3/G4/G5/G7/G9), plus the open decisions. | Before building GeniOS-009 G1–G5, so the API returns what the page draws. |
| [`04-BUILD-REVIEW.md`](04-BUILD-REVIEW.md) | **The review across all of it:** was there → built → why → how → rounds (what was tried and dropped) → how it integrates; risks R1–R12; the integration checklist. | First, when deciding what to do next. |
| [`05-SCREEN/`](05-SCREEN/README.md) | **The Screen page** (Intelligence ▸ Screen): how Screen works in six stages, each item with its path (at once → memory → card), the card it fed nested inside it, popups; a screen item vs a card; live vs preview; the goal each item moves; the look (fill, not borders). **`01-INTEGRATION.md`** is the wiring for Harsh: every field, every button, brain changes S1–S8 in order, the checks. **`02-WHAT-WHY-HOW.md`** is the story for analysis, round by round with a screenshot each. Also: Agents locked. | Before B8, and before the Cards page, which shares its card parts. |
| [`06-CARDS/`](06-CARDS/README.md) | **The Cards page** (Intelligence ▸ Cards): cards grouped by what they ask (Decide · Answer · Waiting); each row a clear subject with what to do and how; the card opened in a side panel in Rohit's order: recommendation · what · why · how · what doing it gets you · goal · deadline · details · where the data came from; only each card's own details; Done · Delegate · Later · Feedback · Answer. **`02-CARD-DEFINITION.md`** is what a card is, field by field, with where each comes from in the brain. **`01-INTEGRATION.md`** is the wiring for Harsh and brain changes C1–C9 in order (the card writer, card-scoped context, delegate). **`04-WHAT-WHY-HOW.md`** is the story, round by round with a screenshot each. | Before the card writer (C1) and before moving Goals and the Mac app onto the one card reader. |

## How the pieces connect

```
 brain (api.thegenios.com)                         dashboard (brain.thegenios.com)
 ─────────────────────────                         ───────────────────────────────
 /api/org/{org}/home-summary   ─┐
 /api/org/{org}/first-scan      │
 /activity                      ├─► homepage/live.ts ──► the home sections (02)
 /api/org/{org}/network-health  │     (builds one view;
 /integrations/status          ─┘      sample data in data.ts has the same shape)
 /v1/seats/me/weekly-report    ───► GeniOS at work tiles, Screen page week strip
 /v1/followups, /v1/moments    ───► Screen page (05): every item, its actions, popups
 /v1/agents, /v1/delegations   ───► AER readiness (what is in place)
 /v1/expertise/domains|request ───► Expertise page (01)
 /v1/company-brief (+ decide, + lines) ──► Goals page (03): goals, proposals, add a goal
 /cards, /cards/{id}           ───► Goals page: situations, scenario, reasoning (by domain)
 /cards, /cards/{id}, /timeline, /history, POST /cards/{id}/action
                               ───► Cards page (06): lib/card-read.ts → list · side panel · buttons
 /v1/goals  (GeniOS-009 G1, not built) ─► goal department, progress, links — sample-only until then
```

## Ground rules the design keeps

These matter more than any one screen:

1. **No made-up number reaches a signed-in customer.**
   - Live mode shows real values, or says "not measured yet" with the reason.
   - Sample numbers appear only in **sample mode**: with `?demo=1`, or on localhost when signed out. They always sit under an orange banner ("Sample numbers — not your data" on home, "Preview — not your data" on Goals).
2. **Unknown is never 0.** A goal with no countable measure shows a striped bar and "Progress unknown", not 0%. This matches GeniOS-009 G5.
3. **A metric that cannot be measured yet still shows something true:**
   - how ready it is (e.g. HIR "67% ready to measure", read from live data);
   - a dotted line labelled "the shape it will take, not a value".
   AER stays locked and blurred until an agent can act.
4. **One slow brain route never blocks the page.** Only `home-summary` gates the page; the other routes fill their sections in as they answer.

## Read order

1. `00-START-HERE.md` (this file)
2. `04-BUILD-REVIEW.md`: the whole build in one review
3. `01-NAVIGATION/README.md`
4. `02-DASHBOARD-HOME/README.md` → `01-SECTIONS.md` → `02-DATA-WIRING.md` → `03-AER-HIR.md` → `04-SCREEN.md` → `05-BRAIN-WORK.md` → `06-RUN-AND-TEST.md`
5. `03-GOALS/README.md` → `03-GOALS/01-GOALS-PAGE.md`
6. `05-SCREEN/02-WHAT-WHY-HOW.md` (the story, for analysis) → `05-SCREEN/README.md` → `05-SCREEN/01-INTEGRATION.md`
7. `06-CARDS/04-WHAT-WHY-HOW.md` (the story) → `06-CARDS/README.md` → `06-CARDS/02-CARD-DEFINITION.md` → `06-CARDS/01-INTEGRATION.md` → `06-CARDS/03-WHAT-WAS-THERE.md`
8. `LOG.md`: what happened, in order.
