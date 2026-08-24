# Layer Numbering and Semantic Map

## Decision

Secret War Updates uses the current code package numbering as its reader-facing sequence. Atlas labels remain visible beside it.

| Secret War layer | Current code package | Atlas label | Single responsibility |
|---:|---|---|---|
| Layer 1 | `capture/` | Layer 1 · Knowledge | Acquire, normalize, qualify, retain, and preserve source evidence |
| Layer 2 | `context/` | Layer 2 · Context Intelligence | Build the roleful, temporal, evidence-backed business situation |
| Layer 3 | `packs/` plus Domain Expertise corpus | Layer 3 · Domain Expertise | Compile applicable capability knowledge and four-brain context without choosing an action |
| Layer 4 | `reason/` | Layer 4 · Reasoning | Generate, reject, compare, rank, or abstain among defensible actions |
| Layer 5 | `executive/` | Layer 5 · Executive | Convert a decision into accountable work with lifecycle and outcome semantics |
| Layer 6 | `deliver/` | Atlas 5.2 · Delivery | Materialize approved intelligence across cards, channels, APIs, digests, and agents |
| Layer 7 | `feedback/` | Atlas 6 · Learning | Learn from verified outcomes through governed, reversible updates |

Therefore:

- **Layer 6** in this update means current code Delivery, explicitly annotated **Atlas 5.2**.
- **Layer 7** means current code Learning, explicitly annotated **Atlas 6**.
- An unqualified “L5” or “L6” is avoided in evidence tables; the semantic name is always included.

## Why the numbering differs

The Atlas inserts Delivery as “5.2” after Executive and calls Learning “6.” The current repository turns Delivery into a full sixth package and Learning into the seventh. This is a numbering translation, not evidence that either design is implemented correctly.

The current code map also separates cross-cutting packages:

| Cross-cutting package | Ownership |
|---|---|
| `contracts/` | Typed boundaries shared across layers |
| `platform/` | Configuration, database, crypto, wiring, and composition root |
| `api/` | Transport surface; it must not silently become business authority |
| Governance | Identity, policy, visibility, tenancy, audit, retention, approvals, budgets, rollback |

Cross-cutting code is audited under the layer whose decision it constrains. For example, a visibility type in `contracts/` is reported in Layer 1 when ingest must preserve it, Layer 2 when correlation must narrow it, and Layer 6 when delivery must enforce it.

## Boundary contract

| From | To | Required handoff | Forbidden shortcut |
|---|---|---|---|
| Layer 1 | Layer 2 | Qualified signal plus provenance, actor, visibility, freshness | Treating transport sender as business subject |
| Layer 2 | Layer 3 | Bounded BusinessSituation with roles, current state, missing context | Passing a person-wide fact dump |
| Layer 3 | Layer 4 | Versioned ExpertisePackage pinned to brain snapshots | Selecting the final action inside expertise |
| Layer 4 | Layer 5 | Decision with candidates, rejections, confidence, trace, abstention | Converting priority score into “confidence” |
| Layer 5 | Layer 6 | Valid ExecutionObject plus delivery intent and lifecycle state | Card click represented as business completion |
| Layer 6 | Layer 7 | DeliveryResult and receipt-backed engagement | Inferring “ignored” from nondelivery |
| Layer 7 | Layer 3/runtime | Governed versioned updates with evidence and rollback | Model-written expert policy or silent promotion |

## Architectural contradictions that remain open

### Executive versus Delivery ownership

Atlas expects Executive to carry semantic `audience_intent`, while Atlas 5.2 resolves concrete recipient, channel, and timing. Current `docs/LAYER_MAP.md` and `executive/communication.py` move concrete who/channel judgment into Executive and make Delivery execute the frozen plan.

This update will not silently select one. Each Layer 5 and Layer 6 report must show:

1. Atlas expectation.
2. Current code behavior.
3. Risk created by the difference.
4. Ratification decision needed.

### LLM placement

Atlas permits model assistance at selected extraction, consultation, drafting, and feedback-parsing points. The current layer map says the single extraction model call lives in Layer 2. The invariant used here is narrower and stable:

> A model may help interpret unstructured content or render already-decided meaning. It may not manufacture evidence, produce authority, choose permissions, compute governed numbers, select recipients, or silently choose the final action.

Layer-specific documents will measure current and proposed calls rather than assigning a vague percentage to an entire layer.

### Confidence shape

Atlas contains scalar integer basis-point contracts and also presents multi-component confidence. Current UI paths sometimes display a normalized priority score as confidence. The audit will separate:

- evidence confidence;
- identity confidence;
- context completeness;
- expertise coverage;
- rule applicability;
- freshness and conflict;
- decision confidence;
- urgency and priority.

No layer may rename one as another for presentation convenience.

## Reader rule

When a report says “present in Layer 3,” it means the artifact belongs to the Layer 3 responsibility. It does not imply it is wired into Layer 4, live in Layer 6, or outcome-proven by Layer 7. Those are separate coverage states.


<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "01-Evidence-Authority-and-Claim-Classes.md" (M1.C1.L-contract.V0.U01)
-->
