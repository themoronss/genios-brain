# Lifecycle and health — the maintenance machinery

*`context/health.py` · `api/routes.py:run_maintenance_sweep` · migration `0039`*

> This page is about the **mechanism**: what runs, when, how it is batched, and what it refuses
> to do.
>
> For what the numbers *mean* and how to read them, see
> [Graph Health Metrics](../04-Context-Quality-Engine/04-Graph-Health-Metrics.md).

---

## §1 · Why maintenance is a separate pass

Steps 1–3 of Layer 2 **build** the graph. Nothing kept it. And the things that go wrong do not
announce themselves — a broken edge is not an exception, it is a traversal that silently returns
less than it should.

The two passes:

| Pass | Writes | Cost |
|---|---|---|
| `refresh_node_lifecycle` | `context_node_lifecycle` | `O(nodes)` |
| `compute_health` | `graph_health` | 8 integrity checks + 9 metric queries = **17 full-table scans** |

---

## §2 · Where they run — and why not in the drain

Both live in the **scheduler sweep** (`run_maintenance_sweep`), which fires every
`sync_interval_hours` — hourly-scale, not per minute.

```python
graph_maintenance = None
if _graph is not None:
    for org in {c.org_id for c in _connections.list_active()}:
        try:
            refresh_node_lifecycle(_graph, org, eval_time=now)
            health = compute_health(_graph, org, eval_time=now)
            purge_old_health(_graph, org)
            if health.overall < 80:
                unhealthy.append(...)
        except Exception:
            _log.exception("graph maintenance failed org=%s", org)   # one org ≠ the rest
```

**Not in the L2 drain**, because both are `O(graph)` and the drain is `O(event)`. Running them
per event would make every single email pay for a whole-tenant scan.

Compare with what *does* belong in the drain:

| Runs per event | Runs per drain | Runs per sweep |
|---|---|---|
| graph writes, correlation | read models, attention, situations | **lifecycle, health** |

The sweep logs a warning for any org below 80, and one org's failure never stops the others.

---

## §3 · Batched writes — how a maintenance pass becomes an outage

`refresh_node_lifecycle` originally wrote **one row at a time**. That is one network round trip
per entity: on a 50,000-entity tenant, **50,000 round trips inside a single transaction.**

```python
_WRITE_BATCH = 500

for start in range(0, len(params), _WRITE_BATCH):
    with store.engine.begin() as conn:
        conn.execute(upsert, params[start:start + _WRITE_BATCH])   # executemany
```

Note what did **not** move into SQL: the lifecycle rule itself.

```python
params.append({..., "lc": node_lifecycle(last_evidence_at=last, now=now)})
```

The state is decided in Python — **one tested definition** — and only the writes are batched.
Expressing the rule a second time in SQL would create two definitions that can drift, and the
SQL one would have no test.

---

## §4 · The `'epoch'` sentinel

`refresh_node_lifecycle` finds each entity's most recent evidence across facts, observations and
edges with `greatest(...)`, which needs a floor:

```sql
greatest(
  coalesce((select max(f.occurred_at) …), 'epoch'::timestamptz),
  coalesce((select max(g.occurred_at) …), 'epoch'::timestamptz),
  coalesce((select max(e.last_seen_at) …), 'epoch'::timestamptz))
```

```python
if last is not None and last.year <= 1970:
    last = None
```

**The sentinel must be converted back to `None`.** Passing `1970-01-01` through as a real
timestamp would archive **every entity that has no dated evidence** — precisely the entities the
unknown-is-not-old rule exists to protect.

A three-line guard standing between correct behaviour and silently retiring a tenant's entire
graph.

---

## §5 · Retention on the monitoring table

```python
def purge_old_health(store, org_id, *, keep_days=180):
    delete from graph_health where computed_at < now() - make_interval(days => :days)
```

`graph_health` is append-only, one row per org per sweep. **Append-only with no clock becomes
the largest table in the database.** The trend is what matters, and six months of it is plenty.

Note the asymmetry with the rest of the layer: this is monitoring *about* the graph, not the
graph. The no-deletion law protects evidence, not metrics.

---

## §6 · What this machinery refuses

### It never repairs

Every one of the eight integrity checks begins with `select`, enforced by
`test_integrity_checks_never_repair`.

> An auto-fix that runs unattended turns a small inconsistency into a **large, silent data
> loss**: it runs at 3am, deletes the rows it decided were wrong, and nobody finds out until a
> decision cannot be explained.

### It never deletes graph data

`test_nothing_in_maintenance_deletes_graph_data` asserts `health.py` contains no
`delete from graph_nodes / graph_facts / graph_edges / graph_observations`, and no `drop table`.

Pruning here is **archival**. Volume was controlled at Layer 1, where the gate drops noise before
it becomes an entity. *An old customer is a dormant relationship, not a mistake to erase.*

### Lifecycle never gates

`dormant` is a **label**. A dormant entity is still evaluated, every sweep. See
[Graph Health §5](../04-Context-Quality-Engine/04-Graph-Health-Metrics.md#5--node-lifecycle--a-label-never-a-filter)
for the starvation loop this prevents, and the test that enforces it.

---

## §7 · The two thresholds, and why they differ

| | Dormant after | Archived after |
|---|---|---|
| **Entity** (`health.py`) | 90 days | 365 days |
| **Situation** (`situations.py`) | 45 days | 180 days after resolution |

A conversation ending is normal. A **relationship** ending takes far longer. Using one threshold
for both would archive customers who are merely between deals — and the entity threshold is
deliberately double the situation window so a customer outlives several of their own situations.

`test_a_relationship_outlives_a_conversation` asserts the inequality directly, importing both
constants, so a future edit to either cannot quietly invert it.

---

## §8 · Operating it

| Task | How |
|---|---|
| Check now, without recording | `GET /api/org/{org}/graph/health` — `compute_health(persist=False)` |
| See the trend | `GET /api/org/{org}/graph/health/history` |
| Force a pass | it runs on the scheduler; there is no manual trigger endpoint |
| Disable | `GENIOS_SCHEDULER_ENABLED=false` — health stops updating; nothing else changes |

---

*Related: [Graph Health Metrics](../04-Context-Quality-Engine/04-Graph-Health-Metrics.md) · [Merge and Reverse](02-Merge-and-Reverse.md) · [Backfill](05-Backfill.md)*
