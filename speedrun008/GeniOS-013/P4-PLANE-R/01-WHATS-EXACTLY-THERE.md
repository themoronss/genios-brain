# P4 · Plane R (reasoning) · 01 · What's exactly there

**What this file answers:** what exists today for how GeniOS thinks, in the product and in the notebook, measured, with file paths. [02](02-WHATS-FAILING-AND-WHY.md) says what fails and why; [07](07-THE-PLANE-R-SPEC.md) is the target.

**The part:** how a professional *thinks*:
- the model as the expert, reasoning over the page, the knowledge and the company's own patterns;
- the ways of thinking it must apply (the reasoning units), with their conditions;
- the calculators that do the arithmetic it must not guess;
- the order of judging, and what wins when two things disagree;
- the checks on what it claims, the confidence, the outcome and the lane;
- reasoning about goals and across situations, and learning from what happened.

Plane R never stores and never renders: P2 keeps, P5 shows.

**Read at:** product code `a729b968` (29 Oct). **Measured on:** the local copy of the design partner's org, cut from production on 28 Oct at 12:45 UTC. Production restarted this org on 21 Oct, so 22–28 Oct is a real first week. Every number below has its query in the measurement notes (private; no names).

---

## 1 · Plane R's functions, one by one

**Key:** ✅ built and on the card path · 🟡 partly, or built and not yet reached · ⬜ built, no caller · ❌ missing.

| Function (Atlas) | In the product | State | Measured in the first week |
|---|---|---|---|
| **A library of reasoning units** (versioned thinking contracts in six groups; fourteen composites in V1) | None. 23 deterministic units in four categories (`reason/reasoners/`); the six groups exist only as checklist steps inside a prompt. The one authored hook, `domain.yaml` `reasoning:`, is used by no domain | ❌ | — |
| **The judge** (one bounded pass per situation) | The L2 pass (`reason/l2/`, GeniOS-008, 18 Oct), reusing the expert pass's prompt, schema, dossier and check | ✅ live for this tenant (`l2_cards` on since 21 Oct) | 138 runs, 86 results, 50 file reviews written, 33 cards |
| **Intake, idempotency, the material-change gate** | Request id hashed; a fingerprint row per subject answers repeats with no call | ✅ | All 138 runs carry trigger `bundle` |
| **Classify the need; compile the plan** | `reason/l2/plan.py`: depth from literals (deep, standard, shallow) | 🟡 | 0 shallow; 69 of 71 deep runs deep because of an L1 conflict; `max_calls` never read |
| **Calculators** (tools before the pass) | `reason/l2/tools.py`: six tools | 🟡 | UTC only; the company's time zone is never read |
| **Precedence** | In prompt rules: "the playbook is a prior …"; the founder's correction is followed or answered | 🟡 | 0 founder corrections in the week |
| **Claims checked** | The claim check, `reason/expert/verify.py` (check v8, 40 closed reasons) on every result | ✅ | 66 of 86 results held |
| **Confidence vector** | Six levels **written by the model**; the card's own confidence is a count of cited mails | 🟡 | "coverage low" in 73 of 86, measured by nothing |
| **Outcome and lane** | `lane_for` by code from the model's words; the card's lane from the old `output_lane.route` | 🟡 | The two agree on 16 of 33 cards |
| **Evidence needs** | Raised by L2; L1's fetchers off by default | 🟡 | 115 raised, 0 met |
| **Second pass** | None (one repair of a malformed answer) | ❌ | Never 3 calls; 27 runs used 2 |
| **Write-back** | `context/l2_admission.py` in shadow: no applier, no compare-and-set | ⬜ | 33 admission rows, 30 interpretations; nothing reads them |
| **Receipts and replay** | A receipt on every row; `reason/l2/replay.py` replays with no model | ⬜ | Replay has no caller outside tests |
| **Goal reasoning** | Per-file goal impacts and at most one goal proposal in the L2 answer | 🟡 | Impacts on 14 of 86 results, a proposal on 6; no goal judged as a goal |
| **Across situations** | None in reasoning | ❌ | — |
| **Company patterns** (`packs/brains/`) | Built and scheduled weekly; not printed to the judge | ⬜ | 0 learned entries |
| **Learning** (`feedback/`) | Calibration in shadow; attribution to six old layers; no prediction store | 🟡 | 3 verdicts, 0 resolved cards |
| **Model sites and policy** | The register `reason/bundle/sites.py` (11 ids); no per-tenant row | 🟡 | About 16 call families bypass it |

