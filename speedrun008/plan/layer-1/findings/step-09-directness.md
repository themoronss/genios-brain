# Step 9 · Claim directness — findings

**Run:** 2026-09-24 · premise checked and cost checked BEFORE any code
**Status:** 9-U1 · U2′ · U3 · U4 **DONE** — nothing left, nothing for Harsh

---

## 1. Premise check — the defect is real, one detail of its wording is not

| Written premise | Verdict |
|---|---|
| No directness field anywhere | ✅ **confirmed** — `grep directness\|firsthand\|hearsay` across `genios_engine/` returned **nothing** |
| Hearsay and first-hand are indistinguishable | ✅ **confirmed** |
| *"Both score `actor_authority = HIGH`"* | ⚠️ **wording** — `Authority` has no `HIGH`. The ladder is over ARTIFACT TYPE: `SIGNED_DOCUMENT 6 · COMPANY_CANON 5 · STRUCTURED_SOURCE 4 · ATTACHMENT 3 · EMAIL_PROSE 2 · CHAT_ASIDE 1 · INFERRED 0` |
| Rule 11's clamp: `corroborate(100, 9000) = 1882` | ✅ **confirmed** — at `INFERRED`. The whole ladder is now pinned |
| 9-U2 · *"the extractor proposes it with a span"* | ⛔ **would cost a third re-extraction** — §2 |

**The premise's conclusion is exactly right and its mechanism is sharper than written:** the
authority ladder ranks the *artifact*, so a CEO's rumour and a CEO's witnessed account are both
`EMAIL_PROSE` and take the identical rank. It is not that they are both "HIGH" — it is that the
ladder never asked the question at all.

---

## 2. ⛔ The cost check changed the design — for the third time

9-U2 says the extractor should **propose** directness with a span. Asking the model means a closed
set in `semantic/vocabulary._SETS` → moves `vocabulary_fingerprint()` → moves the
`l1_extraction_results` cache key → **the whole corpus re-extracts.** A third full bill after step
4's, which is still unpriced.

And the alternative is worse: changing the prompt **without** moving the key leaves every cached row
answering a question it was never asked — the recorded *"260 cached extractions survived a prompt
fix, the numbers did not move, and the conclusion drawn was that the fix had not worked."*

### 2.1 So directness is DERIVED, and that is better on three counts

| | |
|---|---|
| **cost** | no prompt change, no new model call, no re-extraction |
| **doctrine 1** | hearsay is a property of the WORDS, not a judgement. *"I heard"* is in the text or it is not, and a deterministic recogniser cannot hallucinate one |
| **the receipt** | the marker sits **inside the span the claim already carries**, so the evidence for *"this is hearsay"* is the quote itself. A model proposing it would need a SECOND span to justify the first |

> Steps 6, 7 and now 9 have each had their architecture set by the cost check rather than by the
> plan. In all three the cheaper design was also the more correct one.

---

## 3. What was built

### 3.1 · `capture/validate/directness.py` — the recogniser

Four values: `firsthand` / `reported` / `speculative` / `unknown`.

`speculative` is separate from `reported` and the difference is load-bearing: *"I heard Acme is
leaving"* is somebody's account of something that **happened**; *"I think Acme might leave"* is a
guess about something that **has not**. Folding them would let a guess corroborate a witness.

**The weakest reading present wins.**

```
"I heard they might be leaving"                        → SPECULATIVE
"I heard they signed, but I confirmed it with the CFO" → REPORTED
```

Taking the stronger half would let one clause launder a weak claim into a strong one — the exact
failure the axis exists to prevent.

**Absence is `unknown`, never `firsthand`.** Most business prose states facts flatly (*"the renewal
is confirmed"*), and reading that as witnessed would make the default the strongest value.

### 3.2 · The multiplier, and it can only lower

`FIRSTHAND` is **10000** — a witness is not promoted, everything else is discounted. A multiplier
above 10000 would let this axis **raise** a confidence, and Rule 11 permits a raise only by adding
independent evidence and naming it. Directness names none; it reads words already there.

### 3.3 · Wired at the only two `ConfidenceSource` call sites in the tree

`esqe/publisher.py`, both the claim-lane path and the `evidence_refs` fallback, reading the anchor
span's own quote. Pinned by a test asserting **two** call sites, because wiring one of the two would
discount hearsay on one route and not the other.

---

## 4. ⭐ The existing suite refused my first design, and it was right

`UNKNOWN`'s multiplier was **9000** for half an hour, on the word *"conservatively"* in E5.

**Eight tests in `test_confidence.py` went red.** Every caller in the tree passes the default, so a
9000 multiplier **silently discounts every composition in the system by ten percent on deploy day.**

The distinction those failures forced:

| | |
|---|---|
| **conservative** | does not INFLATE on no evidence → **10000** |
| **punitive** | DEDUCTS on no evidence → 9000 |

This axis lowers only on **positive evidence** of hearsay or speculation. `unknown` means no marker
was found — no evidence either way — and deducting for it is punishing silence, which this layer
refuses everywhere else.

> **The best thing that happened in this step.** I wrote the risk into my own docstring
> (*"that would silently DOWNGRADE the entire corpus"*) and then built it anyway. The suite caught
> it in under a minute. `UNKNOWN = 10000` is now recorded with the failure that produced it, so the
> next person who thinks "conservative means lower" finds the eight tests named.

T2 still holds and is the whole point: a CEO's hearsay (7000) composes below the same CEO's
first-hand claim (10000).

---

## 5. Guards held

| | |
|---|---|
| ALG-14's table | **untouched** — all seven ranks pinned exactly (E3: directness is a separate axis and is never folded in) |
| Rule 11's clamp | **unchanged** — `corroborate(100, 9000, INFERRED) = 1882`, and the whole ladder up to `SIGNED_DOCUMENT 4555` is now pinned |
| ALG-17's weights | **untouched** — directness belongs to CONFIDENCE (how sure) not IMPORTANCE (how much it matters) |
| `vocabulary_fingerprint` | `a3d5496aa0d3`, unchanged since step 4 |
| E4 | a junior's witnessed remark still ranks below a signed contract — directness is one input to the clamp, not a new ranking |

---

## 5b. Test result

```
FULL SUITE      12598 passed · 1061 skipped · 152 xfailed · 14 failed
                                                           └── all 14 pre-existing
before step 9:  12568 passed · 14 failed
```

**Zero regressions, +30 tests.** 25 were RED first, for the intended reason.

**No migration, no new model call, no re-extraction, and no stored value changes** — every existing
claim reads `unknown`, which is neutral, so composing the existing corpus produces byte-identical
numbers.

---

## 6. What this step does NOT do

* **It does not ask the model anything.** §2 — and that is the design, not a shortcut.
* **It does not promote a witness.** The multiplier tops out at neutral; only weak readings move.
* **It does not change any stored value.** Every existing claim reads `unknown`, which is neutral,
  so composing the existing corpus produces byte-identical numbers.
* **It does not catch hearsay with no marker.** *"Acme is leaving"* written by someone who was told
  so reads `unknown`. A recogniser cannot know what is not in the words — and inventing a reading
  is the failure this layer exists to prevent.
