# Gold-Standard Intelligence Contract

**Purpose:** define the minimum customer-visible object that deserves the name “GeniOS intelligence.” It is grounded in the seven-layer provenance matrix and the customer contract, not in the current card layout. A fact, activity reminder, generic imperative or confident summary does not qualify.

## The customer promise

Gold-standard intelligence reduces founder reconstruction and decision work while preserving auditability:

> Given current, permission-safe evidence and accepted expertise, identify the exact material situation and **what remains** unresolved; compare defensible moves including waiting/stopping; recommend the best move with stakes, ownership, approval and observable completion; deliver it safely; and learn only from reconciled outcomes.

When those requirements cannot be met, the product must return **Observation only** or a specific review/defer state. It must never fill missing truth with a generic Sales recommendation.

## Mandatory actionable-intelligence contract

| Contract field | Required answer | Source/owner | Hard failure if absent | Customer-visible form |
|---|---|---|---|---|
| Situation state | What material business state exists—not an action headline | L2 bounded situation | Activity or old message substituted for current state | “Investor reconsideration update is due only if a new material milestone exists” |
| **Business subject** | Correct person, company, opportunity, relationship or internal process | L1–L2 identity/role graph | Ambiguous subject, connector/target collapse, person-wide merge | Named subject plus role and relationship |
| Actor-role graph | Requester, connector, target, owner, approver, observer | L1–L2 provenance | Any role is guessed or inferred from transport sender alone | “Theresa: investor partner; Rohit: update owner” |
| Exact open loop | The request, commitment, decision, objection or expected result and its current state | L2 | System cannot state **what remains** after supersession/completion checks | Quoted/paraphrased bounded unresolved object |
| Why now / stakes | Deadline, cadence, state change, opportunity, cost of delay and expiry | L2 evidence + L4 judgment | Age/urgency score is the only reason | Business consequence and decision window |
| **Evidence** | Source/thread receipts, freshness, conflicts, transformations and missing inputs | L1–L4 trace | Synthetic/default receipt or hidden decisive conflict | Reopenable receipts and “missing” list |
| Expertise | Domain, reviewed/accepted capability versions, four-brain snapshot, coverage and exclusions | L3 | Unsupported/stub/draft capability, missing permission resolution, or accepted hash mismatch | Accepted capability, reviewer/hash receipt and coverage badge/details |
| Per-brain influence | Expert, Organization, Behavior and Adaptive entry selected/excluded/absent state; typed consumer; exact goal/constraint/policy/candidate/eligibility/rank field changed | L3–L4 | Snapshot/hash changes but judgment semantics do not | Expandable per-brain **semantic influence** receipt; hash alone is provenance, never authority |
| Primary decision | Specific recipient, action, content/asset, channel intent, timing/trigger and rationale | L4 | “Reply/follow up/send recap/reset” without specifics | One executable recommendation |
| **Alternative** set | Material fallback, wait/do-nothing/stop option, trigger and trade-off | L4 | Rephrased duplicate or forced action | Ranked alternatives and rejection reasons |
| Confidence vector | Evidence, identity, freshness, expertise coverage, decision confidence, urgency and priority separately | Owning layers | One scalar hides a hard missing field; score relabelled confidence | Vector with blocking minimum/hard gate |
| Ownership | Human/agent owner, authority, dependencies and approval boundary | L4–L5 | Wrong/unresolved target/owner or absent approval | “Agent may draft; Rohit must approve/send” |
| **Completion** | Observable real-world event that resolves the loop | L4–L5 | Click, claim or “I’ll do it” is treated as done | “Update delivered to Theresa” |
| Outcome | Business result, measurement window and counterfactual | L5–L7 | Transport receipt treated as business success | “Reply/reconsideration within 21 days; attribution pending” |
| End-to-end trace | Parent ids and source/graph/corpus/brain/manifest/config/policy versions | All layers | Legacy bypass or unpinned authority path | Expandable “why this” receipt |
| Validity | Created, expires, supersedes, authority mode and Learning publication validity | L2–L7 | Stale/shadow decision or invalid learned predecessor remains actionable | Current/expired/revoked state plus proposal/policy/reviewer/publisher/rollback receipt |

## Decision classes

