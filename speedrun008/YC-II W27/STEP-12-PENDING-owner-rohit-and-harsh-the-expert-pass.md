# STEP-12 · PENDING — owner Rohit (the live pass, D50: a key and a yes; D48, D57, D58) and Harsh (deploy, migrations `0197`–`0199`; `expert_review` for Rohit's org only, after the live pass) · the expert pass — one strong judgment per file, only when it changed — M32 and M33 built (§9)

**Owner:** Claude. **Depends on:** `STEP-02` (fingerprint), `STEP-07` (brief), `STEP-09` (files),
`STEP-10` (numbers); `STEP-11` makes it better but is not a precondition (D3). **Decisions:** `06`
D1 (does the judgment decide what matters), D7 (model and cap). **Moves:** golden must-detect
**≥ 90%**, must-abstain **≥ 95%**, forbidden outputs **0**; the per-sweep decider retired for every
file the expert covers.

This is the step `05-HOW-THE-EXPERT-THINKS.md` describes. Read that first.

---

## 1 · What is true now

| | Evidence |
|---|---|
| The current decider calls itself a chief of staff — and is given almost nothing | `[CODE]` `reason/llm_decision_maker.py:479-593`: one situation, the latest **4** messages' summaries, ≤ 40 rule facts, ≤ 25 neighbour facts, the formula's baseline; **no company, no prior decisions or cards or feedback, no history beyond four messages, no timeline**. It is asked for a score per play (`:581-635`); its rationale and *missing* list are written and **read by nothing**; `output_lane` is left NULL |
| The context reasoner built for this never ran | `[CODE]` `reason/situation_reasoner.py` (R-6) behind `RSiteGate`, persisting to `situation_interpretations` (`context/interpretation_store.py:30-59`); `[PROD]` 1,839 rows, **0 with a proposal** — its L4 feature is not default-on (`platform/intelligence_onboarding.py:163-167`) and the table has no reader |
| The prose that exists never reaches the card | `[CODE]` the R-2 narrator (`reason/bundle/sweep.py:47-196`, Sonnet 5, $2/day) writes to `l4_reasoning_bundles`, read only by an API feed |
| The machinery to do this right exists | `[CODE]` the R-site runner `reason/llm_sites.run_site` (`:314-377`) with `RSiteGate` and a durable `PostgresSiteCache` (`:194-245`); the closed site list `reason/bundle/sites.py:20-56`; the replay-safe injection R-1 uses (`reason/llm_interpretation.py:250-269`, `reason/adapters/native.py:289-301`) → `reasoning_context_payloads` (`reason/store.py:688-700`) → `replay_persisted` (`reason/replay.py:145-201`) — **a decision recomputed without calling the model** |
| The seam | `[CODE]` inside `shadow_compile`, right after `build_context_slice` and the package compile (`reason/domain_shadow.py:1059-1068`) — where R-6 already sits (`:1072-1124`) |
| What a card needs to exist | `[CODE]` a full audited L4 run (`reason/authority.py:15-42, 119-265`) through `reason_native_capability` → `persist_execution` (`reason/audit.py:254-286`) → `_emit_capability_signal` (`reason/domain_shadow.py:233-408`) |

## 2 · Why

This is the one thing you asked for: GeniOS thinking about your company like a 30-year expert.
Everything before this step makes the thinking possible; everything after it makes it safe to show.

## 3 · How

