# Typed Contract and Provenance Matrix

**Pinned source:** `harsh/mvp@b739bd5ca682d09550acc400ed2892c38c8518f8`, audited 2026-08-22. This matrix synthesizes the seven verified layer architecture reports. “Present” means a contract/code artifact exists; it does not mean that the same object is authoritative on the customer-visible path.

## The one chain the product must be able to prove

```text
SourceEvent / qualified signal
  → BusinessSituationObject
  → ExpertisePackage
  → DecisionObject + ReasoningTrace
  → ExecutionObject
  → DeliveryObject + DeliveryResult
  → LearningObject proposal + governed brain/metric version
```

Every arrow is a contract. If any producer reconstructs missing provenance, defaults visibility, invents confidence, loses authority state, or hands a legacy projection around the declared consumer, later safety cannot repair the meaning. The customer needs one trace from source evidence to verified outcome—not seven locally valid schemas.

## Seven-boundary contract matrix

| Layer / boundary object | Required producer → consumer | Current authoritative shape | Provenance and version required | Visibility / permitted use | Confidence semantics | Trace / hash requirement | Current contract gap | Fail-closed output |
|---|---|---|---|---|---|---|---|---|
| **L1 SourceEvent / QualifiedEnterpriseSignal** | Connector/capture → Context | `SourceEvent` then `GatedEvent`; Atlas-grade qualified signal is not emitted | Provider event/object/thread ids, source version, capture/world time, raw/preprocess/gate versions, evidence spans | Source ACL/audience stamped once; downstream may only narrow | Relevance, business importance and lifecycle must be separate; triage P0–P3 is processing order only | Stable dedup key plus immutable source/prepared-content receipts | `GatedEvent` omits typed requester/recipient roles, visibility, normalized signal type, formula importance, business lifecycle and expiry | `park` / `review_source`; never reconstruct permission or role downstream |
| **L2 BusinessSituationObject** | Context graph/situation engine → Domain Expertise | Contract exists; producer builds a thin BSO with one anchor, reconstructed evidence, empty relationships/dependencies and neutral importance | Exact member signal ids, graph/spec/extractor versions, fact/source receipts, state transitions and conflict history | Narrowest member visibility, exclusions and use constraints | Preserve evidence/freshness/consistency/identity vector, coverage and missing fields; no constant priority | Situation version + bounded membership hash; no synthetic receipt accepted as complete | Producer hardcodes `org`, allows synthetic signal/evidence fallback, empties missing fields and can expose person-wide state | Review/suppress when subject, role, membership, visibility or current state is unresolved |
| **L3 ExpertisePackage** | Domain compiler + four-brain snapshot → Reasoning | Typed deterministic package exists; compiler is default-off/shadow for live authority | Domain/situation/capability/object/rule/playbook versions, corpus hash, evidence requirements and exclusions | Permission axis Organization → Expert; preference axis Adaptive → Organization → Behavior → Expert; narrowest visibility wins | Expertise coverage is separate from input evidence and later decision confidence | `brain_snapshot_id` combines Expert and runtime-brain snapshots; entries carry versions/hashes/confidence/learning ids | Registry counts are Sales 46 total / 3 non-stub, Support 49 / 9, Admin 57 / 0; all 12 non-stub entries are **draft/unreviewed**, with **zero reviewed or accepted**. The resolver admits any `stub:false`; active cards still use legacy `SALES_V1`/`GENERAL_V1` | Unsupported/partial package with no action-authorizing playbook; review-state admission must reject draft/unreviewed entries, and legacy must not override abstention |
| **L4 DecisionObject / ReasoningDecision** | Reasoning units + Decision Maker → Executive | Rich candidate/outcome contracts exist; active adapters commonly supply one play and six units | Input package id, manifest/unit versions, candidate/rejection evidence, scoring/config versions and expiry | Candidate eligibility must preserve package visibility/permission and owner/approval constraints | Priority, urgency, coverage and calibrated decision confidence are distinct; hard gates cannot be averaged | Full ReasoningTrace: scheduled/executed/skipped units, candidate generation, elimination, ranking and selected/no-selection | Organization/Behavior/Adaptive content has **hash-only influence** in the adapter: it changes snapshot hash/version but not goal, constraints, policies, eligibility or ranking. Expert input is also narrow: a question may set the goal and at most four rules with `definition.steps` become plays. Card projection then uses generic imperatives, maps score to confidence, and permits `stakes: missing` / `completion: missing` | `NO_ACTION`, `DEFER`, `INSUFFICIENT_CONTEXT` or `BLOCKED`; no presentation fallback imperative and no claim of brain influence without a mutation replay that changes judgment |
| **L5 ExecutionObject** | Executive compiler/supervisor → Delivery and outcome store | Immutable content-addressed object is Present/Wired on native commitment path; legacy card action is parallel | Decision/reasoning/context/config lineage, action/dependency ids, owner/approval, clocks, success semantics and revisions | Owner and target must already be unambiguous; approval and scoped action authority recorded | Decision confidence is inherited evidence, not execution progress; completion/outcome are observed states | Idempotent execution id, immutable semantic payload, append-only lifecycle/action/outcome receipts | “I’ll do it” can update card/signal without planned action/execution/outcome; agent handoff is 501; routing ownership is unratified | Waiting/review/cancelled/unproven when authority, target, approval, dependency or success evidence is missing |
| **L6 DeliveryObject / DeliveryResult** | Delivery control plane/worker → recipient/channel + Learning | Legacy durable outbox/gate/Slack path is Wired; Atlas-shaped v2 object/control plane is Present but not production-composed; no single enforced typed `DeliveryResult` class | Execution/decision lineage, dedupe key, fence token, attempt/provider ids, route ladder, policy/config versions and receipts | Re-resolve lawful audience at send time; most restrictive gate wins; never widen upstream visibility | Delivery certainty/engagement is transport truth, not decision correctness or business outcome | Durable outbox event, fenced attempt chronology, provider reconciliation and terminal/suppressed result | v2 resolve/materialize/claim has no production caller; legacy has one operational human adapter; timeout/provider reconciliation and atomic bridge gaps remain | DEFER/SUPPRESS/FAILED result with receipt; never silently drop or treat nondelivery as rejection |
| **L7 LearningObject** | Reconciled execution/delivery/enterprise/verdict evidence → governed publisher | Rich contract, selector and several units exist; explicit feedback/preference/temp-memory and direct Behavior/Adaptive evolution are stubs | Recommendation exposure, actual action, external result, outcome window, counterfactual, independent sources, proposal/policy/target/version/TTL/supersedes | Preserve source permitted use and excluded subjects; target only Organization/Behavior/Adaptive/Runtime/metrics or Expert-review queue | Support, independence, noise, conflict, value and population-aware confidence; click/completion-unproven is never success | Immutable evidence cohort and proposal id; governed promotion/rollback receipt; future brain snapshot links learning id | Outcome truth is fragmented; Organization review approval changes proposal state but does not publish a brain entry; policy loading drops both `blocked_targets` and `blocked_subject_prefixes`; recommendation learning may create Adaptive objects even though the contract permits expiry only for Runtime, so Adaptive TTL/decay is unrepresentable | No promotion without a review-to-publish receipt; neutral/unproven remains non-positive; loaded policy must equal stored policy; non-expiring Adaptive proposals remain blocked pending an explicit contract decision; rollback may select only a predecessor that remains unexpired and permitted under current policy, visibility and permitted-use constraints—otherwise learned influence stays disabled; Expert Brain never auto-mutates |

