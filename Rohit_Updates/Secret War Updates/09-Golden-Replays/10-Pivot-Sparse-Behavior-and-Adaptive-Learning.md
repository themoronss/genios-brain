# Golden Replay 10 — Pivot Reset, Sparse Behavior, and Adaptive Expiry

## Evidence status and scenario boundary

This is a **[MODELLED]** AI-GTM-founder pressure test derived from the uploaded application reference. It is not a claim about a real tenant, a production failure, or validated customer demand. **[CODE]** refers to inspection at `harsh/mvp@b739bd5`; **[ATLAS]** is the intended four-brain and seven-layer contract. The replay becomes **[TEST]** evidence only when implemented and executed. The Outcome below is expected, not observed.

## Business subject and base fixture

The **Business subject** is the organization's versioned go-to-market state and each exact relationship/opportunity whose meaning changes at the pivot—not the founder node or an undifferentiated “company preference.”

At `t0`, Organization Brain version `org-v7` says the company targets early-stage startups. Behavior Brain contains two old observations from one founder and one customer role; it has insufficient independent support for company-wide personalization. **[ATLAS][MODELLED]** Adaptive Brain would have one short-horizon “follow up after three days” entry with a mandatory TTL ending at `t1`. That expiring Adaptive fixture is an intended post-repair state, not an object the current contract can represent. Several open decisions/executions were compiled from `org-v7`.

At `t1`, an authoritative founder declaration changes the ICP to regulated enterprises, changes qualification constraints and supersedes the prior startup strategy. One open startup opportunity may remain intentionally active, while new enterprise situations should use the new strategy. This tests temporal and relationship scope: a pivot is neither “delete all history” nor “keep every old policy alive.”

## Current failure

**[CODE]** contains deterministic brain resolution, versions/hashes, bounded reset machinery and governed learning primitives. But the audited reset is partial: Organization configuration is not proved to be fully superseded, and there is no end-to-end proof that a reset invalidates every dependent Layer 3 package or that a published learned version is consumed by the next compile.

**[CODE] Adaptive cannot carry expiry.** `LearningObject` exposes `expires_at`, but its validation allows `expires_at` only for Runtime and raises when a caller explicitly supplies expiry for any other target. The shared `_cohort_candidate(...)` used by direct Behavior and Adaptive evolution returns `[]`, so direct Adaptive evolution emits no candidate. Separately, `unit_recommendation_learning(...)` can create a `LearningTarget.ADAPTIVE` object while omitting expiry; because the non-Runtime validation is then not triggered, the publisher may persist that object as a durable Adaptive learned-brain entry. Therefore the TTL/decay required by **[ATLAS]** and exercised by this **[MODELLED]** replay is not representable in current code; file presence, an Adaptive target label, a stored proposal, or a published entry cannot prove expiring adaptation.

Consequently, an apparently valid brain snapshot may still carry `org-v7` or overconfident Behavior inferred from one person. More critically, a recommendation-derived Adaptive object may be durable despite representing short-horizon advice because current code cannot encode its expiry. There is **no automatic short-horizon/TTL guard** that infers the intended horizon and blocks an Adaptive proposal or publication when `expires_at` was omitted. Existing cards/executions may survive the pivot, while a UI says the system is adaptive. Conversely, a blunt reset could delete useful history and remove a still-valid relationship exception. A model-generated explanation cannot establish which version is authoritative or manufacture a missing lifecycle contract.

## Expected behavior

**[ATLAS][MODELLED] Required behavior:** the pivot creates `org-v8` with effective time, scope, author/approval, policy version and a supersession edge to `org-v7`. History remains immutable. Every open BSO/package/decision/execution/delivery materialization whose authority depends on the changed fields is invalidated and replayed behind one version fence.

