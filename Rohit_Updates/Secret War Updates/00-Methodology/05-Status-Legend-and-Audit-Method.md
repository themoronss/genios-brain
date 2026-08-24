# Status Legend and Audit Method

## Controlled operational states

The central audit mistake to avoid is calling a component “ready” because its filename, schema, or test exists. Every Atlas component, capability, brain, rule, route, and customer scenario receives one highest-supported state.

| State | Exact meaning | Minimum evidence | What must not be inferred |
|---|---|---|---|
| **Absent** | No current artifact or behavior found at the pinned commit | Negative code search plus expected-location review | That the requirement is unnecessary |
| **Stub** | Shape exists but meaningful content or behavior is intentionally incomplete | Explicit stub/draft marker, empty unit, placeholder, or fail-closed endpoint | Runtime value |
| **Present** | A real contract, corpus item, implementation, or storage object exists | Current code or migration reference | Reachability or tenant use |
| **Wired** | The producing path hands the object to its declared consumer | Composition/root call path or integration test | Feature flag, tenant promotion, or live authority |
| **Live** | The wired path is enabled for the evaluated tenant/path and influences output | Runtime configuration and replay trace | Correctness or outcome impact |
| **Tested** | A named deterministic test validates the material behavior | Fresh passing command with skips disclosed | Production traffic or customer value |
| **Outcome-proven** | The behavior produced a verified customer/business result with attribution | Action, completion, outcome window, and counterfactual receipt | Generalization beyond the evaluated cohort |

Capitalized variants used in prose—**Stub**, **Wired**, **Outcome-proven**—refer to these definitions and nothing broader.

## Status rules

1. The highest state needs direct proof; lower states may be implied only when logically necessary.
2. A feature flag default-off can be Present and Wired but not Live.
3. A shadow decision can be Present, Wired, and Tested while remaining non-authoritative.
4. A generated registry entry can be Present while its capability remains Stub.
5. A card rendered in screenshots can be Live at the surface, even if its underlying interpretation is wrong.
6. A passing unit test cannot promote a capability to Outcome-proven.
7. A skipped test does not contribute to Tested status.
8. A contract with no propagation/enforcement remains Present.
9. “Current tenant unknown” is not converted into Live by assumption.
10. Counts always inherit the commit and command that produced them.

## Required comparison table

Every layer’s current-state report must include rows with this schema:

| Component or scenario | Atlas expected | Current proof | State | Success | Current failure | Loophole | What should have happened | Improvement | Acceptance evidence |
|---|---|---|---|---|---|---|---|---|---|

A success means a responsibility that actually survives to its claimed boundary. A “framework exists” statement belongs under Current proof; it is not automatically a customer-visible success.

## Failure taxonomy

| Failure class | Test question | Example |
|---|---|---|
| Capture loss | Did decisive source meaning survive Layer 1? | Exact request reduced to generic `question` |
| Identity/role loss | Is the correct business subject, actor, owner, and target represented? | Boardy connector becomes the person to reply to |
| State-reduction failure | Did multiple facts become one current state? | Meeting proposed and completed both treated as open |
| Coverage failure | Is the correct domain/capability authored and routable? | Fundraising forced through Sales |
| Authority failure | Did the intended path actually control the live decision? | Deep compiler runs only in shadow |
| Decision failure | Is the recommendation specific, comparative, and defensible? | Age-driven “reply now” |
| Execution failure | Did the accepted recommendation become accountable work? | “I’ll do it” changes card state only |
| Completion failure | Was real-world resolution reconciled? | Replied elsewhere but loop stays open |
| Learning failure | Did verified outcome update a bounded brain safely? | Click treated as success |
| Governance failure | Were visibility and permitted-use constraints preserved? | Private support signal used commercially |
| Value-proof failure | Can benefit be attributed against a counterfactual? | Closed deal counted as influenced because card existed |

## Loophole versus edge case

- A **loophole** is a path that formally satisfies current checks while violating the intended guarantee. Example: a company-name fact makes identity confidence look high even when the recipient is wrong.
- An **edge case** is a legitimate operating shape the design must handle. Example: one person is an investor, customer, and partner in different relationships.
- A **failure** is an observed or mechanically demonstrated incorrect result.
- A **risk** is a plausible consequence without current reproduction.
- A **gap** is expected capability for which present evidence is weaker than required.

These labels are not interchangeable.

## HKS handling

The user supplied the label **HKS** without an authoritative expansion in the evidence set. This update preserves “HKS” literally and uses it for the high-consequence scenario register requested by the user. It does not invent a full form.

Each HKS row includes:

| Field | Required content |
|---|---|
| Business situation | Bounded real-world state |
| Harm if wrong | Revenue, trust, privacy, safety, or operating consequence |
| Required layers | L1–L7 responsibilities |
| Prohibited output | The confident but wrong behavior |
| Fail-closed result | Observation, review, suppression, defer, or no-decision |
| Golden replay | Deterministic fixture and expected trace |
| Exit gate | Evidence required before production authority |

## LLM audit method

A whole-layer percentage is only a planning approximation. Every LLM report must break usage into components:

| Dimension | Required answer |
|---|---|
| Task | Extraction, entity/role resolution, consultation, drafting, or feedback parsing |
| Current path | Model, trigger, default flag, call site |
| Proposed rate | Eligible-event percentage and confidence gate |
| Deterministic pre-gate | Permission, dedup, source integrity, required context |
| Deterministic post-gate | Schema, provenance, conflict, policy, range, replay |
| Cache key | Evidence hash, model/prompt version, tenant boundary |
| Cost | Calls, tokens, latency, fallback, retry ceiling |
| Forbidden authority | Number, score, route, recipient, permission, or final action the model cannot own |

“80% LLM” in Layer 1 can mean high use on messy content extraction; it never means 80% model authority over provenance, permissions, deduplication, or business truth.

## Verdict scale

Each layer ends with one blunt Verdict:

- **Operationally trustworthy** — golden replays and outcome gates are green.
- **Conditionally trustworthy** — bounded scenarios pass; uncovered scenarios abstain safely.
- **Framework-ready, not live-ready** — meaningful implementation exists, but wiring/coverage/evidence is insufficient.
- **Unsafe for prescriptive output** — the layer can generate confident wrong action.
- **Unknown** — required runtime evidence was unavailable.

The final system Verdict is the weakest critical dependency on the active customer-value path, not an average of attractive component scores.


<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "03-Source-and-Commit-Manifest.md" (M1.C1.L-data.V0.U01)
include "04-Customer-Intelligence-Contract.md" (M1.C2.L-contract.V0.U01)
-->
