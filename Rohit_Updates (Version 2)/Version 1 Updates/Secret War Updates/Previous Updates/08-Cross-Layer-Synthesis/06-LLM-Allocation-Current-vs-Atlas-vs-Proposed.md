# LLM Allocation — Current vs Atlas vs Proposed

## Executive decision

This matrix synthesizes the seven layer LLM audits and the master operational coverage matrix at `harsh/mvp@b739bd5ca682d09550acc400ed2892c38c8518f8`. The system is framework-rich but no layer is Outcome-proven. Current tenant traffic mix, cache hit rate, physical provider attempts, and invoice-reconciled spend were not supplied, so current whole-layer LLM percentages and real Cost are **Unknown**.

The correct unit is a component's eligible event, not a layer-wide percentage. “80% LLM in Layer 1” may mean that 80% of eligible messy prose receives model-assisted interpretation; it must never mean that a model owns 80% of source truth or publication authority. Across all seven layers, **LLM authority is 0%** over identity merge, visibility, permission, correlation, graph truth, expertise route/promotion, hard constraints, ranking/selection, owner/channel/timing, execution, delivery lifecycle, outcome truth, causal attribution, or brain activation.

The proposed percentages below are rollout targets, not proof of current invocation. The Token budget values are **provisional per-call planning ceilings** to be calibrated against fixed multilingual/HKS replays before promotion. A ceiling is not permission to fill the prompt; minimum necessary, visibility-filtered evidence remains the rule.

## Measurement contract

| Term | Required definition |
|---|---|
| Eligible event | An item that passed deterministic tenant, source, visibility, integrity, task-specific and budget pre-gates |
| Invocation rate | Physical primary model calls divided by eligible events for that exact component; cache hits are reported separately, never hidden in the denominator |
| Attempt rate | Every provider request, including SDK retry, semantic repair and failed response, divided by eligible events |
| Token budget | Maximum authorized input/output tokens for one physical call; character limits are reported separately and are not mislabeled as tokens |
| Deterministic authority | The code, policy, schema or named human that alone may accept, reject, route, publish, execute or promote the model's candidate |
| Replay | Re-execution from immutable inputs and pinned model/prompt/schema/policy versions; cached replay must respect tenant and visibility boundaries |
| Fallback | Typed behavior when the model is unavailable, over budget, times out, or fails validation; it cannot manufacture the missing authority |
| Cost | All physical input/output tokens, retries, cache status, latency and human review, attributed to an accepted customer-value unit |

## Current, Atlas and proposed layer posture

| Layer | Current at pinned commit | Atlas boundary | Proposed posture |
|---|---|---|---|
| L1 Knowledge | Bounded relevance model can run; semantic extraction is also performed in L2, creating duplicate-read risk | Rules first, models for unstructured interpretation; deterministic ingestion/publication | One shared interpretation call for eligible prose; 0% generative work for structured events; destructive decisions remain deterministic and recoverable |
| L2 Context | Combined extraction call exists for unstructured events; graph, identity, correlation and lifecycle are deterministic | Model-assisted extraction optional; no model graph truth | Approximately 40–60% of all L2 events only if that is the measured unstructured lane; 100% of truly eligible unstructured events may be parsed once |
| L3 Expertise | Runtime compiler is deterministic/shadow, but the resolver excludes `stub:true` only and has no review-state admission; no accepted automated authoring pipeline is proved | Runtime compilation deterministic; offline authoring assistance allowed | Zero runtime calls for package authority; accepted/reviewed state is a deterministic precondition, while models may only accelerate source-grounded offline drafts and adversarial tests |
| L4 Reasoning | Deterministic decision core plus bounded optional explanation; Organization, Behavior and Adaptive values enter the adapter's hash but do not shape the judgment | Consultation only for low confidence, ambiguity and explanation; model never decides | Normal decisions 0%; exceptional consultation and on-demand explanation only after semantic-consumption and model-disabled gates pass |
| L5 Executive | No runtime model client in Executive; planning through monitoring is code-driven | Models only for drafting and summaries | Keep all operational decisions at 0%; optional grounded prose after a valid ExecutionObject exists |
| L6 Delivery | One current render call may generate headline, situation and artifact up to 600 output tokens before deterministic fallback | Very minimal rewriting/drafting/tone; never routing or lifecycle | Move call later: deterministic card first, on-demand artifact/tone only after semantic admission and authority |
| L7 Learning | Direct Behavior/Adaptive cohort evolution is empty, and recommendation learning can still propose non-expiring Adaptive state. Separately, **Organization proposal approval does not publish** an Organization brain row, and policy reload drops both block lists | Interpret ambiguous feedback or draft review prose; governed learning remains deterministic | Roughly 5–15% model-assisted workload, 85–95% deterministic authority path; never direct promotion and never model-repair an authority/lifecycle defect |