**[ATLAS][MODELLED] Required behavior before lifecycle repair:** every proposed short-horizon Adaptive object fails closed as `adaptive_ttl_unresolved`; it is not promoted, selected, compiled, or described as active. **[CODE] does not currently enforce that disposition:** when recommendation learning omits `expires_at`, the Adaptive object can proceed toward durable publication. The governed repair must choose one explicit contract: (a) allow mandatory Adaptive expiry/decay and enforce it through proposal, publish, selection, compiler consumption, supersession and rollback, or (b) prohibit Adaptive publication and represent genuinely temporary instructions as Runtime leases without relabelling them as learned Adaptive policy. Under the post-repair **[ATLAS][MODELLED]** branch, Adaptive entries affected by the pivot are expired/superseded and the `t1` TTL independently prevents later influence. Sparse Behavior remains visible as low-support observation, partitioned by actor role/domain/situation. Its confidence may decay or fall through to Organization/Expert preference, but it is not erased and cannot grant permission. An explicitly grandfathered startup opportunity may retain only the narrowly approved exception.

Customer surfaces show the four-brain coverage honestly: new Organization version present; Expert coverage as actually authored; Behavior sparse/unproven; Adaptive absent/expired. Decisions using uncovered expertise or insufficient context are **Observation only** or Defer. A new compiler fingerprint and consumption receipt prove that `org-v8`, not prose about the pivot, changed only the intended packages.

## Prohibited behavior

- Do not keep `org-v7` authoritative because its snapshot hash is valid or its confidence is high.
- Do not delete old Organization, Behavior or Adaptive history in place.
- Do not convert one founder/customer event into company-wide Behavior or a permanent preference.
- Do not let expired Adaptive state influence compilation, ranking, cadence or delivery.
- Do not claim current-code Adaptive TTL/decay support: `expires_at` is Runtime-only, direct Adaptive evolution is empty, and recommendation learning creates Adaptive without expiry.
- Do not publish a short-horizon Adaptive proposal without a representable, enforced lifecycle or silently call a Runtime lease “Adaptive learning.”
- Do not carry old-ICP cards, queued sends or agent executions forward without revalidation.
- Do not invalidate a deliberately grandfathered opportunity unless the pivot scope actually covers it.
- Do not call a stored learning row “active” without Layer 3 consumption and intended decision-change proof.
- Do not use an LLM to select the brain target, confidence, TTL, permission, scope, promotion or rollback.

## Exact Layer 1–Layer 7 contract

| Layer | Required input and responsibility | Required receipt/output | Fail-closed result |
|---|---|---|---|
| **Layer 1 — Knowledge** | Capture `t0` strategy, `t1` pivot declaration, author/authority, effective time, scope, source version and any exception evidence without overwriting history | Immutable declaration receipts with visibility/use, exact text/span, occurred-at, version/tombstone and source readiness | Park if authority/time/scope is ambiguous; do not emit inferred global policy |
| **Layer 2 — Context Intelligence** | Version Organization facts, establish temporal boundary, mark affected relationships/open situations and preserve explicit grandfathered exceptions | Graph generation with `org-v7 → superseded_by → org-v8`, affected-object set, current BSO versions and missing/conflict codes | Quarantine mixed graph versions; Review source when pivot scope or exception is unclear |
| **Layer 3 — Domain Expertise** | Resolve current valid Organization/Expert permissions and Adaptive→Organization→Behavior→Expert preferences only among valid scoped entries | New four-brain snapshot and ExpertisePackage fingerprint; honest sparse/expired coverage; exclusion of `org-v7` and expired Adaptive influence | Observation only/unsupported where expertise is absent; never fake personalization or use legacy fallback |
| **Layer 4 — Reasoning** | Rebuild affected decisions under the new package; compare proceed, wait, stop and grandfathered exception; state stakes and expiry | New decision version with old decision superseded, candidates/eliminations, confidence vector, completion and outcome window | Defer/No action when sparse evidence cannot justify personalization; no old winner reuse |
| **Layer 5 — Executive** | Revalidate every open execution against new decision/brain authority; cancel, replan or reapprove affected actions | Versioned cancellation/replan/approval receipt preserving old execution history and exact dependency/owner state | Cancel/Blocked while replay incomplete; no execution under stale snapshot |
| **Layer 6 — Delivery** | Fence queued materializations at send time using current decision, package, Organization and Adaptive versions | Suppression/cancellation of stale cards/sends; only current-version DeliveryResult may proceed | Suppress old-ICP payload; never rebuild expired card from unchanged stale semantics |
| **Layer 7 — Learning** | Govern Organization reset and sparse Behavior confidence; **[CODE]** direct Adaptive emits `[]`, recommendation learning can propose Adaptive without expiry, the publisher may persist it durably, and `LearningObject` permits expiry only for Runtime; **[ATLAS][MODELLED]** requires Adaptive TTL/decay/supersession | **[ATLAS][MODELLED]** reset blast-radius receipt, bounded Behavior observation, explicit Adaptive lifecycle-contract version, governed rejection or representable expiry, active version, L3 fingerprint and intended decision-change replay | **[ATLAS][MODELLED]** no promotion from sparse/mixed-role evidence; short-horizon Adaptive returns `adaptive_ttl_unresolved` until the contract is repaired. **[CODE]** has no automatic TTL guard and can publish durable Adaptive when expiry is omitted; that is a replay failure, not a fail-closed pass |

