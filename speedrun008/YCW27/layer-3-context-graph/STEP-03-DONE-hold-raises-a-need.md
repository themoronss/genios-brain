# Step 3 — ✅ DONE · a hold that asks

> **Tree:** `M10.C2.U04`

## What is true now

**467 situations are held against 223 admitted** on the pilot. A HOLD means *recoverable*
incompleteness — the publisher already distinguishes that from an absence no future sweep can
repair. But recoverable by **what**? Nothing says, and nothing goes and gets it. The situation waits
for a later sweep to bring the missing fact in by luck.

## ⛔ Only three of the seven hold reasons are evidence questions

| Hold reason | Count | Need? | Why |
|---|---|---|---|
| `verified_evidence_required` | 398 | ✅ | a span could not be verified — fetching the source settles it |
| `qes_required` | 398 | ✅ | Layer 1 published no qualified signal for it |
| `source_coverage_insufficient` | 69 | ✅ | **the clearest** — we did not read enough to make the claim |
| `identity_review_required` | — | ❌ | a merge proposal is open. **A human decides**; more evidence does not |
| `pattern_evidence_required` | — | ❌ | the pattern fired without a **receipt**. That is a writing gap, not a fetching one |
| `conflict_open` | — | ❌ | two sources disagree. **Adjudication**, not absence |
| `cross_domain_contradiction` | — | ❌ | two domains claiming opposite things — same |

⛔ **The exclusion is the design**, exactly as it is for residue in Layer 1. Raising a need for
`conflict_open` would send Layer 1 to fetch a fact it already has **twice** — and the need would
close successfully, teaching the system that conflicts resolve themselves.

## Scenario → expected result

| Scenario | Expected |
|---|---|
| a situation holds on `source_coverage_insufficient` | an `EvidenceNeed` naming the source and the window |
| a situation holds on `conflict_open` | **no need** — it goes to adjudication |
| the same situation holds twice | **one** need — the id is deterministic |
| a held situation has no subject | no need — the executor would have nothing to fetch for |
| a need already exists for that question | it is not filed again |

---

# ✅ DONE — 2026-09-30

## What was built

`genios_engine/context/hold_needs.py` — a held candidate and its hold reasons become the evidence
questions that would free it.

```
$ .venv/bin/python -m pytest tests/context/test_a_hold_asks_for_what_would_free_it.py -q
...........................                                              [100%]
27 passed in 0.12s
```

## ⛔ The spec said three needs from three reasons. The codebase says two.

This step was written as *"3 of 7 hold reasons become needs."* The three reasons are right. The
number of **questions** is two, and the codebase had already measured it and written it down —
`situation_bso.py:1004`:

> `_preflight` raises `verified_evidence_required` on a missing span AND `qes_required` when
> `importance_source` is not `l1_qualified_signals` — and on the pilot all 349 held candidates carry
> both, which reads like two independent defects. **It is one:** both are downstream of `l1` being
> `None` here... **Feeding the bundle clears both.**

And `l1_refusal` at line 570: *"`qes_required` and `verified_evidence_required` are the SAME cards
rather than two gaps."*

So the pair collapses into one need. Filing two for the 480 holds that carry both would have put
**960 rows in the queue for 480 questions**, had Layer 1 fetch twice for one answer, and charged the
tenant twice — breaking the "one question, one fetch, one charge" rule at the one seam where the
duplication is measured rather than hypothetical.

## The seven reasons, and what each does

| Hold reason | Becomes a need? | Why |
|---|---|---|
| `qes_required` | ✅ ⎫ | **one** need between them — both are downstream of one missing bundle |
| `verified_evidence_required` | ✅ ⎭ | |
| `source_coverage_insufficient` | ✅ | a different question: not *"did Layer 1 publish"* but *"did we look at all of it"* |
| `conflict_open` | ⛔ no | two incompatible facts are BOTH held. Fetching adds a third fact to a disagreement between two; an authority ruling resolves it |
| `cross_domain_contradiction` | ⛔ no | the same shape one layer up. Neither domain is short of evidence |
| `identity_review_required` | ⛔ no | *"are these two people the same person"* is a judgement about records we already hold |
| `pattern_evidence_required` | ⛔ no | **the pattern library lacks a rule.** That is our gap, not the tenant's — their documents cannot supply our rule |

