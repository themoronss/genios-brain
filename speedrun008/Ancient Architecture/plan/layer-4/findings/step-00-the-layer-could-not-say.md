# L4-00 findings · the executive layer could not say which silences were deliberate

**2026-09-25** · +12 tests · `13,313 passed` · 0 regressions · 8/8 mutations caught · **no migration**

---

## 1 · The premise, checked before any code

Layer 3's pattern was *"built and never switched on"* — twelve times. **The expectation going in was
that Layer 4 would be the same.**

**Measured, it is the opposite.**

| | |
|---|---|
| `sweep.run_executive` | ✅ called from `api/routes.py:1150`, **every org, every heartbeat tick**, before distribution |
| `plan_commitments` | ✅ turns authoritative decisions into `executions` |
| `run_lifecycle` | ✅ validate → transition → remind → escalate → close |
| `record_outcome` | ✅ `sweep.py:259` — Layer 7's feed |
| tables | ✅ 5 (migration **0041**) + delegation (**0157**), both applied |
| `deliver/` integration | ✅ imports assignment, communication, lifecycle, execution_store, summary |
| tests | ✅ 14 files, 197 tests |

⛔ **The execution half is done.** The step that was going to be *"switch Layer 4 on"* does not
exist, because it is on.

---

## 2 · What was actually missing

**Every other layer can say which of its silences are deliberate:**

```
reason/uncited_lanes.UNCITED_LANES          reason/situation_binding.SIGNAL_WRITERS
context/lane_health.DORMANT_LANES           patterns/routing.UNROUTED_PATTERN_TYPES
```

⛔ **`executive/` had nothing of the kind.** So a public function with no caller was
indistinguishable from an oversight — and it turns out **two of them are real gaps and four are
correct**, which is exactly the distinction a reader could not make.

---

## 3 · ⛔ Six unreached functions. Two are real product gaps.

| function | verdict |
|---|---|
| ⛔ **`monitor.blocking_action`** | **REAL GAP.** *"'Your Acme follow-up is **stuck on getting it approved**' is a message somebody can act on; 'your Acme follow-up is **stalled**' is a message somebody can only feel bad about."* Measured: `escalation.py` and all of `deliver/` contain **no blocking-step reference**, so every stalled escalation is the second sentence. ⛔ **No tests either** — the weaker of the two unreached states |
| ⛔ **`assignment.resolve_approver_seat`** | **REAL GAP.** `requires_approval` **is** read — `contracts/execution.py:233` gates autonomy on it — but nothing resolves **who signs**. Its docstring predicted the symptom: *"a card that says 'this needs sign-off' and cannot say whose is less useful than one that can."* 8 tests, 0 live callers |
| `coordination.can_complete` | **Correctly dead.** The live route calls `dependencies_met` instead, because *"an already-completed or unknown id falls through to the store, which is idempotent and returns `recorded=false` rather than a 409"* — routing an idempotent re-submit through `can_complete` would turn a double-click into an error |
| `coordination.coordination_snapshot` | No reader. The shape a *"what can I do next"* view would read; that view has not been asked for |
| `execution.build_from_decision` | ⛔ **An alternative entry shape, not a bypassed gate — and the distinction took a measurement.** Its docstring reads as though the sweep should use it. It does not: this starts from a decision OBJECT via `interpret_decision`, the sweep starts from a SQL ROW via `build_context`. **Both run the identical `resolve_owner → build_execution` tail**, so the ordering the docstring protects is not at risk |
| `lifecycle.is_terminal` | Trivial predicate over `TERMINAL_STATES`. Kept so the closed set does not acquire a second inline spelling. **No tests** |

## 3.1 · Five surfaces are PULL-ONLY — a different claim from unreached

| surface | route | |
|---|---|---|
| ⛔ **`modes.load_preventive`** | `GET /preventive` | **THE USP.** `modes.py` names it *"the vision's USP"*. Measured: `deliver/` has **zero** references to preventive, so **no preventive finding has ever become a card** |
| **`brief.load_briefs`** | `GET /briefs` | `brief.py` calls it *"the executive unit of output"*; nothing composes one on a tick |
| `summary.build_summary` | `GET /summary` | closest to pushed — `deliver/outbox.py:315` imports it |
| `memory` | `GET /memory` | working context, never carried forward automatically |
| `explain.why_not` | `GET /why-not` | ⛔ **correctly pull** — a receipt for a silence is asked for, never volunteered |

---

## 4 · ⛔ Two defects the guard found in its own first measurement

### 4.1 Aliased imports read as dead — the exact false verdict it exists to prevent

`deliver/actions.py` does:

```python
from genios_engine.executive.execution_store import link_card as _link_execution_card
```

…and calls the **alias**. The first scan counted only the bare name and reported `link_card` — a
function on the **live card-completion path** — as unreached.

⛔ **The guard made the mistake it was built to catch.** Every renamed import is now resolved back
to its original name before counting.

### 4.2 O(functions × files) — a guard too slow to run is one people skip

The first version called `call_sites` once per candidate, re-parsing ~600 engine modules for each
of ~80 public functions — roughly **48,000 AST parses**, minutes per run.

**Now one pass: 2 seconds.** Same answer.

---

## 5 · A declared UNKNOWN, not a finding

Module docstrings number the units 1, 2, 2.5, 3, 4, 5, 7, 9, 10. `assignment`, `escalation` and
`execution_guard` carry no number. **6 and 8 are absent** — but **three unnumbered files and two
gaps do not divide.**

⛔ **No conclusion drawn, deliberately.** The L5 spec that assigned these numbers is not in this
repository, and **L3-17 is the standing lesson**: `prior_decision 0` was a grep, and the capability
it declared missing had been running on every sweep for months. **An absent number is not an absent
unit.**

---

## 6 · Technique 3 — 8/8

| # | mutation | result |
|---|---|---|
| 1 | a declaration disappears | ✅ RED |
| 2 | a stale declaration stays | ✅ RED |
| 3 | alias resolution breaks (`link_card` reads as dead) | ✅ RED |
| 4 | a mover is dropped | ✅ RED |
| 5 | definitions count as calls | ✅ RED |
| 6 | `public_functions` returns private ones too | ✅ RED |
| 7 | the guard stops excluding itself | ✅ RED |
| 8 | `deliver/` starts referencing preventive | ✅ RED |

---

## 7 · ⛔ A measurement I got wrong and corrected before publishing

**`planning.py` is not untested.** Grepping the test tree for `plan_actions` returned **zero**,
which read as *"Unit 2, 354 lines, no tests"*. Tracing execution showed **162 of 275 lines run**.

> *"No test names it"* and *"no test runs it"* are different claims, and only one of them was
> measured.

**Eleventh appearance of the blunt-grep family on this branch.** The coverage table in
`00-STATUS.md` is traced, not grepped, for exactly this reason.

Also corrected: the suppression-reason count is **six**, not five — the sixth is `situation`.