## Deterministic authority defects: no LLM is eligible to patch them

These are not language-interpretation problems. They are missing admission, semantic-consumption, publication, policy-fidelity and lifecycle invariants in the pinned code. A fluent model response cannot repair them, and no proposed token budget or invocation rate authorizes it to do so.

| Defect | Exact Current code truth at `b739bd5` | Required deterministic authority | LLM eligibility and Fallback | Required Replay |
|---|---|---|---|---|
| L3 review-state admission | `packs/compiler/capability_resolver.py:96-105` removes a capability only when `identity.stub` is true. It does not inspect an accepted/reviewed status, reviewer identity, review receipt or accepted content hash. A non-stub draft is therefore structurally eligible. | Resolve only a named-reviewer-accepted artifact whose accepted hash/version closes every routed dependency; unsupported, stub, draft or unaccepted closure must abstain with a typed reason. | **0% / no LLM eligible.** A model may draft offline but cannot infer acceptance. Fallback is `unsupported_expertise` or review queue, never legacy/generative play invention. | Toggle only review status/accepted hash while content is fixed: draft stays non-authoritative; accepted closure compiles; revocation returns to abstention with receipt. |
| Four-brain semantic consumption | `reason/adapters/expertise.py:180-213` includes Organization rules, Behavior patterns and Adaptive preferences in `knowledge_hash`, manifest version and metadata. `_goal`, fixed constraints/policies and `_plays` do not consume those values to alter goal, constraints, policy, candidate eligibility or ranking. A brain mutation may change the hash while judgment remains unchanged. Expert influence is also narrow: the first capability question may set the goal; only `expert_rules` with `definition.steps` become plays; the adapter stops at four and otherwise emits `review_situation` (`expertise.py:104-168`). | Define a typed, bounded consumer for every permitted brain field and reject fields with no declared consumer. Hash/version lineage is evidence of input change, not evidence of decision effect. | **0% / no LLM eligible.** A model cannot translate arbitrary brain bytes into runtime authority. Fallback is explicit `semantic_no_effect`/abstention, not a claim that adaptation occurred. | One-brain-at-a-time mutation must change only its intended goal/constraint/policy/eligibility/ranking field, or produce an explicit no-effect receipt. With the model disabled, the same typed semantic deltas must remain. |
| Organization review-to-publish | `feedback/publisher.py:168-188` sends an Organization proposal requiring review to `queued_for_review`; brain publication occurs only through `publish_brain` on the promoted path. `api/learning_routes.py:119-143` approves a review by updating `learning_objects.state` to `promoted` and logging a transition, but never calls `publish_brain`. The honest state is `approved_unpublished`, not active Organization Brain. | Approval and publication are separate atomic/audited states; only a new active `learned_brain_entries` version plus compiler-consumption receipt makes the value authoritative. | **0% / no LLM eligible.** A review-summary model cannot activate, publish or backfill a brain row. Fallback is keep `approved_unpublished` blocked from packages and decisions. | Approve an Organization proposal, prove it remains absent from active snapshots until publication, then prove exactly one version is published, consumed and rollback-safe. |
| Lossy learning-policy reload | `contracts/learning.py:267-298` defines `blocked_targets` and `blocked_subject_prefixes`; `feedback/governance.py:31-41` enforces both. `feedback/orchestrator.py:28-45` neither selects nor passes either list when rebuilding `LearningPolicy`, so persisted restrictions reload as empty defaults. | Lossless, hashable policy serialization/reload with field equality before any proposal is evaluated; a missing field makes policy state incomplete and closes promotion. | **0% / no LLM eligible.** A model cannot guess omitted tenant restrictions. Fallback is `policy_incomplete`, no learning promotion or brain publication. | Persist both block lists, reload them byte/semantic-equivalently, and prove blocked target/prefix proposals remain blocked with the model disabled. |
| Adaptive lifecycle contradiction | Direct Behavior and Adaptive evolution return `[]` through `_cohort_candidate` (`feedback/units.py:165-182`). Recommendation learning can nevertheless emit `LearningTarget.ADAPTIVE`, hardcodes `distinct_days=1`, and supplies no `expires_at` (`units.py:187-219`). `LearningObject` permits expiry only for Runtime (`contracts/learning.py:184-227`). **Adaptive cannot carry expiry** under the Current contract. | Ratify one lifecycle: either represent a bounded Adaptive TTL/decay/supersession contract, or route temporary learning to a Runtime lease. Until then, a non-expiring Adaptive recommendation is not publishable authority. | **0% / no LLM eligible.** A model cannot fabricate expiry or waive the contract. Fallback is `adaptive_ttl_unresolved`, review/park, and no active Adaptive version. | Advance a pinned clock through proposal, activation, expiry/supersession and rollback. Model-disabled results must be identical and stale Adaptive state must never influence a package. |

