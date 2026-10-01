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
