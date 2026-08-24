# Failure-Closed, Abstention, and Recovery Matrix

## Decision boundary

This matrix is the cross-layer safety contract for the audited baseline `harsh/mvp@b739bd5ca682d09550acc400ed2892c38c8518f8`. It composes the gold-standard intelligence contract with the seven layer-specific loophole catalogs. It does not claim that every control below is live. It distinguishes the safe result that the system must emit from the current loophole that can bypass it.

The governing rule is:

> If GeniOS cannot prove the business subject, current unresolved state, permitted use, expertise coverage, decision quality, authority, owner, completion predicate, and freshness needed for the next transition, it must withhold that transition, preserve the evidence, and emit a typed, recoverable receipt.

Fail closed does **not** mean return an empty list, hide an exception, lower a percentage, replace deep expertise with generic Sales advice, or leave an item in a queue forever. A safe non-action is a first-class result with an owner and a Recovery path. No LLM score, fluent explanation, elapsed time, or customer value estimate can override a failed hard gate.

## Canonical non-action vocabulary

Each object has one authoritative disposition for the attempted transition. These terms are not interchangeable.

| Disposition | Use when | Customer surface | Required recovery condition | Never reinterpret as |
|---|---|---|---|---|
| `Park` | Evidence may be relevant but capture, extraction, identity, visibility, role, completeness, or version is unresolved | Review queue or bounded “processing needs evidence” state | Source retry, human classification, identity resolution, or version repair | Irrelevant, deleted, or safe to act on |
| `Review source` | The exact source can resolve a semantic question such as requester, target, open ask, occurrence, or completion | Source link plus precise question; no action button | Reviewer records the missing scoped fact with provenance | A generic “check this” task or permission to guess |
| `Observation only` | A grounded fact is useful, but no prescriptive action meets the contract | Fact, uncertainty, and why it is non-actionable | New evidence may trigger a fresh bounded evaluation | Weak recommendation, low-priority action, or silent drop |
| `Abstain` | An extractor, compiler, reasoner, or learner cannot support a requested inference within its declared scope | Typed no-decision and failed gate | Accepted route/capability, required context, or sufficient independent support | Generic fallback or nearest-neighbour prescription |
| `Defer` | The proposed transition may be valid later, but timing, dependency, focus window, source window, or approval is not yet ready | “Waiting until/for …” with `not_before` or event trigger | Named clock/event fires, then every hard gate is revalidated | Retry budget consumption, failure, or indefinite backlog |
| `Suppress` | Visibility, permitted use, audience, duplicate/supersession, fatigue, or stop policy forbids publication/delivery | Usually no sensitive content; authorized operators get an opaque receipt and reason | Only an explicit policy/scope/state change can create a new version | Delete history, widen to admin, or retry through another channel |
| `Blocked` | Work is desirable but current authority, approval, accountable owner, safe executor, or required capability is absent | Named blocker and accountable resolver; no execution | Valid scoped authority/approval/owner/capability receipt | Low confidence or permission for a default assignee |
| `Cancel` / `Supersede` | Earlier authority or meaning is no longer current | Historical item marked non-executable with replacement/reason | A new authoritative object, never revival of the stale one | Completion or negative outcome |
| `No action` / `Stop` | Waiting or acting has lower expected value, the loop is already resolved, or an explicit stop condition applies | Rationale, expiry/observation trigger if any, no action button | Material new scoped evidence may open a new evaluation | Missed work or a system error |
| `Quarantine` | Integrity, cross-tenant, schema/version, duplicate-authority, or poisoned-lineage risk exists | Operator-only containment; no downstream authority | Repair plus deterministic replay proves clean lineage | Parked customer work or a usable source |

`Suppress` has the highest precedence when an item is forbidden; `Cancel/Supersede` wins when authority is stale; `Park` or `Review source` wins when evidence is unresolved; `Blocked` wins when an otherwise valid action lacks permission or executor; `Defer` applies only when a known future condition can reopen evaluation. `Abstain` describes the decision unit's inability to decide, while the containing object still receives one of the durable operational dispositions above.

## Three non-collapsible Layer 7 authority states

The following states are separate because they stop different transitions and require different evidence to recover. They must not be collapsed into “learning pending,” “promoted,” a generic TTL warning, or one combined policy error.

