# Layer 3 — Architecture and Atlas Delta

**Evidence baseline:** `harsh/mvp@b739bd5ca682d09550acc400ed2892c38c8518f8`, audited 2026-08-22. Atlas references are to `GeniOS-System-Design-Atlas.md:1262-1592`. “Current code” means verified source at that commit, not a deployed-tenant claim.

## Blunt answer

Domain Expertise is **not merely a list of YAML files**. YAML is the human-reviewable source representation of the Expert Brain; `ExpertBrainCatalog` parses those sources, the resolver selects the applicable slice, and the compiler emits an immutable `ExpertisePackage`:

`BusinessSituationObject → capability/object resolution → four-brain snapshot → ExpertisePackage → Layer 4`.

That typed chain exists and is wired through Layer 4 **only inside a default-off shadow pass**. It can compile and reason when enabled, but it cannot control the authoritative customer decision or delivery. The customer path still uses the old `SALES_V1` and `GENERAL_V1` pack. The new path is therefore **wired for shadow measurement, not Live for decision authority, and materially incomplete in reviewed expertise**. Wiring alone will not turn 43 Sales stubs into deep expertise; nor do three non-stub files become accepted expertise merely because the compiler admits them.

## Atlas contract versus implementation

| Atlas expectation | Current code proof | State | Gap / consequence |
|---|---|---|---|
| Eight-stage deterministic compiler | `packs/compiler/domain_compiler.py:22-55` composes resolver, retriever, brain resolver, evidence, builder and publisher | Present, tested | Correct architecture exists; live authority is elsewhere |
| Situation → capabilities → objects | `capability_resolver.py`, generated `registry/situation-capability-map.yaml` | Present | Only authored routes work; unsupported situations must abstain |
| Four brains pinned into one package | `brain_resolver.py:20-75` selects and hashes Expert plus runtime snapshots; `reason/adapters/expertise.py:104-213` then builds the Layer 4 manifest | Present in the package; semantically partial downstream | No tenant proof of useful dynamic entries, and the current adapter does not project selected Organization/Behavior/Adaptive values into typed constraints, candidates, ranking or wording |
| Permission axis separate from preference axis | `runtime_brains.py:28-35,136-190` blocks Behavior/Adaptive permission claims and resolves explicit conflicts | Present, tested | Only explicit `conflict_key` collisions are resolved; unkeyed contradictions coexist |
| Narrowest visibility survives compilation | `runtime_brains.py:101-109,193-250` excludes entries the package audience cannot see | Present, tested | Visibility safety is implemented in the new path, not evidence that legacy cards use it |
| Deterministic, byte-replayable `ExpertisePackage` | snapshot hashes in `brain_resolver.py:42-75`; typed contract in `contracts/domain_expertise.py` | Present | Shadow pass uses `publisher=None`; package persistence is not the default live path |
| Layer 3 never decides | `DomainCompiler.compile()` ends at package publication; `ExpertisePackage` explicitly carries no recommendation | Present | Adapter supplies generic plays/DAG; the quality of downstream options is still thin |
| Compiler reaches runtime reasoning | `reason/domain_shadow.py:93-125` compiles, adapts, and calls Layer 4 in `ExecutionMode.SHADOW` | Wired, shadow only | A shadow decision may be measured, but no authoritative decision or card is changed |
| Safe staged activation | `platform/config.py:85-89` defaults `use_domain_compiler=False`; adapter sets `live_delivery_enabled=False` at `reason/adapters/expertise.py:190-213` | Present and Wired, not Live | Deep files can be absent from every customer-visible recommendation |
| Domain expansion without engine rewrite | Sales, Customer Support and Admin directories share one schema/compiler | Present | Authorship and route coverage differ radically across domains |

## Why this is still on the old path: history, not a speed rollback

| Commit/evidence | What changed | What it proves | What it does not prove |
|---|---|---|---|
| `9c7ce4c` · “Layer 3: live shadow wiring (Phase A)” | Introduced `use_domain_compiler=False`, `publisher=None`, and no Layer 4 feed | The design was **shadow-first from inception** and explicitly default-off | That a later performance problem forced a rollback |
| `7da562e` · “Layer 3->4 weld” | Added the `ExpertisePackage → CapabilityManifest` adapter and called reasoning with `ExecutionMode.SHADOW`; manifest retained `live_delivery_enabled=False` | L3→L4 is wired for measurement, while customer authority remains disabled | That shadow output is reviewed, accepted, or production-safe |
| `215b647`, `ec81a31`, `55c26f4`, `3a27eac` · P1/P2 runner performance series | Bulk-loaded context and reduced/batched audit writes in `reason/runner.py` | Later speed work optimized the runner | These commits did not change `use_domain_compiler`, `ExecutionMode.SHADOW`, or `live_delivery_enabled=False`; there is no evidenced “shift back” caused by speed |

