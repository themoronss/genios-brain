# Layer 1 — Knowledge: Architecture and Atlas Delta

## Verdict

**Framework-ready, not live-ready as the Atlas Layer 1 contract.** The current code has a serious capture spine—source registry, buildable connectors, cursor-based sync, webhook intake, deduplication, preprocessing, recoverable parking, trace records, and a typed `GatedEvent`. However, the object actually handed to Layer 2 is not the Atlas `QualifiedEnterpriseSignal`: it does not carry source visibility, a normalized business-signal type, relevance/importance basis points, lifecycle state, expiry, or a source-authoritative recipient/role model. Consequently, Layer 1 can reliably move and filter data while still losing the exact semantics needed for safe executive intelligence.

This is a **[CODE]** verdict for `harsh/mvp@b739bd5`; it is not proof that any particular tenant has every connector configured, that all paths are Live, or that the resulting intelligence is Outcome-proven.

## Responsibility boundary

| Question | Atlas expectation | Current code | Gap / consequence |
|---|---|---|---|
| What does Layer 1 answer? | “What happened?”; collect and qualify, never correlate or decide. | `capture/pipeline.py:124-243` lands, preprocesses, gates, triages and emits; it does not select a final action. | Boundary is directionally correct. Triage labels processing order, but the seam is thinner than the Atlas signal contract. |
| Input surface | 16 enterprise-source classes. | `capture/source_registry.py:74-133` catalogues communication, knowledge, enterprise, deliberate, operational and intelligence sources. Eight canonical source IDs are buildable in `platform/wiring.py:31-85` (`gmail`, `gcal`, `notion`, `gdrive`, `hubspot`, `postgres`, `database`, `mysql`; aliases add stored IDs). | Catalogued is not connected. Slack, Teams, Outlook, Jira/Linear, CRM alternatives, support desks and several financial/product sources are Present only as descriptors or absent from construction. |
| Connector control | Manager, auth, permissions, incremental sync, webhook and volatility-based polling. | Per-org connections and Composio/direct construction are Wired (`platform/wiring.py:44-85`); cursors/recovery and bounded retry are Present (`capture/acquire/sync_runner.py:64-179`); Composio push endpoint is Present (`api/routes.py:1280-1314`). Default polling is six-hourly (`platform/config.py:64-71`). | No Atlas-grade Permission Manager stamps ACLs at capture. Polling is one configurable cadence, not demonstrably source-volatility-driven. Live connector health per tenant is Unknown. |
| Preprocessing | Separate heavy content and light event pipelines. | HTML/native extraction, language detection, PII masking, offset mapping, structured mappings, attachment status and OCR option are Present (`capture/pipeline.py:150-239`; `capture/preprocess/preprocess.py:8-25`). | There is no complete Atlas content pipeline for speech-to-text, general relationship extraction, embeddings and cross-source document dedup. OCR defaults off (`platform/config.py:82-84`). |
| Qualification gateway | ESQE is the only exit; detector → normalizer → classifier → source analysis → relevance → domain → importance → threshold → lifecycle → publisher. | One `run_gate` path controls capture outcomes; S0/S1 are deterministic, S2 is optional LLM/deterministic relevance, then deterministic domain hints and triage (`capture/gate/gate.py:11-60`; `capture/pipeline.py:189-243`). | This is not the ten-part ESQE. It classifies junk vs keep/park/drop but does not produce the full qualified business signal, formula importance, signal lifecycle, or normalized commitment/request/risk type. |
| Output | `QualifiedEnterpriseSignal` with provenance, actor, entities, domain, importance, relevance, state and expiry. | `GatedEvent` carries event/source/object/time, route, structured fields, cheap domain/linkage hints, triage lane and versions (`contracts/gated_event.py:14-39`). | **Contract mismatch:** critical signal semantics are deferred to an L2 model, while Atlas says Layer 1 qualifies before publication. |
| Visibility | Stamp source audience once; all merges may only narrow. | `contracts/visibility.py:30-102` implements scopes, excluded subjects, `can_view`, and `narrowest`. | The capture contracts `RawObject`, `SourceEvent` and `GatedEvent` contain no `visibility`; L2 BSO creation hardcodes `org` (`context/situation_bso.py:122-166`). The protection is Present but not Wired through L1. |

## Component coverage

