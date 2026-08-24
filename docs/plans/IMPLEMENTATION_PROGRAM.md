> **Created:** 2026-08-23 · **Status:** 🟢 Active — awaiting owner approval to start Phase 0/0B
> **Purpose:** The full implementation program derived from the Secret War audit (73 docs / 145k words) cross-verified against live code at `harsh/mvp@b739bd5` and the design-partner org's real Postgres. Covers all 7 layers, 106 canonical gaps, 0 unassigned.
> **Method:** 11 parallel readers over the audit package with live code/DB cross-check → one max-effort synthesis. Audit basis commit == current HEAD, so every `[CODE]` claim is current.
> **Companion:** `INTELLIGENCE_SHALLOWNESS_ROOT_CAUSE.md` (2026-08-22) — the independent data-grounded root-cause that this program reconciles against.

I'll verify the load-bearing numbers I need for the program (failing test IDs, LLM call sites, corpus counts) before writing.
All 9 failing tests named. Now the LLM call inventory.
# GeniOS — FULL IMPLEMENTATION PROGRAM
### Secret War audit → executable remediation, all seven layers, audit dependency order preserved

**Baseline:** `harsh/mvp@b739bd5` — confirmed HEAD, zero commits since the audit was written. Every `[CODE]` claim below was verified at this commit. Design-partner org: `org_e97e86f858ad48b2bbf64b8a` (Rohit Swerashi, founder raising money).

**Canonical gap register:** 106 IDs across L1–L7 + X (cross-cutting). All 148 source-pack gap entries map into these 106; 19 canonical IDs are net-new synthesis objects (RC-1/RC-2 boundary contracts, replay harness, ADR set, cost attribution) that no single pack listed as a gap. Coverage check in §6.9.

**Claim classes used throughout:** `[CODE]` verified against source · `[TEST]` verified by a test run · `[ATLAS]` spec says it should happen · `[CUSTOMER]` customer-observed · `[MODELLED]` proposed behaviour, **not** a bug that exists.

---

# 1. LAYER BY LAYER

## L1 — KNOWLEDGE / CAPTURE
**Package:** `genios_engine/capture/**` + `contracts/{source_event,gated_event,visibility}.py`

### [ATLAS] What it must do
Acquire the company's real operating evidence, qualify it, hand L2 a **QualifiedEnterpriseSignal**: immutable event/thread ids, source receipt, actor **plus typed role candidates** (requester, introducer, introduced contact, owner, business subject), full participant set, source-stamped visibility and exclusions, normalised signal atoms with evidence spans, domain candidates, scoped coverage snapshot, signal lifecycle, and `importance_bp` computed by formula and kept strictly separate from processing priority. Prefer recoverable uncertainty over silent loss: ambiguous or high-value-but-unclear material **parks with its body retained**; unknown visibility suppresses rather than defaults wider; incomplete coverage marks negative predicates *unknown* rather than inferring "no reply". Models may propose semantics; permission, identity, cursor movement, destructive retention, importance and publication stay deterministic. (`01-Layer-1-Knowledge/01/README.md` §"Required architecture decision")

### [CODE] What it actually does
`capture/pipeline.py:124-243` runs raw → land/dedup → preprocess → `run_gate` → triage → `GatedEvent`. Gate = S0 scope, S1.5 structured short-circuit, S1 whitelist-then-hard-rules, S2 optional LLM relevance (`capture/gate/gate.py:11-60`). `GatedEvent` (`contracts/gated_event.py:14-39`) carries event/source/time, route, structured_fields, domain hints, linkage hints, triage_lane, versions — **no visibility, no recipients, no typed roles, no signal atoms, no importance, no lifecycle**. Live: 1,363 landed events — gmail 363 emitted / 286 parked / 657 dropped, gcal 57 emitted; 1,307 of 1,363 (95.9%) carry no domain hint; 394 `document_jobs` all `native_parse_used=false, ocr_engine=NULL`; 286 parked all `status='pending'`.

### Complete gap list, ranked

**L1-01 · Calendar watermark set from meeting START → gcal permanently frozen** `[CODE]` `small`
- Unit: `capture/acquire/sync_runner.py:170-171` (`if raw.occurred_at > watermark`) + `capture/connectors/calendar.py:62` (`occurred_at=_parse_start(ev)`)
- Impact: `sync_cursors` gcal watermark = **2026-08-24 08:30+00 — a future timestamp**. Every meeting booked from now for any time before that is invisible forever. All 9 incremental runs scanned 1 object, 0 new. `can_evaluate_no_meeting` reads *fresh* from a dead connector.
- Fix: `SourceConnector` declares its watermark clock; calendar uses the event `updated` field (already read at `calendar.py:21`), never `start`. `run_sync` refuses to persist a watermark > `now()`.
- Blocks: all meeting intelligence; replay 05; HKS-L1-03/04; acceptance A-L1-03.

**L1-02 · S2 LLM junk gate hard-drops on `disposition` alone — no threshold, no reason, body discarded** `[CODE]` `medium`
- Unit: `capture/gate/gate.py:49-51` (branches on `disp=="drop"`, never reads `relevance`); `capture/gate/relevance.py:235` (`relevance` parse-default 0.5); `capture/gate/relevance.py:107` (BATCH prompt schema has no `reason` field); `capture/pipeline.py:209-220` (payload stored only when `kept in (emitted, parked)`)
- Impact: **109 emails irrecoverably deleted**; 33 at relevance exactly 0.5 (= the parse default, i.e. the model returned nothing), 43/109 at ≥0.3; 109/109 with `detail->>'reason' = ''`; 657 dropped events → 0 payloads. An investor on an unfamiliar domain is deleted on a model coin-flip with no body and no recovery.
- Fix: three-way S2 decision keyed on `v.relevance` against a named threshold constant (drop / park / keep); retain a short-TTL payload for LLM-gate drops specifically; add `reason` to `_GATE_BATCH_PROMPT` and `_verdict_from`.
- Blocks: exit gate "zero unrecoverable material false drops" is currently **unmeasurable**, not merely unmet — the dropped bodies do not exist.

**L1-03 · Whitelist short-circuits the entire hard-rule block → document park skipped for the best senders** `[CODE]` `small`
- Unit: `capture/gate/gate.py:31-40` (W-code hit returns before `hard_rule(ctx)`); DOC park lives at `capture/gate/rules.py:97-104`, N-10 empty-body at `:141-142`
- Impact: **108 attachment events emitted with empty bodies** (`document_jobs` unsupported/emitted 107 + fetch_failed/emitted 1) vs 262 correctly parked. W-01 fired 115×, W-02 49×. A contract or deck PDF from a known investor — the highest-value attachment class — is the case most likely to skip review. **Not in the audit's L1-01..L1-22 catalog.**
- Fix: split `rules.py` — evaluate content-integrity rules (DOC-02/04/05, N-10) unconditionally BEFORE the whitelist; whitelist may bypass only the noise N-codes. A whitelist may prevent a drop, never a park.
- Blocks: A-L1-16, A-L1-06; any claim that attachment evidence is complete.

**L1-04 · Visibility is defined, unit-tested, and never called** `[CODE]` `large`
- Unit: `contracts/visibility.py:30-102` (fully implemented, tested) vs `grep -rn "visibility" genios_engine/capture/` → **zero matches**; no column on `source_events`
- Impact: every captured event is org-scoped from landing; `context/situation_bso.py:122-166` then hardcodes `org` downstream. Private threads and restricted support messages can surface to anyone in the tenant. The passing test is itself the hazard — it makes the layer look protected.
- Fix: `visibility: Visibility` with no default on `SourceEvent` and `GatedEvent`; derive per connector (`composio`, `calendar`, `notion`, `drive`, `hubspot`, both `intake.py` entry points); persist behind a migration; `run_gate` parks with `visibility_unknown` rather than publishing.
- Blocks: HKS-L1-05, A-L1-05/14; all narrowest-merge work in L2.

**L1-05 · Business roles and recipients die at the normalize seam; To/Cc survive only inside an encrypted blob with a 30-day TTL** `[CODE]` `large`
- Unit: `capture/landing/normalize.py:42` (`actor=Actor(type, email)` only); `capture/connectors/base.py::RawObject` (no recipients field); `connectors/composio.py:366-370,400,446` (extracts to/cc into an untyped dict); `capture/pipeline.py:74` (`_EMITTED_PAYLOAD_TTL_DAYS = 30`)
- Impact: root cause of the Boardy failure — one transport sender per event, no introducer/introduced/business-subject distinction. **Time-bounded:** `min(raw_payloads.expires_at)` = 2026-09-16; after that the backfilled emails have no recipient data anywhere, so even best-effort reconstruction stops.
- Fix: typed `participants` + `role_candidates` (with explicit unresolved state) on `RawObject` → `to_source_event` → `SourceEvent`/`GatedEvent`, persisted as first-class columns in `pg_repository.py`. Populate from `_extract_emails` results already computed at `composio.py:366-370`.
- Blocks: HKS-L1-01/02; A-L1-01/02; every L2 identity/relationship split.

**L1-06 · No fundraising/investor domain exists → 95.9% of events reach L2 with no hint** `[CODE]` `medium`
- Unit: `capture/domain/hints.py:10-20` (6 source priors, 3 domains × 8 keywords); `capture/coverage/model.py:11-18` (same 3 domains)
- Impact: 1,307 of 1,363 events unhinted; only 4 distinct hint shapes ever (sales 34, support 10, admin 6, sales+support 6), zero `scope`, zero `history`. Rohit raises money from investors, accelerators and VCs — L1's entire vocabulary cannot express that. Upstream half of "only 7 of 25 rules fire".
- Fix: `hints.py` stops owning the vocabulary. Take domains + keyword evidence from `packs/registry.py::effective()['capture'].classifier_hints`; pass org/pack into `domain_hints(source, text)`. Add `fundraising` to `coverage/model.py::PACK_REQUIREMENTS` in the same change. **Depends on L3-08.**
- Blocks: any pack-driven capture; the fundraising half of the graph.

**L1-07 · Parked queue has no drain: 286 pending, 0 of 394 documents parsed** `[CODE]` `medium`
- Unit: `capture/parked/store.py` (no retry, no SLA, no scheduled caller)
- Impact: DOC-02/pending 262 (since 2026-08-17 11:23), DOC-05/pending 24. DOC-05 is explicitly retryable per `rules.py:104` and is never retried. One in five captured emails sits in a queue nobody empties — a slower black hole.
- Fix: retry pass for retryable reason codes driven from the existing in-process sync sweep (**not** a new Celery periodic task — Upstash quota), re-entering `capture/pipeline.py::capture_event` with the retained payload; add age/owner surface to `parked/store.py`.
- Blocks: any "L1 never silently deletes" claim; attachment-derived evidence for HKS-L1-06.

**L1-08 · `route_document` returns `unsupported` for scanned files — "cannot read" and "chose not to read" are indistinguishable** `[CODE]` `small`
- Unit: `capture/documents/router.py:31-34`; `platform/config.py enable_ocr=False` → `wiring.make_ocr()` returns None. Also `_NATIVE_MIMES` (`router.py:6-11`) is declared and read by nothing — MIME type plays no part in routing.
- Impact: 369 documents labelled with a terminal-sounding reason when many are ordinary scanned PDFs Tesseract would read. The fix ("turn on OCR") is invisible from the data.
- Fix: split the fallback into `ocr_unavailable` (image_ref present, engine None) vs `unsupported`; add the code to `REASON_LABELS` and the DOC park branch; enable `enable_ocr` where the binary exists; let L1-07's retry re-run them.
- Blocks: correctly sizing the parked backlog.

**L1-09 · `compute_coverage` fails OPEN for any unregistered domain** `[CODE]` `small`
- Unit: `capture/coverage/model.py:45` (`PACK_REQUIREMENTS.get(domain, {"required": [], "recommended": []})`) then `:65` (`coverage_ready = len(missing_required)==0`)
- Impact: ask for coverage on `fundraising` — the design partner's actual domain — and L1 answers "ready" with nothing connected. Negative predicates ("they did not reply") then look licensed. Contradicts the module's own docstring at `:7-8`.
- Fix: unregistered domain → `coverage_ready=False` with an explicit `unknown_domain` reason; all `_READINESS` predicates False in that branch.
- Blocks: every negative-inference gate downstream.

**L1-10 · `GatedEvent.coverage_ready` is declared and never assigned** `[CODE]` `small`
- Unit: `contracts/gated_event.py:34` (declared `bool | None = None`); `capture/pipeline.py:92-113 _build_gated_event` — the only constructor — never sets it; only writer is `coverage/model.py:65`, whose return never reaches the pipeline
- Impact: a dead field on a contract is worse than a missing one — it invites false confidence at the seam.
- Fix: bind `compute_coverage` output into `_build_gated_event`, or delete the field. Do not leave it declared and unwritten.
- Blocks: P0.4 scoped completeness.

**L1-11 · Mutable-object versioning optional → a CRM/DB row freezes at first-seen state forever** `[CODE]` `medium`
- Unit: `contracts/source_event.py:21-29` (`compute_dedup_key(..., content_version=None)` returns the versionless base key); `capture/source_registry.py` declares no immutable-vs-mutable flag
- Impact: latent for this org (gmail immutable, gcal versions). The first HubSpot or client-DB connection silently freezes deal stage or account status with every generic test still green.
- Fix: `immutable: bool` / `version_field: str|None` on `source_registry` descriptors; `normalize.to_source_event` parks with `versionless_mutable` when a declared-mutable source arrives without `content_version`.
- Blocks: HKS-L1-07, A-L1-08; must close before HubSpot/client-DB for a paying tenant.

**L1-12 · `make_connector_for` returns `FakeGmailConnector` for every source type in dev** `[CODE]` `small`
- Unit: `platform/wiring.py:60-64` (`if not s.use_real_composio: return FakeGmailConnector(...)` above every source branch, ignores `st`)
- Impact: not a production data path, but any local run or demo can appear to prove Notion/HubSpot coverage using Gmail fixtures — unfalsifiable exactly where it gets shown.
- Fix: dispatch the fake by source type or raise for source types with no fixture; assert `connector.source == connection.source_type` for every buildable id in `tests/test_source_registry.py`.
- Blocks: trusting any local/demo claim about non-Gmail coverage.

**L1-13 · No deletion or revocation path — absence on a later sync is indistinguishable from deletion** `[CODE]` `new_subsystem`
- Unit: whole package is append-oriented; `contracts/source_event.py:33-35` has no tombstone type; no revocation reason code in `REASON_LABELS`
- Impact: if the founder deletes an email, revokes a share or disconnects a source, GeniOS keeps reasoning from it indefinitely. Correctness, trust, and a GDPR deletion-propagation exposure.
- Fix: tombstone event type; connector-side deletion detection in `composio.py`/`calendar.py`; a revocation projection marking dependent graph facts superseded. Nothing current extends into this.
- Blocks: A-L1-09; enterprise deletion conversations.

**L1-14 · The QualifiedEnterpriseSignal boundary object does not exist (RC-1 / B-01)** `[CODE]` `new_subsystem`
- Unit: `contracts/gated_event.py` — operational routing object standing in for a business contract
- Impact: root cause #1 of the entire chain. Requester/connector/target/owner, source visibility+permitted_use, lifecycle and source-readiness are not ONE mandatory versioned boundary, so nothing above L1 can be safe even when its own code is correct.
- Fix: introduce and version a QES mapping carrying immutable source/span/version, typed transport actors, explicitly UNRESOLVED business roles, visibility/use, readiness and lifecycle. Park rather than synthesize. Composes L1-04 + L1-05 + L1-09 + L1-10 into one contract.
- Blocks: RC-2 through RC-7; every CP stage from CP-1 onward.

**L1-15 · Background capture sweep is not demonstrably bound by the platform USD cap** `[CODE]` `small`
- Unit: `platform/config.py daily_llm_usd_cap=25.0`; `api/routes.py:1088-1139` (20,000-daily-call breaker) — neither is proven to bind the capture sweep
- Impact: theoretical at current volume; would matter on a large backfill.
- Fix: route the S2 relevance call through the same cap/breaker check the intelligence paths use; assert it in a test.
- Blocks: nothing today; a large-backfill safety item.

---

## L2 — CONTEXT INTELLIGENCE
**Package:** `genios_engine/context/**`

### [ATLAS] What it must do
Take qualified L1 signals and assemble **current business reality** — never reasoning. Resolve identity without unsafe joins; scope state to the **relationship / thread / opportunity**, not the human; cross-correlate tool, timeline, conversation and dependency; separate confidence, freshness, conflict, coverage and identity into an explainable vector; run situation lifecycle (active/dormant/resolved/archived) and reopen on new scoped evidence; hand L3 ONE versioned `BusinessSituationObject` carrying exact qualified-signal membership, source-authoritative receipts, a roleful entity set (requester / connector / owner / target / approver), typed relationships and dependencies, a state timeline, the narrowest surviving visibility, and explicit `missing_fields`. An incomplete handoff fails closed as `observation_only` / `review_source` / `split_required` / `suppressed_policy`. LLM = model-assisted extraction only; identity merge, correlation, fact authority, confidence, coverage, lifecycle, permissions and BSO validity are 0% LLM.

### [CODE] What it actually does
The deterministic primitives are genuinely good: `graph_store.py:29-223` versions fact writes and records discrepancies; `identity.py:10-31` refuses fuzzy auto-merge; `correlation.py:187-209` does thread-first continuity with a 45-day weak window; `situations.py:100-224` computes a minimum-of-dimensions trust vector. Live: 234 nodes, 998 current facts, 285 edges, 1,210 observations, 3,132 source refs, 73 correlations / 221 members, 73 situations, 420 runs all `done`. **And that output is orphaned.** `reason/runner.py:610-640` selects `graph_nodes ... where valid_to is null`, loops node-by-node, builds `NodeContext` from bulk-loaded facts/observations. `context_situations`/`context_correlations` are read only by `api/situation_routes.py`, `api/home_routes.py`, L2-internal modules, and `reason/domain_shadow.py` — which `reason/runner.py:528` gates on `use_domain_compiler=False`.

### Complete gap list, ranked

