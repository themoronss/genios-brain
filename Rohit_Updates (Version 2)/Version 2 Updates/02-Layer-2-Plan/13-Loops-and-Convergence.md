# L2 — Loops, Convergence and Invalidation

> Layer 2 is the only layer in GeniOS with **feedback inside itself**. A new event changes
> a situation, which changes a score, which changes a lifecycle state, which emits an
> observation — which is an input to correlation. **That is a cycle**, and the first draft
> of this plan did not name it.

---

## The five loops

| # | Loop | Cyclic? | Hazard |
|---|---|---|---|
| L-1 | Drain loop — one pass per sweep | no | — |
| L-2 | Situation lifecycle: `active ⇄ dormant ⇄ resolved ⇄ reopened` | bounded | ✅ reopen path already exists and is correct |
| L-3 | Merge: propose → review → apply → **reverse** | bounded | reverse must **split situations back** |
| **L-4** | **Re-correlation** | **YES** | 🔴 **non-termination** |
| **L-5** | **Coverage change** | **YES** | 🔴 **silent staleness** |

---

# 🔴 L-4 · The re-correlation loop

### The cycle

```
new event joins a situation
   -> situation member set changes
      -> importance recomputed (BLG-18)
         -> lifecycle re-derived (BLG-19)
            -> an observation is emitted  (e.g. situation_reopened)
               -> observations are an INPUT to correlation
                  -> re-correlation
                     -> back to the top
```

Left unguarded this does not terminate. Worse, it does not *obviously* not terminate — it
looks like a slow sweep, then a slower one.

### The fix — bounded fixpoint with a convergence check

```
MAX_PASSES = 3

for pass in 1..MAX_PASSES:
    state_hash_before = hash(situations, memberships, lifecycle states)
    run correlate -> derive -> score -> lifecycle
    state_hash_after = hash(...)
    if state_hash_after == state_hash_before:
        break                      # converged
else:
    # 3 passes and still moving
    record `l2_convergence_exceeded` with the org, the situations still changing,
    and the state hashes. Do NOT keep iterating. Publish what pass 3 produced.
```

**Publishing an unconverged state is correct.** The alternative is an unbounded sweep, and
a slightly-stale situation is recoverable on the next drain while a hung worker is not.

**`l2_convergence_exceeded` is an alert, not a log line.** A tenant that never converges
has a genuine derivation cycle, and that is a design defect to find, not a runtime
condition to tolerate.

### The structural rule that prevents most of this

> ## A derived fact may never be an input to its own computation.

Enforced as a **DAG assertion over the derivation graph**, checked in CI:

```
build the graph: derived_fact -> {facts it reads}
assert it is acyclic
```

**The trap this catches, concretely:** trending `account.open_situation_count` would create
a cycle — situation count feeds importance, importance feeds lifecycle, lifecycle changes
situation count. It looks like an obviously useful metric to trend, and it is a cycle.
`TRENDED_METRICS` must contain **only** facts derived from L1 signals, never from L2's own
situation state. The DAG test is what stops someone adding it in six months.

---

# 🔴 L-5 · The coverage-change loop

### The problem

L2.5.5 licenses **negative inference** on `GENUINELY_ABSENT`: *"no support tickets, and
Zendesk is connected, therefore this customer is healthy."*

**Then the founder connects Intercom.** Yesterday's `GENUINELY_ABSENT` was computed against
a source set that no longer exists. Every negative inference drawn under it is now
**unverified** — and nothing today would notice.

This runs both directions:

| Change | Effect on past inferences |
|---|---|
| Connector **added** | `GENUINELY_ABSENT` may have been wrong → invalidate |
| Connector **revoked** | facts become **stale**, and future absences become `UNKNOWABLE` |
| Connector scope **narrowed** | partial invalidation, per capability |

### The fix — `coverage_epoch`

```sql
alter table source_coverage add column coverage_epoch bigint not null default 1;
```

```
whenever the org's connection set or scope changes:
    coverage_epoch += 1

every negative inference records the epoch it was drawn under.

on read:
    if inference.coverage_epoch < org.coverage_epoch
        and the change touched this capability:
            -> mark STALE_COVERAGE, re-evaluate before use
```

**Never silently wrong.** A negative inference from a superseded epoch is *marked*, not
trusted and not deleted — deleting it would lose the audit trail of what the system
believed and why.

**Scope the invalidation.** A new billing connector does not invalidate support-absence
inferences. The epoch check is per-capability, or every connector change re-derives the
whole graph.

**ACCEPTANCE**
```
pytest tests/context/test_coverage_epoch.py -q
# connecting a new source bumps the epoch
# a negative inference from the old epoch is marked STALE_COVERAGE on read
# invalidation is scoped: a billing connector does not stale support inferences
# a revoked connector turns future absences UNKNOWABLE, not GENUINELY_ABSENT
```

