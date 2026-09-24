# L2-2 · The interpretation fields — **two are missing, not six**

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

1. `ClaimState` exists, closed, guarded.
2. All six fields on v2, with basis-point integers and no floats.
3. **Four validators**: observed needs a receipt · inference must point at an observation · a
   hypothesis needs confidence · empty `unknowns` under low coverage is refused.
4. Migration 0182 written, and the store **names every column in its INSERT and its upsert**.
5. Full suite green; `vocabulary_fingerprint` unchanged.
