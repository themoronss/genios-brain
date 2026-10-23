# 04 · For Harsh

**Written for:** Harsh. Updated with every pushed group: what changed · migrations · switches · commands ·
what you should see · how it goes wrong · how to roll back.

## State on 23 Oct 2026

- **G0.1 is done.** The red on `21b7ae10` (golden-pg 10, database 9) had three causes. You fixed all three on
  22 Oct; the attribution is the G0.1 row in [`03-LOG.md`](03-LOG.md):
  - `3d5a6a3d`: every connection cuts the day in UTC; six cassettes re-recorded;
  - `8d1de446`: an instant at the evaluation time has happened, so no subject is re-decided on an unchanged sweep;
  - `269400dc`: the re-read ladder counts a message's parks once.
- **They are pushed.** `origin/harsh/mvp` is `0cc8d83c`, and `origin/speedrun008` contains it. CI run
  `39796159785` on `0cc8d83c` is green on all three jobs (golden-pg, database, test).
- **G0.2–G0.4 are open:** `l2_cards` on for one tenant, admission gating one type, and Rohit's decisions.
- **Nothing of G1–G9 is built.** There is no `contracts/goal.py`, `context/goals.py` or `api/goal_routes.py`.
  `company_goals`, `goal_refs`, `goal_impacts` and `/v1/goals` appear nowhere in `genios_engine/` or `migrations/`.
- **Two goal-shaped tables already exist.** Neither is the goal object, and G1 does not touch them:
  - `team_milestones` (0151): a dated milestone with an owner seat, for the team readiness pass;
  - `seat_objectives` (0133): one person's focus domain, which reorders that person's card queue.

  `STEP-G1` §1 has the details.

## What each group will need from you (when built)

| Group | Migration | Switch | What you should see |
|---|---|---|---|
| G1 | `<next free ≥0251>_company_goals` (`company_goals`, `company_goal_revisions`) | none (data only) | the golden tenant shows 5 active goals in `GET /v1/goals`; a new stage line `l3.goals_sync` per sweep |
| G2–G5 | `<next free>_goal_situation_links` | rides `l2_reasoning` (shadow) | block G on L2 prompts; `reasoning_results` rows carry `goal_impacts`; links written on ADMIT. **Every L2 cassette re-recorded (ideal reader, no spend)** |
| G6 | `<next free>_card_goals` (`cards.goal_refs`, `goal_line`) | `goal_board`, per tenant, never on by default | `GET /v1/insights?group=goal`; "Not linked to a goal" counted; monitor cards read as waits |
| G7 | `<next free>_situation_checkin` (`context_situations.resolution_state`, `done_when`, `checkin_at`, `checkin_why`) | `checkin_states` | `situation.checkin` card events; "unknown" when a mailbox was not read through, never "overdue" |
| G8 | `<next free>_decision_requests` | `human_decides` | `GET /v1/decisions?state=open`; for that tenant `plan_commitments` plans nothing |
| G9 | `<next free>_goal_progress_events` | `goal_progress` | progress moves only on verified outcomes; "Goal reached — confirm" cards |

**Rollback for every group:** the switch off. All migrations are additive (`if not exists`), so the previous
image runs unchanged against them.

**Numbering:** no planned migration has a number yet. Take the **next free number at build time (≥0251)**.
That is the 0191 → 0212 lesson.
- `0250` is taken by `migrations/0250_screen_followup_read_path.sql` (GeniOS-010 B8, `93ea3cbe`).
- Local-only branches also use `0250` (`0250_expert_review_attempts.sql`, STEP-13b `054b6abf`, on
  `yc2w27-s13b` and four others).

Check every branch, local ones too, just before you name the file:

```sh
git fetch origin
git for-each-ref --format='%(refname:short)' refs/heads refs/remotes/origin \
  | while read b; do git ls-tree --name-only "$b" migrations/; done \
  | grep -oE '^migrations/[0-9]{4}' | sort -u | tail -1
```

It prints the highest number taken (`migrations/0250` on 23 Oct). Take the next one.
