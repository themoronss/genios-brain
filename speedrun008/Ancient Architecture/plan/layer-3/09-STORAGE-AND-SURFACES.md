# Where both graphs live, and what appears where

**2026-09-25** · read from `context/graph_store.py`, `requirements.txt`, `api/routes.py`

---

# PART 1 · Your hypothesis is right

> *"sirf evidence graph hi dikhega, and intelligence reasoned hoke saved rahega, phir zaroorat pe
> card banke aa jayega"*

**Correct — with one addition: the node side-panel.**

| surface | Evidence | Intelligence |
|---|---|---|
| **the graph canvas** (`GET /graph`) | ✅ **only this** | ⛔ **never** |
| **node side-panel** (`GET /graph/node/{id}`) | ✅ its facts, with receipts | ✅ **a summary line** — *"3 situations · 2 decisions · 1 ignored"* |
| **the card** | ✅ the *Why*, with receipts | ✅ **one line** — *"3rd time · dismissed Tuesday"* |
| **a situation timeline** (on demand) | the facts it was built from | ✅ **the full chain** |
| **`/decisions/{id}/explain`** | which facts were cited | ✅ the walk |

## 1.1 · Why Intelligence must stay off the canvas

**1 · The shapes do not lay out together.** The Evidence Graph is a **web** — many-to-many, no
direction, no time. The Intelligence Graph is a **chain in time**. A force-directed layout that
tries to hold both puts a decision node between two people and the result reads as nonsense.

**2 · The canvas is where a user goes to understand *the world*.** Putting our own conclusions on it
blurs fact and guess at exactly the place that must stay clean. Same reason it never sits beside
evidence on a card.

**3 · It is not needed there.** What a user actually wants at a node is *"what have we said about
Acme, and did it work"* — **a summary, not nodes on a canvas.** The side-panel endpoint already
exists and is already node-scoped.

## 1.2 · So the flow is exactly as you described

```
   Evidence Graph  ─────►  visible, explorable, the network view
        │
        ▼  correlate
   BusinessSituation
        │
        ▼  reason
   Intelligence Graph ────►  ⛔ SAVED, not drawn
        │
        ├──► one line on the card         "3rd time · dismissed Tuesday"
        ├──► summary in the side-panel    "3 situations · 2 decisions · 1 ignored"
        └──► full chain only on demand    the timeline / explain view
```

**It works in the background and surfaces as a sentence.**

---

# PART 2 · Where they are stored

## 2.1 · ⛔ There is no graph database. Both are Postgres tables.

Checked against `requirements.txt`: **no Neo4j, no Neptune, no ArangoDB, no JanusGraph, no
TigerGraph, not even networkx.**

```
SQLAlchemy 2.0.51
psycopg[binary] 3.3.4     # postgresql+psycopg://  — Supabase
```

**"Graph" is a shape here, not a technology.** `graph_edges` carries `from_node_id` and
`to_node_id`; a traversal is a JOIN.

And they share **one engine**, not two:

```python
class GraphStore:
    def __init__(self, database_url=None, *, engine=None):
        self._engine = engine if engine is not None else get_engine(database_url)
```

### Why that is the right call

| a separate graph DB would mean | |
|---|---|
| two stores, two transactions | a situation could commit while its facts did not |
| no foreign keys to `orgs` | ⛔ and `on delete cascade` is how **account erasure** is proven |
| a second thing to operate | for a traversal depth that a JOIN already handles |

`test_every_org_scoped_table_has_a_proven_account_delete_cascade` **refused migration 0183** until
it carried `references orgs (id) on delete cascade`. A graph living outside Postgres could not
satisfy that test at all.

## 2.2 · ⛔ How they are written: SOFT DELETE ONLY

> *"An edge, fact or node is **closed** by setting `valid_to`; a hard `DELETE` makes every earlier
> read silently change its answer and there is no way to recover it.
> `tests/context/test_point_in_time.py` scans `context/` for `delete from graph_*` and **fails on
> one**."*

**A rule with a test behind it, not a convention.**

The four `delete` statements that do exist are all on tables that hold no history:

