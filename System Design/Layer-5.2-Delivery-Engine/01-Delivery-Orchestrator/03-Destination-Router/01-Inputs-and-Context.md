# Inputs and context

Inputs are the final `AudienceResolution`, Atlas priority class, active presence surface and
tenant `RegisteredDestination` records. Each registered destination carries a stable channel
name, optional numeric priority and purpose enablement.

`in_app` and `dashboard` are always added to the human candidate ladder; drain-time policy still
requires the tenant channel to be active. A live Gmail/CRM/browser, IDE/desktop, mobile or web
presence can introduce the matching contextual pull surface. External transports enter the
candidate set only through known Layer 5.2 adapters and tenant/agent registration. Sealed
credentials must decrypt successfully and pass the concrete adapter's URL, host, secret and
identity validation before entering that set; ciphertext or row presence alone is not capability.
The same validators drive `/delivery/capabilities`, so reporting and route planning cannot disagree.

The legacy concrete channel stored in `ExecutionObject.communication.channel_id` is not an input
to the new route decision.
