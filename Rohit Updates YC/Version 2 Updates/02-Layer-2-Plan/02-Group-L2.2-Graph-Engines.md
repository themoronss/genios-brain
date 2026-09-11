# L2.2 — Graph Engines

**Group responsibility:** keep the graph usable. *An unmaintained graph degrades into a
plausible-looking lie faster than any other part of this system.*

**Status:** 6 of 8 built. This is the healthiest group in Layer 2.

---

## Component map

| # | Component | BLG | Status |
|---|---|---|---|
| L2.2.1 | Graph Builder | — | ✅ `pipeline.py` |
| L2.2.2 | Graph Updater | — | ✅ `derived.py` |
| L2.2.3 | Graph Validator | — | ✅ `guard.py` |
| L2.2.4 | Graph Deduplicator | BLG-02 | ✅ **strong** |
| L2.2.5 | Freshness Manager | BLG-03 | ⚠️ no per-edge half-life |
| L2.2.6 | Lifecycle Manager | — | ✅ |
| **L2.2.7** | **Version Manager** | **BLG-04** | ⚠️ **a counter, not a reader** |
| L2.2.8 | Consistency Checker | — | ✅ `discrepancies` |

---

# ✅ L2.2.4 · Graph Deduplicator — preserve, do not touch

The strongest component in Layer 2 and better than the Globe spec.

`identity.py` + `merge.py` + `merge_proposals` + `merge_history` + `discrepancies` gives
**governed** entity resolution: a merge is proposed, reviewable, recorded and reversible.
Globe asks for entity resolution; the code delivers auditable entity resolution.

And `identity.py:25` states the rule that must survive every future refactor:

> *"No edit distance, no embeddings, no '0.87 similar'."*

An entity resolved by cosine distance cannot name the rule that resolved it. Globe's own
worst-case here is right: splitting one vendor into two produces *"two half-correct
situations instead of one correct one, which is a worse failure than missing it
entirely."*

**Instruction:** no PR in the Layer 2 plan touches `identity.py` or `merge.py` while doing
something else. Changes here are their own PR with their own review.

---

# ⚠️ L2.2.7 · Version Manager (BLG-04) — a counter, not a reader

### The gap

`graph_store.py:69-72` increments an integer:
```sql
insert into graph_versions (org_id, graph_version) values (:o, 1)
on conflict (org_id) do update set graph_version = graph_versions.graph_version + 1
```

**There is no `as_of` query anywhere.** So Globe's stated purpose for this component —

> *"what did GeniOS know when it made that decision?" — and that question will be asked
> in every enterprise security review*

— **is not answerable today.**

### L2.2.7-U1 · Point-in-time graph read

**WHAT** — `read_graph(org, as_of: datetime)` returning the graph as it stood.

**WHY** — Three separate obligations converge on it:
1. **Replay.** L1 v2 makes extraction replayable; a decision replay also needs the graph
   state that produced it, or replay is only half-exact.
2. **Audit.** The security-review question above.
3. **Explanation.** *"You recommended X in March"* is only defensible against March's graph.

**HOW** (BLG-04) — snapshot + delta, not full copies:
```
graph_facts already carries valid_from / valid_until   -> temporal read is possible today
graph_edges needs the same treatment                   -> add valid_until
graph_snapshots stores a periodic materialized point   -> read = nearest snapshot + deltas

read_graph(org, as_of):
    1. nearest snapshot at or before as_of
    2. apply fact/edge changes between snapshot and as_of
    3. return an immutable view
```

**STORAGE**
```sql
create table if not exists graph_snapshots (
    org_id        text not null,
    snapshot_at   timestamptz not null,
    graph_version bigint not null,
    node_count    int not null,
    payload_ref   text not null,      -- object storage; the graph is too big for a row
    primary key (org_id, snapshot_at)
);
alter table graph_edges add column if not exists valid_until timestamptz;
```

**Cadence:** weekly snapshots, plus one before any bulk merge operation. Retention 24
months, matching `metric_history`.

