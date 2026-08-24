# Layer 3 — LLM Use Cases and Cost

**Baseline:** `harsh/mvp@b739bd5ca682d09550acc400ed2892c38c8518f8`. The Atlas contract at `GeniOS-System-Design-Atlas.md:1262-1592` makes Layer 3 runtime compilation deterministic and replayable. An LLM may help humans author expertise offline; it must not decide which policy, permission, capability or playbook applies at runtime.

## Blunt recommendation

Do **not** solve shallow Domain Expertise by inserting a large model into every compile. The missing quality is mainly accepted knowledge, correct routing and live authority—not prose generation. Runtime Layer 3 should remain approximately **0% LLM authority and 100% deterministic compilation**. Model use belongs primarily in an offline authoring/review pipeline and, if later approved, a quarantined consultation path that can propose evidence-linked candidates but cannot enter an authoritative package without deterministic validation or human acceptance.

The user’s layer percentages are useful workload hypotheses, not permission percentages. “20% LLM” can mean 20% of authoring tasks receive model assistance; it never means the model owns 20% of permissions or business truth.

## Current, Atlas, and Proposed use

| Task | Current at pinned commit | Atlas rule | Proposed LLM role | Deterministic control | Runtime eligibility | Cost posture |
|---|---|---|---|---|---:|---|
| Resolve situation → capability | `DomainCompiler` uses generated registry/resolver | Deterministic | None | Exact accepted route, version and dependency closure | 0% | Near-zero marginal model cost |
| Retrieve Expert artifacts | Catalogue/retriever selects authored corpus | Deterministic | None | Content hashes, visibility, acceptance status | 0% | Cache/process cost only |
| Resolve four brains | `runtime_brains.py` applies category precedence | Deterministic | None | Organization → Expert permissions; Adaptive → Organization → Behavior → Expert preferences | 0% | Database read; snapshot cacheable |
| Build evidence receipt | Compiler collects source-linked requirements | Deterministic | None | Provenance, freshness, purpose and visibility checks | 0% | Linear in selected evidence |
| Build/publish package | Typed builder and snapshot hash | Deterministic and replayable | None | Schema + byte-stable canonicalization | 0% | Small serialization/storage cost |
| Draft a capability file | Human-authored today; many stubs remain | LLM allowed outside runtime authoring boundary | Propose object/rule/playbook/failure-pattern draft from approved sources | Schema, citations, contradiction scan, human expert review | Offline only | Batch with cheap model; no customer-path latency |
| Convert source material into rule candidates | No proved automated accepted pipeline | Offline assistance allowed | Extract candidate constraints and counterexamples | Every claim must cite source span and remain `draft` | Offline only | Cache by source hash + prompt/model version |
| Generate adversarial scenarios | Manual/tests | Offline assistance allowed | Propose edge cases and mutations | Deterministic fixtures and expected outputs authored/reviewed | Offline only | High leverage, low frequency |
| Detect corpus duplicates/contradictions | Validator catches structural issues, not all semantic equivalence | Offline assistance allowed | Suggest semantic clusters/conflicts | Human confirmation; normalized conflict keys; no automatic deletion | Offline only | Embedding/model batch, amortized per corpus revision |
| Suggest route for unseen situation | Current route gaps remain | Runtime compiler must not guess | Authoring-queue recommendation only | Production returns unsupported; reviewer accepts route/version | 0% authoritative | Async queue, capped per unique situation hash |
| Explain why package abstained | Package has structured reasons | Explanation may be downstream, not compiler authority | Optional text rendering outside package truth | Text may quote only receipt fields and cannot alter status | At most low-confidence UI request | Small model; deterministic template fallback |

## Why “LLM everywhere” would reduce intelligence

An LLM can make a generic rule sound senior without adding missing domain coverage. It can also smooth over the exact signals that must remain visible: unsupported domain, stale policy, wrong relationship role, conflicting permission, stub capability or missing completion evidence. The result would be fluent false certainty and loss of replayability.

