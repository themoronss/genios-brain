# 04 · Build review: what was there, what we built, why, how, and how it fits

**Written for:** Rohit and Harsh, to analyse the work before deciding the next step.

**Status, 22 Oct 2026:**
- **Branch:** `rohit/nav-grouping` in `genios-brain-dashbaord`, pushed. HEAD is `9130f84`.
  - 23 commits on top of `origin/main` `6ddc4db`: 33 files, +6,703 / −906 lines.
  - `tsc --noEmit` and `next build` are green at `9130f84`.
- **Not merged, so not live:** brain.thegenios.com serves `main`.
- **No brain code changed.** Every brain change the design needs is named in §6 and in the folder docs.

**Every part below follows the same order:**
1. **What was there:** `origin/main`, which is also what is live.
2. **What we built.**
3. **Why:** Rohit's words.
4. **How:** files, data and the rule each part keeps.
5. **How it changed:** each round of review, with what was tried and dropped.
6. **How it integrates:** brain routes, what is live, what waits.

---

## 0 · The whole thing on one page

| Part | Was there | Now | Live today, signed in | Waits on |
|---|---|---|---|---|
| **Navigation** | A flat list: Brain/Graph/Context under "Intelligence", Needs review, Expertise top-level, Moments under Desktop | Intelligence (Cards · Goals · Screen) · Agents 🔒 · Context (Graph · Company · Domains · Sources) · Workspace · Desktop | everything, once merged | B4: `active` per workspace on `/v1/expertise/domains` |
| **Home** | Header, the "becoming more proactive" notice, 4 headline cards, a counts strip, all from `home-summary` | 7 sections in Rohit's order, with real charts | goal month ring, AER/HIR readiness, activity, the week, checks, the brain card | B1 goals, B2 AER/HIR rollup, B5–B9 |
| **Goals** | No page; a locked "Goals" item | One goal = one card, with details, plan, metrics and numbered cards; Admin only; by month; tags | the brief's goals, finalise-then-approve, add a goal, every Admin card with its real scenario and reasoning | GeniOS-009 G1 · G4 · G5 (+ G7 · G9) |
| **Screen** | Desktop ▸ Moments: a list of popups with Useful / Wrong | Intelligence ▸ Screen: how it works in six stages, every item with its path (at once → memory → card), the card each fed nested inside it, popups | every item with its words, who, due, reminders, how it ended and whether it is in memory; Done · Snooze · Draft a reply · Done elsewhere · Dismiss; popups | B8: how each item was read, its popup and card links, read/skipped counts |
| **Dev tooling** | — | dev proxy, skip-login, sample mode, a stand-in brain | local only | — |

---

## 1 · Navigation

**Details:** `01-NAVIGATION/README.md`. **Commits:** `db422da` · `690def6` (and `0ab7b03` and `f137d41` move Screen and Goals in).

**What was there:**
```
Dashboard · Cards · Intelligence ▸ Brain · Graph · Context · Sources ▸ … · Needs review · Expertise · Agents · Workspace ▸ … · Desktop ▸ Moments · My capture · Devices
```
"Intelligence" held places where things are *known* (Brain, Graph, Context), not what was *concluded*.

**What we built:**
- **Intelligence:** Cards · Goals · Screen.
- **Context:** Graph · Company · Domains (Expertise · Brain) · Sources (Tools · Resources · Memory, plus four locked items).
- Needs review leaves the menu; its page still opens.
- Uploads is renamed Resources.
- The Expertise page shows locked domains, what each would unlock, and **Request to unlock**.

**Why:**
- Rohit: *"you've made everything confusing"*.
- He gave the grouping himself: Intelligence = what the brain concluded; Context = what it knows and reads.
- On the first redesign: *"existing dashboard ko change nahi karna hai, bas update karna hai"*. So every page stays and only the grouping changes.
- On Expertise: *"jo locked wali cheezein hain, wo bhi dikhani hain, taaki unko pata chal sake ki kya-kya unlock kiya ja sakta hai"*.

