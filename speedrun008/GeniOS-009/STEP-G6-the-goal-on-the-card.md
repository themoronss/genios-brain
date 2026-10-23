# STEP-G6 · The goal on the card, and the board grouped by goal — L5 (`deliver/`, `api/`)

**Written for:** Rohit, Harsh and every coding agent.

**Status:** planned. **Needs:** G4, G5, G0.2. **Amended 23 Oct 2026** (GeniOS-011 S26.U3; D7, D11 in
[`08-DECISIONS.md`](08-DECISIONS.md)): unit **G6.8**, the proposed-goal chip, lets the founder approve a
proposed goal in one click on the card of the work it is for, and on the home page. **Needs for G6.8:** G1.6
(and G4.5 for the L2 judgment's proposals; the drafter's show as soon as G1.6 is built).

**Source (MD):**
- *"Card mein… Kaunsa company/departmental goal affect ho raha hai"*;
- *"Card ko ek recurring notification nahi, balki ek persistent, evidence-backed business situation ka living view banao"*;
- *"reasoning result aur card presentation same object nahi hone chahiye"*.

**Target picture:** [`06-CARDS-TARGET.md`](06-CARDS-TARGET.md).


## At a glance

| | |
|---|---|
| **What** | The card shows the goal it moves (*"Moves: Raise the seed round — advances · …"*), and the card list can be grouped by goal into a **board**. |
| **Why** | MD: the card must say which goal is affected; the goal is the organising principle. It also fixes three measured defects (`01` A6–A8):<ul><li>a monitor card that reads as a move (F55);</li><li>confidence as opaque `{C, I, U}`;</li><li>the role missing on 32 of 57 cards.</li></ul> |
| **For what** | The founder sees their work under their goals; what is not linked to a goal is visible and counted. |
| **How** | Migration 0252. `CardLines.goal_line` / `goal_refs`, built from admitted links. `card_builder` copies them. The claim validator refuses an unbacked line. `deliver/board.py` and `GET /v1/insights?group=goal`. A monitor card renders as a wait. Six confidence words on L2 cards. The role comes from the brief's kind, else `contact`. |
| **What changes after** | With `goal_board` on, the founder's list becomes the board in `06-CARDS-TARGET.md` §3. |
| **Done when** | The golden tenant's board matches 06 §3's shape · "Not linked" counted · monitor cards read as waits · L2 cards show six confidence words. |
| **Do not** | Write the goal line from model text · hide unlinked cards · show suppress cards on the board · send a notification for a regrouping. |

---

## 1 · What is true today

- **The gold card fields** come from the review's `card_lines` (`reason/expert/card_lines.py`, code-written: why now, what remains, subject and role, window). They are stored in `expert_reviews.card_lines` (0221), carried on the signal as `capability_render.gold`, and copied by `deliver/card_builder._gold(:902)` onto `cards` (0065 columns).
- **On the L2 path** (`l2_cards`, `de795bb8`), an ADMITTED judgment is written as the file's review, so it takes the same road to the card.
- **The card list** is `GET /v1/insights` (`api/intelligence_routes.py:589`). It is flat; there is no grouping by goal.
- **Measured problems this step also closes** (`01-AS-IS-CARDS` §3):
  - A6: a monitor-lane card reads as a move (F55);
  - A7: confidence is shown as `{C, I, U}`;
  - A8: the role is missing on 32 of 57 cards.

## 2 · Design

1. **The goal line is written by code, from admitted links only** (G4), never from the raw judgment. Its shape:

   *"Moves: Raise the seed round — advances · 2 of 5 funds answered"*

   | Relation | Word on the card |
   |---|---|
   | advances | Moves |
   | threatens | At risk |
   | depends_on | Blocks |
   | unclear | May matter to |

   The progress part is G5's `measured` text or its `counted` text. More than one link: the first by goal deadline, then *"+1 goal"*.
2. **`goal_refs` on the card** for grouping: the open link ids and their goal ids.
3. **The board** is a grouping of the same cards, not new cards:
   - `GET /v1/insights?group=goal` returns `[{goal, progress, lanes: {decision: [...], conflict: [...], investigation: [...], monitor: [...]}}, …, {goal: null, label: "Not linked to a goal", …}]`;
   - order is computed in code: goals by deadline; lanes in the fixed order decision → conflict → investigation → monitor; cards by `nearest_due`;
   - suppress-lane cards are never on the board; they are in the why-not list, counted.
4. **The monitor lane renders as a wait**:
   - headline *"Waiting: <what> — next look <date>"*;
   - the move is kept only in the card's detail;
   - no notification;
   - fixes A6.
5. **Confidence on the card**: show the six named dimensions when the L2 judgment carries them (`L2Judgment.confidence`, keys evidence · frame · temporal · causal · authority · coverage), each a level word with its reason. The old `{C, I, U}` stays only on old-path cards. Closes A7 on the L2 path (GeniOS-008 L2-9).
6. **The role (A8)**: `card_lines._person` already resolves the counterparty. When the brief's in-motion line names the counterparty, the role comes from that line's kind (investor · program · compliance · hiring · partner); otherwise the role is `contact`, **said**, never left empty.

