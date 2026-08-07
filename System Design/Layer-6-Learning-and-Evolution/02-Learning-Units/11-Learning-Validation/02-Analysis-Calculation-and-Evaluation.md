# Analyzer, Calculator and Evaluator

## Analyzer / Calculator

Default checks: 3 observations, 2 days, 6500 confidence bp, at most 2500 noise/conflict bp, at least 1000 value bp and nonzero freshness. Runtime has a separate explicit TTL rule.

## Evaluator

Each failing dimension yields a distinct state/reason; low repetition waits, excessive noise/conflict/value/freshness failures reject.

All counts, thresholds and rates are deterministic integers with explicit observation time.