⛔ The last one is the sharpest. A need for `pattern_evidence_required` would close **successfully
every time** while the situation stayed held, teaching the system that its questions are always
answered. That is worse than not asking.

## Scenario → what actually happened

| Scenario | Expected | Actual |
|---|---|---|
| held on `conflict_open` | nothing filed | ✅ |
| held on `cross_domain_contradiction` | nothing filed | ✅ |
| held on `identity_review_required` | nothing filed | ✅ |
| held on `pattern_evidence_required` | nothing filed | ✅ |
| held on both halves of the pair | **one** need | ✅ |
| held on either half alone | the **same** need id | ✅ so a later hold on both does not file a second row |
| the pair plus a coverage hold | two needs | ✅ |
| a span naming a document | `document:DOC-9` → `reextract` | ✅ cheaper and more targeted than a window re-read |
| no document span | `signal:SIG-7` → `backfill_window` | ✅ |
| a `prepared_content` span | **never** `thread:` | ✅ an event id is not a thread id |
| a coverage hold naming `gmail` | the need refuses `drive` | ✅ coverage is per source, never blended |
| two situations, one subject | one need | ✅ |
| two tenants, one question | two needs | ✅ |

## ⛔ The end-to-end guard

`test_layer_one_can_plan_a_fetch_for_every_need_filed` imports `capture`'s own `plan_fetch` and
asserts it returns a real fetch kind for every subject this module can produce. Without it, a need
could be filed whose subject `plan_fetch` returns `None` for — closing immediately as *"no Layer 1
fetch answers this"*. A question filed and abandoned in the same pass is worse than no question.

## Two things the contract taught me mid-build

**`SituationCandidate` can never be subjectless.** Its constructor refuses an empty `signal_ids` and
an empty `evidence`, so the signal fallback always fires. My defensive branch looked unreachable —
until `situation_bso.l1_refusal` named the split: *"the importance sweep passes dataclass-ish rows;
the PUBLISH path passes SQLAlchemy `RowMapping`s."* So it IS reachable, through a row. The guard
stays, and its test uses a row rather than a candidate, with the reason written down.

**A `chunk:<doc_id>:<n>` span is the only one that maps to a document.** A
`prepared_content:<event_id>` span is a message, and an event id is not a thread id. Mapping it to
`thread:<...>` would file a need whose fetch names a thread that does not exist — a need that can
never be met and never honestly closed.

## For Rohit — what you have to do

Nothing. No migration (0187 already carries the table), no config, no deploy.

## For Harsh — what to know

`needs_from_hold` is not yet called by the publisher. Step 5 wires the **residue** door; the **hold**
door is the remaining integration, and it needs one decision that is not mine to make: whether
`situation_publisher` files needs inside the publication transaction or a later pass reads the ledger
and files them. The second is safer (publication must not wait on anything) and is what I would
recommend.


---

## ⛔ 2026-10-01 · the title line of this file was stale, and is corrected above

This file's **first line** read `Step 3 — TO BUILD · a hold that asks` while the `✅ DONE — 2026-09-30` section below recorded the
work as built, and the filename had already been renamed to `...-DONE-...`. Three labels on one
piece of work and one of them disagreed with the other two.

**Why this is recorded rather than quietly fixed.** A heading that says *TO BUILD* on finished work
is the same defect as a stale comment: it reads as a status somebody checked. Anyone auditing the
programme by scanning headings would have counted this step as outstanding and, worse, might have
rebuilt it. Found while assembling `07-LEDGER-every-step-what-why-how-outcome.md`, which reads the
first line of every step file — the ledger could not have been written without resolving it.

**What was verified before the title was changed:** the artifacts named in the DONE section exist in
the tree, and the full suite is 14,534 passed / 0 failed. The title was not made to agree with the
others; it was made to agree with the code.
