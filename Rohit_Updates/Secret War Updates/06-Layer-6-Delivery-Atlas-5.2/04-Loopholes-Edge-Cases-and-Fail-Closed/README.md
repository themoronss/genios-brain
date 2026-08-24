# Layer 6 Delivery (Atlas 5.2) — Loopholes, Edge Cases, and Fail-Closed Rules

## Definitions

A Loophole is a path that satisfies current checks while violating the promised delivery guarantee. An Edge case is a legitimate operating shape requiring explicit behavior. A Consequence is labelled as observed code effect or risk; code inspection is not promoted to a production incident. “Fail closed” means no adapter call, a durable reason/result, and a retry/defer only when that is semantically safe.

## Loophole register

| ID | Loophole | How current code can pass | Consequence | Fail closed | Structural fix | Golden acceptance |
|---|---|---|---|---|---|---|
| L6-LP-01 | v2 present but legacy authoritative | Rich DeliveryObject/orchestrator/spine/tests exist while maintenance calls legacy `run_distribution` | Architecture appears complete although current audience/fencing/fallback never governs send | Capability status says Present, not live | One canonical materializer and worker | Runtime trace proves v2 delivery id from execution to result |
| L6-LP-02 | Two workers could claim same future v2 row | Legacy drain selects every `status='queued'` row without `legacy_reconcile` filter; v2 claim also selects queued non-legacy | If v2 materialization is enabled without migration, both worker models may touch a row | Do not enable v2 materialization while legacy drain can see its rows | Mutually exclusive row discriminator/queue and rollout fencing | Dual-worker test shows exactly one owner/attempt |
| L6-LP-03 | Legacy rows look v2-claimable | Migration adds `legacy_reconcile default false`; no repair/update writer was found | v2 claim can select old rows lacking `delivery_id`/execution hash if activated | Quarantine all pre-v2 rows before worker cutover | Explicit backfill/reconcile migration and NOT NULL/shape gates for v2 claims | Representative old queue migrates without send ambiguity |
| L6-LP-04 | Priority is lexical | v2 `claim_due` and inbox `order by priority`; priority is text | `background`, `critical`, `high`, `low`, `medium` sort lexically, not declared business rank | Use stable numeric rank; pause ambiguous scheduling | Persist rank or SQL CASE matching contract | Mixed-priority fixture claims critical→high→medium→low→background |
| L6-LP-05 | Live org routing assumes Slack | Distribution enumerates any active-channel org, then calls enqueue functions with default `slack` | Org configured only for another channel can create Slack work that terminally lacks config | Skip with explicit no-operational-route result | Iterate actual operational channels or canonical v2 ladder | Teams-only/no-Slack org never creates phantom Slack row |
| L6-LP-06 | “Operational” may mean secret exists | Capability API treats non-null `secret_ciphertext` as credentialed; no decrypt/shape/health check in that query | Corrupt/unusable secret can report operational | Report configured-but-unverified, not operational | Credential validator plus adapter health/contract probe | Corrupt ciphertext makes operational false without exposing secret |
| L6-LP-07 | Mixed-channel unit credential flag | `human` unit contains Slack/Teams plus in-app/dashboard but `needs_credential=False` at unit level | Human unit can appear operational from a configured push channel lacking usable credential | Evaluate credential need per channel | Per-channel capability contract, then aggregate | Each reported available channel independently usable |
| L6-LP-08 | Phantom universal pull surface | v2 routing inserts `in_app` as always available even if supplied channel list/client readiness lacks it | Unroutable delivery can become queued to a surface no customer polls | Materialization failure if no proven pull client | Tenant/client capability and presence lease for pull surface | No-client tenant gets visible no-route result |
| L6-LP-09 | Enqueue exceptions disappear | Per-org `run_distribution` catches broad exception with `pass` | Persistent org failure is invisible and reminder/event can wait indefinitely between sweeps | Record tenant-scoped enqueue/materialization failure | Dead-letter/metric with reason and retry schedule | Injected enqueue error appears in ops API and does not block other orgs |
| L6-LP-10 | Executive bridge is eventually, not transactionally, durable | Layer 5 event commits; later scan inserts legacy outbox row | Crash does not lose event permanently, but latency/silent backlog violates Atlas same-transaction claim | Surface unmaterialized-event age | Transactional outbox or reliable consumer offset | Crash after event commit recovers within SLA with one row |
| L6-LP-11 | Reminder authority is reduced to open+expiry | Dispatch trusts execution row open and unexpired | A reply/visibility/graph change before next Executive close can still be sent | Cancel/defer if current authority token cannot be proven | Versioned authority predicate or synchronous completion reconciliation | Reply between sweep and drain produces no adapter call |
| L6-LP-12 | Provider timeout retries legacy send | Slack result treats network exception/5xx as failure; bounded retry follows | Provider may have accepted message, causing duplicate human interruption | Mark ambiguous unknown and reconcile/manual review | Live v2 attempt/fence/provider id path | Accepted-then-timeout fixture produces one external message |
| L6-LP-13 | Per-channel dedupe creates multiple logical deliveries | Legacy uniqueness is `(org, card, channel)` | Adding channels can send the same insight once per channel, contrary to v2 one-row ladder | Keep one logical row until route result is definite | Canonical dedupe key + route ladder | Same execution across 10 destinations yields one logical delivery |
| L6-LP-14 | Results API excludes live legacy rows | Result routes require `delivery_id is not null`; legacy enqueues do not set v2 delivery id | Actual Slack deliveries are absent from canonical result timeline/attempt view | Label result API v2-only until cutover | Materialize all live sends as v2 or map legacy explicitly | Every adapter call has a visible DeliveryResult |
| L6-LP-15 | Dead letters miss live terminal name | Legacy writes `failed_terminal`; v2 dead-letter/analytics queries check `status='failed'` or lifecycle failed | Live terminal failures can be absent from dead-letter and failed counts | Query both controlled vocabularies during migration | One canonical terminal enum and backfill | Injected exhausted Slack row appears in API/analytics |
| L6-LP-16 | Legacy delivered lifecycle remains queued | Legacy drain updates `status`/`delivered_at`, not v2 lifecycle/event | Analytics by lifecycle can say queued while transport says delivered | Keep legacy/v2 metrics separate | Canonical transition function for every send | Delivered adapter call yields status/lifecycle/event agreement |
| L6-LP-17 | Client receipt can overstate execution | Receipt endpoint records actor=`client` at org scope; no receipt payload binds seat/device/action evidence | An org caller can mark accepted/executed and downstream may mistake it for real work | Treat as engagement only, not Executive/business completion | Authenticated actor/device, nonce, execution/action command join | Spoof/other-seat receipt rejected or explicitly low-trust |
| L6-LP-18 | “Grounded” hides semantic wrongness | Formatter copies existing fields exactly | Person/node dump or wrong target is delivered without fabrication yet still wrong | Suppress prescriptive delivery lacking semantic target | Required target/thread/current-state fields at materialization | Boardy dump produces review result, no send |
| L6-LP-19 | Rebuild interpreted as freshness | Expired card no longer blocks a new projection at `b739bd5` | Same semantically stale signal can yield the same wrong card again | Revalidate bounded situation before re-render | Situation version and supersession/completion gate | Resolved signal variant never rebuilds |

