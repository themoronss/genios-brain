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
