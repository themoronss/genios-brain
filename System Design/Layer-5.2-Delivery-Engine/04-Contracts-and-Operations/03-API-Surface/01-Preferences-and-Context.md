# Preferences and context

## Preferences

Owner-authenticated organization endpoints read saved preferences, resolve effective field-by-field policy and list work held by delivery admission. Preference write/delete is also owner-only. Scoped credentials are denied by default on these dashboard-style routes. Writes validate timezone and policy domains inside the transaction so invalid persisted values cannot silently fall back at runtime.

Resolved preferences feed quiet hours, channel allowance and materialized attention budget. They remain policy input; the API handler cannot force a send.

## Presence context

`delivery.context.write` permits bounded presence PUT, while `delivery.read` permits GET. Both
routes compare the requested `seat_id` with the scoped credential's authenticated `agent_id`; a
scoped caller cannot publish or inspect another seat. Owners may operate across the organization.
Context delete is owner-only. A PUT stores at most a one-hour lease and clamps `busy_until` to its
expiry, so an abandoned client cannot hold delivery indefinitely.

Presence is an expiring lease, not permanent identity or send authority. Delivery still revalidates execution authority and all other admission units after reading it.

The current self-service boundary is agent identity. If product requirements add native human-seat
context writes, that principal and its ownership checks must be implemented explicitly rather than
inferred from organization membership.
