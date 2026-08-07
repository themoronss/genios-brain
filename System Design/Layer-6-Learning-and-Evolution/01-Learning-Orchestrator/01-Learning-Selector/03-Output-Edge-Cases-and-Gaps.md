# Output, edge cases and gaps

**Output:** one canonical `LearningBatch` containing `FeedbackFact`, `OutcomeFact`,
`EnterpriseFact`, `DeliveryFact` and sanitized `InputRejection` tuples. Invalid inputs retain only
closed reason codes and stable hashes in the rejection ledger; rejected raw values are not copied
into a LearningObject.

Important edge behavior:

- a fact with unprovable ACL/lineage may be represented fail-closed but will be refused by
  preflight before its proposal payload is persisted;
- one physical source may create many database rows, but its independence key prevents duplicated
  support from inflating evidence;
- source identity is stable across scheduler retries and process replicas; and
- an as-of delivery read cannot use an event or attempt that occurred after evaluation time.

**Remaining integration requirement:** upstream systems must actually write trustworthy outcome,
graph-source, execution, delivery and structured-event records. The selector intentionally does
not compensate for missing source normalization by guessing from raw prose.
