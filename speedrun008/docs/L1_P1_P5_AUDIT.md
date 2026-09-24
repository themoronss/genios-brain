# P1–P5 → L1: which semantic objects exist, which are missing, and why

> ## ⚠️ SUPERSEDED BY A MACHINE-CHECKED HARNESS, 2026-09-24
>
> This document was audited **by hand, once**. It is now scored by
> `genios_engine/capture/benchmark.py`, which runs in CI on every commit
> (`tests/golden/l1/test_the_benchmark_scoreboard_is_machine_checked.py`).
>
> **Two errors the harness found in this file on its first run:**
>
> 1. **The summary says "16 built"; the tables below show 15.** Miscounted by one, in the
>    flattering direction, and quoted into the plan as metric 6's baseline. **The correct
>    baseline is 15 built · 9 stranded · 14 missing.**
> 2. **It was already stale.** Five objects have moved since it was written —
>    `relationship_state_change` (step 8) · `coverage_denominator` (step 5) ·
>    `delivery_failure` (step 2) · `six_month_corpus` (step 5) ·
>    `final_unresolved_question` (step 4). **The live score is 20 of 38.**
>
> The tables below are kept as the transcription source and as history. **Do not quote a number
> from them** — run the harness:
>
> ```bash
> .venv/bin/python -c "from genios_engine.capture.benchmark import score_benchmark as s; r=s(); print(r.present,'of',r.total)"
> ```



> The CTO question, answered against code. Branch `speedrun008` · 2026-09-23.
> Read with `L1_BUILD_SPEC.md` (the wiring) and `L1_GROUP_PLAN.md` (the eight groups).

---

## 0. The root cause, found

`contracts/extraction.py` has **two tiers**, and nothing in the codebase says so.

**Tier 1 — typed claims. Each carries `evidence: EvidenceSpan` and `confidence_bp`:**

```
entity_mentions · amounts · dates_mentioned · commitments · decision_states
dependencies · business_facts · unclassified_observations
```

**Tier 2 — untyped bags. Each is `list[str]` or `list[dict[str, Any]]`, and therefore
*structurally cannot* carry a receipt or a confidence:**

```
topics · implied_actions · questions · roles · relationships
scheduling_proposals · availability
```

Doctrine 3 of the build record is *"no claim without a receipt."* Tier 2 cannot obey it. It is
not that these claims lost their receipts — **the type has no field to put one in.**

### And the detector fires real signals off Tier 2

`esqe/detector.py`:

| Line | Predicate | Reads | Tier |
|---|---|---|---|
| 399 | `RELATIONSHIP_CHANGE` | `ex.roles` | **2 — untyped dicts** |
| 406 | `AVAILABILITY_CHANGE` | `ex.availability` | **2 — untyped dicts** |
| 432 | *(decision predicate)* | `ex.questions` | **2 — untyped strings** |

### The causal chain, end to end, all measured

```
untyped contract
      ↓  no typed amount, no typed date, no typed authority to score on
ALG-17 has almost nothing to weigh
      ↓  measured on the pilot
relationship_change scores 880–1240 bp — the LOWEST band of any signal type
      ↓  default floor is 2500
48 of 49 relationship_change signals REFUSED
      ↓
L2 receives almost no relationship signal at all
      ↓
P1 (relationship ledger) and the Radhesh finding are unanswerable
```

**This is the mechanism behind "thin signals."** Not a missing LLM. Not an over-aggressive gate.
A contract with a second-class half, feeding a scorer that cannot see it, into a floor that eats
the result.

---

## 1. P1 · Relationship & Reciprocity Ledger

| # | Object the prompt needs | In L1? | Where | Status |
|---|---|---|---|---|
| 1 | Person identity | partial | `EntityMention` (typed) + `validate/canonical.py` ALG-11 | **⚠️** canonicalisation is a *hint*; L2 is authoritative on identity |
| 2 | Message direction in/out | yes | `_envelope_direction`, refuses with `None` when no rule names it | **⚠️** persisted on `prepared_content` only — **not on the signal** |
| 3 | Who sent last | yes | `reconstruct_thread` → `last_inbound_at`, `last_outbound_at` | **⚠️** computed in L1, not carried to the seam |
| 4 | Whose turn it is | yes | `BallInCourt{us, them, unknown}` | **⚠️** same — computed, not carried |
| 5 | Turn index / reply depth | yes | `MessageTurn.turn_index`, `reply_depth` | **⚠️** same |
| 6 | Reply latency (18 min median) | **no** | computed in `context/waiting.py` — **L2** | **❌** the *pairing* is mechanical and belongs in L1 |
| 7 | Relationship state change | yes, but | `RELATIONSHIP_CHANGE` ← `ex.roles`, **Tier 2** | **❌** 48 of 49 refused by the floor |
| 8 | Coverage (465 of 465) | **no** | `coverage_ready` answers *"is a channel connected"* | **❌** the denominator does not exist |