| # | Unit | Where | What |
|---|---|---|---|
| 3.1 | the dossier | new `reason/expert/dossier.py` | for one file: the brief (`STEP-07`) · the timeline with evidence ids (`STEP-10` 3.1, via `context/bounded_read.py`, whose only caller today is a health check) · open asks and roles (`STEP-09`) · the numbers with provenance (`STEP-10`) · the playbook, accepted or labelled draft (`STEP-11`) · prior judgments and what came of them (`situation_interpretations`, `card_events`, verdicts, `derived.history.*`) · the coverage receipt · a what-if from `reason/simulation.py`. Bounded; truncation reported, never silent |
| 3.2 | the thinking checklist | new `reason/expert/checklist.py` | Plane R's Groups 1–4 compiled into the prompt's sections, in order: establish what is true → frame, and the rival frames → expected vs actual (from the playbook) → patterns and counter-patterns, with their provenance → the unknowns that would change the answer → **scenarios**: do nothing · act now · best · worst · signals to watch → appraisal of stakes, urgency and reversibility, each with its reasons → mode of intervention → best next move, an alternative, a wait-or-stop rule, *done when* → the draft |
| 3.3 | the call | a new site `SITE_EXPERT_REVIEW` in `reason/bundle/sites.py`; run through `llm_sites.run_site` + `RSiteGate` + `PostgresSiteCache` keyed on `STEP-02`'s fingerprint | D7: Sonnet-class by default, Opus-class for high-stakes files; a per-org daily dollar cap — the decider and R-1 have **none** today. A new L4 feature, `expert_review`, armed per tenant. Truncation detected via `stop_reason` (`2caf88aa`) |
| 3.4 | the output contract | new `contracts/expert_review.py` | the Atlas's `reasoning_result` shape (L2·O): `facts[{claim, evidence}]` · `inferences[{claim, based_on}]` · `hypotheses[{proposition, needs}]` · `unknowns[{question, relevance}]` · `frames{primary, rivals}` · `expected_vs_actual` · `scenarios{do_nothing, act, best, worst, signals_to_watch}` · `appraisal{stakes, urgency, reversibility, reasons}` · `mode` · `next_move{who, what, for_whom, by_when}` · `alternative` · `wait_or_stop` · `done_when` · `draft`. Schema-checked; one repair on syntax only, never on substance |
| 3.5 | into the decision, replayably | `reason/adapters/native.py`; `reason/decision_maker.py` | the validated result (after `STEP-13`) is injected into the snapshot as `expert.*` facts with evidence refs **before** execution, exactly as R-1 does. The decision maker reads them deterministically: `mode` → outcome; with D1 = A, `appraisal` → the importance and urgency inputs; the confidence comes from the validated evidence, never from the model. Persisted with the run → **replay recomputes without the model** |
| 3.6 | retire the per-sweep decider | `reason/llm_decision_maker.enabled_for`; `reason/orchestrator.py:252-263` | for a file the expert covers, the old decider and R-1 are not called. Elsewhere they stay behind `STEP-02`'s gate until each lane is covered |
| 3.7 | R-6 and R-2 | `reason/situation_reasoner.py`; `reason/bundle/` | R-6's persistence (`situation_interpretations`) becomes the expert's record — finally with a reader. R-2's prose is superseded by the expert's own explanation |

## 4 · What will happen — Insight Partners, 5 Oct

```
trigger      a meeting with insightpartners.com in 3 days, on a file with no judgment since 27 Sep
gate         fingerprint changed (the 3-days-to-meeting bucket) → one call
dossier      brief v3 · timeline: 27 Sep Neel → you; invite; 8 Oct call · open asks: ___ (from his mail)
             numbers: first contact · your investor reply time ___ (n = ___) · last mail to any investor 26 Aug (40 days)
             playbook (draft): first investor call at pre-seed — traction, team, why now, round; a pre-read helps
expert       frame: first call with a top-tier fund; rival: an exploratory chat with no fund intent
             unknown: does Neel lead deals at your stage?   scenarios: prepared vs unprepared
             appraisal: high stakes, time-bound, reversible  mode: decide
             next move: send a one-page pre-read by 7 Oct; alternative: send it after the call
             done when: the call happens and the agreed next step is logged
check        every claim cites the mail, the invite or a calculator (STEP-13)
lane         Decision (from the mode and the validated evidence)
card         one card, with the pre-read drafted — STEP-14
next sweep   nothing changed → no call (STEP-02)
```

## 5 · Expected

| Measure | Before | After |
|---|---|---|
| Golden must-detect (recorded cassettes) | measured in `STEP-01` | **≥ 90%** |
| Golden must-abstain | measured | **≥ 95%** |
| Forbidden outputs (self as subject, connector as target, invented number, recap of an unconfirmed meeting) | measured | **0** |
| Expert calls a day, this org | — | ~10–30, the files that changed `[MODELLED]` |
| Spend a day | ~$7 today | within D7's cap; ~$2–3 expected `[MODELLED]` |
| Replay of an expert-backed decision | — | identical, **zero** model calls |

## 6 · Verify

