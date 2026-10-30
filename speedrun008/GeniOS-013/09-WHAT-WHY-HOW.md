# 09 · What we are building, why, and how: read this before any part

**Written for:** everyone who builds GeniOS: Rohit, Harsh, and every coding agent.
**Date:** 29 Oct 2026.
**Purpose:** everyone builds the same thing for the same reason, so a step can't be "done" while it moves away from what GeniOS is meant to be.
**Sources:**
- Rohit's launch film (26 Oct; its subtitles are quoted below);
- Rohit's own words in GeniOS-009/010/012;
- the ideal dashboard;
- the measurements in [01](01-WHAT-IS-HAPPENING.md) and in the notebook build `b2` ([10](10-ACCEPTANCE.md)).

**No names:** this repo is public, so cases are referred to by their ids in the private ideal file (`i1`, `p1` …).

---

## 1 · What GeniOS is

From the film, in Rohit's words.

**The problem a manager has:**
- "Every department has its goals and its team, but delegating the right task and keeping track of it, as a manager, is a very time-consuming process. And most of the time, results are far from what was projected."
- Claude skills and LLMs "are good for individual goals". But they break "when the data of multiple tools and departmental goals keep evolving".
- Agents "can do great things, but only for a defined state of context".

**What is missing:** "something that guides me in everything: every department, every departmental goal, every situation, exactly as my company's data evolves, without hundreds of prompts". In other words, "a 24/7 consultant for our company, which says: do this instead of that, to make this happen and get that projected goal."

**What GeniOS does:**
- It "lives in your gadget, reads your data with your permission, and reasons over it with the GeniOS Engine".
- It gives "all possible intelligence to make you and your team reach your departmental goals … all proactively".
- You are "not checking dashboards, not tagging anything, and not prompting more and more".
- You delegate what it says "to people or an agent", and you "approve before anything is sent".
- "Your data stays with you only."

**What is inside the engine:** "company patterns, domain expertise, reasoning patterns, and the current status of your company, how your company is evolving, which right now is only in your head". It shows "multidimensional patterns" that one person cannot see.

**The four kinds of intelligence:** reactive, proactive, predictive, prescriptive. Each says what to do, and why.

**"Every Done teaches."** The system learns from what was done.

## 2 · The test GeniOS must pass first: the film's own example (`i1`)