## Brain-specific authority assertions

| Brain | Base state after `t1` | Authority rule | Required evidence |
|---|---|---|---|
| Organization Brain | `org-v8` active; `org-v7` historical/superseded | May govern company permission/context only within declared product/region/time scope | Founder authority, source, effective time, policy and supersession receipt |
| Expert Brain | Unchanged unless separately reviewed/released | Accepted corpus governs professional permission/default; pivot cannot author missing expertise | Capability closure, corpus hash, coverage and named approval |
| Behavior Brain | Sparse, role-scoped, low-confidence observation | Cannot become company truth or grant permission; fall through when support gate fails | Independent observations, days/entities, role/domain/situation and calibration |
| Adaptive Brain | **[CODE]** no direct candidate; a recommendation-derived candidate may omit expiry and be published durably even though Adaptive cannot carry expiry. **[MODELLED]** pivot-affected entry becomes superseded and TTL-expired entry inactive only after lifecycle repair | **[ATLAS][MODELLED]** fail closed as `adaptive_ttl_unresolved` before publication unless mandatory TTL/decay is representable and enforceable; a Runtime lease may hold a temporary directive but is not proof of Adaptive learning. **[CODE]** does not yet provide this guard | Contract/version decision, exposure/action/outcome evidence, representable TTL/decay, conflict, expiry/supersession and active consumption receipt |

## Mutation matrix

| Mutation | Expected behavior | Prohibited behavior | Outcome / pass evidence |
|---|---|---|---|
| Behavior Brain has zero observations | Expose absent coverage and use bounded Organization/Expert defaults | “Personalized for how you work” | Package coverage says absent; decision authority unchanged |
| One founder preference exists | Retain personal/role observation below promotion threshold | Company-wide Behavior rule | No active company Behavior version |
| Ten independent role-consistent observations pass policy | Produce reviewable scoped Behavior candidate; no automatic activation | Global all-domain rule | Proposal lists population/support and awaits governance |
| Adaptive entry is requested with TTL at `t1` without pivot | **[CODE]** rejects only an explicitly supplied `expires_at` on the non-Runtime Adaptive target; recommendation learning may instead omit expiry and publish durable Adaptive. **[ATLAS][MODELLED]** required pre-repair disposition is `adaptive_ttl_unresolved` with zero publish/compile; after lifecycle repair, expire exactly at TTL and remove future influence | Persist non-expiring Adaptive, silently discard TTL, or present a Runtime lease as active Adaptive learning | **[CODE]** current failure: explicit expiry is rejected while omitted expiry can survive durably. **[MODELLED]** pass: zero pre-repair publish/compile, then post-repair compiler after `t1` excludes the entry while audit retains it |
| Pivot affects only one product/region | Supersede within matching scope; preserve unrelated valid Organization state | Global reset | Package diffs change only matching situations |
| One startup opportunity is explicitly grandfathered | Preserve narrow exception with approval and expiry | Treat exception as old ICP remaining globally valid | Exception appears only in that opportunity's package |
| Queue contains old-ICP outreach | Cancel/suppress before adapter call; rebuild from current state if still open | Send because it was approved earlier | Zero adapter calls from stale version |
| Card expires after pivot | Revalidate BSO/package and create a new semantic decision only if justified | Same stale recommendation regenerated | New object hash/version or no card |
| Pivot and weekly learning sweep race | One version-fenced ordering; other run retries/rebases | Mixed brain snapshot or double publish | Exactly one active Organization version and one consumption receipt |
| Founder rolls back pivot | Validate predecessor against current policy/evidence; publish a new superseding version | Mutate `org-v8` away or revive expired Adaptive entry | `org-v9` records rollback decision; old TTL remains expired |
| Identity correction removes one Behavior observation | Retract descendants and recalibrate support | Keep poisoned confidence | Active proposal suspended until replay completes |
| New enterprise evidence is sparse | Observation only/Defer with exact missing support/expertise | Confident enterprise play from pivot declaration alone | No prescriptive action button |
| Temporary “pause outreach seven days” instruction | Create Runtime/temporary directive with TTL and scoped consumer receipt | Permanent Behavior/Organization rule | Zero influence after expiry |