**FAILURE MODES**

| Failure | Consequence | Mitigation |
|---|---|---|
| Snapshots too sparse | replay walks months of deltas | weekly floor + pre-merge snapshots |
| Edge deletions untracked | as-of read shows edges that were gone | `valid_until` on edges; **soft delete only** — a hard delete makes history unreadable |
| Snapshot storage growth | expensive | object storage by reference, not in-row; 24-month retention |

**ACCEPTANCE**
```
pytest tests/context/test_point_in_time.py -q
# a fact valid Jan-Mar is present in an as_of=Feb read and absent from as_of=Apr
# an edge soft-deleted in Feb is present at as_of=Jan
# read_graph(as_of=now) matches the live graph exactly
# replaying a March decision against as_of=March reproduces its inputs
```

**REVERSE PROMPT**
```
TASK: Make the graph readable at a point in time.
FILES: genios_engine/context/graph_store.py + a new migration

THE GAP: graph_store.py:69-72 increments graph_versions as a counter. There is no as_of
query. Globe's stated purpose for the Version Manager — "what did GeniOS know when it
made that decision", the question every enterprise security review asks — is not
answerable.

IMPLEMENT:
  def read_graph(conn, org_id, *, as_of: datetime) -> GraphView
      # nearest snapshot at or before as_of, then apply deltas to as_of

  def take_snapshot(conn, org_id, *, at: datetime) -> str
      # materialize to object storage, record in graph_snapshots

MIGRATION:
  create table graph_snapshots (DDL in doc 02 L2.2.7-U1)
  alter table graph_edges add column valid_until timestamptz

HARD RULES:
1. SOFT DELETE ONLY for edges from now on. Set valid_until; never DELETE. A hard delete
   makes history unreadable and there is no way to recover it later.
2. graph_facts already has valid_from/valid_until — use it, do not duplicate the pattern.
3. Snapshots go to OBJECT STORAGE by reference. Do not put a serialized graph in a row.
4. Weekly cadence + a snapshot before any bulk merge operation.
5. read_graph(as_of=now) must return exactly the live graph. Test this equivalence.

TEST tests/context/test_point_in_time.py — every row in the ACCEPTANCE list, plus:
  - as_of before the first snapshot returns an empty graph, not an error
  - a merge is visible after its timestamp and invisible before it
```

---

# ⚠️ L2.2.5 · Freshness Manager (BLG-03)

**GAP** — freshness is *scored* (`situations.py:120 freshness_score`) but there is no
**per-edge half-life decay**. Globe: *"A Slack message from nine months ago does not carry
the weight of yesterday's."*

### L2.2.5-U1 · Per-edge decay

**HOW** (BLG-03) — integer half-life per edge type, not one global curve:
```
strength_bp = initial_bp * (5000 ** (age_days // half_life_days)) // (10000 ** (...))
   implemented as a lookup ladder, not exponentiation

half_life_days by edge type:
    promised_to      45     a promise ages fast
    renews_on       365     a contract date does not age at all until it arrives
    owns            180
    approves        365
    depends_on       60
    contacted        30     communication recency decays quickest
```

**Different edge types must not share a curve.** A renewal date is as true in month nine
as in month one; a "contacted" edge is nearly worthless by then. One global decay gets
both wrong.

**Reinforcement resets the clock**, and `last_reinforced` already exists to carry it.

**ACCEPTANCE** — a `contacted` edge at 90 days is materially weaker than a `renews_on`
edge at 90 days; reinforcement restores strength; decay is monotonic and integer-only.

---

## Group acceptance gate

```
pytest tests/context/test_point_in_time.py tests/context/test_freshness.py -q
grep -rn "embedding\|edit_distance\|levenshtein" genios_engine/context/identity.py
```
Expected: suites pass; the grep returns nothing (the identity law holds).

| Metric | Gate |
|---|---|
| `read_graph(as_of=now)` equals the live graph | exact |
| hard `DELETE` statements against `graph_edges` | **0** |
| distinct half-lives in use | >= 4 |