**Verdict:** L1 computes almost every primitive P1 needs and **hands over none of them**. Items
2–5 are derived and discarded; item 7 is derived, scored last, and dropped; item 8 was never built.

---

## 2. P2 · Commitment Ledger — *L1's strongest prompt*

| # | Object | In L1? | Where | Status |
|---|---|---|---|---|
| 1 | Commitment | **yes, typed** | `Commitment(actor, action, beneficiary, due, …)` | **✅** |
| 2 | Promisor / beneficiary | yes | `actor`, `beneficiary` | **✅** |
| 3 | Object of the promise | yes | `action` | **✅** |
| 4 | Deadline | yes | `due` + ALG-09 `dates.py` — a *range with a certainty*, not a point | **✅ strong** |
| 5 | Evidence span | yes | `evidence: EvidenceSpan`, ALG-08 corrects the model's offsets | **✅ 91% verified on pilot** |
| 6 | Signal types | yes | `COMMITMENT_MADE` 44 · `COMMITMENT_DUE` 25 fired | **✅** |
| 7 | **Fulfilment link** | **no** | nothing joins a later message to the commitment it satisfies | **❌** |
| 8 | **State** OPEN/FULFILLED/BROKEN/UNKNOWN | **no** | lifecycle has `active`/`superseded`/`expired`/`resolved` — a *generic* machine | **❌** no `FULFILLED`, no `BROKEN` |
| 9 | **Delivery failure** | **no** | bounces dropped at `gate/rules.py` N-01 and N-03 | **❌ by design** |

**Verdict:** the hardest half is built. Claude beat Gemini on P2 by finding four broken promises —
**L1 can already extract all four.** What it cannot do is say *whether they were kept*, because
nothing links a promise to its fulfilment and the state machine has no word for "broken".

---

## 3. P3 · Cold-Thread Forensics

| # | Object | In L1? | Where | Status |
|---|---|---|---|---|
| 1 | 6-month corpus | capable | `backfill.py` — 540-day window per connection | **⚠️** never proven to complete |
| 2 | Activity count (3+ messages) | yes | `thread_depth`, `turns` | **⚠️** not carried to the seam |
| 3 | Who sent last | yes | `last_inbound_at` / `last_outbound_at` | **⚠️** same |
| 4 | Silence duration | **no** | an absence. L2 has absence receipts | **❌** L1 emits no "nothing since" object |
| 5 | **Final unresolved question** | **Tier 2** | `questions: list[str]` — **no evidence, no owner, no state** | **❌** cannot be cited |
| 6 | Terminal stage | **no** | — | **❌** L2's job, but needs 2–5 to cross first |

**Verdict:** the *retrieval* half is solvable — 540 days is configured, and this is exactly the
wall Claude hit. The *representation* half is not: "the final unresolved question" is the single
most valuable object in P3 and it lives in L1 as a **bare string with no receipt**.

---

## 4. P4 · Calendar × Email

| # | Object | In L1? | Where | Status |
|---|---|---|---|---|
| 1 | Calendar event | yes | `gcal` structured mapping, `calendar_event`, mutable with `updated` | **✅ 100% pass on pilot** |
| 2 | Attendees | yes | structured mapping fields | **✅** |
| 3 | Meeting vs cohort session | **no** | every calendar event is one kind | **❌** 5 of 7 pilot events were cohort sessions where no follow-up is expected |
| 4 | Email ↔ person identity | partial | `EntityMention` + canonical hint | **⚠️** L2 authoritative |
| 5 | **Meeting → follow-up edge** | **no** | cross-source join | **❌** correctly L2's — but needs 1, 2, 4 at the seam |
| 6 | Time delta | yes | `occurred_at` on both sides | **✅** |
| 7 | Scheduling proposals | **Tier 2** | `scheduling_proposals: list[dict]` | **❌** no receipt |

**Verdict:** calendar capture is L1's cleanest source — **100% emit rate on the pilot versus
Gmail's 27%**. The join is L2's and is legitimately blocked on the seam. Item 3 is a genuine L1
gap and it is cheap: a cohort session and an investor meeting are not the same object.

---

## 5. P5 · Conditional Triggers — *the differentiator*

| # | Object | In L1? | Where | Status |
|---|---|---|---|---|
| 1 | Conditional flag | **yes** | `Commitment.is_conditional` | **✅** |
| 2 | Condition text | **yes** | `Commitment.condition_text` | **✅** |
| 3 | Condition owner | yes | `Commitment.actor` | **✅** |
| 4 | Deadline | yes | `Commitment.due` | **✅** |
| 5 | Evidence | yes | `Commitment.evidence` | **✅** |
| 6 | **Condition STATE** (met / unmet / unknown) | **no** | — | **❌** |
| 7 | **Evidence of satisfaction** | **no** | nothing evaluates a condition against later facts | **❌** |
| 8 | Refusal to guess | **yes, structurally** | `unknown` in every enum, never manufactured; `DecisionState` typed | **✅ this is the moat** |

