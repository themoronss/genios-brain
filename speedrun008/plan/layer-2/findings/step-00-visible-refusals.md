# L2-0 · Make every refusal visible — findings

**Run:** 2026-09-24 · premise checked BEFORE any code · **no migration · no model call**
**Against:** `speedrun008` @ `ebfed036`
**Result:** 29 tests, **12,914 passed · 14 failed (all pre-existing) · 0 regressions**

---

## 1. ⛔ Premise check — the step was real, and three-quarters of it was already built

The plan asked for four things. **Three already existed and nothing assembled them.**

| the plan asked for | what was already there |
|---|---|
| U1 · a held situation states its score | `situation_bso.l1_refusal()` **already returns** `{"highest_bp", "floor_bp"}` |
| U3 · a durable refusal ledger | `situation_admission_decisions` **already is one** — `outcome`, `reasons`, the candidate's bytes, `reevaluate_after` |
| U4 · a totality guard over the reasons | the idiom exists **twice** — `patterns/routing.UNROUTED_PATTERN_TYPES` and `lane_health.SILENT_LANES`, both *"declared, with a reason and a mover"*, both checked in both directions |

So the step is **not** "build the accounting". It is **"assemble it, and extend the declared-silence
idiom from patterns to DOMAINS"** — which is smaller than planned and exactly matches the code's own
complaint, that the numbers exist and no surface speaks them.

**The build follows the premise.** Nothing was re-implemented: `l1_refusal` is *called* per held
situation rather than its rule re-written in SQL, and `reason_for()` is *read* rather than passed in
by a caller who could disagree with the declaration.

---

## 2. ⛔ THE FINDING — a number this plan was built on was wrong by 3.4×

The plan, `00-OVERVIEW.md` and step 8 all carried this:

> *"534 capabilities (Admin 211 / Sales 156 / Support 167), **200 admissible (37%)** — so
> `require_admission=True` at cutover takes **334 dark**."*

**Measured, by loading the catalog and calling the compiler's own admission rule:**

```
domain                total  admitted  unreadable  hollow
admin                    59        59           0       0
customer_support         49        49           0       0
sales                    47        47           0       0
ALL                     155       155           0       0
```

### 2.1 · Where 534 came from

`211 / 156 / 167` are **file counts**, not capability counts. A capability is a *directory*:

```
capabilities/01-executive-support/approval-coordination/
    capability.yaml      ← the capability
    objects.yaml         ← its load-set
    knowledge.yaml       ← its manifest
```

`59 × 3 = 177`, plus 34 variant files, `= 211`. The corpus is **155 capabilities**, and the 37% was
a file count divided into a capability count.

### 2.2 · Verified independently of the rule

Not taken on the resolver's word. Every one of the 155 was re-checked directly:

| gate | result |
|---|---|
| `identity.stub` | false on all 155 |
| `identity.status == "stable"` | 155 |
| `metadata.review_status == "approved"` with a named reviewer | 155 |
| `admission.accepted_content_hash` **recomputed** with `semantic_hash(content − admission)` | **155 verify, 0 mismatched** |

### 2.3 · Where the 37% came from — three document kinds, one denominator, one rule

`211` is every YAML file under `Admin Expertise/capabilities/`. That directory holds **three kinds
of document**, and the pre-flight ran the **capability** ceremony over all of them:

| under `capabilities/` | Admin | judged by | carries a content hash? |
|---|---|---|---|
| `capability.yaml` | 59 | `_admission_reason` | **yes** |
| `objects.yaml` · `knowledge.yaml` | 118 | **nothing** — never passed to either rule | no |
| situation files, nested beside their owner | 34 | `situation_admission_reason` | no, by design |

`59 + 118 + 34 = 211`. The 118 companions can never pass a ceremony they are not subject to, so
they land in the failing column and drag the percentage down. **The denominator and the rule
disagreed about what was being counted.**

---

## 2b. ⛔ THE SECOND FINDING — 24 of 69 authored situations cannot instruct

Measuring the situations with **their own** rule found something real that the wrong denominator
had buried:

```
domain                caps  unreadable  hollow  situations  draft
admin                   59           0       0          34      8
customer_support        49           0       0          20     16
sales                   47           0       0          15      0
ALL                    155           0       0          69     24
```