**L2-01 · The entire situation/correlation/BSO substrate is computed and then discarded — no live decision path reads it** `[CODE]` `large`
- Unit: `reason/runner.py:610-613` + `:639` (`_load_context` → `NodeContext`, `reason/engine.py:16`); `context/situation_bso.py` imported only by `reason/domain_shadow.py:23-26`, gated at `reason/runner.py:528` on `platform/config.py:89`
- Impact: everything L2 knows about grouping — that 68 Boardy events are one thread family, that a situation is dormant, that coverage is 50%, that confidence_overall is 33 — has **zero** effect on what Rohit sees. Cards come from a single person row's facts. **The audit's entire L2 P0 register edits a file that does not execute in production.**
- Fix: flip the consumer. `reason/runner.py::run` iterates `context_situations` and loads a situation-scoped context beside `_load_context` — or the situation layer is declared decorative and the claim is deleted.
- Blocks: every L2 P0 in the audit; any honest L3 activation (the compiler's only input is the BSO).

**L2-02 · Company-tier anchoring fuses every counterparty sharing an email domain — the Boardy chimera is real, not modelled** `[CODE]` `large`
- Unit: `context/correlation.py::choose_anchors` + `ANCHOR_PRIORITY` (returns only the strongest tier; docstring: "An email to a person at a company yields ONE company-anchored situation")
- Impact: `corr_7aeab691…` anchored on node `boardy.ai` holds **68 correlation members**; `crescerelabs.com` holds 11. Situation anchors org-wide: 48 company / 25 person. Every person Boardy introduced is inside one situation whose subject is a connector bot. **The audit classes this `[SCREENSHOT][MODELLED]`; live data makes it `[CODE]`.**
- Fix: stop collapsing to the strongest tier when the company node is high-degree or the event's `thread_id` differs from the group's existing threads. Minimum viable: `Anchor.base_key` includes `thread_id` for email-sourced events.
- Blocks: role graph (P0.1), opportunity separation (P1.4), the Boardy golden replay.

**L2-03 · `thread.ball_in_court` is one row per person, last-write-wins across every thread — and it drives 54% of live signals** `[CODE]` `medium`
- Unit: `context/pipeline.py:565-583` writes `thread.ball_in_court` on `sender_node`/`rnode`; `graph_facts` keys on (subject_node_id, field) so the second thread supersedes the first. Consumer: `packs/general_v1.py:41-46 unanswered_email` = 22 of 41 signals
- Impact: 6 person nodes carry a `thread.ball_in_court` fed by more than one `parent_object_id` — `boardy@boardy.ai` = **11 threads**, `rohit@crescerelabs.com` = 7, `adityad@iima.ac.in` = 3. "Reply to Boardy" because one of eleven unrelated introduction threads landed last.
- Fix: write thread-scoped subjects (first-class `thread` node keyed on `source_events.parent_object_id`, or field-path `thread.<id>.ball_in_court`); repoint `unanswered_email`, `champion_quiet`, `objection_open` off the person-global path.
- Blocks: the three highest-volume prescriptive rules.

**L2-04 · `org_seats` is empty → L2's entire internal/self-exclusion is a no-op; the founder and his own company are correlated as counterparties** `[CODE]` `small`
- Unit: `context/runner.py::_internal_emails` reads `org_seats` (**0 rows**) → `pipeline.py:333 internal_set = frozenset()` → `:306-308`/`:323-325` never populate `internal_nodes` → the filter at `:644` passes everything. The code comment at `:320-322` predicts exactly this.
- Impact: `corr_7a50b2f8…` anchored on `Mr Rohit Swerashi` holds 18 members; `context_situations` types `Mr Rohit Swerashi` as `sales/prospect_relationship` and `thegenios.com` as `sales/opportunity`. **GeniOS models its own user as a sales prospect.** Every outbound-only guard at `pipeline.py:564,578` is disabled, so teammate replies flip ball_in_court like prospect replies.
- Fix: `_internal_emails` falls back to `orgs.email` + connection account addresses when `org_seats` is empty — `reason/runner.py:618-622` already does exactly this via `self_keys`. Backfilling the table alone is not the fix; a safety guard must not depend on an optional table.
- Blocks: correlation cleanliness for every anchor-based grouping.

**L2-05 · No fundraising/investor domain in L2 → nine investors and accelerators typed as sales opportunities** `[CODE]` `medium`
- Unit: `context/correlation.py::resolve_domain` takes the FIRST hint, else `DEFAULT_DOMAIN='general'` (`:120`); `context/domain_spec.py:134-175` registers exactly sales, support, admin, general
- Impact: domain='sales' situations for this org are `3one4capital.com`, `afore.vc`, `neon.fund`, `peakxv.com`, `titancapital.vc`, `together.fund` (six VCs), `zfellows.com`, `iima.ac.in`, `bharatkesuperfounders.com` (accelerators) — all typed `opportunity`; plus `boardy.ai` twice and `thegenios.com`. **Zero of 16 sales-domain situations is a customer.** 52 of 73 situations are `general/relationship`.
- Fix: add a `fundraising` pattern to `capture/domain/hints.py::_KEYWORDS` (term sheet, deck, LP, cheque, diligence, allocation, SAFE, round, cap table) and stop letting `budget|contract` alone route an investor thread to sales; `register(DomainSpec(domain="fundraising", situation_types={"company":"investor_relationship","person":"investor_contact"}, ...))` in `context/domain_spec.py`.
- Blocks: any honest fundraising card; the Theresa/Antler replay (HKS-L2-01).

**L2-06 · Extraction schema has no role vocabulary — nothing downstream can ever be role-scoped** `[CODE]` `medium`
- Unit: `context/extract/prompt.py::B3_PROMPT` returns `relevance, noise_type, domains, entity_mentions, fact_candidates, commitments, questions, observations`; `entity_mentions` = `{type,name,email,evidence_text}` with no role; `situation_bso.py:105-141` therefore leaves `relationships`/`dependencies` at contract default
- Impact: the data required to populate a role graph is never extracted. Any attempt to emit requester/target from the current pipeline would have to invent it.
- Fix: typed `roles` array in the SAME call (`{person, role: requester|connector|target|owner|approver, relative_to, evidence_text}`) under the exact-substring grounding rule; write role edges in `pipeline.py` rather than only `corresponded_with`/`works_at`. Deterministic From/To/Cc pre-fill first, model only fills the ambiguous multi-actor case.
- Blocks: P0.1 entirely; the Boardy and multi-role replays.

**L2-07 · `commitments` extraction has no definition of a commitment → scheduling questions become overdue obligations** `[CODE]` `small`
- Unit: `context/extract/prompt.py` defines commitments as `{actor, action, due_text, evidence_text}` with no negative examples and no distinction from a proposal, question or calendar description; `context/pipeline.py:601-616` turns each into a `commitment` node
- Impact: live `graph_facts.field='commitment.text'` values, verbatim: *"What does your next week look like for a quick call?"*, *"Can we do next week?"*, *"Thursday 20 Aug 2026 ⋅ 11:15am – 11:45am"*, *"could we push the call to next Monday at 13:00 Barcelona time instead?"* Consumer `packs/general_v1.py:35-39 commitment_overdue` is `level=prescriptive`, fired 9×. 179 of 260 extractions returned zero `questions` — scheduling asks land in the wrong array. **The audit never inspected extraction output content and misses this entirely.**
- Fix: define a commitment as an explicit first-person promise with an owner and a deliverable; add three negative examples; route scheduling asks to `questions` or a new `scheduling_proposals` array; deterministic post-gate in `pipeline.py:601` rejecting a commitment whose `evidence_text` ends in `?` or contains no verb of obligation.
- Blocks: any credible `commitment_overdue` card; the meeting-lifecycle replay.

**L2-08 · Commitment dual-write collides on (subject, field); "us"-actor commitments land on the owner node where L4 self-excludes them** `[CODE]` `medium`
- Unit: `context/pipeline.py:617-630` (legacy dual-write of `commitment.due_at`/`.action` onto the person, latest-wins); `pipeline.py:224-227 _resolve_subject` falls back to `sender_node` when the actor is unresolvable and the prompt allows `actor:"us"`; `reason/runner.py:618-631` excludes nodes matching `orgs.email`
- Impact: 24 commitment nodes exist; only **15** person-level `commitment.due_at` facts survive → 9 lost to field collision. `owns` edges: `Mr Rohit Swerashi` 8 — **the founder's own promises are captured, stored, then structurally unreachable.** 9 lost + 8 unreachable of 24.
- Fix: delete the legacy person-level dual-write; repoint `commitment_overdue` to `scope="commitment"` reading off the commitment node (nodes + `owns` edges already exist); exempt `node_type='commitment'` reached via an owner `owns` edge from `reason/runner.py`'s self-exclusion.
- Blocks: nothing downstream — the cheapest large win available.

**L2-09 · 34 of 73 situations report `missing=[]` and 100% coverage because `general/relationship` expects ONE trivially-satisfied field** `[CODE]` `small`
- Unit: `context/domain_spec.py:168-175` (`expected_fields={"relationship": {"thread.ball_in_court": "whose turn it is"}}`), written mechanically by `pipeline.py:565-583` on every inbound message; `context/situations.py:165-175 coverage_score`
- Impact: `missing` distribution — `[]` ×34, `["whose turn it is"]` ×25, `["agreed next step"]` ×9, both ×4, `["renewal date"]` ×1. Nearly half of this org's situations are declared context-complete on the strength of knowing who sent the last email. **The audit blames unregistered domains; the live cause is a REGISTERED spec — fixing the unregistered default moves zero of these 34 rows.**
- Fix: relationship expected fields must include at least a counterparty role and an open object; `coverage_score` returns `coverage_status='unknown'` rather than 100 when `fields_for()` returns fewer than N entries.
- Blocks: P0.4 acceptance ("0 actionable output when required context is unknown") would read green today.

**L2-10 · The LLM's own `domains` judgment is extracted, persisted into observation evidence, then discarded** `[CODE]` `small`
- Unit: `context/extract/extractor.py:57` parses `Extraction.domains`; `context/pipeline.py:547-555` writes it into observation evidence; `pipeline.py:643-647` passes the **L1** `domain_hints` parameter (from `process_event`'s signature at `:237`) to `correlate_event`, never `ex.domains`
- Impact: built, output discarded. The one semantic domain judgment made by a model that read the whole email is overruled by an eight-keyword regex that has never heard of fundraising. The `capture/domain/hints.py:6` header comment claiming "L2's combined call decides the real domain" is false.
- Fix: merge `ex.domains` into the hint list passed to `correlate_event`, ranked below a source prior and above a keyword match; record `selected_by` provenance on `context_correlations`.
- Blocks: prerequisite for L2-05's fundraising domain to take effect on free-text email.

**L2-11 · `graph_source_refs.source_object_id` is NULL on all 3,132 rows — receipts cannot be traced to a provider message** `[CODE]` `small`
- Unit: `context/graph_store.py::write_fact/write_edge/write_observation`; the value is available as `source_events.source_object_id` and is already passed to `commit_structured` in `runner.py:71-74` but not to the unstructured lane
- Impact: `situation_bso.py:88-98` builds receipts from these rows, so every receipt carries `source_object_id: null`. There is no path from a card back to the Gmail message that caused it. `evidence` carries only derivation labels (`{"derived":"email to/cc"}`).
- Fix: thread `source_object_id` through `pipeline.py::process_event` into every source-ref write.
- Blocks: P1.7 runtime lineage trace (exit gate 100%); the audit's own demanded next proof.

**L2-12 · BSO producer defects — synthetic membership fallback, hardcoded org visibility, empty `missing_fields`, constant importance (LATENT, zero live incidence)** `[CODE]` `small`
- Unit: `context/situation_bso.py:100-103` (`sig:<situation_id>` + `{"source":"situation","reconstructed":True}`), `:126`/`:159` (`Visibility(scope="org", derived_from="l2:situation")`), `:129` (`importance_bp=DEFAULT_IMPORTANCE_BP` 5000), `:165` (`missing_fields=()`)
- Impact: **221/221 correlation members have matching `graph_source_refs`** → the synthetic fallback fires on 0 of 73 situations; **all 998 current facts are `visibility_scope='org'`** → nothing narrower exists to widen. The audit ranks these P0.2/P0.3; they buy zero customer-visible improvement today. They become P0 the moment L2-01 flips the seam live and a sub-org-visibility source is connected.
- Fix: `gather_evidence_and_signals` raises/flags rather than synthesising; `build_business_situation`/`build_context_slice` intersect `graph_facts.visibility_scope` across members instead of passing a literal.
- Blocks: nothing today; gated on L1-04 emitting a restricted scope.

**L2-13 · Extraction cache key omits model id and schema version — a model swap silently reuses stale extractions** `[CODE]` `small`
- Unit: `context/pipeline.py:242` (`content_hash(f"{org_id}:{PROMPT_VERSION}:{content}")`); `l2_extraction_results.model_snapshot` is written but never read at lookup
- Impact: **must land BEFORE any prompt work** — the org has 260 cached extractions; ship L2-06/L2-07 without a key change and you measure nothing.
- Fix: include `llm.model` and an `EXTRACTION_SCHEMA_VERSION` constant in the hashed key, or reject a row whose `model_snapshot` differs from the caller's model.
- Blocks: any A/B measurement of L2-06/L2-07; the audit's cache-isolation exit gate.

**L2-14 · The BSO is not bounded to one relationship + open loop; there is no `open_loop_id` / stable request identity (RC-2 / B-02)** `[CODE]` `large`
- Unit: `context/situation_bso.py:110-118` builds `entities` as a one-element tuple from `anchor_node_id`
- Impact: root cause #2. Every later layer reasons about the wrong unit even when its own code is correct — Boardy ×68, the founder's own availability quote as an overdue debt, completed work resurfacing.
- Fix: make relationship / opportunity / thread / open_loop_id first-class; require real member evidence; version-fenced blocking BSO validator; return `split_required` when one anchor carries multiple unresolved asks.
- Blocks: RC-3 onward; replay 04's completion matcher; L7's entire ledger.

**L2-15 · No meeting/request lifecycle reducer — `scheduled`, `occurred`, `attended`, `external_counterparty`, `open_loop` are collapsed into `meeting.status`** `[CODE]` `medium`
- Unit: `context/` has no reducer; `packs/general_v1.py:56-62 meeting_no_followup` fires on `meeting.status='confirmed'` (INVITATION state) + `hours_since(start_at)>=24` + `no_obs: followup_sent`
- Impact: three live cards tell the founder to send a recap of cohort workshops he attended as a participant — `[Session] Building Your MVP | Launchpad 30`, `[Session] Early Finance AMA | Launchpad 30`, `[Session] Building Early Metrics Stack`. A group-wide send here leaks the cohort list. Replay 05's assertion 3 forbids exactly this aliasing.
- Fix: split into five independent fields no rule may alias; add typed proposer/responder/organizer and ordered proposal → acceptance → supersession → cancellation states (replay 03 needs the same reducer).
- Blocks: replays 03 and 05; L4's meeting rules.

**L2-16 · No current-state reducer / exact completion matcher — completion authority is person-wide `thread.ball_in_court`** `[CODE]` `large`
- Unit: `packs/general_v1.py:42` is the entire completion authority — the exact signal replay 04 names as prohibited
- Impact: signals resurface. `boardy@boardy.ai` holds `unanswered_email` twice (expired 56, open 52) and `commitment_overdue` twice (expired 45, open 44); the same expired/queued pairing recurs for **eleven** other subjects. HEAD commit `b739bd5` is literally titled *"Let a signal get a fresh card once its old one expires"* — the resurfacing is currently intentional. There is no evidence of a reply ever closing anything.
- Fix: stable request/action identity + ordered current-state reducer + exact completion matcher keyed on thread, target, relationship and completion predicate. A match closes ONE request, never a person. Gate regeneration on "the loop is still genuinely open", not "the card expired".
- Blocks: replay 04; L7's entire ledger (no Completion stage to attribute from).

**L2-17 · Identity alias collision: same-name people share one alias key, first claimant holds it** `[CODE]` `medium`
- Unit: `context/identity.py:134-145` — states it in its own docstring
- Impact: two "John" contacts at different companies merge into one node; every fact, commitment and thread state written to the loser goes to the winner.
- Fix: alias key must include a disambiguator (domain, thread, or explicit unresolved state); collision → `review_source`, never silent first-claimant.
- Blocks: any per-contact lifecycle assertion; replays 09 and 12.

---

## L3 — DOMAIN EXPERTISE
**Package:** `genios_engine/packs/**` (legacy `sales_v1`/`general_v1` + new `compiler/`) + the `Domain Expertise/` corpus

### [ATLAS] What it must do
Turn a role-correct BSO into an immutable, byte-replayable `ExpertisePackage`: situation → capabilities → objects → four-brain snapshot → package → L4. It never decides; it makes good choices possible and bad choices invalid. Permission runs Organization → Expert and learned brains can never grant it; preference runs Adaptive → Organization → Behavior → Expert. Only **reviewed/accepted, exact-hash** capability versions may authorize prescriptive reasoning; a stub, draft, unrouted or unsupported situation returns **typed abstention** with no action-authorizing playbook, never a nearest-route fallback into generic Sales. The pack's declared vocabulary (`schema.fields`, `schema.signal_vocab`, `capture.classifier_hints`) is L3's **outbound contract** and steers what L1 keeps and what L2 extracts. Runtime LLM authority = 0%.

### [CODE] What it actually does
Live path is entirely the old packs: `packs/wiring.py` registers SALES_V1 (v1.10.0, 20 rules) + GENERAL_V1 (v1.1.2, 5 rules); `reason/runner.py:528` calls the new compiler only behind `platform/config.py:89 use_domain_compiler=False`. New path is built well and entirely inert: `reason/domain_shadow.py:82` passes `publisher=None`, `reason/adapters/expertise.py:200` sets `live_delivery_enabled=False`, `expertise_packages` = 0 rows. Corpus verified at HEAD: **152 `capability.yaml`, 152 `status: draft`, 152 `review_status: unreviewed`, 0 reviewed, 0 accepted**; 1,748 files total.

### Complete gap list, ranked

**L3-01 · Route-key vocabulary mismatch — the corpus routes on L3 pack reason_codes while the compiler looks up L2 `situation_type`. Zero overlap.** `[CODE]` `large`
- Unit: `packs/compiler/capability_resolver.py:63` (`domain.routes.get(situation.type)`) vs `context/situation_bso.py:128` (`type=str(situation['situation_type'])`) vs `context/domain_spec.py:139-176` (the closed 8-value vocabulary); corpus index keyed on 20 reason_codes; `Domain Expertise/_schema/vocabulary.yaml:149-152` says the substrate is "Union of both packs' schema.signal_vocab"
- Impact: **73/73 = 100% NoExpertiseRoute** in an in-process run against the real `ExpertBrainCatalog`. Flipping `use_domain_compiler=True` tomorrow yields `no_route: 73, compiled: 0`. The 1,748-file corpus, the compiler, the L3→L4 weld and the whole L3 investment currently return literally nothing for any customer. **The audit reports "Routed L2 types: Sales 19, Support 5" — those are reason_codes, not situation types. Real routed-L2-type count is ZERO for all three domains.**
- Fix: re-key `Domain Expertise/*/capabilities/**/situations/*.yaml` `matches.l2_situation_types` onto the `domain_spec` vocabulary, promoting reason_code to a `matches.when` predicate; regenerate `registry/situation-capability-map.yaml` via `_tools/index.py`; regenerate `_schema/vocabulary.yaml:substrate` FROM `domain_spec.py`. (Alternative — changing `context/situations.py::situation_type()` — moves a contract L4/L5/cards already depend on; do not.)
- Blocks: **everything in L3.** No shadow parity, no route-disposition metric, no review-admission value, no promotion lane, no golden replay. Do not fund a single line of corpus authoring until this is closed.

**L3-02 · Domain-id mismatch on top of the route mismatch — L2 emits `general` and `support`; the catalog knows `sales`, `customer_support`, `admin`** `[CODE]` `medium`
- Unit: `packs/compiler/capability_resolver.py:44-47` raises `NoExpertiseRoute` on any unknown domain; catalog ids from `Domain Expertise/*/domain.yaml`; `context/domain_spec.py:169-176` registers `general`
- Impact: **56 of 73 live situations die on the domain name alone**, before the route key is consulted — 53 `general`, 3 `support`. `general` has no authored domain at all and is 73% of this org's traffic.
- Fix: alias map at the read boundary in `situation_bso.py::build_business_situation` (same pattern as `runtime_brains.py::_L6_SCOPE_ALIASES`) mapping `support→customer_support`; do **not** alias `general→sales`. Owner decision on `general`: author a fourth domain, or return typed `UnsupportedDomain`.
- Blocks: any measurement of L3 route coverage; the "Route disposition coverage = 100%" metric.

**L3-03 · Review-state admission does not exist — `identity.stub` is the entire production-admission ceremony** `[CODE]` `medium`
- Unit: `packs/compiler/capability_resolver.py:96-105` is the ONLY read of `identity.stub` and reads nothing else from identity/metadata; `grep -rn 'review_status|reviewed_by' genios_engine/` → **zero hits**; `_tools/validate.py` never inspects them
- Impact: an author flipping `stub: true → false` in a text editor grants production authority. Once L3-01 is fixed, the first thing to gain customer authority is 12 machine-written unreviewed drafts (`metadata.created_by: ai`). The Gold Standard card requires `expertise.review_state: "accepted"` — a value no file in the repository can produce.
- Fix: admission gate in the `capability_resolver.py:99-105` loop requiring `identity.status in {stable}` AND `metadata.review_status == 'approved'` AND non-empty `metadata.reviewed_by` AND `admission.accepted_content_hash` matching the catalog's computed `SourceDocument.content_hash`; reject on transitive-dependency closure whose hashes are not all accepted. Mirror as a hard error in `_tools/validate.py` so CI blocks before runtime.
- Blocks: any live cutover; promotion of even one capability; CP-2 entirely.

**L3-04 · `accepted` is unrepresentable — no `accepted`/`accepted_at`/`accepted_by`/`accepted_hash` field exists anywhere** `[MODELLED]` `small`
- Unit: `Domain Expertise/_schema/capability.schema.json` (highest states: `identity.status: stable`, `metadata.review_status: approved`); verified absent from all 10 schemas, corpus, engine and `expertise_packages`
- Impact: **none today** — flagged so nobody spends a sprint hunting a broken acceptance pipeline that was never built, and nobody reads the audit's "zero accepted" as a regression.
- Fix: add an `admission` block to `capability.schema.json` carrying `accepted_by` / `accepted_at` / `accepted_content_hash`; treat `review_status: approved` as necessary-but-not-sufficient. Ship with L3-03.
- Blocks: L3-03's hash-binding half; the "accepted artifacts per reviewer-hour" metric.

**L3-05 · Organization / Behavior / Adaptive brains have zero semantic consumers in the L3→L4 adapter — and zero rows to consume** `[CODE]` `large`
- Unit: `reason/adapters/expertise.py:184-186` — the three names appear **exactly once each**, inside the `semantic_hash()` dict; `_plays()` (`:106-152`) reads only `expert_rules`; `_goal()` (`:155-168`) only a capability question; `_default_dag()` (`:57-103`) is situation-agnostic; `policies=("read_only","human_approval_required","evidence_required")` and `constraints` are hardcoded literals. DB: `learned_brain_entries` = **0 rows, all orgs**; `learning_objects` = 3, all `state='governed'`
- Impact: hash-of-nothing. Mutating a Company approval rule produces a new manifest version and a new content hash while goal, constraints, policies, DAG, play eligibility and ranking inputs stay byte-identical. Any product claim that GeniOS applies "your company's policy" is false twice over.
- Fix: typed projections in `expertise.py`, one function per brain, with an authority split — org rules → `policies`/`Goal.constraints` (may eliminate candidates); behavior patterns → reorder already-eligible candidates only; adaptive preferences → bounded expiry/urgency with mandatory TTL. Each writes a per-entry applied/unused receipt into `CapabilityManifest.metadata`, persisted by `reason/audit.py::audit_bundle`. **Prerequisite:** L7-01 and L7-02 must first make `learned_brain_entries` non-empty.
- Blocks: any L3 activation; the four-brain mutation replay; every personalization claim.

**L3-06 · Every compiler test hand-builds `situation_type="buying_signal"` — a value production can never emit — so L3-01's 100% route failure is invisible to CI** `[TEST]` `small`
- Unit: `tests/test_domain_expertise_compiler.py:158`; `tests/test_expertise_adapter.py:24`. Neither value is producible by `context/situations.py:83 situation_type()`
- Impact: this is why nobody caught L3-01 in months, and why the audit accepted the corpus's own `routed_l2_types` field at face value. Green CI actively certifies the bug.
- Fix: build fixtures from `context.domain_spec.spec_for(domain).type_for(anchor_type)`; add one contract test asserting `set(catalog.domain(d).routes) <= set(all domain_spec situation_types)`. **Land this BEFORE the L3-01 re-keying so the re-keying has an oracle.**
- Blocks: verification of L3-01.

**L3-07 · The corpus validator validates against a substrate that does not exist — "0 errors, 715 warnings" certifies nothing about routability** `[CODE]` `small`
- Unit: `Domain Expertise/_tools/validate.py:108` loads `l2_types` from `_schema/vocabulary.yaml:149-151`, errors at `:250-254` on any situation binding outside it. Its loudest check (header line 22: "Every situation binds to types Layer 2 actually emits") is **inverted** — it would ERROR on a correct binding and passes every incorrect one.
- Impact: the audit inherited this false premise and reported 76% route coverage where the truth is 0%.
- Fix: source `l2_types` from a generated census imported from `genios_engine.context.domain_spec`; regenerate `vocabulary.yaml:substrate.l2_situation_types` from the same source. **Land with L3-01 or the re-keying is validated by the same broken oracle.**
- Blocks: trustworthy corpus CI.

**L3-08 · The pack's OUTBOUND seam is severed: `registry.effective()` drops `manifest["schema"]` and `manifest["capture"]`** `[CODE]` `large`
- Unit: `packs/registry.py:139-142` builds `{pack_id, version, state, scoring, rules, plays, templates}` — schema and capture are never copied and never persisted in the snapshot. `capture.classifier_hints` has **ZERO consumers** anywhere in `genios_engine`; `schema.signal_vocab` has exactly one — `api/expertise_routes.py:93`, reading the raw manifest for UI display, not `effective()`
- Impact: L3 cannot tell L1 what to keep or L2 what to extract. A sales pack and a support pack produce byte-identical L1 gating and L2 extraction. Direct contributor to 657/1,306 emails dropped and 15/21 sales rules dead. **Absent from all six L3 audit docs.**
- Fix: pass `manifest.get('schema')` and `manifest.get('capture')` through `effective()` and `persist_effective_snapshot`; give `capture/domain/hints.py::domain_hints()` a `vocab` parameter; convert `context/extract/prompt.py` from a module constant to `build_prompt(*, signal_vocab, fields, classifier_hints)` called from `extractor.py`.
- Blocks: **L1-06 and L2-06 have no vocabulary source without this.** Must land in Phase 1, not Phase 2.

**L3-09 · Corpus depth: 149 of 152 capabilities are stubs, all 12 non-stubs are unreviewed AI drafts, Admin has zero routes, 10 routes resolve to nothing but stubs** `[CODE]` `new_subsystem`
- Unit: the corpus itself. Verified at HEAD: Sales 46/43 stub/3 non-stub; Support 49/40/9; Admin 57/57/0. All 152 draft + unreviewed + empty `reviewed_by`. All-stub routes: Sales 7 (contract_requested, deal_health, going_dark_after_proposal, legal_in_review, security_review_pending, single_threaded_deal, verbal_yes_not_closed), Support 3, Admin 0-of-0. Orphans: Sales 28, Support 39, Admin 57
- Impact: "Sales: 46 capabilities" is 3 unreviewed drafts. Admin — the domain carrying the highest-harm HKS (bank-detail change / financial fraud) — cannot responsibly prescribe anything.
- Fix: a content programme executed one lane at a time (see §4). **Split:** L3-09a = the ONE lane (Phase 2); L3-09b = full Sales remainder → Support → Admin (Phase 8). First lane must serve whatever `general`/`relationship` resolves to under L3-02 — 73% of Rohit's traffic — not the easiest Sales files.
- Blocks: any customer-visible quality improvement from L3 — but is itself BLOCKED BY L3-01, L3-02, L3-07.

**L3-10 · An all-stub route raises an untyped `AuthoringIntegrityError`; the shadow pass swallows it into a generic error counter** `[CODE]` `small`
- Unit: `packs/compiler/capability_resolver.py:137-139`; `packs/compiler/errors.py` has no abstention type (all seven subclasses are `RuntimeError`); `reason/domain_shadow.py:120-134` drops it into `counts["error"] += 1`
- Impact: when L3-01 is fixed and routes start matching, all-stub routes register as indistinguishable error noise rather than the `all_stub` disposition the route-coverage metric depends on. A live cutover would surface an exception, not an honest "we do not cover this yet".
- Fix: add non-error `UnsupportedCoverage` to `errors.py` with `reason ∈ {no_route, all_stub, unreviewed, unsupported_domain}`; return it from `:137-139` and `:129-135`; add matching counters in `domain_shadow.py`. **Land with L3-01.**
- Blocks: "Route disposition coverage = 100%" and "Unsupported prescription rate = 0%".

**L3-11 · Activation is one global boolean, not a scoped promotion key; the 17-unit capability is imported and deliberately excluded** `[CODE]` `medium`
- Unit: `platform/config.py:89 use_domain_compiler: bool` (process-wide, no tenant/domain/situation dimension), read at `reason/runner.py:528`; `packs/capabilities/__init__.py:22 BUILTIN_CAPABILITIES = (DEAL_COOLING_V1,)` — LOCK 1
- Impact: the only available move is all-domains-all-situations-all-orgs, which the audit correctly calls unsafe. No kill switch narrower than a redeploy.
- Fix: replace the boolean with a promotion table keyed on `(org_id, domain_id, situation_type, capability_id, accepted_version)`, reusing the existing `tenant_packs` + `_pack_authority_revision` pattern at `reason/runner.py:536-545` rather than inventing a second mechanism.
- Blocks: any cutover for the design partner. Design it now so L3-03's admission receipt has somewhere to be checked.

**L3-12 · Six L2 types are globally unrouted — two of them fire live for this org — plus 15 orphan Sales capabilities and 1 unreachable object** `[CODE]` `medium`
- Unit: `Domain Expertise/Sales Expertise/registry/situation-capability-map.yaml` §stats — `l2_types_total 26, routed_here 19, unrouted_globally 6`; unrouted list: `budget_freeze, champion_left, deal_sentiment_negative, objection_open, proposal_no_response, timeline_slip`
- Impact: `objection_open` and `timeline_slip` are firing right now for Rohit and would compile to nothing, silently. 33 `timeline_slip` observations exist with nowhere to go.
- Fix: add explicit abstention bindings for all six so silence becomes an auditable disposition rather than a void.
- Blocks: CP-2 exit gate ("all emitted types route or explicitly abstain").

**L3-13 · The ICP companion capability: 11 of its 20 inference patterns are BLOCKED on missing typed L1 facts** `[CODE]` `medium`
- Unit: `Domain Expertise/Sales Expertise/capabilities/01-market-and-targeting/icp-definition/capability.yaml` `metadata.notes` — *"eleven are blocked… the single highest-value gap is `account.industry` / `account.employee_count` / `account.geography` as typed Layer 1 facts — the cheapest enrichment in the stack, absent, and it disables the anti-fit half of this capability entirely"*
- Impact: the ICP capability's entire **anti-fit half** — the disqualifier list, which its own file calls "the entire point" — cannot execute. Every executable pattern infers fit from deal BEHAVIOUR, none from what the account actually IS.
- Fix: either add the three account facts as typed L1 facts (cheap enrichment, feeds L1-14) or prune the 11 blocked patterns and accept a half-capability at review. **Do not accept the capability with 11 silently-dead patterns.**
- Blocks: named-reviewer acceptance of the ICP companion.

**L3-14 · The audit's recommended lane trigger cannot fire for the design-partner org** `[CODE]` `medium`
- Unit: `packs/sales_v1.py:110-115` — `buying_signal` requires `has_obs: budget_approved` AND `thread.ball_in_court='us'`. Live: `graph_observations` for this org has **24 kinds, `budget_approved` is not among them**; `buying_signal` signals = 0. Second-best trigger `intro_followup` (`general_v1.py:66-72`) fired **0** despite 87 `introduction` observations across 28 distinct persons
- Impact: authoring the ADR-02 lane and evaluating it on Rohit's data gives an empty denominator. Rohit is a founder RAISING money, not selling.
- Fix: **do not change the lane** — change the evaluation set. `sales.sit.inbound_fit_check` matches three L2 types, so exercise it through `demo_requested` (14 obs, 1 live signal) and `intro_followup`; trace one of the 28 introduction-bearing persons through the rule evaluator to find why `intro_followup` is silent (30-minute diagnosis); source a second design partner running ordinary B2B sales before treating the pilot denominator as real. State this explicitly in ADR-02.
- Blocks: CP-2 exit gate; the entire CP-7 counterfactual pilot.

> **Lane routing detail worth preserving verbatim in ADR-02:** `sales.sit.inbound_lead` (owned by the primary capability) carries the narrowing predicate `thread.ball_in_court = us` — and only ~9% of founder-inbox persons have it. `sales.sit.inbound_fit_check` (owned by the ICP companion) deliberately carries **no** narrowing predicate ("a fit check must fire before a deal record exists") and reaches `lead_qualification` via `also_serves`. Routing through the unnarrowed situation structurally bypasses the 9% gate. Do NOT "simplify" by routing straight to `inbound_lead`.

---

## L4 — REASONING
**Package:** `genios_engine/reason/**`

### [ATLAS] What it must do
Consume an `ExpertisePackage`, answer "what should happen?", emit `DecisionObject` + `ReasoningTrace` without executing anything. Generate **multiple materially distinct candidates** — primary, fallback, explicit do-nothing/stop — hard-eliminate prohibited or infeasible ones BEFORE ranking, then impose a deterministic total order on separated axes (expected value, urgency, fit, risk, relationship cost). Confidence has exactly one authority and can never override a hard gate; below the floor the system stops recommending and starts asking, returning `DEFER`/`INSUFFICIENT_CONTEXT`/`NO_ACTION`/`BLOCKED` with no selected candidate. All four brains constrain their own authorized dimension, each with a typed semantic effect or an explicit deterministic no-effect receipt. Output carries state-based situation, exact remaining loop, stakes, expiry, owner/approval boundary, observable completion, outcome window. LLM may only explain a frozen decision.

### [CODE] What it actually does
`reason/reasoners/__init__.py:41-65` registers 23 units (17-unit frozen roster + 6 supplementary). The only manifest that runs live is built by `reason/adapters/legacy_pack.py::legacy_capability_manifest`: one matched pack rule → **exactly ONE** `PlayDefinition` with a single generic step `"Prepare {artifact} for human review."` and a fixed 6-spec DAG. `reasoning_reasoner_results` contains exactly those 6 reasoner_ids, 251 rows each. 251 runs → 251 candidates (avg **1.00**), all `disposition='eligible'`, zero eliminated; all 1,004 `reasoning_candidate_checks` rows `outcome='pass'`; `reasoning_run_outputs` 251/251 `outcome_kind='decision'`.

### Complete gap list, ranked

**L4-01 · The weighted total-order ranking formula never executes — `priority_override` short-circuits it on 100% of runs** `[CODE]` `small`
- Unit: `reason/reasoners/legacy_rule.py:49` (`"priority_bp": score*100`) → `reason/adapters/legacy_pack.py` (`core.priority` config `{"source_reasoner":"legacy.rule"}`) → `reason/reasoners/priority.py:154-160` (republishes as `priority_override_bp`) → `reason/decision_maker.py:240-241` (`return priority_override` before the formula at `:244-253`)
- Impact: `utility_bp` IS the legacy rule score × 100. DB disproof of the formula: urgency=10000 rows carry utility 4200–4900 while urgency=6500 rows carry the **highest** utility 6000 — inverted, so a weight-20 urgency term cannot be running. Every ranked card Rohit sees is ordered by a single legacy scalar. **The audit marks this "Present, Tested".**
- Fix: `legacy_capability_manifest` stops declaring `source_reasoner: legacy.rule` on the `core.priority` spec, or `priority_bp` from a legacy rule maps to `urgency_bp` only and `priority_override_bp` requires an explicit organisational override flag. The short-circuit at `decision_maker.py:240-241` is correct and stays.
- Blocks: all candidate ranking, portfolio prioritization, score/urgency separation, L7 confidence calibration, and every acceptance metric assuming ranking reflects business axes.

**L4-02 · `DecisionOutcome.DEFER` is mathematically unreachable — no live manifest declares `confidence_floor_bp`** `[CODE]` `medium`
- Unit: `reason/decision_maker.py:64` + `:382` (`_metadata_bp(request, CONFIDENCE_FLOOR_KEY, 0)`, docstring "Default 0 disables the floor"). Repo-wide, `confidence_floor_bp` is declared **exactly once**: `packs/capabilities/deal_cooling_v2.py:185` — the manifest LOCK 1 excludes
- Impact: the audit's headline safety property has **never once executed**. `reasoning_run_outputs` = 251/251 `decision`. Every low-evidence situation still produces a prescriptive winner. **The audit frames the failure as "API/card fallbacks render an imperative instead of honest abstention" — the true failure is one layer earlier: the core never abstains, so the API fallback path has never been reached.**
- Fix: declare `confidence_floor_bp` per pack in `legacy_capability_manifest`'s metadata (sourced from the pack's `gate.c_min`, already read for `legacy.score_gate`); mirror in `expertise_capability_manifest`; `reason/orchestrator.py` refuses a manifest with `live_delivery_enabled=True` and no declared floor.
- Blocks: "Make abstention authoritative end to end"; abstention precision/recall metrics have no observations to measure.

**L4-03 · Every production run has produced exactly one candidate and never eliminated anything** `[CODE]` `large`
- Unit: `reason/adapters/legacy_pack.py` passes `plays=(play,)`; `decision_maker.py::synthesize_candidates:210` iterates `request.capability.plays`
- Impact: 251/251 runs, avg exactly **1.00** candidate, zero eliminated, 1,004/1,004 checks pass. There is no comparative judgment anywhere in the product. The founder never sees a fallback, a rejected alternative, or a do-nothing option. **The audit says "generally one play" — it is 100.0%, an invariant.**
- Fix: near-term — `legacy_capability_manifest` emits a candidate SET (the rule's play + a mandatory `wait_observe` do-nothing play) so elimination and ranking have something to operate on. Structural — L3 supplies multiple accepted plays per situation (`reason/adapters/expertise.py::_plays`, currently capped at 4 and steps-only).
- Blocks: alternative-distinctness metric, candidate rejection receipts, trade-off/validation unit scheduling, the "sales consultant not activity reminder" positioning.

**L4-04 · Organization / Behavior / Adaptive values reach L4 as bytes in a hash and nothing else** `[CODE]` `new_subsystem`
- Unit: `reason/adapters/expertise.py:180-188` (`semantic_hash({... organization_rules, behavior_patterns, adaptive_preferences, brain_snapshot_id})`); enters the decision at exactly two identity-only places — `:192` `version=f"exp.{knowledge_hash[:16]}"` and `:211` `metadata["knowledge_hash"]`. Repo-wide grep for the three names in `reason/` → zero read sites
- Impact: **latent, not live** (`expertise_packages` = 0, `use_domain_compiler=False`). Governance and personalization claims are provenance theatre.
- Fix: see L3-05 — the typed consumers live in this file.
- Blocks: any L3 activation; the four-brain mutation replay; "Brain semantic-consumption coverage" and "Hash-only manifest mutation rate".

**L4-05 · The `signals` table is a schema-level severance of the DecisionObject — the card layer rebuilds a recommendation from `reason_code` alone** `[CODE]` `large`
- Unit: `reason/publication.py:186-207` + `reason/composer.py:311-333` carry only score, score_inputs, reason_code, evidence, play, run/candidate/decision ids, expiry, cooldown. `ReasoningDecision.do_nothing_consequence`, `.uncertainty`, `.outcome_window_days`, `DecisionCandidate.checks`, `parameters["steps"]` have **no column**. `api/routes.py::_decision_projection` (~`:2056-2098`) re-derives `rec` from a `reason_code` if/elif chain and hardcodes `"stakes":"missing"`, `"completion":"missing"` while still shipping the imperative. `api/intelligence_routes.py:423-440` compounds with a 10-entry `_PLAY_LABEL` dict
- Impact: this is why cards read as activity reminders. The projection is not lossy — it is a **parallel, independent generator** sharing nothing with L4 except a reason_code string.
- Fix: typed decision columns on `signals` (`do_nothing_consequence`, `uncertainty jsonb`, `outcome_window_days`, `rejected_candidates jsonb`, `candidate_steps jsonb`) written by `publication.py`/`composer.py`; rewrite `_decision_projection` to read those columns only and **delete** the reason_code synthesis; `deliver/store.py:118` carries them onto the card row.
- Blocks: "Require stakes and completion", "Lossless card projection", "Candidate rejection receipts", Generic-imperative-rate and Decision-completeness metrics; blocks abstention ever becoming visible even after L4-02.

**L4-06 · 14 of the 17 core units have never executed; the four comparison/challenge units are named only by the LOCK-1-excluded manifest** `[CODE]` `medium`
- Unit: `reason/reasoners/__init__.py:41-65` (17-unit roster, 23 registered); `grep core.alternative|core.tradeoff|core.validation|core.recommendation` matches ONLY `packs/capabilities/deal_cooling_v2.py`; `packs/capabilities/__init__.py:16-22` keeps it out of `BUILTIN_CAPABILITIES`
- Impact: only `core.constraint`, `core.priority`, `core.confidence` of the roster have ever run. No trade-off, alternative generation, validation/challenge, impact, opportunity, cost, dependency, timeline, scheduling, policy or relationship analysis has ever informed a card. "17 reasoning units" is an architecture fact being read as a runtime fact.
- Fix: LOCK 1 removal is step 1 but inert alone (`DEAL_COOLING_V1` also carries `live_delivery_enabled=False`). The real owner is `legacy_capability_manifest`, which must grow per-reason-code manifests naming the units that decision class needs, plus a `reasoner_plan` receipt (already persisted in `reasoning_runs.reasoner_plan`) surfaced to the card as scheduled/executed/skipped.
- Blocks: **sequence strictly after L4-03** — `core.alternative` and `core.tradeoff` have nothing to compare with one candidate.

**L4-07 · Card score is exposed to the extension as `confidence_score`** `[CODE]` `small`
- Unit: `api/intelligence_routes.py::list_insights` — `sc01 = round(sc/100,3)` then `"confidence_score": sc01` and `"scores": {"confidence": _band_label(sc01)}`. Given L4-01, `r.score` is the legacy rule score
- Impact: a card scored 60 because the rule matched strongly displays as 60% confident. `reasoning_run_outputs.confidence_bp` (the real calibrated value, 6500–9800) never reaches the surface. The dashboard path (`api/routes.py::_confidence_block`) does the right thing — the two API surfaces disagree with each other.
- Fix: source `confidence_score` from `signals.score_inputs->>'C'` (or join `reasoning_run_outputs.confidence_bp`); expose `score` under a distinct `priority_score` key.
- Blocks: "Separate score vector"; Score-semantic-integrity metric. Cheap and independent.

**L4-08 · `_actionability` defaults to `actionable` for every reason_code it does not recognise** `[CODE]` `small`
- Unit: `api/routes.py::_actionability` (~`:1986-2011`) handles exactly three reason codes and ends with an unconditional `return {"state":"actionable"}`. **Not named in the audit.**
- Impact: the gate covers 34 of 41 signals; `closed_lost_risk` (4), `objection_open` (1), `demo_requested` (1), `timeline_slip` (1) — the sales-critical ones — pass ungated with zero grounding check. Every new pack rule silently inherits the ungated default.
- Fix: invert the default to `context_incomplete`; require each reason_code to declare its decisive fact field, sourced from the pack rule's `evidence_fields` in `reason/rules.py::Rule` rather than a hand-maintained if/elif chain.
- Blocks: nothing downstream — the cheapest reduction in false prescription available.

**L4-09 · Expert Brain consumption is steps-only, capped at four plays, with a silent generic fallback** `[CODE]` `small`
- Unit: `reason/adapters/expertise.py::_plays:104-153` — `if not raw_steps: continue` (no receipt), `if len(plays) >= 4: break` (silent truncation), `if not plays:` appends hardcoded `review_situation`; `_goal:156-168` takes only the FIRST capability with a `question`
- Impact: **`[MODELLED]` consequence** — when the compiler is activated, a 1,748-file corpus can compile successfully, hash into a new manifest version, and still emit one generic "review the situation" play. Not a live defect today.
- Fix: replace `continue`/`break` with a deterministic ordering policy plus `skipped_rule_ids` and `truncation_reason` in metadata; typed consumers for the non-steps Expert artifact classes or an explicit per-class unsupported receipt; tag the `review_situation` fallback `read_only` **and** non-prescriptive.
- Blocks: L3 activation — must land before `use_domain_compiler` flips, or activation will look successful while producing generic output.

**L4-10 · `reasoning_candidates.score_components` is written but never read — four of five are the dataclass default on 100% of rows** `[CODE]` `medium`
- Unit: `contracts/reasoning.py:317-320` defaults impact/success/effort/risk to 5,000; neither adapter's `PlayDefinition(...)` sets any of the four
- Impact: all 251 rows `{risk:5000, effort:5000, impact:5000, success:5000, urgency:N}`. L3 has no way to express that one play is higher-impact, cheaper or riskier. The persisted row implies a five-factor economic model that does not exist and will mislead L7.
- Fix: per-play `impact_bp`/`effort_bp`/`risk_bp`/`success_probability_bp` in the `sales_v1`/`general_v1` rule dicts, threaded through `legacy_capability_manifest` into `PlayDefinition`. **Inert until L4-01.**
- Blocks: meaningful ranking; the "+20-30% lead prioritization" target.

**L4-11 · The confidence vector is three-quarters decorative** `[CODE]` `small`
- Unit: `api/routes.py::_confidence_block` (~`:2045-2054`) — `identity` is a hardcoded ternary (85 if 'company' or 'role' in facts else 30), `situation` a hardcoded ternary (80/50), `recommendation` literally `evidence` re-emitted. Only `evidence` carries real data (`score_block['C']`, 20 distinct values across 41 cards)
- Impact: three of four dimensions are invented at projection time by the API layer, which owns none of them — violating the "each layer owns its own confidence dimension" rule. **The audit says "score is mapped to confidence" — imprecise; the vector's shape is right and its content is 75% invented.**
- Fix: source identity/situation confidence from L2's real evidence/freshness/consistency/identity vector, or emit only `evidence` and mark the rest explicitly absent. Do not ship four numbers where one is real.
- Blocks: the Gold Standard "Confidence vector" field.

---

## L5 — EXECUTIVE
**Package:** `genios_engine/executive/**` (23 modules) + `contracts/execution.py`

### [ATLAS] What it must do
Convert one still-authoritative L4 decision into accountable work: an immutable, content-addressed `ExecutionObject` with an owner, dependency-aware steps, a communication plan, an escalation ladder and a clock. Supervise until resolution — **validate → transition → observe → decide → speak**, never "remind then check". Close only on scoped post-creation evidence, writing achieved / not-achieved / unproven to the outcome ledger L7 learns from. Escalate by consequence without inventing facts. Refuse (review / waiting / blocked / defer / no execution) whenever authority, semantic target, ownership, approval, dependency, freshness or completion evidence is unresolved.

### [CODE] What it actually does
The subsystem is **complete and correct**. `executive/sweep.py:165 plan_commitments` reads signals through the full `AUTHORITATIVE_SIGNAL_PREDICATE`, interprets, resolves owner, builds, and persists idempotently. Proven by executing the real functions against live production Postgres inside a rolled-back transaction: **27 executions + 27 actions + 27 events, histogram `{"built": 27}`, zero refusals.** Yet all five `execution_*` tables hold 0 rows — because the heartbeat's Layer 5 pass raises `NameError` on its first statement, every tick since 2026-08-08.

### Complete gap list, ranked

**L5-01 · The L5 heartbeat pass is dead code at runtime: `_executive_orgs()` raises `NameError` on its first statement, every tick, swallowed into `{"error": True}`** `[CODE]` `small`
- Unit: `api/routes.py:409-410` — `return [row[0] for row in c.execute(text(` with **no `text` in scope** (no module-level import; ~20 *local* imports elsewhere in the file). Call site `routes.py:298`, inside the try at `:293`, caught by `except Exception` at `:314`. Born broken: `git show 02241c9` line 355 has the identical defect
- Impact: **for 15 days the founder has had a fully working accountable-execution engine that has never planned, tracked, reminded, escalated or closed a single commitment.** Every recommendation stops at a card. Prod logs have printed `'executive': {'error': True}` every 6 hours. This is the single precondition keeping `executions` at 0 — there is no other.
- Fix: `from sqlalchemy import text` inside `_executive_orgs()`; move `orgs = _executive_orgs()` into its own narrow try and surface the exception type/message into the returned dict instead of `{"error": True}`. Backfill immediately via `POST /v1/executive/sweep` (`executive_routes.py:247`, `Depends(require_owner)`), which bypasses `_executive_orgs()` entirely and works today unmodified.
- Blocks: commitment tracking, reminders, escalation, `executive_bridge`, `delivery_outbox`, `execution_outcomes`, every L7 input derived from outcomes, and all HKS golden replays.

**L5-02 · The guard test reads source TEXT, not behaviour — it cannot detect a NameError inside the function it inspects** `[TEST]` `small`
- Unit: `tests/test_executive_sweep.py:500-513` — `source = inspect.getsource(routes.run_maintenance_sweep)`, `assert "run_executive" in source`, then `assert "tenant_packs" in inspect.getsource(routes._executive_orgs)`. Its own docstring: *"Layer 5 is worthless on a timer nobody set"*. The file passes: 68 passed
- Impact: this is why a 1,400-green suite coexists with a layer that has never run. Every "Wired" verdict resting on composition order is unverified, and the same NameError class can recur silently in any other heartbeat block.
- Fix: replace the `inspect.getsource` assertions with an execution test — call `routes._executive_orgs()` against the test engine and assert the seeded org returns; drive `run_maintenance_sweep` with fakes asserting `result["executive"]["commitments_created"]` is an int. Grep the suite for other `inspect.getsource` wiring assertions and convert them the same way.
- Blocks: trusting any "Present and Wired" claim; safely re-enabling the heartbeat.

**L5-03 · Every commitment is born unroutable — `org_seats` is 0 rows, so the escalation ladder is structurally empty and the reminder engine permanently quiet** `[CODE]` `medium`
- Unit: `executive/assignment.py:149` (`Assignment(None, AudienceClass.ADMIN_QUEUE, "rule3_unrouted")`) → `executive/execution.py:107-112` passes `remindable=communication.routable` → `executive/escalation.py:124-125` `if not remindable: return ()`. Live: `org_seats` 0 rows, `org_channels` 0 rows. Rolled-back replay: 27/27 `rule3_unrouted`, assignee NULL, `run_lifecycle` returned `{'quiet_not_remindable': 27}`
- Impact: fixing L5-01 alone gets a commitment ledger visible in `/v1/executive/commitments` that never speaks. The founder would see rows appear and conclude L5 still does nothing.
- Fix: a fourth explicit rule in `assignment.resolve_owner` for a single-seat/founder-only org; onboarding inserts the founder into `org_seats` (`PgSeatDirectory` at `assignment.py:183` only reads). Decide deliberately whether an unrouted commitment gets a degraded in-app-only ladder or stays laddered-off with a named `blocked` reason — do not let `()` remain the silent default.
- Blocks: any reminder or escalation reaching a human; `executive_bridge`; every metric that divides by reminders.

**L5-04 · A signal a human has already resolved or acted on still becomes a live commitment** `[CODE]` `small`
- Unit: `executive/sweep.py:70` docstring claims "open, unexpired, and still authoritative"; the SQL at `:71-87` adds only a no-open-execution guard. `'s.status' in AUTHORITATIVE_SIGNAL_PREDICATE` → **False**. Compare `deliver/actions.py:66`, which does carry `and s.status='open'`
- Impact: of the 26 plannable signals, `group by s.status` returns open=24, **resolved=2** — e.g. `sig_3ab0cde2beef4744bfb4c242`, which my replay built into an execution. The moment L5 is switched on, the founder gets commitments with deadlines for work already finished.
- Fix: add `and s.status='open'` to `_PLANNABLE_SIGNALS` (keep it local to the sweep — the audited-card CTEs in `reason/authority.py` intentionally read acted signals); align the docstring or make it the test.
- Blocks: **must land in the same change as L5-01**, or the first live tick creates commitments for closed work.

**L5-05 · The card surface and the execution subsystem are two disconnected state machines** `[CODE]` `large`
- Unit: `deliver/actions.py` — `grep -c execution` returns **0** for the whole file. `ingest_action` (`:37`) sets `state='acted'` (`:80`), `update cards` (`:89`), `update signals set status='acted'` (`:94`), writes `human_events`/`card_events`, and never touches `executions`. `executive/execution_store.py` exposes `complete_action`/`link_card` that nothing on this path calls. Live: 0 `human.card_action` events ever — no button has been pressed
- Impact: once L5 is live this is a divergence the founder can see: the card says accepted, the commitment stays `created`/`pending` with a running clock. Combined with L5-04 the acted signal keeps re-qualifying. No outcome receipt is ever written, so L7 learns nothing from the one signal the founder actually gives.
- Fix: inside `ingest_action`'s existing transaction, look up the linked execution by `signal_id` (written by `execution_store.persist`) and call `complete_action` / a new claim transition in the same commit, keyed by an idempotency/command id so retry, refresh and concurrent clicks converge. Layer direction is legal (`tests/test_layer_topology.py` allows 6→5; `deliver/router.py` already does it). Present "claimed", never "done", until scoped evidence arrives.
- Blocks: HKS-L5-04; the outcome/value ledger; any "time to accountable owner" or divergence metric; L7's entire feedback loop.

**L5-06 · Agent delegation has no governed protocol; `ExecutionState` cannot express approval or failure** `[CODE]` `new_subsystem`
- Unit: `api/intelligence_routes.py:908` returns **HTTP 501** — *"executor handoff is disabled until the idempotent single-executor approval protocol is available"* (correct, keep it). `contracts/execution.py:58-75 ExecutionState` has no `AWAITING_APPROVAL` and no `FAILED`, so even a built protocol has nowhere to park a pending approval or a distinguishable failure
- Impact: the founder cannot delegate to an agent at all. Correct behaviour today — but the "Decision Copilot acts for you" half of the product is absent, not degraded. **A second, OPEN agent door exists and the audit misses it:** `deliver/agent_api.py` behind `POST /v1/signals/{id}/claim` and `/result` (`routes.py:2490-2520`) has a 15-minute claim lock but no approval token, signed envelope, single-executor lease or revocation. Nothing exploits it today (`agent_registry` = one archived test agent).
- Fix: **split.** L5-06a (Phase 4): add `AWAITING_APPROVAL` and `FAILED` to `ExecutionState` + `ALLOWED_TRANSITIONS` (`contracts/execution.py:81`) + migration — the state machine must express approval before any protocol can use it. L5-06b (Phase 8): a new executor-lease module under `executive/` providing approval-token issuance, one fenced lease per execution, scoped payload, idempotency key, cancellation and signed result receipt; close the `deliver/agent_api.py` door behind the same protocol. Keep the 501 until its security, idempotency and duplicate-delivery suites are green.
- Blocks: HKS-L5-05/10; the Extension's action-first direction; any "GeniOS executes" claim.

**L5-07 · The same `text`-not-imported defect sits in the calibration block of the same heartbeat function** `[CODE]` `small`
- Unit: `api/routes.py:337` — `c.execute(text("select pack_id from tenant_packs ..."))` with no local import in that block (verified over lines 328-342). Unlike L5-01 it sits inside a per-org try at `:335`, so it fails per org rather than aborting the pass
- Impact: `run_calibration` has never executed from the heartbeat — precision → auto-mute → bounded nudges never fires. Consistent with `learning_runs = 2`, `calibration_runs = 0`, `rule_mutes = 0`. Fixing L5 without this leaves the outcome data it starts producing unconsumed.
- Fix: add the local import; audit every remaining bare `text(` in `routes.py` against its enclosing function.
- Blocks: L7 calibration; any learning consuming `execution_outcomes`.

**L5-08 · The audit's "strengthen current authority" P0 points the WRONG WAY — the 4 red executive-authority tests assert a predicate deliberately removed as a bug fix** `[CODE]` `small`
- Unit: `tests/test_executive_authority.py:73` asserts `"authority_ctx.graph_version = (select coalesce(max(gv.graph_version),0)"` is present. `reason/authority.py` carries the removal comment: *"the old `graph_version = max(graph_version)` required the reasoning to have run at the CURRENT graph version, so every card silently vanished the instant anything wrote to the graph — each 6-hourly scheduler sync bumped the version and the queue went empty though the cards were still valid and open"*
- Impact: working the audit's P0 list top-down would **reintroduce the defect that emptied the founder's queue every 6 hours.** The failing tests are stale assertions, not a live authority hole — 26 signals pass the full predicate today.
- Fix: delete the graph_version assertion from the four tests; replace with the open-status + pack-authority + expiry terms the predicate actually enforces. **Do not touch `reason/authority.py`.** If an orphan-execution policy is still wanted, own it in `executive/execution_guard.py`.
- Blocks: a clean baseline.

---

## L6 — DELIVERY (Atlas 5.2)
**Package:** `genios_engine/deliver/**` (28 modules, 4,088 lines) + `api/delivery_routes.py` + `feedback/delivery_facts.py`

### [ATLAS] What it must do
Take an authorized, hash-verified `ExecutionObject` and materialize it safely onto a surface: resolve the concrete recipient **now** against inherited visibility, read the presence lease, build a lawful primary→fallback route ladder, gate the moment (SEND/DEFER/SUPPRESS, most-restrictive wins), commit one logical delivery row plus its `queued` event in one transaction, let a **fenced** worker claim it with an expiring lease, commit a `started` attempt before any network I/O, revalidate authority immediately before the adapter call, settle into one typed `DeliveryResult` with an append-only ledger. Ten destinations = one logical delivery. Engagement receipts authenticated and chronologically legal. An "accepted" click idempotently claims a linked Executive action and never means business completion. Delivery may reject or suppress unsafe material but must never repair wrong meaning.

### [CODE] What it actually does
Three paths in one folder. (1) **Card building is live**: `pipeline.build_cards_for_org` → `card_builder.build_draft` → `render.render_copy` → `store.CardStore.insert_card`, 41 cards for this org, seen only by **pull** (`store.py:294`, `intelligence_routes.py:498` backfill a `card.surfaced` impression). (2) **Legacy push path** is well-engineered and has never enqueued anything — `delivery_outbox`, `delivery_attempts`, `delivery_events`, `delivery_materialization_failures` all 0 rows, all orgs. (3) **Atlas 5.2 v2 control plane** has zero production importers. `deliver/push.py` is the one module that performs outbound I/O today — a synchronous best-effort HMAC POST fired inline from `pipeline.py:128-132` with `except Exception: pass`.

### Complete gap list, ranked

**L6-01 · Zero deliveries have ever occurred: `run_distribution` enumerates `org_channels`, which has 0 rows in the entire database** `[CODE]` `medium`
- Unit: `deliver/outbox.py:483-487` (`select distinct org_id from org_channels where active`)
- Impact: Rohit has never received a single Slack message, digest, or commitment reminder. All 41 cards are visible only if he opens the dashboard. **The product has no proactive surface in production at all.** The audit calls the bridge "real" and "invoked during distribution" — composition-true, runtime-false.
- Fix: `run_distribution` stops equating "a tenant with delivery" with "a tenant with an active chat row" — either provisioning writes an `org_channels` row at onboarding, or non-chat tenants route to the durable pull surface via `routing.PULL_SURFACE`.
- Blocks: everything downstream in L6 — gate correctness, retry, dead letters, analytics, receipts, and L7's entire delivery-evidence feed.

**L6-02 · Band starvation makes card→push structurally unreachable even after a channel exists** `[CODE]` `large`
- Unit: `deliver/outbox.py:167` (`and k.urgency_band in ('high','critical')`); `deliver/bands.py:9` (`{"high":70,"critical":85}`). Live: all 43 cards `urgency_band='standard'`, score 42–60, `I=55` on every score_block
- Impact: even with Slack connected tomorrow, **zero cards would be pushed**. The founder would still get only the digest and Executive reminders (which need `executions`, = 0).
- Fix: the owning defect is L4 (L4-01 + L4-10). L6's own contribution: `enqueue_pending` must treat "no card ever clears the push band across a whole tenant" as an observable condition, not silence.
- Blocks: any claim the push law works; notification-fatigue, defer-correctness and impression-budget metrics all have an empty denominator.

**L6-03 · No recipient exists for any card — `org_seats` is 0 rows, so all 43 cards have `assignee = NULL`** `[CODE]` `medium`
- Unit: `deliver/router.py:27-37` → `executive/assignment.resolve_owner` → rule 3; `deliver/executive_bridge.py:146` additionally requires `x.assignee is not null`
- Impact: HKS-L6-01 (Theresa) and HKS-L6-04 (visibility restriction) cannot even be evaluated — there is no authorized target to resolve or revoke. `router.budget_full` short-circuits to False for every card. The audit flags frozen-assignee staleness; the live problem is one step earlier.
- Fix: provisioning creates an `org_seats` row for the founder (same fix as L5-03); until then `resolve_assignee` returning None must be surfaced as a counted `unrouted` condition rather than absorbed at `pipeline.py:133-134`.
- Blocks: the executive reminder bridge; per-recipient attention budget; every audience/visibility HKS.

**L6-04 · 91% of L6's LLM spend is thrown away; V-01 length overflow is treated identically to a hallucination** `[CODE]` `small`
- Unit: `deliver/render.py:111` (`llm.call(prompt, max_tokens=600)`), `:127-130` (V-01 → whole-output fallback), `:132-139` (V-02), `:77-84` (`_fallback` sets `"body": ""`)
- Impact: all 43 cards made a render call; **39 rejected — 27 by V-02, 12 by V-01** — and every rejection returns an empty artifact body. 37 of 41 cards carry slot-interpolated copy with `artifact_ready: false`, so "Draft reply" advertises nothing. Yield 4/43.
- Fix: (a) split V-01 from V-02 — length overflow is deterministically repairable, so re-prompt once with the measured overflow or reject only the offending field; (b) stop generating the artifact in the card call — move it behind the `run_play` action. **The audit's proposed "validator rejection never receives a creative try again" must be narrowed to V-02; applying it to V-01 is what produces the 28% length loss.**
- Blocks: nothing structurally — the highest ratio of customer-visible quality to effort in this layer.

**L6-05 · L7's learning feed is severed at the contract, not merely starved** `[CODE]` `large`
- Unit: `feedback/delivery_facts.py:61` (`where org_id=:o and delivery_id is not null`); `delivery_id` is written by exactly one function — `deliver/spine.py:63-83 materialize` — which has **no production caller** (grep for `materialize(` outside `tests/` → no hits)
- Impact: even a fully working legacy path would yield zero `DeliveryFacts` forever. The "closed loop" is open at both ends.
- Fix: `enqueue_pending`/`enqueue_digest`/`executive_bridge` stamp a `delivery_id` and `dedupe_key` on every row (the correct direction — it is the same change the v2 cutover needs), or `load_delivery_facts` drops the predicate and keys on `id`.
- Blocks: all delivery-derived learning; the entire Engagement and Outcome metric hierarchy.

**L6-06 · The legacy drain and the v2 claimer are not mechanically disjoint, and no backfill writer exists** `[CODE]` `medium`
- Unit: `deliver/outbox.py:245-250` (drain: `status='queued' and next_attempt_at <= :now`, no discriminator) vs `deliver/spine.py:116` (`and legacy_reconcile = false`). `legacy_reconcile` is `default false` from migration 0043 and **nothing in the repository ever sets it true**
- Impact: risk is zero today because the table is empty — **which is precisely the window in which it is free to fix.** The moment either path writes, both workers can select the same row → duplicate human interruption (HKS-L6-05).
- Fix: add the discriminator to `drain`'s SELECT (`and legacy_reconcile = true` or `and delivery_id is null`) and a NOT NULL shape predicate to `claim_due`. **Ship before either path emits its first row**; an empty table means the backfill migration is a no-op today and a data project later.
- Blocks: the v2 cutover.

**L6-07 · Every operator- and customer-facing delivery API is blind to the live path by construction** `[CODE]` `medium`
- Unit: `api/delivery_routes.py:348` and `:422` (`delivery_id is not null`), `:434` (`status='failed' or lifecycle='failed'`); `deliver/analytics.py:38` (same vocabulary); `outbox._finish` writes `status='failed_terminal'`/`'delivered'` without touching `lifecycle` (stays `'queued'`)
- Impact: when delivery starts, an operator asking "what failed?" gets an empty answer while Slack calls are happening; analytics would report `by_status: {queued: N}` for delivered rows.
- Fix: one canonical transition function in `deliver/outbox` updating `status`, `lifecycle`, `delivered_at` and appending a `delivery_events` row together (the job `spine.log_delivery_event` already does for v2); collapse `failed_terminal` and `failed` into one enum.
- Blocks: any pilot instrumentation; Integrity metrics; the dead-letter completeness gate.

**L6-08 · Quiet hours default to UTC 21:00–08:00 with no org/seat timezone fallback** `[CODE]` `small`
- Unit: `deliver/timing.py:73-76`; `deliver/gate.py:391-395` (only source is `delivery_preferences`, **0 rows**); `gate.py:288` comment explicitly accepts "a broken timezone falls back to UTC quiet hours"
- Impact: for an India-based founder, UTC 21:00–08:00 is **IST 02:30–13:30** — the politeness window covers his entire working morning and leaves IST 22:00–02:30 wide open. The exact inversion of HKS-L6-03.
- Fix: `PgDeliveryContext._read_settings` falls back to the org's timezone before falling back to `AttentionProfile()`; or onboarding writes a wildcard `delivery_preferences` row.
- Blocks: nothing — but it will silently corrupt the very first delivery pilot if not fixed before L6-01.

**L6-09 · `deliver/push.py` performs outbound I/O inline from the card build, bypassing the entire control plane** `[CODE]` `medium`
- Unit: `deliver/pipeline.py:128-132` (`from .push import push_card_to_agents ... except Exception: pass`); `deliver/push.py:18-27`. The `outbox` module's own docstring at `:1-9` names this exact anti-pattern as the reason it exists. **Not mentioned in any of the six L6 audit docs.**
- Impact: latent (`agent_registry` = one archived test agent). The moment a client registers a webhook, a slow endpoint degrades the card build for that org, and agent deliveries appear in no outbox, result API, dead letter or analytics.
- Fix: route `push_card_to_agents` through `deliver/outbox` as an agent-class row — exactly what `routing.AGENT_TRANSPORTS` and the `agent_push` channel class were built for.
- Blocks: any honest "one canonical sender" claim; any agent-channel pilot.

**L6-10 · Priority ordering in the v2 claimer is a lexical text sort while a numeric scheduler with anti-starvation aging sits unused** `[CODE]` `small`
- Unit: `deliver/spine.py:119` (`order by priority, created_at` on a `text` column → background < critical < high < low < medium). The correct rank already exists at `contracts/delivery.py:297-303 _PRIORITY_RANK` and `deliver/scheduler.py:18-45` (`effective_rank` + 4-hour starvation aging), **zero importers outside tests**
- Impact: latent. On activation a `critical` delivery would be claimed after `background` work.
- Fix: order by a SQL CASE mirroring `_PRIORITY_RANK`, or claim a wider window and hand it to `scheduler.schedule_order`. **The audit oversizes this — it is one ORDER BY clause, not a new mechanism.**
- Blocks: nothing.

**L6-11 · Capability truth is overstated in two independent ways** `[CODE]` `small`
- Unit: `api/delivery_routes.py:466` (`and secret_ciphertext is not null` — no decrypt, no shape check); `deliver/units.py:26-27` bundles slack/teams with in_app/dashboard under one `needs_credential=False` while `:46` declares a separate `slack_teams` unit with `True`; `units.py:69` evaluates per unit, not per channel
- Impact: a tenant with a corrupt or rotated Slack secret is told the human unit is operational. Only `get_channel` (`channels/base.py:23-29`) has real adapter truth, and it returns Slack or None — 1 of 11 unit classes has an implementation.
- Fix: move the credential requirement from `Unit` to a per-channel map and aggregate afterwards; replace the null-check with a decrypt-and-shape check.
- Blocks: the Operational/send-probe agreement gate; any surface-expansion phase.

**L6-12 · `run_distribution` swallows every per-org enqueue failure with a bare `except Exception: pass`** `[CODE]` `small`
- Unit: `deliver/outbox.py:496-497` — no log, no metric, no dead letter. Contrast `api/routes.py:307-308`, which does the same isolation but calls `_log.exception`
- Impact: on activation, the single most likely failure — one tenant's malformed channel config — produces total silence indistinguishable from "nothing to send".
- Fix: replace the bare `pass` with `_log.exception` plus a counted per-org failure.
- Blocks: nothing — but it is what makes L6-01's fix debuggable.

**L6-13 · `build_route_ladder` inserts the pull surface `in_app` unconditionally** `[CODE]` `small`
- Unit: `deliver/routing.py:30`, `:94`, `:97` — neither branch checks membership in `available_channels`
- Impact: latent. On activation, a delivery with no lawful route becomes "queued to in_app" rather than a visible materialization failure — silent loss dressed as success.
- Fix: include `PULL_SURFACE` only when it is in `available_channels`; otherwise raise `NoRouteError` so `orchestrator.resolve` writes a `delivery_materialization_failures` row.
- Blocks: the v2 shadow-materialization phase would report false coverage without this.

**L6-14 · Ten of 28 modules have zero production reach — ~700 lines of Atlas-shaped machinery proven by tests and exercised by nothing** `[CODE]` `large`
- Unit: grep outside tests — `orchestrator` 0, `scheduler` 0, `retry` 0, `rate_limiter` 0; `audience`/`presence`/`routing` each 1 (from `orchestrator.py:19-21`); `spine` 1 (via `tracker.py:16`, a read-only API route)
- Impact: the repository reads as a complete delivery control plane. Every capability claim built on module presence — fenced workers, route fallback, presence-aware routing, attention reservations, provider-ambiguity recovery — is unearned.
- Fix: the v2 cutover, sequenced **after** L6-01/02/03 — there is no point wiring a fenced worker to a queue that structurally cannot receive rows. First weld is `deliver/outbox.run_distribution`, where a materializer replaces the three `enqueue_*` calls.
- Blocks: the Atlas 5.2 completeness claim.

**L6-15 · No semantic-target contract at the delivery boundary — `run_play` is attached unconditionally before the renderer has run** `[ATLAS]` `large`
- Unit: `deliver/card_builder.py:131-138` (four-action block, unconditional); `pipeline.py:106-109` later downgrades only `artifact_ready`, never the action
- Impact: the mechanism behind Boardy-connector and person-dump failures — Delivery renders faithfully whatever L3/L4 hands it, so a wrong target is transported reliably rather than refused. **The absence is `[CODE]`-verified; the proposed fail-closed gate is `[MODELLED]`.**
- Fix: a required-fields check in `build_draft` downgrading a card to observation-only (no `run_play`, no `do_it_myself`) when the signal carries no bounded target or thread. **Do not build before L4's target work lands, or it suppresses everything.**
- Blocks: the Boardy and Theresa golden replays; the right-recipient precision metric.

**L6-16 · The abstention gates are real, correct, and welded to ONE read endpoint — they never touch the stored card or the queue** `[CODE]` `medium`
- Unit: `api/routes.py:1987-2010 _actionability`, `:2120-2130 _connector_gate`, `:2132 _meeting_lifecycle` (*"a past scheduled event proves it was SCHEDULED, not HELD"*) — all deterministic and well-reasoned. But `_card_intelligence` is defined at `routes.py:2204` and **called exactly once**, at `:2353` (`GET /cards/{card_id}`). `GET /cards` (`:2336`) returns `_card_store.queue(...)` raw. Even on the detail endpoint the gate adds a sibling field: `:2354` is `_annotate_effects` — annotate, not filter. It does not rewrite `headline`, lower `level`, or remove the `run_play` button
- Impact: the list view — the surface Rohit actually scans — shows *"Reply to boardy@boardy.ai now"* with no gate at all. **This changes the fix from "build an abstention system" to "move an existing function": a week versus a quarter.** The single most important correction in this report.
- Fix: move the gate from read-projection into card build (`deliver/card_builder.py`) — a card failing its clarity gate is **written** with `level='observation'`, a non-imperative headline, and an actions array containing only `wrong`/`snooze`; then apply it in `queue()` too. **Depends on X-02** (a non-prescriptive level must exist to downgrade to).
- Blocks: "Abstention integrity" and "Customer surface" acceptance gates.

**L6-17 · `cards.level` is overwritten with the string literal `'prescriptive'` at the delivery boundary** `[CODE]` `small`
- Unit: `deliver/pipeline.py:35` — `"...as reason_code, 'prescriptive' as level, s.subject_node_id,"` hardcodes the literal into `_open_signals_without_cards`; `deliver/card_builder.py:156` then reads `signal.get("level","prescriptive")` and can only ever receive it. **`signals.level` carries `predictive` correctly**: `closed_lost_risk|predictive|4`, `timeline_slip|predictive|1`. `select count(distinct level) from cards` = 1
- Impact: Rohit receives a predictive risk warning rendered as a direct command. The pack authored 11 of 25 rules as `predictive`; he never sees the distinction. **Built, then its output discarded — the cheapest high-value fix in the package.**
- Fix: select `s.level` instead of the literal; `card_builder.py:156` stops defaulting and fails closed when level is absent; add a level-fidelity assertion so the literal cannot return.
- Blocks: every abstention gate; replays 01, 03, 04, 06, 07, 12; any claim that L4 implements abstention.

**L6-18 · The `cards` table physically cannot carry the Customer Intelligence Contract — six of twelve required answers have no column** `[CODE]` `large`
- Unit: `\d cards` at HEAD. Absent: business_subject/relationship_role, unresolved_item, why_now, expertise capability_key+version+review_state, outcome window/success_signal/counterfactual, and the six-component confidence vector. `assignee` is a GeniOS seat, not the business subject; `template_version='cards.v2'` and `config_snapshot_id` record a PACK snapshot, not a capability; `count(execution_id)` = 0 of 41
- Impact: **live gold-standard score is 5 of 16.** Present: situation state (41/41), business subject via headline (41/41), evidence (37/41 — 4 have zero receipts), primary decision (41/41), validity (41/41). Absent: actor-role graph, exact open loop, why-now/stakes, expertise, per-brain influence, alternative set, ownership, completion, outcome, end-to-end trace. Fake/partial: confidence vector. `stakes` and `completion` are literally the string `"missing"` at `routes.py:2095-2096`. Every downstream promise has nowhere to land — this is why Framework-ready verdicts cannot be closed by tuning.
- Fix: an `IntelligenceCard v3` typed boundary in `contracts/` matching the Gold Standard, a `cards` migration adding the six field groups, and `deliver/card_builder.py` (the dict return at `:155-167`) as the single producer. Treat as the L4→L6 contract change, not a schema patch. **Land with L4-05.**
- Blocks: CP-4/5/6/7; the entire scorecard; every value claim.

**L6-19 · `reject_code` is computed at render and never persisted** `[CODE]` `small`
- Unit: `deliver/render.py:67` (`invention_ok`) computes it; `cards` has no such column. `pipeline.py:81,127` already counts llm vs raw_slot per sweep
- Impact: it is currently impossible to tell from stored data whether the 90% raw_slot rate means the LLM is unwired in the sweep (zero spend, zero output) or wired and rejected on nearly every call (full spend, zero output). Those two states differ by the entire card-render bill. **`card_events` does distinguish them — raw_slot/V-02 27, raw_slot/V-01 12, llm/null 4 — but the card row does not.**
- Fix: persist `reject_code` as a `cards` column; emit the per-sweep counter. Until body is non-empty, `card_builder` must not attach the `run_play` action.
- Blocks: diagnosis of the invention validator's true rejection rate; any credible demo.

---

## L7 — LEARNING & EVOLUTION (Atlas 6)
**Package:** `genios_engine/feedback/**` + `contracts/learning.py` + `api/learning_routes.py`

### [ATLAS] What it must do
Ingest explicit founder corrections, L5 execution outcomes, L5.2 delivery receipts and L1/L2 observations into one bounded tenant cohort; turn them into immutable evidence-carrying proposals; gate each deterministically on support, independence, distinct entities, noise, conflict, privacy and business value; route promotion by target under a versioned tenant policy; publish a reversible, versioned brain value L3 then compiles into the next decision. Organization changes require accountable human approval; Adaptive changes are short-horizon and decay; Runtime changes are leases with mandatory TTL; the Expert Brain is never machine-written. Every refusal is an observable reason code, never a silent drop.

### [CODE] What it actually does
The weekly sweep runs, claims the tenant/week, loads a 28-day cohort and executes ten units. Three are hard `return []` stubs; both personalization-evolution units call `_cohort_candidate`, also `return []`. Of the rest, two target METRICS and one KNOWLEDGE_SUGGESTION (bypassing the confidence floor as "artifacts"). `unit_recommendation_learning` is the only ADAPTIVE emitter and hardcodes `distinct_days=1` against a seeded `min_distinct_days=2`, so it is rejected every run. `unit_pattern_learning` is therefore the only unit reaching governance with a brain target, and ORGANIZATION always routes to HUMAN_REVIEW, where `publish()` returns the string `"queued_for_review"` and writes nothing. Net across all orgs, all time: **2 learning_runs, 3 learning_objects (all parked at `governed`), 0 learning_metrics, 0 learned_brain_entries, 0 temporary_memories, 0 knowledge_suggestions, 0 execution_outcomes, 0 card_feedback_verdicts, 0 calibration_runs, 0 rule_mutes, 0 `human.card_action` events.**

### Complete gap list, ranked

**L7-01 · No reachable write path to any brain — three independent stoppers in series** `[CODE]` `large`
- Unit: (a) `feedback/units.py:165-182` `_cohort_candidate` returns `[]`, killing BEHAVIOR and ADAPTIVE direct evolution; (b) `feedback/units.py:187-219` hardcodes `distinct_days=1` at `:211` while `contracts/learning.py:274` seeds `min_distinct_days=2`, so `validate_learning` returns `insufficient_distinct_days` every time — and `feedback/orchestrator.py:47-56` is the ONLY writer of `learning_policies` (no policy-update endpoint), so the threshold can never be lowered; (c) `feedback/governance.py:103-104` routes ORGANIZATION to HUMAN_REVIEW and `feedback/publisher.py:173-176` writes nothing
- Impact: **L7 cannot change any future decision for anyone, by any path, under any evidence.** Every artifact it produces is bookkeeping about proposals that structurally cannot become behaviour. Any statement that the system "learns" is false today, not merely unproven.
- Fix: make ONE path end-to-end first: `unit_pattern_learning` → `governance.govern` → `publisher.publish` → `learning_routes.review`. That needs only L7-02 and L7-06. **Do NOT fix `distinct_days` until L7-08's Adaptive lifecycle is ratified — raising it is what arms the unreachable hazard.**
- Blocks: everything in L7; every metric, replay, and learning claim.

**L7-02 · `approved_unpublished`: the review endpoint renames the row and never publishes; it also never drains `knowledge_suggestions`** `[CODE]` `medium`
- Unit: `api/learning_routes.py:119-143` — locks, asserts `state=='human_review'`, `update learning_objects set state='promoted'`, inserts a transition, returns `{state:'promoted', expert_brain_changed:False}`. No import of `publish_brain` (the file imports only `rollback_brain`, at `:111`). **Not in the audit:** the same handler never touches `knowledge_suggestions`, so an approved suggestion keeps `state='human_review'` and `reviewed_at=null` forever
- Impact: the owner can click approve on Rohit's one pending proposal (`lo_11eb43b06b269b9218fc9125`) and the API reports `promoted` while nothing changes in any decision. A false-positive success receipt is more dangerous than a visible failure. `tests/test_learning_api.py:23-29` only asserts the route accepts POST.
- Fix: inside the existing transaction — reload the immutable proposal, reconstruct the `LearningObject`, re-run `governance.preflight` against the CURRENT policy revision, call `publisher.publish_brain`, write brain/version into the transition detail, set state to `published` (not `promoted`); on failure persist `approved_unpublished`. Add the parallel `knowledge_suggestions` update. Use the already-deterministic transition id at `:141` as the idempotency key.
- Blocks: the only reachable brain-publish path; any L3 consumption receipt; every promotion-quality metric.

**L7-03 · The explicit-feedback seam is pointed at a SQL CTE name, not a table — it can never resolve, and the unit ignores it anyway** `[CODE]` `medium`
- Unit: `feedback/store.py:97` sets `_OPTIONAL_FEEDBACK_TABLE = "canonical_judgments"`; `store.py:101-109` calls `to_regclass('public.canonical_judgments')`. **`canonical_judgments` is a CTE** defined inside `AUDITED_CARD_JUDGMENTS_CTES` at `reason/authority.py:303-308`, consumed only by `feedback/calibrate.py:36-53`. `select to_regclass('public.canonical_judgments')` → **NULL**. The real ledger `card_feedback_verdicts` exists (migration `0034_l4_learning_authority.sql:146`). Second stopper: `units.py:59-63 unit_feedback_learning` returns `[]` without reading `batch.feedback`
- Impact: `batch.feedback` is permanently `()`. **No migration will ever fix it because there is nothing to create** — the name belongs to a CTE. Every "wire the verdict ledger" plan targeting the migration layer will fail silently.
- Fix: change `_OPTIONAL_FEEDBACK_TABLE` to `card_feedback_verdicts` with an explicit column projection joined to `card_feedback_revisions` (the `select *` + `order by 1` at `store.py:105` is not a stable contract); then implement `unit_feedback_learning` with a scope ceiling. Do the one-line rename first — it makes the emptiness measurable.
- Blocks: "Wire card_feedback_verdicts into the canonical feedback-learning seam"; golden scenario C.

**L7-04 · Zero human judgment has ever entered the system — every input seam is empty at the SOURCE, not just the consumer** `[CUSTOMER]` `medium`
- Unit: writers exist and are correct — `api/intelligence_routes.py:740-747` inserts `card_feedback_verdicts`, `:729-735` inserts `human.feedback_signal`, `deliver/actions.py:108` writes `human.card_action`. They have **never been called.** 85 `card_events` total across all orgs: 41 `card.created`, 26 `card.surfaced`, 15 `window.lapsed`, **0 `human.card_action`**
- Impact: even a perfectly wired L7 would learn nothing today. 26 cards were surfaced to Rohit and not one produced a judgment — which is itself the strongest available signal about card quality. Fixing L7 plumbing without fixing card-side capture buys zero learning.
- Fix: not an L7 unit — the owning surfaces are `intelligence_routes.py::submit_feedback` (already correct) and the dashboard/extension clients that must call it. L7's own obligation is to make the emptiness loud (L7-11).
- Blocks: every outcome-driven unit; the entire calibration loop.

**L7-05 · `feedback/calibrate.py` is absent from the audit — and it is the only code that can actually change L3/L4 behaviour from human feedback** `[CODE]` `medium`
- Unit: `feedback/calibrate.py`, 401 lines, invoked every heartbeat from `api/routes.py:330-347`. It WRITES real authority: `:270-288 insert into rule_mutes ... on conflict do update` (kills a firing rule), `:333 update tenant_packs set lvl3_config` (score offsets, OFFSET_STEP=5, OFFSET_BOUND=15), `:354-359` expires cards and signals, `:367 insert into calibration_nudges`. Gates: WINDOW_DAYS=28, MIN_JUDGMENTS=8, MUTE_PRECISION=0.25, MUTE_MIN_JUDGMENTS=12
- Impact: **the audit's remediation plan optimises the path that publishes nothing and ignores the path that already has write authority over the live pack.** `rule_mutes` can deactivate a live rule with 12 judgments and no human in the loop — a governance surface the audit never assessed. (Currently dormant: `calibration_runs` = 0, blocked by L5-07.)
- Fix: audit-coverage correction plus an owner decision — either bring `run_calibration` under the `LearningPolicy`/governance/publisher contract, or explicitly declare it a separate L4 authority with its own review gate.
- Blocks: correct ordering of the whole L7 plan; any claim that L7 is the sole learning authority.

**L7-06 · Published brain values reach no live decision path** `[CODE]` `large`
- Unit: `feedback/consumer.py` (110 lines) defines `snapshot()` as "the ONLY safe way a lower layer reads" learned state — repo-wide grep returns **zero importers outside the package's own tests**. The only decision-path reader of `learned_brain_entries` is `packs/compiler/runtime_brains.py:263-285`, reached via `packs/domain_wiring.py:31` → `reason/domain_shadow.py:81` → `reason/runner.py:528`, gated on `use_domain_compiler=False`
- Impact: two severed ends face each other — L7 cannot write a brain row (L7-01) and L3's live pack path cannot read one. Closing only the publish side produces audited, versioned values that still change nothing.
- Fix: cross-layer contract decision — either `reason/runner.py::run` calls `consumer.snapshot(consumer='reasoning', ...)` on the LIVE pack path and merges ORGANIZATION/BEHAVIOR values into `registry.effective()` output, **or** the owner ratifies that `learned_brain_entries` is compiler-only and `feedback/consumer.py` is deleted rather than left as a decoy seam.
- Blocks: the publish→compile→decision consumption receipt; the final exit gate's "typed intended decision-field delta".

**L7-07 · `policy_incomplete`: persisted learning policy reload silently drops BOTH prohibition fields** `[CODE]` `small`
- Unit: `feedback/orchestrator.py:30-35` SELECTs 11 columns and omits `blocked_targets` and `blocked_subject_prefixes`; `:37-45` constructs `LearningPolicy` without them → `contracts/learning.py:284-285` defaults to `()`. The columns exist (`migrations/0045_l6_learning.sql:33-34`) and `governance.py:36-41` enforces them. **Correction the audit misses:** the seed INSERT at `:47-56` also omits both, there is no policy-write endpoint (`learning_routes.py:146-155` is read-only), and both live policy rows have both columns NULL
- Impact: **latent, not live** — no tenant prohibition has ever been lost because no tenant prohibition has ever been storable. The audit ranks this P0 alongside review-to-publish; that overstates present risk. It becomes a real authority hole the moment anyone adds a policy-write path.
- Fix: add both columns to the SELECT and the seed INSERT, coerce jsonb to tuple, raise `policy_incomplete` (abort the tenant run) when either is NULL on revision > 1. One function, one file.
- Blocks: any future policy-write surface; the P1 preference/temporary-memory inboxes.

**L7-08 · Adaptive lifecycle is unrepresentable and the reset primitive is misnamed** `[CODE]` `large`
- Unit: `contracts/learning.py:224-227` raises `ValueError("only a Runtime target may carry an expiry")` for any non-RUNTIME target; `feedback/consumer.py:81-84` selects `learned_brain_entries` with NO expiry predicate while `:92-95` DOES apply `expires_at > :now` to `temporary_memories`; `feedback/reset.py:33-36` updates ONLY `temporary_memories` and returns the key `adaptive_expired`; `reset.py:1-12` and `api/routes.py:1350-1356` docstrings both say "Adaptive brain leases"; `routes.py:1370` returns `adaptive_expired` straight to the caller
- Impact: harm is **`[MODELLED]`** (0 `learned_brain_entries`, 0 `organization_resets`). What is real now: an owner reading `adaptive_expired: N` from `POST /organization/reset` would reasonably believe Adaptive brain state was invalidated when only Runtime leases moved. Adaptive holds the HIGHEST preference precedence (`runtime_brains.py::_PREFERENCE_PRECEDENCE` = 3) and cannot go stale.
- Fix: (1) NOW, small — rename the return key to `runtime_memories_expired` and correct both docstrings. (2) BEFORE any Adaptive publish — ratify ONE branch (ADR-10): either permit and REQUIRE `expires_at` for ADAPTIVE end to end (type, publisher, consumer, runtime_brains reader, pivot invalidation, rollback, migration on `learned_brain_entries`), or keep ADAPTIVE publication prohibited in `governance.govern` and express temporary guidance as Runtime leases. Until ratified, return `adaptive_ttl_unresolved`.
- Blocks: safe Adaptive activation; **must precede any fix to `units.py:211`**.

**L7-09 · Two migration-created ledgers have zero writers, and one is loaded into every batch and discarded** `[CODE]` `small`
- Unit: `learning_event_inbox` (`0046_l6_learning_hardening.sql:16-33`) is read by `feedback/store.py:117-119` into `LearningBatch.inbox` — **no INSERT anywhere, and no unit references `batch.inbox`**. `learning_input_rejections` (`0046:39-49`), described in the migration as "sanitized isolation of a malformed/lineage-less input", has **zero Python references at all**
- Impact: the layer's own isolation ledger records nothing, so an isolated malformed input is indistinguishable from an absent one. The audit's no-silent-drop contract has a table waiting for it and no producer.
- Fix: `store._load_enterprise`/`_read_optional_seam` write an isolation row into `learning_input_rejections` on every row dropped by the lineage join or the exception handler at `store.py:108`; either implement a unit consuming `batch.inbox` or remove `_load_inbox` and the field.
- Blocks: "Expose learning input and run health"; the no-silent-drop contract.

**L7-10 · Customer value analytics is hardcoded AND its one non-hardcoded counter matches on the wrong column** `[CODE]` `small`
- Unit: `api/intelligence_routes.py:544-546` returns literal `outcomes_recorded: 0, value_recovered_inr: 0, intervention_rate: None`. **Not in the audit:** `:540-542` computes `actions_taken` as `count(*) from card_events where kind in ('run_play','do_it_myself','card.acted','card.done')` — but writers put those values in the `cause` column (`:729-733` writes `kind='human.feedback_signal', cause=:cause`; `deliver/actions.py:108` writes `kind='human.card_action'`), and `reason/authority.py:280-282` correctly filters `ce.kind='human.card_action' and ce.cause in (...)`. Separately `api/routes.py:1710-1723` returns hardcoded EMPTY SHAPES with honest docstrings — the safe version
- Impact: `/v1/insights/stats` can never report a non-zero action or outcome even after users start acting. The bug will present as "the learning loop still isn't working" long after it is, and will be debugged in the wrong layer.
- Fix: change the `actions_taken` predicate to match `reason/authority.py`'s contract; replace the three constants with reads from `execution_outcomes` plus an explicit `data_unavailable` state rather than 0.
- Blocks: "Replace hardcoded customer value statistics with the canonical ledger"; golden acceptance of any outcome metric.

**L7-11 · The run counter reports review-queued proposals as `published`** `[CODE]` `small`
- Unit: `feedback/orchestrator.py:106-111` — after `sink = publish(...)` it executes `published += 1` regardless of the sink string. Rohit's only run `lrun_cbd50411bcc94c81ab6a2fc6` records `counts = {"held":0,"refused":0,"inserted":1,"proposals":1,"published":1,"unchanged":0}` while `learning_object_evaluations` for the same run correctly records `result_state='human_review', sink_reason='queued_for_review'` — **two ledgers disagreeing inside one transaction**
- Impact: `published = 1` is the number an operator or status endpoint reads. It is wrong for every review-routed object, which today is 100% of brain-target objects.
- Fix: derive counters from the returned `sink` string with a distinct `queued_for_review` bucket; add per-seam counts and an explicit `degraded` flag when a required seam is empty (data already available from `store.py:50-53`).
- Blocks: "Expose learning input and run health". Small — **do it early**; it is what makes every other gap visible without a psql session.

**L7-12 · No joined recommendation → exposure → action → delivery → external-result → counterfactual ledger (RC-7 / B-10)** `[CODE]` `new_subsystem`
- Unit: does not exist. Requires L2-16 (completion truth), L5-05 (execution truth), L6-05/L6-07 (delivery truth) first
- Impact: the same bad card can repeat forever; no ROI number can be produced honestly; there is nothing to show a design partner at the end of a trial.
- Fix: build the canonical ledger with a **pre-registered otherwise-action** and the ten-field counterfactual contract (situation id, recommendation+version, otherwise-action, acceptance state, actual action, delivery/exposure, declared outcome+window, alternative causes, attribution class, value/cost). Only `caused` and an explicitly weighted portion of `assisted` may enter attributable value.
- Blocks: any Outcome-proven claim; the trial-conversion value story.

---

## X — CROSS-CUTTING

**X-01 · No provenance/authority envelope — tenant, client_context, role, visibility/use, origin, versions and invalidations are not propagated L1→L7 (RC-8 / B-09)** `[CODE]` `large`
- Unit: `grep -rn "client_context_id" genios_engine` → **0 hits**; `context/situation_bso.py:114,148` hardcode `Visibility(scope="org")`
- Impact: rated CRITICAL. Cross-client or private-to-commercial leakage; a safe local component still produces an unsafe global result. **`[MODELLED]` for this single-tenant founder org — must NOT be reported as a current leak.** It is a market-expansion gate.
- Fix: a common envelope with deterministic consumer rejection; propagate `(org_id, client_context_id, identity_or_relationship_key)` plus role, visibility/use, origin, versions and invalidations through every boundary. **Constrains every arrow of the chain rather than sitting in it.**
- Blocks: any vertical promotion claim beyond one tenant; agency/community/cohort lanes; replays 09 and 12.

**X-02 · No abstention level vocabulary exists anywhere** `[CODE]` `large`
- Unit: `packs/sales_v1.py` + `general_v1.py` emit exactly two values — `prescriptive` (14 rules) and `predictive` (11); `cards.level` is bare text with no enum; the only file in `genios_engine/` mentioning abstention is `reason/reasoners/constraint.py:42,400`, whose output is an ELIMINATE row, not a deliverable card state
- Impact: the system is structurally incapable of saying "I don't know" or "this is outside my coverage". With 0 accepted capabilities, 100% of what it emits is prescriptive advice on domains it has no reviewed expertise for.
- Fix: an enum in `contracts/` (`prescriptive|predictive|observation|review|wait|suppress`) threaded through `packs/registry.py`, `reason/rules.py::_rule_from_dict:25`, `deliver/pipeline.py`, `deliver/card_builder.py` and a cards migration; plus a policy in `reason/orchestrator.py` downgrading to `observation` when the resolved capability's review_state != accepted.
- Blocks: the pilot's `observation_only` default; CP-2 and CP-4 exit gates; the entire missing-expertise replay family; L6-16.

**X-03 · The product baseline is RED: 9 failures in 3 clusters** `[TEST]` `small` — see §8.

**X-04 · Health metrics prove jobs and schemas, not semantic readiness (RC-9 / B-11)** `[CODE]` `medium`
- Impact: "Present / Wired / Tested" is communicated as active intelligence; an empty sweep looks healthy; a skip reads as a pass.
- Fix: per-boundary SLO receipts — source coverage, BSO validity, capability closure, authority mode, decision completeness, execution weld, delivery reconciliation, learning consumption, counterfactual.
- Blocks: any release claim requiring repo-green.

**X-05 · The audit package makes ZERO `[RUNTIME]` claims** `[CODE]` `medium`
- Unit: `grep -r '\[RUNTIME\]'` across all 73 package `.md` files returns **exactly one hit** — the label's own definition at `00-Methodology/01:34`. Class distribution: `[CODE]` 118, `[MODELLED]` 89, `[SCREENSHOT]` 37, `[TEST]` 29, `[ATLAS]` 28, `[CUSTOMER]` 24, `[INFERENCE]` 5, `[PROPOSAL]` 2, `[UNKNOWN]` 2. Its own limitation column: *"Checkout evidence does not prove deployed tenant state."*
- Impact: every "Framework-ready, not live-ready" verdict is a ceiling derived from code shape. Where runtime is worse — level hardcoding, 17 dark reasoners, 0 executions, 4-of-5 constant components, 100% NoExpertiseRoute — the audit reports the code's capability, not the customer's experience. **Reading the package alone leads to under-scoping.**
- Fix: a pinned read-only SQL manifest per layer run against the design-partner org, so every `[CODE]` verdict carries a paired `[RUNTIME]` row. The missing eighth rung between Tested and Outcome-proven.
- Blocks: trusting the audit for release sequencing.

**X-06 · The package index advertises a status legend the methodology does not define** `[CODE]` `small`
- Unit: `README.md:40` says "Built, Partial, Shadow, Stub, Missing, Outcome-proven"; `00-Methodology/05` defines Absent, Stub, Present, Wired, Live, Tested, Outcome-proven
- Fix: correct `README.md:40` to the seven states; note that "Shadow" is shorthand for Present+Wired+Tested with `live_delivery_enabled=False`, not an eighth state.

**X-07 · Ten ADRs unratified** `[ATLAS]` `medium` — ADR-01 channel/recipient ownership · ADR-02 first authoritative expertise lane · ADR-03 Organization Brain source of truth · ADR-04 confidence surface · ADR-05 canonical lifecycle IDs · ADR-06 outcome/value attribution · ADR-07 LLM budget authority · ADR-08 Organization review-to-publish state machine · ADR-09 learning-policy fidelity · ADR-10 Adaptive TTL/decay target. Ratification schedule in §6.8.

**X-08 · `genios_engine/LAYERS.py` docstring is stale** `[CODE]` `small` — says "an `executive` package will be extracted additively when that split happens" while the `LAYERS` dict below already contains `"executive": 5` and the package exists with 23 modules; the translation table omits `executive`. Harmless to runtime, but it is the file the methodology names as the canonical layer-number source.

**X-09 · No golden-replay harness exists — the 12 replays are specifications with no executable fixtures** `[MODELLED]→required` `large`
- Impact: every exit gate in the program is unverifiable without it. The audit's own acceptance definition cannot be run.
- Fix: pinned fixtures + deterministic mutations for all 12 replays (Theresa, Boardy, availability/reschedule, already-replied, group meeting, closed/rejected/deferred, missing expertise, agent handoff, client isolation, pivot/Adaptive, revenue counterfactual, Antler exploratory), each with an LLM-disabled determinism assertion.
- Blocks: **every phase exit gate in this program.**

**X-10 · No per-execution / per-client cost attribution (D-07)** `[CODE]` `medium`
- Unit: `llm_costs` has no execution key and no client key; V2 engine cost is recorded to the table and never to analytics
- Impact: no margin or 5–10× ROI claim is computable. The mandated metric is "cost per useful ACCEPTED decision" — the denominator is currently zero (`executions` = 0), so every cost-per-value number is **undefined**, not an estimate.
- Fix: add `(execution_id, client_context_id)` attribution columns to `llm_costs`; join into the L7-12 ledger.

---

# 2. THE FOUR BRAINS

| Brain | Storage | Who may write | Runtime influence today | What makes it real |
|---|---|---|---|---|
| **Expert** | Git YAML corpus `Domain Expertise/**` (1,748 files, 152 capabilities) | Human authors only — never machine-written | **Partial and shallow.** Reaches L4 only via `expertise.py::_plays` (steps-only, 4-play cap, generic `review_situation` fallback) — and that path is dark (`use_domain_compiler=False`, `expertise_packages`=0). The LIVE authority is the 25 legacy pack rule dicts, not the corpus. | L3-01 routability + L3-03 admission + L3-04 accepted state + L3-09 authored content + L4-09 non-steps consumption |
| **Organization** | Postgres `learned_brain_entries` (brain='organization') | L7 publisher, after human approval | **NONE — the table has 0 rows in every org.** Even if populated: `expertise.py:184-186` hashes `organization_rules` and no `reason/` file reads it. And approval never publishes (L7-02). | L7-02 review→publish + L7-01 reachable path + L3-05/L4-04 typed consumer (org rules → `policies`/`Goal.constraints`, may **eliminate** candidates) + ADR-03/ADR-08 |
| **Behavior** | Postgres `learned_brain_entries` (brain='behavior') | L7 `unit_behavior_evolution` | **NONE.** `feedback/units.py:167 _cohort_candidate` returns `[]` — the unit emits nothing, ever. Hash-only downstream. | L7-01(a) cohort emission + L3-05/L4-04 typed consumer with a **narrow authority: may only reorder already-eligible candidates and adapt wording/timing** — never eliminate, never grant permission |
| **Adaptive** | Postgres `learned_brain_entries` (brain='adaptive') | L7 `unit_recommendation_learning` | **NONE, and structurally trapped.** The only emitter hardcodes `distinct_days=1` against policy `min_distinct_days=2` → rejected every run; and `contracts/learning.py:224` forbids ADAPTIVE from carrying an expiry, while `consumer.py:81-84` and `runtime_brains.py` apply no expiry filter. It holds the **highest** preference precedence (`_PREFERENCE_PRECEDENCE`=3). | ADR-10 first — either mandatory TTL end-to-end, or prohibit Adaptive publication and use Runtime leases. **Then** L7-01(b). Fixing `units.py:211` before ADR-10 arms an immortal-preference hazard |

**The invariant that governs all four (03-Four-Brains §"What brain_snapshot_id actually proves"):** a changed `knowledge_hash`, package id, manifest version or brain_snapshot_id with an identical judgment **scores ZERO** and is a test FAILURE, not a pass. Every selected decision-relevant entry must emit either a typed semantic effect or an explicit deterministic `semantic_no_effect` receipt.

**Acceptance = one-brain-at-a-time metamorphic mutation.** Pin BSO, Expert corpus and three brains; mutate exactly one entry in the fourth. Company-approval mutation must **block or require approval** on a previously-winning candidate. Behavior mutation may **only reorder**. Adaptive mutation may **only move bounded timing/priority and must carry an expiry**. An inapplicable mutation must preserve the decision and emit the no-effect receipt.

**Precedence, unchanged:** permission runs Organization → Expert, and learned brains can never GRANT permission. Preference runs Adaptive → Organization → Behavior → Expert.

---

# 3. THE LLM MAP

## 3.1 Current inventory — verified at HEAD

Six cost purposes across eight invocation points. **All `claude-haiku-4-5-20251001`.**

| Purpose | Call site | Calls | Tokens in/out | Layer | Authority held |
|---|---|---|---|---|---|
| `relevance_gate` | `capture/gate/relevance.py:186` (batch, 12/call) + `:222` (single) | 160 | 206,944 / 36,640 | L1 | **Destructive drop** ← the one place a model holds authority it must not |
| `extract` | `context/extract/extractor.py:42` + `:44` (repair) | 278 | 402,730 / 190,200 | L2 | Fact/observation proposal only; confidence is deterministic by authority rank |
| `l5_render` | `deliver/render.py:111` (`max_tokens=600`) | 43 | 25,475 / 6,903 | L6 (mislabelled) | Copy only; V-01/V-02 validators gate it |
| `intelligence_query` | `reason/intelligence.py:381` | 1 | 237 / 43 | Ask path | **Explanation only** — decision frozen before the call |
| `intelligence_analyze` | via `api/intelligence_routes.py:309` | — | — | Extension | Analysis text |
| `intelligence_draft` | `api/intelligence_routes.py:1098` (`max_tokens=500`) | — | — | Extension | Draft copy |

**Layer 3 has ZERO LLM calls** (`packs/compiler/**` is pure parse/resolve/hash/build). **Layer 4 has zero judgment LLM.** **Layer 5 has zero** (grep across all 23 `executive/` modules returns only docstrings). **Layer 7 has zero.**

**Total lifetime spend for the design-partner org: ≈ $1.30.** 96% of tokens are L1/L2 capture.

**The consequence, stated plainly:** the LLM never participates in judgment. It gates junk, extracts facts and writes copy. The actual reasoning is deterministic dict-matching over a thin fact set — 25 rule dicts, of which 7 fire, over facts extracted by a global prompt that has never heard of fundraising.

## 3.2 Target allocation, per layer

Reconciled against `08-Cross-Layer-Synthesis/06-LLM-Allocation-Current-vs-Atlas-vs-Proposed.md` and each layer's `05-LLM` doc. The frame **rejects whole-layer percentages** (`00-Methodology/05` §"LLM audit method"): every LLM decision decomposes into task / current path / proposed rate / deterministic pre-gate / deterministic post-gate / cache key / cost / forbidden authority.

### L1 — KEEP the call, CHANGE its authority and its vocabulary. Model tier: **Haiku (do not upgrade).**
- **Remove destructive authority (L1-02):** three-way disposition keyed on `relevance` against a named threshold; the model may PARK but never DROP. This is the single most important LLM change in L1 and it costs nothing.
- **Add `reason` to the batch prompt** (`relevance.py:105-110`) so every verdict is legible.
- **Feed pack vocabulary:** `capture.classifier_hints` from `registry.effective()` (needs L3-08) so the gate knows what a fundraising thread looks like.
- **Do NOT add** an OCR model call — Tesseract is deterministic and free.
- **Cost delta:** ~0. Slightly longer prompt with hints ≈ **+$0.02/org/month**. Batching already collapses ~472 gated emails into 68 calls.
- **The audit's P1.3 (merge L1+L2 calls for cost) is not supported by the ledger** — relevance_gate is $0.13 lifetime vs extract $1.04. Merge for semantic consistency if you like, never on a spend rationale, and never ahead of the P0 correctness work.

### L2 — the biggest change in the program. Model tier: **two-tier Haiku → Sonnet.**
- **CHANGE `context/extract/prompt.py` from a module constant to `build_prompt(*, signal_vocab, schema_fields, classifier_hints, domain_list)`** called from `extractor.py`. Pack-aware extraction is the change that makes every L3 corpus investment able to pay off in capture quality. Depends on L3-08.
- **ADD to the SAME call, not a second one** (per `05-LLM` §"Reuse combined call fields; no second call unless offline repair cohort proves value"):
  - typed `roles` array — requester/connector/target/owner/approver with evidence spans (L2-06)
  - a real commitment definition with three negative examples + a `scheduling_proposals` array (L2-07)
  - meeting lifecycle fields — occurred / attended / external_counterparty (L2-15)
  - a `fundraising` domain in the domain list (L2-05)
- **Deterministic pre-fill first:** From/To/Cc headers resolve roles before the model sees them; the model fills only the ambiguous multi-actor case (~10–25% of unstructured events per `05-LLM`).
- **Deterministic post-gate:** reject a commitment whose `evidence_text` ends in `?` or contains no verb of obligation.
- **Model tier — this is the ONE call that justifies Sonnet.** Role resolution and commitment-vs-proposal discrimination cause the most customer-visible damage (Boardy as target; *"Deliver 'Can we do next week?'"*), and both are span-grounded so they are verifiable. Route: Haiku for the fact/observation pass; escalate to Sonnet only when the deterministic pre-fill leaves roles ambiguous or a commitment candidate is detected.
- **Cache:** bump `PROMPT_VERSION` and add model id + `EXTRACTION_SCHEMA_VERSION` to the key (L2-13) or **you ship the fix and measure nothing** — the org has 260 cached extractions.
- **Cost delta:** base extract ≈ $1.08 lifetime. Longer pack-aware prompt +~1.5k tokens in. If 20% escalate to Sonnet ($3/M in, $15/M out): ≈ $0.67 + $1.26. **Total ≈ $2–3 per org at current volume — roughly 2–3× on a base of $1.**
- **Retry ceiling:** `05-LLM` flags that SDK retries (`max_retries=2`) × one extractor repair × `_MAX_ATTEMPTS=3` in `context/runner.py` compound to **18 theoretical HTTP attempts per event**, and `record_cost` ledgers only the final returned result — the bill is under-reported by construction. Meter physical attempts separately before increasing spend.

### L3 — **ZERO runtime LLM, permanently. Offline authoring only.**
- **Runtime:** the compiler must stay pure parse/resolve/hash/build. Putting a model inside compilation places an unreviewed generator inside the authority path — precisely what the review gate exists to prevent.
- **Offline authoring pipeline (ADD):** source intake → draft → adversarial challenge → reconcile → golden-test draft → **human promotion**. Content-addressed cache keyed on source hash + prompt + model + schema version; cheap-first routing; one repair-retry ceiling.
- **Model tier:** drafting and adversarial challenge justify **Sonnet, and Opus for the challenge pass** — but strictly offline, and cost measured **per ACCEPTED artifact, not per generated YAML file.**
- **HARD RULE (`06-LLM` §"Expertise matching"):** deterministic shortlist first, **NO full-corpus prompt**. Prompting across 152 capability files per situation is the single most expensive mistake available and the audit forbids it by design.
- **Cost reality:** `metadata.created_by: ai` on 152/152 with `reviewed_by` empty on 152/152 — **the corpus IS the output of an unreviewed LLM authoring run. The draft-to-accepted ratio is 152:0.** The dominant cost is reviewer-hours, not tokens.

### L4 — **ZERO judgment LLM. Preserve the one bounded call verbatim.**
- `reason/intelligence.py:198-409` is correctly built and must not be touched: `_fixed_recommendation` selects the action deterministically **before** any call; `_prompt` embeds the decision as "FIXED DECISION (immutable)" and forbids choosing/ranking/adding; the response must have exactly the key set `{"explanation"}` or it is rejected; `_validated_explanation` + `_DIRECTIVE_RE` strip anything imperative and fall back to deterministic text. It has been exercised **once** — the risk of fluent explanation making a generic decision look deeper is future, not present.
- **Do NOT add** a model to candidate generation, ranking, elimination, confidence, or abstention. The reason L4 is shallow is **candidate scarcity (1.00 per run) and four constant score components** — no model spend can repair a missing candidate set.
- **ADD later (Phase 3 only), under the same fixed-decision contract:** after the decision AND its alternatives are frozen, one bounded call may draft the rationale for the alternative and the stop rule. Haiku, ≤700 output tokens, cached on decision hash.
- **Cost delta:** ~0 now; +1 bounded Haiku call per opened card once alternatives exist.

### L5 — **ZERO, and fixing L5 costs zero incremental LLM spend.** The entire L5 gap register is deterministic plumbing. Nobody should reach for a model to make commitments appear; they already build correctly (27/27, zero refusals) and the reason they do not exist is a missing import. Later, grounded reminder prose only — Phase E in the audit's order, never before meaning is correct. `05-LLM` §"Why an '80% LLM Layer 5' target is wrong": Atlas's weight-80 applies to drafting prose, not to 80% of Executive authority.

### L6 — **CHANGE, and it is the only place spend goes DOWN.** Model tier: Haiku for copy, **Sonnet for the on-demand draft only.**
- Split `render.py:111`: deterministic card copy at build time; **artifact generated on demand** when the founder opens the draft. 37 of 41 artifacts are discarded today.
- Separate V-01 (deterministic length repair, one retry) from V-02 (invention — no retry, ever).
- Cache on evidence hash; `pipeline.py:49-54`'s expired-card rebuild currently re-calls the model on identical signal state.
- The draft artifact is an outbound email in the founder's voice to an investor — that justifies Sonnet, and volume is low because it is request-gated.
- **Cost delta: negative.** Today 43 calls × 600 max-out for 4 usable results. After: ~41 cheap copy calls + ~5–10 requested drafts. **Net −40% tokens even with Sonnet on drafts.**
- Rename `purpose="l5_render"` → `l6_render` before any cost dashboard is built on the purpose column; and stop swallowing the sink failure at `render.py:116-117`.

### L7 — **ADD small, offline, zero authority.** Clustering/hypothesis for learning proposals and reviewer briefs (5–15% of workload). Thresholds, validation, promotion, TTL and rollback stay deterministic. **Cost delta ~0 until feedback volume exists** — every eligible-event count in L7 is currently zero, so the LLM budget question is *undecidable* until L7-04 produces the first human judgments. Do not spend planning time on prompt design here.

## 3.3 Where an LLM must NEVER be added

Carried verbatim from `CTO-README §10` and `06-LLM-Allocation`:

| Layer | Model may | Model may **never** own |
|---|---|---|
| L1 | extract, summarize | provenance, tenant boundary, immutable event identity, **destructive drop** |
| L2 | hypothesize roles, extract requests | final identity merge, freshness gate, resolved-state without evidence |
| L3 | assist authoring (offline) | review acceptance, capability authority, route eligibility |
| L4 | generate candidates, draft rationale | hard disqualification, permission, policy override, fabricated confidence |
| L5 | draft plan language | owner authority, approval requirement |
| L6 | adapt message copy | authorize sending, claim delivery |
| L7 | summarize outcomes | causal proof, global promotion, TTL bypass |

## 3.4 Rough per-org cost delta

| | Now | Target | Δ |
|---|---|---|---|
| L1 relevance_gate | $0.13 lifetime | ~same +hints | +$0.02/mo |
| L2 extract | $1.04 lifetime | pack-aware + 20% Sonnet | ×2–3 |
| L3 runtime | $0 | **$0 (hard)** | 0 |
| L3 offline authoring | $0 | one-time per lane; reviewer-hours dominate | see §4 |
| L4 | ~$0 | +1 bounded Haiku/opened card | +small |
| L5 | $0 | **$0** | 0 |
| L6 render | $0.05 lifetime | split + cache | **−40% tokens** |
| L7 | $0 | offline, ~0 until volume | 0 |

**Net runtime per-org: ≈$1.30 → $2.50–3.50/month at current volume.** At 50× volume that is under $200/org/month against a ₹25k/mo plan. **LLM cost is not a constraint and must not shape the plan.** The constraint is reviewer-hours in L3.

**Two things that are NOT wins:** (1) the low bill today is not efficiency — 37 of 41 cards are empty drafts, so cost is near zero *and so is value*; do not report it as a saving. (2) The mandated metric is **cost per useful ACCEPTED decision**, and it is currently **undefined** (`executions` = 0 → denominator zero). Report "undefined", never an estimate, until Phase 4 mints an ExecutionObject with an observable completion predicate.

---

# 4. THE MODULE / CORPUS QUESTION

## 4.1 What the old modules actually are

`packs/sales_v1.py` = 20 rule dicts. `packs/general_v1.py` = 5. A rule dict is:

```
{ id, level, scope, when[] (has_obs | path+op+value | days_since), score, play, cooldown, render_hint }
```

That is the entire content of "expertise" in production today. `unanswered_email` is `ball_in_court='us' AND days_since(last_inbound) >= 2`, with a render_hint instructing *"a direct order to reply to this person now — imperative voice ('Reply to X now')"*. It fires 22 of 41 times.

The gap between this and a capability is not size — it is **kind**. A rule dict fires. A capability reasons **and declines**.

## 4.2 What a properly authored L3 capability consists of

Per file, in `Domain Expertise/<Domain> Expertise/capabilities/<NN-group>/<name>/`:

| Artifact | Contents | Currently |
|---|---|---|
| `capability.yaml` | `identity{id,name,stub,status,version}`, `metadata{created_by,review_status,reviewed_by,confidence,notes}`, the capability's **question**, required facts, exclusions | 152 exist; 149 stubs |
| `knowledge.yaml` | heuristics, mental models, **failure patterns** | present on non-stubs only |
| `objects.yaml` | scoped objects + **inference patterns**, each needing a source fact L1/L2 actually emits | ICP has 20 patterns, **11 blocked** |
| `situations/*.yaml` | `identity.id`, `owner_capability`, `matches.l2_situation_types`, `matches.when`, `priority_bp`, `scope`, `objects.load` / `never_load`, `also_serves` | Sales 6, Support 14, Admin **0** |
| `heuristics/<name>/` | per-heuristic files | ICP has 8 |
| registry row in `<domain>/registry/situation-capability-map.yaml` | route binding | Sales 18 mapped / 28 orphan; Support 10 / 39; Admin 0 / 57 |
| **golden fixtures + counterexamples** | acceptance set proving it fires when it should and abstains when it shouldn't | **do not exist for any capability** |
| **accepted content hash + dependency closure** | immutable admission receipt | **field does not exist** |

## 4.3 The stub → authored → reviewed → accepted lifecycle

| State | Field | File | Who sets it | Who READS it today |
|---|---|---|---|---|
| stub | `identity.stub: true\|false` | `capability.yaml` | author | **`packs/compiler/capability_resolver.py:101` — the ONLY runtime read of any lifecycle field** |
| authored | `identity.status: draft\|review\|stable\|deprecated` | `capability.yaml` (enum in `_schema/capability.schema.json:22`) | author | **nobody** |
| reviewed | `metadata.review_status: unreviewed\|in_review\|approved` | `capability.yaml` | reviewer | **nobody** |
| reviewer identity | `metadata.reviewed_by` | `capability.yaml` | reviewer | **nobody** |
| **accepted** | `admission.accepted_by` / `accepted_at` / `accepted_content_hash` | **does not exist in any schema, corpus file, engine module, or DB table** | — | — |

**So the entire production-admission ceremony is one author flipping a boolean in a text editor.** Making it real = L3-03 (resolver gate) + L3-04 (schema) + mirrored enforcement in `_tools/validate.py` so CI blocks before runtime does.

## 4.4 Current corpus counts — unsoftened, verified at HEAD

```
Sales Expertise              46 capability.yaml   43 stub   3 non-stub
Customer Support Expertise   49 capability.yaml   40 stub   9 non-stub
Admin Expertise              57 capability.yaml   57 stub   0 non-stub
-------------------------------------------------------------------
TOTAL                       152 capability.yaml  140 stub  12 non-stub
  status: draft            152 / 152
  review_status: unreviewed 152 / 152
  reviewed_by: (empty)      152 / 152
  REVIEWED                    0
  ACCEPTED                    0   (the field does not exist)
Total files in corpus tree  1,748
```

Routing: 26 L2 types total, **19 route into Sales, 5 into Support, 0 into Admin, 6 globally unrouted** (`budget_freeze`, `champion_left`, `deal_sentiment_negative`, `objection_open`, `proposal_no_response`, `timeline_slip` — two of which fire live for Rohit). All-stub routes: Sales 7, Support 3. Orphan capabilities with no situation routing into them: Sales 28, Support 39, Admin 57 = **124 of 152**. One unreachable object.

Validator: **0 errors, 715 warnings — and it validates against a substrate that does not exist** (L3-07), so the 0 certifies nothing about routability. Live routing truth: **73/73 = 100% NoExpertiseRoute** (L3-01).

## 4.5 What authoring the full corpus actually involves

Observed reference: the one substantially-authored capability, `sales.market_and_targeting.icp_definition`, carries `capability.yaml` + `knowledge.yaml` + `objects.yaml` + 2 situations + 8 heuristic files + 2 scoped objects with **20 inference patterns** — and its own notes record that **11 of the 20 are blocked** on `account.industry` / `account.employee_count` / `account.geography` as typed L1 facts that do not exist.

**Honest per-capability effort:**
- Authoring (domain expert, with LLM assist): **1.5–3 person-days** — question, required facts, exclusions, objects, inference patterns, heuristics, mental models, failure patterns, counterexamples, situation bindings with priority and `never_load`
- Review to acceptance (named reviewer, adversarial): **0.5–1 person-day**
- Steady state after the schema stabilises: **~2 person-days per capability, all-in**

**Volume:**

| Scope | Capabilities | Person-days @ 2/cap | FTE-months |
|---|---|---|---|
| The ONE lane (CP-2) | 2 (lead_qualification + icp_definition companion) + their dependency closure | ~10–15 | 0.5–0.75 |
| Sales remainder | 44 | ~88 | ~4.5 |
| Customer Support | 49 | ~98 | ~5 |
| Admin | 57 | ~114 | ~5.5 |
| **Full corpus** | **152** | **~304** | **~15 FTE-months** |

Plus a fraction of that output is **dead on arrival** until L1 enrichment lands — the ICP capability's blocked-pattern rate is 11/20 = **55%**, and nobody knows the corpus-wide rate.

**This is precisely why the audit says one lane first.** Not to scope down — to learn the true per-capability cost and the true blocked-pattern rate before committing 15 person-months. Under the mandate the full corpus stays in the program (Phase 8, L3-09b) with a named dependency: **per-capability effort and blocked-pattern rate are unknown until one lane is accepted end to end, and authoring against a route index that resolves 0/73 is measured waste.**

**And the reviewer backlog is not a future risk — it is the current state, 152 files deep.**

---

# 5. RECONCILE WITH THE OWNER'S GROUNDED FINDINGS

## 5.1 What the audit ADDS (things we did not have)

| Addition | Evidence |
|---|---|
| **L3 is not "dark, flip a flag" — it is UNROUTABLE.** The corpus routes on pack reason_codes; the compiler looks up L2 `situation_type`. **73/73 = 100% NoExpertiseRoute.** | `capability_resolver.py:63` vs `domain_spec.py:139-176`; in-process run against the real catalog |
| **Layer 5 is blocked by nothing in itself — it has never been CALLED.** `NameError` at `api/routes.py:409`, every tick since 2026-08-08. Real functions produce 27 executions with zero refusals against live Postgres. | `routes.py:409`, `git show 02241c9:...:355`, rolled-back live replay |
| **Four starvation gates upstream of delivery**, none of which the audit names: `org_channels` 0 rows, band cut unreachable, `org_seats` 0 rows, `executions` 0 rows | `outbox.py:483-487`, `outbox.py:167`, `router.py:27-37` |
| **The feedback seam points at a SQL CTE, not a table.** No migration can fix it. | `store.py:97` vs `authority.py:303-308`; `to_regclass` → NULL |
| **`cards.level` is a hardcoded literal while `signals.level` carries `predictive` correctly** | `deliver/pipeline.py:35`; `signals` group-by |
| **Calendar watermark is in the FUTURE — gcal permanently frozen** | `sync_runner.py:170`, `sync_cursors` = 2026-08-24 08:30 |
| **Whitelist ordering skips the document park for the highest-value senders** — 108 live instances, absent from the audit's own L1-01..L1-22 catalog | `gate.py:31-40` vs `rules.py:97-104` |
| **`org_seats` empty disables the entire L2 self-exclusion chain** → founder typed as sales prospect, own company as opportunity | `context/runner.py::_internal_emails`, `pipeline.py:644` |
| **The `commitments` extraction contract has no definition of a commitment** — "Can we do next week?" becomes a prescriptive overdue card | `extract/prompt.py`; live `commitment.text` values |
| **`feedback/calibrate.py` exists, runs every heartbeat, and has real write authority** over `rule_mutes` and `tenant_packs.lvl3_config` — absent from the audit AND from our findings | `calibrate.py:270-288,333`; `routes.py:330-347` |
| **A second, OPEN agent door** at `deliver/agent_api.py` behind `POST /v1/signals/{id}/claim` — 15-minute lock, no approval token, no lease, no revocation | `routes.py:2490-2520` |
| **The 12 golden replays** as an executable acceptance definition of "correct" | `09-Golden-Replays/**` |
| **The RC-1..RC-9 / B-01..B-11 / ADR-01..ADR-10 dependency spine and its reasoning** | `08/09` and `08/12` |

## 5.2 Where the audit or we are WRONG — adjudicated

1. **`score_components` "= 5000 on all 144 rows"** — ours is right on the four, but **`urgency` is a fifth component and it DOES vary** (10000 ×155, 6500 ×35, 9900 ×26, 9800 ×14, 9600 ×7). Row count is now 251 (a re-run, not drift). **Adjudication: our finding upgrades from "scores are compressed" to "there is no ranking, only a clock."** And even urgency is unread — `priority_override` bypasses the formula entirely.
2. **"652 of 907 emails dropped"** — live: **657 dropped / 1,306 landed gmail**, plus 504 further objects deduped at landing. The 907 denominator does not reconcile with any column. **Adjudication: use 657/1,306 = 50.3% dropped, 27.8% reaching L2.** Direction identical, magnitude corrected.
3. **"L1 domain hints are a hardcoded 8-keyword regex"** — precisely, three domains × 8 keywords + 6 source priors. **Adjudication: refinement, and the material point is worse than a size complaint — there is no fundraising domain at all, so 95.9% of events carry no hint.**
4. **"Impact=55 constant on cards"** — 38 of 41, two distinct values. **Adjudication: substance survives and strengthens one layer down — 5000 on all 251 candidate rows.**
5. **"`live_delivery_enabled=False` keeps things dark"** — true for the L3/expertise path; **NOT true on the L4→L5 authority path.** All 8 `reasoning_capability_snapshots` carry `live_delivery_enabled=true` and 26 signals pass the complete ~9.5KB `AUTHORITATIVE_SIGNAL_PREDICATE`. **Adjudication: authority is healthy. Do not go looking for a flag on the L5 path.**
6. **"23 reasoner files but only 6 fire" vs the audit's "17 units"** — both correct at different granularity: `default_registry()` registers 23 (17-unit frozen roster + 6 supplementary); of the 17-roster only 3 have ever run. **Adjudication: not a contradiction.**
7. **`08/01` coverage matrix credits L4 with "deterministic elimination/ranking/abstention"** — defensible at `[CODE]` (`constraint.py:42,400`), misleading at runtime: 41/41 prescriptive, zero eliminations, DEFER unreachable. **Adjudication: the honest row is "abstention Present, never Live."**
8. **Audit test baseline "9 failed / 1,314 passed / 39 skipped"** — does not reproduce. Measured at the same commit: **9 failed / 1,416 passed / 15 skipped / 1,440 collected.** Failure count and all three clusters match exactly. **Adjudication: cite "9 failures in 3 named clusters"; drop 1314/39 from any deck.**
9. **Audit P0 "require current lineage / graph-version fence"** would **reintroduce the bug that emptied the founder's queue every 6 hours** (`reason/authority.py` removal comment). **Adjudication: the 4 red tests are STALE ASSERTIONS, not a live authority hole. Fix the tests; do not touch `authority.py`.**
10. **The audit's entire L2 P0 register edits `context/situation_bso.py`** — a file that does not execute in production (`use_domain_compiler=False`; `domain_shadow` is its only importer). **Adjudication: the correct P0 is the CONSUMER (`reason/runner.py:610-640`), not the producer.**
11. **Audit blames unregistered domains for false 100% coverage.** Live cause is the **registered** `general/relationship` spec whose one expected field is written mechanically on every inbound email. **Adjudication: fixing the unregistered default moves ZERO of the 34 rows.**
12. **Audit ranks Adaptive-TTL (`B-10C`) and policy block lists (`B-10B`) as P0 live hazards.** Both are **latent** — 0 `learned_brain_entries`, both policy columns NULL, no policy-write path, and the only Adaptive emitter is rejected every run. **Adjudication: fix them because they are 2-line fixes, not because they are on fire.**
13. **Audit: "the value API is hardcoded to zero."** `api/routes.py:1710-1723` returns hardcoded **empty shapes with honest docstrings** — the safe version. `intelligence_routes.py:544-546` IS hardcoded zeros. **Adjudication: split the claim.**
14. **Audit's recommended lane trigger `buying_signal` cannot fire for this org** (0 `budget_approved` observations; `intro_followup` also 0 despite 87 `introduction` observations). **Adjudication: keep the lane — its unnarrowed `inbound_fit_check` routing deliberately bypasses the 9% `ball_in_court` gate — but change the evaluation set and say so in ADR-02.**
15. **Audit oversizes `L6-LP-04` (lexical priority sort).** `_PRIORITY_RANK` and a full anti-starvation `scheduler.py` already exist unused. **Adjudication: one ORDER BY clause.**
16. **Audit's L1 P1.3 (merge relevance+extract on cost).** Ledger: $0.13 vs $1.04. **Adjudication: merge for quality if you like; never sequence it ahead of P0 correctness on a spend rationale.**
17. **Audit describes agent handoff as uniformly fail-closed.** The 501 is real but a second door is open at `deliver/agent_api.py`. **Adjudication: the "keep the 501" conclusion holds; it is guarding the wrong door.**
18. **Audit's L1 loophole catalog is incomplete** — misses the whitelist-ordering defect (108 live instances). **Adjudication: treat the catalog as a floor, not a ceiling.**

## 5.3 What the audit merely CONFIRMS

- `tenant_packs` = sales@1.10.0 + general@1.1.2, both active, both orgs.
- 25 rules total (20 sales dicts + 5 general); exactly 7 ever fire for this org.
- `use_domain_compiler=False` at `platform/config.py:89`; `expertise_packages` = 0 rows, all orgs.
- `reason/adapters/expertise.py:200/203 live_delivery_enabled=False`; `domain_shadow` persists nothing.
- `packs/registry.py:139-142 effective()` drops `schema` and `capture`.
- 23 reasoner unit files; exactly 6 reasoner_ids in `reasoning_reasoner_results`, 251 rows each.
- `decision_maker.py:239-241` `priority_override` short-circuit.
- `executions` / `execution_actions` / `execution_escalations` / `delivery_outbox` = 0 rows, all orgs.
- `learning_runs` = 2 rows total.
- 41 cards for this org; 37 `render_mode='raw_slot'` with empty artifact body; all `urgency_band='standard'`.
- 286 attachments parked with no drain; 0 of 394 documents parsed.
- HEAD = `b739bd5`; zero commits since the audit; every spot-checked `[CODE]` line reference literally true.

---

# 6. THE PROGRAM

Spine = `08-Cross-Layer-Synthesis/09-Root-Cause-Dependency-and-Remediation-Order.md` CP-0..CP-8 and `12-Executive-Decision-and-Phased-Plan.md`. The audit's dependency chain, reproduced faithfully:

> **RC-1** qualified evidence + roles + permission → **RC-2** bounded current BusinessSituation / open loop → **RC-3** reviewed & accepted authoritative expertise or authoritative abstention → **RC-4** semantically consumed brains + gold decision + lossless card → **RC-5** one accountable execution truth → **RC-6** one fenced delivery/result truth → **RC-7** canonical outcome → governed review/policy/lifecycle → future semantic decision.
> **RC-8** (scope/origin/authority envelope) constrains EVERY arrow. **RC-9** (health, golden replay, pilot evidence) gates EVERY promotion.

The audit's own reasons for this order, preserved: building RC-7 before RC-1/RC-2 trains on wrong identity/state; activating RC-3 before deep capability closure replaces generic legacy errors with compiler-backed gaps; moving to v2 Delivery before RC-4/RC-5 sends the wrong action more reliably; a prettier card before RC-2/RC-4 makes ambiguity easier to trust.

**Two annotations to the audit order, each with a named technical dependency:**
- **Phase 0B is inserted** between CP-0 and CP-1. Justified under the audit's own §"Stop unsafe authority expansion". Named dependency: **none** — every item in 0B is contained, has zero upstream dependency, and two of them (L1-02 destructive drops, L1-01 frozen calendar) cause **irreversible loss every day the program runs**. Deferring irreversible loss behind a quarter of contract work is not a sequencing choice, it is data destruction.
- **L3-08 (outbound seam) moves from Phase 2 to Phase 1.** Named dependency: **L1-06 (pack-driven domain hints) and L2-06 (pack-aware extraction) have no vocabulary source without it.** `registry.effective()` must carry `schema` and `capture` before `domain_hints()` or `build_prompt()` can accept a parameter.

---

## PHASE 0 — FREEZE TRUTH (CP-0)
**Layers:** cross-cutting · **Size:** medium

**Units changed:** `tests/test_corpus_can_fire.py` · `tests/test_executive_authority.py` · `tests/test_migrate.py` · `tests/test_executive_sweep.py` · `tests/test_domain_expertise_compiler.py` · `tests/test_expertise_adapter.py` · new `tests/replays/` harness · `genios_engine/LAYERS.py` docstring · `Rohit_Updates/.../README.md:40` · new pinned SQL runtime-receipt manifest · ADR register

**Gaps closed:** X-03, X-04, X-05, X-06, X-07 (ratification schedule authored), X-08, X-09, L3-06, L5-02, L5-08

**Exit gate**
- All 9 baseline failures have exactly one honest state: passing, or quarantined with a named owner, reason and deadline. **No unlabeled skip counts as green; quarantine may isolate diagnosis but must not turn a gate green.**
- All 12 golden replays exist as executable fixtures with pinned source/graph/corpus/config versions and clocks, and replay identically twice.
- `routes._executive_orgs()` has an **execution** test, not an `inspect.getsource` assertion; every other source-text wiring assertion in the suite is converted.
- A contract test asserts `set(catalog.domain(d).routes) <= set(domain_spec situation_types)` for every catalog domain — **it f
ails today**, and it is the oracle for L3-01.
- The per-layer runtime-receipt SQL manifest runs read-only against `org_e97e86f858ad48b2bbf64b8a` and every `[CODE]` verdict in the audit carries a paired `[RUNTIME]` row.
- ADR ratification schedule published (§6.8), with ADR-02 and ADR-07 ratified before Phase 1 starts.

---

## PHASE 0B — STOP THE BLEEDING (annotation to CP-0; no upstream dependency)
**Layers:** L1, L5, L6 · **Size:** small (every item is contained)

**Units changed:** `capture/acquire/sync_runner.py::run_sync` · `capture/connectors/base.py::SourceConnector` · `capture/connectors/calendar.py` · `capture/gate/gate.py::run_gate` · `capture/gate/rules.py` (split into content-integrity vs noise) · `capture/gate/relevance.py` (`_GATE_BATCH_PROMPT`, `_verdict_from`) · `capture/pipeline.py::capture_event` (retention) · `capture/parked/store.py` + the in-process sync sweep · `capture/documents/router.py::route_document` · `platform/wiring.py::make_connector_for` · `api/routes.py:409` and `:337` · `executive/sweep.py::_PLANNABLE_SIGNALS` · `deliver/pipeline.py:35` · `deliver/card_builder.py` + cards migration (`reject_code`) · `deliver/outbox.py::run_distribution`

**Gaps closed:** L1-01, L1-02, L1-03, L1-07, L1-08, L1-12, L1-15, L5-01, L5-04, L5-07, L6-12, L6-17, L6-19

**Ordering inside the phase (hard):** L5-04 must land **in the same commit** as L5-01, or the first live tick creates commitments for the 2 already-resolved signals.

**Safety note — why enabling L5 here is safe:** executions do not create cards; `deliver/executive_bridge` requires `x.assignee is not null` and `org_seats` is empty (L5-03, Phase 4). So L5 comes up as a **shadow ledger that speaks to nobody.** That is deliberate: it produces the runtime evidence L7 needs later, at zero customer exposure.

**Exit gate**
- No persisted sync watermark exceeds `now()` for any connection; gcal `l1_sync_runs` shows non-zero new objects.
- Zero destructive gate decisions are committed without a retained recovery artifact; every `llm_junk` verdict carries a non-empty `reason`.
- A whitelisted sender's attachment is **parked**, not emitted with an empty body; `document_jobs` unsupported/emitted count is 0.
- `parked_events` shows at least one non-`pending` status; `document_jobs` shows at least one `native_parse_used=true` or a distinct `ocr_unavailable` reason code.
- `routes._executive_orgs()` returns both org ids; one heartbeat tick returns `executive = {"orgs": 2, "commitments_created": N>0}` and never `{"error": True}`; `select count(*) from executions` is non-zero on prod; **zero commitments whose source signal is `resolved` or `acted`.**
- `run_calibration` executes from the heartbeat without raising.
- `select count(distinct level) from cards` > 1 and no card carries `level='prescriptive'` whose signal carried `predictive`.
- `cards.reject_code` is populated; the raw_slot rate is attributable to V-01 vs V-02 vs `llm is None` from stored data alone.
- `run_distribution` logs a named exception per failing org instead of `pass`.

---

## PHASE 1 — ESTABLISH SCOPED REALITY (CP-1)
**Layers:** L1 + L2 (+ the L3 outbound seam) · **Size:** large — this is the real Layer 1/2 project

**Units changed**
- L3 seam first: `packs/registry.py::effective` + `persist_effective_snapshot`
- L1: `contracts/source_event.py` · `contracts/gated_event.py` → versioned `QualifiedEnterpriseSignal` · `capture/connectors/base.py::RawObject` · `capture/connectors/{composio,calendar,notion,drive,hubspot}.py` · `capture/landing/normalize.py::to_source_event` · `capture/landing/pg_repository.py` + migration · `capture/intake.py` (both entry points) · `capture/coverage/model.py::compute_coverage` + `PACK_REQUIREMENTS` · `capture/domain/hints.py::domain_hints(source, text, *, vocab)` · `capture/source_registry.py` (immutable/version_field descriptors) · `capture/pipeline.py::_build_gated_event`
- L2: `context/pipeline.py::process_event` (cache key, `ex.domains`, role edges, thread-scoped facts, commitment post-gate, legacy dual-write removal, `source_object_id`) · `context/extract/prompt.py` → `build_prompt(*, signal_vocab, schema_fields, classifier_hints, domain_list)` · `context/extract/extractor.py` · `context/correlation.py::choose_anchors` + `resolve_domain` · `context/domain_spec.py` (fundraising spec; relationship expected fields) · `context/situations.py::coverage_score` · `context/identity.py` (alias disambiguator) · `context/runner.py::_internal_emails` · `context/situation_bso.py` (bounded subject, real receipts, narrowest visibility, truthful `missing_fields`, blocking validator) · new meeting/request lifecycle reducer · new current-state reducer + completion matcher · `context/graph_store.py` (source_object_id) · **`reason/runner.py::run` — the consumer flip**

**Gaps closed:** L3-08, L1-04, L1-05, L1-06, L1-09, L1-10, L1-11, L1-14, L2-01, L2-02, L2-03, L2-04, L2-05, L2-06, L2-07, L2-08, L2-09, L2-10, L2-11, L2-12, L2-13, L2-14, L2-15, L2-16, L2-17

**Ordering inside the phase (hard):**
1. L3-08 before L1-06 and L2-06 — no vocabulary source otherwise.
2. **L2-13 (cache key) before any prompt change** — 260 cached extractions will otherwise mask L2-06/L2-07 entirely.
3. L2-04 before the correlation rebuild — otherwise every anchor re-fuses on `thegenios.com`.
4. L2-01 (consumer flip) last within the phase — it is the switch that makes everything above observable.

**Exit gate**
- Replays **01–05** produce the correct current state: **zero wrong target, zero stale action, zero parallel-ask collapse, zero actor reversal, zero recap for a non-attended internal session.**
- Live SQL assertions against `org_e97e86f858ad48b2bbf64b8a`, all four failing today: zero situations anchored on the owner or `thegenios.com`; zero VCs typed `sales/opportunity`; the `boardy.ai` correlation split from 68 members into per-thread groups; **no person node holding a `thread.ball_in_court` fed by more than one thread.**
- Zero `commitment.text` values ending in `?`; zero commitments unreachable because their owner is the account holder.
- `graph_source_refs.source_object_id` non-null on 100% of new rows; a sampled card resolves back to a permitted Gmail message id.
- Visibility is mandatory on the QES, derived per connector, and narrowest-merged into the BSO — no hardcoded `org` scope survives.
- `coverage_ready` is written on every emitted event; an unregistered domain returns `unknown_domain`, never ready.
- The BSO validator **blocks**: no BSO with unresolved required roles, synthetic membership, or unknown visibility reaches L3; `split_required` is emitted for a multi-ask anchor.
- Model-disabled replay: identical routes, dedupe, visibility, identity merges and lifecycle states with the LLM switched off.

---

## PHASE 2 — ONE ACCEPTED EXPERTISE LANE (CP-2)
**Layers:** L3 · **Size:** large (engineering small, authoring large)

**Ratified in ADR-02, verbatim:** `Sales` / trigger `buying_signal` / situation `sales.sit.inbound_fit_check` (unnarrowed, `priority_bp` 6500) / capability `sales.qualification.lead_qualification`, reached via `also_serves`, with `sales.market_and_targeting.icp_definition` as accepted companion. **Do not "simplify" by routing straight to `sales.sit.inbound_lead`** — that reintroduces the `ball_in_court='us'` gate that only ~9% of founder-inbox persons satisfy. ADR-02 must also record the L3-14 evaluation-set correction.

**Units changed:** `Domain Expertise/*/capabilities/**/situations/*.yaml` (re-key `matches.l2_situation_types`) · `Domain Expertise/_tools/index.py` (regenerate `registry/situation-capability-map.yaml`) · `Domain Expertise/_schema/vocabulary.yaml` (substrate generated FROM `context/domain_spec`) · `Domain Expertise/_tools/validate.py` (L2 census source + admission mirror) · `Domain Expertise/_schema/capability.schema.json` (`admission` block) · `packs/compiler/capability_resolver.py` (domain alias map, admission gate, typed abstention) · `packs/compiler/errors.py` (`UnsupportedCoverage`) · `reason/domain_shadow.py` (typed disposition counters) · `platform/config.py` + `reason/runner.py:528` (scoped promotion table replacing the boolean) · `context/situation_bso.py` (support→customer_support alias) · the corpus content for the lane

**Gaps closed:** L3-01, L3-02, L3-03, L3-04, L3-07, L3-09a (the one lane only), L3-10, L3-11, L3-12, L3-13, L3-14

**Exit gate**
- **Routability:** a shadow run on the design-partner org reports `compiled > 0`, not `no_route: 73`. The Phase-0 contract test passes.
- **Typed disposition:** every live situation resolves to exactly one of `accepted route | all_stub | unreviewed | unsupported_domain | no_route`. **Zero fall into `counts["error"]`. Zero nearest-route substitution** — an unsupported situation must never silently become generic Sales.
- **Admission:** no prescriptive package references a capability unless `identity.status: stable` AND `metadata.review_status: approved` AND `metadata.reviewed_by` names a human AND the computed `content_hash` equals the recorded `accepted_content_hash`. A post-acceptance byte change revokes admission. Enforced in BOTH the resolver and `validate.py`.
- **Dependency closure:** for the promoted route, every required capability, object, rule, playbook and failure pattern is authored, reachable, non-stub and admitted. **Zero all-stub routes inside the promoted scope. Zero blocking-class warnings for that closure.** The ICP companion's 11 blocked patterns are either unblocked by L1 enrichment or pruned — not accepted silently.
- **All 6 globally-unrouted L2 types carry an explicit abstention binding** (`objection_open` and `timeline_slip` are firing live).
- **Replay:** identical BSO + identical brain snapshot yields a byte-identical canonical ExpertisePackage; package id, brain_snapshot_id and admission receipt appear in the L4 decision and on the card.
- **Scoped authority:** promotion is keyed on `(org_id, domain, situation_type, capability, accepted_version)` with a kill switch — never the global boolean. **Legacy may observe a new-path abstention but can never override it into a prescriptive card.**
- **Replay 07 passes:** unsupported fundraising/investor/Admin situations return typed abstention with the exact missing capability named.
- **Measured and recorded:** actual person-days per capability and actual blocked-pattern rate, as the input to Phase 8's sizing.

---

## PHASE 3 — GOLD DECISION + FOUR-BRAIN SEMANTIC CONSUMPTION (CP-3)
**Layers:** L4 (+ L3 adapter, + the card surface of the decision contract) · **Size:** large

**Units changed:** `contracts/` (level enum; `IntelligenceCard v3`) · `packs/{sales_v1,general_v1}.py` (per-play `impact_bp`/`effort_bp`/`risk_bp`/`success_probability_bp`; abstention levels) · `reason/rules.py::_rule_from_dict:25` · `reason/adapters/legacy_pack.py::legacy_capability_manifest` (candidate SET incl. mandatory `wait_observe`; `confidence_floor_bp` from `gate.c_min`; per-reason-code reasoner schedules; stop routing `core.priority` to `legacy.rule`) · `reason/reasoners/priority.py::_override` · `reason/decision_maker.py::score_candidate` · `reason/orchestrator.py` (refuse a live manifest with no declared floor; downgrade to `observation` when review_state != accepted) · `reason/adapters/expertise.py` (typed org/behavior/adaptive consumers with authority split + effect receipts; `_plays` ordering policy, `skipped_rule_ids`, `truncation_reason`, non-prescriptive fallback) · `reason/audit.py::audit_bundle` (persist brain receipts) · `reason/publication.py` + `reason/composer.py` + `signals` migration (decision columns) · `api/routes.py::_decision_projection` (delete the reason_code synthesis) · `api/routes.py::_actionability` (invert the default; source decisive fields from `Rule.evidence_fields`) · `api/routes.py::_confidence_block` · `api/intelligence_routes.py::list_insights` · `deliver/card_builder.py::build_draft` + cards migration · `deliver/store.py:118` · `deliver/pipeline.py` (`queue()` gating)

**Gaps closed:** L4-01, L4-02, L4-03, L4-04, L4-05, L4-06, L4-07, L4-08, L4-09, L4-10, L4-11, L3-05, X-02, L6-16, L6-18

**Ordering inside the phase (hard):**
1. **L4-01 before L4-10** — populating score components while `priority_override` short-circuits the formula changes nothing.
2. **L4-03 before L4-06** — `core.alternative` and `core.tradeoff` have nothing to compare with one candidate. **Do not mass-activate the 17 units**; enable `temporal` and `relationship` first (they feed `why_now` and `relationship_role`), then `alternative` and `tradeoff`, each behind its own replay.
3. **X-02 before L6-16** — the gate needs a non-prescriptive level to downgrade to.
4. **L3-05/L4-04 typed consumers are inert until Phase 6 populates `learned_brain_entries`** — build them here (L3 activation requires them) and prove them with fixture-seeded brain rows; the live proof moves to Phase 6's exit gate.

**Exit gate**
- **Ranking authenticity:** `reasoning_candidates.initial_utility_bp ≠ legacy_score × 100` for any live row, and utility is demonstrably monotone in the declared `ranking_weights`. Fails on 251/251 today.
- **Abstention reachability:** at least one live manifest declares `confidence_floor_bp`; a below-floor fixture produces `outcome_kind != 'decision'` with `selected_candidate_id IS NULL`, projected end-to-end to a card with **no action button**. 251/251 are `decision` today.
- **Candidate plurality:** median candidates-per-run > 1 in the promoted scope, with at least one `disposition='eliminated'` row carrying its check reason. Avg is exactly 1.00 today.
- **Manifest execution receipt:** `reasoning_runs.reasoner_plan` surfaced on the card as scheduled / executed / skipped — so "17 units exist" can never again read as "17 units ran".
- **Projection losslessness:** `_decision_projection` contains **zero** `reason_code`-keyed recommendation synthesis; `do_nothing_consequence`, `uncertainty`, `outcome_window_days`, candidate checks and play steps round-trip to the card. `stakes`/`completion` are never the string `"missing"`.
- **Gold-contract completeness = 100% in the promoted scope** (up from 5/16). Fabricated-stage / fabricated-urgency rate = 0. Critical false-action rate = 0.
- **Score semantics:** `confidence_score` is not sourced from `signals.score`; `priority_score` is a separate key; no dimension of the confidence vector is a hardcoded ternary or an alias.
- **Four-brain mutation replay:** mutate one entry in one brain with everything else pinned — a Company-approval mutation blocks or requires approval on a previously-winning candidate; a Behavior mutation **only reorders**; an Adaptive mutation only moves bounded timing/priority and carries an expiry; an inapplicable mutation preserves the decision and emits `semantic_no_effect`. **A changed `knowledge_hash` with no intended delta and no no-effect receipt is a FAILURE.**
- **Customer surface:** the queue endpoint is gated identically to the detail endpoint; a gate failure rewrites the stored headline, lowers `level`, and removes `run_play`/`do_it_myself` — it never adds a sibling field next to an imperative.
- Replay 06 passes: terminal opportunity state is a **hard action gate**, not a negative score feature; "Save the deal now" cannot be emitted against a party who rejected us.

---

## PHASE 4 — ONE ACCOUNTABLE EXECUTION TRUTH (CP-4)
**Layers:** L5 (+ the card action surface) · **Size:** large

**Units changed:** `executive/assignment.py::resolve_owner` (fourth rule for single-seat/founder orgs) · the onboarding path that creates an org (seed `org_seats`) · `deliver/actions.py::ingest_action` (idempotent claim against the linked execution inside the existing transaction, keyed by command id) · `executive/execution_store.py` (`complete_action`, `link_card` callers) · `contracts/execution.py` (`AWAITING_APPROVAL`, `FAILED` in `ExecutionState` and `ALLOWED_TRANSITIONS:81`) + migration · `executive/escalation.py` (explicit degraded-ladder vs named `blocked`)

**Gaps closed:** L5-03, L5-05, L5-06a

**Exit gate**
- `org_seats` non-empty for every active org; **no commitment carries `routing_rule='rule3_unrouted'` silently**; `execution_escalations` receives rows; `run_lifecycle` no longer returns `quiet_not_remindable` for 100% of the queue.
- **One truth per commitment:** every actionable card carries an execution/action link or is explicitly observation-only. Card/execution divergence is **zero** under duplicate-click, retry, crash and concurrent-actor replays. A click creates or claims **exactly one** execution, or returns `accepted_unclaimed`.
- Claim / approve / execute / complete / outcome remain **distinct receipts**. No UI click alone closes a loop; completion stays evidence-gated. Present "claimed", never "done".
- `ExecutionState` can express awaiting-approval and failure; the transition table rejects illegal moves.
- **Fail-closed holds:** unknown semantic target, missing approval and uncertain completion each produce a named non-authoritative state with evidence and no interrupting delivery. Boardy multi-intro produces separate target-scoped work or abstention — never connector-as-target.
- **Agent handoff still returns HTTP 501** (`api/intelligence_routes.py:908`). Replay 08 passes by staying disabled.
- Model-disabled replay: identical ExecutionObject, owner, route, lifecycle and outcome with drafting off.

---

## PHASE 5 — ONE CANONICAL DELIVERY TRUTH (CP-5)
**Layers:** L6 · **Size:** large

**Ratified in ADR-01:** L5 owns semantic audience/channel **intent and constraints**; L6 owns the currently lawful adapter/route/fallback **within that envelope** and may only **narrow or defer**.

**Units changed:** `deliver/outbox.py::run_distribution` (org enumeration, per-org logging, `delivery_id`/`dedupe_key` stamping, drain discriminator, one canonical transition function) · `deliver/outbox.py::enqueue_pending` (band-starvation observability) · `deliver/spine.py::claim_due` (shape predicate, priority ORDER BY / `scheduler.schedule_order`) · `deliver/gate.py::PgDeliveryContext._read_settings` (org timezone fallback) · `deliver/render.py::render_copy` (V-01/V-02 split, artifact on demand, evidence-hash cache, `purpose` rename) · `deliver/routing.py::build_route_ladder` (conditional `PULL_SURFACE`) · `deliver/units.py` (per-channel credential map) · `api/delivery_routes.py::capabilities` (decrypt-and-shape probe) + results/inbox/dead-letters predicates · `deliver/analytics.py` · `deliver/push.py` → routed through `outbox` as an `agent_push` row; remove the inline call at `deliver/pipeline.py:128-132` · `deliver/card_builder.py::build_draft` (semantic-target required-fields check) · the v2 weld: `orchestrator.resolve` / `spine.materialize` replacing the three `enqueue_*` calls · `feedback/delivery_facts.py` consumer alignment

**Gaps closed:** L6-01, L6-02, L6-03, L6-04, L6-05, L6-06, L6-07, L6-08, L6-09, L6-10, L6-11, L6-13, L6-14, L6-15

**Ordering inside the phase (hard):**
1. **L6-06 (worker disjointness) before the first row is ever enqueued.** It is free today because the table is empty and becomes a data-migration project the moment L6-01 lands.
2. L6-08 (timezone) before the first delivery, or the first message Rohit ever receives is deferred all IST morning and permitted at midnight.
3. L6-15 (semantic-target contract) requires Phase 3's target work, or it suppresses everything.
4. L6-14 (v2 cutover) last — wiring a fenced worker to a queue that structurally cannot receive rows proves nothing.

**Exit gate**
- `select count(*) from delivery_outbox > 0` for the design-partner org, produced by the **real heartbeat**, not a test.
- `deliver/outbox.drain` and `spine.claim_due` have mechanically exclusive predicates, verified by a dual-worker concurrency test showing **zero dual claims**.
- **One vocabulary, one ledger:** every adapter call updates `status`, `lifecycle`, `delivered_at` and appends a `delivery_events` row in one transition; `failed_terminal` and `failed` collapse to one enum; an injected exhausted row appears in `/results`, `/dead-letters` and analytics simultaneously.
- Executed / delivered / opened / completed / outcome states reconcile and **never collapse**. Ten destinations = one logical delivery. Send-time authority revalidation executes and is observable.
- Provider-timeout reconciliation runs **before** any retry. **Forbidden: legacy + v2 dual sending.**
- Every live row carries `delivery_id` and `dedupe_key`; `feedback/delivery_facts.load_delivery_facts` returns non-empty.
- Quiet window computed in the tenant's real local hours; no unrouted delivery is silently queued to `in_app`.
- `/capabilities` reports operational only when a decrypt-and-shape probe passes per channel.
- **LLM yield above 50%:** the raw_slot share falls from 91%; `l6_render` calls per *used* artifact falls; no card advertises "Draft reply" over an empty body.
- Zero cards ship with an action button when the system cannot name what remains unresolved.

---

## PHASE 6 — CLOSE THE LEARNING RECEIPT (CP-6)
**Layers:** L7 (+ the L3 consumption receipt) · **Size:** large

**Ratified first:** ADR-03 (Organization Brain source of truth), ADR-08 (review-to-publish state machine), ADR-09 (policy fidelity), ADR-10 (Adaptive TTL — XOR decision).

**Units changed:** `api/learning_routes.py::review` (reload → re-preflight → `publish_brain` → `published`; `approved_unpublished` on failure; drain `knowledge_suggestions`) · `feedback/publisher.py` · `feedback/orchestrator.py::load_or_seed_policy` (both block lists in SELECT **and** seed; `policy_incomplete` abort) + `run_learning` (sink-derived counters, `queued_for_review` bucket, per-seam counts, `degraded` flag) · `feedback/store.py` (`_OPTIONAL_FEEDBACK_TABLE` → `card_feedback_verdicts` with explicit projection; write `learning_input_rejections`; resolve or remove `batch.inbox`) · `feedback/units.py::unit_feedback_learning` (implement with scope ceiling) and `_cohort_candidate` (emit) and `:211` `distinct_days` (**only after ADR-10**) · `contracts/learning.py:224` + `feedback/consumer.py:81-84` + `packs/compiler/runtime_brains.py` + `learned_brain_entries` migration (per ADR-10) · `feedback/reset.py` (`runtime_memories_expired` rename + docstrings) and `api/routes.py:1350-1370` · `feedback/calibrate.py` (bring under the governance contract or declare a separate reviewed authority) · **`reason/runner.py::run` → `feedback/consumer.py::snapshot(consumer='reasoning')`** merged into `registry.effective()`, or delete `consumer.py` per ADR-03 · dashboard/extension clients calling `submit_feedback`

**Gaps closed:** L7-01, L7-02, L7-03, L7-04, L7-05, L7-06, L7-07, L7-08, L7-09, L7-11

**Ordering inside the phase (hard):**
1. **L7-11 first** — it is what makes every other gap in this phase visible without a psql session.
2. **L7-08 / ADR-10 before touching `units.py:211`** — raising `distinct_days` is what arms the immortal-preference hazard.
3. **L7-04 (get a human to press a button) before or alongside L7-03** — wiring the seam to an empty ledger changes nothing.
4. L7-06 (consumption) is the phase's closing move: publishing without a consumer produces audited values that change nothing.

**Exit gate**
- **Reachability:** one path runs unit → governance → publish → active `learned_brain_entries` row → L3 compilation → a **different** future decision. Today no path exists.
- Approving an ORGANIZATION proposal creates exactly ONE active brain version; reject creates none; duplicate approval is a no-op; a crash or policy race persists `approved_unpublished`, never `promoted`. The `knowledge_suggestions` queue drains.
- **Policy fidelity:** seed, reload, restart and update a policy carrying both block lists; byte-equivalent values reach `preflight` and reject the same proposal on every path. A missing/malformed field yields `policy_incomplete` and aborts the tenant run.
- **Adaptive XOR (ADR-10):** either mandatory expiry is representable end to end (proposal → publish → selection → expiry → supersession → rollback → compiler consumption, with expired Adaptive contributing zero) **or** Adaptive publication is prohibited in `governance.govern` and temporary guidance uses Runtime leases. A non-expiring Adaptive row **fails** acceptance.
- **Reset truthfulness:** a pivot fixture with one active row seeded in every brain proves `apply_organization_reset` changes ONLY `temporary_memories.active`, leaves all `learned_brain_entries` byte-identical, and reports `runtime_memories_expired`.
- **Consumption:** every active learned version carries evidence, target, policy, scope, expiry-where-applicable, predecessor, rollback, a **compiler receipt**, and a **typed intended decision-field delta** or an explicit deterministic no-effect reason. A changed package hash alone FAILS.
- **No silent drop:** every zero-proposal outcome carries a machine-readable reason code written to `learning_input_rejections`; a sweep whose required seams are chronically empty reports `degraded`, not healthy. `learning_runs.counts.published` never counts a review-queued object.
- `card_feedback_verdicts` and `human.card_action` are non-empty; `calibrate.py` is either governed or explicitly declared with its own review gate; `rule_mutes` cannot deactivate a live rule without a recorded human authority.
- Prohibited targets remain prohibited after reload; rollback restores only a currently-valid predecessor.

---

## PHASE 7 — COUNTERFACTUAL PILOT (CP-7)
**Layers:** L7 + analytics · **Size:** large

**Ratified first:** ADR-06 (outcome/value attribution).

**Units changed:** new canonical ledger joining recommendation → exposure → action → delivery → external result → counterfactual · `api/intelligence_routes.py::insight_stats` (fix the `kind`-vs-`cause` predicate; replace the three constants with ledger reads plus an explicit `data_unavailable`) · `api/routes.py:1710-1723` (return `data_unavailable`, not empty shapes) · `llm_costs` migration (`execution_id`, `client_context_id`) · pilot cohort tooling (enabled vs holdout)

**Gaps closed:** L7-10, L7-12, X-10

**Ten-field counterfactual contract, recorded at or before decision time:** situation/opportunity id · GeniOS recommendation + version · **otherwise-action** · acceptance state · actual action · delivery/exposure · declared outcome + window · alternative causes · attribution class · value/cost. Only `caused` and an explicitly weighted portion of `assisted` may enter attributable value; `associated` and `unknown` stay visible and never inflate ROI.

**Exit gate**
- Enabled vs holdout/baseline **inside the accepted lane**, with the otherwise-action **pre-registered before exposure**.
- API totals equal the canonical ledger by class and window; unknown attribution is an explicit state, not zero.
- `net_attention_value = attributable_or_conservatively_assisted_value − correction time − reminder/escalation time − false-action recovery − model/provider/agent cost`.
- **Cost per useful ACCEPTED decision** is computable (denominator non-zero) and per-execution/per-client attributed.
- Decision-quality lift is credible; **no proxy inflation**; the negative denominator is complete.
- **The evaluation-set correction from L3-14 is honoured:** the lane is exercised through `demo_requested`/`intro_followup` and, for ordinary B2B sales volume, a second design partner. A pilot on an empty trigger proves nothing.
- No "Outcome-proven" claim until counterfactual evidence exists.

---

## PHASE 8 — DELIBERATE EXPANSION (CP-8)
**Layers:** L3 corpus, L5 agent protocol, L1 deletion, cross-cutting isolation · **Size:** new_subsystem × 4

Each item below is here for a **named technical dependency**, not for scope or risk.

| Work | Gap | Named dependency that forces this placement |
|---|---|---|
| **Full corpus authoring** — Sales remainder (44) → Support (49) → Admin (57), each a SEPARATE acceptance programme | L3-09b | Per-capability effort and blocked-pattern rate are **unmeasured** until Phase 2 accepts one lane end to end; and authoring against a route index that resolved 0/73 before Phase 2 is measured waste. Phase 2's exit gate records the real numbers that size this. |
| **Governed agent handoff** — approval token, one fenced revocable single-executor lease, scoped payload, idempotency key, cancellation, signed result receipt, `actor_type`/`origin_execution_id` loop guard; close the open `deliver/agent_api.py` door behind the same protocol | L5-06b | Requires `ExecutionState.AWAITING_APPROVAL`/`FAILED` (L5-06a, Phase 4) and one execution truth (L5-05, Phase 4). A delegation protocol on a state machine that cannot express approval is unimplementable. **Keep the 501 until its security, idempotency and duplicate-delivery suites are green.** |
| **Client isolation / provenance envelope completion** — `(org_id, client_context_id, identity_or_relationship_key)` propagated with role, visibility/use, origin, versions and invalidations through every boundary | X-01 | The envelope's L1/L2 half lands in Phase 1 (visibility, roles, narrowest merge). The `client_context_id` dimension requires a **second tenant class to exist** — it has no consumer and no test surface in a single-tenant founder org, and `client_context_id` appears 0 times in the tree today. Replays 09 and 12 are `[MODELLED]` and must not be reported as live leaks. |
| **Deletion / revocation subsystem** — tombstone event type, connector-side deletion detection, revocation projection marking dependent graph facts superseded | L1-13 | Requires the QES boundary (L1-14, Phase 1) to have something to tombstone against, and the completion/current-state reducer (L2-16, Phase 1) to propagate supersession. Nothing in the current append-only package extends into this. |

**Exit gate (per domain, independently):** coverage, false-action, safety and customer-value gates all met. **NO global switch** — this phase exists precisely so that one successful Sales lane cannot launder unrelated coverage.

---

## 6.8 ADR ratification schedule

| ADR | Decision | Ratify before |
|---|---|---|
| ADR-07 | LLM budget authority — per-component eligible denominator, token/retry/cache budget, model-disabled authority replay | **Phase 1** (pack-aware extraction is an LLM change) |
| ADR-02 | First authoritative expertise lane — pinned named-reviewer-accepted hashes, complete closure, everything else authoritative-abstain, **plus the L3-14 evaluation-set correction** | **Phase 2** |
| ADR-04 | Confidence surface — explicit evidence/identity/freshness/expertise/decision **vector**, hard gate dominates | **Phase 3** |
| ADR-03 | Organization Brain source of truth — versioned declared company config PLUS governed learned proposals that cannot silently rewrite policy | **Phase 3** (typed consumer design) and **Phase 6** (publication) |
| ADR-05 | Canonical lifecycle IDs — one `open_loop_id` with immutable typed child ids and reconciliation aliases | **Phase 4** |
| ADR-01 | Channel/recipient ownership — L5 semantic intent, L6 lawful adapter within the envelope, may only narrow or defer | **Phase 5** |
| ADR-08 | Organization review-to-publish state machine — separate reviewed/accepted from published/active; one atomic idempotent publication; active-version pointer; later compiler-consumption receipt | **Phase 6** |
| ADR-09 | Learning-policy fidelity — serialize and hash the COMPLETE policy including both block lists; stored == loaded; re-evaluate at publish/consume/rollback | **Phase 6** |
| ADR-10 | Adaptive TTL/decay target — XOR: mandatory expiry end to end, or Adaptive publication prohibited and Runtime leases used instead | **Phase 6**, and **before any edit to `feedback/units.py:211`** |
| ADR-06 | Outcome/value attribution — caused/assisted/associated/unknown, otherwise-action and window captured BEFORE result | **Phase 7** |

## 6.9 COVERAGE CHECK

| Layer | Gaps catalogued | Gaps assigned to a phase | Unassigned |
|---|---|---|---|
| L1 | 15 | 15 | **0** |
| L2 | 17 | 17 | **0** |
| L3 | 14 | 14 | **0** |
| L4 | 11 | 11 | **0** |
| L5 | 8 | 8 | **0** |
| L6 | 19 | 19 | **0** |
| L7 | 12 | 12 | **0** |
| X | 10 | 10 | **0** |
| **TOTAL** | **106** | **106** | **0** |

**Assignment rows = 108** because two IDs are deliberately split across phases, each with its dependency named: **L3-09** (a = one lane, Phase 2; b = full corpus, Phase 8) and **L5-06** (a = ExecutionState members, Phase 4; b = executor-lease protocol, Phase 8).

**Per-phase counts:** P0 = 10 · P0B = 13 · P1 = 25 · P2 = 11 · P3 = 15 · P4 = 3 · P5 = 14 · P6 = 10 · P7 = 3 · P8 = 4. Sum = 108 rows / 106 unique IDs.

**Source-pack reconciliation:** the eleven audit packs catalogued **148** gap entries (00-Methodology 13 · L1 13 · L2 13 · L3 14 · L4 10 · L5 8 · L6 16 · L7 11 · 08-docs-01-06 16 · 08-docs-07-12 22 · 09-Golden-Replays 12). **All 148 map into the 106 canonical IDs**; 42 were cross-pack restatements of the same defect (e.g. the L3 pack's items 11/12/13 are L7-02/L7-07/L7-08; the L6 pack's "card accepted path never touches L5" is L5-05; RC-3/B-03 is L3-03 + L3-09). **19 canonical IDs are net-new synthesis objects** no single pack listed as a gap: L1-14, L1-15, L2-14, L2-15, L2-16, L2-17, L3-12, L3-13, L3-14, L4-11, L6-16, L6-17, L6-18, L6-19, X-01, X-02, X-07, X-09, X-10.

**Nothing is unassigned. Nothing was dropped, deferred on judgment, or marked out of scope.** Every late placement carries a named technical dependency in §Phase 8 or in the per-phase ordering notes.

## 6.10 Release-state ladder (`12-Executive-Decision`)

Architecture/demo → **Shadow evaluation** (critical false-action classes = 0; coverage and abstention measured) → **Assisted, one accepted lane** (100% gold fields; exact target/owner; execution and suppression replays green) → **Governed execution** (one intent/result chain; approval/policy/idempotency/cancellation green; zero loop) → **Conditional learning** (atomic review→publish→consume; policy field equality; ratified lifecycle/TTL; safe rollback; proven intended next-decision semantic influence) → **Outcome-proven** (counterfactual pilot shows credible lift and positive net value with full attribution).

**Sixteen hard release gates, every threshold ZERO, all conjunctive — a single breach is a release failure regardless of average quality:** wrong business subject/recipient · restricted or cross-client use escape · unsupported expertise prescription · stale/completed/superseded resurfacing · duplicate logical execution/send/outcome · missing mandatory gold field · model-added authority · unreconciled efficacy update · Organization approved without publication · stored-vs-loaded policy mismatch · non-expiring Adaptive authority · unsafe rollback · hash-only brain influence · unexplained input loss · declared golden-replay skips · unsupported-prescription rate.

**Two invariants that override all phase work.** (1) No grounded current state OR no resolved business subject OR no accepted expertise OR no authority OR no observable completion ⇒ **do not promote an action recommendation.** Measured against live data, three of those five fail simultaneously right now, and the system promotes anyway, 41 times out of 41. (2) The ladder Present → Wired → Live → Tested → Outcome-proven and the chain observed → recommended → approved → delegated → sent → acknowledged → completed → outcome_observed **may never be collapsed**, and no later state may be inferred from an earlier one.

---

# 7. WHAT NOT TO DO

Harmful actions only. Every item carries its reasoning and its source.

1. **Do not flip `use_domain_compiler` globally because the files exist.** `12 §Do not do`: presence, schema validity and compilation are not authored expertise. Today it would compile **0 packages** (L3-01, 73/73 no-route) and, once routable, admit **152 unreviewed AI drafts** (L3-03). Promotion is per `(org, domain, situation_type, capability, accepted_version)` — never a boolean.
2. **Do not describe the compiler as absent or rolled back for performance.** `12`: commits `9c7ce4c` and `7da562e` show shadow-first from inception. Shadow was never a rollback.
3. **Do not author all 152 capabilities in parallel.** `12 §Do not do`: volume creates review debt and zero vertical customer proof. One accepted deep lane teaches the real schema, the real per-capability cost, and the real blocked-pattern rate. The draft-to-accepted ratio is already **152:0**.
4. **Do not add LLM to ranking, permissions, action state, completion, attribution or learning promotion.** `12` + `08/06-LLM`: fluency cannot repair a wrong role, visibility, current state, permission or causal outcome — and it **hides missingness**. The reason L4 is shallow is one candidate per run and four constant score components; no model spend fixes that.
5. **Do not ask a stronger model to "use all context".** `12`. And never prompt across the full 152-file corpus at runtime (`08/06-LLM §Expertise matching`) — deterministic shortlist first.
6. **Do not tune urgency/confidence thresholds from screenshots.** `12`: score is already conflated with confidence (L4-07), and thresholds cannot invent expertise.
7. **Do not build a new dashboard, confidence badge or richer card text first.** `12`: presentation makes a wrong decision look **more** authoritative.
8. **Do not connect more agents before origin/lease/result contracts exist.** `12`: wrong intelligence executes faster, loops recursively and double-learns. **Keep the 501 at `api/intelligence_routes.py:908`** and close the open second door at `deliver/agent_api.py` behind the same protocol before anything uses it.
9. **Do not claim a brain shaped a recommendation because its hash appears in lineage.** `08/03`: a changed `knowledge_hash`, package id or manifest version with identical judgment is **provenance theatre** and scores ZERO on the acceptance test.
10. **Do not learn from a single click, send, silence, edit or generated message.** `12`. Silence is not evidence; elapsed time is not evidence.
11. **Do not count click, delivery, display, open, meeting, closed deal or nearby revenue as GeniOS value.** `11 §Scorecard` names cards generated, confidence displayed, emails indexed and YAML files loaded as **vanity metrics**. A higher card count is explicitly not a positive metric.
12. **Do not mass-activate the remaining reasoner units.** `04-Layer-4/01:81`: enable `temporal` and `relationship` first, then `alternative` and `tradeoff`, each behind its own golden replay — and none of them can do anything until candidate plurality exists (L4-03).
13. **Do not re-add the `graph_version` predicate to `reason/authority.py`.** Its removal comment records that it emptied the founder's queue every 6 hours. The 4 red tests are stale assertions. Fix the tests.
14. **Do not fix the corpus test by weakening `KNOWN_UNFIREABLE`.** `CTO-README §4`: remove an entry only if `reason/composer.py` confirms the rule genuinely reaches the gate for a real org; otherwise fix the scoring path.
15. **Do not enable dual sending (legacy + v2).** `06-Layer-6 §Phase 5 forbidden`. And add the drain discriminator **before** the first row is ever enqueued — it is free while the table is empty and a data-migration project afterwards.
16. **Do not publish Adaptive until the lifecycle is representable.** ADR-10. Specifically: **do not "fix" `feedback/units.py:211` `distinct_days=1` first** — that is the single edit that arms the immortal-preference hazard.
17. **Do not let a quarantined test turn a release gate green.** `CTO-README §8 Phase 0`: quarantine may isolate diagnosis; a skip is not a pass; no unlabeled skip counts as green.
18. **Do not report the low LLM bill as efficiency.** 37 of 41 cards are empty drafts; cost is near zero **and so is value**. And do not quote a cost-per-value number at all — the denominator (`executions`) is zero, so it is **undefined**, not small.
19. **Do not merge the L1 and L2 model calls on a cost rationale.** Ledger: relevance_gate $0.13 vs extract $1.04. Merge for semantic consistency if you choose, never ahead of P0 correctness.
20. **Do not build the counterfactual ledger before completion truth exists.** Replay 11 is blocked by replay 04 (completion) and replay 08 (execution). A ledger over a system that cannot tell drafted from sent from completed learns noise.
21. **Do not treat the audit's loophole catalogs as complete.** They missed the L1 whitelist-ordering defect (108 live instances), `deliver/push.py`, `feedback/calibrate.py`, the `canonical_judgments` CTE, and the L3 route-key mismatch. Treat every catalog as a floor.
22. **Do not read `[MODELLED]` items as bug reports.** 89 of 148 audit entries are `[MODELLED]` — release contracts and adversarial probes. Reading a golden replay as a defect report is the single most likely misuse of this package. Replays 09 and 12 in particular describe risks that **do not apply to a single-tenant founder org** and must never be reported as live leaks.

---

# 8. THE RED BASELINE

**Measured at `harsh/mvp@b739bd5`: 9 failed, 1,416 passed, 15 skipped, 1 warning (1,440 collected).** The audit's "9 failed / 1,314 passed / 39 skipped" does not reproduce — failure count and all three clusters match exactly, pass/skip totals do not (its run used a narrower collection or a DB-less environment; 192+11 skips in the delivery suite were live-Postgres gates). **Cite the failure count; drop 1314/39.**

## The 9 failing tests, named

**Cluster 1 — corpus health ledger is stale (1 test)**
```
tests/test_corpus_can_fire.py::test_known_unfireable_list_only_shrinks
```
Six rules now reach the score gate but remain in `KNOWN_UNFIREABLE`: `sales/objection_open` (peak S=53), `sales/security_review_pending` (52), `sales/legal_in_review` (49), `sales/timeline_slip` (43), `general/champion_quiet` (45), `general/meeting_no_followup` (44). Any statement about which rules fire is currently derived from a stale list. **Fix:** `tests/test_corpus_can_fire.py:36` — remove the six entries **only if** `reason/composer.py` confirms they genuinely reach the gate for a real org; otherwise fix the scoring path. Never weaken the assertion.

**Cluster 2 — stale authority assertions (4 tests)**
```
tests/test_executive_authority.py::test_brief_loader_uses_audited_projection_and_bound_config
tests/test_executive_authority.py::test_memory_open_decisions_are_authority_filtered_at_one_time
tests/test_executive_authority.py::test_summary_counts_and_top_share_one_authoritative_row_set
tests/test_executive_authority.py::test_preventive_is_not_suppressed_by_an_unauthoritative_open_projection
```
All four fail on `tests/test_executive_authority.py:73`, asserting `authority_ctx.graph_version = (select coalesce(max(gv.graph_version),0)…` appears in the SQL. That predicate was **deliberately removed as a bug fix** — `reason/authority.py` records that it made every card vanish the instant anything wrote to the graph, so each 6-hourly sync emptied the queue. **These are stale assertions, not a live authority hole** (26 signals pass the full predicate today). **Fix:** delete the graph_version assertion from all four; replace with the open-status + pack-authority + expiry terms the predicate actually enforces. **Do not touch `reason/authority.py`.**

**Cluster 3 — migration-test portability (4 tests)**
```
tests/test_migrate.py::test_applies_once_then_skips
tests/test_migrate.py::test_new_file_applies_incrementally
tests/test_migrate.py::test_checksum_drift_fails_loudly
tests/test_migrate.py::test_failed_file_records_nothing
```
`TypeError: Connection() takes at most 8 arguments` — PostgreSQL connection arguments entering SQLite migration tests. Pure test-harness portability; no production implication. **Fix:** parameterise the connection construction by backend.

## Does it block starting?

**Yes — for the program's exit gates. No — for Phase 0B.**

- **Blocks:** `CTO-README §8 Phase 0` is a hard stop that gates every subsequent phase: *"every one of the 9 baseline failures has exactly one honest state — passing, or quarantined with a named owner, reason and deadline."* **Nothing else may be declared verified while the baseline has unlabeled failures.** No phase exit gate in §6 can be certified against a red suite.
- **Does not block:** Phase 0B's 13 items are contained repairs to ongoing, irreversible data loss and provably-wrong output. Two of the three clusters (executive-authority, migrate) are test-only defects with zero production implication, and the third is a stale ledger. Holding back a one-line `from sqlalchemy import text` — which has kept an entire working layer dead for 15 days — behind a SQLite connection-argument fix would be a sequencing error, not discipline.

## Placement in the program

| Cluster | Phase | Gap id | Note |
|---|---|---|---|
| `test_corpus_can_fire` (1) | **Phase 0** | X-03 | Verify against `reason/composer.py` before editing the list |
| `test_executive_authority` (4) | **Phase 0** | L5-08 | Fix the tests, not `reason/authority.py` — the audit's P0 points the wrong way here |
| `test_migrate` (4) | **Phase 0** | X-03 | Harness portability only |
| `test_executive_sweep` source-text guard | **Phase 0** | L5-02 | Passing today, and that is the problem — convert to an execution test |
| Compiler fixtures using `buying_signal` | **Phase 0** | L3-06 | Land **before** the Phase 2 re-keying so the re-keying has an oracle |

**Phase 0 exit condition on the baseline:** `pytest -q` is green, or every remaining failure carries a named owner, a written reason and a dated deadline in the quarantine register. **A skip is not a pass, and a quarantine must never turn a release gate green.**