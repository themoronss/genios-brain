# L5 · plan — four steps, in this order and for this reason

**Written for:** Harsh (CTO) and Rohit. **Date:** 2026-09-30. **Reads with:** `01-CROSSCHECK.md`.

Order is by **what is broken now**, not by unit number. `U03` first because it closes a defect this
programme created one step ago, and a defect of our own making outranks a gap we inherited.

---

## STEP 01 · `M13.C2.U03` · the lane reaches the card

**What is there.** `signals.output_lane` and `signals.lane_reason`, written on every routed decision by
`reason/domain_shadow.py`. **Zero readers in `deliver/`.**

**What to build.**

| | |
|---|---|
| `deliver/lane_display.py` | ⛔ NEW. `LANE_COPY` — what a card SAYS per lane, in the reader's words, not the engine's. `describe(output_lane, lane_reason)` → `LaneOnCard`. `tally_lane(counts, output_lane=…)` |
| `deliver/pipeline.py` | add `s.output_lane, s.lane_reason` to the selector |
| `deliver/card_builder.py` | `build_draft` carries `output_lane`, `lane_reason`, `lane_label` |
| `migrations/0190_card_lane.sql` | `cards.output_lane`, `cards.lane_reason` — the surface reads the `cards` row, so a lane that stops at `build_draft` has not reached the card |
| `deliver/store.py` | persist both |

**⛔ NULL IS AN ANSWER, AND THIS IS THE WHOLE RISK OF THE STEP.** Every signal written before migration
`0189` has no lane, and so does every signal from a path that does not route. A card in that state is
labelled **`unrouted`** and counted. It is **never** defaulted to `decision`: defaulting would have the
card assert authority no router granted it, which is precisely the failure the lane vocabulary was added
to end.

**⛔ THIS STEP DOES NOT GATE DELIVERY.** A `suppress` lane is displayed and counted, not hidden. Hiding
would change what reaches a founder on the strength of a column that — because of the spend limit — has
**never been written in production**. Carry first, measure, then decide. Deciding now would repeat the
`cards_from_situations` mistake in reverse.

**Outcome.** A card can say which of the five things it is, and a card that nobody routed says that
instead of guessing.

---

## STEP 02 · `M13.C2.U04` · ⛔ rewritten — the recall guard, not a floor replacement

**Why rewritten.** `tree.yaml` says *"the scalar publication floor is replaced by lane routing"*.
**There is no scalar confidence floor in `deliver/`** — see `01-CROSSCHECK.md` §4. The score gate is
`reason/runner.py:1133`, it already writes a `below_gate` receipt, and `executive/explain.py` already
reads it. Replacing a thing that is not there would mean building the thing first in order to remove it.

**What is real in the unit.** Its second half: *"the recall guard proves nothing is lost."* `route()`
was written so a sub-floor decision becomes `MONITOR` and explicitly **not** `SUPPRESS` — but nothing
yet **proves** that property holds, and nothing proves the per-lane counts sum to the pass.

**What to build.**

| | |
|---|---|
| `deliver/lane_recall.py` | ⛔ NEW. `recall_verdict(counts)` — the per-lane tallies must sum to the cards built, or the pass says which lane is missing. `low_confidence_is_never_silent()` walks `route()` over the confidence range and refuses any sub-floor decision that lands in an invisible lane |
| `platform/receipts.py` | one receipt: **every delivered card carries a lane or is labelled `unrouted`** |

**Outcome.** A number that would otherwise be a claim becomes a check that fails.

---

## STEP 03 · `M13.C1.U01` · the claim extractor

**What is there.** `contracts/claim_state.py` — `OBSERVED / INFERRED / HYPOTHESISED / ENVELOPE`, with
`_MODEL_MAY_WRITE`. At **field** level.

**What to build.** `deliver/claims.py` — split rendered copy into sentences, tag each with the **existing
`ClaimState`**. ⛔ No second vocabulary: two spellings of one idea disagree the first time one is extended,
which is the `FEATURE_CARDS_FROM_SITUATIONS` lesson written down one file over.

Deterministic, no model — the mapping reads the sentence against the grounded corpus and its own hedging:

