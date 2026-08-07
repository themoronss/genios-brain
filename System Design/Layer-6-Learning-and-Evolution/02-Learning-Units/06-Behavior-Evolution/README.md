# 6 · Behavior Evolution

**Status:** Partial

Separates stable behavior-shaped preferences into Behavior Brain provenance.

| Boundary | Value |
|---|---|
| Input | Preference Learning objects in communication, decision, meeting, execution or relationship categories |
| Output | Behavior-target LearningObject derived from the preference object |
| Primary code | `feedback/units.py::behavior_evolution` |
| Honest gap | Publisher and versioning are built, but no generic lower-layer Behavior Brain consumer exists. |

## Atlas-named component map

| Atlas component | Live implementation |
|---|---|
| Behavior Analyzer | closed behavior-category filter over explicit preference proposals |
| Behavior Drift | no dedicated drift detector; version supersession only prevents two active values |
| Behavior Confidence | inherited grounded evidence, revalidated by Unit 11 |
| Behavior Publisher | shared versioned Evolution Publisher |

## Component modules

1. [Input, validation and retrieval](01-Input-Validation-and-Retrieval.md)
2. [Analysis, calculation and evaluation](02-Analysis-Calculation-and-Evaluation.md)
3. [Builder, publisher and output](03-Builder-Publisher-and-Output.md)
