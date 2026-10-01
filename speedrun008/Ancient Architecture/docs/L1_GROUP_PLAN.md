# Layer 1 — group by group, component by component, unit by unit

> Branch `speedrun008` · 2026-09-23. Every number here is READ from either the code or
> `docs/plans/L1_L4_PILOT_FUNNEL.md`, which itself came from
> `scripts/pipeline_funnel_report.py --org org_e97e86f858ad48b2bbf64b8a` (849 objects,
> Gmail + Calendar, 12 Aug – 8 Sep 2026). Nothing below is estimated. Where a number is
> illustrative it says so.

---

## 0. Before anything — two numbers that are NOT the same funnel

This has to be settled first, because the whole plan changes depending on which one is the neck.

```
849 captured → 225 emitted → 395 signals → 231 situations → 18 admitted → 112 candidates → 9 cards
     └──────────── LAYER 1 ────────────┘   └──────── LAYER 2 ────────┘  └──── L3/L4 ────┘
```

| Number | What it actually is | Layer |
|---|---|---|
| **367 dropped** | emails refused by the S1 noise gate — `N-02` bulk 198, `N-06` Gmail Promotions 87, `N-03` no-reply 82 | **L1** |
| **18 of 231 (8%)** | *situations* admitted to Layer 3 | **L2** |

They are four stages apart. The 367 are newsletters, promotions and no-reply mail, and the funnel
doc judges that drop **mostly correct** — the one named exception is `N-06`, which is Gmail's own
classifier and takes a first-time vendor's mail with it.

**The narrowest point in the whole system is not in Layer 1.** It is L2's admission gate, and the
single largest loss anywhere is **114 situations** of type `awaiting_response` and
`first_response_overdue` that admit at **zero percent** — because their evidence is a *silence*,
they carry no quoted span, and `verified_evidence_required` holds them every time.

### What this means for this plan

Rebuilding L1's gate for recall would not move that 114. **But L1 is still worth this work**, for
a different and provable reason: of the 395 signals L1 did publish, **every single one scored
under 4,700 of 10,000**, 69 events were never judged for relevance at all, 159 attachments were
never read, and only 9 of the 24 columns L1 stores ever reach L2. L1's problem is not that it
refuses too much. **L1's problem is that what it passes is thin.**

That is the target: **not more signals — more signal.**

---

## 1. The architecture pattern everything below obeys

The old framing was "deterministic here, model there". That is the wrong axis. The right one:

```
        RAW EVIDENCE
             │
             ▼
        INFERENCE          model / small model / rules — proposes a HYPOTHESIS
             │
             ▼
        VALIDATION         schema · closed vocabulary · ontology · evidence resolution
             │
             ▼
        COMMITMENT         deterministic score · state transition · publication gate
```

**Model proposes. Deterministic system validates and commits.** Stated as three laws:

1. **A model may propose anything; nothing it proposes is a fact until validation resolves it
   against source characters.** This is already how `validate/spans.py` works — it *corrects* the
   model's offsets rather than trusting them, and forces `verified=False` on failure.
2. **No model output ever becomes a number that orders anything.** Calibrated confidence from a
   model is an opinion that changes with the model version; `importance_bp` must replay
   byte-identical. Confidence may ROUTE (decide whether to look harder) and may be STORED as
   provenance. It may not RANK.
3. **`unknown` is a valid output and is never manufactured to satisfy a schema.**
   `contracts/intent.py` already enforces this — every enum carries `unknown`, and a missing
   intent means "do not filter on this" rather than a guess.

### The four kinds of work, and the engine each deserves

| Kind | Question | Engine | Example in L1 |
|---|---|---|---|
| **Mechanical** | what bytes are here? | deterministic, 100% | `structural/tokens.py` — 11 token types, offset round-trip is a property test |
| **Semantic** | what does this sentence mean? | model | `semantic/extractor.py` LLM-2 |
| **Judgment** | does this matter, and how much? | model proposes + rules constrain + deterministic score | `esqe/relevance.py`, `esqe/importance.py` |
| **State** | is this still true? | state machine, triggered by semantic recognition | `esqe/lifecycle.py` ALG-19 |

