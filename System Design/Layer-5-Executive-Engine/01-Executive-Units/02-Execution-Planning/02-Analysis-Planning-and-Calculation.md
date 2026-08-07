# Analyzer, Planner and Calculator

## Analyzer / Planner

Steps are classified by a fixed verb lexicon, dependencies are normalized into a DAG, waves are derived, and deadlines are calculated from the declared window.

## Calculator

`plan_actions` and `plan_is_autonomous` are the planning authority. A model does not reorder work or reinterpret an approval boundary.

## Determinism

The same frozen input and evaluation time produce the same result. Ordering, ties and thresholds
are explicit in code and are covered by focused tests; an LLM is not an alternate execution path.