At the pinned head, `reason/runner.py:525-539` still runs the new path as an optional decoupled pass and then resolves the effective legacy pack. The operational reason for old-path cards is therefore the original activation policy plus missing acceptance evidence—not a later reversion.

## The four brains: what, where, and precedence

| Brain | What belongs there | Source/storage now | Current read path | Precedence rule |
|---|---|---|---|---|
| **Expert** (“tumhara expertise”) | Professional capabilities, objects, rules, playbooks, mental models, failure patterns | Human-authored Git under `Domain Expertise/`; content-addressed by the compiler | `ExpertBrainCatalog` → `KnowledgeRetriever` → `ExpertSlice` | Supplies defaults and hard professional constraints; never auto-mutated |
| **Organization / Company Brain** | This company’s policy, ICP, products, approval rules, vocabulary and operating model | Active versioned rows in PostgreSQL `learned_brain_entries`; review-required proposals can remain approved-but-unpublished | `PostgresRuntimeBrains.snapshot()` in `runtime_brains.py:263-286` reads only published active rows | Organization beats Expert on permission; cannot be widened by learned preferences |
| **Behavior Brain** | What people/teams actually do: cadence, channel, working style, repeated outcomes | PostgreSQL `learned_brain_entries`, brain=`behavior` | Same tenant-scoped snapshot reader | Lowest learned preference precedence; cannot define policy/permission |
| **Adaptive Brain** | Atlas intends short-horizon preferences, current phase, priority/notification and calibrated response | PostgreSQL, brain=`adaptive`; current durable `LearningObject` rejects expiry on any non-Runtime target | Same snapshot reader; direct Adaptive evolution currently emits no candidates, while recommendation learning can emit durable non-expiring Adaptive entries | Highest preference precedence, but never overrides permission or compliance; current TTL semantics are unresolved |

The combined `brain_snapshot_id` is derived from the Expert content hash plus runtime-brain snapshot (`brain_resolver.py:71-75`). Every included runtime entry carries version, content hash, confidence, learning id and selection status (`runtime_brains.py:214-249`). This is a real reproducibility mechanism, but it does not prove application. **Organization, Behavior, and Adaptive are hash-only at the current Layer 3-to-4 adapter**: their selected values enter `knowledge_hash`, while `_plays()` consumes only `expert_rules`, `_goal()` consumes only a capability question, and the reasoner DAG and policy tuple remain generic (`reason/adapters/expertise.py:104-213`). A changed hash proves changed package identity/provenance; it does not prove the company rule or learned preference changed Layer 4 constraints, candidates, ordering or wording.

The current producer path has a separate governance break. **Organization approval does not publish, and policy loading drops both prohibition fields**. Review-required Organization proposals are queued (`feedback/publisher.py:168-188`); the review endpoint changes `learning_objects.state` to `promoted` and logs the transition but never invokes `publish_brain` (`api/learning_routes.py:119-143`). Separately, `load_or_seed_policy()` reconstructs `LearningPolicy` without `blocked_targets` or `blocked_subject_prefixes`, even though both exist in the contract (`feedback/orchestrator.py:28-45`; `contracts/learning.py:284-298`). Therefore an approved proposal need not become an active Organization row, and stored target/subject prohibitions need not survive policy reload.

The present lifecycle contract also contradicts “short-horizon Adaptive.” **Adaptive cannot carry expiry; screenshot alignment is an inference, not a reproduced causal trace**. `LearningObject` permits `expires_at` only for `LearningTarget.RUNTIME` and raises for Adaptive (`contracts/learning.py:184-227`); direct Behavior/Adaptive cohort units currently return no candidates, while recommendation learning can create non-expiring Adaptive entries (`feedback/units.py:165-218`). Until an ADR defines TTL/invalidity semantics, a stale decision-relevant Adaptive entry must block prescriptive authority rather than silently win preference precedence. Likewise, code-path compatibility with the supplied cards does not establish the tenant, commit, flags or exact upstream trace that produced them.

