# Layer 3 — Loopholes, Edge Cases, and Fail-Closed Rules

**Audit scope:** `harsh/mvp@b739bd5ca682d09550acc400ed2892c38c8518f8`. A **Loophole** satisfies a present check while violating the intended guarantee. An **Edge case** is a legitimate operating shape. “Fail closed” means Layer 3 returns bounded observation/review/unsupported coverage and supplies no action-authorizing playbook; it does not mean silently falling back to generic Sales.

## Why this layer is dangerous when it looks complete

Layer 3 is the point where facts acquire professional meaning. A structurally valid `ExpertisePackage` can still be strategically empty, scoped to the wrong person, built from stub material, or driven by a non-stub authored draft that is still `draft/unreviewed`. The current compiler has strong visibility and conflict machinery, but the repository’s 0-error validator result coexists with 715 warnings, partial routing, zero reviewed or accepted capabilities, and default-off shadow execution. That creates a specific risk: the system can prove that it compiled **something** while the customer assumes that a seasoned expert approved it.

The dynamic-brain lifecycle has a separate current-code contradiction. In `feedback/units.py:165-182`, **direct Behavior/Adaptive evolution returns no candidates**; recommendation learning can nevertheless emit a durable Adaptive proposal without `expires_at` (`:187-219`). `LearningObject` permits expiry only for Runtime, so **Adaptive cannot carry expiry** (`contracts/learning.py:184-227`). Current code does not automatically reject the omitted-expiry path. Until one lifecycle contract is ratified and enforced by the producer, publisher, reader, compiler and rollback path, the required safe disposition is `adaptive_ttl_unresolved`: exclude the entry and block any prescription that depends on it.

## Loophole register

| Loophole | Mechanism that currently permits it | Consequence | Fail closed rule | Proof required to reopen |
|---|---|---|---|---|
| File count equals capability claim | Sales has 46 files: 43 stubs and 3 non-stub authored drafts; all three are unreviewed | Marketing/runtime reports “46 active skills” or “3 complete skills” without accepted expert depth | Stub and draft/unreviewed capability are unavailable for prescriptive authority | Capability has authored objects, rules, plays, failures, named reviewer, accepted hash and golden tests |
| `stub:false` equals production admission | `capability_resolver.py:96-105` skips only `identity.stub: true` and ignores `status`, `review_status` and `reviewed_by` | Any draft/unreviewed capability can enter an `ExpertisePackage` | Emit unaccepted-coverage receipt; no action-authorizing package | Review-state admission proves accepted status, reviewer, acceptance time and immutable content hash |
| Schema-valid equals expert-valid | `validate.py` reports 0 errors while reporting 715 warnings | Empty/reachable shells look production-ready | Any required warning class blocks promotion for that route | Zero blocking warnings for promoted dependency closure |
| Shadow result equals live authority | `domain_shadow.py:93-125` compiles and reasons, but legacy output still wins | Team believes new rules caused a card they never influenced | Trace labels `SHADOW`; no customer-value claim | Runtime receipt identifies package as authoritative for scoped cohort |
| Global flag equals safe rollout | `use_domain_compiler` is a broad default-off flag | One switch may activate unsupported domains and stubs | Promotion key must include domain, situation, capability/version and tenant/cohort | Golden suite and rollback receipt for each promoted key |
| Route exists, dependencies incomplete | Sales has seven and Support has three all-stub routes; generated registry validity does not make them executable | A valid route can throw after matching or imply shallow coverage | Resolve to accepted dependency closure or typed abstention | Registry CI proves every required capability/artifact accepted and reachable |
| Confidence hides coverage | Evidence confidence can be high while expert capability is absent | 94% “confidence” legitimizes generic advice | Coverage is a separate blocking dimension | API/UI shows expertise coverage and prevents prescriptive output below gate |
| Valid snapshot means useful brains | Hashing proves reproducibility, not population or truth | Empty/stale Organization/Adaptive entries look “personalized” | Mark absent, stale, conflicted and unproven entries explicitly | Tenant snapshot quality/freshness/outcome checks pass |
| Hash changed equals brains constrained reasoning | `reason/adapters/expertise.py:180-188` hashes Expert, Organization, Behavior and Adaptive fields into `knowledge_hash`, while `_plays` consumes only `expert_rules`, `_goal` only a capability question, and the DAG is generic | Company policy or learned preference may produce a new manifest version without changing candidate generation, rejection, ordering or wording—**hash-only influence** | If a selected brain entry has no declared semantic projection, deny prescriptive authority and expose the unused entry | Metamorphic test changes one Organization/Behavior/Adaptive entry and proves the expected constraint, candidate or rank changes—not only the hash |
| Explicit conflict keys are enough | `runtime_brains.py:136-190` resolves keyed conflicts | Semantically conflicting unkeyed policies can coexist | Normalize policy ontology; unresolved semantic conflict blocks permission | Adversarial equivalent-language conflict fixture passes |
| Preference confidence equals authority | Learned entry has high confidence | Behavior/Adaptive habit is treated as policy | Learned brains never grant permission; Organization → Expert governs permission | Resolution trace proves rejected learned permission claim |
| Legacy fallback is graceful degradation | Unsupported new expertise falls back to `SALES_V1`/`GENERAL_V1` | Unknown domain receives confident generic Sales imperative | Unsupported means explicit no-decision/review, not legacy prescription | Safe fallback contract tested on all unsupported situations |
| Person-wide retrieval equals context | All messages for a contact are gathered | Unrelated roles, intros and opportunities contaminate package | Scope by relationship, opportunity, thread and time | Cross-role fixture excludes irrelevant facts |
| Calendar record equals completed meeting | Event exists and time passed | False recap and follow-up playbook | Require occurrence/attendance or corroborated outcome evidence | Cancelled/no-show/internal fixtures all suppress recap |
| Source quote equals open commitment | An old availability/proposal sentence is present | User’s completed or superseded statement becomes overdue work | Require direction, owner, accepted state and absence of completion | Thread replay proves current unresolved state |

