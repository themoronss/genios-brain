# Input, Validator and Retriever

## Input / Validator

Facts carry delivery id, channel, status, attempts, deferrals, created/delivered clocks. Tenant-window selection precedes grouping.

## Retriever

The durable Delivery ledger supplies facts; a client-side impression is not assumed.

The unit never crosses tenant boundaries and never replaces missing source evidence with generated
facts.
