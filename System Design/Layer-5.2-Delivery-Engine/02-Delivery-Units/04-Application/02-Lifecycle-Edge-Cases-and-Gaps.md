# Lifecycle, edge cases and gaps

The backend surface, inbox and presence contracts are active. Delivery means availability; viewed,
accepted and executed remain explicit client events. Presence expires, so a crashed application
cannot leave contextual routing permanently busy.

No complete CRM/ERP/product plugin, desktop shell, IDE plugin or CLI client is present here. The
minute materializer may refresh a queued contextual route when every attempt proves non-delivery;
unsafe/ambiguous transport evidence freezes it for manual recovery. Drain-time timing/policy always
use fresh context.
