# Layer 1 v2 — What Was Built

> **Created:** 2026-09-06 · **Status:** Active

**Purpose:** the unit-by-unit record of what Layer 1 v2 actually is in code — every module, what it
does, why it exists, and how it was proven — plus the one gate that is not met and exactly what
would close it.

**Specification of record:** `Rohit_Updates (Version 2)/Version 2 Updates/01-Layer-1-Plan/` (docs
00–10). That set is the *design*. `L1_V2_BUILD.md` is the *schedule* — waves, gates, sequencing
corrections. **This file is the *result*.**

---

## 1. The one-paragraph version

Layer 1 turns raw enterprise data into `QualifiedEnterpriseSignal` — a typed, evidence-carrying,
deterministically-scored object that Layer 2 can rank. It does that in four stages: S1 finds
structure without a model, S2 asks a model to understand prose and write into a closed schema, S3
verifies every claim against the source text it came from, and S4 decides which claims are signals
and how much each one matters. Eleven waves, sixty-five units, ten of eleven gates met.

```
raw event ──► S1 structural ──► S2 semantic ──► S3 validate ──► S4 ESQE ──► QES ──► Layer 2
              (no model)        (LLM-2)         (pure)          (scoring)
```

---

## 2. Totals

| | |
|---|---|
| Waves | 11 of 11 built |
| Units | 65 of 65 |
| Gates | **G0–G9 met · G10 open** (needs a real tenant) |
| Engine code | ~35,000 LOC across 11 packages |
| Tests | **6,693 passing · 0 failing · 0 skipped** (real Postgres) |
| Migrations | 92 total; 14 new for this layer (`0079`–`0093`) |

The suite number is only meaningful against a real database. The hermetic lane silently skips ~800
tests, so **always run with `GENIOS_TEST_DATABASE_URL` set** — see §8.

---

## 3. The four doctrines everything obeys

These are not style preferences. Each one is enforced by a test or a grep in a gate, because each
one records a failure that actually happened.

**1 · The model may DESCRIBE, never SCORE.**
A score feeds ranking, and ranking must be byte-identical across machines and replays. Every number
that orders anything is computed by deterministic code. `capture/esqe/importance.py` has no LLM
anywhere on its call path.

**2 · Integer basis points. No floats. Anywhere.**
Every score is an `int` in `0..10000`; every amount is integer minor units plus an ISO code.
`conf * 9 // 10`, never `conf * 0.9`. Gates G0, G1 and G7 grep the source for `float(`, and
`contracts/publication.py` V-7 rejects any signal whose serialized form contains one.

**3 · No claim without a receipt.**
Every claim carries `EvidenceSpan` — character offsets into the original source plus the quoted
text. A span is `verified=True` only after `capture/validate/spans.py` (ALG-08) resolves it against
the real source. The extractor cannot stamp its own receipts: schema rule S-9 rejects an
`ExtractionResult` carrying `verified=True`.

**4 · No clocks inside logic.**
Time arrives as an `eval_time` parameter. A function that reads the clock cannot be replayed, and
replay is what makes every gate above checkable. A naive (tz-less) `eval_time` raises rather than
being silently assumed UTC.

---

## 4. The layer, package by package

### 4.1 `contracts/` — the vocabulary (Wave 0)

6 files · 2,609 LOC · **112 tests**

Everything else types against these. `contracts/` may import only stdlib and pydantic — enforced by
`tests/test_layer_topology.py`.

| File | Contracts | What it is |
|---|---|---|
| `evidence.py` | C-01 `EvidenceSpan` | the receipt: source ref, quote, offsets, verified |
| `units.py` | C-02 `Money`, C-03 `ResolvedDate`, `DateCertainty` | integer minor units; a date that knows it is a *range*, not a point |
| `extraction.py` | C-04…C-09 | `EntityMention`, `Commitment`, `DecisionState`, `Dependency`, `UnclassifiedObservation`, `ExtractionResult` |
| `conflict.py` | C-10 `Conflict`, `ConflictClaim` | both sides retained, always |
| `signal.py` | C-11 `SignalType` (14 closed members), C-12 `QualifiedEnterpriseSignal` | **the L1 → L2 boundary object** |
| `publication.py` | V-1…V-7 | the publication gate: emit / park / reject |

