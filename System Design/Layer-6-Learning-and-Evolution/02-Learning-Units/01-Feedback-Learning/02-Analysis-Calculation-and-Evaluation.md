# Analyzer, Calculator and Evaluator

## Analyzer / Calculator

Facts group by `(subject_key, canonical visibility)`, preventing two ACL audiences from merging.
Accepted/executed/run-play/do-it-myself count positive. Rejected/cancelled and only
`wrong:not_relevant` / `wrong:wrong_facts` count negative. `wrong:bad_timing` remains a canonical
verdict but increments the timing bucket and stays neutral for quality, matching calibration.
Legacy normalized explicit `snooze` facts are also timing/neutral; current dashboard/extension
snooze and dashboard requeue are audit/lifecycle actions and do not reach this fact cohort.

The value stores positive (`accepted`), negative (`rejected`), `timing` and total `neutral` counts;
timing is an explanatory subset of neutral, not a fourth quality label. Evidence stores every
source revision ref, unique card-derived independence ref, trace ID, first/last seen time and the
narrowed cohort ACL. Confidence is integer labelled agreement capped by independent labelled
support. Neutral/timing facts contribute to observations and noise only; they never raise
confidence or lower recommendation quality.

## Evaluator

The unit may build a neutral measurement, but Unit 11 then applies lineage preflight, independent
repetition, distinct days, confidence/noise/conflict, current freshness and business value. Thus a
descriptive object can remain observed/candidate instead of being misreported as validated.

All counts, thresholds and rates are deterministic integers with explicit observation time.
