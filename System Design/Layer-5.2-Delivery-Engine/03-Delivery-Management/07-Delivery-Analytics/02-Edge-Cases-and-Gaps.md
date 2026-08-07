# Edge cases and gaps

- Engagement analytics can only be as complete as authenticated clients emitting lifecycle receipts. Incoming webhooks do not provide universal view/open semantics.
- Cross-device impression identity and provider-native delivery/open telemetry are not normalized across every surface.
- Layer 6 currently consumes the row projection and timestamps, not the full append-only event stream; repeated same-state evidence is therefore not a separate learning event.
- Recipient fatigue covers impressions visible to this Delivery Engine. Out-of-band Slack, Teams, email or human communication is invisible.
- `executed_at` supports delivery-response timing but does not prove the Layer 5 operation succeeded or produced value.
- Production dashboards, retention policy and alert thresholds are operational integrations, not established by the deterministic projector itself.