## Cross-layer provenance envelope

Every boundary object needs a common envelope or an equivalent mechanically verified mapping:

| Envelope field | Meaning | Creation owner | Mutation rule | Required downstream proof |
|---|---|---|---|---|
| `tenant_id` | Security and learning boundary | L1 connection/capture | Immutable | Present on every row, cache and trace |
| `trace_id` | One end-to-end derivation | L1 publication | Immutable; child spans append | Links source → situation → package → decision → execution → delivery → learning |
| `object_id` + `schema_version` | Typed boundary identity | Producing layer | New version/object, never in-place semantic rewrite | Consumer rejects unknown/incompatible schema |
| `source_refs` | Provider/thread/event/span receipts | L1, narrowed/annotated by later layers | Append derivation; never fabricate | User/reviewer can reopen decisive evidence |
| `parent_ids` | Exact upstream objects consumed | Every producer | Immutable set for that output | No legacy bypass or synthetic parent hidden |
| `visibility` + `permitted_use` | Audience, exclusions and purpose | Source authority in L1 | Intersection/narrowing only | Every selection, cache, delivery and learning cohort enforces it |
| `semantic_hash` | Canonical content and policy inputs | Every typed producer | Changes when meaning/version changes | Replay compares exact input/output, not display text |
| `authority_mode` | shadow, advisory, authoritative, revoked | Wiring/promotion controller | Append-only transition receipt | Customer card identifies which path won |
| `confidence_vector` | Layer-owned evidence dimensions | Owning layer only | Later layer adds its dimension; never aliases another | No score-to-confidence mapping |
| `missing_fields` / `conflicts` | What blocks authority | Producing layer | Can close only with cited evidence/version | Missing hard field cannot disappear at projection |
| `expires_at` / `supersedes` | Current validity | Owning layer | New object supersedes; history retained | Stale decision/execution/delivery cannot act |

