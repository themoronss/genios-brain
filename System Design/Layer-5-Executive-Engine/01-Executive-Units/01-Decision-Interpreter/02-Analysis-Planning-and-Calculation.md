# Analyzer, Planner and Calculator

## Analyzer / Planner

`classify_execution` uses a fixed vocabulary. Goal, dependencies, priority and deadline are extracted from declared structure; missing optional values receive deterministic defaults.

## Calculator

The six Atlas-named extractors are cohesive functions in `interpret.py`, not six invented service packages. Their combined product is `ExecutionContext`.

## Determinism

The same frozen input and evaluation time produce the same result. Ordering, ties and thresholds
are explicit in code and are covered by focused tests; an LLM is not an alternate execution path.
