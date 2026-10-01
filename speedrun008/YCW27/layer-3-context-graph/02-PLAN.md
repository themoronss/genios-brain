# L3 · the plan — sections → functions → components → units

`context/` — 118 files, 49,713 lines. The largest package in the product.

**Written for:** Harsh (CTO) and Rohit. Every section answers the same six questions, in order:
*what was expected · what is actually true · how we do it · why that way · what the outcome is ·
how it is verified.*

---

## ⛔ Read this before anything else: this plan was written LATE

Layer 1 was done properly: `01-CROSSCHECK.md` → **`02-PLAN.md`** → step specs → build. Layer 3 was
not. I went cross-check → step specs → build and **skipped this document.** That is a process
failure, and it is mine.

So this file is a **plan of record**, not a forecast, and it is marked honestly throughout:

| Marker | Meaning |
|---|---|
| **[planned]** | decided in `01-CROSSCHECK.md` BEFORE any code was written |
| **[learned]** | the codebase or a test corrected the plan DURING the build |
| **[open]** | still not decided; nobody has settled it |

A retro-written plan that pretends to be a forecast is worse than no plan, because it hides exactly
the places where the build taught us something. Three of the eight functions below carry a
**[learned]** correction, and two of those changed the design materially.

---

## ⛔ Correction to `01-CROSSCHECK.md` §2

The cross-check claimed the graph-revision compare-and-set was missing. **It is not.** It exists in
`reason/runner.py:570` (`_graph_version_guard`), is honoured by the caller at line 1276, is taken as
a lock at 12 further sites in `deliver/` and `api/`, and is covered by 6 passing tests.

I found the gap by grepping `context/` for the guard. The read-modify-write **spans packages by
design** — `context/` writes the graph and bumps the counter, `reason/` reads the counter and guards
against it — so `context/` is the one place the guard could not be.

> **A guard lives with the reader, not with the writer. Absence in the writer's package is not
> absence.**

This is the second wrong finding in this programme from counting along the wrong dimension. The first
was Layer 1's `no_model_wired`, which produced *"a count without its dimension is not a
measurement."*

`S1.F1.3` below is therefore **retired, not deferred.** Full retraction in
[`STEP-02-WITHDRAWN-compare-and-set.md`](STEP-02-WITHDRAWN-compare-and-set.md).

---

## The shape

Four sections, eight functions, ten units. One section is not ours.

| | Section | Functions | Units | Ours? |
|---|---|---|---|---|
| **S1** | The bounded read | 3 (one retired) | 2 + 1 retired | ✅ |
| **S2** | The hold that asks | 2 | 2 | ✅ |
| **S3** | The loop closes | 2 | 2 | ✅ |
| **S4** | The queue is written, and read | 2 | 3 | ✅ |
| **S5** | Operational — not ours | — | 2 | ❌ Harsh |

### Why these four and in this order

They are one chain, and each link is useless without the one before it:

```
a bounded question  ──▶  a hold that names what it lacks  ──▶  an answer that frees it
       S1                            S2                              S3
                                      └──────────▶ somewhere to put it ◀──────────┘
                                                        S4
```

S4 is last because it is the only one that touches a running sweep. Building it first would have put
a write into production before anything produced a correct value to write.

---
---

# S1 · The bounded read

## What was expected  **[planned]**

That `context/` could be asked a question about a few nodes.

## What is actually true

It cannot. There are exactly two graph reads and **both return the whole tenant**:

```python
GraphStore.read_graph(org_id, *, as_of)   # the whole org, at a moment
GraphStore.live_graph(org_id)             # the whole org, now
```

No seeds, no hop limit, no node cap. A caller wanting three nodes gets everything and filters in
Python.

## Why it matters, and why now

Survivable at 66 situations and **the wrong shape at any size.** The specific danger is who pays:
`reason/` reads through this, so the cost lands on the layer that can least afford it — the one with
a per-sweep budget and a model in the loop.

## Why it is not a `limit` clause

⛔ Because a `limit` cannot explain itself. A truncated result with no way to name which bound stopped
it is a partial answer that reads as a complete one — the same failure `coverage` exists to prevent
one layer down: *an empty result over an unmeasured slice, reported as a fact about the business.*

