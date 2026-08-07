# Analyzer, Planner and Calculator

## Analyzer / Planner

`coordinate` deterministically derives ready/waiting/completed sets. The calculator does not guess percent complete from prose; progress follows action states.

## Calculator

Coordination currently schedules waves, not people. Concrete cross-seat allocation is explicitly left visible as a gap.

## Determinism

The same frozen input and evaluation time produce the same result. Ordering, ties and thresholds
are explicit in code and are covered by focused tests; an LLM is not an alternate execution path.
