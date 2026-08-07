# Brain Resolver

**Status:** Built

Restricts every proposal to an enum-backed destination chosen by its unit. The implementation
separates Atlas brains from non-brain publication sinks so telemetry and review work cannot be
mistaken for learned brain state.

| Boundary | Current truth |
|---|---|
| Atlas `BrainTarget` | Organization, Behavior, Adaptive, Runtime |
| Wider `LearningTarget` | four brains plus Metrics and Knowledge Suggestion |
| Durable learned-brain table | Organization, Behavior and Adaptive only |
| Runtime | temporary, TTL-bound memory table |
| Non-brain sinks | metrics ledger and human-review suggestion queue |
| Authority | `contracts/learning.py`; unit builders; `feedback/store.py::publish` |

There is no Expert target, publisher branch or table-routing escape hatch. Knowledge Evolution can
only create `knowledge_suggestion`.

## Component modules

1. [Input and selection context](01-Input-and-Selection-Context.md)
2. [Policy and decision](02-Policy-and-Decision.md)
3. [Output, edge cases and gaps](03-Output-Edge-Cases-and-Gaps.md)
