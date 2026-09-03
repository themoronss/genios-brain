# Layer 2 — LLM Use Cases and Cost

## Decision

The proposed “about 50% LLM in Layer 2” must mean **model-assisted semantic extraction for the eligible unstructured workload**, not 50% authority over the context graph. Current traffic mix was not measured in this audit, so no honest Current whole-layer percentage can be claimed. Structured Calendar/CRM-style mappings are deterministic and should stay 0% LLM; messy email/document/chat text may use one combined model call; identity merge, correlation, fact authority, confidence, coverage, lifecycle, permissions and BSO validity remain Deterministic.

**[CODE] baseline:** `harsh/mvp@b739bd5`. **[ATLAS] baseline:** Atlas lines 310–354 and 1219–1238. **Live invocation rate and real tenant Cost are Unknown** without `llm_costs`, cache-hit and event-lane telemetry.

## Current versus Atlas versus Proposed allocation

| Component / task | Current path | Atlas policy | Proposed invocation rate | Deterministic pre-gate | Deterministic post-gate / forbidden authority | Cost control and fallback |
|---|---|---|---|---|---|---|
| Structured source mapping | `runner.py:65-78` maps fields/relations without model | Graph Builder optional, not mandatory | **0%** | Authenticated source, schema/version, dedup, tenant boundary | Mapping types, authority rank, provenance; model never rewrites system-of-record | Zero tokens; mapping failure parks/reviews |
| Unstructured relevance + extraction | Single combined call returns relevance, domains, entities, facts, commitments, questions and observations (`context/extract/extractor.py:9-64`) | Extraction may be model-assisted | **100% of truly unstructured eligible events; target roughly 40–60% of all L2 events after lane split** | Prepared/masked content, source integrity, obvious machine/structured routing, tenant scope | Evidence-span grounding, schema/range checks, authority from source; model output is candidate only | One combined call, cache, cheap bounded model; failure parks after bounded attempts |
| Relationship-role candidates | Model currently emits entity mentions/observations but no guaranteed requester/connector/target contract | Entity linking optional | Gated on multi-actor/connector ambiguity, expected **10–25% of unstructured** | Exact addresses, thread participants and known roles first | Model may propose roles with spans; cannot select target/merge identity/action | Reuse combined call fields; no second call unless offline repair cohort proves value |
| Entity identity resolution | Exact alias keys and merge proposals are deterministic | Entity Linking optional | **0% authority; optional proposal only <5%** | Exact canonical keys and collision set | No auto-merge/name-only selection from model; human/anchored receipt required | Offline queue/batch; deterministic no-merge fallback |
| Temporal/request extraction | Commitments/questions come from combined extraction | Graph Builder optional | Included in combined call for eligible text | Preserve event time, locale, timezone and evidence text | Model cannot own final due time when relative/ambiguous; range and chronology validation | No extra call; ambiguity stored, not retried into certainty |
| Correlation | Thread, anchor, domain hint and window rules (`context/correlation.py`) | **No LLM** | **0%** | Qualified evidence, role candidates, identity state | Model cannot join/split situations or choose domain authority | Deterministic replay; possible-link review instead of model call |
| Graph maintenance/current truth | Versioned writes, historical/replay and discrepancy rules | **No LLM** | **0%** | Provider/field authority and occurred-at | Model cannot supersede, resolve conflict, set graph version or permission | Transactional; no token spend |
| Situation detection/lifecycle | Correlations refresh into typed/lifecycle situations | Situation Detection **No LLM** | **0%** | Correlation membership and required context | Model cannot create lifecycle state, confidence, coverage, priority or completion | Pure deterministic recompute |
| Situation naming | Current name/type is deterministic domain/anchor derived | Optional, cosmetic | **0–10%**, presentation only after valid BSO | Valid situation, allowed facts and non-sensitive display scope | Generated label cannot alter type, target, priority or action; deterministic label always available | Cache by BSO hash; cheap short output; template fallback |
| Context validation | Current grounding/schema/fact rules are deterministic but BSO semantic validation is incomplete | **No LLM** | **0%** | Exact membership, role, visibility, source readiness | Validator alone grants/denies expertise authority | No model; explicit review codes |

## What the Current call actually does

The unstructured lane calls the configured Anthropic model (default string `claude-haiku-4-5-20251001`) only when a key/client exists; otherwise that event becomes `skipped_no_llm` (`genios_engine/platform/config.py:60-62`; `context/runner.py:79-94`). Prompt content is truncated to 8,000 characters, output allows up to 4,096 tokens, temperature is zero, SDK timeout is 60 seconds with two SDK retries, and the extractor performs one additional repair call (`context/extract/extractor.py:31-48`; `context/llm/client.py:22-64`). Temperature zero improves repeatability but is not mathematical determinism; persistence and versioning provide replay stability.

