# L3-04 · Knowledge time — findings

**Run:** 2026-09-25 · premise checked before any code · ⛔ **migration 0184**

---

## 1. ⛔ The premise was half wrong, and the half that was right was worse than stated

The plan said *"`recorded_at` appears in ONE file… the as-of read uses `valid_from`, which is
effective time."*

**`valid_from` IS knowledge time — on two of the three tables.** `graph_nodes` and `graph_facts`
take the column's write-time default and no writer overrides it. So the as-of read was already
answering the right question for them.

⛔ **`graph_edges` is the exception, and one predicate reads all three.**

```python
"values (..., coalesce(:vf, now()), coalesce(:vf, now()), :e)"      # valid_from, last_seen_at
{"vf": occurred_at}
```

`write_edge` binds `:vf` to `occurred_at`, and on the live capture path that is **the message's own
timestamp** — `context/pipeline.py:1040`, `context/structured.py:95`, `context/documents.py:267`.

### 1.1 · What that produces

Backfill a six-month-old email today and the edge it creates is stamped **six months ago**. An
as-of read of five months ago then **sees a relationship we learned about this morning.**

That is **LCX-02** and **CL-02** exactly — *"history is rewritten to make the system appear to have
known the correction earlier than it did"* — and the endpoint's own docstring says it answers
*"what did GeniOS know when it made that decision?"*, the question doc 02 says every enterprise
security review asks.

`write_fact`'s empty-window trick protects facts from precisely this. **Nothing protected edges.**

### 1.2 · ⛔ And L3-0A makes it worse on purpose

That step exists to widen the backfill from 60 days towards 365, because **five of the benchmark's
eight waiting relationships sit outside 60 days.** Every one of those is a year of edges backdated
into the as-of history.

---

## 2. ⛔ Why the column was not simply redefined — the check that changed the fix

`graph_edges.valid_from` has a **second set of readers who are right**:

| | |
|---|---|
| `reason/moments/recall.py:113` | `max(valid_from)` = *"when did we last relate to this node"* |
| `reason/moments/slice.py:100` | orders by it |

**Changing the write to write-time would have moved every one of those answers to a different
question with the same shape — and nothing would have failed.** The worst kind of change.

So the meaning is not taken from anyone. A second, unambiguous one is added: `recorded_at`, and the
predicate becomes `coalesce(recorded_at, valid_from)` — **uniform across all three tables**, which
keeps `_view`'s stated property that *"the two can only ever differ in the window predicate."*

### 2.1 · The migration refuses to fabricate history

`recorded_at` is **nullable, with no default and no backfill.**

* `default now()` would assert we learned a tenant's entire history at the instant this deployed.
* `default valid_from` would assert the very thing the step exists to stop believing.

⛔ **We do not know when we learned the existing rows** — the same rule that makes `claimed_total`
null rather than zero and `completeness_bp` `None` rather than `10000`. Pre-0184 rows fall through
the coalesce to exactly today's behaviour.

---

## 3. ⛔ Four things the existing suite and my own probes caught

### 3.1 · My tests failed their own mutations — twice, in one step

Two of five mutations **applied cleanly and every test stayed green**:

| mutation | why it passed |
|---|---|
| remove `recorded_at` from the edges INSERT | ⛔ **the explanatory comment I had just added contains the word**, and the assertion sliced 1,400 characters and asked whether it appeared *anywhere* |
| redefine edge `valid_from` to write-time | the assertion looked for `coalesce(:vf, now())` anywhere, and it **survived on `last_seen_at`** |

**Sixth occurrence of one family** — L1-14, L1-18, L2-6, L3-00, L3-02b, here. The shape never
changes: **an assertion about text near a thing rather than about the thing's structure.**

Replaced with a parser that reads the concatenated SQL literals, strips the Python conditionals
`graph_facts` composes its statement with, and **zips columns to values positionally.** All six
mutations red afterwards.

### 3.2 · ⛔ `context/importance.py` holds a SECOND COPY of the predicate, and a pin caught it

`test_the_point_in_time_window_matches_the_graph_store` asserts
`FACT_WINDOW_AT == graph_store._WINDOW_AT`, and it went red the moment the first copy moved.

**Without that pin this reader would have quietly kept answering a different question from the
store it mirrors.** A duplicated predicate with a pin is a duplication that announces itself.

### 3.3 · ⛔ My comment violated the no-clock doctrine, and the guard was not loosened

`test_doctrine_four_no_clock_in_this_module` scans the whole file — comments included — for clock
calls. **My explanation of the change contained one.**

The guard is right: a module whose whole job is replayability should not contain those tokens at
all, because a reader skimming for one must not have to decide which occurrences are prose. **The
comment was reworded; the test was not touched.**

### 3.4 · ⛔ The graph schema is duplicated across the test suite

Adding one column broke **8 test files**, each carrying its own hand-written `graph_facts` DDL.
A first, over-broad fix touched **38** files and produced **210 failures** — reverted immediately
and redone against the measured list of 8.

**Recorded, not fixed:** there is no guard that the test DDLs match the migrations, so every graph
column addition is an N-file change discovered by breakage. That is a real cost and it is not this
step's to pay.

---

## 4. Result

```
FULL SUITE   13,198 passed · 1,061 skipped · 152 xfailed · 14 failed
                                                          └── all 14 pre-existing
before L3-04: 13,186 passed · 14 failed
```

**+11 tests · 0 regressions · ⛔ migration 0184 · no model call.**

**Technique 3 — six mutations, all red:** revert the predicate; edges stop recording; edge
`valid_from` redefined; facts stop recording; backfill with write-time; backfill from `valid_from`.

## 5. What this step does NOT do

* **It does not repair existing rows.** They carry `NULL` and read exactly as they do today. ⛔ **An
  as-of read over pre-0184 edges is still wrong, and now it is wrong visibly rather than silently.**
* **It does not change `valid_to`.** That is stamped at close time on all three tables and was
  already knowledge time.
* **It does not touch `reason/moments`.** Those readers keep the meaning they had.
