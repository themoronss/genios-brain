# 06 · The cards after GeniOS-009 — what appears, how it works, how it is organised

**Written for:** Rohit, Harsh and every coding agent.

**What this file is:**
- the **target**: how a card will look and behave once [`02-PLAN.md`](02-PLAN.md) G1–G9 are built;
- every example is a **real card the engine produces today** (measured in [`01-AS-IS-CARDS.md`](01-AS-IS-CARDS.md)) with the new parts **added and marked ➕**;
- nothing here is built yet.

---

## 1 · What a card IS, after GeniOS-009

> A card is the living view of **one business situation**, shown because it **moves a goal** or needs a
> **human decision**, and it stays until the situation is **verified done**, withdrawn, or no longer
> material.

Three objects, never one:

| Object | What it is | Where |
|---|---|---|
| **situation** | the business situation and its lifecycle | `context_situations` (L3) |
| **card** | its view: one card per situation, with versions | `cards` + `card_events` (L5) |
| **notification** | that someone was pinged, when, on which channel | delivery records (L5) |

Dismissing a card never resolves a situation; a new signal never makes a second card.

## 2 · The card, field by field

The left column is today's gold card (STEP-14 + migration 0065), which the engine already fills (fill
rates in `01` §2). ➕ marks a field GeniOS-009 adds.

| # | Field | Example (F24, today's real card, + new parts) | Source |
|---|---|---|---|
| 1 | **Lane** | Decision | `output_lane` (L2 judgment → lane) |
| 2 | **Headline** | Upload the Phase-1 review deck to the cohort folder | judgment, claim-checked |
| 3 | **Subject · role** | Divya Raman · the programme (watched) | `business_subject`, `relationship_role` |
| 4 | ➕ **Goal at stake** | **Moves: "Complete the accelerator's Phase-1" — advances · due 28 Sep** | `goal_refs` (G6) ← admitted `goal_situation_links` (G4) |
| 5 | **Why now** | Nothing in 13 days — longer than this file has gone quiet before (11.96 days) | tools, with n |
| 6 | **What remains** | Divya asked on 1 Sep and 13 Sep — waiting on you | `unresolved_item` |
| 7 | **Recommended** (who · what · for whom · by when) | Upload the deck by the 28th; check the unit-economics sheet is there | `recommended` |
| 8 | **Alternative** | If the deck cannot be ready, tell Divya before the date | `alternative` |
| 9 | **Wait or stop** | Nothing to wait for; done when both are in the folder | `wait_or_stop` |
| 10 | ➕ **Done when** (definition of done) | **Both files visible in the cohort folder** — evidence kind: the folder or Divya's confirmation | judgment `definition_of_done` (G7) |
| 11 | ➕ **Check-in state** | **Open → due in 2 days** (then reported / verified / unknown / overdue / conflicted / withdrawn) | `resolution_state` (G7) |
| 12 | **Outcome window · success signal · if you do nothing** | 2 days · upload confirmed · review goes without your deck | 0065 columns |
| 13 | **Confidence** | today `{C, I, U}` → ➕ **six dimensions**: evidence · frame · temporal · causal · authority · coverage, each a word with its reason | GeniOS-008 L2-9 |
| 14 | **Evidence** | the quoted lines with their mail ids | `why` (claim-checked) |
| 15 | **Versions** | v1 → v2 → v3 (what changed each time) | `card_events` |
| 16 | ➕ **Owner / decider** | **You (founder)** — the decision object's `who` | DecisionObject (G8) |
| 17 | **Actions** | Do it · Delegate to agent ➕(goes through approval) · Snooze · Wrong because… | `actions`, `executive/delegation` |

## 3 · How the board is organised (D8)

```
┌ GOALS ────────────────────────────────────────────────────────────────────────┐
│ ▸ Raise the seed round                       5 open · 2 decisions · 1 at risk │
│     Decision   Write to Rahul Menon directly: thank him …        (F03)        │
│     Decision   Email Mohit a one-page traction summary … Monday  (F13)        │
│     Monitor    Wait — Tom asked for real news only              (F14)         │
│     Investigation  Five funds, eight weeks silent — which still matters? (F15)│
│ ▸ StartupSetu recognition (DPIIT)            1 open · progress: certificate   │
│     Decision   Download the recognition certificate             (F02)         │
│ ▸ Accelerator Phase-1                        1 open · due 28 Sep               │
│     Decision   Upload the Phase-1 review deck …                 (F24)         │
│ ▸ Hire the founding engineer                 1 open · blocked on the board     │
│     Decision   Get the board's approval of the ESOP pool now    (F25)         │
├ NOT LINKED TO A GOAL (counted, never hidden) ─────────────────────────────────┤
│     Investigation  Can you tell us whether you are incubated on campus? (F22) │
├ WAITING FOR YOUR CHECK-IN ────────────────────────────────────────────────────┤
│     Reported done, not verified: Kiran's data room (F10)                      │
└───────────────────────────────────────────────────────────────────────────────┘
```

