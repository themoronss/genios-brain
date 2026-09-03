# Layer 4 — Loopholes, Edge Cases, and Fail-Closed Rules

**Audit baseline:** `harsh/mvp@b739bd5ca682d09550acc400ed2892c38c8518f8`. A **Loophole** passes a current structural check while violating the decision guarantee. An **Edge case** is a legitimate operating situation. “Fail closed” means return typed no-action/defer/review with missing inputs and no action authority; it does not mean emit a safer-sounding generic imperative.

## Central risk

The reasoning engine can be mechanically correct yet strategically useless. If it receives one generic play, lacks business stakes, or confuses score with confidence, deterministic ranking only makes the wrong abstraction reproducible. Layer 4 must challenge both candidates and its own ability to decide. It cannot assume that because Layer 3 compiled a package, the package is complete or the BSO is coherent.

## Loophole register

| Loophole | Mechanism | Consequence | Fail closed control | Evidence needed to permit action |
|---|---|---|---|---|
| One candidate counts as ranking | Legacy adapter supplies one play; decision maker can still select it | No comparative judgment, false inevitability | Require distinct fallback/do-nothing or explicit proof only one safe option exists | Candidate-set diversity and elimination trace |
| Seventeen registered equals seventeen active | Registry contains units not scheduled by active manifest | Architecture is sold as current behavior | Receipt lists actual scheduled/executed/skipped units | Accepted manifest version in runtime trace |
| Brain hash change equals judgment change | `reason/adapters/expertise.py:180-213` includes Organization rules, Behavior patterns and Adaptive preferences in `knowledge_hash`/version but does not use their values to shape goal, constraints, policies, candidate eligibility or ranking | A changed snapshot/version is reported as adaptation while the recommendation remains semantically identical | Treat this **hash-only influence** as provenance only; block claims of brain influence without a typed semantic-consumption receipt | One-brain-at-a-time mutation replay proves the exact allowed decision delta or explicit no-effect |
| Expert presence equals Expert influence | `_goal()` may consume one capability question, while `_plays()` consumes only `expert_rules` with `definition.steps` | Rules, heuristics, mental models and failure patterns can be packaged but decision-inert | Mark every unconsumed artifact class and prohibit “Expert-backed” authority beyond the consumed subset | Artifact-class mutation matrix and per-artifact consumption/rejection receipt |
| **steps-only** play conversion plus **four-play cap** is treated as full playbook coverage | `_plays()` at `reason/adapters/expertise.py:104-153` skips rules without steps, silently stops after four qualifying plays, and falls back to generic `review_situation` when none qualify | A strategically superior fifth play disappears; a rich corpus can collapse to generic review | Do not promote the manifest unless deterministic selection/truncation reasons and coverage are explicit; fallback remains review-only | Five-play fixture proves ordering/selection policy, and zero-steps fixture proves generic fallback has no prescriptive authority |
| Deterministic equals intelligent | Stable scores/order look rigorous | Generic advice is repeatably generic | Gold-grounded utility gate, not replay alone | Expert-labelled candidate and outcome evaluation |
| Score equals confidence | Card score mapped to `confidence_score` | Priority becomes false epistemic certainty | Separate priority, confidence, urgency, coverage | Typed vector with independent calibration |
| Age equals urgency | Last-heard/due age drives card | Old low-value work outranks current high-value opportunity | Require business stakes, cost of delay and expiry | Domain-specific urgency evidence |
| “Ball in court” equals unresolved action | Direction is inferred without exact request/completion state | Completed/superseded threads resurface | Missing request or state yields review/no-action | Exact open-loop object and supersession check |
| Missing stakes/completion accepted | API projection explicitly carries `missing` but still renders imperative | User cannot judge importance or done state | Prescriptive projection blocked on required fields | Stakes and observable completion supplied |
| Generic fallback after abstention | API/legacy templates can still make action text | Core `DEFER` safety is bypassed | Abstention has higher authority than any presentation fallback | End-to-end no-action projection test |
| LLM explanation legitimizes weak decision | Grounded prose can still sound senior | Fluency hides one-play/generic logic | No explanation call until candidate/gate contract passes | Decision quality receipt shown before prose |
| Rephrased options count as alternatives | Semantic duplicates survive as separate strings | Illusion of choice | Candidate semantic-key dedup plus material-difference test | Different channel/timing/strategy/trade-off |
| Empty constraint set means candidate safe | Missing upstream restrictions are treated as no restriction | Unsafe winner | Required constraint classes must be present or explicit not-applicable | Permission, role, visibility, approval receipts |
| Scalar floor fixes missing expertise | Numerical confidence is lowered but action survives elsewhere | Unsupported domain still prescriptive | Coverage is a hard gate, not score factor | Accepted Layer 3 capability/version |
| UI warning repairs reasoning | Connector/context warning shown above malformed card | User still gets wrong aggregated action | Suppress/replace decision, not decorate it | Rebuilt relationship-scoped decision |
| Idempotency equals semantic dedup | Delivery dedup prevents repeated send of same id | Multiple cards represent same underlying loop | Canonical relationship/open-loop decision key | One active authoritative decision per loop |
| “I’ll do it” equals execution/completion | User accepts recommendation | Learning can treat intent as result | Keep proposed/accepted/claimed/executed/completed/outcome distinct | External completion and outcome receipt |

