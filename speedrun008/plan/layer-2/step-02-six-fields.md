# L2-2 · The interpretation fields — **two are missing, not six**

> ## ✅ COMPLETE — 2026-09-24 · [findings](findings/step-02-interpretation-fields.md)
>
> 30 tests · 12,957 passed · 0 regressions · no migration · no model call ·
> `vocabulary_fingerprint` **`a3d5496aa0d3`** unchanged.
>
> ⛔ **THE PREMISE PARAGRAPH BELOW IS WRONG AND THAT IS WHAT MADE THE STEP BUILDABLE TODAY.**
> *"Every field that exists is an observation field"* — v2 is **full** of interpretation and says
> so itself: `visibility` *"a DERIVED claim"*, `coverage_ready` *"may a NEGATIVE inference be
> made"*, `missing_facts` *"the entries are FINDINGS"*, and V-4…V-7 exist **because** trends and
> correlations can be wrong. Layer 2 lacks the **label**, not the interpretation — so the step
> classified the 28 existing fields instead of minting six new ones, and needed **no migration**.
>
> ⛔ **AND V-9 HAD FOUR SUBJECTS THE DAY IT WAS WRITTEN.** `Anomaly`, `MetricCorrelation`,
> `CohortPosition` and `ImportanceAttribution` carry **no evidence reference at all**, while
> `MatchedCondition` states the doctrine for the family: *"'this fired because of these facts' is
> what makes a situation defensible."* All four are built on live paths.
>
> **The four genuinely-absent fields and migration 0182 are DEFERRED to L2-5, with their writer** —
> §5 of this file demanded that choice be made and stated. See §10 of the findings.

⛔ **CORRECTED by the re-analysis.** This step used to add six fields and four validators. Measured
against the tree, only **two names appear nowhere in `genios_engine`**:

```
observed_facts    0 files   ⛔ genuinely missing
inferred_state    0 files   ⛔ genuinely missing
valid_until       8 files   exists — but never on a situation
reasoning_trace   1 file
hypotheses        4 files   in prose, not as a contract field
unknowns          ⛔ ALREADY EXISTS, and better — see below
```

### ⛔ `unknowns` is `missing_facts`, and it is typed five ways

`context/quality/missing.py` — BLG-15, TYPED ABSENCE:

```
PRESENT · STALE · NOT_EXPECTED · UNKNOWABLE · GENUINELY_ABSENT
```

> *"`coverage_ready` is consulted **BEFORE** absence is ever concluded... `UNKNOWABLE` read as
> `GENUINELY_ABSENT` is **the worst output the quality group can emit**."*

**`L2-2-U3` proposed exactly this as new. It exists, it is five-state rather than binary, and it
already reads L1's `coverage_ready`.** Building it again would be building it worse.

**→ U3 becomes: carry `missing_facts` onto the situation as `unknowns`, and SURFACE it.** Today it
is consulted by the compiler and shown to no human.

---

# The original step follows, with U1–U3 corrected

**Needs Harsh:** migration only · **Model calls:** none · **This is the doctrine step**

---

## 1. Premise — the contract proves the diagnosis

`BusinessSituationObject` v2 carries 28 fields. Checked against the 19 the new architecture names:

| present (14 matched) | missing (6) |
|---|---|
| entities · signal_ids · evidence · dependencies · timeline · conflicts · missing_facts · coverage_ready · confidence · state · visibility · correlations · trends · anomalies | **observed_facts** · **inferred_state** · **hypotheses** · **implications** · **reasoning_trace** · **valid_until** |

⛔ **Every field that exists is an observation field. Every field missing is an interpretation
field.** Not a coincidence — the exact signature of a layer that correlates and does not reason.

---

## 2. ⛔ The rule, and why it is the whole step

```
Observation  ≠  Inference  ≠  Hypothesis
```

Three fields, and **write authority differs per field**:

| field | who may write it | enforced by |
|---|---|---|
| `observed_facts` | **machine only** — lifted from L1 signals, each with its evidence ref | validator: every entry must carry an `evidence_ref` |
| `evidence` | **machine only** | unchanged, V-4 already refuses an empty one |
| `inferred_state` | the reasoner, over facts it can point at | validator: every claim resolves into `observed_facts` |
| `hypotheses` | the reasoner, carrying its own confidence and unknowns | validator: a hypothesis with no confidence is refused |
| `implications` | the reasoner | validator: must cite the inference it follows from |
| `unknowns` | either — **but an empty one under low coverage is refused** | validator: reads `coverage_ready` |
| `reasoning_trace` | the reasoner | opaque id; the trace itself is stored, not inlined |
| `valid_until` | the gate | an interpretation expires; a fact does not |

**A model that can write `observed_facts` is a model that can invent a fact. So it cannot.**

This is not new doctrine. It is L1's `EvidenceSpan.verified` rule one layer up:

> *"The moment another caller can set that flag, it stops meaning 'checked' and starts meaning
> 'claimed'."*

---

## 3. Units

### L2-2-U0 · The three-way split as a type, before any field is added
`ClaimState = observed | inferred | hypothesised`. A closed enum, with the repo's totality guard.
**Build this first** — the fields below are shaped by it, and an enum added afterwards is an enum
nobody uses.