| | table | why it is allowed |
|---|---|---|
| `health.py` | `graph_health` | a recomputed score, not a record |
| `identity.py` | `graph_aliases` | an alias moves when a merge is accepted |
| `derived_provenance.py` | `graph_source_refs` | a derived fact's provenance is rewritten, not versioned |
| `graph_store.py` | `graph_change_outbox` | a drained outbox — and ⛔ **a bounded batch**: *"an unbounded DELETE on a long untouched table would be an unbounded transaction on the path that ingests mail"* |

**`graph_nodes`, `graph_facts` and `graph_edges` are never deleted. Not once, anywhere.**

## 2.3 · And numbers are stored as integers, deliberately

`confidence numeric(4,3)` is read back through `Decimal`, never `float`:

> *"`float(...)` on it is how a 0.85 confidence becomes `0.8500000000000001` in one row and `0.85`
> in another, and two reads of the same graph then compare unequal — which would make the
> live/as-of equivalence property untestable."*

## 2.4 · Both halves, same database, same rules

| | **Evidence** | **Intelligence** |
|---|---|---|
| **where** | Postgres / Supabase | ⛔ **the same database, the same schema** |
| **tables** | 10 | 4 today, 2 to add |
| **engine** | one shared SQLAlchemy engine | the same one |
| **deletion** | soft only — `valid_to` | the same rule |
| **erasure** | `on delete cascade` → `orgs` | ⛔ **0183 already has it** |
| **traversal** | a JOIN on `from_node_id`/`to_node_id` | the same |

---

# PART 3 · ⛔ Size — and this is the part that surprises

They grow at completely different rates.

| | **Evidence Graph** | **Intelligence Graph** |
|---|---|---|
| **grows with** | **every message, meeting and document** | **every CHANGED conclusion** |
| **per email** | 1–3 nodes, 2–6 facts, 1+ edges, **a source_ref per claim** | 0 |
| **on a quiet day** | still writes — every mail is an event | ⛔ **writes nothing.** `noop` on an unchanged slice |
| **a repeated conclusion** | `noop` still writes a **corroboration ref** | `noop` — **nothing at all** |
| **rough ratio** | thousands of rows per active tenant per week | **tens** |

⛔ **The Intelligence Graph is the cheap one.** Its unique key is
`(org_id, situation_id, slice_digest)` — *"two sweeps over an unchanged slice must resolve to one
row rather than paying twice."* **A tenant whose world did not move writes nothing.**

That is the opposite of what the 995 MB incident was: a derived content address that **churned
every sweep** and put 4,086 rows and 67% of a tenant's database on one table. **The slice digest is
the exact defence against that** — it changes when the facts change, and only then.

---

# PART 4 · The whole picture

```
                        ONE POSTGRES DATABASE  (Supabase)
  ┌──────────────────────────────────────────────────────────────────────┐
  │                                                                      │
  │   EVIDENCE GRAPH  (10 tables)        INTELLIGENCE GRAPH  (4 + 2)     │
  │   ┌────────────────────────┐         ┌───────────────────────────┐   │
  │   │ graph_nodes            │         │ context_situations        │   │
  │   │ graph_facts            │◄────────┤   anchor_node_id          │   │
  │   │ graph_edges            │  seam 1 │ situation_interpretations │   │
  │   │ graph_observations     │         │ execution_outcomes        │   │
  │   │ graph_source_refs      │◄────────┤ reasoning_evidence_id_map │   │
  │   │ graph_versions         │  seam 2 │ ⛔ + intel_nodes          │   │
  │   │ graph_aliases          │         │ ⛔ + intel_edges          │   │
  │   │ graph_segments         │         └───────────────────────────┘   │
  │   │ graph_health           │                                         │
  │   │ graph_change_outbox    │          soft delete · cascade to orgs  │
  │   └────────────────────────┘          one engine · one transaction   │
  └──────────────────────────────────────────────────────────────────────┘
            │                                        │
            ▼                                        ▼
      GET /graph                            ⛔ never on the canvas
      the network view                         ├─ one line on the card
      (seat-filtered)                          ├─ summary in the side-panel
                                               └─ full chain on demand
```

**Two tables to add. Both seams already exist. Same database, same rules, and the cheaper half is
the one that is missing.**