## 3 · Units

| Unit | File | Change |
|---|---|---|
| G6.1 | `migrations/0252_card_goals.sql` | `alter table cards add column if not exists goal_refs jsonb not null default '[]'::jsonb; … goal_line text;` plus an index `cards (org_id) where goal_refs <> '[]'` |
| G6.2 | `reason/expert/card_lines.py` | `CardLines.goal_line`, `CardLines.goal_refs`; `_goal_line(links, goals, progress) -> (str \| None, tuple)`, pure. The L2 path passes the links just written (G4) |
| G6.3 | `deliver/card_builder.py` | copy `goal_line` and `goal_refs` from `_gold(signal)` onto the card; a monitor-lane headline is rendered as a wait (G6 §2.4) |
| G6.4 | `deliver/claim_validator.py` | refuse a `goal_line` whose goal id has no open admitted link (`GOAL_LINE_UNBACKED`) — the card falls back to no goal line, counted |
| G6.5 | `api/intelligence_routes.py` | `group=goal` on `GET /v1/insights`; the pure grouping lives in `deliver/board.py` (new: `board(cards, goals, progress) -> list[GoalGroup]`) |
| G6.6 | `deliver/lane_display.py` | lane copy for the board headers (decision · conflict · investigation · monitor), in the reader's words |
| G6.7 | `platform/l4_activation.py` | feature `goal_board`, per tenant, never on by default; needs `l2_cards` |
| G6.8 | `deliver/goal_chip.py` (new), `api/intelligence_routes.py`, `platform/l4_activation.py` | the proposed-goal chip (below); feature `goal_chip`, per tenant, never on by default |

### G6.8 · The proposed-goal chip (amendment, 23 Oct 2026)

**Why.** `06-CARDS-TARGET.md` §4 lists a "Proposed goal" card kind, and no unit built it. A proposal sitting
only in the brief's list is easy to miss; Rohit's ask is that goals come from what is in motion without typing.
So the proposal is shown where the founder already looks: on the card of the work it is for. **A chip, not
a new card**: a proposal makes no card of its own and sends no notification.

**What it shows** (code-written, never model text):

> **Make this a goal?** Get admitted to <the accelerator>'s Singapore cohort · under "Get into accelerator and
> incubator programs" · by <deadline> — **Approve** · **Not now**

