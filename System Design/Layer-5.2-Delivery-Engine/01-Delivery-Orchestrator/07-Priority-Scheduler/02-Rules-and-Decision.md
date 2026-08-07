# Rules and decision

Scheduling rules are stable and replayable:

- effective priority rises one class every four waiting hours, capped at critical;
- future-created rows never receive negative aging;
- rows are ranked inside each organization, then selected round-robin across organizations;
- `FOR UPDATE SKIP LOCKED` and a five-minute claim token fence concurrent workers;
- expired claims mark their unfinished physical attempt `unknown` before reclamation;
- timing/policy deferrals move the due time without a provider attempt;
- transport failures use bounded 5, 30, 120 and 720 minute retry slots per route generation;
- a definite terminal route failure can start a fresh retry generation on the next fallback;
- daily and hourly attention reservations are atomic and separate from queue ordering.

The dedicated platform delivery loop invokes materialize, expiry and drain independently of the
heavy sync loop. Due-row claims and fences make concurrent application replicas safe, although
deployment load tests remain required.
