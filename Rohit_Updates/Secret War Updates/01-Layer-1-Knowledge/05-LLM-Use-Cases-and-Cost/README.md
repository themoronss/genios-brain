# Layer 1 — Knowledge: LLM Use Cases and Cost

## Decision

The requested “80% LLM in Layer 1” is reasonable only if it means **up to roughly 80% of eligible messy, unstructured items may receive model-assisted interpretation**. It must not mean that an LLM owns 80% of Layer 1 authority. Provenance, source identity, permissions, deduplication, cursor movement, schema validation, destructive retention, lifecycle, numeric importance, qualification thresholds and publication remain Deterministic.

The Proposed design therefore measures model use by task and eligible event, not by a vague whole-layer percentage. Structured CRM/calendar/database events should normally use 0% generative extraction; ambiguous human language, scans and relationship phrases can use models after deterministic gates.

## Current versus Atlas versus Proposed allocation

| Task | Current implementation | Atlas policy | Proposed LLM rate | Deterministic pre-gate | Deterministic post-gate | Forbidden model authority |
|---|---|---|---:|---|---|---|
| Connector fetch/auth | No LLM | No model required | 0% | Tenant/auth/source/cursor validation | Page receipt, retry, dedup, watermark commit | Source permission, completeness or cursor |
| OCR | Optional Tesseract, default off (`platform/config.py:82-84`) | Traditional OCR, no LLM | 0% generative; OCR engine as needed | MIME, malware, size, page checks | Confidence floor, page/offset receipt | Guess unreadable text as fact |
| Speech-to-text | Not found as a complete L1 path | Yes for transcription | 100% of supported audio after consent | Format, duration, language, visibility | timestamps, speaker uncertainty, transcript quality | Speaker identity without anchor |
| HTML/text normalization | Deterministic native extraction and masking | Deterministic | 0% | MIME and encoding | transformation map, PII/quote checks | Rewrite source meaning |
| Entity mention extraction | Deferred to L2 combined model for unstructured items | Rules first; LLM fallback | 60–85% of messy unstructured events; 0% structured | email/header/source anchors, allowlisted schema | evidence-span grounding, canonical identity proposal, conflict check | Merge/identity authority |
| Relationship/role extraction | Mostly deferred to L2; L1 keeps sender/recipients/thread raw fields | Optional for complex prose | 50–80% where business roles are expressed in prose | deterministic participant/thread graph | role schema, source-span evidence, unresolved-role state | Choose requester/owner/subject without evidence |
| Embeddings | No complete general L1 embedding pipeline demonstrated | Yes for semantic retrieval only | 100% only for approved retrievable content | permitted use, visibility, chunk and retention policy | vector version, tenant partition, deletion propagation | Relevance, truth, permission or decision |
| Junk/relevance triage | L1 `LLMRelevanceClassifier` runs when `l1_llm_gate=true` and Anthropic key exists; default flag true (`platform/config.py:76-81`) | Mostly rules, model fallback | 10–35% after deterministic obvious-noise/known-value gates | whitelist, attachment, source label, HKS protection | calibrated keep/park/drop, quarantine, audit receipt | Irrecoverable drop of ambiguous/high-value item |
| Signal detection | L2 combined extraction currently finds commitments/questions/observations | Model sometimes | 60–85% unstructured, 0% mapped structured | source completeness, content readiness | typed schema, verbatim evidence, actor/target validation | Manufacture request, promise, deadline |
| Domain candidates | Cheap L1 hints; richer model domains in L2 | Domain mapping required; model only where ambiguous | 20–50% ambiguous text | source and tenant scope | allowlisted domains, multi-domain output, coverage check | Final domain routing when unsupported |
| Importance | Processing triage regex only; no Atlas importance formula | No LLM | 0% | Required source/entity/authority inputs | basis-point formula and reason codes | Business priority/confidence |
| Qualification/publication | Gate emits keep/park/drop and `GatedEvent` | Deterministic threshold and publisher | 0% final authority | schema, permission, evidence, coverage | immutable receipt and lifecycle event | Final publish/permission decision |

## Current call and cost shape

