# Four Brains — Storage, Ownership, Precedence, Snapshot, and Replay

## Blunt answer

The four-brain storage and snapshot architecture is real in the new Layer 3 compiler, but the four brains are not equally complete, governable, or semantically active.

- **Expert Brain** is the versioned professional corpus in Git. It is substantial as an architecture, but deep authored coverage is partial and every non-stub capability is still a draft/unreviewed artifact; there are zero reviewed or accepted capabilities.
- **Organization Brain** has a versioned row store and reader, but its default human-review path has a broken **approval bridge**: approval changes proposal state to `promoted` without calling `publish_brain`, so no learned row is created. The declared company-configuration boundary for ICP/products/policies and a complete pivot reset also do not yet exist.
- **Behavior Brain** has storage, governance and read paths, while its direct evolution unit currently emits nothing.
- **Adaptive Brain** has the same storage/read foundation, while its direct evolution unit also emits nothing. Recommendation learning can emit an Adaptive proposal, but `LearningObject.expires_at` is Runtime-only. An explicit Adaptive expiry is rejected, while an omitted expiry can pass validation and the publisher may persist that Adaptive entry durably. Therefore the current code does not fail closed or provide automatic short-horizon decay; `adaptive_ttl_unresolved` is the required safety disposition until the lifecycle contract is repaired.

The compiler deterministically combines the Expert snapshot and relevant runtime-brain snapshot into `brain_snapshot_id`. In the current Layer 4 adapter, however, Organization/Behavior/Adaptive values have **hash-only influence**: changing them can change the knowledge hash/version while leaving the goal, constraints, policies, candidate eligibility and ranking unchanged. Expert consumption is also narrow—a capability question may set the goal, and only up to four expert rules containing `definition.steps` become plays. The package path is default-off/shadow for customer authority. Therefore “stored and reproducible” is not the same as “semantically consumed, learned correctly, live, or outcome-proven.”

## Exact storage and ownership map

| Brain | Meaning | Authoritative source/storage | Write owner | Read/compile path | Version/expiry | Current operational truth |
|---|---|---|---|---|---|---|
| Expert Brain | Universal professional objects, rules, plays, mental models, failure patterns and source manifests | Human-authored YAML/documents under `Domain Expertise/`, loaded by `ExpertBrainCatalog`; immutable source hashes form the expert snapshot | Human/domain review and repository release; Learning may only raise a knowledge suggestion | `KnowledgeRetriever` + object resolution → `BrainResolver` → `ExpertSlice` | Git/content version and content hash; no automatic TTL | Present and compiler-wired, but Sales is 46 total / 3 non-stub drafts, Support 49 / 9, Admin 57 / 0; all 12 non-stub entries are draft/unreviewed and there are zero reviewed or accepted; new path is shadow |
| Organization Brain | This company’s scoped rules, preferences, process and learned company context | PostgreSQL `learned_brain_entries` with `brain='organization'`, keyed by `(org_id, brain, subject, version)` | Validation/governance can queue Organization for human review; the review endpoint currently does not complete the publish write | `PostgresRuntimeBrains.snapshot()` selects active relevant rows by tenant, capability, subject/entity selectors | One active version per published subject; `supersedes` and rollback supported; no general Organization config reset | Storage/read path Present, but the approval bridge is broken: review approval reports `promoted` without creating `learned_brain_entries`; declared config and pivot boundaries are incomplete |
| Behavior Brain | Stable person/team working patterns within a role/situation | Same `learned_brain_entries` table with `brain='behavior'` | Layer 7 governed publisher | Same runtime reader; filtered by relevance, tenant, visibility and conflicts | Versioned active row; rollback supported; stable pattern should not use short TTL | Storage/read path Present; `unit_behavior_evolution` reaches an empty cohort builder, so direct evolution is Stub |
| Adaptive Brain | Recent, scoped play/timing effectiveness and short-horizon preference | Same `learned_brain_entries` table with `brain='adaptive'`; temporary directives live separately in `temporary_memories` | Governed publisher after policy/lifecycle validity in the intended contract; currently an omitted-expiry proposal can reach durable publication | Same runtime reader; selected preference can outrank lower preference sources when valid | Versioned, but the contract permits `expires_at` only for Runtime; Adaptive TTL/decay is currently unrepresentable | Storage/read path Present; direct Adaptive evolution is Stub, recommendation learning can emit Adaptive without representable expiry, the publisher may persist it durably, and causal consumption proof is absent |

## What `brain_snapshot_id` actually proves

`genios_engine/packs/compiler/brain_resolver.py` builds:

1. an Expert snapshot from exact domain, situation, capability, manifest, object, artifact and variant source hashes;
2. a runtime snapshot from relevant Organization, Behavior and Adaptive entries;
3. a combined stable identifier over the two snapshot IDs.