**The publication rules, and why their outcomes differ:**

| Rule | Checks | On failure |
|---|---|---|
| V-1 | envelope complete, `visibility is not None` | **park** — recoverable, not a defect in the claim |
| V-2 | `signal_type` in the closed enum | reject |
| V-3 | `0 ≤ importance_bp ≤ 10000` | reject |
| V-4 | `evidence_refs` non-empty | reject — *a claim with no receipt is a guess* |
| V-5 | every span `verified` | **downgrade confidence and emit**, flagged |
| V-6 | `confidence_bp ≤ min(source confidences)` unless independent evidence is named | reject (Rule 11) |
| V-7 | no float in the serialized object | reject |

V-5 downgrading rather than rejecting is load-bearing: an unverified commitment is still an open
loop worth surfacing, at reduced confidence. The **stored** row must carry the downgraded value —
publishing the input instead silently re-inflates it, and there is a test for exactly that.

---

### 4.2 `capture/structural/` — S1, find without interpreting (Wave 2)

3 files · 1,056 LOC · **140 tests**

| Unit | What it does |
|---|---|
| **L1.3.5-U1** `scan()` | ALG-04. Finds 11 token types — money, dates, URLs, emails, phones, identifiers, quantities — deterministically, before any model sees the text |
| **L1.3.5-U2** `router_counts()` | the counts ALG-05 uses to pick a model tier. *Never call a model to decide which model to call* |
| **L1.3.5-U3** `compile_identifier_pattern()` | tenant-configurable identifier regexes, statically validated (refuses catastrophic backtracking) |
| **L1.3.6-U1** `reconstruct_thread()` | ALG-03. Direction, turn index, `ball_in_court` |
| **L1.3.6-U2** `assemble_chain()` | thread forest from `In-Reply-To` / `References`, falling back to chronology |

**The invariant:** `source[tok.start:tok.end] == tok.text` for every token. G2 asserts zero
round-trip failures; the test is a property over generated text, not a handful of examples.

---

### 4.3 `capture/documents/` `structured/` `parked/` — the rest of S1 (Wave 2)

25 files · 5,633 LOC · **574 tests**

- **`documents/`** — L1.3.4 document router: native text, OCR, chunking. Chunk boundaries preserve
  offsets into the *original* document, because S3 and the evidence binder both resolve against them.
- **`structured/`** — L1.3.9 the S2 bypass. A typed HubSpot field is **not a guess**: it skips the
  model entirely, lands `field_confidence == 10000`, and runs even when the semantic lane is not
  configured. Proven with an LLM client that *raises* if called.
- **`parked/`** — L1.3.8 attachment resolver. Refetch is idempotent and bounded; a transient failure
  stays retryable, a permanent one reaches a terminal state. Every park code is drained by exactly
  one path and counted by `scripts/l1_s1_report.py`.

---

### 4.4 `capture/semantic/` — S2, the extractor (Waves 3 and 4)

13 files · 7,351 LOC · **863 tests**

**Wave 3 built the sink before Wave 4 filled it.** That ordering is not stylistic. A free-form
extractor once invented 268 distinct field names in one org — 192 used exactly once — and rules
reading `deal.status` were dead because the model had written `status`.

| Unit | File | What it does |
|---|---|---|
| L1.4.4-U1 | `vocabulary.py` | the closed vocabularies. Imports nothing above `contracts/` — an import-graph test enforces it, so the sink constrains the rules rather than following them |
| L1.4.4-U2 | `schema_gen.py` | generates the prompt's schema block *from* `ExtractionResult`, so the two cannot drift |
| L1.4.2 | `profiles.py` | 5 extraction profiles; every emphasis field is checked to exist on the real model |
| L1.4.5 | `open_lane.py` | `UnclassifiedObservation` — what the closed vocabulary could not name. Never importable from `packs/` or `reason/` |
| L1.4.6 | `evidence_binder.py` | span attachment and mask→original offset alignment |
| L1.4.1 / L1.4.10 | `router.py` / `model_router.py` | profile selection; tier decision on **deterministic inputs only**; demotion is visible via `tier_demoted` |
| L1.4.9 | `cache.py` | keyed on content + schema version + profile + prompt version |
| L1.4.7 | `injection.py` | content fencing — a payload containing the fence string is escaped |
| L1.4.8 | `batch.py` | batch planner and cost governor |
| L1.4.3 | `extractor.py` | **LLM-2**, the call itself |
| — | `sink_guard.py` | closes the untyped-dict bypasses; an unknown field goes to the open lane or nowhere |

