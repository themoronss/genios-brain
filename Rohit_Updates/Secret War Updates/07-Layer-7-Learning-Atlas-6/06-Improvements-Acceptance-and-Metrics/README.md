# Layer 7 Learning — Improvements, Acceptance, and Metrics

## Outcome to build

Layer 7 is complete only when a customer correction or verified business outcome can be traced into a bounded, governed brain change; that version is consumed by Layer 3; the future decision changes in the intended situation; and the resulting business outcome is measured without proxy inflation. A scheduled sweep, stored proposal, or dashboard count alone is not this outcome.

## Prioritized improvement plan

| Priority | Improvement | Why now | Acceptance replay | Metric | Exit gate |
|---:|---|---|---|---|---|
| P0 | Create one canonical learning event and outcome identity ledger | Card feedback, card outcomes, execution outcomes, delivery facts, and enterprise observations are fragmented | Same Theresa reply observed by Gmail, agent, and UI resolves to one canonical event with retained source aliases | Duplicate outcome rate; unreconciled event age; source coverage | 100% golden duplicates dedupe; contradictions quarantine; no in-place evidence mutation |
| P0 | Wire `card_feedback_verdicts`/revisions into the canonical feedback-learning seam | API stores structured verdicts while `unit_feedback_learning` returns `[]` against another optional seam | “Not relevant—already completed” stores reason/scope and prevents the same open-loop recommendation | Feedback-to-learning ingestion rate; median ingestion lag; repeated-corrected-card rate | Every supported verdict has lineage, revision, learning disposition, and replay result |
| P0 | Model recommendation → exposure → acceptance → execution → delivery → external outcome | Current labels cannot establish causal eligibility end to end | Click “I’ll do it” without execution produces no positive efficacy; executed message with reply produces eligible result | Funnel coverage at every boundary; unknown-outcome ratio | No stage can be inferred from a previous one; one immutable receipt per observed transition |
| P0 | Replace hardcoded customer value statistics with the canonical ledger | Stats currently report zero despite structured outcome paths | API totals equal ledger fixture across proven, failed, neutral, duplicated, and unknown outcomes | Ledger/API reconciliation error; freshness; unknown attribution | Exact agreement in deterministic tests; data-unavailable state replaces constants |
| P0 | Propagate visibility, excluded-subject, retention, and permitted-use controls | Contract shape is insufficient without enforcement | `never_commercial` support evidence cannot train or explain a Sales play | Forbidden-evidence attempted-use count; policy rejection rate | Golden privacy replays show zero forbidden rows in proposal, active brain, compiler trace, and rationale |
| P0 | Expose learning input and run health | A sweep can succeed while required seams are empty | Missing feedback table/seam makes run degraded with actionable reason, not “healthy” | Per-seam rows, freshness, empty streak, rejected/error counts | Alert and UI status fire after policy threshold; every no-proposal result has a reason code |
| P0 | Close the Organization `review-to-publish` seam | An Organization proposal may be queued as `human_review`, but the review endpoint only sets `learning_objects.state=promoted` and appends a transition; it never calls `publish_brain`, so review approval does not publish `learned_brain_entries` | Approve a locked Organization proposal and prove one governed publish, one learned-brain version, and one downstream activation receipt; reject, crash, retry, stale-policy, and concurrent-review variants must not double-publish | Approved-without-publish count and age; approval-to-publish latency; duplicate publish attempts | Approval atomically locks/reloads immutable proposal evidence, re-runs current policy/preflight, invokes the governed publisher, records learned-brain/version and compiler-consumption receipts, or persists `approved_unpublished` with accountable recovery; promoted state alone is never success |
| P0 | Guarantee `policy-load fidelity` for block lists | `LearningPolicy` and preflight support `blocked_targets` and `blocked_subject_prefixes`, while `load_or_seed_policy` drops both during query/construction; a stored prohibition can therefore disappear before evaluation | Seed, load, restart, and update a policy containing both block lists; byte-equivalent normalized values must reach preflight and reject the same proposal on every path | Loaded-versus-stored policy mismatch rate; incomplete-policy abstentions; blocked proposal escape rate | Query, constructor, persistence, cache/reload, and trace retain both lists exactly; absent or malformed required fields produce `policy_incomplete`, never a permissive default |
| P0 | Ratify and enforce an `Adaptive TTL decision` | Direct Behavior/Adaptive evolution currently returns `[]`; recommendation learning can create Adaptive proposals, but `LearningObject` permits `expires_at` only for Runtime, so the promised short-horizon Adaptive TTL/decay is not representable | Replay a time-bounded fundraising cadence through creation, approval, selection, expiry, supersession, pivot, rollback, and clock-boundary cases | Adaptive entries missing expiry/decay; stale Adaptive influence; expiry/supersession latency | Before any Adaptive publication, choose and implement one contract: represent mandatory Adaptive expiry/decay end to end, or prohibit Adaptive publication and express temporary guidance as a Runtime lease; non-expiring Adaptive proposals fail closed |
| P1 | Implement bounded Behavior cohort candidate | Direct Behavior evolution currently emits no proposal | Repeated role-specific behavior changes only that user/team/role brain | Eligible cohorts; promoted cohorts; false generalization rate | Sparse evidence abstains; role switch selects correct version; rollback restores predecessor |
| P1 | Implement Adaptive cohort only under the ratified lifecycle contract | Short-horizon play/timing learning currently emits no direct proposal, while Recommendation Learning can emit durable Adaptive that cannot carry expiry | If mandatory Adaptive TTL/decay is implemented, verified investor-update outcomes tune only fundraising cadence and expire through that lifecycle; otherwise Adaptive publication stays prohibited and temporary guidance uses Runtime | Adaptive lift where enabled; rejected non-expiring proposals; Runtime TTL compliance; stale durable influence | The chosen branch is exclusive and testable: enforce Adaptive TTL/decay end to end, or publish no Adaptive and **expire Runtime only** for temporary guidance; existing durable Adaptive needs separate governed deactivation/supersession |
| P1 | Implement explicit preference and temporary-memory inboxes | Both canonical units return `[]` | “Pause outreach for seven days” becomes a scoped runtime lease, not permanent policy | Parse confirmation rate; TTL compliance; scope corrections | Ambiguous/broad text requires confirmation; policy conflict rejects; expiry has zero later influence |
| P1 | Complete durable-brain version/reset boundary | Current reset updates Runtime `temporary_memories` only; it does not supersede Organization, Behavior, or durable Adaptive learned entries | ICP pivot first records Runtime reset as incomplete for durable brains, then separately governs each durable supersession/deactivation or justified retention, invalidates dependent snapshots, and re-evaluates open situations | Runtime-reset receipts; durable survivor count; affected snapshot replay coverage | Receipt proves only Runtime changed during reset, names every durable pre/post version and transition, preserves history, and blocks authoritative replay until durable governance is complete |
| P1 | Add publish-to-compiler-to-decision consumption receipt | Stored version and changed package fingerprint are provenance, not proof that a brain value affected judgment | Hold BSO, corpus, and other brains fixed; mutate one governed brain version and prove its authorized **intended decision-field delta** or an explicit deterministic no-effect reason | Published-not-consumed count; semantic-effect coverage; activation lag; hash-only mutation rate | Every active brain version has source/policy/version and compiler receipt plus a typed goal/constraint/candidate/rejection/rank effect or explicit no-effect; **hash/fingerprint-only change fails** |
| P1 | Retract descendants after identity/evidence correction | Append-only correction can leave derived poison active | Corrected identity suspends affected learned entries, recomputes cohorts, and supersedes versions | Correction blast-radius age; active poisoned-version count | Trace reaches every descendant; no corrected evidence remains authoritative |
| P2 | Make thresholds population- and sensitivity-aware | Uniform observation/day/entity gates are weak for sparse and sensitive cohorts | One-person tenant gains bounded personal adaptation without claiming population truth | Confidence calibration by population; privacy suppression rate | Policy fixtures cover 1, 3, 10, 100+ entities and sensitivity classes |
| P2 | Add causal and counterfactual attribution classes | Correlation is not customer value | Founder would have sent update without card: result is “associated,” not “caused” | Caused/assisted/associated/unknown distribution; calibration | ROI surface never sums association/unknown into attributed value |
| P2 | Operationalize Expert-knowledge review | Suggestion generation exists; review-to-corpus proof is missing | Poor rule outcome opens accountable review; approval produces tested corpus version | Review SLA; accept/reject rate; post-release regression | Expert Brain changes only through reviewed diff, corpus validation, release receipt, and rollback |
| P2 | Add model-assist governance and cost receipts | Free-text parsing is useful but unsafe as authority | Ambiguous correction abstains; provider outage queues review and leaves deterministic accounting intact | Calls, tokens, cache hits, parse failures, dollars per accepted proposal | LLM cannot set score/target/confidence/publish; daily cap and zero-cross-tenant batching tested |

