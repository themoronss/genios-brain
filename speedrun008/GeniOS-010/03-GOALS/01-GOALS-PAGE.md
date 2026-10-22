# 03.1 · The Goals page: one goal, one card

**Written for:** Harsh.

**Status, 22 Oct 2026:** built, and live where the brain allows it.
- **Commits** on `rohit/nav-grouping` (`genios-brain-dashbaord`):
  - `f137d41`: first version;
  - `e4ff9ce`: reworked to Rohit's model below.
- **Route:** `/dashboard/goals`, at Intelligence ▸ **Goals**. The home page's "This month's goal" heading links to it.

**Rohit's model, in his words (22 Oct):**
- *"Goals banenge, goals ke regarding cards banenge. Cards ki reasoning wo apna part hoga."*
- *"Ek goal ka ek card."* Its face shows *kya scenario hai · kya karna hai · target kahan se hai · capture kahan se hai*.
- **Show more** holds why the goal exists, where it was captured, the reasoning, and all its cards.
- *"Pehle sawaal pooch kar hum goals final kar lein, phir approve karwa lein."*
- *"Ek goal ke andar kai cards … jab tak goal complete nahi ho jata."*
- Metrics without bombarding: what happened, the loopholes from your side, and what we did.
- Every goal has a UUID-style id, and its cards are numbered, so anything is identified at once. Behind everything sits a proof.
- **Domains:** Admin only. Sales, Marketing, Product and Project are shown but locked. Founder Office is removed (folded into Admin).

**Screenshots** (in `screens/`):

| File | What it shows |
|---|---|
| `goals-sample-top.png` · `goals-sample-bottom.png` | The target, in sample mode. The first goal is open. |
| `goals-signed-in.png` | A signed-in owner, against the stand-in brain. |
| `goals-preview-as-it-opens.png` · `goals-preview-everything-open.png` | **The preview Rohit reviews:** `/dashboard/goals?demo=1`, as it opens (the first goal and its card C01 open) and with every goal open. |

---

## 1 · The page, top to bottom

1. **Header** and the chain: **Domain → Goal → Reasoning → Cards**.
   - There is no "See it with sample numbers" link; Rohit found it unclear.
   - The preview opens at `/dashboard/goals?demo=1`. Its banner reads "Preview — not your data. This is how Goals looks once goals, their cards and their details are connected."
   - In the preview, the first goal and its first card open by themselves.
2. **Domain tabs:** All domains · **Admin** · 🔒 Sales · 🔒 Marketing · 🔒 Product · 🔒 Project. A locked tab opens a "{Domain} is locked" panel with a link to Domains ▸ Expertise. Nothing of a locked domain is drawn.
3. **Overview:** a donut of goals by status, then three tiles: **cards working** · **cards done** (verified, not only reported) · **goals to finalise**.
4. **Goals to finalise:** for every goal GeniOS proposes, the ProposedGoalCard shows:
   - its id `G-XXXXXX` and a **Proposed** chip;
   - where GeniOS saw it (proof);
   - **four questions**: what counts and how many · by when · who owns it · how we will know it is done;
   - **"The goal will read …"**: the line the answers make, at most 200 characters (the brief's limit);
   - **Not a goal** / **Approve goal**.
5. **Admin:** a header with goal and card counts, and **Add a goal**. Then one **goal card** per goal.
6. **Cards not linked to a goal yet:** counted, never hidden, each numbered `C-XXXXXX`.
7. **Cards of locked domains:** counted in one line ("1 card belongs to a locked domain…"), not drawn.

## 2 · The goal card

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ #G-3F2A9C  On track  from your brief                                   40%  │
│ Raise the seed round                                              progress  │
│ Owner: You · Due 31 Dec · 4 cards working · 1 done                          │
│ ████████████░░░░░░░░░│░░░░░░░  (the dark mark = where it should be today)   │
│ 2 of 5 funds in diligence                                                   │
│ ┌ SCENARIO ─────────────────────┐ ┌ WHAT TO DO ──────────────────────────┐ │
│ │ Five funds in play: …         │ │ Reply to Rahul today; send Mohit …   │ │
│ ├ TARGET ───────────────────────┤ ├ CAPTURED FROM ───────────────────────┤ │
│ │ ₹4 Cr committed by 31 Dec     │ │ "We're raising a ₹4 Cr seed round…"  │ │
│ │ Source: your brief, 2 Oct …   │ │ Gmail · your mail to Anil · 28 Sep   │ │
│ └───────────────────────────────┘ └──────────────────────────────────────┘ │
│ [Cards 4 open · 1 done] [What happened 3] [From your side 2 gaps] [GeniOS did 3] │
├ Why this goal exists, its reasoning, metrics and cards          Show more ▾ ┤
│ Why this goal exists — the reason, with proof lines (source · date)         │
│ Reasoning — how progress is counted, what moves it, what threatens it       │
│ Metrics — What happened · From your side (loopholes) · What GeniOS did,     │
│           each line with its proof                                          │
│ Cards for this goal — they keep coming until the goal is done               │
│   ● #G-3F2A9C · C01  Decision  Write to Rahul Menon…   Advances   today ▾   │
│       → Scenario (who · what · why now · what remains · if nothing)         │
│       → The card's reasoning (impact on the goal · recommended + steps ·    │
│         alternative · done when · confidence by dimension · proof)          │
│   ● #G-3F2A9C · C05  Done — verified                                        │
│ Goal ID cbl_3f2a9c1e07b84d6a9e52c1d0                                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Ids:**
- **A goal's code** = `G-` + the first six hex characters of its id (`cbl_…` today, `goal_id` after G1). The full id is printed at the foot of the open card.
- **A card's number** = `{goal code} · C{nn}`, numbered within its goal. An unlinked card is `C-` + the first six hex characters of its `card_<hex>` id.
- ⚠ **Brain:** today `nn` is the card's position in the list. For a number that never shifts, G4 should store an ordinal per link (`goal_situation_links.ordinal`, assigned when first admitted) and return it. See §5.

