# Layer 6 production runbook and remaining integrations

## Current defect status

The local hardening pass found and closed the code-level authority defects in scope: permissive
missing ACLs, incomplete delivery/execution identity verification, correlated evidence inflation,
retry-clock identity drift, actor/subject conflation, organization preference poisoning, persistence
before governance, non-versioned policy authority, expiry rollback, stale review, publisher races,
false metric publication and rollback-without-restore.

No known internal P0/P1 Layer 6 code defect remains after the focused and full test runs. That is a
local evidence statement, not a substitute for the deployment proofs below.

## Remaining integrations

1. Four allowlisted lower-layer consumers for Organization, Behavior, Adaptive and Runtime state.
2. Authenticated provider/client receipt publishers and any approved general structured-event
   producer.
3. Tenant policy, privacy, threshold, retention and reviewer-ownership sign-off.
4. Human-owned workflow from an approved knowledge suggestion to a reviewed Git/PR draft.
5. Production metrics, alerts and SLOs for runs, rejections, review, expiry, versioning and sources.
6. Optional LLM fact extractor and optional Redis cache, each held to its documented non-authority
   boundary.

## Deployment proof

1. Quiesce mixed legacy/new workers and rehearse migration 0046 followed by 0047 on a populated
   PostgreSQL copy. Inspect legacy private ACL backfill and constraint validation.
2. Confirm all 138 statements in 0047 are recorded once by the normal migration runner.
3. Preview one representative tenant and compare each proposal with its exact immutable input
   references, visibility, independence keys and pinned policy revision.
4. Race two workers for one fresh tenant/week. One may claim. Force a failure, then prove a bounded
   reclaim does not duplicate an object, evaluation, version, metric, suggestion or transition.
   In a later week, reproduce one held object and prove current-policy/time re-evaluation, Candidate
   non-regression and no reopening of review/published/terminal duplicates.
5. Confirm malformed or incomplete optional inputs create sanitized rejections while valid siblings
   continue; no rejected raw value may appear in the ledger.
6. Confirm weak/noisy/conflicting/stale/correlated evidence is held or rejected and Organization,
   constrained-visibility and Knowledge targets enter review under policy.
7. Create a Runtime memory, let expiry commit, then fail the subsequent analysis transaction. The
   lease must stay expired.
8. Publish two values, roll back the current one and prove exact safe-predecessor restoration. Make
   restoration unsafe and prove rollback-to-empty.
9. Exercise owner and scoped principals over private, participant, organization and public rows;
   verify filtering precedes count/limit.
10. Verify workspace reset removes learning artifacts/inbox/rejections but preserves policy and its
    revisions; verify full tenant erasure cascades everything. On populated PostgreSQL, contend
    reset/delete against learning run, expiry, policy/direct-memory writes, review/rollback and both
    feedback source writers; prove tenant-root blocking, canonical lock order and no deadlock,
    partial wipe or child resurrection.
11. Review a knowledge suggestion and prove no Expert/pack/Git mutation occurs.
12. Keep generic learned-state consumption disabled until each target's typed reader, fallback,
    rollout and rollback tests are independently approved.

## Operational watch list

- failed or repeatedly reclaimed weekly runs;
- input rejection reason and source-starvation rates;
- policy revision attached to every non-legacy run/object;
- one correctly run-policy-bound evaluation per actually evaluated object/run;
- HumanReview queue age and reviewer authorization failures;
- active Runtime memories past expiry;
- more than one active entry per tenant/brain/subject;
- publisher no-op, metric-identity and stale-version conflicts;
- unexpected increases in neutral `completed_unproven` or missing receipt cohorts;
- rollback frequency and whether restoration or empty fallback occurred.
- tenant-root lock wait/deadlock signals during erasure, learning, review, rollback and feedback.
