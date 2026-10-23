# GeniOS-009 · Goals, check-ins and outcomes — start here

**Written for:** Rohit, Harsh and every coding agent.

**What GeniOS-009 is.** GeniOS-008 rebuilds the engine to Design Atlas v2 (L1 → L6). GeniOS-009 adds what
Rohit's *Goal Achievement Loop* document ([`source/`](source/GeniOS-Goal-Achievement-Loop-Chat.md)) asks
for on top of it:
- **departmental goals** as real objects;
- business situations **linked to the goals they move**;
- **check-ins** that tell "verified" from "reported" and "unknown" from "overdue";
- delegation through a human decision;
- **outcomes that move goals**.

GeniOS-008 stays the architecture. GeniOS-009 never contradicts it.

**Status, 23 Oct 2026: G0.1 done (CI green). G0.2–G0.4 open. G1–G9 are PLAN + MEASUREMENTS, nothing built.**
Rohit opens each group. The step table below has the evidence.

## Harsh — start here

Read [`09-HARSH-HANDOVER.md`](09-HARSH-HANDOVER.md) first. It covers:
- what this is and why;
- the order, and why that order;
- the rules;
- every command;
- how to report a step done.

Use [`11-GLOSSARY.md`](11-GLOSSARY.md) for any term. To hand a step to a coding agent, paste
[`10-AGENT-BRIEFS.md`](10-AGENT-BRIEFS.md) §1, then the step's own **"Brief for a coding agent"**.

**Every `STEP-Gn` file opens with an "At a glance" table:**
- what;
- why;
- for what;
- how;
- what changes after;
- done when;
- do not.

**It ends with "Harsh's checklist" and "Brief for a coding agent".**

## Read in this order

| # | File | What it answers |
|---|---|---|
| 1 | [`05-THE-SOURCE.md`](05-THE-SOURCE.md) | What the document asks; what is already ours; the 8 new requirements; what we reject |
| 2 | [`01-AS-IS-CARDS.md`](01-AS-IS-CARDS.md) | Every card the engine produces **today**, measured on the 67-case golden set, both paths |
| 3 | [`06-CARDS-TARGET.md`](06-CARDS-TARGET.md) | How the cards look, behave and are organised **after** — real cards with the new parts marked |
| 4 | [`07-LOOPS.md`](07-LOOPS.md) | The business situation, the goals, and the reasoning, context and learning loops, mapped to the code |
| 5 | [`02-PLAN.md`](02-PLAN.md) | G0–G9: what, where, why, how verified, in what order |
| 6 | [`08-DECISIONS.md`](08-DECISIONS.md) | D1–D8, each with a default |
| 7 | `STEP-G0` … `STEP-G9` (below) | **The build spec, one file per group:**<ul><li>what is true in the code, with file:line;</li><li>the design and why that way;</li><li>every unit with its file and function;</li><li>contracts and migrations written out;</li><li>where the model is used, and what it costs;</li><li>tests, golden cases and mutation proofs;</li><li>flags, rollback, and "done when".</li></ul> |
| 8 | [`03-LOG.md`](03-LOG.md) | Every step, append-only |
| 9 | [`04-FOR-HARSH.md`](04-FOR-HARSH.md) | Flags, migrations, commands, rollback per group |
| 10 | [`09-HARSH-HANDOVER.md`](09-HARSH-HANDOVER.md) | **Harsh's entry point**: what, why, order, rules, commands, how to report done, who decides |
| 11 | [`10-AGENT-BRIEFS.md`](10-AGENT-BRIEFS.md) | The common preamble for a coding agent; how to split a step; how to check returned work |
| 12 | [`11-GLOSSARY.md`](11-GLOSSARY.md) | Every term, one line each |

## The build spec, one file per group

| Group | File |
|---|---|
| G0 | [`STEP-G0-the-ground.md`](STEP-G0-the-ground.md) |
| G1 | [`STEP-G1-the-goal-object.md`](STEP-G1-the-goal-object.md) |
| G2 | [`STEP-G2-goals-in-the-snapshot.md`](STEP-G2-goals-in-the-snapshot.md) |
| G3 | [`STEP-G3-goal-impact-in-the-judgment.md`](STEP-G3-goal-impact-in-the-judgment.md) |
| G4 | [`STEP-G4-goal-situation-links.md`](STEP-G4-goal-situation-links.md) |
| G5 | [`STEP-G5-goal-progress.md`](STEP-G5-goal-progress.md) |
| G6 | [`STEP-G6-the-goal-on-the-card.md`](STEP-G6-the-goal-on-the-card.md) |
| G7 | [`STEP-G7-check-in-states.md`](STEP-G7-check-in-states.md) |
| G8 | [`STEP-G8-a-human-decides-then-delegation.md`](STEP-G8-a-human-decides-then-delegation.md) |
| G9 | [`STEP-G9-outcomes-move-goals.md`](STEP-G9-outcomes-move-goals.md) |

