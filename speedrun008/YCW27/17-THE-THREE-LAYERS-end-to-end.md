# 17 · LAYERS 1, 2 AND 3 — END TO END

> **Written for** Harsh, and any coding agent picking this repo up cold.
> **Date** 2026-10-01 · **Branch** `speedrun008` · **Suite** 14,599 passed · 0 failed
> **Every number in this document was measured on 2026-10-01**, read-only, against production.
> Nothing here is estimated. Where something is unknown it says so.

---

# PART 0 · READ THIS FIRST, OR THE REST WILL MISLEAD YOU

## 0.1 · The layer numbers are not the data flow

There are **four** layer vocabularies in this repo and `genios_engine/LAYERS.py` is the only
place they are reconciled. This document uses the **PRODUCT** column, which is how the product is
described to a founder, and which is what the `speedrun008/YCW27/layer-N-*` folders are named
after.

| PRODUCT | Name | Package(s) | Files | Lines |
|---|---|---|---|---|
| **L1** | Enterprise Signals | `capture/` | 157 | 47,046 |
| **L2** | Signals Qualification (signals + domain expertise = reasoning) | `packs/` + `reason/` + part of `context/` | 154 | 49,282 |
| **L3** | Context Graph | `context/` | 123 | 50,725 |
| L4 | Executive | `executive/` | 27 | 6,167 |
| L5 | Delivery | `deliver/` | 40 | 9,431 |
| L6 | Learning | `feedback/` | 13 | 3,008 |

⛔ **The data does not flow L1 → L2 → L3. It flows L1 → L3 → L2 → L4.**

    capture (L1)  ──►  context/graph (L3)  ──►  context/situations (L3)  ──►  packs + reason (L2)  ──►  executive (L4)

A signal is captured, written into the graph, assembled into a situation, and only then reasoned
about. **Reasoning is downstream of context, always** — you cannot apply domain expertise to a
thing until the thing has been assembled. The PRODUCT numbering puts Reasoning at 2 because that
is the order a founder cares about ("what do you do with my data" before "where do you keep it"),
not the order the bytes move.

Every build in this programme has followed the **data flow**, never the numbering. That is the
single rule that has kept the work buildable: you cannot verify a situation reasoner before
situations exist.

## 0.2 · Two packages span two product layers, and that is deliberate

`LAYERS.py` records this explicitly, because reading a package boundary as a layer boundary is how
a card once came to be wired to a signal while the situation layer was bypassed entirely:

