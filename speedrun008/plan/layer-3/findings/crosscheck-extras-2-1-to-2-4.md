# The four steps the cross-check added — measured

**2026-09-25** · `16-STEP-COUNT-CROSSCHECK.md` raised the Layer 3 count from 22 to **26** by naming
four genuine gaps with no step. Each is premise-checked here against the tree.

**Result: 1 already exists. 3 are real and have NO READER.**

---

## 2.3 · "Held candidates have no recovery policy" — ⛔ **EXISTS**

`migrations/0122` · `situation_admission_decisions`:

```sql
outcome text not null check (outcome in ('admit','hold','reject')),
reevaluate_after timestamptz,
constraint situation_admission_hold_retry check (
    (outcome = 'hold' and reevaluate_after is not null)
    or (outcome <> 'hold' and reevaluate_after is null))
```

…plus `create index … on situation_admission_decisions (org_id, reevaluate_after)`.

⛔ **The policy is not merely present, it is ENFORCED BY THE SCHEMA**: a `hold` without a retry
instant cannot be written, and a non-hold carrying one cannot either. The index is the sweep's.

**CLOSED — the cross-check's own premise was wrong on this one.**

---

## 2.1 · "Situation identity is correlation-based, not obligation-based" — **REAL, no reader**

The unique key is `(org_id, correlation_id)` (`0038_l2_situations.sql:51`), and the spec asks for
`tenant + business_object + obligation_or_condition + period + episode`.

⛔ **Partly solved already, and the cross-check missed it.** Correlation ids are CONSTRUCTED, and
the recurring case already carries its period:

```python
f"corr_period_%_{org_id}_{key}"    # context/periodic.py — key IS the period
f"corr_doc_{artefact.node_id}_{domain}"
f"corr_firstreply_{desk.org_id}_{thread_id}"
```

So the failure the cross-check described — *"two audits… different periods cannot be told apart"* —
does not occur for **periodic** situations, which is the class it was describing.

What is genuinely absent is a general `situation_key` (1 file), `episode_id` (1 file).
⛔ **NOT BUILT: nothing asks for one.** No reader groups situations by obligation or by episode.

---

## 2.2 · "Parent/child situation hierarchy does not exist" — **REAL, no reader**

```
parent_situation_id  0 files      child_situation  0 files      sub_situation  0 files
```

Absent entirely, and `context/situations.py` / `context/situation_bso.py` contain **no mention of
a parent, a hierarchy or a rollup**. Nothing writes it and nothing wants it.

⛔ **NOT BUILT.** A hierarchy with no writer and no reader is two columns and a migration that
would sit empty — and L3-14 measured that 70 of 141 declared substrate fields are already in
exactly that state.

---

## 2.4 · "Change records are untyped" — **REAL, no reader**

The record EXISTS:

```sql
create table if not exists graph_change_outbox (
    change_id text primary key, org_id text not null, graph_version bigint not null,
    cause_event_id text, payload jsonb not null, published_at timestamptz, ...);
```

⛔ **and it has no `change_kind`** — the cross-check is right about that.

⛔ **But it is not a change FEED. It is a version CLOCK.** Its only real reader is:

```sql
select max(graph_version) as v from graph_change_outbox where org_id=:o   -- graph_store.py:1306
```

`published_at` is never read by anything. The other two references are a retention delete and the
account-erasure table list.

**NOT BUILT: typing a record whose only consumer reads `max(graph_version)` adds a column nothing
would select.** The bitemporal history that a typed change record would duplicate already exists —
`valid_to` (95 files), `supersedes` (28), `merge_history`, `graph_versions`.

---

## Summary

| | gap | state |
|---|---|---|
| 2.1 | situation identity / episode | **REAL** · partly solved for periodic situations · **no reader** |
| 2.2 | parent/child hierarchy | **REAL** · absent entirely · **no reader, no writer** |
| 2.3 | held-candidate recovery | ⛔ **EXISTS** — 0122, enforced by a check constraint |
| 2.4 | typed change records | **REAL** · the record exists, the type does not · **the outbox is a version clock, not a feed** |

⛔ **THE MOVER FOR ALL THREE IS THE SAME, and it is not engineering.** Each one is a shape with no
consumer, and L3-14 measured what that costs: **70 of 141 declared substrate fields are already
published every sweep and asked for by nobody.** Adding three more shapes to that pile would make
the measured problem worse, not better.

**They move when something reads them** — a capability that groups by episode, a card that rolls a
child situation into a parent, a consumer of the change feed. **That is corpus and product work.**
