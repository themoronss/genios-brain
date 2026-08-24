# Layer 2 — Context Intelligence: Architecture and Atlas Delta

## Verdict

**Substantial context framework, unsafe as the complete live business-situation authority.** Current code does much more than retrieval: it versions facts, preserves out-of-order history, records discrepancies, resolves anchored identities conservatively, correlates thread and cross-tool evidence, builds lifecycle-aware situations, separates coverage from confidence, and exposes typed Layer 2 → Layer 3 contracts. Yet the final `BusinessSituationObject` seam reconstructs required evidence, hardcodes organization visibility, supplies neutral importance, omits explicit dependencies/relationships and leaves `missing_fields` empty. Live cards can therefore consume person-aggregated or semantically incomplete context even though the graph infrastructure itself is sophisticated.

This **[CODE]** Verdict is pinned to `harsh/mvp@b739bd5`. A focused 214-test Context suite passed, but that is Tested behavior—not proof of tenant runtime completeness or Outcome-proven intelligence.

## Atlas responsibility versus Current code

| Area | Atlas expectation | Current code | State | Gap / consequence |
|---|---|---|---|---|
| Boundary | Input qualified signals; output complete `BusinessSituationObject`; never reason | L2 consumes emitted/structured events, extracts candidates, commits graph, correlates and refreshes situations (`context/runner.py`; `context/pipeline.py:230-657`) | Wired for legacy context path | L1 input is thinner than Atlas qualification; live reasoning does not necessarily consume the typed BSO seam. |
| Context graph | One logical graph with entity, relationship, temporal, authority, ownership, communication, resource and knowledge views | Nodes, edges, versioned facts, observations, source refs, aliases, discrepancies, correlations, situations and derived lenses/read models exist | Present and substantially Wired | Eight views are not explicit complete contracts. Authority/ownership/resource/use-restriction semantics are partial and depend on available fields. |
| Graph quality engines | Build, update, validate, dedup, freshness, lifecycle, version, consistency | Transactional `GraphStore` versions writes; fact write protects against stale/replay overwrite and records conflict (`context/graph_store.py:29-223`); exact identity aliases and merge proposals exist (`context/identity.py:58-225`) | Tested | No proof every graph mutation travels through all eight quality gates; merge review and runtime health ownership remain operational dependencies. |
| Identity | Resolve same real entity without unsafe joins | Exact anchored keys auto-resolve; name collisions do not auto-merge; ambiguous duplicates create proposals | Tested | First claimant holds a same-name alias; later name-only mentions resolve to it (`context/identity.py:134-145`), which can still attach prose to the wrong same-name person. |
| Cross-correlation | Cross tool/resource/user/timeline/conversation/domain/org/dependency | Thread-first hard continuity; otherwise strongest anchor + first deterministic domain hint + 45-day generation; people can lift to company (`context/correlation.py:108-360`) | Tested | Independent deals at one company collapse without deal object; first domain hint forces one domain; explicit dependency/cross-organization engines are not complete. |
| Context quality | Separate confidence, freshness, conflict, noise, missing context, evidence, completeness and validation | Situation vector has evidence/freshness/consistency/identity; overall is minimum; coverage is separate (`context/situations.py:100-224`) | Tested | Generic/unregistered domain declares no expected fields and therefore 100% coverage; absence of expectation can appear complete. Source-coverage readiness is not bound into the BSO. |
| Situation candidate generator | Pattern detection only, before business-situation validation | Correlations are directly materialized into domain/anchor-derived situations during refresh | Present | There is no explicit candidate/discarded stage with receipts; domain specs partly define situation semantics inside L2. |
| Situation engine | Detect, build, cluster, prioritize, score confidence, manage state/lifecycle, publish | Correlation groups, typed situation, confidence vector, active/dormant/resolved/archived lifecycle and active query exist (`context/situations.py:227-464`) | Tested | L2 deliberately does not prioritize, correctly avoiding reasoning; however Atlas “prioritization” wording conflicts with this invariant and needs ratification. |
| Typed output | Evidence, entities, relationships, timeline, dependencies, confidence/importance, state, visibility | `BusinessSituationObject` contract requires these shapes (`contracts/domain_expertise.py:54-124`) | Present | Producer includes one anchor entity/timeline, no relationships/dependencies, neutral importance, reconstructed evidence and hardcoded org visibility (`context/situation_bso.py:69-166`). |
| Projection/lenses | Multiple domain views over one graph, never separate truth | Derived domain projections, boundary edges and unprojected nodes are implemented (`context/projections.py:66-235`) | Tested | Membership follows current situation domain; a wrong first domain hint still puts context in the wrong lens. |
| LLM policy | Optional graph build/entity link/naming; no model correlation or validation authority | One combined temp-0 extraction call creates candidates; grounding/identity/fact authority/correlation are deterministic (`context/extract/extractor.py:9-64`; `context/pipeline.py:258-283`) | Wired when key configured | Model relevance still drives observation confidence and semantic candidates; required role/current-state validation is incomplete. |