The compiler currently has valuable hard guarantees: selected entries carry versions/hashes; visibility is narrowed; learned brains cannot grant permission; and the combined brain snapshot can be reproduced (`brain_resolver.py:20-75`, `runtime_brains.py:136-250`). A model-generated runtime merge would weaken all four unless its output were treated only as an untrusted candidate and revalidated against the same invariants.

## Proposed authoring pipeline

| Stage | LLM work | Required input | Deterministic pre-gate | Deterministic post-gate | Promotion owner |
|---|---|---|---|---|---|
| Source intake | Summarize/extract candidate expertise | Licensed/approved expert source with provenance | Source hash, permission, domain scope | Every statement cites source span | Corpus editor |
| Draft | Produce schema-shaped capability/object/rule/playbook | Accepted template and existing dependency graph | No sensitive cross-tenant context | YAML/schema, ids, enum and dependency validation | Domain expert |
| Challenge | Generate failure examples and contradictory cases | Draft + known incident patterns | Remove secrets; fix scenario boundary | Dedupe and fixture validation | Red-team reviewer |
| Reconcile | Suggest duplicate/conflict clusters | Whole domain index | Tenant isolation and corpus version pin | Explicit conflict key and reviewer decision | Domain maintainer |
| Golden test draft | Propose input/expected receipt cases | Accepted knowledge plus HKS register | Scenario has ground-truth source | Test must run deterministically | QA + domain expert |
| Promotion | No LLM authority | Reviewed artifact closure | Required approvals present | Validator, route closure, replay, shadow comparison | Named approver |

## Cost model and controls

Track cost per **accepted corpus improvement**, not per generated YAML file. For an authoring batch:

`cost = input_tokens × input_rate + output_tokens × output_rate + retry_cost + reviewer_minutes × loaded_rate`.

The dominant hidden cost is expert review. Generating ten variants of a shallow capability increases review load and warning count. Prefer one source-grounded draft, one adversarial pass and one reconciliation pass.

| Cost control | Mechanism | Quality protection | Metric |
|---|---|---|---|
| Content-addressed cache | Key by source hash + prompt + model + schema version | Same source cannot silently drift | Cache hit rate and avoided tokens |
| Delta-only authoring | Send changed artifact and dependency summaries | Avoids whole-corpus context loss/noise | Tokens per accepted change |
| Cheap-first model routing | Small model for extraction/schema; stronger model only for ambiguity/challenge | Escalation requires failed deterministic checks | Escalation rate and acceptance lift |
| Retry ceiling | Maximum one repair attempt per failed schema response | Prevents runaway cost and fabricated repair loops | Retries per accepted artifact |
| Unique-unknown batching | Group unseen situation hashes | Prevents repeated model calls for same route gap | Unknowns deduped per week |
| Human-review budget | Cap proposals to reviewer capacity | Avoids backlog being mislabeled as coverage | Draft-to-accepted ratio and review age |
| No runtime drafting | Never author a rule during a live decision | Preserves deterministic safety and latency | Runtime model calls in L3 must remain zero |

## Suggested operating percentages

| Workstream | LLM share of eligible work | Deterministic/human share | Meaning |
|---|---:|---:|---|
| Live package compilation | **0%** | **100%** | No model authority or call in the customer path |
| First-pass corpus drafting | 50–70% | 30–50% | Model drafts; expert accepts, rejects or rewrites |
| Schema/graph validation | 0% | 100% | Scripts own truth |
| Adversarial scenario ideation | 60–80% | 20–40% | Model broadens test ideas; humans define expected behavior |
| Promotion decision | 0% | 100% | Named human plus deterministic gates |
| Abstention explanation | 0–20% of displayed abstentions | 80–100% template | Optional wording only, never status/action |

## Exit gate

Layer 3’s LLM plan is successful when authoring throughput and accepted depth improve while live packages remain replayable: runtime model-call count is zero, every promoted artifact has source spans and named approval, model-originated drafts are labelled, costs are tied to accepted artifacts, unsupported runtime situations abstain, and no generated text can widen permission, choose a route or authorize a playbook.

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "../01-Architecture-and-Atlas-Delta/README.md" (M3.C1.L-contract.V0.U01)
include "../03-Current-Successes-Failures-and-Expected-Behavior/README.md" (M3.C1.L-data.V0.U01)
-->
