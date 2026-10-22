# 03.1 · The Goals page as it stands

**Written for:** Harsh.

**Status, 22 Oct 2026:**
- Built, and live where the brain allows it.
- Current state: dashboard `cc1b58f` on `rohit/nav-grouping` (`genios-brain-dashbaord`).
- **Route:** `/dashboard/goals`, Intelligence ▸ **Goals**.
- **Preview** (the full target, labelled "Preview — not your data"): `/dashboard/goals?demo=1`.
- The home page's "This month's goal" heading links here.
- How it got here (seven rounds of Rohit's review) is in `../04-BUILD-REVIEW.md` §3.

**Rohit's model, in his words (22 Oct):**
- *"Goals banenge, goals ke regarding cards banenge. Cards ki reasoning wo apna part hoga."*
- *"Ek goal ka ek card"*: on its face, *kya scenario hai · kya karna hai · target kahan se hai · capture kahan se hai*.
- *"Pehle sawaal pooch kar hum goals final kar lein, phir approve karwa lein."*
- *"Ek goal ke andar kai cards … jab tak goal complete nahi ho jata."*
- Metrics without bombarding: what happened, the loopholes from your side, and what we did.
- Every goal has a UUID-style id, and its cards are numbered. Proof sits behind everything.
- Admin only. Sales, Marketing, Product and Project are listed and locked; Founder Office is folded into Admin.
- Goals are arranged by month and carry predefined tags, a deadline and a plan.
- **Look:** the dashboard's theme, professional (no rainbow), details as small cards, and a goal visibly different from a card.

**Screenshots** (in `screens/`):

| File | What it shows |
|---|---|
| `goals-preview-as-it-opens.png` | The preview as it opens: the overview strip, goals to finalise, Admin's tag row, October 2026 first, and goal 1's cards open. |
| `goals-preview-details-open.png` | The seed-round goal's **Details** and its card 1 open, both as small cards. |
| `goals-signed-in.png` | A signed-in owner, against the stand-in brain (`../02-DASHBOARD-HOME/tools/mock_brain.py`). |

---

## 1 · The page, top to bottom

1. **Header:** "Intelligence · October 2026", **Goals**, and one line: Details opens the goal, Cards opens its work. In the preview, the orange "Preview — not your data" banner.
2. **Domain tabs:** All domains · **Admin** · 🔒 Sales · 🔒 Marketing · 🔒 Product · 🔒 Project. A locked tab shows a "{Domain} is locked" panel that links to Domains ▸ Expertise.
3. **Overview, on one strip:** a donut of goals by status with a dot legend · cards working · cards done · to finalise.
4. **Goals to finalise:** a dashed "Proposed goal" card for each goal GeniOS proposes. It shows:
   - id and proof (where GeniOS saw it);
   - **four questions**: what counts and how many · by when · who owns it · how we will know it is done;
   - **"The goal will read …"** (≤ 200 characters);
   - **Not a goal** / **Approve goal**.
5. **Admin:**
   - **Header:** name, note, goal and card counts, and **Add a goal**.
   - **The tag row:** All · Fundraising · Investors · Compliance · Finance · Vendors · Hiring · Legal · Operations, each with a count. It filters the goals.
   - **Goals by month**, newest first: "October 2026 · 3 goals · 1 done", then September, then August. Inside a month, open goals come before done ones.
6. **Cards not linked to a goal yet:** a dashed group, counted, never hidden.
7. **Cards of locked domains:** counted in one line, not drawn.

## 2 · The goal card

```
┌──────────────────────────────────────────────────────────────────────────────────┐  level 1 — the big card,
│  (40%)  GOAL  #G-3F2A9C  ● On track  [Fundraising] [Investors]  [Details▾][Cards 5▾] │  deepest shadow, a two-
│         Raise the seed round                                                     │  layer stack behind it
│         You · due 31 Dec · 2 of 5 funds in diligence                             │  when closed with cards
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━░░░░░░░░│░░░░░░  (the mark = where it should be today)   │
├─ Details: only the goal, as small cards ──────────────────────────────────────────┤
│  THE GOAL           [Scenario ·········][What to do ········]                      │
│                     [Target+src][Deadline · N days left][Owner · tags][Captured from]│
│  PLAN & REASONING   [Plan ✓ ✓ ● ○ ○ with dates][Why it exists + proof][Reasoning]   │
│  METRICS            [What happened n][From your side n][What GeniOS did n]          │
│  Goal ID cbl_…                                                                    │
├─ Cards: only the cards, one under another ────────────────────────────────────────┤
│  [1] DECISION  Write to Rahul Menon directly…     ↑ Advances      today      ▴    │  level 2 — a quiet row;
│      #G-3F2A9C · C01 · Decision · due today                 Open in Cards →       │  click opens it in
│      SCENARIO   [What's going on ······][Who][Why now][What remains][If nothing]   │  place, one at a time
│      REASONING  [What it does to the goal][Done when][What to do + steps]         │  level 3 — small cards
│                 [Otherwise][Confidence ●●●][Proof — quotes]                        │
│  [2] DECISION  Email Mohit a one-page traction summary…  ↑ Advances  Mon 27 Oct ▾ │
│  [3] QUESTION  Five funds, eight weeks silent…        ↓ Threatens              ▾  │
│  [✓] DONE      Share the data room with Kiran — verified opened                ▾  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

- **Three levels that look like three levels:** goal → card → small cards inside. Shadows step down a level at a time (`L1` · `L2` · `L3` in `goals-page.tsx`).
- **Two separate toggles:** **Details** opens only the goal, **Cards** opens only its cards. Inside Cards, one card opens at a time, in place.
- **The theme** (DESIGN.md): 12px cards, 8–10px controls, hairlines, `eyebrow` labels, ink for actions.
- **Colour:**
  - Ink and greys carry everything.
  - The burgundy accent marks only what needs you: at-risk and blocked dots, "↓ Threatens", "From your side", the plan step in progress, and the open card's edge line.
  - Status is a dot and a word.
- **Ids:**
  - A goal's code is `G-` + six hex characters of its id; the full id is at the foot of Details.
  - A card's number is `{goal code} · C{nn}` within its goal (`C-XXXXXX` when unlinked).
  - ⚠ Today `nn` is the card's position in the list. A number that never shifts needs a stored ordinal (§5).
- **Deadline:** `dueDate` (ISO) gives "N days left / due today / N days past".
- **Plan:** steps with ✓ done · ● doing · ○ next, each with a date.

## 3 · Live vs preview

| | Preview (`?demo=1`, or localhost signed out) | Live, signed in, today |
|---|---|---|
| Goals | 6 Admin goals across Aug–Oct 2026, with status, %, owner, deadline, tags, plan and the full face | the brief's **accepted** goal lines, grouped by the month they were accepted. Status **Not measured**; target "Not set yet"; no tags, no plan |
| Captured from · why + proof | sample mail or calendar quotes | **real**: "GeniOS proposed it from what it read; you accepted it" or "You added this goal yourself", with the date and the goal line as proof |
| Metrics | three lists with proof | "counted once its cards are linked" |
| Cards in a goal | numbered, linked, each with full reasoning | none yet (no G4). Every Admin card is under "Cards not linked to a goal yet", with its **real** scenario and reasoning |
| Goals to finalise | one proposal, buttons disabled | **works**: the answers make the line; **Approve goal** accepts it in those words (`decide` with `text`); **Not a goal** rejects it |
| Add a goal | disabled | **works**: `POST /v1/company-brief/lines` |
| Locked domains | — | cards whose `domain` is not `admin` / `founder_office` are counted, not shown |

Checked against the stand-in brain: answering "3 signed pilot agreements · 31 Dec · Rohit" and approving left the brief holding exactly `Land three design partners — 3 signed pilot agreements by 31 Dec · owner: Rohit`.

## 4 · Files

All paths are under `src/`.

```
app/dashboard/goals/page.tsx                   the route
product/internal/dashboard/goals/
  types.ts        Goal (uuid, code, status, pct, due/dueDate, owner, month, tags, plan, face, why+proof, reasoning,
                  metrics, cards) · GoalCardItem · ProposedGoal (questions) · PlanStep · Proof · ADMIN_TAGS · GoalsView
  sample.ts       SAMPLE_GOALS_VIEW — Admin, 6 goals (Aug–Oct 2026), 12 cards, 1 proposal (GeniOS-009 06 §2–§4)
  live.ts         OPEN_DOMAIN · LOCKED_DOMAINS · shortCode · cardItem · finalGoalLine · liveGoalsView · sortCards
  goals-page.tsx  GoalsPage · GoalCardView · GoalDetails · Plan · Mini · MetricBox · CardDeck · CardItem · CardBody
                  · ProposedGoalCard · AddGoal · StatusTag · RelationTag · TagChip
lib/api-goals.ts                               getCompanyBrief · addGoal · decideGoalProposal(lineId, decision, text?)
```

It reuses the home page's `charts.tsx` (Donut, PaceBar) and `ui.tsx` (IconBox, Pill).

## 5 · What the brain should return so every part is real

`GET /v1/goals` (GeniOS-009 G1.4) should carry, per goal:

| On screen | Field (proposal) | From |
|---|---|---|
| `G-XXXXXX`, full id | `goal_id` | G1 |
| Statement · status | `statement`, `status` + the D-010-G1 rule | G1 + README §4 |
| Owner · deadline · days left | `owner_seat`, `deadline` (ISO date) | G1 |
| Month group | `created_at` / `approved_at` | G1 |
| **Tags** | `tags[]` from `ADMIN_TAGS`: set by the founder, or proposed by the drafter and approved | new field on G1 |
| % and progress line | `progress.state / share_bp / actual / target / why` | G5 |
| **Scenario** | `scenario`: one or two sentences from the counted links, worded by L2, claim-checked | G5 `counted` + G3 |
| **What to do** | `next_move`: the top open card's recommendation | G6 board order |
| **Target · source** | `target_text`, `target_source` | G1 `metric` / `target` / `unit` / `deadline` / `approved_by/at` |
| **Captured from** | `captured {text, source, at}` | G1 `source` + the proposal's `evidence` |
| **Plan** | `plan[] {step, state, when}`: milestones (child goals with `parent_goal_id`) or a plan list | G1 (+ G7 states) |
| **Why it exists + proof** | `why`, `why_proof[]` | G1 approval + the proposal's evidence |
| **Reasoning** | `reasoning[]` | G5 + G4 relations |
| **Metrics** | `metrics.happened[] / your_gaps[] / genios_did[]`, each `{text, source, at}` | G9 events · G7 check-ins · L4/L5 actions |
| **Cards** | `cards[] {card_id, ordinal, relation, state}` with a **stable `ordinal`** per link | G4 + G6 `goal_refs` + G7 |

**How the dashboard uses it:**
- Each card's own scenario and reasoning keep coming from `GET /cards/{id}`.
- Once `GET /v1/goals` returns the fields above, `goals/live.ts` maps them and sets `linked: true`.
- The components do not change; the preview already draws this shape.

**The four questions:**
- Client-side today; the answers become the accepted words.
- After G1 they should land as structured fields (`PATCH /v1/goals/{id}`): what counts → `metric`/`target`/`unit` · by when → `deadline` · who owns it → `owner_seat` · done when → `definition_of_done`.
