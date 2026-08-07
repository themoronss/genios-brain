# Output, edge cases and gaps

**Output:** one typed verdict with unit, stable reason, optional `not_before` and audit detail.
The outbox persists the winning unit/reason on defer, suppress and successful admission.

**Edge cases and gaps**

- A stop and a time-bounded hold cannot coexist; corrupt state resolves toward silence.
- Missing policy defaults are permissive, while missing timing defaults remain protective.
- An opt-out suppresses only that route; it does not invent another work owner.
- Malformed v2 visibility rejects the execution; unresolved selected-evidence lineage becomes an
  empty private audience. Neither is interpreted as consent to widen access.
- Delivery policy does not implement consent/domain rules for a future email provider or native
  push permission lifecycle. Those integrations must add provider-specific controls without
  bypassing this gate.