⛔ **Customer Support carries two thirds of the gap: 16 of its 20 situations.**

### 2b.1 · What a `draft` situation costs, in the rule's own words

> *"the gap lands in `admission_gaps` → `plan.admitted=False` → the package's
> `review_state='draft'` → **`deliver/pipeline._apply_abstention` downgrades the card to an
> OBSERVATION.** The intelligence still ships; **it stops instructing.** Removing the situation
> would delete the finding to punish its prose."*

So a Customer Support situation routing through one of those sixteen produces a card that says
*what is happening* and cannot say *what to do*. **That is "domain expertise kuch kaam nahi kar
raha", exactly, and it is one word per file.**

### 2b.2 · The cheapest quality win in Layer 2

`identity.status: draft` → `stable`, by an author, on 24 files. No code, no migration, no model.
The report now names the number so somebody can decide whether those 24 are genuinely unfinished
or merely un-flipped.

### 2b.3 · And a stale count beside it

`situation_admission_reason` says *"24 of 62 authored situations"*. **The 24 is still exact; the
62 is now 69.** Seven situations were authored since, and the failing count happening to stay put
is precisely how a stale denominator survives being read.

---

## 2c. ⛔ A caller-error guard that answers like a data verdict — noticed, not silently fixed

```python
identity = (authored.get("identity") or {}) if hasattr(authored, "get") else {}
```

`situation_admission_reason` takes a **mapping**. Handed a `SourceDocument` — which has no `.get`
— it reads `{}` and answers **`identity_status_absent` for every document**, which reads exactly
like a corpus where nobody set a status.

**It caught the author of this step within a minute.** The first measurement reported *"all 69
situations inadmissible"*, and only re-reading the compiler's own call site
(`authored = domain.situations[situation_id].content`) showed the call was wrong, not the corpus.

The production path is **correct** — the compiler passes `.content`. This is not a live defect. It
is a guard that converts a type error into a plausible wrong answer, and per the working rule
— *"noticed something adjacent? new unit, not a silent fix"* — it is **recorded here and left
alone**, with a comment at the one call site this step added.

---

## 2d. What this changes in the plan

| | was | is |
|---|---|---|
| **step 8's cutover cost** | 334 capabilities go dark at `require_admission=True` | **zero.** The flag is free |
| **step 4's diagnosis** | "the corpus is half-inadmissible" | the capabilities are **healthy**; the gap is **24 draft situations** and a **missing fundraising corpus** |
| **step 4's largest item** | the admission gap | **authoring** — and it always was |
| **`l3-corpus-is-not-empty` memory** | "211 Admin capabilities" | **59** |

⛔ **And this is the step's own thesis happening to the step's own plan.** A refusal that was right
and invisible — except here it was a refusal that *was not happening at all*, and nobody could tell,
because **nothing printed the number**. That is why `--corpus-only` exists: the corpus is on disk, it
was always countable, and the count waited on a database it never needed.

### 2.4 · A stale count in prose, corrected

`_hollow`'s docstring said *"136 of the corpus's capabilities are `stable`, `approved` and
hash-pinned over a file whose own notes read 'Phase 1 stub'"*. **True when written. 0 of 155 today.**

It is now marked as history, the rule it justifies is kept, and the **count moved into
`corpus_health()` where a test can run it** — because a count in prose is a count that goes stale,
and this repository has caught that exact drift five times.

---

## 3. What was built

| | |
|---|---|
| `context/domain_silence.py` | `DARK_DOMAINS` — `fundraising` and `general`, each with a reason and an **ENDS WHEN** |
| `context/quality/refusals.py` | the report, **pure** — no DB, no clock, no contract import |
| `packs/compiler/capability_resolver.py` | `ADMISSION_REASONS` · `DomainHealth` · `domain_health()` · `corpus_health()`, **beside the rule they read** |
| `scripts/l2_refusal_report.py` | read-only, resolved through `scripts/_db.py`; `--corpus-only` needs no database |
| 3 test files | **29 tests**, every one RED first for the stated reason |

### 3.1 · The reason table is built from the enum, never from a second list

```python
def _reason_table() -> dict[str, int]:
    from genios_engine.context.situation_publisher import HoldReason
    return {reason.value: 0 for reason in HoldReason}
```

