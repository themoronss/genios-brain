# Atlas Layer 5.2 implementation status

Status vocabulary is evidence-based: **Built**, **Partial**, **Upstream-owned**, **Missing** or
**Intentional boundary**.

## Part A · Delivery Orchestrator

| Atlas component | Status | Evidence | Remaining edge |
|---|---|---|---|
| Delivery Context Resolver | **Partial** | `presence.py`, `gate.py`, leased presence table | Context is real, but trusted presence is not auto-published from every client/seat |
| Audience Resolver | **Upstream-owned** | Layer 5 `assignment.py`, frozen communication plan | Delivery verifies destination; it does not reassign by design |
| Destination Router | **Built** | `destination.py`, registered priority/fallback | Real provider configuration still environment-dependent |
| Channel Planner | **Partial** | Layer 5 intent + Delivery destination/adapter resolution | No universal capability negotiation across every Atlas surface |
| Timing & Interruptibility | **Built** | `timing.py`, quiet hours/busy/burst | Depends on correct timezone and presence publishers |
| Delivery Policy | **Built** | `policy.py`, `gate.py` | Production tenant policy rollout remains |
| Priority Scheduler | **Built** | outbox priority/due ordering, burst and backoff | No separate distributed priority queue |

## Part B · 11 Delivery Units

| # | Delivery unit | Status | Live boundary / gap |
|---|---|---|---|
| 1 | Human | **Built** | Cards, chat and authenticated pull; no claim of a finished frontend |
| 2 | Agent | **Built** | Poll/claim/result plus HMAC push; not a general autonomous executor |
| 3 | API | **Partial** | REST/authenticated pull exists; no GraphQL, streaming, MCP or SDK suite |
| 4 | Application | **Partial** | Pull aliases support applications; no native app/plugin integrations |
| 5 | Notification | **Partial** | Slack/Teams/chat paths; no OS-native push provider |
| 6 | Dashboard | **Partial** | Inbox/card/result APIs exist; dashboard UI is outside this repository |
| 7 | Webhook | **Built** | Signed HTTPS adapter and retry/failover path |
| 8 | Extension | **Partial** | Pull/presence seams exist; no browser-extension client here |
| 9 | Mobile | **Partial** | Pull/presence seam only; no APNs/FCM |
| 10 | Email | **Missing** | No native email adapter, identity, unsubscribe or receipt lifecycle |
| 11 | Slack / Teams | **Built** | Dedicated adapters; real credentials/endpoints unproven locally |

## Part C · Delivery Management

| Component | Status | Evidence | Remaining edge |
|---|---|---|---|
| Delivery Tracker | **Partial** | outbox ledger, typed results, card events | Transport states exist; viewed/ignored/accepted/executed are not one complete DeliveryResult lifecycle |
| Retry Manager | **Built** | bounded retry/backoff in `outbox.py` | Real provider outage proof remains |
| Failure Recovery | **Built** | terminal-failure-only fallback with authority recheck | Fallback applies only to registered eligible destinations |
| Deduplication | **Partial** | unique outbox identities per logical channel delivery | No global “one human impression” dedupe across every channel/surface |
| Rate Limiter | **Built** | daily user budget + burst/quiet/busy admission | No distributed Redis counter |
| Delivery Analytics | **Partial** | status/channel counts, attempts, deferrals, p50/p95 latency | Open/click/fatigue/execution attribution is incomplete across surfaces |
| Delivery Object Builder | **Built** | `contracts/delivery.py`, `results.py` | Projection uses outbox as ledger; no second result store by design |

## Honest completion statement

The orchestrator core, durable transport ledger, four concrete transport families and governed
recovery are implemented. “All 11 targets built” would be false: native email and mobile push are
not present, several surfaces are API seams rather than clients, and interaction analytics are
partial.