The invariant across all five rows is: **model-disabled operation must preserve the same admission, publication state, policy restrictions, lifecycle law and semantic decision.** If disabling the model changes any of those, the model has acquired forbidden authority. Conversely, changing only a hash while the goal, constraints, policy, candidates and ranking remain identical is not semantic consumption and cannot be marketed as adaptation.

## Per-component allocation matrix

The Token budget column gives a recommended starting ceiling where the layer report did not define one. Those recommended values require replay calibration; `0` means no model call is permitted. Invocation rate is always relative to the named denominator.

| Layer / component | Current evidence | Atlas / allowed model role | Proposed Invocation rate | Proposed Token budget per call | Deterministic authority | Fallback | Replay and cache key | Cost unit |
|---|---|---|---:|---|---|---|---|---|
| L1 connector fetch, auth, cursor, dedup | No LLM | None | **0%** | 0 | Connector contract, tenant auth, cursor/watermark transaction | Retry/park with source-window receipt | Provider page/cursor/version | Cost per 1,000 source events, no model spend |
| L1 OCR | Optional traditional Tesseract, default off | Traditional OCR; no generative reconstruction | **0% generative** | 0 model tokens; budget by pages | MIME/malware/page checks and OCR confidence | Park unreadable content | File/page hash + OCR engine version | Compute per processed page |
| L1 speech transcription | Complete path not found | Transcription allowed after consent | **100% of supported consented audio** | Provider-specific audio-minute cap; transcript is evidence, not generative authority | Consent, format, language, timestamps, speaker uncertainty | Park unsupported/low-quality audio | Audio hash + engine/language/version | Cost per audio minute and accepted transcript |
| L1 relevance triage | Current batch up to 12 items at about 600 prepared chars each; single fallback up to 1,500 chars/120 output | Rules first; model fallback | **10–35%** after certain-value/noise lanes | Target ≤2,500 input / ≤400 output per batch; preserve current tighter single-item output where sufficient | Protected-source rules and keep/park/drop validator; model cannot irrecoverably drop ambiguity | Keep/Park on error or uncertainty | Tenant + evidence hash + prompt/model/schema/policy versions | Cost per 1,000 scanned and per qualified signal |
| L1+L2 shared unstructured interpretation | Today relevance and L2 extraction may read the same item separately | Model may extract candidates, never publish truth | **60–85% of eligible messy prose; 0% mapped structured** | Target ≤3,000 input / ≤700 output compact JSON | Evidence spans, actor/role/time/domain schema, permission and publication rules | Park with exact missing/validation code | Tenant + normalized evidence hash + model/prompt/schema/masking/policy versions | Cost per grounded signal and trusted action |
| L1 relationship/role candidates | Mostly deferred to L2; raw transport roles retained | Optional for complex prose | **50–80% of prose that actually expresses business roles**, preferably inside shared call | No incremental call; use shared-call budget | Exact participants/thread graph; candidate never selects requester/target/owner | Preserve unresolved role | Same shared interpretation replay | Incremental tokens per grounded role candidate |
| L1 embeddings | No complete general pipeline proved | Semantic retrieval only | **100% of approved retrievable chunks** | Target ≤1,000 input tokens/chunk, 0 output | Visibility, permitted use, tenant partition, retention/deletion | No vector; lexical/source retrieval remains | Tenant + content/chunk/model/policy version | Cost per indexed and retrieved approved chunk |
| L1 domain hints | Cheap hints plus richer L2 model domains | Model only when ambiguous | **20–50% of ambiguous eligible text**, inside shared call | No incremental call | Allowlisted multi-domain candidates; final route belongs to L3 | Unknown/multi-domain hint; no guessed route | Shared interpretation key | Incremental tokens per useful domain candidate |
| L1 importance, qualification, publication | Deterministic | No LLM | **0%** | 0 | Typed formula, evidence, visibility, coverage and lifecycle policy | Park/reject with receipt | Exact input/version replay | Compute only |
| L2 structured CRM/calendar/database mapping | Deterministic mapper | Optional model not needed | **0%** | 0 | Source schema, authority, provenance and graph write rules | Park/review mapping failure | Event + mapping/schema versions | Compute per mapped event |
| L2 combined unstructured extraction | Current cap 8,000 characters and 4,096 output tokens; one repair plus SDK retries | Extraction may be model-assisted | **100% of truly eligible unstructured; planning hypothesis 40–60% of all L2 events** | Target ≤3,000 input / ≤700 output; decisive-tail selector required | Source-span grounding, authority rank, schema, chronology and role checks | Park after centrally bounded attempts | Tenant + full evidence hash + model/prompt/schema/masking versions | Cost per uncached event and grounded field |
| L2 multi-actor role proposal | Current output does not guarantee requester/connector/target contract | Candidate proposal only | **10–25% of unstructured multi-actor items**, reuse combined call | No incremental call; if offline repair is approved, ≤1,500/≤300 | Exact addresses, participants and role review; no model identity merge/target choice | Review source / unresolved role | Correlation candidate + evidence/version key | Cost per accepted role resolution |
| L2 identity proposal | Deterministic exact aliases and merge proposals | Optional entity-link suggestion | **<5% proposal queue; 0% authority** | Target ≤1,200 input / ≤200 output | Anchored deterministic/human merge receipt | No merge; preserve separate nodes | Candidate-set + evidence/model versions | Cost per reviewed and accepted merge proposal |
| L2 correlation, graph truth, situation lifecycle/validation | Deterministic | No LLM | **0%** | 0 | Correlation rules, field authority, graph version, required-context validator | Split/review/observation | Graph/event/domain-spec versions | Compute only |
| L2 situation display naming | Deterministic labels exist | Cosmetic optional | **0–10% of valid displayed BSOs** | Target ≤300 input / ≤40 output | Frozen type/target/priority; label cannot alter semantics | Deterministic label | Tenant + BSO hash + language/prompt/model | Cost per actually viewed generated label |
| L3 live route, brain resolution and package compile | Deterministic compiler; currently shadow/default-off; resolver has no review-state admission | Must be deterministic and replayable | **0%** | 0 | Named-reviewer-accepted registry/content hash, dependency closure, corpus/version hashes and permission/preference precedence | Typed unsupported/abstain; never admit a draft or create a generic runtime play | BSO + evidence + accepted artifact receipts + four-brain snapshots | Compute per package |
| L3 source-to-rule candidate extraction, offline | No proved accepted automation | Offline assistance allowed | **50–70% of selected authoring intake** | Target ≤6,000 input / ≤1,200 output | Licensed source hash, source-span citations, draft status and human review | Retain source; no draft promotion | Source + prompt/model/schema/corpus versions | Cost plus reviewer minutes per accepted rule |
| L3 capability/YAML first draft, offline | Human-authored corpus with many stubs | Offline assistance allowed | **50–70% of eligible draft work** | Target ≤8,000 input / ≤2,000 output | Schema/dependency validation and named domain-expert approval | Draft rejected/queued; runtime remains unsupported | Source set + dependency summary + corpus/model versions | Cost per accepted non-stub closure, not generated file |
| L3 adversarial scenario ideation, offline | Manual/tests | Offline assistance allowed | **60–80% of ideation workload** | Target ≤6,000 input / ≤1,500 output | Human defines expected output; deterministic fixture must pass | Discard scenario; no runtime effect | Corpus/draft + prompt/model/test versions | Cost per accepted golden scenario |
| L3 abstention explanation | Structured reason already exists | Wording only downstream | **0–20% of displayed abstentions, on demand** | Target ≤800 input / ≤150 output | Frozen unsupported status and receipt fields | Deterministic template | Package/receipt + audience/language/model | Cost per viewed explanation |
| L4 hard gates, candidate elimination/ranking, selection, confidence | Deterministic core | Model never decides | **0%** | 0 | Reasoning DAG, constraints, calibrated vector and typed outcome | `DEFER` / `BLOCKED` / `NO_ACTION` | Decision/package/manifest versions | Compute per decision |
| L4 low-confidence consultation | Bounded defer path exists | Allowed consultation | **2–8% of total decisions** | Target ≤2,000 input / ≤500 output | Eligibility reason; hypotheses/questions must map to evidence/accepted plays; full rerun decides | Remain defer; no repeated call to manufacture winner | Tenant + visibility + package/decision + prompt/model/schema | Cost per defer correctly resolved without false prescription |
| L4 ambiguous-situation consultation | Generic fallback risk in active path | Allowed consultation | **1–5% of total decisions** | Target ≤2,000 input / ≤500 output | Model cannot change role/domain/state; each hypothesis stays hypothetical | Review source / defer | BSO/ambiguity/evidence/model versions | Cost per verified discriminating fact acquired |
| L4 candidate wording | Templates can be generic | Wording of fully specified action only | **0–20% of displayed accepted decisions** | Target ≤800 input / ≤150 output | Recipient/action/timing/completion frozen and diff-checked | Deterministic wording | Decision semantic hash + surface/language/model | Cost per displayed copy accepted with low edit burden |
| L4 explanation | Optional bounded explanation exists | Allowed after decision | **5–25% on demand** | Target ≤1,200 input / ≤250 output | Frozen selected/rejected trace; no new fact/action/score | Deterministic trace template | Decision/package/prompt/model versions | Cost per viewed explanation and comprehension lift |
| L5 interpretation, planning, ownership, communication plan, validation, monitoring, cadence | Current Executive is model-free | Must remain operationally deterministic | **0%** | 0 | Execution contracts, assignment/policy, dependencies, authority and success predicates | Block/defer/template; no model repair | Decision + context/config/execution versions | Compute per ExecutionObject |
| L5 reminder copy | Deterministic formatter today | Drafting prose allowed | **10–30% of already-approved non-template reminders; default off** | Target ≤800 input / ≤180 output | Valid target, cadence, send intent, fact allowlist | Deterministic reminder or review | Execution state/cadence + audience/prompt/model | Cost per actually sent/accepted draft |
| L5 customer/partner draft | No native model call | Email/Slack drafting allowed | **20–50% of explicitly requested drafts; 0% auto-send** | Target ≤2,000 input / ≤500 output | Approved action/recipient/source/voice snapshot; promise and send controls | Template/review; action remains unchanged | Execution semantic hash + audience/language/voice/model | Cost per used draft plus edit minutes |
| L5 executive status summary | Deterministic summary | Narrative compression allowed | **0–25% of requested complex briefs** | Target ≤4,000 input / ≤700 output | Fixed rows/counts/metrics and omission/numeric validation | Deterministic structured brief | Row-set/window/metric/prompt/model versions | Cost per viewed brief, batched rather than per row |
| L5 outcome narrative | Structured outcomes exist | Report prose allowed | **0–20% on demand** | Target ≤2,000 input / ≤400 output | Outcome and attribution labels frozen | Structured outcome view | Outcome-ledger/window/model versions | Cost per viewed outcome narrative |
| L5 agent instruction prose | Governed handoff is HTTP 501 | Phrasing only after safe protocol | **0% now; optional ≤10% after approval/lease/result protocol is green** | Target ≤800 input / ≤150 output after eligibility | Signed machine schema, scoped approval, one executor lease; model never chooses tool/scope | Keep 501/blocked | Approval + execution/action/tool schema + model | Cost per governed handoff, never before availability |
| L6 card headline/situation render | Current call may generate headline, situation and artifact; output cap 600; fallback deterministic | Minimal rewrite/summary only | **0–20% of semantically admitted bounded cards** | Target ≤1,000 input / ≤180 output | Exact target/thread/action/current state and claim-to-evidence validator | Deterministic card or review; no actionable fallback if meaning missing | Tenant + execution/state/audience/prompt/model | Cost per viewed admitted card |
| L6 action artifact/draft | Current combined render may make nonempty artifact look ready | Drafting allowed, authority forbidden | **0% automatic; 20–60% after explicit approved draft request** | Target ≤2,000 input / ≤500 output | Linked action, recipient/channel policy, allowed claims, approval; handoff remains independent | Review/template; never execute | Execution/action/state/audience/model versions | Cost per used artifact, not per built card |
| L6 reminder copy and tone adaptation | Mostly deterministic current bridge/adapter | Rewrite/tone allowed | Reminder **0–15%**; tone **10–30%** of approved human copy | Target ≤900 input / ≤250 output | Reminder eligibility/recipient/timing frozen; semantic-equivalence check | Grounded template | Reminder state + base copy + audience/language/model | Cost per delivered variant and human edit |
| L6 digest/executive summary | Deterministic summary | Summarization allowed | **0–25% on demand** | Target ≤4,000 input / ≤700 output | Fixed included items, order, counts and links | Structured digest | Item set/window/audience/model | Cost per viewed brief |
| L6 agent envelope | v2 shape exists; intended handoff unavailable | Prose field only, never scope | **0% now; 0–10% after governed route** | Target ≤800 input / ≤150 output | Approval, lease, machine schema, signature and idempotency | 501/blocked | Exact governed command/model versions | Cost per successful governed envelope |
| L6 delivery analytics narrative | Structured arithmetic | Report prose only | **0–10% of explicit report requests** | Target ≤4,000 input / ≤700 output | Recompute numbers; preserve unknown/unproven/association labels | Structured metrics | Metric/window/data-quality/model fingerprint | Cost per viewed report |
| L7 structured delivery/execution/outcome selection and calculation | Deterministic typed loaders/units | No LLM | **0%** | 0 | Canonical identities, windows, evidence, causal and policy gates | Unknown/neutral/degraded receipt | Run/input/policy versions | Compute per learning run |
| L7 free-text card feedback parse | Structured verdict plus optional text; canonical seam incomplete | Interpret language only | **10–30% of feedback events needing text interpretation** | **300–700 input / 80–180 output** | Valid actor/card/action, schema, scope ceiling and confidence gate | Preserve raw text; review/observation | Tenant + verdict revision + evidence/prompt/schema/model | Cost per reviewed/confirmed interpretation |
| L7 explicit preference candidate | Canonical unit currently returns empty | Extract bounded candidate | **5–15% of feedback events** | Reuse feedback parse; otherwise ≤700/≤180 | Explicit first-person instruction, role/domain/duration and confirmation for broad scope | Observation/review; no active preference | Same verdict key + preference schema/policy | Cost per confirmed bounded preference |
| L7 temporary directive | Canonical unit currently returns empty | Parse instruction and time | **3–10% of feedback events** | **250–600 input / ≤120 output**; reuse parse response | Actor authority, deterministic time parser, TTL cap | Review; missing TTL cannot publish | Evidence + directive/policy/model versions | Cost per valid expiring directive |
| L7 reviewer feedback summary | No canonical output | Summarize reconciled observations | **One call per qualified review candidate, not per event** | **600–1,500 input / 150–300 output** | Evidence IDs/counts/confidence/target frozen | Structured review packet | Candidate/evidence-set/model versions | Cost per reviewed proposal |
| L7 unstructured pattern clustering | Deterministic support calculation; empty evolution seams remain | Candidate semantic clustering only | **5–20% of authorized unstructured facts** | **1,500–4,000 input / ≤400 output**, batches 20–50 | Tenant/use class/k-floor first; recount independence/support deterministically | No cluster/promotion | Tenant + fact/evidence-family/prompt/model versions | Cost per accepted cluster candidate |
| L7 Behavior/Adaptive labels/explanations | Direct cohort builders return empty; recommendation learning can create Adaptive without expiry, while Adaptive cannot carry expiry in the contract | Describe only an already-qualified deterministic cohort/delta after lifecycle law exists | **0–5% of qualified candidates each; 0% while lifecycle is unresolved** | Target ≤1,500 input / ≤300 output only after eligibility | Cohort membership, delta, confidence, lifecycle/TTL and activation deterministic | `adaptive_ttl_unresolved`; no proposal/version publication | Cohort/version/brain-policy/lifecycle/model | Cost per reviewed/published version only after wiring and expiry/supersession replay exist |
| L7 provider-error classification | Deterministic performance metrics | Optional root-cause label | **1–10% of unclassified failures** | **300–900 input / ≤100 output** | Redaction and provider/status facts; cannot infer user rejection/success | Unknown error class | Tenant + sanitized error signature/model | Cost per newly classified actionable error |
| L7 knowledge-review brief | Deterministic qualification creates review-only suggestion | Draft human-review brief | **100% of qualified suggestions, expected very low volume** | **1,000–3,000 input / 300–600 output** | Model cannot mutate Expert Brain; human review, corpus tests and release own promotion | Structured suggestion only | Suggestion/evidence/corpus/model versions | Cost plus expert-review minutes per accepted corpus change |
| L7 validation, governance, publish, rollback, consumption | Deterministic | No model authority | **0%** | 0 | Evidence counts, permitted use, confidence, target, approval, version, TTL, rollback and compiler receipt | Reject/quarantine/degraded | LearningObject + policy/brain/compiler versions | Compute per proposal/version |
| L7 learning-health explanation | Customer surface not complete | Explain computed health | **On demand only** | Target ≤2,500 input / **≤400 output** | Metrics/readiness already computed; zero data cannot become healthy | Structured health receipt | Run/metric/data-quality/model fingerprint | Cost per viewed health explanation |

