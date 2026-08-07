# Analyzer, Calculator and Evaluator

## Analyzer / Calculator

Facts group by channel and identical ACL. Delivered includes delivered/viewed/ignored/accepted/
executed status or an actual delivered timestamp. Transport-failed includes only status `failed`
with no `delivered_at`. A tracker may legitimately move ACCEPTED to FAILED after downstream
execution fails; because transport already succeeded, that row remains delivered and contributes
zero transport failure. Its business/execution failure belongs to Outcome Analysis. Queued,
deferred, suppressed, cancelled and expired are counted separately; `open = queued + deferred`.
Because history is append-only, a row later marked expired or failed can retain and count its
earlier delivered/engagement timestamp rather than erasing that fact.

`delivered_bp` uses only delivered + failed as its terminal transport denominator. The value also
records engagement counts, attempts, deferrals and deterministic lower-median delivery latency.
For each delivery, the evidence moment is the latest of creation, latest lifecycle event and any
durable delivery/engagement/expiry receipt. Consequently failed, deferred, suppressed and cancelled
transitions advance `last_seen_at` and freshness instead of leaving creation time as a stale proxy.

## Evaluator

Evidence treats delivered as positive and only pre-delivery failed as negative. Post-delivery
execution failure is still transport-positive; open/held/cancelled/expired facts remain neutral and
cannot increase confidence, and deferrals do not become provider failure. Independent execution
IDs prevent multiple delivery rows/attempts from overstating support.

Unit 11 still applies lineage, repetition, days, confidence, freshness and value policy. All rates
use integer basis points and all lifecycle facts are evaluated at the frozen time.