## Strong architecture already present

| Verified design strength | Evidence | Why it matters |
|---|---|---|
| Store-and-score | Low relevance is retained; only network/correlation is suppressed for detected noise (`context/pipeline.py:258-280`, `652-657`) | Avoids turning model relevance into silent evidence loss. |
| Authority and time ordering | Older facts become historical; lower-authority disagreement becomes a discrepancy; replay never flips current state (`context/graph_store.py:29-55`) | Backfill cannot overwrite today’s truth. |
| Independent corroboration | Same value from a new event adds a source receipt instead of being ignored (`context/graph_store.py:142-159`) | Cross-tool agreement can increase evidence strength. |
| Conservative identity | Exact key equality only; fuzzy names propose rather than merge (`context/identity.py:10-31`) | Prevents invisible fusion of two customers. |
| Under-correlation bias | Thread continuity is hard; weak anchor correlation splits after 45 days; nothing is a valid outcome (`context/correlation.py:14-44`, `187-209`) | Avoids chimeric situations when evidence is weak. |
| Honest meeting label | Past scheduled calendar item is labelled occurrence unverified, never held (`api/routes.py:2132-2149`) | Prevents calendar presence from fabricating attendance. |
| Confidence vector | Overall is the weakest supported trust dimension; coverage is separate (`context/situations.py:22-46`, `190-224`) | One strong score cannot hide identity conflict or stale evidence. |
| Lifecycle | Fact resolution re-derives; human resolution reopens on new evidence; old resolved situations archive | Supports current reality instead of permanent stale loops. |

## The central structural failure

The graph is still frequently **person-scoped where the product needs roleful relationship/thread/deal state**. Direction-derived fields such as `thread.ball_in_court`, `thread.last_inbound`, `thread.last_outbound` are written on person nodes (`context/pipeline.py:393-414`, `558-578`). Legacy commitment fields are dual-written back to the person even after first-class commitment nodes were added (`context/pipeline.py:580-630`). A person who is simultaneously investor, prospect, partner and introducer can therefore expose the latest field from one relationship to a card about another.

Correlation mitigates this with thread-first membership, domain and anchors, but the read/render path can still dump node-wide facts and observations. This code shape is **compatible with the supplied screenshots**, including dozens of Boardy introductions/meetings on one card: storage can know many events while the context slice shown to a decision is not narrowly role/thread scoped. That linkage is an **[INFERENCE]**, **not a reproduced causal trace** for those exact cards; proving causality requires the card's tenant, commit, flags, event membership, BSO/context slice and consuming decision trace.

## BSO boundary delta

| BSO field | Current producer | Atlas-grade requirement |
|---|---|---|
| `signal_ids` | Reconstructed from correlation; synthetic `sig:<situation>` fallback | Persist exact qualified-signal membership; synthetic IDs must force review, not satisfy completeness |
| `evidence` | Reconstructed from source refs; synthetic situation receipt fallback | Source-authoritative receipts with visibility, field spans and transformation versions |
| `entities` | One anchor only | Roleful requester/owner/target/introducer/contact/company/deal set |
| `relationships` | Empty default | Typed role and dependency edges relevant to this situation |
| `timeline` | First/last seen only | State transitions, request/promise/response/meeting/completion sequence |
| `dependencies` | Empty default | Explicit blockers, approvals and upstream/downstream obligations |
| `confidence_bp` | Situation overall percent × 100 | Preserve vector and unknown dimensions; do not collapse context completeness |
| `importance_bp` | Constant 5000 | No L2 business-priority invention; use optional/unknown or downstream decision value |
| `visibility` | Hardcoded `org` | Narrowest visibility of every member signal plus exclusions/use constraints |
| `missing_fields` | Empty in `SituationContextSlice` | Required role/context/readiness gaps, tied to domain/capability version |
| `metadata` | Marks `shadow: true` and default importance | Include graph/spec/coverage/extractor/source completeness versions and conflict state |

## Architecture decision required

Keep the strong graph machinery, but make the situation—not the person—the smallest decision context. Introduce explicit relationship/thread/deal role nodes or scoped state keys; persist qualified-signal membership, source visibility and scoped coverage; build the BSO from that bounded membership; and block action authority when signal IDs/evidence are synthetic, visibility is defaulted, identity is contested, or required role/current-state fields are missing.

Until live reasoning and cards consume that versioned BSO (rather than a broader node snapshot), Layer 2 is **a meaningful, Tested context framework with an unsafe final seam**, not the Atlas-complete current-reality authority.

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "../../00-Methodology/02-Layer-Numbering-and-Semantic-Map.md" (M1.C1.L-contract.V1.U01)
include "../../00-Methodology/05-Status-Legend-and-Audit-Method.md" (M1.C2.L-logic.V0.U01)
-->
