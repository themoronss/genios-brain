# L6 · cross-check — what is actually true in `feedback/`

**Written for:** Harsh (CTO) and Rohit. **Date:** 2026-09-30. **No code written yet.**

`feedback/` — 12 files, 2,737 lines. **Milestone M14, 3 units as specified.**

`M14` ships: *"A wrong card debits the layer that failed, and a timing complaint never lowers a
correct rule's precision."* ⛔ **The second clause is already true and already built.**

---

## The verdict first

| Unit | Verdict |
|---|---|
| `M14.C1.U01` the attribution vocabulary — eleven reasons, one layer each, closed both ways | ✅ **gap**, smaller than it reads: a 7-key ancestor exists |
| `M14.C1.U02` *"Wrong because…"* on the card, returning one of the eleven | ⛔ **partly built** — the card already offers three, and a validator already guards them |
| `M14.C1.U03` the router — reason → layer → the thing that changes, `bad_timing` to L5 timing | ⛔ **the headline half is DONE.** The layer half does not exist at all |

---

## 1 · ⛔ Finding 1 · `bad_timing` already does not touch precision — the milestone's own promise

`feedback/calibrate.py:26`:

```python
TAXONOMY = {
    "run_play":            {"label": "positive_strong",     "precision": "numerator"},
    "do_it_myself":        {"label": "positive_moderate",   "precision": "numerator"},
    "wrong:not_relevant":  {"label": "negative_relevance",  "precision": "denominator"},
    "wrong:wrong_facts":   {"label": "negative_relevance",  "precision": "denominator"},
    "wrong:bad_timing":    {"label": "timing",              "precision": "none"},   # ⛔
    "snooze":              {"label": "timing",              "precision": "none"},
    "requeue":             {"label": "window_mgmt",         "precision": "none"},
}
```

And `feedback/units.py:135`:

```python
judged = c["acted"] + c["wrong"]      # bad_timing does not grade accuracy
```

And `_PRECISION_SQL` restricts the denominator to `in ('not_relevant','wrong_facts')`.

> ⛔ **Three independent places already enforce it**, and `packs/brains/adaptive_lease.py` documents
> the same rule from the consuming side. *"A timing complaint never lowers a correct rule's
> precision"* is not work to do; it is work to **not break**.

⛔ **And the SQL goes further than the milestone asked.** The denominator is also restricted to
`card_level in ('prescriptive','predictive')`, with a comment that is the best statement of the
principle anywhere in the repo: *"counting that as a precision failure made answering the system's
own question evidence the system was wrong."* A NULL level is excluded rather than assumed, because
*"defaulting it to 'instruction' is how the old behaviour comes back."*

**This is the tenth correction to the programme's planning documents.**

---

## 2 · ⛔ Finding 2 · Nothing in `feedback/` names a layer

`grep -rn "layer" genios_engine/feedback/` returns seven hits and **every one is prose in a
comment** about the import topology. There is no reason→layer map, no layer counter, no layer
column. The milestone's **first** clause — *"a wrong card debits the layer that failed"* — is
entirely unbuilt.

`TAXONOMY` is its ancestor: it already routes a reason to *a consequence* (`precision`:
numerator / denominator / none) and to *a label*. What it does not say is **which layer to go and
look at**. `negative_relevance` tells a calibrator to lower a rule's precision; it does not tell an
engineer whether the signal was mis-captured (L1), mis-reasoned (L2), mis-linked (L3), mis-assigned
(L4), or mis-timed (L5).

---

## 3 · ⛔ Finding 3 · There are three reasons, not eleven — and four readers of the three

| Where | What it holds |
|---|---|
| `deliver/card_builder.py:849` | `{"type": "wrong", "reasons": ["not_relevant", "bad_timing", "wrong_facts"]}` |
| `deliver/actions.py:31` | `WRONG_REASONS = {"not_relevant", "wrong_facts", "bad_timing"}` — the **inbound validator** |
| `feedback/calibrate.py:29-31` | three `wrong:*` keys in `TAXONOMY` |
| `feedback/units.py:124` | `elif reason == "bad_timing":` |
| `context/correlation_history.py:148` | documents the three, and reads the pair `(action, reason)` whole |

