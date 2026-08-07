# Lifecycle, edge cases and gaps

The backend route, inbox, result projection, lifecycle endpoint and analytics are active. Transport
delivered means dashboard availability, while viewed/ignored/accepted/executed require client
evidence and remain independent from provider retries.

This repository does not contain a complete dashboard UI or universal instrumentation. Shared
dashboard vs seat-specific visibility must remain tenant/recipient scoped in each client. Legacy
cards may still render, but canonical new outward delivery carries `execution_id` and its frozen
route reason.
