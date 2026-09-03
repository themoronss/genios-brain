# Layer 7 Learning — LLM Use Cases and Cost

## Decision

Layer 7 should be approximately **85–95% deterministic by authority and 5–15% LLM-assisted by workload**. The model may interpret messy human language or draft a review summary; it must never decide evidence count, causal eligibility, confidence, target brain, permitted use, promotion, expiry, rollback, or whether an outcome is proven.

This differs from the requested “50% LLM” planning idea: a whole-layer percentage hides the dangerous boundary. Learning has high-judgment inputs but low tolerance for probabilistic authority. LLM usage should be measured as eligible-event invocation rate, not as ownership of the layer.

## Current versus Atlas versus Proposed allocation

| Component | Current path at `b739bd5` | Atlas intent | Proposed LLM use | Proposed invocation rate | Deterministic pre-gate | Deterministic post-gate / forbidden authority | Token ceiling and Cost control |
|---|---|---|---|---:|---|---|---|
| Batch selection | Tenant/time-bounded database loaders | Bounded evidence cohort | None | 0% | Tenant, window, table health, dedup | Model cannot choose rows or cross tenant | Zero model Cost |
| Structured execution outcome | Typed labels and outcome rows | Learn from verified result | None | 0% | Execution ID, terminal state, evidence/time window | Model cannot turn `completed_unproven` into success | Zero model Cost |
| Delivery facts | Receipt-backed loader | Separate transport from recommendation quality | None | 0% | Provider receipt, message/execution identity | Model cannot infer impression, silence, or engagement | Zero model Cost |
| Card feedback verdict | API persists structured cause/reason/revisions, while learning store expects another optional seam | Interpret explicit verdict safely | Parse only free-text detail when structured reason is insufficient | 10–30% of feedback events | Valid audited card, actor, JSON size, known action, raw text retained | Schema validation, scope ceiling, confidence gate; model cannot promote | 300–700 input, 80–180 output tokens; cache by verdict revision |
| Preference extraction | Canonical unit returns `[]` | Learn explicit bounded preference | Extract candidate subject, behavior, scope, duration, exceptions | 5–15% of feedback events | Must be explicit first-person instruction; policy and identity available | User confirmation for broad scope; model cannot override policy | One call only on candidate text; no retry on ambiguity |
| Temporary directive | Canonical unit returns `[]` | Create expiring Runtime memory | Parse temporal phrase and candidate instruction | 3–10% of feedback events | Actor authority, target, source, and maximum TTL policy | Deterministic time parser/TTL cap; no missing-TTL publish | 250–600 input, <=120 output; reuse preference parse response |
| Feedback summarization | No canonical feedback-learning output | Explain why repeated corrections matter | Summarize already-reconciled observations for reviewer | 1 call per review candidate, not per event | Candidate passed support/privacy gates | Summary cannot change evidence IDs, counts, confidence, or target | 600–1,500 input, 150–300 output; batch evidence references |
| Outcome analysis | Deterministic unit | Compare play/capability result | None by default; optional anomaly narrative after calculation | 0% authority; <2% reports | Canonical outcome and aggregation complete | Narrative numbers must round-trip to computed fields | Small review-only call; never on weekly hot path |
| Pattern learning | Deterministic support/day/entity calculation | Discover repeated enterprise patterns | Candidate semantic clustering only for unstructured facts | 5–20% of unstructured eligible facts | Tenant, use class, k floor, embeddings/cache, schema | Recount support deterministically; model cannot declare independence | Batch 20–50 facts; 1,500–4,000 input, <=400 output |
| Behavior evolution | Cohort candidate currently empty | Stable bounded behavior | Label/describe a deterministic cohort after it qualifies | 0–5% of qualified cohorts | Identity, role, situation, repetitions, drift window | Model cannot select cohort members or publish Behavior Brain | One cached label per cohort/version |
| Adaptive evolution | Cohort candidate currently empty | Short-horizon play/timing efficacy | Optional explanation of deterministic delta | 0–5% of promoted candidates | Exposure, action, outcome, decay, conflict, TTL | Model cannot choose delta, confidence, TTL, or active version | Explanation generated only when rendered/reviewed |
| Recommendation learning | Deterministic outcome minus attention cost | Compare play efficacy | None | 0% | Canonical exposure/action/outcome and cost facts | Model cannot calculate efficacy or rank | Zero model Cost |
| Performance optimization | Deterministic delivery/failure/engagement calculation | Improve operational performance | Optional root-cause classification for unknown provider errors | 1–10% of unclassified failures | Error payload redacted, provider/status known | Classification cannot mark user rejection or success | 300–900 input, <=100 output; cache on error signature |
| Knowledge evolution | Deterministic sustained-poor-outcome suggestion | Human-review Expert improvement | Draft reviewer brief and possible corpus question | 100% of qualified review suggestions, very low volume | Deterministic qualification, evidence/use restrictions | Never mutate Expert Brain; reviewer owns disposition | 1,000–3,000 input, 300–600 output; hard daily queue cap |
| Validation | Counts observations/days/entities/confidence/noise/conflict/value | Gate every proposal | None | 0% | Typed LearningObject and policy version | Model cannot pass/fail a gate | Zero model Cost |
| Governance/publish/rollback | Defective deterministic seams: Organization approval records `promoted` without publishing; policy reload drops both block lists; Recommendation Learning may emit durable Adaptive although Adaptive cannot carry expiry | Controlled promotion with lossless policy, bounded lifecycle, version and rollback | Optional human-readable change note only after deterministic success | 0% authority; one note per actually published version | Published brain/version receipt, stored-vs-loaded policy equality, target, predecessor, lifecycle/TTL where valid | Model cannot approve, activate, repair missing publication/policy fields, invent Adaptive expiry, supersede, or roll back | Generate note asynchronously; publication and recovery cannot depend on it |
| Learning health explanation | No complete customer-facing reconciliation | Expose learning quality and drift | Convert computed health receipt into plain-language explanation | On demand only | Metrics already computed and authorized | Model cannot invent missing metrics or call “zero data” healthy | Cache by run/metric fingerprint; <=400 output tokens |

