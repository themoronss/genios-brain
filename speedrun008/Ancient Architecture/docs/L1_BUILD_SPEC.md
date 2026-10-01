# Layer 1 — the build spec, wired

> Branch `speedrun008` · 2026-09-23. Written against the Gemini/Claude benchmark of 23 Sep 2026
> on `org_e97e86f858ad48b2bbf64b8a`. Every PASS/FAIL below was checked in code, with the file and
> line. Companion to `L1_ANATOMY.md` (what exists) and `L1_GROUP_PLAN.md` (the eight groups).

---

## 0. The benchmark is L1's conformance suite

The benchmark is worth more than an opinion about architecture, because every one of its findings
is a **checkable capability**. Here is the honest scoreboard — what GeniOS would do today if you
ran those five prompts.

| # | Benchmark finding | L1 capability required | Today | Where |
|---|---|---|---|---|
| 1 | **Afore ×2 + Surge never delivered** | parse mailer-daemon DSN, join to sent mail | **❌ FAIL BY DESIGN** | `gate/rules.py:359` |
| 2 | **Radhesh never emailed** (intro'd, replied to introducer only) | recipients captured, reach L2 | **❌ blocked at seam** | `envelope` not in L2's 9-column read |
| 3 | **P3/P4 at 6/12-month scope** | 540-day backfill per connection | **⚠️ capable, unproven** | `connectors/backfill.py` |
| 4 | **"we read N of M"** | indexed-vs-true-total per source | **❌ missing entirely** | `coverage/` answers a different question |
| 5 | **3one4 verbatim quote + date** | EvidenceSpan, offsets, verified | **✅ PASS — 91% on pilot** | `validate/spans.py` |
| 6 | **Stay in the stated window** | `occurred_at` stored per event | **✅ PASS** | `source_events` |
| 7 | **28 days zero outbound** (an absence) | sent mail ingested + direction | **⚠️ partial** | direction on `prepared_content`, not on the signal |
| 8 | **11 Aug template blast, 10 recipients** | identical-body detection | **⚠️ data exists, nothing asks** | `content_hash` on `qualified_signals` |
| 9 | **Median reply 18 min, bimodal** | thread turns + reply pairing | **⚠️ split across layers** | L1 has the turns, L2 computes latency |
| 10 | **4 broken commitments, days overdue** | typed commitment with `due` | **✅ PASS** | `contracts/extraction.Commitment` |
| 11 | **Conditional promises ("come back at stage Z")** | `is_conditional` + `condition_text` | **✅ field exists** | `Commitment` |

**Two PASSes, two partial-with-data, four failures.** The four failures are the whole job.

### The headline, and it is uncomfortable

The benchmark's own words: *"the highest-value finding in the whole run."* Three pitch emails on
11 Aug never reached anyone. Afore ×2 returned `550 5.1.1`, Surge permanently failed.

Layer 1 **deletes that class of mail on purpose**, twice over:

```python
# gate/rules.py:14
# Only DEAD mail is hard-dropped on the sender alone: a bounce/mailer-daemon
# carries no business signal ever.
_DEAD_SENDER = re.compile(r"(mailer-daemon|bounces?@|postmaster@)", re.I)

# :356  a DSN carries Auto-Submitted: auto-replied
if header(hdrs, "Auto-Submitted", "no") not in ("no", ""):
    return ("N-01", "drop")
# :359
if not att and machine:
    return ("N-03", "drop")
```

*"A bounce carries no business signal ever"* is **false**, and the benchmark is the proof. A bounce
is the ONLY record that a pitch did not arrive. It is not noise about a message — **it is a fact
about a message you sent**, and it is the single most expensive fact in the mailbox.

On the pilot, `N-03` dropped **82 emails**. Nobody knows how many were bounces.

> **This is the first thing to fix, and it is small.** It is one rule, one new signal type, one
> join. It is also the most demo-able thing in the entire layer: *"your pitch to Afore never
> arrived, and nobody told you."*

---

## 1. The wiring rule, before any table

Every row in every table below carries an **Engine**. Five values, and the rule for choosing:

| Engine | Use when | Never for |
|---|---|---|
| **D** deterministic | the answer is in the bytes — headers, offsets, IDs, arithmetic | anything needing meaning |
| **R** rules / ontology | a closed business vocabulary decides it, written down in advance | open-ended language |
| **M** small model | bounded classification over a closed set, high volume | anything producing a quote or span |
| **L** LLM | ambiguity, implicit meaning, cross-sentence composition | any number that orders anything |
| **J** JEV *(later)* | choosing HOW MUCH intelligence to spend on this item | replacing any engine above |

**The law:** `Inference → Validation → Commitment`. M and L may only **propose**. D and R
**validate**. Only D **commits** a number or a state.

**JEV is deliberately absent from every "now" column below.** It is a routing layer over engines
that must exist and be measured first. Routing between two unmeasured engines is guesswork with a
vendor bill attached.

---

## 2. Knowledge Connectors — get the bytes, honestly

**Job:** pull objects. Never interpret them. A Gmail connector may not say "this is important".

| # | Item | Today | To do | Engine |
|---|---|---|---|---|
| KC-1 | Backfill window | 540 days per connection (was 60) | **verify it runs** — benchmark P3 needs 6 months and nobody has proven the sweep completes | D |
| KC-2 | Sent mail | the Gmail query carries **no label filter**, so SENT is pulled | prove it: assert `direction=outbound` rows exist per tenant after a sweep | D |
| KC-3 | Webhook parity | fixed — push used to drop attachments and `mailbox_owner` | keep the parity test; it is the only thing stopping a silent re-divergence | D |
| KC-4 | Cadence + jitter | per-source, deterministic (org+connection, not entropy) | — | D |
| KC-5 | **Pagination completeness** | **NEW** — nothing records "the source said there were M, we pulled N" | a per-sync row: source, window, claimed total, fetched, cursor-exhausted yes/no | D |
| KC-6 | **Sent/received symmetry** | **NEW** — nothing asserts both sides of a thread landed | a check that every thread with an inbound has its outbound, and the reverse | D |
| KC-7 | Source registry | 36 sources, 9 buildable, 10 families | — | D |

**KC-5 is benchmark check #4 and it is a new build.** Gemini's single worst failure was claiming
18 of 18 when the true number was ~465. GeniOS cannot beat that failure without storing the
denominator, and today it stores only the numerator.

---

## 3. Event Pipeline — what happened

**Job:** every source's native shape → one canonical event. No meaning.

| # | Item | Today | To do | Engine |
|---|---|---|---|---|
| EV-1 | Landing + dedup | content / message-id / delivery, three distinct jobs | — | D |
| EV-2 | Mutability | per-source `immutable` + `version_field`; a mutable source with no version field **refuses to import** | — | D |
| EV-3 | Direction | `_envelope_direction` — inbound/outbound/internal, **refuses with None** when no rule names it | **carry it onto the signal**, not just `prepared_content` | D |
| EV-4 | Thread reconstruction | ALG-03 — `turn_index`, `reply_depth`, `last_inbound_at`, `last_outbound_at`, `ball_in_court` | — | D |
| EV-5 | **Reply pairing** | turns exist in L1; latency computed in `context/waiting.py` (**L2**) | decide the owner. The PAIR (in→out, Δt) is mechanical and belongs in L1; the *judgement* ("binary responder") is L2's | D |
| EV-6 | **Bounce / DSN as an event** | **dropped** at N-01 and N-03 | **NEW** — parse RFC 3464 delivery-status: original recipient, status code, diagnostic, and the `Message-Id` it failed | D |
| EV-7 | Visibility | stamped at source; gate parks `visibility_unknown` | — | D |
| EV-8 | Triage lane | P1/P2/P3 drain order for L2 | — | D |

---

## 4. Content Pipeline — what it says

| # | Item | Today | To do | Engine |
|---|---|---|---|---|
| CP-1 | HTML strip | at ingestion; subject is part of the prose | — | D |
| CP-2 | PII mask + offset map | masked spans, offsets preserved to the original | — | D |
| CP-3 | Quoted history | `preprocess/quoted.py` — which characters the sender did not write | — | D |
| CP-4 | **OCR** | **built, switched off.** 159 attachments parked on the pilot | **turn it on** — `GENIOS_ENABLE_OCR=true` + `GENIOS_OCR_ENABLED_ORGS`. The parked queue drains itself | D |
| CP-5 | Chunking | section-aware, offset-preserving; every chunk a literal slice | — | D |
| CP-6 | Structural tokens | ALG-04, 11 types, `source[start:end] == text` as a property test | — | D |
| CP-7 | Speech-to-text | seam built, **no provider** | descoped; transcripts arrive via P5 instead | — |
| CP-8 | Extraction | LLM-2, one call, closed schema, open lane for what it cannot name | — | **L** |
| CP-9 | Injection guard | content fencing; a payload containing the fence is escaped | keep, unchanged, for any new model site | D |

**CP-4 is the cheapest large win in the document.** 159 files, image already in the `Dockerfile`,
hours of work.

---

## 5. The eight ESQE groups, wired

### G1 · Intent Classification

| # | Item | Today | To do | Engine |
|---|---|---|---|---|
| G1-1 | Closed enums, all with `unknown` | `IntentCategory` 8 · `Tone` 8 · `Formality` 6 · `Band` 6 | — | R |
| G1-2 | Observation vs **judgement** standing | built, and correct. Judgements rank below observations | **do not touch** | R |
| G1-3 | Intent inference | rides inside LLM-2's mega-prompt | **split into its own contract** — so "intent wrong" and "extraction wrong" are distinguishable | **M** proposes |
| G1-4 | Intent↔gate disagreement | `merged_with` folds them; the disagreement vanishes | record it | D |
| G1-5 | `unknown` rate per source | **nothing counts it** | count it. 80% unknown from one source is a prompt defect | D |

### G2 · Category Identification

| # | Item | Today | To do | Engine |
|---|---|---|---|---|
| G2-1 | ALG-15 predicates over validated claims | 14 predicates, deterministic | — | D |
| G2-2 | ALG-16 precedence → one primary | constant order over 15 types | — | D |
| G2-3 | Taxonomy | **15 members**, prose says 14 | correct the prose; pin `len(SignalType)` in a test | D |
| G2-4 | **Never-fired types** | `escalation`, `anomaly`, `information_conflict`, `availability_change` fired **0 times** on 395 signals | one fixture each that MUST fire it. If none can be written, retire the member | D |
| G2-5 | **`DELIVERY_FAILURE`** | **NEW type** — a bounce is not any of the 15 | add it. This is what EV-6 produces | R |

### G3 · Importance

| # | Item | Today | To do | Engine |
|---|---|---|---|---|
| G3-1 | ALG-17 five terms | money 3000 · deadline 2500 · criticality 2000 · authority 1500 · type 1000 | **formula unchanged** | D |
| G3-2 | Org baseline | `baseline_estimated` flag exists; **nothing reads it** | act on it | D |
| G3-3 | **The measured ceiling** | every score < 4,700 / 10,000. Money term unearnable on a mailbox with no amounts; criticality pinned at `first_seen` 2000 on a 3-week graph | publish the **achievable ceiling** beside the score | D |
| G3-4 | Floor | absolute 2,500 against a scale the tenant cannot reach | relative to the tenant's measured distribution | D |
| G3-5 | Weights | injectable, must sum to 10000 | per-tenant row, with an owner and a date | R |

> **Refused:** no model writes or adjusts `importance_bp`. A model influences it only by changing
> a *validated input* — an amount, a date, an authority rank.

### G4 · Business Relevance

| # | Item | Today | To do | Engine |
|---|---|---|---|---|
| G4-1 | Rule ladder | 5 rules, first match wins, bp per rule | — | R |
| G4-2 | LLM-5 on the remainder | works; fails OPEN on transport error | — | **L** |
| G4-3 | **The budget guard** | above 10% ambiguous → **alerts instead of spending**. On the pilot **69 events (31%) were never judged** | replace on/off with an **allocator**: spend the budget on the highest-importance ambiguous items first | D allocator + L |
| G4-4 | `unjudged_for_budget` | indistinguishable from "judged relevant" | make it a first-class provenance value | D |
| G4-5 | Intrinsic vs situational | not written down | **write it into the constitution.** L1 may never read org state to judge relevance | doctrine |
| G4-6 | *(later)* | — | shadow-probe a System One classifier against LLM-5 on the same remainder | **J** |

### G5 · Source Analysis

| # | Item | Today | To do | Engine |
|---|---|---|---|---|
| G5-1 | ALG-14 authority | 0..6 table, artifact-based | — | D |
| G5-2 | Actor authority | from the graph when known | — | D |
| G5-3 | **Claim directness** | **does not exist.** A CEO's *"I heard Acme is leaving"* is indistinguishable from a CEO's first-hand statement | new field: `firsthand` / `reported` / `speculative` / `unknown`, default `unknown`, never guessed | **L** proposes, D validates |
| G5-4 | Directness → confidence | — | ALG-13 reads it; a reported claim may not compose above a firsthand one. **Rule 11's clamp already exists** | D |
| G5-5 | Directness ≠ authority | — | separate axes. Never fold into the ALG-14 table | doctrine |

### G6 · Domain Mapping

| # | Item | Today | To do | Engine |
|---|---|---|---|---|
| G6-1 | Resolver | **4 keyword regexes.** 815 of 889 events carried **no domain** — 8% recognition | — | R |
| G6-2 | **Multi-label proposal** | single, keyword-matched, usually absent | propose N domains with confidence each. *"Security questionnaire is blocking procurement"* = Sales + Security + Procurement, today it is none | **L** proposes |
| G6-3 | Ontology validation | — | every proposed domain must exist and be one this tenant runs; unknown → `proposed_unknown`, never dropped | R |
| G6-4 | Never-filter | a docstring | make it a test: a signal with all-uncovered domains still emits, degraded | D |
| G6-5 | Coverage metric | — | % of emitted events with a NON-fallback domain. Today 8%, unreported | D |

> **This is the largest gap in L1.** If only one group is rebuilt, rebuild this one.

### G7 · Lifecycle

| # | Item | Today | To do | Engine |
|---|---|---|---|---|
| G7-1 | ALG-19 state machine | `active`/`superseded`/`expired`/`resolved`, typed refusals | — | D |
| G7-2 | Supersession key | `(subject_key, signal_type)`, authority-gated, world-time ordered | — | D |
| G7-3 | **`subject_key` at the seam** | on `qualification_drops` and `signal_lifecycle`; **NOT on `qualified_signals`**. A *refused* signal remembers its subject; a *published* one does not | add the column, publisher writes it | D |
| G7-4 | **Modification vs replacement** | *"I'll send it Monday instead"* must create a new signal | model detects "this modifies", machine decides legality | **L** detects, D commits |
| G7-5 | Lifecycle visibility | nothing outside L1 reads `signal_lifecycle` | a per-tenant state report | D |

### G8 · Evidence & Qualification

| # | Item | Today | To do | Engine |
|---|---|---|---|---|
| G8-1 | ALG-08 spans | grades and **corrects** the model's offsets; forces `verified=False` on failure. **91% verified on the pilot** | — | D |
| G8-2 | V-1…V-7 | `EMIT` / `PARK` / `REJECT` — already three outcomes | — | D |
| G8-3 | Floor overrides | conflict travels · company canon travels · **unscored travels** | — | D |
| G8-4 | Drop ledger | every refusal with components + payload ref | — | D |
| G8-5 | **`REVIEW`** | missing. Low confidence + high value has nowhere to go | add as a **fourth outcome in the contract** — the contract forbids inventing one at a call site | R |
| G8-6 | Review drain | — | a queue and its drain. A REVIEW with no drain is a slower drop | D |
| G8-7 | **Measure before shipping** | — | replay the pilot's 68 floor-refused signals; count how many would become REVIEW. **68 or 0 means the thresholds are wrong** | D |

---

## 6. What is NEW versus what is a FIX

| New builds | Why |
|---|---|
| **EV-6** bounce / DSN parser | benchmark #1 — the highest-value finding in the run |
| **G2-5** `DELIVERY_FAILURE` signal type | what EV-6 produces; a bounce is none of the existing 15 |
| **KC-5** pagination completeness ledger | benchmark #4 — the denominator, so "we read N of M" is sayable |
| **KC-6** sent/received symmetry check | benchmark #7 — an absence is only safe if both sides were pulled |
| **G5-3** claim directness | first-hand vs hearsay, currently indistinguishable |
| **G8-5/6** `REVIEW` outcome + drain | the recall valve |
| **G6-2/3** multi-label domain + ontology | 8% → something real |

| Fixes to what exists | Size |
|---|---|
| **CP-4** turn OCR on | 159 files |
| **G7-3** `subject_key` across the seam | the identity L2 cannot ask for |
| **the 9-column projection** | 15 of 24 stored columns never cross |
| **G4-3** budget allocator | 69 events unjudged |
| **G3-3/4** ceiling honesty + relative floor | all 395 signals |
| **G2-3** prose 14 → 15 | correctness |
| **EV-3** direction onto the signal | benchmark #7 |

---

## 7. The step-by-step process

Each step: what, how, and **how you know it worked**. Nothing moves to the next step without its
proof.

### STEP 1 — Turn OCR on · *hours*
1. Deploy the image (already in `Dockerfile`).
2. `GENIOS_ENABLE_OCR=true`, `GENIOS_OCR_ENABLED_ORGS=<org>`.
3. Let the parked queue drain itself.

**Proof:** `DOC-06` count → 0. Parked total drops from 159 toward `DOC-02` + `DOC-05` only.

### STEP 2 — The bounce path · *days* · **the demo**
1. **Stop deleting it.** In `gate/rules.py`, a DSN is exempted from N-01 and N-03 the way
   `availability_marker` is already exempted — the pattern exists, follow it.
2. Parse RFC 3464 `message/delivery-status`: original recipient, status code, diagnostic text,
   and the `Message-Id` of the message that failed.
3. Add `DELIVERY_FAILURE` to `SignalType` — **the enum is closed, so this is a deliberate
   contract change, not a call-site addition**.
4. Join the failed `Message-Id` to the sent event. That join is the whole finding.

**Proof:** replay the tenant's 11 Aug mail. Three signals must appear —
`madison@afore.vc`, `joseph@afore.vc`, `apply@surgeahead.com` — each carrying its own sent message
as evidence. Anything less is a fail.

### STEP 3 — The seam · *days* · *(already specced as M13 in `tree.yaml`)*
1. Migration: `subject_key` on `qualified_signals` + index `(org_id, subject_key, signal_type)`.
2. `build_signal` passes `NormalizedSignal.subject_key` — it already holds the object.
3. Widen `_L1_SELECT` **and** `_L1_BY_EVENT_SELECT` together; a test asserts they select the same
   columns.
4. `context/runner.py`: replace `array_agg(...)[1]` with a per-signal join.

**Proof:** a composed situation carries domains, confidence and `occurred_at` that are not `None`;
two signals on one event each carry their own extraction.

### STEP 4 — The denominator · *days*
1. Per sync: record source, window, the total the API claimed, the number fetched, and whether the
   cursor was exhausted.
2. Expose it per source per window.

**Proof:** for a 30-day Gmail window the row reads something like `claimed 465 · fetched 465 ·
exhausted true`. **The moment those disagree, the product can say so** — which is precisely the
failure Gemini could not see in itself.

### STEP 5 — Domain mapping · *weeks* · **the biggest**
1. A model proposes N domains with confidence per domain.
2. The ontology validates each against the registered set; unknown → `proposed_unknown`.
3. The never-filter rule becomes a test.
4. Report non-fallback domain coverage per sweep.

**Proof:** the 8% moves. Pick the target before you start, and measure on the same 889 events.

### STEP 6 — The relevance allocator · *days*
1. Sort the ambiguous remainder by `importance_bp`.
2. Spend the budget top-down until exhausted.
3. Everything unspent is marked `unjudged_for_budget`, not "kept".

**Proof:** on the pilot's 69, the high-importance head gets judged and the count of silently-kept
events falls to near zero.

### STEP 7 — Importance honesty · *days*
1. Record when the money term was structurally unearnable.
2. Publish the achievable ceiling next to the score.
3. Make the floor relative to the tenant's own distribution.

**Proof:** re-run `importance_distribution.py`. The distribution shape must not change — only what
it is reported against. **If the numbers move, you changed the formula, and that is a fail.**

### STEP 8 — `REVIEW` · *days*
1. Measure first (G8-7): replay the 68 refusals, count the would-be REVIEWs.
2. Only then add the outcome to `PublicationOutcome`, in the contract.
3. Build the queue and its drain in the same change.

**Proof:** the replay count is between the two bad answers — not 0, not 68.

### STEP 9 — Claim directness · *days*
1. Field on the extraction contract, `unknown` by default.
2. Extractor proposes with a span; `validate/` resolves it like any other claim.
3. ALG-13 reads it.

**Proof:** a fixture where a CEO reports hearsay composes lower than the same CEO stating a fact.

### STEP 10 — Run the benchmark · *the point of all of it*
Run the same five prompts through GeniOS and fill the third column of that HTML page.

**Proof:** the eleven rows in §0. Today two pass. **Target: nine.** Rows 3 and 9 are honestly
part L2, so nine is the real ceiling for a Layer 1 sprint.

---

## 8. What this spec refuses

- **No working module is renamed.** The group names are addresses over `capture/esqe/`.
- **ALG-17's formula stands.** Its distribution properties are the only measured quality gate L1
  has.
- **No model writes a ranking number.** Confidence may route and may be stored; it may not rank.
- **No global boolean flags.** Every threshold is a per-tenant row with an owner and a date.
- **JEV is not wired anywhere yet.** It routes between engines; the engines must be measured
  first. §6 of `L1_GROUP_PLAN.md` holds the empty routing matrix that decides it.