**How:**
- The nav is data in `components/layout/sidebar.tsx` (`navSections`, `memberNavSections`). The render code did not change.
- A locked child has no `href`, shows a lock, and its `lockedNote` is the tooltip.
- `activeChildHref` lights the longest matching child.
- Expertise: `app/dashboard/expertise/page.tsx` adds a Locked chip, the "what you would unlock" box, `COMING_NEXT` (Marketing, Project) and `POST /v1/expertise/request`.

**How it changed:**

| Round | Tried | Outcome |
|---|---|---|
| 1 | A fresh navigation and layout (a prototype artifact) | **Rejected:** "bas update karna hai". Superseded. |
| 2 | Regroup only, keep every page (`db422da`) | Kept |
| 3 | Locked domains on Expertise (`690def6`) | Kept |
| 4 | Moments → Intelligence ▸ Screen (`0ab7b03`); Goals unlocked (`f137d41`) | Kept |
| 5 | Agents locked: the menu item, the page, and the home links to it (`5c0504f`) | Kept |

**How it integrates:**
- No brain change is needed for the nav.
- **⚠ B4:** `/v1/expertise/domains` returns `active: true` for every authored domain. Sales and Support therefore read "Active" for a workspace that has them off.
  - Fix in `genios_engine/api/expertise_routes.py::_corpus_domains`: use `l3_activation.activated_domains(engine, org)`.
  - The page already reads `active`.
- **Merge:** if `main` has gained nav items since `6ddc4db`, put them in the matching group. Do not restore the flat list.

---

## 2 · Dashboard home

**Details:** `02-DASHBOARD-HOME/` (README, `01-SECTIONS` … `06-RUN-AND-TEST`). **Commits:** `0437540` · `ae493c3` · `6921be3` · `ec1c836` · `f8768a7` · `bc52077` · `c8f896c` · `9c71f07` · `9322382`.

**What was there** (`origin/main`):
- A header.
- A **notice:** "Your company is becoming more proactive."
- **Four headline cards:** Intelligent Decisions · Situations formed · Verified outcomes · Human intervention.
- **A counts strip:** Facts · Entities · Relationships · Documents · Active sources · Context calls.
- All of it came from one route, `home-summary`.
- "Decisions over time" and "Recent decisions" were in the code but hidden.
- Nothing said whether GeniOS was *working* for the customer.

**What we built:** seven sections, in Rohit's order.

| # | Section | Live today |
|---|---|---|
| 1 | **This month's goal:** donut, pace bar with a today mark, goal rows | the month ring and a faded preview, until `GET /v1/goals` |
| 2 | **AER** (locked, blurred) and **HIR:** trend chart, then "Show" for the rest | readiness as a %, from `/v1/agents`, `/v1/delegations`, `/integrations/status`, `home-summary` |
| 3 | **Activity this week:** people active · cards raised · done instantly from your screen | `network-health`, `/activity`, `/v1/seats/me/weekly-report` |
| 4 | **This week at a glance:** Goals formed · Situations formed · Situations closed · Business health | `home-summary.cards`, `network-health` |
| 5 | **What is working, what is not** | computed in `live.ts · liveChecks` |
| 6 | Decisions over time · Recent decisions | **sample only** |
| 7 | **What the brain holds:** one white card with the counts line, the context flow, sources with numbers, the feed, changes and health; "Open the graph" in its heading | `home-summary`, `first-scan`, `/activity`, `network-health`, `/integrations/status` |

**Why:**
- Rohit wanted the home page to show what is working and what is not.
- **The notice goes:** "Your company is becoming more proactive" is not information.
- **Metric changes:**
  - HIR moves up, beside AER;
  - Verified outcomes → **Situations closed**;
  - Intelligent decisions → **Goals formed**;
  - add **Business health**.
