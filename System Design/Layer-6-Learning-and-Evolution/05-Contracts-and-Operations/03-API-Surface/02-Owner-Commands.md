# Owner commands

Explicit memory creation and policy update are owner-only. Memory uses a deterministic
tenant+actor+source reference id, writes the normalized `learning_event_inbox` first, then
materializes the immutable object from the held row. Exact replay returns the existing state;
reusing the source reference with different semantics returns a conflict. Value size/depth and
preflight TTL/ACL/consent are checked before accepted persistence.

Review requires `learning.review`; rollback requires `learning.rollback`. Each command must also
pass the object's ACL. Organization review/rollback cannot be delegated through scoped credentials
and remains owner-only. Dynamic rollback may restore its verified predecessor; Metrics cannot use
the dynamic-brain rollback route.

Mutation commands share one concurrency root: `orgs FOR SHARE` before policy or child locks.
Review uses discovery → policy `FOR SHARE` → object `FOR UPDATE`/recheck. Rollback discovers all
policy identities, locks them sorted, then takes subject advisory and object/topology row locks.
Reset/delete holds the same tenant row `FOR UPDATE`, so it cannot interleave with these commands.

Payload tenant ids cannot override authenticated organization context.
