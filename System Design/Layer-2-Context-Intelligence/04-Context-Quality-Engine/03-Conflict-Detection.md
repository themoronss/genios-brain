# Conflict Detection — discrepancies

*Layer 2 · [context/graph_store.py:29–55](../../../genios_engine/context/graph_store.py) (the decision) and [:160–195](../../../genios_engine/context/graph_store.py) (the recording)*

> **When two systems say different things about the same field, which one wins — and where
> does the loser go?**

| | |
|---|---|
| **Files** | [context/graph_store.py](../../../genios_engine/context/graph_store.py) — `fact_write_action` (pure) and `write_fact` / `write_discrepancy` (the writers) |
| **Table** | `discrepancies` — [`0004_l2_context_graph.sql:138`](../../../migrations/0004_l2_context_graph.sql) |
| **Read by** | [situations.py:331](../../../genios_engine/context/situations.py) (`consistency_score`) · [health.py:277](../../../genios_engine/context/health.py) (`open_discrepancies`) · [api/routes.py:1250](../../../genios_engine/api/routes.py) (`GET /context/discrepancies`) · [executive/brief.py:209](../../../genios_engine/executive/brief.py) |
| **Never** | Resolves, merges, averages, or picks a winner on the challenger's behalf |
| **Tests** | [tests/test_fact_write_guard.py](../../../tests/test_fact_write_guard.py) — 9 tests, described in its own docstring as *"frozen behaviour"* |

---

## 1 · The rule

A conflict between two sources is **a product signal, not a data problem**. The comment
above the table says so:

```sql
-- 0004_l2_context_graph.sql:137
-- Source disagreement (a product signal, not a silent overwrite).
create table if not exists discrepancies (
    id              text primary key,
    org_id          text not null,
    subject_node_id text not null,
    field           text not null,
    held            jsonb not null,
    challenger      jsonb not null,
    status          text not null default 'open',
    created_at      timestamptz not null default now()
);
create index if not exists discrepancies_open on discrepancies (org_id, status);
```

Nothing in Layer 2 is allowed to decide *which value is true*. Deciding is Layer 4's job, and
this particular decision usually needs a human anyway. So the graph does three things at
once:

1. **Keeps the held value.** The current active fact does not move.
2. **Records both sides.** `held` and `challenger` are stored as jsonb, each with its
   authority rank.
3. **Reports it.** `GET /api/org/{org}/context/discrepancies` renders it as a card:
   *"which one is true?"*

The API docstring is blunt about how long that took:

> The detector always wrote these; **this is the first surface that reads them.** The flag
> is product — 'which one is true?' is a card.

---

## 2 · `fact_write_action` — the whole conflict policy as a pure function

Every graph write goes through `write_fact`, and every `write_fact` asks this function what
to do. It has no I/O, no clock, and five possible answers.

```python
# graph_store.py:29
def fact_write_action(*, held_value_json, held_rank, held_occurred_at,
                      new_value_json, new_rank, new_occurred_at,
                      replay: bool = False) -> str:
    if held_value_json is None:
        return "insert"
    if held_value_json == new_value_json:
        return "noop"
    ho, no = _ts(held_occurred_at), _ts(new_occurred_at)
    if ho is not None and no is not None and no < ho:
        return "historical"                       # out-of-order → record, never overwrite
    if replay:
        return "historical"                       # replay may fill gaps, never flip state
    if held_rank is not None and new_rank < held_rank:
        return "discrepancy"                      # lower authority disagrees → flag, keep held
    return "supersede"
```

### The five outcomes

| Outcome | Condition | What happens to the graph |
|---|---|---|
| `insert` | No active row for `(node, field)` | New fact, `status='active'` |
| `noop` | New value **equals** held value | **Held row unchanged — but a corroborating source-ref is written.** §3 |
| `historical` | New `occurred_at` is older than held's, **or** `replay=True` | New row inserted with `status='historical'` and `valid_to=now()`. Preserved with provenance, never the active value |
| `discrepancy` | Values differ, new is not older, **and** `new_rank < held_rank` | **Nothing is written to `graph_facts`.** A row lands in `discrepancies`. `write_fact` returns `None` |
| `supersede` | Values differ, new is not older, rank is equal or higher | Held row gets `valid_to=now(), status='superseded'`; new row becomes active |

