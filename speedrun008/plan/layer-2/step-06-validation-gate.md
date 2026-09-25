# L2-6 · The gate — a proposal becomes a situation

**Needs Harsh:** no · **Migration:** none · **Model calls:** ⛔ **none, and that is the point**

> ## ✅ COMPLETE — 2026-09-24 · [findings](findings/step-06-validation-gate.md)
>
> 37 tests · 13,030 passed · 0 regressions · no migration · **zero model calls, proven by AST**.
>
> ⛔ **THE FOUR CHECKS HAD TO BE RE-AIMED.** Check 2 reads `inferred_state → must cite ≥1
> observed_fact`; **neither field exists.** L2-2 measured that v2 is already full of interpretation
> and classified its 28 fields rather than minting six more. So a PROPOSAL is `{field: value}` over
> `model_writable_fields()` — **the list L2-2 built for exactly this caller.** This is where that
> classification stops being a table and becomes a gate.
>
> ⛔ **AND THE UNPLANNED CHECK IS THE ONE §1 ACTUALLY DESCRIBES:** *"a model that can write
> `observed_facts` is a model that can invent a fact"* — now enforceable, because the fields are
> classified. 14 a model may propose, 14 it may never.
>
> ⛔ **THE BINARY GATE PROTOCOL NEARLY SWALLOWED `UNKNOWN`.** `consult` returns RAN only when the
> value is not `None`; an UNKNOWN returned as `None` is **retried and filed as a failed
> generation** — a correct refusal made to look like a broken model. It rides inside the value.
>
> ⛔ **THE BLUNT-GREP MISTAKE, MADE FOR THE THIRD TIME.** The zero-model-calls probe grepped this
> module for `"client"` and matched **the docstring saying it has none.** Steps 14 and 18 recorded
> the same mistake. It now parses the AST.

---

## 0. ⛔ CORRECTED — L2 owes the validator, not the gate

The gate exists. `RSiteGate.consult` step 6 is **"validate the output — the caller's validator (the
V-gauntlet, for R-2)"**, and step 7 is **"on any failure: deterministic fallback, recorded — never a
retry storm, never silence."**

**So this step writes L2's validator and hands it to the existing gate.** The four checks below are
that validator's contents. Everything about *when* a model may be consulted, what it costs and what
happens when it fails is already solved and property-tested.

---

## 1. Premise — the validator is what makes a cheap model safe

The reasoner is Haiku. Haiku makes mistakes. **Haiku is affordable precisely because a deterministic
gate catches them:**

```
HAIKU proposes        ← will be wrong sometimes
    ↓
GATE                  ← deterministic, free, fixed
    ↓
pass → commit  ·  fail → escalate or refuse
```

⛔ **Without the gate you need Sonnet everywhere, because nothing would catch the error.** The gate
is not tidying-up. **It is the cost strategy.**

And it is the same pattern the engine already runs on — *"model proposes, deterministic system
validates and commits"* — which is how `org_rule_extract` lets a model near approval thresholds
without ever letting it emit a number.

---

## 2. The four checks

### Check 1 · Schema
Structured output parses, enums are members, basis points are integers. **V-7: no floats.**

### Check 2 · ⛔ Every claim resolves to a receipt
The heart of the gate.

```
inferred_state  →  must cite ≥1 observed_fact
observed_fact   →  must cite ≥1 evidence_ref
evidence_ref    →  must RESOLVE inside the Evidence Graph
```

A citation that does not resolve is a **fabricated receipt**, and it is refused exactly like an
unanchorable claim is refused in L1 — *"an unanchorable claim is kept and flagged, never invented."*

### Check 3 · Contradiction
Does the interpretation contradict an active fact? Not *"is it surprising"* — **is it in conflict
with a held value**, the same question `write_fact` already asks when it raises a discrepancy rather
than overwriting.

### Check 4 · Uncertainty survives
⛔ Empty `unknowns` + `coverage_ready = false` → **refuse**. The model does not get to decide the
data was complete.

---

## 3. Units

### L2-6-U0 · The four checks as pure functions
No I/O, no clock, `eval_time` a parameter. **Testable without a database**, which is what made L1's
`validate/` the strongest package in that layer.

### L2-6-U1 · Evidence-ref resolution against the graph
The one check that must touch storage. Bounded, batched — **resolve all refs in one read**, never
one query per claim.

```
verify:  pytest tests/context/test_refs_resolve_in_one_read.py -q
```

### L2-6-U2 · The outcome is typed and has four values
Not pass/fail. L1 learned this the hard way when a binary gate held 367 candidates and admitted 18:

```
ACCEPT    → commit
ESCALATE  → Sonnet, once
REFUSE    → recorded with its reason, never silently dropped
UNKNOWN   → committed AS unknown, which is a real answer
```

### L2-6-U3 · Every refusal is written down
**`REFUSE ≠ DELETE`.** A refused proposal lands in a ledger with its check, its claim and its
reason — so *"why didn't GeniOS tell me?"* has an answer that is not a code read.

```
verify:  pytest tests/context/test_every_refusal_has_a_row.py -q
```

### L2-6-U4 · A mutation probe for each check
⛔ **Technique 3, from L1 step 17:** neutralise the check and confirm the probe goes red. *"A probe
that passes with the fix removed proves nothing."* Four checks, four probes, each proven sensitive
to its own check.

---

## 4. What this step does NOT do

* **It does not call a model** — including to judge the model. A verifier that is itself a model
  doubles the bill and inherits the failure mode.
* **It does not silently repair a proposal.** It accepts, escalates, refuses or records unknown.
* **It does not replace the eight admission laws.** It runs before them; they still gate publication.

---

## 5. Completion criteria

| # | criterion | verdict |
|---|---|---|
| 1 | four checks, pure, one batched resolution | ✅ **six** — the four planned, with `unresolved` split from `receipt`, plus **authority** |
| 2 | four outcomes, not two | ✅ and the gate's **binary protocol** nearly swallowed `UNKNOWN` — §4 of the findings |
| 3 | every refusal has a durable row naming its check | ✅ **already true at the gate**; this step made the *check and subject* durable by putting them in the reason CODE, because `record_call` persists codes and **not** `trace` |
| 4 | mutation probes, each proven sensitive | ✅ **six, and they neutralise the RULE** — `model_may_write`, `RECEIPT_REQUIRED`, `fact_write_action` — which proves the check reads it rather than owning a copy |
| 5 | zero model calls, proven | ✅ **by AST.** The grep version matched this module's own docstring — the third time that mistake has been made here |
| 6 | handed to `RSiteGate` — not a second gate | ✅ **driven through the real gate**: ACCEPT and UNKNOWN record RAN, REFUSE records FAILED_VALIDATION with its code, and **the gate owns the retry** |

**All six closed. Nothing deferred, nothing owed to Harsh.**

### 5.1 · What the units became

| planned | built |
|---|---|
| U0 · four checks, pure | ✅ `context/proposal_gate.py` — six, every rule **read** |
| U1 · refs resolve in one batched read | ✅ **handed in**, called once, **not at all when nothing cites** |
| U2 · four typed outcomes | ✅ and §4 — the one that mattered was `UNKNOWN` |
| U3 · every refusal written down | ⛔ **already true.** `RSiteGate._record` — *"every gate outcome on the record, skips included"* |
| U4 · a mutation probe per check | ✅ six, aimed at the **rule** |
| — | **unplanned: the authority check.** §1 argued for it and could not write it; L2-2 made it possible |