```
GENIOS_TEST_DATABASE_URL=… .venv/bin/python -m pytest tests/reason/expert -q
#   the dossier is bounded and reports truncation; the checklist renders every section;
#   a schema-invalid answer is repaired once, a substantive one never; the injected facts make
#   replay_persisted return the same decision with NoLLM
.venv/bin/python -m pytest tests/replays -q                    # recorded cassettes
.venv/bin/python scripts/golden_eval.py --live --model <D7>    # the live scorecard, before any rollout
```

## 7 · Risks

| Risk | Guard |
|---|---|
| A fluent, wrong judgment | `STEP-13` checks every claim and every number before anything is shown |
| Cost runs away | the fingerprint (one call per change), the per-org cap, the overflow queue |
| The model drifts between versions | the cassette suite fails on any prompt change; a model change is a deliberate re-record with the live scorecard attached |
| Rule 02 of the Atlas | D1 — the amendment is explicit, and numbers, permissions and recipients still never come from the model |

---

## 8 · The check of 2026-10-10 — what the 5 Oct plan got right, and wrong

Re-checked claim by claim against `speedrun008` @ `c50f0f7e` by two read-only workers and by hand,
and measured on the golden set from its cassettes (no spend). Since 5 Oct, STEP-02…STEP-11 built most
of what this step's dossier reads — the brief, a file per piece of work, its timeline and numbers with
their n, the change gate, the playbook a file reads. What does not exist is the loop: **nothing in
`reason/` reads a file** (`grep workstream genios_engine/reason/` — 0 hits).

### 8.1 · Measured — the golden set (47 cases, 409 recorded answers)

| | |
|---|---|
| model answers per site | extraction 86 · resolution 71 · **decider 65** (in 24 cases: 39 decision, 26 defer) · relevance 47 · **R-1 42** · junk gate 42 · bundle narrator 29 · card narrator 27 |
| the board | must-detect 13/35 · must-abstain 11/12 · forbidden 4 · Atlas 4/80 |
| the 10 must-detect cases with no card | **7 never reach the decider** — F01, F09, F11, F15, F16, F17, F47 have no decider answer at all; F02 is asked twice and defers twice; F19 and F24 are decided (3 and 2) and carded about someone else |
| the 3 with too many cards | F07 (2), F27 (2), F29 (3) — one ask, several situations, a card each: `STEP-14` |
| the must-abstain failure | F40 — 2 cards about the founder's own sent mail |

**The finding the plan did not have:** the losses sit BEFORE the decider. An expert pass that only
feeds situations which already reach Layer 4 (§3.5) would touch 3 of the 10. The expert has to judge
the FILE, whatever its situations did, and its judgment needs a road of its own to a decision.

### 8.2 · The claims

| # | Claim (§1) | Now | Evidence |
|---|---|---|---|
| 1 | the decider is given almost nothing | **partly** — the brief is in (STEP-07) and v6 quotes ≤6 claims, ≤3 framing blocks, whole steps (STEP-11); still no file, timeline, numbers, prior decisions, cards or feedback, and ≤4 messages inside a 40-line block | `reason/llm_decision_maker.py:552-675` |
| 1b | its rationale and `missing` are read by nothing; `output_lane` NULL | **true** — stored as `llm_*`, read by tests only; the LLM path never routes a lane | `:909-918`, `:923-942`; `reason/decision_maker.py:1195-1211` |
| 2 | R-6 never ran; its table has no reader | **true** — not default-on; and it runs on every compiled situation, shadow included, BEFORE the change gate, writing a row each pass (`03` F141) | `reason/domain_shadow.py:1262-1300` vs `:1356`; `platform/intelligence_onboarding.py:164-168` |
| 3 | R-2's prose never reaches the card | **partly** — two API routes read it, `deliver/` never does | `api/intelligence_routes.py:741, 1576` |
| 4 | the R-site machinery exists; replay recomputes without the model | **partly** — the machinery is there (`run_site`, `RSiteGate`, `PostgresSiteCache`, six closed sites); **replay is model-free only for the formula**: with the decider on, `decide` calls the model again in a fresh process (`03` F139) | `reason/llm_sites.py:314-377`; `reason/decision_maker.py:1119-1126`; `reason/replay.py:165-201` |
| 5 | the seam is right after the slice and the compile | **true, moved** — and it runs before the change gate | `reason/domain_shadow.py:1234-1243` |
| 6 | a card needs a full audited Layer 4 run | **true** | `reason/authority.py:15-42, 119-265`; `reason/audit.py:254-286` |

### 8.3 · New — not in the plan