- **Order inside a goal:**
  1. decision;
  2. conflict;
  3. investigation;
  4. monitor.

  Within a lane, nearest due first. The order is decided in code (a route is never a model's job).
- **A goal header** shows its progress only when G5 can measure it. Otherwise it shows "progress: unknown — no countable metric".
- **Suppress-lane** cards are not on the board. They are in the why-not receipt list, counted.

## 4 · Which cards will exist — the five lanes with the goal added

| Lane | When | Today (measured) | After GeniOS-009 |
|---|---|---|---|
| **Decision** | a move is ours and the evidence holds | 48 of 57 cards | same, plus the goal line, done-when, check-in state and owner |
| **Investigation** | one missing fact decides the move | 8 (today) / 13 (L2 path) | same; the question names which goal it unblocks; one question per goal, not one per fund (F15, `01` A2) |
| **Conflict** | two sources disagree | 0 in the golden set | shown when `signal_conflicts` reaches the judgment (`b8a8a43c`) |
| **Monitor** | nothing to do now; a defined trigger re-opens it | 1 card, and it reads as a move (F55 *"Send Dev Malhotra the pricing sheet"*, `01` A6); F14 is correctly silent | ➕ shown **under its goal** as one wait line ("waiting — next check 14 Oct"), never an imperative, never a ping |
| **Suppress** | not material | not shown | not shown; why-not receipt kept |

**New card kinds the goal makes possible** (not producible today, because no goal object exists):

| Kind | Example | Trigger |
|---|---|---|
| **Goal at risk** | "Raise the seed round: 3 of 5 funds silent > 8 weeks; the round's deadline is 31 Dec" | G5 progress vs deadline, judged by L2 |
| **Goal achieved — verify** | "StartupSetu recognition: certificate downloaded? confirm to close the goal" | G7 reported_complete on the goal's last open situation |
| **Proposed goal** | "GeniOS sees you are preparing for Gulf Launchpad's interview — make 'Join Gulf Launchpad' a goal?" | G1 inferred goal, waiting for approval |
| **Check-in** | "Kiran's data room: you said sent — no mail to Kiran found in the window; mailbox fully read" | G7, coverage complete |
| **Unknown, not overdue** | "Vendor SOW due Friday: Drive was not readable this week — cannot tell" | G7, coverage incomplete |

## 5 · How a card behaves over time — one card, many versions

| Event | What happens to the card | Notify? |
|---|---|---|
| a situation is admitted and is material | card v1 | yes — once |
| the same situation, nothing material | nothing (change gate: 0 calls) | no |
| new evidence changes the move | v2 (a `card.updated` event names what changed) | only if the move or the deadline changed |
| the goal is revised or cancelled | the linked cards are re-judged once; v+1 or cleared | only if the move changed |
| you say done, with no proof | stays; check-in state `reported_complete` | the next check-in asks once |
| proof arrives (the mail, the file, the reply) | `verified_complete`; the card leaves the board; the goal's progress moves (G9) | a single "done" line in the morning brief |
| the source was unreadable | `unknown` — never `overdue` | the brief says which source is down |
| the situation comes back (a new reply after "handled") | the **same** card re-opens (Harsh `21b7ae10`) | yes |
| a genuinely new situation with the same person | a new card | yes |

Today's measurement (`01` §1): **15 of 57 cards already carry more than one version**, and no case
produced two cards about the same subject. The living card works. GeniOS-009 changes *what it carries*, not that it lives.

## 6 · What will NOT change

- The claim check: every sentence stands on a quoted line, or the card becomes a question.
- One card per situation; versions, not pings.
- No model routes, scores, picks a recipient or decides for a human.
- A card with no goal is shown and counted, never dropped.
