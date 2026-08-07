# Intelligence Card and delivery scenarios

An Intelligence Card is a grounded presentation/read model linked to a Layer 5 execution. It can
render and collect a typed action, but it cannot independently authorize outbound delivery. Every
active scenario below starts from a live, identity-checked `ExecutionObject`.

## 1. Human approval card

Layer 5 creates an owned execution whose first action needs human approval. Layer 5.2 resolves the
current recipient, chooses an eligible authenticated surface, materializes one logical delivery and
exposes the linked card. `viewed` or `accepted` is a delivery lifecycle fact. Business success is
recorded only when Layer 5 receives outcome evidence; a click is never silently promoted to that
outcome.

## 2. Immediate chat escalation

Layer 5 supplies the execution, business priority and an escalation hint. Layer 5.2 resolves the
current audience and registered route. It permits a chat interruption only when the resolved
channel is chat, the delivery class is critical, confidence is at least 7000 basis points and the
recipient is not busy/focused. Layer 5 does not freeze the final channel or interrupt decision.

If the current manager changed after the execution was created, the Audience Resolver uses the
current active directory rather than paging the historical manager.

## 3. Inline context surface

A recipient has fresh presence in Gmail, a CRM, browser, IDE, desktop, mobile or dashboard context.
The planner maps that context to extension, application, mobile, dashboard or in-app delivery when
the priority and policy allow it. If presence expires, the surface loses precedence on the next
evaluation. A context surface is still a backend pull route unless its real client integration is
installed.

## 4. Quiet-hours or focus hold

Timing returns `DEFER` with the latest safe next time. The logical delivery remains queued/deferred,
and no physical provider attempt is spent. At the next drain, execution authority, audience,
presence, destination, policy and quota are evaluated again. Closure, reassignment or opt-out can
therefore cancel/suppress work that was valid when first queued.

## 5. Definite Slack failure with webhook fallback

Slack exhausts its bounded retries with a definite terminal result. After Layer 5 authority and
current Delivery Policy are re-proved, the existing logical outbox row advances its route cursor to
a registered webhook. Attempt records preserve both transports. No second independently
authorized delivery row is created.

If the fallback is no longer registered or the execution is closed, the object becomes terminal or
cancelled instead of reviving stale work.

## 6. Ambiguous provider timeout

The adapter may have delivered the payload but lost the acknowledgement. The attempt is recorded
as unknown. Layer 5.2 does not retry across a different channel, because that could create two
human impressions from one intent. Webhook/agent receivers receive a stable idempotency key, but
Slack/Teams are not claimed to provide receiver-side exactly-once semantics and therefore stop in
terminal manual reconciliation. Any uncertain owner replay requires explicit duplicate-risk
acknowledgement.

## 7. Agent delivery

The audience resolves to an active registered agent whose allowed actions contain `delivery.read`.
API pull additionally requires an active key for that exact agent with the same scope. The route
uses the scoped delivery inbox or signed agent webhook and carries the full versioned execution and
safety fields; it does not silently fall back to a human inbox. Raw `/v1/signals*` endpoints return
authenticated `410 Gone`. If the agent or route is unavailable, the delivery becomes
operator-visible rather than being misaddressed.

## 8. Lifecycle receipt and learning

An authenticated client publishes `viewed`, `ignored`, `accepted` or `executed` using an idempotent
lifecycle receipt. The tracker validates the transition, appends an event and updates the stable
`DeliveryResult` projection. Analytics calculate engagement, latency and fatigue from these facts;
Layer 6 can read them in the feedback batch without controlling future transport directly.

## 9. Dashboard, extension and mobile claims

The backend can place the logical delivery on authenticated dashboard, extension and mobile pull
surfaces. That proves durable availability and API semantics only. It does not prove that a
dashboard UI, browser extension, mobile app, device-token service or APNs/FCM integration has
shipped. Those remain explicit integration work in [STATUS.md](../STATUS.md).

## 10. Unsupported email request

An email unit contract exists, but no email channel adapter exists. Capability discovery must
report it as non-operational, and routing must not claim an email was sent. Email remains disabled
until sender/domain verification, unsubscribe, bounce/complaint and delivery/engagement feedback
are implemented end to end.

## 11. Participant/private source evidence

The selected evidence narrows `ExecutionObject` v2 visibility to named email principals. Layer 5.2
filters the current directory by that ACL and permits only an authenticated recipient-scoped
product surface; it does not send the content to Slack, Teams, generic webhook or an unverified
agent. A stored v1 execution re-derives this ACL from immutable reasoning context. Missing lineage
creates an operator-visible failure with an empty private audience, never an org-wide fallback.
