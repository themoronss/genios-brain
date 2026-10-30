# P4 · Plane R · 05 · How it will be done at production level

**Owner:** Harsh and the agents Harsh assigns, for the code. Rohit, or a reviewer Rohit names, for the reasoning units (D-P4-13). Rohit approves each tenant's switch.
**Rule:** each step first passes in the notebook ([04](04-WHAT-NEEDS-TO-BE-DONE-NOW.md)). The full specification is [07](07-THE-PLANE-R-SPEC.md).

---

## 1 · One reasoning path

Today three things decide cards for this tenant: the L2 judge (33 cards), the compiled lane (36) and the legacy pack lane (41), the last two decided by a test-mode model outside the register. The target is **one judge**, the L2 run of 07 §2, judging **pages** (P2) with **packages** (P3) and the **library** (07 §1).

| Module | Today | Target |
|---|---|---|
| `reason/l2/sweep.py` | The pass (`l2_pass`, called from `reason/runner.py` `run_all`): subjects, gate, judge, store, admission, file reviews | The sweep (at most 10 subjects) calling `run_subject`, steps 1–12 of 07 §2, per page, goal, placement batch, analyse window or draft, woken by P1; writes batched in one transaction per sweep, one savepoint per subject (07 §2.7) |
| `reason/l2/plan.py` | Depth from literals | Replaced: the need classification and plan (07 §2.2–2.3), with `_reasoning/need.yaml` |
| `reason/l2/tools.py` | Six tools, UTC | The gateway of 07 §3 (`reason/l2/tools/`), one module per tool group, each pure |
| `reason/l2/prompt.py`, `reason/expert/prompt.py` | Hand-written rules and checklists | One generator (`reason/l2/prompts.py`) that renders the library's fragments per task (07 §13) |
| `reason/l2/dossier.py`, `reason/expert/dossier.py` | Seven blocks; the file dossier embedded | P2's snapshot blocks (P2 §12.1) plus block T (tools) and block X (the package and the units) |
| `reason/l2/judge.py` | One call through the R-9 gate, the checks | Kept: the call, the parse, the claim check; plus the RC checks and the repair rule (07 §6) |
| `contracts/reasoning_result.py` | Model-written confidence; `lane_for` on the model's words | Confidence by calculators; `lane_for` on computed inputs; the fourteen outcomes; `kinds`; `unit_id` per line (07 §5) |
| `reason/l2/evidence.py` | Needs raised, never met | Needs with sources from the package; the stored-event fetcher first; one re-entry (07 §8) |
| `reason/l2/replay.py` | No caller | Nightly and on every check change (07 §16) |
| `reason/l2/goals.py` (new) | — | Goal proposals and the goal judge (07 §9) |
| `reason/l2/place.py` (new) | — | The placement call (07 §10) |
| `reason/l2/rules/` (new) | — | The deterministic units `u.*` (07 §11), on `reason/unit.py`'s template |
| `reason/l2/checks.py` (new) | — | The thirty-three RC checks (07 §6.2), each with its test and mutation proof |
| `reason/l2/result.py` (new) | — | The outcome, the lane, the confidence, `blocked_by`, `why_not` and the hand-off, by code (07 §5, §7) |
| `reason/l2/analyse.py` (new) | — | The weekly pass and company patterns (07 §12) |
| `Domain Expertise/_reasoning/` (new) | — | The fifteen units and the data files of 07 §1.8 |

**What retires, per tenant, at the parity gate** (P4-17; GeniOS-008 L2-D1, H1, H2, H3, L2-12): the expert pass's own call (R-7) and decide path; the 23 units' scores (their checks stay); the test-mode decision maker and its R-1; `context/lifecycle/resolution.py`'s model call; the legacy pack lane. **The formula never takes the decision** (Rohit, 5 Oct): the judge replaces the decision maker.

## 2 · The reasoning library

