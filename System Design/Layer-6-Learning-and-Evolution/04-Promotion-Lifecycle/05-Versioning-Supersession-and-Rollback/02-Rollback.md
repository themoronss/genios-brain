# Rollback

Rollback accepts only an ACL-visible, currently Published Organization/Behavior/Adaptive entry;
Runtime and append-only Metrics are not rollback targets. It requires `learning.rollback`, and an
Organization rollback additionally requires owner authority.

Rollback first holds tenant root and performs discovery-only reads for current publication,
predecessor and all involved policy keys. It locks those policy rows in lexical order, then takes
the tenant+brain+subject advisory lock, locks/rechecks the current object and active/predecessor
topology, and fails closed if discovery changed. This sorted policy-before-subject/object order
prevents rollback from inverting review/publication locks.

Under those locks, the store deactivates the bad successor as `rolled_back` and records actor/reason.
When the exact predecessor is still Superseded, ACL-visible and allowed by its locked current
policy, it is reactivated and transitioned back to Published with a restoration audit. If no
predecessor passes those checks, rollback safely leaves the subject without an active value.

Rollback never edits either immutable proposal/evidence. It restores an existing verified version;
it does not forge a replacement value or reuse version numbers.
