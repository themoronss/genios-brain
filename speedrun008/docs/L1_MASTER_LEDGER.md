# Layer 1 — the master ledger

> Branch `speedrun008` · 2026-09-23. The one document to work from.
> Every status below was measured today: module wiring by AST audit over all 119 modules,
> field wiring by tracing each computed value to its store, losses from
> `docs/plans/L1_L4_PILOT_FUNNEL.md` (849 real objects).

| Companion | Holds |
|---|---|
| `L1_ANATOMY.md` | the inventory — 138 files, 42,311 LOC, what each package is |
| `L1_GROUP_PLAN.md` | the eight ESQE groups, component by component |
| `L1_BUILD_SPEC.md` | the wiring tables — every item's engine (D/R/M/L/J) |
| `L1_P1_P5_AUDIT.md` | the 38 benchmark objects: 16 built · 8 stranded · 14 missing |
| **this file** | **the ledger + the loop** |

---

## 0. The wiring audit — and the result is good news that re-aims everything

The build record names the defect this layer shipped **six times**: *"a unit built, tested, green —
and called by nothing on a real request path."* Its rule: **a unit is done when a real request
path reaches it and a test drives that path.**

So that was checked mechanically, by AST, over every module in `capture/`:

```
capture/ modules                                    119
zero production importers                             3
  → coverage/audit          a gate RATCHET, test-driven by design    ✓
  → documents/fake          a dev/test engine, by design             ✓
  → screen/fingerprint      wired via importlib at pipeline.py:657   ✓
genuinely dead modules                                0
```

**L1's code is wired.** The six-times defect was found and fixed; a seventh instance
(`reconstruct_thread` "had no caller anywhere in the engine") is documented at `pipeline.py:568`
and also fixed.

### This changes the diagnosis

The problem is not dead code. It is **dead data**. Every loss found in this whole investigation is
a value that is *computed correctly and then not carried*:

| Computed by | Value | Ends up |
|---|---|---|
| `structural/threads.py` ALG-03 | `ball_in_court` | on the **trace**, not on the signal |
| `structural/threads.py` ALG-03 | `turn_index`, `thread_depth` | same |
| `pipeline._envelope_direction` | `direction` | on `prepared_content` only |
| `esqe/normalize.py` ALG-22 | `subject_key` | on the **drop ledger**, not on the published signal |
| `esqe/*` | `domain_hints`, `confidence_vector`, `occurred_at`, `expires_at`, `secondary_types`, `internal_kind`, `extraction_ref` | stored in `qualified_signals`, **never selected** by L2 |
| `semantic/extractor.py` | `questions`, `roles`, `availability`, `relationships`, `scheduling_proposals` | **untyped** — cannot carry a receipt at all |

> **L1 does the work and drops it on the floor between itself and Layer 2.**
> That sentence is the whole problem, and it is a much smaller problem than "L1 is not intelligent
> enough."

---

## 1. The component ledger

**Status key:** ✅ working · ⚠️ works but its output is stranded · ❌ missing or broken ·
**Engine:** D deterministic · R rules · M small model · L LLM · *J JEV (later, none yet)*

### A · Enterprise Sources (L1.1)

| # | Component | Status | What is wrong | Fix | Step |
|---|---|---|---|---|---|
| A1 | Source registry — 36 sources, 10 families, 9 buildable | ✅ D | — | — | — |
| A2 | Source waitlist | ✅ D | — | — | — |
| A3 | Coverage declaration — *is a channel connected* | ✅ D | — | — | — |
| A4 | **Coverage denominator** — *how many exist vs indexed* | ❌ | does not exist. Gemini's worst failure was claiming 18 of 18 | per-sync ledger: claimed · fetched · cursor-exhausted | **5** |

### B · Knowledge Connectors (L1.2)

| # | Component | Status | What is wrong | Fix | Step |
|---|---|---|---|---|---|
| B1 | Connector manager / auth / permissions | ✅ D | — | — | — |
| B2 | Backfill window — 540d per connection | ⚠️ D | configured, **never proven to complete** | run it, assert exhaustion | 5 |
| B3 | Webhook parity | ✅ D | — | — | — |
| B4 | Cadence · jitter · catch-up | ✅ D | — | — | — |
| B5 | **Sent/received symmetry** | ❌ | nothing asserts both sides landed; an absence claim is unsafe without it | a per-thread check | 5 |

### C · Event Pipeline (L1.3 part)

| # | Component | Status | What is wrong | Fix | Step |
|---|---|---|---|---|---|
| C1 | Landing + 3 dedup jobs | ✅ D | — | — | — |
| C2 | Mutability + `version_field` | ✅ D | — | — | — |
| C3 | Thread reconstruction ALG-03 | **⚠️ D** | `ball_in_court`, `turn_index`, `thread_depth` computed → **trace only** | carry onto the signal | **3** |
| C4 | Direction | **⚠️ D** | on `prepared_content`, not on the signal | carry onto the signal | **3** |
| C5 | **Reply pairing** (in→out, Δt) | ❌ | latency lives in `context/waiting.py` (L2); the *pairing* is mechanical | pair in L1, judge in L2 | 3 |
| C6 | **Bounce / DSN** | **❌ by design** | `gate/rules.py` N-01 + N-03 delete it. *"a bounce carries no business signal ever"* is false | parse RFC 3464; new `DELIVERY_FAILURE` type | **2** |
| C7 | Visibility stamping | ✅ D | — | — | — |
| C8 | Triage lanes P1/P2/P3 | ✅ D | — | — | — |