### F1.1 · The read request  **[planned]**

**How:** a frozen `ReadRequest` carrying seeds, allowed edge types, max hops, max nodes and the
asking seat's visibility.

**Why bounded by default:** an unbounded default makes every caller's mistake invisible until the
tenant is large — which is the point at which it is hardest to fix. Defaults are 2 hops / 60 nodes.
Two hops because the useful question is almost always *"this thing and what it touches"*, and a third
hop on a well-connected node is most of the tenant.

**Why visibility rides on the request:** a filter applied afterwards has already read the rows it is
meant to withhold.

| Unit | Artifact | Verify |
|---|---|---|
| `M10.C1.U01` | `genios_engine/context/bounded_read.py` | `uv run --no-sync pytest tests/context/test_the_bounded_read_says_when_it_stopped.py -q` |

**Outcome:** a seedless read is refused with `ValueError: a bounded read starts somewhere`. A caller
that could widen its own bounds mid-walk has no bounds, so the request is frozen.

### F1.2 · The bounded reader  **[planned]**

**How:** breadth-first from the seeds, stopping at whichever cap bites first, returning
`(node_ids, edges, revision, truncated, truncated_by, hops_walked)`.

**Why breadth-first:** when a cap bites, what survives should be the nodes **nearest** the thing
asked about. Depth-first under the same cap returns one long thread and calls it a neighbourhood.

**Why one query per node instead of a recursive CTE:** the CTE is fewer round trips and makes the cap
a `limit` the traversal cannot explain. The walk is capped at `max_nodes` queries by construction, so
the round trips are bounded anyway.

**Why the revision comes back:** a read that did not say which revision it saw cannot be the basis of
a compare-and-set, and every read here is a candidate basis for one.

**Why `expand` is split from `read_bounded`:** the rule being enforced is a counting rule, and a test
of a counting rule should not need Postgres to prove the count. All 22 tests run with no database.

| Unit | Artifact | Verify |
|---|---|---|
| `M10.C1.U02` | `genios_engine/context/bounded_read.py` | same command |

**Outcome — the distinction this whole section exists for:**

| | |
|---|---|
| ran out of graph | `complete is True`, `truncated_by is None` |
| a cap bit | `truncated is True`, `truncated_by` names which |
| sat exactly on the cap with nothing beyond | `complete is True` — a cap that fires on being touched would make every caller widen bounds it never hit |

### F1.3 · Compare-and-set  **[learned — RETIRED]**

Already built. See the correction at the top of this file.

| Unit | Status |
|---|---|
| `M10.C1.U03` | ⛔ **retired**, not deferred. `reason/runner.py:570` is it |

---
---

# S2 · The hold that asks

## What was expected  **[planned]**

That a held situation would go and get what it was missing.

## What is actually true

It waits. `situation_publisher` HOLDs a candidate, writes the reason to a ledger, and that is where
it ends. Measured on the pilot: **467 held against 223 admitted.** Every one of those holds is a
question nobody asked.

| Hold reason | Count |
|---|---|
| `verified_evidence_required` | 398 |
| `qes_required` | 398 |
| `source_coverage_insufficient` | 69 |

*(Counts are from the cross-check pass. `situation_bso`'s own comments record an earlier, differently
scoped measurement — 504 held vs 28 admitted, 480 carrying both — taken on 2026-09-16. Both are
quoted with their source rather than blended, because they count different populations.)*

### F2.1 · Which holds are evidence questions  **[planned, then corrected]**

**How:** a closed `NEED_WORTHY_HOLDS` set. Three of the seven hold reasons.

**⛔ Why the EXCLUSION is the design, not the inclusion:**

| Excluded | Why fetching cannot help |
|---|---|
| `conflict_open` | two incompatible facts are BOTH held. Fetching adds a **third** fact to a disagreement between two; an authority ruling resolves it |
| `cross_domain_contradiction` | the same shape one layer up. Neither domain is short of evidence |
| `identity_review_required` | *"are these two people the same person"* is a judgement about records we already hold |
| `pattern_evidence_required` | ⛔ **the pattern library lacks a rule.** That is OUR gap, not the tenant's — their documents cannot supply our rule |