- **`context/` spans PRODUCT L2 and L3.** It holds the graph (L3) *and* it assembles and admits
  situations (part of L2's job).
- **`reason/` spans PRODUCT L2 and L4.** `domain_shadow.py` is expertise reasoning (L2);
  `runner`/`composer`/`store` choose an action (L4).

So "Layer 2" is not a folder. It is a **job** — turn an assembled situation into a judged decision
— and three packages do parts of it.

## 0.3 · `packs/` and `reason/` are planes, not stages

They have no pipeline position. They are what `context/` reasons **with**, consulted rather than
passed through.

- **Plane D — Domain Expertise** (`packs/` + the `Domain Expertise/` corpus): *what a professional
  knows.* 155 capabilities, 69 situations, 3 domains, authored as YAML by humans.
- **Plane R — Reasoning Units** (`reason/reasoners/`): *how a professional thinks.* 23 units —
  17 core + 6 supplementary — each a deterministic function over a situation.

A digit on either would imply sequence. `LAYERS.py` gives them 3 and 4 only because
`tests/test_layer_topology.py` reads that dict to enforce import direction: **a package may import
same-or-lower only, and a build fails on an upward import.** The number is an import rule, not a
claim about order.

## 0.4 · The rule that makes the whole thing hold

    tests/test_layer_topology.py       a package may import same-or-lower layers ONLY
    contracts/                         may import platform and stdlib. NOTHING else.

That second line is why the seam objects in PART 3 are trustworthy. A contract that could import
`context/` would let graph logic leak into the thing that crosses the boundary, and then the
boundary is a suggestion. It cannot, so it is not.

---

# PART 1 · WHAT EACH LAYER IS

## L1 · Enterprise Signals — `capture/` · 157 files · 47,046 lines

**Job:** read the outside world and normalise it. **Zero reasoning.**

**In:** connector payloads — mail, calendar, documents, CRM, finance.
**Out:** `QualifiedEnterpriseSignal` (contract C-12), plus an explicit record of everything that
did *not* qualify and why.

**What it must never do:** decide anything. L1 answers "what happened and can we see it", never
"does it matter". The moment L1 forms an opinion, every layer above inherits it with no way to
re-ask.

**Its own sub-stages, in order:**

| | Stage | Module | What it produces |
|---|---|---|---|
| 1 | intake | `capture/intake.py` | `raw_payloads` — the bytes, untouched |
| 2 | normalize | `capture/esqe/normalize.py` | `source_events` — one typed event |
| 3 | extract | `capture/structured/` | typed claims — commitments, deadlines, decisions |
| 4 | coverage | `capture/coverage/` | **can we even see this domain?** `coverage_ready` + 5 readiness predicates |
| 5 | qualify | `capture/esqe/publisher.py` | `qualified_signals`, or a row in `qualification_drops` |
| 6 | trace | `contracts/trace.py` | `event_trace` — the backwards join, keyed `(org_id, event_id)` |

**The coverage stage is the one most people miss.** Before L1 qualifies anything it asks whether
the tenant has connected the tools this domain is *defined* to need. If not, **no negative
inference is licensed** — "they did not reply" is only a fact if we could have seen a reply.

## L3 · Context Graph — `context/` · 123 files · 50,725 lines

**Job:** hold what is true, and assemble situations from it. Named **Situation Intelligence**, not
"Context Intelligence", because its output is a *situation* — not a graph.

**In:** `GatedEvent` / `QualifiedEnterpriseSignal` from L1.
**Out:** `BusinessSituationObject` (the BSO) — but **only if admitted.**

**Two halves:**

1. **The graph.** `graph_nodes` (who/what), `graph_facts` (what is true, with a source ref per
   fact), `graph_edges` (how they relate), `graph_source_refs` (the receipt — which signal
   asserted this), `graph_observations`.
2. **Situations.** 10 correlator modules (~5,234 lines) read the graph and propose situations;
   **eight admission laws** judge each one; `situation_admission_decisions` records every verdict.

**The confidence vector lives here.** Seven axes now (PART 5), each of which may honestly have
**no basis**, and `overall_bp` is **bounded by the weakest axis that went into it**. Composition is
otherwise a machine for manufacturing certainty: several weak axes agreeing is not corroboration,
and a mean over them produces a number larger than anything it was computed from.

## L2 · Signals Qualification — `packs/` + `reason/` + part of `context/` · 154 files · 49,282 lines

**Job:** apply domain expertise and deterministic reasoning to an admitted situation, and emit a
judged decision with its receipts.

**In:** `BusinessSituationObject` + `ContextSnapshot`.
**Out:** `ReasoningDecision`, with `reasoning_candidates`, `reasoning_reasoner_results` and a
`CritiqueVerdict` where a second pass ran.

**The two planes:**

- **Plane D** reads the authored corpus. A *situation* in the corpus says "this is the shape of
  thing that is happening"; a *capability* says "and here is what a professional does about it".
  `capability_resolver` maps one to the other through each domain's
  `registry/situation-capability-map.yaml`.
- **Plane R** runs 23 units over the situation. Each unit is deterministic, each writes its own
  result row, and **each may decline** — a unit with no basis returns `None` rather than a number.

**⛔ Where a model may and may not run.** The 23 units are deterministic. An LLM may run in L2 only
at the *composition* seam (`reason/bundle/prompt.py`, `l2_model_runs`) and never inside a unit: a
unit that called a model would stop being replayable, and a stored decision that cannot be
recomputed from its own inputs is not a decision, it is a memory.

---

# PART 2 · THE DATA FLOW, TRACED ON ONE REAL EMAIL

This is the whole system in one path. Every stage names the table it writes.

    ┌─ L1 · capture/ ─────────────────────────────────────────────────────────────────┐
    │                                                                                  │
    │  a vendor emails "invoice 4471 is 8 days overdue"                                │
    │                                                                                  │
    │  1. intake        raw_payloads          the bytes, stored before anything reads  │
    │                                         them. A parser that crashes still leaves │
    │                                         the evidence behind.                     │
    │  2. normalize     source_events         one typed event: source, occurred_at,     │
    │                                         subject_key, object_type, signal_type     │
    │  3. extract       (in the event)        a typed Commitment with `due` = a date,   │
    │                                         lifted to `due_at` so it can be SORTED.   │
    │                                         A claim nested in an extraction cannot be │
    │                                         swept by any query.                       │
    │  4. coverage      source_coverage       admin requires [finance, communication].  │
    │                                         ⛔ `finance` is not connected →            │
    │                                         coverage_ready = FALSE                     │
    │  5. qualify       qualified_signals     importance_bp vs the floor. Above → a      │
    │                   qualification_drops   C-12 signal. Below → a DROP ROW that       │
    │                                         records the floor, the score and the       │
    │                                         components. A drop is a measurement.       │
    │  6. trace         event_trace           keyed (org_id, event_id) — the join a      │
    │                                         human follows backwards from any card.     │
    └──────────────────────────────────────────────────────────────────────────────────┘
                                          │
                        QualifiedEnterpriseSignal  (contracts/signal.py:302)
                                          ▼
    ┌─ L3 · context/ ─────────────────────────────────────────────────────────────────┐
    │                                                                                  │
    │  7. graph write   graph_nodes           the vendor becomes a node                 │
    │                   graph_facts           "invoice 4471 is unpaid" becomes a FACT   │
    │                   graph_source_refs     …with a ref to the signal that said so    │
    │                                         ⛔ 36,599 source refs for 6,253 facts —    │
    │                                         a fact with no ref is unfalsifiable        │
    │  8. correlate     context_correlation_  10 correlators read the graph and propose  │
    │                   members               candidate situations                       │
    │  9. assemble      context_situations    the BSO: entities, timeline, evidence,     │
    │                                         importance, the confidence vector          │
    │ 10. score         (on the row)          7 axes. `overall` = min of the COMPOSED    │
    │                                         ones. coverage/analytic/readiness are      │
    │                                         REPORTED beside it, not composed.          │
    │ 11. admit         situation_admission_  EIGHT laws. Every verdict recorded,         │
    │                   decisions             including the refusals. 4,727 rows.         │
    └──────────────────────────────────────────────────────────────────────────────────┘
                                          │
                        BusinessSituationObject  (contracts/situation.py:593)
                          + ContextSnapshot      (contracts/reasoning.py:414)
                                          ▼
    ┌─ L2 · packs/ + reason/ ─────────────────────────────────────────────────────────┐
    │                                                                                  │
    │ 12. type it       (the BSO's own type)  `admin.sit.obligation_falls_due`          │
    │ 13. Plane D       reasoning_capability_ the corpus says which CAPABILITY answers   │
    │                   snapshots             this situation type. ⛔ TWO GATES: the      │
    │                                         situation must be `identity.status =       │
    │                                         stable` AND `review_status = approved`,    │
    │                                         or it cannot instruct.                     │
    │ 14. Plane R       reasoning_reasoner_   23 units run. Each writes its own row.     │
    │                   results               Each may DECLINE. 42,980 rows.             │
    │ 15. candidates    reasoning_candidates  scored options, with score_components.      │
    │                                         34,232 rows. ⛔ Never a neutral 5000.       │
    │ 16. critique      (CritiqueVerdict)     a targeted SECOND pass where one is owed    │
    │ 17. decide        reasoning_runs        one ReasoningDecision. 12,170 runs,         │
    │                   reasoning_run_outputs 100% completed.                             │
    └──────────────────────────────────────────────────────────────────────────────────┘
                                          │
                        ReasoningDecision  (contracts/reasoning.py:1393)
                                          ▼
                       L4 executive/ → L5 deliver/ → cards → L6 feedback/

## The seam contracts, named

Each is in `contracts/`, which may import **platform and stdlib only** — that is what makes them
boundaries rather than suggestions.

| Seam | Contract | Where |
|---|---|---|
| connector → L1 | `GatedEvent` | `contracts/gated_event.py:50` |
| **L1 → L3** | `QualifiedEnterpriseSignal` | `contracts/signal.py:302` |
| L1 → L3, batched | `QualifiedEnterpriseSignalBundle` | `contracts/signal.py:1016` |
| **L3 → L2** | `BusinessSituationObject` | `contracts/situation.py:593` |
| L3 → L2, the read | `ContextSnapshot` | `contracts/reasoning.py:414` |
| L2 input | `ReasoningRequest` | `contracts/reasoning.py:728` |
| **L2 → L4** | `ReasoningDecision` | `contracts/reasoning.py:1393` |
| L2 second pass | `CritiqueVerdict` | `contracts/reasoning.py:1833` |
| Plane D | `ExpertisePackage` | `contracts/domain_expertise.py:766` |
| evidence gap | `EvidenceNeed` | `contracts/evidence.py:213` |
| L4 → L5 | `DeliveryObject` / `DeliveryDecision` | `contracts/delivery.py:390` / `:161` |

⛔ **`SituationSeed` does not exist.** The Atlas names it; it has zero hits in the code. It is the
one seam contract from the Atlas that was never built, and nothing currently needs it — situations
are proposed by correlators reading the graph, not seeded. Recorded so nobody looks for it.

---

# PART 3 · THE PRODUCTION FUNNEL, MEASURED

Read-only against production, 2026-10-01. **Every number is a count, not an estimate.**

## 3.1 · The funnel

    L1  raw_payloads                    3,969      bytes stored before anything parsed them
        source_events                   7,085      normalised typed events
        event_trace                    91,000 rows / 63,327 distinct events traced
          │
          ├─ qualified_signals            555      ⛔ reached the C-12 contract
          ├─ qualification_drops           552      scored BELOW the floor — recorded, not lost
          └─ parked_events               2,555      1,662 pending · 874 dead_letter · 19 recovered

    L3  graph_nodes                        570
        graph_facts                      6,253
        graph_edges                        780
        graph_source_refs               36,599      ⛔ ~6 refs per fact. A fact with no ref is
                                                    unfalsifiable, so every fact carries its source
        graph_observations               1,805
        context_situations                 459      ⛔ assembled AND admitted
        situation_admission_decisions    4,727      every verdict, including the refusals
        situation_interpretations        3,818
        metric_history                   2,514
        baselines                          537

    L2  reasoning_runs                  12,170      ⛔ 100% status = completed
        reasoning_context_snapshots     12,170      one per run — the read is stored, not re-read
        reasoning_run_outputs           12,170
        reasoning_candidates            34,232
        reasoning_candidate_checks      40,580
        reasoning_reasoner_results      42,980
        reasoning_evidence_digests      26,675
        reasoning_capability_snapshots   8,681
        expertise_packages               1,149
        l2_model_runs                      796      the ONLY place a model ran in L2

    L4/L5  cards                           165      150 expired · 9 queued · 6 surfaced
           by domain: admin 84 · general 59 · sales 14 · customer_support 7 · verify 1
           execution_events               1,022 · execution_actions 794 · escalations 466

## 3.2 · What the funnel actually says

**555 of 7,085 events qualified (7.8%).** That is not a leak — it is the floor doing its job.

⛔ **The drops were not borderline.** 552 drops, average floor **2,500 bp**, average importance
**1,251 bp** — they scored **half** the floor, not just under it. So the floor is not the
bottleneck, and lowering it would admit noise rather than recover signal. The drop reasons by type:

    relationship_change  237      commitment_made  131      opportunity_signal  51
    deadline_stated       47      decision_pending  27      decision_made       19

**The biggest loss is the parked queue: 1,662 pending.** Previously decomposed —
`low_relevance` 709, `DOC-06` 598, `DOC-05` 148, `DOC-02` 78, `poison_quarantine` 69,
extraction/model failures 60. **824 of them are `drain.NEEDS_REFETCH`** — attachment stubs whose
bytes never existed, and whose only fix is the OCR deploy (Harsh's H2). The drain *declines* to
re-inject them rather than "report work that did not happen", which is correct.

**L2 has zero incomplete runs.** 12,170 runs, 12,170 completed. The reasoning layer is not where
anything is stuck.

**⛔ 150 of 165 cards are expired and only 6 are surfaced.** That is the end of the funnel, and it
is the honest consequence of a pipeline running over a queue that has been starved since the
OCR deploy did not land. Cards expire on a window; a window with no new input expires everything
in it.

## 3.3 · Per-unit run counts, Plane R

    2,681 runs   core.alternative · core.temporal · core.planning · core.priority
                 core.constraint · core.validation · core.confidence                    (7 units)
    1,973 runs   core.risk · core.opportunity · core.dependency · core.cost
                 core.recommendation · core.timeline · core.scheduling · core.impact
                 core.resource · core.tradeoff · core.context                          (11 units)
      929 runs   core.relationship        ⛔ 929 runs, ZERO completions — needs H5
      708 runs   legacy.rule · legacy.score_gate                                        (2 units)
      165 runs   core.policy
        0 runs   core.signal_composition  ⛔ has NEVER run — needs roster activation

That is 23 units. **Two of them are silent for reasons with named movers**, and both are declared
in `reason/unit_health.py` rather than left to be rediscovered.

## 3.4 · The corpus, Plane D

    domain              capabilities   situations
    admin                        59           34      ⛔ the ONLY activated domain
    customer_support             49           20      on hold
    sales                        47           15      on hold
    TOTAL                       155           69

    situations that CANNOT instruct              20   (was 23 before 2026-10-01)
    admin situations still `draft`                 4   all four DECLARED `pending_l2_types`

**All 155 capabilities are admissible.** The gap has never been the capabilities — it is situations
whose lifecycle is held at `draft`, so the card cannot instruct even though the content is written.

⛔ **Four of Admin's remaining drafts are held ON PURPOSE.** They are declared in
`Domain Expertise/Admin Expertise/registry/situation-capability-map.yaml` under `pending_l2_types`, and
`tests/packs/test_the_corpus_states_its_own_health.py` says in its own words that they **MUST NOT
be flipped** — the L2 type each one needs does not exist yet, and one records that flipping it
*"would cost a false assurance"*. **This is not pending work for anybody.**

## 3.5 · Situation types actually forming

    analytic_movement        60      awaiting_response        47
    meeting_follow_through   42      channel_touch            42
    first_response_overdue   37      dependency_stated        35
    account_admin            32      condition_in_review      23

⛔ **`first_response_overdue` has formed 37 times with ZERO predicates declared.** That is not a
bug. `ContextAdapter.matches(())` returns `PredicateState.TRUE` — an empty `when` is **vacuously
true**, so the situation matches on its L2 type **alone**. It is the *most* permissive form, not
the least. This was once reported backwards ("no predicate — can never fire") and the data had
already refuted it.

---

# PART 4 · WHAT WAS DONE, LAYER BY LAYER

Every step below followed the same four-beat shape, and **never skipped a beat**:

    1. CROSSCHECK   measure what is actually there. Never inherit a claim, not even our own.
    2. PLAN         write the units down, with the verify command FIRST
    3. BUILD        bottom-up. Never a parent before its children are green.
    4. VERIFY       run it, read the output. A skip is not a pass.

## 4.1 · L1 · Enterprise Signals

| | Step | What it was | Outcome |
|---|---|---|---|
| L1-1 | claim-by-claim Atlas verification | the Atlas's badges ("built" / "target" / "gap") were the whole build order, and **1 of the first 3 spot-checked was wrong** | corrected baseline. Several "gaps" were already built: coverage receipts, absence machinery, `ReasoningRequest`, `ContextSnapshot` |
| L1-2 | the coverage declaration | `GatedEvent.coverage_ready` was `None` on **100% of events ever produced**, because nothing passed a `coverage_fn` | wired. `source_coverage` now carries a row per (org, domain) |
| L1-3 | pipeline counters | the five-stage funnel (`signals_detected` → … → `card_delivered`) did not exist | `platform/funnel.py`. ⛔ `signals_detected` is **deliberately left unwritten** — it belongs to `capture` and nothing there writes it yet, and a wrong number where a missing one belongs is worse than a gap |
| L1-4 | output lanes | the five lanes (decision/investigation/conflict/monitor/suppress) did not exist | built, migration `0189` |
| L1-5 | **audit E** — the host-measuring test | a verify that only ran on one machine was being read as a product property | ⛔ **doctrine: a test that leaves one prerequisite to the host is not asserting a product property** |
| L1-6 | **audit CA3** — the parked queue | was there a code gap behind 1,662 parked rows? | **ZERO code gap.** The distribution sums exactly and 824 are `NEEDS_REFETCH` awaiting a deploy. **Nothing was built, and that is the finding** |

## 4.2 · L3 · Context Graph

| | Step | What it was | Outcome |
|---|---|---|---|
| L3-1 | crosscheck the corpus | believed to be empty | **155 capabilities, ALL admissible.** The gap was situations held at `draft`, not missing content |
| L3-2 | the two-gate ceremony | `situation_admission_reason` requires **both** `identity.status == stable` **and** `metadata.review_status == approved` | pinned by test. A situation with approved content and a draft lifecycle **cannot instruct**, and that is correct |
| L3-3 | the review queue | 18 situations needed review, and the first pass asked Rohit **18 engineering questions dressed as product questions** | ⛔ taken back. 18 collapsed to **3** real product decisions. `scripts/dx_review_queue.py` generates the queue offline, MD + HTML |
| L3-4 | three situations accepted | `campaign_awaiting_reply`, `condition_awaiting_review`, `organization_gone_quiet` | **live.** Both gates flipped together, each file records why, and ⛔ **checked against `pending_l2_types` BEFORE the flip — zero overlap.** That check is the whole safety of the edit |
| L3-5 | **ALARM D-A2 retracted** | 5 situations reported as "one-word edits waiting on a human" | ⛔ **wrong.** All 5 are declared `pending_l2_types` and the repo's own test says MUST NOT flip. The validator was crying wolf on 5 correct files. Warnings 40 → 35, false warnings 5 → 0 |
| L3-6 | the empty-`when` correction | 10 situations labelled "NO PREDICATE — can never fire" | ⛔ **exactly backwards.** `matches(())` returns TRUE. They are the **most** permissive |

## 4.3 · L2 · Signals Qualification — both planes

| | Step | What it was | Outcome |
|---|---|---|---|
| L2-1 | prove the claims | 17 core + 6 supplementary units; the 6 have **no `unit_id` class attribute** | identified by `spec.reasoner_id` on an **instance**. An earlier helper read class names and manufactured "6 units never ran" when 5 had run thousands of times |
| L2-2 | the silence receipt | a unit that runs and produces nothing was indistinguishable from one nobody called | `reason/unit_health.py` — **four grains** of declared silence: `DeclaredSilence`, `UnwrittenFact`, `ClosedDefect`, `NeverCompleted` |
| L2-3 | **audit D** — the frozen-formula receipt | 59 candidates scored a neutral 5000 on impact AND risk AND effort | closed at boundary `2026-09-08`, **34,167 clean since**. ⛔ The receipt reads the boundary from a **function**, so it cannot copy the date and go stale |
| L2-4 | the third silence | `core.relationship`: 929 runs, 0 completions. `core.signal_composition`: 0 runs | `NeverCompleted` refuses `runs <= 0` at construction, so a never-called unit cannot be mis-filed as a never-completing one. ⛔ **doctrine: a unit that never completes is not a quiet unit; it is an absent one** |
| L2-5 | **ALARM A6 retired** | an alarm claiming a defect in `priority.py` | ⛔ **all three of its claims were false**, and its proposed fix would have **broken the designed derived branch**. Retracted in place with the measurement; 6 tests pin the real behaviour |
| L2-6 | **audit CA2** — the lost-axis reader | `cost_vs_benefit` had fired **0 times in 1,973 runs** | `scripts/l2_tradeoff_axes.py`. Root cause: a single missing `deal.status` writer (Harsh's H4). Axis counts 0:16 · 1:929 · 2:1,028 · 3:**ZERO** |
| L2-7 | decision #1 closed | the Atlas wanted 6 different ConfidenceVector axes; only 2 of 6 overlapped | **option A** — keep the code's axes, correct the Atlas. `frame_bp`/`causal_bp` have **0 references**; `authority_bp` means three different things in three places |
| L2-8 | **the readiness axis** (PART 5) | Atlas cell L2-07 survived decision #1 | U1 + U2 built, U3 blocked on H1, U4 is a product decision |

## 4.4 · The nine times a state was called a defect before it was counted

This is the most important thing in this document for anyone continuing the work. **Nine times in
this programme a finding was wrong, and it was wrong the same way each time: a state was named a
defect before the declaration that created it was read.**

| | What was claimed | What was true |
|---|---|---|
| 1 | "nothing is frozen" | the defect is defined by *coincidence*; measuring axes independently missed it. The conjunction showed exactly **59** |
| 2 | "the folder names are wrong" | `LAYERS.py` documents **four** vocabularies and the collision |
| 3 | "6 registered units never ran" | 5 had run thousands of times; the id helper read class names |
| 4 | "a 6-axis comparator has never compared 6" | the probe read the *source key* as the axis name |
| 5 | "`core.cost` is an undeclared cause" | it publishes `effort_bp` on **1,973 of 1,973**. Absence was inferred from a declaration list |
| 6 | "every manifest sets this key" (ALARM A6) | `core.confidence` ships with the key **absent** |
| 7 | "5 situations are one-word edits waiting on you" (D-A2) | all 5 are declared `pending_l2_types` and MUST NOT be flipped |
| 8 | "10 situations can never fire" | `matches(())` returns TRUE — they are the **most** permissive |
| 9 | "authored corpora are mis-assessed" (F-2) | ⛔ **zero authored domains exist.** Latent, not live |

> **A declaration list answers "is this absence declared". It never answers "is there an absence."**
> Measure the thing. Then read what somebody already said about it. In that order.

---

# PART 5 · WHAT EACH LAYER SHOULD PRODUCE, AND WHAT IT PRODUCES NOW

## 5.1 · L1 — Enterprise Signals

**Expected after L1:** every connector event is either a `QualifiedEnterpriseSignal`, a recorded
drop with its floor and components, or a parked row with a reason — and **nothing is silently
lost.** Plus: an honest answer to "could we even see this domain", per (org, domain).

**What you get now:**

    ✅  555 qualified · 552 drops recorded with floor+components · 2,555 parked with reasons
    ✅  63,327 events traced, keyed (org_id, event_id) — backwards-navigable from any card
    ✅  source_coverage: a row per (org, domain), 4 domains × 3 orgs
    ⛔  1,662 parked pending, 824 of them awaiting ONE deploy (H2)
    ⛔  141 of 555 signals carry `coverage = 0` meaning "we looked and found nothing"
        when the truth is "nobody ever assessed it"           ← F-3, see 5.4

## 5.2 · L3 — Context Graph

**Expected after L3:** a graph where every fact carries the signal that asserted it, and a set of
situations each of which has passed eight admission laws, carries its own confidence vector, and
can say **which** axis is weak — never just a single number.

**What you get now:**

    ✅  6,253 facts with 36,599 source refs — ~6 receipts per fact
    ✅  459 situations admitted, 4,727 admission verdicts recorded INCLUDING refusals
    ✅  the vector is never collapsed to a scalar. `confidence_bp` is the minimum; the axes
        sit beside it, so "we cannot identify who this is about" is distinguishable from
        "the sources disagree"
    ✅  COVERAGE_UNKNOWN = -1 is a third state. An unassessed axis never reads as 0
    ⛔  103 of 459 situations carry coverage = -1 — and ALL 103 are admin's

## 5.3 · L2 — Signals Qualification

**Expected after L2:** one `ReasoningDecision` per admitted situation, with every unit's verdict
recorded separately, every declining unit's silence *declared*, and a scored candidate set in
which no score is a neutral default.

**What you get now:**

    ✅  12,170 runs, 100% completed. Nothing is stuck in L2
    ✅  42,980 unit results — one row per unit per run, so a decline is visible
    ✅  34,232 candidates, ZERO without score_components
    ✅  the 5000 defect is CLOSED at boundary 2026-09-08 with 34,167 clean since
    ✅  12,170 context snapshots — the read is STORED, so a decision is replayable
    ⛔  core.relationship 929 runs / 0 completions          ← needs H5
    ⛔  core.signal_composition has NEVER run               ← needs roster activation (Rohit)
    ⛔  cost_vs_benefit axis: 0 fires in 1,973 runs         ← needs H4

## 5.4 · The seventh axis — Atlas cell L2-07, and the live defect it uncovered

Cell L2-07 said *"role/source-readiness completeness is not part of the blocking vector"*. It is
**true**, and it now has a number.

`coverage_bp` — the axis that *sounds* like readiness — is not readiness. It reads
`context_situations.coverage`, written by `situations.coverage_score(present_fields, expected)` =
**how many of one situation's own expected FIELDS are known.** Source readiness is computed in
`capture/coverage/model.compute_coverage`, enters L1's **four**-component signal vector as
`10000 if coverage_ready else 0`, and **stops there.**

    source_coverage      admin FALSE ×3 orgs · sales FALSE ×3 · support FALSE ×3 · fundraising TRUE ×3
                         fresh in all three orgs: {calendar, communication}
                         ⛔ `finance` has NEVER been connected → admin has never been ready
    context_situations   admin 310 of 459 (67%)

**Admin is the only activated domain, it is 67% of the stored corpus, it has never been
coverage-ready, and the blocking vector could not see that.**

Built: **U1** `situations.readiness_score()` (pure, 8 tests) and **U2** the axis on
`contracts/situation.CONFIDENCE_AXES` (now 7) + `situations.Confidence` (6 tests).
**U3** (migration `0191` + the writer) is ⛔ **blocked on H1**. **U4** (whether readiness should
*compose*) is a product decision: admin scores 1-of-2, so composing it would cap `overall_bp` on
**all 310 admin situations** through the weakest-axis law.

### ⛔ F-3 · a live defect found while measuring this, 141 rows

    coverage_ready = NULL    141 signals  →  coverage axis = 0 on ALL 141
    coverage_ready = FALSE   353 signals  →  coverage axis = 0 on ALL 353
    coverage_ready = TRUE     61 signals  →  coverage axis = 10000 on all 61

`capture/esqe/publisher.py:415` reads `10000 if coverage_ready else 0`, and `coverage_ready` is a
**tri-state**. So **141 of 555 qualified signals (25%) assert "we looked and found nothing
connected" when the truth is "nobody ever assessed it"** — and they are *indistinguishable* from
the 353 that are honestly FALSE. 494 rows look identical and 141 of them are a different fact.

This is exactly the error `AXIS_UNKNOWN_BP = -1` and `COVERAGE_UNKNOWN = -1` exist to prevent, one
layer down, where neither sentinel was used. **It is L1's own unit, it is not blocked on anything,
and it is the highest-value small fix left in the three layers.**

---

# PART 6 · WHY THIS ARCHITECTURE IS BETTER

Not "modern" — **better at one specific job: never asserting something it cannot back.**

## 6.1 · Absence is never negative evidence

The naive pipeline treats a missing thing as a false thing. "No reply" becomes "they ignored us".
This one refuses, in three separate places:

- **L1** `compute_coverage` fails *closed* for an unregistered domain and says so in prose:
  *"coverage cannot be assessed, so no negative inference is licensed"*. Every readiness predicate
  goes FALSE. An unassessed domain grants no permissions.
- **L3** `COVERAGE_UNKNOWN = -1` is a **third state**. A 0 would rank an unmeasured situation
  *below* every measured one.
- **L2** a unit with no basis returns `None`, and `composed_from` records **which** axes went into
  a number — so "we left freshness out because we could not measure it" and "freshness was fine"
  stay different facts.

## 6.2 · Every number carries the reason it is that number

`composed_from` on the vector. `score_components` on 34,232 candidates. `graph_source_refs` — 6 per
fact. `qualification_drops` storing the floor *and* the components *and* the payload ref. 12,170
stored `ContextSnapshot`s so a decision can be recomputed from its own inputs.

The test of an architecture is not whether it gets the answer right. It is whether, six months
later, you can find out **why** it said what it said. This one can, at every seam.

## 6.3 · Composition cannot manufacture certainty

    overall_bp is bounded by the weakest axis that went into it.

Several weak axes agreeing is not corroboration, and a mean over them produces a number larger
than anything it was computed from. The validator raises on violation rather than clamping, so a
later weighted composition is still legal — and still cannot exceed its weakest input.

## 6.4 · The import direction is a build failure, not a review nit

`tests/test_layer_topology.py` fails the build on an upward import, and `contracts/` may import
platform and stdlib only. This is what keeps domain knowledge out of the engine and context out of
expertise — **mechanically**, not by convention. It is also why decision #2 (correlation
placement) resolved the way it did: putting the 10 correlators in L1 would have been an L1→L3 read,
and the build would have refused it.

## 6.5 · A declaration beats a comment

`reason/unit_health.py` holds **four grains** of declared silence, each with a *named mover* — the
person or deploy that would end it. `starved_by_declared_paths()` is **derived from the roster,
never listed**, so it cannot go stale. The frozen-formula receipt reads its boundary date from a
**function** so it cannot copy the date.

> ⛔ **A receipt over append-only history needs a lower bound, or it is not a gate but a monument.**
> ⛔ **A comment that cites a record reads as a record somebody can go and read.**

## 6.6 · The honest cost of all this

**It is slower to build, and it finds its own errors loudly.** PART 4.4 lists nine findings that
were wrong. Every one was caught by measuring rather than reasoning, and several were caught by
the repo's own tests refusing a change. A pipeline that asserted freely would have shipped all
nine.

The current state is the fair summary: **14,599 tests green, 30 production receipts of which
22 PASS / 7 FAIL / 1 ERROR, and not one remaining failure is a mis-asked question.** Every red is
a deployment, a connector, or a decision with a named owner.

---

# PART 7 · HARSH — THE PENDING WORK, IN DETAIL

**Five items. H1 and H2 are the two that matter; the other three are improvements.**
Nothing here needs a code change from Harsh — all five are **deployment and connector** work.
Every claim below was measured on 2026-10-01.

## H1 · ⛔ APPLY MIGRATIONS `0186`–`0190` — THIS IS BREAKING A WRITE PATH

**Severity: highest. Do this first, before anything else in this document.**

    migrations/0186_signal_bundles.sql
    migrations/0187_evidence_needs.sql
    migrations/0188_pipeline_counters.sql
    migrations/0189_output_lane.sql
    migrations/0190_card_lane.sql        ⛔ the next card write FAILS without this one

**What is true, measured against production 2026-10-01:**

    select version from schema_migrations order by 1 desc limit 1;
      -> 0185_capture_policy_teams_default.sql      applied 2026-09-26 08:10:36 UTC

    select column_name from information_schema.columns
     where table_name='cards' and column_name='lane';
      -> ⛔ ZERO ROWS. The column the card writer names DOES NOT EXIST.

These five have **never run.** The code that needs them is merged and on the branch, so the write
path references a column the database does not have.

**Why `0190` is urgent and not cosmetic:** the card writer names the `lane` column. The column
does not exist. So the next card write raises, rather than degrading — it is not a missing feature,
it is an error path.

**How to apply:** the standard migration runner, all five in order, in one go. They are additive
(`alter table … add column`) and none of them rewrites or drops data.

**How to know it worked:**

    -- all five present (NOTE: `version` holds the FULL FILENAME, not the number)
    select version from schema_migrations
     where version like '018[6-9]%' or version like '0190%' order by version;
    -- the column that is breaking writes
    select column_name from information_schema.columns
      where table_name='cards' and column_name='lane';

**What it unblocks:** the card write path immediately; `QualifiedEnterpriseSignalBundle`,
`EvidenceNeed`, the five pipeline counters and the five output lanes become storable; and **my
U3** (the readiness axis column, migration `0191`) can then be written at all — `0191` cannot be
added in front of five unapplied ones.

## H2 · ⛔ THE OCR STACK — BOTH HALVES, OR NEITHER WORKS

**Severity: highest by row count. 1,696 rows are waiting on this one deploy.**

Two changes, and they must ship **together**:

    1.  requirements          pytesseract  +  Pillow          (the Python bindings)
    2.  the container image   apt-get install tesseract-ocr   (the actual binary)

**Why both:** `pytesseract` is a *wrapper*. Installing it without the `tesseract-ocr` binary gives
you a module that imports cleanly and raises at the first call. Installing the binary without the
bindings gives you a binary nothing calls. **Shipping one half looks like a successful deploy and
changes nothing**, which is the failure mode worth naming out loud.

**What is waiting:**

    872 attachments        never OCR'd — the text was never extracted
    824 parked rows        `drain.NEEDS_REFETCH` = {DOC-02, DOC-04, DOC-05, DOC-06}
    ─────                  attachment stubs whose BYTES NEVER EXISTED
    1,696 rows total       49.6% of the entire parked pending queue (1,662) plus the attachments

**Why the drain will not touch them today, and that is correct:** `drain.NEEDS_REFETCH` marks rows
whose bytes were never stored. The drain *declines* to re-inject them rather than "report work that
did not happen". Re-running the drain before this deploy does nothing, by design.

**How to know it worked:**

    python -c "import pytesseract, PIL; print(pytesseract.get_tesseract_version())"

If that prints a version, both halves are in. If it raises `TesseractNotFoundError`, only the
bindings landed. **Then** re-run the drain and the 824 become re-fetchable.

## H3 · BACKFILL WINDOW 60 → 365 DAYS

**Severity: medium. An improvement, not a fix.**

The connectors currently backfill **60 days**. Every freshness axis, every trend, every cohort
position and every baseline is computed over whatever history exists — so a 60-day window caps the
depth of every comparative judgement the system can make.

**What it affects:** `metric_history` (2,514 rows), `baselines` (537), and the `analytic` confidence
axis — which exists specifically so that *"a situation whose importance leaned on a 5-member cohort
is visibly less certain than one that leaned on 200"*. With 60 days of history, most cohorts are
small, so most `analytic` scores are honestly low. **That is the axis working correctly on thin
input, not a bug** — but the input is thin because of this setting.

**How to know it worked:** `select min(occurred_at) from source_events;` should move back ~10
months after a re-sync.

## H4 · A `deal.status` WRITER

**Severity: medium, and it is the single root cause of a measured zero.**

    cost_vs_benefit axis       0 fires in 1,973 runs
    axis counts                0 axes: 16 · 1 axis: 929 · 2 axes: 1,028 · 3 axes: ZERO

`core.tradeoff` compares three axes. `cost_vs_benefit` needs a cost side and a benefit side, and
one of its two source metrics resolves to `deal.status` — **a fact path with no writer.** 293 graph
nodes could carry it; **none does.** So the axis has never had both sides and has never fired, and
no situation has ever been compared on all three axes.

**What is needed:** any connector that writes `deal.status` onto a graph node — a CRM connector is
the obvious one, and it would need to write across more than 3 of the 293 nodes to move the
measurement.

⛔ **This is already declared**, with Harsh named as its mover, in
`reason/unit_health.py::DECLARED_NEVER_COMPLETED`. It is not a surprise and it is not a bug — it is
a connector that does not exist yet, recorded as such.

## H5 · AN APPROVAL-WORKFLOW SOURCE

**Severity: medium. Same shape as H4.**

    core.relationship          929 runs, ZERO completions

The unit runs every time and completes never, because the fact it needs is never written. It is
declared in `reason/unit_health.py` with the same discipline as H4: a named mover and a reason.

**What is needed:** a source that emits approval-workflow state — who approved what, and when.

## H6 · WHAT HARSH SHOULD **NOT** DO

| | Why |
|---|---|
| ⛔ Do not flip any `identity.status: draft` to `stable` in the corpus | Four Admin situations and one Support situation are declared `pending_l2_types`. The repo's own test says they **MUST NOT be flipped**, and one records that flipping it *"would cost a false assurance"*. **This is not pending work.** |
| ⛔ Do not set `GENIOS_ALLOW_PROD_WRITE` to run a report | That variable is named for writes because it was written for writes. Reads run in `set transaction read only`. |
| ⛔ Do not add migration `0191` or later | `0186`–`0190` must land first. A `0191` in front of five unapplied migrations is a second problem on top of the first. |
| ⛔ Do not lower the qualification floor to "recover" the 552 drops | Measured: average floor 2,500 bp, average dropped importance **1,251 bp**. They scored *half* the floor. Lowering it admits noise, it does not recover signal. |

## H7 · THE ORDER, AND WHAT EACH STEP OPENS

    H1  migrations 0186-0190   ──►  card writes work again
                               ──►  counters/lanes/bundles/needs become storable
                               ──►  unblocks U3 (migration 0191, the readiness column)

    H2  OCR stack (both)       ──►  872 attachments extractable
                               ──►  824 parked rows re-fetchable  (re-run the drain AFTER)
                               ──►  the parked queue drops from 1,662 to ~838

    H3  backfill 60 → 365      ──►  deeper history for every freshness/analytic judgement
    H4  deal.status writer     ──►  cost_vs_benefit can fire for the first time
    H5  approval source        ──►  core.relationship can complete for the first time

**H1 and H2 together are roughly 90% of the available value.** H1 is minutes of work and fixes an
error path. H2 is one requirements line plus one apt line and releases 1,696 rows.

---

# PART 8 · WHAT IS NOT DONE IN L1, L2 AND L3

**All three layers are built.** Nothing below is a missing feature; each is a deploy, a connector,
a product decision, or one unit that is blocked on a deploy.

| | Item | Layer | Whose | Blocked on |
|---|---|---|---|---|
| 1 | ⛔ **F-3** · tri-state `coverage_ready` collapsed to a binary — **141 live rows** | L1 | **me** | nothing. Highest-value small fix left |
| 2 | **F-2** · `compute_coverage` gates on the constant, `declaration.py` iterates the function | L1 | **me** | nothing. ⛔ **latent — zero authored domains exist** |
| 3 | **U3** · migration `0191` + the readiness writer + a 31st receipt | L2/L3 | **me** | ⛔ **H1** |
| 4 | **U4** · should readiness *compose*? Caps 310 admin situations | L2 | **Rohit** | U3 |
| 5 | `0186`–`0190` | all | **Harsh** | nothing · **H1** |
| 6 | OCR stack, both halves | L1 | **Harsh** | nothing · **H2** |
| 7 | backfill 60 → 365 | L1 | **Harsh** | nothing · **H3** |
| 8 | `deal.status` writer | L2 | **Harsh** | nothing · **H4** |
| 9 | approval-workflow source | L2 | **Harsh** | nothing · **H5** |
| 10 | roster activation — ⛔ **A5's ordering FIRST**: schedule `core.impact`/`core.cost`/`core.opportunity` **before** `core.tradeoff` | L2 | **Rohit** | nothing |
| 11 | the **709 `low_relevance`** parks — terminal state, or narrow the receipt? | L1 | **Rohit** | nothing |
| 12 | ⛔🔴 **Anthropic spend limit / DECISION #5** — refused every call since 2026-09-25 11:09 UTC. **Measured 2026-10-01: this is what stopped the card pipeline**, not a convenience. See PART 9 | all | **Rohit** | nothing — and it blocks every card |
| 13 | three Atlas documentation edits (from decision #1 = A) | docs | **Rohit** | nothing |
| 14 | Atlas cell **L2-08**, and the 97 `draft` objects gating question | L2 | **Rohit** | nothing |

## ⛔ Explicitly NOT pending — do not re-open

| | Why |
|---|---|
| ~~ALARM D-A2~~ | **retracted.** The five situations are declared `pending_l2_types` and the repo's own test says they MUST NOT be flipped. **No action, by anybody.** |
| ~~ALARM A6~~ | **retired.** All three of its claims were false and its proposed fix would have broken a designed derived branch. |
| ~~CA1~~ | retired · ~~**CA2**~~ built (`scripts/l2_tradeoff_axes.py`) · ~~**CA3**~~ measured: **zero code gap** in the parked queue |
| ~~the 15 remaining Customer Support situations~~ | **domain on hold.** Only Admin is activated. |
| ~~`SituationSeed`~~ | the Atlas names it; it has zero hits in the code and **nothing needs it**. Situations are proposed by correlators reading the graph, not seeded. |
| ~~lowering the qualification floor~~ | the 552 drops scored **half** the floor, not just under it. |

## Every model-off number in this document

⛔ **The Anthropic API has refused every model call since 2026-09-25 11:09 UTC** (spend limit).
So every production number in this document was taken with the model off. That matters for exactly
one thing: `l2_model_runs` (796 rows) stopped growing on that date, and the composition seam — the
only place in L2 where a model may run — has not been exercised since. **Every other number here
is from deterministic code and is unaffected.**

---

# PART 9 · THE ROAD TO L4

L4 is `executive/` — 27 files, 6,167 lines. It is the smallest package in the stack and it sits
directly downstream of everything in this document.

**What L4 receives:** a `ReasoningDecision` (`contracts/reasoning.py:1393`).
**What L4 owns, per `LAYERS.py`:** the decision **and** who/where it reaches —
`executive/assignment.py` and `executive/communication.py`. ⛔ Not "decision intelligence only":
`deliver/router.py:9-12` records that assignment **moved to** `executive/`, and all four of
`deliver/{audience,orchestrator,gate,outbox}.py` import it.

**What the funnel says about L4 today:**

    cards              165       150 expired · 9 queued · 6 surfaced
    by domain          admin 84 · general 59 · sales 14 · customer_support 7 · verify 1
    execution_events 1,022 · execution_actions 794 · execution_escalations 466
    executive/readiness.py exists · platform/org_readiness_sql.py exists

## ⛔ ANSWERED, 2026-10-01 — and it was neither

The crosscheck ran. The question was *"is the 150 a delivery defect, or the downstream shadow of
H2?"* **It is neither**, and the answer is in
`layer-4-executive/05-RECROSSCHECK-why-the-queue-is-empty.md`.

    L1 / L2 / L3 wrote rows 2026-09-30.   L4 stopped 09-25.   L5 stopped 09-25.
      -> the OCR deploy would have starved L1. It did not. Guess refuted on the spot.

**There are TWO blocks, at two different places, and neither is a defect in `executive/`:**

| | Block | Measured |
|---|---|---|
| **1 · the input** | `GENIOS_L4_LLM_DECISION_MAKER = true` (every org) + the Anthropic spend limit + `llm_decision_maker.py:20`'s declared *"Failure is DEFER, never the formula"* | `formula_utility` **5,469** ✅ healthy · `llm_utility` **0** · `final_utility_bp` **0** on all 8,044 candidates · `outcome_kind` defer 2,669 · decision **ZERO** · **0 signals emitted** |
| **2 · the ladder** | no reporting line, so `manager_of` returns `None` | **124 day-7 manager escalations scheduled, 0 ever fired.** The ladder works to day 3 and stops |

⛔ **So the spend limit did not merely switch off LLM features — it stopped the card pipeline**, in
a way that reads from outside as a delivery defect while six layers report healthy. The logic is
sound and stated; what nobody declared is that **the measurement mode is the production mode.**

> ⛔ **A deliberate refusal to degrade is still a stop.**

That is now **DECISION #5** in `02-DECISIONS.md` — three options, one line, Rohit's. **L4 needs no
build work to start producing.** Six units are planned in `layer-4-executive/02-PLAN.md`, four
buildable, two blocked on a product number.

⛔ **And this changes the priority order in PART 8.** R2 (the spend limit) is not a 🟠 that blocks
nothing — it is a 🔴 that blocks **every card the product could produce**. H1 and H2 remain worth
doing and will not produce a single card until decision #5 is answered.

---

## Where to look next

| | File | What it is |
|---|---|---|
| 1 | `07-LEDGER-every-step-what-why-how-outcome.md` | every step in the programme, with task / why / expected / outcome |
| 2 | **`HANDOFF-HARSH.md`** | the five items above, as standalone briefs |
| 3 | `HANDOFF-CODING-AGENT.md` | three standalone briefs + the twelve rules this repo fails a build over |
| 4 | `STATUS.md` — **the LAST section** | the live task list. ⛔ The table at line 745 is stale |
| 5 | `08-ATLAS-SCORECARD-L1-to-L6.md` | ⛔ **56** Atlas claims, each verified or refuted — renamed from `-L1-to-L5` when L6's eleven were added. ⛔ **L6 here is `feedback/`**: this scorecard numbers `deliver/` as L5, while the source matrix labels the same rows `L7 Learning` |
| 6 | `layer-2-reasoning/16-AUDIT-AND-PLAN-the-readiness-axis.md` | the readiness axis, audit + plan + what was built |
| 7 | `genios_engine/LAYERS.py` | ⛔ **read this before using any layer number** |
| 8 | `genios_engine/reason/unit_health.py` | the four grains of declared silence, each with a named mover |
