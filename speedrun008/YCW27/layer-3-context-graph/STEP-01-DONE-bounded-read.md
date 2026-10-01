# Step 1 — ✅ DONE · the bounded query API

> **Tree:** `M10.C1`, units `U01`–`U02`

## What is true now

Two reads, both whole-tenant:

```python
GraphStore.read_graph(org_id, *, as_of)   # everything, at a moment
GraphStore.live_graph(org_id)             # everything, now
```

No seeds, no hop limit, no node cap, no visibility of the asking seat. `read_models.py` offers
`build_entity_360` and `private_facts_for` — fixed projections for one node, which answer a question
somebody already decided on. Useful; not the same thing.

## What must be true

A caller names what it is asking about and how far it will go, and gets that much — **with the
revision it read**, so [Step 2](STEP-02-compare-and-set.md) has something to guard against.

## The units

| Unit | What | The constraint |
|---|---|---|
| `U01` | the read request contract — seeds, allowed edge types, states, window, max hops, max nodes, unknowns, contradictions, the asking seat's visibility | ⛔ **bounded by default.** An unbounded default makes every caller's mistake invisible until the tenant is large |
| `U02` | the bounded reader — one capped traversal, returning `(view, revision)` | ⛔ it must report **truncation**, not silently stop. A result that hit its cap and does not say so is a partial answer that reads as a complete one — the same failure `coverage` exists to prevent one layer down |

## Scenario → expected result

| Scenario | Expected |
|---|---|
| a caller asks for one node, 2 hops, cap 60 | at most 60 nodes, and `truncated` says whether the cap bit |
| a caller passes no bound | the **default** bound applies — never "everything" |
| the traversal hits the cap | `truncated=True`, and the caller can tell that from "there was nothing more" |
| a seat with restricted visibility asks | it sees no more than its evidence allows |
| the same read runs twice with no writes between | the same revision comes back |

---

# ✅ DONE — 2026-09-30

## What was built

| Unit | Artifact | Result |
|---|---|---|
| `M10.C1.U01` | `genios_engine/context/bounded_read.py` · `ReadRequest` | ✅ bounded by default, frozen, refuses a seedless read |
| `M10.C1.U02` | same file · `expand` + `read_bounded` | ✅ capped breadth-first walk, reports truncation, carries the revision |

`context/` had exactly two graph reads and both returned the whole tenant:

```python
GraphStore.read_graph(org_id, *, as_of)   # the whole org, at a moment
GraphStore.live_graph(org_id)             # the whole org, now
```

This is the third, and it is the first one that can say no.

## Verify

```
$ .venv/bin/python -m pytest tests/context/test_the_bounded_read_says_when_it_stopped.py -q
......................                                                   [100%]
22 passed in 0.04s

$ .venv/bin/python -m pytest tests/context tests/test_layer_topology.py -q
2616 passed, 270 skipped in 19.19s
```

No regression, and the layer topology gate passes — the new module imports nothing upward.

## Scenario → what actually happened

| Scenario | Expected | Actual |
|---|---|---|
| a read with no seeds | refused | ✅ `ValueError: a bounded read starts somewhere` |
| defaults supplied by nobody | still bounded | ✅ 2 hops / 60 nodes |
| the walk runs out of graph | **complete**, not truncated | ✅ `complete is True`, `truncated_by is None` |
| the hop limit bites | truncated, and **says which** | ✅ `truncated_by == "max_hops"` |
| the node cap bites | truncated, and **says which** | ✅ `truncated_by == "max_nodes"` |
| a walk sitting exactly on the cap with nothing beyond | **complete** | ✅ a cap that fires on being touched would make every caller widen bounds it never hit |
| a cycle | terminates | ✅ |
| more seeds than the cap | truncation before hop 1, reported | ✅ |
| a capped walk | never returns an edge to a node it withheld | ✅ **and this one failed first — see below** |
| the revision is unknown | `None`, never `0` | ✅ zero is a revision; `None` is "the store could not say" |

## ⛔ The test found a real defect, and the code was fixed rather than the test

`test_a_capped_walk_never_returns_an_edge_to_a_node_it_withheld` failed on the first run:

```
AssertionError: assert 'd' in {'a', 'b', 'c'}
```

The first version appended the edge **before** checking the node cap. So when the cap bit, the view
came back holding an edge `a → d` while refusing to contain `d`. That is worse than a smaller view:
the caller joins on the edge, finds nothing, and reads that absence as a fact about the business —
the same failure mode `coverage` exists to prevent one layer down.

Fixed by deciding admission first and keeping the edge only once both ends are in the view. The
docstring at the break now records why.

## Design decisions worth knowing

**⛔ Truncation is reported, never silent.** `truncated`, `truncated_by` and `hops_walked` are the
difference between *"there is nothing more"* and *"we stopped looking"*. A caller that cannot tell
them apart will eventually claim the first. `complete` and `truncated` are asserted to never both be
true.

**Breadth-first, deliberately.** When a cap bites, what survives should be the nodes **nearest** the
thing asked about. Depth-first under the same cap returns one long thread and calls it a
neighbourhood.

**One query per node, not a recursive CTE.** The CTE would be fewer round trips and would make the
cap a `limit` the traversal cannot explain — a truncated result with no way to name which bound
stopped it. The walk is capped at `max_nodes` queries by construction, so the round trips are bounded
anyway.

**Split for testability without Postgres.** `expand` takes a `neighbours` callable; `read_bounded`
wires the SQL one. The rule being enforced is a counting rule, and a test of a counting rule should
not need a database to prove the count. All 22 tests run with no database.

**The revision comes back with the view**, so a read-modify-write can guard against it.

## For Rohit — what you have to do

Nothing. No migration, no config, no deploy. This adds a read that did not exist; it changes no
existing read, so nothing in production behaves differently today.

## For Harsh — the one thing to know

`bounded_read.read_bounded` exists and has **no callers yet**. That is on purpose — Step 4 is its
first one. When you next touch a correlator that calls `live_graph(org_id)` and then filters in
Python, this is the replacement, and it will tell you when it truncated.


---

## ⛔ 2026-10-01 · the title line of this file was stale, and is corrected above

This file's **first line** read `Step 1 — TO BUILD · the bounded query API` while the `✅ DONE — 2026-09-30` section below recorded the
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