## Confidence ownership

| Dimension | Owner | Valid input | Invalid substitution |
|---|---|---|---|
| Capture relevance/source authority | L1 | Source and evidence qualification | Inbox age or triage lane as business value |
| Situation evidence/freshness/consistency/identity/coverage | L2 | Bounded current-state graph | Generic domain with no expected fields as 100% complete |
| Expertise coverage/runtime-brain quality | L3 | Accepted capability closure and snapshot | YAML/file count or valid hash as expert completeness |
| Decision confidence/priority/urgency | L4 | Eligible candidate comparison and calibrated correctness | Card priority score relabelled confidence |
| Execution state/outcome evidence | L5 | Action/dependency and post-creation success receipts | User acceptance/click as completion |
| Delivery/engagement certainty | L6 | Provider/client receipts and attempt chronology | Open/click as business success |
| Learning proposal confidence | L7 | Independent reconciled outcomes and policy gates | Recommendation score, one click or nondelivery as efficacy |

No layer may overwrite an upstream dimension with one scalar. The final UI may summarize, but it must retain the vector and expose the blocking minimum/hard gate.

## No-silent-drop seam rules

1. A producer writes either a valid typed output or a typed `park/review/defer/suppress/no-promotion` receipt; absence is never an outcome.
2. A consumer records the exact parent object and schema/version it accepted. Legacy fallback cannot secretly become authority after a new-path abstention.
3. Visibility and permitted use are stamped at source and intersected at every merge, cache, package, decision, delivery and learning cohort.
4. Synthetic ids/evidence, defaulted visibility, missing role/current state, stub or draft/unreviewed expertise, missing stakes/completion, unresolved owner/approval and unverified outcomes are hard missingness—not low scores.
5. Action acceptance, execution, completion, external outcome and attributed value remain different events.
6. Every replay pins source/graph/corpus/four-brain/manifest/config/model/policy versions and produces comparable hashes.

## Blunt synthesis verdict

The repository has meaningful typed contracts at every layer, but not one authoritative typed chain. The two most damaging breaks occur early and late: L1→L2 loses role/visibility semantics, and L4→L6 splits rich decisions/executions from legacy cards/delivery. Learning then receives fragmented outcomes. Until the provenance envelope and fail-closed seam rules are enforced end to end, a valid object inside one layer cannot be presented as proof of high-quality customer intelligence.

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "../01-Layer-1-Knowledge/01-Architecture-and-Atlas-Delta/README.md" (M2.C1.L-contract.V0.U01)
include "../02-Layer-2-Context-Intelligence/01-Architecture-and-Atlas-Delta/README.md" (M2.C2.L-contract.V0.U01)
include "../03-Layer-3-Domain-Expertise/01-Architecture-and-Atlas-Delta/README.md" (M3.C1.L-contract.V0.U01)
include "../04-Layer-4-Reasoning/01-Architecture-and-Atlas-Delta/README.md" (M3.C2.L-contract.V0.U01)
include "../05-Layer-5-Executive/01-Architecture-and-Atlas-Delta/README.md" (M4.C1.L-contract.V0.U01)
include "../06-Layer-6-Delivery-Atlas-5.2/01-Architecture-and-Atlas-Delta/README.md" (M4.C2.L-contract.V0.U01)
include "../07-Layer-7-Learning-Atlas-6/01-Architecture-and-Atlas-Delta/README.md" (M4.C3.L-contract.V0.U01)
-->