## Edge case register

| Edge case | Required interpretation | Failure pattern | Consequence if wrong | Fail closed result |
|---|---|---|---|---|
| One person has investor, customer, partner and introducer roles | Compile per relationship/opportunity/thread, not person globally | Role collapse | Wrong playbook and privacy boundary | Review role graph; no prescriptive package |
| Connector sends repeated introductions | Connector is actor; introduced party is business subject | Boardy becomes target; x77 intros aggregate | Spam connector, lose actual opportunities | Split BSOs and packages by introduced contact |
| Investor asks for periodic updates then stops replying | Consider requested cadence, material update value, sent history and reconsideration condition | “Rejected/last chance” invented from silence | Damaged investor relationship | Fundraising expertise or explicit unsupported review |
| Prospect becomes paying customer mid-thread | Lifecycle transition changes applicable domain and permitted playbooks | Stale Sales chase after conversion | Poor customer experience | Refresh state and suppress superseded Sales rules |
| Proposed meeting is rescheduled, cancelled, then held elsewhere | Reduce multiple events to one verified current state | Every historical event fires | Duplicate/conflicting cards | Wait for reconciled occurrence and completion state |
| Internal workshop has many attendees but no external counterparty | It is not automatically a revenue follow-up | Calendar recap heuristic | User is asked to email themselves/team | Suppress external-action playbook |
| Restricted support statement also signals expansion | Purpose/visibility limitation survives domain crossover | Useful fact copied into Sales | Privacy and trust violation | Observation only unless consent/purpose explicitly permits reuse |
| Bank-detail change comes from known vendor address | Known identity is insufficient for high-risk instruction | Familiar sender bypasses verification | Financial fraud | Admin capability requires out-of-band verification and dual approval |
| Two companies share contact domain/name | Identity evidence conflicts | Company-name match chooses wrong account | Data leakage/wrong commercial action | Block until authoritative entity resolution |
| Adaptive preference was valid last quarter | Recency and phase changed; current durable Adaptive has no enforceable expiry | Highest-precedence preference remains stale | Wrong tone/cadence | Return `adaptive_ttl_unresolved`; exclude it and block dependent prescription. Expiry/fall-through is only a post-repair contract, not current behavior |
| Organization policy differs by geography/product | Permission is conditional, not global | One policy entry applies everywhere | Compliance failure | Require matching scope dimensions or defer |
| Correct domain lacks authored situation route | Input is legitimate but unsupported | Nearest-route guessing | Plausible but wrong expertise | Return uncovered type and request authoring |
| Multiple applicable capabilities disagree | Conflicting professional models need explicit resolution | First registry result wins | Non-auditable selection | Carry conflict to Layer 4 or require expert review |
| Sparse new company has no learned brains | Expert defaults may apply only within hard boundaries | Fake personalization | Misleading confidence | Label runtime brains absent; use bounded Expert defaults |
| Company rule changes but adapter projection does not | Snapshot and `knowledge_hash` change, yet the generic DAG/play may remain behaviorally identical | Hash-only influence is reported as applied company judgment | Policy appears enforced when it only changed provenance bytes | Surface entry as selected-but-unused and abstain where it is decision-critical |
| Draft is accepted, then bytes change without new review | Current source hash differs from the hash the reviewer accepted | Stale approval appears to cover new semantics | Unreviewed advice acquires inherited authority | Revoke admission and require re-review of the new immutable version |

