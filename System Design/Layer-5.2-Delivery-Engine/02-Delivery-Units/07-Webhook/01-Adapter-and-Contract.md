# Adapter and contract

Tenant configuration supplies a public HTTPS URL and secret of at least 16 characters. The
adapter serializes deterministic JSON, signs it with HMAC-SHA256, and sends
`X-Genios-Signature` plus the route-generation `Idempotency-Key`.

The adapter returns HTTP/provider metadata, retryability and ambiguity through `ChannelResult`;
it never owns retry or fallback. The outbox keeps one logical delivery, one row per physical
attempt and avoids cross-channel fallback after an ambiguous acknowledgement. Credentials are
sealed for new writes and never included in error detail.
