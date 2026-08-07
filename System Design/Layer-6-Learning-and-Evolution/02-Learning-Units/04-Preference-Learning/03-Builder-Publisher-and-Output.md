# Builder, Publisher and Output

The builder emits:

- user: target `behavior`, subject `preference:user:<actor>:<key>`; or
- organization: target `organization`, subject `preference:organization:<key>`.

Both preserve key/value/scope/category/support/competing plus exact source, independence, trace and
seen-window lineage. Organization scope preserves the source ACL. User scope emits only a private
ACL containing the resolved subject principal and records its derivation from the source ACL.

Governed publication creates a versioned brain entry. Organization preference requires human review
by default; a valid user preference is review-gated by constrained-visibility policy and visible
only to its subject. Behavior and Adaptive Evolution may create separately namespaced derived
proposals for whitelisted categories, but copy the private cap, subject principal and lineage flag
unchanged.

**Integration note:** lower reasoning/execution layers still need an explicit preference/brain read
contract before published values influence runtime behavior.
