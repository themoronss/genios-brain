# Layer 1 — Knowledge: Improvements, Acceptance, and Metrics

## Improvement objective

Turn the current capable ingestion framework into a source-authoritative Knowledge Layer that can prove: the decisive event was captured once, its roles and permissions survived unchanged, uncertainty was not converted into fact, incomplete coverage stayed visible, and every downstream claim can return to a permitted source receipt.

The order matters. More connectors, embeddings or faster models do not compensate for a missing role/visibility boundary.

## Prioritized decision plan

| Priority | Improvement | Exact change | Why first | Dependency | Acceptance evidence |
|---:|---|---|---|---|---|
| P0.1 | Versioned qualified-signal seam | Replace/extend `GatedEvent` with `QualifiedEnterpriseSignal.v1`: event/thread IDs, source receipt, actor and role candidates, participants, visibility/use class, signal atoms/evidence spans, domain candidates, coverage snapshot, lifecycle, processing lane and separate importance field | Every higher layer depends on this handoff | Contract + migration + connector mapping | Schema rejects missing permission/provenance; golden source fixtures serialize deterministically |
| P0.2 | End-to-end visibility propagation | Derive scope/principals/exclusions at connector/manual intake; store on source/prepared/signal; require narrowest merge above | Prevents data leak and prohibited commercial reuse | P0.1 plus auth identity | Private/participants/org/public and excluded-subject replays remain bounded through final delivery |
| P0.3 | Roleful communication capture | Preserve sender, recipients, internal/external classification, requester, introducer, introduced contact, target and unresolved role candidates by thread | Fixes Boardy and wrong-person intelligence at the source | P0.1; identity anchors | Boardy/Theresa fixtures produce correct roles; ambiguous roles park rather than guess |
| P0.4 | Scoped completeness/readiness | Attach provider/account/scope/window/freshness receipt to negative-evidence predicates | Stops “no reply/no meeting/no usage” when source is absent | Connection health + sync receipts | Disconnect, partial-folder and stale-cursor fixtures force unknown/abstention |
| P0.5 | Recoverable destructive gate | Change ambiguous model/provider drops to park/quarantine; retain minimal restricted audit receipt; calibrate by HKS cohort | Prevents irreversible loss of rare high-value signals | Retention/security policy | Zero unrecoverable high-value false drops in labelled replay set |
| P1.1 | Mutable-object version contract | Registry declares immutable/mutable and required provider version/tombstone mapping | Prevents frozen CRM/account/calendar truth | Source registry and mappings | Identical version dedups; changed version appends once; deletion revokes current state |
| P1.2 | Signal lifecycle projection | Stable signal identity plus new/active/satisfied/expired/superseded/revoked states | Prevents already-done evidence resurfacing as new | P0.1 and L2 reconciliation | Completion/correction fixtures transition exactly once with audit history |
| P1.3 | Single interpretation call | Consolidate L1 relevance and unstructured extraction into one versioned candidate response; deterministic validator/publication | Improves quality/cost while avoiding contradictory double interpretation | P0 contract and labelled corpus | Same or higher recall/role accuracy at lower calls per item; rollback-ready shadow diff |
| P1.4 | Source-specific sync contracts | Per-provider pagination, deletion, ordering, webhook/poll reconciliation and page receipts | Generic cursors cannot prove no-miss across all APIs | Connector fixtures | Fault injection reconciles provider IDs with zero missing/unexplained duplicates |
| P1.5 | Evidence receipt service | Resolve card fact → signal → prepared span → immutable provider locator/hash, with permission check | Makes intelligence quickly challengeable | P0.2 and retention | Authorized user opens exact passage; unauthorized user receives no metadata leak |
| P2.1 | Coverage expansion by value | Add sources only against named customer decisions: support/product/finance/operational | Source count is not intelligence; decision coverage is | P0/P1 correctness | Each new source unlocks a documented predicate and HKS replay |
| P2.2 | Content pipeline completeness | Govern speech-to-text, cross-source content fingerprints, quote/speaker boundaries and approved embeddings | Rich documents/meetings otherwise remain partial | Evidence/visibility controls | Audio/document duplicate and deletion replays preserve evidence and scope |

## Acceptance replay catalog

