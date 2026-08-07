# Rollback

The owner-only rollback path targets a published object, records actor/reason and transitions it to
RolledBack while deactivating its effective entry as defined by the store authority.

Rollback never edits the immutable proposal/evidence. Reinstating a prior version requires an
explicit, audited decision path.