## 2 · What made the 111 cards of the first week

| Path | What it is | Model | Runs | Cards | What decides |
|---|---|---|---|---|---|
| **The L2 judge** (site R-9) | One judgment per file or thread; an admitted result becomes the file's review (`expert_reviews`) and decides its card | claude-sonnet-5, thinking off | 138 (86 results) | **33**: 24 question cards, 9 decisions | The model's review, held to the claim check |
| **The compiled lane** | Admin's compiled situations, the 23 units on the 18-unit roster (`roster_v2`) | the **test-mode LLM decision maker** (Haiku), outside the register | 43 | **36** | The decision maker sees the units' reason codes, never their scores |
| **The legacy pack lane** | The general pack's rules (`commitment_overdue`, `unanswered_email`) | the same test-mode decision maker | 60 | **41** | The same; 17 runs deferred on its daily cap |
| **The expert pass** (site R-7) | STEP-12's own call | — | **0 calls** | — | L2 judges every moved file instead |
| **A native sales lane** | Deal cooling | — | 0 (shadow) | — | — |
| **Other** | One conflict card with no run | — | — | 1 | — |

So **77 of 111 cards** came through the unit lanes, and the model that decided them is not the judge but a Haiku-class decision maker in test mode, with no dollar cap.

## 3 · The L2 judge, step by step

Against the Atlas's twelve steps (Atlas L2 · O):