## Golden acceptance scenarios

### A. Theresa / Antler reconsideration

Input: Theresa said to keep sending updates and she may reconsider; two or three updates were sent without reply. Expected: no “rejected, one last chance” learning. The system maintains a fundraising relationship state, verifies which updates were delivered, calculates justified cadence, and reminds the owner/agent only when the next material update exists or cadence is due. Silence is unknown, not rejection. A later reconsideration reply becomes one outcome and can update the bounded fundraising play.

### B. Duplicate external outcome

Input: Gmail ingestion, delivery webhook, and an agent report all see the same reply. Expected: one canonical outcome, three source aliases, one attribution evaluation, no support inflation. A conflicting agent label is quarantined with visible recovery.

### C. Explicit correction

Input: user marks a card “not relevant—already completed elsewhere.” Expected: the open loop reconciles, the verdict revision is stored, completion is verified or remains unproven, and the same card does not return. The play is not penalized merely because the UI was stale.

### D. Temporary instruction

Input: founder says “Do not contact this investor until September 1.” Expected: bounded runtime directive with actor, subject, reason, source, start, expiry, policy check, and consumer receipt. No permanent Behavior or Organization rule is created.

### E. Company pivot

Input: ICP changes from startups to enterprises. Expected: current reset deactivates and truncates matching Runtime `temporary_memories` only and reports durable-brain reset incomplete. Organization, Behavior, and durable Adaptive rows remain byte-for-byte active until separately reviewed and superseded/deactivated or explicitly retained; dependent Layer 3 snapshots are invalidated before authoritative replay. If the ratified Adaptive contract supports TTL/decay, expiry occurs through that separate lifecycle. If Adaptive publication remains prohibited, temporary guidance must expire Runtime only and no new durable Adaptive is created. History is preserved and old-ICP authority reaches zero only after the governed durable transitions complete.