**Two defects worth remembering, both found by adversarial review:**

- A whole-message extraction could come back empty, be cached as a success, and be **permanently
  empty** — a re-run served the same nothing at zero cost, and the monitor read zero. Now a *total
  loss* parks with a reason and is counted; a *genuinely empty* message still caches, and the
  boundary between the two is stated in one function.
- The prompt never said which string the model's offsets indexed. Every span paid for that guess.
  The frame is now stated explicitly — astral character = 1, CRLF = 2 — and is part of the cache key.

---

### 4.5 `capture/validate/` — S3, verification (Waves 1 and 5)

11 files · 6,971 LOC · **1,568 tests** — the largest and purest package. No float, no clock, no LLM,
no DB.

| Unit | File | What it does |
|---|---|---|
| L1.5.1 | `spans.py` | **ALG-08.** Grades a span exact / whitespace-normalised / relocated / fuzzy / unverified, and *corrects* the model's offsets rather than trusting them. Forces `verified=False` on failure — the extractor cannot keep a flag it asserted |
| L1.5.2 | `dates.py` | **ALG-09.** "next Friday" is a *range with a certainty*, not a point. Relative dates, durations, recurrence, business days |
| L1.5.3 | `money.py` | **ALG-10.** `$84K` and `$84,000` normalise to the same object. Integer path throughout — no `float(x) * 100` anywhere, which is how a cent goes missing |
| L1.5.8 | `authority.py` | **ALG-14.** A signed contract outranks an email outranks a chat aside. A table, not a chain of ifs |
| L1.5.7 | `confidence.py` | **ALG-13, Rule 11.** Composed confidence may never exceed the weakest source unless independent evidence is *named*. Several weak sources repeating one weak thing is not corroboration |
| L1.5.6 | `schema.py` | S-1…S-9 shape and vocabulary rules, stage-scoped |
| L1.5.4 | `canonical.py` | **ALG-11.** "AWS" and "Amazon Web Services" — deterministic alias matching, no embeddings. A *hint*; Layer 2 stays authoritative on identity |
| L1.5.0 | `claim_group.py` | **ALG-22/23.** Groups claims about the same subject across a thread and its attachments. Keys are stable across processes |
| L1.5.5 | `conflict.py` | **ALG-12.** The $74K signed PDF versus the $84K email — **both claims retained**, with a resolution and a reason |
| — | `conflict_store.py` | persistence, so a detected conflict is not computed and discarded |

**Rule 11 in one measurement.** Before the fix, a weak Slack message could waive the ceiling
entirely:

```
prior 2000 · signed.pdf 9000 · slack 100
before:  composed 9002        (the slack message bought an 8,900 bp lift it never earned)
after:   composed 1882        = corroborate(100, 9000) — the sanctioned bound, exactly
```

The same clamp had to move onto the *published* `confidence_vector` too, because V-6 reads only the
scalar and would never have caught an axis carrying `8765` from a corpus whose weakest member was
`1000`.

---

### 4.6 `capture/esqe/` — S4, qualification (Waves 6, 7, 8)

13 files · 7,391 LOC · **645 tests**

