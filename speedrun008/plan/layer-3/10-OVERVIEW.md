# Layer 3 — The Context Graph

**Written:** 2026-09-25 · against `speedrun008` @ `55a06c79`
**Reading order:** the analysis (`00`–`09`) → this page → the step files → [`STATUS`](../STATUS.md)

---

## The contract, in one sentence

> **Layer 3 holds everything that has ever been true and everything we have ever concluded, and
> hands the next decision the history of the last one.**

| | |
|---|---|
| **in** | facts and observations from L1/L2 · the decision L4 made · the card L5 sent · the outcome L6 saw |
| **out** | the **`BusinessSituationObject`** — now carrying its own history |

### The one rule that defines the boundary

```
The Evidence Graph holds what a SOURCE said.
The Intelligence Graph holds what WE concluded.
Neither may ever hold the other's rows.
```

Enforced by **two table families, not a flag** — a flag can be forgotten on one write path.

---

## ⛔ Two premise checks, run before this plan was written, and both shrank it

### 1 · The Decision Object is not five shapes on the live path. It is one, and the schema already voted.

The earlier analysis said *"the Decision Object is five shapes"*. On the **live engine path** there
is exactly **one writer**:

| writer | table | |
|---|---|---|
| `reason/store.py:1552` | `reasoning_run_outputs` | ⛔ **the engine's only decision writer** |
| `api/intelligence_routes.py:112` | `decisions` | the query API's cache, nothing else |

And `reasoning_run_outputs` is not a loose table — it carries `decision_hash` under
`check (decision_hash ~ '^[0-9a-f]{64}$')`, a six-value `outcome_kind` vocabulary
(`decision · no_action · defer · insufficient_context · blocked · failed`) with two cross-checks,
and `confidence_bp` as an **integer** between 0 and 10000.

⛔ **And migration 0031 already declared it authoritative with a foreign key:**

```sql
foreign key (org_id, reasoning_run_id, reasoning_decision_hash)
  references reasoning_run_outputs (org_id, run_id, decision_hash)
```

**The schema chose the Decision Object two hundred migrations ago.** L3-0 is not a selection. It is
writing the name down and demoting the other four to what they already are.

### 2 · ⛔ The `decision → situation` edge is NOT missing. L2-7 created it by accident.

`signals` now carries, **in the same row**:

| column | from | |
|---|---|---|
| `reasoning_decision_hash` ＋ `reasoning_run_id` | migration **0031** | with the FK above |
| `situation_id` | migration **0182** (L2-7) | nullable, no FK, by design |

And `domain_shadow`'s emit binds both in one INSERT — `:dhash` at line 366, `:sit` at line 396.

**So the edge exists as data today:**

```sql
select situation_id, reasoning_run_id, reasoning_decision_hash
from signals
where situation_id is not null and reasoning_decision_hash is not null
```

⛔ **It is a delivery-side table doing a graph's job.** The link is real; it is not addressable,
not walkable backwards, and dies whenever a signal is archived. **Layer 3 does not create this
edge. It lifts it somewhere it can be read.**

---

## What is actually missing, after both corrections

| | | |
|---|---|---|
| ✅ | the Decision Object | exists, has an FK pointing at it, has no name |
| ✅ | `decision ─about→ situation` | exists in `signals`, not addressable |
| ✅ | `decision ─cited→ evidence` | `reasoning_evidence_id_map` (0117) |
| ✅ | `outcome ─followed→ decision` | `execution_outcomes.decision_hash` |
| ✅ | `situation ─anchored→ entity` | `context_situations.anchor_node_id` |
| ⛔ | `decision ─supersedes→ decision` | **genuinely missing** — no column, no table |
| ⛔ | `delivery` and `outcome` written back | `deliver/` and `feedback/` write **nothing** |
| ⛔ | **anything reading any of it** | ⛔ **the whole point, and zero of it exists** |

**Five of seven edges exist. The work is one edge, two writers, and a read.**

---

## ⛔ The measurement that justifies the layer