The last one is the sharpest: a need for it would close **successfully every time** while the
situation stayed held, teaching the system that its questions are always answered. **That is worse
than not asking.** Same rule Layer 1's residue wire is built on.

**⛔ [learned] · THREE REASONS, TWO QUESTIONS.** The plan said three needs. The codebase had already
measured otherwise and written it down — `situation_bso.py:1004`:

> `_preflight` raises `verified_evidence_required` on a missing span AND `qes_required` when
> `importance_source` is not `l1_qualified_signals` — and on the pilot all 349 held candidates carry
> both, which reads like two independent defects. **It is one:** both are downstream of `l1` being
> `None`... **Feeding the bundle clears both.**

And at line 570: *"`qes_required` and `verified_evidence_required` are the SAME cards rather than two
gaps."*

So the pair collapses into one need. Two needs for the 480 holds carrying both would have put **960
rows in the queue for 480 questions**, had Layer 1 fetch twice for one answer, and charged the tenant
twice — breaking *one question, one fetch, one charge* at the one seam where the duplication is
**measured** rather than hypothetical.

**Why a separate module and not inside `situation_publisher`:** publication must not grow a second
responsibility, and this is a pure mapping over a held candidate — testable without the publisher's
eight admission laws.

**Why it never calls `capture/`:** a publication pass that fetched inline would make admission wait on
a network. The need is a row; the executor is a separate pass. `docs/LAYER_MAP.md` records the rule,
and a test asserts the string `genios_engine.capture` does not appear in the module.

| Unit | Artifact | Verify |
|---|---|---|
| `M10.C2.U04` | `genios_engine/context/hold_needs.py` | `uv run --no-sync pytest tests/context/test_a_hold_asks_for_what_would_free_it.py -q` |

### F2.2 · The subject the executor can act on  **[learned]**

**Why this function exists at all:** it was not in the plan. A need must name something Layer 1 can
**fetch**, and a need whose subject `plan_fetch` returns `None` for closes immediately as *"no Layer 1
fetch answers this"* — a question filed and abandoned in the same pass.

**How — and the order is a cost order:**

```
chunk:<doc_id>:<n>   →  document:<doc_id>   →  REEXTRACT        (cheaper, targeted)
(otherwise)          →  signal:<signal_id>  →  BACKFILL_WINDOW
(neither)            →  refuse to file
```

**⛔ Why `prepared_content:<event_id>` is NOT mapped to `thread:`:** an event id is not a thread id.
Inventing that mapping would file a need whose fetch names a thread that does not exist — a need that
can never be met and never honestly closed.

**Why the refuse-to-file branch stays even though `SituationCandidate` makes it unreachable:** the
constructor demands ≥1 signal and ≥1 evidence, so a real candidate always has a subject. But
`situation_bso.l1_refusal` names the split — *"the importance sweep passes dataclass-ish rows; the
PUBLISH path passes SQLAlchemy `RowMapping`s"* — so it IS reachable through a row. The guard stays
and its test enters through the door that is actually open.

**Verify:** `test_layer_one_can_plan_a_fetch_for_every_need_filed` imports `capture`'s own
`plan_fetch` and asserts a real fetch kind for every subject this module can produce.

---
---

# S3 · The loop closes

## What was expected  **[planned]**

*"`unavailable` must not look like `met`."*

## What is actually true  **[learned]**

True, and **only half of it.** The distinction is three-way, and both easy mistakes collapse a
different pair:

| Collapse | What it costs |
|---|---|
| `unavailable` read as `met` | the card claims evidence it never got |
| `unavailable` read as `open` | the situation waits forever for a document that does not exist |

### F3.1 · The disposition  **[planned, widened]**

**How:** four dispositions, not two.

