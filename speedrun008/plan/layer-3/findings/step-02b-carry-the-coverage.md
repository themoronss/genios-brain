# L3-02b · Carry the coverage sentence — findings

**Run:** 2026-09-25 · premise checked before any code · **no migration · no model call**

---

## 1. ⛔ The premise check changed which seam this crosses

The plan said *"carry it onto the QES, the situation and the card — three seams."* **It is one
seam, and not the one named.**

### 1.1 · The window belongs to the QUESTION, not to the signal

*"read 37 of about 465"* is only meaningful with a window attached, and **the window is a property
of the claim, not of the message.** Putting `WindowCoverage` on the QES would freeze one sweep's
coverage onto every signal and answer the wrong question forever — a signal captured in June
carries June's coverage, and the claim being made is about September.

⛔ **So it does not cross the QES at all.** `context/` may import `capture/` (layer 2 → layer 1), so
the situation asks the question at the moment it makes the claim.

### 1.2 · The seam already had the right idiom sitting in it

`situations.unmet_source_families()` answers *"which system of record is not connected"*, reads and
never writes, returns `()` for never-measured, and is memoised one read per sweep. Its consumers
append one sentence per finding to `gaps`.

**The quantitative note is the same shape, one question over.** Built as a sibling in the same
module, consumed at the same two call sites.

> *"`source_coverage_insufficient` is a correct refusal and was an invisible one: 18 situations on
> the pilot were held on it and 0 of 18 named the family."*

⛔ **The quantitative version is worse, because it does not hold anything.** A sweep that read 8% of
a mailbox and exhausted nothing produces situations **indistinguishable from** a sweep that read all
of it.

---

## 2. ⛔ The decision that took the longest, and nearly went wrong

**Which window?**

There is no lookback constant in scope at either call site, and the obvious moves were both wrong:

| | why not |
|---|---|
| a fixed 30 or 90 days | attaches a sentence about **the wrong days** — a more confident error than saying nothing |
| `CAMPAIGN_WINDOW_DAYS` | belongs to campaigns, not to every situation |

⛔ **The defensible window is the situation's own evidence span.** If a reading rests on events from
`first_at` onwards, the coverage question is exactly *"did we read the sources across that span"* —
and it was already available: `stats.first_at` in outreach, `f.first_seen_at` in support.

**`None` means the evidence carries no times, so the question cannot be asked and is not guessed
at.** A sentence about days nobody observed is worse than silence, and both producers skip.

### 2.1 · And the memo key is the span, not the domain

The line above it memoises on `domain`, and copying that would have given **every situation in a
sweep the first situation's coverage sentence.** Keyed on the span: two domains over one span share
the read, one domain over two spans does not.

---

## 3. ⛔ No threshold, deliberately

A percentage floor would be a number nobody could defend, and the first argument about it would be
won by whoever wanted more cards.

**The rule is `WindowCoverage.can_support_absence`** — the cursor was exhausted **and** a
denominator exists — which is the rule `capture/coverage/window` already applies and the one L3-03's
gate will consume. ⛔ **One rule, three readers.**

### 3.1 · Four failures, four different sentences

| health | sentence |
|---|---|
| `FAILED` | *"a gmail sync failed in this window, so nothing here rules anything out"* |
| `PARTIAL` | *"the gmail sweep did not finish, so a tail of this window was never read"* |
| `SUCCESS_EMPTY` | ⛔ *"no gmail activity was read in this window, which is not the same as none existing"* |
| `UNKNOWN` | *"no gmail sync covers this window"* |
| healthy, no denominator | *"gmail gave no total, so we read 37 of an unknown number"* |

*"Coverage is low"* sends nobody anywhere. **A failed sync and a missing denominator are different
problems with different owners**, and collapsing them is what this module exists to stop.

---

## 4. My own weak test, caught by its probe

`test_each_bad_source_contributes_exactly_one_sentence_in_a_stable_order` **passed when `sorted()`
was deleted.** The fixture fed sources already in order, so the assertion was about the fixture, not
the code.

**Fifth time in this family** — L1-14, L1-18, L2-6, L3-00, and now here. The shape is constant: *the
assertion looked right and could not fail.* The sources are now fed unsorted on purpose.

---

## 5. Result

```
FULL SUITE   13,176 passed · 1,061 skipped · 152 xfailed · 14 failed
                                                          └── all 14 pre-existing
before L3-02b: 13,164 passed · 14 failed
```

**+12 tests · 0 regressions · no migration · no model call.**

**Technique 3 — four mutations, all red:** report only outright failures; a fixed 30-day window;
memoise on domain; drop the ordering.

## 6. What this step does NOT do

* ⛔ **It does not reach the card's own copy.** The sentence lands in the situation's `gaps`, which
  is where `unmet_source_families` lands and where the renderer already looks. **Whether the
  renderer surfaces it is a `deliver/` question and is not claimed here.**
* **It does not gate anything.** A situation with a coverage gap is still published — it now says
  what it could not see. **Refusing the claim is L3-03.**
* ⛔ **It says nothing about sources with no runs in the window.** Those are not in the distinct-
  source list, so they contribute nothing — a source the tenant never connected belongs to
  `unmet_source_families`. **Two readers, two questions, neither answering for the other.**