### F. Privacy restriction

Input: private customer-support fact correlates with churn but is `never_commercial`. Expected: it may support allowed service/safety handling, but contributes zero evidence to Sales or commercial rationale. Redaction at UI alone is insufficient.

### G. Organization approval must publish or remain visibly incomplete

Input: an Organization proposal reaches `human_review` and an authorized reviewer approves it. Expected: approval reloads the locked proposal, re-runs the current policy and preflight, calls the governed publisher, creates exactly one `learned_brain_entries` version, and records activation/consumption lineage. A publish error, process crash, policy race, or retry persists `approved_unpublished` plus recovery ownership; merely changing `learning_objects.state` to `promoted` is prohibited from reporting success.

### H. Stored block lists survive every policy load

Input: the active policy blocks the Adaptive target and subject prefix `customer.support.private`. Expected: seed, database reload, service restart, cache refresh, and policy update preserve `blocked_targets` and `blocked_subject_prefixes`; preflight rejects matching proposals with the stored policy version. A missing, malformed, or partially loaded field yields `policy_incomplete` and no proposal evaluation or publication.

### I. Adaptive expiry is representable or Adaptive publication is prohibited

Input: recommendation learning proposes a short-horizon fundraising cadence as Adaptive. Expected: under the ratified contract it either carries enforceable expiry/decay through proposal, review, publish, selection, supersession, rollback, and compiler consumption, or is rejected and represented as an expiring Runtime lease. A non-expiring Adaptive entry, expired influence, or silent conversion to permanent guidance is prohibited.

## Metric contract