- **Where:** `Domain Expertise/_reasoning/`: one YAML per unit, `laws.yaml`, `precedence.yaml`, `need.yaml`, `groups.yaml`, `directory.yaml`, `moves.yaml`, `hard_constraints.yaml`, `admissions/`, and `_schema/r_unit.schema.json`.
- **Built** by P3's one build (P3 07 §3.1) into the same index (`plane = R`), into prompt fragments and into an in-memory registry, built once per deploy and keyed by the library hash. No reasoning path reads the YAML raw (RG-26).
- **Reviewed** with P3's sitting tool; one act approves and switches a unit on (D-P4-13). An unreviewed unit runs in shadow only.
- **Changed** only by the path of 07 §1.7, with its cases and a shadow run; versions are semver; receipts record them.

## 3 · Prompts are generated, never hand-written

`reason/l2/prompts.py` builds each task's prompt (07 §13): the role and the question, the laws, the precedence, the selected units' sections, the package through P3's bridge, the tools' block, the snapshot's blocks, the answer contract. The stable part comes first and is sent as a cached prefix. **A CI test (RG-1) fails any prompt module that holds method or rule text not rendered from the library.**

## 4 · The answer's shape and the API's limits

- Every task's answer contract is the union of its selected units' outputs; the judge's no longer carries confidence or the draft (07 §13.3).
- Citable ids are an enum of the printed catalogue where the API compiles it, else a pattern. This removes most of today's holds (52 of 66).
- **Every contract is probed against the API's compiled-grammar limit in CI** (RG-6). A failed probe costs nothing; a passing one, under a cent. A contract that does not compile fails the build, not a tenant's sweep (the notebook's 12 of 12 refusals on 29 Oct).

## 5 · Checks run before anything reaches the door

- The claim check (check v8) stays, pointed at the page; the thirty-three RC checks are added (07 §6.2), each with its test and mutation proof.
- A failing line is held or downgraded alone, with its RC id; the door (P2 §11) ledgers it. The rest of the result stands.
- **A held line never reaches a founder as text** (RG-19). Today 15 of 24 question cards carry "We held the one we found: …".

## 6 · Calculators, confidence and the lane

- The gateway is pure: no clock, database or network (RG-4, checked on the syntax tree). It reads the frozen snapshot and `eval_time`.
- Every instant is printed in the company's time beside UTC (RG-18). This is P1's relief R3 in the product.
- The six confidence calculators run after validation; the situation's confidence is the weakest; the lane comes from `lane_for` on computed inputs (07 §7), and **the card takes that lane** (P5-1), not the old `output_lane.route`.

## 7 · Goals, placement, deterministic units, the weekly pass

- **Goals** (`reason/l2/goals.py`): proposals in each onboarding wave and weekly; one goal judgment when a goal's linked set moves; health and progress by rule in code (07 §9).
- **Placement** (`reason/l2/place.py`): after P2's continuation; batched by party (07 §10).
- **Deterministic units** (`reason/l2/rules/`): `u.wave`, `u.one_number`, `u.delivery_failure`, `u.done_when_met`, `u.expectation_missed`, `u.next_check`, `u.stop_rule`, `u.routine_move`, `u.founder_question`, `u.transition` (07 §11), each with 0 calls.
- **The weekly pass** (`reason/l2/analyse.py`): over pages, on the batch API, under $1 a week per tenant; company patterns computed by code and written through admission (07 §12).

## 8 · Model policy

- **One row per tenant per site** (`reasoning_site_policy`), for the closed list of seven reasoning sites (07 §14): model, thinking and its budget, output ceiling, timeout, fallback model, budgets per call and per day, and an optional per-depth override. A new tenant gets the defaults from policy rows; nothing is set by hand.
- **The default is production parity** (D-P1-4): claude-sonnet-5, thinking off. A stronger or cheaper model for a site only after it holds the acceptance set, with its cost measured and written in 08-LOG. The result must hold on the default; a stronger model is used only where the stakes need it.
- **Every reasoning call goes through the register** (`reason/bundle/sites.py`) and its gate (RG-7). Today about 16 call families bypass it; the test-mode decision maker and R-1 (3,695 Haiku calls in the week, no dollar cap) are registered with a cap until they retire.

## 9 · Cost

| Item | Today | Target |
|---|---|---|
| The judge's spend that buys no stored result | 39% ($5.28 of $13.55 in the week) | under 10% (P4-13; P1 R5) |
| Runs refused for dossier size | 31 in the week, all one file, every day | 0: the page plus only what is new (P2); an oversize subject split or summarised by code |
| Test-mode decision calls | 3,695 in the week, about $12 | 0 after the parity gate |
| L3's resolution calls | 1,961 in the week, about $5 | 0: moved into L2 |
| A day with nothing new | the judge still runs on every bundle | 0 calls |
| Evolve per tenant per day | about $5.70 for the whole product | under $0.50 (P1) |
| Maintain per tenant per week | — | under $1 (P1) |

## 10 · Rollout, shadow and rollback

- **The notebook first,** then the product: every step proves itself on the local copy against the acceptance set (09 rule 6).
- **In the product, per tenant and per situation type,** behind an activation row: the new run in shadow beside today's (it writes receipts and pages, no cards), compared on the acceptance set, switched one situation type at a time at P1's parity gate. **The first switch is awaiting-reply and outreach** (the investor, introduction and incubator cases; GeniOS-008 L2-I2), for this tenant only, with a day's watch.
- **A new unit, law, precedence or prompt template** runs in shadow on the acceptance set and its cases before it goes live; a pointer per tenant records the library hash; rollback moves the pointer back, logged.
- **Rollback of the switch** is the activation row: flipping it back restores the old lanes the same day.

## 11 · Monitoring

**Per unit, per week, per tenant** (`r_unit_stats`): selected; skipped by reason; used; checks failed by RC id; abstained; the founder's verdicts on the cards that rested on it; outcomes when its advice was followed; predictions due and how many came true.

**Per task, per day:** runs by trigger; outcomes; lanes; depth; calls per run; tokens; cost; repairs; second passes; truncations; refusals for budget or size; lines held by check; waste share; the card's lane against L2's lane.

**The ten measures of the L2 plan,** each on the golden set: evidence grounding, contradiction handling, unknowns calibrated, situation quality, decision usefulness, over-escalation and misses, retrieval efficiency, replayability, outcome quality, and latency and cost. **The Atlas's benchmark** (the five prompts on the six-part rubric, blind-scored with a planted answer key) is re-run once before anyone says GeniOS beats a plain LLM.

The daily health report (P1 §5) carries the judge's line and the top unit failures.

## 12 · Failure modes

| Failure | What happens |
|---|---|
| A model timeout or error | The previous page stands; a receipt; P4's ladder retries once on a narrower packet and the policy's fallback model (07 §15); P1 adds no attempt, parks the subject, and the daily health report counts it (P1 07 §9.6) |
| A malformed or truncated answer | One repair with only the failing part; a truncation adjusts the subject's budget instead of retrying the same request |
| The snapshot moved during the run | The door's compare-and-set refuses; a "stale read" receipt; P1 re-queues |
| A unit's required input missing | The unit is skipped with `dependency_not_scheduled` (or `no_input`); the result says what was not checked |
| No knowledge for the kind of work | Coverage `none`: an investigation or an observation, no recommendation, the gap logged |
| Budget spent | `incomplete`, with its open needs; the subject carried in priority order |
| A deploy mid-run | The run writes nothing; it is idempotent and re-runs from its request |

## 13 · What must never happen

- **Method or rule text in a prompt** that is not rendered from the library.
- **A number or date on a page** with no tool or quote behind it.
- **A rule used where its own conditions fail**, or a stage reading of their silence when the move is ours.
- **"Unknown" written as zero**, or an absence claimed over a source not fully read.
- **Confidence, a rank, a recipient or a permission** produced by the model.
- **A held line's text** shown to a founder.
- **The formula deciding** in place of the judge.
- **A unit changed** without review, cases and a shadow run.
- **A company pattern** crossing tenants, or adapting knowledge on fewer than 5 independent instances.
- **A contract shipped** without its grammar probe.
