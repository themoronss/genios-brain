# Step 3 — PENDING · owner: Harsh

> **Status:** code COMPLETE and green · **two things left, both yours**
> **What it does:** stops Layer 1 throwing away what it just computed. L1 writes 28 columns;
> Layer 2 was reading **nine**.
> **Written:** 2026-09-23 · **Evidence:** [`findings/step-03-seam.md`](findings/step-03-seam.md)

---

## 1. What this step is

Layer 1's **code** is fully wired — an AST audit of all 119 modules found zero dead ones. What was
not wired is the **data**. The one that costs most:

> ALG-19 supersedes on `(subject_key, signal_type)`. `subject_key` had a column on
> `qualification_drops` (0088), on `signal_lifecycle` (0093), on `signal_conflicts` (0087) — and
> **none on `qualified_signals` (0089)**.
>
> **A signal the floor REFUSED recorded what it was about. A signal Layer 1 PUBLISHED did not.**

So Layer 2 could walk a supersession chain by pointer and could never ask *"give me every signal
about the AWS renewal."*

---

## 2. What you need to do

| # | Action | Blocking? | Effort |
|---|---|---|---|
| **1** | **Apply `migrations/0177_qualified_signals_subject_key.sql`** | **YES** — the widened projection selects a column that does not exist yet | minutes |
| **2** | **Scratch Postgres** *(same standing ask)* | yes, for the proof | ~30 min |

### 2.1 · The migration — and the ORDER matters here

```bash
psql "<url>" -f migrations/0177_qualified_signals_subject_key.sql
```

It adds one nullable column and one index:

```sql
alter table qualified_signals add column if not exists subject_key text;
create index if not exists qualified_signals_subject_idx
    on qualified_signals (org_id, subject_key, signal_type);
```

**The index is the point, not the column.** `(org_id, subject_key, signal_type)` is exactly
ALG-19's supersession key with the tenant in front, so *"every signal about this subject, of this
kind"* is one index scan.

> **⚠️ APPLY THIS BEFORE THE CODE SHIPS.** Unlike step 2's migration, this one is a hard ordering
> constraint in the other direction: the widened `_L1_SELECT` **reads** `qs.subject_key`. Deploy
> the code against a database without the column and **every situation read fails** with
> `no such column`. Constraint-then-writer for step 2; **column-then-reader** for this one.

**Nullable on arrival, deliberately.** Every row written before this has no subject, and a
`NOT NULL` would refuse the migration on a live tenant. New rows always carry one
(`NormalizedSignal.subject_key` can never be None), so the null set is closed and shrinks as the
corpus turns over. Tightening it is a separate, later migration once a tenant reports zero nulls.

### 2.2 · Migration order across both steps

```
0176_delivery_failure.sql              step 2 · CHECK widened  → apply BEFORE the code
0177_qualified_signals_subject_key.sql step 3 · column added   → apply BEFORE the code
```

Both before. Apply in number order.

---

## 3. What changed, and how it is wired

```
  esqe/normalize.py        ALG-22 derives subject_key  (unchanged — this already worked)
        │
        ▼
  contracts/signal.py      C-12 gains `subject_key`
        │                  SUPPLIED, NEVER DERIVED. The field note used to argue against the
        │                  field because re-deriving it here would be a second answer. That is
        │                  right about deriving and wrong about carrying — `lifecycle.record_of`
        │                  already takes it as a parameter for exactly this reason.
        ▼
  esqe/publisher.py        build_signal lifts it from the NormalizedSignal it already holds
        ▼
  esqe/signal_store.py     QualifiedSignalRow carries it · _COLUMNS writes it
        ▼
  migrations/0177          the column + the index            ← YOURS
        ▼
  context/situation_bso.py _L1_SELECT          9 → 17 columns
        │                  _L1_BY_EVENT_SELECT identically, and a test now asserts they AGREE
        │                  L1Signals.subject_keys — deduplicated, sorted, all states
        ▼
  Layer 2                  can finally group signals by what they are about
```

**The eight columns added**, each with a consumer that cannot get the value any other way:
`subject_key` · `domain_hints` · `confidence_bp` · `occurred_at` · `expires_at` ·
`secondary_types` · `extraction_ref` · `internal_kind`.

**17, not the 24 the plan asked for.** The other eleven either already cross or have **no reader
in Layer 2 today**. Adding them would hit the number and change nothing, so they were left and
recorded rather than padded.

---

## 4. Cross-check — the procedure

### 4.0 · BEFORE

```sql
-- the column should not exist yet
select count(*) from information_schema.columns
 where table_name = 'qualified_signals' and column_name = 'subject_key';   -- expect 0
```

### 4.1 · GATE 1 — the migration landed

```sql
select count(*) from information_schema.columns
 where table_name = 'qualified_signals' and column_name = 'subject_key';   -- expect 1

select indexname from pg_indexes
 where tablename = 'qualified_signals' and indexname = 'qualified_signals_subject_idx';
```

