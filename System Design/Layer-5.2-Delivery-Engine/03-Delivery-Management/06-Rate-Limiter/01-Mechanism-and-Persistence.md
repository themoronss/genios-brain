# Mechanism and persistence

## Reservation order

Rate capacity is reserved only for a claimed `ChannelClass.CHAT` delivery, after current execution authority and the normal admission gate have passed. The candidate's `intrusive` property follows channel physics, so even a chat route whose presentation flag says `interrupt=false` still consumes attention capacity. Pull, email-like and other non-intrusive routes do not consume this budget.

The worker first reserves an exact rolling-hour row under a transaction-scoped advisory lock. For
Slack/Teams this key uses the organization-wide `*` recipient so the two shared chat adapters spend
one stream; other intrusive channels use their recipient. It then reserves the frozen
`daily_budget` against that person's local-calendar-day row. If daily admission fails, the hourly
reservation is released.

The hourly reservation, daily reservation and claim-owned `started` attempt are one database
transaction. Concurrent workers therefore cannot both take the final slot, and a crash after the
commit still leaves physical-attempt evidence for conservative recovery.

The local-day boundary is calculated from the materialized timezone and therefore follows daylight-saving changes rather than assuming every day is a fixed UTC interval. A denied daily or hourly reservation becomes a `DEFER` until the relevant reset boundary and consumes no transport attempt.

Migration 0046 seeds `delivery_rate_windows` before v2 workers resume: exact timestamps from chat
deliveries in the preceding hour preserve rolling expiry, while current-local-day chat deliveries
seed per-recipient daily rows using the most specific valid saved timezone (UTC fallback). This
prevents the upgrade itself from opening an empty quota window.

On a definite pre-delivery or provider failure, both reservations are released. On delivered or
`unknown`, they remain charged because the recipient may already have been interrupted.