The mistake to avoid is not "using an LLM". It is letting the **semantic** engine write the
**judgment** number.

---

## 2. The eight groups

Numbering below is the NEW naming. The `L1.6.x` in brackets is the component that exists today, so
nothing here is a rename of a working file — it is an address for it.

| # | Group | Answers | Today | LOC |
|---|---|---|---|---|
| **G1** | Signal Intent Classification | what kind of exchange is this? | `contracts/intent.py` + extractor + `esqe/relevance.py` | ~1,400 |
| **G2** | Signal Category Identification | which business event is this? | L1.6.1 `detector.py` + L1.6.3 `classifier.py` | 1,711 |
| **G3** | Signal Importance | how big is this, intrinsically? | L1.6.7 `importance.py` + `baseline_reader.py` | 1,400 |
| **G4** | Signal Business Relevance | is this material to the business at all? | L1.6.5 `relevance.py` | 967 |
| **G5** | Signal Source Analysis | who said it, does that make it weigh more? | L1.6.4 `source_analyzer.py` + ALG-14 `authority.py` | 948 |
| **G6** | Signal Domain Mapping | which domains could this touch? | L1.6.6 `domain.py` + `domain/hints.py` | ~400 |
| **G7** | Signal Lifecycle | is it still true? | L1.6.9 `lifecycle.py` ALG-19 | 1,073 |
| **G8** | Signal Evidence & Qualification | may it leave L1? | L1.6.8 `qualification.py` + `contracts/publication.py` + `validate/spans.py` | ~2,300 |

---

### G1 · Signal Intent Classification

**Sawaal:** *what kind of EXCHANGE is this* — a vendor pitch, an interview thread, a receipt, an
escalation. Deliberately NOT the same question as G2.

**Components**

| Component | File | What it owns |
|---|---|---|
| G1.1 The intent contract | `contracts/intent.py` | `IntentCategory` (8), `Tone` (8), `Formality` (6), `Band` (6) — all closed, all with `unknown` |
| G1.2 Intent extraction | `semantic/extractor.py::_intent` | intent rides along on LLM-2's big prompt |
| G1.3 Intent merge | `MessageIntent.merged_with` | gate's reading + extractor's reading folded; "a silent extractor never erases the gate" |

**Paradigm today:** model (LLM-2), inside one mega-prompt.

**Measured evidence:** of 889 captured events, **815 carried no domain at all** — the four domain
regexes matched 8% of the mail. The intent contract was written precisely because *"the system
classified EVENTS and never the EXCHANGE"*.

**What is already right, and must not be rebuilt:** the observation-vs-judgement split. Some
fields are READ off the message and carry a receipt; others are JUDGEMENTS about what is likely,
are marked as such, rank below observations, and may never be presented as fact. That is the
Inference→Validation pattern already implemented. **Do not touch it.**

**Defect:** intent is one field inside a prompt that also asks for entities, commitments, dates,
amounts, decisions, dependencies and observations. When the answer is wrong you cannot tell
*"intent was wrong"* from *"the whole extraction was wrong"*.

**Units**

| Unit | What | Engine |
|---|---|---|
| G1-U1 | Split intent into its own contract call with its own confidence and its own evidence span — same context window, **separable contract** | small model / classifier |
| G1-U2 | An intent-vs-extraction disagreement is RECORDED, not silently merged — today `merged_with` folds them and the disagreement disappears | deterministic |
| G1-U3 | `unknown` rate per source, on the trace. If a source returns `unknown` for 80% of its mail that is a prompt defect, and nothing currently counts it | deterministic |

---

### G2 · Signal Category Identification

**Sawaal:** *which of the closed business-event types is this, primarily?*

**Components**

| Component | ALG | File | What it owns |
|---|---|---|---|
| G2.1 Detector | ALG-15 | `esqe/detector.py` (527) | a deterministic predicate table over VALIDATED claims. One event may fire several |
| G2.2 Classifier | ALG-16 | `esqe/classifier.py` | a constant precedence order picks ONE primary |
| G2.3 The taxonomy | C-11 | `contracts/signal.py` | **15 closed members** (docs still say 14 — see G2-U3) |