| Part | Rule |
|---|---|
| which proposal | a **pending** `goals` line resting on the card's file: `goal_proposal.subject_ref` (G1.6) or an evidence `file_id` (the drafter's, GeniOS-011 S27.U1), equal to the card's `file:<id>`. G4.5's `held_work` keeps it to one per file; if two exist, the oldest |
| words | the line's text; the parent's statement and the deadline from `goal_proposal`, when present; "proposed by GeniOS" and the `why` in the card's detail |
| **Approve** | `POST /v1/company-brief/proposals/{line_id}/decide` with `{"decision": "accept"}`: one click, no text. The next sweep's `sync_from_brief` makes the goal active, `approved_by` = the founder |
| **Not now** | the same route with `{"decision": "reject"}`; that work is not proposed again for 90 days (`REJECTED_QUIET_DAYS`) |
| who sees it | the account owner only (the route's `require_account_owner`); other seats see no chip |
| where it is computed | at read, in `GET /v1/insights`, from `company_brief_store.pending` — **no column**, so a decided proposal disappears without a write |

**On the home page:** "N goals waiting for you" (GeniOS-011 S27.U3) lists the same pending goal lines with the
same Approve and Not now. A proposal whose file has no open card (a quiet file) shows there and on the Goals
page only.

**Dashboard:** the rendering follows the UI rule (a clickable dummy, Rohit's approval, then real files). The
brain part — `chip_for` and the route field — does not wait for it.

**`deliver/goal_chip.py`:** `chip_for(card, pending_goal_lines) -> GoalChip | None`, pure. The route adds
`goal_proposal: {line_id, statement, parent, deadline, why} | null` to each card it returns.

## 4 · LLM use

**None new.** The card's sentences are the judgment's, already checked. The goal line and the board are code.

## 5 · Tests

**`tests/deliver/test_goal_line.py`** (pure):
1. one `advances` link → *"Moves: … — advances"*-shaped line;
2. two links → the first by deadline, then *"+1 goal"*;
3. no link → None;
4. an `unclear` link → *"May matter to …"*.

**`tests/deliver/test_board.py`** (pure):
1. grouping and order;
2. a card with no goal lands in "Not linked to a goal" and is **counted**;
3. suppress never appears;
4. a monitor card's headline is a wait.

**`tests/deliver/test_claim_validator_goal.py`:** an unbacked goal line is refused, and the card is still delivered without it.

**Golden — new marking:**
- F03, F02, F24 and F25 cards carry their goal line;
- F56's card (when F56 passes) sits under "Not linked";
- an unchanged sweep sends no notification.

**Mutation proofs:**
- drop G6.4 → test 1 of `test_claim_validator_goal.py` fails;
- remove the "Not linked" group → board test 2 fails.

**G6.8 tests** — `tests/deliver/test_goal_chip.py` (pure):
1. a pending goal line on the card's file → a chip with its words, parent and deadline;
2. an accepted, rejected or removed line → no chip;
3. a pending line on another file → no chip;
4. a pending `in_motion` line on the same file → no chip (goals only).

**`tests/api/test_goal_chip_route.py`** (PG): Approve through the chip's route → the line is accepted and,
after `sync_from_brief`, the goal is `active` with `approved_by` = the owner who clicked; a non-owner seat
→ 403 and the goal stays `proposed`.

**G6.8 mutation proofs:** make `chip_for` ignore the line's status → test 2 fails; drop the section check →
test 4 fails.

## 6 · Flags, rollout, rollback

- **Flags:** `goal_board`, per tenant, after `l2_cards` has run a week clean (G0.2).
- **Rollback:** the flag off returns the flat list. The columns stay.

## 7 · Done when

- (G6.8) with `goal_chip` on, a card whose file has a pending goal proposal shows the chip; one click on
  Approve makes the goal active after the next sweep, with the founder as approver; nothing else does.

- On the golden tenant with `goal_board` on, the board matches `06-CARDS-TARGET.md` §3's shape:
  - every card is under a goal or counted under "Not linked";
  - monitor cards read as waits;
  - L2-path cards show the six confidence words.

## Harsh's checklist — in order

1. **Migration** 0252 (the number check).
2. **Tests first:**
   - `tests/deliver/test_goal_line.py`, `test_board.py`, `test_claim_validator_goal.py`;
   - a render test: a monitor card's headline is a wait;
   - a confidence render test: six words on an L2 card, `{C, I, U}` kept on an old-path card.
3. **`reason/expert/card_lines.py`:**
   - `_goal_line` (pure);
   - the L2 path passes the links just written in G4's savepoint, so the review's card lines carry them.
4. **`deliver/card_builder.py`:**
   - copy `goal_line` and `goal_refs` from `_gold(signal)`;
   - the monitor headline as a wait;
   - the role fallback to `contact`.
5. **`deliver/claim_validator.py`:** `GOAL_LINE_UNBACKED`.
6. **`deliver/board.py`**, and `group=goal` on `GET /v1/insights` (`api/intelligence_routes.py:589`).
7. **The `goal_board` feature** in `platform/l4_activation.py` (it needs `l2_cards`).
8. **Golden marking:**
   - F02, F03, F24 and F25 carry their goal line;
   - an unchanged sweep sends no notification.
9. **Re-run the card dump** (handover §6.6) and compare with `01-AS-IS-CARDS.md`: role fill should rise from 25/57; monitor headlines become waits.
10. **G6.8** (needs G1.6 only): `tests/deliver/test_goal_chip.py` and the route test first; `deliver/goal_chip.py`;
    the `goal_proposal` field on `GET /v1/insights`; the `goal_chip` feature; the dashboard chip as a dummy
    first; two mutation proofs.
11. **Mutation proofs, guards, push, CI, logs.** Switch `goal_board` on for D6's tenant only after a week of `l2_cards` running clean.

## Brief for a coding agent

Paste `10-AGENT-BRIEFS.md` §1 first, then this.

**Task:** STEP-G6. Put the goal line on the card, build the goal board, render monitor cards as waits, show the six confidence words on L2 cards, and fill the role.

**Read first:**
- the preamble;
- `STEP-G6-the-goal-on-the-card.md`;
- `06-CARDS-TARGET.md`;
- `reason/expert/card_lines.py`;
- `deliver/card_builder.py` (`_gold`, `gold_headline`), `deliver/claim_validator.py`, `deliver/lane_display.py`;
- `api/intelligence_routes.py` around `GET /v1/insights`.

**You own:**
- `migrations/0252_card_goals.sql`;
- `reason/expert/card_lines.py` (the goal fields);
- `deliver/card_builder.py`, `deliver/claim_validator.py`, `deliver/board.py` (new), `deliver/lane_display.py`;
- `api/intelligence_routes.py` (`group=goal` only);
- `platform/l4_activation.py` (the feature constants: `goal_board`, `goal_chip`);
- `deliver/goal_chip.py` (new, G6.8);
- the new tests.

**Do not touch:**
- the review's model text;
- `context/` writers.

**Acceptance:**
- §5's tests;
- the golden goal lines;
- "Not linked" counted;
- (G6.8) the chip from pending goal lines, one-click Approve through the brief route;
- four mutation proofs (two for G6, two for G6.8);
- a card-dump comparison in the report.
