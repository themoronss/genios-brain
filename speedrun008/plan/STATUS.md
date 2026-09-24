# Build status — all layers

> The live record. Updated at the END of every step, never in advance.
> Format per layer: **START** (the measured state before any work) → one row per step →
> **COMPLETE** (the measured state after, written only when every step's proof has passed).

---

## LAYER 1 — START

**Opened:** 2026-09-23 · branch `speedrun008` @ f905b65e
**Measurement base:** `docs/plans/L1_L4_PILOT_FUNNEL.md` — 849 real objects on
`org_e97e86f858ad48b2bbf64b8a`, Gmail + Calendar, 12 Aug – 8 Sep 2026.

### What Layer 1 is, at the moment work began

| | |
|---|---|
| Code | 138 files · 42,311 LOC · 18 subpackages |
| Tests | 137 files · 2,286 test functions *(collected, not run)* |
| Module wiring | 119 modules · **0 genuinely dead** (AST audit, 2026-09-23) |
| Waves / gates | 11 of 11 built · G0–G9 met · **G10 open** (needs a real tenant + 7 days) |

### The six numbers, at START

> **Metric 1 was re-measured on 2026-09-23 and its START replaced.** The pilot corpus no longer
> exists — see `layer-1/findings/step-01-ocr.md`.
>
> **Metric 3 was WRONG and has been replaced, 2026-09-23.** It said typing the untyped lanes would
> lift `relationship_change` over the floor. Measured: `published 4 · DROPPED 54 · band 880–1560`
> — the ceiling sits BELOW the floor, and `monetary_exposure_bp` / `deadline_proximity_bp` are 0
> **by policy** (`DATE_POLICY=none`, `AMOUNT_POLICY=claims_only`), because a role change genuinely
> states no amount and no deadline. ALG-17 reads both, both are `None`, so typing moves the score
> by **zero basis points**. A ceiling below a floor is a **floor** question → **step 8**. Step 4's
> real metric is 3ʹ: how many claim lanes have somewhere to put a receipt.

| # | Metric | START | Target | Step |
|---|---|---|---|---|
| 1 | Attachments never read | ~~159~~ **120 parked · 28 OCR-addressable** | 28 → 0 | 1 |
| 2 | Columns crossing the L1→L2 seam | **9 of 28** | **17** (the rest have no L2 reader) | 3 |
| 3 | ~~`relationship_change` signals surviving the floor~~ **WRONG — see below** | ~~1 of 49~~ | — | ~~4~~ → **8** |
| 3ʹ | Claim lanes that can carry a receipt *(step 4's real metric)* | **8 of 15** | **11 of 15** | 4 |
| 4 | Events carrying a non-fallback domain | **8%** (74 of 889) | set at step 6 | 6 |
| 5 | Events never judged for relevance | **69 of 225 (31%)** | <5% | 8 |
| 6 | Benchmark semantic objects present | **16 of 38** | 30+ | 11 |

### The six numbers, at END — step 17's last criterion

⛔ **THREE OF THE SIX CANNOT BE RE-MEASURED WITHOUT THE CORPUS, AND THEY ARE NOT GIVEN A NUMBER.**
Writing one would be the failure this whole round was built to end — a figure nobody measured,
sitting in a table that looks measured.

| # | Metric | START | END | Verdict |
|---|---|---|---|---|
| 1 | Attachments never read | 120 parked · 28 OCR-addressable | **⛔ unmeasurable** | the pilot corpus no longer exists, and OCR **has never run once** — Harsh item 5 (deploy) |
| 2 | Columns crossing the L1→L2 seam | 9 of 28 | **17 declared** | ✅ target met on the CONTRACT. Whether they carry values needs migrations 0177/0179/0180 + a Postgres replay |
| 3ʹ | Claim lanes that can carry a receipt | 8 of 15 | **11 of 15** | ✅ **target met.** `RoleAssertion`, `AvailabilityWindow`, `OpenQuestion` promoted in step 4, and ALG-08 now walks them |
| 4 | Events with a non-fallback domain | 8% (74 of 889) | **⛔ unmeasurable** | the tagger, the proposer and the indiscriminate guard are built; the share is Harsh item 10 |
| 5 | Events never judged for relevance | 69 of 225 (31%) | **⛔ unmeasurable** | the all-or-nothing guard is gone and `allocate_budget` defers instead of refusing — the new rate is Harsh item 13 |
| 6 | Benchmark semantic objects present | ~~16~~ **15 of 38** | **24 of 38** | ⚠️ **+9, still short of 30+.** Step 18 carried the conversation and closed 4 `not_carried` misses; **7 of the remaining 14 are still that class** — a seam question, not a capability one |

> ⛔ **METRIC 6's START WAS WRONG AND STEP 11 FOUND IT.** The audit's summary said *"16 built"*
> while its own tables showed **15**. `L1_P1_P5_AUDIT.md` now carries a SUPERSEDED banner.
> `calibrate()` reports **0 unexplained and 0 regressed** against that corrected baseline, so the
> +5 is real movement and not a harness that learned to flatter itself.

**Three of six blocked on one thing.** Metrics 1, 4 and 5 are all *"the code is built, the number
needs the corpus"* — Harsh items 1, 5, 10 and 13.

---

### The diagnosis this plan acts on

> L1's **code** is wired — 0 dead modules. L1's **data** is not. Every measured loss is a value
> that is computed correctly and then not carried: `ball_in_court` and `turn_index` reach only
> the trace, `direction` only `prepared_content`, `subject_key` only the drop ledger, and seven
> claim types are typed as `list[str]` / `list[dict]` so they have **no field in which to hold a
> receipt**.

---

## LAYER 1 — STEPS

| # | Step | Status | Number it moves | Completed |
|---|---|---|---|---|
| 1 | OCR — establish state, then drain | **PENDING · HARSH** ([runbook](layer-1/STEP-01-PENDING-HARSH.md)) | ~~159~~ → **28 OCR-addressable** → 0 | 1-U1 done 2026-09-23 |
| 2 | Bounce / DSN path | **CODE COMPLETE · PENDING · HARSH** ([runbook](layer-1/STEP-02-PENDING-HARSH.md)) | 0 → **3** delivery-failure signals | 2026-09-23 |
| 3 | Widen the seam | **CODE COMPLETE · PENDING · HARSH** ([runbook](layer-1/STEP-03-PENDING-HARSH.md)) | 9 → **17** columns | 2026-09-23 |
| 4 | Promote the untyped bags to typed claims | **CODE COMPLETE · PENDING · HARSH** ([runbook](layer-1/STEP-04-PENDING-HARSH.md)) · **⚠️ re-extracts the corpus — see below** | 8 → **11** of 15 lanes carry a receipt | 2026-09-23 |
| 5 | Coverage denominator | **CODE COMPLETE · PENDING · HARSH** ([runbook](layer-1/STEP-05-PENDING-HARSH.md)) · **⛔ decision needed: 60-day window** | a sweep can now say whether it finished · 5-U5 deferred to step 15 | 2026-09-23 |
| 6 | Domain mapping | **CODE COMPLETE · PENDING · HARSH** ([runbook](layer-1/STEP-06-PENDING-HARSH.md)) · **⛔ 6-U0 baseline needed** | confidence + ontology + proposer built; metric 4's target cannot be set until the corpus is re-measured | 2026-09-24 |
| 7 | Intent split + dead predicates | **CODE COMPLETE · PENDING · HARSH** ([runbook](layer-1/STEP-07-PENDING-HARSH.md)) · **cheapest step yet — zero cost** | all 16 types provably fireable; intent confidence + disagreement + unknown rate | 2026-09-24 |
| 8 | Importance ceiling + relevance allocator | **CODE COMPLETE · PENDING · HARSH** ([runbook](layer-1/STEP-08-PENDING-HARSH.md)) · **⛔ metric 5 needs one query** | 0 judged on an over-budget page → the head judged, the tail NAMED · the ceiling is published | 2026-09-24 |
| 9 | Claim directness | **✅ COMPLETE — all 4 criteria closed, nothing for Harsh** ([findings](layer-1/findings/step-09-directness.md)) | hearsay now composes **below** a witnessed account from the same author | 2026-09-24 |
| 10 | `REVIEW` as a fourth outcome | **10-U0 BUILT · U1–U4 GATED** ([runbook](layer-1/STEP-10-PENDING-HARSH.md)) · **the step gated ITSELF on a measurement** | nothing shipped — `PublicationOutcome` stays closed at three until a real count says otherwise | 2026-09-24 |
| 11 | P1–P5 replay harness | **STRUCTURAL HARNESS BUILT · corpus is HARSH's** ([findings](layer-1/findings/step-11-replay-harness.md)) | **baseline corrected 16 → 15 · measured 20 of 38** · 11 of 18 misses are `not_carried` | 2026-09-24 |
| 12 | Per-type signal states + commitment fulfilment | **CODE COMPLETE** ([findings](layer-1/findings/step-12-signal-states.md)) · 12-U3/U7 deferred with a reason · distribution needs the corpus | `BROKEN` now requires a coverage figure ≥9000 bp — otherwise `UNKNOWN` | 2026-09-24 |
| 13 | Cross-source identity keys | **CODE COMPLETE** ([findings](layer-1/findings/step-13-identity-keys.md)) · joinability figure needs the corpus | `to`/`cc` stop being flattened · attendees keep their names and responses · `meeting_kind` | 2026-09-24 |
| 14 | Temporal field set + reply pairing | **CODE COMPLETE · PENDING · HARSH** (migration 0179) ([findings](layer-1/findings/step-14-temporal.md)) | **2 → 6 world instants** · a signal can now say "8 days overdue" | 2026-09-24 |
| 15 | Coverage on the signal | **✅ ALL 5 CRITERIA CLOSED · PENDING · HARSH** (migration 0180) ([findings](layer-1/findings/step-15-coverage-on-signal.md)) | a `broken` signal **cannot publish** without its coverage | 2026-09-24 |
| 16 | Source field coverage | **✅ ALL CRITERIA CLOSED** ([findings](layer-1/findings/step-16-source-field-coverage.md)) · no migration · one **bounded** re-extraction | ⛔ **every prompt in production said "message 1 of 1"** — a 12-message thread was described to the model as the first and only message | 2026-09-24 |
| 18 | The conversation crosses the seam | **✅ COMPLETE · PENDING · HARSH** (migration 0181) ([findings](layer-1/findings/step-18-conversation-crosses-the-seam.md)) | **benchmark 20 → 24** · ⛔ S01b's diagnosis was wrong and the real defect was one seam later | 2026-09-24 |
| 17 | Adversarial validation | **✅ 6 of 7 CRITERIA CLOSED · 17-U6 BLOCKED ON HARSH** ([findings](layer-1/findings/step-17-adversarial-validation.md) · [failure log](layer-1/FAILURE-LOG.md)) | **40 rows typed by failure class · 28 mutation rows · 1 still OPEN** · ⛔ 991 of 995 skips are one missing env var | 2026-09-24 |

> **✅ STEP 6 IS BUILT — and its cost check PREVENTED a defect instead of documenting one.** Before
> a line was written, the check found that adding domains to LLM-2's prompt would move
> `vocabulary_fingerprint` and re-extract the whole corpus a second time. So the proposer got its
> **own model call**: cache untouched, own metering purpose, skippable under 80 characters, and it
> can die without failing a capture. **This is the first time the plan's own lesson stopped
> something rather than explaining it afterwards.**
>
> It also committed the `claimed_total` defect AGAIN — `domain_tagged` was a field nothing filled —
> and the test written to catch it measured nothing at first, because its fixture used a source
> with no visibility rule and every event parked. **A test can be green, drive the real path, and
> still measure nothing.**
>
> **📋 STEP 6's PLAN CHECK moved it from "weeks" to "days.** Three of its written
> premises were wrong: the matcher is **already multi-label**, the never-filter rule **already has
> 14 green tests** (6-U4 struck), and the *"four keyword tables"* line predates authored corpora.
> Its 8% baseline is from the tenant that was re-synced away, so **6-U0 is now "re-measure and
> write the target down before any code"**. The cost check ran first and **made an architecture
> decision**: the domain proposer gets its OWN model call, because adding a domain set to LLM-2's
> vocabulary would move `vocabulary_fingerprint` and re-extract the whole corpus a second time.
>
> **⛔ STEP 5 FOUND THE THING THAT BLOCKS THE BENCHMARK, and it is not a code defect.** The step
> file said the backfill window is 540 days. **It is 60** (`DEFAULT_BACKFILL_DAYS`, and migration
> 0082 stamps it onto every existing connection). Benchmark **P3 asks about 6 months** and **P4
> about 12** — so on a default connection those are not "unproven", they are **structurally
> impossible: the mail was never fetched.** Raising it is a per-connection admin write, reversible,
> with a one-time extraction cost. **Recommended: raise it for the benchmark tenant only**
> (§2.4 of the step-5 runbook). Until that decision is made we should stop citing P3 and P4.
>
> **⚠️ STEP 4 CARRIES A MODEL BILL, and its own plan never named it.** Measured while ticking the
> done criteria: `vocabulary_fingerprint()` moved `151b9dabf235 → a3d5496aa0d3`, because
> `UNTYPED_LANE_KEYS` is folded into it and that digest is a component of the
> `l1_extraction_results` cache key. **Every cached extraction misses; the whole corpus
> re-extracts on the first sweep after deploy.** That is *correct* — the prompt genuinely changed,
> and the module records the failure where *"260 cached extractions survived a prompt fix, the
> numbers did not move, and the conclusion drawn was that the fix had not worked"* — but it is
> real spend, it needs Harsh's sign-off, and the volume needs one production query (§5.3 of the
> runbook). Now pinned by a test, so the next fingerprint move is announced rather than invoiced.
>
> **Read this as a lesson about the step files, not about step 4.** Seven done criteria were
> written in advance; six were satisfied by the work and the seventh was the only one that found
> anything. **Steps 5–17 should each be checked for a cache-key or cost consequence before they
> are built, not after.**
>
> **CONFIRMED BY STEP 5, immediately.** Its criteria found that the denominator — the headline of
> the whole step — was read with `getattr(batch, "claimed_total", None)` against a field that
> existed on no contract and was set by no connector. `None` on every row forever, with a green
> test that only asked whether `SyncSummary` had somewhere to put it. **Ticking the done criteria
> has now found the most serious defect in two consecutive steps, and in both cases the suite was
> green.** It is not paperwork; treat it as the last verification step of every step from here.

> **Step 17 runs LAST and then again after every future change.** It does not build a feature —
> it tries to break the other sixteen. Every defect found in this investigation was sitting behind
> a green suite, so the suite is not evidence; step 17 is where evidence comes from.

> **Step 16 was added on 2026-09-23 after a reasoning pass.** Steps 1–15 all assume the raw
> object already contains the field they work on; **none of them checks that assumption.** Reading
> two connectors found three confirmed gaps in twenty minutes — Gmail never captures `bcc`,
> `In-Reply-To` or `References` (so ALG-03's `assemble_chain` has never run on real data), and
> Calendar flattens attendees to email strings, discarding `responseStatus`. Step 16 is the
> manifest and the ratchet that stop this class of defect.
>
> **Steps 12–15 were added on 2026-09-23 after a gap check** against the six things a CTO would
> ask for. Steps 1–11 covered corpus accounting, evidence-backed objects and the replay harness;
> they did **not** cover the signal-state model, cross-source identity keys, the temporal
> vocabulary, or carrying coverage onto the signal. Those four are now steps 12–15.

---

## LAYER 1 — WHAT EACH FINISHED STEP ACTUALLY CHANGED

One line per step, for somebody who has not read the findings. **"Mine" = code, done. "Harsh" =
a decision, a migration or an access I cannot do from this machine.**

| Step | The defect, in one sentence | What I built | Still open |
|---|---|---|---|
| **1 · OCR** | OCR has **never run once** in production — every `document_jobs` row has `ocr_engine=NULL`. Not a flag, not a code path: the image never reached the host | corrected a stale `Dockerfile` note claiming two env vars were still required; both clauses were false | **Harsh:** deploy the image |
| **2 · Bounce** | Three pitches to Afore and Surge never arrived. All 5 delivery-status notices were captured and **produced zero signals** — a founder who believed they pitched two funds had not | `delivery_status.py` recogniser, `DELIVERY_FAILURE` as taxonomy member 16, precedence + weight + policy rows + a qualification override, migration 0176 | **Harsh:** 0176 + replay |
| **3 · Seam** | L1 persists **28 columns**; L2 read **9**. Eight values computed every sweep and dropped. `subject_key` had a column on the DROP ledger and none on published signals — a refused signal recorded what it was about, a published one did not | both projections widened 9 → 17, `subject_key` carried end to end, migration 0177 | **Harsh:** 0177 + replay |
| **4 · Typed claims** | Three lanes fired real signal types and **could not carry a receipt** — the type had no field to put one in. `detector.py` said so in its own comment | `RoleAssertion` / `AvailabilityWindow` / `OpenQuestion`, routed through the real binder so S-4 holds by construction; ALG-08 now grades them; 4 predicates now cite; a read-side migration so cached rows still load | **Harsh:** A/B decision + size the re-extraction bill |
| **5 · Coverage** | The manual backfill door printed the word **"done"** when it meant **"stopped"**, and no record anywhere could tell the two apart afterwards | `cursor_exhausted` (three-valued) + `page_budget_spent` + the provider's own count, migration 0178; sent/received symmetry check | **Harsh:** 0178 + the 60-day window decision |
| **6 · Domain** | Domains had no confidence, no ontology, and nothing that reads more words than a regex | `confidence_bp` per hint, a derived ontology, `proposed_unknown`, coverage **and distribution**, a proposer on its own metered model call (off by default) | **Harsh:** the baseline query + on/off decision |
| **7 · Intent** | Four signal types never fired and **nothing could say whether the predicate was unreachable or the tenant simply had none** — the same class of bug the drop ledger was built to kill | a derived intent confidence, the gate↔extractor disagreement recorded instead of folded away, the `unknown` rate per sweep, and a guard that every taxonomy member has a test firing it | **Harsh:** one A/B decision, and it costs nothing either way |
| **15 · Coverage** | *"No follow-up found"* means nothing until you know whether the search covered 100% of the mail or 8% — and the signal carried only a BOOLEAN about whether a channel was connected | the window and per-source completeness carried on the signal, **frozen at capture** so a later backfill cannot retroactively strengthen an old claim, and a contract rule that a negative claim without its proof cannot publish | **Harsh:** apply 0180 |
| **14 · Temporal** | A signal could not say **"8 days overdue"** — the deadline lived inside a claim nested in the extraction jsonb, where nothing can sort or sweep by it. And reply pairing, which is pure arithmetic, was being done in Layer 2 | four world instants on the signal (lifted, never re-derived), migration 0179, and `pair_replies` in L1 with L2's two rules preserved exactly | **Harsh:** apply 0179 |
| **13 · Identity** | P4's join needs `Manik` on an invite and `Manik` in an email to be joinable — and L1 was **destroying the keys**: `to`/`cc` flattened twice, calendar attendees reduced to address strings, no way to tell a cohort session from a meeting somebody owes a recap | the to/cc split preserved additively, attendees kept as people (names and responses included), `meeting_kind`, and a joinability ratio so *"no follow-up found"* can be told from *"never joinable"* | **Harsh:** the joinability figure |
| **12 · States** | *"Did the promise get kept?"* had no vocabulary — and worse, **nothing stopped L1 saying `BROKEN` on a corpus it had read 8% of.** Claude marked four promises broken and was right; the same inference here would be a confident lie | three per-type state vocabularies as contract data, and a coverage gate: an absence means `BROKEN` only when we can show we looked | **Harsh:** the pilot's state distribution — §3 predicts most land in `UNKNOWN` |
| **11 · Harness** | The benchmark scoreboard was audited **by hand, once** — so it miscounted itself by one, went stale, and nothing could notice because nothing re-derived it | a machine-checked scoreboard that runs in CI, separates *improved* from *harness bug* from *regressed*, classes every miss, and **refuses to quote a behavioural number on 8 messages** | **Harsh:** the 425-item corpus and a second mailbox |
| **10 · Review** | A signal that is **low confidence but high value** has nowhere to go — it either emits as though certain or lands in a drop ledger nothing routes to a person | **only the measurement.** `review_candidates.py` counts the refusals sitting near their own ceiling; `PublicationOutcome` stays closed at three until that count exists, because the step's own rule is that the measurement may cancel it | **Harsh:** run the measurement — it decides whether the step exists |
| **9 · Directness** | *"I heard Acme is leaving"* and *"Acme is leaving, I spoke to their CFO"* — same CEO, same email — were **the same number**. ALG-14 ranks the artifact, so both are `EMAIL_PROSE`; nothing asked whether the writer witnessed it | a derived directness axis read off the span's own words, discounting hearsay (7000) and speculation (5000) while a witness stays neutral — so a rumour can no longer outrank a first-hand account | **nothing — this one is closed** |
| **8 · Ceiling** | Every score read as mediocre against a scale **30% of which the tenant could not reach**, and an over-budget page judged **nothing** — 31% of events never assessed | `achievable_ceiling_bp`, the first consumer the ten `ImportanceFlag` members have ever had; and an allocator that spends the same budget on the head instead of refusing to spend it, with the tail NAMED `unjudged_for_budget` | **Harsh:** one query for metric 5 |

### The pattern across all six

> **Five of six steps had a written premise the code or production contradicted** — and not one
> correction was cosmetic. Step 2 thought the gate deleted bounces; it did not. Step 3 thought
> `array_agg[1]` lost signals; it does not. Step 4 thought typing would raise a score; it cannot.
> Step 5 thought the window was 540 days; it is 60. Step 6 thought the matcher was single-label
> and untested; it was neither.
>
> **The rule that found all five — *measure before you change* — has paid for itself every time.**

> **Three defects were found by TICKING THE DONE CRITERIA, not by the suite**, which was green in
> every case: step 4's re-extraction bill, step 5's denominator that nothing fed, step 6's metric
> that nothing incremented. The checklist is not paperwork; it is the last verification step.

---

## LAYER 1 — COMPLETE

*Not written yet. This section is filled only when every step above has passed its proof, and it
must contain: what was built, the START-vs-END number for all six metrics, what is still open and
why, and what was deliberately not done.*

---

## LAYER 2 — START

**Opened 2026-09-24.** Plan: [`layer-2/`](layer-2/) — [overview](layer-2/00-OVERVIEW.md) ·
[architecture](layer-2/ARCHITECTURE.md) · nine step files.

### What Layer 2 is, at the moment work began

```
genios_engine/context/   111 files   48,322 LOC      ← LARGER than L1's 42,311
                         57 root modules · 8 code subpackages · 5 content (YAML) subpackages
7 groups · 44 components · 46 planned units
```

### ⛔ The diagnosis

**Layer 2's dominant failure is a refusal that is right and invisible.**

| | measured | status |
|---|---|---|
| situations held, L1 published nothing | **63 of 159** — scored 528–1920 vs a floor of 2500 | refusal correct, **silence is not** |
| support situations unrouted | **33** — `support` vs `customer_support` | *"why the miss was invisible"* |
| fundraising domain | **no corpus** — `domain = None` → no package, no signal | the pilot is a fundraising founder |
| untraceable promises | **21**, ten carded before refusal | *"the founder saw promises nobody made"* |

Plus two structural findings:

* ⛔ **The card is built from a SIGNAL, not a situation** — `deliver/pipeline.py:269` loops over
  `_open_signals_without_cards`. Three measurements about one person become three cards and can
  never merge.
* ⛔ **Six interpretation fields are missing from the contract** — `observed_facts`,
  `inferred_state`, `hypotheses`, `implications`, `reasoning_trace`, `valid_until`. Every field
  present is an observation field. Every field missing is an interpretation field.

### ⛔ PRE-FLIGHT — measured 2026-09-24, before step 0

[`layer-2/03-PRE-FLIGHT.md`](layer-2/03-PRE-FLIGHT.md) · **it corrected the plan in three places.**

**Layer D is not thin — it is inadmissible.** `Domain Expertise/` holds **1,425 YAML files, 534
capabilities**: Admin 211, Sales 156, Customer Support 167, plus 228 playbooks and 283 heuristics.

| | authored | **admissible** | |
|---|---|---|---|
| Admin | 211 | **85** | 40% |
| Sales | 156 | **62** | 39% |
| Customer Support | 167 | **53** | 31% |
| | **534** | **200** | **37%** |

⛔ **L2-8 flips `require_admission=True` and 334 capabilities go dark.** The largest un-owned risk in
the plan; nothing in the nine steps had addressed it. Now `L2-4-U5`.

Both circulating numbers were wrong: `domain_shadow`'s *"152"* is stale; *"211"* was Admin alone.

**And Plane R is far more complete than the plan assumed.** 114 files, 39,012 LOC, already holding
`decision_maker.py`, `llm_decision_maker.py`, `critique.py` and **`interpretation.py` — R-1, whose
contract is stronger than anything this plan wrote**: *"the model's output is an input to a
deterministic computation"* and ⛔ *"**it cannot raise confidence**."*

⛔ **One gate already exists for every model consult** — `RSiteGate`, seven steps: activation,
precondition, budget, cache, tier, **the caller's validator**, deterministic fallback. *"No R-site
may call a model directly."*

**Three corrections:** the Context Reasoner is not absent, its *pattern* exists · L2-5 registers an
**R-site**, it does not build a gate · L2-6 writes the **validator**, the gate calls it.

⛔ **And the third repetition of one sentence.** `domain_shadow` compiles and drops. R-1 *"has never
fired on the pilot tenant."* 63% of the corpus is authored and inadmissible. **This engine's problem
is not absence — it is things built correctly and never switched on.**

### ⛔ RE-ANALYSIS — the premise was wrong

[`layer-2/04-RE-ANALYSIS.md`](layer-2/04-RE-ANALYSIS.md). **Layer 2 is not half-built. It is built
and unswitched.**

⛔ **All five benchmark prompts already have a situation type**, each declaring the fields it is
expected to know:

| | type | and it declares |
|---|---|---|
| P1 | `awaiting_response` | ⛔ **`their_normal_reply_days`** — the column Gemini AND Claude both skipped |
| P2 | `commitment_overdue` | `delivered_at` |
| P3 | `organization_gone_quiet` | `longest_wait_days` |
| P4 | `meeting_follow_through` | `recap_sent` |
| P5 | `condition_in_review` | `quote` |

⛔ **`fundraising` IS a registered L2 domain** — `investor_relationship`, `investor_contact`. L2
mints them; **no corpus was ever authored to read them.** Authoring, not code.

⛔ **Typed absence already exists with five states** — `PRESENT · STALE · NOT_EXPECTED · UNKNOWABLE
· GENUINELY_ABSENT` — consulting `coverage_ready` before concluding absence, wired producer to
consumer. **Step 2 was going to rebuild it binary.**

### ⛔ Eight things built and never switched on

```
domain_shadow compile      live=False for every caller
R-1 interpreter            "has never fired on the pilot tenant"
534 capabilities           200 admissible
typed absence              consulted by the compiler, shown to no human
63 held situations         l1_refusal() has the score; nothing renders it
33 support situations      "which is why the miss was invisible"
fundraising situations     minted, no corpus
L1 conversation fields     landed step 18; attention.py still recomputes its own
```

`quality/inference.py` names the shape: *"a well-typed value **nobody consults, which is
indistinguishable from not having built it**."*

**Genuinely missing: `observed_facts` (0 files) · `inferred_state` (0 files) · an L2 reasoner site ·
Persona Brain · card-from-situation · goals · the fundraising corpus.** Ten items; four are code.

### LAYER 2 — STEPS

| # | step | status | headline | date |
|---|---|---|---|---|
| 0 | [Make every refusal visible](layer-2/step-00-visible-refusals.md) | **NOT STARTED** | the denominator for every later number | — |
| 1 | [Name it](layer-2/step-01-names.md) | **NOT STARTED** | two classes share one name and it cost this plan a wrong paragraph | — |
| 2 | [Six interpretation fields](layer-2/step-02-six-fields.md) | **NOT STARTED** | observation ≠ inference ≠ hypothesis, with write authority | — |
| 3 | [The evidence slice](layer-2/step-03-evidence-slice.md) | **NOT STARTED** | handed, never fetched — a fetched slice cannot be replayed | — |
| 4 | [Domain Compiler](layer-2/step-04-domain-compiler.md) | **NOT STARTED** | ⛔ fundraising is structurally dark | — |
| 5 | [Context Reasoner](layer-2/step-05-context-reasoner.md) | **NOT STARTED** | the one new model site · **per situation, not per event** | — |
| 6 | [The validation gate](layer-2/step-06-validation-gate.md) | **NOT STARTED** | deterministic, free — **and what makes Haiku safe** | — |
| 7 | [Card from the situation](layer-2/step-07-card-from-situation.md) | **NOT STARTED** | the step the founder actually sees | — |
| 8 | [Turn it on](layer-2/step-08-turn-it-on.md) | **NOT STARTED** | three flips together · adversarial pass | — |

**Order:** 0 → 1 → 2 → 3 → 4 → 6 → 7 → 5 → 8. Steps 0–4, 6 and 7 need nothing from Harsh; 5 needs a
situation count for its cost check and 8 needs the shadow pass tallies.

### What is missing entirely

| | |
|---|---|
| **Persona Brain** | the fifth brain — not in `BrainKind`, not an `ExpertisePackage` lane. Holds *how this kind of company and this role works*, which is what makes a tenant legible before Behavior has history |
| **Context Reasoner** | the interpretation site. Does not exist |
| **Validation gate** | what checks a proposal. Does not exist |
| **Goals** | `org_goals` → 0 files. Belongs in **Organization Brain** as a category row beside `approval`/`policy`/`process`/`criticality` — the extraction machinery already verifies a quote byte-for-byte |
| **`fundraising` corpus** | authored doctrine, not code. The largest non-code item in the plan |

---

## HARSH — THE CONSOLIDATED ORDER

Everything blocked on the CTO, across steps 1–5, in the order to do it:
**[`../HARSH-ORDER.md`](../HARSH-ORDER.md)** — 9 items: 1 access, 3 migrations, 1 deploy,
2 decisions, 1 measurement, 1 question.

`HANDOFF-CTO.md` is superseded by it (it covered steps 1–3 only) and now says so at the top.

**The two that matter most:**

| | |
|---|---|
| **Scratch Postgres** | 618 tests are SKIPPED, not passing. One URL closes the open half of steps 1, 2, 3 and 5 at once |
| **The 60-day window** | until it is raised, benchmark P3 and P4 are **impossible, not unproven** — and we should stop citing them |

---

## LAYER 1 — FINDINGS LOG

One file per step under `layer-1/findings/`. `STATUS.md` stays a table; the detail lives there,
so this file is still readable at step 17.

| Step | Findings | Verdict |
|---|---|---|
| 1 · OCR | [`findings/step-01-ocr.md`](layer-1/findings/step-01-ocr.md) | **1-U1 COMPLETE** · rest is **PENDING on Harsh** → [runbook](layer-1/STEP-01-PENDING-HARSH.md) |
| 3 · Seam | [`findings/step-03-seam.md`](layer-1/findings/step-03-seam.md) | **CODE COMPLETE**, 7 tests green, 0 regressions. Seam widened 9 → 17. **One unit WITHDRAWN** — production showed `array_agg[1]` loses nothing, because LLM-2 runs once per event. Awaiting migration `0177` + a Postgres replay |
| 17 · Adversarial | [`findings/step-17-adversarial-validation.md`](layer-1/findings/step-17-adversarial-validation.md) · [`FAILURE-LOG.md`](layer-1/FAILURE-LOG.md) | ⛔ **THE STEP'S CENTRAL CRITERION IS SELF-CONTRADICTORY AND SAYING SO IS THE FINDING.** §8 wants *"every scenario RED first"*; the plan was written BEFORE steps 1–16 ran, so S01 was closed by step 16, S03 by step 13, S21/S22 by steps 12 and 15 — **making them red means un-fixing the product**, which §9 forbids. Replaced by **technique 3**, which §2 already requires and which is strictly stronger: RED-first proves a test was failing, possibly for unrelated reasons; sensitivity proves it fails **precisely when this fix is removed**. 27 mutation rows + 1 on the harness, covering **all sixteen** steps — nine was the first draft and nine is not sixteen. **Three reproduce regressions that ACTUALLY HAPPENED** (step 9's `UNKNOWN=9000`, step 13's cohort rung, step 4's unwalked lanes). §7's own purity grep **flags its own float guard** and is corrected. Result: 29 closed · 5 guard · 4 corpus · **1 OPEN (S01b — `reconstruct_thread` still gets a ONE-message list)** · 1 impossible. ⛔ **17-U6 cannot be ticked: 991 of 995 skips are `GENIOS_TEST_DATABASE_URL`, and a skip is not a pass** |
| 16 · Field coverage | [`findings/step-16-source-field-coverage.md`](layer-1/findings/step-16-source-field-coverage.md) | **TWO OF THE THREE NAMED GAPS MOVED, AND A FOURTH DEFECT WAS FOUND THAT IS BIGGER THAN ALL THREE.** `responseStatus` was already closed by step 13; `bcc` is **impossible** — the provider does not supply it. The real finding: `pipeline._thread_place` has read `thread_position`/`thread_depth` since it was written and **no connector ever wrote either**, so `_envelope_block` rendered *"message 1 of 1"* into **every prompt this product has ever run** and `turn_index` was 0 for the whole corpus. **Not a missing field — a wrong one, stated confidently**, which is why 12,700 tests never saw it. Fixed at **no extra API cost**: RFC 5322 `References` gives the position (N ancestors → message N+1), and `depth = position` because capture always happens at the tip. **T2 passed on its first run and proved the opposite of its premise** — `assemble_chain` is correct and is fed a ONE-message list, so capturing the headers is *necessary and not sufficient*, recorded rather than papered over. Cost check bounds the re-extraction to **replies only**, and a reply's cached extraction was produced from a prompt that lied — the miss IS the fix |
| 15 · Coverage | [`findings/step-15-coverage-on-signal.md`](layer-1/findings/step-15-coverage-on-signal.md) | **ALL FIVE CRITERIA CLOSED, nothing deferred.** This is the step that closes a loop opened two steps back: **step 5** built the denominator, **step 12** built the `BROKEN`-requires-coverage rule *with nothing wired in*, **step 15** is that somewhere. At 8% an overdue promise reads `UNKNOWN`; at 95% it may read `BROKEN` — nothing about the promise changed, only what we can prove about having looked. **Two locks**: step 12 refuses to RESOLVE, the contract refuses to PUBLISH — because a caller constructing a signal directly bypasses the resolver |
| 14 · Temporal | [`findings/step-14-temporal.md`](layer-1/findings/step-14-temporal.md) | **ALL FOUR CRITERIA CLOSED.** 2 → 6 world instants, migration 0179, and reply pairing moved into L1 with `waiting.py`'s two rules **read first and reproduced, not reinvented** (integer seconds, not float days — V-7). **Two defects found while wiring:** (a) a `getattr` against my own contract that was dead code — step 5's exact smell; (b) **a STEP 6 LEAK** — `build_signal` rebuilt `domain_hints` by hand and dropped `confidence_bp`, so step 6's headline field never reached storage despite being asserted at the other seam |
| 13 · Identity | [`findings/step-13-identity-keys.md`](layer-1/findings/step-13-identity-keys.md) | **THE PREMISE WAS RIGHT AND THE CODE WAS WORSE THAN IT SAID.** `to`/`cc` are read separately from the headers, flattened one line later, preserved in the raw dict, and flattened AGAIN by the only consumer that reads them (`runner.py:161`) — **three chances, all missed**. The cost check decided the design a fourth time: `envelope_hash` is a cache-key component, so the split crosses on the CONTRACT and the prompt stays byte-identical. **E5 is wrong** — bcc is not available from Gmail at all. Calendar attendees stop losing rooms and `responseStatus`; `meeting_kind`'s rung order was corrected so a 20-person session is never chased for a recap |
| 12 · States | [`findings/step-12-signal-states.md`](layer-1/findings/step-12-signal-states.md) | **FIRST STEP IN TWELVE WHOSE PREMISES WERE ALL CORRECT** — it was written after the gap audit with the code already read. **E1 is the whole step**: `BROKEN` requires coverage ≥9000 bp, `None` coverage lands on the same side as low, and the gate guards ONE direction (`FULFILLED` needs none — finding evidence is positive). **My first vocabulary REPLACED the generic four and 6 L2 tests went red** — every stored commitment carries `state="active"`; they are two axes sharing one column, and a union is what §9 demands. 12-U3 deferred: fulfilment detection is a cross-event join and L1's unit is one event |
| 11 · Harness | [`findings/step-11-replay-harness.md`](layer-1/findings/step-11-replay-harness.md) | **THE HARNESS'S FIRST ACT WAS TO FIND TWO ERRORS IN OUR OWN SCOREBOARD.** (a) `L1_P1_P5_AUDIT.md`'s summary says *"16 built"*; its own tables show **15** — miscounted in the flattering direction and quoted into the plan as metric 6's baseline. (b) it was already stale — 5 objects have moved, so the live score is **20 of 38**. It also caught MY bug: checking "does the type exist" made 8 stranded objects read present, and `calibrate`'s *unexplained* population — which exists for exactly that — flagged all 8 within a minute. **`not_carried` is 11 of 18 misses**, which is this plan's thesis as a number |
| 10 · Review | [`findings/step-10-review-outcome.md`](layer-1/findings/step-10-review-outcome.md) | **U0 BUILT · U1–U4 DELIBERATELY NOT BUILT.** The step gates itself — *"68 or 0 both mean the thresholds are wrong, and 0 means the step is not needed yet"* — and the 68 is from the vanished corpus. **The routing rule as written is unbuildable**: `finalize.py` runs QUALIFY before PUBLISH, ALG-13 composes confidence at publish, so at the moment the floor refuses a signal its confidence does not exist. Routed on `achievable_ceiling_bp` instead — which step 8 put in exactly that reach, and which is the better rule anyway. **Steps 4 → 8 → 10 are one finding seen three times** |
| 9 · Directness | [`findings/step-09-directness.md`](layer-1/findings/step-09-directness.md) | **ALL FOUR CRITERIA CLOSED — the first step that needs nothing from Harsh.** 30 tests, no migration, no model call, no re-extraction, and no stored value moves. **The cost check set the architecture for the third time**: asking the model would have re-extracted the corpus, so directness is DERIVED from the anchor span's own words — cheaper, and more correct by doctrine 1, and the receipt is the quote itself. **The existing suite refused my first design**: `UNKNOWN=9000` turned 8 confidence tests red because it silently discounted every composition in the system; corrected to neutral, with the failure recorded |
| 8 · Ceiling | [`findings/step-08-importance-relevance.md`](layer-1/findings/step-08-importance-relevance.md) | **8-U1′/U2/U4/U5 COMPLETE · 8-U3 and 8-U6 deferred with reasons.** 18 tests, **no migration, no re-extraction, no extra spend** — the budget is unchanged, it is now ALLOCATED. **8-U1 was already built and had never been read**: `ImportanceFlag` has ten members, set on every score, and a grep for `.flags` outside the module returned zero — its own docstring predicted that (*"which is how a missing-data bug hides inside a plausible score for a year"*). The ceiling is their first consumer. A totality guard caught an incomplete change mid-build, and a test that asserted the defect was rewritten |
| 7 · Intent | [`findings/step-07-intent-predicates.md`](layer-1/findings/step-07-intent-predicates.md) | **7-U1′/U2/U3/U4′/U6 COMPLETE · 7-U5 nothing to retire · 7-U1 declined on price.** 18 tests, **no migration, no new model call, no re-extraction.** The cost check changed the design for the SECOND time: splitting intent out of LLM-2 would have moved `vocabulary_fingerprint` and re-extracted the corpus a third time, so the confidence is DERIVED from what the model already answers — which doctrine 1 required anyway. **A done criterion asked for something the codebase argues against in writing** (an evidence span on intent) and was amended, not met. All four "silent" types already had fixtures — their silence is a corpus fact |
| 6 · Domain | [`findings/step-06-domain.md`](layer-1/findings/step-06-domain.md) | **6-U1/U2/U3/U5/U6/U7 COMPLETE · 6-U4 STRUCK (already built) · 6-U0 is Harsh's.** 53 tests, no migration, and merging changes production behaviour for nobody — the proposer is off by default and proved byte-identical. **Three premises wrong again**: already multi-label, never-filter already has 14 green tests, "four keyword tables" predates authored corpora. The cost check ran FIRST and decided the architecture. Two self-inflicted defects recorded in §4 |
| 5 · Coverage | [`findings/step-05-coverage.md`](layer-1/findings/step-05-coverage.md) | **5-U1/U2/U4 COMPLETE**, 0 regressions, +28 tests, migration 0178. **2 of 4 done criteria ticked; the other 2 need a real mailbox and are left OPEN rather than ticked.** The build committed the "six times" defect itself — the denominator was `getattr` against a field no contract had and no connector set, so it was `None` forever while the test passed; found by ticking the criteria, not by the suite. Premise wrong for the **5th step running** — the backfill window is 60 days, not 540, which makes P3/P4 impossible rather than unproven. Two doors in one file disagreed about whether "did the sweep finish" mattered; the one that lands a tenant's whole history printed **"done"** when it meant **"stopped"**. 5-U5 **deferred with a reason** — `source_events` has no `run_id`, so the sweep→event join does not exist; it belongs beside step 15 |
| 4 · Typed claims | [`findings/step-04-typed-claims.md`](layer-1/findings/step-04-typed-claims.md) | **CODE COMPLETE**, 0 regressions, **no migration**. Premise wrong for the 4th step running — typing does NOT lift the score. Two defects found that the plan never named: **ALG-08 had never walked these three lanes** (so the only three signal types derived from unverifiable claims were also the only three whose receipts were never graded), and rehydrating a cached row would have **made every stored extraction unreadable** on the live L2 path. One product call open for Harsh — §4.3 of the runbook |
| 2 · Bounce | [`findings/step-02-bounce.md`](layer-1/findings/step-02-bounce.md) | **BUILT, 16 tests green, 0 regressions.** Premise was wrong and was corrected first; the wiring defect the build record names six times was caught by a test that drives the real path. **Awaiting a scratch Postgres to replay the five production bounces.** Full suite: 12,450 passed, 14 pre-existing failures, **0 regressions**. Two guards fired in **Layer 2** — adding a member to L1's closed enum is a change at both ends of the seam |

### The "next step" rule, with step 1 pending

`PENDING · HARSH` is **not** `NOT STARTED`. It is owned, specified and handed off — skip it. The
next actionable step is the lowest-numbered row that is `NOT STARTED` or `NEXT`.
