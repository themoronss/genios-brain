# 25 · `1.3b` — the two untested modules, and one of them guarded health information

**Written for:** Rohit. **Date:** 2026-10-03. ⛔ Step `1.3b` of
[`21-PLAN-TO-PRODUCTION.md`](21-PLAN-TO-PRODUCTION.md) — the only work the audit's **deleted**
naming column left behind.

```
new tests   32   (18 + 14)  ·  mutations 17 caught · 0 survived
⛔ the finding  an untested privacy transformation on HEALTH data
```

---

## 0 · Why these two and nothing else

The audit's *"no test names it"* column was wrong **19 of 33 times** and was deleted
([`24-AUDIT`](24-AUDIT-reason-the-column-that-had-to-go.md)). ⛔ **Two modules survived every repair
and then survived being checked by hand**, which is the only reason they are here:

| module | lines | reached by |
|---|---|---|
| `reason/team/away.py` | 187 | `deadline_situations` 1 engine caller · `team_away` 2 |
| `api/identity_routes.py` | 130 | 5 routes, wired in `main.py` |

⛔ Neither was mentioned by any test file by any means — not a path, not a symbol, not a collection.

---

## 1 · ⛔⛔ `team_away` — the module promises health information never leaves it

Its docstring, and then the mapping itself:

> *"**No leave reason ever leaves this module**: windows are reported as who + when; the `sick` kind
> is reported as `leave`."*
>
> `_PUBLIC_KIND = {"sick": "leave"}` — *"Kinds a person may see about a colleague. `sick` is health
> information → reported as leave."*

⛔⛔ **Nothing asserted it.** A one-line change to that dict, or a new kind added to
`AVAILABILITY_KINDS` and not mapped, tells every seat in the org why a colleague is off.

### What the 18 tests pin

⛔ **The emitted vocabulary is DERIVED, never spelled** — from
`contracts/availability.AVAILABILITY_KINDS`, `ABSENT_KINDS` and `_PUBLIC_KIND`. A hand-written list
would stop covering whatever kind was added last. Then:

| | |
|---|---|
| ⛔ **total over the contract** | one parametrised case per kind in `AVAILABILITY_KINDS`: **no kind reaches a colleague as `sick`** |
| ⛔ **it must TRANSFORM, not suppress** | a dropped window would hide that somebody is away at all, which is the information the view exists to give |
| **nothing but who and when** | the fixture really carries a `cover`, a confidence and a fact id; the assertion is that none of them reaches the row |
| **no stale mapping** | `_PUBLIC_KIND`'s keys must exist in the contract |
| **the three other stated rules** | a seatless external person is not listed · the email fallback when the node is unknown · one absence per `(seat, start)` · the stated sort order |

⛔ **No database.** `team_away`'s two collaborators are module-level imports, so the seam is the
module namespace — and the doubles return the **real** `AvailabilityWindow` and `Person`
dataclasses, so a field renamed in production breaks this test rather than passing it.

**Mutations: 7 caught · 0 survived** — including ⛔ removing `_PUBLIC_KIND` entirely, ⛔ making it
*suppress* instead of map, and ⛔ leaking `cover` into the row.

### ⛔ One test of mine was theatre, and was repaired

`test_a_row_carries_only_who_and_when` originally set the field it was about with
`object.__setattr__(...) if hasattr(...) else None` — an expression that asserted nothing. It now
builds a window that really carries a cover and asserts the fixture carries it **before** asserting
the row does not. *A test that cannot observe the thing it names proves nothing.*

---

## 2 · ⛔ `identity_routes` — a destructive operation with ungated gates

The module's own framing:

> *"The resolver never merges. It records that two nodes claim the same key and stops."* …
> *"Merging is destructive (it rewrites who every fact and edge is about), so it is a POST by a
> human, it is transactional, and it is undoable."*

⛔⛔ **The sharpest gate had no test**: a human confirming a proposal about `A` and `B` may send a
body naming `A` and `C`, and only this line stops the engine rewriting every fact and edge about a
node **nobody proposed**:

```python
if {body.survivor_node_id, body.merged_node_id} != pair:
    raise HTTPException(422, {"error": "nodes_do_not_match_proposal", …})
```

### ⛔ The test asserts the merge did not HAPPEN, not that a 422 was raised

> ⛔ **A gate that raises *after* calling `apply_merge` would pass a test that checked the status
> code alone.** So the double records every call and the assertion is that the destructive one was
> never made — and the mutation proves it: moving the merge **above** the gate fails **four** tests
> while still returning 422.

The other 13 cover the tenant boundary (`_org`'s 403 — the only thing between a credential for one
tenant and another tenant's identity queue), the already-decided 409 over three statuses, the
missing-proposal 404, an unconfigured store as 400 rather than an `AttributeError`, ⛔ **the graph's
refusal reason surviving into the response** (a caller told only *"something went wrong"* cannot
correct it), the reject path both ways, the unreversible-merge 404, and that the proposal **count
agrees with the list** — a caller paginating on a count that disagrees skips rows.

**Mutations: 10 caught · 0 survived.**

---

## 3 · Doctrine

| Rule |
|---|
| ⛔⛔ **assert the destructive call did not happen, not that an error was returned** — a gate placed after the act still returns the right status |
| ⛔ **derive the vocabulary from the contract** — a hand-written kind list stops covering the newest kind |
| ⛔ **a privacy transformation must transform, not suppress** — suppression hides the fact as well as the reason |
| ⛔ **a double returns the real dataclass** — a stand-in cannot fail the way a renamed field fails |
| ⛔ **a test that cannot observe the thing it names proves nothing** — mine set a field with a no-op expression |
| **two modules that survive six heuristic repairs AND a hand check are worth testing; the other nineteen were not** |

---

## 4 · What this closes and what it does not

| | |
|---|---|
| ✅ **closes** | step `1.3b`, and with it everything the deleted column left behind |
| ⚠️ **does not close** | `deadline_situations` — `away.py`'s other public function, which builds the P-10 situation. It needs a `TeamContext` and `CommitmentLink` graph to exercise, and that is a fixture, not a gate. ⛔ Named here rather than silently skipped |
| ⛔ **next** | `1.4 capture/` (19 unreceipted tables, 158 files) or **`2.1` Atlas L2's nine claims** — the largest remaining block |
