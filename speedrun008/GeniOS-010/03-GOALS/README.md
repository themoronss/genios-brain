# 03 · Goals: what the dashboard already draws, and what it needs

**Written for:** Harsh (to build against) and Rohit (we edit goals here next).

**Status, 22 Oct 2026:**
- The **screen** for goals is built, but shows sample data only.
- The **goal object** does not exist: GeniOS-009 G1–G5 are planned, not built. Today a goal is a free-text `company_brief_lines` row with `section = 'goals'`.
- This folder is where the goals edits happen next. Rohit opens each step; nothing here is started before he does.

---

## 1 · Where goals show up on the dashboard today

| Place | What it shows now | File (dashboard repo, `src/`) |
|---|---|---|
| Nav: Intelligence ▸ **Goals** 🔒 | a locked item: "Goals are coming next: what the company wants to achieve, and how far along it is." | `components/layout/sidebar.tsx` |
| Home §1 **This month's goal** | live: the month ring and a faded preview · sample: donut + pace + rows | `product/internal/dashboard/homepage/sections/genios-at-work.tsx` (`MonthOnly`, `MonthPace`, `GoalRows`, `SAMPLE_GOALS`) |
| Home §4 **Goals formed** card | live: 0 with flat weeks · sample: 5 this month | `homepage/live.ts · liveHeadlineCards`, `homepage/data.ts · headlineCards` |
| Home §5 checks | "No goals set yet, so progress toward them cannot be shown" | `homepage/live.ts · liveChecks` |

Screenshot: `../02-DASHBOARD-HOME/screens/home-sample.png`, top section (sample).

## 2 · The shape the screen draws

From `genios-at-work.tsx`:

```ts
type GoalStatus = "done" | "on_track" | "at_risk" | "blocked";

type Goal = {
  name: string;        // "Five investor meetings this month"
  department: string;  // "Founder Office · Fundraising"
  progress: string;    // "3 of 5 held · 2 funds in diligence"   — the words under the bar
  pct: number | null;  // 0–100; null = no countable measure → striped bar, "?", "Progress unknown — …"
  due: string;         // "31 Oct"
  open: string;        // "4 open situations"
  status: GoalStatus;
};
```

**What the screen computes itself:**
- **% of the month gone** = day ÷ days in the month. This is the dark "today" marker on every bar.
- **Average progress** = the mean of `pct` over goals where `pct !== null`. Unknowns are left out, never counted as 0.
- **Ahead / behind pace** = average progress − % of the month gone.
- **Donut** = count by `status`.

## 3 · How it maps onto GeniOS-009

These are `STEP-G1` (goal object) and `STEP-G5` (progress). G1.4 serves `GET /v1/goals`: "live and proposed goals with progress (G5) and open linked situations (G4)".

| Screen field | From GeniOS-009 | Note |
|---|---|---|
| `name` | `Goal.statement` | ≤ 200 chars |
| `department` | `Goal.department` | a live domain (D1) |
| `due` | `Goal.deadline` | formatted `d MMM` |
| `pct` | `GoalProgress.share_bp / 100` when `state = "measured"` | `counted` and `unknown` → `null` |
| `progress` | measured: `"{actual} of {target} {unit}"` · counted: the counted line, e.g. "3 open situations: 2 advance it, 1 threatens it" · unknown: `GoalProgress.why` | G5 says *"unknown is never 0"*. The screen already draws null as unknown |
| `open` | open G4 links for this goal | "N open situations" |
| `status` | **not in G1/G5. Decide below (D-010-G1)** | |

**What `GET /v1/goals` must return so the screen needs no more calls:**

```json
{ "goals": [ {
  "goal_id": "...", "statement": "...", "department": "founder_office", "status": "active",
  "deadline": "2026-10-31", "starts_on": "2026-10-01", "approved_at": "2026-10-02T…",
  "metric": "files_at_stage", "target": 5, "unit": "meetings",
  "progress": { "state": "measured", "actual": 3, "target": 5, "share_bp": 6000, "why": null,
                "counted": { "advances": 2, "threatens": 1, "depends_on": 0 } },
  "open_links": 4
} ] }
```

**The screen also needs `approved_at`** (or a created time), to count "Goals formed this month" for the §4 card.

## 4 · Open decisions (Rohit)

| # | Question | Default if not decided |
|---|---|---|
| **D-010-G1** | How is a goal's **status** (done / on track / at risk / blocked) decided? | **done:** `status = completed`. **blocked:** an open link with relation `depends_on` whose situation is not moving (or a person marks it). **at risk:** `pct` is more than 15 pts behind the goal's own pace, or a `threatens` link is open. **on track:** otherwise. Computed in the brain (`GET /v1/goals`), not in the browser, so every surface agrees. |
| **D-010-G2** | What are **"this month's goals"**? Rohit: *"monthly goals kya hain, is mahine ke goals ke kitne poore ho rahe hain"*. | Every live goal whose `deadline` falls in the current month, **plus** any longer goal's milestone due this month. That needs a `parent_goal_id` child per month (G1 already has `parent_goal_id`). Until milestones exist: deadline in this month. |
| **D-010-G3** | Pace for a goal that is not a month long. | Expected progress = time elapsed between `starts_on` and `deadline`. The screen then draws each row's marker at that goal's own pace. Today it uses the month for every row. |
| **D-010-G4** | Where is the full **Goals page** (Intelligence ▸ Goals, now locked)? | It shows the same rows as home §1, then per goal the open situations (advances / threatens / depends on) and the cards that move it (G6's board, `GET /v1/insights?group=goal`). |

## 5 · What we edit next, in this folder

Rohit opens these. Each gets its own file here:

1. `01-GOALS-PAGE.md`: the Intelligence ▸ Goals page (D-010-G4): layout, states, empty and unknown handling.
2. `02-HOME-GOALS-LIVE.md`: switching home §1 and the "Goals formed" card from sample to `GET /v1/goals`, once G1 + G5 exist.
3. `03-STATUS-AND-PACE.md`: D-010-G1 to G3, written as the brain rule with tests.

## 6 · Wiring it in (when G1 + G5 land)

1. Add `getGoals()` to `src/lib/` (a `seatCall`- or `v2Get`-style client, whichever `GET /v1/goals` is mounted under).
2. In `GeniosAtWork`, replace `const goals = sample ? SAMPLE_GOALS : []` with the mapped goals (§3). Keep `[]` → `MonthOnly` for a workspace with none.
3. In `live.ts · liveHeadlineCards`, set "Goals formed" from the count of `approved_at` in this month. Its 12 bars come from the same field, by week.
4. In `live.ts · liveChecks`, drop the always-on "No goals set yet" row when goals exist. Add "N goals at risk" (watch) and "N goals blocked" (broken).
5. In `sidebar.tsx`, unlock **Goals**: give it `href: "/dashboard/goals"` and drop `locked`.
