# Layer 6 Delivery (Atlas 5.2) — Improvements, Acceptance, and Metrics

## Target

The target is one canonical delivery control plane: every eligible Layer 5 execution event produces one durable logical DeliveryObject or a visible materialization failure; one fenced worker chooses a lawful current route, revalidates authority, records every attempt/result, and joins human/agent action back to the same execution. No legacy/v2 parallel truth, no silent enqueue failure, and no claim that engagement equals business outcome.

## Prioritised improvement register

| Priority | Improvement | Current problem | Delivery slice | Acceptance | Metric | Exit gate |
|---:|---|---|---|---|---|---|
| P0 | Ratify Executive/Delivery routing ownership | Atlas late-binds recipient/channel/time; current Executive freezes them | ADR defines semantic intent, concrete route authority, reassignment/version behavior and migration | Same fixture has one owner at each decision; no layer silently overrides | Cross-layer route disagreement | Approved ADR plus replay suite before schema/wiring change |
| P0 | Quarantine and backfill legacy rows | `legacy_reconcile` defaults false and no repair writer found; old rows can look v2-claimable | Mark rows without v2 identity/lineage as legacy/ambiguous; publish reconciliation report; add v2 shape predicate | Representative queued/delivered/failed-terminal rows classified without adapter call | Unclassified legacy rows; ambiguous external-call rows | Zero unclassified rows; owner-approved replay for ambiguity |
| P0 | Make worker populations mutually exclusive | Legacy drain selects generic queued rows; v2 claim selects non-legacy queued rows | Legacy drain excludes v2 identities; v2 claim requires delivery/execution/hash/dedupe/fence shape; rollout kill switch | Dual workers cannot claim/send same row under concurrency | Dual-claim/duplicate external message rate | Deterministic dual-worker stress test zero duplicates |
| P0 | Wire canonical v2 materialization | No production caller of resolve/materialize/claim | Valid ExecutionObject/event → audience/presence/route/gate → atomic materialize → queued event; failures durable | Runtime trace contains execution hash, delivery id, dedupe key and materialization event | Materialization coverage/latency; unmaterialized-event age | 100% eligible events resolve to object or failure within SLA |
| P0 | Implement fenced v2 dispatch | Strong spine/retry/rate modules are not live sender | Claim lease, started attempt + attention reservation commit before I/O, authority revalidation, adapter call, settle/result | Crash/lease expiry/timeout sequences never create invisible or blind duplicate call | Attempts without ledger; expired claims; unknown outcomes | Failure-injection suite green with zero unledgered calls |
| P0 | Canonicalize lifecycle and DeliveryResult | Legacy status and v2 lifecycle diverge; live rows absent from v2 results/dead letters | One typed versioned DeliveryResult; transition function updates status/lifecycle/events/attempts; map `failed_terminal` | Every terminal and engagement state round-trips; live Slack appears in results/dead letters | Result coverage; status/lifecycle disagreement; hidden terminal failures | 100% adapter calls/results visible; disagreement zero |
| P0 | Enforce semantic input contract | Delivery can faithfully send wrong connector/person dump | Require exact target/thread/action/current authority or observation-only; no model/action button otherwise | Boardy and stale-meeting fixtures suppress/review before adapter | Wrong-target/stale-send rate | Zero wrong-target/stale sends in golden and labelled pilot set |
| P0 | Weld accept/execute to Executive | Delivery/client/card lifecycle can move without ExecutionObject action | Authenticated idempotent command records delivery acceptance and claims linked execution action; completion remains evidence-gated | Duplicate/concurrent click converges on one claim; click never completes outcome | Unlinked actions; card/delivery/execution divergence | Zero divergence in crash/concurrency suite |
| P0 | Keep agent handoff fail-closed | Intended handoff returns 501 | Build approval token, one executor lease, signed scoped envelope, revocation and idempotent result before enabling route | Duplicate approvals yield one executor; stale/revoked token cannot act | Unauthorized/duplicate agent attempts | 501 removed only after security/result suites green |
| P1 | Resolve timeout ambiguity and fallback | Live Slack exception is retried without provider reconciliation; v2 ladder not dispatched | Classify definite failed vs unknown; provider request/message id; unknown stops; definite failure advances only after full re-gate | Provider accepted-then-timeout sends once; definite fail may use one lawful fallback | Duplicate sends; unknown backlog; fallback policy violations | Provider fault-injection suite zero blind replays |
| P1 | Fix priority scheduling | Text `order by priority` is lexical | Persist numeric rank or explicit SQL CASE shared with contract | Mixed queue claims critical→high→medium→low→background, with starvation control | Priority inversions; max wait by class | Ordering/fairness property tests green |
| P1 | Make capabilities truthful | Non-null ciphertext and mixed unit credential flag can overstate operation | Per-channel engine, adapter, client, credential decrypt/shape, health and receipt status; aggregate after channel truth | Corrupt secret/no client reports configured-not-operational | False-operational rate; send-probe agreement | Every operational channel passes conformance/health probe |
| P1 | Record enqueue/materialization failures | Per-org broad exception is swallowed | Tenant-scoped failure/dead-letter, retry clock, alert and resolution workflow | One org’s error remains isolated and visible | Silent enqueue failures; oldest unresolved failure | Silent count zero; failure API/runbook verified |
| P1 | Deepen dispatch authority | Reminder dispatch checks open+expiry only | Fenced current execution/decision/visibility/target version or synchronous completion reconciliation | Reply/revoke between sweep and drain cancels delivery | Stale reminder send rate | Race fixtures zero sends after revocation/completion |
| P1 | Trust receipts explicitly | Org-scoped generic `client` actor can post engagement lifecycle | Seat/device/provider identity, nonce/signature, source class and confidence; executed joins action command | Spoof/other-seat/impossible receipt rejected; duplicate no-op | Untrusted receipt share; illegal transitions | High-trust execute metrics include only verified receipts |
| P1 | Preserve expiry/rebuild liveness with semantic gate | `b739bd5` fixes expired projection block, not meaning | Rebuild after current roleful situation/supersession check; link old/new projection | Resolved signal never rebuilds; still-valid signal rebuilds once | Duplicate rebuilds; stale rebuild rate | Expired/resolved/open matrix green |
| P2 | Move LLM to optional grounded copy | Current one call writes card and artifact early; V-02 is shallow | Deterministic card meaning; optional claim-cited copy; on-demand artifact; cache and durable cost telemetry | Model-off behavior identical; unsupported claims rejected | Unsupported claims; calls/card; cost/used artifact | HKS grounding zero errors and budget fallback green |

