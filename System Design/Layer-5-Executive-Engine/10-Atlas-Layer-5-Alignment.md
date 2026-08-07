[Bugs, Runbook and Gaps](09-Bugs-Runbook-and-Gaps.md) · [Folder map](README.md) · [System Design index](../README.md)

---

# Atlas Layer 5 Alignment

This page reconciles the Atlas contract with the runtime code. Code, migrations and executed
tests are evidence; folder names are not.

## Verdict — 92% aligned

The ten Atlas units exist and the operational chain is deterministic. Unit 2.5 now coordinates
dependency waves at runtime, the full live-work state machine is reachable, blocked work can
escalate, resolved escalation targets receive the actual message, and transport success is no
longer confused with queue admission.

The remaining 8% is explicit: concrete per-action multi-owner seat/agent allocation, batching
digest-planned commitment reminders, Redis acceleration, and live-Postgres execution proof.
The earlier `execution_outcomes` integration gap is closed by Atlas Layer 6 learning.

## Unit-by-unit evidence

| Atlas unit | Runtime implementation | Status |
|---|---|---|
| 1 · Decision Interpreter | `interpret.py` | ✅ Built |
| 2 · Execution Planning | `planning.py` | ✅ Built |
| 2.5 · Execution Coordination | `coordination.py`; dependency-gated action API | 🟡 Core built; concrete multi-owner allocation remains |
| 3 · Communication Planning | `communication.py`, `assignment.py` | ✅ Built |
| 4 · Execution Validation | `execution_guard.py`, pre-send Layer 5.2 recheck | ✅ Built |
| 5 · Reminder | `reminder.py` | ✅ Built |
| 6 · Monitoring | `monitor.py`, observed-event reads | ✅ Built |
| 7 · Escalation | `escalation.py`, live target resolution in `sweep.py` | ✅ Built |
| 8 · Execution Tracking | `lifecycle.py`, `execution_store.py`, five execution tables | ✅ Built |
| 9 · Feedback Collection | `collect.py`, `execution_outcomes`, `feedback/store.py` | ✅ Written and consumed by Outcome / Recommendation / Knowledge learning |
| 10 · Execution Object Builder | `execution.py`, `contracts/execution.py` | ✅ Built |

## State-machine reconciliation

```text
Created → Pending → Running ↔ Waiting
                    ↕
                  Blocked

Open states → Completed / Cancelled / Expired → Archived
```

- `Created → Pending` means **validated and queued**, matching the Atlas. It emits
  `execution.queued`.
- `RUNNING`, `WAITING` and `BLOCKED` can be recorded through the owner-only transition API.
- Action completion cannot jump over unmet dependencies.
- Ordinary reminders stop while blocked, but due escalation rungs remain active.
- All terminal outcomes can only move to `ARCHIVED`; reopening requires a new decision.
- Layer 5.2 adapter success alone sets `delivered_at` and emits
  `execution.delivery_confirmed`.

## Fixes made during this reconciliation

| Defect | Runtime correction |
|---|---|
| Coordination existed only as build-time stages | Added a recomputable coordination projection and dependency-enforced completion |
| `BLOCKED` existed in the enum but had no mutation path | Added owner-only live-state transitions |
| Guard suppression prevented blocked escalation | Blocked state now proceeds to reminder policy; only due rungs may speak |
| Cooldown/fatigue could suppress a promised escalation | Due ladder rungs now outrank ordinary-reminder limits |
| Manager/executive was resolved but message still targeted owner | Resolved target/audience/interrupt now travel on the reminder event into the outbox |
| `EXPIRED → RUNNING` rewrote a terminal outcome | Removed reopening; expired can only archive |
| `PENDING` falsely stamped transport delivery | Split `execution.queued` from `execution.delivery_confirmed` |
| A lost escalation race could still emit a duplicate reminder | Losing worker now reschedules without creating an event |
| An action could be ticked before execution validation | Completion now requires a live open state, never `CREATED` |

## Intentional implementation choices

- The Atlas says PostgreSQL + Redis for reminders and runtime cache. The current due queue is a
  PostgreSQL indexed scan. It is correct and persistent but has no Redis acceleration yet.
- Layer 5 authors the communication and escalation intent. Layer 5.2 owns adapters, admission,
  retries and delivery results. This preserves the repository's downward-only import topology.
- The Atlas names a `Feedback Object → Layer 6`; this implementation persists the stronger
  immutable `execution_outcomes` record. Code Layer 7 (Atlas Layer 6) consumes it without an
  upward import by reading the durable seam.

## Verification

- Coordination, lifecycle, reminder, escalation recipient, API and bridge scenarios execute in
  the automated suite.
- Static schema tests check Layer 5 SQL against migrations and missing binds.
- A real PostgreSQL migration/integration run is still required before production rollout.

---

[Bugs, Runbook and Gaps](09-Bugs-Runbook-and-Gaps.md) · [Folder map](README.md) · [System Design index](../README.md)