**Paradigm today:** fully deterministic — predicates over what the model already said. This is the
correct shape and is NOT a candidate for a model.

**Measured evidence:** 395 signals, **11 of 15 types fired**. Distribution:
`deadline_stated` 131 · `relationship_change` 49 · `opportunity_signal` 46 · `commitment_made` 44
· `commitment_due` 25 · `decision_pending` 24 · `financial_obligation` 22 · `contract_renewal` 21 ·
`approval_requested` 17 · `decision_made` 13 · `risk_flagged` 3. Never fired: `escalation`,
`anomaly`, `information_conflict`, `availability_change`.

**Defect:** four types never fire, and nothing says whether that is because the tenant had none or
because no predicate can fire them. A predicate that can never fire is indistinguishable from a
correct absence — the same class of bug the drop ledger was built to kill.

**Units**

| Unit | What | Engine |
|---|---|---|
| G2-U1 | A per-predicate fire counter on the sweep. A predicate at zero across a whole corpus is REPORTED, not assumed correct | deterministic |
| G2-U2 | For the four never-fired types, a fixture each that MUST fire them. If one cannot be written, the type is dead and should be retired from the enum, not carried | deterministic |
| G2-U3 | Correct "closed 14-member taxonomy" → 15 in `esqe/__init__.py` and the build record; add `len(SignalType)` to a test so it cannot drift again | deterministic |

---

### G3 · Signal Importance

**Sawaal:** *how big is this signal, intrinsically?* — NOT "what should be done first".

**Components**

| Component | File | What it owns |
|---|---|---|
| G3.1 ALG-17 | `esqe/importance.py` (1,184) | five weighted integer terms × an evidence-authority multiplier |
| G3.2 Org baseline | `esqe/baseline_reader.py` | the tenant's own priced history, so the money term is normalised per tenant |
| G3.3 Weights | `ImportanceWeights` | injectable; refuses a set that does not sum to 10000 |

**Paradigm today:** deterministic, integer-only, **no LLM on the call path**. Mutation-checked —
`return 5000` turns 16 tests red. **This must stay model-free.** It is the one thing in L1 that
survived a distribution gate, and a calibrated model confidence dropped in here would destroy
byte-identical replay.

**The shipped weights:**

```
money 3000 · deadline 2500 · criticality 2000 · authority 1500 · signal_type 1000  = 10000
```

**Measured evidence — and this is the most important measurement in the document:**

> Every one of the 395 signals scored **under 4,700 bp of 10,000**. The maximum on the entire
> tenant was `contract_renewal` at **4,640**. The floor at 2,500 therefore did most of the sorting,
> and 68 signals fell under it.

**Why, arithmetically:** the money term is 30% of the whole scale and this inbox carries almost no
amounts, so it contributes ~0 for nearly every signal. `entity_criticality` sits at `first_seen`
(2,000 bp) for nearly every counterparty on a three-week-old graph. So 30% of the scale is
unearnable and another 20% is pinned low — the effective range is roughly **0–5,000, not 0–10,000**,
and the tenant used all of it.

**Defect:** this is not a formula bug. It is a **cold-start** bug — ALG-17 is calibrated for a
tenant with a priced history and a populated graph, and it degrades silently rather than saying so.
`baseline_estimated` exists as a flag; nothing acts on it.

**Units**

| Unit | What | Engine |
|---|---|---|
| G3-U1 | When `org_baseline` is cold-start, RECORD that the money term was unearnable on every affected score — a component that contributed zero for a structural reason is not the same as one that contributed zero on merit | deterministic |
| G3-U2 | Publish the achievable ceiling per tenant alongside the score. A 4,640 out of a 5,000 real ceiling is a HIGH signal; presented against 10,000 it reads as mediocre, and L2/L4 read it that way | deterministic |
| G3-U3 | The floor becomes relative to the tenant's measured distribution, not an absolute 2,500 against a scale the tenant cannot reach. **The formula does not change** — only what it is compared against | deterministic |
| G3-U4 | A per-tenant importance distribution report in CI, not just at G7 gate time | deterministic |

> **Explicitly refused:** no model produces or adjusts `importance_bp`. If a model's reading should
> influence importance, it does so by changing a validated INPUT (an amount, a date, an authority
> rank), never the output.

