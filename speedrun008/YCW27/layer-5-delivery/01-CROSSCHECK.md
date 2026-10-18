# L5 · cross-check — what is actually true in `deliver/`

**Written for:** Harsh (CTO) and Rohit. **Date:** 2026-09-30. **No code written yet.**

`deliver/` — 36 files, 8,674 lines. **Milestone M13, 4 units as specified.**

---

## The verdict first

| Unit as `tree.yaml` specifies it | Verdict |
|---|---|
| `M13.C1.U01` the claim extractor — split copy into claims, tag each | ✅ **gap** — but the **vocabulary already exists**, so this is smaller than it reads |
| `M13.C1.U02` *"widens the invention validator … without weakening it"* | ⛔ **the validator is BUILT and TESTED.** The widening is real work; the premise is not new |
| `M13.C2.U03` the lane renders on the card | ⛔ **the gap I created one step ago** |
| `M13.C2.U04` *"the scalar publication floor is replaced by lane routing"* | ⛔ **there is no scalar confidence floor in `deliver/`** |

---

## 1 · ⛔ Finding 1 · The gap I created, and it is the most important one here

`deliver/` contains **zero** references to `output_lane` or `lane_reason`.

Migration `0189` added those columns to `signals`, `decision_maker` routes every decision, and
`domain_shadow` writes both onto the row — **and nothing reads them.**

> ⛔ That is the **"built, tested, green, and called by nothing"** shape this programme has now found
> **eight** times — and this is the first one it created itself, one step ago, in
> `layer-2-reasoning/STEP-05`.

Its own step document says so in writing: *"`signals.output_lane` … the card layer can group by lane
directly."* It can. It does not. **Closing this is the honest priority of M13.**

---

## 2 · ⛔ Finding 2 · The invention validator exists, and I nearly reported it missing

`deliver/render.py:334`:

```python
def invention_ok(text, corpus_text, corpus_nums) -> tuple[bool, str | None]:
```

with `_digit_runs`, `_proper_nouns`, `_expand_dates`, `_corpus`, `_fold` and `_haystack` behind it.
Called at `render.py:861`, re-exported by `executive/validate.py:69`, and covered by
`tests/test_delivery.py`.

⛔ **I first concluded it did not exist.** I grepped for `reminder_facts` — the name its docstring uses —
found three files, none a validator, and was about to write *"the validator was never written"* into a
cross-check. It is a generic function taking `corpus_text`, so the name never appears near it.

> **Same shape as `no_model_wired` (L1) and the graph-revision guard (L3): a conclusion drawn from one
> name's absence.** Caught before it reached a document this time, which is the only improvement worth
> claiming.

**So `M13.C1.U02`'s premise — "widens the invention validator" — is correct.** There is something to
widen, it works, and it must not be weakened: it refuses any rendered sentence containing a number, name
or date not in the grounded corpus.

---

## 3 · ✅ Finding 3 · The claim vocabulary exists; applying it to sentences does not

`contracts/claim_state.py` already defines the epistemic taxonomy, with both directions checked at import
time:

| | |
|---|---|
| `OBSERVED` | lifted from a source. ⛔ **No model may write one** |
| `INFERRED` | concluded from observations |
| `HYPOTHESISED` | proposed, not concluded — *"never rendered as fact"* |
| `ENVELOPE` | ⛔ not a claim at all, and in the enum on purpose so *"not a claim" never means "nobody classified it"* |

Plus `_MODEL_MAY_WRITE`, the table deciding who may propose what.

⛔ **But it classifies FIELDS, not sentences.** `deliver/` has no sentence-level claim tagging —
`inference` appears three times in the package and every one is prose in a comment.

So `M13.C1.U01` is a real gap **at a different granularity**, and it must reuse `ClaimState` rather than
invent a second taxonomy. Two vocabularies for one idea would disagree the first time one was extended.

---

## 4 · ⛔ Finding 4 · There is no scalar publication floor in `deliver/`

`M13.C2.U04` says to replace it. Measured:

| Where | What it actually does |
|---|---|
| `deliver/gate.py` | **moment + permission** — when and whether it may go. The only "floor" in the file clamps a deferral's `not_before` |
| `deliver/bands.py` | cuts an **urgency band** from the score: `standard / high / critical`, from pack config, *"data, not engine constants"* |
| `reason/runner.py:1133` | ⛔ **here is the score gate** — `out["below_gate"] += 1` |
| `executive/explain.py:13` | and its receipt is already read: *"the score didn't clear the gate — real, but not important enough yet"* |

⛔ **So the thing to be replaced is in a different layer, and it already writes a why-not receipt.** The
Atlas's *"confidence 0.64, below the 0.70 gate"* describes the **old** engine — its own before/after
column says so.

