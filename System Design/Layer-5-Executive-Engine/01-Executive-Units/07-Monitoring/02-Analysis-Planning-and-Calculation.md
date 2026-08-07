# Analyzer, Planner and Calculator

## Analyzer / Planner

The analyzer identifies ready, waiting, stalled and completed work. Calculations use observed state and time, not generated summaries.

## Calculator

The blocking action is derived from dependency order and state, not arbitrary list position.

## Determinism

The same frozen input and evaluation time produce the same result. Ordering, ties and thresholds
are explicit in code and are covered by focused tests; an LLM is not an alternate execution path.
