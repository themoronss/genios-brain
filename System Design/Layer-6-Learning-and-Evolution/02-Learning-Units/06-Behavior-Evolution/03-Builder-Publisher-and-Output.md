# Builder, Publisher and Output

The builder emits unit `behavior_evolution`, target `behavior`, a `behavior:*` subject and
`metadata.derived_from=<preference learning id>`. It preserves exact ACL, trace, independence and
seen-window lineage, including the private one-subject ACL and subject principal for user scope.

After governance/review, publication creates a versioned Behavior Brain entry under a
tenant/brain/subject lock. Value, confidence or ACL change is material; the prior active entry is
superseded. Human rollback can restore only the verified direct predecessor.

**Integration note:** publication is complete and API-visible. A lower-layer consumer must still
define which behavior subjects it reads and how those values influence decisions without bypassing
evidence visibility.