| Sentence | Tag |
|---|---|
| every number, name and date is in the corpus, and it quotes | `OBSERVED` |
| grounded, but asserts something no source states outright | `INFERRED` |
| hedged — `likely`, `may`, `probably`, `suggests`, `appears` | `HYPOTHESISED` |
| an instruction or a question — asserts nothing about the world | `ENVELOPE` |

⛔ **This is not a blunt grep.** The family rule is *"assert on structure, never on text that happens to
sit near a thing."* Here the text **is** the subject: classifying a sentence by its wording is reading the
thing itself, not a proxy for it. Applying the rule here would forbid the only honest method.

**Outcome.** A card's copy stops being one undifferentiated block in which a fact and a guess look alike.

---

## STEP 04 · `M13.C1.U02` · widen the invention validator

**What is there.** `deliver/render.py:334` `invention_ok(text, corpus_text, corpus_nums)` — refuses any
copy containing a number, name or date absent from the grounded corpus. Called at `render.py:861`,
re-exported by `executive/validate.py:69`, covered by `tests/test_delivery.py`.

**What to build.** `deliver/claim_validator.py` — `claims_ok(text, corpus_text, corpus_nums, …)`,
per claim rather than per blob:

1. ⛔ **the existing refusal, unchanged and applied first.** Widening must not become loosening: if
   `invention_ok` refuses the copy, `claims_ok` refuses it, with the same reason.
2. an `OBSERVED` claim that cites nothing is **not** observed — refused, because "lifted from a source"
   with no source named is the strongest thing a card can say and the easiest to say falsely.
3. a `HYPOTHESISED` claim must be **marked** in its own wording. `claim_state.py` requires it: a
   hypothesis is *"never rendered as fact"*.

**⛔ NEVER WEAKEN A VERIFY TO MAKE IT PASS.** `claims_ok` adds refusals and removes none. Every existing
`invention_ok` test must still pass **unchanged** — that is the proof, and it is the reason `invention_ok`
is called rather than reimplemented.

**Outcome.** The validator asks about each claim what it used to ask about the paragraph.

---

## What this plan does NOT do

| | Why |
|---|---|
| gate delivery on the lane | no production row has ever carried one. Carry, measure, then decide |
| touch the score gate in `reason/` | it works and its receipt is read. Out of L5 |
| invent a claim vocabulary | `ClaimState` exists |
| put a model anywhere in L5 | a lane is a route and a claim tag is a classification. §4 of `00-ARCHITECTURE.md`: *"if the output is a number, a route or a permission, no model produces it"* |

---
---

# ⛔ 2026-10-01 · the second half of the plan — eight more steps

**The four steps above were built on 2026-09-30.** This section is the plan produced by re-measuring
`deliver/` **after** that build, and it is specified in
[`05-RECROSSCHECK-the-silences-of-the-delivery-spine.md`](05-RECROSSCHECK-the-silences-of-the-delivery-spine.md).
Each step has its own `STEP-NN-*.md` with its tests, its mutations and its verify command.

**No code has been written for any of them.** The order below is the build order.

---

## Why these eight, and why in this order

Order is **bottom-up**, not by severity. `STEP-05` builds the declared-silence module first, because
`06`, `07`, `08` and `09` each resolve one unreached function and all four need somewhere to write the
resolution down. `STEP-10` is last among mine because it writes production receipts, and a receipt
written before the layer's guarantees are settled asks production a question whose correct answer nobody
had established — which goes green and is believed.

| Step | Unit | What it settles | Owner |
|---|---|---|---|
| 05a/05b | `deliver/` declares what it does not call | ⛔ **123 public functions, 24 unreached, 0 declared** — the only large package with no declaration. Corrected from 133/4 by `06-AUDIT`; the step became a **level** | me |
| 06 | the cutover nobody guards | `spine.recover_expired_claims`: a guard that fires when the v2 cutover is taken | me |
| 07 | two comments that read as measurements | `push.py:19` claims an unreached function is fired; `units.py` claims one adapter where there are two | me |
| 08 | the headline fix nobody wired | `resolved_person_name`, carrying *"35 of 38 person cards named an address in the headline"* | me |
| 09 | the gate writes down why it refused | `gate.describe_decision` — wire it, or declare it and name the missing sink | me |
| 10 | two receipts for nine thousand lines | ⛔ L5 carries **2 of 32** receipts and one of the two ERRORs | me |
| 11 | the Atlas does not know Layer 5.2 exists | three superseded badges and a six-module omission | me |
| 12 | the *lane* receipt cannot run | ⛔ **blocked on H1.** `0190` breaks `insert_card` | **Harsh** |