| # | Step | Today | Gap |
|---|---|---|---|
| 1 | Intake and idempotency | `L2Request` with a closed list of seven triggers; the request id is a hash; repeats answered by the fingerprint row | Only `bundle` ever fired (138 of 138); `owner_change`, `outcome`, `human_ask` have no producer |
| 2 | Material-change gate | A fingerprint of the signals, the file's inputs, settled needs, the nearest-due rung, open conflicts and versions | No pack version, tenant revision or accepted claims in it |
| 3 | Bounded snapshot | `read_snapshot`: 2 hops, 40 nodes, the revision recorded | `as_of` not passed; the file dossier is read outside it |
| 4 | Expertise | None: block D is the STEP-12 file dossier or the company brief | 0 of 138 runs with a package (P3) |
| 5 | Classify the need | `compile_plan`: depth from literals (importance ≥ 7,000 bp, due within 48 h, conflicts) | No stage, evidence, time or stakes dimension |
| 6 | The plan | Six group names, run or answered briefly; every field asked at every depth | No units to select; no exclusions; no budget but the site's |
| 7 | Tools | Six: `newest_signal_age`, `whose_turn` (L1's ball-in-court), `nearest_due`, `unanswered_inbound`, `days_quiet`, `amounts`, each printed as `tool:<name>` | UTC only; 30 minutes past due prints "1 hours ago"; no lead times, baselines or working days |
| 8 | The pass | One call: role, the dossier (seven blocks, A–G), "this run", 24 rules, a 20-step checklist, the merged answer schema; one repair | The stable text comes after the dossier and no cache prefix is passed |
| 9 | Validate | Printed ids, shape, the STEP-13 claim check per line, numbers against the dossier | Confidence not computed; no time or authority check beyond "a move dated before the run" and "a decision with no owner" |
| 10 | Lane and needs | `lane_for` (conflict → the model's mode → a floor on the model's levels); up to 2 needs per run | The lane's inputs are the model's words |
| 11 | Write-back | `l2_admissions` (ADMIT/HOLD/REJECT per situation) in shadow | No applier, no compare-and-set |
| 12 | Receipt, hand-off | A receipt per row; the file's review row feeds the card | No scheduling; replay unused |

**What it costs:** output p50 6,789 tokens (p90 9,700), input p50 11,864 (p90 20,608), $0.09 a result at the median. Its own budget of $2.00 a day and $0.25 a call **bound on every day**: 95 judgments skipped for budget, $1.88–1.96 spent a day. **39% of its spend ($5.28 of $13.55) bought no stored result:** 30 calls failed validation (27 malformed after the repair) and 6 were cut at the 12,000-token ceiling. Another 31 runs were refused before any call because their dossiers were 245,000–280,000 characters.

## 4 · The claim check

`reason/expert/verify.py` with `contracts/claim_check.py`, check v8: about 1,460 lines, 40 closed reasons, four verdicts (kept, corrected, dropped, noted) and four fates (shown, held, suppressed, refused). It is the strongest piece of Plane R that exists. It checks every fact's ids and quotes, every name and number on its lines, the card's words, the recipient, whether an ask was already answered, the founder's corrections, and (for L2) an open conflict, a missing decider, a past move date and weak ground.

- **It held 66 of 86 results** (57 of 63 under the first L2 prompt with check v4; 9 of 23 under prompt v7 with check v8).
- **52 of the 66 were "cites something the file does not show":** the model cited block letters and section names (`F` 47 times, `C` 31, `D` 21, `B` 19, "WHAT WAS CHECKED" 13), not the printed ids.
- **A held result reaches the founder as a question.** 31 of the 40 founder questions read "What is the next step with … ? We held the one we found: …". 24 of the 33 L2 cards are question cards.

## 5 · The 23 units and the compiled lane

- **23 registered:** 17 core in four categories (situation understanding: context, timeline, dependency, constraint; business evaluation: risk, opportunity, impact, priority, confidence; optimisation: trade-off, resource, scheduling, cost, policy; decision support: alternative, validation, recommendation) and 6 supplementary (legacy rule, legacy score gate, temporal, relationship, signal composition, planning). Only the 17 use the eight-stage template (`reason/unit.py`); "evaluate() cannot be overridden" is a docstring, not enforced.
- **They are pure:** no clock, database or network.
- **The roster** (`adapters/expertise.py`, 20 entries) declared 18 of 20 units on all 43 compiled runs (policy and relationship declined), not the Atlas's 15 of 20.
- **Risk is still half-blind:** relationship unmeasured on 43 of 43 risk results, momentum on 12; risk at its 1,000 bp floor on 34. Nothing pulls a unit's sources into the plan.
- **Many outputs are constants:** impact empty on 43 of 43; recommendation "0 supported plays" on 43 of 43; validation `safe_bp` 4,000 on 43 of 43; confidence 6,250 on 36 of 43.
- **Their scores decide nothing here:** every compiled and legacy candidate (242 of 242) was decided by the test-mode LLM decision maker, which is shown the units' reason codes only. What still binds is the units' checks: 12 tenant-policy eliminations by the constraint unit, and the legacy score gate.
- **The model paths:** the expert path imports one unit (`ConstraintReasoner`), and runs it after the model; the L2 judge imports none.
- `reason/critique.py` is not a second reasoning pass: it scores an outside agent's proposed action against a stored run.

## 6 · Model sites

| Site | What | Model | Calls in the week | Note |
|---|---|---|---|---|
| R-9 | The L2 judge | claude-sonnet-5 | 122 run (86 results) + 95 skipped for budget | Its own $2/day |
| R-2 | The decision narrative | claude-sonnet-5 | 96 (56 refused, 49 for a bare digit) | Shared narrative budget |
| R-7 | The expert pass | claude-sonnet-5 | 0 | L2 judges instead |
| R-1, R-3, R-4, R-10 | Interpreter, alternatives, effect, card writer | — | 0 | R-5 has no caller; R-6 retired |
| Test-mode decision maker | Decides compiled and legacy candidates | Haiku 4.5 | 2,045 | Outside the register; an in-process limit of 400 a day (723 calls with R-1 on 22 Oct); about $9.50 |
| Test-mode R-1 | Reads hedged sentences for the decision maker | Haiku 4.5 | 1,650 | Outside the register; about $2.40 |
| `l2:resolution` | Decides whether a situation is resolved, inside L3 | Haiku 4.5 | 1,961 | Outside the register; about $5.30 |

The whole week's model spend across 13 purposes was about $65; reading new mail at capture is the largest share (L1's extraction, about $19). No per-tenant model or thinking row exists; tiers, ceilings and thinking are constants in `reason/bundle/sites.py`.

## 7 · Company patterns and learning