---

### G4 · Signal Business Relevance

**Sawaal:** *is this material to the business at all?*

**Components**

| Component | File | What it owns |
|---|---|---|
| G4.1 The rule ladder | `esqe/relevance.py` | five rules, first match wins |
| G4.2 LLM-5 | `esqe/relevance.py:590` | the ambiguous remainder only |
| G4.3 The budget guard | `AMBIGUOUS_BUDGET_BP` | above 10% ambiguous share the unit ALERTS instead of spending |
| G4.4 The page batcher | `relevance_page` | one prompt for a whole page of ambiguous items |

**The ladder as shipped:**

| Rule | Verdict | bp |
|---|---|---|
| sender known in the graph | relevant | 9000 |
| `internal_kind` set (company canon) | relevant | 9500 |
| structured source (calendar, CRM) | relevant | 8000 |
| bulk headers present | **not** relevant | 500 |
| service account AND zero typed claims | **not** relevant | 800 |
| *(no rule matched)* | → LLM-5 | 6000 / 1000 |

**Paradigm today:** rules first, model for the remainder, fails OPEN on transport failure — *"this
unit says 'not business' on evidence, never on breakage"*.

**Measured evidence — the single biggest judgment hole in L1:**

> `known_counterparty` 58 · `structured_source` 50 · `bulk_headers` 46 · `llm5_not_business` 2 ·
> **`ambiguous_over_budget` 69**

**69 events were never judged by LLM-5 at all** — 31% of everything that reached L2. The guard
tripped because on a three-week-old tenant almost every sender is unknown, so the ambiguous share
blew past 10%. The doctrine is that a high ambiguous share is a *graph-coverage* problem. That
doctrine is right and its consequence is still that the component which could have said *"this is a
mass programme announcement"* never ran on a third of the traffic.

**Defect:** the guard protects cost by turning the judgment off entirely. The failure mode is
binary — either every ambiguous item is judged or none is — when the correct behaviour on a
constrained budget is to spend it on the items where the judgment would change the outcome.

**This is the one place in L1 where a System One model (Jev) has a measured, named case.** See §5.

**Units**

| Unit | What | Engine |
|---|---|---|
| G4-U1 | Replace all-or-nothing with a budget ALLOCATOR — spend the 10% on the highest-`importance_bp` ambiguous items first, and record which items were left unjudged | deterministic allocator |
| G4-U2 | `unjudged_for_budget` becomes a first-class provenance value on the signal, distinct from "judged relevant" — today both arrive as "kept" | contract |
| G4-U3 | **Write the boundary down:** *intrinsic* relevance (decidable from the signal alone) is L1's; *situational* relevance (needs the company's current state — is Acme a prospect, is there an open deal) is L2's. L1 must never reach for org state to answer G4 | doctrine |
| G4-U4 | Shadow-probe a System One classifier on the ambiguous remainder against the current LLM-5, same inputs, both recorded, nothing switched | experiment |

---

### G5 · Signal Source Analysis

**Sawaal:** *who said it, and does that make it weigh more?*

**Components**

| Component | ALG | File |
|---|---|---|
| G5.1 Provenance & actor authority | — | `esqe/source_analyzer.py` (435) |
| G5.2 The authority table | ALG-14 | `validate/authority.py` (513) — 0..6 ranks, a table not a chain of ifs |
| G5.3 Source registry | — | `source_registry.py` — 36 sources, 10 families, 9 buildable |

**Paradigm today:** fully deterministic — a lookup over metadata and artifact type.

**Defect — the one your own example names:** a CEO saying *"I heard Acme is leaving"* scores
`actor_authority = HIGH` and there is **no field anywhere for claim directness**. First-hand and
second-hand claims from the same actor are indistinguishable. Authority currently answers *who
typed it*, never *whether they witnessed it*.

**Units**

