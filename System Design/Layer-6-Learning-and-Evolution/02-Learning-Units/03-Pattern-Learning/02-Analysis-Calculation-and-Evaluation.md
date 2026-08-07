# Analyzer, Calculator and Evaluator

## Analyzer / Calculator

Non-memory facts group by `(pattern_key, kind, canonical visibility)`. The value records occurrences
and distinct days. Evidence preserves every observation ID, stable independence identity, source
trace, narrowed ACL, first/last seen time and lineage completeness.

Confidence is `average_source_confidence_bp × min(10, independent_support) / 10`. This lets weak
upstream observations remain weak and prevents duplicate rows from one origin from creating
certainty.

## Evaluator

All observations are evidence of recurrence, not causation. Unit 11 still requires independent
repetition, days, confidence, acceptable noise/conflict, value, freshness and complete lineage.
Organization target additionally requires public/org source visibility and human review by default.

All counts, thresholds and rates are deterministic integers with explicit observation time.
