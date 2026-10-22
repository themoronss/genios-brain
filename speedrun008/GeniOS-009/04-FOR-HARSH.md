# 04 · For Harsh

**Written for:** Harsh. Updated with every pushed group: what changed · migrations · switches · commands ·
what you should see · how it goes wrong · how to roll back.

## State on 22 Oct 2026

- **Nothing of GeniOS-009 is built.** This folder is the plan and the measurements.
- Your `harsh/mvp` head `21b7ae10` is fast-forwarded into local `speedrun008` and **not pushed**, because CI
  on it is red:
  - **golden-pg (10):** cassette misses at the expert / r1 sites in F03, F07, F14, F24, F55, F56
    (`test_an_unchanged_sweep_costs_nothing`, `test_a_held_file_asks_once`).
  - **database (9):** `test_a_dark_file_is_a_line` (F30, F55 + a cassette miss);
    `test_the_compiled_lane_skips_an_unchanged_subject` (F13, F29 re-decided on an unchanged sweep);
    `test_the_gate_is_counted` (count mismatch); `test_the_ladder_never_starves_pg` (statement timeout).
  - `8ccf9a08` (18 Oct) was green on all three jobs.
- Who fixes these on which branch is G0.1 in [`02-PLAN.md`](02-PLAN.md) — Rohit's call.

## What each group will need from you (when built)

| Group | Migration | Switch | What you should see |
|---|---|---|---|
| G1 | `0250_company_goals` (`company_goals`, `company_goal_revisions`) | none (data only) | the golden tenant shows 5 active goals in `GET /v1/goals`; a new stage line `l3.goals_sync` per sweep |
| G2–G5 | `0251_goal_situation_links` | rides `l2_reasoning` (shadow) | block G on L2 prompts; `reasoning_results` rows carry `goal_impacts`; links written on ADMIT. **Every L2 cassette re-recorded (ideal reader, no spend)** |
| G6 | `0252_card_goals` (`cards.goal_refs`, `goal_line`) | `goal_board`, per tenant, never on by default | `GET /v1/insights?group=goal`; "Not linked to a goal" counted; monitor cards read as waits |
| G7 | `0253_situation_checkin` (`context_situations.resolution_state`, `done_when`, `checkin_at`, `checkin_why`) | `checkin_states` | `situation.checkin` card events; "unknown" when a mailbox was not read through, never "overdue" |
| G8 | `0254_decision_requests` | `human_decides` | `GET /v1/decisions?state=open`; for that tenant `plan_commitments` plans nothing |
| G9 | `0255_goal_progress_events` | `goal_progress` | progress moves only on verified outcomes; "Goal reached — confirm" cards |

**Rollback for every group:** the switch off. All migrations are additive (`if not exists`), so the previous
image runs unchanged against them.

**Numbering:** take the next free migration number at build time, after checking `harsh/mvp`. That is the
0191 → 0212 lesson.
