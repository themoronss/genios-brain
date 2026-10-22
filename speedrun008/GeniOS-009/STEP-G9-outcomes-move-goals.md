# STEP-G9 · Outcomes move goals, and learning is governed — L6 (`feedback/`) + L3

**Written for:** Rohit, Harsh and every coding agent.

**Status:** planned. **Needs:** G5, G7, G8.

**Source (MD):**
- *"GeniOS ko expected aur actual compare karna hai. Task completion, goal progress aur goal achievement alag hain"*;
- *"Learning should come from reviewed outcomes, not from automatically turning every observed correlation into a permanent business rule"*;
- the learning chain: Observation → Candidate → Validation → Governance → Publisher → versioned brain.


## At a glance

| | |
|---|---|
| **What** | Verified outcomes move goals. A reached goal asks the founder to confirm. A goal at risk is judged. Learning from outcomes is governed. |
| **Why** | MD: verify outcomes, adapt, learn only from reviewed outcomes. Today:<ul><li>outcomes are written and move nothing;</li><li>the behaviour and adaptive learning units are stubs;</li><li>`macv_ledger` has no writer.</li></ul> |
| **For what** | The founder sees real progress toward each goal, and GeniOS improves from what actually worked, without one click becoming a rule. |
| **How** | Migration 0255 (`goal_progress_events`). `record_verified` on every verified transition. `completion_due` plus the founder's confirmation. A goal subject `goal:<id>` for the L2 pass. `goal_learning` candidates through `brain_pipeline` (≥ 3 independent). An adaptive lease for the deadline. |
| **What changes after** | With `goal_progress` on:<ul><li>progress lines move only with proof;</li><li>"Goal reached — confirm" cards appear;</li><li>"Goal at risk" cards appear when the judgment says so.</li></ul> |
| **Done when** | F71 passes · every goal's progress traces to verified evidence · no brain entry from fewer than 3 outcomes · the expert brain is untouched. |
| **Do not** | Complete a goal in code · credit a report · publish a pattern from fewer than 3 outcomes · write the expert brain · write `macv_ledger` before D4. |

---

## 1 · What is true today

- **Outcomes are written, and nothing moves a goal** (no goal exists before G1):
  - `execution_outcomes` (0041) is written by `executive/execution_store.py`;
  - `situation_outcomes` (0194) is written by `reason/situation_outcome_store.record(:56)`.
- **`macv_ledger`** (0012, *"the North Star… the number the customer can verify"*) has **no writer**. Its only code reference is the delete list (memory: the-north-star-ledger-has-no-writer).
- **The brains:**
  - store: `learned_brain_entries` (organization · behavior · adaptive · runtime; **never expert**, `contracts/learning.BrainTarget`);
  - pipeline: `feedback/brain_pipeline.admit_proposals(:69)` counts each proposal as held, refused, unchanged, published or queued for review;
  - gaps: the behaviour and adaptive learning units are stubs (GeniOS-008 L6-2); `feedback/attribution.py` counts misses per layer and changes nothing.
- **Corrections** change the next judgment (STEP-16: F65–F67), per file, and one click is never a pattern (F67).

## 2 · Design

1. **A goal moves only on verified outcomes.** When a situation linked to a goal (G4) reaches
   `verified_complete` (G7), or an execution with `goal_refs` (G8) ends in a verified terminal state, one
   `goal_progress_events` row is appended:
   - goal, situation, execution;
   - the evidence ref;
   - the relation it had (advances / depends_on …);
   - `delta` when the goal's metric can count it (G5), else NULL.

   A `reported_complete` adds nothing.
2. **A goal completes only with a human.** When G5's `measured` share reaches the target, or every
   `depends_on` link is verified, the goal is proposed as complete. The card says *"Goal reached — confirm to
   close it"* (06 §4, "Goal achieved — verify"); the founder confirms through `POST /v1/goals/{id}/status`.
   Code never sets `completed` by itself.
