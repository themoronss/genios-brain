# Consumption boundary and gaps

No current Reasoning/Executive/Delivery materializer consumes generic Adaptive entries.

A durable/API-visible row proves publication, not product behavior change. Activation needs a
typed as-of snapshot consumer that preserves tenant, viewer ACL, active version, rollback fallback
and policy revision. That downstream materializer is the remaining integration.