An eighth `HoldReason` appears in the report **the day it is added, at zero**, without anybody
remembering. Same for `ADMISSION_REASONS`: `canonical_admission_reason()` **raises** on a reason the
table does not declare, rather than silently dropping it into an "other" bucket.

### 3.2 · `None` is not zero, and the sentence says so

```
s0: its best evidence scored 1360 against a floor of 2500
s2: its evidence was never scored — no judgement was made, and none should be read into this
```

*Never assessed* and *assessed-then-refused* are different facts, and only the second is a judgement
Layer 1 made. Rendering the first as `0` would invent a verdict.

### 3.3 · Four numbers, four different repairs — kept apart on purpose

| number | who fixes it |
|---|---|
| **held** | nobody — *"the refusal is correct"*, the floor stands |
| **dark domain** | an **author**, writing a corpus. Not code |
| **inadmissible capability** | a **reviewer**, running the ceremony |
| **hollow capability** | an **author**, writing content into an approved shell |
| **draft situation** | an **author**, flipping one word — and it is the cheapest of the five |

Summing them gives one number that sends whoever reads it to the wrong person. `silent_total`
deliberately excludes the corpus: **a capability is not a situation.**

---

## 4. Wiring check — the report assembles, against the pilot's measured shape

Driven with the 63 held / 96 admitted from `l1_refusal`'s own docstring:

```
admitted      96          qes_required                 63
held          63          verified_evidence_required   63
                          [+ 5 reasons at 0]

REFUSED BY LAYER 1, WITH THE NUMBER IT MISSED BY
  s0: its best evidence scored 1360 against a floor of 2500
  s2: its evidence was never scored — no judgement was made...

DOMAINS NO AUTHORED CORPUS CAN READ
  fundraising: 14 situations minted, none readable

THE AUTHORED CORPUS
  domain                caps  unreadable  hollow  situations  draft
  admin                   59           0       0          34      8
  customer_support        49           0       0          20     16
  sales                   47           0       0          15      0
  ALL                    155           0       0          69     24

  ⛔ 24 authored situations are still `draft`. Any card built from one is
     downgraded to an OBSERVATION — it describes, and it does not instruct.

TOTAL SITUATIONS PRODUCING NOTHING: 77
```

⛔ **`qes_required` 63 and `verified_evidence_required` 63 reproduces the code's own claim** that
they are *"the SAME cards rather than two gaps"* — the report is not merely running, it is agreeing
with the measurement it was built to explain.

**77 is a number that did not exist before this step.**

---

## 5. Completion criteria

| # | criterion | |
|---|---|---|
| 1 | one report naming every refusal path, with counts | **✅ built · ⚠️ the DB half awaits Harsh.** The corpus section runs today and is in §2 |
| 2 | a held situation states its score against its floor | ✅ `ScoredRefusal.sentence` |
| 3 | `UNROUTED` counted with its domain | ✅ `DARK_DOMAINS`, named with a mover, checked both directions |
| 4 | the ledger is durable and survives the sweep | ✅ **already true** — `situation_admission_decisions`. §1 |
| 5 | a totality test refuses a new `HoldReason` no surface reports | ✅ and the same guard added for `ADMISSION_REASONS` |

**Four closed. One half-closed, and the open half is a database, not a design.**

---

## 6. What this step does NOT do

* **It does not lower the floor.** 2500 stands. The refusal is correct.
* **It does not run against the pilot.** Every count in §4 is the *measured shape* replayed through
  the real code, not a live read. **Harsh item 1.**
* **It does not fix the `general` catch-all.** It declares it, with what would end it.
* **It does not author the fundraising corpus.** That is authoring, and it is step 4's largest item.
* **It does not count untraceable commitments separately.** They arrive as
  `verified_evidence_required`, which is where the ledger puts them — a second counter would be a
  second answer.
* **It does not flip the 24 draft situations.** Whether they are unfinished or merely un-flipped is
  an authoring judgement, and this step's job was to make somebody able to ask.
* **It does not harden `situation_admission_reason`'s `hasattr` guard.** §2c — recorded as its own
  unit, because a silent fix to an adjacent file is how a step stops being reviewable.