```
prior_decision  0    previous_decision  0    last_decision  0    past_decisions  0
```

**Nothing in the engine reads a prior decision.** Every sweep decides from scratch. That is why the
same card can be sent four times, why *"stop telling me this"* has nowhere to attach, and why
*"of last month's decisions, how many led anywhere"* is unanswerable.

---

## Cost

| | |
|---|---|
| **model calls** | ⛔ **none, in any step.** Layer 3 is structure and reads |
| **`vocabulary_fingerprint`** | unchanged — no prompt is touched |
| **re-extraction** | none |
| **migrations** | **2** — L3-1 (two tables), L3-4 (one column) |
| **row growth** | ⛔ **tens of rows per tenant per week.** A tenant whose world did not move writes nothing |

**The Intelligence Graph is the cheap half.** Its key is `(org_id, situation_id, slice_digest)`, so
an unchanged slice resolves to one row — the exact defence against the 995 MB incident, where a
derived content address churned every sweep.

---

## The eight steps

| | step | needs Harsh | why it is here |
|---|---|---|---|
| **L3-0** | [Name the Decision Object](step-00-name-the-decision.md) | — | a graph of decisions needs decisions to be one thing. The FK already voted |
| **L3-1** | The Intelligence Graph's two tables | ⛔ **migration** | `intel_nodes` + `intel_edges`, closed vocabularies, totality guards, cascade to `orgs` — **landed with their first writer**, never empty |
| **L3-2** | Lift `about` out of `signals` | — | the edge exists in a delivery table; make it addressable and survive archival |
| **L3-3** | Delivery and feedback write back | — | `delivered_as`, `resulted_in`. `execution_outcomes` already has 7 terminal labels waiting |
| **L3-4** | Revision — the five-word action ＋ `supersedes` | ⛔ **migration** | `insert · noop · restated · reversed · expired`. ⛔ **`expired` has no Evidence-Graph equivalent** |
| **L3-5** | ⛔ **The history reaches the situation** | — | ⛔ **the step the other seven exist for.** The correlators read it; the BSO carries *"decided 3×, ignored"* |
| **L3-6** | The surface | — | one line on the card · the side-panel summary · the founder count |
| **L3-7** | Turn it on | — | cutover switches, scenario registry, sensitivity probes — L2-8's pattern |

### Step order is dependency order, and L3-5 is the payload

L3-0 → L3-4 are **plumbing**. Nothing a founder sees changes. **L3-5 is the first step where the
product behaves differently**, and L3-6 is where they can see it.

⛔ **L3-1 lands its tables WITH their first writer, deliberately.** A table with no writer is the
*"unit that nothing calls"* defect this project has caught six times — and the graph's own design
notes cite it by name when refusing a `graph_snapshots` table.

---

## The discipline, unchanged from Layers 1 and 2

Every step: **premise check before any code** → **cost check** → **RED tests** → build →
**wiring check** → **full suite** → four artifacts (findings file · ticked criteria · STATUS row ·
HARSH-ORDER entry) → commit and push.

**Technique 3 on every step:** neutralise the fix, confirm the probe goes red — applied to the
**rule**, not to the module's own code.

**Totality guards on every closed vocabulary:** a table with a row per member, plus an import-time
check in **both** directions.

**Declared silence:** anything deliberately unwritten gets a name, a reason and a mover — the
`DARK_DOMAINS` / `SILENT_LANES` / `EMPTY_BY_DESIGN` idiom.

### Three rules this layer inherits from the Evidence Graph

| | |
|---|---|
| **soft delete only** | closed by `valid_to`, never `DELETE`. `tests/context/test_point_in_time.py` scans `context/` and fails on one |
| **cascade to `orgs`** | `test_every_org_scoped_table_has_a_proven_account_delete_cascade` refused 0183 without it |
| **seat visibility** | `GET /graph` hides nodes known only from another seat's private evidence. ⛔ A decision made on private evidence must be hidden the same way, or the Intelligence Graph becomes a side channel around a rule the Evidence Graph enforces |
