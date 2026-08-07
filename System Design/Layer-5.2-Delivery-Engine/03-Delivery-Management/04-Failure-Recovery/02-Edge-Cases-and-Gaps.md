# Edge cases and gaps

- `unknown` or timeout-with-ambiguous-ACK cannot safely advance to another channel because that could double-deliver.
- A corrupt/non-object stored source payload blocks fallback rendering and remains a visible terminal diagnosis.
- No eligible fallback leaves the row terminal; it is not silently dropped.
- Cancelled or stale-authority work cannot be revived by fallback. Owner replay is restricted to `failed_terminal`.
- Dead-letter output exposes `ambiguous_transport_evidence`. The owner must inspect physical
  attempts and explicitly acknowledge duplicate risk before replaying uncertain or legacy rows.
- Materialization failures and terminal outbox failures are both exposed as dead-letter diagnostics, but only an actual outbox row can be replayed through the owner API.
- Recovery correctness is implemented locally; live channel credentials, downstream permission failures and cross-provider outage drills remain operational validation.