## Edge case register

| Edge case | Correct decision shape | Common wrong candidate | Consequence | Fail closed result |
|---|---|---|---|---|
| Only one legally permitted action exists | One primary plus explicit eliminated alternatives and reasons | Invent unsafe fallback to satisfy plurality | Compliance breach | Select sole action only with complete hard-gate trace |
| Waiting is the best move | `NO_ACTION` with next observation trigger and expiry | Follow up because silence exists | Spam/relationship damage | No action button; schedule observation only |
| Opportunity is valuable but evidence is weak | Request specific evidence/review; do not amplify by value | High value raises confidence | High-impact wrong action | `DEFER` with evidence acquisition step |
| High confidence, low priority | Correct but commercially minor action ranks below material work | Confidence makes it top card | Founder distraction | Preserve separate priority rank |
| Low confidence, high urgency | Escalate review safely before deadline | Model chooses action because delay is costly | Time-pressured error | Human review with deadline; no autonomous execution |
| Candidate has high upside and catastrophic downside | Show downside, permission/approval and safer alternative | Expected-value average hides tail risk | Severe financial/reputation harm | Eliminate if hard risk threshold exceeded |
| Contact is both investor and customer | Generate role-scoped candidates; do not merge objectives | One universal follow-up | Cross-purpose message | Defer until active relationship/opportunity is clear |
| Connector escalation may help | Compare direct follow-up versus permission-safe connector nudge | Always contact connector or never use them | Damaged network | Require connector role/consent/cadence evidence |
| Meeting occurred but notes are absent | Ask owner for outcome/notes, not send invented recap | Generic recap based on invitation | False claims | Review/observation candidate only |
| Meeting did not occur | Suppress recap; decide reschedule only if still desired | “Send recap” | Nonsensical outreach | `NO_ACTION` or evidence-based reschedule decision |
| Thread contains multiple unresolved asks | Separate or sequence decisions by dependency/owner | One vague “reply” | Partial resolution and forgotten ask | Decompose; defer if asks cannot be reliably separated |
| Action was completed in another tool | Reconcile completion and suppress candidate | Repeat task because source thread unchanged | Duplicate work | Await/retrieve cross-tool completion evidence |
| Primary candidate expires while awaiting approval | Re-rank with new timing/state | Execute stale approved action | Context-invalid execution | Decision expires and returns for re-reasoning |
| Two cards compete for same scarce owner/time | Portfolio-level prioritization or dependency | Each card claims urgency 100% | Impossible workload | Surface conflict and require scheduling/portfolio reasoning |
| Do-nothing consequence is genuinely unknown | Label unknown and request evidence | Generic scary consequence | Manipulative urgency | `DEFER` or low-authority observation |
| Company Brain permission changes but adapter semantics do not | New version must eliminate newly prohibited candidates and expose the policy receipt | Only manifest hash changes; prior candidate still wins | False governance assurance | `BLOCKED`/review until semantic policy consumption is proven |
| Behavior or Adaptive entry changes but should legitimately have no effect | Record scoped no-effect because policy, expiry, role or situation makes it inapplicable | Force a visible recommendation change merely to prove adaptation | Learned noise or policy override | Preserve decision and emit deterministic exclusion/no-effect reason |

