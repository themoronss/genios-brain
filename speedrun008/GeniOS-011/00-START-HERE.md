# GeniOS-011 · Make it work — every open step, failure and mistake, and the build

**Written for:** Rohit, Harsh and every coding agent.

On 23 Oct 2026 Rohit asked for the whole picture:
- everything still open;
- every failure;
- every place a mistake was made;
- expected versus what comes out wrong today.

He then asked for all of it to be built, the best way, with agents in parallel. This folder is that picture and the plan, and it records the build as it happens.

## How it was measured

- **The code** is the production head `0cc8d83c`: `origin/harsh/mvp`, CI green on 22 Oct. It is read in its own worktree (`.claude/worktrees/g011`, branch `g011`).
- **The team:**
  - nine auditors, one per slice: L1, L2, L3, L4–L6, Goals, Surfaces, Process, Mistakes, open decisions/findings;
  - one skeptic per slice, who tried to refute every item against the code;
  - a completeness critic;
  - a planner.
- **Result: 255 items survived.**
  - 177 were confirmed as written;
  - 68 were confirmed with a correction;
  - 6 cannot be checked without production;
  - 4 were added by the critic;
  - 1 was refuted and dropped.
  - Another 149 items that older docs list as open were checked and found **already closed**.
- ⚠ **Production was not read.** Production reads need Rohit's permission. Every question only production can answer carries its read-only SQL in [04-FOR-HARSH](04-FOR-HARSH.md).

| Severity | Items | | Status | Items |
|---|---|---|---|---|
| **P0** (breaks or starves the cards now) | 19 | | missing | 78 |
| **P1** (wrong or degraded output) | 126 | | partial | 56 |
| **P2** (polish, hygiene) | 110 | | broken | 46 |
| | | | built, not live | 14 |
| | | | switched off / shadow | 7 |
| | | | unknown until production is read | 18 |
| | | | done, lesson only (mistakes) | 36 |

## The short answers to Rohit's questions

### Why are there fewer cards?

Production must decide which of these it is. S01's readings answer it.