| Class | Meaning | Action authority | UI requirement | Permitted next state |
|---|---|---|---|---|
| **Actionable** | All hard fields and accepted expertise support a ranked decision | Human/agent within explicit scope and approvals | Primary + Alternative + stop rule + Completion | Claim → approve → execute → externally complete |
| **Review source** | Decisive source/role/current-state evidence must be inspected | No business action | Open exact source and state the question to resolve | Rebuild from verified evidence |
| **Observation only** | Material pattern may exist, but context/expertise/stakes/completion is insufficient | None | State observation, uncertainty and next observation trigger; no action button | New evidence may re-evaluate |
| **Defer** | Decision could become safe after named evidence/approval/time condition | None until condition | Missing condition, owner and expiry | Fresh decision after condition |
| **Suppress** | Duplicate, completed, superseded, irrelevant or prohibited | None | Usually hidden; auditable suppression receipt | Reopen only on authoritative new state |
| **Blocked** | A hard policy, permission, safety or dependency constraint forbids action | None | Constraint and lawful recovery path | Re-reason only after constraint changes |
| **No action / stop** | Waiting or stopping is the best supported decision | Observation scheduling only | Explain why activity would harm or add no value | Revisit only at explicit trigger |

## Actionability gate

An item is **Actionable** only when every gate is true:

| Gate | Pass condition | Failure result |
|---|---|---|
| Source integrity | Real provider/thread/event receipt, transformation version and freshness | Review source / park |
| Visibility and purpose | Narrowest audience/permitted use survives every merge | Suppress / blocked |
| Subject and roles | Business subject, target, requester/connector and owner are unambiguous | Review source |
| Current state | Open loop is active, not completed, superseded, expired or duplicated | Suppress / no action |
| Expertise coverage | Accepted domain/capability closure and four-brain policy resolution | Observation only / defer |
| Per-brain semantic use | Every decision-relevant selected brain entry has an allowed typed consumer and an observable intended field change; selected-but-unused is explicit | Observation only / defer |
| Candidate quality | Specific primary plus materially distinct fallback or justified sole safe action | Defer |
| Hard constraints | Permission, approval, feasibility and risk checks pass | Blocked |
| Stakes and timing | Business consequence, cost of delay and expiry are evidence-linked | Observation only |
| Ownership | Accountable human/agent and approval/dependency path exist | Defer |
| Completion and outcome | Observable completion plus result window are declared | Observation only |
| Authority and freshness | Current authoritative versions; not shadow/revoked | Suppress / rebuild |
| Layer 7 validity | Every learned entry has permitted lineage, current policy, lawful publication/supersession/rollback and required lifecycle bounds | Blocked / `adaptive_ttl_unresolved` |

No percentage can compensate for a failed gate. An LLM may explain a passed object or suggest questions in a bounded ambiguity flow; it cannot mark a gate passed.

## Four-brain semantic influence and Layer 7 validity

A gold object must prove more than “all four brains were included”:

| Brain | Required semantic contribution | Validity requirement | Fail-closed result |
|---|---|---|---|
| Expert | Accepted domain concepts, constraints, failure patterns and candidate plays change the applicable decision space | Exact reviewed/accepted version and content hash; no stub or draft/unreviewed dependency | Observation only / unsupported expertise |
| Organization | Current company policy, approval, ICP or operating constraint changes an allowed typed goal/constraint/policy/candidate field | Current published version, policy permitted use, reviewer/publisher where required, no invalid rollback predecessor | Blocked until policy authority is resolved |
| Behavior | Sufficiently supported in-scope pattern may tune preference, never permission | Population/support/freshness/use-class gates and explicit applied/unused receipt | Honest sparse/absent state; no fake personalization |
| Adaptive | Valid recent efficacy/preference may tune an allowed short-horizon field, never permission | A ratified expiry/decay and pivot invalidation rule tied to the exact published entry | `adaptive_ttl_unresolved`; exclude the entry and block any action whose claim depends on it |

At the pinned code, `LearningObject.expires_at` is legal only for `LearningTarget.RUNTIME` (`contracts/learning.py:200,223-227`), while recommendation learning can emit `LearningTarget.ADAPTIVE` without expiry (`feedback/units.py:187-218`). **Adaptive cannot carry expiry** under the current contract. Therefore a short-horizon Adaptive proposal must not be treated as valid merely because it was stored, selected or included in `brain_snapshot_id`. Until the type, publisher, reader and expiry/decay tests are ratified together, publication/consumption must fail closed with `adaptive_ttl_unresolved`.

Likewise, `reason/adapters/expertise.py:180-188` currently places Organization, Behavior and Adaptive values into `knowledge_hash`, but does not map them into the generic DAG, goal, constraints, candidate eligibility or ranking. Gold requires a paired mutation replay: change exactly one brain entry, pin every other input, and prove the intended decision field changes. A new hash/version with identical judgment is **hash-only influence**, not semantic influence and not evidence that the Company, Behavior or Adaptive brain “worked.”

Layer 7 validity continues after publication. The trace must prove source permitted use, complete loaded policy including `blocked_targets` and `blocked_subject_prefixes`, review-to-publish where required, supersession, rollback eligibility under current policy/visibility/use, later L3 selection, and the intended downstream decision delta. An expired, prohibited or policy-invalid predecessor cannot be revived merely because rollback finds it.

## Required recommendation shape