- **Monthly goals:** *"monthly goals kya hain, is mahine ke goals ke kitne poore ho rahe hain"*.
- **The order is his:** *"this month ka goal, AER aur HIR, neeche wala (cards, screens, people), this week"*.

**How:**
- **One shape, two sources:**
  - `data.ts` holds the types every section renders, plus their **sample** values;
  - `live.ts` builds the **same types** from the brain's routes, as pure functions;
  - `company-intelligence-home.tsx` picks one or the other.
  - A section never knows whether it shows live or sample data.
- **Charts are hand-written SVG** in `charts.tsx` (`TrendChart`, `Gauge`, `Donut`, `PaceBar`, `StackBar`, `smoothPath`). No chart library was added.
  - The Goals page reuses `Donut` and `PaceBar`.
- **One card style:** `ui.tsx` (`CARD`, `HomeSection`, `CardHeader`, `Pill`, `IconBox`).
- **Loading:** five routes are fetched in parallel. Only `home-summary` gates the page; the rest fill in as they answer. A failed route leaves its numbers out and never turns them into 0.
- **Sample mode** (`shared/sample-mode.tsx`) is on with `?demo=1`, or on localhost when signed out. It always runs under the orange banner: "Sample numbers — not your data" on home, "Preview — not your data" on Goals.

**How it changed:** nine rounds in one afternoon.

| Commit | Rohit said | What changed | Dropped |
|---|---|---|---|
| `0437540` | goals, AER, HIR should lead | a "GeniOS at work" block at the top | — |
| `ae493c3` | the metric changes above; remove the notice; monthly goals | rebuilt from live routes; context flow; what is working. **Found:** `decisions` holds intelligence-API answers, not cards, so cards are counted from `/activity`; `execution_outcomes` is not "with proof", so it is labelled "outcome checked" | the notice; the four old cards |
| `6921be3` | *"kya ghatiya sa bana rakha hai"* | real charts: AER/HIR trends with targets, goal pace with a today mark, sources with numbers | small progress bars |
| `ec1c836` | signed in, he saw dashes and empty frames | live readiness for AER/HIR, the month ring, live activity tiles | "—" where a visual could go |
| `f8768a7` | three reference dashboards (LifeOS, Salleist, an HR one): *"sab kuch samaan rakho, bas layout, prastuti alag karo"* | 16px cards, larger type, gauges, smooth curves | dense 9–11px labels |
| `bc52077` | his priority order; AER faded and locked; lists scroll | sections 1–4 together at the top; AER blurred; fixed scroll boxes; brain counts on one line | a long open page |
| `c8f896c` | context flow under the brain card; checks under the week; "2/3" confusing; no red gradient | one white brain card; readiness as "67% ready"; white cards with light-gray panels | glass stage tiles, the red gradient card, "2 of 3" |
| `9c71f07` | AER/HIR take too much space | each ends at its chart; the rest opens on **Show** | everything open by default |
| `9322382` | "See it with sample numbers" is unclear | the link is removed; the preview stays at `?demo=1` | the in-page link |

**How it integrates:**
- **Brain work** (`02-DASHBOARD-HOME/05-BRAIN-WORK.md`):
  - B1 `GET /v1/goals` with progress;
  - B2 a weekly AER/HIR rollup;
  - B3 rename the old `intervention_rate`;
  - B5 weekly change counts in `home-summary`;
  - B6 cards raised this week, counted in the brain;
  - B7 `policy_safe` when nothing was decided;
  - B8 Screen links and counts (`05-SCREEN/README.md` §5);
  - B9 drop `snapshot.notice`, then delete `notice-board.tsx`.
- **When B1 lands:** `03-GOALS/README.md` §6, steps 3–5 (home §1, the Goals formed card, the checks).
- **When B2 lands:** `03-AER-HIR.md` §4. The trend chart already takes a weekly series.

---

## 3 · Goals