## Safe cutover plan

| Phase | Scope | Rollback boundary | Completion condition |
|---|---|---|---|
| 0 — contract freeze | ADR, typed DeliveryResult, controlled vocabularies, v2 row shape | Documentation/schema feature flag | Owners sign recipient/channel/time and lifecycle mapping |
| 1 — data reconciliation | Inventory/backfill legacy rows and ambiguous attempts; add read-only reconciliation report | Backfill migration reversal/backup | Every existing row classified; no implicit replay |
| 2 — shadow materialization | v2 resolve/materialize dry comparison without adapter; legacy remains sender | Disable shadow writer | Route/gate/result differences reviewed; no shared-claim risk |
| 3 — fenced worker canary | One tenant/channel uses v2 worker; legacy excludes v2 rows | Tenant kill switch returns to reconciled legacy sender | Failure-injection, receipts, dead letters and metrics green |
| 4 — canonical cutover | All eligible sends use v2; legacy writes disabled | Time-bounded compatibility reader only | 100% DeliveryResult coverage and zero dual claims |
| 5 — surface expansion | Email/extension/mobile/agent added one at a time | Per-adapter operational flag | Conformance, credential, visibility, idempotency and receipt tests per adapter |
| 6 — copy optimisation | On-demand LLM draft/tone with cache | Disable model, deterministic copy remains | Grounding, cost and edit gates green |

## Acceptance scenarios

| Scenario | Required trace | Forbidden result | Acceptance evidence | Exit gate |
|---|---|---|---|---|
| Legacy migration | Old queued/delivered/failed-terminal/ambiguous rows → classification → reconcile decision | Old row claimed as new v2 work or silently replayed | Backfill report, owner decision, no adapter call during migration | All representative states pass |
| Dual-worker race | Legacy drain and v2 claimant run concurrently against mixed rows | Both touch one row | Row discriminator, leases, attempt ledger | 10k-race simulation zero dual claim/send |
| Theresa update | Cadence-qualified execution → correct target → quiet/presence gate → one send → response window | Generic repeated Slack reminder or connector target | Target/thread/cadence, gate, delivery, action/outcome receipts | Exactly one eligible result across timeline |
| Boardy introductions | Connector plus three targets → bounded executions → independent delivery IDs | One Boardy mega-card or cross-target facts | Separate target/thread/dedupe/result | Zero connector-target errors |
| Focus mode | Critical work arrives during live meeting lease | Retry consumed or phone push | DEFER event, exact `not_before`, unchanged attempts; durable pull if permitted | Timing matrix exact |
| Visibility revoke | Delivery queued, access revoked before dispatch | Adapter receives payload | SUPPRESS/cancel with policy/version reason | Zero calls after revoke |
| Provider accepted then timeout | Started attempt commits; provider records message; response lost | Auto-retry/cross-channel duplicate | Unknown attempt, retained attention slot, reconciliation record | One external impression |
| Definite provider failure | Provider proves non-delivery | Unknown forever or blind louder fallback | Failed attempt, released slot, re-gated next rung or terminal result | One lawful result, bounded attempts |
| Priority mix | Five classes plus continuous critical arrivals | Lexical order or starvation | Numeric order and aging/fairness trace | Contract order plus max-wait bound |
| “I’ll do it” | Delivery/card accept → authenticated command → one ExecutionAction claim → later evidence close | `executed`/business completion from click | Actor/idempotency/action/execution/result chain | Duplicate/concurrent replay converges once |
| Agent handoff | Approved exact task → one lease → signed instruction → result | Two agents, generic webhook, unapproved tool | Approval/lease/signature/result | 501 removed only after this passes |
| Expired card rebuild | Expired old projection with open-valid vs resolved situation | Permanent block or stale duplicate | Situation version and old/new link | Only open-valid variant rebuilds once |

