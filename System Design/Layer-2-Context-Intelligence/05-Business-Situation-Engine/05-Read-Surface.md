# The read surface — every way out of Layer 2

*`api/situation_routes.py` · `api/identity_routes.py`*

> Nine HTTP endpoints. **They are currently the only consumers of situations and projections** —
> nothing inside the codebase reads `context_situations`. See
> [Output §6](../Output-To-Layer-3-and-4.md).

---

## §1 · The endpoints

| Method | Path | Returns |
|---|---|---|
| `GET` | `/api/org/{org}/situations` | active situations, most-confident first |
| `GET` | `/api/org/{org}/situations/{id}` | one situation **with its evidence events** |
| `POST` | `/api/org/{org}/situations/{id}/resolve` | mark handled |
| `POST` | `/api/org/{org}/situations/backfill` | apply Layer 2 to pre-existing history |
| `GET` | `/api/org/{org}/projections` | the lenses this tenant has |
| `GET` | `/api/org/{org}/projections/{domain}` | one lens + boundary edges |
| `GET` | `/api/org/{org}/projections/_/unclassified` | what falls through every lens |
| `GET` | `/api/org/{org}/graph/health` | the quality vector, computed now |
| `GET` | `/api/org/{org}/graph/health/history` | the trend |

Identity review lives in `identity_routes.py` — see
[Merge and Reverse §7](../02-Graph-Engine/02-Merge-and-Reverse.md).

Every route resolves the tenant from the credential and **refuses a path naming a different
org**:

```python
def _org(org_id: str, org: str = Depends(get_current_org)) -> str:
    if org_id != org:
        raise HTTPException(403, "org mismatch")
    return org
```

---

## §2 · Confidence comes back as a vector

```json
{
  "situation_id": "sit_9f2a",
  "type": "opportunity",
  "domain": "sales",
  "status": "active",
  "about": {"node_id": "node_44", "name": "acme.io", "type": "company"},
  "evidence_events": 7,
  "confidence": {
    "overall": 40, "evidence": 84, "freshness": 85,
    "consistency": 100, "identity": 40
  },
  "coverage": 50,
  "missing": ["expected close date", "agreed next step"]
}
```

**Never a single number**, because a caller needs to know *why* it is low. *"40 overall, 40
identity"* tells you to go resolve a duplicate. *"40"* tells you nothing you can act on.

`coverage` and `missing` sit **outside** `confidence` deliberately — completeness is not
correctness. Not knowing a close date does not make the stage we *do* know less true.

The detail endpoint adds `confidence.inputs` — the raw arithmetic, including
`domain_spec_version`. **A confidence number nobody can account for is a number nobody should act
on.**

---

## §3 · Ordering is not prioritisation

```python
order by s.confidence_overall desc, s.last_seen_at desc nulls last
```

The response says so explicitly:

```json
"ordering": "confidence_desc",
"note": "ordered by confidence, not priority — ranking is a decision made downstream"
```

A situation we are **sure** about deserves more thought than one assembled from a single
unverified email. Which situation **matters most** is a decision, and Layer 2 does not decide.

Shipping a `/situations` list sorted by anything that looked like importance would quietly make
this layer a ranking engine.

---

## §4 · Resolve reopens by itself

```json
{"situation_id": "sit_9f2a", "status": "resolved", "reopens_on_new_evidence": true}
```

The flag is in the response because callers must not assume "resolved" is terminal.

> Marking something handled is a statement about the **past**, not a promise about the future.
> When the customer writes again, it is open again — a situation that stays closed through new
> activity **actively hides work.**

Evidence older than the resolution does **not** reopen it, so a backfill delivering old emails
cannot resurrect everything a team has closed. See [Lifecycle](02-Lifecycle.md).

---

## §5 · Projections report their own limits

Three honesty features, each preventing a specific wrong belief.

**Truncation is visible.**
```json
{"node_count": 500, "total_members": 41203, "truncated": true}
```
Without `total_members`, "500 members" is indistinguishable from "exactly 500 members" when the
truth is 41,203 — a truncation the caller cannot see and would not suspect.

**Boundary edges are returned, not dropped.** An entity in the Sales lens is often connected to
one that is not. Dropping that edge makes the lens claim the customer has no other
relationships — *a lie by omission, and the worst kind, because the view looks complete.*

**Unclassified is a first-class query, not a diagnostic.**
```json
{"nodes": [...], "total": 812, "truncated": false,
 "note": "not an error — these are simply not reached by any situation yet"}
```
Without it, a projection system is a way to lose things quietly: an entity nobody classified is
invisible in every view, absent from every count, and unreported.

Every lens response also carries:
```json
"note": "a lens narrows retrieval, never evaluation — reasoning still sees every entity"
```

---

## §6 · `registered: false` is a normal state

```json
{"domain": "engineering", "display_name": "Engineering", "registered": false,
 "situations": 12, "active_situations": 9}
```

Lenses are **discovered from the data**, not read from the registry. A domain arriving before
anyone describes it still gets a fully working lens; `registered: false` simply means "present,
not yet described".

If lenses came from the registry, Layer 2 would **block** Layer 3 from ever adding a domain. See
[Domain Specs §6](04-Domain-Specs.md).

---

## §7 · Backfill

```
POST /api/org/{org}/situations/backfill
POST /api/org/{org}/situations/backfill?limit=5000
```

Sits under `/situations` because situations are what it ultimately produces, but it runs all
three passes in order — aliases, correlations, situations. Safe to re-run. See
[Backfill](../02-Graph-Engine/05-Backfill.md).

---

## §8 · What the surface deliberately does not expose

| Not exposed | Why |
|---|---|
| Raw graph traversal | that is what Layer 4 already does, directly, against the tables |
| Fact-level editing | corrections enter through Layer 1's `human` door, so they carry provenance and authority |
| A "priority" field | Layer 2 does not decide |
| Situation creation | situations are **derived**; you cannot POST one into existence |
| Merge without a proposal | `POST /identity/proposals/{id}/merge` requires an existing proposal, and refuses a node pair that does not match it |

That fourth row is load-bearing: a situation you could create by hand would be a situation
nobody could rebuild, and a graph that cannot be rebuilt cannot be trusted.

---

*Related: [Situation Assembly](01-Situation-Assembly.md) · [Projections](03-Projections.md) · [Output to Layer 3 & 4](../Output-To-Layer-3-and-4.md)*
