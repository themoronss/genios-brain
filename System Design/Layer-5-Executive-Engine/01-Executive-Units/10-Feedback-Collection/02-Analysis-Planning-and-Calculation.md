# Analyzer, Planner and Calculator

## Analyzer / Planner

The analyzer separates succeeded, expired untouched/in-progress, human/world/system cancellation and completed-unproven. Attention cost is counted from recorded events.

## Calculator

Outcome semantics are stable because downstream learning depends on them as ground truth.

## Determinism

The same frozen input and evaluation time produce the same result. Ordering, ties and thresholds
are explicit in code and are covered by focused tests; an LLM is not an alternate execution path.
