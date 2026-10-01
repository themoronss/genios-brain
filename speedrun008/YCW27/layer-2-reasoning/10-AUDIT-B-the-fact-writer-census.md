# L2 · B — `core.policy` and `core.signal_composition` · audit, cross-check, then execute

**Written for:** Rohit and Harsh (CTO). **Date:** 2026-10-01.
**Reads with:** `07-DOES-IT-ACTUALLY-WORK.md`, `09-AUDIT-the-lost-axis-receipt.md`.
**Method:** one `set transaction read only` connection to production. No writes, no model.

---

# ⛔ PART 0 · B4 AND B5 ARE BOTH MIS-STATED IN `07`, AND NEITHER IS WHAT I SAID

## B5 · *"`core.signal_composition` is registered and scheduled by nothing"* — **false**

`packs/capabilities/deal_health.py:16` schedules it, and three other units in that manifest depend on
it. `reason/authority.py:40` names it in a SQL ordering.

**It is scheduled by `DEAL_HEALTH_V1`, which is not in `BUILTIN_CAPABILITIES`** —
`BUILTIN_CAPABILITIES = (DEAL_COOLING_V1,)`. Same shape as `DEAL_COOLING_FULL_V2`: defined, usable,
deliberately unswept.

⛔ **So B5 is not a defect. It is `ALARM A2` again** — a capability built and not activated. Nothing to
fix at this layer; it is an activation with a runbook, and Rohit's call.

## B4 · *"`core.policy` is the unit the Organisation-Brain lever works through"* — **incomplete**

I had earlier said the lever reaches `core.constraint`. Both are true, and they are **two different
levers**:

| path | reaches | effect |
|---|---|---|
| `blocked_play_ids` | `core.constraint` | eliminates plays **before ranking** |
| `approval_config` | **`core.policy`** | `expertise.py:788` — *"THE ORGANISATION'S OWN APPROVAL BAR, for the one unit built to enforce it"* |

So `core.policy` matters more than I said, and the rest of B4 is worse than I said.

## And one correction to `B3`

I wrote *"`deal.status` has no writer."* Measured: **`deal.status` has 3 rows.** A writer exists and it
has written three facts. *"No writer"* and *"a writer that reached 3 of 293 nodes"* are different
problems with different fixes, and I stated the first.

---

# PART 1 · THE AUDIT — what, how, why, in what manner

## 1.1 · WHAT · `core.policy`'s four essential facts have ZERO rows

```
deal.value                0 rows    ⛔
deal.approval_status      0 rows    ⛔
contact.do_not_contact    0 rows    ⛔
contact.consent_status    0 rows    ⛔
```

Its roster entry makes **all four `essential`**, and the selector drops a unit when *every* declared
field is missing. **So `core.policy` is skipping correctly, on every run, forever.**

## 1.2 · HOW · and it is not one unit's problem — the census

Every fact path `expertise._ROSTER` binds a unit to, against production:

```
  22 paths bound
⛔ 14 with ZERO rows
```

| present | rows | | absent — **all 14** |
|---|---|---|---|
| `thread.last_outbound` | 206 | | `approval.status` · `finance.approval_status` · `legal.review_status` |
| `thread.last_inbound` | 198 | | `procurement.status` · `security.review_status` |
| `derived.engagement` | 174 | | `deal.value` · `deal.owner` · `deal.approval_status` |
| `derived.momentum` | 174 | | `deal.close_date` · `deal.last_outbound` |
| `meeting.start_at` | 49 | | `contact.do_not_contact` · `contact.consent_status` |
| `deal.last_inbound` | 34 | | `calendar.next_meeting_at` · `schedule.quiet_until` |
| `commitment.due_at` | 30 | | |
| `deal.status` | **3** | | |

⛔ **Every present path is `thread.*`, `derived.*`, `commitment.due_at`, `meeting.start_at`. Every
`deal.*` path beyond `status` (3 rows) and `last_inbound` (34) is empty.** One root: **there is no CRM
connector**, so the deal object barely exists.

**What that starves, unit by unit:**

| unit | starved by |
|---|---|
| `core.policy` | all four of its essential fields |
| `core.dependency` | all five gate fields |
| `core.impact` | `deal.value` — and `core.relationship`'s 3-row `deal.status` for its fallback |
| `core.opportunity` | `deal.owner`, `deal.last_outbound` |
| `core.resource` | `deal.close_date`, `deal.owner` |
| `core.scheduling` | `calendar.next_meeting_at`, `schedule.quiet_until`, `deal.close_date` |

## 1.3 · WHY the existing receipt is not enough

`no_declared_input_available` is already recorded per skip. ⛔ **But it conflates two facts with
different movers:**

