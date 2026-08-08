[Domain Compiler](07-Domain-Compiler.md) · [Overview](00-Overview.md) · [Folder map](README.md)

# Remaining gaps

The Layer 3 boundary is implemented and locally verified. It is not yet honest to call the entire
production path activated.

| Priority | Gap | Exact completion condition |
|---|---|---|
| P0 | Live Layer 2 handoff | The active situation engine publishes `BusinessSituationObject` plus `SituationContextSlice` with the common envelope and no Layer 3 graph reads are needed. |
| P0 | Live Layer 4 handoff | The active reasoner accepts only `ExpertisePackage` for this path, preserves package/snapshot ids in its outputs, and does not read domain authoring files itself. |
| P0 | PostgreSQL proof | Migration `0048` is applied in an integration environment; tenant isolation, query plans, idempotent retries, update rejection, and concurrent publication are tested against real PostgreSQL. |
| P1 | Corpus runtime maturity | Admin gains routable situations; incomplete capability stubs are completed or intentionally retired; the current validator warning backlog is reduced with no invented signals. |
| P1 | Signal vocabulary alignment | The 15 authored situation trigger types that no Layer 2 pack emits yet are either implemented upstream or removed through domain review. |
| P1 | Domain golden scenarios | Each production situation has positive, negative, missing-context, visibility, optional-knowledge, and replay goldens—not only compiler unit fixtures. |
| P1 | Typed brain selectors | Layer 6 publishes first-class capability/entity/object selectors instead of relying partly on compatible `subject_key` token matching. |
| P2 | Cache and invalidation | Add a non-authoritative cache keyed by BSO hash + brain snapshot, with DB/Git sources remaining replay truth. |
| P2 | Legacy retirement | Remove the Python `sales/general` effective-config path only after traffic parity, replay parity, and rollback rehearsal. |
| P2 | Operational telemetry | Add latency, route-expansion, missing-optional, excluded-visibility, stale-registry, publish-conflict, and package-size SLOs. |

## What is not a Layer 3 task

- inventing or qualifying business situations belongs to Layer 2;
- recommending, scoring, planning, or deciding belongs to Layer 4 and above;
- learning from outcomes and publishing new brain versions belongs to Layer 6;
- domain authorship remains a human-reviewed Authoring Engine workflow.

Crossing those boundaries to make a demo appear complete would weaken determinism and provenance.