**Migrations, in build order.** None has a number yet. Each takes the **next free number at build time (≥0251)**.
- `0250` is taken: `migrations/0250_screen_followup_read_path.sql` (GeniOS-010 B8, `93ea3cbe`) is on `harsh/mvp` and `speedrun008`.
- `0250` is also used on local-only branches: `0250_expert_review_attempts.sql` (STEP-13b, `054b6abf`) sits on `yc2w27-s13b` and four other local branches.
- So check every branch, local ones too, just before you name the file:

```sh
git fetch origin
git for-each-ref --format='%(refname:short)' refs/heads refs/remotes/origin \
  | while read b; do git ls-tree --name-only "$b" migrations/; done \
  | grep -oE '^migrations/[0-9]{4}' | sort -u | tail -1
```

It prints the highest number taken on any branch (`migrations/0250` on 23 Oct). Take the next one. That is the
0191 → 0212 lesson.

| Order | Migration | Group |
|---|---|---|
| 1 | `<next free ≥0251>_company_goals` | G1 |
| 2 | `<next free>_goal_situation_links` | G4 |
| 3 | `<next free>_card_goals` | G6 |
| 4 | `<next free>_situation_checkin` | G7 |
| 5 | `<next free>_decision_requests` | G8 |
| 6 | `<next free>_goal_progress_events` | G9 |

**Per-tenant switches**, none on by default:

| Switch | Group |
|---|---|
| `goal_board` | G6 |
| `checkin_states` | G7 |
| `human_decides` | G8 |
| `goal_progress` | G9 |

G1–G5 ride `l2_reasoning` (shadow).

**New golden cases:**

| Case | What it tests | Group |
|---|---|---|
| F68 | reported, not verified | G7 |
| F69 | unknown, not overdue | G7 |
| F70 | verified by the signed document | G7 |
| F71 | goal reached | G9 |

The goal labels for the existing cases are proposed in `STEP-G3` §3.3, to be confirmed in the label sheet.

## The step table

| Group | What | Layer | Status | Owner |
|---|---|---|---|---|
| G0 | CI green · `l2_cards` on one tenant · admission gates one type · decisions | all | **open** — G0.1 done; G0.2–G0.4 open | — |
| G0.1 | CI green | all | **done** — fixes `3d5a6a3d`, `8d1de446`, `269400dc` (22 Oct; `03-LOG` G0.1 row). CI run `39796159785` on `harsh/mvp` `0cc8d83c` is green on golden-pg, database and test | Harsh, with Claude |
| G0.2 | `l2_cards` on for one tenant | L2 | **open** — `l2_cards` is off by default (`platform/l4_activation.py:118-122`); F15 is still `blocked_on` 03 F169 / 06 D57 (`tests/replays/specs/founder/F15.json`) | Rohit names the tenant (D6); Claude/Harsh |
| G0.3 | admission decides that a situation exists, one type first | L3 | **open** — `context/l2_admission.py:25`: "SHADOW: nothing here touches `context_situations`" | Claude/Harsh |
| G0.4 | decisions D1–D8 | — | **open** — every decision in `08-DECISIONS.md` still stands on its default | Rohit |
| G1 | goal object (from accepted brief lines; inferred goals wait for approval) | L3 + L0 | planned | — |
| G2 | goals in the L2 snapshot; a goal change re-reasons its linked subjects | L3 → L2 | planned | — |
| G3 | `goal_impacts` in the L2 judgment, claim-checked | L2 | planned | — |
| G4 | goal ↔ situation links written on ADMIT | L3 | planned | — |
| G5 | goal progress tool (measured or "unknown") | L2 tools | planned | — |
| G6 | goal line on the card; board grouped by goal | L5 | planned | — |
| G7 | check-in states on the situation; definition of done; coverage-aware | L3/L4/L5 | planned | — |
| G8 | L4 reads the DecisionObject; a human decides; agents via approval | L4 | planned | — |
| G9 | verified outcomes move goals; governed learning | L6 | planned | — |

## Three things to know before anything else

1. **The cards are already good.** On the golden set the engine already makes one living card per
   situation, in the gold shape, claim-checked (`01` §2). GeniOS-009 adds the *goal* and the *check-in*
   to that card. It does not rebuild the card.
2. **The expert already thinks in goals, in words.** Today's F02 card ends *"…and mark the brief's
   StartupSetu recognition goal as met"*. The idea is in the prompt, but there is no goal object to
   mark. That is G1.
3. **Nothing goes on a red head.** G0.1 made the head green on 22 Oct. Read the CI run of the head you build on.
4. **Two goal-shaped tables already exist. Neither is the goal object, and neither links to a situation.**
   - `team_milestones` (migration 0151, "a dated goal with an owner seat") is read only by the team readiness
     pass and its API (`reason/team/readiness.py:77`, `GET/POST /v1/team/milestones`).
   - `seat_objectives` (migration 0133) is one person's focus domain; it only reorders that person's card queue
     (`deliver/store.py:988`).
   - `STEP-G1` §1 has the details. G1 does not touch either table.
