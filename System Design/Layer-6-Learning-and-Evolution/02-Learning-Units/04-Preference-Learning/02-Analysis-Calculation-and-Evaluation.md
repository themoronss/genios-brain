# Analyzer, Calculator and Evaluator

## Analyzer / Calculator

Facts group by `(scope, principal, key, category)`. User principal is the actor key; organization
principal is the organization cohort. Within each group, facts group again by canonical value. The
winner is selected by descending support, then canonical value text as a stable tie-break.

Winner support is positive evidence; all competing observations are negative/conflict evidence.
The value retains key, winner, scope, category, support and competing count. Every source ref—not
only winner refs—remains in evidence.

## Evaluator

Conflict is explicit (`competing / observations` basis points), not last-write-wins. Independent
cards cap confidence. Reordering the same facts cannot change the winner, object value or ID.

For user scope, exactly one resolved subject principal is carried into the object and the output ACL
is always private to that subject. The source ACL is still authoritative: unresolved or conflicting
subject resolution, or source evidence that excludes the subject, makes lineage incomplete and
fails preflight. Organization scope keeps the source cohort ACL, requires org/public visibility and
enters default human review.

All counts, thresholds and rates are deterministic integers with explicit observation time.
