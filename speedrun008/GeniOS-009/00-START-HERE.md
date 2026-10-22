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

**Status, 22 Oct 2026: PLAN + MEASUREMENTS. Nothing built.** Rohit opens each group.

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

**Migrations, in build order.** Each number is the next free one at build time; check `origin/harsh/mvp` first.

| Migration | Group |
|---|---|
| `0250_company_goals` | G1 |
| `0251_goal_situation_links` | G4 |
| `0252_card_goals` | G6 |
| `0253_situation_checkin` | G7 |
| `0254_decision_requests` | G8 |
| `0255_goal_progress_events` | G9 |

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
| G0 | CI green · `l2_cards` on one tenant · admission gates one type · decisions | all | **open — CI red on `21b7ae10`** | Rohit decides who fixes; Claude/Harsh |
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
3. **Nothing goes on a red head.** G0.1 first.