## Hard fail-closed matrix

| Trigger | Layer 3 output allowed | Layer 3 output prohibited | Recovery evidence |
|---|---|---|---|
| Ambiguous business subject/role | Diagnostic receipt and required source | Playbook aimed at any person | Role-scoped identity resolution |
| No accepted route | Unsupported situation + closest taxonomy for authoring only | Nearest capability as executable expertise | Accepted situation-capability route |
| Required capability/object is Stub or draft/unreviewed | Coverage gap, review state and dependency list | Generic substitute or unaccepted draft presented as deep expertise | Accepted authored dependency closure with reviewer/hash receipt |
| Selected brain entry has hash-only influence | Selected-but-unused entry list and diagnostic package | Claim that Company/Behavior/Adaptive brain constrained the recommendation | Typed semantic projection plus metamorphic downstream-effect test |
| Short-horizon Adaptive is requested but lifecycle is unrepresentable | `adaptive_ttl_unresolved`; exclude entry and identify the lifecycle decision owner | Publish/select a durable omitted-expiry Adaptive entry or pretend it expired | Ratified Runtime-lease or Adaptive TTL/decay contract with pinned-clock publish, selection, expiry, supersession and safe-rollback replay |
| Visibility/purpose conflict | Exclusion trace; review request | Inclusion because fact is commercially useful | Explicit permission/consent within scope |
| Permission conflict unresolved | Conflicting entries and source receipts | Preference-based override | Organization/Expert resolution or human policy decision |
| Decisive evidence stale/missing | Missing-input contract | Scalar confidence plus imperative | Fresh corroborated evidence |
| Snapshot cannot be reproduced | Error/defer | Unpinned package | Stable Expert/runtime hashes and versions |
| Domain compiler in shadow | Parity metrics only | Claim that card used new expertise | Authoritative scoped runtime trace |

## Invariants that must be mechanically enforced

1. No action-authorizing package may reference a Stub, unreachable, review-rejected, or draft/unreviewed capability; non-authoritative diagnostics must label these states.
2. Every included rule/playbook must carry domain, capability version, source hash and visibility/purpose scope.
3. An unsupported domain or emitted situation must produce an explicit typed abstention.
4. Organization/Expert permission conflicts are blockers; Adaptive/Behavior cannot grant authority.
5. Preference resolution is independent and uses Adaptive → Organization → Behavior → Expert only among valid, in-scope entries.
6. The package must state coverage and missing dependencies independently of evidence confidence.
7. Package identity must be reproducible from BSO/evidence and four-brain snapshots.
8. Legacy fallback cannot convert a new-path abstention into a prescriptive card.
9. Review-state admission must bind accepted status, named reviewer and acceptance timestamp to the exact immutable content hash.
10. A selected Organization, Behavior or Adaptive entry must have a typed semantic consumer and observable downstream effect; inclusion in `knowledge_hash` alone is not influence.

## Verdict

The new architecture has unusually good ingredients for failing closed, especially typed compilation, snapshot hashing, visibility filtering and two precedence axes. The operational loophole is outside and around those controls: incomplete content, partial routing, a permissive legacy fallback and customer-visible scalar confidence. Until promotion gates enforce the matrix above, Layer 3 is **framework-ready, not live-ready** and unsupported cases remain unsafe for prescriptive output.

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "../02-Customer-Expectation-and-HKS/README.md" (M3.C1.L-contract.V1.U01)
include "../03-Current-Successes-Failures-and-Expected-Behavior/README.md" (M3.C1.L-data.V0.U01)
-->
