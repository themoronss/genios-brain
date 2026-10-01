# L5 STEP 04 · `M13.C1.U02` — widen the invention validator · **DONE**

## ⛔ First, the near-miss

The cross-check very nearly recorded that **the invention validator did not exist.** It does:

```
deliver/render.py:334    invention_ok(text, corpus_text, corpus_nums)
deliver/render.py:861    called here
executive/validate.py:69 re-exported
tests/test_delivery.py   covered
```

The wrong conclusion came from grepping `reminder_facts` — the name its own docstring uses —
finding three files, and no validator among them. It is a **generic** function taking
`corpus_text`, so its subject's name appears nowhere near it.

**A conclusion drawn from one name's absence.** Same shape as `no_model_wired` (L1) and the
graph-revision guard (L3). Caught before it reached a document this time, which is the only
improvement worth claiming. `test_the_old_validator_still_exists_and_is_called` makes it permanent.

## What was built

`deliver/claim_validator.py` — `claims_ok(text, corpus_text, corpus_nums, *, quotes_something)`
returning `(ok, reject_detail, refusals)`, plus `observed_claims()` and `ClaimRefusal`.

**Wired at `render.py:861`**, the only place the old function was called. **34 tests** (shared file
with STEP 03).

## Widening is not loosening — and that is the whole discipline

⛔ `invention_ok` is **called, first**, and its verdict is final. Whatever it refuses, this refuses,
**with its reason string unchanged** — a widened validator that renames the old refusals breaks
every reader of `cards.reject_detail` and every count built on one. A caller swapping one for the
other can only ever see **more** refusals, never fewer, and the old function's own tests stand
untouched as the proof.

## What was added

| | Fires today? |
|---|---|
| an ungrounded token inside any claim, in the same `number:12` / `name:Acme` vocabulary | ✅ yes |
| an `OBSERVED` claim that cites nothing is not observed | ⛔ **no** |
| a `HYPOTHESISED` claim must be marked in its own wording | ⛔ **no** |

⛔ **The last two are unreachable through `claims_ok` as it stands, and the module says so in its
own docstring.** `claims.classify` establishes each at the moment it tags: it will not write
`OBSERVED` without the same `quotes_something` the validator checks, and it writes `HYPOTHESISED`
only on a hedge it found in the text. They are **invariant guards over that classifier**, not live
refusals, and the tests drive them directly rather than through the public entry point.

Saying so is the point. This programme has found *"built, tested, green, and called by nothing"*
eight times, and **an unreachable branch nobody labelled is how the ninth would start** — somebody
reads a passing test, believes a refusal is protecting production, and relaxes something upstream.
The branches earn their place by being what fails the day a classifier starts tagging from a field
instead of from the sentence, which is a change somebody will one day want to make.

## The totality guard found a real distinction

The import-time check first ran against `CLAIM_STATES` and **refused to import**: `CLAIM_STATES` is
*"the three that are actually claims. `ENVELOPE` is deliberately not one of them."* True, and not
the question — this module validates every **sentence**, and an instruction is one of the four
things a sentence can be. Guarding against the narrower set would have left `ENVELOPE` sentences
with **no declared rule at all, passing silently forever**, which is the exact failure the guard
exists to catch. It now guards against `ClaimState` (all four) and separately asserts that the
three real claim states each have teeth, with `ENVELOPE` the only one allowed an empty rule.

## Behaviour change in production: none

The only reachable new refusal fires on a token the whole-text `invention_ok` would already have
caught, so `claims_ok` is behaviourally identical today and the swap at `render.py:861` is safe.
What it adds now is **structure** — per-sentence claim tags — and what it adds later is the two
guards, the day the classifier changes.
