# Adapter and contract

A native implementation must add a registered `email` adapter and destination model with verified
sender/domain and recipient identity. It must render only grounded execution content, honor
unsubscribe/preferences, carry stable idempotency, classify provider errors and map accepted,
delivered, deferred, bounced, complained and unsubscribed events into transport/lifecycle facts.

It must use `ChannelResult`, the durable outbox, authority revalidation, delivery policy, timing,
retries, dead letters and append-only receipts. Email provider code cannot invent a recipient,
reuse a generic webhook while labeling it email, or treat provider acceptance as execution.