| Unit | What | Engine |
|---|---|---|
| G5-U1 | `claim_directness` on the extraction contract — `firsthand` / `reported` / `speculative` / `unknown`, with `unknown` the default and never guessed | contract |
| G5-U2 | The extractor proposes directness with its evidence span; `validate/` resolves the span like any other claim | model proposes, rules validate |
| G5-U3 | ALG-13 confidence composition reads directness — a reported claim may not compose above a firsthand one. **Rule 11's clamp already exists; this adds one input to it** | deterministic |
| G5-U4 | ALG-14's table gains no new rank. Directness is a SEPARATE axis from artifact authority and must not be folded into it | doctrine |

---

### G6 · Signal Domain Mapping

**Sawaal:** *which domains could this touch?* — tag, never route, never filter.

**Components:** `esqe/domain.py` (never-filter rule enforced) · `capture/domain/hints.py` (the
resolver) · `FALLBACK_DOMAIN` in `pipeline.py` for emitted events only.

**Paradigm today:** keyword regexes over four domains — `fundraising`, `sales`, `support`, `admin`.

**Measured evidence:**

> **815 of 889 captured events carried NO domain.** Four keyword tables recognised **8%** of a real
> mailbox. Layer 2 had nothing to select a corpus by, and the one activated corpus never spoke.

**Defect:** this is the clearest case in all of L1 where rules cannot do the job. Most mail is
ordinary sentences; a keyword table only knows the language somebody wrote down in advance. The
fallback hint was added so the 92% are not invisible — but a fallback is a placeholder, not an
answer.

**Units**

| Unit | What | Engine |
|---|---|---|
| G6-U1 | Multi-label domain proposal with confidence per domain — *"Security questionnaire is blocking procurement"* is Sales AND Security AND Procurement, and today it is none of them | model proposes |
| G6-U2 | A domain ontology validates that every proposed domain exists and is one this tenant runs; an unknown domain is recorded as `proposed_unknown`, never dropped | rules constrain |
| G6-U3 | The never-filter rule gets a TEST, not just a docstring — a signal whose domains are all uncovered must still emit, degraded | deterministic |
| G6-U4 | Domain coverage measured per sweep: what share of emitted events carry a NON-fallback domain. Today that number is 8% and nothing reports it | deterministic |

> G6 is the group with the largest gap between what it claims and what it does. If only one group
> is rebuilt, it is this one.

---

### G7 · Signal Lifecycle

**Sawaal:** *is this signal still true?*

**Components:** `esqe/lifecycle.py` (1,073) — ALG-19, an explicit transition table with typed
refusal reasons. States: `active` / `superseded` / `expired` / `resolved`.

**Paradigm today:** deterministic state machine. Supersession key is **`(subject_key, signal_type)`**,
gated by authority rank (a newer LOWER-authority signal may not supersede a higher one), ordered by
**world time**, never ingest order. This is more careful than most proposals for it.

**Defect — measured, and it is a plumbing defect, not a logic one:**

> `subject_key` has a column on `qualification_drops` (migration 0088) and on `signal_lifecycle`
> (0093) and **NO column on `qualified_signals`** (0089). A REFUSED signal records what it was
> about; a PUBLISHED one does not. Nothing in L2 reads `signal_lifecycle`. So L2 can walk a
> supersession chain by pointer but cannot ask *"give me every signal about the AWS renewal"*.

**What is genuinely missing beyond that:** an `updated` transition. Today *"Sorry, I'll send it
Monday instead"* must create a new signal that supersedes the old one. That is defensible — but the
semantic RECOGNITION that a commitment was modified rather than replaced has no owner.

**Units**

| Unit | What | Engine |
|---|---|---|
| G7-U1 | `subject_key` on `qualified_signals` + the publisher writes it. *(= M13.C1 in `tree.yaml`)* | contract + deterministic |
| G7-U2 | The extractor proposes "this modifies an existing commitment" with its span; the state machine decides whether that is a legal transition. **Model detects, machine commits** | model proposes, machine commits |
| G7-U3 | A lifecycle sweep report — how many signals are active / superseded / expired per tenant. Today nothing outside L1 can see this table at all | deterministic |

---

### G8 · Signal Evidence & Qualification

**Sawaal:** *may this leave Layer 1?*

**Components**

