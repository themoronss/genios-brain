# Graph health — is our picture of the enterprise still trustworthy?

*`context/health.py` · `graph_health` · `GET /api/org/{org}/graph/health`*

> Steps 1–3 of Layer 2 **build** the graph. Nothing until this **kept** it.
>
> A graph that is only ever written to accumulates broken edges, orphan entities, facts nobody
> can trace and duplicates nobody resolved — and **none of that announces itself.** It surfaces
> as reasoning that is subtly wrong for reasons no one can locate.

---

## §1 · The eight integrity checks

Every one targets a way **this** graph actually breaks, not a textbook one. Each is read-only.

| Check | What it means | What causes it here |
|---|---|---|
| `broken_edge` | an edge whose other end does not exist or is closed | a merge that missed a table — traversal silently incomplete |
| `self_edge` | `Acme corresponded_with Acme` | a merge that repointed both ends of one edge |
| `orphan_fact` | a fact about an entity that no longer exists | unreadable, but still counted in every metric |
| `duplicate_active_fact` | two active values for one `(entity, field)` | readers take `limit 1` — "the truth" becomes whichever row the planner returns |
| `fact_without_evidence` | a fact with no source ref | violates the law that nothing is true just because it is written down |
| `orphan_node` | an entity with no facts, edges or observations | the "dead dots" the P1 anchor rule exists to prevent |
| `alias_to_closed_node` | a lookup key pointing at a closed entity | mentions resolve to something that is gone |
| `correlation_on_closed_node` | a situation anchored on a closed entity | describes something that no longer exists |

`check_integrity` returns **all eight**, clean ones included, so a caller can see what *was*
verified rather than only what failed. The health report lists only the non-zero ones.

---

## §2 · Nothing repairs itself

Every check begins with `select`. Enforced by
`test_graph_health.py::test_integrity_checks_never_repair`, which asserts no check contains
`update`, `delete` or `insert`.

> An auto-fix that runs unattended turns a small inconsistency into a **large, silent data
> loss**: it runs at 3am, deletes the rows it decided were wrong, and nobody finds out until a
> decision cannot be explained.

Detect, report, let a human choose. The same instinct as entity resolution proposing rather than
merging.

---

## §3 · The health vector

Seven dimensions, each 0–100, each derived from a defect **ratio**:

| Dimension | Numerator | Denominator |
|---|---|---|
| `integrity` | broken edges + self edges | total edges |
| `evidence` | facts without evidence | total facts |
| `coherence` | duplicate active + orphan facts | total facts |
| `connectivity` | orphan nodes | total nodes |
| `identity` | open merge proposals | total nodes |
| `consistency` | open discrepancies | total nodes |
| `correlation_reach` | knowledge-bearing events in no situation | events that produced facts |

```python
overall = min(dimension for dimension in dimensions if measured[dimension])
```

### Why minimum, not average

Same rule as situation confidence, for the same reason. A graph with flawless evidence and 40%
broken edges is **not "70% healthy"** — it is a graph you cannot traverse. Averaging lets the
parts that work conceal the part that does not.

### Why an empty graph scores 100, not 0

```python
def _ratio_score(*, bad, total):
    if total <= 0:
        return 100, False        # "nothing measured" — never "0% healthy"
```

A new tenant has not failed anything. **A health page that calls fresh accounts broken is a
health page nobody reads.** Dimensions with nothing behind them are excluded from the minimum
and marked `measured: false` — the same absence-is-not-negative-evidence law that runs through
the whole layer.

---

## §4 · `correlation_reach` — the single best alarm

If you watch one number after go-live, watch this one. It is the fraction of
**knowledge-bearing** events that reached a situation, and a fall means Layer 2 has quietly
stopped working.

The denominator matters, and getting it wrong was a real bug caught in review:

| | Denominator | Result on a healthy tenant |
|---|---|---|
| ❌ first version | **every** emitted event | 1000 events, 100 with facts, all correlated → **10%** |
| ✅ now | events that **produced facts** | same tenant → **100%** |

A newsletter correctly reaches no situation. Measuring against every event would make normal
marketing volume look like a broken engine — and **an alarm that fires on healthy systems is an
alarm people switch off.**

