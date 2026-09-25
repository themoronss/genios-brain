# L2-6 · The validator — findings

**Run:** 2026-09-24 · premise checked BEFORE any code · **no migration · no model call**
**Against:** `speedrun008` @ `25eb22ca`
**Result:** 37 tests, **13,030 passed · 14 failed (all pre-existing) · 0 regressions**

---

## 1. ⛔ The four checks had to be re-aimed, because L2-2 did not build the fields they name

Check 2, as written:

```
inferred_state  →  must cite ≥1 observed_fact
observed_fact   →  must cite ≥1 evidence_ref
```

**Neither field exists.** L2-2 measured that v2 is **already full of interpretation** — its own
comments say `visibility` is *"a DERIVED claim"*, `missing_facts` entries are *"FINDINGS"*, and
V-4…V-7 exist precisely because trends and correlations can be wrong — and **classified the 28
fields it has** rather than minting six more, deferring the genuinely absent ones to L2-5 with
their writer.

**So a PROPOSAL is `{field: value}` over `claim_state.model_writable_fields()`** — the list L2-2
built for exactly this caller:

> *"L2-5's gate needs this list, and deriving it by hand at the call site is how the list and the
> rule stop agreeing."*

⛔ **This is the step where L2-2's classification stops being a table and becomes a gate.**

---

## 2. Every rule is READ, never re-implemented — and a probe proves each one

| check | the rule it consults | where it already lived |
|---|---|---|
| **schema** | `require_no_float` | V-8 |
| **authority** | `claim_state.model_may_write` | **L2-2** |
| **receipt** | `contracts.situation.RECEIPT_REQUIRED` | **L2-2, V-9** |
| **unresolved** | the handed-in resolver | new — U1 |
| **contradiction** | `graph_store.fact_write_action` | already a pure function |
| **completeness** | V-10's reading | **L2-2** |

⛔ **The mutation probes neutralise the RULE, not this module's code.** Breaking `proposal_gate`
would only prove its own code runs; breaking `model_may_write`, `RECEIPT_REQUIRED` and
`fact_write_action` proves the check is genuinely reading what it claims to — the property that
stops a second copy being written later. Six probes, six checks, and a totality test refuses a
check with no probe.

---

## 3. ⛔ The unplanned check — authority — and it is the one §1 actually describes

The plan's §1 argues *"a model that can write `observed_facts` is a model that can invent a
fact"*, then never turns it into a check, because it assumed those fields would be new.

**They are not new; the classification is.** So:

```
a model MAY propose (14)   anomalies · cohort_positions · confidence · conflicts · correlations
                           coverage_ready · domain_ids · importance · matched_conditions
                           missing_facts · pattern_id · state · trends · type

NEVER (observed, 8)        conflict_ids · dependencies · entities · evidence · provenance_refs
                           relationships · signal_ids · timeline
NEVER (envelope, 6)        id · metadata · org_id · schema_version · trace_id · visibility
```

`visibility` is refused for its own stated reason: **a model that may set it may widen an
audience.** `metadata` likewise — *"writing the bag is writing anything in it."*

---

## 4. ⛔ The four outcomes had to survive a binary protocol, and UNKNOWN was the one at risk

`RSiteGate.consult`:

```python
value, codes, record = validate(...)
if value is not None:
    return ConsultResult(outcome=OUTCOME_RAN, value=value, …)
last_outcome = OUTCOME_FAILED_VALIDATION      # → retry, then fail
```

**The gate's protocol is binary.** An UNKNOWN returned as `None` would be **retried and filed as a
failed generation** — a correct refusal made to look like a broken model, which is the exact
defect L2-0 spent a step on.

So the outcomes ride inside the value:

| outcome | to the gate | why |
|---|---|---|
| **ACCEPT** | the value | commit |
| **UNKNOWN** | a value | *the model declined to conclude* is an answer, and it commits |
| **REFUSE** | `None` + codes | the gate retries once, then records it |
| **ESCALATE** | `None` + a code | ⛔ **the validator never escalates itself** |