| Current control | Code evidence | Benefit | Gap / Cost risk |
|---|---|---|---|
| L1 relevance batch | Up to 12 emails per batch, ~600 prepared characters each (`capture/gate/relevance.py:120-204`) | Converts roughly N calls into N/12 for a page | Cache is in-memory for the run; prompt/model/version is not a durable decision key |
| Single fallback call | Up to 1,500 prepared characters, 120 output tokens (`capture/gate/relevance.py:211-227`) | Bounded output and fail-open on error | A correct API response with wrong semantics can still hard-drop |
| Known sender bypass | Known sender returns keep without model (`capture/gate/relevance.py:211-216`) | No spend for trusted correspondence | “Known” quality/tenant scope must itself be trustworthy |
| Cost ledger | Gate can bind to `GraphStore.record_cost`; calls store input/output tokens and purpose | Current model spend becomes measurable | When org/store binding is absent, comments acknowledge spend can be invisible (`platform/wiring.py:239-258`) |
| Per-org call breaker | New sync refuses to start at default 20,000 daily recorded calls (`api/routes.py:1088-1139`) | Stops runaway reprocessing | Very high count cap is not a value/cost budget and fails open if cost query fails |
| Platform USD cap | `daily_llm_usd_cap` defaults to $25 (`platform/config.py:51-53`) | Global control exists for intelligence paths | Evidence that background capture uses the same USD cap is not established |
| Price calculation | Haiku ledger rate is configured as $0.80/M input and $4/M output tokens (`platform/metrics.py:30-53`) | One cost definition across reporting | Model-provider prices can change; actual invoice reconciliation is still required |
| L2 duplicate semantic call | Every unstructured kept event can also receive one combined L2 extraction call, with one repair retry and input capped to 8,000 chars (`context/extract/extractor.py:31-64`) | Rich typed facts from prose | L1 junk judgment plus L2 extraction can read the same email twice; cost and contradictory relevance rise |

## Proposed call topology

1. **Deterministic source stage:** authenticate, derive visibility, verify content, dedup and map structured events.
2. **Zero-cost certain lanes:** mapped structured data goes directly to schema validation; certain junk follows governed quarantine/drop; known direct correspondence bypasses junk-model classification.
3. **One interpretation call for eligible prose:** produce relevance disposition, signal atoms, role candidates, domain candidates and evidence spans in a single versioned response. This avoids separate L1 and L2 semantic reads of the same content.
4. **Deterministic validator:** reject fields without source spans, validate actor/role/time/domain, compute authority and mark conflicts/missing context.
5. **Deterministic publication:** keep, park or publish based on evidence, permission, coverage and calibrated policy. Model score can rank review; it cannot authorize destruction or publication alone.

This topology preserves the Atlas boundary semantically even if the physical model worker is shared with Layer 2. Ownership is decided by the artifact produced and validator applied, not by which Python package holds the API client.

## Cost model

Do not forecast from “80%” alone. For each tenant/day record:

```text
eligible_events = unstructured_kept_after_deterministic_gates
model_calls = ceil(batch_gate_items / batch_size) + uncached_interpretation_items + retries
token_cost_usd = input_tokens × input_rate + output_tokens × output_rate
cost_per_qualified_signal = total_capture_model_cost / published_qualified_signals
cost_per_trusted_action = total_capture_model_cost / actions_with_verified_completion
```

| Cost lever | Proposed policy | Quality guard |
|---|---|---|
| Structured bypass | Never send mapped CRM/calendar/DB fields to a model | Mapping coverage/version alert prevents silent field loss |
| Evidence-hash cache | Key by org, evidence hash, prompt, model, schema and policy versions | Never share cache across tenant/visibility boundary |
| Batch triage | Batch only independent items and validate exact cardinality/index | Any mismatch falls back; it never applies shifted verdicts |
| Progressive depth | Header/snippet triage, fetch full body only when retained | Protected high-value/attachment cases cannot be snippet-dropped |
| Small-model routing | Cheap model for extraction; stronger model only for low-confidence complex role text | Escalation is bounded and measured against replay quality |
| Retry ceiling | One semantic repair only; infrastructure retries bounded | Failure parks item; it does not create a fact |
| Backfill budget | Separate onboarding allowance from steady-state daily budget | Pausing sets coverage stale; no negative inference during pause |
| Retention | Store parsed candidates and evidence receipt, not unlimited raw prompts | Permission/deletion propagation remains enforceable |

## Required metrics and exit gate

| Metric | Required cut | Why |
|---|---|---|
| High-value signal recall | By source, role, language and HKS | Protects against cheap but destructive filtering |
| Irrecoverable false drops | Zero for HKS replay set | A lost investor/customer message cannot be corrected downstream |
| Model-assisted eligible rate | Reported by task, not whole layer | Makes the “80%” assumption falsifiable |
| Grounded field rate | Actor/request/role/deadline each separately | Prevents JSON validity being mistaken for truth |
| Calls and tokens | Per 1,000 scanned, eligible, parked and published items | Shows where cost is actually incurred |
| Cache hit and retry rate | By prompt/model version | Detects churn and unstable output |
| Cost per trusted action | Includes only verified completion/outcome | Connects infrastructure spend to customer value |
| p95 capture latency | Per source and model lane | Keeps proactive intelligence timely |

**Exit gate:** the Proposed allocation becomes authoritative only when a fixed labelled corpus and live shadow sample show that the single-call topology matches or improves recall/role fidelity, produces zero HKS irreversible loss, stays within per-tenant latency/spend budgets, and the deterministic validator rejects every ungrounded permission/identity/deadline attempt. Until then, use it in shadow or recoverable park mode.

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "../01-Architecture-and-Atlas-Delta/README.md" (M2.C1.L-contract.V0.U01)
include "../03-Current-Successes-Failures-and-Expected-Behavior/README.md" (M2.C1.L-data.V0.U01)
-->