### The order of the checks is the design

The docstring calls out the load-bearing ordering:

> The load-bearing rule is 'historical': a fact whose `occurred_at` is OLDER than the held
> row's may never overwrite current state. Without this, any backfill/re-extract replays a
> 2024 `thread.ball_in_court=us` over today's `them` and the correct value is already
> stamped superseded — an unrecoverable corruption. **Order of checks matters: staleness is
> decided BEFORE authority**, so replaying old low-rank mail doesn't spray discrepancies
> against current system-of-record values either.

Two consequences worth stating separately:

* **Old high-rank data does not win.** A rank-4 company policy from last year does not pin a
  field against this morning's rank-3 Stripe row. *Canon is authoritative, not immortal* —
  [capture/internal_knowledge.py:27](../../../genios_engine/capture/internal_knowledge.py).
* **Old low-rank data does not create noise.** Without the ordering, a backfill of two years
  of email would open a discrepancy for every field a CRM has since corrected. The
  discrepancy queue would be unusable on the first day it was turned on, and `consistency`
  would be zero for every entity in the tenant.

```python
# tests/test_fact_write_guard.py:38
def test_stale_beats_authority_check():
    assert act(new_rank=4, new_occurred_at=T_OLD, held_occurred_at=T_NEW) == "historical"
    # and old LOW-rank data doesn't spray discrepancies against current state either
    assert act(new_rank=1, new_occurred_at=T_OLD, held_occurred_at=T_NEW) == "historical"
```

### When timestamps are missing

If either side has no `occurred_at`, the staleness check cannot fire and the write takes the
live path — `supersede` or `discrepancy` depending on rank:

```python
# tests/test_fact_write_guard.py:58
def test_missing_timestamps_keep_live_semantics():
    assert act(held_occurred_at=None, new_occurred_at=None) == "supersede"
    assert act(held_occurred_at=None, new_occurred_at=None,
               new_rank=1, held_rank=3) == "discrepancy"
    # but replay still refuses to touch state without proof of order
    assert act(held_occurred_at=None, new_occurred_at=None, replay=True) == "historical"
```

`replay=True` is the belt-and-braces mode for deliberate reprocessing: **it may fill a
missing fact but never supersedes an active one, regardless of timestamps.**

### The authority ladder

`new_rank < held_rank` is the whole conflict trigger, so the rank scale is the conflict
policy. From [pipeline.py:71](../../../genios_engine/context/pipeline.py):

```python
FACT_CONF_BY_RANK = {4: 1.00, 3: 0.90, 2: 0.85, 1: 0.40}
```

| Rank | Meaning | Written by |
|---:|---|---|
| **4** | Company canon — what the org deliberately asserts about itself | `authority_rank_for()` for any canon `internal_kind` — [capture/internal_knowledge.py:113](../../../genios_engine/capture/internal_knowledge.py) |
| **3** | System of record — a structured row from a connected tool | [context/structured.py:50](../../../genios_engine/context/structured.py) — *"R3 system-of-record"* |
| **2** | Observed — extracted from something we watched happen | `pipeline.py`, the default for the unstructured lane |
| **1** | The `write_fact` default, if a caller passes nothing | `graph_store.write_fact(authority_rank: int = 1)` |

Authority is set by **Layer 1**, not derived here. From `internal_knowledge.py`:

> L1 owns this: authority is a property of PROVENANCE, and provenance is what capture knows.
> **L2 honours it rather than re-deriving it from the source name.**

---

## 3 · The `noop` branch is not a no-op — it is corroboration

Included here because it is the *positive* half of the same mechanism, and because it was
dead for a long time.

