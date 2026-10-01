# Layer 4 (Executive) — STATUS

**Branch `speedrun008` · audited 2026-09-25 · `13,313 passed · 0 regressions`**

> ## ⛔ IS LAYER 4 COMPLETE? **NO — but not in the way Layer 3 was incomplete.**
>
> **The execution half runs in production on every heartbeat tick.** It is not waiting to be
> switched on. What is missing is: two real product gaps, one module with no coverage, two
> surfaces that are built but never pushed, and the org data and policy confirmations that only
> Rohit can supply.
>
> **Nothing here is a rewrite. Every item is small and most are blocked on a decision, not on code.**

**Folder:** [`01-WHAT-HARSH-DOES.md`](01-WHAT-HARSH-DOES.md) — Harsh's list ·
[`02-THE-REMAINING-STEPS.md`](02-THE-REMAINING-STEPS.md) — the seven steps, step by step ·
⛔ [`03-PRODUCTION-READINESS.md`](03-PRODUCTION-READINESS.md) — **safe vs useful, and the one real risk** ·
[`PENDING-layer-4-executive-analysis.md`](PENDING-layer-4-executive-analysis.md) — the analysis ·
[`findings/`](findings/) — per-step findings

---

## The step table

| step | what | status |
|---|---|---|
| **L4-00** | [The layer can say which of its silences are deliberate](PENDING-layer-4-executive-analysis.md) | ✅ **COMPLETE** · +12 tests · 8/8 mutations · 0 regressions. `executive/unreached.py` declares **6 unreached functions** and **5 pull-only surfaces**, checked both directions. ⛔ Found **2 real product gaps** and **2 defects in its own first measurement** (aliased imports read as dead; 48,000 AST parses → one pass) |
| **L4-01** | ⛔ `explain.py` has **0% coverage** | **NOT STARTED** · no decision needed |
| **L4-02** | `assignment.py` coverage — **49%**, and it is the largest module (496 lines) | **NOT STARTED** · no decision needed |
| **L4-03** | `planning.py` coverage — **58%** | **NOT STARTED** · no decision needed |
| **L4-04** | ⛔ **Escalation names the step it is stuck on** (`monitor.blocking_action`) | ⛔ **PREMISE CORRECTED — buildable today, NOT blocked.** First planned as *"needs a rung field + a migration"*. Measured: `target_seat` is already resolved at FIRE time, and `record_reminder` already carries a `facts` payload. **The fix is ONE KEY in `reminder_facts`** — which today says `next_action: first_action.label`, the wrong step on a partly-done commitment. **REAL GAP, small fix** |
| **L4-05** | ⛔ **An approval routes to an approver** (`assignment.resolve_approver_seat`) | **BLOCKED** on org authority rules · **REAL GAP** |
| **L4-06** | ⛔ **Preventive warning → card** | **BLOCKED** on Rohit's threshold decision (C1) |
| **L4-07** | **Brief → pushed or pull-only** | **BLOCKED** on Rohit's decision (C2) |
| **L4-08** | Unit 6 / Unit 8 numbering | **DECLARED UNKNOWN** — the L5 spec is not in this repo |

---

## ⛔ Measured coverage, module by module

Traced by executing all 14 `test_executive*.py` files and counting lines actually run — **not by
grepping test files for names**, which reported `planning.py` as untested when 162 of its 275 lines
execute. *That mistake is the blunt-grep family's eleventh appearance on this branch.*

| module | lines run | total | % | |
|---|---|---|---|---|
| **explain** | **0** | 47 | **0%** | ⛔ **L4-01** |
| **assignment** | 244 | 496 | **49%** | ⛔ **L4-02** — biggest module |
| **planning** | 162 | 275 | **58%** | L4-03 |
| escalation | 82 | 133 | 61% | |
| coordination | 44 | 68 | 64% | |
| monitor | 77 | 113 | 68% | |
| interpret | 202 | 295 | 68% | |
| reminder | 106 | 155 | 68% | |
| brief | 132 | 192 | 68% | |
| collect | 143 | 199 | 71% | |
| modes | 116 | 160 | 72% | |
| memory | 41 | 78 | 52% | |

---

## What is NOT broken — checked, so nobody re-audits it

| | state |
|---|---|
| the sweep runs on every tick | ✅ `api/routes.py:1150`, every org, before distribution |
| commitments are planned from authoritative decisions | ✅ `plan_commitments` |
| validate → transition → remind → escalate → close | ✅ `run_lifecycle` |
| outcomes reach Layer 7 | ✅ `record_outcome` at `sweep.py:259` |
| tables | ✅ 5 tables (migration **0041**) + delegation (**0157**) — **both already applied, neither is in the pending migration list** |
| delegation / agent verbs | ✅ `api/delegation_routes.py` + MCP |
| `deliver/` integration | ✅ imports assignment, communication, lifecycle, execution_store, summary |
| tests | ✅ 14 files, 197 tests, all green |

---

## ⛔ The dependency that gates everything

`plan_commitments` reads `AUTHORITATIVE_SIGNAL_PREDICATE` — **seven conditions**, all required:

```
audited reasoning run · active pack authority · matching authority revision
matching config version · run completed after the pack's last update
signal still open · authority not expired
```

**Until Admin is activated (Layer 3's P3), Layer 4 examines nothing and creates nothing.** It is
running correctly and finding an empty queue.

⛔ **`SweepReport.reasons` is the first number to read once Admin is live** — it counts refusals
*by reason*, and its own docstring says why that matters:

> *"A sweep that plans nothing because every decision was `no_action` is healthy; one that plans
> nothing because every build hit `window_closed` is a misconfigured pack, and a single 'skipped'
> counter cannot tell those apart."*
