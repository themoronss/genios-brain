# Golden Replay 09 — Client Isolation, Dual ACL, and Never-Commercial Evidence

## Evidence status and scenario boundary

This is a **[MODELLED]** AI-agency pressure test derived from the uploaded five-application reference. It is not a reported production incident, customer testimony, or proof of demand. **[CODE]** refers to inspection at `harsh/mvp@b739bd5`; **[ATLAS]** refers to intended architecture. The assertions below become **[TEST]** evidence only after an executable replay passes. The Outcome section is the expected result, not an observed business outcome.

## Business subject and base fixture

The **Business subject** is one client's exact relationship/request inside an agency tenant—not the agency-wide person node, shared email address, model prompt, or another client's account.

The base fixture contains one agency organization with two client contexts:

- `client_alpha`: a private Support ticket from `alex@example.com`, restricted to Alpha's assigned operators, carrying `use_class=never_commercial` and an exclusion for the evidence subject;
- `client_beta`: a legitimate Sales opportunity involving a different relationship that also contains an `Alex` identity and similar company language;
- one agency operator assigned to both clients, plus another operator assigned only to Beta;
- an Admin request for Alpha, although the audited Admin corpus has 57 authored files, all 57 remain stubs: **zero non-stub**, zero reviewed or accepted, and zero executable routes;
- one approved draft/execution for Beta with model and agent usage that must be charged to Beta's execution and margin;
- a later Alpha erasure request that must retract only Alpha-derived facts, prompts, vectors, decisions, learning support and cost-linked content—not Beta's independent records.

The authoritative isolation key is at least `(org_id, client_context_id, identity_or_relationship_key)`. Source ACL and purpose restrictions then narrow the client ACL; organization membership alone never widens access.

## Current failure

**[CODE]** has tenant graph, visibility/use contracts and native execution lineage, but the audit does not prove mandatory `client_context_id` propagation through every source, identity key, cache, graph edge, BSO, brain snapshot, decision, execution, delivery receipt, learning cohort and cost line. Layer 2 currently hardcodes organization visibility in BSO/slice paths. Admin expertise has zero non-stub capabilities and zero reviewed or accepted capabilities, so it is not prescriptive expertise. Governed external-agent handoff is unavailable. Sensitive aggregation, client-scoped erasure and provider-cost attribution are incomplete.

Therefore a structurally valid path could deduplicate two clients' identities/content, expose Alpha support evidence to Beta Sales, reuse a private prompt/cache response, choose the wrong credential/recipient, allocate retries to the wrong margin, or train an agency-global commercial rule. A UI redaction would be too late: the prohibited evidence must be excluded before correlation, reasoning, delivery and learning.

## Expected behavior

The base fixture fails closed at every missing boundary. Alpha's ticket remains usable only for its permitted Support/safety purpose and declared operators. It contributes zero evidence to Beta, Sales, commercial rationale, embeddings, drafting, behavior/adaptive learning or agency-wide aggregation. The Admin request is **Observation only** or `unsupported`, with no generic Sales/Admin action. Beta's Sales path can proceed only from Beta-owned evidence and accepted expertise.

Every visible or executable object carries `org_id`, `client_context_id`, business subject, relationship/thread, visibility principals, unioned exclusions, use class, policy/version and lineage. Delivery uses Beta's recipient, credential and idempotency namespace. Each physical model/agent attempt is attributed once to Beta's execution, including retries, and reconciles to provider invoice and client-margin reporting. Alpha erasure invalidates and rebuilds Alpha descendants while preserving allowed aggregate only if the declared independent-population and sensitivity floor still passes.

## Prohibited behavior

- Do not merge identities, evidence, context, embeddings, caches or open loops across clients because the agency or operator is shared.
- Do not widen `operator_only` evidence to all agency members, a default admin, another client's owner, or the evidence subject.
- Do not use `never_commercial` Support evidence in Sales candidates, copy, rationale, ranking, delivery or learning.
- Do not let an LLM summary, vector similarity, common email/domain, or same filename bypass client scope.
- Do not use generic expertise when Admin or another required capability is Stub/uncovered.
- Do not choose a different client's OAuth credential, channel, recipient or fallback when the scoped route is unavailable.
- Do not count a retry twice, leave compute unallocated, or claim client margin from estimates that do not reconcile to execution/provider receipts.
- Do not erase another client's independent evidence or retain Alpha-derived active influence after Alpha erasure.

