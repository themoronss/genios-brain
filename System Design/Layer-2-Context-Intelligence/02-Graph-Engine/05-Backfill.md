# Backfill — making Layer 2 work on data you already have

*`context/backfill.py` · `POST /api/org/{org}/situations/backfill`*

> **Without this, every feature in Layer 2 does nothing on an existing tenant** — while being
> perfectly implemented. That is worse than missing, because nobody knows where to look.

---

## §1 · Why it has to exist

Two of Layer 2's mechanisms only fire on **arrival**:

| Mechanism | Fires when |
|---|---|
| Alias registration | `find_or_create_node` runs — i.e. a new event touches an entity |
| Correlation | an event is drained through `process_event` / `commit_structured` |

So on a tenant with months of history:

- **no aliases** → "Acme" in an email never reaches the `acme.io` node, and no duplicate is ever
  proposed for entities that already exist
- **no correlations** → historical events belong to no situation
- **no situations** → because they are derived from correlations

Every endpoint returns an empty list. Every test is green. The features look broken.

---

## §2 · The order is not negotiable

```python
def backfill_layer2(store, org_id, *, limit=None):
    aliases      = backfill_aliases(store, org_id)
    correlations = backfill_correlations(store, org_id, limit=limit)
    situations   = refresh_situations(store, org_id)
```

| Wrong order | What happens |
|---|---|
| correlations before aliases | one company is still several nodes → several situations that must later be folded by a merge |
| situations before correlations | nothing at all — situations are 1:1 with correlations |

---

## §3 · Time order is also not negotiable

**Events replay oldest-first:**

```sql
order by se.occurred_at asc nulls last
```

Correlation opens a **new generation** when an event falls outside an existing group's span. So
processing newest-first would open a fresh generation for every older event and **shatter one
history into dozens of situations** — a backfill that makes the graph worse.

**Nodes register oldest-first too:**

```sql
order by valid_from asc
```

Whoever claims a contested alias keeps it, and a proposal is raised for the later claimant.
Reversing this would make the most recently created row canonical purely by accident of
iteration order.

---

## §4 · How an old event's nodes are recovered

The live path holds `touched` in memory. A historical event has no such thing — so the node set
is recovered from **the evidence it left behind**: every fact, observation and node it created.

```sql
select ev, node_id, node_type, canonical_key from (
    select f.created_by_event_id as ev, n.* from graph_facts f join graph_nodes n …
  union
    select o2.created_by_event_id, n.* from graph_observations o2 join graph_nodes n …
  union
    select n.created_by_event_id, n.* from graph_nodes n …
) reached
```

**One query for the whole tenant**, not one per event. On a real history that is the difference
between minutes and hours.

### Our own people are excluded, exactly as in the live path

```python
if (row.canonical_key or "").lower() in internal:
    continue
```

Without it, every outbound email in the tenant's history would anchor on our own company and the
backfill would build **one situation containing the entire business.**

---

## §5 · Safe to re-run

| Step | Why re-running is a no-op |
|---|---|
| Aliases | `insert … on conflict do nothing`; a settled merge proposal is never re-raised |
| Correlations | the query excludes events already in `context_correlation_members`; membership is idempotent |
| Situations | rebuilt from scratch every time; only a human resolution persists |

A backfill that duplicates work on the second pass is a backfill nobody dares run twice.

### Batching

`_BATCH = 200` — one transaction per 200 rows. Small enough that a failure costs little, and a
long backfill never holds one transaction open across a tenant's entire history.

`limit` caps the events processed so a large tenant can be done in passes:

```
POST /api/org/{org}/situations/backfill
POST /api/org/{org}/situations/backfill?limit=5000
```

---

## §6 · What it returns

```json
{
  "nodes_registered": 4182,
  "merge_proposals_raised": 37,
  "events_seen": 21904,
  "events_correlated": 8811,
  "situations_written": 412
}
```

| Field | How to read it |
|---|---|
| `merge_proposals_raised` | **go review these.** Every unresolved duplicate lowers the `identity` confidence of every situation about that entity |
| `events_correlated` < `events_seen` | expected — newsletters and unanchored events correctly correlate to nothing |
| `situations_written` = 0 with events correlated | something is wrong; check `context_correlations.event_count` |

The ratio `events_correlated / events_seen` is *not* the health metric. `correlation_reach` in
`GET /graph/health` uses the right denominator — events that produced **facts** — because an
event with nothing extractable was never correlatable. See
[Graph Health §4](../04-Context-Quality-Engine/04-Graph-Health-Metrics.md).

---

## §7 · What it does NOT do

| Not backfilled | Why |
|---|---|
| Re-extraction | the LLM is never re-run. Backfill works from what the graph already holds — it is free |
| Canon nodes for pre-existing canon | events ingested before Step 6 have no `title`/`knowledge_key` in their payload, so they fall back to an event-keyed node |
| Node lifecycle / health | computed by the scheduler sweep, not here |

That second row is a real, bounded gap: canon written before Layer 2 Step 6 will produce one
node per event rather than one per document. Re-submitting the document through
`POST /knowledge` fixes it, because the dedup key includes a content hash.

---

## §8 · When to run it

| Situation | Run it? |
|---|---|
| First deploy of Layer 2 onto an existing tenant | **yes, once, per org** |
| After migrations `0036`–`0040` are first applied | **yes** |
| After a large historical import | yes |
| Routinely | no — the live path handles new events |

---

*Related: [Entity Resolution](01-Entity-Resolution.md) · [Anchoring](../03-Cross-Correlation-Engine/01-Anchoring.md) · [`Rohit_Updates/Layer 2.md` §5](../../../Rohit_Updates/Layer%202.md)*
