# Atlas alignment · Layer 5

The Atlas names ten Executive Units plus Coordination and a shared component pipeline. The live
folder now mirrors that hierarchy directly.

| Atlas concept | Documentation location | Code truth |
|---|---|---|
| Units 1–10 and 2.5 | `01-Executive-Units/<unit>/` | `genios_engine/executive/` |
| Input/validator/retriever/etc. | numbered component files inside each unit | mapped to real functions or explicit boundaries |
| Execution state machine | `02-Execution-Lifecycle/01-State-Machine/` | `lifecycle.py` + store guards |
| Multi-owner swimlane | Coordination + Audit/Race Safety | dependency control built; per-action allocator partial |
| ExecutionObject | `03-Contracts-and-Operations/01-Execution-Object-Contract/` | `contracts/execution.py` |
| Persistence/API/tests | `03-Contracts-and-Operations/` | migration 0041, API and focused tests |
| LLM policy | Determinism Policy | no decision authority; grounded copy downstream only |

The Atlas's directory example uses `executive/decision_interpreter/` and similar packages. The
repository uses cohesive modules such as `interpret.py` and `planning.py`. Documentation mirrors
the **architecture**, while code links preserve the actual implementation rather than claiming
nonexistent directories.

## Atlas v3.1 changes that land in this layer

**The unit chain is now drawn as two halves, and that matches the runtime.** Atlas Fig 5.1
previously showed all ten units as one line, which implied Feedback Collection ran before
delivery — impossible, since there is nothing to collect until Layer 5.2 has delivered. The
revised figure splits a synchronous path (Units 1 → 2 → 2.5 → 3 → 4 → 10, ending at emit) from a
watch loop (Units 6 → 8 → 5 → 7 → 9) that runs for as long as the commitment lives. The code was
always shaped this way: `sweep.py` drives the loop, `lifecycle.py` guards the transitions.

| Atlas v3.1 concept | Code truth |
|---|---|
| `audience_intent` is semantic; Layer 5 never names a channel | `AudienceClass` on `PlannedAction` and `CommunicationPlan`. Concrete `channel_id`/`channel_class`/`interrupt` remain as v1/v2 compatibility hints the Layer 5.2 orchestrator deliberately does not read — [LAYER_MAP.md](../../../docs/LAYER_MAP.md) |
| `decision_id` lineage | Richer in code: `decision_hash`, `reasoning_run_id`, `candidate_id`, `context_snapshot_id`, `config_snapshot_id`, `capability_version` |
| Integer basis points | `priority_bp`, `confidence_bp` — the Atlas was corrected to match the code, not the reverse |
| `expires_at` + `success_events` let Layer 5.2 revalidate as a lookup | Both on `execution.v2` (and legacy v1); Layer 5.2 re-reads the stored execution before handing anything to an adapter |
| State machine has `Failed`, `Expired`, `AwaitingApproval` | `lifecycle.py` + store guards; migration `0022` carries the approvals queue |
| `do_nothing_consequence` | `do_nothing_consequence` on `execution.v2` and legacy v1 |

**Envelope coverage:** `org_id` ✅, `schema_version` ✅ (`execution.v2`), `visibility` ✅ — this is
the last layer that carries it as a field — `trace_id` ❌ absent. See
[Cross-Cutting · 06-Atlas-Envelope-Alignment.md](../../Cross-Cutting-Contracts-Platform-API/06-Atlas-Envelope-Alignment.md).
