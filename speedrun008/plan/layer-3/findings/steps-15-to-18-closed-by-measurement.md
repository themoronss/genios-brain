# L3-15 · L3-16 · L3-17 · L3-18 — closed by measurement, not by code

**2026-09-25** · ⛔ **no code written for any of these four, and that is the finding**

Each was premise-checked against the tree before anything was built. All four turned out to be
already built, already closed, or blocked on something that is not engineering. Recorded here so
nobody re-opens them on the strength of the plan's original wording.

---

## L3-15 · "Delivery and feedback write back — `delivered_as`, `resulted_in`"

**Premise as written:** *"Today both are read-only against the graph."*

**Measured — the premise is TRUE and the conclusion does not follow.**

```
graph writes in deliver/ + feedback/   0
delivered_as / resulted_in             0 occurrences
```

Both are indeed read-only against `graph_*`. But **the feedback loop is already closed**, through
foreign keys rather than through graph edges:

```
execution_outcomes.decision_hash        (0041)
  → read by feedback/store.py:69
  → read by context/correlation_history.py  →  derived.history.prior_outcome
```

⛔ **Writing `delivered_as` / `resulted_in` as graph edges would be a second copy of a path the
schema already enforces** — the exact argument that deleted L3-13's two tables. And `graph_edges`
carries `authority_rank`, so a delivery edge would start competing with a CRM's assertions on the
same ladder, which is the thing the plan itself said must not happen.

**CLOSED. The loop exists. What nobody does is READ the end of it — which is L3-14.**

---

## L3-16 · "Revision — `insert·noop·restated·reversed·expired` ＋ `supersedes`"

**Premise as written:** a new table keyed `(org_id, situation_id, slice_digest)`.

⛔ **That table exists.** `migrations/0183_situation_interpretations.sql` (**L2-5**):

```sql
unique (org_id, situation_id, slice_digest)
```

— the plan's stated key, character for character. It also already provides:

| the plan wanted | 0183 has |
|---|---|
| history of readings | *"a sweep after the facts moved writes a new row and the history survives"* |
| `expired` | `valid_until timestamptz` + a partial index for the expiry sweep |
| the premises behind a conclusion | `context_slice jsonb` — the bytes, not a hash |
| an outcome vocabulary | `outcome` — `accept · unknown · escalate · refuse` |

⛔ **It is also the fifth Intelligence-Graph node kind** — `interpretation` — which L3-13 reported
as the one it could not find. That finding is corrected: **all five kinds exist.**

**What genuinely does not exist** is the five-word REVISION action (`insert · noop · restated ·
reversed · expired`) — *did this reading change what we said?* It is derivable by comparing
consecutive rows for one `situation_id`.

⛔ **NOT BUILT, DELIBERATELY. There is no reader.** Building a vocabulary nothing consumes is the
"built, tested, green, called by nothing" defect this branch has now counted twelve times — and
L3-14 measured that 70 of 141 substrate fields already sit in exactly that state.
**MOVES WHEN:** something asks a situation how its reading changed. The nearest candidate is the
card side-panel in L3-18, which is itself gated behind the L3-19 comparison.

---

## L3-17 · "⛔ The history reaches the situation — the read"

**Premise as written:** `prior_decision 0 · previous_decision 0 · last_decision 0 · past_decisions 0`

⛔ **Those are the wrong words, and the capability exists under the right ones.**

`genios_engine/context/correlation_history.py` — *"Cross History — what happened the LAST time this
anchor was in this situation"* — publishes four facts and **runs inside the live L2 sweep**
(`context/runner.py:752`):

- `derived.history.times_seen`
- `derived.history.days_since_prior`
- `derived.history.prior_outcome` — from `execution_outcomes.label`
- `derived.history.prior_card_verdict` — ⛔ *"we already told them this and they dismissed it"*

Its own docstring calls the last one *"the single most useful thing this file can say"*.

**CLOSED as a build. The read exists and runs.** The gap is that **nothing consumes it** — zero of
1,425 authored capabilities — which is measured, pinned and owned by **L3-14**.

⛔ **Tenth occurrence of the blunt-grep family, and the first one in the PLAN rather than in a
test.** A capability was declared missing because a search was run for names nobody uses.

---

## L3-18 · "The surface — card line · side panel · founder count"

**Measured — the read side is built and the routing is deliberately not switched.**

| piece | state |
|---|---|
| situation-grouped read | ✅ `deliver/pipeline._open_situations_without_cards` (L2-7) |
| the collapse measurement | ✅ `tally_source` runs on **every** sweep, flag or no flag |
| the per-situation API | ✅ `api/lifecycle_routes` — `/api/org/{org_id}/situations/{situation_id}` |
| card **routing** by situation | ⛔ **not switched — on purpose** |

`deliver/pipeline`'s own comment states the rule: *"BUILT BESIDE THE OLD ONE, NOT OVER IT.
`_open_signals_without_cards` is untouched and stays runnable for one release, because §4 of the
step says the two paths are compared on one sweep before either is retired."*

**CLOSED as blocked on a comparison, not on code.** ⛔ And until L3-19 that comparison could not
even be started, because the switch that labels the lane was refused by `require_feature`.

---

## Summary

| step | outcome |
|---|---|
| **L3-15** | **CLOSED** — the loop is already closed through FKs; graph edges would duplicate it |
| **L3-16** | **CLOSED** — the table is migration 0183. The revision action is **deferred with a mover**: no reader |
| **L3-17** | **CLOSED** — the read exists and runs live. The gap is consumption → **L3-14** |
| **L3-18** | **CLOSED** — read side built; routing deliberately held for the criterion-5 comparison |

⛔ **Four steps, no code, and the layer is better for it.** Every one of them would have built a
second copy of something that already worked.