## Exact Layer 1–Layer 7 contract

| Layer | Required input and responsibility | Required receipt/output | Fail-closed result |
|---|---|---|---|
| **Layer 1 — Knowledge** | Stamp provider object, raw/prepared content, vector/cache candidate and qualified signal with tenant, client context, source ACL, purpose/use, exclusions, version, retention and source readiness | Immutable receipt containing `(org_id, client_context_id, source_id, object_id, version)`, narrowest principals, union exclusions, `never_commercial`, transformation and cursor health | Park missing-client-context input; suppress unauthorized publication; never use org-wide default |
| **Layer 2 — Context Intelligence** | Resolve identity, dedup, correction and erasure inside `(org, client, relationship/thread)`; intersect source and client ACL; keep Alpha Support and Beta Sales projections separate | Client-scoped BSO with exact Business subject, actors, membership, current state, visibility/use, missing/conflict codes and graph version | `suppressed_policy`, `split_required` or Review source; no cross-client join or synthetic authority |
| **Layer 3 — Domain Expertise** | Compile only the client's permitted Organization/Expert/Behavior/Adaptive snapshot and accepted capability closure | ExpertisePackage with client config/brain/corpus hashes, coverage, exclusions and authoritative mode | Observation only for Stub/uncovered Admin; no generic fallback and no Alpha evidence in Beta package |
| **Layer 4 — Reasoning** | Generate candidates only within client objective, budget, permitted evidence and exact open loop; keep confidence, priority and coverage separate | Decision with client ID, stakes, primary/Alternative/wait, owner/approval, completion, outcome window and exclusion trace | Block if client ownership, use permission, expertise or cost owner is absent |
| **Layer 5 — Executive** | Create one client-scoped ExecutionObject; bind actor, approval, dependencies, agent lease/idempotency and every usage/cost event | Execution/action IDs carrying client context, provider attempt lineage, cost center and observable completion | Block unavailable agent/Admin path; no default operator, client or cost allocation |
| **Layer 6 — Delivery** | Revalidate client audience, subject exclusions, current permission, scoped credential, route, content and authority immediately before adapter call | Canonical DeliveryResult with client/execution/action, credential/config version, recipient, provider/idempotency ID and definite/unknown result | Suppress/no-route; never fall back across client, credential, operator or evidence boundary |
| **Layer 7 — Learning** | Join only client-scoped exposure/action/delivery/outcome; enforce permitted use, source-family independence, sensitivity-aware population floor, retention and erasure | Client-bounded proposal/brain version or policy rejection; compiler consumption and retraction receipt; costs stay separate from outcome value | No promotion from `never_commercial`, sparse/cross-client data or missing lineage; erasure quarantines affected descendants |

## Dual-ACL decision rule

| Boundary | Effective permission | Required assertion |
|---|---|---|
| Source → client | `source_principals ∩ client_principals`; exclusions are unioned | A source cannot become broader after client attachment |
| Client → organization operator | Intersection with active role, assignment, purpose and region/time policy | Agency membership alone grants no client access |
| Evidence subject | Subject exclusion applies even when subject has another product login | Protected application/support detail is not rendered back to its subject |
| Purpose | Allowed purposes intersect; `never_commercial` is terminal for commercial paths | Commercial projection receives zero protected rows and zero derived features |
| Derived object | Carries all parent policy versions and is invalidated when any parent narrows/revokes | Cache/vector/BSO/package/decision cannot outlive parent authority |
| Aggregation | Requires declared population, independent client/subject/source families and sensitivity-specific floor | Formal count alone cannot make rare sensitive evidence safe |

## Mutation matrix