**Verdict:** five of eight exist and the two missing ones are the *evaluation*, which needs company
state — **L2's job, correctly**. Item 8 is the important one: Gemini claimed 3one4's condition was
met by citing "$2–3k MRR" that the benchmark says was not in the source. **GeniOS cannot make that
error for a typed claim**, because schema rule S-9 rejects an extraction that stamps its own
`verified=True`, and ALG-08 resolves every span against the real characters.

---

## 6. The scoreboard

| Prompt | Objects needed | Built & typed | Built but stranded | Missing |
|---|---:|---:|---:|---:|
| P1 Relationship ledger | 8 | 1 | 4 | 3 |
| P2 Commitment ledger | 9 | 6 | 0 | 3 |
| P3 Cold threads | 6 | 0 | 3 | 3 |
| P4 Calendar × email | 7 | 3 | 1 | 3 |
| P5 Conditional triggers | 8 | 6 | 0 | 2 |
| **Total** | **38** | **16** | **8** | **14** |

**16 built · 8 stranded · 14 missing.**

That middle column is the finding. **Eight objects are computed by Layer 1 every sweep and then
dropped on the floor** — thread turns, direction, ball-in-court, activity count, last-sender
timestamps. They are not hard problems. They are already solved, and then discarded.

---

## 7. What this changes about the order of work

The diagnosis "L1 loses information between observation and qualification" is **correct**, and it
now has three separable mechanisms with different fixes:

| Mechanism | Evidence | Fix | Size |
|---|---|---|---|
| **A · The stranded eight** | thread/direction primitives computed, never carried | widen the seam — *already specced as M13* | days |
| **B · The two-tier contract** | 7 untyped bags cannot hold a receipt; 3 signal types fire off them; `relationship_change` scores 880–1240 and 48 of 49 die at the floor | **promote Tier 2 to typed claims** with `evidence` + `confidence_bp` | weeks |
| **C · Genuinely absent** | bounce/DSN, coverage denominator, commitment fulfilment state, meeting kind, condition state | build them | weeks |

**B is the new insight from this audit and it outranks most of what came before it.** Promoting
`roles`, `questions`, `availability`, `relationships` and `scheduling_proposals` to typed claims:

- gives every relationship and question a **citable receipt** — P1 and P3 become answerable;
- gives ALG-17 **typed inputs to score on**, which is why those signals sit at the bottom of the
  scale today;
- removes the doctrine violation where a predicate fires on a claim with no receipt.

It does **not** require touching ALG-17's formula, the taxonomy, or any working module. It is an
additive contract change plus the extractor's schema.

---

## 8. Revised order

| # | Do | Fixes | Measured size |
|---|---|---|---|
| 1 | **OCR on** | 159 unread attachments | hours |
| 2 | **Bounce / DSN path** | benchmark's highest-value finding, deleted by design | days |
| 3 | **Widen the seam** (M13) | the stranded eight | days |
| 4 | **Promote Tier 2 to typed claims** | 7 bags · 3 predicates · the 880–1240 band · 48 of 49 refusals | weeks |
| 5 | **Coverage denominator** | "we read N of M" | days |
| 6 | **Domain mapping** | 815 of 889 events | weeks |
| 7 | **Commitment fulfilment state** | P2's missing half | weeks |
| 8 | **Relevance allocator** | 69 unjudged | days |
| 9 | **Importance ceiling honesty** | all 395 signals | days |
| 10 | **P1–P5 replay harness** | makes all of the above empirical | weeks |

Steps 1–3 are days and fix measured losses. **Step 4 is the one that changes what L1 can
represent**, and the audit above is the argument for it.

---

## 9. What the audit does NOT support

- **"L1 over-filters."** The pilot's S1 drops were 198 bulk, 87 Gmail-Promotions, 82 no-reply —
  the funnel judges these mostly correct. The one real over-filter is `N-06`, which takes a
  first-time vendor's mail with it, plus the bounce class in step 2.
- **"L1 needs more LLM."** Of the 14 missing objects, **eleven are deterministic** — a DSN parser,
  a counter, a state field, an event-kind flag. Two need a model to propose (condition evaluation,
  relationship typing). One is L2's.
- **"Reasoning is starved because L1 is not intelligent enough."** L1 produced 395 signals, 91%
  with verified spans, 11 of 15 types firing. The starvation is at the **seam and the contract**,
  not the intelligence.