---

## The rules every one of these eight is built under

These are not new. They are the rules this programme has paid for, and each one below cost something.

| Rule | What it cost to learn |
|---|---|
| ⛔ **an uncalled function on an un-cut-over path is not a bug; it is an unguarded cutover** | one grep away from a wrong live-harm finding in `spine.py` — see `05-RECROSSCHECK §5` |
| **a receipt that cannot fail is not a gate** | L4 |
| **presence is not effect** | eight instances of built-tested-green-and-called-by-nothing |
| **declared and written are two directions; one alone is half a guard** | L4's `unreached.py` |
| **a guard written for one member of a closed table is half of that** | L4 |
| **a grep that finds nothing is not evidence that nothing is there** | ⛔ I added a global receipt-count literal 11 lines above the guard that already existed |
| **two targeted test runs are not a suite run** | L4 |
| **never weaken a verify to make it pass** | the standing rule — `STEP-08` is where it bites, if a resolved name fails `invention_ok` |
| **a stale comment reads as a measurement** | six occurrences, two of them `STEP-07`'s subject |
| **count guards are per layer, never global** | `STEP-10 §4` |
| **a mutation harness that restores by copying a file must clear `__pycache__`** | a mutation result had to be discarded and re-run |

---

## What this plan deliberately does NOT include

| | Why |
|---|---|
| ⛔ **taking the v2 spine cutover** | it changes which code path delivers every notification in the product, nobody asked, and the both-paths measurement that would justify it does not exist for the outbox. **Noticed something adjacent? New unit, not a silent fix** |
| building the four missing channel adapters (`api`, `email`, `teams`, `webhook`) | a product and deployment decision. `capability_report` already reports them correctly and fail-closed |
| gating delivery on the lane | unchanged from M13: that column has never once been written in production |
| ⛔ inventing a sink for `describe_decision` if none fits | a row written and never read is the exact defect found eight times. `STEP-09` declares instead |
| a fresh production re-measure of the 35-of-38 headline defect | ⛔ no database URL is configured in this checkout. Logged as a separate read; **`GENIOS_ALLOW_PROD_WRITE` is never set to run a report** |

---

## Totals, if all eight land

| | |
|---|---|
| new modules | 1 (`deliver/delivery_health.py`) |
| new test files | 6 |
| corrected comments | 2 |
| wired functions | 1–2, depending on `STEP-09`'s measurement |
| declared silences | 4, each with a reason and a mover |
| new receipts | 1 certain (orphaned attempts) + up to 4 candidates, **each measured before it is written** |
| documents corrected | `08-ATLAS-SCORECARD` (renamed to `-L1-to-L5`), `STATUS.md`, `07-LEDGER`, this folder's four |
| mutations to run | 19 planned across steps 05–10 |

⛔ **Nothing is built until Rohit has read the step files.**

---

# ⛔ 2026-10-01 (later) · STEP-05 is built, and it added four steps

`STEP-05` shipped — `deliver/delivery_health.py`, 16 tests, 8 mutations all red. Its own first
measurement found its premise wrong (**24 unreached, not 4**) and the triage of the 24 produced **four
steps that did not exist when this plan was written**:

| Step | Unit | Why it exists | Owner |
|---|---|---|---|
| ⛔ **13** | a call resolved by name alone | `called_names` hid a whole tier behind a name collision — **and L4's table uses it** | me |
| ⛔ **14** | the recall guard nothing calls | `lane_recall`, built 2026-09-30, 24 tests, **imported by nothing**. ⛔ **Highest value in L5** | me |
| ⛔ **15** | a card must become deliverable | `outbox.revive_undeliverable` — a stated promise with no caller | me |
| ⛔ **16** | is there a per-recipient hourly ceiling? | `rate_limiter.py` implements one; nothing imports it | ⛔ **Rohit** |

