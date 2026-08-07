# Policy and decision

`ALL_ANALYSIS_UNITS` is a tuple, so declared architecture order is authoritative. Each unit sorts
its own cohorts and either returns deterministic proposals or an empty list. A final alphabetical
sort is intentionally absent because it would silently replace the Atlas plan.

Derived units reuse the parent proposal's source refs, independent refs, trace IDs, ACL and seen
window. They record `metadata.derived_from` but do not reread mutable data or increase observation
counts. Unit 11 then applies preflight, evidence validation and governance independently to each
result.

The same batch yields the same proposal order and content-addressed IDs. Current freshness is
evaluated later from `last_seen_at`; moving the evaluation clock alone does not mint a new object.
