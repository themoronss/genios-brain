# Analyzer, Planner and Calculator

## Analyzer / Planner

The analyzer evaluates independent invalidation axes. The calculator applies deterministic time and deadline rules; no probabilistic veto exists.

## Calculator

Each failed predicate maps to a distinct verdict so operations can distinguish resolved, revoked, expired, reroutable and temporarily blocked work.

## Determinism

The same frozen input and evaluation time produce the same result. Ordering, ties and thresholds
are explicit in code and are covered by focused tests; an LLM is not an alternate execution path.