```text
Situation: <current business state>
Business subject: <entity + role + scoped relationship>
What remains: <exact unresolved object>
Why now: <stakes + trigger + expiry>

Recommended: <who does exactly what, for whom, when, through which governed path>
Why this wins: <evidence + expertise + trade-off>
Alternative: <fallback + activation trigger>
Wait/stop: <when no action is superior and consequence>

Owner/approval: <human or agent scope>
Completion: <externally observable resolution>
Outcome window: <metric + counterfactual + attribution status>
Confidence: <vector, missing/conflicts, not one opaque scalar>
Evidence: <receipts and versions>
```

## HKS acceptance examples

| Scenario | Gold-standard result | Observation only / fail-closed trigger | Prohibited output |
|---|---|---|---|
| Theresa asked for updates and may reconsider; new material milestone exists | Recommend one milestone-specific update tied to her original request; compare wait and permission-safe connector nudge; name Rohit/agent approval; completion is delivery; outcome is reply/reconsideration window | Fundraising expertise, exact request, sent-update history or milestone evidence missing | “You were rejected; one last chance” or age-only “reply now” |
| Theresa has no new material milestone after several updates | No action until a material update or explicit cadence trigger; record observation trigger | Conflicting sent-history/current state requires source review | Repetitive follow-up merely because silence is old |
| Boardy introduced multiple contacts | Separate situation/decision per introduced contact; Boardy remains connector; connector escalation is only a distinct candidate if appropriate | Introduced target/thread cannot be resolved | One giant Boardy card or reply-to-connector action |
| Calendar event exists but attendance is unverified | Observation only or source review; no recap | Occurrence, attendees or external counterpart absent | High-confidence “Send recap” from invitation text |
| External meeting produced a promised deck | Deliver exact deck to named counterpart by agreed time, with clarify/renegotiate fallback and acceptance receipt | Promise/owner/due date inconsistent | Generic “send recap” |
| User’s own availability proposal was superseded | Suppress/no action | Current schedule remains conflicted | Convert old quote into overdue deliverable |
| Restricted support message signals possible expansion | Resolve support under original purpose; commercial action blocked absent permission | Purpose/visibility unresolved | Sales targeting from private support evidence |
| Vendor changes bank details | Defer until out-of-band verification and dual approval; direct update candidate eliminated | Verified identity/approval absent | Execute based on email familiarity |
| Organization pivot with sparse Behavior and short-horizon Adaptive | Rebuild under the new Organization version; label Behavior sparse; exclude Adaptive and return `adaptive_ttl_unresolved` wherever the recommendation depends on it | No ratified Adaptive expiry/decay or later semantic-consumption proof | Pretend old Adaptive state expired, publish a non-expiring “recent” preference, or call hash-only inclusion personalization |

## Agent handoff contract

“Better agents” means the agent receives the same constraints as the human, not just an action string. A handoff must include exact subject/target, selected action and rejected alternatives, permitted tools/data, visibility, approval token, idempotency key, expiry, success/Completion predicate, stop conditions and result schema. The agent may draft, schedule or execute only within that scope. HTTP 501 is safer than pretending an ungoverned handoff succeeded.

## Completion, outcome and value separation

| Event | Meaning | Must not be called |
|---|---|---|
| Card displayed | Recommendation exposure | Action or value |
| “I’ll do it” | Intent/claim | Execution or Completion |
| Message sent | Action executed and transport attempted | Counterparty outcome |
| Provider delivered/opened | Delivery/engagement receipt | Business success |
| Counterparty replied / meeting booked / asset accepted | Possible declared completion/outcome evidence | Revenue attribution automatically |
| Opportunity advanced inside window | Business result candidate | GeniOS-caused value without counterfactual |
| Reconciled result + counterfactual | Attribution evidence | Universal market proof |

## Acceptance and economic proof

The contract is proven only by golden/mutation replays and customer outcomes: zero wrong-target/connector actions; zero prescriptions on uncovered expertise; zero completed/superseded loops resurfaced; all actionable cards have stakes, alternatives, ownership and completion; founder correction burden declines; accepted recommendations are reconciled to actual actions; and outcome/counterfactual evidence supports the pre-registered 2–4 week design-partner and 60–90 day economic window. Internal scores, card count and clicks are not proof.

## Final rule

If GeniOS cannot name the Business subject, exact open loop, why now, Evidence, accepted expertise, per-brain semantic influence, Layer 7 validity, ranked action and Alternative, owner/approval, Completion and outcome window, it does not yet have actionable intelligence. It has an observation. Label it honestly as **Observation only**, show the precise missing input or review path, and do not display an action button.

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "02-Typed-Contract-and-Provenance-Matrix.md" (M5.C1.L-contract.V0.U01)
include "../00-Methodology/04-Customer-Intelligence-Contract.md" (M1.C2.L-contract.V0.U01)
-->
