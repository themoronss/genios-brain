# Rules and decision

Rules are deterministic and compositional:

1. non-intrusive channels send without timing delay;
2. an interrupting candidate at/above the configured override band may break glass;
3. an active `busy_until`, quiet hours/weekends and the rolling burst limit each produce their
   own deferral;
4. when several constraints apply, the latest safe window wins;
5. atomic Postgres hourly and execution-config daily reservations close multi-worker races after
   live authority is proved and immediately before the provider call.

A definite non-delivery releases its reservation. An ambiguous acknowledgement keeps it because
the provider may have produced the interruption. Deferral changes eligibility and lifecycle
evidence but never consumes the bounded transport retry ladder.