The resulting identifier is placed on `ExpertisePackage.brain_snapshot_id`. It proves that the compiler can reproduce which content set it saw. It does **not** prove that the rows were accurate, fresh, sufficiently supported, permitted for the final use, populated for the tenant, authoritative in the live decision, or causally responsible for an outcome. Most importantly, it does not prove semantic influence: today a runtime-brain mutation can change that identifier and the adapter's knowledge hash while producing the same judgment.

| Receipt in snapshot | What it proves | What it cannot prove |
|---|---|---|
| Expert source version/hash | Exact authored corpus inputs | Professional completeness or live use |
| Runtime entry ID/version/hash | Exact selected learned value | Correct learning or sufficient population |
| `learning_id`/trace ID | Link to proposal lineage | External outcome caused by recommendation |
| Confidence basis points | Stored/published confidence value | Calibration or policy authority |
| Selected vs shadowed | Explicit keyed conflict result | Absence of semantic conflict without a shared key |
| Excluded entry IDs | Visibility filter removed known incompatible entries | End-to-end enforcement before/after this boundary |
| `brain_snapshot_id` | Expert plus runtime snapshot identity | Card authority while compiler remains shadow, or that any runtime value changed a decision field |

## Selection and precedence

Runtime entries are never swept tenant-wide merely because they exist. Selectors include capability IDs, required object IDs, situation ID, declared `brain_subject_keys`, and situation entities. Rows are tenant-scoped, active, relevant, and visibility-compatible before conflict resolution.

Two axes must remain separate:

| Axis | Intended precedence | Current safeguard | Remaining loophole |
|---|---|---|---|
| Permission/policy | Organization constraint overlays cannot be widened by learned Behavior/Adaptive; Expert hard constraints remain mandatory | `_validate_axis` rejects Behavior/Adaptive permission categories; Organization wins keyed runtime permission conflict | Expert-versus-Organization semantic conflict and unkeyed equivalent policies need explicit normalized keys/compile gate |
| Preference | Adaptive → Organization → Behavior → Expert defaults, only among valid in-scope entries | Runtime keyed preference conflicts rank Adaptive 3, Organization 2, Behavior 1 | High stored confidence does not prove outcome quality; stale/unkeyed preferences can coexist |
| Visibility | Narrowest permitted evidence/audience must survive | Runtime rows are rejected when package audience exceeds row visibility | Source-event visibility and downstream rendered-rationale enforcement remain cross-layer gaps |
| Coverage | Missing brain is represented as missing, never hallucinated | Empty runtime snapshot is reproducible | A valid empty hash can still be described to customer as “personalized” |

Selection and conflict resolution are real Layer 3 operations. Downstream semantic use is a separate contract. At the audited commit, the Layer 4 expertise adapter arrays the Organization, Behavior and Adaptive values into its `knowledge_hash`/version but does not map those values into goals, constraints, policies, candidate construction, eligibility or ranking. A selected row therefore has provenance but only hash-only influence until a typed consumer and mutation replay prove otherwise.

## Write lifecycle

```text
verified evidence/outcome
  → LearningObject proposal (immutable)
  → deterministic validation
  → target-specific governance
  → [Organization human review currently stops here: approval state changes, no brain publish]
  → learned_brain_entries version (organization|behavior|adaptive)
  → active relevant row read by Layer 3
  → Expert + runtime snapshot
  → brain_snapshot_id on ExpertisePackage
  → Layer 4 decision
  → execution/delivery/outcome
  → next bounded learning evaluation
```

The publisher does not write Expert Brain. `learning_objects_no_expert` and `learned_brain_no_expert` enforce this at storage; knowledge changes stop in `knowledge_suggestions` for human review. Byte-identical published brain values produce no version noise and material changes supersede the active version. The current rollback primitive can reactivate a predecessor or leave an empty active slot while preserving history, but it does not prove that the predecessor remains eligible under today’s expiry, policy, visibility and permitted-use rules. Required behavior is to restore only a **currently valid predecessor**; otherwise leave the subject empty/disabled and require review. These properties do not repair the Organization approval bridge, and stored LearningPolicy fidelity is also incomplete because `load_or_seed_policy` drops `blocked_targets` and `blocked_subject_prefixes` during load.

## Current gaps by brain

| Brain | Verified foundation | Missing or unsafe today | Required completion receipt |
|---|---|---|---|
| Expert Brain | Deterministic catalog, hashing, typed package, validation | Sales 3 and Support 9 are non-stub authored drafts—not accepted capabilities; Admin has zero non-stub; live legacy pack remains authority | Review-state admission, accepted dependency closure, route coverage, golden reasoning, scoped live package trace |
| Organization Brain | Governed learned target, versioned storage, active reader, human-review default | Review approval does not publish a learned row; policy reload can lose two block lists; no authoritative declared-config table/version for ICP/products/policies; reset avoids Organization rows | Atomic review-to-publish receipt, policy-load fidelity, config schema/version, author/reviewer, supersession, dependent-snapshot invalidation and pivot replay |
| Behavior Brain | Target/storage/read/rollback contracts | Direct cohort evolution returns no candidates; sparse-company confidence semantics incomplete | Roleful repeated cohort, population-aware gate, drift test, published version and compiler-consumption receipt |
| Adaptive Brain | Target/storage/read and preference precedence | Direct cohort evolution returns no candidates; recommendation learning can create Adaptive, but Adaptive cannot carry expiry under the current contract and omitted expiry may become durable; causal efficacy is unproved | Resolve `adaptive_ttl_unresolved`; enforce bounded lifecycle before publication, then require exposure/action/outcome join, delta/decay, pivot invalidation, consumption and later-outcome evaluation |