| Unit | File | What it does |
|---|---|---|
| L1.6.1 | `detector.py` | **ALG-15.** Deterministic predicates over validated claims |
| L1.6.3 | `classifier.py` | **ALG-16.** Into the closed 14-member taxonomy, with a stated precedence |
| L1.6.2 | `normalize.py` | one canonical shape regardless of which detector produced it |
| L1.6.4 | `source_analyzer.py` | provenance and actor authority |
| L1.6.5 | `relevance.py` | **LLM-5** — the one gated model site. *Rules first*, model only for the ambiguous remainder, batched at the page seam |
| L1.6.6 | `domain.py` | domain tagging |
| **L1.6.7** | **`importance.py`** | **ALG-17 — the formula.** Five weighted integer terms: monetary exposure against the org's own p50, deadline proximity, actor authority, entity criticality, signal-type nudge — times an evidence-authority multiplier |
| L1.6.7-U2 | `baseline_reader.py` | reads the org's own priced history so the formula is normalised per tenant |
| L1.6.8 | `qualification.py` | **ALG-18 — the floor.** Below it, dropped *with a ledger row* carrying components and a payload reference |
| L1.6.9 | `lifecycle.py` | **ALG-19.** active / superseded / expired / resolved, as an explicit transition table |
| L1.6.10 | `publisher.py` | wires `validate_publication`; publishes `decision.signal`, never the input |
| L1.7.4 | `signal_store.py` | `qualified_signals` — the L1 → L2 handoff |

#### Why `importance.py` is the point of the whole layer

Before this, `context/situation_bso.py:237` stamped a constant. `reason/decision_maker.py:243`
recorded that *"the formula has never once decided anything"*, and 193 of 223 signals carried an
identical score — **with a green test suite the entire time**. Layer 4 cannot rank what Layer 1
scores flat.

So G7 is a **distribution** check, not an example check. Measured on the production path:

| Metric | Gate | Measured |
|---|---|---|
| distinct `importance_bp` | > 50 | **100** |
| p90 − p50 | > 1500 | **1520** (p50 4480, p90 6000) |
| every score carries components | 100% | **321/321** |
| identical input replayed | byte-identical | stable across wipe-and-recapture |

The spec's worked example — $84K renewal, 12 days out, CFO sender, mission-critical vendor, signed
PDF, org p50 $45K — scores **7825**, inside the required 7500–8500 band.

**Mutation-checked:** replacing the formula with `return 5000` collapses this to 1 distinct value
and a spread of 0. Sixteen tests go red. An example-based test would have passed.

---

### 4.7 `capture/{coverage,connectors,acquire}/` — ingestion (Wave 9)

25 files · 4,034 LOC · **289 tests**

| Unit | What changed |
|---|---|
| L1.1-U1 | `coverage_ready` was **`None` on 100% of emitted events** — the seam existed and no capture door injected it. Now all four doors do, and an AST test fails by file and line if a fifth is added without it |
| L1.1-U2 | registry honesty — the buildable source set is exposed rather than hardcoded in the frontend |
| L1.2.4 | backfill window **60 → 540 days**, per connection. Dedup key guards against re-ingestion |
| L1.2.5 | **webhook parity.** A pushed message dropped its attachments and had no `mailbox_owner` — so the same mail landed 3 rows by poll and 1 by push. Both doors now hand the pipeline the same wiring |
| L1.2.6 | per-source cadence, **deterministic** jitter (derived from org + connection, not entropy), catch-up windows |

---

## 5. What is NOT done

### 5.1 G10 — pilot activation · **the only open gate**

Everything G10 needs is built. What it needs now is **a real tenant and seven days**, which no amount
of code can substitute for.

**What exists:**

| Piece | Where |
|---|---|
| Activation as a per-tenant **row**, not a flag | `l1_semantic_activation` (migration `0085`), `platform/activation.py` |
| The shadow-diff runner | `scripts/l1_shadow_diff.py` — read-only, resolves its DB through `scripts/_db.py` |
| The old L2 extraction path | still present, deliberately — it is removed *after* G10, never before |

**What G10 asks for, from `09-Build-Order-and-Acceptance.md`:**

| Metric | Gate |
|---|---|
| events processed by both paths | 100% |
| signals L1 v2 found that v1 missed | reviewed and reported |
| signals v1 found that L1 v2 missed | **reviewed and explained — each one** |
| unverified span rate | < 5% |
| LLM cost per 1000 events | within 2× of v1 |
| founder-visible regressions | 0 |

