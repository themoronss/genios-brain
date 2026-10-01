# Step 6 · Domain mapping — findings

**Run:** 2026-09-24 · premise checked against code BEFORE planning, cost checked BEFORE building
**Status:** 6-U1 · U2 · U3 · U5 · U6 · U7 **DONE** · 6-U4 **struck (already built)** ·
6-U0 **is Harsh's** (needs a live corpus)

---

## 1. Premise check — three wrong, one unit already built

| Written premise | Verdict |
|---|---|
| *"single-label · 1 or 0 domains per event"* | ❌ **WRONG — already multi-label** |
| *"the never-filter rule has no test"* | ❌ **WRONG — 14 tests, all green** → 6-U4 struck |
| *"four keyword tables"* | ❌ **STALE** — four shipped **+ authored by L3 corpora** |
| *"815 of 889 · 8%"* | ⚠️ **corpus no longer exists** → 6-U0 |
| No per-domain confidence | ✅ confirmed |
| No model proposes a domain | ✅ confirmed |

**Effort dropped from "weeks" to "days" on the strength of these corrections alone.**

### 1.1 The multi-label one, and how the plan inherited it

`hints.py::domain_hints` loops and appends every match. The file's own comment still reads *"the
FIRST match wins in `resolve_domain`"* — **and `resolve_domain` no longer exists.** The function was
made multi-label and the comment was never updated, so a stale line became a plan premise.

So *"Security questionnaire is blocking procurement is Sales AND Security AND Procurement — today
it is none of them"* was half right. The **shape** already supported several domains. What it could
not do was recognise *Security* or *Procurement* at all, or say how sure it was about anything.

> Fixing a comment would have saved this step a week of scope.

### 1.2 The never-filter rule was already tested — 6-U4 struck

14 green tests in `tests/capture/esqe/test_domain.py`, including the strongest form: *"the tag list
is byte-identical whether the tenant has full coverage, no coverage, or no coverage function at
all."* The unit was deleted from the step and kept in §9 as a rule not to break.

> **Fifth and sixth step in a row whose written premises the code corrected.** Steps 2, 3, 4, 5
> and now 6 — twice over.

---

## 2. ⛔ The cost check ran FIRST, and it decided the architecture

The step-4 lesson, applied before a line was written:

> `vocabulary_fingerprint()` folds in every closed set in `semantic/vocabulary._SETS` and is a
> component of the `l1_extraction_results` cache key. **Adding a `domain` set to LLM-2's
> vocabulary would move it and re-extract the entire corpus — a second full model bill on top of
> step 4's.**

**Therefore the domain proposer is its own model call, not a field on LLM-2's prompt.** Four
consequences, all of them wanted:

| | |
|---|---|
| Cache | untouched. Pinned by `test_the_extraction_cache_fingerprint_is_untouched` |
| Metering | its own `purpose`, which 6-U6 required anyway |
| Cost | it can be **skipped** below 80 characters (E10) — impossible inside LLM-2 |
| Failure | it can die without failing extraction (E7) |

This is the first time the plan's own lesson prevented a defect instead of documenting one.

---

## 3. What was built

### 3.1 · 6-U1 — a hint says how sure it is

`DomainHint` gains `confidence_bp: int = Field(default=6000, ge=0, le=10_000)` plus a `before`
validator that **refuses a float outright rather than rounding it** — rounding accepts `0.85` as
1 bp, storing a confident hint as an almost-certainly-wrong one with nothing saying so.

| Source | bp | Why |
|---|---|---|
| `scope` | 9000 | the CONNECTION is that domain. Not 10000 — `hints.py` records a tenant shape where the shipped `stripe → admin` prior is exactly backwards |
| `keyword` | 6000 | this message used that vocabulary |
| `proposed` | 4500 | a *reading* of the text, below a *fact about* the text |
| `fallback` | 1000 | nothing matched. Not zero — zero reads as "certainly wrong", the truth is "no idea" |

The ORDER is the contract, not the literals, so a recalibration is free and an inversion is loud.

### 3.2 · 6-U2 / 6-U3 — the ontology, and `proposed_unknown`

`capture/domain/ontology.py`. The registered set is **derived** from `hints.py`'s own tables
(shipped ∪ authored ∪ fallback), never listed — a hand-written tuple is correct the day it is typed
and wrong the day a tenant authors a corpus, and the failure mode is the worst available: the
matcher produces a domain its own validator refuses.

**No fuzzy matching, deliberately.** Mapping `procurements` → `procurement` would hide the drift
that produced it — the same argument S-3 already makes.