⛔ **So widening the offered set without widening `WRONG_REASONS` would have the card offer a button
the API refuses**, and widening both without `TAXONOMY` would have a reason arrive at calibration
that nothing maps — the `FEATURE_CARDS_FROM_SITUATIONS` failure exactly: *"the reader was looking
for a word the writer rejected."*

**One vocabulary, five readers, changed together or not at all.**

---

## 4 · ⛔ Finding 4 · `contracts/learning.py` exists and is not this

310 lines: `LearningObject` v2, `LearningTarget`, `LearningState`,
`ALLOWED_LEARNING_TRANSITIONS`, `LearningEvidence`, `LearningPolicy`, `Visibility`. A
content-addressed boundary contract with its own hard rules (*"there is no `expert` target in any
enum"*, integer basis points, *"identity uses the source-observation time so a retry clock cannot
mint a new proposal id"*).

`M14.C1.U01` names this file as its artifact. ⛔ **The vocabulary goes BESIDE that contract, not
into it.** `LearningObject` is hashed on its own fields; adding a member to an enum it validates
against would change identities already minted. A new closed map is additive and hashes nothing.

---

## 5 · What is NOT wrong here

| | |
|---|---|
| the precision rule | three places enforce it and a fourth documents it |
| the abstention exclusion | a `review` card answered by a human is not a precision failure, and the comment explains why |
| Wilson intervals | `_wilson_interval` — a rule with 8 judgments does not get the same confidence as one with 800 |
| the mute floor | `MUTE_PRECISION = 0.25` with `MUTE_MIN_JUDGMENTS = 12`, so a cold rule cannot be muted on noise |
| the offset bound | `OFFSET_STEP = 5`, `OFFSET_BOUND = 15` — learning cannot run away |
| the import direction | `feedback/consumer.py` records a real correction: a consumption contract only the producing layer could import was *"a decoy seam"*, and the vocabulary moved to `contracts/` |
| `(action, reason)` carried whole | `correlation_history` keeps the pair: *"`bad_timing` invites a later retry, `not_relevant` does not"* |

---

## 6 · What M14 actually is

| Unit | Action |
|---|---|
| `M14.C1.U01` | ✅ build — the reason→layer map, beside `LearningObject`, closed both directions |
| `M14.C1.U02` | ✅ build — widen the card's reasons, **and the four other readers in the same step** |
| `M14.C1.U03` | ⛔ **narrow.** The precision half is built; build the **layer debit**, and add a guard that fails if anybody makes `bad_timing` grade accuracy |

---

## 7 · The pattern, six layers running

| Layer | The document said | The code said |
|---|---|---|
| L1 | `no_model_wired` is broken wiring | one lane is model-free **on purpose** |
| L3 | nothing guards the graph revision | `reason/runner.py:570` is the guard |
| L2 | plan compile should fail on an unproduced source | it did — **six units to one absent fact** |
| L4 | never read `manager_seat_id` | it is the **standing line** the dated override sits on |
| L5 | replace the scalar publication floor | there is none in `deliver/`; the score gate is in `reason/` and its receipt is already read |
| **L6** | **a timing complaint must stop lowering precision** | **it already does not, in three places, and one of them goes further than asked** |


---

## ⛔ 2026-10-01 · *"No code written yet"* at the top of this file was true on the day it was written

**L6 (M14) has since been built: 3 steps, all DONE, 87 tests.** *(the count on 2026-10-01)*

⛔ **CORRECTED 2026-10-02.** That `87` and `00-START-HERE`'s `53` counted different things on
different days, and neither is the layer's total now — the directory runs **243 passed, 27
skipped** after `S1`–`S9`. ⛔ **A hardcoded count is wrong the next day; the command is the
answer**: `.venv/bin/pytest tests/feedback -q -rs`. The `87` is left standing because it is dated,
and *a dated number is a record rather than a claim about today.*

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
