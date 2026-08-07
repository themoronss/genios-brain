# Lifecycle, edge cases and gaps

The shared in-app seam is active under Human/Application. There is no OS push adapter, device-token registry, token rotation,
permission lifecycle, collapse-key policy, provider receipt reconciliation or uninstall cleanup.
Slack/Teams acceptance is not equivalent to native push delivery.

Until those integrations exist, capabilities report the Notification contract engine-ready but
non-operational, without relabeling ordinary in-app availability as native delivery. Native notifications will also need a precise intrusive
channel classification so device alerts cannot bypass humane timing.
