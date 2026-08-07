# Analyzer, Planner and Calculator

## Analyzer / Planner

`next_state` and transition rules evaluate legal edges. Progress is calculated from action states while timeline derives from append-only events.

## Calculator

Queued, delivered, reminder, escalation, reassignment and outcome facts remain distinct.

## Determinism

The same frozen input and evaluation time produce the same result. Ordering, ties and thresholds
are explicit in code and are covered by focused tests; an LLM is not an alternate execution path.