```sql
events_with_facts_uncorrelated
  = emitted events
    that have at least one graph_fact created_by_event_id = them
    and no row in context_correlation_members
```

---

## §5 · Node lifecycle — a label, never a filter

`refresh_node_lifecycle` writes `context_node_lifecycle`: `active` | `dormant` | `archived`,
from each entity's most recent evidence.

| Threshold | Value | Why not the situation window |
|---|---|---|
| dormant after | **90 days** | a conversation ending is normal; a **relationship** ending takes far longer |
| archived after | **365 days** | |

Situations go dormant at 45 days. Using one threshold for both would archive customers who are
merely between deals.

### The constitutional rule

> **A dormant entity is still evaluated. Every sweep. Always.**

This is the third appearance of the never-gates law in Layer 2, and the most dangerous, because
lifecycle is a **state** rather than a score — it looks authoritative.

If dormancy narrowed evaluation: a quiet entity produces no signals → stays quiet → stays
dormant. **The customer who went silent — exactly the one worth noticing — is the one the system
would go permanently blind to**, with nothing in the logs.

`test_graph_health.py::test_lifecycle_never_gates_evaluation` fails if anything under `reason/`
so much as mentions the table.

### Unknown is not old

```python
if last_evidence_at is None:
    return LIFECYCLE_ACTIVE
```

An entity with no dated evidence is not stale — we cannot tell. Guessing "old" would retire
every entity the moment a source stopped sending timestamps.

The SQL uses `'epoch'` as a floor for `greatest(...)`, and the Python explicitly converts it
back to `None` (`if last.year <= 1970`). Passing the sentinel through as a real timestamp would
archive exactly the entities this rule protects.

---

## §6 · Nothing is deleted — pruning is archival

The Atlas asks for a Pruning Engine so the graph "never grows forever". This implements pruning
as **archival**, and that is a deliberate disagreement.

Volume is already controlled at Layer 1, where the gate drops noise **before** it becomes an
entity. Anything in the graph has passed that bar — deleting it later destroys evidence someone
may need to explain a decision the system already made.

> **An old customer is a dormant relationship, not a mistake to erase.**

`test_nothing_in_maintenance_deletes_graph_data` asserts `health.py` contains no
`delete from graph_nodes/facts/edges/observations` and no `drop table`.

The one thing that *is* purged: `graph_health` history itself, after 180 days
(`purge_old_health`). Append-only with no clock becomes the largest table in the database.

---

## §7 · When it runs, and why not per event

On the **scheduler sweep** (`api/routes.py:run_maintenance_sweep`), hourly-scale, per org.

Both passes are `O(graph)`, not `O(event)`: 8 integrity checks + 9 metric queries = 17
full-table scans. Running that per event would make every email pay for a whole-tenant scan.

The sweep logs a warning for any org scoring below 80, and one org's failure never stops the
others.

Lifecycle writes are batched (`_WRITE_BATCH = 500`, `executemany`). A row-at-a-time loop is one
network round trip per entity — on a 50,000-entity tenant that is 50,000 round trips inside one
transaction, which is how a maintenance pass becomes an outage. The **rule** stays in Python so
there is one tested definition, not a second copy in SQL that can drift.

---

## §8 · Reading the output

```
GET /api/org/{org}/graph/health           ← now, not persisted
GET /api/org/{org}/graph/health/history   ← the trend
```

The trend is the point. One number says little; **the same number falling over three weeks says
a connector broke, a merge went wrong, or correlation stopped reaching anything.**

| If this is low | Look at |
|---|---|
| `correlation_reach` | [Anchoring](../03-Cross-Correlation-Engine/01-Anchoring.md) — are events anchoring at all? |
| `identity` | the merge-proposal queue — unreviewed duplicates are a measurable defect |
| `evidence` | should be 100; anything else means facts are being written without receipts |
| `integrity` | a merge missed a table |
| `connectivity` | orphan entities — the anchor rule is leaking |

---

*Related: [Confidence Vector](01-Confidence-Vector.md) · [Conflict Detection](03-Conflict-Detection.md) · [Merge and Reverse](../02-Graph-Engine/02-Merge-and-Reverse.md)*