| Need states | Disposition | Why |
|---|---|---|
| no needs at all | `no_evidence_question` | four of seven hold reasons raise none. This hold waits on a **ruling** — calling it "waiting" implies a pending fetch that does not exist |
| any still open | `keep_waiting` | re-running admission would spend a sweep re-deriving the same reason |
| all closed, ≥1 met | `retry` | new evidence exists; admission may ADMIT, or hold on a **new** reason — progress either way |
| all closed, none met | `give_up` | ⛔ stop waiting, **and say why** |

**⛔ Why `open` is checked BEFORE `met`:** a situation with one met need and one still open has not got
everything it asked for. Retrying now re-derives the same hold while the outstanding question is still
in flight.

**⛔ Why a partial arrival carries its missing half:** when one need was met and another came back
unavailable, the disposition is `retry` **and the unavailable reasons travel with it**. Dropping them
would let the retry read as *"we have everything now"* — the `not_carried` defect, a value computed at
one boundary and silently lost at the next. `explain()` says
`retrying with X; still missing: Y`.

**Why it decides and does not write:** there is then no read-modify-write here to guard. A test
asserts the module imports no database and no clock.

| Unit | Artifact | Verify |
|---|---|---|
| `M10.C2.U05` | `genios_engine/context/hold_resolution.py` | `uv run --no-sync pytest tests/context/test_a_met_need_clears_its_hold.py -q` |

### F3.2 · Expiry, and replayability  **[learned]**

**Why this function exists:** it was not in the plan, and it is a **permanent-hold bug**.

A need past `expires_at` will never be met — but if the executor has not run, its row still says
`open`. Counting that as waiting is exactly how a hold becomes permanent: the situation waits on a
question nobody will answer, forever, and no surface says so.

**How:** expiry is evaluated here too, at the same `<=` boundary the executor uses. Two different
answers at the same instant would let a need be fetched by one path and refused by the other.

**Why expiry governs the question, not the answer:** a `met` need that has since expired is still met.
An answer that arrived in time does not stop being an answer.

**⛔ Why `eval_time` has no default:** a default would be `now()` at the one seam where replayability
matters. The same hold and the same needs must produce the same disposition when replayed, or a
decision cannot be audited after the fact. `resolve_hold([need])` raises `TypeError` — and a test
asserts that.

---
---

# S4 · The queue is written, and read

## What was expected  **[planned]**

That the residue → need conversion built in Layer 1 was being called.

## What is actually true

Three pieces existed and **did not touch**:

| Piece | State |
|---|---|
| `context/residue.py` `detect_residue` | ✅ shipped, measuring every sweep |
| `context/evidence_needs.py` `needs_from_residue` | ✅ built in L1, tested, green |
| `capture/acquire/evidence_need.py` `execute` | ✅ built, tested, green |
| **anything that wrote a need to the table** | ❌ **nothing** |

So the executor read an empty table. Built, tested, green, and called by nothing — the **sixth**
instance of that shape this programme has found, and the first one it created itself.

### F4.1 · The store  **[learned]**

**⛔ The whole design of this function is one SQL verb: `on conflict do nothing`, never `do update`.**

Residue is re-derived every sweep — that is what *"unexplained as of the last sweep"* means — and a
re-derived need is born `open`. An upsert that UPDATED would reset every closed need back to `open`
on the very next sweep. In order of how bad it gets:

1. A question answered *"the document does not exist"* would be re-asked **forever**.
2. The executor would re-fetch and **re-charge** each time.
3. ⛔ The system would learn that **its questions are always eventually answered**, because every
   closed need would keep reopening and closing.

Point 3 is the exact failure `evidence_needs.py` excludes three of four residue kinds to avoid —
undone by one verb.

**Why `close_need` guards with a predicate, not a lock:** `where need_id = :id and state = 'open'`.
One statement, no read-modify-write, so two concurrent executor passes cannot both win. A `False`
return means another pass settled it first and **its answer stands** — overwriting would reset
`closed_at` and lose when the question was actually settled. ⛔ That `False` must not be retried as an
error.

**This is where the withdrawn S1.F1.3 actually landed** — and it is smaller and better shaped than the
generic guard I was going to build.

**Why the returned count is NEW rows, not rows offered:** a count of needs derived would report the
same number every sweep and read as activity. `0` must mean *"nothing new to ask"*.

