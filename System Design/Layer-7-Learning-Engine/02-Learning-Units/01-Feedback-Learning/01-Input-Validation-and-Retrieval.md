# Input, Validator and Retriever

## Input / Validator

Only facts marked explicit enter the unit. Tenant, identifiers and aware timestamps are validated by frozen fact contracts; source refs are preserved.

## Retriever

The retriever is the batch selector. The unit does not query cards again or let revised/noncanonical feedback re-enter under a new identity.

The unit never crosses tenant boundaries and never replaces missing source evidence with generated
facts.