**ESCALATE is a code the CALLER acts on.** The validator has no client and no budget, and *"no
R-site may call a model directly"*. A second consult at a higher tier is L2-5's decision, not a
verdict's side effect — proven by parsing this module's AST for any name that could reach one.

---

## 5. ⛔ The reason code carries the check and the subject, because the trace is not stored

`BundleStore.record_call` persists `reason_codes` as jsonb and **not** `trace`. So:

```
l2_authority:evidence          survives to a ledger somebody reads days later
{"check": …, "claim": …}       does not
```

Every refusal is therefore `<check>:<subject>` — **the same shape L2-2 chose** for
`observed:V-9:anomalies[0]`. `CHECKS` is a declared table, so a check whose code nobody declared
cannot exist: **a refusal nobody can count is the defect L2-0 spent a step on.**

---

## 6. U3 was already true, and U1 is the only thing that touches storage

**U3 — every refusal written down.** `RSiteGate._record`: *"every gate outcome on the record,
skips included"*, with `reason_codes` persisted. **Nothing was built; the premise check found it.**

**U1 — refs resolve in one read.** `resolve_refs` is **handed in**, never fetched — the same
doctrine L2-3 spent a step on (*"a fetched slice cannot be replayed"*) and the same shape that
kept the import ratchet happy in L2-2. It is called **once with every ref**, and **not at all when
nothing cites**: a round trip bought for an empty set is a round trip bought for nothing.

A ref the Evidence Graph has never heard of is refused separately from a claim that cites nothing,
because **an unresolvable citation is worse than no citation: it looks like proof.**

---

## 7. ⛔ The blunt-grep mistake, made for the THIRD time and now made structurally impossible

`test_escalate_never_calls_anything_itself` first grepped this module's source for `"client"` —
and matched **the docstring explaining that it has none.**

| | |
|---|---|
| L1 step 14 | grepped a migration for `" not null"` and matched its own comment |
| L1 step 18 | repeated it, and recorded that it had been made twice |
| **L2-6** | **third time** |

**A blunt grep over a file that EXPLAINS a rule will always find the rule's own words.** The test
now parses the module and reads every `Name`, `Attribute` and import from the **AST**. Prose is not
code, and a probe that cannot tell them apart proves nothing about either.

---

## 8. Cost check

| | |
|---|---|
| model calls | **zero**, and proven by AST rather than by assertion |
| migration | none |
| runtime behaviour | **unchanged** — nothing calls this yet; L2-5 is its caller |
| I/O | one callable, handed in, invoked once, skipped when unused |

---

## 9. Completion criteria

| # | criterion | verdict |
|---|---|---|
| 1 | four checks, pure, no clock, no I/O except one batched resolution | ✅ **six** — the four planned plus `unresolved` split from `receipt`, plus **authority**, which L2-2 made possible |
| 2 | four outcomes, not two | ✅ and §4 — the binary gate protocol nearly swallowed UNKNOWN, which is the one that matters |
| 3 | every refusal has a durable row naming its check | ✅ **already true** at the gate; this step made the *check and subject* durable by putting them in the code |
| 4 | four mutation probes, each proven sensitive | ✅ **six**, and they neutralise the **rule** rather than this module — strictly stronger |
| 5 | zero model calls, proven | ✅ by AST, after the grep version proved a docstring |
| 6 | handed to `RSiteGate` — not a second gate | ✅ **driven through the real gate** with a fake client: ACCEPT and UNKNOWN record RAN, REFUSE records FAILED_VALIDATION with its code, and **the gate owns the retry** |

**All six closed.** Nothing deferred, nothing owed to Harsh.

---

## 10. What this step does NOT do

* **It does not call a model, including to judge one.** A verifier that is itself a model doubles
  the bill and inherits the failure mode.
* **It does not silently repair a proposal.** Accept, escalate, refuse, or record unknown.
* **It does not replace the ten admission laws.** It runs before them; they still gate
  publication, and V-9/V-10 still observe there.
* **It does not build the caller.** L2-5 is the consumer; this exists before it so the model site
  is born into a world where the rule is already enforced — *"a rule added after its writer is a
  rule the writer was built around."*