| Durable state | Exact Current trigger at `b739bd5` | Transition withheld | Required Recovery receipt | Required operating metrics | Customer/operator truth |
|---|---|---|---|---|---|
| `approved_unpublished` | An Organization proposal enters human review through `feedback/publisher.py:168-188`. Approval through `api/learning_routes.py:119-143` changes the `learning_objects` state to `promoted` and appends a review transition, but does not call `publish_brain` or create an active `learned_brain_entries` version. | No active Organization Brain selection, no future expertise-package influence, no “adapted/published” claim. | Review actor/time, immutable proposal hash, policy revision/hash, preflight result, idempotent `publish_brain` result, active brain/version ID, predecessor/supersession, L3 snapshot/package consumption ID, and rollback result. | Count and oldest age of `approved_unpublished`; approval→publish p50/p95/max; publish→L3-consumption p50/p95/max; duplicate/partial publication count. | “Approved, not published or active.” An approval receipt is not a publication receipt. |
| `policy_incomplete` | `LearningPolicy` defines and preflight enforces `blocked_targets` and `blocked_subject_prefixes` (`contracts/learning.py:267-298`; `feedback/governance.py:31-41`), but `feedback/orchestrator.py:28-45` does not select or reconstruct either list. A persisted restrictive policy can reload as permissive empty defaults. | Abort the tenant learning run before unit evaluation, proposal persistence, promotion or publication; do not use a fallback default policy. | Stored policy revision plus canonical hash, loaded policy revision/hash, lossless equality for every authority-bearing field, both block lists with typed values, preflight decisions for blocked-target and blocked-prefix fixtures, repair actor/time, and resumed run ID. | Policy reload fidelity rate (target 100%); policy hash mismatch count; `blocked_targets`/`blocked_subject_prefixes` loss count (target zero); aborted-run age and recovery latency. | “Learning paused because policy could not be reconstructed safely.” Empty lists are not evidence that nothing is blocked. |
| `adaptive_ttl_unresolved` | Direct Adaptive evolution returns no candidates, but recommendation learning can emit `LearningTarget.ADAPTIVE` without `expires_at` (`feedback/units.py:165-219`). `LearningObject` allows expiry only for Runtime (`contracts/learning.py:184-227`), so a short-horizon Adaptive proposal cannot encode its required lifecycle. | No Adaptive brain publication, activation, package selection or “recent/decaying adaptation” claim. | Ratified lifecycle decision; either an expiring Runtime lease or an Adaptive TTL/decay contract; proposal/entry ID, activation/expiry/supersession clocks, selector exclusion after expiry, pivot invalidation, predecessor/rollback validation and affected L3 package IDs. | Adaptive proposals/entries without representable TTL; active/stale Adaptive influence after expiry (target zero); expiry and supersession timeliness; post-expiry selection count (zero); rollback-correctness rate. | “Adaptive learning is excluded until its expiry law is representable.” Storing or hashing a non-expiring value does not make it short-horizon. |

Recovery is state-specific: publishing an approved Organization proposal cannot repair a lossy policy reload; restoring a policy cannot define Adaptive expiry; defining Adaptive lifecycle cannot activate an unpublished Organization proposal. Every recovery appends a new receipt and replays from the earliest invalid checkpoint. None rewrites the original failure as if it had succeeded.

## No-silent-drop receipt

Every rejected, parked, suppressed, deferred, failed, expired, or abstained transition must append a receipt. Privacy-forbidden content may be omitted, but its opaque identity and policy decision may not disappear.

| Receipt field | Required meaning |
|---|---|
| `receipt_id`, `tenant_id`, `attempted_transition` | Idempotent identity and the boundary that refused progress |
| `object_id`, `object_version`, `source_ids` | Exact evidence/object lineage; never only a person or company node |
| `business_subject_ref`, `relationship_ref`, `thread_or_opportunity_ref` | Roleful semantic scope, or an explicit `unresolved` code |
| `disposition`, `reason_code`, `failed_gate`, `owning_layer` | Machine-readable result and the layer responsible for resolution |
| `policy_version`, `expertise_version`, `graph_version`, `decision_version` | Relevant authority snapshots; absent versions are themselves blockers |
| `created_at`, `expires_at`, `not_before` | Time semantics; only fields applicable to that disposition are populated |
| `recovery_owner`, `recovery_trigger`, `replay_from` | Who acts, what permits retry, and the immutable checkpoint for replay |
| `downstream_invalidations`, `supersedes_receipt_id` | Derived objects that lost authority and the append-only correction chain |
| `safe_customer_summary`, `restricted_detail_ref` | Useful customer explanation without leaking restricted evidence |
| `authority_state`, `policy_hash`, `publication_or_lifecycle_ref` | Distinguishes `approved_unpublished`, `policy_incomplete`, and `adaptive_ttl_unresolved`; fields not applicable remain explicit `not_applicable`, never silently absent |

