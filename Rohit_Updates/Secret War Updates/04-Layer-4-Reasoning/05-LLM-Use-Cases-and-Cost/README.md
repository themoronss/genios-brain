# Layer 4 — LLM Use Cases and Cost

**Evidence baseline:** `harsh/mvp@b739bd5ca682d09550acc400ed2892c38c8518f8`. The Atlas (`GeniOS-System-Design-Atlas.md:1593-1945`) permits model consultation in exactly three reasoning conditions: low confidence, ambiguous situation and explanation. The LLM is never the decider. All candidates, hard constraints, scoring, selection, confidence authority and abstention remain deterministic.

## Blunt recommendation

Do not put an LLM in the routine winner-selection loop to make cards sound smarter. Current output is shallow because the active path supplies one generic play, omits important reasoning units and loses stakes/completion at projection. A model cannot safely invent those missing semantics. Keep normal decisions model-free; invoke a model only for bounded ambiguity consultation or post-decision explanation, and treat every model output as untrusted until deterministic checks accept it.

The current code already demonstrates the right authority boundary in `reason/intelligence.py:198-409`: action and confidence are fixed from audited signals, explanation is optional, invention is rejected, and missing grounding fails closed. Preserve this design while improving the candidate pipeline.

## Current, Atlas, and Proposed allocation

| Task | Current behavior | Atlas allowance | Proposed LLM role | Deterministic control | Eligible rate | Cost posture |
|---|---|---|---|---|---:|---|
| Hard constraint evaluation | Reasoning units/decision maker | Never model authority | None | Typed policy, permission, feasibility gates | 0% | Compute only |
| Candidate scoring/ranking | `decision_maker.py` deterministic ordering | Never model authority | None | Versioned scoring and total-order tie-break | 0% | Compute only |
| Final selection/outcome | Confidence floor and typed outcomes | Never model authority | None | Winner or `NO_ACTION`/`DEFER`/`BLOCKED` | 0% | Compute only |
| Confidence value | Central authority in decision maker | Never model authority | None | Calibrated features and floors | 0% | Compute only |
| Low-confidence consultation | Core can defer | Allowed | Suggest missing questions/evidence or candidate hypotheses, not a winner | Output re-enters schema, evidence and constraint validation; default remains defer | 2–8% of decisions | Strict budget; one call maximum |
| Ambiguous-situation consultation | Upstream ambiguity often yields generic fallback | Allowed | Identify plausible interpretations and discriminating evidence | Cannot change role/domain/state; each interpretation labelled hypothetical | 1–5% | One compact evidence bundle |
| Candidate wording/normalization | Templates are generic | Not needed for authority | Optionally turn a fully specified structured action into concise wording | Recipient/action/timing/completion frozen; diff validator | 0–20% of displayed accepted decisions | Small model, template fallback |
| Decision explanation | `reason/intelligence.py` optional bounded explanation | Allowed | Explain why selected, why alternatives rejected, what changes decision | Only quote/compose trace fields; no new fact/action/score | 5–25% on demand | Generate on open, not precompute all |
| Alternative invention | `AlternativeUnit` exists but often unscheduled | Model may consult only under ambiguity/low confidence | Propose hypotheses for deterministic candidate builder | Must map to accepted Layer 3 playbook and pass hard gates; otherwise discarded | Exceptional | Strong model only after deterministic candidate shortage |
| Stakes/completion creation | Projection currently marks them missing | Model must not fabricate business truth | No authority; may render already-structured fields | Missing stays missing and blocks prescription | 0% authority | No call until fields exist |
| Final card urgency/confidence | Score/confidence currently conflated in API | Never model authority | None | Separate typed priority/urgency/confidence/coverage | 0% | Compute only |

## Deterministic consultation protocol

