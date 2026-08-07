# DeliveryObject

`DeliveryObject` is a frozen `delivery-object.v2` value. It identifies one logical delivery and contains the facts the drain must not reconstruct from mutable upstream state:

- `delivery_id`, `org_id`, `subject_id`, `execution_id` and `created_at`;
- audience, recipient and resolved destination;
- channel, channel class, format kind, band and interrupt flag;
- priority class (`background` through `critical`), rank (`1` through `5`) and frozen daily attention budget (`1` through `15`);
- route reason, ordered route plan and stable logical `dedupe_key`;
- rendered payload and retry interval metadata.

The database additionally stores execution hash/event lineage, source payload and `route_index` needed by the durable control plane.

Source visibility is authority on the parent `ExecutionObject` v2 rather than a mutable
DeliveryObject choice. Human payloads are planned only after current seat email is checked against
that ACL; participant/private routes are limited to authenticated recipient-scoped surfaces. The
full agent payload carries the canonical execution, including visibility, but constrained evidence
currently rejects agents because no verified agent-to-principal binding exists. A consumer that
holds only `DeliveryResult` must join the immutable execution to inspect this ACL.

The object is delivery intent, not permission to execute or send forever. Before each adapter invocation the engine revalidates the current parent execution and expected authority hash.