An empty run must reconcile: `inputs_seen = actionable + observation_only + parked + suppressed + duplicate + terminal_invalid`. Any unexplained difference is a **silent-drop incident**, not “no intelligence.” Suppression and privacy receipts must be access-controlled and retention-limited; auditability is not permission to copy secret content into telemetry.

## Cross-layer fail-closed matrix

| Layer / boundary | Trigger or known loophole at the audited baseline | Required safe result | Prohibited continuation | Recovery owner and proof |
|---|---|---|---|---|
| Layer 1 — ingestion | Relevance classifier is uncertain or destructive LLM skip cannot be reconstructed | `Park` raw item with reason, model/prompt version, source cursor and retry path | Delete as noise or report ingestion complete | Ingestion owner; replay shows the item classified once without evidence loss |
| Layer 1 — extraction | Body/attachment is unavailable, truncated, encrypted, or unsupported | `Park:content_unavailable`; retain raw locator and bounded retry | Emit empty extraction as complete | Connector owner; content hash and successful extraction receipt |
| Layer 1 — visibility | Visibility or permitted use is absent/conflicted | `Suppress` publication and preserve narrow opaque receipt | Default to organization-wide or commercial use | Policy/data owner; explicit inherited scope and purpose proof |
| Layer 1 — mutable source | Update, revocation, deletion, tombstone, or source version cannot be ordered | `Quarantine` affected lineage and invalidate derivatives | Let an older mutable fact remain current | Source owner; monotonic version/tombstone replay and downstream invalidation |
| Layer 1 — coverage | Cursor/window is partial, stale, or provider outage prevents completeness | Mark scoped coverage unknown; forbid silence/absence inference | “No reply,” “nothing sent,” or “no event” from incomplete window | Connector owner; closed source window and cursor continuity |
| Layer 2 — correlation | Same person, company, connector, or thread contains multiple roles/deals/intros | `Park:split_required` or role-scoped observations | Person-wide mega-situation or connector-as-target | Context owner; relationship/opportunity/thread replay yields separate BSOs |
| Layer 2 — business subject | Requester, target, connector, speaker, or exact open action is ambiguous | `Review source`; no prescriptive BSO | Attach quoted/forwarded text to transport sender | Context owner/reviewer; source span plus actor-role graph |
| Layer 2 — completeness | Synthetic membership, empty required-field registry, or generic domain creates apparent 100% coverage | `Observation only` with `context_incomplete` / `requirements_unknown` | Treat a valid shape or synthetic evidence as complete context | Context owner; real qualified members and domain-specific requirement closure |
| Layer 2 — state | Person-global ball-in-court/commitment fields conflict across threads or completion occurs elsewhere | Preserve scoped conflicts; `Review source` or `Park` | Last-write person state, false debt, or broad completion | Context owner; canonical loop ID and one scoped current-state replay |
| Layer 2 — correction | New correction/revocation arrives but dependent rebuild is incomplete | `Quarantine` old BSO authority behind one graph-version fence | Mix old and new graph versions | Graph owner; atomic affected-subgraph rebuild and idempotent replay |
| Layer 3 — route | Domain/situation has no accepted capability route | `Abstain:unsupported`; authoring hint may be diagnostic only | Nearest generic Sales or legacy prescription | Expertise owner; accepted situation-capability route with golden tests |
| Layer 3 — depth | Capability/object/rule/play is Stub, unreachable, warning-blocked, or incomplete | Coverage gap and missing dependency list; `Observation only` | Claim that file count means active expertise | Corpus owner; authored closure, zero blocking warnings, accepted registry reachability |
| Layer 3 — runtime authority | Compiler is shadow/default-off or legacy result remains authoritative | Label `SHADOW`; no customer-value attribution to new rules | Say the card used Layer 3 because compilation succeeded | Runtime owner; trace names authoritative package/cohort and rollback key |
| Layer 3 — brain conflict | Organization/Expert permission conflict or stale/invalid learned preference | `Blocked` for permission; exclude expired preference | Let Behavior/Adaptive confidence grant authority | Policy/expertise owner; resolved scoped entries and reproducible brain snapshots |
| Layer 3 — evidence scope | Restricted support evidence would improve Sales advice | `Suppress` cross-purpose projection | Copy useful evidence across purpose boundary | Policy owner; explicit consent/permitted-use receipt |
| Layer 4 — candidates | Only one generic play, semantic duplicates, or no materially different wait/stop option | `Abstain` or rebuild candidates; sole option needs elimination proof | Present deterministic ranking as comparative judgment | Reasoning owner; diverse candidate keys or documented safe sole option |
| Layer 4 — hard inputs | Exact unresolved object, stakes, constraints, completion, expertise coverage, or confidence basis is missing | `Review source`, `Defer`, or `Observation only` according to missing gate | Imperative with disclaimer, scalar confidence, or generic template | Reasoning/upstream owner; typed vector and all hard-gate receipts |
| Layer 4 — decision | Permission/risk fails, decision expires, or upstream object is superseded | `Blocked`, `No action`, or `Cancel`; force fresh reasoning | Score override or execute old winner | Decision owner; current package, expiry, approval and supersession proof |
| Layer 4 — output | LLM prose adds fact, recipient, option, score, urgency, or authority | Reject projection and retain deterministic decision receipt | Let fluency repair weak logic | Reasoning owner; exact grounding/diff test and no added authority |
| Layer 5 — card acceptance | “I'll do it” changes card/signal state but does not atomically create/claim execution | Mark `accepted_unclaimed` or `Blocked`; never “done” | Cancel source authority or learn success from a click | Executive owner; idempotent card-command-to-ExecutionObject weld |
| Layer 5 — execution target | Requester, target, relationship/thread, action, or cadence is absent | `Review source`; no execution/reminder | Use connector, sender, company node, or generic founder/admin | Executive/context owner; semantic target and cadence object replay |
| Layer 5 — approval/executor | Restricted action lacks approval or agent protocol is not governed | `Blocked`; agent handoff remains HTTP 501 | Infer availability from endpoint or confidence | Governance owner; scoped approval, single lease, signed payload, idempotent result |
| Layer 5 — completion/outcome | Click, send attempt, broad node event, or checked steps exist without scoped success/outcome | `waiting` or `completed_unproven` | Close parallel loop or claim customer/revenue value | Executive/outcome owner; post-creation scoped completion plus separate outcome receipt |
| Layer 5 — expiry/rebuild | At `b739bd5`, an expired card may be rebuilt from the same unresolved signal | `Cancel` old projection; rebuild only after current bounded situation revalidation | Treat rebuild capability as semantic freshness | Executive/reasoning owner; new situation hash plus open/supersession/completion checks |
| Layer 6 — materialization | Current ExecutionObject hash, semantic target, audience, visibility, or proven route is absent | Materialization failure, `Suppress`, or visible no-route result | Deliver person/node dump, widen to admin, or invent in-app/Slack availability | Delivery owner; target-scoped object and channel/client capability proof |
| Layer 6 — queue ownership | Legacy/v2 row shapes overlap, claim fence is absent, or enqueue exception is swallowed | `Quarantine` row / dead-letter with tenant reason; no adapter call | Let two workers send or `pass` on org failure | Delivery owner; one canonical sender, legacy backfill, lease/fence replay |
| Layer 6 — pre-send authority | Reply, completion, permission, assignee, or decision changes after enqueue | `Cancel`/`Suppress` immediately before adapter | Trust enqueue-time state | Executive + Delivery boundary; versioned authority token fenced at POST |
| Layer 6 — provider ambiguity | Provider may have accepted, but response timed out | Hold as `unknown`, retain attention slot, reconcile provider ID/manual evidence | Blind retry or cross-channel fallback | Delivery owner; one external message and definite reconciled result |
| Layer 6 — receipt/analytics | Client-level accepted/executed receipt lacks actor/action binding, or legacy status is invisible | Engagement-only/invalid receipt; exclude or label incomplete analytics | Treat click as Executive completion/ROI | Delivery/analytics owner; actor-device nonce, legal chronology and canonical lifecycle |
| Layer 7 — outcome input | Delivery, action, external outcome, role, or counterfactual is unreconciled | Retain observation; `Abstain` from efficacy update | Train acceptance, transport failure, silence, or `completed_unproven` as success/failure | Learning owner; canonical outcome identity and scoped external evidence |
| Layer 7 — support | Sparse, copied, correlated, cross-role, or one-deal-dominated evidence fails independence | `Park` proposal or bounded personal observation with capped confidence | Promote global/company truth or cross-domain cadence | Learning owner; source-family independence, comparable support and cohort scope |
| Layer 7 — Organization approval | Human review approves an Organization proposal, but no brain row/version and no compiler-consumption receipt exist | `approved_unpublished`; proposal remains non-authoritative | Report `promoted`, count active learning, select it into a snapshot, or let it influence a package | Governance owner; idempotent publication receipt, one active version, current-policy validation, L3 consumption and safe rollback |
| Layer 7 — policy reload | Stored policy may contain either block list, but the reconstructed `LearningPolicy` omits `blocked_targets` or `blocked_subject_prefixes`, has a different hash, or cannot prove lossless field equality | `policy_incomplete`; abort tenant run before unit execution | Continue with constructor defaults, empty lists, old in-memory policy or partial proposal processing | Policy owner; exact revision/hash equality and blocked-target/prefix replay before a new run resumes |
| Layer 7 — Adaptive lifecycle | Recommendation learning emits non-expiring Adaptive state and no ratified TTL/decay law can be represented | `adaptive_ttl_unresolved`; publish/select nothing | Store durable Adaptive authority, pretend it decays, or use a model to invent expiry | Learning/architecture owner; ratified Runtime-lease or Adaptive lifecycle plus clock, expiry, pivot, supersession and rollback replay |
| Layer 7 — activation | Sweep wrote a row but compiler consumption is absent, or every input seam is empty | Report `published_not_consumed` or degraded/insufficient-input | Call the adaptive system healthy/active | Learning/runtime owner; active registry plus compiler snapshot consumption receipt |
| Layer 7 — correction | Identity, ICP, policy, late outcome, or source erasure invalidates a learned version | Suspend, supersede and replay descendants | Mutate history or revive expired predecessor | Learning/privacy owner; lineage retraction and new version with surviving scope |