| Phase | Input allowed | Model may return | Model may not return | Post-gate |
|---|---|---|---|---|
| Eligibility | Decision trace with low-confidence/ambiguity reason | Nothing; script decides whether to call | Self-trigger | Threshold, privacy, tenant and budget gate |
| Context packing | Minimum source receipts + accepted expertise + candidate summaries | Nothing | Unbounded inbox/person history | Purpose/visibility and token cap |
| Consultation | Schema-bound hypotheses, missing evidence, explanation spans | Candidate hypothesis ids, questions, cited receipt ids | Permission, recipient identity, invented fact, final winner | JSON/schema and citation validation |
| Candidate recovery | Accepted playbook ids and candidate builder inputs | Suggested mapping/hypothesis only | Free-text action entering decision directly | Deterministic construction + constraints + dedup |
| Re-reason | Original plus newly verified evidence only | Nothing | Model score/confidence | Full unit DAG and decision maker rerun |
| Explanation | Frozen selected/rejected candidates and trace | Concise customer explanation | New candidate, changed score/action or unsupported claim | Exact-field and grounded-span checks |

If consultation does not produce verified new evidence or a candidate that maps to accepted expertise, the outcome remains `DEFER`/`INSUFFICIENT_CONTEXT`. The system must not repeatedly call the model until it manufactures a winner.

## Cost model

For each eligible call:

`call_cost = input_tokens × input_rate + output_tokens × output_rate + retry_tokens × rate + latency_cost + review_cost`.

For the product:

`monthly_cost = eligible_decisions × call_rate × call_cost`, segmented by consultation versus explanation. Cost must be reported per **accepted decision improvement**, not per generated paragraph.

| Cost control | Implementation | Safety/quality benefit | Metric |
|---|---|---|---|
| Deterministic eligibility gate | Call only on typed low-confidence/ambiguity/explanation demand | Prevents model becoming default reasoner | Calls / total decisions by reason |
| On-demand explanation | Generate when user opens/asks, not for every card | Avoids spending on unseen cards | Explanation view-to-call ratio |
| Evidence-hash cache | Tenant + visibility + package + decision + prompt/model version | Reuses identical safe explanation without cross-tenant leak | Cache hit and invalidation rate |
| Minimal context pack | Only receipts referenced by decision | Reduces token cost and irrelevant leakage | Input tokens per call |
| Cheap-first routing | Small model for structured explanation; stronger only for approved ambiguity | Reserves expensive reasoning for hard cases | Escalation rate and measured lift |
| One-call/one-repair ceiling | One primary call, at most one schema repair | Prevents runaway “ask until action” | Retry count and fail-closed rate |
| Template fallback | Deterministic explanation when model unavailable | Availability without authority drift | Fallback correctness rate |
| No speculative precompute | Do not call for suppressed/deferred cards unless consultation is explicitly useful | Avoids cost on low-value work | Spend per acted-on decision |

## Forbidden LLM authority

The model may never choose or alter: business subject, recipient, domain, capability, policy, permission, visibility, candidate eligibility, score, confidence, urgency, selected action, approval requirement, completion event or outcome. It may not turn “unknown” into a plausible fact. It may not convert an abstention into advice. Its prose cannot be the only location where stakes or completion exist; those must be typed and evidence-backed first.

## Proposed operating targets

| Path | LLM call target | Deterministic share | Exit condition |
|---|---:|---:|---|
| Normal supported decision | **0%** | **100%** | Multiple typed candidates and all required fields present |
| Low-confidence consultation | ≤8% of total decisions | 100% final authority | Measurable reduction in correctable defers without more false prescriptions |
| Ambiguity consultation | ≤5% | 100% final authority | Hypothesis accuracy and evidence acquisition measured |
| Explanation | On-demand, initially ≤25% displayed decisions | 100% frozen decision | Grounding rejection rate near zero and user comprehension improves |
| Final ranking/selection | **0%** | **100%** | Permanent invariant |

## Exit gate

Layer 4’s LLM use is acceptable only when every call has a typed eligibility reason, tenant-scoped evidence-hash cache key, fixed token/retry ceiling, visibility-safe context, schema/citation validation and a recorded fallback; model text cannot change the decision object; consultation that adds no verified evidence remains defer; and A/B evaluation shows improved comprehension or correct evidence acquisition without increasing unsupported prescriptions. Cost optimization is subordinate to this authority boundary.

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "../01-Architecture-and-Atlas-Delta/README.md" (M3.C2.L-contract.V0.U01)
include "../03-Current-Successes-Failures-and-Expected-Behavior/README.md" (M3.C2.L-data.V0.U01)
-->