**Build order, revised.** `13` before `14` — the precise resolver is what proves `14`'s fix landed, and
re-deriving L4's declaration against it may itself produce a finding. `15` and `16` are independent of
both.

    05 ✅  →  13  →  14  →  06  →  07  →  08  →  09  →  15  →  10  →  11
                                                            16 ⛔ Rohit
                                                            12 ⛔ Harsh

⛔ **`10` stays last of mine**, for the reason it always did: it writes production receipts, and a
receipt asking a question nobody has settled goes green and is believed. `14` and `15` each contribute a
candidate receipt, which is why they come first.

## ⛔ The rule this round added to the list

| Rule | What it cost |
|---|---|
| **a reachability number is meaningless without its source set** | the unreached count was reported as 4 when it is 24 |
| **a call resolved by name alone is a call to any function with that name** | a whole tier of the v2 path was invisible |
| **a claim worth asserting is worth storing as data** | a substring check on prose failed on correct data — the 16th in this programme |
| **a measurement can be present under a name you did not search for** | `STEP-06` said the cutover had none; `shadow_resolve_v2` was there |
| **a finding's fix is the most likely place for the next instance of the same finding** | the unit that closed F1 produced F17 |
| **a declaration that cannot distinguish a decision from a defect is paperwork** | three tables, not one |
| **a decomposition that makes a step shippable by shrinking its guard has decomposed the guard** | the 05a/05b split I proposed and withdrew |
| **no file imports itself** | the resolver reported this package's one production measurement as dead |


---

# ⛔ 2026-10-01 (later still) · five steps built, and what each one's measurement changed

Reverse-chronological. **Every single one had its premise corrected by its own first measurement**,
which is the plan working rather than failing.

| Step | Planned | ⛔ Measured | Tests · mutations |
|---|---|---|---|
| **17** | *"a level, nine units, 147 functions"* | ⛔ **one guard, eleven packages, 109 functions.** A third wiring mechanism (**reference**) removed 46 — declaring them would have been 46 lies — and a fourth (**duck-typed dispatch**) cannot be measured at all | 71 |
| **16** | a product decision for Rohit: *"should a ceiling exist?"* | ⛔⛔ **one already does** — `timing.py`, 3/hour, deferring, live. **WITHDRAWN**: the question was manufactured by reading one module | 7 · 6 |
| **11** | *"a document correction, not code"* | ⛔ it was — **plus a code change the plan did not have**: the full suite failed a `tests/executive/` test two targeted runs had missed | — |
| **10** | four candidate receipts, *"each measured first"* | ⛔ **two of five could not fail**; the window needed the scheduler's 6h interval, not my 1h; and L4's docstring promised an L5 count guard **that did not exist** | 11 · 6 |
| **15** | *"the risk nobody has checked — bound it on `expires_at`"* | ⛔ **the docstring had answered it, in the opposite direction.** The bound would have caused harm — **third retraction** | 12 · 6 |
| **09** | *"wire it or declare it"* — *"lowest severity of the four"* | ⛔ a **three-part** unit: both candidate sinks wrong, the function not keeping its own third promise, and **nothing read the table it writes to** | 13 · 6 |
| **08** | *"wire it"* — one line | one line, and it needed the **precedence** it joins and the **scope** it applies to; plus a stale docstring **inside the function being fixed** | 14 · 6 |
| **07** | two stale comments | **four**, and the fourth was in the **test docstring** guarding the behaviour | 6 · 5 |
| **06** | *"the cutover has no measurement"* | it has one — `outbox.shadow_resolve_v2`. ⛔ And 4 tests **could not be run** | 18 · 5 |
| **14** | three unwired functions | **one**. Two take no data at all — *a function that takes no data cannot be measuring production* | 12 · 5 (⛔ **one survived**) |
| **13** | *"expected: nothing changes in L4"* | L4's existing 5 were clean; **five more were missing**, and `executive/readiness.py` is wholly unreached | 9 · 5 |
| **05** | 4 unreached, one table | **24 unreached, three kinds** — the "4" counted `tests/` as callers | 16 · 8 |

