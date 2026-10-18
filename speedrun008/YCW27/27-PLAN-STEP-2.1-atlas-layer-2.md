# ⛔ STEP 2.1 · ATLAS LAYER 2 — the nine open claims

**Written 2026-10-03, after the re-check and before any build**, because the rule this programme
learned the hard way is that *the Atlas check comes first*: planning a layer against six-week-old
badges cost three invented units and missed two live defects the one time it was done last.

Phase 1 closed with 52 candidates raised and 52 retired. This is the largest remaining block.

---

# PART 1 · THE RE-CHECK — nine claims, measured against today's code

| claim | 2026-10-01 verdict | ⛔ 2026-10-03 re-measurement |
|---|---|---|
| **L2-01** | STILL TRUE | ⛔ **refined and sharpened** — see `U02` |
| **L2-02** | STILL TRUE | unchanged. Mover is `H8.5`, a read-only query already on Harsh's page |
| **L2-03** | STILL TRUE | ⛔⛔ **WRONG — CLOSED IN CODE.** See `U04` |
| **L2-04** | STILL TRUE | ⛔ **two retractions of my own first reading** — see `U03` |
| **L2-05** | STILL TRUE | unchanged, and `reason/unit_health.py:142` already names the root in its own words: *"ONE ROOT, FOURTEEN SYMPTOMS. There is no CRM connector, so the deal object barely exists."* **Rohit's** |
| **L2-07** | STILL TRUE | unchanged — this IS the ConfidenceVector axes decision (`02-DECISIONS` #1). **Rohit's** |
| **L2-09** | PARTLY EXPIRED, ⛔ *not re-measured* | ✅ **now measured, and mostly closed** — see `U04` |
| **L2-11** | STILL TRUE | ⛔⛔ **found in code, at a named line** — see `U01` |
| **L2-12** | STILL TRUE | ✅ confirmed absent: no replay machinery anywhere in the engine. A tenant replay is a **product decision** about reprocessing cost, not a missing function. **Rohit's** |

## ⛔ What the re-check cost me, recorded because the cost is the lesson

**Three corrections before a single line was built.** Every one came from broadening a measurement
I had already drawn a conclusion from — the same discipline that produced six retractions in the
`context/` audit.

1. ⛔ **"`AuthorityBasis` is computed and thrown away."** **WRONG.** `capture/pipeline.py:1685`
   persists it. I had read the function that *returns* it and not the caller that *records* it.
   The true finding is narrower and better, and it is `U02`.
2. ⛔ **"Two call sites disagree about `domain_ids`' arity."** **WRONG, and it would have been an
   unfair finding.** `citations.py:127` builds a `domain:<id>` TAG SET, where taking every entry
   is correct; routing takes one, which is also correct. The real defect is that the routing pick
   is **silent**, and that is `U01`.
3. ⛔⛔ **"Three of L2-04's four views are absent."** Drawn from **module filenames**, which is
   precisely *a name that is not distinctive is not evidence*. `authority_view.py` exists and calls
   itself *"the eighth view over the one graph"*; the ownership data is written as facts; and the
   genuine finding turned out to be something else entirely. `U03`.

---

# PART 2 · THE UNITS

Four. Fewer than the nine claims, because the re-check closed two and three are Rohit's.

## ⛔⛔ U01 · L2-11 — the silent first-domain pick · **receipt 45**

**The Atlas claim:** *"Wrong first domain or restricted mixed-domain evidence can still enter the
wrong view."* Six weeks old, graded STILL TRUE, and never located in code. It is here:

```python
# genios_engine/reason/adapters/expertise.py:1462-1463
domain_ids = package.metadata.get("domain_ids") or ()
domain = str(domain_ids[0]) if domain_ids else "general"
```

**Why this is the real defect and not a style complaint.** `domain` selects which domain's
**expertise** the reasoning runs with — the playbook. With two entries in the list, `[0]` routes to
one domain's playbook, the package's own citation tags carry **both** (`citations.py:127` adds a
`domain:<id>` for every entry), and **no line anywhere records that a choice was made**. Two
surfaces would then disagree about the same package, and nothing would explain why.

**Why it does not fire today, and why that is not a defence.** The only writer,
`context/situation_bso.py:1577`, emits `[str(domain)] if domain else []` — length 0 or 1. So `[0]`
cannot currently pick wrong. ⛔ But `situation_publisher.py:231` and the contract both type the
field as a tuple of **any** length. **The safety is a coincidence, not a rule** — exactly the shape
Phase 1 built six guard suites against.

✅ **The fallback is legitimate and needs no change.** `"general"` is a real spec'd domain
(`domain_spec.py:660`) and `domain_spec.py:142` normalises an empty name to it.

**Feasibility, verified end to end before planning the unit:**

| step | fact |
|---|---|
| persisted? | ✅ `expertise_packages.payload` is `jsonb`, written from `to_semantic_dict()` |
| survives the filter? | ✅ that dict carries `"metadata": self.address_free_metadata`, and `_NON_CONTENT_METADATA = ("brain_subject_keys",)` excludes that key and no other |
| the query | `select count(*) from expertise_packages where jsonb_array_length(coalesce(payload->'metadata'->'domain_ids','[]'::jsonb)) > 1` + `:org` |
| kind | **correctness** — `expect(0) is True` |
| derivation | the metadata key from the writer and the exclusion set from `_NON_CONTENT_METADATA`. ⛔ Spell neither |

⛔ **One ambiguity to name rather than hide:** the TABLE belongs to L3 (`0047_l3_domain_compiler.sql`)
while the PICK belongs to L2. The receipt is labelled **L2** because the claim is about the pick,
and the docstring says so — the programme has been burned once already by two vocabularies sharing
one field.

**Deliverable:** receipt 45 · a guard suite · a mutation run with the baseline asserted both sides.

## ⛔ U02 · L2-01 — the unmapped authority floor, and the two numbers that mean two things

**The Atlas claim:** *"`graph_store.py` protects against stale/replay overwrite… Incorrect
authority configuration would still be applied consistently."* Graded STILL TRUE with the note that
the guard is correctness-of-**ordering**, not correctness-of-**config**. That is right, and
underneath it is something measurable.

`capture/validate/authority.py` resolves a rank through four tables in order and, when none
matches, returns the floor **with a warning**, and says why in its own words:

> *"Doc 05's acceptance, in full: rank 0 AND a warning. The warning is the half that gets the table
> fixed — a floor that is silent is indistinguishable from a correct answer, and the source stays
> under-ranked for as long as nobody looks."*

⛔ **Three things are true at once, and together they defeat that mitigation:**

| | |
|---|---|
| 1 | `UNMAPPED_AUTHORITY` is `inferred`, whose rank is **0** — and `inferred` is also a *legitimate* basis. **An unmapped source and a genuine inference are the same number** |
| 2 | `graph_store.write_fact`'s default is `authority_rank: int = 1`, and **1 is `chat_aside`**. A caller that passes nothing writes a fact that reads as a chat aside |
| 3 | `AuthorityBasis.UNMAPPED` — the one value that distinguishes "this is a floor" from "this is a measurement" — is recorded on **exactly one lane's trace** (`capture/pipeline.py:1685`, `STRUCTURED_STAGE`). Nowhere else does the basis survive the seam |

So the code's own named mitigation reduces to a `log.warning` — and **a log line is not a reader**,
the rule L6 produced and L4 paid for.

**Deliverable:** this is a **declaration unit, not a repair.** ⛔ Changing either number is a data
migration over `graph_facts` and is **not mine to decide**. What is mine: write the collision down
in the one place a reader will meet it, guard the declaration in **both** directions so neither the
collision nor its disappearance can go unnoticed, and put the question on Rohit's page with its
cost stated.

## ⛔ U03 · L2-04 — the views, and a count with no list behind it

**The Atlas claim:** *"explicit complete authority/ownership/resource/use-restriction views… are
absent."*

⛔⛔ **My first reading was wrong twice and the second mistake is the interesting one.**

| my first reading | ⛔ what measuring properly showed |
|---|---|
| "all four absent" | **`authority` is built** — `context/authority_view.py`, L2.1.4, with three stated laws (an inferred rule never enforces · absence is not permission · authority is historical) |
| "ownership absent" | the **data** is there: `commitment.owner` is written as a fact, and `context/pipeline.py:1948` records why — `executive/assignment.resolve_owner` *cannot see edges*, which once left *"all 43 carry `assignee = NULL`"*. What is absent is a **read surface**, which the same file calls *"the distinction an ownership surface is built out of"* |
| "`use_restriction` absent — 0 files" | ✅ still the measurement, but it was reached by **grepping a name**, and a name is not evidence. The nearest built concept, `capture/visibility_rules.py`, governs **audience**, not **use** — those are different questions and neither substitutes for the other |

⛔ **And the finding nobody was looking for.** `authority_view.py` opens with *"The eighth view over
the one graph"*. **Nothing in the repository enumerates eight views.** The phrase appears exactly
once, engine-wide. It is a number in prose with no list behind it — *a stale comment reads as a
measurement*, and this one cannot even be checked.

**Deliverable:** measure the view surfaces, declare what exists and what does not **with the
concept named rather than the filename**, correct or substantiate the "eighth" count, and hand the
three unbuilt views to Rohit as the product call they are. ⛔ **Building three graph views is not a
unit I may mint for myself.**

## U04 · paperwork — two scorecard rows that are now wrong

⛔ No code. The scorecard is what the build order rests on, so a stale row there is more expensive
than a stale comment.

**L2-03** — *"First claimant owns a same-name alias, so later name-only prose can attach to the
wrong human."* **Closed in code**, and the chain holds in both directions:

```
observe_person_name   a SECOND LIVE person by the same name → origin='contended'
resolve_alias         excludes contended, AND returns None on 2+ rows
resolve_alias_candidates   so a surface can SEE an ambiguity rather than infer it
tests/context/test_a_person_the_graph_knows_by_name.py   guards it
```

The docstring states the law — *"A name shared by several anchored people resolves to NOBODY, not
to the first claimant"* — and, unusually, the implementation earns it: the writer marks, the reader
excludes, and a third function exists so "nobody" and "several" are not conflated.

**L2-09** — the half graded *not re-measured* is now measured, and it splits:

| | |
|---|---|
| importance | ✅ expired already — `compose_situation_importance`, with `importance_source` in metadata and a named fallback |
| ⛔ relationships / dependencies | **TRUE**: `context/situation_bso.py` is 2,133 lines and mentions `relationships` **0** times and `dependencies` **0** times (against evidence 66, anchor 55, entities 7). But it is **declared twice** — `contracts/situation.py`'s GAP FLAG and `contracts/dependency.py` — and both name the X8 cutover that closes it |
| ✅ *"0 derived facts"* | the number lives in `context/conversion.py`, the census built for exactly this, and it has a **writer** (both correlators call `record_conversion`) **and a reader** (`runner.py:1400` `read_conversion`) **and a test**. ⛔ This is the one I expected to find unread, and it is not |

---

# PART 3 · WHAT GOES TO ROHIT

Three claims are design decisions, not gaps, and no amount of building closes them:

| claim | the decision | why it cannot be mine |
|---|---|---|
| **L2-02** | are two source labels independent causal authorities? | the mover is a read-only measurement, already `H8.5` on Harsh's page |
| **L2-05** | a CRM connector that writes the deal object | `unit_health.py` already calls it ONE ROOT, FOURTEEN SYMPTOMS |
| **L2-07** | the ConfidenceVector axes | open since `02-DECISIONS` #1; 2 of 6 axes overlap with the Atlas |
| **L2-12** | a tenant replay | a cost decision about reprocessing, not a missing function |
| ⛔ **U02's two numbers** | renumbering `inferred`, or changing `write_fact`'s default | a data migration over `graph_facts` |
| ⛔ **U03's three views** | ownership · resource · use-restriction | three new read surfaces is a roadmap item, not a unit |

---

# PART 4 · ORDER AND DEFINITION OF DONE

```
U01  receipt 45 + guard + mutations      ⛔ the only live, buildable defect
U02  the declaration, guarded both ways  ⛔ not a repair
U03  the measurement + the declaration   ⛔ not three views
U04  the two scorecard corrections       no code
```

Bottom-up, one unit at a time, each with its own suite run. **Done** means: the full suite green
with zero skips introduced, every mutation caught or reported as invalid with its reason, the
audit written, and `19-PENDING` carrying whatever turned out to be Rohit's.

⛔ **Not done** means anything claimed without the command having been run and its output read.


---
---

# ⛔ CLOSED 2026-10-03 · PLAN vs ACTUAL

Recorded here rather than only in the audit, because a plan that is never compared to its outcome
teaches nothing the next time.

| | planned | ⛔ actual |
|---|---|---|
| **units** | 4 | **4** — the shape held |
| **receipts** | 1 (`U01`) | **2** — `U02` turned out to be receiptable after all. The plan called it *"a declaration unit, not a repair"*, which was right about the repair and wrong about the measurement |
| **tests** | — | **50** (18 · 20 · 12) |
| **mutations** | — | **49 valid, 49 caught · 0 surviving · 2 invalid** |
| **corrections** | 3 anticipated, and the plan said so up front | ⛔ **11**, nine to my own first reading |

## ⛔ Where the plan was wrong, and it was wrong in the same direction twice

**1 · `U01` was described as "safe today".** The plan said *"the only writer,
`context/situation_bso.py:1577`, emits length 0 or 1, so `[0]` cannot currently pick wrong"*, and
called the risk a coincidence rather than a defect. ⛔⛔ **There is a SECOND writer.**
`packs/compiler/expertise_builder.py:87` writes `plan.domain_ids`, which is
`tuple(sorted(selected_domains))` over a **set**, and a situation with no usable hint resolves
against *every authored domain*. The defect is **live**, not latent — and the plan missed it by
grepping one spelling of the key and stopping at the first writer found.

**2 · `U02` was described as not measurable.** The plan said the finding was *"a declaration unit,
not a repair"* and that *"changing either number is a data migration and not mine to decide"*. The
second half is still true and `R16`/`R17` are Rohit's. ⛔ But between "declare it" and "migrate it"
there was a receipt the plan did not see: **has the collision ever actually happened?** That is
`select … having bool_or(rank <= 6) and bool_or(rank > 6)`, it is zero-expected, and it goes red
exactly when the hazard becomes a corruption. **Receipt 46.**

⛔ **Both misses are the same mistake**: stopping at the first measurement that supported the
conclusion. The first said "one writer, so it's safe"; the second said "a migration, so there's
nothing to build". *Broaden the measurement before you believe it* — which is already a rule in
this programme's memory, and it still had to be learned again here.

## ✅ Where the plan was right, and worth keeping

* **Doing the re-check before drawing units.** Two of the nine claims were stale and three are
  Rohit's — so the nine became four, and `U04` existed only because the re-check found the rows
  wrong. Planning against the six-week-old badges would have produced nine units, five of them
  fictional.
* **Naming the ambiguity rather than hiding it.** Receipt 45's table is L3's and its claim is L2's;
  the plan said to say so out loud, and the declaration does.
* **Refusing to mint "build three graph views" as a unit.** It is a roadmap decision, it is
  declared as one, and a test asserts every absent entry says `Rohit's`.