**How to run it, when a tenant is available:**

```bash
# 1. enable the seam for ONE org — a row, never a global default
#    (insert into l1_semantic_activation; see platform/activation.py for the writer)

# 2. let both paths run side by side for seven days, with no mid-week switch-off

# 3. read the diff
python -m scripts.l1_shadow_diff --org <pilot-org-id> --days 7 \
    --database-url "<explicit url>"

# 4. only after every "old found / new missed" line has an explanation,
#    remove the L2 extraction path
```

**The activation rule, in the plan's own words:** *"Built but not enabled is not done."*

### 5.2 Known-and-accepted

| Item | Status |
|---|---|
| **Speech-to-text (L1.3.4-U3)** | descoped — the voice-transcript connector (P5) appears in no wave. The router seam exists and is exercised against synthetic fixtures; no provider is wired |
| **Golden corpus (G4)** | the runner `scripts/extract_golden.py` is real; the corpus holds **8 messages, not the 30 the spec asks for**. It passes every threshold on those 8 — 5/5 commitments, 27/27 spans verified, 0 fabricated amounts — but it is a partial set and should not be reported as complete |
| **Org holiday calendar** | `add_business_days` takes an injected calendar; nothing in L1 reads a per-org holiday list yet, so weekends-only is the live behaviour |
| **The 35 unwritten unit specs** | the plan's component maps promise 100 units; 65 have spec blocks. `scripts/unit_ledger.py` tracks the gap and `--check` fails if it grows |

---

## 6. How this was proven

Every wave ran the same shape: build → gate → **adversarial review** → fix. The review is what
found nearly everything below, and it is the part worth keeping.

**Techniques that actually caught defects:**

- **Mutation testing.** Break the code, confirm a test goes red. If nothing does, the test is
  decorative. `money.py` — deleting one term killed 23 tests. `importance.py` — `return 5000` killed
  16. This is the only reliable way to tell a real test from a green one.
- **Distribution over examples.** G7 measures the *shape* of 5,760 scores. The old flat-score bug
  passed every example test that existed.
- **Independent reproduction.** The gate agent wrote its own probes rather than reusing the builder's,
  then neutralised each fix in memory to confirm the probe was sensitive.
- **Import-graph assertions.** "The vocabulary must not import the rules" is a *structural* claim; a
  test that walks imports enforces it, a code review does not.
- **Real Postgres, always.** The hermetic lane silently skipped ~800 tests. Running against a scratch
  database surfaced 12 failures the green suite never showed — 10 of them from a *dirty* scratch DB,
  which is its own lesson: drop and recreate before every full run.

### The defect this build shipped six times

A unit built, tested, green — and **called by nothing on a real request path.**

```
extract()                the extractor itself
the poll scheduler       cadence and jitter
the cost governor        budget enforcement
claim_group → conflict   joined only inside a test file
compute_org_baseline     20% of the importance formula pinned to two constants
apply_verdicts           no span was ever actually verified
```

Each cost a full rework cycle. Each was found by adversarial review, never by the test suite —
because a unit test passes perfectly well on code nobody calls.

**The rule that ends it, and it belongs in every future wave's brief:**

> A unit is done when a **real request path** reaches it and a test drives **that path**.
> A test that constructs the collaborator itself proves the unit, not the wiring.

`tests/capture/test_sweep_lanes_wired.py` is the enforcement: deleting any of the three sweep lane
arguments turns it red.

---

## 7. Database

14 new migrations, `0079`–`0093`:

| Migration | Table |
|---|---|
| `0079` | `unclassified_observations` — the open lane |
| `0080` | `l1_extraction_results` (renamed from `l2_extraction_results`) |
| `0082` | `connection_backfill_days` |
| `0083` | `source_waitlist` |
| `0084` | `source_coverage.computed_at` |
| `0085` | `l1_semantic_activation` |
| `0086` | `parked_refetch_failure_kind` |
| `0087` | `signal_conflicts` |
| `0088` | `qualification_floor` |
| `0089` | `qualified_signals` |
| `0090` | `l1_activation_notes` |
| `0091` | `org_mission_critical_entities` |
| `0092` | `publication_rejections` |
| `0093` | `signal_lifecycle` |

