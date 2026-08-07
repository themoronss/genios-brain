# Part 1 · Executive Units

The Atlas defines ten Executive Units plus **2.5 Execution Coordination**. Each child directory is
one unit. Its README explains the unit as a whole; the numbered files map the shared component
pipeline into the actual code:

```text
Input → Validator → Retriever → Analyzer/Planner → Calculator → Evaluator → Builder/Executor → Output
```

| Unit | Folder | Status | Primary authority |
|---|---|---|---|
| 1 | [Decision Interpreter](01-Decision-Interpreter/README.md) | Built | `interpret.py` |
| 2 | [Execution Planning](02-Execution-Planning/README.md) | Built | `planning.py` |
| 2.5 | [Execution Coordination](03-Execution-Coordination/README.md) | Partial | `coordination.py` |
| 3 | [Communication Planning](04-Communication-Planning/README.md) | Built | `communication.py`, `assignment.py` |
| 4 | [Execution Validation](05-Execution-Validation/README.md) | Built | `execution_guard.py` |
| 5 | [Reminder](06-Reminder/README.md) | Built | `reminder.py` |
| 6 | [Monitoring](07-Monitoring/README.md) | Built | `monitor.py` |
| 7 | [Escalation](08-Escalation/README.md) | Built | `escalation.py` |
| 8 | [Execution Tracking](09-Execution-Tracking/README.md) | Built | `lifecycle.py`, `execution_store.py` |
| 9 | [Feedback Collection](10-Feedback-Collection/README.md) | Built | `collect.py` |
| 10 | [Execution Object Builder](11-Execution-Object-Builder/README.md) | Built | `execution.py` |

The Atlas pipeline is a reasoning aid, not permission to invent one Python file per box. A
component file below says whether that box is a distinct function, a composition inside the unit,
an injected dependency, or an intentional boundary.