## Edge case matrix

| ID | Edge case | Correct behavior | Unsafe shortcut | Consequence | Fail-closed receipt |
|---|---|---|---|---|---|
| L6-EC-01 | Message becomes unauthorized while queued | Recheck visibility and recipient; suppress | Frozen assignee implies perpetual access | Privacy breach | `suppressed:visibility_revoked` |
| L6-EC-02 | Recipient leaves company after assignment | Re-resolve owner/recipient or block | Send to stale seat/channel | Data leak/no action | `unroutable:inactive_recipient` |
| L6-EC-03 | Known focus/meeting lease expires | Defer until exact window, retain business priority | Spend retries while waiting | Desired message terminally lost | Deferred event with `not_before` and attempts unchanged |
| L6-EC-04 | Two quiet-hour/rate judges defer differently | Latest `not_before` wins | Earliest window or majority vote | Violates one policy | Binding unit/reason persisted |
| L6-EC-05 | Suppress and defer both returned | Suppress wins | Retry later | Policy-forbidden send | Terminal suppression result |
| L6-EC-06 | Provider definite non-delivery | Release attention slot, bounded retry/fallback after re-gate | Hold quota forever | Artificial fatigue throttle | Failed attempt and next eligible route/time |
| L6-EC-07 | Provider outcome unknown | Retain attention reservation; no automatic cross-channel send | Treat timeout as definite failure | Duplicate notification | Unknown attempt awaiting reconciliation |
| L6-EC-08 | Same receipt retried by offline client | Idempotency key makes no-op | Add duplicate lifecycle events | Inflated engagement | Existing event id/result |
| L6-EC-09 | Receipt predates delivery or far future | Reject chronology | Trust device time blindly | False analytics/learning | 422 chronology error |
| L6-EC-10 | User viewed then delivery expires | Preserve viewed clock; terminal expiry remains distinguishable | Clear prior engagement | Incorrect funnel | Result contains both viewed time and expired state |
| L6-EC-11 | Delivery ignored versus never arrived | Only real delivered impression can become ignored | Infer ignored from queue age/failure | Opposite learning signal | No ignore event without impression |
| L6-EC-12 | One person owns multiple relationship actions | Separate delivery identities and target/thread summaries | Person-wide mega-card | Wrong action/recipient context | No materialization if target scope missing |
| L6-EC-13 | Restricted item has only admin fallback | Do not widen visibility to find a route | Route to admin queue automatically | Unauthorized disclosure | Materialization failure/suppression |
| L6-EC-14 | User has no active external channel | Durable proven pull surface or visible no-route | Pretend Slack/in-app exists | Silent loss | Capability/no-route result |
| L6-EC-15 | Adapter credential rotates between queue/send | Fetch validated current secret; fail affected row safely | Use stale/corrupt config or mark operational by non-null | Failed/unsafe send | Sanitized credential-unavailable result |
| L6-EC-16 | Work completes between gate and POST | Authority check must fence the exact send; cancel | Gate verdict alone authorizes network call | Stale nudge | Cancelled-before-delivery result |
| L6-EC-17 | Outbound HTTP holds authority locks | Bounded timeout and monitored lock duration | Unbounded call under shared graph locks | Write contention/outage | Timeout/unknown attempt and lock SLA alert |
| L6-EC-18 | Agent route exists but approval does not | Handoff stays unavailable | `engine_ready` implies executable | Unauthorized action | 501/blocked approval receipt |