## Invocation and retry accounting

Do not count “one pipeline event” as “one call.” Layer 2 currently combines SDK retries, one extractor repair and up to three processing attempts; the layer audit calculates a theoretical path of up to 18 HTTP attempts if those ceilings compound. The target is one centrally budgeted physical-attempt ladder:

1. Deterministic eligibility and cache lookup.
2. One primary call.
3. At most one repair **only** for syntactically invalid schema when the same evidence is sufficient.
4. No creative retry for semantic ambiguity, policy rejection or absent evidence.
5. Infrastructure retry only within the declared attempt/token/latency budget.
6. Terminal `Park`, deterministic template, review, or typed defer when the ceiling is reached.

Every physical attempt records parent event, tenant, component, model/provider, prompt/schema/policy versions, input/output tokens, cache status, latency, response class, validation result and Cost. Failed attempts cannot disappear merely because a later attempt succeeds.

## Replay contract

| Requirement | Rule |
|---|---|
| Tenant and purpose isolation | No cache or batch crosses tenant, visibility, permitted-use or retention boundary |
| Complete semantic key | Evidence/object hash + model + prompt + output schema + masking + policy + relevant graph/package/execution/brain versions |
| Model drift | A model/config change invalidates the key even when prompt text is unchanged |
| Correction and deletion | Source revocation, identity correction, visibility change or retention deletion invalidates dependent cache entries and outputs |
| Deterministic replay | With models disabled, all authoritative objects, routes, scores, lifecycle states, outcomes and brain versions remain identical |
| Generative replay | Same pinned key returns accepted cached output or is evaluated as a new version; nondeterministic text never mutates prior authority |
| Shadow promotion | New model/prompt/schema runs against fixed labelled corpus and live shadow sample before any eligibility expansion |

