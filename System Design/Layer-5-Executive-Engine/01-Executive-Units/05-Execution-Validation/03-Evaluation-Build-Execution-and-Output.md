# Evaluator, Builder, Executor and Output

## Evaluator / Builder

The evaluator returns exactly one typed verdict and evidence. `PROCEED` alone authorizes the caller to create an outbound event.

## Executor / Output

`REROUTE` updates routing without changing execution identity; `SUPPRESS` keeps the commitment open; terminal verdicts follow guarded lifecycle transitions.

## Failure posture

A rejected or incomplete input returns a typed, auditable result. The unit does not silently skip
an invariant and does not upgrade uncertainty into authority.