| Component | File | What it owns |
|---|---|---|
| G8.1 The floor | `esqe/qualification.py` ALG-18 | per-tenant `org_qualification_floors`, with an append-only change log |
| G8.2 The drop ledger | `qualification_drops` | every refusal with its components and a payload ref |
| G8.3 The publication gate | `contracts/publication.py` | V-1…V-7 |
| G8.4 Span validation | `validate/spans.py` ALG-08 | grades and CORRECTS the model's offsets |
| G8.5 Evidence binding | `semantic/evidence_binder.py` | mask→original offset alignment |

**Paradigm today:** deterministic throughout.

**What is already right:** the floor has three "travel anyway" overrides — a signal carrying a
CONFLICT travels (no score can rank a disagreement), company canon travels (it is the tenant
telling us something), and an **UNSCORED signal travels** (*"never block on a missing score"*). So
"uncertain ≠ drop" is already partly law here.

**And the outcomes are already three, not two:**

```
PublicationOutcome:  EMIT · PARK · REJECT
```

with an explicit warning in the contract that *"a fourth outcome invented at a call site would be
an emit nobody reviewed"*.

**Defect:** there is no **REVIEW** — the case of *low confidence but high value*. Today such a
signal either clears the floor and emits as though it were certain, or falls under and lands in the
drop ledger where nothing routes it to a human. `PARK` exists but means "recoverable, blocked on
something mechanical" (a missing envelope, an unfetched attachment), not "a person should look".

**Units**

| Unit | What | Engine |
|---|---|---|
| G8-U1 | `REVIEW` as a fourth `PublicationOutcome` — added IN THE CONTRACT, deliberately, because the contract forbids inventing one at a call site | contract |
| G8-U2 | The routing rule: `low confidence + high importance → REVIEW`, everything else unchanged. Both thresholds per tenant, both rows, never module constants | deterministic |
| G8-U3 | A review queue surface and its drain, on the same "held, not lost" terms the parked queue already has — a REVIEW with no drain is a slower drop | data + interface |
| G8-U4 | Measure it before shipping it: replay the pilot's 68 floor-refused signals and count how many WOULD have gone to REVIEW. If the answer is 68 or 0, the thresholds are wrong | experiment |

---

## 3. The gate, redrawn

```
                         ESQE
                           │
        ┌──────────┬───────┴───────┬──────────┐
        ▼          ▼               ▼          ▼
     EMIT        PARK           REVIEW      REJECT
   qualified   blocked on      low conf.   not a signal
        │      something        + high         │
        │      mechanical       value          │
        ▼          │               │           ▼
       QES         └───── drain ───┘      drop ledger
        │                  │                (kept, with
        ▼                  ▼                 the reason)
        L2            back into ESQE
```

Three of these four exist. **REVIEW is the only new one**, and it is new in the contract, not at a
call site.

---

## 4. The boundary to write into the constitution

| Question | Owner | Why |
|---|---|---|
| Is this intrinsically relevant? | **L1** | decidable from the signal alone |
| Is this relevant GIVEN the company's current state? | **L2** | needs the graph — is Acme a prospect, is there an open deal |
| How significant is this signal? | **L1** `importance_bp` | intrinsic attributes |
| How severe is this situation? | **L2** | several signals together |
| What should be done first? | **L4** `decision priority` | needs expertise |

The rule that enforces it: **L1 may never read org state to make a judgment.** The moment
`esqe/relevance.py` reaches for the graph to ask "is this account strategic", the two layers have
merged and neither can be tested alone.

---

## 5. Where a System One model (Jev) actually belongs

Not as a replacement for any engine. Two named slots, both measured:

| Slot | Case | Evidence |
|---|---|---|
| **G4 budget allocator** | 69 events unjudged because the ambiguous share blew a 10% budget. At $0.042/MTok input and free output, that budget is a different number | `ambiguous_over_budget` 69 |
| **LLM-1 junk gate** | the gate asks a generative model for a float confidence; the parse default of 0.5 put **33 of 109 deleted emails** at a confidence the model never gave | `gate/relevance.py` |

**Where it is forbidden:** LLM-2 (needs string generation — quotes, spans, surface forms, the open
lane), and any scoring (doctrine 2 above).