## Replay assertions

Except for assertions explicitly labelled **[CODE]**, the assertions below are **[ATLAS][MODELLED]** acceptance requirements. They do not describe behavior already guaranteed by the pinned runtime.

1. No post-`t1` authoritative package, decision, execution or delivery references `org-v7` unless an explicit scoped exception authorizes it.
2. Removing the pivot authority/effective-time proof changes the result to Review source; it never guesses global scope.
3. Expired Adaptive and under-supported Behavior entries contribute zero permission and zero hidden confidence uplift.
4. The reset receipt enumerates every invalidated, preserved and rebuilt descendant; no mixed-version authoritative read occurs.
5. The active brain version has a Layer 3 consumption fingerprint, and only intended scenario packages/decisions change.
6. Rollback creates a new governed version and never revives an entry invalid under current policy or TTL.
7. With the LLM disabled, versions, coverage, invalidation, decisions, execution cancellation, delivery suppression and learning disposition are identical.
8. **[CODE]** At `b739bd5`, direct Adaptive produces no object; recommendation learning may produce an Adaptive object without expiry and the publisher may persist it durably. Only an explicit non-Runtime `expires_at` is rejected. There is no automatic short-horizon/TTL publication guard, so the pinned code does not satisfy the **[ATLAS][MODELLED]** `adaptive_ttl_unresolved` requirement.

## Outcome

**[CODE] The current code does not pass this replay.** It does not prove the complete `org-v8` invalidation/consumption chain, and it does not fail closed for an Adaptive object whose short horizon is implicit and whose `expires_at` is omitted; recommendation learning may publish that object durably. **[ATLAS][MODELLED] Required outcome:** post-pivot intelligence cites `org-v8`; stale actions disappear before delivery; the explicitly scoped exception remains correct; sparse Behavior is visibly weak; and short-horizon Adaptive returns `adaptive_ttl_unresolved` with no publication or consumption until lifecycle support is ratified. The repaired-lifecycle branch additionally requires an expiring Adaptive entry to have zero influence after `t1`. History, correction lineage and rollback remain available. The system must prove `pivot evidence → Organization version → dependent invalidation → Layer 3 consumption → intended decision change`; a stored row, Adaptive label, or changed explanation is insufficient. Modelled success is **zero stale-brain actions, zero fake personalization, zero mixed-version authority, zero non-expiring short-horizon Adaptive publication and zero over-broad reset**. Real Live and Outcome-proven claims still require tenant traces and externally reconciled results.

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "../08-Cross-Layer-Synthesis/04-Gold-Standard-Intelligence-Contract.md" (M5.C1.L-contract.V1.U01)
include "../08-Cross-Layer-Synthesis/08-HKS-and-Scenario-Responsibility-Matrix.md" (M5.C1.L-integration.V1.U01)
include "../07-Layer-7-Learning-Atlas-6/06-Improvements-Acceptance-and-Metrics/README.md" (M4.C3.L-interface.V0.U01)
-->