**Every one is in the tenant-erasure list at `api/account_routes.py:326`, and that is not optional:**
that list executes `delete from {tbl} where org_id=:o` with **no try/except**, so a table missing
from it — or renamed under it — breaks org deletion for every tenant. The `l2_extraction_results`
rename touched 15 references across 9 files for exactly this reason. Erasure is proven on real
Postgres, not asserted.

**Two hazards worth carrying forward:**

1. `expertise_packages` once reached 181 MB over 345 rows and put the database into read-only. A
   lifecycle transition writing to it on every sweep re-armed that exact mechanism; it was caught in
   final review and closed. Any future per-event write to that table deserves the same suspicion.
2. `event_id` is minted fresh on every ingestion (`landing/normalize.py:33`). Anything keyed on it
   breaks across a re-ingestion — use the dedup key (`contracts/source_event.py:35`) instead.

---

## 8. Running it

```bash
cd genios-brain

# real-Postgres lane — ALWAYS use this. The hermetic lane skips ~800 tests silently.
dropdb genios_scratch; createdb genios_scratch      # drop first: a dirty DB gives false failures
GENIOS_TEST_DATABASE_URL="postgresql://$USER@localhost:5432/genios_scratch" \
  ./.venv/bin/python -m pytest -q
# expect: 6693 passed, 0 failed, 0 skipped, 152 xfailed

# the purity greps — these are gate criteria, not lint
grep -rn 'float('                        genios_engine/capture/{structural,validate}/
grep -rnE 'datetime\.now|date\.today'    genios_engine/capture/{structural,validate}/
grep -rnE 'LLMClient|anthropic'          genios_engine/capture/{structural,validate}/
# all three must return nothing

# the spec ratchet — the promised-vs-written unit gap may only shrink
./.venv/bin/python scripts/unit_ledger.py --check

# gate reports (need an explicit --database-url; they never fall back to settings)
python -m scripts.l1_s1_report            --org <org> --since 30d --database-url <url>
python -m scripts.importance_distribution --org <org> --since 30d --database-url <url>
python -m scripts.l1_end_to_end           --org <org> --since 30d --database-url <url>
```

**Never point any of these at production.** `scripts/_db.py` refuses to run without an explicit
`--database-url` or `GENIOS_TARGET_DATABASE_URL`, and refuses a Supabase host outright unless
`GENIOS_ALLOW_PROD_WRITE=1` is set deliberately.

---

## 9. Where things live

```
genios-brain/
  genios_engine/
    contracts/          evidence · units · extraction · conflict · signal · publication
    capture/
      structural/       S1 — tokens, threads
      documents/        S1 — router, chunking, OCR
      structured/       S1 — the typed bypass
      parked/           S1 — attachment refetch
      semantic/         S2 — the sink and the extractor
      validate/         S3 — spans, dates, money, conflict, confidence
      esqe/             S4 — detect, score, qualify, publish
      coverage/ connectors/ acquire/   ingestion
    platform/activation.py              per-tenant activation
  scripts/
    _db.py                              the DB guard every gate script uses
    unit_ledger.py                      the spec ratchet
    l1_s1_report.py · importance_distribution.py · l1_end_to_end.py · l1_shadow_diff.py
  migrations/0079–0093
  tests/
    contracts/ · capture/{structural,documents,structured,parked,coverage,connectors,acquire,semantic,validate,esqe}/
    golden/l1/                          the 8-message corpus
```

---

## 10. Next

| | |
|---|---|
| **Immediate** | run G10 on a pilot tenant (§5.1); grow the golden corpus from 8 to 30 |
| **Then** | Layer 2 — `02-Layer-2-Plan/`, 51 components, but only 33 unit specs written. **Write the ~90 missing specs first**; the L1 waves that had no spec block were the ones that needed rework |
| **Carry forward** | the wiring rule from §6, in every wave's brief from day one — not after the fifth time |