**Details:** `03-GOALS/README.md` (decisions D-010-G1 … G6, wiring) and `03-GOALS/01-GOALS-PAGE.md` (the page, live vs preview, files, the fields `GET /v1/goals` must return). **Commits:** `f137d41` · `e4ff9ce` · `9322382` · `cb962fa` · `6850f07` · `273b858` · `cc1b58f`.

**What was there:**
- No Goals page; after `db422da`, a locked "Goals" item in the menu.
- **In the brain**, a goal is a free-text `company_brief_lines` row with `section = 'goals'`. It has no target, owner, deadline, progress or link to a card.
- GeniOS-009 (G0–G9) plans the goal object, its links and its progress. **None of it is built.**

**What we built:**
- **Tabs:** All domains · **Admin** · 🔒 Sales · 🔒 Marketing · 🔒 Product · 🔒 Project. Founder Office is folded into Admin.
- **An overview strip:** goals by status (donut), cards working, cards done, goals to finalise.
- **Goals to finalise:**
  - each proposed goal asks **four questions**: what counts and how many · by when · who owns it · how we will know it is done;
  - the answers compose the goal line, which is shown before **Approve goal**.
- **Admin:**
  - **Add a goal**;
  - a filter of 8 predefined **tags**: Fundraising · Investors · Compliance · Finance · Vendors · Hiring · Legal · Operations;
  - goals **grouped by month**, newest first; inside a month, open goals come before done ones.
- **One goal = one card:**
  - **Face:** a progress ring, a GOAL label, its code `G-XXXXXX`, a status dot and word, its tags, the statement, owner · due · progress, and a pace bar with a today mark.
  - **Details** (only the goal), as small cards:
    - *The goal:* scenario, what to do, target + source, deadline with days left, owner and tags, captured from;
    - *Plan and reasoning:* a plan with ✓ / ● / ○ steps and dates, why it exists with proof, reasoning;
    - *Metrics:* what happened · from your side · what GeniOS did.
  - **Cards N** (only the cards): a vertical, numbered list (`G-XXXXXX · C01`). A click opens one card in place, showing small cards for its *Scenario* (what is going on, who, why now, what remains, if nothing) and its *Reasoning* (what it does to the goal, done when, what to do and steps, otherwise, confidence, proof).
- **Cards no goal claims yet:** a dashed group, counted and never hidden.
- **Cards of locked domains:** one counted line.
- **The preview** at `?demo=1` shows six Admin goals from Aug to Oct 2026, with twelve cards and one proposal.

