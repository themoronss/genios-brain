# Input, Validator and Retriever

## Input / Validator

Evidence contract validates nonnegative counts, positive+negative bounds, basis-point ranges, aware time and source refs. Runtime memory also requires explicit future expiry.

## Retriever

Policy is loaded tenant-scoped. Validation does not query or mutate a brain.

The unit never crosses tenant boundaries and never replaces missing source evidence with generated
facts.
