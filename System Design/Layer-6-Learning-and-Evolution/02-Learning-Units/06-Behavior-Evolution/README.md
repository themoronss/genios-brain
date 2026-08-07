# 6 · Behavior Evolution

**Status:** Built

Creates Behavior Brain proposals only from explicit preferences in a closed behavior-category set.
It preserves the parent evidence exactly and makes no personality claim beyond the structured
preference that was actually observed.

| Boundary | Value |
|---|---|
| Input | Preference proposals in communication, decision, meeting, execution or relationship categories |
| Derivation | deterministic namespace/target change; no new evidence or source query |
| Output | Behavior-target LearningObject with `derived_from` parent ID and unchanged private subject cap for user scope |
| Primary code | `feedback/units.py::behavior_evolution` |
| Integration requirement | lower reasoning/execution layers need a Behavior Brain reader/materializer |

## Atlas-named component map

| Atlas component | Live implementation |
|---|---|
| Behavior Analyzer | closed behavior-category filter over explicit preference proposals |
| Behavior Drift | immutable versions/supersession expose changed values; no speculative drift model |
| Behavior Confidence | inherited grounded evidence, revalidated by Unit 11 |
| Behavior Publisher | shared versioned Evolution Publisher |

## Component modules

1. [Input, validation and retrieval](01-Input-Validation-and-Retrieval.md)
2. [Analysis, calculation and evaluation](02-Analysis-Calculation-and-Evaluation.md)
3. [Builder, publisher and output](03-Builder-Publisher-and-Output.md)
