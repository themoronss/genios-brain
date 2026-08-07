# Adapter and contract

Notification intent can be materialized from an `ExecutionObject`, receive a final recipient,
priority/format and route, then pass policy/timing before becoming available. The common `in_app`
adapter reports durable availability under Human/Application; the Notification unit itself remains
non-operational in runtime capability output until native transport exists. A client must
separately report view/ignore/accept/execute.

A future APNs/FCM/system adapter must implement the common `ChannelResult`, use registered device
destinations, preserve idempotency and receipts, and remain behind the same authority, preference,
quiet-hour and rate-limit gates. Native push cannot be simulated by relabeling generic webhook.