3. **A goal at risk is a judgment, not an alarm.** G5's progress and the goal's deadline are printed in
   block G. The L2 judgment may write a `threatens` impact on the goal's own subject, `goal:<id>`: a new
   **goal subject**, judged when its fingerprint moves (a link added or closed, progress moved, the
   deadline's rung). It makes the **goal-at-risk card** of 06 §4 through the same lanes. 0 calls when
   nothing moved.
4. **Learning candidates, governed.** Each verified outcome files a `LearningObject` through `brain_pipeline`.
   - **Kind:** `goal_outcome` — what move, on which kind of work, led to the verified outcome, in how many days.
   - **Behaviour brain:** only after **≥ 3 independent verified outcomes** of the same kind of work, with no contrary outcome in the window. The repetition, conflict and freshness checks are the pipeline's.
   - **Adaptive brain:** a goal's deadline and priority become an adaptive lease with a TTL equal to the deadline, so the next compile pins it.
   - **Expert brain:** never written. A repeated miss attributed to Plane D becomes a reviewed suggestion for a Git PR (`feedback/publisher`).
5. **`macv_ledger` waits for D4.** G9 writes goal progress, not money value. When Rohit defines what counts as recovered value, its writer reads `goal_progress_events` + `execution_outcomes`.

## 3 · Units

| Unit | File | Change |
|---|---|---|
| G9.1 | `migrations/0255_goal_progress_events.sql` | `goal_progress_events (org_id, event_id, goal_id, situation_id, execution_id, relation, evidence_ref, delta numeric, at, created_at)`, PK `(org_id, event_id)`, unique `(org_id, goal_id, situation_id, evidence_ref)` so a replay adds nothing; an org cascade |
| G9.2 | `context/goal_progress.py` | `record_verified(conn, *, org_id, situation_id, evidence_ref, at) -> int`, called by `context/checkin.write_checkin` on the transition to `verified_complete`, and by the execution store on a verified terminal state |
| G9.3 | `context/goals.py` | `completion_due(goal, progress) -> bool` (pure); the goal subject `goal:<id>` for the L2 pass (`reason/l2/inputs.read_subjects` adds goal subjects whose fingerprint inputs moved) |
| G9.4 | `feedback/goal_learning.py` (new) | `candidates_from_outcomes(conn, org_id, *, since) -> list[LearningObject]`, fed into the existing `admit_proposals` |
| G9.5 | `feedback/units.py` | the behaviour and adaptive learning units that return `[]` today (L6-2) get their first real input: `goal_outcome` |
| G9.6 | `packs/brains/adaptive_lease.py` | a goal's deadline and priority as an adaptive lease |
| G9.7 | `contracts/goal.py`, `context/goal_progress.py` | the `verified_outcomes` metric (deferred from G5), and the verified count in `counted`, both reading `goal_progress_events` |

## 4 · LLM use

- **None** in recording progress or in learning admission.
- The goal subject's judgment is the existing R-9 pass: 1 call when the goal's inputs moved, 0 otherwise.

## 5 · Tests

**`tests/context/test_goal_progress_events.py`:**
1. `verified_complete` on a linked situation → one event; replaying it adds none;
2. `reported_complete` → none;
3. a delta only when the metric counts it.

**`tests/context/test_goal_completion.py`:** the target reached → proposed, never `completed`, until the founder confirms.

**`tests/feedback/test_goal_learning.py`:**
1. one verified outcome → a candidate held (n < 3), no brain entry;
2. three independent ones → published to `behavior`;
3. a contrary outcome in the window → held;
4. nothing ever targets `expert`.

**Golden — a new case: F71 "Three design partners signed, the goal is reached".** Three partner files are verified in sequence; three progress events; the goal-reached card appears; the founder's confirm closes the goal.

**Mutation proofs:**
- let `reported_complete` record an event → test 2 fails;
- let the target close the goal by itself → the completion test fails;
- publish at n = 1 → learning test 1 fails.

## 6 · Flags, rollback

- **Flags:** `goal_progress`, per tenant.
- **Rollback:** the flag off stops new events and goal subjects. Recorded events stay.

## 7 · Done when

- F71 passes;
- every goal's progress traces to verified evidence;
- no brain entry is published from fewer than three independent outcomes;
- the expert brain is untouched.

## Harsh's checklist — in order

1. **Write F71** ("three design partners signed, the goal is reached") as a golden case and record it (ideal reader). It starts strict-xfail.
2. **Migration** 0255.
3. **Tests first:**
   - `tests/context/test_goal_progress_events.py`, `test_goal_completion.py`;
   - `tests/feedback/test_goal_learning.py`.
4. **`context/goal_progress.record_verified`**, called from `context/checkin.write_checkin` (on the transition to verified) and from the execution store (on a verified terminal state).
5. **`context/goals.completion_due`.** The goal subject in `reason/l2/inputs.read_subjects`, judged only when its inputs moved.
6. **`feedback/goal_learning.py`:**
   - `candidates_from_outcomes` → `brain_pipeline.admit_proposals`;
   - fill the stubbed units in `feedback/units.py`;
   - the adaptive lease in `packs/brains/adaptive_lease.py`.
7. **Flip F71 to pass.** Mutation proofs:
   - a report that credits;
   - a target that closes the goal by itself;
   - publishing at n = 1.
8. **Guards, push, CI, logs.** Switch `goal_progress` on per tenant. Leave `macv_ledger` for D4, and say so in `03-LOG`.

## Brief for a coding agent

Paste `10-AGENT-BRIEFS.md` §1 first, then this.

**Task:** STEP-G9. Credit verified outcomes to goals, propose completion to the founder, judge goals at risk, and feed governed learning.

**Read first:**
- the preamble;
- `STEP-G9-outcomes-move-goals.md`;
- `context/goal_progress.py`, `context/checkin.py`, `context/goals.py`;
- `reason/l2/inputs.py`;
- `feedback/brain_pipeline.py`, `feedback/units.py`;
- `packs/brains/adaptive_lease.py`;
- `contracts/learning.py`.

**You own:**
- `migrations/0255_goal_progress_events.sql`;
- `context/goal_progress.py` (`record_verified`);
- `context/goals.py` (`completion_due`);
- `reason/l2/inputs.py` (the goal subject only);
- `feedback/goal_learning.py`;
- `feedback/units.py` (the stubbed units only);
- `packs/brains/adaptive_lease.py` (the goal lease only);
- F71 and its cassette;
- the tests.

**Do not touch:**
- `macv_ledger`;
- the expert brain;
- governance thresholds other than the ≥ 3 rule written here.

**Acceptance:**
- §5's tests;
- F71;
- three mutation proofs.