**What happened (in the founder's own words in the film):**
- An accelerator rejected the application.
- The founder asked them to reconsider, and they said "resend it and keep us posted".
- Several follow-ups went out.
- Then "priorities changed, and I actually forgot about them".

**What GeniOS should say** (the goal page shown in the film):
- **Goal:** get the accelerator to reconsider. Status: at risk. Found in your mail.
- **Intelligence on this goal:** *"Send one update with a new, checkable fact, then stop until they answer."*
- **Why:** they left the door open in writing; three updates in 20 days got no reply, so the next one must carry a new fact (that day's incubator milestone), not a restatement.
- **Then:** delegate it to a person or an agent, and approve the draft before it is sent.

**Where we are today:**

| | What it said about `i1` |
|---|---|
| Live product | Found the right reading, but the checker **held** it, and an old rule card said "you are 71 days late" |
| Notebook `b2` | The **opposite** call: "stop, wait for the next intake". It never connected the incubator milestone to this goal |

Whatever we build is measured first on this one example, then on the whole acceptance set in [10](10-ACCEPTANCE.md).

## 3 · How GeniOS is built: five parts

The film's engine words map onto five parts with hard boundaries. Each part has its own folder below, with the same five files.

| # | Part | The film's words | What it owns | What it never does |
|---|---|---|---|---|
| **P1** | [Orchestrator](P1-ORCHESTRATOR/) | "proactively", "as your data evolves" | What runs, when, for which situation, in what order, at what cost. The four loops, the triggers, the clock, the budget | Judge, or store a conclusion |
| **P2** | [Notebook](P2-NOTEBOOK/) (Context Graph, L3) | "the current status of your company" | The evidence (every tool, every decision) and the conclusions: who we are, who is who, the business situations, goals, promises, claims, links. Also the code check that runs before anything is kept | Decide what to conclude |
| **P3** | [Plane D](P3-PLANE-D/) | "domain expertise" | What a professional knows, per department and kind of work: playbooks, rules of thumb with their conditions, stages, typical durations. Also how this reaches the model | Reason |
| **P4** | [Plane R](P4-PLANE-R/) | "reasoning patterns", "company patterns", "multidimensional patterns" | How a professional thinks: the model as the expert, written reasoning patterns, calculators, the order of judging, what wins in a conflict, citations, and the patterns learned from this company | Store, or render |
| **P5** | [Cards](P5-CARDS/) | "intelligence", "what to do, and why", "delegate" | When intelligence is raised, what it says, which goal it moves, how it is ranked, versioned and closed, and what you can do with it (Done, Delegate, Later, Feedback, Answer) | Judge the situation behind it |

The four loops run across all five parts. Each loop's chain is its trigger, and the parts involved follow it.

| Loop | Chain | Parts |
|---|---|---|
| **Onboard** | a new customer's data → Notebook → business situations → goals (proposed) → you confirm → intelligence for each goal step | P1, P2, P3, P4, P5 |
| **Evolve** | new data → questioned through the open situations and goals → Notebook updated → situation updated → goal updated → intelligence updated or closed | P1, P2, P3 (the knowledge selected for each situation and goal), P4, P5 |
| **Act** | intelligence → your decision, or a person or agent you delegate to → a verified outcome → Notebook → goal progress | P1, P2, P3 (what proves "done"; feedback on the knowledge), P4 (the outcome checked against its done-when; predictions scored; "wrong because …" sent to the reasoning unit it blames), P5 |
| **Maintain** | daily or weekly over the whole Notebook: correlate, analyse (mistakes, patterns, progress, performance), lifecycle (decay, ignore, prioritise, refresh) → situations and goals updated → fewer, sharper cards | P1, P2, P3 (usage per unit, gaps, review dates, new packs in shadow), P4, P5 |

## 4 · Why it hasn't worked so far: eight causes

Each cause is measured. Each is fixed by a named part.

| # | Cause | Evidence | Fixed in |
|---|---|---|---|
| 1 | **Conclusions are never saved.** Every judgment starts from zero and re-reads about 70,000 characters | 0 of the 16,792 facts in the graph came from the brain; admission runs in shadow | P2 |
| 2 | **The wrong unit of work.** Mail is grouped by sender, not by the business situation | One application sits in 2 files; one intro platform is a single file of 500 mails | P2 |
| 3 | **The knowledge exists but doesn't reach the model** | Admin's approved expertise for renewals and for meeting follow-ups is never shown to the model paths. Founder Office playbooks lose their conditions on the way. The notebook printed only step 1 of each playbook | P3 |
| 4 | **Rules live in prompts, not in the planes** | Three different prompt copies: the expert path, the L2 path and the notebook. A rule written there can't be tested and drifts | P4 |
| 5 | **No goal layer** | 7 goals proposed and 0 approved; 0 cards linked to a goal. The notebook's goals have no target, plan or progress | P2, P4, P5 |
| 6 | **No clock and no single orchestrator** | 138 of 138 brain runs were started by new mail, yet 13 of the 20 ideal cards are about something that did *not* happen. Three card makers run in one sweep | P1 |
| 7 | **The expertise was never reviewed** | The Founder Office domain is `draft`, `unreviewed`, written by AI; 22 situations corpus-wide are still `draft` | P3 |
| 8 | **Intelligence isn't raised, ranked or closed by the reasoning** | The live product makes one card per signal from six writers (111 in a week; one counterparty on 25 to 31 of them), shows the checker's text on 13, and expires every open card within a week; 0 cards carry a goal or close on proof. In the notebook, 23 of 63 cards come from dates alone and 53 answer no ideal card | P5 |

None of these is a misunderstanding on Rohit's part. Causes 1, 2, 4 and 6 are architecture and process (built by us, the AI sessions, step by step without retiring the old path). Causes 3 and 8 are code. Causes 5 and 7 are unfinished work.

## 5 · How we avoid repeating them: ten rules every step follows

1. **One source of truth per rule.** A rule of thumb lives in Plane D or Plane R as a written, versioned item with its conditions, never in prompt text.
2. **The model judges; code remembers, calculates and checks.** No score decides on its own. The model never invents a number, an id or a quote (Rohit, 5 Oct).
3. **Nothing is kept unless it is backed.** Every claim cites evidence it was shown, and code checks it before saving. A refused change is held with its reason, never silently dropped.
4. **Unknown is not zero.** An absence counts as a finding only when the source was fully read.
5. **Time is local.** Every instant is shown in the company's own time zone as well as UTC.
6. **Prove it in the notebook first, then port.** No production change before the same step passes on the local copy.
7. **Measure before and after.** Every step runs the acceptance set ([10](10-ACCEPTANCE.md)) before and after, and records the numbers in [08-LOG](08-LOG.md).
8. **Attribute every failure before fixing it.** Name which part and which item failed, and whose it was. Fix it at that source, never by adding a new rule elsewhere.
9. **One writer per file.** A step is not done without its tests, its measurement and Rohit's look at the result.
10. **Words are fixed.** Notebook, business situation, goal, intelligence (card), Plane D, Plane R, orchestrator, loop. When talking about layers, use the product's layer names (L1 Signals … L6 Learning) and the package name beside them.

## 6 · Words

| Word | Meaning |
|---|---|
| **Notebook** | GeniOS's memory of the company: the evidence it read and the conclusions it reached, each conclusion versioned and backed by evidence. The architecture's Context Graph (L3): the Evidence Graph plus the Intelligence Graph |
| **Business situation** | One piece of work in motion: an application, an investor conversation, an introduction, a renewal, a hire. It has a page: where it stands, whose move it is, what is owed, what should happen next and by when |
| **Goal** | An end the company is driving toward over weeks or months. It has a target (what counts, and where it was said), a plan, progress (or "unknown — why"), a status, and a next move. It is proposed by GeniOS and confirmed by the founder |
| **Intelligence** (a card) | What GeniOS says to a person: what to do and why, for which goal, by when, and how we will know it's done. Four kinds: reactive, proactive, predictive, prescriptive |
| **Plane D** | Domain expertise: what a professional knows |
| **Plane R** | Reasoning: how a professional thinks, including the patterns learned from this company |
| **Orchestrator** | What runs when |
| **Loop** | Onboard, Evolve, Act, Maintain |

## 7 · How the part folders are read

Every part folder holds these five files. A part may add more files, but never fewer.

| File | Answers |
|---|---|
| `01-WHATS-EXACTLY-THERE` | What exists today, in the product and in the notebook, with file paths and measured numbers |
| `02-WHATS-FAILING-AND-WHY` | Each failure, its evidence, its cause, and whose it was |
| `03-EXPECTED-VS-HAPPENING` | What Rohit expects (the film, Rohit's own words, the ideal) beside what happens today |
| `04-WHAT-NEEDS-TO-BE-DONE-NOW` | The decisions for Rohit and the step-wise plan, proved in the notebook first, each step with its test and done-when |
| `05-HOW-AT-PRODUCTION-LEVEL` | How the same thing runs in the product: modules, tables, activation, rollout, cost, monitoring, rollback, owner |

**Order:**
1. Plan **P1 → P2 → P3 → P4 → P5**.
2. Re-check P1, because it wires the other four together.
3. Draw one combined build order.
4. Build step by step, with a written update after each step.

Nothing is built until Rohit approves the plan.