The cache key is `sha256(org_id:PROMPT_VERSION:content)` and prevents cross-tenant reuse (`context/pipeline.py:239-256`). It does **not** include the model ID, extraction schema version or masking policy. A model/config change without a prompt-version bump can therefore reuse stale output. The 8,000-character cap controls Cost but can remove the decisive late-thread request; truncation must be represented as missing context, not silently treated as full coverage.

Model relevance is stored and can rank observations, but fact confidence used by downstream gates is Deterministic by authority rank (`context/pipeline.py:57-76,258-283`). This is the correct authority boundary. The remaining risk is semantic: an evidence-grounded phrase can still be assigned to the wrong role/relationship, and current BSO validation does not require those roles.

## Cost model and accounting gaps

| Cost dimension | Current mechanism | Gap | Proposed control | Acceptance metric |
|---|---|---|---|---|
| Calls | One combined extraction result per uncached event | Repair and SDK retries can multiply physical calls | Record every underlying attempt with parent event/attempt ID | Physical calls / uncached event; p95 ≤ agreed ceiling |
| Retry ceiling | SDK `max_retries=2`, extractor second call, runner parks after 3 processing attempts | In the theoretical worst path these layers can compound to **18 HTTP attempts** across three processing attempts; semantics must be verified against SDK | One centrally budgeted attempt ladder; stop by token/latency budget | Zero retry storms; terminal park receipt after ceiling |
| Token ledger | `record_cost` writes returned input/output tokens per event (`pipeline.py:248-250`; `graph_store.py:326-349`) | Earlier failed repair/SDK attempts may be absent because only final returned result is recorded | Per-attempt token/cost ledger including failures/cache status | Ledger/provider bill variance within agreed tolerance |
| Price calculation | Code prices Haiku at `$0.80/M` input and `$4/M` output (`platform/metrics.py:30-53`) | Code price table can become stale; it is accounting config, not vendor proof | Version prices by effective date; reconcile invoice | Monthly reprice/reconciliation passes |
| Cache | Org + prompt version + content hash | Model/schema/masking policy omitted; duplicate semantic text with harmless formatting misses | Key on tenant, normalized evidence hash, model, prompt, schema, masking version | Hit rate by lane; zero stale-model reuse |
| Input budget | 8,000 characters | Character cap is not token/semantic aware; decisive tail may vanish | Thread-aware selector: latest ask + prior state + evidence spans under token budget | High-value extraction recall versus full-text labelled set |
| Output budget | Maximum 4,096 tokens | Large mixed threads may truncate; repair doubles spend | Strict compact schema, per-field caps and overflow/missing codes | Parse success ≥ target; repair rate below threshold |
| Concurrency | Batch 40, default 3 workers (`context/runner.py:26-30,161-169`) | Throughput can amplify rate-limit retries and database pressure | Tenant/global token bucket, adaptive workers and backpressure | p95 drain latency, 429 rate and queue age within SLO |
| Billing credits | One credit per ten LLM-extracted items, minimum one (`runner.py:208-224`) | Credit proxy is not actual Cost and billing failure is swallowed | Keep product credits separate from audited token spend | Credits, dollars and events reconcile independently |

For planning, expected model spend is:

`uncached_eligible_events × (mean_input_tokens × input_price + mean_output_tokens × output_price) + retry_attempt_spend`.

Do not optimize by randomly skipping half the text. Reach the Proposed ≈50% whole-layer workload through deterministic structured routing, cache reuse, semantic context selection and one combined call. Quality gates outrank the percentage: a Theresa/Boardy/high-value message must not be excluded merely to meet a budget.

## Exit gate

Promote this allocation only after a fixed multilingual/HKS corpus and a Live shadow sample show: role/request/commitment recall and precision at agreed thresholds; zero ungrounded identity creation; zero model-owned route, score, permission or final action; zero high-value silent truncation; cache isolation across tenants/models; full retry token accounting; bounded p95 latency and spend; and no regression against the 214-Tested deterministic context suite. Until then, percentages are design targets—not proof that Layer 2 is intelligent or cost-efficient in production.

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "../01-Architecture-and-Atlas-Delta/README.md" (M2.C2.L-contract.V0.U01)
include "../03-Current-Successes-Failures-and-Expected-Behavior/README.md" (M2.C2.L-data.V0.U01)
-->
