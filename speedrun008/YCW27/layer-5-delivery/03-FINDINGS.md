# L5 · findings — what measuring `deliver/` actually turned up

**Date:** 2026-09-30. Everything here was measured before any code was written.

---

## ⛔ F1 · The defect we created ourselves, one step earlier

```
grep -rn "output_lane\|lane_reason" genios_engine/deliver/   ->   nothing
```

`0189` added the columns. `decision_maker` routes every decision. `domain_shadow` writes both. The
step document promised *"the card layer can group by lane directly."* **Nothing read either.**

**Built, tested, green, and called by nothing** — the eighth instance this programme has found, and
the first of its own making, in a vocabulary added one step earlier to end a different instance of
exactly that.

---

## ⛔ F2 · There is no scalar publication floor in `deliver/`

`M13.C2.U04` said to replace it.

| Where | What is actually there |
|---|---|
| `gate.py` | moment + permission. Its only "floor" clamps a deferral's `not_before` |
| `bands.py` | an urgency band off the score, from **pack config** — *"data, not engine constants"* |
| `reason/runner.py:1133` | ⛔ the score gate — `out["below_gate"] += 1` |
| `executive/explain.py` | already **reads** its receipt: *"real, but not important enough yet"* |

The Atlas's *"confidence 0.64, below the 0.70 gate"* describes the **old** engine; its own
before/after column says so. `U04` became the recall guard. **Correction #9.**

---

## ⛔ F3 · I nearly recorded that the invention validator did not exist

It is at `deliver/render.py:334`, called at `render.py:861`, re-exported by
`executive/validate.py:69`, covered by `tests/test_delivery.py`.

I grepped `reminder_facts` — the name its own docstring uses — found three files, no validator among
them, and was **one sentence away from writing "it was never written" into a cross-check.** It is a
generic function taking `corpus_text`, so its subject's name appears nowhere near it.

> **A conclusion drawn from one name's absence.** Third occurrence: `no_model_wired` (L1), the
> graph-revision guard (L3), this. The only improvement worth claiming is that this one was caught
> before it reached a document.

---

## ⛔ F4 · Three real bugs, found by my own new tests, fixed in the code

**`str(OutputLane.DECISION)` is `"OutputLane.DECISION"`.** It is a `(str, Enum)`, not a `StrEnum`. So
**every in-process caller holding the enum would have been labelled `unrouted`** — and the database
path, which passes plain text, would have kept working and hidden it indefinitely.

**The count and the label gave two answers to one question.** `tally_lane` re-described the raw column
with no reason in hand, and the pair is atomic, so a routed card was displayed as `decision` and
counted as `unrouted` in the same pass.

**The tally described a population nobody received** — and would have made the recall check a
tautology, since the tally and its comparison would be incremented by the same line.

---

## ⛔ F5 · `0189`'s header is now wrong, and a migration cannot be edited

It states the lane is inside `decision_hash`. It was, it broke four replay tests, and it was removed:
`route()` is pure over inputs already in the hash, so **a derived value has no business in a content
hash**. A migration's checksum is its immutability, so the correction is append-only in `0190`, and a
test asserts it is there.

---

## ✅ F6 · What was already right

| | |
|---|---|
| the bridge direction | Executive never imports Delivery; it writes `execution_events` and L5 reads it |
| the outbox | every outbound notification is a **row**, never a blocking call |
| the why-not vocabulary | `below_gate · budget · cooldown · muted · shadow · situation`, written **and read** |
| `COMPARISON_KEYS` | both card paths counted on **every** sweep, before either is retired |
| `card_source` | a situation-less signal is **labelled**, never dropped |
| the band cuts | from pack config, so a small-deal tenant cannot reach `critical` by construction — documented, not a bug |
| `ClaimState` | the epistemic vocabulary already exists, with a model-write permission table |

---

## What changed because of these findings

| Finding | Effect |
|---|---|
| F1 | `lane_display.py`, `0190`, and readers in pipeline / builder / store |
| F2 | `U04` rewritten as `lane_recall.py`; a test now fails if a confidence floor appears in `deliver/` |
| F3 | `claims_ok` **calls** `invention_ok` rather than replacing it; a test pins its existence |
| F4 | three code fixes, each with the test that found it |
| F5 | the correction lives in `0190`, with a test |
| F6 | nothing rebuilt; `claims.py` binds to `ClaimState` instead of inventing a second vocabulary |
