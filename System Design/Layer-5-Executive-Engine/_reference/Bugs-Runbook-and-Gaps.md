# Layer 5 gaps and production runbook

## Remaining product gaps

1. **Multi-owner allocation:** dependency waves and action authority exist, but a planner does not
   yet allocate different actions to different seats/agents with independent escalation chains.
2. **Digest batching:** the communication plan can select digest, but Layer 5 has no cross-commitment
   batching optimizer.
3. **Acceleration:** due work is queried durably from PostgreSQL; Redis caching/queues are not used.
4. **Evidence coverage:** monitoring cannot prove an outcome that upstream connectors never record.
5. **Production proof:** migration 0041 and scheduler behavior require live PostgreSQL/load evidence.

## Safe deployment proof

1. Apply migrations through `0041_l5_execution.sql`.
2. Run one tenant sweep twice; the second planning pass must create no duplicate commitment.
3. Try out-of-order action completion and completion by a non-owner; both must be rejected.
4. Close the business subject while a reminder is queued; the outbound event must cancel.
5. Reassign a commitment and confirm `execution_id` does not change.
6. Complete work without outcome evidence; the result must remain `completed_unproven`.
7. Confirm queued and delivered events remain separate audit facts.

## Failure posture

Layer 5 fails closed on malformed decisions, forbidden external effects, missing authority and stale
work. A transient transport error is not interpreted here; it belongs to Atlas Layer 5.2.