## Propagation and recovery laws

1. **Authority only narrows downstream.** Layer 2 cannot widen Layer 1 visibility; Layer 3 cannot repair an unknown business subject; Layer 4 cannot score away missing expertise; Layer 5 cannot invent an executor; Layer 6 cannot choose a broader audience; Layer 7 cannot turn ambiguous outcomes into truth.
2. **A failed hard gate dominates presentation.** Templates, explanations, cards, reminders and dashboards inherit `Abstain`, `Suppress`, `Blocked`, `Cancel`, and `No action`. Presentation may explain a state but cannot upgrade it.
3. **Recovery produces a new version.** Corrections append receipts, supersede derived objects and replay from the earliest invalid checkpoint. Historical decisions and deliveries remain auditable; they are not rewritten as if the old evidence never existed.
4. **Invalidation is transitive and fenced.** A source visibility/identity/version correction invalidates affected BSO, package, decision, execution, queued delivery and learning proposal. Reads must not combine versions while the cascade is incomplete.
5. **Retries are typed.** Transport retry is allowed only for definite non-delivery after authority revalidation. Semantic ambiguity needs source review. Policy suppression needs a policy change. Unsupported expertise needs authoring. More retries cannot solve the wrong class.
6. **Waiting has a trigger and owner.** `Defer` without `not_before`/event, owner, expiry and revalidation rule is a silent backlog. `Park` without a review/retry queue is a silent drop.
7. **Completion and value are separate.** Display is not delivery; click is not execution; send is not business completion; completion is not outcome; association is not causal value.
8. **Privacy survives observability.** Operators see counts, reason codes and opaque lineage needed for recovery, not content that policy already prohibited.