| it says | it could mean | mover |
|---|---|---|
| this situation did not carry the field | the field exists; this node lacks it | **data coverage** — a sync, a backfill |
| nothing has ever written the field | no writer exists anywhere in the product | **a connector that does not exist** |

A reader cannot tell them apart, and the second is **not fixable by looking at the situation at all.**
`core.policy` has been reporting the first for 165 rows while the truth is the second.

## 1.4 · IN WHAT MANNER · one declaration, extended — not a parallel module

`reason/unit_health.py` already declares *"a unit that completes and says nothing"*, with a reason, a
mover, a share and a date. **A fact path nothing writes is the same doctrine at a different grain** —
*every silent lane carries a reason and a mover* — and a reader looking for *what is declared absent*
must find **one** file.

⛔ **So it extends `unit_health`, and does not become `fact_health`.** A second module would be a
second place to look, and the fifth time this programme has found two declarations of one idea.

---

# PART 2 · THE PLAN — 4 units, bottom-up

```
level 0 ·  U01  the fact declaration        reason/unit_health.py  (extended)
level 1 ·  U02  the census probe            scripts/l2_fact_writers.py
           U03  the receipt                 platform/receipts.py
level 2 ·  U04  the guard                   tests/
```

## `U01` · declare the unwritten facts, with a mover each

`DECLARED_UNWRITTEN: Mapping[str, UnwrittenFact]` — path → `(reason, mover, bound_by, measured_on)`.

⛔ **`bound_by` is required and is the point.** `deal.value` is bound by `core.impact.value_field` AND
`core.policy.approval_value_field`; naming both is what tells a reader how much one missing connector
costs. A declaration that only named the path would be a list of strings.

⛔ **And the mover is a CONNECTOR, not a person for most of these.** Fourteen paths, essentially one
mover: *a CRM connector that writes the deal object*. Saying that once, against fourteen paths, is the
finding.

## `U02` · the census probe

`scripts/l2_fact_writers.py` — read-only. For every path the roster binds: rows in `graph_facts`, the
units bound to it, and whether it is declared. **Exits non-zero on an undeclared empty path.**

⛔ **It derives the path list from `_ROSTER`, never a copy.** A seventh role added to a unit appears in
the census without an edit — which is the rule `S5.U02` established for `AXIS_SOURCES`.

## `U03` · the receipt

> *"every fact path a reasoning unit binds is either written or declared unwritten"*

`expect: n == 0`. ⛔ **Passes today** (all 14 declared) and **fails when a 15th goes empty** — a
regression nobody would otherwise see, because an emptying fact path produces no error anywhere.

⛔ **Not *"no bound path is empty"***, for the reason `08` established: `api/routes.py:161` computes
`ready = not failed`, and a permanently-red gate is a gate nobody reads. 14 of 22 are empty for a
reason this layer cannot clear.

## `U04` · the guard

1. every declared path has a reason, a mover, a `bound_by` and a date — refused if empty
2. every declared path **is actually bound by the roster** — a declaration for a path nothing reads is
   dead paperwork
3. the probe and the receipt read **one** declaration; no third copy exists
4. the path list is **derived from `_ROSTER`**, asserted by AST

---

# PART 3 · WHAT THIS DOES NOT DO

| | Why |
|---|---|
| write a CRM connector | that is the mover for 14 of the 14, and it is not this layer |
| schedule `DEAL_HEALTH_V1` | B5 is `ALARM A2` — an activation, Rohit's call |
| relax `core.policy`'s `essential` roles | it would then run on nothing and publish nothing, which is `core.impact`'s defect imported |
| assert *"no bound path is empty"* | permanently red for a reason this layer cannot clear |

---
---

# PART 4 · EXECUTED — 2026-10-01

**4 units + 1 unplanned fix. 66 tests. 29 receipts (was 28). No migration, no version bump.**

| unit | artifact |
|---|---|
| `U01` | `reason/unit_health.py` **extended** — `UnwrittenFact`, `DECLARED_UNWRITTEN` (14), `roster_fact_paths()` |
| `U02` | `scripts/l2_fact_writers.py` — the census, read-only |
| `U03` | `platform/receipts.py` — the receipt |
| `U04` | `tests/reason/test_a_bound_fact_with_no_writer_is_declared.py` — **59 tests** |
| ⛔ **+1** | `platform/receipts.py::evaluate()` — **a defect found by running it** |

## ⛔ The census, and it is one root

```
bound: 22   written: 8   empty: 14   declared: 14
```

**Five movers cover all fourteen:**