- **N1 · No per-file loop.** Layer 4 iterates situations; a file is the set of situations sharing an
  anchor, and nothing groups them or fans a result back.
- **N2 · Replay is not model-free with the decider on** (`03` F139) — its cache lives in the process.
- **N3 · A truncated answer is detected and read by nobody** (`03` F140): `LLMResult.truncated`
  (`2caf88aa`) has no reader; the decider's own client never reads `stop_reason`; the gate checks `ok`.
- **N4 · The site machinery is not sized for the expert.** One tier per site (T1 Haiku, T2
  `claude-sonnet-5`, no Opus tier); the R-site cache key leaves the model out; the per-consult ceiling
  of $0.05 refuses any Opus-class call; the gate retries on every refusal, so "repair the syntax,
  never the substance" cannot be said; adding a site touches about ten pinned places.
- **N5 · No Plane R result contract exists** (0 hits for any Group 1–4 shape), and the citation
  resolver knows fact versions and source refs, not the event ids a timeline cites.
- **N6 · The dossier's parts exist but are unbounded or unread.** The timeline and numbers have no
  cap; numbers re-read the tenant per file; prior cards, verdicts and `derived.history.*` have no reader
  by file; `bounded_read` walks the graph (the wrong tool); `simulate` needs a finished decision and
  has no "time passes"; a playbook has no version; `Measured` carries no evidence ids.
- **N7 · Spend.** R-sites share a $2/day/org budget; the decider has a call count (400/org/day, per
  process) and no dollar cap; the platform's $25/day cap gates Layer 1 only.
- **N8 · The golden set measures the plumbing, not the model.** The ideal reader answers each site as
  a faithful model would, from what the case authors; an expert site needs an authored answer per
  file. Only a live pass (D12c) measures the model itself.

### 8.4 · What changes in the design

1. **Per file, with its own road to a decision.** The expert reviews a FILE when its fingerprint
   moves; the review is stored once (`expert_reviews`) and replayed from the store. In M33 a covered
   file's review IS its decision — one audited Layer 4 run per file, its anchor the subject — and the
   per-situation decisions on that file stand down (no decider, no R-1). A situation with no file
   stays on today's path.
2. **The model writes judgment; code decides the lane.** The review carries a mode (act · find out ·
   wait · nothing · blocked), an appraisal with reasons, a next move and a draft. Code maps the mode to
   the decision outcome, takes the play from the next move, computes confidence from the evidence that
   validates — never the model's number — and routes the lane with `reason/output_lane.route`. Under
   D1 the appraisal also sets importance and urgency; without it the review is advice and the formula's
   numbers stand.
3. **The fingerprint is the file's:** its events, asks, whose move, quiet days and the next meeting as
   rungs (a 72-hour rung added), the brief version, the playbook's content hash, the verdicts on its
   people, and who decides — model and prompt version (D48).
4. **A refusal is a record:** truncated, schema-invalid or over budget is stored with its reason; one
   repair for syntax only; a substantive refusal stands until the file moves.
5. **R-6 retires** (D51): it never ran in production, runs ahead of the gate, and the expert replaces
   it. R-2 stays until `STEP-14` shows the expert's own explanation.
6. **The number that must move is restated.** *Must-detect ≥ 90%* needs a card per file — this step
   gives each covered file one decision, `STEP-14` makes it the one living card. STEP-12 is measured by:
   every changed file reviewed once and validated; an unchanged sweep 0 expert calls; replay 0 model
   calls; the decider's calls on covered files 0; the board after M33, case by case; and a live pass on
   the D7 model before any rollout (D50).

### 8.5 · What will be built — tree block `yc2_w27_s12` (M32, M33), proposed

**M32 — the expert reviews every changed file, in shadow** (no card changes): C1 the contract — the
review, migration `0197_expert_reviews`, the site and its feature, the tiers and the cache key ·
C2 the dossier — one file read, prior judgments by file, the dossier, the playbook's version, the file
fingerprint · C3 the call — the checklist prompt, the review run, the store, the pass in the sweep, the
route, a health check · C4 the gate's fixes — a truncated answer refused (F140), R-6 retired (F141) ·
C5 the golden set — the ideal reader's expert answers, authored per case, re-recorded, the acceptance.

**M33 — the review decides** (after D1): one audited decision per covered file from its review, the
situations of a covered file standing down, replay with zero model calls (F139 for covered files), the
board measured, and the live pass (D50).

