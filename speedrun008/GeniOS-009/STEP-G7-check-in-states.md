# STEP-G7 · Check-in states — "is it done?" (L2 writes the definition, L3 keeps the state, L4's ladder is the clock)

**Written for:** Rohit, Harsh and every coding agent.

**Status:** planned. **Needs:** G0.3, G3.

**Source (MD):**
- *"Check-in ka uddeshya kewal status refresh karna nahi hai… kya badla, kis baat ka praman hai, kya abhi bhi agyaat hai"*;
- the seven outcomes: verified complete · reported complete · still open · overdue · unknown · conflicted · withdrawn;
- *"No new signal ≠ no progress"*;
- *"Task complete but outcome unverified → pending verification"*.


## At a glance

| | |
|---|---|
| **What** | A check-in that tells **verified done** from **reported done**, **overdue** from **unknown**, plus **conflicted** and **withdrawn**. It lives on the situation, and runs from a definition of done the judgment writes. |
| **Why** | MD: task done ≠ outcome achieved; no new signal ≠ no progress; unknown ≠ false. Today only a card's ending separates VERIFIED from REPLIED, and the check-in never reads coverage, so an unread mailbox can look like silence. |
| **For what** | So nobody is told "overdue" when GeniOS could not see; a click never closes a situation; and G9 credits only proven outcomes. |
| **How** | `DoneWhen` in the judgment. Migration 0253. A pure `context/checkin.evaluate` with 7 ordered rules. It runs on the L2 pass, on a check-in-due trigger, and on new evidence. A situation resolves only from verified or withdrawn. The card shows the state. |
| **What changes after** | With `checkin_states` on:<ul><li>a "done" click shows *"reported — waiting for proof"*;</li><li>a disconnected mailbox shows *"unknown — <mailbox> not read"*;</li><li>proof closes the situation.</li></ul> |
| **Done when** | F68, F69 and F70 pass · no situation resolves from a report · no unread window ever produces "overdue". |
| **Do not** | Add a model call to the evaluator · mark overdue without full coverage · resolve on a report · re-date a conditional promise. |

---

## 1 · What is true today

- **Card endings already separate proof from report** (`context/file_outcomes.py:39-48`):
  - VERIFIED — the ask closed, answered, by the event that closed it;
  - REPLIED — cleared while the ask only got a reply;
  - TAKEN, CALLED_WRONG, LAPSED, DISMISSED, REPLACED, CLEARED, OPEN, UNRECORDED.
- **A card action means "claimed", never "done"** (`deliver/actions.py:299`).
- **Situations:**
  - `context_situations.status`: active | dormant | resolved | archived;
  - `resolved_by`: fact | human | statement;
  - statement resolutions stick (`df3c2aa8`); a handled card returns on new evidence (`21b7ae10`).
- **Coverage:** `context/coverage_receipt.receipt_for(:74)` / `covers(:104)` say whether a mailbox was read through a window. **The check-in does not ask it**: silence in an unread window can still read as "nothing came".
- **The execution reminder** (`executive/reminder.decide_reminder`) returns a `next_check_at`, and the ladder speaks at 1/3/7/14 days.
- **The conditional-promise fix** (`bda38c3d`): a conditional promise gets no due date.

## 2 · Design

1. **The judgment writes the definition of done.** `L2Judgment.done_when: DoneWhen | None`:
   - `says` — one line, e.g. *"Kiran has the data-room link and the cap table"*;
   - `evidence_kind` — one of `reply_from_counterparty | document_present | meeting_held | status_on_portal | payment | founder_confirmation`;
   - `from_whom` (optional);
   - `by_when` (optional).

   Claim-checked like every line. A decision-lane result must have one; others may.
2. **A pure evaluator decides the state.** `context/checkin.evaluate(situation, done_when, evidence, coverage, now) -> CheckIn`, **pure, no model**, first matching rule wins:

| # | Condition | State |
|---|---|---|
| 1 | the situation was withdrawn, superseded or cleared (`CLEARED`, `REPLACED`, a REJECT on admission) | `withdrawn` |
| 2 | evidence of `done_when.evidence_kind` arrived after the move, **and** the ask's closure is VERIFIED (`file_outcomes`) | `verified_complete` |
| 3 | two sources disagree about the done-state (`signal_conflicts` on this subject) | `conflicted` |
| 4 | the founder pressed done, or a reply came that only REPLIED (no evidence of the kind) | `reported_complete` |
| 5 | `by_when` passed and the sources that could carry the evidence are **fully covered** for the window (`covers(...) is True`) | `overdue` |
| 6 | `by_when` passed and coverage is **incomplete** (a mailbox disconnected, paused, or not read through) | `unknown`, why = which source |
| 7 | otherwise | `open` |

3. **When it runs:**
   - on every L2 pass for a judged subject;
   - when the ladder's `next_check_at` is due (a new L2 trigger, `TRIGGER_CHECKIN_DUE`; the fingerprint gains the check-in rung, so a due check-in re-reads once);
   - on new evidence.

   **0 model calls** when rules 1–7 decide from code facts. When rule 2 needs to know whether a reply *answers* the ask, the existing ask-closure reading decides (the STEP-16 VERIFIED/REPLIED split), and no new model site is added.
4. **Stored on the situation** (L3), and shown on the card (G6). A situation resolves to `resolved` only from `verified_complete` or `withdrawn` — never from `reported_complete`.

## 3 · Units