`PROPOSED_UNKNOWN` and `PROPOSED_MALFORMED` are separate outcomes: `""` is a broken answer, not a
domain somebody proposed, and filing them together puts rows in front of a reviewer that name
nothing.

### 3.3 · 6-U5 — coverage is the wrong number on its own

`capture/domain/coverage.py`.

> **A tagger that returns all five domains for every message has 100% coverage and zero
> information.**

That is the six-VCs failure seen from the metric: every one of those events *had* a domain.
Coverage looked excellent until somebody read a card. So three numbers are reported together —
`tagged`, `fallback_only`, `mean_domains_per_event_bp` — plus `is_indiscriminate` and
`dominant_share_bp`, which catch the two different ways a taxonomy collapses.

**The fallback is counted apart from coverage.** `FALLBACK_DOMAIN` is `admin`, which is *also* a
real domain a keyword can match — so the counter tests the hint's **source**, never its name.
Getting that backwards counts every genuine admin thread as a gap.

### 3.4 · 6-U6 — the proposer

`capture/domain/proposer.py`. The model **describes**; `ontology.validate_proposal` **decides**;
the stored confidence is this module's constant, never the model's own number — doctrine 1.

Registered in the metering register as `domain_proposal`. **The guard caught it before I did** —
`test_the_register_lists_exactly_the_modules_that_call_a_model` failed with
`Extra items in the left set: 'capture/domain/proposer.py'` the moment the file existed.

### 3.5 · 6-U7 — the merge, and E8

**Both sides survive.** Keyword says `sales`, proposer says `fundraising` → **both**, with their
sources. Resolving that disagreement silently is how *"six VCs and three accelerator programmes
became sales opportunities. Not one of its sixteen sales situations was a customer."* A merge that
picked a winner would recreate that failure with a model's authority behind it.

Agreement **corroborates and never downgrades** (E9): a keyword's 6000 is not replaced by the
proposer's 4500. The fallback **is** replaced rather than joined — leaving it beside a real domain
counts the event in both columns of metric 4 at once.

---

## 4. Two defects this step's own build committed

Both are the same class, and it is the class this whole plan exists to find.

### 4.1 `domain_tagged` was a field nothing filled

Added to `SyncSummary`, tests green — and **nothing incremented it.** Exactly step 5's
`claimed_total` mistake, two steps later. Caught by writing
`test_metric_four_is_counted_by_the_sweep_that_produces_it`, which drives a real `run_sync`.

Fixed by counting on the actual capture loop, where `summary.gated` is appended.

### 4.2 The fixture that proved it measured nothing

The first version of that test used `source="fake"`, which has no visibility rule, so the event
**parked at S0.6** — `gated` was empty, metric 4 was measured over zero events, and it read a
perfect `0` with nothing wrong.

> **A test can be green, drive the real path, and still measure nothing.** The fix was a real
> source and real recipients; the comment explaining why is in the fixture so the next person
> does not spend the same twenty minutes.

---

## 5. Test result

```
FULL SUITE      12530 passed · 1061 skipped · 152 xfailed · 14 failed
                                                           └── all 14 pre-existing
before step 6:  12498 passed · 14 failed
tests/capture/domain                 53 passed
```

**Zero regressions, +32 tests.** 19 of the 53 domain tests were RED first, for the intended reason.

### 5.1 · One regression the targeted runs missed, and what it proves

`tests/test_domain_hints_seam.py::test_source_prior_survives_roundtrip` failed on the FULL suite
after passing every `tests/capture` run — it lives at the repo root, outside the directories this
step touched.

It asserts the **exact** JSON a `DomainHint` becomes in the jsonb column, and it exists because
`_dump_list` once stored each hint as its `str()` repr: every event fell back to `general` on
Postgres and no in-memory test could see it. Widening the contract moved that shape.

> **The right outcome, and the test earned its exactness.** It was updated to assert
> `confidence_bp` explicitly and that it crosses the boundary as an **int** — so this step's new
> field is now proved to survive the round-trip to storage rather than assumed to.
>
> **The lesson: `tests/capture` is not the blast radius of a contract change.** A widened contract
> reaches every serializer in the tree.

---

## 6. What this step does NOT do

* **It does not turn the proposer on.** `proposer=None` is the shipping default and is proved
  byte-identical to the current behaviour. Enabling it is a cost decision — Harsh's §2.
* **It does not set the target.** 6-U0 needs a live corpus; the 8% is from a tenant that no longer
  exists. Setting a target against a vanished baseline is the mistake this plan exists to prevent.
* **It does not persist `proposed_unknown` anywhere a human reads.** It is carried on
  `DomainTagging`; the review surface belongs with the open-lane discovery report.
* **It does not add domains to L3's corpus catalogue.** Authoring is a corpus task.