## Recovery orchestration

| Failure class | First recovery action | Replay boundary | Downstream treatment while recovering | Escalation condition |
|---|---|---|---|---|
| Transient source/adapter outage | Backoff with bounded attempts and cursor/idempotency key | Last committed source cursor or unsent fenced attempt | `Park`/`Defer`; no negative inference or duplicate send | Attempt/SLA ceiling reached → dead letter and owner alert |
| Semantic ambiguity | Ask one precise source/role/state question | Earliest ambiguous evidence-to-BSO join | `Review source`; suppress action authority | Review SLA expires or candidates remain conflicting |
| Policy/visibility conflict | Stop publication/delivery and invalidate affected derivatives | Original scoped evidence plus new policy version | `Suppress`; no alternate-recipient fallback | Policy owner must resolve; system never auto-widens |
| Unsupported expertise | Record capability/dependency gap and author against golden scenario | BSO into new accepted package version | `Abstain` / `Observation only` | Repeated material uncovered situation enters corpus backlog |
| Stale/superseded authority | Cancel queued/planned work and recompute current state | Latest source/graph/package snapshot | `Cancel`; no revival of prior card or execution | Version fan-out cannot reconcile atomically |
| Unknown provider result | Reconcile provider message/idempotency evidence | Existing started attempt, not a new logical delivery | `unknown`; reserve attention and avoid fallback | Reconciliation SLA → human review, never assumed failure |
| Unreconciled outcome | Hold efficacy neutral and collect scoped external result/counterfactual | Execution/outcome ledger join | `completed_unproven` / observation | Outcome window ends → unknown, not negative |
| Poisoned learned lineage | Suspend dependent entries and packages | Corrected evidence through governed publication/consumption | `Quarantine`; last independently safe version only if current policy permits | No valid predecessor → empty/disabled learned state |
| Approved Organization proposal lacks publication | Resume the governed publisher idempotently under current policy; never manufacture an active row from review state alone | Human-review object → immutable proposal → publisher → active version → L3 snapshot | `approved_unpublished`; no package influence | Age/SLO breach alerts governance owner; conflict or stale policy returns to review, not forced publish |
| Reloaded learning policy is incomplete | Abort the run, reconstruct every stored authority field and compare canonical revision/hash | Stored policy snapshot before any unit or proposal execution | `policy_incomplete`; no default/partial policy | Hash mismatch or block-list loss pages policy owner; malformed revision remains stopped |
| Adaptive lifecycle is unrepresentable | Ratify and implement either bounded Runtime semantics or Adaptive TTL/decay across type, publisher, reader and rollback | Original proposal plus pinned clock and policy | `adaptive_ttl_unresolved`; no brain row or snapshot influence | Any non-expiring/stale selected entry is a release-blocking authority incident |