**If either is empty, stop.** The code will not be able to read.

### 4.2 · GATE 2 — new signals carry a subject

After one sweep:

```sql
select count(*) filter (where subject_key is not null) as with_subject,
       count(*)                                        as total
  from qualified_signals
 where org_id = 'org_e97e86f858ad48b2bbf64b8a' and created_at > now() - interval '1 day';
```

**PASS:** `with_subject = total` for rows written after the deploy. Older rows stay null — that is
the design, not a gap.

### 4.3 · GATE 3 — the published subject matches the refused one

This is the asymmetry the step exists to close.

```sql
select qs.signal_id, qs.subject_key as published, sl.subject_key as lifecycle
  from qualified_signals qs
  join signal_lifecycle sl
    on sl.org_id = qs.org_id and sl.signal_id = qs.signal_id
 where qs.org_id = 'org_e97e86f858ad48b2bbf64b8a' and qs.subject_key is not null
 limit 20;
```

**PASS:** the two columns are identical on every row. They are the same derivation carried twice;
**a single disagreement means something re-derived it**, which is exactly what the field note
forbids.

### 4.4 · GATE 4 — a situation can now group

```sql
select s.correlation_id, count(distinct qs.subject_key) as subjects, count(*) as signals
  from context_correlation_members m
  join qualified_signals qs on qs.event_id = m.event_id and qs.org_id = m.org_id
  join context_situations s on s.correlation_id = m.correlation_id and s.org_id = m.org_id
 where m.org_id = 'org_e97e86f858ad48b2bbf64b8a'
 group by 1 order by signals desc limit 10;
```

**PASS:** `subjects` is populated and is **less than or equal to** `signals` — several signals
about one thing is the whole point. All-1s would mean the subject is degenerating to the event
fallback, which is worth investigating.

### 4.5 · GATE 5 — nothing else moved

```bash
python -m scripts.pipeline_funnel_report --org org_e97e86f858ad48b2bbf64b8a --database-url "<url>"
```

**PASS:** every count unchanged. **This step changes what Layer 2 can SEE, not what Layer 1
does** — §3's own prediction. If a funnel count moves, something broke rather than improved, and
that is the signal to stop.

### 4.6 · The suite, on a real database

```bash
export GENIOS_TEST_DATABASE_URL="<scratch>"     # NOT production
uv run --no-sync pytest tests/test_l2_reads_what_l1_publishes.py tests/test_l1_seam_activation.py -q
uv run --no-sync pytest -q -p no:randomly
```

Those two files are the end-to-end proof for this step and **have never run against this change** —
they are Postgres-marked and skip here. **A skipped test is not a pass.**

### 4.7 · Send back

| | BEFORE | AFTER |
|---|---|---|
| Columns crossing the seam | **9** | ? *(expect 17)* |
| New rows with a non-null `subject_key` | 0 | ? *(expect all)* |
| Published vs lifecycle subject disagreements | — | ? *(expect 0)* |
| Funnel counts | ? | ? *(expect identical)* |
| Suite failures on real Postgres | — | ? *(expect the known 14)* |

---

## 5. One unit was WITHDRAWN, and it is worth knowing why

The plan claimed `runner.py`'s

```sql
(array_agg(qs.extraction_ref order by qs.importance_bp desc, qs.signal_id))[1]
```

loses every signal but the loudest. **Production says otherwise**, over every event with more than
one signal:

```
per event:   signals=5  →  distinct extraction_ref = 1,  distinct domain_hints = 1
```

LLM-2 runs **once per event**, not once per signal, and domain hints are computed per event too.
So `[1]` picks the only distinct value and nothing is lost. Units U10 and U11 are withdrawn.

In their place the test file pins the **invariant that makes `[1]` safe** — one semantic call per
event — because if that ever stops being true, `[1]` becomes a silent loss with no error.

> This is the **second step running** whose written premise production corrected. Step 2's was
> *"the gate deletes bounces"*; it did not. Worth carrying into every later step: **verify the
> premise against production before building, not after.**

---

## 6. Two things this step found that were not in the plan

**6a · The drift the file warned about had no test.** `situation_bso.py` said in its own comment
that two hand-written copies of the projection is how the paths disagree — *"and only one of them
has a test."* There were two copies and **neither had that test.** There is one now, and it passed
*before* the widening, which is what makes it a guard rather than a fix.

**6b · The hermetic test schema drifts the same way.** Two files under `tests/context/` create
their own `qualified_signals` table inline with exactly the old columns. Widening the projection
broke nine tests with `no such column`. Both were widened and both positional
`insert into qualified_signals values (...)` statements made column-explicit — a positional insert
breaks on every column added, and reports a column count instead of the thing the test is about.

**Neither is Layer 1 code. Both are the same class of defect: a hand-written copy nothing keeps in
step.**