| mover | paths |
|---|---|
| **Harsh — an approval-workflow source** | 6 · `approval.status`, `deal.approval_status`, `finance.approval_status`, `legal.review_status`, `procurement.status`, `security.review_status` |
| **Harsh — a CRM connector** | 4 · `deal.value`, `deal.owner`, `deal.close_date`, `deal.last_outbound` |
| **Rohit — whether this product holds consent state at all** | 2 · `contact.do_not_contact`, `contact.consent_status` |
| Harsh — a forward calendar projection | 1 · `calendar.next_meeting_at` |
| Harsh — a quiet-window writer | 1 · `schedule.quiet_until` |

⛔ **A test asserts the movers are GROUPED** (`len(movers) <= 6`). If every path named its own private
mover a reader would see fourteen problems instead of the five that exist — **and the CRM connector
alone unblocks four.**

## ⛔ AND RUNNING IT FOUND A DEFECT IN THE RECEIPT MECHANISM ITSELF

```
before:  {'PASS': 12, 'FAIL': 4, 'ERROR': 13}   of 29
after:   {'PASS': 20, 'FAIL': 8, 'ERROR':  1}   of 29
```

Migration `0190` is unapplied, so the L5 lane receipt raised `UndefinedColumn` — **correctly, once.**
Then **twelve** further receipts reported `InFailedSqlTransaction`, because SQLAlchemy opens an implicit
transaction on first use and a failed statement leaves it invalid for everything after it on the same
connection.

> ⛔ **Twelve phantom ERRORs were hiding four real FAILs and one real ERROR.** `api/routes.py:161`
> computes `ready = not failed`, so the operator page said thirteen things were broken when one was —
> **and named the wrong twelve.**

⛔ **The same defect `domain_shadow` already fixed for its own loop**, whose comment is the diagnosis:
*"ONE connection serves the whole loop … a single bad situation silently takes every situation after it
… The six missing situations were not unroutable; **they were never attempted**."*

Fixed with an unconditional `c.rollback()` in **`finally`**, not `except` — because a receipt whose
query *succeeds* also leaves an open implicit transaction, and resetting only on the failure path would
attribute the next failure to whichever receipt happened to be running. **7 tests**, driven through a
connection that genuinely goes invalid rather than a stub that forgives the second statement.

### What those four real FAILs are — now visible for the first time

| | |
|---|---|
| L1 | the parked queue is not a black hole · drops we might be wrong about · attachments carry readable text |
| L4 | at least one seat has a manager · the score components are measured, not placeholders |
| L6 | cards carry a written draft, not a template stub · a channel this tenant can be reached on |
| L7 | a human verdict has reached the loop |

⛔ **None of these is new breakage.** They were failing before and were invisible behind the cascade.

## The two corrections to `07`, pinned as tests

| `07` said | Truth | pinned by |
|---|---|---|
| `core.signal_composition` is *"scheduled by nothing"* | `deal_health.py:16` schedules it; `DEAL_HEALTH_V1` is simply **not swept** — `ALARM A2`, not a defect | `test_core_signal_composition_IS_scheduled_by_a_capability` |
| `deal.status` has *"no writer"* | it has **3 rows**. A writer that reached 3 of 293 nodes is a **coverage** problem, not an absent connector | `test_deal_status_is_bound_and_is_not_declared_unwritten` |

## Decisions worth defending

⛔ **`unit_health` extended, not a `fact_health` module.** *Every silent lane carries a reason and a
mover* is one doctrine at two grains. A reader looking for *what is declared absent* must find **one**
file; a second module would be the fifth instance of two declarations of one idea here. A test asserts
`reason/fact_health.py` does not exist.

⛔ **`bound_by` is required, and compared against the roster.** It is written by hand and
`roster_fact_paths()` is derived — so a test asserts they are **equal per path**, because two lists that
should agree and are never compared eventually disagree.

⛔ **`core.policy` is NOT relaxed.** Dropping an `essential` role would make it run on nothing and
publish nothing — which is `core.impact`'s defect, imported.

## What is still open

| | |
|---|---|
| 🔴 | **`0190` unapplied** — the one true ERROR on the receipts page. **Harsh** |
| 🔴 | **a CRM connector** — unblocks 4 paths, `core.impact`, `core.opportunity`, `core.resource`, and `cost_vs_benefit`. **Harsh** |
| 🔴 | **an approval-workflow source** — unblocks 6 paths and `core.policy` entirely, which is where the Organisation Brain's approval bar lands. **Harsh** |
| 🟠 | **consent state** — does this product hold it at all? **Rohit** |
| 🟠 | **`ALARM A2`** — `DEAL_HEALTH_V1` and the 20-unit roster are built and unswept. **Rohit** |
| 🟠 | the 8 real receipt FAILs, now visible | each is its own finding |