| Unit | Artifact | Verify |
|---|---|---|
| *(added)* `M10.C2.U06` | `genios_engine/context/evidence_need_store.py` | `uv run --no-sync pytest tests/context/test_residue_reaches_the_sweep.py -q` |

### F4.2 · The wire into the sweep  **[planned]**

**How:** in `context/runner.py` `process_pending`, immediately after `detect_residue`.

**Why immediately after:** the questions come from the measurement. Filing before detecting would
file last sweep's residue every time. A test asserts the source order.

**Why inside `try/except`:** a sweep that could not file its questions has lost a cycle of visibility.
A sweep that **died trying** has lost the tenant's mail. Same trade `detect_residue` makes one call
earlier.

**Why the trace id is derived, not minted:** `process_pending`'s own docstring promises the same graph
at the same `eval_time` replays identically. A fresh `new_id("trace")` would be the one field in the
row a replay could not reproduce, so it is `stable_id("trace", {org, sweep_at})`.

**Why the count is returned:** `evidence_needs_filed` in the sweep result. This programme has found
the `not_carried` shape six times — a value computed correctly and dropped at the boundary. **The wire
is not done until the number is reported.**

---
---

# S5 · Operational — tracked, not ours

| | Owner | Blocks the build? |
|---|---|---|
| apply `migrations/0187_evidence_needs.sql` — never run in production | Harsh | ❌ no. The filing pass logs and files nothing |
| the executor pass: `read_open_needs` → `execute` → `close_need`, with **real connector `fetchers`** | Harsh | ❌ no — inherited from L1, not a new gap |

---
---

## Two unsound verifies, named before anyone trusts them

1. **`tests/context/test_bounded_read.py` and `test_compare_and_set.py` never existed.** `tree.yaml`
   named both. They have been corrected to the tests that do exist, and all five M10 verify commands
   were run and exit 0. ✅ fixed.
2. **`tests/platform/test_migrations_apply.py` does not exist** and is still named by three units in
   `03-PROGRAM.md`. ⛔ **[open]** — so `0187` has no automated proof it applies. This is why S5 is
   Harsh's and not ours to tick off.

---

## Order, and why

```
S1.F1.1 ─▶ S1.F1.2        (a contract before its reader)
S2.F2.1 ─▶ S2.F2.2        (which holds, before what to name)
S3.F3.1 ─▶ S3.F3.2        (the dispositions, before the clock edge)
S4.F4.1 ─▶ S4.F4.2        (a store before anything calls it)
```

S4 last, deliberately: it is the only section that adds a write to a running sweep, and nothing should
write to production before something produces a correct value to write.

---

## ⛔ What we are deliberately NOT doing in L3

| Not doing | Why |
|---|---|
| refactoring `_graph_version_guard` to be shared | it works, it is tested, and it is not what was asked for. Noticing something adjacent makes a new unit, not a silent edit |
| replacing `live_graph` calls in the ten correlators | 5,234 lines, all currently correct. The bounded read is the replacement **when someone touches one**, not a sweep-wide rewrite nobody asked for |
| wiring `hold_needs` into `situation_publisher` | it needs a decision that is not mine: file inside the publication transaction, or a later pass reads the ledger. **The second is safer** — publication must not wait on anything — but it is Rohit's or Harsh's call |
| building the executor pass | needs real connector `fetchers`. Building it with stubs would produce a pass that closes every need successfully and teaches the system its questions are always answered |
| resolving the ConfidenceVector axes | ⛔ **[open]** and it belongs to L2, which is the layer that computes it. It is the first thing M11's cross-check will hit |

---

## ⛔ The one thing to carry out of this layer

**The loop is half-closed.**

```
residue ──▶ need ──▶ [ evidence_needs table ] ──▶  ???
   ✅         ✅            ✅ written             ❌ nothing works them
```

The queue is **write-only** today. Every filed need stays `open`, so `resolve_hold` returns
`keep_waiting` for all of them. Nothing regresses — situations hold today anyway — but
**`evidence_needs_filed > 0` must not be read as "something is being fetched."**
