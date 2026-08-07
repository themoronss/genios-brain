# Analyzer, Planner and Calculator

## Analyzer / Planner

Elapsed-window proportion, urgency, cooldown and fatigue are calculated deterministically. The deadline warning is proportional rather than a fixed number of hours.

## Calculator

After the hard reminder ceiling, the unit stops repeating and lets escalation own the next action.

## Determinism

The same frozen input and evaluation time produce the same result. Ordering, ties and thresholds
are explicit in code and are covered by focused tests; an LLM is not an alternate execution path.