1. **The whole chain may not be running for his org.**
   - Since `7075014c` (4 Oct), the scheduled sweep skips L1 → L5 for an org whose trial lapsed, and the warm lane refuses its events.
   - That commit measured his grace as closed on 21 Sep. Nothing extends it.
   - If so, only a manual **Sync now** makes cards. That fits "fewer, and sometimes".
   - [`cross-billing-gates-silently-stop-the-org`](05-EXPECTED-VS-ACTUAL.md#cross-billing-gates-silently-stop-the-org)
2. **A judgment makes no card unless L3 already filed a situation on the file, in an activated domain.**
   - The `general` fallback domain is decided in shadow only.
   - [`l2-l3-binding-no-situation-no-card`](05-EXPECTED-VS-ACTUAL.md#l2-l3-binding-no-situation-no-card)
3. **The formula lanes spend the shared 7-a-day signal cap before the judged files are decided.**
   - A refused, truncated, over-budget or held judgment is handed back to the formula lanes.
   - Each of these skips is visible only in a server log line.
4. **The switches that arm the expert and the L2 path are all off by default.** `expert_review`, `l2_reasoning`, `l2_cards` and the Founder Office domain are all default off, and their state in production is unknown.
5. **Some cards were removed on purpose:**
   - a resolved card no longer comes back;
   - a conditional promise gets no due date;
   - L2 holds a move it says is not one to make yet.
6. **Some cards never reach where Rohit looks:**
   - question and team cards reach only the Cards page;
   - meeting follow-up cards fail every card door (404);
   - a quiet investor file with no reply pattern is never looked at again.

### Why do the cards read weird?

- **A held card prints a fixed engineer sentence instead of the advice.** Example: *"We held the one we found: a fact your move rests on quotes nothing from the mail it cites"*.
  - Source: `reason/expert/verify.py:787-793` + `claim_check.HELD_BECAUSE`.
  - Nothing tries one repair first.
  - The fixes that cut Haiku's held share from 79% to 18.5% (STEP-13b) sit on an unmerged branch.
- **There is no card writer.** C1–C8 are unbuilt.
  - The subject is the expert's move cut at 60 characters.
  - A "Needs a decision —" prefix leaves 41 characters for the body.
  - The expert's "if you act now" never reaches the card.
- **A card's "why" comes from a hub node,** so it repeats across cards.
  - Quotes are often a bare name.
  - Confidence is still the old `{C, I, U}`.

### Why do L2 and L3 keep failing each other?

- **L3 creates situations before any reasoning.** Nine writers do it. Reasoning then runs over those rows.
  - "L2 proposes, L3 admits" (GeniOS-008) runs in shadow and gates nothing.
  - Admission can see only situations anchored on the file's own node. Every *reading* situation (awaiting reply, overdue promise, meeting, document…) is anchored elsewhere and is invisible to it.
- **One counterparty usually holds several live situations:** one per keyword domain and one per 45-day generation. So the L2 judgment holds, and the file falls back to the old lane.
- **Correlation fails silently in five places, so L2 has nothing to reason on:**
  - archived and noise mail is never filed;
  - a reply inherits a reading's synthetic correlation;
  - an unfiled bundle is judged as a context-free seed;
  - a two-file bundle is judged under the first file only;
  - correlations whose anchor vanished are dropped.
- **A history rebuild deletes situations and re-mints random ids.**
- **L1 has no word for the founder's work.** The 16-type vocabulary has no type for an intro, a meeting, a fundraise or an application, so that work never triggers the L2 pass. The fetchers that would answer L2's "I need more evidence" are not armed.

### Why does no card carry a goal, and why did "Antler Singapore admission" never become one?

- Goals are only free-text brief lines.
- No table, card column or model output carries a goal.
- The only automatic proposer is the weekly brief drafter. It reads memory *patterns*, never the graph's situations.
- GeniOS-009's plan kept that as the only source. So even after G1–G9, a workstream could not become a goal on its own: a plan gap, recorded in [01](01-WHAT-WENT-WRONG.md).
- The fix:
  - **S26** amends the plan: L2 proposes a goal from what is in motion, L3 admits it as a proposal, and Rohit approves in one click.
  - **S27.U1**, being built now, is the interim: the drafter sees the files in motion and proposes their goal lines, and they appear on the Goals page to accept.
  - **S28–S31** then build G1 → G6, so the goal reaches every card.

### Why did this keep happening?

[01-WHAT-WENT-WRONG](01-WHAT-WENT-WRONG.md) has the ledger: 61 mistakes, each with evidence and a rule. The three biggest:
- **We proved the plumbing and called it intelligence.** Every test used the ideal reader, and the real model was measured once.
- **Production changed in one jump while CI was red, and nobody measured it after.**
- **The plans had holes exactly where Rohit looks:** goals, and founder playbooks gated on a review nobody did.

## Read in this order

| # | File | What it holds |
|---|---|---|
| 00 | this file | the answers, the numbers, what is being built, what Rohit and Harsh must do |
| 07 | [07-LOOPHOLES](07-LOOPHOLES.md) | **the shortest read:** 23 loopholes that stop the website making the cards of Rohit's local ideal dashboard, each with evidence, effect, fix and owner |
| 05 | [05-EXPECTED-VS-ACTUAL](05-EXPECTED-VS-ACTUAL.md) | 170 open items by layer, P0 first: expected (with its source), actual (with evidence), what Rohit sees, fix, owner, step |
| 01 | [01-WHAT-WENT-WRONG](01-WHAT-WENT-WRONG.md) | the patterns, 61 mistakes with evidence and the rule each one teaches, and the mistakes inside other items |
| 02 | [02-PLAN](02-PLAN.md) | 43 steps / ~140 units in order, the critical path, files, done-when, owner, dependencies |
| 06 | [06-DECISIONS](06-DECISIONS.md) | 33 decisions for Rohit, each with today's truth and the recommended default |
| 04 | [04-FOR-HARSH](04-FOR-HARSH.md) | production facts, actions, and the read-only SQL for every production question |
| 03 | [03-LOG](03-LOG.md) | append-only: what was built, by whom, verified how |
| data | [data/audit-2026-10-23.json](data/audit-2026-10-23.json) | every verified item as data (addresses and the org id redacted) |

## Status, 23 Oct evening

- **On `origin/speedrun008`:** 19 units are built, independently verified (tests re-run, one mutation per unit red, then restored) and merged. Every unit, what it changes and how to deploy it is in [04-FOR-HARSH](04-FOR-HARSH.md) §1.
- **Held on purpose:** S02.U5 and S16.U3 (04 §3).
- **Building:** S34.U3 (the card writer), S09.U1 (the history window) and S44.U1 (the ideal-card scorecard).
- **Running record:** [03-LOG](03-LOG.md).

## What was built first (wave 1, 23 Oct)

Eleven units that need no production access, no money and no decision. Each is built in its own worktree off the production head. An independent verifier then re-runs its tests and its mutation proof, and there is one fix round. Results land in [03-LOG](03-LOG.md).

| Unit | What it makes true |
|---|---|
| S01.U1 | One read-only runner holds every production question. It refuses anything but SELECT and writes one JSON of readings. |
| S03.U1 | `/health` names the build SHA and the schema head, so "what is deployed" is never a guess again. |
| S04.U1 | CI guards: situation writers may only shrink, and model calls stay in their layer. |
| S06.U1 | L1: a junk verdict stands. An archived newsletter is re-judged, never re-admitted on its snippet. |
| S07.U1 | The real-model harness asks R-9 on its production model, with a 2-call probe before any pass. |
| S14.U1 | L3: a reply stays in its conversation's file, and the "filed" count is true. |
| S18.U1 | L2: judged files are decided before the formula spends the day's cap, and every no-card reason is counted. |
| S18.U2 | L2: the expert still reviews when the L2 path cannot, and one oversized file no longer stops the pass. |
| S27.U1 | Goals, interim: the drafter sees what is in motion and proposes its goal lines (the Antler case). |
| S36.U1 | L5: meeting follow-up cards open instead of 404. |
| S26.U2 | GeniOS-009 docs tell the truth (G0.1 done, migration numbers, Goals page merged). |

## What only Rohit and Harsh can do (the first five)

1. **Rohit:** permission for the read-only production SQL, or run it yourself (S01.U2).
2. **Harsh:**
   - the deployed SHA and date;
   - whether migrations 0191–0250 are applied;
   - whether Rohit's org is expired. If it is, put it on a non-expiring internal plan (S01.U3, S02.U1).
3. **Rohit and Harsh:** branch protection on the prod branch, and deploy only green SHAs (S03.U2).
4. **Rohit:** the live key and a spend cap for one real-model pass on the production models (S07.U2).
5. **Rohit:** the goal decision. Recommended: L2 proposes one goal per workstream, and you approve in one click (S26.U1). A skipped decision takes its default.

⚠ **The repository is public.** It carries Rohit's address, the production org id and real counterparties' names. Making it private is his call ([06](06-DECISIONS.md#process-repo-is-public-with-real-data)). This folder redacts the address and the org id.
