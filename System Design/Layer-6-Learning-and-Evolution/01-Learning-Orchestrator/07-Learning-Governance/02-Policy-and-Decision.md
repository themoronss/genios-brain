# Policy and decision

Preflight runs before `persist_object` and refuses, in order, when:

- learning is disabled;
- target or subject prefix is blocked;
- source refs are absent or lineage is incomplete;
- a participants/private ACL has no audience;
- Organization learning is not backed by public/organization-visible evidence;
- a user preference has no single resolved subject, or its source ACL excludes that subject;
- constrained Behavior/Adaptive evidence is not visible to its learned subject; or
- Runtime lacks a policy-compliant expiry or the explicit-memory marker.

After validation, governance chooses:

- Runtime → `temporary` before review-target evaluation; Runtime is forbidden in
  `require_human_targets` by API and database policy;
- targets listed in `require_human_targets` → `human_review` (Knowledge Suggestion is always forced
  into this list by the policy API);
- constrained durable brain evidence → `human_review` when configured; or
- all other permitted targets → `promoted` for target-specific publication.

Visibility aggregation uses the narrowest source ACL, and aggregated subject namespaces include an
audience hash. User-scoped preferences narrow further to `private + [resolved subject]`; Behavior
and Adaptive derivations copy that visibility, subject and lineage exactly. ACL cohorts cannot
silently merge. High confidence never widens visibility.
