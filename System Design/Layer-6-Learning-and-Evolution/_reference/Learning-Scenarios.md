# Learning scenarios

## Successful recommendation with independent evidence

Repeated succeeded outcomes for one capability/play across independent executions and distinct days
produce Recommendation Learning evidence. After validation/governance, an Adaptive efficacy value
may publish. Repeated rows from one execution count once. The published value remains inert until a
typed Adaptive consumer is integrated.

## Completed but unproven

The outcome remains neutral. It may contribute to attention/progress accounting but cannot increase
positive confidence or become evidence of business success.

## Conflicting explicit preferences

Typed preferences are grouped by actor or owner-authorized organization scope. The deterministic
winner is proposed and competing values increase conflict. A recurring observed pattern alone never
becomes a preference. A migrated Organization preference whose revision is authorization-false can
be resubmitted identically by an owner to create a new authorized revision.

For user scope, even an organization-visible card produces only a private preference for the one
resolved subject. If the source card ACL excludes that subject, or subject resolution is missing or
ambiguous, preflight rejects the proposal; Behavior and Adaptive children cannot widen it.

## Dashboard judgment versus lifecycle action

`run_play`, `do_it_myself` and `wrong` atomically update the card and one versioned canonical
feedback verdict/revision. Repeating the same judgment is idempotent; correcting it appends the next
revision. A `wrong:bad_timing` correction remains canonical/versioned but contributes timing/neutral,
not negative quality, to Feedback Learning. Dashboard requeue and dashboard/extension snooze remain
visible in human/card audit and lifecycle as timing-only/non-verdict actions; they do not become
Layer 6 verdict evidence.

## Temporary explicit memory

An authenticated principal submits bounded canonical JSON with an idempotency source reference and
a future expiry. Preflight validates visibility, actor authority and exact tenant TTL. Publication
creates Runtime memory. Expiry commits separately before weekly analysis, so a later failed run
cannot resurrect it. Reuse of the idempotency key with different semantics returns conflict.
Runtime can never be held for human review: owner API and database policy reject that configuration.

## Non-receipt delivery freshness

A delivery created before the 28-day source window is still selected when it has a lifecycle event
inside the window. A delivery ending in failed, deferred, suppressed or cancelled then contributes
its latest append-only lifecycle timestamp. Performance evidence therefore ages from the real last
event, not only from outbox creation or a receipt that never existed. A failed status is
transport-negative only when no durable `delivered_at` exists. If delivery/acceptance happened
first and downstream execution then failed, Performance Optimization keeps transport delivered and
leaves that later business/execution failure to Outcome Analysis.

## Held object under a later policy

An identical immutable proposal held as Observed or Candidate appears again in a later claimed
week. Layer 6 locks the existing row, recalculates policy-dependent validation/current freshness at
that run's pinned policy revision and evaluation time, and appends the prior/result/reason decision
to `learning_object_evaluations`. The reason is the final sink outcome—for example
`published_to_dynamic_target`, `no_material_change` or `metric_identity_conflict`—rather than a
stale policy-path label. Candidate cannot regress to Observed. If the object is already in
HumanReview, Published, Temporary or any other later/terminal state, the duplicate is counted
unchanged and cannot reopen it.

## Account erasure during learning or feedback

A weekly run, policy change, direct memory, expiry, review or rollback first holds tenant
`orgs FOR SHARE`. Reset/full deletion requests `orgs FOR UPDATE`, so one side waits before child
mutation/deletion begins. Review discovers the policy key, then locks policy and object; rollback
discovers every predecessor policy and locks those keys sorted before subject/object topology.
Dashboard/intelligence feedback follows tenant → graph → card. The committed result is therefore
either a complete authorized mutation before erasure or complete erasure after it—never recreated
Layer 6/card feedback children after deletion. Real contention timing still requires populated
PostgreSQL deployment proof.

## Organization-wide pattern

Repeated normalized facts with complete organization-visible lineage can propose an Organization
entry. Default governance sends it to HumanReview; private/partial lineage cannot be widened to
organization scope. Approval rechecks current policy, ACL and value under lock before publication.

## Supersession and rollback

A materially new Behavior/Adaptive/Organization value gets the next version and supersedes the old
active entry. Rolling it back restores the exact predecessor only if it is still verified, visible,
allowed by current consent/policy and not displaced by newer state. Otherwise no active value is
restored. Both outcomes retain the immutable history and transition ledger.

## Knowledge drift

At least the guarded number of labelled outcomes with sustained poor success can create a
visibility-preserving knowledge suggestion. A human may review it. Approval does not edit the
Expert Brain, pack files or Git; a separately owned reviewed PR workflow is the remaining handoff.

## Malformed or forbidden input

One malformed optional delivery, preference or event is excluded while other valid facts continue.
The rejection ledger stores only a source identity/hash and reason. A blocked target, incomplete
lineage or forbidden ACL is rejected before its proposed value enters `learning_objects`.

## Learning disabled

The tenant's due Runtime memories are still expired for retention correctness. The orchestrator
then stops without claiming a new weekly run or persisting any new proposal. The legacy calibration
path observes the same consent switch.