```python
# graph_store.py:142
if action == "noop":
    already = conn.execute(text(
        "select 1 from graph_source_refs where fact_version_id=:fv "
        "and event_id=:e limit 1"),
        {"fv": held.fact_version_id, "e": event_id}).first()
    if already is None:
        self._write_ref(conn, org_id=org_id, fact_version_id=held.fact_version_id,
                        event_id=event_id, source=source,
                        evidence={**(evidence or {}), "corroborates": True})
    return None
```

The comment records the bug:

> A second source asserting the SAME value is not "nothing happened": it is independent
> confirmation… **This branch used to return None before any ref was written, so `src_count`
> could never exceed 1 and the whole ladder was dead code — email + CRM agreeing looked
> identical to email alone.**

Two sources agreeing and two sources disagreeing are the two halves of consistency, and both
now leave a trace:

| Sources say | `fact_write_action` | Trace left | Effect on quality |
|---|---|---|---|
| The same thing | `noop` | An extra `graph_source_refs` row on the **held** version, tagged `corroborates: true` | Raises `source_count` → raises `evidence_score` |
| Different things, challenger has lower rank | `discrepancy` | A row in `discrepancies` | Raises `open_discrepancies` → lowers `consistency_score` |

The ref is deduped per event (`already is None`) so a re-sync cannot inflate the count, and
`refresh_situations` counts `count(distinct se.source)` so same-source repeats do not either.

---

## 4 · Recording a conflict — and the bug where both sides said the same thing

```python
# graph_store.py:160
if action == "discrepancy":
    # held keeps its OWN value (the system-of-record), challenger carries the new one.
    # (Was a bug: both sides recorded the challenger value → 'paid vs paid', real
    #  conflict lost — e.g. Stripe 'paid' R3 vs email 'unpaid' R2.)
    self.write_discrepancy(
        conn, org_id=org_id, subject_node_id=subject_node_id, field=field,
        held={"value": json.loads(held_val), "rank": held.authority_rank},
        challenger={"value": value, "rank": authority_rank,
                    "source": source, "event_id": event_id})
    return None
```

The two payloads are deliberately **asymmetric**:

| Side | Carries | Why |
|---|---|---|
| `held` | `value`, `rank` | It is already in the graph; its provenance is reachable through `graph_source_refs` on the active fact version |
| `challenger` | `value`, `rank`, `source`, `event_id` | The challenging fact is **never written**, so this row is the only record that the claim was ever made. Without `event_id` the challenge would be unattributable |

The bug in the comment is worth understanding, because it is the exact failure mode a
conflict detector is most exposed to: **it fired, it wrote a row, and the row said nothing.**
Both sides recorded the challenger's value, so a Stripe `paid` (rank 3) versus an email
`unpaid` (rank 2) was stored as *"paid vs paid"*. A queue full of rows where held equals
challenger looks like a broken detector and gets ignored — and the real conflicts are the
ones that disappeared.

`json.loads(held_val)` is the other detail: `held_val` is a JSON string (normalised a few
lines above by `held.value if isinstance(held.value, str) else json.dumps(held.value)`), and
it is decoded before storage so the jsonb column holds a real value, not a string containing
JSON.

**`write_fact` returns `None` for a discrepancy.** Callers cannot tell a conflict from a
no-op by return value alone; both are `None`. The only signal is the `discrepancies` row.

---

## 5 · The consequence nobody has closed: nothing ever resolves a discrepancy

> ### ⚠️ Verified against the whole repository
> ```
> grep -rn "update discrepancies|delete from discrepancies|discrepancies set" \
>      genios_engine migrations tests   → no matches
> ```
> `status` has a default of `'open'` and **no code path anywhere sets it to anything else.**
> There is no resolve endpoint, no sweep, no merge-time cleanup, and no TTL. Every
> discrepancy ever written is open forever.

This is not a cosmetic gap. It propagates into three quality numbers:

### 5.1 · `consistency_score` becomes monotonically non-increasing

```python
consistency_score(open_discrepancies=n)  →  max(0, 100 - min(100, n * 34))
```

| open on this entity | `consistency` | effect on the situation's `overall` |
|---:|---:|---|
| 0 | 100 | none |
| 1 | 66 | caps `overall` at 66 |
| 2 | 32 | caps `overall` at 32 |
| **3+** | **0** | **`overall` = 0, permanently** |

Because `overall = min(trust)`, **three conflicts on one entity pin every situation about
that entity to zero confidence for the lifetime of the tenant** — with no way to clear them
short of a manual `UPDATE`. On an entity with a chatty low-authority source (an email thread
that keeps restating a stale price against a live Stripe row), three is not a large number.

### 5.2 · The health `consistency` dimension has the same shape

```python
# health.py:230
("consistency", metrics.get("open_discrepancies", 0), nodes),
```

`_ratio_score(bad=open_discrepancies, total=nodes_total)`. Since `bad` only ever grows and
`total` grows much more slowly, this dimension trends downward for every tenant. Once
`open_discrepancies ≥ nodes_total` it is 0, and since `overall = min(measured)`, the whole
graph health score is 0 with no repair path.

### 5.3 · The executive brief reports it as a risk

```python
# executive/brief.py:110
if signal.get("open_discrepancies"):
    risks.append(f"{signal['open_discrepancies']} unresolved record conflict(s) on this entity")
```

A permanent risk line on every entity that has ever had one conflict.

### What a fix would look like

The pieces already exist. `GET /api/org/{org}/context/discrepancies` renders the queue;
`merge_proposals` shows the pattern for a settled-decision status (`open | merged |
rejected`), and `identity.py` shows the *"do not ask again"* guard for a rejected pair. A
resolve endpoint that sets `status` and, on "the challenger was right", performs an
authority-aware `write_fact` would close the loop. **None of it is built.**

---

## 6 · Worked example — Stripe says paid, an email says unpaid

**Setup.** A `subscription.status` fact on the Acme company node.

| | value | rank | occurred_at | source |
|---|---|---:|---|---|
| **Held** | `"paid"` | 3 (system of record) | 2026-08-05 | `stripe` |
| **Challenger** | `"unpaid"` | 2 (observed) | 2026-08-06 | `gmail` |

**Step 1 — `fact_write_action`:**

| Check | Result |
|---|---|
| `held_value_json is None`? | No — there is an active row |
| `held_value_json == new_value_json`? | `'"paid"' != '"unpaid"'` → no |
| `no < ho`? | `2026-08-06 < 2026-08-05` → **no**, the challenge is newer |
| `replay`? | No |
| `new_rank < held_rank`? | `2 < 3` → **yes** |
| → | **`"discrepancy"`** |

**Step 2 — what is written:**

```json
{
  "id": "disc_…",
  "org_id": "org_acme",
  "subject_node_id": "node_acme",
  "field": "subscription.status",
  "held":       { "value": "paid",   "rank": 3 },
  "challenger": { "value": "unpaid", "rank": 2,
                  "source": "gmail", "event_id": "evt_…" },
  "status": "open"
}
```

`graph_facts` is **untouched**. `subscription.status` is still `"paid"`, still rank 3, still
the value every read model returns. `write_fact` returns `None`.

**Step 3 — what the quality engine does with it, on the next drain:**

| Consumer | Query | Effect |
|---|---|---|
| `refresh_situations` | `select subject_node_id, count(*) from discrepancies where org_id=:o and status='open' group by subject_node_id` | `open_discrepancies = 1` for `node_acme` |
| `consistency_score` | `100 − 34` | **66** |
| Every situation anchored on Acme | `overall = min(evidence, 66, identity[, freshness])` | capped at **66** |
| `compute_health` | `open_discrepancies` metric | `consistency = round(100 × (1 − 1/nodes_total))` |
| `GET /context/overview` | `conflictsDetected` | `1` |
| `GET /context/discrepancies` | the card | *"Acme · subscription.status · held: paid (rank 3) · challenger: unpaid (rank 2, gmail)"* |

