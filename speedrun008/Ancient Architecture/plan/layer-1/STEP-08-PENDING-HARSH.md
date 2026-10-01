# Step 8 — PENDING · owner: Harsh

> **Status:** code COMPLETE and green · **NO migration · NO re-extraction · NO extra model spend**
> **What it does:** every score read as mediocre against a scale a third of which the tenant could
> not reach, and a third of events were never judged at all.
> **Written:** 2026-09-24 · **Evidence:** [`findings/step-08-importance-relevance.md`](findings/step-08-importance-relevance.md)

---

## 1. TL;DR — what you have to do

| # | Action | Blocking? | Time |
|---|---|---|---|
| **1** | **Run one SQL query (§3)** so metric 5 gets a real number | **YES — the last open criterion** | 5 min |
| **2** | Nothing else. **No migration, no env var, no deploy risk, no new spend.** | — | — |

**The budget is unchanged.** §9 of the step says *"do not raise the budget to make the problem go
away — allocate it"*, and that is exactly what happened: the same LLM-5 budget now judges the head
of an over-budget page instead of judging nothing.

---

## 2. The two defects, and what they cost

### 2.1 · Every score read as mediocre — and it was not

The tenant topped out at **4,640 of 10,000** across 395 signals, which reads like a system that
cannot find anything important. It is not.

ALG-17's weights are `money 3000 · deadline 2500 · criticality 2000 · authority 1500 ·
signal_type 1000`. **This inbox carries almost no amounts**, so the money term — **30% of the
scale** — contributed ~0 on nearly every signal. On a three-week-old graph `entity_criticality` sat
at `first_seen` for nearly every counterparty too.

> The effective range was roughly **0–5,000, and the tenant used all of it.**
> **4,640 is not a mediocre score. It is close to the maximum this tenant could earn.**

It is a **cold-start** problem, not a formula bug — and ALG-17 degrades *silently*. The
`baseline_estimated` flag has said so on every row since it was written.

**Nothing has ever read it.** Not it, and not any of the other nine flags: a grep for `.flags`
outside `importance.py` returns **zero**. The flag's own docstring predicted this exactly:
*"...which is how a missing-data bug hides inside a plausible score for a year."*

### 2.2 · A third of events were never judged

`ambiguous_over_budget` — **69 events, 31%** of everything reaching Layer 2. Above the ambiguous
share the guard alerted and judged **nothing**, and on a young tenant almost every sender is
unknown, so the guard always tripped.

The component that could have said *"this is a mass programme announcement"* never ran once.

---

## 3. ⭐ The one number I need — metric 5

The 31% is from the tenant re-synced away on 19 September, so metric 5 has no live baseline.

```sql
select count(*)                                                   as events,
       count(*) filter (where relevance_rule = 'ambiguous_over_budget') as never_judged,
       count(*) filter (where relevance_rule = 'unjudged_for_budget')   as deferred_new,
       count(*) filter (where relevance_rule like 'llm5%')              as model_judged