**Why** (Rohit's model):
- *"Goals banenge, goals ke regarding cards banenge. Cards ki reasoning wo apna part hoga."*
- *"Ek goal ka ek card"*: on its face, *kya scenario hai · kya karna hai · target kahan se hai · capture kahan se hai*.
- *"Pehle sawaal pooch kar hum goals final kar lein, phir approve karwa lein."*
- *"Ek goal ke andar kai cards … jab tak goal complete nahi ho jata."*
- Metrics without bombarding; a UUID-style id for every goal and a number for every card; proof behind everything.
- Admin only.
- Goals by calendar month; predefined tags; a deadline, details and a plan per goal.

**How:**
- **Files:**
  - `goals/types.ts`: one `Goal` type that both sources fill;
  - `goals/sample.ts`: the preview;
  - `goals/live.ts`: builds the page from the brain;
  - `goals/goals-page.tsx`: the components;
  - `lib/api-goals.ts`: the brief calls.
- **Live mapping** (`liveGoalsView`):
  - every **accepted** brief goal line → a goal card, with status *Not measured*, target "Not set yet", and its month taken from `accepted_at`;
  - every **proposed** goal line → a "to finalise" card;
  - **open cards:** `GET /cards`, then `GET /cards/{id}` for the first 40. Each card's `domain` (from the detail, else the list) decides Admin or locked; an empty domain counts as Admin (risk R2, §6). Cards cannot belong to a goal yet, so they all sit under "not linked to a goal yet".
- **Finalise:** `finalGoalLine` composes "statement — target by deadline · owner: X · done when Y" (≤ 200 characters). **Approve** sends it as `decide(lineId, "accept", text)`.
- **Ids:** `shortCode("G", id)` takes the first six hex characters of the line's id. Card numbers are positional today.
- **Looks** (DESIGN.md):
  - 12px cards and 8–10px controls; three shadow levels (`L1` goal, `L2` card, `L3` small card);
  - ink and greys carry everything; burgundy only where something needs the founder;
  - status is a dot and a word.

**How it changed:** seven rounds.

| Commit | Rohit said | What changed | Dropped |
|---|---|---|---|
| `f137d41` | unlock Goals; *"domain-wise goals, goals-wise situations, situation-wise scenarios, aur reasoning"* | a tree: domain → goal → situation → scenario → reasoning | — |
| `e4ff9ce` | one goal, one card; finalise by questions; ids and numbers; Admin only, Founder Office out, four domains locked | goal cards with the four-part face and Show more; the four-question finalise card; `G-XXXXXX` / `· C01` | the deep tree, department grouping, Founder Office |
| `9322382` | show a dummy, connected, to review; remove "See it with sample numbers" | the preview at `?demo=1` opens its first goal and first card | the in-page sample link |
| `cb962fa` | a goal must look different from a card; layers and fading shadows; write less; open a goal → only the goal, open its cards → only the cards | three levels, two toggles (Details / Cards N), a stack behind a closed goal, the overview on one strip | the single "Show more" |
| `6850f07` | match the website theme; cards vertical, opening in place | a numbered vertical list, one open at a time; the dashboard's theme | horizontal numbered tiles |
| `273b858` | *"rang-biranga"*: make it professional | ink and greys; accent only for at risk, blocked, threatens, your side, the open card; status as a dot + word | lane colours, coloured status edges and blocks |
| `cc1b58f` | the open goal is a mess: small cards inside; group by month; predefined tags; a deadline, details and plan per goal | grouped small cards in the goal and in every card; month groups; the tag filter with counts; a plan with states and dates; days left | long text blocks |

**How it integrates:**
- **The page is built to `GET /v1/goals`** (GeniOS-009 G1.4). `01-GOALS-PAGE.md` §5 lists every field, from `goal_id` and `deadline` to `tags[]`, `plan[]`, `metrics.*` and `cards[] {card_id, ordinal, relation, state}`.
  - When the route returns them, `goals/live.ts` maps them and sets `linked: true`. **The components do not change.**
- **The brain needs:**
  - G1, the goal object, with two fields G1 does not plan yet: `tags` and `plan`;
  - G4, goal ↔ card links with a **stable ordinal**;
  - G5, progress, where unknown is never 0;
  - G7 and G9 for the metrics.
- **The four questions:** after G1 they land as structured fields through `PATCH /v1/goals/{id}`, not just words.
- **Open decisions:** D-010-G1 status rule · G2 "this month's goals" · G3 pace for goals longer than a month · G5 stable ordinals. Defaults are written in `03-GOALS/README.md` §4.

---

## 4 · Screen

**Details:** `05-SCREEN/README.md` (it replaces `02-DASHBOARD-HOME/04-SCREEN.md`). **Commits:** `0ab7b03` (first version) · `f151019` (shared card parts) · `9130f84` (rebuilt).

**What was there:** Desktop ▸ **Moments**: the popups the desktop app raised, with Useful / Wrong feedback, and This week / Open follow-ups.

**What we built:**
- **How Screen works**, on the page: Read → Sort → at once (Save · Remind/popup) and next (Memory · Reason → card), each with this week's count, plus **The rules** (never read, what is kept, when a popup shows, who sees it, what it costs, where it ends up).
- **What your screen caught:** every item (`S-XXXXXX`) grouped by day, its path on the row — **At once → Memory → Card** — opening into small cards: on your screen · at once (seconds) · next (memory and reasoning, hourly) · the card it fed, nested as its own card.
- **Cards your screen fed** (each once, with the items that fed it) and **Popups** (shown or held back, Useful / Wrong).
- A preview at `?demo=1`: 10 items, 5 cards (the Goals preview's own), 5 popups.

**Why:**
- Rohit (first round): what the screen catches shows here; instant things are saved at once, things with context are reasoned over and become a card — *"iska koi alag part banana padega ki nahi"*. **No separate part**: what reasoning produces is a card.
- Rohit (22 Oct): *"kaise, kya, kis tareeke se hoga … ek dummy dikhayein"*, and *"screen aur card ek saath ho jaayein, lekin alag-alag rahein"*.

**How:**
- `screen/types.ts` · `sample.ts` · `live.ts` · `screen-page.tsx`, the same shape-twice pattern as Goals.
- The card inside an item and in the cards section is Goals' own `CardItem` / `CardBody`, moved to `intel/parts.tsx`, so a card reads the same on every page. An item is drawn differently: the app's mark, an ink edge, its own sections.
- Live: `GET /v1/followups?status=all`, the weekly report and `GET /v1/moments`; actions call resolve, snooze and draft.

**How it changed:**

| Commit | Rohit said | What changed | Dropped |
|---|---|---|---|
| `0ab7b03` | show what the screen catches; does reasoning need its own part? | two lanes on top of Moments; reasoning lane links to Cards | — |
| `9130f84` | details on how and what; a dummy; screen and cards together but apart | the six stages and rules; items with their path; the card nested; cards fed; popups; preview | the two-lane block, This week and Open follow-ups as separate boxes |

**How it integrates:**
- **Live today:** items with their words, who, due, reminders, how they ended and whether they are in memory; all actions; popups.
- **Waits on B8** (`05-SCREEN/README.md` §5): `read_by`, `graph_written_at`, each item's popup and `card_ids[]`, `screen_items[]` on a card, and the read / skipped / threads / cards counts. Until then the page says "not served yet" in those places.
- **Cards, next:** a card fed by the screen should say so in Cards too (`screen_items[]`); the Cards page can reuse `intel/parts`.

---

## 5 · Dev and test tooling

**Details:** `02-DASHBOARD-HOME/06-RUN-AND-TEST.md`.

| Tool | What it does | Guard |
|---|---|---|
| `GENIOS_DEV_API_PROXY` (`de27094`) | `next.config.ts` rewrites `/brain-api/*` to a deployed brain. The brain's CORS refuses localhost | dev only; never set in Vercel |
| `NEXT_PUBLIC_DEV_SKIP_LOGIN` (`2db6d7d`) | opens the dashboard on localhost without the password screen | `DEV_SKIP_LOGIN` is `false` unless `NODE_ENV === "development"` |
| Sample mode | `?demo=1`, or localhost signed out: every page shows its sample under the banner | never on by itself in a deployment |
| Stand-in brain | `02-DASHBOARD-HOME/tools/mock_brain.py` on :8000 serves every route the home and Goals pages read, including brief accept and add | local only |

**How it was checked:**
- `tsc --noEmit` and `next build` are green.
- Every round was rendered signed in against the stand-in brain, and in the preview.
- The finalise → approve path was run end to end: the brief held exactly the composed line.

**Not covered:**
- The dashboard has **no test runner** (scripts: `dev`, `build`, `start`, `lint`) and no lint config.
- Phones: the app shell's sidebar never collapses, so below about 700px the content is squeezed. This was true before this branch.

---

## 6 · Risks and gaps, for the analysis

| # | What | Effect | Where it gets fixed |
|---|---|---|---|
| R1 | The branch is not merged | Customers see none of this | Rohit merges `rohit/nav-grouping`, or approves the merge |
| R2 | **Goals: a card with an empty `domain` counts as Admin.** `live.ts` folds `""` into Admin (`FOLDED_INTO_ADMIN`). `GET /cards` does send `domain` (`deliver/store.py::queue` selects `k.domain`), but the dashboard's `OpenCard` type does not declare it, so the page reads it through a cast. Separately, card details are fetched only for the first 40 cards | Any card whose domain is empty shows under Admin, whatever it really is. Cards past the 40th show without their reasoning. How many cards have an empty domain was **not measured** | **Found during this review; not fixed.** A new unit (dashboard): declare `domain` on `OpenCard`; show an empty domain as "unknown", not Admin; page the details past 40 |
| R3 | Card numbers are positions in the list | A card's `C03` can become `C02` when another card closes | D-010-G5: a stored `ordinal` on the G4 link |
| R4 | Expertise marks every authored domain Active | The page says Sales and Support are on when they are off | B4 |
| R5 | Live goals have no target, owner, progress or cards | Every live goal reads *Not measured* | GeniOS-009 G1 · G4 · G5 |
| R6 | AER and HIR have no weekly series | Section 2 shows readiness only | B2 |
| R7 | "Goals formed" reads 0 live | The week card cannot count goals | B1 (`approved_at`) |
| R8 | Decisions over time and Recent decisions | Sample only, hidden in live mode | no live source planned yet |
| R9 | No automated tests in the dashboard repo | Regressions are caught by `tsc`, `next build` and eyes | a test runner is a separate decision |
| R10 | Phone layout | Content is squeezed below about 700px | `app/dashboard/layout.tsx`, a separate fix |
| R11 | Screen: which card an item fed, and how it was read, are not served | Live items show the card step as "not served yet" | B8 (`05-SCREEN/README.md` §5) |
| R12 | Agents locked in the dashboard only | An agent already connected keeps working in the brain; only the page is closed | intended — unlock steps in `05-SCREEN/README.md` §7 |

## 7 · Integration checklist for Harsh, in order

1. **Merge** `rohit/nav-grouping` into `main` (Rohit approves). Resolve any new nav items into their groups (§1).
2. **Check Vercel:** neither `GENIOS_DEV_API_PROXY` nor `NEXT_PUBLIC_DEV_SKIP_LOGIN` is set.
3. **Small brain fixes:** B4 (Expertise `active`), B7 (`policy_safe`), B9 (the notice), B3 (the rename).
4. **Counts and links:** B5 (weekly changes in `home-summary`), B6 (cards raised this week), B8 (Screen: per-item read path, popup and card links; read/skipped/threads/cards counts).
5. **GeniOS-009 G1 + G5 → `GET /v1/goals`** with the fields in `03-GOALS/01-GOALS-PAGE.md` §5, including `tags` and `plan`. Then wire it in following `03-GOALS/README.md` §6.
6. **G4 with a stable ordinal** per link. Goals then hold their cards, and R3 closes.
7. **R2 (dashboard):** declare `domain` on `OpenCard`, show an empty domain as "unknown" rather than Admin, and page card details past 40.
8. **B2:** the AER/HIR weekly rollup (`03-AER-HIR.md` §4).

## 8 · Where each thing is written

| Question | File |
|---|---|
| Where does every page live now? | `01-NAVIGATION/README.md` |
| What does each home section show, live and sample? | `02-DASHBOARD-HOME/01-SECTIONS.md` |
| Which route feeds which number? | `02-DASHBOARD-HOME/02-DATA-WIRING.md` |
| What are AER and HIR, and what must the brain serve? | `02-DASHBOARD-HOME/03-AER-HIR.md` |
| The Screen page, and Agents locked | `05-SCREEN/README.md` |
| All brain work, B1–B9 | `02-DASHBOARD-HOME/05-BRAIN-WORK.md` |
| Run, test, ship | `02-DASHBOARD-HOME/06-RUN-AND-TEST.md` |
| Goals: decisions and wiring | `03-GOALS/README.md` |
| Goals: the page and `GET /v1/goals` | `03-GOALS/01-GOALS-PAGE.md` |
| What happened, in order | `LOG.md` |