**Step 4 — the reversed case.** Same two facts, but Stripe's row arrives *second*:

| Check | Result |
|---|---|
| values differ | yes |
| `no < ho`? | `2026-08-06 < 2026-08-05`? no — Stripe's is newer |
| `new_rank < held_rank`? | `3 < 2` → **no** |
| → | **`"supersede"`** |

The email's `"unpaid"` gets `valid_to=now(), status='superseded'`, Stripe's `"paid"` becomes
active, and **no discrepancy is recorded**. Higher authority arriving later is not a
conflict; it is a correction. The conflict only exists when the *weaker* source is the newer
one — which is precisely the case a human needs to look at, because the newest information
came from the least reliable place.

---

## 7 · What the read surface exposes

```python
# api/routes.py:1250
@router.get("/context/discrepancies")
def context_discrepancies(limit: int = 50, org_id: str = Depends(get_current_org)) -> dict:
```

| Field | Source |
|---|---|
| `id`, `field`, `detected_at` | the `discrepancies` row |
| `entity`, `entity_id` | `left join graph_nodes` on `subject_node_id`, `valid_to is null` |
| `held`, `challenger` | the two jsonb payloads, decoded |

Ordering is `created_at desc`, capped at 200 (`limit = max(1, min(int(limit), 200))`). The
join is a **left** join, so a discrepancy on a node that has since been closed still appears,
with `entity: null` — the conflict survives the entity, which is consistent with the layer's
never-delete rule.

`GET /context/overview` surfaces the count as `conflictsDetected`, and its docstring records
that this too was once a lie:

> `conflictsDetected` is the REAL open-discrepancy count (was hardcoded 0 while the conflict
> detector ran and wrote rows nobody read).

---

## 8 · Edge cases and invariants

| Case | Behaviour |
|---|---|
| Both values identical | `noop` — a corroborating source-ref, never a discrepancy |
| Equal ranks, different values, newer challenger | `supersede`. **Equal authority is not a conflict** — `new_rank < held_rank` is strict |
| `held_rank is None` | The rank check is skipped → `supersede`. A held row with a null `authority_rank` can always be overwritten |
| Challenger is older | `historical` — recorded with provenance, never a discrepancy |
| `replay=True` and values differ | `historical`, always. A deliberate reprocess can never open a discrepancy |
| The same conflict arrives twice | **Two rows.** There is no uniqueness constraint on `(org_id, subject_node_id, field)` and no dedup check. A repeating low-authority source drives `open_discrepancies` up on every event |
| Node is merged away | **`discrepancies` is not in `merge.py`'s `_NODE_REFERENCES`.** The eight tables listed there get their `node_id` repointed to the survivor; this one does not. So the rows keep pointing at the closed node, stop counting toward the survivor's `open_discrepancies`, and render with `entity: null`. **A merge silently clears an entity's consistency penalty** |
| Two workers write the same conflict concurrently | Both succeed; `id` is a fresh `new_id("disc")` each time |

> The "same conflict arrives twice" row is the one to watch. Combined with §5 (nothing ever
> closes a discrepancy) and the `× 34` slope of `consistency_score`, a single misbehaving
> low-rank source that re-asserts a stale value on three separate emails is enough to zero
> the confidence of every situation about that entity, permanently.

---

## 9 · See also

* [01 · The Confidence Vector §4](01-Confidence-Vector.md) — `consistency_score` and the `× 34` slope
* [04 · Graph Health Metrics](04-Graph-Health-Metrics.md) — the `consistency` and `identity` dimensions, and the six integrity checks that measure the same class of damage at graph scale
* [capture/internal_knowledge.py](../../../genios_engine/capture/internal_knowledge.py) — why rank 4 exists and why freshness still beats it