## Fallback hierarchy

| Failure class | Fallback | Prohibited response |
|---|---|---|
| Budget exhausted | Structured bypass, cache or deterministic template; preserve important work as review/defer | Randomly skip high-value events to hit a percentage |
| Provider unavailable/timeout | Bounded infrastructure handling, then Park/defer/template with receipt | Treat outage as irrelevant evidence or new business truth |
| Invalid syntax | One schema repair within budget, then Park/review/template | Re-prompt repeatedly until something parses |
| Ungrounded/unsupported claim | Reject the entire candidate/draft; deterministic output or review | Partially merge the plausible sentences |
| Semantic ambiguity | Preserve candidates and ask for discriminating evidence | Model chooses the most likely identity, role, route or action |
| Unsupported expertise | Typed abstention and authoring backlog | Runtime model invents a playbook |
| Missing authority/approval | Block execution/delivery | Fluent draft becomes permission or agent command |
| Missing causal outcome | Neutral/unknown learning result | Model labels silence, click or delivery as success/failure |

## Cost model and controls

For component `i` and reporting window `w`:

```text
physical_calls_i = primary_attempts_i + retry_attempts_i + repair_attempts_i
token_cost_i = sum(input_tokens × configured_input_rate
                 + output_tokens × configured_output_rate) over every physical call
fully_loaded_cost_i = token_cost_i + reviewer_minutes × loaded_rate + failure_recovery_cost
monthly_cost_i = eligible_events_i × invocation_rate_i × (1 - cache_hit_rate_i)
               × expected_cost_per_primary_call + retry_and_repair_cost_i
```

