# Analyzer, Calculator and Evaluator

## Analyzer / Calculator

Facts group by capability, play and ACL. The value records total outcomes, successes, failures,
unproven neutral results, success bp, average progress, attention cost and average seconds to close.

`success_bp = successes / (successes + failures)`; neutral labels are excluded. Attention cost uses
reminders + 2×escalations against a bounded four-units-per-outcome denominator. Averages and basis
points use deterministic integer arithmetic.

## Evaluator

Confidence also uses only positive/negative labels and independent executions. Adding any number of
neutral outcomes does not raise certainty or change the learning ID when the evidence facts are
otherwise unchanged. Neutral still contributes to descriptive totals/progress.

Unit 11 evaluates exact lineage, independent support, days, confidence, conflict/noise, value and
freshness. Empty labelled denominators resolve to zero rather than division or implicit success.