### D · Content Pipeline (L1.3 part)

| # | Component | Status | What is wrong | Fix | Step |
|---|---|---|---|---|---|
| D1 | HTML strip · PII mask · offset map | ✅ D | — | — | — |
| D2 | Quoted-history detection | ✅ D | — | — | — |
| D3 | **OCR** | **❌ off** | built, switched off. **159 attachments unread** on the pilot | deploy + two env vars | **1** |
| D4 | Chunking, offset-preserving | ✅ D | — | — | — |
| D5 | Structural tokens ALG-04 | ✅ D | — | — | — |
| D6 | Speech-to-text | — | descoped, no provider | transcripts arrive via P5 instead | — |
| D7 | Structured lane ALG-21 | ✅ D | calendar emits at **100%** vs Gmail's 27% | — | — |
| D8 | Extraction LLM-2 | ✅ **L** | — | — | — |
| D9 | Injection guard | ✅ D | — | keep for any new model site | — |

### E · Validation (L1.5)

| # | Component | Status | Fix | Step |
|---|---|---|---|---|
| E1 | ALG-08 spans — grades **and corrects** the model's offsets | ✅ D · **91% verified on pilot** | — | — |
| E2 | ALG-09 dates — a range with a certainty | ✅ D | — | — |
| E3 | ALG-10 money — integer path throughout | ✅ D | — | — |
| E4 | ALG-11 canonicalisation | ✅ D | a *hint*; L2 authoritative | — |
| E5 | ALG-12 conflict — both claims retained | ✅ D | — | — |
| E6 | ALG-13 confidence, Rule 11 | ✅ D | gains `claim_directness` as an input | 9 |
| E7 | ALG-14 authority table | ✅ D | — | — |
| E8 | **Claim directness** | ❌ | *"I heard Acme is leaving"* weighs as first-hand | new field, `unknown` default | **9** |
| E9 | Schema validator S-1…S-9 | ✅ D | — | — |

### F · The eight ESQE groups (L1.6)

| # | Group | Status | Measured | Fix | Step |
|---|---|---|---|---|---|
| F1 | Intent classification | ⚠️ **L** | rides inside LLM-2's mega-prompt; failures indistinguishable | separable contract | 7 |
| F2 | Category ALG-15/16 | ⚠️ D | **4 of 15 types never fired** on 395 signals | a fixture each, or retire | 7 |
| F3 | Importance ALG-17 | ⚠️ D | **every score < 4,700/10,000**; money term unearnable, criticality pinned at `first_seen` | publish the achievable ceiling; relative floor | 8 |
| F4 | Business relevance | ⚠️ R+**L** | **69 events (31%) never judged** — `ambiguous_over_budget` | budget **allocator**, not on/off | 8 |
| F5 | Source analysis | ⚠️ D | no directness axis | see E8 | 9 |
| F6 | Domain mapping | **❌ R** | **815 of 889 events carried no domain** — 8% recognition | multi-label proposal + ontology validation | **6** |
| F7 | Lifecycle ALG-19 | ⚠️ D | key is `(subject_key, signal_type)` but `subject_key` **never crosses the seam** | column + publisher writes it | **3** |
| F8 | Evidence & qualification | ⚠️ D | 3 outcomes exist; **no `REVIEW`** for low-confidence-high-value | fourth outcome, in the contract | 10 |

### G · The contract itself — *the finding that outranks the rest*

| # | Item | Status | What is wrong | Fix | Step |
|---|---|---|---|---|---|
| G1 | 8 typed claim lists | ✅ | each carries `evidence` + `confidence_bp` | — | — |
| G2 | **7 untyped bags** | **❌** | `questions`, `roles`, `relationships`, `availability`, `scheduling_proposals`, `implied_actions`, `topics` are `list[str]` / `list[dict]` — **no field exists to hold a receipt** | promote to typed claims | **4** |
| G3 | 3 predicates fire off them | **❌** | `RELATIONSHIP_CHANGE`←`roles` · `AVAILABILITY_CHANGE`←`availability` · a decision predicate←`questions` | follows from G2 | 4 |
| G4 | The consequence | **measured** | `relationship_change` scores **880–1240 bp** — lowest of any type — and **48 of 49 died at the floor** | follows from G2 | 4 |

### H · Storage & seam (L1.7)