Configured prices are versioned accounting inputs, not architectural constants. The current code's Haiku ledger values (`$0.80/M` input and `$4/M` output) are code configuration evidence at the pinned commit, not a guarantee of current vendor pricing. Reconcile the ledger to provider invoices by effective price version.

| Control | Required metric | Quality boundary |
|---|---|---|
| Structured bypass | Eligible rate by source/type | Missing mapping fields must Park, not silently disappear |
| Semantic cache | Hit/invalidation rate by complete key | No stale-model, cross-tenant or post-revocation reuse |
| Minimal context packing | Input tokens and decisive-field recall | Token savings cannot remove the latest ask, role or contradiction |
| Compact schema/output cap | Output tokens, parse/repair rate | Truncation becomes an explicit missing code |
| Cheap-first routing | Cost and quality lift by model tier | Escalation only after a typed eligibility reason |
| Batching | Calls per independent item/brief | Never batch target-specific drafts or mixed visibility |
| Human capacity | Draft-to-reviewed-to-accepted ratio and review age | Generated backlog is not expertise coverage |
| Value denominator | Cost per grounded signal, trusted action, accepted corpus change and proven outcome | Paragraphs, YAML file count and clicks are not customer value |

## Release gates

1. Current and target invocation/attempt rates are visible by component and eligible denominator; no whole-layer percentage is presented as authority or production proof.
2. Every allowed call has an explicit Token budget, retry ceiling, complete cache key, visibility-safe input contract, validator and typed Fallback.
3. The model-disabled replay yields identical source authority, review-state admission, graph, package, decision, execution, delivery route/lifecycle, outcome classification, policy restrictions and active brain version.
4. Boardy, Theresa, stale-meeting, restricted-use, card-action and agent-handoff HKS fixtures cannot be turned prescriptive by model text.
5. Unsupported-claim and ungrounded-identity/role/deadline/permission rates are zero on the golden release set; ambiguous cases abstain or review.
6. Every physical attempt, including failed retries and repairs, reconciles tokens and configured Cost to provider billing within the agreed tolerance.
7. Budget exhaustion and provider outage preserve important work and deterministic operations; they never change recipient, route, priority, timing, lifecycle, completion, outcome or learning promotion.
8. Eligibility expansion is scoped by tenant + component + model/prompt/schema/policy version, shadow compared, reversible and tied to a measurable quality or customer-value lift.
9. Each Organization, Expert, Behavior and Adaptive mutation passes a semantic-consumption replay: it changes only the intended typed judgment field or records explicit no-effect; a changed knowledge hash alone is a failure.
10. Organization approval remains `approved_unpublished` until an active-version and compiler-consumption receipt exists; policy reload is lossless for both block lists; non-expiring Adaptive proposals remain `adaptive_ttl_unresolved` until a ratified lifecycle can be replayed.