---

# L-3 · Merge reversal must split situations back

`merge.py` already merges situations when their entities merge, and it preserves the human
resolution correctly (`merge.py:153-158`). **The reverse path is missing.**

When a merge is reversed:
1. situations merged **because of** that merge must split back
2. their `signal_ids` must return to the correct side
3. importance and confidence must be **re-derived**, not restored — the inputs changed
4. a `merge_reversed` observation is emitted so downstream can invalidate its own caches

**Re-derive, do not restore.** Restoring the pre-merge score assumes nothing else changed
in the interim, and something usually has.

---

## The ten edge cases, and the loop each belongs to

| # | Case | Loop | Expected behaviour |
|---|---|---|---|
| E-1 | Late event on a resolved situation | L-2 | ✅ reopens — already correct |
| E-2 | Entity merge invalidates existing situations | L-3 | re-derive affected situations in the same pass |
| E-3 | **Merge reversed** | L-3 | 🆕 split back + re-derive |
| E-4 | 🔴 **Coverage added** | L-5 | 🆕 epoch bump → mark stale |
| E-5 | Connector revoked | L-5 | 🆕 facts stale; future absences `UNKNOWABLE` |
| E-6 | Circular dependency chain | L-4 | emit `circular_wait` — it is **output, not an error** |
| E-7 | Cohort member leaves mid-computation | L-1 | percentile carries `population_size` **as computed**; membership snapshot pinned per pass |
| E-8 | Situation's anchor entity merged away | L-3 | anchor re-resolves; situation survives |
| E-9 | Two patterns fire on one reality | L-1 | clustering merges (L2.7.3 + M-8) |
| E-10 | 🔴 **History gap: org holiday vs broken coverage** | L-5 | 🆕 **see below** |

---

# 🔴 E-10 · Holiday versus broken coverage

**The subtlest failure in Layer 2, and the one most likely to reach a customer.**

Zero emails during Diwali week and zero emails because the Gmail token expired **look
identical** in `metric_history`: both are `known=False`. And a gap read as a decline is a
**false churn signal** — on a real account, delivered with a confident receipt.

### The distinction, made explicit

```
gap_reason:
  ORG_INACTIVE      the whole org was quiet (all sources, same window)
                    -> NOT a decline. Exclude the period from the trend fit entirely.
  COVERAGE_BROKEN   this source stopped reporting while others continued
                    -> NOT a decline. Mark UNKNOWABLE, degrade confidence.
  GENUINELY_ZERO    sources were healthy, the org was active, this node was quiet
                    -> THIS IS A REAL SIGNAL. Feed the trend.
```

**How to tell them apart — deterministically, no LLM:**

```
org_activity = total events across ALL sources in the period

if org_activity == 0                        -> ORG_INACTIVE
elif this source's events == 0
     and other sources reported normally    -> COVERAGE_BROKEN
else                                        -> GENUINELY_ZERO
```

**Only `GENUINELY_ZERO` may contribute to a trend.** The other two are excluded from the
fit — and excluded, not zero-filled, because zero-filling a holiday manufactures exactly
the decline this rule exists to prevent.

**A holiday calendar is not required** and should not be used. Org-wide silence is
measurable from the data itself, which works for any org in any country without
configuration — and configuration is the thing most likely to be missing on the tenant
where it matters.

**ACCEPTANCE**
```
pytest tests/context/analytic/test_gap_reason.py -q
# all sources silent for a week -> ORG_INACTIVE, period excluded, trend unchanged
# gmail silent while calendar and hubspot report -> COVERAGE_BROKEN, UNKNOWABLE
# sources healthy, org active, this account silent -> GENUINELY_ZERO, feeds the trend
# a 7-day org-wide gap does NOT produce a DECLINING trend  <-- the false-churn test
```

**That last assertion is the one to write first.** It is the test that stops Layer 2 from
telling a founder their healthiest customer is churning because the team took a week off.

---

## Convergence acceptance gate

```
pytest tests/context/test_convergence.py tests/context/test_coverage_epoch.py \
       tests/context/analytic/test_gap_reason.py -q
python scripts/derivation_dag_check.py
```

| Metric | Gate |
|---|---|
| derivation graph is acyclic | **passes** — CI-enforced |
| drains exceeding `MAX_PASSES` | **0** on a pilot over 7 days |
| negative inferences from a superseded epoch used unmarked | **0** |
| `DECLINING` trends produced across an org-wide silence window | **0** |
| situations left unconverged at pass 3 | reported, and each one explained |
