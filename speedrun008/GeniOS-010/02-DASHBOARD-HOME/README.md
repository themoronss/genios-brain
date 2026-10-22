# 02 · The dashboard home page

**Written for:** Harsh.

**Branch:** `rohit/nav-grouping` in `genios-brain-dashbaord`. Home-page commits, oldest first:

| Commit | What |
|---|---|
| `0437540` | First "GeniOS at work" block: goals, AER, HIR |
| `de27094` | Dev proxy `GENIOS_DEV_API_PROXY` (local only) |
| `2db6d7d` | Dev `NEXT_PUBLIC_DEV_SKIP_LOGIN` (local only) |
| `0ab7b03` | Intelligence → Screen page (see `04-SCREEN.md`) |
| `ae493c3` | Monthly goals, new headline metrics, context flow, what is working |
| `6921be3` | Charts: AER/HIR trends, goal pace, glass flow (since restyled), sources with numbers |
| `ec1c836` | Signed-in view: live readiness, month ring, live activity tiles |
| `f8768a7` | Roomier layout, larger type, gauges, smooth curves |
| `bc52077` | Rohit's priority order; AER locked; lists scroll in fixed boxes |
| `c8f896c` | Checks under the week; one formal "What the brain holds" card |
| `9c71f07` | AER and HIR end at the chart; the rest opens on Show |
| `f137d41` | The Goals page (`03-GOALS/01-GOALS-PAGE.md`); home §1's heading gets "Open goals" |
| `9322382` | "See it with sample numbers" removed from home §1 (the preview stays at `?demo=1`) |

What each round changed, and what was dropped: `../04-BUILD-REVIEW.md` §2. The Screen page (`0ab7b03`, rebuilt in `9130f84`) is now in `../05-SCREEN/`.

**Screenshots** (in `screens/`):

| File | What it shows |
|---|---|
| `home-signed-in.png` | A signed-in owner, against the stand-in brain in `tools/mock_brain.py`. It shows what a real customer sees today. |
| `home-sample.png` | `?demo=1`, with every section filled with labelled sample numbers. It shows the target state. |

---

## The page, top to bottom

This order is Rohit's, given on 22 Oct: *"priority pe aana chahiye: this month ka goal, AER aur HIR, neeche wala (cards, screens, people), this week"*.

| # | Section (heading on screen) | Component | Feeds from |
|---|---|---|---|
| 0 | Header: date · "Welcome back, {first name}" · bell | `company-intelligence-home.tsx` | `getUserInfo()` (local storage) |
| — | Orange **sample banner** (sample mode only) | `shared/sample-mode.tsx · SampleBanner` | — |
| — | Sync progress (only while a sync runs) | `components/integrations/sync-progress` | unchanged |
| 1 | **This month's goal** | `sections/genios-at-work.tsx · MonthPace / GoalRows / MonthOnly` | sample only; live shows the real month ring and a preview. Needs `GET /v1/goals` → `03-GOALS` |
| 2 | **Automation and intervention**: AER (locked) · HIR | `sections/genios-at-work.tsx · MetricPanel` | sample only for values; live readiness from `/v1/agents`, `/v1/delegations`, `/integrations/status`, `home-summary` |
| 3 | **Activity this week**: people active · cards raised · done instantly from your screen | `sections/genios-at-work.tsx · liveTiles` | `network-health`, `/activity`, `/v1/seats/me/weekly-report` |
| 4 | **This week at a glance**: goals formed · situations formed · situations closed · business health | `sections/headline-cards.tsx` | `home-summary.cards`, `network-health` |
| 5 | **What is working, what is not** | `sections/whats-working.tsx` | computed in `live.ts · liveChecks` from the same inputs |
| 6 | Decisions over time · Recent decisions (**sample mode only**) | `sections/decision-trend.tsx`, `recent-decisions.tsx` (pre-existing, previously hidden) | static sample; no live source yet |
| 7 | **What the brain holds**: one white card with the counts strip, the flow, where it comes from, latest changes, what changed this week, and the health strip. "Open the graph" sits in the heading. | `sections/context-moving.tsx · ContextMoving` + `sections/graph-knowledge.tsx · KnowledgeStrip` | `home-summary`, `first-scan`, `/activity`, `network-health`, `/integrations/status` |

Section by section: `01-SECTIONS.md`. Route by route: `02-DATA-WIRING.md`.

## File map

All paths are under `src/`.

```
app/dashboard/layout.tsx                        session gate; DEV_SKIP_LOGIN lets localhost open signed-out
app/dashboard/moments/page.tsx                  the Screen page (route kept) — now renders ScreenPage, see ../05-SCREEN
components/layout/sidebar.tsx                   nav (01-NAVIGATION)
lib/session.ts                                  + DEV_SKIP_LOGIN constant
product/internal/shared/sample-mode.tsx         NEW · useSampleMode() + SampleBanner (used by home + Screen)
product/internal/dashboard/homepage/
  company-intelligence-home.tsx                 the page: fetches, picks live vs sample, lays out the sections
  data.ts                                       types every section renders + their SAMPLE values
  live.ts                                       NEW · builds the same types from the brain's routes (pure functions)
  charts.tsx                                    NEW · TrendChart, Gauge, Donut, PaceBar, StackBar, smoothPath
  ui.tsx                                        NEW · CARD, HomeSection, CardHeader, Pill, IconBox (one card style)
  definition.ts                                 section list, in page order
  sections/genios-at-work.tsx                   1–3: goals, AER/HIR, activity tiles
  sections/headline-cards.tsx                   4: the four week cards
  sections/whats-working.tsx                    NEW · 5
  sections/context-moving.tsx                   NEW · 7 (the brain card)
  sections/graph-knowledge.tsx                  7: KnowledgeStrip (the counts line)
  sections/decision-trend.tsx, recent-decisions.tsx   pre-existing, now shown in sample mode
  sections/notice-board.tsx                     pre-existing, no longer rendered (the "becoming more proactive" notice)
next.config.ts                                  + local-only /brain-api proxy rewrite
```

`notice-board.tsx` was left in place, not deleted, because the brain still sends `snapshot.notice`. Delete both together once nothing reads them; see `05-BRAIN-WORK.md`.

## Live vs sample, in one paragraph

- `useSampleMode()` is **on** with `?demo=1`, or on localhost when `NEXT_PUBLIC_DEV_SKIP_LOGIN=1` and nobody is signed in. Sample mode is never on by itself in a deployment.
- **In sample mode:** every section renders its `data.ts` sample under the orange banner, and nothing is fetched.
- **In live mode:**
  - the page fetches five routes in parallel; `home-summary` gates the page, and the other four fill in as they land;
  - `GeniosAtWork` also fetches the weekly report, agents and delegations itself;
  - a failed route leaves its numbers out (null / "—"). It never becomes 0.

## Ready to merge?

- Typecheck is green and `next build` passes on the branch. The repo has no lint config, so `next lint` installs ESLint 10 and stops.
- **Not covered:** phones. The app shell's sidebar never collapses, so below roughly 700px the content column is squeezed. This was true before this branch too. It is a separate fix in `app/dashboard/layout.tsx`.
- **To go live:** merge `rohit/nav-grouping` into `main`. Rohit has to do it or approve it; an automated push to `main` was refused.
- **Do not ship the dev flags:**
  - neither `GENIOS_DEV_API_PROXY` nor `NEXT_PUBLIC_DEV_SKIP_LOGIN` may be set in Vercel/production;
  - even if set, `DEV_SKIP_LOGIN` is false in a production build, because it is gated on `NODE_ENV === "development"`.