`U04`'s recall guard half is separately real and already partly built: `card_source.COMPARISON_KEYS`
counts cards from situations, uninterpreted cards and cards from raw signals on every sweep, and the
guard is stated as *"fewer cards must come from merging, never from dropping."*

---

## 5 · What is NOT wrong here

| | |
|---|---|
| the bridge direction | Executive never imports Delivery; it writes `execution_events` and L5 reads it |
| the outbox | every outbound notification is a **row**, never a blocking call |
| the invention validator | built, called, tested, and generic enough to widen |
| the why-not vocabulary | `below_gate · budget · cooldown · muted · shadow · situation`, written and read |
| the cutover measurement | `COMPARISON_KEYS` counts both paths on every sweep, before the switch is taken |
| `card_source` | classifies SITUATION vs UNINTERPRETED, so a situation-less signal is labelled rather than dropped |
| the band cuts | from pack config — a small-deal tenant cannot reach `critical` **by construction**, and that is documented, not a bug |

---

## 6 · What M13 actually is

| Unit | Action |
|---|---|
| `M13.C2.U03` | ✅ **build first** — the lane reaches the card. It closes a defect this programme created |
| `M13.C1.U01` | ✅ build — sentence-level claims, **reusing `ClaimState`** |
| `M13.C1.U02` | ✅ build — widen `invention_ok` to claim type, evidence, span, wording, visibility |
| `M13.C2.U04` | ⛔ **rewrite.** There is no scalar floor here to replace. What is real is the **recall guard**: prove nothing dies of low confidence without a receipt |

---

## 7 · The pattern, five layers running

| Layer | The document said | The code said |
|---|---|---|
| L1 | `no_model_wired` is broken wiring | one lane is model-free **on purpose** |
| L3 | nothing guards the graph revision | `reason/runner.py:570` is the guard |
| L2 | plan compile should fail on an unproduced source | it did, and it cost **six units to one absent fact** |
| L4 | never read `manager_seat_id` | it is the **standing line** the dated override sits on |
| **L5** | **replace the scalar publication floor** | **there is no scalar floor here — the score gate is in `reason/`, and it already writes a receipt** |


---

## ⛔ 2026-10-01 · *"No code written yet"* at the top of this file was true on the day it was written

**L5 (M13) has since been built: 4 steps, all DONE, 222 tests.**

This file is a **crosscheck**, so *"no code written yet"* is not an error — it is what a crosscheck
says, and the date beside it is what makes it honest. It is noted here anyway because a reader
scanning for status reads that line as current, and this programme has now paid for that mistake
three separate times: a corpus comment that was true when written sent a whole unit to be specified
before it was withdrawn; seven step files carried `TO BUILD` titles on finished work; and
`02-DECISIONS.md` said *"all four open"* when two were closed.

**Nothing above is retracted.** The findings in this crosscheck are what the build was planned from,
and where one of them turned out to be wrong the retraction is recorded at the point it was found,
not here. For current status read
[`../07-LEDGER-every-step-what-why-how-outcome.md`](../07-LEDGER-every-step-what-why-how-outcome.md)
— or `../../07-LEDGER-...` from a plane folder.

---

## ⛔ 2026-10-01 · this file has a successor

M13 was built from the findings above. **Re-measuring `deliver/` after that build found more**, and
those findings are in a separate document rather than appended here, because a crosscheck's value is
that it records what was known *before* the code was written:

→ [`05-RECROSSCHECK-the-silences-of-the-delivery-spine.md`](05-RECROSSCHECK-the-silences-of-the-delivery-spine.md)

**The four largest:** `deliver/` has **123 public functions, 24 unreached, 0 declared** (⛔ the
re-cross-check first said 133 and 4; corrected in `06-AUDIT-the-measurement-that-corrected-itself.md`)
and is the only
large package with no declared-silence module · L5 carries **2 of 32 production receipts** (⛔ CORRECTED 2026-10-02: a LABEL, not a package — `deliver/` carried **5**, four of them working; [`08-CORRECTION-a-receipt-label-is-not-a-package.md`](08-CORRECTION-a-receipt-label-is-not-a-package.md)) for 9,431
lines, and one of the two ERRORs · **three Atlas L5 badges are superseded**, two of them by this
programme four days ago · and an entire six-module "Layer 5.2" architecture the Atlas names nowhere.

⛔ **One finding in that document is a retraction of a finding I nearly wrote.**
`spine.recover_expired_claims` looked like a live silent double-send. It is not: `spine.claim_due` is
called by nothing in production either, so the v2 path is **un-cut-over**. *An uncalled function on an
un-cut-over path is not a bug; it is an unguarded cutover.*
