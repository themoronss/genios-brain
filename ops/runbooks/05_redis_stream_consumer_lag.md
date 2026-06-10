# 05 — Redis Streams consumer lag (brain router)

## Trigger
- Brain router not producing recommendations despite active ingestion
- `XLEN genios:events:fact` growing large (> 10k pending)
- Users report "my insights are stale"

## Diagnosis
1. Check stream length: `redis-cli XLEN genios:events:fact`
2. Check pending per consumer: `redis-cli XPENDING genios:events:fact brain_router` — shows pending, min-id, max-id, consumers
3. Is a Celery worker running the `brain_router` queue? Check `celery inspect active_queues` — must include `brain_router`.
4. Check `task_brain_router` error count in Sentry — router exception storm?

## Mitigation
- Worker not consuming `brain_router` queue → restart worker with `-Q high_priority,low_priority,brain_router` (see PHASE_DEVIATIONS.md Phase 2 section)
- Router crashing on bad event → acks happen up-front, so crash mid-tick just drops that tick; stream fills if crashes repeat. Look at the stacktrace.
- Stream too big and dominated by stale events: trim manually `XTRIM genios:events:fact MAXLEN 1000` — acceptable because events are only triggers for re-computation, not source of truth.

## Follow-up
- Add alert on `XLEN` > 5000 sustained
- If one event type floods: add dedup at publish time in `event_bus.publish()`
- Confirm `MAXLEN ~ 100000` is actually being honored (approximation can drift)