## High-risk scenario expectations

| Scenario | Safe intelligence result | Failure that must be impossible | Recovery proof |
|---|---|---|---|
| Theresa requested periodic investor updates; several were sent; no reply | Role-scoped fundraising observation; act only when requested cadence, material update, last-sent history and reconsideration condition make a new update eligible | “Rejected,” “last chance,” or generic chase inferred from silence | Fundraising route plus cadence object and complete sent/reply window |
| Boardy introduces several people from one connector mailbox/thread | Connector is actor/evidence; each introduced counterparty has a separate bounded relationship/open loop | Boardy mega-card, x77 aggregate, or reply addressed to connector | Target-specific actor-role graph and split BSO replay |
| Past calendar invitation has no attendance evidence | Occurrence unknown; `Review source` or `Observation only` | “Send recap” or “confirm meeting” from a past scheduled event | Completed/cancelled/no-show/rescheduled fixture resolves distinctly |
| Support fact would help a Sales opportunity | Keep fact in permitted support scope; `Suppress` commercial projection | Commercial targeting because the information is useful | Explicit purpose/consent receipt before any new Sales version |
| User presses “I'll do it” | Create/claim exactly one execution or show accepted-unclaimed | Card appears complete; learning counts success | Atomic idempotent weld and later scoped completion receipt |
| Agent handoff is requested | `Blocked` and HTTP 501 until governed protocol exists | Endpoint presence presented as safe execution | Approval, single lease, revocation and idempotent result suite |
| Provider accepts send then times out | One `unknown` attempt awaiting reconciliation | Automatic duplicate/cross-channel interruption | Provider/idempotency evidence proves exactly one external message |
| Source correction arrives after card and delivery queue exist | Invalidate, cancel/suppress queued work, rebuild from corrected version | Old target/action still sends or teaches learning | Transitive invalidation trace across all affected object IDs |