## Why the Current LLM footprint is not the main failure

`feedback/units.py` explicitly states that units calculate and no LLM has scoring or target authority. That is a sound safety boundary. The product also has LLM-backed intelligence query and drafting surfaces in `api/intelligence_routes.py`, but those calls are not proof that Layer 7 learns. The failure is missing canonical inputs, empty evolution units, fragmented outcomes, no publish-to-compiler-to-better-outcome receipt, and three deterministic governance defects—not insufficient model usage.

Adding a model directly to empty units would produce eloquent ungrounded preferences. First wire typed evidence; then use a model narrowly where language ambiguity is irreducible.

## Deterministic defects no model may repair

1. **Organization approval is not publication.** `api/learning_routes.py:119-143` changes the review row to `promoted` and appends a transition, but it does not call the governed publisher or create `learned_brain_entries`. Until an idempotent transaction creates the brain/version and consumption receipts, the state is `approved_unpublished`; a model-written summary cannot promote it.
2. **Loaded policy is weaker than stored policy.** `feedback/orchestrator.py:28-46` omits `blocked_targets` and `blocked_subject_prefixes` when reconstructing `LearningPolicy`. Promotion requires byte-equivalent **stored-vs-loaded policy equality** and must fail `policy_incomplete` when authority-bearing fields are missing; a model cannot infer the lost prohibitions.
3. **Adaptive lifecycle is unrepresentable.** Recommendation Learning can emit an Adaptive proposal, but the contract permits `expires_at` only for Runtime: **Adaptive cannot carry expiry**. Until a ratified TTL/decay representation exists, non-expiring Adaptive publication is rejected or the temporary instruction becomes a bounded Runtime lease; prose cannot manufacture lifecycle authority.

Accordingly, **no LLM is eligible to repair these semantics**. Review-to-publish, policy reconstruction, target eligibility, expiry/decay, version activation, rollback, and semantic consumption stay model-free. Each repair needs a **model-disabled semantic-equivalence replay**: the same evidence and policy must produce the same publish/defer/reject decision, active version, expiry behavior, and downstream semantic effect with model calls disabled; enabling an optional explanation may change wording only.

## Proposed call pipeline

```text
raw human text
  -> deterministic eligibility and redaction
  -> cached LLM candidate parse (strict JSON)
  -> deterministic schema, identity, role, scope, time and policy checks
  -> observation / confirmation / review (never direct promotion)
  -> support and causal reconciliation
  -> deterministic validation and governance
  -> versioned publish and consumption receipt
```

## Cost model

For component `i`:

```text
monthly_cost_i = eligible_events_i
               × invocation_rate_i
               × (input_tokens_i × input_price + output_tokens_i × output_price)
               × (1 - cache_hit_rate_i)
               + retry_cost_i
```

Track actual provider/model prices in configuration at runtime; do not freeze speculative dollar numbers into policy. The budget controller should expose calls, input/output tokens, cache hits, retry rate, latency p50/p95, parsing failures, and dollars per accepted learning proposal.

| Cost guard | Required policy |
|---|---|
| Cache key | Tenant + evidence hash + verdict revision + prompt/schema version + model version |
| Retry ceiling | One repair attempt only for syntactically invalid JSON; zero retry for ambiguous meaning |
| Batch strategy | Cluster only already-authorized facts; never batch across tenants or visibility classes |
| Daily cap | Separate learning-assist cap from interactive intelligence/drafting credits |
| Degradation | Preserve raw event and queue review; deterministic learning continues without LLM |
| Model routing | Small structured model for parsing; stronger model only for rare knowledge-review briefs |
| Observability | Cost and latency attached to proposal/run; no invisible background spend |
| ROI denominator | Cost per reviewed proposal, promoted version, changed decision, and proven outcome—not per token alone |

## Exit gate

LLM assistance is production-eligible only when golden replays prove: identical evidence and prompt version produce schema-valid bounded candidates; ambiguity abstains; forbidden evidence is never sent; deterministic gates reject scope/policy violations; model outage does not corrupt or block deterministic outcome accounting; no model response can activate a brain version by itself; and the model-disabled semantic-equivalence replay preserves every authoritative decision while optional model output changes explanation text only.

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "../01-Architecture-and-Atlas-Delta/README.md" (M4.C3.L-contract.V0.U01)
include "../03-Current-Successes-Failures-and-Expected-Behavior/README.md" (M4.C3.L-data.V0.U01)
-->
