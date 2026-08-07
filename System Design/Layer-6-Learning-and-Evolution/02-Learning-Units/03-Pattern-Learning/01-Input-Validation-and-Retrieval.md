# Input, Validator and Retriever

## Input / Validator

`EnterpriseFact` requires event ID, pattern key, kind, aware occurrence time, structured value,
0–10,000 source-confidence bp, optional actor/trace/independence identity, typed visibility and a
lineage-complete flag. Explicit temporary-memory facts are excluded from Pattern Learning.

## Retriever

For Layer 2 graph input, the selector accepts only active observations with exact
`graph_source_refs` bound to the creating source event. It narrows all contributing source-event
ACLs, hashes their event IDs into a stable trace and hashes source independence groups into one
stable independence identity. Missing source lineage is rejected.

Normalized `learning_event_inbox` events are the second supported seam and must carry explicit
trace, independence and visibility. The unit does not read or classify raw prose.
