# Lifecycle, edge cases and gaps

The mobile pull/presence seam is active. APNs/FCM adapters, device-token registry/rotation,
notification permission state, background-delivery semantics, collapse policy, provider receipts
and uninstall cleanup are missing. Pull support is not native push.

Until those integrations land, `delivered` on the mobile surface means inbox availability, not
device notification. Native alerts must be classified as intrusive so quiet hours, focus state
and attention budgets cannot be bypassed.