## Metric hierarchy

| Level | Metric | Definition | Anti-gaming rule | Target/alert |
|---|---|---|---|---|
| Integrity | Eligible materialization coverage | Eligible execution events with DeliveryObject or visible failure | Failure counts in denominator | 100% |
| Integrity | Result coverage | Adapter calls with typed DeliveryResult, attempt and event | Legacy rows not excluded | 100% |
| Integrity | Dual-claim rate | Logical rows touched by more than one live worker/fence | Retries counted separately, not hidden | 0 |
| Integrity | Status/lifecycle disagreement | Rows whose status, lifecycle, clocks and last event conflict | Migration rows labelled, not discarded | 0 after cutover |
| Correctness | Right-recipient precision | Labelled deliveries sent to exact authorized target/thread | Connector/admin fallback errors included | 100% golden; pilot threshold agreed |
| Correctness | Stale-send rate | Adapter calls after authoritative completion/revoke/supersession | Queue delay does not excuse | 0 |
| Safety | Duplicate external impression rate | More than one human interruption for one logical event without explicit approved replay | Cross-channel duplicates included | 0 |
| Safety | Untrusted executed receipts | Executed lifecycle lacking actor/device/action proof | Do not promote generic client receipt | 0 in outcome/learning feed |
| Reliability | Materialization latency | Executive event commit to queued DeliveryObject/failure | Include failures/backlog | p50/p95 plus oldest age alert |
| Reliability | Unknown-attempt age | Time ambiguous provider attempt awaits reconciliation | Never auto-count as failed/delivered | SLA and alert |
| Reliability | Dead-letter completeness | Known materialization/terminal failures visible in API | Include `failed_terminal` during migration | 100% |
| Policy | Defer correctness | Holds with attempts unchanged and correct binding window | Failure retries excluded | 100% golden |
| Policy | Suppression/cancel reason coverage | Terminal no-send states with unit/reason | Generic error not enough | 100% |
| Attention | Intrusive impressions per recipient | Verified chat/push deliveries by window | Only delivered impressions | Tenant budget and fatigue trend |
| Capability | Operational/send-probe agreement | Channels labelled operational that pass adapter/client/credential probe | Config row alone insufficient | 100% |
| Engagement | View/accept/execute rates | Verified events over delivered impressions | Never mix nondelivery or low-trust receipt | Reported with source class |
| Outcome | Delivery-to-business-result join | Results joined to ExecutionOutcome and attribution window | Engagement not ROI | Coverage and attributed cohort, no invented lift |
| LLM | Unsupported claim rate | Model claims without explicit allowed evidence | Names/numbers-only validation insufficient | 0 HKS/golden |
| LLM | Cost per used artifact | All generation/retry spend divided by artifacts actually used | Rejected/unused calls remain cost | Configured budget; downward trend |

## Release gates

1. The fresh `192 passed, 11 skipped` selected suite is not sufficient for cutover: required database, worker-crash, provider-ambiguity and adapter integration cases run with zero skips.
2. Legacy and v2 workers have mechanically disjoint predicates before v2 materialization is enabled.
3. Every v2 claim requires non-null delivery identity, execution lineage/hash, dedupe key and a valid fence.
4. Priority order is encoded numerically and tested; lexical text order is removed from claims/inbox.
5. Every actual adapter call appears in typed results, attempts, events, dead letters and analytics under one vocabulary.
6. Missing semantic target, visibility, operational route, current authority or approval yields a durable non-send result.
7. Card/delivery acceptance is welded to Executive action; a click cannot mean completion/outcome.
8. Agent handoff remains HTTP 501 until approval, single-executor and result gates pass.
9. `a90ff66` bounded maintenance and `b739bd5` expired-card rebuild behavior remain, with an added semantic-current-state gate.
10. LLM-disabled operation preserves route, gate, priority, lifecycle and output truth; budget failure never suppresses important work silently.

## Decision

Do not add channels first. The decisive Improvement is to make the extensive v2 code the single truthful sender without allowing it to race or reinterpret legacy rows. After data reconciliation, fenced cutover, canonical results, semantic target enforcement and Executive action welding, add one adapter at a time. The Exit gate is a customer-verifiable chain from exact execution to one lawful delivery and one trustworthy result—not the number of delivery units present in the repository.

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "../04-Loopholes-Edge-Cases-and-Fail-Closed/README.md" (M4.C2.L-logic.V0.U01)
include "../05-LLM-Use-Cases-and-Cost/README.md" (M4.C2.L-logic.V1.U01)
-->