**Remaining:** ⛔ **nothing of mine.** `12` and `H6` are Harsh's — it is nine packages and
147 functions, and L5's own steps come first. `12` and `H6` are Harsh's; `16` is Rohit's.

## ⛔ The rules this round added

| Rule | What it cost |
|---|---|
| **establish the baseline, or the harness is theatre** | a surviving mutation reported as caught |
| **a grep for a known-false phrase matches the record of its own correction** | nearly the 17th blunt-grep instance, and the first where the match was the fix |
| **a factual claim is guarded by making the fact derivable and named once, never by forbidding its wrong form** | four weeks of a stale justification nobody re-read |
| **a guard must not inherit the blind spot of the thing it guards** | a receipt that would have counted only the recoverable orphans |
| **a behavioural test that skips everywhere it is run is not a guard — and a skip is not a pass** | 4 tests written, 0 run |
| **a function that takes no data cannot be measuring production** | nearly wired a settled question into a per-org tick |
| **"I could not measure this" and "I measured it and it is wrong" are different sentences** | a broad `try` hid a defect in the acting half |
| **never pipe a suite run through `tail -5`** | `6 failed` with two names unaccounted for |
| ⛔ **a membership list shrinks every time the work succeeds; an invariant does not** | one test failed on correct code **twice**, and the first repair only diagnosed it |
| **a substring check against a normalised corpus is not the test; the validator is** | `'Maria' in corpus` was False while `invention_ok` passed |
| **a one-line wiring can still need two decisions** | ungated, it would have renamed a company card after one of its people |
| ⛔ **a record nobody reads is presence without effect — the reader is half the unit** | `delivery_events.detail` was written by one path and read by none |
| ⛔ **a parameter accepted and never read is presence without effect, in the signature** | `_defer(…, context, …)` ignored it, and the answer a founder wants was inside it |
| **a function can fail to keep its own docstring's third promise, and nothing will say so** | *"and the settings behind it"* read only `config_error` |
| **the right table can still be the wrong call** | `_mark_lifecycle` exists so a column and its event cannot disagree |
| ⛔ **a dead row cannot tell "we chose not to send" from "we lost it"** | the `expires_at` bound this plan proposed would have destroyed that distinction |
| ⛔ **a doctrine applied only to the instance that produced it is not a doctrine** | the third membership list, written in the step that wrote the rule against it |
| **re-deriving a canonical gate's conditions by hand is that gate's own defect, by hand** | `deliverable_channels` exists because both its conditions were once assumed |
| ⛔ **refer to a receipt by its claim, never by its position — unless quoting a dated run** | 11 live references and one filename rotted when two receipts were inserted |
| ⛔ **a rejection is reviewable only if its premise is asserted** | two candidates rejected as "cannot fail"; both premises now tested |
| **a convention is enforced by the guard that implements it, not by a test that greps for its own prose** | a meta-test failed on its own assertion string |
| ⛔ **an omission costs a rebuild; a wrong badge costs a unit** | the Atlas names none of the six Layer 5.2 modules |
| ⛔ **two targeted test runs are not a suite run — and an arbitrary subset is not a smaller suite** | a cross-layer break sat green through two targeted passes; a hand-built file list then manufactured 8 errors the real suite does not have |
| **a receipt's subject is what its first `from` names; everything after is a condition on it** | my own "stricter" fix was substring-shaped too |
| ⛔ **before asking whether a capability should exist, search the layer for it under every name it might have** | a manufactured decision reached Rohit |
| ⛔ **two implementations of one idea are not always a duplicate — one may be the race-free version of the other** | deleting `rate_limiter` would have meant rebuilding it at cutover |
| **a limit that is exact only at one worker count is a latent condition, and it must be declared** | nothing said the ceiling depends on `--workers` |
| ⛔ **a function is reached four ways and only three can be measured** | call · decorator · reference · duck-typed dispatch |
| ⛔ **a reference is a wiring mechanism** | 46 of 123 — `require_owner` has 35 references and no calls |
| ⛔ **a list you must remember to extend is a list that will be wrong** | the self-exclusion list was wrong within a minute of being written |
| ⛔ **one guard over eleven packages catches the twelfth; nine copies catch none of it** | every package was unasked before this |