| Replay | Input shape | Required Layer 1 output | Forbidden output | Pass condition |
|---|---|---|---|---|
| A-L1-01 Theresa | Reconsideration invitation + 3 founder updates + silence | Four events, one relationship/thread chain, partner role, exact invitation, coverage state | “Rejected,” “last chance,” or invented deadline | No semantic loss; negative reply state only if inbox coverage complete |
| A-L1-02 Boardy | Connector with separate introductions | Connector role plus distinct introduced contacts and thread IDs | Boardy as target; one merged person history | N introductions create N bounded subject receipts |
| A-L1-03 Meeting state | Proposed, rescheduled, cancelled, completed/no-show variants | Each immutable calendar transition and current source state | “Met” from past schedule alone | Provider occurrence IDs reconcile without guess |
| A-L1-04 Group session | Internal-heavy cohort event, no transcript | Meeting event plus attendee/evidence availability | Synthetic recap commitment | No action signal without grounded external request/commitment |
| A-L1-05 Private support | Restricted ticket with affected subject | Private/use-restricted visibility and subject exclusion | Sales-eligible org-wide signal | Constraint survives every serialized seam |
| A-L1-06 Unknown investor | Sparse personal-email message with deck | Park/keep with attachment receipt and unresolved identity | Irrecoverable junk drop | Discoverable/recoverable and later linkable without duplicate |
| A-L1-07 Provider mislabel | Human request marked Promotions | Restricted quarantine receipt | Silent permanent deletion | Review restores the original exactly once |
| A-L1-08 CRM mutation | Same deal ID stage v1 then v2 | Two immutable events, one current v2 | Frozen v1 or duplicate v2 | Provider ID/version reconciliation exact |
| A-L1-09 Tombstone | Source deletes message/record | Revocation/tombstone event plus historical receipt | Continuing current use as active | Dependent signal becomes revoked/superseded |
| A-L1-10 Partial sync | Failure after N of page M | Error/page receipt; watermark at last safe boundary | Advancing beyond unseen items | Restart yields full provider-ID set |
| A-L1-11 Duplicate content | Same PDF via Drive, email, upload | One content identity, three source receipts | Triple evidence inflation | Semantic identity dedup; provenance retained |
| A-L1-12 Hinglish deadline | “kal bhej dunga” across timezones | Exact text, actor, due-text and ambiguity/anchor | Unreceipted absolute deadline | Resolve only with locale/time anchor, else ambiguous |
| A-L1-13 Unauthorized canon | Agent uploads false pricing as company policy | Ordinary/quarantined authority pending approval | Rank-4 company canon | Author/authority gate refuses promotion |
| A-L1-14 Visibility intersection | Org doc + private thread create one situation | Narrowest permitted principals, union exclusions | Org scope after merge | No viewer outside intersection can resolve receipt |
| A-L1-15 Backfill plus webhook | Same event arrives both routes | One source event and linked duplicate trace | Two active signals | Stable dedup across transport paths |
| A-L1-16 Encrypted scan | Password PDF from vendor | Park with reason, owner and retry/review route | Empty emitted request | No downstream interpretation until content available |
| A-L1-17 Alias/employer change | Same name, personal/work aliases, new company | Separate source identities plus merge proposal | Automatic cross-company collapse | No merge without approved/strong anchor |
| A-L1-18 Source disconnect | Gmail stale, CRM fresh | Coverage receipt scoped by source/predicate | “They did not reply” | Reply predicate unknown until Gmail fresh |

## Health Metric dictionary

| Metric | Numerator / denominator | Slice | Alarm meaning |
|---|---|---|---|
| Capture completeness | provider IDs durably accounted / provider IDs observed | source, account, window | Missing/advanced cursor or mapping loss |
| Signal recall | labelled material signals emitted or parked / labelled material signals | signal class, role, language, source | Valuable content lost before L2 |
| Irrecoverable false-drop rate | material drops without recoverable receipt / material labelled inputs | HKS and unknown sender | Production blocker; target zero for HKS |
| Role completeness | qualified signals with grounded actor/requester/target/subject state / communication signals | connector/thread type | Wrong-person risk |
| Visibility completeness | emitted signals with source-derived visibility/use class / emitted signals | source type | Permission guarantee not met |
| Evidence-grounding rate | semantic fields with valid source span / extracted semantic fields | field type/model version | Model output outruns evidence |
| Mutable freshness | mutable objects whose current version matches provider / sampled mutable objects | source/object type | Frozen or duplicate system truth |
| Parked age/SLA | parked items unresolved beyond policy / parked items | reason/owner | Recoverable queue has become a black hole |
| Capture-to-publish latency | p50/p95 event occurrence/capture to qualified publish | source/lane | Proactive window missed |
| Coverage freshness | predicates with fresh complete source receipt / enabled predicates | tenant/domain | Negative inference unsafe |
| Cost per 1k eligible events | model USD / eligible events × 1000 | task/model/source | Inefficient call topology |
| Cost per trusted signal | capture model USD / signals later accepted as grounded | tenant/domain | Spend disconnected from usable intelligence |
| Replay determinism | identical artifacts across identical evidence/version runs / replay runs | prompt/schema version | Non-reproducible capture |
| Receipt resolvability | permitted sampled facts opening exact source / sampled facts | age/source | Explainability or retention broken |

## Exit gate

Layer 1 may be promoted from **Framework-ready, not live-ready** to **Conditionally trustworthy** only when all of the following are freshly demonstrated:

1. The qualified-signal seam is Present, Wired and versioned; visibility, roles, evidence and scoped coverage are mandatory.
2. All 18 Acceptance replays pass with no skips, especially Theresa, Boardy, private support and partial-sync cases.
3. The HKS set has zero unrecoverable material false drops and zero visibility widening.
4. Provider reconciliation demonstrates no unexplained missing events for every production connector.
5. Negative-evidence predicates automatically become unknown when their exact source scope is stale/incomplete.
6. Model fields without valid source spans are rejected or parked; no model decides permission, identity merge, importance or publication.
7. p95 latency and cost per trusted signal meet an agreed tenant budget on a shadow cohort.
8. Every sampled downstream fact resolves to a permitted source receipt and transformation version.

**Live-ready** still requires tenant runtime traces. **Outcome-proven** additionally requires later-layer evidence that these correctly captured signals improved decisions or economic outcomes. Layer 1 test success alone can never satisfy either claim.

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "../04-Loopholes-Edge-Cases-and-Fail-Closed/README.md" (M2.C1.L-logic.V0.U01)
include "../05-LLM-Use-Cases-and-Cost/README.md" (M2.C1.L-logic.V1.U01)
-->
