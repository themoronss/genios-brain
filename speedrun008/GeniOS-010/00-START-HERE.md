# GeniOS-010 · The dashboard: navigation, home page, goals

**Written for:** Harsh. The aim is that you can take the new dashboard design and wire it in without asking.

**Status, 22 Oct 2026:**
- Built and tested, but **not live**.
- Everything is on the dashboard branch `rohit/nav-grouping` in `github.com/themoronss/genios-brain-dashbaord`: 14 commits on top of `origin/main` `6ddc4db`. The last one, `f137d41`, is the Goals page.
- brain.thegenios.com serves `main`, so nothing here is visible until that branch is merged.
- No brain code changed for any of this. Every brain change the design needs is listed in `02-DASHBOARD-HOME/05-BRAIN-WORK.md` and `03-GOALS/README.md`.

**Who decided what:**
- Rohit set the grouping, the priority order of the home page and the look, over one afternoon of reviews.
- The design follows his words: *"existing dashboard ko change nahi karna hai, bas update karna hai"*. Pages were regrouped and updated, not replaced.

---

## The three folders

| Folder | What it covers | Read when |
|---|---|---|
| [`01-NAVIGATION/`](01-NAVIGATION/README.md) | The sidebar regrouping (Intelligence · Context · Workspace · Desktop), locked items, Screen under Intelligence, the Expertise page showing locked domains. | First. It is small and explains where every page now lives. |
| [`02-DASHBOARD-HOME/`](02-DASHBOARD-HOME/README.md) | The home page, section by section: what each shows, which brain route feeds it, what is sample-only, AER/HIR, the Screen page, how to run and test it, and the brain work it needs. | When you wire the home page to real data or merge the branch. |
| [`03-GOALS/`](03-GOALS/README.md) | **The Goals page** (Intelligence ▸ Goals): Domain → Goal → Situation → Scenario → Reasoning. It shows what is live today and what waits for GeniOS-009 G1/G3/G4/G5/G7, plus the goal shape, its mapping onto `GET /v1/goals`, and the open decisions. | Before building GeniOS-009 G1–G5, so the API returns what the page draws. |

## How the pieces connect

```
 brain (api.thegenios.com)                         dashboard (brain.thegenios.com)
 ─────────────────────────                         ───────────────────────────────
 /api/org/{org}/home-summary   ─┐
 /api/org/{org}/first-scan      │
 /activity                      ├─► homepage/live.ts ──► the home sections (02)
 /api/org/{org}/network-health  │     (builds one view;
 /integrations/status          ─┘      sample data in data.ts has the same shape)
 /v1/seats/me/weekly-report    ───► GeniOS at work tiles, Screen page lanes
 /v1/agents, /v1/delegations   ───► AER readiness (what is in place)
 /v1/expertise/domains|request ───► Expertise page (01)
 /v1/company-brief (+ decide, + lines) ──► Goals page (03): goals, proposals, add a goal
 /cards, /cards/{id}           ───► Goals page: situations, scenario, reasoning (by domain)
 /v1/goals  (GeniOS-009 G1, not built) ─► goal department, progress, links — sample-only until then
```

## Ground rules the design keeps

These matter more than any one screen:

1. **No made-up number reaches a signed-in customer.**
   - Live mode shows real values, or says "not measured yet" with the reason.
   - Sample numbers appear only in **sample mode**: with `?demo=1`, or on localhost when signed out. They always sit under an orange "Sample numbers — not your data" banner.
2. **Unknown is never 0.** A goal with no countable measure shows a striped bar and "Progress unknown", not 0%. This matches GeniOS-009 G5.
3. **A metric that cannot be measured yet still shows something true:**
   - how ready it is (e.g. HIR "67% ready to measure", read from live data);
   - a dotted line labelled "the shape it will take, not a value".
   AER stays locked and blurred until an agent can act.
4. **One slow brain route never blocks the page.** Only `home-summary` gates the page; the other routes fill their sections in as they answer.

## Read order

1. `00-START-HERE.md` (this file)
2. `01-NAVIGATION/README.md`
3. `02-DASHBOARD-HOME/README.md` → `01-SECTIONS.md` → `02-DATA-WIRING.md` → `03-AER-HIR.md` → `04-SCREEN.md` → `05-BRAIN-WORK.md` → `06-RUN-AND-TEST.md`
4. `03-GOALS/README.md` → `03-GOALS/01-GOALS-PAGE.md`
5. `LOG.md`: what happened, in order.