The product does not need “more LLM” as a general goal. It needs model assistance exactly where language is irreducibly messy, deterministic gates everywhere authority changes, and evidence that each paid call improves a grounded decision or accepted knowledge asset without weakening replay, privacy or accountability.

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "../01-Layer-1-Knowledge/05-LLM-Use-Cases-and-Cost/README.md" (M2.C1.L-logic.V1.U01)
include "../02-Layer-2-Context-Intelligence/05-LLM-Use-Cases-and-Cost/README.md" (M2.C2.L-logic.V1.U01)
include "../03-Layer-3-Domain-Expertise/05-LLM-Use-Cases-and-Cost/README.md" (M3.C1.L-logic.V1.U01)
include "../04-Layer-4-Reasoning/05-LLM-Use-Cases-and-Cost/README.md" (M3.C2.L-logic.V1.U01)
include "../05-Layer-5-Executive/05-LLM-Use-Cases-and-Cost/README.md" (M4.C1.L-logic.V1.U01)
include "../06-Layer-6-Delivery-Atlas-5.2/05-LLM-Use-Cases-and-Cost/README.md" (M4.C2.L-logic.V1.U01)
include "../07-Layer-7-Learning-Atlas-6/05-LLM-Use-Cases-and-Cost/README.md" (M4.C3.L-logic.V1.U01)
include "01-Master-Atlas-vs-Code-Coverage-Matrix.md" (M5.C1.L-data.V0.U01)
-->