28 units (22 in M32, 6 in M33), critical path 14 — ⛔ widened to **37** (30 in M32, 7 in M33) by §8.8 — ⛔ **60** as built (39 in M32, 21 in M33): the build minted each unit where it measured what the plan had not (§9). Each unit, its artifact and its verify command are in `tree.yaml`.

### 8.6 · Decisions

| | Question | Recommended | Default |
|---|---|---|---|
| D1 | Does the expert's appraisal decide what matters? | yes — the Atlas RULE 02 amendment; numbers, permissions and recipients never from the model | advice only: M32 builds, M33 waits |
| D7 | Which model, and the cap? | Sonnet-class; Opus-class for files with a deadline or a meeting within 72 h; $5/day/org | Sonnet only |
| D48 | Does a prompt change re-decide? | yes, from here: the prompt version is in the fingerprint | waits for inputs |
| D49 | Who writes the golden set's expert answers? | Claude, per case, from the case's own text, each marked `claude` — you may correct any | the same |
| D50 | A live golden pass on the D7 model before rollout? | yes — an estimate: ≈ 140 reviews, ≈ $6 at Sonnet-class list prices | no spend; the board measures the plumbing only |
| D51 | Retire R-6? | yes — never ran, runs ahead of the gate, superseded | it keeps writing a row per situation per pass |