| Metric family | Required Metric | Correct numerator / denominator | Anti-metric |
|---|---|---|---|
| Input health | Canonical seam coverage | Valid events loaded / expected eligible source events | Sweep count |
| Reconciliation | Canonical outcome completeness | Outcomes with exposure, action, delivery, external result, window / all outcomes | Raw card events |
| Data quality | Duplicate/conflict rate | Deduped or quarantined collisions / incoming candidate events | Silently dropped rows |
| Learning yield | Valid proposal yield | Validated proposals / eligible reconciled cohorts | Objects emitted per run without eligibility |
| Promotion quality | Promotion precision | Promoted versions later supported / evaluable promoted versions | Approval count |
| Consumption | Active consumption coverage | Active brain versions with Layer 3 receipt / active versions | Stored versions |
| Decision effect | Intended decision-change rate | Replays changing intended decision only / promoted-version replays | Any text difference |
| Outcome lift | Incremental outcome change | Comparable proven outcome delta versus counterfactual/control | Deals correlated with a card |
| Attention | Net attention cost | Reminders + escalations + false actions per proven value event | Notification opens |
| Calibration | Confidence calibration error | Predicted probability versus observed comparable outcome | Average confidence |
| Privacy | Forbidden-use escape rate | Forbidden evidence reaching unauthorized target / attempted forbidden evidence | Number of policies configured |
| Recovery | Mean correction-to-clean time | Time until all descendants are suspended/recomputed | Time to append correction row |
| Review publication | Approved-without-publish exposure | Approved Organization objects lacking learned-brain publish and activation receipts / approved Organization objects | Objects whose state merely says `promoted` |
| Policy fidelity | Policy-load mismatch rate | Loaded policies differing from persisted governed fields / policy loads | Policy-row fetch success |
| Adaptive lifecycle | Stale Adaptive influence rate | Expired, undecayed, or contract-ineligible Adaptive entries affecting selection / Adaptive entries evaluated | Adaptive proposal count |
| Semantic consumption | Brain decision-effect coverage | Active learned versions with typed intended decision-field delta or explicit deterministic no-effect receipt / active learned versions replayed | Changed package hash/fingerprint |
| Cost | Cost per accepted learning change | Model + compute + review cost / consumed validated versions | Cost per token alone |
| Product truth | Analytics reconciliation error | Absolute API-versus-ledger mismatch | Dashboard refreshes |

## Release sequence

1. Build canonical event/outcome and verdict reconciliation; do not start with model prompts.
2. Enforce privacy/use constraints and expose seam/run health.
3. Make customer analytics truthful.
4. Close Organization `review-to-publish` with idempotent publication and visible recovery; promoted state without a learned-brain receipt remains incomplete.
5. Prove `policy-load fidelity`, including both block lists, across persistence, restart, cache, evaluation, and publication paths.
6. Ratify the `Adaptive TTL decision`; implement lifecycle representation end to end or keep Adaptive publication disabled and use Runtime leases.
7. Implement Behavior candidates and the durable-brain reset boundary; implement Adaptive candidates only if the ratified lifecycle makes them representable, otherwise keep Adaptive publication prohibited and use Runtime leases.
8. Prove governed publish is consumed by Layer 3 and Layer 4: a package hash is lineage only; require the authorized decision-field effect or explicit no-effect receipt.
9. Run golden replays, shadow on real tenant data, calibrate thresholds, then grant bounded authority.
10. Add optional LLM parsing/reviewer assistance only after deterministic contracts are green.

## Final Exit gate

Layer 7 moves from **framework-ready** to **conditionally trustworthy** only when all nine golden scenarios pass with zero skips; Organization review has atomic, idempotent `review-to-publish` or a durable `approved_unpublished` recovery state; `policy-load fidelity` preserves `blocked_targets` and `blocked_subject_prefixes` exactly and fails closed as `policy_incomplete`; the `Adaptive TTL decision` is implemented across creation, publication, selection, expiry/decay, supersession, rollback, and consumption—or Adaptive publication remains prohibited and bounded temporary guidance uses Runtime; current reset is reported as Runtime-only until separate durable-brain transitions and snapshot invalidations complete; every active learned version has evidence, target, policy, scope, expiry where applicable, predecessor, rollback, compiler receipt, and a typed intended decision-field delta or explicit deterministic no-effect; a hash/fingerprint-only change fails acceptance; stats reconcile exactly; forbidden evidence escape is zero; duplicate outcomes count once; ambiguous feedback abstains; and a measured cohort shows better decision/outcome quality against a declared counterfactual. Outcome-proven requires real customer evidence beyond deterministic replays.

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "../04-Loopholes-Edge-Cases-and-Fail-Closed/README.md" (M4.C3.L-logic.V0.U01)
include "../05-LLM-Use-Cases-and-Cost/README.md" (M4.C3.L-logic.V1.U01)
-->