## Required golden replays

| Replay | Expert | Organization | Behavior | Adaptive | Expected package/result |
|---|---|---|---|---|---|
| Company discount cap conflicts with recent winning discount play | Supplies negotiation constraints | Cap/approval rule wins permission | Cannot widen cap | Winning play may affect preference only within cap | Package records rejected permission attempt and safe alternatives |
| Founder prefers terse emails but investor update needs substance | Supplies investor-update structure if domain covered | Company voice/policy constrains | Stable terse style informs formatting | Recent cadence evidence informs timing | Content requirement survives style; unsupported fundraising abstains rather than invents |
| Same human is investor and customer | Supplies domain-specific rules | Relationship/company policy scoped | Behavior entry selected only for correct role | Adaptive efficacy selected only for correct situation | Separate `brain_snapshot_id` values; no cross-role leakage |
| Sparse one-founder company | Expert defaults available | Declared policy available | Low-population behavior stays capped/observation | Empty or low-confidence Adaptive | Honest coverage vector; no fake personalization |
| ICP pivot | Expert remains unchanged | Old Organization version superseded | Writing style retained with confidence review | **Pre-repair:** `adaptive_ttl_unresolved`, so affected Adaptive authority is disabled/abstained; **post-repair [MODELLED]:** explicitly governed entries expire or are invalidated | All open situations recompiled; old ICP has no authority; current code does not pass this replay |
| Restricted support fact suggests upsell | Support expertise may interpret within allowed purpose | Company privacy policy blocks commercial use | No behavior reuse outside purpose | No Sales adaptive promotion | Evidence excluded from Sales package and rationale |
| Exact same evidence and brain versions replayed | Same content hash | Same selected row/version | Same selected row/version | Same selected row/version | Byte-identical `brain_snapshot_id` and package |
| Published learned value rolled back | Expert unchanged | Organization predecessor considered when targeted | Behavior predecessor considered when targeted | Adaptive predecessor considered only after lifecycle resolution | Recompile uses a currently valid predecessor under current expiry, policy, visibility and permitted-use rules; otherwise the subject remains empty/disabled, with no orphan active version |
| One runtime-brain value changes while all other inputs stay pinned | Expert unchanged | One normalized Organization constraint changes | Or one Behavior preference changes | Or one Adaptive preference changes under a valid lifecycle | `brain_snapshot_id` changes **and** the intended typed goal/constraint/policy/candidate/eligibility/ranking field changes; if only hash/version changes while judgment remains identical, semantic influence fails |

## Customer-visible contract

For any prescriptive card or agent consultation, the trace should expose: Expert corpus version, review state and accepted coverage; Organization/Behavior/Adaptive entries selected, shadowed, excluded, absent or stale; their evidence/learning versions; the final `brain_snapshot_id`; the exact typed decision field each selected value influenced; compiler authority mode; missing domain/capability; and policy/preference conflict resolution. Sensitive values may be redacted, but their existence, influence and exclusion reason must remain auditable. “Selected” or “included in hash” must never be presented as “used in judgment.”

## Final verdict

The answer is neither “four brains are missing” nor “four brains are ready.” The new compiler can read three runtime-brain stores, hash selected rows with the Expert Brain, enforce useful visibility/precedence rules, and publish a reproducible package. But Expert authorship has zero reviewed or accepted capabilities; Organization review approval does not publish; policy reload can widen authority; Behavior/Adaptive direct evolution are stubs; Adaptive expiry is unrepresentable and omitted expiry may be durably published; and Organization/Behavior/Adaptive currently have hash-only influence in Layer 4. The required `adaptive_ttl_unresolved` fail-closed state is not currently enforced. Tenant population/outcomes are unproven and the compiler remains shadow. The architecture is **framework-ready; four-brain semantic customer intelligence is not live- or outcome-proven**.

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "../03-Layer-3-Domain-Expertise/03-Current-Successes-Failures-and-Expected-Behavior/README.md" (M3.C1.L-data.V0.U01)
include "../03-Layer-3-Domain-Expertise/04-Loopholes-Edge-Cases-and-Fail-Closed/README.md" (M3.C1.L-logic.V0.U01)
include "../07-Layer-7-Learning-Atlas-6/03-Current-Successes-Failures-and-Expected-Behavior/README.md" (M4.C3.L-data.V0.U01)
-->