from source_events
where org_id = '<pilot org>';
```

*(If `relevance_rule` is not a column on `source_events` in your schema, the same fields are on the
trace — tell me and I will rewrite the query against it.)*

**`never_judged` is the number metric 5 tracks.** Send it and I will record the measured baseline
and the post-allocator figure in `STATUS.md`.

---

## 4. What changed

### 4.1 · The achievable ceiling — `ImportanceScore.achievable_ceiling_bp`

```
10000 − the weight of every term the TENANT'S OWN STATE closed off
```

A cold-start tenant with no priced history now reports a ceiling of **7,000**, so 4,640 reads as
**66% of what was reachable** rather than 46% of a scale it never had.

**The distinction it rests on**, and getting it backwards would make the ceiling a lie:

| | |
|---|---|
| `NO_MONEY` — *this signal* named no amount | **does not lower the ceiling.** The scale was there; this message did not use it |
| `NO_MONEY_BASELINE` — *the org* has no priced history | **does.** No signal in this tenant could earn the term |

`CURRENCY_MISMATCH` is deliberately excluded: that is a gap in **our** module (no FX table), not a
property of the tenant, and **excusing our own gap by lowering the bar is how a missing-data bug
stops being visible.**

### 4.2 · The allocator — same budget, more information

Measured on the test page (100 events, 40 ambiguous):

```
before:  llm calls 0  ·  40 × ambiguous_over_budget   ← nothing judged
after:   llm calls 1  ·  10 × llm5_business + 30 × unjudged_for_budget
```

**The alert was always right** — a high ambiguous share *is* a graph-coverage problem, too few known
counterparties, not a relevance problem. Only the consequence was wrong.

`unjudged_for_budget` is a first-class provenance value now, so an event nobody assessed is
**distinguishable** from one judged relevant. Before, both arrived as "kept" — a third of the
corpus indistinguishable from the part we actually looked at.

Every event is still kept. **Not judging is a statement about our budget, never about the message.**

---

## 5. What I got wrong / what caught me

**The totality guard caught an incomplete change mid-build.** Adding `unjudged_for_budget` without a
row in `_RULE_RELEVANCE_BP` raised `KeyError` on the first real page — the table working exactly as
designed, and the fourth time in this plan a totality guard has caught something before a test
could.

**A test asserted the defect.** `test_an_over_budget_page_alerts_instead_of_spending` asserted
`llm.calls == 0` — it pinned the all-or-nothing behaviour as correct. Rewritten to the new contract,
with the reasoning recorded in the test rather than in a commit message.

---

## 6. How to cross-check me

```bash
.venv/bin/python -m pytest tests -q -p no:randomly          # ~7 min
```
**Expect:** `12568 passed · 14 failed`. Before step 8: `12549 passed · 14 failed` — **zero regressions, +19 tests.** All 14 pre-existing.

```bash
.venv/bin/python -m pytest tests/capture/esqe/test_the_ceiling_and_the_allocator.py -q
```
**Expect:** `18 passed`. 12 were RED first.

### The guard that matters most here — the formula must be untouched

```bash
.venv/bin/python -m pytest tests/capture/esqe/test_importance_gate_probe.py -q
```

**Expect:** `10 passed`, including `test_gate_the_whole_corpus_replays_byte_identically` and
`test_gate_the_distribution_is_wide_enough_for_layer_4_to_rank_on`. **If the distribution moved,
the formula was changed and this step failed** — that is the step's own stated success test.

### See the ceiling yourself

```bash
.venv/bin/python -c "
from genios_engine.capture.esqe.importance import ImportanceFlag as F, achievable_ceiling_bp as c
print('healthy tenant :', c(()))                          # 10000
print('no priced hist :', c((F.NO_MONEY_BASELINE,)))      # 7000
print('signal w/o \$   :', c((F.NO_MONEY,)))               # 10000 — not the tenant's fault
"
```

---

## 7. What this step does NOT fix

* **It does not change any score.** ALG-17 untouched and pinned.
* **It does not move the floor.** 8-U3 (a floor relative to the tenant's measured distribution) is
  **deferred with a reason**: the step's own E4 says a relative floor on a tenant with three
  signals is meaningless, and the corpus we measured no longer exists.
* **It does not lift `relationship_change` over the floor.** Step 4 established that is a floor
  question. The ceiling makes it *measurable* for the first time — that is the prerequisite, not
  the fix.
* **It does not add a CI distribution report (8-U6).** Its properties are already enforced at gate
  time by the 10 probe tests; a report over a fixture adds ceremony and no information, and one
  over a real tenant needs production access.

---

## 8. Send back to me

| # | Item | Your answer |
|---|---|---|
| 1 | §3 — `never_judged` / `deferred_new` / `model_judged` | |
| 2 | §6 — did the 10 gate-probe tests pass? (**this is the "formula unchanged" proof**) | |
| 3 | §6 — full suite passed / failed counts | |
