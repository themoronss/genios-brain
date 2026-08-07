# Lifecycle, edge cases and gaps

No native email transport, provider configuration, verified domain, suppression list, bounce/
complaint webhook or deliverability telemetry exists. The capability registry therefore reports
`engine_ready=true` but `operational=false` with no available email channel.

Email remains unavailable rather than being routed through webhook and mislabeled as complete.
Presence in an email editor may legitimately select the Extension unit for an inline suggestion;
that is not a sent email. Provider/legal/compliance choices must be completed before this status
can become operational.