## Fail-closed matrix

| Trigger | Allowed outcome | Prohibited outcome | Recovery condition |
|---|---|---|---|
| No exact unresolved object | `INSUFFICIENT_CONTEXT` + open source | “Reply now” | Thread-scoped request/state verified |
| No accepted expertise coverage | `DEFER`/unsupported | General Sales imperative | Accepted Layer 3 package |
| Business subject/role conflict | Review identity/role graph | Candidate targeting any conflicted person | Conflict resolved with provenance |
| Fewer than required constraints | Diagnostic trace | Winner selected from unconstrained set | Required constraint receipts present |
| No stakes or completion | Observation/review only | Prescriptive card/action button | Both fields concrete and evidence-linked |
| Candidate set only semantic duplicates | Rebuild candidate set or explain sole option | Artificial alternative list | Material-difference test passes |
| Confidence below floor | `DEFER`, no selected candidate | Low-confidence imperative with disclaimer | New evidence raises calibrated confidence |
| Hard permission/risk failure | `BLOCKED` + rejected candidate receipt | Score override | Policy/approval state changes |
| Decision expired/superseded | No action; re-run on current state | Execute old selection | Fresh package and decision |
| Upstream connector aggregation | Suppress and split | One giant connector decision | Per-relationship BSOs/packages |
| No observable completion | No delegation/execution authority | “I’ll do it” workflow | Completion predicate specified |

## Required decision invariants

1. Elimination precedes ranking, and missing mandatory constraints is not equivalent to passing them.
2. An authoritative prescriptive decision has a state-based situation, exact loop, stakes, expiry, owner/approval and completion.
3. Priority score, urgency, expertise coverage and calibrated confidence remain separate fields.
4. Alternatives must be materially different; do-nothing/stop is a first-class candidate.
5. A one-candidate decision is allowed only when the trace proves why alternatives were unsafe/infeasible.
6. `NO_ACTION`, `DEFER`, `INSUFFICIENT_CONTEXT` and `BLOCKED` cannot be overwritten by templates.
7. LLM text cannot add facts, candidates, score, recipient, permission or action.
8. Accepted, executed, completed and outcome-verified remain distinct states outside reasoning.
9. Canonical open-loop keys and semantic candidate keys prevent duplicate decisions without hiding separate relationships.
10. Brain snapshot/version change is never evidence of decision influence; the trace names the exact consumed entry and semantic effect or an explicit no-effect reason.
11. Expert play conversion discloses steps-only eligibility, deterministic ordering, the four-play cap, skipped rule IDs and fallback source.

## Verdict

Layer 4’s core supports strong fail-closed behavior, but active adapters and projection leave exploitable gaps around it. The most dangerous loopholes are one-candidate “ranking,” score/confidence conflation, generic fallback after abstention, and prescriptive cards with missing stakes/completion. Until those paths are blocked end to end, the layer is **unsafe for broad prescriptive output** even though its internal decision maker is framework-ready.

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "../02-Customer-Expectation-and-HKS/README.md" (M3.C2.L-contract.V1.U01)
include "../03-Current-Successes-Failures-and-Expected-Behavior/README.md" (M3.C2.L-data.V0.U01)
-->
