# Adapter and contract

The surface adapter accepts only a registered pull-surface name. Because the canonical payload is
already committed to `delivery_outbox`, adapter success means “available in the authenticated
application inbox,” not “a window rendered” or “a user acted.”

An application client may publish a short-lived presence lease (`ide`, `desktop`, `web_app`, etc.)
so the orchestrator can prefer the contextual surface. It then reads the same `DeliveryObject`
and posts idempotent lifecycle receipts. Client code cannot alter the frozen route/priority or
bypass policy and authority checks.
