# 7 · Adaptive Evolution

**Status:** Built

Creates Adaptive Brain proposals from explicit current-operating preferences. A closed category set
keeps short-horizon personalization distinct from stable Behavior Brain claims.

| Boundary | Value |
|---|---|
| Input | Preference proposals in priority, notification, execution-preference or runtime-personalization categories |
| Derivation | deterministic namespace/target change with unchanged evidence |
| Output | Adaptive-target LearningObject with parent lineage and unchanged private subject cap for user scope |
| Primary code | `feedback/units.py::adaptive_evolution` |
| Integration requirement | lower reasoning/execution layers need an Adaptive Brain reader/materializer |

## Atlas-named component map

| Atlas component | Live implementation |
|---|---|
| Adaptive Analyzer | closed current-operating category filter |
| Adaptive Confidence | inherited evidence plus Unit 11 policy validation |
| Preference Updater | versioned tenant+subject Adaptive entry |
| Adaptive Publisher | shared Evolution Publisher |

## Component modules

1. [Input, validation and retrieval](01-Input-Validation-and-Retrieval.md)
2. [Analysis, calculation and evaluation](02-Analysis-Calculation-and-Evaluation.md)
3. [Builder, publisher and output](03-Builder-Publisher-and-Output.md)