| Unit | File | Change |
|---|---|---|
| G7.1 | `contracts/reasoning_result.py` | `DoneWhen` + `L2Judgment.done_when`; claim check `DONE_WHEN_UNPRINTED` when `from_whom` or a date is not printed; a decision-lane result without `done_when` → `NO_DONE_WHEN` (a line problem, not a refusal) |
| G7.2 | `migrations/0253_situation_checkin.sql` | `alter table context_situations add column if not exists resolution_state text, add column if not exists done_when jsonb, add column if not exists checkin_at timestamptz, add column if not exists checkin_why text;` plus a check constraint on the seven states (and NULL for rows before G7) |
| G7.3 | `context/checkin.py` (new) | `CheckIn(state, why, evidence_ref, coverage_ref)`; `evaluate(...)`, pure; `write_checkin(conn, …)`, writing only on a state change, plus a `card_events` row `situation.checkin` naming from → to |
| G7.4 | `reason/l2/sweep.py` | after admission: `done_when` saved on ADMIT; `checkin.evaluate` for every judged subject with a live situation; `TRIGGER_CHECKIN_DUE` |
| G7.5 | `context/situations.py` | `resolved` only from `verified_complete` / `withdrawn` for situations that carry a `done_when`; older rows keep today's path |
| G7.6 | `deliver/card_builder.py` | the check-in state on the card; a `reported_complete` card stays on the board under "Waiting for your check-in" |

## 4 · LLM use

- `done_when` is written inside the existing judgment: ≈ 30 output tokens, no new call.
- The evaluator makes no call.

## 5 · Tests

**`tests/context/test_checkin.py`** (pure, one case per rule of §2.2, plus these):
1. done pressed, no artifact → `reported_complete`;
2. the artifact arrives → `verified_complete`;
3. due passed, mailbox disconnected → `unknown` naming the mailbox, **never `overdue`**;
4. due passed, fully covered, nothing came → `overdue`;
5. a conditional promise → no `by_when`, never overdue (the `bda38c3d` rule kept).

**`tests/reason/l2/test_done_when.py`:** a decision result with no `done_when` is a counted problem; an unprinted `from_whom` is dropped.

**Golden — new cases, written as JSON in `tests/replays/specs/founder/`, with cassettes recorded by the ideal reader:**
- **F68 "You said the data room went; it did not"**: an investor asks for the data room; the founder presses done; no mail to the investor in a fully covered window → `reported_complete`, then at the due rung `overdue`;
- **F69 "The mailbox went quiet because it was disconnected"**: the same as F68 with the connection paused → `unknown`, never overdue;
- **F70 "The signed NDA closes it"**: F57's shape → `verified_complete`, with the card ended VERIFIED.

**Mutation proofs:**
- swap rules 5 and 6 → F69 fails;
- let `reported_complete` resolve the situation → F68 fails.

## 6 · Flags, rollback

- **Flags:** `checkin_states`, per tenant. Off: the evaluator writes the state and nothing reads it.
- **Rollback:** the flag off.

## 7 · Done when

- F68, F69 and F70 pass;
- no situation resolves from a report alone;
- no unread window ever produces "overdue".

## Harsh's checklist — in order

1. **Write the three golden cases first** (`tests/replays/specs/founder/F68.json`, `F69.json`, `F70.json`), modelled on F10 / F57's shape:
   - F68 reported, not verified;
   - F69 the mailbox paused, so unknown;
   - F70 the signed NDA verifies.

   Add them to the label sheet and record their cassettes with the ideal reader. They start **strict-xfail**.
2. **Tests first:**
   - `tests/context/test_checkin.py`: one case per rule, plus §5's five;
   - `tests/reason/l2/test_done_when.py`.
3. **Contract:** `DoneWhen` + `L2Judgment.done_when`, with its claim-check codes. Prompt: one line asking for it on decision results (bump the version, re-record).
4. **Migration** 0253.
5. **`context/checkin.py`:**
   - `evaluate` (pure, rule order exactly as §2.2);
   - `write_checkin` (only on change, plus a `card_events` row).
6. **`reason/l2/sweep.py`:**
   - save `done_when` on ADMIT;
   - evaluate per judged subject;
   - add `TRIGGER_CHECKIN_DUE` and the check-in rung in the fingerprint.
7. **`context/situations.py`:** resolution only from verified or withdrawn for rows that carry `done_when`.
8. **`deliver/card_builder.py`:** the state on the card; a reported card under "Waiting for your check-in".
9. **Flip F68–F70** from xfail to pass. Mutation proofs:
   - swap rules 5 and 6;
   - let a report resolve.
10. **Guards, push, CI, logs.** Switch `checkin_states` on per tenant.

## Brief for a coding agent

Paste `10-AGENT-BRIEFS.md` §1 first, then this.

**Task:** STEP-G7. Add the definition of done to the judgment and a pure check-in evaluator that never confuses a report with proof, or a blind spot with lateness.

**Read first:**
- the preamble;
- `STEP-G7-check-in-states.md`;
- `context/file_outcomes.py`, `context/coverage_receipt.py`;
- `executive/reminder.py`;
- `context/situations.py` (the on-conflict clause);
- `tests/replays/specs/founder/F10.json` and `F57.json` (shapes for the new cases).

**You own:**
- `contracts/reasoning_result.py` (`DoneWhen`);
- `reason/l2/prompt.py` (one line);
- `migrations/0253_situation_checkin.sql`;
- `context/checkin.py`;
- `reason/l2/sweep.py` (the check-in call, the trigger and the rung only);
- `context/situations.py` (the resolution rule only);
- `deliver/card_builder.py` (the state display only);
- F68–F70 and their cassettes;
- the tests.

**Do not touch:**
- existing case expectations;
- `capture/`.

**Acceptance:**
- every rule has a test;
- F68–F70 pass;
- two mutation proofs.