| Atlas component | Current proof | State | Success | Gap |
|---|---|---|---|---|
| Source registry | `capture/source_registry.py:56-185` is the derived source of family/capability/buildability views. | Tested at baseline, current targeted status not rerun here | Eliminates several drifting hand-maintained lists. | A descriptor does not prove connector availability, data depth, permissions or freshness. |
| Incremental sync | `capture/acquire/sync_runner.py:96-179` resumes cursor/watermark, retries, quarantines poison events and avoids moving recovery watermark. | Present and Wired | Boundary overlap is deduped; failed objects do not crash the batch. | Provider ordering and deletion/tombstone semantics need source-specific replays. |
| Immutable landing | Stable dedup key and world/capture time split in `contracts/source_event.py:21-57`. | Present and Wired | Mutable structured objects can use a content version; immutable mail replays dedup. | Wrong/missing provider version can either freeze changes or duplicate history. |
| Prepared evidence | PII-masked text plus offset map in `contracts/prepared_content.py:25-48`; persisted at `capture/pipeline.py:221-223`. | Present and Wired on configured store | Evidence can map back to source offsets without retaining raw text indefinitely. | HTML stripping changes coordinate basis; model-grounding and user-visible receipt replay require end-to-end proof. |
| Recoverable grey zone | Unsupported/OCR-review/fetch-failed content parks; parked payload TTL is 365 days (`capture/gate/rules.py:97-104`; `capture/pipeline.py:205-220`). | Present | Ambiguous or failed material is not silently deleted. | Human review SLA, queue ownership and recovery completeness are not Atlas output fields. |
| Junk gate | Deterministic high-certainty rules plus optional batched LLM relevance (`capture/gate/rules.py:88-145`; `capture/gate/relevance.py:113-227`). | Wired; Live depends on key and tenant settings | LLM failure opens to keep, preventing infrastructure failure from silently losing email. | A confident model can still hard-drop a real unknown-sender message, and the dropped body is not retained for audit/recovery. |
| Domain hints | Cheap source/text hints are persisted (`capture/pipeline.py:194-212`). | Present and Wired | Gives L2 a routing hint without final decision authority. | Hints are not an authored Domain Mapping decision or coverage guarantee. |
| Importance | Triage regex returns P0–P3 (`capture/triage/triage.py:8-43`). | Present | Gives deterministic processing order. | It is explicitly not business priority and cannot replace Atlas `importance_bp`. |
| Signal lifecycle | Source outcome is emitted/parked/dropped/duplicate; mutable versions can re-land. | Partial | Operational capture lifecycle exists. | No `new → active → satisfied/expired/superseded` lifecycle for the business signal at the L1 boundary. |
| Visibility propagation | `Visibility` contract exists. | Present, not Wired through capture | Narrowest/exclusion semantics are well defined in isolation. | Defaulting reconstructed situations to org scope can widen private evidence and violates the Atlas source-stamping invariant. |

## Atlas design versus present execution

The Atlas places most semantic qualification in deterministic ESQE and permits models only for ambiguous extraction/relevance. Current code makes a different cut: Layer 1 emits a routing envelope, then Layer 2 makes a combined relevance-plus-extraction call (`platform/config.py:60-62`; `context/pipeline.py:230-283`). That choice is not automatically wrong, but it creates three obligations that current architecture has not fully discharged:

1. **No source meaning may disappear before L2.** Recipient roles, visibility, provider ACL, exact thread identity, attachments and source state must survive the seam.
2. **L2 model output cannot become authority.** Grounded extraction can propose semantics, but provenance, permissions, numeric importance, identity joins and destructive state transitions need deterministic validation.
3. **The seam needs an explicit equivalence contract.** Either implement Atlas `QualifiedEnterpriseSignal` in L1, or ratify `GatedEvent` as a deliberately thinner boundary and prove Layer 2 reconstructs every required field without guessing.

## Highest-risk architectural delta

The largest risk is not missing source count; it is **role-and-permission loss at the first handoff**. Gmail connectors retain `to` and `cc` in raw payload, but `RawObject` and `SourceEvent` identify only a transport actor, and the emitted `GatedEvent` does not preserve a typed requester, introducer, business subject, owner or visibility object. Later code can read recipient arrays from the retained payload, but that is a best-effort reconstruction, not the Atlas guarantee. This is how a Boardy connector can become the “person to reply to,” and how person-wide facts can be displayed without the correct thread boundary.

## Required architecture decision

Adopt a versioned `QualifiedEnterpriseSignal.v1` (or formally equivalent `GatedEvent.v3`) containing: source receipt, immutable event/thread IDs, actor plus role candidates, recipients/participants, source visibility and exclusions, exact signal atoms with evidence spans, deterministic source family/authority, domain candidates, model extraction metadata, conflict flags, lifecycle, and separately named processing-priority versus business-importance fields. Publication to Layer 2 must fail closed to `park/review_source` when permission, source identity, or required evidence is missing; it must never synthesize those fields downstream.

Until that seam is implemented, wired, replay-tested and observed on tenant traces, Layer 1 should be described as a capable ingestion framework—not as a complete Knowledge Layer satisfying the Atlas.

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "../../00-Methodology/02-Layer-Numbering-and-Semantic-Map.md" (M1.C1.L-contract.V1.U01)
include "../../00-Methodology/05-Status-Legend-and-Audit-Method.md" (M1.C2.L-logic.V0.U01)
-->