```
verify:  pytest tests/contracts/test_claim_state.py -q
```

### L2-2-U1 · `observed_facts` — and the validator that makes it mean something
The field, plus: **a situation whose `observed_facts` carry no evidence ref is refused at
construction.** The field without the validator is decoration.

```
verify:  pytest tests/contracts/test_observed_facts_need_receipts.py -q
```

### L2-2-U2 · `inferred_state` + `hypotheses` + `implications`
Each entry carries `value`, `confidence_bp`, `evidence_refs`, `state`. **Integer basis points —
V-7, no floats**, same as everywhere else in the engine.

### L2-2-U3 · `unknowns` and the low-coverage refusal
⛔ **The most important validator in the step.** An empty `unknowns` on a situation whose
`coverage_ready` is false is a claim of completeness the data does not support. Refuse it.

This is L1's step-12 lesson, carried up: *"telling a founder they broke a promise they kept is the
failure that loses trust rather than quality."*

```
verify:  pytest tests/contracts/test_unknowns_survive_low_coverage.py -q
```

### L2-2-U4 · `reasoning_trace` and `valid_until`
`reasoning_trace` is an **id**, not prose — the trace is stored once and referenced, so a situation
row does not carry a paragraph. `valid_until` is what lets an interpretation expire while the facts
under it do not.

### L2-2-U5 · Migration 0182 + the store
Columns, nullable. **And the INSERT must name them** — *"a column no writer names is null forever"*,
which is `started_at` on `l1_sync_runs` and the reason step 14 and 18 both wrote that sentence down.

```
verify:  pytest tests/context/test_situation_store_names_the_new_columns.py -q
         grep -c "observed_facts" genios_engine/context/...store.py   # > 0 in _COLUMNS and INSERT
```

### L2-2-U6 · A ninth admission law
The eight laws gate the v2 object today. Add the ninth: **no interpretation without a receipt.**
It belongs beside the others, not in a separate validator nobody runs.

---

## 4. Cost check

| | |
|---|---|
| model calls | **none** — this step adds fields and refusals, not reasoning |
| migration | **0182**, six nullable columns |
| existing rows | carry nulls, which read as *"nothing was interpreted"* — true |
| re-extraction | none |

---

## 5. What this step does NOT do

* **It does not fill the fields.** Nothing writes them until L2-5. A field with no writer is the
  `started_at` mistake, so **L2-2 and L2-5 ship together or L2-2 ships knowingly empty** — and the
  STATUS row must say which.
* **It does not weaken the eight laws.** It adds a ninth.
* **It does not let the reasoner near `observed_facts`.** That is the point of the step.

---

## 6. Completion criteria

| # | criterion | verdict |
|---|---|---|
| 1 | `ClaimState` exists, closed, guarded | ✅ Four members — three claims plus `envelope` for the fields that are not claims — with totality **both ways** over all 28 v2 fields |
| 2 | all six fields on v2, integer basis points | ⛔ **DEFERRED to L2-5, with their writer.** §6.2 |
| 3 | four validators | ⚠️ **two built AND wired into the gate.** V-9 · an interpretation cites nothing. V-10 · empty `missing_facts` under low coverage. The other two need the fields and travel with them |
| 4 | migration 0182 + the store names every column | ⛔ **DEFERRED with #2** |
| 5 | full suite green, fingerprint unchanged | ✅ 12,957 passed · 14 pre-existing · `a3d5496aa0d3` |

### 6.1 · What the units actually became

| planned | built |
|---|---|
| U0 · `ClaimState` | ✅ `contracts/claim_state.py` |
| U1 · `observed_facts` + its validator | ⛔ **struck.** `evidence` + `signal_ids` + `entities` + `timeline` **are** the observed facts and are now labelled. A fifth name for them is the defect L2-1 just removed |
| U2 · `inferred_state` · `hypotheses` · `implications` | ⛔ deferred to L2-5 |
| U3 · `unknowns` + the low-coverage refusal | ✅ as **V-10**, and **narrowed by measurement**: 11 of 37 situation types declare no `expected_fields`, and the plan's unconditional rule would have accused all eleven |
| U4 · `reasoning_trace` · `valid_until` | ⛔ deferred to L2-5 |
| U5 · migration 0182 + the store | ⛔ deferred to L2-5 |
| U6 · a ninth law | ✅ **and a tenth** — and V-9 has four subjects today |
| — | **unplanned: the write-authority table.** `model_may_write` / `model_writable_fields()` — the list L2-5's gate reads instead of keeping its own |
| — | **unplanned: the observation machinery.** `test_h0_gate` refused a non-rejecting action until one existed, and it was right to |

### 6.2 · ⛔ The choice §5 demanded, made and stated

> *"A field with no writer is the `started_at` mistake, so L2-2 and L2-5 ship together or L2-2
> ships knowingly empty — and the STATUS row must say which."*

Build order is `0 → 1 → 2 → 3 → 4 → 6 → 7 → 5 → 8`. **L2-5 is five steps away.** Shipping the
columns now means Harsh applies a migration for fields that stay null through five steps — and
**L2-0's entire finding was eight things built and never switched on.**

**The doctrine ships now; the storage ships with its writer.** Nothing deferred here needs a
column, and everything L2-5 needs in order to be born correct exists before it.