| # | Component | Status | What is wrong | Fix | Step |
|---|---|---|---|---|---|
| H1 | Payload store, tiered TTL | ✅ D | — | — | — |
| H2 | Prepared content + offsets | ✅ D | — | — | — |
| H3 | Extraction store | ✅ D | — | — | — |
| H4 | `qualified_signals` — 28 columns written | **⚠️** | **L2 selects 9** | widen both projections together | **3** |
| H5 | `extraction_ref` resolution | **❌** | `array_agg(...)[1]` — **only the loudest signal per event** gets an extraction | per-signal join | **3** |
| H6 | `signal_lifecycle` | **⚠️** | nothing outside L1 reads it | — | 3 |

---

## 2. The steps, in order

Each step states its proof. **Nothing advances without it.**

| Step | Do | Fixes | Effort | Proof |
|---|---|---|---|---|
| **1** | Turn OCR on | 159 unread attachments | hours | `DOC-06` → 0 |
| **2** | Bounce / DSN path + `DELIVERY_FAILURE` | the benchmark's highest-value finding, deleted by design | days | 11 Aug replay yields Afore ×2 + Surge, each citing its sent message |
| **3** | Widen the seam — `subject_key`, both projections, per-signal extraction join | the stranded eight | days | a composed situation carries domains, confidence, `occurred_at`, `ball_in_court` — none `None` |
| **4** | **Promote the 7 untyped bags to typed claims** | 3 predicates · the 880–1240 band · 48 of 49 refusals | weeks | `relationship_change` carries a citable span and scores above the floor |
| **5** | Coverage denominator + backfill completion + symmetry | "we read N of M" | days | `claimed 465 · fetched 465 · exhausted true` |
| **6** | Domain mapping — multi-label + ontology | 815 of 889 events | weeks | non-fallback domain coverage moves off 8% |
| **7** | Intent split · dead predicates | debuggability | days | a fixture fires each of the 4 silent types, or the type is retired |
| **8** | Importance ceiling + relevance allocator | all 395 signals · 69 unjudged | days | distribution **shape unchanged**; unjudged count → ~0 |
| **9** | Claim directness | hearsay weighs as fact | days | a CEO's hearsay composes below the same CEO's fact |
| **10** | `REVIEW` outcome — **measured first** | recall valve | days | replaying the 68 refusals yields a count that is neither 0 nor 68 |
| **11** | **P1–P5 replay harness** | makes all of it empirical | weeks | the benchmark's third column fills |

**Steps 1–3 are days and fix measured losses. Step 4 is what changes what L1 can represent.**

---

## 3. The loop — how "better results" stops being an opinion

The request was: *always remember the expected results, and loop the reasoning to reach them.*
That only works if "better" is a number. So every step runs the same cycle:

```
      ┌─────────────────────────────────────────────┐
      │  1. MEASURE   pipeline_funnel_report.py      │
      │               on the frozen corpus           │
      └───────────────────┬─────────────────────────┘
                          ▼
      ┌─────────────────────────────────────────────┐
      │  2. PREDICT   write the expected number      │
      │               BEFORE the change              │
      └───────────────────┬─────────────────────────┘
                          ▼
      ┌─────────────────────────────────────────────┐
      │  3. CHANGE    one step, one unit at a time   │
      └───────────────────┬─────────────────────────┘
                          ▼
      ┌─────────────────────────────────────────────┐
      │  4. RE-MEASURE  same command, same corpus    │
      └───────────────────┬─────────────────────────┘
                          ▼
      ┌─────────────────────────────────────────────┐
      │  5. COMPARE   predicted vs actual            │
      │     match   → next step                      │
      │     miss    → the MODEL of the system was    │
      │               wrong; fix the understanding   │
      │               before writing more code       │
      └─────────────────────────────────────────────┘
```

### The six numbers that define "better", with today's values

| # | Metric | Today | Target | Step |
|---|---|---|---|---|
| 1 | Attachments unread | **159** | 0 | 1 |
| 2 | Columns crossing the seam | **9 of 28** | 24+ | 3 |
| 3 | Signals with a citable receipt | typed only — `relationship_change` **48 of 49 dropped** | all types above the floor | 4 |
| 4 | Events with a non-fallback domain | **8%** | target set before starting | 6 |
| 5 | Events never judged for relevance | **69 (31%)** | <5% | 8 |
| 6 | Benchmark objects present | **16 of 38** | 30+ | 11 |

**One rule for the loop:** a step whose measured number does not move is **not done**, even if its
tests are green. The four documents in this folder exist because a green suite has already hidden
each of these losses once.

---

## 4. What is deliberately not in the plan

- **JEV is wired nowhere.** It routes between engines; the engines must exist and be measured
  first. The empty routing matrix in `L1_GROUP_PLAN.md` §6 is what decides it.
- **No module is renamed.** The group names are addresses over `capture/esqe/`.
- **ALG-17's formula is untouched.** Step 8 changes what the score is compared against, never the
  arithmetic. If the distribution shape moves, that step failed.
- **No model writes a ranking number.** Confidence may route and may be stored; it may not rank.
- **The L2 admission gate** holding 114 absence-shaped situations is the largest single loss in
  the system and is **not L1's**. It belongs in the L2 plan.