## Unresolved ownership contradiction

The audited design materials do not yet provide one ratified answer for whether Executive owns final channel choice or Delivery owns channel routing/fallback. This matrix does not silently choose a side. Until an ADR defines the decision input, authority, override order, migration and replay behavior, a disagreement between the Layer 5 routing intent and Layer 6 route ladder is `Blocked:routing_owner_conflict`. No adapter call is permitted. The recovery proof is an approved architecture decision plus deterministic replay showing one logical delivery and one accountable owner.

## Acceptance gates

| Gate | Required evidence |
|---|---|
| Accounting | For every layer and tenant run, all inputs reconcile to explicit output/disposition counts; unexplained loss is zero |
| Abstention integrity | Unsupported domain, missing role/current state, failed permission and unreconciled outcome produce zero prescriptive actions |
| Scope safety | Zero visibility widening, connector-as-target, cross-role/deal leakage, or restricted cross-purpose projection in golden replays |
| Recovery | Source outage, correction, policy change, expiry and crash replay are idempotent, version-fenced and produce no duplicate authority |
| Lifecycle | Accepted, claimed, executing, delivered, completed, outcome-proven and learned remain distinct in API, UI and ledger |
| Delivery | Exactly one fenced sender; definite failure, unknown result, suppression and defer have distinct durable results |
| Learning | Zero positive/negative efficacy updates without reconciled action and external outcome; empty sweeps expose degraded reasons |
| Learning publication | Every approved Organization proposal is either durably `approved_unpublished` or has exactly one active-version and L3-consumption receipt; approval→publish and publish→consume latency are measured |
| Policy fidelity | Stored and loaded policy hashes/revisions/authority fields are equal, both block lists survive restart, policy-loss incidents are zero, and `policy_incomplete` aborts before unit execution |
| Adaptive lifecycle | Every Adaptive influence has a ratified expiry/decay/supersession law and pinned-clock replay; otherwise `adaptive_ttl_unresolved` produces zero publication and zero post-expiry selection |
| Customer surface | Non-authoritative states show the exact missing condition and safe next step; no action button appears when hard gates fail |
| Operations | Parked age, deferred age, suppressed counts, dead letters, unmaterialized events, unknown provider results, `approved_unpublished` age, policy-hash/list-loss incidents, Adaptive-without-TTL counts and published-not-consumed entries have owners and SLOs |

The release condition is not “the pipeline returned cards.” It is that actionable cards satisfy the gold contract, every non-action has a truthful typed reason, and every recoverable item has a tested path back into evaluation without widening authority or losing evidence.

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "04-Gold-Standard-Intelligence-Contract.md" (M5.C1.L-contract.V1.U01)
include "../01-Layer-1-Knowledge/04-Loopholes-Edge-Cases-and-Fail-Closed/README.md" (M2.C1.L-logic.V0.U01)
include "../02-Layer-2-Context-Intelligence/04-Loopholes-Edge-Cases-and-Fail-Closed/README.md" (M2.C2.L-logic.V0.U01)
include "../03-Layer-3-Domain-Expertise/04-Loopholes-Edge-Cases-and-Fail-Closed/README.md" (M3.C1.L-logic.V0.U01)
include "../04-Layer-4-Reasoning/04-Loopholes-Edge-Cases-and-Fail-Closed/README.md" (M3.C2.L-logic.V0.U01)
include "../05-Layer-5-Executive/04-Loopholes-Edge-Cases-and-Fail-Closed/README.md" (M4.C1.L-logic.V0.U01)
include "../06-Layer-6-Delivery-Atlas-5.2/04-Loopholes-Edge-Cases-and-Fail-Closed/README.md" (M4.C2.L-logic.V0.U01)
include "../07-Layer-7-Learning-Atlas-6/04-Loopholes-Edge-Cases-and-Fail-Closed/README.md" (M4.C3.L-logic.V0.U01)
-->