- **Company patterns** (`packs/brains/`): behaviour distillation, adaptive leases and organisation discovery are built and run weekly on the 6-hour tick. They produced **0 learned entries**: 140 trend facts, none rising or falling; 3 card verdicts in the week, all "do it myself"; no rule-bearing document uploaded. Their thresholds are the tenant's learning policy (3 observations, 2 days, 3 entities). **Neither model path prints a learned brain.**
- **"Yours" in the dossier** comes from `context/kind_numbers` (days between the reviews that first named one stage and the next), and appears in 0 of 50 dossiers: no file had a kind of work, so no playbook and no stage. `reason/expert/stage_dwell.py` has no caller.
- **Calibration** (`feedback/calibrate.py`) runs weekly in shadow (7 runs) and scores only legacy pack rules: 0 for Admin and the Founder Office, whose cards carry no rule any manifest holds.
- **Attribution** (`feedback/attribution.py`) maps 11 reasons to six old layers and changes nothing by design; a scorecard reads it.
- **Predictions:** none stored. `macv_ledger` has no writer. No card was resolved in the week.

## 8 · In the notebook (`b2`, as of 23 Oct 07:10 IST)

The notebook's whole Plane R is one hand-written prompt plus code admission.

| Piece | File | What it holds |
|---|---|---|
| The judge | `nb/judge.py` (system prompt) | **A nine-step order of judging:** who is involved and what each is to us, then what the work is and its stage → the loops (questions, requests, promises), each settled only by a later mail from the side that owes it → claims, word for word → whose move it is → what should happen next and by when → the status → the frame, summary, importance and goal links → **is the founder needed now** → members out, evidence, unknowns. **Five "chief of staff" rules** as bullets under "apply it; the playbook, when printed, is more specific" (the follow-up after a call is ours, due within a week; a question is answered only by what was asked; three unanswered messages are a decision; a renewal within 7 days is the founder's decision; ask rather than assume). None has a condition, none is cited, none is checked by code |
| The page's shape | `nb/contracts.py` (`JUDGE_SCHEMA`) | The fields in judging order. The first full schema was refused 12 of 12 times ("The compiled grammar is too large"); confidence, links, per-loop reasons and the metric list were cut. Confidence is null on 380 of 380 pages |
| Relating everything | `nb/relate.py` | **One** model call over 296 pieces of work (not 421): 15 goals, 8 links, 1 merge, 5 notes, $0.17. Code finds two things on its own: numbers told two ways to different people (1 work) and mail that never arrived (5 bounce notices) |
| The checks | `nb/checks.py` | P2's admission, change by change, each held change with its reason: 115 held over all runs, 87 on the saved pages. 20 of the 87 are the model citing a meeting where a mail was required |
| The playbook | `nb/common.py` | Printed whole for every page of its kind, not selected; each stage's "quiet means" cut to 260 characters, each move to its first step |
| Model | `nb/llm.py` | claude-sonnet-5, thinking off; $20 cap across builds ($9.24 spent) |
| Calculators | — | **None shown to the model.** It reads UTC timestamps with no weekday and works out time, turns and gaps itself. Code computes overdue, "within 7 days" and whose move only **after** the answer, and whose move only as a note (27 pages disagree; none corrected) |
| Company patterns, confidence, goal judgment, a pass across pages | — | None |

**Measured on `b2`:** 423 pieces of work (127 noise); 380 judged pages; 401 judge calls ($6.37); $8.41 for the build; 42 live pages say the founder is needed; 63 open cards (40 because the page says so, 19 because a date passed, 4 within a week; 37 of the 63 rest on a date more than 30 days old).

**The pages contradict themselves, and nothing checks it:** 31 pieces of work hold an open loop we owe while their status is done, dropped or noise; 53 done or dropped pages say the move is ours; 89 of 123 "waiting on us" pages say the founder is not needed. A date labelled "stated" is never checked against a mail: 29 pages carry one, and in `b3` it appears in none of the thread's mails.

**What it does well, and Plane R keeps:** the order of judging that ends in "is the founder needed now?"; admission change by change with the reason kept; absence as a finding when the mail was read; code that finds what no thread shows (numbers told two ways, bounces).

## 9 · The ideal's reasoning against today's, card by card

The cards whose fix [10](../10-ACCEPTANCE.md) gives to P4, traced in the notebook (`b2`) to the reasoning step that failed. Ids only.

| Card | The reasoning the ideal shows | What happened in `b2` | The Plane R cause |
|---|---|---|---|
| `f1` | The review is today at 11:30 company time; join early, lead with one number | Right on two versions; the re-judge after relate asked "did you attend?" | No local time; two clocks (calendar 05:00 UTC, the mail's 11:30) with no tool to reconcile them; the page's own earlier line fed back as fact |
| `b3` | The ball is in their court: let it close | "You owe them times", under a date labelled "stated" that no mail holds | No whose-turn from the last ask and answer; a "stated" date never checked; the investor playbook printed for a peer introduction (P2, P3) |
| `i2` | They asked for current traction and got a projection: answer in three lines | The loop closed as "answered"; "usually a soft no" | No check that a reply answers the ask; the playbook "more specific" than the rules |
| `i3` | The follow-up after the call is ours: send it today | "Their move"; the "soft no" rule | The precedence line; the playbook's first-call condition cut at 260 characters; two stages' notes blended |
| `b2` | Two partner calls, no written next step: send the collaboration note | Loop opened and the move set to us, but the status left "done" and the founder "not needed" | Status and whose move written by the model and never checked against the loops |
| `c2` | Renews within the week: keep or downgrade, ask for credits | Filed as noise | A page made before the renewal rule existed, never re-judged because "noise" was skipped even when forced; no "days until" |
| `i1` | The incubator's milestone is the new, checkable fact: one update, then stop | "Stop, wait for the next intake" | A generic stage prior beat the accelerator's written offer; the incubator's review never reached this page; no goal judgment |
| `f3` | A promised referral silent 24 days against the platform's same-day pace: ask | Missed | A pile of 30 threads (P2's grouping); no elapsed-time tool; no goal judgment |
| `i4` | Of 12 recipients with no reply in 10 weeks, which still matter | One card, the numbers conflict | One card and one lane per page; no reasoning over the recipients |
| `i5` | Mail that bounced was never received: resend to working addresses | One of five bounces carded | One next step per page; nothing ranks the five |

And in the live product the same cards show the product's own failures: `i1`'s right reading was held by the checker, `i2` and `b3` were never judged, `i3` was held, `c2` was read and nothing recognised (10 §1).

## 10 · What exists but does not fit

| Exists | Why it does not fit as it is | What happens to it |
|---|---|---|
| The 23 units | Scorers with sales-shaped roles; their scores decide nothing; many outputs constant | Arithmetic to tools, checks kept, scores retired at the parity gate (07 §3.3) |
| The six group names in `reason/l2/plan.py` | Only a prompt note; every field asked at every depth | Become the units' groups (07 §1.2) |
| The six confidence levels | Written by the model, measured by nothing | Computed by calculators (07 §7.1) |
| `lane_for` | Code, but on the model's words; the card uses another lane | Kept, on computed inputs; the card takes it (07 §7.3) |
| The claim check | Right, and strong; but its holds turn into founder questions in the checker's words | Kept; printed ids only; no held text to the founder (07 §6.1) |
| The expert checklist (10 steps) and the L2 steps (10 more) | The right order, as untestable prompt text | Become the units' questions (07 §1.4) |
| `context/kind_numbers` ("yours") | Only when reviews name a stage, which never happened | Replaced by company patterns from the pages (07 §12.3) |
| `reason/expert/stage_dwell.py` | No caller | Becomes `t.days_in_stage` |
| `reason/critique.py` | Scores an outside agent's proposal; not a second reasoning pass | Kept as the agents' seam; the second pass is new (07 §2.5) |
| `reason/simulation.what_if_nothing` | Live: what 3, 7 and 14 days of nothing do | Kept, as `s.what_if_nothing` (07 §3.2) |
| `foresight`, `simulation.simulate` | Not on any path this tenant uses | Left; a calculator only if a unit needs it |
| `packs/brains/` producers | Computed from slow metrics; produced nothing | Company patterns from the pages (07 §12.3) |
| Calibration | Shadow; cannot see the judge's cards | Stays shadow; per-unit measurement for Plane R (07 §17.4) |
| Attribution | Maps to six old layers; changes nothing | Maps to the layer and the unit (07 §17.2) |
| `reason/l2/replay.py` | No caller | Nightly and on every check change (07 §16) |
| L1's need fetchers | Off | The stored-event fetcher first; L1's armed once verified (07 §8) |
| `context/l2_admission.py` | Shadow; no applier | Replaced by P2's door |