## Fail-closed gates

| Gate | Required proof | Failure result | Never do |
|---|---|---|---|
| Input | Hash-verified current ExecutionObject, exact target/thread/action | Materialization failure/review | Deliver a person/node dump |
| Audience | Current active recipient and inherited visibility | SUPPRESS/unroutable | Widen to admin/connector silently |
| Capability | Implemented adapter/client, valid credential and health contract | No-route/dead letter | Equate config row with operational |
| Timing | Current presence, quiet hours, rate/budget and deadline | DEFER with clock or SUPPRESS | Spend retries on a hold |
| Authority | Current decision/execution/version immediately before adapter | CANCEL | Trust enqueue-time state alone |
| Worker ownership | Valid fence/lease and recorded started attempt | No call/reconcile | Send from expired/unowned claim |
| Provider result | Definite delivered/failed versus unknown classified | Reconcile/dead-letter unknown | Blind cross-channel retry on ambiguity |
| Receipt | Tenant, delivery, actor/device, chronology, legal transition and idempotency | Reject/no-op | Treat arbitrary `executed` as business success |
| Analytics | Real impression denominator and canonical statuses | Exclude/label incomplete | Count failed-terminal as invisible or click as ROI |

## Consequence-ranked blockers

| Priority | Blocker | Consequence | Exit condition |
|---:|---|---|---|
| P0 | Dual legacy/v2 worker truth | Unsafe cutover, missing canonical receipts, misleading readiness | One fenced sender; legacy quarantine/backfill green |
| P0 | Wrong semantic target allowed | More reliable delivery of wrong intelligence | Required target/thread gate and Boardy replay green |
| P0 | Card/receipt not welded to Executive | Accepted/executed analytics without accountable work | Idempotent command join green |
| P0 | Agent handoff unavailable | Capability promise exceeds safe behavior | Keep 501 until approval/lease/result suite green |
| P1 | Timeout ambiguity/live attempts | Duplicate human contact | Provider id/unknown reconciliation suite green |
| P1 | Result/dead-letter/status vocabulary split | Operators and analytics miss real deliveries/failures | Canonical lifecycle migration and reconciliation green |
| P1 | Operational capability overstatement | Customer configures a surface that cannot deliver | Credential/client health truth green |
| P1 | Routing ownership contradiction | Executive and Delivery can choose differently | Approved ADR and replay migration |
| P2 | Semantic expiry/rebuild gap | Stale recommendation regenerates | Current situation version gate |

## Verdict

The live path has good safety primitives, but these Loopholes show why enabling v2 piecemeal would be dangerous. Fail closed on input meaning, visibility, route capability, authority, worker ownership and receipt trust. The highest-risk work is consolidation: quarantine legacy rows, choose one sender, canonicalize status/results, and weld accepted actions to Executive before expanding channels or increasing notification volume.

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "../02-Customer-Expectation-and-HKS/README.md" (M4.C2.L-contract.V1.U01)
include "../03-Current-Successes-Failures-and-Expected-Behavior/README.md" (M4.C2.L-data.V0.U01)
-->