**Answered on 10 Oct**, with the go: **D1 yes** · **D7 Sonnet-class only, $2/day per org** (no Opus tier:
M32.C1.L-contract.V0.U04 keeps the model in the cache key and the expert's own per-consult ceiling, and
drops T3; a busy day reviews the nearest deadlines first and carries the rest, said) · **D49 yes** ·
**D50 yes** · **D51 yes**. D48 stays open. Before the build: the steps before it completed and aligned
(the founder's condition for the go) — §8.8.

### 8.7 · Risks

- **A golden answer written by the same hand as the code** — the board then shows that the plumbing
  carries a judgment, not that the judgment is good. The live pass (D50) is the test of the model.
- **A file with several kinds of situation** — one review per file must not erase a situation the file
  does not explain; a situation the review does not mention keeps its own decision.
- **Cost** — a busy tenant's first sweep reviews every file once; the pass is bounded per sweep, by
  nearest deadline first, and capped per day.

### 8.8 · Before the build — the steps before it, completed and aligned (`yc2_w27_align`, M34)

Your go of 10 Oct came with a condition: every step before this one complete and aligned first
(`10-BEFORE-STEP-12.md`). The block that met it, and what it changes here:

**What this step now stands on.** The exam is **58 cases** (F48–F58 added: the benchmark's five
shapes, three brief-only, a renewal, a verified close, our domain as the platform's), every case
forbids something and a forbidden phrase is matched as a claim — the before-score this step is
measured against is in `03` §F.1. A file's quiet window follows its kind (`06` D33 in code); the
brief has a seventh kind, `vendor` (D18); a programme's or a portal's file is refused
`misfiled_kind`, never decided as an investor; a file's history places each ending on its own file
and generation (F113); dates read late are framed by the mail's own day (F148) and a window's promise
is due when it closes (F149); the first-connect door reaches the sweep's verdict on all 58 cases; two
health checks say how far back memory reaches and whether every piece of work in motion has one file.

**What this step takes in, and where** — nine units the block adds to `yc2_w27_s12` (37 in all):

| Input | From | Unit |
|---|---|---|
| an in-motion counterparty is a named sender, so its archived mail is promoted | `03` F125 (measured by M34.C2 U08: F21, F22) | M32.C1.L-contract.V0.U05 |
| the brief's draft prints each proposal's kind | F127 | M32.C1.L-interface.V0.U06 |
| a touch's words in the timeline — a portal's notices, the reply a promise answered — and each event's outcome asked first | F99, F147, F57 | M32.C2.L-data.V0.U06 |
| each situation's lifecycle, with the quiet window of its kind | STEP-11, D33 | M32.C2.L-data.V0.U07 |
| the time-passes what-if | `06` D39 | M32.C2.L-logic.V1.U08 |
| the file's own past in *what was judged before* | F113 (placed by M34.C2 U07) | M32.C2.L-data.V0.U02, widened |
| what triggered a review, and no review without one | `05` §5 | M32.C3.L-logic.V1.U09 |
| the stage's dwell against its prior | D39 | M32.C3.L-logic.V2.U07 |
| the expert proposing a kind, labelled — the founder accepts | F132, F151 | M32.C3.L-logic.V2.U08 |
| the compiled lane's corpus thresholds read the file's numbers | F104 | M33.C1.L-logic.V0.U04 |

**And as decided, not built here:** your reply time is not split by who wrote first (D52); a screen
touch is not in a file's timeline (D53); a *"soon"* promise is no deadline — the expert judges it
(D56); the shadow decider's spend ends with M33, which replaces it on covered files (F11, D51).
Owned elsewhere: F146 and F150 are `STEP-14`'s, F152 is `STEP-13`'s, `STEP-14`'s and `STEP-16`'s.

---

## 9 · Built — 12 Oct (tree `yc2_w27_s12`, 60 units)

**M32 — the expert reviews every changed file, in shadow** (39 units). The review is a contract
(`contracts/expert_review`: facts that cite, a frame and its rivals, expected against actual, scenarios,
an appraisal of levels with reasons, a next move, a draft) and a store (migrations `0197`–`0199`: the
review, the inputs its fingerprint read, what triggered it). The expert is R-7, Sonnet-class with its own
ceiling and a $2 day (`06` D7). Its dossier is one file read alone — the brief, the timeline with each
touch's words, what was judged before, the file's numbers with their n, its kind's playbook with its
version, the time-passes what-if — and its fingerprint is the file's: events, asks, whose move, quiet and
meeting rungs, the brief's and the playbook's versions, who decides. One repair for syntax only; a cut
answer refused (F140); a refusal a record. The pass runs in the sweep: each file that moved and that
something touched (`05` §5) reviewed once, nearest deadline first, at most ten a pass; an unchanged sweep
asks nothing. A kind the expert proposes is a labelled proposal you accept (F132, F151). R-6 retired
(D51). The golden set's expert answers are authored per case (D49, 66 files over 58 cases).

**M33 — the review decides each covered file** (21 units, under `06` D1). A covered file is decided once,
from its review, as an ordinary audited Layer 4 run (`reason/expert/decide`): the mode is the outcome —
act a decision, find out an Investigation, wait or blocked Monitor, nothing Suppress — confidence is
code's (the source events its facts cite), the appraisal's levels set urgency and importance, and no
model is asked: no decider, no R-1, and a replay asks none (F139). The pass runs first and names what its
valid reviews cover and who is in each file; everything a review explains stands down — the compiled
lane's situations on the file, on its people, on a node no one owns, the packs' rules, the shadow native
lane (F173); the file keeps ONE decision — the same advice stands, other advice replaces it, a review
that names no move clears it (F174, F175); its card speaks the review's own words and its success is the
review's `done_when`. The compiled lane's corpus thresholds read the file's measured numbers (F104).

**Measured** (`03` §F.1): must-detect **13 → 21** of 45, must-abstain **12 → 13** of 13, forbidden outputs
**8 → 0**, the Atlas replays passing **4 → 6** of 80. On all 58 cases the decider is asked nothing a covered
file's review explains, eight files that never reached the decider before are decided, every must-abstain
case holds, and every expert decision replays with every model door poisoned (M33.C2 U02). The
first-connect door tells a founder who presses Sync what the sweep tells them, on all 58 (F177). The live
pass is ready and has not run: `scripts/golden_eval.py --dry-run --site expert` counts **97 expert calls,
≈ $2.08** on `claude-sonnet-5` (the ideal reader's token estimates).

**What did not move, and whose it is:** a second card where the review's advice changed as the file
moved, or was re-decided after its week (F02, F05, F06, F12, F24, F25, F50 — F176, `STEP-14`'s living
card); a *find out* review held in Investigation with no card to ask it (F01, F52 — `STEP-13`); F15's wave
reviewed once and never again (F169, `06` D57); F19's three people in one file (`06` D58); F56's renewal
lost at the gate; an expert founder card whose move names no date stands the 7-day default (F179,
`STEP-14`); the expert's prompt does not say to speak to you as *"you"* (F178, `STEP-13` §3.3).

**Still owed:** the live pass on your yes and a key (`06` D50); the push; the deploy — migrations
`0197`–`0199`, `expert_review` on for your org only, the expert's health check a day later; D48, D57, D58.