| Mutation | Expected behavior | Prohibited behavior | Outcome / pass evidence |
|---|---|---|---|
| Same email appears in Alpha and Beta | Two client-scoped identity/relationship records; reviewed link may acknowledge same human without sharing facts | Agency-global person node supplies both contexts | Two BSOs with disjoint memberships and policy traces |
| Same PDF is uploaded by both clients | Content fingerprint may detect duplicate bytes, but each source receipt, ACL and permitted use stays separate | Reuse Alpha-extracted private facts in Beta | Cache/vector entries remain tenant+client+policy keyed |
| Alpha operator is also Beta operator | Access is evaluated per current assignment and purpose | Operator role becomes bridge between graphs | Audit shows two distinct access decisions |
| `client_context_id` removed from one event | Park and alert exact missing key | Default to agency org or “most likely” client | Zero graph/BSO/package descendants |
| Alpha private Support fact predicts churn | Use only for permitted Support/safety handling; commercial projection suppressed | Sales expansion/retention campaign or commercial learning | Zero protected evidence IDs/features in Sales trace |
| Alpha Admin bank-change request arrives | Unsupported/Blocked pending accepted Admin/security expertise and approvals | Generic operational instruction | No ExecutionObject or delivery |
| Beta route credential missing | Visible no-route/Blocked; preserve execution | Borrow Alpha credential or default Slack | Zero adapter calls and scoped recovery receipt |
| Provider accepts Beta send then timeout | One ambiguous attempt charged once to Beta; reconcile before retry | Duplicate send or duplicate cost/margin charge | One provider/idempotency identity and canonical cost line |
| Agent callback omits client context | Quarantine/reject result; execution remains unresolved | Attach by actor/name or latest execution | No completion/learning influence |
| Alpha requests erasure | Remove/retract Alpha subject rows and descendants; recompute aggregates | Delete Beta independent evidence or leave Alpha brain influence active | Retraction blast-radius receipt and zero active Alpha descendants |
| Aggregate falls below sensitivity floor after erasure | Disable/supersede learned aggregate | Retain because it was previously approved | New active registry excludes version; history remains restricted |
| Model cache contains identical prompt text | Miss across client/policy boundary | Shared response/cache hit | Cache key proves tenant+client+visibility+model/prompt/schema versions |

## Replay assertions

1. Every object from source through learning either carries the exact client context or fails closed before authority.
2. Alpha protected source IDs, raw text, embeddings and derived features appear zero times in Beta's BSO, package, prompt, decision, delivery and learning trace.
3. Removing `never_commercial` only from a downstream copy does not enable Sales; parent policy lineage still blocks it.
4. Admin's zero non-stub coverage always produces Observation only/Blocked, regardless of model fluency or operator confidence.
5. The same provider attempt and retry sequence yields one reconciled client cost ledger; no unallocated or cross-client usage survives.
6. Erasure is versioned and transitive: all affected descendants lose authority, while unrelated client state remains byte-identical.
7. A model-disabled replay produces identical isolation, routing, execution, delivery and learning dispositions.

## Outcome

The replay passes when authorized Alpha operators can resolve the private Support case under its original purpose, Beta receives only Beta-grounded Sales intelligence, the uncovered Admin case remains non-actionable, and every execution/delivery/model/agent Cost reconciles to exactly one client. Alpha erasure removes only Alpha-derived active influence and safely recomputes aggregates. Success is **zero cross-client leakage, zero `never_commercial` escape, zero wrong credential/recipient, zero unallocated or double-counted compute, and zero false expertise authority**. This deterministic replay would establish [TEST] safety for the modelled fixture; real Live and Outcome-proven claims still require tenant traces and customer evidence.

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "../08-Cross-Layer-Synthesis/04-Gold-Standard-Intelligence-Contract.md" (M5.C1.L-contract.V1.U01)
include "../08-Cross-Layer-Synthesis/08-HKS-and-Scenario-Responsibility-Matrix.md" (M5.C1.L-integration.V1.U01)
include "../01-Layer-1-Knowledge/06-Improvements-Acceptance-and-Metrics/README.md" (M2.C1.L-interface.V0.U01)
-->