## Domain scope and actual completeness

Fresh mechanical counts at `b739bd5`:

| Domain | Capability files | Stubs | Non-stub authored drafts | Reviewed or accepted | Routed L2 types | Authored situations | All-stub routes | Operational reading |
|---|---:|---:|---:|---:|---:|---:|---|---|
| Sales | **46** | **43** | **3** | **0** | **19** | **6** | **7**: `contract_requested`, `deal_health`, `going_dark_after_proposal`, `legal_in_review`, `security_review_pending`, `single_threaded_deal`, `verbal_yes_not_closed` | Broad skeleton; the three admitted capabilities are draft/unreviewed, not a seasoned seller |
| Customer Support | **49** | **40** | **9** | **0** | **5** | **14** | **3**: `intro_followup`, `meeting_no_followup`, `unanswered_email` | The registry has **14 authored situations** but only five routed L2 types; three of those routes contain only stubs |
| Admin | **57** | **57** | **0** | **0** | **0** | **0** | none | Taxonomy only for runtime purposes; cannot responsibly prescribe Admin work |

“Non-stub” is a mechanical admission marker, not a quality grade. All 3 Sales and all 9 Support non-stub capabilities have `identity.status: draft`, `metadata.review_status: unreviewed`, and no reviewer; across all three domains there are **zero reviewed or accepted** capabilities. `CapabilityResolver` filters only `identity.stub: true` (`capability_resolver.py:96-105`) and has no review-state gate, so any `stub:false` capability is admitted regardless of draft/unreviewed status.

`validate.py` reports **0 errors and 715 warnings**. Passing means structurally admissible, not expert-complete: warnings include unreachable artifacts, unauthored core objects and six emitted L2 situation types with no route. The Sales README is stale where it says “1 complete, 45 stub”; the commit-stamped file inspection above is authoritative.

## What the live customer path uses

`packs/wiring.py:9-23` registers `SALES_V1` and `GENERAL_V1` as built-in defaults. `reason/runner.py:525-540` optionally calls the new compiler only behind the default-off flag, then continues into the effective legacy pack. The live pack rules are compiled through `reason/adapters/legacy_pack.py:24-145`, typically exposing one generic review play. Native manifests remain shadow-first; `packs/capabilities/__init__.py:16-22` sweeps only the seven-unit Deal Cooling baseline, while the full 17-unit candidate is imported but excluded.

This code state is **compatible with the supplied screenshots**: a large new corpus can exist on disk while cards still say “Reply now”, “Send recap”, or “Reset the plan.” That is an **[INFERENCE]** from the pinned default/authority path, not proof that those exact cards ran this commit and tenant configuration. A card-level causal claim still requires its runtime trace. At the pinned code default, the old rule/template path remains authoritative and the deeper compiler output measures parity without replacing it.

## Architecture decision

Do not flip one global switch. Promotion must be by **domain + situation + capability version**, with an admission manifest that requires: `stub:false`; `review_status: reviewed|accepted`; named human reviewer; immutable version/content hash; route and required objects complete; zero all-stub route; dynamic-brain visibility/conflict tests; a typed consumer plus metamorphic semantic-effect proof for each decision-relevant selected brain entry; byte-stable package replay; L4 multiple defensible candidates or explicit abstention; reviewed legacy/new shadow parity; and a golden customer replay that beats the legacy card. Before promotion, repair review-to-publish, preserve both prohibition fields on policy reload, and ratify Adaptive TTL/invalidity behavior. A hash is provenance and change detection, not semantic approval or downstream influence.

## Verdict

**Framework-ready, not live-ready.** The Atlas-shaped compiler, typed package, four-brain snapshot and two-axis precedence are real. The new Layer 3 is wired for deliberately default-off shadow execution, not customer authority, and the corpus is materially partial and unaccepted. Sales is not “46 active capabilities”; Support is not complete merely because 14 situations are authored; Admin has no executable route. Activating it before review-state admission and capability-by-capability acceptance would replace generic legacy errors with confident compiler-backed gaps.

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "../../00-Methodology/02-Layer-Numbering-and-Semantic-Map.md" (M1.C1.L-contract.V1.U01)
include "../../00-Methodology/05-Status-Legend-and-Audit-Method.md" (M1.C2.L-logic.V0.U01)
-->
