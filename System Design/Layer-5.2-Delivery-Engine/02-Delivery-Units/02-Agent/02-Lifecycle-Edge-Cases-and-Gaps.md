# Lifecycle, edge cases and gaps

Missing active identity, scope or canonical route creates a durable materialization failure rather
than leaking to a person. Definite provider failures can retry/fail terminally; ambiguous
acknowledgements stay on the same route generation. Signed delivery proves origin/integrity, not
that the agent executed the business action.

Participant/private source visibility currently rejects agent delivery because an agent registry
id is not a verified email ACL principal. This fails closed until a reviewed principal-binding
contract exists; it does not widen sensitive evidence to an autonomous runtime.

The agent webhook still requires runtime registration, a public HTTPS endpoint, secret rotation
and receiver-side idempotency/signature verification. It is not a general autonomous executor or
universal agent protocol, and external-effect actions remain governed by the full Layer 5 plan and
approval rules carried in the payload.
