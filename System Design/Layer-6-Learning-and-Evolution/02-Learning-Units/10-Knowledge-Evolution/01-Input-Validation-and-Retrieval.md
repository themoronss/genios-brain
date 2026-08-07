# Input, Validator and Retriever

## Input / Validator

Input is a validated-shape Outcome Analysis proposal grounded in exact Layer 5 execution outcomes.
The trigger counts only `successes + failures`; at least eight labelled outcomes are required.
Neutral/unproven outcomes remain in the cohort value but cannot satisfy that floor or raise
confidence.

## Retriever

The unit deterministically derives from `outcome_analysis(batch)`, preserving the exact outcome
refs, independent execution refs, reasoning traces, ExecutionObject ACL, first/last seen times and
lineage completeness. It records the parent learning ID.

It does not inspect Expert content, Git state or raw customer prose. Missing outcome coverage cannot
be replaced with a speculative knowledge suggestion.