## 3 · Live vs sample

| | Sample (`?demo=1`, or localhost signed out) | Live, signed in, today |
|---|---|---|
| Goals | 5 Admin goals with status, %, owner, due and the full face | the brief's **accepted** goal lines, in Admin. Status **Not measured**; target "Not set yet"; scenario and what-to-do say no card is linked yet |
| Captured from | a mail, a calendar entry or "added by you", with date | **real**: "GeniOS proposed it from what it read; you accepted it" or "You added this goal yourself", with the accepted date |
| Why it exists + proof | sample reason with proof lines | **real**: it is a goal in your brief, with the goal line and its date as proof |
| Metrics | three lists with proof | "—". Counted per goal once cards are linked |
| Cards in a goal | numbered, linked, each with reasoning | none yet (no G4). Every Admin card is under "Cards not linked to a goal yet" with its **real** scenario and reasoning |
| Goals to finalise | one proposal, two of four questions answered, buttons disabled | **works**: the answers make the line, and **Approve goal** accepts it *in those words* (`decide` with `text`). **Not a goal** rejects it |
| Add a goal | disabled | **works**: `POST /v1/company-brief/lines` |
| Locked domains | — | cards whose `domain` is not `admin` / `founder_office` are counted, not shown |

Checked against the stand-in brain:
1. Answering "3 signed pilot agreements · 31 Dec · Rohit" and approving left the brief holding exactly `Land three design partners — 3 signed pilot agreements by 31 Dec · owner: Rohit`.
2. The proposal left the list.
3. The new goal card appeared.

## 4 · Files

All paths are under `src/`.

```
app/dashboard/goals/page.tsx                   the route
product/internal/dashboard/goals/
  types.ts        Goal (uuid, code, face: scenario · nextMove · target · captured; why + proof; reasoning;
                  metrics; cards) · GoalCardItem (number, lane, state, scenario, reasoning) · ProposedGoal
                  (questions) · Proof · GoalsView
  sample.ts       SAMPLE_GOALS_VIEW — Admin, 5 goals, 11 cards, 1 proposal (from GeniOS-009 06 §2–§4)
  live.ts         OPEN_DOMAIN, LOCKED_DOMAINS, shortCode, cardItem, finalGoalLine, liveGoalsView, sortCards
  goals-page.tsx  GoalsPage · GoalCardView · ProposedGoalCard · CardRow · CardScenario · CardReasoning · AddGoal
lib/api-goals.ts                               getCompanyBrief · addGoal · decideGoalProposal(lineId, decision, text?)
```

## 5 · What the brain should return so every part is real

GeniOS-009 G1–G9, read through this page. `GET /v1/goals` (G1.4) should carry, per goal:

| On screen | Field (proposal) | From |
|---|---|---|
| `G-XXXXXX`, full id | `goal_id` | G1 |
| Statement, status chip | `statement`, `status` + the D-010-G1 rule | G1 + README §4 |
| Owner · due | `owner_seat`, `deadline` | G1 |
| % and progress line | `progress.state / share_bp / actual / target / why` | G5 |
| **Scenario** | `scenario`: one or two sentences on where the goal stands, written from its counted links ("5 funds: 2 in diligence, …"). The counted line is G5's; the wording is L2's, claim-checked | G5 `counted` + G3 |
| **What to do** | `next_move`: the recommendation of the goal's top open card (decision lane, nearest due) | G6 board order |
| **Target · source** | `target_text` (metric + target + unit + deadline in words), `target_source` (who set it, when) | G1 `metric`, `target`, `unit`, `deadline`, `approved_by/at` |
| **Captured from** | `captured`: `{text, source, at}`. The founder's own line, or the drafter's evidence quote and its mail/meeting | G1 `source` + the brief proposal's `evidence` |
| **Why it exists + proof** | `why`, `why_proof[]` | G1 (the approval) + the proposal's evidence |
| **Reasoning** | `reasoning[]`: how progress is counted, what moves it, what threatens it | G5 + G4 relations |
| **Metrics** | `metrics.happened[]`, `metrics.your_gaps[]`, `metrics.genios_did[]`, each `{text, source, at}` | G9 progress events, G7 check-in states (owed by the founder, overdue), L4/L5 actions (drafts, reminders, verifications) |
| **Cards** | `cards[]`: `{card_id, ordinal, relation, state}`, ordered decision → conflict → question → waiting, then due | G4 links (with a stable `ordinal`) + G6 `goal_refs` + G7 `verified_complete` |

**How the dashboard uses it:**
- Each card's own scenario and reasoning keep coming from `GET /cards/{id}`, exactly as today.
- Once `GET /v1/goals` returns the fields above, `goals/live.ts` maps them and sets `linked: true`.
- The components do not change; sample mode already draws this shape.

**The proposed goal's four questions:**
- They are client-side today. The answers become the accepted words.
- After G1 they should land as structured fields, via `PATCH /v1/goals/{id}`: `metric`/`target`/`unit` from "what counts", `deadline` from "by when", `owner_seat` from "who owns it", `definition_of_done` from "done when".
- The questions can also be served by the brain (G1 + D-010-G1), so the drafter asks what it actually lacks.
