# L2-6 · The gate — a proposal becomes a situation

**Needs Harsh:** no · **Migration:** none · **Model calls:** ⛔ **none, and that is the point**

---

## 1. Premise — the gate is what makes a cheap model safe

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

1. Four checks, pure, no clock, no I/O except the one batched ref resolution.
2. Four outcomes, **not two**.
3. Every refusal has a durable row naming its check.
4. Four mutation probes, each proven to go red when its check is neutralised.
5. Zero model calls in the gate — proven by the metering test.