**Four things it must satisfy before it touches the capture path:** integer-bp at the adapter edge
(V-7 rejects floats); a pinnable model snapshot in the cache key (or replay dies); a row in
`llm_costs` with a new `purpose` (`tests/test_every_llm_call_site_is_metered.py` fails both ways);
and the existing prompt fencing (`semantic/injection.py`) unchanged.

---

## 6. What to measure before building any of it

Every unit above is a hypothesis. The corpus is how they stop being hypotheses.

**The gold corpus.** Real tenant data, not synthetic. Today's golden set is **8 messages against
the 30 the spec asks for** — that is the first thing to fix, and it is cheap.

| Slice | Count | Annotate |
|---|---|---|
| email | 300 | intent · category · domains · entities · relevance · directness · importance band |
| calendar | 50 | same |
| documents | 50 | same + whether OCR was needed |
| transcripts | 25 | same + speaker attribution |

**The routing matrix** — run four systems over the same corpus and fill this in with MEASURED
numbers. The table below is the SHAPE; every cell is currently empty:

| Operation | Rules | Small model | LLM | Winner |
|---|---|---|---|---|
| date extraction | ? | ? | ? | ? |
| entity extraction | ? | ? | ? | ? |
| explicit intent | ? | ? | ? | ? |
| implicit intent | ? | ? | ? | ? |
| domain mapping | ? | ? | ? | ? |
| claim directness | ? | ? | ? | ? |
| business relevance | ? | ? | ? | ? |

Measure precision, recall, calibration, evidence grounding, cost and latency per cell. **Then** the
architecture is a reading of a table rather than an argument.

**Classify every failure**, so the corpus teaches something: `F01` lexical ambiguity · `F02` missing
context · `F03` cross-sentence · `F04` cross-source · `F05` domain knowledge · `F06` entity
ambiguity · `F07` contradiction · `F08` temporal · `F09` conditional · `F10` taxonomy ambiguity ·
`F11` insufficient evidence · `F12` hallucination · `F13` rule-coverage gap · `F14` ingestion
failure.

---

## 7. The order I would do this in

Ranked by measured size of the thing it fixes, not by how interesting it is.

| # | Do | Fixes | Size | Effort |
|---|---|---|---|---|
| **1** | Turn OCR on — the image is built (`Dockerfile`); deploy, then `GENIOS_ENABLE_OCR=true` + `GENIOS_OCR_ENABLED_ORGS` | 159 attachments never read | **159 files** | hours |
| **2** | G7-U1 — `subject_key` across the seam, and widen the 9-column projection | everything L1 concluded reaching L2 | 15 of 24 columns | *already specced as M13* |
| **3** | G6 — domain mapping from 8% to something real | L2 has nothing to select a corpus by | **815 of 889 events** | weeks |
| **4** | G4-U1 — budget allocator instead of an on/off guard | judgment never ran | **69 events (31%)** | days |
| **5** | G3-U1..U3 — cold-start honesty and a relative floor | every score capped at 4,640/10,000 | **all 395 signals** | days |
| **6** | G8-U1..U4 — REVIEW as a fourth outcome, measured first | low-confidence high-value signals | 68 refused | days |
| **7** | The gold corpus 8 → 425 | every hypothesis above | — | weeks |
| **8** | G5 — claim directness | second-hand claims weigh as first-hand | unmeasured | days |

**Not on this list, deliberately:** the L2 admission gate holding 114 absence-shaped situations.
It is the largest single loss in the system and it is **not L1's**. It belongs in the L2 plan, and
it should probably be done before most of this — but doing it inside L1 would put the layer
boundary back where this whole document argues it should not be.

---

## 8. What this plan refuses to do

- **No working module is renamed.** The eight groups are addresses over `capture/esqe/`, not a
  reorganisation of it.
- **ALG-17's formula is not touched.** G3 changes what the score is COMPARED against and what is
  recorded alongside it. The formula, its five weights and its distribution properties stand.
- **No model writes a number that orders anything.** Confidence may route and may be stored. It may
  not rank.
- **No global boolean flags.** Every threshold introduced here is a per-tenant row with an owner
  and a date, because the codebase has already been burned by `use_domain_compiler` — 152 authored
  capabilities that never influenced one customer-visible recommendation.
